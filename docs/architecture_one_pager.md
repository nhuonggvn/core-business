# Architecture One-Pager — Core Business Service (A6)

Tài liệu này tóm tắt kiến trúc của dịch vụ Core Business (A6) phục vụ báo cáo bài tập lớn.

---

## 1. Kiến trúc hệ thống cục bộ (Local Stack)
Dịch vụ chạy trên môi trường container hóa Docker Compose bao gồm 3 thành phần chính kết nối qua mạng nội bộ `team-internal`:

- **API Container (`fit4110-api-a6`)**: 
  - Framework: FastAPI (Python 3.11).
  - Vai trò: Tiếp nhận request `/access/check` từ Access Gate, gọi AI Vision để phân tích hình ảnh, áp dụng các chính sách (Policy Engine) và gọi Notification Service để báo động.
- **Database Container (`fit4110-db-a6`)**:
  - Hệ quản trị: PostgreSQL 15.
  - Vai trò: Lưu trữ logs ra vào, thông tin thẻ và các chính sách an ninh hoạt động.
- **Mock AI Container (`fit4110-ai-mock`)**:
  - Vai trò: Giả lập dịch vụ AI Vision trả về kết quả nhận diện (phục vụ tự kiểm thử offline).

---

## 2. Kiến trúc Tích hợp Mạng nội bộ (Radmin VPN)
Khi tích hợp liên nhóm, dịch vụ kết nối với các đối tác thông qua mạng LAN ảo **Radmin VPN** (mạng `saubaysigmaboy`):

- **IP Core Business chính (máy bạn)**: `26.88.31.108:8000` (được gọi bởi Access Gate A3 và IoT Ingestion A1).
- **IP Notification (A7)**: `26.19.238.62:8000` (Core Business gọi sang để gửi cảnh báo).
- **IP AI Vision (A4)**: `26.15.57.238:8000` (Core Business gọi smoke-test hoặc nhận kết quả).
- **Bảo mật**: Sử dụng Header xác thực `Authorization: Bearer smart-campus-secret-token` thống nhất giữa các nhóm để đảm bảo an toàn kết nối.
