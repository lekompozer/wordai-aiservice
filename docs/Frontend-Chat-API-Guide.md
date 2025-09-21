# Frontend Chat API Integration Guide
# Hướng Dẫn Tích Hợp API Chat Cho Frontend

## 📋 Tổng Quan

Tài liệu này hướng dẫn Frontend tích hợp với API Chat Streaming của hệ thống AI Agent.

## 🚀 API Endpoint

### **POST** `/api/unified/chat-stream`

- **URL**: `https://api.agent8x.io.vn/api/unified/chat-stream`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Response**: `text/event-stream` (Server-Sent Events)

## 📋 Request Format

### Headers
```http
Content-Type: application/json
X-Company-ID: {company_id}  # Optional, có thể gửi trong body
```

### Request Body
```json
{
  "message": "Tôi muốn tìm hiểu về lãi suất vay",
  "company_id": "comp_123456",
  "industry": "banking",
  "language": "vietnamese",
  "user_info": {
    "user_id": "user_123",
    "name": "Nguyễn Văn A",
    "email": "user@example.com",
    "source": "web_device"
  },
  "session_id": "session_abc123",  # Optional - hệ thống sẽ tự tạo nếu không có
  "context": {
    "page_url": "https://example.com/banking",
    "user_agent": "Mozilla/5.0...",
    "disable_webhooks": false
  }
}
```

### Required Fields
- `message` (string): Tin nhắn của người dùng
- `company_id` (string): ID công ty
- `industry` (enum): Ngành nghề - `banking`, `insurance`, `restaurant`, `hotel`, `retail`, `fashion`, `industrial`, `healthcare`, `education`, `other`
- `user_info.user_id` (string): ID người dùng
- `user_info.source` (enum): Nguồn truy cập - `web_device`, `facebook_messenger`, `whatsapp`, `zalo`, `instagram`, `website_plugin`

### Optional Fields
- `language` (enum): `vietnamese`, `english`, `auto_detect` (default: `auto_detect`)
- `session_id` (string): ID phiên chat - hệ thống sẽ tự tạo nếu không có
- `user_info.name` (string): Tên người dùng
- `user_info.email` (string): Email người dùng
- `context` (object): Thông tin ngữ cảnh bổ sung

## 📡 Response Format (Server-Sent Events)

Response được trả về dưới dạng **Server-Sent Events (SSE)** với format:

```
data: {"type": "language", "language": "vietnamese"}

data: {"type": "intent", "intent": "information", "confidence": 0.85}

data: {"type": "content", "chunk": "Chào bạn! "}

data: {"type": "content", "chunk": "Tôi có thể "}

data: {"type": "content", "chunk": "giúp bạn tìm hiểu "}

data: {"type": "content", "chunk": "về lãi suất vay ngân hàng."}

data: {"type": "done", "session_id": "session_abc123", "conversation_id": "conv_xyz789"}
```

### Event Types

| Type | Description | Data Fields |
|------|-------------|-------------|
| `language` | Kết quả phát hiện ngôn ngữ | `language` |
| `intent` | Kết quả phát hiện ý định | `intent`, `confidence` |
| `content` | Từng phần nội dung trả lời | `chunk` |
| `done` | Tín hiệu hoàn thành | `session_id`, `conversation_id` |
| `error` | Thông báo lỗi | `error`, `message` |

## 💻 JavaScript Implementation

### 1. Basic Fetch with EventSource

```javascript
async function sendChatMessage(message, companyId, userId) {
  const response = await fetch('/api/unified/chat-stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Company-ID': companyId
    },
    body: JSON.stringify({
      message: message,
      company_id: companyId,
      industry: 'banking',
      language: 'auto_detect',
      user_info: {
        user_id: userId,
        source: 'web_device'
      }
    })
  });

  // Đọc stream response
  const reader = response.body.getReader();
  let result = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = new TextDecoder().decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        handleStreamEvent(data);
      }
    }
  }
}

function handleStreamEvent(data) {
  switch (data.type) {
    case 'language':
      console.log('Detected language:', data.language);
      break;
    case 'intent':
      console.log('Detected intent:', data.intent, 'confidence:', data.confidence);
      break;
    case 'content':
      // Hiển thị từng chunk nội dung
      appendToChat(data.chunk);
      break;
    case 'done':
      console.log('Chat completed:', data.session_id);
      break;
    case 'error':
      console.error('Chat error:', data.error);
      break;
  }
}
```

### 2. React Implementation

```jsx
import React, { useState, useCallback } from 'react';

const ChatComponent = ({ companyId, userId }) => {
  const [messages, setMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = useCallback(async (message) => {
    if (!message.trim()) return;

    // Thêm tin nhắn user vào chat
    setMessages(prev => [...prev, { type: 'user', content: message }]);
    setCurrentMessage('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/unified/chat-stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Company-ID': companyId
        },
        body: JSON.stringify({
          message,
          company_id: companyId,
          industry: 'banking',
          user_info: {
            user_id: userId,
            source: 'web_device'
          }
        })
      });

      const reader = response.body.getReader();
      let aiResponse = '';

      // Tạo placeholder cho AI response
      setMessages(prev => [...prev, { type: 'ai', content: '', isStreaming: true }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = new TextDecoder().decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'content') {
              aiResponse += data.chunk;
              // Cập nhật real-time
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMessage = newMessages[newMessages.length - 1];
                if (lastMessage.type === 'ai') {
                  lastMessage.content = aiResponse;
                }
                return newMessages;
              });
            } else if (data.type === 'done') {
              // Hoàn thành streaming
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMessage = newMessages[newMessages.length - 1];
                if (lastMessage.type === 'ai') {
                  lastMessage.isStreaming = false;
                }
                return newMessages;
              });
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, { 
        type: 'error', 
        content: 'Đã có lỗi xảy ra. Vui lòng thử lại.' 
      }]);
    } finally {
      setIsLoading(false);
    }
  }, [companyId, userId]);

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.type}`}>
            {msg.content}
            {msg.isStreaming && <span className="cursor">|</span>}
          </div>
        ))}
      </div>
      
      <div className="input-container">
        <input
          type="text"
          value={currentMessage}
          onChange={(e) => setCurrentMessage(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage(currentMessage)}
          disabled={isLoading}
          placeholder="Nhập tin nhắn..."
        />
        <button 
          onClick={() => sendMessage(currentMessage)}
          disabled={isLoading || !currentMessage.trim()}
        >
          Gửi
        </button>
      </div>
    </div>
  );
};
```

### 3. Vue.js Implementation

```vue
<template>
  <div class="chat-container">
    <div class="messages">
      <div 
        v-for="(message, index) in messages" 
        :key="index" 
        :class="`message ${message.type}`"
      >
        {{ message.content }}
        <span v-if="message.isStreaming" class="cursor">|</span>
      </div>
    </div>
    
    <div class="input-container">
      <input
        v-model="currentMessage"
        @keyup.enter="sendMessage"
        :disabled="isLoading"
        placeholder="Nhập tin nhắn..."
      />
      <button 
        @click="sendMessage"
        :disabled="isLoading || !currentMessage.trim()"
      >
        Gửi
      </button>
    </div>
  </div>
</template>

<script>
export default {
  props: ['companyId', 'userId'],
  data() {
    return {
      messages: [],
      currentMessage: '',
      isLoading: false
    }
  },
  methods: {
    async sendMessage() {
      if (!this.currentMessage.trim()) return;

      // Thêm tin nhắn user
      this.messages.push({ 
        type: 'user', 
        content: this.currentMessage 
      });

      const message = this.currentMessage;
      this.currentMessage = '';
      this.isLoading = true;

      try {
        const response = await fetch('/api/unified/chat-stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Company-ID': this.companyId
          },
          body: JSON.stringify({
            message,
            company_id: this.companyId,
            industry: 'banking',
            user_info: {
              user_id: this.userId,
              source: 'web_device'
            }
          })
        });

        const reader = response.body.getReader();
        let aiResponse = '';

        // Thêm placeholder cho AI response
        this.messages.push({ 
          type: 'ai', 
          content: '', 
          isStreaming: true 
        });

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = new TextDecoder().decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'content') {
                aiResponse += data.chunk;
                const lastMessage = this.messages[this.messages.length - 1];
                lastMessage.content = aiResponse;
              } else if (data.type === 'done') {
                const lastMessage = this.messages[this.messages.length - 1];
                lastMessage.isStreaming = false;
              }
            }
          }
        }
      } catch (error) {
        console.error('Chat error:', error);
        this.messages.push({ 
          type: 'error', 
          content: 'Đã có lỗi xảy ra. Vui lòng thử lại.' 
        });
      } finally {
        this.isLoading = false;
      }
    }
  }
}
</script>
```

## 🎨 CSS Styling

```css
.chat-container {
  max-width: 600px;
  margin: 0 auto;
  border: 1px solid #ddd;
  border-radius: 8px;
  overflow: hidden;
}

.messages {
  height: 400px;
  overflow-y: auto;
  padding: 16px;
  background: #f9f9f9;
}

.message {
  margin-bottom: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  max-width: 80%;
}

.message.user {
  background: #007bff;
  color: white;
  margin-left: auto;
  text-align: right;
}

.message.ai {
  background: white;
  border: 1px solid #ddd;
}

.message.error {
  background: #dc3545;
  color: white;
}

.cursor {
  animation: blink 1s infinite;
  font-weight: bold;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.input-container {
  display: flex;
  padding: 16px;
  background: white;
  border-top: 1px solid #ddd;
}

.input-container input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin-right: 8px;
}

.input-container button {
  padding: 8px 16px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.input-container button:disabled {
  background: #ccc;
  cursor: not-allowed;
}
```

## 🔍 Testing

### Test với cURL
```bash
curl -X POST https://api.agent8x.io.vn/api/unified/chat-stream \
  -H "Content-Type: application/json" \
  -H "X-Company-ID: comp_123456" \
  -d '{
    "message": "Tôi muốn tìm hiểu về lãi suất vay",
    "company_id": "comp_123456",
    "industry": "banking",
    "user_info": {
      "user_id": "test_user",
      "source": "web_device"
    }
  }'
```

## 📝 Best Practices

1. **Session Management**: Luôn lưu trữ `session_id` để duy trì ngữ cảnh cuộc hội thoại
2. **Error Handling**: Xử lý các lỗi mạng và server một cách graceful
3. **Loading States**: Hiển thị trạng thái loading khi đang stream
4. **Rate Limiting**: Tránh gửi quá nhiều request liên tiếp
5. **User Experience**: Hiển thị typing indicator và streaming effect

## 🐛 Common Issues

1. **CORS Error**: Đảm bảo domain được whitelist ở server
2. **Network Timeout**: Thêm timeout handling cho các request dài
3. **Memory Leaks**: Đóng các stream reader khi component unmount
4. **Special Characters**: Đảm bảo UTF-8 encoding cho tin nhắn tiếng Việt

## 📞 Support

Nếu có vấn đề trong quá trình tích hợp, vui lòng liên hệ:
- Email: support@agent8x.io.vn
- Documentation: https://docs.agent8x.io.vn
