# Hướng dẫn vận hành bằng Docker Compose — Core Business (A6)

Tài liệu này hướng dẫn chi tiết cách thiết lập, khởi chạy và kiểm thử dịch vụ **Core Business (A6)** sử dụng **Docker Compose** trên môi trường local hoặc mạng nội bộ Radmin VPN.

---

## 1. Yêu cầu hệ thống
- **Docker Desktop** đã được cài đặt và đang chạy (hỗ trợ WSL2 trên Windows).
- **Node.js** phiên bản 20 trở lên (chỉ cần thiết nếu bạn muốn chạy lệnh kiểm thử Newman từ máy host).

---

## 2. Các bước chuẩn bị

### Bước 2.1: Thiết lập cấu hình biến môi trường
Sao chép tệp cấu hình mẫu `.env.example` thành `.env`:

```bash
cp .env.example .env
```

Mở tệp `.env` vừa tạo và cấu hình các giá trị phù hợp (ví dụ trỏ IP sang máy đối tác A7 và A4):

```env
# Cấu hình API Core Business của bạn
APP_HOST=0.0.0.0
APP_PORT=8000
AUTH_TOKEN=smart-campus-secret-token
SERVICE_NAME=core-business
SERVICE_VERSION=0.5.0
ENV=local

# Cấu hình Database Postgres
POSTGRES_USER=lab05
POSTGRES_PASSWORD=lab05pass
POSTGRES_DB=iotdb

# Cấu hình URL tích hợp liên nhóm qua Radmin VPN
NOTIFICATION_SERVICE_URL=http://26.19.238.62:8000
VISION_SERVICE_URL=http://26.15.57.238:8000/api/v1/vision/detect
AI_SERVICE_URL=http://26.15.57.238:8000/api/v1/vision/detect
```

---

## 3. Khởi chạy hệ thống

### Bước 3.1: Build và khởi động các dịch vụ
Chạy lệnh sau tại thư mục gốc của dự án để biên dịch Dockerfile và khởi chạy các container dưới dạng chạy ngầm (detached mode):

```bash
docker compose up -d --build
```

### Bước 3.2: Kiểm tra trạng thái hoạt động
Xác nhận cả 3 container (`fit4110-api-a6`, `fit4110-db-a6`, `fit4110-ai-mock`) đều ở trạng thái `Up` và `healthy`:

```bash
docker compose ps
```

### Bước 3.3: Xem log vận hành thời gian thực
Theo dõi logs chi tiết của container API để kiểm tra các request đi vào từ bên ngoài:

```bash
docker compose logs -f api
```

---

## 4. Kiểm tra sức khỏe dịch vụ (Health Check)
Sử dụng curl hoặc trình duyệt truy cập endpoint public để xác định dịch vụ đã sẵn sàng nhận kết nối:

```bash
curl http://localhost:8000/health
```

Kết quả trả về mong đợi (HTTP 200 OK):
```json
{
  "status": "ok",
  "service": "core-business",
  "version": "0.5.0"
}
```

---

## 5. Thực hiện kiểm thử tự động (Newman Contract Tests)

Dự án tích hợp sẵn bộ kiểm thử tự động để verify toàn bộ 26 assertions của hợp đồng API.

1. Cài đặt các thư viện kiểm thử trên máy host:
```bash
npm install
```

2. Thực hiện chạy kiểm thử tự động:
```bash
npm run test:compose
```

Lệnh này sẽ tự động gọi các endpoint của API, giả lập các trường hợp quẹt thẻ thành công, thẻ hết hạn, lỗi xác thực, kiểm tra khả năng gọi sang AI Vision và xuất báo cáo kết quả ra thư mục `reports/`.

---

## 6. Dừng hệ thống
Để hạ toàn bộ các container và giải phóng tài nguyên hệ thống:

```bash
docker compose down
```

Nếu muốn xóa sạch cả dữ liệu lưu trữ trong Database (xóa volume):

```bash
docker compose down -v
```
