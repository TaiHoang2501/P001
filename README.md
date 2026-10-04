# BookingBot AI Agent · Trợ lý Đặt lịch Xem nhà & Giữ căn Vinhomes

> **BookingBot AI Agent** là giải pháp AI-first chuyên biệt cho thị trường Bất động sản đại đô thị Vinhomes: Tự động trích xuất nhu cầu bằng ngôn ngữ tự nhiên, gợi ý căn hộ chính xác qua cơ chế lọc lai (Hybrid SQL + Soft Score), tự động điều phối lịch xem nhà giữa Người mua và Chủ nhà, bảo vệ giao dịch bằng cơ chế **Viewing Hold nguyên tử** (tạm khóa căn chống trùng lịch) và tích hợp bảng điều khiển vận hành cho Chủ đầu tư/Operator.

Dự án phát triển dựa trên đặc tả kỹ thuật chuẩn: [`.specify/spec_final.md`](.specify/spec_final.md) và tài liệu kiến trúc [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 1. Vấn đề & Giải pháp (Problem & Solution)

### Vấn đề thực tế
- **Khách mua (Buyer):** Mất quá nhiều thời gian tìm kiếm giữa hàng nghìn tin đăng ảo/tin trùng, liên tục bị làm phiền bởi các cuộc gọi môi giới không rõ nguồn gốc, dễ gặp rủi ro căn hộ đã có người khác xem hoặc bán mất ngay khi vừa đến nơi.
- **Chủ căn hộ (Owner):** Khó tiếp cận người mua thực, mất công nghe các cuộc gọi rác và phải tự trao đổi qua lại nhiều lần để hẹn lịch xem nhà phù hợp với thời gian biểu cá nhân.
- **Bất cập hiện tại:** Các sàn BĐS truyền thống chỉ đóng vai trò là "bảng tin đăng tĩnh", thiếu năng lực điều phối tự động (Orchestration) và không có cơ chế giữ chỗ tạm thời bảo đảm trong giờ xem nhà.

### Giải pháp BookingBot
1. **AI Natural Language Extraction:** Trò chuyện tự nhiên qua Chat; AI tự động bóc tách thành tiêu chí tìm kiếm chuẩn hóa (ngân sách, số phòng ngủ, diện tích, phân khu, khoảng tầng, hướng ban công).
2. **Hybrid Recommendation Engine:** Kết hợp lọc cứng SQL (Hard filter) và chấm điểm mềm (Soft scoring) kèm giải thích chi tiết lý do đề xuất.
3. **Owner Approval Workflow:** Người mua chọn lịch rảnh → hệ thống khớp với lịch trống của chủ nhà → gửi yêu cầu kèm **Deal ID** → Chủ nhà xác nhận (`Approve`).
4. **Atomic Viewing Hold (Chống trùng lịch):** Khóa giữ căn độc quyền trong khung giờ hẹn xem nhà bằng cơ chế khóa cơ sở dữ liệu (PostgreSQL exclusion constraint), loại bỏ triệt để hiện tượng Double-Booking.
5. **Automated Reminders:** Tự động gửi thông báo và nhắc lịch trước giờ xem (T-24h và T-2h).
6. **Operator Console & Escalation:** Bảng điều khiển dành cho Chủ đầu tư/Operator kiểm duyệt chủ nhà, duyệt tin đăng pháp lý (Sổ đỏ/HĐMB) và xử lý ngoại lệ phát sinh.

---

## 2. Công nghệ sử dụng (Tech Stack)

| Phân tầng | Công nghệ | Chi tiết |
|---|---|---|
| **AI Agent** | LangGraph, LangChain | Stateful multi-turn agent, bóc tách nhu cầu, gọi tools và quản lý hội thoại. Hỗ trợ cả **OpenAI** (`gpt-4o-mini`) và **Google Gemini** (`gemini-2.5-flash` / `gemini-flash-lite`). |
| **Backend** | FastAPI, Python 3.11+, Pydantic v2 | Kiến trúc Router module hóa, Async I/O, JWT Auth & Phone/Email OTP, Background jobs. |
| **Database** | PostgreSQL 15+, SQLAlchemy, Alembic | Neon Serverless Postgres, giao dịch ACID, Exclusion locks chống xung đột khung giờ. |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS v4 | Giao diện Responsive chia 3 cổng: Buyer Portal, Owner Portal, Operator Console. Tích hợp React Router 7 và TanStack Query. |
| **DevOps & Deploy** | Docker, Render, Vercel, Neon | Backend chạy Docker trên Render; Frontend SPA trên Vercel; Database trên Neon Postgres. |
| **Testing & Eval** | Pytest, AI Golden Set | 150+ unit/integration/concurrency tests; bộ đánh giá Golden Set ≥20 kịch bản thực tế. |

---

## 3. Cấu trúc thư mục

```
P-001/
├── alembic/                # Alembic database migrations
│   └── versions/           # Các script di chuyển schema (identity, deals, bookings, v.v.)
├── data/                   # Bộ dữ liệu hạt giống (Seed data)
│   ├── properties_seed.csv # Danh sách căn hộ mẫu Vinhomes
│   ├── users_seed.csv      # Danh sách tài khoản mẫu (Buyer, Owner, Operator)
│   ├── amenities_seed.csv  # Tiện ích nội khu
│   └── projects_buildings_seed.csv # Dự án & Tòa nhà
├── eval/                   # AI Agent Evaluation
│   ├── golden_set.json     # Bộ kịch bản kiểm thử chuẩn vàng cho AI
│   └── run_golden.py       # Script chạy đánh giá tự động và xuất báo cáo
├── frontend/               # Giao diện Web (React 19 + Vite + Tailwind CSS)
│   ├── src/
│   │   ├── auth/           # Context xác thực & phân quyền (Buyer/Owner/Operator)
│   │   ├── components/     # Component UI dùng chung
│   │   └── pages/          # Các màn hình: Chat, PropertyDetail, Owner, Operator
│   └── vercel.json         # Cấu hình rewrite SPA cho Vercel
├── scripts/                # Utility scripts & hook ghi log AI
│   ├── start.sh            # Script khởi động tự động cho production container
│   ├── log_antigravity.py  # Hook ghi log phiên làm việc cho Antigravity IDE
│   └── submit_log.py       # Tự động gửi log lên server chấm điểm
├── src/                    # Mã nguồn Backend (FastAPI + LangGraph)
│   ├── agents/             # Định nghĩa Graph, Prompts và Tools của Agent
│   ├── api/routers/        # Endpoints: auth, chat, properties, deals, bookings, operator, owner
│   ├── core/               # Bảo mật, phân quyền, cấu hình dùng chung
│   ├── db/                 # Kết nối DB, Models (SQLAlchemy), Seed runner
│   ├── models/             # Pydantic schemas (Request/Response)
│   ├── services/           # Nghiệp vụ: booking, scheduling, hold, notification, escalation
│   ├── config.py           # Pydantic Settings & nạp biến môi trường
│   ├── jobs.py             # Background tasks (hết hạn hold, nhắc lịch)
│   └── main.py             # Khởi tạo FastAPI Application
├── tests/                  # Bộ kiểm thử Pytest (150+ tests)
│   ├── test_agents/        # Kiểm tra tính bền vững của hội thoại AI
│   ├── test_api/           # Test API endpoints và phân quyền
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
- PostgreSQL 15+ (hoặc kết nối tới Neon Postgres)

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
  - Dùng OpenAI: `LLM_PROVIDER=openai` và `OPENAI_API_KEY=sk-...`
  - Dùng Google Gemini: `LLM_PROVIDER=google` và `GOOGLE_API_KEY=AIza...` (Tùy chọn `MODEL_NAME=gemini-flash-lite-latest` nếu bản flash gặp giới hạn tốc độ).

```bash
# 4. Khởi tạo cơ sở dữ liệu và nạp dữ liệu mẫu
alembic upgrade head
python -m src.db.seed

# 5. Khởi động Backend API
uvicorn src.main:app --reload --port 8000
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

## 5. Tài khoản Demo kiểm thử

Mật khẩu mặc định cho toàn bộ tài khoản demo là: `Password123!`

| Vai trò | Email đăng nhập | Quyền hạn & Chức năng kiểm thử |
|---|---|---|
| **Người mua (Buyer)** | `an.nguyen@gmail.com` | Chat tìm nhà với AI, xem danh sách căn hộ, chọn lịch rảnh và đặt lịch xem. |
| **Chủ căn hộ (Owner)** | `tuan.pham@gmail.com`<br>`lan.hoang@gmail.com` | Đăng tin căn hộ, quản lý khung giờ rảnh, duyệt/từ chối yêu cầu đặt lịch xem nhà. |
| **Chủ đầu tư (Operator)** | `operator@vinhomes.vn` | Duyệt chủ nhà, kiểm duyệt hồ sơ căn hộ, giám sát lịch xem và xử lý hàng đợi ngoại lệ. |

*Hệ thống cũng hỗ trợ đăng nhập qua mã OTP (khi chưa cấu hình SMS/Zalo Gateway, mã OTP sẽ hiển thị trực tiếp trên màn hình).*

---

## 6. Kiểm thử & Đánh giá chất lượng

Hệ thống được trang bị bộ kiểm thử tự động toàn diện:

```bash
# Chạy toàn bộ 150+ unit, integration & concurrency tests
pytest tests -q

# Chạy riêng kiểm thử luồng Demo hoàn chỉnh (Core Demo Flow)
pytest tests/test_e2e/test_core_demo_flow.py -v

# Kiểm tra xử lý xung đột đồng thời (Anti-Double-Booking / AC-08)
pytest tests/test_services/test_concurrency.py -v

# Chạy bộ đánh giá AI Golden Set (≥20 kịch bản đánh giá với model thực tế)
python eval/run_golden.py
```
*Kết quả đánh giá AI sẽ được tự động ghi lại tại [`eval/results/golden_report.md`](eval/results/golden_report.md).*

---

## 7. Hướng dẫn Triển khai Production (Vercel + Render + Neon)

Hệ thống được thiết kế theo mô hình phân tán tối ưu chi phí (hoàn toàn có thể chạy trên các gói Free Tier):
- **PostgreSQL Database:** Lưu trữ trên **Neon Serverless Postgres**.
- **Backend API & AI Engine:** Đóng gói Docker chạy trên **Render Web Service** (đáp ứng các tác vụ chạy ngầm, duy trì bộ nhớ hội thoại và giữ kết nối lâu dài).
- **Frontend SPA:** Triển khai trên **Vercel Edge Network**.

### Các bước triển khai:

1. **Cơ sở dữ liệu (Neon):**
   - Tạo Project mới trên Neon Console, lấy chuỗi kết nối (`postgresql://...neon.tech/neondb?sslmode=require`).
2. **Backend API (Render):**
   - Đăng nhập Render Dashboard → New → Blueprint → Trỏ tới repository (sử dụng file [`render.yaml`](render.yaml)).
   - Điền các biến môi trường: `DATABASE_URL` (từ Neon), `GOOGLE_API_KEY` hoặc `OPENAI_API_KEY`, tạm để trống `CORS_ORIGINS`.
   - File [`scripts/start.sh`](scripts/start.sh) sẽ tự động chạy migration, nạp seed ban đầu và mở các khung giờ xem trống trong 7 ngày tới.
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
