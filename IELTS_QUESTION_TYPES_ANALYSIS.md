# IELTS Question Types - System Upgrade Analysis

## 📋 Tổng Quan

Hiện tại hệ thống chỉ hỗ trợ 2 loại câu hỏi:
- **MCQ** (Multiple Choice Questions) - Trắc nghiệm
- **Essay** - Tự luận

Cần mở rộng để hỗ trợ **6 loại câu hỏi IELTS Listening** chuẩn:
1. **Multiple Choice** - Trắc nghiệm (đã có)
2. **Matching** - Nối đáp án
3. **Map/Diagram Labeling** - Gắn nhãn bản đồ/sơ đồ
4. **Form/Note/Table Completion** - Điền vào form/ghi chú/bảng
5. **Sentence Completion** - Hoàn thành câu
6. **Short Answer** - Trả lời ngắn

---

## 🔍 Phân Tích Hệ Thống Hiện Tại

### 1. Database Schema (MongoDB)

```javascript
// Collection: online_tests
{
  "_id": ObjectId,
  "test_type": "mcq" | "essay" | "mixed" | "listening",
  "questions": [
    {
      "question_id": "q1",
      "question_number": 1,
      "question_type": "mcq" | "essay",  // ❌ GIỚI HẠN: Chỉ 2 loại
      "question_text": "...",

      // MCQ fields
      "options": [{"option_key": "A", "option_text": "..."}],
      "correct_answer_keys": ["A", "B"],  // Multi-answer support

      // Essay fields
      "max_points": 10,
      "grading_rubric": "...",

      // Common fields
      "explanation": "...",
      "media_type": "image" | "audio",
      "media_url": "...",
      "audio_section": 1  // For listening tests
    }
  ]
}
```

**Vấn đề:**
- `question_type` chỉ có 2 giá trị: `mcq`, `essay`
- Cấu trúc câu hỏi cứng nhắc, không linh hoạt cho các dạng IELTS
- Không có field để lưu metadata cho matching, diagram labeling, etc.

---

### 2. Pydantic Models (`online_test_models.py`)

```python
class ManualTestQuestion(BaseModel):
    question_type: str = "mcq"  # ❌ GIỚI HẠN: mcq hoặc essay
    question_text: str

    # MCQ-specific
    options: Optional[list] = None
    correct_answer_keys: Optional[List[str]] = None

    # Essay-specific
    max_points: Optional[int] = 1
    grading_rubric: Optional[str] = None

    @field_validator("question_type")
    def validate_question_type(cls, v):
        if v not in ["mcq", "essay"]:  # ❌ HARD-CODED
            raise ValueError("question_type must be 'mcq' or 'essay'")
```

**Vấn đề:**
- Hard-coded validation chỉ chấp nhận `mcq` hoặc `essay`
- Cấu trúc không mở rộng được cho các dạng IELTS

---

### 3. Affected Endpoints

#### 📤 Generation & Creation
- `POST /api/v1/tests/generate` - AI generation
  - File: `test_creation_routes.py`
  - Calls: `TestGeneratorService._build_generation_prompt()`
  - Impact: ⚠️ **HIGH** - AI prompt cần biết 6 dạng câu hỏi IELTS

- `POST /api/v1/tests/listening/generate` - Listening test generation
  - File: `test_creation_routes.py`
  - Calls: `ListeningTestGeneratorService.generate_listening_test()`
  - Impact: ⚠️ **CRITICAL** - Cần update AI prompt để generate 6 dạng

- `POST /api/v1/tests/manual` - Manual test creation
  - File: `test_creation_routes.py`
  - Uses: `ManualTestQuestion` model
  - Impact: ⚠️ **HIGH** - Validation cần chấp nhận 6 dạng mới

#### 📥 Taking & Submission
- `GET /api/v1/tests/{test_id}` - Get test details
  - File: `test_taking_routes.py` (lines 1-350)
  - Returns: Full test or student view (hide answers)
  - Impact: ⚠️ **MEDIUM** - Cần format đúng cho từng dạng câu hỏi

- `POST /api/v1/tests/{test_id}/start` - Start test session
  - File: `test_taking_routes.py` (lines 366-680)
  - Calls: `test_generator.get_test_for_taking()`
  - Impact: ⚠️ **LOW** - Chỉ cần pass questions, không xử lý logic

- `POST /api/v1/tests/{test_id}/submit` - Submit answers
  - File: `test_taking_routes.py` (lines 682-1100)
  - Logic: Chấm điểm MCQ, lưu essay
  - Impact: ⚠️ **CRITICAL** - Cần logic chấm cho 6 dạng câu hỏi

#### 📊 Grading & Results
- `GET /api/v1/tests/submissions/{submission_id}` - Get submission results
  - File: `test_taking_routes.py` (lines 1500-1800)
  - Returns: Scored answers with correct/incorrect
  - Impact: ⚠️ **MEDIUM** - Format kết quả cho từng dạng

- `POST /api/v1/tests/grade-essay/{submission_id}/{question_id}` - Grade essay
  - File: `test_grading_routes.py`
  - Impact: ⚠️ **LOW** - Chỉ áp dụng cho essay questions

#### ✏️ Editing & Management
- `PUT /api/v1/tests/{test_id}/question/{question_id}` - Update question
  - File: `test_creation_routes.py`
  - Uses: `ManualTestQuestion` model
  - Impact: ⚠️ **HIGH** - Validation cần hỗ trợ 6 dạng

---

### 4. Services

#### `TestGeneratorService`
```python
# File: src/services/test_generator_service.py

def _build_generation_prompt(self, ...):
    # ❌ PROMPT chỉ biết generate MCQ
    # ❌ JSON schema hard-coded cho MCQ format
```

**Impact:** ⚠️ **HIGH** - Cần update prompt và JSON schema

#### `ListeningTestGeneratorService`
```python
# File: src/services/listening_test_generator_service.py

response_schema = {
    "questions": {
        "items": {
            "question_text": str,
            "options": [...],  # ❌ Giả định tất cả là MCQ
            "correct_answer_keys": [...]
        }
    }
}
```

**Impact:** ⚠️ **CRITICAL** - JSON schema cần linh hoạt cho 6 dạng

#### `get_test_for_taking()` - Test Retrieval
```python
# File: test_generator_service.py (lines 974-1070)

for q in test_doc["questions"]:
    q_type = q.get("question_type", "mcq")

    if q_type == "mcq":
        question_data["options"] = q.get("options", [])
    elif q_type == "essay":
        question_data["max_points"] = q.get("max_points", 1)
    # ❌ KHÔNG XỬ LÝ 6 dạng IELTS mới
```

**Impact:** ⚠️ **MEDIUM** - Cần thêm logic cho 6 dạng

---

## 🎯 IELTS Question Types - Chi Tiết Schema

### 1. Multiple Choice (đã có)
```javascript
{
  "question_type": "mcq",
  "question_text": "What is the main topic?",
  "options": [
    {"option_key": "A", "option_text": "Topic A"},
    {"option_key": "B", "option_text": "Topic B"},
    {"option_key": "C", "option_text": "Topic C"}
  ],
  "correct_answer_keys": ["A"],
  "explanation": "..."
}
```

**Answer Format:**
```javascript
{
  "question_id": "q1",
  "answer_type": "mcq",
  "selected_answer_keys": ["A"]
}
```

---

### 2. Matching
```javascript
{
  "question_type": "matching",
  "question_text": "Match the speakers to their opinions",
  "instruction": "Write the correct letter A-F next to questions 1-4",

  "left_items": [  // Items to match (1, 2, 3, 4)
    {"key": "1", "text": "Speaker John"},
    {"key": "2", "text": "Speaker Mary"},
    {"key": "3", "text": "Speaker Tom"},
    {"key": "4", "text": "Speaker Lisa"}
  ],

  "right_options": [  // Options to choose from (A, B, C, D, E, F)
    {"key": "A", "text": "Likes modern art"},
    {"key": "B", "text": "Prefers classical music"},
    {"key": "C", "text": "Enjoys outdoor activities"},
    {"key": "D", "text": "Interested in technology"},
    {"key": "E", "text": "Loves reading books"},
    {"key": "F", "text": "Passionate about cooking"}
  ],

  "correct_matches": {  // Mapping: left_key → right_key
    "1": "D",  // John → Technology
    "2": "A",  // Mary → Modern art
    "3": "C",  // Tom → Outdoor activities
    "4": "F"   // Lisa → Cooking
  },

  "audio_section": 2,
  "max_points": 4
}
```

**Answer Format:**
```javascript
{
  "question_id": "q5",
  "answer_type": "matching",
  "matches": {
    "1": "D",
    "2": "A",
    "3": "C",
    "4": "F"
  }
}
```

**Scoring:** 1 point per correct match (4/4 = 100%, 3/4 = 75%)

---

### 3. Map/Diagram Labeling
```javascript
{
  "question_type": "map_labeling",
  "question_text": "Label the map",
  "instruction": "Write the correct letter A-H next to questions 1-5",

  "diagram_url": "https://r2.../library-map.png",
  "diagram_description": "Floor plan of a university library",

  "label_positions": [  // Positions to label
    {"key": "1", "description": "Entrance hall"},
    {"key": "2", "description": "Reading room"},
    {"key": "3", "description": "Computer lab"},
    {"key": "4", "description": "Meeting room"},
    {"key": "5", "description": "Cafe"}
  ],

  "options": [  // Available labels
    {"key": "A", "text": "North wing"},
    {"key": "B", "text": "South wing"},
    {"key": "C", "text": "East wing"},
    {"key": "D", "text": "West wing"},
    {"key": "E", "text": "Ground floor"},
    {"key": "F", "text": "First floor"},
    {"key": "G", "text": "Second floor"},
    {"key": "H", "text": "Basement"}
  ],

  "correct_labels": {
    "1": "E",  // Entrance → Ground floor
    "2": "F",  // Reading → First floor
    "3": "F",  // Computer → First floor
    "4": "G",  // Meeting → Second floor
    "5": "E"   // Cafe → Ground floor
  },

  "audio_section": 1,
  "max_points": 5
}
```

**Answer Format:**
```javascript
{
  "question_id": "q2",
  "answer_type": "map_labeling",
  "labels": {
    "1": "E",
    "2": "F",
    "3": "F",
    "4": "G",
    "5": "E"
  }
}
```

---

### 4. Form/Note/Table Completion
```javascript
{
  "question_type": "completion",
  "completion_subtype": "form",  // or "note", "table"
  "question_text": "Complete the registration form",
  "instruction": "Write NO MORE THAN TWO WORDS for each answer",

  "template": "Customer Registration\nName: John Smith\nPhone: _____(1)_____\nEmail: _____(2)_____\nAddress: _____(3)_____ Street, Apartment _____(4)_____\nPreferred contact: _____(5)_____",

  "blanks": [  // Blanks to fill
    {
      "key": "1",
      "position": "Phone number",
      "word_limit": 2,
      "hint": "Numbers only"
    },
    {
      "key": "2",
      "position": "Email address",
      "word_limit": 2,
      "hint": "Include @ symbol"
    },
    {
      "key": "3",
      "position": "Street name",
      "word_limit": 2
    },
    {
      "key": "4",
      "position": "Apartment number",
      "word_limit": 1
    },
    {
      "key": "5",
      "position": "Contact method",
      "word_limit": 1
    }
  ],

  "correct_answers": {
    "1": ["555-1234", "555 1234"],  // Multiple acceptable answers
    "2": ["john.smith@email.com"],
    "3": ["Main Street", "main street"],  // Case-insensitive
    "4": ["12A", "12a"],
    "5": ["Email", "email"]
  },

  "case_sensitive": false,
  "audio_section": 3,
  "max_points": 5
}
```

**Answer Format:**
```javascript
{
  "question_id": "q10",
  "answer_type": "completion",
  "answers": {
    "1": "555-1234",
    "2": "john.smith@email.com",
    "3": "Main Street",
    "4": "12A",
    "5": "Email"
  }
}
```

**Scoring:** Case-insensitive, accept multiple valid answers

---

### 5. Sentence Completion
```javascript
{
  "question_type": "sentence_completion",
  "question_text": "Complete the sentences",
  "instruction": "Write NO MORE THAN THREE WORDS for each answer",

  "sentences": [
    {
      "key": "1",
      "template": "The library opens at _____ on weekdays.",
      "word_limit": 2,
      "correct_answers": ["8 AM", "eight o'clock", "8 o'clock"]
    },
    {
      "key": "2",
      "template": "Students can borrow books for a maximum of _____.",
      "word_limit": 3,
      "correct_answers": ["two weeks", "2 weeks", "fourteen days"]
    },
    {
      "key": "3",
      "template": "Late return fee is _____ per day.",
      "word_limit": 2,
      "correct_answers": ["50 cents", "$0.50", "fifty cents"]
    }
  ],

  "case_sensitive": false,
  "audio_section": 2,
  "max_points": 3
}
```

**Answer Format:**
```javascript
{
  "question_id": "q15",
  "answer_type": "sentence_completion",
  "answers": {
    "1": "8 AM",
    "2": "two weeks",
    "3": "50 cents"
  }
}
```

---

### 6. Short Answer
```javascript
{
  "question_type": "short_answer",
  "question_text": "Answer the questions",
  "instruction": "Write NO MORE THAN THREE WORDS AND/OR A NUMBER for each answer",

  "questions": [
    {
      "key": "1",
      "text": "What is the speaker's occupation?",
      "word_limit": 3,
      "correct_answers": ["Software Engineer", "software engineer", "Engineer"]
    },
    {
      "key": "2",
      "text": "How many years of experience does she have?",
      "word_limit": 2,
      "correct_answers": ["5 years", "five years", "5"]
    },
    {
      "key": "3",
      "text": "What programming language does she prefer?",
      "word_limit": 1,
      "correct_answers": ["Python", "python"]
    }
  ],

  "case_sensitive": false,
  "audio_section": 4,
  "max_points": 3
}
```

**Answer Format:**
```javascript
{
  "question_id": "q20",
  "answer_type": "short_answer",
  "answers": {
    "1": "Software Engineer",
    "2": "5 years",
    "3": "Python"
  }
}
```

---

## 📊 Impact Summary

### Critical Changes (Must Update)
1. ✅ **Pydantic Models** - Add 6 new question types with validation
2. ✅ **AI Generation Prompts** - Update Gemini prompts for 6 dạng
3. ✅ **Submission Endpoint** - Scoring logic cho 6 dạng
4. ✅ **Database Schema** - Flexible question structure

### Medium Changes (Should Update)
1. ⚠️ **Get Test Endpoint** - Format questions correctly
2. ⚠️ **Test Generator Service** - Support 6 types in `get_test_for_taking()`
3. ⚠️ **Socket Auto-Save** - Handle new answer formats

### Low Changes (Nice to Have)
1. 💡 **Frontend Types** - TypeScript interfaces cho 6 dạng
2. 💡 **API Documentation** - Update examples with 6 types

---

## 🚀 Implementation Roadmap

### Phase 1: Models & Validation (2-3 days)
- [ ] Update `ManualTestQuestion` to support 6 types
- [ ] Add validation rules for each type (word limits, options, etc.)
- [ ] Add new Pydantic models for each type
- [ ] Update `question_type` validator to accept 6 values
- [ ] Add backward compatibility for existing `mcq` and `essay`

### Phase 2: AI Generation (3-4 days)
- [ ] Update `ListeningTestGeneratorService` prompt
- [ ] Define JSON schema for 6 question types
- [ ] Update AI response parsing logic
- [ ] Test generation for all 6 types
- [ ] Handle AI errors and fallbacks

### Phase 3: Submission & Scoring (3-4 days)
- [ ] Update `submit_test()` to handle 6 answer formats
- [ ] Implement scoring logic for matching
- [ ] Implement scoring for completion/sentence/short answer
  - Case-insensitive comparison
  - Multiple acceptable answers
  - Word limit validation
- [ ] Update submission response format
- [ ] Add detailed feedback for each type

### Phase 4: Endpoints & Services (2-3 days)
- [ ] Update `get_test_for_taking()` to format 6 types
- [ ] Update `GET /tests/{test_id}` owner/student views
- [ ] Update socket auto-save for new formats
- [ ] Update manual test creation/editing
- [ ] Add validation for diagram URLs (map labeling)

### Phase 5: Testing & Documentation (2-3 days)
- [ ] Write unit tests for each question type
- [ ] Integration tests for submission/scoring
- [ ] Update API documentation with examples
- [ ] Test with production data
- [ ] Deploy to staging

### Phase 6: Migration (1-2 days)
- [ ] Ensure backward compatibility (old tests still work)
- [ ] Add migration script if needed
- [ ] Monitor production errors

---

## 💡 Backward Compatibility Strategy

### Database
- Keep existing `question_type: "mcq"` working
- New fields are optional (default to null/empty)
- Use `question_type` as discriminator

### API
- Accept both old and new formats
- Convert legacy `selected_answer_key` → `selected_answer_keys`
- Return format based on `question_type`

### Frontend
- Detect `question_type` and render appropriate UI
- Fallback to MCQ view if type unknown
- Progressive enhancement (new types = better UX)

---

## 📝 Next Steps

1. **Review & Approve** this analysis document
2. **Prioritize** question types (start with matching, completion)
3. **Create** detailed implementation plan for Phase 1
4. **Estimate** total time: ~15-20 days for full implementation
5. **Start** with Phase 1: Models & Validation

---

## ❓ Questions to Resolve

1. **AI Model**: Gemini có thể generate cả 6 dạng câu hỏi không? (cần test)
2. **Word Limit Validation**: Có check word limit khi submit không? (recommend: warning only)
3. **Diagram Generation**: AI có thể generate diagram/map không? (probably not, need manual upload)
4. **Scoring Strictness**: Case-sensitive? Accept typos? (recommend: lenient for completion types)
5. **Mixed Test**: Cho phép mix 6 dạng trong 1 test listening? (recommend: yes)

---

## 🎓 IELTS Standards Reference

- **IELTS Listening**: 40 questions, 4 sections
- **Question Distribution**:
  - Section 1-2: Everyday contexts (form completion, matching)
  - Section 3-4: Educational/academic (MCQ, sentence completion)
- **Scoring**: 1 point per question, band score = raw score / 40
- **Word Limits**: Strictly enforced (e.g., "NO MORE THAN TWO WORDS")
- **Spelling**: British or American English accepted
- **Case**: Usually case-insensitive

---

**Status**: ✅ Analysis Complete - Ready for Implementation Planning
**Date**: 2025-12-09
**Author**: AI Assistant
**Reviewed By**: (Pending)
