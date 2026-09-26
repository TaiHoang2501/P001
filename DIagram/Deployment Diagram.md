# Deployment Diagram (Sơ đồ Triển khai Hạ tầng)

> Sơ đồ kiến trúc triển khai hệ thống **BookingBot AI Agent** theo đặc tả kỹ thuật tại **§10 của [spec_updated.md](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/.specify/spec_updated.md)** (Docker + AWS, Next.js, FastAPI, PostgreSQL với Full-text search, S3 Media, WebSocket Realtime Chat, OpenAI API).

```mermaid
graph LR
    subgraph Clients["Các Bên Sử dụng (Clients - Responsive Web)"]
        C_USER["Khách hàng (Customer)<br/>Web Chat & Tra cứu căn"]
        O_USER["Chủ nhà (Owner)<br/>Dashboard duyệt lịch & Đăng căn"]
        OP_USER["Ban Quản trị (Investor / Operator)<br/>Kiểm duyệt, Giám sát & Báo cáo"]
    end

    subgraph ExternalServices["Dịch vụ SaaS & Bên thứ 3"]
        GITHUB["GitHub (Repository & CI/CD Actions)"]
        LLM_API["OpenAI API (gpt-4o-mini / gpt-4o)<br/>Bóc tách nhu cầu & Tool calling"]
        NOTIF_GATEWAY["Dịch vụ Thông báo (SMS / Zalo Provider)<br/>Nhắc lịch T-24h & T-2h, Báo duyệt"]
    end

    subgraph AWSCloud["Hạ tầng Đám mây (AWS Cloud / Docker Infrastructure)"]
        subgraph FrontendTier["Frontend Layer (Vercel / AWS Amplify)"]
            NEXTJS["Next.js + TypeScript (Responsive Web)
            - AI Chat Interface (Streaming SSE)
            - Owner Approval & Listing UI
            - Investor/Operator Moderation Dashboard"]
        end

        subgraph BackendTier["Backend Application Layer (Docker on AWS ECS / EC2)"]
            FASTAPI["FastAPI Server (Python 3.11+)
            - RESTful Endpoints & Schema Validation
            - LangGraph AI Agent Orchestrator
            - Recommendation Engine (Hard+Soft scoring)
            - Booking State Machine & Viewing Hold Engine
            - WebSocket Chat Server (Khách ↔ Chủ nhà)"]
        end

        subgraph StorageTier["Data & Media Storage Layer"]
            POSTGRES[("PostgreSQL Database
            - Relational Tables (Users, Listings, Bookings)
            - Full-text Search + pg_trgm (Tra cứu)
            - Atomic Transactions & Row Locks
            - Structured Audit Logs")]

            S3_BUCKET[("Amazon S3 Bucket
            - Lưu trữ Hình ảnh & Video căn hộ Vinhomes
            - Tách biệt hoàn toàn media khỏi Database")]
        end
    end

    %% Client Connections
    C_USER -- "HTTPS / WSS (Chat)" --> NEXTJS
    O_USER -- "HTTPS (Dashboard & Duyệt lịch)" --> NEXTJS
    OP_USER -- "HTTPS (Giám sát & Báo cáo)" --> NEXTJS

    %% Frontend to Backend
    NEXTJS -- "HTTPS REST API & Streaming SSE" --> FASTAPI
    NEXTJS <== "WSS: WebSocket Realtime Chat" ==> FASTAPI

    %% Backend to Internal Storage
    FASTAPI -- "SQL Queries, Full-text Search & Tx Locks" --> POSTGRES
    FASTAPI -- "Upload / Presigned URL" --> S3_BUCKET

    %% Backend to External
    FASTAPI -- "HTTPS API Calls (JSON Tools)" --> LLM_API
    FASTAPI -- "Webhook / API Dispatches" --> NOTIF_GATEWAY

    %% CI/CD
    GITHUB -. "Build & Deploy Frontend" .-> NEXTJS
    GITHUB -. "Build Docker Image & Deploy" .-> FASTAPI
```