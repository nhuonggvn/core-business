Biên bản đàm phán hợp đồng Sự kiện (Event Contract)
## Cặp đàm phán: Pair 05 — IoT Ingestion (A1/B1) ↔ Core Business (A6/B6)

- **Cơ chế**: Queue async
- **Publisher (Producer)**: IoT Ingestion (A1)
- **Subscriber (Consumer)**: Core Business (A6)
- **Phiên**: v1.0
- **Ngày**: 01-06-2026

---

## Issue #1: Tiêu chuẩn hóa hệ thống đơn vị đo lường (Metric Units)

- **Raised by**: Subscriber (Core Business)
- **Endpoint/Event**: `sensor.reading.created` & `sensor.threshold.exceeded`
- **Concern**: IoT Ingestion thu thập dữ liệu từ các cảm biến phần cứng của nhiều hãng sản xuất khác nhau, dẫn tới dữ liệu nhiệt độ có thể là độ Celsius (°C) hoặc Fahrenheit (°F), dữ liệu độ ẩm có thể là tỷ lệ phần trăm (0-100) hoặc số thực (0.0-1.0). Nếu gửi lung tung, Core Business sẽ không thể đánh giá chính xác các chính sách vận hành khẩn cấp trong Policy Engine.
- **Proposal**: Subscriber đề xuất bắt buộc chuẩn hóa toàn bộ giá trị đo lường (`value`) về hệ đo lường quốc tế (SI) cụ thể: `CELSIUS` cho nhiệt độ, `PERCENTAGE` (0.0-100.0) cho độ ẩm/khói, `PASCAL` cho áp suất, và `LUX` cho ánh sáng. Định dạng này phải được ghi nhận rõ trong trường `unit`.
- **Resolution**: Accepted
- **Rationale**: Đảm bảo tính nhất quán tuyệt đối của dữ liệu đầu vào, giúp bộ lọc quy tắc (Policy Engine) của Core Business tính toán nhanh chóng mà không mất tài nguyên convert đơn vị.
- **Impact**:
  - **IoT Ingestion**: Thực hiện chuyển đổi đơn vị ở tầng Gateway/Adapter trước khi đóng gói payload gửi lên hàng đợi.
  - **Core Business**: Định nghĩa Enum cho trường `unit` và xây dựng logic xử lý theo hệ đo lường chuẩn hóa.

---

## Issue #2: Yêu cầu định danh vị trí vật lý (`locationId`)

- **Raised by**: Subscriber (Core Business)
- **Endpoint/Event**: Cả hai sự kiện
- **Concern**: Thiết kế payload ban đầu của IoT Ingestion chỉ chứa `deviceId` và chỉ số đo được. Tuy nhiên, Core Business cần biết cảm biến đó đang được lắp đặt ở phòng học, hành lang hay tầng mấy để kích hoạt các kịch bản an ninh tương ứng (như mở/đóng cửa thoát hiểm của tòa nhà đó khi có cháy). Nếu chỉ có `deviceId`, Core Business sẽ phải truy vấn thêm DB để phân tích vị trí, gây trễ thời gian phản hồi.
- **Proposal**: Subscriber yêu cầu IoT Ingestion đính kèm thuộc tính `locationId` (kiểu chuỗi định danh vị trí) trực tiếp vào trong payload của mỗi sự kiện.
- **Resolution**: Accepted
- **Rationale**: Việc đính kèm `locationId` giúp Core Business xử lý logic tại chỗ (In-memory Rule Processing) cực kỳ nhanh chóng mà không cần thực hiện thêm các thao tác JOIN database đắt đỏ trong luồng realtime khẩn cấp.
- **Impact**:
  - **IoT Ingestion**: Bổ sung cơ chế làm giàu dữ liệu (Data Enrichment) tại tầng Ingestion để đính kèm `locationId` tương ứng với `deviceId` trước khi publish event.
  - **Core Business**: Cập nhật logic xử lý sự kiện để trích xuất trực tiếp `locationId` phục vụ Policy Engine.

---

## Issue #3: Giới hạn độ trễ xử lý thông điệp khẩn cấp (Event TTL)

- **Raised by**: Subscriber (Core Business)
- **Endpoint/Event**: Cả hai sự kiện
- **Concern**: Trong trường hợp Broker bị tắc nghẽn hoặc mất kết nối mạng cục bộ, các thông điệp có thể bị kẹt trong hàng đợi nhiều giờ. Khi mạng thông suốt, broker sẽ tự động đẩy hàng loạt thông điệp cũ lên Consumer. Nếu Core Business xử lý các sự kiện khẩn cấp cũ này (như báo khói cũ cách đây 2 tiếng), nó có thể kích hoạt các cảnh báo giả, hú còi và khóa cửa campus không đúng thời điểm hiện tại.
- **Proposal**: Subscriber đề xuất áp dụng luật TTL (Time-To-Live): Nếu thời gian nhận sự kiện trễ hơn quá **5 phút** so với thời điểm xảy ra sự kiện (`occurredAt`), Core Business sẽ ghi log cảnh báo và bỏ qua việc kích hoạt kịch bản khẩn cấp.
- **Resolution**: Accepted with Modification
- **Rationale**: Bảo vệ hệ thống Smart Campus khỏi các quyết định an ninh sai lệch do dữ liệu cũ (stale data), đồng thời vẫn lưu trữ thông tin phục vụ mục đích kiểm toán (audit log) và phân tích lịch sử sau này.
- **Impact**:
  - **Core Business**: Cấu hình logic lọc sự kiện: So sánh `timestamp_hiện_tại - occurredAt`. Nếu > 300 giây, bỏ qua xử lý Policy Engine, chỉ lưu DB kiểm toán.

---

## Ký kết đồng thuận Pair 05 (v1.0)

- **Publisher sign-off**: Nguyễn Tuấn Anh (Đại diện nhóm A1 IoT Ingestion)
- **Subscriber sign-off**: Nguyễn Thị Hồng Duyên (Đại diện nhóm A6 Core Business)
- **Witness (GV/TA)**: Lê Thái Bảo
- **Date**: 01-06-2026


## Cặp đàm phán: Pair 03 — Access Gate (A3/B3) ↔ Core Business (A6/B6)

- **Cơ chế**: REST sync
- **Publisher (Producer)**: Access Gate (A3)
- **Subscriber (Consumer)**: Core Business (A6)
- **Phiên**: v1.0
- **Ngày**: 02-06-2026

## Issue #1: Cơ chế Phân trang cho Endpoint `/access/logs/recent` (Pair 03)

- Raised by: Consumer (Core Business)
- Endpoint: `GET /access/logs/recent`
- Concern: Lượng sinh viên quẹt thẻ ra vào Campus hàng ngày là cực kỳ lớn. Nếu dùng phân trang truyền thống bằng Offset (`page`/`limit`), hệ thống sẽ bị chậm (vấn đề Performance) ở các trang phía sau và có nguy cơ bỏ sót hoặc lặp log nếu có bản ghi mới chèn vào liên tục.
- Proposal: Áp dụng cơ chế phân trang dựa trên con trỏ (Cursor-based pagination) bằng một chuỗi mã hóa an toàn.
- Resolution: Accepted. Hai bên thống nhất sử dụng query parameter `cursor` (kiểu chuỗi mã hóa Base64 chứa ID của bản ghi cuối cùng và mốc thời gian) và tham số giới hạn `limit` (tối đa 100 bản ghi/request). Response trả về bắt buộc bao gồm mảng `data` và trường `nextCursor`.
- Rationale: Cursor-based pagination giúp tối ưu hóa truy vấn cơ sở dữ liệu ở biên (Edge), tốc độ phản hồi ổn định $O(1)$ bất kể độ sâu của trang dữ liệu, đồng thời tránh trùng lặp bản ghi khi kéo stream log liên tục.
- Impact: Phía Access Gate phải cấu hình logic sinh con trỏ Base64 từ bản ghi cuối cùng. Core Business phải lưu lại `nextCursor` nhận được từ request trước để truyền vào query param cho request kế tiếp.

---

## Issue #2: Cấu trúc Dữ liệu Định danh Thẻ và Ràng buộc Định dạng (Pair 03 & 10)

- Raised by: Provider (Access Gate)
- Endpoint: `GET /cards/{cardId}`, `POST /access/check`, `GET /access/logs/recent`
- Concern: Thiết bị phần cứng (Đầu đọc RFID, máy quét QR) thu thập dữ liệu thẻ dưới dạng chuỗi ký tự Alphanumeric hoặc mã Hex (ví dụ: RFID88776655). Nếu hệ thống Core Business thiết kế trường này dạng số nguyên tự tăng (Integer ID) hoặc chuỗi tự do không kiểm soát sẽ gây lỗi phân rã dữ liệu (Parse error) tại biên.
- Proposal: Thống nhất kiểu dữ liệu của `cardId` là `string` cố định kèm theo định nghĩa biểu thức chính quy (Regex Pattern) nghiêm ngặt trong JSON Schema.
- Resolution: Accepted. Trường `cardId` được chốt là kiểu chuỗi (`type: string`) với ràng buộc Pattern: `^[A-Z0-9]{8,16}$`.
- Rationale: Giúp sàng lọc dữ liệu lỗi ngay từ tầng API Gateway (bằng Spectral/Prism hoặc Validator) trước khi truyền sâu vào hệ thống Core xử lý, bao quát được nhiều loại thẻ vật lý (Mã QR, chip RFID, Barcode).
- Impact: Cả hai đội phát triển phải cập nhật cấu trúc cơ sở dữ liệu để lưu trữ mã thẻ dưới dạng String trường độ từ 8 đến 16 ký tự viết hoa/số.

## Ký kết đồng thuận Pair 03 
- **Publisher sign-off**: Đặng Văn Thanh(Đại diện nhóm A3 Access Gate)
- **Subscriber sign-off**: Trần Công Thưởng (Đại diện nhóm A6 Core Business)
- **Witness (GV/TA)**: Lê Thái Bảo
- **Date**: 02-06-2026

## Cặp đàm phán: Pair 08 — Analytics (A5/B5) ↔ Core Business (A6/B6)

- **Cơ chế**: Queue async
- **Publisher (Producer)**: Core Business (A6)
- **Subscriber (Consumer)**: Analytics (A5)
- **Phiên**: v1.0
- **Ngày**: 03-06-2026

## Issue đàm phán với Core Business (A6)
- **Raised by:** Provider (Analytics - A5)
- **Endpoint:** Topic `core.alert.published`
- **Concern:** Analytics cần biết mức độ nghiêm trọng để phân loại KPI cảnh báo trên Dashboard.
- **Proposal:** Nhóm A6 (Core) bắt buộc cung cấp trường `severity` với tập giá trị Enum: `[LOW, MEDIUM, HIGH, CRITICAL]`.
- **Resolution:** Accepted
- **Rationale:** Đảm bảo Analytics có đủ dữ liệu để tính toán KPI vận hành và hiển thị biểu đồ phân loại sự cố chính xác.
- **Impact:** Nhóm A6 bổ sung ràng buộc dữ liệu tại tầng phát sự kiện.

## Issue thống nhất chuẩn định dạng thời gian (Cả 2 nhóm)
- **Concern:** Sai lệch múi giờ gây lỗi timeline trên biểu đồ thống kê KPI.
- **Proposal:** Thống nhất định dạng `occurredAt` theo chuẩn ISO 8601, múi giờ UTC (đuôi Z).
- **Resolution:** Accepted
- **Rationale:** Giúp hệ thống Analytics sắp xếp thứ tự sự cố (Ordering) chính xác tuyệt đối.
- **Impact:** Nhóm A6 đồng ý format lại timestamp trước khi gửi tin nhắn vào Queue.

**Provider sign-off:** Nguyễn Hữu Tuấn Minh (Leader A5)
**Consumer sign-off:** Trần Công Thưởng (A6)

## Ký kết đồng thuận Pair 08

- **Publisher sign-off**: Nguyễn Hữu Tuấn Minh (Đại diện nhóm A5 Analytics)
- **Subscriber sign-off**: Trần Công Thưởng (Đại diện nhóm A6 Core Business)
- **Witness (GV/TA)**: Lê Thái Bảo
- **Date**: 03-06-2026

# BIÊN BẢN ĐÀM PHÁN HỢP ĐỒNG API

**Provider:** A7 – Notification Service
**Consumer:** A6 – Core Business Service
**Phiên bản:** v1.0
**Ngày:** [4/6/2026]

---

## Issue #1

**Đề xuất bởi:** Consumer

**Endpoint:** POST /events/alert.created

**Vấn đề:**
Consumer chưa rõ trường `severity` có bắt buộc hay không và các giá trị hợp lệ là gì.

**Đề xuất:**
Quy định `severity` là trường bắt buộc với các giá trị chuẩn:

* LOW
* MEDIUM
* HIGH
* CRITICAL

**Kết quả:**
Accepted (Chấp nhận)

**Lý do:**
Mức độ nghiêm trọng của cảnh báo giúp Notification Service xác định mức ưu tiên và lựa chọn phương thức gửi phù hợp.

**Tác động:**
Consumer phải kiểm tra và cung cấp giá trị `severity` hợp lệ trước khi gửi sự kiện.

---

## Issue #2

**Đề xuất bởi:** Consumer

**Endpoint:** POST /events/alert.created

**Vấn đề:**
Khi xảy ra lỗi mạng hoặc timeout, việc gửi lại yêu cầu có thể làm phát sinh sự kiện trùng lặp.

**Đề xuất:**
Sử dụng `eventId` làm khóa idempotency để đảm bảo cùng một sự kiện chỉ được xử lý một lần.

**Kết quả:**
Accepted (Chấp nhận)

**Lý do:**
Cho phép Consumer gửi lại yêu cầu một cách an toàn mà không tạo ra các bản ghi hoặc thông báo trùng lặp.

**Tác động:**
Provider phải kiểm tra sự tồn tại của `eventId` trước khi xử lý sự kiện.

---

## Issue #3

**Đề xuất bởi:** Provider

**Endpoint:** POST /events/alert.created

**Vấn đề:**
Consumer có thể không gửi trường `channels` trong một số trường hợp.

**Đề xuất:**
Nếu không có trường `channels`, Notification Service sẽ tự động lựa chọn kênh gửi mặc định dựa trên chính sách cấu hình của hệ thống.

**Kết quả:**
Modified (Chấp nhận có điều chỉnh)

**Lý do:**
Đảm bảo tính linh hoạt cho Consumer nhưng vẫn duy trì khả năng gửi thông báo hiệu quả.

**Tác động:**
Provider cần xây dựng cơ chế lựa chọn kênh mặc định và ghi nhận kênh đã sử dụng trong kết quả xử lý.

---

## Issue #4

**Đề xuất bởi:** Consumer

**Endpoint:** GET /events/{id}

**Vấn đề:**
Chưa có quy định thống nhất về trạng thái của sự kiện khi thực hiện tra cứu.

**Đề xuất:**
Chuẩn hóa các trạng thái xử lý như sau:

* PENDING
* PROCESSING
* SUCCESS
* FAILED

**Kết quả:**
Accepted (Chấp nhận)

**Lý do:**
Giúp Consumer dễ dàng theo dõi tiến trình xử lý của sự kiện.

**Tác động:**
Provider phải áp dụng thống nhất các giá trị trạng thái đã thỏa thuận.

---

## Issue #5

**Đề xuất bởi:** Provider

**Endpoint:** POST /events/alert.created

**Vấn đề:**
Chưa xác định rõ mã lỗi chuẩn khi dữ liệu gửi lên không hợp lệ hoặc vi phạm quy tắc nghiệp vụ.

**Đề xuất:**

* Trả về HTTP 400 Bad Request đối với lỗi sai cấu trúc hoặc không đúng schema.
* Trả về HTTP 422 Unprocessable Entity đối với lỗi nghiệp vụ.

**Kết quả:**
Accepted (Chấp nhận)

**Lý do:**
Giúp phân biệt rõ lỗi dữ liệu đầu vào và lỗi nghiệp vụ, hỗ trợ xử lý lỗi chính xác hơn.

**Tác động:**
Consumer cần triển khai xử lý riêng cho từng loại lỗi.

---

## Issue #6

**Đề xuất bởi:** Consumer

**Endpoint:** POST /events/alert.created

**Vấn đề:**
Chưa xác định rõ Notification Service xử lý theo cơ chế đồng bộ hay bất đồng bộ.

**Đề xuất:**
API chỉ xác nhận đã tiếp nhận yêu cầu, sau đó xử lý bất đồng bộ thông qua hàng đợi (Queue). Consumer có thể tra cứu trạng thái xử lý bằng endpoint:

GET /events/{id}

**Kết quả:**
Accepted (Chấp nhận)

**Lý do:**
Phù hợp với kiến trúc hướng sự kiện (Event-Driven Architecture) và giảm thời gian chờ của Consumer.

**Tác động:**
Consumer không được giả định rằng thông báo đã được gửi thành công ngay sau khi nhận phản hồi từ API mà phải kiểm tra trạng thái xử lý khi cần thiết.

## Ký kết đồng thuận Pair 04

- **Publisher sign-off**: Nguyễn Thanh Danh (Đại diện nhóm A7 Notification)
- **Subscriber sign-off**: Trần Công Thưởng (Đại diện nhóm A6 Core Business)
- **Witness (GV/TA)**: Lê Thái Bảo
- **Date**: 04-06-2026

# Biên bản đàm phán hợp đồng API

- **Cặp đàm phán**: Pair 02 — Core Business (A6/B6) ↔ AI Vision (A4/B4)
- **Product**: Product A
- **Provider**: AI Vision (A4) - Đại diện: Nguyễn Minh Mạnh
- **Consumer**: Core Business (A6) - Đại diện: Nguyễn Thị Hồng Duyên
- **Phiên**: v1.0
- **Ngày**: 05-06-2026

---

## Issue #1: Định dạng dữ liệu hình ảnh (imageUrl vs imageBase64)

- **Raised by**: Provider (AI Vision)
- **Endpoint**: `POST /vision/detect`
- **Concern**: Provider lo ngại rằng nếu gửi ảnh dạng `imageBase64` trực tiếp trong request body, kích thước request sẽ rất lớn (lên tới 10MB+ cho mỗi frame chất lượng cao), gây tải nặng cho network bandwidth và buffer bộ nhớ của server AI Vision. Provider đề xuất chỉ hỗ trợ `imageUrl` (ảnh được upload lên CDN/Object Storage dùng chung).
- **Proposal**: Consumer giải thích rằng trong một số tình huống khẩn cấp hoặc khi camera mất kết nối Internet ngoại vi, camera chỉ có thể chụp frame local và đẩy trực tiếp chuỗi Base64 lên Core Business. Do đó, Consumer đề xuất hỗ trợ cả hai: `imageUrl` (ưu tiên hàng đầu) và `imageBase64` (phương án dự phòng).
- **Resolution**: Accepted with Modification
- **Rationale**: Hai bên thống nhất sử dụng cấu trúc `oneOf` kết hợp `discriminator` với thuộc tính phân loại `imageType` (`URL` hoặc `BASE64`) trong schema `VisionDetectRequest`. Đồng thời, thiết lập giới hạn cứng kích thước chuỗi base64 tối đa là 10MB để tránh tấn công từ chối dịch vụ (DoS/Out of memory).
- **Impact**:
  - **AI Vision**: Cấu hình middleware giới hạn tối đa request body là 10MB.
  - **Core Business**: Cấu hình luồng nghiệp vụ ưu tiên upload CDN lấy `imageUrl`, chỉ sử dụng `imageBase64` khi CDN gặp sự cố.

---

## Issue #2: Cơ chế xử lý Đồng bộ (Synchronous) vs Bất đồng bộ (Asynchronous)

- **Raised by**: Consumer (Core Business)
- **Endpoint**: `POST /vision/detect`
- **Concern**: Consumer yêu cầu tốc độ phản hồi nhanh (đồng bộ) để kịp thời ra quyết định đóng/mở cổng hoặc gửi cảnh báo an ninh tức thời. Tuy nhiên, Provider giải thích rằng việc phân tích Deep Learning (như chạy YOLOv8x) có thể mất từ 200ms đến hơn 2s tùy thuộc vào tải GPU hiện tại. Nếu bắt buộc xử lý đồng bộ khi tải cao sẽ gây ra nghẽn hàng đợi request và timeout.
- **Proposal**: Consumer đề xuất thiết kế API hỗ trợ đồng thời cả hai mã trạng thái phản hồi:
  1. Trả về `201 Created` kèm kết quả nhận dạng tức thời (luồng Đồng bộ khi GPU rảnh).
  2. Trả về `202 Accepted` kèm header `Location` trỏ đến đường dẫn tra cứu kết quả (luồng Bất đồng bộ khi GPU tải cao).
- **Resolution**: Accepted
- **Rationale**: Thiết kế lai này giúp hệ thống co giãn tốt, tránh nghẽn luồng mạng khi lượng request đột biến, đồng thời đảm bảo Core Business vẫn có thể nhận kết quả nhanh nhất khi hệ thống bình thường.
- **Impact**:
  - **AI Vision**: Thiết kế thêm cơ chế background queue xử lý ngầm và sinh thêm endpoint tra cứu `GET /vision/detect/{requestId}`.
  - **Core Business**: Thiết kế Rule Engine hỗ trợ nhận kết quả tức thời (201) hoặc chuyển sang luồng Polling định kỳ (202) để lấy kết quả từ endpoint GET.

---

## Issue #3: Bổ sung tọa độ đối tượng nhận dạng (Bounding Box)

- **Raised by**: Consumer (Core Business)
- **Endpoint**: `POST /vision/detect` & `GET /vision/detect/{requestId}`
- **Concern**: Thiết kế API ban đầu của AI Vision chỉ trả về danh sách nhãn nhận diện (`type`) và độ tin cậy (`confidence`). Tuy nhiên, Consumer cần vẽ lại khung nhận dạng trên Dashboard của Admin để làm bằng chứng an ninh trực quan (đặc biệt là vùng xâm nhập trái phép hoặc khuôn mặt đối tượng lạ).
- **Proposal**: Consumer yêu cầu Provider bổ sung thêm thông tin tọa độ và kích thước khung giới hạn (`boundingBox`) cho mỗi đối tượng nhận dạng được.
- **Resolution**: Accepted
- **Rationale**: Việc hiển thị trực quan Bounding Box là tính năng cực kỳ quan trọng đối với Dashboard giám sát, giúp tăng trải nghiệm người dùng và độ chính xác khi kiểm chứng an ninh.
- **Impact**:
  - **AI Vision**: Trích xuất thêm thông tin tọa độ `x`, `y`, `width`, `height` từ output của model AI và định nghĩa schema `BoundingBox` trong response.
  - **Core Business**: Cập nhật Processing DB để lưu trữ thông tin tọa độ này.

---

## Issue #4: Chuẩn hóa định dạng phản hồi lỗi (Problem Details - RFC 7807)

- **Raised by**: Consumer (Core Business)
- **Endpoint**: Tất cả endpoints
- **Concern**: Consumer muốn có một cấu trúc phản hồi lỗi thống nhất và giàu ngữ cảnh để dễ dàng xử lý tự động trong code và hiển thị chi tiết lỗi cho quản trị viên, thay vì mỗi lỗi trả về một kiểu (nhuy plain text hoặc JSON thiếu cấu trúc).
- **Proposal**: Consumer đề xuất áp dụng chuẩn **Problem Details (RFC 7807)** với định dạng Content-Type là `application/problem+json` cho toàn bộ mã lỗi `4xx` và `5xx`.
- **Resolution**: Accepted
- **Rationale**: Đảm bảo tính chuyên nghiệp và đồng bộ trên toàn bộ kiến trúc Smart Campus Platform.
- **Impact**:
  - **Cả hai bên**: Thống nhất cấu trúc schema `Problem` bao gồm các trường: `type` (URI lỗi), `title` (tiêu đề lỗi), `status` (HTTP code), `detail` (mô tả lỗi chi tiết), `instance` (URI xảy ra lỗi) và mảng `errors` (danh sách lỗi chi tiết ở từng field cụ thể).

---

## Issue #5: Chống trùng lặp yêu cầu xử lý (Idempotency)

- **Raised by**: Provider (AI Vision)
- **Endpoint**: `POST /vision/detect`
- **Concern**: Khi kết nối mạng chập chờn hoặc xảy ra hiện tượng timeout giả, Core Business có thể tự động gửi lại (retry) cùng một yêu cầu phân tích. Nếu không chống trùng lặp, AI Vision sẽ phải chạy model phân tích lại từ đầu trên cùng một frame ảnh, gây lãng phí tài nguyên GPU cực kỳ lớn.
- **Proposal**: Provider yêu cầu Consumer bắt buộc phải tạo và đính kèm một ID duy nhất (`requestId` định dạng UUID) cho mỗi frame ảnh gửi lên. AI Vision sẽ dựa vào ID này để cache và kiểm tra trùng lặp.
- **Resolution**: Accepted
- **Rationale**: Bảo vệ tài nguyên GPU của hệ thống tránh quá tải vô ích bởi các request retry lặp lại từ phía Consumer.
- **Impact**:
  - **Core Business**: Đảm bảo sinh chuỗi UUID ngẫu nhiên duy nhất cho mỗi yêu cầu phân tích mới và truyền vào trường `requestId`.
  - **AI Vision**: Cấu hình cache kiểm tra `requestId`. Nếu request trùng lặp đang được xử lý, trả về mã lỗi `409 Conflict`. Nếu đã xử lý xong từ trước, trả về trực tiếp kết quả đã lưu trong database mà không cần chạy lại model AI.

---

## Issue #6: Đồng bộ hóa nhãn nhận dạng (Labels) và phiên bản Model AI

- **Raised by**: Consumer (Core Business)
- **Endpoint**: `GET /vision/models`
- **Concern**: AI Vision liên tục nâng cấp các phiên bản model nhận dạng (ví dụ từ YOLOv8 lên YOLOv9) dẫn đến việc thay đổi hoặc bổ sung thêm các nhãn nhận diện mới (như thêm nhãn `WEAPON` hoặc `FIRE`). Nếu Core Business không biết trước điều này, Rule Engine có thể xử lý sai hoặc bỏ qua các cảnh báo nguy hiểm do chưa được cấu hình nhãn tương ứng.
- **Proposal**: Consumer đề xuất AI Vision cung cấp một endpoint trả về danh sách các model AI đang chạy kèm theo phiên bản của chúng. Đồng thời, trong kết quả phân tích ảnh bắt buộc phải đính kèm trường thông tin `modelVersion`.
- **Resolution**: Accepted
- **Rationale**: Giúp Core Business tự động kiểm soát tính tương thích và cập nhật các cấu hình quy tắc (Rule Engine) một cách chủ động mà không cần can thiệp thủ công vào code khi AI Vision cập nhật model.
- **Impact**:
  - **AI Vision**: Triển khai thêm endpoint `/vision/models` trả về thông tin chi tiết của các model đang kích hoạt và bổ sung trường `modelVersion` vào schema `VisionDetectResult`.
  - **Core Business**: Sử dụng thông tin phiên bản model để ghi log kiểm toán (audit log) và đưa ra quyết định cảnh báo phù hợp.

---

# Chốt hợp đồng v1.0

- **Provider sign-off**: Nguyễn Minh Mạnh (Đại diện nhóm A4 AI Vision)  
- **Consumer sign-off**: Nguyễn Thị Hồng Duyên (Đại diện nhóm A6 Core Business)  
- **Witness (GV/TA)**: Lê Thái Bảo  
- **Date**: 05-06-2026  