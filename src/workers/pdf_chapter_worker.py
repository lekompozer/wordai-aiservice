"""
PDF Chapter Processing Worker

Handles async PDF-to-chapter conversion for large PDF files
to avoid request timeouts.

Flow:
1. API receives PDF upload → enqueue job → return job_id
2. Worker processes: Download PDF → Extract pages → Upload images → Create chapter
3. Update job status in Redis
4. Frontend polls job status

Usage:
    python -m src.workers.pdf_chapter_worker
"""

import os
import sys
import asyncio
import logging
import signal
import time
import tempfile
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Load environment
env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
env_file = "development.env" if env_var == "development" else ".env"
load_dotenv(env_file)

from src.database.db_manager import DBManager
from src.queue.queue_manager import set_job_status, get_job_status
from src.services.pdf_chapter_processor import PDFChapterProcessor
from src.utils.logger import setup_logger
import boto3

logger = setup_logger(__name__)


class PDFChapterWorker:
    """
    Worker for processing PDF-to-chapter conversion jobs
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        redis_url: Optional[str] = None,
        queue_name: str = "pdf_chapter_queue",
        poll_interval: float = 2.0,
    ):
        self.worker_id = worker_id or f"pdf_worker_{int(time.time())}_{os.getpid()}"
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://redis-server:6379"
        )
        self.queue_name = queue_name
        self.poll_interval = poll_interval
        self.running = False

        # Initialize components
        self.db_manager = None
        self.db = None
        self.redis_client = None
        self.s3_client = None
        self.pdf_processor = None

        logger.info(f"🔧 PDF Chapter Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")
        logger.info(f"   📦 Queue: {self.queue_name}")

    async def initialize(self):
        """Initialize worker components"""
        try:
            # Database
            self.db_manager = DBManager()
            self.db = self.db_manager.db
            logger.info("✅ Connected to MongoDB")

            # Redis (async version)
            import redis.asyncio as aioredis

            self.redis_client = aioredis.from_url(
                self.redis_url, decode_responses=True, socket_timeout=10
            )
            await self.redis_client.ping()
            logger.info("✅ Connected to Redis")

            # S3/R2 Client
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=os.getenv("R2_ENDPOINT"),
                aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
                region_name=os.getenv("R2_REGION", "auto"),
            )
            logger.info("✅ Connected to R2 Storage")

            # Cloudflare Images (optional)
            cf_images = None
            try:
                from src.services.cloudflare_images_service import (
                    get_cloudflare_images_service,
                )

                cf_images = get_cloudflare_images_service()
                if cf_images.enabled:
                    logger.info("✅ Cloudflare Images service enabled")
                else:
                    logger.info("ℹ️ Cloudflare Images disabled, using R2 Storage")
            except Exception as e:
                logger.warning(f"⚠️ Cloudflare Images not available: {e}")

            # PDF Processor
            self.pdf_processor = PDFChapterProcessor(
                s3_client=self.s3_client,
                r2_bucket=os.getenv("R2_BUCKET_NAME", "wordai"),
                cdn_base_url=os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro"),
                cloudflare_images_service=cf_images,
            )
            logger.info("✅ PDF Processor initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize worker: {e}")
            raise

    async def process_job(self, job_data: Dict[str, Any]) -> None:
        """
        Process a single PDF chapter creation job

        Job Data:
            - job_id: Unique job ID
            - user_id: User ID
            - book_id: Book ID
            - file_id: PDF file ID from user_files
            - title: Chapter title
            - slug: Optional URL slug
            - order_index: Chapter order
            - parent_id: Optional parent chapter ID
            - is_published: Publish status
            - is_preview_free: Free preview status
        """
        job_id = job_data.get("job_id")
        user_id = job_data.get("user_id")
        book_id = job_data.get("book_id")
        file_id = job_data.get("file_id")

        try:
            logger.info(f"📄 [JOB {job_id}] Processing PDF chapter")
            logger.info(f"   Book: {book_id}, File: {file_id}")

            # Update job status: processing
            await set_job_status(
                redis_client=self.redis_client,
                job_id=job_id,
                status="processing",
                user_id=user_id,
                progress=0,
                message="Starting PDF processing...",
            )

            # 1. Get PDF file from database
            file_doc = self.db.user_files.find_one(
                {"file_id": file_id, "user_id": user_id, "is_deleted": False}
            )
            if not file_doc:
                raise ValueError(f"PDF file not found: {file_id}")

            # Verify file type
            file_type = file_doc.get("file_type", "")
            if (
                not file_type.lower().endswith(".pdf")
                and file_type != "application/pdf"
            ):
                raise ValueError(f"File must be PDF (got: {file_type})")

            # Update progress: 10%
            await set_job_status(
                redis_client=self.redis_client,
                job_id=job_id,
                status="processing",
                progress=10,
                message=f"Downloading PDF: {file_doc.get('filename')}",
            )

            # 2. Download PDF from R2
            r2_key = file_doc.get("r2_key")
            if not r2_key:
                raise ValueError("PDF file has no R2 key")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                temp_pdf_path = tmp_file.name

                file_obj = self.s3_client.get_object(
                    Bucket=os.getenv("R2_BUCKET_NAME", "wordai"), Key=r2_key
                )
                file_content = file_obj["Body"].read()
                tmp_file.write(file_content)

                logger.info(
                    f"✅ Downloaded {len(file_content)} bytes to {temp_pdf_path}"
                )

            try:
                # Update progress: 30%
                await set_job_status(
                    redis_client=self.redis_client,
                    job_id=job_id,
                    status="processing",
                    progress=30,
                    message="Extracting pages from PDF...",
                )

                # 3. Process PDF to pages with progress callback
                chapter_id = str(uuid.uuid4())

                # Progress callback to update job status during batch processing
                async def update_progress(current_page, total_pages):
                    # Map 30-70% progress to page extraction (40% range)
                    progress = 30 + int((current_page / total_pages) * 40)
                    await set_job_status(
                        redis_client=self.redis_client,
                        job_id=job_id,
                        status="processing",
                        progress=progress,
                        message=f"Processed {current_page}/{total_pages} pages...",
                    )

                result = await self.pdf_processor.process_pdf_to_pages(
                    pdf_path=temp_pdf_path,
                    user_id=user_id,
                    chapter_id=chapter_id,
                    dpi=150,  # A4 @ 150 DPI = 1240×1754px
                    batch_size=10,  # Process 10 pages at a time
                    progress_callback=update_progress,
                )

                logger.info(f"✅ PDF processed: {result['total_pages']} pages")

                # Update progress: 70%
                await set_job_status(
                    redis_client=self.redis_client,
                    job_id=job_id,
                    status="processing",
                    progress=70,
                    message=f"Processed {result['total_pages']} pages. Creating chapter...",
                )

                # 4. Create chapter document
                title = job_data.get("title")
                slug = job_data.get("slug")

                # Generate unique slug
                from src.services.book_chapter_manager import BookChapterManager

                chapter_manager = BookChapterManager(self.db_manager)

                base_slug = slug or chapter_manager._generate_slug(title)
                unique_slug = chapter_manager._generate_unique_slug(book_id, base_slug)

                chapter_doc = {
                    "_id": chapter_id,
                    "chapter_id": chapter_id,
                    "book_id": book_id,
                    "user_id": user_id,
                    "title": title,
                    "slug": unique_slug,
                    "order_index": job_data.get("order_index", 0),
                    "parent_id": job_data.get("parent_id"),
                    "depth": 0,  # Calculate if needed
                    "content_mode": "pdf_pages",
                    "pages": result["pages"],
                    "total_pages": result["total_pages"],
                    "source_file_id": file_id,
                    "is_published": job_data.get("is_published", True),
                    "is_preview_free": job_data.get("is_preview_free", False),
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }

                # Insert chapter
                self.db.book_chapters.insert_one(chapter_doc)
                logger.info(f"✅ Created chapter: {chapter_id}")

                # 5. Update book timestamp
                self.db.online_books.update_one(
                    {"book_id": book_id},
                    {"$set": {"updated_at": datetime.utcnow()}},
                )

                # 6. Mark file as used
                self.db.user_files.update_one(
                    {"file_id": file_id},
                    {
                        "$set": {
                            "used_in_chapter": chapter_id,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

                # Update job status: completed
                await set_job_status(
                    redis_client=self.redis_client,
                    job_id=job_id,
                    status="completed",
                    progress=100,
                    message=f"Chapter created successfully with {result['total_pages']} pages",
                    result={
                        "chapter_id": chapter_id,
                        "total_pages": result["total_pages"],
                    },
                )

                logger.info(f"✅ [JOB {job_id}] Completed successfully")

            finally:
                # Cleanup temp file
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
                    logger.info(f"🗑️ Cleaned up temp PDF file")

        except Exception as e:
            logger.error(f"❌ [JOB {job_id}] Failed: {e}", exc_info=True)

            # Update job status: failed
            await set_job_status(
                redis_client=self.redis_client,
                job_id=job_id,
                status="failed",
                error=str(e),
                message=f"PDF processing failed: {str(e)}",
            )

    async def run(self):
        """Main worker loop"""
        self.running = True
        logger.info(f"🚀 Worker {self.worker_id} started")

        try:
            await self.initialize()

            while self.running:
                try:
                    # Get job from Redis queue (blocking pop with timeout)
                    result = await self.redis_client.brpop(
                        self.queue_name, timeout=self.poll_interval
                    )

                    if result:
                        queue_name, job_json = result
                        job_data = eval(job_json)  # Convert string to dict

                        logger.info(f"📥 Got job: {job_data.get('job_id')}")
                        await self.process_job(job_data)

                except KeyboardInterrupt:
                    logger.info("⚠️ Received shutdown signal")
                    break
                except Exception as e:
                    logger.error(f"❌ Worker error: {e}", exc_info=True)
                    await asyncio.sleep(1)

        finally:
            logger.info(f"🛑 Worker {self.worker_id} stopped")

    def stop(self):
        """Stop worker gracefully"""
        logger.info("🛑 Stopping worker...")
        self.running = False


async def main():
    """Main entry point"""
    worker = PDFChapterWorker()

    # Handle signals
    loop = asyncio.get_event_loop()

    def signal_handler(sig, frame):
        logger.info(f"⚠️ Received signal {sig}")
        worker.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker.run()
    except Exception as e:
        logger.error(f"❌ Worker crashed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
