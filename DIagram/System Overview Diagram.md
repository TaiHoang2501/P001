# Sơ đồ Kiến trúc Tổng thể (System Overview Diagram)

> Sơ đồ kiến trúc tổng thể của hệ thống **BookingBot AI Agent** theo cấu trúc phân tầng (Frontend, Backend, AI Agent) và đặc tả kỹ thuật chi tiết tại **§10 của [spec_updated.md](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/.specify/spec_updated.md)**.

```mermaid
flowchart TD
    %% ==========================================
    %% 1. FRONTEND LAYER (RESPONSIVE WEB)
    %% ==========================================
    subgraph Frontend["Frontend (Next.js + TypeScript)"]
        UI["Customer Web Chat<br/><i>(Khách tìm căn & Đặt lịch qua AI - Streaming SSE)</i>"]
        OWNER_UI["Owner Dashboard<br/><i>(Chủ nhà duyệt lịch & Quản lý tin đăng)</i>"]
        ADMIN_UI["Investor / Operator Dashboard<br/><i>(Kiểm duyệt tin, Giám sát booking & Analytics)</i>"]
    end

    %% ==========================================
    %% 2. BACKEND LAYER (SOURCE OF TRUTH)
    %% ==========================================
    subgraph Backend["Backend (FastAPI - Python 3.11+)"]
        API["FastAPI API Endpoints<br/><i>(Routing, Pydantic Validation & Security Gatekeeper)</i>"]
        AUTH["Xác thực & Phân quyền (RBAC)<br/><i>(JWT, OTP, Password Hashing Argon2id/bcrypt)</i>"]
        
        subgraph CoreServices["Dịch vụ Nghiệp vụ Lõi (Business Services)"]
            SEARCH_ENG["Search & Ranking Engine<br/><i>(Hard filter SQL + Soft scoring + Proximity)</i>"]
            BOOKING_SM["Booking State Machine<br/><i>(Requested → Confirmed → Completed / Cancelled)</i>"]
            HOLD_ENG["Viewing Hold Engine<br/><i>(Atomic Hold khóa căn đúng khung giờ xem)</i>"]
            WS_CHAT["WebSocket Realtime Chat<br/><i>(Kênh chat trực tiếp Khách ↔ Chủ nhà sau khi xem)</i>"]
            NOTIFY_SVC["Notification Service<br/><i>(Nhắc lịch tự động T-24h, T-2h qua SMS/Zalo/In-app)</i>"]
        end

        DB[("Database<br/><i>PostgreSQL (Full-text + pg_trgm, ACID Transactions)</i>")]
        MEDIA[("Storage Media<br/><i>Amazon S3 (Ảnh & Video căn hộ)</i>")]
    end

    %% ==========================================
    %% 3. AI AGENT LAYER (ORCHESTRATOR)
    %% ==========================================
    subgraph Agent["AI Agent Layer (LangGraph)"]
        ROUTER["Intent & Requirement Extractor<br/><i>(Bóc tách Budget, PN, Diện tích, Phân khu, Hướng)</i>"]
        MEM["Agent Memory & State<br/><i>(Lưu trữ Ngữ cảnh đa lượt & LangGraph Checkpointer)</i>"]
        TOOLS["Controlled Agent Tools<br/><i>(search_properties, check_availability, create_booking)</i>"]
        LLM["LLM Provider Adapter<br/><i>(OpenAI API: gpt-4o-mini / gpt-4o)</i>"]
    end

    %% ==========================================
    %% CONNECTIONS & INTERACTIONS
    %% ==========================================
    %% Frontend -> Backend API Endpoints
    UI --> API
    OWNER_UI --> API
    ADMIN_UI --> API

    %% Backend API liên kết với các Dịch vụ & Dữ liệu
    API --> AUTH
    API --> CoreServices
    CoreServices --> DB
    API --> MEDIA
    CoreServices --> DB

    %% Giao tiếp giữa Backend và AI Agent
    API <--> ROUTER

    %% Trong nội bộ AI Agent
    ROUTER --> MEM
    ROUTER --> TOOLS
    ROUTER --> LLM
    TOOLS --> LLM

    %% Tool execution: Agent gọi Tools -> Backend thực thi có kiểm soát
    TOOLS -. "Gọi thực thi nghiệp vụ có kiểm duyệt" .-> API
```

---

## Bóc tách chi tiết thành phần theo `spec_updated.md`

| Phân tầng | Thành phần | Đặc tả kỹ thuật theo `spec_updated.md` |
|---|---|---|
| **Frontend (Next.js + TypeScript)** | **Customer Web Chat** | Giao diện AI-first đàm thoại tự nhiên với khách hàng; hỗ trợ streaming SSE, hiển thị Property Cards kèm điểm xếp hạng và lý do gợi ý (Explainability). |
| | **Owner Dashboard** | Giao diện cho Chủ nhà: Quản lý danh sách căn hộ đăng bán/cho thuê, nhận thông báo và phê duyệt/từ chối lịch xem nhà (Owner Approval). |
| | **Operator Dashboard** | Giao diện Ban quản trị / Chủ đầu tư: Duyệt tin đăng (`APPROVED`), theo dõi trạng thái Viewing Hold, xử lý ngoại lệ và xem báo cáo chỉ số (KPIs). |
| **Backend (FastAPI)** | **API Endpoints** | Cổng giao tiếp RESTful API; kiểm soát bảo mật, Pydantic schemas, đóng vai trò **Source of Truth** (tuyệt đối không cho AI ghi đè dữ liệu trực tiếp). |
| | **Auth & RBAC** | Xác thực đa vai trò: Khách hàng qua OTP/Booking Code; Chủ nhà & Ban quản trị đăng nhập JWT + Password Hashing bằng Argon2id/bcrypt. |
| | **Search & Ranking Engine** | Thuật toán xếp hạng lai 5 bước: (1) Hard filter SQL $\rightarrow$ (2) Soft scoring (Giá 30%, DT 20%, PN 20%, Hướng 15%, Tầng 15%) $\rightarrow$ (3) Priority weighting $\rightarrow$ (4) Proximity score $\rightarrow$ (5) Explainability. |
| | **Booking & Hold Engine** | Quản lý vòng đời Booking (`REQUESTED → CONFIRMED → COMPLETED`) và cơ chế **Viewing Hold nguyên tử (Atomic)**: Chỉ khóa căn đúng khung giờ xem sau khi chủ nhà duyệt. |
| | **WebSocket Realtime Chat** | Kênh chat trực tiếp 1-1 giữa Khách hàng và Chủ nhà sau khi buổi xem nhà thành công và có Purchase Request. |
| | **Storage & Database** | **PostgreSQL**: Lưu trữ bảng quan hệ, Full-text Search + `pg_trgm`, ACID transactions; **Amazon S3**: Lưu trữ toàn bộ media hình ảnh, video căn hộ. |
| **AI Agent (LangGraph)** | **Intent Router & Extractor** | Phân loại intent từ câu chat của khách hàng, trích xuất cấu trúc `CustomerPreference`, xác định các tiêu chí còn thiếu để hỏi lại. |
| | **Agent Memory** | Quản lý hội thoại đa lượt (Multi-turn state), ghi nhớ lịch sử tương tác qua cơ chế Checkpointing của LangGraph. |
| | **Controlled Tools** | Bộ công cụ chuẩn hóa: `search_properties`, `get_property_detail`, `check_availability`, `create_booking_request`, `reschedule_booking`, `cancel_booking`. |
| | **LLM Provider** | OpenAI API (`gpt-4o-mini` mặc định, tối ưu chi phí & độ trễ). |