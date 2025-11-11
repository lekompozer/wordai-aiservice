# 📄 PDF SPLIT API DOCUMENTATION

## Endpoint Overview

**Endpoint:** `POST /api/documents/{document_id}/split`
**Authentication:** Required (Bearer Token)
**Purpose:** Split a PDF file into multiple parts (files), creating new entries in Upload Files

---

## 🔑 Key Features

- ✅ Split PDF into equal chunks (Auto mode)
- ✅ Split PDF with custom page ranges (Manual mode)
- ✅ Creates **new files** in `user_files` collection (visible in Upload Files)
- ✅ Upload to R2 storage: `uploads/{user_id}/{file_id}.pdf`
- ✅ Each split part can be converted with AI independently
- ✅ Optional: Keep or delete original file
- ✅ Backward compatible with old documents

---

## 📥 Request

### URL Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `document_id` | string | Yes | File ID or Document ID to split |

### Request Body

#### Mode: Auto (Equal Chunks)

```json
{
  "mode": "auto",
  "chunk_size": 10,
  "keep_original": true
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `mode` | string | Yes | - | `"auto"` for equal chunks |
| `chunk_size` | integer | No | 10 | Pages per chunk (1-10) |
| `keep_original` | boolean | No | true | Keep original file after split |

---

#### Mode: Manual (Custom Ranges)

```json
{
  "mode": "manual",
  "keep_original": true,
  "split_ranges": [
    {
      "title": "Chapter 1 - Introduction",
      "start_page": 1,
      "end_page": 10,
      "description": "Introduction section"
    },
    {
      "title": "Chapter 2 - Main Content",
      "start_page": 11,
      "end_page": 25,
      "description": "Core material"
    },
    {
      "title": "Chapter 3 - Conclusion",
      "start_page": 26,
      "end_page": 30,
      "description": "Final thoughts"
    }
  ]
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | Yes | `"manual"` for custom ranges |
| `keep_original` | boolean | No | Keep original file after split |
| `split_ranges` | array | Yes | Array of range objects (required for manual mode) |

**split_ranges Object:**

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `title` | string | Yes | 1-200 chars | Title for the split part (becomes filename) |
| `start_page` | integer | Yes | >= 1 | Starting page number (1-indexed) |
| `end_page` | integer | Yes | >= start_page | Ending page number (1-indexed) |
| `description` | string | No | - | Optional description for the file |

**Validation Rules:**
- `end_page` must be >= `start_page`
- Page numbers must not exceed total pages in PDF
- Ranges can overlap (no validation for gaps)

---

## 📤 Response

### Success Response (200 OK)

```json
{
  "success": true,
  "original_document_id": "file_abc123",
  "original_kept": true,
  "split_documents": [
    {
      "document_id": "file_abc123_part1",
      "title": "Document - Part 1.pdf",
      "pages": "1-10",
      "pages_count": 10,
      "r2_path": "uploads/user123/file_abc123_part1.pdf",
      "file_size_mb": 2.45,
      "created_at": "2025-11-11T10:30:00.000Z"
    },
    {
      "document_id": "file_abc123_part2",
      "title": "Document - Part 2.pdf",
      "pages": "11-20",
      "pages_count": 10,
      "r2_path": "uploads/user123/file_abc123_part2.pdf",
      "file_size_mb": 2.38,
      "created_at": "2025-11-11T10:30:01.000Z"
    },
    {
      "document_id": "file_abc123_part3",
      "title": "Document - Part 3.pdf",
      "pages": "21-25",
      "pages_count": 5,
      "r2_path": "uploads/user123/file_abc123_part3.pdf",
      "file_size_mb": 1.12,
      "created_at": "2025-11-11T10:30:02.000Z"
    }
  ],
  "total_parts": 3,
  "processing_time_seconds": 4.23
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Always `true` for successful requests |
| `original_document_id` | string | ID of the original file/document |
| `original_kept` | boolean | Whether original file was kept or deleted |
| `split_documents` | array | Array of created split parts |
| `total_parts` | integer | Number of parts created |
| `processing_time_seconds` | float | Time taken to process the split |

**split_documents Object:**

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | string | File ID of the split part (use this as `file_id`) |
| `title` | string | Filename of the split part |
| `pages` | string | Page range (e.g., "1-10") |
| `pages_count` | integer | Number of pages in this part |
| `r2_path` | string | R2 storage path |
| `file_size_mb` | float | File size in megabytes |
| `created_at` | string | ISO 8601 timestamp |

---

### Error Responses

#### 404 Not Found - File Not Found

```json
{
  "detail": "File not found"
}
```

**Причина:** File ID không tồn tại hoặc không thuộc về user

---

#### 400 Bad Request - Not a PDF

```json
{
  "detail": "Only PDF files can be split, got: .docx"
}
```

**Причина:** File không phải là PDF

---

#### 400 Bad Request - No R2 Path

```json
{
  "detail": "File does not have R2 storage path"
}
```

**Причина:** File chưa được upload lên R2

---

#### 400 Bad Request - Invalid Ranges

```json
{
  "detail": "Invalid split ranges: Page 50 exceeds total pages (30)"
}
```

**Причина:** Page range vượt quá số trang trong PDF

---

#### 500 Internal Server Error

```json
{
  "detail": "Split failed: [error message]"
}
```

**Причина:** Lỗi server khi xử lý split

---

## 🗂️ Database Changes

### Created in `user_files` Collection

Each split part creates a new document in `user_files`:

```javascript
{
  "file_id": "file_abc123_part1",
  "user_id": "user123",
  "filename": "Document - Part 1.pdf",
  "file_type": ".pdf",
  "file_size": 2567890,
  "r2_key": "uploads/user123/file_abc123_part1.pdf",
  "upload_date": ISODate("2025-11-11T10:30:00Z"),
  "last_modified": ISODate("2025-11-11T10:30:00Z"),

  // Split metadata
  "is_split_part": true,
  "original_file_id": "file_abc123",
  "split_info": {
    "start_page": 1,
    "end_page": 10,
    "part_number": 1,
    "total_parts": 3,
    "split_mode": "auto"  // or "manual"
  }
}
```

### Updated in Original File

Original file is updated with child references:

```javascript
{
  "file_id": "file_abc123",
  "child_file_ids": [
    "file_abc123_part1",
    "file_abc123_part2",
    "file_abc123_part3"
  ],
  "last_modified": ISODate("2025-11-11T10:30:02Z")
}
```

---

## 📊 Subscription Usage

**Counter Updated:** `files`
**Amount:** Number of split parts created

Example: Splitting into 3 parts will add +3 to user's file count.

---

## 🎯 Use Cases

### Use Case 1: Split Large PDF for AI Processing

**Scenario:** User has a 100-page PDF and wants to convert only specific chapters with AI

**Steps:**
1. Split PDF using manual mode with chapter ranges
2. Each part appears in Upload Files
3. Convert each part independently with `/api/documents/{file_id}/convert-with-ai`

**Benefits:**
- Save AI points by processing only needed sections
- Faster processing (smaller chunks)
- Better organization

---

### Use Case 2: Share Specific Pages

**Scenario:** User wants to share only pages 5-15 of a confidential document

**Steps:**
1. Split PDF using manual mode: `{"start_page": 5, "end_page": 15}`
2. Original file kept (confidential)
3. Share only the split part file

**Benefits:**
- No need to manually extract pages
- Split file is a separate, independent file
- Can be shared or converted separately

---

### Use Case 3: Organize Large Documents

**Scenario:** User has a 200-page report with multiple sections

**Steps:**
1. Split into equal 20-page chunks (auto mode)
2. Each chunk becomes a manageable file
3. Convert or process each chunk independently

**Benefits:**
- Better organization in Upload Files
- Easier to manage and navigate
- Can process in parallel

---

## 🔄 Workflow Integration

### Frontend Flow

```
User selects PDF in Upload Files
  ↓
Click "Split PDF" button
  ↓
Choose mode (Auto / Manual)
  ↓
[Auto] Set chunk_size
[Manual] Define ranges with titles
  ↓
POST /api/documents/{file_id}/split
  ↓
Response with split_documents array
  ↓
Display new files in Upload Files list
  ↓
User can convert each part with AI independently
```

---

## ⚠️ Important Notes

1. **File ID vs Document ID:**
   - Split creates **files** (`user_files`), not documents
   - Use returned `document_id` as `file_id` for subsequent operations

2. **R2 Storage Path:**
   - Split files: `uploads/{user_id}/{file_id}_part{N}.pdf`
   - Same folder as regular uploads

3. **Backward Compatibility:**
   - Endpoint accepts both `file_id` (new) and `document_id` (old)
   - Old documents in `documents` collection still work

4. **File Naming:**
   - **Auto mode:** `{original_name} - Part {N}.pdf`
   - **Manual mode:** `{title}.pdf` (no automatic suffix)

5. **Counter Updates:**
   - Split updates **files counter**, not documents counter
   - Each split part counts as 1 file

6. **Original File Deletion:**
   - If `keep_original: false`, original is deleted from database AND R2
   - Split parts remain independent

---

## 🧪 Testing Examples

### Test 1: Auto Split (Default)

```bash
curl -X POST "https://api.wordai.com/api/documents/file_test123/split" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "auto",
    "chunk_size": 10,
    "keep_original": true
  }'
```

**Expected:** 30-page PDF → 3 parts (10 pages each)

---

### Test 2: Manual Split with Custom Titles

```bash
curl -X POST "https://api.wordai.com/api/documents/file_test123/split" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "manual",
    "keep_original": false,
    "split_ranges": [
      {
        "title": "Executive Summary",
        "start_page": 1,
        "end_page": 5
      },
      {
        "title": "Financial Report",
        "start_page": 6,
        "end_page": 20,
        "description": "Q4 2024 financial data"
      }
    ]
  }'
```

**Expected:**
- 2 files created: `Executive Summary.pdf`, `Financial Report.pdf`
- Original file deleted

---

## 🔗 Related Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/simple-files/upload` | Upload PDF file first |
| `POST /api/documents/{file_id}/convert-with-ai` | Convert split part with AI |
| `GET /api/documents/{document_id}/preview-split` | Preview split suggestions |
| `GET /api/documents/{document_id}/split-info` | Get split metadata |
| `POST /api/documents/merge` | Merge split parts back together |

---

## 📝 Version History

- **v1.0** (2025-11-11): Initial release
  - Auto and Manual split modes
  - Creates files in `user_files` collection
  - R2 storage in `uploads/` folder
  - File counter updates

---

## 🆘 Support

For issues or questions, contact the development team or check the main API documentation.
