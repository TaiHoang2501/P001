# BookingBot AI Agent Guidelines

## 1. Project Overview
- **Project:** BookingBot AI Agent — Trợ lý điều phối quy trình đặt lịch xem nhà & giữ căn tự động.
- **Domain:** Bất động sản / Vinhomes.
- **Deadline prototype:** 25/10/2026.
- **Spec reference:** `.specify/spec.md` (MVP Spec v1.0 + Architecture Patch — AI Agent Orchestrator v2).
- **Product Thesis:** BookingBot là **AI Agent điều phối quy trình**. Agent hiểu nhu cầu, quản lý trạng thái hội thoại và lựa chọn Function/Tool để thực hiện từng bước của workflow; **Backend kiểm soát** business rules, availability, resource locking, authorization và trạng thái booking; **HITL** được kích hoạt khi workflow cần con người phê duyệt hoặc xử lý ngoại lệ.

---

## 2. Architecture & Tech Stack
- **Frontend:** Next.js + TypeScript (Web Chat có streaming + Staff Operations Dashboard).
- **Backend (Source of Truth):** Python 3.11+ + FastAPI (RESTful, OpenAPI docs, deterministic business services, tool schemas).
- **Agent Orchestrator:** LangGraph (Stateful workflow, tool selection, multi-turn state, human-in-the-loop, error recovery).
- **Database:** PostgreSQL 15+ (Relational core data, row-level locks, booking events, audit logs) + `pgvector` (RAG/knowledge retrieval only).
- **Model Layer:** Model-agnostic adapter. OpenAI (`gpt-4o-mini` default, `gpt-4o`). Đổi provider không làm thay đổi business logic.
- **External Adapters:** Vehicle mock adapter, Email (SendGrid/SMTP), Mock SMS/Zalo.
- **Deployment:** Frontend → Vercel, Backend → Managed Container/Cloud, DB → Managed PostgreSQL, Local → Docker Compose.

---

## 3. Core Principles
1. **Backend is Source of Truth** — Dữ liệu căn, giá, lịch trống, trạng thái booking 100% do Backend DB kiểm soát.
2. **AI Agent = Orchestrator** — AI hiểu intent, duy trì trạng thái hội thoại, chọn Function/Tool phù hợp và quyết định bước tiếp theo; AI tuyệt đối **không tự quyết định hoặc ghi đè business rules**.
3. **Agent CANNOT commit `Confirmed` directly** — Mọi trạng thái `Confirmed` phải do Backend commit sau khi đã qua validation và HITL approval (nếu cần).
4. **Never Hallucinate Tool Success** — Không coi việc LLM sinh tool call là hành động đã thành công. Phải đợi Backend trả kết quả transaction mới thông báo cho khách.
5. **Verify before Committing** — Tất cả booking phải qua kiểm tra 4 resource: Property + Sale + Capacity + Vehicle.
6. **Prevent Double-Booking at DB Level** — Dùng PostgreSQL transaction + row-level locking (`SELECT ... FOR UPDATE`), không dựa vào prompt của LLM.
7. **HITL for High-Risk & Exceptions** — Khách VIP, ngoài giờ quy định, căn đặc biệt, conflict lịch, special request bắt buộc route sang Staff Dashboard.
8. **RAG is Knowledge Support, NOT Transaction Authority** — RAG chỉ trả lời FAQ/chính sách từ pgvector; không được dùng RAG để trả lời giá, availability hay booking state.
9. **Reschedule Safety** — Luôn kiểm tra và soft-hold slot mới thành công trước khi giải phóng slot cũ; rollback nếu bước mới thất bại.
10. **Comprehensive Audit Trail** — Ghi nhận đầy đủ: `Agent Action → Tool Call → Backend Result → Final State` vào audit logs và booking events.

---

## 4. AI Agent Boundary & Standard Tool Contracts

### Standard Tools (8 Functions theo Architecture Patch v2):
1. `search_property(criteria)`: Lọc BĐS theo nhu cầu dựa trên dữ liệu Backend.
2. `get_property_detail(property_id)`: Lấy thông tin chi tiết thẻ căn hộ.
3. `check_availability(property_id, datetime, guest_count, vehicle_requirement)`: Kiểm tra đồng thời 4 resource.
4. `create_soft_hold(property_id, slot_id, customer_info)`: Tạo giữ chỗ tạm thời có thời hạn (configurable).
5. `request_sale_approval(booking_id, reason)`: Gửi yêu cầu phê duyệt vào HITL Queue.
6. `reschedule_booking(booking_id, new_slot)`: Đổi lịch an toàn (check mới trước, release cũ sau).
7. `cancel_booking(booking_id, reason)`: Hủy lịch và giải phóng tài nguyên đã cấp phát.
8. `send_notification(recipient, channel, template_id, params)`: Gửi thông báo xác nhận/nhắc lịch.
- *Tool tri thức & Escalate:* `search_knowledge(query)` (RAG FAQ) và `escalate_to_human(reason)`.

### AI ĐƯỢC PHÉP:
- Hiểu ngôn ngữ tự nhiên, trích xuất thực thể/ràng buộc.
- Hỏi lại khách hàng khi thiếu thông tin cần thiết (missing parameters).
- Duy trì ngữ cảnh hội thoại nhiều lượt (multi-turn state).
- Chọn Function/Tool dựa trên ngữ cảnh và trạng thái hiện tại.
- Đề xuất slot thay thế khi gặp conflict dựa trên dữ liệu Backend trả về.

### AI KHÔNG ĐƯỢC:
- Tự ý suy diễn/phát minh giá bán, tình trạng phòng trống, thông tin căn hộ.
- Tự quyết định thay đổi trạng thái booking thành `Confirmed`.
- Gọi tool mutation khi chưa xác định rõ entity (vd: gọi cancel/reschedule mà không biết booking nào).
- Bỏ qua Backend để truy cập trực tiếp vào Database.

---

## 5. Tool Execution Pipeline & Guardrails
Mọi Tool Call từ Agent phải đi qua pipeline 6 bước trên Backend:
```text
Agent Tool Call
      ↓
1. Tool Schema Validation (Pydantic types & bounds)
      ↓
2. Authentication & Authorization (Customer OTP / Staff RBAC)
      ↓
3. Business Rule Validation (Chính sách, điều kiện nghiệp vụ)
      ↓
4. Availability Check & Row-level Locking (PostgreSQL Tx)
      ↓
5. Execution & State Transition
      ↓
6. Structured Tool Result returned to Agent + Audit Log emitted
```
- **Fail-safe Rule:** Nếu bất kỳ bước nào thất bại, Backend rollback transaction, không thay đổi state, trả về Structured Error. Agent nhận diện lỗi và đưa ra giải pháp (hỏi lại khách, gợi ý slot khác hoặc escalate).

---

## 6. Failure Modes Bổ sung (F13–F16)
- **F13 (Agent chọn sai function):** Backend schema & Auth chặn lại → trả structured error → Agent điều hướng lại đúng workflow.
- **F14 (Tool call thiếu tham số):** Backend từ chối → Agent phân tích field còn thiếu và chủ động hỏi lại khách.
- **F15 (Agent hiểu sai ngữ cảnh / Ambiguous context):** Khách nói "Đổi sang 16h" nhưng chưa xác định booking nào → Agent bắt buộc hỏi rõ booking cần đổi trước khi gọi `reschedule_booking`.
- **F16 (Agent hallucinate tool success):** Agent chỉ được thông báo thành công sau khi Backend trả `success=true` và transaction đã commit.

---

## 7. Booking State Machine & Confirmation Rule
```text
Draft → Soft-held → Pending Sale Approval → Confirmed → Completed / No-show / Cancelled
Soft-held --expiry--> Expired
Pending Sale Approval → Rejected
Confirmed --reschedule--> Rescheduled (lưu dạng booking event)
Confirmed --cancel--> Cancelled
```

### Confirmation Rule:
```text
Customer Request Confirmation
        ↓
Backend validates business rules & availability
        ↓
HITL requirement check (VIP / Ngoài giờ / Căn đặc biệt / Conflict)
        ↓
Sale / Operator approval (nếu bắt buộc)
        ↓
Backend transaction commit (SELECT ... FOR UPDATE → COMMIT)
        ↓
booking.status = Confirmed
        ↓
Agent observes success=true → Announce confirmation to Customer
```

---

## 8. Coding Conventions
- **Python (Backend):**
  - Khai báo kiểu đầy đủ (strict type hints).
  - Sử dụng `Pydantic v2` cho toàn bộ schemas, inputs và outputs.
  - Tuân thủ linter `ruff`.
  - Mọi mutation endpoint/tool phải thực hiện trong PostgreSQL database transaction rõ ràng.
- **TypeScript (Frontend):**
  - Strict type checking, type definitions đồng bộ với Pydantic schema backend.
  - Xử lý streaming response mượt mà cho Web Chat.
  - Component hóa giao diện gọn gàng (Tailwind / shadcn/ui).

---

## 9. Definition of Done — AI Agent
Feature được coi là hoàn thành khi:
1. Agent nhận diện đúng intent trong các kịch bản test MVP.
2. Agent chọn đúng Function/Tool theo context hội thoại.
3. Tham số Tool call hợp lệ, tuân thủ schema.
4. Backend validate 100% Tool Call.
5. Xử lý multi-turn conversation và phục hồi khi thiếu thông tin.
6. Xử lý có cấu trúc các mã lỗi từ Tool (Tool Error).
7. Không hallucinate báo thành công khi transaction Backend thất bại.
8. HITL được trigger chính xác khi gặp điều kiện rủi ro/ngoại lệ.
9. Trạng thái booking được quản lý nghiêm ngặt bởi State Machine.
10. Anti-double-booking chạy qua DB transaction locking, chống race condition hoàn hảo.
11. Toàn bộ chuỗi sự kiện được ghi nhận vào Audit Log.
