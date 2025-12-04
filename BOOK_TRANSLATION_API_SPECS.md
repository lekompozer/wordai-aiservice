# Book Translation API Technical Specifications

## Overview
This document provides technical specifications for the Book Translation API endpoints. The system supports translation of books and chapters into 17 languages using AI-powered translation with Gemini 2.5 Pro.

## Base URL
```
Production: https://api.wordai.pro
Development: http://localhost:8000
```

## Authentication
All endpoints require Firebase authentication token in the Authorization header:
```
Authorization: Bearer <firebase_id_token>
```

## Supported Languages

| Language Code | Language Name | Flag |
|--------------|---------------|------|
| `en` | English | 🇬🇧 |
| `vi` | Tiếng Việt | 🇻🇳 |
| `zh-CN` | Chinese (Simplified) | 🇨🇳 |
| `zh-TW` | Chinese (Traditional) | 🇹🇼 |
| `ja` | Japanese | 🇯🇵 |
| `ko` | Korean | 🇰🇷 |
| `th` | Thai | 🇹🇭 |
| `id` | Indonesian | 🇮🇩 |
| `km` | Khmer | 🇰🇭 |
| `lo` | Lao | 🇱🇦 |
| `hi` | Hindi | 🇮🇳 |
| `ms` | Malay | 🇲🇾 |
| `pt` | Portuguese | 🇵🇹 |
| `ru` | Russian | 🇷🇺 |
| `fr` | French | 🇫🇷 |
| `de` | German | 🇩🇪 |
| `es` | Spanish | 🇪🇸 |

## Endpoints

### 1. Translate Entire Book

Translates book metadata and all chapters to target language.

**Endpoint:** `POST /api/v1/books/{book_id}/translate`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book

**Request Body:**
```json
{
  "target_language": "vi"
}
```

**Request Fields:**
- `target_language` (string, required): Target language code from supported languages list

**Response:** `200 OK`
```json
{
  "success": true,
  "book_id": "675042a31d364fd60986bfe5",
  "target_language": "vi",
  "source_language": "en",
  "translated_fields": {
    "title": "Tiêu đề đã dịch",
    "description": "Mô tả đã dịch",
    "content_html": null
  },
  "chapters_translated": 5,
  "total_cost_points": 12,
  "message": "Book translated successfully to vi"
}
```

**Response Fields:**
- `success` (boolean): Indicates if translation was successful
- `book_id` (string): ID of the translated book
- `target_language` (string): Language code used for translation
- `source_language` (string): Source language code
- `translated_fields` (object): Contains translated content
  - `title` (string): Translated book title
  - `description` (string): Translated book description
  - `content_html` (string|null): Always null for books (only used in chapter responses)
- `chapters_translated` (integer): Number of chapters successfully translated
- `total_cost_points` (integer): Total points deducted (2 for metadata + 2 per chapter)
- `message` (string): Success message with language code

**Points Cost:**
- 2 points for book metadata (title + description)
- 2 points per chapter
- Total = 2 + (2 × number_of_chapters)

**Error Responses:**

`400 Bad Request` - Invalid language code:
```json
{
  "detail": "Language 'xyz' is not supported"
}
```

`403 Forbidden` - Insufficient points:
```json
{
  "detail": {
    "error": "insufficient_points",
    "message": "Không đủ points để dịch book. Cần: 12, Còn: 5",
    "points_needed": 12,
    "points_available": 5
  }
}
```

`404 Not Found` - Book not found:
```json
{
  "detail": "Book not found or you don't have permission"
}
```

`403 Forbidden` - No access permission:
```json
{
  "detail": "Book not found or you don't have permission"
}
```

`409 Conflict` - Translation already exists:
```json
{
  "detail": "Translation for language 'vi' already exists for this book"
}
```

`500 Internal Server Error` - Translation service error:
```json
{
  "detail": "Translation service error: <error_message>"
}
```

---

### 2. Translate Single Chapter

Translates a specific chapter to target language.

**Endpoint:** `POST /api/v1/books/{book_id}/chapters/{chapter_id}/translate`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book
- `chapter_id` (string, required): The unique identifier of the chapter

**Request Body:**
```json
{
  "target_language": "vi"
}
```

**Request Fields:**
- `target_language` (string, required): Target language code from supported languages list

**Response:** `200 OK`
```json
{
  "success": true,
  "chapter_id": "675042a31d364fd60986bfe6",
  "book_id": "675042a31d364fd60986bfe5",
  "target_language": "vi",
  "source_language": "en",
  "translated_fields": {
    "title": "Tiêu đề chương đã dịch",
    "description": "Mô tả chương đã dịch",
    "content_html": "<p>Nội dung đã dịch...</p>"
  },
  "translation_cost_points": 2,
  "message": "Chapter translated successfully to vi"
}
```

**Response Fields:**
- `success` (boolean): Indicates if translation was successful
- `chapter_id` (string): ID of the translated chapter
- `book_id` (string): ID of the book
- `target_language` (string): Language code used for translation
- `source_language` (string): Source language code
- `translated_fields` (object): Contains translated content
  - `title` (string): Translated chapter title
  - `description` (string): Translated chapter description
  - `content_html` (string): Full translated HTML content of the chapter
- `translation_cost_points` (integer): Points deducted (always 2 per chapter)
- `message` (string): Success message with language code

**Points Cost:**
- 2 points per chapter translation

**Error Responses:**

`400 Bad Request` - Invalid language code:
```json
{
  "detail": "Language 'xyz' is not supported"
}
```

`403 Forbidden` - Insufficient points:
```json
{
  "detail": {
    "error": "insufficient_points",
    "message": "Không đủ points để dịch chapter. Cần: 2, Còn: 1",
    "points_needed": 2,
    "points_available": 1
  }
}
```

`404 Not Found` - Book or chapter not found:
```json
{
  "detail": "Book not found or you don't have permission"
}
```
```json
{
  "detail": "Chapter 675042a31d364fd60986bfe6 not found in book 675042a31d364fd60986bfe5"
}
```

`403 Forbidden` - No access permission:
```json
{
  "detail": "Book not found or you don't have permission"
}
```

`409 Conflict` - Translation already exists:
```json
{
  "detail": "Translation for language 'vi' already exists for this chapter"
}
```

`500 Internal Server Error` - Translation service error:
```json
{
  "detail": "Translation service error: <error_message>"
}
```

---

### 3. Get Available Languages for Book

Retrieves list of all available translations for a book.

**Endpoint:** `GET /api/v1/books/{book_id}/languages`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book

**Response:** `200 OK`
```json
{
  "book_id": "675042a31d364fd60986bfe5",
  "default_language": "en",
  "available_languages": [
    {
      "code": "en",
      "name": "English",
      "flag": "🇬🇧",
      "is_default": true,
      "translated_at": null
    },
    {
      "code": "vi",
      "name": "Tiếng Việt",
      "flag": "🇻🇳",
      "is_default": false,
      "translated_at": "2024-12-04T10:30:00Z"
    },
    {
      "code": "zh-CN",
      "name": "Chinese (Simplified)",
      "flag": "🇨🇳",
      "is_default": false,
      "translated_at": "2024-12-04T11:15:00Z"
    }
  ]
}
```

**Response Fields:**
- `book_id` (string): ID of the book
- `default_language` (string): Original language of the book
- `available_languages` (array): List of all available language versions
  - `code` (string): Language code
  - `name` (string): Full language name (e.g., "English", "Chinese (Simplified)")
  - `flag` (string): Emoji flag for the language
  - `is_default` (boolean): True if this is the original language
  - `translated_at` (string|null): ISO timestamp when translation was created (null for default language)

**Error Responses:**

`404 Not Found` - Book not found:
```json
{
  "detail": "Book not found"
}
```

`403 Forbidden` - No access permission:
```json
{
  "detail": "You don't have access to this book"
}
```

---

### 4. Update Background for Language

Sets a custom background configuration for a specific language version of a book or chapter.

**Book Endpoint:** `PUT /api/v1/books/{book_id}/background/{language}`

**Chapter Endpoint:** `PUT /api/v1/books/{book_id}/chapters/{chapter_id}/background/{language}`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book
- `chapter_id` (string, required for chapter endpoint): The unique identifier of the chapter
- `language` (string, required): Language code from supported languages list

**Request Body:**
```json
{
  "background_config": {
    "url": "https://static.wordai.pro/backgrounds/book-vi.jpg",
    "type": "image",
    "blur": 5
  }
}
```

**Request Fields:**
- `background_config` (object, required): Background configuration object for this language version
  - Can contain any custom fields (url, type, blur, color, etc.)

**Response:** `200 OK`
```json
{
  "success": true,
  "book_id": "675042a31d364fd60986bfe5",
  "chapter_id": null,
  "language": "vi",
  "background_config": {
    "url": "https://static.wordai.pro/backgrounds/book-vi.jpg",
    "type": "image",
    "blur": 5
  },
  "message": "Background updated for vi version"
}
```

**Response Fields:**
- `success` (boolean): Indicates if update was successful
- `book_id` (string|null): ID of the book (null if updating chapter)
- `chapter_id` (string|null): ID of the chapter (null if updating book)
- `language` (string): Language code for which background was updated
- `background_config` (object): The new background configuration
- `message` (string): Success message with language code

**Error Responses:**

`400 Bad Request` - Invalid language code:
```json
{
  "detail": "Language 'xyz' is not supported"
}
```

`404 Not Found` - Book not found or translation doesn't exist:
```json
{
  "detail": "Book not found"
}
```
```json
{
  "detail": "Translation for language 'vi' does not exist"
}
```

`403 Forbidden` - No access permission:
```json
{
  "detail": "You don't have access to this book"
}
```

---

### 5. Delete Translation

Removes a specific language translation from a book and all its chapters.

**Endpoint:** `DELETE /api/v1/books/{book_id}/translations/{language}`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book
- `language` (string, required): Language code from supported languages list

**Response:** `200 OK`
```json
{
  "success": true,
  "book_id": "675042a31d364fd60986bfe5",
  "chapter_id": null,
  "language_deleted": "vi",
  "remaining_languages": ["en", "zh-CN"],
  "message": "Translation for vi deleted successfully (6 items updated)"
}
```

**Response Fields:**
- `success` (boolean): Indicates if deletion was successful
- `book_id` (string|null): ID of the book
- `chapter_id` (string|null): ID of the chapter (null for book deletions)
- `language_deleted` (string): Language code that was deleted
- `remaining_languages` (array): List of language codes still available after deletion
- `message` (string): Success message with language code and count of items updated

**Error Responses:**

`400 Bad Request` - Cannot delete default language:
```json
{
  "detail": "Cannot delete the default language"
}
```

`400 Bad Request` - Invalid language code:
```json
{
  "detail": "Language 'xyz' is not supported"
}
```

`404 Not Found` - Book not found or translation doesn't exist:
```json
{
  "detail": "Book not found"
}
```
```json
{
  "detail": "Translation for language 'vi' does not exist"
}
```

`403 Forbidden` - No access permission:
```json
{
  "detail": "You don't have access to this book"
}
```

---

### 6. Get Book with Language (Phase 1)

**NEW:** Retrieve book metadata in a specific language. Returns translated title/description if available.

**Endpoint:** `GET /api/v1/books/{book_id}?language={language_code}`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book

**Query Parameters:**
- `language` (string, optional): Target language code. If omitted, returns default language.

**Response:** `200 OK`
```json
{
  "book_id": "675042a31d364fd60986bfe5",
  "title": "Tiêu đề đã dịch",
  "description": "Mô tả đã dịch",
  "current_language": "vi",
  "available_languages": ["en", "vi", "zh-CN"],
  "...": "... other book fields ..."
}
```

**Response Fields:**
- `current_language` (string): The language code of the returned content
- `available_languages` (array): List of all available language translations
- `title` (string): Book title in requested language (falls back to default if translation missing)
- `description` (string): Book description in requested language

**Error Responses:**

`404 Not Found` - Translation not available:
```json
{
  "detail": "Translation for language 'vi' is not available for this book"
}
```

---

### 7. Get Chapters Tree with Language (Phase 1)

**NEW:** Retrieve chapter tree structure with translations. Supports recursive translation of nested chapters.

**Endpoint:** `GET /api/v1/books/{book_id}/chapters?language={language_code}`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book

**Query Parameters:**
- `language` (string, optional): Target language code. If omitted, returns default language.

**Response:** `200 OK`
```json
{
  "chapters": [
    {
      "chapter_id": "675042a31d364fd60986bfe6",
      "title": "Tiêu đề chương đã dịch",
      "description": "Mô tả đã dịch",
      "slug": "chapter-1",
      "order_index": 1,
      "children": []
    }
  ],
  "current_language": "vi",
  "available_languages": ["en", "vi", "zh-CN"]
}
```

**Response Fields:**
- `chapters` (array): Chapter tree with translated titles/descriptions
- `current_language` (string): Language of returned content
- `available_languages` (array): Available translation languages

**Note:** If translation missing, silently falls back to default language.

---

### 8. Get Single Chapter with Language (Phase 1)

**NEW:** Retrieve full chapter content including `content_html` in specific language. Essential for Tiptap editor.

**Endpoint:** `GET /api/v1/books/{book_id}/chapters/{chapter_id}?language={language_code}`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book
- `chapter_id` (string, required): The unique identifier of the chapter

**Query Parameters:**
- `language` (string, optional): Target language code. If omitted, returns default language.

**Response:** `200 OK`
```json
{
  "chapter_id": "675042a31d364fd60986bfe6",
  "book_id": "675042a31d364fd60986bfe5",
  "title": "Tiêu đề chương đã dịch",
  "description": "Mô tả đã dịch",
  "content_html": "<p>Nội dung HTML đầy đủ đã dịch...</p>",
  "slug": "chapter-1",
  "order_index": 1,
  "document_id": "doc_123",
  "current_language": "vi",
  "available_languages": ["en", "vi", "zh-CN"],
  "...": "... other chapter fields ..."
}
```

**Response Fields:**
- `content_html` (string): Full HTML content of chapter in requested language
- `current_language` (string): Language of returned content
- `available_languages` (array): Available translations for this chapter

**Use Case:** Load chapter content into Tiptap editor with specific language.

**Note:** Falls back to default language if translation missing.

---

### 9. Start Background Translation Job (Phase 2)

**NEW:** Start asynchronous translation of all chapters. Returns immediately with `job_id` for status polling.

**Endpoint:** `POST /api/v1/books/{book_id}/translate/start`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book

**Request Body:**
```json
{
  "target_language": "vi",
  "source_language": "en",
  "backgrounds": {
    "preserve_original": true
  }
}
```

**Request Fields:**
- `target_language` (string, required): Target language code
- `source_language` (string, optional): Source language code (default: book's original_language or "en")
- `backgrounds` (object, optional): Background handling options
  - `preserve_original` (boolean): Keep original backgrounds
  - `color` (string): Use solid color background
  - `gradient` (object): Use gradient background
  - `image_url` (string): Use custom image background

**Response:** `200 OK`
```json
{
  "job_id": "trans_a1b2c3d4e5f6",
  "book_id": "675042a31d364fd60986bfe5",
  "target_language": "vi",
  "source_language": "en",
  "status": "pending",
  "chapters_total": 9,
  "chapters_completed": 0,
  "chapters_failed": 0,
  "progress_percentage": 0,
  "current_chapter_id": null,
  "current_chapter_title": null,
  "estimated_time_remaining_seconds": 540,
  "started_at": null,
  "completed_at": null,
  "error": null,
  "failed_chapters": [],
  "points_deducted": 20,
  "created_at": "2024-12-04T10:00:00Z",
  "updated_at": "2024-12-04T10:00:00Z"
}
```

**Response Fields:**
- `job_id` (string): Unique job identifier for status polling
- `status` (string): Job status - `pending`, `in_progress`, `completed`, `failed`, `cancelled`
- `chapters_total` (integer): Total chapters to translate
- `chapters_completed` (integer): Chapters completed so far
- `chapters_failed` (integer): Chapters that failed translation
- `progress_percentage` (integer): Completion percentage (0-100)
- `current_chapter_id` (string|null): Currently translating chapter ID
- `current_chapter_title` (string|null): Currently translating chapter title
- `estimated_time_remaining_seconds` (integer): Estimated time to completion
- `failed_chapters` (array): List of failed chapter details
- `points_deducted` (integer): Total points deducted (2 + 2×chapters)

**Points Cost:**
- Points are deducted **immediately** when job starts
- 2 points for book metadata + 2 points per chapter
- Example: 9 chapters = 2 + (9 × 2) = 20 points

**Error Responses:**

`402 Payment Required` - Insufficient points:
```json
{
  "detail": "Not enough points. Need 20, have 15"
}
```

`400 Bad Request` - No chapters:
```json
{
  "detail": "Book has no chapters to translate"
}
```

---

### 10. Get Translation Job Status (Phase 2)

**NEW:** Poll for translation job progress. Frontend should call this endpoint every 2-5 seconds.

**Endpoint:** `GET /api/v1/books/{book_id}/translate/status/{job_id}`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book
- `job_id` (string, required): Job ID returned from `/translate/start`

**Response:** `200 OK`
```json
{
  "job_id": "trans_a1b2c3d4e5f6",
  "book_id": "675042a31d364fd60986bfe5",
  "target_language": "vi",
  "source_language": "en",
  "status": "in_progress",
  "chapters_total": 9,
  "chapters_completed": 3,
  "chapters_failed": 0,
  "progress_percentage": 33,
  "current_chapter_id": "chapter_004",
  "current_chapter_title": "Chapter 4: Advanced Techniques",
  "estimated_time_remaining_seconds": 360,
  "started_at": "2024-12-04T10:00:05Z",
  "completed_at": null,
  "error": null,
  "failed_chapters": [],
  "points_deducted": 20,
  "created_at": "2024-12-04T10:00:00Z",
  "updated_at": "2024-12-04T10:03:15Z"
}
```

**Status Values:**
- `pending`: Job created, waiting to start
- `in_progress`: Currently translating chapters
- `completed`: All chapters translated successfully
- `failed`: Critical error, job stopped
- `cancelled`: User cancelled the job

**Polling Strategy:**
- Poll every 2-5 seconds while `status` is `pending` or `in_progress`
- Stop polling when `status` is `completed`, `failed`, or `cancelled`
- Use `progress_percentage` and `estimated_time_remaining_seconds` for UI

**Error Responses:**

`404 Not Found` - Job not found:
```json
{
  "detail": "Translation job not found"
}
```

---

### 11. Cancel Translation Job (Phase 2)

**NEW:** Cancel an in-progress translation job.

**Endpoint:** `DELETE /api/v1/books/{book_id}/translate/cancel/{job_id}`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book
- `job_id` (string, required): Job ID to cancel

**Response:** `200 OK`
```json
{
  "message": "Translation job cancelled successfully",
  "job_id": "trans_a1b2c3d4e5f6"
}
```

**Note:** Cancellation is best-effort. The current chapter being translated may still complete.

**Error Responses:**

`400 Bad Request` - Cannot cancel:
```json
{
  "detail": "Cannot cancel job in current state"
}
```

---

### 12. List All Translation Jobs (Phase 2)

**NEW:** Get all translation jobs for a specific book.

**Endpoint:** `GET /api/v1/books/{book_id}/translate/jobs?limit=20&skip=0`

**Path Parameters:**
- `book_id` (string, required): The unique identifier of the book

**Query Parameters:**
- `limit` (integer, optional): Maximum jobs to return (default: 20)
- `skip` (integer, optional): Number of jobs to skip (default: 0)

**Response:** `200 OK`
```json
{
  "jobs": [
    {
      "job_id": "trans_a1b2c3d4e5f6",
      "book_id": "675042a31d364fd60986bfe5",
      "target_language": "vi",
      "status": "completed",
      "chapters_total": 9,
      "chapters_completed": 9,
      "progress_percentage": 100,
      "created_at": "2024-12-04T10:00:00Z",
      "...": "... other job fields ..."
    }
  ],
  "total": 3,
  "limit": 20,
  "skip": 0
}
```

**Response Fields:**
- `jobs` (array): List of translation job objects
- `total` (integer): Total number of jobs for this book
- `limit` (integer): Limit used in query
- `skip` (integer): Skip value used in query

---

## Database Schema Changes

### Books Collection

**New Fields:**
```json
{
  "default_language": "en",
  "current_language": "en",
  "available_languages": ["en", "vi", "zh-CN"],
  "translations": {
    "vi": {
      "title": "Tiêu đề sách",
      "description": "Mô tả sách"
    },
    "zh-CN": {
      "title": "书名",
      "description": "书籍描述"
    }
  },
  "background_translations": {
    "vi": "https://static.wordai.pro/backgrounds/book-vi.jpg",
    "zh-CN": "https://static.wordai.pro/backgrounds/book-zh.jpg"
  }
}
```

**Field Descriptions:**
- `default_language`: Original language of the book (immutable)
- `current_language`: Currently active language for display
- `available_languages`: Array of all language codes that have translations
- `translations`: Object mapping language codes to translated metadata
- `background_translations`: Object mapping language codes to custom background URLs

**Indexes:**
```javascript
db.books.createIndex({ "default_language": 1 })
db.books.createIndex({ "current_language": 1 })
db.books.createIndex({ "available_languages": 1 })
```

### Chapters Collection

**New Fields:**
```json
{
  "default_language": "en",
  "current_language": "en",
  "available_languages": ["en", "vi", "zh-CN"],
  "translations": {
    "vi": {
      "content": "<p>Nội dung chương đã dịch...</p>"
    },
    "zh-CN": {
      "content": "<p>翻译的章节内容...</p>"
    }
  }
}
```

**Field Descriptions:**
- `default_language`: Original language of the chapter
- `current_language`: Currently active language for display
- `available_languages`: Array of all language codes that have translations
- `translations`: Object mapping language codes to translated content (HTML preserved)

**Indexes:**
```javascript
db.chapters.createIndex({ "book_id": 1, "available_languages": 1 })
db.chapters.createIndex({ "default_language": 1 })
```

---

## Translation Behavior

### HTML Structure Preservation
- All HTML tags, attributes, and structure are preserved during translation
- Only text content within tags is translated
- Code blocks, links, images remain unchanged
- Formatting (bold, italic, lists) is maintained

### Translation Quality
- Uses Gemini 2.5 Pro for high-quality translations
- Context-aware translation for better accuracy
- Preserves tone and style of original content
- Handles technical terms appropriately

### Retry Logic
- Automatic retry up to 3 attempts on translation failures
- Exponential backoff between retries
- Detailed error messages for debugging

### Points System
- Book metadata translation: 2 points
- Chapter translation: 2 points each
- Points are deducted before translation begins
- Failed translations do not consume points

---

## Error Handling

### Common HTTP Status Codes

| Status Code | Meaning | Common Causes |
|------------|---------|---------------|
| `200` | Success | Operation completed successfully |
| `400` | Bad Request | Invalid language code, invalid request body, cannot delete default language |
| `401` | Unauthorized | Missing or invalid authentication token |
| `403` | Forbidden | Insufficient points, user doesn't have access to the book |
| `404` | Not Found | Book, chapter, or translation not found |
| `409` | Conflict | Translation already exists |
| `500` | Internal Server Error | Database error, AI service error |

### Error Response Format
All error responses follow this format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

---

## Rate Limiting

Currently no rate limiting is implemented for translation endpoints. Consider implementing:
- Maximum translations per user per day
- Cooldown period between translations
- Queue system for bulk translations

---

## Performance Considerations

### Translation Time
- Book metadata: ~5-10 seconds
- Single chapter: ~60-120 seconds (1-2 minutes per chapter)
- Full book (9 chapters): ~10-20 minutes
- **Production Issue:** HTTP requests timeout at 30-60 seconds, causing issues with multi-chapter books

### Phase 1 Solution: Fast Metadata Translation
- **Default Behavior Changed:** `POST /translate` now translates **metadata only** by default
- Set `translate_chapters: false` (new default) for instant translation (5-10 seconds)
- Set `translate_chapters: true` to translate all chapters (use only for small books)
- **GET with ?language parameter:** Fast retrieval of translated content without re-translation

### Phase 2 Solution: Background Jobs
- **Problem:** Translating 9 chapters = 9-18 minutes → Frontend timeout
- **Solution:** Asynchronous job processing with status polling
- **Flow:**
  1. `POST /translate/start` → Returns `job_id` immediately (<1 second)
  2. Translation happens in background
  3. Frontend polls `GET /translate/status/{job_id}` every 2-5 seconds
  4. UI shows progress bar with `progress_percentage`, `current_chapter_title`, `estimated_time_remaining_seconds`
- **Benefits:** No timeout, better UX, progress tracking

### Recommendations
- ✅ **Implemented:** Background job processing with polling (Phase 2)
- ✅ **Implemented:** Progress tracking with real-time updates
- ✅ **Implemented:** Language parameter in GET endpoints (Phase 1)
- Consider adding webhooks for job completion (future enhancement)
- Implement job cleanup for old completed jobs (>30 days)

---

## Future Enhancements

### Planned Features
1. **Batch Translation**: Translate multiple books at once
2. **Translation Quality Scoring**: User ratings for translations
3. **Custom Glossary**: User-defined term translations
4. **Translation Memory**: Reuse previous translations for consistency
5. **Auto-Translation**: Automatic translation on book creation
6. **Language Detection**: Automatically detect source language
7. **Partial Retranslation**: Re-translate specific paragraphs
8. **Webhooks**: Notification when translation job completes (alternative to polling)

### API Extensions
1. `POST /api/v1/books/{book_id}/retranslate` - Force retranslation of existing content
2. `GET /api/v1/translations/history` - View user's all translation history across books
3. `POST /api/v1/translations/batch` - Batch translate multiple books
4. `POST /api/v1/books/{book_id}/translate/webhook` - Register webhook for job completion

### ✅ Completed (Phase 1 & 2)
- ~~Progress tracking for translations~~ → Background jobs with status polling
- ~~Background job processing~~ → Async processing with `asyncio`
- ~~Translation status tracking~~ → Job status: pending/in_progress/completed/failed/cancelled
- ~~Polling for completion~~ → `GET /translate/status/{job_id}` endpoint

---

## Testing Recommendations

### Test Cases for Frontend

1. **Happy Path Testing**
   - Translate a book with 1-2 chapters
   - Verify all fields are populated correctly
   - Check points deduction is accurate
   - Confirm translations appear in available_languages list

2. **Error Handling**
   - Test with insufficient points
   - Attempt to translate to invalid language
   - Try translating already-translated content
   - Test with non-existent book_id

3. **Edge Cases**
   - Books with no chapters
   - Books with 50+ chapters
   - HTML content with complex nested structures
   - Special characters in content (emojis, symbols)

4. **Permission Testing**
   - Access with valid authentication
   - Access without authentication
   - Access book you don't own
   - Access deleted book

5. **UI/UX Considerations**
   - Display loading states during translation
   - Show progress for multi-chapter translations
   - Handle translation errors gracefully
   - Confirm before expensive operations
   - Display remaining points before translation

---

## Integration Notes

### Frontend Integration Checklist

- [ ] Add language selector dropdown in book viewer
- [ ] Implement translation trigger buttons/modals
- [ ] Display available languages list
- [ ] Show points cost before translation
- [ ] Handle loading states (could take 30s-5min)
- [ ] Display success/error notifications
- [ ] Update UI after successful translation
- [ ] Cache translated content appropriately
- [ ] Implement language switching in reader
- [ ] Show custom backgrounds per language
- [ ] Add translation management UI for authors

### API Client Configuration

**Base Headers:**
```
Content-Type: application/json
Authorization: Bearer <firebase_token>
```

**Timeout Settings:**
- Standard requests: 30 seconds
- Translation requests: 300 seconds (5 minutes)
- Use longer timeouts for full book translations

### Security Considerations

1. **Authentication**: Always include valid Firebase token
2. **Authorization**: Backend validates book ownership
3. **Input Validation**: Validate language codes on frontend
4. **Points Check**: Show available points before operations
5. **Error Messages**: Don't expose sensitive system details

---

## Changelog

### Version 1.2.0 (2024-12-04) - Phase 2: Background Jobs

**✨ New Features:**
- 4 new endpoints for background translation jobs
- Asynchronous translation processing with `asyncio.create_task()`
- Job status tracking: `pending`, `in_progress`, `completed`, `failed`, `cancelled`
- Progress tracking: `chapters_completed`, `progress_percentage`, `estimated_time_remaining`
- Polling-based status checks for frontend integration
- Failed chapter tracking with error messages
- Partial success support (some chapters succeed, some fail)

**📝 New Endpoints:**
- `POST /books/{book_id}/translate/start` - Start background translation job
- `GET /books/{book_id}/translate/status/{job_id}` - Poll job status
- `DELETE /books/{book_id}/translate/cancel/{job_id}` - Cancel running job
- `GET /books/{book_id}/translate/jobs` - List all jobs for a book

**🔧 Technical Details:**
- New `translation_jobs` MongoDB collection with indexes
- Points deducted upfront when job starts (not when completed)
- Job processing isolated in `TranslationJobService`
- Translation continues even if some chapters fail
- Job cleanup strategy needed (future enhancement)

**🎯 Problem Solved:**
- Production timeout issue: 9 chapters × 2 min = 18 min → Frontend timeout at 30-60s
- Now returns `job_id` in <1 second, translation happens in background

---

### Version 1.1.0 (2024-12-04) - Phase 1: Language Parameters

**✨ New Features:**
- 3 new/modified GET endpoints with `?language` query parameter
- Fast retrieval of translated content without re-translation
- Recursive translation support for nested chapter trees
- Silent fallback to default language if translation missing

**📝 New/Modified Endpoints:**
- `GET /books/{book_id}?language=xx` - Get book with specific language
- `GET /books/{book_id}/chapters?language=xx` - Get chapter tree with translation
- `GET /books/{book_id}/chapters/{chapter_id}?language=xx` - Get single chapter with full `content_html`

**🔄 Breaking Changes:**
- `POST /books/{book_id}/translate` default behavior changed:
  - Old: `translate_chapters=true` (translates all chapters immediately)
  - New: `translate_chapters=false` (metadata only, much faster)
  - **Migration:** Explicitly set `translate_chapters: true` for old behavior

**🎯 UX Improvements:**
- User selects language → Load translated book/chapters instantly
- Tiptap editor loads `content_html` in selected language
- No unnecessary re-translation of existing content
- Better separation between metadata and chapter translation

---

### Version 1.0.0 (2024-12-04) - Initial Release

**✨ Features:**
- Initial release of Book Translation API
- Support for 17 languages
- 5 core endpoints implemented
- Points-based pricing system (2 for metadata + 2 per chapter)
- HTML structure preservation
- AI-powered translation with Gemini 2.5 Pro

**📝 Endpoints:**
- `POST /books/{book_id}/translate` - Translate entire book
- `POST /books/{book_id}/chapters/{chapter_id}/translate` - Translate single chapter
- `POST /books/{book_id}/translate-background` - Translate with background options
- `GET /books/{book_id}/translations/languages` - List available languages
- `DELETE /books/{book_id}/translations/{language}` - Delete translation

---

## Support

For API issues or questions:
- Check server logs for detailed error messages
- Review Swagger UI documentation at `/docs`
- Contact backend team for integration support

**API Documentation:** http://localhost:8000/docs (Development)
**API Documentation:** https://api.wordai.pro/docs (Production)
