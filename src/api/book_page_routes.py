"""
Book Page Text & Audio Routes

6 endpoints for LetsRead book per-page text (from letsread_page_crawler)
and TTS audio generation.

Route ordering (CRITICAL — static before path parameters):
  /pages/batch                        ← static, matched first
  /pages                              ← static
  /audio/generate                     ← static
  /audio/generate/status/{job_id}     ← path param under /audio/generate/
  /audio                              ← static (GET with ?voice= query param)
  /audio/{voice}                      ← path param, comes last

Authentication:
  - POST  /pages/batch  → requires current_user (admin/script use)
  - GET   /pages        → public (no auth needed)
  - POST  /audio/generate → requires current_user
  - GET   /audio/generate/status/{job_id} → requires current_user
  - GET   /audio        → public
  - DELETE /audio/{voice} → requires current_user (admin)
"""

import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from bson import ObjectId
from datetime import datetime

from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.models.book_page_models import (
    BatchSavePagesRequest,
    BatchSavePagesResponse,
    BookPagesResponse,
    BookPage,
    AudioGenerateRequest,
    AudioGenerateResponse,
    AudioJobStatus,
    AudioJobStatusResponse,
    BookAudioResponse,
    PageTimestamp,
    DeleteAudioResponse,
    TranslateRequest,
    TranslateResponse,
)
from src.services.book_page_audio_service import (
    BookPageAudioService,
    get_book_page_audio_service,
)

logger = logging.getLogger("chatbot")

router = APIRouter(
    prefix="/api/v1/books/{book_id}",
    tags=["Book Pages & Audio"],
)

# Module-level singletons
db_manager = DBManager()
db = db_manager.db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _book_exists(book_id: str) -> bool:
    """Check the book_id is a valid online_books document."""
    try:
        return db.online_books.find_one({"_id": ObjectId(book_id)}) is not None
    except Exception:
        return False


def _require_valid_book(book_id: str) -> None:
    if not _book_exists(book_id):
        raise HTTPException(status_code=404, detail=f"Book not found: {book_id}")


# ---------------------------------------------------------------------------
# 1. POST /pages/batch — save crawled pages (admin / script use)
# ---------------------------------------------------------------------------


@router.post(
    "/pages/batch",
    response_model=BatchSavePagesResponse,
    summary="Save crawled pages for a book (admin)",
)
async def batch_save_pages(
    book_id: str,
    body: BatchSavePagesRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> BatchSavePagesResponse:
    """
    **Store per-page text + image data for a book.**

    Typically called by `letsread_page_crawler.py` after fetching from the
    LetsRead REST API. Accepts a JSON payload with a `pages` list.

    Each page is upserted (unique on `book_id` + `page_number`).
    Set `force=true` to overwrite existing pages.

    **Authentication:** Required (any authenticated user — restrict to admin in prod)
    """
    _require_valid_book(book_id)

    saved = 0
    total = len(body.pages)

    for page in body.pages:
        doc = {
            "book_id": book_id,
            "letsread_book_id": body.letsread_book_id,
            "letsread_lang_id": body.letsread_lang_id,
            "language": body.language,
            "page_number": page.page_number,
            "api_page_num": page.page_number + 1,  # pageNum in API for story pages
            "text_content": page.text_content,
            "image_url": page.image_url,
            "image_url_cdn": page.image_url_cdn,
            "image_url_hires": page.image_url_hires,
            "image_name": page.image_name,
            "image_width": page.image_width,
            "image_height": page.image_height,
            "has_audio": page.has_audio,
            "letsread_page_id": page.letsread_page_id,
            "updated_at": datetime.utcnow(),
        }
        filter_q = {"book_id": book_id, "page_number": page.page_number}

        if body.force:
            db.book_page_texts.replace_one(filter_q, doc, upsert=True)
            saved += 1
        else:
            existing = db.book_page_texts.find_one(filter_q)
            if not existing:
                doc["created_at"] = datetime.utcnow()
                db.book_page_texts.insert_one(doc)
                saved += 1

    # Update online_books metadata
    db.online_books.update_one(
        {"_id": ObjectId(book_id)},
        {
            "$set": {
                "metadata.letsread_book_id": body.letsread_book_id,
                "metadata.letsread_lang_id": body.letsread_lang_id,
                "metadata.has_page_texts": True,
                "metadata.total_pages": total,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    return BatchSavePagesResponse(
        book_id=book_id,
        letsread_book_id=body.letsread_book_id,
        saved=saved,
        total=total,
        message=f"Saved {saved} of {total} pages",
    )


# ---------------------------------------------------------------------------
# 2. GET /pages — list pages with text
# ---------------------------------------------------------------------------


@router.get(
    "/pages",
    response_model=BookPagesResponse,
    summary="Get all pages (text + images) for a book",
)
async def get_book_pages(
    book_id: str,
    language: str = Query(default="en", description="Language code"),
) -> BookPagesResponse:
    """
    **Return all story pages for a book.**

    Pages are sorted by `page_number` ascending.
    Returns an empty list if no pages have been crawled yet.

    **Authentication:** Not required (public)
    """
    cursor = db.book_page_texts.find({"book_id": book_id, "language": language}).sort(
        "page_number", 1
    )

    pages = []
    for doc in cursor:
        pages.append(
            BookPage(
                page_number=doc["page_number"],
                text_content=doc.get("text_content") or "",
                image_url=doc.get("image_url") or "",
                image_url_cdn=doc.get("image_url_cdn"),
                image_url_hires=doc.get("image_url_hires"),
                image_name=doc.get("image_name"),
                image_width=doc.get("image_width"),
                image_height=doc.get("image_height"),
                has_audio=doc.get("has_audio", False),
                letsread_page_id=doc.get("letsread_page_id"),
            )
        )

    return BookPagesResponse(
        book_id=book_id,
        total_pages=len(pages),
        language=language,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# 2b. POST /pages/translate — translate EN pages to another language (admin)
# ---------------------------------------------------------------------------


@router.post(
    "/pages/translate",
    response_model=TranslateResponse,
    summary="Translate EN pages to another language via DeepSeek (admin)",
)
async def translate_book_pages(
    book_id: str,
    body: TranslateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TranslateResponse:
    """
    **Translate all EN pages to the target language using DeepSeek.**

    Currently supports: `"vi"` (Vietnamese).

    The translated pages are saved to `book_page_texts` with the target
    language code. Image data is inherited from the EN pages.

    Set `force=true` to re-translate even if target-language pages exist.

    **Authentication:** Required
    """
    _require_valid_book(book_id)

    if body.target_language not in ("vi",):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target_language '{body.target_language}'. Supported: vi",
        )

    svc = get_book_page_audio_service()
    try:
        result = await svc.translate_pages_to_vi(book_id=book_id, force=body.force)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {e}")

    return TranslateResponse(
        book_id=book_id,
        source_language="en",
        target_language=body.target_language,
        saved=result["saved"],
        skipped=result["skipped"],
        total=result["total"],
        message=(
            f"Translated {result['saved']} pages EN→{body.target_language}"
            if result["saved"] > 0
            else f"{result['skipped']} pages already translated (use force=true to redo)"
        ),
    )


# ---------------------------------------------------------------------------
# 3. POST /audio/generate — start async audio generation
# ---------------------------------------------------------------------------


@router.post(
    "/audio/generate",
    response_model=AudioGenerateResponse,
    summary="Generate TTS audio for the entire book (async)",
)
async def generate_book_audio(
    book_id: str,
    body: AudioGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> AudioGenerateResponse:
    """
    **Generate TTS audio for all pages of a book.**

    Processing runs in the background. Poll the status endpoint to track progress.

    Voice options:
    - `"auto"` (default) — deterministic assignment: 70% Aoede (Female), 30% Algenib (Male)
    - `"Aoede"` — Female, breezy
    - `"Algenib"` — Male, gravelly
    - Any valid Gemini TTS voice name (see `google_tts_service.py`)

    Set `force_regenerate=true` to delete existing audio and regenerate.

    **Authentication:** Required
    """
    _require_valid_book(book_id)

    svc = get_book_page_audio_service()
    voice_name = svc.resolve_voice(book_id, body.voice)

    # For Vietnamese: auto-translate if VI pages don't exist yet
    if body.language == "vi":
        try:
            await svc.ensure_vi_pages(book_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"VI translation failed: {e}")

    # Count pages
    total_pages = db.book_page_texts.count_documents(
        {"book_id": book_id, "language": body.language}
    )
    if total_pages == 0:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No pages found for book_id={book_id} language={body.language}. "
                "Run letsread_page_crawler first."
            ),
        )

    # Create pending job record immediately so we can return job_id
    version = svc._next_version(db, book_id, voice_name, body.language)
    if body.force_regenerate:
        # Delete existing records for this voice + language before creating new job
        db.book_page_audio.delete_many(
            {"book_id": book_id, "voice_name": voice_name, "language": body.language}
        )
        version = 1

    job_id = svc.create_job_record(
        db=db,
        book_id=book_id,
        voice_name=voice_name,
        language=body.language,
        version=version,
        total_pages=total_pages,
    )

    # Run generation in background (non-blocking)
    async def _run():
        try:
            await svc._run_generation(
                job_id=job_id,
                book_id=book_id,
                voice_name=voice_name,
                language=body.language,
                version=version,
                use_pro_model=body.use_pro_model,
            )
        except Exception as e:
            logger.error(f"Background audio generation failed: {e}", exc_info=True)

    background_tasks.add_task(_run)

    return AudioGenerateResponse(
        job_id=job_id,
        book_id=book_id,
        voice=voice_name,
        status=AudioJobStatus.PENDING,
        message=f"Audio generation started for {total_pages} pages (voice: {voice_name})",
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# 4. GET /audio/generate/status/{job_id} — poll job
# ---------------------------------------------------------------------------


@router.get(
    "/audio/generate/status/{job_id}",
    response_model=AudioJobStatusResponse,
    summary="Poll audio generation job status",
)
async def get_audio_job_status(
    book_id: str,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> AudioJobStatusResponse:
    """
    **Poll the progress of an audio generation job.**

    Returns `status` as:
    - `pending` — queued, not started yet
    - `processing` — TTS in progress
    - `completed` — ready (`audio_url` available)
    - `failed` — error (`error` field has details)

    **Authentication:** Required
    """
    try:
        doc = db.book_page_audio.find_one({"_id": ObjectId(job_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    if not doc:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if doc.get("book_id") != book_id:
        raise HTTPException(status_code=404, detail="Job does not belong to this book")

    return AudioJobStatusResponse(
        job_id=str(doc["_id"]),
        book_id=book_id,
        status=AudioJobStatus(doc.get("status", "pending")),
        voice=doc.get("voice_name"),
        progress=doc.get("progress"),
        audio_url=doc.get("audio_url"),
        total_duration_seconds=doc.get("total_duration_seconds"),
        error=doc.get("error"),
        created_at=(doc["created_at"].isoformat() if doc.get("created_at") else None),
        completed_at=(
            doc["completed_at"].isoformat() if doc.get("completed_at") else None
        ),
    )


# ---------------------------------------------------------------------------
# 5. GET /audio — get merged audio + timestamps (MAIN frontend endpoint)
# ---------------------------------------------------------------------------


@router.get(
    "/audio",
    response_model=BookAudioResponse,
    summary="Get audio URL + page timestamps for frontend playback",
)
async def get_book_audio(
    book_id: str,
    voice: Optional[str] = Query(
        default=None,
        description="Voice name. Defaults to book's assigned voice.",
    ),
    language: str = Query(default="en"),
    include_pages: bool = Query(
        default=False,
        description="Include full pages list in response",
    ),
) -> BookAudioResponse:
    """
    **Primary endpoint for frontend book-reader audio playback.**

    Returns:
    - `audio_url` — CDN URL for the merged WAV file
    - `page_timestamps` — list of `{page_number, start_time, end_time}` for sync
    - `total_duration_seconds`

    The frontend uses `page_timestamps` to show the correct page image/text
    as the audio plays (no extra API calls during playback).

    If `voice` is omitted, the book's default deterministic voice is used.

    **Authentication:** Not required (public)
    """
    svc = get_book_page_audio_service()

    if not voice:
        voice = svc.get_default_voice(book_id)
    else:
        voice = voice.capitalize()

    doc = db.book_page_audio.find_one(
        {
            "book_id": book_id,
            "voice_name": voice,
            "language": language,
            "status": "completed",
        },
        sort=[("version", -1)],
    )

    if not doc:
        # Check if there's a pending/processing job
        pending = db.book_page_audio.find_one(
            {
                "book_id": book_id,
                "voice_name": voice,
                "language": language,
                "status": {"$in": ["pending", "processing"]},
            },
            sort=[("version", -1)],
        )
        if pending:
            return BookAudioResponse(
                book_id=book_id,
                voice=voice,
                version=pending.get("version", 1),
                status=AudioJobStatus.PROCESSING,
            )

        return BookAudioResponse(
            book_id=book_id,
            voice=voice,
            version=0,
            status=AudioJobStatus.PENDING,
        )

    timestamps = [
        PageTimestamp(
            page_number=ts["page_number"],
            start_time=ts["start_time"],
            end_time=ts["end_time"],
            duration=ts["duration"],
        )
        for ts in (doc.get("page_timestamps") or [])
    ]

    pages_data = None
    if include_pages:
        pages_cursor = db.book_page_texts.find(
            {"book_id": book_id, "language": language}
        ).sort("page_number", 1)
        pages_data = [
            BookPage(
                page_number=p["page_number"],
                text_content=p.get("text_content") or "",
                image_url=p.get("image_url") or "",
                image_url_cdn=p.get("image_url_cdn"),
                image_url_hires=p.get("image_url_hires"),
                image_name=p.get("image_name"),
                image_width=p.get("image_width"),
                image_height=p.get("image_height"),
                has_audio=p.get("has_audio", False),
                letsread_page_id=p.get("letsread_page_id"),
            )
            for p in pages_cursor
        ]

    audio_meta = doc.get("audio_metadata") or {}
    generated_at = doc.get("completed_at") or doc.get("created_at")

    return BookAudioResponse(
        book_id=book_id,
        voice=voice,
        version=doc.get("version", 1),
        status=AudioJobStatus.COMPLETED,
        audio_url=doc.get("audio_url"),
        total_duration_seconds=doc.get("total_duration_seconds"),
        total_pages=doc.get("total_pages"),
        page_timestamps=timestamps,
        pages=pages_data,
        generated_at=generated_at.isoformat() if generated_at else None,
        model=audio_meta.get("model"),
    )


# ---------------------------------------------------------------------------
# 6. DELETE /audio/{voice} — delete audio
# ---------------------------------------------------------------------------


@router.delete(
    "/audio/{voice}",
    response_model=DeleteAudioResponse,
    summary="Delete generated audio for a specific voice",
)
async def delete_book_audio(
    book_id: str,
    voice: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> DeleteAudioResponse:
    """
    **Delete all audio records for this book × voice.**

    Also removes the file from R2 storage (best-effort).

    **Authentication:** Required

    **Common use:** Admin cleanup or forcing regeneration with `force_regenerate=true`
    on the generate endpoint.
    """
    _require_valid_book(book_id)

    voice_name = voice.capitalize()
    svc = get_book_page_audio_service()
    deleted = await svc.delete_book_audio(book_id, voice_name)

    return DeleteAudioResponse(
        book_id=book_id,
        voice=voice_name,
        deleted=deleted,
        message=(
            f"Deleted audio for voice={voice_name}"
            if deleted
            else f"No audio found for voice={voice_name}"
        ),
    )
