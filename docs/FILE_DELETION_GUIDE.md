# File Deletion API Guide
# Hướng dẫn API Xóa File

Tài liệu này mô tả chi tiết **2 loại xóa file khác nhau** và cách sử dụng endpoints đã được phân tách để tránh xung đột.

## 📋 Tổng quan File Deletion APIs

Hệ thống có **2 loại xóa file khác nhau** phục vụ 2 workflows khác nhau:

### 1. **Simple File Deletion** (Raw Content)
- **Endpoint**: `DELETE /api/admin/companies/{company_id}/files/{file_id}`
- **File**: `src/api/admin/file_routes.py`
- **Chức năng**: Xóa file đơn giản - chỉ xóa raw content chunks
- **Use Case**: Xóa file upload thông thường (documents, images, etc.)

### 2. **Extraction Data Deletion** (Structured Data)
- **Endpoint**: `DELETE /api/admin/companies/{company_id}/extractions/{file_id}`  
- **File**: `src/api/admin/products_services_routes.py`
- **Chức năng**: Xóa file + TẤT CẢ structured data (products/services) được extract
- **Use Case**: Xóa kết quả AI extraction hoàn toàn

---

## 🗑️ Type 1: Simple File Deletion

### Endpoint:
```
DELETE /api/admin/companies/{company_id}/files/{file_id}
```

### Description:
Xóa file đơn giản - chỉ xóa file content chunks, không ảnh hướng tới structured data.

### Request Example:
```bash
curl -X DELETE "https://ai-api.example.com/api/admin/companies/company-123/files/file_456789" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Response (Success):
```json
{
  "success": true,
  "message": "File file_456789 deleted successfully",
  "deleted_points": 8,
  "collection": "multi_company_data"
}
```

### Response (Not Found):
```json
{
  "success": false,
  "message": "File file_456789 not found in company company-123",
  "deleted_points": 0,
  "collection": "multi_company_data",
  "company_id": "company-123",
  "file_id": "file_456789",
  "error": "FILE_NOT_FOUND",
  "details": "No data found for this file in the vector database. File may have been already deleted or never uploaded."
}
```

### Logic Flow:
1. ✅ Validates company_id and file_id
2. ✅ Uses `ai_service.delete_file_from_qdrant()` with file_id filter
3. ✅ Deletes only file content chunks from Qdrant
4. ✅ Returns count of deleted chunks
5. ❌ Does NOT delete products/services extracted from this file

### When to Use:
- Xóa file documents thông thường
- Xóa file images/videos không cần structured data
- Cleanup file storage without affecting business data

---

## 🎯 Type 2: Extraction Data Deletion

### Endpoint:
```
DELETE /api/admin/companies/{company_id}/extractions/{file_id}
```

### Description:
Xóa file + TẤT CẢ structured data (products, services, extraction metadata) được extract từ file đó.

### Request Example:
```bash
curl -X DELETE "https://ai-api.example.com/api/admin/companies/company-123/extractions/file_456789" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Response (Success):
```json
{
  "success": true,
  "message": "File file_456789 with all extraction data deleted successfully",
  "deleted_points": 25,
  "collection": "multi_company_data",
  "deletion_details": {
    "file_chunks": 8,
    "products_deleted": 12,
    "services_deleted": 5,
    "total_points": 25
  }
}
```

### Response (Not Found):
```json
{
  "success": false,
  "message": "File file_456789 with extraction data not found in company company-123",
  "deleted_points": 0,
  "collection": "multi_company_data",
  "company_id": "company-123",
  "file_id": "file_456789",
  "error": "EXTRACTION_DATA_NOT_FOUND",
  "details": "No extraction data (products/services) found for this file. File may have been already deleted, never processed for extraction, or only contains raw content."
}
```

### Logic Flow:
1. ✅ Validates company_id and file_id
2. ✅ Deletes ALL points with file_id filter (includes products, services, file content)
3. ✅ Additional cleanup with company_id + file_id filter for safety
4. ✅ Returns detailed count of deleted data types
5. ✅ Completely removes ALL traces of file and its extracted data

### When to Use:
- Xóa hoàn toàn kết quả AI extraction
- Remove file + all business data extracted từ file đó
- Cleanup after failed/incorrect extractions
- Complete data removal for compliance

---

## 🔄 File Workflows Comparison

### Workflow 1: File Upload → Simple Deletion
```mermaid
graph LR
    A[File Upload] --> B[Raw Content Extraction]
    B --> C[File Chunks in Qdrant]
    C --> D[DELETE /files/{file_id}]
    D --> E[File Chunks Deleted]
    E --> F[Structured Data Unchanged]
```

### Workflow 2: AI Extraction → Extraction Deletion
```mermaid
graph LR
    A[File Upload] --> B[AI Extraction]
    B --> C[Products + Services + File Chunks]
    C --> D[DELETE /extractions/{file_id}]
    D --> E[ALL Data Deleted]
    E --> F[Complete Removal]
```

---

## 🛠 Backend Implementation Examples

### 1. Simple File Deletion (JavaScript)
```javascript
// Delete uploaded file content only
const deleteFile = async (companyId, fileId) => {
  try {
    const response = await fetch(
      `/api/admin/companies/${companyId}/files/${fileId}`,
      {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${API_KEY}`
        }
      }
    );
    
    const result = await response.json();
    
    if (result.success) {
      console.log(`✅ File deleted: ${result.deleted_points} chunks removed`);
      // File content removed, structured data intact
    } else {
      console.error(`❌ File deletion failed: ${result.message}`);
    }
    
    return result;
  } catch (error) {
    console.error('File deletion error:', error);
  }
};
```

### 2. Extraction Data Deletion (JavaScript)
```javascript
// Delete file + all extracted products/services
const deleteExtraction = async (companyId, fileId) => {
  try {
    const response = await fetch(
      `/api/admin/companies/${companyId}/extractions/${fileId}`,
      {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${API_KEY}`
        }
      }
    );
    
    const result = await response.json();
    
    if (result.success) {
      console.log(`✅ Extraction deleted completely:`);
      console.log(`   📄 File chunks: ${result.deletion_details.file_chunks}`);
      console.log(`   📦 Products: ${result.deletion_details.products_deleted}`);
      console.log(`   🔧 Services: ${result.deletion_details.services_deleted}`);
      console.log(`   📊 Total points: ${result.deletion_details.total_points}`);
      
      // Complete data removal - file + all business data
    } else {
      console.error(`❌ Extraction deletion failed: ${result.message}`);
    }
    
    return result;
  } catch (error) {
    console.error('Extraction deletion error:', error);
  }
};
```

---

## 🔍 Testing & Debugging

### Test Simple File Deletion:
```bash
# 1. Upload a file first
curl -X POST "https://ai-api.example.com/api/admin/companies/test-company/files/upload" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "r2_url": "https://example.com/test.pdf",
    "data_type": "document",
    "industry": "REAL_ESTATE",
    "metadata": {
      "original_name": "test.pdf",
      "file_id": "test_file_123"
    }
  }'

# 2. Check file status
curl -X GET "https://ai-api.example.com/api/admin/companies/test-company/files/test_file_123/status" \
  -H "Authorization: Bearer YOUR_API_KEY"

# 3. Delete file only
curl -X DELETE "https://ai-api.example.com/api/admin/companies/test-company/files/test_file_123" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Test Extraction Data Deletion:
```bash
# 1. Run AI extraction first
curl -X POST "https://ai-api.example.com/api/admin/companies/test-company/extract" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "r2_url": "https://example.com/menu.pdf",
    "company_id": "test-company",
    "industry": "RESTAURANT",
    "file_metadata": {
      "original_name": "menu.pdf",
      "file_id": "menu_file_456"
    }
  }'

# 2. Check extraction results
curl -X GET "https://ai-api.example.com/api/admin/companies/test-company/products" \
  -H "Authorization: Bearer YOUR_API_KEY"

# 3. Delete extraction data completely
curl -X DELETE "https://ai-api.example.com/api/admin/companies/test-company/extractions/menu_file_456" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## 🚨 Important Notes

### ⚠️ Endpoint Conflict Resolution:
- **BEFORE**: Both endpoints used `/companies/{company_id}/files/{file_id}` → **CONFLICT!**
- **AFTER**: 
  - Simple deletion: `/companies/{company_id}/files/{file_id}`
  - Extraction deletion: `/companies/{company_id}/extractions/{file_id}` ← **NEW PATH**

### 🔐 Security & Authorization:
- Both endpoints require `verify_internal_api_key` dependency
- Only internal admin APIs can delete files
- No public access to deletion operations

### 📊 Data Impact:

| Operation | File Content | Products | Services | Metadata |
|-----------|-------------|----------|----------|----------|
| Simple File Deletion | ❌ Deleted | ✅ Preserved | ✅ Preserved | ✅ Preserved |
| Extraction Deletion | ❌ Deleted | ❌ Deleted | ❌ Deleted | ❌ Deleted |

### 🎯 Use Case Decision Tree:
```
Need to delete file?
├── File contains extracted business data? 
│   ├── YES → Use `/extractions/{file_id}` (complete removal)
│   └── NO → Use `/files/{file_id}` (file content only)
└── Want to keep extracted products/services?
    ├── YES → Use `/files/{file_id}` (preserve business data)
    └── NO → Use `/extractions/{file_id}` (complete cleanup)
```

---

## 📝 Summary

**✅ Đã giải quyết xung đột endpoint:**
- `file_routes.py`: `/companies/{company_id}/files/{file_id}` (simple deletion)
- `products_services_routes.py`: `/companies/{company_id}/extractions/{file_id}` (complete deletion)

**✅ Đã implement deletion methods:**
- `ai_service.delete_file_from_qdrant()`: Xóa tất cả points với file_id filter
- `ai_service.delete_file_with_company_filter()`: Xóa bổ sung với company_id + file_id filter

**✅ 2 workflows deletion rõ ràng:**
1. **Simple File Deletion**: Chỉ xóa file content, giữ nguyên structured data
2. **Extraction Data Deletion**: Xóa file + TẤT CẢ products/services extracted

**✅ Backend có thể chọn deletion type phù hợp:**
- Use `/api/admin/companies/{company_id}/files/{file_id}` cho file cleanup đơn giản
- Use `/api/admin/companies/{company_id}/extractions/{file_id}` cho complete data removal

**✅ Implementation Details:**
- Both routes now use proper AI service methods with Qdrant Cloud integration
- Error handling and logging for production debugging
- Proper point counting and deletion confirmation
- Fallback mechanisms for edge cases

**Next Steps:**
1. Backend update API calls sử dụng đúng endpoints
2. Test cả 2 loại deletion để verify hoạt động chính xác  
3. Update frontend UI để differentiate giữa 2 deletion options
4. Monitor deletion performance in production environment
