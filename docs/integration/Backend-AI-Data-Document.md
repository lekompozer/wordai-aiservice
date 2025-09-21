# 🤖 AI SERVICE API DOCUMENTATION

## 📋 KIẾN TRÚC TỔNG QUAN

Backend Agent8x tương tác với AI Service thông qua RESTful API để quản lý dữ liệu công ty và xử lý AI. AI Service sử dụng Qdrant Vector Database để lưu trữ và tìm kiếm dữ liệu.

**Base URL AI Service**: 
- Production: `https://ai.aimoney.io.vn`
- Development: `http://localhost:8000`

---

## 🔐 AUTHENTICATION

Tất cả request đến AI Service sử dụng API Key authentication:

```typescript
Headers: {
  'X-API-Key': 'agent8x-backend-secret-key-2025',
  'X-API-Version': '1.0',
  'Content-Type': 'application/json'
}
```

---

## 📁 1. QUẢN LÝ COMPANY

### 1.1 Tạo Company (Register Company) ✅

**Backend Route**: `POST /api/companies/register`  
**AI Service Endpoint**: `POST /api/admin/companies/register`  
**Status**: ✅ Implemented

```typescript
// Trigger: User đăng ký company mới
const aiRegistrationData = {
  company_id: companyData.id,
  company_name: companyData.name,
  industry: companyData.industry
};

const result = await aiService.registerCompany(companyData.id, aiRegistrationData);
```

**AI Service Actions:**
- Tạo Collection mới trong Qdrant với `company_id`
- Khởi tạo cấu trúc dữ liệu vector store
- Tạo metadata fields cho company

### 1.2 Cập nhật Company Basic Info ✅

**Backend Route**: `PUT /api/companies/me`  
**AI Service Endpoint**: `PUT /api/admin/companies/{companyId}/basic-info`  
**Status**: ✅ Implemented

```typescript
// Trigger: User cập nhật thông tin company
const updateData = {
  company_name: company.name,
  industry: company.industry,
  metadata: {
    email: company.email,
    phone: company.phone,
    website: company.website,
    location: {
      country: company.country,
      city: company.city,
      address: company.address
    },
    description: company.description,
    social_links: company.socialLinks,
    business_info: {
      language: company.language,
      timezone: company.timezone,
      owner_firebase_uid: req.user.uid,
      created_at: company.createdAt
    }
  }
};

await aiService.updateCompanyBasicInfo(companyId, updateData);
```

### 1.3 Xóa Company ✅

**Backend Route**: `DELETE /api/companies/me`  
**AI Service Endpoint**: `DELETE /api/admin/companies/{companyId}`  
**Status**: ✅ Implemented

```typescript
// Trigger: Admin xóa company
await aiService.deleteCompany(companyId);
```

**AI Service Actions:**
- Xóa toàn bộ Collection trong Qdrant
- Xóa tất cả vector embeddings  
- Cleanup metadata

**Backend Actions:**
- Xóa tất cả files và R2 cleanup
- Xóa products, services, tags
- Xóa extraction jobs và templates
- Xóa company record

---

## 📄 2. QUẢN LÝ FILES (DOCUMENTS)

### 2.1 Upload File Thường ✅

**Backend Route**: `POST /api/files/upload`  
**AI Service Endpoint**: `POST /api/admin/companies/{companyId}/files/upload`  
**Status**: ✅ Implemented

```typescript
// Data types: 'document', 'image', 'video', 'audio', 'other'
const fileData = {
  r2_url: r2FileUrl,
  data_type: 'document',
  industry: company.industry,
  metadata: {
    original_name: file.originalname,
    file_id: fileId,
    file_name: fileName,
    file_size: file.size,
    file_type: file.mimetype,
    uploaded_by: req.user.uid,
    description: description,
    tags: tagNames
  }
};

await aiService.uploadFile(companyId, fileData);
```

### 2.2 Upload File Products/Services ✅

**Backend Route**: `POST /api/files/upload-with-industry`  
**AI Service Endpoint**: `POST /api/extract/process`  
**Status**: ✅ Implemented

```typescript
// Trigger: User upload file cho Products/Services extraction
const extractRequest = {
  r2_url: r2FileUrl,
  company_id: companyId,
  industry: validIndustry,
  file_metadata: {
    original_name: file.originalname,
    file_size: file.size,
    file_type: file.mimetype,
    uploaded_at: new Date().toISOString(),
    file_id: fileId
  },
  company_info: {
    id: company.id,
    name: company.name,
    industry: company.industry,
    description: company.description
  },
  language: language || 'vi',
  upload_to_qdrant: true,
  callback_url: `${config.urls.base}/api/webhooks/ai-service`
};

await aiService.extractFromR2(extractRequest);
```

### 2.3 Xóa File ✅

**Backend Route**: `DELETE /api/files/:fileId`  
**AI Service Endpoint**: `DELETE /api/admin/companies/{companyId}/files/{fileId}`  
**Status**: ✅ Implemented

```typescript
// Trigger: User xóa file
await aiService.deleteFile(companyId, fileId);
```

**AI Service Actions:**
- Xóa vector embeddings từ Qdrant
- Xóa raw text và JSON data
- Cleanup associated metadata

### 2.4 Xóa Files theo Tag ✅

**Backend Route**: `DELETE /api/files/tags/:tagId`  
**AI Service Endpoint**: `DELETE /api/admin/companies/{companyId}/files/tags/{tagName}`  
**Status**: ✅ Implemented

```typescript
// Trigger: User xóa tag (và tất cả files liên quan)
await aiService.deleteFilesByTag(companyId, tagName);
```

---

## 📦 3. QUẢN LÝ PRODUCTS & SERVICES

### 3.1 Extraction Process ✅

**Status**: ✅ Implemented  
**AI Service Process:**
1. Nhận file từ R2 URL
2. Extract dữ liệu theo industry template
3. Tạo JSON structured data
4. Upload vectors vào Qdrant
5. Gửi webhook callback về Backend

### 3.2 Lấy danh sách Products ✅

**Backend Route**: `GET /api/products`  
**AI Service Endpoint**: `GET /api/admin/companies/{companyId}/products`  
**Status**: ✅ Implemented

```typescript
// Query parameters: page, limit, category, status, search
const products = await productServiceController.getProducts(req, res);
```

### 3.3 Cập nhật Product ✅

**Backend Route**: `PUT /api/products/:productId`  
**AI Service Endpoint**: `PUT /api/admin/companies/{companyId}/products/{productId}`  
**Status**: ✅ Implemented

```typescript
// Trigger: User sửa thông tin product từ frontend
const updateData = {
  name: updatedName,
  description: updatedDescription,
  price: updatedPrice,
  category: updatedCategory,
  metadata: {
    updated_by: req.user.uid,
    updated_at: new Date().toISOString()
  }
};

await aiService.updateProduct(companyId, productId, updateData);
```

### 3.4 Xóa Product ✅

**Backend Route**: `DELETE /api/products/:productId`  
**AI Service Endpoint**: `DELETE /api/admin/companies/{companyId}/products/{productId}`  
**Status**: ✅ Implemented

### 3.5 Lấy danh sách Services ✅

**Backend Route**: `GET /api/services`  
**AI Service Endpoint**: `GET /api/admin/companies/{companyId}/services`  
**Status**: ✅ Implemented

### 3.6 Cập nhật Service ✅

**Backend Route**: `PUT /api/services/:serviceId`  
**AI Service Endpoint**: `PUT /api/admin/companies/{companyId}/services/{serviceId}`  
**Status**: ✅ Implemented

### 3.7 Xóa Service ✅

**Backend Route**: `DELETE /api/services/:serviceId`  
**AI Service Endpoint**: `DELETE /api/admin/companies/{companyId}/services/{serviceId}`  
**Status**: ✅ Implemented

---

## 🖼️ 4. QUẢN LÝ IMAGES

### 4.1 Upload Images với AI Instructions ✅

**Backend Route**: `POST /api/images/upload`  
**AI Service Endpoint**: `POST /api/admin/companies/{companyId}/images/upload`  
**Status**: ✅ Implemented

```typescript
// Trigger: User upload hình ảnh với AI instructions
const imageData = {
  r2_url: imageUrl,
  folder_name: folderName,
  ai_instruction: aiInstruction,
  metadata: {
    original_name: image.originalname,
    image_id: imageId,
    file_size: image.size,
    file_type: image.mimetype,
    uploaded_by: req.user.uid,
    description: description,
    alt_text: altText
  }
};

await aiService.uploadImage(companyId, imageData);
```

### 4.2 Lấy danh sách Images ✅

**Backend Route**: `GET /api/images`  
**AI Service Endpoint**: `GET /api/admin/companies/{companyId}/images`  
**Status**: ✅ Implemented

```typescript
// Query parameters: page, limit, folder_id, search, status
const images = await aiService.getImages(companyId, queryParams);
```

### 4.3 Cập nhật Images ✅

**Backend Route**: `PUT /api/images/:imageId`  
**AI Service Endpoint**: `PUT /api/admin/companies/{companyId}/images/{imageId}`  
**Status**: ✅ Implemented

```typescript
// Trigger: User cập nhật thông tin image, AI instructions
const updateData = {
  ai_instruction: updatedInstruction,
  description: updatedDescription,
  alt_text: updatedAltText,
  status: updatedStatus,
  metadata: {
    updated_by: req.user.uid,
    updated_at: new Date().toISOString()
  }
};

await aiService.updateImage(companyId, imageId, updateData);
```

### 4.4 Quản lý Folders ✅

**Backend Routes**: 
- `POST /api/images/folders` - Tạo folder
- `GET /api/images/folders` - Lấy danh sách folders
- `PUT /api/images/folders/:folderId` - Cập nhật folder  
- `DELETE /api/images/folders/:folderId` - Xóa folder và tất cả images

**AI Service Endpoints**:
- `POST /api/admin/companies/{companyId}/images/folders`
- `GET /api/admin/companies/{companyId}/images/folders`
- `PUT /api/admin/companies/{companyId}/images/folders/{folderId}`
- `DELETE /api/admin/companies/{companyId}/images/folders/{folderId}`

**Status**: ✅ Implemented

### 4.5 Xóa Images ✅

**Backend Route**: `DELETE /api/images/:imageId`  
**AI Service Endpoint**: `DELETE /api/admin/companies/{companyId}/images/{imageId}`  
**Status**: ✅ Implemented

```typescript
// Trigger: User xóa image
await aiService.deleteImage(companyId, imageId);
```

**AI Service Actions:**
- Xóa image vectors từ Qdrant
- Xóa image metadata và AI instructions
- Cleanup associated folder relationships

---

## 📊 5. MONITORING & HEALTH CHECK

### 5.1 Health Check ✅

**AI Service Endpoint**: `GET /api/health`  
**Status**: ✅ Implemented

```typescript
const healthStatus = await aiService.healthCheck();
```

### 5.2 Get Company Info ✅

**AI Service Endpoint**: `GET /api/admin/companies/{companyId}`  
**Status**: ✅ Implemented

### 5.3 Get Company Files ✅

**AI Service Endpoint**: `GET /api/admin/companies/{companyId}/files`  
**Status**: ✅ Implemented

---

## 🔔 6. WEBHOOK INTEGRATION

### 6.1 AI Service Webhook ✅

**Backend Endpoint**: `POST /api/webhooks/ai-service`  
**Status**: ✅ Implemented

AI Service gửi callback khi:
- File extraction hoàn thành
- Processing errors
- Status updates

### 6.2 AI Extraction Webhook ✅

**Backend Endpoint**: `POST /api/webhooks/ai/extraction`  
**Status**: ✅ Implemented

Webhook theo specification mới:

```typescript
const schema = {
  event: 'file.processed',
  companyId: 'string',
  data: {
    fileId: 'string',
    status: 'completed' | 'failed' | 'processing',
    extractedItems: number,
    chunksCreated: number,
    processingTime: number,
    processedAt: 'string',
    error?: 'string'
  },
  timestamp: 'string'
};
```

---

## 🎯 IMPLEMENTATION STATUS

### ✅ COMPLETED
- [x] Company registration
- [x] Company basic info update
- [x] Company deletion
- [x] File upload (regular)
- [x] File upload with industry processing
- [x] File deletion
- [x] Tag management
- [x] Products/Services extraction
- [x] Products management APIs
- [x] Services management APIs
- [x] Image management system
- [x] Image folder management
- [x] Image upload with R2 storage
- [x] Image CRUD operations
- [x] Webhook integration
- [x] Health monitoring

### ⚠️ IN PROGRESS (Priority 1)
- [ ] Enhanced error handling
- [ ] Performance optimizations for large image batches

### ❌ TODO (Priority 2)
- [ ] Image batch operations
- [ ] Advanced image search capabilities
- [ ] Retry mechanisms for failed uploads

---

## 📝 NOTES

### Error Handling
- All AI Service calls include retry logic with exponential backoff
- Webhook signature verification for security
- Comprehensive logging for debugging

### Security
- API Key authentication
- Request validation using Joi schemas
- Rate limiting protection

### Performance
- Async processing for file operations
- Background webhook processing
- Optimized database queries

---

## 🔧 CONFIGURATION

### Environment Variables

```bash
# AI Service Configuration
AI_SERVICE_URL=https://ai.aimoney.io.vn
AI_SERVICE_API_KEY=agent8x-backend-secret-key-2025
AI_SERVICE_TIMEOUT=30000
AI_WEBHOOK_SECRET=webhook-secret-for-signature
AI_SERVICE_RETRIES=3
AI_SERVICE_RETRY_DELAY=1000
```

### AI Service Base URLs

```typescript
const aiServiceConfig = {
  production: 'https://ai.aimoney.io.vn',
  development: 'http://localhost:8000',
  timeout: 30000,
  retries: 3
};
```

---

*Last updated: July 22, 2025*
