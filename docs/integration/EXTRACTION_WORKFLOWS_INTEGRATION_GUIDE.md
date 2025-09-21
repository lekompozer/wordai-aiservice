# File Upload Integration Guide - Extraction Workflows

## Overview

This document provides comprehensive integration guide for the AI Extraction Service with two distinct workflows:

1. **Sync Extraction** - Immediate processing with response (`/api/extract/process`)
2. **Async Extraction** - Queue-based processing with callback (`/api/extract/process-async`)

Both workflows now support **backend data type tracking** and **optimized chunking strategy**.

## Architecture Summary

```
Backend → AI Service → [Sync/Async] → AI Templates → Optimized Chunking → Qdrant
```

### Key Features
- ✅ **Backend Data Type Tracking** - Backend can specify exact data type (products/services/auto)
- ✅ **Inconsistency Detection** - Logs when data_type and target_categories don't match
- ✅ **Optimized Chunking** - Groups items by categories or minimum 20 items per chunk
- ✅ **Template-Based Extraction** - Industry-specific AI templates with JSON schemas
- ✅ **AI Provider Selection** - Automatic provider selection (ChatGPT/Gemini)
- ✅ **Queue-Based Processing** - Redis queue with async worker processing
- ✅ **Comprehensive Logging** - Detailed tracking for backend requests

---

## Workflow 1: Sync Extraction (Immediate Response)

### Endpoint
```
POST /api/extract/process
```

### Use Case
Backend needs immediate extraction results with full data processing.

### Request Model

```typescript
interface ExtractionRequest {
  // Required fields
  r2_url: string;                    // Public R2 URL of uploaded file
  company_id: string;               // Company ID for Qdrant storage
  industry: "insurance" | "banking" | "restaurant" | "hotel" | "other";
  
  // Backend tracking (NEW)
  data_type?: "products" | "services" | "auto";  // Backend data type specification
  target_categories?: string[];                   // ["products", "services"]
  
  // File metadata
  file_metadata: {
    original_name: string;
    file_size: number;
    file_type: string;
    uploaded_at: string;
  };
  
  // Processing options
  language?: "vi" | "en";
  upload_to_qdrant?: boolean;       // Whether to upload to Qdrant
  callback_url?: string;            // Callback for async Qdrant upload
  company_info?: object;            // Optional company context
}
```

### Response Model

```typescript
interface ExtractionResponse {
  success: boolean;
  message: string;
  
  // Core results
  raw_content?: string;
  structured_data?: {
    products: Product[];
    services: Service[];
    extraction_summary: object;
  };
  
  // Processing metadata
  template_used?: string;
  ai_provider?: string;
  industry?: string;
  data_type?: string;
  processing_time?: number;
  total_items_extracted?: number;
  
  // Error handling
  error?: string;
  error_details?: object;
}
```

### Backend Implementation Example

```typescript
// Example 1: Products page upload
const extractProducts = async (fileUrl: string, companyId: string) => {
  const response = await fetch('/api/extract/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      r2_url: fileUrl,
      company_id: companyId,
      industry: 'insurance',
      data_type: 'products',           // Backend specifies exact type
      target_categories: ['products'], // Consistent with data_type
      file_metadata: {
        original_name: 'products.pdf',
        file_size: 1024000,
        file_type: 'application/pdf',
        uploaded_at: new Date().toISOString()
      },
      language: 'vi',
      upload_to_qdrant: true
    })
  });
  
  const result = await response.json();
  
  if (result.success) {
    console.log(`Extracted ${result.structured_data.products.length} products`);
    console.log(`Processing time: ${result.processing_time}s`);
    return result.structured_data.products;
  } else {
    throw new Error(result.error);
  }
};

// Example 2: Auto extraction (both products and services)
const extractAll = async (fileUrl: string, companyId: string) => {
  const response = await fetch('/api/extract/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      r2_url: fileUrl,
      company_id: companyId,
      industry: 'restaurant',
      data_type: 'auto',                      // Backend wants both types
      target_categories: ['products', 'services'],
      file_metadata: { /* ... */ },
      language: 'vi',
      upload_to_qdrant: true
    })
  });
  
  const result = await response.json();
  return {
    products: result.structured_data.products,
    services: result.structured_data.services
  };
};
```

---

## Workflow 2: Async Extraction (Queue-Based)

### Endpoint
```
POST /api/extract/process-async
```

### Use Case
Backend needs to upload large files without waiting for processing completion. Uses Redis queue + worker processing.

### Request Model

```typescript
interface ExtractionQueueRequest {
  // Required fields
  r2_url: string;
  company_id: string;
  industry: "insurance" | "banking" | "restaurant" | "hotel" | "other";
  
  // File metadata
  file_name: string;
  file_size?: number;
  file_type?: string;
  
  // Backend tracking (NEW)
  data_type?: "products" | "services" | "auto";
  target_categories?: string[];
  
  // Processing options
  language?: "vi" | "en";
  callback_url?: string;            // Required for notifications
  company_info?: object;
}
```

### Response Model

```typescript
interface ExtractionQueueResponse {
  success: boolean;
  task_id: string;                  // Unique task ID for tracking
  company_id: string;
  status: "queued" | "failed";
  message: string;
  estimated_time: number;           // Estimated processing time in seconds
  error?: string;
}
```

### Backend Implementation Example

```typescript
// Queue-based extraction
const queueExtraction = async (fileUrl: string, companyId: string) => {
  const response = await fetch('/api/extract/process-async', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      r2_url: fileUrl,
      company_id: companyId,
      industry: 'insurance',
      file_name: 'large_catalog.pdf',
      file_size: 5000000,
      file_type: 'application/pdf',
      data_type: 'products',
      target_categories: ['products'],
      language: 'vi',
      callback_url: 'https://your-backend.com/api/extraction-callback'
    })
  });
  
  const result = await response.json();
  
  if (result.success) {
    console.log(`Task queued: ${result.task_id}`);
    console.log(`Estimated time: ${result.estimated_time}s`);
    
    // Store task_id for tracking
    await saveTaskId(result.task_id, companyId);
    
    return result.task_id;
  } else {
    throw new Error(result.error);
  }
};

// Callback handler
app.post('/api/extraction-callback', (req, res) => {
  const { task_id, status, success, extraction_summary, error } = req.body;
  
  if (success) {
    console.log(`Task ${task_id} completed successfully`);
    console.log(`Products: ${extraction_summary.products_count}`);
    console.log(`Services: ${extraction_summary.services_count}`);
    console.log(`Processing time: ${req.body.processing_time}s`);
    
    // Update database with completion status
    updateTaskStatus(task_id, 'completed', extraction_summary);
  } else {
    console.error(`Task ${task_id} failed: ${error}`);
    updateTaskStatus(task_id, 'failed', { error });
  }
  
  res.json({ received: true });
});
```

---

## Backend Data Type Tracking

### New Features

The AI Service now provides detailed tracking of backend requests:

```bash
# Example log output showing backend tracking
[15:25:54] INFO: 🚀 Starting AI auto-categorization extraction
[15:25:54] INFO:    🔗 R2 URL: https://static.agent8x.io.vn/company/.../file.txt
[15:25:54] INFO:    🏭 Industry: insurance
[15:25:54] INFO:    🏢 Company ID: 9a974d00-1a4b-4d5d-8dc3-4b5058255b8f
[15:25:54] INFO: ==================================================
[15:25:54] INFO: 📊 BACKEND REQUEST ANALYSIS:
[15:25:54] INFO:    📋 Backend Data Type: 'products'
[15:25:54] INFO:    📊 Target Categories: ['products']
[15:25:54] INFO:    📄 File: insurance_products.txt
[15:25:54] INFO:    📦 File Size: 50000 bytes
[15:25:54] INFO:    📝 File Type: text/plain
[15:25:54] INFO: ==================================================
```

### Inconsistency Detection

```bash
# Example: Backend says 'products' but includes 'services'
[15:25:54] WARNING: ⚠️  INCONSISTENCY: Backend specified 'products' but target_categories includes 'services'
```

### Backend Best Practices

1. **Consistent Requests**: Ensure `data_type` matches `target_categories`
   ```typescript
   // ✅ Good
   { data_type: 'products', target_categories: ['products'] }
   
   // ❌ Inconsistent (will be logged as warning)
   { data_type: 'products', target_categories: ['products', 'services'] }
   ```

2. **Proper Data Types**:
   - `products` - Only extract product information
   - `services` - Only extract service information  
   - `auto` - Extract both products and services

3. **File Metadata**: Always provide complete file metadata for better processing

---

## Optimized Chunking Strategy

### New Chunking Algorithm

The AI Service now uses an optimized chunking strategy:

```
OLD: 1 chunk per item (inefficient)
NEW: Minimum 20 items per chunk OR grouped by categories
```

### Chunking Logic

1. **Category Grouping**: Items with same category → single chunk
2. **Minimum Threshold**: Ensure minimum 20 items per chunk  
3. **Batch Processing**: Uncategorized items → batched in groups of 20+
4. **Optimized Embedding**: Enhanced content_for_embedding for better search

### Example Chunking Output

```bash
[15:26:15] INFO: 📊 Categorization summary for products:
[15:26:15] INFO:    - Categories found: 3
[15:26:15] INFO:    - Uncategorized items: 5
[15:26:15] INFO:    - Category 'auto_insurance': 25 items → 1 chunk
[15:26:15] INFO:    - Category 'life_insurance': 18 items → added to uncategorized
[15:26:15] INFO:    - Category 'health_insurance': 32 items → 1 chunk
[15:26:15] INFO:    - Processing 23 uncategorized items in batches → 2 batches
[15:26:15] INFO: ✅ Created 4 optimized chunks for 75 products
```

---

## Queue Processing Workflow

### Architecture

```
Backend → Queue API → Redis Queue → Worker → AI Service → Qdrant → Callback
```

### Worker Processing Steps

1. **Task Detection**: Worker detects extraction mode vs document mode
2. **AI Template Loading**: Load industry-specific templates
3. **AI Provider Selection**: Choose ChatGPT Vision or Gemini
4. **Structured Extraction**: Extract with JSON schemas
5. **Optimized Chunking**: Group by categories or minimum items
6. **Qdrant Upload**: Store chunks with enhanced metadata
7. **Callback Notification**: Send completion/error callback

### Monitoring

```bash
# Worker logs for extraction tasks
[15:26:10] INFO: 🎯 EXTRACTION MODE: Processing with AI templates and structured data
[15:26:12] INFO: 🤖 Calling AI extraction service...
[15:26:15] INFO: ✅ AI extraction completed
[15:26:15] INFO:    📦 Products found: 75
[15:26:15] INFO:    🔧 Services found: 23
[15:26:16] INFO: 📤 Preparing for Qdrant ingestion with optimized chunking...
[15:26:18] INFO: ✅ Successfully uploaded extraction chunks to Qdrant
[15:26:18] INFO:    📊 Upload result: success
[15:26:18] INFO:    📈 Points added: 8
[15:26:18] INFO:    🎯 Total chunks: 8
[15:26:18] INFO: ✅ Extraction success callback sent for task extract_1737825970123_a1b2c3d4
```

---

## Error Handling

### Common Errors and Solutions

1. **Queue Service Unavailable**
   ```json
   {
     "success": false,
     "error": "Queue service unavailable",
     "status": "failed"
   }
   ```
   **Solution**: Check Redis connection and worker status

2. **Industry Template Not Found**
   ```json
   {
     "success": false,
     "error": "No template found for industry: unknown_industry"
   }
   ```
   **Solution**: Use supported industries or "other"

3. **AI Provider Failure**
   ```json
   {
     "success": false,
     "error": "All AI providers failed"
   }
   ```
   **Solution**: Check API keys and provider status

4. **Qdrant Upload Failure**
   ```json
   {
     "success": false,
     "error": "Failed to upload to Qdrant: Connection timeout"
   }
   ```
   **Solution**: Check Qdrant service and credentials

### Retry Strategy

```typescript
const extractWithRetry = async (request: ExtractionRequest, maxRetries = 3) => {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch('/api/extract/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      });
      
      if (response.ok) {
        return await response.json();
      } else if (response.status >= 500 && attempt < maxRetries) {
        console.log(`Attempt ${attempt} failed, retrying...`);
        await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
        continue;
      } else {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }
    } catch (error) {
      if (attempt === maxRetries) throw error;
      console.log(`Attempt ${attempt} failed: ${error.message}, retrying...`);
      await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
    }
  }
};
```

---

## Testing

### Test Script

Run the comprehensive test script:

```bash
python test_extraction_workflows.py
```

### Test Coverage

- ✅ Sync extraction with different data_types
- ✅ Async extraction with queue processing  
- ✅ Backend data type tracking and inconsistency detection
- ✅ Health and service info endpoints
- ✅ Error handling scenarios
- ✅ Callback notification testing

### Performance Benchmarks

| Workflow | File Size | Items | Processing Time | Chunks Created |
|----------|-----------|-------|-----------------|----------------|
| Sync     | 50KB      | 25    | 15-30s         | 2-3            |
| Async    | 500KB     | 100   | 60-120s        | 5-8            |
| Async    | 5MB       | 500+  | 180-300s       | 15-25          |

---

## Production Deployment

### Environment Variables

```bash
# AI Service Configuration
DEEPSEEK_API_KEY=your_deepseek_key
CHATGPT_API_KEY=your_openai_key  
GEMINI_API_KEY=your_gemini_key

# Qdrant Configuration
QDRANT_URL=https://your-qdrant-cloud.io
QDRANT_API_KEY=your_qdrant_key
VECTOR_SIZE=1536

# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_DB=0

# Queue Configuration
DOCUMENT_PROCESSING_QUEUE=document_processing
```

### Scaling Considerations

1. **Worker Scaling**: Deploy multiple workers for high throughput
2. **Redis Scaling**: Use Redis Cluster for large queues
3. **Qdrant Scaling**: Consider Qdrant Cloud for production
4. **Callback Reliability**: Implement callback retry mechanisms

---

## Support

For integration support, check:
1. API documentation: `/api/extract/info`
2. Health status: `/api/extract/health`  
3. Worker logs for processing details
4. Test script for validation

## Changelog

### Version 2.0 (Current)
- ✅ Added backend data type tracking
- ✅ Implemented optimized chunking strategy  
- ✅ Added queue-based async processing
- ✅ Enhanced logging and monitoring
- ✅ Improved error handling and callbacks
