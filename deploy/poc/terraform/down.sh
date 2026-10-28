#!/usr/bin/env bash
# Destroy everything this stack created. Billing stops when this returns.
# The ECR repository is force-deleted, so the image goes with it.
set -euo pipefail
cd "$(dirname "$0")"
terraform destroy -input=false -auto-approve
