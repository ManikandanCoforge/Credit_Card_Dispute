#!/usr/bin/env bash
# Deploy the Card Disputes Copilot POC to AWS ECS Fargate behind an ALB.
# Idempotent: re-running creates only what is missing and rolls a new task revision.
#
# Requires: aws CLI v2 (configured profile), docker (running), bash.
# Usage:
#   ./deploy/poc/deploy.sh                 # build + push + deploy
#   CPU_ARCH=ARM64 ./deploy/poc/deploy.sh  # Graviton (needs docker buildx)
#   SKIP_BUILD=1 ./deploy/poc/deploy.sh    # reuse the existing image tag
set -euo pipefail
cd "$(dirname "$0")/../.."

REGION="${AWS_REGION:-us-east-1}"
NAME="${NAME:-ccd-poc}"
CPU_ARCH="${CPU_ARCH:-X86_64}"          # X86_64 or ARM64
CPU="${CPU:-512}"
MEMORY="${MEMORY:-1024}"
TAG="${TAG:-poc}"
ALLOW_CIDR="${ALLOW_CIDR:-0.0.0.0/0}"   # tighten to your IP/32 for anything shared

CLUSTER="$NAME"
SERVICE="$NAME-api"
REPO="$NAME-api"
ALB="$NAME-alb"
TG="$NAME-tg"
LOG_GROUP="/ecs/$NAME-api"
EXEC_ROLE="$NAME-exec"
TASK_ROLE="$NAME-task"

say() { printf '\n== %s\n' "$*"; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 not on PATH"; exit 1; }; }

need aws
need docker
need curl
docker info >/dev/null 2>&1 || { echo "ERROR: docker daemon not running"; exit 1; }

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR_HOST="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
IMAGE="$ECR_HOST/$REPO:$TAG"
PLATFORM="linux/amd64"
if [ "$CPU_ARCH" = "ARM64" ]; then PLATFORM="linux/arm64"; fi
echo "account=$ACCOUNT region=$REGION name=$NAME arch=$CPU_ARCH image=$IMAGE"

# --- 1. image ---------------------------------------------------------------
say "image"
if ! aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1; then
  aws ecr create-repository --repository-name "$REPO" --region "$REGION" \
    --image-scanning-configuration scanOnPush=true >/dev/null
  echo "created ECR repo $REPO"
fi
if [ "${SKIP_BUILD:-0}" != "1" ]; then
  aws ecr get-login-password --region "$REGION" \
    | docker login --username AWS --password-stdin "$ECR_HOST" >/dev/null
  docker build --platform "$PLATFORM" -f deploy/poc/Dockerfile -t "$IMAGE" .
  docker push "$IMAGE"
fi

# --- 2. logs + cluster ------------------------------------------------------
say "logs + cluster"
aws logs create-log-group --log-group-name "$LOG_GROUP" --region "$REGION" 2>/dev/null \
  || echo "log group exists"
aws logs put-retention-policy --log-group-name "$LOG_GROUP" --retention-in-days 7 --region "$REGION" >/dev/null 2>&1 || true
aws ecs create-cluster --cluster-name "$CLUSTER" --capacity-providers FARGATE \
  --region "$REGION" >/dev/null 2>&1 || echo "cluster exists"

# --- 3. IAM ----------------------------------------------------------------
say "IAM roles"
TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
for role in "$EXEC_ROLE" "$TASK_ROLE"; do
  aws iam get-role --role-name "$role" >/dev/null 2>&1 \
    || aws iam create-role --role-name "$role" --assume-role-policy-document "$TRUST" >/dev/null
done
aws iam attach-role-policy --role-name "$EXEC_ROLE" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy >/dev/null 2>&1 || true
aws iam put-role-policy --role-name "$TASK_ROLE" --policy-name ecs-exec-channel \
  --policy-document file://deploy/poc/task-role-policy.json
EXEC_ROLE_ARN="$(aws iam get-role --role-name "$EXEC_ROLE" --query Role.Arn --output text)"
TASK_ROLE_ARN="$(aws iam get-role --role-name "$TASK_ROLE" --query Role.Arn --output text)"
sleep 10   # IAM propagation before ECS tries to assume the roles

# --- 4. network -------------------------------------------------------------
say "network"
VPC="$(aws ec2 describe-vpcs --region "$REGION" --filters Name=is-default,Values=true \
  --query 'Vpcs[0].VpcId' --output text)"
if [ "$VPC" = "None" ]; then
  echo "ERROR: no default VPC in $REGION; create one there or edit VPC_ID at the top"
  exit 1
fi
mapfile -t SUBNETS < <(aws ec2 describe-subnets --region "$REGION" \
  --filters "Name=vpc-id,Values=$VPC" Name=default-for-az,Values=true \
  --query 'Subnets[].SubnetId' --output text | tr '\t' '\n')
if [ "${#SUBNETS[@]}" -lt 2 ]; then
  mapfile -t SUBNETS < <(aws ec2 describe-subnets --region "$REGION" \
    --filters "Name=vpc-id,Values=$VPC" --query 'Subnets[].SubnetId' --output text | tr '\t' '\n')
fi
echo "vpc=$VPC subnets=${SUBNETS[0]},${SUBNETS[1]}"

sg_id() { aws ec2 describe-security-groups --region "$REGION" --filters \
  "Name=group-name,Values=$1" "Name=vpc-id,Values=$VPC" --query 'SecurityGroups[0].GroupId' \
  --output text; }
ALB_SG="$(sg_id "$NAME-alb-sg")"
if [ "$ALB_SG" = "None" ]; then
  ALB_SG="$(aws ec2 create-security-group --region "$REGION" --group-name "$NAME-alb-sg" \
    --description "POC ALB ingress" --vpc-id "$VPC" --query GroupId --output text)"
  aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$ALB_SG" \
    --protocol tcp --port 80 --cidr "$ALLOW_CIDR" >/dev/null
fi
TASK_SG="$(sg_id "$NAME-task-sg")"
if [ "$TASK_SG" = "None" ]; then
  TASK_SG="$(aws ec2 create-security-group --region "$REGION" --group-name "$NAME-task-sg" \
    --description "POC task ingress from ALB only" --vpc-id "$VPC" --query GroupId --output text)"
  aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$TASK_SG" \
    --protocol tcp --port 8000 --source-group "$ALB_SG" >/dev/null
fi
echo "alb_sg=$ALB_SG task_sg=$TASK_SG"

# --- 5. ALB ----------------------------------------------------------------
say "load balancer"
ALB_ARN="$(aws elbv2 describe-load-balancers --region "$REGION" --names "$ALB" \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || true)"
if [ -z "$ALB_ARN" ] || [ "$ALB_ARN" = "None" ]; then
  ALB_ARN="$(aws elbv2 create-load-balancer --region "$REGION" --name "$ALB" --type application \
    --scheme internet-facing --subnets "${SUBNETS[0]}" "${SUBNETS[1]}" \
    --security-groups "$ALB_SG" --query 'LoadBalancers[0].LoadBalancerArn' --output text)"
fi
TG_ARN="$(aws elbv2 describe-target-groups --region "$REGION" --names "$TG" \
  --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || true)"
if [ -z "$TG_ARN" ] || [ "$TG_ARN" = "None" ]; then
  TG_ARN="$(aws elbv2 create-target-group --region "$REGION" --name "$TG" --protocol HTTP \
    --port 8000 --target-type ip --vpc-id "$VPC" --health-check-path /health \
    --health-check-interval-seconds 15 --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 --unhealthy-threshold-count 3 --matcher HttpCode=200 \
    --query 'TargetGroups[0].TargetGroupArn' --output text)"
fi
if ! aws elbv2 describe-listeners --region "$REGION" --load-balancer-arn "$ALB_ARN" \
    --query 'Listeners[?Port==`80`].ListenerArn' --output text | grep -q .; then
  aws elbv2 create-listener --region "$REGION" --load-balancer-arn "$ALB_ARN" \
    --protocol HTTP --port 80 \
    --default-actions Type=forward,TargetGroupArn="$TG_ARN" >/dev/null
fi
ALB_DNS="$(aws elbv2 describe-load-balancers --region "$REGION" --load-balancer-arns "$ALB_ARN" \
  --query 'LoadBalancers[0].DNSName' --output text)"
echo "alb=$ALB_DNS"

# --- 6. task definition -----------------------------------------------------
say "task definition"
TASK_DEF_FILE="$(mktemp)"
cat >"$TASK_DEF_FILE" <<JSON
{
  "family": "$NAME-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "$CPU",
  "memory": "$MEMORY",
  "runtimePlatform": {"cpuArchitecture": "$CPU_ARCH", "operatingSystemFamily": "LINUX"},
  "executionRoleArn": "$EXEC_ROLE_ARN",
  "taskRoleArn": "$TASK_ROLE_ARN",
  "containerDefinitions": [
    {
      "name": "main",
      "image": "$IMAGE",
      "essential": true,
      "portMappings": [{"name": "http", "containerPort": 8000, "protocol": "tcp", "appProtocol": "http"}],
      "environment": [
        {"name": "BANK_DATA_DIR", "value": "/app/data/dev"},
        {"name": "BANK_STATE", "value": "/app/.state/mock.sqlite"},
        {"name": "BANK_PORT", "value": "8000"}
      ],
      "linuxParameters": {"initProcessEnabled": true},
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "$LOG_GROUP",
          "awslogs-region": "$REGION",
          "awslogs-stream-prefix": "api"
        }
      }
    }
  ]
}
JSON
TASK_DEF_ARN="$(aws ecs register-task-definition --region "$REGION" \
  --cli-input-json "file://$TASK_DEF_FILE" --query 'taskDefinition.taskDefinitionArn' --output text)"
rm -f "$TASK_DEF_FILE"
echo "registered $TASK_DEF_ARN"

# --- 7. service -------------------------------------------------------------
say "service"
NETCONF="awsvpcConfiguration={subnets=[${SUBNETS[0]},${SUBNETS[1]}],securityGroups=[$TASK_SG],assignPublicIp=ENABLED}"
if aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" --region "$REGION" \
    --query 'services[?status==`ACTIVE`].serviceName' --output text | grep -q .; then
  aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" --region "$REGION" \
    --task-definition "$TASK_DEF_ARN" --force-new-deployment >/dev/null
  aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" --region "$REGION" \
    --enable-execute-command --enable-execute-command-configuration \
    "logging=OVERRIDE,executeCommandConfiguration={logConfiguration={cloudWatchLogGroupName=$LOG_GROUP,cloudWatchEncryptionEnabled=false}}" >/dev/null
else
  aws ecs create-service --cluster "$CLUSTER" --service-name "$SERVICE" --region "$REGION" \
    --task-definition "$TASK_DEF_ARN" --desired-count 1 --launch-type FARGATE \
    --enable-execute-command \
    --enable-execute-command-configuration \
    "logging=OVERRIDE,executeCommandConfiguration={logConfiguration={cloudWatchLogGroupName=$LOG_GROUP,cloudWatchEncryptionEnabled=false}}" \
    --deployment-configuration "deploymentCircuitBreaker={enable=true,rollback=true}" \
    --health-check-grace-period-seconds 90 \
    --network-configuration "$NETCONF" \
    --load-balancers "targetGroupArn=$TG_ARN,containerName=main,containerPort=8000" >/dev/null
fi

say "waiting for service stability (2-4 min on first deploy)"
aws ecs wait services-stable --cluster "$CLUSTER" --services "$SERVICE" --region "$REGION"

say "smoke test"
curl -fsS --max-time 10 "http://$ALB_DNS/health" && echo
cat <<EOF

Deployed.
  API base URL : http://$ALB_DNS
  health       : http://$ALB_DNS/health
  cluster/svc  : $CLUSTER / $SERVICE
  log group    : $LOG_GROUP

Operator console (ECS Exec):
  ./deploy/poc/demo.sh exec 'python -m tools.runtime pending'

Tear down when the demo is over (billing stops):
  ./deploy/poc/teardown.sh --yes
EOF
