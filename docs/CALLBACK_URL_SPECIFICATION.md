# 📞 CALLBACK URL SPECIFICATION - AI Service to Backend
# Đặc tả URL Callback - Từ AI Service về Backend

## 🎯 Overview / Tổng quan

AI Service có **2 luồng xử lý bất đồng bộ** khác### 🔐 Headers (Thực tế từ DocumentProcessingWorker)
```

Content-Type: application/json
X-Webhook-Source: ai-service  
X-Webhook-Signature: sha256=44cbf92ddcfb7a9d4c30fb2be77f6e5d2a6aa747d1e381cdeca8d3bcba9b0af1
User-Agent: Agent8x-AI-Service/1.0
Accept: */*
Accept-Encoding: gzip, deflate, br
Content-Length: 3705
```luồng cần **callback URL riêng biệt** để thông báo kết quả về backend:

1. **🔧 `/upload` Flow**: Xử lý file upload đơn giản → Trả về **RAW CONTENT** only
2. **🤖 `/process-async` Flow**: Xử lý AI extraction phức tạp → Trả về **STRUCTURED DATA** + RAW CONTENT

---

## 📄 1. UPLOAD WORKFLOW CALLBACK

### 🔗 Backend Callback URL
```
https://api.agent8x.io.vn/api/webhooks/file-processed
```

### 📋 Endpoint trong Backend
```typescript
POST /api/webhooks/file-processed
```

### 📊 Payload Structure (RAW CONTENT ONLY) - THỰC TẾ TỪ WORKER
```json
{
  "task_id": "54955ac7-0ab9-4418-b3b0-5436f09b5a06",
  "status": "completed",
  "timestamp": "2025-07-28T20:23:31.235375",
  "data": {
    "task_id": "54955ac7-0ab9-4418-b3b0-5436f09b5a06",
    "company_id": "5a44b799-4783-448f-b6a8-b9a51ed7ab76",
    "status": "completed",
    "success": true,
    "processing_time": 14.225093841552734,
    "timestamp": "2025-07-28T20:23:31.234924",
    
    // ✅ RAW CONTENT ONLY - Nội dung đã trích xuất từ DOCX file thực tế
    "raw_content": "THÔNG TIN CƠ BẢN VỀ AIA TOÀN CẦU VÀ AIA VIỆT NAM (CẬP NHẬT 2025)\nI. AIA TOÀN CẦU (AIA GROUP LIMITED)\n1. Giới thiệu chung:\n- Tên đầy đủ: AIA Group Limited\n- Thành lập: Năm 1919 tại Thượng Hải, Trung Quốc\n- Trụ sở chính: Central, Hồng Kông\n- Niêm yết: Sàn chứng khoán Hồng Kông (HKEX) - mã cổ phiếu: 1299.HK\n\n2. Quy mô & kết quả tài chính (Q1/2025):\n- VONB đạt 1,497 triệu USD (tăng 13% so với cùng kỳ)\n- ANP đạt 2,617 triệu USD (tăng 7%)\n- VONB margin: 57.5%\n- NB CSM: tăng 16%\n- Tổng tài sản: >330 tỷ USD\n\n3. Chiến lược & hoạt động:\n- Mạnh ở kênh Premier Agency và bancassurance\n- Mở rộng thị trường tại Trung Quốc đại lục (Anhui, Shandong)\n- Mua lại cổ phiếu trị giá 1,6 tỷ USD\n\n4. Đầu tư & an toàn tài chính:\n- Tỷ lệ nợ dưới chuẩn: chỉ 2% (~3.2 tỷ USD)\n- Dự phòng ECL ước tính 463 triệu USD\nII. AIA VIỆT NAM\n1. Giới thiệu:\n- Thành lập: Năm 2000\n- Vốn điều lệ: >5.500 tỷ đồng\n- Trụ sở: Saigon Centre, Quận 1, TP.HCM\n\n2. Quy mô hoạt động (2025):\n- Hơn 1,6 triệu hợp đồng bảo hiểm đang phục vụ\n- 200+ văn phòng và trung tâm dịch vụ\n- 27.000+ đại lý trên toàn quốc\n\n3. Tài chính & chi trả:\n- Tổng tài sản: ~67.557 tỷ VND (~2,7 tỷ USD)\n- Tỷ lệ dự phòng thanh khoản: 191%\n- Chi trả quyền lợi bảo hiểm cộng dồn: >15.000 tỷ VND\n\n4. Sản phẩm & công nghệ:\n- AIA Vitality: kết hợp chăm sóc sức khỏe\n- MyAIA, iClaim, iPoS: xử lý hợp đồng và bồi thường online\n- Gói bảo hiểm \"Bung Gia Lực\", \"Uplift Your Life 10+\"\n\n5. Giải thưởng:\n- Golden Dragon Awards 2025\n- Insurance Asia Awards 2023: Health Initiative of the Year\n- Asian Technology Excellence Awards: Cloud Life Insurance\n\n6. CSR & hoạt động cộng đồng:\n- AIA Pink Journey: tầm soát ung thư vú cho phụ nữ Việt Nam\n- Hướng tới 30.000 người thụ hưởng đến 2030",
    
    "file_processing": {
      "ai_provider": "simple_text_extraction",
      "extraction_type": "raw_text_only",
      "file_name": "company-profile.docx",
      "content_length": 1701,
      "processing_method": "document_upload_workflow"
    },
    
    "file_metadata": {
      "original_name": "company-profile.docx",
      "file_size": 250000,
      "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "data_type": "document",
      "industry": "Industry.INSURANCE",
      "language": "Language.VIETNAMESE"
    }
  }
}
```

### ❌ Error Payload (Upload Failed)
```json
{
  "task_id": "doc_worker_1722159487_12345",
  "status": "failed",
  "timestamp": "2025-07-28T10:30:45.123Z",
  "data": {
    "task_id": "doc_worker_1722159487_12345", 
    "company_id": "company_123",
    "status": "failed",
    "success": false,
    "processing_time": 5.23,
    "timestamp": "2025-07-28T10:30:45.123Z",
    "error": "Failed to extract content from PDF file",
    "error_details": {
      "workflow": "document_upload",
      "step": "content_extraction", 
      "timestamp": "2025-07-28T10:30:45.123Z"
    }
  }
}
```

---

## 🤖 2. AI EXTRACTION WORKFLOW CALLBACK  

### 🔗 Backend Callback URL
```
https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback
```

### 📋 Endpoint trong Backend  
```typescript
POST /api/webhooks/ai/extraction-callback
```

### 📊 Payload Structure (STRUCTURED DATA + RAW CONTENT)
```json
{
  "task_id": "storage_hybrid_extract_1753701221742_6ccc00e6",
  "status": "completed",
  "company_id": "aia-test-company-hybrid",
  "timestamp": "2025-07-28T18:14:10.257689",
  
  // ✅ RAW CONTENT - Nội dung gốc được trích xuất từ file
  "raw_content": "--- DỊCH VỤ AIA VIỆT NAM (25/7/2025) – CHI TIẾT QUYỀN LỢI – PHÍ – ĐIỀU KIỆN ---\n\n1. AIA – Khỏe Trọn Vẹn (Bảo hiểm liên kết chung)...",
  
  // ✅ STRUCTURED DATA - Products và Services với Qdrant IDs
  "structured_data": {
    "products": [
      {
        "name": "AIA – Khỏe Trọn Vẹn",
        "qdrant_point_id": "6a7fd65f-1e06-494a-bc37-d23d2433d3d8",
        "category": "bao_hiem",
        "original_data": {
          "id": 1,
          "name": "AIA – Khỏe Trọn Vẹn",
          "description": "Bảo hiểm liên kết chung. Bảo vệ tài chính trước rủi ro tử vong...",
          "category": "bao_hiem",
          "sub_category": "bao_hiem_hon_hop",
          "tags": ["bao_hiem_doi_song", "bao_hiem_suc_khoe", "lien_ket_dau_tu"],
          "target_audience": ["gia_dinh", "nguoi_lao_dong", "nguoi_cao_tuoi"],
          "coverage_type": ["tu_vong", "thuong_tat", "benh_tat"],
          "content_for_embedding": "Bảo hiểm AIA – Khỏe Trọn Vẹn...",
          "premium": null,
          "currency": null
        }
      },
      {
        "name": "Bảo hiểm Toàn diện Bệnh hiểm nghèo 2.0",
        "qdrant_point_id": "af059fcc-7812-4404-9afb-63c8761703ff",
        "category": "bao_hiem",
        "original_data": {
          "id": 2,
          "name": "Bảo hiểm Toàn diện Bệnh hiểm nghèo 2.0",
          "description": "Bảo vệ trước 107 bệnh hiểm nghèo...",
          "category": "bao_hiem",
          "sub_category": "bao_hiem_suc_khoe",
          "tags": ["benh_hiem_ngheo", "toan_dien", "bao_ve_suc_khoe"],
          "target_audience": ["gia_dinh", "ca_nhan"],
          "coverage_type": ["benh_tat"],
          "content_for_embedding": "Bảo hiểm Toàn diện Bệnh hiểm nghèo 2.0...",
          "premium": null,
          "currency": null
        }
      }
    ],
    "services": []
  },
  
  // ✅ EXTRACTION METADATA với thông tin xử lý
  "extraction_metadata": {
    "callback_url": "http://localhost:8088/extraction-callback",
    "total_products_stored": 3,
    "total_services_stored": 0,
    "storage_strategy": "individual_qdrant_points",
    "processed_by": "worker_2_storage_callback"
  }
}
```

### ❌ Error Payload (AI Extraction Failed)
```json
{
  "task_id": "storage_hybrid_extract_1753701221742_6ccc00e6",
  "status": "failed",
  "company_id": "aia-test-company-hybrid",
  "timestamp": "2025-07-28T18:14:10.257689",
  "error": "AI extraction service unavailable",
  "extraction_metadata": {
    "callback_url": "http://localhost:8088/extraction-callback",
    "processed_by": "worker_2_storage_callback"
  }
}
```

---

## 🔐 3. WEBHOOK SECURITY

### � Headers (Thực tế từ Worker 2)
```
Host: localhost:8088
Content-Type: application/json
X-Webhook-Source: ai-service  
X-Webhook-Signature: sha256=e08312ebf89e89b01e535473118b3f655f0976ac18e0e8af2faa057579276194
User-Agent: Agent8x-AI-Service/1.0
Accept: */*
Accept-Encoding: gzip, deflate, br
Content-Length: 12679
```

### 🔒 Signature Verification
```typescript
// Backend cần verify signature 
const signature = req.headers['x-webhook-signature'];
const expectedSignature = 'sha256=' + 
  crypto.createHmac('sha256', WEBHOOK_SECRET)
    .update(JSON.stringify(req.body, null, 0))
    .digest('hex');

if (signature !== expectedSignature) {
  throw new Error('Invalid webhook signature');
}
```

---

## 🛠️ 4. BACKEND IMPLEMENTATION

### 📁 File Upload Callback Handler
```typescript
// /api/webhooks/file-processed
export async function handleFileProcessedCallback(req: Request, res: Response) {
  try {
    // Verify webhook signature
    verifyWebhookSignature(req);
    
    const { task_id, status, data } = req.body;
    
    if (status === 'completed') {
      // ✅ File upload thành công - chỉ có raw content
      const { raw_content, file_processing, file_metadata } = data;
      
      // Update file record in database
      await updateFileRecord(task_id, {
        status: 'processed',
        raw_content: raw_content,
        processing_method: file_processing.processing_method, // "document_upload_workflow"
        ai_provider: file_processing.ai_provider, // "simple_text_extraction"
        extraction_type: file_processing.extraction_type, // "raw_text_only"
        content_length: file_processing.content_length, // 1701
        file_name: file_processing.file_name, // "company-profile.docx"
        original_name: file_metadata.original_name,
        file_type: file_metadata.file_type,
        industry: file_metadata.industry, // 
        language: file_metadata.language, // "Language.vi"
        processing_time: data.processing_time // 14.225093841552734
      });
      
      // Notify frontend via WebSocket/SSE
      notifyFileProcessingComplete(data.company_id, task_id, {
        content_length: file_processing.content_length,
        ai_provider: file_processing.ai_provider,
        processing_time: data.processing_time
      });
      
    } else if (status === 'failed') {
      // ❌ File upload thất bại  
      await updateFileRecord(task_id, {
        status: 'failed',
        error: data.error
      });
    }
    
    res.status(200).json({ received: true });
  } catch (error) {
    console.error('File callback error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
}
```

### 🤖 AI Extraction Callback Handler
```typescript  
// /api/webhooks/ai/extraction-callback
export async function handleExtractionCallback(req: Request, res: Response) {
  try {
    // Verify webhook signature
    verifyWebhookSignature(req);
    
    const { task_id, status, company_id, structured_data, raw_content, extraction_metadata } = req.body;
    
    if (status === 'completed') {
      // ✅ AI extraction thành công - có structured data + raw content
      const products = structured_data?.products || [];
      const services = structured_data?.services || [];
      
      // Save extraction results to database
      await saveExtractionResults(task_id, {
        company_id: company_id,
        raw_content: raw_content,
        structured_data: structured_data,
        products_count: products.length,
        services_count: services.length,
        total_products_stored: extraction_metadata.total_products_stored,
        total_services_stored: extraction_metadata.total_services_stored,
        storage_strategy: extraction_metadata.storage_strategy,
        processed_by: extraction_metadata.processed_by
      });
      
      // Process individual items with Qdrant IDs for CRUD operations
      for (const product of products) {
        await saveProductWithQdrantId(company_id, {
          name: product.name,
          category: product.category,
          qdrant_point_id: product.qdrant_point_id, // Critical for deletion
          original_data: product.original_data // Full AI extracted data
        });
      }
      
      for (const service of services) {
        await saveServiceWithQdrantId(company_id, {
          name: service.name,
          category: service.category,
          qdrant_point_id: service.qdrant_point_id, // Critical for deletion
          original_data: service.original_data // Full AI extracted data
        });
      }
      
      // Update company knowledge base stats
      await updateCompanyKnowledgeBase(company_id, {
        total_products: extraction_metadata.total_products_stored,
        total_services: extraction_metadata.total_services_stored,
        last_extraction: new Date(),
        storage_strategy: extraction_metadata.storage_strategy
      });
      
      // Notify frontend 
      notifyExtractionComplete(company_id, task_id, {
        products_count: products.length,
        services_count: services.length,
        total_stored: extraction_metadata.total_products_stored + extraction_metadata.total_services_stored
      });
      
    } else if (status === 'failed') {
      // ❌ AI extraction thất bại
      await updateExtractionStatus(task_id, 'failed', req.body.error);
    }
    
    res.status(200).json({ received: true });
  } catch (error) {
    console.error('Extraction callback error:', error);  
    res.status(500).json({ error: 'Internal server error' });
  }
}
```

---

## 📚 5. USAGE EXAMPLES

### 🔧 Frontend gọi Upload API
```typescript
// 1. Upload file (Raw content only)
const uploadResponse = await fetch('/api/admin/companies/123/files/upload', {
  method: 'POST',
  body: JSON.stringify({
    r2_url: 'https://pub-xyz.r2.dev/file.pdf',
    data_type: 'document', 
    industry: 'REAL_ESTATE',
    metadata: { /* file info */ },
    callback_url: 'https://api.agent8x.io.vn/api/webhooks/file-processed' // ✅ Upload callback URL
  })
});

// Backend sẽ nhận callback tại /api/webhooks/file-processed với raw content
```

### 🤖 Frontend gọi AI Extraction API  
```typescript
// 2. AI Extraction (Structured data + raw content)
const extractResponse = await fetch('/api/extract/process-async', {
  method: 'POST',
  body: JSON.stringify({
    r2_url: 'https://pub-xyz.r2.dev/menu.pdf',
    company_id: 'restaurant_123',
    industry: 'RESTAURANT',
    file_name: 'menu.pdf',
    language: 'vi', // ✅ Language code: 'vi', 'en', 'auto'
    target_categories: ['products', 'services'],
    callback_url: 'https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback' // ✅ AI callback URL  
  })
});

// Backend sẽ nhận callback tại /api/webhooks/ai/extraction-callback với structured data + raw content
```

---

## ✅ 6. SUMMARY / TÓM TẮT

| Workflow | Callback URL | Payload Content | Use Case |
|----------|-------------|-----------------|----------|
| **📄 /upload** | `/api/webhooks/file-processed` | **RAW CONTENT** only | Simple file upload & indexing |  
| **🤖 /process-async** | `/api/webhooks/ai/extraction-callback` | **STRUCTURED DATA** + RAW CONTENT + **QDRANT IDs** | AI-powered data extraction with individual item storage |

### 🎯 Key Differences / Điểm khác biệt chính:

1. **📄 Upload Callback**: 
   - **Content**: Chỉ có `raw_content` từ simple text extraction
   - **AI Provider**: 
   - **Processing**: DocumentProcessingWorker với `document_upload_workflow`
   - **Use Case**: File upload đơn giản, indexing và search cơ bản

2. **🤖 Extraction Callback**: 
   - **Content**: `structured_data` với `qdrant_point_id` cho từng item + `raw_content`
   - **AI Provider**: ChatGPT/Gemini với template-based extraction
   - **Processing**: ExtractionProcessingWorker với AI-powered analysis
   - **Use Case**: AI chatbot, advanced search và **individual CRUD operations**

### 🔑 Critical Fields cho Backend:

#### ✅ File Upload Workflow (Thực tế từ DocumentProcessingWorker):
- **`raw_content`**: Nội dung text đầy đủ được extract từ DOCX file (1701 chars)
- **`file_processing.ai_provider`**: "simple_text_extraction" (không phải ChatGPT/Gemini)
- **`file_processing.extraction_type`**: "raw_text_only" 
- **`file_processing.processing_method`**: "document_upload_workflow"
- **`file_processing.content_length`**: Độ dài thực tế của raw content
- **`file_metadata.industry`**: Format "Industry.INSURANCE" (enum string)
- **`file_metadata.language`**: Format "Language.VIETNAMESE" (enum string)
- **`processing_time`**: Thời gian xử lý thực tế (14.225 seconds cho DOCX file)

#### ✅ Individual Item Management:
- **`qdrant_point_id`**: UUID để xóa/update specific item trong Qdrant
- **`original_data`**: Full AI extracted data cho từng product/service
- **`category`**: AI categorized category cho filtering

#### ✅ Storage Summary:
- **`total_products_stored`**: Số products đã lưu thành công vào Qdrant
- **`total_services_stored`**: Số services đã lưu thành công vào Qdrant
- **`storage_strategy`**: "individual_qdrant_points" - mỗi item = 1 point

### 🚨 Backend Implementation Notes:

1. **CRUD Operations**: Sử dụng `qdrant_point_id` để delete specific items:
   ```typescript
   async function deleteProductFromQdrant(qdrantPointId: string) {
     await qdrantService.deletePoint("multi_company_data", qdrantPointId);
   }
   ```

2. **Data Structure**: `structured_data.products[].original_data` chứa full AI data:
   ```typescript
   const aiExtractedData = product.original_data; // All AI fields: tags, target_audience, etc.
   ```

3. **Validation**: Backend không cần validate structure - AI service đã xử lý raw data

### 🔒 Security: 
- Cả 2 callback đều có **webhook signature** để verify tính toàn vẹn
- Backend **PHẢI** verify signature trước khi xử lý

### 📡 Response:
- Backend **PHẢI** trả về HTTP 200 để AI service biết callback thành công
- Nếu callback fail, AI service sẽ log error nhưng không retry (by design)
