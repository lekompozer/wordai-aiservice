# 🎓 Conversation Test - IELTS Question Types Implementation

**Date:** 14/02/2026
**Purpose:** Chi tiết phân tích IELTS question types từ database thực tế và prompt generation cho conversation vocabulary/grammar tests

---

## 📊 Database Analysis - IELTS Question Types (Production Data)

### **Supported Question Types** (từ `online_tests` collection)

```javascript
// Query: db.online_tests.distinct("questions.question_type")
[
  "completion",           // ⭐ IELTS - Fill in blanks (form/note/table) -> Grammar
  "essay",                // Essay questions
  "matching",             // ⭐ IELTS - Match items -> Words
  "mcq",                  // ✅ Standard MCQ (1 correct answer)
  "mcq_multiple",         // ✅ MCQ with 2+ correct answers
  "sentence_completion",  // ⭐ IELTS - Complete sentences -> Words
  "short_answer",         // ⭐ IELTS - Short answer (1-3 words) -> Grammar
  "true_false_multiple"   // True/False questions
]
```

**Statistics:**
- Total tests: 239
- MCQ tests: 122
- Listening tests (IELTS style): 54

---

## 🎯 IELTS Question Types - Database Schema & Examples

### **1. MCQ (Single Answer)** ✅ PHÙ HỢP cho Vocabulary Definition

**Database Schema:**
```javascript
{
  "question_id": "q1",
  "question_type": "mcq",
  "question_text": "What is the primary industry focus of 7xCRM according to the comparison chart?",
  "options": [
    {"option_key": "A", "option_text": "Broad (Insurance)"},
    {"option_key": "B", "option_text": "Generic/None"},
    {"option_key": "C", "option_text": "Exclusive (Life Insurance)"},
    {"option_key": "D", "option_text": "All-in-One Marketing"}
  ],
  "correct_answers": ["C"],
  "explanation": "The document explicitly states under the 'Industry Focus' category that 7xCRM has an 'Exclusive (Life Insurance)' focus.",
  "max_points": 1
}
```

**Use Cases cho Conversation Test:**
- ✅ Vocabulary definition ("What does 'greet' mean?")
- ✅ Synonym/Antonym selection
- ✅ Best word to fill in blank
- ✅ Grammar pattern recognition ("Which sentence is correct?")

**Gemini Prompt Example:**
```json
{
  "question_type": "mcq",
  "question_text": "What does the word 'arrange' mean in the conversation?",
  "options": [
    {"option_key": "A", "option_text": "To organize or plan something"},
    {"option_key": "B", "option_text": "To cancel a meeting"},
    {"option_key": "C", "option_text": "To delay an event"},
    {"option_key": "D", "option_text": "To forget about plans"}
  ],
  "correct_answers": ["A"],
  "explanation": "In the conversation, 'arrange' means to organize or plan something, as seen in 'I'll arrange a meeting for next week.' | Trong hội thoại, 'arrange' có nghĩa là sắp xếp hoặc lên kế hoạch, như câu 'Tôi sẽ sắp xếp một cuộc họp vào tuần sau.'"
}
```

---

### **2. MCQ Multiple Answers** ✅ PHÙ HỢP cho Multiple Correct Options

**Database Schema:**
```javascript
{
  "question_id": "q2",
  "question_type": "mcq_multiple",
  "question_text": "Which of the following are modal verbs? (Select ALL that apply)",
  "options": [
    {"option_key": "A", "option_text": "can"},
    {"option_key": "B", "option_text": "walk"},
    {"option_key": "C", "option_text": "should"},
    {"option_key": "D", "option_text": "might"}
  ],
  "correct_answers": ["A", "C", "D"],  // Multiple correct!
  "explanation": "Modal verbs are: can, could, may, might, must, shall, should, will, would.",
  "max_points": 1
}
```

**Use Cases:**
- ✅ Select all grammar patterns used in conversation
- ✅ Identify all correct word forms
- ✅ Multiple vocabulary items with same meaning

---

### **3. MATCHING** ⭐ IELTS - PHÙ HỢP cho Vocabulary/Grammar Matching

**Database Schema:**
```javascript
{
  "question_id": "q3",
  "question_type": "matching",
  "question_text": "Match each word to its correct definition",
  "instruction": "Write the correct letter A-E next to each number 1-3",

  "left_items": [
    {"key": "1", "text": "greet"},
    {"key": "2", "text": "introduce"},
    {"key": "3", "text": "farewell"}
  ],

  "right_options": [
    {"key": "A", "text": "To say hello to someone"},
    {"key": "B", "text": "To make someone known to others"},
    {"key": "C", "text": "To say goodbye"},
    {"key": "D", "text": "To ask a question"},
    {"key": "E", "text": "To give directions"}
  ],

  "correct_answers": [
    {"left_key": "1", "right_key": "A"},
    {"left_key": "2", "right_key": "B"},
    {"left_key": "3", "right_key": "C"}
  ],

  "explanation": "Matching vocabulary to definitions based on conversation context.",
  "max_points": 1
}
```

**Production Example (Hotel Booking):**
```javascript
{
  "question_text": "Where are the following facilities located?",
  "left_items": [
    {"key": "8", "text": "Gym"},
    {"key": "9", "text": "Spa"},
    {"key": "10", "text": "Kids Club"}
  ],
  "right_options": [
    {"key": "A", "text": "On the rooftop"},
    {"key": "B", "text": "Behind the reception"},
    {"key": "C", "text": "Next to the garden"},
    {"key": "D", "text": "Near the swimming pool"},
    {"key": "E", "text": "In the basement"}
  ],
  "correct_answers": [
    {"left_key": "8", "right_key": "C"},
    {"left_key": "9", "right_key": "A"},
    {"left_key": "10", "right_key": "B"}
  ]
}
```

**Use Cases for Conversation:**
- ✅ Match vocabulary words to Vietnamese translations
- ✅ Match grammar patterns to examples from conversation
- ✅ Match words to their part of speech (NOUN, VERB, ADJ)
- ✅ Match speakers to what they said

**⚠️ CRITICAL:** 1 matching question object = 1 question (không phải 3 câu!)

---

### **4. COMPLETION** ⭐ IELTS - PHÙ HỢP cho Fill-in-the-Blank

**Database Schema:**
```javascript
{
  "question_id": "q4",
  "question_type": "completion",
  "question_text": "Complete the booking form below",
  "instruction": "Write NO MORE THAN TWO WORDS AND/OR A NUMBER for each answer",

  "template": "BOOKING FORM\n\nArrival Date: _____(1)_____\nRoom Type: _____(2)_____\nGuest Surname: _____(3)_____\nPhone Number: _____(4)_____",

  "blanks": [
    {"key": "1", "position": "Arrival Date", "word_limit": 3},
    {"key": "2", "position": "Room Type", "word_limit": 3},
    {"key": "3", "position": "Guest Surname", "word_limit": 1},
    {"key": "4", "position": "Phone Number", "word_limit": 3}
  ],

  "correct_answers": [
    {"blank_key": "1", "answers": ["15th July", "15 July", "July 15th", "July 15"]},
    {"blank_key": "2", "answers": ["Ocean View Suite", "Ocean View", "Suite"]},
    {"blank_key": "3", "answers": ["Miller", "MILLER"]},
    {"blank_key": "4", "answers": ["0908 555 231", "0908555231"]}
  ],

  "explanation": "Information extracted from the hotel booking conversation.",
  "max_points": 1
}
```

**Use Cases for Conversation:**
- ✅ Complete dialogue with missing vocabulary words
- ✅ Fill in grammar patterns in conversation context
- ✅ Complete phrases from conversation

**Gemini Prompt Example:**
```json
{
  "question_type": "completion",
  "question_text": "Complete the conversation excerpt below",
  "instruction": "Write NO MORE THAN TWO WORDS for each answer",
  "template": "A: How _____(1)_____ you?\nB: I'm _____(2)_____, thanks. And you?\nA: Not _____(3)_____. Just a bit tired.",
  "blanks": [
    {"key": "1", "position": "greeting question", "word_limit": 1},
    {"key": "2", "position": "response", "word_limit": 1},
    {"key": "3", "position": "negative response", "word_limit": 1}
  ],
  "correct_answers": [
    {"blank_key": "1", "answers": ["are", "ARE"]},
    {"blank_key": "2", "answers": ["fine", "good", "well", "great"]},
    {"blank_key": "3", "answers": ["bad", "terrible", "awful"]}
  ],
  "explanation": "Standard greeting patterns: 'How are you?' + positive/negative responses."
}
```

**⚠️ CRITICAL:** 1 completion object = 1 question (dù có 5 blanks!)

---

### **5. SENTENCE COMPLETION** ⭐ IELTS - PHÙ HỢP cho Grammar Practice

**Database Schema:**
```javascript
{
  "question_id": "q5",
  "question_type": "sentence_completion",
  "question_text": "Complete the sentences below using words from the conversation",
  "instruction": "Write NO MORE THAN ONE WORD for each answer",

  "sentences": [
    {
      "key": "1",
      "template": "The guest mentions that his wife is a ______.",
      "word_limit": 1,
      "correct_answers": ["vegetarian"]
    },
    {
      "key": "2",
      "template": "The hotel offers a ______ breakfast buffet.",
      "word_limit": 1,
      "correct_answers": ["complimentary", "free"]
    },
    {
      "key": "3",
      "template": "Check-out time is at ______ noon.",
      "word_limit": 1,
      "correct_answers": ["12", "twelve"]
    }
  ],

  "explanation": "Details from the hotel booking conversation.",
  "max_points": 1
}
```

**Use Cases for Conversation:**
- ✅ Complete sentences using vocabulary from dialogue
- ✅ Fill in correct grammar forms (tense, preposition, etc.)
- ✅ Practice word forms (noun/verb/adjective variations)

**Gemini Prompt Example:**
```json
{
  "question_type": "sentence_completion",
  "question_text": "Complete the sentences using grammar patterns from the conversation",
  "instruction": "Write NO MORE THAN TWO WORDS for each answer",
  "sentences": [
    {
      "key": "1",
      "template": "I would like ______ a meeting for next week.",
      "word_limit": 2,
      "correct_answers": ["to arrange", "to schedule", "to plan"]
    },
    {
      "key": "2",
      "template": "Can you ______ me the documents?",
      "word_limit": 1,
      "correct_answers": ["send", "email", "give"]
    },
    {
      "key": "3",
      "template": "I'm looking forward ______ from you.",
      "word_limit": 2,
      "correct_answers": ["to hearing", "to receiving"]
    }
  ],
  "explanation": "Common business English patterns: 'would like to + verb', 'Can you + verb', 'looking forward to + -ing'"
}
```

**⚠️ CRITICAL:** 1 sentence_completion object với 3 sentences = 1 question (không phải 3!)

---

### **6. SHORT ANSWER** ⭐ IELTS - PHÙ HỢP cho Open-ended Questions

**Database Schema:**
```javascript
{
  "question_id": "q6",
  "question_type": "short_answer",
  "question_text": "What time does the library open?",
  "instruction": "Write NO MORE THAN TWO WORDS AND/OR A NUMBER",
  "word_limit": 3,

  "correct_answers": [
    "9 AM",
    "9:00 AM",
    "9 o'clock",
    "nine AM"
  ],

  "explanation": "The librarian mentions opening time in the conversation.",
  "max_points": 1
}
```

**Use Cases for Conversation:**
- ✅ Answer questions about conversation content
- ✅ Extract specific information (time, place, names)
- ✅ Grammar transformation exercises

**Gemini Prompt Example:**
```json
{
  "question_type": "short_answer",
  "question_text": "What does Sarah want to do?",
  "instruction": "Write NO MORE THAN THREE WORDS",
  "word_limit": 3,
  "correct_answers": [
    "arrange a meeting",
    "schedule a meeting",
    "plan a meeting",
    "set up meeting"
  ],
  "explanation": "Sarah says 'I'd like to arrange a meeting' in the conversation."
}
```

---

## 🎨 Question Distribution by Level

### **Beginner (10 Questions Total)**

**Distribution:**
```
4 MCQ (Single) - Vocabulary definition          40%
2 Matching - Words to Vietnamese               20%
2 Completion - Fill dialogue blanks            20%
2 Sentence Completion - Grammar practice        20%
```

**Example Test Structure:**
```json
{
  "questions": [
    // Q1-4: MCQ Vocabulary
    {"question_type": "mcq", "question_text": "What does 'greet' mean?", ...},
    {"question_type": "mcq", "question_text": "What does 'morning' mean?", ...},
    {"question_type": "mcq", "question_text": "Choose the correct synonym for 'hello'", ...},
    {"question_type": "mcq", "question_text": "Which word means 'goodbye'?", ...},

    // Q5: Matching (1 question object, 4 matches)
    {
      "question_type": "matching",
      "question_text": "Match each English word to its Vietnamese translation",
      "left_items": [
        {"key": "1", "text": "hello"},
        {"key": "2", "text": "goodbye"},
        {"key": "3", "text": "thank you"},
        {"key": "4", "text": "you're welcome"}
      ],
      "right_options": [
        {"key": "A", "text": "tạm biệt"},
        {"key": "B", "text": "xin chào"},
        {"key": "C", "text": "cảm ơn"},
        {"key": "D", "text": "không có gì"},
        {"key": "E", "text": "xin lỗi"}
      ],
      "correct_answers": [
        {"left_key": "1", "right_key": "B"},
        {"left_key": "2", "right_key": "A"},
        {"left_key": "3", "right_key": "C"},
        {"left_key": "4", "right_key": "D"}
      ]
    },

    // Q6: Completion (1 question, 3 blanks)
    {
      "question_type": "completion",
      "question_text": "Complete the dialogue below",
      "instruction": "Write NO MORE THAN ONE WORD for each answer",
      "template": "A: _____(1)_____, how are you?\nB: I'm _____(2)_____, thanks!\nA: Nice to _____(3)_____ you!",
      "blanks": [
        {"key": "1", "word_limit": 1},
        {"key": "2", "word_limit": 1},
        {"key": "3", "word_limit": 1}
      ],
      "correct_answers": [
        {"blank_key": "1", "answers": ["Hello", "Hi", "Hey"]},
        {"blank_key": "2", "answers": ["fine", "good", "great", "well"]},
        {"blank_key": "3", "answers": ["meet", "see"]}
      ]
    },

    // Q7-8: Sentence Completion
    {"question_type": "sentence_completion", "sentences": [...]}
  ]
}
```

---

### **Intermediate (15 Questions Total)**

**Distribution:**
```
5 MCQ (Single/Multiple) - Vocabulary nuances     33%
3 Matching - Grammar patterns to examples        20%
3 Completion - Fill conversation gaps            20%
2 Sentence Completion - Grammar structures       13%
2 Short Answer - Comprehension                   14%
```

---

### **Advanced (20 Questions Total)**

**Distribution:**
```
6 MCQ (Mixed) - Idiomatic expressions           30%
4 Matching - Complex vocabulary/register         20%
4 Completion - Advanced grammar contexts         20%
3 Sentence Completion - Complex structures       15%
3 Short Answer - Discourse analysis              15%
```

---

## 🤖 DeepSeek/Gemini Prompt Template (Complete)

### **Prompt for Beginner Test (10 Questions)**

```
Generate an English vocabulary and grammar test for BEGINNER level based on the conversation below.

**SOURCE CONVERSATION:**
Title: "Hello, How Are You?"
Dialogue:
[Speaker A] Hi! How are you?
[Speaker B] I'm fine, thanks. And you?
[Speaker A] I'm good. Nice to meet you!
[Speaker B] Nice to meet you too!

**VOCABULARY (8 words):**
1. greet (VERB) - To say hello to someone
   Example: "I greet my friends every morning"

2. fine (ADJ) - In good health or condition
   Example: "I'm fine, thanks"

... (6 more vocabulary items)

**GRAMMAR (4 patterns):**
1. How are you? - Common greeting question
   Example: "Hi John, how are you today?"

... (3 more grammar patterns)

---

**TEST REQUIREMENTS:**

**Question Count:** EXACTLY 10 questions (CRITICAL - count carefully!)

**Question Distribution:**
- 4 MCQ (single answer) - Vocabulary definitions
- 2 Matching - Words to Vietnamese translation
- 2 Completion - Fill dialogue blanks
- 2 Sentence Completion - Grammar practice

**Question Types Explained:**

1. **MCQ (question_type: "mcq"):**
   - 4 options (A, B, C, D)
   - 1 correct answer
   - Use "correct_answers": ["A"]
   - Include explanation in BOTH English and Vietnamese

2. **Matching (question_type: "matching"):**
   - left_items: 4-5 items to match (numbered keys: "1", "2", etc.)
   - right_options: 5-6 options (letter keys: "A", "B", etc.) - MORE than left items
   - correct_answers: [{{"left_key": "1", "right_key": "A"}}, ...]
   - 1 matching object = 1 question (not 4 questions!)

3. **Completion (question_type: "completion"):**
   - template: String with _____(1)_____, _____(2)_____ format
   - blanks: Array matching number of blanks
   - correct_answers: [{{"blank_key": "1", "answers": ["word1", "word2"]}}, ...]
   - 1 completion object = 1 question (not 3 questions!)

4. **Sentence Completion (question_type: "sentence_completion"):**
   - sentences: Array of sentence objects
   - Each sentence: {{"key": "1", "template": "...", "word_limit": 1, "correct_answers": ["word"]}}
   - 1 sentence_completion object = 1 question

**OUTPUT FORMAT (JSON only, no markdown):**
{{
  "questions": [
    {{
      "question_type": "mcq",
      "question_text": "What does the word 'greet' mean?",
      "options": [
        {{"option_key": "A", "option_text": "To say hello"}},
        {{"option_key": "B", "option_text": "To say goodbye"}},
        {{"option_key": "C", "option_text": "To ask a question"}},
        {{"option_key": "D", "option_text": "To make a request"}}
      ],
      "correct_answers": ["A"],
      "explanation": "The word 'greet' means to say hello or welcome someone. | Từ 'greet' có nghĩa là chào hỏi hoặc chào đón ai đó.",
      "max_points": 1
    }},

    ... (3 more MCQ)

    {{
      "question_type": "matching",
      "question_text": "Match each English word from the conversation to its Vietnamese translation",
      "instruction": "Write the correct letter A-E next to numbers 1-4",
      "left_items": [
        {{"key": "1", "text": "hello"}},
        {{"key": "2", "text": "fine"}},
        {{"key": "3", "text": "thanks"}},
        {{"key": "4", "text": "meet"}}
      ],
      "right_options": [
        {{"key": "A", "text": "khỏe"}},
        {{"key": "B", "text": "xin chào"}},
        {{"key": "C", "text": "cảm ơn"}},
        {{"key": "D", "text": "gặp"}},
        {{"key": "E", "text": "tạm biệt"}}
      ],
      "correct_answers": [
        {{"left_key": "1", "right_key": "B"}},
        {{"left_key": "2", "right_key": "A"}},
        {{"left_key": "3", "right_key": "C"}},
        {{"left_key": "4", "right_key": "D"}}
      ],
      "explanation": "Vocabulary translations from the greeting conversation.",
      "max_points": 1
    }},

    ... (2 Completion questions)
    ... (2 Sentence Completion questions)
  ]
}}

**CRITICAL VALIDATION BEFORE RETURNING:**
✅ Total questions = 10 (count question objects, NOT sub-items!)
✅ Each MCQ has exactly 4 options
✅ Each matching has correct_answers with left_key/right_key pairs
✅ Each completion has template + blanks + correct_answers with blank_key
✅ Each sentence_completion has sentences array with correct_answers
✅ All explanations are in English | Vietnamese format
✅ All questions use vocabulary/grammar from the conversation ONLY

Generate the test now. Return ONLY valid JSON (no markdown, no extra text).
```

---

## 📋 Implementation Script Structure

### **File: `crawler/generate_conversation_tests_ielts.py`**

**Key Functions:**

```python
def build_test_prompt(conversation_id: str, vocab_data: Dict, level: str) -> str:
    """Build DeepSeek prompt with IELTS question types"""

    # Get conversation dialogue
    conv = db.conversation_library.find_one({"conversation_id": conversation_id})
    dialogue_text = format_dialogue(conv["dialogue"])

    # Get vocabulary and grammar
    vocabulary = vocab_data["vocabulary"]  # 8-15 items
    grammar_points = vocab_data["grammar_points"]  # 3-6 patterns

    # Level-specific configuration
    config = {
        "beginner": {
            "total_questions": 10,
            "distribution": {
                "mcq": 4,
                "matching": 2,
                "completion": 2,
                "sentence_completion": 2
            },
            "difficulty_desc": "Simple vocabulary, basic grammar patterns"
        },
        "intermediate": {
            "total_questions": 15,
            "distribution": {
                "mcq": 5,
                "matching": 3,
                "completion": 3,
                "sentence_completion": 2,
                "short_answer": 2
            },
            "difficulty_desc": "Moderate vocabulary with nuances, complex grammar"
        },
        "advanced": {
            "total_questions": 20,
            "distribution": {
                "mcq": 6,
                "mcq_multiple": 2,
                "matching": 4,
                "completion": 4,
                "sentence_completion": 3,
                "short_answer": 3
            },
            "difficulty_desc": "Advanced idiomatic expressions, sophisticated grammar"
        }
    }

    level_config = config[level]

    # Build prompt (see template above)
    prompt = f"""
    Generate an English vocabulary and grammar test for {level.upper()} level...

    **CONVERSATION:**
    {dialogue_text}

    **VOCABULARY ({len(vocabulary)} words):**
    {format_vocabulary(vocabulary)}

    **GRAMMAR ({len(grammar_points)} patterns):**
    {format_grammar(grammar_points)}

    **QUESTION DISTRIBUTION:**
    {format_distribution(level_config["distribution"])}

    ... (full prompt template)
    """

    return prompt


async def generate_test_questions(
    conversation_id: str,
    vocab_data: Dict,
    level: str
) -> List[Dict]:
    """Generate test questions using DeepSeek"""

    prompt = build_test_prompt(conversation_id, vocab_data, level)

    # Call DeepSeek API
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1"
    )

    for attempt in range(3):  # Retry up to 3 times
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000
            )

            # Parse JSON response
            content = response.choices[0].message.content
            content = content.strip().replace("```json", "").replace("```", "")
            data = json.loads(content)

            questions = data["questions"]

            # Validate question count
            expected_count = get_expected_count(level)
            if len(questions) != expected_count:
                logger.warning(f"Question count mismatch: {len(questions)} != {expected_count}")
                continue  # Retry

            # Validate each question schema
            for idx, q in enumerate(questions):
                validate_question_schema(q, idx + 1)

            logger.info(f"✅ Generated {len(questions)} questions for {conversation_id}")
            return questions

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error (attempt {attempt + 1}): {e}")
            if attempt == 2:
                raise
        except Exception as e:
            logger.error(f"Generation error (attempt {attempt + 1}): {e}")
            if attempt == 2:
                raise

    raise Exception("Failed after 3 attempts")


def validate_question_schema(question: Dict, index: int):
    """Validate question follows IELTS schema"""

    q_type = question.get("question_type")

    if not q_type:
        raise ValueError(f"Question {index}: Missing question_type")

    if q_type == "mcq":
        # Validate MCQ
        assert "question_text" in question
        assert "options" in question
        assert len(question["options"]) == 4
        assert "correct_answers" in question
        assert "explanation" in question

    elif q_type == "matching":
        # Validate Matching
        assert "left_items" in question
        assert "right_options" in question
        assert "correct_answers" in question
        # Verify correct_answers has left_key/right_key pairs
        for match in question["correct_answers"]:
            assert "left_key" in match and "right_key" in match

    elif q_type == "completion":
        # Validate Completion
        assert "template" in question
        assert "blanks" in question
        assert "correct_answers" in question
        # Verify correct_answers has blank_key/answers structure
        for answer in question["correct_answers"]:
            assert "blank_key" in answer and "answers" in answer

    elif q_type == "sentence_completion":
        # Validate Sentence Completion
        assert "sentences" in question
        for sent in question["sentences"]:
            assert "key" in sent
            assert "template" in sent
            assert "correct_answers" in sent

    elif q_type == "short_answer":
        # Validate Short Answer
        assert "question_text" in question
        assert "correct_answers" in question
        assert isinstance(question["correct_answers"], list)

    logger.debug(f"✅ Question {index} ({q_type}) validated")


async def save_test_to_database(
    conversation_id: str,
    questions: List[Dict],
    level: str,
    topic: str,
    title: str
) -> Tuple[str, str]:
    """Save test to online_tests collection"""

    # Generate test slug
    slug = f"test-{level}-{topic}-{conversation_id.split('_')[-1]}"

    # Prepare test document
    test_doc = {
        "title": f"Vocabulary & Grammar Test: {title}",
        "description": f"Test your understanding of vocabulary and grammar from the conversation '{title}'",

        # Creator info
        "creator_id": "wordai_team",  # ⭐ System-generated
        "creator_name": "WordAI Team",

        # Test configuration
        "test_type": "mcq",
        "test_category": "academic",
        "status": "ready",
        "is_active": True,

        # Conversation linkage (NEW)
        "source_type": "conversation",  # ⭐ NEW
        "conversation_id": conversation_id,
        "conversation_level": level,
        "conversation_topic": topic,

        # Test settings
        "time_limit_minutes": get_time_limit(level),  # 10/15/20
        "max_retries": 3,
        "passing_score": 70,
        "show_answers_timing": "immediate",

        # Questions (IELTS format)
        "questions": questions,

        # Marketplace (optional)
        "marketplace_config": {
            "is_published": False,
            "price_points": 0,  # Free
            "category": "English Learning - Conversations",
            "tags": f"{level},vocabulary,grammar,conversation,IELTS"
        },

        # Cover image (placeholder)
        "cover_image_url": None,  # Generate later with Gemini

        # Timestamps
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "generated_at": datetime.utcnow()
    }

    # Insert to database
    result = db.online_tests.insert_one(test_doc)
    test_id = str(result.inserted_id)

    logger.info(f"💾 Saved test: {test_id} | Slug: {slug}")

    # Update conversation document
    db.conversation_library.update_one(
        {"conversation_id": conversation_id},
        {
            "$set": {
                "online_test_id": ObjectId(test_id),
                "online_test_slug": slug,
                "has_online_test": True
            }
        }
    )

    return test_id, slug
```

---

## 🔑 Key Insights from Production Database

### **1. Question Type Confusion (AI Error Patterns)**

**Common Mistakes:**
```javascript
// ❌ WRONG: AI confuses completion with matching
{
  "question_type": "completion",
  "correct_matches": [...]  // Wrong field for completion!
}

// ✅ CORRECT: Completion uses correct_answers with blank_key
{
  "question_type": "completion",
  "correct_answers": [
    {"blank_key": "1", "answers": ["word"]}
  ]
}
```

**Solution:** Validation function catches this error and rejects question

---

### **2. Question Counting Logic**

**CRITICAL:** 1 question object ≠ number of sub-items

```javascript
// Example 1: MATCHING - Counts as 1 question (not 5!)
{
  "question_type": "matching",
  "left_items": [
    {"key": "1", ...},
    {"key": "2", ...},
    {"key": "3", ...},
    {"key": "4", ...},
    {"key": "5", ...}
  ],
  ...
}
// This is 1 QUESTION (not 5 questions!)

// Example 2: COMPLETION - Counts as 1 question (not 4!)
{
  "question_type": "completion",
  "template": "_____(1)_____ ... _____(2)_____ ... _____(3)_____ ... _____(4)_____",
  ...
}
// This is 1 QUESTION (not 4 questions!)
```

**Why This Matters:**
- If generating 10 questions total
- 1 matching (5 items) + 1 completion (4 blanks) + 8 MCQ = 10 questions ✅
- NOT: 5 + 4 + 8 = 17 questions ❌

---

### **3. Explanation Format**

**Best Practice (Bilingual):**
```javascript
{
  "explanation": "The word 'greet' means to say hello or welcome someone. | Từ 'greet' có nghĩa là chào hỏi hoặc chào đón ai đó."
}
```

**Format:** `English explanation. | Vietnamese explanation.`

---

## ✅ Testing & Validation Checklist

Before running full generation (1,739 conversations):

- [ ] Test prompt với 1 beginner conversation
- [ ] Test prompt với 1 intermediate conversation
- [ ] Test prompt với 1 advanced conversation
- [ ] Validate question count cho mỗi level
- [ ] Validate tất cả question types schema
- [ ] Check explanation format (EN | VI)
- [ ] Verify correct_answers structure cho mỗi type
- [ ] Test với English teacher (native speaker review)
- [ ] A/B test với 50 beta users
- [ ] Monitor DeepSeek API error rate
- [ ] Check database insert success rate

---

## 📊 Expected Results

**After Full Generation:**

```javascript
// Query conversation tests
db.online_tests.countDocuments({source_type: "conversation"})
// Expected: 1,739 tests

// Query by level
db.online_tests.countDocuments({
  source_type: "conversation",
  conversation_level: "beginner"
})
// Expected: 600

// Query with test link
db.conversation_library.countDocuments({has_online_test: true})
// Expected: 1,739

// Example document
{
  _id: ObjectId("..."),
  title: "Vocabulary & Grammar Test: Hello, How Are You?",
  creator_id: "wordai_team",
  source_type: "conversation",
  conversation_id: "conv_beginner_greetings_01_001",
  questions: [
    {"question_type": "mcq", ...},
    {"question_type": "matching", ...},
    {"question_type": "completion", ...},
    {"question_type": "sentence_completion", ...}
  ]
}
```

---

## 🚀 Next Steps

1. ✅ **Validated IELTS Schema** - Complete
2. ⏳ **Create Prompt Template** - Ready for implementation
3. ⏳ **Build Generation Script** - `crawler/generate_conversation_tests_ielts.py`
4. ⏳ **Test with 3 conversations** (1 per level)
5. ⏳ **Manual review** (English teacher validation)
6. ⏳ **Full generation** (1,739 conversations)
7. ⏳ **Frontend integration** ("Take Test" button)

---

**Document Version:** 1.0
**Last Updated:** 14/02/2026
**Based On:** Production database analysis (104.248.147.155)
