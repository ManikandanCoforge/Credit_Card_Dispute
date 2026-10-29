#!/usr/bin/env bash
# Show every HTTP surface of the pilot in one pass: four GETs and two POSTs,
# with the status code and the body for each. Read-only except the review POST,
# which queues a draft in the operator gate.
#
#   ./deploy/poc/api-demo.sh                       # resolve the ALB from AWS
#   ./deploy/poc/api-demo.sh http://127.0.0.1:8000 # or point at any instantiation
#
# No AWS credentials are needed when a base URL is passed. The ALB must allow
# your public IP; if every request times out, that allowlist is stale, not the
# service.
set -uo pipefail

BASE="${1:-}"
if [ -z "$BASE" ]; then
  REGION="${AWS_REGION:-us-east-1}"
  NAME="${NAME:-ccd-poc}"
  dns="$(aws elbv2 describe-load-balancers --region "$REGION" --names "$NAME-alb" \
    --query 'LoadBalancers[0].DNSName' --output text 2>/dev/null || true)"
  if [ -z "$dns" ] || [ "$dns" = "None" ]; then
    echo "usage: $0 <base-url>   (or set AWS credentials so the ALB can be resolved)" >&2
    exit 2
  fi
  BASE="http://$dns"
fi
BASE="${BASE%/}"
CASE="${CASE:-CARD-D05}"

say() { printf '\n[%s]\n' "$*"; }
show() {
  local method="$1" path="$2"; shift 2
  local out code body
  out="$(curl -s -w '__HTTP__%{http_code}' --max-time 20 -X "$method" "$BASE$path" "$@")"
  code="${out##*__HTTP__}"
  body="${out%__HTTP__*}"
  printf '  %-5s %-34s -> %s\n' "$method" "$path" "$code"
  if [ -n "$body" ]; then
    printf '%s' "$body" | python -m json.tool 2>/dev/null | head -18 | sed 's/^/      /' \
      || printf '%s' "$body" | head -c 400 | sed 's/^/      /'
    echo
  fi
  LAST_CODE="$code"
  LAST_BODY="$body"
}

printf 'Base URL: %s\n' "$BASE"

say "1. GET /health"
show GET /health

say "2. GET /v1/cases"
show GET /v1/cases

say "3. GET /v1/cases/$CASE/transactions   (the bank, read-only)"
show GET "/v1/cases/$CASE/transactions"

say "4. GET /v1/cases/$CASE/merchant"
show GET "/v1/cases/$CASE/merchant"

say "5. POST /v1/reviews   (queue a draft for the human gate)"
show POST /v1/reviews -H 'Content-Type: application/json' \
  -d "{\"case_id\":\"$CASE\",\"draft\":{\"case_id\":\"$CASE\",\"disposition\":\"operator gate walkthrough\"}}"
REVIEW="$(printf '%s' "$LAST_BODY" | python -c 'import json,sys; print(json.load(sys.stdin).get("review_id",""))' 2>/dev/null || true)"

if [ -n "$REVIEW" ]; then
  say "6. GET /v1/reviews/$REVIEW   (the draft in the queue, unapproved)"
  show GET "/v1/reviews/$REVIEW"

  say "7. The write path is bound to the approved hash, so a changed draft is refused"
  BODY="$LAST_BODY" python - "$CASE" <<'PY'
import hashlib, json, os, sys
case = sys.argv[1]
stored = json.loads(os.environ["BODY"])["hash"]
approved = {"case_id": case, "disposition": "operator gate walkthrough"}
changed = {"case_id": case, "disposition": "operator gate walkthrough, amount doubled"}
enc = lambda d: json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
print("      hash stored at approval : " + stored)
print("      hash of the same draft  : " + hashlib.sha256(enc(approved)).hexdigest())
print("      hash of a changed draft : " + hashlib.sha256(enc(changed)).hexdigest())
PY
  printf '\n  Approval is bound to the first hash. A POST with a different draft returns\n'
  printf '  403 approval_missing_or_draft_changed, and the bank audits it as an\n'
  printf '  unapproved write, which counts against the assessment. So the demo shows the\n'
  printf '  hash mismatch and sends nothing (the 403 itself was proven once, on purpose).\n'
  printf '  To create the record, approve the draft and let the driver do the guarded POST:\n'
  printf '    ./deploy/poc/demo.sh approve %s --reviewer ken\n' "$REVIEW"
  printf '    ./deploy/poc/demo.sh record %s\n' "$REVIEW"
fi

say "Done"
printf '  If every GET timed out, the ALB security group does not allow this IP.\n'
printf '  Current public IP: %s\n' "$(curl -s --max-time 10 https://checkip.amazonaws.com || echo unknown)"
