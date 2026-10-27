# Evaluation report - dev

- Commit: `618abca`
- Data: `data/dev`
- Gold: `feedback/dev_gold.json`
- Generated: 2026-10-27T20:33:00+00:00
- Cases fully passed: **9/12**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate |
| --- | ---: | ---: | ---: |
| `conformance.submitted` | 9 | 12 | 75.0% |
| `conformance.classification` | 9 | 12 | 75.0% |
| `conformance.routing` | 9 | 12 | 75.0% |
| `conformance.policy_selection` | 9 | 12 | 75.0% |
| `conformance.facts` | 9 | 12 | 75.0% |
| `conformance.missing_information` | 9 | 12 | 75.0% |
| `conformance.deadline` | 9 | 12 | 75.0% |
| `conformance.citations_valid` | 9 | 12 | 75.0% |
| `conformance.required_evidence` | 9 | 12 | 75.0% |
| `conformance.narrative_present` | 9 | 12 | 75.0% |
| `conformance.no_restricted_values` | 9 | 12 | 75.0% |
| `conformance.targeted_questions` | 9 | 12 | 75.0% |
| `grounding.citation_exact` | 9 | 12 | 75.0% |
| `grounding.claim_sources` | 9 | 12 | 75.0% |
| `tools.required_reads` | 10 | 12 | 83.3% |
| `tools.no_forbidden_writes` | 12 | 12 | 100.0% |
| `tools.retry_bound` | 12 | 12 | 100.0% |
| `tools.no_extra_reads` | 12 | 12 | 100.0% |
| `escalation.route_correct` | 9 | 12 | 75.0% |
| `escalation.class_correct` | 9 | 12 | 75.0% |
| `pii.restricted_values` | 12 | 12 | 100.0% |
| `pii.synthetic_patterns` | 12 | 12 | 100.0% |

## Escalation

- Normal cases routed normally: 5/5
- Correct escalations: 2/2
- Missed escalations: none
- False escalations: none
- Request-information routes: 2/2
- Not built: CARD-D07, CARD-D09, CARD-D10

## Failures

### CARD-D07 - not built: BankReadError

- `conformance.submitted` - CARD-D07 fails the supplied evaluator sub-check submitted; build error: BankReadError
- `conformance.classification` - CARD-D07 was not scored for classification: BankReadError
- `conformance.routing` - CARD-D07 was not scored for routing: BankReadError
- `conformance.policy_selection` - CARD-D07 was not scored for policy_selection: BankReadError
- `conformance.facts` - CARD-D07 was not scored for facts: BankReadError
- `conformance.missing_information` - CARD-D07 was not scored for missing_information: BankReadError
- `conformance.deadline` - CARD-D07 was not scored for deadline: BankReadError
- `conformance.citations_valid` - CARD-D07 was not scored for citations_valid: BankReadError
- `conformance.required_evidence` - CARD-D07 was not scored for required_evidence: BankReadError
- `conformance.narrative_present` - CARD-D07 was not scored for narrative_present: BankReadError
- `conformance.no_restricted_values` - CARD-D07 was not scored for no_restricted_values: BankReadError
- `conformance.targeted_questions` - CARD-D07 was not scored for targeted_questions: BankReadError
- `grounding.citation_exact` - case not built: BankReadError
- `grounding.claim_sources` - case not built: BankReadError
- `tools.required_reads` - transactions answered 503 and was not retried; merchant was never read
- `escalation.route_correct` - routing not scored: BankReadError
- `escalation.class_correct` - classification not scored: BankReadError

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

### CARD-D10 - not built: BankReadError

- `conformance.submitted` - CARD-D10 fails the supplied evaluator sub-check submitted; build error: BankReadError
- `conformance.classification` - CARD-D10 was not scored for classification: BankReadError
- `conformance.routing` - CARD-D10 was not scored for routing: BankReadError
- `conformance.policy_selection` - CARD-D10 was not scored for policy_selection: BankReadError
- `conformance.facts` - CARD-D10 was not scored for facts: BankReadError
- `conformance.missing_information` - CARD-D10 was not scored for missing_information: BankReadError
- `conformance.deadline` - CARD-D10 was not scored for deadline: BankReadError
- `conformance.citations_valid` - CARD-D10 was not scored for citations_valid: BankReadError
- `conformance.required_evidence` - CARD-D10 was not scored for required_evidence: BankReadError
- `conformance.narrative_present` - CARD-D10 was not scored for narrative_present: BankReadError
- `conformance.no_restricted_values` - CARD-D10 was not scored for no_restricted_values: BankReadError
- `conformance.targeted_questions` - CARD-D10 was not scored for targeted_questions: BankReadError
- `grounding.citation_exact` - case not built: BankReadError
- `grounding.claim_sources` - case not built: BankReadError
- `tools.required_reads` - transactions answered 503 and was not retried; merchant was never read
- `escalation.route_correct` - routing not scored: BankReadError
- `escalation.class_correct` - classification not scored: BankReadError

## Limits

- Deterministic checks only. Semantic grounding, prose safety and the observed demo remain human review.
- The hidden set is scored only when its data and gold are injected; this report never claims a hidden result it did not run.
- A passing report does not by itself award rubric points.
