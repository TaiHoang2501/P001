# Hướng dẫn Nhập Dữ liệu Căn hộ: `properties_seed.csv`

> File dữ liệu nguồn cho dự án **BookingBot AI Agent**, được thiết kế để mở và chỉnh sửa trực tiếp bằng **Microsoft Excel** hoặc **Google Sheets**.

---

## 1. Danh sách các cột & Quy ước giá trị

| Tên cột trong CSV | Bắt buộc | Kiểu / Giá trị cho phép | Ví dụ | Ý nghĩa nghiệp vụ |
|---|---|---|---|---|
| `property_code` | **Bắt buộc** | Text (Unique) | `S2.01-12A08` | Mã định danh căn hộ chuẩn |
| `project_name` | **Bắt buộc** | Text | `Vinhomes Ocean Park 1`, `Vinhomes Smart City`, `Vinhomes West Point` | Dự án đại đô thị |
| `zone` | Tùy chọn | Text | `The Sapphire 1`, `The Tonkin`, `The Miami` | Phân khu căn hộ |
| `building` | **Bắt buộc** | Text | `S2.01`, `GS3`, `TK1` | Tòa nhà |
| `floor_display` | **Bắt buộc** | Text | `08`, `12A`, `15` | Tầng thực tế hiển thị cho người dùng |
| `floor_range` | **Bắt buộc** | `LOW` / `MID` / `HIGH` | `MID` | Phân nhóm: `LOW` (2-10), `MID` (11-25), `HIGH` (26+) để AI tìm theo tầng |
| `property_type` | **Bắt buộc** | `APARTMENT` / `STUDIO` / `VILLA` / `SHOPHOUSE` | `APARTMENT` | Loại hình bất động sản |
| `layout_type` | **Bắt buộc** | `STUDIO`, `1PN`, `1PN_PLUS`, `2PN_1WC`, `2PN_2WC`, `2PN_PLUS`, `3PN` | `2PN_PLUS` | Cực kỳ quan trọng để AI phân biệt căn `+1` |
| `bedrooms` | **Bắt buộc** | Số nguyên (0, 1, 2, 3...) | `2` | Số phòng ngủ chính |
| `has_plus_one` | **Bắt buộc** | `TRUE` / `FALSE` | `TRUE` | Có không gian phụ đa năng (kê thêm giường/bàn học) |
| `bathrooms` | **Bắt buộc** | Số nguyên (1, 2...) | `2` | Số nhà vệ sinh |
| `area_sqm` | **Bắt buộc** | Số thực (m²) | `69.5` | Diện tích thông thủy |
| `selling_price` | **Bắt buộc** | Số nguyên (VNĐ) | `4200000000` | Giá bán niêm yết (4 tỷ 200 triệu) |
| `is_all_in_price` | **Bắt buộc** | `TRUE` / `FALSE` | `TRUE` | `TRUE`: Giá đã bao toàn bộ thuế phí sang tên; `FALSE`: Khách chịu phí |
| `tenure_type` | **Bắt buộc** | `PERPETUAL` / `50_YEARS` | `PERPETUAL` | `PERPETUAL`: Sổ hồng lâu dài; `50_YEARS`: Căn Officetel/50 năm |
| `legal_status` | **Bắt buộc** | `RED_BOOK` / `SPA` | `RED_BOOK` | `RED_BOOK`: Đã có Sổ đỏ/Sổ hồng; `SPA`: Đang là HĐMB |
| `direction_balcony`| Tùy chọn | Text | `Đông Nam`, `Tây Bắc`, `Nam`... | Hướng ban công chính để AI tính điểm hướng mát |
| `view_description` | Tùy chọn | Text | `View hồ san hô`, `View vườn hoa nội khu` | Mô tả tầm nhìn thực tế |
| `furnishing_status`| **Bắt buộc** | `RAW` / `BASIC` / `FULL` | `FULL` | `RAW` (thô), `BASIC` (cơ bản CĐT), `FULL` (đầy đủ đồ) |
| `key_highlights`   | **Bắt buộc** | Text (ngăn cách bởi dấu `;`) | `Căn góc 2 mặt thoáng; Đã có sổ hồng; Giá bao phí` | AI sẽ trích xuất trực tiếp câu này để **giải thích lý do đề xuất (Explainability)** |
| `nearby_amenities` | Tùy chọn | Text (ngăn cách bởi dấu `;`) | `Hồ Ngọc Trai: 350m; Vinschool: 200m` | Tiện ích nổi bật gần căn hộ |
| `viewing_weekdays` | **Bắt buộc** | Text | `18:30 - 20:30` | Khung giờ chủ nhà rảnh các ngày trong tuần |
| `viewing_weekends` | **Bắt buộc** | Text | `09:00 - 11:30 \| 14:30 - 17:30` | Khung giờ chủ nhà rảnh thứ 7 & Chủ nhật |
| `listing_status`   | **Bắt buộc** | `AVAILABLE` | `AVAILABLE` | Trạng thái hiển thị tìm kiếm |

---

## 2. Mẹo chỉnh sửa bằng Excel / Google Sheets
1. **Mở trên Google Sheets:** Tải file `properties_seed.csv` lên Google Drive $\rightarrow$ Chuột phải $\rightarrow$ Chọn *Open with Google Sheets*.
2. **Khi điền các trường danh sách (như `key_highlights` hoặc `nearby_amenities`):** Ngăn cách các ý bằng dấu chấm phẩy `;` (không dùng dấu phẩy `,` để tránh xung đột định dạng CSV).
3. **Khi lưu / Export:** Chọn **File $\rightarrow$ Download $\rightarrow$ Comma-separated values (.csv)**.
