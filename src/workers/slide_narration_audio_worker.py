"""
Slide Narration Audio Worker
Processes audio generation tasks from Redis queue
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

from bson import ObjectId

from src.queue.queue_manager import QueueManager, set_job_status
from src.models.ai_queue_tasks import SlideNarrationAudioTask
from src.services.slide_narration_service import get_slide_narration_service
from src.services.online_test_utils import get_mongodb_service
from src.utils.logger import setup_logger

logger = setup_logger()


class SlideNarrationAudioWorker:
    """Worker that processes slide narration audio tasks from Redis queue"""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        redis_url: Optional[str] = None,
        batch_size: int = 1,
        max_retries: int = 2,
        max_concurrent_jobs: int = 3,
    ):
        self.worker_id = (
            worker_id or f"narration_audio_worker_{int(time.time())}_{os.getpid()}"
        )
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://redis-server:6379"
        )
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.max_concurrent_jobs = max_concurrent_jobs
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="slide_narration_audio"
        )
        self.narration_service = get_slide_narration_service()
        self.mongo = get_mongodb_service()

        logger.info(f"🔧 Narration Audio Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            await self.queue_manager.connect()
            logger.info(
                f"✅ Worker {self.worker_id}: Connected to Redis narration_audio queue"
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

    async def process_task(self, task: SlideNarrationAudioTask) -> bool:
        """
        Process a single audio generation task

        Args:
            task: SlideNarrationAudioTask from Redis queue

        Returns:
            bool: True if processing successful
        """
        job_id = task.job_id
        start_time = datetime.utcnow()

        try:
            logger.info(f"🎵 Processing audio job {job_id}")
            logger.info(f"   Subtitle: {task.subtitle_id}")

            # Update status to processing (Redis for realtime polling)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=task.user_id,
                presentation_id=task.presentation_id,
                subtitle_id=task.subtitle_id,
                started_at=start_time.isoformat(),
            )

            self.mongo.db.narration_audio_jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "processing",
                        "started_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            # Generate audio for all slides
            audio_docs = await self.narration_service.generate_audio_v2(
                subtitle_id=task.subtitle_id,
                voice_config=task.voice_config,
                user_id=task.user_id,
                force_regenerate=task.force_regenerate,
            )

            # Update presentation_subtitles with audio status and IDs
            merged_audio_id = str(audio_docs[0]["_id"]) if audio_docs else None
            audio_update = {
                "audio_status": "ready",
                "audio_generated_at": datetime.utcnow(),
                "merged_audio_id": merged_audio_id,
                "audio_count": len(audio_docs),
                "audio_metadata": {
                    "audio_type": (
                        audio_docs[0].get("audio_type", "merged_presentation")
                        if audio_docs
                        else None
                    ),
                    "duration_seconds": (
                        audio_docs[0]
                        .get("audio_metadata", {})
                        .get("duration_seconds", 0)
                        if audio_docs
                        else 0
                    ),
                    "slide_count": (
                        audio_docs[0].get("slide_count", 0) if audio_docs else 0
                    ),
                    "voice_name": task.voice_config.get("voice_name"),
                    "model": task.voice_config.get(
                        "model", "gemini-2.5-flash-preview-tts"
                    ),
                },
            }

            self.mongo.db.presentation_subtitles.update_one(
                {"_id": ObjectId(task.subtitle_id)},
                {"$set": audio_update},
            )
            logger.info(f"✅ Updated subtitle {task.subtitle_id} with audio status")

            # Mark as completed (Redis for realtime polling)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=task.user_id,
                audio_count=len(audio_docs),
                audio_ids=[str(doc["_id"]) for doc in audio_docs],
            )

            self.mongo.db.narration_audio_jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "audio_count": len(audio_docs),
                    }
                },
            )

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"✅ Audio job {job_id} completed in {elapsed:.1f}s")
            logger.info(f"   Generated {len(audio_docs)} audio files")

            return True

        except Exception as e:
            error_msg = str(e)

            # Check if this is a partial failure (some chunks succeeded)
            is_partial_failure = "Partial failure:" in error_msg

            if is_partial_failure:
                logger.warning(f"⚠️  Audio job {job_id} partially succeeded: {e}")

                # Update status to partial_success (Redis for realtime polling)
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=job_id,
                    status="partial_success",
                    user_id=task.user_id,
                    error=error_msg,
                    retry_message="Retry this job to generate remaining chunks",
                )

                self.mongo.db.narration_audio_jobs.update_one(
                    {"_id": job_id},
                    {
                        "$set": {
                            "status": "partial_success",
                            "updated_at": datetime.utcnow(),
                            "error": error_msg,
                            "retry_message": "Retry to generate remaining chunks. Previously completed chunks will be reused.",
                        }
                    },
                )

                return True  # Consider partial success as successful task

            # Full failure
            logger.error(f"❌ Audio job {job_id} failed: {e}", exc_info=True)

            # Update status to failed (Redis for realtime polling)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=task.user_id,
                error=error_msg,
            )

            self.mongo.db.narration_audio_jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "failed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "error": str(e),
                    }
                },
            )

            return False

    async def run(self):
        """Main worker loop with concurrency support"""
        self.running = True
        logger.info(f"🚀 Worker {self.worker_id}: Starting to process tasks...")
        logger.info(f"   Batch size: {self.batch_size}")
        logger.info(f"   Max retries: {self.max_retries}")
        logger.info(f"   🔄 Max concurrent jobs: {self.max_concurrent_jobs}")

        consecutive_errors = 0
        max_consecutive_errors = 5
        running_tasks = set()

        while self.running:
            try:
                # Fill up to max concurrency
                while len(running_tasks) < self.max_concurrent_jobs and self.running:
                    task_data = await self.queue_manager.dequeue_generic_task(
                        worker_id=self.worker_id, timeout=1
                    )

                    if not task_data:
                        break

                    consecutive_errors = 0  # Reset error count on successful dequeue

                    # Parse task
                    try:
                        task = SlideNarrationAudioTask(**task_data)
                    except Exception as parse_error:
                        logger.error(f"❌ Failed to parse task: {parse_error}")
                        continue

                    # Start task in background
                    task_future = asyncio.create_task(self.process_task(task))
                    running_tasks.add(task_future)
                    logger.info(f"📝 Started task {task.task_id} ({len(running_tasks)}/{self.max_concurrent_jobs} active)")

                # Wait for at least one task to complete
                if running_tasks:
                    done, running_tasks = await asyncio.wait(
                        running_tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    for completed_task in done:
                        try:
                            success = await completed_task
                            if not success:
                                logger.warning(f"⚠️  Task processing failed")
                        except Exception as e:
                            logger.error(f"❌ Task raised exception: {e}", exc_info=True)
                else:
                    await asyncio.sleep(2)

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
    worker = SlideNarrationAudioWorker()

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
