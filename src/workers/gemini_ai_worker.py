"""
Gemini AI Worker (Combined)
Processes both Architecture Analysis and Project Scaffolding using Gemini 3 Pro
Handles 2 queues:
- software_lab_analyze_architecture
- software_lab_scaffold_project
"""

import asyncio
import json
import logging
import signal
from datetime import datetime
import uuid

from src.queue.queue_manager import QueueManager, set_job_status
from src.services.vertex_ai_service import get_vertex_ai_service
from src.services.points_service import get_points_service
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

# Points cost
POINTS_COST_AI_CODE = 2


class GeminiAIWorker:
    """Combined worker for Architecture Analysis and Project Scaffolding"""

    def __init__(
        self,
        worker_id: str = "gemini_ai_worker",
        redis_url: str = "redis://redis-server:6379",
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.running = False

        # Initialize 2 queue managers
        self.architecture_queue = QueueManager(
            redis_url=self.redis_url, queue_name="software_lab_analyze_architecture"
        )
        self.scaffold_queue = QueueManager(
            redis_url=self.redis_url, queue_name="software_lab_scaffold_project"
        )

        self.vertex_ai = get_vertex_ai_service()
        self.points_service = get_points_service()
        self.db_manager = DBManager()

        logger.info(
            f"🔧 Gemini AI Worker {self.worker_id} initialized (Architecture + Scaffold)"
        )

    async def initialize(self):
        await self.architecture_queue.connect()
        await self.scaffold_queue.connect()
        logger.info(f"✅ Worker {self.worker_id}: Connected to both queues")

    async def start(self):
        self.running = True
        logger.info(f"🚀 Worker {self.worker_id}: Starting dual-queue processing...")

        # Process both queues concurrently
        await asyncio.gather(
            self._process_architecture_queue(),
            self._process_scaffold_queue(),
            return_exceptions=True,
        )

    async def _process_architecture_queue(self):
        """Process architecture analysis tasks"""
        while self.running:
            try:
                task = await self.architecture_queue.redis_client.brpop(
                    self.architecture_queue.task_queue_key, timeout=1
                )

                if task:
                    _, task_data = task
                    job = json.loads(task_data)
                    logger.info(
                        f"📦 [Architecture] Processing job: {job.get('job_id')}"
                    )
                    await self._handle_architecture_job(job)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ [Architecture] Queue error: {e}")
                await asyncio.sleep(5)

    async def _process_scaffold_queue(self):
        """Process project scaffolding tasks"""
        while self.running:
            try:
                task = await self.scaffold_queue.redis_client.brpop(
                    self.scaffold_queue.task_queue_key, timeout=1
                )

                if task:
                    _, task_data = task
                    job = json.loads(task_data)
                    logger.info(f"📦 [Scaffold] Processing job: {job.get('job_id')}")
                    await self._handle_scaffold_job(job)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ [Scaffold] Queue error: {e}")
                await asyncio.sleep(5)

    # Import methods from original workers
    async def _handle_architecture_job(self, job: dict):
        """Handle architecture analysis job using original worker logic"""
        from src.workers.analyze_architecture_worker import AnalyzeArchitectureWorker

        # Create instance with same config
        arch_worker = AnalyzeArchitectureWorker(
            worker_id=self.worker_id, redis_url=self.redis_url
        )
        # Replace queue manager with our architecture queue
        arch_worker.queue_manager = self.architecture_queue
        arch_worker.vertex_ai = self.vertex_ai
        arch_worker.points_service = self.points_service
        arch_worker.db_manager = self.db_manager

        # Process task
        await arch_worker._process_task(job)

    async def _handle_scaffold_job(self, job: dict):
        """Handle scaffolding job using original worker logic"""
        from src.workers.scaffold_project_worker import ScaffoldProjectWorker

        # Create instance with same config
        scaffold_worker = ScaffoldProjectWorker(
            worker_id=self.worker_id, redis_url=self.redis_url
        )
        # Replace queue manager with our scaffold queue
        scaffold_worker.queue_manager = self.scaffold_queue
        scaffold_worker.vertex_ai = self.vertex_ai
        scaffold_worker.points_service = self.points_service
        scaffold_worker.db_manager = self.db_manager

        # Process task
        await scaffold_worker._process_task(job)

    async def stop(self):
        """Stop worker gracefully"""
        logger.info(f"🛑 Worker {self.worker_id}: Stopping...")
        self.running = False
        await self.architecture_queue.disconnect()
        await self.scaffold_queue.disconnect()
        logger.info(f"✅ Worker {self.worker_id}: Stopped")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"⚠️  Received signal {signum}, shutting down gracefully...")
    raise KeyboardInterrupt


async def main():
    """Main async entry point"""
    worker = GeminiAIWorker()

    try:
        await worker.initialize()
        await worker.start()
    except KeyboardInterrupt:
        logger.info("⚠️  Shutdown signal received")
        await worker.stop()
    except Exception as e:
        logger.error(f"❌ Worker fatal error: {e}", exc_info=True)
        await worker.stop()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    asyncio.run(main())
