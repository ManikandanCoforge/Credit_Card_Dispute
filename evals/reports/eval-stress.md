# Evaluation report - stress

- Commit: `8a915e0`
- Data: `evals/fixtures/stress/data`
- Gold: `evals/fixtures/stress/gold.json`
- Generated: 2026-10-28T03:49:40+00:00
- Cases fully passed: **4/16**
- Format errors: 0

## Metrics

| Metric | Passed | n | Rate |
| --- | ---: | ---: | ---: |
| `conformance.submitted` | 6 | 16 | 37.5% |
| `conformance.classification` | 5 | 16 | 31.2% |
| `conformance.routing` | 5 | 16 | 31.2% |
| `conformance.policy_selection` | 6 | 16 | 37.5% |
| `conformance.facts` | 6 | 16 | 37.5% |
| `conformance.missing_information` | 6 | 16 | 37.5% |
| `conformance.deadline` | 5 | 16 | 31.2% |
| `conformance.citations_valid` | 6 | 16 | 37.5% |
| `conformance.required_evidence` | 6 | 16 | 37.5% |
| `conformance.narrative_present` | 6 | 16 | 37.5% |
| `conformance.no_restricted_values` | 6 | 16 | 37.5% |
| `conformance.targeted_questions` | 6 | 16 | 37.5% |
| `grounding.citation_exact` | 6 | 16 | 37.5% |
| `grounding.claim_sources` | 5 | 16 | 31.2% |
| `tools.required_reads` | 16 | 16 | 100.0% |
| `tools.no_forbidden_writes` | 16 | 16 | 100.0% |
| `tools.retry_bound` | 16 | 16 | 100.0% |
| `tools.no_extra_reads` | 16 | 16 | 100.0% |
| `escalation.route_correct` | 5 | 16 | 31.2% |
| `escalation.class_correct` | 5 | 16 | 31.2% |
| `pii.restricted_values` | 16 | 16 | 100.0% |
| `pii.synthetic_patterns` | 16 | 16 | 100.0% |

## Escalation

- Normal cases routed normally: 1/1
- Correct escalations: 1/2
- Missed escalations: STR-P15
- False escalations: none
- Request-information routes: 3/3
- Not built: STR-P03, STR-P05, STR-P06, STR-P07, STR-P08, STR-P09, STR-P10, STR-P11, STR-P12, STR-P14

## Failures

### STR-P03 - not built: the intake supports no supported classification

- `conformance.submitted` - STR-P03 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - STR-P03 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - STR-P03 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - STR-P03 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - STR-P03 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - STR-P03 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - STR-P03 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - STR-P03 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - STR-P03 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - STR-P03 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - STR-P03 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - STR-P03 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### STR-P05 - not built: the intake supports no supported classification

- `conformance.submitted` - STR-P05 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - STR-P05 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - STR-P05 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - STR-P05 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - STR-P05 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - STR-P05 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - STR-P05 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - STR-P05 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - STR-P05 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - STR-P05 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - STR-P05 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - STR-P05 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### STR-P06 - not built: the intake supports no supported classification

- `conformance.submitted` - STR-P06 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - STR-P06 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - STR-P06 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - STR-P06 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - STR-P06 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - STR-P06 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - STR-P06 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - STR-P06 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - STR-P06 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - STR-P06 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - STR-P06 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - STR-P06 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### STR-P07 - not built: the intake supports no supported classification

- `conformance.submitted` - STR-P07 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - STR-P07 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - STR-P07 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - STR-P07 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - STR-P07 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - STR-P07 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - STR-P07 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - STR-P07 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - STR-P07 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - STR-P07 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - STR-P07 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - STR-P07 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### STR-P08 - not built: the intake supports no supported classification

- `conformance.submitted` - STR-P08 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - STR-P08 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - STR-P08 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - STR-P08 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - STR-P08 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - STR-P08 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - STR-P08 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - STR-P08 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - STR-P08 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - STR-P08 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - STR-P08 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - STR-P08 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### STR-P09 - not built: the intake supports no supported classification

- `conformance.submitted` - STR-P09 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - STR-P09 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - STR-P09 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - STR-P09 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - STR-P09 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - STR-P09 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - STR-P09 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - STR-P09 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - STR-P09 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - STR-P09 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - STR-P09 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - STR-P09 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### STR-P10 - not built: the intake supports no supported classification

- `conformance.submitted` - STR-P10 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - STR-P10 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - STR-P10 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - STR-P10 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - STR-P10 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - STR-P10 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - STR-P10 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - STR-P10 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - STR-P10 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - STR-P10 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - STR-P10 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - STR-P10 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### STR-P11 - not built: the intake supports no supported classification

- `conformance.submitted` - STR-P11 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - STR-P11 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - STR-P11 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - STR-P11 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - STR-P11 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - STR-P11 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - STR-P11 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - STR-P11 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - STR-P11 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - STR-P11 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - STR-P11 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - STR-P11 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### STR-P12 - not built: the intake supports no supported classification

- `conformance.submitted` - STR-P12 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - STR-P12 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - STR-P12 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - STR-P12 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - STR-P12 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - STR-P12 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - STR-P12 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - STR-P12 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - STR-P12 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - STR-P12 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - STR-P12 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - STR-P12 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

### STR-P13

- `grounding.claim_sources` - missing claim citations: manual_review_rule

### STR-P14 - not built: the intake supports no supported classification

- `conformance.submitted` - STR-P14 fails the supplied evaluator sub-check submitted; build error: the intake supports no supported classification
- `conformance.classification` - STR-P14 was not scored for classification: the intake supports no supported classification
- `conformance.routing` - STR-P14 was not scored for routing: the intake supports no supported classification
- `conformance.policy_selection` - STR-P14 was not scored for policy_selection: the intake supports no supported classification
- `conformance.facts` - STR-P14 was not scored for facts: the intake supports no supported classification
- `conformance.missing_information` - STR-P14 was not scored for missing_information: the intake supports no supported classification
- `conformance.deadline` - STR-P14 was not scored for deadline: the intake supports no supported classification
- `conformance.citations_valid` - STR-P14 was not scored for citations_valid: the intake supports no supported classification
- `conformance.required_evidence` - STR-P14 was not scored for required_evidence: the intake supports no supported classification
- `conformance.narrative_present` - STR-P14 was not scored for narrative_present: the intake supports no supported classification
- `conformance.no_restricted_values` - STR-P14 was not scored for no_restricted_values: the intake supports no supported classification
- `conformance.targeted_questions` - STR-P14 was not scored for targeted_questions: the intake supports no supported classification
- `grounding.citation_exact` - case not built: the intake supports no supported classification
- `grounding.claim_sources` - case not built: the intake supports no supported classification
- `escalation.route_correct` - routing not scored: the intake supports no supported classification
- `escalation.class_correct` - classification not scored: the intake supports no supported classification

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
