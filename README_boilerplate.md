# [Tên Dự Án]

> Thông tin BĐS phân tán, khó tìm đúng căn và đặt lịch xem qua nhiều Sale → BookingBot AI tự động matching BĐS phù hợp và hỗ trợ đặt lịch trực tiếp với Ban quản lý cho khách hàng có nhu cầu mua BĐS tại Vinhomes.

## Vấn đề (Problem)

Mô tả pain point cụ thể với data/số liệu:
- Ai đang gặp vấn đề? Khách hàng có nhu cầu mua BĐS, đặc biệt khách đang tìm căn hộ tại các dự án Vinhomes. Khảo sát người tiêu dùng BĐS Q4/2024 của Batdongsan.com.vn (N=500) cho thấy 62% người tiêu dùng lựa chọn kênh thông tin BĐS trực tuyến để tìm nhà đất.
- Vấn đề tốn bao nhiêu thời gian/tiền? Người mua phải tiếp cận lượng lớn nguồn cung và phụ thuộc vào thông tin từ nhiều bên. Trong khảo sát Q4/2024, 32% người dùng chọn trang tin vì có nhiều nguồn cung để lựa chọn; 25% coi độ chính xác/tin cậy của tin đăng là yếu tố quan trọng; 31% coi môi giới uy tín là yếu tố quan trọng nhất khi chọn trang tin.
- Tại sao các giải pháp hiện tại chưa đủ? Vinhomes Market hiện đã cung cấp tìm kiếm BĐS, tư vấn, đặt lịch tham quan và xác minh chuyên viên/đại lý. Khoảng trống mà BookingBot AI kiểm chứng không phải là “xây thêm một sàn BĐS”, mà là rút ngắn flow từ nhu cầu của khách → căn phù hợp → slot xem nhà, giảm số lần khách phải tự tìm kiếm, trao đổi và chờ phản hồi thủ công.

## Giải pháp (Solution)

Sản phẩm giải quyết vấn đề như thế nào bằng AI:
- Feature 1 – AI thu thập & phân tích nhu cầu: Khách mô tả nhu cầu bằng ngôn ngữ tự nhiên; AI tự động xác định các tiêu chí như dự án, ngân sách, diện tích, số phòng, hướng, view, nội thất và tiêu chí ưu tiên.
- Feature 2 – AI Matching BĐS: AI đối chiếu nhu cầu với nguồn dữ liệu BĐS đã xác thực, chấm mức độ phù hợp và đề xuất các căn phù hợp nhất, giúp khách giảm thời gian tự tìm kiếm và lọc nhiều tin đăng.
- Feature 3 – AI Booking & kết nối trực tiếp: AI kiểm tra slot xem nhà còn trống, đề xuất thời gian phù hợp và hỗ trợ khách đặt lịch; thông tin booking được chuyển đến Ban quản lý/đầu mối được xác thực để xác nhận, giảm số lần phải trao đổi qua Sale/trung gian.

## Target User

- Primary: Khách hàng có nhu cầu mua BĐS tại các dự án Vinhomes, đã có mức độ quan tâm nhất định và muốn đi xem thực tế nhưng gặp rào cản về nguồn cung phân tán và quy trình đặt lịch thủ công.
- Secondary: Các bạn Sale hoặc môi giới BĐS đang tìm kiếm kênh tiếp cận khách hàng đã được sàng lọc và có nhu cầu rõ ràng, giúp giảm thời gian tìm kiếm thủ công và tăng tỷ lệ chốt deal. 

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Agent | LangGraph + [LLM] |
| Backend | FastAPI + Python 3.11+ |
| Frontend | React/Next.js + TypeScript |
| Database | PostgreSQL / SQLite |
| DevOps | Docker + GitHub Actions |

## Project Structure

```
├── src/
│   ├── agents/          # LangGraph agent definitions
│   │   ├── graph.py     # Main graph (nodes + edges)
│   │   ├── state.py     # State schema
│   │   ├── nodes/       # Individual nodes
│   │   └── tools/       # Agent tools
│   ├── api/             # FastAPI routes
│   ├── models/          # Pydantic schemas
│   ├── services/        # Business logic
│   ├── config.py        # Settings
│   └── main.py          # App entry point
├── tests/               # Test suite
├── docs/                # Documentation
├── eval/                # Evaluation results
├── presentation/        # Demo materials
├── Dockerfile           # Multi-stage build
├── docker-compose.yml   # Full stack
└── .github/workflows/   # CI/CD pipelines
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| POST | /api/v1/chat | Chat with agent |
| POST | /api/v1/analyze | Analyze input |

## Deliverables Checklist

- [x] Source Code (GitHub)
- [x] README.md
- [x] Architecture Diagram (`docs/architecture_diagram.md`)
- [x] AI Logs (auto-collected)
- [ ] Live URL / Deploy
- [ ] Video Demo
- [ ] Pitch Deck (`presentation/`)
- [x] Weekly Journal (`JOURNAL.md`)
- [x] Worklog (`WORKLOG.md`)
- [ ] Evaluation Evidence (`eval/results/`)

## Team

| Member | Role | Student ID |
|--------|------|-----------|
| Hoàng Anh Tài | Leader | 2A202602612 |
| Trần Thị Thu Trang | BA/QA	 | 2A202602581 |
| Ngọ Doãn Ngọc | Backend | 2A202602635 |
| Nguyễn Văn Bảo| Data | 2A202602862 |

## License

MIT
