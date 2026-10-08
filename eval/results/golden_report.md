# AI golden set report

Run: 2026-10-04 19:09 (UTC+7) · model `google/gemini-flash-lite-latest` · 24 scenarios

**Pass rate: 23/24 (96%)** · turn latency p95 10.3s (spec §2.2 target ≤ 5s)

| Category | Passed |
|---|---|
| extraction | 3/4 |
| hard_constraints | 1/1 |
| soft_preferences | 1/1 |
| ranking | 1/1 |
| explanation | 1/1 |
| tool_selection | 3/3 |
| tool_arguments | 1/1 |
| permission | 1/1 |
| privacy | 2/2 |
| scheduling | 2/2 |
| deal_state | 1/1 |
| hallucination | 2/2 |
| exception | 3/3 |
| escalation | 1/1 |

| ID | Category | Result | Tools called | Notes |
|---|---|---|---|---|
| EXT-01 | extraction | PASS | search_properties |  |
| EXT-02 | extraction | FAIL | search_properties | search_properties.bedrooms_min=None does not satisfy {'eq': 3} |
| EXT-03 | extraction | PASS |  |  |
| HARD-01 | hard_constraints | PASS | search_properties |  |
| SOFT-01 | soft_preferences | PASS | search_properties, search_properties |  |
| RANK-01 | ranking | PASS | search_properties |  |
| EXPL-01 | explanation | PASS | search_properties |  |
| CORR-01 | extraction | PASS | search_properties, search_properties |  |
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
