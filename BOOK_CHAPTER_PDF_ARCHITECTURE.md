# Book Chapter Multimedia Content Architecture - Analysis & Design

**Date**: January 9, 2026 (Updated)
**Purpose**: Support multiple content types for book chapters (HTML, PDF pages, Image pages)
**Version**: 2.0 - Multi-format Chapter System

---

## 1. Current System Architecture

### 1.1. Existing Chapter Structure

**Collection**: `book_chapters`

**Current Fields**:
```javascript
{
  "chapter_id": "chapter_uuid",
  "book_id": "book_uuid",
  "title": "Chapter Title",
  "slug": "chapter-slug",
  "parent_id": null,  // For nested chapters
  "order_index": 0,
  "depth": 0,  // Max: 3 levels

  // CONTENT STORAGE MODEL (DEPRECATED - 2 modes)
  "content_source": "inline" | "document",  // ❌ DEPRECATED: "document" mode will be removed

  // MODE 1: INLINE (content stored in chapter)
  "content_html": "<h1>Chapter content...</h1>",
  "content_json": {...},  // TipTap editor format

  // MODE 2: DOCUMENT (reference to documents collection) - ❌ TO BE DEPRECATED
  "document_id": "doc_uuid",  // Links to documents.document_id
  "content_html": null,  // Not stored, loaded dynamically

  // Metadata
  "is_published": true,
  "is_preview_free": false,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### 1.2. Content Source Modes (Current - To Be Replaced)

| Mode | Storage | Use Case | Status |
|------|---------|----------|--------|
| **`inline`** | Content in chapter | Standalone chapters | ✅ KEEP - Enhanced |
| **`document`** | Reference to document | Reusable content | ❌ DEPRECATED - Remove |

### 1.3. Existing Manager Methods

**File**: `src/services/book_chapter_manager.py`

```python
class GuideBookBookChapterManager:

    # Create chapter (supports both modes)
    def create_chapter(book_id, chapter_data) -> dict

    # Get chapter with content (auto-loads from document if needed)
    def get_chapter_with_content(chapter_id) -> dict

    # Update chapter content (handles both modes)
    def update_chapter_content(chapter_id, content_html, content_json)

    # Create chapter from existing document
    def create_chapter_from_document(book_id, document_id, title, ...)

    # Convert document to chapter (copy or link)
    def convert_document_to_chapter(document_id, book_id, user_id, copy_content=True)
```

---

## 2. Problem Statement & New Requirements

### 2.1. Current Limitations
- ❌ Chapters only support HTML/JSON content (inline mode)
- ❌ Document reference mode creates confusion (external dependency)
- ❌ No support for rich media content (PDF, images, manga/comics)
- ❌ Cannot create interactive multimedia books

### 2.2. User Requirements (Updated)

**Support 3 multimedia content types**:

1. **Text-based chapters** (existing HTML/JSON)
2. **PDF-based chapters** - Convert PDF pages to background images with overlay elements
   - Use case: Textbooks, academic materials, worksheets
3. **Image-based chapters** (NEW) - Manga, comics, photo books
   - Use case: Comics, manga, graphic novels, photo albums

**Key Features**:
- Pages array structure (similar to slide system pattern)
- Background images with optional overlay elements
- Support annotations, highlights, interactive elements
- A4 portrait dimensions for PDF (210×297mm)
- Flexible dimensions for images (manga: variable sizes)
- Frontend can add elements dynamically (notes, highlights, speech bubbles)

**Business Value**:
- 📚 Traditional books (HTML chapters)
- 📄 Educational content (PDF pages)
- 🎨 Comics & Manga (Image pages)
- 🖼️ Photo books & portfolios

---

## 3. New Architecture Design

### 3.1. Enhanced Chapter Structure (3 Content Modes)

**REMOVE**: `document` reference mode (deprecated)

**NEW MODES**:

```javascript
{
  "chapter_id": "chapter_uuid",
  "book_id": "book_uuid",
  "title": "Chapter 1: Introduction",
  "slug": "chapter-1-introduction",

  // ═══════════════════════════════════════════════
  // CONTENT SOURCE (3 MODES)
  // ═══════════════════════════════════════════════

  "content_source": "inline" | "pdf_pages" | "image_pages",

  // ───────────────────────────────────────────────
  // MODE 1: INLINE (Text-based - HTML/JSON)
  // ───────────────────────────────────────────────
  "content_html": "<div>Chapter content...</div>",
  "content_json": {...},  // TipTap editor format

  // ───────────────────────────────────────────────
  // MODE 2: PDF_PAGES (PDF → Pages with backgrounds)
  // ───────────────────────────────────────────────
  "file_id": "file_abc123",  // Reference to studyhub_files (PDF file)
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://cdn.wordai.com/.../page-1.png",
      "width": 1240,        // A4 @ 150 DPI
      "height": 1754,       // A4 @ 150 DPI
      "elements": [         // Optional overlay elements
        {
          "id": "highlight-001",
          "type": "highlight",
          "x": 100,
          "y": 200,
          "width": 300,
          "height": 50,
          "color": "rgba(255,255,0,0.3)"
        },
        {
          "id": "text-001",
          "type": "text",
          "x": 150,
          "y": 500,
          "content": "Important note",
          "fontSize": 16,
          "color": "#ff0000"
        }
      ]
    },
    {
      "page_number": 2,
      "background_url": "https://cdn.wordai.com/.../page-2.png",
      "width": 1240,
      "height": 1754,
      "elements": []
    }
  ],
  "total_pages": 10,
  "original_file_name": "textbook-chapter1.pdf",

  // ───────────────────────────────────────────────
  // MODE 3: IMAGE_PAGES (Comics/Manga - Image sequence)
  // ───────────────────────────────────────────────
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://cdn.wordai.com/.../manga-page-1.jpg",
      "width": 800,         // Variable (manga sizes differ)
      "height": 1200,       // Variable
      "elements": [         // Optional: Speech bubbles, effects
        {
          "id": "bubble-001",
          "type": "speech_bubble",
          "x": 300,
          "y": 150,
          "content": "Hello!",
          "style": "round"
        }
      ]
    },
    {
      "page_number": 2,
      "background_url": "https://cdn.wordai.com/.../manga-page-2.jpg",
      "width": 800,
      "height": 1200,
      "elements": []
    }
  ],
  "total_pages": 24,
  "manga_metadata": {
    "reading_direction": "right-to-left",  // or "left-to-right"
    "is_colored": false,
    "artist": "Author Name"
  },

  // Common metadata for all modes
  "is_published": true,
  "is_preview_free": false,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### 3.2. Content Mode Comparison

| Feature | Inline (HTML) | PDF Pages | Image Pages |
|---------|--------------|-----------|-------------|
| **Use Case** | Text books, articles | Textbooks, worksheets | Comics, manga, photo books |
| **Storage** | `content_html`, `content_json` | `pages[]` array | `pages[]` array |
| **Background** | None (HTML content) | PDF pages → PNG images | Image files (JPG/PNG) |
| **Dimensions** | Responsive (CSS) | A4 (1240×1754 @ 150 DPI) | Variable (manga sizes) |
| **Elements** | N/A (HTML renders) | Highlights, notes, shapes | Speech bubbles, effects |
| **File Reference** | N/A | `file_id` → studyhub_files | Multiple files or ZIP |
| **Frontend Rendering** | ContentEditable div | Canvas/SVG with backgrounds | Image viewer with overlays |

### 3.3. Database Changes Summary

**Add to `book_chapters` collection**:
```javascript
{
  // New fields for pdf_pages and image_pages modes
  "file_id": "file_uuid",           // NEW - Reference to PDF/ZIP file
  "pages": [...],                    // NEW - Pages array
  "total_pages": 10,                 // NEW - Page count
  "original_file_name": "file.pdf",  // NEW - Original filename
  "manga_metadata": {...},           // NEW - Manga-specific metadata

  // Deprecated (to be removed in Phase 2)
  "document_id": "doc_uuid"  // ❌ DEPRECATED - Remove after migration
}
```

---

## 4. Implementation Phases

### Phase 1: Foundation & PDF Pages (Week 1-2)

**Goal**: Implement `pdf_pages` mode for educational content

**Tasks**:

**1.1. Database Models & Validation**
- [ ] Update `ChapterCreate` Pydantic model
  - Add `content_source: "inline" | "pdf_pages" | "image_pages"`
  - Add `file_id: Optional[str]`
  - Add `pages: Optional[List[PageContent]]`
- [ ] Create `PageContent` model
  ```python
  class PageElement(BaseModel):
      id: str
      type: str  # highlight, text, shape, image
      x: float
      y: float
      width: Optional[float]
      height: Optional[float]
      # ... type-specific properties

  class PageContent(BaseModel):
      page_number: int
      background_url: str
      width: int
      height: int
      elements: List[PageElement] = []
  ```
- [ ] Add validation rules for each content mode

**1.2. PDF Processing Service**
- [ ] Create `PDFChapterProcessor` service
  - `extract_pdf_pages(file_path) -> List[PIL.Image]`
  - `upload_page_images_to_r2(images, user_id, chapter_id) -> List[str]`
  - `create_pages_array(image_urls, dimensions) -> List[Dict]`
- [ ] Integrate with existing `pdf_slide_import_service.py` (reuse PDF→Image logic)
- [ ] A4 dimensions: 1240 × 1754 px @ 150 DPI

**1.3. Book Chapter Manager Updates**
- [ ] Update `create_chapter()` to handle `pdf_pages` mode
  - Validate `file_id` exists in `studyhub_files`
  - Process PDF → extract pages → upload to R2
  - Create chapter with pages array
- [ ] Update `get_chapter_with_content()`
  - Return pages array when `content_source = "pdf_pages"`
  - Keep backward compatibility with `inline` mode
- [ ] Add `update_chapter_pages()` method
  - Update page elements (highlights, notes)
  - Preserve background URLs

**1.4. API Endpoints (PDF Pages)**
- [ ] `POST /books/{book_id}/chapters/from-pdf`
  - Request: `{file_id, title, order_index, ...}`
  - Process: Link existing PDF from studyhub_files
  - Response: Chapter with pages array
- [ ] `POST /books/{book_id}/chapters/upload-pdf`
  - Request: Multipart form with PDF file
  - Process: Upload to R2 → Extract pages → Create chapter
  - Response: Chapter with pages array
- [ ] `PUT /chapters/{chapter_id}/pages`
  - Update page elements (frontend adds highlights/notes)
  - Preserve background images

**1.5. Testing & Documentation**
- [ ] Unit tests for PDF processing
- [ ] Integration tests for endpoints
- [ ] Update API documentation
- [ ] Migration guide for existing chapters

**Deliverables**:
- ✅ PDF chapters working end-to-end
- ✅ Pages array with backgrounds + elements
- ✅ API endpoints tested
- ✅ Documentation updated

---

### Phase 2: Image Pages & Manga Support (Week 3-4)

**Goal**: Implement `image_pages` mode for comics, manga, photo books

**Tasks**:

**2.1. Image Processing Service**
- [ ] Create `ImageChapterProcessor` service
  - `process_image_sequence(files) -> List[Dict]`
  - `upload_images_to_r2(images, user_id, chapter_id) -> List[str]`
  - `detect_dimensions(images) -> List[Tuple[width, height]]`
- [ ] Support multiple image formats (JPG, PNG, WebP)
- [ ] Support ZIP upload (extract images → create pages)

**2.2. Manga Metadata Support**
- [ ] Add `MangaMetadata` model
  ```python
  class MangaMetadata(BaseModel):
      reading_direction: str = "right-to-left"  # or "left-to-right"
      is_colored: bool = False
      artist: Optional[str]
      genre: Optional[str]
  ```
- [ ] Store in `chapter.manga_metadata` field

**2.3. Book Chapter Manager Updates**
- [ ] Update `create_chapter()` to handle `image_pages` mode
  - Accept multiple image files or ZIP
  - Process images → upload to R2
  - Create pages array with variable dimensions
- [ ] Add `update_manga_metadata()` method

**2.4. API Endpoints (Image Pages)**
- [ ] `POST /books/{book_id}/chapters/from-images`
  - Request: `{file_ids: [...], title, manga_metadata, ...}`
  - Process: Link existing images from studyhub_files
  - Response: Chapter with pages array
- [ ] `POST /books/{book_id}/chapters/upload-images`
  - Request: Multipart form with multiple images
  - Process: Upload to R2 → Create pages array
  - Response: Chapter with pages array
- [ ] `POST /books/{book_id}/chapters/upload-manga-zip`
  - Request: ZIP file with manga pages
  - Process: Extract → Sort → Upload → Create chapter
  - Response: Chapter with pages array
- [ ] `PUT /chapters/{chapter_id}/manga-metadata`
  - Update manga-specific settings

**2.5. Frontend Support Requirements**
- [ ] Document element types for image_pages:
  - `speech_bubble` - Comic speech bubbles
  - `sound_effect` - Manga sound effects (SFX)
  - `annotation` - User notes/comments
- [ ] Define rendering guidelines (manga viewer patterns)

**Deliverables**:
- ✅ Image chapters working (manga, comics)
- ✅ ZIP upload support
- ✅ Manga metadata system
- ✅ Element overlay system

---

### Phase 3: Migration & Cleanup (Week 5)

**Goal**: Deprecate `document` reference mode, migrate existing data

**Tasks**:

**3.1. Data Migration**
- [ ] Create migration script `migrate_document_chapters_to_inline.py`
  - Find all chapters with `content_source = "document"`
  - Copy content from referenced documents to chapter
  - Update `content_source` to `"inline"`
  - Keep `document_id` for reference (but mark as deprecated)
- [ ] Backup database before migration
- [ ] Run migration on staging environment
- [ ] Verify all chapters still accessible

**3.2. Code Cleanup**
- [ ] Remove `document` mode logic from `get_chapter_with_content()`
- [ ] Update `create_chapter()` - reject `document` mode
- [ ] Update `convert_document_to_chapter()` - always copy content (remove `copy_content` parameter)
- [ ] Add deprecation warnings for existing `document_id` references

**3.3. Database Schema Update**
- [ ] Mark `document_id` field as deprecated (add comment)
- [ ] Add index on `content_source` field
- [ ] Add index on `file_id` field (for PDF/image lookups)

**3.4. Documentation & Communication**
- [ ] Update API documentation (remove document mode)
- [ ] Migration guide for existing users
- [ ] Changelog entry
- [ ] Frontend notification (if needed)

**Deliverables**:
- ✅ All document-mode chapters migrated to inline
- ✅ Document reference mode removed from codebase
- ✅ Database optimized with indexes
- ✅ Documentation updated

---

### Phase 4: Advanced Features & Optimization (Week 6+)

**Goal**: Polish, optimize, and add advanced features

**Tasks**:

**4.1. Performance Optimization**
- [ ] Lazy-load pages array (pagination for large books)
  - API: `GET /chapters/{id}?page_start=1&page_end=10`
  - Return subset of pages instead of full array
- [ ] Thumbnail generation for pages (preview images)
- [ ] CDN optimization for R2 images
- [ ] Compress images before upload (balance quality vs size)

**4.2. Advanced Element Types**
- [ ] Implement element library:
  - PDF mode: Highlight, underline, strikethrough, text box, arrow, shape
  - Manga mode: Speech bubble templates, sound effect fonts, panel borders
- [ ] Element z-index management
- [ ] Element grouping/layers

**4.3. Collaborative Features**
- [ ] Shared annotations (multiple users add notes to same chapter)
- [ ] Comment threads on pages
- [ ] Version history for elements (track changes)

**4.4. Export Features**
- [ ] Export chapter to PDF (with annotations)
- [ ] Export manga pages as CBZ (comic book archive)
- [ ] Print-friendly format

**4.5. Analytics & Tracking**
- [ ] Track page views per chapter
- [ ] Reading progress (which pages user viewed)
- [ ] Popular annotations/highlights

**Deliverables**:
- ✅ Optimized performance for large books
- ✅ Rich element library
- ✅ Export capabilities
- ✅ Analytics dashboard

---

## 5. API Endpoints Summary

### 5.1. Phase 1 Endpoints (PDF Pages)

**Create PDF Chapter (from existing file)**
```http
POST /api/books/{book_id}/chapters/from-pdf
Authorization: Bearer {firebase_token}
Content-Type: application/json

{
  "file_id": "file_abc123",
  "title": "Chapter 1: Introduction",
  "order_index": 0,
  "parent_id": null,
  "is_published": true
}

Response 201:
{
  "chapter_id": "chapter_xyz",
  "content_source": "pdf_pages",
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://cdn.wordai.com/.../page-1.png",
      "width": 1240,
      "height": 1754,
      "elements": []
    }
  ],
  "total_pages": 10
}
```

**Create PDF Chapter (upload new file)**
```http
POST /api/books/{book_id}/chapters/upload-pdf
Authorization: Bearer {firebase_token}
Content-Type: multipart/form-data

Form data:
- file: [PDF file]
- title: "Chapter 1: Introduction"
- order_index: 0
- is_published: true

Response 201:
{
  "chapter_id": "chapter_xyz",
  "file_id": "file_generated_123",
  "content_source": "pdf_pages",
  "pages": [...],
  "total_pages": 10
}
```

**Update Page Elements (add highlights/notes)**
```http
PUT /api/chapters/{chapter_id}/pages
Authorization: Bearer {firebase_token}
Content-Type: application/json

{
  "pages": [
    {
      "page_number": 1,
      "elements": [
        {
          "id": "highlight-001",
          "type": "highlight",
          "x": 100,
          "y": 200,
          "width": 300,
          "height": 50,
          "color": "rgba(255,255,0,0.3)"
        }
      ]
    }
  ]
}

Response 200:
{
  "chapter_id": "chapter_xyz",
  "pages_updated": 1,
  "total_elements": 1
}
```

### 5.2. Phase 2 Endpoints (Image Pages)

**Create Image Chapter (from existing files)**
```http
POST /api/books/{book_id}/chapters/from-images
Authorization: Bearer {firebase_token}
Content-Type: application/json

{
  "file_ids": ["file_img1", "file_img2", "file_img3"],
  "title": "Chapter 1: The Beginning",
  "order_index": 0,
  "manga_metadata": {
    "reading_direction": "right-to-left",
    "is_colored": false,
    "artist": "Manga Artist"
  }
}

Response 201:
{
  "chapter_id": "chapter_manga_xyz",
  "content_source": "image_pages",
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://cdn.wordai.com/.../page-1.jpg",
      "width": 800,
      "height": 1200,
      "elements": []
    }
  ],
  "total_pages": 3,
  "manga_metadata": {...}
}
```

**Upload Manga ZIP**
```http
POST /api/books/{book_id}/chapters/upload-manga-zip
Authorization: Bearer {firebase_token}
Content-Type: multipart/form-data

Form data:
- file: [ZIP with manga pages]
- title: "Chapter 1"
- reading_direction: "right-to-left"

Response 201:
{
  "chapter_id": "chapter_manga_xyz",
  "content_source": "image_pages",
  "pages": [...],
  "total_pages": 24
}
```

---

## 6. Database Schema Changes

### 6.1. book_chapters Collection (Updated)

```javascript
{
  // Existing fields (unchanged)
  "_id": ObjectId("..."),
  "chapter_id": "chapter_uuid",
  "book_id": "book_uuid",
  "user_id": "user_firebase_id",
  "title": "Chapter Title",
  "slug": "chapter-slug",
  "parent_id": null,
  "order_index": 0,
  "depth": 0,

  // ═══════════════════════════════════════════════
  // CONTENT SOURCE (UPDATED - 3 modes)
  // ═══════════════════════════════════════════════

  "content_source": "inline",  // "inline" | "pdf_pages" | "image_pages"

  // ───────────────────────────────────────────────
  // MODE 1: INLINE (existing)
  // ───────────────────────────────────────────────
  "content_html": "<div>...</div>",
  "content_json": {...},

  // ───────────────────────────────────────────────
  // MODE 2 & 3: PDF_PAGES / IMAGE_PAGES (NEW)
  // ───────────────────────────────────────────────

  // ✅ NEW FIELDS
  "file_id": "file_uuid",               // Reference to studyhub_files (PDF/ZIP)
  "pages": [                            // Pages array
    {
      "page_number": 1,
      "background_url": "https://cdn.../page-1.png",
      "width": 1240,
      "height": 1754,
      "elements": [
        {
          "id": "element-uuid",
          "type": "highlight",          // highlight|text|shape|image|speech_bubble|sound_effect
          "x": 100,
          "y": 200,
          "width": 300,
          "height": 50,
          // Type-specific properties
          "color": "rgba(255,255,0,0.3)",
          "content": "Note text",
          "fontSize": 16
        }
      ]
    }
  ],
  "total_pages": 10,
  "original_file_name": "textbook.pdf",

  // ✅ NEW - Manga-specific metadata (image_pages only)
  "manga_metadata": {
    "reading_direction": "right-to-left",
    "is_colored": false,
    "artist": "Author Name",
    "genre": "Action"
  },

  // ───────────────────────────────────────────────
  // DEPRECATED (Phase 3 removal)
  // ───────────────────────────────────────────────
  "document_id": "doc_uuid",  // ❌ DEPRECATED - Remove in Phase 3

  // Existing metadata
  "is_published": true,
  "is_preview_free": false,
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

### 6.2. Indexes (Phase 3)

```javascript
// Existing indexes
db.book_chapters.createIndex({ "book_id": 1, "order_index": 1 })
db.book_chapters.createIndex({ "chapter_id": 1 }, { unique: true })

// ✅ NEW indexes
db.book_chapters.createIndex({ "content_source": 1 })      // Filter by content type
db.book_chapters.createIndex({ "file_id": 1 })             // Lookup by file
db.book_chapters.createIndex({ "book_id": 1, "content_source": 1 })  // Composite
```

---

## 7. File Processing Services

### 7.1. PDFChapterProcessor (Phase 1)

**File**: `src/services/pdf_chapter_processor.py`

```python
class PDFChapterProcessor:
    """Process PDF files into chapter pages"""

    def __init__(self, s3_client, r2_bucket: str):
        self.s3_client = s3_client
        self.r2_bucket = r2_bucket

    async def process_pdf_to_pages(
        self,
        pdf_path: str,
        user_id: str,
        chapter_id: str,
        dpi: int = 150  # A4 quality
    ) -> Dict[str, Any]:
        """
        Convert PDF to pages array

        Returns:
            {
                "pages": [{page_number, background_url, width, height, elements: []}],
                "total_pages": 10,
                "original_file_name": "file.pdf"
            }
        """
        # 1. Extract PDF pages to images (PyMuPDF)
        images = await self._extract_pdf_pages(pdf_path, dpi)

        # 2. Upload images to R2 with chapter-specific path
        background_urls = await self._upload_page_images(
            images, user_id, chapter_id
        )

        # 3. Build pages array
        pages = []
        for idx, (image, url) in enumerate(zip(images, background_urls), 1):
            pages.append({
                "page_number": idx,
                "background_url": url,
                "width": image.width,   # A4: 1240px @ 150 DPI
                "height": image.height, # A4: 1754px @ 150 DPI
                "elements": []
            })

        return {
            "pages": pages,
            "total_pages": len(pages),
            "original_file_name": os.path.basename(pdf_path)
        }

    async def _extract_pdf_pages(self, pdf_path: str, dpi: int) -> List[PIL.Image]:
        """Extract PDF pages to PIL Images using PyMuPDF"""
        # Reuse logic from pdf_slide_import_service.py
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        images = []

        zoom = dpi / 72  # PyMuPDF default is 72 DPI
        mat = fitz.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            images.append(img)

        doc.close()
        return images

    async def _upload_page_images(
        self,
        images: List[PIL.Image],
        user_id: str,
        chapter_id: str
    ) -> List[str]:
        """Upload page images to R2 CDN"""
        urls = []

        for idx, image in enumerate(images, 1):
            # R2 path: studyhub/chapters/{chapter_id}/page-{idx}.png
            object_key = f"studyhub/chapters/{chapter_id}/page-{idx}.png"

            # Convert PIL Image to bytes
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            buffer.seek(0)

            # Upload to R2
            self.s3_client.upload_fileobj(
                buffer,
                self.r2_bucket,
                object_key,
                ExtraArgs={"ContentType": "image/png"}
            )

            # Generate CDN URL
            cdn_url = f"https://cdn.wordai.com/{object_key}"
            urls.append(cdn_url)

        return urls
```

### 7.2. ImageChapterProcessor (Phase 2)

**File**: `src/services/image_chapter_processor.py`

```python
class ImageChapterProcessor:
    """Process image files (manga, comics) into chapter pages"""

    async def process_images_to_pages(
        self,
        image_files: List[str],  # File paths
        user_id: str,
        chapter_id: str
    ) -> Dict[str, Any]:
        """
        Convert images to pages array

        Returns:
            {
                "pages": [{page_number, background_url, width, height, elements: []}],
                "total_pages": 24
            }
        """
        # 1. Load images
        images = [Image.open(path) for path in image_files]

        # 2. Upload to R2
        background_urls = await self._upload_images(images, user_id, chapter_id)

        # 3. Build pages array (variable dimensions for manga)
        pages = []
        for idx, (image, url) in enumerate(zip(images, background_urls), 1):
            pages.append({
                "page_number": idx,
                "background_url": url,
                "width": image.width,   # Variable (manga sizes differ)
                "height": image.height,
                "elements": []
            })

        return {
            "pages": pages,
            "total_pages": len(pages)
        }

    async def process_zip_to_pages(
        self,
        zip_path: str,
        user_id: str,
        chapter_id: str
    ) -> Dict[str, Any]:
        """Extract manga ZIP and create pages"""
        import zipfile

        # 1. Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Get image files (jpg, png, webp)
            image_files = [
                f for f in zip_ref.namelist()
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
            ]

            # Sort numerically (page-01.jpg, page-02.jpg, ...)
            image_files.sort()

            # Extract to temp directory
            temp_dir = tempfile.mkdtemp()
            for file in image_files:
                zip_ref.extract(file, temp_dir)

            # Process extracted images
            full_paths = [os.path.join(temp_dir, f) for f in image_files]
            result = await self.process_images_to_pages(
                full_paths, user_id, chapter_id
            )

            # Cleanup
            shutil.rmtree(temp_dir)

            return result
```

---

## 8. Pydantic Models (Phase 1 & 2)

### 8.1. Base Models

**File**: `src/models/book_chapter_models.py`

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class ContentSource(str, Enum):
    """Chapter content source types"""
    INLINE = "inline"           # HTML/JSON content
    PDF_PAGES = "pdf_pages"     # PDF → pages array
    IMAGE_PAGES = "image_pages" # Images → pages array (manga/comics)

class ElementType(str, Enum):
    """Page element types"""
    # PDF mode elements
    HIGHLIGHT = "highlight"
    TEXT = "text"
    SHAPE = "shape"
    IMAGE = "image"
    ARROW = "arrow"

    # Manga mode elements
    SPEECH_BUBBLE = "speech_bubble"
    SOUND_EFFECT = "sound_effect"
    ANNOTATION = "annotation"

class PageElement(BaseModel):
    """Element overlay on page background"""
    id: str = Field(..., description="Unique element ID")
    type: ElementType = Field(..., description="Element type")
    x: float = Field(..., description="X position (pixels)")
    y: float = Field(..., description="Y position (pixels)")
    width: Optional[float] = Field(None, description="Width (for shapes/images)")
    height: Optional[float] = Field(None, description="Height (for shapes/images)")
    z_index: int = Field(default=1, description="Layer order")

    # Type-specific properties (union type)
    color: Optional[str] = Field(None, description="Color (highlight, text, shape)")
    content: Optional[str] = Field(None, description="Text content")
    font_size: Optional[int] = Field(None, description="Font size (text)")
    src: Optional[str] = Field(None, description="Image URL (image type)")
    style: Optional[str] = Field(None, description="Style variant (speech bubble)")

class PageContent(BaseModel):
    """Single page with background and elements"""
    page_number: int = Field(..., description="Page number (1-indexed)")
    background_url: str = Field(..., description="R2 CDN URL for background image")
    width: int = Field(..., description="Page width in pixels")
    height: int = Field(..., description="Page height in pixels")
    elements: List[PageElement] = Field(default=[], description="Overlay elements")

class MangaMetadata(BaseModel):
    """Manga-specific metadata (image_pages mode only)"""
    reading_direction: str = Field(default="right-to-left", description="Reading order")
    is_colored: bool = Field(default=False, description="Colored or black & white")
    artist: Optional[str] = Field(None, description="Artist/Author name")
    genre: Optional[str] = Field(None, description="Genre (Action, Romance, etc.)")

class ChapterCreatePDFPages(BaseModel):
    """Create chapter from PDF (pdf_pages mode)"""
    file_id: Optional[str] = Field(None, description="Existing file ID from studyhub_files")
    title: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(None)
    parent_id: Optional[str] = Field(None)
    order_index: int = Field(default=0, ge=0)
    is_published: bool = Field(default=True)
    is_preview_free: bool = Field(default=False)

class ChapterCreateImagePages(BaseModel):
    """Create chapter from images (image_pages mode)"""
    file_ids: Optional[List[str]] = Field(None, description="Existing image file IDs")
    title: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(None)
    parent_id: Optional[str] = Field(None)
    order_index: int = Field(default=0, ge=0)
    is_published: bool = Field(default=True)
    is_preview_free: bool = Field(default=False)
    manga_metadata: Optional[MangaMetadata] = Field(None, description="Manga settings")

class ChapterPagesUpdate(BaseModel):
    """Update page elements (add highlights, notes, etc.)"""
    pages: List[PageContent] = Field(..., description="Pages with updated elements")
```

---

## 9. Updated Manager Methods

### 9.1. BookChapterManager Updates (Phase 1)

**File**: `src/services/book_chapter_manager.py`

```python
class GuideBookBookChapterManager:

    # ═══════════════════════════════════════════════
    # PHASE 1: PDF PAGES SUPPORT
    # ═══════════════════════════════════════════════

    async def create_chapter_from_pdf(
        self,
        book_id: str,
        user_id: str,
        file_id: str,
        title: str,
        order_index: int = 0,
        parent_id: Optional[str] = None,
        is_published: bool = True,
        is_preview_free: bool = False
    ) -> Dict[str, Any]:
        """
        Create chapter from existing PDF file (pdf_pages mode)

        Flow:
        1. Validate file exists in studyhub_files
        2. Download PDF from R2
        3. Extract pages → Upload to R2 as PNG images
        4. Create chapter with pages array
        """
        # 1. Validate file
        file_doc = self.db["studyhub_files"].find_one({
            "file_id": file_id,
            "uploaded_by": user_id,
            "deleted": {"$ne": True},
            "file_type": "application/pdf"
        })

        if not file_doc:
            raise ValueError(f"PDF file {file_id} not found or invalid")

        # 2. Download PDF from R2
        pdf_temp_path = await self._download_file_from_r2(file_doc["file_url"])

        # 3. Process PDF → pages array
        from src.services.pdf_chapter_processor import PDFChapterProcessor

        processor = PDFChapterProcessor(self.s3_client, self.r2_bucket)
        chapter_id = self._generate_chapter_id()

        pages_data = await processor.process_pdf_to_pages(
            pdf_temp_path, user_id, chapter_id, dpi=150
        )

        # 4. Create chapter document
        chapter_data = {
            "chapter_id": chapter_id,
            "book_id": book_id,
            "user_id": user_id,
            "title": title,
            "slug": self._generate_slug(title),
            "parent_id": parent_id,
            "order_index": order_index,
            "depth": self._calculate_depth(parent_id),

            # PDF pages mode
            "content_source": "pdf_pages",
            "file_id": file_id,
            "pages": pages_data["pages"],
            "total_pages": pages_data["total_pages"],
            "original_file_name": pages_data["original_file_name"],

            # Null out inline fields
            "content_html": None,
            "content_json": None,

            "is_published": is_published,
            "is_preview_free": is_preview_free,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        self.chapters_collection.insert_one(chapter_data)

        # 5. Update file's studyhub_context
        self.db["studyhub_files"].update_one(
            {"file_id": file_id},
            {"$set": {
                "studyhub_context.book_id": book_id,
                "studyhub_context.chapter_id": chapter_id
            }}
        )

  // CONTENT SOURCE: 3 modes
  "content_source": "inline" | "document" | "file",  // ⭐ NEW: "file"

  // MODE 1: INLINE (HTML content in chapter)
  "content_html": "<h1>...</h1>",
  "content_json": {...},

  // MODE 2: DOCUMENT (reference to documents collection)
  "document_id": "doc_uuid",

  // MODE 3: FILE (reference to studyhub_files collection) ⭐ NEW
  "file_id": "file_uuid",  // Links to studyhub_files._id
  "file_url": "https://cdn.wordai.pro/studyhub/files/chapter_123.pdf",
  "file_name": "chapter_3_intro_ai.pdf",
  "file_type": "application/pdf",
  "file_size": 2456789,

  // Metadata
  "is_published": true,
  "is_preview_free": false,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### 3.2. Content Source Comparison

| Mode | Storage | Content Fields | Use Case |
|------|---------|----------------|----------|
| `inline` | In chapter document | `content_html`, `content_json` | Standalone HTML chapters |
| `document` | Reference to documents | `document_id` | Reusable A4/Slide documents |
| `file` ⭐ NEW | Reference to files | `file_id`, `file_url`, `file_name`, `file_type`, `file_size` | PDF chapters |

### 3.3. File Collection Integration

**Use existing**: `studyhub_files` collection

```javascript
{
  "_id": ObjectId,
  "file_id": "file_uuid",  // Custom ID for easier reference
  "uploaded_by": "user_id",
  "file_name": "chapter_3.pdf",
  "file_type": "application/pdf",
  "file_size": 2456789,
  "file_url": "https://cdn.wordai.pro/studyhub/files/file_123.pdf",

  // StudyHub context (reuse existing pattern)
  "studyhub_context": {
    "enabled": true,
    "mode": "private",
    "subject_id": null,  // Not used for book chapters
    "module_id": null,
    "requires_enrollment": false,
    "is_preview": false,

    // NEW: Book chapter context ⭐
    "book_id": "book_uuid",
    "chapter_id": "chapter_uuid"
  },

  // File metadata
  "uploaded_at": ISODate,
  "deleted": false,
  "deleted_at": null,
  "download_count": 0,

  // Video-specific (if applicable)
  "duration": null,
  "thumbnail_url": null
}
```

---

## 4. API Design

### 4.1. New Endpoints

#### Endpoint 1: Link Existing PDF to Chapter

```
POST /api/v1/books/{book_id}/chapters/from-file
```

**Request Body**:
```json
{
  "file_id": "file_123456",
  "title": "Chapter 3: Introduction to AI",
  "slug": "chapter-3-intro-ai",  // Optional, auto-generated from title
  "parent_id": null,
  "order_index": 2,
  "is_published": true,
  "is_preview_free": false
}
```

**Response** `201 Created`:
```json
{
  "chapter_id": "chapter_abc123",
  "book_id": "book_xyz789",
  "title": "Chapter 3: Introduction to AI",
  "slug": "chapter-3-intro-ai",
  "content_source": "file",
  "file_id": "file_123456",
  "file_url": "https://cdn.wordai.pro/studyhub/files/file_123456.pdf",
  "file_name": "chapter_3.pdf",
  "file_type": "application/pdf",
  "file_size": 2456789,
  "order_index": 2,
  "is_published": true,
  "created_at": "2026-01-09T10:00:00Z"
}
```

**Validation**:
- ✅ File must exist in `studyhub_files`
- ✅ File must belong to user (`uploaded_by` check)
- ✅ File must be PDF type (`file_type = "application/pdf"`)
- ✅ File must not be deleted (`deleted != true`)
- ✅ User must own the book

---

#### Endpoint 2: Upload New PDF and Create Chapter

```
POST /api/v1/books/{book_id}/chapters/upload-pdf
```

**Request** (`multipart/form-data`):
- `file` (required) - PDF file to upload
- `title` (required) - Chapter title (1-200 chars)
- `slug` (optional) - URL slug (auto-generated if not provided)
- `parent_id` (optional) - Parent chapter ID for nesting
- `order_index` (optional, default: 0) - Display order
- `is_published` (optional, default: true) - Publish status
- `is_preview_free` (optional, default: false) - Free preview flag

**Response** `201 Created`:
```json
{
  "chapter_id": "chapter_abc123",
  "book_id": "book_xyz789",
  "title": "Chapter 3: Introduction to AI",
  "slug": "chapter-3-intro-ai",
  "content_source": "file",
  "file_id": "file_123456",
  "file_url": "https://cdn.wordai.pro/studyhub/files/file_123456.pdf",
  "file_name": "chapter_3.pdf",
  "file_type": "application/pdf",
  "file_size": 2456789,
  "order_index": 2,
  "is_published": true,
  "created_at": "2026-01-09T10:00:00Z"
}
```

**Upload Process**:
1. Validate file type (must be PDF)
2. Validate file size (max 100 MB for chapters)
3. Upload to Cloudflare R2 storage
4. Create record in `studyhub_files`
5. Create chapter with `content_source = "file"`
6. Set `studyhub_context` on file

**Validation**:
- ✅ File must be PDF (`application/pdf`)
- ✅ Max file size: 100 MB
- ✅ User must own the book
- ✅ Chapter slug must be unique in book

---

### 4.2. Updated Existing Endpoints

#### GET Chapter with Content

```
GET /api/v1/books/{book_id}/chapters/{chapter_id}
```

**Current Response** (HTML chapter):
```json
{
  "chapter_id": "chapter_abc123",
  "content_source": "inline",
  "content_html": "<h1>Chapter content...</h1>",
  "content_json": {...}
}
```

**New Response** (PDF chapter):
```json
{
  "chapter_id": "chapter_abc123",
  "content_source": "file",
  "file_id": "file_123456",
  "file_url": "https://cdn.wordai.pro/studyhub/files/file_123456.pdf",
  "file_name": "chapter_3.pdf",
  "file_type": "application/pdf",
  "file_size": 2456789,
  "file_details": {
    "uploaded_at": "2026-01-08T15:30:00Z",
    "uploaded_by": "user_123",
    "download_count": 45
  }
}
```

---

## 5. Implementation Plan

### 5.1. Database Changes

**No schema changes needed!** MongoDB is schemaless.

Just add new fields to chapters when `content_source = "file"`:
- `file_id`
- `file_url`
- `file_name`
- `file_type`
- `file_size`

### 5.2. Manager Updates

**File**: `src/services/book_chapter_manager.py`

```python
class GuideBookBookChapterManager:

    # NEW METHOD 1: Create chapter from existing file
    def create_chapter_from_file(
        self,
        book_id: str,
        file_id: str,
        title: str,
        slug: Optional[str] = None,
        order_index: int = 0,
        parent_id: Optional[str] = None,
        is_published: bool = True,
        is_preview_free: bool = False,
    ) -> Dict[str, Any]:
        """
        Create chapter that references a PDF file

        Args:
            book_id: Book UUID
            file_id: File ID from studyhub_files
            title: Chapter title
            slug: URL slug (auto-generated if not provided)
            order_index: Position in chapter list
            parent_id: Parent chapter for nesting
            is_published: Publish status
            is_preview_free: Free preview flag

        Returns:
            Created chapter document

        Raises:
            ValueError: If file not found, not PDF, or not owned by user
        """
        # 1. Verify file exists and is PDF
        file_doc = self.db.studyhub_files.find_one({
            "_id": ObjectId(file_id),
            "deleted": {"$ne": True},
            "file_type": "application/pdf"
        })

        if not file_doc:
            raise ValueError("PDF file not found or invalid")

        # 2. Verify user owns file
        if file_doc.get("uploaded_by") != user_id:
            raise ValueError("You don't own this file")

        # 3. Generate slug if not provided
        if not slug:
            slug = self._generate_slug(title)

        # 4. Calculate depth
        depth = self._calculate_depth(book_id, parent_id)

        # 5. Create chapter document
        chapter_id = f"chapter_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        chapter_doc = {
            "chapter_id": chapter_id,
            "book_id": book_id,
            "parent_id": parent_id,
            "title": title,
            "slug": slug,
            "order_index": order_index,
            "depth": depth,

            # FILE content mode
            "content_source": "file",
            "file_id": file_id,
            "file_url": file_doc.get("file_url"),
            "file_name": file_doc.get("file_name"),
            "file_type": file_doc.get("file_type"),
            "file_size": file_doc.get("file_size"),

            # No HTML content
            "content_html": None,
            "content_json": None,
            "document_id": None,

            # Metadata
            "is_published": is_published,
            "is_preview_free": is_preview_free,
            "created_at": now,
            "updated_at": now,
        }

        # 6. Insert chapter
        self.chapters_collection.insert_one(chapter_doc)

        # 7. Update file's studyhub_context
        self.db.studyhub_files.update_one(
            {"_id": ObjectId(file_id)},
            {
                "$set": {
                    "studyhub_context.enabled": True,
                    "studyhub_context.book_id": book_id,
                    "studyhub_context.chapter_id": chapter_id,
                }
            }
        )

        # 8. Update book timestamp
        self.book_manager.touch_book(book_id)

        return chapter_doc


    # NEW METHOD 2: Upload PDF and create chapter
    async def upload_pdf_and_create_chapter(
        self,
        book_id: str,
        file: UploadFile,
        title: str,
        slug: Optional[str] = None,
        order_index: int = 0,
        parent_id: Optional[str] = None,
        is_published: bool = True,
        is_preview_free: bool = False,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Upload PDF file and create chapter

        Args:
            book_id: Book UUID
            file: Uploaded PDF file
            title: Chapter title
            slug: URL slug
            order_index: Position
            parent_id: Parent chapter
            is_published: Publish status
            is_preview_free: Free preview
            user_id: User ID

        Returns:
            Created chapter with file info
        """
        # 1. Validate file type
        if file.content_type != "application/pdf":
            raise ValueError("Only PDF files are allowed")

        # 2. Validate file size (max 100 MB)
        MAX_SIZE = 100 * 1024 * 1024  # 100 MB
        file_content = await file.read()
        if len(file_content) > MAX_SIZE:
            raise ValueError("File size exceeds 100 MB limit")

        # 3. Upload to R2 storage (implementation pending)
        # TODO: Implement R2 upload
        # file_id, file_url = await upload_to_r2(file_content, file.filename)

        # TEMPORARY: Save file metadata without actual upload
        file_id = f"file_{uuid.uuid4().hex[:12]}"
        file_url = f"https://cdn.wordai.pro/studyhub/files/{file_id}.pdf"

        # 4. Create file record in studyhub_files
        file_doc = {
            "_id": ObjectId(),
            "file_id": file_id,
            "uploaded_by": user_id,
            "file_name": file.filename,
            "file_type": file.content_type,
            "file_size": len(file_content),
            "file_url": file_url,
            "uploaded_at": datetime.now(timezone.utc),
            "deleted": False,
            "download_count": 0,
            "studyhub_context": {
                "enabled": False,  # Will be set when chapter created
                "book_id": None,
                "chapter_id": None,
            }
        }

        result = self.db.studyhub_files.insert_one(file_doc)
        file_id_str = str(result.inserted_id)

        # 5. Create chapter using existing method
        chapter = self.create_chapter_from_file(
            book_id=book_id,
            file_id=file_id_str,
            title=title,
            slug=slug,
            order_index=order_index,
            parent_id=parent_id,
            is_published=is_published,
            is_preview_free=is_preview_free,
        )

        return chapter


    # UPDATE EXISTING METHOD: get_chapter_with_content
    def get_chapter_with_content(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """
        Get chapter with content (handles inline, document, and file modes)
        """
        chapter = self.chapters_collection.find_one(
            {"chapter_id": chapter_id}, {"_id": 0}
        )

        if not chapter:
            return None

        content_source = chapter.get("content_source", "inline")

        if content_source == "document":
            # Load from documents collection (existing logic)
            # ...

        elif content_source == "file":
            # NEW: Enrich with file details
            file_id = chapter.get("file_id")
            if file_id:
                file_doc = self.db.studyhub_files.find_one(
                    {"_id": ObjectId(file_id)}
                )
                if file_doc:
                    chapter["file_details"] = {
                        "uploaded_at": file_doc.get("uploaded_at"),
                        "uploaded_by": file_doc.get("uploaded_by"),
                        "download_count": file_doc.get("download_count", 0),
                    }

        else:  # inline
            # Existing logic
            # ...

        return chapter
```

### 5.3. Route Additions

**File**: `src/api/book_chapter_routes.py`

```python
from fastapi import UploadFile, File

# NEW ROUTE 1: Link existing PDF
@router.post(
    "/{book_id}/chapters/from-file",
    response_model=ChapterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_chapter_from_file(
    book_id: str,
    request: ChapterFromFileRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create chapter from existing PDF file

    - Links file from studyhub_files collection
    - File must be PDF and belong to user
    - Sets content_source = "file"
    """
    user_id = current_user["uid"]

    # Verify book ownership
    book = book_manager.get_book(book_id)
    if not book or book.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not book owner")

    try:
        chapter = chapter_manager.create_chapter_from_file(
            book_id=book_id,
            file_id=request.file_id,
            title=request.title,
            slug=request.slug,
            order_index=request.order_index,
            parent_id=request.parent_id,
            is_published=request.is_published,
            is_preview_free=request.is_preview_free,
        )

        return chapter

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# NEW ROUTE 2: Upload PDF and create chapter
@router.post(
    "/{book_id}/chapters/upload-pdf",
    response_model=ChapterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_pdf_chapter(
    book_id: str,
    file: UploadFile = File(...),
    title: str = Form(...),
    slug: Optional[str] = Form(None),
    order_index: int = Form(0),
    parent_id: Optional[str] = Form(None),
    is_published: bool = Form(True),
    is_preview_free: bool = Form(False),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Upload PDF file and create chapter

    - Accepts multipart/form-data
    - Max file size: 100 MB
    - File must be PDF type
    - Uploads to R2 storage
    """
    user_id = current_user["uid"]

    # Verify book ownership
    book = book_manager.get_book(book_id)
    if not book or book.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not book owner")

    try:
        chapter = await chapter_manager.upload_pdf_and_create_chapter(
            book_id=book_id,
            file=file,
            title=title,
            slug=slug,
            order_index=order_index,
            parent_id=parent_id,
            is_published=is_published,
            is_preview_free=is_preview_free,
            user_id=user_id,
        )

        return chapter

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 5.4. Model Additions

**File**: `src/models/book_chapter_models.py`

```python
class ChapterFromFileRequest(BaseModel):
    """Request to create chapter from existing file"""

    file_id: str = Field(..., description="File ID from studyhub_files")
    title: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=200)
    parent_id: Optional[str] = None
    order_index: int = Field(default=0, ge=0)
    is_published: bool = True
    is_preview_free: bool = False
```

---

## 6. Validation Rules

### 6.1. File Validation

| Rule | Value | Error Message |
|------|-------|---------------|
| File type | `application/pdf` only | "Only PDF files are allowed" |
| Max file size | 100 MB | "File size exceeds 100 MB limit" |
| File ownership | `uploaded_by = current_user` | "You don't own this file" |
| File deleted | `deleted != true` | "File has been deleted" |

### 6.2. Chapter Validation

| Rule | Validation |
|------|------------|
| Slug uniqueness | Must be unique within book |
| Max depth | 3 levels (0, 1, 2) |
| Parent exists | Parent chapter must exist in same book |
| Book ownership | User must own the book |

---

## 7. Frontend Integration

### 7.1. Chapter Display Logic

```javascript
// Frontend component logic
function renderChapterContent(chapter) {
  const contentSource = chapter.content_source;

  switch (contentSource) {
    case 'inline':
      // Render HTML content
      return <div dangerouslySetInnerHTML={{ __html: chapter.content_html }} />;

    case 'document':
      // Load from document (same as inline after loading)
      return <div dangerouslySetInnerHTML={{ __html: chapter.content_html }} />;

    case 'file':
      // NEW: Render PDF viewer
      return (
        <div className="pdf-viewer">
          <iframe
            src={chapter.file_url}
            title={chapter.title}
            width="100%"
            height="800px"
          />
          <div className="file-info">
            <p>File: {chapter.file_name}</p>
            <p>Size: {formatFileSize(chapter.file_size)}</p>
            <a href={chapter.file_url} download>Download PDF</a>
          </div>
        </div>
      );

    default:
      return <p>Unsupported content type</p>;
  }
}
```

### 7.2. Chapter Creation Flow

**Option 1: Link Existing PDF**
```javascript
// 1. List user's PDF files
GET /api/studyhub/files?file_type=application/pdf

// 2. Select file and create chapter
POST /api/v1/books/{book_id}/chapters/from-file
Body: {
  file_id: "file_123",
  title: "Chapter 3",
  order_index: 2
}
```

**Option 2: Upload New PDF**
```javascript
// Single request with multipart/form-data
POST /api/v1/books/{book_id}/chapters/upload-pdf
FormData: {
  file: <PDF File>,
  title: "Chapter 3",
  order_index: 2
}
```

---

## 8. Database Indexes

### 8.1. Existing Indexes
```javascript
// book_chapters collection
db.book_chapters.createIndex({ "chapter_id": 1 }, { unique: true });
db.book_chapters.createIndex({ "book_id": 1, "slug": 1 }, { unique: true });
db.book_chapters.createIndex({ "book_id": 1, "order_index": 1 });
```

### 8.2. New Indexes Needed
```javascript
// For file-based chapters
db.book_chapters.createIndex({ "content_source": 1, "file_id": 1 });
db.book_chapters.createIndex({ "book_id": 1, "content_source": 1 });

// For studyhub_files
db.studyhub_files.createIndex({ "studyhub_context.book_id": 1 });
db.studyhub_files.createIndex({ "studyhub_context.chapter_id": 1 });
```

---

## 9. Migration Strategy

### 9.1. No Database Migration Needed

✅ **Backward compatible**: Existing chapters continue to work
- Old chapters have `content_source = "inline"` or `"document"`
- New PDF chapters have `content_source = "file"`
- All old code paths still work

### 9.2. Deployment Steps

1. Deploy new manager methods
2. Deploy new API routes
3. Update frontend to handle `content_source = "file"`
4. Add new MongoDB indexes
5. Test with PDF upload

---

## 10. Testing Plan

### 10.1. Unit Tests

```python
def test_create_chapter_from_file():
    """Test linking existing PDF to chapter"""
    chapter = chapter_manager.create_chapter_from_file(
        book_id="book_123",
        file_id="file_456",
        title="Chapter 3",
    )
    assert chapter["content_source"] == "file"
    assert chapter["file_id"] == "file_456"

def test_upload_pdf_chapter():
    """Test uploading PDF and creating chapter"""
    with open("test.pdf", "rb") as f:
        chapter = await chapter_manager.upload_pdf_and_create_chapter(
            book_id="book_123",
            file=f,
            title="Chapter 3",
            user_id="user_abc",
        )
    assert chapter["content_source"] == "file"
    assert chapter["file_type"] == "application/pdf"

def test_get_chapter_with_file_content():
    """Test retrieving PDF chapter with file details"""
    chapter = chapter_manager.get_chapter_with_content("chapter_123")
    assert "file_details" in chapter
    assert "file_url" in chapter
```

### 10.2. Integration Tests

- Create book → Upload PDF chapter → Retrieve chapter → Verify PDF URL
- Link existing PDF → Update chapter metadata → Verify changes
- Delete chapter → Verify file soft delete

---

## 11. Security Considerations

### 11.1. File Upload Security

| Risk | Mitigation |
|------|-----------|
| Malicious PDFs | Virus scanning on upload (future) |
| Large files (DoS) | Max size limit: 100 MB |
| Unauthorized access | File ownership check (`uploaded_by`) |
| Path traversal | Use generated file IDs, not user filenames |

### 11.2. Permission Checks

✅ **Book ownership**: User must own book to add chapters
✅ **File ownership**: User must own file to link
✅ **Chapter editing**: Only book owner can edit
✅ **Public access**: Respect `is_published` and `is_preview_free` flags

---

## 12. Future Enhancements

### 12.1. Phase 2 Features

- **PDF Processing**: Extract text for search indexing
- **Thumbnail Generation**: Generate PDF preview thumbnails
- **Page Count**: Store and display PDF page count
- **PDF Viewer**: Embedded PDF viewer with annotations
- **Multi-file Chapters**: Support multiple files per chapter

### 12.2. Additional File Types

After PDF support is stable, consider:
- Word documents (`.docx`)
- PowerPoint (`.pptx`)
- ePub files
- Audio files (`.mp3`)
- Video files (`.mp4`)

---

## 13. Summary

### ✅ **Architecture Ready**

**Current System**:
- Chapters support HTML (`inline`) and Document references (`document`)
- Clean separation of content storage models
- Flexible `content_source` field

**Proposed Enhancement**:
- Add 3rd mode: `content_source = "file"`
- Reuse existing `studyhub_files` collection
- 2 ways to add PDF: link existing OR upload new
- Backward compatible (no breaking changes)

**Implementation Effort**:
- Manager: 2 new methods + 1 update (~150 lines)
- Routes: 2 new endpoints (~100 lines)
- Models: 1 new request model (~10 lines)
- Frontend: Update chapter renderer to handle PDF
- Total: ~260 lines of code

**Ready to implement**: Yes ✅

---

**Document Version**: 1.0
**Last Updated**: January 9, 2026
**Status**: Architecture Design Complete
**Next Step**: Implement manager methods and routes
