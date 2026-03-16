"""
Video Generation Worker — Final Render Step

Consumes from Redis queue `queue:video_generation`.

For each job:
1. Load task from MongoDB (step2 image URLs + step3 audio URLs)
2. Download assets from R2 public URLs to temp dir
3. Render HTML frames via Playwright (image + text_overlay)
4. Encode each segment via FFmpeg (frame PNG + audio WAV → MP4)
5. Concat all segments → final.mp4
6. Upload final.mp4 to R2
7. Update MongoDB task status → completed
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Load env
from dotenv import load_dotenv

env_var = os.getenv("ENVIRONMENT", "production")
load_dotenv(".env" if env_var != "development" else "development.env")

import redis.asyncio as aioredis

from src.database.db_manager import DBManager
from src.services.video_generation_service import VideoGenerationService
from src.utils.logger import setup_logger

logger = setup_logger()

QUEUE_KEY = "queue:video_generation"
POLL_TIMEOUT = 5  # seconds for BRPOP timeout
MAX_RETRIES = 2


# ─────────────────────────────────────────────
# Worker class
# ─────────────────────────────────────────────


class VideoGenerationWorker:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        self.redis: aioredis.Redis = None
        self.db = DBManager().db
        self.svc = VideoGenerationService()
        self.running = False

    async def start(self):
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
        self.running = True
        logger.info(f"🎬 VideoGenerationWorker started — listening on {QUEUE_KEY}")

        while self.running:
            try:
                result = await self.redis.brpop(QUEUE_KEY, timeout=POLL_TIMEOUT)
                if result is None:
                    continue

                _, payload = result
                job = json.loads(payload)
                task_id = job.get("task_id")
                user_id = job.get("user_id")

                if not task_id or not user_id:
                    logger.warning(f"Invalid job payload: {payload[:200]}")
                    continue

                logger.info(f"[{task_id[:8]}] Render job received")
                await self._process_render(task_id, user_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(2)

        await self.redis.aclose()
        logger.info("VideoGenerationWorker stopped")

    async def stop(self):
        self.running = False

    # ─────────────────────────────────────────────

    async def _process_render(self, task_id: str, user_id: str):
        task = self.db.video_tasks.find_one({"task_id": task_id, "user_id": user_id})
        if not task:
            logger.error(f"[{task_id[:8]}] Task not found in DB")
            return

        if task.get("status") not in ("rendering",):
            logger.warning(
                f"[{task_id[:8]}] Unexpected status '{task.get('status')}', skipping"
            )
            return

        task_dir = Path(tempfile.mkdtemp(prefix=f"video_render_{task_id}_"))
        logger.info(f"[{task_id[:8]}] Render dir: {task_dir}")

        try:
            step1 = task.get("step1", {})
            step2 = task.get("step2", [])
            step3 = task.get("step3", [])
            video_title = step1.get("title", "WordAI Video")
            scenes = step1.get("scenes", [])
            n_scenes = len(scenes)

            # Validate all images/audio are ready
            for i in range(n_scenes):
                img = step2[i] if i < len(step2) else {}
                aud = step3[i] if i < len(step3) else {}
                if img.get("status") != "done":
                    raise ValueError(
                        f"Scene {i} image not ready (status: {img.get('status')})"
                    )
                if aud.get("status") != "done":
                    raise ValueError(
                        f"Scene {i} audio not ready (status: {aud.get('status')})"
                    )

            # ── Download images and audio ──────────────────────────────────
            logger.info(f"[{task_id[:8]}] Downloading {n_scenes} images + audio...")
            import httpx

            async with httpx.AsyncClient(timeout=60.0) as client:
                for i in range(n_scenes):
                    img_url = step2[i]["image_url"]
                    aud_url = step3[i]["audio_url"]

                    img_resp = await client.get(img_url)
                    img_resp.raise_for_status()
                    img_path = task_dir / f"scene_{i:02d}_image.png"
                    img_path.write_bytes(img_resp.content)

                    aud_resp = await client.get(aud_url)
                    aud_resp.raise_for_status()
                    aud_path = task_dir / f"scene_{i:02d}_audio.wav"
                    aud_path.write_bytes(aud_resp.content)

            # ── Render frames ──────────────────────────────────────────────
            logger.info(
                f"[{task_id[:8]}] Rendering {n_scenes} frames via Playwright..."
            )
            frame_paths = []
            for i, scene in enumerate(scenes):
                fp = await self.svc.render_frame(
                    image_path=task_dir / f"scene_{i:02d}_image.png",
                    text_overlay=scene.get("text_overlay", ""),
                    scene_index=i,
                    total_scenes=n_scenes,
                    video_title=video_title,
                    task_dir=task_dir,
                )
                frame_paths.append(fp)

            # ── Encode segments (Ken Burns motion effect) ──────────────────
            logger.info(
                f"[{task_id[:8]}] Encoding {n_scenes} Ken Burns segments via FFmpeg..."
            )
            segments = []
            for i in range(n_scenes):
                seg = self.svc.create_video_segment_ken_burns(
                    frame_path=frame_paths[i],
                    audio_path=task_dir / f"scene_{i:02d}_audio.wav",
                    scene_index=i,
                    task_dir=task_dir,
                )
                segments.append(seg)

            # ── Concat ────────────────────────────────────────────────────
            logger.info(f"[{task_id[:8]}] Concatenating segments...")
            final_path = self.svc.concat_segments(segments, task_dir)

            # ── Upload to R2 ───────────────────────────────────────────────
            logger.info(f"[{task_id[:8]}] Uploading final video to R2...")
            video_url = await self.svc.upload_to_r2(final_path, task_id, user_id)

            # ── Mark completed ─────────────────────────────────────────────
            self.db.video_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": "completed",
                        "final_video_url": video_url,
                        "render_error": None,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            logger.info(f"✅ [{task_id[:8]}] Render complete: {video_url}")

        except Exception as e:
            logger.error(f"❌ [{task_id[:8]}] Render failed: {e}", exc_info=True)
            self.db.video_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "status": "failed",
                        "render_error": str(e)[:500],
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
        finally:
            shutil.rmtree(task_dir, ignore_errors=True)


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────


async def main():
    worker = VideoGenerationWorker()

    import signal

    loop = asyncio.get_event_loop()

    def shutdown(sig, frame):
        logger.info(f"Signal {sig} received — stopping worker...")
        asyncio.ensure_future(worker.stop())

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
