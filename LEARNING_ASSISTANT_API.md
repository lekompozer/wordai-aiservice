# Learning Assistant API — Technical Specification

**Base path:** `/api/learning-assistant`
**Auth:** Firebase Bearer token required on all endpoints
**Model:** Gemini 3.1 Flash Lite Preview (`gemini-3.1-flash-lite-preview`)
**Cost:** 1 point per request (deducted up-front on POST)

---

## Overview

Two features, each with an async queue pattern:

| Feature | POST (start job) | GET (poll result) |
|---------|-----------------|-------------------|
| Solve Homework | `POST /solve` | `GET /solve/{job_id}/status` |
| Grade & Study Plan | `POST /grade` | `GET /grade/{job_id}/status` |
| History (list) | `GET /history` | — |
| History (detail) | `GET /history/{job_id}` | — |

**Polling flow:**
1. POST → receive `job_id`, `status: "pending"`, points deducted immediately
2. GET status repeatedly until `status` is `"completed"` or `"failed"` (poll every 2–3 s)

---

## Common Types

### Math Formatting (KaTeX)

All AI responses use **KaTeX** for mathematical notation:
- Inline math: `$...$` — e.g. `$x^2 + 1$`, `$\int_0^1 f(x)dx$`
- Block math: `$$...$$` — e.g. `$$\frac{a^2+b^2}{c}$$`

Frontend must render these with a KaTeX library (e.g. `react-katex`, `katex`, `rehype-katex`). Applies to all subjects: Math, Physics, Chemistry, Biology, etc.

### Job Status Values

| Value | Meaning |
|-------|---------|
| `pending` | Queued, not yet picked up |
| `processing` | AI is generating |
| `completed` | Result ready — all result fields populated |
| `failed` | Error — check `error` field |

### Subject Values

`math` · `physics` · `chemistry` · `biology` · `literature` · `history` · `english` · `computer_science` · `other`

### Grade Level Values

| Value | Meaning |
|-------|---------|
| `primary` | Tiểu học |
| `middle_school` | Trung học cơ sở |
| `high_school` | Trung học phổ thông |
| `university` | Đại học / Cao đẳng |
| `other` | Khác |

### Image Encoding

Images must be **base64-encoded** strings of the raw image bytes (no `data:image/...;base64,` prefix).

Supported MIME types: `image/jpeg`, `image/png`
Maximum recommended decoded size: ~4 MB per image.

---

## Feature 1 — Solve Homework

### POST `/api/learning-assistant/solve`

Start an AI homework-solving job. The AI returns a numbered step-by-step solution with formulas used, a definitive final answer, and study tips.

**At least one of `question_text` or `question_image` is required.** Both may be sent together (e.g. typed context + photo of the problem).

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question_text` | `string` (max 5 000 chars) | Conditional | Typed question text |
| `question_image` | `string` (base64) | Conditional | Photo of the question |
| `image_mime_type` | `string` | No | `image/jpeg` (default) or `image/png` |
| `subject` | `string` | No | See Subject Values. Default: `other` |
| `grade_level` | `string` | No | See Grade Level Values. Default: `other` |
| `language` | `string` | No | `vi` (default) or `en` |

#### Response — 200 OK (job started)

| Field | Type | Description |
|-------|------|-------------|
| `success` | `boolean` | `true` |
| `job_id` | `string` | e.g. `solve_a3f9b12c0d1e` — use this to poll |
| `status` | `string` | `"pending"` |
| `points_deducted` | `integer` | `1` |
| `new_balance` | `integer` | Remaining points after deduction |

#### Error Responses

| HTTP | Condition |
|------|-----------|
| 403 | Insufficient points — `detail` includes `Cần: 1, Còn lại: N` |
| 422 | Neither `question_text` nor `question_image` provided |
| 401 | Invalid / missing Firebase token |

---

### GET `/api/learning-assistant/solve/{job_id}/status`

Poll for the result of a solve job.

#### Path Parameter

| Parameter | Description |
|-----------|-------------|
| `job_id` | Returned by the POST endpoint |

#### Response — 200 OK

| Field | Type | When present | Description |
|-------|------|-------------|-------------|
| `success` | `boolean` | Always | `true` |
| `job_id` | `string` | Always | |
| `status` | `string` | Always | `pending` / `processing` / `completed` / `failed` |
| `points_deducted` | `integer` | Always | `1` |
| `new_balance` | `integer` | Completed | Balance after deduction |
| `solution_steps` | `string[]` | Completed | Ordered list of step descriptions (plain text, may contain LaTeX) |
| `final_answer` | `string` | Completed | Concise final answer |
| `explanation` | `string` | Completed | Conceptual explanation of the approach |
| `key_formulas` | `string[]` | Completed | Formulas / theorems used |
| `study_tips` | `string[]` | Completed | Personalised study suggestions |
| `tokens` | `object` | Completed | `{ input_tokens, output_tokens }` |
| `error` | `string` | Failed | Error message |

#### Error Responses

| HTTP | Condition |
|------|-----------|
| 404 | Job not found or expired |
| 403 | job_id belongs to a different user |

---

## Feature 2 — Grade & Study Plan

### POST `/api/learning-assistant/grade`

Start an AI grading job. The AI scores the student's work, explains mistakes in detail, provides the correct solution, and generates a personalised study plan.

**At least one of `assignment_image` or `assignment_text` is required.**
**At least one of `student_work_image` or `student_answer_text` is required.**

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `assignment_image` | `string` (base64) | Conditional | Photo of the assignment / question sheet |
| `assignment_image_mime_type` | `string` | No | `image/jpeg` (default) or `image/png` |
| `assignment_text` | `string` | Conditional | Typed assignment text |
| `student_work_image` | `string` (base64) | Conditional | Photo of student's handwritten / typed work |
| `student_work_image_mime_type` | `string` | No | `image/jpeg` (default) or `image/png` |
| `student_answer_text` | `string` | Conditional | Typed student answer |
| `subject` | `string` | No | See Subject Values. Default: `other` |
| `grade_level` | `string` | No | See Grade Level Values. Default: `other` |
| `language` | `string` | No | BCP-47 / ISO 639-1 language code. Default: `vi`. See [Supported Languages](#supported-languages) |

#### Response — 200 OK (job started)

| Field | Type | Description |
|-------|------|-------------|
| `success` | `boolean` | `true` |
| `job_id` | `string` | e.g. `grade_7c2d4e1f8a09` — use this to poll |
| `status` | `string` | `"pending"` |
| `points_deducted` | `integer` | `1` |
| `new_balance` | `integer` | Remaining points after deduction |

#### Error Responses

| HTTP | Condition |
|------|-----------|
| 403 | Insufficient points |
| 422 | Missing assignment source or missing student work source |
| 401 | Invalid / missing Firebase token |

---

### GET `/api/learning-assistant/grade/{job_id}/status`

Poll for the result of a grade job.

#### Path Parameter

| Parameter | Description |
|-----------|-------------|
| `job_id` | Returned by the POST endpoint |

#### Response — 200 OK

| Field | Type | When present | Description |
|-------|------|-------------|-------------|
| `success` | `boolean` | Always | `true` |
| `job_id` | `string` | Always | |
| `status` | `string` | Always | `pending` / `processing` / `completed` / `failed` |
| `points_deducted` | `integer` | Always | `1` |
| `new_balance` | `integer` | Completed | Balance after deduction |
| `score` | `number` | Completed | Numeric score, e.g. `8.5` (scale set by AI based on assignment) |
| `score_breakdown` | `object` | Completed | Per-criterion scores, key = criterion name, value = score |
| `overall_feedback` | `string` | Completed | Summary feedback paragraph |
| `strengths` | `string[]` | Completed | What the student did well |
| `weaknesses` | `string[]` | Completed | Specific mistakes / gaps identified |
| `correct_solution` | `string` | Completed | Full correct answer / model solution |
| `improvement_plan` | `string[]` | Completed | Concrete next steps to improve this assignment type |
| `study_plan` | `object[]` | Completed | Weekly study plan items. Each: `{ week, focus, activities[], resources[] }` |
| `recommended_materials` | `string[]` | Completed | Textbook chapters, topics, or keywords to review |
| `tokens` | `object` | Completed | `{ input_tokens, output_tokens }` |
| `error` | `string` | Failed | Error message |

#### Error Responses

| HTTP | Condition |
|------|-----------|
| 404 | Job not found or expired |
| 403 | job_id belongs to a different user |

---

## Notes for Frontend

- **Points are deducted immediately** when the POST is called. If the AI fails, points are **not** auto-refunded (contact support).
- Job results are stored in Redis and expire after **24 hours**. Cache results on the client to avoid re-polling.
- Both `solution_steps` and `study_plan` arrays can be empty `[]` in rare edge cases — always guard against null/empty.
- `score_breakdown` keys are dynamic (AI-generated criterion names, language matches `language` param). Do not hard-code keys.
- `study_plan[].resources` may be an empty array if no specific resources are applicable.
- Typical processing time: **5–20 seconds** depending on image size and complexity.

---

## Feature 3 — History

### GET `/api/learning-assistant/history`

Return the authenticated user's completed Learning Assistant jobs stored in MongoDB. Jobs are persisted permanently (no expiry, unlike Redis which expires in 24 h).

**Note:** Images are never stored in history — only text content and results.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | `string` | — | Filter by job type: `solve` or `grade` |
| `subject` | `string` | — | Filter by subject (e.g. `math`, `physics`) |
| `limit` | `integer` | `20` | Max records to return (max `100`) |
| `skip` | `integer` | `0` | Offset for pagination |

#### Response — 200 OK

| Field | Type | Description |
|-------|------|-------------|
| `success` | `boolean` | `true` |
| `total` | `integer` | Total matching records (for pagination) |
| `limit` | `integer` | Limit used |
| `skip` | `integer` | Skip used |
| `items` | `object[]` | Array of history records, newest first |

#### History Item Fields

Common fields on every item:

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `string` | Original job ID |
| `type` | `string` | `"solve"` or `"grade"` |
| `subject` | `string` | Subject |
| `grade_level` | `string` | Grade level |
| `language` | `string` | Language code used for this job |
| `points_deducted` | `integer` | `1` |
| `created_at` | `string` | ISO 8601 timestamp |

Additional fields for `type: "solve"` items:

| Field | Type | Description |
|-------|------|-------------|
| `question_text` | `string\|null` | Typed question (null if image-only) |
| `question_image_url` | `string\|null` | R2 public URL of the question image (null if no image was sent) |
| `solution_steps` | `string[]` | Step-by-step solution |
| `final_answer` | `string` | Final answer |
| `explanation` | `string` | Conceptual explanation |
| `key_formulas` | `string[]` | Formulas used |
| `study_tips` | `string[]` | Study tips |

Additional fields for `type: "grade"` items:

| Field | Type | Description |
|-------|------|-------------|
| `assignment_text` | `string\|null` | Typed assignment text |
| `assignment_image_url` | `string\|null` | R2 public URL of the assignment image (null if no image was sent) |
| `student_answer_text` | `string\|null` | Typed student answer |
| `student_image_url` | `string\|null` | R2 public URL of the student work image (null if no image was sent) |
| `score` | `number` | Numeric score |
| `score_breakdown` | `object` | Per-criterion scores |
| `overall_feedback` | `string` | Summary feedback |
| `strengths` | `string[]` | What was done well |
| `weaknesses` | `string[]` | Mistakes / gaps |
| `correct_solution` | `string` | Model solution |
| `improvement_plan` | `string[]` | Concrete next steps |
| `study_plan` | `object[]` | Weekly study plan |
| `recommended_materials` | `string[]` | Topics to review |

---

## Supported Languages

The `language` parameter accepts any BCP-47 / ISO 639-1 code that Gemini supports.
The AI will respond entirely in the specified language, including all explanations, study tips, and study plans.

| Code | Language |
|------|----------|
| `vi` | Tiếng Việt (Vietnamese) — **default** |
| `en` | English |
| `ja` | 日本語 (Japanese) |
| `ko` | 한국어 (Korean) |
| `zh` | 中文简体 (Chinese Simplified) |
| `zh-tw` | 中文繁體 (Chinese Traditional) |
| `fr` | Français (French) |
| `de` | Deutsch (German) |
| `es` | Español (Spanish) |
| `pt` | Português (Portuguese) |
| `ru` | Русский (Russian) |
| `ar` | العربية (Arabic) |
| `th` | ภาษาไทย (Thai) |
| `id` | Bahasa Indonesia |
| `ms` | Bahasa Melayu (Malay) |
| `hi` | हिंदी (Hindi) |
| `tr` | Türkçe (Turkish) |
| `it` | Italiano (Italian) |
| `nl` | Nederlands (Dutch) |
| `pl` | Polski (Polish) |
| `uk` | Українська (Ukrainian) |

Any other valid BCP-47 code is also accepted — the AI will attempt to respond in that language.

---

## Image Input Notes

**Current flow — base64 inline, then R2 for history:**

1. Frontend reads the image file
2. Encodes it as a base64 string (raw bytes only — no `data:image/...;base64,` prefix)
3. Sends base64 string in the JSON request body
4. Backend forwards it directly to Gemini for AI processing
5. **After AI completes**, the worker uploads the image to R2 under `learning-assistant/{user_id}/{job_id}_{suffix}.jpg`
6. The R2 public URL is saved in MongoDB history (`question_image_url`, `assignment_image_url`, `student_image_url`)
7. The original base64 is never persisted — only the R2 URL is stored

URL format: `https://static.wordai.pro/learning-assistant/{user_id}/{job_id}_{suffix}.jpg`
