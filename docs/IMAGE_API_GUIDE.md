# Tài Liệu Tích Hợp API: Quản Lý Hình Ảnh & Thư Mục

Tài liệu này mô tả các API endpoint để quản lý hình ảnh và thư mục, cho phép backend tương tác với AI Service để lưu trữ, truy vấn, và xử lý dữ liệu hình ảnh.

**Authentication:** Tất cả các endpoint trong tài liệu này yêu cầu xác thực qua Internal API Key, được gửi trong header của request.

---

### 1. Tổng Quan

Hệ thống quản lý hình ảnh được thiết kế để lưu trữ metadata và các vector tìm kiếm của hình ảnh trong Qdrant, trong khi file ảnh gốc được lưu trên Cloudflare R2. Các API này là cầu nối để thực hiện các tác vụ đó.

*   **Image:** Đại diện cho một file ảnh, chứa URL trên R2, metadata, và các chỉ dẫn xử lý cho AI.
*   **Folder:** Dùng để tổ chức các ảnh theo một cấu trúc logic.

---

### 2. Endpoints Quản Lý Thư Mục (Folders)

#### 2.1. Tạo Thư Mục Mới

*   **Endpoint:** `POST /companies/{company_id}/images/folders`
*   **Mô tả:** Tạo một thư mục mới để tổ chức hình ảnh.
*   **Request Body:**
    ```json
    {
      "folder_name": "Sản phẩm Mùa Hè 2025",
      "description": "Các hình ảnh cho chiến dịch quảng bá mùa hè 2025.",
      "parent_folder_id": "uuid-cua-thu-muc-cha" // Tùy chọn, cho phép tạo thư mục lồng nhau
    }
    ```
*   **Response (Success 200):**
    ```json
    {
      "success": true,
      "data": {
        "status": "success",
        "folder_id": "uuid-moi-cua-thu-muc"
      }
    }
    ```

#### 2.2. Lấy Danh Sách Thư Mục

*   **Endpoint:** `GET /companies/{company_id}/images/folders`
*   **Mô tả:** Lấy danh sách tất cả các thư mục của một công ty.
*   **Response (Success 200):**
    ```json
    {
      "success": true,
      "data": [
        {
          "id": "uuid-cua-thu-muc-1",
          "payload": {
            "folder_name": "Sản phẩm Mùa Hè 2025",
            "description": "...",
            "parent_folder_id": null,
            "created_at": "2025-07-25T10:00:00Z",
            "content_type": "folder"
          },
          "vector": null
        }
        // ... các thư mục khác
      ]
    }
    ```

#### 2.3. Cập Nhật Thông Tin Thư Mục

*   **Endpoint:** `PUT /companies/{company_id}/images/folders/{folder_id}`
*   **Mô tả:** Cập nhật tên, mô tả, hoặc thư mục cha của một thư mục đã có.
*   **Request Body:**
    ```json
    {
      "folder_name": "Updated Folder Name", // Tùy chọn
      "description": "Updated description." // Tùy chọn
    }
    ```
*   **Response (Success 200):**
    ```json
    {
      "success": true,
      "data": {
        "status": "success",
        "folder_id": "uuid-cua-thu-muc-da-cap-nhat"
      }
    }
    ```

#### 2.4. Xóa Thư Mục

*   **Endpoint:** `DELETE /companies/{company_id}/images/folders/{folder_id}`
*   **Mô tả:** Xóa một thư mục và **tất cả các hình ảnh bên trong nó**. Đây là một hành động nguy hiểm, cần có xác nhận từ người dùng.
*   **Response (Success 200):**
    ```json
    {
      "success": true,
      "message": "Folder and all images deleted successfully"
    }
    ```

---

### 3. Endpoints Quản Lý Hình Ảnh (Images)

#### 3.1. Upload và Đăng Ký Hình Ảnh

*   **Endpoint:** `POST /companies/{company_id}/images/upload`
*   **Mô tả:** Đăng ký một hình ảnh đã được upload lên R2 vào hệ thống. Có thể kèm theo chỉ dẫn để AI xử lý trong nền.
*   **Request Body:**
    ```json
    {
      "r2_url": "https://pub-....r2.dev/your-image.jpg",
      "folder_name": "Sản phẩm Mùa Hè 2025", // Tùy chọn
      "ai_instruction": "Tạo mô tả chi tiết cho sản phẩm trong ảnh và 5 từ khóa SEO.", // Tùy chọn
      "metadata": {
        "original_name": "ao-thun-mua-he.jpg",
        "tags": ["áo thun", "mùa hè", "cotton"],
        "source": "Website Campaign"
      }
    }
    ```
*   **Luồng Hoạt Động:**
    1.  Nếu `ai_instruction` được cung cấp, API sẽ trả về ngay lập tức với `status: "processing"` và đưa tác vụ xử lý AI vào hàng đợi (background task).
    2.  Nếu không, ảnh sẽ được lưu với `status: "uploaded"`.
*   **Response (Success 200):**
    ```json
    {
      "success": true,
      "data": {
        "status": "success",
        "image_id": "uuid-moi-cua-anh"
      }
    }
    ```

#### 3.2. Lấy Danh Sách Hình Ảnh (Kèm Phân Trang và Lọc)

*   **Endpoint:** `GET /companies/{company_id}/images`
*   **Mô tả:** Lấy danh sách hình ảnh với nhiều tùy chọn lọc và phân trang.
*   **Query Parameters:**
    *   `page`: Số trang (mặc định: 1).
    *   `limit`: Số lượng kết quả mỗi trang (mặc định: 50).
    *   `folder_id`: Lọc ảnh theo ID thư mục.
    *   `search`: Tìm kiếm theo tên, mô tả, alt text...
    *   `status`: Lọc theo trạng thái (`uploaded`, `processing`, `completed`, `failed`).
*   **Ví dụ:** `GET /companies/your-company/images?page=1&limit=20&status=completed`
*   **Response (Success 200):**
    ```json
    {
      "success": true,
      "data": [
        {
          "id": "uuid-cua-anh",
          "payload": {
            "r2_url": "...",
            "folder_name": "...",
            "ai_instruction": "...",
            "status": "completed",
            "metadata": { "...": "..." }
          }
        }
      ],
      "pagination": {
        "page": 1,
        "limit": 20,
        "total": 150 // Tổng số ảnh khớp với điều kiện lọc
      }
    }
    ```

#### 3.3. Cập Nhật Thông Tin Hình Ảnh

*   **Endpoint:** `PUT /companies/{company_id}/images/{image_id}`
*   **Mô tả:** Cập nhật thông tin của một ảnh. Nếu `ai_instruction` được thay đổi, hệ thống sẽ kích hoạt lại tiến trình xử lý AI.
*   **Request Body:**
    ```json
    {
      "ai_instruction": "Tạo lại mô tả tập trung vào chất liệu vải.", // Tùy chọn
      "description": "Mô tả mới do người dùng nhập.", // Tùy chọn
      "alt_text": "Áo thun cotton màu xanh.", // Tùy chọn
      "status": "archived", // Tùy chọn
      "metadata": { "tags": ["new-tag"] } // Tùy chọn
    }
    ```
*   **Response (Success 200):**
    ```json
    {
      "success": true,
      "data": {
        "status": "success",
        "image_id": "uuid-cua-anh-da-cap-nhat"
      }
    }
    ```

#### 3.4. Xóa Hình Ảnh

*   **Endpoint:** `DELETE /companies/{company_id}/images/{image_id}`
*   **Mô tả:** Xóa một ảnh khỏi hệ thống (xóa metadata và vector trong Qdrant).
*   **Response (Success 200):**
    ```json
    {
      "success": true,
      "message": "Image deleted successfully"
    }
    ```

---

### 4. Tích Hợp Với Hệ Thống Chat

Hệ thống quản lý hình ảnh đã được tích hợp với **Unified Chat System** để cung cấp khả năng trả lời bằng hình ảnh trong các cuộc hội thoại.

#### 4.1. Luồng Hoạt Động Tích Hợp

1.  **Phát Hiện Yêu Cầu Hình Ảnh:**
    *   Khi người dùng gửi tin nhắn như "cho xem ảnh sản phẩm", "không gian nhà hàng trông thế nào?", "show me the hotel rooms", hệ thống Intent Detection sẽ phát hiện `needs_images: true`.
    *   AI sẽ phân tích và trích xuất `image_query` (ví dụ: "sản phẩm", "không gian nhà hàng", "hotel rooms").

2.  **Tìm Kiếm Hình Ảnh:**
    *   `UnifiedChatService` sử dụng `AdminService.search_images_by_description()` để tìm kiếm các hình ảnh phù hợp.
    *   Tìm kiếm dựa trên vector embeddings của `image_query` so với `ai_instruction` và `description` của các hình ảnh đã lưu.

3.  **Trả Lời Với Hình Ảnh:**
    *   AI sẽ sinh ra câu trả lời văn bản kết hợp với danh sách hình ảnh liên quan.
    *   Response sẽ bao gồm trường `attachments` chứa URL hình ảnh từ R2.

#### 4.2. Cấu Trúc Response Từ Chat API

Khi hệ thống chat trả lời bằng hình ảnh, `UnifiedChatResponse` sẽ có cấu trúc như sau:

```json
{
  "response": "Đây là một số hình ảnh về sản phẩm áo thun mùa hè của chúng tôi. Các sản phẩm này được làm từ chất liệu cotton cao cấp...",
  "intent": "information",
  "confidence": 0.95,
  "language": "vi",
  "attachments": [
    {
      "type": "image",
      "url": "https://pub-....r2.dev/ao-thun-mua-he-1.jpg",
      "description": "Áo thun cotton nam màu xanh navy, thiết kế basic",
      "alt_text": "Áo thun cotton màu xanh",
      "metadata": {
        "image_id": "uuid-anh-1",
        "folder_name": "Sản phẩm Mùa Hè 2025",
        "score": 0.89
      }
    },
    {
      "type": "image", 
      "url": "https://pub-....r2.dev/ao-thun-mua-he-2.jpg",
      "description": "Áo thun cotton nữ màu hồng pastel, form fitted",
      "alt_text": "Áo thun cotton màu hồng",
      "metadata": {
        "image_id": "uuid-anh-2",
        "folder_name": "Sản phẩm Mùa Hè 2025", 
        "score": 0.85
      }
    }
  ],
  "session_id": "session-123",
  "timestamp": "2025-07-25T15:30:00Z"
}
```

#### 4.3. Các Trigger Keywords Cho Hình Ảnh

Hệ thống sẽ tự động phát hiện các yêu cầu hình ảnh khi người dùng sử dụng:

**Tiếng Việt:**
*   "cho xem", "cho tôi xem", "xem ảnh", "hình ảnh"
*   "trông như thế nào", "như nào", "ra sao"
*   "không gian", "design", "thiết kế", "mẫu"
*   "sản phẩm", "dịch vụ", "món ăn", "phòng"

**Tiếng Anh:**
*   "show me", "let me see", "pictures", "images", "photos"
*   "what does it look like", "how does it look"
*   "space", "design", "sample", "model"
*   "products", "services", "rooms", "food"

#### 4.4. Best Practices Cho Backend

1.  **Xử Lý Attachments:**
    *   Khi nhận response từ chat API, kiểm tra trường `attachments`.
    *   Hiển thị hình ảnh cùng với text response để tạo trải nghiệm phong phú.

2.  **Caching Hình Ảnh:**
    *   Có thể cache các hình ảnh thường được truy cập để tăng tốc độ tải.
    *   R2 URLs có thể được CDN để tối ưu hiệu suất.

3.  **Fallback:**
    *   Nếu không tìm thấy hình ảnh phù hợp, AI vẫn trả lời bằng text và gợi ý liên hệ để xem thêm hình ảnh.

---

### 5. Lưu Ý Bảo Mật & Hiệu Suất

*   **Authentication:** Tất cả endpoints yêu cầu Internal API Key.
*   **File Size:** Khuyến nghị giới hạn kích thước file ảnh upload (ví dụ: tối đa 10MB).
*   **Rate Limiting:** Backend nên implement rate limiting để tránh spam requests.
*   **Vector Search:** Tìm kiếm hình ảnh sử dụng embeddings, hiệu suất phụ thuộc vào chất lượng `ai_instruction` và `description`.
