"""
Learning Assistant Worker (Combined)
Processes both queues using Gemini Flash:
  - learning_assistant_solve   → Solve Homework
  - learning_assistant_grade   → Grade & Tips
"""

import asyncio
import json
import logging
import signal
from datetime import datetime
import os

from src.queue.queue_manager import QueueManager, set_job_status

logger = logging.getLogger("chatbot")

POINTS_COST = 2  # Gemini vision feature


class LearningAssistantWorker:
    """Combined worker for Solve Homework and Grade & Tips."""

    def __init__(
        self,
        worker_id: str = "learning_assistant_worker",
        redis_url: str = "redis://redis-server:6379",
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.running = False

        self.solve_queue = QueueManager(
            redis_url=self.redis_url, queue_name="learning_assistant_solve"
        )
        self.grade_queue = QueueManager(
            redis_url=self.redis_url, queue_name="learning_assistant_grade"
        )

        # Lazy-init service (avoids import-time crash if config not set)
        self._service = None

        logger.info(f"🎓 LearningAssistantWorker {self.worker_id} initialized")

    @property
    def service(self):
        if self._service is None:
            from src.services.learning_assistant_service import (
                LearningAssistantService,
            )

            self._service = LearningAssistantService()
        return self._service

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self):
        await self.solve_queue.connect()
        await self.grade_queue.connect()
        logger.info(f"✅ {self.worker_id}: connected to queues (solve + grade)")

    async def start(self):
        self.running = True
        logger.info(f"🚀 {self.worker_id}: starting dual-queue processing…")
        await asyncio.gather(
            self._consume_solve(),
            self._consume_grade(),
            return_exceptions=True,
        )

    async def stop(self):
        self.running = False
        await self.solve_queue.disconnect()
        await self.grade_queue.disconnect()
        logger.info(f"⏹ {self.worker_id}: stopped")

    # ------------------------------------------------------------------
    # Queue consumers
    # ------------------------------------------------------------------

    async def _consume_solve(self):
        while self.running:
            try:
                task = await self.solve_queue.redis_client.brpop(
                    self.solve_queue.task_queue_key, timeout=1
                )
                if task:
                    _, data = task
                    job = json.loads(data)
                    logger.info(f"📦 [Solve] job={job.get('job_id')}")
                    await self._handle_solve(job)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"❌ [Solve] error: {exc}", exc_info=True)
                await asyncio.sleep(5)

    async def _consume_grade(self):
        while self.running:
            try:
                task = await self.grade_queue.redis_client.brpop(
                    self.grade_queue.task_queue_key, timeout=1
                )
                if task:
                    _, data = task
                    job = json.loads(data)
                    logger.info(f"📦 [Grade] job={job.get('job_id')}")
                    await self._handle_grade(job)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"❌ [Grade] error: {exc}", exc_info=True)
                await asyncio.sleep(5)

    # ------------------------------------------------------------------
    # Job handlers
    # ------------------------------------------------------------------

    async def _handle_solve(self, job: dict):
        job_id = job["job_id"]
        user_id = job.get("user_id")
        redis = self.solve_queue.redis_client

        await set_job_status(
            redis_client=redis,
            job_id=job_id,
            status="processing",
            user_id=user_id,
        )

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.service.solve_homework(
                    question_text=job.get("question_text"),
                    question_image_b64=job.get("question_image"),
                    image_mime_type=job.get("image_mime_type", "image/jpeg"),
                    subject=job.get("subject", "other"),
                    grade_level=job.get("grade_level", "other"),
                    language=job.get("language", "vi"),
                ),
            )

            await set_job_status(
                redis_client=redis,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                solution_steps=result.get("solution_steps", []),
                final_answer=result.get("final_answer", ""),
                explanation=result.get("explanation", ""),
                key_formulas=result.get("key_formulas", []),
                study_tips=result.get("study_tips", []),
                tokens=result.get("tokens", {}),
                points_deducted=POINTS_COST,
            )
            logger.info(f"✅ [Solve] {job_id} completed")

        except Exception as exc:
            logger.error(f"❌ [Solve] {job_id} failed: {exc}", exc_info=True)
            await set_job_status(
                redis_client=redis,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                error=str(exc),
            )

    async def _handle_grade(self, job: dict):
        job_id = job["job_id"]
        user_id = job.get("user_id")
        redis = self.grade_queue.redis_client

        await set_job_status(
            redis_client=redis,
            job_id=job_id,
            status="processing",
            user_id=user_id,
        )

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.service.grade_and_tips(
                    assignment_image_b64=job.get("assignment_image"),
                    assignment_image_mime=job.get(
                        "assignment_image_mime_type", "image/jpeg"
                    ),
                    assignment_text=job.get("assignment_text"),
                    student_work_image_b64=job.get("student_work_image"),
                    student_work_mime=job.get(
                        "student_work_image_mime_type", "image/jpeg"
                    ),
                    student_answer_text=job.get("student_answer_text"),
                    subject=job.get("subject", "other"),
                    grade_level=job.get("grade_level", "other"),
                    language=job.get("language", "vi"),
                ),
            )

            await set_job_status(
                redis_client=redis,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                score=result.get("score", 0),
                score_breakdown=result.get("score_breakdown", {}),
                overall_feedback=result.get("overall_feedback", ""),
                strengths=result.get("strengths", []),
                weaknesses=result.get("weaknesses", []),
                correct_solution=result.get("correct_solution", ""),
                improvement_plan=result.get("improvement_plan", []),
                study_plan=result.get("study_plan", []),
                recommended_materials=result.get("recommended_materials", []),
                tokens=result.get("tokens", {}),
                points_deducted=POINTS_COST,
            )
            logger.info(f"✅ [Grade] {job_id} completed")

        except Exception as exc:
            logger.error(f"❌ [Grade] {job_id} failed: {exc}", exc_info=True)
            await set_job_status(
                redis_client=redis,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                error=str(exc),
            )


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------


async def main():
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
    worker = LearningAssistantWorker(redis_url=redis_url)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))

    try:
        await worker.initialize()
        await worker.start()
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
