# Two-Worker Architecture Implementation Summary

## ✅ Thực hiện theo đúng sequence diagram

### 🏗️ Architecture Overview

```
Backend → API → Redis Queue → ExtractionWorker → AI → StorageWorker → Enhanced Callback Handler → Backend
```

### 📋 Sequence Flow Implementation

1. **Backend → API**: POST `/process-async` (r2_url, company_id)
2. **API**: Tạo `ExtractionProcessingTask` với `hybrid_strategy_enabled=True`
3. **API → Redis Queue**: Push task_1 (AI_EXTRACTION)
4. **ExtractionWorker**: Poll Redis queue, nhận `ExtractionProcessingTask`
5. **ExtractionWorker → AI**: Gọi `ai_extraction_service.extract_from_r2_url()`
6. **AI**: Xử lý với Gemini/ChatGPT, trả về `structured_data`
7. **ExtractionWorker**: Tạo `StorageProcessingTask` với kết quả AI
8. **ExtractionWorker → Redis Queue**: Push task_2 (STORAGE_PROCESSING)
9. **StorageWorker**: Poll Redis queue, nhận `StorageProcessingTask`
10. **StorageWorker → Enhanced Callback Handler**: Gọi `store_structured_data_and_callback()`
11. **Handler**: Generate embeddings + Store Qdrant + Send Backend Callback
12. **Handler → Backend**: Enhanced Callback với `qdrant_point_id`

### 📁 Files Created/Modified

#### ✅ New Files Created:
- `src/workers/extraction_processing_worker.py` - Worker 1 (AI extraction only)
- `src/workers/storage_processing_worker.py` - Worker 2 (Storage + callback only)
- `start_two_workers.py` - Script để chạy đồng thời 2 workers
- `demo_two_workers.sh` - Demo script

#### ✅ Files Modified:
- `src/queue/task_models.py` - Added `StorageProcessingTask` model
- `src/api/callbacks/enhanced_callback_handler.py` - Optimized, removed duplicate code
- `src/api/extraction_routes.py` - Updated to use `enqueue_generic_task()`

#### ✅ Files Preserved:
- `src/workers/document_processing_worker.py` - Giữ nguyên cho endpoint `/upload`
- `src/services/ai_extraction_service.py` - Sử dụng bởi ExtractionWorker
- `src/api/admin/file_routes.py` - Endpoint `/upload` vẫn hoạt động bình thường

### 🎯 Worker Responsibilities

#### Worker 1: ExtractionProcessingWorker
- **📍 Location**: `src/workers/extraction_processing_worker.py`
- **🎯 Job**: AI extraction ONLY
- **🔧 Dependencies**: `ai_extraction_service.py`
- **📤 Output**: `StorageProcessingTask` → Redis Queue

#### Worker 2: StorageProcessingWorker  
- **📍 Location**: `src/workers/storage_processing_worker.py`
- **🎯 Job**: Qdrant storage + backend callback ONLY
- **🔧 Dependencies**: `enhanced_callback_handler.py`
- **📞 Output**: Enhanced callback to backend

### 🚀 How to Run

#### Start Both Workers:
```bash
python3 start_two_workers.py
```

#### Demo with Environment Setup:
```bash
./demo_two_workers.sh
```

#### Test API Call:
```bash
curl -X POST "http://localhost:8000/api/v1/extraction/process-async" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "test-company",
    "r2_url": "https://example.com/file.pdf",
    "file_name": "test.pdf",
    "industry": "restaurant",
    "callback_url": "https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback"
  }'
```

### 🎯 Enhanced Callback Handler Optimization

#### ✅ Removed Duplicate Code:
- Consolidated storage logic into single function
- Removed redundant product/service processing loops
- Unified backend callback mechanism

#### ✅ Fixed Backend Callback URL:
- Hard-coded to: `https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback`
- No endpoint created in this service (storage function only)

#### ✅ Function Responsibilities:
- `store_structured_data_and_callback()`: ONLY handles storage + callback
- `send_backend_callback()`: Utility function for webhook calls
- `generate_embedding()`: Utility function for embedding generation

### 🔧 Environment Variables Required

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379

# AI Provider Keys
DEEPSEEK_API_KEY=your_deepseek_key
CHATGPT_API_KEY=your_chatgpt_key
GEMINI_API_KEY=your_gemini_key

# Qdrant Configuration  
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_key

# Webhook Configuration
WEBHOOK_SECRET=webhook-secret-for-signature
```

### 📊 Task Models

#### ExtractionProcessingTask (Worker 1 Input):
```python
{
    "task_id": "hybrid_extract_...",
    "company_id": "test-company", 
    "r2_url": "https://example.com/file.pdf",
    "industry": "restaurant",
    "processing_metadata": {
        "hybrid_strategy_enabled": True,
        "individual_storage_mode": True,
        # ... other flags
    }
}
```

#### StorageProcessingTask (Worker 2 Input):
```python
{
    "task_id": "storage_hybrid_extract_...",
    "company_id": "test-company",
    "structured_data": {
        "products": [...],
        "services": [...]
    },
    "metadata": {...},
    "callback_url": "https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback",
    "original_extraction_task_id": "hybrid_extract_..."
}
```

### ✅ Backward Compatibility

- `/upload` endpoint vẫn sử dụng `DocumentProcessingWorker` (không thay đổi)
- Standard extraction mode vẫn hoạt động bình thường
- Chỉ hybrid strategy sử dụng 2-worker architecture

### 🎯 Key Achievements

1. ✅ **True Separation**: 2 workers riêng biệt, mỗi worker có 1 nhiệm vụ
2. ✅ **Exact Sequence**: Theo đúng sequence diagram user cung cấp
3. ✅ **No Duplicate Code**: Optimized enhanced_callback_handler.py
4. ✅ **No New Endpoints**: Handler chỉ là function, không tạo API endpoint
5. ✅ **AI Service Integration**: Worker 1 sử dụng ai_extraction_service.py
6. ✅ **Enhanced Callback**: Worker 2 gửi callback với qdrant_point_id
7. ✅ **Preserved Existing**: Không làm hỏng endpoint `/upload` hiện tại
