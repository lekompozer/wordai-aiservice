# Slide Edit by AI - API Technical Specifications

## Endpoint

```
POST /api/slides/ai-edit
```

**Authentication**: Required (Firebase Bearer token)

**AI Provider**: Google Gemini 3 Pro Preview (low creativity, temperature=0.3)

**Cost**: 2 points per slide (Mode 1), 5 points per chunk for Mode 2/3 (max 12 slides/chunk)

---

## Overview

Edit slide content based on user instruction. AI focuses strictly on user query with minimal changes, preserving layout and structure.

**Use Cases**:
- "Make it shorter" → Remove verbose parts, keep key points
- "Add more details" → Expand with relevant specifics
- "Simplify for beginners" → Replace jargon with simple terms
- "Add statistics" → Insert relevant numbers/data

---

## Mode 1: Single Slide Edit

### Request

```json
{
  "slide_index": 2,
  "current_html": "<div class=\"slide-wrapper\" style=\"width: 1920px; height: 1080px;\"><h1>Current Title</h1><p>Current content</p></div>",
  "elements": [],
  "background": null,
  "user_instruction": "Make it more concise",
  "format_type": "edit"
}
```

**Required Fields**:
- `slide_index` (integer): Slide position (0-based)
- `current_html` (string): Current slide HTML content
- `user_instruction` (string): Edit instruction (required, max 2000 chars)
- `format_type` (string): Must be `"edit"`

**Optional Fields**:
- `elements` (array): Slide elements (shapes, images) - empty for edit mode
- `background` (object|null): Slide background config
- `document_id` (string): Document ID (optional for Mode 1)

### Response

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Edit job for slide 2 queued. Poll /api/slides/jobs/{job_id} for status.",
  "estimated_time": "10-30 seconds"
}
```

### Job Status Response (After Completion)

Poll: `GET /api/slides/jobs/{job_id}`

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "slide_number": 3,
  "formatted_html": "<div class=\"slide-wrapper\" style=\"width: 1920px; height: 1080px;\"><h1>Concise Title</h1><p>Key points only</p></div>",
  "suggested_elements": null,
  "suggested_background": null,
  "ai_explanation": "Removed verbose descriptions, kept essential information",
  "created_at": "2025-12-28T12:00:00Z",
  "started_at": "2025-12-28T12:00:01Z",
  "completed_at": "2025-12-28T12:00:15Z",
  "processing_time_seconds": 14.2,
  "error": null
}
```

**Response Fields**:
- `slide_number` (integer): 1-based slide number (slide_index + 1)
- `formatted_html` (string): Edited slide HTML
- `ai_explanation` (string): Summary of changes made
- `status` (enum): `"pending"` | `"processing"` | `"completed"` | `"failed"`

---

## Mode 2: Multiple Specific Slides Edit

### Request

```json
{
  "slides_data": [
    {
      "slide_index": 0,
      "current_html": "<div class=\"slide-wrapper\">...</div>",
      "elements": [],
      "background": null
    },
    {
      "slide_index": 2,
      "current_html": "<div class=\"slide-wrapper\">...</div>",
      "elements": [],
      "background": null
    },
    {
      "slide_index": 5,
      "current_html": "<div class=\"slide-wrapper\">...</div>",
      "elements": [],
      "background": null
    }
  ],
  "user_instruction": "Add more emphasis to key points",
  "format_type": "edit"
}
```

**Required Fields**:
- `slides_data` (array): Array of slides to edit
  - Each slide: `{ slide_index, current_html, elements, background }`
- `user_instruction` (string): Edit instruction (same for all slides)
- `format_type` (string): Must be `"edit"`

**Optional Fields**:
- `document_id` (string): Document ID (optional for Mode 2)
- `process_all_slides` (boolean): Must be `false` or omitted for Mode 2

**Limits**:
- Maximum 50 slides per request

### Response

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "pending",
  "message": "Edit job for 3 slides queued. Poll /api/slides/jobs/{job_id} for status.",
  "estimated_time": "45-90 seconds"
}
```

### Job Status Response (After Completion)

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "completed",
  "is_batch": true,
  "total_slides": 3,
  "completed_slides": 3,
  "failed_slides": 0,
  "slide_numbers": [1, 3, 6],
  "slides_results": [
    {
      "slide_index": 0,
      "formatted_html": "<div class=\"slide-wrapper\">...</div>",
      "ai_explanation": "Added bold emphasis to key metrics",
      "error": null
    },
    {
      "slide_index": 2,
      "formatted_html": "<div class=\"slide-wrapper\">...</div>",
      "ai_explanation": "Highlighted important points with strong tags",
      "error": null
    },
    {
      "slide_index": 5,
      "formatted_html": "<div class=\"slide-wrapper\">...</div>",
      "ai_explanation": "Emphasized action items with increased font weight",
      "error": null
    }
  ],
  "created_at": "2025-12-28T12:00:00Z",
  "started_at": "2025-12-28T12:00:01Z",
  "completed_at": "2025-12-28T12:01:30Z",
  "processing_time_seconds": 89.5,
  "error": null
}
```

**Response Fields**:
- `is_batch` (boolean): Always `true` for Mode 2
- `total_slides` (integer): Total number of slides requested
- `completed_slides` (integer): Number successfully edited
- `failed_slides` (integer): Number that failed
- `slide_numbers` (array): 1-based slide numbers that were edited
- `slides_results` (array): Results for each slide
  - `slide_index` (integer): 0-based slide position
  - `formatted_html` (string): Edited HTML
  - `ai_explanation` (string): Changes summary
  - `error` (string|null): Error message if failed

---

## Mode 3: Entire Document Edit

### Request

```json
{
  "process_all_slides": true,
  "document_id": "doc_abc123xyz",
  "slides_data": [
    {
      "slide_index": 0,
      "current_html": "<div class=\"slide-wrapper\">...</div>",
      "elements": [],
      "background": null
    },
    {
      "slide_index": 1,
      "current_html": "<div class=\"slide-wrapper\">...</div>",
      "elements": [],
      "background": null
    }
  ],
  "user_instruction": "Simplify technical terms for general audience",
  "format_type": "edit"
}
```

**Required Fields**:
- `process_all_slides` (boolean): Must be `true` for Mode 3
- `document_id` (string): Document ID (REQUIRED for Mode 3)
- `slides_data` (array): ALL slides in document
- `user_instruction` (string): Edit instruction
- `format_type` (string): Must be `"edit"`

**Limits**:
- Maximum 50 slides per request

### Response

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440002",
  "status": "pending",
  "message": "Edit job for 30 slides queued. Poll /api/slides/jobs/{job_id} for status.",
  "estimated_time": "450-900 seconds"
}
```

### Job Status Response (After Completion)

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440002",
  "status": "completed",
  "is_batch": true,
  "total_slides": 30,
  "completed_slides": 30,
  "failed_slides": 0,
  "slide_numbers": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30],
  "slides_results": [
    {
      "slide_index": 0,
      "formatted_html": "<div class=\"slide-wrapper\">...</div>",
      "ai_explanation": "Replaced 'API' with 'Application Programming Interface'",
      "error": null
    },
    {
      "slide_index": 1,
      "formatted_html": "<div class=\"slide-wrapper\">...</div>",
      "ai_explanation": "Simplified 'asynchronous processing' to 'background tasks'",
      "error": null
    }
  ],
  "created_at": "2025-12-28T12:00:00Z",
  "started_at": "2025-12-28T12:00:01Z",
  "completed_at": "2025-12-28T12:15:30Z",
  "processing_time_seconds": 929.0,
  "error": null
}
```

**Same as Mode 2**, no additional version fields (unlike Format endpoint Mode 3)

---

## Error Responses

### Validation Errors (400)

```json
{
  "detail": "user_instruction is required for editing. Provide clear instructions like 'Make it shorter', 'Add more details', etc."
}
```

```json
{
  "detail": "This endpoint only accepts format_type='edit'. Use /api/slides/ai-format for format_type='format'"
}
```

```json
{
  "detail": "document_id is required for Mode 3 (process_all_slides=true)"
}
```

```json
{
  "detail": "Too many slides. Maximum 50 slides per edit request."
}
```

### Insufficient Points (402)

```json
{
  "detail": {
    "error": "INSUFFICIENT_POINTS",
    "message": "Không đủ điểm để edit 10 slide(s). Cần: 20, Còn: 5",
    "points_needed": 20,
    "points_available": 5,
    "slides_count": 10
  }
}
```

### Authentication Error (401)

```json
{
  "detail": "Missing or invalid authentication token"
}
```

### Server Error (500)

```json
{
  "detail": "Failed to enqueue task to Redis"
}
```

---

## Job Status Polling

**Endpoint**: `GET /api/slides/jobs/{job_id}`

**Polling Strategy**:
1. Poll every 2-3 seconds
2. Stop when `status` is `"completed"` or `"failed"`
3. Show progress using `completed_slides` / `total_slides` for batch jobs

**Status Values**:
- `"pending"`: Job queued, waiting for worker
- `"processing"`: Worker is editing slides
- `"completed"`: All slides edited successfully
- `"failed"`: Job failed with error

---

## Points Deduction

**Timing**: Points deducted BEFORE job starts

**Cost Calculation**:
- Mode 1: 2 points (single slide)
- Mode 2: 5 points per chunk (max 12 slides/chunk)
- Mode 3: 5 points per chunk (max 12 slides/chunk)

**Examples**:GET /api/slides/ai-generate/status/{document_id}
- 1 slide = 2 points (Mode 1)
- 5 slides = 5 points (Mode 2/3: 1 chunk)
- 10 slides = 5 points (Mode 2/3: 1 chunk)
- 15 slides = 10 points (Mode 2/3: 2 chunks)
- 30 slides = 15 points (Mode 2/3: 3 chunks)
- 50 slides = 25 points (Mode 2/3: 5 chunks, max)

---

## Key Differences: Format vs Edit

| Feature | **Format** (`/api/slides/ai-format`) | **Edit** (`/api/slides/ai-edit`) |
|---------|--------------------------------------|----------------------------------|
| **AI Model** | Claude Sonnet 4.5 (Vertex AI) | Gemini 3 Pro Preview |
| **Temperature** | 0.7 (high creativity) | 0.3 (low creativity) |
| **Focus** | Layout, design, visual hierarchy | User instruction only |
| **Changes** | Structure, spacing, fonts, colors | Text content only |
| **Creativity** | Suggest improvements | Minimal changes |
| **Cost** | 10 points/chunk (format), 2/slide (edit) | 5 points/chunk (edit), 2/slide (single) |
| **User Instruction** | Optional | REQUIRED |

---

## Processing Time Estimates

**Single Slide (Mode 1)**:
- Average: 10-30 seconds
- Depends on content length and complexity

**Multiple Slides (Mode 2/3)**:
- Per slide: 10-30 seconds
- Parallel processing: All slides processed simultaneously
- Total time ≈ longest single slide processing time

**Examples**:
- 1 slide: 10-30 seconds
- 5 slides: 15-30 seconds (parallel)
- 10 slides: 20-35 seconds (parallel)
- 30 slides: 25-40 seconds (parallel)

---

## Best Practices

1. **Clear Instructions**: Be specific in `user_instruction`
   - ✅ Good: "Make it shorter by removing examples"
   - ❌ Bad: "Improve it"

2. **Appropriate Mode Selection**:
   - Use Mode 1 for single slide quick edits
   - Use Mode 2 for specific slides with same instruction
   - Use Mode 3 only when all slides need same edit

3. **Batch Size**: Keep under 30 slides for faster response

4. **Polling**: Don't poll too frequently (2-3 seconds interval)

5. **Error Handling**: Always check `error` field in results

6. **Points Check**: Verify sufficient points before calling endpoint

---

## Common Use Cases

### Shorten Content
```json
{
  "user_instruction": "Make it more concise, keep only key points"
}
```

### Add Details
```json
{
  "user_instruction": "Add more specific examples and statistics"
}
```

### Simplify Language
```json
{
  "user_instruction": "Simplify technical terms for non-technical audience"
}
```

### Add Emphasis
```json
{
  "user_instruction": "Add more emphasis to important points using bold"
}
```

### Change Tone
```json
{
  "user_instruction": "Make it more professional and formal"
}
```
