# Evaluation report - dev

- Commit: `b22743a`
- Data: `data/dev`
- Gold: `feedback/dev_gold.json`
- Generated: 2026-10-28T00:57:10+00:00
- Cases fully passed: **12/12**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate |
| --- | ---: | ---: | ---: |
| `conformance.submitted` | 12 | 12 | 100.0% |
| `conformance.classification` | 12 | 12 | 100.0% |
| `conformance.routing` | 12 | 12 | 100.0% |
| `conformance.policy_selection` | 12 | 12 | 100.0% |
| `conformance.facts` | 12 | 12 | 100.0% |
| `conformance.missing_information` | 12 | 12 | 100.0% |
| `conformance.deadline` | 12 | 12 | 100.0% |
| `conformance.citations_valid` | 12 | 12 | 100.0% |
| `conformance.required_evidence` | 12 | 12 | 100.0% |
| `conformance.narrative_present` | 12 | 12 | 100.0% |
| `conformance.no_restricted_values` | 12 | 12 | 100.0% |
| `conformance.targeted_questions` | 12 | 12 | 100.0% |
| `grounding.citation_exact` | 12 | 12 | 100.0% |
| `grounding.claim_sources` | 12 | 12 | 100.0% |
| `tools.required_reads` | 12 | 12 | 100.0% |
| `tools.no_forbidden_writes` | 12 | 12 | 100.0% |
| `tools.retry_bound` | 12 | 12 | 100.0% |
| `tools.no_extra_reads` | 12 | 12 | 100.0% |
| `escalation.route_correct` | 12 | 12 | 100.0% |
| `escalation.class_correct` | 12 | 12 | 100.0% |
| `pii.restricted_values` | 12 | 12 | 100.0% |
| `pii.synthetic_patterns` | 12 | 12 | 100.0% |

## Escalation

- Normal cases routed normally: 7/7
- Correct escalations: 3/3
- Missed escalations: none
- False escalations: none
- Request-information routes: 2/2
- Not built: none

## Failures

No failing cases in this run.
## Limits

- Deterministic checks only. Semantic grounding, prose safety and the observed demo remain human review.
- The hidden set is scored only when its data and gold are injected; this report never claims a hidden result it did not run.
- A passing report does not by itself award rubric points.
