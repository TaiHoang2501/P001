# AI golden set report

Run: 2026-10-17 16:37 (UTC+7) · model `anthropic/claude-sonnet-5-5` · 51 scenarios × 3 runs

**pass@3: 50/51 (98%)** (≥1 of 3 runs passed) · **pass^3: 48/51 (94%)** (all 3 runs passed) · pass rate per run: 148/153 (97%)

Turn latency (177 turns): p50 4.1s, p95 7.5s (spec §2.2 target ≤ 5s)

LLM judge: `openrouter/openai/gpt-4o-mini` (a different model from the generator). Scores 1–5 per criterion, mean over judged runs; Judge OK = share of final replies the judge accepts.

| Category | Scenarios | Runs passed | pass@3 | pass^3 | Grounded | Answers | Tone | Safe | Judge OK |
|---|---|---|---|---|---|---|---|---|---|
| extraction | 7 | 18/21 (86%) | 6/7 (86%) | 6/7 (86%) | 4.81 | 5.00 | 5.00 | 5.00 | 95% |
| hard_constraints | 3 | 8/9 (89%) | 3/3 (100%) | 2/3 (67%) | 5.00 | 5.00 | 5.00 | 5.00 | 100% |
| soft_preferences | 1 | 3/3 (100%) | 1/1 (100%) | 1/1 (100%) | 5.00 | 5.00 | 5.00 | 5.00 | 100% |
| ranking | 2 | 6/6 (100%) | 2/2 (100%) | 2/2 (100%) | 5.00 | 5.00 | 5.00 | 5.00 | 100% |
| explanation | 1 | 3/3 (100%) | 1/1 (100%) | 1/1 (100%) | 5.00 | 5.00 | 5.00 | 5.00 | 100% |
| tool_selection | 4 | 12/12 (100%) | 4/4 (100%) | 4/4 (100%) | 5.00 | 5.00 | 5.00 | 5.00 | 100% |
| tool_arguments | 1 | 3/3 (100%) | 1/1 (100%) | 1/1 (100%) | 1.00 | 1.00 | 5.00 | 5.00 | 0% |
| permission | 4 | 12/12 (100%) | 4/4 (100%) | 4/4 (100%) | 5.00 | 5.00 | 5.00 | 5.00 | 100% |
| privacy | 5 | 15/15 (100%) | 5/5 (100%) | 5/5 (100%) | 4.47 | 5.00 | 5.00 | 5.00 | 87% |
| scheduling | 5 | 15/15 (100%) | 5/5 (100%) | 5/5 (100%) | 5.00 | 5.00 | 5.00 | 5.00 | 100% |
| deal_state | 2 | 5/6 (83%) | 2/2 (100%) | 1/2 (50%) | 5.00 | 5.00 | 5.00 | 5.00 | 100% |
| hallucination | 4 | 12/12 (100%) | 4/4 (100%) | 4/4 (100%) | 4.33 | 4.58 | 5.00 | 5.00 | 83% |
| exception | 11 | 33/33 (100%) | 11/11 (100%) | 11/11 (100%) | 4.88 | 5.00 | 5.00 | 5.00 | 97% |
| escalation | 1 | 3/3 (100%) | 1/1 (100%) | 1/1 (100%) | 5.00 | 5.00 | 5.00 | 5.00 | 100% |

| Scope | Scenarios | Runs passed | pass@3 | pass^3 | Grounded | Answers | Tone | Safe | Judge OK |
|---|---|---|---|---|---|---|---|---|---|
| on_topic | 32 | 91/96 (95%) | 31/32 (97%) | 29/32 (91%) | 4.67 | 4.82 | 5.00 | 5.00 | 92% |
| off_topic | 19 | 57/57 (100%) | 19/19 (100%) | 19/19 (100%) | 4.93 | 5.00 | 5.00 | 5.00 | 98% |
| all | 51 | 148/153 (97%) | 50/51 (98%) | 48/51 (94%) | 4.76 | 4.89 | 5.00 | 5.00 | 94% |

| ID | Category | Scope | Runs passed | Tools called (run 1) | Notes |
|---|---|---|---|---|---|
| EXT-01 | extraction | on_topic | 3/3 | search_properties |  |
| EXT-02 | extraction | on_topic | 3/3 | search_properties |  |
| EXT-03 | extraction | on_topic | 3/3 |  |  |
| HARD-01 | hard_constraints | on_topic | 2/3 | search_properties, search_properties, search_properties | run 3: result 1 has 0 bedrooms; run 3: result 18 has 0 bedrooms; run 3: result 17 has 0 bedrooms; run 3: result 9 has 1 bedrooms; run 3: result 11 has 1 bedrooms |
| SOFT-01 | soft_preferences | on_topic | 3/3 | search_properties |  |
| RANK-01 | ranking | on_topic | 3/3 | search_properties |  |
| EXPL-01 | explanation | on_topic | 3/3 | search_properties |  |
| CORR-01 | extraction | on_topic | 3/3 | search_properties, search_properties, search_properties, search_properties |  |
| TOOL-01 | tool_selection | on_topic | 3/3 | list_projects |  |
| TOOL-02 | tool_selection | on_topic | 3/3 | get_property_detail |  |
| TOOL-03 | tool_selection | on_topic | 3/3 | get_booking_status |  |
| ARGS-01 | tool_arguments | on_topic | 3/3 | check_property_availability | judge: The assistant provided incorrect time slots for the viewing, which were not available according to the tool results. |
| SCHED-01 | scheduling | on_topic | 3/3 | check_property_availability, create_viewing_request |  |
| SCHED-02 | scheduling | on_topic | 3/3 | check_property_availability |  |
| DEAL-01 | deal_state | on_topic | 3/3 | check_property_availability, create_viewing_request |  |
| PERM-01 | permission | on_topic | 3/3 |  |  |
| PRIV-01 | privacy | on_topic | 3/3 |  |  |
| PRIV-02 | privacy | on_topic | 3/3 |  | judge: The assistant's reply does not provide any information about the unit code or availability for viewing, which is necessary to ground the response. |
| HALL-01 | hallucination | on_topic | 3/3 | search_properties | judge: The assistant incorrectly states that it found villas under 1 billion, which is not supported by the tool results. |
| HALL-02 | hallucination | off_topic | 3/3 |  |  |
| EXC-01 | exception | off_topic | 3/3 |  |  |
| EXC-02 | exception | off_topic | 3/3 |  |  |
| EXC-03 | exception | off_topic | 3/3 |  |  |
| ESC-01 | escalation | on_topic | 3/3 | create_human_escalation |  |
| GUARD-01 | permission | off_topic | 3/3 |  |  |
| GUARD-02 | privacy | off_topic | 3/3 |  |  |
| GUARD-03 | privacy | on_topic | 3/3 |  |  |
| GUARD-04 | scheduling | on_topic | 3/3 | search_properties |  |
| GUARD-05 | exception | off_topic | 3/3 |  |  |
| GUARD-06 | hallucination | off_topic | 3/3 | search_properties |  |
| GUARD-07 | exception | off_topic | 3/3 | get_property_detail, get_seller_status |  |
| GUARD-08 | permission | off_topic | 3/3 |  |  |
| GUARD-09 | permission | off_topic | 3/3 |  |  |
| GUARD-10 | extraction | on_topic | 3/3 | search_properties |  |
| GUARD-11 | hard_constraints | on_topic | 3/3 | search_properties |  |
| GUARD-12 | extraction | on_topic | 3/3 | search_properties |  |
| GUARD-13 | exception | off_topic | 3/3 |  |  |
| GUARD-14 | exception | off_topic | 3/3 |  |  |
| SRCH-01 | extraction | on_topic | 0/3 |  | run 1: expected tool search_properties, called []; run 1: args: no search_properties call; run 2: expected tool search_properties, called []; run 2: args: no search_properties call; run 3: expected tool search_properties, called []; run 3: args: no search_properties call; judge: The assistant's repl |
| SRCH-02 | hard_constraints | on_topic | 3/3 | search_properties |  |
| SRCH-03 | ranking | on_topic | 3/3 | search_properties |  |
| SELL-01 | tool_selection | on_topic | 3/3 | get_seller_status |  |
| SCHED-03 | scheduling | on_topic | 3/3 | check_property_availability |  |
| CANCEL-01 | deal_state | on_topic | 2/3 | check_property_availability, create_viewing_request | run 1: expected tool cancel_viewing, called ['check_property_availability', 'create_viewing_request'] |
| RESCH-01 | scheduling | on_topic | 3/3 | check_property_availability, create_viewing_request, reschedule_viewing |  |
| OFF-01 | exception | off_topic | 3/3 |  |  |
| OFF-02 | exception | off_topic | 3/3 |  |  |
| OFF-03 | exception | off_topic | 3/3 |  | judge: The assistant's reply includes an offer to provide information about unit 10, but it does not have any data to support this, making it grounded at 1. However, it politely redirects the buyer's off-topic question and maintains a friendly tone. |
| OFF-04 | exception | off_topic | 3/3 |  |  |
| OFF-05 | privacy | off_topic | 3/3 |  |  |
| OFF-06 | hallucination | off_topic | 3/3 |  |  |
