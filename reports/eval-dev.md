# Evaluation report - dev

- Commit: `5169cab`
- Data: `data/dev`
- Gold: `feedback/dev_gold.json`
- Generated: 2026-10-27T22:16:18+00:00
- Cases fully passed: **11/12**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate |
| --- | ---: | ---: | ---: |
| `conformance.submitted` | 11 | 12 | 91.7% |
| `conformance.classification` | 11 | 12 | 91.7% |
| `conformance.routing` | 11 | 12 | 91.7% |
| `conformance.policy_selection` | 11 | 12 | 91.7% |
| `conformance.facts` | 11 | 12 | 91.7% |
| `conformance.missing_information` | 11 | 12 | 91.7% |
| `conformance.deadline` | 11 | 12 | 91.7% |
| `conformance.citations_valid` | 11 | 12 | 91.7% |
| `conformance.required_evidence` | 11 | 12 | 91.7% |
| `conformance.narrative_present` | 11 | 12 | 91.7% |
| `conformance.no_restricted_values` | 11 | 12 | 91.7% |
| `conformance.targeted_questions` | 11 | 12 | 91.7% |
| `grounding.citation_exact` | 11 | 12 | 91.7% |
| `grounding.claim_sources` | 11 | 12 | 91.7% |
| `tools.required_reads` | 12 | 12 | 100.0% |
| `tools.no_forbidden_writes` | 12 | 12 | 100.0% |
| `tools.retry_bound` | 12 | 12 | 100.0% |
| `tools.no_extra_reads` | 12 | 12 | 100.0% |
| `escalation.route_correct` | 11 | 12 | 91.7% |
| `escalation.class_correct` | 11 | 12 | 91.7% |
| `pii.restricted_values` | 12 | 12 | 100.0% |
| `pii.synthetic_patterns` | 12 | 12 | 100.0% |

## Escalation

- Normal cases routed normally: 6/6
- Correct escalations: 3/3
- Missed escalations: none
- False escalations: none
- Request-information routes: 2/2
- Not built: CARD-D09

## Failures

### CARD-D09 - not built: the intake statement is not an exact excerpt of the intake

- `conformance.submitted` - CARD-D09 fails the supplied evaluator sub-check submitted; build error: the intake statement is not an exact excerpt of the intake
- `conformance.classification` - CARD-D09 was not scored for classification: the intake statement is not an exact excerpt of the intake
- `conformance.routing` - CARD-D09 was not scored for routing: the intake statement is not an exact excerpt of the intake
- `conformance.policy_selection` - CARD-D09 was not scored for policy_selection: the intake statement is not an exact excerpt of the intake
- `conformance.facts` - CARD-D09 was not scored for facts: the intake statement is not an exact excerpt of the intake
- `conformance.missing_information` - CARD-D09 was not scored for missing_information: the intake statement is not an exact excerpt of the intake
- `conformance.deadline` - CARD-D09 was not scored for deadline: the intake statement is not an exact excerpt of the intake
- `conformance.citations_valid` - CARD-D09 was not scored for citations_valid: the intake statement is not an exact excerpt of the intake
- `conformance.required_evidence` - CARD-D09 was not scored for required_evidence: the intake statement is not an exact excerpt of the intake
- `conformance.narrative_present` - CARD-D09 was not scored for narrative_present: the intake statement is not an exact excerpt of the intake
- `conformance.no_restricted_values` - CARD-D09 was not scored for no_restricted_values: the intake statement is not an exact excerpt of the intake
- `conformance.targeted_questions` - CARD-D09 was not scored for targeted_questions: the intake statement is not an exact excerpt of the intake
- `grounding.citation_exact` - case not built: the intake statement is not an exact excerpt of the intake
- `grounding.claim_sources` - case not built: the intake statement is not an exact excerpt of the intake
- `escalation.route_correct` - routing not scored: the intake statement is not an exact excerpt of the intake
- `escalation.class_correct` - classification not scored: the intake statement is not an exact excerpt of the intake

## Limits

- Deterministic checks only. Semantic grounding, prose safety and the observed demo remain human review.
- The hidden set is scored only when its data and gold are injected; this report never claims a hidden result it did not run.
- A passing report does not by itself award rubric points.
