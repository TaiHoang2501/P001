# Agent Flow Diagram

> Một lượt chat của người mua đi qua **BookingBot AI Agent** như thế nào, theo code hiện tại
> (`src/api/routers/chat.py` → `src/services/chat_service.py` → `src/agents/graph.py` / `tools.py` / `guardrails.py`).
> Đặc tả: [`.specify/spec_final.md`](../.specify/spec_final.md); quy tắc đang chạy: [`CLAUDE.md`](../CLAUDE.md).

## 1. Một lượt chat (từ tin nhắn tới câu trả lời)

```mermaid
graph TD
    MSG([Người mua / khách chưa đăng nhập gửi tin nhắn]) --> GATE_API

    subgraph Entry["API chat: /chat, /chat/stream, /chat/guest, /chat/guest/stream"]
        GATE_API{Trợ lý AI đang bật?<br/>kill switch của dev}
        GATE_API -- Tắt --> OFF[503 AI_DISABLED<br/>khung chat báo bảo trì + tổng đài]
        GATE_API -- Bật --> RL{Trong giới hạn tần suất?<br/>theo tài khoản / IP khách / trần ngày}
        RL -- Vượt --> LIMIT[429 RATE_LIMITED]
    end

    RL -- OK --> IN_GUARD

    subgraph InGuard["Guardrails đầu vào"]
        IN_GUARD[Che SĐT / email / CCCD / số thẻ<br/>bỏ dòng giả mạo thời điểm gửi]
        IN_GUARD --> INJ{Nghi prompt injection / jailbreak?<br/>regex, giám khảo AI khi có dấu hiệu}
    end
    INJ -- Có --> FIXED[Trả lời cố định<br/>không gọi model, không vào bộ nhớ agent]

    INJ -- Không --> AGENT

    subgraph Graph["LangGraph: agent ⇄ tools (bộ nhớ hội thoại = checkpoint PostgreSQL)"]
        AGENT[Node agent: LLM nhận prompt + lịch ngày tháng<br/>+ tiêu chí đã nhớ của khách buyer_memory]
        AGENT --> NEED{Cần gọi tool?}
        NEED -- Có --> TOOLS[Node tools: 12 tool]
        TOOLS --> AGENT
    end

    LLM[["LLM theo LLM_PROVIDER<br/>Gemini / OpenAI / Claude / OpenRouter / Groq<br/>lỗi → model dự phòng"]]
    AGENT <--> LLM

    NEED -- Không, đã có câu trả lời --> OUT_GUARD

    subgraph OutGuard["Guardrails đầu ra (StreamGate khi streaming: gửi từng câu đã kiểm tra)"]
        OUT_GUARD[Che SĐT / email trong câu trả lời]
        OUT_GUARD --> RISK{Vi phạm?<br/>nói đã xác nhận mà không có tool CONFIRMED<br/>mã căn không có trong kết quả tool<br/>đặt cọc / chuyển khoản, đàm phán / dự đoán giá,<br/>cam kết pháp lý}
        RISK -- Có chủ đề rủi ro --> JUDGE[Giám khảo AI model nhỏ<br/>bắt câu lách luật / tha câu chặn nhầm]
    end
    JUDGE --> RISK2{Kết luận vi phạm?}
    RISK -- Không --> REPLY
    RISK2 -- Không --> REPLY
    RISK -- Vi phạm dữ liệu --> SAFE
    RISK2 -- Có --> SAFE[Thay bằng câu an toàn<br/>SSE gửi sự kiện replace, sửa cả state LangGraph]
    SAFE --> REPLY

    REPLY([Câu trả lời + thẻ căn / giờ đề xuất / trạng thái lịch<br/>ghi ai_conversations, ai_messages, ai_turns, audit_logs AI_GUARDRAIL])
```

## 2. Tool của agent và đường đi tới Database

```mermaid
graph LR
    subgraph Read["Tool đọc"]
        T1[list_projects]
        T2[search_properties<br/>SQL hard filter + soft scoring]
        T3[get_property_detail]
        T4[get_seller_status<br/>không trả PII]
        T5[check_seller_availability]
        T6[check_property_availability]
        T7[get_deal_status]
        T8[get_booking_status]
    end
    subgraph Act["Tool hành động"]
        A1[create_viewing_request<br/>tạo / tái dùng Deal + Booking REQUESTED]
        A2[cancel_viewing]
        A3[reschedule_viewing]
        A4[create_human_escalation]
    end

    Read --> API[agent_api.py<br/>quyền của chính khách đang chat]
    Act --> API

    subgraph Pipeline["Service layer (cùng pipeline với web)"]
        P1[1. Pydantic validation]
        P2[2. Xác thực + RBAC<br/>khách chưa đăng nhập → UNAUTHENTICATED]
        P3[3. Business rules: căn AVAILABLE, người bán VERIFIED,<br/>Deal chưa đóng, đúng trạng thái, đúng khung giờ,<br/>báo trước tối thiểu VIEWING_MIN_NOTICE_MINUTES]
        P4[4. Transaction + khóa dòng + exclusion constraint]
        P5[5. Ghi Deal / Booking, audit_logs, notifications]
        P1 --> P2 --> P3 --> P4 --> P5
    end
    API --> P1
    P5 --> DB[(PostgreSQL)]
    P2 -. lỗi có cấu trúc .-> RES[Kết quả tool trả cho agent]
    P3 -. lỗi có cấu trúc .-> RES
    P5 --> RES
```

Không có tool xác nhận lịch, tạo / nhả hold, gửi thông báo hay đọc SĐT/email: xác nhận lịch là việc của chủ căn
trên web, hold do Service tạo trong cùng transaction xác nhận và job nền nhả, thông báo do Service gửi. Agent chỉ
báo "đã gửi yêu cầu" sau khi tool trả kết quả thành công từ Backend. Khách chưa đăng nhập mà muốn đặt lịch → tool
trả `UNAUTHENTICATED`, web hiện khung đăng ký SĐT + OTP rồi gửi tiếp yêu cầu.

## 3. Sau khi agent gửi yêu cầu xem (ngoài lượt chat)

```mermaid
graph TD
    REQ[Booking REQUESTED<br/>gửi thẳng cho chủ căn, Operator không duyệt] --> OWNER{Chủ căn trả lời trên web}
    OWNER -- Xác nhận --> CONF[CONFIRMED + Viewing Hold ACTIVE<br/>cùng transaction]
    CONF --> SUPER[Yêu cầu khác của cùng chủ căn trùng giờ → REJECTED<br/>agent nhắn người mua kèm giờ khác]
    CONF --> REMIND[Nhắc lịch T-24h / T-2h<br/>agent viết lời nhắc cho từng khách]
    REMIND --> VIEW[Buổi xem]
    VIEW --> OUTCOME[Chủ căn ghi: Đã xem xong / Khách không đến<br/>quá 48h → UNREPORTED]
    OUTCOME --> FEEDBACK[Người mua: Quan tâm → Deal INTERESTED<br/>Chưa phù hợp → Deal CLOSED, agent gợi ý căn khác<br/>Không đồng ý → ca VIEWING_DISPUTE cho Operator]
    OWNER -- Từ chối, có thể đề xuất tối đa 3 giờ --> REJ[REJECTED<br/>người mua bấm một giờ = yêu cầu mới cùng Deal]
    OWNER -- Quá hạn respond_by --> ESC[Ca SELLER_NO_RESPONSE cho Operator<br/>agent follow-up gợi ý giờ / căn khác]
    OWNER -- Tới giờ xem vẫn chưa trả lời --> EXP[EXPIRED, người mua được báo]
```

MVP kết thúc tại buổi xem: Purchase Request, chat trực tiếp Người mua ↔ Chủ căn và các bước giao dịch là post-MVP.
