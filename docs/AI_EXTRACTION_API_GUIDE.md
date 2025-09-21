Luồng xử lý của endpoint @router.post("/process") trong file extraction_routes.py và ai_extraction_service.py.

Dưới đây là phân tích và tài liệu hướng dẫn cho team backend của bạn.

Phân Tích Luồng Xử Lý và Dữ Liệu
Endpoint POST /api/extract/process hoạt động như thế nào?

Backend gửi yêu cầu chứa URL của file trên R2 và các thông tin metadata (như industry, company_id).
AI Service nhận yêu cầu, chọn một "template" trích xuất dựa trên industry.
Service sử dụng AI (Gemini hoặc ChatGPT) để đọc file (văn bản, PDF, hoặc ảnh) và trích xuất dữ liệu theo cấu trúc JSON được định nghĩa trong template đó.
Kết quả trả về bao gồm hai phần chính: raw_content (toàn bộ text thô) và structured_data (dữ liệu đã được bóc tách và phân loại thành products và services).
Dữ liệu trả về có khớp với yêu cầu của Frontend không?

Có, hoàn toàn khớp. Dữ liệu mà AI service trả về trong structured_data chứa tất cả các thông tin cần thiết. Backend sẽ cần thực hiện một bước ánh xạ đơn giản để chuyển đổi dữ liệu này thành định dạng mà Frontend yêu cầu.

structured_data: Chứa 2 danh sách chính là products và services.

Mỗi phần tử trong products là một object chứa các chi tiết như name, price, category, description, và các trường khác tùy theo ngành (industry).
Mỗi phần tử trong services cũng tương tự.
Ánh Xạ Dữ Liệu (Backend thực hiện)
Đây là cách backend sẽ xử lý response từ AI service để tạo ra dữ liệu cho Frontend:

Cột Frontend	Nguồn Dữ Liệu từ Response của AI Service	Ghi Chú cho Backend
ID	(Backend tự sinh)	Backend sẽ tự tạo ID tăng dần cho mỗi sản phẩm/dịch vụ được lưu vào database.
Name	item['name']	Lấy từ mỗi object trong list products hoặc services.
Prices	item['price']	Lấy từ mỗi object. Có thể kèm theo currency.
Information	item (toàn bộ object)	Đây chính là yêu cầu của bạn. Backend sẽ lấy toàn bộ object JSON của sản phẩm/dịch vụ và lưu lại. Khi Frontend yêu cầu, backend sẽ trả về object này để hiển thị và cho phép chỉnh sửa.
Category	item['category']	Lấy từ mỗi object. Nếu không có, để trống.
Data Type	(Backend tự xác định)	Nếu item đến từ list products, gán là "Product". Nếu từ list services, gán là "Service".
Uploaded	request.file_metadata['uploaded_at']	Backend lấy từ metadata của file mà chính backend đã gửi trong request ban đầu.
Kết luận: Luồng xử lý hiện tại đã rất hợp lý. AI Service làm đúng nhiệm vụ là trích xuất và cấu trúc hóa dữ liệu. Backend có vai trò xử lý dữ liệu này, tạo ID, và ánh xạ sang định dạng cuối cùng cho Frontend.

# Tài Liệu Tích Hợp API: Trích Xuất Dữ Liệu Sản Phẩm/Dịch Vụ

**Endpoint:** `POST /api/extract/process`
**Content-Type:** `application/json`

Tài liệu này mô tả luồng hoạt động và cấu trúc dữ liệu của API trích xuất thông tin từ file, nhằm mục đích đồng bộ hóa giữa AI Service và Backend để phục vụ cho việc hiển thị dữ liệu trên Frontend.

---

### 1. Luồng Hoạt Động Tổng Quan

1.  **Backend**: Upload một file (PDF, DOCX, TXT, JPG, PNG,...) lên Cloudflare R2.
2.  **Backend**: Sau khi có URL public của file trên R2, Backend gọi đến endpoint `POST /api/extract/process` của AI Service.
3.  **AI Service**:
    *   Nhận request, phân tích `industry` để chọn template trích xuất phù hợp.
    *   Gọi đến AI Provider (Gemini/ChatGPT) để bóc tách dữ liệu từ file theo cấu trúc đã định sẵn trong template.
    *   Trả về một đối tượng JSON chứa cả nội dung thô (`raw_content`) và dữ liệu có cấu trúc (`structured_data`).
4.  **Backend**:
    *   Nhận phản hồi từ AI Service.
    *   Lưu trữ `raw_content` để hiển thị ở màn hình quản lý file upload.
    *   **Duyệt qua danh sách `products` và `services` trong `structured_data`**. Với mỗi item, Backend sẽ tạo một bản ghi mới trong database của mình để cung cấp cho Frontend.

---

### 2. Cấu Trúc Request Body (Backend -> AI Service)

Backend cần gửi request với cấu trúc như sau:

```json
{
  "r2_url": "https://pub-....r2.dev/your-file.pdf",
  "company_id": "your-company-uuid",
  "industry": "restaurant", // Enum: "restaurant", "real_estate", "finance", "education", "other"
  "target_categories": ["products", "services"], // Tùy chọn, nếu null sẽ tự động trích xuất cả hai
  "file_metadata": {
    "original_name": "menu_nha_hang.pdf",
    "file_size": 1024000,
    "file_type": "application/pdf",
    "uploaded_at": "2025-07-24T10:00:00Z" // Backend tự quản lý
  },
  "company_info": { // Tùy chọn, cung cấp thêm ngữ cảnh cho AI
    "id": "golden-dragon-restaurant",
    "name": "Golden Dragon Restaurant",
    "description": "Nhà hàng chuyên các món Việt Nam"
  },
  "upload_to_qdrant": false, // Mặc định là false
  "callback_url": null // Tùy chọn
}
```

---

### 3. Cấu Trúc Response Body (AI Service -> Backend)

AI Service sẽ trả về cấu trúc `ExtractionResponse` như sau:

```json
{
  "success": true,
  "message": "Auto-categorization extraction completed successfully",
  "raw_content": "Toàn bộ nội dung text được trích xuất từ file...",
  "structured_data": {
    "products": [
      {
        "name": "Vịt quay Hong Kong",
        "price": 260000,
        "currency": "VND",
        "category": "Món chính",
        "description": "Vịt quay da giòn, tẩm ướp theo công thức gia truyền."
      },
      {
        "name": "Cơm chiên Dương Châu",
        "price": 85000,
        "currency": "VND",
        "category": "Cơm & Mì",
        "description": "Cơm chiên với lạp xưởng, tôm, và rau củ."
      }
    ],
    "services": [
      {
        "name": "Giao hàng tận nơi",
        "service_type": "delivery",
        "pricing": "Miễn phí cho đơn hàng trên 500K",
        "availability": "Trong bán kính 5km"
      }
    ],
    "extraction_summary": {
      "total_products": 2,
      "total_services": 1,
      "data_quality": "high",
      "categorization_notes": "Items were categorized based on menu sections.",
      "industry_context": "Standard restaurant menu items."
    }
  },
  "template_used": "RestaurantTemplate",
  "ai_provider": "gemini-1.5-pro-latest",
  "processing_time": 15.7
}
```

**Lưu ý quan trọng:** Cấu trúc của các object bên trong `products` và `services` sẽ **thay đổi tùy theo `industry`**. Ví dụ, ngành tài chính sẽ có các trường như `interest_rate`, `loan_term` thay vì `price`, `description`.

---

### 4. Ánh Xạ Dữ Liệu cho Frontend (Backend Thực Hiện)

Backend sẽ dựa vào `ExtractionResponse` để tạo dữ liệu cho Frontend theo các cột sau:

Đây là cách backend sẽ xử lý response từ AI service để tạo ra dữ liệu cho Frontend:
Cột Frontend	Nguồn Dữ Liệu từ Response của AI Service	Ghi Chú cho Backend
ID	(Backend tự sinh)	Backend sẽ tự tạo ID tăng dần cho mỗi sản phẩm/dịch vụ được lưu vào database.
Name	item['name']	Lấy từ mỗi object trong list products hoặc services.
Prices	item['price']	Lấy từ mỗi object. Có thể kèm theo currency.
Information	item (toàn bộ object)	Đây chính là yêu cầu của bạn. Backend sẽ lấy toàn bộ object JSON của sản phẩm/dịch vụ và lưu lại. Khi Frontend yêu cầu, backend sẽ trả về object này để hiển thị và cho phép chỉnh sửa.
Category	item['category']	Lấy từ mỗi object. Nếu không có, để trống.
Data Type	(Backend tự xác định)	Nếu item đến từ list products, gán là "Product". Nếu từ list services, gán là "Service".
Uploaded	request.file_metadata['uploaded_at']	Backend lấy từ metadata của file mà chính backend đã gửi trong request ban đầu.

