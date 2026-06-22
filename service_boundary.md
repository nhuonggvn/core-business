# Service Boundary — Core Business Service (A6)

Tài liệu này định nghĩa ranh giới dịch vụ, vai trò và các giao tiếp tích hợp của dịch vụ **Core Business (A6)** trong hệ thống **Smart Campus Operations Platform**.

---

## 1. Vai trò của Core Business Service (A6)

Core Business là service trung tâm xử lý các quy tắc nghiệp vụ và điều phối hoạt động an ninh trong Campus:
- **Xử lý Quyết định Ra Vào (Access Decision)**: Tiếp nhận yêu cầu kiểm tra quyền truy cập từ Access Gate (A3), thực thi các chính sách an ninh (Policy Engine) và trả về quyết định cho phép (Allow) hoặc từ chối (Deny) ra vào.
- **Tạo Cảnh báo (Alert Ingestion)**: Nhận biết các sự kiện bất thường từ cảm biến IoT (qua IoT Ingestion A1) hoặc vi phạm ra vào, tự động kích hoạt cảnh báo gửi sang Notification Service (A7).
- **Quản lý Chính sách (Policy Management)**: Lưu trữ và cung cấp thông tin về các chính sách ra vào đang áp dụng trong khuôn viên trường.

---

## 2. Ranh giới Giao tiếp (API & Network Interfaces)

Core Business (A6) đóng cả hai vai trò: **Provider** (Cung cấp API) và **Consumer** (Gọi API bên thứ ba).

### 2.1. Vai trò Provider (Cung cấp API)
Cung cấp các REST endpoint đồng bộ (REST sync) cho **Access Gate (A3)** gọi sang:
- `POST /access/check`: Tiếp nhận yêu cầu quẹt thẻ và trả về kết quả cho phép/từ chối ra vào.
- `GET /policies/access/{policy_id}`: Lấy thông tin chi tiết của một chính sách ra vào.
- `GET /decisions/{decision_id}`: Lấy thông tin chi tiết của một quyết định ra vào đã thực hiện.
- `GET /gates/{gate_id}/status`: Trả về trạng thái hoạt động của cổng ra vào.

### 2.2. Vai trò Consumer (Gọi API đối tác)
Gọi sang dịch vụ của nhóm khác trong hệ thống:
- **Notification Service (A7)**: Gọi API `POST /api/v1/alerts` khi phát hiện các vi phạm an ninh (thẻ hết hạn, cố tình quẹt thẻ khi cổng đang khóa, ra vào ngoài giờ cho phép).
- **AI Vision Service (A4)** (Môi trường phát triển): Gọi API `POST /detect` để phân tích hình ảnh khi phát hiện chuyển động bất thường.

---

## 3. Mô hình Luồng Dữ liệu (Data Flow Diagram)

Mô hình tương tác mạng LAN ảo (qua Radmin VPN) giữa các nhóm trong Product A:

```text
+-----------------------+                    +-------------------------+
|   Access Gate (A3)    |                    |    IoT Ingestion (A1)   |
|   (Radmin IP: Port)   |                    |    (Radmin IP: Port)    |
+-----------+-----------+                    +------------+------------+
            |                                             |
            | (REST: POST /access/check)                  | (REST/MQTT Event)
            v                                             v
+-----------+---------------------------------------------+------------+
|                                                                      |
|                       Core Business Service (A6)                     |
|                              Port: 8000                              |
|                                                                      |
+-----------------------------------+----------------------------------+
                                    |
                                    | (REST: POST /api/v1/alerts, Timeout: 3.0s)
                                    v
                        +-----------+-----------+
                        |  Notification (A7)    |
                        |   (Radmin IP: Port)   |
                        +-----------------------+
```
