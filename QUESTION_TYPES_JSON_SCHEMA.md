# Question Types - Complete JSON Schema Reference

**For Frontend Integration**

This document describes the EXACT JSON format for ALL question types returned by the backend API.

---

## Database & Collection Info

- **Database:** `ai_service_db`
- **Collection:** `online_tests`
- **ID Format:** ObjectId (use `ObjectId(test_id)` in MongoDB queries)
- **Connection String:** `mongodb://admin:ai_admin_2025_secure_password@mongodb:27017/?authSource=admin`

---

## Response Structure

All test endpoints return tests with a `questions` array:

```json
{
  "_id": "ObjectId('...')",
  "title": "Test Title",
  "status": "ready",
  "questions": [
    { /* Question Object - see formats below */ }
  ],
  "num_questions": 15,
  "time_limit_minutes": 20,
  "created_at": "2025-12-14T19:43:04.547000",
  "generated_at": "2025-12-14T19:43:58.501000"
}
```

---

## Question Types Overview

| Type | Description | Field Name | Correct Answer Format |
|------|-------------|------------|----------------------|
| `mcq` | Multiple Choice (Single) | `correct_answers` | `["A"]` |
| `mcq_multiple` | Multiple Choice (Multiple) | `correct_answers` | `["A", "C"]` |
| `matching` | Match Items | `correct_answers` | `[{"left_key": "1", "right_key": "A"}]` |
| `completion` | Fill Blanks (IELTS) | `correct_answers` | `[{"blank_key": "1", "answers": ["text"]}]` |
| `sentence_completion` | Complete Sentence | `correct_answers` | `["word", "variation"]` |
| `short_answer` | Short Answer | `correct_answers` | `["answer", "variation"]` |

⚠️ **CRITICAL:** ALL question types use `correct_answers` field (NOT `correct_answer_keys`, `correct_matches`, etc.)

---

## 1. MCQ (Multiple Choice - Single Answer)

**Type:** `"question_type": "mcq"`

### JSON Schema

```json
{
  "question_type": "mcq",
  "question_text": "What is the capital of France?",
  "options": [
    {
      "option_key": "A",
      "option_text": "London"
    },
    {
      "option_key": "B",
      "option_text": "Paris"
    },
    {
      "option_key": "C",
      "option_text": "Berlin"
    },
    {
      "option_key": "D",
      "option_text": "Madrid"
    }
  ],
  "correct_answers": ["B"],
  "explanation": "Paris is the capital and largest city of France.",
  "points": 1,
  "question_id": "693eb10e3456aa028c4ee80a"
}
```

### Required Fields
- `question_type`: `"mcq"`
- `question_text`: String (the question)
- `options`: Array of objects with `option_key` and `option_text`
- `correct_answers`: Array with ONE option key (e.g., `["B"]`)
- `explanation`: String (why answer is correct)
- `points`: Integer (1-5, difficulty scoring)

### Frontend Display
```typescript
// Render options with radio buttons
question.options.map(opt => (
  <Radio
    value={opt.option_key}
    checked={userAnswer === opt.option_key}
  >
    {opt.option_key}. {opt.option_text}
  </Radio>
))

// Check answer
const isCorrect = question.correct_answers.includes(userAnswer)
```

---

## 2. MCQ Multiple (Multiple Correct Answers)

**Type:** `"question_type": "mcq_multiple"`

### JSON Schema

```json
{
  "question_type": "mcq_multiple",
  "question_text": "Which of these are European capitals?",
  "options": [
    {
      "option_key": "A",
      "option_text": "Paris"
    },
    {
      "option_key": "B",
      "option_text": "Tokyo"
    },
    {
      "option_key": "C",
      "option_text": "Berlin"
    },
    {
      "option_key": "D",
      "option_text": "Sydney"
    }
  ],
  "correct_answers": ["A", "C"],
  "explanation": "Paris (France) and Berlin (Germany) are European capitals.",
  "points": 2,
  "question_id": "693eb10e3456aa028c4ee80b"
}
```

### Required Fields
- `question_type`: `"mcq_multiple"`
- `question_text`: String
- `options`: Array of objects with `option_key` and `option_text`
- `correct_answers`: Array with TWO OR MORE option keys (e.g., `["A", "C"]`)
- `explanation`: String
- `points`: Integer (1-5)

### Frontend Display
```typescript
// Render options with checkboxes
question.options.map(opt => (
  <Checkbox
    value={opt.option_key}
    checked={userAnswers.includes(opt.option_key)}
  >
    {opt.option_key}. {opt.option_text}
  </Checkbox>
))

// Check answer (must match exactly)
const isCorrect =
  userAnswers.sort().toString() ===
  question.correct_answers.sort().toString()
```

---

## 3. Matching

**Type:** `"question_type": "matching"`

### JSON Schema

```json
{
  "question_type": "matching",
  "question_text": "Match each country to its capital",
  "left_items": [
    {
      "key": "1",
      "text": "France"
    },
    {
      "key": "2",
      "text": "Germany"
    },
    {
      "key": "3",
      "text": "Italy"
    }
  ],
  "right_options": [
    {
      "key": "A",
      "text": "Paris"
    },
    {
      "key": "B",
      "text": "Berlin"
    },
    {
      "key": "C",
      "text": "Rome"
    },
    {
      "key": "D",
      "text": "Madrid"
    },
    {
      "key": "E",
      "text": "Athens"
    }
  ],
  "correct_answers": [
    {
      "left_key": "1",
      "right_key": "A"
    },
    {
      "left_key": "2",
      "right_key": "B"
    },
    {
      "left_key": "3",
      "right_key": "C"
    }
  ],
  "explanation": "Standard European capital city matches.",
  "points": 3,
  "question_id": "693eb10e3456aa028c4ee80c"
}
```

### Required Fields
- `question_type`: `"matching"`
- `question_text`: String
- `left_items`: Array of objects with `key` and `text`
- `right_options`: Array of objects with `key` and `text` (usually more options than items)
- `correct_answers`: Array of match objects with `left_key` and `right_key`
- `explanation`: String
- `points`: Integer (1-5)

### Frontend Display
```typescript
// Render matching interface
question.left_items.map(item => (
  <div>
    <span>{item.text}</span>
    <Select
      value={userMatches[item.key]}
      options={question.right_options}
    />
  </div>
))

// Check answer
const isCorrect = question.correct_answers.every(match =>
  userMatches[match.left_key] === match.right_key
)
```

---

## 4. Completion (IELTS Format)

**Type:** `"question_type": "completion"`

### JSON Schema

```json
{
  "question_type": "completion",
  "question_text": "Complete the registration form",
  "template": "Name: _____(1)_____\nPhone: _____(2)_____\nEmail: _____(3)_____",
  "blanks": [
    {
      "key": "1",
      "position": "Name field"
    },
    {
      "key": "2",
      "position": "Phone field"
    },
    {
      "key": "3",
      "position": "Email field"
    }
  ],
  "correct_answers": [
    {
      "blank_key": "1",
      "answers": ["John Smith", "john smith", "JOHN SMITH"]
    },
    {
      "blank_key": "2",
      "answers": ["0412 555 678", "0412555678"]
    },
    {
      "blank_key": "3",
      "answers": ["john@email.com", "JOHN@EMAIL.COM"]
    }
  ],
  "explanation": "Standard contact information format.",
  "points": 3,
  "question_id": "693eb10e3456aa028c4ee80d"
}
```

### Required Fields
- `question_type`: `"completion"`
- `question_text`: String (instructions)
- `template`: String with blanks marked as `_____(1)_____`, `_____(2)_____`, etc.
- `blanks`: Array of objects with `key` and `position` description
- `correct_answers`: Array of objects with:
  - `blank_key`: String (matches blank key)
  - `answers`: Array of acceptable text variations (case-insensitive matching)
- `explanation`: String
- `points`: Integer (1-5)

### Frontend Display
```typescript
// Parse template and render blanks as inputs
const parts = question.template.split(/_____(\\d+)_____/)
parts.map((part, i) => {
  if (i % 2 === 0) {
    return <span>{part}</span>
  } else {
    const blankKey = part
    return (
      <input
        value={userAnswers[blankKey]}
        placeholder={`(${blankKey})`}
      />
    )
  }
})

// Check answers (case-insensitive, trimmed)
question.correct_answers.forEach(answer => {
  const userAnswer = userAnswers[answer.blank_key]?.toLowerCase().trim()
  const isCorrect = answer.answers.some(valid =>
    valid.toLowerCase().trim() === userAnswer
  )
})
```

---

## 5. Sentence Completion

**Type:** `"question_type": "sentence_completion"`

⚠️ **CRITICAL FOR FRONTEND:** This type has `template` field containing the actual sentence to complete!

### JSON Schema

```json
{
  "question_type": "sentence_completion",
  "question_text": "Complete the sentence with ONE word from the text.",
  "template": "Remote employment has evolved from a contingency measure into a _____ feature of corporate strategy.",
  "correct_answers": ["permanent"],
  "explanation": "The text states remote employment has evolved into a 'permanent' feature of corporate strategy.",
  "points": 1,
  "question_id": "693eb10e3456aa028c4ee80d"
}
```

### Required Fields
- `question_type`: `"sentence_completion"`
- `question_text`: String (instructions - often generic like "Complete the sentence")
- `template`: String with `_____` marking where to fill in ⚠️ **MUST DISPLAY THIS!**
- `correct_answers`: Array of acceptable answer variations (strings)
- `explanation`: String
- `points`: Integer (1-5)

### Alternative Format (IELTS - with `sentences` array)

Some questions may use the IELTS format with multiple sentences:

```json
{
  "question_type": "sentence_completion",
  "question_text": "Complete each sentence with ONE word",
  "sentences": [
    {
      "key": "1",
      "template": "The library opens at _____.",
      "correct_answers": ["8 AM", "8:00 AM", "eight o'clock"]
    },
    {
      "key": "2",
      "template": "Books can be borrowed for _____ weeks.",
      "correct_answers": ["2", "two", "TWO"]
    }
  ],
  "explanation": "Based on library operating hours.",
  "points": 2,
  "question_id": "693eb10e3456aa028c4ee80e"
}
```

### Frontend Display

**IMPORTANT:** Must handle BOTH formats!

```typescript
// Check which format
if (question.template) {
  // Simple format - single sentence
  return (
    <div>
      <p>{question.question_text}</p>
      <div>
        {renderTemplateWithBlank(question.template)}
      </div>
    </div>
  )
} else if (question.sentences) {
  // IELTS format - multiple sentences
  return (
    <div>
      <p>{question.question_text}</p>
      {question.sentences.map(sent => (
        <div key={sent.key}>
          {sent.key}. {renderTemplateWithBlank(sent.template)}
        </div>
      ))}
    </div>
  )
}

// Helper to render template with blank
function renderTemplateWithBlank(template) {
  const parts = template.split('_____')
  return (
    <>
      <span>{parts[0]}</span>
      <input
        type="text"
        placeholder="..."
        style={{width: '150px'}}
      />
      <span>{parts[1]}</span>
    </>
  )
}

// Check answer (case-insensitive)
const userAnswer = userInput.toLowerCase().trim()
const isCorrect = question.correct_answers.some(valid =>
  valid.toLowerCase().trim() === userAnswer
)
```

---

## 6. Short Answer

**Type:** `"question_type": "short_answer"`

### JSON Schema

```json
{
  "question_type": "short_answer",
  "question_text": "What is the speaker's occupation?",
  "correct_answers": ["software engineer", "Software Engineer", "engineer"],
  "explanation": "Speaker mentions being a software engineer.",
  "points": 1,
  "question_id": "693eb10e3456aa028c4ee80f"
}
```

### Required Fields
- `question_type`: `"short_answer"`
- `question_text`: String (the question)
- `correct_answers`: Array of acceptable answer variations (1-3 words each)
- `explanation`: String
- `points`: Integer (1-5)

### Frontend Display
```typescript
// Simple text input
<div>
  <p>{question.question_text}</p>
  <input
    type="text"
    value={userAnswer}
    placeholder="Type your answer (1-3 words)"
  />
</div>

// Check answer (case-insensitive, trimmed)
const userAnswer = userInput.toLowerCase().trim()
const isCorrect = question.correct_answers.some(valid =>
  valid.toLowerCase().trim() === userAnswer
)
```

---

## Common Fields (All Types)

### Always Present
- `question_type`: String (one of: `mcq`, `mcq_multiple`, `matching`, `completion`, `sentence_completion`, `short_answer`)
- `question_text`: String (the question or instructions)
- `explanation`: String (why answer is correct / educational context)
- `points`: Integer (1-5, difficulty-based scoring)
- `question_id`: String (unique identifier)

### Answer Field
- `correct_answers`: Array (format varies by type - see above)

⚠️ **NEVER use these deprecated fields:**
- ❌ `correct_answer_key`
- ❌ `correct_answer_keys`
- ❌ `correct_matches`

---

## API Endpoints

### Get Test by ID
```http
GET /api/v1/tests/{test_id}
Authorization: Bearer {firebase_token}
```

⚠️ **IMPORTANT:** Response varies based on user's relationship to the test!

#### 1️⃣ **OWNER VIEW** (Creator/Owner)

**Includes:** Full test configuration + ALL questions **WITH correct_answers**

```json
{
  "success": true,
  "test_id": "693eb0d83456aa028c4ee7fe",
  "view_type": "owner",
  "is_owner": true,
  "access_type": "owner",

  // Basic info
  "title": "Advanced Reading Test",
  "description": "IELTS style reading comprehension",
  "test_type": "mcq",
  "test_category": "academic",
  "is_active": true,
  "status": "ready",

  // Test settings
  "max_retries": 3,
  "time_limit_minutes": 60,
  "passing_score": 70,
  "deadline": "2025-12-31T23:59:59",
  "show_answers_timing": "immediate",

  // Questions (WITH correct_answers for owner!)
  "num_questions": 15,
  "questions": [
    {
      "question_id": "...",
      "question_type": "mcq",
      "question_text": "What is...?",
      "options": [...],
      "correct_answers": ["B"],          // ✅ INCLUDED for owner
      "explanation": "...",              // ✅ INCLUDED for owner
      "max_points": 1
    },
    {
      "question_type": "sentence_completion",
      "question_text": "Complete the sentence...",
      "template": "The economy has _____.",
      "correct_answers": ["grown"],      // ✅ INCLUDED for owner
      "explanation": "...",
      "max_points": 1
    }
  ],

  // Audio sections (if listening test)
  "audio_sections": [
    {
      "section_number": 1,
      "section_title": "Conversation",
      "audio_url": "https://...",
      "duration_seconds": 180,
      "transcript": "Full transcript..."  // ✅ INCLUDED for owner
    }
  ],

  // Creation info
  "creation_type": "ai_generated",
  "test_language": "en",
  "evaluation_criteria": {...},

  // Statistics
  "total_submissions": 42,

  // Marketplace (if published)
  "is_published": true,
  "marketplace_config": {...},

  // Timestamps
  "created_at": "2025-12-14T19:43:04.547000",
  "updated_at": "2025-12-14T20:00:00.000000"
}
```

#### 2️⃣ **SHARED VIEW** (Invited Users/Test Takers)

**Includes:** Questions for taking **WITHOUT correct_answers**

```json
{
  "success": true,
  "test_id": "693eb0d83456aa028c4ee7fe",
  "view_type": "shared",
  "is_owner": false,
  "access_type": "shared",
  "status": "ready",

  "title": "Advanced Reading Test",
  "description": "IELTS style reading comprehension",
  "time_limit_minutes": 60,
  "num_questions": 15,

  "questions": [
    {
      "question_id": "...",
      "question_type": "mcq",
      "question_text": "What is...?",
      "options": [...],
      "max_points": 1
      // ❌ NO correct_answers
      // ❌ NO explanation
    },
    {
      "question_type": "sentence_completion",
      "question_text": "Complete the sentence...",
      "sentences": [
        {
          "key": "1",
          "template": "The economy has _____.",
          "word_limit": 1
          // ❌ NO correct_answers
        }
      ],
      "max_points": 1
      // ❌ NO explanation
    }
  ],

  // Attachments (PDF for reading comprehension)
  "attachments": [
    {
      "attachment_id": "...",
      "title": "Reading Passage 1",
      "description": "...",
      "file_url": "https://..."
    }
  ],

  // Audio sections (if listening test)
  "audio_sections": [
    {
      "section_number": 1,
      "section_title": "Conversation",
      "audio_url": "https://...",
      "duration_seconds": 180
      // ❌ NO transcript (owner-only)
    }
  ]
}
```

#### 3️⃣ **PUBLIC VIEW** (Marketplace - Not Purchased)

**Includes:** Marketplace info only, NO questions revealed

```json
{
  "success": true,
  "test_id": "693eb0d83456aa028c4ee7fe",
  "view_type": "public",
  "is_owner": false,
  "access_type": "public",

  // Marketplace info
  "title": "Advanced Reading Test",
  "description": "Complete IELTS style test...",
  "short_description": "Perfect for exam prep",
  "cover_image_url": "https://...",

  // Test configuration (basic)
  "num_questions": 15,
  "time_limit_minutes": 60,
  "passing_score": 70,
  "max_retries": 3,

  // Marketplace metadata
  "price_points": 500,
  "category": "ielts",
  "tags": ["reading", "academic"],
  "difficulty_level": "advanced",
  "version": "v1",

  // Community statistics
  "total_participants": 328,
  "average_participant_score": 72.5,
  "average_rating": 4.7,
  "rating_count": 156,

  // Publication info
  "published_at": "2025-11-01T00:00:00",
  "creator_id": "...",

  // User-specific info
  "already_participated": false,
  "attempts_used": 0,
  "user_best_score": null,

  // Additional metadata
  "creation_type": "ai_generated",
  "test_language": "en"

  // ❌ NO questions (must purchase first)
}
```

#### Access Control Summary

| User Type | Questions Included? | Correct Answers? | Explanation? | Full Config? |
|-----------|-------------------|-----------------|--------------|--------------|
| **Owner** | ✅ All questions | ✅ Yes | ✅ Yes | ✅ Yes |
| **Shared** | ✅ All questions | ❌ No | ❌ No | ❌ Basic only |
| **Public** | ❌ No questions | ❌ No | ❌ No | ❌ Marketplace only |

**Key Points:**
- **Owner:** Sees everything including correct_answers, explanation, transcript
- **Shared:** Gets questions for taking, but NO correct_answers or explanation
- **Public:** Marketplace info only, must purchase to get access

### Get My Tests
```http
GET /api/v1/tests/me/tests?limit=100&offset=0
Authorization: Bearer {firebase_token}
```

### Get Submission Results (After Submit)
```http
GET /api/v1/me/submissions/{submission_id}
Authorization: Bearer {firebase_token}
```

**Response - Full (show_answers_timing: immediate):**
```json
{
  "submission_id": "693eb...",
  "test_title": "Test Title",
  "test_category": "academic",
  "is_diagnostic_test": false,
  "has_ai_evaluation": true,
  "grading_status": "fully_graded",

  // Score fields (ALL displayed on frontend)
  "score": 8.5,                    // Total score out of 10 (thang 10)
  "score_percentage": 85.0,        // Percentage (%)
  "mcq_score": 6.0,                // MCQ score only (if applicable)
  "essay_score": 2.5,              // Essay score only (if applicable)
  "mcq_correct_count": 6,          // Number of correct MCQ answers
  "correct_answers": 6,            // Total correct (mainly for MCQ)
  "total_questions": 10,

  "time_taken_seconds": 1200,
  "attempt_number": 1,
  "is_passed": true,
  "submitted_at": "2025-12-14T20:00:00",

  "results": [
    { /* Question result objects - see formats above */ }
  ],

  "audio_sections": [],             // For listening tests
  "message": "..."                  // Optional status message
}
```

**Response - Limited (show_answers_timing: after_deadline, before deadline):**
```json
{
  "submission_id": "693eb...",
  "test_title": "Test Title",
  "grading_status": "fully_graded",

  // Score fields (still shown)
  "score": 8.5,
  "score_percentage": 85.0,
  "mcq_score": 6.0,                // NEW: Now included
  "essay_score": 2.5,              // NEW: Now included
  "correct_answers": 6,
  "total_questions": 10,

  "is_passed": true,
  "submitted_at": "2025-12-14T20:00:00",
  "results_hidden_until_deadline": "2025-12-20T23:59:59",
  "message": "Detailed answers and explanations will be revealed after the deadline"
}
```

**Grading Status Values:**
- `auto_graded`: All questions auto-graded (MCQ/IELTS only)
- `pending_grading`: Has essay questions, none graded yet
- `partially_graded`: Some essays graded, some pending
- `fully_graded`: All essays graded

**Score Fields Explanation:**
- `score`: Total score scaled to 10-point scale (thang 10)
- `score_percentage`: Percentage score (0-100%)
- `mcq_score`: Points earned from MCQ questions only (if test has MCQ)
- `essay_score`: Points earned from essay questions only (if test has essays)
- `correct_answers`: Count of correct MCQ answers
- `total_questions`: Total number of questions in test

---

## Validation Rules

### Answer Checking
1. **MCQ/MCQ Multiple:** Exact match of option keys
2. **Matching:** All pairs must match exactly
3. **Completion:** Case-insensitive, trimmed match against any valid variation
4. **Sentence Completion:** Case-insensitive, trimmed match against any valid variation
5. **Short Answer:** Case-insensitive, trimmed match against any valid variation

### Points Calculation
```typescript
const calculateScore = (userAnswers, questions) => {
  let totalPoints = 0
  let earnedPoints = 0

  questions.forEach(q => {
    totalPoints += q.points
    if (isAnswerCorrect(q, userAnswers[q.question_id])) {
      earnedPoints += q.points
    }
  })

  return {
    earnedPoints,
    totalPoints,
    percentage: (earnedPoints / totalPoints) * 100
  }
}
```

---





---

## Troubleshooting

### Common Issues

**1. Test not found**
- ✅ Use `ObjectId(test_id)` not string
- ✅ Query `ai_service_db` database
- ✅ Query `online_tests` collection

**2. Questions not displaying**
- ✅ Check `question.template` field for sentence_completion
- ✅ Don't just show `question_text` (it's often generic)
- ✅ Handle both simple and IELTS formats for sentence_completion

**3. Answer validation failing**
- ✅ Use `correct_answers` field (not old field names)
- ✅ Trim and lowercase for text answers
- ✅ Check all variations in `answers` array

**4. MongoDB connection fails**
- ✅ Use admin credentials
- ✅ Specify `authSource=admin`
- ✅ Connect to correct database: `ai_service_db`

---

## Version Info

- **Last Updated:** December 14, 2025
- **Backend Version:** Production
- **Database:** MongoDB (ai_service_db)
- **Schema Version:** 2.0 (unified correct_answers)

---

## Contact

For issues or questions about this schema:
- Backend: Check `src/services/test_generator_service.py`
- Prompts: Check `src/services/prompt_builders.py`
- Routes: Check `src/api/test_creation_routes.py`
