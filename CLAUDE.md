# BookingBot AI Agent Guidelines

## 1. Project Overview
- **Project:** BookingBot AI Agent — Trợ lý AI-first tìm kiếm BĐS Vinhomes & điều phối lịch xem nhà.
- **Domain:** Bất động sản / Vinhomes-only.
- **Spec reference:** `.specify/spec_updated.md` (AI SPEC v1.0).
- **Actors:** `Customer` (Khách hàng), `Owner` (Chủ nhà), `Investor / Operator` (Ban quản trị / Chủ đầu tư).
- **Product Thesis:** BookingBot AI Agent là trợ lý AI-first giúp khách hàng tìm đúng căn Vinhomes từ nhu cầu tự nhiên, tự động điều phối lịch xem và giữ căn trong thời gian xem, đồng thời kết nối khách với chủ nhà sau khi booking thành công --- với **Owner approval** và **business-rule controls** tại các điểm cam kết.

---

## 2. Architecture & Tech Stack
- **Frontend:** Next.js + TypeScript (Responsive Web gồm: Customer Web Chat có streaming SSE, Owner Dashboard, Operator Moderation UI).
- **Backend (Source of Truth):** Python 3.11+ + FastAPI (RESTful, OpenAPI auto-docs, Pydantic type validation, WebSocket server).
- **Agent Orchestrator:** LangGraph (Stateful workflow, tool selection, multi-turn state, human-in-the-loop, error recovery).
- **Database:** PostgreSQL 15+ (Relational tables, Full-text Search + `pg_trgm`, ACID transactions, row-level locks).
- **Media Storage:** Amazon S3 (Lưu trữ ảnh & video căn hộ độc lập với DB).
- **Model Layer:** OpenAI API (`gpt-4o-mini` mặc định tối ưu chi phí & latency, `gpt-4o`).
- **Realtime Chat:** WebSocket tích hợp qua FastAPI (Chat 1-1 Khách ↔ Chủ nhà).
- **Vector DB / RAG:** **Không dùng trong MVP** (tối ưu hóa độ phức tạp; recommendation dùng thuật toán lọc kết hợp SQL + scoring).

---

## 3. Core Principles & Boundaries
1. **Backend is Source of Truth** — Dữ liệu căn, tình trạng duyệt, lịch trống, trạng thái booking và hold 100% do Backend DB kiểm soát.
2. **AI Agent = Orchestrator** — AI hiểu intent, trích xuất `CustomerPreference`, duy trì hội thoại đa lượt, chọn Tool và giải thích đề xuất; AI tuyệt đối **không tự quyết định hoặc ghi đè business rules**.
3. **Owner Approval is Mandatory (HITL)** — Booking bắt đầu ở trạng thái `REQUESTED`; chỉ chuyển sang `CONFIRMED` khi chính **Chủ nhà (Owner)** phê duyệt. Agent không được tự ý confirm.
4. **Atomic Viewing Hold** — "Giữ căn" trong MVP chỉ là **tạm khóa căn trong đúng khung giờ xem nhà**, không phải giữ để mua. Khóa bằng giao dịch nguyên tử (`SELECT ... FOR UPDATE`), hết giờ xem tự động nhả về `AVAILABLE`.
5. **Never Hallucinate Tool Success** — Không coi việc LLM tạo Tool call là hành động đã thành công. Phải đợi Backend commit transaction mới thông báo cho khách.
6. **Chat Gating** — Kênh chat trực tiếp 1-1 (WebSocket) giữa Khách hàng và Chủ nhà chỉ được mở sau khi buổi xem nhà thành công (`COMPLETED`) và khách có `Purchase Request`.
7. **Strict Non-Goals (MUST NOT HAVE)**:
   - Không thanh toán / đặt cọc online.
   - Không ký hợp đồng điện tử.
   - Không định giá BĐS bằng AI hay dự đoán giá.
   - Không để AI tự đàm phán giá (khách và chủ nhà tự trao đổi).
   - Không hỗ trợ BĐS ngoài Vinhomes.
   - Không tích hợp CRM / môi giới Sale trung gian ngoài luồng.

---

## 4. AI Agent Boundary & Controlled Tools

### Bộ Tools Chuẩn hóa:
1. `search_properties(criteria)`: Lọc BĐS theo hard filters SQL và tính điểm soft scoring.
2. `get_property_detail(property_id)`: Trả về thông tin chi tiết căn hộ `APPROVED`.
3. `check_availability(property_id, datetime)`: Kiểm tra lịch trống của căn hộ và chủ nhà.
4. `create_booking_request(property_id, slot, customer_info)`: Tạo yêu cầu lịch xem (`REQUESTED`).
5. `reschedule_booking(booking_id, new_slot)`: Yêu cầu đổi lịch (cần Owner duyệt lại).
6. `cancel_booking(booking_id)`: Khách hàng tự hủy lịch hẹn đã tạo.

### AI ĐƯỢC PHÉP:
- Bóc tách ngôn ngữ tự nhiên thành thực thể: Ngân sách, số PN, diện tích, phân khu, hướng, tầng.
- Hỏi lại khách hàng khi thiếu thông tin quan trọng.
- Đề xuất Top-N căn phù hợp kèm lời giải thích (Explainability).
- Gợi ý khung giờ thay thế khi gặp xung đột lịch.

### AI KHÔNG ĐƯỢC:
- Tự ý bịa đặt thông tin căn hộ không có trong DB.
- Tự quyết định xác nhận booking bỏ qua Owner.
- Tự đàm phán giá hoặc cam kết pháp lý với khách.
- Truy cập trực tiếp vào Database bỏ qua Service Layer.

---

## 5. Tool Execution Pipeline & Guardrails
```text
AI Agent Tool Call
      ↓
1. Pydantic Schema Validation (Types, bounds, required fields)
      ↓
2. Authentication & Authorization (Customer OTP / Owner JWT)
      ↓
3. Business Rule Validation (Căn APPROVED, đúng khung giờ)
      ↓
4. Time Conflict Check & Row-level Lock (PostgreSQL Tx)
      ↓
5. Execution & State Transition
      ↓
6. Structured Response returned to Agent + Audit Log emitted
```
- Nếu có lỗi: Rollback transaction an toàn, trả về Structured Error, Agent nhận diện lỗi để giải thích và đề xuất phương án thay thế.

---

## 6. Lifecycles (Vòng đời Nghiệp vụ)

### 6.1. Property Listing Lifecycle:
```text
DRAFT → PENDING_REVIEW → APPROVED / AVAILABLE → VIEWING_HELD → AVAILABLE (hoặc SOLD)
                  └──> REJECTED
```
- Chỉ căn `APPROVED / AVAILABLE` mới xuất hiện trên giao diện tìm kiếm của khách.

### 6.2. Booking Lifecycle:
```text
REQUESTED → CONFIRMED → COMPLETED
     │          │
     ├─> REJECTED  ├─> CANCELLED
     │             └─> RESCHEDULE_REQUESTED ──> CONFIRMED
```
- Owner Approve $\rightarrow$ `CONFIRMED` $\rightarrow$ Kích hoạt `Viewing Hold` $\rightarrow$ Nhắc lịch T-24h & T-2h $\rightarrow$ Xem nhà xong $\rightarrow$ `COMPLETED` $\rightarrow$ `Purchase Request` $\rightarrow$ Mở Chat 1-1.

---

## 7. Coding Conventions
- **Python / Backend:**
  - Khai báo kiểu dữ liệu nghiêm ngặt (`type hints`).
  - Pydantic v2 cho toàn bộ Request/Response Schemas.
  - Tuân thủ linter `ruff`.
  - Mọi thao tác ghi dữ liệu nhạy cảm (Booking, Hold) phải nằm trong Database Transaction rõ ràng.
- **Frontend / Next.js:**
  - Strict TypeScript, đồng bộ kiểu dữ liệu với Backend Pydantic Schemas.
  - Xử lý streaming SSE mượt mà cho Web Chat.
  - Giao diện đáp ứng (Responsive Web) cho cả Mobile và Desktop.
