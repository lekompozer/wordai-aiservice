"""
Slide Narration Combined Worker
Runs both Audio and Subtitle generation concurrently in a single process.
Saves ~512 MB RAM vs running two separate containers.

Queues handled:
  - slide_narration_audio    → SlideNarrationAudioWorker
  - slide_narration_subtitle → SlideNarrationSubtitleWorker
"""

import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
load_dotenv("development.env" if env_var == "development" else ".env")

from src.utils.logger import setup_logger
from src.workers.slide_narration_audio_worker import SlideNarrationAudioWorker
from src.workers.slide_narration_subtitle_worker import SlideNarrationSubtitleWorker

logger = setup_logger()


async def main():
    """Start audio + subtitle workers concurrently in the same process."""

    audio_worker = SlideNarrationAudioWorker(
        worker_id="narration_audio_combined",
        redis_url=os.getenv("REDIS_URL", "redis://redis-server:6379"),
    )
    subtitle_worker = SlideNarrationSubtitleWorker(
        worker_id="narration_subtitle_combined",
        redis_url=os.getenv("REDIS_URL", "redis://redis-server:6379"),
    )

    shutdown_event = asyncio.Event()

    def _signal_handler(sig, frame):
        logger.info(f"⚠️  Received signal {sig}, shutting down both workers…")
        shutdown_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info("🚀 Slide Narration Combined Worker starting (audio + subtitle)…")

    async def run_audio():
        try:
            await audio_worker.initialize()
            await audio_worker.run()
        except Exception as exc:
            logger.error(f"❌ Audio worker crashed: {exc}", exc_info=True)
        finally:
            await audio_worker.shutdown()

    async def run_subtitle():
        try:
            await subtitle_worker.initialize()
            await subtitle_worker.run()
        except Exception as exc:
            logger.error(f"❌ Subtitle worker crashed: {exc}", exc_info=True)
        finally:
            await subtitle_worker.shutdown()

    async def watch_shutdown():
        await shutdown_event.wait()
        audio_worker.running = False
        subtitle_worker.running = False

    await asyncio.gather(
        run_audio(),
        run_subtitle(),
        watch_shutdown(),
        return_exceptions=True,
    )

    logger.info("✅ Slide Narration Combined Worker stopped.")


if __name__ == "__main__":
    asyncio.run(main())
