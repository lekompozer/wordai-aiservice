# Firebase Authentication API Documentation

## 📋 Overview

Firebase Authentication API endpoints cho việc quản lý user authentication, profile, và conversations trong hệ thống AI Chat với RAG.

**Base URL (Production)**: `https://ai.aimoney.io.vn`
**Base URL (Development)**: `http://localhost:8000`
**Authentication**: Firebase ID Token trong Authorization header

## 🔐 Authentication Endpoints

### 1. Health Check
```http
GET /api/auth/health
```
**Description**: Check trạng thái của authentication service.
**Authentication**: Not required
**Response**:
```json
{
  "status": "healthy",
  "firebase_initialized": true,
  "firebase_status": "configured",
  "development_mode": false,
  "timestamp": "2025-08-28T12:00:00.000Z"
}
```

### 2. Register/Login User
```http
POST /api/auth/register
Authorization: Bearer <firebase_id_token>
```
**Description**: Đăng ký hoặc đăng nhập user với Firebase token. Endpoint này sẽ tạo mới user trong DB nếu chưa có, hoặc cập nhật `last_login` nếu đã tồn tại.
**Authentication**: Required (Firebase ID token)
**Response (200 OK)**:
```json
{
  "success": true,
  "message": "User registered/updated successfully",
  "user": {
    "firebase_uid": "user123",
    "email": "user@example.com",
    "display_name": "John Doe",
    "photo_url": "https://example.com/avatar.jpg",
    "email_verified": true,
    "provider": "google.com",
    "created_at": "2025-08-27T22:50:00Z",
    "last_login": "2025-08-28T12:00:00Z",
    "subscription_plan": "free",
    "total_conversations": 0,
    "total_files": 0,
    "preferences": {
      "default_ai_provider": "openai",
      "theme": "light",
      "language": "vi"
    }
  }
}
```

### 3. Get User Profile
```http
GET /api/auth/profile
Authorization: Bearer <firebase_id_token>
```
**Description**: Lấy thông tin profile của user hiện tại.
**Authentication**: Required
**Response (200 OK)**:
```json
{
  "firebase_uid": "user123",
  "email": "user@example.com",
  "display_name": "John Doe",
  "photo_url": "https://example.com/avatar.jpg",
  "email_verified": true,
  "provider": "google.com",
  "created_at": "2025-08-27T22:50:00Z",
  "last_login": "2025-08-28T12:00:00Z",
  "subscription_plan": "free",
  "total_conversations": 5,
  "total_files": 10,
  "preferences": {
    "default_ai_provider": "openai",
    "theme": "light",
    "language": "vi"
  }
}
```

### 4. Validate Token
```http
GET /api/auth/validate
Authorization: Bearer <firebase_id_token>
```
**Description**: Validate Firebase token. Hữu ích để client kiểm tra token có còn hiệu lực không.
**Authentication**: Required
**Response (200 OK)**:
```json
{
  "valid": true,
  "firebase_uid": "user123",
  "email": "user@example.com",
  "display_name": "John Doe"
}
```

### 5. Logout
```http
POST /api/auth/logout
```
**Description**: Endpoint để ghi log hoặc thực hiện cleanup phía server khi user logout. Việc logout thực tế (xóa token) được xử lý ở client.
**Authentication**: Not required
**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Logout successful. Please clear Firebase token on client side."
}
```

## 💬 Conversation Endpoints (Summary)

### 6. Get User Conversations
```http
GET /api/auth/conversations?limit=20&offset=0
Authorization: Bearer <firebase_id_token>
```
**Description**: Lấy danh sách tóm tắt các conversations của user.
**Authentication**: Required
**Query Parameters**:
- `limit` (optional): Số lượng conversations trả về (default: 20).
- `offset` (optional): Vị trí bắt đầu lấy (default: 0).

**Response (200 OK)**:
```json
[
  {
    "conversation_id": "conv123",
    "created_at": "2025-08-27T22:50:00Z",
    "updated_at": "2025-08-27T22:55:00Z",
    "message_count": 5,
    "last_message": "Đây là tin nhắn cuối cùng của cuộc trò chuyện...",
    "ai_provider": "openai_gpt-4o"
  },
  {
    "conversation_id": "conv456",
    "created_at": "2025-08-26T10:00:00Z",
    "updated_at": "2025-08-26T10:15:00Z",
    "message_count": 12,
    "last_message": "So sánh giúp tôi ưu và nhược điểm của hai sản phẩm này.",
    "ai_provider": "gemini_2.0_flash"
  }
]
```

## 🔧 Error Responses

### Authentication Errors
```json
{
  "detail": "Authentication token required"
}
```
**Status**: `401 Unauthorized`

```json
{
  "detail": "Invalid authentication token"
}
```
**Status**: `401 Unauthorized`

```json
{
  "detail": "Authentication token has expired"
}
```
**Status**: `401 Unauthorized`

### Server Errors
```json
{
  "detail": "Registration failed: <error_message>"
}
```
**Status**: `500 Internal Server Error`

## 🚀 Usage Examples

### Frontend JavaScript Integration

#### 1. Get Firebase ID Token
```javascript
import { getAuth, onAuthStateChanged } from 'firebase/auth';

const auth = getAuth();
onAuthStateChanged(auth, async (user) => {
  if (user) {
    const idToken = await user.getIdToken();
    // Use idToken for API calls
  }
});
```

#### 2. Register/Login User
```javascript
async function registerUser(idToken) {
  const response = await fetch('https://ai.aimoney.io.vn/api/auth/register', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${idToken}`,
      'Content-Type': 'application/json'
    }
  });

  const data = await response.json();
  return data;
}
```

#### 3. Get User Profile
```javascript
async function getUserProfile(idToken) {
  const response = await fetch('https://ai.aimoney.io.vn/api/auth/profile', {
    headers: {
      'Authorization': `Bearer ${idToken}`
    }
  });

  return await response.json();
}
```

#### 4. Get Conversations
```javascript
async function getConversations(idToken, limit = 20, offset = 0) {
  const response = await fetch(
    `https://ai.aimoney.io.vn/api/auth/conversations?limit=${limit}&offset=${offset}`,
    {
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    }
  );

  return await response.json();
}
```

### cURL Examples

#### Register User
```bash
curl -X POST 'https://ai.aimoney.io.vn/api/auth/register' \
  -H 'Authorization: Bearer YOUR_FIREBASE_TOKEN' \
  -H 'Content-Type: application/json'
```

#### Get Profile
```bash
curl -X GET 'https://ai.aimoney.io.vn/api/auth/profile' \
  -H 'Authorization: Bearer YOUR_FIREBASE_TOKEN'
```

#### Get Conversations
```bash
curl -X GET 'https://ai.aimoney.io.vn/api/auth/conversations?limit=10' \
  -H 'Authorization: Bearer YOUR_FIREBASE_TOKEN'
```

## 🔒 Security Considerations

1. **Token Verification**: Tất cả protected endpoints verify Firebase ID token.
2. **User Isolation**: Users chỉ có thể access data của chính họ.
3. **Token Expiration**: Firebase tokens có expiration time, frontend cần refresh.
4. **HTTPS Only**: Production environment phải sử dụng HTTPS.
5. **CORS Configuration**: Configure CORS cho frontend domains.

## 📊 Database Collections

### Users Collection
```javascript
{
  _id: ObjectId,
  firebase_uid: "string",     // Primary key
  email: "string",
  display_name: "string",
  photo_url: "string",
  email_verified: boolean,
  provider: "string",        // google.com, password, etc.
  created_at: ISODate,
  last_login: ISODate,
  subscription_plan: "free|premium",
  total_conversations: number,
  total_files: number,
  preferences: {
    default_ai_provider: "openai|deepseek|gemini",
    theme: "light|dark",
    language: "vi|en"
  }
}
```

### Conversations Collection
```javascript
{
  _id: ObjectId,
  conversation_id: "string",  // UUID
  user_id: "string",         // Firebase UID
  created_at: ISODate,
  updated_at: ISODate,
  messages: [
    {
      role: "user|assistant",
      content: "string",
      timestamp: ISODate
    }
  ],
  ai_provider: "string",
  metadata: {
    temperature: number,
    max_tokens: number,
    total_tokens: number
  }
}
```

## 🚦 Status Codes

- `200 OK`: Request successful
- `401 Unauthorized`: Invalid or missing authentication
- `403 Forbidden`: Access denied
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

## ⚡ Rate Limiting

Currently not implemented. Consider adding rate limiting for production:
- Authentication endpoints: 10 requests/minute per IP
- Profile endpoints: 60 requests/minute per user
- Conversation endpoints: 100 requests/minute per user
