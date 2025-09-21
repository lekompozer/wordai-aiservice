# 📋 PHÂN TÍCH KẾ HOẠCH CHI TIẾT & IMPLEMENTATION PLAN

## 🎯 TỔNG QUAN GIẢI PHÁP

**Mục tiêu:** Xây dựng hệ thống quản lý Product ID nội bộ để AI Service có khả năng:
1. Tự tạo và quản lý `product_id` / `service_id` duy nhất
2. Lưu trữ dữ liệu catalog sạch (4 trường) để feed vào AI prompt
3. Đồng bộ ID với Backend qua callback
4. Enable tính năng `check_quantity` chính xác

---

## 📊 PHÂN TÍCH HIỆN TRẠNG CODE

### **1. MongoDB Infrastructure (✅ SẴN SÀNG)**
- **File:** `src/database/db_manager.py`
- **Status:** Đã có MongoDB connection với authentication
- **Collection:** Sẽ tạo mới `internal_products_catalog`
- **Connection String:** Đã setup đầy đủ với `MONGODB_URI_AUTH`

### **2. Callback Handler (❌ CẦN SỬA)**
- **File:** `src/api/callbacks/enhanced_callback_handler.py`
- **Vấn đề:** Chỉ tạo `qdrant_point_id`, không có `product_id`/`service_id`
- **Cần sửa:** Thêm logic tạo ID + lưu MongoDB trước khi gửi callback

### **3. Chat Service (❌ CẦN SỬA)**
- **File:** `src/services/unified_chat_service.py`
- **Vấn đề:** Chỉ dùng Qdrant RAG, không có product catalog lookup
- **Cần sửa:** Thêm catalog search cho prompt với 4 trường sạch

### **4. Prompt System (❌ CẦN SỬA)**
- **Vấn đề:** Prompt không biết về product catalog nội bộ
- **Cần sửa:** Update prompt để ưu tiên catalog data cho inventory questions

---

## 🚀 KẾ HOẠCH IMPLEMENTATION CHI TIẾT

### **BƯỚC 1: Tạo ProductCatalogService 🎯**

**File mới:** `src/services/product_catalog_service.py`

**Chức năng:**
```python
class ProductCatalogService:
    async def register_item() -> Dict[str, Any]        # Tạo ID + lưu MongoDB
    async def get_catalog_for_prompt() -> List[Dict]   # Lấy data sạch cho prompt
    async def find_by_name() -> Optional[Dict]         # Tìm product theo tên
    async def update_quantity() -> bool                # Update số lượng
    async def get_by_id() -> Optional[Dict]            # Lấy product theo ID
```

**Schema MongoDB:**
```json
{
  "product_id": "prod_uuid_123",
  "service_id": "serv_uuid_456",
  "company_id": "company_123",
  "item_type": "product|service",
  "name": "Phở Bò Tái",
  "price": 65000,
  "quantity": 50,
  "currency": "VND",
  "raw_ai_data": {...},
  "created_at": "2025-08-19T...",
  "updated_at": "2025-08-19T..."
}
```

### **BƯỚC 2: Tích Hợp vào Callback Handler 🔧**

**File:** `src/api/callbacks/enhanced_callback_handler.py`

**Thay đổi:**
```python
# OLD - Chỉ tạo qdrant_point_id
products_stored.append({
    "name": product_name,
    "qdrant_point_id": point_id,
    "original_data": product_data
})

# NEW - Tạo product_id + lưu MongoDB
enriched_data = await catalog_service.register_item(product_data, company_id, "product")
product_id = enriched_data.get("product_id")

products_stored.append({
    "name": product_name,
    "product_id": product_id,           # ✅ Real ID
    "qdrant_point_id": point_id,
    "original_data": enriched_data      # ✅ Data có ID
})
```

### **BƯỚC 3: Nâng Cấp Chat Service 💬**

**File:** `src/services/unified_chat_service.py`

**Thay đổi:**
```python
# OLD - Chỉ RAG search
async def _hybrid_search_company_data_optimized(self, company_id: str, query: str) -> str:
    rag_results = await self._hybrid_search_company_data(...)
    return format_rag_only(rag_results)

# NEW - RAG + Catalog search
async def _hybrid_search_company_data_optimized(self, company_id: str, query: str) -> str:
    rag_results = await self._hybrid_search_company_data(...)
    catalog_results = await self.catalog_service.get_catalog_for_prompt(company_id, query)

    return f"""
[DỮ LIỆU TỒN KHO - CHÍNH XÁC NHẤT]
{format_catalog(catalog_results)}

[DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]
{format_rag(rag_results)}
"""
```

### **BƯỚC 4: Cập Nhật Prompt System 📝**

**Thay đổi prompt chính:**
```python
unified_prompt = f"""
**BỐI CẢNH ĐƯỢC CUNG CẤP:**
2. **Dữ liệu công ty (Bao gồm Tồn Kho và Mô Tả):**
   {company_data}

**HƯỚNG DẪN XỬ LÝ DỮ LIỆU:**
- **QUAN TRỌNG:** Khi khách hàng hỏi về GIÁ, SỐ LƯỢNG, TỒN KHO → ƯU TIÊN TUYỆT ĐỐI dữ liệu từ [DỮ LIỆU TỒN KHO]
- Dữ liệu [DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU] chỉ dùng để lấy thông tin mô tả chi tiết
- Khi trả lời intent `check_quantity` → bao gồm `product_id` hoặc `service_id` từ catalog
"""
```

---

## 📈 LUỒNG DỮ LIỆU SAU KHI IMPLEMENT

### **Luồng Ingestion (Nhập dữ liệu):**
```
1. AI trích xuất từ file → JSON (name, description, price...)
2. Callback Handler nhận JSON
3. ProductCatalogService.register_item():
   - Tạo product_id duy nhất
   - Lưu full data vào MongoDB
   - Trả về data đã có ID
4. Lưu vào Qdrant (có product_id)
5. Gửi callback về Backend (có product_id)
```

### **Luồng Chat (Trả lời khách hàng):**
```
1. User hỏi: "Còn phở bò không?"
2. Chat Service search:
   - Catalog: product_id, name, quantity, price
   - RAG: description chi tiết
3. AI prompt với 2 nguồn data
4. AI ưu tiên catalog cho số lượng/giá
5. Response: "Còn 15 bát phở bò, giá 65,000đ"
```

### **Luồng Check Quantity:**
```
1. Intent: CHECK_QUANTITY
2. AI tìm product_id từ catalog
3. Webhook gửi về Backend với product_id thật
4. Backend check inventory mới nhất
5. Response về AI với data cập nhật
```

---

## 💻 FILES CẦN TẠO MỚI

1. `src/services/product_catalog_service.py` - Core service
2. `tests/test_product_catalog_service.py` - Unit tests
3. `docs/PRODUCT_CATALOG_API.md` - API documentation

## 📝 FILES CẦN SỬA ĐỔI

1. `src/api/callbacks/enhanced_callback_handler.py` - Add catalog integration
2. `src/services/unified_chat_service.py` - Add catalog search
3. `src/services/unified_chat_service.py` - Update prompt system

---

## 🧪 TESTING STRATEGY

### **Unit Tests:**
- ProductCatalogService methods
- MongoDB operations
- ID generation uniqueness

### **Integration Tests:**
- Callback → Catalog → MongoDB flow
- Chat → Catalog → Prompt flow
- Webhook với product_id thật

### **End-to-End Tests:**
- File upload → Extract → Catalog → Chat → Check quantity

---

## 📊 SUCCESS METRICS

**Trước khi implement:**
- ❌ callback.product_id = undefined
- ❌ AI check_quantity = bịa UUID
- ❌ Backend webhook = 404/500 errors

**Sau khi implement:**
- ✅ callback.product_id = real UUID
- ✅ AI check_quantity = real product_id
- ✅ Backend webhook = 200 success + real data

---

## 🚦 IMPLEMENTATION ORDER

1. **PHASE 1** (Ngày 1): Tạo ProductCatalogService + tests
2. **PHASE 2** (Ngày 2): Tích hợp vào Callback Handler
3. **PHASE 3** (Ngày 3): Nâng cấp Chat Service + Prompt
4. **PHASE 4** (Ngày 4): End-to-end testing + bug fixes

**READY TO START IMPLEMENTATION!** 🚀
