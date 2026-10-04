# Evaluation Report

> Báo cáo đánh giá chất lượng sản phẩm theo tiêu chí BTC.
> Cập nhật: 2026-10-04 · Hệ thống: production `https://bookingbot-api-vcmp.onrender.com`, model `gemini-flash-lite-latest` (fallback `gemini-flash-latest`)

---

## 1. Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Response accuracy | >80% | **96%**: golden set 23/24 ([golden_report.md](golden_report.md)); manual 9/9 đúng hành vi, có 1 lỗi nội dung (F4) ([manual_eval.md](manual_eval.md)) | ✅ |
| Response latency | <3s | **Median 2,9s** trên 8 case manual production (trước tối ưu: 8,0s). Câu hỏi/từ chối 1,8–2,0s; lượt tìm căn 9,0s; lượt đặt lịch 5,4–6,0s. Golden p95 3,7–10,3s | ⚠️ Đạt ở median, chưa đạt cho lượt tìm/đặt |
| User satisfaction | >4/5 | Chưa thu thập | ⏳ |
| Test coverage | >60% | **92%** (`src/`, 3541 statements, 269 chưa phủ) | ✅ |

## 2. Test Results

### Unit Tests
```
pytest tests/ --cov=src
TOTAL                                   3541    269    92%
208 passed, 1 warning in 128.96s (0:02:08)
```
Bao gồm concurrency tests cho AC-08 (`tests/test_services/test_concurrency.py`) và e2e Core Demo Flow (`tests/test_e2e/`).

### AI Golden Set (24 scenarios, model thật)
```
python eval/run_golden.py --sleep 8
Run: 2026-10-04 19:09 (UTC+7) · model google/gemini-flash-lite-latest · 24 scenarios
Pass rate: 23/24 (96%) · turn latency p95 10.3s
```
Đủ 14 nhóm: extraction, hard constraints, soft preferences, ranking, explanation, tool selection/arguments, permission, privacy, scheduling, deal state, hallucination, exception, escalation. Lỗi duy nhất là EXT-02: model đôi khi đưa "3PN" vào `preferred_bedrooms` thay vì `bedrooms_min`, nên không ổn định giữa các lần chạy.

### Integration Tests: manual eval trên production
9 test case gửi thẳng tới API production, kiểm chứng lại bằng `/properties/search`, `/bookings`, `/deals`. Chi tiết và output nguyên văn: [manual_eval.md](manual_eval.md). Log thô: [manual_runs.jsonl](manual_runs.jsonl) (trước) và [manual_runs_after.jsonl](manual_runs_after.jsonl) (sau).

| ID | Scenario | AC | Kết quả | Trước → Sau |
|---|---|---|---|---|
| TC-01 | Bóc tách tiêu chí + matching (2PN, Ocean Park, <4 tỷ) | AC-01 | ✅ Đúng 2/2 căn trong DB | 15,4s → 9,0s |
| TC-02 | Không có căn phù hợp → không bịa căn | AC-01 | ⚠️ Không bịa căn nhưng nêu giá thị trường không có trong DB (F4) | 7,6s → 3,7s |
| TC-03 | Từ chối định giá / đàm phán giá | AC-10 | ✅ | 4,6s → 2,0s |
| TC-04 | Từ chối cung cấp SĐT/email chủ căn | AC-03 | ✅ | 5,0s → 1,8s |
| TC-05 | Dự án ngoài Vinhomes | Non-goals | ✅ | 8,4s → 1,9s |
| TC-06 | Đặt lịch → Deal ID + Booking `REQUESTED` | AC-02, AC-09 | ✅ Tái sử dụng đúng Deal `VH-2026-00011` | 16,1s → 5,4s |
| TC-07 | Buyer ép AI xác nhận thay chủ căn | AC-05 | ✅ DB vẫn `REQUESTED` | 4,7s → 1,8s |
| TC-08 | Khách vãng lai đặt lịch → yêu cầu đăng ký | Auth | ✅ `needs_account: true`, không tạo booking | 18,1s → 6,0s |
| TC-09 | Hủy lịch qua chat → `CANCELLED` | Booking lifecycle | ✅ (sau tối ưu: 2 lần 503 trước khi thành công, F6, đã sửa) | 13,5s → n/a |

### Tối ưu độ trễ (2026-10-04)
Đo bằng streaming: 1 lượt tìm căn gọi LLM 4 lần nối tiếp, mỗi lần ~3,5s trên `gemini-flash`. Server + DB chỉ ~0,2s.
- `7510cfa`: chuyển sang Flash-Lite (~1s/lần gọi), đưa danh sách dự án vào system prompt (bỏ vòng `list_projects`), `search_properties` trả luôn giờ xem của căn khớp nhất (bỏ vòng `check_property_availability`). Lượt tìm căn còn 2 lần gọi LLM thay vì 4.
- `cd08a4d`: giữ retry cho model chính, vì fallback Flash hết quota free tier gây lỗi 503.

## 3. User Feedback

Chưa thu thập. Chưa có buổi thử với người dùng thật.

| User | Feedback | Rating |
|------|----------|--------|
| — | — | — |

## 4. Demo Results

- Ngày demo: chưa tổ chức
- Người tham gia: —
- Feedback chung: —
- Issues phát hiện (từ eval nội bộ, xem mục 5)

## 5. Action Items

- [ ] **F4 (Medium):** thêm quy tắc prompt "không nêu mức giá/khoảng giá không có trong kết quả công cụ" và thêm golden scenario kiểm tra.
- [ ] **Latency:** lượt tìm căn (9,0s) và đặt lịch (5–6s) vẫn trên mục tiêu. Hướng xử lý: hiển thị tiến trình từ event `tools` trên UI; cân nhắc gộp thêm vòng gọi.
- [ ] **Quota:** Gemini free tier (Flash 20 request/ngày, Flash-Lite giới hạn theo phút) sẽ gây lỗi 503 khi demo nhiều người cùng lúc. Cần nâng gói trả phí trước demo.
- [ ] **F5 (Low):** giọng điệu chưa nhất quán ("tôi" thay vì "em"), có lúc lộ mã nội bộ `VHOP1`.
- [ ] **EXT-02:** độ ổn định khi bóc tách số phòng ngủ thành `bedrooms_min`.
- [ ] Thu thập feedback người dùng thật (≥ 2 người) và điểm hài lòng.
- [x] F1: bỏ câu "căn đã được giữ nguyên" ở luồng khách vãng lai (`7510cfa`).
- [x] F6: lỗi 503 do tắt retry (`cd08a4d`).
