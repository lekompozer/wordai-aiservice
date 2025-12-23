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

from src.queue.queue_manager import (
    QueueManager,
    set_job_status,
    update_job_field,
    get_job_status,
)
from src.models.ai_queue_tasks import SlideFormatTask
from src.services.slide_ai_service import get_slide_ai_service

logger = logging.getLogger("chatbot")


class SlideFormatWorker:
    """Worker for processing slide AI format tasks"""

    def __init__(
        self,
        worker_id: str = "slide_format_worker",
        redis_url: str = "redis://redis-server:6379",
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

            if task.is_batch:
                logger.info(
                    f"   📦 Batch processing: {task.total_slides} slides (1 AI call)"
                )
                if task.process_entire_document:
                    logger.info(f"   📋 Mode 3: Entire document")
                else:
                    logger.info(f"   📋 Mode 2: Selected slides")

            # Update job status to "processing" in Redis
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=task.user_id,
                started_at=start_time.isoformat(),
                slide_index=task.slide_index,
                format_type=task.format_type,
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

            # Handle result based on mode
            if task.is_batch:
                # Mode 2 & 3: Split combined HTML back to individual slides
                formatted_html = result["formatted_html"]

                # Parse slides (assuming AI returns with same markers)
                import re

                slide_htmls = re.split(r"<!-- Slide \d+ -->\s*", formatted_html)
                slide_htmls = [html.strip() for html in slide_htmls if html.strip()]

                # Update batch job with all results at once
                slides_results = []
                for i, html in enumerate(slide_htmls):
                    slides_results.append(
                        {
                            "slide_index": i,
                            "formatted_html": html,
                            "suggested_elements": result.get("suggested_elements", []),
                            "suggested_background": result.get("suggested_background"),
                            "ai_explanation": result.get("ai_explanation", ""),
                            "error": None,
                        }
                    )

                # Update batch job status to completed
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=task.batch_job_id,
                    status="completed",
                    user_id=task.user_id,
                    completed_slides=len(slides_results),
                    failed_slides=0,
                    slides_results=slides_results,
                    completed_at=end_time.isoformat(),
                    processing_time_seconds=processing_time,
                )

                logger.info(
                    f"✅ Batch completed: {len(slides_results)} slides in {processing_time:.1f}s (1 AI call)"
                )
            else:
                # Mode 1: Single slide processing
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=job_id,
                    status="completed",
                    user_id=task.user_id,
                    formatted_html=result["formatted_html"],
                    suggested_elements=result.get("suggested_elements", []),
                    suggested_background=result.get("suggested_background"),
                    ai_explanation=result["ai_explanation"],
                    completed_at=end_time.isoformat(),
                    processing_time_seconds=processing_time,
                )

                logger.info(
                    f"✅ Job {job_id} completed in {processing_time:.1f}s (slide {task.slide_index})"
                )

            return True

        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)

            # Update status to failed
            if task.is_batch:
                # Mode 2 & 3: Fail entire batch job
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=task.batch_job_id,
                    status="failed",
                    user_id=task.user_id,
                    error=str(e),
                    completed_at=datetime.utcnow().isoformat(),
                    failed_slides=task.total_slides,
                )
            else:
                # Mode 1: Fail individual job
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=job_id,
                    status="failed",
                    user_id=task.user_id,
                    error=str(e),
                    completed_at=datetime.utcnow().isoformat(),
                )

            return False

    async def _update_batch_job(
        self,
        batch_job_id: str,
        slide_index: int,
        result: dict = None,
        error: str = None,
    ):
        """Update parent batch job with slide result"""
        try:
            # Get current batch job
            batch_job = await get_job_status(
                self.queue_manager.redis_client, batch_job_id
            )
            if not batch_job:
                logger.warning(f"⚠️ Batch job {batch_job_id} not found in Redis")
                return

            # Get or initialize slides_results
            slides_results = batch_job.get("slides_results", [])

            # Add/update this slide's result
            slide_result = {
                "slide_index": slide_index,
                "formatted_html": result.get("formatted_html") if result else None,
                "suggested_elements": (
                    result.get("suggested_elements", []) if result else None
                ),
                "suggested_background": (
                    result.get("suggested_background") if result else None
                ),
                "ai_explanation": result.get("ai_explanation") if result else None,
                "error": error,
            }

            # Remove existing result for this slide (if any) and add new one
            slides_results = [
                r for r in slides_results if r.get("slide_index") != slide_index
            ]
            slides_results.append(slide_result)

            # Count completed and failed
            completed_slides = len(
                [r for r in slides_results if r.get("formatted_html")]
            )
            failed_slides = len([r for r in slides_results if r.get("error")])
            total_slides = batch_job.get("total_slides", 0)

            # Determine if batch is complete
            all_done = (completed_slides + failed_slides) == total_slides

            # Update batch job
            update_data = {
                "slides_results": slides_results,
                "completed_slides": completed_slides,
                "failed_slides": failed_slides,
            }

            if all_done:
                update_data["status"] = "completed"
                update_data["completed_at"] = datetime.utcnow().isoformat()
            elif completed_slides > 0 or failed_slides > 0:
                update_data["status"] = "processing"
                if not batch_job.get("started_at"):
                    update_data["started_at"] = datetime.utcnow().isoformat()

            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=batch_job_id,
                user_id=batch_job.get("user_id"),
                **update_data,
            )

            logger.info(
                f"📦 Batch job {batch_job_id}: {completed_slides}/{total_slides} completed, {failed_slides} failed"
            )

        except Exception as e:
            logger.error(
                f"❌ Failed to update batch job {batch_job_id}: {e}", exc_info=True
            )

    async def run(self):
        """Main worker loop"""
        await self.initialize()
        self.running = True

        logger.info(f"🚀 Worker {self.worker_id}: Started processing tasks")

        while self.running:
            try:
                # Fetch task from Redis queue
                task_data = await self.queue_manager.dequeue_generic_task(
                    worker_id=self.worker_id, timeout=5
                )

                if not task_data:
                    await asyncio.sleep(1)
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
        redis_url=os.getenv("REDIS_URL", "redis://redis-server:6379"),
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
