# Specification: BookingBot AI Agent

## 1. Product Overview
**BookingBot AI** là một trợ lý hội thoại trên Web Chat giúp khách hàng tìm kiếm BĐS phù hợp tại Vinhomes và điều phối lịch xem nhà tự động. 
Hệ thống giải quyết bài toán thông tin BĐS phân tán, giảm thiểu số lần trao đổi qua trung gian (Sale), và tránh xung đột lịch thông qua việc kiểm tra đồng thời 4 nguồn lực: Sale, Căn/Nhà mẫu, Sức chứa dự án, và Phương tiện di chuyển.

## 2. Core Features (Tính năng Cốt lõi)
1. **Tìm kiếm bằng hội thoại (AI Search):** Thu thập nhu cầu (Dự án, loại căn, diện tích, giá, hướng, v.v.) qua chat và hiển thị danh sách BĐS (Property Card).
2. **Booking & Soft-hold (Đặt lịch & Giữ chỗ tạm thời):** Kiểm tra availability đa nguồn lực, tạo Soft-hold, và chuyển cho Sale duyệt (Approve/Reject).
3. **Reschedule & Cancel (Đổi/Hủy lịch):** Hỗ trợ đổi hoặc hủy lịch xem nhà tự động thông qua AI, tự động giải phóng các nguồn lực.
4. **HITL (Human-in-the-Loop):** Xử lý ngoại lệ (Khách VIP, ngoài giờ, yêu cầu đặc biệt) bằng cách tạo task cho Operator/Sale xử lý thủ công.
5. **RAG (Knowledge Base):** Trả lời các câu hỏi về chính sách, tiện ích, nội quy xem nhà (không quyết định giá/availability).

## 3. User Roles (Đối tượng sử dụng)
- **Customer (Khách hàng):** Tìm BĐS, đặt lịch, đổi/hủy lịch qua Web Chat.
- **Sale (Môi giới):** Duyệt booking, cập nhật trạng thái lịch, xem lịch phân công cá nhân.
- **Operator (Điều phối viên):** Quản lý toàn bộ booking, phân công Sale, quản lý nguồn lực (căn, xe, capacity), xử lý HITL.

## 4. Non-Functional Requirements (Yêu cầu Phi chức năng)
- **Độ chính xác:** Backend là nguồn sự thật (Source of Truth). AI không tự quyết định/ảo giác về giá, availability, hay business rules.
- **Độ tin cậy:** Tránh double-booking tuyệt đối thông qua Database Transaction/Locking. AI chỉ dùng tool để check/request.
- **Bảo mật:** RBAC cho Sale/Operator. Customer chỉ xem booking thông qua phương thức xác thực. Password hashing, HTTPS.
- **Hiệu năng:** Chat streaming, phản hồi nhanh, backend xử lý bất đồng bộ khi cần.

## 5. Out of Scope (Ngoài phạm vi Prototype)
- Đàm phán giá, thanh toán/đặt cọc online, ký hợp đồng điện tử.
- Tư vấn tài chính/vay ngân hàng.
- Tích hợp CRM production của Vinhomes.
