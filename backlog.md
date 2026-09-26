# Backlog: BookingBot AI Agent

Danh sách các công việc được chia nhỏ dựa trên Kế hoạch Triển khai 6 Giai đoạn và Ranh giới MVP của **[spec_updated.md](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/.specify/spec_updated.md)**.
- **Phạm vi:** Vinhomes-only · MVP Web responsive · AI-first.
- **3 Actors:** Customer (Khách hàng), Owner (Chủ nhà), Investor / Operator (Ban quản trị / Vận hành).
- **Ranh giới cốt lõi (MUST NOT HAVE):** Không thanh toán/đặt cọc online; Không ký hợp đồng điện tử; Không định giá BĐS bằng AI; Không BĐS ngoài Vinhomes; Không AI tự đàm phán giá; Không CRM/Sale môi giới bên ngoài; Không Vector DB / RAG trong MVP.

---

## Phase 1: Foundation (Khởi tạo dự án & Hạ tầng Nền tảng)

- [ ] **Task 1.1: Repo, Docker & PostgreSQL Setup**
  - Khởi tạo repo Git + branching workflow (`main`, feature branches).
  - Cấu hình `docker-compose.yml` chạy PostgreSQL 15+ có cài đặt sẵn extension `pg_trgm` cho tìm kiếm Full-text.
  - Cấu hình file môi trường `.env.example` và module config `src/config.py`.

- [ ] **Task 1.2: Database Models & Migrations (Alembic)**
  - Xây dựng Data Models theo đặc tả:
    - `users` (id, email, phone, role, password_hash, created_at)
    - `properties` (id, owner_id, project_name, building, price, bedrooms, area, floor, direction, amenities, status, created_at)
    - `property_media` (id, property_id, s3_url, media_type, is_primary)
    - `bookings` (id, property_id, customer_id, owner_id, start_time, end_time, status, created_at)
    - `viewing_holds` (id, booking_id, property_id, start_time, end_time, is_active)
    - `purchase_requests` (id, booking_id, customer_id, owner_id, status, created_at)
    - `chat_rooms` & `chat_messages` (id, room_id, sender_id, message, created_at)
    - `audit_logs` (id, actor_id, action, target_type, target_id, details, timestamp)
  - Viết script seed data: 30–50 căn hộ Vinhomes mẫu (Ocean Park, Smart City, Grand Park).

- [ ] **Task 1.3: Authentication & Role-Based Access Control (RBAC)**
  - Customer: Xác thực qua SMS OTP hoặc mã định danh Booking.
  - Owner & Investor/Operator: Đăng nhập Email + Mật khẩu băm an toàn bằng **Argon2id/bcrypt** + JWT Bearer Token.
  - Phân quyền RBAC chặt chẽ trong FastAPI Middleware.

- [ ] **Task 1.4: Media Storage Service (Amazon S3)**
  - Tích hợp Amazon S3 client (Boto3) để tải lên ảnh và video căn hộ.
  - Cấp phát Presigned URL an toàn, tách biệt hoàn toàn media khỏi Database.

- [ ] **Task 1.5: Listing Moderation Workflow**
  - API cho Chủ nhà tạo căn (`DRAFT`) và gửi duyệt (`PENDING_REVIEW`).
  - API cho Ban quản trị duyệt tin (`APPROVED / AVAILABLE`) hoặc từ chối (`REJECTED`).
  - Quy tắc: Chỉ căn `APPROVED` mới xuất hiện trong tìm kiếm của khách hàng.

---

## Phase 2: Customer Discovery & Recommendation Engine

- [ ] **Task 2.1: LangGraph Agent Core & State Management**
  - Thiết lập StateGraph với `TypedDict` State: lưu trữ lịch sử tin nhắn, tiêu chí bóc tách `CustomerPreference`, thông tin còn thiếu.
  - Hỗ trợ lưu trữ phiên hội thoại qua cơ chế Checkpointer.

- [ ] **Task 2.2: Natural Language Requirement Extraction**
  - Xây dựng Prompt cho LLM (`gpt-4o-mini`) trích xuất chính xác các ràng buộc cứng (ngân sách, số phòng ngủ, phân khu) và sở thích mềm (hướng ban công, khoảng tầng, tiện ích).
  - Phản hồi làm rõ: Nếu thiếu tiêu chí bắt buộc, Agent chủ động hỏi lại khách.

- [ ] **Task 2.3: Hybrid Search & Scoring Engine**
  - Triển khai thuật toán xếp hạng 5 bước:
    1. *Hard filtering:* SQL lọc dự án, trạng thái `APPROVED`, ngân sách trần, số phòng ngủ tối thiểu.
    2. *Soft scoring:* Giá (30%), Diện tích (20%), Thiết kế/Layout (20%), Hướng (15%), Tầng (15%).
    3. *Priority weighting:* Tự động tăng trọng số theo yêu cầu nhấn mạnh của khách.
    4. *Proximity score:* Tính điểm theo khoảng cách đến tiện ích (trường học, hồ, metro).
    5. *Explainability:* Tạo câu giải thích logic vì sao căn hộ phù hợp.

- [ ] **Task 2.4: Controlled Search Tools**
  - Bọc service tìm kiếm thành `@tool` LangChain an toàn: `search_properties(criteria)`.
  - Bọc service xem chi tiết căn hộ: `get_property_detail(property_id)`.
  - Format kết quả trả về dạng Property Cards kèm hình ảnh S3 và nút bấm đặt lịch.

- [ ] **Task 2.5: Streaming Web Chat Interface**
  - Xây dựng giao diện Next.js Web Chat hỗ trợ streaming SSE (Server-Sent Events) hiển thị tin nhắn tức thì.

---

## Phase 3: Booking & Atomic Viewing Hold

- [ ] **Task 3.1: Availability Engine**
  - Tool `check_availability(property_id, datetime)`: Kiểm tra lịch trống của căn hộ và khung giờ đón tiếp của chủ nhà.

- [ ] **Task 3.2: Booking Request Creation**
  - Tool `create_booking_request`: Tạo lịch hẹn mới ở trạng thái `REQUESTED`.
  - Khách hàng có quyền tự hủy booking (`CANCELLED`).

- [ ] **Task 3.3: Owner Approval Workflow (HITL Bắt buộc)**
  - Gửi thông báo ngay lập tức cho Chủ nhà qua In-app / SMS khi có booking mới.
  - Màn hình cho Chủ nhà: Bấm Duyệt (`Approve`) hoặc Từ chối (`Reject`).
  - Nếu Chủ nhà từ chối $\rightarrow$ AI Agent giải thích và đề xuất khung giờ hoặc căn hộ tương tự cho khách.

- [ ] **Task 3.4: Atomic Viewing Hold Engine**
  - Khi Chủ nhà xác nhận Approve $\rightarrow$ chuyển trạng thái Booking sang `CONFIRMED`.
  - Kích hoạt **Viewing Hold nguyên tử**: Sử dụng Transaction & Row-level lock (`SELECT ... FOR UPDATE`) tạm khóa căn hộ đúng thời gian diễn ra buổi xem nhà.
  - Tuyệt đối không cho phép 2 booking trùng thời gian trên cùng 1 căn hộ (Anti-Double-Booking).
  - Hết thời gian xem $\rightarrow$ tự động giải phóng Hold đưa căn hộ về trạng thái `AVAILABLE`.

- [ ] **Task 3.5: Reschedule Booking**
  - Luồng đổi lịch hẹn (`RESCHEDULE_REQUESTED`): Bắt buộc kiểm tra giờ trống mới và cần Chủ nhà phê duyệt lại trước khi cập nhật.

---

## Phase 4: Post-Viewing, Reminders & Realtime Direct Chat

- [ ] **Task 4.1: Automated Reminders Worker**
  - Lên lịch background worker gửi thông báo nhắc hẹn tự động:
    - Trước **T-24h**: Thông báo xác nhận lịch hẹn và thời gian xem nhà.
    - Trước **T-2h**: Nhắc nhở kèm vị trí, số nhà và lưu ý khi đến dự án.

- [ ] **Task 4.2: Viewing Completion & Purchase Request**
  - Cập nhật trạng thái buổi xem sau khi diễn ra: `COMPLETED` (hoặc `NO_SHOW`).
  - Khách hàng gửi `Purchase Request` bày tỏ nhu cầu xúc tiến mua/thuê căn hộ.

- [ ] **Task 4.3: Realtime 1-1 Chat Service (WebSocket)**
  - Xây dựng WebSocket server trong FastAPI.
  - Cơ chế **Chat Gating**: Chỉ mở phòng chat trực tiếp Khách hàng ↔ Chủ nhà khi đã hoàn thành xem nhà và có Purchase Request.
  - Khách và Chủ nhà tự do trao đổi và đàm phán giá (AI không can thiệp đàm phán hay chốt giao dịch).

---

## Phase 5: Operations, Monitoring & Dashboards

- [ ] **Task 5.1: Owner Management Dashboard**
  - Giao diện quản lý danh sách căn hộ đăng tin.
  - Giao diện tiếp nhận và phê duyệt yêu cầu đặt lịch xem nhà.

- [ ] **Task 5.2: Investor / Operator Dashboard**
  - Giao diện kiểm duyệt tin đăng (`PENDING_REVIEW` $\rightarrow$ `APPROVED`).
  - Bảng giám sát các buổi xem nhà và tình trạng Viewing Hold.
  - Cơ chế can thiệp thủ công (Operator Fallback) khi hệ thống gặp ngoại lệ hoặc tranh chấp.

- [ ] **Task 5.3: Structured Audit Logs & KPI Analytics**
  - Ghi nhận Audit Log toàn diện cho các thao tác quan trọng.
  - Đo lường các chỉ số vận hành: Thời gian phản hồi của Chủ nhà, Tỷ lệ duyệt booking, Tỷ lệ no-show, Tỷ lệ chuyển đổi sau khi xem nhà.

---

## Phase 6: QA, Concurrency Testing & Final Evaluation

- [ ] **Task 6.1: Golden Evaluation Dataset for AI**
  - Xây dựng bộ 50+ test cases đánh giá độ chính xác bóc tách yêu cầu và lựa chọn Tool của Agent.

- [ ] **Task 6.2: Concurrency & Stress Testing**
  - Kiểm thử áp lực tranh chấp slot (Race Condition) đảm bảo cơ chế Viewing Hold hoạt động chuẩn xác và không bị double-booking.

- [ ] **Task 6.3: Guardrail & Edge-case Verification**
  - Kiểm tra ranh giới an toàn: AI không tự nhận đặt cọc, không bịa đặt căn ngoài Vinhomes, không tự ý commit giao dịch.

- [ ] **Task 6.4: CI/CD & Local Packaging**
  - Hoàn thiện Dockerfile và Docker Compose chạy ổn định local.
  - Cấu hình GitHub Actions CI kiểm tra lint (`ruff`) và unit tests (`pytest`).
