# Deployment Diagram (Sơ đồ Triển khai Hạ tầng)

> Hạ tầng đang chạy của **BookingBot AI Agent**: frontend SPA trên Vercel, backend Docker trên **Render**
> ([`render.yaml`](../render.yaml)) hoặc **Google Cloud Run** ([`.github/workflows/deploy-cloudrun.yml`](../.github/workflows/deploy-cloudrun.yml)),
> cả hai dùng chung Dockerfile và một database Neon Postgres. Hướng dẫn: mục 8 của [`README.md`](../README.md).

```mermaid
graph LR
    subgraph Clients["Người dùng (Responsive Web)"]
        C_USER["Người mua<br/>AI Chat (SSE), trang Hoạt động, mã QR"]
        O_USER["Chủ căn<br/>sổ đỏ, tin đăng, lịch trống, yêu cầu xem"]
        OP_USER["Chủ đầu tư / Operator<br/>duyệt tin, ngoại lệ, giám sát lịch xem"]
        DEV_USER["Dev<br/>/dev: kill switch + số liệu, scripts/ai_traces.py"]
        GUARD["Bảo vệ / lễ tân<br/>/pass/:token quét mã QR"]
    end

    subgraph Vercel["Vercel"]
        SPA["React 19 + Vite SPA (frontend/)<br/>VITE_API_URL → backend"]
    end

    subgraph Backend["Backend: 1 container Docker (Python 3.11, FastAPI)"]
        direction TB
        RENDER["Render Web Service (free, Singapore)<br/>start.sh: alembic + seed_once rồi uvicorn<br/>Gemini flash-lite, dự phòng flash<br/>OTP local (mã hiện trên màn hình)"]
        CLOUDRUN["Cloud Run (asia-southeast1, 1 instance)<br/>job bookingbot-setup: migration + seed mỗi deploy<br/>Claude Sonnet, dự phòng OpenRouter Gemini<br/>OTP qua Firebase, secret từ Secret Manager"]
        APP["Trong mỗi container:<br/>REST API + chat SSE + thông báo SSE<br/>LangGraph agent + guardrails<br/>job nền trong tiến trình (src/jobs.py, mỗi 60 s)<br/>ảnh tải lên phục vụ qua /api/v1/media/{id}"]
    end

    subgraph Data["Dữ liệu"]
        NEON[("Neon Serverless PostgreSQL<br/>24 bảng nghiệp vụ + checkpoint* LangGraph<br/>media_files: ảnh và giấy tờ tải lên<br/>exclusion constraint chống trùng lịch")]
    end

    subgraph External["Dịch vụ ngoài"]
        LLM_API["LLM API<br/>Google Gemini / Anthropic Claude / OpenAI<br/>OpenRouter / Groq"]
        FIREBASE["Firebase Phone Auth<br/>gửi SMS OTP (khi OTP_PROVIDER=firebase)"]
        OBS["Langfuse / LangSmith<br/>trace AI (tùy chọn)"]
        SCHED["Cloud Scheduler<br/>gọi /health 5 phút/lần (Cloud Run)"]
    end

    GITHUB["GitHub Actions<br/>ci.yml: ruff + pytest<br/>cd.yml: image lên GHCR<br/>deploy-cloudrun.yml"]

    C_USER -- HTTPS --> SPA
    O_USER -- HTTPS --> SPA
    OP_USER -- HTTPS --> SPA
    DEV_USER -- HTTPS --> SPA
    GUARD -- HTTPS --> SPA

    SPA -- "REST (openapi-fetch) + SSE" --> RENDER
    SPA -- "REST (openapi-fetch) + SSE" --> CLOUDRUN
    RENDER --- APP
    CLOUDRUN --- APP

    APP -- "SQL, transaction, khóa dòng" --> NEON
    APP -- "prompt + tool calling" --> LLM_API
    APP -- "xác minh Firebase ID token" --> FIREBASE
    SPA -- "gửi / kiểm mã SMS trên trình duyệt" --> FIREBASE
    APP -. trace .-> OBS
    SCHED -. ping .-> CLOUDRUN

    GITHUB -. "Render tự deploy từ main" .-> RENDER
    GITHUB -. "build image, Artifact Registry, deploy" .-> CLOUDRUN
```

## Ghi chú

- **Một instance backend**: hold hết hạn, nhắc lịch, hết hạn yêu cầu, escalation, follow-up chạy trong tiến trình
  API (`src/jobs.py`), nên Cloud Run đặt `--max-instances=1`. Thông báo realtime (`GET /notifications/stream`) đọc
  bảng `notifications` theo chu kỳ nên vẫn đúng nếu sau này chạy nhiều instance; luồng SSE tự đóng sau 240 s (dưới
  timeout Cloud Run) và web tự nối lại.
- **Media**: ảnh người bán tải lên và giấy tờ hỗ trợ xác thực lưu trong PostgreSQL (`media_files`), giấy tờ là
  riêng tư (chỉ người gửi và Operator xem). Amazon S3 là đích dài hạn, chưa dùng.
- **Chưa có**: gửi SMS/Zalo cho thông báo (chỉ in-app + bong bóng realtime), WebSocket chat Người mua ↔ Chủ căn
  (post-MVP), Vector DB.
- **Seed demo**: chỉ chạy một lần mỗi DB (`src/db/seed_once.py`, `SEED_VERSION`); `SEED_DEMO_DATA=false` cho DB thật.
