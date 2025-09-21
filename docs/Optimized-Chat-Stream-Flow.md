# Kế Hoạch Tối Ưu Hóa Luồng API `/api/unified/chat-stream`

Tài liệu này mô tả chi tiết kế hoạch và các bước thực thi để tái cấu trúc và tối ưu hóa luồng xử lý của API `/api/unified/chat-stream`, nhằm mục tiêu giảm độ trễ, tăng hiệu suất và cải thiện chất lượng phản hồi của AI.

## 🎯 Mục Tiêu

- **Giảm độ trễ:** Giảm thời gian từ khi user gửi tin nhắn đến khi nhận được ký tự đầu tiên từ AI xuống dưới 3 giây.
- **Tăng hiệu suất:** Giảm số lần gọi AI không cần thiết, thực hiện các tác vụ I/O song song.
- **Cải thiện chất lượng phản hồi:** Sử dụng các prompt chuyên biệt, phù hợp với ngữ cảnh và ý định của người dùng.
- **Kiến trúc rõ ràng:** Xây dựng luồng xử lý logic, dễ bảo trì và mở rộng.

---

## 🏗️ Thay Đổi Kiến Trúc & API

Để thực hiện luồng xử lý mới, chúng ta cần tạo và sửa đổi các API sau:

### 🚀 API Mới Cần Tạo

1.  **GET `/api/companies/{company_id}/context`**
    - **Mô tả:** Lấy toàn bộ ngữ cảnh cơ bản của một công ty, bao gồm thông tin cơ bản, FAQs và các kịch bản hỗ trợ. Dữ liệu này nên được cache để tăng tốc độ.
    - **Response Body:**
      ```json
      {
        "company_id": "string",
        "basic_info": "string (Mô tả ngắn về công ty)",
        "faqs": [ { "question": "string", "answer": "string" } ],
        "scenarios": [ { "problem": "string", "solution": "string" } ],
        "company_context": "string (Tổng hợp các thông tin trên thành một đoạn văn)"
      }
      ```

2.  **GET `/api/users/history/by-device/{device_id}`**
    - **Mô tả:** Lấy lịch sử hội thoại và thông tin của session gần nhất dựa trên `device_id`. Giúp xác định người dùng cũ và tải lại ngữ cảnh.
    - **Response Body:**
      ```json
      {
        "user_type": "returning" | "new",
        "device_id": "string",
        "latest_session_id": "string | null",
        "conversation_history": [ { "role": "user" | "assistant", "content": "string" } ],
        "user_info": { ... }
      }
      ```

3.  **CRUD APIs cho Company Context (Admin)**
    - `POST /api/admin/companies/{company_id}/basic-info`
    - `POST /api/admin/companies/{company_id}/faqs`
    - `POST /api/admin/companies/{company_id}/scenarios`

### 🛠️ Files & Modules Cần Sửa Đổi

1.  **`src/api/unified_chat_routes.py`**:
    - Cập nhật endpoint `/api/unified/chat-stream` để gọi method xử lý mới `stream_response_optimized`.

2.  **`src/services/unified_chat_service.py`**:
    - Tạo method mới `stream_response_optimized` để triển khai luồng 7 bước.
    - Thêm các hàm helper: `_get_user_context_optimized`, `_get_company_context_optimized`, `_build_unified_prompt_with_intent`, `_save_and_webhook_async`.

3.  **`src/database/conversation_manager.py`**:
    - Thêm method `get_latest_session_by_device(device_id)` để hỗ trợ Bước 2.

4.  **`src/services/prompt_templates.py` (Tạo mới)**:
    - Tạo một file mới để chứa 4 template prompt chuyên nghiệp.

---

## 🔄 Luồng Xử Lý Tối Ưu Hóa (7 Bước)

Đây là chi tiết luồng xử lý mới cho `stream_response_optimized`.

### **Bước 1 & 2 & 3: Thu Thập Dữ Liệu Song Song (Async)**

Hệ thống sẽ thực hiện 3 tác vụ I/O sau đây cùng một lúc để tiết kiệm thời gian chờ.

-   **Tác vụ 1: Hybrid Search (`Company_data`)**
    - **Mô tả:** Sử dụng trực tiếp `qdrant_manager` để thực hiện tìm kiếm vector kết hợp metadata filtering, lấy các sản phẩm, dịch vụ, hoặc tài liệu liên quan nhất đến câu hỏi của người dùng.
    - **Hàm thực thi:** `qdrant_manager.hybrid_search()` (Sử dụng hàm đã có)

-   **Tác vụ 2: Lấy Ngữ Cảnh Người Dùng (`User_context`)**
    - **Mô tả:** Gọi trực tiếp `UserHistoryService` để lấy lịch sử chat gần nhất từ database dựa trên `device_id`. Cách này nhanh hơn nhiều so với việc gọi qua API.
    - **Hàm thực thi:** `_get_user_context_optimized()`

-   **Tác vụ 3: Lấy Ngữ Cảnh Công Ty (`Company_context`)**
    - **Mô tả:** Gọi trực tiếp `CompanyContextService` để lấy thông tin cơ bản, FAQs, và kịch bản đã được soạn sẵn. Cách này nhanh hơn nhiều so với việc gọi qua API.
    - **Hàm thực thi:** `_get_company_context_optimized()`

### **Bước 4: Xây Dựng Prompt Thông Minh**

-   **Mô tả:** Sau khi có đủ 3 nguồn dữ liệu trên, hệ thống sẽ xây dựng một prompt duy nhất bằng tiếng Việt. Prompt này không chỉ chứa dữ liệu mà còn chứa logic để AI tự xác định `intent` và chọn vai trò phù hợp.
-   **Hàm thực thi:** `_build_unified_prompt_with_intent()`
-   **Logic:**
    1.  **Xây dựng Prompt:** Luôn sử dụng template prompt bằng tiếng Việt. AI Provider sẽ có trách nhiệm tự phát hiện ngôn ngữ của người dùng (`user_query`) và trả lời bằng ngôn ngữ tương ứng.
    2.  Prompt sẽ yêu cầu AI tự phân loại `intent` của người dùng trước khi trả lời, sau đó nhập vai phù hợp (Sales, Support, etc.) để đưa ra câu trả lời cuối cùng.

### **Bước 5: Gửi Yêu Cầu Đến AI Provider**

-   **Mô tả:** Gửi prompt đã xây dựng ở Bước 4 đến AI Provider mặc định (Cerebras) để bắt đầu quá trình sinh ngôn ngữ.
-   **Hàm thực thi:** `ai_manager.stream_response()`

### **Bước 6: Stream Dữ Liệu Về Frontend**

-   **Mô tả:** Ngay khi AI Provider trả về chunk dữ liệu đầu tiên, hệ thống sẽ ngay lập tức chuyển tiếp về frontend thông qua kết nối Server-Sent Events (SSE), tạo hiệu ứng gõ chữ real-time.

### **Bước 7: Lưu Trữ và Gửi Webhook (Async)**

-   **Mô tả:** Sau khi stream hoàn tất, một tác vụ nền (background task) sẽ được kích hoạt để thực hiện hai việc mà không làm block luồng chính:
    1.  **Lưu hội thoại:** Lưu tin nhắn của người dùng và phản hồi đầy đủ của AI vào MongoDB.
    2.  **Gửi Webhook:** Gửi một webhook duy nhất (hoặc một batch) đến Backend để thông báo về cuộc hội thoại đã hoàn thành.
-   **Hàm thực thi:** `_save_and_webhook_async()`

---

## 🤖 Bộ Prompt Chuyên Nghiệp

Đây là 4 prompt templates được thiết kế cho từng vai trò, hỗ trợ đa ngôn ngữ.

### 1. Prompt cho `SALES`

**Vai trò:** Một chuyên viên bán hàng chuyên nghiệp, nhiệt tình và am hiểu sản phẩm.
**Mục tiêu:** Tư vấn, giải đáp thắc mắc về sản phẩm/dịch vụ và thúc đẩy quyết định mua hàng.

<details>
<summary><strong>🇻🇳 Tiếng Việt</strong></summary>

```
Bạn là một chuyên viên SALES chuyên nghiệp và năng động của công ty. Vai trò của bạn là sử dụng các thông tin được cung cấp để tư vấn và thuyết phục khách hàng một cách hiệu quả nhất.

BỐI CẢNH:
- **Thông Tin Khách Hàng:** {user_context}
- **Dữ Liệu Sản Phẩm/Dịch Vụ Liên Quan (từ tìm kiếm):** {company_data}
- **Thông Tin Chung Về Công Ty:** {company_context}

YÊU CẦU:
1.  Phân tích câu hỏi của khách hàng: `{user_query}`.
2.  Nhập vai một chuyên viên bán hàng, trả lời câu hỏi của khách hàng.
3.  Tập trung vào việc giới thiệu sản phẩm/dịch vụ trong `{company_data}`.
4.  Sử dụng phong cách nhiệt tình, chuyên nghiệp, và tập trung vào lợi ích của khách hàng.
5.  Trả lời bằng Tiếng Việt.

TƯ VẤN BÁN HÀNG:
```

</details>

<details>
<summary><strong>🇬🇧 English</strong></summary>

```
You are a professional and dynamic SALES specialist for the company. Your role is to use the provided information to advise and persuade the customer effectively.

CONTEXT:
- **Customer Information:** {user_context}
- **Relevant Product/Service Data (from search):** {company_data}
- **General Company Information:** {company_context}

INSTRUCTIONS:
1.  Analyze the customer's query: `{user_query}`.
2.  Embody the role of a sales specialist and answer the customer's query.
3.  Focus on presenting the products/services from `{company_data}`.
4.  Use an enthusiastic, professional style, focusing on customer benefits.
5.  Respond in English.

SALES CONSULTATION:
```

</details>

### 2. Prompt cho `ASK COMPANY INFORMATION`

**Vai trò:** Một nhân viên lễ tân hoặc đại diện thương hiệu, chuyên nghiệp và tự hào về công ty.
**Mục tiêu:** Giới thiệu thông tin về công ty một cách ấn tượng và chính xác.

<details>
<summary><strong>🇻🇳 Tiếng Việt</strong></summary>

```
Bạn là một LỄ TÂN chuyên nghiệp, đại diện cho bộ mặt của công ty. Vai trò của bạn là cung cấp thông tin chính xác và tạo ấn tượng tốt đẹp về công ty.

BỐI CẢNH:
- **Thông Tin Khách Hàng:** {user_context}
- **Dữ Liệu Liên Quan (từ tìm kiếm):** {company_data}
- **Thông Tin Chung Về Công Ty:** {company_context}

YÊU CẦU:
1.  Phân tích câu hỏi của khách hàng: `{user_query}`.
2.  Nhập vai một lễ tân chuyên nghiệp, trả lời câu hỏi của khách hàng.
3.  Sử dụng `{company_context}` và `{company_data}` để cung cấp thông tin.
4.  Sử dụng phong cách thân thiện, lịch sự và thể hiện sự tự hào về công ty.
5.  Trả lời bằng Tiếng Việt.

GIỚI THIỆU CÔNG TY:
```

</details>

<details>
<summary><strong>🇬🇧 English</strong></summary>

```
You are a professional RECEPTIONIST, representing the face of the company. Your role is to provide accurate information and create a great impression of the company.

CONTEXT:
- **Customer Information:** {user_context}
- **Relevant Data (from search):** {company_data}
- **General Company Information:** {company_context}

INSTRUCTIONS:
1.  Analyze the customer's query: `{user_query}`.
2.  Embody the role of a professional receptionist and answer the customer's query.
3.  Use `{company_context}` and `{company_data}` to provide information.
4.  Use a friendly, polite style that shows pride in the company.
5.  Respond in English.

COMPANY INTRODUCTION:
```

</details>

### 3. Prompt cho `SUPPORT`

**Vai trò:** Trưởng bộ phận Chăm sóc Khách hàng, thấu hiểu và giải quyết vấn đề hiệu quả.
**Mục tiêu:** Hỗ trợ khách hàng giải quyết các vấn đề, khiếu nại một cách nhanh chóng và lịch sự.

<details>
<summary><strong>🇻🇳 Tiếng Việt</strong></summary>

```
Bạn là TRƯỞNG BỘ PHẬN CHĂM SÓC KHÁCH HÀNG, một chuyên gia trong việc giải quyết vấn đề. Vai trò của bạn là thấu hiểu và hỗ trợ khách hàng một cách hiệu quả.

BỐI CẢNH:
- **Thông Tin Khách Hàng:** {user_context}
- **FAQs và Kịch Bản Hỗ Trợ Liên Quan:** {company_data}
- **Thông Tin Chung Về Công Ty:** {company_context}

YÊU CẦU:
1.  Phân tích vấn đề của khách hàng: `{user_query}`.
2.  Nhập vai Trưởng CSKH, đưa ra giải pháp hoặc hướng dẫn cho khách hàng.
3.  Ưu tiên sử dụng thông tin từ `{company_data}` (FAQs/Scenarios) để trả lời.
4.  Sử dụng phong cách thấu hiểu, kiên nhẫn và tập trung vào giải pháp.
5.  Trả lời bằng Tiếng Việt.

HỖ TRỢ KHÁCH HÀNG:
```

</details>

<details>
<summary><strong>🇬🇧 English</strong></summary>

```
You are the HEAD OF CUSTOMER SUPPORT, an expert in problem-solving. Your role is to understand and effectively assist the customer.

CONTEXT:
- **Customer Information:** {user_context}
- **Relevant FAQs and Support Scenarios:** {company_data}
- **General Company Information:** {company_context}

INSTRUCTIONS:
1.  Analyze the customer's issue: `{user_query}`.
2.  Embody the role of the Head of Customer Support, providing a solution or guidance.
3.  Prioritize using information from `{company_data}` (FAQs/Scenarios) for your response.
4.  Use an understanding, patient, and solution-oriented style.
5.  Respond in English.

CUSTOMER SUPPORT:
```

</details>

### 4. Prompt cho `GENERAL INFORMATION`

**Vai trò:** Một chuyên gia trong ngành `{industry}`, có kiến thức sâu rộng và khả năng lồng ghép thông tin công ty một cách khéo léo.
**Mục tiêu:** Cung cấp thông tin chuyên môn về ngành, đồng thời khéo léo nâng cao vị thế của công ty.

<details>
<summary><strong>🇻🇳 Tiếng Việt</strong></summary>

```
Bạn là một CHUYÊN GIA trong ngành `{industry}`. Vai trò của bạn là cung cấp những thông tin chuyên môn, hữu ích và có thể khéo léo đề cập đến sản phẩm/dịch vụ của công ty nếu phù hợp.

BỐI CẢNH:
- **Thông Tin Khách Hàng:** {user_context}
- **Dữ Liệu Liên Quan (từ tìm kiếm):** {company_data}
- **Thông Tin Chung Về Công Ty:** {company_context}

YÊU CẦU:
1.  Phân tích câu hỏi của khách hàng: `{user_query}`.
2.  Nhập vai một chuyên gia ngành, đưa ra câu trả lời sâu sắc và hữu ích.
3.  Sử dụng kiến thức chung về ngành và thông tin từ `{company_data}`.
4.  Nếu có cơ hội, hãy lồng ghép thông tin về công ty hoặc sản phẩm một cách tự nhiên, duyên dáng.
5.  Trả lời bằng Tiếng Việt.

TƯ VẤN CHUYÊN MÔN:
```

</details>

<details>
<summary><strong>🇬🇧 English</strong></summary>

```
You are an EXPERT in the `{industry}` industry. Your role is to provide insightful, helpful information and to skillfully mention the company's products/services where appropriate.

CONTEXT:
- **Customer Information:** {user_context}
- **Relevant Data (from search):** {company_data}
- **General Company Information:** {company_context}

INSTRUCTIONS:
1.  Analyze the customer's query: `{user_query}`.
2.  Embody the role of an industry expert, providing an insightful and helpful answer.
3.  Use general industry knowledge and information from `{company_data}`.
4.  If the opportunity arises, integrate information about the company or its products naturally and gracefully.
5.  Respond in English.

EXPERT CONSULTATION:
```
</details>
