# Core Business Service (A6) — Smart Campus Operations Platform

Dịch vụ nghiệp vụ trung tâm (Core Business Service) phụ trách xử lý các quy tắc nghiệp vụ, quyết định quyền ra vào, và phát sinh cảnh báo trong hệ thống Smart Campus.

---

## 1. Vai trò của Service trong hệ thống
Core Business đóng vai trò bộ não trung tâm của kiến trúc Smart Campus:
- Kiểm tra hợp lệ thẻ ra vào từ đầu đọc RFID/QR (được gọi từ Access Gate A3).
- Áp dụng các chính sách an ninh động (Policy Engine) để đưa ra quyết định cho phép/từ chối ra vào.
- Tích hợp phát sinh cảnh báo đẩy sang Notification Service (A7) khi có vi phạm.
- Cung cấp logs giao dịch cho Analytics Service (A5).

---

## 2. Thành viên nhóm (A6)
- **Trần Công Thưởng** (Service Lead & Backend Developer)
- **Nguyễn Thị Hồng Duyên** (API Owner & Test/DevOps Developer)

---

## 3. Công nghệ sử dụng
- **Backend Framework**: Python (FastAPI v0.115)
- **Database**: PostgreSQL v15
- **HTTP Client**: requests (gọi Notification API với timeout 3s)
- **Linter**: Pyrefly / Flake8
- **Containerization**: Docker & Docker Compose
- **Testing**: Newman & Postman

---

## 4. Cấu trúc thư mục dự án

```text
team-a6-core-business/
    .dockerignore
    .env.example
    .gitignore
    Dockerfile
    docker-compose.yml
    openapi.yaml
    package.json
    pyrefly.toml
    requirements.txt
    service_boundary.md
    endpoint_catalog.md
    README.md
    RUN_LOCAL.md
    docs/
        analysis-consumer.md
        analysis-provider.md
        negotiation-log.md
    evidence/
        buoi-02/
            spectral-report.txt
    src/
        __init__.py
        main.py
        ai_service/
            __init__.py
            main.py
    tests/
        postman_collection.json
        environment_local.json
```

---

## 5. Danh sách Endpoints chính
- `GET /health` : Kiểm tra trạng thái sống của API (Public).
- `POST /access/check` : Kiểm tra quyền ra vào từ Access Gate (Yêu cầu Bearer Token).
- `GET /policies/access/{policy_id}` : Truy vấn chi tiết chính sách ra vào (Yêu cầu Bearer Token).
- `GET /decisions/{decision_id}` : Truy vấn lịch sử quyết định ra vào (Yêu cầu Bearer Token).
- `GET /gates/{gate_id}/status` : Truy vấn trạng thái cổng (Yêu cầu Bearer Token).

---

## 6. Service Upstream / Downstream
- **Upstream (Gọi A6)**: Access Gate (A3), IoT Ingestion (A1).
- **Downstream (A6 gọi)**: Notification Service (A7), AI Vision (A4 - môi trường dev mock).

---

## 7. Hướng dẫn chạy nhanh dự án

### Cách 1: Chạy bằng Docker Compose (Khuyến nghị)
Yêu cầu đã cài đặt Docker Desktop.

1. Thiết lập file môi trường:
```bash
cp .env.example .env
```
2. Khởi chạy Docker Compose stack:
```bash
docker compose up -d --build
```
3. Kiểm tra các container hoạt động:
```bash
docker compose ps
```
4. Kiểm tra sức khỏe dịch vụ:
```bash
curl http://localhost:8000/health
```

### Cách 2: Chạy Local (Không Docker)
Yêu cầu cài đặt Python 3.11+.

1. Tạo virtual environment và kích hoạt:
```bash
python -m venv .venv
.venv\Scripts\activate
```
2. Cài đặt các thư viện:
```bash
pip install -r requirements.txt
```
3. Chạy ứng dụng bằng uvicorn:
```bash
uvicorn main:app --app-dir src --host 0.0.0.0 --port 8000 --reload
```

---

## 8. Hướng dẫn kiểm thử (Newman Test)
Dự án đã tích hợp sẵn Postman Collection và Environment kiểm thử hợp đồng API tự động bằng Newman.

Để chạy Newman cục bộ:
1. Đảm bảo stack Docker Compose đang chạy.
2. Cài đặt các thư viện Node.js cần thiết:
```bash
npm install
```
3. Thực thi lệnh test tự động:
```bash
npm run test:compose
```
4. Newman sẽ tự động gửi 26 assertions và xuất kết quả báo cáo trực tiếp tại terminal.
