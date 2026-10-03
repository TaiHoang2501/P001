# Data Flow Diagram (Sơ đồ Luồng Dữ liệu)

> Dữ liệu đi qua hệ thống **BookingBot AI Agent** như thế nào, theo đúng code hiện tại (nhánh `feature/Baor-app`):
> ai gửi gì, đi qua lớp nào, được ghi vào bảng nào và ai được đọc lại. Database PostgreSQL là nguồn sự thật;
> AI Agent không truy cập DB trực tiếp mà luôn đi qua Tool Layer → Service Layer.

---

## 1. Tổng quan luồng dữ liệu (Level 1)

```mermaid
flowchart LR
    %% ---------- Tác nhân ----------
    BUYER(["Người xem nhà<br/>(khách hoặc đã đăng nhập)"])
    SELLER(["Người bán nhà"])
    OPER(["Chủ đầu tư / Quản trị viên"])

    %% ---------- Giao diện ----------
    subgraph WEB["Web React + Vite (Vercel)"]
        W_BUYER["Khu người mua /buyer/*<br/>chat, chi tiết căn, chọn giờ, theo dõi Deal"]
        W_SELLER["Cổng người bán /owner/*<br/>sổ đỏ, tin đăng, lịch trống, yêu cầu xem"]
        W_OPER["Bảng Chủ đầu tư /operator/*<br/>duyệt người bán, duyệt tin, ngoại lệ"]
    end

    %% ---------- Backend ----------
    subgraph API["FastAPI (Render)"]
        AUTH["Auth: OTP / JWT<br/>phân quyền theo vai trò"]
        CHAT["Chat service<br/>/chat, /chat/guest, /claim"]
        SVC["Service layer<br/>property · booking · deal · hold<br/>ownership · seller · notification · escalation"]
        JOBS["Job nền<br/>hết hạn giữ căn, nhắc lịch T-24h/T-2h<br/>agent follow-up: gợi ý giờ/căn khác"]
    end

    subgraph AI["AI Agent"]
        AGENT["LangGraph agent<br/>nhận mục tiêu, tự gọi tool đến khi xong"]
        TOOLS["Agent tools<br/>tìm căn · khớp lịch · đặt/đổi/hủy · chuyển người thật"]
    end
    LLM[["Gemini API<br/>flash, dự phòng flash-lite"]]

    %% ---------- Kho dữ liệu ----------
    subgraph DB["PostgreSQL (Neon)"]
        D_ID[("Danh tính + trí nhớ khách<br/>users · otp_codes · seller_profiles<br/>buyer_profiles (tiêu chí, giờ rảnh)")]
        D_RB[("Sổ đỏ<br/>property_ownership_verifications")]
        D_INV[("Kho căn<br/>projects · buildings · properties<br/>property_media · availability_slots")]
        D_DEAL[("Giao dịch xem<br/>deals · bookings · property_holds")]
        D_AI[("AI<br/>ai_conversations · ai_messages · recommendations<br/>checkpoint* (bộ nhớ hội thoại)")]
        D_OPS[("Vận hành<br/>notifications · escalations · audit_logs")]
    end

    %% ---------- Người mua ----------
    BUYER -- "nhu cầu bằng lời, SĐT + OTP" --> W_BUYER
    W_BUYER -- "tin nhắn" --> CHAT
    CHAT -- "lượt chat" --> AGENT
    AGENT -- "prompt + lịch sử" --> LLM
    LLM -- "trả lời / lệnh gọi tool" --> AGENT
    AGENT --> TOOLS
    TOOLS -- "gọi qua kiểm tra quyền + quy tắc" --> SVC
    CHAT -- "lưu lượt chat (người đã đăng nhập)" --> D_AI
    AGENT <-- "lịch sử hội thoại" --> D_AI
    TOOLS -- "nhớ tiêu chí + giờ rảnh" --> D_ID
    W_BUYER -- "đặt lịch trực tiếp, xem lịch của tôi" --> SVC

    %% ---------- Người bán ----------
    SELLER -- "SĐT + OTP, tên + mã sổ đỏ, tin đăng" --> W_SELLER
    W_SELLER --> AUTH
    W_SELLER --> SVC

    %% ---------- Chủ đầu tư ----------
    OPER -- "email + mật khẩu, quyết định duyệt" --> W_OPER
    W_OPER --> AUTH
    W_OPER --> SVC

    %% ---------- Ghi / đọc DB ----------
    AUTH <--> D_ID
    SVC <--> D_RB
    SVC <--> D_INV
    SVC <--> D_DEAL
    SVC --> D_OPS
    SVC -- "cập nhật trạng thái người bán" --> D_ID
    JOBS <--> D_DEAL
    JOBS -- "đọc tiêu chí, giờ rảnh" --> D_ID
    JOBS -- "gợi ý cho khách" --> D_OPS

    %% ---------- Dữ liệu trả về ----------
    SVC -. "căn phù hợp, giờ trống, Deal + trạng thái" .-> W_BUYER
    SVC -. "yêu cầu xem: chỉ mã người mua + khoảng ngân sách" .-> W_SELLER
    SVC -. "hàng chờ duyệt, lịch xem, ngoại lệ" .-> W_OPER
```

**Đọc sơ đồ:** người mua chỉ nói chuyện với AI Agent; mọi thao tác của agent (tìm căn, khớp lịch, đặt lịch)
đều đi qua cùng Service layer với web, nên cùng kiểm tra quyền và quy tắc nghiệp vụ. Chủ căn không bao giờ
nhận số điện thoại hay email của người mua (privacy Level 1).

---

## 2. Luồng chính: người mới chat → đặt lịch → chủ căn xác nhận

```mermaid
sequenceDiagram
    autonumber
    actor B as Người xem nhà (khách)
    participant W as Web (khu người mua)
    participant API as FastAPI
    participant AG as AI Agent + Gemini
    participant DB as PostgreSQL
    actor S as Chủ căn

    B->>W: "Tôi cần căn 2PN ở Ocean Park, dưới 3,5 tỷ"
    W->>API: POST /chat/guest (không cần tài khoản)
    API->>AG: lượt chat, user_id = trống
    AG->>DB: search_properties (đọc properties AVAILABLE của người bán đã xác thực)
    AG->>DB: check_property_availability (đọc availability_slots, bookings, property_holds)
    AG-->>W: trả lời + thẻ căn + giờ đề xuất
    B->>W: chọn giờ xem
    AG->>DB: create_viewing_request → bị từ chối (UNAUTHENTICATED), không ghi gì
    AG-->>W: needs_account + pending_viewing (căn + giờ đã chọn)
    W-->>B: hiện khung đăng ký SĐT + OTP
    B->>W: SĐT, mã OTP, họ tên
    W->>API: /auth/otp/request, /auth/otp/verify
    API->>DB: ghi otp_codes (chỉ hash), tạo users + buyer_profiles
    W->>API: POST /chat/guest/{id}/claim
    API->>AG: chuyển lịch sử chat khách sang tài khoản mới
    W->>API: POST /bookings (căn + giờ đã chọn)
    API->>DB: tạo/tái dùng deals, tạo bookings REQUESTED, ghi audit_logs, notifications
    API-->>W: mã Deal VH-2026-xxxxx, "Chờ chủ căn xác nhận"
    S->>API: xác nhận yêu cầu xem (cổng người bán)
    API->>DB: bookings CONFIRMED + property_holds ACTIVE (cùng transaction), deals cập nhật
    API->>DB: notifications cho người mua + nhắc lịch T-24h/T-2h
    Note over API,DB: Job nền: nhả hold khi hết khung giờ, gửi nhắc lịch đến hạn
```

---

## 3. Luồng người bán: xác thực sổ đỏ → đăng tin → Chủ đầu tư duyệt

```mermaid
sequenceDiagram
    autonumber
    actor S as Người bán
    participant W as Web (cổng người bán)
    participant API as FastAPI
    participant DB as PostgreSQL
    actor O as Chủ đầu tư

    S->>W: SĐT + OTP (không có mật khẩu)
    W->>API: /auth/otp/request, /auth/otp/verify (role OWNER)
    API->>DB: users + seller_profiles (UNVERIFIED)
    S->>W: họ tên người đứng tên + mã số sổ đỏ
    W->>API: POST /owner/ownership/claim
    API->>DB: đối chiếu property_ownership_verifications
    API->>DB: otp_codes (gửi tới owner_phone ghi trên sổ), sổ → OTP_SENT
    S->>W: nhập OTP
    W->>API: POST /owner/ownership/{id}/confirm
    API->>DB: sổ → VERIFIED, gắn user_id, seller_profiles → PENDING, ghi audit_logs
    Note over API,DB: Sai OTP 5 lần → sổ FAILED (khóa)
    S->>W: tạo tin đăng, chọn sổ đỏ đã xác thực
    W->>API: POST /owner/properties (verification_id)
    API->>DB: properties DRAFT (mỗi sổ chỉ một tin), rồi PENDING_REVIEW khi gửi duyệt
    O->>API: duyệt hồ sơ người bán, duyệt tin
    API->>DB: seller_profiles VERIFIED, properties AVAILABLE
    Note over API,DB: Chỉ căn AVAILABLE của người bán VERIFIED mới được AI gợi ý và nhận đặt lịch
```

---

## 4. Kho dữ liệu: ai ghi, ai đọc

| Kho (bảng) | Ghi bởi | Đọc bởi | Ghi chú |
|---|---|---|---|
| `users`, `otp_codes` | Auth (đăng nhập/đăng ký OTP) | Auth, mọi API cần đăng nhập | OTP chỉ lưu hash, hết hạn 5 phút, sai 5 lần thì hủy |
| `buyer_profiles` | Auth khi tạo người mua; agent ghi tiêu chí + giờ rảnh khi tìm căn / khớp lịch | Booking (chủ căn chỉ thấy ngân sách); prompt của agent ở các cuộc chat sau; job follow-up | Không chứa SĐT/email |
| `seller_profiles` | Auth, xác thực sổ đỏ, Chủ đầu tư | Duyệt tin, tìm căn | Chỉ người bán VERIFIED mới có căn được gợi ý |
| `property_ownership_verifications` | Seed từ dữ liệu Chủ đầu tư; xác thực sổ đỏ | Xác thực sổ đỏ, tạo tin đăng | Mỗi sổ gắn đúng một tin (`properties.verification_id`) |
| `properties`, `property_media` | Người bán; Chủ đầu tư duyệt | Agent (tìm căn), web | Giấy tờ sở hữu không bao giờ công khai |
| `availability_slots` | Người bán (lịch trống) | Khớp lịch | Seed bổ sung lịch demo 7 ngày tới |
| `deals`, `bookings` | Đặt lịch (web hoặc agent), chủ căn xác nhận/từ chối | Người mua, chủ căn, Chủ đầu tư | Chặn đặt trùng giờ bằng ràng buộc DB |
| `property_holds` | Khi chủ căn xác nhận; job nền nhả hold | Khớp lịch | Giữ căn cho buổi xem, không phải giữ để mua |
| `ai_conversations`, `ai_messages`, `recommendations` | Chat service (người đã đăng nhập) | Lịch sử chat | |
| `checkpoints`, `checkpoint_*` | LangGraph (bộ nhớ hội thoại, cả chat khách) | Agent mỗi lượt chat | Bảng do LangGraph tự tạo/migrate, Alembic bỏ qua |
| `notifications` | Booking, sổ đỏ, duyệt tin, job nhắc lịch, agent follow-up (`AGENT_FOLLOWUP`, `AGENT_NEW_MATCH`) | Chuông thông báo trên web (cả khu người mua) | Chưa có SMS/Zalo; mỗi gợi ý của agent gửi một lần (`dedupe_key`) |
| `escalations` | Agent (`create_human_escalation`) | Chủ đầu tư (hàng ngoại lệ) | Khi không có giờ chung, khách muốn gặp người thật… |
| `audit_logs` | Mọi hành động quan trọng | Kiểm tra, truy vết | |

**Bộ nhớ hội thoại** nằm trong PostgreSQL (`AGENT_MEMORY=postgres`), khởi động lại server không mất ngữ cảnh.
Nếu không kết nối được (vd. Windows chạy uvicorn không có `--reload`), server dùng RAM và ghi cảnh báo.
