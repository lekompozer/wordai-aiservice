"""
Translation Job Routes
API endpoints for background translation jobs
"""

import logging
import asyncio
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional, List

from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.services.translation_job_service import TranslationJobService
from src.services.book_manager import UserBookManager
from src.services.points_service import get_points_service
from src.models.translation_job_models import (
    StartTranslationJobRequest,
    TranslationJobResponse,
    TranslationJobStatus,
    DuplicateLanguageRequest,
)
from src.models.book_translation_models import SUPPORTED_LANGUAGES

logger = logging.getLogger("chatbot")

router = APIRouter(
    prefix="/api/v1/books/{book_id}/translate", tags=["Translation Jobs"]
)

# Initialize DB connection once at module level (avoid creating new connections per request)
db_manager = DBManager()
db = db_manager.db

# Initialize services once
translation_job_service = TranslationJobService(db)
book_manager_instance = UserBookManager(db)


def get_job_service() -> TranslationJobService:
    """Get translation job service instance"""
    return translation_job_service


def get_book_manager() -> UserBookManager:
    """Get book manager instance"""
    return book_manager_instance


def format_job_response(job_data: Dict[str, Any]) -> TranslationJobResponse:
    """Convert database job document to response model"""
    return TranslationJobResponse(
        job_id=job_data["job_id"],
        book_id=job_data["book_id"],
        target_language=job_data["target_language"],
        source_language=job_data["source_language"],
        status=job_data["status"],
        chapters_total=job_data["chapters_total"],
        chapters_completed=job_data["chapters_completed"],
        chapters_failed=job_data["chapters_failed"],
        progress_percentage=job_data["progress_percentage"],
        current_chapter_id=job_data.get("current_chapter_id"),
        current_chapter_title=job_data.get("current_chapter_title"),
        estimated_time_remaining_seconds=job_data["estimated_time_remaining_seconds"],
        started_at=job_data.get("started_at"),
        completed_at=job_data.get("completed_at"),
        error=job_data.get("error"),
        failed_chapters=job_data.get("failed_chapters", []),
        points_deducted=job_data["points_deducted"],
        created_at=job_data["created_at"],
        updated_at=job_data["updated_at"],
    )


@router.post("/start", response_model=TranslationJobResponse)
async def start_translation_job(
    book_id: str,
    background_tasks: BackgroundTasks,
    request: StartTranslationJobRequest,
    user: dict = Depends(get_current_user),
    job_service: TranslationJobService = Depends(get_job_service),
    book_manager: UserBookManager = Depends(get_book_manager),
):
    """
    Start a background translation job for all chapters

    Returns immediately with job_id for status polling.
    Translation happens in background.

    **Flow:**
    1. Validates book ownership/permissions
    2. Validates language support
    3. Counts chapters to translate
    4. Calculates and deducts points (2 for book + 2 per chapter)
    5. Creates job with PENDING status
    6. Starts background translation
    7. Returns job_id immediately

    **Points:** 2 points for book metadata + 2 points per chapter
    """
    try:
        user_id = user["uid"]
        # Validate target language
        if request.target_language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported target language: {request.target_language}",
            )

        # Get book
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        # Check ownership/permissions
        if book.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to translate this book",
            )

        # Check if book is deleted
        if book.get("is_deleted", False):
            raise HTTPException(status_code=404, detail="Book not found")

        # Get source language
        source_language = request.source_language or book.get("original_language", "en")

        # Count chapters
        db_manager = DBManager()
        db = db_manager.db
        chapters_count = db.book_chapters.count_documents(
            {
                "book_id": book_id,
                "is_deleted": {"$ne": True},
            }
        )

        if chapters_count == 0:
            raise HTTPException(
                status_code=400,
                detail="Book has no chapters to translate",
            )

        # Calculate points (2 for book + 2 per chapter)
        points_needed = 2 + (chapters_count * 2)

        # Get points service
        points_service = get_points_service()

        # Check user points
        check_result = await points_service.check_sufficient_points(
            user_id=user_id, points_needed=points_needed, service="book_translation_job"
        )

        if not check_result["has_points"]:
            raise HTTPException(
                status_code=402,
                detail=f"Not enough points. Need {points_needed}, have {check_result['points_available']}",
            )

        # Deduct points
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_needed,
                service="book_translation_job",
                resource_id=book_id,
                description=f"Translation job: {request.target_language} ({chapters_count} chapters)",
            )
            logger.info(
                f"💰 Deducted {points_needed} points from user {user_id} "
                f"for translation job (book + {chapters_count} chapters)"
            )
        except Exception as e:
            logger.error(f"❌ Failed to deduct points: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to deduct points",
            )

        # Parse background settings from request
        preserve_background = request.preserve_background
        custom_background = request.custom_background

        # Create translation job
        job_id = job_service.create_job(
            book_id=book_id,
            user_id=user_id,
            target_language=request.target_language,
            source_language=source_language,
            chapters_total=chapters_count,
            points_deducted=points_needed,
            preserve_background=preserve_background,
            custom_background=custom_background,
        )

        # Start background processing (fire and forget)
        asyncio.create_task(job_service.process_job(job_id))

        logger.info(
            f"🚀 Started translation job {job_id} for book {book_id} "
            f"({chapters_count} chapters, {request.target_language})"
        )

        # Return job status immediately
        job_data = job_service.get_job(job_id)
        return format_job_response(job_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to start translation job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}", response_model=TranslationJobResponse)
async def get_translation_job_status(
    book_id: str,
    job_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    job_service: TranslationJobService = Depends(get_job_service),
):
    """
    Get translation job status

    Poll this endpoint to check translation progress.

    **Status values:**
    - `pending`: Job created, not started yet
    - `in_progress`: Currently translating chapters
    - `completed`: All chapters translated successfully
    - `failed`: Translation failed (check error field)
    - `cancelled`: Job was cancelled by user

    **Response includes:**
    - `progress_percentage`: 0-100%
    - `chapters_completed`: Number of chapters done
    - `chapters_total`: Total chapters to translate
    - `current_chapter_title`: Currently translating chapter
    - `estimated_time_remaining_seconds`: Time estimate
    - `failed_chapters`: List of chapters that failed
    """
    try:
        user_id = user["uid"]

        # Get job
        job_data = job_service.get_job(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Translation job not found")

        # Verify book_id matches
        if job_data["book_id"] != book_id:
            raise HTTPException(status_code=404, detail="Translation job not found")

        # Verify ownership
        if job_data["user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to view this translation job",
            )

        return format_job_response(job_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get translation job status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/cancel", response_model=TranslationJobResponse)
async def cancel_translation_job(
    book_id: str,
    job_id: str,
    user: dict = Depends(get_current_user),
    job_service: TranslationJobService = Depends(get_job_service),
    book_manager: UserBookManager = Depends(get_book_manager),
):
    """
    Cancel a translation job

    Can only cancel jobs that are pending or in_progress.

    **Note:** Cancellation is best-effort. The current chapter
    being translated may still complete.
    """
    try:
        user_id = user["uid"]

        # Get job
        job_data = job_service.get_job(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Translation job not found")

        # Verify book_id matches
        if job_data["book_id"] != book_id:
            raise HTTPException(status_code=404, detail="Translation job not found")

        # Verify ownership
        if job_data["user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to cancel this translation job",
            )

        # Cancel job
        success = job_service.cancel_job(job_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel job in current state",
            )

        logger.info(f"🛑 User {user_id} cancelled translation job {job_id}")

        return {
            "message": "Translation job cancelled successfully",
            "job_id": job_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to cancel translation job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", response_model=Dict[str, Any])
async def get_user_translation_jobs(
    book_id: str,
    limit: int = 20,
    skip: int = 0,
    user: Dict[str, Any] = Depends(get_current_user),
    job_service: TranslationJobService = Depends(get_job_service),
    book_manager: UserBookManager = Depends(get_book_manager),
):
    """
    Get all translation jobs for a book

    Returns list of jobs with status, progress, and timestamps.
    """
    try:
        user_id = user["uid"]

        # Verify book exists and user has access
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        if book.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to view this book's translation jobs",
            )

        # Get jobs
        jobs = job_service.get_user_jobs(
            user_id=user_id,
            book_id=book_id,
            limit=limit,
            skip=skip,
        )

        total_count = job_service.count_user_jobs(
            user_id=user_id,
            book_id=book_id,
        )

        return {
            "jobs": [format_job_response(job) for job in jobs],
            "total": total_count,
            "limit": limit,
            "skip": skip,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get translation jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/duplicate",
    status_code=200,
    summary="Duplicate content to create new language version (manual editing)",
)
async def duplicate_language_version(
    book_id: str,
    request_data: DuplicateLanguageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    book_manager: UserBookManager = Depends(get_book_manager),
    points_service: Any = Depends(get_points_service),
):
    """
    **Duplicate book content to create new language version for manual editing**

    Creates a new language version by copying:
    - Book title & description (for manual translation)
    - All chapter titles & content_html (for manual editing)

    Keeps unchanged:
    - Slugs (book & chapters)
    - Background configs
    - Chapter structure

    **Use Case:** User wants to manually translate/edit content without AI

    **Authentication:** Required (Owner only)

    **Request Body:**
    - `target_language`: Language code (e.g., "en", "zh-CN")

    **Points Cost:** FREE (no AI translation involved)

    **Returns:**
    - 200: Language version created successfully
    - 400: Invalid language or translation already exists
    - 403: Not book owner or insufficient points
    - 404: Book not found
    """
    try:
        user_id = current_user["uid"]
        target_language = request_data.target_language

        # Validate language
        if target_language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Language '{target_language}' is not supported. Supported: {', '.join(SUPPORTED_LANGUAGES.keys())}",
            )

        # Get book
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        # Check ownership
        if book.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="Only book owner can duplicate language versions",
            )

        # Check if translation already exists
        default_language = book.get("default_language", "vi")
        available_languages = book.get("available_languages", [default_language])

        if target_language in available_languages:
            raise HTTPException(
                status_code=400,
                detail=f"Translation for language '{target_language}' already exists",
            )

        # Get all chapters
        chapters = list(
            db.book_chapters.find(
                {"book_id": book_id, "is_deleted": {"$ne": True}}
            ).sort("order_index", 1)
        )

        if not chapters:
            raise HTTPException(
                status_code=400, detail="Book has no chapters to duplicate"
            )

        # Duplicate book metadata
        book_translations = book.get("translations", {})
        book_translations[target_language] = {
            "title": book.get("title", ""),
            "description": book.get("description", ""),
        }

        # Update book
        db.online_books.update_one(
            {"book_id": book_id},
            {
                "$set": {
                    "translations": book_translations,
                    "available_languages": available_languages + [target_language],
                }
            },
        )

        # Duplicate all chapters
        chapters_updated = 0
        for chapter in chapters:
            # Get content_html: prefer document content, fallback to inline content
            document_id = chapter.get("document_id")
            content_html = ""

            if document_id:
                from src.services.document_manager import DocumentManager

                document_manager = DocumentManager(db)
                document = document_manager.get_document(document_id, user_id)
                if document:
                    content_html = document.get("content_html", "")

            # If no document, use inline content_html
            if not content_html:
                content_html = chapter.get("content_html", "")

            # Get background_config from chapter
            background_config = chapter.get("background_config")

            # Duplicate chapter metadata & content
            chapter_translations = chapter.get("translations", {})
            translation_data = {
                "title": chapter.get("title", ""),
                "description": chapter.get("description", ""),
                "content_html": content_html,  # Duplicate content for manual editing
            }

            # Add background_config if exists
            if background_config:
                translation_data["background_config"] = background_config

            chapter_translations[target_language] = translation_data

            # Update chapter
            db.book_chapters.update_one(
                {"chapter_id": chapter["chapter_id"]},
                {
                    "$set": {
                        "translations": chapter_translations,
                        "available_languages": chapter.get("available_languages", [])
                        + [target_language],
                    }
                },
            )

            chapters_updated += 1

        logger.info(
            f"✅ User {user_id} duplicated book {book_id} to {target_language}: "
            f"{chapters_updated} chapters (manual editing mode)"
        )

        return {
            "success": True,
            "book_id": book_id,
            "target_language": target_language,
            "source_language": default_language,
            "chapters_duplicated": chapters_updated,
            "total_cost_points": 0,  # FREE - no AI translation
            "message": f"Content duplicated to {target_language}. Ready for manual editing.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to duplicate language version: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{language}",
    status_code=200,
    summary="Delete translation for a specific language",
)
async def delete_translation(
    book_id: str,
    language: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    book_manager: UserBookManager = Depends(get_book_manager),
):
    """
    **Delete all translations for a specific language**

    Removes:
    - Book title & description translation
    - All chapter title, description & content_html translations
    - Background config translations (if any)
    - Language from available_languages list

    **Use Case:** Remove unwanted language version or reset translation

    **Authentication:** Required (Owner only)

    **Path Parameters:**
    - `language`: Language code to delete (e.g., "en", "zh-CN")

    **Returns:**
    - 200: Translation deleted successfully
    - 400: Cannot delete default language
    - 403: Not book owner
    - 404: Book not found or language doesn't exist
    """
    try:
        user_id = current_user["uid"]

        # Validate language
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Language '{language}' is not supported. Supported: {', '.join(SUPPORTED_LANGUAGES.keys())}",
            )

        # Get book
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        # Check ownership
        if book.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="Only book owner can delete translations",
            )

        # Check default language
        default_language = book.get("default_language", "vi")
        if language == default_language:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete default language '{default_language}'. Change default language first.",
            )

        # Check if translation exists
        available_languages = book.get("available_languages", [default_language])
        if language not in available_languages:
            raise HTTPException(
                status_code=404,
                detail=f"Translation for language '{language}' does not exist",
            )

        # Remove translation from book
        db.online_books.update_one(
            {"book_id": book_id},
            {
                "$unset": {f"translations.{language}": ""},
                "$pull": {"available_languages": language},
            },
        )

        # Get all chapters
        chapters = list(
            db.book_chapters.find({"book_id": book_id, "is_deleted": {"$ne": True}})
        )

        # Remove translation from all chapters
        chapters_updated = 0
        for chapter in chapters:
            result = db.book_chapters.update_one(
                {"chapter_id": chapter["chapter_id"]},
                {
                    "$unset": {f"translations.{language}": ""},
                    "$pull": {"available_languages": language},
                },
            )
            if result.modified_count > 0:
                chapters_updated += 1

        logger.info(
            f"🗑️ User {user_id} deleted translation {language} from book {book_id}: "
            f"{chapters_updated} chapters cleaned"
        )

        return {
            "success": True,
            "book_id": book_id,
            "language_deleted": language,
            "chapters_cleaned": chapters_updated,
            "message": f"Translation for '{language}' deleted successfully.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete translation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
