# Callback Webhook Integration Guide
# Hướng dẫn Tích hợp Callback Webhook

Tài liệu này mô tả chi tiết 2 loại callback webhooks khác nhau và cách backend cần implement để nhận notifications.

## 📋 Tổng quan Callback Webhooks

Hệ thống có **2 loại callback webhook chính** tương ứng với 2 workflows khác nhau:

### 1. **File Upload Callback** (Raw Content Processing)
- **Endpoint Pattern**: `/api/webhooks/file-processed`
- **Workflow**: File upload → Raw content extraction → Qdrant storage
- **API**: `POST /companies/{companyId}/files/upload`

### 2. **AI Extraction Callback** (Structured Data Processing)  
- **Endpoint Pattern**: `/api/webhooks/ai/extraction-callback`
- **Workflow**: File → AI template extraction → Structured data → Qdrant storage
- **API**: `POST /api/extract/process-async`

---

## 🔄 Workflow 1: File Upload Callback

### Backend Request Example:
```bash
POST /companies/company-123/files/upload
Content-Type: application/json

{
  "r2_url": "https://pub-xyz.r2.dev/companies/company-123/documents/file.pdf",
  "data_type": "document", 
  "industry": "REAL_ESTATE",
  "language": "VIETNAMESE",
  "metadata": {
    "original_name": "company_profile.pdf",
    "file_id": "file_123456789",
    "file_size": 1024000,
    "file_type": "application/pdf",
    "uploaded_by": "user_uid_123"
  },
  "upload_to_qdrant": true,
  "callback_url": "https://api.agent8x.io.vn/api/webhooks/file-processed"
}
```

### Expected Callback (Success):
```bash
POST https://api.agent8x.io.vn/api/webhooks/file-processed
Content-Type: application/json
X-Webhook-Source: ai-service
X-Webhook-Signature: sha256=abc123...
User-Agent: Agent8x-AI-Service/1.0

{
  "event": "file.uploaded",
  "companyId": "company-123", 
  "data": {
    "fileId": "file_123456789",
    "status": "completed",
    "chunksCreated": 8,
    "processingTime": 5.23,
    "processedAt": "2025-07-27T07:30:00.123Z",
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
      "r2_url": "https://static.agent8x.io.vn/company/company-123/files/AIA_company_profile.pdf"
    }
  },
  "timestamp": "2025-07-27T07:30:00.123Z"
}
```

### Expected Callback (Error):
```bash
POST https://api.agent8x.io.vn/api/webhooks/file-processed
Content-Type: application/json

{
  "event": "file.uploaded",
  "companyId": "company-123",
  "data": {
    "fileId": "file_123456789", 
    "status": "failed",
    "error": "AI extraction failed: Invalid file format",
    "failedAt": "2025-07-27T07:30:00.123Z"
  },
  "timestamp": "2025-07-27T07:30:00.123Z"
}
```

---

## 🎯 Workflow 2: AI Extraction Callback

### Backend Request Example:
```bash
POST /api/extract/process-async
Content-Type: application/json

{
  "r2_url": "https://pub-xyz.r2.dev/companies/aia/documents/insurance_products.pdf",
  "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
  "industry": "INSURANCE",
  "file_name": "insurance_products.pdf",
  "file_size": 2048000,
  "file_type": "application/pdf", 
  "data_type": "products",
  "target_categories": ["products", "services"],
  "language": "VIETNAMESE",
  "callback_url": "https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback",
  "company_info": {
    "name": "AIA Vietnam",
    "industry": "insurance"
  }
}
```

### Expected Callback (Success):
```bash
POST https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback
Content-Type: application/json
X-Webhook-Source: ai-service
X-Webhook-Signature: sha256=abc123...
User-Agent: Agent8x-AI-Service/1.0

{
  "task_id": "extract_1753600241578_a6406721",
  "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
  "status": "completed",
  "processing_time": 16.6029052734375,
  "timestamp": "2025-07-27T07:11:00.602714",
  
  // Summary results for quick display
  "results": {
    "products_count": 3,
    "services_count": 2, 
    "total_items": 5,
    "ai_provider": "gemini",
    "template_used": "InsuranceExtractionTemplate"
  },
  
  // ✅ FULL RAW CONTENT (Complete original file text)
  "raw_content": "--- DỊCH VỤ AIA VIỆT NAM (25/7/2025) – CHI TIẾT QUYỀN LỢI – PHÍ – ĐIỀU KIỆN ---\n\n1. AIA – Khỏe Trọn Vẹn (Bảo hiểm liên kết chung)\n   * Quỹ bảo vệ: Khách đóng phí cơ bản đầy đủ trong 4‑15 năm đầu tùy phương án...",
  
  // ✅ FULL STRUCTURED DATA (Complete products and services with all details + AI categorization)
  "structured_data": {
    "products": [
      {
        "name": "AIA – Khỏe Trọn Vẹn",
        "type": "Bảo hiểm liên kết chung",
        "description": "Bảo vệ tài chính trước rủi ro tử vong, thương tật toàn bộ vĩnh viễn, bệnh hiểm nghèo (tùy gói). Hưởng giá trị bảo vệ ưu việt; quyền lợi bảo vệ có thể tăng thêm tới 20% STBH nhờ chương trình AIA Vitality. Thưởng duy trì hợp đồng.",
        "coverage_period": "30 năm",
        "premium": "Tùy thuộc vào tuổi, giới tính, chương trình, sản phẩm bổ sung",
        "terms_and_conditions": "Tùy sản phẩm, yêu cầu sức khỏe và khai thác thông tin y tế.",
        // ✅ AI-generated categorization for hybrid search
        "category": "bảo_hiểm_nhân_thọ",
        "sub_category": "bảo_hiểm_liên_kết",
        "tags": ["nhân_thọ", "liên_kết_chung", "bảo_vệ_toàn_diện", "aia_vitality", "thưởng_duy_trì"],
        "target_audience": ["cá_nhân", "gia_đình"],
        "coverage_type": ["tử_vong", "thương_tật", "bệnh_hiểm_nghèo"]
      },
      {
        "name": "Bảo hiểm Toàn diện Bệnh hiểm nghèo 2.0",
        "type": "Critical Illness 2.0",
        "description": "Bảo vệ trước 107 bệnh hiểm nghèo, chi trả theo giai đoạn.",
        "age_range": "30 ngày – 65 tuổi",
        "coverage_period": "Tối đa đến 75 tuổi",
        "premium": "Phí thay đổi tùy theo tuổi, gói bảo hiểm",
        "terms_and_conditions": "Tuổi từ 30 ngày đến 65 tuổi, không tham gia nếu đã có bệnh hiểm nghèo tại thời điểm tham gia; Quy định thời gian chờ.",
        // ✅ AI-generated categorization for hybrid search
        "category": "bảo_hiểm_sức_khỏe",
        "sub_category": "bệnh_hiểm_nghèo",
        "tags": ["bệnh_hiểm_nghèo", "107_bệnh", "chi_trả_giai_đoạn", "toàn_diện"],
        "target_audience": ["mọi_lứa_tuổi"],
        "coverage_type": ["bệnh_hiểm_nghèo", "ung_thư", "tim_mạch"]
      },
      {
        "name": "Bảo hiểm sức khỏe Bùng Gia Lực",
        "type": "Family Health Insurance",
        "description": "Bảo hiểm sức khỏe cho gia đình.",
        "age_range": "30 ngày tuổi đến 46 tuổi",
        "coverage_area": "Chỉ tại Việt Nam",
        "premium": "Phí tùy theo gói chọn (Cơ bản, Nâng cao, Toàn diện, Hoàn hảo), giới tính, tuổi và phạm vi bảo vệ (Việt Nam/Toàn cầu)",
        "terms_and_conditions": "Tuổi từ 30 ngày đến 46 tuổi (hoặc theo điều khoản cụ thể), điều kiện sức khỏe theo thẩm định của AIA.",
        // ✅ AI-generated categorization for hybrid search
        "category": "bảo_hiểm_sức_khỏe",
        "sub_category": "bảo_hiểm_gia_đình",
        "tags": ["gia_đình", "sức_khỏe", "nhiều_gói", "việt_nam", "toàn_cầu"],
        "target_audience": ["gia_đình", "trẻ_em"],
        "coverage_type": ["y_tế", "nội_trú", "ngoại_trú"]
      }
    ],
    "services": [
      {
        "name": "AIA Vitality",
        "type": "Chương trình ưu đãi",
        "description": "Chương trình AIA Vitality cung cấp quyền lợi bảo vệ có thể tăng thêm tới 20% STBH cho sản phẩm AIA – Khỏe Trọn Vẹn và thưởng đến 30% phí bảo hiểm trung bình 5 năm cho sản phẩm Bảo hiểm Toàn diện Bệnh hiểm nghèo 2.0 và thưởng đến 60% phí cho sản phẩm Bảo hiểm sức khỏe Bùng Gia Lực.",
        "pricing": "Tích hợp vào các gói bảo hiểm",
        "availability": "Có sẵn cho các sản phẩm bảo hiểm AIA",
        // ✅ AI-generated categorization for hybrid search
        "category": "chương_trình_ưu_đãi",
        "sub_category": "vitality_rewards",
        "tags": ["ưu_đãi", "tăng_quyền_lợi", "thưởng_phí", "sức_khỏe", "lối_sống"],
        "target_audience": ["khách_hàng_hiện_tại"],
        "service_type": ["loyalty_program", "health_wellness"]
      },
      {
        "name": "Đặt lịch khám tại bệnh viện",
        "type": "Dịch vụ hỗ trợ",
        "description": "Ưu đãi dịch vụ đặt lịch khám tại một số bệnh viện uy tín (từ 17/7/2025 đến 31/12/2025)",
        "pricing": "Miễn phí",
        "availability": "Từ 17/7/2025 đến 31/12/2025",
        // ✅ AI-generated categorization for hybrid search
        "category": "dịch_vụ_hỗ_trợ",
        "sub_category": "đặt_lịch_khám",
        "tags": ["đặt_lịch", "bệnh_viện", "miễn_phí", "hỗ_trợ_khách_hàng"],
        "target_audience": ["tất_cả_khách_hàng"],
        "service_type": ["customer_support", "healthcare_booking"]
      }
    ],
    "extraction_summary": {
      "total_products": 3,
      "total_services": 2,
      "data_quality": "high",
      "categorization_notes": "The categorization was based on whether the item was a tangible product or an intangible service. Insurance plans were categorized as products, while additional benefits and support services were categorized as services.",
      "industry_context": "The insurance industry context was used to differentiate between insurance plans (products) and added-value services."
    }
  },
  
  // Full extraction metadata for reference
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
    "extraction_timestamp": "2025-07-26T14:52:54.626455",
    "total_items": 5,
    "source": "ai_extraction_service_v2"
  }
}
```

### Expected Callback (Error):
```bash  
POST https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback
Content-Type: application/json

{
  "task_id": "extract_1753600241578_a6406721",
  "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f", 
  "status": "failed",
  "error": "AI extraction timeout after 30 seconds",
  "timestamp": "2025-07-27T07:11:00.602714"
}
```

---

## 🛠 Backend Implementation Requirements

### 1. **File Upload Webhook Handler**

```javascript
// Backend implementation for File Upload Callback
app.post('/api/webhooks/file-processed', webhookAuth, async (req, res) => {
  try {
    const { event, companyId, data, timestamp } = req.body;
    
    if (event === 'file.uploaded') {
      if (data.status === 'completed') {
        // ✅ File upload và raw extraction thành công - LƯU TOÀN BỘ DỮ LIỆU
        console.log(`✅ File ${data.fileId} processed successfully`);
        console.log(`   📄 Raw content: ${data.raw_content ? data.raw_content.length : 0} characters`);
        console.log(`   📦 Chunks created: ${data.chunksCreated}`);
        console.log(`   🏷️ Tags: ${data.tags ? data.tags.join(', ') : 'none'}`);
        console.log(`   ⏱️ Processing time: ${data.processingTime}s`);
        
        // Store file upload record in database
        const fileRecord = await db.uploaded_files.create({
          file_id: data.fileId,
          company_id: companyId,
          original_name: data.file_metadata.original_name,
          file_name: data.file_metadata.file_name,
          file_size: data.file_metadata.file_size,
          file_type: data.file_metadata.file_type,
          uploaded_by: data.file_metadata.uploaded_by,
          description: data.file_metadata.description,
          r2_url: data.file_metadata.r2_url,
          raw_content: data.raw_content,  // Store complete file content
          tags: JSON.stringify(data.tags),
          chunks_created: data.chunksCreated,
          processing_time: data.processingTime,
          processed_at: new Date(data.processedAt),
          status: data.status,
          created_at: new Date()
        });
        
        // Update company file count
        await db.companies.update(
          { id: companyId },
          { 
            total_files: db.sequelize.literal('total_files + 1'),
            last_file_uploaded: new Date()
          }
        );
        
        // Index tags for search
        if (data.tags && data.tags.length > 0) {
          for (const tag of data.tags) {
            await db.file_tags.upsert({
              company_id: companyId,
              tag_name: tag,
              file_count: db.sequelize.literal('file_count + 1'),
              updated_at: new Date()
            });
          }
        }
        
        res.status(200).json({
          success: true,
          message: "File upload record saved successfully",
          file_record: {
            id: fileRecord.id,
            file_id: data.fileId,
            chunks_created: data.chunksCreated,
            raw_content_length: data.raw_content ? data.raw_content.length : 0
          }
        });
        
      } else if (data.status === 'failed') {
        // ❌ File upload thất bại
        console.error(`❌ File ${data.fileId} processing failed: ${data.error}`);
        
        // Update database status  
        await db.uploaded_files.create({
          file_id: data.fileId,
          company_id: companyId,
          status: 'failed',
          error_message: data.error,
          raw_content: data.raw_content || "", // Partial content if available
          file_metadata: JSON.stringify(data.file_metadata || {}),
          created_at: new Date()
        });
        
        res.status(200).json({
          success: true,
          message: "Error status updated successfully"
        });
      }
    }
    
  } catch (error) {
    console.error('❌ File upload webhook processing failed:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});
```

### 2. **AI Extraction Webhook Handler**

```javascript
// Backend implementation for AI Extraction Callback
app.post('/api/webhooks/ai/extraction-callback', webhookAuth, async (req, res) => {
  try {
    const { 
      task_id, 
      company_id, 
      status, 
      processing_time,
      results,
      raw_content,
      structured_data,
      extraction_metadata,
      error, 
      timestamp 
    } = req.body;
    
    if (status === 'completed') {
      // ✅ AI Extraction thành công - LƯU TOÀN BỘ DỮ LIỆU
      console.log(`🎉 AI extraction ${task_id} completed successfully`);
      console.log(`   📦 Products: ${results.products_count}`);
      console.log(`   🔧 Services: ${results.services_count}`);
      console.log(`   📄 Raw content: ${raw_content ? raw_content.length : 0} characters`);
      console.log(`   🤖 AI Provider: ${results.ai_provider}`);
      console.log(`   📋 Template: ${results.template_used}`);
      
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
      
      // 2. Save extracted PRODUCTS to database
      if (structured_data.products && structured_data.products.length > 0) {
        for (const product of structured_data.products) {
          await db.extracted_products.create({
            job_id: job.id,
            company_id: company_id,
            name: product.name,
            type: product.type,
            description: product.description,
            coverage_period: product.coverage_period,
            age_range: product.age_range,
            coverage_area: product.coverage_area,
            premium: product.premium,
            terms_and_conditions: product.terms_and_conditions,
            created_at: new Date()
          });
        }
        console.log(`✅ Saved ${structured_data.products.length} products to database`);
      }
      
      // 3. Save extracted SERVICES to database
      if (structured_data.services && structured_data.services.length > 0) {
        for (const service of structured_data.services) {
          await db.extracted_services.create({
            job_id: job.id,
            company_id: company_id,
            name: service.name,
            type: service.type,
            description: service.description,
            pricing: service.pricing,
            availability: service.availability,
            created_at: new Date()
          });
        }
        console.log(`✅ Saved ${structured_data.services.length} services to database`);
      }
      
      // 4. Return success response
      res.status(200).json({
        success: true,
        message: "Extraction results saved successfully",
        saved_items: {
          products: structured_data.products ? structured_data.products.length : 0,
          services: structured_data.services ? structured_data.services.length : 0,
          total: results.total_items
        }
      });
      
    } else if (status === 'failed') {
      // ❌ AI Extraction thất bại  
      console.error(`❌ AI extraction ${task_id} failed: ${error}`);
      
      // Update database status
      await db.extraction_jobs.update(
        { task_id: task_id },
        {
          status: 'failed',
          completed_at: new Date(),
          error_message: error
        }
      );
      
      res.status(200).json({
        success: true,
        message: "Error status updated successfully"
      });
    }
    
  } catch (error) {
    console.error('❌ AI extraction webhook processing failed:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});
```

---

## � Database Schema Updates

### Required Database Tables:

#### 1. **uploaded_files table** (for file upload callbacks)
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
    raw_content TEXT,  -- Store complete file content
    tags JSONB,
    chunks_created INTEGER DEFAULT 0,
    processing_time DECIMAL(10,3),
    processed_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'uploaded',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### 2. **extraction_jobs table** (for AI extraction callbacks)
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
    raw_content TEXT,  -- Store complete original content
    extraction_metadata JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### 3. **extracted_products table** (store individual products với AI categorization)
```sql
CREATE TABLE extracted_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES extraction_jobs(id),
    company_id VARCHAR(255),
    name VARCHAR(500) NOT NULL,
    type VARCHAR(200),
    description TEXT,
    coverage_period VARCHAR(100),
    age_range VARCHAR(100),
    coverage_area VARCHAR(200),
    premium TEXT,
    terms_and_conditions TEXT,
    -- ✅ AI Categorization fields cho Hybrid Search
    category VARCHAR(200), -- e.g., "bảo_hiểm_nhân_thọ", "bảo_hiểm_sức_khỏe"
    sub_category VARCHAR(200), -- e.g., "bảo_hiểm_liên_kết", "bệnh_hiểm_nghèo"
    tags JSONB, -- e.g., ["nhân_thọ", "liên_kết_chung", "bảo_vệ_toàn_diện"]
    target_audience JSONB, -- e.g., ["cá_nhân", "gia_đình"]
    coverage_type JSONB, -- e.g., ["tử_vong", "thương_tật", "bệnh_hiểm_nghèo"]
    -- ✅ Qdrant integration
    qdrant_point_id VARCHAR(255), -- Single point ID for individual product storage
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 4. **extracted_services table** (store individual services với AI categorization)
```sql
CREATE TABLE extracted_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES extraction_jobs(id),
    company_id VARCHAR(255),
    name VARCHAR(500) NOT NULL,
    type VARCHAR(200),
    description TEXT,
    pricing TEXT,
    availability VARCHAR(200),
    -- ✅ AI Categorization fields cho Hybrid Search
    category VARCHAR(200), -- e.g., "chương_trình_ưu_đãi", "dịch_vụ_hỗ_trợ"
    sub_category VARCHAR(200), -- e.g., "vitality_rewards", "đặt_lịch_khám"
    tags JSONB, -- e.g., ["ưu_đãi", "tăng_quyền_lợi", "thưởng_phí"]
    target_audience JSONB, -- e.g., ["khách_hàng_hiện_tại"]
    service_type JSONB, -- e.g., ["loyalty_program", "health_wellness"]
    -- ✅ Qdrant integration
    qdrant_point_id VARCHAR(255), -- Single point ID for individual service storage
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 5. **file_tags table** (for tag indexing)
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

#### 6. **companies table** (update for file tracking)
```sql
ALTER TABLE companies 
ADD COLUMN total_files INTEGER DEFAULT 0,
ADD COLUMN last_file_uploaded TIMESTAMP;
```

### Database Indexes:
```sql
-- Performance indexes
CREATE INDEX idx_extraction_jobs_company_id ON extraction_jobs(company_id);
CREATE INDEX idx_extraction_jobs_task_id ON extraction_jobs(task_id);
CREATE INDEX idx_extracted_products_company_id ON extracted_products(company_id);
CREATE INDEX idx_extracted_services_company_id ON extracted_services(company_id);
CREATE INDEX idx_uploaded_files_company_id ON uploaded_files(company_id);
CREATE INDEX idx_file_tags_company_id ON file_tags(company_id);

-- ✅ Hybrid Search indexes cho metadata filtering
CREATE INDEX idx_extracted_products_category ON extracted_products(category);
CREATE INDEX idx_extracted_products_sub_category ON extracted_products(sub_category);
CREATE INDEX idx_extracted_products_tags ON extracted_products USING GIN(tags);
CREATE INDEX idx_extracted_products_target_audience ON extracted_products USING GIN(target_audience);
CREATE INDEX idx_extracted_products_coverage_type ON extracted_products USING GIN(coverage_type);

CREATE INDEX idx_extracted_services_category ON extracted_services(category);
CREATE INDEX idx_extracted_services_sub_category ON extracted_services(sub_category);
CREATE INDEX idx_extracted_services_tags ON extracted_services USING GIN(tags);
CREATE INDEX idx_extracted_services_target_audience ON extracted_services USING GIN(target_audience);
CREATE INDEX idx_extracted_services_service_type ON extracted_services USING GIN(service_type);

-- ✅ Qdrant integration indexes
CREATE INDEX idx_extracted_products_qdrant_point_id ON extracted_products(qdrant_point_id);
CREATE INDEX idx_extracted_services_qdrant_point_id ON extracted_services(qdrant_point_id);
```

---

## 🔄 Hybrid Search Strategy: AI Categorization + Vector Search + User Feedback

### Problem: Precision vs Recall Trade-off

- **Search (Precision-focused)**: Tìm ra vài kết quả **liên quan nhất** (ví dụ: "trà nào tốt cho người mất ngủ?" -> trả về trà hoa cúc)
- **Retrieval (Recall-focused)**: Lấy ra **tất cả** các mục thuộc một danh mục (ví dụ: "liệt kê tất cả các loại trà" -> trả về toàn bộ 30 món trà)

### Solution: Hybrid Strategy với AI Categorization + User Feedback Loop

#### 1. **AI Categorization at Extraction Time**

AI service sẽ được cấu hình để tự động phân loại products/services với structured prompt:

```javascript
// ✅ Enhanced AI Extraction Prompt Template
const extractionPrompt = `
Bạn là chuyên gia phân tích sản phẩm/dịch vụ. Hãy trích xuất thông tin và PHÂN LOẠI chi tiết theo format JSON sau:

IMPORTANT: Cho mỗi product/service, hãy tạo:
1. category: Danh mục chính (dùng snake_case, tiếng Việt không dấu)
2. sub_category: Danh mục phụ (chi tiết hơn)
3. tags: Array các từ khóa tìm kiếm (5-8 tags)
4. target_audience: Đối tượng khách hàng mục tiêu
5. coverage_type/service_type: Loại bảo hiểm/dịch vụ

Ví dụ categorization cho ngành bảo hiểm:
- category: "bao_hiem_nhan_tho", "bao_hiem_suc_khoe", "chuong_trinh_uu_dai"
- sub_category: "bao_hiem_lien_ket", "bệnh_hiểm_nghèo", "vitality_rewards"
- tags: ["nhan_tho", "gia_dinh", "bao_ve_toan_dien", "uu_dai"]

Phân loại dựa trên:
- Nội dung mô tả sản phẩm
- Đối tượng khách hàng
- Loại bảo hiểm/dịch vụ
- Tính năng đặc biệt

${fileContent}

Trả về JSON format với đầy đủ categorization metadata.
`;
```

#### 2. **Enhanced Database Schema với Qdrant Point IDs**

```sql
-- Remove chunking approach, use single point per product/service
ALTER TABLE extracted_products 
DROP COLUMN IF EXISTS qdrant_point_ids,
ADD COLUMN qdrant_point_id VARCHAR(255);  -- Single point ID

ALTER TABLE extracted_services 
DROP COLUMN IF EXISTS qdrant_point_ids,
ADD COLUMN qdrant_point_id VARCHAR(255);  -- Single point ID
```

#### 3. **Enhanced Callback Handler với Individual Product/Service Storage + AI Categorization**

```javascript
// Enhanced AI Extraction Callback Handler với Hybrid Search Strategy
app.post('/api/webhooks/ai/extraction-callback', webhookAuth, async (req, res) => {
  try {
    const { structured_data, extraction_metadata, ... } = req.body;
    
    if (status === 'completed') {
      // 🔑 STRATEGY: Store each product/service as SINGLE Qdrant point with rich metadata
      
      // Save products với individual Qdrant storage + AI categorization
      if (structured_data.products && structured_data.products.length > 0) {
        for (let i = 0; i < structured_data.products.length; i++) {
          const product = structured_data.products[i];
          
          // 1. Create database record first để get UUID
          const savedProduct = await db.extracted_products.create({
            job_id: job.id,
            company_id: company_id,
            name: product.name,
            type: product.type,
            description: product.description,
            coverage_period: product.coverage_period,
            age_range: product.age_range,
            coverage_area: product.coverage_area,
            premium: product.premium,
            terms_and_conditions: product.terms_and_conditions,
            // ✅ Store AI categorization in database
            category: product.category,
            sub_category: product.sub_category,
            tags: JSON.stringify(product.tags || []),
            target_audience: JSON.stringify(product.target_audience || []),
            coverage_type: JSON.stringify(product.coverage_type || []),
            created_at: new Date()
          });
          
          // 2. Create SINGLE Qdrant point cho product này với rich metadata
          const productContent = `${product.name} - ${product.type}\n${product.description}\nPhí: ${product.premium}\nĐiều kiện: ${product.terms_and_conditions}`;
          const pointId = `product_${savedProduct.id}`;
          
          // Generate embedding và store trong Qdrant với comprehensive metadata
          const embedding = await generateEmbedding(productContent);
          
          await qdrant.upsert('multi_company_data', {
            points: [{
              id: pointId,
              vector: embedding,
              payload: {
                content: productContent,
                content_type: 'extracted_product',
                product_id: savedProduct.id, // Link to database UUID
                product_name: product.name,
                product_type: product.type,
                // ✅ Rich metadata cho hybrid filtering
                category: product.category,
                sub_category: product.sub_category,
                tags: product.tags || [],
                target_audience: product.target_audience || [],
                coverage_type: product.coverage_type || [],
                // ✅ Search optimization fields
                searchable_text: `${product.name} ${product.type} ${product.description} ${(product.tags || []).join(' ')}`,
                company_id: company_id,
                job_id: job.id,
                created_at: new Date().toISOString()
              }
            }]
          });
          
          // 3. Update database với Qdrant point ID
          await savedProduct.update({
            qdrant_point_id: pointId
          });
          
          console.log(`✅ Product ${savedProduct.id} stored as single Qdrant point: ${pointId}`);
          console.log(`   📂 Category: ${product.category}`);
          console.log(`   🏷️ Tags: ${(product.tags || []).join(', ')}`);
        }
      }
      
      // Same strategy for services với individual storage + AI categorization
      if (structured_data.services && structured_data.services.length > 0) {
        for (let i = 0; i < structured_data.services.length; i++) {
          const service = structured_data.services[i];
          
          // 1. Create database record first
          const savedService = await db.extracted_services.create({
            job_id: job.id,
            company_id: company_id,
            name: service.name,
            type: service.type,
            description: service.description,
            pricing: service.pricing,
            availability: service.availability,
            // ✅ Store AI categorization in database
            category: service.category,
            sub_category: service.sub_category,
            tags: JSON.stringify(service.tags || []),
            target_audience: JSON.stringify(service.target_audience || []),
            service_type: JSON.stringify(service.service_type || []),
            created_at: new Date()
          });
          
          // 2. Create SINGLE Qdrant point cho service này với rich metadata
          const serviceContent = `${service.name} - ${service.type}\n${service.description}\nGiá: ${service.pricing}\nCó sẵn: ${service.availability}`;
          const pointId = `service_${savedService.id}`;
          
          const embedding = await generateEmbedding(serviceContent);
          
          await qdrant.upsert('multi_company_data', {
            points: [{
              id: pointId,
              vector: embedding,
              payload: {
                content: serviceContent,
                content_type: 'extracted_service',
                service_id: savedService.id, // Link to database UUID
                service_name: service.name,
                service_type_primary: service.type,
                // ✅ Rich metadata cho hybrid filtering
                category: service.category,
                sub_category: service.sub_category,
                tags: service.tags || [],
                target_audience: service.target_audience || [],
                service_type: service.service_type || [],
                // ✅ Search optimization fields
                searchable_text: `${service.name} ${service.type} ${service.description} ${(service.tags || []).join(' ')}`,
                company_id: company_id,
                job_id: job.id,
                created_at: new Date().toISOString()
              }
            }]
          });
          
          // 3. Update database với Qdrant point ID
          await savedService.update({
            qdrant_point_id: pointId
          });
          
          console.log(`✅ Service ${savedService.id} stored as single Qdrant point: ${pointId}`);
          console.log(`   📂 Category: ${service.category}`);
          console.log(`   🏷️ Tags: ${(service.tags || []).join(', ')}`);
        }
      }
      
      // 4. Return success response
      res.status(200).json({
        success: true,
        message: "Extraction results saved successfully",
        saved_items: {
          products: structured_data.products ? structured_data.products.length : 0,
          services: structured_data.services ? structured_data.services.length : 0,
          total: results.total_items
        }
      });
      
    } else if (status === 'failed') {
      // ❌ AI Extraction thất bại  
      console.error(`❌ AI extraction ${task_id} failed: ${error}`);
      
      // Update database status
      await db.extraction_jobs.update(
        { task_id: task_id },
        {
          status: 'failed',
          completed_at: new Date(),
          error_message: error
        }
      );
      
      res.status(200).json({
        success: true,
        message: "Error status updated successfully"
      });
    }
  } catch (error) {
    console.error('❌ AI extraction webhook processing failed:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});
```

---

## **✅ STRATEGY 4: Hybrid Search Implementation với Individual Product/Service Storage + AI Categorization**

```javascript
// 🎯 HYBRID SEARCH: Kết hợp Metadata Filtering (category-based) với Vector Search (similarity ranking)

// ============ HYBRID SEARCH: Category-based Product/Service Retrieval ============
app.post('/api/chat/hybrid-search/:company_id', async (req, res) => {
  try {
    const { company_id } = req.params;
    const { query, mode = 'hybrid', categories = [], tags = [], limit = 20 } = req.body;
    
    let searchResults = [];
    
    if (mode === 'category' || mode === 'hybrid') {
      // 🔍 STEP 1: Metadata Filtering để get tất cả products/services trong categories
      const metadataFilter = {
        must: [
          { key: 'company_id', match: { value: company_id }},
          { key: 'content_type', match: { any: ['extracted_product', 'extracted_service'] }}
        ]
      };
      
      // Add category filter nếu user specify categories
      if (categories.length > 0) {
        metadataFilter.must.push({
          key: 'category',
          match: { any: categories }
        });
      }
      
      // Add tag filter nếu user specify tags
      if (tags.length > 0) {
        metadataFilter.must.push({
          key: 'tags',
          match: { any: tags }
        });
      }
      
      // Query với metadata filtering only (no vector search yet)
      const metadataResults = await qdrant.scroll('multi_company_data', {
        filter: metadataFilter,
        limit: 100, // Get more results để sau đó rank bằng vector search
        with_payload: true,
        with_vector: false
      });
      
      console.log(`📂 Metadata filtering found ${metadataResults.points.length} items`);
      
      if (mode === 'category') {
        // Pure category mode: return all found items without vector ranking
        searchResults = metadataResults.points.map(point => ({
          id: point.id,
          content: point.payload.content,
          score: 1.0, // No similarity score
          metadata: point.payload
        }));
      } else {
        // Hybrid mode: rank filtered results by vector similarity
        if (metadataResults.points.length > 0 && query) {
          const queryEmbedding = await generateEmbedding(query);
          
          // Get vectors for filtered points và calculate similarity
          const vectorResults = await qdrant.search('multi_company_data', {
            vector: queryEmbedding,
            filter: metadataFilter,
            limit: Math.min(limit, metadataResults.points.length),
            with_payload: true
          });
          
          searchResults = vectorResults.map(result => ({
            id: result.id,
            content: result.payload.content,
            score: result.score,
            metadata: result.payload
          }));
          
          console.log(`🎯 Hybrid search ranked ${searchResults.length} items by similarity`);
        } else {
          // Fallback to metadata results nếu no query
          searchResults = metadataResults.points.slice(0, limit).map(point => ({
            id: point.id,
            content: point.payload.content,
            score: 1.0,
            metadata: point.payload
          }));
        }
      }
    } else if (mode === 'semantic') {
      // Pure semantic search
      if (query) {
        const queryEmbedding = await generateEmbedding(query);
        
        const vectorResults = await qdrant.search('multi_company_data', {
          vector: queryEmbedding,
          filter: {
            must: [
              { key: 'company_id', match: { value: company_id }},
              { key: 'content_type', match: { any: ['extracted_product', 'extracted_service'] }}
            ]
          },
          limit: limit,
          with_payload: true
        });
        
        searchResults = vectorResults.map(result => ({
          id: result.id,
          content: result.payload.content,
          score: result.score,
          metadata: result.payload
        }));
      }
    }
    
    // Group results by product/service để avoid duplicates
    const groupedResults = {};
    searchResults.forEach(result => {
      const productId = result.metadata.product_id;
      const serviceId = result.metadata.service_id;
      const key = productId ? `product_${productId}` : `service_${serviceId}`;
      
      if (!groupedResults[key] || result.score > groupedResults[key].score) {
        groupedResults[key] = result;
      }
    });
    
    const finalResults = Object.values(groupedResults);
    
    res.json({
      success: true,
      mode: mode,
      total_found: finalResults.length,
      categories_used: categories,
      tags_used: tags,
      results: finalResults.map(result => ({
        content: result.content,
        score: result.score,
        metadata: {
          type: result.metadata.content_type,
          name: result.metadata.product_name || result.metadata.service_name,
          category: result.metadata.category,
          sub_category: result.metadata.sub_category,
          tags: result.metadata.tags,
          target_audience: result.metadata.target_audience
        }
      }))
    });
    
  } catch (error) {
    console.error('❌ Hybrid search error:', error);
    res.status(500).json({
      success: false,
      error: 'Hybrid search failed',
      details: error.message
    });
  }
});

// ============ CATEGORY MANAGEMENT: User Feedback Loop ============
app.post('/api/management/update-category/:company_id', async (req, res) => {
  try {
    const { company_id } = req.params;
    const { 
      item_type, // 'product' or 'service'
      item_id, 
      new_category, 
      new_sub_category, 
      new_tags = [], 
      new_target_audience = [] 
    } = req.body;
    
    // 1. Update database record
    const table = item_type === 'product' ? 'extracted_products' : 'extracted_services';
    const updateData = {
      category: new_category,
      sub_category: new_sub_category,
      tags: JSON.stringify(new_tags),
      target_audience: JSON.stringify(new_target_audience),
      updated_at: new Date()
    };
    
    const updatedRecord = await db[table].update(updateData, {
      where: { 
        id: item_id,
        company_id: company_id 
      },
      returning: true
    });
    
    if (updatedRecord[0] === 0) {
      return res.status(404).json({
        success: false,
        error: `${item_type} not found`
      });
    }
    
    // 2. Update corresponding Qdrant point với new metadata
    const record = updatedRecord[1][0];
    const pointId = record.qdrant_point_id;
    
    if (pointId) {
      // Get current point data
      const currentPoint = await qdrant.retrieve('multi_company_data', [pointId]);
      
      if (currentPoint.length > 0) {
        const currentPayload = currentPoint[0].payload;
        
        // Update payload với new categorization
        const updatedPayload = {
          ...currentPayload,
          category: new_category,
          sub_category: new_sub_category,
          tags: new_tags,
          target_audience: new_target_audience,
          searchable_text: `${currentPayload.product_name || currentPayload.service_name} ${currentPayload.product_type || currentPayload.service_type_primary} ${currentPayload.content} ${new_tags.join(' ')}`,
          updated_at: new Date().toISOString()
        };
        
        // Upsert với updated payload (keep same vector)
        await qdrant.upsert('multi_company_data', {
          points: [{
            id: pointId,
            vector: currentPoint[0].vector,
            payload: updatedPayload
          }]
        });
        
        console.log(`✅ Updated ${item_type} ${item_id} category: ${new_category} -> ${new_sub_category}`);
        console.log(`   🏷️ New tags: ${new_tags.join(', ')}`);
      }
    }
    
    res.json({
      success: true,
      message: `${item_type} categorization updated`,
      updated_record: {
        id: item_id,
        category: new_category,
        sub_category: new_sub_category,
        tags: new_tags,
        target_audience: new_target_audience
      }
    });
    
  } catch (error) {
    console.error('❌ Category update error:', error);
    res.status(500).json({
      success: false,
      error: 'Category update failed',
      details: error.message
    });
  }
});

// ============ CATEGORY ANALYTICS: Understanding Distribution ============
app.get('/api/analytics/categories/:company_id', async (req, res) => {
  try {
    const { company_id } = req.params;
    
    // Aggregate categories from Qdrant để get real-time distribution
    const allPoints = await qdrant.scroll('multi_company_data', {
      filter: {
        must: [
          { key: 'company_id', match: { value: company_id }},
          { key: 'content_type', match: { any: ['extracted_product', 'extracted_service'] }}
        ]
      },
      limit: 1000,
      with_payload: true,
      with_vector: false
    });
    
    const categoryStats = {};
    const tagStats = {};
    const typeStats = { products: 0, services: 0 };
    
    allPoints.points.forEach(point => {
      const payload = point.payload;
      
      // Count by type
      if (payload.content_type === 'extracted_product') {
        typeStats.products++;
      } else if (payload.content_type === 'extracted_service') {
        typeStats.services++;
      }
      
      // Count by category
      const category = payload.category || 'uncategorized';
      if (!categoryStats[category]) {
        categoryStats[category] = {
          count: 0,
          sub_categories: {}
        };
      }
      categoryStats[category].count++;
      
      // Count by sub_category
      const subCategory = payload.sub_category || 'other';
      if (!categoryStats[category].sub_categories[subCategory]) {
        categoryStats[category].sub_categories[subCategory] = 0;
      }
      categoryStats[category].sub_categories[subCategory]++;
      
      // Count by tags
      (payload.tags || []).forEach(tag => {
        if (!tagStats[tag]) {
          tagStats[tag] = 0;
        }
        tagStats[tag]++;
      });
    });
    
    res.json({
      success: true,
      total_items: allPoints.points.length,
      type_distribution: typeStats,
      category_distribution: categoryStats,
      top_tags: Object.entries(tagStats)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 20)
        .map(([tag, count]) => ({ tag, count }))
    });
    
  } catch (error) {
    console.error('❌ Category analytics error:', error);
    res.status(500).json({
      success: false,
      error: 'Category analytics failed',
      details: error.message
    });
  }
});
```

#### 3. **CRUD Operations với Individual Product/Service Management**

```javascript
// === UPDATE Product/Service (Individual Granular Control) ===
app.put('/api/products/:productId', async (req, res) => {
  try {
    const { productId } = req.params;
    const updates = req.body;
    
    // 1. Get existing product với Qdrant point IDs
    const product = await db.extracted_products.findByPk(productId);
    if (!product) {
      return res.status(404).json({ error: 'Product not found' });
    }
    
    const qdrantPointIds = JSON.parse(product.qdrant_point_ids || '[]');
    
    // 2. Delete ALL old Qdrant points for this specific product
    if (qdrantPointIds.length > 0) {
      await qdrant.delete('multi_company_data', {
        points: qdrantPointIds
      });
      console.log(`🗑️ Deleted ${qdrantPointIds.length} old Qdrant points for product ${productId}`);
    }
    
    // 3. Update database record
    await product.update(updates);
    
    // 4. Create NEW Qdrant points với updated content
    const updatedContent = `${updates.name || product.name} - ${updates.type || product.type}\n${updates.description || product.description}\nPhí: ${updates.premium || product.premium}\nĐiều kiện: ${updates.terms_and_conditions || product.terms_and_conditions}`;
    
    const chunks = chunkContent(updatedContent, 2000);
    const newQdrantPointIds = [];
    
    for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex++) {
      const pointId = `product_${productId}_chunk_${chunkIndex}`;
      newQdrantPointIds.push(pointId);
      
      const embedding = await generateEmbedding(chunks[chunkIndex]);
      
      await qdrant.upsert('multi_company_data', {
        points: [{
          id: pointId,
          vector: embedding,
          payload: {
            content: chunks[chunkIndex],
            content_type: 'extracted_product',
            product_id: productId,
            product_name: updates.name || product.name,
            product_type: updates.type || product.type,
            company_id: product.company_id,
            chunk_index: chunkIndex,
            total_chunks: chunks.length,
            updated_at: new Date().toISOString()
          }
        }]
      });
    }
    
    // 5. Update database với new Qdrant point IDs
    await product.update({
      qdrant_point_ids: JSON.stringify(newQdrantPointIds)
    });
    
    res.json({
      success: true,
      message: 'Product updated successfully',
      product: product,
      qdrant_changes: {
        old_points_deleted: qdrantPointIds.length,
        new_points_created: newQdrantPointIds.length
      }
    });
    
  } catch (error) {
    console.error('Failed to update product:', error);
    res.status(500).json({ error: 'Failed to update product' });
  }
});

// === DELETE Product/Service (Individual Clean Removal) ===
app.delete('/api/products/:productId', async (req, res) => {
  try {
    const { productId } = req.params;
    
    // 1. Get product với Qdrant point IDs
    const product = await db.extracted_products.findByPk(productId);
    if (!product) {
      return res.status(404).json({ error: 'Product not found' });
    }
    
    const qdrantPointIds = JSON.parse(product.qdrant_point_ids || '[]');
    
    // 2. Delete ALL Qdrant points for this specific product ONLY
    if (qdrantPointIds.length > 0) {
      await qdrant.delete('multi_company_data', {
        points: qdrantPointIds
      });
      console.log(`🗑️ Deleted ${qdrantPointIds.length} Qdrant points for product ${productId}`);
    }
    
    // 3. Delete từ database
    await product.destroy();
    
    res.json({
      success: true,
      message: 'Product deleted successfully',
      deleted_product: {
        id: productId,
        name: product.name,
        qdrant_points_deleted: qdrantPointIds.length
      }
    });
    
  } catch (error) {
    console.error('Failed to delete product:', error);
    res.status(500).json({ error: 'Failed to delete product' });
  }
});

// === PARTIAL UPDATE (chỉ update specific fields) ===
app.patch('/api/products/:productId/fields', async (req, res) => {
  try {
    const { productId } = req.params;
    const { field, value } = req.body; // e.g., { field: 'premium', value: '2000 USD/year' }
    
    const product = await db.extracted_products.findByPk(productId);
    if (!product) {
      return res.status(404).json({ error: 'Product not found' });
    }
    
    // Validate field
    const allowedFields = ['name', 'type', 'description', 'premium', 'coverage_period', 'age_range', 'coverage_area', 'terms_and_conditions'];
    if (!allowedFields.includes(field)) {
      return res.status(400).json({ error: `Field '${field}' is not allowed for update` });
    }
    
    // Update specific field
    const updates = { [field]: value };
    await product.update(updates);
    
    // Re-create Qdrant points với updated content (same as full update)
    const qdrantPointIds = JSON.parse(product.qdrant_point_ids || '[]');
    
    if (qdrantPointIds.length > 0) {
      await qdrant.delete('multi_company_data', { points: qdrantPointIds });
    }
    
    const updatedProduct = await db.extracted_products.findByPk(productId);
    const updatedContent = `${updatedProduct.name} - ${updatedProduct.type}\n${updatedProduct.description}\nPhí: ${updatedProduct.premium}\nĐiều kiện: ${updatedProduct.terms_and_conditions}`;
    
    const chunks = chunkContent(updatedContent, 2000);
    const newQdrantPointIds = [];
    
    for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex++) {
      const pointId = `product_${productId}_chunk_${chunkIndex}`;
      newQdrantPointIds.push(pointId);
      
      const embedding = await generateEmbedding(chunks[chunkIndex]);
      
      await qdrant.upsert('multi_company_data', {
        points: [{
          id: pointId,
          vector: embedding,
          payload: {
            content: chunks[chunkIndex],
            content_type: 'extracted_product',
            product_id: productId,
            product_name: updatedProduct.name,
            product_type: updatedProduct.type,
            company_id: updatedProduct.company_id,
            chunk_index: chunkIndex,
            total_chunks: chunks.length,
            updated_at: new Date().toISOString()
          }
        }]
      });
    }
    
    await updatedProduct.update({
      qdrant_point_ids: JSON.stringify(newQdrantPointIds)
    });
    
    res.json({
      success: true,
      message: `Field '${field}' updated successfully`,
      updated_field: field,
      new_value: value,
      qdrant_points_recreated: newQdrantPointIds.length
    });
    
  } catch (error) {
    console.error('Failed to update product field:', error);
    res.status(500).json({ error: 'Failed to update product field' });
  }
});

// === BULK DELETE (by company or job) với Individual Tracking ===
app.delete('/api/companies/:companyId/extracted-data', async (req, res) => {
  try {
    const { companyId } = req.params;
    
    // 1. Get all products và services cho company
    const products = await db.extracted_products.findAll({
      where: { company_id: companyId }
    });
    const services = await db.extracted_services.findAll({
      where: { company_id: companyId }
    });
    
    // 2. Collect all Qdrant point IDs từ individual records
    const allQdrantPointIds = [];
    const productDetails = [];
    const serviceDetails = [];
    
    products.forEach(product => {
      const pointIds = JSON.parse(product.qdrant_point_ids || '[]');
      allQdrantPointIds.push(...pointIds);
      productDetails.push({
        id: product.id,
        name: product.name,
        points_count: pointIds.length
      });
    });
    
    services.forEach(service => {
      const pointIds = JSON.parse(service.qdrant_point_ids || '[]');
      allQdrantPointIds.push(...pointIds);
      serviceDetails.push({
        id: service.id,
        name: service.name,
        points_count: pointIds.length
      });
    });
    
    // 3. Bulk delete từ Qdrant
    if (allQdrantPointIds.length > 0) {
      await qdrant.delete('multi_company_data', {
        points: allQdrantPointIds
      });
      console.log(`🗑️ Bulk deleted ${allQdrantPointIds.length} Qdrant points for company ${companyId}`);
    }
    
    // 4. Bulk delete từ database
    await db.extracted_products.destroy({
      where: { company_id: companyId }
    });
    await db.extracted_services.destroy({
      where: { company_id: companyId }
    });
    
    res.json({
      success: true,
      message: 'All extracted data deleted successfully',
      deleted_summary: {
        products: {
          count: products.length,
          details: productDetails
        },
        services: {
          count: services.length,
          details: serviceDetails
        },
        total_qdrant_points_deleted: allQdrantPointIds.length
      }
    });
    
  } catch (error) {
    console.error('Failed to bulk delete extracted data:', error);
    res.status(500).json({ error: 'Failed to bulk delete extracted data' });
  }
});
```

#### 4. **Search với Individual Product/Service Mapping**

```javascript
// === SEARCH với Individual Product/Service Resolution ===
app.get('/api/companies/:companyId/search', async (req, res) => {
  try {
    const { companyId } = req.params;
    const { query, limit = 10, type = 'all' } = req.query; // type: 'products', 'services', 'all'
    
    // 1. Search Qdrant với filters
    const filters = {
      must: [
        { key: 'company_id', match: { value: companyId } }
      ]
    };
    
    // Filter by content type if specified
    if (type === 'products') {
      filters.must.push({ key: 'content_type', match: { value: 'extracted_product' } });
    } else if (type === 'services') {
      filters.must.push({ key: 'content_type', match: { value: 'extracted_service' } });
    } else {
      filters.must.push({ 
        key: 'content_type', 
        match: { any: ['extracted_product', 'extracted_service'] } 
      });
    }
    
    const searchResults = await qdrant.search('multi_company_data', {
      vector: await generateEmbedding(query),
      filter: filters,
      limit: limit * 5, // Get more results để aggregate by product/service
      with_payload: true,
      score_threshold: 0.7 // Only high-relevance results
    });
    
    // 2. Group search results by individual product/service IDs
    const productMatches = new Map(); // productId -> {chunks: [], maxScore: number}
    const serviceMatches = new Map(); // serviceId -> {chunks: [], maxScore: number}
    
    searchResults.forEach(result => {
      const payload = result.payload;
      const score = result.score;
      
      if (payload.content_type === 'extracted_product') {
        const productId = payload.product_id;
        if (!productMatches.has(productId)) {
          productMatches.set(productId, { chunks: [], maxScore: score });
        }
        productMatches.get(productId).chunks.push({
          content: payload.content,
          score: score,
          chunk_index: payload.chunk_index
        });
        // Update max score
        if (score > productMatches.get(productId).maxScore) {
          productMatches.get(productId).maxScore = score;
        }
      } else if (payload.content_type === 'extracted_service') {
        const serviceId = payload.service_id;
        if (!serviceMatches.has(serviceId)) {
          serviceMatches.set(serviceId, { chunks: [], maxScore: score });
        }
        serviceMatches.get(serviceId).chunks.push({
          content: payload.content,
          score: score,
          chunk_index: payload.chunk_index
        });
        if (score > serviceMatches.get(serviceId).maxScore) {
          serviceMatches.get(serviceId).maxScore = score;
        }
      }
    });
    
    // 3. Get complete database records cho matched products/services
    const productIds = Array.from(productMatches.keys());
    const serviceIds = Array.from(serviceMatches.keys());
    
    const products = await db.extracted_products.findAll({
      where: { id: productIds },
      include: [{
        model: db.extraction_jobs,
        as: 'job',
        attributes: ['task_id', 'file_name', 'submitted_at']
      }]
    });
    
    const services = await db.extracted_services.findAll({
      where: { id: serviceIds },
      include: [{
        model: db.extraction_jobs,
        as: 'job', 
        attributes: ['task_id', 'file_name', 'submitted_at']
      }]
    });
    
    // 4. Combine database records với search scores và rank by relevance
    const productResults = products.map(product => ({
      ...product.toJSON(),
      search_info: {
        max_score: productMatches.get(product.id).maxScore,
        chunks_matched: productMatches.get(product.id).chunks.length,
        best_matching_chunks: productMatches.get(product.id).chunks
          .sort((a, b) => b.score - a.score)
          .slice(0, 2) // Top 2 matching chunks
      }
    })).sort((a, b) => b.search_info.max_score - a.search_info.max_score);
    
    const serviceResults = services.map(service => ({
      ...service.toJSON(),
      search_info: {
        max_score: serviceMatches.get(service.id).maxScore,
        chunks_matched: serviceMatches.get(service.id).chunks.length,
        best_matching_chunks: serviceMatches.get(service.id).chunks
          .sort((a, b) => b.score - a.score)
          .slice(0, 2)
      }
    })).sort((a, b) => b.search_info.max_score - a.search_info.max_score);
    
    // 5. Apply final limit và combine results
    const finalProducts = productResults.slice(0, type === 'services' ? 0 : Math.ceil(limit / 2));
    const finalServices = serviceResults.slice(0, type === 'products' ? 0 : Math.floor(limit / 2));
    
    res.json({
      success: true,
      search_query: query,
      search_type: type,
      results: {
        products: finalProducts,
        services: finalServices,
        total_products_found: productResults.length,
        total_services_found: serviceResults.length,
        returned_products: finalProducts.length,
        returned_services: finalServices.length
      },
      search_metadata: {
        qdrant_raw_matches: searchResults.length,
        unique_products_matched: productMatches.size,
        unique_services_matched: serviceMatches.size,
        score_threshold: 0.7,
        company_id: companyId
      }
    });
    
  } catch (error) {
    console.error('Search failed:', error);
    res.status(500).json({ error: 'Search failed' });
  }
});

// === ADVANCED SEARCH với Filters ===
app.post('/api/companies/:companyId/search/advanced', async (req, res) => {
  try {
    const { companyId } = req.params;
    const {
      query,
      filters = {},
      limit = 10,
      include_chunks = false
    } = req.body;
    
    // Build dynamic Qdrant filters
    const qdrantFilters = {
      must: [
        { key: 'company_id', match: { value: companyId } }
      ]
    };
    
    // Add content type filter
    if (filters.content_type) {
      qdrantFilters.must.push({
        key: 'content_type',
        match: { value: filters.content_type }
      });
    }
    
    // Add product/service type filter (e.g., "Bảo hiểm sức khỏe")
    if (filters.product_type) {
      qdrantFilters.must.push({
        key: 'product_type',
        match: { value: filters.product_type }
      });
    }
    
    if (filters.service_type) {
      qdrantFilters.must.push({
        key: 'service_type', 
        match: { value: filters.service_type }
      });
    }
    
    const searchResults = await qdrant.search('multi_company_data', {
      vector: await generateEmbedding(query),
      filter: qdrantFilters,
      limit: limit * 3,
      with_payload: true,
      score_threshold: 0.6
    });
    
    // Process results same as basic search but with filters applied
    // ... (same grouping and database mapping logic) ...
    
    res.json({
      success: true,
      advanced_search: true,
      filters_applied: filters,
      // ... results ...
    });
    
  } catch (error) {
    console.error('Advanced search failed:', error);
    res.status(500).json({ error: 'Advanced search failed' });
  }
});
```

#### 5. **Consistency Check Tools**

```javascript
// === VERIFY Qdrant-Database Consistency ===
app.get('/api/admin/verify-qdrant-consistency/:companyId', async (req, res) => {
  try {
    const { companyId } = req.params;
    
    // 1. Get all database records
    const products = await db.extracted_products.findAll({
      where: { company_id: companyId }
    });
    const services = await db.extracted_services.findAll({
      where: { company_id: companyId }
    });
    
    // 2. Check Qdrant points existence
    const inconsistencies = [];
    
    for (const product of products) {
      const qdrantPointIds = JSON.parse(product.qdrant_point_ids || '[]');
      
      for (const pointId of qdrantPointIds) {
        try {
          await qdrant.retrieve('multi_company_data', { ids: [pointId] });
        } catch (error) {
          inconsistencies.push({
            type: 'missing_qdrant_point',
            record_type: 'product',
            record_id: product.id,
            missing_point_id: pointId
          });
        }
      }
    }
    
    // Same check for services...
    
    res.json({
      success: true,
      company_id: companyId,
      total_products: products.length,
      total_services: services.length,
      inconsistencies: inconsistencies,
      is_consistent: inconsistencies.length === 0
    });
    
  } catch (error) {
    console.error('Consistency check failed:', error);
    res.status(500).json({ error: 'Consistency check failed' });
  }
});
```

---

## 🔒 Webhook Authentication

### Implement Webhook Authentication Middleware:

```javascript
// Webhook authentication middleware
const crypto = require('crypto');

function webhookAuth(req, res, next) {
  try {
    const signature = req.headers['x-webhook-signature'];
    const webhookSecret = process.env.WEBHOOK_SECRET;
    
    if (!signature || !webhookSecret) {
      return res.status(401).json({ error: 'Missing webhook signature or secret' });
    }
    
    // Extract signature from "sha256=..." format
    const receivedSignature = signature.replace('sha256=', '');
    
    // Calculate expected signature
    const payload = JSON.stringify(req.body, null, 0);
    const expectedSignature = crypto
      .createHmac('sha256', webhookSecret)
      .update(payload, 'utf8')
      .digest('hex');
    
    // Compare signatures securely
    if (!crypto.timingSafeEqual(
      Buffer.from(receivedSignature, 'hex'),
      Buffer.from(expectedSignature, 'hex')
    )) {
      return res.status(401).json({ error: 'Invalid webhook signature' });
    }
    
    next();
  } catch (error) {
    console.error('Webhook authentication failed:', error);
    return res.status(401).json({ error: 'Webhook authentication failed' });
  }
}

// Usage in routes
app.post('/api/webhooks/file-processed', webhookAuth, async (req, res) => {
  // Handler implementation...
});

app.post('/api/webhooks/ai/extraction-callback', webhookAuth, async (req, res) => {
  // Handler implementation...
});
```

---

## 🔍 Debugging & Testing

### Test Webhook Endpoints với Full Data:

```bash
# Test AI extraction callback với full structured data
curl -X POST https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=your_signature_here" \
  -d '{
    "task_id": "test-task-123",
    "company_id": "test-company",
    "status": "completed", 
    "processing_time": 15.5,
    "timestamp": "2025-07-27T07:30:00.123Z",
    "results": {
      "products_count": 2,
      "services_count": 1,
      "total_items": 3,
      "ai_provider": "gemini",
      "template_used": "InsuranceExtractionTemplate"
    },
    "raw_content": "Full original file content here...",
    "structured_data": {
      "products": [
        {
          "name": "Test Product",
          "type": "Insurance",
          "description": "Test description",
          "premium": "1000 USD/year"
        }
      ],
      "services": [
        {
          "name": "Test Service", 
          "type": "Support",
          "description": "Test service description"
        }
      ]
    }
  }'

# Test file upload callback với raw content
curl -X POST https://api.agent8x.io.vn/api/webhooks/file-processed \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=your_signature_here" \
  -d '{
    "event": "file.uploaded",
    "companyId": "test-company",
    "data": {
      "fileId": "test-file-123",
      "status": "completed",
      "chunksCreated": 5,
      "processingTime": 3.2,
      "tags": ["test", "company-info"],
      "raw_content": "Complete file content here...",
      "file_metadata": {
        "original_name": "test_file.pdf",
        "file_size": 1024000,
        "file_type": "application/pdf"
      }
    },
    "timestamp": "2025-07-27T07:30:00.123Z"
  }'
```

### Verification Checklist:

#### ✅ File Upload Workflow:
- [ ] Backend receives callback tại `/api/webhooks/file-processed`
- [ ] Callback có đầy đủ fields: `event`, `companyId`, `data`, `timestamp`
- [ ] `data.status` là `completed` hoặc `failed`  
- [ ] Với success: có `raw_content` (full file content), `chunksCreated`, `file_metadata`
- [ ] Với error: có `error` message chi tiết và partial `raw_content` nếu có
- [ ] Webhook signature verification works với `X-Webhook-Signature`
- [ ] Database lưu được complete file record với raw content

#### ✅ AI Extraction Workflow:
- [ ] Backend receives callback tại `/api/webhooks/ai/extraction-callback`
- [ ] Callback có đầy đủ fields: `task_id`, `company_id`, `status`, `timestamp`
- [ ] Với success: có `raw_content` (complete original text), `structured_data` (full products/services), `results`, `extraction_metadata`
- [ ] Với error: có `error` message chi tiết
- [ ] `structured_data.products[]` chứa tất cả product details (name, type, description, coverage_period, premium, v.v.)
- [ ] `structured_data.services[]` chứa tất cả service details (name, type, description, pricing, availability)
- [ ] Database lưu được individual products và services từ structured_data
- [ ] Response time từ backend < 5 seconds

#### ✅ Security & Authentication:
- [ ] Webhook signature verification hoạt động correctly
- [ ] `WEBHOOK_SECRET` được configured properly
- [ ] Timestamps được validate để prevent replay attacks
- [ ] Error handling không expose sensitive information

#### ✅ Database Integration:
- [ ] All required tables created (uploaded_files, extraction_jobs, extracted_products, extracted_services, file_tags)
- [ ] Raw content được stored completely cho both workflows
- [ ] Individual products/services được parsed và stored đúng cách
- [ ] Company file counts được updated
- [ ] Tags được indexed properly for search

---

## 🚨 Troubleshooting

### Common Issues:

1. **Callback không nhận được**:
   - Kiểm tra URL có accessible từ AI service không
   - Verify firewall/security groups
   - Check HTTP vs HTTPS

2. **Callback timeout**:
   - Backend phải response trong < 30 seconds  
   - Return `200 OK` ngay lập tức, process async nếu cần

3. **Callback format sai**:
   - Ensure Content-Type là `application/json`
   - Validate JSON payload structure

4. **Duplicate callbacks**:
   - AI service có thể retry nếu không nhận được 200 OK
   - Backend cần handle idempotency với `task_id` hoặc `fileId`

---

## 📝 Summary

**Đã implement đầy đủ cả 2 loại callback:**

1. ✅ **File Upload Callback** (`/api/webhooks/file-processed`)
   - Raw content processing notifications
   - Success/error status với metadata

2. ✅ **AI Extraction Callback** (`/api/webhooks/ai/extraction-callback`) 
   - Structured data extraction notifications
   - Products/services count và AI metadata

**Backend cần implement 2 webhook endpoints tương ứng để nhận notifications và update database status accordingly.**

**Next Steps:**
1. Backend implement 2 webhook handlers theo examples trên
2. Test với curl commands để verify
3. Update frontend để show real-time status updates
