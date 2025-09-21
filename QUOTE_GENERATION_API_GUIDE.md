# Hướng Dẫn Frontend: Tích Hợp Tính Năng Tạo Báo Giá

Tài liệu này mô tả chi tiết luồng hoạt động và các API endpoints cần thiết để tích hợp tính năng tạo báo giá tự động bằng AI.

## 1. Xác Thực (Authentication)

Tất cả các endpoint được liệt kê dưới đây đều yêu cầu xác thực. Frontend **PHẢI** gửi một `session_cookie` (ưu tiên, hiệu lực 24 giờ) hoặc `id_token` (hiệu lực 1 giờ) trong `Authorization` header.

**Header Mẫu:**
```json
{
  "Authorization": "Bearer <your_session_cookie_or_id_token>",
  "Content-Type": "application/json"
}
```

## 2. Luồng Hoạt Động (Workflow)

Đây là luồng hoạt động chuẩn gồm 3 bước mà frontend phải tuân theo:

1.  **Bước 1: Lấy Dữ Liệu Cũ & Cấu Hình (Setup Form)**
    - **Mục đích:** Giảm thiểu việc nhập liệu cho người dùng.
    - **Hành động:** Khi vào trang, gọi `GET /api/quotes/user-data`. API này sẽ trả về cấu hình gần nhất người dùng đã lưu. Dùng dữ liệu này để điền sẵn vào form.
    - **Kết quả:** Người dùng thấy form đã được điền sẵn thông tin, chỉ cần chỉnh sửa nếu cần.

2.  **Bước 2: Lưu Cấu Hình (Save Settings)**
    - **Mục đích:** Lưu thông tin công ty, khách hàng, và điều khoản thanh toán.
    - **Hành động:** Sau khi người dùng điền/chỉnh sửa form, gọi `POST /api/quotes/settings/save`.
    - **Kết quả:** API trả về một `settings_id`. Frontend **PHẢI LƯU LẠI** `settings_id` này để sử dụng ở bước 3.

3.  **Bước 3: Tạo Báo Giá (Generate Quote)**
    - **Mục đích:** Tạo ra file báo giá DOCX từ một câu lệnh của người dùng.
    - **Hành động:** Người dùng nhập yêu cầu (ví dụ: "tạo báo giá cho 2 laptop..."). Frontend gọi `POST /api/quotes/generate` cùng với `settings_id` đã lưu và câu lệnh này.
    - **Kết quả:** API trả về đường dẫn `file_url` để tải file báo giá. Frontend hiển thị link tải file cho người dùng.

---

## 3. Chi Tiết Các API Endpoints

### Endpoint 1: Lấy Dữ Liệu Người Dùng

- **Mục đích:** Lấy cấu hình gần nhất và danh sách template.
- **Method:** `GET`
- **URL:**
    - **Development:** `http://localhost:8000/api/quotes/user-data`
    - **Production:** `https://ai.aimoney.io.vn/api/quotes/user-data`
- **Headers:**
    ```json
    { "Authorization": "Bearer <token>" }
    ```
- **Request Body:** (Không có)
- **Success Response (200 OK):**
    ```json
    {
        "settings": {
            "id": "63a5f1b9e4b0d8a7f6b1c2d3",
            "user_id": "user123",
            "firebase_uid": "firebase_uid_abc",
            "company_info": {
                "name": "Công ty TNHH ABC",
                "address": "123 Đường ABC, Quận 1, TP.HCM",
                "tax_code": "0123456789",
                "representative": "Nguyễn Văn A",
                "phone": "0901234567",
                "email": "contact@abc.com"
            },
            "customer_info": {
                "name": "Khách hàng XYZ",
                "address": "456 Đường XYZ, Quận 2, TP.HCM",
                "phone": "0987654321",
                "email": "customer@xyz.com"
            },
            "payment_terms": {
                "method": "transfer",
                "due_days": 30,
                "discount_percent": 0.0,
                "notes": "Thanh toán trong vòng 30 ngày"
            },
            "template_id": "template_quote_001"
        },
        "recent_quotes": [],
        "available_templates": [
            {
                "id": "template_quote_001",
                "name": "Template Báo Giá Mặc Định",
                "description": "Template chuẩn cho các báo giá thông thường.",
                "type": "quote",
                "file_path": "templates/documents/quote_template_default.docx"
            }
        ]
    }
    ```

### Endpoint 2: Lưu Cấu Hình Ban Đầu

- **Mục đích:** Lưu thông tin và lấy `settings_id`.
- **Method:** `POST`
- **URL:**
    - **Development:** `http://localhost:8000/api/quotes/settings/save`
    - **Production:** `https://ai.aimoney.io.vn/api/quotes/settings/save`
- **Headers:**
    ```json
    {
      "Authorization": "Bearer <token>",
      "Content-Type": "application/json"
    }
    ```
- **Request Body:**
    ```json
    {
      "company_info": {
        "name": "Công ty TNHH ABC Test",
        "address": "123 Đường Test, Quận 1, TP.HCM",
        "tax_code": "0123456789",
        "representative": "Nguyễn Văn Test",
        "phone": "0901234567",
        "email": "test@abc.com"
      },
      "customer_info": {
        "name": "Khách hàng Test XYZ",
        "address": "456 Đường XYZ, Quận 2, TP.HCM",
        "phone": "0987654321",
        "email": "customer@xyz.com"
      },
      "payment_terms": {
        "method": "transfer",
        "due_days": 30,
        "discount_percent": 0.0,
        "notes": "Thanh toán trong vòng 30 ngày"
      },
      "template_id": "template_quote_001"
    }
    ```
- **Success Response (200 OK):**
    ```json
    {
      "success": true,
      "message": "Quote settings saved successfully",
      "settings_id": "63a5f1b9e4b0d8a7f6b1c2d3"
    }
    ```
- **Error Response (422 Unprocessable Entity):**
    ```json
    {
      "detail": [
        {
          "loc": ["body", "company_info", "email"],
          "msg": "value is not a valid email address",
          "type": "value_error.email"
        }
      ]
    }
    ```

### Endpoint 3: Tạo Báo Giá

- **Mục đích:** Gửi yêu cầu tạo file báo giá.
- **Method:** `POST`
- **URL:**
    - **Development:** `http://localhost:8000/api/quotes/generate`
    - **Production:** `https://ai.aimoney.io.vn/api/quotes/generate`
- **Headers:**
    ```json
    {
      "Authorization": "Bearer <token>",
      "Content-Type": "application/json"
    }
    ```
- **Request Body:**
    ```json
    {
      "settings_id": "63a5f1b9e4b0d8a7f6b1c2d3",
      "user_query": "Tạo báo giá cho 5 máy tính với giá 15.000.000 VND mỗi cái và 2 màn hình với giá 5.000.000 VND mỗi cái",
      "template_id": "template_quote_001"
    }
    ```
- **Success Response (200 OK):**
    ```json
    {
      "success": true,
      "message": "Quote generated successfully",
      "quote_id": "63a5f2c4e4b0d8a7f6b1c2d4",
      "file_path": "/generated_documents/quotes/quote_test_user_1671820740.docx",
      "file_url": "http://localhost:8000/generated_documents/quotes/quote_test_user_1671820740.docx",
      "total_amount": 85000000.0,
      "currency": "VND"
    }
    ```
- **Error Response (404 Not Found):**
    ```json
    {
      "detail": "Settings with ID 'some_invalid_id' not found."
    }
    ```

### Endpoint 4: Lấy Lịch Sử Báo Giá

- **Mục đích:** Hiển thị danh sách các báo giá đã tạo.
- **Method:** `GET`
- **URL:**
    - **Development:** `http://localhost:8000/api/quotes/history`
    - **Production:** `https://ai.aimoney.io.vn/api/quotes/history`
- **Headers:**
    ```json
    { "Authorization": "Bearer <token>" }
    ```
- **Request Body:** (Không có)
- **Success Response (200 OK):**
    ```json
    {
      "success": true,
      "count": 1,
      "quotes": [
        {
          "id": "63a5f2c4e4b0d8a7f6b1c2d4",
          "user_id": "user123",
          "file_path": "/generated_documents/quotes/quote_test_user_1671820740.docx",
          "file_url": "http://localhost:8000/generated_documents/quotes/quote_test_user_1671820740.docx",
          "created_at": "2025-09-11T10:39:00.123Z",
          "total_amount": 85000000.0,
          "currency": "VND",
          "customer_name": "Khách hàng Test XYZ"
        }
      ]
    }
    ```

---

## 4. Troubleshooting & Common Issues

### Issue 1: CORS Policy Error
**Lỗi:** `Access to fetch at 'http://localhost:8000/...' from origin 'http://localhost:3000' has been blocked by CORS policy`

**Giải pháp:**
- Đảm bảo backend đang chạy với CORS được bật cho localhost:3000
- Kiểm tra `CORS_ORIGINS` trong file `.env` có chứa `http://localhost:3000`
- Backend đã được cấu hình để chỉ enable CORS cho development environment

### Issue 2: URL Path Sai
**Lỗi:** Request đến `/api/chat/api/quotes/user-data` thay vì `/api/quotes/user-data`

**Giải pháp:**
- Kiểm tra base URL trong frontend service
- Đảm bảo không có duplicated path segments
- URLs chính xác theo tài liệu này

### Issue 3: 401 Unauthorized
**Lỗi:** Token hết hạn hoặc không hợp lệ

**Giải pháp:**
- Kiểm tra token format trong Authorization header: `Bearer <token>`
- Đảm bảo token còn hiệu lực (Firebase ID token: 1 giờ)
- Firebase token có thể được verify trực tiếp từ frontend

### Issue 4: 405 Method Not Allowed cho OPTIONS
**Lỗi:** Preflight requests bị reject

**Giải pháp:**
- Backend đã được cấu hình để hỗ trợ OPTIONS method cho development
- CORS middleware sẽ tự động xử lý preflight requests

### Issue 5: Token Firebase bị lỗi "iss" claim
**Lỗi:** Session cookie có incorrect "iss" claim

**Giải pháp:**
- Backend đã được cấu hình để verify ID token trước, sau đó mới thử session cookie
- Frontend nên sử dụng Firebase ID token trực tiếp thay vì session cookie cho development

---

## 5. Authentication Flow cho Development

### Sử dụng Firebase ID Token trực tiếp
Đối với development, frontend có thể sử dụng Firebase ID token trực tiếp:

1. **Lấy Firebase ID Token sau khi login:**
```javascript
const user = firebase.auth().currentUser;
const idToken = await user.getIdToken();
```

2. **Sử dụng ID Token cho API calls:**
```javascript
const headers = {
  'Authorization': `Bearer ${idToken}`,
  'Content-Type': 'application/json'
};
```

**Lưu ý:** ID Token có hiệu lực 1 giờ, frontend cần tự động refresh khi cần thiết.
