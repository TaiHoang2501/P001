# AI SPEC --- BookingBot AI Agent · Trợ lý đặt lịch xem nhà & giữ căn

**Nhóm:** BĐS\
**Mã đề:** BDSO2O-04\
**Scope:** Vinhomes-only · MVP Web responsive · AI-first\
**Trạng thái:** Draft v1.0 --- tổng hợp từ phỏng vấn yêu cầu\
**Ngày:** 25/09/2026

------------------------------------------------------------------------

## 0. Executive Summary

### 0.1 Bài toán

Khách hàng có nhu cầu mua BĐS tại Vinhomes gặp khó khăn khi tìm đúng BĐS
phù hợp và đặt lịch xem nhà trong bối cảnh thông tin BĐS phân tán. Khách
phải tự tìm kiếm trên nhiều kênh, liên hệ Sale/chủ nhà và chờ phản
hồi/xác nhận lịch. Điều này làm tăng thời gian tìm kiếm, khó tìm đúng
căn và có thể khiến khách bị làm phiền bởi nhiều cuộc gọi.

### 0.2 Giải pháp

**BookingBot AI Agent** là trợ lý AI-first trên web, giúp khách:

> Nhập nhu cầu bằng hội thoại → AI thu thập tiêu chí → tìm/lọc/xếp hạng
> căn Vinhomes phù hợp → khách chọn căn → xem thông tin → chọn thời gian
> → tạo yêu cầu booking → chủ nhà xác nhận → hệ thống giữ căn trong
> khoảng thời gian xem → nhắc lịch → khách đến xem → nếu muốn mua, gửi
> yêu cầu mua và mở chat với chủ nhà.

AI tự động xử lý phần lớn hành trình. Các hành động nghiệp vụ nhạy cảm
được kiểm soát bằng business rules và quyền của actor.

### 0.3 Phạm vi

-   Chỉ BĐS thuộc hệ sinh thái Vinhomes.
-   MVP là **responsive web app**, không xây mobile app.
-   AI-first; khách bắt đầu bằng chat.
-   Nguồn dữ liệu kiến thức của AI là database BookingBot do Chủ đầu
    tư/chủ nhà quản lý.
-   Chủ nhà tự đăng căn; căn chỉ được tìm kiếm sau khi Chủ đầu tư kiểm
    duyệt.
-   Không triển khai thanh toán/đặt cọc, ký hợp đồng, định giá AI, dự
    đoán giá, vay ngân hàng, tự đàm phán giá, hoàn tất giao dịch,
    CRM/Sales ngoài hệ thống, voice AI/gọi tự động.

------------------------------------------------------------------------

# §1. User & Job / Evidence

## 1.1 Actors

  -----------------------------------------------------------------------
  Actor                   Mục tiêu                Quyền chính
  ----------------------- ----------------------- -----------------------
  **Customer**            Tìm căn phù hợp, đặt    Chat AI, search/filter,
                          lịch, xem nhà và kết    xem căn, booking, hold
                          nối mua                 xem nhà, yêu cầu mua,
                                                  chat sau booking

  **Owner**               Đăng bán căn, quản lý   CRUD căn, lịch xem, xác
                          lịch và xử lý khách     nhận/từ chối booking,
                                                  xem khách, yêu cầu mua,
                                                  chat

  **Investor / Operator** Quản trị nguồn cung và  Quản lý dự án/tòa/căn,
                          giám sát vận hành       duyệt tin, quản lý
                                                  owner, booking/hold,
                                                  analytics
  -----------------------------------------------------------------------

> **Operator = Chủ đầu tư** trong scope này.

## 1.2 User Job

### Customer Job-to-be-Done

> "Khi tôi có nhu cầu mua một căn Vinhomes, tôi muốn mô tả nhu cầu bằng
> ngôn ngữ tự nhiên và được hệ thống tìm, giải thích, sắp xếp các căn
> phù hợp, sau đó giúp tôi đặt lịch xem và kết nối với chủ nhà mà không
> phải tự liên hệ nhiều kênh."

### Owner Job-to-be-Done

> "Khi tôi có căn Vinhomes cần bán, tôi muốn đăng và quản lý căn, lịch
> xem, booking và khách quan tâm trong một nơi."

### Investor / Operator Job-to-be-Done

> "Khi nhiều owner và booking phát sinh, tôi muốn kiểm soát chất lượng
> tin đăng, nguồn cung, trạng thái căn và hoạt động booking mà giảm đáng
> kể công sức điều phối thủ công."

## 1.3 Evidence / Market & Research Evidence

> **Nguyên tắc:** Phần này dùng evidence bên ngoài để kiểm chứng vấn đề và
> logic sản phẩm. Các target KPI ở §2.2 vẫn là **product targets**; không
> coi các số liệu của thị trường khác là baseline trực tiếp của BookingBot.

### A. Evidence về nhu cầu tìm đúng BĐS

- **NAR 2025 Profile of Home Buyers and Sellers:** 52% người mua nhà tìm
  được căn họ mua thông qua tìm kiếm online; median thời gian tìm nhà là 10
  tuần; **56%** người mua cho biết “finding the right property” là bước khó
  nhất trong quá trình mua nhà. Đây là evidence trực tiếp cho problem
  “tìm đúng căn” và lý do cần một lớp search/recommendation tốt hơn.
- **Realtor.com AI Search:** một khảo sát do Realtor.com công bố cho biết
  gần 2/3 người mua hiện tại/tiềm năng cảm thấy khó chịu vì không thể tìm
  kiếm bằng các tiêu chí thực sự quan trọng với họ; 62% muốn mô tả nhu cầu
  bằng ngôn ngữ tự nhiên và nhận kết quả có ý nghĩa. Điều này hỗ trợ hướng
  **AI-first conversational search** của BookingBot.

### B. Evidence về nhu cầu rút ngắn thời gian phản hồi/booking

- **Harvard Business Review – The Short Life of Online Sales Leads:** nghiên
  cứu về xử lý lead online cho thấy nhiều doanh nghiệp phản hồi quá chậm;
  nguồn này là cơ sở cho nguyên tắc “speed-to-lead” và việc giảm thời gian
  từ request → xử lý.
- **InsideSales Lead Response Study 2021:** phân tích hơn 55 triệu hoạt động
  bán hàng trên 5,7 triệu inbound leads tại hơn 400 công ty; báo cáo cho thấy
  conversion trong 5 phút đầu cao hơn đáng kể so với phản hồi muộn. Đây là
  evidence hỗ trợ target **≥90% request được xử lý trong 5 phút**, nhưng không
  nên diễn giải thành dự báo trực tiếp cho conversion BĐS Vinhomes.

### C. Evidence về online scheduling và reminder

- **Frontiers in Digital Health (2025):** nghiên cứu retrospective trên 16.894
  appointment tại một practice và 81.173 appointment tại một university
  hospital. Ở practice, no-show trung vị của appointment đặt online thấp hơn
  appointment offline (1,8% vs 5,9%); nghiên cứu cũng ghi nhận SMS reminder là
  một yếu tố hữu ích trong giảm no-show ở hospital. Evidence này hỗ trợ việc
  BookingBot có **online booking + reschedule/cancel + reminder T-24h/T-2h**,
  nhưng vì đây là healthcare nên chỉ dùng làm evidence về cơ chế scheduling,
  không dùng làm benchmark trực tiếp cho BĐS.

## 1.4 Benchmark: sản phẩm/dịch vụ tương tự

| Sản phẩm / dịch vụ | Họ giải quyết gì? | Giá trị khiến người dùng có lý do chọn | Rào cản / lý do có thể không phù hợp với BookingBot |
|---|---|---|---|
| **Zillow / Zillow AI Mode** | Conversational home discovery, kết nối listing data với hành động như tour scheduling và agent connection. | Một luồng liên tục từ tìm nhà → hiểu listing → hành động; AI hiểu câu hỏi tự nhiên và có thể dẫn tới booking tour. | Tập trung thị trường Mỹ; hệ sinh thái và dữ liệu khác Vinhomes. Không thể lấy trực tiếp làm mô hình dữ liệu/booking tại Việt Nam. |
| **Realtor.com** | Tìm nhà, AI-powered search và request/schedule private showing. | Cho phép mô tả nhu cầu bằng ngôn ngữ tự nhiên; request tour trực tiếp từ property detail; kết nối buyer với agent nhanh. | Mô hình phụ thuộc agent network của Mỹ; BookingBot cần Owner approval và inventory do hệ thống nội bộ quản lý. |
| **ShowingTime / Zillow Real-Time Touring** | Điều phối availability và booking tour giữa buyer/agent/listing. | Giảm back-and-forth về lịch; hiển thị slot và hỗ trợ schedule/reschedule/cancel; đã có quy mô sử dụng lớn trong hệ sinh thái Mỹ. | Đây chủ yếu là touring/scheduling infrastructure, không giải quyết đầy đủ discovery + recommendation + owner marketplace như BookingBot. |
| **Batdongsan.com.vn** | Marketplace tìm kiếm BĐS với filter, bản đồ, thông tin listing và dữ liệu thị trường. | Nguồn cung lớn, nhiều tiêu chí tìm kiếm; bản đồ giúp so sánh vị trí/giá và giảm việc chuyển giữa các ứng dụng. | Chủ yếu là search/listing marketplace; BookingBot đặt trọng tâm vào conversational discovery + booking orchestration + viewing hold. |

> **Lưu ý về “vì sao người dùng chọn/không chọn”:** các nguồn công khai trên
> chủ yếu mô tả tính năng, value proposition và một số kết quả nội bộ; không
> có cùng một bộ khảo sát độc lập để định lượng lý do người dùng chọn từng sản
> phẩm. Vì vậy bảng trên phân biệt **giá trị được sản phẩm công bố** với
> **rào cản/scope mismatch**, không khẳng định đây là tỷ lệ preference của
> người dùng.

### 1.5 Khoảng trống mà BookingBot nhắm tới

Từ benchmark trên có thể thấy các capability đã xuất hiện trên thị trường
nhưng thường tách rời:

1. **Discovery/search:** Batdongsan.com.vn, Zillow, Realtor.com.
2. **Conversational search:** Zillow AI Mode, Realtor.com AI Search.
3. **Tour scheduling:** Zillow, Realtor.com, ShowingTime.
4. **Scheduling infrastructure:** ShowingTime.

BookingBot kết hợp các capability này trong một flow hẹp cho **Vinhomes**:

> **Natural-language need → recommendation → real-time availability →
> Owner approval → atomic viewing hold → reminders → viewing → purchase
> request/chat.**

Đây là hypothesis sản phẩm cần được kiểm chứng bằng pilot; benchmark không
chứng minh rằng BookingBot chắc chắn tạo ra conversion uplift.

## 1.6 Nguồn tham khảo

- National Association of REALTORS®, *2025 Profile of Home Buyers and Sellers*.
- Realtor.com / NAR REALTOR® News, *Search It, How You Say It Comes to realtor.com®* (2025).
- Harvard Business Review, Oldroyd, McElheran & Elkington, *The Short Life of Online Sales Leads* (2011).
- InsideSales, *Lead Response Study 2021*.
- Frontiers in Digital Health, *Efficient patient care in the digital age: impact of online appointment scheduling...* (2025).
- Zillow, *Zillow debuts AI mode...* (2026).
- Zillow, *Booking an apartment tour used to mean waiting by the phone...* (2026).
- Realtor.com, *Find a Home and Schedule a Tour*.
- Realtor.com, *Scheduling property tours in the mobile app*.
- Batdongsan.com.vn, *Tính năng Bản đồ nhà đất*.
- Zillow / ShowingTime, *New ShowingTime feature brings real-time tour availability to brokerage sites*.

# §2. Impact & Quyết định

## 2.1 Impact hypothesis

Nếu BookingBot: 1. thu thập nhu cầu bằng hội thoại, 2. tự động tìm/xếp
hạng căn, 3. tự động kiểm tra availability, 4. điều phối booking và
notification, 5. giữ căn atomic trong khoảng thời gian xem,

thì có thể giảm thao tác điều phối của Operator, rút ngắn thời gian phản
hồi và giảm xung đột lịch/căn.

## 2.2 Success Metrics

| Metric | Target | Vai trò |
|---|---:|---|
| Double-booking rate | **≤ 1%** | **Primary** |
| Availability synchronization accuracy | **≥ 95%** | **Primary** |
| Recommendation Precision@5 | **≥ 85%** | **Primary** |
| AI response latency (p95) | **≤ 5 giây** | **Primary** |

### Định nghĩa metric mới

- **Recommendation Precision@5 ≥ 85%:** trong 5 căn đầu tiên AI đề xuất, ít nhất 85% kết quả được đánh giá là đáp ứng đúng các hard constraints và phù hợp với các preference chính của khách. Target 85% là mức đề xuất ban đầu và cần được calibration bằng evaluation set thực tế.
- **AI response latency (p95) ≤ 5 giây:** ít nhất 95% request AI phải nhận được phản hồi đầu tiên trong tối đa 5 giây. Có thể theo dõi thêm p50 latency để phân tích trải nghiệm điển hình.

## 2.3 Product principles

1.  **AI-first, nhưng không AI-only:** AI điều phối, business service
    quyết định quyền và trạng thái.
2.  **Database là source of truth:** AI chỉ tư vấn từ dữ liệu đã có
    trong hệ thống.
3.  **Human approval ở điểm có quyền cam kết:** chủ nhà phải xác nhận
    booking.
4.  **Atomic booking/hold:** không để hai request cùng giữ một căn trong
    cùng thời điểm.
5.  **Least privilege:** actor và AI tool chỉ được truy cập dữ liệu cần
    thiết.
6.  **Explainable recommendation:** khi đề xuất căn, hệ thống cần giải
    thích căn phù hợp theo tiêu chí khách.
7.  **Fail safely:** lỗi nghiệp vụ → xử lý/đề xuất thay thế; lỗi hệ
    thống → fallback người thật.
8.  **Không để LLM trực tiếp thao tác database.**

------------------------------------------------------------------------

# §3. Nghiên cứu / Giải pháp tương tự

## 3.1 Pattern cần tham khảo

MVP nên tham chiếu các pattern sản phẩm sau thay vì sao chép một sản
phẩm cụ thể:

-   Conversational search: dùng LLM để chuyển nhu cầu tự nhiên thành
    structured criteria.
-   Structured filtering: hard constraints loại căn không phù hợp.
-   Ranking: soft preferences + priority weighting + distance/proximity
    scoring.
-   Human-in-the-loop approval: yêu cầu owner xác nhận trước khi booking
    thành công.
-   Transactional booking/hold: action tạo booking/hold phải atomic.
-   Event-driven notification: booking, hold, reminder, purchase request
    tạo event.
-   RBAC + audit log: kiểm soát quyền và truy vết hành động.

### Ghi chú

Không sử dụng web search/RAG bên ngoài cho kiến thức Vinhomes trong MVP.
Nguồn dữ liệu được kiểm soát bởi database nội bộ.

------------------------------------------------------------------------

# §4. Thiết kế

## 4.1 Lát cắt sản phẩm

### Core slice

**Customer discovery → recommendation → booking → owner approval →
viewing hold → viewing → purchase request/chat**

### Non-goals

1.  Thanh toán hoặc đặt cọc online.
2.  Ký hợp đồng điện tử.
3.  Định giá BĐS bằng AI.
4.  Dự đoán giá tăng/giảm.
5.  Vay ngân hàng/mortgage.
6.  BĐS ngoài Vinhomes.
7.  AI tự đàm phán giá.
8.  Hoàn tất giao dịch mua bán.
9.  CRM/Sales bên ngoài.
10. Voice AI/gọi điện tự động.
11. Recommendation ngoài phạm vi Vinhomes.

## 4.2 Canvas / Actor Flow

``` mermaid
flowchart LR
    C[Customer] --> AI[BookingBot AI]
    AI --> SEARCH[Search + Recommendation]
    SEARCH --> P[Approved Properties]
    C --> B[Create Booking Request]
    B --> O[Owner]
    O -->|Approve| CONF[Confirmed Booking]
    O -->|Reject| ALT[Alternative Slot/Property]
    CONF --> HOLD[Viewing Hold]
    HOLD --> REM[24h + 2h Reminder]
    REM --> VIEW[Customer Views Property]
    VIEW --> BUY[Purchase Request]
    BUY --> CHAT[Customer ↔ Owner Chat]

    OWNER[Owner] --> LIST[Create/Edit/Delete Listing]
    LIST --> REVIEW[Investor/Operator Review]
    REVIEW -->|Approved| P

    OP[Investor / Operator] --> REVIEW
    OP --> MON[Booking/Hold Monitoring]
    OP --> ANA[Analytics]
```

## 4.3 Augment / Automate / Human-in-the-loop

  Tác vụ                      Mode                        Quy tắc
  --------------------------- --------------------------- ------------------------------------
  Hiểu nhu cầu khách          Automate                    AI trích xuất criteria
  Tìm căn                     Automate                    Tool/API + hard filters
  Ranking                     Automate                    Scoring engine
  Giải thích recommendation   Automate                    Chỉ dựa trên dữ liệu có thật
  Kiểm tra availability       Automate                    Read-only tool
  Tạo booking request         Automate                    Kiểm tra quyền + availability
  Xác nhận booking            **Human-in-the-loop**       Owner bắt buộc xác nhận
  Hold căn                    Automate sau confirmation   Atomic hold
  Nhắc lịch                   Automate                    24h + 2h
  Hủy booking                 Automate                    Customer có thể tự hủy
  Đổi lịch                    HITL                        Owner phải xác nhận
  Purchase request            Automate                    Tạo request sau khi viewing hợp lệ
  Mở chat                     Automate theo rule          Chỉ sau booking xem nhà thành công
  Đàm phán giá                Không làm                   Chủ nhà và khách tự trao đổi
  Xác nhận giao dịch          Không làm                   Ngoài scope
  System failure              Fallback                    Operator xử lý

## 4.4 Customer journey

``` text
Landing
  ↓
AI Chat
  ↓
Collect requirements
  ↓
Search + Filter + Ranking
  ↓
Recommended Property Cards
  ↓
Property Detail
  ↓
Choose viewing date/time
  ↓
Check availability
  ↓
Create Booking Request
  ↓
Owner confirms
  ├── Reject → Alternative
  └── Confirm
        ↓
Viewing Hold
        ↓
Reminder T-24h / T-2h
        ↓
Customer views
        ↓
Purchase Request
        ↓
Open Customer ↔ Owner Chat
```

## 4.5 Customer requirement schema

Các tiêu chí AI cần thu thập:

1.  Ngân sách.
2.  Mục đích: ở / đầu tư.
3.  Dự án / khu vực.
4.  Loại căn.
5.  Diện tích.
6.  Số phòng ngủ.
7.  Tầng.
8.  Hướng / view.
9.  Nội thất.
10. Thời gian đi xem.
11. Nhu cầu đặc biệt.

> Việc trường nào bắt buộc/optional cần được xác định bằng dữ liệu sử
> dụng thực tế; chưa tự áp đặt tất cả là required.

## 4.6 Recommendation logic

### Step 1 --- Hard constraints

Ví dụ:

``` text
budget
project
property_type
```

Nếu không đạt hard constraint → loại khỏi candidate set.

### Step 2 --- Soft preferences

Các yếu tố:

-   tầng
-   view
-   nội thất
-   diện tích
-   số phòng ngủ
-   nhu cầu đặc biệt

### Step 3 --- Priority weighting

Ngôn ngữ khách thể hiện mức ưu tiên:

-   "rất ưu tiên"
-   "ưu tiên"
-   "không quan trọng"

sẽ được chuyển thành priority weights.

### Step 4 --- Proximity score

Căn càng gần: - ngân sách mục tiêu, - diện tích mong muốn, - các
preference định lượng,

thì điểm càng cao.

### Step 5 --- Explainability

Mỗi recommendation nên trả về:

``` text
Property
Match score
Matched criteria
Unmatched / trade-off criteria
```

Trọng số cụ thể: **TBD**, cần calibration bằng dữ liệu thực tế.

------------------------------------------------------------------------

## 4.7 Property listing lifecycle

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
```

Nhánh:

``` text
PENDING_REVIEW → REJECTED
AVAILABLE → SOLD
```

### Rule

-   Căn `PENDING_REVIEW` không xuất hiện trong customer search.
-   Chỉ căn `APPROVED/AVAILABLE` mới có thể được recommendation/booking.
-   `VIEWING_HELD` chỉ khóa căn trong khoảng thời gian xem.
-   Hết thời gian xem → căn trở lại `AVAILABLE`, trừ khi trạng thái khác
    đã được cập nhật.

------------------------------------------------------------------------

## 4.8 Booking lifecycle

``` text
REQUESTED
   ↓
CONFIRMED
   ↓
COMPLETED
```

Các nhánh:

``` text
REQUESTED → REJECTED
CONFIRMED → CANCELLED
CONFIRMED → RESCHEDULE_REQUESTED → CONFIRMED
```

### Rules

-   Owner bắt buộc xác nhận trước khi booking được `CONFIRMED`.
-   Customer có thể tự hủy booking.
-   Đổi lịch cần Owner xác nhận.
-   Thời hạn hủy/đổi lịch: **TBD**.
-   System phải ngăn booking/hold concurrent gây double-booking.

------------------------------------------------------------------------

## 4.9 Viewing Hold

"Giữ căn" trong MVP có nghĩa:

> **Tạm khóa căn để phục vụ buổi xem nhà của khách, không phải giữ để
> mua.**

Rules:

1.  Chỉ tạo hold sau khi Owner xác nhận booking.
2.  Hold gắn với booking/customer/time window.
3.  Hold chỉ tồn tại trong khoảng thời gian xem.
4.  Không được giữ căn ngoài viewing window.
5.  Hết viewing window → release.
6.  Hold phải atomic.
7.  Không có hai active hold/booking xung đột cho cùng một căn và time
    window.
8.  Implementation cụ thể của lock/transaction: **TBD**.

------------------------------------------------------------------------

## 4.10 Purchase request

Điều kiện:

``` text
Booking = Confirmed/Completed viewing
```

Sau khi khách xem nhà:

``` text
Customer → Purchase Request → Owner
                         ↓
                       Chat
                         ↓
                 Customer ↔ Owner
```

-   Chat chỉ mở sau khi booking xem nhà thành công.
-   Owner và Customer tự trao đổi/chốt.
-   AI không đàm phán giá.
-   AI không xác nhận giao dịch.
-   Không thanh toán/đặt cọc trong MVP.

------------------------------------------------------------------------

## 4.11 Owner listing flow

``` text
Owner creates listing
        ↓
PENDING_REVIEW
        ↓
Investor/Operator reviews
   ├── Reject → Owner sees rejection reason
   └── Approve
          ↓
       AVAILABLE
          ↓
   Search/Recommendation
```

### Listing fields

-   Property ID / mã căn.
-   Project.
-   Building.
-   Floor.
-   Area.
-   Address.
-   Property type.
-   Bedrooms.
-   Selling price.
-   Direction/view.
-   Furnishing.
-   Images.
-   Videos.
-   Description.
-   Legal status.
-   Sale status.
-   Viewing availability.
-   Viewing-hold time policy.

------------------------------------------------------------------------

## 4.12 Screens

### Customer

1.  Login/Register.
2.  AI Chat.
3.  Search/Filter BĐS.
4.  Recommended properties.
5.  Property detail.
6.  Book viewing.
7.  My bookings/viewings.
8.  Current viewing holds.
9.  Purchase request / owner connection.

**Rule:** Purchase request/chat chỉ hiện sau khi booking xem nhà thành
công.

### Owner

1.  Dashboard.
2.  Property management.
3.  Add/Edit property.
4.  Viewing availability management.
5.  Booking management.
6.  Purchase request management.
7.  Customer chat.

**Rule:** Chat với customer chỉ hiện sau khi booking xem nhà thành công.

### Investor / Operator

1.  Admin dashboard.
2.  Project management.
3.  Building/property management.
4.  Owner listing moderation.
5.  Owner account management.
6.  Booking/hold monitoring.
7.  Reports/analytics.

------------------------------------------------------------------------

## 4.13 Data model

### Core entities

-   `User`
-   `CustomerProfile`
-   `OwnerProfile`
-   `InvestorOperatorProfile`
-   `Project`
-   `Building`
-   `Property`
-   `PropertyMedia`
-   `PropertyAvailability`
-   `Booking`
-   `PropertyHold`
-   `PurchaseRequest`
-   `Chat`
-   `Message`
-   `Notification`
-   `AIConversation`
-   `AIMessage`
-   `SearchRecommendation`
-   `AuditLog`

### Relationships chính

``` text
Project 1 ── N Building
Building 1 ── N Property
Owner 1 ── N Property
Property 1 ── N Media
Property 1 ── N Availability
Property 1 ── N Booking
Booking 1 ── 0..1 Hold
Booking 1 ── 0..1 PurchaseRequest
Booking 1 ── 1 Chat
Chat 1 ── N Message
User 1 ── N Notification
User 1 ── N AuditLog
Customer 1 ── N AIConversation
```

------------------------------------------------------------------------

## 4.14 Authentication & authorization

  Actor               Authentication
  ------------------- ---------------------------------
  Customer            Phone + OTP
  Owner               Phone/Email + Password hoặc OTP
  Investor/Operator   Email + Password + 2FA

-   RBAC.
-   Một account chỉ có một role.
-   Password hash, không plaintext.
-   OTP có expiry và retry limit.
-   Customer chỉ xem dữ liệu cần thiết.
-   Owner chỉ xem customer data sau khi booking được xác nhận.
-   Chat access giới hạn theo booking relationship.
-   Audit log cho hành động quan trọng.
-   Encryption in transit + at rest.

------------------------------------------------------------------------

## 4.15 AI Tools

### Read tools

``` text
search_properties
get_property_detail
compare_properties
check_availability
get_booking_status
```

### Action tools

``` text
create_booking_request
cancel_booking
reschedule_booking
create_property_hold
release_property_hold
create_purchase_request
open_owner_chat
send_notification
```

### Tool policy

-   LLM không truy cập DB trực tiếp.
-   Tool layer kiểm tra authentication/authorization.
-   Tool layer kiểm tra business rules.
-   Write action phải validate state transition.
-   AI không được tự bypass owner approval.
-   Tool response chỉ trả dữ liệu cần thiết cho model.

------------------------------------------------------------------------

## 4.16 Notification

### Events

1.  Owner có booking request mới.
2.  Owner xác nhận/từ chối lịch.
3.  Booking được xác nhận thành công.
4.  Property được hold.
5.  Hold hết hạn.
6.  Sắp đến giờ xem.
7.  Customer gửi purchase request.
8.  Owner nhận purchase request.
9.  Có message mới.
10. Listing được Investor/Operator approve/reject.

### Reminder

-   T-24h.
-   T-2h.

### Channel

-   Booking confirmed: **In-app + SMS/Zalo**.
-   Các event khác: channel policy cần chốt theo cost/operational
    requirement.

------------------------------------------------------------------------

## 4.17 Error handling

### Business errors

AI tự xử lý/đề xuất alternative nếu có thể:

-   Không có căn phù hợp → nới soft preference hoặc đề xuất căn gần
    nhất.
-   Căn vừa được giữ → tìm candidate khác.
-   Slot không còn → đề xuất slot khác.
-   Owner từ chối → đề xuất slot/property khác.
-   Listing không hợp lệ → không recommendation.

### System errors

Fallback Operator:

-   API unavailable.
-   Database unavailable.
-   AI/LLM unavailable.
-   Notification service failure.
-   Booking transaction failure.
-   Unexpected internal error.

AI không được giả vờ booking/hold thành công khi transaction chưa được
xác nhận.

------------------------------------------------------------------------

## 4.18 AI guardrails

AI **không được**:

1.  Tự xác nhận lịch khi Owner chưa duyệt.
2.  Tự thay đổi giá bán.
3.  Tự thay đổi trạng thái pháp lý.
4.  Tự xóa tin đăng.
5.  Tự xác nhận giao dịch mua bán.
6.  Tự nhận/thu tiền hoặc đặt cọc.
7.  Tự chia sẻ PII ngoài phạm vi cho phép.
8.  Tự mở chat Customer ↔ Owner trước khi booking thành công.
9.  Tự giữ căn ngoài viewing window.
10. Tự đàm phán giá.

------------------------------------------------------------------------

# §5. Kiểu lỗi

  -----------------------------------------------------------------------
  Error type              Ví dụ                   Expected behavior
  ----------------------- ----------------------- -----------------------
  Missing information     Thiếu ngân sách/dự án   AI hỏi bổ sung

  No match                Không có căn đạt hard   AI giải thích + đề xuất
                          constraints             nới soft criteria

  Stale availability      Slot vừa mất            Re-check + đề xuất slot
                                                  khác

  Owner rejection         Owner từ chối           Đề xuất alternative

  Concurrent booking      Hai customer cùng       Atomic transaction; một
                          booking                 request fail/re-route

  Invalid listing         Dữ liệu căn sai/thiếu   Không đưa vào
                                                  recommendation

  Unauthorized action     AI/user gọi tool ngoài  Reject
                          quyền                   

  Notification failure    SMS/Zalo lỗi            Retry/fallback policy

  System failure          API/DB/LLM lỗi          Fallback Operator

  State conflict          Booking đã cancelled    Reject transition
                          nhưng action confirm    

  Chat access violation   User chưa có booking    Deny access
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# §6. Bốn đường đi trải nghiệm

## 6.1 Happy path

``` text
Customer
→ AI collects need
→ Search/rank
→ Select property
→ Select viewing slot
→ Booking request
→ Owner confirms
→ Hold during viewing
→ Reminder T-24h/T-2h
→ Customer views
→ Purchase request
→ Owner chat
```

## 6.2 Correction path

Ví dụ customer thay đổi:

> "Ngân sách của tôi từ 5 tỷ lên 6 tỷ, ưu tiên view hồ hơn."

AI phải cập nhật structured criteria và chạy lại recommendation, không
tạo một profile mới không liên quan.

``` text
Existing criteria
→ Customer correction
→ Update criteria
→ Re-run ranking
→ Show changed recommendations
```

## 6.3 Exception path

Ví dụ:

> Customer chọn 14:00 nhưng slot vừa bị người khác đặt.

``` text
Selected slot
→ Re-check availability
→ Slot unavailable
→ Explain
→ Suggest available slots
→ Customer chooses new slot
→ Create request
```

## 6.4 Fallback path

``` text
AI/Backend/System error
→ Stop unsafe action
→ Preserve request context
→ Create escalation
→ Operator handles manually
→ Customer receives status
```

------------------------------------------------------------------------

# §7. Kiểm thử

## 7.1 Functional test areas

### Customer

-   Login/OTP.
-   Natural-language requirement extraction.
-   Recommendation.
-   Property detail.
-   Booking.
-   Cancellation.
-   Reschedule.
-   Hold.
-   Reminder.
-   Purchase request.
-   Chat gating.

### Owner

-   Listing CRUD.
-   Listing availability.
-   Review booking.
-   Approve/reject.
-   Booking list.
-   Purchase requests.
-   Chat.

### Investor/Operator

-   Project CRUD.
-   Building/property management.
-   Listing moderation.
-   Owner account management.
-   Booking/hold monitoring.
-   Analytics.
-   Exception handling.

## 7.2 AI evaluation

Golden set tối thiểu đề xuất: **≥20 scenario** cho MVP ban đầu, sau đó
mở rộng theo dữ liệu thật.

Các nhóm test:

1.  Requirement extraction.
2.  Hard constraint adherence.
3.  Soft preference ranking.
4.  Priority interpretation.
5.  Explanation correctness.
6.  Tool selection.
7.  Tool argument correctness.
8.  Permission enforcement.
9.  Booking state transition.
10. Hold state transition.
11. No hallucinated property.
12. No unauthorized commitment.
13. Correction handling.
14. Exception handling.
15. Fallback behavior.

## 7.3 Critical acceptance criteria

### AC-01 --- Không hallucinate căn

**Given:** database không có căn phù hợp\
**When:** customer hỏi căn\
**Then:** AI không tự tạo property; phải báo không có match và đề xuất
alternative.

### AC-02 --- Owner approval bắt buộc

**Given:** booking request chưa được Owner approve\
**When:** AI xử lý booking\
**Then:** booking không được chuyển `CONFIRMED`.

### AC-03 --- Atomic hold

**Given:** hai request concurrent cho cùng property/time window\
**When:** hệ thống tạo hold\
**Then:** không quá một hold hợp lệ được tạo.

### AC-04 --- Hold hết viewing window

**Given:** viewing window kết thúc\
**When:** scheduler xử lý expiry\
**Then:** hold được release và property trở lại trạng thái khả dụng nếu
không có trạng thái mới.

### AC-05 --- Chat gating

**Given:** customer chưa có booking xem nhà thành công\
**When:** customer cố mở owner chat\
**Then:** hệ thống từ chối quyền truy cập.

### AC-06 --- Purchase request gating

**Given:** customer chưa hoàn thành/được xác nhận lịch xem hợp lệ\
**When:** customer yêu cầu mua\
**Then:** không tạo purchase request theo policy.

### AC-07 --- Price protection

**Given:** customer yêu cầu AI đổi giá căn\
**When:** AI xử lý\
**Then:** AI từ chối action và không gọi tool thay đổi giá.

### AC-08 --- System fallback

**Given:** booking service unavailable\
**When:** customer đặt lịch\
**Then:** không báo booking thành công; request được chuyển trạng thái
xử lý lỗi/fallback Operator.

## 7.4 Quality bar

-   Không có hallucinated property.
-   Không có unauthorized booking confirmation.
-   Không có unauthorized hold.
-   Không có double-booking trong test concurrency.
-   Recommendation phải giải thích dựa trên dữ liệu có thật.
-   Các critical write action phải có audit trail.
-   Error state phải observable và recoverable.

------------------------------------------------------------------------

# §8. Phân công & kế hoạch

## 8.1 Workstreams

  Workstream     Scope
  -------------- -------------------------------------------------------
  Product / PM   Requirement, business rules, KPI, acceptance criteria
  AI / Agent     Prompt, orchestration, tools, evaluation
  Backend        API, booking, hold, RBAC, database
  Frontend       AI chat, property cards, booking, dashboards
  Data           Property/project schema, search/ranking
  QA             Functional, integration, concurrency, AI eval
  DevOps         Docker, CI/CD, monitoring, secrets
  Security       Auth, RBAC, PII, audit

**Tên người phụ trách:** `[FILL]`

## 8.2 MVP implementation phases

### Phase 1 --- Foundation

-   Auth/RBAC.
-   User/Owner/Investor.
-   Project/Building/Property schema.
-   Listing moderation.

### Phase 2 --- Customer discovery

-   AI chat.
-   Requirement extraction.
-   Property search.
-   Ranking.
-   Property detail.

### Phase 3 --- Booking

-   Availability.
-   Booking request.
-   Owner approval.
-   Booking state machine.
-   Atomic hold.

### Phase 4 --- Post-viewing

-   Reminders.
-   Purchase request.
-   Chat gating.
-   Owner/customer chat.

### Phase 5 --- Operations

-   Operator dashboard.
-   Booking/hold monitoring.
-   Analytics.
-   Audit logs.
-   Error/fallback.

### Phase 6 --- Evaluation

-   Golden set.
-   AI regression tests.
-   Concurrency tests.
-   KPI instrumentation.
-   Pilot measurement.

------------------------------------------------------------------------

# §9. Changelog

## v1.0 --- 25/09/2026

-   Xác định scope Vinhomes-only.
-   Xác định 3 actor: Customer, Owner, Investor/Operator.
-   Xác định AI-first responsive web.
-   Xác định customer journey từ discovery → viewing → purchase request.
-   Xác định Owner approval là bắt buộc trước booking confirmation.
-   Xác định viewing hold chỉ có hiệu lực trong khoảng thời gian xem.
-   Xác định hybrid search/recommendation.
-   Xác định database nội bộ là source of truth.
-   Xác định RBAC và authentication theo từng actor.
-   Xác định notification events và reminder T-24h/T-2h.
-   Xác định business-error vs system-error strategy.
-   Xác định AI guardrails.
-   Xác định success metrics.
-   Xác định state machine property/booking.
-   Xác định non-goals MVP.
-   Công nghệ cụ thể được đề xuất tại §10.

------------------------------------------------------------------------

# §10. Technical Architecture Proposal

## 10.1 Recommended stack

  -----------------------------------------------------------------------------------
  Layer                   Recommendation          Lý do
  ----------------------- ----------------------- -----------------------------------
  Frontend                **Next.js +             Phù hợp responsive web, component
                          TypeScript**            architecture, dễ tích hợp API

  Backend                 **Python + FastAPI**    Phù hợp AI/data workload, API rõ
                                                  ràng, async support

  Database                **PostgreSQL**          Transaction, relational data và
                                                  state machine booking phù hợp

  Search                  **PostgreSQL            MVP chưa cần thêm search cluster;
                          Full-text + pg_trgm**   giảm operational complexity

  Vector DB               **Không dùng trong      Không có RAG/knowledge-base;
                          MVP**                   recommendation chủ yếu là
                                                  structured filtering/ranking

  LLM                     **OpenAI API**          Phù hợp conversational extraction +
                                                  tool calling; model cụ thể để
                                                  benchmark theo cost/quality

  Agent orchestration     **LangGraph**           Phù hợp stateful workflow, tool
                                                  calling, branching và fallback

  Auth                    **JWT + OTP**           Phù hợp web/API và role-based
                                                  session

  Password                **Argon2id/bcrypt**     Hash password an toàn; không lưu
                                                  plaintext

  Media                   **Amazon S3**           Phù hợp ảnh/video và tách media
                                                  khỏi DB

  Realtime chat           **WebSocket qua         Đủ cho MVP, tránh thêm Firebase nếu
                          FastAPI**               không cần

  Notifications           In-app + provider       Provider cụ thể: **TBD**
                          SMS/Zalo                

  Deployment              **Docker + AWS**        Có thể triển khai
                                                  frontend/backend/database/storage
                                                  theo từng service

  Observability           Structured logs +       Cần theo dõi booking, errors,
                          metrics + audit log     latency và AI actions
  -----------------------------------------------------------------------------------

## 10.2 Architecture

``` mermaid
flowchart TB
    USER[Customer / Owner / Investor]
    WEB[Next.js Responsive Web]
    API[FastAPI API]
    AUTH[Auth + RBAC]
    AGENT[LangGraph AI Agent]
    TOOLS[Controlled Agent Tools]
    SEARCH[PostgreSQL Search + Ranking]
    DB[(PostgreSQL)]
    MEDIA[S3 Media]
    NOTIFY[Notification Service]
    CHAT[WebSocket Chat]
    LLM[LLM API]

    USER --> WEB
    WEB --> API
    API --> AUTH
    API --> AGENT
    AGENT --> LLM
    AGENT --> TOOLS
    TOOLS --> SEARCH
    TOOLS --> DB
    API --> DB
    API --> MEDIA
    API --> NOTIFY
    API --> CHAT
```

### Security boundary

``` text
LLM
  ↓
Agent Tool Layer
  ↓
Authorization + Business Rule Validation
  ↓
Service Layer
  ↓
Database
```

**Không cho LLM truy cập database trực tiếp.**

## 10.3 Recommendation architecture

``` text
User natural language
        ↓
LLM requirement extraction
        ↓
Structured CustomerPreference
        ↓
PostgreSQL hard filtering
        ↓
Candidate set
        ↓
Soft scoring
        ↓
Priority weighting
        ↓
Proximity scoring
        ↓
Top-N recommendations
        ↓
Explanation generation
```

## 10.4 Booking/hold architecture requirement

Booking/hold phải được thực hiện trong transactional service:

``` text
Check current state
      ↓
Validate time conflict
      ↓
Atomic write
      ↓
Create/confirm booking or hold
      ↓
Emit event
      ↓
Notification
```

Implementation cụ thể của database row lock, advisory lock, Redis lock
hoặc cơ chế khác: **TBD sau benchmark concurrency**.

------------------------------------------------------------------------

# §11. Open Questions / TBD

1.  Owner không phản hồi booking trong bao lâu thì request hết hạn?
2.  Thời hạn hủy booking.
3.  Thời hạn/điều kiện đổi lịch.
4.  Chính xác viewing window có bao gồm buffer trước/sau hay không.
5.  Trọng số recommendation.
6.  Những trường Customer preference nào là required vs optional.
7.  SMS/Zalo provider.
8.  Cơ chế escalation Operator chi tiết.
9.  Baseline KPI trước khi triển khai.
10. Chi tiết pháp lý và validation cho "tình trạng pháp lý" của căn.
11. Chính sách lưu trữ/xóa chat và PII.
12. Quy tắc Owner được phép xem dữ liệu Customer ở mức nào sau
    confirmation.
13. Cách xác định "booking thành công" trong KPI.
14. Cách đo "availability synchronization accuracy".
15. Tên thành viên/phân công cụ thể.

------------------------------------------------------------------------

# §12. Final MVP Boundary

### MUST HAVE

-   Customer authentication.
-   AI-first chat.
-   Natural-language requirement extraction.
-   Property search/filter.
-   Recommendation/ranking.
-   Property detail.
-   Owner property CRUD.
-   Investor/Operator moderation.
-   Availability management.
-   Booking request.
-   Owner approval.
-   Atomic viewing hold.
-   Booking cancellation.
-   Rescheduling with Owner approval.
-   T-24h/T-2h reminders.
-   Purchase request after viewing.
-   Customer ↔ Owner chat after successful booking/viewing flow.
-   RBAC.
-   Audit log.
-   Error handling + Operator fallback.
-   Analytics/KPI instrumentation.

### MUST NOT HAVE

-   Payment/deposit.
-   E-contract.
-   AI valuation.
-   Price prediction.
-   Mortgage.
-   Non-Vinhomes properties.
-   AI price negotiation.
-   AI transaction confirmation.
-   External CRM/Sales integration.
-   Voice AI.
-   Automatic phone calls.
-   External web knowledge/RAG in MVP.

------------------------------------------------------------------------

# One-line product definition

> **BookingBot AI Agent là trợ lý AI-first giúp khách hàng tìm đúng căn
> Vinhomes từ nhu cầu tự nhiên, tự động điều phối lịch xem và giữ căn
> trong thời gian xem, đồng thời kết nối khách với chủ nhà sau khi
> booking thành công --- với Owner approval và business-rule controls
> tại các điểm cam kết.**
