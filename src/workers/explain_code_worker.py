"""
Explain Code Worker
Processes AI code explanation tasks from Redis queue
Creates inline comments to explain code structure
"""

import asyncio
import json
import logging
import signal
from datetime import datetime
from typing import Optional, List

from src.queue.queue_manager import (
    QueueManager,
    set_job_status,
    get_job_status,
)
from src.services.vertex_ai_service import get_vertex_ai_service
from src.services.points_service import get_points_service
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

# Points cost for AI code explanation
POINTS_COST_AI_CODE = 2


class ExplainCodeWorker:
    """Worker for processing AI code explanation tasks"""

    def __init__(
        self,
        worker_id: str = "explain_code_worker",
        redis_url: str = "redis://redis-server:6379",
        max_concurrent_jobs: int = 3,
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.max_concurrent_jobs = max_concurrent_jobs
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="software_lab_explain_code"
        )
        self.vertex_ai = get_vertex_ai_service()
        self.points_service = get_points_service()
        self.db_manager = DBManager()

        logger.info(f"🔧 Explain Code Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            await self.queue_manager.connect()
            logger.info(f"✅ Worker {self.worker_id}: Connected to Redis queue")
        except Exception as e:
            logger.error(f"❌ Worker {self.worker_id}: Initialization failed: {e}")
            raise

    async def start(self):
        """Start processing tasks"""
        self.running = True
        logger.info(f"🚀 Worker {self.worker_id}: Starting task processing...")

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        while self.running:
            try:
                # Get job from Redis queue
                job_data = await self.queue_manager.redis_client.brpop(
                    self.queue_manager.task_queue_key, timeout=5
                )

                if not job_data:
                    continue

                # Parse job
                _, job_json = job_data
                job = json.loads(job_json)
                job_id = job.get("job_id")

                logger.info(f"📥 Received job {job_id}")

                # Process task
                await self._process_task(job)

            except asyncio.CancelledError:
                logger.info(f"⏸️ Worker {self.worker_id}: Task processing cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Worker {self.worker_id}: Error in main loop: {e}")
                await asyncio.sleep(1)

        logger.info(f"🛑 Worker {self.worker_id}: Stopped")

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"🛑 Worker {self.worker_id}: Received shutdown signal")
        self.running = False

    async def _process_task(self, job: dict):
        """Process a single code explanation task with timeout protection"""
        job_id = job.get("job_id")
        user_id = job.get("user_id")

        # ⏱️ TIMEOUT PROTECTION: 15 minutes max
        timeout_seconds = 900  # 15 minutes

        try:
            return await asyncio.wait_for(
                self._process_task_internal(job), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(
                f"❌ Job {job_id} TIMEOUT after {timeout_seconds}s - auto-failing"
            )

            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                error=f"Processing timeout after 15 minutes",
                completed_at=datetime.utcnow().isoformat(),
            )

            # Refund points on timeout
            try:
                await self.points_service.refund_points(
                    user_id=user_id,
                    amount=POINTS_COST_AI_CODE,
                    reason="Code explanation timeout after 15 minutes",
                )
                logger.info(
                    f"💰 Refunded {POINTS_COST_AI_CODE} points to user {user_id}"
                )
            except Exception as refund_error:
                logger.error(f"❌ Failed to refund points: {refund_error}")

            return False
        except Exception as e:
            logger.error(f"❌ Worker error: {e}", exc_info=True)
            return False

    async def _process_task_internal(self, job: dict):
        """Internal task processing (separated for timeout wrapper)"""
        job_id = job.get("job_id")
        user_id = job.get("user_id")
        project_id = job.get("project_id")
        file_id = job.get("file_id")
        selection = job.get("selection")
        question = job.get("question")

        try:
            logger.info(f"⚙️ Processing explain code job {job_id}")

            # Update status to processing
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                started_at=datetime.utcnow().isoformat(),
            )

            # Get file from MongoDB
            db = self.db_manager.db
            file = await db.software_lab_files.find_one({"file_id": file_id})

            if not file:
                raise Exception(f"File {file_id} not found")

            # Get architecture if exists
            architecture = await db.software_lab_architectures.find_one(
                {"project_id": project_id}
            )

            # Get code to explain
            code_content = file.get("content", "")

            # If selection, extract only those lines
            if selection:
                lines = code_content.split("\n")
                start = selection.get("start_line", 1) - 1  # 0-indexed
                end = selection.get("end_line", len(lines))
                code_content = "\n".join(lines[start:end])

            # Build prompts
            system_prompt = self._build_system_prompt(file, architecture)
            user_prompt = self._build_user_prompt(code_content, question)

            # Call Claude 4.5 via Vertex AI
            response = await self.vertex_ai.call_claude(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=32000,
                temperature=0.3,
            )

            # Extract explanation
            content = response["content"]
            tokens = response["tokens"]

            # Parse response to create annotated code
            annotated_code = self._create_annotated_code(code_content, content)
            explanation, key_concepts, code_snippets = self._parse_explanation(content)

            # Save interaction to MongoDB
            interaction = {
                "user_id": user_id,
                "project_id": project_id,
                "file_id": file_id,
                "action": "explain",
                "selection": selection,
                "user_question": question,
                "ai_response": content,
                "model": response["model"],
                "tokens_input": tokens["input"],
                "tokens_output": tokens["output"],
                "tokens_total": tokens["total"],
                "created_at": datetime.utcnow(),
            }
            await db.software_lab_ai_interactions.insert_one(interaction)

            # Update job status to completed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                file_path=file.get("path"),
                annotated_code=annotated_code,
                explanation=explanation,
                key_concepts=key_concepts,
                code_snippets=code_snippets,
                tokens=tokens,
                completed_at=datetime.utcnow().isoformat(),
            )

            logger.info(f"✅ Job {job_id} completed")

        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)

            # Update status to failed
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
                    reason=f"Code explanation failed: {str(e)[:100]}",
                )
                logger.info(
                    f"💰 Refunded {POINTS_COST_AI_CODE} points to user {user_id}"
                )
            except Exception as refund_error:
                logger.error(f"❌ Failed to refund points: {refund_error}")

    def _build_system_prompt(self, file: dict, architecture: Optional[dict]) -> str:
        """Build system prompt for Claude"""
        prompt = f"""You are a patient programming tutor explaining code to students.

FILE: {file.get('path')}
LANGUAGE: {file.get('language', 'unknown')}
"""

        if architecture:
            arch_doc = architecture.get("architecture_document", {})
            prompt += f"""
SYSTEM CONTEXT:
This code is part of a larger system: {arch_doc.get('system_overview', '')[:200]}
"""

        prompt += """
YOUR TASK:
Explain this code by adding INLINE COMMENTS at key sections.

OUTPUT FORMAT:
Return the SAME code with added comments (// or #) explaining:
1. What each major section does
2. Why certain approaches are used
3. Key concepts (useState, async/await, etc.)
4. Best practices demonstrated

Add comments above or inline with code blocks. DO NOT change the code structure.
"""

        return prompt

    def _build_user_prompt(self, code: str, question: Optional[str]) -> str:
        """Build user prompt"""
        prompt = f"""CODE TO EXPLAIN:
```
{code}
```
"""

        if question:
            prompt += f"\nSTUDENT'S QUESTION: {question}\n"
        else:
            prompt += "\nExplain this code with inline comments.\n"

        return prompt

    def _create_annotated_code(self, original_code: str, ai_response: str) -> str:
        """
        Create annotated code with inline comments.
        AI should return code with comments already added.
        """
        # If AI response contains code blocks, extract them
        if "```" in ai_response:
            # Extract code from markdown fences
            parts = ai_response.split("```")
            if len(parts) >= 3:
                # Take the code block (between first and second ```)
                code_block = parts[1]
                # Remove language identifier from first line
                lines = code_block.split("\n")
                if lines and lines[0].strip() in [
                    "python",
                    "javascript",
                    "jsx",
                    "js",
                    "py",
                ]:
                    lines = lines[1:]
                return "\n".join(lines)

        # Otherwise, return AI response as-is (should already be annotated code)
        return ai_response

    def _parse_explanation(self, content: str) -> tuple[str, List[str], List[dict]]:
        """Parse explanation into components"""
        # For now, return simple structure
        # Frontend can parse the annotated code for display

        explanation = "Code explained with inline comments. See annotated code."
        key_concepts = []
        code_snippets = []

        # Try to extract key concepts from content
        if "KEY CONCEPTS:" in content:
            parts = content.split("KEY CONCEPTS:")
            if len(parts) > 1:
                concepts_text = parts[1].split("\n\n")[0]
                key_concepts = [
                    c.strip("- ").strip()
                    for c in concepts_text.split("\n")
                    if c.strip()
                ]

        return explanation, key_concepts, code_snippets

    async def stop(self):
        """Stop worker gracefully"""
        self.running = False
        await self.queue_manager.disconnect()
        logger.info(f"✅ Worker {self.worker_id}: Stopped gracefully")


# Run worker if executed directly
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    worker = ExplainCodeWorker()

    async def main():
        await worker.initialize()
        await worker.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
