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

from src.queue.queue_manager import QueueManager, set_job_status
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
        worker_id: Optional[str] = None,
        redis_url: Optional[str] = None,
        batch_size: int = 1,
        max_retries: int = 3,
        max_concurrent_jobs: int = 3,
    ):
        self.worker_id = (
            worker_id or f"slide_gen_worker_{int(time.time())}_{os.getpid()}"
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
        # Route based on step
        if task.step == 1:
            # Step 1: Analysis (text or PDF)
            return await self.process_analysis_task(task)
        elif task.step == 2:
            # Step 2: HTML generation
            return await self.process_html_generation_task(task)
        else:
            logger.error(f"❌ Unknown task step: {task.step}")
            return False

    async def process_analysis_task(self, task: SlideGenerationTask) -> bool:
        """
        Process Step 1: Slide analysis (text or PDF)

        Args:
            task: SlideGenerationTask with step=1

        Returns:
            bool: True if successful
        """
        analysis_id = task.document_id  # analysis_id is stored as document_id
        start_time = datetime.utcnow()

        try:
            logger.info(
                f"📝 Processing slide analysis for analysis_id {analysis_id} (user: {task.user_id})"
            )

            # Update Redis status to processing
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=analysis_id,
                status="processing",
                user_id=task.user_id,
                started_at=start_time.isoformat(),
                title=task.title or "Untitled Analysis",
            )

            # Determine if text-based or PDF-based analysis
            is_pdf = task.file_id is not None

            if is_pdf:
                logger.info(f"📄 PDF-based analysis: file_id={task.file_id}")

                # Validate required fields for PDF analysis
                if not all(
                    [
                        task.file_id,
                        task.title,
                        task.target_goal,
                        task.slide_type,
                        task.num_slides_range,
                        task.language,
                        task.user_query,
                    ]
                ):
                    raise Exception("Missing required fields for PDF analysis")

                # 1. Get file info from MongoDB to get R2 key
                from src.services.user_manager import get_user_manager

                user_manager = get_user_manager()
                file_doc = user_manager.get_file_by_id(
                    str(task.file_id), task.user_id  # type: ignore
                )

                if not file_doc:
                    raise Exception(
                        f"File {task.file_id} not found for user {task.user_id}"
                    )

                r2_key = file_doc.get("r2_key")
                if not r2_key:
                    raise Exception(f"File {task.file_id} has no R2 key")

                # 2. Download PDF from R2 to temp file
                from src.services.file_download_service import FileDownloadService

                logger.info(f"📥 Downloading PDF from R2: {r2_key}")
                temp_file_path = (
                    await FileDownloadService._download_file_from_r2_with_boto3(
                        r2_key, "pdf"
                    )
                )

                if not temp_file_path:
                    raise Exception(f"Failed to download PDF from R2 key: {r2_key}")

                logger.info(f"✅ PDF downloaded to: {temp_file_path}")

                # 3. Call PDF analysis service with local file path
                try:
                    analysis_result = (
                        await self.ai_service.analyze_slide_requirements_from_pdf(
                            title=task.title,  # type: ignore
                            target_goal=task.target_goal,  # type: ignore
                            slide_type=task.slide_type,  # type: ignore
                            num_slides_range=task.num_slides_range,  # type: ignore
                            language=task.language,  # type: ignore
                            user_query=task.user_query,  # type: ignore
                            pdf_path=temp_file_path,
                        )
                    )
                finally:
                    # Cleanup temp file
                    import os

                    try:
                        os.remove(temp_file_path)
                        logger.info(f"🗑️ Cleaned up temp file: {temp_file_path}")
                    except Exception as cleanup_error:
                        logger.warning(
                            f"⚠️ Failed to cleanup temp file: {cleanup_error}"
                        )
            else:
                logger.info(f"📝 Text-based analysis")

                # Validate required fields for text analysis
                if not all(
                    [
                        task.title,
                        task.target_goal,
                        task.slide_type,
                        task.num_slides_range,
                        task.language,
                        task.user_query,
                    ]
                ):
                    raise Exception("Missing required fields for text analysis")

                # Call text analysis service
                analysis_result = await self.ai_service.analyze_slide_requirements(
                    title=task.title,  # type: ignore
                    target_goal=task.target_goal,  # type: ignore
                    slide_type=task.slide_type,  # type: ignore
                    num_slides_range=task.num_slides_range,  # type: ignore
                    language=task.language,  # type: ignore
                    user_query=task.user_query,  # type: ignore
                )

            processing_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            # Convert slides to SlideOutlineItem format
            from src.models.slide_ai_generation_models import SlideOutlineItem

            slides_outline = []
            for slide_data in analysis_result["slides"]:
                slides_outline.append(
                    {
                        "slide_number": slide_data["slide_number"],
                        "title": slide_data["title"],
                        "content_points": slide_data.get("content_points", []),
                        "suggested_visuals": slide_data.get("suggested_visuals", []),
                        "image_suggestion": slide_data.get("image_suggestion"),
                        "estimated_duration": slide_data.get("estimated_duration"),
                        "image_url": None,  # User will add later
                    }
                )

            # Save completed analysis to MongoDB
            await asyncio.to_thread(
                self.mongo.db["slide_analyses"].update_one,
                {"_id": ObjectId(analysis_id)},
                {
                    "$set": {
                        "presentation_summary": analysis_result.get(
                            "presentation_summary", ""
                        ),
                        "num_slides": analysis_result["num_slides"],
                        "slides_outline": slides_outline,
                        "status": "completed",
                        "processing_time_ms": processing_time,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            logger.info(
                f"✅ Analysis completed: {len(slides_outline)} slides in {processing_time}ms"
            )

            # Deduct points after success
            points_service = get_points_service()
            await points_service.deduct_points(
                user_id=task.user_id,
                amount=2,
                service="slide_ai_analysis_pdf" if is_pdf else "slide_ai_analysis",
                resource_id=analysis_id,
                description=f"Slide AI Analysis: {task.title}",
            )

            logger.info(f"💰 Deducted 2 points from user {task.user_id}")

            # Update Redis status to completed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=analysis_id,
                status="completed",
                user_id=task.user_id,
                progress_percent=100,
                total_slides=len(slides_outline),
                title=task.title or "Untitled Analysis",
            )

            return True

        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}", exc_info=True)

            # Update MongoDB status to failed
            try:
                await asyncio.to_thread(
                    self.mongo.db["slide_analyses"].update_one,
                    {"_id": ObjectId(analysis_id)},
                    {
                        "$set": {
                            "status": "failed",
                            "error_message": str(e),
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
            except Exception as db_error:
                logger.error(f"❌ Failed to update MongoDB: {db_error}")

            # Update Redis status to failed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=analysis_id,
                status="failed",
                user_id=task.user_id,
                error=str(e),
            )

            return False

    async def process_html_generation_task(self, task: SlideGenerationTask) -> bool:
        """
        Process Step 2: HTML slide generation

        Args:
            task: SlideGenerationTask with step=2

        Returns:
            bool: True if successful
        """
        document_id = task.document_id
        start_time = datetime.utcnow()

        try:
            logger.info(f"🎨 Processing slide generation for document {document_id}")

            # Get document and analysis (use asyncio.to_thread for sync MongoDB calls)
            doc = await asyncio.to_thread(
                self.mongo.db["documents"].find_one, {"document_id": document_id}
            )
            if not doc:
                raise Exception(f"Document {document_id} not found")

            analysis = await asyncio.to_thread(
                self.mongo.db["slide_analyses"].find_one,
                {"_id": ObjectId(task.analysis_id), "user_id": task.user_id},
            )
            if not analysis:
                raise Exception(f"Analysis {task.analysis_id} not found")

            # ✅ Check if this is first AI generation or regeneration
            # IMPORTANT: Only AI-generated slides have version tracking (they have slides_outline)
            # Manual slides don't have outline → no version tracking

            # First AI generation = version 1 (no snapshot needed)
            # Regeneration = new version (snapshot old version first)
            current_version = doc.get("version", 1)
            existing_outline = doc.get("slides_outline", [])

            # Check if document already has AI-generated slides
            # Detect by: has slides_outline (AI slides always have outline)
            has_ai_generated_slides = len(existing_outline) > 0

            if has_ai_generated_slides:
                # This is regeneration (2nd+ AI generation) - create new version
                try:
                    new_version = await asyncio.to_thread(
                        self.doc_manager.save_version_snapshot,
                        document_id=document_id,
                        user_id=task.user_id,
                        description=f"Before AI slide regeneration (v{current_version} → v{current_version + 1})",
                    )
                    logger.info(
                        f"📸 Regeneration: Saved version {current_version} snapshot, creating version {new_version}"
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️ Failed to save version snapshot: {e}. Continuing with generation..."
                    )
            else:
                # This is first AI generation - stay at version 1
                logger.info(
                    f"🆕 First AI generation: Staying at version {current_version} (no snapshot needed)"
                )

            # Get generation data from document
            gen_data = doc.get("slide_generation_data", {})
            logo_url = gen_data.get("logo_url")
            slide_images = gen_data.get("slide_images", {})
            user_query = gen_data.get("user_query")
            points_needed = gen_data.get("points_needed", 2)

            # Update Redis status to processing (MongoDB no longer tracks status)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=document_id,
                status="processing",
                user_id=task.user_id,
                document_id=document_id,
                started_at=start_time.isoformat(),
                total_slides=len(analysis["slides_outline"]),
                title=analysis.get("title", "Untitled Presentation"),
            )

            # Get slides from analysis
            slides_outline = analysis["slides_outline"]
            num_slides = len(slides_outline)
            BATCH_SIZE = 10  # Reduced from 15 to 10 to avoid Claude token limits
            total_batches = (num_slides + BATCH_SIZE - 1) // BATCH_SIZE

            logger.info(
                f"📊 Generating {num_slides} slides in {total_batches} batch(es) ({BATCH_SIZE} slides/batch)"
            )

            # Generate HTML in batches
            all_slides_html = []
            generation_error = None  # Track if any batch fails
            first_slide_sample = None  # Save first slide for style consistency

            for i in range(total_batches):
                start_idx = i * BATCH_SIZE
                end_idx = min((i + 1) * BATCH_SIZE, num_slides)
                batch_slides = slides_outline[start_idx:end_idx]

                logger.info(
                    f"🔄 Batch {i+1}/{total_batches}: slides {start_idx+1}-{end_idx}"
                )

                try:
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
                        first_slide_sample=first_slide_sample,  # Pass style reference from batch 1
                    )

                    all_slides_html.extend(batch_html)

                    # Save first content slide (slide 1, not title slide 0) for style reference
                    if i == 0 and len(batch_html) >= 2:
                        first_slide_sample = batch_html[
                            1
                        ]  # Use slide 1 (Table of Contents)
                        logger.info(
                            "📌 Saved slide 1 as style reference for subsequent batches"
                        )

                    # Update Redis progress (MongoDB no longer tracks progress)
                    progress = int((i + 1) / total_batches * 100)
                    await set_job_status(
                        redis_client=self.queue_manager.redis_client,
                        job_id=document_id,
                        status="processing",
                        user_id=task.user_id,
                        progress_percent=progress,
                        batches_completed=i + 1,
                        total_batches=total_batches,
                        title=analysis.get("title", "Untitled Presentation"),
                    )

                    logger.info(
                        f"✅ Batch {i+1}/{total_batches} completed ({progress}%)"
                    )

                    # Small delay between batches
                    if i < total_batches - 1:
                        await asyncio.sleep(0.5)

                except Exception as batch_error:
                    logger.error(
                        f"❌ Batch {i+1}/{total_batches} failed: {batch_error}. "
                        f"Saving {len(all_slides_html)} partial slides..."
                    )
                    generation_error = batch_error
                    break  # Stop processing remaining batches

            # Check if generation completed successfully
            if generation_error:
                # Save partial slides with outline for retry
                if all_slides_html:
                    partial_html = "\n\n".join(all_slides_html)
                    slide_backgrounds = self._create_default_backgrounds(
                        len(all_slides_html), analysis["slide_type"]
                    )

                    logger.warning(
                        f"⚠️ Saving {len(all_slides_html)}/{num_slides} partial slides to database"
                    )

                    # Use asyncio.to_thread for blocking MongoDB update
                    await asyncio.to_thread(
                        self.doc_manager.update_document,
                        document_id=document_id,
                        user_id=task.user_id,
                        title=analysis["title"],
                        content_html=partial_html,
                        content_text=analysis.get("presentation_summary", ""),
                        slide_backgrounds=slide_backgrounds,
                        slides_outline=slides_outline,  # Save full outline for retry
                    )

                # Update Redis status to failed with retry info
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=document_id,
                    status="failed",
                    user_id=task.user_id,
                    document_id=document_id,
                    error=f"Generated {len(all_slides_html)}/{num_slides} slides. {str(generation_error)}",
                    completed_at=datetime.utcnow().isoformat(),
                    title=analysis.get("title", "Untitled Presentation"),
                    slides_generated=len(all_slides_html),
                    slides_expected=num_slides,
                    can_retry=True,  # Flag for frontend to show retry button
                )

                logger.error(
                    f"❌ Generation incomplete: {len(all_slides_html)}/{num_slides} slides saved. "
                    f"User can retry with saved outline."
                )
                return False

            # Combine all slides into final HTML
            final_html = "\n\n".join(all_slides_html)
            actual_slides_count = len(all_slides_html)

            # Create default backgrounds (use actual count, not expected)
            slide_backgrounds = self._create_default_backgrounds(
                actual_slides_count, analysis["slide_type"]
            )

            # Complete = All batches ran successfully (no errors), regardless of slide count
            # Partial = Had errors during batch processing (some batches didn't complete)
            is_complete = generation_error is None

            if actual_slides_count != num_slides:
                if actual_slides_count < num_slides:
                    logger.warning(
                        f"⚠️ Generated {actual_slides_count}/{num_slides} slides (missing {num_slides - actual_slides_count})"
                    )
                else:
                    logger.info(
                        f"✨ Generated {actual_slides_count}/{num_slides} slides (bonus: +{actual_slides_count - num_slides})"
                    )

            logger.info(
                f"✅ All batches completed: {actual_slides_count} slides generated "
                f"({'complete' if is_complete else 'partial'})"
            )

            # Save HTML to document (use asyncio.to_thread for blocking MongoDB update)
            await asyncio.to_thread(
                self.doc_manager.update_document,
                document_id=document_id,
                user_id=task.user_id,
                title=analysis["title"],
                content_html=final_html,
                content_text=analysis.get("presentation_summary", ""),
                slide_backgrounds=slide_backgrounds,
                slides_outline=slides_outline,  # Save outline for retry capability
            )

            # ✅ Add/Update version in version_history
            current_doc = await asyncio.to_thread(
                self.mongo.db["documents"].find_one, {"document_id": document_id}
            )
            if not current_doc:
                raise Exception(f"Document {document_id} not found after save")

            current_version = current_doc.get("version", 1)
            version_history = current_doc.get("version_history", [])

            # Check if current version exists in history
            version_exists = any(
                v.get("version") == current_version for v in version_history
            )

            if version_exists:
                # Update existing version in history (regeneration)
                await asyncio.to_thread(
                    self.mongo.db["documents"].update_one,
                    {
                        "document_id": document_id,
                        "user_id": task.user_id,
                        "version_history.version": current_version,
                    },
                    {
                        "$set": {
                            "version_history.$.content_html": final_html,
                            "version_history.$.slides_outline": slides_outline,
                            "version_history.$.slide_backgrounds": slide_backgrounds,
                            "version_history.$.slide_count": len(slides_outline),
                        }
                    },
                )
                logger.info(
                    f"📸 Updated version {current_version} in history with generated slides"
                )
            else:
                # First generation - add version 1 to history
                version_snapshot = {
                    "version": current_version,
                    "created_at": datetime.utcnow(),
                    "description": f"AI generated slides (first generation)",
                    "content_html": final_html,
                    "slides_outline": slides_outline,
                    "slide_backgrounds": slide_backgrounds,
                    "slide_elements": [],
                    "slide_count": len(slides_outline),
                }

                await asyncio.to_thread(
                    self.mongo.db["documents"].update_one,
                    {
                        "document_id": document_id,
                        "user_id": task.user_id,
                    },
                    {"$push": {"version_history": version_snapshot}},
                )
                logger.info(
                    f"📸 Created version {current_version} in history (first generation)"
                )

            # Deduct points (only if all batches completed successfully)
            if is_complete:
                points_service = get_points_service()
                await points_service.deduct_points(
                    user_id=task.user_id,
                    amount=points_needed,
                    service="slide_ai_generation",
                    resource_id=document_id,
                    description=f"AI Slide Generation: {actual_slides_count} slides ({total_batches} batches × 5 points)",
                )
                logger.info(
                    f"💰 Deducted {points_needed} points ({total_batches} batches × 5 points/batch)"
                )
            else:
                logger.info(
                    f"💰 No points deducted (partial: had errors during batch processing)"
                )

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            # Update Redis status (completed or partial)
            status = "completed" if is_complete else "partial"
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=document_id,
                status=status,
                user_id=task.user_id,
                document_id=document_id,
                completed_at=end_time.isoformat(),
                processing_time_seconds=processing_time,
                slides_generated=actual_slides_count,
                slides_expected=num_slides,
                batches_processed=total_batches,
                title=analysis.get("title", "Untitled Presentation"),
                can_retry=not is_complete,  # Show retry button if had errors
            )

            if is_complete:
                logger.info(
                    f"✅ Slide generation COMPLETED: {document_id} in {processing_time:.1f}s, "
                    f"{actual_slides_count} slides, {points_needed} points deducted"
                )
            else:
                logger.warning(
                    f"⚠️ Slide generation PARTIAL: {document_id} in {processing_time:.1f}s, "
                    f"{actual_slides_count}/{num_slides} slides, NO points deducted"
                )

            return True

        except Exception as e:
            logger.error(
                f"❌ Slide generation failed: {document_id}, error: {e}", exc_info=True
            )

            # Update Redis status to failed (MongoDB no longer tracks status)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=document_id,
                status="failed",
                user_id=task.user_id,
                document_id=document_id,
                error=str(e),
                completed_at=datetime.utcnow().isoformat(),
                title=(
                    analysis.get("title", "Untitled Presentation")
                    if analysis
                    else "Untitled Presentation"
                ),
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
        """Main worker loop with concurrency support"""
        await self.initialize()
        self.running = True

        logger.info(
            f"🚀 Worker {self.worker_id}: Started processing slide generation tasks"
        )
        logger.info(f"   🔄 Max concurrent jobs: {self.max_concurrent_jobs}")

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

                    # Parse task
                    try:
                        task = SlideGenerationTask(**task_data)
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
                            if success:
                                logger.info(f"✅ Task completed successfully")
                            else:
                                logger.error(f"❌ Task failed")
                        except Exception as e:
                            logger.error(f"❌ Task raised exception: {e}", exc_info=True)
                else:
                    await asyncio.sleep(1)

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
