Chắc chắn rồi! Đây là phân tích chi tiết về kiến trúc lưu trữ và tìm kiếm tối ưu cho dự án của bạn, đặc biệt khi sử dụng RAG với Qdrant và AI provider là Deepseek (thuần text).

---

### **Phần 1: Tổng quan kiến trúc tối ưu cho RAG với Deepseek**

Mục tiêu chính là cung cấp cho Deepseek (một mô hình ngôn ngữ thuần text) ngữ cảnh (context) **chính xác, đầy đủ và súc tích nhất** để trả lời câu hỏi của người dùng. Kiến trúc tối ưu sẽ xoay quanh 3 nguyên tắc:

1.  **Vector hóa "Ngữ nghĩa" (Semantic Vectorization):** Mọi thứ phải được chuyển thành văn bản có ý nghĩa trước khi tạo embedding. Deepseek không thể "thấy" JSON hay hình ảnh, nó chỉ có thể "đọc" mô tả về chúng. Vector sẽ đại diện cho ngữ nghĩa của mô tả đó.
2.  **Tìm kiếm Lai (Hybrid Search):** Kết hợp sức mạnh của tìm kiếm vector (tìm kiếm theo ngữ nghĩa) và lọc metadata (tìm kiếm chính xác). Đây là chìa khóa để thu hẹp phạm vi tìm kiếm, tăng độ chính xác và giảm chi phí.
3.  **Lưu trữ Kép (Dual Storage):** Mỗi "điểm" (point) trong Qdrant sẽ lưu trữ hai thứ:
    *   **Vector của Nội dung đã Xử lý (Processed Content):** Một đoạn văn bản được tối ưu hóa cho AI đọc và tạo embedding.
    *   **Dữ liệu Gốc (Raw/Structured Data):** JSON gốc hoặc URL hình ảnh. Dữ liệu này không dùng để tìm kiếm mà để **ứng dụng (application layer) sử dụng sau khi đã tìm thấy** nhằm hiển thị câu trả lời đẹp mắt cho người dùng (ví dụ: hiển thị card sản phẩm với giá và hình ảnh).

---

### **Phần 2: Cấu trúc lưu trữ chi tiết trên Qdrant**

Mỗi mẩu thông tin sẽ được lưu dưới dạng một `PointStruct` trong Qdrant. Dưới đây là cấu trúc đề xuất cho một `Point`.

#### **Cấu trúc PointStruct chung:**

```json
{
  "id": "unique_chunk_id", // UUID cho mỗi chunk
  "vector": [0.123, 0.456, ...], // Vector embedding của trường "content_for_embedding"
  "payload": {
    // --- Metadata cốt lõi để lọc (Filtering) ---
    "company_id": "golden-dragon-restaurant",
    "data_type": "PRODUCTS", // Enum: COMPANY_INFO, PRODUCTS, SERVICES, FAQ, IMAGE_INFO...
    "language": "vi", // Ngôn ngữ của nội dung (vi, en,...)
    "source_file_id": "file_abc_123", // ID của file gốc nếu có
    "created_at": "2025-07-22T10:00:00Z",

    // --- Nội dung cho RAG ---
    "content_for_embedding": "Phở Tái. Món phở bò truyền thống với thịt bò tái mềm, nước dùng đậm đà ninh từ xương trong 12 tiếng. Giá 65,000 VND.", // **QUAN TRỌNG**: Text dùng để tạo vector và cho AI đọc
    "structured_data": { ... }, // JSON gốc hoặc dữ liệu có cấu trúc
    
    // --- Metadata bổ sung ---
    "tags": ["best-seller", "traditional"],
    "metadata_extra": { ... } // Các thông tin khác
  }
}
```

#### **Chiến lược Chunking và Lưu trữ cho từng loại dữ liệu:**

**1. Company Basic Info (data_type: `COMPANY_INFO`)**

*   **Chunking:** Chỉ có **một chunk duy nhất** cho toàn bộ thông tin cơ bản của công ty.
*   **`content_for_embedding`:** Tạo một đoạn văn bản mạch lạc, tổng hợp tất cả thông tin:
    > "Nhà hàng Golden Dragon là một nhà hàng Việt Nam chuyên về ẩm thực truyền thống tại 123 Nguyễn Huệ, Quận 1, TP.HCM. Giờ mở cửa từ 9h sáng đến 10h tối. Liên hệ qua email contact@goldendragon.vn hoặc số điện thoại +84901234567. Website: https://goldendragon.vn."
*   **`structured_data`:** Lưu JSON gốc chứa tất cả các trường (tên, địa chỉ, email, giờ mở cửa, v.v.).

**2. Files (Raw data - data_type: `KNOWLEDGE_BASE`, `POLICIES`)**

*   **Chunking:** Sử dụng kỹ thuật "Semantic Chunking". Chia văn bản thành các đoạn (chunk) dựa trên ngữ nghĩa, thường là theo từng đoạn văn (paragraph) hoặc các tiêu đề. Mỗi chunk nên tự chứa một ý tưởng trọn vẹn.
*   **`content_for_embedding`:** Chính là nội dung của chunk văn bản đó.
*   **`structured_data`:** Có thể để trống hoặc lưu thông tin về vị trí của chunk trong tài liệu gốc (ví dụ: `{"page": 2, "paragraph": 3}`).

**3. Products / Services (data_type: `PRODUCTS`, `SERVICES`)**

*   **Chunking:** **Mỗi sản phẩm/dịch vụ là một chunk.** Đây là cách tối ưu nhất.
*   **`content_for_embedding`:** Chuyển đổi đối tượng JSON của sản phẩm thành một câu văn tự nhiên, dễ hiểu cho AI.
    *   **JSON gốc:**
        ```json
        { "name": "Phở Tái", "price": 65000, "currency": "VND", "description": "Thịt bò tái mềm, nước dùng đậm đà.", "category": "Món chính" }
        ```
    *   **Chuyển thành `content_for_embedding`:**
        > "Tên sản phẩm: Phở Tái. Mô tả: Thịt bò tái mềm, nước dùng đậm đà. Thuộc danh mục: Món chính. Giá: 65,000 VND."
*   **`structured_data`:** Lưu lại JSON gốc của sản phẩm.

**4. Hình ảnh (data_type: `IMAGE_INFO`)**

*   **Chunking:** Mỗi hình ảnh là một chunk.
*   **`content_for_embedding`:** **Mô tả chi tiết về hình ảnh**. Đây là phần quan trọng nhất vì Deepseek không xem được ảnh.
    > "Hình ảnh một tô Phở Tái bốc khói nghi ngút, trang trí với hành lá, ngò gai và lát ớt đỏ. Tô phở đặt trên bàn gỗ, bên cạnh là đĩa rau thơm và chén nước chấm."
*   **`structured_data`:**
    ```json
    {
      "r2_url": "https://static.agent8x.io.vn/...",
      "alt_text": "Tô phở bò tái nóng hổi",
      "folder_id": "folder_menu_items"
    }
    ```

---

### **Phần 3: Kiến trúc tìm kiếm tối ưu (Hybrid Search)**

Khi người dùng chat, ví dụ: *"Quán có phở không em?"*, quy trình tìm kiếm sẽ như sau:

**Bước 1: Phân tích câu hỏi và tạo Vector**

*   Câu hỏi của người dùng *"Quán có phở không em?"* được đưa qua mô hình embedding (đa ngôn ngữ) để tạo ra một query vector.

**Bước 2: Tìm kiếm Vector kết hợp Lọc Metadata (Hybrid Search)**

*   Thực hiện một lệnh `search` tới Qdrant với:
    *   **`query_vector`**: Vector từ câu hỏi của người dùng.
    *   **`limit`**: Giới hạn số lượng kết quả (ví dụ: 5).
    *   **`score_threshold`**: Ngưỡng điểm tương đồng (ví dụ: 0.75).
    *   **`filter`**: **Đây là phần cực kỳ quan trọng.**
        ```json
        {
          "must": [
            { "key": "company_id", "match": { "value": "current_company_id" } },
            { "key": "language", "match": { "value": "vi" } } // Lọc theo ngôn ngữ đã phát hiện
          ],
          "should": [ // Ưu tiên các loại dữ liệu liên quan
            { "key": "data_type", "match": { "value": "PRODUCTS" } },
            { "key": "data_type", "match": { "value": "SERVICES" } },
            { "key": "data_type", "match": { "value": "FAQ" } }
          ]
        }
        ```

**Bước 3: Tổng hợp Ngữ cảnh và Gửi cho AI**

*   Qdrant trả về 5 chunks có điểm số cao nhất và thỏa mãn điều kiện lọc.
*   Hệ thống của bạn sẽ lấy trường `content_for_embedding` từ mỗi chunk này.
*   Nối các đoạn text này lại thành một ngữ cảnh (context) duy nhất.
*   Tạo prompt cuối cùng cho Deepseek:
    ```
    Bạn là trợ lý của nhà hàng Golden Dragon. Dựa vào thông tin dưới đây, hãy trả lời câu hỏi của khách hàng một cách thân thiện.

    --- Ngữ cảnh ---
    [Nội dung content_for_embedding của chunk 1]
    [Nội dung content_for_embedding của chunk 2]
    ...
    --- Hết ngữ cảnh ---

    Câu hỏi của khách: "Quán có phở không em?"
    ```

**Bước 4: Xử lý và Hiển thị Kết quả**

*   Deepseek trả về câu trả lời dạng text, ví dụ: "Dạ có ạ, nhà hàng Golden Dragon có phục vụ món Phở Tái với giá 65,000 VND ạ. Món này có thịt bò tái mềm và nước dùng rất đậm đà. Anh/chị có muốn dùng thử không ạ?"
*   **Tối ưu hiển thị:** Vì kết quả tìm kiếm từ Qdrant có chứa cả `structured_data`, ứng dụng của bạn có thể nhận diện câu trả lời nhắc đến "Phở Tái" và hiển thị một card sản phẩm đẹp mắt (lấy từ `structured_data`) kèm theo câu trả lời của AI.

### **Vấn đề đa ngôn ngữ**

*   **Mô hình Embedding:** Phải sử dụng một mô hình embedding đa ngôn ngữ mạnh mẽ, ví dụ: `paraphrase-multilingual-mpnet-base-v2` hoặc các mô hình mới hơn từ Sentence-Transformers. Điều này đảm bảo rằng câu hỏi "Do you have pho?" và "Quán có phở không?" sẽ có vector gần giống nhau.
*   **Lưu trữ:** Mỗi chunk dữ liệu nên được lưu với một ngôn ngữ cụ thể trong `payload.language`.
*   **Tìm kiếm:** Khi tìm kiếm, bạn có thể:
    1.  Phát hiện ngôn ngữ của câu hỏi người dùng và lọc theo `payload.language`.
    2.  Nếu không chắc chắn, không lọc theo ngôn ngữ và để mô hình embedding đa ngôn ngữ tự tìm kiếm trên toàn bộ dữ liệu. Cách (1) thường cho kết quả chính xác hơn.

Bằng cách áp dụng kiến trúc này, bạn sẽ tận dụng tối đa sức mạnh của Qdrant và cung cấp cho Deepseek ngữ cảnh chất lượng cao nhất, giúp chatbot trả lời thông minh và chính xác.

Hiện tại: 

Tuyệt vời! Đây là một câu hỏi rất quan trọng để đảm bảo dự án thành công. File qdrant_company_service.py của bạn là **nền tảng rất tốt**, nhưng để đạt được hiệu quả tối ưu theo chiến lược đã phân tích, chúng ta cần thực hiện một số cải tiến quan trọng.

Hãy cùng phân tích chi tiết.

---

### **Phân tích qdrant_company_service.py**

#### **Điểm Tốt (Nền tảng vững chắc):**

1.  **Cấu trúc Class rõ ràng:** `QdrantCompanyDataService` đóng gói tất cả logic liên quan đến Qdrant, giúp code dễ quản lý và bảo trì.
2.  **Khởi tạo Collection mạnh mẽ:** Phương thức `initialize_company_collection` đã xử lý việc kiểm tra collection tồn tại và tự động tạo payload index (`_create_payload_indexes`). Đây là bước cực kỳ quan trọng để tối ưu tốc độ lọc (filter).
3.  **Sử dụng Model thống nhất:** Việc dùng `QdrantDocumentChunk` làm đầu vào cho `add_document_chunks` giúp đảm bảo dữ liệu được đưa vào Qdrant luôn có cấu trúc nhất quán.
4.  **Đã có Hybrid Search cơ bản:** Phương thức `search_company_data` đã kết hợp tìm kiếm vector với lọc metadata (`Filter(must=...)`), đây chính là cốt lõi của Hybrid Search.

#### **Điểm Cần Cải Thiện (Để đạt hiệu quả tối ưu):**

Dựa trên tài liệu RAG-INTRUCTIONS.md, đây là những điểm cần nâng cấp:

**1. Tách biệt "Nội dung cho Embedding" và "Nội dung Gốc"**

*   **Vấn đề hiện tại:** Phương thức `add_document_chunks` đang sử dụng `chunk.content` để vừa tạo embedding, vừa lưu vào payload. Điều này vi phạm nguyên tắc "Vector hóa Ngữ nghĩa" và "Lưu trữ Kép". Chúng ta cần một trường riêng biệt, được tối ưu cho AI đọc, để tạo vector.
*   **Giải pháp:**
    *   Trong `QdrantDocumentChunk` (model), thêm một trường mới: `content_for_embedding: str`.
    *   Cập nhật `add_document_chunks` để sử dụng trường mới này.

**2. Tối ưu hóa Logic Tìm kiếm để linh hoạt hơn**

*   **Vấn đề hiện tại:** `search_company_data` đang dùng `Filter(must=...)` cho tất cả các điều kiện, bao gồm cả `content_types`. Điều này có nghĩa là nếu người dùng hỏi một câu chung chung không thuộc `content_type` nào được chỉ định, sẽ không có kết quả nào được trả về.
*   **Giải pháp:** Sử dụng `should` cho `content_types` để **ưu tiên** chúng thay vì bắt buộc, giúp tìm kiếm linh hoạt hơn.

**3. Thống nhất tên trường trong Payload**

*   **Vấn đề hiện tại:** Trong code, bạn dùng `content_type`, nhưng trong tài liệu kiến trúc, chúng ta thống nhất dùng `data_type` để thể hiện vai trò của dữ liệu (PRODUCTS, SERVICES, FAQ,...).
*   **Giải pháp:** Đổi tên trường trong payload thành `data_type` để nhất quán với kiến trúc.

**4. Loại bỏ Fallback Embedding không an toàn**

*   **Vấn đề hiện tại:** `_generate_embedding` có một cơ chế fallback sử dụng `hashlib`. Đây là một **rủi ro rất lớn**. Vector tạo ra từ hash **không có ý nghĩa ngữ nghĩa**, việc đưa nó vào Qdrant sẽ làm "nhiễu" và giảm chất lượng tìm kiếm của toàn bộ hệ thống.
*   **Giải pháp:** Nếu việc tạo embedding thật bị lỗi, nên báo lỗi và dừng lại thay vì tạo ra một vector vô nghĩa.

---

### **Phương án thực hiện chi tiết:**

Đây là cách bạn có thể cập nhật file qdrant_company_service.py:

#### **Bước 1: Cập nhật `add_document_chunks`**

Thay đổi phương thức này để sử dụng `content_for_embedding`.

````python
// ...existing code...
    async def add_document_chunks(
        self, chunks: List[QdrantDocumentChunk], company_id: str
    ) -> Dict[str, Any]:
// ...existing code...
            points = []
            for chunk in chunks:
                # **THAY ĐỔI 1: Sử dụng content_for_embedding để tạo vector**
                # Logic tạo ra `content_for_embedding` (ví dụ: chuyển JSON thành câu)
                # nên được thực hiện ở lớp service cao hơn (ví dụ: admin_service) trước khi gọi hàm này.
                text_for_embedding = chunk.content_for_embedding if hasattr(chunk, 'content_for_embedding') and chunk.content_for_embedding else chunk.content
                embedding = await self._generate_embedding(text_for_embedding)

                # Create point for Qdrant / Tạo point cho Qdrant
                point = PointStruct(
                    id=chunk.chunk_id,
                    vector=embedding,
                    payload={
                        "company_id": chunk.company_id,
                        "file_id": chunk.file_id,
                        # **THAY ĐỔI 2: Đổi tên `content_type` thành `data_type` cho nhất quán**
                        "data_type": chunk.data_type.value,
                        # **THAY ĐỔI 3: Thêm `content_for_embedding` vào payload để debug và tham khảo**
                        "content_for_embedding": text_for_embedding,
                        "structured_data": chunk.structured_data,
                        "language": chunk.language.value,
                        "industry": chunk.industry.value,
                        # ... các trường khác giữ nguyên
                        "created_at": chunk.created_at.isoformat(),
                        "updated_at": chunk.updated_at.isoformat() if chunk.updated_at else None,
                    },
                )
                points.append(point)
// ...existing code...
````

#### **Bước 2: Cập nhật `search_company_data`**

Sửa đổi logic filter để linh hoạt hơn.

````python
// ...existing code...
    async def search_company_data(
        self,
        company_id: str,
        query: str,
        industry: Industry,
        # **THAY ĐỔI 4: Đổi tên tham số cho nhất quán**
        data_types: Optional[List[IndustryDataType]] = None,
        language: Language = Language.VIETNAMESE,
        limit: int = 10,
        score_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
// ...existing code...
            # Build filter conditions / Xây dựng điều kiện lọc
            must_conditions = [
                FieldCondition(key="company_id", match=MatchValue(value=company_id)),
                FieldCondition(key="industry", match=MatchValue(value=industry.value)),
            ]
            
            if language != Language.AUTO_DETECT:
                must_conditions.append(
                    FieldCondition(
                        key="language", match=MatchValue(value=language.value)
                    )
                )

            # **THAY ĐỔI 5: Sử dụng `should` để ưu tiên data_type thay vì bắt buộc**
            should_conditions = []
            if data_types:
                data_type_values = [dt.value for dt in data_types]
                should_conditions.append(
                    FieldCondition(
                        # Đổi tên trường thành `data_type`
                        key="data_type", match=models.MatchAny(any=data_type_values)
                    )
                )

            # Perform search / Thực hiện tìm kiếm
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                # **THAY ĐỔI 6: Xây dựng filter với cả `must` và `should`**
                query_filter=Filter(must=must_conditions, should=should_conditions),
                limit=limit,
// ...existing code...
            for result in search_results:
                formatted_result = {
                    "chunk_id": result.id,
                    "score": result.score,
                    # **THAY ĐỔI 7: Trả về `content_for_embedding` cho AI**
                    "content_for_rag": result.payload.get("content_for_embedding", ""),
                    "data_type": result.payload.get("data_type", ""),
                    "structured_data": result.payload.get("structured_data", {}),
// ...existing code...
````

#### **Bước 3: Cập nhật `_generate_embedding`**

Loại bỏ fallback không an toàn.

````python
// ...existing code...
    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using AI provider
        Tạo vector embedding cho text sử dụng AI provider
        """
        if not self.ai_manager:
            self.logger.error("AI Manager is not initialized. Cannot generate embeddings.")
            raise ValueError("AI Manager is not available.")

        try:
            embedding = await self.ai_manager.generate_embedding(text)
            if not embedding or len(embedding) != self.vector_size:
                raise ValueError("Generated embedding is invalid or has incorrect size.")
            return embedding
        except Exception as e:
            self.logger.error(f"❌ Failed to generate embedding for text '{text[:50]}...': {e}")
            # **THAY ĐỔI 8: Báo lỗi thay vì tạo vector giả**
            raise e
// ...existing code...
````

### **Kết luận**

File qdrant_company_service.py của bạn đang đi đúng hướng. Bằng cách thực hiện các thay đổi trên, bạn sẽ nâng cấp nó để hoàn toàn tương thích với kiến trúc RAG tối ưu đã đề ra:

1.  **Lưu trữ đúng cách:** Tách biệt rõ ràng giữa nội dung cho AI và dữ liệu gốc.
2.  **Tìm kiếm thông minh hơn:** Linh hoạt trong việc tìm kiếm, giúp bắt được nhiều ý định của người dùng hơn.
3.  **Đảm bảo chất lượng dữ liệu:** Ngăn chặn việc đưa các vector "rác" vào hệ thống.

Sau khi cập nhật file này, bạn sẽ cần điều chỉnh các lớp service gọi đến nó (như admin_service.py) để cung cấp đúng dữ liệu đầu vào (ví dụ: `content_for_embedding`).