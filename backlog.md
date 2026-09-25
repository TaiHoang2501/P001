# Backlog: BookingBot AI Agent

Danh sách các công việc được chia nhỏ dựa trên Roadmap và **Architecture Patch — AI Agent Orchestrator v2** của `.specify/spec.md`.
- **Deadline prototype:** 25/10/2026.
- **Scope rule:** Nếu trễ tiến độ, cắt Phase 4/5 (RAG, analytics UI) trước; **không bao giờ cắt Phase 2** (availability, soft-hold, locking, state machine, HITL).

---

## Phase 1: Foundation (Khởi tạo dự án & Hạ tầng)

- [ ] **Task 1.1: Repo & Database Schema**
  - Khởi tạo repo Git + branching workflow.
  - Khởi tạo dự án Next.js + TypeScript (frontend) và FastAPI + Python 3.11+ (backend).
  - Cấu hình `docker-compose.yml` (PostgreSQL 15+ có pgvector, Redis optional).
  - Viết DDL cho toàn bộ bảng theo Data Model `spec.md`:
    - `users`, `roles`, `customers`, `sales`
    - `projects`, `properties`, `property_images`
    - `viewing_resources`, `project_capacities`, `vehicles`
    - `availability_slots`, `bookings`, `booking_events`, `soft_holds`
    - `notifications`, `conversations`, `messages`
    - `tool_calls`, `ai_runs`
    - `knowledge_documents`, `knowledge_chunks`
    - `audit_logs`, `system_configs`

- [ ] **Task 1.2: Seed Data & Authentication**
  - Viết script seed data: 30–100 properties, sales, projects, capacities, vehicles mock, availability slots, knowledge documents.
  - Thiết lập Authentication:
    - Customer: không bắt buộc login; xác thực booking bằng booking code/OTP.
    - Sale/Operator: Login + password hashing + RBAC.
  - Thiết lập RBAC (Role-Based Access Control) cho FastAPI.
  - Data isolation theo role (Sale chỉ xem dữ liệu trong phạm vi được phân quyền).

- [ ] **Task 1.3: UI Framework**
  - Thiết lập thư viện UI/Component cho Next.js (Tailwind, shadcn/ui hoặc tương đương).
  - Tạo layout chính cho Web Chat (hỗ trợ streaming) và Staff Dashboard.

---

## Phase 2: Core Transaction (Nghiệp vụ cốt lõi Backend) — **HIGHEST PRIORITY (Source of Truth)**

- [ ] **Task 2.1: Property Search & Detail Services**
  - Service/API `search_property(criteria)`: lọc BĐS theo dự án, loại căn, khoảng giá, diện tích, tầng, hướng/ban công, nội thất, tình trạng, mục đích mua.
  - Service/API `get_property_detail(property_id)`: trả Property Card đầy đủ (mã căn, dự án, loại, diện tích, giá, tầng, hướng, nội thất, trạng thái, hình ảnh/mô tả).
  - **Rule:** LLM chỉ trích xuất constraints; Backend/SQL thực hiện filtering. Tuyệt đối không dùng LLM để ranking hay phát minh facts về BĐS.

- [ ] **Task 2.2: Availability Engine**
  - Kiểm tra đồng thời 4 resource: Property/Showroom + Sale + Project Capacity + Vehicle (mock adapter).
  - Vehicle availability qua **mock/simulation adapter** (adapter pattern để sau này thay bằng integration thật).
  - Phát hiện conflict khi bất kỳ resource nào không khả dụng.

- [ ] **Task 2.3: Booking State Machine**
  - Implement state machine chặt chẽ:
    ```
    Draft → Soft-held → Pending Sale Approval → Confirmed → Completed / No-show / Cancelled
    Soft-held --expiry--> Expired
    Pending Sale Approval → Rejected
    Confirmed --reschedule--> Rescheduled (lưu dạng booking event/version)
    Confirmed --cancel--> Cancelled
    ```
  - Mọi state transition phải ghi nhận vào `booking_events` (audit trail).

- [ ] **Task 2.4: Soft-hold & Anti-Double-Booking**
  - Soft-hold service: tạo hold với thời gian hết hạn **configurable trên Staff Dashboard**.
  - Khi hết hạn: tự động giải phóng Sale slot + Unit slot + Project capacity + Vehicle reservation.
  - Anti-double-booking sequence:
    ```
    check availability → BEGIN TRANSACTION → lock resource rows (SELECT ... FOR UPDATE) → re-check availability → create hold/booking → COMMIT → release locks
    ```
  - Sử dụng PostgreSQL transaction/row-level locking. Không bao giờ dựa vào prompt/LLM để chống double-booking.

- [ ] **Task 2.5: Sale Approval & HITL Workflow**
  - API `request_sale_approval(booking_id)`.
  - Sale approve/reject soft-hold từ Staff Dashboard.
  - HITL kích hoạt khi: VIP, slot ngoài giờ, căn đặc biệt, không tìm được slot tự động, availability conflict, special request, thay đổi VIP status.
  - Backend authorization + business-rule validation trước khi commit mọi mutation quan trọng.

- [ ] **Task 2.6: Reschedule & Cancel**
  - `reschedule_booking(booking_id, new_slot)`:
    - Kiểm tra availability mới **trước** khi release slot cũ.
    - Soft-hold slot mới trước khi commit.
    - Rollback khi bước mới thất bại.
    - Chỉ release slot cũ sau khi slot mới đủ điều kiện.
  - `cancel_booking(booking_id)`: xác thực quyền → hủy booking → giải phóng resource → gửi notification.

- [ ] **Task 2.7: Audit Log & Tool Execution Security Pipeline**
  - Thiết lập pipeline bảo mật cho mọi Tool Call:
    ```
    Agent Request → Tool Schema Validation → Auth/RBAC Check → Business Rule & Availability Check → Row Lock & Transaction → Execute Mutation → Structured Response → Audit Log
    ```
  - Ghi nhận `ai_runs`, `tool_calls`, `audit_logs` cho mọi hành động.

---

## Phase 3: AI Agent Orchestrator (LangGraph & LLM) — **Patch v2 Aligned**

- [ ] **Task 3.1: Model-Agnostic LLM Adapter & Agent State**
  - Model-agnostic adapter (OpenAI gpt-4o-mini default, dễ dàng đổi sang Claude/Gemini không ảnh hưởng logic).
  - Định nghĩa Agent State (`TypedDict` trong LangGraph): chat history, extracted criteria, missing fields, tool results, current workflow step.

- [ ] **Task 3.2: Tool Contracts (8 Standard Functions from Patch v2)**
  - Đóng gói các services Phase 2 thành standard tools:
    1. `search_property(criteria)`
    2. `get_property_detail(property_id)`
    3. `check_availability(property_id, datetime, guest_count, vehicle_requirement)`
    4. `create_soft_hold(property_id, slot_id, customer_info)`
    5. `request_sale_approval(booking_id, reason)`
    6. `reschedule_booking(booking_id, new_slot)`
    7. `cancel_booking(booking_id, reason)`
    8. `send_notification(recipient, channel, template_id, params)`
    - Bổ sung tool tri thức & escalate: `search_knowledge(query)`, `escalate_to_human(reason)`.

- [ ] **Task 3.3: Agentic Loop Implementation**
  - Xây dựng vòng lặp agentic theo chuẩn Patch v2:
    `Customer Request → Understand Intent → Update State → Determine Missing Fields → Select Tool → Backend Validates & Executes → Tool Result → Agent Observes Result → Determine Next Action / Response`.
  - Ngăn chặn suy luận Tool chỉ từ từ khóa đơn lẻ; bắt buộc kết hợp context & state.

- [ ] **Task 3.4: Confirmation Rule Guardrail (Anti-Hallucination)**
  - **Quy tắc bắt buộc:** Agent **không được tự ý commit `Confirmed`**.
  - Agent chỉ thông báo booking thành công khi Backend trả `success=true` và transaction đã commit (`booking.status = Confirmed`).
  - Luồng: Request confirmation → Backend validates → HITL check → Sale approval nếu cần → Backend commit → Agent quan sát kết quả và thông báo.

- [ ] **Task 3.5: Failure Modes & Exception Handling (F1–F16)**
  - F13: Agent chọn sai function → Tool schema & Auth chặn lại, trả lỗi có cấu trúc, Agent điều hướng lại.
  - F14: Tool Call thiếu tham số → Backend từ chối, Agent xác định field thiếu và hỏi lại khách.
  - F15: Agent hiểu sai ngữ cảnh (vd: "đổi sang 16h" nhưng chưa rõ booking nào) → Agent hỏi rõ booking context trước khi gọi tool.
  - F16: Agent tưởng Tool thành công khi Backend thất bại → Tool trả trạng thái rõ ràng, Agent xử lý fail-safe.

- [ ] **Task 3.6: HITL Routing**
  - Edge riêng cho HITL trong đồ thị LangGraph.
  - Route các case: VIP, ngoài giờ, căn đặc biệt, conflict, special request vào queue của Staff.

---

## Phase 4: RAG & Notifications

- [ ] **Task 4.1: Knowledge Base Setup**
  - Knowledge sources: project info, tiện ích, chính sách xem nhà, quy định đưa đón, FAQ BĐS.
  - Pipeline: Documents → Cleaning → Metadata → Chunking → Embedding → pgvector.

- [ ] **Task 4.2: RAG Integration & Boundaries**
  - Tool `search_knowledge(query)` trả lời FAQ.
  - **RAG Guardrail:** RAG chỉ hỗ trợ tri thức tĩnh/chính sách, tuyệt đối không quyết định giá, live availability, booking state hay phân bổ Sale.
  - Không tìm thấy tài liệu → thông báo rõ chưa có thông tin, không bịa đặt.

- [ ] **Task 4.3: Notification Engine**
  - Provider abstraction: `WebNotificationProvider`, `EmailProvider` (thực tế), `SMSProvider` (mock), `ZaloProvider` (mock).
  - Triggers: booking confirmed/rejected/cancelled/rescheduled, soft-hold sắp hết hạn, nhắc lịch 24h, cập nhật HITL.

---

## Phase 5: Dashboard & Analytics (Staff UI)

- [ ] **Task 5.1: Dashboard Overview**
  - Tổng quan booking trong ngày, pending approvals, active soft-holds, HITL queue.
  - Core KPI cards: processing time, booking success, double-booking rate, HITL rate.

- [ ] **Task 5.2: Booking Management & HITL UI**
  - Danh sách booking, bộ lọc, xem chi tiết, approve/reject/reschedule/cancel.
  - HITL Queue: lý do escalate, thông tin khách, căn hộ, slot yêu cầu, nút thao tác duyệt/từ chối.

- [ ] **Task 5.3: Resource Calendar & CRUD**
  - Calendar view: Sale availability, căn hộ/showroom, công suất dự án, xe đưa đón.
  - Quản lý dữ liệu CRUD cơ bản (Properties, Projects, Sales, Vehicles).
  - Cấu hình Soft-hold duration trực tiếp trên giao diện Dashboard.

- [ ] **Task 5.4: Analytics & Evaluation**
  - Thống kê tỷ lệ chuyển đổi, thời gian xử lý của Operator (SLA ≤ 5 phút), double-booking rate (= 0), AI self-resolution rate, tool latency.

---

## Phase 6: QA, Tests & Demo

- [ ] **Task 6.1: Functional Tests**
  - Test search property, property detail, booking, approval, reschedule, cancel, reminder, CRUD, RBAC.

- [ ] **Task 6.2: AI & Orchestrator Tests**
  - **Intent → Tool Selection Test Set:** Đánh giá độ chính xác chọn tool theo 8 function chuẩn.
  - **Tool Safety Matrix:** Kiểm thử sai tool, thiếu argument, sai kiểu, booking không tồn tại, booking không thuộc user, slot bị giữ, soft-hold hết hạn, sale không có quyền, concurrent booking.
  - **Anti-Hallucination Test:** Xác minh Agent không bao giờ thông báo đặt lịch thành công khi Backend chưa commit `success=true`.

- [ ] **Task 6.3: Reliability & Concurrency Tests**
  - Test concurrent booking (chống double-booking với 2 khách cùng tranh 1 slot).
  - Test hết hạn soft-hold tự động giải phóng tài nguyên.
  - Test rollback khi reschedule thất bại.
  - Test timeout API/LLM/tool.

- [ ] **Task 6.4: Security Tests**
  - Authentication, password hashing, RBAC, phân quyền Sale data isolation, audit logging.

- [ ] **Task 6.5: End-to-End Demo Scenarios**
  - **Scenario A:** Conversational search → booking (happy path).
  - **Scenario B:** Concurrent booking — 2 khách tranh 1 slot → chỉ 1 thành công, 1 nhận conflict + gợi ý slot khác (**primary demo**).
  - **Scenario C:** HITL exception — VIP/ngoài giờ → HITL queue → Sale duyệt trên Dashboard.
  - **Scenario D:** Reschedule — đổi slot an toàn (check mới trước, release cũ sau).
  - **Scenario E:** RAG boundary — câu hỏi FAQ trả lời từ KB; câu hỏi availability bắt buộc gọi tool.

- [ ] **Task 6.6: Deployment & Final Deliverables**
  - Local: Docker Compose hoàn chỉnh.
  - Online: Frontend trên Vercel, Backend trên Cloud/Container, Database PostgreSQL trên Cloud.
  - GitHub CI kiểm tra lint/test.
  - Slide thuyết trình, báo cáo kỹ thuật và video demo.

---

## Updated Definition of Done — AI Agent (From spec.md v2)

Tính năng AI Agent được coi là hoàn thành khi đáp ứng đủ 12 tiêu chí:
1. - [ ] Agent nhận diện đúng intent trong toàn bộ các test cases MVP.
2. - [ ] Agent chọn đúng Function/Tool với tỷ lệ mục tiêu do team xác định qua test set.
3. - [ ] Tool arguments hợp lệ và tuân thủ chặt chẽ Pydantic schema.
4. - [ ] Backend validate toàn bộ Tool Call (không để Agent gọi thẳng DB).
5. - [ ] Agent xử lý mượt mà multi-turn conversation (giữ context qua nhiều lượt chat).
6. - [ ] Agent xử lý missing information bằng cách hỏi lại khách thay vì tự suy đoán.
7. - [ ] Agent xử lý có cấu trúc các lỗi trả về từ Tool (Tool Error).
8. - [ ] Agent tuyệt đối không hallucinate báo thành công khi transaction Backend thất bại.
9. - [ ] HITL được kích hoạt chính xác theo các điều kiện định trước (VIP, ngoài giờ, conflict...).
10. - [ ] Booking state không bị Agent tự ý thay đổi ngoài quyền hạn.
11. - [ ] Concurrent booking không bao giờ tạo ra double-booking (bảo vệ ở tầng DB transaction).
12. - [ ] Audit log ghi nhận đầy đủ chuỗi: `Agent action → Tool Call → Backend result → Final state`.
