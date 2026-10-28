#!/usr/bin/env bash
# One command to stand the pilot up: ECR, image, then the rest of the stack.
#
# The repository must exist before the image can be pushed, and the image must
# exist before the service starts, so this runs in three phases. Terraform stays
# the only writer of infrastructure state; docker only writes image layers.
set -euo pipefail
cd "$(dirname "$0")"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 is not on PATH" >&2; exit 1; }; }
need terraform
need aws
need curl

echo "== phase 1: repository"
terraform init -input=false
terraform apply -input=false -auto-approve -target=aws_ecr_repository.api

echo "== phase 2: image"
./push-image.sh

echo "== phase 3: everything else"
terraform apply -input=false -auto-approve

URL="$(terraform output -raw api_base_url)"
echo "== smoke test $URL/health"
for _ in $(seq 1 40); do
  if curl -fsS --max-time 5 "$URL/health"; then
    echo
    echo "up: $URL"
    echo "operator console: ./deploy/poc/demo.sh exec 'python -m tools.runtime pending'"
    exit 0
  fi
  printf '.'
  sleep 15
done

echo
echo "ERROR: /health did not return 200 within 10 minutes." >&2
echo "Next: aws ecs describe-services --cluster \"$(terraform output -raw cluster_name)\" --services \"$(terraform output -raw service_name)\" --query 'services[0].events[0:5]'" >&2
exit 1
