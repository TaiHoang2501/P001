# Worklog — xuất thô từ git

> Sinh tự động, không sửa tay. Lệnh:
> `git log --all --no-merges --date=short --format="%ad  %<(16,trunc)%an  %h  %s"` (bỏ commit của bot).
> Mới nhất ở trên. Bí danh tác giả: `ngoc.ngodoan` / `NgDoNgoc` / `nngocnd` = Ngô Doãn Ngọc; `Baor-AI` = Nguyễn Văn Bảo; `TaiHoang` = Hoàng Anh Tài.
> Bản tổng hợp theo ngày: [../WORKLOG.md](../WORKLOG.md). Xuất lúc: 2026-10-17, HEAD `e6c67af` (nhánh `bao/dev`).

```text
2026-10-17  Nguyễn Văn Bảo    e6c67af  docs: align README, .specify and diagrams with the running system
2026-10-17  Nguyễn Văn Bảo    ac1c92f  fix(chat): show homes' photos as cards instead of printing file paths
2026-10-17  Nguyễn Văn Bảo    cf17246  fix(dev): the kill switch on /dev needs a reason, as the API now requires
2026-10-17  Nguyễn Văn Bảo    bc6d691  fix: QA round 2 — sold-to buyer, operator workflow, privacy and wording
2026-10-17  ngoc.ngodoan      fa24fd4  style(tests): ruff format test_notifications.py (CI format check)
2026-10-17  ngoc.ngodoan      3c1eb9b  fix(deploy): no comment inside the Cloud Run secrets block
2026-10-17  ngoc.ngodoan      000c7bc  feat(dev): /dev page with metrics dashboard and AI kill switch
2026-10-17  Nguyễn Văn Bảo    452cdc3  feat(property): marking a home sold closes the viewings ahead and tells those buyers; QA fixes
2026-10-17  ngoc.ngodoan      0ba3a90  feat(seed): a sold listing when Lan's spare red books are already listed
2026-10-17  Nguyễn Văn Bảo    9f627cb  feat(notifications): live pop-up notifications for buyers, sellers and operators
2026-10-17  Nguyễn Văn Bảo    fe2325d  fix(auth): keep the operator and seller sign-ins apart
2026-10-17  Nguyễn Văn Bảo    09c8079  feat(operator): drop the AI assistant tab from the Operator Console
2026-10-17  ngoc.ngodoan      af604f3  feat(seed): every case for each role, loaded once per database
2026-10-16  ngoc.ngodoan      f56c079  feat(observability): trace chat turns to LangSmith
2026-10-16  Nguyễn Văn Bảo    54c946a  feat(admin): move the AI kill switch from operators to developers
2026-10-16  Nguyễn Văn Bảo    841d584  feat(auth): demo accounts sign in without an OTP
2026-10-16  Nguyễn Văn Bảo    dfbd525  feat(admin): move the AI kill switch from operators to developers
2026-10-16  ngoc.ngodoan      9b69d72  feat(auth): demo phones sign in without SMS; keep only demo accounts
2026-10-16  ngoc.ngodoan      282e7b4  feat(chat): highlight the homes the assistant recommended
2026-10-16  Nguyễn Văn Bảo    7763fc6  feat(chat): guardrail judge, sentence-gated streaming, shared rate limits
2026-10-16  Nguyễn Văn Bảo    7fd17e5  feat(chat): AI guardrails, chat rate limits and an operator kill switch
2026-10-15  ngoc.ngodoan      772c2bf  fix(chat): recycle dead Postgres connections in the agent memory pool
2026-10-15  ngoc.ngodoan      a7cd680  fix(chat): keep showing the sign-up box when a guest books again
2026-10-15  ngoc.ngodoan      efd46f5  perf(chat): build the AI agent at start-up, not on the first chat
2026-10-15  ngoc.ngodoan      b2ae60c  feat(deploy): keep one Cloud Run instance up (min-instances=1)
2026-10-15  ngoc.ngodoan      070d82e  feat(deploy): keep Cloud Run warm and cut its cold start from ~22s to ~4s
2026-10-15  ngoc.ngodoan      db352dd  feat(buyer): show "Hoạt động" in the top bar only to signed-in buyers
2026-10-15  ngoc.ngodoan      e1f6608  feat(buyer): stream sign-up and viewing-request progress in the chat
2026-10-15  ngoc.ngodoan      c919b92  fix(web): keep a single @firebase/app so phone sign-in loads Firebase Auth
2026-10-14  ngoc.ngodoan      7aa7c8c  feat: real SMS sign-in codes with Firebase Phone Auth
2026-10-14  ngoc.ngodoan      b81957d  feat: floating pill on the start page pointing to the demo accounts and guide
2026-10-14  ngoc.ngodoan      3eade64  fix: keep Claude conversations append-only so later turns keep their thinking
2026-10-13  ngoc.ngodoan      abb6b7b  feat: Claude as the AI agent's main model, OpenRouter Gemini as fallback
2026-10-13  ngoc.ngodoan      0e0b947  feat(seed): bathroom and balcony/view demo photos, six photos per listing
2026-10-12  ngoc.ngodoan      c674eaf  feat: demo accounts table and operator guide on the start page
2026-10-12  ngoc.ngodoan      0e21e21  fix: show the agent tool results in Vietnam time
2026-10-12  ngoc.ngodoan      44ca01d  feat: Langfuse tracing for AI chat turns; Groq provider; Cloud Run on OpenRouter
2026-10-11  Nguyễn Văn Bảo    d9e1eb4  fix: operator test report (time zone, past viewings, stale cases, queue rules)
2026-10-10  Nguyễn Văn Bảo    785aca8  feat: AI traces, operator case context, expired requests, notification jump and groups
2026-10-09  Nguyễn Văn Bảo    046f38f  fix: QA reports (buyer, seller, MVP) and owner-suggested viewing times
2026-10-09  Hoàng Anh Tài     4874906  docs(spec): refine KPIs to be realistic and measurable by system
2026-10-09  Hoàng Anh Tài     d874dab  docs(spec): align core flow with predefined owner availability
2026-10-09  Hoàng Anh Tài     448dbaa  docs(spec): make KPI targets intuitive in Vietnamese and clarify metrics
2026-10-09  Hoàng Anh Tài     3f99990  fix(spec): replace LaTeX math with clean markdown text to fix renderer error
2026-10-09  Hoàng Anh Tài     9e7cc97  docs(spec): rewrite spec_final in clear Vietnamese and reduce English jargon
2026-10-08  Nguyễn Văn Bảo    1060505  feat(seed): showcase demo cases for every deployment
2026-10-08  Nguyễn Văn Bảo    ccd01a2  feat: after the viewing - outcome, buyer feedback and disputes
2026-10-08  ngoc.ngodoan      c3b1445  feat(seed): 35 more demo interior photos so listings stop sharing covers
2026-10-07  Nguyễn Văn Bảo    c48d948  feat: owner-level viewing overlap, photo uploads, red-book listings, ownership support
2026-10-07  ngoc.ngodoan      aa19b8a  ci(deploy): add Cloud Run deploy alongside Render
2026-10-07  Nguyễn Văn Bảo    a4b0d41  feat(buyer): "Hoạt động" page with the viewing history; fairer OTP limit
2026-10-06  Nguyễn Văn Bảo    d973fea  feat(seller): open listing photos full screen with the home's details
2026-10-06  Nguyễn Văn Bảo    58b4082  feat(buyer): QR viewing pass, phone-only buyer login, redesigned entry and chat
2026-10-06  Nguyễn Văn Bảo    0a003a0  feat(seller): redesigned seller area and clickable notifications
2026-10-06  Nguyễn Văn Bảo    ee94137  feat(buyer): redesigned buyer area (buyer design v2, blue)
2026-10-06  Nguyễn Văn Bảo    0289ebd  feat(seed): demo story seller, interior photos and viewing requests
2026-10-06  Nguyễn Văn Bảo    ed4bb3a  feat(owner): seller overview API, buyer names for sellers, listing ids in notices
2026-10-04  ngoc.ngodoan      427f5ea  docs(eval): fill evaluation report with measured results
2026-10-04  ngoc.ngodoan      77cb905  docs(eval): before/after latency of the manual cases on production
2026-10-04  ngoc.ngodoan      cd08a4d  fix(agent): keep retries on the main model
2026-10-04  ngoc.ngodoan      7510cfa  perf(agent): cut a search turn from 4 LLM calls to 2 and use Flash-Lite
2026-10-04  ngoc.ngodoan      6500186  docs(eval): manual eval evidence, 9 cases against the live API
2026-10-04  Nguyễn Văn Bảo    cea1366  fix(search): '2 phòng ngủ' finds two-bedroom homes, not pricier larger ones
2026-10-04  ngoc.ngodoan      b334096  fix(web): strip trailing slash from VITE_API_URL so chat streaming doesn't 404
2026-10-04  nngocnd           b3f84c1  chore: redeploy frontend on Vercel
2026-10-04  Nguyễn Văn Bảo    ce79d9e  feat(web): home details beside the chat, clearer buyer header
2026-10-04  Nguyễn Văn Bảo    ce7e8af  feat(web): chat alone until the assistant finds homes, then open the results panel
2026-10-04  Nguyễn Văn Bảo    7232005  feat(web): animated 'Trợ lý AI' robot and a streamed chat reply
2026-10-04  Nguyễn Văn Bảo    99c57ae  feat(chat): stream the assistant's reply over SSE
2026-10-04  Hoàng Anh Tài     1e42819  docs(readme): add dedicated sample queries section for buyer interaction
2026-10-04  Hoàng Anh Tài     8dc11a3  docs: enrich README with PR-24 features (guest chat, red book verification, buyer memory)
2026-10-04  Hoàng Anh Tài     13ae68d  fix(scripts): improve macOS unicode path handling and SSL context in ai-log
2026-10-04  Hoàng Anh Tài     be5d2e4  docs: update README with BookingBot MVP guide and remove boilerplate
2026-10-04  Nguyễn Văn Bảo    3ba5cc7  feat(auth): separate seller and operator login pages without revealing operator accounts
2026-10-04  Nguyễn Văn Bảo    984bdfe  docs(diagram): explain each component of the data flow
2026-10-04  Nguyễn Văn Bảo    d594631  feat(web): every buyer step inside the agent chat
2026-10-04  Nguyễn Văn Bảo    0d3f4e7  feat(booking): let buyers move a request the seller has not answered yet
2026-10-04  Nguyễn Văn Bảo    16668ca  fix(auth): tell 'phone already exists' only on sign-up, not on login
2026-10-03  ngoc.ngodoan      ce1350e  feat(media): upload listing media to S3-compatible storage (Supabase/R2/S3)
2026-10-03  Nguyễn Văn Bảo    defc323  feat(agent): act on goals, remember buyers, follow up while they are away
2026-10-03  Nguyễn Văn Bảo    fd410f5  feat(auth,web): say a phone already exists; animated slogan before the buyer start
2026-10-03  Nguyễn Văn Bảo    db10276  docs(diagram): fix Mermaid parse error in the seller sequence (';' ends a message)
2026-10-03  Nguyễn Văn Bảo    78c9168  docs(diagram): add a data flow diagram of the current system
2026-10-03  Nguyễn Văn Bảo    85e30bb  docs(readme): describe the current web (roles, guest chat, red book verification) and stack
2026-09-30  ngoc.ngodoan      b016056  fix(seed): add missing demo red books to databases seeded before they existed
2026-09-30  Nguyễn Văn Bảo    9ea5f71  chore(web): ignore the local .vercel project link
2026-09-30  Nguyễn Văn Bảo    45039a5  fix(deploy): keep red book seed data in the image; OTP_EXPOSE_CODE for red book OTPs
2026-09-30  Nguyễn Văn Bảo    7bb6ffe  feat: role chooser, buyer web app with guest chat, red book seller verification
2026-09-30  ngoc.ngodoan      3e77c02  chore: keep LF line endings for shell scripts
2026-09-30  ngoc.ngodoan      bdd7742  chore(deploy): Vercel (web) + Render (API) + Neon (Postgres)
2026-09-29  ngoc.ngodoan      9e99965  test: end-to-end Core Demo Flow, AI golden set and run instructions
2026-09-29  ngoc.ngodoan      ed14104  feat(web): seller portal and operator console
2026-09-29  ngoc.ngodoan      4745267  feat(web): buyer web app on the spec_final API
2026-09-29  ngoc.ngodoan      b99349e  feat(llm): support Gemini as the agent's model provider
2026-09-29  ngoc.ngodoan      551e7b5  fix(booking): report exclusion-constraint deadlocks as SLOT_UNAVAILABLE
2026-09-29  ngoc.ngodoan      b35a3c1  feat(escalation): operator exception queue and human escalation
2026-09-29  ngoc.ngodoan      0a91497  feat(notification): in-app event notifications and T-24h/T-2h reminders
2026-09-29  ngoc.ngodoan      2263f1b  feat(ai): persist chat turns, tool results and recommendations
2026-09-29  ngoc.ngodoan      b6d209f  feat(agent): LangGraph buyer agent with the spec_final tool set
2026-09-29  ngoc.ngodoan      cdcdd18  feat(booking): owner confirmation creates the viewing hold; reschedule flow
2026-09-29  ngoc.ngodoan      277b9a6  feat(deal): every viewing request opens a Deal; seller sees level-1 data only
2026-09-29  ngoc.ngodoan      b2fe440  feat(scheduling): match buyer and seller availability into viewing times
2026-09-29  ngoc.ngodoan      bc2bd0b  feat(listing): property media, ownership document and withdrawal
2026-09-29  ngoc.ngodoan      8e4775c  feat(seller): operator verifies owners before they can list or be booked
2026-09-29  ngoc.ngodoan      1f98d66  feat(auth): phone/email OTP login for buyers and sellers
2026-09-29  ngoc.ngodoan      9bfa948  feat(db): deals, viewing holds and buyer availability
2026-09-29  ngoc.ngodoan      cd3b3d7  feat(db): seller/buyer profiles, property media and OTP codes
2026-09-29  ngoc.ngodoan      38cf54f  docs: use spec_final.md from main as the single spec
2026-09-28  ngoc.ngodoan      aa2422b  feat(backend): MVP booking backend on PostgreSQL
2026-09-29  ngoc.ngodoan      04341f6  docs: adopt spec_v2 and align CLAUDE.md with it
2026-09-29  Hoàng Anh Tài     f17ef4e  docs: add spec_final.md
2026-09-26  Hoàng Anh Tài     b8872a3  feat: add investor/operator datasets (projects, buildings, amenities, users, pending listings)
2026-09-26  Hoàng Anh Tài     f352d07  feat: add properties_seed.csv template and schema documentation
2026-09-26  Hoàng Anh Tài     393cf3e  Revert "docs: add core entities and mandatory database fields to ARCHITECTURE.md"
2026-09-26  Hoàng Anh Tài     474d250  docs: add core entities and mandatory database fields to ARCHITECTURE.md
2026-09-26  Hoàng Anh Tài     0bc7a92  docs: rewrite ARCHITECTURE.md with natural, accessible language
2026-09-26  Hoàng Anh Tài     1463dd8  docs: assign DevOps & Security workstream to Ngo Doan Ngoc
2026-09-26  Hoàng Anh Tài     4e016a2  docs: assign Frontend workstream to Ngo Doan Ngoc in backlog and readme
2026-09-26  Hoàng Anh Tài     148ff0d  docs: comprehensive update of backlog.md aligned with spec.md
2026-09-26  Hoàng Anh Tài     cafa804  fix(docs): format all tables into GFM pipe tables in spec_updated.md
2026-09-26  Hoàng Anh Tài     43a2650  Cập nhật System Overview Diagram
2026-09-26  Hoàng Anh Tài     f25b647  ci: expand CI branches and add automated CD workflow
2026-09-26  Hoàng Anh Tài     d697dd1  docs: align all diagrams, architecture, plan, tasks, backlog and claude with spec_updated v1.0
2026-09-25  Hoàng Anh Tài     a4e96b4  docs: replace Sale/Operator with chu nha in spec and diagrams
2026-09-25  Hoàng Anh Tài     fce7644  fix(docs): fix markdown table formatting in spec.md
2026-09-25  Hoàng Anh Tài     8d727a9  docs: add current journey diagram in spec and diagrams
2026-09-25  Hoàng Anh Tài     cec70bc  docs: update system overview diagram according to reference architecture
2026-09-25  Hoàng Anh Tài     7bfb65d  docs: align diagrams, backlog, and CLAUDE.md with spec v2 architecture patch
2026-09-25  Hoàng Anh Tài     6d34452  feat: add architecture and flow diagrams
2026-09-25  Hoàng Anh Tài     822985e  cập nhật Claude và backlog
2026-09-25  Hoàng Anh Tài     1650ee5  cập nhật spec
2026-09-23  Hoàng Anh Tài     ae030ec  Cập nhật nội dung README_boilerplate.md cho BookingBot AI
```

## Pull request đã merge

```text
2026-10-17  NgDoNgoc          f2a3f59  Merge pull request #7 from nngocnd/fix/cloudrun-secrets-comment
2026-10-17  NgDoNgoc          d83bb3c  Merge pull request #6 from nngocnd/feat/dev-dashboard
2026-10-17  NgDoNgoc          1926540  Merge pull request #5 from nngocnd/feat/seed-sold-listing
2026-10-17  Baor-AI           c23a373  Merge pull request #4 from nngocnd/bao/dev
2026-10-17  NgDoNgoc          9db578f  Merge pull request #3 from nngocnd/feat/seed-all-cases-once
2026-10-16  Baor-AI           2c5ed9c  Merge pull request #2 from nngocnd/bao/dev
2026-10-11  NgDoNgoc          31bd867  Merge pull request #31 from AI20K-Build-Phase-Cohort-4/deploy/sync-main-2026-10-11
2026-10-09  TaiHoang          3354dba  Merge pull request #30 from AI20K-Build-Phase-Cohort-4/TaiHoang
2026-10-09  TaiHoang          37f4345  Merge pull request #29 from AI20K-Build-Phase-Cohort-4/TaiHoang
2026-10-08  Baor-AI           819ce30  Merge pull request #28 from AI20K-Build-Phase-Cohort-4/feature/Baor-app
2026-10-04  NgDoNgoc          aac0cb9  Merge pull request #27 from AI20K-Build-Phase-Cohort-4/migrate/bookingbot-mvp
2026-10-04  TaiHoang          b3693bb  Merge pull request #26 from AI20K-Build-Phase-Cohort-4/TaiHoang
2026-10-04  TaiHoang          a22ebc7  Merge pull request #24 from AI20K-Build-Phase-Cohort-4/feature/Baor-app
2026-10-04  TaiHoang          38098c0  Merge pull request #25 from AI20K-Build-Phase-Cohort-4/TaiHoang
2026-09-30  NgDoNgoc          40bee8a  Merge pull request #23 from AI20K-Build-Phase-Cohort-4/fix/red-book-seed-upgrade
2026-09-30  NgDoNgoc          0cb4515  Merge pull request #22 from AI20K-Build-Phase-Cohort-4/feature/20-deploy-vercel-render
2026-09-30  NgDoNgoc          aa6ac6a  Merge pull request #21 from AI20K-Build-Phase-Cohort-4/feature/19-e2e-golden-set
2026-09-29  NgDoNgoc          425237d  Merge pull request #2 from AI20K-Build-Phase-Cohort-4/feature/01-baseline
2026-09-29  TaiHoang          2062540  Merge pull request #1 from AI20K-Build-Phase-Cohort-4/TaiHoang
```
