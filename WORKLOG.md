# Worklog — Team BookingBot

> Ghi lại tất cả công việc đã làm theo ngày. Ai làm gì, kết quả gì.
>
> **Nguồn:** tổng hợp từ `git log --all` (ngày = ngày tác giả commit, giờ Việt Nam). Task được gom từ commit message; Output là mã commit / PR. Bản xuất thô từng commit: [docs/worklog.md](docs/worklog.md). Git không ghi số giờ làm, nên bỏ cột Time của template.
>
> **Trạng thái:** "Đã merge" = có trong `origin/main`; "Chưa merge" = chỉ có trên nhánh `bao/dev` lúc tổng hợp (2026-10-17). `AI20K#n` = PR trên repo `AI20K-Build-Phase-Cohort-4`; `nngocnd#n` = PR trên repo `nngocnd/bookingbot-mvp` (đánh số lại từ #2).
>
> **Bí danh tác giả đã gộp:** `ngoc.ngodoan` / `NgDoNgoc` / `nngocnd` = Ngô Doãn Ngọc · `Baor-AI` = Nguyễn Văn Bảo · `TaiHoang` = Hoàng Anh Tài. Bỏ commit của bot (`phoenix-mentor[bot]`, initial commit 2026-09-08).

---

## Tổng kết

- **Khoảng thời gian:** 2026-09-23 → 2026-10-17 (25 ngày lịch), **20 ngày có commit**.
- **Commit (không tính merge):** 132.

| Thành viên | Commit (không merge) | Merge commit | Ngày có commit | Mảng chính (theo commit) |
|---|---|---|---|---|
| Ngô Doãn Ngọc | 57 | 16 | 13 | Nền backend + agent, test/eval, deploy (Render, Cloud Run), model layer, OTP Firebase, quan sát AI, seed |
| Nguyễn Văn Bảo | 44 | 7 | 11 | Web người mua/người bán, sổ đỏ, agent (bộ nhớ, follow-up), sau buổi xem, guardrail, kill switch, QA |
| Hoàng Anh Tài | 31 | 9 | 6 | Spec, backlog, sơ đồ, ARCHITECTURE, README, dữ liệu mẫu, CI/CD ban đầu |

- **PR đã merge:** 19 — AI20K#1, #2, #21, #22, #23, #24, #25, #26, #27, #28, #29, #30, #31; nngocnd#2, #3, #4, #5, #6, #7.
- Ghi chú: 2 commit của Bảo (`dfbd525`, `841d584`) chỉ nằm trên nhánh local `bao/dev-backup`; `dfbd525` là bản trùng nội dung của `54c946a` đã merge. Chúng vẫn được tính trong 44 vì lấy theo `--all`.

| Tuần | Ngọc | Bảo | Tài |
|---|---|---|---|
| W1 (21–27/09) | 0 | 0 | 21 |
| W2 (28/09–04/10) | 31 | 18 | 5 |
| W3 (05–11/10) | 2 | 13 | 5 |
| W4 (12–17/10) | 24 | 13 | 0 |

---

## 2026-09-23

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Hoàng Anh Tài | README boilerplate cho BookingBot AI | Đã merge | `ae030ec` |

## 2026-09-25

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Hoàng Anh Tài | Cập nhật spec, CLAUDE.md, backlog theo spec v2 | Đã merge | `1650ee5`, `822985e`, `7bfb65d` |
| Hoàng Anh Tài | Sơ đồ kiến trúc, luồng, system overview, current journey | Đã merge | `6d34452`, `cec70bc`, `8d727a9` |
| Hoàng Anh Tài | Sửa bảng markdown trong spec; đổi Sale/Operator thành chủ nhà | Đã merge | `fce7644`, `a4e96b4` |

## 2026-09-26

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Hoàng Anh Tài | Đồng bộ sơ đồ, kiến trúc, plan, tasks, backlog, CLAUDE.md với spec_updated v1.0; format bảng GFM | Đã merge | `d697dd1`, `43a2650`, `cafa804`, `148ff0d` |
| Hoàng Anh Tài | CI mở rộng nhánh + workflow CD tự động | Đã merge | `f25b647` |
| Hoàng Anh Tài | Phân công Frontend, DevOps & Security cho Ngọc | Đã merge | `4e016a2`, `1463dd8` |
| Hoàng Anh Tài | Viết lại ARCHITECTURE.md (thêm rồi revert phần thực thể DB) | Đã merge | `0bc7a92`, `474d250`, `393cf3e` |
| Hoàng Anh Tài | Dữ liệu mẫu: properties_seed.csv, dự án, tòa, tiện ích, người dùng, tin chờ duyệt | Đã merge | `f352d07`, `b8872a3` |

**Tổng kết tuần 1:** chỉ có commit của Tài, tập trung vào spec, sơ đồ, backlog và dữ liệu mẫu.

## 2026-09-28

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Ngô Doãn Ngọc | Backend MVP trên PostgreSQL: model + migration, exclusion constraint chống trùng lịch, JWT, dịch vụ tìm kiếm / lịch / booking, 34 test gồm race 10 luồng | Đã merge | `aa2422b` |

## 2026-09-29

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Hoàng Anh Tài | Thêm spec_final.md | Đã merge | `f17ef4e`, AI20K#1 |
| Ngô Doãn Ngọc | Dùng spec_final làm spec duy nhất | Đã merge | `04341f6`, `38cf54f` |
| Ngô Doãn Ngọc | DB: hồ sơ người mua/bán, media, OTP, Deal, hold, lịch rảnh người mua | Đã merge | `cd3b3d7`, `9bfa948` |
| Ngô Doãn Ngọc | Đăng nhập OTP; Operator xác thực chủ căn; media, giấy tờ, rút tin | Đã merge | `1f98d66`, `8e4775c`, `bc2bd0b` |
| Ngô Doãn Ngọc | Khớp lịch; Deal cho mỗi yêu cầu xem; chủ căn xác nhận tạo hold; đổi lịch | Đã merge | `b2fe440`, `277b9a6`, `cdcdd18` |
| Ngô Doãn Ngọc | Agent LangGraph với bộ tool spec_final; lưu lượt chat; thông báo T-24h/T-2h; hàng chờ escalation | Đã merge | `b6d209f`, `2263f1b`, `0a91497`, `b35a3c1` |
| Ngô Doãn Ngọc | Sửa deadlock exclusion constraint → `SLOT_UNAVAILABLE` | Đã merge | `551e7b5` |
| Ngô Doãn Ngọc | Hỗ trợ Gemini làm model | Đã merge | `b99349e` |
| Ngô Doãn Ngọc | Web người mua, cổng người bán, Operator Console | Đã merge | `4745267`, `ed14104` |
| Ngô Doãn Ngọc | Test e2e Core Demo Flow, golden set 24 kịch bản | Đã merge | `9e99965`, AI20K#2 |

**Tổng kết ngày:** 19 commit của Ngọc dựng toàn bộ nền MVP, merge qua AI20K#2.

## 2026-09-30

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Ngô Doãn Ngọc | Merge golden set; deploy Vercel + Render + Neon; giữ LF cho shell script | Đã merge | AI20K#21, `bdd7742`, `3e77c02`, AI20K#22 |
| Nguyễn Văn Bảo | Màn chọn vai trò, web người mua có chat khách vãng lai, xác thực sổ đỏ | Đã merge | `7bb6ffe` |
| Nguyễn Văn Bảo | Sửa deploy: giữ dữ liệu sổ đỏ trong image; OTP_EXPOSE_CODE cho OTP sổ đỏ; bỏ qua `.vercel` | Đã merge | `45039a5`, `9ea5f71` |
| Ngô Doãn Ngọc | Thêm sổ đỏ demo còn thiếu vào DB đã seed | Đã merge | `b016056`, AI20K#23 |

## 2026-10-03

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Nguyễn Văn Bảo | README và sơ đồ data flow của hệ thống hiện tại; sửa lỗi Mermaid | Đã merge | `85e30bb`, `78c9168`, `db10276` |
| Nguyễn Văn Bảo | Báo SĐT đã tồn tại; slogan động trước màn người mua | Đã merge | `fd410f5` |
| Nguyễn Văn Bảo | Agent theo đuổi mục tiêu, nhớ người mua, follow-up khi vắng | Đã merge | `defc323` |
| Ngô Doãn Ngọc | Upload media lên S3-compatible (Supabase/R2/S3) | Đã merge | `ce1350e` |

## 2026-10-04

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Nguyễn Văn Bảo | Auth: báo SĐT tồn tại chỉ khi đăng ký; tách trang đăng nhập người bán / Operator | Đã merge | `16668ca`, `3ba5cc7` |
| Nguyễn Văn Bảo | Đổi giờ yêu cầu chưa được trả lời; mọi bước người mua trong chat | Đã merge | `0d3f4e7`, `d594631` |
| Nguyễn Văn Bảo | Streaming SSE; robot "Trợ lý AI"; panel kết quả và chi tiết căn cạnh chat | Đã merge | `99c57ae`, `7232005`, `ce7e8af`, `ce79d9e`, AI20K#24 |
| Nguyễn Văn Bảo | Sửa tìm "2 phòng ngủ"; giải thích sơ đồ data flow | Đã merge | `cea1366`, `984bdfe` |
| Hoàng Anh Tài | README hướng dẫn MVP, tính năng PR-24, câu hỏi mẫu; sửa script ai-log trên macOS | Đã merge | `be5d2e4`, `8dc11a3`, `1e42819`, `13ae68d`, AI20K#25, #26 |
| Ngô Doãn Ngọc | Redeploy Vercel; sửa `/` cuối `VITE_API_URL` | Đã merge | `b3f84c1`, `b334096` |
| Ngô Doãn Ngọc | Manual eval 9 case; giảm 4 → 2 lần gọi LLM, Flash-Lite; giữ retry; báo cáo eval | Đã merge | `6500186`, `7510cfa`, `cd08a4d`, `77cb905`, `427f5ea`, AI20K#27 |

**Tổng kết ngày:** ngày nhiều commit nhất (21), cả 3 thành viên cùng commit; có bản báo cáo eval đầu tiên.

## 2026-10-06

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Nguyễn Văn Bảo | API tổng quan người bán; seed câu chuyện demo | Đã merge | `ed4bb3a`, `0289ebd` |
| Nguyễn Văn Bảo | Thiết kế lại khu người mua (v2) và người bán; QR vào cửa; xem ảnh toàn màn hình | Đã merge | `ee94137`, `0a003a0`, `58b4082`, `d973fea` |

## 2026-10-07

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Nguyễn Văn Bảo | Trang "Hoạt động"; giới hạn OTP | Đã merge | `a4b0d41` |
| Nguyễn Văn Bảo | Chồng lịch theo chủ căn, ảnh tải từ máy, tin lấy từ sổ đỏ, hỗ trợ sổ đỏ | Đã merge | `c48d948` |
| Ngô Doãn Ngọc | Workflow deploy Cloud Run song song Render | Đã merge | `aa19b8a` |

## 2026-10-08

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Ngô Doãn Ngọc | Thêm 35 ảnh nội thất demo; merge nhánh của Bảo | Đã merge | `c3b1445`, `fcdd2df` |
| Nguyễn Văn Bảo | Sau buổi xem: kết quả, phản hồi người mua, tranh chấp; seed showcase | Đã merge | `ccd01a2`, `1060505`, AI20K#28 |

## 2026-10-09

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Hoàng Anh Tài | Viết lại spec_final bằng tiếng Việt; bỏ LaTeX; KPI dễ hiểu và đo được; luồng theo lịch trống định sẵn | Đã merge | `9e7cc97`, `3f99990`, `448dbaa`, `d874dab`, `4874906`, AI20K#29, #30 |
| Nguyễn Văn Bảo | Sửa theo báo cáo QA (người mua, người bán, MVP); giờ chủ căn đề xuất | Đã merge | `046f38f` |

## 2026-10-10

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Nguyễn Văn Bảo | Trace AI (`ai_turns`), ngữ cảnh ca Operator, yêu cầu `EXPIRED`, nhảy tới mục từ thông báo, OpenRouter | Đã merge | `785aca8` |

## 2026-10-11

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Nguyễn Văn Bảo | Sửa theo báo cáo test Operator (múi giờ, buổi xem đã qua, ca cũ, quy tắc hàng chờ) | Đã merge | `d9e1eb4` |
| Ngô Doãn Ngọc | Merge nhánh của Bảo và spec/README vào nhánh đồng bộ deploy | Đã merge | `a42437e`, `349878f`, `70d9a77`, AI20K#31 |

## 2026-10-12

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Ngô Doãn Ngọc | Langfuse; provider Groq; Cloud Run dùng OpenRouter | Đã merge | `44ca01d` |
| Ngô Doãn Ngọc | Kết quả tool theo giờ Việt Nam; bảng tài khoản demo + hướng dẫn Operator | Đã merge | `0e21e21`, `c674eaf` |

## 2026-10-13

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Ngô Doãn Ngọc | Ảnh phòng tắm, ban công/view (6 ảnh mỗi tin) | Đã merge | `0e0b947` |
| Ngô Doãn Ngọc | Claude làm model chính, Gemini (OpenRouter) dự phòng | Đã merge | `abb6b7b` |

## 2026-10-14

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Ngô Doãn Ngọc | Sửa lỗi thinking block của Claude (hội thoại append-only) | Đã merge | `3eade64` |
| Ngô Doãn Ngọc | Nút nổi chỉ tới tài khoản demo; OTP SMS thật bằng Firebase | Đã merge | `b81957d`, `7aa7c8c` |

## 2026-10-15

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Ngô Doãn Ngọc | Sửa trùng `@firebase/app` | Đã merge | `c919b92` |
| Ngô Doãn Ngọc | Tiến trình đăng ký / đặt lịch trong chat; "Hoạt động" chỉ cho người đã đăng nhập; giữ hộp đăng ký khi khách đặt lại | Đã merge | `e1f6608`, `db352dd`, `a7cd680` |
| Ngô Doãn Ngọc | Cloud Run: giữ ấm, `min-instances=1`, build agent lúc khởi động; tái tạo kết nối Postgres chết | Đã merge | `070d82e`, `b2ae60c`, `efd46f5`, `772c2bf` |

## 2026-10-16

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Nguyễn Văn Bảo | Guardrail AI, rate limit chat, kill switch; giám khảo AI, streaming theo câu, rate limit dùng chung | Đã merge | `7fd17e5`, `7763fc6`, merge `d48b61d` |
| Nguyễn Văn Bảo | Chuyển kill switch sang dev | Đã merge | `54c946a`, nngocnd#2 |
| Nguyễn Văn Bảo | Bản trên nhánh backup: kill switch cho dev, tài khoản demo không cần OTP | Chưa merge (`bao/dev-backup`) | `dfbd525`, `841d584` |
| Ngô Doãn Ngọc | Làm nổi căn AI gợi ý; SĐT demo không cần SMS, chỉ giữ tài khoản demo; trace LangSmith | Đã merge | `282e7b4`, `9b69d72`, `f56c079` |

## 2026-10-17

| Member | Task | Status | Output |
|--------|------|--------|--------|
| Ngô Doãn Ngọc | Seed đủ mọi trường hợp, chạy một lần mỗi DB; tin đã bán trong seed | Đã merge | `af604f3`, nngocnd#3; `0ba3a90`, nngocnd#5 |
| Ngô Doãn Ngọc | Trang `/dev`: dashboard số liệu + kill switch | Đã merge | `000c7bc`, nngocnd#6 |
| Ngô Doãn Ngọc | Sửa khối secrets Cloud Run; ruff format test | Đã merge | `3c1eb9b`, `fa24fd4`, nngocnd#7 |
| Nguyễn Văn Bảo | Bỏ tab Trợ lý AI khỏi Operator Console; tách đăng nhập Operator/người bán; thông báo bong bóng realtime | Đã merge | `09c8079`, `fe2325d`, `9f627cb`, nngocnd#4 |
| Nguyễn Văn Bảo | Đánh dấu đã bán đóng lịch xem phía trước; QA vòng 2; kill switch `/dev` cần lý do; ảnh căn thành thẻ trong chat; đồng bộ README / .specify / sơ đồ | Chưa merge (`bao/dev`) | `452cdc3`, `bc6d691`, `cf17246`, `ac1c92f`, `e6c67af` |

**Tổng kết ngày:** 13 commit, 5 PR merge trên repo `nngocnd/bookingbot-mvp`; 5 commit QA/tài liệu của Bảo còn chờ merge.
