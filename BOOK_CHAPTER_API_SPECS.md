# Book Chapter API Technical Specifications

**Version**: 2.0
**Last Updated**: January 9, 2026
**Status**: Production

## Overview

The Book Chapter system now supports **3 content modes** for different types of content:

1. **`inline`** - Text-based content (HTML/JSON) - *Legacy mode*
2. **`pdf_pages`** - PDF documents converted to page backgrounds with annotation overlays
3. **`image_pages`** - Image sequences (manga, comics, photo books) with element overlays

---

## Content Modes

### Mode: `inline`

**Description**: Traditional text content stored directly in chapter document.

**Use Cases**: Text-based books, articles, tutorials.

**Schema**:
```
{
  "content_mode": "inline",
  "content": "<p>HTML content...</p>",
  "content_type": "html"
}
```

---

### Mode: `pdf_pages`

**Description**: PDF files converted to fixed-size page background images with overlay elements.

**Use Cases**: Digital textbooks, academic papers, manuals, documents.

**Page Dimensions**: Fixed A4 size @ 150 DPI
- Width: `1240px`
- Height: `1754px`

**Element Types**: `highlight`, `text`, `shape`, `image`, `video`, `note`, `arrow`, `underline`, `strikethrough`

**Schema**:
```
{
  "content_mode": "pdf_pages",
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://static.wordai.pro/studyhub/chapters/{chapter_id}/page-1.jpg",
      "width": 1240,
      "height": 1754,
      "elements": [...]
    }
  ],
  "total_pages": 24,
  "source_file_id": "file_id_reference"
}
```

---

### Mode: `image_pages`

**Description**: Image sequences with variable dimensions and optional manga metadata.

**Use Cases**: Manga, comics, photo books, image galleries.

**Page Dimensions**: Variable (preserves original image dimensions)

**Element Types**: `speech_bubble`, `sound_effect`, `annotation`, `panel_border`, `highlight`, `text`, `shape`, `image`, `video`, `note`, `arrow`

**Schema**:
```
{
  "content_mode": "image_pages",
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://static.wordai.pro/studyhub/chapters/{chapter_id}/page-1.jpg",
      "width": 850,
      "height": 1200,
      "elements": [...]
    }
  ],
  "total_pages": 42,
  "manga_metadata": {
    "reading_direction": "rtl",
    "is_colored": false,
    "artist": "Artist Name",
    "genre": "Action, Adventure"
  },
  "source_file_id": "zip_file_id_reference"
}
```

---

## API Endpoints

### 1. Create Chapter from PDF

**Endpoint**: `POST /api/v1/books/{book_id}/chapters/from-pdf`

**Authentication**: Required (Owner only)

**Content Mode**: `pdf_pages`

**Request Body**:
```
{
  "file_id": "uuid",              // Required - File ID from POST /api/files/upload
  "title": "string",              // Required
  "slug": "string",               // Optional - Auto-generated if not provided
  "order_index": 0,               // Optional - Default: 0
  "parent_id": "uuid",            // Optional - For nested chapters
  "is_published": true,           // Optional - Default: true
  "is_preview_free": false        // Optional - Default: false
}
```

**Response** (201 Created):
```
{
  "success": true,
  "chapter": {
    "_id": "uuid",
    "book_id": "uuid",
    "user_id": "uuid",
    "title": "Chapter Title",
    "slug": "chapter-title",
    "content_mode": "pdf_pages",
    "pages": [...],
    "total_pages": 24,
    "source_file_id": "uuid",
    "created_at": "2026-01-09T10:00:00Z",
    "updated_at": "2026-01-09T10:00:00Z"
  },
  "total_pages": 24,
  "message": "Chapter created with 24 PDF pages"
}
```

**Process**:
1. Validates PDF file ownership (from user_files collection)
2. Downloads PDF from R2
3. Extracts pages as images (A4 @ 150 DPI → 1240×1754px)
4. Uploads page images to R2: `studyhub/chapters/{chapter_id}/page-{N}.jpg`
5. Creates chapter with pages array
6. Marks file as used in chapter

**Error Responses**:
- `400` - Invalid file type (not PDF), validation error
- `403` - Access denied (not owner)
- `404` - Book or file not found
- `500` - Processing error

**Important Notes**:
- PDF file must be uploaded via `POST /api/files/upload` first
- File is stored in `user_files` collection (My Files)
- Extracted page images are stored separately in R2
- Original PDF file remains in My Files for download/reference

---

### 2. Upload Images for Chapter

**Endpoint**: `POST /api/v1/books/{book_id}/chapters/upload-images`

**Authentication**: Required (Owner only)

**Content Type**: `multipart/form-data`

**Description**: Upload images directly to chapter storage and get CDN URLs.

**Form Data**:
```
files: File[]               // Required - Image files (max 10 per request)
chapter_id: string          // Optional - Use same ID for multiple upload batches
```

**Request Headers**:
```
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

**Response** (200 OK):
```
{
  "success": true,
  "chapter_id": "uuid",              // NEW - Auto-generated on first upload
  "images": [
    {
      "file_name": "image1.jpg",
      "file_size": 234567,
      "url": "https://static.wordai.pro/studyhub/chapters/{chapter_id}/page-1.jpg",
      "width": 850,
      "height": 1200,
      "page_number": 1               // NEW - Sequential page number
    },
    {
      "file_name": "image2.png",
      "file_size": 345678,
      "url": "https://static.wordai.pro/studyhub/chapters/{chapter_id}/page-2.jpg",
      "width": 920,
      "height": 1300,
      "page_number": 2
    }
  ],
  "total_uploaded": 2,
  "total_size": 580245,
  "current_page_count": 2,           // NEW - Total pages uploaded so far
  "message": "Uploaded 2 images successfully"
}
```

**Constraints**:
- Max files per request: **10 files**
- Max total size per request: **100 MB**
- Supported formats: JPG, PNG, WEBP, GIF
- Each file max size: **20 MB**

**Process**:
1. First upload: Generates new `chapter_id` (UUID)
2. Subsequent uploads: Use same `chapter_id` to continue adding pages
3. Converts images to RGB (handles transparency)
4. Compresses to JPEG (quality 90)
5. Uploads directly to permanent storage: `studyhub/chapters/{chapter_id}/page-{N}.jpg`
6. Returns URLs immediately (no temp storage, no re-upload)

**Usage Flow**:
1. User selects 10 images → Upload → Get `chapter_id` + URLs (pages 1-10)
2. User selects 10 more → Upload with same `chapter_id` → Get URLs (pages 11-20)
3. Repeat as needed
4. Call `POST /from-images` with `chapter_id` + metadata (title, etc.)

**Storage**: Direct permanent storage - No temp folder, no cleanup needed

**Error Responses**:
- `400` - Too many files (>10), total size >100MB, unsupported format
- `403` - Access denied (not owner)
- `413` - Payload too large
- `500` - Upload error

---

### 3. Create Chapter from Images

**Endpoint**: `POST /api/v1/books/{book_id}/chapters/from-images`

**Authentication**: Required (Owner only)

**Content Mode**: `image_pages`

**Request Body**:
```
{
  "chapter_id": "uuid",                      // Required - From upload-images response
  "title": "string",                         // Required
  "slug": "string",                          // Optional
  "order_index": 0,                          // Optional
  "parent_id": "uuid",                       // Optional
  "is_published": true,                      // Optional
  "is_preview_free": false,                  // Optional
  "manga_metadata": {                        // Optional
    "reading_direction": "rtl",              // "ltr" or "rtl"
    "is_colored": false,                     // Boolean
    "artist": "Artist Name",                 // String
    "genre": "Action, Adventure"             // String
  }
}
```

**Response** (201 Created):
```
{
  "success": true,
  "chapter": {
    "_id": "uuid",                           // Same as chapter_id from upload
    "content_mode": "image_pages",
    "pages": [...],                          // All uploaded pages
    "total_pages": 42,
    "manga_metadata": {...}
  },
  "total_pages": 42,
  "message": "Chapter created with 42 image pages"
}
```

**Process**:
1. Validates chapter_id has uploaded images
2. Retrieves all page URLs from storage metadata
3. Creates chapter document with pages array (images already in permanent storage)
4. No image processing or moving needed

**Error Responses**:
- `400` - Invalid chapter_id, no images found
- `403` - Access denied
- `404` - Chapter images not found
- `500` - Processing error

---

### 4. Create Chapter from ZIP

**Endpoint**: `POST /api/v1/books/{book_id}/chapters/from-zip`

**Authentication**: Required (Owner only)

**Content Mode**: `image_pages`

**Status**: ⚠️ **Not available** - File system doesn't support ZIP upload yet

**Alternative**: Use `POST /upload-images` endpoint multiple times + `POST /from-images`

**Future Implementation**: Will be enabled when ZIP file upload is supported in StudyHub file system.

---

### 5. Update Page Elements

**Endpoint**: `PUT /api/v1/books/chapters/{chapter_id}/pages`

**Authentication**: Required (Owner only)

**Content Modes**: `pdf_pages`, `image_pages` only

**Request Body**:
```json
{
  "pages": [
    {
      "page_number": 1,
      "elements": [
        {
          "id": "element_uuid",
          "type": "highlight",
          "x": 100,
          "y": 200,
          "width": 300,
          "height": 50,
          "z_index": 1,
          "color": "#FFFF00",
          "opacity": 0.3
        },
        {
          "id": "note_001",
          "type": "note",
          "x": 150,
          "y": 250,
          "width": 400,
          "height": 120,
          "content": "My annotation here",
          "color": "#FFF9C4",
          "opacity": 0.9,
          "z_index": 2
        }
      ]
    }
  ]
}
```

**Important Notes**:
- **Only send `page_number` and `elements`** - do NOT include `background_url`, `width`, `height`
- Backend preserves existing page metadata (background URL, dimensions)
- Elements array **replaces** existing elements for that page
- Use partial updates: only include pages that changed

**Response**:
```
{
  "success": true,
  "chapter": {...},
  "pages_updated": 3,
  "total_elements": 15,
  "message": "Updated 3 pages with 15 elements"
}
```

**Behavior**:
- Replaces elements array for specified pages
- Preserves background_url, width, height
- Only updates pages included in request
- Validates element schema

---

### 6. Delete Page from Chapter

**Endpoint**: `DELETE /api/v1/books/chapters/{chapter_id}/pages/{page_number}`

**Authentication**: Required (Owner only)

**Content Modes**: `pdf_pages`, `image_pages` only

**Description**: Delete a specific page and renumber remaining pages.

**Path Parameters**:
```
chapter_id: string    // Chapter ID
page_number: number   // Page number to delete (1-indexed)
```

**Response**:
```
{
  "success": true,
  "deleted_page": 3,
  "total_pages": 23,
  "message": "Page 3 deleted successfully"
}
```

**Process**:
1. Removes page from pages array
2. Deletes page image from R2 storage
3. Renumbers remaining pages sequentially
4. Updates total_pages count

**Example**:
- Before: [page 1, page 2, page 3, page 4]
- Delete page 2
- After: [page 1, page 2 (old 3), page 3 (old 4)]

**Error Responses**:
- `400` - Invalid content mode (not pdf_pages/image_pages)
- `403` - Access denied (not owner)
- `404` - Chapter or page not found
- `500` - Processing error

**Warning**: This operation cannot be undone. Page image is permanently deleted from storage.

---

### 7. Reorder Pages in Chapter

**Endpoint**: `PUT /api/v1/books/chapters/{chapter_id}/pages/reorder`

**Authentication**: Required (Owner only)

**Content Modes**: `pdf_pages`, `image_pages` only

**Description**: Reorder pages by specifying new sequence.

**Request Body**:
```
{
  "page_order": [3, 1, 2, 4]  // New page order (1-indexed)
}
```

**Response**:
```
{
  "success": true,
  "total_pages": 4,
  "new_order": [3, 1, 2, 4],
  "message": "Pages reordered successfully"
}
```

**Validation**:
- Array length must match `total_pages`
- All numbers must be unique
- All numbers must be valid (1 to total_pages)

**Example**:
- Original order: [page 1, page 2, page 3, page 4]
- Request: `page_order = [3, 1, 2, 4]`
- Result: [page 3, page 1, page 2, page 4]
- Page numbers updated: [1, 2, 3, 4]

**Use Cases**:
- Fix incorrect page order from PDF extraction
- Rearrange manga/comic pages
- Move important pages to front

**Error Responses**:
- `400` - Invalid page_order (wrong length, duplicates, invalid numbers)
- `403` - Access denied (not owner)
- `404` - Chapter not found
- `500` - Processing error

---

### 8. Update Manga Metadata

**Endpoint**: `PUT /api/v1/books/chapters/{chapter_id}/manga-metadata`

**Authentication**: Required (Owner only)

**Content Mode**: `image_pages` only

**Query Parameters**:
```
reading_direction: string   // Optional - "ltr" or "rtl"
is_colored: boolean         // Optional
artist: string              // Optional
genre: string               // Optional
```

**Response**:
```
{
  "success": true,
  "chapter": {...},
  "manga_metadata": {
    "reading_direction": "rtl",
    "is_colored": false,
    "artist": "Updated Artist",
    "genre": "Updated Genre"
  },
  "message": "Manga metadata updated successfully"
}
```

**Validation**:
- `reading_direction` must be `"ltr"` or `"rtl"`
- At least one field must be provided

---

### 6. Get Chapter with Content

**Endpoint**: `GET /api/v1/books/chapters/{chapter_id}`

**Authentication**: Required

**Response Schema**:

#### For `inline` mode:
```
{
  "_id": "uuid",
  "book_id": "uuid",
  "title": "Chapter Title",
  "content_mode": "inline",
  "content": "<p>HTML content...</p>",
  "content_type": "html",
  "is_published": true,
  "created_at": "2026-01-09T10:00:00Z"
}
```

#### For `pdf_pages` mode:
```
{
  "_id": "uuid",
  "book_id": "uuid",
  "title": "Chapter Title",
  "content_mode": "pdf_pages",
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://static.wordai.pro/...",
      "width": 1240,
      "height": 1754,
      "elements": [...]
    }
  ],
  "total_pages": 24,
  "source_file_id": "uuid",
  "file_details": {
    "file_name": "document.pdf",
    "file_size": 2456789,
    "file_type": "application/pdf",
    "file_url": "https://static.wordai.pro/..."
  }
}
```

#### For `image_pages` mode:
```
{
  "_id": "uuid",
  "book_id": "uuid",
  "title": "Chapter Title",
  "content_mode": "image_pages",
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://static.wordai.pro/...",
      "width": 850,
      "height": 1200,
      "elements": [...]
    }
  ],
  "total_pages": 42,
  "manga_metadata": {
    "reading_direction": "rtl",
    "is_colored": false,
    "artist": "Artist Name",
    "genre": "Action"
  },
  "source_file_id": "uuid",
  "file_details": {...}
}
```

**Behavior**:
- Returns chapter document with content populated
- For `pdf_pages` and `image_pages`: Includes full pages array
- For `image_pages`: Includes manga_metadata if available
- If `source_file_id` exists: Enriches with file_details

---

## Data Structures

### Page Element

**Common Properties**:
```
{
  "id": "uuid",           // Unique element ID
  "type": "string",       // Element type (see below)
  "x": number,            // X position (pixels)
  "y": number,            // Y position (pixels)
  "width": number,        // Element width (pixels)
  "height": number,       // Element height (pixels)
  "z_index": number,      // Layer order (higher = on top)
  "color": "string",      // Hex color (#RRGGBB)
  "opacity": number,      // 0.0 - 1.0
  "content": "string"     // Text content (if applicable)
}
```

### Element Types

#### For `pdf_pages`:
- **`highlight`** - Transparent colored overlay (x, y, width, height, color, opacity)
- **`text`** - Text annotation (x, y, content, font_size, color)
- **`shape`** - Rectangle, circle, etc. (x, y, width, height, color, style)
- **`image`** - Embedded image (x, y, width, height, src)
- **`video`** - Embedded video (x, y, width, height, src) ⭐ NEW
- **`note`** - Rectangular note/comment area (x, y, width, height, content) ⭐ NEW
- **`arrow`** - Directional arrow (x, y, width, height, color)
- **`underline`** - Text underline (x, y, width, color)
- **`strikethrough`** - Text strikethrough (x, y, width, color)

#### For `image_pages`:
- **`speech_bubble`** - Comic speech bubble (x, y, width, height, content, style)
- **`sound_effect`** - Sound effect text (x, y, content, font_size)
- **`annotation`** - General annotation (x, y, content)
- **`panel_border`** - Panel boundary (x, y, width, height, color)
- Plus all `pdf_pages` types (highlight, text, shape, image, video, note, arrow, etc.)

### Element Examples

#### Text Element
```json
{
  "id": "text_001",
  "type": "text",
  "x": 100,
  "y": 50,
  "content": "Important annotation",
  "font_size": 16,
  "color": "#FF0000",
  "font_family": "Arial",
  "z_index": 2
}
```

#### Image Element
```json
{
  "id": "img_001",
  "type": "image",
  "x": 200,
  "y": 300,
  "width": 400,
  "height": 300,
  "src": "https://static.wordai.pro/images/diagram.png",
  "z_index": 1
}
```

#### Video Element ⭐ NEW
```json
{
  "id": "video_001",
  "type": "video",
  "x": 150,
  "y": 200,
  "width": 640,
  "height": 360,
  "src": "https://youtube.com/embed/abc123",
  "z_index": 1
}
```

#### Note Element ⭐ NEW
```json
{
  "id": "note_001",
  "type": "note",
  "x": 50,
  "y": 100,
  "width": 300,
  "height": 150,
  "content": "This is a detailed note explaining this section. Users can drag to create rectangular note areas.",
  "color": "#FFF9C4",
  "opacity": 0.9,
  "z_index": 3
}
```

#### Highlight Element
```json
{
  "id": "hl_001",
  "type": "highlight",
  "x": 100,
  "y": 200,
  "width": 400,
  "height": 30,
  "color": "#FFFF00",
  "opacity": 0.3,
  "z_index": 0
}
```

#### Speech Bubble (Manga)
```json
{
  "id": "bubble_001",
  "type": "speech_bubble",
  "x": 250,
  "y": 150,
  "width": 200,
  "height": 100,
  "content": "Hello there!",
  "style": "round",
  "font_size": 14,
  "z_index": 2
}
```

### Manga Metadata

```
{
  "reading_direction": "rtl",  // "ltr" (left-to-right) or "rtl" (right-to-left)
  "is_colored": false,         // true = colored, false = black & white
  "artist": "string",          // Artist/illustrator name
  "genre": "string"            // Comma-separated genres
}
```

---

## Frontend Implementation Guidelines

### 1. Chapter Creation Flow

**For PDF Books**:
1. User uploads PDF via `POST /api/files/upload` → Get `file_id`
2. Call `POST /books/{book_id}/chapters/from-pdf` with `file_id`
3. Wait for processing (can take 10-30 seconds for large PDFs)
4. Receive chapter with `pages` array (extracted images)
5. Redirect to chapter viewer

**Important Notes**:
- PDF uploaded to **My Files** (user_files collection)
- PDF remains accessible in My Files for download/sharing
- Chapter uses extracted page images (JPG), not original PDF
- Original PDF referenced via `source_file_id`

**For Manga/Comics (Images)**:
1. User selects 10 images → Upload via `POST /upload-images`
2. Receive `chapter_id` + page URLs (pages 1-10)
3. User selects 10 more images → Upload with same `chapter_id`
4. Receive more page URLs (pages 11-20)
5. Repeat as needed
6. Call `POST /from-images` with `chapter_id` + title + metadata
7. Chapter created immediately (images already in storage)
8. Redirect to chapter viewer

**For Manga/Comics (ZIP)** - ⚠️ Not available yet:
1. ~~User uploads ZIP to StudyHub files → Get `zip_file_id`~~
2. ~~Call `POST /books/{book_id}/chapters/from-zip` with `zip_file_id`~~
3. Alternative: Extract ZIP client-side → Upload images in batches → Use images flow above

### 2. Chapter Viewer Implementation

**Detect Content Mode**:
```
if (chapter.content_mode === 'inline') {
  // Render HTML content
  renderHTMLContent(chapter.content)
}
else if (chapter.content_mode === 'pdf_pages') {
  // Render pages with fixed A4 dimensions
  renderPDFPages(chapter.pages, { width: 1240, height: 1754 })
}
else if (chapter.content_mode === 'image_pages') {
  // Render pages with variable dimensions
  renderImagePages(chapter.pages)

  // Handle manga reading direction
  if (chapter.manga_metadata?.reading_direction === 'rtl') {
    enableRightToLeftNavigation()
  }
}
```

**Page Rendering**:
- Display `background_url` as page background
- Overlay `elements` array on top
- Respect `z_index` for element layering
- Handle element interactions (select, edit, delete)

**Reading Direction**:
- `ltr`: Next page → Right arrow, Previous page → Left arrow
- `rtl`: Next page → Left arrow, Previous page → Right arrow (manga style)

### 3. Annotation Editor

**Add Element**:
1. User draws/clicks on page
2. Calculate `{x, y, width, height}` in page coordinates
3. Create element object with type, color, content
4. Update local state
5. Call `PUT /chapters/{id}/pages` to save

**Edit Element**:
1. User selects element
2. Modify properties (color, size, content)
3. Update element in array
4. Call `PUT /chapters/{id}/pages` to save

**Delete Element**:
1. Remove element from array
2. Call `PUT /chapters/{id}/pages` to save

---

### 4. Page Management

**Delete Page**:
```javascript
// User clicks delete on page 3
await DELETE `/chapters/{chapter_id}/pages/3`

// Response: { deleted_page: 3, total_pages: 23 }
// Remaining pages auto-renumbered: [1, 2, 3(old 4), 4(old 5), ...]
```

**Reorder Pages**:
```javascript
// Original: [page 1, page 2, page 3, page 4]
// User drags page 3 to first position

const newOrder = [3, 1, 2, 4]  // Page 3 now first

await PUT `/chapters/{chapter_id}/pages/reorder`, {
  page_order: newOrder
}

// Pages renumbered to: [1(old 3), 2(old 1), 3(old 2), 4]
```

**UI Recommendations**:
- Show page thumbnails in grid/list view
- Drag & drop to reorder
- Delete button with confirmation dialog
- Undo not available - warn users before delete
- Show loading state during reorder (updates chapter)

---

### 5. Performance Considerations

**Large Books (100+ pages)**:
- Consider implementing lazy loading (load pages on demand)
- Use pagination or infinite scroll
- Cache loaded pages in memory
- Preload adjacent pages

**Image Optimization**:
- Display images at appropriate resolution
- Use CDN caching (images are on R2 CDN)
- Consider implementing thumbnail generation (Phase 4 feature)

### 5. Error Handling

**Processing Errors**:
- PDF extraction failed → Show error, allow retry
- Image download failed → Show error, allow re-upload
- ZIP extraction failed → Show error, check ZIP format

**Validation Errors**:
- Invalid file type → Clear error message
- Missing required fields → Highlight fields
- Access denied → Redirect to book list

---

## Migration Notes

### Deprecated: `document` Mode

**Status**: Legacy mode, being phased out

**Migration**: Use `inline` mode instead

**If you encounter `content_mode: "document"`**:
- Backend will auto-populate `content` from document reference
- Frontend should treat as `inline` mode
- New chapters should use `inline`, `pdf_pages`, or `image_pages`

---

## CDN & Storage

**CDN Base URL**: `https://static.wordai.pro`

**Storage Collections**:
- **PDF Files**: `user_files` collection (My Files)
  - Uploaded via: `POST /api/files/upload`
  - Storage path: `files/{user_id}/root/{file_id}/{filename}`
  - Original PDF preserved for download

- **Extracted Page Images**: Direct R2 storage (no collection)
  - Created during: PDF/Image chapter creation
  - Storage path: `studyhub/chapters/{chapter_id}/page-{N}.jpg`
  - Permanent storage, referenced in chapter.pages array

**Path Patterns**:
- **PDF files**: `files/{user_id}/root/{file_id}/{filename}.pdf` (private, signed URLs)
- **Chapter pages**: `studyhub/chapters/{chapter_id}/page-{N}.jpg` (public CDN)
- **Thumbnails** (future): `studyhub/chapters/{chapter_id}/page-{N}-thumb.jpg`

**Storage Flow for PDF**:
1. User uploads PDF → `POST /api/files/upload`
2. PDF stored in: `files/{user_id}/root/{file_id}/document.pdf`
3. Create chapter → `POST /from-pdf`
4. Backend extracts pages → Upload to: `studyhub/chapters/{chapter_id}/page-1.jpg`, `page-2.jpg`, ...
5. Chapter references both: `source_file_id` (PDF) + `pages[].background_url` (images)

**Storage Flow for Images**:
1. Upload images → `POST /upload-images` (with optional chapter_id)
2. Images stored directly: `studyhub/chapters/{chapter_id}/page-{N}.jpg`
3. Create chapter → `POST /from-images` (images already in place)
4. No file moving, single upload only

**Image Format**: JPEG (quality 90, optimized)

**Caching**:
- Chapter page images: Public CDN, cached
- PDF files: Private, signed URLs (1 hour expiry)

---

## Rate Limits & Constraints

**File Upload**:
- Max PDF size: 50MB
- Max ZIP size: 100MB
- Max images per chapter: 500 pages

**Processing Time**:
- PDF (100 pages): ~20-30 seconds
- ZIP (50 images): ~10-15 seconds
- Images (10 URLs): ~5-10 seconds

**Concurrent Requests**: Max 5 chapter creations per user simultaneously

---

## Changelog

### Version 2.1 (January 9, 2026 - Updated)
- **BREAKING CHANGE**: PDF files now uploaded via `POST /api/files/upload` (My Files)
- **BREAKING CHANGE**: `/from-pdf` now queries `user_files` collection (not studyhub_files)
- Added `DELETE /chapters/{chapter_id}/pages/{page_number}` - Delete page + auto-renumber
- Added `PUT /chapters/{chapter_id}/pages/reorder` - Reorder pages with validation
- Clarified storage architecture: PDF in user_files, extracted images in R2
- Updated documentation with page management workflows

### Version 2.0 (January 9, 2026)
- Added `pdf_pages` content mode
- Added `image_pages` content mode
- Added manga metadata support
- Added ZIP upload for manga
- Added page element overlays
- New endpoints: `/from-pdf`, `/from-images`, `/from-zip`, `/manga-metadata`

### Version 1.0 (Legacy)
- `inline` mode only
- `document` reference mode (deprecated)

---

## Support

**API Documentation**: `/docs` endpoint on server

**Architecture**: See `/BOOK_CHAPTER_PDF_ARCHITECTURE.md`

**System Reference**: See `/SYSTEM_REFERENCE.md`

**Questions**: Contact backend team
