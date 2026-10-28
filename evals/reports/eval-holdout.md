# Evaluation report - holdout

- Commit: `cb51c79`
- Data: `evals/fixtures/holdout/data`
- Gold: `evals/fixtures/holdout/gold.json`
- Generated: 2026-10-28T18:46:50+00:00
- Cases fully passed: **8/8**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate |
| --- | ---: | ---: | ---: |
| `conformance.submitted` | 8 | 8 | 100.0% |
| `conformance.classification` | 8 | 8 | 100.0% |
| `conformance.routing` | 8 | 8 | 100.0% |
| `conformance.policy_selection` | 8 | 8 | 100.0% |
| `conformance.facts` | 8 | 8 | 100.0% |
| `conformance.missing_information` | 8 | 8 | 100.0% |
| `conformance.deadline` | 8 | 8 | 100.0% |
| `conformance.citations_valid` | 8 | 8 | 100.0% |
| `conformance.required_evidence` | 8 | 8 | 100.0% |
| `conformance.narrative_present` | 8 | 8 | 100.0% |
| `conformance.no_restricted_values` | 8 | 8 | 100.0% |
| `conformance.targeted_questions` | 8 | 8 | 100.0% |
| `grounding.citation_exact` | 8 | 8 | 100.0% |
| `grounding.claim_sources` | 8 | 8 | 100.0% |
| `tools.required_reads` | 8 | 8 | 100.0% |
| `tools.no_forbidden_writes` | 8 | 8 | 100.0% |
| `tools.retry_bound` | 8 | 8 | 100.0% |
| `tools.no_extra_reads` | 8 | 8 | 100.0% |
| `escalation.route_correct` | 8 | 8 | 100.0% |
| `escalation.class_correct` | 8 | 8 | 100.0% |
| `pii.restricted_values` | 8 | 8 | 100.0% |
| `pii.synthetic_patterns` | 8 | 8 | 100.0% |

## Escalation

- Normal cases routed normally: 6/6
- Correct escalations: 2/2
- Missed escalations: none
- False escalations: none
- Request-information routes: 0/0
- Not built: none

## Failures

No failing cases in this run.
## Limits

- Deterministic checks only. Semantic grounding, prose safety and the observed demo remain human review.
- The hidden set is scored only when its data and gold are injected; this report never claims a hidden result it did not run.
- A passing report does not by itself award rubric points.
