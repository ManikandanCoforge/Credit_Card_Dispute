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

REGION="$(terraform output -raw region)"
REPO="$(terraform output -raw ecr_repository_url)"
TAG="$(terraform output -raw image_tag)"
ARCH="$(terraform output -raw cpu_architecture)"
REGISTRY="${REPO%%/*}"
IMAGE="$REPO:$TAG"

PLATFORM="linux/amd64"
if [ "$ARCH" = "ARM64" ]; then PLATFORM="linux/arm64"; fi

printf 'region=%s\nimage=%s\nplatform=%s\n' "$REGION" "$IMAGE" "$PLATFORM"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

# Context is the repository root; Dockerfile is deploy/poc/Dockerfile.
docker build --platform "$PLATFORM" -f ../Dockerfile -t "$IMAGE" ../..
docker push "$IMAGE"

printf '\npushed %s\n' "$IMAGE"
