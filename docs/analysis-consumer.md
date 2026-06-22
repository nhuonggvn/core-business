# Phân tích yêu cầu — vai Consumer

- Cặp đàm phán: Pair 02 — Core Business (A6/B6) ↔ AI Vision (A4/B4)
- Product: A
- Consumer service: Core Business (A6) — xử lý nghiệp vụ trung tâm / Rule Engine
- Provider service: AI Vision (A4) — phân tích hình ảnh / detect
- Người viết: Nguyễn Văn Hưởng
- Ngày: 27-05-2026

--
## 1. Resource Consumer cần nhận/gửi

| Resource | Consumer dùng để làm gì? | Field bắt buộc với Consumer | Field có thể tùy chọn |
|---|---|---|---|
| `VisionDetectRequest` | Gửi yêu cầu AI Vision phân tích ảnh (nhận diện người lạ/biển số/đột nhập) để Core ra quyết định nghiệp vụ | `requestId`, `cameraId`, `capturedAt`, **một trong** (`imageUrl` hoặc `imageBase64`) | `locationId`, `correlationId`, `priority`, `metadata` |
| `VisionDetectResult` | Nhận kết quả detect để Core tạo alert, ghi log, hoặc điều khiển Access Gate | `requestId`, `status`, `detectedAt`, `detections[]` (mỗi detection có `type`, `confidence`) | `faces[]/plates[]`, `boundingBoxes[]`, `processingTimeMs`, `rawModelVersion`, `notes` |

---

## 2. API Consumer cần gọi

| Method | Path | Lúc nào gọi? | Kỳ vọng response |
|---|---|---|---|
| POST | `/vision/detect` | Khi Core cần phân tích 1 ảnh/frame (theo event motion hoặc theo nghiệp vụ) | `201` trả `VisionDetectResult`; lỗi trả `Problem` |
| GET | `/vision/detect/{requestId}` | Khi Core muốn lấy lại kết quả theo requestId (trường hợp xử lý async nội bộ phía AI Vision) | `200` trả `VisionDetectResult`, `404` nếu không có |
| GET | `/vision/models` | Khi Core cần biết model/version đang chạy để audit hoặc debug | `200` trả danh sách model + version |
| GET | `/health` | Khi Core kiểm tra service AI Vision còn hoạt động để quyết định fallback | `200` trả HealthStatus |

> Ghi chú đàm phán: nếu AI Vision xử lý lâu, có thể trả `202 Accepted` ở POST và Core dùng GET theo `requestId` để poll.

---

## 3. Error case Consumer cần xử lý

| Status | Consumer hiểu là gì? | Consumer sẽ xử lý thế nào? |
|---:|---|---|
| 400 | Payload sai schema (thiếu imageUrl/base64, sai format) | Log lỗi, không retry, fix payload |
| 401 | Thiếu/expired token | Refresh token / cấu hình lại JWT |
| 403 | Không đủ quyền gọi detect | Báo lỗi quyền, kiểm tra scope/role |
| 404 | Không tìm thấy requestId khi GET | Dừng poll, đánh dấu job failed |
| 409 | Trùng requestId (idempotency) | Không tạo job mới; coi idempotent hoặc đổi requestId |
| 422 | Ảnh hợp lệ JSON nhưng không xử lý được (vd ảnh quá lớn/không đúng định dạng) | Hiển thị reason cụ thể, fallback sang phương án khác |
| 500 | Lỗi nội bộ AI Vision | Retry có backoff (giới hạn), hoặc fallback rule |

---

## 4. Giả định bổ sung

- Auth dùng Bearer JWT (`Authorization: Bearer <token>`).
- `requestId` là UUID và unique (dùng làm idempotency key nếu thống nhất).
- `capturedAt/detectedAt` dùng `date-time` ISO-8601 UTC.
- Nếu dùng `imageBase64`, cần chốt giới hạn kích thước (vd <= 2MB) và content-type.

---

## 5. Câu hỏi cho Provider

1. POST `/vision/detect` trả `201` ngay hay `202` + poll bằng GET? SLA xử lý dự kiến bao lâu?
2. Chốt format ảnh: ưu tiên `imageUrl` hay `imageBase64`? Có giới hạn size/định dạng (jpg/png) không?
3. `detections[].type` có enum cố định không (UNKNOWN_PERSON/INTRUSION/PLATE/...) và `confidence` range 0..1 hay 0..100?

---

## 6. Rủi ro tích hợp

| Rủi ro | Tác động | Đề xuất xử lý |
|---|---|---|
| Không thống nhất format ảnh | Core gửi không xử lý được | Chốt `imageUrl`/`imageBase64`, size limit, mime types |
| Model/labels thay đổi | Core mapping sai loại detection | Chốt enum/type + versioning, có `/vision/models` |
| Xử lý lâu/timeout | Core bị treo flow nghiệp vụ | Thống nhất 202 + polling hoặc timeout + fallback |