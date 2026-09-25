# Kế hoạch Triển khai (Implementation Plan): BookingBot AI

## 1. Kiến trúc Hệ thống (System Architecture)
Hệ thống tuân thủ mô hình 3 lớp (3-Tier) theo tiêu chuẩn của P-001:
- **Agent Layer (`src/agents/`)**: Sử dụng LangGraph. Quản lý hội thoại, bóc tách nhu cầu và gọi Tools.
- **Service/Business Layer (`src/services/`)**: Các hàm xử lý nghiệp vụ độc lập như tìm kiếm BĐS trong Database, kiểm tra lịch trống, và gửi thông báo xác nhận.
- **API/Routing Layer (`src/api/`)**: FastAPI endpoints tiếp nhận request từ phía Frontend/Chat interface.

## 2. Thiết kế Cơ sở dữ liệu (Database Design)
Sử dụng PostgreSQL/SQLite với các bảng (tables) chính:
- **Properties**: `id`, `name`, `project` (Vinhomes), `price`, `bedrooms`, `direction`, `amenities`, `status` (available/sold).
- **Bookings**: `id`, `property_id`, `user_id`, `viewing_time`, `status` (pending/confirmed).
- **Users/Agents**: Thông tin khách hàng và đầu mối Ban quản lý.

## 3. Kế hoạch Triển khai Từng phần (Phased Implementation)

### Giai đoạn 1: Xây dựng LangGraph Agent (Trọng tâm AI)
- **Mục tiêu**: Xây dựng thành công bộ não phân tích ngôn ngữ tự nhiên.
- **Công việc**:
  1. Định nghĩa `TypedDict` State cho luồng chat (`messages`, `extracted_criteria`).
  2. Tạo Prompt bóc tách thực thể (Ngân sách, Số phòng, Hướng...) bằng LLM (gpt-4o-mini).
  3. Viết Unit test đảm bảo AI bắt đúng các từ khoá nhu cầu từ câu chat phức tạp.

### Giai đoạn 2: Xây dựng Tool Matching (Slot 1)
- **Mục tiêu**: Kết nối AI với Database để tìm BĐS.
- **Công việc**:
  1. Xây dựng hàm `search_properties(criteria)` tại `src/services/`.
  2. Bọc hàm trên thành LangChain `@tool` tại `src/agents/tools/`.
  3. Cập nhật LangGraph để Agent tự động gọi Tool khi đã bóc tách đủ nhu cầu, sau đó format kết quả trả về cho khách.

### Giai đoạn 3: Xây dựng Tool Booking & Connect (Slot 2 & Slot 3)
- **Mục tiêu**: Hỗ trợ đặt lịch và kết nối Ban quản lý.
- **Công việc**:
  1. Xây dựng hàm `check_availability` và `create_booking` tương tác với bảng Bookings.
  2. Bọc thành Tool cho LangGraph.
  3. Tạo luồng (edge) trong đồ thị: nếu khách chọn "Đặt lịch" -> gọi Booking Tool -> Trả về kết quả cho khách.

### Giai đoạn 4: Hoàn thiện API và Tích hợp
- **Mục tiêu**: Mở cổng giao tiếp ra bên ngoài.
- **Công việc**:
  1. Viết `POST /api/v1/chat`: Chuyển text của user vào luồng LangGraph và trả về phản hồi.
  2. Khởi tạo `config.py` để load `OPENAI_API_KEY` và `DATABASE_URL`.
  3. Cài đặt các hook ghi log AI theo yêu cầu của course.

## 4. Xử lý Rủi ro (Risk Management)
- **Rủi ro AI sinh ảo (Hallucination)**: Agent có thể bịa ra căn nhà không có thật.
  - *Giải pháp*: Prompt của Agent bị giới hạn nghiêm ngặt, chỉ được phép sử dụng kết quả trực tiếp từ Tool `search_properties`. Không được tự nghĩ ra thông tin.
- **Trùng lịch Booking (Concurrency)**:
  - *Giải pháp*: Đặt ràng buộc (Unique constraint) trên bảng Bookings với cặp `(property_id, viewing_time)`. Xử lý lỗi mượt mà trong Tool để báo AI thông báo khách chọn giờ khác.
