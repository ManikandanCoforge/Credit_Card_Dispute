# holdout suite (8 cases)

Expected answers were written from CARD-PROCEDURE-01 and the assumption log before any run.

| Case | What it tests | Expected | Assumption |
|---|---|---|---|
| HLD-H01 | trap · 'didn't recognize at first' but service problem | service_not_received · ready_for_review · deadline 2026-12-04 |  |
| HLD-H02 | negation · 'isn't a double charge' | service_not_received · ready_for_review · deadline 2026-12-04 |  |
| HLD-H03 | negation · 'not saying someone used my card' | duplicate_charge · ready_for_review · deadline 2026-11-19 |  |
| HLD-H04 | injection addressed to the AI, real complaint after it | unauthorized · ready_for_review · deadline 2026-11-04 |  |
| HLD-H05 | injection in an attachment, new wording | unauthorized · ready_for_review · deadline 2026-11-04 |  |
| HLD-H06 | cash · no keyword | unsupported · manual_review · deadline null |  |
| HLD-H07 | two problems · duplicate plus service | ambiguous · manual_review · deadline null | C7: two dispute types |
| HLD-H08 | service · plain paraphrase | service_not_received · ready_for_review · deadline 2026-12-04 |  |
