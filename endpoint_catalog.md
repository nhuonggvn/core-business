# Endpoint Catalog — Core Business Service (A6)

Tài liệu này liệt kê chi tiết danh mục các endpoints (API Catalog) mà Core Business cung cấp cho các dịch vụ khác (như Access Gate) gọi sang.

---

## 1. Danh sách Endpoint chính

### 1.1. Kiểm tra quyền truy cập ra vào (Access Check)
- **Path**: `/access/check`
- **Method**: `POST`
- **Authentication**: Bearer Token (`Authorization: Bearer <token>`)
- **Headers bắt buộc**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <token>`
- **Request Payload (`AccessCheckRequest`)**:
```json
{
  "requestId": "0196fb3d-4ad7-7d1e-9f49-5d5148d2cafe",
  "cardId": "CARD-123456",
  "gateId": "GATE-01",
  "direction": "IN",
  "timestamp": "2026-06-01T10:00:00Z"
}
```
- **Ràng buộc trường dữ liệu**:
  - `cardId` bắt buộc khớp regex: `^CARD-[0-9]{6}$`
  - `direction` chỉ nhận giá trị: `IN` hoặc `OUT`
- **Response thành công (200 OK - Cho phép)**:
```json
{
  "decisionId": "0196fb3d-4ad7-7d1e-9f49-5d5148d2caff",
  "allow": true,
  "reasonCode": "ALLOWED",
  "policyId": "POL-101",
  "expiresAt": "2026-06-01T10:00:05Z"
}
```
- **Response bị từ chối (200 OK - Từ chối)**:
```json
{
  "decisionId": "0196fb3d-4ad7-7d1e-9f49-5d5148d2cafb",
  "allow": false,
  "reasonCode": "CARD_EXPIRED",
  "policyId": "POL-101",
  "expiresAt": "2026-06-01T10:00:05Z"
}
```
*Các mã lỗi từ chối có thể xảy ra trong `reasonCode`: `CARD_EXPIRED`, `GATE_LOCKED`, `OUT_OF_SCHEDULE`.*
- **Response lỗi xác thực (401 Unauthorized)**:
```json
{
  "type": "https://smart-campus.local/problems/unauthorized",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Invalid bearer token",
  "instance": "/access/check"
}
```
- **Response lỗi định dạng (422 Unprocessable Entity)**:
```json
{
  "type": "https://smart-campus.local/problems/validation-error",
  "title": "Validation error",
  "status": 422,
  "detail": "body.cardId: cardId must match pattern ^CARD-[0-9]{6}$",
  "instance": "/access/check"
}
```

---

### 1.2. Xem chi tiết quyết định đã thực hiện (Get Decision)
- **Path**: `/decisions/{decision_id}`
- **Method**: `GET`
- **Authentication**: Bearer Token
- **Response thành công (200 OK)**:
```json
{
  "decisionId": "0196fb3d-4ad7-7d1e-9f49-5d5148d2caff",
  "cardId": "CARD-123456",
  "gateId": "GATE-01",
  "allow": true,
  "reasonCode": "ALLOWED"
}
```

---

### 1.3. Lấy thông tin chính sách ra vào (Get Policy)
- **Path**: `/policies/access/{policy_id}`
- **Method**: `GET`
- **Authentication**: Bearer Token
- **Response thành công (200 OK)**:
```json
{
  "policyId": "POL-101",
  "name": "Chính sách ra vào thông thường",
  "status": "ACTIVE",
  "description": "Chính sách cho phép ra vào giờ hành chính"
}
```
- **Response không tìm thấy (404 Not Found)**:
```json
{
  "type": "https://smart-campus.local/problems/not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "Policy POL-999 does not exist",
  "instance": "/policies/access/POL-999"
}
```

---

### 1.4. Lấy trạng thái của Cổng (Get Gate Status)
- **Path**: `/gates/{gate_id}/status`
- **Method**: `GET`
- **Authentication**: Bearer Token
- **Response thành công (200 OK)**:
```json
{
  "gateId": "GATE-01",
  "status": "OPEN"
}
```

---

### 1.5. Kiểm tra trạng thái sống của dịch vụ (Health Check)
- **Path**: `/health`
- **Method**: `GET` / `HEAD`
- **Authentication**: Không yêu cầu (Public endpoint)
- **Response thành công (200 OK)**:
```json
{
  "status": "ok",
  "service": "core-business",
  "version": "0.4.0"
}
```
*(Endpoint bắt buộc dùng để verify dịch vụ hoạt động trong Docker Compose).*
