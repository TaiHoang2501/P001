# Kế hoạch Triển khai (Implementation Plan): BookingBot AI Agent

> Căn cứ theo đặc tả kỹ thuật toàn diện tại [spec_updated.md](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/.specify/spec_updated.md).

---

## 1. Kiến trúc Hệ thống (System Architecture)
Hệ thống tuân thủ kiến trúc phân tầng an toàn:
- **Frontend Layer**: Next.js + TypeScript (Responsive Web gồm: Customer AI Chat hỗ trợ streaming SSE, Owner Approval & Listing Dashboard, Operator Moderation & Monitoring Dashboard).
- **AI Agent Layer (`src/agents/`)**: Sử dụng **LangGraph**. Đóng vai trò **Orchestrator**: Bóc tách nhu cầu tự nhiên thành `CustomerPreference`, duy trì hội thoại đa lượt, chọn công cụ (Tools), giải thích đề xuất (Explainability).
- **Service/Business Layer (`src/services/`)**: Thực thi nghiệp vụ xác định: Tìm kiếm & xếp hạng hybrid (SQL Hard Filter + Soft Scoring), Availability Engine, Booking State Machine, Viewing Hold Engine, Quản lý kênh Chat WebSocket.
- **API Layer (`src/api/`)**: FastAPI endpoints tiếp nhận request từ Frontend, kiểm soát Auth & RBAC (JWT + OTP, Argon2id/bcrypt), Pydantic Schemas, đóng vai trò **Source of Truth** (tuyệt đối không cho AI ghi đè dữ liệu trực tiếp).
- **Database & Storage**: PostgreSQL (Relational tables, Full-text Search + `pg_trgm`, ACID transactions, Row-level locking) + Amazon S3 (Lưu trữ ảnh & video căn hộ).

---

## 2. Thiết kế Cơ sở Dữ liệu & Thực thể Chính
- **Users & Roles**: `Customer`, `Owner` (Chủ nhà), `Investor / Operator` (Ban quản trị).
- **Properties**: `id`, `owner_id`, `project_name` (Vinhomes), `zone/building`, `price`, `bedrooms`, `area`, `floor`, `direction`, `amenities`, `status` (`DRAFT`, `PENDING_REVIEW`, `APPROVED/AVAILABLE`, `VIEWING_HELD`, `SOLD`).
- **Bookings**: `id`, `property_id`, `customer_id`, `owner_id`, `viewing_window` (start/end), `status` (`REQUESTED`, `CONFIRMED`, `COMPLETED`, `REJECTED`, `CANCELLED`, `RESCHEDULE_REQUESTED`).
- **Viewing Holds**: `id`, `booking_id`, `property_id`, `start_time`, `end_time`, `is_active` (Atomic Hold khóa căn đúng khung giờ xem sau khi Owner duyệt).
- **Purchase Requests & Direct Chats**: `id`, `booking_id`, `customer_id`, `owner_id`, `status`, `created_at` (Mở kênh WebSocket chat 1-1).
- **Audit Logs & AI Runs**: Lưu vết đầy đủ `User Action → Agent Run → Tool Call → DB Mutation`.

---

## 3. Kế hoạch Triển khai 6 Giai đoạn (6 MVP Phases)

### Phase 1 --- Foundation (Nền tảng & Dữ liệu)
- [ ] Thiết lập Auth & RBAC (Khách qua OTP/Booking Code; Chủ nhà & Operator qua JWT + Argon2id).
- [ ] Thiết lập cấu trúc cơ sở dữ liệu PostgreSQL (Users, Roles, Properties, Bookings, Holds).
- [ ] Cấu hình tích hợp Amazon S3 để upload và lưu trữ media ảnh/video căn hộ Vinhomes.
- [ ] Xây dựng quy trình kiểm duyệt tin đăng của Chủ nhà (`DRAFT → PENDING_REVIEW → APPROVED`).

### Phase 2 --- Customer Discovery (Khám phá & Gợi ý Căn hộ AI)
- [ ] Xây dựng AI Chat với LangGraph: Trích xuất `CustomerPreference` (Budget, PN, Diện tích, Phân khu, Hướng, Tầng).
- [ ] Triển khai Thuật toán Tìm kiếm & Xếp hạng 5 bước:
  1. *Hard filter:* SQL lọc dự án, ngân sách trần, số phòng ngủ tối thiểu.
  2. *Soft scoring:* Giá (30%), Diện tích (20%), Thiết kế/Layout (20%), Hướng (15%), Tầng (15%).
  3. *Priority weighting & Proximity score:* Ưu tiên theo nhu cầu nổi bật của khách.
  4. *Explainability:* Tạo câu giải thích vì sao căn này phù hợp nhất với khách.
- [ ] Trả về Property Cards trực quan trên Web Chat.

### Phase 3 --- Booking & Viewing Hold (Đặt lịch & Giữ căn)
- [ ] Xây dựng Tool `check_availability` kiểm tra lịch trống của căn và chủ nhà.
- [ ] Xây dựng Tool `create_booking_request`: Tạo yêu cầu đặt lịch ở trạng thái `REQUESTED`.
- [ ] Xây dựng quy trình Chủ nhà duyệt lịch (**Owner Approval - Bắt buộc / HITL**): Chủ nhà Approve $\rightarrow$ chuyển sang `CONFIRMED`.
- [ ] Kích hoạt **Viewing Hold nguyên tử (Atomic)**: Tạm khóa căn trong khung giờ xem, ngăn chặn tuyệt đối double-booking.
- [ ] Xử lý hủy lịch (Khách tự hủy) và đổi lịch (cần Chủ nhà xác nhận lại).

### Phase 4 --- Post-Viewing & Direct Chat (Hậu xem nhà & Kết nối)
- [ ] Thiết lập hệ thống gửi thông báo nhắc lịch tự động tại thời điểm **T-24h và T-2h** (In-app, SMS/Zalo mock).
- [ ] Ghi nhận kết quả buổi xem nhà (`COMPLETED`).
- [ ] Khách gửi **Purchase Request** sau khi xem nhà thành công.
- [ ] Hệ thống mở kênh **Chat trực tiếp 1-1 (WebSocket)** giữa Khách hàng và Chủ nhà để tự đàm phán giá.

### Phase 5 --- Operations & Dashboards (Vận hành & Giám sát)
- [ ] Giao diện **Owner Dashboard**: Quản lý căn hộ, danh sách lịch xem cần duyệt.
- [ ] Giao diện **Investor/Operator Dashboard**: Duyệt tin đăng căn hộ, giám sát Viewing Hold, xử lý báo cáo tranh chấp.
- [ ] Giám sát lỗi hệ thống (Fallback sang Operator khi có sự cố).
- [ ] Ghi nhận và theo dõi các chỉ số KPIs (Thời gian xử lý của Chủ nhà, Tỷ lệ duyệt, Tỷ lệ chuyển đổi).

### Phase 6 --- Evaluation & Testing (Kiểm thử & Đánh giá)
- [ ] Xây dựng Golden Test Set cho AI: Đánh giá độ chính xác bóc tách yêu cầu và chọn công cụ.
- [ ] Concurrency Test: Giả lập 2 khách đặt trùng slot $\rightarrow$ kiểm tra tính toàn vẹn của Viewing Hold và cơ chế khóa hàng.
- [ ] Kiểm thử luồng ngoại lệ: Chủ nhà từ chối lịch $\rightarrow$ AI gợi ý khung giờ/căn hộ thay thế.
- [ ] Đóng gói Docker Compose chạy toàn diện local và chuẩn bị kịch bản demo end-to-end.

---

## 4. Quản lý Rủi ro & Ranh giới Hệ thống (Risk & Guardrails)
- **Rủi ro AI phát ngôn sai lệch / Hallucination**: AI không được tự suy diễn thông tin căn hộ ngoài dữ liệu DB; giải thích đề xuất phải dựa trên dữ liệu thật.
- **Rủi ro Double-booking**: Áp dụng giao dịch nguyên tử (Atomic Transaction) với row-level lock (`SELECT ... FOR UPDATE`); chỉ một khách được giữ căn trong cùng một khung giờ.
- **Ranh giới sản phẩm (Non-goals)**:
  - Tuyệt đối không làm thanh toán/đặt cọc trực tuyến.
  - Tuyệt đối không để AI tự đàm phán giá hoặc tự ý xác nhận giao dịch mua bán.
  - Không sử dụng Vector DB / RAG ngoài phạm vi trong MVP.
