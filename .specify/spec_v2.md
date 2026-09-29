# AI SPEC --- AI Agent Direct Connect BĐS

**Tên sản phẩm:** AI Agent Direct Connect\
**Tên gọi trong MVP:** BookingBot AI Agent\
**Nhóm:** BĐS\
**Mã đề:** BDSO2O-04\
**Scope:** Vinhomes-only · MVP Web responsive · AI-first\
**Trạng thái:** Draft v2.0\
**Ngày:** 28/09/2026

------------------------------------------------------------------------

# 0. Executive Summary

## 0.1. Bài toán

Khách hàng có nhu cầu mua BĐS tại Vinhomes gặp khó khăn khi tìm đúng căn
phù hợp và chủ động đặt lịch xem nhà trong bối cảnh thông tin BĐS phân
tán và việc kết nối với chủ căn thường phụ thuộc vào Sale hoặc nhiều bên
trung gian.

Khách hàng hiện phải:

-   Tìm kiếm trên nhiều kênh.
-   Liên hệ nhiều Sale.
-   Cung cấp thông tin cá nhân cho nhiều bên.
-   Chờ xác nhận căn và lịch xem.
-   Trao đổi nhiều lần để tìm đúng căn.

Điều này dẫn đến:

-   Mất thời gian.
-   Khó xác minh căn còn khả dụng.
-   Phụ thuộc vào trung gian.
-   Có nguy cơ thông tin cá nhân được tiếp cận bởi nhiều bên.
-   Bị làm phiền bởi nhiều cuộc gọi/tin nhắn.
-   Khó chủ động trong hành trình mua.

Ở chiều ngược lại, **chủ sở hữu có nhu cầu bán** chưa có một kênh trực
tiếp hiệu quả để tiếp cận Buyer có nhu cầu thực.

Trong khi đó, **Chủ đầu tư** có thể xác thực thông tin Property/Owner
nhưng chưa có một lớp AI đủ tốt để tự động kết nối nhu cầu mua với nguồn
cung có nhu cầu bán.

## 0.2. Giải pháp

**AI Agent Direct Connect** là trợ lý AI-first giúp:

> **Buyer nhập nhu cầu → AI hiểu & matching → tìm căn đã xác thực →
> Buyer yêu cầu xem → AI kết nối Seller → AI khớp lịch → Owner xác nhận
> → xem nhà → tạo Deal → chuyển sang quy trình Chủ đầu tư khi cần.**

Mô hình hướng tới:

> **Buyer → AI Agent → Seller**

Trong đó:

> **Chủ đầu tư = Trust & Transaction Layer**

Chủ đầu tư xác thực:

-   Owner.
-   Property.
-   Trạng thái căn.
-   Các bước giao dịch cần kiểm soát.

## 0.3. Giá trị cốt lõi

### Buyer

> **Tìm đúng căn -- ít trung gian -- ít chia sẻ thông tin -- chủ động
> lịch xem.**

### Seller

> **Tiếp cận đúng Buyer -- không phải phụ thuộc nhiều Sale -- chủ động
> lịch xem.**

### Chủ đầu tư

> **Sở hữu nguồn cung xác thực -- kiểm soát hành trình giao dịch -- tăng
> giao dịch trực tiếp trong hệ sinh thái.**

## 0.4. Phạm vi MVP

### In scope

-   Chỉ BĐS thuộc hệ sinh thái Vinhomes.
-   Responsive Web.
-   AI-first; Buyer bắt đầu bằng hội thoại.
-   Seller có thể đăng ký nhu cầu bán.
-   Property phải được Chủ đầu tư/Operator duyệt trước khi xuất hiện.
-   AI matching Buyer--Property.
-   AI điều phối lịch Buyer--Seller.
-   Owner xác nhận lịch.
-   Tạo Deal ID cho mỗi kết nối.
-   Bảo vệ thông tin cá nhân bằng progressive disclosure.
-   Viewing hold chỉ có nghĩa là **giữ căn phục vụ buổi xem**, không
    phải giữ căn để mua.
-   Các trường hợp ngoại lệ được chuyển Human/Chủ đầu tư.

### Out of scope

-   Thanh toán.
-   Đặt cọc.
-   Ký hợp đồng.
-   AI định giá.
-   Dự đoán giá.
-   AI đàm phán giá.
-   AI tự xác nhận giao dịch.
-   Voice AI/gọi điện tự động.
-   Marketplace BĐS ngoài Vinhomes.
-   CRM/Sale ngoài hệ thống.

------------------------------------------------------------------------

# §1. User & Job / Evidence

## 1.1. Actors

  -----------------------------------------------------------------------
  Actor                   Mục tiêu                Quyền chính
  ----------------------- ----------------------- -----------------------
  **Buyer**               Tìm căn, xem nhà, kết   Chat AI, search,
                          nối Seller              recommendation,
                                                  booking, viewing,
                                                  
  **Seller/Owner**        Đăng bán căn, tiếp cận  CRUD listing,
                          Buyer phù hợp           availability, nhận
                                                  request, xác nhận lịch,
                                                  xem Deal

  **Investor/Operator**   Xác thực nguồn cung và  Duyệt listing, quản lý
                          giám sát vận hành       Owner, Property, Deal,
                                                  booking, exception

  **AI Agent**            Điều phối hành trình    Understand, match,
                                                  schedule, notify,
                                                  workflow orchestration

  **Human Operator**      Xử lý ngoại lệ và điểm  Verify, resolve
                          cần quyết định          conflict, transaction
                                                  support
  -----------------------------------------------------------------------

> **Operator = Chủ đầu tư trong MVP.**

## 1.2. User Job-to-be-Done

### Buyer

> "Khi tôi có nhu cầu mua một căn Vinhomes, tôi muốn mô tả nhu cầu bằng
> ngôn ngữ tự nhiên, được AI tìm đúng căn và kết nối trực tiếp với chủ
> căn để đặt lịch xem mà không phải liên hệ nhiều Sale hoặc chia sẻ
> thông tin cá nhân cho nhiều bên."

### Seller

> "Khi tôi có căn Vinhomes cần bán, tôi muốn có một kênh chính thức để
> đăng bán, tiếp cận Buyer phù hợp và chủ động quản lý lịch xem mà không
> phải phụ thuộc vào nhiều trung gian."

### Investor/Operator

> "Khi có nhiều Buyer, Seller và Property, tôi muốn kiểm soát nguồn
> cung, xác thực các bên và giám sát hành trình từ kết nối đến giao dịch
> mà giảm điều phối thủ công."

## 1.3. Evidence / Research

### Problem

Các benchmark trong SPEC gốc hỗ trợ ba nhu cầu chính:

-   Discovery/search để tìm đúng BĐS.
-   Conversational search để mô tả nhu cầu tự nhiên.
-   Online scheduling để giảm trao đổi qua lại khi đặt lịch.

Các benchmark này là **evidence hỗ trợ cơ chế sản phẩm**, không phải
baseline KPI trực tiếp cho Vinhomes.

### Product gap

Các capability thường xuất hiện riêng rẽ:

1.  Discovery/search.
2.  Conversational search.
3.  Tour scheduling.
4.  Scheduling infrastructure.

Sản phẩm hướng tới kết hợp chúng trong một flow hẹp cho Vinhomes:

> **Natural-language need → recommendation → verified property → direct
> owner connection → scheduling → viewing → Deal.**

------------------------------------------------------------------------

# §2. Impact & Quyết định

## 2.1. Impact Hypothesis

Nếu AI Agent có thể:

1.  Hiểu nhu cầu Buyer.
2.  Tìm Property phù hợp.
3.  Kết nối Buyer với Seller đã xác thực.
4.  Hạn chế chia sẻ PII không cần thiết.
5.  Tự động tìm khoảng thời gian giao nhau.
6.  Tạo Deal ID.
7.  Chuyển Human khi có exception.

thì có thể:

-   Giảm thời gian tìm kiếm.
-   Giảm số lượng Sale/trung gian Buyer phải tiếp xúc.
-   Giảm việc chia sẻ thông tin cá nhân không cần thiết.
-   Giảm cuộc gọi/tin nhắn không mong muốn.
-   Tăng số Buyer tiếp cận Seller phù hợp.
-   Tăng số giao dịch được thực hiện trong hệ sinh thái Chủ đầu tư.

## 2.2. Success Metrics

  Metric                                                 Target MVP Vai trò
  -------------------------------- -------------------------------- ------------
  Recommendation Precision@5                                   ≥85% Primary
  Viewing booking success rate                                 ≥80% Primary
  Double-booking rate                                           ≤1% Critical
  Availability accuracy                                        ≥95% Critical
  AI response latency p95                                   ≤5 giây UX
  Buyer phải tiếp xúc nhiều Sale               Giảm so với baseline Business
  Unwanted contact rate                        Giảm so với baseline Privacy
  Seller → qualified Buyer match                      TBD qua pilot Business
  Human escalation rate              Theo dõi, chưa đặt target cứng Operations

> Các target là product targets ban đầu và cần calibration bằng dữ liệu
> pilot thực tế.

## 2.3. Product Principles

1.  **AI-first, không AI-only:** AI điều phối; business rules và Human
    quyết định các hành động có tính cam kết.
2.  **Direct connection:** giảm phụ thuộc vào Sale/trung gian ở Search →
    Match → Connect → Schedule.
3.  **Privacy by design:** không chia sẻ toàn bộ thông tin Buyer cho
    Seller/Sale ngay từ đầu.
4.  **Database là Source of Truth:** AI chỉ sử dụng dữ liệu
    Property/Seller đã có trong hệ thống.
5.  **Owner verification:** Seller phải được xác thực trước khi Property
    được đưa vào marketplace.
6.  **Human approval:** các điểm có quyền cam kết hoặc rủi ro cao phải
    có Human.
7.  **Atomic booking:** không cho hai Buyer cùng đặt cùng một căn trong
    cùng thời điểm.
8.  **Fail safely:** AI không chắc chắn → hỏi lại hoặc chuyển Human.

------------------------------------------------------------------------

# §3. Nghiên cứu / Giải pháp tương tự

## 3.1. Pattern tham khảo

MVP tham khảo các pattern:

-   Conversational search.
-   Structured filtering.
-   Recommendation/ranking.
-   Direct owner connection.
-   Availability scheduling.
-   Human approval.
-   Transactional booking.
-   Progressive disclosure.
-   Deal tracking.
-   RBAC.
-   Audit log.

## 3.2. Khoảng trống sản phẩm

Sản phẩm không định vị là:

> "Một website đăng tin BĐS khác."

và cũng không chỉ là:

> "Một chatbot tư vấn BĐS."

Điểm khác biệt là:

> **AI Agent biến nhu cầu Buyer thành một kết nối được xác thực với
> Seller, sau đó điều phối lịch xem và chuyển Deal vào quy trình của Chủ
> đầu tư.**

------------------------------------------------------------------------

# §4. Thiết kế

## 4.1. Core Product Slice

> **Buyer discovery → AI matching → Verified Property → Direct Seller
> Connection → AI Scheduling → Owner approval → Viewing → Deal →

## 4.2. Actor Flow

``` text
BUYER
  │
  ▼
AI AGENT
  │
  ├── Understand Need
  ├── Search Property
  ├── Rank / Explain
  │
  ▼
VERIFIED PROPERTY
  │
  ▼
Buyer chọn "Tôi muốn xem"
  │
  ▼
CREATE DEAL ID
  │
  ▼
Seller nhận Viewing Request
  │
  ▼
AI Scheduling
  │
  ├── Có slot chung
  │       ↓
  │   Owner Confirm
  │       ↓
  │   Viewing Hold
  │
  └── Không có slot / Exception
          ↓
       HUMAN
          ↓
      Alternative
```

## 4.3. Augment / Automate / Human-in-the-loop

  -----------------------------------------------------------------------
  Tác vụ                  Mode                    Quy tắc
  ----------------------- ----------------------- -----------------------
  Hiểu nhu cầu Buyer      Automate                AI extract criteria

  Tìm Property            Automate                Tool + database

  Ranking                 Automate                Matching engine

  Giải thích              Automate                Chỉ dựa dữ liệu thật
  recommendation                                  

  Kiểm tra availability   Automate                Read-only

  Tạo viewing request     Automate                Kiểm tra quyền

  Tìm slot chung          Automate                Intersection

  Owner xác nhận lịch     **HITL**                Owner bắt buộc xác nhận

  Viewing hold            Automate                Sau confirmation

  Seller không phản hồi   **HITL**                Operator xử lý

  Không có slot chung     **HITL** nếu AI không   Operator hỗ trợ
                          giải quyết được         

  Property có vấn đề      **HITL**                Operator verify

  Reminder                Automate                T-24h/T-2h


  Chat                    Automate theo rule      Sau viewing hợp lệ

  Đàm phán giá            Không làm               Buyer ↔ Seller

  Xác nhận giao dịch      Human                   Ngoài quyền AI
  -----------------------------------------------------------------------

## 4.4. Customer Journey

``` text
Landing
 ↓
AI Chat
 ↓
Collect Requirements
 ↓
Search + Matching
 ↓
Recommended Properties
 ↓
Property Detail
 ↓
"Tôi muốn xem"
 ↓
Create Deal ID
 ↓
Seller receives request
 ↓
AI checks Buyer/Seller availability
 ↓
Owner confirms
 ↓
Viewing Hold
 ↓
Reminder
 ↓
Customer views
 ↓
 ↓
Buyer ↔ Seller Chat
 ↓
Transaction Support / Human
```

## 4.5. Seller Journey

``` text
Owner Login
 ↓
"My Property"
 ↓
"I want to sell"
 ↓
Input selling information
 ↓
Owner Verification
 ↓
Listing Review
 ↓
APPROVED
 ↓
AVAILABLE
 ↓
AI Matching
 ↓
Receive qualified Buyer request
 ↓
Confirm viewing
 ↓
Viewing
 ↓
Purchase Interest
 ↓
Deal
```

## 4.6. Seller Acquisition

### Nguồn Seller

**A. Owner chủ động**

> "Tôi muốn bán căn này."

**B. AI phát hiện Selling Intent**

Ví dụ Owner hỏi:

> "Giá căn này hiện nay bao nhiêu?"

> "Tôi muốn bán căn này thì thủ tục thế nào?"

AI có thể hỏi:

> "Bạn có muốn đăng ký nhu cầu bán căn này không?"

AI **không tự đăng bán**.

**C. Kênh Chủ đầu tư**

-   App.
-   Website.
-   CSKH.
-   Ban quản lý.
-   Hotline.

→ dẫn Owner vào Seller Portal.

## 4.7. Privacy / Direct Connection

### Nguyên tắc

> **Buyer không cần cung cấp số điện thoại cho nhiều Sale chỉ để tìm một
> căn.**

### Level 1 --- Anonymous Matching

Seller chỉ nhận:

``` text
Buyer ID
Budget range
Property preference
Viewing preference
```

### Level 2 --- Viewing

Hai bên xác nhận lịch.

### Level 3 --- Continue Transaction

Khi Buyer/Seller muốn tiếp tục, hệ thống mới chia sẻ thông tin cần thiết
theo policy.

### Level 4 --- Transaction

Chủ đầu tư hỗ trợ quy trình.

## 4.8. Scheduling Logic

Buyer:

> Thứ 7: 14h--17h

Seller:

> Thứ 7: 14h30--16h

AI tính:

``` text
Intersection = 14h30–16h
```

Đề xuất:

> 14h30 / 15h / 15h30

Buyer chọn:

> 15h

Seller:

> Confirm

→ **Booking Confirmed**

### HITL trong Scheduling

AI tự xử lý lịch bình thường.

Human can thiệp khi:

-   Seller không phản hồi.
-   Không có slot chung.
-   Lịch conflict.
-   Seller thay đổi lịch.
-   Property thay đổi trạng thái.
-   Có nhiều Buyer cùng yêu cầu một Property.

## 4.9. Deal ID

Mỗi quan hệ:

> **Buyer + Seller + Property**

tạo một:

> `Deal ID`

Ví dụ:

`VH-2026-00128`

### Deal Lifecycle

``` text
MATCHED
 ↓
VIEWING_REQUESTED
 ↓
VIEWING_CONFIRMED
 ↓
VIEWED
 ↓
INTERESTED
 ↓
NEGOTIATING
 ↓
TRANSACTION_SUPPORT
 ↓
COMPLETED / CLOSED
```

## 4.10. Anti-circumvention / Giao dịch ngoài hệ thống

Không giả định hệ thống có thể ngăn tuyệt đối Buyer và Seller giao dịch
ngoài.

Thay vào đó, platform tạo giá trị:

-   Verified Seller.
-   Verified Property.
-   Deal ID.
-   Lịch sử kết nối.
-   Hỗ trợ hồ sơ.
-   Hỗ trợ giao dịch.
-   Transaction Officer.
-   Quy trình chính thức.

### Deal Attribution

Nếu Buyer và Seller đã được kết nối qua `Deal ID`, Chủ đầu tư có thể đối
chiếu:

> **Buyer + Seller + Property + Deal ID**

để ghi nhận nguồn giao dịch.

> Cơ chế attribution window và chính sách phí là TBD, cần được quyết
> định với Chủ đầu tư.

## 4.11. Property Lifecycle

``` text
DRAFT
 ↓
PENDING_REVIEW
 ↓
APPROVED / AVAILABLE
 ↓
VIEWING_HELD
 ↓
AVAILABLE
 ↓
SOLD
```

Rules:

-   `PENDING_REVIEW`: không xuất hiện.
-   `APPROVED`: được matching.
-   `VIEWING_HELD`: chỉ khóa trong viewing window.
-   Hết viewing window → release.
-   `SOLD`: không recommendation/booking.

## 4.12. Booking Lifecycle

``` text
REQUESTED
 ↓
OWNER_CONFIRMED
 ↓
VIEWING_HELD
 ↓
COMPLETED
```

Nhánh:

``` text
REQUESTED → REJECTED
CONFIRMED → CANCELLED
CONFIRMED → RESCHEDULE_REQUESTED
```

Rules:

-   Owner bắt buộc xác nhận.
-   Buyer có thể hủy.
-   Đổi lịch cần Owner xác nhận.
-   Hệ thống phải ngăn double-booking.

## 4.13. Viewing Hold

Trong MVP:

> **Hold = tạm khóa căn để phục vụ buổi xem, KHÔNG phải giữ căn để
> mua.**

Rules:

1.  Chỉ hold sau Owner confirmation.
2.  Gắn với Deal + Buyer + time window.
3.  Không hold ngoài viewing window.
4.  Hết window → release.
5.  Atomic.
6.  Không có double booking.


Sau khi Buyer đã xem:

``` text
Customer
   ↓
   ↓
Seller
   ↓
Buyer ↔ Seller Chat
```

AI:

-   Không đàm phán giá.
-   Không xác nhận giao dịch.
-   Không nhận tiền.
-   Không đặt cọc.

Nếu cần hỗ trợ:

> **Human Operator / Chủ đầu tư**

## 4.15. Screens

### Buyer

1. Login.
2. AI Chat.
3. Recommendation.
4. Property Detail.
5. Viewing Request.
6. Booking / Viewing Status.
7. My Bookings.
8. Viewing reminder/status.

### Seller

1. Dashboard.
2. My Properties.
3. Sell Property.
4. Listing Management.
5. Viewing Availability.
6. Viewing Requests.
7. Booking / Viewing Management.

### Operator

1. Dashboard.
2. Property moderation.
3. Owner verification.
4. Booking / viewing monitoring.
5. Exception queue.
6. Audit / operational monitoring.

> Purchase Request, Buyer ↔ Seller Chat và transaction screens không thuộc MVP.

## 4.16. Core Data Model

``` text
User
BuyerProfile
SellerProfile
Project
Building
Property
PropertyMedia
PropertyAvailability
Deal
Booking
PropertyHold
PurchaseRequest
Chat
Message
Notification
AIConversation
AIMessage
Recommendation
AuditLog
```

Quan hệ chính:

``` text
Seller 1 ── N Property
Buyer 1 ── N Deal
Property 1 ── N Deal
Deal 1 ── N Booking
Booking 1 ── 0..1 PropertyHold
Deal 1 ── 0..1 PurchaseRequest
Deal 1 ── 0..1 Chat
```

## 4.17. Authentication & Authorization

  Actor      Authentication
  ---------- ------------------------
  Buyer      Phone + OTP
  Seller     Phone/Email + OTP
  Operator   Email + Password + 2FA

Rules:

-   RBAC.
-   Seller chỉ xem Buyer data cần thiết.
-   Buyer không xem PII của Seller nếu chưa được phép.
-   Chat chỉ mở khi đủ điều kiện.
-   Audit log cho hành động quan trọng.

## 4.18. AI Tools

### Read tools

``` text
search_properties
get_property_detail
get_seller_status
check_property_availability
check_seller_availability
get_deal_status
```

### Action tools

``` text
create_viewing_request
confirm_viewing
cancel_viewing
reschedule_viewing
create_property_hold
release_property_hold
open_chat
send_notification
create_human_escalation
```

### Tool Policy

-   LLM không truy cập DB trực tiếp.
-   Tool kiểm tra authorization.
-   Tool kiểm tra business rule.
-   Write action phải validate state.
-   AI không bypass Owner approval.
-   AI không truy cập PII ngoài quyền.

## 4.19. Notification

### Events

-   Seller có viewing request mới.
-   Seller xác nhận/từ chối.
-   Booking confirmed.
-   Viewing hold created/released.
-   Sắp đến giờ xem.
-   Listing được approve/reject.

### Reminder

-   T-24h.
-   T-2h.

------------------------------------------------------------------------

# §5. Kiểu lỗi

  Error                 Ví dụ                      Expected behavior
  --------------------- -------------------------- -------------------------
  Missing information   Thiếu ngân sách            AI hỏi
  No match              Không có căn phù hợp       Đề xuất alternative
  Seller unavailable    Seller không có lịch       Đề xuất Seller/căn khác
  No common slot        Hai lịch không giao nhau   Đề xuất lịch khác/Human
  Owner rejection       Owner từ chối              Alternative
  Concurrent booking    Hai Buyer cùng chọn        Atomic transaction
  Stale property        Căn vừa bán                Không booking
  Unauthorized action   AI truy cập PII            Reject
  Seller unverified     Owner chưa xác thực        Không cho booking
  System failure        API/DB/LLM lỗi             Fallback Human
  Deal conflict         Deal đã đóng               Reject action

------------------------------------------------------------------------

# §6. Bốn đường đi trải nghiệm

## 6.1. Happy Path

``` text
Buyer
 ↓
AI hiểu nhu cầu
 ↓
Matching
 ↓
Chọn căn
 ↓
Create Deal
 ↓
Seller nhận request
 ↓
AI khớp lịch
 ↓
Seller xác nhận
 ↓
Viewing Hold
 ↓
Buyer xem
 ↓
 ↓
Buyer ↔ Seller
```

## 6.2. Correction Path

Buyer:

> "Tôi tăng ngân sách lên 6 tỷ và ưu tiên view hồ."

``` text
Existing Profile
 ↓
Update criteria
 ↓
Re-run matching
 ↓
New recommendations
```

## 6.3. Exception Path

Buyer chọn 15h nhưng Seller vừa có lịch khác.

``` text
Check availability
 ↓
Slot unavailable
 ↓
AI thông báo
 ↓
Suggest 15h30 / 16h
 ↓
Buyer chọn
 ↓
Seller confirm
```

Nếu không giải quyết được:

> **Human Operator**

## 6.4. Fallback Path

``` text
System/AI Error
 ↓
Stop unsafe action
 ↓
Preserve context
 ↓
Create escalation
 ↓
Human handles
 ↓
Customer receives status
```

------------------------------------------------------------------------

# §7. Kiểm thử

## 7.1. Functional Test Areas

### Buyer

-   Login.
-   AI search.
-   Recommendation.
-   Property detail.
-   Viewing request.
-   Scheduling.
-   Cancellation.
-   Reschedule.

### Seller

-   Registration.
-   Verification.
-   Listing.
-   Availability.
-   Booking approval.
-   Buyer request.
-   Deal.

### Operator

-   Listing moderation.
-   Seller verification.
-   Booking monitoring.
-   Deal monitoring.
-   Exception handling.

## 7.2. AI Evaluation

Golden set tối thiểu:

> **≥20 scenarios**

Các nhóm test:

1.  Requirement extraction.
2.  Hard constraints.
3.  Soft preferences.
4.  Ranking.
5.  Explanation.
6.  Tool selection.
7.  Tool arguments.
8.  Permission.
9.  Privacy.
10. Scheduling.
11. Deal state.
12. Hallucination.
13. Exception.
14. Human escalation.

## 7.3. Critical Acceptance Criteria

### AC-01 --- Không hallucinate Property

**Given:** Database không có căn phù hợp.

**Then:** AI không được tự tạo căn.

### AC-02 --- Direct Connection

**Given:** Buyer chọn Property.

**Then:** Hệ thống tạo Deal ID và gửi request tới Seller phù hợp.

### AC-03 --- Privacy

**Given:** Buyer chưa xác nhận tiếp tục giao dịch.

**Then:** Seller không được tự động nhận số điện thoại/email của Buyer.

### AC-04 --- Seller Verification

**Given:** Seller chưa được xác thực.

**Then:** Property không được phép booking.

### AC-05 --- Owner Approval

**Given:** Buyer gửi viewing request.

**Then:** Booking không được `CONFIRMED` nếu Seller chưa xác nhận.

### AC-06 --- Scheduling

**Given:**

Buyer: `14h–17h`

Seller: `14h30–16h`

**Then:** AI phải tìm intersection `14h30–16h`.

### AC-07 --- No Common Slot

**Given:** Không có intersection.

**Then:** AI đề xuất alternative hoặc escalate Human.

### AC-08 --- Atomic Hold

**Given:** Hai Buyer đồng thời yêu cầu cùng Property/time.

**Then:** Không quá một booking/hold hợp lệ.

### AC-09 --- Deal Tracking

Khi Buyer yêu cầu xem:

> Deal ID phải được tạo.

### AC-10 --- Transaction Protection

AI không được:

-   Xác nhận giao dịch.
-   Nhận tiền.
-   Đặt cọc.
-   Thay đổi giá.
-   Tự xác nhận pháp lý.

------------------------------------------------------------------------

# §8. Phân công & kế hoạch

  Workstream   Scope
  ------------ -------------------------------------------
  Product/PM   Problem, PRD, business rules, KPI
  AI/Agent     Prompt, orchestration, tools, evaluation
  Backend      API, DB, Deal, Booking, Hold
  Frontend     Chat, Property, Booking, Seller dashboard
  Data         Property/Seller data, matching
  QA           Functional + AI + concurrency
  DevOps       Deployment, monitoring
  Security     Auth, RBAC, PII

## MVP Implementation Phases

### Phase 1 --- Foundation

-   Auth/RBAC.
-   Buyer/Seller/Operator.
-   Property schema.
-   Listing moderation.

### Phase 2 --- AI Discovery

-   AI Chat.
-   Requirement extraction.
-   Property search.
-   Ranking.
-   Recommendation.

### Phase 3 --- Direct Connection & Booking

-   Seller availability.
-   Deal creation.
-   Viewing request.
-   AI scheduling.
-   Owner approval.
-   Atomic hold.

### Phase 4 --- Post-viewing

-   Reminder.
-   Buyer--Seller chat.

### Phase 5 --- Operations

-   Operator dashboard.
-   Exception queue.
-   Deal monitoring.
-   Analytics.
-   Audit logs.

### Phase 6 --- Evaluation

-   Golden set.
-   AI regression tests.
-   Concurrency tests.
-   KPI instrumentation.
-   Pilot measurement.

------------------------------------------------------------------------

# §9. Technical Architecture Proposal

## 9.1. Recommended Stack

  Layer          Recommendation                   Lý do
  -------------- -------------------------------- ------------------------------------------
  Frontend       Next.js + TypeScript             Responsive web
  Backend        Python + FastAPI                 AI/data workload
  Database       PostgreSQL                       Transaction + relational state
  Search         PostgreSQL Full-text + pg_trgm   Đủ cho MVP
  Vector DB      Không bắt buộc MVP               Recommendation chủ yếu structured
  LLM            Gemini/OpenAI API                Conversational extraction + tool calling
  Agent          LangGraph                        Stateful workflow + branching
  Auth           JWT + OTP                        Web/API
  Media          S3                               Ảnh/video
  Chat           WebSocket                        Realtime
  Notification   SMS/Zalo/In-app                  TBD provider
  Deployment     Docker                           Portable
  Monitoring     Logs + Metrics + Audit           Observability

## 9.2. Architecture

``` text
              BUYER
                │
              SELLER
                │
                ▼
       ┌──────────────────┐
       │   WEB FRONTEND   │
       └────────┬─────────┘
                ▼
       ┌──────────────────┐
       │    FASTAPI       │
       └────────┬─────────┘
                │
       ┌────────▼─────────┐
       │    AI AGENT      │
       │                  │
       │ Understand       │
       │ Match            │
       │ Schedule         │
       │ Orchestrate      │
       └────────┬─────────┘
                │
       ┌────────▼─────────┐
       │   TOOL LAYER     │
       └────────┬─────────┘
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
 Property    Scheduling   Deal
 Database      Engine     Manager
     │          │          │
     └──────────┼──────────┘
                ▼
        ┌───────────────┐
        │   OPERATOR    │
        │   HUMAN HITL  │
        └───────────────┘
```

## 9.3. Security Boundary

``` text
LLM
 ↓
Agent Tool Layer
 ↓
Authorization
 ↓
Business Rules
 ↓
Service Layer
 ↓
Database
```

> **Không cho LLM truy cập Database trực tiếp.**

## 9.4. Recommendation Architecture

``` text
Buyer Natural Language
        ↓
LLM Extraction
        ↓
Structured Buyer Profile
        ↓
Hard Filter
        ↓
Candidate Properties
        ↓
Soft Preference Scoring
        ↓
Priority Weight
        ↓
Top-N
        ↓
Explanation
```

## 9.5. Scheduling Architecture

``` text
Buyer Availability
        │
        ▼
Seller Availability
        │
        ▼
Intersection
        │
        ▼
Candidate Slots
        │
        ▼
Buyer Selection
        │
        ▼
Seller Confirmation
        │
        ▼
Viewing Hold
```

------------------------------------------------------------------------

# §10. Open Questions / TBD

1.  Chủ đầu tư lấy Seller từ những kênh nào?
2.  Seller có được miễn phí đăng căn không?
3.  Phí giao dịch/service fee là bao nhiêu?
4.  Ai là bên trả phí?
5.  Phí tính theo transaction hay service package?
6.  Nếu Buyer/Seller giao dịch ngoài hệ thống thì attribution được xác
    định thế nào?
7.  Deal attribution window bao lâu?
8.  Seller không phản hồi booking trong bao lâu thì escalate?
9.  Buyer/Seller được chia sẻ PII ở level nào?
10. Khi nào được mở chat?
11. Khi nào Seller được xem số điện thoại Buyer?
12. Viewing window bao lâu?
13. Có buffer giữa hai lịch xem không?
14. Nếu một Property có nhiều Buyer thì priority rule thế nào?
15. Chính sách cancellation/no-show?
16. Human Operator thuộc bộ phận nào?
17. Transaction Officer tham gia ở bước nào?
18. Provider SMS/Zalo nào?
19. Chính sách lưu trữ/xóa PII và chat?
20. Baseline hiện tại về số cuộc gọi Sale/Buyer?
21. Baseline thời gian từ nhu cầu → viewing?
22. Cơ chế phí và incentive nào khiến Buyer/Seller tiếp tục giao dịch
    trên platform thay vì giao dịch ngoài hệ thống?

------------------------------------------------------------------------

# §11. Final MVP Boundary

## MUST HAVE

-   Buyer authentication.
-   Seller authentication.
-   AI-first chat.
-   Natural-language requirement extraction.
-   Property search.
-   AI recommendation.
-   Property detail.
-   Seller registration.
-   Seller listing.
-   Owner verification.
-   Operator moderation.
-   Availability management.
-   Direct Buyer--Seller connection.
-   Deal ID.
-   Viewing request.
-   AI scheduling.
-   Owner approval.
-   Atomic viewing hold.
-   Reminder.
-   RBAC.
-   PII protection.
-   Human escalation.
-   Audit log.
-   Analytics.

## MUST NOT HAVE

-   Payment.
-   Deposit.
-   E-contract.
-   AI valuation.
-   Price prediction.
-   Mortgage.
-   AI negotiation.
-   AI transaction confirmation.
-   Automatic phone calls.
-   Voice AI.
-   External CRM.
-   BĐS ngoài Vinhomes.
-   AI tự thu thập PII từ bên ngoài.
-   AI tự chia sẻ PII.
-   AI tự xác nhận giao dịch.

------------------------------------------------------------------------

# §12. One-line Product Definition

> **AI Agent giúp khách hàng tìm đúng BĐS Vinhomes, kết nối trực tiếp
> với chủ căn và tự động khớp lịch xem, giảm sự phụ thuộc vào Sale và
> hạn chế việc chia sẻ thông tin cá nhân cho nhiều bên, đồng thời để Chủ
> đầu tư xác thực nguồn cung, kiểm soát Deal và can thiệp tại các điểm
> cần Human-in-the-loop.**

## Core Demo Flow

``` text
BUYER
  ↓
"Tôi cần căn 2PN ~5 tỷ"
  ↓
AI MATCHING
  ↓
3 CĂN PHÙ HỢP
  ↓
Buyer chọn căn
  ↓
DEAL ID
  ↓
SELLER ĐÃ XÁC THỰC
  ↓
AI KHỚP LỊCH
  ↓
SELLER CONFIRM
  ↓
VIEWING HOLD
  ↓
XEM NHÀ
  ↓
XEM NHÀ
  ↓
MVP END
```

## Product Positioning

> **Không phải AI thay thế Sale.**
>
> **AI giảm sự phụ thuộc vào Sale ở các khâu tìm kiếm, matching, kết nối
> và đặt lịch; con người vẫn tham gia ở những điểm cần tư vấn, xác thực
> và xử lý giao dịch.**
