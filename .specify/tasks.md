# Danh sách Công việc Cụ thể (Tasks Checklist): BookingBot AI Agent

> Bảng phân rã công việc chi tiết từ [plan.md](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/.specify/plan.md) và [spec_updated.md](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/.specify/spec_updated.md). Sử dụng làm checklist thực thi cho nhóm phát triển.

---

## Phase 1: Foundation & Data Layer (Hạ tầng & Dữ liệu)
- [ ] **Task 1.1: Docker & PostgreSQL Setup**
  - Cấu hình `docker-compose.yml` chạy PostgreSQL với extension `pg_trgm` phục vụ Full-text Search.
  - Cấu hình file môi trường `.env` và `src/config.py` (Database URL, OpenAI API Key, S3 Credentials, JWT Secrets).
- [ ] **Task 1.2: Database Models & Migrations (Alembic)**
  - Viết SQLAlchemy / SQLModel cho các bảng: `users`, `roles`, `properties`, `bookings`, `viewing_holds`, `purchase_requests`, `messages`, `audit_logs`.
  - Tạo migration ban đầu và script seed data mẫu: 30–50 căn hộ Vinhomes (Ocean Park, Smart City, Grand Park).
- [ ] **Task 1.3: Authentication & RBAC Engine**
  - Xây dựng middleware xác thực JWT và cơ chế băm mật khẩu Argon2id/bcrypt.
  - Phân quyền 3 Role rõ rệt: `Customer` (xác thực OTP/Code), `Owner` (Quản lý căn & Duyệt lịch), `Investor/Operator` (Kiểm duyệt & Vận hành).
- [ ] **Task 1.4: Media Upload Service (Amazon S3)**
  - Xây dựng endpoint hỗ trợ upload ảnh/video căn hộ hoặc tạo Presigned URL lên S3, tách biệt hoàn toàn media khỏi Database.
- [ ] **Task 1.5: Listing Moderation Workflow**
  - Xây dựng API cho Chủ nhà tạo căn (`DRAFT`), gửi duyệt (`PENDING_REVIEW`).
  - Xây dựng API cho Ban quản trị phê duyệt (`APPROVED`) hoặc từ chối (`REJECTED`).

---

## Phase 2: Customer Discovery & Recommendation Engine
- [ ] **Task 2.1: LangGraph Agent Core & State Definition**
  - Định nghĩa `TypedDict` cho Agent State: `messages`, `customer_preference` (ngân sách, số PN, diện tích, phân khu, hướng, tầng, tiện ích), `current_step`.
  - Thiết lập LangGraph StateGraph hỗ trợ multi-turn conversation và lưu checkpoint.
- [ ] **Task 2.2: Requirement Extraction Prompting**
  - Viết System Prompt chuyên sâu bóc tách nhu cầu tự nhiên từ câu chat của khách hàng, nhận diện rõ tiêu chí bắt buộc vs tiêu chí ưu tiên.
  - Xây dựng luồng phản hồi: Nếu thiếu tiêu chí quan trọng (như ngân sách, số phòng), AI chủ động hỏi lại lịch sự.
- [ ] **Task 2.3: Hybrid Search & Ranking Service**
  - Viết hàm `search_properties(criteria)` tại `src/services/property_service.py`:
    - Bước 1: Hard filter SQL (Lọc căn `APPROVED`, đúng dự án, giá trong ngưỡng, đủ số phòng).
    - Bước 2: Soft scoring (Giá 30%, Diện tích 20%, Thiết kế 20%, Hướng 15%, Tầng 15%).
    - Bước 3: Proximity scoring và tính điểm tổng hợp.
    - Bước 4: Tạo lời giải thích ngắn gọn vì sao căn phù hợp (Explainability).
- [ ] **Task 2.4: Property Search Tool**
  - Đóng gói hàm tìm kiếm thành LangChain `@tool` an toàn.
  - Cập nhật Agent Graph để AI tự động gọi Tool và format danh sách Property Cards trả về kèm nút "Xem chi tiết" & "Đặt lịch".
- [ ] **Task 2.5: Streaming Chat API Endpoint**
  - Xây dựng `POST /api/v1/chat` hỗ trợ Server-Sent Events (SSE) để truyền streaming text và thẻ căn hộ mượt mà về Frontend.

---

## Phase 3: Booking & Viewing Hold (Nghiệp vụ Đặt lịch & Giữ căn)
- [ ] **Task 3.1: Availability Engine**
  - Xây dựng API và Tool `check_availability(property_id, datetime)`: Kiểm tra lịch trống của căn hộ và khung giờ khả dụng của chủ nhà.
- [ ] **Task 3.2: Create Booking Request**
  - Xây dựng API và Tool `create_booking_request`: Tạo bản ghi Booking ở trạng thái `REQUESTED`.
  - Khách hàng có thể tự hủy lịch (`CANCELLED`) bất cứ lúc nào trước khi duyệt.
- [ ] **Task 3.3: Owner Approval Workflow (HITL)**
  - Xây dựng API cho Chủ nhà: `POST /api/v1/owner/bookings/{id}/approve` và `reject`.
  - Tích hợp thông báo tức thời cho Chủ nhà khi có yêu cầu mới (In-app notification / Webhook).
- [ ] **Task 3.4: Atomic Viewing Hold Engine**
  - Khi Chủ nhà bấm Approve $\rightarrow$ chuyển trạng thái Booking thành `CONFIRMED`.
  - Tự động tạo bản ghi **`Viewing Hold`** nguyên tử với khóa hàng (`SELECT ... FOR UPDATE`), tạm khóa căn đúng khung giờ xem nhà.
  - Xử lý xung đột (Concurrency): Nếu có yêu cầu khác trùng khung giờ, lập tức báo bận và gợi ý khung giờ thay thế.
- [ ] **Task 3.5: Reschedule Booking**
  - Xây dựng luồng đổi lịch (`RESCHEDULE_REQUESTED`): Bắt buộc kiểm tra giờ trống mới và gửi Chủ nhà duyệt lại trước khi đổi.

---

## Phase 4: Post-Viewing, Reminders & Realtime Direct Chat
- [ ] **Task 4.1: Scheduled Reminder Worker**
  - Cấu hình Background Task / Cron Job quét các booking sắp diễn ra:
    - Gửi thông báo nhắc lịch trước **T-24h**.
    - Gửi thông báo nhắc lịch trước **T-2h** kèm hướng dẫn đường đi, vị trí căn hộ.
- [ ] **Task 4.2: Viewing Status Update**
  - Endpoint cập nhật kết quả sau buổi xem: `COMPLETED` (hoặc `NO_SHOW`).
- [ ] **Task 4.3: Purchase Request Workflow**
  - Khách hàng bấm gửi `Purchase Request` sau khi buổi xem nhà hoàn tất.
  - Hệ thống ghi nhận nhu cầu mua/thuê thực tế của khách hàng.
- [ ] **Task 4.4: WebSocket 1-1 Chat Service**
  - Xây dựng WebSocket Server tại `src/api/websocket.py`.
  - Cơ chế **Chat Gating**: Chỉ kích hoạt phòng chat 1-1 khi Booking đã `COMPLETED` và có `Purchase Request`.
  - Cho phép Khách hàng và Chủ nhà nhắn tin trực tiếp để tự do đàm phán giá (AI không can thiệp đàm phán).

---

## Phase 5: Operations, Monitoring & Dashboards
- [ ] **Task 5.1: Owner Dashboard UI**
  - Giao diện đăng tin căn hộ, cập nhật thông tin, tải ảnh lên S3.
  - Danh sách yêu cầu đặt lịch xem cần duyệt (Approve / Reject / Đổi giờ).
- [ ] **Task 5.2: Investor / Operator Dashboard UI**
  - Màn hình duyệt tin đăng căn hộ mới của Chủ nhà.
  - Bảng theo dõi các buổi xem nhà đang diễn ra và trạng thái Viewing Hold.
  - Quản lý tranh chấp, can thiệp thủ công khi hệ thống gặp ngoại lệ (Operator Fallback).
- [ ] **Task 5.3: Structured Audit Logging & Analytics**
  - Ghi nhận Audit Log toàn diện cho các tác vụ quan trọng: duyệt tin, duyệt booking, kích hoạt hold, hủy booking.
  - Đo lường các chỉ số vận hành: Thời gian phản hồi của Chủ nhà, Tỷ lệ duyệt, Tỷ lệ chuyển đổi từ chat $\rightarrow$ booking $\rightarrow$ purchase.

---

## Phase 6: QA, Concurrency Testing & Final Evaluation
- [ ] **Task 6.1: Golden Dataset & AI Extraction Test**
  - Xây dựng bộ dữ liệu 50 kịch bản hội thoại mẫu để đánh giá khả năng bóc tách thực thể và chọn Tool của LangGraph.
- [ ] **Task 6.2: Concurrency & Double-Booking Stress Test**
  - Viết test script (`pytest` + `asyncio`) giả lập 10 requests cùng lúc tranh 1 khung giờ xem nhà $\rightarrow$ Đảm bảo đúng 1 request thành công, các request còn lại nhận thông báo bận an toàn.
- [ ] **Task 6.3: Guardrail & Hallucination Verification**
  - Kiểm thử các ca biên: Khách hỏi giá bịa đặt, đòi đặt cọc online, hỏi BĐS ngoài Vinhomes $\rightarrow$ Xác nhận AI từ chối đúng quy định.
- [ ] **Task 6.4: CI/CD Pipeline & Code Quality**
  - Chạy `ruff check` và `ruff format` toàn bộ mã nguồn.
  - Cấu hình GitHub Actions CI chạy tự động bộ test suite trước khi merge.
