# AI20K Agent Template

Template chính thức cho học viên VinUni AI20K Build Phase: cấu trúc dự án, code
mẫu và hướng dẫn kỹ thuật để xây dựng một AI Agent hoàn chỉnh — từ kiến trúc,
code, test cho đến deploy và nộp bài Demo Day.

Technical Guidebook: <https://phoenix.note.transformerlabs.ai/technical-book>

## BookingBot AI Agent — chạy MVP

Trợ lý AI-first giúp người mua tìm căn Vinhomes đã xác thực, kết nối trực tiếp với chủ căn và
khớp lịch xem nhà (spec: `.specify/spec_final.md`, quy ước: `CLAUDE.md`).

**Luồng MVP (spec §12):** người mua chat với AI → AI gợi ý căn thật từ DB → khớp giờ rảnh của
người mua với lịch trống chủ căn → tạo yêu cầu xem kèm **Deal ID** → chủ căn xác nhận → căn được
**giữ riêng trong khung giờ xem** → nhắc lịch T-24h/T-2h → xem nhà. Chủ căn chứng minh quyền sở hữu
bằng sổ đỏ + OTP; Chủ đầu tư duyệt hồ sơ người bán, duyệt tin và xử lý hàng đợi ngoại lệ.

### Web gồm những gì

Trang đầu (`/`) hỏi **"Bạn muốn làm gì hôm nay?"** với hai lựa chọn:

- **Người xem nhà** → khu người mua `/buyer/*` (giao diện theo wireframe 1.1–1.6). Trước khi chat, web
  hỏi **người mới hay đã có tài khoản**:
  - **Người mới:** chat ngay với AI Agent với tư cách khách, không cần tài khoản. Khi xác nhận lịch xem
    (trong chat hoặc ở trang chọn giờ), khung **đăng ký SĐT + OTP** hiện ra; đăng ký xong yêu cầu xem
    được gửi luôn và cuộc trò chuyện chuyển sang tài khoản mới (AI vẫn nhớ ngữ cảnh).
  - **Người cũ:** đăng nhập trước, rồi chat, xem lại / đổi / hủy lịch ở "Lịch xem của tôi".
  - Các trang: chat + danh sách căn phù hợp, chi tiết căn, chọn ngày/giờ xem, theo dõi trạng thái Deal.
- **Người bán nhà** → cổng BookingBot (`/login`, `/owner/*`), dùng chung với **Chủ đầu tư** (`/operator/*`):
  - Người bán **chỉ đăng nhập bằng SĐT + OTP** (backend chặn đăng nhập/đăng ký bằng mật khẩu cho vai
    trò này); lần đầu dùng số là tạo tài khoản.
  - **Xác thực sổ đỏ** (`/owner/verify`): nhập đúng họ tên người đứng tên + mã số sổ như dữ liệu của
    Chủ đầu tư (`property_ownership_verifications`) → OTP gửi tới SĐT chủ sở hữu ghi trên sổ → nhập đúng
    là sổ thuộc tài khoản này. Sai OTP 5 lần thì sổ bị khóa. Mỗi sổ chỉ dùng cho **một** tin đăng.
  - Xác thực sổ xong, hồ sơ người bán vào hàng chờ; **Chủ đầu tư vẫn duyệt** hồ sơ và từng tin đăng
    trước khi căn được AI gợi ý cho người mua.
  - Chủ đầu tư đăng nhập bằng email + mật khẩu (tab "Quản trị viên").

### AI Agent làm được gì

Agent (LangGraph + Gemini) nhận **mục tiêu** rồi tự gọi công cụ đến khi xong, chỉ hỏi lại khi thiếu thông tin:

- **Tìm căn xong là đề xuất giờ luôn:** cùng câu trả lời, agent kiểm tra lịch của căn khớp nhất và đưa 2–3 giờ
  trống để khách bấm chọn.
- **Tự chọn giờ và đặt:** "Đặt căn S1.08-2410 chiều Chủ nhật, giờ nào cũng được" → agent đặt giờ sớm nhất
  khớp lịch chủ căn, báo mã Deal và giờ thay thế. Backend từ chối mọi giờ nằm ngoài khung giờ khách đã nói.
- **Làm trọn chuỗi:** "Đặt giúp tôi căn hợp nhất chiều Chủ nhật này" → tìm → chọn căn → khớp lịch → đặt.
- **Nhớ khách:** tiêu chí, ngân sách và giờ rảnh của khách đã đăng nhập được lưu ở `buyer_profiles`, nên sang
  cuộc chat mới không phải hỏi lại. Lịch sử hội thoại lưu trong PostgreSQL, khởi động lại server không mất.
- **Làm việc khi khách không chat** (job nền, thông báo trong chuông 🔔 của khu người mua):
  - Chủ căn chưa phản hồi sau `AGENT_FOLLOWUP_MINUTES` (mặc định 60 phút) hoặc đã từ chối → agent gửi khách giờ
    trống khác của căn đó và căn tương tự. Yêu cầu gốc giữ nguyên; sau 24h vẫn chuyển Chủ đầu tư như cũ.
  - Có căn mới được duyệt khớp tiêu chí đã lưu → báo khách.
  - Nhắc lịch T-24h / T-2h được agent viết riêng cho khách.
  - Tin nhắn chỉ dùng dữ kiện từ database; model lỗi hoặc làm mất dữ kiện (mã Deal, giờ) thì dùng mẫu cố định.
- Giới hạn giữ nguyên: agent không xác nhận lịch thay chủ căn, không đàm phán giá, không nhận cọc.

Dữ liệu đi qua các lớp và bảng nào: xem [`DIagram/Data Flow Diagram.md`](DIagram/Data%20Flow%20Diagram.md).

### Chạy local

Cần Python 3.11+, PostgreSQL 15+ và Node 20+.

```bash
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # điền DATABASE_URL, JWT_SECRET và khóa LLM (xem bên dưới)

alembic upgrade head    # tạo bảng
python -m src.db.seed   # dữ liệu demo (DB trống); DB cũ sau khi pull: python -m src.db.seed --ensure-red-books
uvicorn src.main:app --reload --port 8000        # API: http://localhost:8000/docs

cd frontend && npm install && npm run dev        # Web: http://localhost:5173
# nếu API chạy cổng khác: API_PROXY=http://localhost:8001 npm run dev
```

**Mô hình AI** (`.env`): `LLM_PROVIDER=openai` + `OPENAI_API_KEY`, hoặc `LLM_PROVIDER=google` +
`GOOGLE_API_KEY` (Gemini). Nên dùng `MODEL_NAME=gemini-flash-latest` (bản lite hay chọn sai ngày/giờ khi tự
đặt lịch); khi model chính lỗi hoặc quá tải, `MODEL_FALLBACK_NAME` (mặc định `gemini-flash-lite-latest`) trả lời thay.

**Bộ nhớ hội thoại** (`AGENT_MEMORY=postgres`, mặc định): lưu trong PostgreSQL (bảng `checkpoint*` do
LangGraph tự tạo). Trên **Windows** phải chạy uvicorn với `--reload` (như lệnh trên / `make run`); chạy không
`--reload` thì server vẫn lên nhưng dùng bộ nhớ RAM (mất khi khởi động lại) và ghi cảnh báo vào log.
Chạy server nền / demo không cần tự nạp lại code: `python scripts/run_api.py` (tự chọn event loop đúng trên
Windows, giữ bộ nhớ Postgres).

**Tài khoản demo:** người mua `an.nguyen@gmail.com` và Chủ đầu tư `operator@vinhomes.vn` (mật khẩu
`Password123!`). Chủ căn chỉ đăng nhập bằng số điện thoại + OTP: Tuấn `0918765432`, Lan `0912345678`.
Khi chưa có nhà cung cấp SMS/Zalo, mã OTP hiện ngay trên màn hình (ngoài production, hoặc khi bật
`OTP_EXPOSE_CODE=true`).

**Sổ đỏ demo** (`data/property_ownership_verifications_seed.csv`): Tuấn và Lan đã có sổ xác thực sẵn
để đăng tin; sổ **Nguyễn Thị Hương · `SD-2017-0332211`** chưa ai xác thực, dùng để thử luồng xác thực
với một tài khoản người bán mới. Sổ của Trần Văn Đức đang bị khóa (nhập sai OTP quá số lần).

**Câu chat mẫu:** "Tôi cần căn 2 phòng ngủ ở Ocean Park, dưới 3,5 tỷ".

**Đã có DB từ trước?** `seed` chỉ nạp vào DB trống. Sau khi pull bản có dữ liệu mới (vd. sổ đỏ),
chạy `python -m src.db.seed --ensure-red-books` để thêm phần còn thiếu mà không xóa dữ liệu đang có
(hoặc `--reset` để làm lại từ đầu).

### Deploy (Vercel + Render + Neon, đều có gói miễn phí)

Web (React) chạy trên **Vercel**; API (FastAPI, Dockerfile) chạy trên **Render**; PostgreSQL trên **Neon**.
API không đặt trên Vercel vì cần tiến trình chạy lâu: bộ nhớ hội thoại AI, job nền (hết hạn giữ căn,
nhắc lịch, chuyển ngoại lệ) và lượt chat có thể dài hơn giới hạn của serverless function.

1. **Neon** — tạo project → copy connection string (`postgresql://...neon.tech/...?sslmode=require`).
2. **Render** — Dashboard → New → Blueprint → chọn repo (dùng `render.yaml`). Điền `DATABASE_URL`
   (Neon), `GOOGLE_API_KEY`, và tạm để `CORS_ORIGINS` trống. Lần khởi động đầu tự chạy migration,
   nạp dữ liệu demo và mở lịch trống 7 ngày tới (`scripts/start.sh`); các lần sau chỉ bổ sung sổ đỏ
   demo còn thiếu và lịch trống, không nạp lại dữ liệu khác. Ghi lại URL API, ví dụ
   `https://bookingbot-api.onrender.com`.
   `render.yaml` deploy nhánh `main`; muốn chạy nhánh khác (vd. `feature/Baor-app` trước khi merge),
   tạo **New → Web Service** (Docker) chọn nhánh đó và điền các biến như trong `render.yaml`.
3. **Vercel** — New Project → chọn repo → **Root Directory: `frontend`** → thêm biến
   `VITE_API_URL` = URL API ở bước 2 → Deploy. Ghi lại URL web, ví dụ `https://bookingbot.vercel.app`.
4. Quay lại Render, đặt `CORS_ORIGINS` = URL web ở bước 3 (không có `/` ở cuối) → service tự deploy lại.

Lưu ý: gói free của Render ngủ sau ~15 phút không dùng, request đầu tiên sau đó mất khoảng 1 phút.
Dữ liệu demo công khai (mật khẩu `Password123!`, mã OTP hiện trên màn hình) — chỉ dùng dữ liệu giả.

### Kiểm thử

```bash
pytest tests -q                # 180+ test, cần PostgreSQL (tự tạo DB <tên>_test)
python eval/run_golden.py      # golden set AI ≥20 kịch bản với model thật -> eval/results/golden_report.md
```

- `tests/test_e2e/test_core_demo_flow.py` chạy trọn luồng demo qua API (model giả lập).
- Test tranh chấp đồng thời (AC-08): `tests/test_services/test_concurrency.py`.

## Template có sẵn những gì

- **Cấu trúc thư mục tách lớp** — `agents/`, `api/`, `services/`, `models/` đã
  chia sẵn, không phải bàn lại từ đầu.
- **Code mẫu chạy được** — LangGraph agent (state, node, tool), FastAPI routes,
  Pydantic settings, schema.
- **Docker và CI** — Dockerfile multi-stage, `docker-compose.yml`, workflow
  GitHub Actions chạy `ruff` + `pytest` khi push lên `main`/`develop` và khi mở
  pull request vào `main`.
- **Technical Guidebook 10 chương** trong `docs/guide/`, đồng thời đọc được
  online.
- **Checklist 10 deliverables** của Demo Day.
- **AI usage logging** — hook cài sẵn cho 6 công cụ AI, log tự động gửi lên
  grading server mỗi lần `git push`.

## Yêu cầu

- Python 3.11 (phiên bản CI đang dùng)
- Git
- Docker — tuỳ chọn, chỉ cần nếu chạy `docker compose`

## Bắt đầu

### 1. Clone repo của đội

Khi đội được chốt, hệ thống tự sinh repo cho đội từ template này, nằm trong org
GitHub của khoá bạn đang học và đặt tên theo mã đội. Copy URL ở trang đội trên
Phoenix rồi clone về:

```bash
git clone https://github.com/<ORG-CỦA-KHOÁ>/<MÃ-ĐỘI>.git
cd <MÃ-ĐỘI>
```

Không cần `rm -rf .git`, `git init` hay `git remote add`: repo sinh từ template
đã bắt đầu bằng lịch sử riêng của đội và remote trỏ sẵn đúng chỗ. Chưa thấy repo
của đội thì báo BTC — repo tự tạo nằm ngoài org sẽ không được chấm.

### 2. Cài môi trường

```bash
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường

```bash
cp .env.example .env
```

Mở `.env` và điền `OPENAI_API_KEY`. Riêng `AI_LOG_API_KEY`, mỗi thành viên tự
tạo key riêng tại [dashboard Phoenix](https://phoenix.note.transformerlabs.ai/api-keys)
rồi thay vào chỗ `<get-your-api-key-from-dashboard-phoenix>` — giá trị trong
`.env.example` chỉ là placeholder, để nguyên thì log không vào được hệ thống chấm.

### 4. Cài hook ghi log AI

```bash
bash scripts/setup_hooks.sh                                      # Linux / macOS / Git Bash
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1 # Windows PowerShell
```

Chạy một lần sau khi clone. Hook ghi lại prompt khi bạn dùng Claude Code, Cursor,
Codex CLI, Gemini CLI, Antigravity hoặc GitHub Copilot, và cài pre-push hook để
đẩy log lên server.

### 5. Chạy server

```bash
uvicorn src.main:app --reload --port 8000
```

Swagger UI ở <http://localhost:8000/docs>. Hoặc dùng `make run`, `make test`,
`make lint` — xem `Makefile`.

## Cấu trúc thư mục

```
src/
  agents/            LangGraph agent
    graph.py         State graph (agent node <-> tool node)
    prompts.py       System prompt (quy tắc của agent)
    tools.py         Agent tools: tìm căn, khớp lịch, đặt/đổi/hủy lịch, chuyển người thật
    state.py         State schema
  api/routers/       FastAPI endpoints (auth, chat, properties, bookings, owner, operator...)
  core/              Auth, phân quyền, lỗi chuẩn
  db/                SQLAlchemy models, session, seed dữ liệu demo
  models/            Pydantic schemas
  services/          Nghiệp vụ: booking, deal, hold, OTP, sổ đỏ, chat, thông báo, ngoại lệ...
  jobs.py            Job nền (hết hạn giữ căn, nhắc lịch)
  config.py          Pydantic Settings
  main.py            App entry point
alembic/             Migration cơ sở dữ liệu
data/                Dữ liệu demo (CSV)
frontend/            Web React + Vite + Tailwind
  src/pages/         Chọn vai trò, đăng nhập, cổng người bán (owner/) và Chủ đầu tư (operator/)
  src/buyer/         Khu người mua: chat AI, chi tiết căn, chọn giờ, theo dõi Deal, chat khách
tests/               pytest suite
scripts/             Hook ghi log AI + installer
docs/
  guide/             Technical Guidebook (nguồn của bản online)
  architecture_diagram.md
eval/                Kết quả evaluation
presentation/        Slide và video Demo Day
.claude/ .codex/ .cursor/ .gemini/ .agents/ .github/hooks/
                     Config hook cho từng công cụ
.github/workflows/   CI
Dockerfile           Multi-stage build
docker-compose.yml   Chạy backend bằng Docker
README_boilerplate.md  Khung README cho dự án của đội
```

## Technical Guidebook

| Chương | Nội dung | Thời gian |
|---|---|---|
| 1 | Lời mở đầu — mục tiêu, cách sử dụng | 15 phút |
| 2 | Khởi tạo dự án — clone, setup, git workflow | 4 giờ |
| 3 | Thiết kế kiến trúc — 3-tier, diagram, ADR | 6 giờ |
| 4 | LangGraph Agent — state, node, edge, tool, RAG | 8 giờ |
| 5 | FastAPI — routes, validation, error handling, streaming | 6 giờ |
| 6 | Giao diện — Next.js và Streamlit | 6 giờ |
| 7 | DevOps — Docker, CI/CD, deploy, logging | 6 giờ |
| 8 | Kiểm thử — unit test, integration test, RAGAS | 4 giờ |
| 9 | Demo Day — 10 deliverables, checklist | 2 giờ |
| 10 | Tài nguyên — khoá học, tài liệu, BMAD method | tham khảo |

Đọc online tại <https://phoenix.note.transformerlabs.ai/technical-book>: đăng
nhập bằng GitHub (đúng account đã được BTC mời vào org của khoá), chọn tab
**Technical Book** ở sidebar trái. Bản offline nằm trong `docs/guide/`, mở được
bằng bất kỳ markdown viewer nào.

## 10 deliverables cho Demo Day

| # | Deliverable | Vị trí | Template lo tới đâu |
|---|---|---|---|
| 1 | Source code | `src/` | Khung sẵn |
| 2 | README | copy `README_boilerplate.md` thành `README.md` | Khung sẵn |
| 3 | Architecture diagram | `docs/architecture_diagram.md` | Khung sẵn |
| 4 | AI logs | LangSmith (3 biến môi trường) + auto AI usage logging | Cấu hình sẵn |
| 5 | Live URL | deploy lên Render/Vercel | CI/CD sẵn |
| 6 | Video demo | `presentation/` | Đội tự làm |
| 7 | Pitch deck | `presentation/` | Đội tự làm |
| 8 | Development journal | `JOURNAL.md` | Khung sẵn |
| 9 | Worklog | `WORKLOG.md` | Khung sẵn |
| 10 | Evaluation evidence | `eval/` | Đội tự làm |

## Tech stack

| Lớp | Công nghệ |
|---|---|
| Agent | LangGraph + LangChain 0.3 |
| Backend | FastAPI 0.115 + Uvicorn |
| LLM | Gemini (`gemini-flash-lite-latest`) hoặc OpenAI (`gpt-4o-mini`), chọn bằng `LLM_PROVIDER` |
| Cơ sở dữ liệu | PostgreSQL 16 + SQLAlchemy 2 + Alembic |
| Giao diện | React + Vite + TypeScript + Tailwind, TanStack Query, `openapi-fetch` |
| Lint / test | ruff + pytest 8 |
| DevOps | Docker + GitHub Actions; deploy Vercel (web) + Render (API) + Neon (DB) |

## AI usage logging

Mọi prompt được ghi vào `.ai-log/session.jsonl` và tự động gửi lên grading server
ở bước pre-push.

| Công cụ | Cấu hình | Thời điểm ghi |
|---|---|---|
| Claude Code | `.claude/settings.json` | mỗi prompt (`UserPromptSubmit`) |
| Cursor | `.cursor/hooks.json` | mỗi prompt và khi dừng |
| OpenAI Codex CLI | `.codex/hooks.json` | mỗi prompt và khi dừng |
| Gemini CLI | `.gemini/settings.json` | mỗi lượt agent chạy |
| GitHub Copilot | `.github/hooks/hooks.json` | mỗi prompt và cuối session |
| Antigravity IDE | `.agents/hooks.json` | mỗi prompt, kèm lần quét lại lúc `git push` |

Dùng ChatGPT hay công cụ web khác thì log thủ công:

```bash
bash scripts/_pyrun.sh scripts/log_manual.py --tool chatgpt --prompt "What you asked"
```

## Đóng góp

Repo này là open source. Đọc [CONTRIBUTING.md](CONTRIBUTING.md) trước khi mở PR.

Nội dung trong `docs/guide/` là nguồn của Technical Book và được đồng bộ lên bản
online, nên mọi thay đổi ở đó cần review của
[@AI20K-Build-Phase/book-maintainers](https://github.com/orgs/AI20K-Build-Phase/teams/book-maintainers)
— xem [.github/CODEOWNERS](.github/CODEOWNERS).

Báo lỗ hổng bảo mật theo [SECURITY.md](SECURITY.md), đừng mở public issue.

## License

[MIT](LICENSE) — dùng tự do cho mục đích giáo dục.
