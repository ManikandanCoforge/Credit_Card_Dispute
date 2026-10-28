#!/usr/bin/env bash
# Deploy the pilot one phase at a time, so every step can be checked before the
# next one spends money. Each subcommand is idempotent: running it twice is safe.
#
#   ./phases.sh preflight   credentials, tools, identity. No AWS resources.
#   ./phases.sh registry    ECR repository only.
#   ./phases.sh core        log group, IAM roles, security groups.
#   ./phases.sh image       docker build and push. No Terraform.
#   ./phases.sh edge        load balancer, target group, listener.
#   ./phases.sh service     cluster, task definition, service, exec logging.
#   ./phases.sh verify      smoke test, target health, exec agent status.
#   ./phases.sh status      plan only, reports drift, changes nothing.
#   ./phases.sh destroy     terraform destroy, stops billing.
#   ./phases.sh all         every phase in order, stopping at the first failure.
#
# Credentials come from .env at the repository root, never from arguments, and
# are never echoed. Copy .env.example to .env first.
#
# Tests: bash -n phases.sh

set -euo pipefail
cd "$(dirname "$0")"

REPO_ROOT="$(cd ../../.. && pwd)"
ENV_FILE="$REPO_ROOT/.env"

die() { echo "ERROR: $*" >&2; exit 1; }
say() { echo; echo "== $*"; }

load_env() {
  [ -f "$ENV_FILE" ] || die "no .env at $ENV_FILE. Copy .env.example to .env and fill in the credentials."
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
  export AWS_REGION="${AWS_REGION:-us-east-1}"
  export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"
  # Terraform on Windows fails provider downloads when %TEMP% is unwritable or
  # given as an MSYS path (/d/...). Hand it a native path with forward slashes.
  mkdir -p "$REPO_ROOT/.local/tmp"
  local tmp_native
  tmp_native="$(cygpath -m "$REPO_ROOT/.local/tmp" 2>/dev/null || echo "$REPO_ROOT/.local/tmp")"
  export TMPDIR="$tmp_native" TEMP="$tmp_native" TMP="$tmp_native"
  # The checkout ships Terraform, the AWS CLI and the Session Manager plugin
  # under .local/tools, so nothing has to be installed globally. Anything found
  # on PATH first still wins.
  local d
  for d in "$REPO_ROOT/.local/tools/bin" \
           "$REPO_ROOT/.local/tools/awscli/Amazon/AWSCLIV2" \
           "$REPO_ROOT/.local/tools"; do
    [ -d "$d" ] || continue
    case ":$PATH:" in
      *":$d:"*) ;;
      *) PATH="$d:$PATH" ;;
    esac
  done
  export PATH

  # Credentials: .env is the primary source, but it is not the only one. If the
  # keys are blank, accept whatever the AWS CLI is already configured with
  # (~/.aws/credentials, or an assumed role exported in this shell), so running
  # "aws configure" once is enough for both the CLI and Terraform.
  if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
    if aws sts get-caller-identity >/dev/null 2>&1; then
      echo "note: .env has no keys, using the credentials the AWS CLI is already configured with" >&2
    else
      die "no usable AWS credentials. Either fill AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in $ENV_FILE, or run 'aws configure' once."
    fi
  fi
}

need_tools() {
  for t in "$@"; do
    command -v "$t" >/dev/null 2>&1 || die "$t is not on PATH"
  done
}

tf() { terraform "$@" -input=false; }

preflight() {
  load_env
  need_tools terraform aws
  say "tools"
  echo "terraform $(terraform version | head -1 | cut -d' ' -f2 | tr -d v)"
  echo "aws       $(aws --version 2>&1 | cut -d' ' -f1 | cut -d/ -f2)"
  say "identity (no secrets shown)"
  aws sts get-caller-identity --query 'join(` `, [Account, Arn])' --output text
  local alias
  alias="$(aws iam list-account-aliases --query 'AccountAliases[0]' --output text 2>/dev/null || true)"
  [ -n "$alias" ] && [ "$alias" != "None" ] && echo "alias     $alias"
  echo
  echo "Confirm this is the sandbox account before ./phases.sh registry."
}

registry() {
  load_env
  need_tools terraform
  say "phase 1, registry"
  tf init -upgrade
  tf apply -auto-approve -target=aws_ecr_repository.api
  terraform output -raw ecr_repository_url
  echo
}

core() {
  load_env
  need_tools terraform
  say "phase 2, network, log group, IAM, security groups"
  # The network targets are only meaningful when create_vpc = true; Terraform
  # ignores a target that has count = 0 with a warning, so listing them is safe
  # in either mode.
  tf apply -auto-approve \
    -target=aws_vpc.poc \
    -target=aws_subnet.public \
    -target=aws_internet_gateway.poc \
    -target=aws_route_table.public \
    -target=aws_route_table_association.public \
    -target=aws_cloudwatch_log_group.api \
    -target=aws_iam_role.execution \
    -target=aws_iam_role_policy_attachment.execution_managed \
    -target=aws_iam_role.task \
    -target=aws_iam_role_policy.exec_channel \
    -target=aws_security_group.alb \
    -target=aws_security_group.task \
    -target=aws_vpc_security_group_ingress_rule.alb_http \
    -target=aws_vpc_security_group_egress_rule.alb_all \
    -target=aws_vpc_security_group_ingress_rule.task_from_alb \
    -target=aws_vpc_security_group_egress_rule.task_all
}

image() {
  load_env
  need_tools docker aws
  say "phase 3, image"
  ./push-image.sh
}

edge() {
  load_env
  need_tools terraform
  say "phase 4, load balancer"
  tf apply -auto-approve \
    -target=aws_lb.api \
    -target=aws_lb_target_group.api \
    -target=aws_lb_listener.http
  echo
  echo "dns name: $(terraform output -raw alb_dns_name)"
}

service() {
  load_env
  need_tools terraform aws
  say "phase 5, cluster, task definition, service"
  tf apply -auto-approve

  # ECS Exec session logging is a cluster setting that the AWS provider 6.70
  # does not model (no configuration block on aws_ecs_cluster, no
  # execute_command_configuration on aws_ecs_service). The API supports it on
  # UpdateCluster, so it is applied here, after the cluster exists. Idempotent:
  # re-running just rewrites the same configuration. Failure is a warning, not
  # a stop, because Exec itself still works without session logging.
  if [ "${TF_VAR_exec_session_logging:-true}" = "true" ]; then
    say "phase 5b, ECS Exec session logging to CloudWatch"
    local cluster log_group rc
    cluster="$(terraform output -raw cluster_name 2>/dev/null || echo ccd-poc)"
    log_group="$(terraform output -raw log_group_name 2>/dev/null || echo /ecs/ccd-poc-api)"
    aws ecs update-cluster --region "$AWS_REGION" --cluster "$cluster" \
      --configuration "{\"executeCommandConfiguration\":{\"logging\":\"OVERRIDE\",\"logConfiguration\":{\"cloudWatchLogGroupName\":\"$log_group\",\"cloudWatchEncryptionEnabled\":false}}}" \
      --query 'cluster.configuration.executeCommandConfiguration.logging' --output text || rc=$?
    if [ -n "${rc:-}" ]; then
      echo "warn: could not set Exec session logging (exit $rc). Exec still works; session output will not be logged." >&2
    fi
  fi
}

verify() {
  load_env
  need_tools terraform aws curl
  local url cluster service_ tg
  url="$(terraform output -raw api_base_url)"
  cluster="$(terraform output -raw cluster_name)"
  service_name="$(terraform output -raw service_name)"
  tg="$(terraform output -raw target_group_arn)"
  say "health at $url/health"
  for _ in $(seq 1 40); do
    if curl -fsS --max-time 5 "$url/health"; then
      echo
      break
    fi
    printf '.'
    sleep 15
  done
  say "target health"
  aws elbv2 describe-target-health --target-group-arn "$tg" \
    --query 'TargetHealthDescriptions[0].TargetHealth.State' --output text
  say "exec agent"
  aws ecs describe-tasks --cluster "$cluster" \
    --tasks "$(aws ecs list-tasks --cluster "$cluster" --service-name "$service_name" --query 'taskArns[0]' --output text)" \
    --query 'tasks[0].containers[0].managedAgents[0].lastStatus' --output text
  say "done"
  echo "service:  $url"
  echo "beats:    ../demo.sh health && ../demo.sh score"
}

status() {
  load_env
  need_tools terraform
  say "plan only, nothing is applied"
  set +e
  terraform plan -input=false -detailed-exitcode -out=/dev/null
  local rc=$?
  set -e
  case "$rc" in
    0) echo "no changes: what is deployed matches the code" ;;
    2) echo "changes pending: the code differs from what is deployed" ;;
    *) echo "plan failed, read the error above" >&2; exit "$rc" ;;
  esac
}

destroy() {
  load_env
  need_tools terraform
  say "destroy, this stops billing"
  terraform destroy -auto-approve -input=false
}

all() {
  preflight
  registry
  core
  image
  edge
  service
  verify
}

cmd="${1:-}"
case "$cmd" in
  preflight|registry|core|image|edge|service|verify|status|destroy|all) "$cmd" ;;
  ""|-h|--help|help)
    awk 'NR>1 { if (/^#/) { sub(/^# ?/, ""); print; next } exit }' "$0"
    ;;
  *) die "unknown phase: $cmd. Try --help." ;;
esac
