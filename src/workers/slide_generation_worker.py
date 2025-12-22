"""
Slide Generation Worker for processing slide generation tasks from Redis queue.
Pulls tasks from slide_generation queue and generates HTML with Gemini.
"""

import os
import sys
import asyncio
import logging
import signal
import time
from typing import Optional, List, Dict
from datetime import datetime
from dotenv import load_dotenv
from bson import ObjectId

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Load environment variables
env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
env_file = "development.env" if env_var == "development" else ".env"
load_dotenv(env_file)

from src.queue.queue_manager import QueueManager
from src.models.ai_queue_tasks import SlideGenerationTask
from src.services.slide_ai_generation_service import get_slide_ai_service
from src.services.document_manager import DocumentManager
from src.services.points_service import get_points_service
from src.services.online_test_utils import get_mongodb_service
from src.utils.logger import setup_logger

logger = setup_logger()


class SlideGenerationWorker:
    """Worker that processes slide generation tasks from Redis queue"""

    def __init__(
        self,
        worker_id: str = None,
        redis_url: str = None,
        batch_size: int = 1,
        max_retries: int = 3,
    ):
        self.worker_id = (
            worker_id or f"slide_gen_worker_{int(time.time())}_{os.getpid()}"
        )
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="slide_generation"
        )
        self.ai_service = get_slide_ai_service()
        self.mongo = get_mongodb_service()
        self.doc_manager = DocumentManager(self.mongo.db)

        logger.info(f"🔧 Slide Generation Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            await self.queue_manager.connect()
            logger.info(
                f"✅ Worker {self.worker_id}: Connected to Redis slide_generation queue"
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

    async def process_task(self, task: SlideGenerationTask) -> bool:
        """
        Process a single slide generation task

        Args:
            task: SlideGenerationTask from Redis queue

        Returns:
            bool: True if processing successful
        """
        document_id = task.document_id
        start_time = datetime.utcnow()

        try:
            logger.info(f"🎨 Processing slide generation for document {document_id}")

            # Get document and analysis
            doc = self.mongo.db["documents"].find_one({"document_id": document_id})
            if not doc:
                raise Exception(f"Document {document_id} not found")

            analysis = self.mongo.db["slide_analyses"].find_one(
                {"_id": ObjectId(task.analysis_id), "user_id": task.user_id}
            )
            if not analysis:
                raise Exception(f"Analysis {task.analysis_id} not found")

            # Get generation data from document
            gen_data = doc.get("slide_generation_data", {})
            logo_url = gen_data.get("logo_url")
            slide_images = gen_data.get("slide_images", {})
            user_query = gen_data.get("user_query")
            points_needed = gen_data.get("points_needed", 2)

            # Update status to processing
            self.mongo.db["documents"].update_one(
                {"document_id": document_id},
                {
                    "$set": {
                        "ai_generation_status": "processing",
                        "updated_at": datetime.now(),
                    }
                },
            )

            # Get slides from analysis
            slides_outline = analysis["slides_outline"]
            num_slides = len(slides_outline)
            total_batches = (num_slides + 14) // 15  # Max 15 slides per batch

            logger.info(
                f"📊 Generating {num_slides} slides in {total_batches} batch(es)"
            )

            # Generate HTML in batches
            all_slides_html = []
            for i in range(total_batches):
                start_idx = i * 15
                end_idx = min((i + 1) * 15, num_slides)
                batch_slides = slides_outline[start_idx:end_idx]

                logger.info(
                    f"🔄 Batch {i+1}/{total_batches}: slides {start_idx+1}-{end_idx}"
                )

                # Call AI to generate HTML for this batch
                batch_html = await self.ai_service.generate_slide_html_batch(
                    title=analysis["title"],
                    slide_type=analysis["slide_type"],
                    language=analysis["language"],
                    slides_outline=batch_slides,
                    slide_images=slide_images,
                    logo_url=logo_url,
                    user_query=user_query,
                    batch_number=i + 1,
                    total_batches=total_batches,
                )

                all_slides_html.extend(batch_html)

                # Update progress
                progress = int((i + 1) / total_batches * 100)
                self.mongo.db["documents"].update_one(
                    {"document_id": document_id},
                    {
                        "$set": {
                            "ai_progress_percent": progress,
                            "updated_at": datetime.now(),
                        }
                    },
                )

                logger.info(f"✅ Batch {i+1}/{total_batches} completed ({progress}%)")

                # Small delay between batches
                if i < total_batches - 1:
                    await asyncio.sleep(0.5)

            # Combine all slides into final HTML
            final_html = "\n\n".join(all_slides_html)

            # Create default backgrounds
            slide_backgrounds = self._create_default_backgrounds(
                num_slides, analysis["slide_type"]
            )

            logger.info(f"✅ All slides generated. Total: {num_slides}")

            # Save final HTML to document
            self.doc_manager.update_document(
                document_id=document_id,
                user_id=task.user_id,
                title=analysis["title"],
                content_html=final_html,
                content_text=analysis.get("presentation_summary", ""),
                slide_backgrounds=slide_backgrounds,
            )

            # Update AI generation status
            self.mongo.db["documents"].update_one(
                {"document_id": document_id},
                {
                    "$set": {
                        "ai_generation_status": "completed",
                        "ai_progress_percent": 100,
                        "updated_at": datetime.now(),
                    }
                },
            )

            # Deduct points (only after successful completion)
            points_service = get_points_service()
            await points_service.deduct_points(
                user_id=task.user_id,
                amount=points_needed,
                service="slide_ai_generation",
                resource_id=document_id,
                description=f"AI Slide Generation: {num_slides} slides ({total_batches} batches)",
            )

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            logger.info(
                f"✅ Slide generation completed: {document_id} in {processing_time:.1f}s, "
                f"deducted {points_needed} points"
            )

            return True

        except Exception as e:
            logger.error(
                f"❌ Slide generation failed: {document_id}, error: {e}", exc_info=True
            )

            # Mark as failed
            self.mongo.db["documents"].update_one(
                {"document_id": document_id},
                {
                    "$set": {
                        "ai_generation_status": "failed",
                        "ai_error_message": str(e),
                        "updated_at": datetime.now(),
                    }
                },
            )

            return False

    def _create_default_backgrounds(
        self, num_slides: int, slide_type: str
    ) -> List[dict]:
        """Create default gradient backgrounds for slides"""

        # Color schemes based on slide type
        academy_gradients = [
            {
                "type": "gradient",
                "gradient": {
                    "type": "linear",
                    "colors": ["#667eea", "#764ba2"],
                    "angle": 135,
                },
            },
            {
                "type": "gradient",
                "gradient": {
                    "type": "linear",
                    "colors": ["#f093fb", "#f5576c"],
                    "angle": 135,
                },
            },
            {
                "type": "gradient",
                "gradient": {
                    "type": "linear",
                    "colors": ["#4facfe", "#00f2fe"],
                    "angle": 135,
                },
            },
            {"type": "color", "value": "#ffffff"},
        ]

        business_gradients = [
            {
                "type": "gradient",
                "gradient": {
                    "type": "linear",
                    "colors": ["#232526", "#414345"],
                    "angle": 135,
                },
            },
            {
                "type": "gradient",
                "gradient": {
                    "type": "linear",
                    "colors": ["#373B44", "#4286f4"],
                    "angle": 135,
                },
            },
            {
                "type": "gradient",
                "gradient": {
                    "type": "linear",
                    "colors": ["#1e3c72", "#2a5298"],
                    "angle": 135,
                },
            },
            {"type": "color", "value": "#ffffff"},
        ]

        gradients = (
            business_gradients if slide_type == "business" else academy_gradients
        )

        # Assign backgrounds cyclically
        backgrounds = []
        for i in range(num_slides):
            backgrounds.append(gradients[i % len(gradients)])

        return backgrounds

    async def run(self):
        """Main worker loop"""
        await self.initialize()
        self.running = True

        logger.info(
            f"🚀 Worker {self.worker_id}: Started processing slide generation tasks"
        )

        while self.running:
            try:
                # Fetch task from Redis queue (blocking with timeout)
                task_data = await self.queue_manager.dequeue_task(timeout=5)

                if not task_data:
                    # No task available, continue loop
                    continue

                # Parse task
                try:
                    task = SlideGenerationTask(**task_data)
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
    """Main entry point for Slide Generation Worker"""
    worker = SlideGenerationWorker()

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

        logger.info("✅ Slide Generation Worker shutdown complete")

    except Exception as e:
        logger.error(f"❌ Slide Generation Worker fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
