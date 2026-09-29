# Project Constitution: AI20K Agent (P-001)

## 1. Code Quality & Architecture
- **3-Tier Architecture Strictness**: Maintain clear boundaries between routing (`api/`), business logic/external integrations (`services/`), and agent workflows (`agents/`). Do not mix FastAPI request handling with LangGraph state transitions.
- **Type Safety**: Strictly use `Pydantic` models for API schemas (`models/`) and `TypedDict` for LangGraph state (`agents/state.py`). Ensure all functions have Python type hints.
- **Linting & Formatting**: Adhere to the configured `ruff` rules. Code must pass all linting checks before being merged.

## 2. Testing & Evaluation
- **Unit & Integration Tests**: Write comprehensive tests using `pytest` for all individual components (API endpoints, tools, and services).
- **Agent Behavior Evaluation**: Treat the LLM-based agent as non-deterministic. Use the provided evaluation frameworks (e.g., in the `eval/` directory) to measure the agent's accuracy and reliability over time.
- **Test-Driven AI Logging**: Ensure the AI usage logging hooks are not bypassed during tests or normal execution, to maintain observability.

## 3. Maintainability & Operations
- **Environment Management**: Never hardcode secrets. Always use `config.py` (Pydantic Settings) loaded from environment variables (`.env`).
- **Error Handling & Observability**: Gracefully handle external API failures (e.g., OpenAI/LLM timeouts). Use structured logging.
- **Documentation**: Keep `README.md` and `JOURNAL.md` updated with major architectural decisions and setup instructions. Comment complex LLM prompts and state graphs.

## 4. Agentic Interaction Principles
- **Clarity First**: When extending the agent's capabilities, prefer explicit state transitions over complex prompt engineering.
- **Tool Independence**: Build tools (`agents/tools/`) so they can be tested independently of the LangGraph flow.
