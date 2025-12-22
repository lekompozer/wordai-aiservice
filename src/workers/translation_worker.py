"""
Translation Worker for processing book translation jobs from Redis queue.
Pulls tasks from translation_jobs queue and translates books with Gemini.
"""

import os
import sys
import asyncio
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

from src.queue.queue_manager import QueueManager
from src.models.ai_queue_tasks import TranslationTask
from src.services.translation_job_service import TranslationJobService
from src.database.db_manager import DBManager
from src.utils.logger import setup_logger

logger = setup_logger()


class TranslationWorker:
    """Worker that processes translation jobs from Redis queue"""

    def __init__(
        self,
        worker_id: str = None,
        redis_url: str = None,
        batch_size: int = 1,
        max_retries: int = 2,
    ):
        self.worker_id = (
            worker_id or f"translation_worker_{int(time.time())}_{os.getpid()}"
        )
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://redis-server:6379"
        )
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="translation_jobs"
        )

        db_manager = DBManager()
        self.job_service = TranslationJobService(db_manager.db)

        logger.info(f"🔧 Translation Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            await self.queue_manager.connect()
            logger.info(
                f"✅ Worker {self.worker_id}: Connected to Redis translation_jobs queue"
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

    async def process_task(self, task: TranslationTask) -> bool:
        """
        Process a single translation task

        Args:
            task: TranslationTask from Redis queue

        Returns:
            bool: True if processing successful
        """
        job_id = task.job_id

        try:
            logger.info(
                f"🌐 Processing translation job {job_id} "
                f"(book={task.book_id}, {task.source_language} → {task.target_language})"
            )

            # Use existing translation job service to process
            await self.job_service.process_job(job_id)

            logger.info(f"✅ Translation job {job_id} completed successfully")

            return True

        except Exception as e:
            logger.error(f"❌ Translation job {job_id} failed: {e}", exc_info=True)
            return False

    async def run(self):
        """Main worker loop"""
        await self.initialize()
        self.running = True

        logger.info(f"🚀 Worker {self.worker_id}: Started processing translation tasks")

        while self.running:
            try:
                # Fetch task from Redis queue (blocking with timeout)
                task_data = await self.queue_manager.dequeue_task(
                    worker_id=self.worker_id, timeout=5
                )

                if not task_data:
                    # No task available, continue loop
                    continue

                # Parse task
                try:
                    task = TranslationTask(**task_data)
                except Exception as parse_error:
                    logger.error(f"❌ Failed to parse task: {parse_error}")
                    continue

                # Process task
                success = await self.process_task(task)

                if success:
                    logger.info(f"✅ Task {task.task_id} completed successfully")
                else:
                    logger.error(f"❌ Task {task.task_id} failed")

            except asyncio.CancelledError:
                logger.info(f"🛑 Worker {self.worker_id}: Cancelled")
                break
            except Exception as e:
                logger.error(
                    f"❌ Worker {self.worker_id}: Error in main loop: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(5)  # Wait before retrying

        await self.shutdown()


async def main():
    """Main entry point for Translation Worker"""
    worker = TranslationWorker()

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info(f"📡 Received signal {sig}, initiating graceful shutdown...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Run worker
        worker_task = asyncio.create_task(worker.run())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for either task to complete
        done, pending = await asyncio.wait(
            [worker_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("✅ Translation Worker shutdown complete")

    except Exception as e:
        logger.error(f"❌ Translation Worker fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
