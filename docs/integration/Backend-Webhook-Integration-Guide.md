# Backend Webhook Integration Guide
# Hướng Dẫn Tích Hợp Webhook Cho Backend

## 📋 Tổng Quan

Tài liệu này hướng dẫn Backend nhận và xử lý các webhook events từ AI Service để lưu trữ và quản lý conversation data với hỗ trợ mới cho **Chat Plugin** channels và **Dynamic CORS** handling.

## 🆕 **New Features in Chat Plugin Integration**

### **Chat Plugin Channel Support**
- **Channel**: `chat-plugin` - Website chat widget embedded trên domain của khách hàng
- **Request Source**: Browser của khách hàng (domain khác với AI Service)
- **CORS Requirement**: Dynamic CORS configuration cho từng `pluginId` → `domain` → `companyId`

### **Dynamic CORS Management**
- AI Service cần allow CORS từ customer domains
- Backend quản lý mapping: `pluginId` ↔ `allowedDomains` ↔ `companyId`
- Real-time CORS updates khi customer thay đổi domain

## 🔗 Webhook Events Overview

AI Service sẽ gửi các webhook events đến Backend để đồng bộ dữ liệu conversation theo thời gian thực, bao gồm cả chat-plugin channels từ customer domains.

### Base Webhook URL
- **Development**: `http://localhost:8001`
- **Production**: `https://api.agent8x.io.vn`
- **Custom**: Set via `BACKEND_WEBHOOK_URL` environment variable

## 🌐 **Dynamic CORS Configuration**

### **CORS Requirements cho Chat Plugin**

Chat Plugin chạy trên domain của khách hàng và gọi trực tiếp đến AI Service:

```javascript
// Plugin running on customer domain
// https://customer-website.com/chat-plugin
fetch('https://ai.aimoney.io.vn/api/unified/chat-stream', {
    method: 'POST',
    body: JSON.stringify({
        channel: 'chat-plugin',
        pluginId: 'plugin_123',
        companyId: 'comp_456'
    })
});
```

**CORS Challenge**: AI Service cần dynamically allow customer domains based on plugin configuration.

### **Domain Management Flow**

```mermaid
graph TD
    A[Customer Setup Plugin] --> B[Backend Stores Domain Mapping]
    B --> C[Backend Notifies AI Service]
    C --> D[AI Service Updates CORS Rules]
    D --> E[Plugin Works on Customer Domain]

    F[Customer Changes Domain] --> G[Backend Updates Mapping]
    G --> H[Backend Notifies AI Service]
    H --> I[AI Service Updates CORS Rules]
```

## 🔐 Security & Authentication

### Simple Secret Verification

Mỗi webhook request sẽ có secret key trong header (tương tự như callback upload):

```http
X-Webhook-Source: ai-service
X-Webhook-Secret: your-webhook-secret-key
User-Agent: Agent8x-AI-Service/1.0
Content-Type: application/json
```



// Test endpoint
app.post('/api/webhooks/ai/test', webhookVerification, (req, res) => {
  console.log('Webhook test received:', req.body);
  res.status(200).json({
    status: 'success',
    message: 'Webhook connection test successful'
  });
});
```

```

## 📡 Webhook Endpoints

### 1. Conversation Events
**Endpoint**: `POST /api/webhooks/ai/conversation`

### 2. Test Connection
**Endpoint**: `POST /api/webhooks/ai/test`

## 🎯 Event Types

### 1. Conversation Created

**Event**: `conversation.created`
**Trigger**: Khi user bắt đầu conversation mới

```json
{
  "event": "conversation.created",
  "companyId": "comp_123456",
  "timestamp": "2025-07-31T10:30:00.000Z",
  "data": {
    "conversationId": "conv_abc123",
    "sessionId": "session_xyz789",
    "channel": "chat-plugin",
    "intent": "sales_inquiry",
    "startedAt": "2025-07-31T10:30:00.000Z",
    "userInfo": {
      "user_id": "anon_web_a1b2c3d4",
      "device_id": "dev_fingerprint_xyz789",
      "source": "chat_plugin",
      "name": "Nguyễn Văn A",
      "email": "nguyenvana@email.com"
    },
    "metadata": {}
  },
  "metadata": {}
}
```

**🔑 Key Fields cho Backend Processing**:

**Core Conversation Data**:
- `conversationId`: ID duy nhất của conversation
- `sessionId`: ID phiên chat
- `channel`: Kênh truy cập (6 channels: `messenger`, `instagram`, `whatsapp`, `zalo`, `chat-plugin`, `chatdemo`)
- `intent`: Ý định được phát hiện (`sales_inquiry`, `information`, `support`, `general_chat`)
- `startedAt`: Thời gian bắt đầu conversation

**👤 User Information** (từ frontend/platform):
- `userInfo.user_id`: ID user (authenticated hoặc anonymous)
- `userInfo.device_id`: Device fingerprint/identifier
- `userInfo.source`: Nguồn technical (`chat_plugin`, `web_device`, `facebook_messenger`, etc.)
- `userInfo.name`: Tên user (nếu có)
- `userInfo.email`: Email user (nếu có)

### 2. Message Created

**Event**: `message.created`
**Trigger**: Khi có tin nhắn mới (từ user hoặc AI)

```json
{
  "event": "message.created",
  "companyId": "comp_123456",
  "timestamp": "2025-07-31T10:30:15.000Z",
  "data": {
    "messageId": "msg_def456",
    "conversationId": "conv_abc123",
    "role": "user",
    "content": "Tôi muốn tìm hiểu về lãi suất vay",
    "timestamp": "2025-07-31T10:30:15.000Z",
    "userInfo": {
      "user_id": "anon_web_a1b2c3d4",
      "device_id": "dev_fingerprint_xyz789",
      "source": "chat_plugin",
      "name": "Nguyễn Văn A",
      "email": "nguyenvana@email.com"
    },
    "metadata": {
      "intent": "sales_inquiry",
      "language": "VIETNAMESE",
      "confidence": 0.85
    }
  },
  "metadata": {}
}
```

**🔑 Key Fields cho Backend Processing**:

**Core Message Data**:
- `messageId`: ID duy nhất của tin nhắn
- `conversationId`: ID conversation chứa tin nhắn
- `role`: Vai trò (`user` hoặc `assistant`)
- `content`: Nội dung tin nhắn
- `timestamp`: Thời gian tin nhắn

**👤 User Information** (từ conversation context):
- `userInfo.user_id`: ID user liên kết với tin nhắn
- `userInfo.device_id`: Device identifier
- `userInfo.source`: Nguồn technical
- `userInfo.name`: Tên user
- `userInfo.email`: Email user

**📊 Message Metadata**:
- `metadata.intent`: Intent của tin nhắn (cho AI messages)
- `metadata.language`: Ngôn ngữ tin nhắn
- `metadata.confidence`: Độ tin cậy intent detection

### 3. Conversation Updated

**Event**: `conversation.updated`
**Trigger**: Khi conversation có thay đổi status hoặc metadata

```json
{
  "event": "conversation.updated",
  "companyId": "comp_123456",
  "timestamp": "2025-07-31T10:35:00.000Z",
  "data": {
    "conversationId": "conv_abc123",
    "status": "ACTIVE",
    "messageCount": 4,
    "endedAt": null,
    "summary": null,
    "satisfactionScore": null
  },
  "metadata": {}
}
```

**Fields**:
- `status`: Trạng thái conversation (`ACTIVE`, `COMPLETED`, `ABANDONED`)
- `messageCount`: Tổng số tin nhắn trong conversation
- `endedAt`: Thời gian kết thúc (nếu có)
- `summary`: Tóm tắt conversation (nếu có)
- `satisfactionScore`: Điểm hài lòng (nếu có)

### 4. AI Response Completed

**Event**: `ai.response.completed`
**Trigger**: Khi AI hoàn thành response cho backend channels (messenger, instagram, whatsapp, zalo) và frontend channels (chatdemo, chat-plugin)

```json
{
  "event": "ai.response.completed",
  "companyId": "comp_123456",
  "timestamp": "2025-07-31T10:30:25.000Z",
  "data": {
    "messageId": "msg_jkl012",
    "conversationId": "conv_abc123",
    "response": "Tôi có thể giúp bạn tìm hiểu về các gói lãi suất vay hiện tại...",
    "processingTime": 2.3,
    "channel": "messenger",
    "pluginId": "plugin_123456", // ✅ CHỈ CÓ KHI channel = "chat-plugin" - QUAN TRỌNG cho Backend xác định plugin
    "customerDomain": "https://customer-website.com", // ✅ CHỈ CÓ KHI channel = "chat-plugin" - Domain của khách hàng
    "userInfo": {
      "user_id": "fb_user_98765",
      "device_id": "mobile_device_123",
      "source": "facebook_messenger",
      "name": "Trần Thị B",
      "email": "tranthib@email.com"
    },
    "thinking": {
      "intent": "SALES",
      "persona": "Chuyên viên tư vấn tài chính",
      "reasoning": "Khách hàng đang hỏi về lãi suất vay thông qua Messenger, có ý định mua sản phẩm"
    },
    "metadata": {
      "intent": "loan_inquiry",
      "confidence": 0.95,
      "language": "VIETNAMESE",
      "ai_provider": "cerebras",
      "model": "qwen-3-235b-a22b-instruct-2507",
      "token_usage": {
        "prompt_tokens": 1180,
        "completion_tokens": 340,
        "total_tokens": 1520
      }
    }
  },
  "metadata": {}
}
```

**🔑 Key Fields cho Backend Processing**:

**Core Response Data**:
- `messageId`: ID của AI response message
- `conversationId`: ID conversation
- `response`: Nội dung phản hồi của AI
- `processingTime`: Thời gian xử lý (giây)
- `channel`: Channel (`messenger`, `instagram`, `whatsapp`, `zalo`, `chat-plugin`, `chatdemo`)

**🔌 Plugin-specific Fields** (CHỈ KHI channel = "chat-plugin"):
- `pluginId`: ID của plugin - **QUAN TRỌNG** để Backend xác định plugin nào gửi request
- `customerDomain`: Domain của khách hàng sử dụng plugin

**👤 User Information** (từ platform API hoặc frontend):
- `userInfo.user_id`: Platform user ID (Facebook ID, WhatsApp số điện thoại, anonymous ID, etc.)
- `userInfo.device_id`: Device identifier từ platform hoặc browser fingerprint
- `userInfo.source`: Nguồn platform (`facebook_messenger`, `whatsapp`, `instagram`, `zalo`, `chat_plugin`, `web_device`)
- `userInfo.name`: Tên user từ platform profile hoặc frontend input
- `userInfo.email`: Email user (nếu platform hoặc frontend cung cấp)

**🧠 AI Thinking Details** (từ AI response):
- `thinking.intent`: Intent được AI phân tích
- `thinking.persona`: Vai trò AI đảm nhận
- `thinking.reasoning`: Lý do AI chọn intent và persona đó

**📊 Advanced Metadata**:
- `metadata.language`: Ngôn ngữ response
- `metadata.ai_provider`: AI provider đã sử dụng
- `metadata.model`: Model cụ thể
- `metadata.token_usage`: Chi tiết token consumption

### 5. 🆕 AI Response Plugin Completed

**Event**: `ai.response.plugin.completed`
**Trigger**: Khi AI hoàn thành response cho frontend channels (chatdemo, chat-plugin)

```json
{
  "event": "ai.response.plugin.completed",
  "companyId": "comp_123456",
  "timestamp": "2025-08-14T04:13:27.000Z",
  "data": {
    "messageId": "msg_1755144800409_ah7l7mmn",
    "conversationId": "sess_dev_vuix_1755098277",
    "processingTime": 1.8,
    "channel": "chat-plugin",
    "userInfo": {
      "user_id": "anon_dev_vuix49",
      "device_id": "dev_vuix49",
      "source": "chat-plugin"
    },
    "thinking": {
      "intent": "SALES",
      "persona": "Chuyên viên tư vấn",
      "reasoning": "Khách hàng hỏi về thông tin phòng, cho thấy họ đang quan tâm đến việc đặt phòng và có xu hướng tìm hiểu để đặt phòng. Đây là dấu hiệu rõ ràng của ý định mua hàng hoặc so sánh lựa chọn, do đó intent phù hợp là SALES."
    },
    "userMessage": {
      "content": "cho tao thông tin giá phòng đi",
      "messageId": "msg_1755144800409_ah7l7mmn",
      "timestamp": "2025-08-14T04:13:25.000Z"
    },
    "aiResponse": {
      "content": "```json\n{\n  \"thinking\": {\n    \"intent\": \"SALES\",\n    \"persona\": \"Chuyên viên tư vấn\",\n    \"reasoning\": \"Khách hàng yêu cầu thông tin giá phòng, cho thấy họ đang quan tâm đến các lựa chọn lưu trú và có xu hướng tìm hiểu để đặt phòng. Đây là dấu hiệu rõ ràng của ý định mua hàng hoặc so sánh lựa chọn, do đó intent phù hợp là SALES.\"\n  },\n  \"final_answer\": \"Chào bạn! Dưới đây là bảng giá một số hạng phòng nổi bật tại Mermaid Seaside Hotel Vũng Tàu:\\n\\n1. **Superior Standard** (28m²): Chỉ từ **754.691 ₫/đêm** (giảm đến63%), bao gồm bữa sáng, wifi miễn phí, ban công và cửa sổ. Có thể chọn giường đôi hoặc2 giường đơn.\\n\\n2. **Superior Seaview** (30m²): Từ **804.010 ₫/đêm**, hướng nhìn một phần ra biển, ban công, nội thất tiện nghi. Được đánh giá8.3/10 và có chính sách hủy miễn phí.\\n\\n3. **1 Bedroom Apartment**: Từ **1.025.324 ₫/đêm**, phù hợp cho cặp đôi hoặc khách đi công tác, có bếp nhỏ, sofa bed và view đẹp.\\n\\n4. **Grand Family Room** (dành cho6 khách): Từ **2.300.949 ₫/đêm**, không gian rộng rãi, lý tưởng cho gia đình, đi kèm bữa sáng và đánh giá cao (8.6/10).\\n\\nTất cả giá đều đã bao gồm thuế, phí dịch vụ và bữa sáng (trừ một số mức giá đặc biệt), cùng chính sách hủy linh hoạt. Bạn muốn đặt phòng cho bao nhiêu người và trong khoảng thời gian nào vậy? Để mình hỗ trợ kiểm tra phòng trống và ưu đãi tốt nhất nhé!\"\n}\n```",
      "messageId": "msg_1755144800409_ah7l7mmn_ai",
      "timestamp": "2025-08-14T04:13:27.000Z"
    },
    "pluginId": "562e86a5-5f75-42b3-8d06-9bffda7304f7",
    "customerDomain": "agent8x.io.vn",
    "metadata": {
      "streaming": true,
      "language": "VIETNAMESE",
      "ai_provider": "cerebras",
      "model": "qwen-3-235b-a22b-instruct-2507",
      "token_usage": {
        "prompt_tokens": 6,
        "completion_tokens": 257,
        "total_tokens": 263
      }
    }
  },
  "metadata": {}
}
```

**🔑 Key Fields cho Backend Processing**:

**Core Response Data**:
- `messageId`: ID của AI response message
- `conversationId`: ID conversation
- `response`: Nội dung phản hồi của AI (sau khi streaming hoàn thành)
- `processingTime`: Thời gian xử lý (giây)
- `channel`: Frontend channel (`chatdemo`, `chat-plugin`)

**👤 User Information** (từ frontend payload):
- `userInfo.user_id`: ID user từ frontend (authenticated hoặc anonymous)
- `userInfo.device_id`: Device fingerprint từ browser
- `userInfo.source`: Nguồn request (`chat_plugin`, `web_device`)
- `userInfo.name`: Tên user (nếu có)
- `userInfo.email`: Email user (nếu có)

**🧠 AI Thinking Details** (từ AI response):
- `thinking.intent`: Intent được AI phân tích (`SALES`, `ASK_COMPANY_INFORMATION`, `SUPPORT`, `GENERAL_INFORMATION`)
- `thinking.persona`: Vai trò AI đảm nhận (`Chuyên viên tư vấn`, `Lễ tân`, etc.)
- `thinking.reasoning`: Lý do AI chọn intent và persona đó

**🔌 Plugin-specific Fields** (only for chat-plugin channel):
- `pluginId`: ID của chat plugin
- `customerDomain`: Domain của khách hàng

**📊 Advanced Metadata**:
- `metadata.language`: Ngôn ngữ response (`VIETNAMESE`, `ENGLISH`)
- `metadata.ai_provider`: AI provider đã sử dụng (`cerebras`, `openai`, etc.)
- `metadata.model`: Model cụ thể (`qwen-3-235b-a22b-instruct-2507`, `gpt-4`, etc.)
- `metadata.token_usage`: Chi tiết token consumption

### 6. File Processed

**Event**: `file.processed`
**Trigger**: Khi file upload được xử lý xong

```json
{
  "event": "file.processed",
  "companyId": "comp_123456",
  "timestamp": "2025-07-31T10:40:00.000Z",
  "data": {
    "fileId": "file_ghi789",
    "status": "SUCCESS",
    "extractedItems": 15,
    "chunksCreated": 45,
    "processingTime": 12.5,
    "processedAt": "2025-07-31T10:40:00.000Z",
    "errorMessage": null
  },
  "metadata": {}
}
```

**Fields**:
- `fileId`: ID của file được xử lý
- `status`: Trạng thái (`SUCCESS`, `FAILED`, `PROCESSING`)
- `extractedItems`: Số lượng item được trích xuất
- `chunksCreated`: Số chunk được tạo cho vector database
- `processingTime`: Thời gian xử lý (giây)
- `errorMessage`: Thông báo lỗi (nếu có)

## 🔄 **Channel Routing Differences**

### **Frontend Channels** (chatdemo, chat-plugin)
- **Flow**: Browser Request → AI Stream Response → Backend Callback
- **User Experience**: Real-time streaming trong browser
- **Webhook**: `ai.response.plugin.completed` sau khi streaming xong
- **CORS**: Required cho chat-plugin từ customer domains

### **Backend Channels** (messenger, instagram, whatsapp, zalo)
- **Flow**: Platform Webhook → AI Process → Platform Response
- **User Experience**: Traditional request-response
- **Webhook**: `ai.response.completed` sau khi response được gửi
- **CORS**: Not required (server-to-server communication)

## 🔄 **CORS Management for Chat Plugin**

### **CORS Endpoint Requirements**

Backend cần cung cấp endpoint để AI Service query domain mappings cho CORS configuration:

```http
GET /api/cors/plugin-domains?pluginId={pluginId}
```

**Response**:
```json
{
  "pluginId": "plugin_123",
  "companyId": "comp_456",
  "allowedDomains": [
    "https://customer-website.com",
    "https://www.customer-website.com",
    "https://staging.customer-website.com"
  ],
  "lastUpdated": "2025-07-31T10:30:00.000Z"
}
```

### **CORS Update Flow**

```mermaid
sequenceDiagram
    participant C as Customer
    participant B as Backend
    participant A as AI Service
    participant P as Plugin

    C->>B: Update Plugin Domain Settings
    B->>B: Store Domain Mapping
    B->>A: POST /api/internal/cors/update-domains
    A->>A: Update CORS Rules
    A->>B: 200 OK
    B->>C: Settings Updated

    Note over P: Plugin now works on new domain
    P->>A: Chat Request from New Domain
    A->>A: CORS Check Passes
    A->>P: Stream Response
    A->>B: Webhook: ai.response.plugin.completed
```

### **Backend CORS Management Endpoints**

#### **1. Update Plugin Domain Mapping**

**Development**: `POST http://localhost:8001/api/plugins/{pluginId}/domains`
**Production**: `POST https://api.agent8x.io.vn/api/plugins/{pluginId}/domains`

**Purpose**: Cập nhật danh sách domains được phép cho plugin và thông báo AI Service
**Authentication**: Bearer token required

**Request Headers**:
```
Content-Type: application/json
Authorization: Bearer your-api-token
```

**Path Parameters**:
- `pluginId`: ID của plugin (e.g., `plugin_123`)

**Request Payload**:
```json
{
  "domains": [
    "https://customer-website.com",
    "https://www.customer-website.com",
    "https://staging.customer-website.com"
  ],
  "companyId": "comp_456"
}
```

**Success Response (200)**:
```json
{
  "success": true,
  "message": "Plugin domains updated successfully",
  "pluginId": "plugin_123",
  "domainsCount": 3
}
```

**Error Response (400/500)**:
```json
{
  "success": false,
  "error": "Invalid domain format",
  "details": "Domain must start with https://"
}
```

#### **2. Get Plugin Domains**

**Development**: `GET http://localhost:8001/api/cors/plugin-domains?pluginId={pluginId}`
**Production**: `GET https://api.agent8x.io.vn/api/cors/plugin-domains?pluginId={pluginId}`

**Purpose**: Lấy danh sách domains được phép cho plugin (được AI Service gọi)
**Authentication**: None (public endpoint for AI Service)

**Query Parameters**:
- `pluginId`: ID của plugin (required)

**Success Response (200)**:
```json
{
  "pluginId": "plugin_123",
  "companyId": "comp_456",
  "allowedDomains": [
    "https://customer-website.com",
    "https://www.customer-website.com",
    "https://staging.customer-website.com"
  ],
  "lastUpdated": "2025-08-13T10:30:00.000Z"
}
```

**Error Response (404)**:
```json
{
  "pluginId": "plugin_123",
  "companyId": null,
  "allowedDomains": [],
  "lastUpdated": null
}
```

### **AI Service Internal API Endpoints**

Backend cần gọi các internal endpoints của AI Service để quản lý CORS configuration:

#### **1. Update Plugin Domains**

**Development**: `POST http://localhost:8000/api/internal/cors/update-domains`
**Production**: `POST https://ai.aimoney.io.vn/api/internal/cors/update-domains`

**Purpose**: Cập nhật danh sách domains được phép cho plugin
**Authentication**: `X-Internal-Key` header required

**Request Headers**:
```
Content-Type: application/json
X-Internal-Key: agent8x-backend-secret-key-2025
```

**Request Payload**:
```json
{
  "pluginId": "plugin_123",
  "allowedDomains": [
    "https://customer-website.com",
    "https://www.customer-website.com",
    "https://staging.customer-website.com"
  ]
}
```

**Success Response (200)**:
```json
{
  "success": true,
  "message": "CORS domains updated successfully",
  "pluginId": "plugin_123",
  "domainsCount": 3,
  "cacheUpdated": true
}
```

**Error Response (400/500)**:
```json
{
  "success": false,
  "error": "Plugin ID is required",
  "code": "MISSING_PLUGIN_ID"
}
```

#### **2. Clear Plugin Cache**

**Development**: `DELETE http://localhost:8000/api/internal/cors/clear-cache/{plugin_id}`
**Production**: `DELETE https://ai.aimoney.io.vn/api/internal/cors/clear-cache/{plugin_id}`

**Purpose**: Xóa cache CORS cho một plugin cụ thể
**Authentication**: `X-Internal-Key` header required

**Request Headers**:
```
X-Internal-Key: agent8x-backend-secret-key-2025
```

**Path Parameters**:
- `plugin_id`: ID của plugin cần xóa cache (e.g., `plugin_123`)

**Success Response (200)**:
```json
{
  "success": true,
  "message": "Plugin cache cleared successfully",
  "pluginId": "plugin_123",
  "cacheCleared": true
}
```

**Error Response (404)**:
```json
{
  "success": false,
  "error": "Plugin not found in cache",
  "pluginId": "plugin_123"
}
```

#### **3. Clear All Cache**

**Development**: `DELETE http://localhost:8000/api/internal/cors/clear-cache`
**Production**: `DELETE https://ai.aimoney.io.vn/api/internal/cors/clear-cache`

**Purpose**: Xóa toàn bộ CORS cache (emergency use)
**Authentication**: `X-Internal-Key` header required

**Request Headers**:
```
X-Internal-Key: agent8x-backend-secret-key-2025
```

**Success Response (200)**:
```json
{
  "success": true,
  "message": "All CORS cache cleared successfully",
  "cacheCleared": true,
  "timestamp": "2025-08-13T10:30:00.000Z"
}
```

#### **4. Get CORS Middleware Status**

**Development**: `GET http://localhost:8000/api/internal/cors/status`
**Production**: `GET https://ai.aimoney.io.vn/api/internal/cors/status`

**Purpose**: Kiểm tra trạng thái và thống kê của CORS middleware
**Authentication**: `X-Internal-Key` header required

**Request Headers**:
```
X-Internal-Key: agent8x-backend-secret-key-2025
```

**Success Response (200)**:
```json
{
  "status": "active",
  "statistics": {
    "totalPlugins": 15,
    "cachedDomains": 45,
    "requestsProcessed": 1250,
    "cacheHitRate": 0.87,
    "lastCacheUpdate": "2025-08-13T10:25:00.000Z"
  },
  "health": {
    "middleware": "healthy",
    "cache": "healthy",
    "lastHealthCheck": "2025-08-13T10:30:00.000Z"
  }
}
```

### AI Service CORS Configuration

AI Service sẽ automatically query Backend để lấy domain mappings và handle CORS cho chat-plugin requests từ customer domains.

## 🏗️ Backend Implementation

### Database Schema

### Database Schema

```sql
-- Conversations table
CREATE TABLE conversations (
    id VARCHAR(255) PRIMARY KEY,
    company_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    intent VARCHAR(50),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    message_count INT DEFAULT 0,
    summary TEXT NULL,
    satisfaction_score DECIMAL(3,2) NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_company_id (company_id),
    INDEX idx_session_id (session_id),
    INDEX idx_started_at (started_at),
    INDEX idx_status (status)
);

-- Messages table
CREATE TABLE messages (
    id VARCHAR(255) PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_role (role)
);

-- 🆕 Plugin Domains table (for CORS management)
CREATE TABLE plugin_domains (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plugin_id VARCHAR(255) NOT NULL,
    company_id VARCHAR(255) NOT NULL,
    allowed_domains JSON NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY unique_plugin (plugin_id),
    INDEX idx_company_id (company_id),
    INDEX idx_active (is_active)
);

-- File Processing table
CREATE TABLE file_processes (
    id VARCHAR(255) PRIMARY KEY,
    company_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    extracted_items INT DEFAULT 0,
    chunks_created INT DEFAULT 0,
    processing_time DECIMAL(8,2) DEFAULT 0,
    processed_at TIMESTAMP NULL,
    error_message TEXT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_company_id (company_id),
    INDEX idx_status (status),
    INDEX idx_processed_at (processed_at)
);
```
    role ENUM('user', 'assistant') NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_role (role)
);

-- File processing logs
CREATE TABLE file_processing_logs (
    id VARCHAR(255) PRIMARY KEY,
    company_id VARCHAR(255) NOT NULL,
    file_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    extracted_items INT DEFAULT 0,
    chunks_created INT DEFAULT 0,
    processing_time DECIMAL(10,2) DEFAULT 0,
    error_message TEXT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_company_id (company_id),
    INDEX idx_file_id (file_id),
    INDEX idx_status (status)
);
```


```

## 📈 Monitoring & Analytics

### Metrics to Track

1. **Conversation Metrics**:
   - Total conversations per day/month
   - Average conversation duration
   - Message count per conversation
   - Channel distribution

2. **Response Metrics**:
   - Average response time
   - Intent detection accuracy
   - Customer satisfaction scores

3. **System Metrics**:
   - Webhook delivery success rate
   - Processing errors
   - Database performance

### Sample Analytics Queries

```sql
-- Daily conversation stats
SELECT
    DATE(started_at) as date,
    COUNT(*) as total_conversations,
    AVG(message_count) as avg_messages,
    AVG(TIMESTAMPDIFF(MINUTE, started_at, ended_at)) as avg_duration_minutes
FROM conversations
WHERE started_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(started_at)
ORDER BY date DESC;

-- Intent distribution
SELECT
    intent,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM conversations), 2) as percentage
FROM conversations
WHERE started_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY intent
ORDER BY count DESC;

-- Channel performance
SELECT
    channel,
    COUNT(*) as conversations,
    AVG(message_count) as avg_messages,
    AVG(satisfaction_score) as avg_satisfaction
FROM conversations
WHERE started_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY channel
ORDER BY conversations DESC;
```

## 🧪 Testing

### Test Webhook Connection

```bash
# Test from AI Service
curl -X GET https://api.agent8x.io.vn/api/unified/webhook/test

# Direct test to your webhook endpoint
curl -X POST http://localhost:8001/api/webhooks/ai/test \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Source: ai-service" \
  -H "X-Webhook-Secret: webhook-secret-for-signature" \
  -d '{
    "event": "test.connection",
    "companyId": "test",
    "data": {
      "message": "Webhook connection test",
      "timestamp": "2025-07-31T10:00:00.000Z"
    },
    "timestamp": "2025-07-31T10:00:00.000Z"
  }'

# Test AI Service Internal API endpoints
curl -X POST https://ai.aimoney.io.vn/api/internal/cors/update-domains \
  -H "X-Internal-Key: agent8x-backend-secret-key-2025" \
  -H "Content-Type: application/json" \
  -d '{
    "pluginId": "plugin_123",
    "allowedDomains": ["https://test-domain.com"]
  }'

# Test AI Service CORS status
curl -X GET https://ai.aimoney.io.vn/api/internal/cors/status \
  -H "X-Internal-Key: agent8x-backend-secret-key-2025"

# Test clear plugin cache
curl -X DELETE https://ai.aimoney.io.vn/api/internal/cors/clear-cache/plugin_123 \
  -H "X-Internal-Key: agent8x-backend-secret-key-2025"
```

### Development Environment Setup

```bash
# Set environment variables
export WEBHOOK_SECRET="your-webhook-secret"
export DATABASE_URL="mysql://user:pass@localhost:3306/chatbot"
export AI_SERVICE_URL="https://ai.aimoney.io.vn"
export AI_SERVICE_INTERNAL_KEY="your-internal-api-key"

# Start your webhook server
npm start  # or python app.py
```

### Environment Variables

```bash
# Required - Webhook Configuration
WEBHOOK_SECRET=webhook-secret-for-signature

# Required - AI Service Integration
AI_SERVICE_URL=https://ai.aimoney.io.vn
AI_SERVICE_INTERNAL_KEY=agent8x-backend-secret-key-2025

# Required - Database
DATABASE_URL=mysql://user:pass@localhost:3306/chatbot

# Optional - Webhook Settings
WEBHOOK_TIMEOUT=30  # seconds
WEBHOOK_RETRY_COUNT=3
WEBHOOK_MAX_DELAY=30  # seconds

# Optional - CORS Management
CORS_CACHE_TTL=300  # seconds
CORS_UPDATE_RETRY=3  # retry attempts
```

### AI Service Configuration

```bash
# In AI Service .env
BACKEND_WEBHOOK_URL=https://your-backend.com
WEBHOOK_SECRET=webhook-secret-for-signature
INTERNAL_API_KEY=agent8x-backend-secret-key-2025
ENVIRONMENT=production  # or development
```

## � **WEBHOOK PAYLOAD SUMMARY cho Backend Developers**

### **🔑 Key Fields trong mọi webhook**

**Core Event Data** (luôn có):
```json
{
  "event": "conversation.created | message.created | ai.response.completed | ai.response.plugin.completed",
  "companyId": "comp_123456",
  "timestamp": "2025-07-31T10:30:00.000Z",
  "data": { /* event-specific data */ },
  "metadata": {}
}
```

**👤 User Information** (trong `data.userInfo` - quan trọng cho user tracking):
```json
{
  "userInfo": {
    "user_id": "anon_web_a1b2c3d4",        // ✅ Frontend-generated hoặc platform ID
    "device_id": "dev_fingerprint_xyz789",  // ✅ Browser fingerprint hoặc device ID
    "source": "chat_plugin",               // ✅ Technical source (6 values cố định)
    "name": "Nguyễn Văn A",               // ✅ Tên user từ frontend/platform (có thể null)
    "email": "nguyenvana@email.com"       // ✅ Email user từ frontend/platform (có thể null)
  }
}
```

**🧠 AI Thinking Details** (trong `data.thinking` - chỉ có trong AI response webhooks):
```json
{
  "thinking": {
    "intent": "SALES",                     // ✅ AI-analyzed intent (4 values cố định)
    "persona": "Chuyên viên tư vấn",      // ✅ AI role cho response
    "reasoning": "Khách hàng hỏi về..."   // ✅ AI reasoning
  }
}
```

### **📡 Channel Mapping cho Backend Processing**

**6 Channels được Support** (trong `data.channel`):
```
messenger      → Facebook Messenger
instagram      → Instagram Direct
whatsapp       → WhatsApp Business
zalo           → Zalo Official Account
chat-plugin    → Website Chat Widget
chatdemo       → Frontend Chat Demo
```

**Source Technical Values** (trong `userInfo.source`):
```
facebook_messenger → từ messenger channel
instagram          → từ instagram channel
whatsapp          → từ whatsapp channel
zalo              → từ zalo channel
chat_plugin       → từ chat-plugin channel
web_device        → từ chatdemo channel
```

### **🎯 Intent Values cho Business Logic**

**4 Intent Types** (trong `thinking.intent`):
```
SALES                    → Khách hàng có ý định mua/đăng ký
ASK_COMPANY_INFORMATION → Hỏi thông tin công ty/sản phẩm
SUPPORT                 → Cần hỗ trợ kỹ thuật/dịch vụ
GENERAL_INFORMATION     → Hỏi thông tin chung/tư vấn
```

### **💾 Database Storage Recommendations**

**User Tracking**:
- Primary Key: `userInfo.user_id` (luôn có, generated từ deviceId nếu anonymous)
- Secondary: `userInfo.device_id` (browser fingerprint, quan trọng cho anonymous users)
- Source: `userInfo.source` (để biết user đến từ channel nào)

**Conversation Analytics**:
- Intent Distribution: Track `thinking.intent` để phân tích customer behavior
- Channel Performance: Track `data.channel` để đo hiệu quả từng kênh
- Response Quality: Track `thinking.persona` + `metadata.confidence`

**Business Intelligence**:
- Lead Scoring: Combine `thinking.intent` + `userInfo` + conversation history
- Channel ROI: Track conversion từ `data.channel` → actual sales
- User Journey: Follow `userInfo.user_id` across multiple conversations

## �🚨 **Error Handling & Best Practices**

### **Common Error Codes**

**AI Service Internal API Errors**:
- `400`: Bad Request - Missing required fields
- `401`: Unauthorized - Invalid or missing X-Internal-Key
- `404`: Not Found - Plugin not found
- `500`: Internal Server Error - AI Service error

**Backend API Errors**:
- `400`: Bad Request - Invalid payload format
- `401`: Unauthorized - Invalid Bearer token
- `404`: Not Found - Plugin not found
- `500`: Internal Server Error - Database or AI Service communication error

### **Retry Strategy**

- **AI Service calls**: 3 retries with exponential backoff (1s, 2s, 4s)
- **Webhook delivery**: 3 retries with delays (30s, 60s, 120s)
- **Cache updates**: Queue failed updates for background processing

### **Monitoring Requirements**

- Track CORS update success/failure rates
- Monitor plugin domain mapping changes
- Alert on high numbers of failed AI Service calls
- Log all CORS-related errors with plugin context
