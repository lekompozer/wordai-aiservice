# Prompt Restructure Implementation Summary

## ✅ ĐÃ HOÀN THÀNH (Completed)

### 1. Tạo Module Prompt Builders Mới
**File:** `src/services/prompt_builders.py`

**Cấu trúc:**
- `PromptBuilder` class với các static methods
- `_get_question_type_definitions()` - Shared section định nghĩa 6 loại câu hỏi
- `build_academic_document_prompt()` - Prompt cho Academic test từ document/PDF
- `build_academic_general_prompt()` - Prompt cho Academic test từ general knowledge
- `build_diagnostic_prompt()` - Prompt riêng cho Diagnostic/Personality tests

**Đặc điểm:**
- ✅ Tách riêng 4 prompts khác nhau (3 cho academic/diagnostic, listening đã có sẵn)
- ✅ Giữ chung phần question types definitions để đồng nhất
- ✅ Mỗi prompt có system prompt và critical instructions riêng biệt
- ✅ Diagnostic prompt KHÔNG có `correct_answer_keys` và `points`, CÓ `diagnostic_criteria`

### 2. Refactor TestGeneratorService
**File:** `src/services/test_generator_service.py`

**Thay đổi:**
- Import `prompt_builder` từ module mới
- Method `_build_generation_prompt()` giờ route đến đúng prompt builder dựa trên:
  * `test_category == "diagnostic"` → Diagnostic Prompt
  * `is_general_knowledge == True` → Academic General Prompt
  * Otherwise → Academic Document Prompt
- Xoá 300+ dòng code cũ (difficulty map, option keys generation, MCQ distribution logic...)

**Cơ chế routing:**
```python
if test_category == "diagnostic":
    return prompt_builder.build_diagnostic_prompt(...)
elif is_general_knowledge:
    return prompt_builder.build_academic_general_prompt(...)
else:
    return prompt_builder.build_academic_document_prompt(...)
```

---

## ⏳ CÒN LẠI (Remaining Work)

### 3. Cập nhật Method Signatures
**Cần làm:**
- [ ] Update `_build_generation_prompt()` signature để nhận:
  * `title: str` - Test title
  * `topic: str` - Test topic/description
  * `is_general_knowledge: bool` - Flag để phân biệt general vs document

- [ ] Update `_generate_questions_with_ai()` để truyền title/topic xuống `_build_generation_prompt()`

- [ ] Update `generate_test_from_content()` để nhận title/topic từ caller (routes)

### 4. Cập nhật Routes
**File:** `src/api/test_creation_routes.py`

**Cần update các endpoints:**

#### 4.1. `/generate` (Document/PDF Test)
```python
# Trong generate_test_background():
result = await generator.generate_test_from_content(
    content=content,
    title=test_data["title"],  # Đã có
    topic=test_data.get("description", test_data["title"]),  # Thêm
    user_query=test_data["user_query"],
    language=test_data["language"],
    num_questions=test_data["num_questions"],
    ...
    is_general_knowledge=False  # Thêm
)
```

#### 4.2. `/generate/general` (General Knowledge Test)
```python
# Trong generate_test_background():
result = await generator.generate_test_from_content(
    content="",  # Empty for general knowledge
    title=test_data["title"],
    topic=test_data.get("topic", test_data["title"]),  # Thêm
    user_query=test_data["user_query"],
    language=test_data["language"],
    num_questions=test_data["num_questions"],
    ...
    is_general_knowledge=True  # Thêm flag này!
)
```

#### 4.3. Diagnostic Tests
- Đã support sẵn qua `test_category="diagnostic"` parameter
- Chỉ cần đảm bảo routes truyền đúng `test_category`

### 5. Listening Test (Không cần thay đổi)
**File:** `src/services/listening_test_generator_service.py`

✅ Đã hoạt động tốt với IELTS prompt từ `ielts_question_schemas.py`
- Prompt structure đã đúng
- JSON output đúng format
- Không cần refactor

---

## 📊 CẤU TRÚC PROMPT MỚI

### Cấu trúc chung cho tất cả prompts:

```
1. SYSTEM PROMPT
   - Role definition
   - Task description

2. TEST CONFIGURATION
   - Title: {title}
   - Topic: {topic}
   - Language: {language}
   - Difficulty: {difficulty}
   - Number of Questions: {num_questions}

3. USER REQUIREMENTS
   {user_query}

4. QUESTION TYPES (Shared section)
   - MCQ, MCQ Multiple, Matching, Completion, Sentence Completion, Short Answer
   - JSON examples for each type
   - Points system (1-5)

5. CRITICAL INSTRUCTIONS (Unique per prompt type)
   - Output format requirements
   - Question count rules
   - Content source rules
   - Answer accuracy rules
   - Language rules

6. DOCUMENT CONTENT (For document-based tests only)
   ---
   {document_content}
   ---

7. RETURN INSTRUCTION
   "Return ONLY the JSON object, no additional text, no markdown code blocks."
```

### Sự khác biệt giữa 3 prompts:

| Feature | Academic Document | Academic General | Diagnostic |
|---------|------------------|------------------|------------|
| System Prompt | "expert educational assessment creator specializing in ACADEMIC tests" | "expert educational assessment creator specializing in ACADEMIC tests" | "expert psychologist and personality assessment creator specializing in DIAGNOSTIC tests" |
| Content Source | "from provided document" | "from general knowledge" | "personality/behavior questions" |
| Has Document | ✅ Yes | ❌ No | ❌ No |
| Has Points | ✅ Yes (1-5) | ✅ Yes (1-5) | ❌ No |
| Has correct_answer_keys | ✅ Yes | ✅ Yes | ❌ No |
| Has diagnostic_criteria | ❌ No | ❌ No | ✅ Yes |
| Explanation Focus | "WHY answer is correct" | "WHY answer is correct" | "What option reveals about personality" |

---

## 🧪 TESTING CHECKLIST

### Test Case 1: Academic Document Test
- [ ] Upload PDF/Document
- [ ] Set `test_category="academic"`
- [ ] Verify prompt uses "Academic Document" builder
- [ ] Check questions reference document content
- [ ] Verify `points` field present
- [ ] Verify `correct_answer_keys` present

### Test Case 2: Academic General Test
- [ ] Use `/generate/general` endpoint
- [ ] Set `test_category="academic"`
- [ ] Verify prompt uses "Academic General" builder
- [ ] Check questions based on general knowledge
- [ ] Verify NO document section in prompt
- [ ] Verify `points` field present

### Test Case 3: Diagnostic Test
- [ ] Use any endpoint with `test_category="diagnostic"`
- [ ] Verify prompt uses "Diagnostic" builder
- [ ] Check questions about personality/preferences
- [ ] Verify NO `correct_answer_keys` field
- [ ] Verify NO `points` field
- [ ] Verify `diagnostic_criteria` object present

### Test Case 4: Listening Test (Existing)
- [ ] Use `/generate/listening` endpoint
- [ ] Verify IELTS prompt used
- [ ] Check `audio_sections` structure correct
- [ ] Verify question types (mcq, matching, completion, etc.)

---

## 🔧 NEXT ACTIONS

1. **Update `_build_generation_prompt()` signature:**
   ```python
   def _build_generation_prompt(
       self,
       user_query: str,
       num_questions: int,
       document_content: str,
       language: str = "vi",
       difficulty: Optional[str] = None,
       num_options: int = 4,
       num_correct_answers: int = 1,
       test_category: str = "academic",
       mcq_type_config: Optional[Dict] = None,
       title: str = "",  # NEW
       topic: str = "",  # NEW
       is_general_knowledge: bool = False,  # NEW
   ) -> str:
   ```

2. **Update callers in routes:**
   - Truyền `title` từ request
   - Truyền `topic` từ request.description hoặc request.topic
   - Set `is_general_knowledge=True` cho `/generate/general` endpoint

3. **Test từng endpoint:**
   - Document test → Kiểm tra reference document
   - General test → Kiểm tra không có document content
   - Diagnostic test → Kiểm tra format đúng

---

## 📝 LƯU Ý QUAN TRỌNG

1. **Listening Test không động chạm:**
   - Đã working tốt với IELTS prompt
   - JSON structure đúng
   - Question types đầy đủ

2. **Diagnostic vs Academic:**
   - TUYỆT ĐỐI không dùng chung prompt
   - Diagnostic không có correct_answer_keys
   - Diagnostic không có points
   - Diagnostic phải có diagnostic_criteria

3. **Question Type Definitions:**
   - Giữ chung ở `_get_question_type_definitions()`
   - Đảm bảo consistency across all prompts
   - Include đầy đủ 6 types: mcq, mcq_multiple, matching, completion, sentence_completion, short_answer

4. **User Settings Display:**
   - Hiển thị rõ ràng trong mỗi prompt
   - Title, Topic, Language, Difficulty, Num Questions
   - Giúp AI hiểu context trước khi generate

---

## 📈 BENEFITS CỦA CẤU TRÚC MỚI

✅ **Rõ Ràng:** System prompt và critical instructions khác biệt rõ ràng cho từng loại test
✅ **Tái Sử Dụng:** Question types definition chung cho tất cả
✅ **Dễ Maintain:** Mỗi prompt trong 1 method riêng, dễ sửa
✅ **Đúng Logic:** Academic có answer đúng/sai, Diagnostic không có
✅ **Clean Code:** Xoá 300+ dòng code cũ, logic rõ ràng hơn
