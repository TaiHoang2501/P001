# Q&A prep — câu hỏi BGK hay hỏi

> Câu trả lời dựa trên hệ thống đang chạy (xem `CLAUDE.md`, `docs/evaluation.md`). Phân công người trả lời ở cột cuối.
> Số liệu nào chưa đo thì nói "chưa đo", không ước đoán.

| Câu hỏi | Trả lời gợi ý | Người trả lời |
|---|---|---|
| Tại sao chọn LangGraph thay vì CrewAI / AutoGen? | Một agent duy nhất cần vòng lặp agent ⇄ tools có trạng thái, checkpoint lưu trong PostgreSQL (khởi động lại không mất hội thoại), streaming và kiểm soát từng bước. Không cần nhiều agent nói chuyện với nhau; multi-agent chỉ thêm độ trễ và rủi ro. | [__] |
| Làm sao giảm hallucination? | Ba lớp: (1) AI chỉ dùng dữ liệu tool trả về, DB là nguồn sự thật; (2) guardrail bằng code thay câu trả lời nếu nhắc mã căn không có trong kết quả tool, hoặc nói lịch "đã xác nhận" khi chưa có kết quả `CONFIRMED`; (3) giám khảo AI model nhỏ duyệt câu có chủ đề rủi ro. Có test cho từng trường hợp và nhóm `hallucination` trong golden set. | [__] |
| Tại sao không dùng RAG / Vector DB? | Dữ liệu căn là dữ liệu có cấu trúc (giá, số phòng, diện tích, hướng, tầng). Lọc cứng bằng SQL + chấm điểm mềm chính xác hơn, giải thích được và không bao giờ trả về căn đã bán. | [__] |
| AI có tự đặt cọc / đàm phán giá không? | Không. Thanh toán, đặt cọc, định giá, đàm phán, cam kết pháp lý là non-goal. Câu trả lời có nội dung đó bị guardrail thay thế. AI cũng không có tool xác nhận lịch: chỉ chủ căn xác nhận. | [__] |
| Làm sao bảo đảm người đăng là chủ thật? | Xác thực sổ đỏ: họ tên + mã sổ khớp dữ liệu Chủ đầu tư, tài khoản phải đăng nhập bằng đúng SĐT chủ sở hữu ghi trên sổ, rồi OTP tới số đó. Biết tên + mã sổ thôi là không đủ. Trường hợp đặc biệt (bán thay, thừa kế…) đi luồng hỗ trợ cho Chủ đầu tư kiểm tra giấy tờ. Chủ đầu tư còn duyệt từng tin đăng. | [__] |
| Hai người cùng đặt một giờ thì sao? | Yêu cầu chưa xác nhận được phép trùng (chủ căn chọn người). Khi xác nhận, transaction + exclusion constraint của PostgreSQL bảo đảm chỉ một lịch thắng; các yêu cầu trùng giờ tự đóng và AI báo người mua kèm giờ khác. Test concurrency AC-08 mô phỏng 10 người tranh một giờ. | [__] |
| Cost per request là bao nhiêu? | Mỗi lượt chat được ghi token trong trace (`ai_turns`, `python scripts/ai_traces.py stats`). 10 lượt mẫu ngày 17/10: tổng 199.154 token vào / 4.516 token ra, tức khoảng 20 nghìn token vào + 450 token ra mỗi lượt (phần lớn là prompt hệ thống + định nghĩa tool). Chi phí mỗi lượt: [__] (nhân với giá model đang dùng). | [__] |
| Độ ổn định của agent? | pass@3 98% nhưng pass^3 94%: 3/51 kịch bản chưa đạt cả 3 lần (vd. AI nói "có căn" ở Grand Park trước khi tra DB). Đã ghi trong `docs/evaluation.md` và là việc sửa tiếp theo. | [__] |
| Scale khi có 1000 người dùng đồng thời? | Hiện tại 1 instance vì job nền chạy trong tiến trình API. Đường scale: tách job nền sang worker riêng, rồi tăng số instance API (thông báo realtime đọc từ DB nên đã chạy được nhiều instance, rate limit đếm trong DB dùng chung). Giới hạn thật là quota của LLM — có model dự phòng ở provider khác. Chưa load test ở mức 1000. | [__] |
| Độ trễ mỗi lượt? | Golden set 51 × 3 (177 lượt): p50 4,1 s, p95 7,5 s mỗi lượt (mục tiêu spec ≤ 5 s — p50 đạt, p95 chưa). Streaming hiện chữ ngay khi có câu đầu đã kiểm tra nên người dùng không chờ trắng màn hình. Hướng giảm: model nhanh hơn cho bước đơn giản, giảm số lần gọi tool. | [__] |
| Dữ liệu cá nhân xử lý thế nào? | Chủ căn chỉ thấy họ tên + nhu cầu người mua, không thấy SĐT/email. SĐT, email, CCCD khách gõ vào chat bị che trước khi tới model và trước khi lưu trace. Giấy tờ xác thực chỉ người gửi và Chủ đầu tư xem. Chi tiết ở trang `/privacy`. | [__] |
| Mô hình kinh doanh? | [__ — phí theo giao dịch cho Chủ đầu tư / phí dịch vụ… đội tự quyết; spec để TBD] | [__] |
| Roadmap? | Sau buổi xem: chat trực tiếp người mua ↔ chủ căn, bàn giao sang thủ tục của Chủ đầu tư, thông báo SMS/Zalo. | [__] |
| Khác gì Batdongsan / Chợ Tốt? | Họ là bảng tin; BookingBot xác thực chủ sở hữu, điều phối lịch có bảo đảm và không lộ số điện thoại. [__ bảng so sánh 3 đối thủ] | [__] |
