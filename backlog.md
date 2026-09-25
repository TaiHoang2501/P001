# Backlog: BookingBot AI Agent

Danh sách các công việc được chia nhỏ dựa trên lộ trình (Roadmap) của `spec_1.md`.

## Phase 1: Foundation (Khởi tạo dự án & Hạ tầng)
- [ ] **Task 1.1: Setup repo & Database**
  - Khởi tạo dự án Next.js (frontend) và FastAPI (backend).
  - Cấu hình file `docker-compose.yml` (PostgreSQL, pgvector, Redis).
  - Khởi tạo mô hình DDL Database (bảng users, properties, projects, bookings).
- [ ] **Task 1.2: Base API & Seed Data**
  - Viết script tạo seed data (khoảng 100 properties, sales, capacities, vehicles).
  - Thiết lập Basic Authentication & RBAC (Role-Based Access Control) cho FastAPI.
- [ ] **Task 1.3: UI Framework**
  - Thiết lập thư viện UI/Component cho Next.js (ví dụ Tailwind, shadcn/ui).
  - Tạo khung layout chính cho Web Chat và Staff Dashboard.

## Phase 2: Core Transaction (Nghiệp vụ cốt lõi Backend)
- [ ] **Task 2.1: Property APIs**
  - API Search (lọc BĐS theo criteria).
  - API xem chi tiết Property.
- [ ] **Task 2.2: Booking State Machine & Soft-hold**
  - Cài đặt state machine cho Booking (Draft -> Soft-held -> Confirmed...).
  - Xây dựng service tạo Soft-hold và cấu hình hết hạn (expiry).
- [ ] **Task 2.3: Availability Service**
  - Xây dựng thuật toán check đồng thời 4 resource: Căn, Sale, Sức chứa, Phương tiện.
- [ ] **Task 2.4: Approval Workflow**
  - API cho phép Sale approve/reject soft-hold.
  - API xử lý Reschedule/Cancel booking.

## Phase 3: AI Agent (LangGraph & LLM)
- [ ] **Task 3.1: LLM Adapter & State**
  - Viết Adapter gọi LLM (OpenAI) trong `src/agents/`.
  - Định nghĩa `TypedDict` cho Agent (chat history, extracted criteria).
- [ ] **Task 3.2: Tools Integration**
  - Bọc các services ở Phase 2 thành LangChain `@tool` (`search_properties`, `check_availability`, `create_hold`, `request_approval`).
- [ ] **Task 3.3: Agent Orchestration & Guardrails**
  - Định nghĩa luồng Graph (Nodes, Edges).
  - Cài đặt cơ chế bắt lỗi (Fallback) và kiểm duyệt để chống hallucination thông tin BĐS.
- [ ] **Task 3.4: HITL (Human-in-the-Loop)**
  - Xây dựng edge riêng cho HITL. Đẩy các request không tự động duyệt được (VIP, out-of-hours) vào queue cho Sale/Operator xử lý.

## Phase 4: RAG & Notifications
- [ ] **Task 4.1: Knowledge Base Setup**
  - Định nghĩa Schema cho tài liệu nội quy, chính sách.
  - Cài đặt pipeline embedding & pgvector retrieval.
- [ ] **Task 4.2: Tích hợp RAG vào Agent**
  - Tạo tool cho phép Agent truy vấn Knowledge Base trả lời FAQ.
- [ ] **Task 4.3: Notifications Engine**
  - Khởi tạo Notification Provider Abstraction (Email, SMS mock, Web).
  - Gắn trigger gửi thông báo khi thay đổi state của Booking và gửi nhắc nhở 24h.

## Phase 5: Dashboard & Analytics (Staff UI)
- [ ] **Task 5.1: Booking Management & HITL UI**
  - Màn hình quản lý Booking (duyệt/từ chối/đổi lịch).
  - Màn hình hàng chờ HITL.
- [ ] **Task 5.2: Resource Calendar & CRUD**
  - Calendar view quản lý Sale, Property, Capacity.
  - CRUD giao diện quản lý Properties, Users.
- [ ] **Task 5.3: Analytics Dashboard**
  - Các KPI cards (Tổng booking, tỷ lệ chốt, no-show).
  - Biểu đồ thống kê.

## Phase 6: QA & Demo
- [ ] **Task 6.1: End-to-End Testing**
  - Viết test Happy path, Failure testing, Concurrency (chống double-booking).
- [ ] **Task 6.2: Security & Logging Audit**
  - Kiểm tra log AI/Tool, Audit log.
- [ ] **Task 6.3: Deploy & Demo script**
  - Deploy frontend lên Vercel, Backend/DB lên cloud.
  - Hoàn thiện script demo kịch bản A, B, C, D theo `spec_1.md`.
