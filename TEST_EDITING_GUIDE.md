# Test Editing API Guide

Complete documentation for editing tests, managing attachments, and updating questions.

## Table of Contents

1. [Overview](#overview)
2. [Update Questions](#update-questions)
3. [Manage Test Attachments](#manage-test-attachments)
4. [Question Media Files](#question-media-files)
5. [Question Type Specifications](#question-type-specifications)
6. [Full Test Edit](#full-test-edit)
7. [Common Use Cases](#common-use-cases)

---

## Overview

**Access Control**: Only test **creator** (owner) can edit tests.

**Key Concepts**:
- **Test Attachments**: Files attached to entire test (e.g., reading passages, reference materials)
- **Question Media**: Images/audio attached to individual questions
- **Validation**: Smart validation skips checking if questions unchanged (optimization for attachment-only updates)

---

## Update Questions

### Endpoint
```
PUT /api/v1/tests/{test_id}/questions
```

### Purpose
Update all questions in a test. Used when:
- Editing question text or answers
- Adding/removing questions
- Changing question types
- Modifying question media

### Request Body
```json
{
  "questions": [
    {
      "question_id": "507f1f77bcf86cd799439011",
      "question_number": 1,
      "question_type": "mcq",
      "question_text": "What is the capital of France?",
      "points": 1,
      "options": [
        {"key": "A", "text": "London"},
        {"key": "B", "text": "Paris"},
        {"key": "C", "text": "Berlin"},
        {"key": "D", "text": "Madrid"}
      ],
      "correct_answers": ["B"],
      "explanation": "Paris is the capital and largest city of France.",
      "media_type": "image",
      "media_url": "https://storage.com/question1.jpg"
    }
  ]
}
```

### Smart Validation
- **If questions unchanged**: Skips validation, only updates timestamp
- **If questions changed**: Full validation runs
- **Benefit**: Can update attachments without triggering question validation errors

### Response
```json
{
  "success": true,
  "test_id": "693eaa44ab5c49b582ba10dc",
  "questions_updated": 20,
  "message": "No changes to questions",  // If unchanged
  "updated_at": "2025-12-14T22:03:38.366Z"
}
```

### Error Codes
- `404`: Test not found
- `403`: Not the test creator
- `400`: Validation errors (see [Question Type Specifications](#question-type-specifications))

---

## Manage Test Attachments

Test attachments are files (PDFs, documents) attached to the **entire test**, not individual questions.

### Use Cases
- Reading comprehension passages
- Reference materials
- Background documents
- Instructions sheets

### 1. Get All Attachments

```
GET /api/v1/tests/{test_id}/attachments
```

**Response:**
```json
{
  "success": true,
  "test_id": "693eaa44ab5c49b582ba10dc",
  "test_title": "IELTS Reading Practice",
  "creator_id": "user123",
  "is_owner": true,
  "attachments": [
    {
      "attachment_id": "a1b2c3d4e5f6",
      "title": "Reading Passage 1",
      "description": "Article about climate change",
      "file_url": "https://r2.storage.com/files/passage1.pdf",
      "file_size_mb": 2.5,
      "uploaded_at": "2025-12-14T20:00:00.000Z"
    }
  ],
  "total_attachments": 1,
  "total_storage_mb": 2.5
}
```

**Access:**
- Owner: Full access
- Others with test access: Read-only

---

### 2. Add Attachment

```
POST /api/v1/tests/{test_id}/attachments
```

**Request Body:**
```json
{
  "title": "Reading Passage 1",
  "description": "Short story for comprehension questions",
  "file_url": "https://r2.storage.com/files/passage1.pdf",
  "file_size_mb": 2.5
}
```

**Response:**
```json
{
  "success": true,
  "test_id": "693eaa44ab5c49b582ba10dc",
  "attachment": {
    "attachment_id": "a1b2c3d4e5f6",
    "title": "Reading Passage 1",
    "description": "Short story for comprehension questions",
    "file_url": "https://r2.storage.com/files/passage1.pdf",
    "file_size_mb": 2.5,
    "uploaded_at": "2025-12-14T22:00:00.000Z"
  },
  "message": "Attachment added successfully"
}
```

**Important:**
- File size counts toward owner's storage quota
- System automatically updates user's storage usage

**Access:** Owner only

---

### 3. Update Attachment

```
PUT /api/v1/tests/{test_id}/attachments/{attachment_id}
```

**Request Body:**
```json
{
  "title": "Updated Reading Passage 1",
  "description": "Updated description",
  "file_url": "https://r2.storage.com/files/updated_passage1.pdf",
  "file_size_mb": 3.0
}
```

**Response:**
```json
{
  "success": true,
  "test_id": "693eaa44ab5c49b582ba10dc",
  "attachment_id": "a1b2c3d4e5f6",
  "message": "Attachment updated successfully"
}
```

**Access:** Owner only

---

### 4. Delete Attachment

```
DELETE /api/v1/tests/{test_id}/attachments/{attachment_id}
```

**Response:**
```json
{
  "success": true,
  "test_id": "693eaa44ab5c49b582ba10dc",
  "attachment_id": "a1b2c3d4e5f6",
  "message": "Attachment deleted successfully"
}
```

**Important:**
- System automatically decreases user's storage usage by file size
- Attachment removed from test's attachments array

**Access:** Owner only

---

## Question Media Files

Individual questions can have media (images or audio) attached directly to them.

### Usage
Set `media_type` and `media_url` in question object:

```json
{
  "question_id": "q1",
  "question_type": "mcq",
  "question_text": "Identify the animal in the image:",
  "media_type": "image",
  "media_url": "https://storage.com/images/elephant.jpg",
  "options": [
    {"key": "A", "text": "Elephant"},
    {"key": "B", "text": "Giraffe"}
  ],
  "correct_answers": ["A"]
}
```

### Media Types
- `image`: Display image with question
- `audio`: Audio player for listening questions

### Validation
- `media_type` must be `"image"` or `"audio"`
- `media_url` required when `media_type` is set

### Where to Store
- Upload files to Cloudflare R2 or CDN
- Store URL in question's `media_url` field
- File size does NOT count toward test attachments quota (counted per question if needed)

---

## Question Type Specifications

Complete validation rules and data formats for all 8 question types.

### 1. MCQ (Multiple Choice Question)

**Type:** `"mcq"`

**Required Fields:**
- `question_text`: Question text
- `options`: Array of answer options (min 2)
  - Each option: `{key: "A", text: "Answer text"}`
- `correct_answers`: Array of correct option keys (unified field)

**Optional Fields:**
- `correct_answer_key`: Legacy single answer (for backward compatibility)
- `correct_answer_keys`: Legacy array (for backward compatibility)
- `explanation`: Explanation text
- `media_type`, `media_url`: Question media

**Example:**
```json
{
  "question_id": "q1",
  "question_number": 1,
  "question_type": "mcq",
  "question_text": "What is 2 + 2?",
  "points": 1,
  "options": [
    {"key": "A", "text": "3"},
    {"key": "B", "text": "4"},
    {"key": "C", "text": "5"},
    {"key": "D", "text": "6"}
  ],
  "correct_answers": ["B"],
  "explanation": "2 + 2 equals 4"
}
```

**Multiple Correct Answers:**
```json
{
  "question_type": "mcq",
  "question_text": "Select all prime numbers:",
  "options": [
    {"key": "A", "text": "2"},
    {"key": "B", "text": "3"},
    {"key": "C", "text": "4"},
    {"key": "D", "text": "5"}
  ],
  "correct_answers": ["A", "B", "D"]
}
```

**Validation:**
- Min 2 options
- All `correct_answers` must exist in `options` keys
- Diagnostic tests: `correct_answers` optional

---

### 2. Essay

**Type:** `"essay"`

**Required Fields:**
- `question_text`: Essay prompt

**Optional Fields:**
- `word_limit_min`: Minimum word count
- `word_limit_max`: Maximum word count
- `rubric`: Grading rubric text

**Example:**
```json
{
  "question_id": "q2",
  "question_type": "essay",
  "question_text": "Discuss the impact of social media on modern communication.",
  "points": 10,
  "word_limit_min": 250,
  "word_limit_max": 500,
  "rubric": "Content (40%), Grammar (30%), Vocabulary (30%)"
}
```

**Validation:**
- Cannot have `options`, `correct_answer_key`, or `correct_answer_keys`
- Requires manual grading (cannot be auto-scored)

---

### 3. Matching

**Type:** `"matching"`

**Required Fields:**
- `left_items`: Array of items to match (min 2)
  - Each: `{key: "1", text: "Item text"}`
- `right_options`: Array of match options (min 2)
  - Each: `{key: "A", text: "Option text"}`
- `correct_answers`: Array of correct matches (unified field)
  - Each: `{left_key: "1", right_key: "A"}`

**Optional Legacy Field:**
- `correct_matches`: Legacy format `{"1": "A", "2": "B"}`

**Example:**
```json
{
  "question_id": "q3",
  "question_type": "matching",
  "question_text": "Match each country with its capital:",
  "points": 3,
  "left_items": [
    {"key": "1", "text": "France"},
    {"key": "2", "text": "Germany"},
    {"key": "3", "text": "Italy"}
  ],
  "right_options": [
    {"key": "A", "text": "Berlin"},
    {"key": "B", "text": "Paris"},
    {"key": "C", "text": "Rome"}
  ],
  "correct_answers": [
    {"left_key": "1", "right_key": "B"},
    {"left_key": "2", "right_key": "A"},
    {"left_key": "3", "right_key": "C"}
  ]
}
```

**Scoring:**
- Proportional: Correct 2/3 = 2 points (if max_points = 3)
- Empty answer = 0 points

**Validation:**
- Min 2 left_items
- Min 2 right_options
- Must have `correct_answers` OR `correct_matches` (legacy)

---

### 4. Map Labeling

**Type:** `"map_labeling"`

⚠️ **MANUAL CREATION ONLY** - Not generated by AI (Gemini). Must be created/edited manually.

**Required Fields:**
- `diagram_url`: URL to diagram/map image
- `label_positions`: Array of positions to label (min 1)
  - Each: `{key: "1", x: 100, y: 200, description: "Position 1"}`
- `options`: Array of label options
  - Each: `{key: "A", text: "Label text"}`
- `correct_answers`: Correct labels for each position (unified field)
  - Format: `[{label_key: "1", option_key: "A"}, ...]`

**Optional Legacy Field:**
- `correct_labels`: Legacy format `{"1": "A", "2": "B"}`

**Example:**
```json
{
  "question_id": "q4",
  "question_type": "map_labeling",
  "question_text": "Label the parts of the cell:",
  "points": 5,
  "diagram_url": "https://storage.com/cell-diagram.jpg",
  "diagram_description": "Diagram of a eukaryotic cell",
  "label_positions": [
    {"key": "1", "x": 150, "y": 100, "description": "Organelle A"},
    {"key": "2", "x": 250, "y": 150, "description": "Organelle B"}
  ],
  "options": [
    {"key": "A", "text": "Nucleus"},
    {"key": "B", "text": "Mitochondria"},
    {"key": "C", "text": "Ribosome"}
  ],
  "correct_answers": [
    {"label_key": "1", "option_key": "A"},
    {"label_key": "2", "option_key": "B"}
  ]
}
```

**Scoring:**
- Proportional: Correct 1/2 = 2.5 points (if max_points = 5)
- Empty answer = 0 points

**Validation:**
- `diagram_url` required (NOT `map_url`)
- `label_positions` required (NOT `positions`)
- Min 1 label position
- Must have `correct_answers` OR `correct_labels` (legacy)

---

### 5. Completion (Form/Note/Table)

**Type:** `"completion"`

**Required Fields:**
- `template`: HTML template with `[blank_X]` placeholders
- `blanks`: Array of blank definitions (min 1)
  - Each: `{key: "1", label: "Blank 1"}`
- `correct_answers`: Acceptable answers per blank
  - Format: `[{blank_key: "1", answers: ["ans1", "ans2"]}, ...]`
  - OR: `{"1": ["ans1", "ans2"], "2": ["ans3"]}`

**Optional:**
- `case_sensitive`: Boolean (default: false)

**Example:**
```json
{
  "question_id": "q5",
  "question_type": "completion",
  "question_text": "Complete the biographical information:",
  "points": 3,
  "template": "Name: [blank_1]<br>Age: [blank_2]<br>Occupation: [blank_3]",
  "blanks": [
    {"key": "1", "label": "Name"},
    {"key": "2", "label": "Age"},
    {"key": "3", "label": "Occupation"}
  ],
  "correct_answers": [
    {"blank_key": "1", "answers": ["John Smith", "John"]},
    {"blank_key": "2", "answers": ["25", "twenty-five"]},
    {"blank_key": "3", "answers": ["Engineer", "Software Engineer"]}
  ],
  "case_sensitive": false
}
```

**Scoring:**
- Proportional: Correct 2/3 blanks = 2 points
- Case-insensitive matching by default
- Multiple acceptable answers per blank

**Validation:**
- `template` required
- Min 1 blank
- `correct_answers` required

---

### 6. Sentence Completion

**Type:** `"sentence_completion"`

**Required Fields:**
- `sentences`: Array of sentences to complete (min 1)
  - Each sentence:
    - `key`: Sentence identifier
    - `template`: Sentence with `[blank]` placeholder
    - `correct_answers`: Array of acceptable answers

**Optional:**
- `case_sensitive`: Boolean

**Example:**
```json
{
  "question_id": "q6",
  "question_type": "sentence_completion",
  "question_text": "Complete each sentence:",
  "points": 2,
  "sentences": [
    {
      "key": "1",
      "template": "The meeting starts at [blank].",
      "correct_answers": ["8 AM", "8:00", "eight o'clock"]
    },
    {
      "key": "2",
      "template": "She borrowed [blank] books from the library.",
      "correct_answers": ["5", "five"]
    }
  ],
  "case_sensitive": false
}
```

**Scoring:**
- Proportional: Correct 1/2 sentences = 1 point
- Flexible matching with multiple acceptable answers

**Validation:**
- Min 1 sentence
- Each sentence needs `template` and `correct_answers`

---

### 7. Short Answer

**Type:** `"short_answer"`

**Required Fields:**
- `questions`: Array of sub-questions (min 1)
  - Each:
    - `key`: Question identifier
    - `text`: Question text
    - `correct_answers`: Array of acceptable answers

**Optional:**
- `case_sensitive`: Boolean

**Example:**
```json
{
  "question_id": "q7",
  "question_type": "short_answer",
  "question_text": "Answer the following questions about the reading passage:",
  "points": 3,
  "questions": [
    {
      "key": "1",
      "text": "What is the author's profession?",
      "correct_answers": ["Software Engineer", "Engineer", "Developer"]
    },
    {
      "key": "2",
      "text": "How many years of experience does the author have?",
      "correct_answers": ["5", "five", "5 years"]
    },
    {
      "key": "3",
      "text": "What programming language is mentioned?",
      "correct_answers": ["Python", "python"]
    }
  ],
  "case_sensitive": false
}
```

**Scoring:**
- Proportional: Correct 2/3 = 2 points
- Flexible text matching

**Validation:**
- Min 1 question
- Each question needs `text` and `correct_answers`

---

### 8. Listening

**Type:** `"listening"`

**Required Fields:**
- `audio_sections`: Array of audio files and timestamps

**Example:**
```json
{
  "question_id": "q8",
  "question_type": "listening",
  "question_text": "Listen to the audio and answer:",
  "points": 5,
  "audio_sections": [
    {
      "section_id": "s1",
      "audio_url": "https://storage.com/audio1.mp3",
      "duration_seconds": 120
    }
  ]
}
```

**Validation:**
- `audio_sections` required

---

## Full Test Edit

### Endpoint
```
PUT /api/v1/tests/{test_id}/edit
```

### Purpose
Comprehensive endpoint to update **all test aspects** in one call:
- Basic config (title, description, is_active)
- Test settings (max_retries, time_limit, passing_score, deadline)
- Questions (full array)
- Marketplace config (if published)

### Request Body (All Fields Optional)
```json
{
  "title": "Updated Test Title",
  "description": "Updated description",
  "is_active": true,
  "creator_name": "John Doe",
  "max_retries": 3,
  "time_limit_minutes": 60,
  "passing_score": 70,
  "deadline": "2025-12-31T23:59:59Z",
  "show_answers_timing": "after_each_submission",
  "questions": [...],
  "marketplace_title": "IELTS Reading Practice - Advanced",
  "marketplace_description": "Comprehensive IELTS reading test...",
  "short_description": "Advanced IELTS practice with 40 questions",
  "price_points": 100,
  "category": "IELTS",
  "tags": "ielts,reading,advanced",
  "difficulty_level": "advanced",
  "is_public": true,
  "estimated_time_minutes": 60
}
```

### Response
```json
{
  "success": true,
  "test_id": "693eaa44ab5c49b582ba10dc",
  "updated_fields": ["title", "description", "questions"],
  "message": "Test updated successfully"
}
```

**Access:** Owner only

---

## Common Use Cases

### Use Case 1: Edit Question Text Only

**Goal:** Fix typo in question 5

**Steps:**
1. GET `/api/v1/tests/{test_id}` - Get current questions
2. Modify question 5's `question_text`
3. PUT `/api/v1/tests/{test_id}/questions` - Send full questions array

**Note:** Even though you only changed 1 question, send the entire `questions` array.

---

### Use Case 2: Add Reading Passage (Attachment)

**Goal:** Add a PDF reading passage to test

**Steps:**
1. Upload PDF to storage (Cloudflare R2)
2. POST `/api/v1/tests/{test_id}/attachments`:
   ```json
   {
     "title": "Reading Passage 1",
     "description": "Climate change article",
     "file_url": "https://r2.storage.com/passage1.pdf",
     "file_size_mb": 2.5
   }
   ```

**Result:**
- Attachment added to test
- User's storage quota increased by 2.5MB

---

### Use Case 3: Update Question with Image

**Goal:** Add an image to question 3

**Steps:**
1. Upload image to storage
2. GET `/api/v1/tests/{test_id}` - Get questions
3. Update question 3:
   ```json
   {
     "question_id": "q3",
     "media_type": "image",
     "media_url": "https://storage.com/diagram.jpg"
   }
   ```
4. PUT `/api/v1/tests/{test_id}/questions` - Update

---

### Use Case 4: Fix Wrong Answer

**Goal:** Change correct answer for question 10 from "B" to "C"

**Steps:**
1. GET `/api/v1/tests/{test_id}` - Get questions
2. Find question 10
3. Update `correct_answers: ["C"]`
4. PUT `/api/v1/tests/{test_id}/questions` - Update

**Important:** System uses unified `correct_answers` field. Legacy fields (`correct_answer_key`, `correct_answer_keys`) automatically updated for backward compatibility.

---

### Use Case 5: Add Attachment Without Changing Questions

**Goal:** Add reference PDF, don't touch questions

**Problem:** Old behavior would validate ALL questions even if unchanged → Errors on deprecated fields

**Solution (NEW):**
1. POST `/api/v1/tests/{test_id}/attachments` - Add attachment
2. PUT `/api/v1/tests/{test_id}/questions` - Send unchanged questions
3. System detects no changes → Skips validation ✅

**Benefit:** Can add attachments without triggering validation errors on old tests.

---

## Field Migration Guide

### Unified Fields (NEW)
Tests generated with Gemini 2.0+ use unified fields:
- `correct_answers`: Unified field for all question types
  - MCQ: Array of option keys `["A", "B"]`
  - Matching: Array of objects `[{left_key: "1", right_key: "A"}]`
  - Completion: Array of objects `[{blank_key: "1", answers: ["ans1"]}]`

### Legacy Fields (OLD)
Old tests use deprecated fields:
- `correct_answer_key`: Single MCQ answer
- `correct_answer_keys`: Multiple MCQ answers
- `correct_matches`: Matching answers as dict `{"1": "A"}`

### Backward Compatibility
✅ System accepts BOTH unified and legacy fields
✅ When updating, system normalizes to unified format
✅ Legacy fields kept for old test compatibility

**Recommendation:** Use `correct_answers` for all new tests.

---

## Validation Summary

| Question Type | Required Fields | Optional | Min Items | AI Generated? |
|--------------|----------------|----------|-----------|---------------|
| MCQ | `question_text`, `options`, `correct_answers` | `explanation`, `media_*` | 2 options | ✅ Yes |
| Essay | `question_text` | `word_limit_*`, `rubric` | - | ✅ Yes |
| Matching | `left_items`, `right_options`, `correct_answers` | - | 2 left, 2 right | ✅ Yes |
| Map Labeling | `diagram_url`, `label_positions`, `options`, `correct_answers` | `diagram_description` | 1 position | ❌ Manual only |
| Completion | `template`, `blanks`, `correct_answers` | `case_sensitive` | 1 blank | ✅ Yes |
| Sentence Completion | `sentences` (with `template`, `correct_answers`) | `case_sensitive` | 1 sentence | ✅ Yes |
| Short Answer | `questions` (with `text`, `correct_answers`) | `case_sensitive` | 1 question | ✅ Yes |
| Listening | `audio_sections` | - | - | ❌ Manual only |

---

## Error Handling

### Common Errors

**400 Bad Request:**
- Missing required fields
- Invalid question type
- Correct answer not in options
- Wrong media_type value

**403 Forbidden:**
- Not the test creator

**404 Not Found:**
- Test doesn't exist
- Attachment not found

### Example Error Response
```json
{
  "detail": "Question 5: MCQ requires at least 2 options"
}
```

---

## Best Practices

1. **Always send full questions array** when updating questions (not partial)
2. **Upload files first** (images/PDFs) before referencing in questions/attachments
3. **Validate client-side** before sending to reduce errors
4. **Use unified fields** (`correct_answers`) for new questions
5. **Test after updates** - verify questions display correctly
6. **Monitor storage quota** when adding attachments
7. **Keep backup** of questions before bulk updates

---

## Related Documentation

- [QUESTION_TYPES_JSON_SCHEMA.md](./QUESTION_TYPES_JSON_SCHEMA.md) - Complete JSON formats
- [SYSTEM_REFERENCE.md](./SYSTEM_REFERENCE.md) - Infrastructure and deployment
- API Docs: `/docs` endpoint (Swagger UI)

---

**Last Updated:** December 14, 2025
**Version:** 1.0
