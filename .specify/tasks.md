# Danh sách Công việc (Tasks): BookingBot AI

Dưới đây là danh sách các task được chia nhỏ và cụ thể hoá từ `plan.md`. Bạn có thể dùng file này làm checklist (đánh dấu `[x]`) trong quá trình code.

## Giai đoạn 1: Xây dựng LangGraph Agent (Trọng tâm AI)
- [ ] **Task 1.1:** Cấu hình file `.env` và `src/config.py` để load `OPENAI_API_KEY`.
- [ ] **Task 1.2:** Cập nhật file `src/agents/state.py` để định nghĩa lại `TypedDict` cho Agent State (cần lưu `messages` và `extracted_criteria` như giá tiền, số phòng...).
- [ ] **Task 1.3:** Cập nhật Prompt cho Agent tại `src/agents/nodes/` để AI biết cách hỏi han và bóc tách nhu cầu của khách.
- [ ] **Task 1.4:** Viết một vài Unit Test (`tests/`) để thử đưa vài câu chat khó xem AI bóc tách đúng thông tin không.

## Giai đoạn 2: Xây dựng Tool Matching (Slot 1)
- [ ] **Task 2.1:** Tạo Pydantic Schema cho BĐS (`Property`) tại `src/models/schemas.py`.
- [ ] **Task 2.2:** Viết logic tìm kiếm BĐS `search_properties(criteria)` tại lớp Business Logic (`src/services/`). (Giai đoạn đầu có thể dùng Mock data hoặc SQLite).
- [ ] **Task 2.3:** Bọc hàm `search_properties` thành một LangChain `@tool` trong thư mục `src/agents/tools/`.
- [ ] **Task 2.4:** Gắn Tool vào LangGraph (`src/agents/graph.py`) để AI tự gọi Tool khi đã hiểu nhu cầu của khách.

## Giai đoạn 3: Xây dựng Tool Booking & Kết nối (Slot 2 & Slot 3)
- [ ] **Task 3.1:** Tạo Pydantic Schema cho `Booking` (Lịch hẹn).
- [ ] **Task 3.2:** Viết hàm `check_availability` (xem giờ trống) và `create_booking` (tạo lịch hẹn) tại `src/services/`.
- [ ] **Task 3.3:** Bọc các hàm này thành LangChain `@tool` để cấp quyền cho AI sử dụng.
- [ ] **Task 3.4:** Bổ sung vào Prompt hướng dẫn AI: "Nếu khách muốn xem nhà, hãy dùng Tool check giờ trống và tạo lịch".
- [ ] **Task 3.5:** Viết luồng bắt lỗi (ví dụ: bị trùng lịch) trong Graph để AI yêu cầu khách chọn lại giờ khác.

## Giai đoạn 4: Hoàn thiện API (Giao tiếp với Frontend)
- [ ] **Task 4.1:** Xây dựng route `POST /api/v1/chat` (`src/api/routes.py`) để nhận tin nhắn của user, gọi LangGraph và trả kết quả về.
- [ ] **Task 4.2:** Xây dựng route `GET /api/v1/booking/{id}/status` để tra cứu lịch hẹn đã tạo.
- [ ] **Task 4.3:** Setup xong Database thật (PostgreSQL) kết nối qua Docker (nếu chạy local).
- [ ] **Task 4.4:** Kiểm tra lại AI Logging hook (để nộp bài cho trường).
- [ ] **Task 4.5:** Chạy `ruff` để chuẩn hóa code và `pytest` để hoàn tất nghiệm thu.
