# Changelog — Core Business Service (A6)

Tất cả các thay đổi đáng chú ý đối với dịch vụ Core Business (A6) sẽ được ghi lại trong tệp này.

---

## [1.0.0-final] - 2026-06-17

### Added
- Tích hợp thành công kết nối API Alert đồng bộ gọi sang Notification Service (A7) tại `http://26.19.238.62:8000/api/v1/alerts`.
- Thêm cơ chế Timeout **3.0s** và bọc khối `try-except` của thư viện `requests` để xử lý các lỗi kết nối mạng (connection refused, timeout) mà không làm crash API chính.
- Thêm biến môi trường `AI_SERVICE_URL` và `NOTIFICATION_SERVICE_URL` cấu hình linh hoạt trong `.env`.
- Bổ sung tài liệu chuẩn hóa dự án: `service_boundary.md`, `endpoint_catalog.md`, `RUN_LOCAL.md`.

### Changed
- Tổ chức lại cấu trúc repository: Đưa file chạy chính ra thư mục gốc `src/main.py` thay vì cấu trúc lặp `src/core_app/core_app/main.py` của Lab 05.
- Cập nhật lại Dockerfile và Docker Compose thích ứng với cấu trúc mã nguồn mới.
- Đổi token xác thực mặc định sang `smart-campus-secret-token` để đồng bộ kết nối liên nhóm.
- Sửa lại các tệp môi trường Postman kiểm thử tự động để trỏ Newman test sang các máy đối tác thật trên Radmin VPN.
