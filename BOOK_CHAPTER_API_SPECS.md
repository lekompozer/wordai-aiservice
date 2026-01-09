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

**Element Types**: `highlight`, `text`, `shape`, `image`, `arrow`, `underline`, `strikethrough`

**Schema**:
```
{
  "content_mode": "pdf_pages",
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://cdn.wordai.com/studyhub/chapters/{chapter_id}/page-1.jpg",
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

**Element Types**: `speech_bubble`, `sound_effect`, `annotation`, `panel_border`, `highlight`, `text`, `shape`, `image`, `arrow`

**Schema**:
```
{
  "content_mode": "image_pages",
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://cdn.wordai.com/studyhub/chapters/{chapter_id}/page-1.jpg",
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
  "file_id": "uuid",              // Required - StudyHub file ID (must be PDF)
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
1. Validates PDF file ownership
2. Downloads PDF from R2
3. Extracts pages as images (A4 @ 150 DPI)
4. Uploads page images to R2
5. Creates chapter with pages array
6. Updates file studyhub_context

**Error Responses**:
- `400` - Invalid file type (not PDF), validation error
- `403` - Access denied (not owner)
- `404` - Book or file not found
- `500` - Processing error

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
      "url": "https://cdn.wordai.com/studyhub/chapters/{chapter_id}/page-1.jpg",
      "width": 850,
      "height": 1200,
      "page_number": 1               // NEW - Sequential page number
    },
    {
      "file_name": "image2.png",
      "file_size": 345678,
      "url": "https://cdn.wordai.com/studyhub/chapters/{chapter_id}/page-2.jpg",
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
```
{
  "pages": [
    {
      "page_number": 1,           // Required
      "elements": [               // Required
        {
          "id": "element_uuid",
          "type": "highlight",    // See Element Types
          "x": 100,
          "y": 200,
          "width": 300,
          "height": 50,
          "z_index": 1,
          "color": "#FFFF00",
          "opacity": 0.3,
          "content": "Annotation text"
        }
      ]
    }
  ]
}
```

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

### 5. Update Manga Metadata

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
      "background_url": "https://cdn.wordai.com/...",
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
    "file_url": "https://cdn.wordai.com/..."
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
      "background_url": "https://cdn.wordai.com/...",
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
- **`highlight`** - Transparent colored overlay
- **`text`** - Text annotation
- **`shape`** - Rectangle, circle, etc.
- **`image`** - Embedded image
- **`arrow`** - Directional arrow
- **`underline`** - Text underline
- **`strikethrough`** - Text strikethrough

#### For `image_pages`:
- **`speech_bubble`** - Comic speech bubble
- **`sound_effect`** - Sound effect text
- **`annotation`** - General annotation
- **`panel_border`** - Panel boundary
- Plus all `pdf_pages` types

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
1. User uploads PDF to StudyHub files → Get `file_id`
2. Call `POST /books/{book_id}/chapters/from-pdf` with `file_id`
3. Wait for processing (can take 10-30 seconds for large PDFs)
4. Receive chapter with `pages` array
5. Redirect to chapter viewer

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

### 4. Performance Considerations

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

**CDN Base URL**: `https://cdn.wordai.com`

**Path Patterns**:
- **Chapter pages**: `studyhub/chapters/{chapter_id}/page-{N}.jpg` (permanent, uploaded directly)
- **Thumbnails** (future): `studyhub/chapters/{chapter_id}/page-{N}-thumb.jpg`

**Storage Flow (Simplified)**:
1. Upload images → Direct to permanent storage with auto-generated `chapter_id`
2. Create chapter → Use existing `chapter_id`, images already in place
3. No temp storage, no file moving, single upload only

**Image Format**: JPEG (quality 90, optimized)

**Caching**: CDN cached, no authentication required for public URLs

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
