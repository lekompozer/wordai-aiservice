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
- Single chapter: ~10-30 seconds depending on length
- Full book: 2-5 minutes for average book with 10-20 chapters

### Recommendations
- Implement progress tracking for full book translations
- Consider background job processing for large books
- Add translation status field to track in-progress translations
- Implement webhooks or polling for completion notifications

---

## Future Enhancements

### Planned Features
1. **Batch Translation**: Translate multiple books at once
2. **Translation History**: Track all translation operations
3. **Translation Quality Scoring**: User ratings for translations
4. **Custom Glossary**: User-defined term translations
5. **Translation Memory**: Reuse previous translations for consistency
6. **Auto-Translation**: Automatic translation on book creation
7. **Language Detection**: Automatically detect source language
8. **Partial Retranslation**: Re-translate specific paragraphs

### API Extensions
1. `GET /api/v1/books/{book_id}/translation-status` - Check translation progress
2. `POST /api/v1/books/{book_id}/retranslate` - Force retranslation
3. `GET /api/v1/translations/history` - View user's translation history
4. `POST /api/v1/translations/batch` - Batch translate multiple items

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

### Version 1.0.0 (2024-12-04)
- Initial release of Book Translation API
- Support for 17 languages
- 5 core endpoints implemented
- Points-based pricing system
- HTML structure preservation
- AI-powered translation with Gemini 2.5 Pro

---

## Support

For API issues or questions:
- Check server logs for detailed error messages
- Review Swagger UI documentation at `/docs`
- Contact backend team for integration support

**API Documentation:** http://localhost:8000/docs (Development)
**API Documentation:** https://api.wordai.pro/docs (Production)
