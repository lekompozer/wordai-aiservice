"""
Analyze Architecture Worker
Processes architecture generation tasks using Gemini 3 Pro
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


class AnalyzeArchitectureWorker:
    """Worker for processing architecture analysis tasks using Gemini 3 Pro"""

    def __init__(
        self,
        worker_id: str = "analyze_architecture_worker",
        redis_url: str = "redis://redis-server:6379",
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.running = False

        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="software_lab_analyze_architecture"
        )
        self.vertex_ai = get_vertex_ai_service()
        self.points_service = get_points_service()
        self.db_manager = DBManager()

        logger.info(f"🔧 Analyze Architecture Worker {self.worker_id} initialized")

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
                    reason="Architecture analysis timeout",
                )
            except Exception as e:
                logger.error(f"❌ Refund failed: {e}")
            return False

    async def _process_task_internal(self, job: dict):
        """Internal processing logic"""
        job_id = job.get("job_id")
        user_id = job.get("user_id")
        project_id = job.get("project_id")
        requirements = job.get("requirements")
        tech_stack = job.get("tech_stack", {})

        try:
            logger.info(f"⚙️ Processing architecture analysis job {job_id}")

            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                started_at=datetime.utcnow().isoformat(),
            )

            # Build prompt for Gemini
            prompt = self._build_architecture_prompt(requirements, tech_stack)

            # Define JSON schema for structured output
            response_schema = self._get_architecture_schema()

            # Call Gemini 3 Pro via Vertex AI
            response = await self.vertex_ai.call_gemini(
                prompt=prompt,
                max_tokens=32000,
                temperature=0.7,
                response_schema=response_schema,
            )

            architecture_doc = response["content"]  # Already parsed JSON
            tokens = response["tokens"]

            # Generate architecture ID
            import uuid

            architecture_id = f"arch_{uuid.uuid4().hex[:12]}"

            # Save to MongoDB
            db = self.db_manager.db
            architecture_record = {
                "architecture_id": architecture_id,
                "user_id": user_id,
                "project_id": project_id,
                "requirements": requirements,
                "tech_stack_preferences": tech_stack,
                "architecture_document": architecture_doc,
                "model": response["model"],
                "tokens_input": tokens["input"],
                "tokens_output": tokens["output"],
                "tokens_total": tokens["total"],
                "used_as_context_count": 0,
                "scaffolded": False,
                "scaffolded_at": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            await db.software_lab_architectures.insert_one(architecture_record)

            # Update job status
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                architecture_id=architecture_id,
                architecture=architecture_doc,
                tokens=tokens,
                completed_at=datetime.utcnow().isoformat(),
            )

            logger.info(
                f"✅ Job {job_id} completed - Architecture {architecture_id} created"
            )

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
                    reason=f"Architecture analysis failed: {str(e)[:100]}",
                )
                logger.info(
                    f"💰 Refunded {POINTS_COST_AI_CODE} points to user {user_id}"
                )
            except Exception as refund_error:
                logger.error(f"❌ Failed to refund points: {refund_error}")

    def _build_architecture_prompt(self, requirements: str, tech_stack: dict) -> str:
        """Build prompt for architecture generation"""
        backend = tech_stack.get("backend", ["Python", "FastAPI"])
        frontend = tech_stack.get("frontend", ["React"])
        database = tech_stack.get("database", ["SQLite"])

        prompt = f"""You are a senior software architect helping students plan their projects.

STUDENT REQUIREMENTS:
{requirements}

TECH STACK CONSTRAINTS:
- Backend: {', '.join(backend)}
- Frontend: {', '.join(frontend)}
- Database: {', '.join(database)}

YOUR TASK:
Create a comprehensive system architecture document in JSON format with:

1. SYSTEM OVERVIEW (3-5 paragraphs explaining what the system does, architecture type, technologies, scalability)

2. FEATURES LIST (break requirements into specific features with priority: high/medium/low and complexity: low/medium/high)

3. USER FLOWS (map out key user journeys with step-by-step actions)

4. DATABASE SCHEMA (design SQLite tables with columns, types, and constraints)

5. FOLDER STRUCTURE (organize backend and frontend code files)

6. IMPLEMENTATION PHASES (break into 3-5 phases with tasks and time estimates)

PRINCIPLES:
- Keep it simple for students
- Use proven patterns
- Prioritize maintainability
- Include educational value

Output valid JSON matching the schema.
"""

        return prompt

    def _get_architecture_schema(self) -> dict:
        """Get JSON schema for Gemini structured output"""
        return {
            "type": "object",
            "properties": {
                "system_overview": {"type": "string"},
                "features_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                            },
                            "complexity": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                        },
                        "required": ["name", "description", "priority", "complexity"],
                    },
                },
                "user_flows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "steps": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["name", "steps"],
                    },
                },
                "database_schema": {
                    "type": "object",
                    "properties": {
                        "tables": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "columns": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "name": {"type": "string"},
                                                "type": {"type": "string"},
                                                "constraints": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                            "required": ["name", "type"],
                                        },
                                    },
                                },
                                "required": ["name", "columns"],
                            },
                        }
                    },
                    "required": ["tables"],
                },
                "folder_structure": {
                    "type": "object",
                    "properties": {
                        "backend": {"type": "array", "items": {"type": "string"}},
                        "frontend": {"type": "array", "items": {"type": "string"}},
                        "shared": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["backend", "frontend"],
                },
                "implementation_phases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "phase": {"type": "integer"},
                            "name": {"type": "string"},
                            "tasks": {"type": "array", "items": {"type": "string"}},
                            "estimated_hours": {"type": "integer"},
                        },
                        "required": ["phase", "name", "tasks", "estimated_hours"],
                    },
                },
            },
            "required": [
                "system_overview",
                "features_list",
                "user_flows",
                "database_schema",
                "folder_structure",
                "implementation_phases",
            ],
        }

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

    worker = AnalyzeArchitectureWorker()

    async def main():
        await worker.initialize()
        await worker.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
