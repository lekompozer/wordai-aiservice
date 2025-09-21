# 🔍 PHÂN TÍCH CHI TIẾT: PROMPT SYSTEM & PRODUCTID/SERVICEID ISSUES

## 📋 TỔNG QUAN VẤN ĐỀ

Sau khi phân tích kỹ codebase, tôi phát hiện **5 vấn đề nghiêm trọng** trong prompt system và quản lý ProductId/ServiceId của các intent mới:

---

## 🚨 VẤN ĐỀ 1: PROMPT KHÔNG HƯỚNG DẪN AI TẠO JSON WEBHOOK DATA

### ❌ **Vấn đề hiện tại:**
```python
# Trong unified_chat_service.py dòng 2800-2900
unified_prompt = f"""
**NHIỆM VỤ CỦA BẠN:**
Thực hiện các bước sau trong đầu và chỉ trả về một đối tượng JSON duy nhất:

1. **Phân tích (Thinking Process):** ...
2. **Tạo câu trả lời cuối cùng (Final Answer):** ...

**ĐỊNH DẠNG ĐẦU RA (OUTPUT FORMAT):**
```json
{{
  "thinking": {{
    "intent": "...",
    "persona": "...",
    "reasoning": "..."
  }},
  "final_answer": "..."
}}
```
```

### ⚠️ **Rủi ro nghiêm trọng:**

1. **THIẾU HƯỚNG DẪN WEBHOOK DATA:** Prompt chỉ yêu cầu AI trả về `thinking` và `final_answer`, KHÔNG có hướng dẫn tạo dữ liệu webhook cho 3 intent mới
2. **AI KHÔNG BIẾT CẤU TRÚC BACKEND:** AI không được hướng dẫn tạo `productId`, `serviceId`, order data theo chuẩn API_WEBHOOK_BE.md
3. **DỮ LIỆU PLACEHOLDER:** Khi AI không biết structure, sẽ tạo dữ liệu giả hoặc placeholder

---

## 🚨 VẤN ĐỀ 2: PRODUCTID/SERVICEID KHÔNG CÓ NGUỒN DỮ LIỆU THẬT

### ❌ **Vấn đề hiện tại:**
```python
# Trong _extract_check_quantity_data() dòng 2241-2242
extraction_prompt = f"""
{{
  "productId": "UUID sản phẩm (nếu xác định được)",
  "serviceId": "UUID dịch vụ (nếu xác định được)",
  ...
}}
"""
```

### ⚠️ **Rủi ro bịa đặt dữ liệu:**

1. **AI SẼ TẠO UUID GIẢ:** Khi không có dữ liệu thật, AI sẽ tạo UUID ngẫu nhiên hoặc placeholder
2. **BACKEND SẼ BỊ LỖI:** Khi nhận UUID không tồn tại, backend sẽ trả về 404 hoặc 500
3. **CUSTOMER EXPERIENCE THẤT BẠI:** Khách hàng sẽ nhận thông báo lỗi thay vì phản hồi hữu ích

### 🔍 **Phát hiện từ code:**
```python
# AdminService CÓ methods để lấy products/services
async def get_company_products(self, company_id: str) -> List[Dict[str, Any]]:
async def get_company_services(self, company_id: str) -> List[Dict[str, Any]]:

# NHƯNG unified_chat_service KHÔNG sử dụng chúng!
```

---

## 🚨 VẤN ĐỀ 3: LOGIC EXTRACTION DỮ LIỆU KÉM HIỆU QUẢ

### ❌ **Vấn đề hiện tại:**
```python
# Trong _extract_order_data_from_response()
extraction_result = await self.ai_manager.stream_response(
    question=extraction_prompt,
    session_id=f"extract_{int(datetime.now().timestamp())}",
    user_id="system",
    provider="cerebras",
)
```

### ⚠️ **Rủi ro performance và độ chính xác:**

1. **DOUBLE AI CALL:** Gọi AI 2 lần (1 lần response + 1 lần extraction) → tăng latency
2. **KHÔNG CÓ CONTEXT:** AI extraction không có context từ conversation history
3. **JSON PARSING LỖI:** Regex để tìm JSON trong response không reliable
4. **FALLBACK DATA KHÔNG HỮU ÍCH:** Default data không giúp backend xử lý được

---

## 🚨 VẤN ĐỀ 4: KHÔNG CÓ PRODUCT/SERVICE LOOKUP SYSTEM

### ❌ **Thiếu hệ thống tra cứu:**

AI Service cần có khả năng:
1. **TÌM PRODUCT BY NAME:** Khách hàng nói "áo thun nam size M" → tìm productId từ MongoDB
2. **FUZZY MATCHING:** "phở bò" → tìm "Phở Bò Tái" trong menu
3. **VALIDATION:** Kiểm tra productId/serviceId có tồn tại không trước khi gửi webhook
4. **MULTI-LANGUAGE:** Tìm kiếm bằng tiếng Việt và tiếng Anh

### 🔍 **Evidence từ AdminService:**
```python
# AdminService có methods này nhưng không được sử dụng
async def get_company_products(self, company_id: str) -> List[Dict[str, Any]]:
    """Fetches products for company"""

async def get_company_services(self, company_id: str) -> List[Dict[str, Any]]:
    """Fetches services for company"""
```

---

## 🚨 VẤN ĐỀ 5: KHÔNG CÓ REAL-TIME INVENTORY CHECKING

### ❌ **CHECK_QUANTITY intent thiếu logic:**

```python
# Trong _extract_check_quantity_data() chỉ tạo JSON
# KHÔNG CHECK inventory thật từ MongoDB
return {
    "itemName": "Sản phẩm/dịch vụ từ cuộc hội thoại",
    "itemType": "Product",
    # productId VẪN CHƯA CÓ THẬT!
}
```

---

Worker 1 (extraction_processing_worker.py):

Nhiệm vụ: Gọi AI để đọc file (PDF, DOCX...) và trích xuất thông tin sản phẩm/dịch vụ thành một cấu trúc JSON.
Lỗ hổng: Prompt của AI (_build_auto_categorization_system_prompt) chỉ yêu cầu trích xuất các thuộc tính như name, description, price. Nó hoàn toàn không yêu cầu và không thể tự tạo ra một product_id hay service_id duy nhất và bền vững. Kết quả là JSON từ AI không chứa ID.
Callback Handler (enhanced_callback_handler.py):

Nhiệm vụ: Nhận kết quả JSON từ Worker 1, lưu vào Qdrant để tìm kiếm, và gửi callback về Backend.
Lỗ hổng:
Hàm enhanced_extraction_callback nhận product_data và service_data không có ID.
Nó chỉ tạo ra point_id là ID cho vector trong Qdrant, không phải là ID cho sản phẩm.
Khi gửi callback về Backend, nó gửi original_data (dữ liệu gốc từ AI, không có ID) và qdrant_point_id. Backend nhận được dữ liệu nhưng không có một mã định danh (product_id) để lưu vào database của họ.
Kết Luận: Hệ thống hiện tại chỉ "trôi" dữ liệu từ AI đến Backend mà không làm giàu hay định danh dữ liệu. Điều này khiến việc đồng bộ và các tính năng tương tác sau này (như check_quantity) là không thể.

Giải Pháp: Implement Hệ Thống Quản Lý Product ID Nội Bộ
Giải pháp bạn đề xuất là hoàn toàn chính xác. AI Service cần một "bộ não" nhỏ để quản lý danh mục sản phẩm của riêng mình.

Kế Hoạch Hành Động Chi Tiết:

Bước 1: Tạo Service Quản Lý Product/Service trên MongoDB
Chúng ta cần một service mới để tương tác với collection products_services trên MongoDB.

Bước 2: Tích Hợp Service Mới vào Callback Handler
Bây giờ, chúng ta sẽ sửa enhanced_callback_handler.py để gọi service này, sử dụng dữ liệu trả về từ AI, tạo ID, lưu vào MongoDB, và sau đó gửi ID đó trong callback về Backend.

Lợi Ích:

Đồng Bộ Hóa: Backend và AI Service giờ đây có một mã định danh chung (product_id) để tham chiếu đến cùng một sản phẩm.
Nền Tảng Cho Tương Lai: AI Service đã có sẵn dữ liệu (product_id, name, quantity...) trong MongoDB của mình, sẵn sàng cho việc implement logic check_quantity một cách chính xác.

Sửa Luồng Retrieval: Cập nhật unified_chat_service.py để khi xử lý chat, nó sẽ lấy dữ liệu "sạch" (4 trường) từ Catalog Service để đưa vào prompt. Lưu ý chỉ lấy 4 trường này để đưa vào prompt.

Product_id
Name (product)
Quantity (product)
Price (các trường dữ liệu của price)


Nâng Cấp Prompt: Cập nhật prompt chính để AI hiểu và ưu tiên sử dụng dữ liệu tồn kho từ catalog trước, đồng thời hỏi khách hàng cần check trực tiếp với doanh nghiệp không thì hệ thống sẽ gọi API callback check quantity về backend để backend tự check dữ liệu mới nhất và gửi email cho doanh nghiệp như đã implement.

## 🎯 KẾT LUẬN & KHUYẾN NGHỊ

### ⚡ **PRIORITY 1 - CRITICAL:**
1. **FIX PROMPT SYSTEM:** Thêm webhook data guidance vào prompt
2. **IMPLEMENT PRODUCT LOOKUP:** Tạo service tìm kiếm productId/serviceId thật
3. **VALIDATE BEFORE SEND:** Kiểm tra dữ liệu trước khi gửi webhook

### ⚡ **PRIORITY 2 - HIGH:**
4. **INVENTORY INTEGRATION:** Tích hợp real-time inventory check
5. **ERROR HANDLING:** Xử lý lỗi khi không tìm thấy product/service
6. **MONITORING:** Theo dõi chất lượng dữ liệu webhook

### ⚡ **PRIORITY 3 - MEDIUM:**
7. **TESTING FRAMEWORK:** Tạo framework test tự động
8. **PERFORMANCE OPTIMIZATION:** Giảm số lần gọi AI
9. **MULTI-LANGUAGE:** Hỗ trợ tìm kiếm đa ngôn ngữ

---

## 🚀 IMPACT EXPECTED

**TRƯỚC KHI FIX:**
- ❌ ProductId/ServiceId = placeholder/fake UUID
- ❌ Backend nhận 404/500 errors
- ❌ Customer experience thất bại
- ❌ 3 intent mới không hoạt động production

**SAU KHI FIX:**
- ✅ ProductId/ServiceId = real data từ MongoDB
- ✅ Backend xử lý thành công webhook
- ✅ Customer nhận response chính xác
- ✅ 3 intent mới production-ready 100%

**TIMELINE ƯỚC TÍNH:** 2-3 ngày development + testing cho complete fix

---

## 📞 NEXT ACTIONS

1. **Confirm priorities** với user
2. **Implement Step 1-3** (core fixes)
3. **Test với real company data**
4. **Deploy và monitor**
5. **Iterate based on results**

Bạn muốn tôi bắt đầu implement từ Step nào trước?
