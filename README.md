# BookingBot AI Agent · Trợ lý Đặt lịch Xem nhà & Giữ căn Vinhomes

> **BookingBot AI Agent** là giải pháp AI-first chuyên biệt cho thị trường Bất động sản đại đô thị Vinhomes: Tự động trích xuất nhu cầu bằng ngôn ngữ tự nhiên, gợi ý căn hộ chính xác qua cơ chế lọc lai (Hybrid SQL + Soft Score), tự động điều phối lịch xem nhà giữa Người mua và Chủ nhà, bảo vệ giao dịch bằng cơ chế **Viewing Hold nguyên tử** (tạm khóa căn chống trùng lịch), xác thực chủ sở hữu qua **Sổ đỏ + OTP** và tích hợp bảng điều khiển vận hành cho Chủ đầu tư/Operator.

Dự án phát triển dựa trên đặc tả kỹ thuật chuẩn: [`.specify/spec_final.md`](.specify/spec_final.md), tài liệu kiến trúc [`ARCHITECTURE.md`](ARCHITECTURE.md) và sơ đồ luồng dữ liệu [`DIagram/Data Flow Diagram.md`](DIagram/Data%20Flow%20Diagram.md).

---

## 1. Vấn đề & Giải pháp (Problem & Solution)

### Vấn đề thực tế
- **Khách mua (Buyer):** Mất quá nhiều thời gian tìm kiếm giữa hàng nghìn tin đăng ảo/tin trùng, liên tục bị làm phiền bởi các cuộc gọi môi giới không rõ nguồn gốc, dễ gặp rủi ro căn hộ đã có người khác xem hoặc bán mất ngay khi vừa đến nơi.
- **Chủ căn hộ (Owner):** Khó tiếp cận người mua thực, mất công nghe các cuộc gọi rác và phải tự trao đổi qua lại nhiều lần để hẹn lịch xem nhà phù hợp với thời gian biểu cá nhân.
- **Bất cập hiện tại:** Các sàn BĐS truyền thống chỉ đóng vai trò là "bảng tin đăng tĩnh", thiếu năng lực điều phối tự động (Orchestration), không có cơ chế giữ chỗ tạm thời bảo đảm trong giờ xem nhà và thiếu kiểm duyệt pháp lý quyền sở hữu.

### Giải pháp BookingBot
1. **AI Natural Language Extraction & Hybrid Scoring:** Trò chuyện tự nhiên qua Chat; AI tự động bóc tách nhu cầu và chấm điểm gợi ý căn hộ (Hard filter SQL + Soft score) kèm giải thích lý do đề xuất.
2. **Trải nghiệm Chat-Centric & Khách vãng lai (Guest Chat):** Người mua tìm căn, xem chi tiết, chọn / đổi giờ ngay trong khung chat (streaming). Khách mới có thể chat ngay mà **chưa cần tạo tài khoản**; khi chốt lịch mới cần SĐT + OTP (người mua không dùng email / mật khẩu). Trạng thái và lịch sử lịch xem (chủ căn xác nhận, từ chối, đổi giờ, hủy…) nằm ở trang **"Hoạt động"** nên không mất khi bắt đầu cuộc trò chuyện mới; lịch đã xác nhận có **mã QR vào cửa** cho bảo vệ / lễ tân quét.
3. **Xác thực Quyền sở hữu Sổ đỏ (Property Ownership Verification):** Chủ căn nhập họ tên + mã số Sổ đỏ khớp dữ liệu của Chủ đầu tư (`property_ownership_verifications`) rồi nhập OTP gửi về SĐT chủ sở hữu trên sổ → sổ **và tài khoản người bán** được xác thực ngay, không cần chờ duyệt. Dữ liệu sổ có sẵn thông tin căn gốc (tòa, mã căn, diện tích, số phòng, tầng, hướng): khi đăng tin, form tự điền và khóa các thông tin này, người bán chỉ nhập giá, view, nội thất, mô tả và **ảnh tải từ máy**. Mỗi sổ gắn duy nhất 1 tin. Trường hợp không tự xác thực được (không nhận OTP, sổ bị khóa, sai lệch dữ liệu, bán thay có ủy quyền, đồng sở hữu, thừa kế, chưa có sổ, sổ bị người khác nhận) → người bán gửi **yêu cầu hỗ trợ** kèm giấy tờ (riêng tư) cho Chủ đầu tư.
4. **Owner Approval Workflow & Atomic Viewing Hold:** Người mua chọn lịch rảnh → khớp lịch trống của chủ nhà → gửi yêu cầu kèm **Deal ID** → Chủ nhà xác nhận → căn được **giữ cho buổi xem** trong khung giờ đó. Nhiều người có thể cùng xin một giờ (chủ căn chọn tiếp ai); PostgreSQL exclusion constraint bảo đảm **một chủ căn không bao giờ có 2 lịch đã xác nhận trùng giờ, kể cả ở 2 căn khác nhau** — xác nhận một người thì các yêu cầu trùng giờ khác tự đóng và AI báo họ kèm giờ khác.
5. **Năng lực Agentic & Trí nhớ đa lượt (Buyer Memory & Autonomous Follow-up):**
   - **Tự hoàn thành mục tiêu:** "Đặt giúp tôi căn 2PN Ocean Park rẻ nhất chiều Chủ nhật" → AI tự tìm căn, chọn khung giờ sớm nhất khớp lịch chủ nhà và tạo Deal.
   - **Ghi nhớ tiêu chí:** Ngân sách, hướng, tầng và khung giờ rảnh lưu tại `buyer_profiles` trong PostgreSQL, sang phiên chat mới không cần hỏi lại.
   - **Chăm sóc chủ động khi khách rời đi:** Job nền theo dõi định kỳ (`AGENT_FOLLOWUP_MINUTES`, mặc định 60 phút); nếu chủ nhà chưa phản hồi hoặc từ chối, AI chủ động gửi thông báo qua chuông 🔔 gợi ý khung giờ khác hoặc căn tương tự.
6. **Bảng điều khiển Chủ đầu tư (Operator Console) & Xử lý ngoại lệ:** Duyệt tin đăng (từ chối kèm lý do; người bán sửa ngay trong tab "Căn đang yêu cầu duyệt" và gửi lại), giám sát lịch xem, và hàng đợi ngoại lệ: chủ căn quá hạn 24h chưa trả lời, AI chuyển cho người thật, **hỗ trợ xác thực sổ đỏ** (mở khóa sổ, cập nhật SĐT chủ sở hữu, xác thực thủ công sau khi xem giấy tờ, thu hồi xác thực sai).

---

## 2. Công nghệ sử dụng (Tech Stack)

| Phân tầng | Công nghệ | Chi tiết |
|---|---|---|
| **AI Agent** | LangGraph, LangChain | Stateful multi-turn agent, bóc tách nhu cầu, gọi tools và quản lý hội thoại. Hỗ trợ cả **Google Gemini** (`gemini-flash-latest`, tự chuyển sang `gemini-flash-lite-latest` khi lỗi / quá tải — cấu hình của bản demo trên Render) và **OpenAI** (`gpt-4o-mini`, mặc định trong code). |
| **Backend** | FastAPI, Python 3.11+, Pydantic v2 | Kiến trúc Router module hóa, Async I/O, JWT Auth & Phone OTP, Background jobs (hết hạn hold, follow-up, nhắc lịch). |
| **Database** | PostgreSQL 15+, SQLAlchemy, Alembic | Neon Serverless Postgres, giao dịch ACID, Exclusion locks chống trùng lịch, bảng `checkpoint*` lưu bộ nhớ hội thoại LangGraph. |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS v4 | Web Responsive chia 3 cổng: Buyer Portal (`/buyer/*`), Owner Portal (`/owner/*`), Operator Console (`/operator/*`). Tích hợp React Router 7 và TanStack Query. |
| **DevOps & Deploy** | Docker, Render, Vercel, Neon | Backend chạy Docker trên Render; Frontend SPA trên Vercel; Database trên Neon Postgres. |
| **Testing & Eval** | Pytest, AI Golden Set | **230+ tests** unit/integration/concurrency; bộ đánh giá AI Golden Set ≥20 kịch bản thực tế. |

---

## 3. Cấu trúc thư mục

```
P-001/
├── alembic/                # Alembic database migrations
│   └── versions/           # Schema migrations (identity, deals, bookings, sổ đỏ, v.v.)
├── data/                   # Bộ dữ liệu hạt giống (Seed data)
│   ├── properties_seed.csv # Danh sách căn hộ mẫu Vinhomes
│   ├── users_seed.csv      # Danh sách tài khoản mẫu (Buyer, Owner, Operator)
│   ├── amenities_seed.csv  # Tiện ích nội khu
│   ├── projects_buildings_seed.csv           # Dự án & Tòa nhà
│   └── property_ownership_verifications_seed.csv # Dữ liệu Sổ đỏ mẫu
├── DIagram/                # Sơ đồ thiết kế hệ thống
│   ├── Data Flow Diagram.md # Sơ đồ luồng dữ liệu chi tiết giữa các tầng & tác nhân
│   ├── Agent Flow Diagram.md
│   └── System Overview Diagram.md
├── eval/                   # AI Agent Evaluation
│   ├── golden_set.json     # Bộ kịch bản kiểm thử chuẩn vàng cho AI
│   └── run_golden.py       # Script chạy đánh giá tự động và xuất báo cáo
├── frontend/               # Giao diện Web (React 19 + Vite + Tailwind CSS)
│   ├── src/
│   │   ├── buyer/          # Người mua: chat với AI (guest chat, streaming), trang Hoạt động, mã QR vào cửa
│   │   ├── auth/           # Context xác thực & phân quyền (Buyer/Owner/Operator)
│   │   ├── components/     # Component UI dùng chung
│   │   └── pages/
│   │       ├── owner/      # Căn của tôi (đăng tin + ảnh, chờ duyệt), yêu cầu xem, Xác thực sổ đỏ + yêu cầu hỗ trợ (/owner/verify)
│   │       ├── operator/   # Duyệt tin, hàng đợi ngoại lệ (kể cả hỗ trợ xác thực sổ đỏ), giám sát lịch xem
│   │       └── RoleSelectPage.tsx # Màn hình chọn vai trò người dùng ban đầu
│   └── vercel.json         # Cấu hình rewrite SPA cho Vercel
├── scripts/                # Utility scripts & hook ghi log AI
│   ├── run_api.py          # Script chạy server FastAPI tối ưu bộ nhớ hội thoại trên Windows/macOS
│   ├── start.sh            # Script khởi động tự động cho production container
│   ├── log_antigravity.py  # Hook ghi log phiên làm việc cho Antigravity IDE
│   └── submit_log.py       # Tự động gửi log lên server chấm điểm
├── src/                    # Mã nguồn Backend (FastAPI + LangGraph)
│   ├── agents/             # Định nghĩa Graph, Prompts và Tools của Agent
│   ├── api/routers/        # Endpoints: auth, chat, properties, deals, bookings, operator, owner
│   ├── core/               # Bảo mật, phân quyền, mã hóa OTP
│   ├── db/                 # Kết nối DB, Models (SQLAlchemy), Seed runner
│   ├── models/             # Pydantic schemas (Request/Response)
│   ├── services/           # Nghiệp vụ: booking, scheduling, hold, ownership, buyer memory, agent follow-up
│   ├── config.py           # Pydantic Settings & nạp biến môi trường
│   ├── jobs.py             # Background tasks (hết hạn hold, nhắc lịch, agent follow-up)
│   └── main.py             # Khởi tạo FastAPI Application
├── tests/                  # Bộ kiểm thử Pytest (230+ tests)
│   ├── test_agents/        # Kiểm tra trí nhớ AI, năng lực agentic, guest chat
│   ├── test_api/           # Test API endpoints, xác thực sổ đỏ, phân quyền
│   ├── test_e2e/           # Test toàn bộ luồng nghiệp vụ Core Demo Flow
│   └── test_services/      # Test concurrency (AC-08) và thuật toán xếp lịch
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
- **Bộ nhớ hội thoại AI** (`AGENT_MEMORY=postgres`, mặc định): lưu trong PostgreSQL (bảng `checkpoint*` của LangGraph).

```bash
# 4. Khởi tạo cơ sở dữ liệu và nạp dữ liệu mẫu
alembic upgrade head
python -m src.db.seed   # Nếu DB đã có từ trước, chạy: python -m src.db.seed --if-empty --ensure-red-books --ensure-listings --ensure-seller-story --ensure-red-book-units --ensure-sellers-verified --ensure-photos --ensure-slots 7 --ensure-requests --ensure-showcase

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
- Mỗi khu giữ phiên đăng nhập riêng trong trình duyệt: có thể mở người bán và Chủ đầu tư ở hai tab cùng lúc.

### Danh sách tài khoản demo
Chỉ tài khoản Chủ đầu tư có mật khẩu (mặc định `Password123!`); người mua và chủ căn đăng nhập bằng SĐT + OTP.

| Vai trò | Thông tin đăng nhập | Chức năng kiểm thử nổi bật |
|---|---|---|
| **Người mua (Buyer)** | SĐT: `0901111222` (An), `0902222333` (Bình) | Chat tìm nhà, đặt / đổi lịch, trang Hoạt động, mã QR vào cửa. |
| **Chủ căn hộ (Owner)** | SĐT: `0918765432` (Tuấn)<br>SĐT: `0912345678` (Lan: 8 sổ đỏ, 4 căn đang bán) | Xác thực sổ đỏ, đăng tin kèm ảnh, xác nhận / từ chối lịch xem, quản lý khung giờ rảnh. |
| **Chủ đầu tư (Operator)** | `operator@vinhomes.vn` | Duyệt tin đăng, giám sát lịch xem, xử lý hàng đợi ngoại lệ (kể cả hỗ trợ xác thực sổ đỏ). |

### Dữ liệu Sổ đỏ mẫu (`property_ownership_verifications_seed.csv`)
- **Đã xác thực sẵn:** Sổ của Tuấn và Lan; mọi tin đăng mẫu đều gắn một sổ đỏ đã xác thực. Mỗi sổ có sẵn thông tin căn (tòa, mã căn, diện tích, số phòng, tầng, hướng), nên khi "Đăng tin bán" form tự điền.
- **Chưa xác thực (Dùng để test tính năng mới):** Chủ sở hữu **Nguyễn Thị Hương** · Mã sổ **`SD-2017-0332211`** (dùng SĐT người bán mới để trải nghiệm luồng xác thực nhận OTP qua sổ).
- **Sổ bị khóa:** Sổ của **Trần Văn Đức** · **`SD-2015-0110022`** (bị khóa do nhập sai OTP quá 5 lần) — dùng để thử luồng "Gửi yêu cầu mở khóa" và các thao tác của Chủ đầu tư trong tab "Ngoại lệ".

*Lưu ý: Khi chưa cấu hình SMS Gateway ngoài production, mã OTP sẽ hiển thị trực tiếp trên giao diện màn hình (hoặc bật `OTP_EXPOSE_CODE=true` trong `.env`).*

---

## 6. Kiểm thử & Đánh giá chất lượng

Hệ thống được trang bị bộ kiểm thử tự động toàn diện:

```bash
# Chạy toàn bộ 230+ unit, integration, concurrency & agentic tests
pytest tests -q

# Chạy riêng kiểm thử luồng Demo hoàn chỉnh (Core Demo Flow)
pytest tests/test_e2e/test_core_demo_flow.py -v

# Kiểm tra xử lý xung đột đồng thời (Anti-Double-Booking / AC-08)
pytest tests/test_services/test_concurrency.py -v

# Kiểm tra năng lực Agentic & Guest Chat của AI
pytest tests/test_agents/test_agentic.py tests/test_agents/test_guest_chat.py -v

# Chạy bộ đánh giá AI Golden Set (≥20 kịch bản đánh giá với model thực tế)
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

---

## 7. Hướng dẫn Triển khai Production (Vercel + Render + Neon)

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
   - File [`scripts/start.sh`](scripts/start.sh) sẽ tự động chạy migration, nạp seed ban đầu (kèm sổ đỏ demo và thông tin căn trên sổ), xác thực người bán đã có sổ và mở các khung giờ xem trống trong 7 ngày tới.
   - Ảnh người bán tải lên được lưu trong PostgreSQL (bảng `media_files`) nên không mất khi Render khởi động lại; backend tự lấy địa chỉ công khai từ `RENDER_EXTERNAL_URL` để web trên Vercel hiển thị được ảnh.
   - Ghi lại URL của Backend (ví dụ: `https://bookingbot-api.onrender.com`).
3. **Frontend (Vercel):**
   - Đăng nhập Vercel → New Project → Chọn repository.
   - Thiết lập **Root Directory: `frontend`**.
   - Thêm biến môi trường: `VITE_API_URL` = URL Backend ở Bước 2.
   - Bấm Deploy và lưu lại tên miền (ví dụ: `https://bookingbot.vercel.app`).
4. **Cập nhật CORS:**
   - Quay lại Render, cập nhật biến `CORS_ORIGINS` = URL của trang web trên Vercel (không có dấu `/` ở cuối). Service sẽ tự động cập nhật.

---

## 8. AI Usage Logging (Dành cho Học viên VinUni AI20K)

Dự án tích hợp sẵn hệ thống hook tự động ghi nhận nhật ký sử dụng AI vào `.ai-log/session.jsonl` và tự động gửi về máy chủ chấm điểm ở bước `git push`.

Cài đặt hook sau khi clone repo:
```bash
# Linux / macOS / Git Bash
bash scripts/setup_hooks.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
```

---

## 9. Giấy phép (License)

Dự án được phân phối dưới giấy phép [MIT License](LICENSE).
