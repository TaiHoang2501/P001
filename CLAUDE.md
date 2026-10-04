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
- **Media Storage:** Amazon S3 (ảnh/video căn, giấy tờ xác thực Owner).
- **Model Layer:** OpenAI API (`gpt-4o-mini` mặc định, `gpt-4o` khi cần); spec cho phép Gemini/OpenAI.
- **Auth:** JWT + OTP.
- **Realtime Chat:** WebSocket qua FastAPI (Buyer ↔ Seller, post-MVP — xem §6.3).
- **Notification:** SMS/Zalo/In-app (provider TBD).
- **Vector DB / RAG:** **Không dùng trong MVP** — recommendation = SQL hard filter + soft scoring.
- **Deployment / Observability:** Docker; Logs + Metrics + Audit.

---

## 3. Core Principles & Boundaries
1. **Database là Source of Truth** — Property, Seller, lịch trống, Deal, Booking, Hold 100% do Backend DB kiểm soát. AI chỉ dùng dữ liệu đã có trong hệ thống.
2. **AI-first, không AI-only** — AI hiểu intent, trích xuất tiêu chí Buyer, matching, khớp lịch, giải thích đề xuất; business rules và Human quyết định các hành động có tính cam kết. AI **không tự quyết định hoặc ghi đè business rules**.
3. **Owner Verification** — Seller phải được xác thực và Property phải được Operator duyệt trước khi xuất hiện trong matching. Seller chưa xác thực → **không cho booking** (AC-04).
4. **Owner Approval (HITL)** — Booking bắt đầu ở `REQUESTED` và gửi thẳng tới Seller. Chỉ chuyển sang `CONFIRMED` khi chính **Seller/Owner** xác nhận (AC-05). Agent không được tự confirm. Operator **không** duyệt từng booking; Operator chỉ can thiệp khi có exception (§3.9).
5. **Deal ID** — Mỗi quan hệ `Buyer + Seller + Property` có đúng một Deal (mã dạng `VH-2026-00128`). Deal phải được tạo khi Buyer yêu cầu xem (AC-02, AC-09). Deal đã đóng → reject mọi action.
6. **Privacy by Design (Progressive Disclosure)** — Seller không tự động nhận SĐT/email Buyer khi Buyer chưa xác nhận tiếp tục giao dịch (AC-03):
   - Level 1 — Anonymous Matching: Seller chỉ thấy Buyer ID, budget range, property preference, viewing preference.
   - Level 2 — Viewing: hai bên xác nhận lịch.
   - Level 3 — Continue Transaction: chia sẻ thông tin cần thiết theo policy khi cả hai muốn tiếp tục.
   - Level 4 — Transaction: Chủ đầu tư hỗ trợ quy trình.
   - AI không tự thu thập PII từ bên ngoài, không tự chia sẻ PII, không truy cập PII ngoài quyền.
7. **Atomic Viewing Hold** — Hold = **tạm khóa căn để phục vụ buổi xem, KHÔNG phải giữ căn để mua**. Chỉ hold sau Owner confirmation; gắn với Deal + Buyer + time window; không hold ngoài viewing window; hết window → release. Atomic (`SELECT ... FOR UPDATE` + exclusion constraint) — không quá một booking/hold hợp lệ cho cùng Property/time (AC-08).
8. **Never Hallucinate Tool Success / Property** — Không coi Tool call là đã thành công; chỉ thông báo sau khi Backend commit. DB không có căn phù hợp → AI không được tự tạo căn (AC-01).
9. **Fail Safely & Human Escalation** — AI không chắc chắn → hỏi lại hoặc chuyển Human. Human can thiệp khi: Seller không phản hồi, không có slot chung, lịch conflict, Seller đổi lịch, Property đổi trạng thái, nhiều Buyer cùng yêu cầu một Property, lỗi hệ thống (API/DB/LLM). Fallback: dừng action không an toàn → giữ context → tạo escalation → Human xử lý → Buyer nhận trạng thái.
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
DRAFT → PENDING_REVIEW → AVAILABLE (= APPROVED) → SOLD
               └──> REJECTED
```
- `PENDING_REVIEW` không xuất hiện với Buyer; chỉ `AVAILABLE` (Seller `VERIFIED`) được matching/booking; `SOLD` không recommendation/booking.
- `VIEWING_HELD` trong spec **không lưu thành cột trạng thái** của Property — được suy ra từ `property_holds` đang `ACTIVE` trong viewing window, để căn vẫn nhận booking ở khung giờ khác và tự "release" khi hết window.
- Buyer không có trang tìm kiếm/bộ lọc: sau khi đăng nhập, Buyer vào thẳng AI Chat.

### 6.2. Booking Lifecycle (spec §4.12)
```text
REQUESTED ──(Owner confirm)──> CONFIRMED ──(xem xong)──> COMPLETED
    │                              │
    ├─> REJECTED (Owner)           ├─> CANCELLED (Buyer/Owner)
    ├─> CANCELLED (Buyer)          └─> RESCHEDULE_REQUESTED ──(Owner confirm)──> CONFIRMED
    └─> REQUESTED (Buyer đổi giờ, Owner chưa trả lời: chuyển thẳng sang giờ mới, vẫn chờ Owner xác nhận)
```
- Đổi giờ khi `REQUESTED` (mở rộng so với spec §4.12): chưa có hold nên Booking chuyển ngay sang giờ mới, giữ nguyên Deal; Seller được báo (`VIEWING_REQUEST_UPDATED`) và vẫn phải xác nhận. Đổi giờ khi `CONFIRMED` giữ giờ cũ + hold cho tới khi Owner đồng ý giờ mới.
- `OWNER_CONFIRMED` trong spec = `CONFIRMED`; `VIEWING_HELD` = Booking `CONFIRMED` có `property_hold` `ACTIVE`.
- Owner confirm → tạo Viewing Hold (cùng transaction) → nhắc lịch T-24h & T-2h → xem nhà → `COMPLETED`.
- Hệ thống phải ngăn double-booking (exclusion constraint trên `property_id` + khoảng thời gian).

### 6.3. Deal Lifecycle (spec §4.9)
```text
MATCHED → VIEWING_REQUESTED → VIEWING_CONFIRMED → VIEWED → INTERESTED → NEGOTIATING → TRANSACTION_SUPPORT → COMPLETED / CLOSED
```
- Deal state được Service cập nhật cùng transaction với Booking; Booking là nguồn chi tiết của buổi xem.
- **MVP kết thúc tại buổi xem** (Core Demo Flow). `INTERESTED` trở đi, Purchase Request, Buyer ↔ Seller Chat và transaction screens là **post-MVP** (spec §4.15). Deal attribution window và phí là TBD.

---

## 7. Data Model (spec §4.16, mở rộng)
Bản đầy đủ gồm 22 bảng:
- **Identity & Auth:** `users`, `otp_codes`, `buyer_profiles`, `seller_profiles`
- **Inventory:** `projects`, `buildings`, `properties`, `property_media`
- **Scheduling:** `availability_slots` (lịch trống Seller), `buyer_availability`
- **Deal & Viewing:** `deals`, `bookings`, `property_holds`
- **Post-viewing (post-MVP):** `purchase_requests`, `chats`, `messages`
- **AI:** `ai_conversations`, `ai_messages`, `recommendations`
- **Operations:** `escalations`, `notifications`, `audit_logs`

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
