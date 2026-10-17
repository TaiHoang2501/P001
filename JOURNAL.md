# Weekly Journal — Team BookingBot

> Ghi lại mỗi tuần: học được gì, khó khăn gì, quyết định gì, kế hoạch tiếp.
>
> **Nguồn:** journal này được tổng hợp lại từ lịch sử commit (`git log --all`), nội dung commit message, các PR đã merge và tài liệu trong repo (`backlog.md`, `eval/results/*.md`, `.specify/`). Mọi sự kiện, con số đều lấy từ đó; chỗ nào "vì sao" được suy ra từ commit message hoặc comment trong code thì ghi rõ là suy ra. Journal chưa có cảm nhận cá nhân: **mỗi thành viên nên tự bổ sung phần suy nghĩ / bài học riêng của mình.**
>
> **Thành viên** (vai trò theo `backlog.md`): Hoàng Anh Tài (Leader, Product/PM, spec) · Ngô Doãn Ngọc (AI/Agent, Backend, Frontend, DevOps & Security) · Nguyễn Văn Bảo (Data & Systems). Thực tế theo commit, Bảo làm nhiều phần web/agent/guardrail, Ngọc làm nền backend, eval, deploy và model layer.
>
> **Quy ước mã PR:** `AI20K#n` = PR trên repo `AI20K-Build-Phase-Cohort-4` (tới 2026-10-11); `nngocnd#n` = PR trên repo `nngocnd/bookingbot-mvp` (từ 2026-10-16, đánh số lại từ #2). Chi tiết theo ngày: [WORKLOG.md](WORKLOG.md).

---

## Quyết định kỹ thuật chính

| # | Quyết định | Phương án khác đã có / đã bỏ | Lý do (theo commit / tài liệu) | Ref |
|---|---|---|---|---|
| 1 | Chặn trùng lịch bằng **exclusion constraint `btree_gist`** của PostgreSQL, sau đó mở rộng lên mức **chủ căn** (`owner_id` + khoảng giờ) cho lịch đã xác nhận | Kiểm tra trùng ở tầng ứng dụng; ràng buộc chỉ theo `property_id` | DB là nguồn sự thật, bảo đảm AC-08 kể cả khi 10 người đặt cùng lúc (test race 10 luồng). Mở rộng vì một chủ căn không thể có mặt ở 2 căn cùng giờ; yêu cầu `REQUESTED` được trùng để chủ căn tự chọn | `aa2422b`, `551e7b5`, `c48d948` (AI20K#28) |
| 2 | Agent **không có tool `confirm_viewing` / hold** | Cho agent gọi đủ 15 tool theo spec | Chỉ Owner được xác nhận (AC-05), hold do Service tạo trong cùng transaction; commit ghi "No confirm_viewing / hold tools on purpose", có test khóa điều này | `b6d209f` (AI20K#2) |
| 3 | Model layer nhiều provider: OpenAI → **Gemini** → Gemini Flash-Lite → OpenRouter / Groq → **Claude làm model chính, Gemini (OpenRouter) dự phòng khác provider** | Một provider cố định | Spec cho phép Gemini/OpenAI; Gemini 503 "high demand" làm một lượt chat treo hàng phút nên thêm timeout/retry; Flash-Lite ~1s/bước so với ~3,5s; fallback cùng provider hết quota free (20 req/ngày) nên sau đó cho phép fallback ở provider khác | `b99349e`, `7510cfa`, `cd08a4d`, `785aca8`, `44ca01d`, `abb6b7b` |
| 4 | Xác thực người bán bằng **sổ đỏ + OTP tới SĐT chủ sổ**, bỏ hẳn luồng Operator duyệt người bán | Operator duyệt giấy tờ người bán (bản đầu, `8e4775c`) | Sổ đã xác thực là bằng chứng sở hữu, Operator chỉ duyệt tin. Sau QA thêm điều kiện đăng nhập bằng đúng SĐT trên sổ (`NOT_OWNER_PHONE`) vì commit `452cdc3` ghi người bán khác có thể chiếm hoặc khóa sổ của người khác | `7bb6ffe`, `c48d948`, `046f38f`, `452cdc3`, `bc6d691` |
| 5 | **Khách vãng lai chat ngay**, chỉ cần SĐT + OTP khi chốt lịch; hội thoại chuyển sang tài khoản mới | Bắt đăng ký trước khi chat | Giảm rào cản cho người mua (suy ra từ thiết kế wireframe 1.1–1.6 trong commit) | `7bb6ffe` (AI20K#24) |
| 6 | Trả lời chat bằng **SSE streaming**, sau đó **StreamGate** chỉ thả từng câu đã qua kiểm tra | Trả nguyên câu trả lời một lần | Rút thời gian chờ cảm nhận; StreamGate để "câu vi phạm không bao giờ hiện ra", có sự kiện `replace` khi phải thay | `99c57ae`, `7763fc6` |
| 7 | **Guardrail bằng code** (regex + kiểm tra theo kết quả tool) và **giám khảo AI model nhỏ chỉ gọi khi có dấu hiệu rủi ro** | Chỉ dựa vào system prompt; gọi giám khảo mọi lượt | Bắt các vi phạm AC-01/05/10 kể cả khi model lách prompt; giám khảo chỉ chạy khi cần (suy ra: để tiết kiệm độ trễ/chi phí), không bao giờ tha lỗi kiểm tra dữ liệu (`unconfirmed_claim`, `unknown_unit`) | `7fd17e5`, `7763fc6` (merge `d48b61d`) |
| 8 | **Kill switch Trợ lý AI thuộc về dev**, không phải Operator | Trang "Trợ lý AI" trong Operator Console (bản đầu) | Commit `54c946a`: người biết khi nào phải tắt AI (trace sai, provider lỗi, chi phí tăng, bị tấn công) là dev theo dõi hệ thống; Operator xử lý ngoại lệ nghiệp vụ | `7fd17e5` → `54c946a`, `09c8079`, `000c7bc` (nngocnd#6) |
| 9 | Rate limit và thông báo realtime **đếm / đọc qua bảng PostgreSQL** | Bộ nhớ tiến trình; pub/sub riêng | Dùng chung mọi instance (Cloud Run có thể nhiều instance); SSE thông báo đọc bảng `notifications` theo chu kỳ "so it works across API instances" | `7763fc6`, `9f627cb` (nngocnd#4) |
| 10 | Deploy: **Vercel + Render + Neon** → thêm **Cloud Run** (GitHub Actions, Secret Manager, Workload Identity) rồi tối ưu cold start | Chỉ Render free plan | Commit Cloud Run không nêu lý do chuyển. Sau khi chuyển: cold start ~22s → ~4s nhờ ping `/health`, job migration riêng, `min-instances=1`, build agent lúc khởi động | `bdd7742`, `aa19b8a`, `070d82e`, `b2ae60c`, `efd46f5` |
| 11 | **Seed chạy một lần mỗi DB** (`seed.version` trong `system_settings`) | Seed `--if-empty` + nhiều cờ `--ensure-*` chạy mỗi lần khởi động | `--if-empty` làm DB đã seed trước đó thiếu dữ liệu sổ đỏ mới (`b016056`); seed-once giảm ~2,5s → ~0,6s mỗi lần khởi động | `b016056`, `af604f3` (nngocnd#3) |
| 12 | OTP thật bằng **Firebase Phone Auth**, giữ `OTP_PROVIDER=local` cho dev/test; SĐT demo dùng mã cố định `123456` | Chỉ hiện mã OTP trên màn hình (`OTP_EXPOSE_CODE`) | Gửi SMS thật cho người dùng thật, nhưng demo không tốn SMS / không bị rate limit | `7aa7c8c`, `9b69d72` |
| 13 | Quan sát AI: bảng **`ai_turns`** trong DB + **Langfuse** + **LangSmith**, đều che SĐT/email | Chỉ log ứng dụng | Dev cần xem từng bước model/tool, token, thời gian; dữ liệu cá nhân được che trước khi xuất ra ngoài | `785aca8`, `44ca01d`, `f56c079` |
| 14 | Bộ nhớ agent trong **PostgreSQL** (`langgraph-checkpoint-postgres`) + tiêu chí/lịch rảnh của người mua lưu ở `buyer_profiles` | Bộ nhớ tiến trình | Hội thoại không mất khi restart/đổi instance; có fallback về bộ nhớ tiến trình | `defc323` |
| 15 | Ảnh người bán tải lên lưu trong **PostgreSQL (`media_files`)** | Upload lên S3-compatible (Supabase/R2/S3) — `ce1350e` | Commit `c48d948` chuyển sang `media_files` phục vụ qua API nhưng **không ghi lý do**; S3 vẫn là đích dài hạn theo CLAUDE.md | `ce1350e`, `c48d948` |

---

## Week 1: 2026-09-21 - 2026-09-27

### Mục tiêu tuần này
- [x] Chốt đặc tả sản phẩm (spec) và backlog cho MVP
- [x] Vẽ sơ đồ kiến trúc / luồng người dùng
- [x] Chuẩn bị dữ liệu mẫu Vinhomes và khung CI/CD

### Đã hoàn thành
- Tài cập nhật README boilerplate cho BookingBot (`ae030ec`, 23/09), viết và nhiều lần chỉnh spec (`1650ee5`, `fce7644`, `cafa804`), backlog (`148ff0d`) và CLAUDE.md theo spec v2 / spec_updated v1.0 (`7bfb65d`, `d697dd1`).
- Bộ sơ đồ kiến trúc và luồng (`6d34452`, `cec70bc`, `8d727a9`, `43a2650`); ARCHITECTURE.md viết lại bằng ngôn ngữ dễ hiểu (`0bc7a92`).
- Phân công workstream Frontend và DevOps & Security cho Ngọc trong backlog/README (`4e016a2`, `1463dd8`).
- CI mở rộng nhánh + workflow CD tự động (`f25b647`).
- Dữ liệu mẫu: template `properties_seed.csv` và bộ dữ liệu dự án, tòa, tiện ích, người dùng, tin chờ duyệt (`f352d07`, `b8872a3`).

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|----------|-----------|---------|
| Bảng markdown trong spec hiển thị sai | Chuyển toàn bộ sang bảng GFM pipe | `fce7644`, `cafa804` |
| Vai trò trung gian trong spec chưa đúng hướng "kết nối trực tiếp" | Thay "Sale/Operator" bằng "chủ nhà" trong spec và sơ đồ | `a4e96b4` |
| Phần thực thể/trường DB thêm vào ARCHITECTURE.md bị rút lại | Revert cùng ngày (commit không ghi lý do) | `474d250` → `393cf3e` |

### Bài học
- Spec thay đổi nhiều vòng trong tuần đầu (spec → spec v2 → spec_updated v1.0), nên phải đồng bộ lại cả sơ đồ, backlog và CLAUDE.md mỗi lần (`7bfb65d`, `d697dd1`); sang tuần 2 nhóm gom về một file `spec_final.md` duy nhất (`38cf54f`).

### Kế hoạch tuần sau
- [x] Chốt `spec_final.md` (đã làm: `f17ef4e`, AI20K#1)
- [x] Dựng backend + agent + web theo spec (đã làm: AI20K#2)

---

## Week 2: 2026-09-28 - 2026-10-04

### Mục tiêu tuần này
- [x] Có bản MVP chạy được toàn bộ Core Demo Flow (tìm căn → yêu cầu xem → Deal → chủ căn xác nhận → hold)
- [x] Deploy công khai
- [x] Đo chất lượng AI (golden set + manual eval)

### Đã hoàn thành
- **Nền backend + agent (Ngọc, AI20K#2, 28–29/09):** PostgreSQL + Alembic, exclusion constraint chống trùng lịch, JWT/OTP, xác thực người bán, Deal ID, hold khi chủ căn xác nhận, agent LangGraph với bộ tool của spec_final, thông báo T-24h/T-2h, hàng chờ escalation, web người mua / người bán / Operator (`aa2422b` … `ed14104`).
- **Test & eval (Ngọc, AI20K#21):** e2e Core Demo Flow + golden set 24 kịch bản / 14 nhóm, có validate trong CI (`9e99965`).
- **Deploy (Ngọc, AI20K#22):** Vercel (web) + Render (API) + Neon (Postgres) (`bdd7742`).
- **Luồng người mua/người bán mới (Bảo, AI20K#24):** màn chọn vai trò, khách vãng lai chat rồi đăng ký khi chốt lịch, xác thực sổ đỏ (`7bb6ffe`); agent tự theo đuổi mục tiêu, nhớ người mua, nhắn follow-up (`defc323`); đổi giờ khi chủ căn chưa trả lời (`0d3f4e7`); mọi bước người mua nằm trong chat (`d594631`); streaming SSE (`99c57ae`) và giao diện chat mới (`7232005`, `ce7e8af`, `ce79d9e`).
- Ngọc thêm upload media lên S3-compatible (`ce1350e`).
- Tài chốt `spec_final.md` (`f17ef4e`, AI20K#1), viết lại README hướng dẫn MVP và câu hỏi mẫu (`be5d2e4`, `8dc11a3`, `1e42819`; AI20K#25, #26).
- **Eval & tối ưu (Ngọc, 04/10):** manual eval 9 case trên production, báo cáo đánh giá: golden set 23/24, coverage 92%, 208 test (`6500186`, `427f5ea`; `eval/results/report.md`). Các commit này vào main qua nhánh `migrate/bookingbot-mvp` (AI20K#27).

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|----------|-----------|---------|
| Hai người đặt trùng giờ cùng lúc: Postgres báo deadlock `40P01` (không phải `IntegrityError`), người thua nhận lỗi 500 | Coi `23P01` và `40P01` là "slot đã có người đặt", trả `SLOT_UNAVAILABLE` kèm giờ khác | `551e7b5`: race 10 luồng pass 15/15 lần chạy |
| Gemini trả 503 "high demand", một lượt chat treo hàng phút; `gemini-2.5-flash` đóng với tài khoản API mới | `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES`, báo `AGENT_UNAVAILABLE`; dùng `gemini-flash-lite-latest` | `b99349e` |
| Image Docker không khởi động: package cài dưới `/root` không đọc được với user non-root | Cài vào `/opt/venv` | `bdd7742` |
| API trên Render không lên vì `.dockerignore` loại `data/` (thiếu CSV sổ đỏ) | Giữ dữ liệu seed sổ đỏ trong image | `45039a5` |
| DB đã seed trước đó có 0 sổ đỏ (seed `--if-empty` bỏ qua), mọi lần nhận sổ đều báo không khớp | `ensure_red_books()` chạy mỗi lần khởi động, chỉ thêm sổ còn thiếu | `b016056` (AI20K#23) |
| Streaming 404 khi `VITE_API_URL` có dấu `/` cuối | Bỏ `/` cuối trước khi nối đường dẫn | `b334096` |
| "2 phòng ngủ" trả về căn lớn hơn, đắt hơn | Thêm `bedrooms` (lọc cứng) tách khỏi `bedrooms_min`; ngân sách không còn là "mục tiêu", căn rẻ hơn lên trước | `cea1366` |
| Một lượt tìm căn gọi LLM 4 lần nối tiếp (~3,5s/lần), median 8,0s | Đưa danh sách dự án vào system prompt, `search_properties` trả luôn giờ xem; dùng Flash-Lite | `7510cfa`: 2 lần gọi; median manual 8,0s → 2,9s (report.md) |
| Bỏ retry làm lỗi nhỏ đổ sang fallback Flash đã hết quota free (20 req/ngày) → 503 | Giữ retry trên model chính | `cd08a4d` |
| Sơ đồ Mermaid lỗi parse vì `;` | Sửa cú pháp | `db10276` |

### Bài học
- Ràng buộc ở DB đã bảo đảm đúng nghiệp vụ (tối đa một booking mỗi khung giờ), nhưng phải test đồng thời mới lộ ra lỗi báo sai cho người thua (`551e7b5`).
- Seed kiểu "chỉ khi DB rỗng" không đưa được dữ liệu mới vào DB đã có sẵn (`b016056`); vấn đề này dẫn tới thiết kế seed-once ở tuần 4.
- Độ trễ chủ yếu nằm ở số lần gọi LLM nối tiếp (server + DB ~0,2s theo report.md), nên giảm số vòng tool hiệu quả hơn tối ưu backend.

### Kế hoạch tuần sau
- [x] Thiết kế lại khu vực người mua / người bán (đã làm: `ee94137`, `0a003a0`)
- [x] Xử lý giai đoạn sau buổi xem (đã làm: `ccd01a2`)
- [ ] Độ trễ lượt tìm / đặt lịch vẫn trên mục tiêu (report.md: lượt tìm căn 9,0s) — còn mở

---

## Week 3: 2026-10-05 - 2026-10-11

### Mục tiêu tuần này
- [x] Thiết kế lại giao diện người mua / người bán
- [x] Hoàn thiện nghiệp vụ lịch xem (chồng lịch theo chủ căn, sau buổi xem, hết hạn)
- [x] Sửa lỗi từ các vòng QA
- [x] Chuẩn bị deploy Cloud Run

### Đã hoàn thành
- **Bảo:** API tổng quan người bán, tên người mua cho người bán (`ed4bb3a`); thiết kế lại khu người mua (v2) và người bán (`ee94137`, `0a003a0`); mã QR vào cửa, người mua chỉ đăng nhập bằng SĐT (`58b4082`); trang "Hoạt động" (`a4b0d41`).
- **Bảo, AI20K#28:** chồng lịch theo chủ căn, ảnh tải từ máy, tin đăng lấy thông tin từ sổ đỏ, luồng hỗ trợ sổ đỏ (`c48d948`); sau buổi xem: ghi nhận kết quả, phản hồi người mua, tranh chấp (`ccd01a2`); seed showcase (`1060505`).
- **Bảo:** sửa theo báo cáo QA người mua/người bán/MVP và giờ chủ căn đề xuất (`046f38f`); trace AI `ai_turns`, ngữ cảnh ca cho Operator, yêu cầu `EXPIRED`, provider OpenRouter (`785aca8`); sửa theo báo cáo test Operator B1–B10 (`d9e1eb4`).
- **Ngọc:** workflow deploy Cloud Run song song Render (`aa19b8a`); thêm 35 ảnh nội thất demo (`c3b1445`); đồng bộ nhánh deploy (AI20K#31).
- **Tài:** viết lại spec_final bằng tiếng Việt rõ ràng, KPI đo được bằng hệ thống, luồng chính theo lịch trống định sẵn của chủ căn (`9e7cc97`, `448dbaa`, `d874dab`, `4874906`; AI20K#29, #30).

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|----------|-----------|---------|
| Ràng buộc trùng lịch theo căn không đủ: một chủ căn có thể bị xác nhận 2 buổi xem cùng giờ ở 2 căn | Exclusion constraint `ex_bookings_owner_no_overlap` trên `owner_id` (trigger điền); xác nhận một người thì đóng các yêu cầu trùng và báo người mua kèm giờ khác | `c48d948` |
| Chủ căn không trả lời tới giờ xem thì yêu cầu treo mãi | Job nền chuyển `EXPIRED`, báo người mua | `785aca8` |
| Báo cáo test Operator: sai múi giờ ở ca tranh chấp, ca "người bán không trả lời" cho buổi đã tới giờ, ca cũ không tự đóng | Đổi sang giờ địa phương, job tự đóng ca thừa, ghi chú đóng ca ≥ 10 ký tự, "Nhận lại ca" | `d9e1eb4` |
| Phiên đăng nhập hết hạn giữa chat làm mất câu hỏi | Đăng nhập lại và quay về đúng cuộc chat, giữ câu chưa gửi | `046f38f` |
| Công thức LaTeX trong spec làm lỗi trình hiển thị | Đổi sang text markdown | `3f99990` |

### Bài học
- Rút ra từ commit `c48d948`: ràng buộc nghiệp vụ "không trùng lịch" cần đặt theo con người (chủ căn), không chỉ theo tài sản.
- Các vòng QA có báo cáo đánh mã lỗi (B1–B10) được sửa gọn trong một commit, dễ đối chiếu (`d9e1eb4`).

### Kế hoạch tuần sau
- [x] Đưa production sang Cloud Run và theo dõi AI (đã làm: `44ca01d`, `070d82e`)
- [x] Guardrail và kill switch cho Trợ lý AI (đã làm: `7fd17e5`, `7763fc6`)
- [x] OTP SMS thật (đã làm: `7aa7c8c`)

---

## Week 4: 2026-10-12 - 2026-10-17

### Mục tiêu tuần này
- [x] Ổn định production trên Cloud Run (model, OTP, cold start)
- [x] An toàn AI: guardrail, rate limit, kill switch, quan sát
- [x] Dữ liệu demo đủ mọi trường hợp cho Demo Day
- [x] QA vòng 2

### Đã hoàn thành
- **Ngọc — model & quan sát:** Langfuse, provider Groq, Cloud Run dùng OpenRouter (`44ca01d`); Claude làm model chính, Gemini qua OpenRouter dự phòng (`abb6b7b`); trace sang LangSmith (`f56c079`).
- **Ngọc — đăng nhập & deploy:** OTP SMS thật bằng Firebase Phone Auth (`7aa7c8c`); SĐT demo không cần SMS, chỉ giữ tài khoản demo (`9b69d72`); giữ Cloud Run ấm, cold start ~22s → ~4s (`070d82e`, `b2ae60c`, `efd46f5`).
- **Ngọc — trải nghiệm & demo:** bảng tài khoản demo + hướng dẫn Operator ở trang đầu (`c674eaf`, `b81957d`); hiện tiến trình đăng ký / đặt lịch trong chat (`e1f6608`); làm nổi căn AI gợi ý (`282e7b4`); seed đủ mọi trường hợp, chạy một lần mỗi DB (`af604f3`, nngocnd#3); tin đã bán trong seed (`0ba3a90`, nngocnd#5); trang `/dev` dashboard số liệu + kill switch (`000c7bc`, nngocnd#6).
- **Bảo — an toàn AI:** guardrail đầu vào/đầu ra, rate limit chat, kill switch (`7fd17e5`); giám khảo AI, streaming theo câu, rate limit dùng chung (`7763fc6`); merge `d48b61d` ghi golden set 38/38 và 351 test pass; chuyển kill switch sang dev (`54c946a`; merge nngocnd#2).
- **Bảo — nghiệp vụ & QA:** bỏ tab Trợ lý AI khỏi Operator Console, tách đăng nhập Operator/người bán, thông báo bong bóng realtime cho 3 vai trò (`09c8079`, `fe2325d`, `9f627cb`; nngocnd#4); đánh dấu đã bán đóng các lịch xem phía trước (`452cdc3`); QA vòng 2: bán cho ai, quy trình Operator, quyền riêng tư (`bc6d691`); sửa ảnh trong chat và đồng bộ tài liệu (`ac1c92f`, `e6c67af`). Năm commit cuối này đang ở nhánh `bao/dev`, chưa merge vào `main` lúc tổng hợp.
- Golden set chạy lại 17/10 với `anthropic/claude-sonnet-5-5`: **38/38 (100%)**, p95 9,9s (`eval/results/golden_report.md`).

### Khó khăn & Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|----------|-----------|---------|
| Claude báo 400 "thinking block is bound to a different conversation" ở lượt 2, vì system prompt dựng lại mỗi lần với giờ hiện tại | Dựng system prompt một lần mỗi hội thoại, đóng dấu giờ vào từng tin nhắn người mua, gửi toàn bộ lịch sử | `3eade64` |
| Đăng nhập Firebase lỗi "Component auth has not been registered yet" do có 2 bản `@firebase/app` | Giữ một bản duy nhất | `c919b92` |
| Lượt chat đầu trên instance Cloud Run mới chờ ~22s (import SDK, compile graph, chặn event loop) | Build agent lúc khởi động; Cloud Scheduler ping `/health`; migration/seed thành Cloud Run job; `min-instances=1` | `efd46f5`, `070d82e`, `b2ae60c`: ~4s |
| Instance chạy lâu thì Neon cắt kết nối SSL nhàn rỗi → "SSL error: unexpected eof" | Kiểm tra kết nối trước khi dùng, đóng kết nối nhàn rỗi > 4 phút | `772c2bf` |
| Regex chống prompt injection chặn nhầm câu thường ("đóng vai trò", "Gia Lâm", "bỏ qua tiêu chí") và bỏ sót tiếng Việt không dấu | Khớp cả không dấu, bỏ các mẫu chặn nhầm; giám khảo AI xử lý ca khó | `7763fc6`: golden set thêm 7 kịch bản tấn công / chặn nhầm |
| Rate limit theo IP khách có thể bị giả qua `X-Forwarded-For` | Đọc IP từ phải sang theo `TRUSTED_PROXY_HOPS` / `CLIENT_IP_HEADER`, có endpoint kiểm tra sau deploy | `7763fc6`, `54c946a` |
| Lỗ hổng: xác nhận OTP sổ đỏ không bắt buộc SĐT trên sổ, người bán khác có thể chiếm / khóa sổ | Bắt buộc đúng SĐT chủ sổ | `452cdc3` |
| Deploy Cloud Run lỗi vì comment trong khối `secrets` bị đọc thành mount path | Bỏ comment | `3c1eb9b` (nngocnd#7) |
| CI kiểm tra format thất bại | `ruff format` file test | `fa24fd4` |

### Bài học
- Rút ra từ `3eade64`: với model có "thinking", lịch sử hội thoại phải chỉ được nối thêm (append-only); thông tin thay đổi theo thời gian nên gắn vào tin nhắn thay vì system prompt.
- Rút ra từ `54c946a`: công tắc khẩn cấp nên nằm ở người thấy được tín hiệu (trace, lỗi provider, chi phí), không ở người vận hành nghiệp vụ.
- Kiểm tra theo dữ liệu (lịch "đã xác nhận" phải có kết quả tool `CONFIRMED`, mã căn phải có trong kết quả tool) không được để model tha (`7763fc6`).
- Trạng thái dùng chung (rate limit, kill switch, thông báo) đặt ở PostgreSQL thì không phụ thuộc số instance.

### Kế hoạch tuần sau
- [ ] Merge 5 commit của `bao/dev` (`452cdc3`, `bc6d691`, `cf17246`, `ac1c92f`, `e6c67af`) vào `main`
- [ ] Thu thập phản hồi người dùng thật (report.md: "Chưa thu thập")
- [ ] Độ trễ: golden p95 9,9s vẫn trên mục tiêu ≤ 5s của spec §2.2
- [ ] Mỗi thành viên bổ sung phần suy nghĩ cá nhân vào journal này
