# Phân tích yêu cầu — vai Provider

- Cặp đàm phán: Pair 02 — Core Business (A6/B6) ↔ AI Vision (A4/B4)
- Product: A
- Provider service: AI Vision (A4)
- Consumer service: Core Business (A6)
- Người viết: Nguyễn Văn Hưởng
- Ngày: 27-05-2026

---

## 1. Resource chính

| Resource | Mô tả | Thuộc tính bắt buộc | Thuộc tính tùy chọn |
|---|---|---|---|
| `VisionDetectRequest` | Yêu cầu phân tích 1 ảnh/frame | `requestId`, `cameraId`, `capturedAt`, (`imageUrl` hoặc `imageBase64`) | `correlationId`, `locationId`, `metadata` |
| `VisionDetectResult` | Kết quả detect trả cho Core | `requestId`, `status`, `detectedAt`, `detections[]` | `processingTimeMs`, `modelVersion`, `notes` |

---

## 2. Action/API dự kiến

| Method | Path | Mục đích | Consumer gọi khi nào? |
|---|---|---|---|
| POST | `/vision/detect` | Nhận yêu cầu detect và trả kết quả | Khi Core cần phân tích ảnh/frame |
| GET | `/vision/detect/{requestId}` | Lấy lại kết quả theo requestId (nếu xử lý async) | Khi Core poll hoặc tra cứu |
| GET | `/vision/models` | Trả thông tin model/version | Khi Core cần audit/debug |
| GET | `/health` | Health check | Khi Core kiểm tra tình trạng service |

---

## 3. Error case

| Status | Tình huống | Response body dự kiến |
|---:|---|---|
| 400 | Thiếu ảnh hoặc sai format field | `Problem` |
| 401 | Thiếu Bearer token | `Problem` |
| 403 | Không đủ quyền | `Problem` |
| 404 | GET requestId không tồn tại | `Problem` |
| 409 | Trùng requestId | `Problem` |
| 422 | Ảnh quá lớn/không decode được/không đúng định dạng | `Problem` |
| 500 | Lỗi model/runtime | `Problem` |

---

## 4. Giả định bổ sung

- `requestId` là UUID và unique.
- `confidence` là số trong khoảng 0..1.
- Image mime types: `image/jpeg`, `image/png` (cần chốt).
- Nếu xử lý lâu: POST có thể trả `202 Accepted` + `Location` trỏ tới GET result.

---

## 5. Câu hỏi cho Consumer

1. Core cần kết quả đồng bộ (201) hay chấp nhận async (202 + poll)?
2. Core có cần bounding box/landmark chi tiết hay chỉ cần “type + confidence”?
3. Core muốn retry như thế nào khi 500/timeout (max retries, backoff)?

---

## 6. Rủi ro tích hợp

| Rủi ro | Tác động | Đề xuất xử lý |
|---|---|---|
| Payload ảnh quá lớn | Timeout/429/422 | Chốt size limit + hướng dẫn gửi `imageUrl` |
| Enum detection thay đổi theo model | Core xử lý sai | Chốt enum/versioning + modelVersion |
| Lỗi không chuẩn Problem Details | Core khó log/hiển thị | Chuẩn hóa `application/problem+json` |