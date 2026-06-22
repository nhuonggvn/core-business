# Hướng dẫn chạy và tích hợp mạng nội bộ — Core Business (A6)

Tài liệu này hướng dẫn chi tiết cách chạy thử nghiệm local, cấu hình mạng nội bộ LAN / Radmin VPN phục vụ tích hợp liên nhóm (Buổi 6) cho dịch vụ **Core Business (A6)**.

---

## 1. Thiết lập file môi trường `.env`

File `.env` chứa các biến cấu hình cổng, token bảo mật và URL của các service đối tác. Tạo file `.env` bằng cách copy từ `.env.example`:

```bash
cp .env.example .env
```

Các biến môi trường cấu hình bắt buộc:

```env
# Cấu hình API Core Business
APP_HOST=0.0.0.0
APP_PORT=8000
AUTH_TOKEN=local-dev-token
SERVICE_NAME=core-business
SERVICE_VERSION=0.4.0

# Cấu hình Database Postgres
POSTGRES_USER=lab05
POSTGRES_PASSWORD=lab05pass
POSTGRES_DB=iotdb

# Cấu hình URL tích hợp liên nhóm (Radmin IP hoặc IP Hotspot)
NOTIFICATION_SERVICE_URL=http://26.31.10.34:8000
VISION_SERVICE_URL=http://26.31.10.7:9000
```

> [!WARNING]
> Tuyệt đối không commit file `.env` chứa token bảo mật hoặc IP thật của môi trường thực tế lên Git. Tệp `.env` đã được cấu hình bỏ qua trong `.gitignore`.

---

## 2. Cấu hình Radmin VPN cho buổi tích hợp (Buổi 6)

Khi chạy thử từ xa hoặc demo tại lớp học, để các máy tính có thể gọi API chéo của nhau:

1. **Cài đặt Radmin VPN**: Tải bản cài đặt cho Windows tại [Radmin VPN](https://www.radmin-vpn.com/vi/).
2. **Join mạng**:
   - Chọn `Network` -> `Join Network`.
   - Nhập tên mạng và mật khẩu do lớp trưởng hoặc giảng viên cung cấp (Ví dụ: `FIT4110-DEMO-A`, mật khẩu: `fit4110-demo-A@2026`).
3. **Lấy IP**: Trên giao diện Radmin VPN, copy địa chỉ IP ảo được cấp (dải IP thường bắt đầu bằng `26.x.x.x`). Cung cấp IP này cho nhóm **Access Gate (A3)** để họ điền vào `.env` gọi sang mình.
4. **Cập nhật IP đối tác**:
   - Lấy IP Radmin của nhóm **Notification (A7)** điền vào `NOTIFICATION_SERVICE_URL` trong file `.env`.
   - Khởi động lại dịch vụ để áp dụng IP mới:
     ```bash
     docker compose down
     docker compose up -d --build
     ```

---

## 3. Cấu hình Windows Firewall (Bắt buộc)

Nếu nhóm Access Gate (A3) gọi sang máy demo của bạn mà gặp lỗi **Timeout**, nguyên nhân chủ yếu là Windows Firewall chặn kết nối đi vào cổng `8000`.

Mở PowerShell với quyền **Administrator** và chạy lệnh sau để mở chặn:

```powershell
netsh advfirewall firewall add rule name="FIT4110 A6 Core Business 8000" dir=in action=allow protocol=TCP localport=8000
```

Để thu hồi quyền sau buổi học:

```powershell
netsh advfirewall firewall delete rule name="FIT4110 A6 Core Business 8000"
```

---

## 4. Kiểm tra kết nối đa dịch vụ

Sau khi mọi người đã kết nối chung mạng Radmin VPN và bật Docker Compose:

1. **Kiểm tra sức khỏe local**:
   ```bash
   curl http://localhost:8000/health
   ```
2. **Kiểm tra kết nối chéo sang Notification (A7)**:
   ```bash
   curl http://<RADMIN_IP_A7>:8000/health
   ```
3. **Giả lập sự kiện quẹt thẻ lỗi để kích hoạt gửi Alert**:
   Gửi request xác thực truy cập với timestamp năm `2029` (Kích hoạt luật thẻ hết hạn `CARD_EXPIRED`):
   ```bash
   curl -X POST http://localhost:8000/access/check \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer local-dev-token" \
     -d '{
       "requestId": "0196fb3d-4ad7-7d1e-9f49-5d5148d2cafe",
       "cardId": "CARD-123456",
       "gateId": "GATE-01",
       "direction": "IN",
       "timestamp": "2029-06-01T10:00:00Z"
     }'
   ```
4. **Xem logs ghi nhận gửi Alert**:
   ```bash
   docker compose logs -f api
   ```
   *Logs cần hiển thị dòng chữ: `Sending alert to Notification Service...` và `Alert sent successfully.` hoặc log lỗi timeout chi tiết nếu Notification đang offline.*
