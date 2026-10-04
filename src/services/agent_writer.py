"""The agent words its own messages (follow-ups, reminders) from fixed facts.

The model only rephrases: every fact comes from the database, the reply must still contain the key facts
(deal code, time...), and anything unusable, slow or failing falls back to the template text. Off in tests
and when no model key is configured.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.services.llm import get_fallback_llm, get_llm

logger = logging.getLogger(__name__)

_MAX_CHARS = 700

_SYSTEM = """Bạn là BookingBot, trợ lý AI của sàn căn hộ Vinhomes. Viết MỘT tin nhắn thông báo trong ứng dụng
gửi cho người mua, tiếng Việt, thân thiện, tối đa 4 câu, không chào hỏi dài dòng, không emoji, không markdown.
Chỉ dùng đúng các dữ kiện được cho: không thêm căn, giá, giờ, con số, lời hứa hay đường link nào khác.
Giữ nguyên nguyên văn mã deal, mã căn, giá và giờ như trong dữ kiện. Không hứa chủ căn sẽ đồng ý."""


def enabled() -> bool:
    s = get_settings()
    return s.agent_personalize and s.app_env != "test" and bool(s.llm_api_key)


def compose(purpose: str, facts: dict[str, str], fallback: str, must_include: list[str]) -> str:
    """The model's wording of `facts`, or `fallback` when it is off, fails, or drops a required fact."""
    if not enabled():
        return fallback
    lines = "\n".join(f"- {k}: {v}" for k, v in facts.items() if v)
    try:
        llm = get_llm()
        if (backup := get_fallback_llm()) is not None:
            llm = llm.with_fallbacks([backup])
        reply = llm.invoke([SystemMessage(_SYSTEM), HumanMessage(f"Mục đích tin nhắn: {purpose}\nDữ kiện:\n{lines}")])
        text = " ".join(reply.text.split())
    except Exception as e:
        logger.warning("agent message wording failed (%s); using the template", str(e)[:200])
        return fallback
    if not 20 <= len(text) <= _MAX_CHARS or "http" in text or any(f not in text for f in must_include):
        logger.info("agent message wording rejected; using the template")
        return fallback
    return text
