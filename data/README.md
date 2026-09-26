# Bộ Dữ liệu Mẫu (Seed Datasets): BookingBot AI Agent

> Bộ dữ liệu nguồn dạng **CSV / Excel** phục vụ việc khởi tạo database ban đầu, test thuật toán AI Recommendation, luồng duyệt tin của Investor/Operator và luồng Booking & Viewing Hold.

---

## 1. Danh sách các file trong thư mục `data/`

| Tên file | Đối tượng sử dụng | Mô tả chức năng |
|---|---|---|
| [`properties_seed.csv`](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/data/properties_seed.csv) | Khách hàng, Chủ nhà & Operator | Danh sách căn hộ đăng bán gồm căn `AVAILABLE` (cho AI tìm kiếm), căn `PENDING_REVIEW` (để Operator test duyệt tin) và căn `REJECTED`. |
| [`projects_buildings_seed.csv`](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/data/projects_buildings_seed.csv) | **Investor / Operator** | Danh mục chuẩn các đại dự án (Ocean Park 1, Smart City, West Point, Grand Park), phân khu, tòa nhà và tọa độ GPS (`lat`, `long`). |
| [`amenities_seed.csv`](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/data/amenities_seed.csv) | **Investor / Operator** & AI | Danh mục các tiện ích hạt nhân của Vinhomes (Biển hồ, Hồ Ngọc Trai, Vincom, VinUni, Vinmec...) kèm tọa độ GPS để Backend tính `Proximity Scoring` thật. |
| [`users_seed.csv`](file:///Users/macos/AI%20Th%E1%BB%B1c%20Chi%E1%BA%BFn/P001-Discovery/P-001/data/users_seed.csv) | Hệ thống Auth & RBAC | Tài khoản mẫu cho cả 3 vai trò: `INVESTOR_OPERATOR` (Admin quản trị & kiểm duyệt), `OWNER` (Chủ nhà) và `CUSTOMER` (Khách tìm mua). |

---

## 2. Chi tiết dữ liệu cho vai trò Investor / Operator (Chủ đầu tư / Ban quản trị)

Theo đặc tả §4.11 & §4.13 của `spec_updated.md`, Investor/Operator có 3 nhiệm vụ trọng tâm được hỗ trợ bởi các file dữ liệu này:

### A. Kiểm duyệt tin đăng căn hộ (`Listing Moderation`)
Trong file `properties_seed.csv`:
- Các căn có `listing_status = 'PENDING_REVIEW'` (như căn `S2.05-1809` và `SA2-2508`): Dùng để test màn hình **Operator Dashboard**, nơi Operator xem chi tiết thông tin căn và bấm nút **Phê duyệt (Approve)** hoặc **Từ chối (Reject)**.
- Các căn có `listing_status = 'REJECTED'` (như căn `S1.02-0402`): Kiểm tra hiển thị lý do từ chối (thiếu ảnh sổ hồng, giá bất thường).

### B. Quản trị Danh mục Dự án & Tòa nhà (`projects_buildings_seed.csv`)
- Operator là bên duy nhất có quyền thêm/sửa danh mục Dự án và Tòa nhà.
- Toàn bộ căn hộ đăng bán của Chủ nhà bắt buộc phải liên kết (Foreign Key) với Tòa nhà và Dự án hợp lệ trong danh mục này.
- Có sẵn tọa độ `latitude` và `longitude` của từng tòa nhà.

### C. Quản lý Tiện ích & Vận hành AI Scoring (`amenities_seed.csv`)
- Thay vì để AI "đoán mò" khoảng cách, Operator khai báo tọa độ các tiện ích trọng điểm (Vincom, Vinschool, Hồ điều hòa...).
- Khi khách hỏi: *"Tìm căn gần công viên hoặc gần trường Vinschool"*, hệ thống đo khoảng cách hình học từ Tòa nhà tới Tiện ích để xếp hạng căn hộ.

---

## 3. Mẹo mở và chỉnh sửa trên Excel / Google Sheets
- Mở trực tiếp bằng Microsoft Excel hoặc tải lên Google Drive để mở bằng Google Sheets.
- Nhập thêm dòng hoặc sửa thông tin tùy ý, sau đó lưu lại dưới dạng file **CSV (Comma delimited)**.
