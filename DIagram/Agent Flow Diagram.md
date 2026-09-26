# Agent Flow Diagram

> Sơ đồ luồng hoạt động của **BookingBot AI Agent** theo đặc tả [spec_updated.md](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/.specify/spec_updated.md): Từ bóc tách nhu cầu tự nhiên, tìm kiếm/xếp hạng căn Vinhomes, kiểm tra lịch trống, tạo yêu cầu booking, quy trình Chủ nhà (Owner) phê duyệt, kích hoạt Viewing Hold, nhắc lịch đến mở kênh chat trực tiếp sau khi xem nhà.

```mermaid
graph TD
    %% 1. User & Intent Stage
    CR([Khách hàng: Nhập tin nhắn / Yêu cầu tìm kiếm]) --> INTENT[AI Agent: Natural Language Understanding]
    INTENT --> EXTRACT[Trích xuất nhu cầu có cấu trúc: Budget, PN, Diện tích, Phân khu, Hướng, Tầng]
    
    %% Missing Info Check
    EXTRACT --> CHK_INFO{Đã đủ tiêu chí lọc cơ bản?}
    CHK_INFO -- Chưa đủ / Mơ hồ --> ASK[Agent: Hỏi thêm thông tin làm rõ]
    ASK --> CR
    
    %% Tool Selection & Recommendation
    CHK_INFO -- Đủ tiêu chí --> SELECT_ACTION[Agentic Tool Selection: Chọn công cụ phù hợp]
    
    SELECT_ACTION -- Tìm kiếm BĐS Vinhomes --> T_SEARCH[search_properties: PostgreSQL Hard Filter + Soft Scoring]
    SELECT_ACTION -- Xem chi tiết căn --> T_DETAIL[get_property_detail: Căn hộ Approved / Available]
    SELECT_ACTION -- Kiểm tra lịch xem --> T_AVAIL[check_availability: Lịch trống của căn hộ & chủ nhà]
    SELECT_ACTION -- Đặt lịch xem nhà --> T_BOOK[create_booking_request: Tạo yêu cầu lịch xem]
    SELECT_ACTION -- Đổi lịch xem --> T_RESCHED[reschedule_booking: Yêu cầu đổi slot mới]
    SELECT_ACTION -- Hủy lịch xem --> T_CANCEL[cancel_booking: Khách hàng tự hủy booking]

    %% 2. Backend Security & Execution Pipeline (Source of Truth)
    subgraph BackendPipeline["FastAPI Backend Pipeline (Source of Truth)"]
        VAL_SCHEMA[1. Pydantic Schema & Parameter Validation]
        VAL_AUTH[2. Authentication & RBAC Check: JWT / OTP]
        VAL_BIZ[3. Business Rules Validation: Căn Approved, Đúng khung giờ]
        TX_LOCK[4. Atomic Lock & Transaction: Kiểm tra xung đột lịch]
        EXEC_OP[5. Thực thi nghiệp vụ & Ghi nhận Audit Log]
    end

    T_SEARCH --> VAL_SCHEMA
    T_DETAIL --> VAL_SCHEMA
    T_AVAIL --> VAL_SCHEMA
    T_BOOK --> VAL_SCHEMA
    T_RESCHED --> VAL_SCHEMA
    T_CANCEL --> VAL_SCHEMA

    VAL_SCHEMA --> VAL_AUTH
    VAL_AUTH --> VAL_BIZ
    VAL_BIZ --> TX_LOCK
    TX_LOCK --> EXEC_OP

    %% 3. Outcome & Fail-safe Handling
    VAL_BIZ -- Xung đột lịch / Dữ liệu không hợp lệ --> ERR_BIZ[Trả lỗi cấu trúc: Conflict / Out of bounds]
    VAL_AUTH -- Không có quyền truy cập --> ERR_AUTH[Trả lỗi cấu trúc: 403 Forbidden]
    VAL_SCHEMA -- Sai tham số --> ERR_SCHEMA[Trả lỗi cấu trúc: 422 Validation Error]

    ERR_BIZ --> TOOL_RES[Tool Result trả về cho AI Agent]
    ERR_AUTH --> TOOL_RES
    ERR_SCHEMA --> TOOL_RES
    EXEC_OP --> TOOL_RES

    %% 4. Agent Observation & Output
    TOOL_RES --> OBSERVE[AI Agent: Quan sát kết quả từ Backend]
    
    OBSERVE --> CHECK_RES{Loại kết quả?}
    
    CHECK_RES -- Có lỗi / Conflict --> HANDLE_ERR[Agent giải thích rõ ràng & Đề xuất căn / slot khác]
    HANDLE_ERR --> RESP([Phản hồi cho Khách hàng trên Web Chat])

    CHECK_RES -- Kết quả Tìm kiếm / Chi tiết --> REC_ENGINE[Gợi ý Top-N căn + Lời giải thích: Explainability]
    REC_ENGINE --> RESP

    CHECK_RES -- Tạo yêu cầu Booking --> BOOKING_REQUESTED[Trạng thái Booking: REQUESTED]
    
    %% 5. Owner Approval (HITL) & Viewing Hold Lifecycle
    subgraph OwnerLifecycle["Quy trình Chủ nhà (Owner Approval & Viewing Hold)"]
        NOTIF_OWNER[Hệ thống thông báo cho Chủ nhà: In-app / SMS]
        OWNER_DECISION{Chủ nhà duyệt lịch xem?}
        
        OWNER_DECISION -- Từ chối (Reject) --> REJECT_STATE[Trạng thái: REJECTED]
        REJECT_STATE --> ALT_SUGGEST[Hệ thống gợi ý slot / căn thay thế cho khách]
        
        OWNER_DECISION -- Đồng ý (Approve) --> CONFIRM_STATE[Trạng thái Booking: CONFIRMED]
        CONFIRM_STATE --> CREATE_HOLD[Kích hoạt Viewing Hold: Tạm khóa căn trong khung giờ xem]
        CREATE_HOLD --> REMINDERS[Lên lịch nhắc hẹn tự động: T-24h và T-2h]
    end

    BOOKING_REQUESTED --> NOTIF_OWNER
    NOTIF_OWNER --> OWNER_DECISION
    ALT_SUGGEST --> RESP
    
    %% 6. Post-Viewing & Direct Chat
    subgraph PostViewing["Giai đoạn sau khi xem nhà (Post-Viewing)"]
        VIEWING_DONE[Khách đến xem nhà thực tế]
        VIEWING_DONE --> PURCHASE_REQ[Khách gửi Yêu cầu mua / thuê: Purchase Request]
        PURCHASE_REQ --> UNLOCK_CHAT[Hệ thống tự động Mở kênh Chat trực tiếp: Khách ↔ Chủ nhà]
        UNLOCK_CHAT --> DIRECT_TALK([Khách & Chủ nhà trao đổi trực tiếp qua WebSocket])
    end

    REMINDERS --> VIEWING_DONE
```