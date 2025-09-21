# Callback Implementation Status - RAW CONTENT & STRUCTURED DATA

## ✅ CẬP NHẬT HOÀN TẤT - Tất cả Callback đã bao gồm RAW CONTENT và STRUCTURED DATA

### 1. AI Extraction Callbacks (MAIN - ĐÃ CẬP NHẬT)

#### A. `_send_extraction_callback()` - ExtractionProcessingTask
**File**: `src/workers/document_processing_worker.py:637`
**Status**: ✅ **ĐÃ CẬP NHẬT** - Gửi đầy đủ RAW CONTENT và STRUCTURED DATA

**Payload includes**:
```javascript
{
    // Basic info
    "task_id": "extract_xxx",
    "company_id": "xxx",
    "status": "completed",
    
    // 📄 FULL RAW CONTENT
    "raw_content": "Full original text from file...",
    
    // 📦 FULL STRUCTURED DATA 
    "structured_data": {
        "products": [...],  // Full product details for database
        "services": [...],  // Full service details for database
        "extraction_summary": {...}
    },
    
    // Metadata
    "extraction_metadata": {...}
}
```

#### B. `_send_extraction_success_callback()` - DocumentProcessingTask  
**File**: `src/workers/document_processing_worker.py:877`
**Status**: ✅ **ĐÃ CẬP NHẬT** - Gửi đầy đủ RAW CONTENT và STRUCTURED DATA

#### C. `CallbackService.send_completion_callback()`
**File**: `src/workers/document_processing_worker.py:1554`
**Status**: ✅ **ĐÃ CẬP NHẬT** - Gửi đầy đủ RAW CONTENT và STRUCTURED DATA

### 2. Error Callbacks (OK - Không cần RAW CONTENT)
- ✅ `_send_extraction_error_callback()` - OK
- ✅ `_send_error_callback()` - OK  
- ✅ `CallbackService.send_error_callback()` - OK

### 3. File Upload Callback (ĐÃ CẬP NHẬT - Bây giờ có RAW CONTENT)
**File**: `src/api/admin/file_routes.py`
**Status**: ✅ **ĐÃ CẬP NHẬT** - Bổ sung RAW CONTENT cho đồng nhất

**Enhanced Payload includes**:
```javascript
{
    "event": "file.uploaded",
    "companyId": "xxx",
    "data": {
        "fileId": "xxx",
        "status": "completed",
        
        // ✅ RAW CONTENT (cho đồng nhất với các callback khác)
        "raw_content": "Full file content...",
        
        // ✅ Complete file metadata
        "file_metadata": {
            "original_name": "...",
            "file_name": "...",
            "file_size": 123,
            "file_type": "...",
            "uploaded_by": "...",
            "description": "...",
            "r2_url": "..."
        }
    }
}
```

---

## Backend Implementation Guide

### `/api/webhooks/ai/extraction-callback` (MAIN)
```javascript
app.post('/api/webhooks/ai/extraction-callback', webhookAuth, async (req, res) => {
    const { 
        task_id, 
        company_id, 
        raw_content,        // 📄 Full original text 
        structured_data,    // 📦 Products & Services array
        extraction_metadata,
        results 
    } = req.body;
    
    // 1. Save RAW CONTENT to database
    await db.extraction_jobs.update(
        { task_id },
        { 
            raw_content: raw_content,  // Store full original text
            extraction_metadata: JSON.stringify(extraction_metadata)
        }
    );
    
    // 2. Save PRODUCTS to database
    if (structured_data.products) {
        for (const product of structured_data.products) {
            await db.extracted_products.create({
                company_id: company_id,
                name: product.name,
                type: product.type,
                description: product.description,
                // ... all product fields
            });
        }
    }
    
    // 3. Save SERVICES to database  
    if (structured_data.services) {
        for (const service of structured_data.services) {
            await db.extracted_services.create({
                company_id: company_id,
                name: service.name,
                type: service.type,
                description: service.description,
                // ... all service fields
            });
        }
    }
    
    res.json({ 
        success: true, 
        message: "Full extraction data saved successfully" 
    });
});
```

## ✅ KẾT LUẬN

**TẤT CẢ CALLBACK đã được cập nhật để gửi đầy đủ**:
1. **📄 RAW CONTENT** - Full original text từ file (cả file upload và AI extraction)
2. **📦 STRUCTURED DATA** - Arrays của products và services với full details (AI extraction)
3. **📋 EXTRACTION METADATA** - Thông tin AI provider, template, etc.
4. **🔒 WEBHOOK SIGNATURES** - X-Webhook-Signature cho tất cả callbacks

**Không còn thiếu dữ liệu nào cho backend database storage!** 🎉

## 🔄 **Complete Workflow Summary**:

### File Upload Flow (Enhanced with RAW CONTENT):
```
File Upload → Extract RAW CONTENT → Callback with RAW CONTENT + FILE METADATA
                                        ↓
                                Backend stores file record + raw content
```

### AI Extraction Flow (Full Data):
```
AI Extraction → RAW CONTENT + STRUCTURED DATA → Callback with FULL DATA
                                                       ↓
                             Backend stores extraction job + products + services
```
```
POST /companies/{id}/files/upload 
→ Background worker processes file
→ Raw content extraction  
→ Qdrant storage
→ Callback: POST /api/webhooks/file-processed
```

### AI Extraction Flow:
```
POST /api/extract/process-async
→ Worker with AI templates
→ Structured data extraction (products/services)
→ Qdrant storage with optimization  
→ Callback: POST /api/webhooks/ai/extraction-callback
```

## 🧪 **Testing**:

Backend team có thể test webhooks với:
1. curl commands trong documentation
2. Monitor logs để verify callbacks được gửi
3. Check response status codes từ backend

## ✅ **Ready for Production**

Cả 2 callback workflows đã được implement đầy đủ và sẵn sàng cho backend integration.
