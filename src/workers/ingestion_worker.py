"""
Ingestion Worker for processing document ingestion tasks from the Redis queue.
Downloads files from R2 storage and processes them through the ingestion pipeline.

This worker connects to Redis, pulls tasks from the queue, and processes them
using the existing AIDocumentProcessor.
"""

import os
import os
import sys
import asyncio
import logging
import signal
import time
import traceback
from typing import Optional
from dotenv import load_dotenv

# Add src to path to enable imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Load environment variables
env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
env_file = "development.env" if env_var == "development" else ".env"
load_dotenv(env_file)

from src.workers.document_processor import AIDocumentProcessor
from src.queue.queue_manager import QueueManager, IngestionTask, TaskStatus
from src.utils.logger import setup_logger

# ==============================================================================
# WORKER CONFIGURATION
# ==============================================================================

logger = setup_logger()


class DocumentIngestionWorker:
    """
    Worker that processes document ingestion tasks from Redis queue.
    """

    def __init__(
        self,
        worker_id: str = None,
        redis_url: str = None,
        batch_size: int = 1,
        max_retries: int = 3,
    ):
        self.worker_id = worker_id or f"worker_{int(time.time())}_{os.getpid()}"
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://redis-server:6379"
        )
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(redis_url=self.redis_url)
        self.doc_processor = None

        logger.info(f"🔧 Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")
        logger.info(f"   📦 Batch size: {self.batch_size}")

        # Debug environment variables
        logger.info(f"🔧 Environment Debug:")
        logger.info(f"   ENV: {os.getenv('ENV', 'NOT_SET')}")
        logger.info(f"   R2_BUCKET_NAME: {os.getenv('R2_BUCKET_NAME', 'NOT_SET')}")
        logger.info(
            f"   R2_ACCOUNT_ID: {os.getenv('R2_ACCOUNT_ID', 'NOT_SET')[:10]}..."
        )
        logger.info(
            f"   R2_ACCESS_KEY_ID: {os.getenv('R2_ACCESS_KEY_ID', 'NOT_SET')[:10]}..."
        )
        logger.info(f"   Environment file loaded: {env_file}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            # Connect to Redis
            await self.queue_manager.connect()
            logger.info(f"✅ Worker {self.worker_id}: Connected to Redis")

            # Initialize document processor
            self.doc_processor = AIDocumentProcessor()
            logger.info(f"✅ Worker {self.worker_id}: Document processor ready")

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

    async def process_task(self, task: IngestionTask) -> bool:
        """
        Process a single ingestion task.

        Args:
            task: IngestionTask to process

        Returns:
            True if successful, False if failed
        """
        start_time = time.time()

        logger.info(f"🚀 Worker {self.worker_id}: Processing task {task.task_id}")
        logger.info(f"   📄 Document: {task.document_id}")
        logger.info(f"   👤 User: {task.user_id}")
        logger.info(f"   📁 File: {task.filename}")
        logger.info(f"   🗂️ R2 Key: {task.file_path}")

        try:
            # Step 1: Download file from R2
            logger.info(f"📥 Worker {self.worker_id}: Downloading from R2...")
            bucket_name = os.getenv("R2_BUCKET_NAME", "studynotes")
            logger.info(f"🪣 Worker {self.worker_id}: Using bucket: '{bucket_name}'")
            logger.info(f"🔑 Worker {self.worker_id}: R2 Key: '{task.file_path}'")
            file_content = await self.doc_processor.download_from_r2(
                bucket_name, task.file_path
            )
            logger.info(
                f"✅ Worker {self.worker_id}: Downloaded {len(file_content)} bytes"
            )

            # Step 2: Extract text content
            logger.info(f"🔍 Worker {self.worker_id}: Extracting text content...")
            text_content = await self.doc_processor.extract_text_content(
                file_content, task.file_type, task.filename
            )

            if not text_content or len(text_content.strip()) < 50:
                raise Exception("Document appears to be empty or too short")

            logger.info(
                f"✅ Worker {self.worker_id}: Extracted {len(text_content)} characters"
            )

            # Step 3: Chunk document
            logger.info(f"🔪 Worker {self.worker_id}: Chunking document...")
            chunks = self.doc_processor.chunk_document(text_content)
            logger.info(f"✅ Worker {self.worker_id}: Created {len(chunks)} chunks")

            # Step 4: Generate embeddings
            logger.info(f"🧠 Worker {self.worker_id}: Generating embeddings...")
            embeddings = await self.doc_processor.generate_embeddings(chunks)
            logger.info(
                f"✅ Worker {self.worker_id}: Generated {len(embeddings)} embeddings"
            )

            # Step 5: Store in Qdrant
            collection_name = f"user_{task.user_id}_documents"
            logger.info(
                f"💾 Worker {self.worker_id}: Storing in Qdrant collection: {collection_name}"
            )

            await self.doc_processor.store_in_qdrant(
                collection_name=collection_name,
                chunks=chunks,
                embeddings=embeddings,
                task_data={
                    "userId": task.user_id,
                    "uploadId": task.document_id,
                    "taskId": task.task_id,
                    "fileName": task.filename,
                    "contentType": task.file_type,
                    "metadata": task.additional_metadata,
                },
            )

            processing_time = time.time() - start_time

            # Step 6: Send SUCCESS callback to backend
            if task.callback_url:
                logger.info(f"📞 Worker {self.worker_id}: Sending success callback...")
                callback_success = await self.doc_processor.send_callback(
                    task_data={
                        "callbackUrl": task.callback_url,
                        "taskId": task.task_id,
                        "uploadId": task.document_id,
                        "userId": task.user_id,
                    },
                    status="completed",
                    result={
                        "message": "Document processing completed successfully",
                        "chunksProcessed": len(chunks),
                        "collectionName": collection_name,
                        "documentLength": len(text_content),
                        "processingTime": processing_time,
                    },
                    processing_time=processing_time,
                    chunks_processed=len(chunks),
                    collection_name=collection_name,
                )
                logger.info(
                    f"📞 Worker {self.worker_id}: Callback: {'✅' if callback_success else '❌'}"
                )

            # Mark task as completed
            await self.queue_manager.complete_task(task.task_id, success=True)

            logger.info(
                f"✅ Worker {self.worker_id}: Task {task.task_id} completed successfully"
            )
            logger.info(f"   📊 Chunks: {len(chunks)}")
            logger.info(f"   💾 Collection: {collection_name}")
            logger.info(f"   ⏱️ Time: {processing_time:.2f}s")

            return True

        except Exception as e:
            error_msg = str(e)
            processing_time = time.time() - start_time

            logger.error(
                f"❌ Worker {self.worker_id}: Task {task.task_id} failed: {error_msg}"
            )
            logger.error(
                f"🔍 Worker {self.worker_id}: Traceback: {traceback.format_exc()}"
            )

            # Send FAILED callback to backend
            if task.callback_url:
                await self.doc_processor.send_callback(
                    task_data={
                        "callbackUrl": task.callback_url,
                        "taskId": task.task_id,
                        "uploadId": task.document_id,
                        "userId": task.user_id,
                    },
                    status="failed",
                    error=error_msg,
                    processing_time=processing_time,
                )

            # Mark task as failed
            await self.queue_manager.complete_task(
                task.task_id, success=False, error_message=error_msg
            )

            return False

    async def run(self):
        """
        Main worker loop - continuously process tasks from queue.
        """
        logger.info(f"🎬 Worker {self.worker_id}: Starting main loop")
        self.running = True

        consecutive_empty_polls = 0
        max_empty_polls = 5  # Wait longer after multiple empty polls

        while self.running:
            try:
                # Get next task from queue (with timeout)
                task = await self.queue_manager.dequeue_task(
                    worker_id=self.worker_id, timeout=10  # 10 second timeout
                )

                if task:
                    consecutive_empty_polls = 0

                    # Process the task
                    success = await self.process_task(task)

                    if success:
                        logger.info(
                            f"✅ Worker {self.worker_id}: Task processed successfully"
                        )
                    else:
                        logger.error(
                            f"❌ Worker {self.worker_id}: Task processing failed"
                        )

                else:
                    # No task available - implement backoff
                    consecutive_empty_polls += 1

                    if consecutive_empty_polls >= max_empty_polls:
                        sleep_time = min(
                            30, consecutive_empty_polls * 2
                        )  # Max 30 seconds
                        logger.debug(
                            f"💤 Worker {self.worker_id}: No tasks, sleeping {sleep_time}s"
                        )
                        await asyncio.sleep(sleep_time)
                    else:
                        await asyncio.sleep(1)  # Short wait

            except asyncio.CancelledError:
                logger.info(f"🛑 Worker {self.worker_id}: Received cancellation signal")
                break

            except Exception as e:
                logger.error(
                    f"❌ Worker {self.worker_id}: Unexpected error in main loop: {e}"
                )
                logger.error(
                    f"🔍 Worker {self.worker_id}: Traceback: {traceback.format_exc()}"
                )

                # Sleep before retrying to avoid tight error loop
                await asyncio.sleep(5)

        logger.info(f"🏁 Worker {self.worker_id}: Main loop ended")


# ==============================================================================
# MAIN WORKER SCRIPT
# ==============================================================================


async def main():
    """Main worker entry point"""
    # Handle shutdown signals
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        logger.info(f"📡 Received signal {signum}, initiating shutdown...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and initialize worker
    worker = DocumentIngestionWorker()

    try:
        await worker.initialize()

        # Run worker until shutdown signal
        worker_task = asyncio.create_task(worker.run())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for either worker completion or shutdown signal
        done, pending = await asyncio.wait(
            [worker_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"❌ Worker failed to start: {e}")

    finally:
        await worker.shutdown()


if __name__ == "__main__":
    logger.info("🚀 Starting Document Ingestion Worker")
    asyncio.run(main())
