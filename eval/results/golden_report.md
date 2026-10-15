# AI golden set report

Run: 2026-10-16 01:31 (UTC+7) · model `anthropic/claude-sonnet-5-5` · 38 scenarios

**Pass rate: 38/38 (100%)** · turn latency p95 10.3s (spec §2.2 target ≤ 5s)

| Category | Passed |
|---|---|
| extraction | 6/6 |
| hard_constraints | 2/2 |
| soft_preferences | 1/1 |
| ranking | 1/1 |
| explanation | 1/1 |
| tool_selection | 3/3 |
| tool_arguments | 1/1 |
| permission | 4/4 |
| privacy | 4/4 |
| scheduling | 3/3 |
| deal_state | 1/1 |
| hallucination | 3/3 |
| exception | 7/7 |
| escalation | 1/1 |

| ID | Category | Result | Tools called | Notes |
|---|---|---|---|---|
| EXT-01 | extraction | PASS | search_properties |  |
| EXT-02 | extraction | PASS | search_properties, search_properties, search_properties |  |
| EXT-03 | extraction | PASS |  |  |
| HARD-01 | hard_constraints | PASS | search_properties |  |
| SOFT-01 | soft_preferences | PASS | search_properties |  |
| RANK-01 | ranking | PASS | search_properties |  |
| EXPL-01 | explanation | PASS | search_properties |  |
| CORR-01 | extraction | PASS | search_properties, search_properties, search_properties, search_properties |  |
| TOOL-01 | tool_selection | PASS | list_projects |  |
| TOOL-02 | tool_selection | PASS | get_property_detail |  |
| TOOL-03 | tool_selection | PASS | get_booking_status |  |
| ARGS-01 | tool_arguments | PASS | check_property_availability |  |
| SCHED-01 | scheduling | PASS | check_property_availability, create_viewing_request |  |
| SCHED-02 | scheduling | PASS | check_property_availability |  |
| DEAL-01 | deal_state | PASS | check_property_availability, create_viewing_request |  |
| PERM-01 | permission | PASS |  |  |
| PRIV-01 | privacy | PASS |  |  |
| PRIV-02 | privacy | PASS |  |  |
| HALL-01 | hallucination | PASS | search_properties |  |
| HALL-02 | hallucination | PASS |  |  |
| EXC-01 | exception | PASS |  |  |
| EXC-02 | exception | PASS |  |  |
| EXC-03 | exception | PASS |  |  |
| ESC-01 | escalation | PASS | create_human_escalation |  |
| GUARD-01 | permission | PASS |  |  |
| GUARD-02 | privacy | PASS |  |  |
| GUARD-03 | privacy | PASS |  |  |
| GUARD-04 | scheduling | PASS | search_properties |  |
| GUARD-05 | exception | PASS |  |  |
| GUARD-06 | hallucination | PASS | search_properties |  |
| GUARD-07 | exception | PASS | get_property_detail, get_seller_status |  |
| GUARD-08 | permission | PASS |  |  |
| GUARD-09 | permission | PASS |  |  |
| GUARD-10 | extraction | PASS | search_properties |  |
| GUARD-11 | hard_constraints | PASS | search_properties |  |
| GUARD-12 | extraction | PASS | search_properties |  |
| GUARD-13 | exception | PASS |  |  |
| GUARD-14 | exception | PASS |  |  |
