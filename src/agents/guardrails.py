"""Deterministic guardrails around the buyer agent, on top of the rules in the system prompt (prompts.py).

The prompt asks the model to behave; these checks make sure it did, in code:

- Input (`screen_input`), before the message reaches the model:
  - personal data the buyer pasted (phone, email, ID card, bank card) is masked: the model provider never
    receives it and the agent does not collect PII it does not need (AC-03);
  - lines that imitate what the system adds to buyer messages ("[Thời điểm khách gửi tin này: …]") are removed;
  - clear prompt-injection / jailbreak attempts are answered with a fixed reply, without calling the model.
- Output (`screen_output`), before the reply is shown and kept in the conversation:
  - phone numbers and emails are masked (contact details are never shared by the assistant);
  - a viewing claimed as confirmed while no tool result says CONFIRMED (AC-05);
  - a unit code that no tool result or buyer message mentioned (made-up property, AC-01);
  - payment / deposit instructions, price negotiation or prediction, legal or transaction commitments (AC-10)
  replace the whole reply with an honest fallback.

Checks are pattern based (Vietnamese and English) and kept conservative: a sentence that negates
("không", "chưa"...) or states a condition ("khi chủ căn xác nhận") is not a violation.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

# ---------- Personal data ----------

_PHONE = re.compile(r"(?<![\d+])(?:\+84|0)[\s.-]?[35789](?:[\s.-]?\d){8}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# CCCD: 12 digits starting with a province code 0xx (prices never start with 0)
_ID_CARD = re.compile(r"(?<!\d)0\d{11}(?!\d)")
_BANK_CARD = re.compile(r"(?<!\d)\d{4}(?:[\s-]?\d{4}){3}(?!\d)")

PHONE_MASK = "[SĐT đã ẩn]"
EMAIL_MASK = "[email đã ẩn]"
ID_MASK = "[số giấy tờ đã ẩn]"
CARD_MASK = "[số thẻ đã ẩn]"


def mask_pii(text: str) -> tuple[str, list[str]]:
    """The text with personal data masked, and the kinds found."""
    found: list[str] = []
    for kind, pattern, mask in (
        ("email", _EMAIL, EMAIL_MASK),
        ("bank_card", _BANK_CARD, CARD_MASK),
        ("id_card", _ID_CARD, ID_MASK),
        ("phone", _PHONE, PHONE_MASK),
    ):
        text, n = pattern.subn(mask, text)
        if n:
            found.append(kind)
    return text, found


# ---------- Input ----------

# Lines the system itself adds to buyer messages (graph.turn_context); a buyer typing them could fake the time
_FORGED_CONTEXT = re.compile(
    r"^\s*\[\s*(?:Thời điểm khách gửi tin này|Lịch tham chiếu)[^\n]*\n?", re.MULTILINE | re.IGNORECASE
)

_INJECTION = re.compile(
    "|".join(
        (
            # "ignore / forget the previous instructions"
            r"\b(?:ignore|disregard|forget|override)\b.{0,30}\b(?:instructions?|rules?|prompts?|guidelines?)\b",
            r"\b(?:bỏ qua|phớt lờ|quên|bỏ hết|vô hiệu)\b.{0,30}\b(?:hướng dẫn|chỉ dẫn|chỉ thị|quy tắc|luật|lệnh|prompt)\b",
            # asking for the hidden instructions
            r"\b(?:system|developer)\s*(?:prompt|message|instructions?)\b",
            r"(?:lời nhắc|chỉ dẫn|hướng dẫn|cấu hình) (?:hệ thống|gốc|ban đầu|ẩn)",
            r"\b(?:reveal|show|print|repeat|tiết lộ|in ra|nhắc lại|cho xem)\b.{0,30}\b(?:prompt|hướng dẫn|chỉ dẫn)\b",
            # changing who the assistant is
            r"\b(?:jailbreak|DAN mode|developer mode|god mode)\b",
            r"\b(?:you are now|from now on you are|act as|pretend (?:to be|you are))\b",
            r"(?:từ giờ|từ bây giờ|bây giờ) (?:bạn|mày|em) (?:là|đóng vai)",
            r"\b(?:đóng vai|giả làm|giả vờ là|nhập vai)\b",
            # markup imitating the conversation roles
            r"</?\s*(?:system|assistant|tool)\s*>|\[\s*(?:SYSTEM|INST)\s*\]|<\|im_start\|>",
        )
    ),
    re.IGNORECASE,
)

INJECTION_REPLY = (
    "Em là trợ lý của BookingBot, chỉ hỗ trợ tìm căn Vinhomes đã được Chủ đầu tư xác thực và đặt lịch xem nhà "
    "trực tiếp với chủ căn. Em không thể thay đổi vai trò hay quy tắc làm việc của mình. "
    "Anh/chị đang tìm căn ở dự án nào, ngân sách khoảng bao nhiêu ạ?"
)


@dataclass
class InputVerdict:
    text: str  # what the model receives
    blocked: bool = False  # answered with INJECTION_REPLY, the model is not called
    flags: list[str] = field(default_factory=list)


def screen_input(message: str) -> InputVerdict:
    # NFKC folds look-alike characters (full-width letters...) used to slip past the patterns
    text = unicodedata.normalize("NFKC", message)
    text = re.sub(r"[​-‏⁠﻿]", "", text)
    flags: list[str] = []
    text, n = _FORGED_CONTEXT.subn("", text)
    if n:
        flags.append("forged_context")
    if _INJECTION.search(text):
        flags.append("prompt_injection")
    text, pii = mask_pii(text)
    flags += [f"pii_{kind}" for kind in pii]
    text = text.strip() or message.strip()
    return InputVerdict(text=text, blocked="prompt_injection" in flags, flags=flags)


# ---------- Output ----------

# Sentence ends: . ! ? followed by a space, or a line break (not the dot inside "S1.08-2410")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_NEGATION = re.compile(r"\b(?:không|chưa|chẳng|ko|hông|đừng|không thể|từ chối)\b", re.IGNORECASE)
_CONDITION = re.compile(r"\b(?:khi|sau khi|nếu|ngay khi|lúc|một khi|chờ|đợi)\b", re.IGNORECASE)

_CONFIRMED_CLAIM = re.compile(
    r"đã được (?:chủ căn |chủ nhà )?(?:xác nhận|chấp nhận|duyệt)"
    r"|(?:chủ căn|chủ nhà) đã (?:đồng ý|xác nhận|chấp nhận|nhận lịch)"
    r"|lịch (?:xem )?(?:nhà )?đã (?:được )?(?:chốt|xác nhận)"
    r"|(?:em|mình) đã xác nhận (?:lịch|buổi xem)",
    re.IGNORECASE,
)
_CONFIRMED_STATUS = re.compile(r'"status":\s*"CONFIRMED"')

# Unit codes: S1.08-2410, GS3-1206, W2-0911 (not deal codes like VH-2026-00128: no digit before the dash)
_UNIT_CODE = re.compile(r"(?<![\w.])[A-Z]{1,3}\d{1,2}(?:\.\d{1,2})?-\d{3,4}(?![\w-])")

_COMMITMENTS: dict[str, re.Pattern[str]] = {
    "payment": re.compile(
        r"số tài khoản|\bSTK\b|chuyển khoản (?:vào|tới|đến|qua|cho)|(?:đặt|nộp|chuyển) (?:tiền )?cọc"
        r"|thanh toán (?:qua|tại|ngay|trước)|nhận (?:tiền )?(?:cọc|thanh toán)|giữ chỗ bằng",
        re.IGNORECASE,
    ),
    "negotiation": re.compile(
        r"(?:em|mình|tôi) (?:sẽ |đã )?(?:thương lượng|đàm phán|xin giảm|deal giá|ép giá)"
        r"|(?:chủ căn|chủ nhà) (?:đã |sẽ )?(?:đồng ý|chấp nhận|chịu) (?:giảm|bớt|hạ)"
        r"|giá (?:chốt|cuối cùng|sau giảm) (?:là|còn)",
        re.IGNORECASE,
    ),
    "price_prediction": re.compile(
        r"(?:sẽ|dự kiến|dự báo|chắc chắn|có thể) (?:tăng|lên|giảm|đạt) (?:giá )?(?:khoảng |tới |lên |thêm )?\d"
        r"|giá (?:sẽ|dự kiến|dự báo) (?:tăng|lên|giảm|đạt)|(?:lãi|lời|sinh lời) (?:khoảng |tới )?\d+ ?%",
        re.IGNORECASE,
    ),
    "legal_commitment": re.compile(
        r"(?:giao dịch|hợp đồng|mua bán|thương vụ)[^.!?]{0,20}? (?:đã |đã được )?(?:xác nhận|hoàn tất|chốt|thành công)"
        r"|(?:em|mình|bookingbot|hệ thống) (?:cam kết|bảo đảm|đảm bảo) (?:về )?(?:pháp lý|sổ|giao dịch|giá)",
        re.IGNORECASE,
    ),
}

_FALLBACKS = {
    "unconfirmed_claim": (
        "Lịch xem chỉ có hiệu lực khi chủ căn xác nhận; hiện em chưa thấy chủ căn xác nhận lịch này. "
        'Anh/chị xem trạng thái mới nhất ở mục Lịch xem, hoặc hỏi em "lịch xem của tôi thế nào" để em kiểm tra lại.'
    ),
    "unknown_unit": (
        "Em chưa tìm thấy căn đó trong dữ liệu của hệ thống. Anh/chị cho em biết dự án, ngân sách và số phòng ngủ "
        "để em tìm các căn đã được xác thực nhé."
    ),
    "payment": (
        "BookingBot không nhận thanh toán hay đặt cọc, và em không cung cấp thông tin chuyển khoản. "
        "Em có thể giúp anh/chị đặt lịch xem căn trực tiếp với chủ căn; các bước giao dịch sau đó do Chủ đầu tư hỗ trợ."
    ),
    "negotiation": (
        "Em không thể thương lượng hay thay đổi giá thay chủ căn. Anh/chị có thể trao đổi trực tiếp với chủ căn "
        "trong buổi xem nhà; em giúp anh/chị đặt lịch xem nhé?"
    ),
    "price_prediction": (
        "Em không định giá hay dự đoán giá căn hộ. Em có thể cho anh/chị xem giá chủ căn đang chào và "
        "so sánh với các căn tương tự đang có trên hệ thống."
    ),
    "legal_commitment": (
        "Em không thể xác nhận giao dịch hay cam kết về pháp lý. Các bước này do Chủ đầu tư hỗ trợ khi hai bên "
        "muốn tiếp tục sau buổi xem nhà."
    ),
}
_FALLBACK_PREFIX = "Em xin lỗi, câu trả lời vừa rồi của em chưa chính xác nên em đã ẩn đi. "


@dataclass
class OutputVerdict:
    text: str  # the reply shown to the buyer and kept in the conversation
    violations: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.violations)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


def _asserts(pattern: re.Pattern[str], sentence: str, allow_condition: bool = False) -> bool:
    """The sentence states the pattern as a fact: not negated (and, for claims, not a condition)."""
    if not pattern.search(sentence) or _NEGATION.search(sentence):
        return False
    return allow_condition or not _CONDITION.search(sentence)


def _known_text(history: Sequence[BaseMessage]) -> str:
    """Everything the reply may quote: tool results and what the buyer wrote."""
    return "\n".join(m.text for m in history if isinstance(m, ToolMessage | HumanMessage))


def screen_output(reply: str, history: Sequence[BaseMessage]) -> OutputVerdict:
    """Check the agent's reply against the conversation so far (`history` includes this turn's tool results)."""
    sentences = _sentences(reply)

    blocking: list[str] = []
    if any(_asserts(_CONFIRMED_CLAIM, s) for s in sentences):
        tool_text = "\n".join(m.text for m in history if isinstance(m, ToolMessage))
        if not _CONFIRMED_STATUS.search(tool_text):
            blocking.append("unconfirmed_claim")
    known = _known_text(history)
    if any(code not in known for code in _UNIT_CODE.findall(reply)):
        blocking.append("unknown_unit")
    for kind, pattern in _COMMITMENTS.items():
        if any(_asserts(pattern, s, allow_condition=True) for s in sentences):
            blocking.append(kind)

    if blocking:
        return OutputVerdict(text=_FALLBACK_PREFIX + _FALLBACKS[blocking[0]], violations=blocking)

    text, pii = mask_pii(reply)
    return OutputVerdict(text=text, violations=[f"pii_{kind}" for kind in pii])


def guarded_reply(message: AIMessage, verdict: OutputVerdict) -> AIMessage:
    """The reply message with the screened text; same id, so it replaces the original in the conversation.
    Plain text content: a model's thinking blocks for the discarded text are not kept."""
    return AIMessage(content=verdict.text, id=message.id, response_metadata=message.response_metadata)
