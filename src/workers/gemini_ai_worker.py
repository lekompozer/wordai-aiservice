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
    from src.workers.analyze_architecture_worker import AnalyzeArchitectureWorker
    from src.workers.scaffold_project_worker import ScaffoldProjectWorker

    # Copy _handle_job methods
    async def _handle_architecture_job(self, job: dict):
        """Handle architecture analysis job (copied from AnalyzeArchitectureWorker)"""
        # Use original logic
        from src.workers.analyze_architecture_worker import AnalyzeArchitectureWorker

        temp_worker = AnalyzeArchitectureWorker.__new__(AnalyzeArchitectureWorker)
        temp_worker.queue_manager = self.architecture_queue
        temp_worker.vertex_ai = self.vertex_ai
        temp_worker.points_service = self.points_service
        temp_worker.db_manager = self.db_manager
        temp_worker.worker_id = self.worker_id

        await temp_worker._handle_job(job)

    async def _handle_scaffold_job(self, job: dict):
        """Handle scaffolding job (copied from ScaffoldProjectWorker)"""
        from src.workers.scaffold_project_worker import ScaffoldProjectWorker

        temp_worker = ScaffoldProjectWorker.__new__(ScaffoldProjectWorker)
        temp_worker.queue_manager = self.scaffold_queue
        temp_worker.vertex_ai = self.vertex_ai
        temp_worker.points_service = self.points_service
        temp_worker.db_manager = self.db_manager
        temp_worker.worker_id = self.worker_id

        await temp_worker._handle_job(job)

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


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    worker = GeminiAIWorker()

    try:
        asyncio.run(worker.initialize())
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        logger.info("⚠️  Shutdown signal received")
        asyncio.run(worker.stop())
    except Exception as e:
        logger.error(f"❌ Worker fatal error: {e}", exc_info=True)
        asyncio.run(worker.stop())
