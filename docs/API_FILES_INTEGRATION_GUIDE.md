# Hướng Dẫn Tích Hợp API Dịch Vụ AI

Tài liệu này mô tả chi tiết các API endpoint do dịch vụ AI cung cấp để backend có thể tích hợp chính xác. Bao gồm quản lý file và trích xuất dữ liệu tự động với đầy đủ định dạng payload và response.

**Base URL:** `http://<your-ai-service-host>:<port>`

**Authentication:** Tất cả API yêu cầu header `X-Internal-API-Key: your-internal-api-key-here`

---

## 📁 1. API Quản Lý File (`file_routes.py`)

API này dùng để quản lý các file chung của công ty như tài liệu, hình ảnh, video,... (ví dụ: hồ sơ công ty, báo cáo, hình ảnh sản phẩm).

**Prefix:** `/api/admin`

### 1.1. Upload và Xử Lý File (Bất đồng bộ)

Upload file qua R2 URL và đưa vào queue xử lý bất đồng bộ.

**Endpoint:** `POST /api/admin/companies/{companyId}/files/upload`

**Headers:**
```
Content-Type: application/json
X-Internal-API-Key: your-internal-api-key-here
```

**Path Parameters:**
| Tên | Kiểu | Bắt buộc | Mô tả |
|-----|------|----------|-------|
| `companyId` | string | ✅ | ID của công ty |

**Request Body:**
```json
{
  "r2_url": "https://pub-xyz.r2.dev/companies/company-123/documents/file.pdf",
  "data_type": "document",
  "industry": "REAL_ESTATE",
  "metadata": {
    "original_name": "company_profile.pdf",
    "file_id": "file_123456789",
    "file_name": "company_profile_processed.pdf",
    "file_size": 1024000,
    "file_type": "application/pdf",
    "uploaded_by": "user_uid_123",
    "description": "Company profile document",
    "tags": ["profile", "company_info", "overview"]
  },
  "upload_to_qdrant": true,
  "callback_url": "https://backend.example.com/api/webhooks/file-processed"
}
```

**Request Schema:**
- `r2_url` (string, required): Public R2 URL của file đã upload
- `data_type` (string, required): Loại file (`document`, `image`, `video`, `audio`, `other`)
- `industry` (string, required): Ngành nghề công ty (`REAL_ESTATE`, `RESTAURANT`, `BANKING`, `ECOMMERCE`, `OTHER`)
- `metadata` (object, required): Metadata file từ backend
  - `original_name` (string): Tên file gốc
  - `file_id` (string): ID file từ backend
  - `file_name` (string): Tên file đã xử lý
  - `file_size` (number): Kích thước file (bytes)
  - `file_type` (string): MIME type
  - `uploaded_by` (string): User ID người upload
  - `description` (string): Mô tả file
  - `tags` (array): Danh sách tags
- `upload_to_qdrant` (boolean): Có upload lên Qdrant không (default: true)
- `callback_url` (string, optional): URL callback khi xử lý xong

**Success Response (200 OK):**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "queued",
  "message": "File upload task queued successfully. Use task_id to check processing status.",
  "company_id": "company-123",
  "status_check_url": "/api/admin/tasks/document/a1b2c3d4-e5f6-7890-1234-567890abcdef/status",
  "file_type": "application/pdf",
  "data_type": "document",
  "estimated_processing_time": "30-60 seconds",
  "created_at": "2025-07-25T10:30:00.123Z"
}
```

**Error Response (503 Service Unavailable):**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "status": "failed",
  "message": "Failed to queue file upload task: Queue service unavailable",
  "company_id": "company-123",
  "status_check_url": "/api/admin/tasks/document/a1b2c3d4-e5f6-7890-1234-567890abcdef/status",
  "file_type": "unknown",
  "data_type": "document",
  "error": "Queue service unavailable. Please try again later.",
  "created_at": "2025-07-25T10:30:00.123Z"
}
```

---

### 1.2. Xóa File theo ID

Xóa một file cụ thể và tất cả dữ liệu liên quan trong Qdrant.

**Endpoint:** `DELETE /api/admin/companies/{company_id}/files/{file_id}`

**Headers:**
```
X-Internal-API-Key: your-internal-api-key-here
```

**Path Parameters:**
| Tên | Kiểu | Bắt buộc | Mô tả |
|-----|------|----------|-------|
| `company_id` | string | ✅ | ID của công ty |
| `file_id` | string | ✅ | ID của file cần xóa |

**Success Response (200 OK):**
```json
{
  "success": true,
  "message": "File file_123456789 deleted successfully",
  "deleted_points": 15,
  "collection": "multi_company_data"
}
```

**Error Response (404 Not Found):**
```json
{
  "detail": "File file_123456789 not found in company company-123"
}
```

**Error Response (500 Internal Server Error):**
```json
{
  "detail": "Failed to delete file: <error_message>"
}
```

---

### 1.3. Kiểm Tra Trạng Thái File

Kiểm tra file có tồn tại trong Qdrant và lấy thông tin chi tiết.

**Endpoint:** `GET /api/admin/companies/{company_id}/files/{file_id}/status`

**Headers:**
```
X-Internal-API-Key: your-internal-api-key-here
```

**Path Parameters:**
| Tên | Kiểu | Bắt buộc | Mô tả |
|-----|------|----------|-------|
| `company_id` | string | ✅ | ID của công ty |
| `file_id` | string | ✅ | ID của file cần kiểm tra |

**Success Response (200 OK) - File tồn tại:**
```json
{
  "success": true,
  "message": "File status check completed",
  "file_found": true,
  "collection": "multi_company_data",
  "company_id": "company-123",
  "file_id": "file_123456789",
  "points_found": {
    "by_file_id": 15,
    "by_company_and_file_id": 15,
    "total_unique": 15
  },
  "file_details": {
    "file_id": "file_123456789",
    "company_id": "company-123",
    "content_type": "file_document",
    "data_type": "document",
    "industry": "REAL_ESTATE",
    "language": "vi",
    "created_at": "2025-07-25T10:30:00.123Z",
    "updated_at": "2025-07-25T10:30:00.123Z",
    "metadata": {
      "original_name": "company_profile.pdf",
      "description": "Company profile document"
    },
    "tags": ["profile", "company_info", "overview"]
  },
  "sample_point_ids": [
    "file_123456789_chunk_0",
    "file_123456789_chunk_1",
    "file_123456789_chunk_2",
    "file_123456789_chunk_3",
    "file_123456789_chunk_4"
  ]
}
```

**Success Response (200 OK) - File không tồn tại:**
```json
{
  "success": false,
  "message": "Collection multi_company_data does not exist",
  "file_found": false,
  "collection": "multi_company_data",
  "company_id": "company-123",
  "file_id": "file_123456789"
}
```

---

### 1.4. Xóa File theo Tag (Chưa implement)

**Endpoint:** `DELETE /api/admin/companies/{company_id}/files/tags/{tag_name}`

**Response:**
```json
{
  "success": false,
  "message": "Delete by tag 'profile' not yet implemented",
  "collection": "multi_company_data"
}
```

---

## 🤖 2. API Trích Xuất Dữ Liệu (`extraction_routes.py`)

API chuyên dụng để trích xuất thông tin có cấu trúc (sản phẩm, dịch vụ) từ các file như menu, bảng giá, brochure.

**Prefix:** `/api/extract`

### 2.1. Trích Xuất và Phân Loại Tự Động

Endpoint chính để xử lý file và trích xuất dữ liệu sản phẩm/dịch vụ có cấu trúc.

**Endpoint:** `POST /api/extract/process`

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "r2_url": "https://pub-xyz.r2.dev/companies/golden-dragon/menus/menu.pdf",
  "company_id": "golden-dragon-restaurant",
  "industry": "RESTAURANT",
  "target_categories": ["products", "services"],
  "file_metadata": {
    "original_name": "golden_dragon_menu.pdf",
    "file_id": "menu_file_abcde",
    "file_size": 1024000,
    "file_type": "application/pdf",
    "uploaded_at": "2025-07-16T10:00:00Z"
  },
  "company_info": {
    "id": "golden-dragon-restaurant",
    "name": "Golden Dragon Restaurant",
    "industry": "restaurant",
    "description": "Traditional Vietnamese restaurant specializing in Pho and Bun Cha"
  },
  "language": "vi",
  "upload_to_qdrant": true,
  "callback_url": "https://backend.example.com/api/webhooks/extraction-complete"
}
```

**Request Schema:**
- `r2_url` (string, required): Public R2 URL của file
- `company_id` (string, required): Company ID để lưu vào Qdrant
- `industry` (string, required): Ngành nghề để chọn template (`RESTAURANT`, `REAL_ESTATE`, `BANKING`, `ECOMMERCE`, `OTHER`)
- `target_categories` (array, optional): Target categories (`["products", "services"]`) - nếu null sẽ tự động extract cả hai
- `file_metadata` (object, required): Metadata file
  - `original_name` (string): Tên file gốc
  - `file_id` (string): ID file
  - `file_size` (number): Kích thước file
  - `file_type` (string): MIME type
  - `uploaded_at` (string): Thời gian upload
- `company_info` (object, optional): Thông tin công ty để có context
- `language` (string, optional): Ngôn ngữ kết quả (`vi`, `en`) - default: `vi`
- `upload_to_qdrant` (boolean, optional): Upload kết quả lên Qdrant - default: `false`
- `callback_url` (string, optional): URL callback khi xử lý xong

**Success Response (200 OK):**
```json
{
  "success": true,
  "message": "Auto-categorization extraction completed successfully",
  "raw_content": "Thực đơn nhà hàng Rồng Vàng\nPhở Bò Tái: 50.000đ\nBún Chả Hà Nội: 45.000đ\nDịch vụ giao hàng tận nơi: 15.000đ - 30.000đ\n...",
  "structured_data": {
    "products": [
      {
        "product_id": "pho_bo_tai_01",
        "name": "Phở Bò Tái",
        "description": "Phở bò truyền thống với thịt bò tái mềm, nước dùng đậm đà",
        "price": 50000,
        "currency": "VND",
        "category": "Món chính",
        "tags": ["phở", "bò", "món nước"],
        "availability": "available",
        "preparation_time": "10-15 phút"
      },
      {
        "product_id": "bun_cha_ha_noi_01",
        "name": "Bún Chả Hà Nội",
        "description": "Bún chả truyền thống Hà Nội với thịt nướng thơm ngon",
        "price": 45000,
        "currency": "VND",
        "category": "Món chính",
        "tags": ["bún chả", "nướng", "hà nội"],
        "availability": "available",
        "preparation_time": "12-18 phút"
      }
    ],
    "services": [
      {
        "service_id": "delivery_01",
        "name": "Giao hàng tận nơi",
        "description": "Dịch vụ giao hàng trong bán kính 5km từ nhà hàng",
        "price_range": "15.000đ - 30.000đ",
        "pricing_type": "variable",
        "conditions": "Áp dụng cho đơn hàng từ 100.000đ",
        "duration": "30-45 phút",
        "availability": "daily"
      }
    ],
    "extraction_summary": {
      "total_products": 2,
      "total_services": 1,
      "currency_detected": "VND",
      "categories_found": ["Món chính"],
      "price_range": {
        "min": 45000,
        "max": 50000
      }
    }
  },
  "template_used": "restaurant_menu_v2",
  "ai_provider": "gemini-1.5-pro-latest",
  "industry": "RESTAURANT",
  "data_type": "auto_categorized",
  "processing_time": 15.78,
  "total_items_extracted": 3,
  "extraction_metadata": {
    "confidence_score": 0.95,
    "pages_processed": 2,
    "total_items": 3,
    "language_detected": "vi",
    "template_matched": true
  },
  "error": null,
  "error_details": null
}
```

**Error Response (500 Internal Server Error):**
```json
{
  "success": false,
  "message": "Auto-categorization extraction failed",
  "processing_time": 8.45,
  "industry": "RESTAURANT",
  "data_type": "auto_categorized",
  "error": "Failed to download file from R2 URL",
  "error_details": {
    "r2_url": "https://pub-xyz.r2.dev/companies/golden-dragon/menus/menu.pdf",
    "industry": "RESTAURANT",
    "target_categories": ["products", "services"],
    "file_name": "golden_dragon_menu.pdf",
    "error_type": "ConnectionError",
    "processing_time": 8.45
  },
  "raw_content": null,
  "structured_data": null,
  "template_used": null,
  "ai_provider": null,
  "total_items_extracted": null,
  "extraction_metadata": null
}
```

---

### 2.2. Kiểm Tra Sức Khỏe Dịch Vụ

**Endpoint:** `GET /api/extract/health`

**Success Response (200 OK):**
```json
{
  "service": "AI Extraction Service",
  "status": "healthy",
  "timestamp": "2025-07-25T11:00:00.456Z",
  "ai_providers": {
    "deepseek": true,
    "chatgpt": true,
    "gemini": true
  },
  "template_system": {
    "status": "ready",
    "available_templates": 5,
    "supported_industries": [
      "REAL_ESTATE",
      "RESTAURANT", 
      "BANKING",
      "ECOMMERCE",
      "OTHER"
    ]
  },
  "supported_file_types": [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  ]
}
```

**Degraded Response (200 OK):**
```json
{
  "service": "AI Extraction Service",
  "status": "degraded",
  "timestamp": "2025-07-25T11:00:00.456Z",
  "ai_providers": {
    "deepseek": false,
    "chatgpt": true,
    "gemini": true
  },
  "template_system": {
    "status": "ready",
    "available_templates": 5,
    "supported_industries": [
      "REAL_ESTATE",
      "RESTAURANT",
      "BANKING", 
      "ECOMMERCE",
      "OTHER"
    ]
  },
  "supported_file_types": [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain"
  ]
}
```

---

### 2.3. Thông Tin Dịch Vụ

**Endpoint:** `GET /api/extract/info`

**Success Response (200 OK):**
```json
{
  "service_name": "AI Extraction Service",
  "version": "2.1.0",
  "description": "Intelligent document processing and data extraction service",
  "capabilities": [
    "Multi-format file processing",
    "Industry-specific template extraction", 
    "Auto-categorization (products/services)",
    "Multi-language support",
    "Vector embedding generation",
    "Qdrant integration"
  ],
  "ai_providers": {
    "primary": "gemini-1.5-pro-latest",
    "fallback": "chatgpt-4o-mini",
    "vision": "chatgpt-4o-vision",
    "embedding": "text-embedding-3-small"
  },
  "template_system": {
    "total_templates": 5,
    "industries": {
      "RESTAURANT": "Menu and service extraction",
      "REAL_ESTATE": "Property and service listings",
      "BANKING": "Financial products and services",
      "ECOMMERCE": "Product catalogs and offerings",
      "OTHER": "Generic business documents"
    }
  },
  "api_endpoints": {
    "main_endpoint": "/api/extract/process",
    "description": "Single endpoint for R2 URL extraction with industry templates",
    "implemented_features": [
      "Industry-specific template selection",
      "JSON schema integration", 
      "AI provider auto-selection",
      "Raw + structured data extraction",
      "Background Qdrant upload",
      "Error handling with detailed responses"
    ]
  },
  "performance": {
    "avg_processing_time": "10-30 seconds",
    "supported_file_size": "up to 50MB",
    "concurrent_requests": "up to 10"
  }
}
```

---

## 🔗 3. Webhook Callbacks (Tương lai)

Khi `callback_url` được cung cấp, dịch vụ sẽ gửi notification về backend khi xử lý hoàn tất.

### 3.1. File Upload Callback

**URL:** `{callback_url từ request}`  
**Method:** `POST`  
**Headers:** `Content-Type: application/json`

**Success Callback:**
```json
{
  "event": "file.uploaded",
  "companyId": "company-123",
  "data": {
    "fileId": "file_123456789",
    "status": "completed",
    "chunksCreated": 15,
    "processingTime": 25.6,
    "processedAt": "2025-07-25T11:05:30.789Z",
    "tags": ["profile", "company_info", "overview"]
  },
  "timestamp": "2025-07-25T11:05:30.789Z"
}
```

**Error Callback:**
```json
{
  "event": "file.uploaded", 
  "companyId": "company-123",
  "data": {
    "fileId": "file_123456789",
    "status": "failed",
    "error": "Failed to process file: unsupported format",
    "failedAt": "2025-07-25T11:05:30.789Z"
  },
  "timestamp": "2025-07-25T11:05:30.789Z"
}
```

### 3.2. Extraction Callback

**Success Callback:**
```json
{
  "event": "extraction.completed",
  "companyId": "golden-dragon-restaurant", 
  "data": {
    "fileId": "menu_file_abcde",
    "status": "completed",
    "extractedItems": {
      "products": 15,
      "services": 3
    },
    "processingTime": 18.4,
    "processedAt": "2025-07-25T11:05:30.789Z"
  },
  "timestamp": "2025-07-25T11:05:30.789Z"
}
```

---

## 📋 4. Error Codes và Troubleshooting

### Common Error Codes

| HTTP Code | Description | Giải pháp |
|-----------|-------------|-----------|
| `400` | Bad Request - Invalid payload | Kiểm tra format JSON và required fields |
| `401` | Unauthorized - Missing API key | Thêm header `X-Internal-API-Key` |
| `404` | Not Found - File/Resource not exists | Kiểm tra file_id và company_id |
| `503` | Service Unavailable - Queue/AI service down | Retry sau vài phút |
| `500` | Internal Server Error | Liên hệ AI team để debug |

### Debugging Tips

1. **File không tìm thấy:** Sử dụng endpoint `/companies/{company_id}/files/{file_id}/status` để kiểm tra
2. **Queue bị đầy:** Response sẽ có status `503`, retry sau 30-60 giây
3. **Extraction thất bại:** Kiểm tra file format và R2 URL accessibility
4. **Callback không nhận được:** Đảm bảo callback_url accessible và accept POST request

---

## 📞 5. Support & Contact

- **Technical Issues:** Liên hệ AI Development Team
- **API Documentation:** Repository `/docs` folder  
- **Service Status:** Sử dụng `/api/extract/health` endpoint
- **Emergency:** Check service logs tại `/logs` directory

---

*Cập nhật lần cuối: 25/07/2025*
*Phiên bản API: 2.1.0*

### Endpoint Chính: Chat Streaming

**URL**: `POST /api/unified/chat-stream`

**Headers**:
```http
Content-Type: application/json
X-Company-Id: company_123 (optional, có thể gửi trong body)
```

**Request Body**:
```json
{
  "message": "Tôi muốn biết về lãi suất vay nhà",
  "company_id": "company_123",
  "industry": "banking",
  "user_info": {
    "user_id": "DEVICE_ABC123",
    "source": "web_device",
    "name": "Nguyễn Văn A",
    "avatar_url": "https://example.com/avatar.jpg",
    "platform_specific_data": {
      "browser": "Chrome/125.0",
      "ip": "192.168.1.1",
      "device_type": "desktop"
    }
  },
  "session_id": "DEVICE_ABC123",
  "language": "auto_detect",
  "context": {
    "page_url": "https://bank.com/products",
    "referring_source": "google"
  },
  "metadata": {
    "app_version": "1.2.0",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Response**: Server-Sent Events Stream

```
data: {"type": "language", "language": "vi", "confidence": 0.98}

data: {"type": "intent", "intent": "INFORMATION", "confidence": 0.95, "reasoning": "User asking about loan interest rates"}

data: {"type": "content", "chunk": "Xin chào anh Nguyễn Văn A! "}

data: {"type": "content", "chunk": "Dựa vào cuộc trò chuyện trước, "}

data: {"type": "content", "chunk": "tôi hiểu anh quan tâm đến vay mua nhà. "}

data: {"type": "content", "chunk": "Hiện tại ngân hàng có gói lãi suất ưu đãi..."}

data: {"type": "sources", "sources": [{"type": "qdrant_rag", "chunks": 3}, {"type": "chat_history", "messages": 5}]}

data: {"type": "done", "session_id": "DEVICE_ABC123", "message_id": "msg_456"}
```

### User Sources Hỗ Trợ

| Source Code | Mô tả | User ID Format | Channel Webhook | Thông tin bổ sung |
|-------------|--------|----------------|-----------------|--------------------|
| `web_device` | Website/WebApp | Device UUID | `WEB` | Browser info, IP |
| `facebook_messenger` | FB Messenger | FB User ID | `FACEBOOK` | Profile info, avatar |
| `whatsapp` | WhatsApp Business | Phone Number | `WHATSAPP` | Contact name |
| `zalo` | Zalo OA | Zalo User ID | `ZALO` | Display name, avatar |
| `instagram` | Instagram DM | IG User ID | `INSTAGRAM` | Username, profile |
| `website_plugin` | Embedded Plugin | Generated ID | `PLUGIN` | Page context |

### Webhook Events (AI Service → Backend)
1. X-Webhook-Signature là gì?
X-Webhook-Signature là một digital signature (chữ ký số) để:

Xác thực: Đảm bảo webhook thực sự đến từ AI Service, không phải từ kẻ tấn công
Tính toàn vẹn: Đảm bảo dữ liệu không bị thay đổi trong quá trình truyền
2. Cách tạo HMAC SHA256 Signature:
Trong AI Service (gửi):
import hmac
import hashlib

# Secret key chia sẻ giữa AI Service và Backend
secret_key = "webhook-secret-for-signature"

# Payload JSON string
payload = '{"event":"message.created","data":{...}}'

# Tạo signature
signature = hmac.new(
    secret_key.encode('utf-8'),
    payload.encode('utf-8'), 
    hashlib.sha256
).hexdigest()

# Gửi header
headers = {
    "X-Webhook-Signature": f"sha256={signature}"
}
Trong Backend (verify)
const crypto = require('crypto');

function verifyWebhookSignature(payload, receivedSignature, secret) {
    // Tạo expected signature từ payload
    const expectedSignature = crypto
        .createHmac('sha256', secret)
        .update(payload, 'utf8')
        .digest('hex');
    
    // So sánh với signature nhận được
    const expectedHeader = `sha256=${expectedSignature}`;
    
    // Secure comparison để tránh timing attacks
    return crypto.timingSafeEqual(
        Buffer.from(receivedSignature),
        Buffer.from(expectedHeader)
    );
}

// Middleware xác thực
app.post('/api/webhooks/ai/conversation', (req, res) => {
    const signature = req.headers['x-webhook-signature'];
    const payload = JSON.stringify(req.body);
    
    if (!verifyWebhookSignature(payload, signature, WEBHOOK_SECRET)) {
        return res.status(401).json({
            success: false,
            error: {
                code: "UNAUTHORIZED",
                message: "Invalid webhook signature"
            }
        });
    }
    
    // Xử lý webhook...
});
#### 1. Conversation Created
```json
{
  "event": "conversation.created",
  "timestamp": "2025-01-15T10:30:00Z",
  "companyId": "company_123",
  "data": {
    "conversationId": "conv_uuid_789",
    "sessionId": "DEVICE_ABC123",
    "userInfo": {
      "user_id": "DEVICE_ABC123",
      "source": "web_device", 
      "name": "Nguyễn Văn A",
      "avatar_url": "https://example.com/avatar.jpg"
    },
    "channel": "WEB",
    "industry": "banking",
    "startedAt": "2025-01-15T10:30:00Z",
    "metadata": {
      "industry": "banking",
      "language": "vi",
      "user_info": {
        "user_id": "DEVICE_ABC123",
        "source": "web_device",
        "name": "Nguyễn Văn A",
        "avatar_url": "https://example.com/avatar.jpg"
      },
      "context": {
        "page_url": "https://bank.com/products"
      }
    }
  }
}
```

#### 2. Message Created (cho mỗi tin nhắn user & AI)
```json
{
  "event": "message.created", 
  "timestamp": "2025-01-15T10:30:05Z",
  "companyId": "company_123",
  "data": {
    "conversationId": "conv_uuid_789",
    "messageId": "msg_uuid_456",
    "role": "user",
    "content": "Tôi muốn biết về lãi suất vay nhà",
    "timestamp": "2025-01-15T10:30:05Z",
    "metadata": {
      "intent": "INFORMATION",
      "language": "vi",
      "confidence": 0.95,
      "session_id": "DEVICE_ABC123",
      "processing_time": 1.2,
      "user_info": {
        "user_id": "DEVICE_ABC123",
        "source": "web_device",
        "name": "Nguyễn Văn A"
      },
      "context_used": {
        "chat_history_messages": 5,
        "rag_chunks": 3
      }
    }
  }
}
```

## Tính Năng Nâng Cao

### 1. Context-Aware Responses
- AI sử dụng lịch sử chat recent (10 tin nhắn gần nhất) làm context
- Hiểu được follow-up questions và references đến cuộc hội thoại trước
- Cá nhân hóa phản hồi dựa trên thông tin user (tên, platform)

### 2. Session Management
- Session ID = User ID để đảm bảo consistency
- Lịch sử được lưu trữ trong memory của AI Service
- Auto-cleanup sessions sau thời gian inactive

### 3. Multi-Language Support
- Auto-detect ngôn ngữ từ tin nhắn
- Translate query để search documents đa ngôn ngữ
- Response theo ngôn ngữ phù hợp

### 4. RAG Enhancement
- Search company documents với ngữ cảnh từ chat history
- Kết hợp multiple search queries (original + translated)
- Deduplicate và rank results theo relevance

## API Endpoints Bổ Sung

### 1. Lấy Thông Tin Session
```http
GET /api/unified/session/{session_id}
```

**Response**:
```json
{
  "session_id": "DEVICE_ABC123",
  "data": {
    "user_info": {
      "user_id": "DEVICE_ABC123",
      "source": "web_device",
      "name": "Nguyễn Văn A"
    },
    "company_id": "company_123",
    "industry": "banking"
  },
  "conversation_history": [
    {
      "role": "user",
      "content": "Xin chào",
      "intent": "GREETING",
      "language": "vi", 
      "timestamp": "2025-01-15T10:25:00Z"
    },
    {
      "role": "assistant",
      "content": "Chào anh! Tôi có thể giúp gì?",
      "intent": "GREETING",
      "language": "vi",
      "timestamp": "2025-01-15T10:25:02Z"
    }
  ],
  "message_count": 6,
  "last_activity": "2025-01-15T10:30:05Z"
}
```

### 2. Xóa Session
```http
DELETE /api/unified/session/{session_id}
```

### 3. Thống Kê Hệ Thống
```http
GET /api/unified/stats
```

## Implementation Notes

### Backend Webhook Endpoints
Backend cần implement các endpoints sau để nhận data từ AI Service:

```http
POST /api/webhooks/ai/conversation
```

**Expected Headers**:
```http
Content-Type: application/json
X-Webhook-Source: ai-service
X-Webhook-Signature: <hmac_sha256_signature>
```

**Production Webhook URL**: `https://ai.aimoney.io.vn`

### Frontend Implementation Tips

1. **SSE Connection Management**:
```javascript
const eventSource = new EventSource('/api/unified/chat-stream', {
  headers: {
    'X-Company-Id': 'company_123'
  }
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'content':
      appendToChat(data.chunk);
      break;
    case 'done':
      finalizeChatMessage(data.session_id);
      break;
    case 'error':
      handleError(data.error);
      break;
  }
};
```

2. **User Info Collection**:
```javascript
// Web Device
const userInfo = {
  user_id: getOrCreateDeviceId(),
  source: 'web_device',
  name: getUserName(),
  platform_specific_data: {
    browser: navigator.userAgent,
    screen_resolution: `${screen.width}x${screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
  }
};

// Facebook Messenger
const userInfo = {
  user_id: messengerUserId,
  source: 'facebook_messenger', 
  name: messengerUserName,
  avatar_url: messengerAvatarUrl,
  platform_specific_data: {
    messenger_thread_id: threadId,
    page_id: pageId
  }
};
```

### Error Handling

| Error Code | Mô tả | Giải pháp |
|------------|--------|-----------|
| 400 | Missing user_info hoặc company_id | Kiểm tra request body format |
| 401 | Invalid company_id | Verify company access |
| 429 | Rate limit exceeded | Implement retry với backoff |
| 500 | AI Service error | Check logs, retry |

### Performance Considerations

1. **Memory Management**: AI Service lưu session trong memory, cần monitor usage
2. **Rate Limiting**: Implement rate limiting theo user_id và company_id  
3. **Webhook Delivery**: Implement retry logic cho webhook failures
4. **Chat History**: Limit history size để tránh context quá dài

## Security

1. **Company Isolation**: Data được isolate theo company_id
2. **User Privacy**: User data chỉ lưu temporary trong session
3. **Webhook Security**: Implement signature verification cho webhooks
4. **Rate Limiting**: Prevent abuse từ individual users

## Monitoring & Analytics

### Metrics cần track:
- Response time theo company và industry
- Intent detection accuracy
- RAG hit rate (có tìm thấy relevant docs không)
- User engagement (messages per session)
- Error rates theo platform

### Logs quan trọng:
- User interactions với platform info
- RAG search results và relevance scores  
- AI provider response times
- Webhook delivery status

Tài liệu này cung cấp đầy đủ thông tin để Frontend và Backend teams có thể tích hợp với AI Service một cách hiệu quả.
