# Prompt Restructure Analysis - Test Generation Endpoints

## 📋 Hiện Trạng (Current State)

### 3 Endpoints Chính:

1. **`POST /api/v1/tests/generate`** - Document/PDF Test
   - Service: `TestGeneratorService._build_generation_prompt()`
   - Input: Document content hoặc PDF file
   - Question types: MCQ, MCQ_Multiple, Matching, Completion, Sentence Completion, Short Answer

2. **`POST /api/v1/tests/generate/general`** - General AI Knowledge Test
   - Service: `TestGeneratorService._build_generation_prompt()` (cùng method)
   - Input: Topic + User Query (không cần document)
   - Question types: Giống endpoint #1

3. **`POST /api/v1/tests/generate/listening`** - Listening Test
   - Service: `ListeningTestGeneratorService._build_listening_prompt()`
   - Input: Language + Topic + Audio config
   - Question types: **IELTS Listening** (MCQ, Matching, Completion, Sentence Completion, Short Answer) + audio_sections

---

## ⚠️ VẤN ĐỀ PHÁT HIỆN

### 1. **Prompt Lộn Xộn**
- System prompt, user settings, instructions trộn lẫn nhau
- Không có cấu trúc rõ ràng từ trên xuống dưới
- Quá nhiều chữ "CRITICAL" khiến AI confused

### 2. **Language Không Lấy từ User Settings**
```python
# ❌ BAD: Hardcode language trong prompt
lang_instruction = f"Generate all questions in {language} language."
```

**PHẢI:**
```python
# ✅ GOOD: Display user settings riêng biệt
**USER SETTINGS:**
- Language: {language}
- Difficulty: {difficulty}
- Number of Questions: {num_questions}
```

### 3. **Prompt General và Document Dùng Chung**
- Hiện tại `/generate` và `/generate/general` dùng cùng `_build_generation_prompt()`
- Nhưng logic khác nhau:
  - Document: Có document content
  - General: Không có document, chỉ có topic

### 4. **Listening Prompt Riêng Nhưng Thiếu Structured**
- `ListeningTestGeneratorService._build_listening_prompt()` đã tách riêng ✅
- Nhưng thiếu section "USER SETTINGS" rõ ràng
- Cần apply IELTS question type rules rõ ràng hơn

---

## ✅ CẤU TRÚC MỚI (New Structure)

### Template Chung Cho Tất Cả Prompts:

```
1. SYSTEM PROMPT
   - Role definition
   - Task description

2. USER SETTINGS (Display Settings)
   - Test Title: {title}
   - Topic: {topic}
   - Test Type: {test_type}
   - Number of Questions: {num_questions}
   - Language: {language}
   - Difficulty: {difficulty}
   - Category: {test_category}
   - Options per Question: {num_options}
   - Correct Answers per Question: {num_correct_answers}

3. USER QUERY
   - User's detailed instructions

4. CRITICAL INSTRUCTIONS
   - Rules for question generation
   - Question type specifications
   - Difficulty rules
   - Points system (1-5 based on difficulty)

5. JSON STRUCTURE & EXAMPLE
   - Schema definition
   - Example output

6. RETURN INSTRUCTION
   - "Return ONLY the JSON object, no additional text, no markdown code blocks."
```

---

## 🔧 IMPLEMENTATION PLAN

### Phase 1: Create Separate Prompt Builders

#### 1.1. Document/PDF Test Prompt
```python
def _build_document_prompt(
    self,
    title: str,
    topic: str,
    test_type: str,
    num_questions: int,
    language: str,
    difficulty: str,
    test_category: str,
    num_options: int,
    num_correct_answers: int,
    user_query: str,
    document_content: str,
    mcq_type_config: Optional[Dict] = None,
) -> str:
    """Build prompt for document-based test generation"""

    # 1. SYSTEM PROMPT
    system_prompt = """You are an expert in creating educational assessments.
Your task is to generate a comprehensive test based on the provided document and user requirements."""

    # 2. USER SETTINGS
    user_settings = f"""
**USER SETTINGS:**
- Test Title: {title}
- Topic: {topic}
- Test Type: {test_type}
- Number of Questions: {num_questions}
- Language: {language}
- Difficulty: {difficulty}
- Category: {test_category}
- Options per Question: {num_options}
- Correct Answers per Question: {num_correct_answers}
"""

    # 3. USER QUERY
    user_query_section = f"""
**USER QUERY:**
{user_query}
"""

    # 4. CRITICAL INSTRUCTIONS (gộp lại từ các rules cũ)
    critical_instructions = """
**CRITICAL INSTRUCTIONS:**

1. **OUTPUT FORMAT:**
   - Output MUST be a single, valid JSON object
   - Properly escape special characters: use \\" for quotes, \\n for newlines
   - Validate JSON before returning: ensure balanced brackets

2. **QUESTION COUNT (ABSOLUTE):**
   - Generate EXACTLY {num_questions} questions. NO MORE, NO LESS.
   - NO DUPLICATES: Each question must be unique

3. **CONTENT SOURCE:**
   - All content must come directly from the provided document
   - Explanations must reference specific document info

4. **DIFFICULTY & POINTS:**
   - Assign 'points' (1-5) based on difficulty:
     * 1 = very easy
     * 2 = easy
     * 3 = medium
     * 4 = hard
     * 5 = very hard

5. **QUESTION TYPES:**
   {self._get_question_type_rules(mcq_type_config, num_options)}
"""

    # 5. JSON STRUCTURE
    json_structure = """
**JSON STRUCTURE:**
{
  "questions": [
    {
      "question_type": "mcq",
      "question_text": "string",
      "options": [{"option_key": "A", "option_text": "string"}, ...],
      "correct_answer_keys": ["A"],
      "explanation": "string",
      "points": 1
    }
  ]
}
"""

    # 6. DOCUMENT CONTENT
    document_section = f"""
**DOCUMENT CONTENT:**
---
{document_content}
---
"""

    # 7. RETURN INSTRUCTION
    return_instruction = "Return ONLY the JSON object, no additional text, no markdown code blocks."

    return f"{system_prompt}\n\n{user_settings}\n\n{user_query_section}\n\n{critical_instructions}\n\n{json_structure}\n\n{document_section}\n\n{return_instruction}"
```

#### 1.2. General Knowledge Test Prompt
```python
def _build_general_prompt(
    self,
    title: str,
    topic: str,
    test_type: str,
    num_questions: int,
    language: str,
    difficulty: str,
    test_category: str,
    num_options: int,
    num_correct_answers: int,
    user_query: str,
    mcq_type_config: Optional[Dict] = None,
) -> str:
    """Build prompt for general knowledge test generation (NO DOCUMENT)"""

    # 1. SYSTEM PROMPT
    system_prompt = """You are an expert in creating educational assessments.
Your task is to generate a comprehensive test based on general knowledge of the specified topic."""

    # 2. USER SETTINGS
    user_settings = f"""
**USER SETTINGS:**
- Test Title: {title}
- Topic: {topic}
- Test Type: {test_type}
- Number of Questions: {num_questions}
- Language: {language}
- Difficulty: {difficulty}
- Category: {test_category}
- Options per Question: {num_options}
- Correct Answers per Question: {num_correct_answers}
"""

    # 3. USER QUERY
    user_query_section = f"""
**USER QUERY:**
{user_query}

**IMPORTANT:** You are NOT provided with a document. Generate questions based on:
- General knowledge of the topic: {topic}
- Common information available in educational resources
- Standard academic content for this subject
"""

    # 4-7: Same as document prompt but without document section

    return f"{system_prompt}\n\n{user_settings}\n\n{user_query_section}\n\n{critical_instructions}\n\n{json_structure}\n\n{return_instruction}"
```

#### 1.3. Listening Test Prompt (Refactor Existing)
```python
def _build_listening_prompt(
    self,
    title: str,
    topic: str,
    test_type: str,
    num_questions: int,
    language: str,
    difficulty: str,
    num_audio_sections: int,
    num_speakers: int,
    user_query: str,
) -> str:
    """Build prompt for listening test generation with IELTS question types"""

    # 1. SYSTEM PROMPT
    system_prompt = """You are an expert in creating listening comprehension tests (IELTS/TOEFL-style).
Your task is to generate a listening test with audio scripts and questions."""

    # 2. USER SETTINGS
    user_settings = f"""
**USER SETTINGS:**
- Test Title: {title}
- Topic: {topic}
- Test Type: Listening Comprehension
- Number of Questions: {num_questions}
- Language: {language}
- Difficulty: {difficulty}
- Audio Sections: {num_audio_sections}
- Number of Speakers: {num_speakers}
"""

    # 3. USER QUERY
    user_query_section = f"""
**USER QUERY:**
{user_query}
"""

    # 4. CRITICAL INSTRUCTIONS
    critical_instructions = """
**CRITICAL INSTRUCTIONS:**

1. **OUTPUT FORMAT:**
   - Output MUST be valid JSON with audio_sections array
   - Each section contains: script + questions

2. **QUESTION COUNT:**
   - Generate EXACTLY {num_questions} questions distributed across {num_audio_sections} sections

3. **IELTS QUESTION TYPES (Listening-specific):**
   - **MCQ** ("question_type": "mcq"): Standard multiple choice
   - **Matching** ("question_type": "matching"): Match speakers/topics
   - **Completion** ("question_type": "completion"): Fill forms/notes (IELTS format)
   - **Sentence Completion** ("question_type": "sentence_completion"): Complete sentences
   - **Short Answer** ("question_type": "short_answer"): 1-3 word answers

4. **AUDIO SCRIPT REQUIREMENTS:**
   - Natural conversation/monologue
   - Include speaker roles (e.g., Customer, Agent)
   - Questions must be answerable from audio ONLY
   - Include timestamp hints for each question
"""

    # 5. JSON STRUCTURE (Listening-specific)
    json_structure = """
**JSON STRUCTURE:**
{
  "audio_sections": [
    {
      "section_number": 1,
      "section_title": "string",
      "script": {
        "speaker_roles": ["Customer", "Agent"],
        "lines": [
          {"speaker": 0, "text": "Good morning..."},
          {"speaker": 1, "text": "Hello..."}
        ]
      },
      "questions": [...]
    }
  ]
}
"""

    return f"{system_prompt}\n\n{user_settings}\n\n{user_query_section}\n\n{critical_instructions}\n\n{json_structure}\n\n{return_instruction}"
```

---

## 📊 MAPPING USER SETTINGS

### Settings từ Request Model:

| Setting | Document/PDF | General | Listening |
|---------|-------------|---------|-----------|
| `title` | ✅ | ✅ | ✅ |
| `topic` | ✅ (from description) | ✅ | ✅ |
| `test_type` | ✅ | ✅ | Fixed: "listening" |
| `num_questions` | ✅ | ✅ | ✅ |
| `language` | ✅ | ✅ | ✅ |
| `difficulty` | ✅ | ✅ | ✅ |
| `test_category` | ✅ | ✅ | Fixed: "academic" |
| `num_options` | ✅ | ✅ | N/A (varies by type) |
| `num_correct_answers` | ✅ | ✅ | N/A (varies by type) |
| `num_audio_sections` | N/A | N/A | ✅ |
| `num_speakers` | N/A | N/A | ✅ |

---

## 🎯 NEXT STEPS

1. ✅ Create this analysis document
2. ⏳ Refactor `TestGeneratorService`:
   - Extract `_build_document_prompt()` from `_build_generation_prompt()`
   - Create new `_build_general_prompt()`
   - Keep `_build_essay_generation_prompt()` (for essay tests)
3. ⏳ Refactor `ListeningTestGeneratorService`:
   - Update `_build_listening_prompt()` to match new structure
4. ⏳ Update route handlers:
   - `/generate` → use `_build_document_prompt()`
   - `/generate/general` → use `_build_general_prompt()`
   - `/generate/listening` → use updated `_build_listening_prompt()`

---

## 🔍 BENEFITS

1. **Rõ Ràng Hơn:** AI đọc settings trước khi đọc instructions
2. **Dễ Debug:** Biết chính xác user muốn gì (từ USER SETTINGS section)
3. **Tách Biệt Logic:** Document vs General vs Listening có prompt riêng
4. **Consistent:** Tất cả prompts follow cùng 1 template
5. **Language Từ Settings:** Không hardcode trong instructions nữa
