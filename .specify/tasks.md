# Danh sách Công việc Cụ thể (Tasks Checklist): BookingBot AI Agent

> Phân rã từ [plan.md](plan.md) và [spec_final.md](spec_final.md); quy tắc đang chạy ở [CLAUDE.md](../CLAUDE.md).
> `[x]` đã có trong code (kèm vị trí chính), `[ ]` chưa làm, *(post-MVP)* = ngoài phạm vi MVP.

---

## Phase 1: Foundation & Data Layer (Hạ tầng & Dữ liệu)
- [x] **Task 1.1: Docker & PostgreSQL Setup**
  - `docker-compose.yml`, `Dockerfile`, PostgreSQL với `pg_trgm`.
  - `.env.example` + `src/config.py` (Pydantic Settings: DB, LLM provider/keys, JWT, OTP, rate limit, guardrails…).
- [x] **Task 1.2: Database Models & Migrations (Alembic)**
  - SQLAlchemy models trong `src/db/models.py` (24 bảng: users, otp_codes, buyer/seller_profiles, property_ownership_verifications, projects, buildings, properties, property_media, media_files, availability_slots, buyer_availability, deals, bookings, property_holds, ai_*, recommendations, escalations, notifications, audit_logs, system_settings, rate_limit_hits).
  - Seed demo chạy một lần mỗi DB (`src/db/seed_once.py`, `SEED_VERSION`); dữ liệu chỉ còn tài khoản demo (`--demo-accounts-only`) và đủ mọi trường hợp cho từng vai trò (`--ensure-all-cases`).
- [x] **Task 1.3: Authentication & RBAC Engine**
  - JWT; người mua / người bán chỉ SĐT + OTP (`OTP_PROVIDER=local` hoặc `firebase`), Operator email + mật khẩu Argon2id.
  - 3 role: `CUSTOMER`, `OWNER`, `INVESTOR_OPERATOR` (`src/core/actor.py`, `deps.py`).
- [x] **Task 1.4: Media Upload Service**
  - `POST /owner/media` lưu ảnh / giấy tờ trong PostgreSQL (`media_files`), phục vụ qua `/api/v1/media/{id}`; giấy tờ riêng tư.
  - [ ] Chuyển sang Amazon S3 / presigned URL (`src/services/storage_service.py` đã có nhưng chưa dùng).
- [x] **Task 1.5: Ownership Verification & Listing Moderation**
  - Xác thực sổ đỏ: họ tên + mã sổ + SĐT đăng nhập = SĐT trên sổ + OTP → người bán `VERIFIED`; luồng hỗ trợ `OWNERSHIP_SUPPORT`.
  - "Đăng tin bán" tạo tin `PENDING_REVIEW` ngay (không có bản nháp); Operator duyệt (`AVAILABLE`) / từ chối kèm lý do (`REJECTED`) / gỡ tin đang bán.

---

## Phase 2: Customer Discovery & Recommendation Engine
- [x] **Task 2.1: LangGraph Agent Core & State Definition**
  - `src/agents/state.py`, `graph.py`: node `agent` ⇄ `tools`, checkpoint PostgreSQL (`AGENT_MEMORY=postgres`).
- [x] **Task 2.2: Requirement Extraction Prompting**
  - `src/agents/prompts.py`: bóc tách tiêu chí, hỏi lại khi thiếu; tiêu chí + giờ rảnh nhớ qua `buyer_profiles` (`buyer_memory`).
- [x] **Task 2.3: Hybrid Search & Ranking Service**
  - `src/services/property_service.py`: hard filter SQL (căn `AVAILABLE` của người bán `VERIFIED`, dự án, giá, PN…) + soft scoring theo trọng số trong `config.py`, kèm lý do phù hợp.
- [x] **Task 2.4: Agent Tools**
  - `src/agents/tools.py` → `src/services/agent_api.py`: 12 tool (`list_projects`, `search_properties`, `get_property_detail`, `get_seller_status`, `check_seller_availability`, `check_property_availability`, `get_deal_status`, `get_booking_status`, `create_viewing_request`, `cancel_viewing`, `reschedule_viewing`, `create_human_escalation`).
- [x] **Task 2.5: Streaming Chat API Endpoint**
  - `POST /api/v1/chat/stream` và `/chat/guest/stream` (SSE), `/chat/guest/{id}/claim`; thẻ căn + giờ đề xuất ngay trong chat.
- [x] **Task 2.6: Guardrails**
  - `src/agents/guardrails.py` + `guardrail_judge.py`: che PII, chặn injection, chặn câu trả lời sai sự thật / ngoài phạm vi, `StreamGate`.

---

## Phase 3: Booking & Viewing Hold (Nghiệp vụ Đặt lịch & Giữ căn)
- [x] **Task 3.1: Availability Engine**
  - `availability_service.py`, `scheduling.py` (`propose_viewing_times`, báo trước tối thiểu `VIEWING_MIN_NOTICE_MINUTES`); `POST /properties/{id}/viewing-times`.
- [x] **Task 3.2: Create Booking Request**
  - `POST /bookings` / tool `create_viewing_request`: tạo / tái dùng Deal + Booking `REQUESTED`; người mua hủy (`CANCELLED`).
- [x] **Task 3.3: Owner Approval Workflow (HITL)**
  - `POST /owner/bookings/{id}/approve` và `/reject` (lý do ≥ 10 ký tự, tối đa 3 giờ đề xuất, có thể đóng khung giờ).
  - Thông báo in-app + bong bóng realtime (SSE `/notifications/stream`).
- [x] **Task 3.4: Atomic Viewing Hold Engine**
  - Xác nhận → `CONFIRMED` + hold `ACTIVE` cùng transaction (`SELECT ... FOR UPDATE` + exclusion constraint theo căn và theo chủ căn).
  - Yêu cầu trùng giờ của cùng chủ căn tự `REJECTED`, agent báo người mua kèm giờ khác.
- [x] **Task 3.5: Reschedule & Expiry**
  - Đổi giờ khi `REQUESTED`: chuyển thẳng giờ mới; khi `CONFIRMED`: `RESCHEDULE_REQUESTED`, giữ giờ cũ tới khi chủ căn đồng ý.
  - Tới giờ xem mà chủ căn chưa trả lời → `EXPIRED`; quá `respond_by` → escalation `SELLER_NO_RESPONSE`.

---

## Phase 4: Post-Viewing & Reminders
- [x] **Task 4.1: Scheduled Reminder Worker**
  - `src/jobs.py` (trong tiến trình API, mỗi 60 s): nhắc T-24h / T-2h (agent viết lời nhắc), nhả hold hết hạn, follow-up.
- [x] **Task 4.2: Viewing Outcome**
  - `viewing_outcome_service.py`: chủ căn `COMPLETED` / `NO_SHOW`, quá 48h → `UNREPORTED`; người mua Quan tâm / Chưa phù hợp / tranh chấp `VIEWING_DISPUTE`; Operator ghi `COMPLETED` / `NO_SHOW` / `OWNER_ABSENT`.
- [x] **Task 4.3: Viewing Pass**
  - Mã QR vào cửa (`GET /bookings/{id}/pass`, trang `/pass/:token`).
- [ ] **Task 4.4: Purchase Request Workflow** *(post-MVP)*
- [ ] **Task 4.5: WebSocket 1-1 Chat Service** *(post-MVP)* — chat Người mua ↔ Chủ căn có gating; AI không can thiệp đàm phán.
- [ ] **Task 4.6: SMS / Zalo notifications** — hiện chỉ in-app.

---

## Phase 5: Operations, Monitoring & Dashboards
- [x] **Task 5.1: Seller Portal UI** (`frontend/src/pages/owner/`)
  - Xác thực sổ đỏ + yêu cầu hỗ trợ, đăng / sửa tin (form tự điền từ sổ, ảnh tải từ máy), lịch trống, yêu cầu xem, ghi nhận sau buổi xem, tạm ngừng, đánh dấu đã bán.
- [x] **Task 5.2: Operator Console UI** (`frontend/src/pages/operator/`)
  - Duyệt tin (tab "Chờ duyệt" / "Đang bán", gỡ tin), giám sát và hủy lịch xem kèm lý do, hàng ngoại lệ dễ đọc (hỗ trợ sổ đỏ, tranh chấp, chủ căn chưa trả lời, AI chuyển người thật).
- [x] **Task 5.3: Structured Audit Logging**
  - `audit_logs` cho duyệt tin, xác nhận / hủy lịch, hold, sổ đỏ, guardrails, kill switch; trang Hoạt động của người mua đọc từ đây.
- [x] **Task 5.4: Dev operations**
  - Trace `ai_turns` (`scripts/ai_traces.py`), kill switch (`/dev`, `scripts/ai_switch.py`), rate limit chat, dashboard `GET /admin/metrics`.
- [ ] **Task 5.5: Business KPI analytics** — tỷ lệ chuyển đổi chat → booking → purchase.

---

## Phase 6: QA, Concurrency Testing & Final Evaluation
- [x] **Task 6.1: Golden Dataset & AI Evaluation**
  - `eval/golden_set.json`: 51 kịch bản (32 đúng phạm vi + 19 ngoài phạm vi); `python eval/run_golden.py` → `eval/results/golden_report.md`.
- [x] **Task 6.2: Concurrency & Double-Booking Test**
  - `tests/test_services/test_concurrency.py` (AC-08: chỉ một bên thành công, cả trường hợp chủ căn ở 2 căn).
- [x] **Task 6.3: Guardrail & Hallucination Verification**
  - `tests/test_agents/test_guardrails.py`, `test_guardrails_chat.py`: đặt cọc, đàm phán / dự đoán giá, căn bịa, injection, PII.
- [x] **Task 6.4: CI/CD Pipeline & Code Quality**
  - `.github/workflows/ci.yml` (ruff check + format, pytest 389 test, coverage 91%), `cd.yml` (image GHCR), `deploy-cloudrun.yml`; Render qua `render.yaml`.
