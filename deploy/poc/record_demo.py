"""Demo driver: turn an approved review into a record, then show the guards.

Runs inside the container (same base URL, same state file) so the operator's
approval is a real cloud-side action. Every step prints the HTTP status and the
body, which is what the demo shows on screen.

    python deploy/poc/record_demo.py --review rev_ab12cd34ef56
"""
import argparse
import json
import urllib.error
import urllib.request


def call(base, path, method="GET", body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def show(label, status, body):
    print("\n" + label)
    print("  status " + str(status))
    print("  " + json.dumps(body, sort_keys=True)[:400])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", default="http://127.0.0.1:8000")
    p.add_argument("--review", required=True, help="review id from tools.runtime pending")
    p.add_argument("--key", default="demo-key-1")
    a = p.parse_args()

    status, review = call(a.base, f"/v1/reviews/{a.review}")
    if status != 200:
        show("review lookup failed", status, review)
        return 1
    show("1. review as stored (draft stays a string)", status,
         {k: review[k] for k in ("id", "case_id", "status", "hash", "reviewer")})
    if review.get("status") != "approved":
        print("\nreview is not approved; run: python -m tools.runtime approve "
              f"{a.review} --reviewer <name> --state /app/.state/mock.sqlite")
        return 1

    draft = json.loads(review["draft"])
    body = {"case_id": review["case_id"], "draft": draft, "review_id": review["id"]}

    show("2. create with Idempotency-Key " + a.key,
         *call(a.base, "/v1/records", "POST", body, {"Idempotency-Key": a.key}))

    show("3. replay of the same key (expect 200 and the same body)",
         *call(a.base, "/v1/records", "POST", body, {"Idempotency-Key": a.key}))

    tampered = dict(draft)
    tampered["demo_tamper"] = True
    show("4. same key, changed draft (expect 409 idempotency_conflict)",
         *call(a.base, "/v1/records", "POST",
                {"case_id": review["case_id"], "draft": tampered, "review_id": review["id"]},
                {"Idempotency-Key": a.key}))

    show("5. new key, changed draft (expect 403 approval_missing_or_draft_changed)",
         *call(a.base, "/v1/records", "POST",
                {"case_id": review["case_id"], "draft": tampered, "review_id": review["id"]},
                {"Idempotency-Key": a.key + "-tampered"}))

    show("6. record as stored", *call(a.base, f"/v1/records/{review['case_id']}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
