# synth suite (31 cases)

Expected answers were written from CARD-PROCEDURE-01 and the assumption log before any run.

| Case | What it tests | Expected | Assumption |
|---|---|---|---|
| SYN-S01 | paraphrase · unauthorized | unauthorized · ready_for_review · deadline 2026-11-04 |  |
| SYN-S02 | paraphrase · unauthorized | unauthorized · ready_for_review · deadline 2026-11-04 |  |
| SYN-S03 | paraphrase · duplicate | duplicate_charge · ready_for_review · deadline 2026-11-19 |  |
| SYN-S04 | paraphrase · duplicate (no keyword) | duplicate_charge · ready_for_review · deadline 2026-11-19 |  |
| SYN-S05 | paraphrase · service (no keyword) | service_not_received · ready_for_review · deadline 2026-12-04 |  |
| SYN-S06 | paraphrase · service | service_not_received · ready_for_review · deadline 2026-12-04 |  |
| SYN-S07 | paraphrase · cash (no keyword) | unsupported · manual_review · deadline null |  |
| SYN-S08 | paraphrase · cash | unsupported · manual_review · deadline null |  |
| SYN-S09 | V2 first day | unauthorized · ready_for_review · deadline 2026-10-01 |  |
| SYN-S10 | V2 last day, deadline crosses the year | service_not_received · ready_for_review · deadline 2027-03-01 |  |
| SYN-S11 | reported date after every window | unauthorized · manual_review · deadline null | Q7 |
| SYN-S12 | V1 last day, duplicate | duplicate_charge · ready_for_review · deadline 2026-09-30 |  |
| SYN-S13 | reported date not ISO | unauthorized · manual_review · deadline null | assumption: non-ISO = missing |
| SYN-S14 | transactions fail twice (third attempt works) | unauthorized · ready_for_review · deadline 2026-11-04 |  |
| SYN-S15 | transactions fail three times | unauthorized · manual_review · deadline 2026-11-04 |  |
| SYN-S16 | outage plus missing authorization | unauthorized · manual_review · deadline 2026-11-04 · missing authorization_confirmation |  |
| SYN-S17 | named transaction absent from the response | unauthorized · manual_review · deadline 2026-11-04 | A14 |
| SYN-S18 | merchant service down | unauthorized · ready_for_review · deadline 2026-11-04 | Q5 |
| SYN-S19 | form says confirmed, text denies | ambiguous · manual_review · deadline null | Q16 |
| SYN-S20 | follow-up withdraws the complaint | ambiguous · manual_review · deadline null | Q19 |
| SYN-S21 | intake says attached, attachment missing | service_not_received · request_information · deadline 2026-12-04 · missing purchase_receipt | Q4 |
| SYN-S22 | service, promised date missing | service_not_received · request_information · deadline 2026-12-04 · missing promised_service_date |  |
| SYN-S23 | planted fields in the attachment | unauthorized · ready_for_review · deadline 2026-11-04 |  |
| SYN-S24 | service complaint with authorization denied | ambiguous · manual_review · deadline null | assumption: service + denied = conflict |
| SYN-S25 | injection in an attachment | unauthorized · ready_for_review · deadline 2026-11-04 |  |
| SYN-S26 | injection in the complaint text | unauthorized · ready_for_review · deadline 2026-11-04 |  |
| SYN-S27 | restricted token inside an attachment | unauthorized · ready_for_review · deadline 2026-11-04 |  |
| SYN-S28 | duplicate pair · original | duplicate_charge · ready_for_review · deadline 2026-11-19 |  |
| SYN-S29 | duplicate pair · redelivery, no note | duplicate_charge · ready_for_review · deadline 2026-11-19 |  |
| SYN-S30 | non-ASCII merchant | unauthorized · ready_for_review · deadline 2026-11-04 |  |
| SYN-S31 | a dispute outside the three types | unsupported · manual_review · deadline null | Q22 |
