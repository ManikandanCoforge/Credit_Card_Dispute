# Evaluation report - dev

- Commit: `36e3c6b`
- Data: `data/dev`
- Gold: `feedback/dev_gold.json`
- Generated: 2026-10-27T18:02:12+00:00
- Cases fully passed: **9/12**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate | 95% CI |
| --- | ---: | ---: | ---: | --- |
| `conformance.classification` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.routing` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.policy_selection` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.facts` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.missing_information` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.deadline` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.citations_valid` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.required_evidence` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.narrative_present` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.no_restricted_values` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.targeted_questions` | 9 | 9 | 100.0% | 70.1% - 100.0% |
| `conformance.submitted` | 0 | 3 | 0.0% | 0.0% - 56.2% |
| `grounding.citation_exact` | 9 | 12 | 75.0% | 46.8% - 91.1% |
| `grounding.claim_sources` | 9 | 12 | 75.0% | 46.8% - 91.1% |
| `tools.required_reads` | 10 | 12 | 83.3% | 55.2% - 95.3% |
| `tools.no_forbidden_writes` | 12 | 12 | 100.0% | 75.7% - 100.0% |
| `tools.retry_bound` | 12 | 12 | 100.0% | 75.7% - 100.0% |
| `tools.no_extra_reads` | 12 | 12 | 100.0% | 75.7% - 100.0% |
| `escalation.route_correct` | 9 | 12 | 75.0% | 46.8% - 91.1% |
| `escalation.class_correct` | 9 | 12 | 75.0% | 46.8% - 91.1% |
| `pii.restricted_values` | 12 | 12 | 100.0% | 75.7% - 100.0% |
| `pii.synthetic_patterns` | 12 | 12 | 100.0% | 75.7% - 100.0% |

## Escalation

- Normal cases routed normally: 5/7
- Correct escalations: 2/3
- Missed escalations: CARD-D07
- False escalations: none
- Request-information routes: 2/2

## Failures

### CARD-D07 - not built: BankReadError

- `conformance.submitted` - CARD-D07 fails the supplied evaluator sub-check submitted; build error: BankReadError
- `grounding.citation_exact` - case not built: BankReadError
- `grounding.claim_sources` - case not built: BankReadError
- `tools.required_reads` - transactions never answered 200 (attempts: 503); merchant was never read
- `escalation.route_correct` - routing not scored: BankReadError
- `escalation.class_correct` - classification not scored: BankReadError

### CARD-D09 - not built: the intake statement is not an exact excerpt of the intake

- `conformance.submitted` - CARD-D09 fails the supplied evaluator sub-check submitted; build error: the intake statement is not an exact excerpt of the intake
- `grounding.citation_exact` - case not built: the intake statement is not an exact excerpt of the intake
- `grounding.claim_sources` - case not built: the intake statement is not an exact excerpt of the intake
- `escalation.route_correct` - routing not scored: the intake statement is not an exact excerpt of the intake
- `escalation.class_correct` - classification not scored: the intake statement is not an exact excerpt of the intake

### CARD-D10 - not built: BankReadError

- `conformance.submitted` - CARD-D10 fails the supplied evaluator sub-check submitted; build error: BankReadError
- `grounding.citation_exact` - case not built: BankReadError
- `grounding.claim_sources` - case not built: BankReadError
- `tools.required_reads` - transactions never answered 200 (attempts: 503); merchant was never read
- `escalation.route_correct` - routing not scored: BankReadError
- `escalation.class_correct` - classification not scored: BankReadError

## Limits

- Deterministic checks only. Semantic grounding, prose safety and the observed demo remain human review.
- The hidden set is scored only when its data and gold are injected; this report never claims a hidden result it did not run.
- A passing report does not by itself award rubric points.
