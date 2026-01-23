"""
Test Generation Worker - Handles all test generation tasks

This worker processes test generation jobs from Redis queue:
- Listening comprehension tests
- Grammar tests
- Vocabulary tests
- General tests

Uses Redis Worker Pattern with max 5 concurrent tasks.
"""

import asyncio
import json
import logging
from datetime import datetime

from src.queue.queue_manager import set_job_status
from src.services.listening_test_generator_service import ListeningTestGeneratorService
from src.database.db_manager import DBManager
from src.models.ai_queue_tasks import TestGenerationTask

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test-generation-worker")


class TestGenerationWorker:
    """Worker for processing test generation tasks"""

    def __init__(
        self,
        worker_id: str = "test_generation_worker",
        redis_url: str = "redis://redis-server:6379",
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.queue_manager = None
        self.db_manager = DBManager()
        self.db = self.db_manager.db
        self.running = False
        self.active_tasks = set()
        self.max_concurrent_tasks = 5

        logger.info(f"🔧 Test Generation Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")

    async def initialize(self):
        """Initialize queue manager"""
        from src.queue.queue_manager import QueueManager

        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="test_generation"
        )
        await self.queue_manager.connect()
        logger.info(f"✅ Test Generation Worker {self.worker_id} initialized")
        logger.info(f"   Max concurrent tasks: {self.max_concurrent_tasks}")

    async def process_listening_test(self, task_data: dict):
        """Process listening test generation task"""
        job_id = task_data.get("job_id", "unknown")
        user_id = task_data.get("creator_id", "unknown")
        test_id = task_data.get("test_id")  # Get test_id from task data

        try:
            logger.info(f"🎙️ Processing listening test job {job_id}")

            # Update status to processing
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                progress_percent=10,
                message="AI is generating questions...",
            )

            # Generate test
            generator = ListeningTestGeneratorService()
            result = await generator.generate_listening_test(
                title=task_data["title"],
                description=task_data.get("description"),
                language=task_data["language"],
                topic=task_data["topic"],
                difficulty=task_data["difficulty"],
                num_questions=task_data["num_questions"],
                num_audio_sections=task_data["num_audio_sections"],
                audio_config=task_data.get("audio_config", {}),
                user_query=task_data.get("user_query", ""),
                time_limit_minutes=task_data.get("time_limit_minutes", 60),
                passing_score=task_data.get("passing_score", 70),
                use_pro_model=task_data.get("use_pro_model", False),
                creator_id=user_id,
                user_transcript=task_data.get("user_transcript"),
                audio_file_path=task_data.get("audio_file_path"),
            )

            # Update status to completed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                progress_percent=100,
                message="Test generated successfully",
                test_id=test_id,  # Use test_id from task_data, not result
                completed_at=datetime.utcnow().isoformat(),
            )

            logger.info(f"✅ Listening test job {job_id} completed")
            return {"test_id": test_id}  # Return test_id for consistency

        except Exception as e:
            logger.error(f"❌ Listening test job {job_id} failed: {e}", exc_info=True)

            # Update status to failed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                progress_percent=0,
                message=f"Test generation failed: {str(e)}",
                error=str(e),
            )

            raise

    async def process_pdf_test(self, task_data: dict):
        """Process PDF/Document test generation task"""
        job_id = task_data.get("job_id", "unknown")
        user_id = task_data.get("creator_id", "unknown")
        test_id = task_data.get("test_id")

        try:
            logger.info(f"📄 Processing PDF test job {job_id}, test_id={test_id}")

            # Update status to processing
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                progress_percent=10,
                message="AI is analyzing document and generating questions...",
            )

            # Import and call existing generate_test_background function
            from src.services.online_test_utils import generate_test_background
            from src.services.document_manager import get_document_manager

            # Fetch document content if source_type is 'document'
            content = ""
            gemini_pdf_bytes = None
            source_type = task_data.get("source_type", "file")

            if source_type == "document":
                # Fetch document content from MongoDB
                doc_manager = get_document_manager()
                doc = doc_manager.get_document(task_data.get("source_id"))
                if not doc:
                    raise ValueError(f"Document {task_data.get('source_id')} not found")
                content = doc.get("content", "")
            elif source_type == "file":
                # For file type, we need to fetch from R2 (handled by generate_test_background)
                # Just pass the R2 key
                content = ""  # Will be fetched from R2 in generate_test_background

            # Call the existing generation function
            await generate_test_background(
                test_id=test_id,
                content=content,
                title=task_data["title"],
                user_query=task_data.get("user_query", ""),
                language=task_data["language"],
                difficulty=task_data["difficulty"],
                num_questions=task_data["num_questions"],
                creator_id=user_id,
                source_type=source_type,
                source_id=task_data.get("source_id"),
                time_limit_minutes=task_data.get("time_limit_minutes", 60),
                gemini_pdf_bytes=gemini_pdf_bytes,
                num_options=task_data.get("num_options", 4),
                num_correct_answers=task_data.get("num_correct_answers", 1),
                test_category=task_data.get("test_category", "academic"),
                test_type=task_data.get("test_type", "multiple_choice"),
                num_mcq_questions=task_data.get("num_mcq_questions", 0),
                num_essay_questions=task_data.get("num_essay_questions", 0),
                mcq_type_config=task_data.get("mcq_type_config"),
                topic=task_data.get("topic", task_data["title"]),
                is_general_knowledge=False,
            )

            # Update status to completed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                progress_percent=100,
                message="Test generated successfully",
                test_id=test_id,
                completed_at=datetime.utcnow().isoformat(),
            )

            logger.info(f"✅ PDF test job {job_id} completed")
            return {"test_id": test_id}

        except Exception as e:
            logger.error(f"❌ PDF test job {job_id} failed: {e}", exc_info=True)

            # Update status to failed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                progress_percent=0,
                message=f"Test generation failed: {str(e)}",
                error=str(e),
            )

            raise

    async def process_general_test(self, task_data: dict):
        """Process general knowledge test generation task"""
        job_id = task_data.get("job_id", "unknown")
        user_id = task_data.get("creator_id", "unknown")
        test_id = task_data.get("test_id")

        try:
            logger.info(f"🧠 Processing general test job {job_id}, test_id={test_id}")

            # Update status to processing
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                progress_percent=10,
                message="AI is generating questions from general knowledge...",
            )

            # Import and call existing generate_test_background function
            from src.services.online_test_utils import generate_test_background

            # Build content from topic and query
            topic = task_data.get("topic", "")
            user_query = task_data.get("user_query", "")
            test_category = task_data.get("test_category", "academic")

            content = f"""Topic: {topic}

Instructions: {user_query}

Generate a comprehensive {test_category} test based on general knowledge of this topic."""

            # Call the existing generation function
            await generate_test_background(
                test_id=test_id,
                content=content,
                title=task_data["title"],
                user_query=user_query,
                language=task_data["language"],
                difficulty=task_data["difficulty"],
                num_questions=task_data["num_questions"],
                creator_id=user_id,
                source_type="general_knowledge",
                source_id=topic,
                time_limit_minutes=task_data.get("time_limit_minutes", 60),
                gemini_pdf_bytes=None,
                num_options=task_data.get("num_options", 4),
                num_correct_answers=task_data.get("num_correct_answers", 1),
                test_category=test_category,
                test_type=task_data.get("test_type", "multiple_choice"),
                num_mcq_questions=task_data.get("num_mcq_questions", 0),
                num_essay_questions=task_data.get("num_essay_questions", 0),
                mcq_type_config=task_data.get("mcq_type_config"),
                topic=topic,
                is_general_knowledge=True,
            )

            # Update status to completed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                progress_percent=100,
                message="Test generated successfully",
                test_id=test_id,
                completed_at=datetime.utcnow().isoformat(),
            )

            logger.info(f"✅ General test job {job_id} completed")
            return {"test_id": test_id}

        except Exception as e:
            logger.error(f"❌ General test job {job_id} failed: {e}", exc_info=True)

            # Update status to failed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                progress_percent=0,
                message=f"Test generation failed: {str(e)}",
                error=str(e),
            )

            raise

    async def process_task(self, task_data: dict):
        """Process a test generation task based on type"""
        task_type = task_data.get("task_type", "listening")
        job_id = task_data.get("job_id")

        try:
            logger.info(f"📝 Processing {task_type} test job {job_id}")

            if task_type == "listening":
                return await self.process_listening_test(task_data)
            elif task_type == "pdf":
                return await self.process_pdf_test(task_data)
            elif task_type == "general":
                return await self.process_general_test(task_data)
            elif task_type == "grammar":
                # TODO: Implement grammar test generation
                logger.warning(f"⚠️ Grammar test not implemented yet")
                raise NotImplementedError("Grammar test generation not implemented")
            elif task_type == "vocabulary":
                # TODO: Implement vocabulary test generation
                logger.warning(f"⚠️ Vocabulary test not implemented yet")
                raise NotImplementedError("Vocabulary test generation not implemented")
                logger.warning(f"⚠️ General test not implemented yet")
                raise NotImplementedError("General test generation not implemented")
            else:
                raise ValueError(f"Unknown task type: {task_type}")

        except Exception as e:
            logger.error(f"❌ Task {job_id} failed: {e}")
            raise

    async def worker_loop(self):
        """Main worker loop - process tasks from queue"""
        logger.info("🚀 Starting test generation worker loop...")

        while self.running:
            try:
                # Check if we can process more tasks
                if len(self.active_tasks) >= self.max_concurrent_tasks:
                    await asyncio.sleep(1)
                    continue

                # Get next task from queue (returns dict with task JSON)
                task_data = await self.queue_manager.dequeue_generic_task(
                    worker_id=self.worker_id, timeout=1
                )

                if task_data is None:
                    # No tasks available, wait a bit
                    await asyncio.sleep(2)
                    continue

                # Parse task to TestGenerationTask model
                try:
                    task = TestGenerationTask(**task_data)
                    logger.info(f"📝 Dequeued {task.task_type} test task {task.job_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to parse task data: {e}")
                    logger.error(f"   Task data: {task_data}")
                    continue

                # Convert task to dict for process_task
                task_dict = task.model_dump()

                # Process task in background
                async_task = asyncio.create_task(self.process_task(task_dict))
                self.active_tasks.add(async_task)
                async_task.add_done_callback(self.active_tasks.discard)

                logger.info(
                    f"📋 Active tasks: {len(self.active_tasks)}/{self.max_concurrent_tasks}"
                )

            except Exception as e:
                logger.error(f"❌ Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def start(self):
        """Start the worker"""
        self.running = True
        await self.initialize()
        await self.worker_loop()

    async def stop(self):
        """Stop the worker gracefully"""
        logger.info("🛑 Stopping test generation worker...")
        self.running = False

        # Wait for active tasks to complete
        if self.active_tasks:
            logger.info(f"⏳ Waiting for {len(self.active_tasks)} active tasks...")
            await asyncio.gather(*self.active_tasks, return_exceptions=True)

        logger.info("✅ Test generation worker stopped")


async def main():
    """Main entry point for worker"""
    worker = TestGenerationWorker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("⚠️ Received shutdown signal")
        await worker.stop()
    except Exception as e:
        logger.error(f"❌ Worker crashed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
