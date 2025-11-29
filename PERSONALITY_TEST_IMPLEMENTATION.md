# Diagnostic & Academic Test Implementation Specs

## 1. Overview
Hệ thống hỗ trợ 2 loại hình kiểm tra chính:
1.  **Academic Test (Kiểm tra kiến thức)**: Có đáp án đúng/sai, chấm điểm, đánh giá năng lực.
2.  **Diagnostic Test (Chẩn đoán/Tính cách)**: Không có đáp án đúng/sai, phân loại người dùng dựa trên xu hướng lựa chọn (Diagnostic Result).

*Note: Thuật ngữ "Personality" cũ được thay thế thống nhất bằng "Diagnostic".*

---

## 2. Implementation Status - ALL PHASES COMPLETED ✅

### ✅ Phase 1: Manual Test Creation (COMPLETED)
- **Manual Test Creation** (`POST /api/tests/manual`): Hỗ trợ `test_category` field.
- **Validation Logic**: `correct_answer_key` là optional cho Diagnostic tests.
- **AI Evaluation Service**: Prompt rẽ nhánh cho Academic vs Diagnostic.
- **Database Schema**: Thêm `test_category` vào collection `online_tests`.

### ✅ Phase 2: AI Test Generation (COMPLETED)
- **Updated `POST /api/tests/generate`**: Thêm `test_category` field, AI tạo `evaluation_criteria` cho diagnostic tests.
- **New `POST /api/tests/generate/general`**: Tạo test từ topic (không cần file).
- **Service Layer**: `test_generator_service.py` hỗ trợ cả academic và diagnostic prompts.
- **Database**: Lưu `evaluation_criteria` cho diagnostic tests.

### ✅ Phase 3: Test Submission & Point System (COMPLETED)
- **`POST /api/tests/{test_id}/submit`**:
  - Diagnostic tests: Không tính correct/incorrect.
  - Trừ 1 điểm để AI đánh giá diagnostic result.
  - Nếu không đủ điểm: Vẫn lưu submission nhưng `has_ai_evaluation = false`.
- **Point Deduction Logic**: Kiểm tra `users` collection, tạo user profile nếu chưa có.
- **Response Fields**: Thêm `is_diagnostic_test`, `has_ai_evaluation`, `message`.

### ✅ Phase 4: AI Evaluation Service (COMPLETED)
- **`gemini_test_evaluation_service.py`**:
  - Sử dụng `evaluation_criteria` từ DB cho diagnostic tests.
  - Prompt khác biệt giữa academic (strengths/weaknesses) và diagnostic (result_title/traits).
  - Terminology updated: `is_personality_test` → `is_diagnostic_test`.

### ✅ Phase 5: GET Endpoints (COMPLETED)
- **`GET /api/tests/me/tests`**: Thêm `test_category` field.
- **`GET /api/tests/me/submissions`**: Thêm `test_category`, `is_diagnostic_test`, `has_ai_evaluation`.
- **`GET /api/tests/me/submissions/{id}`**: Hiển thị đầy đủ diagnostic fields + message nếu thiếu AI eval.

### ✅ Phase 6: Additional Updates (COMPLETED)
- **`PUT /api/tests/{test_id}/questions`**: Validation tôn trọng `test_category`.
- **`POST /api/tests/{test_id}/duplicate`**: Copy `test_category`, `evaluation_criteria`, `topic`.

---

## 3. Data Models

### 📦 Request Models

---

## 4. API Technical Specifications

### 4.1. POST /api/tests/generate - Generate Test from File/Document

**Endpoint**: `POST /api/v1/tests/generate`

**Purpose**: Tạo test từ file (PDF/DOCX) hoặc document có sẵn, hỗ trợ cả Academic và Diagnostic tests.

#### Request Payload
```json
{
  "title": "string (5-200 chars, required)",
  "description": "string (optional, max 1000 chars)",
  "test_category": "academic | diagnostic (default: academic)",
  "language": "vi | en (default: vi)",
  "difficulty": "easy | medium | hard (optional)",
  "num_questions": "number (1-100, required)",
  "time_limit_minutes": "number (1-300, default: 30)",
  "max_retries": "number (1-10, default: 3)",
  "passing_score": "number (0-100, default: 70)",
  "deadline": "ISO datetime string (optional)",
  "show_answers_timing": "immediate | after_deadline (default: immediate)",
  "num_options": "number (2-10, default: 4)",
  "num_correct_answers": "number (0-10, default: 1)",
  "source_type": "file | document (required)",
  "file_id": "string (required if source_type=file)",
  "document_id": "string (required if source_type=document)"
}
```

#### Response (Success - 200 OK)
```json
{
  "test_id": "string (MongoDB ObjectId)",
  "status": "pending | generating | ready | failed",
  "message": "Test generation started in background",
  "test_category": "academic | diagnostic",
  "title": "string",
  "estimated_time_seconds": "number (optional)"
}
```

#### Behavior Notes
- **Academic tests**: AI tạo questions với `correct_answer_key`, không có `evaluation_criteria`.
- **Diagnostic tests**: AI tạo questions không có `correct_answer_key`, có `evaluation_criteria` (JSON string chứa result_types và mapping_rules).

---

### 4.1.1. GET /api/tests/{test_id} - Get Test Details (Owner View)

**Endpoint**: `GET /api/v1/tests/{test_id}`

**Purpose**: Lấy chi tiết test (owner view trả về đầy đủ thông tin bao gồm evaluation_criteria).

#### Response (Success - 200 OK) - Owner View
```json
{
  "success": true,
  "test_id": "string",
  "view_type": "owner",
  "is_owner": true,
  "access_type": "owner",
  "title": "string",
  "description": "string",
  "test_category": "academic | diagnostic",
  "is_active": "boolean",
  "status": "ready | pending | generating | failed",
  "max_retries": "number",
  "time_limit_minutes": "number",
  "passing_score": "number",
  "deadline": "ISO datetime string (nullable)",
  "show_answers_timing": "immediate | after_deadline",
  "num_questions": "number",
  "questions": [
    {
      "question_id": "string",
      "question_text": "string",
      "question_type": "mcq | essay",
      "options": ["array (for MCQ)"],
      "correct_answer_keys": ["array (for academic MCQ)"],
      "explanation": "string"
    }
  ],
  "creation_type": "manual | ai_generated",
  "test_language": "vi | en",
  "evaluation_criteria": "string (JSON string, only for diagnostic tests) - Contains result_types and mapping_rules for AI evaluation",
  "total_submissions": "number",
  "is_published": "boolean",
  "marketplace_config": "object (if published)",
  "created_at": "ISO datetime string",
  "updated_at": "ISO datetime string"
}
```

#### Evaluation Criteria Structure (for Diagnostic Tests)
Trường `evaluation_criteria` là JSON string chứa:
```json
{
  "result_types": [
    {
      "type_id": "string (e.g., 'high_iq', 'medium_iq', 'genius')",
      "title": "string (e.g., 'Thiên tài', 'Trí tuệ xuất sắc')",
      "description": "string (Mô tả chi tiết về loại kết quả này)",
      "traits": ["array of strings (Các đặc điểm của loại này)"]
    }
  ],
  "mapping_rules": "string (Chi tiết cách ánh xạ từ câu trả lời sang result_type, ví dụ: 'Nếu trả lời đúng 18-20/20 câu -> genius, 15-17/20 -> high_iq, ...')"
}
```

**Behavior Notes:**
- `evaluation_criteria` chỉ có giá trị với diagnostic tests
- AI sử dụng evaluation_criteria này để phân loại user khi submit test
- Owner có thể thấy tiêu chí này để hiểu cách AI sẽ đánh giá

---

### 4.2. POST /api/tests/generate/general - Generate Test from General Knowledge

**Endpoint**: `POST /api/v1/tests/generate/general`

**Purpose**: Tạo test từ kiến thức tổng quát của AI, không cần file nguồn. Hỗ trợ cả Academic và Diagnostic tests.

#### Request Payload
```json
{
  "title": "string (5-200 chars, required)",
  "description": "string (optional, max 1000 chars)",
  "topic": "string (3-200 chars, required) - Example: 'Leadership Styles', 'Python Programming', 'MBTI Diagnostic'",
  "user_query": "string (10-500 chars, required) - Detailed instructions for AI - Example: 'Focus on modern leadership theories', 'Include questions about decorators and generators'",
  "test_category": "academic | diagnostic (default: academic)",
  "language": "vi | en (default: vi)",
  "difficulty": "easy | medium | hard (optional)",
  "num_questions": "number (1-100, required)",
  "time_limit_minutes": "number (1-300, default: 30)",
  "max_retries": "number (1-10, default: 3)",
  "passing_score": "number (0-100, default: 70)",
  "deadline": "ISO datetime string (optional)",
  "show_answers_timing": "immediate | after_deadline (default: immediate)",
  "num_options": "number (2-10, default: 4)",
  "num_correct_answers": "number (0-10, default: 1)"
}
```

#### Response (Success - 200 OK)
```json
{
  "test_id": "string (MongoDB ObjectId)",
  "status": "pending",
  "message": "Test generation started in background",
  "test_category": "academic | diagnostic",
  "topic": "string",
  "title": "string",
  "source_type": "general_knowledge",
  "estimated_time_seconds": 30
}
```

#### Error Responses

**400 Bad Request** - Validation errors
```json
{
  "detail": "Validation error message"
}
```

**401 Unauthorized** - Missing or invalid token
```json
{
  "detail": "Unauthorized"
}
```

**429 Too Many Requests** - Rate limit exceeded
```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

#### Behavior Notes
- **Academic tests**: AI generate questions testing knowledge về topic, với correct answers.
- **Diagnostic tests**: AI generate questions revealing personality/preferences liên quan đến topic, kèm evaluation_criteria.
- **Background Processing**: Test được tạo asynchronously, client cần poll `GET /api/tests/{test_id}` để check status.

---

### 4.3. POST /api/tests/{test_id}/submit - Submit Test Answers

**Endpoint**: `POST /api/v1/tests/{test_id}/submit`

**Purpose**: Submit câu trả lời và nhận kết quả đánh giá. Hỗ trợ cả Academic và Diagnostic tests.

#### Request Payload
```json
{
  "session_id": "string (required) - From /start endpoint",
  "answers": {
    "question_1": "A",
    "question_2": "B",
    "essay_question_1": "Long text answer..."
  },
  "time_taken_seconds": "number (optional)"
}
```

#### Response (Success - 200 OK)

**For Academic Tests**:
```json
{
  "submission_id": "string (MongoDB ObjectId)",
  "test_id": "string",
  "test_category": "academic",
  "is_diagnostic_test": false,
  "has_ai_evaluation": true,
  "score": "number (0-100)",
  "score_percentage": "number (0-100)",
  "total_questions": "number",
  "correct_answers": "number",
  "is_passed": "boolean",
  "attempt_number": "number",
  "time_taken_seconds": "number",
  "grading_status": "auto_graded | pending_grading | fully_graded",
  "submitted_at": "ISO datetime string",
  "results": [
    {
      "question_id": "string",
      "question_text": "string",
      "question_type": "mcq | essay",
      "your_answer": "string",
      "correct_answer": "string (for MCQ)",
      "is_correct": "boolean (for MCQ)",
      "explanation": "string",
      "ai_feedback": "string (personalized feedback)"
    }
  ],
  "overall_evaluation": {
    "strengths": ["string"],
    "weaknesses": ["string"],
    "recommendations": ["string"],
    "study_plan": "string"
  }
}
```

**For Diagnostic Tests (with sufficient points)**:
```json
{
  "submission_id": "string (MongoDB ObjectId)",
  "test_id": "string",
  "test_category": "diagnostic",
  "is_diagnostic_test": true,
  "has_ai_evaluation": true,
  "total_questions": "number",
  "attempt_number": "number",
  "time_taken_seconds": "number",
  "submitted_at": "ISO datetime string",
  "points_deducted": 1,
  "remaining_points": "number",
  "results": [
    {
      "question_id": "string",
      "question_text": "string",
      "question_type": "mcq",
      "your_answer": "string",
      "is_correct": null,
      "explanation": "string",
      "ai_feedback": "string (insight about choice)"
    }
  ],
  "overall_evaluation": {
    "result_title": "string - Example: 'The Creative Visionary'",
    "result_description": "string - Detailed description of diagnostic type",
    "personality_traits": ["string", "string"],
    "advice": ["string", "string"]
  }
}
```

**For Diagnostic Tests (insufficient points)**:
```json
{
  "submission_id": "string (MongoDB ObjectId)",
  "test_id": "string",
  "test_category": "diagnostic",
  "is_diagnostic_test": true,
  "has_ai_evaluation": false,
  "total_questions": "number",
  "attempt_number": "number",
  "time_taken_seconds": "number",
  "submitted_at": "ISO datetime string",
  "points_deducted": 0,
  "remaining_points": 0,
  "message": "Câu trả lời của bạn đã được lưu nhưng chưa có đánh giá AI do không đủ điểm. Bạn cần 1 điểm để nhận đánh giá AI cho bài test chẩn đoán này.",
  "results": [
    {
      "question_id": "string",
      "question_text": "string",
      "question_type": "mcq",
      "your_answer": "string",
      "is_correct": null
    }
  ]
}
```

#### Error Responses

**404 Not Found** - Test không tồn tại
```json
{
  "detail": "Test not found"
}
```

**400 Bad Request** - Session invalid hoặc đã complete
```json
{
  "detail": "Session already completed"
}
```

**403 Forbidden** - Không có quyền truy cập
```json
{
  "detail": "Access denied"
}
```

#### Behavior Notes - Point System for Diagnostic Tests
- **Academic tests**: Không trừ điểm, AI evaluation miễn phí.
- **Diagnostic tests**:
  - Trừ **1 điểm** để nhận AI evaluation (personality analysis).
  - Nếu user có đủ ≥1 điểm: Trừ điểm → Lưu submission → Gọi AI → Trả về full evaluation.
  - Nếu user có 0 điểm: Không trừ → Lưu submission → KHÔNG gọi AI → Trả về `has_ai_evaluation: false` + message.
  - User profile tự động được tạo nếu chưa tồn tại trong `users` collection.

---

### 4.4. GET /api/tests/me/tests - Get My Created Tests

**Endpoint**: `GET /api/v1/tests/me/tests`

**Purpose**: Lấy danh sách tests do user tạo, có phân trang.

#### Query Parameters
- `limit`: number (default: 10, max: 100)
- `offset`: number (default: 0)

#### Response (Success - 200 OK)
```json
{
  "tests": [
    {
      "test_id": "string",
      "title": "string",
      "description": "string",
      "test_category": "academic | diagnostic",
      "num_questions": "number",
      "time_limit_minutes": "number",
      "status": "ready | pending | generating | failed | draft",
      "is_active": "boolean",
      "is_public": "boolean",
      "created_at": "ISO datetime string",
      "updated_at": "ISO datetime string",
      "total_submissions": "number"
    }
  ],
  "total": "number",
  "limit": "number",
  "offset": "number",
  "has_more": "boolean"
}
```

---

### 4.5. GET /api/tests/me/submissions - Get My Test Submissions

**Endpoint**: `GET /api/v1/tests/me/submissions`

**Purpose**: Lấy danh sách submissions của user, grouped by test.

#### Response (Success - 200 OK)
```json
{
  "tests": [
    {
      "test_id": "string",
      "test_title": "string",
      "test_description": "string",
      "test_category": "academic | diagnostic",
      "test_creator_id": "string",
      "is_owner": "boolean",
      "total_attempts": "number",
      "best_score": "number (null for diagnostic)",
      "best_score_percentage": "number (null for diagnostic)",
      "latest_attempt_at": "ISO datetime string",
      "submission_history": [
        {
          "submission_id": "string",
          "attempt_number": "number",
          "score": "number (null for diagnostic)",
          "score_percentage": "number (null for diagnostic)",
          "is_passed": "boolean",
          "is_diagnostic_test": "boolean",
          "has_ai_evaluation": "boolean",
          "grading_status": "auto_graded | pending_grading | fully_graded",
          "submitted_at": "ISO datetime string"
        }
      ]
    }
  ]
}
```

---

### 4.6. GET /api/tests/me/submissions/{submission_id} - Get Submission Detail

**Endpoint**: `GET /api/v1/tests/me/submissions/{submission_id}`

**Purpose**: Lấy chi tiết kết quả của 1 submission cụ thể.

#### Response (Success - 200 OK)

**For Academic Tests**:
```json
{
  "submission_id": "string",
  "test_title": "string",
  "test_category": "academic",
  "is_diagnostic_test": false,
  "has_ai_evaluation": true,
  "grading_status": "auto_graded | fully_graded",
  "score": "number",
  "score_percentage": "number",
  "total_questions": "number",
  "correct_answers": "number",
  "is_passed": "boolean",
  "time_taken_seconds": "number",
  "attempt_number": "number",
  "submitted_at": "ISO datetime string",
  "results": [
    {
      "question_id": "string",
      "question_text": "string",
      "question_type": "mcq | essay",
      "your_answer": "string",
      "correct_answer": "string",
      "is_correct": "boolean",
      "explanation": "string",
      "max_points": "number",
      "points_awarded": "number"
    }
  ]
}
```

**For Diagnostic Tests**:
```json
{
  "submission_id": "string",
  "test_title": "string",
  "test_category": "diagnostic",
  "is_diagnostic_test": true,
  "has_ai_evaluation": true,
  "total_questions": "number",
  "time_taken_seconds": "number",
  "attempt_number": "number",
  "submitted_at": "ISO datetime string",
  "results": [
    {
      "question_id": "string",
      "question_text": "string",
      "question_type": "mcq",
      "your_answer": "string",
      "is_correct": null,
      "explanation": "string"
    }
  ],
  "message": "Câu trả lời của bạn đã được lưu nhưng chưa có đánh giá AI do không đủ điểm. (only if has_ai_evaluation=false)"
}
```

---

## 5. Affected Endpoints Summary

| Endpoint | Status | Changes Made |
|----------|--------|--------------|
| `POST /api/tests/generate` | ✅ Updated | Added `test_category` field, saves `evaluation_criteria` for diagnostic tests. |
| `POST /api/tests/generate/general` | ✅ Created | New endpoint for creating tests from general knowledge without file source. |
| `POST /api/tests/manual` | ✅ Updated | Supports `test_category` field. |
| `POST /api/tests/{test_id}/duplicate` | ✅ Updated | Copies `test_category`, `evaluation_criteria`, and `topic` fields. |
| `PUT /api/tests/{test_id}/questions` | ✅ Updated | Validation respects `test_category` (no `correct_answer_key` required for diagnostic). |
| `POST /api/tests/{test_id}/submit` | ✅ Updated | Deducts 1 point for diagnostic AI evaluation, saves answers even with insufficient points. |
| `GET /api/tests/me/tests` | ✅ Updated | Returns `test_category` field. |
| `GET /api/tests/me/submissions` | ✅ Updated | Returns `test_category`, `is_diagnostic_test`, `has_ai_evaluation` fields. |
| `GET /api/tests/me/submissions/{id}` | ✅ Updated | Returns diagnostic-specific fields and messages. |
| `GET /api/tests/{test_id}` | ✅ No change | Already returns full test document (includes all new fields). |
| `POST /api/tests/{test_id}/start` | ✅ No change | No logic dependent on test category. |
| `POST /api/evaluation/evaluate` | ✅ Updated | Uses `evaluation_criteria` from DB for diagnostic tests. |

---

## 6. Database Schema Updates

### Collection: `online_tests`
```javascript
{
    // Existing fields...
    "_id": "ObjectId",
    "title": "string",
    "description": "string (optional)",
    "creator_id": "string (Firebase UID)",
    "questions": [
        {
            "question_id": "string",
            "question_text": "string",
            "question_type": "mcq | essay",
            "options": ["array of strings (for MCQ)"],
            "correct_answer_key": "string (optional for diagnostic)",
            "explanation": "string",
            "max_points": "number"
        }
    ],

    // NEW FIELDS for Diagnostic Support
    "test_category": "string ('academic' | 'diagnostic', default: 'academic')",
    "evaluation_criteria": "string (optional, JSON string or text, only for diagnostic tests)",
    "topic": "string (optional, for general knowledge tests)",
    "source_type": "string ('file' | 'document' | 'general_knowledge')",

    // Existing fields continued...
    "time_limit_minutes": "number",
    "passing_score": "number",
    "status": "string",
    "created_at": "datetime",
    "updated_at": "datetime"
}
```

### Collection: `test_submissions`
```javascript
{
    // Existing fields...
    "_id": "ObjectId",
    "test_id": "string",
    "user_id": "string (Firebase UID)",
    "user_answers": "array",

    // NEW FIELDS for Diagnostic Support
    "test_category": "string ('academic' | 'diagnostic')",
    "is_diagnostic_test": "boolean",
    "has_ai_evaluation": "boolean (false if insufficient points for diagnostic)",
    "evaluation_criteria": "string (optional, copied from test)",

    // Existing fields continued...
    "score": "number (optional)",
    "score_percentage": "number (optional)",
    "is_passed": "boolean",
    "attempt_number": "number",
    "submitted_at": "datetime",
    "ai_evaluation": {
        "overall_evaluation": {
            // For academic:
            "strengths": ["array"],
            "weaknesses": ["array"],
            "recommendations": ["array"],
            "study_plan": "string",

            // For diagnostic:
            "result_title": "string",
            "result_description": "string",
            "personality_traits": ["array"],
            "advice": ["array"]
        },
        "question_evaluations": ["array"]
    }
}
```

### Collection: `users` - Point System
```javascript
{
    "_id": "ObjectId",
    "firebase_uid": "string",
    "email": "string",
    "points": "number (default: 0)",
    "point_transactions": [
        {
            "type": "add | deduct",
            "amount": "number",
            "reason": "string (e.g., 'AI evaluation for diagnostic test')",
            "timestamp": "datetime",
            "related_test_id": "string (optional)",
            "related_submission_id": "string (optional)"
        }
    ],
    "created_at": "datetime",
    "updated_at": "datetime"
}
```

### Migration Notes
- **Backward Compatible**: Không cần migration. Existing tests mặc định `test_category = "academic"`.
- **Existing Submissions**: Không có `is_diagnostic_test` field → Frontend cần handle default `false`.
- **Point System**: User profile tự động được tạo khi submit diagnostic test lần đầu.

---

## 7. Implementation Priority

### Phase 2.1 (High Priority)
1.  ✅ Update `POST /api/tests/generate` to support `test_category`.
2.  ✅ Modify `test_generator_service.py` prompt logic.
3.  ✅ Save `evaluation_criteria` to DB.
4.  ✅ Update `gemini_test_evaluation_service.py` to consume `evaluation_criteria`.

### Phase 2.2 (Medium Priority)
1.  ✅ Create `POST /api/tests/generate/general` endpoint.
2.  ✅ Update `PUT /api/tests/{test_id}/questions` validation.
3.  ✅ Update `POST /api/tests/{test_id}/duplicate` to copy new fields.

### Phase 2.3 (Low Priority)
1.  ✅ Update `PUT /api/tests/{test_id}/edit` to allow editing `test_category`.
2.  ✅ Add UI hints in `POST /api/tests/{test_id}/submit` response for Diagnostic tests.

---

## 7. Testing Checklist

### Unit Tests
- [ ] Test prompt generation for Academic vs Diagnostic.
- [ ] Test JSON parsing with `diagnostic_criteria`.
- [ ] Test validation logic for Diagnostic questions (no `correct_answer_key` required).

### Integration Tests
- [ ] Create Academic test from file → Verify questions have `correct_answer_key`.
- [ ] Create Diagnostic test from file → Verify `evaluation_criteria` is saved.
- [ ] Submit Diagnostic test → Verify AI evaluation uses criteria.
- [ ] Create test from general knowledge → Verify it works without source file.

### Edge Cases
- [ ] Switch test from Academic to Diagnostic (via edit) → Check if questions need update.
- [ ] Duplicate Diagnostic test → Verify criteria is copied.
- [ ] Submit Diagnostic test without answers → Verify graceful handling.

---

## 8. Notes for Frontend Integration
- **Test Creation UI**: Add `test_category` selector ("Academic" vs "Diagnostic").
- **Question Editor**: Hide "Correct Answer" field if `test_category = "diagnostic"`.
- **Results Display**:
    - Academic: Show score, strengths/weaknesses, study plan.
    - Diagnostic: Highlight `result_title`, `result_description`, `personality_traits`.
- **General Knowledge Flow**: New UI for creating tests without file upload (Topic + Query inputs).
