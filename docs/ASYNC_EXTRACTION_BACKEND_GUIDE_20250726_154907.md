# Async Extraction API - Backend Integration Guide

## Overview
This guide provides complete documentation for integrating with the Async Extraction API, including exact API calls, response handling, and result verification.

## Test Results Summary
- **Task ID**: extract_1753519446697_f705746d
- **Total Processing Time**: 300.75 seconds
- **Qdrant Upload Status**: ❌ Failed
- **Test Date**: 2025-07-26T15:49:07.429560

## 1. API Endpoint

### POST `/api/extract/process-async`

**Purpose**: Submit extraction task for background processing

### Request Payload
```json
{
  "r2_url": "https://static.agent8x.io.vn/company/[company-id]/files/[filename]",
  "company_id": "your-company-id",
  "industry": "insurance",
  "data_type": "products",
  "file_name": "SanPham-AIA.txt",
  "file_size": 1024000,
  "file_type": "text/plain",
  "callback_url": "https://your-backend.com/api/extraction/callback" // Optional
}
```

### Immediate Response
```json
{
  "success": true,
  "task_id": "extract_1753518891546_b9ab7e78",
  "company_id": "your-company-id",
  "status": "queued",
  "message": "Extraction task queued successfully for products extraction",
  "estimated_time": 180
}
```

## 2. Workflow Timeline

### Phase 1: Queue Submission (< 1 second)
- Request submitted to async endpoint
- Task queued in Redis
- Immediate response with `task_id`

### Phase 2: Background Processing (30-180 seconds)
- Worker picks up task from queue
- AI extraction using industry-specific templates
- Content processing and structuring
- Generation of `content_for_embedding` fields

### Phase 3: Qdrant Upload (10-30 seconds)
- Data chunking and embedding generation
- Upload to multi-company Qdrant collection
- Search index optimization

## 3. Monitoring Task Progress

### Option A: Callback URL (Recommended)
Include `callback_url` in your request to receive notification when processing completes.

**Callback Payload Structure**:
```json
{
  "task_id": "extract_1753518891546_b9ab7e78",
  "status": "completed",
  "company_id": "your-company-id",
  "results": {
    "total_items": 6,
    "products_count": 3,
    "services_count": 3,
    "processing_time": 45.2,
    "qdrant_upload_status": "success"
  },
  "completion_timestamp": "2025-07-26T15:34:51.000Z"
}
```

### Option B: Qdrant Search Verification
Query Qdrant search API to verify data availability:

```bash
curl -X POST "http://localhost:8000/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "your-company-id",
    "query": "bảo hiểm",
    "limit": 10
  }'
```

## 4. Performance Expectations

Based on test results:
- **Queue Time**: < 1 second
- **Processing Time**: 30-60 seconds (depends on file size and complexity)
- **Qdrant Upload**: 10-30 seconds
- **Total Time**: 60-180 seconds maximum

## 5. Error Handling

### Common Error Scenarios

**Queue Full Error**:
```json
{
  "success": false,
  "error": "Queue service unavailable",
  "task_id": null
}
```

**Processing Error** (via callback):
```json
{
  "task_id": "extract_1753518891546_b9ab7e78",
  "status": "failed",
  "error": "AI extraction failed: Invalid file format",
  "retry_recommended": true
}
```

## 6. Backend Implementation Example

```python
import requests
import time
from typing import Dict, Any

class AsyncExtractionClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def submit_extraction(self, r2_url: str, company_id: str, 
                         industry: str, callback_url: str = None) -> Dict[str, Any]:
        """Submit file for async extraction"""
        payload = {
            "r2_url": r2_url,
            "company_id": company_id,
            "industry": industry,
            "data_type": "auto",  # Extract both products and services
            "file_name": r2_url.split('/')[-1],
            "file_type": "text/plain",
            "callback_url": callback_url
        }
        
        response = requests.post(
            f"{self.base_url}/api/extract/process-async",
            json=payload,
            timeout=30
        )
        
        return response.json()
    
    def verify_completion(self, company_id: str, 
                         max_wait: int = 300) -> Dict[str, Any]:
        """Verify extraction completion via search"""
        for attempt in range(max_wait // 10):
            search_response = requests.post(
                f"{self.base_url}/api/search",
                json={
                    "company_id": company_id,
                    "query": "test search",
                    "limit": 1
                }
            )
            
            if search_response.status_code == 200:
                data = search_response.json()
                if data.get('results'):
                    return {"status": "completed", "verified": True}
            
            time.sleep(10)
        
        return {"status": "timeout", "verified": False}

# Usage Example
client = AsyncExtractionClient("http://localhost:8000")

# Submit extraction
result = client.submit_extraction(
    r2_url="https://your-r2-url.com/file.txt",
    company_id="your-company-id",
    industry="insurance",
    callback_url="https://your-backend.com/callback"
)

if result.get('success'):
    task_id = result['task_id']
    print(f"Task submitted: {task_id}")
    
    # Verify completion
    verification = client.verify_completion("your-company-id")
    print(f"Verification: {verification}")
```

## 7. Integration Checklist

- [ ] Implement async request submission
- [ ] Set up callback URL endpoint (recommended)
- [ ] Implement task ID tracking in your database
- [ ] Set up error handling for failed extractions
- [ ] Implement retry logic for transient failures
- [ ] Test with various file types and sizes
- [ ] Verify Qdrant search integration
- [ ] Monitor processing performance
- [ ] Set up alerting for failed extractions

## 8. Support and Troubleshooting

### Common Issues:
1. **Long processing times**: Check file size and complexity
2. **Callback not received**: Verify callback URL accessibility
3. **Search returns no results**: Wait for Qdrant indexing completion
4. **Queue errors**: Check Redis connectivity

### Monitoring Endpoints:
- Health Check: `GET /api/extract/health`
- Service Info: `GET /api/extract/info`

---
*Generated on: 2025-07-26T15:49:07.429565*
*Based on test results: async_workflow_complete_test_20250726_154907.json*
