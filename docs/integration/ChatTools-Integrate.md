# 🤖 Multi-Channel AI Service Integration v2.1

**Last Updated**: August 13, 2025
**Version**: 2.1 - Channel Routing Architecture
**Changes**: Updated 6-channel architecture with dynamic CORS support

## 📋 Tổng Quan

Tài liệu này mô tả cách tích hợp Multi-Channel platforms (Messenger, Instagram, WhatsApp, Zalo, Chat-Plugin, ChatDemo) với AI Service v2.1 sử dụng dynamic channel routing, streaming response, Lead Source tracking, và enhanced payload structure.

Agent8X v2.1 được thiết kế theo kiến trúc **hybrid multi-channel** với 2 luồng xử lý chính:

### 🤖 **AI Service Integration** (Real-time Chat)
- **Protocol**: HTTP POST với Server-Sent Events (SSE) streaming
- **Endpoint**: `/api/unified/chat-stream`
- **Purpose**: Xử lý tin nhắn real-time và trả về streaming responses
- **Features**: Language detection, Intent recognition, Content streaming

### 📚 **Backend Webhook Integration** (Response Handling)
- **Protocol**: HTTP POST webhooks
- **Endpoint**: `/api/ai/response`
- **Purpose**: Nhận AI responses và route đến đúng platform APIs
- **Features**: Channel routing, Message mapping, Platform delivery

Hệ thống tự động detect channel type và route responses đến đúng destination, đảm bảo seamless experience cho users với streaming AI responses và platform-specific message delivery.

## 🏗️ System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Agent8X Multi-Channel System v2.1                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │  Meta Platforms │    │   Zalo Platform │    │  Frontend Apps  │          │
│  │                 │    │                 │    │                 │          │
│  │ • Messenger     │    │ • Zalo OA       │    │ • ChatDemo      │          │
│  │ • Instagram     │    │ • Webhooks      │    │ • Custom Apps   │          │
│  │ • WhatsApp      │    │ • API Calls     │    │ • Direct API    │          │
│  │ • Meta Webhook  │    │                 │    │                 │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                     Chat Plugin (Dynamic CORS)                          ││
│  │                                                                         ││
│  │ • Customer Websites                                                     ││
│  │ • Domain Validation                                                     ││
│  │ • Real-time Streaming                                                   ││
│  │ • Backend Callbacks                                                     ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
           │                         │                         │
           │ Platform Messages       │ Platform Messages       │ Direct API Calls
           │                         │                         │
           ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Backend API    │    │  Backend API    │    │   AI Service    │
│   (Webhooks)    │    │   (Webhooks)    │    │   (Direct)      │
│                 │    │                 │    │                 │
│ • Message Parse │    │ • Message Parse │    │ • Stream Chat   │
│ • Company ID    │    │ • Company ID    │    │ • JSON Response │
│ • User Context  │    │ • User Context  │    │ • Frontend UI   │
│ • Lead Source   │    │ • Lead Source   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
           │                         │                         │
           │ AI Service Requests     │ AI Service Requests     │
           │                         │                         │
           ▼                         ▼                         │
┌─────────────────────────────────────────────────────────────┐               │
│                    AI Service (Cerebras/OpenAI)             │               │
│                                                             │               │
│ • Language Detection                                        │               │
│ • Intent Recognition                                        │               │
│ • Company Context Processing                                │               │
│ • Streaming Response Generation                             │               │
│ • Industry-specific Responses                               │               │
└─────────────────────────────────────────────────────────────┘               │
           │                         │                                       │
           │ Backend Webhooks        │ Backend Webhooks                      │
           │                         │                                       │
           ▼                         ▼                                       │
┌─────────────────┐    ┌─────────────────┐                                   │
│  Backend API    │    │  Backend API    │                                   │
│ (Response Hand) │    │ (Response Hand) │ ←─────────────────────────────────┘
│                 │    │                 │     Frontend Response (Direct)
│ • Parse AI Resp │    │ • Parse AI Resp │
│ • Extract Answer│    │ • Extract Answer│
│ • Platform API  │    │ • Platform API  │
│ • User Delivery │    │ • User Delivery │
└─────────────────┘    └─────────────────┘
           │                         │
           │ Platform APIs           │ Platform APIs
           │                         │
           ▼                         ▼
┌─────────────────┐    ┌─────────────────┐
│  Meta APIs      │    │   Zalo APIs     │
│                 │    │                 │
│ • Send Message  │    │ • Send Message  │
│ • User Delivery │    │ • User Delivery │
└─────────────────┘    └─────────────────┘
```

## 🎯 Channel Architecture Overview v2.1

Hệ thống Agent8X v2.1 hỗ trợ **6 channels** chính với dynamic routing architecture:

### **Backend Channels** (4 channels)
*(Backend platforms gọi AI Service và xử lý response internally)*

1. **🔵 `messenger`** - Facebook Messenger Business
   - **Integration**: Meta Business Platform
   - **Authentication**: Facebook App verification token
   - **Response Flow**: Platform → Backend → AI Service → Backend → Platform API
   - **Message Format**: Complete response with business context

2. **🟣 `instagram`** - Instagram Business Messaging
   - **Integration**: Meta Business Platform
   - **Authentication**: Instagram Business Account
   - **Response Flow**: Platform → Backend → AI Service → Backend → Platform API
   - **Message Format**: Complete response with visual content support

3. **🟢 `whatsapp`** - WhatsApp Business API
   - **Integration**: Meta Business Platform
   - **Authentication**: WhatsApp Business Account
   - **Response Flow**: Platform → Backend → AI Service → Backend → Platform API
   - **Message Format**: Complete response (24-hour messaging window rule)

4. **💬 `zalo`** - Zalo Official Account
   - **Integration**: Zalo Business Platform
   - **Authentication**: Zalo OA verification
   - **Response Flow**: Platform → Backend → AI Service → Backend → Platform API
   - **Message Format**: Complete response with Vietnamese localization

5. **🌐 `chat-plugin`** - Website Chat Widget
   - **Integration**: Customer website embedding
   - **Authentication**: Plugin ID + Domain validation
   - **Response Flow**: Customer Website → AI Service → Customer Website (direct streaming)
   - **Message Format**: Real-time streaming to frontend
   - **Backend Callback**: Parallel webhook to backend for database storage
   - **🆕 NEW**: Dynamic CORS support for customer domains

### **Frontend Channels** (2 channels)
*(Frontend applications gọi trực tiếp AI Service)*

5. **🌐 `chat-plugin`** - Website Chat Widget
   - **Integration**: Customer website embedding
   - **Authentication**: Plugin ID + Domain validation
   - **Response Flow**: Customer Website → AI Service → Customer Website (direct streaming)
   - **Message Format**: Real-time streaming to frontend
   - **Backend Callback**: Parallel webhook to backend for database storage
   - **🆕 NEW**: Dynamic CORS support for customer domains

6. **🖥️ `chatdemo`** - Frontend Chat Demo/Interface
   - **Integration**: Frontend application (React, Vue, etc.)
   - **Authentication**: Company ID based
   - **Response Flow**: Frontend → AI Service → Frontend (direct streaming)
   - **Message Format**: Real-time streaming chunks
   - **Backend Callback**: Parallel callback to backend for analytics

### **Backend-Initiated Channels**
*(Backend gửi request đến AI Service và xử lý response)*

1. **🔵 `messenger`** - Facebook Messenger
   - Webhook: `/api/meta/webhook`
   - Platform: Facebook Pages API
   - Response: Backend receives AI response → send to user via Messenger API

2. **🟣 `instagram`** - Instagram Direct Message
   - Webhook: `/api/meta/webhook`
   - Platform: Instagram Business API
   - Response: Backend receives AI response → send to user via Instagram API

3. **🟢 `whatsapp`** - WhatsApp Business
   - Webhook: `/api/meta/webhook`
   - Platform: WhatsApp Business API
   - Response: Backend receives AI response → send to user via WhatsApp API
   - **Special Rule**: 24-hour messaging window

4. **💬 `zalo`** - Zalo Official Account
   - Webhook: `/api/zalo/webhook`
   - Platform: Zalo API
   - Response: Backend receives AI response → send to user via Zalo API

### **Frontend-Initiated Channels**
*(Frontend gửi request đến AI Service và tự xử lý response)*

5. **🌐 `chat-plugin`** - Website Chat Widget
   - Source: Customer website embedding
   - API: Direct call from plugin to AI Service
   - Response: **Frontend receives AI response directly**
   - Backend: Parallel webhook for database storage only

6. **🖥️ `chatdemo`** - Frontend Chat Demo
   - Source: Frontend application
   - API: Direct call from frontend to AI Service
   - Response: **Frontend receives AI response directly**
   - **⚠️ LƯU Ý QUAN TRỌNG**: AI Service cần phân biệt channel này để biết trả response về **frontend** chứ không phải backend

---

## 🚨 **Channel Response Routing**

### **Backend Channels** → AI Service trả về Backend
```
User → Platform → Backend Webhook → AI Service → Backend → Platform API → User
```

### **Frontend Channels** → AI Service trả về Frontend
```
User → Frontend → AI Service → Frontend → User
```

**Channels `chat-plugin` và `chatdemo` đặc biệt**: AI Service cần check channel để biết trả response về **frontend** chứ không phải backend!

---

## 🔄 Complete Processing Flow

### 1️⃣ **Backend Channels Processing Flow**
```
User Message → Platform Webhook → Backend Parse → Company Lookup
     ↓
Session Creation → Lead Source Attachment → AI Service Request
     ↓
POST /api/unified/chat-stream → SSE Stream Processing → AI Response
     ↓
Backend Webhook → Response Parsing → Platform API Call → User Delivery
```

### 2️⃣ **Frontend Channel Processing Flow**
```
User Input → Frontend Validation → AI Service Request (Direct)
     ↓
POST /api/unified/chat-stream → SSE Stream Processing → Frontend Updates
     ↓
JSON Parsing → final_answer Extraction → UI Display
     ↓
Optional Backend Callback → Analytics Tracking → Session Update
```

### 3️⃣ **Chat Plugin Processing Flow** (Frontend Channel)
```
User Message → Plugin Widget → AI Service Request (Direct)
     ↓
POST /api/unified/chat-stream → SSE Stream Processing → Plugin UI Updates
     ↓
Real-time Frontend Display → Optional Backend Webhook → Database Storage
     ↓
Domain CORS Validation → Session Tracking → Analytics Update
```

### 4️⃣ **Error Handling Flow**
```
Request Error → Retry Logic → Fallback Response → User Notification
     ↓
Stream Error → Stop Processing → Error Message → Reset State
     ↓
Platform Error → Backend Logging → Alternative Delivery → Support Alert
```

---

## 🌐 Network Communication Patterns

### **Backend to AI Service Pattern**
```
┌─────────────────┐    HTTP POST     ┌─────────────────┐
│   Backend API   │ ──────────────── │   AI Service    │
│   (Webhooks)    │    Streaming     │   (Cerebras)    │
└─────────────────┘                  └─────────────────┘
        │                                     │
        │ Server-Sent Events (SSE)            │
        │ ← data: {"type":"language"}         │
        │ ← data: {"type":"intent"}           │
        │ ← data: {"type":"content"}          │
        │ ← data: {"type":"done"}             │
        │                                     │
        │ Webhook Response                    │
        │ POST /api/ai/response               │
        │ {"company_id", "message_id", ...}   │
        └─────────────────────────────────────┘
```

### **Frontend to AI Service Pattern**
```
┌─────────────────┐    HTTP POST     ┌─────────────────┐
│   Frontend App  │ ──────────────── │   AI Service    │
│   (React/Vue)   │    Streaming     │   (Direct)      │
└─────────────────┘                  └─────────────────┘
        │                                     │
        │ Server-Sent Events (SSE)            │
        │ ← data: {"type":"content"}          │
        │ ← data: {"final_answer": "..."}     │
        │ ← data: {"type":"done"}             │
        └─────────────────────────────────────┘
```

### **Chat Plugin Hybrid Pattern**
```
┌─────────────────┐    HTTP POST     ┌─────────────────┐
│   Chat Plugin   │ ──────────────── │   AI Service    │
│   (Customer)    │    Streaming     │   (CORS)        │
└─────────────────┘                  └─────────────────┘
        │                                    │
        │ SSE Stream (Direct to Plugin)      │
        │ ← Real-time UI Updates             │
        │                                    │
        │            Webhook Callback        │
        │ ┌─────────────────┐                │
        │ │   Backend API   │ ←──────────────┘
        │ │   (Storage)     │
        │ └─────────────────┘
        │ ← Session Tracking
        └─────────────────────────────────────┘
```

### **Platform API Integration Pattern**
```
┌─────────────────┐    Platform APIs ┌─────────────────┐
│   Backend API   │ ──────────────── │  Meta/Zalo APIs │
│   (Response)    │    HTTP POST     │   (Delivery)    │
└─────────────────┘                  └─────────────────┘
        │                                     │
        │ • Authentication Headers            │
        │ • Message Payload                   │
        │ • User Targeting                    │
        │ • Delivery Confirmation             │
        │ ← Success/Error Response            │
        └─────────────────────────────────────┘
```

---

## 📊 Data Flow & State Management

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Multi-Channel State Management                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │   Channel State │    │  Session State  │    │  Message State  │          │
│  │                 │    │                 │    │                 │          │
│  │ • Channel Type  │    │ • Session ID    │    │ • Message ID    │          │
│  │ • Platform Info │    │ • User Context  │    │ • Content       │          │
│  │ • Auth Status   │    │ • Company ID    │    │ • Streaming     │          │
│  │ • CORS Config   │    │ • Lead Source   │    │ • Response Map  │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
              │                        │                        │
              ▼                        ▼                        ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │ Channel Router  │    │ Session Manager │    │ Response Router │
    │                 │    │                 │    │                 │
    │ • Route Logic   │    │ • Context Store │    │ • Message Map   │
    │ • Backend vs    │    │ • Device Track  │    │ • Platform API  │
    │   Frontend      │    │ • Persistence   │    │ • Error Handle  │
    │ • CORS Handle   │    │ • Analytics     │    │ • Delivery      │
    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 🎯 Concept

- **1 Facebook Page**: GnB Software (493031920566909)
- **Nhiều Company**: Test AI của bất kỳ company nào
- **Format Test**: `slug:query` trong tin nhắn
- **Kết quả**: AI trả lời theo context của company được chỉ định

---

## 🔄 Flow Xử Lý

### **Step 1: User Input**
```
👤 User → 📱 GnB Software Page: "aia:Tôi muốn mua bảo hiểm"
```

### **Step 2: Meta Webhook**
```
📱 Facebook → 🔗 Backend: POST /api/meta/webhook
{
  "object": "page",
  "entry": [{
    "id": "493031920566909",
    "messaging": [{
      "sender": {"id": "USER_PSID"},
      "message": {"text": "aia:Tôi muốn mua bảo hiểm"}
    }]
  }]
}
```

### **Step 3: Parse Message**
```javascript
// Extract slug and query
const message = "aia:Tôi muốn mua bảo hiểm";
const [slug, query] = message.split(':', 2);
// slug = "aia"
// query = "Tôi muốn mua bảo hiểm"
```

### **Step 4: Find Company**
```javascript
// Tìm company từ slug
const company = await CompanyModel.findOne({ slug: slug });
// Result: AIA Company data với industry: insurance
```

### **Step 5: Call AI Service**
```javascript
// Gọi AI API với company context
POST https://ai.aimoney.io.vn/api/unified/chat-stream
{
  "message": "User's message text",
  "message_id": "msg_fb_messenger_1691234567890",
  "company_id": "company-uuid",
  "industry": "insurance|banking|hotel|etc",
  "session_id": "messenger_USER_PSID_1691234567890",
  "user_info": {
    "user_id": "FACEBOOK_USER_PSID",
    "device_id": "messenger_USER_PSID",
    "source": "facebook_messenger",
    "name": "User Full Name",
    "email": null,
    "phone": null
  },
  "lead_source": {
    "id": "lead-source-uuid",
    "name": "Facebook Messenger",
    "sourceCode": "FB_MESSENGER",
    "category": "social_media"
  },
  "channel": "messenger",
  "language": "VIETNAMESE"
}
```

### **Step 6: AI Response**
```javascript
// AI trả về response theo context AIA
"Chào bạn! Tôi là AI assistant của AIA.
Chúng tôi có nhiều sản phẩm bảo hiểm:
- Bảo hiểm nhân thọ
- Bảo hiểm sức khỏe
- Bảo hiểm tai nạn
Bạn quan tâm đến loại bảo hiểm nào?"
```

### **Step 7: Send Response**
```javascript
// Gửi qua Messenger API
POST https://graph.facebook.com/v18.0/me/messages
{
  "recipient": {"id": "USER_PSID"},
  "message": {"text": "AI_RESPONSE"}
}
```

---

## 🔧 Enhanced Implementation Features

### **1. Streaming AI Response**
- Sử dụng Server-Sent Events (SSE) streaming từ AI Service
- Realtime processing và extract `final_answer`
- Improved response time và user experience

### **2. Lead Source Integration**
- Auto-attach Lead Source ID to AI requests
- Track conversation source for analytics
- Fallback to first active Lead Source per company

### **3. Channel Identification & Response Routing**
- Clear channel tracking: `messenger`, `instagram`, `whatsapp`, `zalo`, `chat-plugin`, `chatdemo`
- **Backend Channels**: AI Service trả response về Backend để xử lý
- **Frontend Channel (`chatdemo`)**: AI Service trả response trực tiếp về Frontend
- Channel-specific user info và session management
- Enhanced logging với channel context

### **4. Enhanced Error Handling**
- User-friendly error messages
- Automatic fallback responses
- Comprehensive error logging

---

## 🎯 AI Service Payload Structure

### **Enhanced Payload Format**
```json
{
  "message": "User's message text",
  "message_id": "msg_fb_messenger_1691234567890",
  "company_id": "company-uuid",
  "industry": "insurance|banking|hotel|etc",
  "session_id": "messenger_USER_PSID_1691234567890",
  "user_info": {
    "user_id": "FACEBOOK_USER_PSID",
    "device_id": "messenger_USER_PSID",
    "source": "facebook_messenger",
    "name": "User Full Name",
    "email": null,
    "phone": null
  },
  "lead_source": {
    "id": "lead-source-uuid",
    "name": "Facebook Messenger",
    "sourceCode": "FB_MESSENGER",
    "category": "social_media"
  },
  "channel": "messenger",
  "language": "VIETNAMESE"
}
```

### **Channel Values & Response Routing**

#### **Backend-Handled Channels** *(AI Service → Backend → Platform)*
- `"channel": "messenger"` → Backend receives response → Send via Facebook Messenger API
- `"channel": "instagram"` → Backend receives response → Send via Instagram API
- `"channel": "whatsapp"` → Backend receives response → Send via WhatsApp Business API
- `"channel": "zalo"` → Backend receives response → Send via Zalo API

#### **Frontend-Handled Channels** *(AI Service → Frontend)*
- `"channel": "chat-plugin"` → **Frontend receives response directly** + Backend webhook for storage
- `"channel": "chatdemo"` → **Frontend receives response directly**

### **Key Enhancements**
1. **Message ID**: Unique identifier để track và map requests với responses
2. **Lead Source Object**: Provides marketing attribution tracking
3. **Channel Field**: **⚠️ CRITICAL** - Determines response routing destination
4. **Enhanced User Info**: More complete user context
5. **Session ID**: Unique per channel và timestamp

---

## 🌊 Streaming Response Processing

### **How Streaming Works**
```typescript
// 1. Call AI Service endpoint
const response = await fetch(`${AI_SERVICE_URL}/api/unified/chat-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(enhancedPayload)
});

// 2. Process streaming response
const reader = response.body?.getReader();
let accumulatedContent = '';
let finalAnswer = '';

while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    accumulatedContent += new TextDecoder().decode(value);

    // Extract final_answer as we stream
    if (accumulatedContent.includes('"final_answer":')) {
        const match = accumulatedContent.match(/"final_answer":\s*"([^"]*(?:\\.[^"]*)*)"/);
        if (match) {
            finalAnswer = match[1]
                .replace(/\\n/g, '\n')
                .replace(/\\"/g, '"')
                .replace(/\\\\/g, '\\');
        }
    }
}

// 3. Send only final_answer to user
await sendPlatformMessage(finalAnswer);
```

### **Expected AI Service Response Format**
```json
{
  "thinking": {
    "intent": "product_inquiry",
    "reasoning": "User asking about insurance products",
    "language": "VIETNAMESE"
  },
  "intent": "product_inquiry",
  "language": "VIETNAMESE",
  "final_answer": "Chào bạn! Tôi là AI assistant của AIA. Chúng tôi có các sản phẩm bảo hiểm sau..."
}
```

---

## 🎯 **AI Service Message ID Flow**

### **📋 Message ID Tracking Logic**

**⚠️ QUAN TRỌNG**: AI Service **KHÔNG tạo** `message_id`. AI Service **nhận** `message_id` từ Backend và **trả về** trong webhook để Backend mapping.

#### **🔄 Complete Message ID Flow**

1. **Backend generates message_id** khi nhận user message
2. **Backend sends message_id** to AI Service trong request payload
3. **AI Service processes** và **returns same message_id** trong webhook response
4. **Backend uses message_id** để map response với original user context

```
📱 User Message → 🔗 Backend (generates msg_123) → 🤖 AI Service (receives msg_123)
                                                           ↓
📱 User Receives ← 🔗 Backend (maps msg_123) ← 🤖 AI Service (returns msg_123)
```

### **🔧 Implementation Steps**

#### **Step 1: Backend Generates Message ID**
```typescript
// Backend tạo unique message_id khi nhận user message
const messageId = `msg_${channel}_${userId}_${Date.now()}`;

// Store message context cho mapping sau này
await MessageContext.create({
  messageId: messageId,
  companyId: company.id,
  userId: senderId,
  channel: 'messenger',
  platform: 'facebook',
  userInfo: userProfile,
  timestamp: new Date()
});
```

#### **Step 2: Backend Sends to AI Service**
```typescript
// Gửi message_id trong AI Service request
const aiPayload = {
  message: userText,
  message_id: messageId,  // 🔥 Backend-generated ID
  company_id: company.id,
  user_info: userInfo,
  channel: 'messenger'
  // ...other fields
};

await fetch(`${AI_SERVICE_URL}/api/unified/chat-stream`, {
  method: 'POST',
  body: JSON.stringify(aiPayload)
});
```

#### **Step 3: AI Service Returns Same Message ID**
```typescript
// AI Service gửi webhook với SAME message_id
const webhookPayload = {
  company_id: request.company_id,
  message_id: request.message_id,  // 🔥 Same ID from Backend
  event: "ai.response.ready",
  channel: request.channel,
  structured_response: aiResponse
};

await sendWebhook('/api/ai/response', webhookPayload);
```

#### **Step 4: Backend Maps Response**
```typescript
// Backend webhook handler
app.post('/api/ai/response', async (req, res) => {
  const { company_id, message_id, channel, structured_response } = req.body;

  // ✅ Use message_id để get original context
  const messageContext = await MessageContext.findOne({
    messageId: message_id,
    companyId: company_id
  });

  if (!messageContext) {
    logger.error(`Message context not found for ID: ${message_id}`);
    return res.status(404).json({ error: 'Message context not found' });
  }

  // ✅ Send response to original user
  const finalAnswer = structured_response.final_answer;
  await sendPlatformMessage(messageContext, finalAnswer);

  // ✅ Clean up message context (optional)
  await MessageContext.deleteOne({ messageId: message_id });
});
```

### **📋 Response Format Overview**

AI Service trả về **cùng một JSON structure** cho tất cả channels, nhưng cách xử lý khác nhau:

#### **🔄 Standard AI Response Format**
```json
{
  "thinking": {
    "intent": "product_inquiry|company_information|support|general_information",
    "persona": "Chuyên viên tư vấn|Lễ tân|Chuyên viên hỗ trợ",
    "reasoning": "Detailed analysis of user intent",
    "language": "VIETNAMESE|ENGLISH"
  },
  "intent": "product_inquiry",
  "language": "VIETNAMESE",
  "final_answer": "Actual response content for user display"
}
```

### **🔀 Channel-Based Response Processing**

#### **📤 Backend Channels Response (messenger, instagram, whatsapp, zalo, chat-plugin)**

**AI Service → Backend Endpoint**: `/api/ai/response`

**Required Headers:**
```http
Content-Type: application/json
X-Webhook-Source: ai-service
X-Webhook-Secret: ${WEBHOOK_SECRET}
```

**⚠️ Header Notes:**
- **X-Webhook-Secret**: Sử dụng từ environment variable `WEBHOOK_SECRET` (production.env)
- **No Authorization Bearer**: Không cần vì webhook authentication dùng X-Webhook-Secret
- **No tracking headers**: X-Request-ID và X-Timestamp bỏ để tối ưu performance

**Request Payload:**
```json
{
  "company_id": "company-uuid",
  "message_id": "msg_1691234567890",
  "event": "ai.response.ready",
  "channel": "messenger|instagram|whatsapp|zalo|chat-plugin",
  "structured_response": {
    // Complete AI response JSON - NO DUPLICATION!
    "thinking": {
      "intent": "product_inquiry",
      "persona": "Chuyên viên tư vấn",
      "reasoning": "User is asking about insurance products",
      "language": "VIETNAMESE"
    },
    "final_answer": "Chào bạn! Tôi là AI assistant của AIA. Chúng tôi có các sản phẩm bảo hiểm: Bảo hiểm nhân thọ, Bảo hiểm sức khỏe, Bảo hiểm tai nạn. Bạn quan tâm đến loại bảo hiểm nào?"
  },
  "metadata": {
    "industry": "insurance",
    "language": "VIETNAMESE",
    "ai_provider": "cerebras",
    "model": "llama3.1-70b",
    "token_usage": {
      "prompt_tokens": 1200,
      "completion_tokens": 350,
      "total_tokens": 1550
    },
    "ai_response_type": "structured_json",
    "parsing_success": true,
    "processing_time_ms": 2450
  }
}
```

**Production cURL Example:**
```bash
# Production webhook call to Backend
curl -X POST https://api.agent8x.io.vn/api/ai/response \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Source: ai-service" \
  -H "X-Webhook-Secret: ${WEBHOOK_SECRET}" \
  -d '{
    "company_id": "aia-company-uuid-2024",
    "message_id": "msg_fb_messenger_1691234567890",
    "event": "ai.response.ready",
    "channel": "messenger",
    "structured_response": {
      "thinking": {
        "intent": "product_inquiry",
        "persona": "Chuyên viên tư vấn AIA",
        "reasoning": "User đang hỏi về sản phẩm bảo hiểm của AIA, cần tư vấn chi tiết các loại bảo hiểm available",
        "language": "VIETNAMESE"
      },
      "final_answer": "Chào bạn! Tôi là AI assistant của AIA. Chúng tôi có các sản phẩm bảo hiểm chính:\n\n🛡️ **Bảo hiểm nhân thọ**: Bảo vệ tài chính cho gia đình\n🏥 **Bảo hiểm sức khỏe**: Chi trả viện phí, điều trị\n⚡ **Bảo hiểm tai nạn**: Bảo vệ khỏi rủi ro bất ngờ\n💰 **Bảo hiểm đầu tư**: Vừa bảo vệ vừa sinh lời\n\nBạn quan tâm đến loại bảo hiểm nào? Tôi sẽ tư vấn chi tiết cho bạn!"
    },
    "metadata": {
      "industry": "insurance",
      "language": "VIETNAMESE",
      "ai_provider": "cerebras",
      "model": "llama3.1-70b",
      "token_usage": {
        "prompt_tokens": 1847,
        "completion_tokens": 421,
        "total_tokens": 2268
      },
      "ai_response_type": "structured_json",
      "parsing_success": true,
      "processing_time_ms": 3210
    }
  }'
```
```

#### **🖥️ Frontend Channel Response (chatdemo)**

**AI Service → Frontend Callback** (if configured):

```json
{
  "company_id": "company-uuid",
  "message_id": "msg_1691234567890",
  "event": "ai.response.completed",
  "channel": "chatdemo",
  "structured_response": {
    // Complete AI response JSON - NO DUPLICATION!
    "thinking": {
      "intent": "product_inquiry",
      "persona": "Chuyên viên tư vấn",
      "reasoning": "User is asking about insurance products",
      "language": "VIETNAMESE"
    },
    "intent": "product_inquiry",
    "language": "VIETNAMESE",
    "final_answer": "Final answer content for user display"
  },
  "metadata": {
    "industry": "insurance",
    "language": "VIETNAMESE",
    "ai_provider": "cerebras",
    "model": "llama3.1-70b",
    "token_usage": {
      "prompt_tokens": 1200,
      "completion_tokens": 350,
      "total_tokens": 1550
    },
    "ai_response_type": "structured_json",
    "parsing_success": true
  }
}
```

### **🛠️ Response Processing Implementation**

#### **Backend Processing (5 channels)**
```typescript
// Backend receives AI response từ webhook `/api/ai/response`
app.post('/api/ai/response', async (req, res) => {
  const { company_id, message_id, channel, structured_response, metadata } = req.body;

  // ✅ CRITICAL: Use message_id để map với original user context
  const messageContext = await getMessageContext(company_id, message_id);

  if (!messageContext) {
    logger.error(`❌ Message context not found for message_id: ${message_id}`);
    return res.status(404).json({ error: 'Message context not found' });
  }

  // Extract final_answer từ structured_response để hiển thị cho user
  const displayMessage = structured_response.final_answer;  // From AI JSON
  const fullResponse = structured_response;  // Complete JSON for business logic

  switch (channel) {
    case 'messenger':
      await sendMessengerMessage(messageContext.user_id, displayMessage);
      break;
    case 'instagram':
      await sendInstagramMessage(messageContext.user_id, displayMessage);
      break;
    case 'whatsapp':
      await sendWhatsAppMessage(messageContext.phone, displayMessage);
      break;
    case 'zalo':
      await sendZaloMessage(messageContext.user_id, displayMessage);
      break;
    case 'chat-plugin':
      await sendWebSocketMessage(messageContext.session_id, displayMessage);
      break;
  }

  // Use fullResponse.thinking, fullResponse.intent for business logic
  await logConversationAnalytics(company_id, fullResponse.thinking, fullResponse.intent);

  // ✅ Clean up message context sau khi xử lý
  await cleanupMessageContext(message_id);

  res.json({ success: true, message_id: message_id });
});

// Helper function để get message context
async function getMessageContext(companyId: string, messageId: string) {
  return await MessageContext.findOne({
    messageId: messageId,
    companyId: companyId
  });
}
```

#### **Frontend Processing (chatdemo)**
```typescript
// Frontend receives streaming response và tự parse JSON
const processAIResponse = async (rawResponse: string) => {
  try {
    // Parse AI JSON response
    const aiData = JSON.parse(rawResponse);

    // Extract final_answer để hiển thị
    const displayContent = aiData.final_answer;

    // Keep debug data riêng (không hiển thị)
    const debugInfo = {
      intent: aiData.intent,
      language: aiData.language,
      thinking: aiData.thinking,
      fullResponse: aiData
    };

    // Update UI với chỉ final_answer
    updateChatUI(displayContent);

    // Log debug info cho development
    console.debug('AI Response Analysis:', debugInfo);

    // Store thinking/intent cho business logic (optional)
    storeConversationMetadata(debugInfo);

  } catch (error) {
    console.error('Failed to parse AI response:', error);
    updateChatUI(rawResponse); // Fallback hiển thị raw response
  }
};
```

### **🔍 Response Field Explanations**

#### **Core Response Fields**
- **`company_id`**: UUID để identify company context (from Backend request)
- **`message_id`**: **Backend-generated** unique identifier để map với original user request
- **`event`**: "ai.response.ready" (Backend) hoặc "ai.response.completed" (Frontend)
- **`channel`**: Channel routing identifier (messenger|instagram|whatsapp|zalo|chat-plugin|chatdemo)
- **`structured_response`**: Complete AI JSON object cho business logic
- **`structured_response.final_answer`**: Clean content cho user display
- **`structured_response.thinking`**: AI analysis including intent, persona, reasoning
- **`structured_response.intent`**: Detected user intent cho automation
- **`structured_response.language`**: Detected language cho localization

#### **Message ID Rules**
- ✅ **Backend creates**: `msg_${channel}_${userId}_${timestamp}`
- ✅ **AI Service receives**: Same `message_id` trong request
- ✅ **AI Service returns**: Same `message_id` trong webhook
- ✅ **Backend maps**: Sử dụng `message_id` để get original user context

#### **Metadata Fields**
- **`ai_response_type`**: "structured_json" indicates proper JSON parsing
- **`parsing_success`**: Boolean indicating successful JSON extraction
- **`token_usage`**: AI model usage stats cho cost tracking
- **`industry`**: Company industry context
- **`ai_provider`**: AI service provider (cerebras, openai, etc.)

### **⚡ Streaming vs Webhook Response Flow**

#### **Frontend Channel (chatdemo) - Streaming**
```
User → Frontend → AI Service (Streaming SSE) → Frontend
                    ↓
               Parse JSON → Extract final_answer → Display
```

#### **Backend Channels - Webhook**
```
User → Platform → Backend → AI Service → Backend Webhook → Platform API → User
                                ↓
                        Parse JSON → Extract final_answer → Send to Platform
```

---

### **🧪 Response Testing & Validation**

#### **Test Backend Response Structure**
```bash
# Test backend endpoint locally
curl -X POST http://localhost:3000/api/ai/response \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Source: ai-service" \
  -H "X-Webhook-Secret: ${WEBHOOK_SECRET}" \
  -H "X-Request-ID: req_test_$(date +%s)" \
  -H "X-Timestamp: $(date -u +%Y-%m-%dT%H:%M:%S.000Z)" \
  -d '{
    "company_id": "test-company-uuid",
    "message_id": "msg_test_1691234567890",
    "event": "ai.response.ready",
    "channel": "messenger",
    "structured_response": {
      "thinking": {
        "intent": "test_inquiry",
        "persona": "Test Assistant",
        "reasoning": "This is a test case for webhook integration",
        "language": "VIETNAMESE"
      },
      "final_answer": "Đây là test response từ AI Service để kiểm tra webhook integration."
    },
    "metadata": {
      "industry": "test",
      "language": "VIETNAMESE",
      "ai_provider": "cerebras",
      "model": "llama3.1-70b",
      "token_usage": {
        "prompt_tokens": 500,
        "completion_tokens": 150,
        "total_tokens": 650
      },
      "ai_response_type": "structured_json",
      "parsing_success": true,
      "processing_time_ms": 1200
    }
  }'

# Expected Response: HTTP 200
{
  "status": "success",
  "message": "AI response processed successfully",
  "channel": "messenger",
  "message_sent": true,
  "processing_time": "245ms"
}
```

#### **Validate Frontend JSON Parsing**
```typescript
// Test frontend parsing logic
const testAIResponse = `{
  "thinking": {
    "intent": "product_inquiry",
    "persona": "Chuyên viên tư vấn",
    "reasoning": "User asking about insurance products",
    "language": "VIETNAMESE"
  },
  "intent": "product_inquiry",
  "language": "VIETNAMESE",
  "final_answer": "Chào bạn! Tôi có thể giúp bạn tìm hiểu về các sản phẩm bảo hiểm."
}`;

// Should extract only final_answer for display
const parsed = JSON.parse(testAIResponse);
console.log('Display:', parsed.final_answer);
console.log('Metadata:', { intent: parsed.intent, thinking: parsed.thinking });
```

#### **Response Validation Checklist**
- ✅ **Backend generates unique message_id** cho mỗi user request
- ✅ **AI Service receives message_id** trong request payload
- ✅ **AI Service returns same message_id** trong webhook response
- ✅ **Backend maps response** using message_id to original user context
- ✅ **Message context cleanup** sau khi processing completed
- ✅ **Frontend receives complete JSON** và tự extract final_answer
- ✅ **thinking/intent data available** cho business logic
- ✅ **Error handling** cho malformed JSON hoặc missing message context
- ✅ **Fallback display** nếu parsing fails
- ✅ **Token usage tracking** cho cost monitoring
- ✅ **Simplified payload** - loại bỏ duplicate data

---

### **Lead Source Auto-Detection**
```typescript
// Get default Lead Source for company
const leadSource = await LeadSource.findOne({
    companyId: company.id,
    isActive: true
}).sort({ createdAt: 1 }); // First active source

// Include in AI payload
const payload = {
    // ...other fields...
    lead_source: {
        id: leadSource.id,
        name: leadSource.name,
        sourceCode: leadSource.sourceCode,
        category: leadSource.category
    }
};
```

## 📊 Lead Source Integration

### **Lead Source Auto-Detection**
```typescript
// Get default Lead Source for company
const leadSource = await LeadSource.findOne({
    companyId: company.id,
    isActive: true
}).sort({ createdAt: 1 }); // First active source

// Include in AI payload
const payload = {
    // ...other fields...
    lead_source: {
        id: leadSource.id,
        name: leadSource.name,
        sourceCode: leadSource.sourceCode,
        category: leadSource.category
    }
};
```

### **Lead Source Categories**
- `social_media`: Facebook, Instagram platforms
- `messaging`: WhatsApp, Messenger direct
- `website`: Chat plugins, website forms
- `affiliate`: Partner referrals
- `advertising`: Paid campaigns

---

## 🎯 **Key Integration Differences**

### **📋 Response Content Extraction**

#### **Backend Channels (Auto-Extract)**
```typescript
// Backend automatically extracts final_answer
const userMessage = response.message;  // Pre-extracted final_answer
await sendToMessenger(userMessage);    // Direct send to user

// Business logic uses structured data
const { intent, thinking } = response.structured_response;
await updateCRMWithIntent(intent);
```

#### **Frontend Channel (Manual Extract)**
```typescript
// Frontend must parse JSON manually
const aiResponse = await streamingResponse.text();
const parsed = JSON.parse(aiResponse);
const userMessage = parsed.final_answer;  // Extract final_answer
updateChatUI(userMessage);                // Display to user

// Optional: Use thinking/intent for UX
if (parsed.intent === 'product_inquiry') {
  showProductCatalogButton();
}
```

### **🔄 Response Flow Summary**

| Channel | Flow | Response Handling | Display Content |
|---------|------|-------------------|-----------------|
| `messenger` | User→Platform→Backend→AI→Backend→Platform→User | Auto-extracted `message` | `final_answer` only |
| `instagram` | User→Platform→Backend→AI→Backend→Platform→User | Auto-extracted `message` | `final_answer` only |
| `whatsapp` | User→Platform→Backend→AI→Backend→Platform→User | Auto-extracted `message` | `final_answer` only |
| `zalo` | User→Platform→Backend→AI→Backend→Platform→User | Auto-extracted `message` | `final_answer` only |
| `chat-plugin` | User→Plugin→AI→Plugin→User + Backend Webhook | Manual JSON parsing | Extract `final_answer` |
| `chatdemo` | User→Frontend→AI→Frontend→User | Manual JSON parsing | Extract `final_answer` |

### **⚠️ Critical Implementation Notes**

1. **Consistent Content**: All channels hiển thị cùng nội dung từ `final_answer`
2. **Structured Metadata**: `thinking`, `intent`, `language` available cho business logic
3. **Error Fallback**: Nếu JSON parsing fails, hiển thị raw response
4. **Performance**: Backend pre-extracts, Frontend parses real-time
5. **Analytics**: Use `structured_response` cho conversation insights

---

## � **Message Context Management**

### **📋 Message Context Schema**
```typescript
interface MessageContext {
  messageId: string;           // Backend-generated unique ID
  companyId: string;          // Company UUID
  userId: string;             // Platform-specific user ID
  channel: string;            // messenger|instagram|whatsapp|zalo|chat-plugin
  platform: string;          // facebook|instagram|whatsapp|zalo|websocket
  userInfo: {
    user_id: string;
    device_id: string;
    source: string;
    name: string;
    email?: string;
    phone?: string;
  };
  originalMessage: string;    // User's original message text
  timestamp: Date;            // When message was received
  leadSourceId?: string;      // Associated lead source
  sessionId?: string;         // WebSocket session (for chat-plugin)
}
```

### **🔧 Message Context Operations**

#### **Create Context (Before AI Service Call)**
```typescript
async function createMessageContext(
  messageId: string,
  companyId: string,
  userId: string,
  channel: string,
  userInfo: any,
  originalMessage: string,
  leadSourceId?: string
) {
  return await MessageContext.create({
    messageId,
    companyId,
    userId,
    channel,
    platform: getPlatformFromChannel(channel),
    userInfo,
    originalMessage,
    timestamp: new Date(),
    leadSourceId,
    sessionId: channel === 'chat-plugin' ? userId : undefined
  });
}
```

#### **Retrieve Context (In Webhook Handler)**
```typescript
async function getMessageContext(companyId: string, messageId: string) {
  const context = await MessageContext.findOne({
    messageId: messageId,
    companyId: companyId
  });

  if (!context) {
    throw new Error(`Message context not found: ${messageId}`);
  }

  return context;
}
```

#### **Cleanup Context (After Processing)**
```typescript
async function cleanupMessageContext(messageId: string) {
  // Optional: Keep for analytics or delete immediately
  await MessageContext.deleteOne({ messageId: messageId });

  // Alternative: Mark as processed instead of delete
  // await MessageContext.updateOne(
  //   { messageId: messageId },
  //   { processed: true, processedAt: new Date() }
  // );
}
```

### **⏰ Context Lifecycle**

```
1. 👤 User sends message
2. 🔗 Backend creates MessageContext với unique message_id
3. 🔗 Backend calls AI Service với message_id
4. 🤖 AI Service processes và returns webhook với same message_id
5. 🔗 Backend retrieves MessageContext using message_id
6. 🔗 Backend sends response to user
7. 🗑️ Backend cleans up MessageContext
```

### **🚨 Error Scenarios**

#### **Missing Message Context**
```typescript
app.post('/api/ai/response', async (req, res) => {
  const { company_id, message_id, channel } = req.body;

  try {
    const context = await getMessageContext(company_id, message_id);
    // Process normally...
  } catch (error) {
    logger.error(`❌ Message context not found: ${message_id}`, {
      companyId: company_id,
      channel: channel,
      error: error.message
    });

    // Return error to AI Service
    return res.status(404).json({
      error: 'Message context not found',
      message_id: message_id,
      retry: false  // Don't retry this message
    });
  }
});
```

#### **Duplicate Message ID**
```typescript
async function createMessageContext(...args) {
  try {
    return await MessageContext.create({...contextData});
  } catch (error) {
    if (error.code === 11000) { // MongoDB duplicate key
      logger.warn(`⚠️ Duplicate message_id: ${messageId}`);
      // Handle duplicate - maybe update existing or generate new ID
      return await MessageContext.findOne({ messageId: messageId });
    }
    throw error;
  }
}
```

## �🔧 Platform-Specific Implementation

### **Backend-Handled Channels**

#### **1. Messenger Integration** (`channel: "messenger"`)
```typescript
// Backend generates message_id và stores context
const messageId = `msg_messenger_${senderId}_${Date.now()}`;

// Store context để map response later
await MessageContext.create({
  messageId: messageId,
  companyId: company.id,
  userId: senderId,
  channel: 'messenger',
  platform: 'facebook',
  userInfo: userProfile,
  timestamp: new Date()
});

const userInfo = {
    user_id: senderId,           // Facebook PSID
    device_id: `messenger_${senderId}`,
    source: 'facebook_messenger',
    name: userFullName,          // From Meta API
    email: null
};

const aiPayload = {
    message: messageText,
    message_id: messageId,       // 🔥 Backend-generated ID
    company_id: company.id,
    user_info: userInfo,
    lead_source: leadSource,
    channel: 'messenger'
};

// Send to AI Service với message_id
await callAIServiceWithStreaming(aiPayload);

// ✅ AI Service sẽ return webhook với same message_id
// ✅ Backend webhook handler sẽ map response using message_id
```

#### **2. Instagram Integration** (`channel: "instagram"`)
```typescript
const userInfo = {
    user_id: senderId,           // Instagram IGID
    device_id: `instagram_${senderId}`,
    source: 'instagram',
    name: username || senderId,  // Instagram username
    email: null
};

// ✅ Backend receives response và sends to user
await metaService.sendInstagramMessage(instagramConfig, messagePayload);
```

#### **3. WhatsApp Integration** (`channel: "whatsapp"`)
```typescript
const userInfo = {
    user_id: phoneNumber,        // WhatsApp phone number
    device_id: `whatsapp_${phoneNumber}`,
    source: 'whatsapp',
    name: profileName,           // WhatsApp profile name
    email: null,
    phone: phoneNumber
};

// 24-hour window check required for WhatsApp
const can24hReply = await checkWhatsApp24HourWindow(phoneNumber, company.id);

// ✅ Backend receives response và sends to user
await metaService.sendWhatsAppMessage(whatsappConfig, messagePayload);
```

#### **4. Zalo Integration** (`channel: "zalo"`)
```typescript
const userInfo = {
    user_id: zaloUserId,
    device_id: `zalo_${zaloUserId}`,
    source: 'zalo',
    name: zaloDisplayName,
    email: null
};

// ✅ Backend receives response và sends to user
await zaloService.sendMessage(zaloConfig, messagePayload);
```

### **Frontend-Handled Channels**

#### **5. Chat Plugin Integration** (`channel: "chat-plugin"`)
```typescript
// ⚠️ FRONTEND CHANNEL: Plugin calls AI Service directly
const userInfo = {
    user_id: sessionId,
    device_id: `web_${sessionId}`,
    source: 'website',
    name: visitorName || 'Anonymous',
    email: visitorEmail || null
};

const aiPayload = {
    message: userMessage,
    company_id: companyId,
    user_info: userInfo,
    channel: "chat-plugin",  // 🔥 CRITICAL: AI Service returns response to Frontend
    language: "VIETNAMESE"
};

// Plugin calls AI Service directly
const response = await fetch('/api/unified/chat-stream', {
    method: 'POST',
    body: JSON.stringify(aiPayload)
});

// ✅ Plugin receives response directly và handles UI updates
const finalAnswer = await processStreamingResponse(response);
updatePluginUI(finalAnswer);

// ✅ Backend receives parallel webhook for database storage
```

#### **6. Chat Demo Integration** (`channel: "chatdemo"`)
```typescript
// ⚠️ SPECIAL CASE: Frontend calls AI Service directly
const aiPayload = {
    message: userMessage,
    company_id: companyId,
    user_info: frontendUserInfo,
    lead_source: selectedLeadSource,
    channel: "chatdemo",  // 🔥 CRITICAL: AI Service uses this to return response to Frontend
    language: "VIETNAMESE"
};

// Frontend calls AI Service directly
const response = await fetch('/api/unified/chat-stream', {
    method: 'POST',
    body: JSON.stringify(aiPayload)
});

// ✅ Frontend receives response directly và handles UI updates
const finalAnswer = await processStreamingResponse(response);
updateChatUI(finalAnswer);
```

---

## ⚠️ **Critical Channel Routing Rules**

### **AI Service Response Logic**
```typescript
// In AI Service:
if (payload.channel === 'chatdemo' || payload.channel === 'chat-plugin') {
    // Return response directly to Frontend (current requester)
    return streamResponseToFrontend(aiResponse);
} else {
    // Return response to Backend for further processing
    return streamResponseToBackend(aiResponse);
}
```

### **Backend Processing Logic**
```typescript
// In Backend:
switch (channel) {
    case 'messenger':
        await metaService.sendMessengerMessage(config, response);
        break;
    case 'instagram':
        await metaService.sendInstagramMessage(config, response);
        break;
    case 'whatsapp':
        await metaService.sendWhatsAppMessage(config, response);
        break;
    case 'zalo':
        await zaloService.sendMessage(config, response);
        break;
    case 'chat-plugin':
        // ❌ Should never reach here - Frontend handles directly
        throw new Error('Chat Plugin should be handled by Frontend');
        break;
    case 'chatdemo':
        // ❌ Should never reach here - Frontend handles directly
        throw new Error('ChatDemo should be handled by Frontend');
        break;
}
```
    user_id: senderId,           // Instagram IGID
    device_id: `instagram_${senderId}`,
    source: 'instagram',
    name: username || senderId,  // Instagram username
    email: null
};

// Similar processing với Instagram-specific config
```

### **WhatsApp Integration**
```typescript
const userInfo = {
    user_id: phoneNumber,        // WhatsApp phone number
    device_id: `whatsapp_${phoneNumber}`,
    source: 'whatsapp',
    name: profileName,           // WhatsApp profile name
    email: null,
    phone: phoneNumber
};

// 24-hour window check required for WhatsApp
const can24hReply = await checkWhatsApp24HourWindow(phoneNumber, company.id);
```

---

## 📈 Enhanced Logging & Monitoring

### **Structured Logging Format**
```typescript
logger.info('📱 Processing Messenger message', {
    senderId: senderId,
    companyId: company.id,
    messageLength: messageText.length,
    leadSourceId: leadSource?.id,
    leadSourceCode: leadSource?.sourceCode,
    channel: 'messenger'
});

logger.info('✅ AI Service streaming completed', {
    responseLength: finalAnswer.length,
    processingTime: Date.now() - startTime,
    leadSource: leadSource?.sourceCode,
    channel: 'messenger'
});
```

### **Error Tracking**
```typescript
logger.error('💥 Error processing message', {
    error: error.message,
    senderId: senderId,
    companyId: company.id,
    channel: 'messenger',
    step: 'ai_service_call|user_profile|message_send'
});
```

---

## 🚀 Production Deployment

### **Environment Variables Required**
```bash
# AI Service Integration
AI_SERVICE_URL=https://ai.aimoney.io.vn
AI_SERVICE_TOKEN=your_ai_service_token

# Meta Integration
META_WEBHOOK_VERIFY_TOKEN=agent8x_webhook_verify_token_2024
META_APP_SECRET=your_meta_app_secret

# GnB Software Testing Page
GNB_SOFTWARE_PAGE_ID=493031920566909
GNB_SOFTWARE_TOKEN=your_gnb_page_token
```

### **Deployment Commands**
```bash
# Deploy với enhanced integration
./fix-and-deploy.sh

# Verify logs
docker logs agent8x-backend -f | grep "META\|AI Service"
```

---

## 🧪 Testing Guidelines

### **Test Messaging Flow**
1. Send message to any configured Meta platform
2. Verify Lead Source is attached to AI request
3. Confirm streaming response processing
4. Check final_answer extraction và delivery
5. Validate error handling scenarios

### **Monitor Key Metrics**
- Response time (streaming vs traditional)
- AI service success rate
- Lead Source attribution accuracy
- Channel-specific performance
- Error rate by platform

---

## 📋 Migration Notes

### **Changes from Previous Implementation**
1. **Streaming Response**: Replaced blocking AI calls với streaming
2. **Lead Source**: Added automatic Lead Source attachment
3. **Enhanced Payload**: Richer context for AI service
4. **Channel Routing**: Clear distinction between Backend vs Frontend channels
5. **Better Logging**: Structured logging với channel tracking
6. **Error Recovery**: User-friendly error messages

### **Backward Compatibility**
- Maintains existing Meta webhook endpoints
- Compatible với existing company configurations
- Fallback to previous behavior if Lead Source not found

---

## 📊 **Complete Channel Summary**

### **🔧 Backend-Processed Channels (4)**
```
🔵 messenger    → Backend → Facebook Messenger API
🟣 instagram    → Backend → Instagram Business API
🟢 whatsapp     → Backend → WhatsApp Business API
💬 zalo         → Backend → Zalo API
```

### **🖥️ Frontend-Processed Channels (2)**
```
🌐 chat-plugin  → Frontend handles response directly + Backend webhook for storage
🖥️ chatdemo     → Frontend handles response directly
```

### **⚠️ Critical Integration Points**

1. **AI Service**: Must check `channel` field để route response correctly
2. **Backend**: Handles 4 channels via webhooks (messenger, instagram, whatsapp, zalo)
3. **Frontend**: Handles 2 channels directly (chat-plugin, chatdemo)
4. **Chat Plugin**: Frontend receives direct stream + Backend gets webhook for database storage
5. **Lead Source**: Auto-attached cho all channels
6. **Streaming**: SSE processing cho faster responses

---

This enhanced integration provides better user experience through streaming responses, improved analytics through Lead Source tracking, comprehensive channel support, và more robust error handling across all 6 communication platforms.
