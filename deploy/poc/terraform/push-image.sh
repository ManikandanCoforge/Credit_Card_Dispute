#!/usr/bin/env bash
# Build the pilot image and push it to the ECR repository Terraform created.
# Reads region, repository, tag and architecture from the Terraform outputs, so
# it cannot disagree with the task definition.
#
# Requires: aws CLI v2 (configured profile), docker (daemon running), terraform
# state in this directory. Run ./up.sh for the whole sequence.
set -euo pipefail
cd "$(dirname "$0")"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 is not on PATH" >&2; exit 1; }; }
need aws
need docker
need terraform
docker info >/dev/null 2>&1 || { echo "ERROR: docker daemon is not running" >&2; exit 1; }

# Outputs only land in state when an apply has walked the whole graph, and the
# phased rollout applies targets, so fall back to the environment and the
# defaults in variables.tf. Region matters most: it decides which registry we
# log in to.
out() {
  local v
  v="$(terraform output -raw "$1" 2>/dev/null || true)"
  [ -n "$v" ] && printf '%s' "$v" || printf '%s' "$2"
}
REGION="$(out region "${AWS_REGION:-us-east-1}")"
REPO="$(out ecr_repository_url "")"
TAG="$(out image_tag poc)"
ARCH="$(out cpu_architecture X86_64)"
[ -n "$REPO" ] || { echo "ERROR: no ecr_repository_url output. Run ./phases.sh registry first." >&2; exit 1; }
REGISTRY="${REPO%%/*}"
IMAGE="$REPO:$TAG"

PLATFORM="linux/amd64"
if [ "$ARCH" = "ARM64" ]; then PLATFORM="linux/arm64"; fi

printf 'region=%s\nimage=%s\nplatform=%s\n' "$REGION" "$IMAGE" "$PLATFORM"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

# Context is the repository root. This script lives in deploy/poc/terraform, so
# the root is three levels up, not two: the two-level form silently builds with
# deploy/ as the context and every COPY of src/ fails.
ROOT="$(cd ../../.. && pwd)"
[ -f "$ROOT/pyproject.toml" ] || { echo "ERROR: $ROOT is not the repository root" >&2; exit 1; }
docker build --platform "$PLATFORM" -f ../Dockerfile -t "$IMAGE" "$ROOT"
docker push "$IMAGE"

printf '\npushed %s\n' "$IMAGE"
