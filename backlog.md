# Product Backlog: BookingBot AI Agent

> - **Phạm vi (Scope):** Vinhomes-only · MVP Web responsive · AI-first.
> - **3 Actors chính:** Customer (Khách hàng), Owner (Chủ nhà), Investor / Operator (Ban quản trị / Vận hành).
> - **Nguyên tắc cốt lõi:** Backend là Source of Truth; AI Agent là Orchestrator; Owner Approval là bắt buộc (HITL); Viewing Hold nguyên tử; Chat Gating chặt chẽ; RAG/Vector DB không dùng trong MVP.

---

## 1. Mục tiêu & Chỉ số Thành công (Success Metrics & KPIs - §2.2)

| Chỉ số (KPI) | Mục tiêu MVP | Phương pháp đo lường |
|---|---|---|
| **Thời gian phản hồi của Chủ nhà** | $\le 2$ giờ | Thời gian từ lúc tạo Booking Request đến khi Chủ nhà Approve/Reject |
| **Tỷ lệ buổi xem nhà hoàn thành** | $\ge 70\%$ | Số buổi xem nhà `COMPLETED` / Tổng số booking `CONFIRMED` |
| **Tỷ lệ khách vắng mặt (No-show)** | $\le 10\%$ | Số buổi `NO_SHOW` / Tổng số booking `CONFIRMED` |
| **Tỷ lệ trùng lịch (Double-booking)** | **$0\%$** | Tuyệt đối không để xảy ra 2 active hold/booking trùng khung giờ |
| **Tỷ lệ gửi yêu cầu mua sau khi xem** | $\ge 20\%$ | Số `Purchase Request` / Tổng số buổi xem `COMPLETED` |
| **Độ chính xác bóc tách nhu cầu của AI** | $\ge 90\%$ | Đánh giá trên tập dữ liệu Golden Test Set (50+ ca) |
| **Độ chính xác chọn Tool của AI** | $\ge 95\%$ | Đánh giá qua bộ test Intent $\rightarrow$ Tool Selection |

---

## 2. Ma trận Phân công Trách nhiệm (Workstreams - §8.1)

| Workstream | Phạm vi công việc chính | Thành viên phụ trách |
|---|---|---|
| **Product / PM** | Yêu cầu nghiệp vụ, Business rules, KPIs, Acceptance criteria, Spec | Hoàng Anh Tài (Leader) |
| **AI / Agent** | System Prompt, LangGraph StateGraph, Tool schemas, AI Evaluation | Ngọ Doãn Ngọc |
| **Backend** | FastAPI routes, Booking Engine, Viewing Hold, RBAC, WebSocket chat | Ngọ Doãn Ngọc |
| **Frontend** | Responsive Web Next.js, Streaming chat SSE, Property Cards, Dashboards | Ngọ Doãn Ngọc |
| **Data & Systems** | PostgreSQL schema, Full-text Search + `pg_trgm`, Tích hợp Amazon S3 | Nguyễn Văn Bảo |
| **QA / Testing** | Unit tests, Integration tests, Concurrency test race condition, Test report | Trần Thị Thu Trang |
| **DevOps & Security** | Docker, CI/CD GitHub Actions, AWS S3, Auth JWT/OTP, PII & Audit logs | Hoàng Anh Tài / Team |

---

## 3. Danh mục Công việc Chi tiết theo 6 Giai đoạn MVP (§8.2)

### Phase 1: Foundation (Khởi tạo Nền tảng, Dữ liệu & Phân quyền)
> **Mục tiêu:** Xây dựng hạ tầng container, cấu trúc cơ sở dữ liệu PostgreSQL, dịch vụ lưu trữ media S3 và hệ thống xác thực phân quyền 3 roles.

- [ ] **Task 1.1: Docker & PostgreSQL Setup**
  - Cấu hình `docker-compose.yml` chạy PostgreSQL 15+ cài sẵn extension `pg_trgm`.
  - Cấu hình `.env.example` và module `src/config.py` (Database URL, OpenAI API Key, S3 Credentials, JWT Secret).
  - *Acceptance Criteria:* `docker compose up` khởi động thành công PostgreSQL và Backend server mà không có lỗi.
- [ ] **Task 1.2: Database Models & Migrations (Alembic)**
  - Thiết kế models SQLAlchemy/SQLModel: `users`, `properties`, `property_media`, `bookings`, `viewing_holds`, `purchase_requests`, `chat_rooms`, `chat_messages`, `audit_logs`.
  - Viết script seed data mẫu: 30–50 căn hộ Vinhomes thật (Ocean Park, Smart City, Grand Park) với đầy đủ thông số.
  - *Acceptance Criteria:* Chạy migrate tự động tạo đúng toàn bộ bảng, quan hệ khóa ngoại (Foreign Keys) và indexes.
- [ ] **Task 1.3: Authentication & Role-Based Access Control (RBAC)**
  - Customer: Xác thực qua SMS OTP hoặc mã định danh Booking Code.
  - Owner & Operator: Đăng nhập Email + Mật khẩu mã hóa bằng **Argon2id/bcrypt** + JWT Bearer Token.
  - Phân quyền middleware: Chặn truy cập trái phép (`403 Forbidden`) đối với các endpoint ngoài quyền.
  - *Acceptance Criteria:* Mỗi tài khoản chỉ gắn với 1 vai trò duy nhất; mật khẩu không bao giờ lưu plaintext.
- [ ] **Task 1.4: Amazon S3 Media Storage Service**
  - Tích hợp Boto3 client tạo Presigned URL upload ảnh và video căn hộ lên S3.
  - Tách biệt hoàn toàn việc lưu media tĩnh ra khỏi database quan hệ.
  - *Acceptance Criteria:* Ảnh căn hộ được upload trực tiếp lên S3 và database chỉ lưu đường dẫn URL hợp lệ.
- [ ] **Task 1.5: Listing Moderation Workflow**
  - Xây dựng API cho Chủ nhà tạo căn (`DRAFT`), gửi duyệt (`PENDING_REVIEW`).
  - Xây dựng API cho Ban quản trị duyệt tin (`APPROVED / AVAILABLE`) hoặc từ chối (`REJECTED`).
  - *Acceptance Criteria:* Chỉ căn `APPROVED` mới xuất hiện trên kết quả tìm kiếm của khách hàng.

---

### Phase 2: Customer Discovery & Recommendation Engine
> **Mục tiêu:** Xây dựng bộ não AI đàm thoại tự nhiên với khách hàng qua Web Chat, trích xuất cấu trúc nhu cầu và thực thi thuật toán xếp hạng căn hộ 5 bước.

- [ ] **Task 2.1: LangGraph Agent Core & State Schema**
  - Định nghĩa State TypedDict: `messages`, `customer_preference` (ngân sách min/max, số PN, diện tích, phân khu, khoảng tầng, hướng ban công, tiện ích), `current_step`.
  - Thiết lập StateGraph hỗ trợ đàm thoại đa lượt (Multi-turn state) và lưu session checkpoint.
  - *Acceptance Criteria:* AI duy trì được ngữ cảnh qua ít nhất 5 lượt chat liên tục mà không mất thông tin.
- [ ] **Task 2.2: Natural Language Requirement Extraction Prompt**
  - Xây dựng System Prompt chuẩn hóa cho `gpt-4o-mini`: trích xuất chính xác các tiêu chí bắt buộc vs sở thích mềm.
  - Xử lý thiếu thông tin (**F1 - Missing info**): Nếu thiếu ngân sách hoặc số phòng, AI chủ động hỏi lại lịch sự thay vì đoán mò.
  - *Acceptance Criteria:* Bóc tách chính xác $\ge 90\%$ các tiêu chí từ các câu hội thoại phức tạp.
- [ ] **Task 2.3: Hybrid Search & Scoring Engine (5 bước theo §4.6)**
  - Bước 1: *Hard filter SQL:* Lọc căn `APPROVED`, đúng dự án Vinhomes, giá $\le$ ngân sách trần, số PN $\ge$ số phòng tối thiểu.
  - Bước 2: *Soft scoring:* Giá (30%), Diện tích (20%), Thiết kế/Layout (20%), Hướng (15%), Tầng (15%).
  - Bước 3: *Priority weighting:* Tự động tăng trọng số theo ưu tiên của khách (vd: ưu tiên hướng Đông Nam hoặc view hồ).
  - Bước 4: *Proximity score:* Tính điểm khoảng cách đến các tiện ích Vinhomes (Vincom, Vinschool, Hồ, Ga Metro).
  - Bước 5: *Explainability:* Tạo câu giải thích ngắn gọn vì sao căn này phù hợp nhất với khách.
  - *Acceptance Criteria:* Trả về Top 3–5 căn có điểm cao nhất kèm lý do giải thích minh bạch dựa trên dữ liệu thật.
- [ ] **Task 2.4: Controlled Search Tools**
  - Bọc service tìm kiếm thành LangChain tool: `search_properties(criteria)`.
  - Bọc service chi tiết căn hộ: `get_property_detail(property_id)`.
  - Xử lý không tìm thấy căn (**F2 - No match**): Giải thích rõ và đề xuất nới lỏng các tiêu chí mềm.
  - *Acceptance Criteria:* Agent gọi Tool chính xác theo Pydantic schema, format trả về thẻ căn hộ (Property Cards) trực quan.
- [ ] **Task 2.5: Streaming Chat API & UI**
  - Xây dựng endpoint `POST /api/v1/chat` hỗ trợ Server-Sent Events (SSE).
  - Giao diện Web Chat Next.js hiển thị chữ chạy thời gian thực và thẻ căn hộ tương tác.
  - *Acceptance Criteria:* Thời gian phản hồi token đầu tiên (TTFT) $\le 1.5$ giây trên môi trường mạng thông thường.

---

### Phase 3: Booking & Atomic Viewing Hold
> **Mục tiêu:** Xây dựng quy trình đặt lịch xem nhà chuẩn mực, cơ chế Chủ nhà phê duyệt (HITL) và khóa căn nguyên tử (Viewing Hold) chống trùng lịch.

- [ ] **Task 3.1: Availability Engine**
  - Tool `check_availability(property_id, datetime)`: Kiểm tra lịch trống của căn hộ và khung giờ khả dụng của Chủ nhà.
  - Xử lý lịch hết hạn (**F3 - Stale availability**): Tự động re-check trước khi xác nhận và báo cho khách nếu slot vừa mất.
  - *Acceptance Criteria:* Trả về chính xác các khung giờ còn trống trong ngày của căn hộ.
- [ ] **Task 3.2: Create Booking Request**
  - Tool `create_booking_request`: Tạo yêu cầu lịch xem mới ở trạng thái `REQUESTED`.
  - Khách hàng có quyền tự hủy booking (`CANCELLED`) bất cứ lúc nào trước buổi xem.
  - *Acceptance Criteria:* Bản ghi Booking được lưu với đúng `property_id`, `customer_id`, `owner_id`, thời gian bắt đầu và kết thúc.
- [ ] **Task 3.3: Owner Approval Workflow (HITL Bắt buộc)**
  - Gửi thông báo tức thời cho Chủ nhà qua In-app notification / SMS khi có yêu cầu mới.
  - Màn hình cho Chủ nhà duyệt lịch: Bấm `Approve` hoặc `Reject`.
  - Xử lý Chủ nhà từ chối (**F4 - Owner rejection**): Hệ thống tự động báo cho khách và AI gợi ý khung giờ khác hoặc căn tương tự.
  - *Acceptance Criteria:* Trạng thái booking chỉ chuyển sang `CONFIRMED` khi có quyết định Approve từ chính Chủ nhà.
- [ ] **Task 3.4: Atomic Viewing Hold Engine**
  - Khi booking chuyển sang `CONFIRMED` $\rightarrow$ Tự động tạo bản ghi `Viewing Hold` với giao dịch nguyên tử (`SELECT ... FOR UPDATE`).
  - Tạm khóa căn hộ **đúng trong khung giờ xem nhà**, không cho khách khác đặt trùng giờ.
  - Xử lý tranh chấp đồng thời (**F5 - Concurrent booking**): Đúng 1 request thành công, request thứ hai nhận thông báo xung đột an toàn.
  - Hết thời gian xem nhà $\rightarrow$ Background job tự động giải phóng Hold đưa căn hộ về trạng thái `AVAILABLE`.
  - *Acceptance Criteria:* Tỷ lệ double-booking đạt tuyệt đối $0\%$ trong các bài test áp lực.
- [ ] **Task 3.5: Reschedule Booking Workflow**
  - Luồng đổi lịch hẹn: Chuyển trạng thái sang `RESCHEDULE_REQUESTED`.
  - Bắt buộc kiểm tra giờ trống mới và gửi Chủ nhà phê duyệt lại trước khi giải phóng slot cũ.
  - *Acceptance Criteria:* Nếu đổi lịch thất bại hoặc Chủ nhà từ chối, lịch hẹn cũ vẫn được giữ nguyên an toàn.

---

### Phase 4: Post-Viewing, Reminders & Realtime Direct Chat
> **Mục tiêu:** Tự động hóa gửi thông báo nhắc lịch T-24h/T-2h, ghi nhận kết quả xem nhà và kích hoạt kênh chat 1-1 Khách ↔ Chủ nhà.

- [ ] **Task 4.1: Automated Reminders Worker**
  - Background worker quét các booking sắp diễn ra:
    - Nhắc hẹn trước **T-24h**: Thông báo xác nhận lịch xem nhà.
    - Nhắc hẹn trước **T-2h**: Thông báo kèm vị trí chi tiết căn hộ, mã số căn và lưu ý khi đến dự án Vinhomes.
  - Xử lý lỗi gửi tin (**F8 - Notification failure**): Ghi log lỗi và thử lại (retry) theo chính sách exponential backoff.
  - *Acceptance Criteria:* $100\%$ booking `CONFIRMED` đều nhận được thông báo nhắc hẹn đúng thời điểm.
- [ ] **Task 4.2: Viewing Completion & Status Transition**
  - Sau thời gian xem nhà: Cập nhật trạng thái thành `COMPLETED` (hoặc `NO_SHOW` nếu khách không đến).
  - *Acceptance Criteria:* Trạng thái chuyển đổi chính xác và Viewing Hold được giải phóng an toàn.
- [ ] **Task 4.3: Purchase Request Workflow**
  - Khách hàng bấm gửi `Purchase Request` sau khi buổi xem nhà hoàn thành để thể hiện nhu cầu xúc tiến giao dịch.
  - *Acceptance Criteria:* Yêu cầu mua/thuê được gửi thông báo đến Chủ nhà kèm thông tin liên lạc xác thực của khách.
- [ ] **Task 4.4: WebSocket 1-1 Chat Service & Chat Gating**
  - Xây dựng WebSocket endpoint `/ws/chat/{room_id}` trong FastAPI.
  - **Cơ chế Chat Gating chặt chẽ (§4.10):** Chỉ mở quyền truy cập phòng chat khi booking đã `COMPLETED` và có `Purchase Request`.
  - Xử lý vi phạm truy cập (**F11 - Chat access violation**): Từ chối kết nối nếu chưa đủ điều kiện nghiệp vụ.
  - Cho phép Khách hàng và Chủ nhà tự do trao đổi và đàm phán giá (AI không can thiệp đàm phán hay chốt giao dịch).
  - *Acceptance Criteria:* Tin nhắn truyền gửi tức thời qua WebSocket, lưu trữ đầy đủ trong database để phục vụ tra cứu khi tranh chấp.

---

### Phase 5: Operations, Dashboards & Monitoring
> **Mục tiêu:** Xây dựng giao diện quản trị chuyên biệt cho Chủ nhà và Ban quản trị, cơ chế giám sát vận hành và xử lý sự cố.

- [ ] **Task 5.1: Owner Management Dashboard UI**
  - Màn hình quản lý danh sách căn hộ đăng bán/cho thuê (tạo mới, sửa thông tin, tải ảnh S3).
  - Màn hình danh sách yêu cầu đặt lịch xem: Xem chi tiết nhu cầu khách, bấm Approve / Reject / Đổi giờ.
  - Màn hình chat trực tiếp 1-1 với khách hàng đã xem nhà.
  - *Acceptance Criteria:* Chủ nhà thao tác duyệt lịch mượt mà trong vòng dưới 3 clicks.
- [ ] **Task 5.2: Investor / Operator Moderation Dashboard UI**
  - Màn hình kiểm duyệt tin đăng mới của Chủ nhà (`DRAFT` $\rightarrow$ `APPROVED` hoặc `REJECTED`).
  - Bảng theo dõi thời gian thực các buổi xem nhà và trạng thái Viewing Hold.
  - Cơ chế can thiệp thủ công (**F9 - System failure / Operator Fallback**): Ban quản trị có quyền hủy hoặc điều phối lại khi hệ thống gặp ngoại lệ.
  - *Acceptance Criteria:* Operator lọc và duyệt tin đăng nhanh chóng, có bộ lọc xem các booking đang tranh chấp.
- [ ] **Task 5.3: Structured Audit Logging & Analytics**
  - Ghi nhận Audit Log toàn diện cho các thao tác quan trọng: duyệt tin, duyệt booking, kích hoạt hold, hủy booking.
  - Dashboard thống kê các chỉ số vận hành: Thời gian phản hồi của Chủ nhà, Tỷ lệ duyệt, Tỷ lệ no-show, Tỷ lệ chuyển đổi sau khi xem nhà.
  - *Acceptance Criteria:* Mọi mutation nhạy cảm đều có log truy vết chứa `actor_id`, `action`, `target_id`, `timestamp`.

---

### Phase 6: QA, Concurrency Testing & Final Evaluation
> **Mục tiêu:** Kiểm thử toàn diện chất lượng AI, kiểm thử áp lực chống double-booking, rà soát bảo mật và hoàn tất đóng gói.

- [ ] **Task 6.1: Golden Dataset & AI Extraction Test**
  - Xây dựng bộ dữ liệu 50+ kịch bản hội thoại mẫu kiểm thử: Bóc tách thực thể, xử lý câu hỏi thiếu thông tin, nhận diện intent và gọi Tool.
  - *Acceptance Criteria:* Tỷ lệ trích xuất đúng đạt $\ge 90\%$, tỷ lệ chọn tool đúng đạt $\ge 95\%$.
- [ ] **Task 6.2: Concurrency & Anti-Double-Booking Stress Test**
  - Viết test script (`pytest` + `asyncio`) giả lập 10 concurrent requests cùng tranh 1 khung giờ xem nhà.
  - *Acceptance Criteria:* Đúng 1 request thành công và được tạo Viewing Hold; 9 requests còn lại nhận thông báo xung đột an toàn; không có race condition.
- [ ] **Task 6.3: Guardrail & Strict Boundary Verification**
  - Kiểm tra ranh giới an toàn: AI không tự nhận đặt cọc, không bịa đặt căn ngoài Vinhomes, không tự ý commit giao dịch, không đàm phán giá.
  - *Acceptance Criteria:* $100\%$ các câu hỏi cố tình vi phạm ranh giới đều bị từ chối lịch sự và an toàn.
- [ ] **Task 6.4: CI/CD Pipeline & Packaging Verification**
  - Kiểm tra workflow CI tự động chạy `ruff` và `pytest` khi push code lên nhánh `TaiHoang`, `develop`, `main`.
  - Kiểm tra workflow CD tự động đóng gói Docker container và đẩy lên GitHub Container Registry (`ghcr.io`).
  - *Acceptance Criteria:* Build Docker sạch sẽ, container chạy ổn định và vượt qua toàn bộ test suite.

---

## 4. Danh mục Màn hình Cần Xây dựng (Screens Checklist - §4.12)

### 4.1. Màn hình Khách hàng (Customer Screens)
- [ ] **Screen C1 - Landing Page & Search Bar:** Giới thiệu giải pháp, khung tìm kiếm nhanh căn hộ Vinhomes.
- [ ] **Screen C2 - AI Web Chat Interface:** Giao diện hội thoại AI-first hỗ trợ streaming SSE.
- [ ] **Screen C3 - Recommended Property Cards:** Danh sách thẻ căn hộ gợi ý kèm điểm số, thông số và lời giải thích.
- [ ] **Screen C4 - Property Detail View:** Chi tiết căn hộ, thư viện ảnh S3, tiện ích phân khu và lịch trống.
- [ ] **Screen C5 - Booking Request Modal:** Chọn khung giờ xem nhà và gửi yêu cầu đến Chủ nhà.
- [ ] **Screen C6 - Booking Tracking & Status:** Theo dõi tiến độ duyệt lịch, xem thông báo xác nhận và nút hủy lịch.
- [ ] **Screen C7 - Purchase Request Modal:** Gửi yêu cầu bày tỏ mong muốn mua/thuê sau buổi xem nhà.
- [ ] **Screen C8 - Customer ↔ Owner Realtime Chat:** Phòng chat 1-1 trực tiếp với chủ nhà qua WebSocket.

### 4.2. Màn hình Chủ nhà (Owner Screens)
- [ ] **Screen O1 - Owner Authentication:** Đăng nhập / Đăng ký qua Email + Password hoặc OTP.
- [ ] **Screen O2 - Owner Property Listing Manager:** CRUD danh sách căn hộ đăng tin, tải ảnh lên S3.
- [ ] **Screen O3 - Booking Approval Queue:** Bảng tiếp nhận yêu cầu đặt lịch xem nhà với nút Approve / Reject / Đổi giờ.
- [ ] **Screen O4 - Owner ↔ Customer Realtime Chat:** Phòng chat 1-1 với khách hàng đã xem nhà thành công.

### 4.3. Màn hình Ban Quản trị / Chủ đầu tư (Investor / Operator Screens)
- [ ] **Screen A1 - Operator Login:** Đăng nhập bảo mật cao (Password + 2FA).
- [ ] **Screen A2 - Listing Moderation Queue:** Màn hình duyệt tin đăng mới của Chủ nhà (`APPROVED` / `REJECTED`).
- [ ] **Screen A3 - Viewing Hold & Booking Monitor:** Giám sát các buổi xem nhà và tình trạng khóa căn thời gian thực.
- [ ] **Screen A4 - Operations Analytics Dashboard:** Bảng điều khiển biểu đồ theo dõi các chỉ số KPIs vận hành.

---

## 5. Danh mục 11 Kịch bản Xử lý Ngoại lệ (Failure Modes Handling - §5)

| Mã lỗi | Tình huống ngoại lệ | Quy tắc xử lý tự động trong hệ thống |
|---|---|---|
| **F1** | **Missing information** | Khách thiếu ngân sách/dự án $\rightarrow$ AI lịch sự hỏi bổ sung thông tin trước khi tìm. |
| **F2** | **No match** | Không có căn đạt hard constraints $\rightarrow$ AI giải thích rõ và gợi ý nới lỏng tiêu chí mềm. |
| **F3** | **Stale availability** | Khung giờ vừa bị người khác đặt mất $\rightarrow$ Hệ thống re-check và gợi ý ngay khung giờ khác. |
| **F4** | **Owner rejection** | Chủ nhà từ chối lịch $\rightarrow$ Thông báo lý do và AI gợi ý khung giờ hoặc căn hộ tương đương. |
| **F5** | **Concurrent booking** | Hai khách cùng đặt 1 slot $\rightarrow$ Khóa nguyên tử (Atomic transaction); chỉ 1 khách thành công, khách còn lại nhận thông báo bận. |
| **F6** | **Invalid listing** | Căn hộ chưa được duyệt hoặc thiếu thông tin $\rightarrow$ Tự động loại trừ khỏi kết quả đề xuất. |
| **F7** | **Unauthorized action** | Gọi công cụ hoặc truy cập ngoài quyền hạn $\rightarrow$ Backend lập tức từ chối (`403 Forbidden`). |
| **F8** | **Notification failure** | Lỗi gửi tin SMS/Zalo $\rightarrow$ Kích hoạt cơ chế thử lại (Retry) và ghi log cảnh báo. |
| **F9** | **System failure** | Lỗi sập API/Database/LLM $\rightarrow$ Giữ trạng thái an toàn và chuyển luồng xử lý thủ công cho Operator. |
| **F10** | **State conflict** | Yêu cầu hành động trái với State Machine (vd: confirm lịch đã hủy) $\rightarrow$ Từ chối giao dịch. |
| **F11** | **Chat access violation** | Khách chưa hoàn tất xem nhà đòi mở chat $\rightarrow$ Chặn quyền kết nối (Chat Gating). |
