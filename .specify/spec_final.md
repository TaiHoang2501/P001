# ĐẶC TẢ SẢN PHẨM: TRỢ LÝ AI KẾT NỐI TRỰC TIẾP BẤT ĐỘNG SẢN (AI SPEC)

**Tên sản phẩm:** AI Agent Direct Connect — Trợ lý AI Kết nối Trực tiếp Bất động sản  
**Tên gọi trong phiên bản thử nghiệm (MVP):** BookingBot AI Agent  
**Nhóm chuyên trách:** Bất động sản (BĐS)  
**Mã đề án:** BDSO2O-04  
**Phạm vi áp dụng:** Đại đô thị Vinhomes · Giao diện Web tương thích mọi thiết bị (Responsive Web) · Định hướng AI dẫn dắt (AI-first)  
**Trạng thái tài liệu:** Bản đặc tả kỹ thuật v2.0 (Đã tinh giản thuật ngữ chuyên ngành)  
**Ngày cập nhật:** Tháng 10/2026  

---

# §0. Tóm tắt Tổng quan Dự án

## 0.1. Bài toán thực tế

Khách hàng có nhu cầu mua nhà tại các đại đô thị Vinhomes thường gặp nhiều khó khăn trong việc tìm đúng căn hộ ưng ý và chủ động đặt lịch hẹn xem nhà trực tiếp. Hiện trạng phổ biến là thông tin nhà đất bị phân tán, tin đăng ảo hoặc tin trùng lặp tràn lan, và việc kết nối với chủ căn hộ hầu như phụ thuộc hoàn toàn vào môi giới hoặc nhiều bên trung gian.

**Khách hàng hiện nay phải đối mặt với:**
- Mất nhiều thời gian tìm kiếm thông tin trên hàng chục hội nhóm, website khác nhau.
- Phải liên hệ và tiếp chuyện với quá nhiều nhân viên môi giới.
- Bị yêu cầu cung cấp số điện thoại và thông tin cá nhân cho nhiều bên không quen biết.
- Mất thời gian chờ đợi xác nhận xem căn hộ đó còn trống hay đã bán.
- Bị làm phiền liên tục bởi các cuộc gọi, tin nhắn chào mời rác sau khi để lại thông tin.
- Hoàn toàn bị động trong việc sắp xếp thời gian đi xem nhà thực tế.

**Ở chiều ngược lại, Chủ căn hộ có nhu cầu bán:**
- Thiếu một kênh chính thống, tin cậy để tiếp cận trực tiếp những người mua có nhu cầu thực tế và thiện chí.
- Mất nhiều thời gian tiếp các cuộc gọi thăm dò từ môi giới thay vì người mua thật.
- Khó chủ động quản lý lịch rảnh của bản thân để đón tiếp khách xem nhà.

**Về phía Chủ đầu tư:**
- Nắm giữ toàn bộ dữ liệu xác thực về căn hộ và chủ sở hữu hợp pháp (qua sổ đỏ và hợp đồng mua bán), nhưng chưa có một hệ thống công nghệ thông minh đủ tốt để tự động kết nối nhu cầu giữa người mua thực và nguồn cung chính chủ.

## 0.2. Giải pháp: BookingBot AI Agent

**BookingBot AI Agent** là trợ lý thông minh ứng dụng trí tuệ nhân tạo (AI-first) giúp kết nối trực tiếp Người mua và Chủ nhà:

> **Người mua nhập nhu cầu bằng ngôn ngữ tự nhiên → Trợ lý AI thấu hiểu & tìm kiếm căn phù hợp → Gợi ý các căn hộ chính chủ đã kiểm duyệt → Người mua yêu cầu xem nhà → AI tự động tính toán khung giờ rảnh chung → Chủ nhà bấm duyệt → Hệ thống tạm khóa căn trong khung giờ xem (chống trùng lịch) → Buổi xem nhà diễn ra → Tạo hồ sơ kết nối (Mã giao dịch) → Chuyển sang quy trình thủ tục của Chủ đầu tư khi hai bên chốt mua.**

Mô hình vận hành cốt lõi:

> **Người mua (Buyer)** ── *(Tương tác tự nhiên)* ──► **Trợ lý AI (BookingBot)** ── *(Khớp lịch & Kết nối)* ──► **Chủ nhà (Owner)**

Trong mô hình này:
> **Chủ đầu tư đóng vai trò là Lớp bảo chứng Pháp lý và Giao dịch (Trust & Transaction Layer).**

Chủ đầu tư chịu trách nhiệm xác thực:
- Danh tính chính chủ của Chủ nhà (thông qua đối soát thông tin Sổ đỏ + mã xác thực OTP).
- Tính có thật và thông số pháp lý của Căn hộ.
- Trạng thái căn hộ (đang mở bán, đang tạm khóa giờ xem, hoặc đã bán).
- Giám sát các bước chuyển giao dịch để hỗ trợ thủ tục mua bán chính thức.

## 0.3. Giá trị cốt lõi mang lại

### Đối với Người mua:
> **Tìm đúng căn hộ ưng ý — Không qua môi giới trung gian — Không bị lộ thông tin cá nhân sớm — Hoàn toàn chủ động lịch hẹn xem nhà.**

### Đối với Chủ nhà:
> **Tiếp cận trực tiếp người mua có nhu cầu thực — Không bị môi giới rác làm phiền — Tự chủ quyết định lịch đón tiếp khách.**

### Đối với Chủ đầu tư:
> **Xây dựng nguồn cung căn hộ sạch đã xác thực — Kiểm soát minh bạch hành trình giao dịch — Thúc đẩy giao dịch an toàn ngay trong hệ sinh thái dự án.**

## 0.4. Phạm vi phiên bản thử nghiệm (MVP)

### Nằm trong phạm vi thực hiện (In scope):
- Chỉ áp dụng cho các căn hộ thuộc đại đô thị Vinhomes (Vinhomes Ocean Park, Smart City, Grand Park...).
- Hoạt động trên nền tảng Website tương thích hoàn hảo với cả máy tính và điện thoại di động (Responsive Web).
- Trải nghiệm trò chuyện là trọng tâm: Khách mua bắt đầu hành trình bằng khung chat tự nhiên; khách vãng lai có thể tìm kiếm tự do, chỉ cần xác thực số điện thoại qua OTP khi chốt lịch xem.
- Chủ nhà có thể tự đăng ký thông tin căn hộ cần bán.
- Bắt buộc Chủ đầu tư / Ban quản trị kiểm duyệt hồ sơ căn hộ và đối soát Sổ đỏ trước khi tin đăng hiển thị công khai.
- Trợ lý AI tự động phân tích nhu cầu và gợi ý căn hộ kèm giải thích lý do đề xuất.
- Trợ lý AI tự động tính toán khung giờ giao nhau giữa thời gian rảnh của Người mua và Chủ nhà.
- Quyền quyết định đồng ý lịch hẹn luôn thuộc về Chủ nhà (luôn có sự kiểm soát của con người — Human-in-the-loop).
- Hệ thống tự động cấp một Mã giao dịch (Deal ID) cho mỗi lượt kết nối thành công.
- Cơ chế bảo vệ thông tin cá nhân theo từng nấc: Không chia sẻ số điện thoại của người mua cho chủ nhà khi chưa có sự đồng thuận.
- Cơ chế tạm khóa căn giữ chỗ xem nhà (Viewing Hold): Chỉ có ý nghĩa tạm khóa căn hộ trong đúng khung giờ xem để loại bỏ nguy cơ trùng lịch, **tuyệt đối không phải là đặt cọc giữ chỗ mua bán**.
- Mọi tình huống tranh chấp, sự cố hoặc yêu cầu đặc biệt đều được tự động chuyển về cho Nhân viên hỗ trợ của Chủ đầu tư xử lý.

### Nằm ngoài phạm vi giai đoạn này (Out of scope):
- Không xử lý thanh toán tiền mặt hoặc chuyển khoản trực tuyến.
- Không nhận tiền đặt cọc giữ mua căn hộ.
- Không ký hợp đồng mua bán điện tử trên hệ thống.
- AI không tự ý định giá hoặc dự báo biến động giá bất động sản.
- AI không tham gia đàm phán, mặc cả giá thay cho các bên.
- AI không tự động chốt hoặc phê duyệt giao dịch mua bán.
- Không tích hợp cuộc gọi tự động bằng giọng nói (Voice AI).
- Không mở rộng ra các dự án bất động sản ngoài hệ sinh thái Vinhomes.
- Không kết nối với các hệ thống quản trị môi giới (CRM) bên ngoài.

---

# §1. Đối tượng Người dùng & Bài toán Thực tế

## 1.1. Các bên tham gia hệ thống

| Bên tham gia | Mục tiêu cốt lõi | Quyền hạn và Chức năng chính |
|---|---|---|
| **Người mua (Buyer)** | Tìm đúng căn hộ ưng ý, đặt lịch xem nhà trực tiếp với chủ căn hộ. | Nhắn tin với Trợ lý AI, xem kết quả gợi ý căn hộ, xem chi tiết thông số/hình ảnh, chọn giờ và gửi yêu cầu xem nhà, theo dõi lịch hẹn. |
| **Chủ nhà (Owner)** | Đăng bán căn hộ, tiếp cận khách mua thiện chí, chủ động thời gian tiếp khách. | Đăng tin căn hộ, nhập thông tin Sổ đỏ để xác thực chính chủ, cài đặt các khung giờ rảnh trong tuần, duyệt hoặc từ chối yêu cầu xem nhà, theo dõi tiến độ giao dịch. |
| **Ban quản trị / Chủ đầu tư (Operator)** | Làm sạch nguồn cung, bảo chứng pháp lý và giám sát vận hành toàn hệ thống. | Duyệt tin đăng căn hộ, đối soát thông tin Sổ đỏ chính chủ, quản lý danh mục bất động sản, giám sát lịch đặt hẹn, tiếp nhận và xử lý các trường hợp ngoại lệ. |
| **Trợ lý AI (BookingBot)** | Đóng vai trò chuyên viên tư vấn và điều phối viên thông minh 24/7. | Lắng nghe và bóc tách nhu cầu của khách bằng tiếng Việt, tra cứu cơ sở dữ liệu, chấm điểm độ phù hợp của căn hộ, tính toán khớp lịch rảnh, gửi thông báo nhắc nhở tự động. |
| **Nhân viên hỗ trợ (Human Operator)** | Can thiệp giải quyết các điểm nghẽn và tình huống phát sinh ngoài kịch bản. | Xác minh giấy tờ khi có nghi vấn, hòa giải đổi lịch khi hai bên không tìm được tiếng nói chung, tiếp nhận hồ sơ giao dịch sau khi xem nhà thành công. |

> **Lưu ý:** Trong phiên bản thử nghiệm này, vai trò Ban quản trị và Nhân viên hỗ trợ thuộc quyền quản lý trực tiếp của Chủ đầu tư.

## 1.2. Mong muốn thực tế của từng đối tượng (Job-to-be-Done)

### Người mua:
> *"Khi tôi muốn mua một căn hộ tại Vinhomes, tôi muốn nói rõ nhu cầu của mình bằng ngôn ngữ nói chuyện hàng ngày, được trợ lý AI tìm đúng những căn có thật và hẹn trực tiếp với chủ nhà để đi xem, mà không phải liên hệ với hàng chục môi giới hay để lộ số điện thoại cho các cuộc gọi làm phiền."*

### Chủ nhà:
> *"Khi tôi có căn hộ cần bán, tôi muốn một kênh chính thống của Chủ đầu tư để đăng tin, gặp đúng những người mua thực sự có nhu cầu và tự chủ quyết định giờ tiếp khách, không muốn qua các khâu trung gian phiền toái."*

### Ban quản trị / Chủ đầu tư:
> *"Tôi muốn kiểm soát chất lượng nguồn cung căn hộ chuyển nhượng, xác thực rõ ràng chủ sở hữu hợp pháp, đồng thời ứng dụng AI để tự động hóa tối đa quy trình tìm kiếm và đặt lịch, giúp tiết kiệm chi phí nhân sự mà vẫn đảm bảo trải nghiệm khách hàng cao cấp."*

## 1.3. Căn cứ thực tiễn & Khoảng trống trên thị trường

Hiện nay, các công cụ trên thị trường bất động sản thường hoạt động rời rạc:
1. **Trang web đăng tin truyền thống:** Đóng vai trò là bảng tin thụ động, nhiều tin ảo, không xác minh chính chủ và không có công cụ điều phối lịch hẹn.
2. **Chatbot thông thường:** Chỉ trả lời theo kịch bản có sẵn, không có khả năng hiểu ngữ cảnh phức tạp hoặc tra cứu dữ liệu thời gian thực.
3. **Ứng dụng đặt lịch chung chung:** Không gắn liền với quy trình kiểm chứng pháp lý bất động sản và không giải quyết được bài toán bảo vệ quyền riêng tư.

**BookingBot AI Agent tạo ra sự khác biệt bằng việc kết nối toàn bộ các mắt xích này thành một quy trình khép kín:**
> **Nhập nhu cầu tự nhiên → AI gợi ý căn hộ chuẩn xác → Đối soát chính chủ Sổ đỏ → Kết nối trực tiếp Chủ nhà → Tự động tính lịch rảnh → Tạm khóa căn chống trùng lịch → Xem nhà thực tế → Mở hồ sơ giao dịch.**

---

# §2. Tác động Dự kiến & Các Nguyên tắc Cốt lõi

## 2.1. Giả thuyết về tác động tích cực

Khi hệ thống Trợ lý AI vận hành đồng bộ, sản phẩm kỳ vọng đạt được các kết quả:
- **Rút ngắn đáng kể thời gian tìm nhà:** Người mua không cần tự lọc hàng trăm tin đăng mà có ngay danh sách căn sát nhất với nhu cầu chỉ sau vài lượt trò chuyện.
- **Loại bỏ môi giới trung gian không mong muốn:** Giảm số lượng bên trung gian mà người mua phải tiếp xúc từ 5–10 người xuống còn 0 (chỉ làm việc trực tiếp với AI và Chủ nhà).
- **Bảo vệ tuyệt đối thông tin riêng tư:** Giảm triệt để tình trạng lộ số điện thoại, chấm dứt hoàn toàn các cuộc gọi làm phiền.
- **Tăng tỷ lệ kết nối thành công:** Đảm bảo 100% cuộc hẹn xem nhà đều diễn ra với chủ nhà thật và căn hộ thật đã kiểm duyệt.
- **Tối ưu hóa nguồn lực cho Chủ đầu tư:** Tự động hóa hơn 80% công việc tư vấn và sắp xếp lịch xem nhà ban đầu.

## 2.2. Bảng chỉ số đánh giá thành công (KPIs)

| Chỉ số đánh giá | Mục tiêu cần đạt | Ý nghĩa và Cách hiểu cụ thể |
|---|:---:|---|
| **Độ chính xác gợi ý 3 căn đầu tiên** | **Từ 85% trở lên** | Trong 100 khách tìm nhà, ít nhất 85 người thấy 3 căn AI đề xuất đúng với ngân sách, số phòng ngủ và khu vực mình cần. |
| **Tỷ lệ đặt lịch xem nhà thành công** | **Từ 80% trở lên** | Trong 100 yêu cầu đặt lịch gửi đi, ít nhất 80 lịch được chủ nhà bấm đồng ý và khách đến xem nhà thực tế. |
| **Tỷ lệ bị trùng lịch xem nhà** | **0% (Tuyệt đối không có)** | Nhờ hệ thống tự động tạm khóa căn ngay khi chủ nhà duyệt, không bao giờ có chuyện 2 khách cùng đến xem 1 căn tại cùng 1 giờ. |
| **Độ chính xác của lịch rảnh** | **Từ 95% trở lên** | Giờ rảnh của chủ nhà hiển thị trên hệ thống phải đúng với thực tế để khách không bị hẹn hụt. |
| **Thời gian AI trả lời câu hỏi** | **Dưới 5 giây** | Khách nhắn tin hỏi là AI trả lời ngay trong vòng 5 giây, không để khách phải đợi lâu. *(Lưu ý: Không phải "Thứ hai")* |
| **Cuộc gọi môi giới làm phiền** | **Giảm về 0 cuộc gọi** | Tuyệt đối không để lộ số điện thoại của người mua cho môi giới; chỉ hai bên gặp nhau xong mới mở liên lạc nếu đồng ý. |
| **Tỷ lệ phải nhờ nhân viên hỗ trợ** | **Dưới 15%** | AI tự động xử lý tốt 85% trường hợp; chỉ những ca khó (tranh chấp, đổi lịch phức tạp) mới cần người thật can thiệp. |

## 2.3. Tám nguyên tắc sản phẩm bất di bất dịch

1. **AI là trung tâm điều phối, con người là người quyết định cuối cùng:** AI chịu trách nhiệm hiểu ngôn ngữ, tra cứu thông tin và sắp xếp lịch; nhưng mọi hành động có tính cam kết (đồng ý lịch hẹn, đổi lịch, chốt mua bán) đều phải do con người phê duyệt trực tiếp (Human-in-the-loop).
2. **Kết nối trực tiếp giữa hai chủ thể:** Cắt giảm tối đa các khâu trung gian không cần thiết trong suốt hành trình từ Tìm kiếm → Gợi ý → Đặt lịch → Xem nhà.
3. **Bảo mật quyền riêng tư ngay từ khâu thiết kế (Privacy by Design):** Không bao giờ cung cấp số điện thoại hay thông tin cá nhân của người mua cho chủ nhà ngay từ đầu; chỉ mở thông tin liên hệ khi hai bên đã gặp mặt xem nhà và đồng thuận tiếp tục giao dịch.
4. **Cơ sở dữ liệu là chân lý duy nhất (Single Source of Truth):** AI chỉ được phép gợi ý các căn hộ có thật, đang hoạt động trong cơ sở dữ liệu đã được Ban quản trị duyệt; tuyệt đối nghiêm cấm AI tự bịa đặt căn hộ ảo (chống Hallucination).
5. **Bắt buộc xác thực danh tính Chủ sở hữu:** Mọi căn hộ đưa lên hệ thống đều phải trải qua bước đối soát thông tin Họ tên + Mã số Sổ đỏ với dữ liệu gốc của Chủ đầu tư và xác nhận qua mã OTP gửi về số điện thoại trên sổ.
6. **Chủ nhà toàn quyền duyệt lịch xem:** Không một lịch hẹn nào được xác nhận nếu chủ nhà chưa trực tiếp bấm "Đồng ý".
7. **Tạm khóa căn nguyên tử (Atomic Hold):** Khi chủ nhà đồng ý lịch xem, hệ thống lập tức khóa căn hộ trong đúng khung giờ đó bằng cơ chế khóa chặt chẽ trong cơ sở dữ liệu, đảm bảo không thể xảy ra trùng lịch.
8. **Cơ chế xử lý dự phòng an toàn:** Bất cứ khi nào AI không chắc chắn về câu trả lời hoặc gặp sự cố kỹ thuật, hệ thống phải lịch sự hỏi lại người dùng hoặc tự động chuyển vụ việc cho Nhân viên hỗ trợ của Chủ đầu tư.

---

# §3. Mô hình Tham khảo & Định vị Khác biệt

## 3.1. Các mô hình và tính năng tham khảo
Hệ thống chắt lọc và tích hợp những ưu điểm từ các nền tảng công nghệ hàng đầu:
- Giao diện trò chuyện tự nhiên (tương tự như ChatGPT / Claude).
- Bộ lọc tiêu chí bất động sản đa chiều (giá, diện tích, khoảng tầng, hướng ban công).
- Cơ chế gợi ý và xếp hạng theo điểm tương đồng sở thích.
- Thuật toán tự động tìm khung giờ giao nhau giữa hai thời gian biểu (tương tự Google Calendar / Calendly).
- Cơ chế con người phê duyệt trực tiếp (Human-in-the-loop).
- Cơ chế khóa tài nguyên chống tranh chấp đồng thời (Atomic concurrency locks).
- Phân quyền người dùng nghiêm ngặt và lưu vết nhật ký kiểm toán toàn diện.

## 3.2. Định vị khác biệt của sản phẩm

BookingBot AI Agent được định vị rõ ràng:
> **Không phải là một trang web đăng tin rao vặt bất động sản thụ động thông thường.**  
> **Cũng không phải là một chatbot hỏi đáp chung chung chỉ biết trả lời lý thuyết.**

Điểm khác biệt cốt lõi là:
> **Một Trợ lý AI có năng lực điều phối hành động: Tự động chuyển đổi nhu cầu bằng lời nói của người mua thành một cuộc hẹn xem nhà chính chủ, bảo vệ quyền riêng tư, loại bỏ hoàn toàn trùng lịch và kết nối trực tiếp vào quy trình giao dịch an toàn của Chủ đầu tư.**

---

# §4. Thiết kế Chức năng & Kiến trúc Nghiệp vụ Chi tiết

## 4.1. Luồng trải nghiệm cốt lõi

```text
Người mua nhắn nhu cầu
         ↓
Trợ lý AI phân tích & tìm kiếm căn hộ phù hợp
         ↓
Hệ thống đối soát căn hộ chính chủ đã kiểm duyệt
         ↓
Người mua chọn căn và bấm "Tôi muốn xem căn này"
         ↓
Tạo Hồ sơ kết nối (Mã giao dịch - Deal ID)
         ↓
Chủ nhà nhận thông báo yêu cầu xem nhà
         ↓
AI tính toán khung giờ rảnh chung giữa hai bên
         ↓
Chủ nhà bấm "Đồng ý"
         ↓
Hệ thống Tạm khóa căn trong khung giờ hẹn (Viewing Hold)
         ↓
Hai bên gặp mặt xem nhà thực tế
         ↓
Hỗ trợ thủ tục giao dịch chính thức cùng Chủ đầu tư
```

## 4.2. Sơ đồ phối hợp tổng thể giữa các bên

```text
NGƯỜI MUA (BUYER)
       │
       ▼
TRỢ LÝ AI (BOOKINGBOT)
       │
       ├── Bóc tách nhu cầu (ngân sách, số phòng, phân khu)
       ├── Tra cứu kho căn hộ đã kiểm duyệt
       ├── Chấm điểm phù hợp & giải thích lý do đề xuất
       │
       ▼
DANH SÁCH CĂN HỘ CHÍNH CHỦ
       │
       ▼
Người mua bấm: "Tôi muốn đặt lịch xem căn này"
       │
       ▼
KHỞI TẠO MÃ GIAO DỊCH (DEAL ID)
       │
       ▼
CHỦ NHÀ (OWNER) nhận thông báo có khách muốn xem
       │
       ▼
AI TÍNH TOÁN & GỢI Ý CÁC MỐC GIỜ RẢNH CHUNG
       │
       ├── Tìm được khung giờ trùng khớp
       │       ↓
       │   Chủ nhà bấm "Đồng ý"
       │       ↓
       │   TẠM KHÓA CĂN CHỐNG TRÙNG LỊCH (VIEWING HOLD)
       │       ↓
       │   Gửi thông báo nhắc lịch trước 24h và 2h
       │
       └── Không tìm được giờ trùng / Chủ nhà bận
               ↓
           CHUYỂN CHO NHÂN VIÊN HỖ TRỢ (HUMAN OPERATOR)
               ↓
           Đề xuất khung giờ khác hoặc giới thiệu căn tương tự
```

## 4.3. Phân định: Tự động hóa / Hỗ trợ / Con người trực tiếp xử lý

| Hạng mục công việc | Phương thức xử lý | Quy tắc và Ranh giới kiểm soát |
|---|:---:|---|
| **Hiểu nhu cầu người mua** | Tự động hoàn toàn | AI bóc tách ngân sách, vị trí, tiện ích từ ngôn ngữ tự nhiên. |
| **Tìm kiếm căn hộ** | Tự động hoàn toàn | Tra cứu qua công cụ an toàn, chỉ đọc dữ liệu từ kho căn đã duyệt. |
| **Xếp hạng & Đề xuất căn** | Tự động hoàn toàn | Lọc cứng theo tiêu chí bắt buộc + chấm điểm mềm theo sở thích. |
| **Giải thích lý do gợi ý** | Tự động hoàn toàn | Chỉ giải thích dựa trên thông số có thật của căn hộ. |
| **Kiểm tra lịch rảnh** | Tự động hoàn toàn | Chỉ đọc dữ liệu lịch rảnh, không tự ý thay đổi lịch của người dùng. |
| **Tạo yêu cầu đặt lịch** | Tự động theo lệnh | Kiểm tra tính khả dụng của căn trước khi tạo yêu cầu. |
| **Tính toán khung giờ chung** | Tự động hoàn toàn | Tìm các khoảng thời gian giao nhau giữa hai bên (mỗi mốc 30 phút). |
| **Chủ nhà xác nhận lịch** | **Bắt buộc Con người** | Chỉ Chủ nhà mới có quyền bấm Đồng ý hoặc Từ chối lịch hẹn. |
| **Tạm khóa căn chống trùng** | Tự động nguyên tử | Hệ thống tự động kích hoạt khóa trên cơ sở dữ liệu ngay khi chủ nhà duyệt. |
| **Chủ nhà không phản hồi** | **Nhân viên hỗ trợ can thiệp** | Nếu sau 2 giờ chủ nhà không trả lời, hệ thống thông báo cho nhân viên hỗ trợ. |
| **Không tìm được giờ rảnh chung** | **Nhân viên hỗ trợ hỗ trợ** | AI đề xuất các khung giờ lân cận; nếu khách không ưng, nhân viên sẽ liên hệ. |
| **Kiểm duyệt Sổ đỏ & Tin đăng** | **Bắt buộc Con người** | Ban quản trị Chủ đầu tư kiểm tra hồ sơ trước khi mở bán căn hộ. |
| **Nhắc lịch hẹn trước giờ xem** | Tự động hoàn toàn | Tự động gửi thông báo nhắc nhở trước 24 giờ và trước 2 giờ. |
| **Mở phòng chat trực tiếp** | Tự động theo quy tắc | Chỉ mở kênh nhắn tin sau khi buổi xem nhà được xác nhận thành công. |
| **Đàm phán và bớt giá** | **Người mua ↔ Chủ nhà** | AI tuyệt đối không tham gia mặc cả hay thương lượng giá thay cho các bên. |
| **Xác nhận giao dịch mua bán** | **Văn phòng Chủ đầu tư** | Mọi thủ tục đặt cọc và hợp đồng đều do bộ phận nghiệp vụ của Chủ đầu tư đảm trách. |

## 4.4. Hành trình của Người mua (Buyer Journey)

1. **Khám phá tự nhiên:** Khách truy cập trang web, có thể trò chuyện tìm nhà ngay lập tức mà không cần tạo tài khoản trước (chế độ Khách vãng lai - Guest Chat).
2. **Nêu nhu cầu:** Nhắn câu nói thông thường (Ví dụ: *"Anh cần tìm căn 2 ngủ bên Ocean Park, ban công Đông Nam thoáng mát, tài chính tầm 4 tỷ rưỡi"*).
3. **Nhận đề xuất trực quan:** AI phân tích và trả về các Thẻ căn hộ tương tác (Interactive Rich Cards) với đầy đủ ảnh, giá, diện tích và lời giải thích ngắn gọn vì sao căn đó hợp ý khách.
4. **Xem chi tiết:** Khách bấm xem sâu thông số từng căn, tiện ích xung quanh, hình ảnh nội thất.
5. **Đặt lịch xem:** Bấm nút *"Tôi muốn xem căn này"* → Chọn các khung giờ mình rảnh trong tuần.
6. **Xác thực số điện thoại:** Khi chốt yêu cầu đặt lịch, khách nhập số điện thoại và mã OTP để hoàn tất đăng ký và lưu hồ sơ.
7. **Theo dõi tiến độ:** Nhận thông báo khi chủ nhà duyệt lịch, nhận mã thẻ xem nhà điện tử và thông báo nhắc giờ khi đến hẹn.

## 4.5. Hành trình của Chủ nhà (Owner Journey)

1. **Đăng nhập:** Đăng nhập qua số điện thoại và mã OTP.
2. **Tạo tin đăng bán căn hộ:** Nhập các thông tin cơ bản của căn hộ (mã căn, tòa nhà, phân khu, diện tích, giá bán mong muốn, tình trạng nội thất).
3. **Xác thực chính chủ qua Sổ đỏ:** Tải ảnh giấy tờ và nhập Họ tên + Mã số Sổ đỏ. Hệ thống tự động đối soát với cơ sở dữ liệu của Chủ đầu tư và gửi mã OTP về số điện thoại đăng ký trên sổ đỏ để chứng minh quyền sở hữu (nhập sai OTP quá 5 lần thì hồ sơ sổ đỏ bị tạm khóa).
4. **Cài đặt khung giờ rảnh:** Chủ nhà chủ động tích chọn các khung giờ có thể đón khách xem nhà trong tuần (Ví dụ: Chiều Thứ Bảy từ 14h đến 17h, Sáng Chủ Nhật từ 9h đến 11h).
5. **Tiếp nhận & Duyệt lịch:** Khi có khách đặt lịch, chủ nhà nhận thông báo kèm thông tin tóm tắt về nhu cầu của khách → Chủ nhà chỉ cần bấm **"Đồng ý"** hoặc **"Từ chối"**.
6. **Đón tiếp khách xem nhà:** Đúng giờ hẹn, chủ nhà đón khách đến xem thực tế căn hộ của mình.

## 4.6. Cơ chế Bảo vệ Quyền riêng tư Đa tầng (Progressive Disclosure)

Nhằm chấm dứt tình trạng lộ dữ liệu cá nhân, hệ thống áp dụng cơ chế phân tầng thông tin nghiêm ngặt:

```text
[CẤP ĐỘ 1: KẾT NỐI ẨN DANH]
Khách mua và Chủ nhà chưa thấy số điện thoại của nhau.
Chủ nhà chỉ nhìn thấy: Mã người mua (Ví dụ: KH-02612), nhu cầu tìm kiếm và khung giờ mong muốn.
                    ↓
[CẤP ĐỘ 2: HẸN XEM NHÀ THÀNH CÔNG]
Chủ nhà bấm duyệt → Cấp Mã xem nhà (Viewing Pass) cùng thời gian và địa điểm căn hộ.
Vẫn giữ ẩn số điện thoại cá nhân; mọi liên lạc diễn ra qua thông báo ứng dụng.
                    ↓
[CẤP ĐỘ 3: KẾT NỐI SAU BUỔI XEM]
Sau khi buổi xem nhà kết thúc, nếu cả hai bên cùng đánh giá hài lòng và muốn trao đổi thêm,
hệ thống sẽ mở phòng chat trực tiếp bên trong ứng dụng.
                    ↓
[CẤP ĐỘ 4: CHUYỂN GIAO DỊCH CHÍNH THỨC]
Khi hai bên quyết định mua bán, thông tin được chuyển trực tiếp tới Văn phòng thủ tục của Chủ đầu tư
để hỗ trợ hợp đồng và sang tên chính chủ theo quy định pháp luật.
```

## 4.8. Cơ chế Khớp Lịch Xem Nhà Tự động (Scheduling Engine)

Hệ thống sử dụng thuật toán tìm giao điểm thời gian (Intersection) giữa hai thời gian biểu:

- **Thời gian rảnh của Người mua:** Chiều Thứ Bảy từ `14h00 đến 17h00`.
- **Thời gian rảnh của Chủ nhà:** Chiều Thứ Bảy từ `14h30 đến 16h00`.
- **Thuật toán tính toán:** Khung giờ giao nhau là `14h30 – 16h00`.
- **Hệ thống đề xuất các mốc giờ 30 phút:** `14h30`, `15h00`, `15h30`.
- **Người mua chọn:** `15h00`.
- **Chủ nhà nhận thông báo và bấm:** **"Đồng ý"**.
- → Hệ thống chuyển trạng thái thành **"Lịch hẹn đã xác nhận"** và tự động kích hoạt Tạm khóa căn hộ.

### Xử lý khi có sự cố về lịch:
- Nếu Chủ nhà không phản hồi trong vòng **2 giờ**, hệ thống gửi cảnh báo nhắc nhở; nếu quá hạn, chuyển vụ việc sang Nhân viên hỗ trợ để gọi điện xác nhận.
- Nếu không có khung giờ nào trùng nhau, AI tự động gợi ý các khung giờ gần nhất của chủ nhà hoặc đề xuất căn hộ tương tự cùng phân khu.

## 4.9. Mã Định danh Hồ sơ Kết nối (Deal ID)

Mỗi khi một Người mua yêu cầu xem một Căn hộ của một Chủ nhà cụ thể, hệ thống tự động sinh một mã quản lý duy nhất:
> **Mã giao dịch (Deal ID):** Ví dụ `VH-2026-00128`

### Vòng đời trạng thái của một hồ sơ kết nối:
```text
ĐÃ KHỚP NHU CẦU (Matched)
          ↓
ĐÃ GỬI YÊU CẦU XEM NHÀ (Viewing Requested)
          ↓
CHỦ NHÀ ĐÃ ĐỒNG Ý LỊCH (Viewing Confirmed)
          ↓
ĐÃ HOÀN TẤT BUỔI XEM (Viewing Completed)
          ↓
KHÁCH THIỆN CHÍ QUAN TÂM (Interested)
          ↓
HAI BÊN ĐANG TRAO ĐỔI (In Discussion)
          ↓
CHUYỂN VĂN PHÒNG CHỦ ĐẦU TƯ HỖ TRỢ THỦ TỤC (Transaction Escorted)
          ↓
GIAO DỊCH THÀNH CÔNG / ĐÓNG HỒ SƠ (Closed)
```

## 4.10. Cơ chế Gắn kết & Hạn chế Giao dịch Ngoài Hệ thống

Hệ thống không kỳ vọng có thể cấm đoán tuyệt đối các giao dịch bên ngoài bằng biện pháp kỹ thuật thuần túy. Thay vào đó, nền tảng tạo ra các **giá trị bảo chứng vượt trội** khiến các bên tự nguyện gắn bó với hệ sinh thái của Chủ đầu tư:
1. **Tính xác thực tuyệt đối:** Chỉ có căn hộ trên nền tảng mới được Chủ đầu tư chứng nhận chính chủ qua Sổ đỏ.
2. **Loại trừ rủi ro trùng lịch:** Cơ chế tạm khóa độc quyền đảm bảo người mua đến nơi chắc chắn được xem nhà.
3. **Mã xem nhà và lịch sử minh bạch:** Mọi yêu cầu đều được ghi nhận bằng Mã giao dịch để làm căn cứ pháp lý.
4. **Hỗ trợ thủ tục chuyển nhượng miễn phí:** Chủ đầu tư hỗ trợ kiểm tra quy hoạch, soạn thảo văn bản và hướng dẫn thủ tục sang tên nhanh chóng, an toàn.

## 4.11. Vòng đời Trạng thái của Căn hộ (Property Lifecycle)

```text
BẢN NHÁP (Draft)
       ↓
CHỜ BAN QUẢN TRỊ DUYỆT (Pending Moderation)
       ↓
ĐÃ DUYỆT & ĐANG MỞ BÁN (Active Listing)
       ↓
ĐANG TẠM KHÓA GIỜ XEM (Viewing Held)
       ↓
SẴN SÀNG NHẬN KHÁCH TIẾP (Available)
       ↓
ĐÃ BÁN THÀNH CÔNG (Sold / Archived)
```

## 4.12. Vòng đời của Lịch hẹn Xem nhà (Booking Lifecycle)

```text
CHỜ CHỦ NHÀ PHÊ DUYỆT (Pending Approval)
       ↓
CHỦ NHÀ ĐÃ DUYỆT & TẠM KHÓA CĂN (Confirmed & Held)
       ↓
BUỔI XEM NHÀ HOÀN TẤT (Completed)

* Các nhánh chuyển trạng thái khác:
- CHỜ DUYỆT → CHỦ NHÀ TỪ CHỐI (Rejected)
- ĐÃ DUYỆT → NGƯỜI DÙNG HỦY LỊCH (Cancelled)
- ĐÃ DUYỆT → YÊU CẦU ĐỔI GIỜ HẸN (Reschedule Requested)
```

## 4.13. Cơ chế Tạm khóa Căn giữ chỗ Xem nhà (Viewing Hold)

Trong phiên bản thử nghiệm:
> **TẠM KHÓA CĂN (Viewing Hold) là việc hệ thống tự động khóa căn hộ trong đúng khung giờ hẹn xem nhà để ngăn chặn bất kỳ ai khác đặt trùng lịch. Đây HOÀN TOÀN KHÔNG PHẢI là việc đặt cọc giữ chỗ mua bán căn hộ.**

### Sáu quy tắc kỹ thuật vận hành cơ chế tạm khóa:
1. **Chỉ kích hoạt sau khi Chủ nhà bấm "Đồng ý":** Tuyệt đối không tự ý khóa căn khi yêu cầu mới ở trạng thái chờ duyệt.
2. **Khóa đúng người, đúng việc, đúng thời điểm:** Khung giờ bị khóa gắn liền với đúng Mã giao dịch, đúng Người mua và đúng khoảng thời gian đã hẹn.
3. **Không khóa ngoài giờ hẹn:** Sau khi hết khung giờ xem nhà, căn hộ tự động mở lại trạng thái sẵn sàng để đón các lượt khách tiếp theo.
4. **Tự động mở khóa khi hủy lịch:** Nếu người mua bấm hủy hoặc hai bên thống nhất đổi giờ, khóa cũ lập tức được giải phóng.
5. **Khóa nguyên tử đồng bộ (Atomic Concurrency Locking):** Tận dụng ràng buộc loại trừ độc quyền trên cơ sở dữ liệu PostgreSQL (Exclusion Constraint), đảm bảo dù có nhiều người cùng bấm đặt lịch tại một tích tắc thì hệ thống cũng chỉ cấp phát duy nhất một lịch hẹn hợp lệ.
6. **Tuyệt đối không để xảy ra trùng lịch (0% Double-Booking).**

## 4.14. Quy định Sau Buổi Xem Nhà & Giới hạn Trách nhiệm của AI

Sau khi hoàn tất buổi xem nhà:
- Hai bên có thể gửi phản hồi đánh giá chất lượng buổi gặp.
- Nếu muốn tiếp tục, hệ thống mở kênh trao đổi tin nhắn trực tiếp giữa hai bên.

### Giới hạn an toàn tuyệt đối của Trợ lý AI:
- AI không tham gia đàm phán, mặc cả giá bán thay cho bất kỳ bên nào.
- AI không tự ý đưa ra kết luận pháp lý mang tính cam kết.
- AI không tiếp nhận tiền, không nhận cọc và không xác nhận việc mua bán thành công.
- Mọi khâu liên quan đến hợp đồng và tiền bạc đều do Nhân viên hỗ trợ của Chủ đầu tư thực hiện trực tiếp cùng khách hàng.

## 4.15. Danh mục Các Màn hình Giao diện

### Cổng Khách mua (Buyer Portal):
1. Khung trò chuyện thông minh với Trợ lý AI (hỗ trợ hiển thị Thẻ căn hộ tương tác dạng vuốt/lưới).
2. Trang xem chi tiết căn hộ (thông số, tiện ích, vị trí, ảnh chụp thực tế).
3. Bảng chọn khung giờ rảnh và gửi yêu cầu đặt lịch xem nhà.
4. Trang quản lý lịch hẹn của tôi (xem mã thẻ xem nhà, hủy lịch, yêu cầu đổi lịch).
5. Kênh nhắn tin trực tiếp với Chủ nhà sau khi xem nhà thành công.
6. Trung tâm thông báo nhắc lịch hẹn và cập nhật trạng thái hồ sơ.

### Cổng Chủ nhà (Owner Portal):
1. Bảng tổng quan hoạt động (số lượt xem tin, số yêu cầu hẹn xem mới).
2. Danh sách căn hộ của tôi và trạng thái kiểm duyệt.
3. Màn hình đăng tin căn hộ mới và tải ảnh giấy tờ.
4. Màn hình xác thực Sổ đỏ chính chủ qua mã OTP điện thoại.
5. Lịch biểu quản lý các khung giờ rảnh trong tuần.
6. Hàng đợi duyệt yêu cầu xem nhà (bấm Đồng ý hoặc Từ chối kèm lý do).
7. Danh sách các buổi xem nhà sắp diễn ra và lịch sử các lượt xem đã hoàn tất.

### Cổng Ban quản trị & Vận hành (Operator Console):
1. Bảng điều hành tổng hợp chỉ số toàn hệ thống (số tin đăng, số lịch hẹn, tỷ lệ thành công).
2. Hàng đợi kiểm duyệt thông tin căn hộ trước khi hiển thị công khai.
3. Hàng đợi đối soát và xác minh hồ sơ Sổ đỏ chính chủ.
4. Bảng giám sát các lịch hẹn xem nhà và tiến độ các hồ sơ giao dịch.
5. Danh sách các trường hợp ngoại lệ cần nhân viên hỗ trợ can thiệp (chủ nhà quá hạn phản hồi, trùng lịch, khiếu nại).
6. Nhật ký kiểm toán hệ thống (ghi lại toàn bộ lịch sử thao tác để phục vụ tra cứu).

## 4.16. Cấu trúc Mô hình Dữ liệu Cốt lõi (Data Model)

Các bảng dữ liệu chính trong cơ sở dữ liệu:
- `User`: Bảng thông tin tài khoản người dùng chung.
- `BuyerProfile`: Hồ sơ khách mua (lưu trữ sở thích, ngân sách, phân khu quan tâm).
- `OwnerProfile`: Hồ sơ chủ nhà (trạng thái xác minh, thông tin liên hệ).
- `Project`: Danh mục dự án đô thị (Vinhomes Ocean Park, Smart City...).
- `Building`: Danh mục tòa nhà trong dự án.
- `Property`: Thông tin chi tiết căn hộ (mã căn, tầng, diện tích, giá bán, hướng ban công, trạng thái).
- `PropertyMedia`: Kho lưu trữ hình ảnh và video thực tế của căn hộ.
- `PropertyAvailability`: Các khung giờ rảnh mà chủ nhà cài đặt để tiếp khách.
- `Deal`: Hồ sơ kết nối giữa Người mua, Chủ nhà và Căn hộ cụ thể.
- `Booking`: Lịch hẹn xem nhà (ngày giờ hẹn, trạng thái duyệt).
- `PropertyHold`: Bản ghi tạm khóa khung giờ căn hộ để chống trùng lịch.
- `PurchaseRequest`: Yêu cầu xúc tiến giao dịch mua bán sau khi xem nhà.
- `Chat`: Phòng trao đổi tin nhắn trực tiếp giữa hai bên.
- `Message`: Nội dung tin nhắn trao đổi.
- `Notification`: Thông báo gửi tới người dùng.
- `AIConversation`: Phiên trò chuyện giữa Người mua và Trợ lý AI.
- `AIMessage`: Lịch sử tin nhắn trong phiên trò chuyện cùng AI.
- `Recommendation`: Nhật ký các căn hộ đã được AI gợi ý cho khách.
- `AuditLog`: Nhật ký kiểm toán ghi lại mọi thay đổi dữ liệu quan trọng.

## 4.17. Cơ chế Xác thực & Phân quyền Người dùng

| Vai trò người dùng | Phương thức xác thực danh tính |
|---|---|
| **Người mua (Buyer)** | Số điện thoại cá nhân + Mã xác thực một lần (OTP). |
| **Chủ nhà (Owner)** | Số điện thoại / Email + Mã xác thực OTP + Đối soát thông tin Sổ đỏ. |
| **Ban quản trị (Operator)** | Email nội bộ + Mật khẩu mã hóa bảo mật cao + Xác thực hai bước (2FA). |

### Các quy tắc phân quyền bắt buộc:
- Người dùng chỉ được truy cập vào đúng dữ liệu và chức năng thuộc vai trò của mình.
- Chủ nhà không được xem số điện thoại hay thông tin cá nhân của Người mua khi chưa hoàn tất buổi xem nhà.
- Người mua không được xem thông tin riêng tư của Chủ nhà nếu chưa được cấp phép.
- Phòng chat trực tiếp chỉ được mở khi buổi xem nhà được xác nhận hợp lệ.
- Toàn bộ thao tác can thiệp dữ liệu đều được ghi lại trong nhật ký kiểm toán.

## 4.18. Bộ Công cụ Dành cho Trợ lý AI (Agent Tools)

Để đảm bảo an toàn tuyệt đối, Trợ lý AI chỉ được phép tương tác với hệ thống thông qua bộ công cụ có kiểm duyệt chặt chẽ, chia làm 2 nhóm:

### 1. Nhóm công cụ tra cứu thông tin (Chỉ đọc - Read Tools):
- `search_properties`: Tra cứu danh sách căn hộ theo các tiêu chí (dự án, khoảng giá, số phòng ngủ, hướng).
- `get_property_detail`: Xem thông tin chi tiết, hình ảnh và tiện ích của một căn hộ cụ thể.
- `get_owner_status`: Kiểm tra trạng thái xác thực chính chủ của chủ nhà.
- `check_property_availability`: Kiểm tra lịch rảnh của căn hộ.
- `check_owner_availability`: Kiểm tra lịch rảnh của chủ nhà.
- `get_deal_status`: Tra cứu tiến độ xử lý của hồ sơ kết nối.

### 2. Nhóm công cụ thực hiện thao tác (Ghi dữ liệu - Action Tools):
- `create_viewing_request`: Tạo yêu cầu hẹn xem nhà mới theo khung giờ khách chọn.
- `confirm_viewing`: Xác nhận lịch xem nhà (khi có sự đồng ý của chủ nhà).
- `cancel_viewing`: Hủy lịch hẹn xem nhà.
- `reschedule_viewing`: Đổi lịch hẹn sang khung giờ khác.
- `create_property_hold`: Kích hoạt tạm khóa khung giờ xem căn hộ để chống trùng.
- `release_property_hold`: Mở khóa căn hộ khi buổi xem hoàn tất hoặc bị hủy.
- `open_chat`: Kích hoạt mở phòng nhắn tin trực tiếp giữa hai bên.
- `send_notification`: Gửi thông báo đến ứng dụng của người dùng.
- `create_human_escalation`: Chuyển vụ việc phát sinh cho Nhân viên hỗ trợ xử lý thủ công.

### Quy định an toàn bắt buộc khi gọi công cụ:
- Trí tuệ nhân tạo (LLM) tuyệt đối không được truy cập trực tiếp vào cơ sở dữ liệu.
- Mọi công cụ đều phải tự kiểm tra quyền hạn của người dùng trước khi thực thi.
- Mọi thao tác ghi dữ liệu đều phải kiểm tra tính hợp lệ của trạng thái hiện tại.
- AI không bao giờ được tự ý bỏ qua bước phê duyệt bắt buộc của Chủ nhà.
- AI không bao giờ được phép đọc hoặc chia sẻ thông tin cá nhân ngoài phạm vi cho phép.

## 4.19. Hệ thống Thông báo & Nhắc nhở Tự động

### Các sự kiện kích hoạt thông báo tức thời:
- Chủ nhà có yêu cầu hẹn xem nhà mới từ khách.
- Chủ nhà bấm Đồng ý hoặc Từ chối lịch hẹn.
- Lịch hẹn xem nhà được xác nhận thành công.
- Khung giờ xem nhà được tạm khóa thành công.
- Tin đăng căn hộ được Ban quản trị phê duyệt hoặc từ chối.

### Lịch nhắc nhở tự động trước buổi xem:
- Nhắc lần 1: Trước giờ hẹn **24 giờ**.
- Nhắc lần 2: Trước giờ hẹn **2 giờ**.

---

# §5. Bảng Phân loại & Xử lý Các Tình huống Ngoại lệ

| Tình huống ngoại lệ | Ví dụ thực tế phát sinh | Cách hệ thống xử lý mong đợi |
|---|---|---|
| **Thiếu thông tin nhu cầu** | Khách chỉ nhắn: *"Tìm cho anh căn đẹp"* | AI lịch sự hỏi thêm về tầm tiền, dự án hoặc số phòng ngủ mong muốn. |
| **Không có căn hộ phù hợp** | Tìm căn 3 phòng ngủ giá dưới 2 tỷ ở Ocean Park | AI giải thích rõ không có căn ở mức giá này và gợi ý phương án gần nhất (ví dụ: căn 2 phòng ngủ hoặc mức ngân sách phù hợp hơn). |
| **Chủ nhà chưa có lịch rảnh** | Căn hộ ưng ý nhưng chủ nhà chưa cài đặt giờ đón khách | AI gợi ý các căn hộ tương tự có sẵn lịch xem ngay, đồng thời gửi thông báo nhắc chủ nhà cập nhật lịch. |
| **Không có giờ rảnh trùng nhau** | Khách chỉ rảnh sáng Thứ Bảy, Chủ nhà chỉ rảnh chiều Chủ Nhật | AI đề xuất các khung giờ liền kề; nếu không thể thu xếp, chuyển cho Nhân viên hỗ trợ liên hệ hỗ trợ. |
| **Chủ nhà từ chối lịch hẹn** | Chủ nhà bận việc gia đình đột xuất nên bấm từ chối | AI thông báo rõ cho người mua và chủ động gợi ý khung giờ khác hoặc căn hộ tương tự cùng phân khu. |
| **Nhiều khách cùng đặt một giờ** | Hai khách cùng bấm đặt lịch xem căn hộ vào lúc 15h00 | Cơ chế khóa nguyên tử đảm bảo chỉ yêu cầu đầu tiên được duyệt; khách còn lại được gợi ý khung giờ lân cận ngay tức thì. |
| **Căn hộ vừa bán xong** | Căn hộ vừa được xác nhận bán xong trong khi khách đang xem | Hệ thống tự động ẩn căn khỏi danh mục tìm kiếm và AI thông báo cập nhật cho khách. |
| **Hành vi vượt thẩm quyền** | Khách yêu cầu AI cung cấp số điện thoại riêng của chủ nhà | AI lịch sự từ chối theo chính sách bảo mật và giải thích thông tin sẽ được chia sẻ sau buổi xem nhà. |
| **Chủ nhà chưa xác thực Sổ đỏ** | Căn hộ mới tạo bản nháp, chưa hoàn tất đối soát giấy tờ | Hệ thống nghiêm cấm không cho phép đặt lịch xem đối với các căn chưa được kiểm duyệt. |
| **Sự cố hệ thống kỹ thuật** | Mất kết nối mạng, lỗi máy chủ hoặc dịch vụ AI gián đoạn | Hệ thống tự động dừng mọi thao tác ghi dữ liệu, bảo toàn nội dung trao đổi của khách và chuyển vụ việc sang Nhân viên hỗ trợ. |
| **Xung đột hồ sơ giao dịch** | Khách yêu cầu đặt lịch cho một hồ sơ đã bị hủy trước đó | Hệ thống từ chối thao tác và hướng dẫn khách bắt đầu một yêu cầu mới. |

---

# §6. Bốn Kịch bản Trải nghiệm Người dùng Điển hình

## 6.1. Kịch bản Thuận lợi Chuẩn (Happy Path)

```text
Khách mua trò chuyện cùng Trợ lý AI
       ↓
AI thấu hiểu nhu cầu và tìm kiếm căn hộ
       ↓
AI gợi ý danh sách căn hộ phù hợp kèm giải thích lý do
       ↓
Khách chọn căn ưng ý và gửi yêu cầu đặt lịch xem
       ↓
Khởi tạo Mã giao dịch (Deal ID)
       ↓
Chủ nhà nhận thông báo yêu cầu xem nhà
       ↓
AI tính toán khớp khung giờ rảnh chung
       ↓
Chủ nhà bấm "Đồng ý"
       ↓
Hệ thống Tạm khóa căn trong đúng giờ hẹn (chống trùng lịch)
       ↓
Khách đến xem nhà thực tế đúng hẹn
       ↓
Hai bên trao đổi trực tiếp và tiến tới giao dịch cùng Chủ đầu tư
```

## 6.2. Kịch bản Điều chỉnh Nhu cầu (Correction Path)

Khách mua nhắn: *"Anh muốn nâng ngân sách lên 6 tỷ và ưu tiên căn nhìn thẳng ra hồ lớn."*

```text
Hệ thống tải lại hồ sơ nhu cầu hiện tại của khách
       ↓
Cập nhật tiêu chí mới (ngân sách 6 tỷ, hướng nhìn ra hồ)
       ↓
Chạy lại thuật toán tìm kiếm và chấm điểm
       ↓
Gợi ý danh sách các căn hộ mới phù hợp ngay trong khung chat
```

## 6.3. Kịch bản Phát sinh Thay đổi về Lịch hẹn (Exception Path)

Khách chọn 15h00 nhưng Chủ nhà vừa phát sinh việc bận đột xuất vào giờ đó:

```text
Hệ thống kiểm tra tính khả dụng của khung giờ
       ↓
Phát hiện khung giờ không còn phù hợp
       ↓
AI lịch sự thông báo lý do cho khách mua
       ↓
Gợi ý các khung giờ trống liền kề gần nhất (15h30 hoặc 16h00)
       ↓
Khách mua chọn khung giờ mới
       ↓
Chủ nhà bấm "Đồng ý"
       ↓
Nếu vẫn không thống nhất được: Tự động chuyển Nhân viên hỗ trợ gọi điện hỗ trợ
```

## 6.4. Kịch bản Dự phòng khi Gặp Sự cố Kỹ thuật (Fallback Path)

Khi xảy ra lỗi đường truyền, lỗi cơ sở dữ liệu hoặc dịch vụ AI gặp sự cố:

```text
Phát hiện lỗi kỹ thuật bất thường
       ↓
Dừng ngay lập tức các thao tác ghi dữ liệu để bảo đảm an toàn
       ↓
Lưu giữ nguyên vẹn nội dung và trạng thái phiên làm việc của khách
       ↓
Tạo cảnh báo ngoại lệ gửi về bộ phận kỹ thuật và vận hành
       ↓
Nhân viên hỗ trợ tiếp nhận và liên hệ trực tiếp hỗ trợ khách
       ↓
Khách hàng nhận được thông báo trạng thái rõ ràng, minh bạch
```

---

# §7. Kế hoạch Kiểm thử & Tiêu chuẩn Nghiệm thu Cốt lõi

## 7.1. Các khu vực kiểm thử chức năng theo từng đối tượng

### 1. Dành cho Người mua:
- Đăng nhập thuận tiện bằng số điện thoại và mã OTP.
- Khả năng trò chuyện tự nhiên và bóc tách tiêu chí chính xác của AI.
- Độ chính xác của danh sách căn hộ gợi ý và nội dung giải thích lý do đề xuất.
- Xem chi tiết thông số, tiện ích và hình ảnh thực tế của căn hộ.
- Gửi yêu cầu đặt lịch hẹn xem nhà theo khung giờ rảnh.
- Quản lý, xem mã thẻ xem nhà, thực hiện đổi giờ hoặc hủy lịch hẹn.

### 2. Dành cho Chủ nhà:
- Quy trình đăng ký tài khoản và đăng tin bán căn hộ mới.
- Quy trình đối soát thông tin Sổ đỏ chính chủ qua mã OTP.
- Cài đặt và cập nhật các khung giờ rảnh trong tuần.
- Nhận thông báo và thao tác phê duyệt hoặc từ chối lịch xem nhà.
- Quản lý danh sách lịch hẹn và theo dõi tiến độ hồ sơ giao dịch.

### 3. Dành cho Ban quản trị & Vận hành:
- Bảng điều hành kiểm duyệt tin đăng căn hộ trước khi hiển thị.
- Bảng đối soát và xác minh hồ sơ Sổ đỏ chính chủ.
- Giám sát toàn bộ các lịch hẹn xem nhà và các hồ sơ giao dịch đang diễn ra.
- Tiếp nhận và xử lý kịp thời các trường hợp ngoại lệ trong hàng đợi.

## 7.2. Bộ kịch bản chuẩn vàng đánh giá Trí tuệ Nhân tạo (AI Golden Evaluation Set)

Hệ thống được kiểm thử tự động trên bộ dữ liệu chuẩn vàng bao gồm **ít nhất 20 kịch bản thực tế khắt khe**:
1. Bóc tách chính xác các tiêu chí trong câu nói thông thường của người dùng.
2. Tuân thủ nghiêm ngặt các điều kiện lọc cứng (đúng tầm giá, đúng số phòng ngủ, đúng dự án).
3. Chấm điểm chính xác mức độ ưu tiên theo sở thích mềm (hướng ban công, khoảng tầng, view).
4. Xếp hạng căn hộ hợp lý và giải thích rõ ràng, trung thực vì sao đề xuất căn đó.
5. Lựa chọn đúng công cụ kỹ thuật tương ứng với ý định của người dùng.
6. Truyền đúng tham số đầu vào cho các công cụ.
7. Tuân thủ phân quyền và bảo vệ nghiêm ngặt dữ liệu riêng tư.
8. Tính toán chính xác giao điểm các khung giờ rảnh giữa hai bên.
9. Cập nhật đúng trạng thái của hồ sơ giao dịch qua từng bước.
10. **Tuyệt đối không bịa đặt căn hộ ảo khi trong kho không có căn phù hợp (Zero Hallucination).**
11. Xử lý khéo léo các tình huống từ chối, đổi lịch hoặc lỗi hệ thống.
12. Tự động chuyển giao việc cho con người đúng thời điểm khi vượt quá thẩm quyền.

## 7.3. Mười Tiêu chuẩn Nghiệm thu Cốt lõi (Acceptance Criteria)

### AC-01: Tuyệt đối không sinh thông tin căn hộ ảo (Chống Hallucination)
- **Điều kiện:** Cơ sở dữ liệu không có căn hộ nào thỏa mãn hoàn toàn yêu cầu của khách.
- **Kết quả bắt buộc:** Trợ lý AI phải nói rõ sự thật là hiện chưa có căn phù hợp, tuyệt đối không được tự bịa ra thông tin hay thông số của căn hộ ảo.

### AC-02: Tạo mã kết nối giao dịch trực tiếp
- **Điều kiện:** Người mua chọn một căn hộ và gửi yêu cầu đặt lịch xem.
- **Kết quả bắt buộc:** Hệ thống tự động tạo một Mã giao dịch (Deal ID) duy nhất và gửi thông báo trực tiếp đến Chủ nhà của căn hộ đó.

### AC-03: Bảo vệ tuyệt đối thông tin cá nhân (Privacy)
- **Điều kiện:** Người mua chưa hoàn tất buổi xem nhà hoặc chưa xác nhận muốn tiếp tục giao dịch.
- **Kết quả bắt buộc:** Chủ nhà tuyệt đối không được nhìn thấy số điện thoại hay email cá nhân của Người mua.

### AC-04: Bắt buộc xác thực danh tính Chủ nhà
- **Điều kiện:** Căn hộ chưa hoàn thành bước đối soát Sổ đỏ chính chủ và chưa được Ban quản trị phê duyệt.
- **Kết quả bắt buộc:** Hệ thống không cho phép bất kỳ ai gửi yêu cầu đặt lịch xem đối với căn hộ này.

### AC-05: Bắt buộc có sự phê duyệt của Chủ nhà
- **Điều kiện:** Người mua gửi yêu cầu đặt lịch xem nhà.
- **Kết quả bắt buộc:** Trạng thái lịch hẹn không bao giờ được chuyển sang "Đã xác nhận" nếu Chủ nhà chưa trực tiếp bấm "Đồng ý".

### AC-06: Tự động tính toán giao điểm khung giờ rảnh
- **Điều kiện:** Người mua rảnh từ `14h00 – 17h00`, Chủ nhà rảnh từ `14h30 – 16h00`.
- **Kết quả bắt buộc:** AI phải tìm đúng khoảng thời gian giao nhau là `14h30 – 16h00` và đề xuất các mốc giờ 30 phút tương ứng.

### AC-07: Xử lý khi không có khung giờ trùng nhau
- **Điều kiện:** Lịch rảnh của Người mua và Chủ nhà hoàn toàn lệch nhau, không có điểm chung.
- **Kết quả bắt buộc:** AI phải giải thích rõ ràng và gợi ý các phương án giờ khác hoặc chuyển cho Nhân viên hỗ trợ can thiệp.

### AC-08: Tạm khóa căn nguyên tử, chống trùng lịch tuyệt đối (Atomic Hold)
- **Điều kiện:** Hai người mua cùng bấm đặt lịch vào đúng một căn hộ tại cùng một khung giờ.
- **Kết quả bắt buộc:** Cơ sở dữ liệu chỉ chấp nhận duy nhất một lịch hẹn được xác nhận và tạm khóa; người thứ hai lập tức nhận được thông báo khung giờ này đã có người giữ và được gợi ý khung giờ khác.

### AC-09: Quản lý xuyên suốt qua Mã giao dịch (Deal Tracking)
- **Điều kiện:** Người mua gửi yêu cầu xem nhà thành công.
- **Kết quả bắt buộc:** Mọi lịch sử trò chuyện, trạng thái lịch hẹn, nhật ký đổi giờ và kết quả buổi xem đều phải gắn liền với Mã giao dịch đã cấp.

### AC-10: Ranh giới an toàn, không can thiệp giao dịch tài chính
- **Điều kiện:** Bất kỳ tình huống nào trong quá trình vận hành.
- **Kết quả bắt buộc:** Trợ lý AI tuyệt đối không được tự ý xác nhận giao dịch mua bán, không nhận tiền, không nhận cọc và không tự ý thay đổi giá bán của căn hộ.

---

# §8. Phân công Trách nhiệm & Lộ trình Thực hiện 6 Giai đoạn

## 8.1. Ma trận phân công công việc chính

| Khối chuyên trách | Trách nhiệm cốt lõi | Thành viên phụ trách |
|---|---|---|
| **Quản lý Sản phẩm (Product / PM)** | Xác định bài toán thực tế, quy tắc nghiệp vụ, tiêu chuẩn nghiệm thu và giám sát chất lượng sản phẩm. | Hoàng Anh Tài (Trưởng nhóm) |
| **Trí tuệ Nhân tạo (AI / Agent)** | Xây dựng kịch bản điều phối, thiết kế đồ thị luồng xử lý (LangGraph), định nghĩa bộ công cụ an toàn và đánh giá AI. | Ngọ Doãn Ngọc |
| **Máy chủ & Nghiệp vụ (Backend)** | Xây dựng các cổng kết nối API, bộ máy xử lý lịch hẹn, cơ chế tạm khóa chống trùng, xác thực bảo mật và các tác vụ nền. | Ngọ Doãn Ngọc |
| **Giao diện Người dùng (Frontend)** | Phát triển website tương thích đa thiết bị, giao diện khung chat trò chuyện tương tác, thẻ căn hộ và bảng điều khiển cho từng vai trò. | Ngọ Doãn Ngọc |
| **Dữ liệu & Hệ thống (Data & Systems)** | Thiết kế cấu trúc cơ sở dữ liệu PostgreSQL, tìm kiếm văn bản nhanh, tích hợp lưu trữ hình ảnh trên đám mây S3. | Nguyễn Văn Bảo |
| **Kiểm thử Chất lượng (QA / Testing)** | Thực hiện kiểm thử chức năng, kiểm thử tải đồng thời chống trùng lịch, kiểm thử bộ kịch bản chuẩn vàng AI. | Trần Thị Thu Trang |
| **Vận hành & Bảo mật (DevOps & Security)** | Đóng gói ứng dụng trong container Docker, thiết lập máy chủ triển khai, bảo vệ dữ liệu cá nhân và nhật ký kiểm toán. | Ngọ Doãn Ngọc |

## 8.2. Lộ trình triển khai phiên bản thử nghiệm qua 6 giai đoạn

### Giai đoạn 1: Xây dựng Nền tảng, Dữ liệu mẫu & Phân quyền (Foundation)
- Thiết lập môi trường vận hành trên Docker và cấu hình cơ sở dữ liệu PostgreSQL.
- Thiết kế các bảng dữ liệu, chạy kịch bản tạo bảng và nạp dữ liệu mẫu gồm 30–50 căn hộ Vinhomes có thật.
- Xây dựng cơ chế đăng nhập, xác thực bằng mã OTP và phân quyền rõ ràng cho 3 vai trò (Khách mua, Chủ nhà, Ban quản trị).

### Giai đoạn 2: Trợ lý AI Khám phá & Gợi ý Căn hộ (AI Discovery)
- Tích hợp mô hình ngôn ngữ lớn (Google Gemini / OpenAI GPT) qua khung điều phối LangGraph.
- Xây dựng năng lực bóc tách nhu cầu của khách bằng tiếng Việt tự nhiên.
- Phát triển cơ chế lọc căn kết hợp (lọc cứng theo tiêu chí bắt buộc + chấm điểm mềm theo sở thích).
- Hoàn thiện giao diện khung chat và các Thẻ căn hộ tương tác cho khách vãng lai.

### Giai đoạn 3: Kết nối Trực tiếp, Khớp lịch & Tạm khóa Căn (Direct Connection & Booking)
- Xây dựng màn hình cài đặt khung giờ rảnh cho Chủ nhà và xác thực Sổ đỏ qua mã OTP.
- Phát triển thuật toán tự động tính toán khung giờ giao nhau giữa hai bên.
- Tạo mã giao dịch (Deal ID) và gửi thông báo tức thời tới Chủ nhà.
- Hiện thực hóa cơ chế Tạm khóa căn nguyên tử trên PostgreSQL để loại trừ hoàn toàn nguy cơ trùng lịch.

### Giai đoạn 4: Chăm sóc Sau Buổi Xem & Kênh Trao đổi Trực tiếp (Post-viewing)
- Xây dựng hệ thống tự động gửi thông báo nhắc lịch hẹn trước 24 giờ và trước 2 giờ.
- Mở phòng nhắn tin trực tiếp an toàn giữa Khách mua và Chủ nhà sau khi hoàn tất buổi xem.
- Thiết lập tác vụ nền tự động theo dõi, chăm sóc khách hàng nếu chủ nhà chưa phản hồi.

### Giai đoạn 5: Bảng Điều hành Quản trị & Xử lý Ngoại lệ (Operations)
- Xây dựng bảng điều khiển cho Ban quản trị Chủ đầu tư: duyệt tin đăng, duyệt hồ sơ Sổ đỏ.
- Thiết lập hàng đợi tiếp nhận và xử lý các trường hợp ngoại lệ, khiếu nại hoặc quá hạn phản hồi.
- Hoàn thiện hệ thống nhật ký kiểm toán ghi lại mọi thay đổi dữ liệu quan trọng.

### Giai đoạn 6: Đánh giá Chất lượng Thực tế & Thử nghiệm (Evaluation)
- Chạy tự động bộ kiểm thử chuẩn vàng AI Golden Set trên hơn 20 kịch bản thực tế.
- Kiểm thử tải đồng thời (Concurrency Test) để chứng minh không bao giờ xảy ra trùng lịch.
- Đo lường các chỉ số hiệu quả (KPIs) và hoàn thiện báo cáo thử nghiệm toàn diện.

---

# §9. Đề xuất Kiến trúc Kỹ thuật Hệ thống

## 9.1. Bảng công nghệ khuyến nghị (Tech Stack)

| Phân tầng hệ thống | Công nghệ lựa chọn | Lý do và Lợi ích mang lại |
|---|---|---|
| **Giao diện người dùng (Frontend)** | **React 19, TypeScript, Tailwind CSS, Vite** | Tạo giao diện mượt mà, tốc độ tải trang cực nhanh, tương thích hoàn hảo với cả điện thoại và máy tính; phân chia rõ ràng 3 cổng chức năng. |
| **Máy chủ xử lý (Backend)** | **Python 3.11+, FastAPI, Pydantic v2** | Hiệu năng xử lý bất đồng bộ cao, xử lý mượt mà các tác vụ AI và dữ liệu, tự động sinh tài liệu chuẩn hóa API (Swagger UI). |
| **Cơ sở dữ liệu (Database)** | **PostgreSQL 15+ (Neon Serverless)** | Hệ quản trị cơ sở dữ liệu hàng đầu thế giới, đảm bảo giao dịch toàn vẹn 100%, hỗ trợ khóa loại trừ độc quyền chống trùng lịch hoàn hảo. |
| **Tìm kiếm văn bản (Search)** | **PostgreSQL Full-text Search (`pg_trgm`)** | Tận dụng trực tiếp tính năng tìm kiếm văn bản tiếng Việt cực nhanh có sẵn trong PostgreSQL, tiết kiệm chi phí vận hành hạ tầng riêng. |
| **Cơ sở dữ liệu Vector (Vector DB)** | *Chưa dùng trong bản thử nghiệm* | Do giai đoạn này hệ thống ưu tiên lọc chính xác theo tiêu chí thực tế (giá, số phòng, phân khu) thay vì tìm kiếm tài liệu mở; giúp tối ưu chi phí. |
| **Mô hình Trí tuệ Nhân tạo (LLM)** | **Google Gemini & OpenAI GPT** | Hỗ trợ linh hoạt cả Google Gemini (`gemini-2.5-flash`) và OpenAI (`gpt-4o-mini`) giúp đảm bảo tốc độ phản hồi nhanh và chi phí hợp lý. |
| **Khung điều phối Agent** | **LangGraph & LangChain** | Quản lý phiên hội thoại nhiều lượt có nhớ trạng thái, phân nhánh kịch bản linh hoạt và kiểm soát chặt chẽ việc gọi công cụ an toàn. |
| **Bộ nhớ hội thoại AI** | **PostgreSQL Checkpointer** | Lưu giữ toàn bộ ngữ cảnh và trí nhớ của khách hàng ngay trong cơ sở dữ liệu, đảm bảo không bị mất dữ liệu khi khởi động lại máy chủ. |
| **Bảo mật & Đăng nhập** | **Mã OTP điện thoại & Khóa Token JWT** | Đăng nhập tiện lợi bằng số điện thoại qua mã OTP, mã hóa mật khẩu nhiều lớp đảm bảo an toàn tuyệt đối cho thông tin cá nhân. |
| **Lưu trữ hình ảnh/video** | **Amazon S3 / Supabase Storage** | Lưu trữ toàn bộ ảnh chụp thực tế và video căn hộ chất lượng cao lên đám mây, giúp trang web tải nhẹ và nhanh chóng. |
| **Đóng gói & Triển khai** | **Docker, Render, Vercel** | Đóng gói đồng nhất, dễ dàng triển khai tự động lên các nền tảng đám mây hiện đại. |

## 9.2. Sơ đồ kiến trúc tổng thể

```text
              NGƯỜI MUA (BUYER)          CHỦ NHÀ (OWNER)
                      │                         │
                      └────────────┬────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │    GIAO DIỆN WEB (FRONTEND)   │
                   │   React 19 + TypeScript + Vite│
                   └───────────────┬───────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │    MÁY CHỦ XỬ LÝ (BACKEND)    │
                   │       FastAPI + Python        │
                   └───────────────┬───────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │    BỘ NÃO AI (AGENT ENGINE)   │
                   │     LangGraph + Gemini / GPT  │
                   │                               │
                   │ • Thấu hiểu câu nói tự nhiên  │
                   │ • Chấm điểm & Gợi ý căn hộ    │
                   │ • Tính toán khớp lịch rảnh    │
                   │ • Điều phối luồng hành động   │
                   └───────────────┬───────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │    LỚP CÔNG CỤ AN TOÀN        │
                   │      (SAFE TOOL LAYER)        │
                   │  (Kiểm tra quyền hạn & quy tắc)│
                   └───────────────┬───────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│ KHO DỮ LIỆU   │          │ BỘ MÁY XỬ LÝ  │          │ BỘ QUẢN LÝ    │
│ CĂN HỘ & USER │          │ LỊCH HẸN      │          │ HỒ SƠ GIAO    │
│ (PostgreSQL)  │          │ (Scheduling)  │          │ DỊCH (Deal)   │
└───────┬───────┘          └───────┬───────┘          └───────┬───────┘
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   ▼
                   ┌───────────────────────────────┐
                   │ BAN QUẢN TRỊ / NHÂN VIÊN      │
                   │ HỖ TRỢ CỦA CHỦ ĐẦU TƯ         │
                   │      (Human-in-the-loop)      │
                   └───────────────────────────────┘
```

## 9.3. Ranh giới Bảo mật Nhiều lớp (Security Boundary)

```text
Trí tuệ Nhân tạo (LLM / Agent)
            ↓
Lớp công cụ kiểm duyệt an toàn (Tool Layer)
            ↓
Xác thực danh tính & Kiểm tra quyền hạn (Authorization)
            ↓
Kiểm tra tính hợp lệ của quy tắc nghiệp vụ (Business Rules)
            ↓
Lớp dịch vụ xử lý dữ liệu (Service Layer)
            ↓
Cơ sở dữ liệu PostgreSQL (Database)
```

> **Nguyên tắc bất biến: Tuyệt đối không bao giờ cho phép mô hình AI truy cập hoặc chỉnh sửa trực tiếp cơ sở dữ liệu.**

## 9.4. Quy trình Gợi ý Căn hộ Thông minh (5 bước)

```text
1. Khách nhắn nhu cầu bằng tiếng Việt tự nhiên
   ("Tìm cho anh căn 2 ngủ Ocean Park, tài chính dưới 4 tỷ rưỡi, ban công Đông Nam mát mẻ")
                           ↓
2. AI chắt lọc các tiêu chí cốt lõi
   (Dự án: Ocean Park | Số phòng ngủ: 2 | Ngân sách trần: 4.5 tỷ | Ưu tiên: Ban công Đông Nam)
                           ↓
3. Lọc cứng trong cơ sở dữ liệu (Hard Filtering)
   (Chỉ lấy các căn ĐÃ KIỂM DUYỆT, đúng 2 phòng ngủ, giá bán <= 4.5 tỷ; loại ngay các căn không đạt)
                           ↓
4. Chấm điểm độ phù hợp theo sở thích (Soft Scoring & Weighting)
   - Độ hợp lý về giá bán (30%)
   - Độ rộng và bố trí diện tích (20%)
   - Hướng ban công & Tầm nhìn thoáng mát (20%)
   - Khoảng tầng phù hợp (15%)
   - Tiện ích nội khu gần công viên, hồ nước (15%)
                           ↓
5. Chọn ra Top các căn điểm cao nhất và Giải thích lý do đề xuất
   ("Em gợi ý căn này vì nằm đúng tầm giá 4.2 tỷ của anh, ban công hướng Đông Nam đón gió rất mát và chỉ cách hồ trung tâm 150m")
```

## 9.5. Cơ chế Tự động Khớp Lịch Xem Nhà

```text
Thời gian rảnh của Người mua
            │
            ▼
Thời gian rảnh của Chủ nhà
            │
            ▼
Tính toán khoảng thời gian giao nhau (Intersection)
            │
            ▼
Tạo danh sách các mốc giờ hẹn gợi ý (mỗi mốc 30 phút)
            │
            ▼
Người mua chọn khung giờ thuận tiện nhất
            │
            ▼
Chủ nhà nhận thông báo và bấm "Đồng ý"
            │
            ▼
Hệ thống Tạm khóa căn trong đúng khung giờ đó (Viewing Hold)
```

---

# §10. Danh mục Các Câu hỏi Mở Cần Hoàn thiện Tiếp

1. Chủ đầu tư sẽ thu hút nguồn căn hộ thứ cấp từ những kênh truyền thông nội bộ nào?
2. Chủ nhà đăng tin bán căn hộ có được miễn phí hoàn toàn trong giai đoạn đầu hay không?
3. Mức phí dịch vụ hỗ trợ thủ tục giao dịch của Chủ đầu tư dự kiến là bao nhiêu?
4. Bên nào sẽ chịu trách nhiệm chi trả khoản phí dịch vụ này (Người mua, Chủ nhà hay chia đôi)?
5. Phí dịch vụ sẽ được tính theo từng giao dịch thành công hay theo gói dịch vụ định kỳ?
6. Nếu Người mua và Chủ nhà tự ý giao dịch riêng ngoài hệ thống thì cơ chế đối soát nguồn gốc được thực hiện như thế nào?
7. Khoảng thời gian ghi nhận nguồn gốc giao dịch phát sinh từ nền tảng là bao lâu (ví dụ: 60 ngày hay 90 ngày)?
8. Nếu Chủ nhà không bấm duyệt yêu cầu xem nhà trong bao lâu thì hệ thống tự động chuyển cho nhân viên hỗ trợ gọi điện can thiệp?
9. Thông tin cá nhân giữa Người mua và Chủ nhà được mở ở cấp độ chi tiết nào sau khi buổi xem nhà kết thúc?
10. Khi nào thì hệ thống cho phép kích hoạt phòng chat trực tiếp giữa hai bên?
11. Khi nào thì Chủ nhà được phép nhìn thấy số điện thoại của Người mua?
12. Thời lượng tiêu chuẩn cho một buổi xem nhà là bao lâu (ví dụ: 30 phút hay 45 phút)?
13. Có cần khoảng thời gian đệm cách nhau giữa hai lượt xem nhà liên tiếp hay không (ví dụ: nghỉ 15 phút)?
14. Nếu một căn hộ nhận được yêu cầu xem từ nhiều người mua cùng lúc thì quy tắc ưu tiên xếp lịch sẽ ra sao?
15. Chính sách xử lý đối với các trường hợp người mua hoặc chủ nhà vắng mặt không đến xem (No-show) là gì?
16. Nhân viên hỗ trợ xử lý ngoại lệ sẽ trực thuộc ban quản lý tòa nhà hay phòng chăm sóc khách hàng của Chủ đầu tư?
17. Chuyên viên thủ tục giao dịch sẽ tham gia tiếp nhận hồ sơ từ thời điểm nào?
18. Lựa chọn đơn vị cung cấp dịch vụ gửi tin nhắn SMS hoặc tin nhắn Zalo ZNS nào tại Việt Nam?
19. Chính sách lưu trữ và thời hạn xóa dữ liệu tin nhắn hội thoại cá nhân là bao lâu để bảo đảm tuân thủ Nghị định 13/2023/NĐ-CP?
20. Mức số liệu cơ sở hiện tại về số cuộc gọi làm phiền mà một người mua nhà phải nhận là bao nhiêu?
21. Thời gian trung bình hiện nay từ lúc khách phát sinh nhu cầu đến lúc được đi xem nhà thực tế là bao nhiêu ngày?
22. Những chính sách ưu đãi thiết thực nào sẽ giữ chân Người mua và Chủ nhà tiếp tục hoàn tất giao dịch trong hệ thống thay vì giao dịch ngoài?

---

# §11. Ranh giới Chốt chặn của Phiên bản Thử nghiệm (MVP Boundary)

## Các tính năng BẮT BUỘC PHẢI CÓ (Must Have):
- Xác thực đăng nhập cho Người mua bằng số điện thoại và mã OTP.
- Xác thực đăng nhập cho Chủ nhà và đối soát Sổ đỏ chính chủ.
- Trải nghiệm trò chuyện tự nhiên với Trợ lý AI (hỗ trợ khách vãng lai).
- Tự động bóc tách nhu cầu của người mua bằng tiếng Việt.
- Tra cứu kho căn hộ và lọc căn kết hợp (lọc cứng + chấm điểm mềm).
- Trợ lý AI giải thích rõ lý do đề xuất từng căn hộ.
- Hiển thị đầy đủ chi tiết thông số, tiện ích và hình ảnh căn hộ.
- Quy trình đăng ký căn hộ cần bán dành cho Chủ nhà.
- Kiểm duyệt tin đăng và xác minh giấy tờ từ Ban quản trị.
- Cài đặt và quản lý các khung giờ rảnh của căn hộ.
- Kết nối trực tiếp giữa Người mua và Chủ nhà không qua môi giới rác.
- Tự động cấp Mã giao dịch (Deal ID) cho mỗi lượt kết nối.
- Gửi yêu cầu đặt lịch xem nhà theo khung giờ mong muốn.
- Tự động tính toán các mốc giờ giao nhau giữa hai thời gian biểu.
- Bắt buộc Chủ nhà phê duyệt lịch hẹn (Human-in-the-loop).
- Cơ chế Tạm khóa căn nguyên tử trên cơ sở dữ liệu để chống trùng lịch tuyệt đối.
- Tự động gửi thông báo nhắc lịch hẹn trước 24 giờ và trước 2 giờ.
- Cơ chế phân quyền và bảo vệ quyền riêng tư nghiêm ngặt.
- Tự động chuyển giao các trường hợp ngoại lệ cho Nhân viên hỗ trợ.
- Nhật ký kiểm toán ghi lại mọi thay đổi dữ liệu quan trọng.

## Các tính năng TUYỆT ĐỐI KHÔNG LÀM trong giai đoạn này (Must Not Have):
- Tuyệt đối không tích hợp cổng thanh toán trực tuyến hoặc chuyển khoản ngân hàng.
- Tuyệt đối không nhận tiền đặt cọc giữ chỗ mua bán căn hộ.
- Tuyệt đối không ký hợp đồng mua bán điện tử trên hệ thống.
- Tuyệt đối không để AI tự ý định giá hoặc dự báo biến động giá thị trường.
- Tuyệt đối không tích hợp gói vay ngân hàng hoặc tính toán trả góp phức tạp.
- Tuyệt đối không để AI tham gia đàm phán, mặc cả giá bán thay người dùng.
- Tuyệt đối không để AI tự ý xác nhận hoặc chốt giao dịch mua bán.
- Tuyệt đối không sử dụng cuộc gọi tự động bằng giọng nói (Voice AI).
- Tuyệt đối không kết nối với các hệ thống môi giới (CRM) bên ngoài.
- Tuyệt đối không mở rộng ra các dự án bất động sản ngoài hệ sinh thái Vinhomes.
- Tuyệt đối nghiêm cấm AI tự ý thu thập hoặc chia sẻ số điện thoại cá nhân khi chưa được cho phép.

---

# §12. Định nghĩa Sản phẩm Cốt lõi & Luồng Trình diễn Tiêu biểu

## Định nghĩa sản phẩm trong một câu duy nhất:
> **BookingBot AI Agent là trợ lý thông minh giúp khách hàng tìm đúng căn hộ Vinhomes ưng ý, kết nối trực tiếp với chủ sở hữu chính chủ và tự động sắp xếp lịch hẹn xem nhà mượt mà, chấm dứt hoàn toàn sự phụ thuộc vào môi giới rác và các cuộc gọi làm phiền; đồng thời giúp Chủ đầu tư làm sạch nguồn cung, bảo chứng pháp lý, loại trừ trùng lịch và kiểm soát an toàn toàn bộ hành trình giao dịch.**

## Luồng Trình diễn Tiêu biểu (Core Demo Flow)

```text
NGƯỜI MUA
   │
   ▼
Nhắn câu tự nhiên: "Anh cần tìm căn 2 ngủ bên Ocean Park tầm 4 tỷ rưỡi"
   │
   ▼
TRỢ LÝ AI HIỂU NHU CẦU & CHẤM ĐIỂM
   │
   ▼
HIỂN THỊ 3 THẺ CĂN HỘ PHÙ HỢP NHẤT KÈM LÝ DO ĐỀ XUẤT
   │
   ▼
Người mua chọn căn ưng ý và bấm "Tôi muốn xem căn này"
   │
   ▼
CẤP MÃ GIAO DỊCH (DEAL ID)
   │
   ▼
CHỦ NHÀ ĐÃ XÁC THỰC SỔ ĐỎ NHẬN ĐƯỢC YÊU CẦU
   │
   ▼
AI TÍNH TOÁN KHỚP KHUNG GIỜ RẢNH CHUNG
   │
   ▼
CHỦ NHÀ BẤM "ĐỒNG Ý"
   │
   ▼
TẠM KHÓA CĂN CHỐNG TRÙNG LỊCH (VIEWING HOLD)
   │
   ▼
HAI BÊN ĐẾN XEM NHÀ THỰC TẾ ĐÚNG HẸN
   │
   ▼
HOÀN TẤT BUỔI XEM NHÀ THÀNH CÔNG (KẾT THÚC DEMO MVP)
```

## Định vị Giá trị Cốt lõi:
> **Mục tiêu của dự án không phải là dùng AI để thay thế con người.**  
> **Trí tuệ Nhân tạo đóng vai trò giải phóng con người khỏi những khâu thủ công tốn thời gian (sàng lọc thông tin, bóc tách nhu cầu, đối soát lịch và nhắc hẹn); trong khi con người vẫn nắm giữ trọn vẹn vai trò quyết định tại các điểm mấu chốt: Chủ nhà trực tiếp phê duyệt lịch, Chủ đầu tư bảo chứng pháp lý Sổ đỏ, Nhân viên hỗ trợ đồng hành và chuyên viên thủ tục hoàn tất giao dịch an toàn.**
