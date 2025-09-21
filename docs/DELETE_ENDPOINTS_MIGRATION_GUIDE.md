# Delete Endpoints Migration Guide
## ⚠️ BREAKING CHANGES: Updated Delete APIs for Complete Data Consistency

## Overview

Các delete endpoints đã được cập nhật để sử dụng **business IDs** (`product_id`, `service_id`, `file_id`) thay vì **internal Qdrant Point IDs** (`qdrant_point_id`). Điều này đảm bảo complete data consistency across multiple storage systems (MongoDB + Qdrant).

## 🔥 Breaking Changes Summary

### OLD Approach (❌ Deprecated)
```http
DELETE /api/admin/companies/{company_id}/products/{qdrant_point_id}
DELETE /api/admin/companies/{company_id}/services/{qdrant_point_id}
```

### NEW Approach (✅ Current)
```http
DELETE /api/admin/companies/{company_id}/products/{product_id}
DELETE /api/admin/companies/{company_id}/services/{service_id}
DELETE /api/admin/companies/{company_id}/extractions/{file_id}
```

---

## 🎯 Why This Change?

### Previous Issues:
1. **Inconsistent API Design**: Create/Update sử dụng business IDs, nhưng Delete sử dụng Qdrant Point IDs
2. **Backend Complexity**: Backend phải store và manage Qdrant Point IDs
3. **Incomplete Cleanup**: Chỉ xóa từ Qdrant, không xóa từ MongoDB catalog service
4. **Data Inconsistency**: Orphaned data có thể tồn tại trong MongoDB

### New Benefits:
1. **Consistent API Design**: Tất cả endpoints đều sử dụng business IDs
2. **Complete Data Cleanup**: Xóa từ cả MongoDB catalog và Qdrant
3. **Simplified Backend**: Backend chỉ cần quản lý business IDs
4. **Data Integrity**: Đảm bảo không có orphaned data

---

## 🚀 Updated Delete Endpoints

### 1. Delete Product

#### Endpoint
```http
DELETE /api/admin/companies/{company_id}/products/{product_id}
```

#### Parameters
- **company_id** (path, required): Company identifier
- **product_id** (path, required): Business product ID (từ Backend, consistent với create/update)

#### Request Headers
```json
{
  "X-API-Key": "your-internal-api-key"
}
```

#### New Data Flow
```
1. Backend calls DELETE /products/{product_id}
   ↓
2. AI Service deletes from MongoDB catalog service first
   ↓
3. AI Service deletes from Qdrant using product_id filter
   ↓
4. AI Service returns comprehensive deletion summary
```

#### Response Format
```json
{
  "success": true,
  "message": "Product prod_001 deletion completed (removed from both MongoDB catalog and Qdrant)",
  "item_id": "prod_001",
  "qdrant_point_id": null,
  "changes_made": {
    "operation": "complete_deletion",
    "product_id": "prod_001",
    "company_id": "comp_123",
    "mongodb_catalog_deleted": true,
    "qdrant_points_deleted": 1,
    "storage_systems_cleaned": ["mongodb_catalog", "qdrant"]
  }
}
```

### 2. Delete Service

#### Endpoint
```http
DELETE /api/admin/companies/{company_id}/services/{service_id}
```

#### Parameters
- **company_id** (path, required): Company identifier
- **service_id** (path, required): Business service ID (từ Backend, consistent với create/update)

#### Request Headers
```json
{
  "X-API-Key": "your-internal-api-key"
}
```

#### New Data Flow
```
1. Backend calls DELETE /services/{service_id}
   ↓
2. AI Service deletes from MongoDB catalog service first
   ↓
3. AI Service deletes from Qdrant using service_id filter
   ↓
4. AI Service returns comprehensive deletion summary
```

#### Response Format
```json
{
  "success": true,
  "message": "Service serv_001 deletion completed (removed from both MongoDB catalog and Qdrant)",
  "item_id": "serv_001",
  "qdrant_point_id": null,
  "changes_made": {
    "operation": "complete_deletion",
    "service_id": "serv_001",
    "company_id": "comp_123",
    "mongodb_catalog_deleted": true,
    "qdrant_points_deleted": 1,
    "storage_systems_cleaned": ["mongodb_catalog", "qdrant"]
  }
}
```

### 3. Delete File with All Products/Services

#### Endpoint
```http
DELETE /api/admin/companies/{company_id}/extractions/{file_id}
```

#### Parameters
- **company_id** (path, required): Company identifier
- **file_id** (path, required): File ID to delete with all its products and services

#### Request Headers
```json
{
  "X-API-Key": "your-internal-api-key"
}
```

#### New Data Flow
```
1. Backend calls DELETE /extractions/{file_id}
   ↓
2. AI Service deletes ALL products/services from MongoDB catalog by file_id
   ↓
3. AI Service deletes ALL vector points from Qdrant by file_id
   ↓
4. AI Service returns comprehensive deletion summary
```

#### Response Format
```json
{
  "success": true,
  "message": "File file_456 and all associated products/services deleted successfully from ALL storage systems",
  "deleted_points": 15,
  "deleted_catalog_items": 8,
  "total_deleted": 23,
  "collection": "multi_company_data",
  "company_id": "comp_123",
  "file_id": "file_456",
  "details": {
    "mongodb_catalog_deleted": 8,
    "qdrant_points_deleted": 15,
    "storage_systems_cleaned": ["mongodb_catalog", "qdrant"],
    "complete_cleanup": true
  }
}
```

---

## 📝 Backend Migration Checklist

### ❌ Remove Old Logic
```javascript
// OLD - Remove this approach
const response = await fetch('/api/admin/companies/comp_123/products-services');
const data = await response.json();

// Find target product and extract qdrant_point_id
const targetProduct = data.data.products.find(p => p.item_id === 'prod_001');
const qdrantPointId = targetProduct.qdrant_point_id;

// Delete using qdrant_point_id
await fetch(`/api/admin/companies/comp_123/products/${qdrantPointId}`, {
  method: 'DELETE'
});
```

### ✅ New Implementation
```javascript
// NEW - Use business IDs directly
const productId = 'prod_001'; // Business product ID
const serviceId = 'serv_001'; // Business service ID
const fileId = 'file_456';   // File ID

// Delete product using business ID
const deleteProductResponse = await fetch(`/api/admin/companies/comp_123/products/${productId}`, {
  method: 'DELETE',
  headers: {
    'X-API-Key': 'your-internal-api-key'
  }
});

// Delete service using business ID
const deleteServiceResponse = await fetch(`/api/admin/companies/comp_123/services/${serviceId}`, {
  method: 'DELETE',
  headers: {
    'X-API-Key': 'your-internal-api-key'
  }
});

// Delete entire file with all products/services
const deleteFileResponse = await fetch(`/api/admin/companies/comp_123/extractions/${fileId}`, {
  method: 'DELETE',
  headers: {
    'X-API-Key': 'your-internal-api-key'
  }
});

// Check comprehensive results
console.log('Product deletion:', await deleteProductResponse.json());
console.log('Service deletion:', await deleteServiceResponse.json());
console.log('File deletion:', await deleteFileResponse.json());
```

---

## 🔄 Migration Steps for Backend

### Step 1: Update URL Patterns
```javascript
// OLD URLs
const DELETE_PRODUCT_URL = `/api/admin/companies/${companyId}/products/${qdrantPointId}`;
const DELETE_SERVICE_URL = `/api/admin/companies/${companyId}/services/${qdrantPointId}`;

// NEW URLs
const DELETE_PRODUCT_URL = `/api/admin/companies/${companyId}/products/${productId}`;
const DELETE_SERVICE_URL = `/api/admin/companies/${companyId}/services/${serviceId}`;
const DELETE_FILE_URL = `/api/admin/companies/${companyId}/extractions/${fileId}`;
```

### Step 2: Remove Qdrant Point ID Management
```javascript
// REMOVE - No longer needed
class ProductManager {
  // Remove this method
  async getQdrantPointIdForProduct(productId) {
    // This logic is no longer needed
  }

  // Remove this storage
  private qdrantPointIds = new Map();
}
```

### Step 3: Update Delete Functions
```javascript
// NEW Delete Functions
class ProductService {
  async deleteProduct(companyId, productId) {
    const response = await fetch(`${API_BASE}/companies/${companyId}/products/${productId}`, {
      method: 'DELETE',
      headers: { 'X-API-Key': process.env.AI_SERVICE_API_KEY }
    });

    const result = await response.json();

    if (result.success) {
      console.log(`✅ Product ${productId} completely removed from all storage systems`);
      console.log(`   MongoDB items deleted: ${result.changes_made.mongodb_catalog_deleted ? 'Yes' : 'No'}`);
      console.log(`   Qdrant points deleted: ${result.changes_made.qdrant_points_deleted}`);
    }

    return result;
  }

  async deleteService(companyId, serviceId) {
    const response = await fetch(`${API_BASE}/companies/${companyId}/services/${serviceId}`, {
      method: 'DELETE',
      headers: { 'X-API-Key': process.env.AI_SERVICE_API_KEY }
    });

    const result = await response.json();

    if (result.success) {
      console.log(`✅ Service ${serviceId} completely removed from all storage systems`);
    }

    return result;
  }

  async deleteFileWithAllData(companyId, fileId) {
    const response = await fetch(`${API_BASE}/companies/${companyId}/extractions/${fileId}`, {
      method: 'DELETE',
      headers: { 'X-API-Key': process.env.AI_SERVICE_API_KEY }
    });

    const result = await response.json();

    if (result.success) {
      console.log(`✅ File ${fileId} and ALL associated data removed from all storage systems`);
      console.log(`   Total items deleted: ${result.total_deleted}`);
      console.log(`   MongoDB catalog items: ${result.deleted_catalog_items}`);
      console.log(`   Qdrant points: ${result.deleted_points}`);
    }

    return result;
  }
}
```

### Step 4: Update Error Handling
```javascript
// Handle new response format
const handleDeleteResult = (result, itemType, itemId) => {
  if (result.success) {
    const cleanedSystems = result.changes_made?.storage_systems_cleaned || [];
    console.log(`✅ ${itemType} ${itemId} deleted from: ${cleanedSystems.join(', ')}`);

    // Update UI - item completely removed
    removeItemFromUI(itemId);

    return { success: true, message: result.message };
  } else {
    if (result.error === 'EXTRACTION_DATA_NOT_FOUND') {
      // Item not found in any storage system
      console.warn(`⚠️ ${itemType} ${itemId} not found - may have been already deleted`);

      // Still update UI - item is effectively "deleted"
      removeItemFromUI(itemId);

      return { success: true, message: `${itemType} not found (may have been already deleted)` };
    } else {
      // Actual error
      console.error(`❌ Failed to delete ${itemType} ${itemId}: ${result.message}`);
      return { success: false, error: result.message };
    }
  }
};
```

---

## 🧪 Testing Guide

### Test Cases for Backend

#### 1. Test Product Deletion
```javascript
describe('Product Deletion', () => {
  it('should delete product using business ID', async () => {
    const companyId = 'comp_test';
    const productId = 'prod_test_001';

    // Delete product
    const result = await productService.deleteProduct(companyId, productId);

    // Verify complete deletion
    expect(result.success).toBe(true);
    expect(result.item_id).toBe(productId);
    expect(result.changes_made.mongodb_catalog_deleted).toBe(true);
    expect(result.changes_made.qdrant_points_deleted).toBeGreaterThan(0);

    // Verify both storage systems cleaned
    expect(result.changes_made.storage_systems_cleaned).toContain('mongodb_catalog');
    expect(result.changes_made.storage_systems_cleaned).toContain('qdrant');
  });

  it('should handle product not found gracefully', async () => {
    const result = await productService.deleteProduct('comp_test', 'nonexistent_product');

    expect(result.success).toBe(false);
    expect(result.error).toBe('EXTRACTION_DATA_NOT_FOUND');
  });
});
```

#### 2. Test Service Deletion
```javascript
describe('Service Deletion', () => {
  it('should delete service using business ID', async () => {
    const companyId = 'comp_test';
    const serviceId = 'serv_test_001';

    const result = await productService.deleteService(companyId, serviceId);

    expect(result.success).toBe(true);
    expect(result.item_id).toBe(serviceId);
    expect(result.changes_made.storage_systems_cleaned).toEqual(['mongodb_catalog', 'qdrant']);
  });
});
```

#### 3. Test File Deletion
```javascript
describe('File Deletion', () => {
  it('should delete file and all associated products/services', async () => {
    const companyId = 'comp_test';
    const fileId = 'file_test_001';

    const result = await productService.deleteFileWithAllData(companyId, fileId);

    expect(result.success).toBe(true);
    expect(result.file_id).toBe(fileId);
    expect(result.total_deleted).toBeGreaterThan(0);
    expect(result.deleted_catalog_items).toBeGreaterThanOrEqual(0);
    expect(result.deleted_points).toBeGreaterThanOrEqual(0);
    expect(result.details.complete_cleanup).toBe(true);
  });
});
```

---

## 💡 Best Practices

### 1. Error Handling
- Always check `result.success` before proceeding
- Handle `EXTRACTION_DATA_NOT_FOUND` as a non-critical warning
- Log deletion summary for audit purposes

### 2. UI Updates
- Remove items from UI immediately after successful deletion
- Show comprehensive deletion summary to users
- Handle partial failures gracefully

### 3. Data Consistency
- Use the new delete endpoints for complete cleanup
- Don't attempt to manually clean individual storage systems
- Trust the AI service to handle cross-system consistency

### 4. Monitoring
- Monitor deletion success rates
- Track which storage systems are being cleaned
- Alert on consistent deletion failures

---

## 📞 Support & Migration Help

### Common Issues During Migration

#### Issue 1: "Product not found" errors
**Cause**: Product may have been deleted from Qdrant but still exists in Backend DB
**Solution**: Use the new endpoints which handle both storage systems

#### Issue 2: Orphaned data in MongoDB
**Cause**: Old delete endpoints only cleaned Qdrant
**Solution**: Run a cleanup script or use the new file deletion endpoint

#### Issue 3: Inconsistent deletion results
**Cause**: Using old qdrant_point_id approach
**Solution**: Switch to business ID approach immediately

### Migration Timeline
1. **Phase 1**: Update Backend code to use new URLs and business IDs
2. **Phase 2**: Test with staging environment
3. **Phase 3**: Deploy to production and monitor deletion success rates
4. **Phase 4**: Clean up any orphaned data from old deletion approach

### Contact
- **Technical Issues**: Check AI service logs for detailed error messages
- **Data Consistency Issues**: Use file deletion endpoint to clean up
- **Performance Issues**: Monitor total deletion time and success rates

---

## 🎯 Summary

The new delete endpoints provide:
- **✅ Complete Data Consistency**: MongoDB + Qdrant cleanup
- **✅ Simplified Backend Logic**: Use business IDs directly
- **✅ Comprehensive Results**: Detailed deletion summary
- **✅ Better Performance**: Optimized deletion flow
- **✅ Audit Trail**: Complete logging and monitoring

**Action Required**: Update Backend code to use the new delete endpoints immediately for complete data consistency across all storage systems.
