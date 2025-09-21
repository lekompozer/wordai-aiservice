# AI Service Integration - Create & Update Product APIs

## Overview
Tài liệu này mô tả cách AI Service tích hợp với Backend để tạo và cập nhật sản phẩm thông qua API endpoints. Backend sử dụng pattern "Optimistic Update" để đảm bảo phản hồi nhanh cho Frontend và đồng bộ với AI Service trong background.

## API Flow Summary

### 1. Create Product Flow
```
Frontend → Backend → Database (Immediate Save) → AI Service (Background Sync)
```
- Backend tạo sản phẩm mới trong database ngay lập tức
- Backend trả response thành công cho Frontend
- Backend gọi AI Service để tạo vector embedding trong background
- AI Service trả về `qdrant_point_id` và Backend update vào database

### 2. Update Product Flow  
```
Frontend → Backend → Check qdrant_point_id → Database (Immediate Update) → AI Service (Background Sync)
```
- **QUAN TRỌNG**: Product bắt buộc phải có `qdrant_point_id` từ AI Service
- Nếu không có `qdrant_point_id` → Trả lỗi `BAD_REQUEST`
- Backend update sản phẩm trong database ngay lập tức
- Backend trả response thành công cho Frontend  
- Backend gọi AI Service để update vector embedding trong background

## Backend Endpoints cho AI Service

### 1. Create Product API

**Frontend calls:**
```
POST /api/products-services/products
```

**Backend then calls AI Service:**
```
POST /api/admin/companies/{company_id}/products/{product_id}
```

#### Request Data Structure for CREATE
Backend sẽ gửi data tới AI Service với `product_id` trong URL path (AI Service sẽ tạo qdrant_point_id mới):

```json
{
  "name": "Tên sản phẩm",
  "type": "product",
  "category": "loan", 
  "description": "Mô tả sản phẩm",
  "price": "2000000",
  "currency": "VND",
  "price_unit": "VND/tháng",
  "sku": "PRODUCT-SKU",
  "status": "draft",
  "tags": ["tag1", "tag2"],
  "target_audience": ["audience1"],
  "image_urls": ["url1", "url2"],
  "additional_fields": {
    "custom_field": "value"
  },
  "industry_data": {
    "industry": "insurance",
    "template": "Life Insurance Product Extractor",
    "country": "Việt Nam",
    "language": "vi",
    "sub_category": "bao_hiem_suc_khoe",
    "coverage_type": ["benh_tat"]
  },
  "metadata": {
    "content_for_embedding": "Nội dung để tạo embedding",
    "ai_industry": "insurance",
    "ai_type": "Life Insurance"
  }
}
```

**Lưu ý**: 
- `product_id` được gửi trong URL path: `/products/{product_id}`
- AI Service sẽ tạo `qdrant_point_id` mới và trả về trong response
- Body chứa đầy đủ thông tin product bao gồm industry_data và metadata

#### Expected AI Service Response for CREATE
```json
{
  "success": true,
  "message": "Product created successfully",
  "item_id": "N/A",
  "qdrant_point_id": "generated-qdrant-point-id-12345",
  "changes_made": {
    "operation": "creation",
    "new_name": "Tên sản phẩm",
    "fresh_embedding": true,
    "fresh_content": true
  }
}
```

### 2. Update Product API

**Frontend calls:**
```
PUT /api/products-services/products/{productId}
```

**Backend then calls AI Service:**
```
PUT /api/admin/companies/{company_id}/products/{qdrant_point_id}
```

#### Request Data Structure for UPDATE
Backend sẽ gửi data tới AI Service với `qdrant_point_id` có sẵn trong URL path:

```json
{
  "name": "Tên sản phẩm đã cập nhật",
  "type": "product",
  "category": "loan",
  "description": "Mô tả đã cập nhật",
  "price": "2500000",
  "currency": "VND", 
  "price_unit": "VND/tháng",
  "sku": "PRODUCT-SKU",
  "status": "available",
  "tags": ["tag1", "tag2", "updated"],
  "target_audience": ["audience1"],
  "image_urls": ["url1", "url2"],
  "additional_fields": {
    "custom_field": "updated_value"
  },
  "industry_data": {
    "industry": "insurance",
    "template": "Life Insurance Product Extractor",
    "country": "Việt Nam",
    "language": "vi",
    "sub_category": "bao_hiem_suc_khoe",
    "coverage_type": ["benh_tat"],
    "premium": "2500000"
  },
  "metadata": {
    "content_for_embedding": "Nội dung đã cập nhật để tạo embedding",
    "ai_industry": "insurance",
    "ai_type": "Life Insurance",
    "target_audience": ["gia_dinh"]
  }
}
```

**Lưu ý**: 
- `qdrant_point_id` được gửi trong URL path: `/products/{qdrant_point_id}`
- Product phải có `qdrant_point_id` từ lần tạo trước đó
- Body chứa đầy đủ thông tin để update bao gồm industry_data và metadata
- AI Service sẽ update vector embedding với data mới

#### Expected AI Service Response for UPDATE
```json
{
  "success": true,
  "message": "Product completely replaced successfully",
  "item_id": "N/A",
  "qdrant_point_id": "existing-qdrant-point-id-12345",
  "changes_made": {
    "operation": "complete_replacement",
    "new_name": "Tên sản phẩm đã cập nhật",
    "fresh_embedding": true,
    "fresh_content": true
  }
}
```

## AI Service Implementation Requirements

### 1. API Endpoints
AI Service cần implement 2 endpoints riêng biệt:

#### CREATE Product Endpoint:
```
POST /api/admin/companies/{company_id}/products/{product_id}
```

#### UPDATE Product Endpoint:
```
PUT /api/admin/companies/{company_id}/products/{qdrant_point_id}
```

**Lưu ý quan trọng**:
- **CREATE**: Backend gửi `product_id` trong URL path, AI Service tạo `qdrant_point_id` mới
- **UPDATE**: Backend gửi `qdrant_point_id` có sẵn trong URL path, AI Service update vector hiện tại

### 2. Logic Handling

#### For CREATE (POST endpoint):
1. Nhận `product_id` từ URL path
2. Generate new `qdrant_point_id` 
3. Tạo vector embeddings từ `metadata.content_for_embedding`
4. Store in Qdrant database với payload đầy đủ bao gồm industry_data
5. Return success với `qdrant_point_id` mới tạo

#### For UPDATE (PUT endpoint):
1. Nhận `qdrant_point_id` từ URL path
2. Update existing vector trong Qdrant
3. Re-generate embeddings từ `metadata.content_for_embedding` mới
4. Update payload với industry_data và metadata mới
5. Return success confirmation

### 3. Data Structure để lưu trong Qdrant
Payload trong Qdrant Point sẽ chứa:

```json
{
  "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
  "content_type": "extracted_product",
  "product_name": "AIA – Khỏe Trọn Vẹn",
  "description": "Mô tả chi tiết sản phẩm...",
  "price": "2000000",
  "currency": "VND",
  "category": "bao_hiem",
  "sku": "3",
  "status": "draft",
  "tags": ["sức khỏe", "cao cấp", "premium"],
  "target_audience": ["gia_dinh"],
  "image_urls": ["https://example.com/image.jpg"],
  "industry_data": {
    "industry": "insurance",
    "template": "Life Insurance Product Extractor", 
    "country": "Việt Nam",
    "language": "vi",
    "sub_category": "bao_hiem_suc_khoe",
    "coverage_type": ["benh_tat"],
    "premium": "2000000"
  },
  "additional_fields": {
    "custom_field": "custom_value"
  },
  "searchable_text": "AIA Khỏe Trọn Vẹn bảo hiểm sức khỏe cao cấp...",
  "content": "Content for embedding generation",
  "created_at": "2025-07-30T10:00:00Z",
  "updated_at": "2025-07-30T10:00:00Z"
}
```

### 3. Error Handling
AI Service should return appropriate errors:

```json
{
  "success": false,
  "error": {
    "code": "QDRANT_ERROR",
    "message": "Failed to create/update vector",
    "details": "Specific error details"
  }
}
```

## Backend Implementation Details

### 1. Optimistic Update Pattern
- **Create Product**: Backend immediately saves to database → Returns success → Calls AI Service asynchronously
- **Update Product**: Backend checks `qdrant_point_id` exists → Updates database → Returns success → Calls AI Service asynchronously

### 2. Update Product Validation
**BẮT BUỘC**: Update API chỉ hoạt động khi product đã có `qdrant_point_id`
```typescript
if (!qdrantPointId) {
    throw errors.BAD_REQUEST('Product does not have qdrant_point_id - cannot update. Product must be synced with AI service first.');
}
```

### 3. AI Sync Status Tracking
Backend tracks sync status in database:
- `pending`: AI sync in progress
- `completed`: AI sync successful  
- `failed`: AI sync failed (with error message)

### 4. Background Sync Methods

#### syncNewProductWithAI() - Cho Create Product
```typescript
private async syncNewProductWithAI(
    companyId: string,
    productId: string, 
    data: ProductWithIndustryData
): Promise<void> {
    // Call AI Service: POST /api/admin/companies/{companyId}/products/{productId}
    // Gửi đầy đủ data bao gồm industry_data và metadata
    // Nhận qdrant_point_id từ AI Service response
    // Update qdrant_point_id vào database
    // Update ai_sync_status
}
```

#### syncExistingProductWithAI() - Cho Update Product
```typescript
private async syncExistingProductWithAI(
    companyId: string,
    qdrantPointId: string,
    data: ProductWithIndustryData
): Promise<void> {
    // Call AI Service: PUT /api/admin/companies/{companyId}/products/{qdrantPointId}
    // Gửi đầy đủ data bao gồm industry_data và metadata mới
    // Không cần update qdrant_point_id (đã có sẵn)
    // Update ai_sync_status
}
```

#### ProductWithIndustryData Interface
```typescript
interface ProductWithIndustryData {
  // Core fields
  name: string;
  type: string;
  category: string;
  description: string;
  price: string;
  currency?: string;
  price_unit?: string;
  sku?: string;
  status?: string;
  tags?: string[];
  target_audience?: string[];
  image_urls?: string[];
  
  // Industry template data
  industry_data?: {
    industry: string;
    template: string;
    country: string;
    language: string;
    sub_category?: string;
    coverage_type?: string[];
    premium?: string;
    [key: string]: any;
  };
  
  // AI metadata  
  metadata?: {
    content_for_embedding: string;
    ai_industry: string;
    ai_type: string;
    target_audience?: string[];
    [key: string]: any;
  };
  
  // Additional custom fields
  additional_fields?: {
    [key: string]: any;
  };
}
```

### 4. Database Schema Updates
Products table includes industry template support:
```sql
-- Core product fields  
name VARCHAR(255) NOT NULL,
description TEXT,
price VARCHAR(100),
currency VARCHAR(10) DEFAULT 'VND',
price_unit VARCHAR(50) DEFAULT 'per item',
sku VARCHAR(100),
status VARCHAR(50) DEFAULT 'draft',
tags TEXT[], -- Array of tags
target_audience TEXT[], -- Array of target audience
image_urls TEXT[], -- Array of image URLs

-- Industry template data (JSONB)
industry_data JSONB, -- Template selection, industry-specific fields
additional_fields JSONB, -- Custom user fields  
metadata JSONB, -- AI metadata including content_for_embedding

-- AI Service integration fields
qdrant_point_id VARCHAR(255), -- ID from AI Service
ai_sync_status VARCHAR(50) DEFAULT 'pending', -- pending|completed|failed
ai_sync_error TEXT, -- Error message if sync failed
ai_last_sync_at TIMESTAMP -- Last sync timestamp
```

#### Example industry_data JSONB:
```json
{
  "industry": "insurance",
  "template": "Life Insurance Product Extractor",
  "country": "Việt Nam", 
  "language": "vi",
  "sub_category": "bao_hiem_suc_khoe",
  "coverage_type": ["benh_tat"],
  "premium": "2000000"
}
```

#### Example metadata JSONB:
```json
{
  "content_for_embedding": "Bảo hiểm sức khỏe Bùng Gia Lực...",
  "ai_industry": "insurance",
  "ai_type": "Life Insurance",
  "target_audience": ["gia_dinh"]
}
```

## Testing Considerations

### 1. Database Testing Priority (Môi trường Test)
Trong môi trường test, ưu tiên test database operations:
- ✅ **CREATE**: Product được tạo thành công trong database
- ✅ **UPDATE**: Product được cập nhật thành công trong database  
- ✅ **VALIDATION**: Update API từ chối product không có qdrant_point_id
- ✅ **DATA INTEGRITY**: Dữ liệu được lưu đúng định dạng
- ⚠️ **AI SERVICE SYNC**: Secondary priority (có thể mock)

### 2. Test Cases Quan Trọng

#### Test Create Product với Industry Template
```javascript
const createData = {
  name: "AIA – Khỏe Trọn Vẹn",
  type: "product", 
  category: "bao_hiem",
  description: "Bảo hiểm sức khỏe toàn diện...",
  price: "2000000",
  currency: "VND",
  industry_data: {
    industry: "insurance",
    template: "Life Insurance Product Extractor",
    country: "Việt Nam",
    language: "vi",
    sub_category: "bao_hiem_suc_khoe",
    coverage_type: ["benh_tat"]
  },
  metadata: {
    content_for_embedding: "Nội dung chi tiết để tạo embedding...",
    ai_industry: "insurance",
    ai_type: "Life Insurance"
  },
  additional_fields: {
    custom_field: "custom_value"
  }
};

const response = await createProduct(createData);
expect(response.status).toBe(201);
expect(response.data.productId).toBeDefined();

// Verify trong database
const dbProduct = await getProductFromDB(response.data.productId);
expect(dbProduct.name).toBe(createData.name);
expect(dbProduct.industry_data.industry).toBe("insurance");
expect(dbProduct.metadata.ai_industry).toBe("insurance");
```

#### Test Update Product với Industry Template
```javascript
const updateData = {
  name: "AIA – Khỏe Trọn Vẹn (Cập nhật)",
  type: "product",
  category: "bao_hiem", 
  description: "Mô tả đã cập nhật...",
  price: "2500000",
  industry_data: {
    industry: "insurance",
    template: "Life Insurance Product Extractor",
    country: "Việt Nam", 
    language: "vi",
    sub_category: "bao_hiem_suc_khoe",
    coverage_type: ["benh_tat", "tai_nan"],
    premium: "2500000" // Updated premium
  },
  metadata: {
    content_for_embedding: "Nội dung cập nhật để tạo embedding...",
    ai_industry: "insurance",
    ai_type: "Life Insurance",
    target_audience: ["gia_dinh", "ca_nhan"]
  }
};

// Product có qdrant_point_id (đã sync với AI)
const response = await updateProduct(productId, updateData);
expect(response.status).toBe(200);

// Verify database updated với industry template
const dbProduct = await getProductFromDB(productId);
expect(dbProduct.name).toBe(updateData.name);
expect(dbProduct.industry_data.premium).toBe("2500000");
expect(dbProduct.metadata.target_audience).toContain("ca_nhan");
```

#### Test Update Product - Validation Error
```javascript
// Product chưa có qdrant_point_id
const response = await updateProduct(newProductId, updateData);
expect(response.status).toBe(400);
expect(response.error.message).toContain('qdrant_point_id');
```
Recommend using mock AI Service responses for unit tests:
```typescript
// Mock successful response
mockAIService.updateProduct.mockResolvedValue({
    success: true,
    data: { qdrant_point_id: "mock-id" }
});
```

### 3. Integration Testing
For integration tests with real AI Service:
- Test create product flow end-to-end
- Test update product flow end-to-end
- Test error handling scenarios
- Test retry mechanisms

## Error Recovery

### 1. Failed AI Sync Handling
- Product remains in database with `ai_sync_status: 'failed'`
- Background job can retry sync later
- Admin dashboard can show sync status
- Manual retry option available

### 2. Retry Mechanism
```typescript
// Implement exponential backoff retry
private async retryAISync(
    productId: string,
    maxRetries: number = 3
): Promise<void> {
    // Retry logic with exponential backoff
}
```

## Monitoring & Logging

### 1. Key Metrics to Track
- Product creation success rate
- Product update success rate  
- AI sync success rate
- Average sync response time
- Failed sync error patterns

### 2. Logging Requirements
```typescript
logger.info(`Product ${productId} created successfully in database`);
logger.info(`Syncing product ${productId} with AI service...`);
logger.error(`AI sync failed for product ${productId}:`, error);
logger.info(`AI sync completed for product ${productId} with qdrant_id: ${qdrantId}`);
```

## Conclusion

Pattern này đảm bảo:
- ✅ Frontend có response ngay lập tức
- ✅ Database consistency được đảm bảo
- ✅ AI Service sync không block main flow
- ✅ Error handling và retry mechanism
- ✅ Full traceability và monitoring

AI Service team chỉ cần focus vào implement PUT endpoint với logic create/update vector embeddings và return appropriate responses.
