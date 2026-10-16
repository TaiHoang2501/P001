from langchain_core.messages import AIMessage, HumanMessage

from src.services import llm_observability as obs


def test_langsmith_masks_pii_in_run_data() -> None:
    data = {
        "messages": [HumanMessage("số tôi 0912 345 678, mail an@example.com"), AIMessage("Dạ")],
        "nested": {"note": "+84987654321"},
    }
    masked = obs._mask_run_data(data)
    text = str(masked)
    assert "0912 345 678" not in text and "an@example.com" not in text and "+84987654321" not in text
    assert "[phone]" in text and "[email]" in text


def test_langsmith_metadata_drops_buyer_name_and_memory() -> None:
    masked = obs._mask_metadata(
        {"buyer_name": "Nguyễn Văn An", "buyer_memory": "thích view hồ", "conversation_id": "c1", "user_id": 7}
    )
    assert masked == {"conversation_id": "c1", "user_id": 7}


def test_langsmith_off_in_tests() -> None:
    assert obs.get_langsmith() is None
