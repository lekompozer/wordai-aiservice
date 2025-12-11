# MCQ Type Distribution & Merge Tests API Documentation

## Overview
This document describes two major features added to the test creation system:
1. **MCQ Type Distribution**: Configure different types of multiple-choice questions in AI-generated tests
2. **Merge Tests**: Combine questions from multiple tests into one new test

---

## Feature 1: MCQ Type Distribution

### Supported MCQ Question Types

The system now supports 6 different types of MCQ questions:

1. **Single-answer MCQ** (`mcq`): Traditional multiple choice with 1 correct answer
2. **Multiple-answer MCQ** (`mcq_multiple`): Select all that apply (2+ correct answers)
3. **Matching** (`matching`): Match left items to right options (IELTS style)
4. **Completion** (`completion`): Fill in blanks in form/note/table (IELTS style)
5. **Sentence Completion** (`sentence_completion`): Complete sentences (IELTS style)
6. **Short Answer** (`short_answer`): 1-3 words answers (IELTS style)

### Distribution Modes

- **Auto Mode** (default): AI decides question type distribution based on document content
- **Manual Mode**: User specifies exact quantity for each question type

---

## Endpoints Supporting MCQ Type Distribution

### 1. Generate Test from Document/File

**Endpoint:** `POST /api/v1/tests/generate`

**New Field:** `mcq_type_config` (optional)

#### Request Body Schema

```
{
  "source_type": "document" | "file",
  "source_id": "string (document ID or R2 file key)",
  "title": "string (5-200 chars)",
  "description": "string (optional, max 1000 chars)",
  "creator_name": "string (optional, 2-100 chars)",
  "user_query": "string (optional, 10-2000 chars)",
  "language": "string (default: 'vi')",
  "difficulty": "easy" | "medium" | "hard" | null,
  "test_type": "mcq" | "essay" | "mixed",
  "num_questions": integer (1-100) [for mcq/essay type],
  "num_mcq_questions": integer (0-100) [for mixed type],
  "num_essay_questions": integer (0-20) [for mixed type],
  "mcq_points": integer (0-1000) [optional, for mixed type],
  "essay_points": integer (0-1000) [optional, for mixed type],
  "time_limit_minutes": integer (1-270, default: 30),
  "max_retries": integer (1-10, default: 3),
  "passing_score": integer (0-100, default: 70),
  "deadline": "ISO 8601 datetime string" | null,
  "show_answers_timing": "immediate" | "after_deadline" (default: "immediate"),
  "num_options": integer (0-10, default: 4),
  "num_correct_answers": integer (0-10, default: 1),
  "test_category": "academic" | "diagnostic" (default: "academic"),
  "mcq_type_config": {
    "num_single_answer_mcq": integer (0-50) | null,
    "num_multiple_answer_mcq": integer (0-30) | null,
    "num_matching": integer (0-20) | null,
    "num_completion": integer (0-20) | null,
    "num_sentence_completion": integer (0-20) | null,
    "num_short_answer": integer (0-20) | null,
    "distribution_mode": "auto" | "manual" (default: "auto")
  } | null
}
```

#### mcq_type_config Validation Rules

**Manual Mode:**
- At least one question type count must be specified (non-zero)
- Total questions across all types cannot exceed 100
- All counts must be non-negative

**Auto Mode:**
- All type counts are ignored
- AI determines best distribution based on content

#### Response Schema

**Success Response (202 Accepted):**
```
{
  "success": true,
  "test_id": "string (MongoDB ObjectId)",
  "status": "pending",
  "title": "string",
  "description": "string | null",
  "num_questions": integer,
  "time_limit_minutes": integer,
  "created_at": "ISO 8601 datetime string",
  "message": "Test created successfully. AI is generating questions..."
}
```

**Error Responses:**

- **400 Bad Request** - Invalid source_id, invalid field validation, or missing required fields
- **403 Forbidden** - Access denied to source document/file
- **404 Not Found** - Source document/file not found
- **500 Internal Server Error** - Server error during test creation

---

### 2. Generate Test from General Knowledge

**Endpoint:** `POST /api/v1/tests/generate/general`

**New Field:** `mcq_type_config` (optional)

#### Request Body Schema

```
{
  "title": "string (5-200 chars)",
  "description": "string (optional, max 1000 chars)",
  "creator_name": "string (optional, 2-100 chars)",
  "topic": "string (3-200 chars)",
  "user_query": "string (10-2000 chars)",
  "test_category": "academic" | "diagnostic" (default: "academic"),
  "language": "string (default: 'vi')",
  "difficulty": "easy" | "medium" | "hard" | null,
  "test_type": "mcq" | "essay" | "mixed" (default: "mcq"),
  "num_questions": integer (1-100) | null [for mcq/essay type],
  "num_mcq_questions": integer (0-100) | null [for mixed type],
  "num_essay_questions": integer (0-20) | null [for mixed type],
  "mcq_points": integer (0-1000) | null [for mixed type],
  "essay_points": integer (0-1000) | null [for mixed type],
  "time_limit_minutes": integer (1-300, default: 30),
  "max_retries": integer (1-10, default: 3),
  "passing_score": integer (0-100, default: 50),
  "deadline": "ISO 8601 datetime string" | null,
  "show_answers_timing": "immediate" | "after_deadline" (default: "immediate"),
  "num_options": integer (0-10, default: 4),
  "num_correct_answers": integer (0-10, default: 1),
  "mcq_type_config": {
    "num_single_answer_mcq": integer (0-50) | null,
    "num_multiple_answer_mcq": integer (0-30) | null,
    "num_matching": integer (0-20) | null,
    "num_completion": integer (0-20) | null,
    "num_sentence_completion": integer (0-20) | null,
    "num_short_answer": integer (0-20) | null,
    "distribution_mode": "auto" | "manual" (default: "auto")
  } | null
}
```

#### Validation Rules for test_type

**For test_type = "mixed":**
- `num_mcq_questions` and `num_essay_questions` are REQUIRED
- Total (num_mcq_questions + num_essay_questions) cannot exceed 100
- `num_questions` is auto-computed from the sum

**For test_type = "mcq" or "essay":**
- `num_questions` is REQUIRED
- Individual counts are auto-computed based on type

#### Response Schema

**Success Response (200 OK):**
```
{
  "success": true,
  "test_id": "string (MongoDB ObjectId)",
  "status": "pending",
  "title": "string",
  "description": "string | null",
  "topic": "string",
  "test_category": "string",
  "num_questions": integer,
  "time_limit_minutes": integer,
  "created_at": "ISO 8601 datetime string",
  "message": "Test created successfully. AI is generating questions from general knowledge..."
}
```

**Error Responses:**

- **400 Bad Request** - Invalid validation (test_type mismatch, question count validation, mcq_type_config validation)
- **401 Unauthorized** - Missing or invalid authentication token
- **500 Internal Server Error** - Server error during test creation

---

## Feature 2: Merge Tests

### Overview

Combine questions from 2-10 existing tests into one new test. All question metadata is preserved, and the new test owner is the current user.

---

### 2.1 Preview Questions Endpoint

Before merging tests, use this endpoint to preview questions from source tests for custom selection.

**POST /api/v1/tests/preview-questions**

#### Request Body Schema

```json
{
  "test_ids": ["string (ObjectId)", ...] (1-10 unique test IDs)
}
```

#### Response Schema

**Success Response (200 OK):**
```json
{
  "success": true,
  "tests": {
    "test_id": {
      "test_id": "string",
      "title": "string",
      "test_type": "string",
      "num_questions": integer,
      "questions": [
        {
          "index": integer (0-based),
          "question_type": "mcq" | "essay" | "listening" | "matching" | "completion" | "sentence_completion" | "short_answer",
          "question_text": "string (truncated to 200 chars for preview)",
          "has_media": boolean,
          "instruction": "string | null",
          "num_options": integer (for MCQ),
          "num_correct_answers": integer (for MCQ/matching),
          "max_score": integer (for essay),
          "left_items_count": integer (for matching),
          "right_options_count": integer (for matching),
          "num_blanks": integer (for completion/sentence_completion),
          "max_words": integer (for short_answer)
        }
      ]
    }
  },
  "total_tests": integer
}
```

**Note:** correct_answer_keys are NOT included in preview for security.

#### Error Responses

- **400 Bad Request:** Invalid test_id format, empty test_ids array, or too many test IDs
- **403 Forbidden:** Access denied to one or more tests
- **404 Not Found:** One or more test IDs not found
- **401 Unauthorized:** Missing/invalid authentication

#### Use Case

1. User selects multiple tests to merge
2. Frontend calls preview endpoint to get question lists
3. Frontend displays questions with type, text preview, and metadata
4. User selects specific questions by index for each test
5. Frontend constructs custom_selection object
6. Frontend calls merge endpoint with custom selection

---

### 2.2 Merge Tests Endpoint

**POST /api/v1/tests/merge**

#### Request Body Schema

```
{
  "source_test_ids": ["string (ObjectId)", ...] (2-10 unique test IDs),
  "title": "string (5-200 chars)",
  "description": "string (optional, max 1000 chars)",
  "creator_name": "string (optional, 2-100 chars)",
  "test_type": "mcq" | "essay" | "mixed" | "listening" | "auto",
  "test_category": "academic" | "diagnostic" (default: "academic"),
  "time_limit_minutes": integer (1-300, default: 30),
  "max_retries": integer (1-10, default: 3),
  "passing_score": integer (0-100, default: 50),
  "mcq_points": integer (0-1000) | null [for mixed type],
  "essay_points": integer (0-1000) | null [for mixed type],
  "essay_grading_criteria": "string (max 2000 chars)" | null,
  "question_selection": "all" | "random" | "custom" (default: "all"),
  "max_questions": integer (1-100) | null [required if question_selection="random"],
  "custom_selection": {
    "test_id": {
      "question_indices": [integer, ...],
      "part_title": "string (optional)",
      "part_description": "string (optional)"
    }
  } | null [required if question_selection="custom"],
  "deadline": "ISO 8601 datetime string" | null,
  "show_answers_timing": "immediate" | "after_deadline" (default: "immediate")
}
```

#### Field Descriptions

**source_test_ids:**
- Array of test IDs to merge
- Must contain 2-10 unique test IDs
- All IDs must be valid MongoDB ObjectId format
- User must have access to all tests (owner or shared access)

**test_type:**
- `mcq`: MCQ only
- `essay`: Essay only
- `mixed`: Both MCQ and essay
- `listening`: Listening test
- `auto`: Auto-infer from question composition

**question_selection:**
- `all`: Include all questions from all source tests (default)
- `random`: Randomly select up to max_questions
- `custom`: Select specific questions by index (requires custom_selection)

**max_questions:**
- Required when question_selection = "random"
- Cannot be set when question_selection = "all" or "custom"

**custom_selection:**
- Required when question_selection = "custom"
- Cannot be set when question_selection = "all" or "random"
- Structure: Dict mapping test_id to part configuration
- Each part config contains:
  - `question_indices`: Array of question indices (0-based) to include
  - `part_title`: Optional title for this part (e.g., "Reading Comprehension")
  - `part_description`: Optional description for this part

**essay_grading_criteria:**
- Custom AI grading criteria for essay questions
- If not provided, uses default criteria

#### Validation Rules

1. **source_test_ids must be unique** (no duplicate test IDs)
2. **question_selection validation:**
   - If "random", max_questions is required
   - If "all", max_questions should not be set
   - If "custom", custom_selection is required
3. **custom_selection validation:**
   - Can only be set when question_selection = "custom"
   - Must be a dict mapping test_id to part config
   - Each part config must have "question_indices" array
   - All indices must be non-negative integers
   - At least one question must be selected per test
   - Indices must be within valid range (0 to num_questions-1)
4. **Access control:**
   - User must be owner OR have shared access to all source tests
   - Returns 403 if any test is inaccessible

#### Response Schema

**Success Response (200 OK):**
```
{
  "success": true,
  "test_id": "string (new merged test MongoDB ObjectId)",
  "title": "string",
  "test_type": "string (inferred or specified)",
  "num_questions": integer (total questions in merged test),
  "num_mcq_questions": integer,
  "num_essay_questions": integer,
  "max_points": integer (computed from all questions),
  "source_tests": integer (number of source tests merged),
  "created_at": "ISO 8601 datetime string",
  "message": "Successfully merged N tests into 1 new test with M questions",
  "parts": [
    {
      "part_number": integer,
      "part_title": "string | null",
      "part_description": "string | null",
      "source_test_id": "string",
      "source_test_title": "string",
      "question_start_index": integer,
      "question_end_index": integer,
      "num_questions": integer
    }
  ] (only present if question_selection="custom")
}
```

**Error Responses:**

- **400 Bad Request:**
  - Invalid test_id format in source_test_ids
  - Duplicate test IDs
  - Invalid question_selection configuration
  - No questions found in source tests
  - Validation errors (question_selection mismatch with max_questions)

- **403 Forbidden:**
  - Access denied to one or more source tests
  - Returns specific test_id that caused the error

- **404 Not Found:**
  - One or more source test IDs not found
  - Returns specific test_id that was not found

- **401 Unauthorized:**
  - Missing or invalid authentication token

- **500 Internal Server Error:**
  - Database error
  - Unexpected server error

#### Merged Test Metadata

**Fields stored in merged test document:**
```
{
  "title": "string (user-specified)",
  "description": "string | null",
  "creator_name": "string | null",
  "test_category": "string",
  "test_type": "string (inferred or specified)",
  "test_language": "string (from first source test)",
  "source_type": "merged",
  "source_test_ids": ["array of source test IDs"],
  "creator_id": "string (current user UID)",
  "time_limit_minutes": integer,
  "num_questions": integer,
  "num_mcq_questions": integer,
  "num_essay_questions": integer,
  "mcq_points": integer | null,
  "essay_points": integer | null,
  "max_points": integer (computed),
  "max_retries": integer,
  "passing_score": integer,
  "deadline": datetime | null,
  "show_answers_timing": "string",
  "essay_grading_criteria": "string | null",
  "creation_type": "merged",
  "question_selection": "string",
  "status": "ready" (immediately ready, no AI generation),
  "questions": [array of merged questions],
  "parts": [array of part metadata] (only if question_selection="custom"),
  "is_active": true,
  "created_at": datetime,
  "updated_at": datetime
}
```

#### Question Metadata Preserved

All questions retain their original structure:
- `question_type`: mcq, essay, listening, matching, completion, etc.
- `question_text`
- `instruction` (optional)
- `options` (for MCQ)
- `correct_answer_keys` (for MCQ)
- `explanation`
- `max_score` / `max_points`
- `grading_rubric` (for essay)
- `audio_url`, `transcript` (for listening)
- `media_type`, `media_url`, `media_description`
- IELTS-specific fields (left_items, right_options, correct_matches, etc.)

#### Scoring Computation

**max_points calculation:**
- Essay questions: Sum of `max_score` from original questions
- MCQ/Listening questions: 1 point each
- Total: Sum of all question points

**Example:**
- 5 MCQ questions = 5 points
- 2 Essay questions (max_score: 10, 15) = 25 points
- **Total max_points = 30**

#### Auto-infer test_type Logic

When test_type = "auto":
1. If any listening questions → `listening`
2. If MCQ + Essay questions → `mixed`
3. If only MCQ questions → `mcq`
4. If only Essay questions → `essay`
5. Default → `mcq`

---

## Use Cases

### MCQ Type Distribution

**Use Case 1: IELTS-style reading test**
```
Request:
- test_type: "mcq"
- num_questions: 10
- mcq_type_config: {
    "distribution_mode": "manual",
    "num_matching": 3,
    "num_completion": 4,
    "num_short_answer": 3
  }

Result: AI generates 3 matching + 4 completion + 3 short answer questions
```

**Use Case 2: Mixed question types (auto mode)**
```
Request:
- test_type: "mcq"
- num_questions: 15
- mcq_type_config: {
    "distribution_mode": "auto"
  }

Result: AI decides best distribution based on document content
```

**Use Case 3: Traditional MCQ with multiple-answer questions**
```
Request:
- test_type: "mcq"
- num_questions: 10
- mcq_type_config: {
    "distribution_mode": "manual",
    "num_single_answer_mcq": 7,
    "num_multiple_answer_mcq": 3
  }

Result: 7 questions with 1 correct answer + 3 questions with 2+ correct answers
```

### Merge Tests

**Use Case 1: Combine chapter tests into final exam**
```
Request:
- source_test_ids: ["chapter1_test_id", "chapter2_test_id", "chapter3_test_id"]
- question_selection: "all"
- test_type: "auto"

Result: All questions from 3 chapter tests merged into 1 comprehensive exam
```

**Use Case 2: Create practice test with random selection**
```
Request:
- source_test_ids: ["test1_id", "test2_id", "test3_id"]
- question_selection: "random"
- max_questions: 20
- test_type: "mcq"

Result: Randomly select 20 MCQ questions from 3 source tests
```

**Use Case 3: Merge listening tests**
```
Request:
- source_test_ids: ["listening_test1_id", "listening_test2_id"]
- question_selection: "all"
- test_type: "listening"

Result: All listening questions merged, audio URLs preserved
```

**Use Case 4: Custom selection for multi-part test (English General Test)**
```json
Step 1: Preview questions
POST /api/v1/tests/preview-questions
{
  "test_ids": ["reading_test_id", "listening_test_id", "essay_test_id"]
}

Step 2: User selects specific questions from UI

Step 3: Merge with custom selection
POST /api/v1/tests/merge
{
  "source_test_ids": ["reading_test_id", "listening_test_id", "essay_test_id"],
  "title": "English General Test - Level B2",
  "question_selection": "custom",
  "custom_selection": {
    "reading_test_id": {
      "question_indices": [0, 2, 4, 5, 7],
      "part_title": "Part 1: Reading Comprehension",
      "part_description": "Read the passage and answer questions"
    },
    "listening_test_id": {
      "question_indices": [1, 3, 4],
      "part_title": "Part 2: Listening",
      "part_description": "Listen to the audio and answer questions"
    },
    "essay_test_id": {
      "question_indices": [0],
      "part_title": "Part 3: Writing",
      "part_description": "Write an essay (200-250 words)"
    }
  },
  "test_type": "mixed",
  "time_limit_minutes": 90
}

Result: Multi-part test with 9 questions:
- Part 1: 5 reading questions
- Part 2: 3 listening questions
- Part 3: 1 essay question
- parts array stored in test document with metadata
```

**Use Case 5: Select best questions from multiple tests**
```json
POST /api/v1/tests/merge
{
  "source_test_ids": ["test_v1_id", "test_v2_id"],
  "title": "Best Questions - Final Version",
  "question_selection": "custom",
  "custom_selection": {
    "test_v1_id": {
      "question_indices": [0, 1, 5, 8, 9],
      "part_title": "Set A"
    },
    "test_v2_id": {
      "question_indices": [2, 3, 7, 10],
      "part_title": "Set B"
    }
  }
}

Result: Cherry-picked 9 questions from 2 test versions
```

---

## Important Notes

### MCQ Type Distribution

1. **Default behavior:** If `mcq_type_config` is not provided, AI generates standard single-answer MCQ questions
2. **Manual mode requirement:** At least one question type must have a non-zero count
3. **Total limit:** Sum of all question type counts cannot exceed 100
4. **Works with mixed tests:** For test_type="mixed", mcq_type_config only applies to the MCQ portion

### Merge Tests

1. **Ownership:** New test owner is the current user (not original test owners)
2. **Source tests unchanged:** Original tests remain intact
3. **Immediate availability:** Merged tests have status="ready" (no AI generation needed)
4. **Access control:** User must have access to ALL source tests
5. **Question order:** Questions maintain order from source tests (first test's questions first, then second test, etc.)
6. **Random selection:** When using "random" mode, question types are preserved but selection is random
7. **Language:** Merged test inherits language from first source test
8. **Custom selection:** Enables precise control over which questions to include from each test
9. **Parts structure:** Custom selection creates multi-part tests with metadata for each part
10. **Preview endpoint:** Use preview endpoint first to get question lists before custom selection
11. **Question indices:** Use 0-based indices (first question = index 0)
12. **Parts metadata:** Each part includes source test info, title, description, and question ranges

---

## Polling for Test Status

Both endpoints return immediately with `status: "pending"`. Frontend should poll the status endpoint:

**GET /api/v1/tests/{test_id}/status**

**Response:**
```
{
  "status": "pending" | "generating" | "ready" | "failed",
  "progress_percent": integer (0-100),
  "progress_message": "string" | null,
  "error_message": "string" | null (only if status="failed"),
  "test_id": "string",
  "title": "string",
  "num_questions": integer,
  "created_at": "ISO 8601 datetime string",
  "generated_at": "ISO 8601 datetime string" | null
}
```

**Polling Strategy:**
- Poll every 2-3 seconds
- Stop when status is "ready" or "failed"
- Show progress_percent to user
- If status="failed", display error_message

---

## Authentication

All endpoints require Firebase authentication token in header:

```
Authorization: Bearer <firebase_id_token>
```

**401 Unauthorized** returned if:
- Token is missing
- Token is invalid
- Token is expired

---

## Limitations

### MCQ Type Distribution
- Maximum 100 total questions across all types
- Each individual type has specific limits (see schema)
- Manual mode requires at least one type specified

### Merge Tests
- Minimum 2 tests, maximum 10 tests
- Must have access to all source tests
- Cannot merge tests with no questions
- Random selection limited to 100 questions

---

## Error Handling

### Common Error Response Format

```
{
  "detail": "Error message describing what went wrong"
}
```

### Validation Error Response Format (422 Unprocessable Entity)

```
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Error message",
      "type": "error_type"
    }
  ]
}
```

**Example validation errors:**
- Missing required field
- Invalid data type
- Value out of range
- Invalid enum value
- Custom validation failure (e.g., mcq_type_config validation)

---

## Version Information

- **API Version:** v1
- **Base URL:** `/api/v1/tests`
- **Last Updated:** December 11, 2025
- **Features Added:**
  - MCQ Type Distribution (6 question types)
  - Merge Tests (2-10 tests)
