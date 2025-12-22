"""
Chapter Translation Worker
Processes chapter translation tasks from Redis queue
"""

import asyncio
import logging
import os
import signal
import uuid
import re
from datetime import datetime
from typing import Optional

from src.queue.queue_manager import QueueManager
from src.models.ai_queue_tasks import ChapterTranslationTask
from src.services.online_test_utils import get_mongodb_service
from src.services.ai_chat_service import ai_chat_service, AIProvider

logger = logging.getLogger("chatbot")


def slugify(text: str) -> str:
    """Convert Vietnamese text to URL-friendly slug"""
    vietnamese_map = {
        "à": "a",
        "á": "a",
        "ạ": "a",
        "ả": "a",
        "ã": "a",
        "â": "a",
        "ầ": "a",
        "ấ": "a",
        "ậ": "a",
        "ẩ": "a",
        "ẫ": "a",
        "ă": "a",
        "ằ": "a",
        "ắ": "a",
        "ặ": "a",
        "ẳ": "a",
        "ẵ": "a",
        "è": "e",
        "é": "e",
        "ẹ": "e",
        "ẻ": "e",
        "ẽ": "e",
        "ê": "e",
        "ề": "e",
        "ế": "e",
        "ệ": "e",
        "ể": "e",
        "ễ": "e",
        "ì": "i",
        "í": "i",
        "ị": "i",
        "ỉ": "i",
        "ĩ": "i",
        "ò": "o",
        "ó": "o",
        "ọ": "o",
        "ỏ": "o",
        "õ": "o",
        "ô": "o",
        "ồ": "o",
        "ố": "o",
        "ộ": "o",
        "ổ": "o",
        "ỗ": "o",
        "ơ": "o",
        "ờ": "o",
        "ớ": "o",
        "ợ": "o",
        "ở": "o",
        "ỡ": "o",
        "ù": "u",
        "ú": "u",
        "ụ": "u",
        "ủ": "u",
        "ũ": "u",
        "ư": "u",
        "ừ": "u",
        "ứ": "u",
        "ự": "u",
        "ử": "u",
        "ữ": "u",
        "ỳ": "y",
        "ý": "y",
        "ỵ": "y",
        "ỷ": "y",
        "ỹ": "y",
        "đ": "d",
        "À": "A",
        "Á": "A",
        "Ạ": "A",
        "Ả": "A",
        "Ã": "A",
        "Â": "A",
        "Ầ": "A",
        "Ấ": "A",
        "Ậ": "A",
        "Ẩ": "A",
        "Ẫ": "A",
        "Ă": "A",
        "Ằ": "A",
        "Ắ": "A",
        "Ặ": "A",
        "Ẳ": "A",
        "Ẵ": "A",
        "È": "E",
        "É": "E",
        "Ẹ": "E",
        "Ẻ": "E",
        "Ẽ": "E",
        "Ê": "E",
        "Ề": "E",
        "Ế": "E",
        "Ệ": "E",
        "Ể": "E",
        "Ễ": "E",
        "Ì": "I",
        "Í": "I",
        "Ị": "I",
        "Ỉ": "I",
        "Ĩ": "I",
        "Ò": "O",
        "Ó": "O",
        "Ọ": "O",
        "Ỏ": "O",
        "Õ": "O",
        "Ô": "O",
        "Ồ": "O",
        "Ố": "O",
        "Ộ": "O",
        "Ổ": "O",
        "Ỗ": "O",
        "Ơ": "O",
        "Ờ": "O",
        "Ớ": "O",
        "Ợ": "O",
        "Ở": "O",
        "Ỡ": "O",
        "Ù": "U",
        "Ú": "U",
        "Ụ": "U",
        "Ủ": "U",
        "Ũ": "U",
        "Ư": "U",
        "Ừ": "U",
        "Ứ": "U",
        "Ự": "U",
        "Ử": "U",
        "Ữ": "U",
        "Ỳ": "Y",
        "Ý": "Y",
        "Ỵ": "Y",
        "Ỷ": "Y",
        "Ỹ": "Y",
        "Đ": "D",
    }
    for vn_char, en_char in vietnamese_map.items():
        text = text.replace(vn_char, en_char)
    text = text.lower()
    text = re.sub(r"[^\w\s-:]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")[:100]


class ChapterTranslationWorker:
    """Worker for processing chapter translation tasks"""

    def __init__(
        self,
        worker_id: str = "chapter_translation_worker",
        redis_url: str = "redis://redis-server:6379",
    ):
        self.worker_id = worker_id
        self.redis_url = redis_url
        self.running = False

        # Initialize components
        self.queue_manager = QueueManager(
            redis_url=self.redis_url, queue_name="chapter_translation"
        )
        self.mongo = get_mongodb_service()
        self.jobs_collection = self.mongo.db["chapter_translation_jobs"]
        self.db = self.mongo.db

        logger.info(f"🔧 Chapter Translation Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            await self.queue_manager.connect()
            logger.info(
                f"✅ Worker {self.worker_id}: Connected to Redis chapter_translation queue"
            )
        except Exception as e:
            logger.error(f"❌ Worker {self.worker_id}: Initialization failed: {e}")
            raise

    async def shutdown(self):
        """Gracefully shutdown worker"""
        logger.info(f"🛑 Worker {self.worker_id}: Shutting down...")
        self.running = False

        if self.queue_manager:
            await self.queue_manager.disconnect()
            logger.info(f"✅ Worker {self.worker_id}: Queue disconnected")

    async def process_task(self, task: ChapterTranslationTask) -> bool:
        """
        Process chapter translation task

        Args:
            task: ChapterTranslationTask from Redis queue

        Returns:
            bool: True if processing successful
        """
        job_id = task.job_id
        start_time = datetime.utcnow()

        try:
            logger.info(
                f"⚙️ Processing chapter translation job {job_id} "
                f"({task.source_language} -> {task.target_language})"
            )

            # Create job in MongoDB (upsert)
            self.jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$setOnInsert": {
                        "job_id": job_id,
                        "user_id": task.user_id,
                        "book_id": task.book_id,
                        "chapter_id": task.chapter_id,
                        "source_language": task.source_language,
                        "target_language": task.target_language,
                        "create_new_chapter": task.create_new_chapter,
                        "created_at": start_time,
                    },
                    "$set": {
                        "status": "processing",
                        "started_at": start_time,
                    },
                },
                upsert=True,
            )

            # AI Translation
            prompt = f"""You are a professional translator. Translate the following HTML content from {task.source_language} to {task.target_language}.

**CRITICAL RULES:**
1. ONLY return the translated HTML content
2. DO NOT translate HTML tags, attributes, CSS classes, or inline styles
3. Preserve the exact HTML structure
4. Translate ONLY the text content inside tags
5. Keep all formatting, links, and images intact

**Original HTML:**
{task.content_html}

**Return only the translated HTML (no explanations, no markdown):**"""

            messages = [
                {
                    "role": "system",
                    "content": f"You are a professional translator specializing in {task.target_language}. You only return clean translated HTML.",
                },
                {"role": "user", "content": prompt},
            ]

            # Call AI (Gemini Pro)
            translated_html = await ai_chat_service.chat(
                provider=AIProvider.GEMINI_PRO,
                messages=messages,
                temperature=0.3,
                max_tokens=16000,
            )

            translated_html = translated_html.strip()

            # Create new chapter if requested
            new_chapter_id = None
            new_chapter_title = None
            new_chapter_slug = None

            if task.create_new_chapter:
                chapter = self.db.book_chapters.find_one(
                    {"chapter_id": task.chapter_id}
                )

                if chapter:
                    # Generate unique title
                    suffix = (
                        task.new_chapter_title_suffix
                        or f" ({task.target_language[:2].upper()})"
                    )
                    attempt = 0
                    while True:
                        if attempt == 0:
                            test_title = f"{chapter['title']}{suffix}"
                        else:
                            test_title = f"{chapter['title']}{suffix}_{attempt}"

                        existing = self.db.book_chapters.find_one(
                            {"book_id": task.book_id, "title": test_title}
                        )
                        if not existing:
                            new_chapter_title = test_title
                            break
                        attempt += 1

                    # Generate unique slug
                    base_slug = slugify(new_chapter_title)
                    slug_attempt = 0
                    while True:
                        if slug_attempt == 0:
                            test_slug = base_slug
                        else:
                            test_slug = f"{base_slug}-{slug_attempt}"

                        existing_slug = self.db.book_chapters.find_one(
                            {"book_id": task.book_id, "slug": test_slug}
                        )
                        if not existing_slug:
                            new_chapter_slug = test_slug
                            break
                        slug_attempt += 1

                    # Create new chapter
                    new_chapter_id = f"chapter_{uuid.uuid4().hex[:12]}"
                    now = datetime.utcnow()

                    new_chapter = {
                        "chapter_id": new_chapter_id,
                        "book_id": task.book_id,
                        "parent_id": chapter.get("parent_id"),
                        "title": new_chapter_title,
                        "slug": new_chapter_slug,
                        "order_index": chapter.get("order_index", 0) + 1,
                        "depth": chapter.get("depth", 0),
                        "content_source": "inline",
                        "document_id": None,
                        "content_html": translated_html,
                        "content_json": None,
                        "is_published": True,
                        "is_preview_free": chapter.get("is_preview_free", False),
                        "created_at": now,
                        "updated_at": now,
                    }

                    self.db.book_chapters.insert_one(new_chapter)
                    logger.info(
                        f"✅ Created new chapter: {new_chapter_id} ('{new_chapter_title}')"
                    )

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            # Update status to completed
            self.jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "completed",
                        "translated_html": translated_html,
                        "new_chapter_id": new_chapter_id,
                        "new_chapter_title": new_chapter_title,
                        "new_chapter_slug": new_chapter_slug,
                        "completed_at": end_time,
                        "processing_time_seconds": processing_time,
                    }
                },
            )

            logger.info(f"✅ Job {job_id} completed in {processing_time:.1f}s")

            return True

        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)

            # Update status to failed
            self.jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": str(e),
                        "completed_at": datetime.utcnow(),
                    }
                },
            )

            return False

    async def run(self):
        """Main worker loop"""
        await self.initialize()
        self.running = True

        logger.info(f"🚀 Worker {self.worker_id}: Started processing tasks")

        while self.running:
            try:
                # Fetch task from Redis queue
                task_data = await self.queue_manager.dequeue_task(
                    worker_id=self.worker_id, timeout=5
                )

                if not task_data:
                    continue

                # Parse task
                try:
                    task = ChapterTranslationTask(**task_data)
                except Exception as parse_error:
                    logger.error(f"❌ Failed to parse task: {parse_error}")
                    continue

                # Process task
                success = await self.process_task(task)

                if not success:
                    logger.warning(f"⚠️ Task {task.task_id} processing failed")

            except asyncio.CancelledError:
                logger.info(f"🛑 Worker {self.worker_id}: Cancelled")
                break
            except Exception as e:
                logger.error(
                    f"❌ Worker {self.worker_id}: Error in main loop: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(5)

        logger.info(f"🏁 Worker {self.worker_id}: Stopped")


async def main():
    """Main entry point for worker"""
    worker = ChapterTranslationWorker(
        worker_id=os.getenv("WORKER_ID", "chapter_translation_worker_1"),
        redis_url=os.getenv("REDIS_URL", "redis://redis-server:6379"),
    )

    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info(f"📡 Received signal {sig}, shutting down...")
        asyncio.create_task(worker.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker.run()
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
