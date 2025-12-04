# Translation Feature UX/UI Analysis & Solutions

## Current Problems

### 1. **Translation Timeout Issue** ⚠️
- **Problem**: Full book translation (9 chapters) takes 10-20 minutes
- **Root Cause**: Sequential translation with Gemini API (~1-2 min per chapter)
- **Impact**: Frontend timeout (usually 30-60s), user sees error but translation continues in background
- **Evidence**: Logs show only 2/9 chapters completed before frontend gave up

### 2. **Missing Language Parameter in GET Endpoints** ❌
- **Problem**: Current `GET /books/{book_id}` and `GET /books/{book_id}/chapters` don't support `?language=xx` parameter
- **Impact**: Cannot retrieve translated content for display

---

## UX/UI Requirements Analysis

### User Flow Requirement:
1. User opens book page (view BookId)
2. User selects language from dropdown (e.g., Vietnamese → English)
3. Frontend loads book metadata + chapters list in selected language
4. User clicks a chapter → Tiptap editor opens with `content_html` of that language
5. Each chapter can be viewed/edited in any available language

### Current API Gaps:

| Requirement | Current API | Status | Fix Needed |
|------------|-------------|--------|------------|
| Get book in specific language | `GET /books/{book_id}` | ❌ No `?language` param | **YES** |
| Get chapters list in specific language | `GET /books/{book_id}/chapters` | ❌ No `?language` param | **YES** |
| Get single chapter in specific language | Not available | ❌ Missing endpoint | **YES** |
| List available languages | `GET /books/{book_id}/languages` | ✅ Exists | No |
| Translate book | `POST /books/{book_id}/translate` | ⚠️ Timeout issue | **YES** |
| Translate single chapter | `POST /books/{book_id}/chapters/{chapter_id}/translate` | ✅ Works | No |

---

## Solutions

### Solution 1: Add `?language` Parameter to GET Endpoints

#### A. Update `GET /api/v1/books/{book_id}?language=xx`

**Changes needed in `book_routes.py`:**
```python
@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: str,
    language: Optional[str] = Query(None, description="Language code (e.g., 'en', 'vi')"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get book with optional language translation

    **Query Parameters:**
    - language: Language code to retrieve translated content
      * If specified and translation exists, returns translated title/description
      * If not specified or no translation, returns default language
      * If translation doesn't exist, returns 404
    """
    # ... existing access checks ...

    # Get book data
    book = book_manager.get_book(book_id)

    # Apply language translation if requested
    if language and language != book.get("default_language"):
        translations = book.get("translations", {})
        if language not in translations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Translation for language '{language}' not found"
            )

        # Merge translated fields into response
        book["title"] = translations[language].get("title", book["title"])
        book["description"] = translations[language].get("description", book["description"])
        book["current_language"] = language
    else:
        book["current_language"] = book.get("default_language", "vi")

    return book
```

#### B. Update `GET /api/v1/books/{book_id}/chapters?language=xx`

**Changes needed in `book_chapter_routes.py`:**
```python
@router.get("/{book_id}/chapters", response_model=Dict[str, Any])
async def get_chapter_tree(
    book_id: str,
    language: Optional[str] = Query(None, description="Language code for translations"),
    include_unpublished: bool = Query(False),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Get chapters with optional language translation

    **Query Parameters:**
    - language: Language code to retrieve translated content
      * If specified, returns translated title/description for each chapter
      * Original structure preserved, only text content translated
    """
    # ... existing logic ...

    # Build chapter tree
    chapters = build_chapter_tree(...)

    # Apply language translations if requested
    if language and language != book.get("default_language"):
        chapters = apply_language_to_chapters(chapters, language)

    return {
        "book_id": book_id,
        "title": book_title,  # Already translated from book endpoint
        "chapters": chapters,
        "current_language": language or book.get("default_language"),
        "total_chapters": total_count
    }
```

#### C. Create NEW `GET /api/v1/books/{book_id}/chapters/{chapter_id}?language=xx`

**New endpoint needed:**
```python
@router.get("/{book_id}/chapters/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    book_id: str,
    chapter_id: str,
    language: Optional[str] = Query(None, description="Language code"),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Get single chapter with full content_html in specified language

    **Use Case:** Load chapter content into Tiptap editor

    **Query Parameters:**
    - language: Language code (e.g., 'en', 'vi')
      * If specified and exists, returns translated content_html
      * If not specified, returns default language content_html

    **Response:**
    {
        "chapter_id": "...",
        "book_id": "...",
        "title": "Translated title",
        "description": "Translated description",
        "content_html": "<p>Translated HTML content...</p>",
        "current_language": "en",
        "available_languages": ["vi", "en", "zh-CN"],
        "order_index": 1,
        "level": 0
    }
    """
    # Check access permissions
    # ...

    chapter = db.book_chapters.find_one({"chapter_id": chapter_id, "book_id": book_id})

    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # Apply language translation
    if language and language != chapter.get("default_language"):
        translations = chapter.get("translations", {})
        if language not in translations:
            raise HTTPException(
                status_code=404,
                detail=f"Translation for language '{language}' not found"
            )

        trans = translations[language]
        chapter["title"] = trans.get("title", chapter["title"])
        chapter["description"] = trans.get("description", chapter["description"])
        chapter["content_html"] = trans.get("content_html", chapter["content_html"])
        chapter["current_language"] = language
    else:
        chapter["current_language"] = chapter.get("default_language", "vi")

    return chapter
```

---

### Solution 2: Fix Translation Timeout Issue

#### Option A: Background Job Processing (RECOMMENDED) ⭐

**Implementation:**
1. Create translation job status tracking
2. Return immediately after starting translation
3. Frontend polls for status updates

```python
# New endpoint: Start translation (returns immediately)
@router.post("/{book_id}/translate/start")
async def start_book_translation(...):
    """
    Start book translation as background job

    **Returns immediately with job_id**

    Response:
    {
        "job_id": "trans_123abc",
        "status": "in_progress",
        "book_id": "...",
        "target_language": "en",
        "estimated_time_minutes": 15,
        "chapters_total": 9,
        "chapters_completed": 0
    }
    """
    # Validate and deduct points
    # ...

    # Create job record in database
    job_id = create_translation_job(book_id, target_language, chapters_count)

    # Start background task (using asyncio.create_task or Celery)
    asyncio.create_task(
        process_book_translation_background(job_id, book_id, target_language)
    )

    return {
        "job_id": job_id,
        "status": "in_progress",
        "chapters_total": chapters_count,
        "chapters_completed": 0
    }

# New endpoint: Check translation status
@router.get("/{book_id}/translate/status/{job_id}")
async def get_translation_status(book_id: str, job_id: str):
    """
    Check translation job progress

    Response:
    {
        "job_id": "trans_123abc",
        "status": "in_progress",  // or "completed", "failed"
        "chapters_total": 9,
        "chapters_completed": 3,
        "progress_percentage": 33,
        "current_chapter": "Chương 3: ...",
        "estimated_time_remaining_seconds": 720,
        "error": null
    }
    """
    job = db.translation_jobs.find_one({"job_id": job_id, "book_id": book_id})

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job
```

**Database Schema for Jobs:**
```javascript
// New collection: translation_jobs
{
    "job_id": "trans_123abc",
    "book_id": "book_xyz",
    "user_id": "user_123",
    "target_language": "en",
    "source_language": "vi",
    "status": "in_progress",  // pending, in_progress, completed, failed
    "chapters_total": 9,
    "chapters_completed": 3,
    "chapters_failed": 0,
    "progress_percentage": 33,
    "current_chapter_id": "chapter_xyz",
    "current_chapter_title": "Chương 3: ...",
    "estimated_time_remaining": 720,  // seconds
    "started_at": ISODate("2024-12-04T17:00:00Z"),
    "completed_at": null,
    "error": null,
    "points_deducted": 20
}
```

**Frontend Flow:**
```javascript
// 1. Start translation
const response = await fetch('/api/v1/books/{book_id}/translate/start', {
    method: 'POST',
    body: JSON.stringify({ target_language: 'en' })
});
const { job_id } = await response.json();

// 2. Show progress modal and poll for status
const interval = setInterval(async () => {
    const status = await fetch(`/api/v1/books/{book_id}/translate/status/${job_id}`);
    const data = await status.json();

    updateProgressBar(data.progress_percentage);
    updateCurrentChapter(data.current_chapter);

    if (data.status === 'completed') {
        clearInterval(interval);
        showSuccessMessage();
        reloadBookData();
    } else if (data.status === 'failed') {
        clearInterval(interval);
        showErrorMessage(data.error);
    }
}, 3000); // Poll every 3 seconds
```

#### Option B: Translate Only Metadata First (Quick Win) 🚀

**Implementation:**
```python
# Modify existing endpoint to have optional flag
@router.post("/{book_id}/translate")
async def translate_book(
    book_id: str,
    request: TranslateBookRequest,  // add flag: translate_chapters=False by default
    ...
):
    """
    By default only translates book metadata (2 points, <10 seconds)

    Set translate_chapters=true to translate all chapters (slower)
    """
    # ... existing validation ...

    # Always translate metadata first
    await translation_service.translate_book_metadata(...)

    # Only translate chapters if explicitly requested
    if request.translate_chapters:
        # This will be slow, frontend should show loading
        await translation_service.translate_chapters(...)

    return response
```

**UX Flow:**
1. User clicks "Translate to English"
2. Book metadata translates immediately (<10s) → ✅ User sees translated title
3. Show banner: "Chapters are being translated (3/9 done)... Translate remaining?"
4. User can translate chapters one-by-one when needed (2 points each)

---

## Recommended Implementation Plan

### Phase 1: Critical Fixes (Deploy ASAP) 🔴
1. ✅ Add `?language` parameter to `GET /books/{book_id}`
2. ✅ Add `?language` parameter to `GET /books/{book_id}/chapters`
3. ✅ Create `GET /books/{book_id}/chapters/{chapter_id}?language=xx`
4. ✅ Change default behavior: `translate_chapters=false` in book translation

### Phase 2: Better UX (Next Sprint) 🟡
1. ✅ Add translation job status tracking
2. ✅ Create `POST /books/{book_id}/translate/start` (background job)
3. ✅ Create `GET /books/{book_id}/translate/status/{job_id}` (polling)
4. ✅ Frontend implements progress bar with polling

### Phase 3: Optimization (Future) 🟢
1. Use task queue (Celery/Redis) for better background processing
2. Add translation cancellation endpoint
3. Implement translation caching/memory
4. Batch translate multiple chapters in parallel

---

## Updated API Endpoints Summary

### Reading Translated Content (NEW)
```
GET /api/v1/books/{book_id}?language=en
GET /api/v1/books/{book_id}/chapters?language=en
GET /api/v1/books/{book_id}/chapters/{chapter_id}?language=en  (NEW!)
```

### Translation Management (EXISTING)
```
GET  /api/v1/books/{book_id}/languages
POST /api/v1/books/{book_id}/translate
POST /api/v1/books/{book_id}/chapters/{chapter_id}/translate
PUT  /api/v1/books/{book_id}/background/{language}
DELETE /api/v1/books/{book_id}/translations/{language}
```

### Translation Jobs (NEW - Phase 2)
```
POST /api/v1/books/{book_id}/translate/start
GET  /api/v1/books/{book_id}/translate/status/{job_id}
DELETE /api/v1/books/{book_id}/translate/cancel/{job_id}  (Future)
```

---

## Frontend Integration Example

```typescript
// 1. Load book with selected language
const loadBook = async (bookId: string, language: string) => {
    const book = await api.get(`/books/${bookId}?language=${language}`);
    const chapters = await api.get(`/books/${bookId}/chapters?language=${language}`);

    setBook(book);
    setChapters(chapters);
};

// 2. Load chapter content for editor
const loadChapter = async (bookId: string, chapterId: string, language: string) => {
    const chapter = await api.get(
        `/books/${bookId}/chapters/${chapterId}?language=${language}`
    );

    // Load into Tiptap editor
    editor.commands.setContent(chapter.content_html);
};

// 3. Start translation with progress tracking
const translateBook = async (bookId: string, targetLang: string) => {
    // Start job
    const { job_id } = await api.post(`/books/${bookId}/translate/start`, {
        target_language: targetLang
    });

    // Show progress modal
    showProgressModal();

    // Poll for status
    const pollStatus = setInterval(async () => {
        const status = await api.get(`/books/${bookId}/translate/status/${job_id}`);

        updateProgress(status.progress_percentage);

        if (status.status === 'completed') {
            clearInterval(pollStatus);
            hideProgressModal();
            reloadBook();
        }
    }, 3000);
};
```

---

## Testing Checklist

- [ ] Get book in default language (no ?language param)
- [ ] Get book in translated language (?language=en)
- [ ] Get book in non-existent language (should 404)
- [ ] Get chapters list in default language
- [ ] Get chapters list in translated language
- [ ] Get single chapter content_html in default language
- [ ] Get single chapter content_html in translated language
- [ ] Translate book metadata only (fast, <10s)
- [ ] Translate book with all chapters (slow, background job)
- [ ] Check translation progress while in-progress
- [ ] Load translated chapter into Tiptap editor
- [ ] Switch between languages in book viewer
- [ ] Translate single chapter (2 points)
- [ ] Delete translation and verify content reverts to default

---

## Migration Notes

### Database Changes Needed:
1. No schema changes required for Phase 1
2. Add `translation_jobs` collection for Phase 2
3. Add indexes:
   ```javascript
   db.translation_jobs.createIndex({ "book_id": 1, "user_id": 1 })
   db.translation_jobs.createIndex({ "status": 1, "created_at": -1 })
   ```

### Deployment:
1. Deploy Phase 1 changes immediately (no breaking changes)
2. Update frontend to use `?language` parameter
3. Test with existing translated books
4. Deploy Phase 2 after frontend is ready for polling
