# Phase 4: Advanced Features - Implementation Plan

## Overview

Phase 4 adds advanced capabilities to the multi-format book chapter system, including performance optimizations, export features, and analytics.

## Features

### 1. Lazy Loading for Large Books

**Problem**: Books with 500+ pages load slowly

**Solution**: Paginated page loading

#### API Endpoint

```python
@router.get("/chapters/{chapter_id}/pages/range")
async def get_chapter_pages_range(
    chapter_id: str,
    start_page: int = 1,
    end_page: Optional[int] = None,
    page_size: int = 10,
    current_user = Depends(get_current_user)
):
    """
    Get a range of pages (for lazy loading)

    Returns: {
        "pages": [...],  # Pages [start_page, end_page]
        "total_pages": 500,
        "has_more": true
    }
    """
```

#### Database Optimization

```javascript
// Index for faster page queries
db.book_chapters.createIndex({
  "_id": 1,
  "pages.page_number": 1
})

// Projection query (only fetch needed pages)
db.book_chapters.findOne(
  { _id: chapter_id },
  {
    title: 1,
    total_pages: 1,
    pages: { $slice: [startPage - 1, pageSize] }
  }
)
```

#### Frontend Implementation

```javascript
// React lazy loading
const ChapterViewer = () => {
  const [pages, setPages] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);

  const loadMorePages = async () => {
    const response = await fetch(
      `/api/v1/books/chapters/${chapterId}/pages/range?start_page=${currentPage}&page_size=10`
    );
    const data = await response.json();
    setPages([...pages, ...data.pages]);
  };

  // Infinite scroll or pagination
};
```

---

### 2. Thumbnail Generation

**Problem**: Page previews take bandwidth

**Solution**: Generate thumbnails on upload

#### Service Method

```python
# In PDFChapterProcessor / ImageChapterProcessor
async def _generate_thumbnail(
    self,
    image: Image.Image,
    max_width: int = 200,
    max_height: int = 300
) -> Image.Image:
    """Generate thumbnail preserving aspect ratio"""

    # Calculate thumbnail size
    ratio = min(max_width / image.width, max_height / image.height)
    new_size = (int(image.width * ratio), int(image.height * ratio))

    # Resize with high quality
    thumbnail = image.resize(new_size, Image.LANCZOS)

    return thumbnail
```

#### Database Schema

```javascript
// Add thumbnails to pages
{
  "pages": [
    {
      "page_number": 1,
      "background_url": "https://cdn.wordai.com/.../page-1.jpg",
      "thumbnail_url": "https://cdn.wordai.com/.../page-1-thumb.jpg",  // NEW
      "width": 1240,
      "height": 1754,
      "thumbnail_width": 138,  // NEW
      "thumbnail_height": 200,  // NEW
      "elements": []
    }
  ]
}
```

#### API Update

```python
# GET /chapters/{id}/thumbnails
@router.get("/chapters/{chapter_id}/thumbnails")
async def get_chapter_thumbnails(chapter_id: str):
    """
    Get all page thumbnails for quick preview

    Returns: {
        "thumbnails": [
            {"page": 1, "url": "...", "width": 138, "height": 200},
            ...
        ]
    }
    """
```

---

### 3. Export Features

**Problem**: Users want to download annotated content

**Solution**: Export to PDF/CBZ with annotations

#### PDF Export (with Annotations)

```python
# src/services/chapter_export_service.py
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PyPDF2 import PdfReader, PdfWriter

class ChapterExportService:
    """Export chapters to various formats"""

    async def export_to_pdf(
        self,
        chapter_id: str,
        include_annotations: bool = True
    ) -> bytes:
        """
        Export chapter to PDF with annotations

        Process:
        1. Load chapter pages
        2. Download background images
        3. Create PDF with ReportLab
        4. Draw annotations (highlights, text, shapes)
        5. Return PDF bytes
        """

        # Get chapter
        chapter = await self.get_chapter(chapter_id)

        # Create PDF
        pdf_buffer = io.BytesIO()
        pdf = canvas.Canvas(pdf_buffer, pagesize=A4)

        for page in chapter["pages"]:
            # Draw background image
            img_path = await self.download_temp_image(page["background_url"])
            pdf.drawImage(img_path, 0, 0, width=A4[0], height=A4[1])

            if include_annotations:
                # Draw elements
                for element in page.get("elements", []):
                    self._draw_element(pdf, element)

            pdf.showPage()

        pdf.save()
        return pdf_buffer.getvalue()

    def _draw_element(self, pdf: canvas.Canvas, element: Dict):
        """Draw element on PDF canvas"""

        if element["type"] == "highlight":
            pdf.setFillColorRGB(*self._hex_to_rgb(element["color"]))
            pdf.setAlpha(0.3)
            pdf.rect(
                element["x"], element["y"],
                element["width"], element["height"],
                fill=1, stroke=0
            )

        elif element["type"] == "text":
            pdf.setFillColorRGB(0, 0, 0)
            pdf.setFont("Helvetica", element.get("font_size", 12))
            pdf.drawString(
                element["x"], element["y"],
                element.get("content", "")
            )

        # ... other element types
```

#### CBZ Export (for Manga)

```python
async def export_to_cbz(
    self,
    chapter_id: str,
    include_annotations: bool = False
) -> bytes:
    """
    Export manga chapter to CBZ (Comic Book ZIP)

    CBZ format:
    - ZIP archive containing JPG/PNG images
    - Images named: 001.jpg, 002.jpg, ...
    - Optional ComicInfo.xml metadata
    """

    chapter = await self.get_chapter(chapter_id)

    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:

        # Add images
        for idx, page in enumerate(chapter["pages"], 1):
            img_data = await self.download_image_bytes(page["background_url"])
            zip_file.writestr(f"{idx:03d}.jpg", img_data)

        # Add ComicInfo.xml
        comic_info = self._generate_comic_info(chapter)
        zip_file.writestr("ComicInfo.xml", comic_info)

    return zip_buffer.getvalue()
```

#### API Endpoints

```python
@router.get("/chapters/{chapter_id}/export/pdf")
async def export_chapter_pdf(
    chapter_id: str,
    include_annotations: bool = True,
    current_user = Depends(get_current_user)
):
    """Export chapter to PDF"""

    pdf_bytes = await export_service.export_to_pdf(
        chapter_id, include_annotations
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=chapter-{chapter_id}.pdf"
        }
    )

@router.get("/chapters/{chapter_id}/export/cbz")
async def export_chapter_cbz(
    chapter_id: str,
    current_user = Depends(get_current_user)
):
    """Export manga chapter to CBZ"""

    cbz_bytes = await export_service.export_to_cbz(chapter_id)

    return Response(
        content=cbz_bytes,
        media_type="application/x-cbz",
        headers={
            "Content-Disposition": f"attachment; filename=chapter-{chapter_id}.cbz"
        }
    )
```

---

### 4. Analytics & Tracking

**Problem**: No insight into user reading behavior

**Solution**: Page view analytics

#### Database Schema

```javascript
// New collection: page_views
{
  "_id": ObjectId(),
  "user_id": "user123",
  "book_id": "book456",
  "chapter_id": "chapter789",
  "page_number": 42,
  "viewed_at": ISODate("2026-01-09T10:00:00Z"),
  "duration_seconds": 15,  // Time spent on page
  "device": "mobile",
  "user_agent": "..."
}

// Indexes
db.page_views.createIndex({ user_id: 1, chapter_id: 1, page_number: 1 });
db.page_views.createIndex({ viewed_at: 1 });
```

#### API Endpoint

```python
@router.post("/chapters/{chapter_id}/pages/{page_number}/view")
async def track_page_view(
    chapter_id: str,
    page_number: int,
    duration_seconds: Optional[int] = None,
    current_user = Depends(get_current_user)
):
    """Track page view"""

    await analytics_service.track_page_view(
        user_id=current_user["uid"],
        chapter_id=chapter_id,
        page_number=page_number,
        duration_seconds=duration_seconds
    )

    return {"success": True}

@router.get("/chapters/{chapter_id}/analytics")
async def get_chapter_analytics(
    chapter_id: str,
    current_user = Depends(get_current_user)
):
    """
    Get chapter reading analytics

    Returns: {
        "total_views": 1523,
        "unique_readers": 42,
        "avg_completion_rate": 0.65,
        "popular_pages": [1, 5, 12],
        "avg_time_per_page": 18.5,
        "page_stats": [
            {"page": 1, "views": 100, "avg_duration": 20},
            ...
        ]
    }
    """
```

#### Frontend Integration

```javascript
// Track page view when user stays on page
useEffect(() => {
  const startTime = Date.now();

  return () => {
    const duration = Math.floor((Date.now() - startTime) / 1000);

    fetch(`/api/v1/books/chapters/${chapterId}/pages/${pageNumber}/view`, {
      method: 'POST',
      body: JSON.stringify({ duration_seconds: duration })
    });
  };
}, [pageNumber]);
```

---

### 5. Search & Full-Text Indexing

**Problem**: Can't search within pages

**Solution**: OCR for PDF pages + text indexing

#### OCR Implementation

```python
# Use Tesseract OCR or Google Vision API
from PIL import Image
import pytesseract

async def extract_text_from_page(
    self,
    page_image_url: str
) -> str:
    """Extract text from page image using OCR"""

    # Download image
    image = await self.download_image(page_image_url)

    # Run OCR
    text = pytesseract.image_to_string(image, lang='eng+jpn')

    return text
```

#### Database Schema

```javascript
// Add searchable text to pages
{
  "pages": [
    {
      "page_number": 1,
      "background_url": "...",
      "text_content": "Extracted text from OCR...",  // NEW
      "elements": []
    }
  ]
}

// Text index for search
db.book_chapters.createIndex({
  "pages.text_content": "text",
  "title": "text"
});
```

#### Search API

```python
@router.get("/books/{book_id}/search")
async def search_book(
    book_id: str,
    query: str,
    current_user = Depends(get_current_user)
):
    """
    Search within book pages

    Returns: {
        "results": [
            {
                "chapter_id": "...",
                "chapter_title": "Chapter 1",
                "page_number": 5,
                "preview": "...highlighted text...",
                "score": 0.95
            }
        ]
    }
    """
```

---

## Implementation Priority

### High Priority (2-3 weeks)
1. **Lazy Loading** - Critical for large books
2. **Thumbnail Generation** - Improves UX significantly

### Medium Priority (2-3 weeks)
3. **PDF Export** - User-requested feature
4. **Analytics** - Business intelligence

### Low Priority (1-2 weeks)
5. **CBZ Export** - Niche feature for manga
6. **Full-Text Search** - Nice-to-have

## Dependencies

```txt
# requirements.txt additions

# For PDF export
reportlab==4.0.7
PyPDF2==3.0.1

# For OCR (optional)
pytesseract==0.3.10
# Also requires: apt-get install tesseract-ocr

# For image processing (already have PIL/Pillow)
```

## Testing Strategy

### Unit Tests
- Thumbnail generation quality
- PDF export with annotations
- CBZ archive structure
- Analytics calculations

### Integration Tests
- Lazy loading pagination
- Export file downloads
- Search accuracy
- Analytics tracking

### Performance Tests
- Lazy loading speed (500+ pages)
- Thumbnail generation time
- Export generation time
- Search query speed

## Rollout Plan

**Week 1**: Lazy Loading
- Implement pagination API
- Update frontend
- Performance testing

**Week 2**: Thumbnails
- Generate on upload
- Backfill existing chapters
- Frontend integration

**Week 3**: Export Features
- PDF export with annotations
- CBZ export for manga
- Download endpoints

**Week 4**: Analytics
- Track page views
- Analytics dashboard
- Insights API

**Week 5+**: Search (optional)
- OCR integration
- Text indexing
- Search API

---

## Success Metrics

- ✅ Large books (500+ pages) load in <2 seconds
- ✅ Thumbnail generation adds <5% to upload time
- ✅ PDF export completes in <10 seconds for 100 pages
- ✅ Analytics track 95%+ of page views
- ✅ Search finds relevant pages with 80%+ accuracy

---

**Last Updated**: January 9, 2026
**Status**: Phase 4 - Planning Complete, Ready for Implementation
