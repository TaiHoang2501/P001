# Project Constitution: AI20K Agent (P-001)

## 1. Code Quality & Architecture
- **3-Tier Architecture Strictness**: Maintain clear boundaries between routing (`api/`), business logic/external integrations (`services/`), and agent workflows (`agents/`). Do not mix FastAPI request handling with LangGraph state transitions. Agent tools only reach data through `services/agent_api.py` → services, never the DB directly.
- **Type Safety**: Strictly use `Pydantic` models for API schemas (`models/`) and `TypedDict` for LangGraph state (`agents/state.py`). Keep the frontend types generated from the backend OpenAPI (`npm run gen:api`). Ensure all functions have Python type hints.
- **Linting & Formatting**: Adhere to the configured `ruff` rules. Code must pass all linting checks before being merged.

## 2. Testing & Evaluation
- **Unit & Integration Tests**: Write comprehensive tests using `pytest` for all individual components (API endpoints, tools, and services).
- **Agent Behavior Evaluation**: Treat the LLM-based agent as non-deterministic. Use the provided evaluation frameworks (e.g., in the `eval/` directory) to measure the agent's accuracy and reliability over time.
- **Test-Driven AI Logging**: Ensure the AI usage logging hooks are not bypassed during tests or normal execution, to maintain observability. Every chat turn is traced in `ai_turns` (`scripts/ai_traces.py`).

## 3. Maintainability & Operations
- **Environment Management**: Never hardcode secrets. Always use `config.py` (Pydantic Settings) loaded from environment variables (`.env`).
- **Error Handling & Observability**: Gracefully handle external API failures (an LLM error falls back to the fallback model, then to a clear "interrupted" message with nothing written; an unexpected tool failure stops the action and opens a `SYSTEM_FAILURE` escalation). Use structured logging. Important actions write `audit_logs`.
- **Documentation**: Keep `README.md`, `CLAUDE.md`, `JOURNAL.md`, `.specify/` and the diagrams in `DIagram/` updated with major architectural decisions, business rules and setup instructions. Comment complex LLM prompts and state graphs.

## 4. Agentic Interaction Principles
- **Clarity First**: When extending the agent's capabilities, prefer explicit state transitions over complex prompt engineering.
- **Tool Independence**: Build tools (`agents/tools.py`, backed by `services/agent_api.py`) so they can be tested independently of the LangGraph flow.
- **Guardrails in code, not only in prompts**: business rules, privacy and "never claim success without a committed tool result" are enforced by the service layer and `agents/guardrails.py`, not by the system prompt alone.
