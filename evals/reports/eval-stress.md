# Evaluation report - stress

- Commit: `cb51c79`
- Data: `evals/fixtures/stress/data`
- Gold: `evals/fixtures/stress/gold.json`
- Generated: 2026-10-28T18:46:52+00:00
- Cases fully passed: **16/16**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate |
| --- | ---: | ---: | ---: |
| `conformance.submitted` | 16 | 16 | 100.0% |
| `conformance.classification` | 16 | 16 | 100.0% |
| `conformance.routing` | 16 | 16 | 100.0% |
| `conformance.policy_selection` | 16 | 16 | 100.0% |
| `conformance.facts` | 16 | 16 | 100.0% |
| `conformance.missing_information` | 16 | 16 | 100.0% |
| `conformance.deadline` | 16 | 16 | 100.0% |
| `conformance.citations_valid` | 16 | 16 | 100.0% |
| `conformance.required_evidence` | 16 | 16 | 100.0% |
| `conformance.narrative_present` | 16 | 16 | 100.0% |
| `conformance.no_restricted_values` | 16 | 16 | 100.0% |
| `conformance.targeted_questions` | 16 | 16 | 100.0% |
| `grounding.citation_exact` | 16 | 16 | 100.0% |
| `grounding.claim_sources` | 16 | 16 | 100.0% |
| `tools.required_reads` | 16 | 16 | 100.0% |
| `tools.no_forbidden_writes` | 16 | 16 | 100.0% |
| `tools.retry_bound` | 16 | 16 | 100.0% |
| `tools.no_extra_reads` | 16 | 16 | 100.0% |
| `escalation.route_correct` | 16 | 16 | 100.0% |
| `escalation.class_correct` | 16 | 16 | 100.0% |
| `pii.restricted_values` | 16 | 16 | 100.0% |
| `pii.synthetic_patterns` | 16 | 16 | 100.0% |

## Escalation

- Normal cases routed normally: 5/5
- Correct escalations: 8/8
- Missed escalations: none
- False escalations: none
- Request-information routes: 3/3
- Not built: none

## Failures

No failing cases in this run.
## Limits

- Deterministic checks only. Semantic grounding, prose safety and the observed demo remain human review.
- The hidden set is scored only when its data and gold are injected; this report never claims a hidden result it did not run.
- A passing report does not by itself award rubric points.
