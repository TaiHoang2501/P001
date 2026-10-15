# BookingBot AI Agent Guidelines

## 1. Project Overview
- **Project:** AI Agent Direct Connect BĐS (tên MVP: **BookingBot AI Agent**) — Trợ lý AI-first giúp Buyer tìm đúng căn Vinhomes, kết nối trực tiếp với Seller đã xác thực và tự động khớp lịch xem nhà.
- **Domain:** Bất động sản / Vinhomes-only.
- **Spec reference:** `.specify/spec_final.md` (AI SPEC Draft v2.0).
- **Actors:** `Buyer` (Khách mua), `Seller / Owner` (Chủ căn có nhu cầu bán), `Investor / Operator` (Chủ đầu tư — trong MVP Operator = Chủ đầu tư), `AI Agent`, `Human Operator` (xử lý ngoại lệ).
- **Mô hình:** `Buyer → AI Agent → Seller`, trong đó **Chủ đầu tư = Trust & Transaction Layer** (xác thực Owner, Property, trạng thái căn, các bước giao dịch cần kiểm soát).
- **Product Thesis:** Buyer nhập nhu cầu → AI hiểu & matching → tìm căn đã xác thực → Buyer yêu cầu xem → **tạo Deal ID** → AI kết nối Seller → AI khớp lịch → **Owner xác nhận** → Viewing Hold → xem nhà → chuyển sang quy trình Chủ đầu tư khi cần. Giảm phụ thuộc vào Sale/trung gian và hạn chế chia sẻ PII.

---

## 2. Architecture & Tech Stack
- **Frontend:** React + Vite + TypeScript, Tailwind, TanStack Query, `openapi-fetch` với types sinh từ OpenAPI (`npm run gen:api`) (Responsive Web: Buyer AI Chat có streaming SSE, Seller Portal/Dashboard, Operator Console).
- **Backend (Source of Truth):** Python 3.11+ + FastAPI (RESTful, OpenAPI auto-docs, Pydantic, WebSocket server).
- **Agent Orchestrator:** LangGraph (stateful workflow, tool selection, multi-turn state, human-in-the-loop, error recovery).
- **Database:** PostgreSQL 15+ (relational, Full-text Search + `pg_trgm`, ACID, row-level locks, GiST exclusion constraints).
- **Media Storage:** Amazon S3 (ảnh/video căn, giấy tờ xác thực Owner) là đích dài hạn; hiện ảnh người bán tải lên được lưu trong PostgreSQL (`media_files`, phục vụ qua `/api/v1/media/{id}`; giấy tờ hỗ trợ xác thực là riêng tư — chỉ người gửi và Operator xem được).
- **Model Layer:** OpenAI API (`gpt-4o-mini` mặc định trong code, `gpt-4o` khi cần); spec cho phép Gemini/OpenAI. Bản demo trên Render dùng Gemini (`LLM_PROVIDER=google`, `gemini-flash-latest`, dự phòng `gemini-flash-lite-latest`). Cũng hỗ trợ Claude (`LLM_PROVIDER=anthropic`, mặc định `claude-opus-5-5`); model dự phòng có thể ở provider khác qua `LLM_FALLBACK_PROVIDER` (vd. Claude trước, OpenRouter `google/gemini-3.8-flash` khi Claude lỗi / hết credit).
- **Auth:** JWT + OTP. `OTP_PROVIDER=local` (mặc định; mã tự sinh, không gửi SMS, hiện trên màn hình ngoài production) hoặc `firebase` (Firebase Phone Auth sinh/gửi SMS/kiểm mã trên trình duyệt; backend xác minh Firebase ID token trong `src/services/firebase_auth.py`, cho cả đăng nhập và OTP sổ đỏ).
- **Realtime Chat:** WebSocket qua FastAPI (Buyer ↔ Seller, post-MVP — xem §6.3).
- **Notification:** SMS/Zalo/In-app (provider TBD).
- **Vector DB / RAG:** **Không dùng trong MVP** — recommendation = SQL hard filter + soft scoring.
- **Deployment / Observability:** Docker; Logs + Metrics + Audit.

---

## 3. Core Principles & Boundaries
1. **Database là Source of Truth** — Property, Seller, lịch trống, Deal, Booking, Hold 100% do Backend DB kiểm soát. AI chỉ dùng dữ liệu đã có trong hệ thống.
2. **AI-first, không AI-only** — AI hiểu intent, trích xuất tiêu chí Buyer, matching, khớp lịch, giải thích đề xuất; business rules và Human quyết định các hành động có tính cam kết. AI **không tự quyết định hoặc ghi đè business rules**.
3. **Owner Verification** — Seller phải được xác thực và Property phải được Operator duyệt trước khi xuất hiện trong matching. Seller chưa xác thực → **không cho booking** (AC-04).
   - Seller được xác thực **tự động** khi xác thực sổ đỏ thành công (họ tên + mã sổ khớp dữ liệu Chủ đầu tư, tài khoản **đăng nhập bằng đúng SĐT chủ sở hữu trên sổ**, rồi OTP tới SĐT đó). Biết tên + mã sổ (kể cả nhận được mã OTP từ chủ nhà) không đủ: SĐT đăng nhập khác SĐT trên sổ → `NOT_OWNER_PHONE`, đi luồng hỗ trợ (bán thay có ủy quyền…). Nhập sai tên/mã sổ bị giới hạn `OWNERSHIP_CLAIM_FAILURES_PER_HOUR` (5) lần/giờ/tài khoản; một căn chỉ có một sổ còn hiệu lực (`UNIT_CLAIMED`). Operator **không duyệt người bán**, chỉ **duyệt tin đăng**.
   - Giao diện gọi là "sổ đỏ / sổ hồng" (căn hộ thường là sổ hồng); trong code vẫn là `red_book`.
   - Thông tin gốc của căn (tòa, mã căn, loại hình, diện tích, phòng ngủ, phòng tắm, tầng, hướng) lấy từ dữ liệu sổ đỏ của Chủ đầu tư; seller không sửa được, chỉ nhập giá, view, nội thất, mô tả, ảnh.
   - Ngoại lệ (không nhận OTP, sổ bị khóa, sai lệch dữ liệu, bán thay có ủy quyền, đồng sở hữu, thừa kế, chưa có sổ, sổ bị người khác nhận): seller gửi yêu cầu hỗ trợ → escalation `OWNERSHIP_SUPPORT` → Operator mở khóa sổ / cập nhật SĐT / xác thực thủ công / thu hồi xác thực. Mọi thao tác ghi `audit_logs` và báo seller.
4. **Owner Approval (HITL)** — Booking bắt đầu ở `REQUESTED` và gửi thẳng tới Seller. Chỉ chuyển sang `CONFIRMED` khi chính **Seller/Owner** xác nhận (AC-05). Agent không được tự confirm. Operator **không** duyệt từng booking; Operator chỉ can thiệp khi có exception (§3.9).
5. **Deal ID** — Mỗi quan hệ `Buyer + Seller + Property` có đúng một Deal (mã dạng `VH-2026-00128`). Deal phải được tạo khi Buyer yêu cầu xem (AC-02, AC-09). Deal đã đóng → reject mọi action.
6. **Privacy by Design (Progressive Disclosure)** — Seller không tự động nhận SĐT/email Buyer khi Buyer chưa xác nhận tiếp tục giao dịch (AC-03):
   - Level 1 — Matching: Seller thấy Buyer ID, **họ tên** người mua (quyết định sản phẩm, dùng cả trong thông báo), budget range, property preference, viewing preference; **SĐT/email luôn ẩn**.
   - Level 2 — Viewing: hai bên xác nhận lịch; SĐT/email vẫn ẩn.
   - Level 3 — Continue Transaction: chia sẻ thông tin cần thiết theo policy khi cả hai muốn tiếp tục.
   - Level 4 — Transaction: Chủ đầu tư hỗ trợ quy trình.
   - AI không tự thu thập PII từ bên ngoài, không tự chia sẻ PII, không truy cập PII ngoài quyền.
7. **Atomic Viewing Hold** — Hold = **tạm khóa căn để phục vụ buổi xem, KHÔNG phải giữ căn để mua**. Chỉ hold sau Owner confirmation; gắn với Deal + Buyer + time window; không hold ngoài viewing window; hết window → release. Atomic (`SELECT ... FOR UPDATE` + exclusion constraint) — không quá một hold cho cùng Property/time, và **một chủ căn không có 2 lịch xem đã xác nhận trùng giờ, kể cả ở 2 căn khác nhau** (AC-08). Yêu cầu chưa xác nhận (`REQUESTED`) được phép trùng giờ — chủ căn chọn tiếp ai; khi chủ xác nhận một lịch, các yêu cầu khác của chủ đó bị trùng giờ tự đóng và AI báo người mua kèm giờ khác.
8. **Never Hallucinate Tool Success / Property** — Không coi Tool call là đã thành công; chỉ thông báo sau khi Backend commit. DB không có căn phù hợp → AI không được tự tạo căn (AC-01).
9. **Fail Safely & Human Escalation** — AI không chắc chắn → hỏi lại hoặc chuyển Human. Human can thiệp khi: Seller không phản hồi, không có slot chung, lịch conflict, Seller đổi lịch, Property đổi trạng thái, nhiều Buyer cùng yêu cầu một Property, lỗi hệ thống (API/DB/LLM). Fallback: dừng action không an toàn → giữ context → tạo escalation → Human xử lý → Buyer nhận trạng thái. Mỗi ca trong hàng chờ hiện cho Operator bằng lời dễ đọc (`GET /operator/escalations/{id}/context`): tên + SĐT người mua / chủ căn, căn, lịch xem, và với ca do AI chuyển là đoạn chat gần nhất của khách với Trợ lý (chỉ tin nhắn, không có chi tiết kỹ thuật — Operator không phải người làm IT; trace AI là việc của dev, xem §7 `ai_turns`).
10. **Strict Non-Goals (MUST NOT HAVE)**:
    - Không thanh toán / đặt cọc / mortgage.
    - Không ký hợp đồng điện tử.
    - Không AI định giá / dự đoán giá.
    - Không để AI đàm phán giá, thay đổi giá, xác nhận giao dịch hay xác nhận pháp lý (AC-10).
    - Không gọi điện tự động / Voice AI.
    - Không BĐS ngoài Vinhomes.
    - Không CRM / Sale trung gian bên ngoài.

---

## 4. AI Agent Boundary & Controlled Tools

### Read tools
1. `search_properties(criteria)` — Hard filter SQL + soft preference scoring → Top-N (chỉ căn `AVAILABLE` của Seller đã xác thực).
2. `get_property_detail(property_id)` — Chi tiết căn đã duyệt.
3. `get_seller_status(property_id)` — Seller đã xác thực chưa (không trả PII).
4. `check_property_availability(property_id, window)` — Khung giờ căn còn trống (không bị booking/hold).
5. `check_seller_availability(property_id, window)` — Lịch trống Seller; dùng để tính intersection với lịch Buyer.
6. `get_deal_status(deal_id)` — Trạng thái Deal và booking liên quan.

### Action tools
7. `create_viewing_request(property_id, buyer_windows | slot)` — Tạo/tái sử dụng Deal + tạo Booking `REQUESTED`.
8. `confirm_viewing(booking_id)` — **Chỉ thực thi khi actor là Seller của căn**; Agent không được tự gọi thay Owner.
9. `cancel_viewing(booking_id)` — Buyer hủy lịch.
10. `reschedule_viewing(booking_id, new_slot)` — Yêu cầu đổi lịch (cần Owner xác nhận lại).
11. `create_property_hold(booking_id)` — Chỉ sau Owner confirmation (thường do Service tự tạo trong cùng transaction confirm).
12. `release_property_hold(hold_id)` — Nhả hold (hết window / hủy).
13. `open_chat(deal_id)` — Chỉ khi đủ điều kiện gating (post-MVP).
14. `send_notification(user_id, event)` — Qua Notification Service.
15. `create_human_escalation(type, context)` — Đưa vào Exception Queue của Operator.

> Danh sách trên là năng lực theo spec. Agent thực tế (`src/agents/tools.py`) có 12 tool: `list_projects`, `search_properties`, `get_property_detail`, `get_seller_status`, `check_seller_availability`, `check_property_availability`, `get_deal_status`, `get_booking_status`, `create_viewing_request`, `cancel_viewing`, `reschedule_viewing`, `create_human_escalation`. Các mục 8, 11–14 **không** cấp cho agent: xác nhận lịch là thao tác của Owner trên web, hold do Service tạo/nhả trong transaction và job nền, thông báo do Service gửi, chat Buyer ↔ Seller là post-MVP.

### Tool Policy
- LLM không truy cập DB trực tiếp: `LLM → Agent Tool Layer → Authorization → Business Rules → Service Layer → Database`.
- Tool kiểm tra authorization và business rule; write action phải validate state hiện tại.
- AI không bypass Owner approval, không truy cập PII ngoài quyền.

### AI ĐƯỢC PHÉP
- Bóc tách ngôn ngữ tự nhiên: ngân sách, số PN, diện tích, dự án/phân khu, hướng, view, tầng.
- Hỏi lại khi thiếu thông tin quan trọng; cập nhật tiêu chí và re-run matching (Correction Path).
- Đề xuất Top-N kèm giải thích dựa trên dữ liệu thật.
- Tính intersection lịch Buyer/Seller, đề xuất slot (vd. 14h30 / 15h / 15h30) và slot thay thế khi conflict.
- Phát hiện Selling Intent của Owner và **hỏi** có muốn đăng ký bán không (không tự đăng bán).

### AI KHÔNG ĐƯỢC
- Bịa thông tin căn không có trong DB.
- Xác nhận booking thay Owner.
- Đàm phán giá, nhận tiền, đặt cọc, cam kết pháp lý, xác nhận giao dịch.
- Chia sẻ PII hoặc truy cập DB bỏ qua Service Layer.

---

## 5. Tool Execution Pipeline & Guardrails
```text
AI Agent Tool Call
      ↓
1. Pydantic Schema Validation (types, bounds, required fields)
      ↓
2. Authentication & Authorization (JWT; RBAC Buyer / Seller / Operator)
      ↓
3. Business Rule Validation (Property AVAILABLE, Seller VERIFIED, Deal chưa đóng, đúng state, đúng khung giờ)
      ↓
4. Time Conflict Check & Row-level Lock (PostgreSQL Tx)
      ↓
5. Execution & State Transition (Booking + Deal + Hold trong cùng transaction)
      ↓
6. Structured Response returned to Agent + Audit Log + Notification event
```
- Lỗi → rollback, trả Structured Error; Agent giải thích và đề xuất phương án thay thế, hoặc tạo escalation.

### Guardrails quanh chat (`src/agents/guardrails.py`, gắn trong `chat_service`)
Ngoài quy tắc trong system prompt, mỗi lượt chat đi qua lớp kiểm tra bằng code:
- **Đầu vào**: che SĐT/email/CCCD/số thẻ khách gõ (model và `ai_turns` không nhận PII); bỏ dòng giả mạo `[Thời điểm khách gửi tin này…]`; prompt injection / jailbreak rõ ràng → trả lời cố định, **không gọi model**, không đưa vào bộ nhớ agent.
- **Đầu ra**: che SĐT/email trong câu trả lời; thay toàn bộ câu trả lời bằng câu an toàn khi AI nói lịch "đã được xác nhận" mà không có kết quả tool `CONFIRMED`, nhắc mã căn không có trong kết quả tool/lời khách, hoặc hướng dẫn chuyển khoản/đặt cọc, đàm phán/dự đoán giá, cam kết pháp lý/giao dịch (câu phủ định "không/chưa…" không tính). Câu trả lời thay thế cũng thay trong state LangGraph.
- **Kill switch** (`src/services/assistant_control.py`): Operator bấm "Tắt AI" ở Operator Console → trang **Trợ lý AI** (`/operator/ai`; API `PUT /operator/ai-assistant`). Trạng thái lưu ở `system_settings` nên mọi instance thấy ngay; khi tắt, mọi endpoint chat trả 503 `AI_DISABLED` không gọi model, khung chat của người mua hiện "Hệ thống AI đang bảo trì, vui lòng liên hệ Tổng đài `SUPPORT_HOTLINE`…" và khóa ô nhập (`GET /chat/assistant-status`), tin nhắn follow-up dùng mẫu cố định. Đặt lịch / xác nhận lịch vẫn chạy. Bật/tắt ghi `audit_logs` (`AI_ASSISTANT_ENABLED` / `AI_ASSISTANT_DISABLED`).
- Mọi thay đổi ghi `audit_logs` (`AI_GUARDRAIL`, `extra.flags`). Chat bị giới hạn tần suất (`CHAT_MESSAGES_PER_*`, `GUEST_CHAT_MESSAGES_PER_*`; theo tài khoản / IP khách, đếm trong bộ nhớ từng instance) → 429 `RATE_LIMITED` (`details.scope = "chat"`).

### Error Handling (spec §5)
| Error | Expected behavior |
|---|---|
| Missing information | AI hỏi lại |
| No match | Đề xuất alternative (không bịa căn) |
| Seller unavailable | Đề xuất Seller/căn khác |
| No common slot | Đề xuất lịch khác hoặc escalate Human (AC-07) |
| Owner rejection | Đề xuất alternative |
| Concurrent booking | Atomic transaction, chỉ một bên thành công |
| Stale property (vừa bán) | Không booking |
| Unauthorized action / PII | Reject |
| Seller unverified | Không cho booking |
| System failure (API/DB/LLM) | Fallback Human |
| Deal conflict (Deal đã đóng) | Reject action |

---

## 6. Lifecycles (Vòng đời Nghiệp vụ)

### 6.1. Property Lifecycle
```text
(Đăng tin bán) → PENDING_REVIEW → AVAILABLE (= APPROVED) ⇄ WITHDRAWN (tạm ngừng → gửi duyệt lại)
                      │                 └──> SOLD (không hoàn tác)
                      └──> REJECTED (kèm lý do) ──(seller sửa)──> PENDING_REVIEW
```
- Không còn bản nháp: "Đăng tin bán" tạo tin ở `PENDING_REVIEW` ngay (`DRAFT` chỉ còn trong dữ liệu cũ). Seller sửa được tin khi `PENDING_REVIEW` / `REJECTED` / `WITHDRAWN`.
- `PENDING_REVIEW` không xuất hiện với Buyer; chỉ `AVAILABLE` (Seller `VERIFIED`) được matching/booking; `SOLD` không recommendation/booking.
- `VIEWING_HELD` trong spec **không lưu thành cột trạng thái** của Property — được suy ra từ `property_holds` đang `ACTIVE` trong viewing window, để căn vẫn nhận booking ở khung giờ khác và tự "release" khi hết window.
- Buyer không có trang tìm kiếm/bộ lọc: sau khi đăng nhập, Buyer vào thẳng AI Chat.

### 6.2. Booking Lifecycle (spec §4.12)
```text
REQUESTED ──(Owner confirm)──> CONFIRMED ──(xem xong)──> COMPLETED
    │                              │
    ├─> REJECTED (Owner)           ├─> CANCELLED (Buyer / Operator)
    ├─> EXPIRED (tới giờ xem mà Owner chưa trả lời)
    ├─> CANCELLED (Buyer)          └─> RESCHEDULE_REQUESTED ──(Owner confirm)──> CONFIRMED
    └─> REQUESTED (Buyer đổi giờ, Owner chưa trả lời: chuyển thẳng sang giờ mới, vẫn chờ Owner xác nhận)
```
- Owner từ chối có thể **đề xuất tối đa 3 giờ khác** (`suggested_starts`, chỉ lấy từ giờ trống của chính Owner cho căn đó): yêu cầu → `REJECTED`, Buyer nhận `VIEWING_TIMES_SUGGESTED` và bấm một giờ là tạo yêu cầu mới (cùng Deal). Từ chối với lý do bận có thể **đóng luôn khung giờ đó** (`close_time`, trừ khi còn yêu cầu khác cùng giờ).
- `REJECTED` cũng xảy ra tự động khi Owner xác nhận một người khác trùng giờ (yêu cầu bị đóng, AI báo người mua kèm giờ khác). Owner không có nút hủy lịch đã xác nhận; hủy là của Buyer, hoặc Operator khi xử lý ngoại lệ (vd. thu hồi xác thực sổ đỏ).
- Đổi giờ khi `REQUESTED` (mở rộng so với spec §4.12): chưa có hold nên Booking chuyển ngay sang giờ mới, giữ nguyên Deal; Seller được báo (`VIEWING_REQUEST_UPDATED`) và vẫn phải xác nhận. Đổi giờ khi `CONFIRMED` giữ giờ cũ + hold cho tới khi Owner đồng ý giờ mới.
- Giờ xem được đề xuất / đặt sớm nhất sau `VIEWING_MIN_NOTICE_MINUTES` (mặc định 120 phút) kể từ hiện tại; AI, trang chi tiết căn và màn đặt lịch dùng chung một nguồn (`propose_viewing_times`) và đều tính từ hôm nay.
- Tới giờ xem mà Owner vẫn chưa trả lời → yêu cầu tự **`EXPIRED`** (job nền; Buyer được báo trong chat kèm gợi ý tìm giờ khác; ca `SELLER_NO_RESPONSE` tự đóng). Giờ mới Buyer xin (`RESCHEDULE_REQUESTED`) đã qua mà chưa được đồng ý → lịch giữ giờ cũ. Giao diện chỉ hiện giờ bắt đầu buổi xem (vd. "14:00"); rê chuột vào nhãn trạng thái để xem giải thích.
- Hạn Owner trả lời yêu cầu (`respond_by`) = sớm hơn giữa gửi + `SELLER_RESPONSE_HOURS` (24h) và giờ xem − `SELLER_RESPONSE_LEAD_MINUTES` (60 phút); quá hạn → escalation `SELLER_NO_RESPONSE` (chỉ cho buổi xem chưa tới giờ). Ca này tự đóng khi yêu cầu được trả lời / hủy / hết hạn (job nền cũng dọn ca còn sót); thông báo của ca đã đóng tự đánh dấu đã đọc với Operator.
- Operator: đóng ca phải ghi kết quả ≥ 10 ký tự; ca người khác đã nhận thì phải "Nhận lại ca" trước. Hủy lịch (ngoại lệ) chỉ được trước giờ xem; sau giờ xem lịch `CONFIRMED` hiện "Chờ ghi nhận kết quả". Lý do chủ căn từ chối ≥ 10 ký tự. Đăng nhập chỉ nhận số di động VN (10 số, đầu 03/05/07/08/09).
- `OWNER_CONFIRMED` trong spec = `CONFIRMED`; `VIEWING_HELD` = Booking `CONFIRMED` có `property_hold` `ACTIVE`.
- Owner confirm → tạo Viewing Hold (cùng transaction) → nhắc lịch T-24h & T-2h → xem nhà → `COMPLETED`.
- **Sau giờ xem** (`viewing_outcome_service`): Owner ghi nhận "Đã xem xong" (`COMPLETED`) hoặc "Khách không đến" (`NO_SHOW`); quên thì được nhắc một lần; sau `VIEWING_OUTCOME_HOURS` (48h) không ai ghi nhận → `UNREPORTED` (không tính lỗi cho ai). Buyer sau buổi xem đã diễn ra cho biết Quan tâm (Deal → `INTERESTED`, báo Owner) / Chưa phù hợp (Deal → `CLOSED`, AI gợi ý căn khác). Buyer không đồng ý ("Tôi có đến" / "Chủ căn không có mặt") → escalation `VIEWING_DISPUTE`; Operator gọi hai bên rồi ghi kết quả (`COMPLETED` / `NO_SHOW` / `OWNER_ABSENT`). Không phạt tự động; số lần vắng mặt chỉ hiển thị để Operator tham khảo.
- Hệ thống phải ngăn double-booking: exclusion constraint trên `owner_id` + khoảng thời gian cho Booking `CONFIRMED`/`RESCHEDULE_REQUESTED` (chủ căn không thể ở 2 nơi cùng lúc), và trên `property_id` cho hold `ACTIVE`.

### 6.3. Deal Lifecycle (spec §4.9)
```text
MATCHED → VIEWING_REQUESTED → VIEWING_CONFIRMED → VIEWED → INTERESTED → NEGOTIATING → TRANSACTION_SUPPORT → COMPLETED / CLOSED
```
- Deal state được Service cập nhật cùng transaction với Booking; Booking là nguồn chi tiết của buổi xem.
- **MVP kết thúc tại buổi xem** (Core Demo Flow). `INTERESTED` trở đi, Purchase Request, Buyer ↔ Seller Chat và transaction screens là **post-MVP** (spec §4.15). Deal attribution window và phí là TBD.

---

## 7. Data Model (spec §4.16, mở rộng)
Bản đầy đủ gồm 26 bảng:
- **Identity & Auth:** `users`, `otp_codes`, `buyer_profiles`, `seller_profiles`
- **Ownership:** `property_ownership_verifications` (dữ liệu sổ đỏ của Chủ đầu tư + thông tin căn gốc; mỗi sổ gắn tối đa một tin qua `properties.verification_id`)
- **Inventory:** `projects`, `buildings`, `properties`, `property_media`, `media_files` (ảnh / giấy tờ tải lên)
- **Scheduling:** `availability_slots` (lịch trống Seller), `buyer_availability`
- **Deal & Viewing:** `deals`, `bookings`, `property_holds`
- **Post-viewing (post-MVP):** `purchase_requests`, `chats`, `messages`
- **AI:** `ai_conversations`, `ai_messages`, `recommendations`, `ai_turns` (trace cho dev: mỗi lượt chat — cả khách chưa đăng nhập và lượt lỗi — kèm từng bước gọi model/công cụ, thời gian, token; xem bằng `python scripts/ai_traces.py`; tự xóa sau `AI_TRACE_RETENTION_DAYS`. Chỉ dành cho dev, không hiển thị cho Buyer/Seller/Operator)
- **Operations:** `escalations`, `notifications`, `audit_logs`, `system_settings` (công tắc vận hành dùng chung mọi instance, vd. kill switch Trợ lý AI)

Quan hệ chính: Seller 1─N Property · Buyer 1─N Deal · Property 1─N Deal · Deal 1─N Booking · Booking 1─0..1 PropertyHold · Deal 1─0..1 PurchaseRequest · Deal 1─0..1 Chat.

---

## 8. Coding Conventions
- **Python / Backend:**
  - Khai báo kiểu dữ liệu nghiêm ngặt (`type hints`).
  - Pydantic v2 cho toàn bộ Request/Response Schemas.
  - Tuân thủ linter `ruff`.
  - Mọi thao tác ghi dữ liệu nhạy cảm (Deal, Booking, Hold) phải nằm trong Database Transaction rõ ràng.
  - Mọi hành động quan trọng phải ghi `audit_logs`.
- **Frontend / React + Vite:**
  - Strict TypeScript, đồng bộ kiểu dữ liệu với Backend Pydantic Schemas.
  - Xử lý streaming SSE mượt mà cho AI Chat.
  - Responsive Web cho cả Mobile và Desktop.
- **Testing:** Golden set AI ≥20 scenarios (extraction, constraints, ranking, explanation, tool selection/arguments, permission, privacy, scheduling, deal state, hallucination, exception, escalation) + concurrency tests cho AC-08.
