# Architecture Diagram

Bản rút gọn. Sơ đồ đầy đủ nằm trong [`DIagram/`](../DIagram/) — bắt đầu từ
[`System Overview Diagram.md`](../DIagram/System%20Overview%20Diagram.md) và [`Data Flow Diagram.md`](../DIagram/Data%20Flow%20Diagram.md).

## System Overview

```mermaid
graph TB
    User([Người mua / Chủ căn / Operator]) --> UI[Frontend<br/>React 19 + Vite]
    UI -->|REST + SSE| API[FastAPI Backend]
    API --> Guard[Guardrails]
    Guard --> Agent[LangGraph Agent]
    Agent --> LLM[LLM<br/>Gemini / OpenAI / Claude / OpenRouter / Groq]
    Agent --> Tools[12 Agent Tools]
    Tools --> Services[Service Layer]
    API --> Services
    Services --> DB[(PostgreSQL)]
    Agent --> DB
```

## Agent Flow

```mermaid
graph LR
    START((Tin nhắn)) --> In[Guardrails đầu vào]
    In --> Agent[Node agent: gọi LLM]
    Agent --> Decide{Cần tool?}
    Decide -->|Có| CallTool[Node tools]
    CallTool --> Agent
    Decide -->|Không| Out[Guardrails đầu ra]
    Out --> END((Câu trả lời))
```

## Component Details

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | React 19 + Vite + TypeScript, Tailwind, TanStack Query | Web cho 3 vai trò + trang dev |
| Backend | FastAPI, Pydantic v2 | REST API, chat SSE, job nền |
| Agent | LangGraph | Điều phối agent, bộ nhớ hội thoại (checkpoint PostgreSQL) |
| LLM | Gemini / OpenAI / Claude (+ OpenRouter, Groq) | Language model, có model dự phòng |
| Database | PostgreSQL 15+ (Neon) | Source of truth, cả ảnh tải lên (`media_files`) |
| Vector Store | — | Không dùng trong MVP (recommendation = SQL hard filter + soft scoring) |
