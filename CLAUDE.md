# BookingBot AI Agent Guidelines

## 1. Project Overview
- **Project:** BookingBot AI Agent — Trợ lý đặt lịch xem nhà & giữ căn tự động.
- **Domain:** Bất động sản / Vinhomes.
- **Deadline prototype:** 25/10/2026.
- **Spec reference:** `.specify/spec_2.md` (MVP Spec v1.0).

## 2. Architecture & Tech Stack
- **Frontend:** Next.js + TypeScript (Web Chat + Staff Dashboard trong cùng 1 web app).
- **Backend:** Python 3.11+ + FastAPI (API-first, OpenAPI docs tự động).
- **Agent Orchestration:** LangGraph (stateful workflow, tool calling, streaming, HITL, persistence/checkpoint).
- **Database:** PostgreSQL (core transactions, audit logs) + `pgvector` (RAG/knowledge retrieval only).
- **Model Layer:** LLM-agnostic adapter. OpenAI (gpt-4o-mini/gpt-4o) là default. Swap provider không đổi business logic.
- **Cache:** Redis optional — ưu tiên PostgreSQL transaction/row-level locking cho anti-double-booking.
- **Deployment:** Frontend → Vercel, Backend → managed container/cloud, DB → managed PostgreSQL, Local → Docker Compose.

## 3. Core Principles (10 Key Product Principles)
1. **Backend is source of truth** — pricing, availability, bookings 100% từ backend DB.
2. **AI orchestrates; AI does not own business rules** — AI gọi deterministic tools; backend validate + commit.
3. **Never hallucinate transactional information** — AI MUST use tools trước khi suggest dates/times/properties.
4. **Verify before committing** — tất cả booking phải qua backend validation (transaction/lock).
5. **Use HITL for high-risk/exception cases** — VIP, out-of-hours, căn đặc biệt, conflict, special request.
6. **Prevent double-booking at transaction level, not by prompt** — PostgreSQL row-level locking.
7. **Every important action is auditable** — audit log + booking events cho mọi critical action.
8. **RAG is knowledge support, not transaction authority** — RAG không quyết định price/availability/booking state.
9. **Provider/model can be replaced without rewriting business logic.**
10. **Prototype scope optimized for 4-person team and 25/10 deadline.**

## 4. AI Agent Boundary

### AI được phép:
- Hiểu intent, thu thập thông tin còn thiếu.
- Chuyển ngôn ngữ tự nhiên → structured constraints.
- Gọi tools: `search_properties`, `get_property`, `check_availability`, `create_soft_hold`, `request_sale_approval`, `confirm_booking`, `reschedule_booking`, `cancel_booking`, `send_notification`, `get_customer_booking`, `search_knowledge`, `escalate_to_human`.
- Đề xuất slot dựa trên kết quả backend.
- Giải thích conflict và đề xuất phương án tiếp theo.

### AI KHÔNG được:
- Tự tạo giá, availability, booking state, quyền truy cập, VIP status, business rule.
- Tự quyết định resource availability.
- Tự confirm booking khi case yêu cầu human approval.
- Dùng RAG để trả lời câu hỏi availability/price/booking state (phải gọi tool).
- Hallucinate property facts hoặc live availability.

### HITL bắt buộc khi:
- Khách VIP.
- Slot ngoài giờ quy định.
- Căn đặc biệt.
- Không tìm được slot tự động.
- Availability không đồng nhất.
- Special request cần phê duyệt.
- Thay đổi VIP status.

## 5. Booking State Machine
```
Draft → Soft-held → Pending Sale Approval → Confirmed → Completed/No-show/Cancelled
Soft-held --expiry--> Expired
Pending Sale Approval → Rejected
Confirmed --reschedule--> Rescheduled (lưu dạng booking event)
Confirmed --cancel--> Cancelled
```

## 6. Anti-Double-Booking
```
check availability → BEGIN TRANSACTION → lock resource rows → re-check availability → create hold/booking → COMMIT → release locks
```
- Agent không truy cập database trực tiếp.
- Agent gọi deterministic service/tool; service kiểm tra authorization, business rules, transaction/lock rồi mới commit.

## 7. Global Guardrail: Verify → Fail safely → Escalate
1. Nhận diện yêu cầu.
2. Gọi tool/backend xác minh.
3. Thiếu dữ liệu → hỏi lại hoặc thử tool phù hợp.
4. Không xác minh được → không suy đoán.
5. Thông báo rõ cho khách.
6. Escalate Sale/Operator nếu cần.

## 8. Database Strategy
- Prototype dùng seed data (30–100 properties, mock Sales, resources). **Không dùng dữ liệu production Vinhomes.**
- Never write credentials/secrets into codebase.
- Sensitive data encryption. Không đưa sensitive data không cần thiết vào prompt/log.

## 9. Coding Conventions
- **Python (Backend):**
  - `Pydantic` cho schemas và validation.
  - Type hinting mandatory cho tất cả functions.
  - Follow `ruff` linting rules.
  - Mỗi tool phải: validate input → check authorization → check business rules → return structured output → emit audit/event log.
- **TypeScript (Frontend):**
  - Functional components + React hooks.
  - Strict typing cho API responses matching backend Pydantic models.
  - Chat phải hỗ trợ streaming.

## 10. Scope Priority Rule
Nếu trễ tiến độ:
- **CẮT TRƯỚC:** UI/analytics/RAG (Phase 4, 5).
- **KHÔNG BAO GIỜ CẮT:** Availability, soft-hold, locking, state machine, HITL (Phase 2).
