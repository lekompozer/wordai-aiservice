# API Documentation - Company Management và CRUD Operations

## 📋 Tổng quan
Hướng dẫn đầy đủ về các API để quản lý company information, FAQs và Scenarios với MongoDB collection `companies`.

## 🏗️ Cấu trúc dữ liệu MongoDB

### Collection: `companies`
```javascript
{
  "_id": ObjectId("..."),
  "company_id": "uuid-string",
  "company_name": "Tên công ty",
  "industry": "banking|insurance|restaurant|...",
  "languages": ["vi", "en"],
  "qdrant_collection": "multi_company_data",

  // Basic Info Fields (THIẾU - cần cập nhật)
  "data_sources": {},
  "ai_config": {},
  "industry_config": {},
  "business_hours": null,
  "contact_info": null,

  // Extended Info (metadata)
  "metadata": {
    "email": "contact@company.com",
    "phone": "+84901234567",
    "website": "https://company.com",
    "location": {
      "country": "Vietnam",
      "city": "Ho Chi Minh City",
      "address": "123 Street Name"
    },
    "description": "Company description",
    "social_links": {
      "facebook": "https://facebook.com/company",
      "instagram": "https://instagram.com/company"
    },
    "faqs": [
      {
        "id": "uuid",
        "question": "Câu hỏi?",
        "answer": "Câu trả lời",
        "category": "general|products|services",
        "language": "vi|en",
        "priority": 1,
        "is_active": true,
        "created_at": "2025-08-03T00:00:00.000Z",
        "updated_at": "2025-08-03T00:00:00.000Z"
      }
    ],
    "scenarios": [
      {
        "id": "uuid",
        "title": "Scenario Title",
        "description": "Mô tả kịch bản",
        "trigger_keywords": ["keyword1", "keyword2"],
        "response_template": "Template phản hồi",
        "category": "greeting|support|sales",
        "language": "vi|en",
        "priority": 1,
        "is_active": true,
        "created_at": "2025-08-03T00:00:00.000Z",
        "updated_at": "2025-08-03T00:00:00.000Z"
      }
    ]
  },

  "created_at": ISODate("2025-08-03T00:00:00.000Z"),
  "updated_at": ISODate("2025-08-03T00:00:00.000Z")
}
```

## 🔧 API Endpoints

### 1. Company Registration & Basic Info

#### 1.1 Tạo công ty mới
```http
POST /api/admin/companies
Content-Type: application/json
Authorization: Bearer your-internal-api-key

{
  "company_id": "693409fd-c214-47db-a465-2e565b00be05",
  "company_name": "AIA Vietnam",
  "industry": "insurance"
}
```

#### 1.2 Cập nhật thông tin cơ bản công ty ⚠️ **ENDPOINT CHÍNH**
```http
PUT /api/admin/companies/{company_id}/basic-info
# HOẶC
POST /api/admin/companies/{company_id}/basic-info
Content-Type: application/json
Authorization: Bearer your-internal-api-key

{
  "basic_info": {
    "company_name": "AIA Vietnam Insurance",
    "industry": "insurance",
    "description": "Công ty bảo hiểm hàng đầu Việt Nam, cung cấp các giải pháp bảo hiểm và đầu tư toàn diện",
    "introduction": "Công ty bảo hiểm hàng đầu Việt Nam, cung cấp các giải pháp bảo hiểm và đầu tư toàn diện",
    "email": "contact@aia.com.vn",
    "phone": "+84 28 3520 2468",
    "website": "https://www.aia.com.vn",
    "location": {
      "country": "VN",
      "city": "Ho Chi Minh City",
      "address": "Unit 1501, 15th Floor, Saigon Trade Center, 37 Ton Duc Thang Street, Ben Nghe Ward, District 1"
    },
    "logo": "https://storage.company.com/logos/aia-logo.png",
    "socialLinks": {
      "facebook": "https://facebook.com/AIAVietnam",
      "twitter": "",
      "zalo": "0123456789",
      "whatsapp": "",
      "telegram": "",
      "instagram": "https://instagram.com/aiavietnam",
      "linkedin": "https://linkedin.com/company/aia-vietnam"
    },
    "products_summary": "Doanh nghiệp hoạt động trong lĩnh vực insurance",
    "contact_info": "Email: contact@aia.com.vn | Phone: +84 28 3520 2468 | Website: https://www.aia.com.vn | Address: Unit 1501, 15th Floor, Saigon Trade Center, Ho Chi Minh City, VN"
  }
}
```

**Lưu ý mapping dữ liệu:**
- `basic_info.company_name` → `companies.company_name` (root level)
- `basic_info.industry` → `companies.industry` (root level)
- `basic_info.email|phone|website|description|introduction|logo|products_summary|contact_info` → `companies.metadata.*`
- `basic_info.location` → `companies.metadata.location`
- `basic_info.socialLinks` → `companies.metadata.social_links`

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "success",
    "updated_fields": ["company_name", "industry", "metadata"],
    "company": {
      "_id": "688e6c85e00eae57e00a4698",
      "company_id": "693409fd-c214-47db-a465-2e565b00be05",
      "company_name": "AIA Vietnam Insurance",
      "industry": "insurance",
      "metadata": { /* metadata object */ },
      "updated_at": "2025-08-03T10:30:00.000Z"
    }
  }
}
```

#### 1.3 Lấy thông tin công ty
```http
GET /api/admin/companies/{company_id}
Authorization: Bearer your-internal-api-key
```

### 2. FAQs Management

#### 2.1 Tạo/Thay thế tất cả FAQs
```http
POST /api/admin/companies/{company_id}/context/faqs
Content-Type: application/json
Authorization: Bearer your-internal-api-key

[
  {
    "id": "faq-001",
    "question": "AIA có những sản phẩm bảo hiểm nào?",
    "answer": "AIA cung cấp đa dạng sản phẩm bảo hiểm nhân thọ, bảo hiểm sức khỏe, bảo hiểm giáo dục và đầu tư...",
    "category": "products",
    "language": "vi",
    "priority": 1,
    "is_active": true
  },
  {
    "id": "faq-002",
    "question": "What insurance products does AIA offer?",
    "answer": "AIA offers diverse life insurance, health insurance, education insurance and investment products...",
    "category": "products",
    "language": "en",
    "priority": 1,
    "is_active": true
  }
]
```

#### 2.2 Lấy tất cả FAQs
```http
GET /api/admin/companies/{company_id}/context/faqs
Authorization: Bearer your-internal-api-key
```

#### 2.3 Cập nhật FAQs (replace all)
```http
PUT /api/admin/companies/{company_id}/context/faqs
Content-Type: application/json
Authorization: Bearer your-internal-api-key

[/* FAQs array */]
```

#### 2.4 Thêm FAQ mới
```http
POST /api/admin/companies/{company_id}/context/faqs/add
Content-Type: application/json
Authorization: Bearer your-internal-api-key

{
  "id": "faq-003",
  "question": "Làm thế nào để đăng ký bảo hiểm AIA?",
  "answer": "Bạn có thể đăng ký bảo hiểm AIA qua website, hotline hoặc liên hệ trực tiếp với tư vấn viên...",
  "category": "services",
  "language": "vi",
  "priority": 2,
  "is_active": true
}
```

#### 2.5 Xóa tất cả FAQs
```http
DELETE /api/admin/companies/{company_id}/context/faqs
Authorization: Bearer your-internal-api-key
```

### 3. Scenarios Management

#### 3.1 Tạo/Thay thế tất cả Scenarios
```http
POST /api/admin/companies/{company_id}/context/scenarios
Content-Type: application/json
Authorization: Bearer your-internal-api-key

[
  {
    "id": "scenario-001",
    "title": "Chào đón khách hàng mới",
    "description": "Kịch bản chào đón và giới thiệu dịch vụ cho khách hàng lần đầu",
    "trigger_keywords": ["xin chào", "hello", "chào", "hi"],
    "response_template": "Xin chào! Chào mừng bạn đến với AIA Vietnam. Tôi có thể hỗ trợ gì cho bạn hôm nay?",
    "category": "greeting",
    "language": "vi",
    "priority": 1,
    "is_active": true
  },
  {
    "id": "scenario-002",
    "title": "Tư vấn sản phẩm bảo hiểm",
    "description": "Kịch bản tư vấn và giới thiệu các sản phẩm bảo hiểm",
    "trigger_keywords": ["sản phẩm", "bảo hiểm", "gói", "products", "insurance"],
    "response_template": "AIA có nhiều sản phẩm bảo hiểm phù hợp với từng nhu cầu. Bạn quan tâm đến loại bảo hiểm nào?",
    "category": "sales",
    "language": "vi",
    "priority": 2,
    "is_active": true
  }
]
```

#### 3.2 Lấy tất cả Scenarios
```http
GET /api/admin/companies/{company_id}/context/scenarios
Authorization: Bearer your-internal-api-key
```

#### 3.3 Cập nhật Scenarios (replace all)
```http
PUT /api/admin/companies/{company_id}/context/scenarios
Content-Type: application/json
Authorization: Bearer your-internal-api-key

[/* Scenarios array */]
```

#### 3.4 Thêm Scenario mới
```http
POST /api/admin/companies/{company_id}/context/scenarios/add
Content-Type: application/json
Authorization: Bearer your-internal-api-key

{
  "id": "scenario-003",
  "title": "Hỗ trợ khiếu nại",
  "description": "Kịch bản xử lý khiếu nại và hỗ trợ khách hàng",
  "trigger_keywords": ["khiếu nại", "complaint", "vấn đề", "problem", "help"],
  "response_template": "Tôi rất tiếc khi biết bạn gặp vấn đề. Bạn có thể chia sẻ chi tiết để tôi hỗ trợ tốt nhất?",
  "category": "support",
  "language": "vi",
  "priority": 3,
  "is_active": true
}
```

#### 3.5 Xóa tất cả Scenarios
```http
DELETE /api/admin/companies/{company_id}/context/scenarios
Authorization: Bearer your-internal-api-key
```

## 🔍 Validation & Testing

### Kiểm tra dữ liệu hiện tại trong MongoDB
```javascript
// Check company data
db.companies.find({"company_id": "693409fd-c214-47db-a465-2e565b00be05"}).pretty()

// Check if metadata exists
db.companies.find(
  {"company_id": "693409fd-c214-47db-a465-2e565b00be05"},
  {"metadata": 1, "company_name": 1, "industry": 1}
).pretty()

// Check FAQs
db.companies.find(
  {"company_id": "693409fd-c214-47db-a465-2e565b00be05"},
  {"metadata.faqs": 1}
).pretty()

// Check Scenarios
db.companies.find(
  {"company_id": "693409fd-c214-47db-a465-2e565b00be05"},
  {"metadata.scenarios": 1}
).pretty()
```

## ⚠️ Vấn đề hiện tại cần fix

### 1. **Thiếu thông tin cơ bản** ✅ FIXED
Dữ liệu hiện tại chỉ có:
```javascript
{
  company_id: '693409fd-c214-47db-a465-2e565b00be05',
  company_name: 'AIA',
  industry: 'insurance',
  // THIẾU tất cả metadata: email, phone, website, location, description, social_links
  // THIẾU faqs và scenarios
}
```
**Status**: ✅ API đã hỗ trợ dual-format cho backward compatibility

### 2. **Zalo field xử lý string** ✅ FIXED
Zalo field đã được định nghĩa như `Optional[str]` để hỗ trợ cả số điện thoại và link (zalo.me/username).

### 3. **AI Response History không lưu được** ✅ FIXED
**Vấn đề**: Trong streaming mode, AI response chỉ được lưu với placeholder `"[Streamed Response]"` thay vì nội dung thực tế.

**Giải pháp**:
- Tạo mechanism thu thập full response từ streaming chunks
- Sử dụng `_save_complete_conversation_async()` để lưu FULL AI response sau khi streaming hoàn tất
- Loại bỏ placeholder và lưu nội dung thực tế vào MongoDB

**Luồng xử lý mới**:
1. Stream chunks cho frontend
2. Accumulate full response trong memory
3. Sau khi stream xong, gọi `_save_complete_conversation_async()` với full content
4. Lưu user message + FULL AI response vào MongoDB

### 4. **Cần test API update basic info**
```bash
# Test update basic info API
curl -X PUT "http://localhost:8000/api/admin/companies/693409fd-c214-47db-a465-2e565b00be05/basic-info" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-internal-api-key" \
  -d '{
    "company_name": "AIA Vietnam Insurance",
    "metadata": {
      "email": "contact@aia.com.vn",
      "phone": "+84 28 3520 2468",
      "website": "https://www.aia.com.vn"
    }
  }'
### 4. **Cần test API update basic info**
```bash
# Test update basic info API
curl -X PUT "http://localhost:8000/api/admin/companies/693409fd-c214-47db-a465-2e565b00be05/basic-info" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-internal-api-key" \
  -d '{
    "company_name": "AIA Vietnam Insurance",
    "metadata": {
      "email": "contact@aia.com.vn",
      "phone": "+84 28 3520 2468",
      "website": "https://www.aia.com.vn"
    }
  }'
```

### 5. **Cần test FAQs và Scenarios**
Thêm FAQs và Scenarios để hoàn thiện company context.

## 📋 Checklist Implementation

- [x] **Fix Zalo field** - Hỗ trợ string cho link (zalo.me/username)
- [x] **Fix AI Response History** - Lưu FULL content thay vì "[Streamed Response]"
- [x] **API dual-format support** - Backward compatibility với legacy backend payload
- [ ] **Test API update basic info** với metadata đầy đủ
- [ ] **Verify dữ liệu được lưu** vào MongoDB collection `companies`
- [ ] **Test CRUD FAQs** - Create, Read, Update, Delete
- [ ] **Test CRUD Scenarios** - Create, Read, Update, Delete
- [ ] **Verify chat history** hiển thị đầy đủ với company context
- [ ] **Test multilingual support** cho FAQs và Scenarios
- [ ] **Performance test** với large dataset

## 🚀 Next Steps

1. **Immediate**: Test update basic info API để đảm bảo metadata được lưu
2. **Test**: Thêm FAQs và Scenarios mẫu cho company AIA
3. **Verify**: Chat responses sử dụng đúng company context
4. **Optimize**: Performance và caching cho large-scale operations

## ⚠️ Architecture Changes - DEPRECATED FILES

### Files đã DEPRECATED (không sử dụng nữa):
- `src/services/company_context_mongodb_service.py.DEPRECATED` - Service riêng cho company context
- Collection `company_context` (MongoDB) - Không sử dụng nữa

### Architecture hiện tại (UNIFIED):
- **Single Collection**: `companies` - Lưu tất cả thông tin company
- **Single Service**: `CompanyDBService` - Quản lý tất cả CRUD operations
- **FAQs & Scenarios**: Lưu trong `metadata.faqs` và `metadata.scenarios`
- **Basic Info**: Lưu trực tiếp trong company document

### Lý do thay đổi:
1. **Tránh dual-collection sync**: Không cần sync giữa 2 collections
2. **Đơn giản hóa**: Một service, một collection, dễ maintain
3. **Performance**: Giảm queries, tăng tốc độ
4. **Consistency**: Đảm bảo data integrity
