# Backlog: BookingBot AI Agent

Danh sách các công việc được chia nhỏ dựa trên Roadmap của `spec_2.md`.
**Deadline prototype:** 25/10/2026.
**Scope rule:** Nếu trễ tiến độ, cắt Phase 4/5 (RAG, analytics UI) trước; **không bao giờ cắt Phase 2** (availability, soft-hold, locking, state machine, HITL).

---

## Phase 1: Foundation (Khởi tạo dự án & Hạ tầng)

- [ ] **Task 1.1: Repo & Database Schema**
  - Khởi tạo repo Git + branching workflow.
  - Khởi tạo dự án Next.js + TypeScript (frontend) và FastAPI + Python 3.11+ (backend).
  - Cấu hình `docker-compose.yml` (PostgreSQL + pgvector, Redis optional).
  - Viết DDL cho toàn bộ bảng theo Data Model spec_2:
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
  - Tạo layout chính cho Web Chat và Staff Dashboard.
  - Hỗ trợ streaming cho chat UI.

---

## Phase 2: Core Transaction (Nghiệp vụ cốt lõi Backend) — **HIGHEST PRIORITY**

- [ ] **Task 2.1: Property Search & Detail APIs**
  - API `search_properties(criteria)`: lọc BĐS theo dự án, loại căn, khoảng giá, diện tích, tầng, hướng/ban công, nội thất, tình trạng, mục đích mua.
  - API `get_property(property_id)`: trả Property Card đầy đủ (mã căn, dự án, loại, DT, giá, tầng, hướng, nội thất, trạng thái, hình ảnh/mô tả).
  - **Rule:** LLM chỉ extract constraints; Backend/SQL thực hiện filtering. Không dùng LLM để ranking hay phát minh property facts.

- [ ] **Task 2.2: Availability Engine**
  - Kiểm tra đồng thời 4 resource: Property/Showroom + Sale + Project Capacity + Vehicle (mock adapter).
  - Vehicle availability qua **mock/simulation adapter** (adapter pattern để sau này thay bằng integration thật).
  - Phát hiện conflict khi resource không khả dụng.

- [ ] **Task 2.3: Booking State Machine**
  - Implement state machine:
    ```
    Draft → Soft-held → Pending Sale Approval → Confirmed → Completed/No-show/Cancelled
    Soft-held --expiry--> Expired
    Pending Sale Approval → Rejected
    Confirmed --reschedule--> Rescheduled (lưu dạng booking event/version)
    Confirmed --cancel--> Cancelled
    ```
  - `Rescheduled` lưu dưới dạng booking event/version; booking giữ trạng thái active cuối cùng.
  - Mọi state transition phải ghi Booking Event (audit trail).

- [ ] **Task 2.4: Soft-hold & Anti-Double-Booking**
  - Soft-hold service: tạo hold với expiry **configurable trên Staff Dashboard**.
  - Khi hết hạn: giải phóng Sale slot + Unit/showroom slot + Project capacity + Vehicle reservation.
  - Anti-double-booking sequence:
    ```
    check availability → BEGIN TRANSACTION → lock resource rows → re-check availability → create hold/booking → COMMIT → release locks
    ```
  - Sử dụng PostgreSQL transaction/row-level locking. Không dựa vào prompt/LLM để chống double-booking.

- [ ] **Task 2.5: Sale Approval & HITL Workflow**
  - API `request_sale_approval(booking_id)`.
  - Sale approve/reject soft-hold.
  - HITL kích hoạt khi: VIP, slot ngoài giờ, căn đặc biệt, không tìm được slot tự động, availability conflict, special request, thay đổi VIP status.
  - Backend authorization + business-rule validation trước khi commit mọi mutation quan trọng.

- [ ] **Task 2.6: Reschedule & Cancel**
  - `reschedule_booking(booking_id, new_slot)`:
    - Kiểm tra availability mới **trước** khi release slot cũ.
    - Soft-hold slot mới trước khi commit.
    - Rollback khi bước mới thất bại.
    - Chỉ release slot cũ sau khi slot mới đủ điều kiện.
  - `cancel_booking(booking_id)`: xác thực quyền → hủy booking → giải phóng resource → notification.

- [ ] **Task 2.7: Audit Log & Booking Events**
  - Ghi Booking Event cho mọi state change (`booking_events` table).
  - Audit log cho tất cả critical actions.
  - Mỗi tool call phải: validate input → check authorization → check business rules → return structured output → emit audit/event log.

---

## Phase 3: AI Agent (LangGraph & LLM)

- [ ] **Task 3.1: LLM Adapter & Agent State**
  - Model-agnostic adapter (Provider A/B/C swap không đổi business logic).
  - Dùng OpenAI (gpt-4o-mini/gpt-4o) làm default.
  - Định nghĩa Agent State (`TypedDict`): chat history, extracted criteria, current workflow step.

- [ ] **Task 3.2: Tool Contracts**
  - Bọc services Phase 2 thành LangChain `@tool`:
    - `search_properties(criteria)`
    - `get_property(property_id)`
    - `check_availability(property_id, datetime, guest_count, vehicle_requirement)`
    - `create_soft_hold(request)`
    - `request_sale_approval(booking_id)`
    - `confirm_booking(booking_id)`
    - `reschedule_booking(booking_id, new_slot)`
    - `cancel_booking(booking_id)`
    - `send_notification(notification)`
    - `get_customer_booking(customer_id)`
    - `search_knowledge(query)`
    - `escalate_to_human(reason)`

- [ ] **Task 3.3: Agent Orchestration & Guardrails**
  - Định nghĩa LangGraph workflow (Nodes, Edges).
  - AI được phép: hiểu intent, extract constraints, gọi tools, đề xuất slot, giải thích conflict.
  - AI **không được**: tự tạo giá, availability, booking state, quyền truy cập, VIP status, business rule.
  - Global guardrail: Verify → Fail safely → Escalate.
  - Xử lý failure: AI không hiểu → thiếu info → không tìm thấy căn → hết slot → conflict → timeout → thay đổi giữa chừng.

- [ ] **Task 3.4: HITL Routing**
  - Edge riêng cho HITL trong LangGraph.
  - Route VIP, out-of-hours, căn đặc biệt, no auto-slot, availability conflict, special request vào queue cho Sale/Operator.
  - AI không tự confirm các case yêu cầu human approval.

---

## Phase 4: RAG & Notifications

- [ ] **Task 4.1: Knowledge Base Setup**
  - Knowledge sources: project info, amenities, viewing policies/rules, transportation/pickup, booking/reschedule/cancel policies, property FAQ.
  - Schema metadata: `document_id`, `project_id`, `document_type`, `title`, `source`, `version`, `effective_from/to`, `chunk_id`, `updated_at`.
  - Pipeline: Documents → Cleaning → Metadata → Chunking → Embedding → pgvector.

- [ ] **Task 4.2: RAG Integration vào Agent**
  - Tool `search_knowledge(query)` cho Agent trả lời FAQ.
  - **RAG guardrails:** RAG không được quyết định price, live availability, booking state, Sale assignment, capacity, vehicle availability. Những dữ liệu này phải từ transactional backend.
  - Không tìm thấy tài liệu → nói rõ chưa có dữ liệu; không hallucinate.

- [ ] **Task 4.3: Notification Engine**
  - Provider abstraction: `WebNotificationProvider`, `EmailProvider`, `SMSProvider` (mock), `ZaloProvider` (mock).
  - Events trigger: booking confirmed/rejected/cancelled/rescheduled, soft-hold expiring, reminder 24h, HITL update.
  - Email tích hợp thật; SMS/Zalo mock nếu chưa có credentials.

---

## Phase 5: Dashboard & Analytics (Staff UI)

- [ ] **Task 5.1: Dashboard Overview**
  - Booking hôm nay, pending approvals, active soft-holds, HITL queue.
  - Core KPI cards: processing time, booking success, double-booking rate, HITL rate.

- [ ] **Task 5.2: Booking Management & HITL UI**
  - Booking list/filter/detail/approve/reject/reschedule/cancel/status update.
  - HITL Queue: reason, customer, property, requested slot, current status, approve/reject/escalate.

- [ ] **Task 5.3: Resource Calendar & CRUD**
  - Calendar view: Sale availability, Property/showroom, Project capacity, Vehicle mock.
  - Data Management CRUD: Properties, Projects, Sale, Vehicles, Capacity, Knowledge Base metadata.
  - Soft-hold duration configurable trên Dashboard.

- [ ] **Task 5.4: Analytics & Evaluation**
  - KPI: request→booking conversion, avg Operator processing time, request SLA ≤5 phút, double-booking rate, availability accuracy, HITL rate, AI self-resolution rate, tool/API latency, error rate.
  - Chart/bảng tối thiểu phục vụ evaluation. Không xây analytics suite lớn.

---

## Phase 6: QA & Demo

- [ ] **Task 6.1: Functional Tests**
  - Search property, property detail, booking, approval, reschedule, cancel, reminder, no-show, CRUD, RBAC.

- [ ] **Task 6.2: AI Tests**
  - Intent recognition, missing information recovery, tool selection, tool argument correctness, multi-turn correction, hallucination prevention, RAG grounding, HITL routing.

- [ ] **Task 6.3: Reliability Tests**
  - API/LLM/tool timeout, concurrent booking (anti-double-booking), soft-hold expiry, availability conflict.

- [ ] **Task 6.4: Security Tests**
  - Authentication, password hashing, RBAC, unauthorized booking access, Sale data isolation, audit logging, HTTPS, sensitive-data encryption.

- [ ] **Task 6.5: Demo Scenarios (end-to-end)**
  - **Scenario A:** Conversational search → booking (happy path).
  - **Scenario B:** Concurrent booking — 2 customers cùng slot → chỉ 1 thành công, 1 nhận conflict + đề xuất alternative (**primary demo**).
  - **Scenario C:** HITL exception — VIP/special/outside-hours → HITL queue → Sale/Operator approve/reject.
  - **Scenario D:** Reschedule — đổi slot → check resource mới → soft-hold → commit → release slot cũ.
  - **Scenario E:** RAG boundary — FAQ trả lời từ KB; câu hỏi availability gọi tool, **không dùng RAG**.

- [ ] **Task 6.6: Deploy & Final**
  - Local: Docker Compose chạy đầy đủ.
  - Online: Frontend → Vercel, Backend → managed container/cloud, DB → managed PostgreSQL.
  - GitHub CI.
  - Final report/slide/demo script.

---

## Definition of Done (from spec_2.md)

### Core thesis
- [ ] Customer search được property qua Web Chat.
- [ ] LLM extract được structured requirements.
- [ ] Property results đến từ backend data.
- [ ] Availability Engine kiểm tra Property + Sale + Capacity.
- [ ] Vehicle path chạy qua mock adapter.
- [ ] Soft-hold configurable.
- [ ] Booking state machine hoạt động.
- [ ] PostgreSQL transaction/locking chống double-booking.
- [ ] Sale approval/HITL hoạt động.
- [ ] Reschedule và cancel hoạt động.

### Supporting system
- [ ] RBAC hoạt động.
- [ ] Staff Dashboard: Booking List/Detail, Calendar, HITL Queue.
- [ ] Basic CRUD hoạt động.
- [ ] RAG trả lời knowledge questions; không can thiệp transaction facts.
- [ ] Web/Email notification hoạt động; SMS/Zalo mock nếu cần.
- [ ] Audit + AI/tool logs được lưu.
- [ ] Core analytics/evaluation được đo.

### Quality
- [ ] Test concurrent booking.
- [ ] Test soft-hold expiry.
- [ ] Test reschedule rollback.
- [ ] Test API/LLM/tool timeout.
- [ ] Test hallucination prevention.
- [ ] Test RBAC/data isolation.
- [ ] Chạy local.
- [ ] Deploy online.
- [ ] Demo end-to-end reproducible.
