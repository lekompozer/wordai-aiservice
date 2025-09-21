# Backend Integration API Documentation
## Products & Services CRUD Operations

## Overview
API endpoints for managing individual products and services with complete data replacement strategy. All operations work directly with Qdrant vector database and maintain data consistency through complete replacement approach.

### Base URL
```
POST /api/admin/companies/{company_id}/extract
GET  /api/admin/companies/{company_id}/products-services
PUT  /api/admin/companies/{company_id}/products/{qdrant_point_id}
PUT  /api/admin/companies/{company_id}/services/{qdrant_point_id}
DELETE /api/admin/companies/{company_id}/products/{qdrant_point_id}
DELETE /api/admin/companies/{company_id}/services/{qdrant_point_id}
```

### Authentication
All endpoints require `X-API-Key` header with internal API key.

### ⚠️ IMPORTANT: Backend Implementation Notes
**For ALL PUT and DELETE operations, Backend MUST send the Qdrant Point ID in the URL path:**

- **PUT/DELETE Path Parameter**: Use `qdrant_point_id` instead of `product_id`/`service_id`
- **Backend Responsibility**: Backend gets `qdrant_point_id` from the initial listing endpoint
- **AI Service Simplicity**: AI service performs direct Qdrant operations without searching
- **No Additional Verification**: Company ownership verification is optional since Backend controls the point IDs

**Example Flow:**
1. Backend calls GET `/products-services` → Gets items with `qdrant_point_id`
2. Backend stores/caches the `qdrant_point_id` for each item
3. For updates: Backend calls PUT `/products/{qdrant_point_id}` with new data
4. For deletion: Backend calls DELETE `/products/{qdrant_point_id}`
5. AI service performs direct Qdrant operations using the point ID

---

## 1. 📋 Get All Products & Services

### Endpoint
```http
GET /api/admin/companies/{company_id}/products-services
```

### Parameters
- **company_id** (path, required): Company identifier
- **limit** (query, optional): Maximum items to return (default: 100)
- **offset** (query, optional): Number of items to skip (default: 0)

### Request Headers
```json
{
  "X-API-Key": "your-internal-api-key",
  "Content-Type": "application/json"
}
```

### Response Format
```json
{
  "success": true,
  "message": "Retrieved all products and services for company comp_123",
  "company_id": "comp_123",
  "data": {
    "products": [
      {
        "qdrant_point_id": "product_abc123",
        "item_id": "prod_001",
        "name": "Bảo hiểm sức khỏe Premium",
        "type": "Bảo hiểm y tế",
        "category": "Bảo hiểm",
        "description": "Gói bảo hiểm toàn diện cho cả gia đình",
        "price": "2.500.000 VND/năm",
        "sku": "BH-SK-001",
        "status": "available",
        "tags": ["sức khỏe", "gia đình", "toàn diện"],
        "target_audience": ["gia đình trẻ", "người trung niên"],
        "image_urls": ["https://example.com/product1.jpg", "https://example.com/product1_thumb.jpg"],
        "created_at": "2025-07-29T10:00:00Z",
        "updated_at": "2025-07-29T10:00:00Z",
        "file_id": "file_456",
        "additional_fields": {
          "coverage_area": "Toàn quốc",
          "age_range": "0-65 tuổi",
          "terms_and_conditions": "Áp dụng sau 30 ngày chờ",
          "coverage_type": ["nội trú", "ngoại trú"]
        }
      }
    ],
    "services": [
      {
        "qdrant_point_id": "service_xyz789",
        "item_id": "serv_001",
        "name": "Tư vấn bảo hiểm miễn phí",
        "type": "Dịch vụ tư vấn",
        "category": "Tư vấn",
        "description": "Tư vấn miễn phí về các gói bảo hiểm phù hợp",
        "price": "Miễn phí",
        "sku": "TV-001",
        "status": "available",
        "tags": ["tư vấn", "miễn phí"],
        "target_audience": ["khách hàng mới"],
        "image_urls": ["https://example.com/service1.jpg"],
        "created_at": "2025-07-29T10:00:00Z",
        "updated_at": "2025-07-29T10:00:00Z",
        "file_id": "file_456",
        "additional_fields": {
          "availability": "24/7",
          "service_type": ["online", "offline"]
        }
      }
    ]
  },
  "total_count": 2,
  "summary": {
    "total_products": 1,
    "total_services": 1,
    "collection_name": "multi_company_data",
    "offset": 0,
    "limit": 100
  }
}
```

---

## 2. 🔄 Update Product (Complete Replacement)

### Endpoint
```http
PUT /api/admin/companies/{company_id}/products/{qdrant_point_id}
```

### Parameters
- **company_id** (path, required): Company identifier
- **qdrant_point_id** (path, required): Qdrant Point ID from the listing endpoint

### ⚠️ Backend Implementation
**Backend MUST provide the exact `qdrant_point_id` obtained from the GET `/products-services` endpoint:**
```javascript
// 1. Backend gets products list
const response = await fetch('/api/admin/companies/comp_123/products-services');
const data = await response.json();

// 2. Backend finds target product and extracts qdrant_point_id
const targetProduct = data.data.products.find(p => p.item_id === 'prod_001');
const qdrantPointId = targetProduct.qdrant_point_id; // e.g., "abc-123-xyz-789"

// 3. Backend sends update request with qdrant_point_id
await fetch(`/api/admin/companies/comp_123/products/${qdrantPointId}`, {
  method: 'PUT',
  body: JSON.stringify(updatedProductData)
});
```

### Request Headers
```json
{
  "X-API-Key": "your-internal-api-key",
  "Content-Type": "application/json"
}
```

### Request Body
```json
{
  "name": "Bảo hiểm sức khỏe Premium Plus",
  "type": "Bảo hiểm y tế cao cấp",
  "category": "Bảo hiểm",
  "description": "Gói bảo hiểm cao cấp với nhiều quyền lợi vượt trội",
  "price": "3.500.000 VND/năm",
  "sku": "BH-SK-002",
  "status": "available",
  "tags": ["sức khỏe", "cao cấp", "premium"],
  "target_audience": ["doanh nhân", "gia đình có thu nhập cao"],
  "image_urls": [
    "https://example.com/new_product_main.jpg",
    "https://example.com/new_product_detail.jpg",
    "https://cdn.mysite.com/uploaded/product_custom.png"
  ],
  "additional_fields": {
    "coverage_area": "Toàn cầu",
    "age_range": "0-75 tuổi",
    "terms_and_conditions": "Không có thời gian chờ",
    "coverage_type": ["nội trú", "ngoại trú", "răng hàm mặt", "sinh con"],
    "benefits": ["Khám sức khỏe định kỳ", "Ưu tiên khám bệnh"],
    "partner_hospitals": ["Vinmec", "FV Hospital", "Columbia Asia"]
  }
}
```

### Required Fields
- **name**: Product name (string)
- **type**: Product type (string)
- **category**: Product category (string)
- **description**: Product description (string)
- **price**: Product price (string)

### Optional Fields
- **sku**: Product SKU (string)
- **status**: Product status (string, default: "available")
- **tags**: Product tags (array of strings)
- **target_audience**: Target audience (array of strings)
- **image_urls**: Product image URLs (array of strings) - Upload or external URLs
- **additional_fields**: Any additional data as JSON object

### Response Format
```json
{
  "success": true,
  "message": "Product completely replaced successfully",
  "item_id": "prod_001",
  "qdrant_point_id": "abc-123-xyz-789",
  "changes_made": {
    "operation": "complete_replacement",
    "old_name": "Bảo hiểm sức khỏe Premium",
    "new_name": "Bảo hiểm sức khỏe Premium Plus",
    "fresh_embedding": true,
    "fresh_content": true,
    "immutable_fields_preserved": ["company_id", "file_id", "created_at"],
    "required_fields_updated": ["name", "type", "category", "description", "price"],                "optional_fields_count": 4,
                "additional_fields_keys": ["coverage_area", "age_range", "terms_and_conditions", "coverage_type", "benefits", "partner_hospitals"]
  }
}
```

---

## 3. 🔄 Update Service (Complete Replacement)

### Endpoint
```http
PUT /api/admin/companies/{company_id}/services/{qdrant_point_id}
```

### Parameters
- **company_id** (path, required): Company identifier
- **qdrant_point_id** (path, required): Qdrant Point ID from the listing endpoint

### ⚠️ Backend Implementation
**Backend MUST provide the exact `qdrant_point_id` obtained from the GET `/products-services` endpoint:**
```javascript
// 1. Backend gets services list
const response = await fetch('/api/admin/companies/comp_123/products-services');
const data = await response.json();

// 2. Backend finds target service and extracts qdrant_point_id
const targetService = data.data.services.find(s => s.item_id === 'serv_001');
const qdrantPointId = targetService.qdrant_point_id; // e.g., "def-456-uvw-012"

// 3. Backend sends update request with qdrant_point_id
await fetch(`/api/admin/companies/comp_123/services/${qdrantPointId}`, {
  method: 'PUT',
  body: JSON.stringify(updatedServiceData)
});
```

### Request Headers
```json
{
  "X-API-Key": "your-internal-api-key",
  "Content-Type": "application/json"
}
```

### Request Body
```json
{
  "name": "Tư vấn bảo hiểm chuyên sâu",
  "type": "Dịch vụ tư vấn chuyên nghiệp",
  "category": "Tư vấn",
  "description": "Tư vấn chuyên sâu về các gói bảo hiểm phức tạp với chuyên gia",
  "price": "500.000 VND/session",
  "sku": "TV-002",
  "status": "available",
  "tags": ["tư vấn", "chuyên sâu", "chuyên gia"],
  "target_audience": ["doanh nghiệp", "khách hàng cao cấp"],
  "image_urls": [
    "https://example.com/consultant_service.jpg",
    "https://cdn.mysite.com/office_consultation.png"
  ],
  "additional_fields": {
    "availability": "Thứ 2-6, 9:00-17:00",
    "duration": "60 phút",
    "service_type": ["online", "offline", "tại nhà"],
    "consultant_level": "Senior Expert",
    "booking_required": true
  }
}
```

### Required Fields
- **name**: Service name (string)
- **type**: Service type (string)
- **category**: Service category (string)
- **description**: Service description (string)
- **price**: Service price (string)

### Optional Fields
- **sku**: Service SKU (string)
- **status**: Service status (string, default: "available")
- **tags**: Service tags (array of strings)
- **target_audience**: Target audience (array of strings)
- **image_urls**: Service image URLs (array of strings) - Upload or external URLs
- **additional_fields**: Any additional data as JSON object

### Response Format
```json
{
  "success": true,
  "message": "Service completely replaced successfully",
  "item_id": "serv_001",
  "qdrant_point_id": "def-456-uvw-012",
  "changes_made": {
    "operation": "complete_replacement",
    "old_name": "Tư vấn bảo hiểm miễn phí",
    "new_name": "Tư vấn bảo hiểm chuyên sâu",
    "fresh_embedding": true,
    "fresh_content": true,
    "immutable_fields_preserved": ["company_id", "file_id", "created_at"],
    "required_fields_updated": ["name", "type", "category", "description", "price"],                "optional_fields_count": 6,
                "additional_fields_keys": ["availability", "duration", "service_type", "consultant_level", "booking_required"]
  }
}
```

---

## 4. 🗑️ Delete Product

### Endpoint
```http
DELETE /api/admin/companies/{company_id}/products/{qdrant_point_id}
```

### Parameters
- **company_id** (path, required): Company identifier
- **qdrant_point_id** (path, required): Qdrant Point ID from the listing endpoint

### ⚠️ Backend Implementation
**Backend MUST provide the exact `qdrant_point_id` obtained from the GET `/products-services` endpoint:**
```javascript
// 1. Backend gets products list
const response = await fetch('/api/admin/companies/comp_123/products-services');
const data = await response.json();

// 2. Backend finds target product and extracts qdrant_point_id  
const targetProduct = data.data.products.find(p => p.item_id === 'prod_001');
const qdrantPointId = targetProduct.qdrant_point_id; // e.g., "abc-123-xyz-789"

// 3. Backend sends delete request with qdrant_point_id
await fetch(`/api/admin/companies/comp_123/products/${qdrantPointId}`, {
  method: 'DELETE'
});
```

### ✅ AI Service Implementation
**AI Service performs direct deletion without additional verification:**
```python
# AI Service receives qdrant_point_id directly from URL path
qdrant_point_id = path_params.get("qdrant_point_id")

# Direct deletion - no search required
result = qdrant_manager.client.delete(
    collection_name=collection_name,
    points_selector=[qdrant_point_id],  # Direct point ID deletion
    wait=True
)
```

### Request Headers
```json
{
  "X-API-Key": "your-internal-api-key"
}
```

### Response Format
```json
{
  "success": true,
  "message": "Product deleted successfully",
  "item_id": "prod_001",
  "qdrant_point_id": "abc-123-xyz-789",
  "changes_made": {
    "deleted": true,
    "product_name": "Bảo hiểm sức khỏe Premium Plus"
  }
}
```

---

## 5. 🗑️ Delete Service

### Endpoint
```http
DELETE /api/admin/companies/{company_id}/services/{qdrant_point_id}
```

### Parameters
- **company_id** (path, required): Company identifier
- **qdrant_point_id** (path, required): Qdrant Point ID from the listing endpoint

### ⚠️ Backend Implementation
**Backend MUST provide the exact `qdrant_point_id` obtained from the GET `/products-services` endpoint:**
```javascript
// 1. Backend gets services list
const response = await fetch('/api/admin/companies/comp_123/products-services');
const data = await response.json();

// 2. Backend finds target service and extracts qdrant_point_id
const targetService = data.data.services.find(s => s.item_id === 'serv_001');
const qdrantPointId = targetService.qdrant_point_id; // e.g., "def-456-uvw-012"

// 3. Backend sends delete request with qdrant_point_id
await fetch(`/api/admin/companies/comp_123/services/${qdrantPointId}`, {
  method: 'DELETE'
});
```

### ✅ AI Service Implementation
**AI Service performs direct deletion without additional verification:**
```python
# AI Service receives qdrant_point_id directly from URL path
qdrant_point_id = path_params.get("qdrant_point_id")

# Direct deletion - no search required
result = qdrant_manager.client.delete(
    collection_name=collection_name,
    points_selector=[qdrant_point_id],  # Direct point ID deletion
    wait=True
)
```

### Request Headers
```json
{
  "X-API-Key": "your-internal-api-key"
}
```

### Response Format
```json
{
  "success": true,
  "message": "Service deleted successfully",
  "item_id": "serv_001",
  "qdrant_point_id": "def-456-uvw-012",
  "changes_made": {
    "deleted": true,
    "service_name": "Tư vấn bảo hiểm chuyên sâu"
  }
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Validation error message"
}
```

### 401 Unauthorized
```json
{
  "detail": "Invalid API key"
}
```

### 403 Forbidden
```json
{
  "detail": "Access denied: Product belongs to different company"
}
```

### 404 Not Found
```json
{
  "detail": "Product not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Product replacement failed: detailed error message"
}
```

---

## Key Features

### 🔒 Immutable Fields
These fields cannot be changed during updates:
- **company_id**: Security - ensures data ownership
- **file_id**: Traceability - maintains link to original extraction file
- **created_at**: Audit trail - preserves original creation timestamp

### 🔄 Complete Replacement Strategy
- **Fresh Embedding**: New vector generated from updated content
- **No Stale Data**: All fields completely replaced with new payload
- **Flexible Structure**: Additional fields allow custom data extension
- **Direct Operations**: No search required - uses Qdrant Point ID directly

### 📊 Rich Metadata
Each item includes comprehensive metadata for:
- **Filtering**: By category, tags, target audience, status
- **Search**: Vector similarity and text-based search
- **Management**: Creation/update timestamps, file references

### 🎯 Backend Integration Requirements
- **Point ID Management**: Backend MUST store and use `qdrant_point_id` from listing API
- **Direct Operations**: All PUT/DELETE operations use Qdrant Point ID in URL path
- **No Search Overhead**: AI Service performs direct Qdrant operations without filtering
- **Simplified Flow**: No additional verification steps required in AI Service

### 🚀 Performance Benefits
- **Faster Operations**: Direct point access vs. filtered search
- **Reduced Complexity**: No index requirements for filtering fields
- **Better Reliability**: Eliminates search-based errors and edge cases
- **Scalable**: Works efficiently even with large datasets
- **Image Management**: Support for multiple image URLs per item

### 🖼️ Image URL Management
- **Multiple Images**: Each product/service can have multiple image URLs
- **Flexible Sources**: Support both uploaded files and external URLs
- **Frontend Control**: Frontend can add/remove/reorder image URLs
- **Optional Field**: Images are optional - items can exist without images
- **URL Validation**: Frontend should validate URL format and accessibility

---

## Usage Examples

## Usage Examples

### Backend Integration Flow
```javascript
// 1. Get all products and services with their Qdrant Point IDs
const response = await fetch('/api/admin/companies/comp_123/products-services');
const data = await response.json();

// 2. Store point IDs for later operations
const productPointIds = {};
const servicePointIds = {};

data.data.products.forEach(product => {
  productPointIds[product.item_id] = product.qdrant_point_id;
});

data.data.services.forEach(service => {
  servicePointIds[service.item_id] = service.qdrant_point_id;
});

// 3. Update a product using its Qdrant Point ID
const qdrantPointId = productPointIds['prod_001']; // Get stored point ID
await fetch(`/api/admin/companies/comp_123/products/${qdrantPointId}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: "Updated Product Name",
    type: "Updated Type",
    category: "Updated Category",
    description: "Updated Description",
    price: "Updated Price"
  })
});

// 4. Delete a service using its Qdrant Point ID
const serviceQdrantId = servicePointIds['serv_001']; // Get stored point ID
await fetch(`/api/admin/companies/comp_123/services/${serviceQdrantId}`, {
  method: 'DELETE'
});
```

### Complete Product Management Flow
1. **List Products**: Get all products with their Qdrant point IDs
2. **Store Point IDs**: Backend stores mapping between item IDs and Qdrant point IDs
3. **Update Product**: Send complete new data using Qdrant Point ID
4. **Delete Product**: Remove individual product using Qdrant Point ID
5. **Verify Changes**: Re-list to confirm updates

### Custom Field Management
```json
{
  "additional_fields": {
    "custom_category": "Special Offer",
    "promotion_data": {
      "discount": "20%",
      "valid_until": "2025-12-31"
    },
    "internal_notes": "High-priority product",
    "compliance_data": {
      "regulations": ["GDPR", "Insurance Law"],
      "last_audit": "2025-07-01"
    }
  }
}
```

### Image URL Management Examples
```json
{
  "image_urls": [
    "https://cdn.mycompany.com/uploads/product_123_main.jpg",
    "https://cdn.mycompany.com/uploads/product_123_detail.jpg", 
    "https://external-site.com/shared/product_image.png",
    "https://s3.amazonaws.com/mybucket/product_gallery/img1.webp"
  ]
}
```

**Image URL Guidelines:**
- Use HTTPS URLs for security
- Support common formats: JPG, PNG, WebP, GIF
- Recommended: CDN URLs for better performance
- Frontend validation: Check URL accessibility before saving
- Multiple images: Main image should be first in array

This API provides complete flexibility while maintaining data integrity and security through the complete replacement strategy.
