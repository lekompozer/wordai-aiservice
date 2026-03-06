"""
AI Assistant GLM-5 Worker
Combined worker for all 3 AI Assistant (Software Lab) queues using GLM-5 via Vertex AI.

Replaces (disabled):
  - generate-code-worker  (queue: software_lab_generate_code)
  - explain-code-worker   (queue: software_lab_explain_code)
  - transform-code-worker (queue: software_lab_transform_code)

Uses GLM-5 (zai-org/glm-5-maas) via Vertex AI instead of Claude.
Saves ~700MB RAM vs running 3 separate workers.
"""

import asyncio
import json
import logging
import signal
import sys
import os
from datetime import datetime
from typing import Optional, List

from dotenv import load_dotenv

# Load env
env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
load_dotenv("development.env" if env_var == "development" else ".env")

from src.queue.queue_manager import QueueManager, set_job_status
from src.services.glm5_client import get_glm5_client
from src.services.points_service import get_points_service
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

POINTS_COST_AI_CODE = 1

QUEUE_GENERATE = "queue:software_lab_generate_code"
QUEUE_EXPLAIN = "queue:software_lab_explain_code"
QUEUE_TRANSFORM = "queue:software_lab_transform_code"
ALL_QUEUES = [QUEUE_GENERATE, QUEUE_EXPLAIN, QUEUE_TRANSFORM]


class AIAssistantGLM5Worker:
    """
    Single worker handling generate/explain/transform queues with GLM-5.
    Uses brpop([queue1, queue2, queue3]) for multi-queue polling.
    """

    def __init__(
        self,
        worker_id: str = "ai_assistant_glm5_worker",
        redis_url: str = "redis://redis-server:6379",
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.running = False

        # Shared Redis connection via one QueueManager (any queue name works)
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="software_lab_generate_code"
        )
        self.glm5 = get_glm5_client()
        self.points_service = get_points_service()
        self.db_manager = DBManager()

        logger.info(f"🔧 AI Assistant GLM-5 Worker '{self.worker_id}' initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")
        logger.info(f"   🤖 Model: zai-org/glm-5-maas (Vertex AI)")
        logger.info(f"   📬 Queues: {', '.join(ALL_QUEUES)}")

    async def initialize(self):
        await self.queue_manager.connect()
        logger.info(f"✅ Worker '{self.worker_id}': Connected to Redis")

    async def start(self):
        self.running = True
        logger.info(f"🚀 Worker '{self.worker_id}': Starting...")

        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        while self.running:
            try:
                # Poll all 3 queues simultaneously
                result = await self.queue_manager.redis_client.brpop(
                    ALL_QUEUES, timeout=5
                )
                if not result:
                    continue

                queue_key, job_json = result
                job = json.loads(job_json)
                queue_key = (
                    queue_key.decode() if isinstance(queue_key, bytes) else queue_key
                )

                logger.info(f"📥 Job {job.get('job_id')} from {queue_key}")

                await self._dispatch(queue_key, job)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info(f"🛑 Worker '{self.worker_id}': Stopped")

    def _handle_shutdown(self, signum, frame):
        logger.info(f"🛑 Shutdown signal received")
        self.running = False

    async def _dispatch(self, queue_key: str, job: dict):
        """Route job to the correct handler based on queue"""
        try:
            await asyncio.wait_for(
                self._dispatch_internal(queue_key, job), timeout=900  # 15 min max
            )
        except asyncio.TimeoutError:
            job_id = job.get("job_id")
            user_id = job.get("user_id")
            logger.error(f"❌ Job {job_id} TIMEOUT")
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                error="Processing timeout after 15 minutes",
                completed_at=datetime.utcnow().isoformat(),
            )
            await self._refund(user_id, "Timeout after 15 minutes")

    async def _dispatch_internal(self, queue_key: str, job: dict):
        if QUEUE_GENERATE in queue_key:
            await self._handle_generate(job)
        elif QUEUE_EXPLAIN in queue_key:
            await self._handle_explain(job)
        elif QUEUE_TRANSFORM in queue_key:
            await self._handle_transform(job)
        else:
            logger.warning(f"⚠️ Unknown queue: {queue_key}")

    # =========================================================================
    # GENERATE CODE
    # =========================================================================

    async def _handle_generate(self, job: dict):
        job_id = job.get("job_id")
        user_id = job.get("user_id")
        project_id = job.get("project_id")
        user_query = job.get("user_query", "")

        try:
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                started_at=datetime.utcnow().isoformat(),
            )

            db = self.db_manager.db
            project = await asyncio.to_thread(
                db.software_lab_projects.find_one, {"project_id": project_id}
            )
            if not project:
                raise Exception(f"Project {project_id} not found")

            # Context files (cloud)
            context_files = []
            if job.get("context_file_ids"):
                cursor = db.software_lab_files.find(
                    {"file_id": {"$in": job["context_file_ids"]}}
                )
                context_files = await asyncio.to_thread(list, cursor)
            elif job.get("include_all_files"):
                cursor = db.software_lab_files.find({"project_id": project_id})
                context_files = await asyncio.to_thread(list, cursor)

            # Context files (local — desktop only): merge after cloud files
            for lf in job.get("context_local_files") or []:
                context_files.append(
                    {
                        "file_id": None,
                        "path": lf.get("path", "local_file"),
                        "language": lf.get("language", "unknown"),
                        "content": lf.get("content", ""),
                    }
                )

            architecture = await asyncio.to_thread(
                db.software_lab_architectures.find_one, {"project_id": project_id}
            )

            system_prompt = self._generate_system_prompt(project, architecture)
            user_prompt = self._generate_user_prompt(user_query, context_files)

            response = await self.glm5.call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=8000,
                temperature=0.3,
            )

            content = response["content"]
            tokens = response["tokens"]
            lines = content.split("\n")
            explanation = lines[0] if lines else ""
            generated_code = "\n".join(lines[1:]).strip() if len(lines) > 1 else content

            suggested_file = self._suggest_file(
                user_query, job.get("target_path"), project
            )

            await asyncio.to_thread(
                db.software_lab_ai_interactions.insert_one,
                {
                    "user_id": user_id,
                    "project_id": project_id,
                    "action": "generate",
                    "user_query": user_query,
                    "context_files": [
                        f["file_id"] for f in context_files if f.get("file_id")
                    ],
                    "ai_response": content,
                    "generated_code": generated_code,
                    "model": response["model"],
                    "tokens_input": tokens["input"],
                    "tokens_output": tokens["output"],
                    "tokens_total": tokens["total"],
                    "created_at": datetime.utcnow(),
                },
            )

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
            logger.info(f"✅ generate job {job_id} done")

        except Exception as e:
            logger.error(f"❌ generate job {job_id} failed: {e}", exc_info=True)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                error=str(e),
                completed_at=datetime.utcnow().isoformat(),
            )
            await self._refund(user_id, f"Code generation failed: {str(e)[:100]}")

    def _generate_system_prompt(
        self, project: dict, architecture: Optional[dict]
    ) -> str:
        prompt = f"""You are an expert software engineer helping students learn to code.

PROJECT: {project.get('name', 'Untitled')}
"""
        if architecture:
            arch_doc = architecture.get("architecture_document", {})
            prompt += f"\nSYSTEM OVERVIEW:\n{arch_doc.get('system_overview', '')}\n"

        prompt += """
YOUR TASK:
Generate clean, well-commented code that:
1. Follows best practices
2. Includes comments explaining WHY, not just WHAT
3. Uses modern syntax and patterns
4. Is educational

OUTPUT FORMAT:
Line 1: Brief explanation (1-2 sentences)
Then: The code (no markdown fences, no backticks)
"""
        return prompt

    def _generate_user_prompt(self, user_query: str, context_files: list) -> str:
        prompt = f"REQUIREMENTS:\n{user_query}\n\n"
        if context_files:
            prompt += "CONTEXT FILES:\n"
            for f in context_files[:5]:
                prompt += f"\n// File: {f.get('path')}\n"
                prompt += f.get("content", "")[:2000] + "\n"
        return prompt

    def _suggest_file(
        self, user_query: str, target_path: Optional[str], project: dict
    ) -> dict:
        if target_path:
            return {"path": target_path, "exists": False}
        q = user_query.lower()
        if "component" in q or "jsx" in q:
            return {"path": "src/components/NewComponent.jsx", "exists": False}
        elif "model" in q or "database" in q:
            return {"path": "backend/models/model.py", "exists": False}
        elif "api" in q or "route" in q:
            return {"path": "backend/routes/routes.py", "exists": False}
        return {"path": "src/utils.js", "exists": False}

    # =========================================================================
    # EXPLAIN CODE
    # =========================================================================

    async def _handle_explain(self, job: dict):
        job_id = job.get("job_id")
        user_id = job.get("user_id")
        project_id = job.get("project_id")
        file_id = job.get("file_id")
        selection = job.get("selection")
        question = job.get("question")

        try:
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                started_at=datetime.utcnow().isoformat(),
            )

            db = self.db_manager.db

            # Resolve file: local (desktop) or cloud (DB lookup)
            local_file_data = job.get("local_file")
            if local_file_data:
                file = {
                    "file_id": None,
                    "path": local_file_data.get("path", "local_file"),
                    "language": local_file_data.get("language", "unknown"),
                    "content": local_file_data.get("content", ""),
                }
                logger.info(
                    f"📂 explain job {job_id}: using local file '{file['path']}'"
                )
            else:
                file = await asyncio.to_thread(
                    db.software_lab_files.find_one, {"file_id": file_id}
                )
                if not file:
                    raise Exception(f"File {file_id} not found")

            architecture = await asyncio.to_thread(
                db.software_lab_architectures.find_one, {"project_id": project_id}
            )

            code_content = file.get("content", "")
            if selection:
                lines = code_content.split("\n")
                start = selection.get("start_line", 1) - 1
                end = selection.get("end_line", len(lines))
                code_content = "\n".join(lines[start:end])

            system_prompt = f"""You are a patient programming tutor explaining code to students.

FILE: {file.get('path')}
LANGUAGE: {file.get('language', 'unknown')}
{f"SYSTEM CONTEXT: {architecture.get('architecture_document', {}).get('system_overview', '')[:200]}" if architecture else ""}

YOUR TASK:
Return the SAME code with INLINE COMMENTS explaining:
1. What each major section does
2. Why certain approaches are used
3. Key concepts and patterns
Add above/inline comments, DO NOT change the code structure.
"""
            user_prompt = f"""CODE TO EXPLAIN:
{code_content}
"""
            if question:
                user_prompt += f"\nSTUDENT'S QUESTION: {question}\n"

            response = await self.glm5.call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=8000,
                temperature=0.3,
            )

            content = response["content"]
            tokens = response["tokens"]

            # Extract annotated code (handle markdown fences if present)
            annotated_code = content
            if "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    block = parts[1]
                    block_lines = block.split("\n")
                    if block_lines and block_lines[0].strip() in [
                        "python",
                        "javascript",
                        "jsx",
                        "js",
                        "py",
                        "typescript",
                        "ts",
                    ]:
                        block_lines = block_lines[1:]
                    annotated_code = "\n".join(block_lines)

            await asyncio.to_thread(
                db.software_lab_ai_interactions.insert_one,
                {
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
                },
            )

            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                file_path=file.get("path"),
                annotated_code=annotated_code,
                explanation="Code explained with inline comments. See annotated code.",
                key_concepts=[],
                code_snippets=[],
                tokens=tokens,
                completed_at=datetime.utcnow().isoformat(),
            )
            logger.info(f"✅ explain job {job_id} done")

        except Exception as e:
            logger.error(f"❌ explain job {job_id} failed: {e}", exc_info=True)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                error=str(e),
                completed_at=datetime.utcnow().isoformat(),
            )
            await self._refund(user_id, f"Code explanation failed: {str(e)[:100]}")

    # =========================================================================
    # TRANSFORM CODE
    # =========================================================================

    async def _handle_transform(self, job: dict):
        job_id = job.get("job_id")
        user_id = job.get("user_id")
        project_id = job.get("project_id")
        file_id = job.get("file_id")
        transformation = job.get("transformation", "refactor")
        instruction = job.get("instruction", "")
        selection = job.get("selection")

        try:
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                started_at=datetime.utcnow().isoformat(),
            )

            db = self.db_manager.db

            # Resolve file: local (desktop) or cloud (DB lookup)
            local_file_data = job.get("local_file")
            if local_file_data:
                file = {
                    "file_id": None,
                    "path": local_file_data.get("path", "local_file"),
                    "language": local_file_data.get("language", "unknown"),
                    "content": local_file_data.get("content", ""),
                }
                logger.info(
                    f"📂 transform job {job_id}: using local file '{file['path']}'"
                )
            else:
                file = await asyncio.to_thread(
                    db.software_lab_files.find_one, {"file_id": file_id}
                )
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
2. Maintain or improve readability
3. Follow best practices
4. Preserve existing functionality unless explicitly changing it
5. Add comments on significant changes

OUTPUT FORMAT:
Line 1: Summary of changes (1-2 sentences)
Then: The transformed code (no markdown fences, no backticks)
"""
            user_prompt = f"""ORIGINAL CODE:
{code_content}

Transform this code: {instruction}
"""

            response = await self.glm5.call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=8000,
                temperature=0.3,
            )

            content = response["content"]
            tokens = response["tokens"]

            lines = content.split("\n")
            changes_summary = lines[0] if lines else ""
            transformed_code = (
                "\n".join(lines[1:]).strip() if len(lines) > 1 else content
            )

            original_lines = code_content.split("\n")
            transformed_lines = transformed_code.split("\n")
            additions = max(0, len(transformed_lines) - len(original_lines))
            deletions = max(0, len(original_lines) - len(transformed_lines))
            diff = {
                "additions": additions,
                "deletions": deletions,
                "preview": f"+{additions} lines, -{deletions} lines",
            }

            await asyncio.to_thread(
                db.software_lab_ai_interactions.insert_one,
                {
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
                },
            )

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
            logger.info(f"✅ transform job {job_id} done")

        except Exception as e:
            logger.error(f"❌ transform job {job_id} failed: {e}", exc_info=True)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=user_id,
                error=str(e),
                completed_at=datetime.utcnow().isoformat(),
            )
            await self._refund(user_id, f"Code transformation failed: {str(e)[:100]}")

    # =========================================================================
    # HELPERS
    # =========================================================================

    async def _refund(self, user_id: Optional[str], reason: str):
        if not user_id:
            return
        try:
            await self.points_service.refund_points(
                user_id=user_id,
                amount=POINTS_COST_AI_CODE,
                reason=reason,
            )
            logger.info(f"💰 Refunded {POINTS_COST_AI_CODE} pts to {user_id}")
        except Exception as e:
            logger.error(f"❌ Refund failed: {e}")

    async def stop(self):
        self.running = False
        await self.queue_manager.disconnect()
        logger.info(f"✅ Worker '{self.worker_id}': Stopped gracefully")


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    worker = AIAssistantGLM5Worker()

    async def main():
        await worker.initialize()
        await worker.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
