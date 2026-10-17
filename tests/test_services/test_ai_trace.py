"""Developer traces of chat turns (ai_turns): what the tracer takes from each model call."""

from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from src.services.ai_trace import TurnTracer


def _call(tracer: TurnTracer, usage: dict) -> None:
    run_id = uuid4()
    tracer.on_chat_model_start({}, [], run_id=run_id, invocation_params={"model": "claude-sonnet-5-5"})
    message = AIMessage(content="ok", usage_metadata=usage)
    tracer.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]), run_id=run_id)


def test_tracer_records_tokens_read_from_the_prompt_cache():
    tracer = TurnTracer()
    _call(
        tracer,
        {
            "input_tokens": 11235,
            "output_tokens": 125,
            "total_tokens": 11360,
            "input_token_details": {"cache_read": 10710},
        },
    )
    # A model without prompt caching reports no cache details
    _call(tracer, {"input_tokens": 500, "output_tokens": 20, "total_tokens": 520})
    first, second = tracer.steps
    assert (first["prompt_tokens"], first["cache_read_tokens"]) == (11235, 10710)
    assert second["cache_read_tokens"] is None
