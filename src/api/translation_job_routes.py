"""
Translation Job Routes
API endpoints for background translation jobs
"""

import logging
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional, List

from src.middleware.firebase_auth import get_current_user_id
from src.database.db_manager import DBManager
from src.services.translation_job_service import TranslationJobService
from src.services.book_manager import BookManager
from src.services.user_manager import UserManager
from src.models.translation_job_models import (
    StartTranslationJobRequest,
    TranslationJobResponse,
    TranslationJobStatus,
)
from src.models.book_translation_models import SUPPORTED_LANGUAGES

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/books/{book_id}/translate", tags=["Translation Jobs"])


def get_job_service() -> TranslationJobService:
    """Get translation job service instance"""
    db_manager = DBManager()
    db = db_manager.get_database()
    return TranslationJobService(db)


def get_book_manager() -> BookManager:
    """Get book manager instance"""
    db_manager = DBManager()
    db = db_manager.get_database()
    return BookManager(db)


def get_user_manager() -> UserManager:
    """Get user manager instance"""
    db_manager = DBManager()
    db = db_manager.get_database()
    return UserManager(db)


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
    request: StartTranslationJobRequest,
    user_id: str = Depends(get_current_user_id),
    job_service: TranslationJobService = Depends(get_job_service),
    book_manager: BookManager = Depends(get_book_manager),
    user_manager: UserManager = Depends(get_user_manager),
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
        db = db_manager.get_database()
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

        # Check user points
        user = user_manager.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        current_points = user.get("points", 0)
        if current_points < points_needed:
            raise HTTPException(
                status_code=402,
                detail=f"Not enough points. Need {points_needed}, have {current_points}",
            )

        # Deduct points
        success = user_manager.add_points(user_id, -points_needed)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to deduct points",
            )

        logger.info(
            f"💰 Deducted {points_needed} points from user {user_id} "
            f"for translation job (book + {chapters_count} chapters)"
        )

        # Parse background settings
        preserve_background = True
        custom_background = None

        if request.backgrounds:
            if request.backgrounds.preserve_original:
                preserve_background = True
            elif request.backgrounds.color:
                preserve_background = False
                custom_background = {
                    "type": "color",
                    "color": request.backgrounds.color,
                }
            elif request.backgrounds.gradient:
                preserve_background = False
                custom_background = {
                    "type": "gradient",
                    "gradient": request.backgrounds.gradient,
                }
            elif request.backgrounds.image_url:
                preserve_background = False
                custom_background = {
                    "type": "image",
                    "image_url": request.backgrounds.image_url,
                }

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
    user_id: str = Depends(get_current_user_id),
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


@router.delete("/cancel/{job_id}")
async def cancel_translation_job(
    book_id: str,
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    job_service: TranslationJobService = Depends(get_job_service),
):
    """
    Cancel a translation job

    Can only cancel jobs that are pending or in_progress.

    **Note:** Cancellation is best-effort. The current chapter
    being translated may still complete.
    """
    try:
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
    user_id: str = Depends(get_current_user_id),
    job_service: TranslationJobService = Depends(get_job_service),
    book_manager: BookManager = Depends(get_book_manager),
):
    """
    Get all translation jobs for a book

    Returns list of jobs with status, progress, and timestamps.
    """
    try:
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
