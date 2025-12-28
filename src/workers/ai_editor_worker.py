"""
AI Editor Worker for processing AI edit/format jobs from Redis queue.
Pulls tasks from ai_editor queue and processes them using Claude/Gemini.
"""

import os
import sys
import asyncio
import logging
import signal
import time
import traceback
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Load environment variables
env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
env_file = "development.env" if env_var == "development" else ".env"
load_dotenv(env_file)

from src.queue.queue_manager import QueueManager, set_job_status, update_job_field
from src.models.ai_queue_tasks import AIEditorTask
from src.services.claude_service import ClaudeService
from src.utils.logger import setup_logger

logger = setup_logger()


class AIEditorWorker:
    """Worker that processes AI editor tasks from Redis queue"""

    def __init__(
        self,
        worker_id: str = None,
        redis_url: str = None,
        batch_size: int = 1,
        max_retries: int = 3,
    ):
        self.worker_id = (
            worker_id or f"ai_editor_worker_{int(time.time())}_{os.getpid()}"
        )
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://redis-server:6379"
        )
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="ai_editor"
        )
        self.claude = ClaudeService()

        logger.info(f"🔧 AI Editor Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")
        logger.info(f"   📦 Batch size: {self.batch_size}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            await self.queue_manager.connect()
            logger.info(
                f"✅ Worker {self.worker_id}: Connected to Redis ai_editor queue"
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

    async def process_task(self, task: AIEditorTask) -> bool:
        """
        Process a single AI editor task

        Args:
            task: AIEditorTask from Redis queue

        Returns:
            bool: True if processing successful
        """
        job_id = task.job_id
        start_time = datetime.utcnow()

        try:
            logger.info(
                f"⚙️ Processing AI editor job {job_id} (type={task.job_type}, size={len(task.content):,} chars)"
            )

            # Update job status to "processing" in Redis
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=task.user_id,
                job_type=task.job_type,
                document_id=task.document_id,
                started_at=start_time.isoformat(),
                content_size=len(task.content),
                estimated_tokens=len(task.content) // 4,
            )

            # Process based on job type and content type
            result = await self._process_content(task)

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            # Update status to completed in Redis
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=task.user_id,
                job_type=task.job_type,
                document_id=task.document_id,
                result=result,
                completed_at=end_time.isoformat(),
                processing_time_seconds=processing_time,
            )

            logger.info(
                f"✅ Job {job_id} completed in {processing_time:.1f}s "
                f"(output: {len(result):,} chars)"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)

            # Update status to failed in Redis
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=task.user_id,
                job_type=task.job_type,
                document_id=task.document_id,
                error=str(e),
                completed_at=datetime.utcnow().isoformat(),
            )

            return False

    async def _process_content(self, task: AIEditorTask) -> str:
        """
        Process content using appropriate AI service

        Args:
            task: AIEditorTask with content and metadata

        Returns:
            str: Processed HTML content
        """
        if task.job_type == "format":
            # Format content
            if task.content_type == "slide":
                # Use Claude for slides (5-min timeout, chunking support)
                logger.info(
                    f"📊 Formatting SLIDE with Claude Sonnet (job={task.job_id})"
                )
                result = await self.claude.format_slide_html(
                    html_content=task.content,
                    user_query=task.user_query,
                )
            else:
                # Use Gemini for documents/chapters
                logger.info(
                    f"📄 Formatting DOCUMENT with Gemini 2.5 Flash (job={task.job_id})"
                )
                from src.providers.gemini_provider import gemini_provider

                if not gemini_provider.enabled:
                    raise Exception("Gemini service is not available")

                result = await gemini_provider.format_document_html(
                    html_content=task.content,
                    user_query=task.user_query,
                )

        elif task.job_type == "edit":
            # Edit content based on content type
            if task.content_type == "slide":
                # Use Claude for slides
                logger.info(f"✏️ Editing SLIDE with Claude (job={task.job_id})")
                result = await self.claude.edit_html(
                    html_content=task.content,
                    user_instruction=task.user_query,
                    document_type="slide",
                )
            else:
                # Use Gemini for documents/chapters
                logger.info(f"✏️ Editing DOCUMENT with Gemini (job={task.job_id})")
                from src.providers.gemini_provider import gemini_provider

                if not gemini_provider.enabled:
                    raise Exception("Gemini service is not available")

                result = await gemini_provider.edit_document_html(
                    html_content=task.content,
                    user_instruction=task.user_query,
                )

        elif task.job_type == "bilingual":
            # Convert to bilingual format
            logger.info(
                f"🌐 Converting to bilingual {task.source_language}->{task.target_language} "
                f"with Gemini (job={task.job_id})"
            )
            from src.services.ai_chat_service import ai_chat_service, AIProvider

            # Build style-specific examples
            if task.bilingual_style == "slash_separated":
                style_description = "'Original / Translated' for slash_separated"
                example_input = "<td>Item 1</td>"
                example_output = "<td>Item 1 / Mục 1</td>"
            else:  # line_break
                style_description = (
                    "place translation on a new line with <br> for line_break"
                )
                example_input = "<p>This is a paragraph.</p>"
                example_output = "<p>This is a paragraph.<br>Đây là một đoạn văn.</p>"

            prompt = f"""You are an expert document translator specializing in creating bilingual documents. Your task is to convert the provided HTML document into a bilingual version, combining the source and target languages while preserving the original HTML structure.

- Source Language: '{task.source_language}'
- Target Language: '{task.target_language}'
- Bilingual Format Style: '{task.bilingual_style}' (e.g., {style_description}).

**CRITICAL RULES:**
1.  **ONLY return the modified bilingual HTML content.**
2.  **DO NOT translate HTML tags, attributes, or CSS styles.**
3.  **Preserve the original HTML structure meticulously (e.g., <h1>, <p>, <li>, <table>, <span>).**
4.  For every piece of text inside a tag, provide both the original and the translation according to the specified style.

**Example:**
- Input: `{example_input}`
- Output: `{example_output}`

Now, convert the following HTML document:
{task.content}"""

            messages = [
                {
                    "role": "system",
                    "content": "You are an expert bilingual document converter. You only return clean bilingual HTML without any markdown or explanations.",
                },
                {"role": "user", "content": prompt},
            ]

            result = await ai_chat_service.chat(
                provider=AIProvider.GEMINI_PRO,
                messages=messages,
                temperature=0.3,
                max_tokens=16000,
            )

        else:
            raise ValueError(f"Unknown job type: {task.job_type}")

        return result

    async def run(self):
        """Main worker loop"""
        await self.initialize()
        self.running = True

        logger.info(f"🚀 Worker {self.worker_id}: Started processing tasks")

        while self.running:
            try:
                # Fetch task from Redis queue (blocking with timeout)
                task_data = await self.queue_manager.dequeue_generic_task(
                    worker_id=self.worker_id, timeout=5
                )

                if not task_data:
                    # No task available, continue loop
                    continue

                # Parse task
                try:
                    task = AIEditorTask(**task_data)
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
    """Main entry point for AI Editor Worker"""
    worker = AIEditorWorker()

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

        logger.info("✅ AI Editor Worker shutdown complete")

    except Exception as e:
        logger.error(f"❌ AI Editor Worker fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
