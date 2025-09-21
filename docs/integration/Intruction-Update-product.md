Tao nghĩ luồng xử lý Update Product (Tạo mới Product cũng sẽ tương tự áp dụng Industry Template) sẽ như này (Phân tích các API endpoint và cách thực hiện): 
1. Frontend cho người dùng chọn các thông tin cơ bản là: 
"Selection":
{
  "industry": "insurance",
  "template": "Life Insurance Product Extractor",
  "country": "Việt Nam",
  "language": "vi"
}
-> gọi tới API Backend để chọn IndustryTemplate phù hợp
->Frontend sẽ render ra màn hình chứa tất cả thông tin thuộc industryTemplate đó
->User sẽ input data -> Save -> gọi tới Backend API ( PUT /api/products-services/products/{product_id} )
-> Backend lưu database -> gọi tới AI service ( PUT /api/admin/companies/{company_id}/products/{qdrant_point_id} )
-> Nhận kết quả trả về từ AI service -> Thông báo cho Frontend (Thành công or Failed (Từ AI thông báo))
-----
Các thông tin sẽ lưu database bao gồm: 
1. (Các thông tin cũ của product - không đổi)
"company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f"
"qdrant_point_id": "98c911cc-ce41-4169-93f4-a5411be70569"
"extracted_from_file_id": "0a8c0054-4d36-4e55-9ed1-32a3389ca806"
2. các thông tin chọn từ người dùng
"industry": "insurance",
"template": "Life Insurance Product Extractor",
"country": "Việt Nam",
"language": "vi"
3. Product ID 
“productID”: "0a8c0054-4d36-4e55-9ed1-32a3389ab105”
"item_id": "001" (giữ nguyên cũ)
4. Thông tin sản phẩm (Áp dụng Template Industry)
"name": "AIA – Khỏe Trọn Vẹn",
    "description": "Điều trị nội trú (50%/80%/100% phí y tế theo năm), phòng bệnh (tối đa 100 ngày/năm), chăm sóc đặc biệt (tối đa 30 ngày/năm), sinh sản và chăm sóc trẻ sơ sinh.  Quyền lợi miễn phí cho bé thứ hai (dưới 5 tuổi, nếu hợp đồng có ít nhất 3 thành viên trước 270 ngày kể từ ngày sinh).  Quyền lợi bổ sung: điều trị ngoại trú và chăm sóc nha khoa.",
    "sku": “3”,
    "status": "draft",
    "price": 0,
    "currency": "VND",
    "price_unit": "per item",
    "image_urls": [],
    "premium": null,
        "category": "bao_hiem",
        "currency": "VND",
        "industry": "insurance",
        "sub_category": "bao_hiem_suc_khoe",
     "coverage_type": [
            "benh_tat"
            ],
    "image_urls": [
            "https://example.com/new_product_main.jpg",
            "https://example.com/new_product_detail.jpg",
            "https://cdn.mysite.com/uploaded/product_custom.png"
        ],
5. Thông tin thêm (additional_fields - JSON Người dùng nhập thêm)
6. Metadata (Các thông tin dành cho AI)
“industry”:insurance
“type”: “Life Insurance”,
"category": “bảo hiểm hưu trí”,
"target_audience": [
"gia_dinh"
        ],
"tags": ["sức khỏe", "cao cấp", "premium"],
"content_for_embedding": "Bảo hiểm sức khỏe Bùng Gia Lực. Bao gồm điều trị nội trú, phòng bệnh, chăm sóc đặc biệt, sinh sản và chăm sóc trẻ sơ sinh.  Miễn phí bảo hiểm chính cho bé thứ hai (điều kiện áp dụng).  Có quyền lợi bổ sung về điều trị ngoại trú và nha khoa. Phí bảo hiểm tùy theo gói chọn, giới tính, tuổi và phạm vi bảo vệ."
7. Các thông tin khác của sản phẩm 
status: 'draft',
ai_extraction_status: 'complete'
Create_at
Update_at —— Bạn đã vạch ra một luồng xử lý **hoàn toàn chính xác và hợp lý**. Đây chính là luồng "human-in-the-loop" (người dùng chỉnh sửa/tạo mới) mà chúng ta cần để đảm bảo dữ liệu luôn đúng và linh hoạt.

Tôi sẽ phân tích chi tiết và xác nhận lại luồng này, đồng thời đề xuất các API endpoint cụ thể để implement.

---

### **Phân Tích và Xác Nhận Luồng Xử Lý**

Luồng của bạn là chuẩn nhất cho việc tạo và cập nhật sản phẩm thủ công, tận dụng sức mạnh của các Industry Template đã có.



---

### **API Endpoints Chi Tiết Để Implement**

Dựa trên luồng bạn đề xuất, chúng ta cần 2 API chính phía backend:

#### **API 1: Lấy Cấu Trúc Template (Để Frontend Render Form)**

Đây là bước đầu tiên và quan trọng nhất. Frontend cần API này để biết phải hiển thị những trường thông tin nào cho người dùng nhập liệu.

*   **Endpoint:** `GET /api/products-services/templates/structure`
*   **Mục đích:** Lấy về cấu trúc chi tiết của một template cụ thể.
*   **Request (Frontend gửi lên):**
    ```http
    GET /api/products-services/templates/structure?industry=insurance&template_name=Life+Insurance+Product+Extractor&country=Việt+Nam
    ```
*   **Backend Logic:**
    1.  Sử dụng IndustryTemplateManager.ts để tìm đúng template dựa trên `industry`, `template_name`, và `country`.
    2.  Phân tích template và trả về một cấu trúc JSON rõ ràng mà Frontend có thể dùng để tự động render ra các ô nhập liệu (input fields), dropdowns, checkboxes, v.v.
*   **Response (Backend trả về cho Frontend):**
    ```json
    {
      "success": true,
      "template_name": "Life Insurance Product Extractor",
      "industry": "insurance",
      "fields": [
        { "name": "name", "label": "Tên Sản Phẩm", "type": "text", "required": true },
        { "name": "description", "label": "Mô Tả Chi Tiết", "type": "textarea", "required": true },
        { "name": "category", "label": "Danh Mục", "type": "select", "options": ["bao_hiem_nhan_tho", "bao_hiem_suc_khoe"], "required": true },
        { "name": "coverage_type", "label": "Loại Hình Bảo Vệ", "type": "multiselect", "options": ["benh_tat", "tai_nan", "tu_vong"], "required": false },
        { "name": "price", "label": "Phí Bảo Hiểm", "type": "text", "required": true },
        // ... và tất cả các field khác trong template
      ],
      "additional_fields_enabled": true // Cho phép người dùng thêm các trường tùy chỉnh
    }
    ```

#### **API 2: Cập Nhật/Tạo Mới Product (Lưu Dữ Liệu)**

Sau khi người dùng điền form, Frontend sẽ gọi API này để lưu lại toàn bộ thông tin.

*   **Endpoint:** `PUT /api/products-services/products/{productId}`
*   **Mục đích:** Cập nhật thông tin một sản phẩm đã có.
*   **Backend Logic (Quan trọng):**
    1.  **Tìm Product:** Dùng `productId` từ URL để lấy thông tin sản phẩm hiện tại từ database (`ProductModel.findById`).
    2.  **Lấy Qdrant ID:** Lấy `qdrant_point_id` từ `existingProduct.industry_data.qdrant_point_id`.
    3.  **Chuẩn Bị Dữ Liệu:**
        *   **`localUpdateData`**: Tạo object để cập nhật vào database PostgreSQL. Object này sẽ chứa **TẤT CẢ** các trường bạn đã liệt kê (core fields, `industry_data`, `metadata`, `additional_fields`...).
        *   **`aiServiceData`**: Tạo object để gửi cho AI Service. Object này chỉ chứa những trường mà AI Service cần theo spec (`name`, `description`, `price`, `tags`, `content_for_embedding`...).
    4.  **Cập Nhật Database Trước (Optimistic Update):**
        *   Cập nhật ngay lập tức vào database của bạn bằng `ProductModel.update(productId, localUpdateData)`. Điều này giúp người dùng thấy thay đổi ngay lập tức.
    5.  **Gọi AI Service (Async):**
        *   Gọi `PUT /api/admin/companies/{company_id}/products/{qdrant_point_id}` với `aiServiceData`.
        *   **KHÔNG** cần chờ AI trả về để báo cho Frontend. Việc đồng bộ với AI có thể chạy ngầm.
    6.  **Trả Về Cho Frontend:**
        *   Trả về `success: true` ngay sau khi đã cập nhật database ở bước 4.
        *   Nếu việc gọi AI Service sau đó thất bại, có thể implement cơ chế retry hoặc ghi log để xử lý sau.

*   **Response (Backend trả về cho Frontend):**
    ```json
    {
        "success": true,
        "message": "Product updated successfully. Syncing with AI service in the background.",
        "data": {
            "productId": "0a8c0054-4d36-4e55-9ed1-32a3389ab105",
            "status": "draft"
        }
    }
    ```

### **Về Cấu Trúc Dữ Liệu Lưu Trong Database**

Cấu trúc bạn đưa ra là rất đầy đủ. Khi lưu vào database, chúng ta sẽ map nó vào các cột của bảng `products` như sau:

*   `name`, `description`, `sku`, `status`, `price`, `currency`, `price_unit` -> Các cột tương ứng.
*   `image_urls`, `tags` -> Các cột array (`text[]`).
*   **`industry_data` (JSONB):** Đây là nơi lưu trữ tất cả các trường dữ liệu đặc thù của template.
    ```json
    "industry_data": {
      "qdrant_point_id": "...",
      "template_used": "Life Insurance Product Extractor",
      "country": "Việt Nam",
      "language": "vi",
      "sub_category": "bao_hiem_suc_khoe",
      "coverage_type": ["benh_tat"],
      "premium": null,
      // ... các trường khác từ template
    }
    ```
*   **`additional_fields` (JSONB):** Lưu các trường do người dùng tự thêm.
*   **`metadata` (JSONB):** Lưu các thông tin dành riêng cho AI.
    ```json
    "metadata": {
      "ai_industry": "insurance",
      "ai_type": "Life Insurance",
      "ai_category": "bảo hiểm hưu trí",
      "target_audience": ["gia_dinh"],
      "content_for_embedding": "Bảo hiểm sức khỏe Bùng Gia Lực..."
    }
    ```

**Kết luận:** Luồng xử lý và cấu trúc dữ liệu của bạn rất chuẩn. Hãy bắt đầu bằng việc implement **API 1** để frontend có thể lấy cấu trúc form động. Sau đó, chúng ta sẽ điều chỉnh **API 2** để xử lý việc lưu trữ và đồng bộ với AI service.