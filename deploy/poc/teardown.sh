#!/usr/bin/env bash
# Delete every resource deploy.sh created. Billing stops when this finishes.
#   ./deploy/poc/teardown.sh --yes
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
NAME="${NAME:-ccd-poc}"
CLUSTER="$NAME"
SERVICE="$NAME-api"
REPO="$NAME-api"
ALB="$NAME-alb"
TG="$NAME-tg"
LOG_GROUP="/ecs/$NAME-api"

[ "${1:-}" = "--yes" ] || { echo "Refusing to delete without --yes"; exit 1; }

say() { printf '\n== %s\n' "$*"; }

say "service"
aws ecs update-service --region "$REGION" --cluster "$CLUSTER" --service "$SERVICE" \
  --desired-count 0 >/dev/null 2>&1 || true
aws ecs delete-service --region "$REGION" --cluster "$CLUSTER" --service "$SERVICE" \
  --force >/dev/null 2>&1 || true
aws ecs wait services-inactive --region "$REGION" --cluster "$CLUSTER" \
  --services "$SERVICE" 2>/dev/null || true

say "cluster"
aws ecs delete-cluster --region "$REGION" --cluster "$CLUSTER" >/dev/null 2>&1 || true

say "load balancer"
ALB_ARN="$(aws elbv2 describe-load-balancers --region "$REGION" --names "$ALB" \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || true)"
if [ -n "$ALB_ARN" ] && [ "$ALB_ARN" != "None" ]; then
  aws elbv2 delete-load-balancer --region "$REGION" --load-balancer-arn "$ALB_ARN" >/dev/null
  aws elbv2 wait load-balancers-deleted --region "$REGION" --load-balancer-arns "$ALB_ARN" || true
fi
TG_ARN="$(aws elbv2 describe-target-groups --region "$REGION" --names "$TG" \
  --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || true)"
if [ -n "$TG_ARN" ] && [ "$TG_ARN" != "None" ]; then
  aws elbv2 delete-target-group --region "$REGION" --target-group-arn "$TG_ARN" >/dev/null
fi

say "security groups"
for sg in "$NAME-alb-sg" "$NAME-task-sg"; do
  id="$(aws ec2 describe-security-groups --region "$REGION" \
    --filters "Name=group-name,Values=$sg" --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || true)"
  if [ -n "$id" ] && [ "$id" != "None" ]; then
    aws ec2 delete-security-group --region "$REGION" --group-id "$id" >/dev/null 2>&1 \
      || echo "  (retry $sg in a minute; ENIs from the ALB can linger)"
  fi
done

say "logs + image + roles"
aws logs delete-log-group --region "$REGION" --log-group-name "$LOG_GROUP" >/dev/null 2>&1 || true
aws ecr delete-repository --region "$REGION" --repository-name "$REPO" --force >/dev/null 2>&1 || true
aws iam detach-role-policy --role-name "$NAME-exec" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy >/dev/null 2>&1 || true
aws iam delete-role-policy --role-name "$NAME-task" --policy-name ecs-exec-channel >/dev/null 2>&1 || true
for role in "$NAME-exec" "$NAME-task"; do
  aws iam delete-role --role-name "$role" >/dev/null 2>&1 || true
done

echo
echo "Teardown requested. Check the Billing console tomorrow to confirm zero spend."
