# Gemini Prompt Simulation - Grade 10 English Test

## Vấn đề phát hiện
- **Yêu cầu**: 35 câu hỏi
- **Thực tế**: 336 câu (MCQ: 40, Completion: 296)
- **Duplicate**: "Volunteering is a great way" lặp 94 lần

## Phân tích Flow

### 1. User Query (Input)
```
Create a 35-question English test for Vietnamese Grade 10, A2-B1 level.
Topics: school life, environment, technology, culture, social issues.

CRITICAL: Use specified question_type for each part.

PART 1: PHONETICS (4 MCQ questions)
- 2 questions: different underlined sound
- 2 questions: different stress pattern
Use question_type: "mcq", 4 options, 1 correct answer

PART 2: VOCABULARY & GRAMMAR (8 questions)
A. Grammar MCQ (3 questions) - question_type: "mcq"
B. Word Form (2 questions) - question_type: "short_answer"
C. Verb Form (3 questions) - question_type: "short_answer"

PART 3: READING (10 questions)
A. Reading Passage (5 questions) - question_type: "mcq"
B. Cloze Test (5 questions) - question_type: "completion"

PART 4: WRITING (5 questions)
A. Error Identification (2 questions) - question_type: "mcq"
B. Sentence Transformation (3 questions) - question_type: "short_answer"

SUMMARY:
- 22 MCQ questions
- 8 short_answer questions
- 5 completion questions
- Total: 35 questions
```

### 2. Config từ Backend
```python
num_questions = 35
language = "vi"
difficulty = None
num_options = 4
num_correct_answers = 1
test_category = "academic"
mcq_type_config = {"distribution_mode": "auto"}  # Default AUTO mode
```

### 3. Prompt Thực Tế Gửi đến Gemini

---

```
You are an expert in creating educational assessments. Your task is to generate a comprehensive test based on the provided document and user query.

**TEST TYPE: This is an ACADEMIC test. Questions should test knowledge with clear correct answers.**

**🎯 PRIMARY DIRECTIVE - USER QUERY ANALYSIS:**
BEFORE generating questions, carefully analyze the user query below:
"Create a 35-question English test for Vietnamese Grade 10, A2-B1 level.
Topics: school life, environment, technology, culture, social issues.

CRITICAL: Use specified question_type for each part.

PART 1: PHONETICS (4 MCQ questions)
- 2 questions: different underlined sound
- 2 questions: different stress pattern
Use question_type: "mcq", 4 options, 1 correct answer

PART 2: VOCABULARY & GRAMMAR (8 questions)
A. Grammar MCQ (3 questions) - question_type: "mcq"
Test: tenses, comparatives, modals, articles, prepositions, phrasal verbs

B. Word Form (2 questions) - question_type: "short_answer"
Give word in parentheses, student writes correct form

C. Verb Form (3 questions) - question_type: "short_answer"
Give verb in parentheses, student writes correct tense/form

PART 3: READING (10 questions)
A. Reading Passage (5 questions) - question_type: "mcq"
150-200 word passage, test: main idea, detail, inference, vocabulary

B. Cloze Test (5 questions) - question_type: "completion"
Use "template" field with _____(1)_____, _____(2)_____ format

PART 4: WRITING (5 questions)
A. Error Identification (2 questions) - question_type: "mcq"
Sentence divided into A/B/C/D, choose part with error

B. Sentence Transformation (3 questions) - question_type: "short_answer"
Complete second sentence using given structure (passive, comparisons, too/enough, so/such)

SUMMARY:
- 22 MCQ questions (phonetics + grammar MCQ + reading + error ID)
- 8 short_answer questions (word form + verb form + transformation)
- 5 completion questions (cloze test)
- Total: 35 questions"

**If the user query specifies:**
- Specific question formats (e.g., "phonetics", "pronunciation", "word stress", "error identification", "cloze test", "reading comprehension", "sentence transformation")
- Particular sections/parts with different question types
- Structured test layout (e.g., "PART 1: PHONETICS", "PART 2: VOCABULARY")
- Specific question counts per section

**THEN you MUST:**
1. Choose appropriate "question_type" based on format:
   - **PHONETICS / PRONUNCIATION / WORD STRESS / ERROR IDENTIFICATION**: Use "mcq" (standard multiple choice with 4 options, 1 correct answer)
   - **CLOZE TEST**: Use "completion" with IELTS format:
     * "template": Text with blanks marked as _____(1)_____, _____(2)_____
     * "blanks": Array like [{"key": "1", "position": "description"}]
     * "correct_answers": Array like [{"blank_key": "1", "answers": ["answer", "variation1", "variation2"]}]
     * DO NOT use "options" or "correct_answer_keys" for completion type
   - **SENTENCE TRANSFORMATION / REWRITE**: Use "short_answer" (free-text answer with multiple acceptable variations)
   - **READING COMPREHENSION / VOCABULARY / GRAMMAR**: Use "mcq" (standard multiple choice)
   - **COMMUNICATION / DIALOGUE**: Use "mcq" (standard multiple choice)
2. Structure questions according to the user's specified parts/sections
3. If MCQ TYPE DISTRIBUTION is specified below, follow those exact counts. Otherwise, match the requested question counts per section from user query

**CRITICAL INSTRUCTIONS:**
1. Your output MUST be a single, valid JSON object.
2. **IMPORTANT: Properly escape all special characters in JSON strings:**
   - Use \" for double quotes inside strings
   - Use \n for newlines inside strings
   - Use \\\\ for backslashes inside strings
3. Generate all questions, options, and explanations in vi language.
4. The JSON object must conform to the following structure:
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
         "correct_answer_keys": ["A"],
         "explanation": "string (Explain WHY the correct answer(s) are right, based on the document).",
         "points": 1
       }
     ]
   }
5. **⚠️ CRITICAL - QUESTION COUNT:** You MUST generate EXACTLY 35 questions total. NO MORE, NO LESS.
   - This count is ABSOLUTE and CANNOT be changed regardless of user query content
   - If user query mentions sections/parts, distribute these 35 questions across those sections
   - NEVER generate duplicate questions - each question must be unique
6. All information used to create questions, answers, and explanations must come directly from the provided document.
7. Each question has 4 options (A, B, C, D). Adjust if user query indicates otherwise.
8. The "correct_answer_keys" field must be an array with exactly ONE correct option key. However, adjust if question complexity requires it.
9. Explanations should be clear and reference specific information from the document.
10. Assign a 'points' value (1-5) to each question based on difficulty: 1=very easy, 2=easy, 3=medium, 4=hard, 5=very hard.
11. **CRITICAL: For "completion" question_type, you MUST use IELTS format:**
    - Include "template" field with text containing _____(1)_____, _____(2)_____ placeholders
    - Include "blanks" array with metadata for each blank
    - Include "correct_answers" array with blank_key and multiple answer variations
    - DO NOT use "options" array for completion questions
    - DO NOT use "correct_answer_keys" for completion questions
12. **VALIDATE your JSON output before returning it. Make sure all strings are properly escaped and all brackets are balanced.**


**MCQ TYPE DISTRIBUTION (AI AUTO MODE):**
You have the flexibility to use a variety of question types to create the most effective assessment. Generate a mix of different question types based on the content:

**Available question types:**
1. **Standard MCQ** ("question_type": "mcq"): Single correct answer with 4 options
2. **Multiple-answer MCQ** ("question_type": "mcq_multiple"): 2+ correct answers (select all that apply)
3. **Matching** ("question_type": "matching"): Match left items to right options
4. **Completion** ("question_type": "completion"): Fill blanks using IELTS format
5. **Sentence completion** ("question_type": "sentence_completion"): Complete sentences
6. **Short answer** ("question_type": "short_answer"): 1-3 word answers with variations

**Choose the most appropriate question types** to test the content effectively. For example:
- Use "completion" for vocabulary in context, listening comprehension forms/notes
- Use "matching" for connecting concepts, pairing definitions with terms
- Use "short_answer" for quick factual recall
- Use "mcq" for concept understanding with distractors
- Use "mcq_multiple" when several answers are correct

**DOCUMENT CONTENT:**
---
[Document về school life, environment, technology, culture, social issues sẽ được insert vào đây]
---

Now, generate the quiz based on the instructions and the document provided. Return ONLY the JSON object, no additional text, no markdown code blocks.
```

---

## ⚠️ VẤN ĐỀ PHÁT HIỆN

### 1. **Conflict trong Instructions**

**Line 5 (CRITICAL):**
```
⚠️ CRITICAL - QUESTION COUNT: You MUST generate EXACTLY 35 questions total. NO MORE, NO LESS.
```

**Line 3 (USER QUERY):**
```
If user query mentions sections/parts, distribute these 35 questions across those sections
```

**Line 3 (AUTO MODE):**
```
You have the flexibility to use a variety of question types...
Choose the most appropriate question types to test the content effectively.
```

**⚠️ XUNG ĐỘT:**
- Instruction #5 nói "EXACTLY 35 questions"
- Nhưng AUTO MODE nói "flexibility" và "choose appropriate types"
- User query chi tiết breakdown: 4+8+10+5+8 = 35 (có 5 completion)
- AI hiểu nhầm "flexibility" = có thể thay đổi số lượng → tạo 296 completion thay vì 5!

### 2. **Thiếu Validation Strict**

Prompt KHÔNG có:
- ❌ "If you generate more than 35 questions, your output will be REJECTED"
- ❌ "Count your questions before returning to ensure exactly 35"
- ❌ "Each Part MUST have EXACTLY the specified count"

### 3. **AUTO Mode Gây Confuse**

```python
mcq_type_config = {"distribution_mode": "auto"}  # Default
```

AUTO mode cho AI "flexibility" → AI nghĩ có thể tự quyết định:
- User query nói 5 completion
- AI thấy document về "volunteering" → tạo thêm 291 completion nữa!
- Kết quả: 94 câu giống hệt "Volunteering is a great way"

## 🔧 GIẢI PHÁP

### Fix 1: Loại bỏ AUTO Mode khi có User Query Chi Tiết

```python
# Nếu user query có breakdown chi tiết → FORCE manual mode
if "PART" in user_query.upper() and any(word in user_query.lower() for word in ["question_type", "mcq", "completion"]):
    mcq_type_config = {"distribution_mode": "manual"}
    # Extract counts từ user query
```

### Fix 2: Thêm Validation Strict vào Prompt

```
5. **⚠️ CRITICAL - QUESTION COUNT:**
   - Generate EXACTLY 35 questions total
   - DO NOT generate duplicate questions
   - If you generate 36 questions, DELETE 1
   - If you generate 34 questions, ADD 1
   - STOP generating after reaching 35
   - COUNT your output before returning: must be exactly 35
```

### Fix 3: Thêm Section Breakdown Explicit

```
**REQUIRED BREAKDOWN:**
- PART 1 (PHONETICS): 4 MCQ → question_type: "mcq"
- PART 2A (GRAMMAR): 3 MCQ → question_type: "mcq"
- PART 2B (WORD FORM): 2 SHORT ANSWER → question_type: "short_answer"
- PART 2C (VERB FORM): 3 SHORT ANSWER → question_type: "short_answer"
- PART 3A (READING): 5 MCQ → question_type: "mcq"
- PART 3B (CLOZE): 5 COMPLETION → question_type: "completion"
- PART 4A (ERROR ID): 2 MCQ → question_type: "mcq"
- PART 4B (TRANSFORM): 3 SHORT ANSWER → question_type: "short_answer"

TOTAL: 4+3+2+3+5+5+2+3 = 27 questions (NOT 35!)

⚠️ USER QUERY HAS ERROR: Claims 35 but breakdown = 27!
```

### Fix 4: Remove "Flexibility" Language in AUTO Mode

Thay:
```
You have the flexibility to use a variety of question types...
```

Bằng:
```
You MUST strictly follow the user query breakdown.
DO NOT add extra questions beyond the specified count for each part.
```

## KẾT LUẬN

**Root Cause:**
1. AUTO mode + "flexibility" → AI nghĩ được tự do thay đổi
2. User query chi tiết NHƯNG code vẫn dùng AUTO mode
3. Thiếu validation strict về số lượng câu hỏi
4. Gemini "hallucinate" khi response dài → lặp lại nội dung

**Action Items:**
1. ✅ Detect user query có breakdown → force manual mode
2. ✅ Parse exact counts từ user query
3. ✅ Remove "flexibility" language
4. ✅ Add strict validation: "STOP at 35 questions"
5. ✅ Add duplicate detection sau khi parse
