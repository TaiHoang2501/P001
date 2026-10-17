# Kế hoạch Triển khai (Implementation Plan): BookingBot AI Agent

> Căn cứ theo đặc tả [spec_final.md](spec_final.md); quy tắc nghiệp vụ đang chạy và các điểm hệ thống khác spec ghi
> trong [CLAUDE.md](../CLAUDE.md). Checklist chi tiết: [tasks.md](tasks.md).
> Trạng thái: `[x]` đã có trong code, `[ ]` chưa làm, *(post-MVP)* = ngoài phạm vi MVP (MVP kết thúc tại buổi xem nhà).

---

## 1. Kiến trúc Hệ thống (System Architecture)
Hệ thống tuân thủ kiến trúc phân tầng an toàn (sơ đồ: [`DIagram/System Overview Diagram.md`](../DIagram/System%20Overview%20Diagram.md)):
- **Frontend Layer** (`frontend/`): React 19 + Vite + TypeScript, Tailwind, TanStack Query, `openapi-fetch` với kiểu sinh từ OpenAPI. Responsive Web gồm: Buyer AI Chat (streaming SSE, khách chưa đăng nhập vẫn chat được), trang Hoạt động + mã QR, Seller Portal (sổ đỏ, tin đăng, lịch trống, yêu cầu xem), Operator Console (duyệt tin, ngoại lệ, giám sát lịch xem), trang dev `/dev`.
- **AI Agent Layer (`src/agents/`)**: **LangGraph** (node `agent` ⇄ `tools`, bộ nhớ hội thoại = checkpoint PostgreSQL). Bóc tách nhu cầu, hội thoại đa lượt, chọn 12 tool có kiểm soát, giải thích đề xuất; guardrails bằng code + giám khảo AI quanh mỗi lượt chat.
- **Service/Business Layer (`src/services/`)**: Tìm kiếm & xếp hạng (SQL Hard Filter + Soft Scoring), Availability/Scheduling, Booking State Machine, Deal, Viewing Hold, xác thực sổ đỏ + hỗ trợ, ghi nhận sau buổi xem, thông báo (in-app + SSE realtime), escalation, rate limit, kill switch, trace AI.
- **API Layer (`src/api/`)**: FastAPI, Auth & RBAC (SĐT + OTP cho người mua / người bán — `local` hoặc Firebase Phone Auth; email + mật khẩu Argon2 cho Operator; JWT), Pydantic v2. Backend là **Source of Truth** (AI không ghi dữ liệu trực tiếp).
- **Database & Storage**: PostgreSQL 15+ (Neon) — ACID, row-level lock, exclusion constraint chống trùng lịch, `pg_trgm`. Ảnh / giấy tờ tải lên lưu trong `media_files` (Amazon S3 là đích dài hạn, chưa dùng).
- **Deploy**: Docker; backend trên Render hoặc Google Cloud Run, frontend trên Vercel; CI GitHub Actions (ruff + pytest).

---

## 2. Thiết kế Cơ sở Dữ liệu & Thực thể Chính
Chi tiết: §7 của [CLAUDE.md](../CLAUDE.md) và [`src/db/models.py`](../src/db/models.py) (24 bảng).
- **Users & Roles**: `CUSTOMER` (người mua), `OWNER` (người bán), `INVESTOR_OPERATOR` (Chủ đầu tư). `buyer_profiles` nhớ tiêu chí + giờ rảnh; `seller_profiles` trạng thái xác thực.
- **Sổ đỏ**: `property_ownership_verifications` — dữ liệu Chủ đầu tư + thông tin căn gốc; mỗi sổ gắn tối đa một tin.
- **Properties**: thông tin gốc lấy từ sổ đỏ (tòa, mã căn, loại, diện tích, PN, WC, tầng, hướng); người bán nhập giá, view, nội thất, mô tả, ảnh. `status`: `PENDING_REVIEW`, `AVAILABLE`, `REJECTED`, `WITHDRAWN`, `SOLD` (`DRAFT` chỉ còn trong dữ liệu cũ). `VIEWING_HELD` suy ra từ hold `ACTIVE`, không phải cột trạng thái.
- **Deals**: mỗi Buyer + Seller + Property một Deal (`VH-yyyy-xxxxx`), `MATCHED → VIEWING_REQUESTED → VIEWING_CONFIRMED → VIEWED → INTERESTED → … → COMPLETED / CLOSED`.
- **Bookings**: `REQUESTED`, `CONFIRMED`, `RESCHEDULE_REQUESTED`, `REJECTED`, `CANCELLED`, `EXPIRED`, `COMPLETED`, `NO_SHOW`, `OWNER_ABSENT`, `UNREPORTED`; exclusion constraint theo `owner_id` + thời gian cho lịch đã xác nhận.
- **Property Holds**: `booking_id`, `property_id`, khung giờ, `status` (`ACTIVE` …) — tạo cùng transaction khi chủ căn xác nhận; exclusion constraint theo căn.
- **Purchase Requests & Direct Chats** *(post-MVP, chưa tạo bảng)*: `purchase_requests`, `chats`, `messages`.
- **AI & Vận hành**: `ai_conversations`, `ai_messages`, `recommendations`, `ai_turns` (trace cho dev), `notifications`, `escalations`, `audit_logs`, `system_settings`, `rate_limit_hits`.

---

## 3. Kế hoạch Triển khai 6 Giai đoạn (6 MVP Phases)

### Phase 1 --- Foundation (Nền tảng & Dữ liệu)
- [x] Auth & RBAC: người mua / người bán chỉ SĐT + OTP (`local` hoặc Firebase), Operator email + mật khẩu (Argon2) + JWT; SĐT demo dùng mã cố định.
- [x] Cơ sở dữ liệu PostgreSQL + Alembic migrations; seed demo chạy một lần mỗi DB (`src/db/seed_once.py`).
- [x] Media: ảnh căn và giấy tờ hỗ trợ lưu trong PostgreSQL (`media_files`, giấy tờ riêng tư). Chuyển sang Amazon S3: [ ] chưa làm.
- [x] Xác thực chủ sở hữu bằng sổ đỏ + OTP (người bán tự động `VERIFIED`; luồng hỗ trợ cho ngoại lệ).
- [x] Kiểm duyệt tin đăng: `PENDING_REVIEW → AVAILABLE / REJECTED (lý do)`, tạm ngừng, gỡ tin, đã bán.

### Phase 2 --- Customer Discovery (Khám phá & Gợi ý Căn hộ AI)
- [x] AI Chat với LangGraph: trích xuất tiêu chí (ngân sách, PN, diện tích, dự án/phân khu, hướng, view, tầng), hỏi lại khi thiếu, nhớ tiêu chí qua `buyer_profiles`.
- [x] Tìm kiếm & xếp hạng: SQL hard filter (chỉ căn `AVAILABLE` của người bán `VERIFIED`) + soft scoring, Top-N kèm giải thích dựa trên dữ liệu thật; không có căn phù hợp thì không bịa căn.
- [x] Property Cards (ảnh, chi tiết) ngay trong khung chat streaming; khách chưa đăng nhập chat được.
- [x] Guardrails: che PII, chặn prompt injection, chặn câu trả lời sai sự thật / ngoài phạm vi; giám khảo AI.

### Phase 3 --- Booking & Viewing Hold (Đặt lịch & Giữ căn)
- [x] Tool `check_seller_availability` / `check_property_availability`, giờ đề xuất dùng chung `propose_viewing_times` (báo trước tối thiểu 120 phút).
- [x] Tool `create_viewing_request`: tạo / tái dùng Deal + Booking `REQUESTED`.
- [x] Chủ căn xác nhận (**Owner Approval — HITL**, agent không làm thay) → `CONFIRMED`; từ chối kèm lý do, đề xuất tối đa 3 giờ khác, có thể đóng khung giờ.
- [x] **Viewing Hold nguyên tử** tạo cùng transaction xác nhận; exclusion constraint theo căn và theo chủ căn; yêu cầu trùng giờ của cùng chủ căn tự đóng khi một lịch được xác nhận.
- [x] Hủy lịch (người mua), đổi lịch (khi `REQUESTED`: chuyển thẳng giờ mới; khi `CONFIRMED`: cần chủ căn đồng ý), `EXPIRED` khi tới giờ mà chủ căn chưa trả lời.

### Phase 4 --- Post-Viewing (Hậu xem nhà)
- [x] Nhắc lịch tự động **T-24h và T-2h** (in-app; agent viết lời nhắc). SMS/Zalo: [ ] chưa tích hợp.
- [x] Mã QR vào cửa cho lịch đã xác nhận (`/pass/:token`).
- [x] Ghi nhận kết quả buổi xem: chủ căn `COMPLETED` / `NO_SHOW`, quá 48h → `UNREPORTED`; người mua Quan tâm / Chưa phù hợp / tranh chấp (`VIEWING_DISPUTE`).
- [ ] Khách gửi **Purchase Request** sau khi xem nhà *(post-MVP)*.
- [ ] Kênh **Chat trực tiếp 1-1 (WebSocket)** Người mua ↔ Chủ căn *(post-MVP)*.

### Phase 5 --- Operations & Dashboards (Vận hành & Giám sát)
- [x] **Seller Portal**: căn của tôi, đăng tin (form tự điền từ sổ đỏ), lịch trống, yêu cầu xem cần trả lời, ghi nhận sau buổi xem, đánh dấu đã bán.
- [x] **Operator Console**: duyệt / gỡ tin, giám sát và hủy lịch xem (kèm lý do), hàng ngoại lệ dễ đọc (chủ căn chưa trả lời, AI chuyển người thật, hỗ trợ sổ đỏ, tranh chấp). Operator không duyệt từng booking hay người bán.
- [x] Fallback sang người thật: escalation từ agent, job nền (`SELLER_NO_RESPONSE`), lỗi hệ thống (`SYSTEM_FAILURE`).
- [x] Thông báo in-app + bong bóng realtime (SSE) cho cả 3 vai trò.
- [x] Vận hành AI cho dev: kill switch, rate limit chat, trace `ai_turns`, dashboard số liệu `/dev`.
- [ ] KPI kinh doanh đầy đủ (tỷ lệ chuyển đổi chat → booking → purchase) — dashboard `/dev` mới có số liệu AI + nghiệp vụ cơ bản.

### Phase 6 --- Evaluation & Testing (Kiểm thử & Đánh giá)
- [x] Golden Set AI: 38 kịch bản / 14 nhóm (`eval/golden_set.json`, `python eval/run_golden.py`).
- [x] Concurrency test AC-08 (`tests/test_services/test_concurrency.py`).
- [x] Luồng ngoại lệ: chủ căn từ chối → gợi ý giờ / căn thay thế; e2e Core Demo Flow.
- [x] Docker + `docker-compose.yml`, deploy Render / Cloud Run + Vercel, CI ruff + pytest (340+ tests).

---

## 4. Quản lý Rủi ro & Ranh giới Hệ thống (Risk & Guardrails)
- **Hallucination**: AI chỉ dùng dữ liệu tool trả về; guardrails thay câu trả lời nhắc mã căn không có thật hoặc nói lịch "đã xác nhận" khi chưa có kết quả `CONFIRMED`.
- **Double-booking**: transaction với `SELECT ... FOR UPDATE` + exclusion constraint (theo căn cho hold, theo chủ căn cho lịch đã xác nhận); chỉ một bên thành công.
- **Privacy**: chủ căn thấy họ tên + nhu cầu người mua, SĐT/email luôn ẩn; PII khách gõ bị che trước khi tới model.
- **Ranh giới sản phẩm (Non-goals)**:
  - Không thanh toán / đặt cọc / mortgage, không ký hợp đồng điện tử.
  - Không để AI định giá, đàm phán giá, xác nhận giao dịch hay pháp lý.
  - Không gọi điện tự động, không BĐS ngoài Vinhomes, không CRM / Sale trung gian.
  - Không dùng Vector DB / RAG trong MVP.
