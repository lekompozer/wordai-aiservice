# StudyHub Content Management API - Technical Specifications

## Overview

Content Management APIs cho phép subject owners link các tài liệu từ hệ thống hiện tại (Documents, Tests, Books) hoặc upload files mới vào StudyHub modules. Tổng cộng **16 endpoints** được chia thành 4 nhóm chính.

**Base URL**: `/api/studyhub`

**Authentication**: Required - Firebase JWT token in `Authorization: Bearer {token}` header

**Permission**: Subject owner only (except GET endpoints có thể access bởi enrolled users)

---

## Content Types

| Type | Source Collection | Description |
|------|------------------|-------------|
| `document` | `online_documents` | Tài liệu A4/Slides/Notes đã tạo |
| `test` | `online_tests` | Bài kiểm tra đã tạo |
| `book` | `online_books` | Sách đã xuất bản |
| `file` | `studyhub_files` | Files upload (PDF, video, audio, images, etc.) |

---

## 1. DOCUMENT CONTENT APIs (4 endpoints)

### 1.1. Add Document to Module

**POST** `/modules/{module_id}/content/documents`

Link document từ My Documents vào StudyHub module.

**Path Parameters**:
- `module_id` (string, required) - Module ID

**Request Body**:
```json
{
  "document_id": "string",     // ID from online_documents (required)
  "title": "string",           // Display title (required, 1-200 chars)
  "is_required": false,        // Required for completion (optional, default: false)
  "is_preview": false          // Free preview content (optional, default: false)
}
```

**Response** `201 Created`:
```json
{
  "id": "695fe6c420bf18c2002f4acc",
  "module_id": "695fe6c420bf18c2002f4abb",
  "content_type": "document",
  "title": "Introduction to AI",
  "data": {
    "document_id": "doc_123456",
    "document_url": "/documents?id=doc_123456"
  },
  "is_required": false,
  "is_preview": false,
  "order_index": 1
}
```

**Error Responses**:
- `401 Unauthorized` - Missing or invalid authentication token
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Module or document not found
- `500 Internal Server Error` - Server error

**Side Effects**:
- Sets `studyhub_context.enabled = true` on document
- Sets `studyhub_context.subject_id` and `module_id`
- Auto-assigns `order_index` (last + 1)

---

### 1.2. Get Module Documents

**GET** `/modules/{module_id}/content/documents`

Lấy danh sách tất cả documents trong module.

**Path Parameters**:
- `module_id` (string, required) - Module ID

**Response** `200 OK`:
```json
{
  "contents": [
    {
      "id": "695fe6c420bf18c2002f4acc",
      "module_id": "695fe6c420bf18c2002f4abb",
      "title": "Introduction to AI",
      "data": {
        "document_id": "doc_123456",
        "document_url": "/documents?id=doc_123456"
      },
      "is_required": false,
      "is_preview": true,
      "order_index": 1,
      "document_details": {
        "title": "AI Fundamentals",
        "url": "/documents?id=doc_123456",
        "type": "slides",
        "created_at": "2026-01-08T10:00:00Z"
      }
    }
  ],
  "total": 1
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `404 Not Found` - Module not found

**Notes**:
- Results sorted by `order_index` ASC
- Includes enriched `document_details` from `online_documents`
- Accessible by subject owner OR enrolled users

---

### 1.3. Update Document Content

**PUT** `/content/documents/{content_id}`

Cập nhật settings của document content.

**Path Parameters**:
- `content_id` (string, required) - Content ID (not document_id)

**Request Body** (all fields optional):
```json
{
  "title": "string",           // Update display title (1-200 chars)
  "is_required": true,         // Update required flag
  "is_preview": false          // Update preview flag
}
```

**Response** `200 OK`:
```json
{
  "id": "695fe6c420bf18c2002f4acc",
  "title": "Updated Title",
  "is_required": true,
  "is_preview": false
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Content not found
- `422 Unprocessable Entity` - Validation error

**Side Effects**:
- If `is_preview` changed → updates `studyhub_context` on original document
- Không thay đổi `order_index`

---

### 1.4. Remove Document from Module

**DELETE** `/content/documents/{content_id}`

Unlink document khỏi module (không xóa document gốc).

**Path Parameters**:
- `content_id` (string, required) - Content ID

**Response** `200 OK`:
```json
{
  "success": true,
  "message": "Document removed from module"
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Content not found

**Side Effects**:
- Deletes content record from `studyhub_module_contents`
- Sets `studyhub_context.enabled = false` on original document
- Document vẫn tồn tại trong `online_documents`

---

## 2. TEST CONTENT APIs (4 endpoints)

### 2.1. Add Test to Module

**POST** `/modules/{module_id}/content/tests`

Link test từ My Tests vào StudyHub module.

**Path Parameters**:
- `module_id` (string, required) - Module ID

**Request Body**:
```json
{
  "test_id": "string",         // ID from online_tests (required)
  "title": "string",           // Display title (required, 1-200 chars)
  "passing_score": 70,         // Minimum score to pass (optional, 0-100, default: 70)
  "is_required": false,        // Required for completion (optional, default: false)
  "is_preview": false          // Free preview (optional, default: false)
}
```

**Response** `201 Created`:
```json
{
  "id": "695fe6c420bf18c2002f4acd",
  "module_id": "695fe6c420bf18c2002f4abb",
  "content_type": "test",
  "title": "AI Quiz Chapter 1",
  "data": {
    "test_id": "test_123456",
    "passing_score": 70
  },
  "is_required": true,
  "is_preview": false,
  "order_index": 2
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Module or test not found
- `422 Unprocessable Entity` - Invalid passing_score (must be 0-100)

**Notes**:
- `passing_score` determines minimum score để pass module
- Test phải thuộc về user (checked via `owner_id`)

---

### 2.2. Get Module Tests

**GET** `/modules/{module_id}/content/tests`

Lấy danh sách tất cả tests trong module.

**Path Parameters**:
- `module_id` (string, required) - Module ID

**Response** `200 OK`:
```json
{
  "contents": [
    {
      "id": "695fe6c420bf18c2002f4acd",
      "module_id": "695fe6c420bf18c2002f4abb",
      "title": "AI Quiz Chapter 1",
      "data": {
        "test_id": "test_123456",
        "passing_score": 70
      },
      "is_required": true,
      "is_preview": false,
      "order_index": 2,
      "test_details": {
        "title": "AI Fundamentals Quiz",
        "total_questions": 20,
        "time_limit": 1800,
        "created_at": "2026-01-07T15:30:00Z"
      }
    }
  ],
  "total": 1
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `404 Not Found` - Module not found

---

### 2.3. Update Test Content

**PUT** `/content/tests/{content_id}`

Cập nhật settings của test content.

**Path Parameters**:
- `content_id` (string, required) - Content ID

**Request Body** (all fields optional):
```json
{
  "title": "string",           // Update display title (1-200 chars)
  "passing_score": 80,         // Update passing score (0-100)
  "is_required": true,         // Update required flag
  "is_preview": false          // Update preview flag
}
```

**Response** `200 OK`:
```json
{
  "id": "695fe6c420bf18c2002f4acd",
  "title": "Updated Quiz Title",
  "data": {
    "test_id": "test_123456",
    "passing_score": 80
  },
  "is_required": true,
  "is_preview": false
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Content not found
- `422 Unprocessable Entity` - Invalid passing_score

**Side Effects**:
- Updates `data.passing_score` nếu provided
- Updates `studyhub_context` if `is_preview` changed

---

### 2.4. Remove Test from Module

**DELETE** `/content/tests/{content_id}`

Unlink test khỏi module (không xóa test gốc).

**Path Parameters**:
- `content_id` (string, required) - Content ID

**Response** `200 OK`:
```json
{
  "success": true,
  "message": "Test removed from module"
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Content not found

**Side Effects**:
- Deletes content record
- Sets `studyhub_context.enabled = false` on test
- Test vẫn tồn tại trong `online_tests`

---

## 3. BOOK CONTENT APIs (4 endpoints)

### 3.1. Add Book to Module

**POST** `/modules/{module_id}/content/books`

Link book từ My Books vào StudyHub module.

**Path Parameters**:
- `module_id` (string, required) - Module ID

**Request Body**:
```json
{
  "book_id": "string",                // ID from online_books (required)
  "title": "string",                  // Display title (required, 1-200 chars)
  "selected_chapters": ["ch1", "ch2"], // Optional: specific chapters only
  "is_required": false,               // Required for completion (optional, default: false)
  "is_preview": false                 // Free preview (optional, default: false)
}
```

**Response** `201 Created`:
```json
{
  "id": "695fe6c420bf18c2002f4ace",
  "module_id": "695fe6c420bf18c2002f4abb",
  "content_type": "book",
  "title": "Machine Learning Basics",
  "data": {
    "book_id": "book_123456",
    "selected_chapters": ["chapter1", "chapter2"]
  },
  "is_required": false,
  "is_preview": true,
  "order_index": 3
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Module or book not found

**Notes**:
- `selected_chapters` rỗng = all chapters
- Chapters phải tồn tại trong book (không validate ngay, check khi access)

---

### 3.2. Get Module Books

**GET** `/modules/{module_id}/content/books`

Lấy danh sách tất cả books trong module.

**Path Parameters**:
- `module_id` (string, required) - Module ID

**Response** `200 OK`:
```json
{
  "contents": [
    {
      "id": "695fe6c420bf18c2002f4ace",
      "module_id": "695fe6c420bf18c2002f4abb",
      "title": "Machine Learning Basics",
      "data": {
        "book_id": "book_123456",
        "selected_chapters": ["chapter1", "chapter2"]
      },
      "is_required": false,
      "is_preview": true,
      "order_index": 3,
      "book_details": {
        "title": "ML for Beginners",
        "total_chapters": 10,
        "cover_url": "https://cdn.wordai.pro/books/cover_123.jpg",
        "created_at": "2025-12-15T08:00:00Z"
      }
    }
  ],
  "total": 1
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `404 Not Found` - Module not found

---

### 3.3. Update Book Content

**PUT** `/content/books/{content_id}`

Cập nhật settings của book content.

**Path Parameters**:
- `content_id` (string, required) - Content ID

**Request Body** (all fields optional):
```json
{
  "title": "string",                  // Update display title (1-200 chars)
  "selected_chapters": ["ch1", "ch3"], // Update chapter selection
  "is_required": true,                // Update required flag
  "is_preview": false                 // Update preview flag
}
```

**Response** `200 OK`:
```json
{
  "id": "695fe6c420bf18c2002f4ace",
  "title": "Updated Book Title",
  "data": {
    "book_id": "book_123456",
    "selected_chapters": ["chapter1", "chapter3"]
  },
  "is_required": true,
  "is_preview": false
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Content not found
- `422 Unprocessable Entity` - Validation error

**Side Effects**:
- Updates `data.selected_chapters` nếu provided
- Updates `studyhub_context` if `is_preview` changed

---

### 3.4. Remove Book from Module

**DELETE** `/content/books/{content_id}`

Unlink book khỏi module (không xóa book gốc).

**Path Parameters**:
- `content_id` (string, required) - Content ID

**Response** `200 OK`:
```json
{
  "success": true,
  "message": "Book removed from module"
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Content not found

**Side Effects**:
- Deletes content record
- Sets `studyhub_context.enabled = false` on book
- Book vẫn tồn tại trong `online_books`

---

## 4. FILE CONTENT APIs (4 endpoints)

### 4.1. Link Existing File to Module

**POST** `/modules/{module_id}/content/files/existing`

Link file đã upload từ My Files vào StudyHub module.

**Path Parameters**:
- `module_id` (string, required) - Module ID

**Request Body**:
```json
{
  "file_id": "string",         // ID from studyhub_files (required)
  "title": "string",           // Display title (required, 1-200 chars)
  "is_required": false,        // Required for completion (optional, default: false)
  "is_preview": false          // Free preview (optional, default: false)
}
```

**Response** `201 Created`:
```json
{
  "id": "695fe6c420bf18c2002f4acf",
  "module_id": "695fe6c420bf18c2002f4abb",
  "content_type": "file",
  "title": "Chapter 1 Lecture Video",
  "data": {
    "file_id": "file_123456",
    "file_url": "https://cdn.wordai.pro/studyhub/files/file_123456.mp4",
    "file_name": "lecture_ch1.mp4",
    "file_type": "video/mp4",
    "file_size": 45678901
  },
  "is_required": true,
  "is_preview": false,
  "order_index": 4
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner or file doesn't belong to user
- `404 Not Found` - Module or file not found
- `409 Conflict` - File already linked to this module

**Side Effects**:
- Sets `studyhub_context.enabled = true` on file
- Sets `studyhub_context.subject_id` and `module_id`
- Auto-assigns `order_index` (last + 1)

**Notes**:
- File phải thuộc về user (`uploaded_by` check)
- File không được đánh dấu deleted
- Có thể link same file vào multiple modules của cùng subject

---

### 4.2. Upload File to Module

**POST** `/modules/{module_id}/content/files`

Upload file mới vào StudyHub module (PDF, videos, audio, images, etc.).

**Path Parameters**:
- `module_id` (string, required) - Module ID

**Request Body** (`multipart/form-data`):
- `file` (file, required) - File to upload
- `title` (string, required) - Display title (1-200 chars)
- `description` (string, optional) - File description
- `is_required` (boolean, optional) - Required for completion (default: false)
- `is_preview` (boolean, optional) - Free preview (default: false)

**Supported File Types**:
- Documents: `.pdf`, `.docx`, `.pptx`, `.xlsx`
- Videos: `.mp4`, `.webm`, `.mov`, `.avi`
- Audio: `.mp3`, `.wav`, `.m4a`, `.ogg`
- Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`
- Archives: `.zip`, `.rar`

**Max File Size**: 500 MB

**Response** `201 Created`:
```json
{
  "id": "695fe6c420bf18c2002f4acf",
  "module_id": "695fe6c420bf18c2002f4abb",
  "content_type": "file",
  "title": "Chapter 1 Lecture Video",
  "data": {
    "file_id": "file_123456",
    "file_url": "https://cdn.wordai.pro/studyhub/files/file_123456.mp4",
    "file_name": "lecture_ch1.mp4",
    "file_type": "video/mp4",
    "file_size": 45678901,
    "description": "Introduction to Machine Learning"
  },
  "is_required": true,
  "is_preview": false,
  "order_index": 4
}
```

**Error Responses**:
- `400 Bad Request` - Invalid file type or size exceeds limit
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Module not found
- `413 Payload Too Large` - File size > 500 MB
- `500 Internal Server Error` - Upload failed

**Upload Process**:
1. Validates file type and size
2. Uploads to CDN/R2 storage
3. Creates record in `studyhub_files` collection
4. Creates content link in `studyhub_module_contents`
5. Returns URL for immediate access

**Notes**:
- Files are uploaded to Cloudflare R2 storage
- URL format: `https://cdn.wordai.pro/studyhub/files/{file_id}.{ext}`
- Files persist even if removed from module (soft delete)
- Virus scanning performed on upload

---

### 4.3. Get Module Files

**GET** `/modules/{module_id}/content/files`

Lấy danh sách tất cả files trong module.

**Path Parameters**:
- `module_id` (string, required) - Module ID

**Response** `200 OK`:
```json
{
  "contents": [
    {
      "id": "695fe6c420bf18c2002f4acf",
      "module_id": "695fe6c420bf18c2002f4abb",
      "title": "Chapter 1 Lecture Video",
      "data": {
        "file_id": "file_123456",
        "file_url": "https://cdn.wordai.pro/studyhub/files/file_123456.mp4",
        "file_name": "lecture_ch1.mp4",
        "file_type": "video/mp4",
        "file_size": 45678901,
        "description": "Introduction to Machine Learning"
      },
      "is_required": true,
      "is_preview": false,
      "order_index": 4,
      "file_details": {
        "uploaded_at": "2026-01-09T10:30:00Z",
        "uploaded_by": "user_123",
        "download_count": 25,
        "duration": 1845,  // Video duration in seconds (if applicable)
        "thumbnail_url": "https://cdn.wordai.pro/studyhub/files/file_123456_thumb.jpg"
      }
    }
  ],
  "total": 1
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `404 Not Found` - Module not found

**Notes**:
- Results sorted by `order_index` ASC
- `file_details` includes metadata from `studyhub_files`
- Video files include `duration` and `thumbnail_url`
- `file_size` in bytes

---

### 4.4. Remove File from Module

**DELETE** `/content/files/{content_id}`

Unlink file khỏi module (soft delete - file vẫn tồn tại trong storage).

**Path Parameters**:
- `content_id` (string, required) - Content ID

**Response** `200 OK`:
```json
{
  "success": true,
  "message": "File removed from module"
}
```

**Error Responses**:
- `401 Unauthorized` - Missing authentication
- `403 Forbidden` - Not subject owner
- `404 Not Found` - Content not found

**Side Effects**:
- Deletes content record from `studyhub_module_contents`
- Marks file as `deleted = true` in `studyhub_files` (soft delete)
- File URL vẫn accessible nếu có direct link (cho đến khi cleanup job chạy)
- Permanent deletion sau 30 days (automated cleanup)

**Notes**:
- Không có Update File endpoint (phải delete + re-upload)
- Để update title/description, update content record:
  ```
  PUT /api/studyhub/content/{content_id}
  Body: { title: "New Title" }
  ```

---

## Common Patterns

### Authentication
Tất cả endpoints yêu cầu Firebase JWT token:
```
Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6ImQ4Mjg5...
```

### Permission Check
- **POST/PUT/DELETE**: Chỉ subject owner
- **GET**: Subject owner HOẶC enrolled users

### Error Response Format
```json
{
  "detail": "Error message description"
}
```

### Order Index
- Auto-assigned khi add content (last + 1)
- Không thay đổi khi update
- Dùng Module reorder API để sắp xếp lại

---

## StudyHub Context

Khi link content vào module, field `studyhub_context` được thêm vào document/test/book gốc:

```json
{
  "studyhub_context": {
    "enabled": true,
    "mode": "private",              // "private" hoặc "marketplace"
    "subject_id": "ObjectId",
    "module_id": "ObjectId",
    "requires_enrollment": true,    // !is_preview
    "is_preview": false
  }
}
```

**Mode changes**:
- Khi subject ở private → `mode = "private"`
- Khi publish to marketplace → `mode = "marketplace"`
- Khi unlink → `studyhub_context` bị xóa

---

## Frontend Integration Notes

### 1. Listing User's Content
Trước khi add content, frontend cần list available documents/tests/books:
- Documents: `GET /api/documents` (existing API)
- Tests: `GET /api/tests` (existing API)
- Books: `GET /api/books` (existing API)

Filter by `owner_id = current_user` và `studyhub_context.enabled != true` (chưa được dùng)

**For Files**:
- List available: `GET /api/studyhub/files` (user's uploaded files)
- Filter: `uploaded_by = current_user` và `deleted != true`
- Or upload new: `POST /modules/{module_id}/content/files` (direct upload)

### 2. Content Display
GET endpoints trả về `*_details` object chứa thông tin từ collection gốc. Dùng để display preview không cần call thêm API.

### 3. Preview vs Required
- `is_preview = true` → Free access cho all users (marketing)
- `is_required = true` → Phải complete để hoàn thành module
- Có thể combine: preview + required

### 4. Reordering Content
Dùng existing Module reorder API:
```
POST /api/studyhub/modules/{module_id}/reorder
Body: { new_order: [content_id1, content_id2, ...] }
```

### 5. Multi-Type Listing
Để get ALL content types trong 1 module:
```
GET /api/studyhub/modules/{module_id}/content
```
(Existing API - returns all types mixed)

---

## Validation Rules

### Title
- Required, 1-200 characters
- Cho phép unicode (Vietnamese)

### Passing Score (Tests only)
- Integer, 0-100
- Represents percentage

### Selected Chapters (Books only)
- Array of strings
- Empty array = all chapters
- Không validate chapters exist (check runtime)

### Content IDs
- Must be valid MongoDB ObjectId format (24 hex chars)
- Must exist in respective collection
- Must belong to user (`owner_id` check)

### File Upload (Files only)
- Max size: 500 MB
- Allowed extensions: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.mp4`, `.webm`, `.mov`, `.avi`, `.mp3`, `.wav`, `.m4a`, `.ogg`, `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.zip`, `.rar`
- Virus scanning performed automatically
- Uploaded to Cloudflare R2 CDN

---

## Rate Limiting

Content Management APIs share rate limit với StudyHub APIs:
- **Authenticated**: 100 requests / minute
- **Burst**: 20 requests / second

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.2 | 2026-01-09 | Added Link Existing File endpoint (16 total) |
| 1.1 | 2026-01-09 | Added Files APIs (Upload/Get/Delete) |
| 1.0 | 2026-01-09 | Initial release - 12 endpoints (Documents/Tests/Books) |

---

## Support

**API Documentation**: `https://api.wordai.pro/docs`

**Questions**: Contact backend team

---

**Document Version**: 1.2
**Last Updated**: January 9, 2026
**Total Endpoints**: 16 (Documents: 4, Tests: 4, Books: 4, Files: 4)
**Authentication**: Firebase JWT Required
**Permission Model**: Owner-based + Enrollment-based
