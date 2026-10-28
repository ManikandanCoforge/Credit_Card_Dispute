# Evaluation report - holdout

- Commit: `02a241d`
- Data: `evals/fixtures/holdout/data`
- Gold: `evals/fixtures/holdout/gold.json`
- Generated: 2026-10-28T19:23:09+00:00
- Cases fully passed: **6/8**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate |
| --- | ---: | ---: | ---: |
| `conformance.submitted` | 8 | 8 | 100.0% |
| `conformance.classification` | 6 | 8 | 75.0% |
| `conformance.routing` | 7 | 8 | 87.5% |
| `conformance.policy_selection` | 8 | 8 | 100.0% |
| `conformance.facts` | 8 | 8 | 100.0% |
| `conformance.missing_information` | 8 | 8 | 100.0% |
| `conformance.deadline` | 7 | 8 | 87.5% |
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
| `escalation.route_correct` | 7 | 8 | 87.5% |
| `escalation.class_correct` | 6 | 8 | 75.0% |
| `pii.restricted_values` | 8 | 8 | 100.0% |
| `pii.synthetic_patterns` | 8 | 8 | 100.0% |

## Escalation

- Normal cases routed normally: 5/6
- Correct escalations: 2/2
- Missed escalations: none
- False escalations: HLD-H08
- Request-information routes: 0/0
- Not built: none

## Failures

### HLD-H06

- `conformance.classification` - HLD-H06 fails the supplied evaluator sub-check classification
- `escalation.class_correct` - classification 'ambiguous' is not one of ['unsupported']

### HLD-H08

- `conformance.classification` - HLD-H08 fails the supplied evaluator sub-check classification
- `conformance.routing` - HLD-H08 fails the supplied evaluator sub-check routing
- `conformance.deadline` - HLD-H08 fails the supplied evaluator sub-check deadline
- `escalation.route_correct` - routing 'manual_review' is not one of ['ready_for_review']
- `escalation.class_correct` - classification 'ambiguous' is not one of ['service_not_received']

## Limits

- Deterministic checks only. Semantic grounding, prose safety and the observed demo remain human review.
- The hidden set is scored only when its data and gold are injected; this report never claims a hidden result it did not run.
- A passing report does not by itself award rubric points.
