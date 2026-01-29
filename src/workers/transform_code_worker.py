"""
Transform Code Worker
Processes AI code transformation tasks (refactor, optimize, convert, fix, add-feature)
"""

import asyncio
import json
import logging
import signal
from datetime import datetime

from src.queue.queue_manager import QueueManager, set_job_status
from src.services.vertex_ai_service import get_vertex_ai_service
from src.services.points_service import get_points_service
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

# Points cost
POINTS_COST_AI_CODE = 2


class TransformCodeWorker:
    """Worker for processing AI code transformation tasks"""

    def __init__(
        self,
        worker_id: str = "transform_code_worker",
        redis_url: str = "redis://redis-server:6379",
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.running = False

        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="software_lab_transform_code"
        )
        self.vertex_ai = get_vertex_ai_service()
        self.points_service = get_points_service()
        self.db_manager = DBManager()

        logger.info(f"🔧 Transform Code Worker {self.worker_id} initialized")

    async def initialize(self):
        await self.queue_manager.connect()
        logger.info(f"✅ Worker {self.worker_id}: Connected to Redis queue")

    async def start(self):
        self.running = True
        logger.info(f"🚀 Worker {self.worker_id}: Starting task processing...")

        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        while self.running:
            try:
                job_data = await self.queue_manager.redis_client.brpop(
                    self.queue_manager.task_queue_key, timeout=5
                )
                if not job_data:
                    continue

                _, job_json = job_data
                job = json.loads(job_json)
                await self._process_task(job)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Worker error: {e}")
                await asyncio.sleep(1)

        logger.info(f"🛑 Worker {self.worker_id}: Stopped")

    def _handle_shutdown(self, signum, frame):
        self.running = False

    async def _process_task(self, job: dict):
        """Process task with 15-minute timeout protection"""
        job_id = job.get("job_id")
        user_id = job.get("user_id")

        # ⏱️ TIMEOUT: 15 minutes max
        try:
            return await asyncio.wait_for(self._process_task_internal(job), timeout=900)
        except asyncio.TimeoutError:
            logger.error(f"❌ Job {job_id} TIMEOUT after 15 minutes")
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                error="Processing timeout after 15 minutes",
                completed_at=datetime.utcnow().isoformat(),
            )
            # Refund points
            try:
                await self.points_service.refund_points(
                    user_id=user_id,
                    amount=POINTS_COST_AI_CODE,
                    reason="Transform timeout",
                )
            except Exception as e:
                logger.error(f"❌ Refund failed: {e}")
            return False

    async def _process_task_internal(self, job: dict):
        """Internal processing logic"""
        job_id = job.get("job_id")
        user_id = job.get("user_id")
        file_id = job.get("file_id")
        transformation = job.get("transformation")
        instruction = job.get("instruction")
        selection = job.get("selection")

        try:
            logger.info(f"⚙️ Processing transform job {job_id}: {transformation}")

            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                started_at=datetime.utcnow().isoformat(),
            )

            db = self.db_manager.db
            file = await db.software_lab_files.find_one({"file_id": file_id})
            if not file:
                raise Exception(f"File {file_id} not found")

            code_content = file.get("content", "")

            if selection:
                lines = code_content.split("\n")
                start = selection.get("start_line", 1) - 1
                end = selection.get("end_line", len(lines))
                code_content = "\n".join(lines[start:end])

            system_prompt = f"""You are a code refactoring expert.

TRANSFORMATION TYPE: {transformation}
INSTRUCTION: {instruction}

YOUR TASK:
1. Apply the requested transformation
2. Maintain or improve code readability
3. Follow best practices
4. Preserve existing functionality unless explicitly changing it
5. Add comments explaining significant changes

OUTPUT FORMAT:
Line 1: Summary of changes made (1-2 sentences)
Then: The transformed code (no markdown fences)
"""

            user_prompt = f"""ORIGINAL CODE:
```
{code_content}
```

Transform this code: {instruction}
"""

            response = await self.vertex_ai.call_claude(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=32000,
                temperature=0.3,
            )

            content = response["content"]
            tokens = response["tokens"]

            lines = content.split("\n")
            changes_summary = lines[0] if lines else ""
            transformed_code = "\n".join(lines[1:]) if len(lines) > 1 else content

            diff = self._calculate_diff(code_content, transformed_code)

            interaction = {
                "user_id": user_id,
                "file_id": file_id,
                "action": "transform",
                "transformation": transformation,
                "instruction": instruction,
                "selection": selection,
                "ai_response": content,
                "model": response["model"],
                "tokens_input": tokens["input"],
                "tokens_output": tokens["output"],
                "tokens_total": tokens["total"],
                "created_at": datetime.utcnow(),
            }
            await db.software_lab_ai_interactions.insert_one(interaction)

            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                transformed_code=transformed_code,
                changes_summary=changes_summary,
                diff=diff,
                tokens=tokens,
                completed_at=datetime.utcnow().isoformat(),
            )

            logger.info(f"✅ Job {job_id} completed")

        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)

            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                error=str(e),
                completed_at=datetime.utcnow().isoformat(),
            )

            # Refund points on failure
            try:
                await self.points_service.refund_points(
                    user_id=user_id,
                    amount=POINTS_COST_AI_CODE,
                    reason=f"Code transformation failed: {str(e)[:100]}",
                )
                logger.info(
                    f"💰 Refunded {POINTS_COST_AI_CODE} points to user {user_id}"
                )
            except Exception as refund_error:
                logger.error(f"❌ Failed to refund points: {refund_error}")

    def _calculate_diff(self, original: str, transformed: str) -> dict:
        """Calculate simple diff statistics"""
        original_lines = original.split("\n")
        transformed_lines = transformed.split("\n")

        additions = max(0, len(transformed_lines) - len(original_lines))
        deletions = max(0, len(original_lines) - len(transformed_lines))

        preview = f"+{additions} lines, -{deletions} lines"

        return {"additions": additions, "deletions": deletions, "preview": preview}

    async def stop(self):
        self.running = False
        await self.queue_manager.disconnect()
        logger.info(f"✅ Worker {self.worker_id}: Stopped gracefully")


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    worker = TransformCodeWorker()

    async def main():
        await worker.initialize()
        await worker.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
