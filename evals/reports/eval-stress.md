# Evaluation report - stress

- Commit: `02a241d`
- Data: `evals/fixtures/stress/data`
- Gold: `evals/fixtures/stress/gold.json`
- Generated: 2026-10-28T19:23:11+00:00
- Cases fully passed: **7/16**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate |
| --- | ---: | ---: | ---: |
| `conformance.submitted` | 16 | 16 | 100.0% |
| `conformance.classification` | 7 | 16 | 43.8% |
| `conformance.routing` | 11 | 16 | 68.8% |
| `conformance.policy_selection` | 16 | 16 | 100.0% |
| `conformance.facts` | 16 | 16 | 100.0% |
| `conformance.missing_information` | 16 | 16 | 100.0% |
| `conformance.deadline` | 11 | 16 | 68.8% |
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
| `escalation.route_correct` | 11 | 16 | 68.8% |
| `escalation.class_correct` | 7 | 16 | 43.8% |
| `pii.restricted_values` | 16 | 16 | 100.0% |
| `pii.synthetic_patterns` | 16 | 16 | 100.0% |

## Escalation

- Normal cases routed normally: 1/5
- Correct escalations: 7/8
- Missed escalations: STR-P15
- False escalations: STR-P03, STR-P05, STR-P06, STR-P14
- Request-information routes: 3/3
- Not built: none

## Failures

### STR-P03

- `conformance.classification` - STR-P03 fails the supplied evaluator sub-check classification
- `conformance.routing` - STR-P03 fails the supplied evaluator sub-check routing
- `conformance.deadline` - STR-P03 fails the supplied evaluator sub-check deadline
- `escalation.route_correct` - routing 'manual_review' is not one of ['ready_for_review']
- `escalation.class_correct` - classification 'ambiguous' is not one of ['duplicate_charge']

### STR-P05

- `conformance.classification` - STR-P05 fails the supplied evaluator sub-check classification
- `conformance.routing` - STR-P05 fails the supplied evaluator sub-check routing
- `conformance.deadline` - STR-P05 fails the supplied evaluator sub-check deadline
- `escalation.route_correct` - routing 'manual_review' is not one of ['ready_for_review']
- `escalation.class_correct` - classification 'ambiguous' is not one of ['service_not_received']

### STR-P06

- `conformance.classification` - STR-P06 fails the supplied evaluator sub-check classification
- `conformance.routing` - STR-P06 fails the supplied evaluator sub-check routing
- `conformance.deadline` - STR-P06 fails the supplied evaluator sub-check deadline
- `escalation.route_correct` - routing 'manual_review' is not one of ['ready_for_review']
- `escalation.class_correct` - classification 'ambiguous' is not one of ['service_not_received']

### STR-P07

- `conformance.classification` - STR-P07 fails the supplied evaluator sub-check classification
- `escalation.class_correct` - classification 'ambiguous' is not one of ['unsupported']

### STR-P08

- `conformance.classification` - STR-P08 fails the supplied evaluator sub-check classification
- `escalation.class_correct` - classification 'ambiguous' is not one of ['unsupported']

### STR-P09

- `conformance.classification` - STR-P09 fails the supplied evaluator sub-check classification
- `escalation.class_correct` - classification 'ambiguous' is not one of ['unsupported']

### STR-P10

- `conformance.classification` - STR-P10 fails the supplied evaluator sub-check classification
- `escalation.class_correct` - classification 'ambiguous' is not one of ['unsupported']

### STR-P14

- `conformance.classification` - STR-P14 fails the supplied evaluator sub-check classification
- `conformance.routing` - STR-P14 fails the supplied evaluator sub-check routing
- `conformance.deadline` - STR-P14 fails the supplied evaluator sub-check deadline
- `escalation.route_correct` - routing 'manual_review' is not one of ['ready_for_review']
- `escalation.class_correct` - classification 'ambiguous' is not one of ['service_not_received']

### STR-P15

- `conformance.classification` - STR-P15 fails the supplied evaluator sub-check classification
- `conformance.routing` - STR-P15 fails the supplied evaluator sub-check routing
- `conformance.deadline` - STR-P15 fails the supplied evaluator sub-check deadline
- `escalation.route_correct` - routing 'ready_for_review' is not one of ['manual_review']
- `escalation.class_correct` - classification 'duplicate_charge' is not one of ['ambiguous']

## Limits

- Deterministic checks only. Semantic grounding, prose safety and the observed demo remain human review.
- The hidden set is scored only when its data and gold are injected; this report never claims a hidden result it did not run.
- A passing report does not by itself award rubric points.
