"""
Video Studio Worker
Processes async jobs from the video_studio Redis queue.

Handles task_type:
  generate_story      — brief → story structure (deepseek-reasoner, 120s)
  generate_narration  — story + brief → narration (deepseek-reasoner, 120s)
  generate_script     — brief + narration → N scenes (deepseek-reasoner, 200s)
  generate_image      — image_prompt → image file → R2
  tts                 — scene_text + narrator → audio file → R2
"""

import os
import sys
import asyncio
import logging
import signal
import time
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
env_file = "development.env" if env_var == "development" else ".env"
load_dotenv(env_file)

from src.queue.queue_manager import QueueManager, set_job_status
from src.models.ai_queue_tasks import VideoStudioTask
from src.utils.logger import setup_logger

logger = setup_logger()

# Timeout per job type (seconds)
JOB_TIMEOUT = {
    "generate_story": 150,
    "generate_narration": 150,
    "generate_script": 240,
    "generate_image": 120,
    "tts": 90,
}

# Narrator → edge-tts voice mapping
NARRATOR_MAP = {
    "Hà Nữ": "vi-VN-HoaiMyNeural",
    "Nam": "vi-VN-NamMinhNeural",
    "Glen": "en-US-GuyNeural",
    "Sara": "en-US-SaraNeural",
}
DEFAULT_NARRATOR_VOICE = "vi-VN-HoaiMyNeural"


class VideoStudioWorker:
    """Worker that processes Video Studio tasks from Redis queue"""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        redis_url: Optional[str] = None,
        max_concurrent_jobs: int = 3,
    ):
        self.worker_id = (
            worker_id or f"video_studio_worker_{int(time.time())}_{os.getpid()}"
        )
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://redis-server:6379"
        )
        self.max_concurrent_jobs = max_concurrent_jobs
        self.running = False

        self.queue_manager = QueueManager(
            redis_url=self.redis_url,
            queue_name="video_studio",
        )

        # Lazy-init service
        self._video_svc = None

        logger.info(f"🔧 Video Studio Worker {self.worker_id} initialized")

    def _get_service(self):
        if self._video_svc is None:
            from src.services.video_generation_service import (
                get_video_generation_service,
            )

            self._video_svc = get_video_generation_service()
        return self._video_svc

    async def initialize(self):
        await self.queue_manager.connect()
        logger.info(f"✅ Video Studio Worker: Connected to Redis queue 'video_studio'")

    async def shutdown(self):
        logger.info(f"🛑 {self.worker_id}: Shutting down...")
        self.running = False
        await self.queue_manager.disconnect()
        logger.info(f"✅ {self.worker_id}: Shutdown complete")

    # ── Handlers ──────────────────────────────────────────────────────────

    async def _handle_generate_story(self, task: VideoStudioTask) -> None:
        svc = self._get_service()
        brief = task.brief or {}

        story = await svc.generate_story_from_brief(brief)

        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=task.job_id,
            status="completed",
            user_id=task.user_id,
            project_id=task.project_id,
            title=story.get("title", ""),
            hook=story.get("hook", ""),
            beats=story.get("beats", []),
            tone=story.get("tone", ""),
            pacing=story.get("pacing", ""),
            completed_at=datetime.utcnow().isoformat(),
        )

    async def _handle_generate_narration(self, task: VideoStudioTask) -> None:
        svc = self._get_service()
        story = task.story or {}
        brief = task.brief or {}

        result = await svc.generate_narration_from_story(story, brief)

        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=task.job_id,
            status="completed",
            user_id=task.user_id,
            project_id=task.project_id,
            suggested_title=result.get("suggestedTitle", ""),
            narration=result.get("narration", ""),
            hook_strength_score=result.get("hookStrengthScore", 0),
            completed_at=datetime.utcnow().isoformat(),
        )

    async def _handle_generate_script(self, task: VideoStudioTask) -> None:
        svc = self._get_service()
        brief = task.brief or {}
        n_scenes = task.n_scenes or 5

        result = await svc.generate_script_from_brief(brief, n_scenes)

        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=task.job_id,
            status="completed",
            user_id=task.user_id,
            project_id=task.project_id,
            title=result.get("title", ""),
            style_anchor=result.get("style_anchor", ""),
            mood=result.get("mood", ""),
            scenes=result.get("scenes", []),
            completed_at=datetime.utcnow().isoformat(),
        )

    async def _handle_generate_image(self, task: VideoStudioTask) -> None:
        svc = self._get_service()
        model_hint = (task.model_hint or "gemini").lower()

        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)

            if model_hint == "xai":
                image_path = await svc.generate_scene_image_xai(
                    prompt=task.image_prompt or "",
                    scene_index=task.scene_index or 0,
                    task_dir=task_dir,
                )
            else:
                image_path = await svc.generate_scene_image(
                    prompt=task.image_prompt or "",
                    scene_index=task.scene_index or 0,
                    task_dir=task_dir,
                )

            # Upload to R2
            r2_key = f"video-studio/{task.user_id}/{task.project_id}/scene_{task.scene_index:02d}_img.png"
            cdn_url = await svc.upload_asset_to_r2(
                local_path=image_path,
                r2_key=r2_key,
                content_type="image/png",
            )

        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=task.job_id,
            status="completed",
            user_id=task.user_id,
            project_id=task.project_id,
            scene_index=task.scene_index,
            image_url=cdn_url,
            completed_at=datetime.utcnow().isoformat(),
        )

    async def _handle_tts(self, task: VideoStudioTask) -> None:
        svc = self._get_service()
        narrator_key = task.narrator or "Hà Nữ"
        edge_voice = NARRATOR_MAP.get(narrator_key, DEFAULT_NARRATOR_VOICE)
        language = task.language or "vi"

        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)

            audio_path = await svc.generate_scene_audio(
                text=task.scene_text or "",
                scene_index=task.scene_index or 0,
                task_dir=task_dir,
                tts_provider="edge",
                edge_voice=edge_voice,
            )

            # Read duration via soundfile
            duration_seconds = 0.0
            try:
                import soundfile as sf  # type: ignore[import-untyped]

                info = sf.info(str(audio_path))
                duration_seconds = round(info.duration, 2)
            except Exception:
                pass

            # Upload to R2
            r2_key = f"video-studio/{task.user_id}/{task.project_id}/scene_{task.scene_index:02d}_audio.wav"
            cdn_url = await svc.upload_asset_to_r2(
                local_path=audio_path,
                r2_key=r2_key,
                content_type="audio/wav",
            )

        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=task.job_id,
            status="completed",
            user_id=task.user_id,
            project_id=task.project_id,
            scene_index=task.scene_index,
            audio_url=cdn_url,
            duration_seconds=duration_seconds,
            completed_at=datetime.utcnow().isoformat(),
        )

    # ── Process task ───────────────────────────────────────────────────────

    async def process_task(self, task: VideoStudioTask) -> bool:
        job_id = task.job_id
        task_type = task.task_type

        logger.info(f"⚙️  Processing [{task_type}] job={job_id} user={task.user_id}")

        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=job_id,
            status="processing",
            user_id=task.user_id,
            task_type=task_type,
            project_id=task.project_id,
            started_at=datetime.utcnow().isoformat(),
        )

        try:
            dispatch = {
                "generate_story": self._handle_generate_story,
                "generate_narration": self._handle_generate_narration,
                "generate_script": self._handle_generate_script,
                "generate_image": self._handle_generate_image,
                "tts": self._handle_tts,
            }
            handler = dispatch.get(task_type)
            if not handler:
                raise ValueError(f"Unknown task_type: {task_type!r}")

            await handler(task)
            logger.info(f"✅ [{task_type}] job={job_id} completed")
            return True

        except Exception as e:
            logger.error(f"❌ [{task_type}] job={job_id} failed: {e}", exc_info=True)
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=task.user_id,
                task_type=task_type,
                error=str(e),
                failed_at=datetime.utcnow().isoformat(),
            )
            return False

    # ── Main run loop ──────────────────────────────────────────────────────

    async def run(self):
        self.running = True
        logger.info(
            f"🚀 {self.worker_id} started (max_concurrent={self.max_concurrent_jobs})"
        )
        running_tasks = set()

        while self.running:
            try:
                while len(running_tasks) < self.max_concurrent_jobs and self.running:
                    task_dict = await self.queue_manager.dequeue_generic_task(
                        worker_id=self.worker_id, timeout=1
                    )
                    if not task_dict:
                        break

                    try:
                        task = VideoStudioTask(**task_dict)
                    except Exception as parse_err:
                        logger.error(f"❌ Failed to parse task: {parse_err}")
                        continue

                    timeout_secs = JOB_TIMEOUT.get(task.task_type, 180)
                    logger.info(
                        f"📥 Dequeued [{task.task_type}] job={task.job_id} timeout={timeout_secs}s"
                    )

                    async def run_with_timeout(t=task, timeout=timeout_secs):
                        try:
                            await asyncio.wait_for(
                                self.process_task(t), timeout=timeout
                            )
                        except asyncio.TimeoutError:
                            logger.error(
                                f"⏱️ [{t.task_type}] job={t.job_id} TIMEOUT after {timeout}s"
                            )
                            await set_job_status(
                                redis_client=self.queue_manager.redis_client,
                                job_id=t.job_id,
                                status="failed",
                                user_id=t.user_id,
                                error=f"Timeout after {timeout}s",
                            )

                    task_future = asyncio.create_task(run_with_timeout())
                    running_tasks.add(task_future)

                if running_tasks:
                    done, running_tasks = await asyncio.wait(
                        running_tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for completed in done:
                        try:
                            await completed
                        except Exception as e:
                            logger.error(f"❌ Task raised: {e}", exc_info=True)
                else:
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(5)

        if running_tasks:
            logger.info(f"⏳ Waiting for {len(running_tasks)} remaining tasks...")
            await asyncio.gather(*running_tasks, return_exceptions=True)

        logger.info(f"✅ {self.worker_id} stopped")


async def main():
    worker = VideoStudioWorker()

    def signal_handler(sig, frame):
        logger.info(f"🛑 Received signal {sig}, shutting down...")
        asyncio.create_task(worker.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await worker.initialize()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
