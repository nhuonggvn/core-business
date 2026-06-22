# Integration Notes — Core Business (A6)

Tài liệu này ghi lại thông tin cấu hình mạng và kết quả tích hợp thực tế trên Radmin VPN của nhóm Core Business (A6) tại Buổi 6.

---

## 1. Bảng phân phối IP & Port trong mạng `saubaysigmaboy`

| Nhóm | Service | Radmin IP | Port | Trạng thái tích hợp |
|---|---|---|---|---|
| **A1** | IoT Ingestion | `26.79.10.201` | `8000` | Sẵn sàng nhận sự kiện cảm biến |
| **A3** | Access Gate | `26.144.83.132` | `8000` | Gửi request `/access/check` sang A6 |
| **A4** | AI Vision | `26.15.57.238` | `8000` | Gọi thành công `/api/v1/vision/detect` (mã HTTP 422) |
| **A6 (Chính)** | **Core Business** | `26.88.31.108` | `8000` | Máy chủ chính thức của nhóm (chạy API & DB) |
| **A6 (Phụ)** | Core Business | `26.15.45.202` | `8000` | Máy phụ nhóm |
| **A7** | Notification | `26.19.238.62` | `8000` | Gửi Alert thành công từ A6 sang A7 |

---

## 2. Nhật ký Tích hợp chi tiết

### 2.1. Tích hợp A6 -> Notification (A7)
- **Địa chỉ gọi**: `http://26.19.238.62:8000/api/v1/alerts`
- **Kết quả**: Thành công hoàn toàn. Thời gian phản hồi giảm xuống còn **~34ms - 100ms** khi container A7 online, chứng tỏ hệ thống A7 đã tiếp nhận và phản hồi tức thời.

### 2.2. Tích hợp A6 -> AI Vision (A4)
- **Địa chỉ gọi**: `http://26.15.57.238:8000/api/v1/vision/detect`
- **Kết quả**: Kết nối mạng Radmin và xác thực token Bearer thành công. Dịch vụ A4 phản hồi mã lỗi `422 Unprocessable Entity` do payload mock của Lab 05 chưa đồng nhất cấu trúc, nhưng hạ tầng mạng đã thông suốt 100%.
- **Token sử dụng**: `smart-campus-secret-token`.
