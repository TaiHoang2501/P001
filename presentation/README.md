# Pitch Deck & Demo Materials

## Files

| File | Nội dung | Trạng thái |
|---|---|---|
| [`demo_script.md`](demo_script.md) | Kịch bản demo 3 phút theo AIDA (click → màn hình → lời nói), cũng là kịch bản quay video | Có — đội điền số liệu `[__]` |
| [`qa_prep.md`](qa_prep.md) | Câu hỏi BGK hay gặp + câu trả lời soạn sẵn, phân công người trả lời | Có — đội điền `[__]` |
| [`../docs/pitch-deck.pdf`](../docs/pitch-deck.pdf) | Pitch deck 10 slide (16:9) | Có — còn các chỗ `[__]` đội cần điền |
| `../docs/video-demo.md` | Link YouTube video demo 3–5 phút | Chờ quay |

## Pitch Deck Structure (10 slides, theo mục 13.8 Technical Book)

1. **Title** — BookingBot AI Agent, tagline, team, ngày Demo Day
2. **Problem** — người mua / chủ căn / sàn tin đăng (số liệu phỏng vấn `[__]`)
3. **Solution** — chat bằng lời, chỉ căn đã xác thực, khớp lịch + giữ giờ xem, không lộ SĐT
4. **Product Demo** — 3 ảnh: chat + thẻ căn, chủ căn xác nhận, Hoạt động + mã QR
5. **Architecture** — Web → FastAPI → LangGraph agent → Service layer → PostgreSQL
6. **AI/LLM Approach** — agent có kiểm soát, gợi ý giải thích được, golden set
7. **Technical Highlights** — 389 test, guardrail 2 lớp, concurrency AC-08, privacy
8. **Demo Video** — câu chat mẫu + QR tới video
9. **Challenges & Learnings** — bảng thách thức → cách giải quyết
10. **Team & Next Steps** — thành viên, roadmap sau MVP, QR tới trang web

## Video Demo Checklist

- [ ] Quay theo `demo_script.md` (3–5 phút, HD, có tiếng rõ; phụ đề càng tốt)
- [ ] Có: giới thiệu team, use case chính (D1–D5), một edge case (D6 hoặc chủ căn từ chối kèm giờ khác), kiến trúc 20–30 giây
- [ ] Upload YouTube (unlisted được), ghi link vào `docs/video-demo.md` và slide 8
- [ ] Lưu một bản file local làm backup tầng 2

## Checklist 1 ngày trước Demo Day

- [ ] Deploy bản ổn định, không push code mới sáng hôm sau
- [ ] Dữ liệu demo còn đủ (seed chỉ chạy một lần mỗi DB; muốn làm mới thì tăng `SEED_VERSION`)
- [ ] Tài khoản demo đăng nhập sẵn ở 3 tab
- [ ] Chạy hết `demo_script.md` một lần cuối, không có lỗi console
- [ ] Video + ảnh chụp từng bước sẵn sàng, file video có bản local
- [ ] Trợ lý AI đang bật (`python scripts/ai_switch.py status`)
