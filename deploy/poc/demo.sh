#!/usr/bin/env bash
# Thin operator wrapper for the POC. Every "in-cloud" beat runs through ECS Exec
# into the one task that owns the SQLite state file, so the approval is a real
# operator action against real cloud state.
#
#   ./deploy/poc/demo.sh url          # public base URL
#   ./deploy/poc/demo.sh health       # GET /health
#   ./deploy/poc/demo.sh cases        # GET /v1/cases
#   ./deploy/poc/demo.sh score        # scored run from inside the container
#   ./deploy/poc/demo.sh request CARD-D01   # queue a draft for review
#   ./deploy/poc/demo.sh pending      # operator queue
#   ./deploy/poc/demo.sh approve rev_x --reviewer ken   # human gate
#   ./deploy/poc/demo.sh record rev_x # create + replay + guard checks
#   ./deploy/poc/demo.sh audit        # audit trail
#   ./deploy/poc/demo.sh exec 'any command'
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
CLUSTER="${NAME:-ccd-poc}"
SERVICE="$CLUSTER-api"
ALB="$CLUSTER-alb"

albdns() { aws elbv2 describe-load-balancers --region "$REGION" --names "$ALB" \
  --query 'LoadBalancers[0].DNSName' --output text; }
taskid() { aws ecs list-tasks --region "$REGION" --cluster "$CLUSTER" --service-name "$SERVICE" \
  --desired-status RUNNING --query 'taskArns[0]' --output text; }
exec_in() {
  local t; t="$(taskid)"
  if [ -z "$t" ] || [ "$t" = "None" ]; then echo "no RUNNING task"; exit 1; fi
  aws ecs execute-command --region "$REGION" --cluster "$CLUSTER" --task "$t" \
    --container main --interactive --command "$1"
}

cmd="${1:-url}"; shift || true
case "$cmd" in
  url)    echo "http://$(albdns)" ;;
  health) curl -fsS "http://$(albdns)/health"; echo ;;
  cases)  curl -fsS "http://$(albdns)/v1/cases" | python -m json.tool | head -40 ;;
  score)  exec_in "python -m tools.scored_run --base-url http://127.0.0.1:8000" ;;
  request)
    case_id="${1:-CARD-D01}"
    curl -fsS -X POST "http://$(albdns)/v1/reviews" \
      -H 'Content-Type: application/json' \
      -d "{\"case_id\":\"$case_id\",\"draft\":{\"case_id\":\"$case_id\",\"disposition\":\"demo draft for the operator gate\"}}"
    echo ;;
  pending) exec_in "python -m tools.runtime pending --state /app/.state/mock.sqlite" ;;
  approve)
    rev="$1"; shift || true
    reviewer="${REVIEWER:-ken}"
    if [ "${1:-}" = "--reviewer" ]; then reviewer="${2:-$reviewer}"; fi
    exec_in "python -m tools.runtime approve $rev --reviewer $reviewer --state /app/.state/mock.sqlite" ;;
  audit)  exec_in "python -m tools.runtime audit --state /app/.state/mock.sqlite" ;;
  record) exec_in "python deploy/poc/record_demo.py --base http://127.0.0.1:8000 --review $1" ;;
  exec)   exec_in "$1" ;;
  *)      echo "unknown command: $cmd"; exit 2 ;;
esac
