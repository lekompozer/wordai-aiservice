"""
Translation Job Service
Manages background translation jobs with progress tracking
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pymongo.database import Database
import uuid

from src.services.book_translation_service import BookTranslationService
from src.models.translation_job_models import TranslationJobStatus

logger = logging.getLogger("chatbot")


class TranslationJobService:
    """Service for managing translation jobs"""

    def __init__(self, db: Database):
        self.db = db
        self.jobs_collection = db["translation_jobs"]
        self.translation_service = BookTranslationService(db)

        # Create indexes
        self._create_indexes()

    def _create_indexes(self):
        """Create database indexes for translation jobs"""
        try:
            self.jobs_collection.create_index([("job_id", 1)], unique=True)
            self.jobs_collection.create_index([("book_id", 1), ("user_id", 1)])
            self.jobs_collection.create_index([("status", 1), ("created_at", -1)])
            self.jobs_collection.create_index([("user_id", 1), ("created_at", -1)])
            logger.info("✅ Translation job indexes created")
        except Exception as e:
            logger.warning(f"⚠️ Translation job indexes may already exist: {e}")

    def create_job(
        self,
        book_id: str,
        user_id: str,
        target_language: str,
        source_language: str,
        chapters_total: int,
        points_deducted: int,
        preserve_background: bool = True,
        custom_background: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new translation job

        Returns:
            job_id: Unique job identifier
        """
        now = datetime.now(timezone.utc)
        job_id = f"trans_{uuid.uuid4().hex[:12]}"

        job_data = {
            "job_id": job_id,
            "book_id": book_id,
            "user_id": user_id,
            "target_language": target_language,
            "source_language": source_language,
            "status": TranslationJobStatus.PENDING,
            "chapters_total": chapters_total,
            "chapters_completed": 0,
            "chapters_failed": 0,
            "progress_percentage": 0,
            "current_chapter_id": None,
            "current_chapter_title": None,
            "estimated_time_remaining_seconds": chapters_total
            * 60,  # Estimate 1 min per chapter
            "started_at": None,
            "completed_at": None,
            "error": None,
            "failed_chapters": [],
            "points_deducted": points_deducted,
            "preserve_background": preserve_background,
            "custom_background": custom_background,
            "created_at": now,
            "updated_at": now,
        }

        self.jobs_collection.insert_one(job_data)
        logger.info(f"📋 Created translation job: {job_id} for book {book_id}")

        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get translation job by ID"""
        return self.jobs_collection.find_one({"job_id": job_id})

    def update_job_status(
        self,
        job_id: str,
        status: str,
        chapters_completed: Optional[int] = None,
        chapters_failed: Optional[int] = None,
        current_chapter_id: Optional[str] = None,
        current_chapter_title: Optional[str] = None,
        error: Optional[str] = None,
        failed_chapter: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update job status and progress"""
        now = datetime.now(timezone.utc)

        update_data = {
            "status": status,
            "updated_at": now,
        }

        if chapters_completed is not None:
            update_data["chapters_completed"] = chapters_completed

        if chapters_failed is not None:
            update_data["chapters_failed"] = chapters_failed

        if current_chapter_id is not None:
            update_data["current_chapter_id"] = current_chapter_id

        if current_chapter_title is not None:
            update_data["current_chapter_title"] = current_chapter_title

        if error is not None:
            update_data["error"] = error

        if (
            status == TranslationJobStatus.IN_PROGRESS
            and "started_at" not in update_data
        ):
            job = self.get_job(job_id)
            if job and not job.get("started_at"):
                update_data["started_at"] = now

        if status in [TranslationJobStatus.COMPLETED, TranslationJobStatus.FAILED]:
            update_data["completed_at"] = now

        # Calculate progress percentage
        job = self.get_job(job_id)
        if job:
            total = job["chapters_total"]
            completed = (
                chapters_completed
                if chapters_completed is not None
                else job["chapters_completed"]
            )
            if total > 0:
                progress = int((completed / total) * 100)
                update_data["progress_percentage"] = progress

                # Update time estimate (average 60 seconds per chapter)
                remaining_chapters = total - completed
                update_data["estimated_time_remaining_seconds"] = (
                    remaining_chapters * 60
                )

        # Add failed chapter to list if provided
        if failed_chapter:
            self.jobs_collection.update_one(
                {"job_id": job_id}, {"$push": {"failed_chapters": failed_chapter}}
            )

        result = self.jobs_collection.update_one(
            {"job_id": job_id}, {"$set": update_data}
        )

        return result.modified_count > 0

    async def process_job(self, job_id: str):
        """
        Process translation job in background

        This is the main worker function that translates all chapters
        """
        try:
            job = self.get_job(job_id)
            if not job:
                logger.error(f"❌ Job not found: {job_id}")
                return

            logger.info(f"🚀 Starting translation job: {job_id}")

            # Update status to in_progress
            self.update_job_status(job_id, TranslationJobStatus.IN_PROGRESS)

            # Translate book metadata first
            try:
                translated_metadata = (
                    await self.translation_service.translate_book_metadata(
                        book_id=job["book_id"],
                        target_language=job["target_language"],
                        source_language=job["source_language"],
                    )
                )

                background_to_save = (
                    None if job["preserve_background"] else job.get("custom_background")
                )
                await self.translation_service.save_book_translation(
                    book_id=job["book_id"],
                    target_language=job["target_language"],
                    translated_data=translated_metadata,
                    custom_background=background_to_save,
                )

                logger.info(f"✅ Translated book metadata for job {job_id}")

            except Exception as e:
                logger.error(
                    f"❌ Failed to translate book metadata for job {job_id}: {e}"
                )
                self.update_job_status(
                    job_id,
                    TranslationJobStatus.FAILED,
                    error=f"Failed to translate book metadata: {str(e)}",
                )
                return

            # Get all chapters
            chapters = list(
                self.db.book_chapters.find({"book_id": job["book_id"]}).sort(
                    "order_index", 1
                )
            )

            completed_count = 0
            failed_count = 0

            # Translate each chapter
            for i, chapter in enumerate(chapters):
                chapter_num = i + 1
                chapter_id = chapter["chapter_id"]
                chapter_title = chapter.get("title", f"Chapter {chapter_num}")

                logger.info(
                    f"🌍 Translating chapter {chapter_num}/{len(chapters)}: {chapter_title}"
                )

                # Update current chapter in job
                self.update_job_status(
                    job_id,
                    TranslationJobStatus.IN_PROGRESS,
                    current_chapter_id=chapter_id,
                    current_chapter_title=chapter_title,
                )

                try:
                    # Translate chapter
                    chapter_translation = (
                        await self.translation_service.translate_chapter_content(
                            chapter_id=chapter_id,
                            target_language=job["target_language"],
                            source_language=job["source_language"],
                        )
                    )

                    # Save translation
                    await self.translation_service.save_chapter_translation(
                        chapter_id=chapter_id,
                        target_language=job["target_language"],
                        translated_data=chapter_translation,
                        custom_background=background_to_save,
                    )

                    completed_count += 1

                    # Update progress
                    self.update_job_status(
                        job_id,
                        TranslationJobStatus.IN_PROGRESS,
                        chapters_completed=completed_count,
                    )

                    logger.info(
                        f"✅ Completed chapter {chapter_num}/{len(chapters)}: {chapter_title}"
                    )

                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Failed to translate chapter {chapter_id}: {e}")

                    # Record failed chapter
                    self.update_job_status(
                        job_id,
                        TranslationJobStatus.IN_PROGRESS,
                        chapters_failed=failed_count,
                        failed_chapter={
                            "chapter_id": chapter_id,
                            "chapter_title": chapter_title,
                            "error": str(e),
                        },
                    )

                    # Continue with other chapters

            # Job completed
            final_status = (
                TranslationJobStatus.COMPLETED
                if failed_count == 0
                else (
                    TranslationJobStatus.FAILED
                    if completed_count == 0
                    else TranslationJobStatus.COMPLETED
                )  # Partial success
            )

            error_msg = None
            if failed_count > 0:
                error_msg = (
                    f"{failed_count}/{len(chapters)} chapters failed to translate"
                )

            self.update_job_status(
                job_id,
                final_status,
                chapters_completed=completed_count,
                chapters_failed=failed_count,
                error=error_msg,
                current_chapter_id=None,
                current_chapter_title=None,
            )

            logger.info(
                f"🏁 Translation job completed: {job_id} "
                f"({completed_count} succeeded, {failed_count} failed)"
            )

        except Exception as e:
            logger.error(f"❌ Translation job failed: {job_id} - {e}", exc_info=True)
            self.update_job_status(
                job_id,
                TranslationJobStatus.FAILED,
                error=str(e),
            )

    def get_user_jobs(
        self,
        user_id: str,
        limit: int = 20,
        skip: int = 0,
        book_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get translation jobs for a user"""
        query = {"user_id": user_id}
        if book_id:
            query["book_id"] = book_id

        jobs = list(
            self.jobs_collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        return jobs

    def count_user_jobs(
        self,
        user_id: str,
        book_id: Optional[str] = None,
    ) -> int:
        """Count translation jobs for a user"""
        query = {"user_id": user_id}
        if book_id:
            query["book_id"] = book_id

        return self.jobs_collection.count_documents(query)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a translation job"""
        job = self.get_job(job_id)
        if not job:
            return False

        # Only cancel if pending or in_progress
        if job["status"] not in [
            TranslationJobStatus.PENDING,
            TranslationJobStatus.IN_PROGRESS,
        ]:
            return False

        self.update_job_status(job_id, TranslationJobStatus.CANCELLED)
        logger.info(f"🛑 Translation job cancelled: {job_id}")

        return True
