# MOBI to EPUB Conversion Plan

## Problem Statement
2656 crawled books have `.pdf` file extensions but are actually MOBI format files. These cannot be read by PDF viewers, causing "Failed to load PDF document" errors.

## Solution: Convert MOBI → EPUB

### Why EPUB instead of PDF?
- ✅ **No GPU/Qt requirements**: MOBI → EPUB conversion works in headless Docker
- ✅ **Format similarity**: Both MOBI and EPUB are ebook formats (easier conversion)
- ✅ **Better quality**: Text remains reflowable, preserves formatting
- ✅ **JavaScript readers**: Libraries like epub.js work great in browsers
- ✅ **Smaller file size**: EPUB typically 20-30% smaller than source MOBI

### Test Results
```bash
# Tested on production server in Docker container
Input:  515,807 bytes (MOBI)
Output: 377,738 bytes (EPUB)
Status: ✅ SUCCESS - no errors
Tool:   Calibre ebook-convert 8.5.0
```

## Implementation Plan

### Phase 1: Scan & Identify ✅ IN PROGRESS
**Script**: `scan_mobi_books.py`
**Status**: Running on production server (background process)

**Output**: `mobi_books_list.json`
```json
{
  "scan_date": "2026-02-09T...",
  "total_mobi_files": 1234,
  "books": [
    {
      "book_id": "book_xxx",
      "book_title": "Harry Potter",
      "chapter_id": "990dbf57...",
      "pdf_url": "https://static.wordai.pro/books/crawled/...",
      "scanned_at": "..."
    }
  ]
}
```

**Progress**: ~100/2656 checked (estimated 10-20 min to complete)

### Phase 2: Batch Conversion 🔄 READY
**Script**: `batch_convert_mobi_to_epub.py` (to be created)

**Workflow**:
1. Read `mobi_books_list.json`
2. For each MOBI file:
   - Download from R2
   - Convert MOBI → EPUB using `ebook-convert`
   - Upload EPUB to R2: `books/crawled-epub/{book_id}_{chapter_id}.epub`
   - Update MongoDB:
     ```python
     {
       "epub_url": "https://static.wordai.pro/books/crawled-epub/...",
       "original_mobi_url": "https://static.wordai.pro/books/crawled/...",
       "chapter_type": "epub",  # Changed from "pdf"
       "content_mode": "epub_file",  # Changed from "pdf_file"
       "converted_at": datetime.utcnow(),
       "conversion_tool": "calibre-ebook-convert-8.5.0"
     }
     ```

**Features**:
- Resume capability (skip already converted)
- Progress tracking (every 10 books)
- Error handling & logging
- Parallel processing (5 workers)
- Estimated time: ~2-4 hours for 1000+ books

### Phase 3: Frontend EPUB Reader 🔜 TODO
**Library**: [epub.js](https://github.com/futurepress/epub.js)

**Integration**:
```javascript
// In book reader component
import ePub from 'epubjs';

const book = ePub(epubUrl);
const rendition = book.renderTo("viewer", {
  width: "100%",
  height: 600
});
rendition.display();
```

**Backend Changes**:
- Update `book_chapters` schema to support `epub_url` field
- Add `chapter_type="epub"` handling in API endpoints
- Update frontend to check `chapter_type` and use appropriate reader

## Database Schema Changes

### book_chapters Collection
```python
{
  # Existing fields
  "chapter_id": str,
  "book_id": str,
  "chapter_type": str,  # "pdf" | "epub" | "audio"
  "content_mode": str,  # "pdf_file" | "epub_file" | "audio_file"

  # New/Updated fields
  "pdf_url": str | None,  # Original PDF URL (kept for audit)
  "epub_url": str | None,  # NEW: EPUB URL after conversion
  "original_mobi_url": str | None,  # NEW: Original MOBI URL before conversion

  # Metadata
  "converted_at": datetime | None,  # When conversion happened
  "conversion_tool": str | None,  # "calibre-ebook-convert-8.5.0"
}
```

## Conversion Statistics (Estimated)

Based on test results (100/2656 scanned):
- **Total chapters**: 2,656
- **MOBI files**: ~800-1,200 (30-45%)
- **Valid PDFs**: ~1,400-1,800 (55-65%)
- **Errors**: ~50-100 (2-5%)

## Deployment Plan

### Step 1: Wait for scan to complete
```bash
ssh root@104.248.147.155 "tail -f /tmp/scan_mobi.log"
ssh root@104.248.147.155 "docker cp ai-chatbot-rag:/app/mobi_books_list.json /tmp/"
scp root@104.248.147.155:/tmp/mobi_books_list.json ./
```

### Step 2: Create batch conversion script
- Implement `batch_convert_mobi_to_epub.py`
- Test with 5-10 books first
- Review converted EPUBs manually

### Step 3: Run batch conversion
```bash
# Upload script
scp batch_convert_mobi_to_epub.py root@104.248.147.155:/tmp/
ssh root@104.248.147.155 "docker cp /tmp/batch_convert_mobi_to_epub.py ai-chatbot-rag:/app/"

# Run conversion (background process)
ssh root@104.248.147.155 "nohup docker exec ai-chatbot-rag python3 /app/batch_convert_mobi_to_epub.py > /tmp/convert_mobi.log 2>&1 &"

# Monitor progress
ssh root@104.248.147.155 "tail -f /tmp/convert_mobi.log"
```

### Step 4: Frontend integration
1. Install epub.js: `npm install epubjs`
2. Create EpubReader component
3. Update book reader to detect `chapter_type` and use appropriate reader
4. Test with converted EPUB files

## Timeline

- ✅ **Phase 1**: Scanning - 20 minutes
- 🔄 **Phase 2**: Batch conversion - 2-4 hours
- 🔜 **Phase 3**: Frontend integration - 1-2 hours
- 🔜 **Testing**: Verify random books load correctly - 30 minutes

**Total estimated time**: 4-7 hours

## Rollback Plan

If EPUB reader doesn't work well:
1. Keep original MOBI files in database (`original_mobi_url`)
2. Can revert MongoDB updates
3. Can try alternative approach (convert to HTML with images)

## Success Criteria

- [ ] All MOBI files identified and listed
- [ ] >95% successful conversion rate (MOBI → EPUB)
- [ ] All converted EPUBs uploaded to R2
- [ ] MongoDB updated with new `epub_url` fields
- [ ] Frontend can display EPUB files using epub.js
- [ ] Users can read previously broken books

---

**Created**: 2026-02-09
**Status**: Phase 1 in progress
**Next Action**: Wait for scan completion, then create batch conversion script
