# Slide Version Management - API Specs for Frontend

## ⚠️ IMPORTANT: SLIDE DOCUMENTS ONLY

**Các tính năng version management chỉ áp dụng cho:**
- ✅ **Document type: `slide`** (presentations)

**KHÔNG áp dụng cho:**
- ❌ Document type: `doc` (A4 documents)
- ❌ Document type: `note` (Notes)

**Lý do:** A4 và Notes documents chưa được implement các endpoint liên quan đến version, language, hay subtitle. Chỉ slide documents mới có đầy đủ tính năng này.

---

## Overview

All **SLIDE document** endpoints now support **optional `version` parameter** for working with historical versions. If `version` is not provided, the latest version is used automatically.

**Key Concepts:**
- ✅ All **SLIDE** endpoints (GET/PUT/AI/Download/Subtitle/Audio) support version parameter
- ✅ Version parameter is **optional** - defaults to latest version
- ✅ Version switching is **FREE** (no points cost)
- ✅ AI operations on historical versions create new snapshots
- ✅ Version history is **automatic** - saved before edits and AI regenerations
- ⚠️ **Only for `document_type: "slide"`** - A4/Notes documents not supported

---

## 1. Outline Management Endpoints

**⚠️ SLIDE DOCUMENTS ONLY** - These endpoints only work with `document_type: "slide"`

### 1.1 GET /api/slides/outline - View Current Outline

Get the current slide outline for a **slide document**.

**Request:**
```http
GET /api/slides/outline?document_id={document_id}&version={version}
Authorization: Bearer {firebase_token}
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `document_id` | string | ✅ Yes | Document ID |
| `version` | integer | ❌ Optional | Specific version number (default: latest) |

**Response (200 OK):**
```json
{
  "success": true,
  "document_id": "doc_abc123",
  "version": 3,
  "slide_count": 25,
  "slides_outline": [
    {
      "slide_index": 0,
      "slide_type": "title",
      "title": "Presentation Title",
      "subtitle": "Subtitle text",
      "bullets": null,
      "notes": "Speaker notes",
      "image_url": null,
      "keywords": ["intro", "welcome"]
    },
    {
      "slide_index": 1,
      "slide_type": "content",
      "title": "Main Topic",
      "subtitle": null,
      "bullets": ["Point 1", "Point 2", "Point 3"],
      "notes": "Detailed explanation",
      "image_url": "https://...",
      "keywords": ["topic", "content"]
    }
  ]
}
```

**Use Cases:**
- Display outline in sidebar for editing
- Preview historical version's structure
- Compare outlines across versions

---

### 1.2 PUT /api/slides/outline - Update Full Outline

Update the entire slide outline (all slides).

**⚠️ Important:** Creates a version snapshot BEFORE applying changes.

**Request:**
```http
PUT /api/slides/outline
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "document_id": "doc_abc123",
  "slides_outline": [
    {
      "slide_index": 0,
      "slide_type": "title",
      "title": "Updated Title",
      "subtitle": "New subtitle",
      "bullets": null,
      "notes": "Updated notes",
      "image_url": null,
      "keywords": ["updated"]
    },
    {
      "slide_index": 1,
      "slide_type": "content",
      "title": "Content Slide",
      "subtitle": null,
      "bullets": ["Bullet 1", "Bullet 2"],
      "notes": "Content notes",
      "image_url": null,
      "keywords": ["content"]
    }
  ],
  "change_description": "Manual outline update"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Outline updated successfully",
  "document_id": "doc_abc123",
  "updated_slides": 25,
  "new_version": 4,
  "can_regenerate": true
}
```

**Field Details:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `document_id` | string | ✅ Yes | Document ID |
| `slides_outline` | array | ✅ Yes | Complete array of slide outlines |
| `change_description` | string | ❌ Optional | Description of changes (default: "Manual outline update") |

---

### 1.3 POST /api/slides/outline/add - Add Single Slide

Insert a new slide at a specific position.

**Request:**
```http
POST /api/slides/outline/add
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "document_id": "doc_abc123",
  "insert_after_index": 5,
  "new_slide": {
    "slide_index": 6,
    "slide_type": "content",
    "title": "New Slide Title",
    "subtitle": null,
    "bullets": ["New point 1", "New point 2"],
    "notes": "Speaker notes for new slide",
    "image_url": null,
    "keywords": ["new", "inserted"]
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Slide added successfully",
  "new_slide_index": 6,
  "total_slides": 26
}
```

**Behavior:**
- Inserts slide at position `insert_after_index + 1`
- Automatically reindexes subsequent slides
- Saves version snapshot before insertion

---

### 1.4 DELETE /api/slides/outline/slide - Delete Single Slide

Remove a slide from the outline.

**Request:**
```http
DELETE /api/slides/outline/slide
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "document_id": "doc_abc123",
  "slide_index": 10,
  "reason": "Duplicate content"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Slide deleted successfully",
  "deleted_index": 10,
  "remaining_slides": 24
}
```

**Behavior:**
- Removes slide at specified index
- Automatically reindexes remaining slides
- Saves version snapshot before deletion

---

## 2. Version Management Endpoints

### 2.1 GET /api/slides/versions - View Version History

Retrieve all historical versions of a document.

**Request:**
```http
GET /api/slides/versions?document_id={document_id}
Authorization: Bearer {firebase_token}
```

**Response (200 OK):**
```json
{
  "success": true,
  "document_id": "doc_abc123",
  "current_version": 5,
  "versions": [
    {
      "version": 5,
      "created_at": "2025-12-26T10:30:00Z",
      "description": "AI formatting batch (12 slides)",
      "slide_count": 25,
      "is_current": true
    },
    {
      "version": 4,
      "created_at": "2025-12-26T09:15:00Z",
      "description": "Manual outline update",
      "slide_count": 25,
      "is_current": false
    },
    {
      "version": 3,
      "created_at": "2025-12-25T18:00:00Z",
      "description": "Before adding slide at position 10",
      "slide_count": 24,
      "is_current": false
    },
    {
      "version": 2,
      "created_at": "2025-12-25T16:45:00Z",
      "description": "Before deleting slide 15",
      "slide_count": 25,
      "is_current": false
    },
    {
      "version": 1,
      "created_at": "2025-12-25T15:00:00Z",
      "description": "Initial version",
      "slide_count": 26,
      "is_current": false
    }
  ]
}
```

**Use Cases:**
- Display version timeline in UI
- Allow user to browse historical versions
- Show what changed in each version

---

### 2.2 POST /api/slides/versions/switch - Restore to Previous Version

Switch to a previous version (restores content, outline, backgrounds, elements).

**💰 Cost:** FREE (no points deducted)

**Request:**
```http
POST /api/slides/versions/switch
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "document_id": "doc_abc123",
  "target_version": 3
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Switched to version 3",
  "document_id": "doc_abc123",
  "restored_version": 3,
  "slide_count": 24
}
```

**Behavior:**
- Restores `content_html`, `slides_outline`, `slide_backgrounds`, `slide_elements`
- Updates `last_saved_at` timestamp
- Does NOT create a new version (direct restoration)
- FREE operation (no points cost)

---

## 3. Document Viewing & Editing Endpoints

**⚠️ Version parameter ONLY for SLIDE documents** - `document_type: "slide"` only

### 3.1 GET /api/documents/{document_id} - Get Document

Retrieve document content (supports version parameter **for slides only**).

**Request:**
```http
GET /api/documents/{document_id}?version={version}
Authorization: Bearer {firebase_token}
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `version` | integer | ❌ Optional | Specific version number (default: latest) **- SLIDE documents only** |

**Response (200 OK):**
```json
{
  "document_id": "doc_abc123",
  "title": "My Presentation",
  "document_type": "slide",
  "version": 3,
  "content_html": "<div class=\"slide-page\">...</div>",
  "slides_outline": [...],
  "slide_backgrounds": [...],
  "slide_elements": [...],
  "slide_count": 25,
  "created_at": "2025-12-25T15:00:00Z",
  "updated_at": "2025-12-26T10:30:00Z",
  "last_saved_at": "2025-12-26T10:30:00Z",
  "is_version_snapshot": false,
  "version_description": ""
}
```

**When version is specified:**
- Returns reconstructed document from `version_history`
- `is_version_snapshot: true` indicates historical version
- `version_description` contains snapshot description

---

### 3.2 PUT /api/documents/{document_id} - Update Document

Update document content (auto-saves version snapshot).

**Request:**
```http
PUT /api/documents/{document_id}
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "content_html": "<div class=\"slide-page\">...</div>",
  "slides_outline": [...],
  "slide_backgrounds": [...],
  "slide_elements": [...],
  "is_auto_save": false
}
```

**Behavior:**
- Automatically saves version snapshot before update
- Increments version number
- Description: "Manual edit" or "Auto-save"

---

## 4. AI Processing Endpoints

**⚠️ SLIDE DOCUMENTS ONLY** - AI formatting/editing only for `document_type: "slide"`

### 4.1 POST /api/slides/ai-format - AI Formatting (Async)

Format **slide documents** with AI to improve layout, typography, and visual hierarchy.

**💰 Cost:**
- Single slide (Mode 1): 2 points
- Batch slides (Mode 2/3): 5 points per chunk (max 12 slides/chunk)

**Request:**
```http
POST /api/slides/ai-format?version={version}
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `version` | integer | ❌ Optional | Version to format (default: latest) **- SLIDE documents only** |
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `version` | integer | ❌ Optional | Version to format (default: latest) |

**Request Body - Mode 1 (Single Slide):**
```json
{
  "slide_index": 5,
  "current_html": "<div>...</div>",
  "elements": [],
  "background": null,
  "format_type": "format",
  "user_instruction": "Make it more modern"
}
```

**Request Body - Mode 3 (All Slides):**
```json
{
  "process_all_slides": true,
  "slides_data": [
    {
      "slide_index": 0,
      "current_html": "<div>...</div>",
      "elements": [],
      "background": null
    },
    {
      "slide_index": 1,
      "current_html": "<div>...</div>",
      "elements": [],
      "background": null
    }
  ],
  "format_type": "format"
}
```

**Field Details:**
| Field | Type | Description |
|-------|------|-------------|
| `format_type` | string | `"format"` = layout optimization (5 pts/chunk), `"edit"` = content rewrite (2 pts/slide) |
| `slides_data` | array | Array of slides to process (Mode 2/3) |
| `process_all_slides` | boolean | `true` = process entire document (Mode 3) |
| `user_instruction` | string | Optional user instruction for AI |

**Response (200 OK):**
```json
{
  "success": true,
  "job_id": "uuid-job-123",
  "message": "Formatting job queued",
  "is_batch": true,
  "total_slides": 25,
  "chunks": 3,
  "points_deducted": 15,
  "estimated_time_seconds": 120
}
```

**Poll for status at:** `GET /api/slides/jobs/{job_id}`

**Behavior:**
- Creates version snapshot BEFORE formatting
- Processes slides in chunks (max 12/chunk)
- Returns job_id for async polling
- Points deducted upfront

---

### 4.2 POST /api/slides/ai-format (Edit Mode)

Same endpoint but with `format_type: "edit"` for content rewriting.

**💰 Cost:** 2 points per slide (not per chunk)

**Request Body:**
```json
{
  "slide_index": 5,
  "current_html": "<div>...</div>",
  "elements": [],
  "background": null,
  "format_type": "edit",
  "user_instruction": "Simplify the language"
}
```

**Points Calculation:**
- Single slide: 2 points
- Multiple slides: 2 points × number of slides

---

## 5. Export/Download Endpoints

### 5.1 GET /api/documents/{document_id}/download/{format}

Download document in specified format (PDF, DOCX, TXT, HTML).

**Request:**
```http
GET /api/documents/{document_id}/download/{format}?version={version}&document_type={type}
Authorization: Bearer {firebase_token}
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `version` | integer | ❌ Optional | Version to download (default: latest) |
| `document_type` | string | ❌ Optional | `"slide"` or `"doc"` (auto-detected if not provided) |

**Supported Formats:**
- `pdf` - PDF document
- `docx` - Word document
- `txt` - Plain text
- `html` - HTML file

**Response (200 OK):**
```json
{
  "download_url": "https://r2.wordai.pro/exports/My_Document_20251226_153045.pdf",
  "filename": "My_Document_20251226_153045.pdf",
  "file_size": 123456,
  "format": "pdf",
  "expires_in": 3600,
  "expires_at": "2025-12-26T16:30:45Z"
}
```

**Frontend Usage:**
```javascript
window.open(response.download_url, '_blank');
```

---

## 6. Subtitle & Audio Endpoints

**⚠️ SLIDE DOCUMENTS ONLY** - Subtitles and audio generation only for `document_type: "slide"`

A4 và Notes documents không hỗ trợ subtitle/audio features.

### 6.1 POST /api/presentations/{presentation_id}/subtitles/v2

Generate subtitles for a specific language.

**💰 Cost:** 2 points

**Request:**
```http
POST /api/presentations/{presentation_id}/subtitles/v2?version={version}
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `version` | integer | ❌ Optional | Version to generate subtitles for (default: latest) **- SLIDE only** |

**Request Body:**
```json
{
  "language": "vi",
  "mode": "simple",
  "user_query": "Focus on technical aspects"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "subtitle": {
    "subtitle_id": "sub_123",
    "presentation_id": "doc_abc123",
    "version": 1,
    "language": "vi",
    "mode": "simple",
    "slides": [
      {
        "slide_index": 0,
        "script": "Xin chào, đây là slide giới thiệu...",
        "duration_seconds": 15
      }
    ],
    "created_at": "2025-12-26T10:00:00Z"
  },
  "points_deducted": 2
}
```

---

### 6.2 GET /api/presentations/{presentation_id}/subtitles/v2

List all subtitles for a presentation.

**Request:**
```http
GET /api/presentations/{presentation_id}/subtitles/v2
Authorization: Bearer {firebase_token}
```

**Response (200 OK):**
```json
{
  "success": true,
  "subtitles": [
    {
      "subtitle_id": "sub_123",
      "language": "vi",
      "version": 1,
      "mode": "simple",
      "created_at": "2025-12-26T10:00:00Z"
    },
    {
      "subtitle_id": "sub_456",
      "language": "en",
      "version": 2,
      "mode": "detailed",
      "created_at": "2025-12-26T11:00:00Z"
    }
  ]
}
```

---

### 6.3 POST /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}/audio

Generate audio from subtitles.

**💰 Cost:** 2 points

**Request:**
```http
POST /api/presentations/{presentation_id}/subtitles/v2/{subtitle_id}/audio
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "voice_config": {
    "voice_id": "vi-VN-Standard-A",
    "speed": 1.0,
    "pitch": 0.0
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "audio": {
    "audio_id": "audio_789",
    "subtitle_id": "sub_123",
    "voice_config": {...},
    "audio_files": [
      {
        "slide_index": 0,
        "audio_url": "https://r2.wordai.pro/audio/slide_0.mp3",
        "duration_seconds": 15
      }
    ],
    "created_at": "2025-12-26T12:00:00Z"
  },
  "points_deducted": 2
}
```

---

## 7. Version Parameter Behavior Summary

### 7.1 When version IS provided:

**GET endpoints:**
- Retrieve historical data from `version_history` array
- Return reconstructed document/outline from snapshot
- `is_version_snapshot: true` in response

**AI/Processing endpoints:**
- Operate on historical version data
- Create NEW version snapshot after processing
- User can preview old version before regenerating

**Download endpoints:**
- Export historical version as PDF/DOCX/etc
- Useful for comparing different versions

### 7.2 When version NOT provided (default):

- All endpoints use **latest/current version**
- Standard behavior (backward compatible)
- Most common use case

---

## 8. Common Integration Patterns

### 8.1 Display Version Timeline

```javascript
// Fetch version history
const response = await fetch(
  `/api/slides/versions?document_id=${docId}`,
  { headers: { Authorization: `Bearer ${token}` } }
);
const { versions, current_version } = await response.json();

// Display in UI
versions.forEach(v => {
  console.log(`Version ${v.version}: ${v.description} (${v.created_at})`);
});
```

### 8.2 Preview Historical Version

```javascript
// Get specific version
const response = await fetch(
  `/api/documents/${docId}?version=3`,
  { headers: { Authorization: `Bearer ${token}` } }
);
const document = await response.json();

// Check if historical
if (document.is_version_snapshot) {
  console.log('Viewing historical version:', document.version);
  console.log('Description:', document.version_description);
}
```

### 8.3 Restore Previous Version

```javascript
// Switch to version 3
const response = await fetch(
  `/api/slides/versions/switch`,
  {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      document_id: docId,
      target_version: 3
    })
  }
);

// FREE - no points deducted
const result = await response.json();
console.log('Restored to version:', result.restored_version);
```

### 8.4 Format Specific Version

```javascript
// Format version 3 instead of current
const response = await fetch(
  `/api/slides/ai-format?version=3`,
  {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      process_all_slides: true,
      slides_data: [...],
      format_type: 'format'
    })
  }
);

// This will create NEW version based on version 3
const { job_id } = await response.json();
```

### 8.5 Download Historical Version

```javascript
// Download version 3 as PDF
const response = await fetch(
  `/api/documents/${docId}/download/pdf?version=3`,
  { headers: { Authorization: `Bearer ${token}` } }
);

const { download_url } = await response.json();
window.open(download_url, '_blank');
```

---

## 9. Error Handling

### 9.1 Version Not Found (404)

```json
{
  "detail": "Version 10 not found"
}
```

**Cause:** Requested version doesn't exist in version_history

### 9.2 Document Not Found (404)

```json
{
  "detail": "Document not found"
}
```

**Cause:** Invalid document_id or user doesn't have access

### 9.3 Insufficient Points (402)

```json
{
  "detail": {
    "error": "INSUFFICIENT_POINTS",
    "message": "Không đủ điểm để format 25 slide(s). Cần: 15, Còn: 5",
    "points_needed": 15,
    "points_available": 5,
    "slides_count": 25
  }
}
```

### 9.4 Wrong Document Type (400/404)

**Nếu frontend cố gắng dùng version parameter trên A4/Notes documents:**

```json
{
  "detail": "Version 3 not found"
}
```

**Cause:** A4 và Notes documents không có `version_history` field, nên bất kỳ version nào cũng sẽ trả về 404.

**⚠️ Frontend cần check:** Chỉ enable version features khi `document_type === "slide"`

---

## 10. Migration Status

✅ **Migration Completed:** 284 **SLIDE** documents now have `version_history` field

**⚠️ Important:** Chỉ slide documents được migrate. A4 và Notes documents không có version_history field.

**Schema:**
```json
{
  "version_history": [
    {
      "version": 1,
      "created_at": "2025-12-25T15:00:00Z",
      "description": "Initial version",
      "content_html": "...",
      "slides_outline": [...],
      "slide_backgrounds": [...],
      "slide_elements": [...],
      "slide_count": 26
    }
  ]
}
```

---

## 11. Summary of Affected Endpoints

**⚠️ TẤT CẢ endpoints dưới đây CHỈ áp dụng cho SLIDE documents (`document_type: "slide"`)**

**KHÔNG áp dụng cho:**
- ❌ A4 documents (`document_type: "doc"`)
- ❌ Notes documents (`document_type: "note"`)

| Endpoint | Version Support | Points Cost | Document Type |
|----------|----------------|-------------|---------------|
| GET `/api/slides/outline` | ✅ Yes | FREE | **SLIDE only** |
| PUT `/api/slides/outline` | N/A | FREE | **SLIDE only** |
| POST `/api/slides/outline/add` | N/A | FREE | **SLIDE only** |
| DELETE `/api/slides/outline/slide` | N/A | FREE | **SLIDE only** |
| GET `/api/slides/versions` | N/A | FREE | **SLIDE only** |
| POST `/api/slides/versions/switch` | N/A | FREE | **SLIDE only** |
| GET `/api/documents/{id}` | ✅ Yes (slides) | FREE | **SLIDE only for version param** |
| PUT `/api/documents/{id}` | N/A | FREE | **SLIDE only for snapshots** |
| POST `/api/slides/ai-format` | ✅ Yes | 2-5 points | **SLIDE only** |
| GET `/api/documents/{id}/download/{format}` | ✅ Yes (slides) | FREE | **SLIDE only for version param** |
| POST `/api/presentations/{id}/subtitles/v2` | ✅ Yes | 2 points | **SLIDE only** |
| POST `/api/presentations/{id}/subtitles/v2/{sub_id}/audio` | ✅ Yes | 2 points | **SLIDE only** |

---

## Questions?

Contact backend team for clarification on version parameter usage or endpoint behavior.
