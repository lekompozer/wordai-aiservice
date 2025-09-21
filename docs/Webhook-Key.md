1. X-Webhook-Signature là gì?
X-Webhook-Signature là một digital signature (chữ ký số) để:
* Xác thực: Đảm bảo webhook thực sự đến từ AI Service, không phải từ kẻ tấn công
* Tính toàn vẹn: Đảm bảo dữ liệu không bị thay đổi trong quá trình truyền
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
 Trong Backend (verify):
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

## 3. Webhook Endpoints của AI Service

AI Service gửi webhook tới 2 endpoints chính:

### A. File Upload Callback (Raw Content)
**Endpoint**: `/api/webhooks/file-processed`
**Purpose**: Thông báo khi file upload và xử lý content hoàn tất

**Headers gửi từ AI Service**:
```javascript
{
    "Content-Type": "application/json",
    "X-Webhook-Source": "ai-service", 
    "X-Webhook-Signature": "sha256=abc123...",
    "User-Agent": "Agent8x-AI-Service/1.0"
}
```

**Payload Structure**:
```javascript
{
    "file_id": "550e8400-e29b-41d4-a716-446655440000",
    "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
    "status": "completed",
    "processing_time": 5.24,
    "content_type": "text/plain",
    "file_size": 2048,
    "content_summary": {
        "total_characters": 1850,
        "has_raw_content": true
    },
    "timestamp": "2025-07-27T11:02:27.443808"
}
```

### B. AI Extraction Callback (Structured Data)
**Endpoint**: `/api/webhooks/ai/extraction-callback`
**Purpose**: Thông báo khi AI extraction hoàn tất với dữ liệu products/services

**Headers gửi từ AI Service**:
```javascript
{
    "Content-Type": "application/json",
    "X-Webhook-Source": "ai-service", 
    "X-Webhook-Signature": "sha256=def456...", 
    "User-Agent": "Agent8x-AI-Service/1.0"
}
```

**Payload Structure**:
```javascript
{
    "task_id": "extract_1753617620355_de12d50e",
    "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
    "status": "completed",
    "processing_time": 16.32,
    "results": {
        "products_count": 3,
        "services_count": 1,
        "total_items": 4,
        "ai_provider": "gemini",
        "template_used": "InsuranceExtractionTemplate"
    },
    "raw_content": "--- DỊCH VỤ AIA VIỆT NAM ---\n\nCông ty AIA Việt Nam cung cấp...",
    "structured_data": {
        "products": [
            {
                "name": "AIA – Khỏe Trọn Vẹn",
                "type": "Bảo hiểm liên kết chung",
                "description": "Bảo vệ tài chính trước rủi ro...",
                "coverage_period": "30 năm",
                "premium": "Tùy thuộc vào tuổi, giới tính..."
            }
        ],
        "services": [
            {
                "name": "AIA Vitality",
                "type": "Chương trình ưu đãi",
                "description": "Chương trình khuyến khích...",
                "pricing": "Tích hợp vào sản phẩm bảo hiểm"
            }
        ]
    },
    "extraction_metadata": {
        "ai_provider": "gemini",
        "template_used": "InsuranceExtractionTemplate",
        "industry": "insurance",
        "file_name": "SanPham-AIA.txt"
    },
    "timestamp": "2025-07-27T11:02:27.443808"
}
```

## 4. Backend Implementation Example

```javascript
const crypto = require('crypto');
const express = require('express');
const app = express();

// Webhook secret - phải giống với AI Service
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || "webhook-secret-for-signature";

function verifyWebhookSignature(payload, receivedSignature, secret) {
    const expectedSignature = crypto
        .createHmac('sha256', secret)
        .update(payload, 'utf8')
        .digest('hex');
    
    const expectedHeader = `sha256=${expectedSignature}`;
    
    return crypto.timingSafeEqual(
        Buffer.from(receivedSignature),
        Buffer.from(expectedHeader)
    );
}

// Middleware verify signature
function webhookAuth(req, res, next) {
    const signature = req.headers['x-webhook-signature'];
    const payload = JSON.stringify(req.body);
    
    if (!signature) {
        return res.status(401).json({
            success: false,
            error: {
                code: "UNAUTHORIZED",
                message: "Missing webhook signature"
            }
        });
    }
    
    if (!verifyWebhookSignature(payload, signature, WEBHOOK_SECRET)) {
        return res.status(401).json({
            success: false,
            error: {
                code: "UNAUTHORIZED", 
                message: "Invalid webhook signature"
            }
        });
    }
    
    next();
}

// File upload callback endpoint
app.post('/api/webhooks/file-processed', webhookAuth, (req, res) => {
    const { file_id, company_id, status, processing_time } = req.body;
    
    console.log(`File ${file_id} processed for company ${company_id}`);
    console.log(`Status: ${status}, Time: ${processing_time}s`);
    
    // Xử lý logic business
    // - Cập nhật database
    // - Gửi notification cho user
    // - Trigger next workflow
    
    res.json({
        success: true,
        message: "File upload callback received"
    });
});

// AI extraction callback endpoint  
app.post('/api/webhooks/ai/extraction-callback', webhookAuth, (req, res) => {
    const { 
        task_id, 
        company_id, 
        status, 
        results, 
        raw_content, 
        structured_data,
        extraction_metadata 
    } = req.body;
    
    console.log(`Extraction ${task_id} completed for company ${company_id}`);
    console.log(`Products: ${results.products_count}, Services: ${results.services_count}`);
    console.log(`Raw content: ${raw_content ? raw_content.length : 0} characters`);
    
    // Xử lý logic business
    // - Lưu raw_content vào database
    // - Lưu structured_data.products vào bảng products
    // - Lưu structured_data.services vào bảng services
    // - Cập nhật extraction status
    // - Notify user về kết quả
    
    // Example: Save products to database
    if (structured_data.products) {
        structured_data.products.forEach(async (product) => {
            await db.products.create({
                company_id: company_id,
                name: product.name,
                type: product.type,
                description: product.description,
                premium: product.premium,
                // ... other product fields
            });
        });
    }
    
    // Example: Save services to database
    if (structured_data.services) {
        structured_data.services.forEach(async (service) => {
            await db.services.create({
                company_id: company_id,
                name: service.name,
                type: service.type,
                description: service.description,
                pricing: service.pricing,
                // ... other service fields
            });
        });
    }
    
    res.json({
        success: true,
        message: "Extraction callback received and data saved",
        processed_items: results.total_items
    });
});
```

## 5. Security Best Practices

1. **Always verify signature**: Không bao giờ tin tưởng webhook không có signature
2. **Use environment variables**: Store webhook secret trong environment
3. **Implement timeout**: Set timeout cho webhook processing
4. **Log webhook events**: Ghi log để debug và monitoring
5. **Return proper status codes**: 200 for success, 4xx for client errors
6. **Implement idempotency**: Handle duplicate webhooks gracefully

## 6. Testing Webhook Integration

### Test với curl:
```bash
# Tạo test signature
SECRET="webhook-secret-for-signature"
PAYLOAD='{"test":"data"}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

# Gửi test webhook
curl -X POST http://localhost:8001/api/webhooks/ai/extraction-callback \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Source: ai-service" \
  -H "X-Webhook-Signature: sha256=$SIGNATURE" \
  -H "User-Agent: Agent8x-AI-Service/1.0" \
  -d "$PAYLOAD"
```

### Expected Response:
```javascript
{
    "success": true,
    "message": "Extraction callback received"
}
```
