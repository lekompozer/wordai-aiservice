"""
Scaffold Project Worker
Generates project files from architecture using Gemini 3 Pro
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


class ScaffoldProjectWorker:
    """Worker for scaffolding project files from architecture"""

    def __init__(
        self,
        worker_id: str = "scaffold_project_worker",
        redis_url: str = "redis://redis-server:6379",
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.running = False

        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="software_lab_scaffold_project"
        )
        self.vertex_ai = get_vertex_ai_service()
        self.points_service = get_points_service()
        self.db_manager = DBManager()

        logger.info(f"🔧 Scaffold Project Worker {self.worker_id} initialized")

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
                    reason="Scaffold project timeout",
                )
            except Exception as e:
                logger.error(f"❌ Refund failed: {e}")
            return False

    async def _process_task_internal(self, job: dict):
        """Internal processing logic"""
        job_id = job.get("job_id")
        user_id = job.get("user_id")
        project_id = job.get("project_id")
        architecture_id = job.get("architecture_id")
        include_comments = job.get("include_comments", True)
        file_types = job.get("file_types")

        try:
            logger.info(f"⚙️ Processing scaffold project job {job_id}")

            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                started_at=datetime.utcnow().isoformat(),
            )

            db = self.db_manager.db

            # Get architecture
            architecture = await asyncio.to_thread(
                db.software_lab_architectures.find_one,
                {"architecture_id": architecture_id},
            )
            if not architecture:
                raise Exception(f"Architecture {architecture_id} not found")

            arch_doc = architecture.get("architecture_document", {})
            folder_structure = arch_doc.get("folder_structure", {})

            # Get file list from folder structure
            backend_files = folder_structure.get("backend", [])
            frontend_files = folder_structure.get("frontend", [])
            shared_files = folder_structure.get("shared", [])

            all_files = backend_files + frontend_files + shared_files

            # Filter by file types if specified
            if file_types:
                all_files = [
                    f
                    for f in all_files
                    if any(f.endswith(f".{ext}") for ext in file_types)
                ]

            logger.info(f"📋 Scaffolding {len(all_files)} files...")

            files_created = []
            folders_created = set()

            # Process files in batches to avoid token limits
            batch_size = 5
            for i in range(0, len(all_files), batch_size):
                batch = all_files[i : i + batch_size]
                logger.info(f"🔄 Processing batch {i//batch_size + 1}: {batch}")

                # Generate files using Gemini
                generated_files = await self._generate_files_batch(
                    arch_doc, batch, include_comments
                )

                # Save files to MongoDB
                for file_data in generated_files:
                    file_path = file_data["path"]
                    content = file_data["content"]
                    language = file_data["language"]

                    # Extract folder path
                    folder_path = "/".join(file_path.split("/")[:-1])
                    if folder_path:
                        folders_created.add(folder_path)

                    # Create file record
                    file_id = f"file_{uuid.uuid4().hex[:12]}"
                    file_record = {
                        "file_id": file_id,
                        "project_id": project_id,
                        "user_id": user_id,
                        "path": file_path,
                        "content": content,
                        "language": language,
                        "size": len(content.encode("utf-8")),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }

                    # Insert or update
                    await asyncio.to_thread(
                        db.software_lab_files.update_one,
                        {"project_id": project_id, "path": file_path},
                        {"$set": file_record},
                        True,  # upsert
                    )

                    files_created.append(
                        {
                            "path": file_path,
                            "content": content,
                            "language": language,
                            "size_bytes": len(content.encode("utf-8")),
                            "file_id": file_id,
                        }
                    )

                logger.info(
                    f"✅ Batch {i//batch_size + 1} completed: {len(generated_files)} files"
                )

            # Update architecture record
            await asyncio.to_thread(
                db.software_lab_architectures.update_one,
                {"architecture_id": architecture_id},
                {
                    "$set": {
                        "scaffolded": True,
                        "scaffolded_at": datetime.utcnow(),
                    }
                },
            )

            # Calculate summary
            languages = {}
            for f in files_created:
                lang = f["language"]
                languages[lang] = languages.get(lang, 0) + 1

            summary = {
                "total_files": len(files_created),
                "total_folders": len(folders_created),
                "languages": languages,
            }

            # Update job status
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=user_id,
                files_created=files_created,
                folders_created=list(folders_created),
                summary=summary,
                completed_at=datetime.utcnow().isoformat(),
            )

            logger.info(
                f"✅ Job {job_id} completed - Created {len(files_created)} files"
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
                    reason=f"Project scaffolding failed: {str(e)[:100]}",
                )
                logger.info(
                    f"💰 Refunded {POINTS_COST_AI_CODE} points to user {user_id}"
                )
            except Exception as refund_error:
                logger.error(f"❌ Failed to refund points: {refund_error}")

    async def _generate_files_batch(
        self, arch_doc: dict, file_paths: list, include_comments: bool
    ) -> list:
        """Generate file contents for a batch of files"""

        # Build prompt
        prompt = f"""You are a programming instructor creating starter code for students.

ARCHITECTURE DOCUMENT:
{json.dumps(arch_doc, indent=2)[:5000]}

YOUR TASK:
Generate template files with educational comments for these paths:
{json.dumps(file_paths, indent=2)}

For each file:
- Include comprehensive header comment explaining purpose
- Add TODO comments for student implementation
- Provide code templates with clear placeholders
- Include educational comments explaining concepts
- Reference related files
- Suggest learning resources

{'IMPORTANT: Add detailed comments and TODOs' if include_comments else 'Minimal comments only'}

Output JSON array of objects with: path, content, language
"""

        # Call Gemini for code generation
        response_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "language": {"type": "string"},
                },
                "required": ["path", "content", "language"],
            },
        }

        response = await self.vertex_ai.call_gemini(
            prompt=prompt,
            max_tokens=32000,
            temperature=0.7,
            response_schema=response_schema,
        )

        return response["content"]  # Already parsed JSON array

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

    worker = ScaffoldProjectWorker()

    async def main():
        await worker.initialize()
        await worker.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
