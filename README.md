# BookingBot AI Agent · Trợ lý Đặt lịch Xem nhà & Giữ căn Vinhomes

> **BookingBot AI Agent** là giải pháp AI-first chuyên biệt cho thị trường Bất động sản đại đô thị Vinhomes: Tự động trích xuất nhu cầu bằng ngôn ngữ tự nhiên, gợi ý căn hộ chính xác qua cơ chế lọc lai (Hybrid SQL + Soft Score), tự động điều phối lịch xem nhà giữa Người mua và Chủ nhà, bảo vệ giao dịch bằng cơ chế **Viewing Hold nguyên tử** (tạm khóa căn chống trùng lịch), xác thực chủ sở hữu qua **Sổ đỏ + OTP** và tích hợp bảng điều khiển vận hành cho Chủ đầu tư/Operator.

Dự án phát triển dựa trên đặc tả kỹ thuật chuẩn: [`.specify/spec_final.md`](.specify/spec_final.md), quy tắc nghiệp vụ đang chạy trong [`CLAUDE.md`](CLAUDE.md), tài liệu kiến trúc [`ARCHITECTURE.md`](ARCHITECTURE.md) và các sơ đồ trong [`DIagram/`](DIagram/) (bắt đầu từ [`Data Flow Diagram.md`](DIagram/Data%20Flow%20Diagram.md)).

---

## 1. Vấn đề & Giải pháp (Problem & Solution)

### Vấn đề thực tế
- **Khách mua (Buyer):** Mất quá nhiều thời gian tìm kiếm giữa hàng nghìn tin đăng ảo/tin trùng, liên tục bị làm phiền bởi các cuộc gọi môi giới không rõ nguồn gốc, dễ gặp rủi ro căn hộ đã có người khác xem hoặc bán mất ngay khi vừa đến nơi.
- **Chủ căn hộ (Owner):** Khó tiếp cận người mua thực, mất công nghe các cuộc gọi rác và phải tự trao đổi qua lại nhiều lần để hẹn lịch xem nhà phù hợp với thời gian biểu cá nhân.
- **Bất cập hiện tại:** Các sàn BĐS truyền thống chỉ đóng vai trò là "bảng tin đăng tĩnh", thiếu năng lực điều phối tự động (Orchestration), không có cơ chế giữ chỗ tạm thời bảo đảm trong giờ xem nhà và thiếu kiểm duyệt pháp lý quyền sở hữu.

### Giải pháp BookingBot
1. **AI Natural Language Extraction & Hybrid Scoring:** Trò chuyện tự nhiên qua Chat; AI tự động bóc tách nhu cầu và chấm điểm gợi ý căn hộ (Hard filter SQL + Soft score) kèm giải thích lý do đề xuất.
2. **Trải nghiệm Chat-Centric & Khách vãng lai (Guest Chat):** Người mua tìm căn, xem chi tiết, chọn / đổi giờ ngay trong khung chat (streaming). Khách mới có thể chat ngay mà **chưa cần tạo tài khoản**; khi chốt lịch mới cần SĐT + OTP (người mua không dùng email / mật khẩu). Trạng thái và lịch sử lịch xem (chủ căn xác nhận, từ chối, đổi giờ, hủy…) nằm ở trang **"Hoạt động"** nên không mất khi bắt đầu cuộc trò chuyện mới; lịch đã xác nhận có **mã QR vào cửa** cho bảo vệ / lễ tân quét.
3. **Xác thực Quyền sở hữu Sổ đỏ (Property Ownership Verification):** Chủ căn **đăng nhập bằng đúng SĐT chủ sở hữu ghi trên sổ**, nhập họ tên + mã số Sổ đỏ khớp dữ liệu của Chủ đầu tư (`property_ownership_verifications`) rồi nhập OTP gửi về SĐT đó → sổ **và tài khoản người bán** được xác thực ngay, không cần chờ duyệt (Chủ đầu tư không duyệt người bán, chỉ duyệt tin đăng). Đăng nhập bằng SĐT khác SĐT trên sổ → `NOT_OWNER_PHONE`, phải đi luồng hỗ trợ; nhập sai tên/mã sổ bị giới hạn 5 lần/giờ. Dữ liệu sổ có sẵn thông tin căn gốc (tòa, mã căn, diện tích, số phòng, tầng, hướng): khi đăng tin, form tự điền và khóa các thông tin này, người bán chỉ nhập giá, view, nội thất, mô tả và **ảnh tải từ máy**. Mỗi sổ gắn duy nhất 1 tin. Trường hợp không tự xác thực được (không nhận OTP, sổ bị khóa, sai lệch dữ liệu, bán thay có ủy quyền, đồng sở hữu, thừa kế, chưa có sổ, sổ bị người khác nhận) → người bán gửi **yêu cầu hỗ trợ** kèm giấy tờ (riêng tư) cho Chủ đầu tư.
4. **Owner Approval Workflow & Atomic Viewing Hold:** Người mua chọn lịch rảnh → khớp lịch trống của chủ nhà → gửi yêu cầu kèm **Deal ID** → Chủ nhà xác nhận → căn được **giữ cho buổi xem** trong khung giờ đó. Nhiều người có thể cùng xin một giờ (chủ căn chọn tiếp ai); PostgreSQL exclusion constraint bảo đảm **một chủ căn không bao giờ có 2 lịch đã xác nhận trùng giờ, kể cả ở 2 căn khác nhau** — xác nhận một người thì các yêu cầu trùng giờ khác tự đóng và AI báo họ kèm giờ khác.
5. **Năng lực Agentic & Trí nhớ đa lượt (Buyer Memory & Autonomous Follow-up):**
   - **Tự hoàn thành mục tiêu:** "Đặt giúp tôi căn 2PN Ocean Park rẻ nhất chiều Chủ nhật" → AI tự tìm căn, chọn khung giờ sớm nhất khớp lịch chủ nhà và tạo Deal.
   - **Ghi nhớ tiêu chí:** Ngân sách, hướng, tầng và khung giờ rảnh lưu tại `buyer_profiles` trong PostgreSQL, sang phiên chat mới không cần hỏi lại.
   - **Chăm sóc chủ động khi khách rời đi:** Job nền theo dõi định kỳ (`AGENT_FOLLOWUP_MINUTES`, mặc định 60 phút); nếu chủ nhà chưa phản hồi, từ chối, hoặc yêu cầu bị đóng vì chủ căn đã nhận người khác trùng giờ / căn đã bán, AI chủ động nhắn trong chat (kèm chuông 🔔 và bong bóng thông báo realtime) gợi ý khung giờ khác hoặc căn tương tự.
6. **Sau buổi xem:** chủ căn ghi nhận "Đã xem xong" / "Khách không đến" (quên thì được nhắc, quá 48h → `UNREPORTED`); người mua cho biết Quan tâm / Chưa phù hợp, hoặc báo không đồng ý kết quả → ca tranh chấp cho Chủ đầu tư. MVP kết thúc tại buổi xem: chưa có Purchase Request, chat trực tiếp Người mua ↔ Chủ căn hay thanh toán.
7. **Bảng điều khiển Chủ đầu tư (Operator Console) & Xử lý ngoại lệ:** Duyệt tin đăng (từ chối kèm lý do; người bán sửa ngay trong tab "Căn đang yêu cầu duyệt" và gửi lại), gỡ tin đang bán, giám sát / hủy lịch xem (kèm lý do), và hàng đợi ngoại lệ hiển thị bằng lời dễ đọc: chủ căn quá hạn chưa trả lời, AI chuyển cho người thật (kèm đoạn chat gần nhất), tranh chấp sau buổi xem, **hỗ trợ xác thực sổ đỏ** (mở khóa sổ, cập nhật SĐT chủ sở hữu, xác thực thủ công sau khi xem giấy tờ, thu hồi xác thực sai). Operator không duyệt từng lịch xem.
8. **Guardrails & vận hành AI:** che SĐT/email/CCCD ở cả đầu vào lẫn đầu ra, chặn prompt injection, chặn câu trả lời nói "đã xác nhận" khi chưa có, bịa mã căn, hướng dẫn đặt cọc / đàm phán / dự đoán giá; "giám khảo AI" model nhỏ duyệt các câu có rủi ro; streaming chỉ hiện câu đã kiểm tra. Rate limit chat theo tài khoản / IP. Dev có kill switch Trợ lý AI và dashboard số liệu tại trang `/dev`.

---

## 2. Công nghệ sử dụng (Tech Stack)

| Phân tầng | Công nghệ | Chi tiết |
|---|---|---|
| **AI Agent** | LangGraph, LangChain | Stateful multi-turn agent (12 tool), bóc tách nhu cầu, gọi tools và quản lý hội thoại; guardrails bằng code + giám khảo AI. Chọn provider bằng `LLM_PROVIDER`: **OpenAI** (`gpt-4o-mini`, mặc định trong code), **Google Gemini** (bản trên Render: `gemini-flash-lite-latest`, dự phòng `gemini-flash-latest`), **Claude** (`anthropic`, mặc định `claude-opus-5-5`; bản trên Cloud Run dùng `claude-sonnet-5-5`), **OpenRouter**, **Groq**. Model dự phòng có thể ở provider khác (`LLM_FALLBACK_PROVIDER`, vd. Claude → OpenRouter `google/gemini-3.8-flash`). Trace tùy chọn qua Langfuse / LangSmith. |
| **Backend** | FastAPI, Python 3.11+, Pydantic v2 | Router module hóa, chat streaming SSE, JWT + OTP (`OTP_PROVIDER=local` hoặc `firebase`), thông báo realtime qua SSE, background jobs trong tiến trình (hết hạn hold, nhắc lịch, hết hạn yêu cầu, follow-up, ghi nhận sau buổi xem). |
| **Database** | PostgreSQL 15+, SQLAlchemy, Alembic | Neon Serverless Postgres, 24 bảng (3 bảng post-MVP `purchase_requests` / `chats` / `messages` của spec chưa tạo), giao dịch ACID, exclusion constraint chống trùng lịch (theo căn và theo chủ căn), bảng `checkpoint*` lưu bộ nhớ hội thoại LangGraph; ảnh tải lên lưu trong `media_files` (chưa dùng S3). |
| **Frontend** | React 19, TypeScript, Vite 6, Tailwind CSS v4 | Web Responsive: Buyer (`/buyer/*`), Owner Portal (`/owner/*`), Operator Console (`/operator/*`), trang dev (`/dev`), trang quét mã QR (`/pass/:token`). React Router 7, TanStack Query, `openapi-fetch` với kiểu sinh từ OpenAPI (`npm run gen:api`). |
| **DevOps & Deploy** | Docker, GitHub Actions, Render / Cloud Run, Vercel, Neon | Backend chạy Docker trên Render (`render.yaml`) hoặc Google Cloud Run (`.github/workflows/deploy-cloudrun.yml`); Frontend SPA trên Vercel; Database trên Neon Postgres. CI chạy ruff + pytest. |
| **Testing & Eval** | Pytest, AI Golden Set | **340+ tests** unit/integration/concurrency/e2e; bộ đánh giá AI Golden Set 38 kịch bản (14 nhóm). |

---

## 3. Cấu trúc thư mục

```
bookingbot-mvp/
├── .github/workflows/      # ci.yml (ruff + pytest), cd.yml (image GHCR), deploy-cloudrun.yml (Cloud Run)
├── .specify/               # Đặc tả (spec_final.md), constitution, plan, tasks
├── alembic/                # Alembic database migrations
│   └── versions/           # Schema migrations (identity, deals, bookings, sổ đỏ, v.v.)
├── data/                   # Bộ dữ liệu hạt giống (Seed data)
│   ├── properties_seed.csv # Danh sách căn hộ mẫu Vinhomes
│   ├── users_seed.csv      # Danh sách tài khoản mẫu (Buyer, Owner, Operator)
│   ├── amenities_seed.csv  # Tiện ích nội khu
│   ├── projects_buildings_seed.csv           # Dự án & Tòa nhà
│   ├── property_ownership_verifications_seed.csv # Dữ liệu Sổ đỏ mẫu
│   └── demo_uploads/       # Ảnh demo cho tin đăng
├── DIagram/                # Sơ đồ thiết kế hệ thống
│   ├── Data Flow Diagram.md        # Luồng dữ liệu chi tiết giữa các tầng & tác nhân (sơ đồ chính)
│   ├── System Overview Diagram.md  # Kiến trúc tổng thể
│   ├── Agent Flow Diagram.md       # Vòng lặp agent, tool, guardrails, Owner xác nhận
│   ├── Current Journey Diagram.md  # Hành trình người mua: trước / sau BookingBot
│   └── Deployment Diagram.md       # Hạ tầng triển khai
├── eval/                   # AI Agent Evaluation
│   ├── golden_set.json     # Bộ kịch bản kiểm thử chuẩn vàng cho AI
│   ├── run_golden.py       # Script chạy đánh giá tự động và xuất báo cáo
│   └── manual_chat.py      # Chat thử với agent thật từ terminal
├── frontend/               # Giao diện Web (React 19 + Vite + Tailwind CSS)
│   ├── src/
│   │   ├── api/            # Client openapi-fetch + schema.d.ts sinh từ OpenAPI
│   │   ├── buyer/          # Người mua: chat với AI (guest chat, streaming), trang Hoạt động, mã QR vào cửa, sau buổi xem
│   │   ├── auth/           # Context xác thực & phân quyền (Buyer/Owner/Operator), Firebase Phone Auth
│   │   ├── components/     # Component UI dùng chung (chuông + bong bóng thông báo realtime…)
│   │   └── pages/
│   │       ├── owner/      # Căn của tôi (đăng tin + ảnh, chờ duyệt), lịch trống, yêu cầu xem, Xác thực sổ đỏ + yêu cầu hỗ trợ (/owner/verify)
│   │       ├── operator/   # Duyệt tin, hàng đợi ngoại lệ (hỗ trợ sổ đỏ, tranh chấp…), giám sát lịch xem
│   │       ├── dev/        # Trang /dev: kill switch Trợ lý AI + dashboard số liệu (ADMIN_API_TOKEN)
│   │       ├── PassCheckPage.tsx  # /pass/:token — bảo vệ / lễ tân quét mã QR
│   │       └── RoleSelectPage.tsx # Màn hình chọn vai trò người dùng ban đầu
│   └── vercel.json         # Cấu hình rewrite SPA cho Vercel
├── scripts/                # Utility scripts & hook ghi log AI
│   ├── run_api.py          # Script chạy server FastAPI tối ưu bộ nhớ hội thoại trên Windows/macOS
│   ├── start.sh            # Khởi động container: migration, seed một lần mỗi DB, chạy API
│   ├── ai_switch.py        # Kill switch Trợ lý AI (on / off / status / client-ip) qua API dev
│   ├── ai_traces.py        # Xem trace từng lượt chat (ai_turns)
│   ├── gcp-setup.sh        # Thiết lập Google Cloud một lần cho deploy Cloud Run
│   ├── log_antigravity.py  # Hook ghi log phiên làm việc cho Antigravity IDE
│   └── submit_log.py       # Tự động gửi log lên server chấm điểm
├── src/                    # Mã nguồn Backend (FastAPI + LangGraph)
│   ├── agents/             # Graph, Prompts, Tools, guardrails + giám khảo AI
│   ├── api/routers/        # Endpoints: auth, chat, properties, deals, bookings, owner, operator, escalations, media, notifications, admin
│   ├── core/               # Bảo mật, phân quyền (Actor), lỗi chuẩn hóa
│   ├── db/                 # Kết nối DB, Models (SQLAlchemy), seed + seed_once
│   ├── evaluation/         # Chấm golden set
│   ├── models/             # Pydantic schemas (Request/Response)
│   ├── services/           # Nghiệp vụ: booking, scheduling, hold, deal, ownership, viewing outcome, chat, notification, rate limit, trace…
│   ├── config.py           # Pydantic Settings & nạp biến môi trường
│   ├── jobs.py             # Background tasks (hết hạn hold / yêu cầu, nhắc lịch, escalation, follow-up, dọn trace)
│   └── main.py             # Khởi tạo FastAPI Application
├── tests/                  # Bộ kiểm thử Pytest (340+ tests)
│   ├── test_agents/        # Trí nhớ AI, năng lực agentic, guest chat, streaming, guardrails, trace
│   ├── test_api/           # API endpoints, xác thực sổ đỏ, phân quyền, kill switch, thông báo realtime
│   ├── test_db/            # Schema và các bước seed
│   ├── test_e2e/           # Toàn bộ luồng nghiệp vụ Core Demo Flow
│   ├── test_eval/          # Kiểm tra golden set
│   └── test_services/      # Concurrency (AC-08), xếp lịch, xếp hạng tìm kiếm, agent API
├── render.yaml             # Blueprint triển khai tự động lên Render
├── Dockerfile              # Containerfile chạy backend
└── requirements.txt        # Các thư viện Python phụ thuộc
```

---

## 4. Hướng dẫn chạy Local

### Yêu cầu hệ thống
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ (hoặc chuỗi kết nối Neon Postgres)

### Các bước khởi chạy

#### Bước 1: Thiết lập Backend
```bash
# 1. Tạo và kích hoạt môi trường ảo
python3 -m venv .venv
source .venv/bin/activate          # Trên Windows: .venv\Scripts\activate

# 2. Cài đặt các gói thư viện
pip install -r requirements.txt

# 3. Tạo file cấu hình môi trường
cp .env.example .env
```

Mở `.env` và thiết lập các biến quan trọng:
- `DATABASE_URL`: Đường dẫn kết nối PostgreSQL (ví dụ `postgresql+psycopg2://postgres:postgres@localhost:5432/bookingbot`).
- `JWT_SECRET`: Chuỗi bí mật bất kỳ để tạo token.
- **Cấu hình mô hình AI**:
  - Dùng Google Gemini: `LLM_PROVIDER=google` và `GOOGLE_API_KEY=AIza...` (khuyên dùng `MODEL_NAME=gemini-flash-latest`, dự phòng `MODEL_FALLBACK_NAME=gemini-flash-lite-latest`).
  - Dùng OpenAI: `LLM_PROVIDER=openai` và `OPENAI_API_KEY=sk-...` (mặc định `gpt-4o-mini`).
  - Dùng Claude: `LLM_PROVIDER=anthropic` và `ANTHROPIC_API_KEY=...` (mặc định `claude-opus-5-5`); có thể đặt model dự phòng ở provider khác, vd. `LLM_FALLBACK_PROVIDER=openrouter` + `MODEL_FALLBACK_NAME=google/gemini-3.8-flash`.
- **Bộ nhớ hội thoại AI** (`AGENT_MEMORY=postgres`, mặc định): lưu trong PostgreSQL (bảng `checkpoint*` của LangGraph).
- **OTP**: `OTP_PROVIDER=local` (mặc định, không gửi SMS) hoặc `firebase` (xem ghi chú ở mục 5).
- **API dev** (tùy chọn): `ADMIN_API_TOKEN` bật trang `/dev` (kill switch Trợ lý AI, dashboard) và `scripts/ai_switch.py`; để trống thì API dev tắt.

```bash
# 4. Khởi tạo cơ sở dữ liệu và nạp dữ liệu mẫu (giống scripts/start.sh khi khởi động container)
alembic upgrade head
python -m src.db.seed_once   # Chỉ chạy một lần mỗi DB; DB đã có SEED_VERSION hiện tại thì bỏ qua ngay

# 5. Khởi động Backend API
uvicorn src.main:app --reload --port 8000
# Hoặc chạy: python scripts/run_api.py (tự chọn event loop chuẩn trên Windows, duy trì bộ nhớ hội thoại)
```
API Documentation (Swagger UI) sẽ sẵn sàng tại: <http://localhost:8000/docs>

#### Bước 2: Thiết lập Frontend
Mở một cửa sổ Terminal mới:
```bash
cd frontend
npm install
npm run dev
```
Giao diện Web sẽ chạy tại: <http://localhost:5173> *(mặc định tự proxy sang API cổng 8000)*.

---

## 5. Tài khoản & Dữ liệu Demo kiểm thử

### Phân quyền các cổng Web
- **Khu Người mua (`/buyer/*`):** Người mới chat trực tiếp với AI; khi đặt lịch chỉ cần nhập SĐT nhận OTP. Người cũ đăng nhập tại `/buyer/login` chỉ bằng SĐT + OTP (không có email/mật khẩu) để quản lý lịch.
- **Cổng Chủ nhà (`/owner/*`):** Chỉ đăng nhập bằng SĐT + OTP tại `/login` (lần đầu tự tạo tài khoản). Xác thực sổ đỏ tại `/owner/verify` (tab "Xác thực sổ đỏ").
- **Cổng Chủ đầu tư (`/operator/login`):** Đăng nhập bằng Email + Mật khẩu quản trị (tách biệt hoàn toàn, không hiển thị trên trang người bán).
- **Trang dev (`/dev`):** nhập `ADMIN_API_TOKEN` để bật / tắt Trợ lý AI và xem dashboard số liệu. Không dành cho Operator.
- Mỗi khu giữ phiên đăng nhập riêng trong trình duyệt: có thể mở người bán và Chủ đầu tư ở hai tab cùng lúc.

### Danh sách tài khoản demo
Dữ liệu demo chỉ còn các tài khoản dưới đây (seed `--demo-accounts-only` đã chuyển mọi căn / sổ đỏ của người bán khác cho Tuấn và xóa người mua không phải demo). Chỉ tài khoản Chủ đầu tư có mật khẩu (mặc định `Password123!`); người mua và chủ căn đăng nhập bằng SĐT + OTP. **SĐT demo không bao giờ nhận SMS: mã luôn là `123456` và được điền sẵn trên màn hình.** Seed `--ensure-all-cases` tạo sẵn đủ mọi trạng thái cho từng vai trò (lịch xem mọi trạng thái, tranh chấp, ca của Operator, tin chờ duyệt / bị từ chối / đã bán / tạm ngừng, hỗ trợ sổ đỏ).

| Vai trò | Thông tin đăng nhập | Chức năng kiểm thử nổi bật |
|---|---|---|
| **Người mua (Buyer)** | SĐT: `0901111222` (Nguyễn Văn An), `0902222333` (Trần Thị Bình) | Chat tìm nhà, đặt / đổi / hủy lịch, trang Hoạt động, mã QR vào cửa, phản hồi sau buổi xem. |
| **Chủ căn hộ (Owner)** | SĐT: `0912345678` (Hoàng Thị Lan: 8 sổ đỏ đã xác thực)<br>SĐT: `0918765432` (Phạm Minh Tuấn: sở hữu mọi căn và sổ đỏ còn lại) | Xác thực sổ đỏ, đăng tin kèm ảnh, xác nhận / từ chối (đề xuất giờ khác) lịch xem, quản lý khung giờ rảnh, ghi nhận sau buổi xem, đánh dấu đã bán. |
| **Chủ đầu tư (Operator)** | `operator@vinhomes.vn` (Nguyễn Quang Dũng), `coordinator@vinhomes.vn` (Trần Thu Hà) | Duyệt / gỡ tin đăng, giám sát lịch xem, xử lý hàng đợi ngoại lệ (hỗ trợ sổ đỏ, tranh chấp, chủ căn chưa trả lời, AI chuyển người thật). |

### Dữ liệu Sổ đỏ mẫu (`property_ownership_verifications_seed.csv`)
- **Đã xác thực sẵn:** Sổ của Lan và Tuấn; mọi tin đăng mẫu đều gắn một sổ đỏ đã xác thực. Mỗi sổ có sẵn thông tin căn (tòa, mã căn, diện tích, số phòng, tầng, hướng), nên khi "Đăng tin bán" form tự điền và khóa các thông tin này.
- **Chưa xác thực (thử luồng xác thực):** Mã sổ **`SD-2017-0332211`**, người đứng tên **Phạm Minh Tuấn** — đăng nhập bằng SĐT của Tuấn rồi nhập họ tên + mã sổ để nhận OTP. Đăng nhập bằng SĐT khác (kể cả biết tên + mã sổ) sẽ bị từ chối `NOT_OWNER_PHONE`.
- **Sổ bị khóa:** **`SD-2015-0110022`** (Tuấn, bị khóa do nhập sai OTP quá 5 lần) đã có sẵn yêu cầu hỗ trợ — dùng để thử các thao tác của Chủ đầu tư trong tab "Ngoại lệ" (mở khóa, cập nhật SĐT, xác thực thủ công, thu hồi).

*Lưu ý — mã OTP có hai chế độ (`OTP_PROVIDER`):*
- *`local` (mặc định): hệ thống tự sinh mã, **không gửi SMS**; ngoài production mã hiện ngay trên màn hình (hoặc bật `OTP_EXPOSE_CODE=true`).*
- *`firebase`: **Firebase Phone Auth** tự sinh, gửi SMS và kiểm tra mã ngay trên trình duyệt (kèm reCAPTCHA ẩn); backend chỉ xác minh Firebase ID token (chữ ký Google, đúng project, đúng SĐT, vừa nhập mã trong `OTP_TTL_SECONDS`). Cần `FIREBASE_PROJECT_ID` + `FIREBASE_WEB_API_KEY`, bật Sign-in method "Phone" và thêm domain frontend vào Authorized domains. Áp dụng cho cả đăng nhập lẫn OTP xác thực sổ đỏ. Các SĐT demo (`DEMO_PHONES`) không đi qua Firebase: mã cố định `123456`, không tốn SMS, không tính rate limit.*
- *Đăng nhập chỉ nhận số di động Việt Nam (10 số, đầu 03/05/07/08/09).*

---

## 6. Các câu truy vấn mẫu (Sample Queries)

Dưới đây là các câu truy vấn / prompt mẫu đại diện cho 5 kịch bản tương tác chính của Người mua với AI Agent:

### 1. Tìm kiếm căn hộ theo nhu cầu tự nhiên
- **Tìm kiếm cơ bản:**
  > *"Tôi cần tìm căn hộ 2 phòng ngủ ở Vinhomes Ocean Park, tài chính khoảng 3 đến 3,5 tỷ."*
- **Tìm kiếm đa tiêu chí nâng cao (khoảng tầng, hướng, phân khu):**
  > *"Tìm cho tôi căn 3 phòng ngủ tại Vinhomes Smart City, phân khu Sapphire hoặc Tonkin, ban công hướng Đông Nam, tầng trung từ 10 đến 20, giá dưới 5 tỷ."*
- **Tìm kiếm theo tiện ích nội khu:**
  > *"Có căn studio hoặc 1PN nào ở Grand Park gần công viên ánh sáng 36ha và trường Vinschool không?"*

### 2. Xem chi tiết căn hộ & Giải thích đề xuất
- **Xem thông số và pháp lý:**
  > *"Cho tôi xem chi tiết căn S1.08-2410: diện tích thông thủy, giá bán, nội thất bàn giao và căn này đã có Sổ đỏ chưa?"*
- **So sánh và giải thích:**
  > *"Tại sao bạn lại đề xuất căn S1.08-2410 này cho tôi? So với căn S2.05 thì căn nào tối ưu hơn về diện tích và tầm view?"*

### 3. Đặt lịch xem nhà thông minh (Goal-Driven Booking)
- **Tự động khớp lịch sớm nhất (Ủy quyền toàn bộ cho Agent):**
  > *"Đặt giúp tôi căn 2PN giá tốt nhất Ocean Park vào chiều Chủ nhật tuần này, khung giờ nào cũng được."*
  *(Agent tự bóc tách: tìm căn phù hợp nhất ➔ kiểm tra lịch trống chủ nhà ➔ chọn giờ sớm nhất ➔ tạo Deal ID và gửi yêu cầu xem).*
- **Chỉ định khoảng thời gian rảnh:**
  > *"Tôi ưng căn S1.08-2410 rồi, thứ Bảy này tôi rảnh từ 9h đến 11h sáng, hãy kiểm tra lịch chủ nhà và xếp lịch xem giúp tôi."*

### 4. Dời lịch hoặc Hủy lịch hẹn
- **Dời lịch khi chủ nhà chưa duyệt:**
  > *"Tôi có việc bận đột xuất vào chiều Chủ nhật, dời lịch xem căn S1.08 sang 15h chiều thứ Hai giúp tôi nhé."*
- **Hủy lịch hẹn:**
  > *"Hủy yêu cầu xem căn S2.05 của tôi vào sáng mai đi, tôi đã chọn được căn khác rồi."*

### 5. Yêu cầu chuyển cho người thật hỗ trợ (Human Escalation)
- **Khiếu nại sự cố buổi xem nhà:**
  > *"Tôi đã đến điểm hẹn căn S1.08 lúc 10h nhưng chủ nhà không có mặt và không nghe máy, hãy chuyển cho nhân viên hỗ trợ tôi ngay."*
- **Tư vấn chuyên sâu về tài chính / ngân hàng:**
  > *"Tôi cần gặp trực tiếp chuyên viên của chủ đầu tư để hỏi về gói vay 0% lãi suất và thủ tục sang tên sổ đỏ cho căn này."*

---

## 7. Kiểm thử & Đánh giá chất lượng

Hệ thống được trang bị bộ kiểm thử tự động toàn diện:

```bash
# Chạy toàn bộ 340+ unit, integration, concurrency & agentic tests (cần PostgreSQL)
pytest tests -q

# Chạy riêng kiểm thử luồng Demo hoàn chỉnh (Core Demo Flow)
pytest tests/test_e2e/test_core_demo_flow.py -v

# Kiểm tra xử lý xung đột đồng thời (Anti-Double-Booking / AC-08)
pytest tests/test_services/test_concurrency.py -v

# Kiểm tra năng lực Agentic & Guest Chat của AI
pytest tests/test_agents/test_agentic.py tests/test_agents/test_guest_chat.py -v

# Chạy bộ đánh giá AI Golden Set (38 kịch bản, 14 nhóm, với model thực tế)
python eval/run_golden.py
```
*Kết quả đánh giá AI sẽ được tự động ghi lại tại [`eval/results/golden_report.md`](eval/results/golden_report.md).*

### Trace AI cho dev

Mỗi lượt chat với Trợ lý AI (cả khách chưa đăng nhập và lượt bị lỗi) được ghi vào bảng `ai_turns`: câu hỏi, kết quả, từng lần gọi model / công cụ kèm thời gian và token. Mã trace (`trace_id`) có trong phản hồi chat và trong log server khi một lượt bị lỗi. Phần này chỉ dành cho đội phát triển.

```bash
python scripts/ai_traces.py recent -n 20            # các lượt gần đây (--errors: chỉ lượt lỗi, --guests: chỉ khách)
python scripts/ai_traces.py show <trace_id>         # chi tiết một lượt: từng bước, tin nhắn, tham số và kết quả công cụ
python scripts/ai_traces.py stats --days 7          # tỉ lệ lỗi, thời gian p50/p95, token, công cụ hay lỗi
```
Trace cũ tự xóa sau `AI_TRACE_RETENTION_DAYS` ngày (mặc định 180).

Kill switch Trợ lý AI (cũng có trên trang `/dev`): khi tắt, mọi endpoint chat trả 503 `AI_DISABLED` không gọi model, khung chat người mua báo bảo trì kèm số tổng đài; đặt lịch / xác nhận lịch vẫn chạy.

```bash
python scripts/ai_switch.py status
python scripts/ai_switch.py off --reason "Model trả lời sai, đang kiểm tra"
python scripts/ai_switch.py on
```

---

## 8. Hướng dẫn Triển khai Production (Vercel + Render + Neon)

Hệ thống được thiết kế theo mô hình phân tán tối ưu chi phí (hoàn toàn chạy được trên các gói Free Tier):
- **PostgreSQL Database:** Lưu trữ trên **Neon Serverless Postgres**.
- **Backend API & AI Engine:** Đóng gói Docker chạy trên **Render Web Service** (đáp ứng các tác vụ chạy ngầm, duy trì bộ nhớ hội thoại và giữ kết nối lâu dài).
- **Frontend SPA:** Triển khai trên **Vercel Edge Network**.

### Các bước triển khai:

1. **Cơ sở dữ liệu (Neon):**
   - Tạo Project mới trên Neon Console, lấy chuỗi kết nối (`postgresql://...neon.tech/neondb?sslmode=require`).
2. **Backend API (Render):**
   - Đăng nhập Render Dashboard → New → Blueprint → Trỏ tới repository (sử dụng file [`render.yaml`](render.yaml)).
   - Điền các biến môi trường: `DATABASE_URL` (từ Neon), `GOOGLE_API_KEY` hoặc `OPENAI_API_KEY`, tạm để trống `CORS_ORIGINS`.
   - File [`scripts/start.sh`](scripts/start.sh) sẽ tự động chạy migration rồi `python -m src.db.seed_once`: seed demo chỉ chạy **một lần mỗi DB** (DB đã có `seed.version` = `SEED_VERSION` thì bỏ qua ngay; đổi dữ liệu demo thì tăng `SEED_VERSION`). `SEED_DEMO_DATA=false` bỏ seed cho DB thật. Job nền hằng ngày giữ lịch trống demo 14 ngày tới.
   - Ảnh người bán tải lên được lưu trong PostgreSQL (bảng `media_files`) nên không mất khi Render khởi động lại; backend tự lấy địa chỉ công khai từ `RENDER_EXTERNAL_URL` để web trên Vercel hiển thị được ảnh.
   - Ghi lại URL của Backend (ví dụ: `https://bookingbot-api.onrender.com`).
3. **Frontend (Vercel):**
   - Đăng nhập Vercel → New Project → Chọn repository.
   - Thiết lập **Root Directory: `frontend`**.
   - Thêm biến môi trường: `VITE_API_URL` = URL Backend ở Bước 2.
   - Bấm Deploy và lưu lại tên miền (ví dụ: `https://bookingbot.vercel.app`).
4. **Cập nhật CORS:**
   - Quay lại Render, cập nhật biến `CORS_ORIGINS` = URL của trang web trên Vercel (không có dấu `/` ở cuối). Service sẽ tự động cập nhật.
5. **Kiểm tra sau deploy:** đặt `ADMIN_API_TOKEN` rồi chạy `python scripts/ai_switch.py client-ip` để chắc IP khách (dùng cho rate limit) được lấy đúng qua proxy (`TRUSTED_PROXY_HOPS` / `CLIENT_IP_HEADER`).

### Phương án khác: Google Cloud Run
Workflow [`.github/workflows/deploy-cloudrun.yml`](.github/workflows/deploy-cloudrun.yml) build cùng Dockerfile, chạy migration + seed bằng một Cloud Run job mỗi lần deploy (`sh scripts/start.sh setup`, service khởi động với `DB_SETUP_ON_START=false`) rồi deploy service (1 instance, vì job nền chạy trong tiến trình). Bản này dùng Claude (`claude-sonnet-5-5`, dự phòng OpenRouter `google/gemini-3.8-flash`), OTP thật qua Firebase Phone Auth và secret từ Secret Manager. Thiết lập GCP một lần bằng [`scripts/gcp-setup.sh`](scripts/gcp-setup.sh); workflow không chạy khi chưa có các biến `GCP_*` của repository.

---

## 9. AI Usage Logging (Dành cho Học viên VinUni AI20K)

Dự án tích hợp sẵn hệ thống hook tự động ghi nhận nhật ký sử dụng AI vào `.ai-log/session.jsonl` và tự động gửi về máy chủ chấm điểm ở bước `git push`.

Cài đặt hook sau khi clone repo:
```bash
# Linux / macOS / Git Bash
bash scripts/setup_hooks.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
```

---

## 10. Giấy phép (License)

Dự án được phân phối dưới giấy phép [MIT License](LICENSE).

