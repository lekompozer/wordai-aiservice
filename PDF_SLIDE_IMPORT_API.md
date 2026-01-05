# PDF Slide Import API Documentation

## Overview

Import existing PDF presentations as image-based slides. Each PDF page becomes a slide with the page rendered as a background image.

**Feature Type:** FREE (no AI processing, no points deducted)

---

## Use Case

**Problem:** User has beautifully designed PDF slides but AI text extraction loses formatting, design, and layout.

**Solution:** Convert each PDF page to high-quality image → Use as slide background → Preserve original design perfectly.

**Perfect for:**
- Marketing presentations with custom branding
- Template-based slides with specific layouts
- Slides with complex graphics, charts, diagrams
- Presentations where visual design is critical

---

## API Endpoint

### POST `/api/slides/ai-generate/import-from-pdf`

Import PDF presentation as image-based slides.

**Authentication:** Required (Firebase token)

**Content-Type:** `application/json`

---

## Request Format

### Query Parameters

| Parameter | Type   | Required | Description                              |
|-----------|--------|----------|------------------------------------------|
| `file_id` | string | ✅ Yes    | File ID from `/api/files/upload`        |
| `title`   | string | ✅ Yes    | Title for the imported slide document   |

### Request Body

```json
{
  "file_id": "file_abc123xyz",
  "title": "Q4 Marketing Strategy"
}
```

### File Requirements

- **Format:** PDF only (`.pdf`)
- **Max Size:** 20 MB
- **Upload Method:** Must upload via `/api/files/upload` first to get `file_id`
- **Validation:** Backend checks file exists, is PDF, and belongs to requesting user

---

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "document_id": "doc_06de72fea3d7",
  "num_slides": 25,
  "title": "Q4 Marketing Strategy",
  "message": "Successfully imported 25 slides from PDF. Each page is now a slide background."
}
```

### Response Fields

| Field         | Type    | Description                                    |
|---------------|---------|------------------------------------------------|
| `success`     | boolean | Always `true` on success                       |
| `document_id` | string  | Document ID - use for editing/viewing slides   |
| `num_slides`  | integer | Number of pages/slides imported                |
| `title`       | string  | Document title (same as request)               |
| `message`     | string  | Human-readable success message                 |

---

## Error Responses

### 400 Bad Request - Invalid File Type

```json
{
  "detail": "Invalid file type: .docx. Only PDF files are supported."
}
```

### 404 Not Found - File Not Found

```json
{
  "detail": "File not found or you don't have access"
}
```

### 500 Internal Server Error - Conversion Failed

```json
{
  "detail": "Failed to convert PDF to images: [error details]"
}
```

---

## Processing Flow

### Backend Process

1. **Validate Request**
   - Check user authentication
   - Verify file exists in MongoDB
   - Confirm file type is PDF
   - Validate file belongs to user

2. **Download PDF**
   - Download PDF from R2 storage to temp file
   - Use existing `FileDownloadService`

3. **Convert Pages to Images**
   - Use PyMuPDF library (150 DPI resolution)
   - Each page → PNG image
   - Maintains aspect ratio and quality

4. **Upload Images to R2**
   - Upload each image to R2 storage
   - Path: `files/{user_id}/slide_import/{file_id}/page-{N}.png`
   - Generate CDN URLs for each image

5. **Create Document**
   - Create slide document in MongoDB
   - Type: `slide`
   - Generation type: `pdf_import`
   - Each slide has empty HTML content
   - Background: Image URL for corresponding page

6. **Cleanup**
   - Delete temporary PDF file
   - Return document_id to frontend

### Processing Time

- **Small PDFs (1-10 pages):** ~5-10 seconds
- **Medium PDFs (11-30 pages):** ~15-30 seconds
- **Large PDFs (31-50 pages):** ~30-60 seconds

**Note:** Processing is synchronous - frontend waits for completion (not queued like AI generation)

---

## Document Structure

### Slide Backgrounds

Each slide has an image background:

```json
{
  "slide_backgrounds": [
    {
      "type": "image",
      "imageUrl": "https://cdn.r2.dev/files/user123/slide_import/file_abc/page-1.png"
    },
    {
      "type": "image",
      "imageUrl": "https://cdn.r2.dev/files/user123/slide_import/file_abc/page-2.png"
    }
  ]
}
```

### Slide HTML Content

Each slide has minimal HTML (empty by default):

```html
<div class="slide" data-slide-number="0">
  <!-- Slide 1: Background image only -->
</div>

<div class="slide" data-slide-number="1">
  <!-- Slide 2: Background image only -->
</div>
```

**User can later:**
- Add text overlays via slide editor
- Add interactive elements
- Customize backgrounds
- Edit/replace individual slide backgrounds

---

## Frontend Integration

### Step 1: Upload PDF

```
POST /api/files/upload
→ Returns: { file_id: "file_abc123" }
```

### Step 2: Import as Slides

```
POST /api/slides/ai-generate/import-from-pdf
Body: { file_id: "file_abc123", title: "My Presentation" }
→ Returns: { document_id: "doc_xyz", num_slides: 25 }
```

### Step 3: Redirect to Editor

```
Navigate to: /slides/edit/{document_id}
```

---

## UI/UX Recommendations

### Upload Flow

1. **File Selection**
   - Show file picker for PDF only
   - Display file name and size
   - Preview first page if possible

2. **Processing Indicator**
   - Show loading spinner during conversion
   - Display progress message: "Converting PDF pages to images... (page X/Y)"
   - Estimated time based on page count

3. **Success State**
   - Show success message with slide count
   - Preview first 3-5 slides as thumbnails
   - "Edit Slides" button → Redirect to editor

4. **Error Handling**
   - Clear error messages for user
   - Suggest solutions (e.g., "File too large, try reducing PDF size")
   - Allow retry with different file

### User Benefits to Highlight

- ✅ **Preserve Design** - Original PDF formatting stays perfect
- ✅ **Quick Import** - No manual slide recreation needed
- ✅ **Editable** - Add text overlays and elements later
- ✅ **Free** - No points deducted (unlike AI generation)

---

## Comparison: Import vs AI Analysis

| Feature                  | PDF Import (New)           | AI Analysis (Existing)     |
|--------------------------|----------------------------|----------------------------|
| **Cost**                 | FREE (0 points)            | 2 points                   |
| **Processing**           | Image conversion           | AI text extraction         |
| **Output**               | Image backgrounds          | Structured text content    |
| **Design Preservation**  | 100% accurate              | Lost (text only)           |
| **Editability**          | Add overlays later         | Full HTML content          |
| **Best For**             | Designed presentations     | Text-heavy documents       |
| **Speed**                | Fast (~30s for 30 pages)   | Slower (AI processing)     |

---

## Technical Details

### Image Quality

- **DPI:** 150 (good balance of quality and file size)
- **Format:** PNG (lossless, supports transparency)
- **Optimization:** Enabled (reduces file size ~20-30%)

### Image Storage

- **Location:** Cloudflare R2
- **CDN:** Public URLs with caching
- **Path Pattern:** `files/{user_id}/slide_import/{file_id}/page-{N}.png`
- **Retention:** Permanent (until document deleted)

### Document Metadata

```json
{
  "document_id": "doc_xyz",
  "doc_type": "slide",
  "ai_generation_type": "pdf_import",
  "source_file_id": "file_abc123",
  "slide_count": 25,
  "created_at": "2026-01-05T10:30:00Z"
}
```

---

## Limitations & Constraints

### File Size

- **Max PDF Size:** 20 MB
- **Max Pages:** No hard limit (recommended max 50 pages)
- **Reason:** Processing time and storage constraints

### PDF Requirements

- **Standard PDFs:** Work perfectly
- **Scanned PDFs:** Work but may have lower quality
- **Protected PDFs:** May fail if encryption prevents rendering
- **Form PDFs:** Interactive elements not preserved (rendered as static)

### Browser Compatibility

- Images use standard `<img>` tags or CSS backgrounds
- Works in all modern browsers
- Mobile-friendly (images are responsive)

---

## Example Use Cases

### 1. Marketing Team

**Scenario:** Marketing team has Q4 strategy deck with custom branding, charts, and infographics.

**Flow:**
1. Upload `Q4_Strategy.pdf` (35 pages)
2. Import to slides → 35 slides with original design
3. Add speaker notes as text overlays
4. Present with preserved branding

### 2. Sales Presentations

**Scenario:** Sales rep has product demo slides with screenshots and pricing tables.

**Flow:**
1. Upload `Product_Demo.pdf` (12 pages)
2. Import → Keep all visual elements intact
3. Add custom text for specific client
4. Export or present directly

### 3. Template Conversion

**Scenario:** Designer created templates in PowerPoint → Exported to PDF → Import to platform.

**Flow:**
1. Export PowerPoint → PDF
2. Import to platform
3. Distribute template to team
4. Team adds content via overlays

---

## Support & Troubleshooting

### Common Issues

**Issue:** "PDF has no pages or conversion failed"
- **Cause:** Corrupted PDF or unsupported PDF version
- **Solution:** Re-export PDF from source application

**Issue:** "Failed to download PDF from R2"
- **Cause:** File was deleted or R2 connection issue
- **Solution:** Re-upload PDF file

**Issue:** "Slow processing for large PDFs"
- **Cause:** High page count (>40 pages)
- **Solution:** Split PDF into smaller chunks or wait for completion

---

## Future Enhancements (Roadmap)

### Phase 1 (Current)
- ✅ Basic PDF page → Image conversion
- ✅ R2 storage integration
- ✅ Document creation

### Phase 2 (Planned)
- 🔄 Async processing with queue (for large PDFs)
- 🔄 Progress tracking endpoint
- 🔄 Custom DPI selection (user chooses quality)

### Phase 3 (Future)
- 📋 OCR text extraction (for searchability)
- 📋 Automatic element detection (identify text regions)
- 📋 Batch import (multiple PDFs at once)

---

## API Status Codes

| Code | Meaning              | When It Happens                          |
|------|----------------------|------------------------------------------|
| 200  | OK                   | Successfully imported PDF                |
| 400  | Bad Request          | Invalid file type or corrupted PDF       |
| 401  | Unauthorized         | Missing or invalid auth token            |
| 404  | Not Found            | File ID doesn't exist or access denied   |
| 500  | Internal Error       | PDF conversion failed or R2 upload error |

---

## Security & Privacy

### File Access Control

- ✅ User can only import their own uploaded files
- ✅ File ownership verified before processing
- ✅ Imported images stored in user-specific R2 path

### Data Retention

- **Source PDF:** Not stored (deleted after import)
- **Generated Images:** Stored permanently in R2
- **Document:** Stored in MongoDB until user deletes

### Image URLs

- **Public CDN URLs:** Images accessible via URL (no auth required)
- **Security:** URLs use unique file_id (hard to guess)
- **Recommendation:** Don't share document URLs publicly if slides contain sensitive data

---

## Rate Limiting

**Current:** No specific rate limits for import endpoint

**Recommended Frontend Behavior:**
- Disable "Import" button during processing
- Show clear "Processing..." state
- Prevent duplicate submissions

---

## Monitoring & Analytics

### Success Metrics to Track

1. **Import Success Rate:** % of imports that complete successfully
2. **Average Processing Time:** Seconds per page
3. **File Size Distribution:** Most common PDF sizes
4. **Page Count Distribution:** Most common page counts
5. **Error Rate:** % of failures by error type

### Frontend Analytics Events

```javascript
// Track import start
analytics.track('pdf_import_started', {
  file_id: 'file_abc',
  page_count: 25,
  file_size_mb: 5.2
})

// Track import success
analytics.track('pdf_import_completed', {
  document_id: 'doc_xyz',
  page_count: 25,
  processing_time_seconds: 28
})

// Track import failure
analytics.track('pdf_import_failed', {
  file_id: 'file_abc',
  error_type: 'conversion_failed',
  error_message: 'PDF processing failed'
})
```

---

## Support Contact

For issues or questions:
- **Backend Team:** Check `/SYSTEM_REFERENCE.md` for implementation details
- **API Endpoint:** `POST /api/slides/ai-generate/import-from-pdf`
- **Service:** `PDFSlideImportService` in `src/services/pdf_slide_import_service.py`

---

**Last Updated:** January 5, 2026
**Version:** 1.0
**Status:** Production Ready ✅
