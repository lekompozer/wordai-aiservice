# Backend Webhook Integration Guide
# Hướng Dẫn Tích Hợp Webhook Cho Backend với Token Analysis

## 📋 Tổng Quan

Tài liệu này hướng dẫn Backend nhận và xử lý các webhook events từ AI Service để lưu trữ và quản lý conversation data với hỗ trợ mới cho **Chat Plugin** channels, **Token Analysis** và **Thinking Data** cho conversation analytics.

## 🆕 **New Features in Latest Update**

### **Enhanced Token Analysis**
- **Input Tokens**: Token count của user message
- **Output Tokens**: Token count của AI response
- **Total Tokens**: Tổng token sử dụng trong conversation
- **Character Count**: Chi tiết số ký tự input/output cho analytics
- **Cost Calculation**: Cơ sở tính toán chi phí AI usage

### **AI Thinking Data Integration**
- **Thinking Content**: Full reasoning process của AI trước khi response
- **Intent Analysis**: Extracted intent từ AI thinking process
- **Confidence Scoring**: Mức độ confidence của AI decisions
- **Response Quality Metrics**: Metrics để đánh giá chất lượng response

### **Chat Plugin Channel Support**
- **Channel**: `chat-plugin` - Website chat widget embedded trên domain của khách hàng
- **Request Source**: Browser của khách hàng (domain khác với AI Service)
- **CORS Requirement**: Dynamic CORS configuration cho từng `pluginId` → `domain` → `companyId`

### **Dynamic CORS Management**
- AI Service cần allow CORS từ customer domains
- Backend quản lý mapping: `pluginId` ↔ `allowedDomains` ↔ `companyId`
- Real-time CORS updates khi customer thay đổi domain

## 🔗 Webhook Events Overview

AI Service sẽ gửi các webhook events đến Backend để đồng bộ dữ liệu conversation theo thời gian thực, bao gồm cả chat-plugin channels từ customer domains với full token analysis và thinking data.

### Base Webhook URL
- **Development**: `http://localhost:8001`
- **Production**: `https://api.agent8x.io.vn`
- **Custom**: Set via `BACKEND_WEBHOOK_URL` environment variable

## 🔐 Security & Authentication

### Simple Secret Verification

Mỗi webhook request sẽ có secret key trong header:

```http
X-Webhook-Source: ai-service
X-Webhook-Secret: your-webhook-secret-key
User-Agent: Agent8x-AI-Service/1.0
Content-Type: application/json
```

## 📡 Webhook Endpoints

### 1. Conversation Events
**Endpoint**: `POST /api/webhooks/ai/conversation`

### 2. Test Connection
**Endpoint**: `POST /api/webhooks/ai/test`

## 🎯 Current Active Events

Backend sẽ nhận **ONLY 2 loại events** sau đây từ AI Service:

### 1. Frontend Channels Event

**Event**: `ai.response.plugin.completed`
**Channels**: `chatdemo`, `chat-plugin`
**Purpose**: Complete conversation data cho frontend channels

### 2. Backend Channels Event

**Event**: `conversation.updated`
**Channels**: `messenger`, `instagram`, `whatsapp`, `zalo`
**Purpose**: Enhanced conversation analytics cho backend channels

---

## 📋 Event Details

## 📋 Event Details

### 1. AI Response Plugin Completed (Frontend Channels)

**Event**: `ai.response.plugin.completed`
**Trigger**: Khi AI hoàn thành response cho frontend channels (chatdemo, chat-plugin)
**Purpose**: Gửi complete conversation data để Backend save conversation history

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
    "pluginId": "562e86a5-5f75-42b3-8d06-9bffda7304f7",
    "customerDomain": "agent8x.io.vn",
    "userInfo": {
      "user_id": "anon_dev_vuix49",
      "device_id": "dev_vuix49",
      "source": "chat-plugin"
    },
    "thinking": {
      "intent": "SALES",
      "persona": "Chuyên viên tư vấn",
      "reasoning": "Khách hàng hỏi về thông tin phòng, cho thấy họ đang quan tâm đến việc đặt phòng..."
    },
    "userMessage": {
      "content": "cho tao thông tin giá phòng đi",
      "messageId": "msg_1755144800409_ah7l7mmn",
      "timestamp": "2025-08-14T04:13:25.000Z"
    },
    "aiResponse": {
      "content": "```json\n{\n  \"thinking\": {\n    \"intent\": \"SALES\",\n    \"persona\": \"Chuyên viên tư vấn\",\n    \"reasoning\": \"Khách hàng hỏi về thông tin phòng...\"\n  },\n  \"final_answer\": \"Chào bạn! Dưới đây là bảng giá một số hạng phòng nổi bật...\"\n}\n```",
      "messageId": "msg_1755144800409_ah7l7mmn_ai",
      "timestamp": "2025-08-14T04:13:27.000Z"
    },
    "metadata": {
      "intent": "unknown",
      "confidence": 0.0,
      "streaming": true,
      "language": "VIETNAMESE",
      "ai_provider": "cerebras",
      "model": "llama3.1-70b",
      "token_usage": {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
      }
    }
  },
  "metadata": {}
}
```

**Key Fields**:
- `messageId`: ID của user message
- `conversationId`: ID conversation
- `userMessage`: **User query** với content, messageId, timestamp
- `aiResponse`: **AI response** với full content, messageId, timestamp
- `thinking`: Extracted thinking object từ AI response (parsed)
- `pluginId` & `customerDomain`: Chỉ có cho chat-plugin channel
- `userInfo`: User identification từ frontend request
- `metadata`: Basic AI metadata (token usage có thể = 0)

**⚠️ NOTES**:
- **No Duplication**: Removed duplicate `response` field - chỉ có `aiResponse.content`
- **Complete History**: Có cả user message và AI response để save full conversation
- **Frontend Only**: Chỉ dành cho chatdemo và chat-plugin channels

### 2. Conversation Updated (Backend Channels)

**Event**: `conversation.updated`
**Trigger**: Khi AI hoàn thành response cho backend channels (messenger, instagram, whatsapp, zalo)
**Purpose**: Enhanced conversation analytics với full token analysis và thinking data

```json
{
  "event": "conversation.updated",
  "companyId": "comp_123456",
  "timestamp": "2025-08-13T10:30:35.000Z",
  "data": {
    "conversationId": "conv_abc123",
    "status": "ACTIVE",
    "messageCount": 3,
    "endedAt": null,
    "summary": "Khách hàng hỏi về lãi suất vay",
    "satisfactionScore": null,
    "channel": "messenger",
    "intent": "information",

    // 🆕 AI Thinking Data - RAW FULL JSON từ AI Response
    "thinking": "{\n  \"intent\": \"ASK_COMPANY_INFORMATION\",\n  \"persona\": \"Chuyên viên tư vấn ngân hàng\",\n  \"reasoning\": \"Khách hàng hỏi về lãi suất vay với số tiền cụ thể, cho thấy họ đang có nhu cầu thực tế về vay vốn. Đây là intent ASK_COMPANY_INFORMATION vì họ cần thông tin chính thức về sản phẩm vay của ngân hàng.\"\n}",

    // 🆕 Last User Message with Character Count
    "lastUserMessage": {
      "content": "Cho tôi biết về lãi suất vay hiện tại",
      "timestamp": "2025-08-13T10:30:32.000Z",
      "messageId": "msg_user_789",
      "metadata": {
        "characterCount": 35
      }
    },

    // 🆕 Last AI Response with Enhanced Token Analysis
    "lastAiResponse": {
      "content": "Tôi có thể giúp bạn tìm hiểu về các gói lãi suất vay hiện tại...",
      "timestamp": "2025-08-13T10:30:35.000Z",
      "messageId": "msg_ai_790",
      "metadata": {
        "intent": "information",        // Mapped từ thinking.intent
        "language": "vietnamese",
        "confidence": 0.9,
        "responseTime": 3.0,

        // 🆕 Enhanced Token Analysis for Cost Tracking
        "tokens": {
          "input": 35,           // User input tokens (word count)
          "output": 245,         // AI output tokens (word count)
          "total": 280           // Total tokens in this exchange
        },

        // 🆕 Character Count Analysis
        "characterCount": {
          "input": 35,           // User input character count
          "output": 1842,        // AI output character count
          "total": 1877          // Total characters
        }
      }
    },

    // User identification for analytics
    "userInfo": {
      "user_id": "user_456789",
      "device_id": "device_abc",
      "source": "messenger",
      "name": null,
      "email": null
    }
  },
  "metadata": {}
}
```

**Key Fields**:
- `conversationId`: ID của conversation được update
- `status`: Trạng thái conversation (`ACTIVE`, `ENDED`)
- `messageCount`: Tổng số messages trong conversation
- `thinking`: **RAW JSON STRING** - Full thinking process từ AI response (không parse)
- `lastUserMessage`: Message cuối cùng của user với character count
- `lastAiResponse`: Response cuối cùng của AI với enhanced token analysis
- `tokens`: Token usage analysis cho cost tracking và performance monitoring
- `characterCount`: Character count analysis cho data usage tracking
- `userInfo`: User identification data cho analytics

**⚠️ NOTES**:
- **Backend Only**: Chỉ dành cho messenger, instagram, whatsapp, zalo channels
- **Enhanced Analytics**: Full token analysis và thinking data cho business intelligence
- **Raw Thinking**: Thinking field chứa raw JSON string, không duplicate trong lastAiResponse.metadata

---

## 🔄 **Channel Routing Summary**

### **Frontend Channels** (chatdemo, chat-plugin)
- **Event**: `ai.response.plugin.completed`
- **Content**: Complete conversation with userMessage + aiResponse
- **Purpose**: Save full conversation history
- **CORS**: Required cho chat-plugin từ customer domains

### **Backend Channels** (messenger, instagram, whatsapp, zalo)
- **Event**: `conversation.updated`
- **Content**: Enhanced analytics với token analysis
- **Purpose**: Business intelligence và cost tracking
- **CORS**: Not required (server-to-server communication)

### **⚠️ Single Webhook Policy**

**NO Duplicates**: Mỗi channel chỉ nhận 1 webhook event:
- **Frontend**: `ai.response.plugin.completed` only
- **Backend**: `conversation.updated` only

---

## 📊 **Event Comparison**

| Aspect | ai.response.plugin.completed | conversation.updated |
|--------|------------------------------|---------------------|
| **Channels** | chatdemo, chat-plugin | messenger, instagram, whatsapp, zalo |
| **Purpose** | Save conversation history | Analytics & cost tracking |
| **User Message** | `userMessage` object | `lastUserMessage` object |
| **AI Response** | `aiResponse` object | `lastAiResponse` object |
| **Content Format** | Raw AI JSON response | Clean final_answer |
| **Token Analysis** | Basic (may be 0) | Enhanced input/output/total |
| **Thinking Data** | Parsed object | Raw JSON string |
| **User Info** | Frontend request data | Analytics data |
| **Plugin Fields** | pluginId, customerDomain | Not applicable |

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
  "lastUpdated": "2025-08-13T10:30:00.000Z"
}
```

### **Backend CORS Management Endpoints**

#### **1. Update Plugin Domain Mapping**

**Development**: `POST http://localhost:8001/api/plugins/{pluginId}/domains`
**Production**: `POST https://api.agent8x.io.vn/api/plugins/{pluginId}/domains`

**Purpose**: Cập nhật danh sách domains được phép cho plugin và thông báo AI Service

**Request Payload**:
```json
{
  "domains": [
    "https://customer-website.com",
    "https://www.customer-website.com"
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
  "domainsCount": 2
}
```

### **AI Service Internal API Endpoints**

Backend gọi các internal endpoints của AI Service để quản lý CORS configuration:

#### **1. Update Plugin Domains**

**Development**: `POST http://localhost:8000/api/internal/cors/update-domains`
**Production**: `POST https://ai.aimoney.io.vn/api/internal/cors/update-domains`

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
    "https://www.customer-website.com"
  ]
}
```

**Success Response (200)**:
```json
{
  "success": true,
  "message": "Successfully updated 2 domains",
  "pluginId": "plugin_123",
  "domainsCount": 2
}
```

## 🏗️ Backend Implementation

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

-- Plugin Domains table (for CORS management)
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
```

## 🧪 Testing

### Test Webhook Connection

```bash
# Test from AI Service
curl -X GET https://ai.aimoney.io.vn/api/unified/webhook/test

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
      "timestamp": "2025-08-13T10:00:00.000Z"
    },
    "timestamp": "2025-08-13T10:00:00.000Z"
  }'

# Test AI Service Internal API endpoints
curl -X POST https://ai.aimoney.io.vn/api/internal/cors/update-domains \
  -H "X-Internal-Key: agent8x-backend-secret-key-2025" \
  -H "Content-Type: application/json" \
  -d '{
    "pluginId": "plugin_123",
    "allowedDomains": ["https://test-domain.com"]
  }'

# Test intent update webhook
curl -X POST http://localhost:8001/api/webhooks/ai/conversation \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Source: ai-service" \
  -H "X-Webhook-Secret: webhook-secret-for-signature" \
  -d '{
    "event": "conversation.intent_updated",
    "companyId": "comp_123",
    "timestamp": "2025-08-13T10:30:30.000Z",
    "data": {
      "conversationId": "conv_abc123",
      "intent": "sales_inquiry",
      "confidence": 0.9,
      "reasoning": "Customer asking about room information",
      "extractedFromAI": true,
      "updatedAt": "2025-08-13T10:30:30.000Z"
    }
  }'
```

## 📈 Event Processing Workflow

### Intent Update Flow

```mermaid
sequenceDiagram
    participant U as User
    participant P as Plugin/Frontend
    participant A as AI Service
    participant B as Backend

    U->>P: Send message
    P->>A: POST /api/unified/chat-stream
    A->>A: Process & Generate Response
    A->>A: Extract intent from AI JSON
    A->>P: Stream response to frontend
    A->>B: Webhook: ai.response.plugin.completed
    A->>B: Webhook: conversation.intent_updated
    B->>B: Update conversation intent
```

## 🚨 Error Handling

### Webhook Validation

Backend cần validate các webhook events:

```javascript
// Validate conversation.intent_updated event
function validateIntentUpdateEvent(data) {
  const required = ['conversationId', 'intent', 'extractedFromAI', 'updatedAt'];
  const validIntents = ['information', 'sales_inquiry', 'support', 'general_chat'];

  for (const field of required) {
    if (!data[field]) {
      throw new Error(`Missing required field: ${field}`);
    }
  }

  if (!validIntents.includes(data.intent)) {
    throw new Error(`Invalid intent: ${data.intent}`);
  }

  if (typeof data.extractedFromAI !== 'boolean') {
    throw new Error('extractedFromAI must be boolean');
  }
}
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
```

---

## 📊 **Token Analysis Benefits for Backend**

### Cost Tracking
- **Input/Output Token Separation**: Phân tích chi phí theo token input vs output
- **Per-Conversation Cost**: Tính toán chi phí từng conversation dựa trên token usage
- **Monthly Usage Reports**: Báo cáo usage và cost theo company/channel

### Performance Analytics
- **Response Quality**: Correlate token count với satisfaction score
- **Efficiency Metrics**: Token-to-value ratio analysis
- **AI Model Optimization**: So sánh performance các AI models

### Business Intelligence
- **Customer Engagement**: Token usage patterns theo conversation intent
- **Channel Performance**: So sánh hiệu quả các channels dựa trên token metrics
- **Content Quality**: Character-to-token ratio cho content optimization

---

## 📊 **Current Implementation Summary**

### **Single Webhook Per Channel Policy**

Để tránh duplicate webhook processing, AI Service hiện tại implement như sau:

#### **Frontend Channels** (chatdemo, chat-plugin):
- **Event**: `ai.response.plugin.completed`
- **Content**: Raw AI response (full JSON string)
- **Timing**: Sau khi streaming hoàn thành
- **Fields**: messageId, conversationId, response, userInfo, thinking, metadata

#### **Backend Channels** (messenger, instagram, whatsapp, zalo):
- **Event**: `conversation.updated`
- **Content**: Structured conversation data với enhanced analytics
- **Timing**: Sau khi conversation được save
- **Fields**: conversationId, status, lastUserMessage, lastAiResponse, thinking, token analysis

### **Key Differences**

| Aspect | Frontend Webhook | Backend Webhook |
|--------|------------------|-----------------|
| **Event Type** | `ai.response.plugin.completed` | `conversation.updated` |
| **Content Format** | Raw AI response string + structured messages | Structured conversation object |
| **User Message** | `userMessage` object with content/messageId/timestamp | `lastUserMessage` object |
| **AI Response** | `aiResponse` object + raw `response` field | `lastAiResponse` object |
| **Conversation History** | Full message pair (user + AI) | Full conversation context |
| **Response Field** | Full JSON with thinking | Clean final_answer only |
| **Token Analysis** | Basic (may be 0) | Enhanced with input/output/total |
| **User Info** | From frontend request | Extracted for analytics |
| **Thinking Data** | Parsed object | Raw JSON string |

### **Fix Applied**

**Problem**: `ai.response.plugin.completed` không có content vì dùng `parsed_response.get("final_answer", "")` nhưng JSON parsing failed.

**Solution**: Changed to use `ai_response` raw content thay vì parsed final_answer:

```python
# Before (BROKEN)
"response": parsed_response.get("final_answer", "")  # Empty when parsing fails

# After (FIXED)
"response": ai_response  # Full raw AI response content
```

**Result**: Frontend webhook giờ có đầy đủ AI response content, không còn empty response field.

---

**🔄 Updated**: January 26, 2025 - Fixed ai.response.plugin.completed content issue, clarified single webhook policy, documented current implementation differences between frontend and backend channels.

**🔄 Previous**: January 26, 2025 - Added enhanced token analysis, thinking data integration, and conversation.updated webhook with full analytics support. Clarified thinking data structure to avoid duplication.
