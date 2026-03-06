"""
Book Processing Combined Worker
Runs Chapter Translation and PDF Chapter workers concurrently in a single process.
Saves ~512 MB RAM vs running two separate containers.

Queues handled:
  - chapter_translation  → ChapterTranslationWorker
  - pdf_chapter_queue    → PDFChapterWorker
"""

import asyncio
import logging
import os
import signal

from dotenv import load_dotenv

env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
load_dotenv("development.env" if env_var == "development" else ".env")

from src.utils.logger import setup_logger
from src.workers.chapter_translation_worker import ChapterTranslationWorker
from src.workers.pdf_chapter_worker import PDFChapterWorker

logger = setup_logger()


async def main():
    """Start chapter-translation + pdf-chapter workers concurrently in the same process."""

    redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")

    translation_worker = ChapterTranslationWorker(
        worker_id="chapter_translation_combined",
        redis_url=redis_url,
    )
    pdf_worker = PDFChapterWorker(
        worker_id="pdf_chapter_combined",
        redis_url=redis_url,
    )

    shutdown_event = asyncio.Event()

    def _signal_handler(sig, frame):
        logger.info(f"⚠️  Received signal {sig}, shutting down both workers…")
        shutdown_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info(
        "🚀 Book Processing Combined Worker starting (chapter-translation + pdf-chapter)…"
    )

    async def run_translation():
        try:
            await translation_worker.run()
        except Exception as exc:
            logger.error(f"❌ Chapter Translation worker crashed: {exc}", exc_info=True)
        finally:
            await translation_worker.shutdown()

    async def run_pdf():
        try:
            await pdf_worker.run()
        except Exception as exc:
            logger.error(f"❌ PDF Chapter worker crashed: {exc}", exc_info=True)

    async def watch_shutdown():
        await shutdown_event.wait()
        # Signal both workers to stop
        translation_worker.running = False
        pdf_worker.stop()

    await asyncio.gather(
        run_translation(),
        run_pdf(),
        watch_shutdown(),
        return_exceptions=True,
    )

    logger.info("✅ Book Processing Combined Worker stopped.")


if __name__ == "__main__":
    asyncio.run(main())
