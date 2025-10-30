# Phân tích Tính năng: Tạo Bài Thi Online (Make Test Online)

**Tác giả:** GitHub Copilot
**Ngày tạo:** 28/10/2025
**Version:** 1.0

## 1. Tổng quan

Tính năng "Make Test Online" cho phép người dùng tự động tạo ra các bài thi trắc nghiệm từ nội dung của tài liệu (PDF, DOCX) hoặc các văn bản đã được chỉnh sửa trong hệ thống. Người dùng có thể làm bài thi, xem kết quả, và chia sẻ bài thi với người khác.

## 2. Luồng Người dùng (User Flow)

1.  **Khởi tạo**:
    *   Người dùng click chuột phải vào một file đã upload (PDF, DOCX) hoặc một document đang soạn thảo.
    *   Một menu ngữ cảnh hiện ra với tùy chọn **"Make Test Online"**.

2.  **Cấu hình Bài thi**:
    *   Click vào "Make Test Online", một popup hiện ra yêu cầu người dùng nhập các thông tin:
        *   **Chủ đề/Yêu cầu** (User Query): Mô tả ngắn gọn về nội dung bài thi (ví dụ: "Tạo 10 câu hỏi về các khái niệm chính trong chương 2").
        *   **Số lượng câu hỏi** (Number of Questions): Số câu hỏi trắc nghiệm cần tạo.
        *   **Thời gian làm bài** (Time Limit): Thời gian tối đa để hoàn thành bài thi (tính bằng phút).
        *   **(Tùy chọn) Deadline**: Hạn chót để hoàn thành bài thi (chỉ áp dụng khi chia sẻ).

3.  **Tạo và Nhận Bài thi**:
    *   Người dùng nhấn "Generate Test". Frontend gửi yêu cầu đến Backend.
    *   Backend xử lý và dùng AI để tạo câu hỏi.
    *   Sau khi tạo xong, Backend lưu bài thi và trả về danh sách câu hỏi (không kèm đáp án) cho Frontend.
    *   Frontend hiển thị thông báo "Tạo bài thi thành công!" và cung cấp 2 lựa chọn: **"Làm bài ngay"** hoặc **"Để làm sau"**.

4.  **Làm bài thi**:
    *   Khi người dùng bắt đầu làm bài, Frontend hiển thị giao diện làm bài với đồng hồ đếm ngược.
    *   Người dùng chọn các đáp án và nhấn "Nộp bài" (Submit).

5.  **Chấm điểm và Xem kết quả**:
    *   Frontend gửi câu trả lời của người dùng đến Backend để chấm điểm.
    *   Backend trả về kết quả: điểm số, đáp án đúng, và giải thích chi tiết cho từng câu.

6.  **Chia sẻ và Lịch sử**:
    *   Người dùng có thể xem lại lịch sử các bài thi đã làm.
    *   Người tạo bài thi có thể chia sẻ nó với người dùng khác qua email.
    *   Người được chia sẻ nhận thông báo (in-app và email) và có thể vào làm bài thi.
    *   Người tạo có thể xem kết quả của những người đã được mình chia sẻ.

## 3. Phân tích Lựa chọn AI Provider (Gemini vs. Claude)

Cả hai model AI hàng đầu hiện nay đều có khả năng xử lý tác vụ này, nhưng có những ưu/nhược điểm riêng.

| Tiêu chí | Google Gemini (Gemini 2.5 Pro/Flash) | Anthropic Claude (Claude 3.5 Sonnet) | Lựa chọn đề xuất |
| :--- | :--- | :--- | :--- |
| **Chất lượng JSON** | **Rất mạnh**. Hỗ trợ **JSON Mode** nguyên bản, đảm bảo output luôn là một JSON hợp lệ, giảm thiểu lỗi parsing phía backend. | **Mạnh**. Có khả năng tuân thủ định dạng JSON tốt thông qua prompt engineering và tính năng Tool Use. Tuy nhiên, không có JSON mode chuyên dụng như Gemini. | **Gemini** |
| **Khả năng Suy luận** | Tốt. Có khả năng hiểu và trích xuất thông tin phức tạp để tạo câu hỏi và giải thích. | **Rất tốt**. Khả năng suy luận và giải thích "tại sao" đáp án đúng thường được đánh giá cao, phù hợp với yêu cầu giải thích đáp án. | **Claude** |
| **Context Window** | **Rất lớn** (lên đến 2 triệu tokens), cho phép xử lý các tài liệu cực kỳ dài mà không cần chia nhỏ. | Lớn (200k tokens), đủ cho hầu hết các tài liệu thông thường nhưng có thể cần chia nhỏ file lớn. | **Gemini** |
| **Chi phí** | Thường cạnh tranh hơn, đặc biệt với các model như Gemini Flash, cho tốc độ nhanh và chi phí thấp. | Chi phí có thể cao hơn một chút cho các model có khả năng suy luận tương đương. | **Gemini** |
| **Tốc độ** | Gemini Flash rất nhanh, phù hợp cho các tác vụ tương tác thời gian thực. | Claude 3.5 Sonnet cũng rất nhanh, nhưng Haiku có thể không đủ mạnh để suy luận sâu. | **Ngang nhau** |

**=> Kết luận:** **Gemini (cụ thể là Gemini 2.5 Pro)** là lựa chọn được đề xuất cho tính năng này. Lý do chính là **JSON Mode** giúp hệ thống ổn định và dễ bảo trì hơn. Context window khổng lồ cũng là một lợi thế lớn để xử lý tài liệu mà không cần logic phức tạp.

## 4. Thiết kế Kỹ thuật

### 4.1. Sơ đồ Cơ sở dữ liệu (MongoDB Collections)

1.  **`online_tests`**: Lưu thông tin về các bài thi được tạo.
    ```json
    {
      "_id": ObjectId,
      "title": "Bài test về chương 2", // Từ user query
      "source_document_id": ObjectId, // ID từ collection `documents`
      "source_file_r2_key": "path/to/file.pdf", // Hoặc key từ R2
      "creator_id": ObjectId, // User tạo bài thi
      "time_limit_minutes": 30,
      "questions": [
        {
          "question_id": ObjectId,
          "question_text": "Câu hỏi 1 là gì?",
          "options": [
            {"option_key": "A", "option_text": "Đáp án A"},
            {"option_key": "B", "option_text": "Đáp án B"}
          ],
          "correct_answer_key": "A",
          "explanation": "Đáp án A đúng vì..."
        }
      ],
      "created_at": ISODate,
      "updated_at": ISODate
    }
    ```

2.  **`test_submissions`**: Lưu kết quả mỗi lần người dùng làm bài.
    ```json
    {
      "_id": ObjectId,
      "test_id": ObjectId, // Tham chiếu đến `online_tests`
      "user_id": ObjectId, // User làm bài
      "user_answers": [
        {"question_id": ObjectId, "selected_answer_key": "B"}
      ],
      "score": 80.0, // Điểm số (ví dụ: 8/10 -> 80.0)
      "time_taken_seconds": 1200,
      "submitted_at": ISODate,
      "is_passed": true
    }
    ```

3.  **`test_shares`**: Quản lý việc chia sẻ bài thi.
    ```json
    {
      "_id": ObjectId,
      "test_id": ObjectId,
      "sharer_id": ObjectId, // Người chia sẻ
      "sharee_email": "user@example.com",
      "sharee_id": ObjectId, // (Optional) ID của người được chia sẻ nếu họ đã đăng ký
      "deadline": ISODate, // (Optional) Hạn chót làm bài
      "status": "pending", // pending, accepted, completed, expired
      "shared_at": ISODate
    }
    ```

4.  **`notifications`**: Lưu thông báo trong ứng dụng.
    *   Sử dụng collection `notifications` hiện có, thêm type `online_test_share`.

### 4.2. Thiết kế API Endpoints

| Method | Endpoint | Mô tả | Request Body | Response Body |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/api/v1/tests/generate` | **Tạo bài thi mới** từ tài liệu hoặc file. | `GenerateTestRequest` | `TestQuestionsResponse` |
| **POST** | `/api/v1/tests/{test_id}/submit` | **Nộp bài thi** và nhận kết quả chấm điểm. | `SubmitTestRequest` | `TestResultResponse` |
| **GET** | `/api/v1/tests/{test_id}` | **Lấy thông tin bài thi** để bắt đầu làm bài (chỉ câu hỏi). | - | `TestQuestionsResponse` |
| **GET** | `/api/v1/me/tests` | **Lấy danh sách các bài thi** của user (đã tạo, được chia sẻ). | - | `List<TestSummary>` |
| **GET** | `/api/v1/me/submissions/{submission_id}` | **Xem lại kết quả** một lần làm bài cụ thể. | - | `TestResultResponse` |
| **POST** | `/api/v1/tests/{test_id}/share` | **Chia sẻ bài thi** với người dùng khác. | `ShareTestRequest` | `{"success": true}` |
| **GET** | `/api/v1/tests/{test_id}/analytics` | **Xem thống kê** kết quả của những người được chia sẻ (chỉ cho người tạo). | - | `TestAnalyticsResponse` |

### 4.3. Định nghĩa DTO (Data Transfer Objects)

*   **`GenerateTestRequest`**:
    *   `source_type`: "document" | "file"
    *   `source_id`: string (document_id hoặc R2 key)
    *   `user_query`: string
    *   `num_questions`: int
    *   `time_limit_minutes`: int

*   **`TestQuestionsResponse`**:
    *   `test_id`: string
    *   `title`: string
    *   `time_limit_minutes`: int
    *   `questions`: `List<Question>` (chỉ có `question_id`, `question_text`, `options`)

*   **`SubmitTestRequest`**:
    *   `user_answers`: `List<{question_id, selected_answer_key}>`

*   **`TestResultResponse`**:
    *   `submission_id`: string
    *   `score`: float
    *   `results`: `List<{question_id, your_answer, correct_answer, explanation}>`

*   **`ShareTestRequest`**:
    *   `sharee_emails`: `List<string>`
    *   `deadline`: `ISODate` (optional)

*   **`TestAnalyticsResponse`**:
    *   `test_title`: string
    *   `submissions`: `List<{sharee_email, score, submitted_at}>`

## 5. Prompt Engineering cho AI

Đây là một ví dụ về prompt gửi cho Gemini để tạo bài thi.

```text
You are an expert in creating educational assessments. Your task is to generate a multiple-choice quiz based on the provided document and user query.

**CRITICAL INSTRUCTIONS:**
1.  Your output MUST be a single, valid JSON object.
2.  The JSON object must conform to the following structure:
    {
      "questions": [
        {
          "question_text": "string",
          "options": [
            {"option_key": "A", "option_text": "string"},
            {"option_key": "B", "option_text": "string"},
            {"option_key": "C", "option_text": "string"},
            {"option_key": "D", "option_text": "string"}
          ],
          "correct_answer_key": "string",
          "explanation": "string (Explain WHY the correct answer is right, based on the document)."
        }
      ]
    }
3.  Generate exactly {{num_questions}} questions.
4.  The questions must be relevant to the user's query: "{{user_query}}".
5.  All information used to create questions, answers, and explanations must come directly from the provided document.

**DOCUMENT CONTENT:**
---
{{document_content}}
---

Now, generate the quiz based on the instructions and the document provided.
```

Bằng cách sử dụng **JSON Mode** của Gemini, chúng ta có thể đảm bảo rằng kết quả trả về luôn tuân thủ cấu trúc đã định nghĩa, giúp cho việc phát triển backend trở nên đáng tin cậy hơn.
