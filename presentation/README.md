# Pitch Deck & Demo Materials

## Files

| File | Nội dung | Trạng thái |
|---|---|---|
| [`pitch_script.md`](pitch_script.md) | Kịch bản nói cho cả 12 slide (~8 phút, gồm 2 phút demo live), có câu chuyển giữa các slide | Có — đội điền `[__]` |
| [`demo_script.md`](demo_script.md) | Kịch bản demo 3 phút theo AIDA (click → màn hình → lời nói), cũng là kịch bản quay video | Có — đội điền số liệu `[__]` |
| [`../docs/pitch-deck.pdf`](../docs/pitch-deck.pdf) | Pitch deck 12 slide (16:9) | Có — còn các chỗ `[__]` đội cần điền |
| `../docs/video-demo.md` | Link YouTube video demo 3–5 phút | Chờ quay |

## Pitch Deck Structure (12 slides — kể theo câu chuyện của một người mua, chị Bình)

1. **Bìa** — "Đặt lịch xem căn hộ Vinhomes chỉ bằng một cuộc trò chuyện", team, ngày Demo Day
2. **Đây là chị Bình** — nhu cầu nói trong một câu
3. **Hành trình hôm nay** — 4 bước người mua phải tự lo
4. **Insight người mua** — 62% tìm kiếm trực tuyến (nguồn cần kiểm chứng); 3 nhu cầu: phù hợp, tin cậy, thuận tiện
5. **Giải pháp** — BookingBot đáp ứng đúng 3 nhu cầu trong một cuộc trò chuyện
6. **Hành trình mới** — 3 ảnh: chat + thẻ căn, chủ căn xác nhận, Hoạt động + mã QR
7. **Demo live** — câu chat mẫu, video dự phòng
8. **Vì sao cần AI agent** — 3 việc bộ lọc không làm được
9. **AI có giới hạn** — AI được / không được làm; mọi thao tác qua lớp kiểm tra quyền + luật
10. **Số liệu** — golden set 51/51, coverage 91%, độ trễ tìm căn / đặt lịch
11. **Bài học** — AI đã sai ở đâu → xử lý thế nào
12. **Đội & bước tiếp theo** — roadmap sau MVP, QR tới trang web

## Video Demo Checklist

- [ ] Quay theo `demo_script.md` (3–5 phút, HD, có tiếng rõ; phụ đề càng tốt)
- [ ] Có: giới thiệu team, use case chính (D1–D5), một edge case (D6 hoặc chủ căn từ chối kèm giờ khác), kiến trúc 20–30 giây
- [ ] Upload YouTube (unlisted được), ghi link vào `docs/video-demo.md` và slide 7
- [ ] Lưu một bản file local làm backup tầng 2

## Checklist 1 ngày trước Demo Day

- [ ] Deploy bản ổn định, không push code mới sáng hôm sau
- [ ] Dữ liệu demo còn đủ (seed chỉ chạy một lần mỗi DB; muốn làm mới thì tăng `SEED_VERSION`)
- [ ] Tài khoản demo đăng nhập sẵn ở 3 tab
- [ ] Chạy hết `demo_script.md` một lần cuối, không có lỗi console
- [ ] Video + ảnh chụp từng bước sẵn sàng, file video có bản local
- [ ] Trợ lý AI đang bật (`python scripts/ai_switch.py status`)
