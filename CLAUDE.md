# BookingBot AI Agent Guidelines

## 1. Project Architecture & Tech Stack
- **Frontend**: Next.js + TypeScript (Web Chat + Staff UI).
- **Backend**: Python 3.11+ + FastAPI.
- **Agent Orchestration**: LangGraph (for stateful workflow, tool calling, streaming).
- **Database**: PostgreSQL (for core transactions, audit logs, caching if needed) + `pgvector` for RAG.
- **Model Layer**: LLM agnostic adapter. Use OpenAI (gpt-4o-mini/gpt-4o) as default.

## 2. Core Principles
- **Backend is the Source of Truth**: Pricing, availability, and bookings are 100% determined by the backend database, never guessed by the LLM.
- **No Hallucination on Transactions**: AI must ALWAYS use tools (e.g., `check_availability`, `search_properties`) before suggesting dates, times, or properties.
- **Verify Before Committing**: All bookings must pass backend validation (transaction/lock) before confirmation.
- **HITL (Human-in-the-Loop)**: High-risk scenarios (VIPs, special requests, out-of-hours, conflicting rules) must be routed to Sale/Operator via HITL queues.
- **Auditing**: Every critical AI decision and tool call must be logged for evaluation.

## 3. Database Strategy
- Prototype does **not** use real Vinhomes data. We use seed data (~100 properties, mock Sales, resources).
- Never write credentials/secrets into the codebase.

## 4. Coding Conventions
- **Python (Backend)**:
  - Use `Pydantic` for schemas and validation.
  - Type hinting is mandatory for all functions.
  - Follow `ruff` linting rules.
- **TypeScript (Frontend)**:
  - Use functional components and React hooks.
  - Use strict typing for API responses matching backend Pydantic models.
