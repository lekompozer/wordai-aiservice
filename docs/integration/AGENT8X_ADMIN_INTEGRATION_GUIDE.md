# Agent8x Admin Integration Guide
## Hướng dẫn tích hợp AI Service cho Admin Panel

---

## 📋 Tổng Quan

Tài liệu này hướng dẫn chi tiết cách tích hợp AI Service với Admin Panel của Agent8x. AI Service cung cấp các API cho việc quản lý công ty, xử lý file và đồng bộ dữ liệu conversation.

### Kiến Trúc Hệ Thống
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Admin Panel   │────▶│  Backend NodeJS │────▶│   AI Service    │
│  (Frontend)     │     │ (api.agent8x)   │     │(ai.aimoney.io.vn)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                         │
         │                       ▼                         ▼
         └─────────────▶│  Cloudflare R2  │      │     Qdrant      │
                        │  (File Storage) │      │  (Vector Store) │
                        └─────────────────┘      └─────────────────┘
```

---

## 🔐 Authentication & Security

### API Key Authentication
AI Service sử dụng **Internal API Key** để xác thực các request từ Backend:

```http
X-API-Key: agent8x-backend-secret-key-2025
```

⚠️ **QUAN TRỌNG - Backend cần kiểm tra:**
1. **Header phải chính xác**: `X-API-Key` (không phải `x-api-key` hay `API-Key`)
2. **Giá trị API Key**: `agent8x-backend-secret-key-2025`
3. **Phải gửi kèm với mọi request** tới AI Service

### Environment Configuration
```bash
# AI Service (.env)
INTERNAL_API_KEY=agent8x-backend-secret-key-2025
WEBHOOK_SECRET=webhook-secret-for-signature
BACKEND_WEBHOOK_URL=https://api.agent8x.io.vn

# Backend (.env) - CẦN KIỂM TRA CÁC GIÁ TRỊ NÀY
AI_SERVICE_URL=http://localhost:8000  # Development
AI_SERVICE_API_KEY=agent8x-backend-secret-key-2025
AI_WEBHOOK_SECRET=webhook-secret-for-signature
```

### Webhook Signature Verification
AI Service ký các webhook bằng HMAC SHA256:

```python
# Tạo signature
signature = hmac.new(
    webhook_secret.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

# Header: X-Webhook-Signature
```

---

## 📡 API Endpoints

### Base URL
- **Production**: `https://ai.aimoney.io.vn`
- **Development**: `http://localhost:8000`

### Admin API Endpoints (Backend → AI Service)

#### 1. Company Registration
```http
POST /api/admin/companies/register
Headers:
  X-API-Key: agent8x-backend-secret-key-2025
  Content-Type: application/json
```

**Request Body:**
```json
{
  "company_id": "uuid-from-backend",
  "company_name": "Nhà hàng ABC",
  "industry": "restaurant",
  "metadata": {
    "email": "admin@abc.com",
    "phone": "+84901234567",
    "website": "https://abc.com",
    "location": {
      "country": "Vietnam",
      "city": "Ho Chi Minh City",
      "address": "123 Nguyễn Trãi, Quận 1, TP.HCM"
    },
    "description": "Nhà hàng chuyên phục vụ món ăn Việt Nam truyền thống",
    "social_links": {
      "facebook": "https://facebook.com/nhahangarc",
      "twitter": "@nhahangarc",
      "zalo": "0901234567",
      "whatsapp": "+84901234567",
      "telegram": "@nhahangarc"
    },
    "business_info": {
      "language": "vi",
      "timezone": "Asia/Ho_Chi_Minh",
      "owner_firebase_uid": "firebase-uid-123",
      "created_at": "2025-07-13T10:00:00Z"
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Company registered successfully",
  "data": {
    "company_id": "uuid-from-backend",
    "qdrant_collection": "company_uuid_data",
    "industry_config": {
      "supported_data_types": ["menu_items", "ingredients", "nutritional_info"],
      "extraction_prompts": "restaurant_specific_prompts"
    },
    "company_info_indexed": true,
    "indexed_data": {
      "basic_info": true,
      "location": true,
      "social_links": true,
      "business_info": true
    }
  }
}
```

#### 1.1. Update Company Basic Info
```http
PUT /api/admin/companies/{company_id}/basic-info
Headers:
  X-API-Key: agent8x-backend-secret-key-2025
  Content-Type: application/json
```

**Request Body:**
```json
{
  "company_name": "Nhà hàng ABC - Cập nhật",
  "metadata": {
    "email": "newemail@abc.com",
    "phone": "+84901234999",
    "website": "https://newabc.com",
    "location": {
      "country": "Vietnam",
      "city": "Ho Chi Minh City",
      "address": "456 Lê Lợi, Quận 1, TP.HCM"
    },
    "description": "Nhà hàng chuyên phục vụ món ăn Việt Nam truyền thống và hiện đại",
    "social_links": {
      "facebook": "https://facebook.com/nhahangarc.new",
      "twitter": "@nhahangarc_new",
      "zalo": "0901234999",
      "whatsapp": "+84901234999",
      "telegram": "@nhahangarc_new"
    },
    "business_info": {
      "language": "en",
      "timezone": "Asia/Bangkok"
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Company basic info updated successfully",
  "data": {
    "company_id": "uuid-from-backend",
    "updated_fields": [
      "company_name",
      "email",
      "phone", 
      "website",
      "location",
      "description",
      "social_links",
      "language",
      "timezone"
    ],
    "qdrant_updated": true,
    "vector_points_updated": 5
  }
}
```

#### 2. File Upload & Processing
```http
POST /api/admin/companies/{company_id}/files/upload
Headers:
  X-API-Key: agent8x-backend-secret-key-2025
  Content-Type: multipart/form-data
```

⚠️ **LƯU Ý QUAN TRỌNG CHO BACKEND:**
- **KHÔNG có endpoint `/process`** - File sẽ được xử lý tự động sau khi upload
- **Endpoint chính xác**: `/api/admin/companies/{company_id}/files/upload`
- **Không gọi**: `/api/admin/companies/{company_id}/files/{file_id}/process` ❌
- **Không gọi**: `/api/admin/companies/{company_id}/files/company/{company_id}/files/{file_id}/process` ❌

**Form Data:**
```
files: [binary file data]
data_type: "products" | "services" | "info"
metadata: {
  "original_name": "menu.pdf",
  "uploaded_by": "admin_user_id",
  "r2_url": "https://r2.domain.com/path/to/file",
  "file_name": "Menu Chính Thức 2025",
  "description": "Menu món ăn chính của nhà hàng, bao gồm các món truyền thống và đặc sản",
  "tags": ["menu", "food", "main", "vietnamese", "traditional"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Files processed successfully",
  "data": {
    "processed_files": [
      {
        "file_id": "uuid",
        "original_name": "menu.pdf",
        "file_name": "Menu Chính Thức 2025",
        "status": "PROCESSED",
        "extracted_items": 25,
        "chunks_created": 15,
        "processing_time": 12.5,
        "tags_indexed": ["menu", "food", "main", "vietnamese", "traditional"]
      }
    ],
    "failed_files": []
  }
}
```

#### 3. File Deletion (Single File)
```http
DELETE /api/admin/companies/{company_id}/files/{file_id}
Headers:
  X-API-Key: agent8x-backend-secret-key-2025
```

**Response:**
```json
{
  "success": true,
  "message": "File data deleted successfully",
  "data": {
    "file_id": "uuid",
    "file_name": "menu.pdf",
    "chunks_deleted": 15,
    "vector_points_removed": 15,
    "tags_removed": ["menu", "food", "main"]
  }
}
```

#### 4. Delete Files by Tags
```http
DELETE /api/admin/companies/{company_id}/files/tags/{tag_name}
Headers:
  X-API-Key: agent8x-backend-secret-key-2025
```

**Query Parameters:**
```
confirm: true  // Required confirmation parameter
```

**Response:**
```json
{
  "success": true,
  "message": "All files with tag 'old-menu' deleted successfully",
  "data": {
    "tag_name": "old-menu",
    "deleted_files": [
      {
        "file_id": "uuid-1",
        "file_name": "menu-2024.pdf",
        "chunks_deleted": 15,
        "vector_points_removed": 15
      },
      {
        "file_id": "uuid-2", 
        "file_name": "old-price-list.xlsx",
        "chunks_deleted": 8,
        "vector_points_removed": 8
      }
    ],
    "total_files_deleted": 2,
    "total_chunks_deleted": 23,
    "total_vector_points_removed": 23
  }
}
```

#### 5. Get Files by Tags
```http
GET /api/admin/companies/{company_id}/files/tags/{tag_name}
Headers:
  X-API-Key: agent8x-backend-secret-key-2025
```

**Response:**
```json
{
  "success": true,
  "data": {
    "tag_name": "menu",
    "files": [
      {
        "file_id": "uuid-1",
        "file_name": "Menu Chính Thức 2025",
        "original_name": "menu.pdf",
        "status": "PROCESSED",
        "uploaded_at": "2025-07-13T10:00:00Z",
        "chunks_count": 15,
        "tags": ["menu", "food", "main", "vietnamese", "traditional"]
      }
    ],
    "total_files": 1
  }
}
```

#### 6. List All Tags
```http
GET /api/admin/companies/{company_id}/tags
Headers:
  X-API-Key: agent8x-backend-secret-key-2025
```

**Response:**
```json
{
  "success": true,
  "data": {
    "tags": [
      {
        "name": "menu",
        "file_count": 3,
        "created_at": "2025-07-13T10:00:00Z",
        "last_used": "2025-07-15T14:30:00Z"
      },
      {
        "name": "food",
        "file_count": 5,
        "created_at": "2025-07-13T10:00:00Z", 
        "last_used": "2025-07-15T14:30:00Z"
      },
      {
        "name": "pricing",
        "file_count": 2,
        "created_at": "2025-07-14T09:00:00Z",
        "last_used": "2025-07-14T16:20:00Z"
      }
    ],
    "total_tags": 3
  }
}
```

#### 7. Search Company Data
```http
POST /api/admin/companies/{company_id}/search
Headers:
  X-API-Key: agent8x-backend-secret-key-2025
  Content-Type: application/json
```

**Request Body:**
```json
{
  "query": "món chay có giá dưới 100k",
  "limit": 10,
  "content_types": ["products"],
  "language": "vi",
  "filter_tags": ["menu", "food"]
}
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "content": "Cơm chay nấm đông cô - 85,000đ",
        "score": 0.95,
        "metadata": {
          "item_type": "main_course",
          "price": 85000,
          "category": "vegetarian"
        },
        "source_file": "menu.pdf"
      }
    ],
    "count": 1,
    "processing_time": 0.234
  }
}
```

#### 8. Company Statistics
```http
GET /api/admin/companies/{company_id}/stats
Headers:
  X-API-Key: agent8x-backend-secret-key-2025
```

**Response:**
```json
{
  "success": true,
  "data": {
    "total_files": 5,
    "processed_files": 4,
    "failed_files": 1,
    "total_chunks": 125,
    "vector_points": 125,
    "storage_used_mb": 45.2,
    "last_activity": "2025-07-13T10:30:00Z",
    "data_types": {
      "products": 80,
      "services": 30,
      "info": 15
    },
    "tags_summary": {
      "total_tags": 8,
      "most_used_tags": [
        {"name": "menu", "file_count": 3},
        {"name": "food", "file_count": 5},
        {"name": "pricing", "file_count": 2}
      ]
    },
    "company_info": {
      "indexed": true,
      "last_updated": "2025-07-15T09:30:00Z",
      "language": "vi",
      "timezone": "Asia/Ho_Chi_Minh"
    }
  }
}
```

### Chat API Endpoints (Frontend → AI Service)

#### Unified Chat
```http
POST /api/unified/chat
Headers:
  X-Company-Id: company-uuid
  Content-Type: application/json
```

**Request Body:**
```json
{
  "message": "Cho tôi xem menu món chay",
  "session_id": "unique-session-id",
  "language": "vi",
  "industry": "restaurant",
  "context": {
    "previous_intent": "MENU_INQUIRY",
    "user_preferences": ["vegetarian"]
  }
}
```

**Response:**
```json
{
  "success": true,
  "response": "Dưới đây là các món chay trong menu của chúng tôi:\n\n1. Cơm chay nấm đông cô - 85,000đ\n2. Phở chay - 75,000đ\n3. Bánh mì chay - 35,000đ",
  "intent": {
    "detected": "MENU_INQUIRY",
    "confidence": 0.95,
    "subcategory": "vegetarian_food"
  },
  "sources": [
    {
      "file_name": "menu.pdf",
      "relevance_score": 0.89
    }
  ],
  "session_id": "unique-session-id",
  "conversation_id": "conv-uuid"
}
```

---

## 🔄 Webhook Integration

### Webhook Events
AI Service gửi các webhook events về Backend khi có hoạt động chat:

#### 1. Conversation Created
```json
{
  "event": "conversation.created",
  "companyId": "company-uuid",
  "data": {
    "conversationId": "conv-uuid",
    "sessionId": "session-123",
    "channel": "WEB",
    "intent": "MENU_INQUIRY",
    "startedAt": "2025-07-13T10:00:00Z",
    "metadata": {
      "industry": "restaurant",
      "language": "vi",
      "user_agent": "Mozilla/5.0..."
    }
  },
  "timestamp": "2025-07-13T10:00:00Z"
}
```

#### 2. Message Created
```json
{
  "event": "message.created",
  "companyId": "company-uuid",
  "data": {
    "messageId": "msg-uuid",
    "conversationId": "conv-uuid",
    "role": "user", // or "assistant"
    "content": "Cho tôi xem menu món chay",
    "timestamp": "2025-07-13T10:00:00Z",
    "metadata": {
      "intent": "MENU_INQUIRY",
      "confidence": 0.95,
      "processing_time": 1.234
    }
  },
  "timestamp": "2025-07-13T10:00:00Z"
}
```

#### 3. Conversation Updated
```json
{
  "event": "conversation.updated",
  "companyId": "company-uuid",
  "data": {
    "conversationId": "conv-uuid",
    "status": "COMPLETED",
    "messageCount": 8,
    "endedAt": "2025-07-13T10:15:00Z",
    "summary": "User inquired about vegetarian menu options and received recommendations",
    "satisfaction_score": 4.5
  },
  "timestamp": "2025-07-13T10:15:00Z"
}
```

### Webhook Endpoint (Backend)
```http
POST /api/webhooks/ai/conversation
Headers:
  X-Webhook-Signature: sha256-signature
  Content-Type: application/json
```

---

## 🏭 Industry-Specific Features

### Restaurant Industry
```json
{
  "supported_data_types": [
    "menu_items",
    "ingredients", 
    "nutritional_info",
    "pricing",
    "availability"
  ],
  "extraction_capabilities": [
    "dish_names",
    "prices",
    "descriptions",
    "dietary_restrictions",
    "allergen_information"
  ],
  "search_intents": [
    "MENU_INQUIRY",
    "PRICE_INQUIRY", 
    "DIETARY_RESTRICTIONS",
    "RESERVATION_INQUIRY"
  ]
}
```

### Hotel Industry
```json
{
  "supported_data_types": [
    "room_types",
    "amenities",
    "pricing",
    "availability",
    "policies"
  ],
  "extraction_capabilities": [
    "room_descriptions",
    "rates",
    "capacity",
    "amenities_list",
    "booking_policies"
  ],
  "search_intents": [
    "ROOM_INQUIRY",
    "AMENITY_INQUIRY",
    "PRICING_INQUIRY",
    "BOOKING_INQUIRY"
  ]
}
```

### Banking Industry
```json
{
  "supported_data_types": [
    "loan_products",
    "interest_rates",
    "requirements",
    "fees",
    "terms"
  ],
  "extraction_capabilities": [
    "product_names",
    "interest_rates",
    "loan_terms",
    "eligibility_criteria",
    "fee_structures"
  ],
  "search_intents": [
    "LOAN_INQUIRY",
    "RATE_INQUIRY",
    "ELIGIBILITY_INQUIRY",
    "APPLICATION_INQUIRY"
  ]
}
```

---

## 🔧 Implementation Steps

### 1. Authentication Middleware (AI Service)
```python
# src/middleware/auth.py
from fastapi import Header, HTTPException
from typing import Optional
import os

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

async def verify_internal_api_key(x_api_key: Optional[str] = Header(None)):
    if not x_api_key or x_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

async def verify_company_access(x_company_id: Optional[str] = Header(None)):
    if not x_company_id:
        raise HTTPException(status_code=400, detail="Company ID required")
    return x_company_id
```

### 2. Admin Routes với Authentication
```python
# src/api/admin_routes.py
from fastapi import APIRouter, Depends
from src.middleware.auth import verify_internal_api_key

router = APIRouter()

@router.post("/api/admin/companies/register", dependencies=[Depends(verify_internal_api_key)])
async def register_company(request: CompanyRegistration):
    # Implementation here
    pass

@router.post("/api/admin/companies/{company_id}/files/upload", dependencies=[Depends(verify_internal_api_key)])
async def upload_files(company_id: str, files: List[UploadFile]):
    # Implementation here
    pass
```

### 3. Webhook Service
```python
# src/services/webhook_service.py
import httpx
import hashlib
import hmac
import json
from datetime import datetime

class WebhookService:
    def __init__(self):
        self.webhook_url = os.getenv("BACKEND_WEBHOOK_URL")
        self.webhook_secret = os.getenv("WEBHOOK_SECRET")
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def _generate_signature(self, payload: str) -> str:
        return hmac.new(
            self.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    async def send_conversation_event(self, event_type: str, company_id: str, data: dict):
        payload = {
            "event": event_type,
            "companyId": company_id,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        payload_str = json.dumps(payload, sort_keys=True)
        signature = self._generate_signature(payload_str)
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature
        }
        
        await self.client.post(
            f"{self.webhook_url}/api/webhooks/ai/conversation",
            json=payload,
            headers=headers
        )

webhook_service = WebhookService()
```

### 4. Unified Chat với Webhook Integration
```python
# src/services/unified_chat_service.py
from src.services.webhook_service import webhook_service
import uuid

class UnifiedChatService:
    async def process_message(self, request: UnifiedChatRequest):
        # Track conversations
        conversation_id = self.get_or_create_conversation(request.session_id)
        
        # Notify new conversation
        if self.is_new_conversation(request.session_id):
            await webhook_service.send_conversation_event(
                "conversation.created",
                request.company_id,
                {
                    "conversationId": conversation_id,
                    "sessionId": request.session_id,
                    "channel": "WEB",
                    "startedAt": datetime.now().isoformat()
                }
            )
        
        # Notify user message
        await webhook_service.send_conversation_event(
            "message.created",
            request.company_id,
            {
                "messageId": str(uuid.uuid4()),
                "conversationId": conversation_id,
                "role": "user",
                "content": request.message,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        # Process message and get response
        response = await self.generate_response(request)
        
        # Notify assistant message
        await webhook_service.send_conversation_event(
            "message.created",
            request.company_id,
            {
                "messageId": str(uuid.uuid4()),
                "conversationId": conversation_id,
                "role": "assistant",
                "content": response.response,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "intent": response.intent.detected,
                    "confidence": response.intent.confidence
                }
            }
        )
        
        return response
```

---

## 📊 Data Flow Examples

### Complete Company Setup Flow
```
1. Admin creates company in Admin Panel
   ↓
2. Backend calls POST /api/admin/companies/register
   ↓
3. AI Service creates Qdrant collection
   ↓
4. Backend receives confirmation
   ↓
5. Admin can now upload files and chat
```

### File Processing Flow
```
1. Admin uploads files in Admin Panel
   ↓
2. Backend saves files to Cloudflare R2
   ↓
3. Backend calls POST /api/admin/companies/{id}/files/upload
   ↓
4. AI Service downloads from R2 and processes
   ↓
5. AI Service extracts data and indexes to Qdrant
   ↓
6. Backend receives processing results
   ↓
7. Data ready for chat queries
```

### Chat & Webhook Flow
```
1. Customer chats on website
   ↓
2. Frontend calls POST /api/unified/chat
   ↓
3. AI Service processes and responds
   ↓
4. AI Service sends webhook to Backend
   ↓
5. Backend saves conversation to database
   ↓
6. Admin can view conversation in Admin Panel
```

---

## 🚨 Error Handling & Backend Integration Issues

### Phân tích Log của Backend

Từ log bạn cung cấp, có các vấn đề sau:

```bash
# ✅ OK - Health check hoạt động bình thường
INFO: 127.0.0.1:62061 - "GET /health HTTP/1.1" 200 OK

# ❌ LỖI 1: 401 Unauthorized - Thiếu API Key
INFO: 127.0.0.1:62097 - "DELETE /api/admin/companies/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/38100efd-4691-4d77-9506-2cfd70f90020 HTTP/1.1" 401 Unauthorized

# ❌ LỖI 2: 404 Not Found - Gọi sai endpoint  
INFO: 127.0.0.1:62104 - "POST /api/admin/companies/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/f3a192f0-0ad1-47de-93ea-e9cd88fa2227.docx/process HTTP/1.1" 404 Not Found

# ❌ LỖI 3: 401 Unauthorized - Thiếu API Key  
INFO: 127.0.0.1:62384 - "DELETE /api/admin/companies/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/f3a192f0-0ad1-47de-93ea-e9cd88fa2227 HTTP/1.1" 401 Unauthorized

# ❌ LỖI 4: 404 Not Found - Gọi sai endpoint
INFO: 127.0.0.1:62393 - "POST /api/admin/companies/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/e0439112-8596-4fe7-8297-324abd1c96a6/process HTTP/1.1" 404 Not Found
```

### Common Error Codes

#### 401 Unauthorized - API Key Issues
```json
{
  "detail": "Invalid API key"
}
```

**Nguyên nhân:**
- Backend không gửi header `X-API-Key`
- Giá trị API Key sai
- Tên header sai (`x-api-key` thay vì `X-API-Key`)

**Giải pháp:**
```javascript
// Backend cần gửi header chính xác
const headers = {
  'X-API-Key': 'agent8x-backend-secret-key-2025',
  'Content-Type': 'application/json'
};
```

#### 404 Not Found - Wrong Endpoints
```json
{
  "detail": "Not Found"
}
```

**Nguyên nhân:**
Backend đang gọi các endpoint SAI:
- `POST .../files/company/.../process` ❌
- `POST .../files/{file_id}/process` ❌

**Giải pháp:**
Gọi đúng endpoint:
- `POST .../files/upload` ✅ (để upload và process file)
- `DELETE .../files/{file_id}` ✅ (để xóa file)

#### 400 Bad Request
```json
{
  "detail": "Company ID required"
}
```
**Solution**: Include `X-Company-Id` header for chat APIs

#### 415 Unsupported Media Type
```json
{
  "detail": "Unsupported file type: application/zip"
}
```
**Solution**: Use supported file types (PDF, DOCX, XLSX, TXT, JPG, PNG)

### Supported File Types
- **Documents**: PDF, DOCX, DOC, TXT
- **Spreadsheets**: XLSX, XLS, CSV
- **Images**: JPG, JPEG, PNG, WEBP
- **Data**: JSON, CSV

### File Size Limits
- **Maximum file size**: 100MB per file
- **Maximum files per upload**: 10 files
- **Total storage per company**: Based on plan

### Rate Limits
- **Admin APIs**: 100 requests/minute per company
- **Chat APIs**: 1000 messages/hour per company
- **Webhook retries**: 3 attempts with exponential backoff

---

## 🚨 TROUBLESHOOTING CHO BACKEND DEVELOPER

### Lỗi 401 Unauthorized - Kiểm tra Authentication

**Nguyên nhân phổ biến:**
1. **Header sai tên**: Phải là `X-API-Key` (viết hoa chữ X và K)
2. **Giá trị API Key sai**: Phải là `agent8x-backend-secret-key-2025`
3. **Missing header**: Backend quên gửi header

**Cách debug:**
```javascript
// Backend NodeJS - Kiểm tra header đang gửi
const headers = {
  'X-API-Key': 'agent8x-backend-secret-key-2025',  // ✅ Đúng
  'Content-Type': 'application/json'
};

// ❌ Các cách SAI thường gặp:
// 'x-api-key': '...'           // Sai: viết thường
// 'API-Key': '...'             // Sai: thiếu chữ X
// 'Authorization': 'Bearer...' // Sai: không phải Bearer token
```

### Lỗi 404 Not Found - Kiểm tra URL Endpoints

**Các endpoint SAI mà Backend thường gọi:**
```bash
# ❌ CÁC ENDPOINT SAI - ĐỪNG GỌI:
POST /api/admin/companies/{id}/files/{file_id}/process
POST /api/admin/companies/{id}/files/company/{id}/files/{file_id}/process  
POST /api/admin/companies/{id}/files/process

# ✅ ENDPOINT ĐÚNG - GỌI CÁC NÀY:
POST /api/admin/companies/{id}/files/upload           # Upload file
DELETE /api/admin/companies/{id}/files/{file_id}      # Delete file  
GET /api/admin/companies/{id}/files                   # List files
GET /api/admin/companies/{id}/stats                   # Get stats
```

#### 🔧 HƯỚNG DẪN FIX CHO BACKEND TEAM

#### Fix Lỗi 401 Unauthorized

**1. Kiểm tra environment variables:**
```bash
# Backend .env file cần có:
AI_SERVICE_URL=http://localhost:8000
AI_SERVICE_API_KEY=agent8x-backend-secret-key-2025
```

**2. Kiểm tra code gửi request:**
```javascript
// ✅ ĐÚNG - JavaScript/Node.js
const response = await fetch(`${process.env.AI_SERVICE_URL}/api/admin/companies/${companyId}/files/${fileId}`, {
  method: 'DELETE',
  headers: {
    'X-API-Key': process.env.AI_SERVICE_API_KEY,
    'Content-Type': 'application/json'
  }
});

// ✅ ĐÚNG - Axios
const response = await axios.delete(`${AI_SERVICE_URL}/api/admin/companies/${companyId}/files/${fileId}`, {
  headers: {
    'X-API-Key': process.env.AI_SERVICE_API_KEY
  }
});
```

#### Fix Lỗi 404 Not Found - Wrong Endpoints

**Từ log lỗi, Backend đang gọi SAI endpoint:**

```bash
# ❌ SAI - Backend đang gọi:
POST /api/admin/companies/{id}/files/company/{id}/files/{file}.docx/process

# ✅ ĐÚNG - Backend cần gọi:  
POST /api/admin/companies/{id}/files/upload
```

**Sửa code Backend:**
```javascript
// ❌ ĐỪNG GỌI CÁC ENDPOINT NÀY:
// POST .../files/{fileId}/process
// POST .../files/company/.../process  
// POST .../files/process

// ✅ GỌI ĐÚNG ENDPOINT:
// Upload file (AI Service sẽ tự động process)
const uploadResponse = await fetch(`${AI_SERVICE_URL}/api/admin/companies/${companyId}/files/upload`, {
  method: 'POST',
  headers: {
    'X-API-Key': process.env.AI_SERVICE_API_KEY,
    // Content-Type sẽ được set tự động cho multipart/form-data
  },
  body: formData // Chứa file + metadata
});

// Delete file  
const deleteResponse = await fetch(`${AI_SERVICE_URL}/api/admin/companies/${companyId}/files/${fileId}`, {
  method: 'DELETE',
  headers: {
    'X-API-Key': process.env.AI_SERVICE_API_KEY
  }
});
```

#### Kiểm tra Full Flow Upload

**Backend cần làm theo thứ tự:**

```javascript
// Bước 1: Upload file lên R2 (Backend tự làm)
const r2Url = await uploadFileToR2(file);

// Bước 2: Tạo FormData cho AI Service
const formData = new FormData();
formData.append('file', file);
formData.append('data_type', 'products'); // hoặc 'services', 'info'  
formData.append('metadata', JSON.stringify({
  original_name: file.name,
  uploaded_by: userId,
  r2_url: r2Url,
  file_name: 'Tên file hiển thị',
  description: 'Mô tả file',
  tags: ['tag1', 'tag2']
}));

// Bước 3: Gọi AI Service để process
const response = await fetch(`${AI_SERVICE_URL}/api/admin/companies/${companyId}/files/upload`, {
  method: 'POST',
  headers: {
    'X-API-Key': process.env.AI_SERVICE_API_KEY,
    // Không set Content-Type cho multipart/form-data
  },
  body: formData
});

const result = await response.json();
if (result.success) {
  console.log('File processed successfully:', result.data);
} else {
  console.error('Processing failed:', result);
}
```

#### Debug Checklist cho Backend Team

**Trước khi gọi AI Service, kiểm tra:**

1. ✅ **Environment Variables**
   ```bash
   echo $AI_SERVICE_URL          # Should be: http://localhost:8000  
   echo $AI_SERVICE_API_KEY      # Should be: agent8x-backend-secret-key-2025
   ```

2. ✅ **AI Service Health**
   ```bash
   curl -X GET http://localhost:8000/health
   # Should return: {"status": "healthy", ...}
   ```

3. ✅ **Test Authentication**
   ```bash
   curl -X GET http://localhost:8000/api/admin/companies/test-id/stats \
     -H "X-API-Key: agent8x-backend-secret-key-2025"
   # Should NOT return 401
   ```

4. ✅ **Correct Endpoint URLs**
   - Upload: `POST /api/admin/companies/{id}/files/upload`
   - Delete: `DELETE /api/admin/companies/{id}/files/{file_id}`
   - Stats: `GET /api/admin/companies/{id}/stats`

**Nếu vẫn lỗi, log thêm info:**
```javascript
console.log('AI_SERVICE_URL:', process.env.AI_SERVICE_URL);
console.log('AI_SERVICE_API_KEY:', process.env.AI_SERVICE_API_KEY?.substring(0, 10) + '...');
console.log('Request URL:', `${AI_SERVICE_URL}/api/admin/companies/${companyId}/files/upload`);
console.log('Request Headers:', headers);
```
````
