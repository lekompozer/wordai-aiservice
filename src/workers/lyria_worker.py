"""
Lyria Music Generation Worker
Processes music generation tasks from Redis queue
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
from src.models.lyria_models import LyriaMusicTask
from src.services.lyria_service import get_lyria_service
from src.services.r2_storage_service import get_r2_service
from src.database.db_manager import DBManager
from src.services.library_manager import LibraryManager
from src.services.points_service import get_points_service
from src.utils.logger import setup_logger

logger = setup_logger()


class LyriaMusicWorker:
    """Worker that processes Lyria music generation tasks from Redis queue"""

    # Job timeout: 15 minutes (music generation ~30-60s, but allow buffer for retries)
    JOB_TIMEOUT_SECONDS = 900

    def __init__(
        self,
        worker_id: Optional[str] = None,
        redis_url: Optional[str] = None,
        batch_size: int = 1,
        max_retries: int = 3,
        max_concurrent_jobs: int = 2,
    ):
        self.worker_id = (
            worker_id or f"lyria_music_worker_{int(time.time())}_{os.getpid()}"
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
            redis_url=self.redis_url, queue_name="lyria_music"
        )
        self.lyria_service = get_lyria_service()
        self.r2_service = get_r2_service()

        # Database and library
        db_manager = DBManager()
        self.db = db_manager.db
        self.library_manager = LibraryManager(
            db=self.db, s3_client=self.r2_service.s3_client
        )
        self.points_service = get_points_service()

        logger.info(f"🔧 Lyria Music Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            await self.queue_manager.connect()
            logger.info(
                f"✅ Worker {self.worker_id}: Connected to Redis lyria_music queue"
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

    async def process_task(self, task: LyriaMusicTask) -> bool:
        """
        Process a single music generation task

        Args:
            task: LyriaMusicTask from Redis queue

        Returns:
            bool: True if processing successful
        """
        job_id = task.job_id
        start_time = datetime.utcnow()

        try:
            logger.info(f"🎵 Processing music job {job_id}")
            logger.info(f"   Prompt: {task.prompt[:100]}...")

            # Update status to processing (Redis for realtime polling)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=task.user_id,
                prompt=task.prompt,
                started_at=start_time.isoformat(),
            )

            # Generate music using Lyria
            audio_bytes, metadata = await self.lyria_service.generate_music(
                prompt=task.prompt,
                negative_prompt=task.negative_prompt,
                seed=task.seed,
            )

            logger.info(f"✅ Music generated: {len(audio_bytes)} bytes")
            logger.info(f"   Duration: ~{metadata.get('duration_seconds', 30)}s")

            # Upload to R2
            timestamp = int(time.time())
            file_name = f"lyria_music_{task.user_id}_{timestamp}.mp3"
            r2_key = f"lyria/{task.user_id}/{job_id}.mp3"

            upload_result = await self.r2_service.upload_file(
                file_content=audio_bytes,
                r2_key=r2_key,
                content_type="audio/mpeg",
            )
            audio_url = upload_result["public_url"]

            logger.info(f"✅ Uploaded to R2: {audio_url}")

            # Save to library_audio
            library_audio = self.library_manager.save_library_file(
                user_id=task.user_id,
                filename=file_name,
                file_type="audio",
                category="audio",
                r2_url=audio_url,
                r2_key=r2_key,
                file_size=len(audio_bytes),
                mime_type="audio/mpeg",
                metadata={
                    "source_type": "lyria_music",
                    "job_id": job_id,
                    "prompt": task.prompt,
                    "negative_prompt": task.negative_prompt,
                    "seed": task.seed,
                    "model": metadata.get("model", "lyria-002"),
                    "duration_seconds": metadata.get("duration_seconds", 30),
                    "format": "mp3",
                },
            )

            library_audio_id = str(
                library_audio.get("library_id", library_audio.get("file_id"))
            )

            logger.info(f"✅ Saved to library_audio: {library_audio_id}")

            # Mark as completed (Redis for realtime polling)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=task.user_id,
                audio_url=audio_url,
                library_audio_id=library_audio_id,
                duration_seconds=metadata.get("duration_seconds", 30),
            )

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"✅ Music job {job_id} completed in {elapsed:.1f}s")
            logger.info(f"   Audio URL: {audio_url}")
            logger.info(f"   Library ID: {library_audio_id}")

            return True

        except Exception as e:
            logger.error(f"❌ Music job {job_id} failed: {e}", exc_info=True)

            # Mark as failed (Redis for realtime polling)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=task.user_id,
                error=str(e),
            )

            # Refund points on failure
            try:
                await self.points_service.refund_points(
                    user_id=task.user_id,
                    amount=3,  # POINTS_COST_MUSIC
                    reason=f"Lyria music generation failed: {str(e)[:100]}",
                )
                logger.info(f"✅ Refunded 3 points to user {task.user_id}")
            except Exception as refund_error:
                logger.error(f"❌ Failed to refund points: {refund_error}")

            # Re-raise to trigger retry (if retries remaining)
            raise

    async def run(self):
        """Main worker loop - process tasks from queue with timeout protection"""
        self.running = True
        logger.info(
            f"🚀 Worker {self.worker_id} starting (timeout={self.JOB_TIMEOUT_SECONDS}s)"
        )

        # Setup signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            logger.info(
                f"🛑 Worker {self.worker_id}: Received signal {sig}, shutting down..."
            )
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        while self.running:
            try:
                # Dequeue single task
                task_data = await self.queue_manager.dequeue_generic_task(
                    worker_id=self.worker_id,
                    timeout=5,  # 5 second timeout for blocking pop
                )

                if not task_data:
                    # No tasks, wait before polling again
                    await asyncio.sleep(2)
                    continue

                # Parse task
                task = LyriaMusicTask(**task_data)

                # Process task with timeout protection
                try:
                    await asyncio.wait_for(
                        self.process_task(task), timeout=self.JOB_TIMEOUT_SECONDS
                    )
                    logger.info(
                        f"✅ Worker {self.worker_id}: Completed task {task.job_id} within {self.JOB_TIMEOUT_SECONDS}s timeout"
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        f"⏱️ Worker {self.worker_id}: Task {task.job_id} exceeded {self.JOB_TIMEOUT_SECONDS}s timeout - marking as failed"
                    )
                    # Mark job as failed due to timeout
                    await set_job_status(
                        redis_client=self.queue_manager.redis_client,
                        job_id=task.job_id,
                        status="failed",
                        error=f"Job exceeded {self.JOB_TIMEOUT_SECONDS}s timeout",
                        updated_at=datetime.utcnow().isoformat(),
                    )

                    # Refund points on timeout
                    try:
                        points_service = get_points_service()
                        await points_service.refund_points(
                            user_id=task.user_id,
                            amount=3,  # POINTS_COST_MUSIC
                            reason=f"Lyria music generation timeout after {self.JOB_TIMEOUT_SECONDS}s",
                        )
                        logger.info(
                            f"💰 Refunded points for user {task.user_id} due to timeout"
                        )
                    except Exception as refund_err:
                        logger.error(
                            f"❌ Failed to refund points: {refund_err}",
                            exc_info=True,
                        )

            except Exception as e:
                logger.error(f"❌ Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retrying

        logger.info(f"✅ Worker {self.worker_id} stopped")


async def main():
    """Main entry point for worker"""
    worker = LyriaMusicWorker()

    try:
        await worker.initialize()
        await worker.run()
    except KeyboardInterrupt:
        logger.info("🛑 Worker interrupted by user")
    except Exception as e:
        logger.error(f"❌ Worker crashed: {e}", exc_info=True)
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
