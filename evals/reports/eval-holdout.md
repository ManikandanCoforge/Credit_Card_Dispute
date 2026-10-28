# Evaluation report - holdout

- Commit: `8a915e0`
- Data: `evals/fixtures/holdout/data`
- Gold: `evals/fixtures/holdout/gold.json`
- Generated: 2026-10-28T03:49:38+00:00
- Cases fully passed: **3/8**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate |
| --- | ---: | ---: | ---: |
| `conformance.submitted` | 4 | 8 | 50.0% |
| `conformance.classification` | 3 | 8 | 37.5% |
| `conformance.routing` | 3 | 8 | 37.5% |
| `conformance.policy_selection` | 4 | 8 | 50.0% |
| `conformance.facts` | 4 | 8 | 50.0% |
| `conformance.missing_information` | 4 | 8 | 50.0% |
| `conformance.deadline` | 3 | 8 | 37.5% |
| `conformance.citations_valid` | 4 | 8 | 50.0% |
| `conformance.required_evidence` | 4 | 8 | 50.0% |
| `conformance.narrative_present` | 4 | 8 | 50.0% |
| `conformance.no_restricted_values` | 4 | 8 | 50.0% |
| `conformance.targeted_questions` | 4 | 8 | 50.0% |
| `grounding.citation_exact` | 4 | 8 | 50.0% |
| `grounding.claim_sources` | 4 | 8 | 50.0% |
| `tools.required_reads` | 8 | 8 | 100.0% |
| `tools.no_forbidden_writes` | 8 | 8 | 100.0% |
| `tools.retry_bound` | 8 | 8 | 100.0% |
| `tools.no_extra_reads` | 8 | 8 | 100.0% |
| `escalation.route_correct` | 3 | 8 | 37.5% |
| `escalation.class_correct` | 3 | 8 | 37.5% |
| `pii.restricted_values` | 8 | 8 | 100.0% |
| `pii.synthetic_patterns` | 8 | 8 | 100.0% |

## Escalation

- Normal cases routed normally: 3/4
- Correct escalations: 0/0
- Missed escalations: none
- False escalations: HLD-H01
- Request-information routes: 0/0
- Not built: HLD-H05, HLD-H06, HLD-H07, HLD-H08

## Failures

### HLD-H01

- `conformance.classification` - HLD-H01 fails the supplied evaluator sub-check classification
- `conformance.routing` - HLD-H01 fails the supplied evaluator sub-check routing
- `conformance.deadline` - HLD-H01 fails the supplied evaluator sub-check deadline
- `escalation.route_correct` - routing 'manual_review' is not one of ['ready_for_review']
- `escalation.class_correct` - classification 'ambiguous' is not one of ['service_not_received']

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

### HLD-H06 - not built: the intake supports no supported classification

- `conformance.submitted` - HLD-H06 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - HLD-H06 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - HLD-H06 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - HLD-H06 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - HLD-H06 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - HLD-H06 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - HLD-H06 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - HLD-H06 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - HLD-H06 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - HLD-H06 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - HLD-H06 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - HLD-H06 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### HLD-H07 - not built: the intake supports no supported classification

- `conformance.submitted` - HLD-H07 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - HLD-H07 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - HLD-H07 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - HLD-H07 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - HLD-H07 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - HLD-H07 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - HLD-H07 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - HLD-H07 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - HLD-H07 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - HLD-H07 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - HLD-H07 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - HLD-H07 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### HLD-H08 - not built: the intake supports no supported classification

- `conformance.submitted` - HLD-H08 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - HLD-H08 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - HLD-H08 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - HLD-H08 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - HLD-H08 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - HLD-H08 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - HLD-H08 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - HLD-H08 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - HLD-H08 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - HLD-H08 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - HLD-H08 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - HLD-H08 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

## Limits

- Deterministic checks only. Semantic grounding, prose safety and the observed demo remain human review.
- The hidden set is scored only when its data and gold are injected; this report never claims a hidden result it did not run.
- A passing report does not by itself award rubric points.
