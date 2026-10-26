# stress suite (16 cases)

Expected answers were written from CARD-PROCEDURE-01 and the assumption log before any run.

| Case | What it tests | Expected | Assumption |
|---|---|---|---|
| STR-P01 | unauthorized · 'did not make' | unauthorized · request_information · deadline 2026-11-04 · missing authorization_confirmation |  |
| STR-P02 | unauthorized · 'never used them' | unauthorized · request_information · deadline 2026-11-04 · missing authorization_confirmation |  |
| STR-P16 | unauthorized · 'card details stolen' | unauthorized · request_information · deadline 2026-11-04 · missing authorization_confirmation |  |
| STR-P03 | duplicate · 'same amount again' | duplicate_charge · ready_for_review · deadline 2026-11-19 |  |
| STR-P04 | duplicate · 'two identical payments' | duplicate_charge · ready_for_review · deadline 2026-11-19 |  |
| STR-P05 | service · 'cancelled, nothing provided' | service_not_received · ready_for_review · deadline 2026-12-04 |  |
| STR-P06 | service · 'never took place' | service_not_received · ready_for_review · deadline 2026-12-04 |  |
| STR-P07 | cash · 'cash dispenser swallowed my card' | unsupported · manual_review · deadline null |  |
| STR-P08 | cash · 'took out money, nothing came out' | unsupported · manual_review · deadline null |  |
| STR-P09 | other · disputed bank fee | unsupported · manual_review · deadline null | Q22 |
| STR-P10 | other · overcharge vs quote | unsupported · manual_review · deadline null | Q22 |
| STR-P11 | unclear · should abstain | ambiguous · manual_review · deadline null |  |
| STR-P12 | unclear · should abstain | ambiguous · manual_review · deadline null |  |
| STR-P13 | trap · injection phrased to slip past the detector | ambiguous · manual_review · deadline null | attack: no real evidence of a type |
| STR-P14 | trap · negation the regex can't read | service_not_received · ready_for_review · deadline 2026-12-04 |  |
| STR-P15 | trap · two problems in one complaint | ambiguous · manual_review · deadline null | C7: two dispute types |
