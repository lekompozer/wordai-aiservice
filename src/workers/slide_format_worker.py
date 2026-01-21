"""
Slide Format Worker
Processes slide AI formatting tasks from Redis queue
"""

import asyncio
import json
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
from src.services.document_manager import DocumentManager
from src.services.online_test_utils import get_mongodb_service

logger = logging.getLogger("chatbot")


class SlideFormatWorker:
    """Worker for processing slide AI format tasks"""

    def __init__(
        self,
        worker_id: str = "slide_format_worker",
        redis_url: str = "redis://redis-server:6379",
        batch_size: int = 1,
        max_concurrent_jobs: int = 5,
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.batch_size = batch_size
        self.max_concurrent_jobs = max_concurrent_jobs
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

            # Cleanup stuck tasks from previous crashes
            await self._cleanup_stuck_tasks()
        except Exception as e:
            logger.error(f"❌ Worker {self.worker_id}: Initialization failed: {e}")
            raise

    async def _cleanup_stuck_tasks(self):
        """Reset tasks stuck in 'processing' status > 10 minutes (from previous worker crashes)"""
        try:
            logger.info(f"🔍 Checking for stuck tasks...")

            # Get all job keys
            all_keys = await self.queue_manager.redis_client.keys("job:*")  # type: ignore
            stuck_count = 0

            for key in all_keys:  # type: ignore
                if isinstance(key, bytes):
                    key = key.decode()

                # Skip chunk tasks, only check parent jobs and single jobs
                if "_chunk_" in key:
                    continue

                job_id = key.replace("job:", "")
                job = await get_job_status(self.queue_manager.redis_client, job_id)

                if job and job.get("status") == "processing":
                    started_at_str = job.get("started_at")
                    if started_at_str:
                        try:
                            started_at = datetime.fromisoformat(started_at_str)
                            elapsed_seconds = (
                                datetime.utcnow() - started_at
                            ).total_seconds()

                            # Reset if stuck > 10 minutes
                            if elapsed_seconds > 600:
                                logger.warning(
                                    f"🔄 Resetting stuck job {job_id} (stuck for {elapsed_seconds:.0f}s)"
                                )

                                await set_job_status(
                                    redis_client=self.queue_manager.redis_client,
                                    job_id=job_id,
                                    status="failed",
                                    user_id=job.get("user_id", ""),
                                    error="Worker crashed or timeout - task auto-reset on worker restart",
                                    completed_at=datetime.utcnow().isoformat(),
                                )
                                stuck_count += 1
                        except Exception as e:
                            logger.error(f"Error parsing started_at for {job_id}: {e}")

            if stuck_count > 0:
                logger.info(f"✅ Reset {stuck_count} stuck task(s)")
            else:
                logger.info(f"✅ No stuck tasks found")

        except Exception as e:
            logger.error(f"❌ Failed to cleanup stuck tasks: {e}", exc_info=True)
            # Don't fail initialization if cleanup fails

    async def shutdown(self):
        """Gracefully shutdown worker"""
        logger.info(f"🛑 Worker {self.worker_id}: Shutting down...")
        self.running = False

        if self.queue_manager:
            await self.queue_manager.disconnect()
            logger.info(f"✅ Worker {self.worker_id}: Queue disconnected")

    async def process_task(self, task: SlideFormatTask) -> bool:
        """
        Process slide format task with timeout protection

        Args:
            task: SlideFormatTask from Redis queue

        Returns:
            bool: True if processing successful
        """
        job_id = task.job_id
        start_time = datetime.utcnow()

        # ⏱️ TIMEOUT PROTECTION: Dynamic timeout based on slides count
        # Base 60s + 30s per slide (e.g., 12 slides = 420s = 7 minutes)
        total_slides = task.total_slides or 1
        timeout_seconds = 60 + (total_slides * 30)

        logger.info(f"⏱️ Task timeout: {timeout_seconds}s ({total_slides} slide(s))")

        try:
            return await asyncio.wait_for(
                self._process_task_internal(task), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(
                f"❌ Job {job_id} TIMEOUT after {timeout_seconds}s ({total_slides} slides) - auto-failing"
            )
            logger.error(
                f"   Task details: user={task.user_id}, doc={task.document_id}, batch={task.is_batch}"
            )

            # Mark as failed in Redis
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=task.user_id,
                error=f"Processing timeout after {timeout_seconds}s for {total_slides} slides",
                failed_at=datetime.utcnow().isoformat(),
            )
            return False
        except Exception as e:
            logger.error(
                f"❌ Job {job_id} failed: {e}\n"
                f"   Task: user={task.user_id}, doc={task.document_id}, "
                f"slides={task.total_slides}, batch={task.is_batch}",
                exc_info=True,
            )

            # Update status to failed
            if task.is_batch:
                # Mode 2 & 3: Fail entire batch job
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=task.batch_job_id or "",
                    status="failed",
                    user_id=task.user_id,
                    error=str(e),
                    completed_at=datetime.utcnow().isoformat(),
                    failed_slides=task.total_slides,
                )
            else:
                # Mode 1: Single slide
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=job_id,
                    status="failed",
                    user_id=task.user_id,
                    error=str(e),
                    failed_at=datetime.utcnow().isoformat(),
                )

            return False

    async def _process_task_internal(self, task: SlideFormatTask) -> bool:
        """Internal task processing (separated for timeout wrapper)"""
        job_id = task.job_id
        start_time = datetime.utcnow()

        try:
            logger.info(
                f"⚙️ Processing slide format job {job_id} (slide={task.slide_index}, type={task.format_type})"
            )

            if task.is_batch:
                if task.total_chunks and task.total_chunks > 1:
                    logger.info(
                        f"   📦 Chunk {(task.chunk_index or 0) + 1}/{task.total_chunks}: {task.total_slides} slides"
                    )

                    # Add delay between chunks to avoid Claude rate limits
                    # First chunk (index 0) processes immediately
                    # Subsequent chunks wait 90s * chunk_index to spread API calls
                    if task.chunk_index and task.chunk_index > 0:
                        delay_seconds = 90 * task.chunk_index
                        logger.info(
                            f"   ⏱️ Delaying chunk {task.chunk_index + 1} by {delay_seconds}s to avoid rate limits..."
                        )
                        await asyncio.sleep(delay_seconds)
                        logger.info(
                            f"   ✅ Delay complete, starting chunk {task.chunk_index + 1}"
                        )
                else:
                    logger.info(f"   📦 Batch processing: {task.total_slides} slides")
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
            result = await self.slide_ai_service.format_slide(request, task.user_id)  # type: ignore

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            # Handle result based on mode
            if task.is_batch:
                # Mode 2 & 3: Split combined HTML back to individual slides
                formatted_html = result["formatted_html"]

                # Parse slides with their markers to extract actual slide_index
                import re

                # Find all slide sections with their markers
                slide_pattern = r"<!-- Slide (\d+) -->\s*(.*?)(?=<!-- Slide \d+ --|$)"
                matches = re.findall(slide_pattern, formatted_html, re.DOTALL)

                # Prepare results for this chunk
                chunk_results = []

                if matches:
                    # Case 1: AI preserved slide markers (ideal)
                    for slide_index_str, html in matches:
                        slide_index = int(slide_index_str)
                        chunk_results.append(
                            {
                                "slide_index": slide_index,  # Use actual slide_index from marker
                                "formatted_html": html.strip(),
                                "suggested_elements": result.get(
                                    "suggested_elements", []
                                ),
                                "suggested_background": result.get(
                                    "suggested_background"
                                ),
                                "ai_explanation": result.get("ai_explanation", ""),
                                "error": None,
                            }
                        )
                else:
                    # Case 2: AI didn't preserve markers (fallback)
                    # Assume entire response is for the single slide being processed
                    logger.warning(
                        f"⚠️ No slide markers found in AI response, using entire HTML for slide {task.slide_index}"
                    )

                    # Debug: Log formatted_html length and first 200 chars
                    logger.info(
                        f"📝 Formatted HTML length: {len(formatted_html)} chars"
                    )
                    logger.info(
                        f"📝 HTML preview (first 200 chars): {formatted_html[:200]}"
                    )

                    # Check if HTML has unexpected data-slide-index attribute
                    if "data-slide-index=" in formatted_html:
                        import re

                        attr_match = re.search(
                            r'data-slide-index="([^"]*)"', formatted_html
                        )
                        if attr_match:
                            attr_value = attr_match.group(1)
                            logger.warning(
                                f"⚠️ Found data-slide-index attribute with value: {attr_value[:100]}"
                            )

                    chunk_results.append(
                        {
                            "slide_index": task.slide_index,  # Use task's slide index
                            "formatted_html": formatted_html.strip(),
                            "suggested_elements": result.get("suggested_elements", []),
                            "suggested_background": result.get("suggested_background"),
                            "ai_explanation": result.get("ai_explanation", ""),
                            "error": None,
                        }
                    )

                logger.info(
                    f"   📊 Extracted {len(chunk_results)} slides from AI response"
                )
                if chunk_results:
                    indices = [r["slide_index"] for r in chunk_results]
                    logger.info(f"   📌 Slide indices: {indices}")

                # Update batch job based on chunking mode
                if task.total_chunks and task.total_chunks > 1:
                    # Mode 3: Chunked batch - merge chunk results
                    await self._merge_chunk_results(
                        batch_job_id=task.batch_job_id or "",
                        chunk_index=task.chunk_index or 0,
                        total_chunks=task.total_chunks or 1,
                        chunk_results=chunk_results,
                        processing_time=processing_time,
                        document_id=task.document_id,
                        user_id=task.user_id,
                        process_entire_document=task.process_entire_document,
                    )
                    logger.info(
                        f"✅ Chunk {(task.chunk_index or 0) + 1}/{task.total_chunks} completed: {len(chunk_results)} slides in {processing_time:.1f}s"
                    )
                else:
                    # Mode 2: Non-chunked batch - update batch job directly for each slide
                    for slide_result in chunk_results:
                        await self._update_batch_job(
                            batch_job_id=task.batch_job_id or "",
                            slide_index=slide_result["slide_index"],
                            result=slide_result,
                            error=slide_result.get("error"),
                        )
                    logger.info(
                        f"✅ Batch job updated: {len(chunk_results)} slide(s) in {processing_time:.1f}s"
                    )
            else:
                # Mode 1: Single slide processing
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=job_id,
                    status="completed",
                    user_id=task.user_id,
                    slide_number=task.slide_index
                    + 1,  # Convert 0-indexed to 1-indexed for frontend
                    formatted_html=result["formatted_html"],
                    suggested_elements=result.get("suggested_elements", []),
                    suggested_background=result.get("suggested_background"),
                    ai_explanation=result.get("ai_explanation", ""),
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
                    job_id=task.batch_job_id or "",
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
        result: Optional[dict] = None,
        error: Optional[str] = None,
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
                user_id=batch_job.get("user_id") or "",
                **update_data,
            )

            logger.info(
                f"📦 Batch job {batch_job_id}: {completed_slides}/{total_slides} completed, {failed_slides} failed"
            )

        except Exception as e:
            logger.error(
                f"❌ Failed to update batch job {batch_job_id}: {e}", exc_info=True
            )

    async def _merge_chunk_results(
        self,
        batch_job_id: str,
        chunk_index: int,
        total_chunks: int,
        chunk_results: list,
        processing_time: float,
        document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        process_entire_document: bool = False,
    ):
        """Merge chunk results into batch job and mark complete when all chunks done"""
        try:
            # Get current batch job
            batch_job = await get_job_status(
                self.queue_manager.redis_client, batch_job_id
            )
            if not batch_job:
                logger.warning(f"⚠️ Batch job {batch_job_id} not found in Redis")
                return

            # Get or initialize chunk results storage
            chunk_results_key = f"chunks:{batch_job_id}"

            # Store this chunk's results
            await self.queue_manager.redis_client.hset(  # type: ignore
                chunk_results_key, str(chunk_index), json.dumps(chunk_results)
            )
            await self.queue_manager.redis_client.expire(chunk_results_key, 86400)  # type: ignore

            # Check if all chunks are complete
            all_chunks = await self.queue_manager.redis_client.hgetall(chunk_results_key)  # type: ignore
            chunks_completed = len(all_chunks)  # type: ignore

            logger.info(
                f"📦 Batch job {batch_job_id}: {chunks_completed}/{total_chunks} chunks completed"
            )

            if chunks_completed == total_chunks:
                # All chunks done - merge all results
                all_slides_results = []
                for idx in range(total_chunks):
                    chunk_data = all_chunks.get(  # type: ignore
                        str(idx).encode()
                        if isinstance(list(all_chunks.keys())[0], bytes)  # type: ignore
                        else str(idx)
                    )
                    if chunk_data:
                        if isinstance(chunk_data, bytes):
                            chunk_data = chunk_data.decode()
                        chunk_slides = json.loads(chunk_data)
                        all_slides_results.extend(chunk_slides)

                # Prepare update data
                slide_numbers = [
                    r.get("slide_index") + 1 for r in all_slides_results
                ]  # Convert 0-indexed to 1-indexed for frontend

                update_data = {
                    "status": "completed",
                    "user_id": batch_job.get("user_id") or "",
                    "slide_numbers": slide_numbers,  # Array of formatted slide numbers (1-based)
                    "completed_slides": len(all_slides_results),
                    "failed_slides": 0,
                    "slides_results": all_slides_results,
                    "completed_at": datetime.utcnow().isoformat(),
                    "processing_time_seconds": processing_time,
                }

                # Mode 3: Create new version in database (auto-save formatted slides)
                if process_entire_document:
                    # Use document_id/user_id from task (more reliable than Redis batch_job)

                    if document_id and user_id:
                        try:
                            logger.info(
                                f"📋 Mode 3: Creating new version for document {document_id}"
                            )

                            # Get DocumentManager
                            mongo = get_mongodb_service()
                            doc_manager = DocumentManager(mongo.db)

                            # Get current document and version before creating snapshot
                            doc = doc_manager.get_document(document_id, user_id)
                            if doc:
                                previous_version = doc.get("version", 1)

                                # STEP 1: Create version snapshot FIRST (saves current state as old version)
                                new_version = doc_manager.save_version_snapshot(
                                    document_id=document_id,
                                    user_id=user_id,
                                    description=f"Version {previous_version} (before AI formatting)",
                                )

                                logger.info(
                                    f"✅ Saved version snapshot: v{previous_version} → v{new_version}"
                                )

                                # STEP 2: Update current document with formatted slides
                                # Parse current content_html to extract individual slides
                                current_content_html = doc.get("content_html", "")

                                # Create mapping of slide_index -> formatted_html
                                formatted_map = {}
                                for slide_result in all_slides_results:
                                    slide_idx = slide_result.get("slide_index")
                                    formatted_html = slide_result.get("formatted_html")
                                    if slide_idx is not None and formatted_html:
                                        formatted_map[slide_idx] = formatted_html
                                        logger.info(
                                            f"   ✅ Formatted slide {slide_idx} ready ({len(formatted_html)} chars)"
                                        )

                                # Split content_html into individual slides
                                # Slides are separated by <!-- Slide N --> comments
                                import re

                                slide_pattern = (
                                    r"(<!-- Slide \d+ -->.*?(?=<!-- Slide \d+ -->|$))"
                                )
                                slides_html = re.findall(
                                    slide_pattern, current_content_html, re.DOTALL
                                )

                                # If no slide markers found, treat entire content as slides concatenated
                                if not slides_html:
                                    # Try to split by slide-page div
                                    slide_pattern = (
                                        r'(<div class="slide-page">.*?</div>\s*</div>)'
                                    )
                                    slides_html = re.findall(
                                        slide_pattern, current_content_html, re.DOTALL
                                    )

                                logger.info(
                                    f"📄 Extracted {len(slides_html)} slides from content_html"
                                )

                                # Replace formatted slides
                                updated_slides = []
                                for i, slide_html in enumerate(slides_html):
                                    if i in formatted_map:
                                        # Use formatted HTML
                                        updated_slides.append(formatted_map[i])
                                        logger.info(
                                            f"   🔄 Replaced slide {i} with formatted version"
                                        )
                                    else:
                                        # Keep original
                                        updated_slides.append(slide_html)

                                # Combine into new content_html
                                new_content_html = "\n\n".join(updated_slides)

                                # Save updated document with new content_html
                                doc_manager.update_document(
                                    document_id=document_id,
                                    user_id=user_id,
                                    content_html=new_content_html,
                                )

                                logger.info(
                                    f"✅ Updated document {document_id} with {len(formatted_map)} formatted slides"
                                )

                                update_data["new_version"] = new_version
                                update_data["previous_version"] = previous_version

                                logger.info(
                                    f"✅ Mode 3 complete: v{previous_version} (old) → v{new_version} (formatted)"
                                )
                            else:
                                logger.warning(
                                    f"⚠️ Document {document_id} not found, cannot create version"
                                )

                        except Exception as e:
                            logger.error(
                                f"❌ Failed to create version for document {document_id}: {e}",
                                exc_info=True,
                            )
                            # Don't fail the entire job if version creation fails
                            # User can still see formatted slides in job status
                    else:
                        logger.warning(
                            "⚠️ Mode 3 but missing document_id or user_id, cannot create version"
                        )

                # ✅ CRITICAL: Mode 2 - Update MongoDB slide_backgrounds array for frontend polling
                # Even without process_entire_document, we need to update individual slides in MongoDB
                else:
                    # Mode 2: Update individual slides in slide_backgrounds array
                    # Use document_id/user_id from task (more reliable than Redis batch_job)

                    if document_id and user_id:
                        try:
                            logger.info(
                                f"📋 Mode 2: Updating slide_backgrounds for document {document_id}"
                            )

                            # Get DocumentManager
                            mongo = get_mongodb_service()
                            doc_manager = DocumentManager(mongo.db)

                            # Get current document
                            doc = doc_manager.get_document(document_id, user_id)
                            if doc:
                                slide_backgrounds = doc.get("slide_backgrounds", [])

                                # Update slide_backgrounds with formatted HTML
                                for slide_result in all_slides_results:
                                    slide_idx = slide_result.get("slide_index")
                                    formatted_html = slide_result.get("formatted_html")

                                    if (
                                        slide_idx is not None
                                        and formatted_html
                                        and slide_idx < len(slide_backgrounds)
                                    ):
                                        # Update the slide's formatted_html field
                                        slide_backgrounds[slide_idx][
                                            "formatted_html"
                                        ] = formatted_html
                                        logger.info(
                                            f"   ✅ Updated slide {slide_idx} in slide_backgrounds"
                                        )

                                # Save updated slide_backgrounds to MongoDB
                                mongo.db.documents.update_one(
                                    {"document_id": document_id, "user_id": user_id},
                                    {"$set": {"slide_backgrounds": slide_backgrounds}},
                                )

                                logger.info(
                                    f"✅ Mode 2: Updated {len(all_slides_results)} slides in MongoDB"
                                )
                            else:
                                logger.warning(
                                    f"⚠️ Document {document_id} not found for Mode 2 update"
                                )

                        except Exception as e:
                            logger.error(
                                f"❌ Failed to update slide_backgrounds for document {document_id}: {e}",
                                exc_info=True,
                            )
                    else:
                        logger.warning(
                            "⚠️ Mode 2 but missing document_id or user_id, cannot update MongoDB"
                        )

                # Update batch job status to completed
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=batch_job_id,
                    **update_data,
                )

                # Cleanup chunk results
                await self.queue_manager.redis_client.delete(chunk_results_key)  # type: ignore

                logger.info(
                    f"✅ Batch job {batch_job_id} COMPLETED: All {total_chunks} chunks merged, {len(all_slides_results)} total slides"
                )
            else:
                # Update progress
                await set_job_status(
                    redis_client=self.queue_manager.redis_client,
                    job_id=batch_job_id,
                    status="processing",
                    user_id=batch_job.get("user_id") or "",
                    completed_slides=chunks_completed * 12,  # Approximate
                )

        except Exception as e:
            logger.error(
                f"❌ Failed to merge chunk results for batch job {batch_job_id}: {e}",
                exc_info=True,
            )

    async def run(self):
        """Main worker loop with concurrency support"""
        await self.initialize()
        self.running = True

        logger.info(f"🚀 Worker {self.worker_id}: Started processing tasks")
        logger.info(f"   🔄 Max concurrent jobs: {self.max_concurrent_jobs}")

        # Track running tasks
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
                        task = SlideFormatTask(**task_data)
                    except Exception as parse_error:
                        logger.error(f"❌ Failed to parse task: {parse_error}")
                        continue

                    # Start task in background
                    task_future = asyncio.create_task(self.process_task(task))
                    running_tasks.add(task_future)
                    logger.info(
                        f"📝 Started task {task.task_id} ({len(running_tasks)}/{self.max_concurrent_jobs} active)"
                    )

                # Wait for at least one task to complete
                if running_tasks:
                    done, running_tasks = await asyncio.wait(
                        running_tasks, return_when=asyncio.FIRST_COMPLETED
                    )

                    # Log completed tasks
                    for completed_task in done:
                        try:
                            success = await completed_task
                            if not success:
                                logger.warning(f"⚠️ A task processing failed")
                        except Exception as e:
                            logger.error(
                                f"❌ Task raised exception: {e}", exc_info=True
                            )
                else:
                    # No tasks running and no tasks in queue
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info(f"🛑 Worker {self.worker_id}: Cancelled")
                break
            except Exception as e:
                logger.error(
                    f"❌ Worker {self.worker_id}: Error in main loop: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(5)

        # Wait for remaining tasks to complete
        if running_tasks:
            logger.info(f"⏳ Waiting for {len(running_tasks)} tasks to complete...")
            await asyncio.gather(*running_tasks, return_exceptions=True)

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
