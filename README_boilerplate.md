# BookingBot AI Agent · Trợ lý Đặt lịch Xem nhà & Giữ căn Vinhomes

> **BookingBot AI Agent** là trợ lý AI-first trên nền tảng Web Responsive chuyên biệt cho hệ sinh thái Vinhomes: Tự động bóc tách nhu cầu tự nhiên của khách hàng, gợi ý căn hộ chính xác qua thuật toán xếp hạng lai (Hard filter + Soft score), tự động điều phối lịch xem nhà với sự phê duyệt của **Chủ nhà (Owner Approval)**, áp dụng cơ chế **Viewing Hold nguyên tử** để tạm khóa căn trong thời gian xem, và kết nối trực tiếp khách hàng với chủ nhà sau khi xem nhà thành công.

---

## 1. Vấn đề (Problem)

- **Ai đang gặp vấn đề?** Khách hàng có nhu cầu mua hoặc thuê BĐS tại các đại đô thị Vinhomes (Ocean Park, Smart City, Grand Park) và Chủ nhà (Owner) cần tìm khách hàng tiềm năng thực sự.
- **Thực trạng và Dữ liệu minh chứng:**
  - Khảo sát người tiêu dùng BĐS Q4/2024 của *Batdongsan.com.vn* ($N=500$) cho thấy **62%** người tiêu dùng lựa chọn kênh thông tin BĐS trực tuyến để tìm nhà đất; **32%** chọn trang tin vì có nhiều nguồn cung nhưng **25%** coi độ chính xác/tin cậy của tin đăng là yếu tố then chốt.
  - Khách hàng phải tự tìm kiếm trên nhiều kênh phân tán, bị nhiều môi giới gọi điện làm phiền, mất nhiều thời gian trao đổi qua lại để chốt lịch xem nhà, và dễ gặp rủi ro căn hộ bị bán mất hoặc có người khác xem trước ngay khi vừa di chuyển đến nơi.
- **Tại sao giải pháp hiện tại chưa đủ?** Các trang rao vặt hay sàn BĐS truyền thống chỉ đóng vai trò là "bảng tin đăng tĩnh", thiếu năng lực điều phối tự động (Orchestration), không có cơ chế giữ chỗ tạm thời trong giờ xem, và không bảo vệ thông tin liên lạc của khách hàng.

---

## 2. Giải pháp (Solution)

1. **AI Natural Language Extraction:** Khách hàng trò chuyện tự nhiên với AI Agent; hệ thống tự động bóc tách thành cấu trúc `CustomerPreference` (ngân sách, số phòng ngủ, diện tích, phân khu, khoảng tầng, hướng ban công, tiện ích).
2. **Hybrid Recommendation Engine:** Thuật toán 5 bước kết hợp Hard Filtering SQL và Soft Scoring (Giá 30%, Diện tích 20%, Thiết kế 20%, Hướng 15%, Tầng 15%) kèm tính năng giải thích đề xuất (**Explainability**).
3. **Owner Approval Workflow (HITL Bắt buộc):** Yêu cầu đặt lịch được gửi tức thời đến Chủ nhà; chỉ khi Chủ nhà bấm Duyệt (`Approve`), lịch hẹn mới chính thức được chuyển sang `CONFIRMED`.
4. **Atomic Viewing Hold (Giữ căn nguyên tử):** Tạm khóa căn hộ đúng trong khung giờ diễn ra buổi xem nhà, ngăn chặn triệt để tình trạng trùng lịch (Anti-Double-Booking).
5. **Automated Reminders (T-24h & T-2h):** Tự động gửi thông báo nhắc nhở kèm sơ đồ vị trí căn hộ trước thời điểm xem.
6. **Chat Gating & Realtime 1-1 Chat (WebSocket):** Sau buổi xem nhà (`COMPLETED`), nếu khách gửi `Purchase Request`, hệ thống tự động mở phòng chat trực tiếp 1-1 để Khách hàng và Chủ nhà tự do đàm phán giá.

---

## 3. Các Bên Sử dụng (Target Users)

- **Primary User — Khách hàng (Customer):** Người có nhu cầu tìm mua/thuê căn hộ Vinhomes, muốn tìm căn chuẩn xác, xem nhà đúng hẹn mà không bị làm phiền bởi các cuộc gọi rác.
- **Secondary User — Chủ nhà (Owner):** Người sở hữu căn hộ Vinhomes muốn đăng tin minh bạch, chủ động duyệt lịch xem phù hợp với thời gian biểu cá nhân và tiếp cận khách mua thực tế.
- **Tertiary User — Ban Quản trị / Chủ đầu tư (Investor / Operator):** Kiểm duyệt tin đăng căn hộ (`APPROVED`), giám sát các buổi xem nhà và xử lý can thiệp khi có tranh chấp phát sinh.

---

## 4. Công nghệ Sử dụng (Tech Stack)

| Phân tầng | Công nghệ | Vai trò & Lý do lựa chọn |
|---|---|---|
| **AI Agent** | **LangGraph + OpenAI (gpt-4o-mini)** | Stateful workflow, bóc tách nhu cầu, quản lý hội thoại đa lượt và kích hoạt công cụ (Tools). |
| **Backend** | **Python 3.11+ + FastAPI** | API-first, Pydantic v2 type safety, async I/O cao, tích hợp WebSocket server. |
| **Frontend** | **Next.js + TypeScript** | Web responsive, kiến trúc component hiện đại, hỗ trợ Server-Sent Events (SSE) streaming chat. |
| **Database** | **PostgreSQL 15+** | Relational core data, Full-text Search + `pg_trgm`, ACID transactions, row-level locking. |
| **Media Storage**| **Amazon S3** | Lưu trữ độc lập toàn bộ hình ảnh và video căn hộ Vinhomes, tách biệt khỏi Database. |
| **Realtime** | **WebSocket qua FastAPI** | Kênh chat trực tiếp 1-1 tức thời giữa Khách hàng và Chủ nhà sau khi xem nhà. |
| **DevOps** | **Docker + GitHub Actions** | Đóng gói môi trường container nhất quán và tự động hóa CI kiểm thử code (`ruff` + `pytest`). |

---

## 5. Cấu trúc Thư mục Dự án (Project Structure)

```text
├── src/
│   ├── agents/          # LangGraph Agent Core (State, Nodes, Graph, Tools)
│   │   ├── graph.py     # Định nghĩa StateGraph & Edges
│   │   ├── state.py     # TypedDict Schema cho CustomerPreference & Context
│   │   └── tools/       # Controlled Tools: search, detail, availability, booking
│   ├── api/             # FastAPI REST Routers & WebSocket Server
│   │   ├── routes/      # Endpoints: /chat, /properties, /bookings, /owner, /operator
│   │   └── websocket.py # WebSocket Server chat trực tiếp 1-1 Khách ↔ Chủ nhà
│   ├── models/          # SQLAlchemy Database Models & Pydantic Schemas
│   ├── services/        # Business Logic (Search Engine, Hold Engine, State Machine)
│   ├── config.py        # Settings & Biến môi trường
│   └── main.py          # FastAPI Application Entrypoint
├── tests/               # Test suites (Unit, Integration, Concurrency, AI eval)
├── docs/                # Sơ đồ & Tài liệu kỹ thuật
├── presentation/        # Demo materials & Pitch deck
├── Dockerfile           # Multi-stage Docker build
└── docker-compose.yml   # Full stack local deployment
```

---

## 6. Danh mục API Endpoints Chính

| Phương thức | Đường dẫn | Mô tả chức năng |
|---|---|---|
| `GET` | `/health` | Kiểm tra tình trạng hoạt động của hệ thống |
| `POST` | `/api/v1/chat` | Endpoint AI Chat chính (nhận ngôn ngữ tự nhiên, streaming SSE) |
| `GET` | `/api/v1/properties` | Tìm kiếm và xếp hạng căn hộ theo tiêu chí (Hard filter + Soft score) |
| `GET` | `/api/v1/properties/{id}` | Lấy thông tin chi tiết căn hộ `APPROVED` |
| `POST` | `/api/v1/bookings` | Tạo yêu cầu đặt lịch xem nhà mới (Trạng thái `REQUESTED`) |
| `POST` | `/api/v1/owner/bookings/{id}/approve` | Chủ nhà phê duyệt lịch xem $\rightarrow$ chuyển `CONFIRMED` & tạo `Viewing Hold` |
| `POST` | `/api/v1/owner/bookings/{id}/reject` | Chủ nhà từ chối lịch $\rightarrow$ AI gợi ý khung giờ khác cho khách |
| `POST` | `/api/v1/bookings/{id}/purchase-request` | Khách gửi yêu cầu mua/thuê sau buổi xem $\rightarrow$ mở quyền chat |
| `WSS` | `/ws/chat/{room_id}` | WebSocket phòng chat trực tiếp 1-1 Khách hàng ↔ Chủ nhà |

---

## 7. Thành viên Thực hiện (Team)

| Họ và Tên | Vai trò | Trách nhiệm chính |
|---|---|---|
| **Hoàng Anh Tài** | Leader | Tổng hợp kiến trúc, Quản trị dự án, Báo cáo & Spec |
| **Trần Thị Thu Trang** | BA / QA | Đặc tả User Stories, Tiêu chuẩn nghiệm thu, Test Suite |
| **Ngọ Doãn Ngọc** | Backend / AI | Xây dựng FastAPI, LangGraph Agent, Booking Engine |
| **Nguyễn Văn Bảo** | Data / Systems | Thiết kế Schema PostgreSQL, Thuật toán Ranking, Tích hợp S3 |

---

## 8. License

MIT
