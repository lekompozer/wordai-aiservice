"""
Slide Narration Subtitle Worker
Processes subtitle generation tasks from Redis queue
"""

import os
import sys
import asyncio
import logging
import signal
import time
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Load environment variables
env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
env_file = "development.env" if env_var == "development" else ".env"
load_dotenv(env_file)

from src.queue.queue_manager import QueueManager, set_job_status
from src.models.ai_queue_tasks import SlideNarrationSubtitleTask
from src.services.slide_narration_service import get_slide_narration_service
from src.database.db_manager import DBManager
from src.utils.logger import setup_logger

logger = setup_logger()


class SlideNarrationSubtitleWorker:
    """Worker that processes slide narration subtitle generation tasks from Redis queue"""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        redis_url: Optional[str] = None,
        batch_size: int = 1,
        max_retries: int = 2,
    ):
        self.worker_id = (
            worker_id or f"narration_subtitle_worker_{int(time.time())}_{os.getpid()}"
        )
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://redis-server:6379"
        )
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="slide_narration_subtitle"
        )
        self.narration_service = get_slide_narration_service()
        self.db_manager = DBManager()
        self.db = self.db_manager.db

        logger.info(f"🔧 Narration Subtitle Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            await self.queue_manager.connect()
            logger.info(
                f"✅ Worker {self.worker_id}: Connected to Redis narration_subtitle queue"
            )
        except Exception as e:
            logger.error(f"❌ Worker {self.worker_id}: Initialization failed: {e}")
            raise

    async def shutdown(self):
        """Gracefully shutdown worker"""
        logger.info(f"🛑 Worker {self.worker_id}: Shutting down...")
        self.running = False

        if self.queue_manager:
            await self.queue_manager.disconnect()

        logger.info(f"✅ Worker {self.worker_id}: Shutdown complete")

    def _get_next_version(self, presentation_id: str, language: str) -> int:
        """Get next version number for presentation subtitles in specific language"""
        latest = self.db.presentation_subtitles.find_one(
            {"presentation_id": presentation_id, "language": language},
            sort=[("version", -1)],
        )
        return (latest.get("version", 0) + 1) if latest else 1

    async def process_task(self, task: SlideNarrationSubtitleTask) -> bool:
        """
        Process a single subtitle generation task

        Args:
            task: SlideNarrationSubtitleTask from Redis queue

        Returns:
            bool: True if processing successful
        """
        job_id = task.job_id
        start_time = datetime.utcnow()

        try:
            logger.info(f"🎙️ Processing subtitle job {job_id}")
            logger.info(f"   Presentation: {task.presentation_id}")
            logger.info(
                f"   Slides: {len(task.slides)}, Mode: {task.mode}, Language: {task.language}"
            )

            # Normalize language code: convert BCP-47 to short code
            # Examples: "en-US" → "en", "vi-VN" → "vi", "zh-CN" → "zh"
            language = task.language.split("-")[0] if "-" in task.language else task.language
            
            logger.info(f"   Language normalized: {task.language} → {language}")

            # Update status to processing (Redis for realtime polling)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=task.user_id,
                presentation_id=task.presentation_id,
                started_at=start_time.isoformat(),
                slide_count=len(task.slides),
            )

            # Generate subtitles using service
            result = await self.narration_service.generate_subtitles(
                presentation_id=task.presentation_id,
                slides=task.slides,
                mode=task.mode,
                language=language,  # Use normalized language code
                user_query=task.user_query,
                title=task.title,
                topic=task.topic,
                user_id=task.user_id,
            )

            # Calculate total duration
            total_duration = sum(slide["slide_duration"] for slide in result["slides"])

            # Get next version number (for this language)
            version = self._get_next_version(task.presentation_id, language)

            # Save to presentation_subtitles collection (NEW v2 schema)
            subtitle_doc = {
                "presentation_id": task.presentation_id,
                "user_id": task.user_id,
                "version": version,
                "language": language,  # Use normalized short code (en, vi, zh)
                "mode": task.mode,
                "user_query": task.user_query,
                "slides": result["slides"],
                "total_duration": total_duration,
                "audio_status": "pending",  # Audio not generated yet
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            insert_result = self.db.presentation_subtitles.insert_one(subtitle_doc)
            subtitle_id = str(insert_result.inserted_id)

            logger.info(f"✅ Subtitle document created: {subtitle_id}")

            # Mark as completed (Redis for realtime polling)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=task.user_id,
                subtitle_id=subtitle_id,
                version=version,
                slide_count=len(result["slides"]),
                total_duration=total_duration,
                processing_time_ms=result["processing_time_ms"],
            )

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"✅ Subtitle job {job_id} completed in {elapsed:.1f}s")
            logger.info(f"   Generated subtitles for {len(result['slides'])} slides")
            logger.info(f"   Total duration: {total_duration:.1f}s")

            return True

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Subtitle job {job_id} failed: {e}", exc_info=True)

            # Update status to failed (Redis for realtime polling)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=task.user_id,
                error=error_msg,
            )

            return False

    async def run(self):
        """Main worker loop"""
        self.running = True
        logger.info(f"🚀 Worker {self.worker_id}: Starting to process tasks...")
        logger.info(f"   Batch size: {self.batch_size}")
        logger.info(f"   Max retries: {self.max_retries}")

        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.running:
            try:
                # Dequeue task (returns raw dict, not parsed model)
                task_data = await self.queue_manager.dequeue_generic_task(
                    worker_id=self.worker_id, timeout=5
                )

                if not task_data:
                    # No task available, wait before retry
                    await asyncio.sleep(2)
                    continue

                consecutive_errors = 0  # Reset error count on successful dequeue

                # Parse task
                task = SlideNarrationSubtitleTask(**task_data)

                # Process task
                success = await self.process_task(task)

                if not success:
                    logger.warning(f"⚠️  Task {task.task_id} processing failed")

            except KeyboardInterrupt:
                logger.info(f"⚠️  Worker {self.worker_id}: Keyboard interrupt received")
                break

            except Exception as e:
                consecutive_errors += 1
                logger.error(
                    f"❌ Worker {self.worker_id}: Unexpected error: {e}", exc_info=True
                )

                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(
                        f"💀 Worker {self.worker_id}: Too many consecutive errors ({consecutive_errors}), shutting down"
                    )
                    break

                await asyncio.sleep(5)

        logger.info(f"🏁 Worker {self.worker_id}: Stopped processing tasks")


async def main():
    """Main entry point"""
    worker = SlideNarrationSubtitleWorker()

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"⚠️  Received signal {sig}, initiating shutdown...")
        asyncio.create_task(worker.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker.initialize()
        await worker.run()
    except Exception as e:
        logger.error(f"❌ Worker crashed: {e}", exc_info=True)
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
