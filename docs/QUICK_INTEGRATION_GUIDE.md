# Quick Integration Guide: Async Document Extraction

## TL;DR cho Backend Developer

### 1. Submit File cho AI Extraction
```javascript
const response = await fetch('/api/extract/process-async', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    r2_url: "https://static.agent8x.io.vn/company/abc/files/document.txt",
    company_id: "company-123",
    industry: "insurance",
    data_type: "auto",
    file_name: "document.txt",
    file_size: 1024000,
    file_type: "text/plain"
  })
});

const { task_id } = await response.json();
// Response in ~0.04s: { task_id: "extract_xxx", estimated_processing_time: "15-25 seconds" }
```

### 2. Monitor Progress
```javascript
async function waitForResults(task_id) {
  while (true) {
    const status = await fetch(`/api/extract/status/${task_id}`);
    const data = await status.json();
    
    if (data.status === 'completed') {
      return await fetch(`/api/extract/result/${task_id}`).then(r => r.json());
    } else if (data.status === 'failed') {
      throw new Error('Extraction failed');
    }
    
    await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2s
  }
}
```

### 3. Parse Results để lưu Database
```javascript
const results = await waitForResults(task_id);

// Lưu job info
await db.extraction_jobs.create({
  task_id: results.task_id,
  company_id: company_id,
  processing_time: results.processing_time,
  total_items: results.total_items_extracted,
  ai_provider: results.ai_provider,
  status: 'completed'
});

// Lưu products
for (const product of results.structured_data.products) {
  await db.products.create({
    job_id: job.id,
    name: product.name,
    type: product.type,
    description: product.description,
    premium: product.premium,
    conditions: product.conditions
  });
}

// Lưu services  
for (const service of results.structured_data.services) {
  await db.services.create({
    job_id: job.id,
    name: service.name,
    type: service.type,
    description: service.description,
    pricing: service.pricing
  });
}
```

## Example Response Structure

### Queue Response (0.04s)
```json
{
  "task_id": "extract_d4f2a891-c3b2-4e6f-8a9d-1b2c3d4e5f6g",
  "estimated_processing_time": "15-25 seconds"
}
```

### Final Results (~20s sau)
```json
{
  "success": true,
  "processing_time": 19.83,
  "total_items_extracted": 5,
  "ai_provider": "gemini",
  "structured_data": {
    "products": [
      {
        "name": "AIA – Khỏe Trọn Vẹn",
        "type": "Bảo hiểm liên kết chung", 
        "description": "Bảo vệ tài chính trước rủi ro...",
        "premium": "Tùy thuộc vào tuổi, giới tính...",
        "conditions": "Tùy sản phẩm, yêu cầu sức khỏe..."
      }
    ],
    "services": [
      {
        "name": "AIA Vitality",
        "type": "Chương trình ưu đãi",
        "description": "Chương trình AIA Vitality...",
        "pricing": "Tích hợp vào các sản phẩm bảo hiểm"
      }
    ]
  }
}
```

## Performance 
- **Queue time**: 0.03-0.04s ⚡
- **AI processing**: 18-22s 🤖  
- **Total**: ~22s ✅
- **Success rate**: >95% 🎯

## Error Handling
```javascript
try {
  const results = await waitForResults(task_id);
  await saveToDatabase(results);
} catch (error) {
  await markJobAsFailed(task_id, error.message);
}
```

## Test Script
```bash
python test_realtime_async.py
# Output: async_workflow_complete_test_YYYYMMDD_HHMMSS.json
```

Xem file đầy đủ: `docs/ASYNC_EXTRACTION_API_GUIDE.md`
