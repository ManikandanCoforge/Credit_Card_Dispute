# Evaluation report - holdout

- Commit: `a65379c`
- Data: `evals/fixtures/holdout/data`
- Gold: `evals/fixtures/holdout/gold.json`
- Generated: 2026-10-28T17:44:27+00:00
- Cases fully passed: **5/8**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate |
| --- | ---: | ---: | ---: |
| `conformance.submitted` | 7 | 8 | 87.5% |
| `conformance.classification` | 5 | 8 | 62.5% |
| `conformance.routing` | 6 | 8 | 75.0% |
| `conformance.policy_selection` | 7 | 8 | 87.5% |
| `conformance.facts` | 7 | 8 | 87.5% |
| `conformance.missing_information` | 7 | 8 | 87.5% |
| `conformance.deadline` | 6 | 8 | 75.0% |
| `conformance.citations_valid` | 7 | 8 | 87.5% |
| `conformance.required_evidence` | 7 | 8 | 87.5% |
| `conformance.narrative_present` | 7 | 8 | 87.5% |
| `conformance.no_restricted_values` | 7 | 8 | 87.5% |
| `conformance.targeted_questions` | 7 | 8 | 87.5% |
| `grounding.citation_exact` | 7 | 8 | 87.5% |
| `grounding.claim_sources` | 7 | 8 | 87.5% |
| `tools.required_reads` | 8 | 8 | 100.0% |
| `tools.no_forbidden_writes` | 8 | 8 | 100.0% |
| `tools.retry_bound` | 8 | 8 | 100.0% |
| `tools.no_extra_reads` | 8 | 8 | 100.0% |
| `escalation.route_correct` | 6 | 8 | 75.0% |
| `escalation.class_correct` | 5 | 8 | 62.5% |
| `pii.restricted_values` | 8 | 8 | 100.0% |
| `pii.synthetic_patterns` | 8 | 8 | 100.0% |

## Escalation

- Normal cases routed normally: 4/5
- Correct escalations: 2/2
- Missed escalations: none
- False escalations: HLD-H08
- Request-information routes: 0/0
- Not built: HLD-H05

## Failures

### HLD-H05 - not built: expected exactly one 'Amount:' line in the source

- `conformance.submitted` - HLD-H05 fails the supplied evaluator sub-check submitted; build error: expected exactly one 'Amount:' line in the source
- `conformance.classification` - HLD-H05 was not scored for classification: expected exactly one 'Amount:' line in the source
- `conformance.routing` - HLD-H05 was not scored for routing: expected exactly one 'Amount:' line in the source
- `conformance.policy_selection` - HLD-H05 was not scored for policy_selection: expected exactly one 'Amount:' line in the source
- `conformance.facts` - HLD-H05 was not scored for facts: expected exactly one 'Amount:' line in the source
- `conformance.missing_information` - HLD-H05 was not scored for missing_information: expected exactly one 'Amount:' line in the source
- `conformance.deadline` - HLD-H05 was not scored for deadline: expected exactly one 'Amount:' line in the source
- `conformance.citations_valid` - HLD-H05 was not scored for citations_valid: expected exactly one 'Amount:' line in the source
- `conformance.required_evidence` - HLD-H05 was not scored for required_evidence: expected exactly one 'Amount:' line in the source
- `conformance.narrative_present` - HLD-H05 was not scored for narrative_present: expected exactly one 'Amount:' line in the source
- `conformance.no_restricted_values` - HLD-H05 was not scored for no_restricted_values: expected exactly one 'Amount:' line in the source
- `conformance.targeted_questions` - HLD-H05 was not scored for targeted_questions: expected exactly one 'Amount:' line in the source
- `grounding.citation_exact` - case not built: expected exactly one 'Amount:' line in the source
- `grounding.claim_sources` - case not built: expected exactly one 'Amount:' line in the source
- `escalation.route_correct` - routing not scored: expected exactly one 'Amount:' line in the source
- `escalation.class_correct` - classification not scored: expected exactly one 'Amount:' line in the source

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
