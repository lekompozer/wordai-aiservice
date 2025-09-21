"""
Storage Processing Worker - Worker 2 in 2-Worker Architecture
Handles ONLY Qdrant storage and backend callbacks using enhanced_callback_handler.py

Flow: Redis Queue -> StorageProcessingWorker -> enhanced_callback_handler.py -> Backend Callback
"""

import asyncio
import os
import time
import traceback
from typing import Optional

from src.utils.logger import setup_logger
from src.queue.queue_dependencies import (
    get_storage_queue,
)  # ✅ Use separate storage queue
from src.queue.task_models import StorageProcessingTask

logger = setup_logger(__name__)


class StorageProcessingWorker:
    """
    Worker 2: Storage Processing Worker - ONLY handles Qdrant storage and callbacks.
    Uses enhanced_callback_handler.py for actual storage logic.

    Responsibilities:
    - Poll Redis queue for StorageProcessingTask
    - Call enhanced_callback_handler.store_structured_data_and_callback()
    - Log results
    """

    def __init__(
        self,
        worker_id: str = None,
        redis_url: str = None,
        poll_interval: float = 1.0,
        max_retries: int = 3,
    ):
        self.worker_id = worker_id or f"storage_worker_{int(time.time())}_{os.getpid()}"
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.running = False
        self.queue_manager = None

        logger.info(f"🔧 Storage Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")
        logger.info(f"   ⏱️ Poll interval: {self.poll_interval}s")
        logger.info(f"   🔄 Max retries: {self.max_retries}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            # ✅ Get storage queue manager (separate from extraction queue!)
            self.queue_manager = await get_storage_queue()
            logger.info(
                f"✅ Storage Worker {self.worker_id}: Connected to storage queue (storage_processing)"
            )

        except Exception as e:
            logger.error(
                f"❌ Storage Worker {self.worker_id}: Initialization failed: {e}"
            )
            raise

    async def shutdown(self):
        """Gracefully shutdown worker"""
        logger.info(f"🛑 Storage Worker {self.worker_id}: Shutting down...")
        self.running = False
        logger.info(f"✅ Storage Worker {self.worker_id}: Shutdown complete")

    async def run(self):
        """Main worker loop - continuously poll for StorageProcessingTask from Redis queue"""
        logger.info(f"🚀 Starting storage processing worker {self.worker_id}")
        self.running = True

        while self.running:
            try:
                # Dequeue storage tasks from Redis
                task_data = await self.queue_manager.dequeue_generic_task(
                    worker_id=self.worker_id, timeout=2  # 2 second timeout for polling
                )

                if task_data:
                    logger.info(
                        f"💾 [STORAGE WORKER] Processing storage task: {task_data.get('task_id')}"
                    )

                    try:
                        # This worker ONLY processes StorageProcessingTask
                        # We can identify it by the presence of 'original_extraction_task_id'
                        if "original_extraction_task_id" in task_data:
                            # Parse as StorageProcessingTask
                            task = StorageProcessingTask(**task_data)
                            await self.process_storage_task(task)
                        else:
                            # This is not our task type, skip it
                            logger.info(
                                f"🔄 [STORAGE WORKER] Task {task_data.get('task_id')} is not a StorageProcessingTask, skipping"
                            )

                    except Exception as task_error:
                        logger.error(
                            f"❌ [STORAGE WORKER] Task processing error: {task_error}"
                        )
                        logger.error(f"🔍 [STORAGE WORKER] Task data: {task_data}")

                else:
                    # No tasks, wait briefly before next poll
                    await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"❌ [STORAGE WORKER] Worker loop error: {e}")
                logger.error(f"🔍 [STORAGE WORKER] Traceback: {traceback.format_exc()}")
                await asyncio.sleep(self.poll_interval)

        logger.info(f"🛑 Storage processing worker {self.worker_id} stopped")

    async def process_storage_task(self, task: StorageProcessingTask) -> bool:
        """
        Process a single StorageProcessingTask.

        Worker 2 responsibilities:
        1. Receive structured_data from Worker 1 (ExtractionWorker)
        2. Call enhanced_callback_handler.store_structured_data_and_callback()
        3. Handler will: generate embeddings, store to Qdrant, send callback to backend

        Args:
            task: StorageProcessingTask instance

        Returns:
            bool: True if successful, False otherwise
        """
        start_time = time.time()

        try:
            logger.info(f"💾 [STORAGE WORKER] Processing storage task {task.task_id}")
            logger.info(f"   🏢 Company: {task.company_id}")
            logger.info(
                f"   📋 Original extraction task: {task.original_extraction_task_id}"
            )
            logger.info(
                f"   📊 Structured data keys: {list(task.structured_data.keys())}"
            )
            logger.info(f"   📞 Callback URL: {task.callback_url}")

            # Import storage function from enhanced_callback_handler
            from src.api.callbacks.enhanced_callback_handler import (
                store_structured_data_and_callback,
            )

            # Call storage handler - this does all the work:
            # 1. Generate embeddings for each product/service
            # 2. Store individual points to Qdrant with metadata
            # 3. Send enhanced callback to backend with qdrant_point_id for each item
            logger.info(
                f"💾 [STORAGE WORKER] Calling enhanced_callback_handler.store_structured_data_and_callback()"
            )
            logger.info(
                f"   📋 Using original extraction task ID: {task.original_extraction_task_id}"
            )
            logger.info(f"   🆔 Storage task ID: {task.task_id}")

            success = await store_structured_data_and_callback(
                task_id=task.original_extraction_task_id,  # ✅ Use original task ID for backend lookup
                structured_data=task.structured_data,
                company_id=task.company_id,
                callback_url=task.callback_url,
                metadata=task.metadata,
            )

            processing_time = time.time() - start_time

            if success:
                logger.info(
                    f"✅ [STORAGE WORKER] Storage task {task.task_id} completed successfully"
                )
                logger.info(f"   ⏱️ Processing time: {processing_time:.2f}s")
                logger.info(
                    f"   📋 Original task ID sent in callback: {task.original_extraction_task_id}"
                )
                logger.info(
                    f"   📈 Enhanced callback sent to backend with qdrant_point_id data"
                )
                return True
            else:
                logger.error(f"❌ [STORAGE WORKER] Storage task {task.task_id} failed")
                logger.error(f"   ⏱️ Processing time: {processing_time:.2f}s")
                return False

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"❌ [STORAGE WORKER] Storage task {task.task_id} failed: {str(e)}"
            )
            logger.error(f"   ⏱️ Processing time: {processing_time:.2f}s")
            logger.error(f"🔍 [STORAGE WORKER] Error details: {traceback.format_exc()}")
            return False


# =============================================================================
# STANDALONE RUNNER FOR STORAGE WORKER
# =============================================================================


async def run_storage_worker():
    """Standalone function to run storage processing worker"""
    worker = StorageProcessingWorker()

    try:
        await worker.initialize()
        await worker.run()
    except KeyboardInterrupt:
        logger.info("🛑 Storage worker interrupted by user")
    except Exception as e:
        logger.error(f"❌ Storage worker crashed: {e}")
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    """Run storage worker as standalone process"""
    asyncio.run(run_storage_worker())
