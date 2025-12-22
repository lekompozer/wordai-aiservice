"""
Slide Format Worker
Processes slide AI formatting tasks from Redis queue
"""

import asyncio
import logging
import os
import signal
from datetime import datetime
from typing import Optional

from src.queue.queue_manager import QueueManager
from src.models.ai_queue_tasks import SlideFormatTask
from src.services.online_test_utils import get_mongodb_service
from src.services.slide_ai_service import get_slide_ai_service

logger = logging.getLogger("chatbot")


class SlideFormatWorker:
    """Worker for processing slide AI format tasks"""

    def __init__(
        self,
        worker_id: str = "slide_format_worker",
        redis_url: str = "redis://localhost:6379",
        batch_size: int = 1,
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.batch_size = batch_size
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="slide_format"
        )
        self.slide_ai_service = get_slide_ai_service()
        self.mongo = get_mongodb_service()
        self.jobs_collection = self.mongo.db["slide_format_jobs"]

        logger.info(f"🔧 Slide Format Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            await self.queue_manager.connect()
            logger.info(
                f"✅ Worker {self.worker_id}: Connected to Redis slide_format queue"
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
            logger.info(f"✅ Worker {self.worker_id}: Queue disconnected")

    async def process_task(self, task: SlideFormatTask) -> bool:
        """
        Process slide format task

        Args:
            task: SlideFormatTask from Redis queue

        Returns:
            bool: True if processing successful
        """
        job_id = task.job_id
        start_time = datetime.utcnow()

        try:
            logger.info(
                f"⚙️ Processing slide format job {job_id} (slide={task.slide_index}, type={task.format_type})"
            )

            # Create job in MongoDB (upsert to handle race conditions)
            self.jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$setOnInsert": {
                        "job_id": job_id,
                        "user_id": task.user_id,
                        "slide_index": task.slide_index,
                        "format_type": task.format_type,
                        "created_at": start_time,
                    },
                    "$set": {
                        "status": "processing",
                        "started_at": start_time,
                    },
                },
                upsert=True,
            )

            # Build request object for slide AI service
            class FormatRequest:
                slide_index = task.slide_index
                current_html = task.current_html
                elements = task.elements
                background = task.background
                user_instruction = task.user_instruction
                format_type = task.format_type

            request = FormatRequest()

            # Process with slide AI service
            result = await self.slide_ai_service.format_slide(request, task.user_id)

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            # Update status to completed
            self.jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "completed",
                        "formatted_html": result["formatted_html"],
                        "suggested_elements": result.get("suggested_elements", []),
                        "suggested_background": result.get("suggested_background"),
                        "ai_explanation": result["ai_explanation"],
                        "completed_at": end_time,
                        "processing_time_seconds": processing_time,
                    }
                },
            )

            logger.info(
                f"✅ Job {job_id} completed in {processing_time:.1f}s "
                f"(slide {task.slide_index})"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)

            # Update status to failed
            self.jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": str(e),
                        "completed_at": datetime.utcnow(),
                    }
                },
            )

            return False

    async def run(self):
        """Main worker loop"""
        await self.initialize()
        self.running = True

        logger.info(f"🚀 Worker {self.worker_id}: Started processing tasks")

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
                    task = SlideFormatTask(**task_data)
                except Exception as parse_error:
                    logger.error(f"❌ Failed to parse task: {parse_error}")
                    continue

                # Process task
                success = await self.process_task(task)

                if not success:
                    logger.warning(f"⚠️ Task {task.task_id} processing failed")

            except asyncio.CancelledError:
                logger.info(f"🛑 Worker {self.worker_id}: Cancelled")
                break
            except Exception as e:
                logger.error(
                    f"❌ Worker {self.worker_id}: Error in main loop: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(5)  # Wait before retry

        logger.info(f"🏁 Worker {self.worker_id}: Stopped")


async def main():
    """Main entry point for worker"""
    worker = SlideFormatWorker(
        worker_id=os.getenv("WORKER_ID", "slide_format_worker_1"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
    )

    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info(f"📡 Received signal {sig}, shutting down...")
        asyncio.create_task(worker.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker.run()
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
