# Phân Tích Chi Tiết QdrantCompanyDataService
# Detailed Analysis of QdrantCompanyDataService for Company Context CRUD

## 🏗️ Kiến Trúc Tổng Quan (Overall Architecture)

`QdrantCompanyDataService` được thiết kế theo mô hình **Multi-tenant** trong một **Unified Collection** để tối ưu cho Qdrant Free Plan. Thay vì tạo collection riêng cho mỗi công ty, tất cả dữ liệu được lưu trong collection `multi_company_data` và phân biệt bằng `company_id`.

### Cấu Trúc Dữ Liệu (Data Structure)
```python
# Point Structure in Qdrant
{
    "id": "chunk_id",  # UUID unique
    "vector": [0.1, 0.2, ...],  # 768-dimension embedding
    "payload": {
        "company_id": "abc_insurance_001",  # PRIMARY FILTER
        "file_id": "company_context",
        "content": "Raw content text",
        "content_for_embedding": "Optimized text for embedding",
        "data_type": "company_info",  # IndustryDataType enum
        "structured_data": {...},  # Additional metadata
        "language": "vietnamese",
        "industry": "insurance",
        "location": "vietnam",
        "created_at": "2025-07-31T...",
        "updated_at": "2025-07-31T..."
    }
}
```

---

## 📋 Phân Tích Từng Hàm CRUD

### 1. **Initialization Functions** (Khởi Tạo)

#### `__init__()`
- **Mục đích**: Khởi tạo kết nối Qdrant và AI service
- **Tham số**: `qdrant_url`, `qdrant_api_key` cho cloud hoặc `host/port` cho local
- **Quan trọng**: 
  - Sử dụng `unified_collection_name = "multi_company_data"`
  - Cache company metadata trong `self.company_collections`

#### `initialize_company_collection(company_config: CompanyConfig)`
- **Mục đích**: Khởi tạo collection cho company mới
- **Hoạt động**:
  1. Kiểm tra collection `multi_company_data` có tồn tại chưa
  2. Tạo collection với `VectorParams(size=768, distance=COSINE)` nếu chưa có
  3. Tạo payload indexes cho filtering hiệu quả
  4. Cache company info vào memory

```python
# Usage for Company Context Setup
await qdrant_service.initialize_company_collection(CompanyConfig(
    company_id="abc_insurance_001",
    industry=Industry.INSURANCE,
    company_name="ABC Insurance"
))
```

#### `ensure_unified_collection_exists()`
- **Mục đích**: Đảm bảo collection tồn tại (phiên bản đơn giản)
- **Sử dụng**: Khi cần đảm bảo collection có sẵn trước khi thao tác

---

### 2. **CREATE Operations** (Tạo Mới)

#### `add_document_chunks(chunks: List[QdrantDocumentChunk], company_id: str)`
- **Mục đích**: Thêm company context chunks vào Qdrant
- **Hoạt động**:
  1. Auto-ensure collection exists
  2. Generate embeddings cho từng chunk
  3. Convert thành PointStruct format
  4. Batch upsert vào Qdrant

```python
# Usage for Company Context Upload
chunks = [
    QdrantDocumentChunk(
        chunk_id=str(uuid.uuid4()),
        company_id="abc_insurance_001",
        file_id="company_context",
        content="Company basic information...",
        content_for_embedding="Optimized content for search...",
        content_type=IndustryDataType.COMPANY_INFO,
        language=Language.VIETNAMESE,
        industry=Industry.INSURANCE,
        structured_data={
            "section": "basic_info",
            "company_name": "ABC Insurance",
            "products": ["life_insurance", "health_insurance"]
        }
    )
]

result = await qdrant_service.add_document_chunks(chunks, "abc_insurance_001")
```

**Đặc điểm quan trọng**:
- Sử dụng `content_for_embedding` để tạo vector (tối ưu cho tìm kiếm)
- `data_type` thay vì `content_type` trong payload
- Batch processing cho hiệu suất cao

---

### 3. **READ Operations** (Đọc/Tìm Kiếm)

#### `search_company_data(company_id, query, industry, data_types, language, limit, score_threshold)`
- **Mục đích**: Tìm kiếm semantic trong dữ liệu company context
- **Hoạt động**:
  1. Generate embedding cho query
  2. Xây dựng filter với `must` và `should` conditions
  3. Thực hiện vector search với filtering
  4. Format kết quả cho AI consumption

```python
# Usage for Company Context Search
results = await qdrant_service.search_company_data(
    company_id="abc_insurance_001",
    query="bảo hiểm sức khỏe cho gia đình",
    industry=Industry.INSURANCE,
    data_types=[IndustryDataType.COMPANY_INFO, IndustryDataType.PRODUCTS],
    language=Language.VIETNAMESE,
    limit=5,
    score_threshold=0.7
)
```

**Filter Logic**:
- **MUST**: `company_id`, `industry` (bắt buộc)
- **SHOULD**: `data_types` (ưu tiên nhưng không bắt buộc)
- **OPTIONAL**: `language` (nếu không phải AUTO_DETECT)

#### `get_company_data_stats(company_id: str)`
- **Mục đích**: Lấy thống kê dữ liệu company
- **Trả về**: `CompanyDataStats` với số lượng chunks theo data_type

---

### 4. **UPDATE Operations** (Cập Nhật)

#### `update_document_chunk(chunk: QdrantDocumentChunk, company_id: str)`
- **Mục đích**: Cập nhật một chunk cụ thể
- **Hoạt động**:
  1. Generate embedding mới cho content
  2. Upsert point với same ID
  3. Update `updated_at` timestamp

```python
# Usage for Company Context Update
updated_chunk = QdrantDocumentChunk(
    chunk_id="existing_chunk_id",
    company_id="abc_insurance_001",
    content="Updated company information...",
    # ... other fields
)

result = await qdrant_service.update_document_chunk(updated_chunk, "abc_insurance_001")
```

#### `upsert_points(collection_name: str, points: List[Dict])`
- **Mục đích**: Raw upsert operation cho batch updates
- **Sử dụng**: Khi cần update nhiều points cùng lúc

---

### 5. **DELETE Operations** (Xóa)

#### `delete_company_data(company_id: str, file_ids: Optional[List[str]])`
- **Mục đích**: Xóa dữ liệu company theo file hoặc toàn bộ
- **Hoạt động**:
  - Nếu có `file_ids`: Xóa specific files
  - Nếu không: Xóa tất cả dữ liệu company

```python
# Delete specific files
result = await qdrant_service.delete_company_data(
    company_id="abc_insurance_001",
    file_ids=["company_context", "old_policies"]
)

# Delete all company data
result = await qdrant_service.delete_company_data("abc_insurance_001")
```

#### `delete_points(collection_name: str, point_ids: List[str])`
- **Mục đích**: Xóa points cụ thể theo IDs
- **Sử dụng**: Cleanup operations

---

### 6. **Utility Functions** (Hàm Tiện Ích)

#### `scroll_points(collection_name, scroll_filter, limit, offset)`
- **Mục đích**: Duyệt qua large datasets
- **Sử dụng**: Export, statistics, bulk operations

#### `_generate_embedding(text: str)`
- **Mục đích**: Tạo embedding vector cho text
- **Sử dụng**: Internal function cho tất cả operations cần embedding

---

## 🎯 Ứng Dụng Cho Company Context CRUD

### **Workflow Upload Company Context**

```python
# 1. Initialize company collection
await qdrant_service.initialize_company_collection(company_config)

# 2. Prepare company context chunks
basic_info_chunk = QdrantDocumentChunk(
    chunk_id=str(uuid.uuid4()),
    company_id=company_id,
    file_id="company_context",
    content=formatted_basic_info,
    content_for_embedding=optimized_content,
    content_type=IndustryDataType.COMPANY_INFO,
    language=Language.VIETNAMESE,
    industry=company_config.industry,
    structured_data={
        "section": "basic_info",
        "company_name": basic_info.company_name,
        "introduction": basic_info.introduction
    }
)

faq_chunks = [...]  # Multiple FAQ chunks
scenario_chunks = [...]  # Multiple scenario chunks

# 3. Batch upload all chunks
all_chunks = [basic_info_chunk] + faq_chunks + scenario_chunks
result = await qdrant_service.add_document_chunks(all_chunks, company_id)

# 4. Verify upload
stats = await qdrant_service.get_company_data_stats(company_id)
print(f"Uploaded {stats.total_chunks} chunks")
```

### **Integration với CompanyContextService**

```python
# In CompanyContextService._index_context_to_qdrant()
async def _index_context_to_qdrant(self, company_id: str):
    context = await self._get_or_create_context(company_id)
    formatted_context = self._format_context_to_string(context)
    
    if not formatted_context.strip():
        return
    
    # Use QdrantCompanyDataService
    qdrant_service = await self._get_qdrant_service()
    
    context_chunk = QdrantDocumentChunk(
        chunk_id=str(uuid.uuid4()),
        company_id=company_id,
        file_id="company_context",
        content=formatted_context,
        content_for_embedding=formatted_context,
        content_type=IndustryDataType.COMPANY_INFO,
        language=Language.VIETNAMESE,
        industry=Industry.OTHER,  # Or detect from company config
    )
    
    await qdrant_service.add_document_chunks([context_chunk], company_id)
```

---

## 🔧 Best Practices cho Company Context

### **1. Chunk Strategy**
- **Basic Info**: 1 chunk toàn bộ thông tin company
- **FAQs**: 1 chunk per FAQ hoặc group theo chủ đề
- **Scenarios**: 1 chunk per scenario với structured steps

### **2. Metadata Design**
```python
{
    "section": "basic_info|faq|scenario",
    "faq_category": "products|services|support",
    "scenario_type": "sales|support|information",
    "target_audience": ["individual", "business"],
    "priority": "high|medium|low"
}
```

### **3. Search Optimization**
- Sử dụng `content_for_embedding` với keywords optimized
- Include synonyms và alternate phrasings
- Structure content theo search intent

### **4. Maintenance Strategy**
- Auto-reindex khi company context thay đổi
- Periodic cleanup của stale data
- Version control cho major updates

---

## 📊 Performance Considerations

### **Indexing Performance**
- Batch upload tất cả chunks cùng lúc
- Sử dụng proper payload indexes
- Monitor collection size và query performance

### **Search Performance**
- Cache frequent search results
- Use appropriate score_threshold
- Limit search scope với proper filtering

### **Memory Management**
- Clear company_collections cache khi cần
- Monitor Qdrant memory usage
- Implement data retention policies

---

## 🛡️ Security & Multi-tenancy

### **Data Isolation**
- `company_id` là PRIMARY FILTER bắt buộc
- Validate company access trong API layer
- Audit logs cho all operations

### **Error Handling**
- Graceful fallback khi Qdrant unavailable
- Retry logic cho network failures
- Comprehensive error logging

---

Phân tích này cung cấp roadmap chi tiết để implement company context CRUD operations sử dụng `QdrantCompanyDataService` một cách hiệu quả và scalable.
