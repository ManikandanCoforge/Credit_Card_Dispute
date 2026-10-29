# Hybrid model run

Model: `azure_openai/gpt-6-luna`
Commit: `e4368df`
Generated: 2026-10-29T06:01:30Z

| Suite | Design | Passed | Wrong ready | Manual review | Not built | Calls | Tokens in/out |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dev | rules | 12 / 12 | 0 | 3 | 0 | 0 | 0 / 0 |
| dev | hybrid | 12 / 12 | 0 | 3 | 0 | 7 | 981 / 244 |
| synth | rules | 25 / 31 | 0 | 15 | 0 | 0 | 0 / 0 |
| synth | hybrid | 30 / 31 | 0 | 12 | 0 | 22 | 4494 / 663 |
| stress | rules | 7 / 16 | 1 | 11 | 0 | 0 | 0 / 0 |
| stress | hybrid | 16 / 16 | 0 | 8 | 0 | 16 | 5585 / 604 |
| holdout | rules | 6 / 8 | 0 | 3 | 0 | 0 | 0 / 0 |
| holdout | hybrid | 8 / 8 | 0 | 2 | 0 | 9 | 2226 / 410 |

## Failures

- synth / rules: SYN-S03 (classification, deadline, routing)
- synth / rules: SYN-S04 (classification, deadline, routing)
- synth / rules: SYN-S05 (classification, deadline, routing)
- synth / rules: SYN-S07 (classification)
- synth / rules: SYN-S26 (classification, deadline, routing)
- synth / rules: SYN-S31 (classification)
- synth / hybrid: SYN-S26 (classification, deadline, routing)
- stress / rules: STR-P03 (classification, deadline, routing)
- stress / rules: STR-P05 (classification, deadline, routing)
- stress / rules: STR-P06 (classification, deadline, routing)
- stress / rules: STR-P07 (classification)
- stress / rules: STR-P08 (classification)
- stress / rules: STR-P09 (classification)
- stress / rules: STR-P10 (classification)
- stress / rules: STR-P14 (classification, deadline, routing)
- stress / rules: STR-P15 (classification, deadline, routing)
- holdout / rules: HLD-H06 (classification)
- holdout / rules: HLD-H08 (classification, deadline, routing)
