"""
Generate Code Worker
Processes AI code generation tasks from Redis queue
"""

import asyncio
import json
import logging
import signal
from datetime import datetime
from typing import Optional

from src.queue.queue_manager import (
    QueueManager,
    set_job_status,
    get_job_status,
)
from src.services.vertex_ai_service import get_vertex_ai_service
from src.services.points_service import get_points_service
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

# Points cost for AI code generation
POINTS_COST_AI_CODE = 2


class GenerateCodeWorker:
    """Worker for processing AI code generation tasks"""

    def __init__(
        self,
        worker_id: str = "generate_code_worker",
        redis_url: str = "redis://redis-server:6379",
        max_concurrent_jobs: int = 3,
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.max_concurrent_jobs = max_concurrent_jobs
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="software_lab_generate_code"
        )
        self.vertex_ai = get_vertex_ai_service()
        self.points_service = get_points_service()
        self.db_manager = DBManager()

        logger.info(f"🔧 Generate Code Worker {self.worker_id} initialized")
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
        """Process a single code generation task with timeout protection"""
        job_id = job.get("job_id")
        user_id = job.get("user_id")
        project_id = job.get("project_id")
        user_query = job.get("user_query")

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

            # Mark as failed in Redis
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
                    reason="Code generation timeout after 15 minutes",
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
        user_query = job.get("user_query")

        try:
            logger.info(f"⚙️ Processing generate code job {job_id}")

            # Update status to processing
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                started_at=datetime.utcnow().isoformat(),
            )

            # Get project and files from MongoDB (sync calls wrapped in async)
            db = self.db_manager.db
            project = await asyncio.to_thread(
                db.software_lab_projects.find_one, {"project_id": project_id}
            )

            if not project:
                raise Exception(f"Project {project_id} not found")

            # Get context files
            context_files = []
            if job.get("context_file_ids"):
                file_ids = job["context_file_ids"]
                cursor = db.software_lab_files.find({"file_id": {"$in": file_ids}})
                files = await asyncio.to_thread(list, cursor)
                context_files = files
            elif job.get("include_all_files"):
                cursor = db.software_lab_files.find({"project_id": project_id})
                files = await asyncio.to_thread(list, cursor)
                context_files = files

            # Get architecture if exists
            architecture = await asyncio.to_thread(
                db.software_lab_architectures.find_one, {"project_id": project_id}
            )

            # Build prompts
            system_prompt = self._build_system_prompt(project, architecture)
            user_prompt = self._build_user_prompt(user_query, context_files)

            # Call Claude 4.5 via Vertex AI
            response = await self.vertex_ai.call_claude(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=32000,
                temperature=0.3,
            )

            # Extract code and explanation
            content = response["content"]
            tokens = response["tokens"]

            # Parse response (code + explanation)
            generated_code, explanation = self._parse_response(content)

            # Suggest file location
            suggested_file = self._suggest_file_location(
                user_query, job.get("target_path"), project
            )

            # Save interaction to MongoDB
            interaction = {
                "user_id": user_id,
                "project_id": project_id,
                "action": "generate",
                "user_query": user_query,
                "context_files": [f["file_id"] for f in context_files],
                "ai_response": content,
                "generated_code": generated_code,
                "model": response["model"],
                "tokens_input": tokens["input"],
                "tokens_output": tokens["output"],
                "tokens_total": tokens["total"],
                "created_at": datetime.utcnow(),
            }
            await asyncio.to_thread(
                db.software_lab_ai_interactions.insert_one, interaction
            )

            # Update job status to completed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                generated_code=generated_code,
                explanation=explanation,
                suggested_file=suggested_file,
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
                    reason=f"Code generation failed: {str(e)[:100]}",
                )
                logger.info(
                    f"💰 Refunded {POINTS_COST_AI_CODE} points to user {user_id}"
                )
            except Exception as refund_error:
                logger.error(f"❌ Failed to refund points: {refund_error}")

    def _build_system_prompt(self, project: dict, architecture: Optional[dict]) -> str:
        """Build system prompt for Claude"""
        prompt = f"""You are an expert software engineer helping students learn to code.

PROJECT: {project.get('name', 'Untitled')}
"""

        if architecture:
            arch_doc = architecture.get("architecture_document", {})
            prompt += f"""
SYSTEM ARCHITECTURE:
{arch_doc.get('system_overview', '')}

FEATURES:
"""
            features = arch_doc.get("features_list", [])
            for feat in features[:5]:  # Top 5 features
                prompt += f"- {feat.get('name')}: {feat.get('description')}\n"

        prompt += """
YOUR TASK:
Generate clean, well-commented code that:
1. Follows best practices
2. Includes helpful comments explaining WHY, not just WHAT
3. Uses modern syntax and patterns
4. Is educational - students will learn from reading it

OUTPUT FORMAT:
First line: Brief explanation (1-2 sentences)
Then: The code (no markdown fences)
"""

        return prompt

    def _build_user_prompt(self, user_query: str, context_files: list) -> str:
        """Build user prompt with context"""
        prompt = f"REQUIREMENTS:\n{user_query}\n\n"

        if context_files:
            prompt += "CONTEXT FILES:\n"
            for file in context_files[:5]:  # Max 5 files
                prompt += f"\n// File: {file.get('path')}\n"
                content = file.get("content", "")[:2000]  # First 2K chars
                prompt += content + "\n"

        return prompt

    def _parse_response(self, content: str) -> tuple[str, str]:
        """Parse AI response into code and explanation"""
        lines = content.split("\n")

        # First line is explanation
        explanation = lines[0] if lines else ""

        # Rest is code
        code = "\n".join(lines[1:]) if len(lines) > 1 else content

        return code.strip(), explanation.strip()

    def _suggest_file_location(
        self, user_query: str, target_path: Optional[str], project: dict
    ) -> dict:
        """Suggest where to save the generated code"""
        if target_path:
            return {"path": target_path, "exists": False}  # Frontend should check

        # Simple heuristic based on query
        query_lower = user_query.lower()

        if "component" in query_lower or "jsx" in query_lower:
            return {"path": "src/components/NewComponent.jsx", "exists": False}
        elif "model" in query_lower or "database" in query_lower:
            return {"path": "backend/models/model.py", "exists": False}
        elif "api" in query_lower or "route" in query_lower:
            return {"path": "backend/routes/routes.py", "exists": False}
        else:
            return {"path": "src/utils.js", "exists": False}

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

    worker = GenerateCodeWorker()

    async def main():
        await worker.initialize()
        await worker.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
