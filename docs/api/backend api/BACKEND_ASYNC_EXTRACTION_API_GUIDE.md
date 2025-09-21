# API Documentation: Async Document Extraction Workflow

## Overview
API hỗ trợ xử lý bất đồng bộ để extract dữ liệu từ documents bằng AI (Gemini), cho phép backend submit file và nhận kết quả thông qua callback mechanism.

**✅ IMPLEMENTED ENDPOINTS**:
- `POST /api/extract/process-async` - Submit extraction task
- `GET /api/extract/status/{task_id}` - Check task status
- `GET /api/extract/result/{task_id}` - Get extraction results
- Callback mechanism for real-time notifications

## Performance Metrics
- **Queue Submission**: ~0.03-0.04s (immediate response)
- **AI Processing**: ~18-22s (depends on file size and complexity)
- **Total Workflow**: ~22-25s (including Qdrant upload)

---

## 1. Submit Async Extraction Request

### Endpoint
```
POST /api/extract/process-async
```

### Headers
```json
{
  "Content-Type": "application/json"
}
```

### Request Body
```json
{
  "r2_url": "https://static.agent8x.io.vn/company/{company_id}/files/{filename}",
  "company_id": "your-company-id",
  "industry": "insurance",
  "data_type": "auto",
  "file_name": "document.txt",
  "file_size": 1024000,
  "file_type": "text/plain"
}
```

### Request Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `r2_url` | string | ✅ | Full URL to the file stored in R2 |
| `company_id` | string | ✅ | Unique company identifier |
| `industry` | string | ✅ | Industry type (`insurance`, `banking`, `retail`, etc.) |
| `data_type` | string | ✅ | Extraction type (`auto`, `products`, `services`) |
| `file_name` | string | ✅ | Original filename |
| `file_size` | integer | ✅ | File size in bytes |
| `file_type` | string | ✅ | MIME type |

### Response (Immediate - ~0.04s)
```json
{
  "success": true,
  "message": "Document queued for processing",
  "task_id": "extract_d4f2a891-c3b2-4e6f-8a9d-1b2c3d4e5f6g",
  "estimated_processing_time": "15-25 seconds",
  "status_check_url": "/api/extract/status/{task_id}",
  "queue_position": 1
}
```

### Error Response
```json
{
  "success": false,
  "error": "Invalid request parameters",
  "error_details": {
    "r2_url": "URL is required",
    "company_id": "Company ID is required"
  }
}
```

---

## 2. Check Processing Status

### Endpoint
```
GET /api/extract/status/{task_id}
```

### Response - Processing
```json
{
  "task_id": "extract_d4f2a891-c3b2-4e6f-8a9d-1b2c3d4e5f6g",
  "status": "processing",
  "progress": {
    "stage": "ai_extraction",
    "estimated_remaining": "12-18 seconds"
  },
  "submitted_at": "2025-07-26T15:18:07.159081Z"
}
```

### Response - Completed
```json
{
  "task_id": "extract_d4f2a891-c3b2-4e6f-8a9d-1b2c3d4e5f6g",
  "status": "completed",
  "processing_time": 19.83,
  "completed_at": "2025-07-26T15:18:27.159081Z",
  "result_available": true
}
```

---

## 3. Get Extraction Results

### Endpoint
```
GET /api/extract/result/{task_id}
```

### Full Response Structure
```json
{
  "success": true,
  "message": "Auto-categorization extraction completed successfully",
  "task_id": "extract_d4f2a891-c3b2-4e6f-8a9d-1b2c3d4e5f6g",
  "processing_time": 19.83,
  "total_items_extracted": 5,
  "ai_provider": "gemini",
  "template_used": "InsuranceExtractionTemplate",
  "industry": "insurance",
  "data_type": "auto",
  "raw_content": "--- DỊCH VỤ AIA VIỆT NAM... (full original text)",
  "structured_data": {
    "products": [
      {
        "name": "AIA – Khỏe Trọn Vẹn",
        "type": "Bảo hiểm liên kết chung",
        "description": "Bảo vệ tài chính trước rủi ro...",
        "coverage_period": "30 năm",
        "premium": "Tùy thuộc vào tuổi, giới tính...",
        "conditions": "Tùy sản phẩm, yêu cầu sức khỏe..."
      }
    ],
    "services": [
      {
        "name": "AIA Vitality",
        "type": "Chương trình ưu đãi",
        "description": "Chương trình AIA Vitality...",
        "pricing": "Tích hợp vào các sản phẩm bảo hiểm",
        "availability": "Áp dụng cho các sản phẩm bảo hiểm tương ứng"
      }
    ],
    "extraction_summary": {
      "total_products": 3,
      "total_services": 2,
      "data_quality": "high",
      "categorization_notes": "Categorization based on product descriptions...",
      "industry_context": "Insurance products and related services..."
    }
  },
  "extraction_metadata": {
    "r2_url": "https://static.agent8x.io.vn/company/.../files/SanPham-AIA.txt",
    "extraction_mode": "auto_categorization",
    "target_categories": ["products", "services"],
    "ai_provider": "gemini",
    "template_used": "InsuranceExtractionTemplate",
    "industry": "insurance",
    "company_name": null,
    "file_extension": ".txt",
    "extraction_timestamp": "2025-07-26T15:18:07.159081",
    "total_items": 5,
    "source": "r2_extraction_service_v2",
    "categorization_summary": {
      "products": 3,
      "services": 2
    }
  },
  "error": null,
  "error_details": null
}
```

---

## 4. Webhook Callback Structure (CHÍNH XÁC)

### File Upload Callback (Now includes RAW CONTENT)
**Endpoint Backend**: `/api/webhooks/file-uploaded`
**Headers từ AI Service**:
```javascript
{
    "Content-Type": "application/json",
    "X-Webhook-Source": "ai-service",
    "X-Webhook-Signature": "sha256=abc123...",
    "User-Agent": "Agent8x-AI-Service/1.0"
}
```

**ENHANCED FILE UPLOAD CALLBACK** (Bây giờ có RAW CONTENT):
```javascript
{
    "event": "file.uploaded",
    "companyId": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
    "data": {
        "fileId": "file_1753617620355_de12d50e",
        "status": "completed",
        "chunksCreated": 3,
        "processingTime": 5.23,
        "processedAt": "2025-07-27T12:00:38.751498",
        "tags": ["company-info", "profile", "overview"],

        // ✅ RAW CONTENT (Full original file content for database storage)
        "raw_content": "CÔNG TY CỔ PHẦN BẢO HIỂM AIA VIỆT NAM\n\nThông tin công ty:\nAIA Việt Nam được thành lập từ năm 2000...\n\nCác sản phẩm chính:\n1. Bảo hiểm nhân thọ\n2. Bảo hiểm sức khỏe\n3. Bảo hiểm liên kết chung...",

        // ✅ Complete file metadata for reference
        "file_metadata": {
            "original_name": "AIA_company_profile.pdf",
            "file_name": "AIA_company_profile_processed.pdf",
            "file_size": 2048000,
            "file_type": "application/pdf",
            "uploaded_by": "user_uid_123",
            "description": "Company profile and information document",
            "r2_url": "https://static.agent8x.io.vn/company/9a974d00-1a4b-4d5d-8dc3-4b5058255b8f/files/AIA_company_profile.pdf"
        }
    },
    "timestamp": "2025-07-27T12:00:38.751498"
}
```

### AI Extraction Callback (Full Data)
**Endpoint Backend**: `/api/webhooks/ai/extraction-callback`
**Headers từ AI Service**:
```javascript
{
    "Content-Type": "application/json",
    "X-Webhook-Source": "ai-service",
    "X-Webhook-Signature": "sha256=abc123...",
    "User-Agent": "Agent8x-AI-Service/1.0"
}
```

### **FULL CALLBACK PAYLOAD** (Chứa tất cả dữ liệu để lưu database)
```javascript
{
    // Basic task information
    "task_id": "extract_1753617620355_de12d50e",
    "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
    "status": "completed",
    "processing_time": 16.318650007247925,
    "timestamp": "2025-07-27T12:00:38.751498",

    // Summary results for quick overview
    "results": {
        "products_count": 3,
        "services_count": 0,
        "total_items": 3,
        "ai_provider": "gemini",
        "template_used": "InsuranceExtractionTemplate"
    },

    // 📄 FULL RAW CONTENT (Original text from file)
    "raw_content": "--- DỊCH VỤ AIA VIỆT NAM ---\n\nCông ty AIA Việt Nam cung cấp các sản phẩm bảo hiểm...\n\n1. AIA – Khỏe Trọn Vẹn\nĐây là sản phẩm bảo hiểm liên kết chung...",

    // 📦 FULL STRUCTURED DATA (Products & Services cho database) - ✅ CẬP NHẬT BƯỚC 2
    "structured_data": {
        "products": [
            {
                // ✅ NEW STEP 2: AI Service tự generate product_id duy nhất
                "product_id": "prod_9c96ef4a-af0f-4974-b151-93ca5c1d94eb",
                "name": "AIA – Khỏe Trọn Vẹn",
                "type": "Bảo hiểm liên kết chung",
                "description": "Bảo vệ tài chính trước rủi ro bệnh tật, thương tật và tử vong, đồng thời tích lũy tài chính cho tương lai",
                "coverage_period": "30 năm",
                "age_range": "18-60 tuổi",
                "premium": "Tùy thuộc vào tuổi, giới tính và mức bảo hiểm",
                "conditions": "Tùy sản phẩm, yêu cầu sức khỏe và điều kiện cụ thể",

                // ✅ NEW: Trường retrieval_context cho RAG optimization
                "retrieval_context": "AIA – Khỏe Trọn Vẹn là bảo hiểm liên kết chung bảo vệ tài chính trước rủi ro bệnh tật, thương tật và tử vong, đồng thời tích lũy tài chính cho tương lai. Thời gian bảo hiểm 30 năm, độ tuổi tham gia 18-60 tuổi. Phí bảo hiểm tùy thuộc vào tuổi, giới tính và mức bảo hiểm.",

                // ✅ NEW STEP 2: Clean data từ AI Service catalog
                "catalog_price": 1500000.0,
                "catalog_quantity": 50,
                // Backend tracking fields
                "qdrant_point_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
            },
            {
                // ✅ NEW STEP 2: AI Service tự generate product_id duy nhất
                "product_id": "prod_dc5b9197-9d52-4750-9694-de853532a20b",
                "name": "AIA – An Gia Phú Quý",
                "type": "Bảo hiểm nhân thọ truyền thống",
                "description": "Bảo vệ tài chính gia đình với quyền lợi tử vong và thương tật toàn bộ vĩnh viễn",
                "coverage_period": "Đến 99 tuổi",
                "age_range": "30 ngày - 65 tuổi",
                "premium": "Phí cố định hàng năm",
                "conditions": "Khám sức khỏe và khai báo y tế",

                // ✅ NEW: Trường retrieval_context cho RAG optimization
                "retrieval_context": "AIA – An Gia Phú Quý là bảo hiểm nhân thọ truyền thống bảo vệ tài chính gia đình với quyền lợi tử vong và thương tật toàn bộ vĩnh viễn. Thời gian bảo hiểm đến 99 tuổi, độ tuổi tham gia từ 30 ngày - 65 tuổi. Phí cố định hàng năm, yêu cầu khám sức khỏe và khai báo y tế.",

                // ✅ NEW STEP 2: Clean data từ AI Service catalog
                "catalog_price": 2800000.0,
                "catalog_quantity": 25,
                // Backend tracking fields
                "qdrant_point_id": "b2c3d4e5-f6g7-8901-bcde-f23456789012"
            }
        ],
        "services": [
            {
                // ✅ NEW STEP 2: AI Service tự generate service_id duy nhất
                "service_id": "serv_aba78752-c1d2-437b-aeb9-5df058972b7e",
                "name": "AIA Vitality",
                "type": "Chương trình ưu đãi sức khỏe",
                "description": "Chương trình khuyến khích lối sống lành mạnh với nhiều ưu đãi và phần thưởng",
                "pricing": "Tích hợp vào các sản phẩm bảo hiểm",
                "availability": "Áp dụng cho khách hàng có sản phẩm bảo hiểm tương ứng",

                // ✅ NEW: Trường retrieval_context cho RAG optimization
                "retrieval_context": "AIA Vitality là chương trình ưu đãi sức khỏe khuyến khích lối sống lành mạnh với nhiều ưu đãi và phần thưởng. Được tích hợp vào các sản phẩm bảo hiểm và áp dụng cho khách hàng có sản phẩm bảo hiểm tương ứng.",

                // ✅ NEW STEP 2: Clean data từ AI Service catalog
                "catalog_price": 500000.0,
                "catalog_quantity": -1,  // Service không track quantity
                // Backend tracking fields
                "qdrant_point_id": "c3d4e5f6-g7h8-9012-cdef-345678901234"
            }
        ],
        "extraction_summary": {
            "total_products": 2,
            "total_services": 1,
            "data_quality": "high",
            "categorization_notes": "Extracted 2 products and 1 services using InsuranceExtractionTemplate template",
            "industry_context": "insurance industry extraction",
            // ✅ NEW STEP 2: AI Service metadata
            "internal_catalog_updates": {
                "products_registered": 2,
                "services_registered": 1,
                "catalog_service_version": "1.0.0"
            }
        }
    },

    // 📋 Full extraction metadata for reference
    "extraction_metadata": {
        "r2_url": "https://static.agent8x.io.vn/company/9a974d00-1a4b-4d5d-8dc3-4b5058255b8f/files/SanPham-AIA.txt",
        "extraction_mode": "auto_categorization",
        "target_categories": ["products", "services"],
        "ai_provider": "gemini",
        "template_used": "InsuranceExtractionTemplate",
        "industry": "insurance",
        "data_type": "auto",
        "file_name": "SanPham-AIA.txt",
        "file_size": 15420,
        "file_type": "text/plain",
        "language": "vi",
        "extraction_timestamp": "2025-07-27T12:00:38.751498",
        "total_items": 4,
        "source": "ai_extraction_service_v2"
    }
}
```

### **Backend Implementation cho File Upload Callback**

```javascript
// /api/webhooks/file-uploaded
app.post('/api/webhooks/file-uploaded', webhookAuth, async (req, res) => {
    const {
        event,
        companyId,
        data: {
            fileId,
            status,
            chunksCreated,
            processingTime,
            processedAt,
            tags,
            raw_content,
            file_metadata
        }
    } = req.body;

    try {
        // 1. Store file upload record in database
        const fileRecord = await db.uploaded_files.create({
            file_id: fileId,
            company_id: companyId,
            original_name: file_metadata.original_name,
            file_name: file_metadata.file_name,
            file_size: file_metadata.file_size,
            file_type: file_metadata.file_type,
            uploaded_by: file_metadata.uploaded_by,
            description: file_metadata.description,
            r2_url: file_metadata.r2_url,
            raw_content: raw_content,  // Store complete file content
            tags: JSON.stringify(tags),
            chunks_created: chunksCreated,
            processing_time: processingTime,
            processed_at: new Date(processedAt),
            status: status,
            created_at: new Date()
        });

        // 2. Update company file count
        await db.companies.update(
            { id: companyId },
            {
                total_files: db.sequelize.literal('total_files + 1'),
                last_file_uploaded: new Date()
            }
        );

        // 3. Index tags for search
        if (tags && tags.length > 0) {
            for (const tag of tags) {
                await db.file_tags.upsert({
                    company_id: companyId,
                    tag_name: tag,
                    file_count: db.sequelize.literal('file_count + 1'),
                    updated_at: new Date()
                });
            }
        }

        // 4. Log successful processing
        console.log(`✅ File upload completed for ${fileId}`);
        console.log(`   📄 Original name: ${file_metadata.original_name}`);
        console.log(`   📦 Chunks created: ${chunksCreated}`);
        console.log(`   📄 Raw content: ${raw_content ? raw_content.length : 0} characters`);
        console.log(`   🏷️ Tags: ${tags ? tags.join(', ') : 'none'}`);
        console.log(`   ⏱️ Processing time: ${processingTime}s`);

        // 5. Return success response
        res.json({
            success: true,
            message: "File upload record saved successfully",
            file_record: {
                id: fileRecord.id,
                file_id: fileId,
                chunks_created: chunksCreated,
                raw_content_length: raw_content ? raw_content.length : 0
            }
        });

    } catch (error) {
        console.error(`❌ Failed to save file upload record for ${fileId}:`, error);
        res.status(500).json({
            success: false,
            error: "Failed to save file upload record",
            details: error.message
        });
    }
});
```

### **Backend Implementation cho Extraction Callback**

```javascript
// /api/webhooks/ai/extraction-callback
app.post('/api/webhooks/ai/extraction-callback', webhookAuth, async (req, res) => {
    const {
        task_id,
        company_id,
        status,
        processing_time,
        raw_content,
        structured_data,
        extraction_metadata,
        results
    } = req.body;

    try {
        // 1. Update extraction job status
        await db.extraction_jobs.update(
            { task_id: task_id },
            {
                status: status,
                completed_at: new Date(),
                processing_time: processing_time,
                ai_provider: results.ai_provider,
                template_used: results.template_used,
                total_items_extracted: results.total_items,
                raw_content: raw_content, // Store full original content
                extraction_metadata: JSON.stringify(extraction_metadata)
            }
        );

        const job = await db.extraction_jobs.findOne({ task_id: task_id });

        // 2. Save extracted PRODUCTS to database - ✅ CẬP NHẬT BƯỚC 2
        if (structured_data.products && structured_data.products.length > 0) {
            for (const product of structured_data.products) {
                await db.extracted_products.create({
                    job_id: job.id,
                    company_id: company_id,
                    // ✅ NEW STEP 2: AI Service provided product_id
                    product_id: product.product_id,  // UUID từ AI Service
                    qdrant_point_id: product.qdrant_point_id,  // Vector search ID
                    name: product.name,
                    type: product.type,
                    description: product.description,
                    coverage_period: product.coverage_period,
                    age_range: product.age_range,
                    premium: product.premium,
                    conditions: product.conditions,

                    // ✅ NEW: Trường retrieval_context cho RAG optimization
                    retrieval_context: product.retrieval_context,

                    // ✅ NEW STEP 2: Clean catalog data từ AI Service
                    catalog_price: product.catalog_price,
                    catalog_quantity: product.catalog_quantity,
                    created_at: new Date()
                });
            }
            console.log(`✅ Saved ${structured_data.products.length} products to database`);
            console.log(`   🔗 All products have AI Service product_id for sync`);
        }

        // 3. Save extracted SERVICES to database - ✅ CẬP NHẬT BƯỚC 2
        if (structured_data.services && structured_data.services.length > 0) {
            for (const service of structured_data.services) {
                await db.extracted_services.create({
                    job_id: job.id,
                    company_id: company_id,
                    // ✅ NEW STEP 2: AI Service provided service_id
                    service_id: service.service_id,  // UUID từ AI Service
                    qdrant_point_id: service.qdrant_point_id,  // Vector search ID
                    name: service.name,
                    type: service.type,
                    description: service.description,
                    pricing: service.pricing,
                    availability: service.availability,

                    // ✅ NEW: Trường retrieval_context cho RAG optimization
                    retrieval_context: service.retrieval_context,

                    // ✅ NEW STEP 2: Clean catalog data từ AI Service
                    catalog_price: service.catalog_price,
                    catalog_quantity: service.catalog_quantity,
                    created_at: new Date()
                });
            }
            console.log(`✅ Saved ${structured_data.services.length} services to database`);
            console.log(`   🔗 All services have AI Service service_id for sync`);
        }

        // 4. Log successful processing
        console.log(`🎉 Extraction completed for task ${task_id}`);
        console.log(`   📦 Products: ${results.products_count}`);
        console.log(`   🔧 Services: ${results.services_count}`);
        console.log(`   📄 Raw content: ${raw_content ? raw_content.length : 0} characters`);
        console.log(`   ⏱️ Processing time: ${processing_time}s`);

        // 5. Return success response
        res.json({
            success: true,
            message: "Extraction results saved successfully",
            saved_items: {
                products: structured_data.products ? structured_data.products.length : 0,
                services: structured_data.services ? structured_data.services.length : 0,
                total: results.total_items
            }
        });

    } catch (error) {
        console.error(`❌ Failed to save extraction results for ${task_id}:`, error);
        res.status(500).json({
            success: false,
            error: "Failed to save extraction results",
            details: error.message
        });
    }
});
```

### **Database Schema Update - ✅ CẬP NHẬT BƯỚC 2**

```sql
-- Add raw_content column to store original file content
ALTER TABLE extraction_jobs
ADD COLUMN raw_content TEXT,
ADD COLUMN extraction_metadata JSONB;

-- ✅ NEW STEP 2: Add AI Service sync fields to product table
ALTER TABLE extracted_products
ADD COLUMN company_id VARCHAR(255),
ADD COLUMN product_id VARCHAR(255) UNIQUE,  -- AI Service generated UUID
ADD COLUMN qdrant_point_id VARCHAR(255),    -- Vector search reference
ADD COLUMN catalog_price DECIMAL(12,2),     -- Clean price từ AI Service
ADD COLUMN catalog_quantity INTEGER,        -- Inventory count
ADD COLUMN retrieval_context TEXT;          -- ✅ NEW: RAG optimized context

-- ✅ NEW STEP 2: Add AI Service sync fields to service table
ALTER TABLE extracted_services
ADD COLUMN company_id VARCHAR(255),
ADD COLUMN service_id VARCHAR(255) UNIQUE,  -- AI Service generated UUID
ADD COLUMN qdrant_point_id VARCHAR(255),    -- Vector search reference
ADD COLUMN catalog_price DECIMAL(12,2),     -- Clean price từ AI Service
ADD COLUMN catalog_quantity INTEGER,        -- Availability count (-1 = không track)
ADD COLUMN retrieval_context TEXT;          -- ✅ NEW: RAG optimized context

-- Add indexes for better performance
CREATE INDEX idx_extraction_jobs_company_id ON extraction_jobs(company_id);
CREATE INDEX idx_extracted_products_company_id ON extracted_products(company_id);
CREATE INDEX idx_extracted_services_company_id ON extracted_services(company_id);

-- ✅ NEW STEP 2: Add indexes for AI Service sync
CREATE INDEX idx_extracted_products_product_id ON extracted_products(product_id);
CREATE INDEX idx_extracted_services_service_id ON extracted_services(service_id);
CREATE INDEX idx_extracted_products_qdrant_id ON extracted_products(qdrant_point_id);
CREATE INDEX idx_extracted_services_qdrant_id ON extracted_services(qdrant_point_id);
```

---

## Backend Integration Guide

### 1. Database Schema Recommendations

#### uploaded_files table (for file upload callbacks)
```sql
CREATE TABLE uploaded_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id VARCHAR(255) UNIQUE NOT NULL,
    company_id VARCHAR(255) NOT NULL,
    original_name VARCHAR(500) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    file_type VARCHAR(100) NOT NULL,
    uploaded_by VARCHAR(255),
    description TEXT,
    r2_url TEXT NOT NULL,
    raw_content TEXT,
    tags JSONB,
    chunks_created INTEGER DEFAULT 0,
    processing_time DECIMAL(10,3),
    processed_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'uploaded',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### extraction_jobs table (for AI extraction callbacks)
```sql
CREATE TABLE extraction_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(255) UNIQUE NOT NULL,
    company_id VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    r2_url TEXT NOT NULL,
    industry VARCHAR(100) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'queued',
    submitted_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP NULL,
    processing_time DECIMAL(10,3) NULL,
    ai_provider VARCHAR(50) NULL,
    template_used VARCHAR(100) NULL,
    total_items_extracted INTEGER NULL,
    raw_content TEXT,
    extraction_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### file_tags table (for tag indexing)
```sql
CREATE TABLE file_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id VARCHAR(255) NOT NULL,
    tag_name VARCHAR(100) NOT NULL,
    file_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, tag_name)
);
```

#### extracted_products table (for AI extraction results)
```sql
CREATE TABLE extracted_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES extraction_jobs(id),
    company_id VARCHAR(255),
    -- ✅ NEW: AI Service sync fields
    product_id VARCHAR(255) UNIQUE,     -- AI Service generated UUID
    qdrant_point_id VARCHAR(255),       -- Vector search reference
    -- Product information
    name VARCHAR(500) NOT NULL,
    type VARCHAR(200),
    description TEXT,
    coverage_period VARCHAR(100),
    age_range VARCHAR(100),
    premium TEXT,
    conditions TEXT,
    -- ✅ NEW: RAG optimization field
    retrieval_context TEXT,             -- Optimized context for AI chat responses
    -- Catalog integration
    catalog_price DECIMAL(12,2),        -- Clean price từ AI Service
    catalog_quantity INTEGER,           -- Inventory count
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### extracted_services table
```sql
CREATE TABLE extracted_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES extraction_jobs(id),
    company_id VARCHAR(255),
    -- ✅ NEW: AI Service sync fields
    service_id VARCHAR(255) UNIQUE,     -- AI Service generated UUID
    qdrant_point_id VARCHAR(255),       -- Vector search reference
    -- Service information
    name VARCHAR(500) NOT NULL,
    type VARCHAR(200),
    description TEXT,
    pricing TEXT,
    availability VARCHAR(200),
    -- ✅ NEW: RAG optimization field
    retrieval_context TEXT,             -- Optimized context for AI chat responses
    -- Catalog integration
    catalog_price DECIMAL(12,2),        -- Clean price từ AI Service
    catalog_quantity INTEGER,           -- Availability count (-1 = không track)
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2. Implementation Workflow

#### Step 1: Submit and Store
```python
async def submit_extraction(file_data):
    # Submit to AI service
    response = await http_client.post("/api/extract/process-async", json=file_data)
    task_data = response.json()

    # Store immediately in database
    job = await db.extraction_jobs.create({
        "task_id": task_data["task_id"],
        "company_id": file_data["company_id"],
        "file_name": file_data["file_name"],
        "r2_url": file_data["r2_url"],
        "industry": file_data["industry"],
        "data_type": file_data["data_type"],
        "status": "queued"
    })

    return {"job_id": job.id, "task_id": task_data["task_id"]}
```

#### Step 2: Monitor Processing
```python
async def monitor_extraction(task_id):
    while True:
        status = await http_client.get(f"/api/extract/status/{task_id}")

        if status["status"] == "completed":
            # Get results and store
            results = await http_client.get(f"/api/extract/result/{task_id}")
            await store_extraction_results(task_id, results)
            break
        elif status["status"] == "failed":
            await handle_extraction_failure(task_id, status)
            break

        await asyncio.sleep(2)  # Check every 2 seconds
```

#### Step 3: Store Results
```python
async def store_extraction_results(task_id, results):
    # Update job status
    await db.extraction_jobs.update(
        {"task_id": task_id},
        {
            "status": "completed",
            "completed_at": datetime.now(),
            "processing_time": results["processing_time"],
            "ai_provider": results["ai_provider"],
            "template_used": results["template_used"],
            "total_items_extracted": results["total_items"]
        }
    )

    job = await db.extraction_jobs.get({"task_id": task_id})

    # Store products
    if "products" in results["structured_data"]:
        for product in results["structured_data"]["products"]:
            await db.extracted_products.create({
                "job_id": job.id,
                "company_id": job.company_id,
                "name": product["name"],
                "type": product.get("type"),
                "description": product.get("description"),
                "premium": product.get("premium"),
                "conditions": product.get("conditions")
            })

    # Store services
    if "services" in results["structured_data"]:
        for service in results["structured_data"]["services"]:
            await db.extracted_services.create({
                "job_id": job.id,
                "company_id": job.company_id,
                "name": service["name"],
                "type": service.get("type"),
                "description": service.get("description"),
                "pricing": service.get("pricing"),
                "availability": service.get("availability")
            })
```

### 3. Polling Strategy

#### Recommended Polling Implementation
```python
class ExtractionMonitor:
    def __init__(self, http_client, db):
        self.http_client = http_client
        self.db = db

    async def start_monitoring(self, task_id):
        """Start monitoring with exponential backoff"""
        max_wait = 60  # seconds
        check_interval = 2  # start with 2 seconds
        total_waited = 0

        while total_waited < max_wait:
            try:
                status = await self.http_client.get(f"/api/extract/status/{task_id}")

                if status["status"] == "completed":
                    await self._handle_completion(task_id)
                    return True
                elif status["status"] == "failed":
                    await self._handle_failure(task_id, status)
                    return False

                await asyncio.sleep(check_interval)
                total_waited += check_interval

                # Exponential backoff (2s -> 3s -> 5s -> 5s...)
                check_interval = min(check_interval * 1.5, 5)

            except Exception as e:
                logger.error(f"Monitoring error for {task_id}: {e}")
                await asyncio.sleep(5)

        # Timeout handling
        await self._handle_timeout(task_id)
        return False
```

### 4. Error Handling

#### Common Error Scenarios
```python
async def handle_extraction_errors(task_id, error_response):
    error_mapping = {
        "file_not_found": "File không tồn tại hoặc đã bị xóa",
        "unsupported_format": "Định dạng file không được hỗ trợ",
        "ai_service_error": "Lỗi dịch vụ AI, thử lại sau",
        "timeout": "Xử lý quá thời gian cho phép",
        "invalid_content": "Nội dung file không hợp lệ"
    }

    await db.extraction_jobs.update(
        {"task_id": task_id},
        {
            "status": "failed",
            "error_message": error_mapping.get(
                error_response.get("error_code"),
                "Lỗi không xác định"
            ),
            "completed_at": datetime.now()
        }
    )
```

### 5. Performance Optimization

#### Batch Processing
```python
async def process_multiple_files(file_list):
    """Process multiple files efficiently"""
    tasks = []

    for file_data in file_list:
        task = submit_extraction(file_data)
        tasks.append(task)

    # Submit all files first (fast)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Then monitor all in parallel
    task_ids = [r["task_id"] for r in results if not isinstance(r, Exception)]

    monitor_tasks = [
        monitor_extraction(task_id)
        for task_id in task_ids
    ]

    await asyncio.gather(*monitor_tasks, return_exceptions=True)
```

---

## ✅ BƯỚC 2: ENHANCED PRODUCT/SERVICE ID INTEGRATION

### **🔑 Key Features Added (Aug 2025)**

1. **Product ID Auto-Generation**: AI Service tự tạo `product_id` và `service_id` duy nhất
2. **Internal Catalog Management**: AI Service lưu trữ catalog nội bộ với 4 trường sạch
3. **Real-time Synchronization**: Backend nhận full data với IDs để đồng bộ
4. **Enhanced Webhook Data**: Callback payload bao gồm catalog metadata

### **🎯 Benefits cho Backend**

| Before Step 2 | After Step 2 |
|----------------|--------------|
| ❌ No product_id/service_id | ✅ Real UUID generated by AI Service |
| ❌ Only raw AI data | ✅ Clean catalog data (price, quantity) |
| ❌ No inventory integration | ✅ Real-time inventory sync possible |
| ❌ Callback missing IDs | ✅ Full webhook data with tracking IDs |

### **🔗 Synchronization Use Cases**

#### 1. **Product Lookup by AI Service ID**
```javascript
// Backend có thể tra cứu product bằng AI Service ID
const product = await db.extracted_products.findOne({
    product_id: "prod_9c96ef4a-af0f-4974-b151-93ca5c1d94eb"
});

console.log(`Found product: ${product.name}`);
console.log(`AI Service price: ${product.catalog_price}`);
console.log(`AI Service quantity: ${product.catalog_quantity}`);
```

#### 2. **Cross-Reference với Chat System**
```javascript
// AI Chat System gửi webhook với product_id từ catalog
// Backend có thể update inventory chính xác
app.post('/api/webhooks/ai/check-quantity', async (req, res) => {
    const { product_id, requested_quantity } = req.body;

    // Tìm product bằng AI Service ID
    const product = await db.extracted_products.findOne({
        product_id: product_id
    });

    if (product) {
        // Update quantity based on real data
        const available_quantity = await checkRealInventory(product.id);

        // Send response back to AI Service
        res.json({
            product_id: product_id,
            current_quantity: available_quantity,
            can_fulfill: available_quantity >= requested_quantity
        });
    }
});
```

#### 3. **Qdrant Vector Reference**
```javascript
// Backend có thể xóa/update vectors bằng qdrant_point_id
const deleteProductFromSearch = async (product_id) => {
    const product = await db.extracted_products.findOne({ product_id });

    // Call AI Service để xóa vector
    await fetch(`${AI_SERVICE_URL}/api/qdrant/delete/${product.qdrant_point_id}`, {
        method: 'DELETE'
    });

    // Xóa khỏi database
    await db.extracted_products.destroy({ where: { product_id } });
};
```

### **📊 Enhanced Callback Data Structure**

#### Key Fields Backend Should Track:

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `product_id` | UUID | AI Service unique identifier | `prod_9c96ef4a...` |
| `service_id` | UUID | AI Service unique identifier | `serv_aba78752...` |
| `qdrant_point_id` | UUID | Vector search reference | `a1b2c3d4-e5f6...` |
| `catalog_price` | Decimal | Clean price từ AI extraction | `1500000.0` |
| `catalog_quantity` | Integer | Inventory count (-1 for services) | `50` |
| `retrieval_context` | Text | **✅ NEW**: RAG-optimized context | `"AIA – Khỏe Trọn Vẹn là bảo hiểm liên kết chung..."` |

#### **🔍 Chi tiết về trường `retrieval_context`**

**Mục đích**: Trường này được AI tạo ra đặc biệt cho hệ thống RAG (Retrieval-Augmented Generation) để tối ưu hóa các cuộc trò chuyện với khách hàng.

**Cấu trúc**:
- **Products**: "Tên sản phẩm + mô tả ngắn gọn + thông tin giá + điều kiện chính"
- **Services**: "Tên dịch vụ + mô tả lợi ích + thông tin giá + điều kiện áp dụng"

**Ví dụ thực tế**:

```json
{
  "product_id": "prod_9c96ef4a-af0f-4974-b151-93ca5c1d94eb",
  "name": "AIA – Khỏe Trọn Vẹn",
  "retrieval_context": "AIA – Khỏe Trọn Vẹn là bảo hiểm liên kết chung bảo vệ tài chính trước rủi ro bệnh tật, thương tật và tử vong, đồng thời tích lũy tài chính cho tương lai. Thời gian bảo hiểm 30 năm, độ tuổi tham gia 18-60 tuổi. Phí bảo hiểm tùy thuộc vào tuổi, giới tính và mức bảo hiểm."
}
```

**Lợi ích cho Backend**:
- 📄 **Content Ready**: Sẵn sàng hiển thị cho khách hàng không cần xử lý thêm
- 🤖 **AI-Optimized**: Được tạo ra bởi AI để phù hợp với ngữ cảnh trò chuyện
- 🔍 **Search Friendly**: Tối ưu cho việc tìm kiếm và gợi ý sản phẩm
- 📱 **Mobile Friendly**: Văn bản ngắn gọn, dễ đọc trên mobile

**Sử dụng trong Backend**:
```javascript
// Hiển thị thông tin sản phẩm cho khách hàng
const displayProductInfo = (product) => {
  return {
    id: product.product_id,
    name: product.name,
    price: product.catalog_price,
    summary: product.retrieval_context,  // ✅ Sẵn sàng hiển thị
    quantity: product.catalog_quantity
  };
};

// Tìm kiếm sản phẩm với AI context
const searchProducts = async (query) => {
  return await db.extracted_products.findAll({
    where: {
      [Op.or]: [
        { name: { [Op.iLike]: `%${query}%` } },
        { retrieval_context: { [Op.iLike]: `%${query}%` } }  // ✅ Search trong context
      ]
    }
  });
};
```

#### Internal Catalog Updates:
```javascript
// AI Service sẽ gửi thêm metadata về catalog updates
"extraction_summary": {
    "internal_catalog_updates": {
        "products_registered": 2,
        "services_registered": 1,
        "catalog_service_version": "1.0.0"
    }
}
```

### **⚙️ Implementation Notes cho Backend**

1. **Database Migration**: Chạy SQL schema updates trước khi deploy
2. **Index Performance**: Các index mới sẽ tăng tốc lookup by product_id/service_id
3. **Webhook Validation**: Validate product_id format (`prod_` hoặc `serv_` prefix)
4. **Error Handling**: Handle case khi AI Service không thể generate ID (fallback)

---

## 📋 PAYLOAD STRUCTURE SUMMARY - Trường retrieval_context mới

### **🔄 Comparison: Before vs After**

#### **Before (Old Structure)**
```json
{
  "structured_data": {
    "products": [{
      "name": "AIA – Khỏe Trọn Vẹn",
      "type": "Bảo hiểm liên kết chung",
      "description": "Bảo vệ tài chính trước rủi ro bệnh tật...",
      "coverage_period": "30 năm",
      "age_range": "18-60 tuổi"
      // Thiếu retrieval_context - AI phải tự ghép nối từ nhiều trường
    }]
  }
}
```

#### **After (New Structure với retrieval_context)**
```json
{
  "structured_data": {
    "products": [{
      "product_id": "prod_9c96ef4a-af0f-4974-b151-93ca5c1d94eb",
      "name": "AIA – Khỏe Trọn Vẹn",
      "type": "Bảo hiểm liên kết chung",
      "description": "Bảo vệ tài chính trước rủi ro bệnh tật...",
      "coverage_period": "30 năm",
      "age_range": "18-60 tuổi",

      "retrieval_context": "AIA – Khỏe Trọn Vẹn là bảo hiểm liên kết chung bảo vệ tài chính trước rủi ro bệnh tật, thương tật và tử vong, đồng thời tích lũy tài chính cho tương lai. Thời gian bảo hiểm 30 năm, độ tuổi tham gia 18-60 tuổi. Phí bảo hiểm tùy thuộc vào tuổi, giới tính và mức bảo hiểm.",

      "catalog_price": 1500000.0,
      "catalog_quantity": 50,
      "qdrant_point_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    }]
  }
}
```

### **💡 Key Benefits của retrieval_context**

| Aspect | Before | After |
|--------|--------|-------|
| **AI Response Quality** | Phải ghép từ nhiều fields | ✅ Context sẵn sàng, chất lượng cao |
| **Database Storage** | Lưu riêng rẻ nhiều trường | ✅ Một trường tối ưu cho RAG |
| **Search Performance** | Query nhiều columns | ✅ Search trong 1 trường đã tối ưu |
| **Mobile Display** | Text dài, phức tạp | ✅ Ngắn gọn, dễ đọc |
| **Maintenance** | Update nhiều fields | ✅ Chỉ cần update 1 field |

### **🎯 Implementation Checklist cho Backend**

- [ ] **Database Schema**: Thêm column `retrieval_context TEXT` vào `extracted_products` và `extracted_services`
- [ ] **Webhook Handler**: Update callback handler để lưu trường `retrieval_context`
- [ ] **API Response**: Include `retrieval_context` trong product/service API responses
- [ ] **Search Function**: Sử dụng `retrieval_context` cho tìm kiếm sản phẩm
- [ ] **Display Logic**: Sử dụng `retrieval_context` cho hiển thị thông tin nhanh
- [ ] **Mobile Optimization**: Leverage ngắn gọn của `retrieval_context` cho mobile UI

### **📱 Frontend Usage Examples**

```javascript
// Product Card Component
const ProductCard = ({ product }) => (
  <div className="product-card">
    <h3>{product.name}</h3>
    <p className="product-summary">
      {product.retrieval_context}  {/* ✅ Perfect for quick display */}
    </p>
    <span className="price">{product.catalog_price.toLocaleString()} VNĐ</span>
  </div>
);

// Search Results
const SearchResults = ({ results }) => (
  <div>
    {results.map(item => (
      <div key={item.product_id} className="search-result">
        <strong>{item.name}</strong>
        <p>{item.retrieval_context}</p>  {/* ✅ No need to concat fields */}
      </div>
    ))}
  </div>
);
```

---

## Testing và Validation

### Test Script Usage
```bash
# Run comprehensive test
python test_realtime_async.py

# Results saved to: async_workflow_complete_test_YYYYMMDD_HHMMSS.json
```

### Expected Performance
- ✅ Queue submission: < 0.1s
- ✅ AI processing: 15-25s (typical file)
- ✅ Total workflow: < 30s
- ✅ Success rate: > 95%

### Monitoring Recommendations
1. **Queue Length**: Monitor Redis queue length
2. **Processing Time**: Track average processing time
3. **Error Rate**: Monitor failed extractions
4. **Resource Usage**: CPU/Memory during AI processing

---

## Contact & Support

Để hỗ trợ implementation hoặc troubleshooting, kiểm tra logs tại:
- Application logs: `/logs/`
- Worker logs: Worker processing details
- Redis monitoring: Queue status và task progress
