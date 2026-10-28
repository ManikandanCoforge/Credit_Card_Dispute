# AWS target architecture: services

**Status: target state, not the assessed deployment.** The repo today runs one local container with SQLite and no reviewer identity. This is the proposed AWS shape for a bank-hosted run. It is not built or measured.

Diagram: `docs/aws-architecture.html` (A3 landscape, print to PDF).

## Service map

| Layer | Service | What it does here | Configuration / control |
|---|---|---|---|
| Edge | Route 53 | Private DNS for the bank-facing API; public alias for the reviewer console | Private hosted zone for bank traffic; public record only for the console |
| Edge | CloudFront + AWS WAF | Reviewer console delivery, TLS, rate limiting | Managed rule groups; only public surface |
| Identity | Amazon Cognito | Reviewer sign-in, MFA, `reviewers` group | Authorizer on the review API; no agent access |
| API | Amazon API Gateway (REST) | Private intake API; review API | IAM auth for bank services; Cognito for humans; request validation; 413 limit |
| Queue | Amazon SQS + DLQ | Buffer intake bursts; retry failed cases | Visibility timeout 6x Lambda timeout; `maxReceiveCount` 3 |
| Orchestration | AWS Step Functions (Standard) | One execution per case: validate, build, decide, wait for review, create | `WaitForTaskToken` for the human gate; retries and timeouts; X-Ray |
| Compute | AWS Lambda (Python 3.12, ARM64) | Validate, build record, rules draft, model gateway, review service, create case, audit emitter | 512-1024 MB; 30-60 s; reserved concurrency; private subnets |
| Integration | AWS PrivateLink / VPC Lattice | Private access to bank transaction, merchant and case APIs | No public internet; mTLS or OAuth2 per bank contract |
| Data | Amazon S3 | Intake documents, policy corpus, drafts, contracts, audit exports | SSE-KMS; versioning; Block Public Access; Object Lock on policy and audit |
| Data | Amazon DynamoDB | Cases, drafts, reviews, idempotency keys, model registry | On-demand; PITR; conditional writes; TTL on idempotency; Streams to EventBridge |
| AI | Amazon Bedrock | Two closed questions, single turn, schema-constrained | Approved model ID only; Guardrails; invocation logging restricted or off; no tools |
| AI | Amazon Bedrock Guardrails | Prompt-attack and denied-topic filter | Applied to the model gateway only |
| Events | Amazon EventBridge + Amazon SNS | Case state changes, reviewer notifications, audit fan-out | Event bus per environment; SNS topic for email or Teams; DLQ |
| Security | AWS KMS | Customer-managed keys per data class | Intake, policy, audit, model logs |
| Security | AWS Secrets Manager | Bank API credentials, model provider keys | Rotation; no secrets in environment variables |
| Security | AWS IAM | Least-privilege roles per function | Separate review-write role; workflow role cannot write approvals |
| Audit | AWS CloudTrail + AWS Config | Account/API audit, configuration compliance | Organisation trail; S3/DynamoDB data events; Config rules |
| Detection | Amazon GuardDuty + Amazon Macie | Threat detection; PII/card leak detection in S3 | Macie on artifacts and audit buckets |
| Observability | Amazon CloudWatch | Structured logs, metrics, alarms, dashboards | JSON logs; 90-day retention; no prompts or PANs; alarms on 5xx, DLQ, workflow failures |
| Observability | AWS X-Ray | End-to-end traces | API Gateway -> Lambda -> Step Functions -> DynamoDB/Bedrock |
| Delivery | GitHub Actions + OIDC | CI/CD without long-lived keys | `pytest` 100%, mypy, ruff, bandit; `cdk deploy` |
| IaC | AWS CDK (Python) | Infrastructure as code | `dev`, `staging`, `prod` stacks; drift detection |
| Batch | AWS Batch on Fargate | Offline eval and scored run | `tools/hybrid_eval.py`, `tools/scored_run.py`; reports to S3 |
| Sandbox | ECS Fargate + Aurora Serverless v2 | Capstone mock bank only | Not production; SQLite on EFS is acceptable for parity |

## Code mapping

| Repo module | AWS runtime | Notes |
|---|---|---|
| `src/build_records.py` | Lambda: validate intake | Schema, size, source IDs |
| `src/contract_records.py` | Lambda: build working record | Policy by reported date; transactions and merchant |
| `src/contract.py` | Lambda: rules draft | Classification, routing, deadline, citations |
| `src/model_cue.py`, `src/model_clients.py` | Lambda: model gateway + Bedrock adapter | New adapter needed; current clients are Azure OpenAI/Foundry |
| `src/model_registry.py`, `models.toml` | DynamoDB model registry + deploy-time config | Schema hash and `approved_by`; live call refused if empty |
| `src/untrusted.py` | Bundled in every Lambda | Detectors and redaction; no separate service |
| `tools/runtime.py` | Lambda: review service + create case; mock bank in sandbox | Review, records, idempotency, audit |
| `tools/hybrid_eval.py` | AWS Batch/Fargate eval job | Offline replay; reports to S3 |
| `tools/scored_run.py` | AWS Batch/Fargate eval job | Rules baseline; zero model calls |

## Controls mapped to the repo invariants

- **Approval bound to the draft hash.** DynamoDB conditional write on `draft_hash` and `status=pending`. The reviewer role is the only writer; the workflow role can read a review and send the task token but cannot write an approval.
- **Idempotency.** DynamoDB conditional put on `Idempotency-Key`; exact replay returns the stored response; a different body returns 409; TTL cleans old keys.
- **Duplicate case.** Conditional put on `case_id`; an existing underlying complaint returns 409 `duplicate_case`, never a second case.
- **Restricted values.** App-level detectors and redaction run before the model; CloudWatch logs carry no prompts or answers; Bedrock invocation logging is restricted or off; Macie is the backstop for S3.
- **Prompt injection.** `has_instruction`, `addresses_a_model` and the command detector run before the model; Guardrails adds a second filter; the model has no tools, no browsing and no memory; the answer schema is validated.
- **Exact citations.** S3 versioned policy corpus; deterministic retrieval by policy version and source ID; the model never writes a citation.
- **Deadlines.** Computed in code from the policy version selected by the reported date; never from today's date and never by the model.
- **Audit.** DynamoDB Streams -> EventBridge -> Firehose -> S3 Object Lock; CloudTrail data events on S3 and DynamoDB.

## Running cost estimate

List prices, `us-east-1`, on-demand, no support plan, no taxes. Model prices from the AWS Price List API on 16 Oct 2026: Claude Haiku 5.5 at $0.10/$0.50 per 1M input/output tokens; Claude Sonnet 5.5 at $2.00/$10.00. One model call per case, 1,000 input and 100 output tokens.

| Cases per month | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|
| 1,000 | ~$160 | ~$165 |
| 10,000 | ~$184 | ~$213 |
| 100,000 | ~$414 | ~$699 |

At 10,000 cases, the bill is roughly:

- PrivateLink endpoints: $102 (7 interface endpoints, 2 AZs, $0.01/hour each)
- GuardDuty $20, Macie $12, CloudTrail and Config $2
- CloudWatch and X-Ray $15
- WAF $12
- KMS, Secrets Manager, Route 53 $8
- Lambda, Step Functions, API Gateway, SQS $5
- S3, DynamoDB, CloudFront, data transfer $3
- Bedrock and Guardrails $4.50 (Haiku) or $33 (Sonnet)
- Total: about $184 (Haiku) or $213 (Sonnet)

Assumptions: 10 Lambda invocations per case at 1 GB and 1 s; 12 Step Functions transitions; 10 API requests; 30 DynamoDB writes and 50 reads; 12 GB S3 with versions; 10 GB CloudFront; 50 reviewers; 12 GB Macie scan; 7 interface endpoints in 2 AZs.

What moves the number:

- **PrivateLink is the floor.** Each interface endpoint in 2 AZs is $14.60/month. One aggregated bank endpoint and one AZ cut the $102 to about $15 to $51.
- **Macie is $1/GB scanned.** At 100,000 cases it is $120 if every object is scanned; scope it to the audit and artifact buckets. At 10% coverage the 100,000-case total drops from about $414 to $306.
- **The model is small at this volume.** $1.50 (Haiku) or $30 (Sonnet) at 10,000 cases; $15 or $300 at 100,000 cases. Two calls per case doubles it.
- **AWS Business Support** adds from $100/month or a percentage of usage; on a small bill it can be the largest line.
- **NAT Gateway is avoided.** If used, add about $33/month per AZ plus data processing.
- **Lean pilot:** one AZ, five endpoints, no GuardDuty, Macie or Config, about $85/month at 10,000 cases.

The AI is not the cost driver at this volume. The private network and security baseline is about 89% of the 10,000-case bill; compute, storage and model calls are the rest.

## Why not

- **No RDS or Aurora for the app.** The bank case system is the system of record; DynamoDB holds workflow state. Aurora is only for the optional mock sandbox.
- **No OpenSearch or vector database.** The policy corpus is small, versioned and citation-exact. Deterministic retrieval is safer; a vector index adds recall but weakens exactness and needs re-qualification.
- **No EKS.** The workload is small and bursty; Lambda + Step Functions is simpler and cheaper.
- **No public agent endpoint.** The agent is internal; the reviewer console is the only public surface.
- **No model autonomy.** Bedrock is a single-turn classifier with a fixed schema, not an agent. No tools, browsing or memory.
- **No production identity in the current repo.** Cognito is new work; the operator CLI is a training simplification.

## Open items before this is real

1. Build the Bedrock adapter and a qualification record; the current clients are Azure OpenAI and Microsoft Foundry.
2. Build the reviewer console and Cognito; the current UI is an operator CLI.
3. Agree PrivateLink and mTLS/OAuth2 with the bank.
4. Write the CDK stacks and separate `dev`, `staging`, `prod` accounts.
5. Load and latency test at the expected volume.
6. Legal and retention review for S3 Object Lock.
7. Decide whether Bedrock invocation logging is allowed; if not, rely on metadata only.
