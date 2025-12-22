"""
AI Editor Job Service
Background processing for long-running AI edit/format operations
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict
import uuid
from loguru import logger

from src.services.mongo_service import MongoService
from src.services.claude_service import ClaudeService
from src.models.ai_editor_job_models import (
    AIEditorJobDocument,
    AIEditorJobType,
    AIEditorJobStatus,
)


class AIEditorJobService:
    """Service for managing AI editor async jobs"""

    def __init__(self, mongo_service: MongoService):
        self.mongo = mongo_service
        self.db = mongo_service.db
        self.jobs_collection = self.db["ai_editor_jobs"]
        self.claude = ClaudeService()

    async def create_job(
        self,
        document_id: str,
        job_type: AIEditorJobType,
        content_type: str,
        content: str,
        user_query: Optional[str] = None,
    ) -> str:
        """
        Create a new AI editor job

        Args:
            document_id: Document ID
            job_type: edit or format
            content_type: document, slide, etc.
            content: HTML content to process
            user_query: Optional user instruction

        Returns:
            job_id: Job ID for polling
        """
        job_id = str(uuid.uuid4())
        estimated_tokens = len(content) // 4

        job_doc = {
            "job_id": job_id,
            "document_id": document_id,
            "job_type": job_type.value,
            "content_type": content_type,
            "status": AIEditorJobStatus.PENDING.value,
            "content": content,
            "user_query": user_query,
            "result": None,
            "error": None,
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "content_size": len(content),
            "estimated_tokens": estimated_tokens,
            "actual_tokens": None,
            "processing_time_seconds": None,
        }

        await self.jobs_collection.insert_one(job_doc)

        logger.info(
            f"📝 Created AI editor job {job_id} "
            f"(type={job_type.value}, size={len(content):,} chars, ~{estimated_tokens:,} tokens)"
        )

        # Start processing in background (fire and forget)
        asyncio.create_task(self._process_job(job_id))

        return job_id

    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """
        Get job status and result

        Args:
            job_id: Job ID

        Returns:
            Job document or None if not found
        """
        job = await self.jobs_collection.find_one({"job_id": job_id})
        return job

    async def _process_job(self, job_id: str):
        """
        Background job processor
        Runs AI operation and updates status
        """
        try:
            # Get job
            job = await self.jobs_collection.find_one({"job_id": job_id})
            if not job:
                logger.error(f"❌ Job {job_id} not found")
                return

            # Update to processing
            await self.jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": AIEditorJobStatus.PROCESSING.value,
                        "started_at": datetime.utcnow(),
                    }
                },
            )

            logger.info(f"⚙️ Processing job {job_id} (type={job['job_type']})...")

            start_time = datetime.utcnow()

            # Process based on job type
            if job["job_type"] == AIEditorJobType.FORMAT.value:
                result = await self._format_content(
                    job["content"],
                    job["content_type"],
                    job.get("user_query"),
                )
            elif job["job_type"] == AIEditorJobType.EDIT.value:
                result = await self._edit_content(
                    job["content"],
                    job.get("user_query"),
                )
            else:
                raise ValueError(f"Unknown job type: {job['job_type']}")

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            # Update to completed
            await self.jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": AIEditorJobStatus.COMPLETED.value,
                        "result": result,
                        "completed_at": end_time,
                        "processing_time_seconds": processing_time,
                    }
                },
            )

            logger.info(
                f"✅ Job {job_id} completed in {processing_time:.1f}s "
                f"(output: {len(result):,} chars)"
            )

        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}")

            # Update to failed
            await self.jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": AIEditorJobStatus.FAILED.value,
                        "error": str(e),
                        "completed_at": datetime.utcnow(),
                    }
                },
            )

    async def _format_content(
        self,
        content: str,
        content_type: str,
        user_query: Optional[str] = None,
    ) -> str:
        """Format content using Claude"""
        if content_type == "slide":
            return await self.claude.format_slide_html(content, user_query)
        else:
            return await self.claude.format_document_html(content, user_query)

    async def _edit_content(
        self,
        content: str,
        user_query: Optional[str] = None,
    ) -> str:
        """Edit content using Claude"""
        return await self.claude.edit_html(content, user_query)

    async def cleanup_old_jobs(self, days: int = 7):
        """
        Cleanup old completed/failed jobs

        Args:
            days: Delete jobs older than this many days
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        result = await self.jobs_collection.delete_many(
            {
                "status": {
                    "$in": [
                        AIEditorJobStatus.COMPLETED.value,
                        AIEditorJobStatus.FAILED.value,
                    ]
                },
                "created_at": {"$lt": cutoff},
            }
        )

        logger.info(f"🧹 Cleaned up {result.deleted_count} old AI editor jobs")

        return result.deleted_count
