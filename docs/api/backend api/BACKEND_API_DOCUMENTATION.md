# Agent8x Backend API Documentation

## Tổng quan
Agent8x Backend API cung cấp các dịch vụ quản lý công ty, xử lý tệp tin, trò chuyện AI và thanh toán qua Stripe. API được xây dựng với Node.js, TypeScript và Express.js.

**Base URL**: `https://api.agent8x.io.vn/api`
**Version**: 1.0.0

---

## Authentication

### Firebase Authentication
Tất cả API endpoints (trừ webhooks và health check) yêu cầu Firebase Authentication token trong header:

```
Authorization: Bearer <firebase_id_token>
```

### API Response Format
Tất cả API responses đều có format chuẩn:

```json
{
  "success": true|false,
  "message": "Description",
  "data": {...},
  "error": "Error details (nếu có)"
}
```

---

## 1. Health & System APIs

### GET /health
Kiểm tra trạng thái hệ thống

**Response:**
```json
{
  "success": true,
  "status": "ok",
  "timestamp": "2025-07-13T10:00:00.000Z",
  "version": "1.0.0",
  "environment": "production"
}
```

### GET /
Thông tin API và danh sách endpoints

**Response:**
```json
{
  "success": true,
  "message": "Agent8x Backend API",
  "version": "1.0.0",
  "documentation": "https://docs.agent8x.io.vn",
  "endpoints": {
    "health": "/api/health",
    "companies": "/api/companies",
    "files": "/api/files",
    "conversations": "/api/conversations",
    "billing": "/api/billing"
  }
}
```

---

## 2. Company Management APIs

### POST /companies/register
Đăng ký công ty mới với Firebase Auth

**Request Body:**
```json
{
  "name": "Công ty ABC",
  "industry": "banking",
  "phone": "+84901234567",
  "website": "https://example.com",
  "email": "admin@example.com"
}
```

**Industry Values:**
- `banking`: Ngân hàng
- `insurance`: Bảo hiểm  
- `restaurant`: Nhà hàng
- `hotel`: Khách sạn
- `retail`: Bán lẻ
- `fashion`: Thời trang
- `industrial`: Công nghiệp
- `healthcare`: Y tế
- `education`: Giáo dục
- `real_estate`: Bất động sản
- `automotive`: Ô tô
- `technology`: Công nghệ
- `consulting`: Tư vấn
- `logistics`: Logistics
- `manufacturing`: Sản xuất
- `other`: Khác

**Response:**
```json
{
  "success": true,
  "message": "Company registered successfully",
  "data": {
    "id": "uuid-company-id",
    "name": "Công ty ABC",
    "industry": "banking",
    "status": "TRIAL",
    "plan": "TRIAL",
    "trialEndsAt": "2025-07-20T10:00:00.000Z",
    "isOnboarded": false
  }
}
```

### GET /companies/me
Lấy thông tin công ty hiện tại với thống kê

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "uuid-company-id",
    "name": "Công ty ABC",
    "industry": "banking",
    "email": "admin@example.com",
    "phone": "+84901234567",
    "website": "https://example.com",
    "status": "TRIAL",
    "plan": "TRIAL",
    "trialStartsAt": "2025-07-13T10:00:00.000Z",
    "trialEndsAt": "2025-07-20T10:00:00.000Z",
    "storageUsed": 1024000,
    "storageLimit": 10737418240,
    "apiCallsCount": 150,
    "apiCallsLimit": 1000,
    "isOnboarded": false,
    "onboardingSteps": {
      "profileCompleted": true,
      "dataUploaded": false,
      "firstChatCompleted": false,
      "integrationSetup": false
    },
    "timezone": "Asia/Ho_Chi_Minh",
    "language": "vi",
    "usage": {
      "files": 5,
      "conversations": 12,
      "storageUsed": 1024000,
      "storageLimit": 10737418240,
      "apiCalls": 150,
      "apiLimit": 1000
    }
  }
}
```

### PUT /companies/me
Cập nhật thông tin công ty

**Request Body:**
```json
{
  "name": "Công ty ABC Updated",
  "phone": "+84901234568",
  "website": "https://newwebsite.com",
  "metadata": {
    "customField": "value"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Company profile updated successfully"
}
```

### GET /companies/stats
Lấy thống kê chi tiết công ty

**Response:**
```json
{
  "success": true,
  "data": {
    "files": {
      "total": 15,
      "processed": 12,
      "failed": 1
    },
    "conversations": {
      "total": 48,
      "today": 3,
      "thisMonth": 25,
      "avgLength": 8.5
    },
    "usage": {
      "apiCalls": 1250,
      "apiLimit": 5000,
      "storageUsed": 2048000,
      "storageLimit": 10737418240
    },
    "intents": {
      "PRODUCT_INQUIRY": 15,
      "SUPPORT": 8,
      "GENERAL": 25
    },
    "channels": {
      "WEB": 30,
      "MOBILE": 15,
      "API": 3
    }
  }
}
```

---

## 3. File Management APIs

### POST /files/upload
Upload multiple files (tối đa 10 files)

**Content-Type:** `multipart/form-data`

**Form Data:**
- `files`: Array of files (max 10)
- `category`: Optional file category
- `metadata`: Optional JSON metadata

**Response:**
```json
{
  "success": true,
  "message": "Files uploaded successfully",
  "data": {
    "uploadedFiles": [
      {
        "id": "uuid-file-id",
        "filename": "document.pdf",
        "originalName": "my-document.pdf",
        "mimeType": "application/pdf",
        "size": 1024000,
        "category": "DOCUMENT",
        "status": "UPLOADED",
        "path": "/uploads/company-id/uuid-file-id.pdf",
        "url": "https://storage.agent8x.io.vn/uploads/company-id/uuid-file-id.pdf"
      }
    ],
    "failedFiles": []
  }
}
```

### GET /files
Lấy danh sách files với phân trang và lọc

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20, max: 100)
- `category`: Filter by category
- `status`: Filter by status
- `search`: Search by filename

**Response:**
```json
{
  "success": true,
  "data": {
    "files": [
      {
        "id": "uuid-file-id",
        "filename": "document.pdf",
        "originalName": "my-document.pdf",
        "mimeType": "application/pdf",
        "size": 1024000,
        "category": "DOCUMENT",
        "status": "PROCESSED",
        "uploadedAt": "2025-07-13T10:00:00.000Z",
        "processedAt": "2025-07-13T10:01:00.000Z",
        "metadata": {}
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 15,
      "totalPages": 1,
      "hasNext": false,
      "hasPrev": false
    }
  }
}
```

### DELETE /files/:fileId
Xóa file

**Response:**
```json
{
  "success": true,
  "message": "File deleted successfully"
}
```

### GET /files/stats/storage
Lấy thống kê storage

**Response:**
```json
{
  "success": true,
  "data": {
    "totalFiles": 15,
    "totalSize": 25600000,
    "sizeByCategory": {
      "DOCUMENT": 15360000,
      "IMAGE": 5120000,
      "VIDEO": 5120000
    },
    "sizeByStatus": {
      "PROCESSED": 20480000,
      "FAILED": 2560000,
      "PROCESSING": 2560000
    },
    "dailyUploads": [
      {
        "date": "2025-07-13",
        "count": 3,
        "size": 5120000
      }
    ]
  }
}
```

---

## 4. Conversation APIs

### GET /conversations
Lấy danh sách conversations với phân trang

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20)
- `status`: Filter by status
- `channel`: Filter by channel
- `intent`: Filter by intent
- `startDate`: Filter from date (ISO string)
- `endDate`: Filter to date (ISO string)

**Response:**
```json
{
  "success": true,
  "data": {
    "conversations": [
      {
        "id": "uuid-conversation-id",
        "sessionId": "session-123",
        "channel": "WEB",
        "status": "COMPLETED",
        "intent": "PRODUCT_INQUIRY",
        "messageCount": 8,
        "startedAt": "2025-07-13T10:00:00.000Z",
        "endedAt": "2025-07-13T10:15:00.000Z",
        "duration": 900,
        "metadata": {},
        "lastMessage": {
          "content": "Cảm ơn bạn đã liên hệ!",
          "role": "assistant",
          "timestamp": "2025-07-13T10:15:00.000Z"
        }
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 48,
      "totalPages": 3,
      "hasNext": true,
      "hasPrev": false
    }
  }
}
```

### GET /conversations/:conversationId
Lấy chi tiết conversation

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "uuid-conversation-id",
    "sessionId": "session-123",
    "channel": "WEB",
    "status": "COMPLETED",
    "intent": "PRODUCT_INQUIRY",
    "messageCount": 8,
    "startedAt": "2025-07-13T10:00:00.000Z",
    "endedAt": "2025-07-13T10:15:00.000Z",
    "duration": 900,
    "metadata": {
      "userAgent": "Mozilla/5.0...",
      "ipAddress": "192.168.1.1"
    }
  }
}
```

### GET /conversations/:conversationId/messages
Lấy messages của conversation

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 50)

**Response:**
```json
{
  "success": true,
  "data": {
    "messages": [
      {
        "id": "uuid-message-id",
        "conversationId": "uuid-conversation-id",
        "role": "user",
        "content": "Cho tôi biết về sản phẩm này",
        "timestamp": "2025-07-13T10:00:00.000Z",
        "metadata": {}
      },
      {
        "id": "uuid-message-id-2",
        "conversationId": "uuid-conversation-id",
        "role": "assistant",
        "content": "Đây là thông tin chi tiết về sản phẩm...",
        "timestamp": "2025-07-13T10:00:30.000Z",
        "metadata": {
          "tokensUsed": 150,
          "responseTime": 800
        }
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 50,
      "total": 8,
      "totalPages": 1,
      "hasNext": false,
      "hasPrev": false
    }
  }
}
```

### GET /conversations/analytics
Lấy analytics conversations

**Query Parameters:**
- `period`: Period for analytics (7d, 30d, 90d - default: 30d)
- `groupBy`: Group by (day, week, month - default: day)

**Response:**
```json
{
  "success": true,
  "data": {
    "period": "30d",
    "summary": {
      "totalConversations": 125,
      "totalMessages": 1200,
      "avgDuration": 720,
      "avgMessagesPerConversation": 9.6,
      "completionRate": 0.85
    },
    "daily": [
      {
        "date": "2025-07-13",
        "conversations": 8,
        "messages": 75,
        "avgDuration": 650,
        "completionRate": 0.875
      }
    ],
    "intentBreakdown": {
      "PRODUCT_INQUIRY": 45,
      "SUPPORT": 25,
      "GENERAL": 55
    },
    "channelBreakdown": {
      "WEB": 80,
      "MOBILE": 35,
      "API": 10
    }
  }
}
```

---

## 5. Billing APIs

### GET /billing/summary
Lấy tổng quan billing

**Response:**
```json
{
  "success": true,
  "data": {
    "currentPlan": "TRIAL",
    "status": "ACTIVE",
    "trialEndsAt": "2025-07-20T10:00:00.000Z",
    "subscriptionStartsAt": null,
    "subscriptionEndsAt": null,
    "nextBillingDate": null,
    "usage": {
      "apiCalls": 150,
      "apiLimit": 1000,
      "storage": 1024000,
      "storageLimit": 10737418240
    },
    "billing": {
      "amount": 0,
      "currency": "USD",
      "interval": null
    }
  }
}
```

### GET /billing/subscription
Lấy thông tin subscription hiện tại

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "sub_123456789",
    "status": "active",
    "currentPeriodStart": "2025-07-01T00:00:00.000Z",
    "currentPeriodEnd": "2025-08-01T00:00:00.000Z",
    "plan": {
      "id": "plan_basic",
      "name": "Basic Plan",
      "amount": 2900,
      "currency": "USD",
      "interval": "month"
    },
    "customer": {
      "id": "cus_123456789",
      "email": "admin@example.com"
    }
  }
}
```

### POST /billing/subscribe
Tạo subscription mới

**Request Body:**
```json
{
  "planId": "price_basic_monthly",
  "paymentMethodId": "pm_123456789"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Subscription created successfully",
  "data": {
    "subscriptionId": "sub_123456789",
    "clientSecret": "pi_123456789_secret_xyz",
    "status": "active"
  }
}
```

### POST /billing/cancel
Hủy subscription

**Response:**
```json
{
  "success": true,
  "message": "Subscription cancelled successfully",
  "data": {
    "subscriptionId": "sub_123456789",
    "cancelAtPeriodEnd": true,
    "currentPeriodEnd": "2025-08-01T00:00:00.000Z"
  }
}
```

### GET /billing/invoices
Lấy danh sách invoices

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20)

**Response:**
```json
{
  "success": true,
  "data": {
    "invoices": [
      {
        "id": "in_123456789",
        "number": "INV-001",
        "status": "paid",
        "amount": 2900,
        "currency": "USD",
        "created": "2025-07-01T00:00:00.000Z",
        "dueDate": "2025-07-01T00:00:00.000Z",
        "paidAt": "2025-07-01T00:05:00.000Z",
        "hostedInvoiceUrl": "https://invoice.stripe.com/i/abc123",
        "invoicePdf": "https://pay.stripe.com/invoice/abc123/pdf"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 5,
      "totalPages": 1,
      "hasNext": false,
      "hasPrev": false
    }
  }
}
```

---

## 6. Webhook APIs

### POST /webhooks/stripe
Stripe webhook endpoint (không cần auth)

**Headers Required:**
- `stripe-signature`: Stripe webhook signature

**Response:**
```json
{
  "success": true,
  "message": "Webhook processed successfully"
}
```

---

## Error Codes

### HTTP Status Codes
- `200`: Success
- `201`: Created
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `409`: Conflict
- `422`: Validation Error
- `429`: Rate Limited
- `500`: Internal Server Error

### Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": {
      "field": "email",
      "message": "Email is required"
    }
  }
}
```

### Common Error Codes
- `VALIDATION_ERROR`: Request validation failed
- `UNAUTHORIZED`: Authentication required
- `FORBIDDEN`: Insufficient permissions
- `NOT_FOUND`: Resource not found
- `ALREADY_EXISTS`: Resource already exists
- `RATE_LIMITED`: Too many requests
- `PAYMENT_REQUIRED`: Payment or subscription required
- `INTERNAL_ERROR`: Server error

---

## Rate Limiting

### Limits by Plan
- **Trial**: 1000 API calls/month
- **Basic**: 10,000 API calls/month
- **Pro**: 100,000 API calls/month
- **Enterprise**: Unlimited

### Rate Limit Headers
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1625097600
```

---

## File Upload Limits

### File Size Limits
- **Single file**: 100MB
- **Total upload**: 500MB per request
- **Supported formats**: PDF, DOC, DOCX, TXT, CSV, JSON, XML, HTML

### Storage Limits by Plan
- **Trial**: 10GB
- **Basic**: 100GB
- **Pro**: 1TB
- **Enterprise**: Unlimited

---

## Data Types

### Industry Types
```typescript
enum Industry {
  BANKING = 'banking',          // Ngân hàng
  INSURANCE = 'insurance',      // Bảo hiểm
  RESTAURANT = 'restaurant',    // Nhà hàng
  HOTEL = 'hotel',             // Khách sạn
  RETAIL = 'retail',           // Bán lẻ
  FASHION = 'fashion',         // Thời trang
  INDUSTRIAL = 'industrial',   // Công nghiệp
  HEALTHCARE = 'healthcare',   // Y tế
  EDUCATION = 'education',     // Giáo dục
  REAL_ESTATE = 'real_estate', // Bất động sản
  AUTOMOTIVE = 'automotive',   // Ô tô
  TECHNOLOGY = 'technology',   // Công nghệ
  CONSULTING = 'consulting',   // Tư vấn
  LOGISTICS = 'logistics',     // Logistics
  MANUFACTURING = 'manufacturing', // Sản xuất
  OTHER = 'other'              // Khác
}
```

### Company Status
```typescript
enum CompanyStatus {
  TRIAL = 'TRIAL',
  ACTIVE = 'ACTIVE',
  SUSPENDED = 'SUSPENDED',
  CANCELLED = 'CANCELLED'
}
```

### Plan Types
```typescript
enum PlanType {
  TRIAL = 'TRIAL',
  BASIC = 'BASIC',
  PRO = 'PRO',
  ENTERPRISE = 'ENTERPRISE'
}
```

### File Categories
```typescript
enum FileCategory {
  DOCUMENT = 'DOCUMENT',
  IMAGE = 'IMAGE',
  VIDEO = 'VIDEO',
  AUDIO = 'AUDIO',
  SPREADSHEET = 'SPREADSHEET',
  PRESENTATION = 'PRESENTATION',
  OTHER = 'OTHER'
}
```

### File Status
```typescript
enum FileStatus {
  UPLOADED = 'UPLOADED',
  PROCESSING = 'PROCESSING',
  PROCESSED = 'PROCESSED',
  FAILED = 'FAILED',
  DELETED = 'DELETED'
}
```

---

## Support

- **Documentation**: https://docs.agent8x.io.vn
- **Support Email**: support@agent8x.io.vn
- **Discord**: https://discord.gg/agent8x
- **GitHub**: https://github.com/agent8x/backend

---

*Last updated: July 13, 2025*
