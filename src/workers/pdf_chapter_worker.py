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
        max_concurrent_jobs: int = 3,  # Process up to 3 PDFs simultaneously
    ):
        self.worker_id = worker_id or f"pdf_worker_{int(time.time())}_{os.getpid()}"
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://redis-server:6379"
        )
        self.queue_name = queue_name
        self.poll_interval = poll_interval
        self.max_concurrent_jobs = max_concurrent_jobs
        self.running = False
        self.active_jobs: set = set()  # Track active job_ids for concurrency control

        # Initialize components
        self.db_manager = None
        self.db = None
        self.redis_client = None
        self.s3_client = None
        self.pdf_processor = None

        logger.info(f"🔧 PDF Chapter Worker {self.worker_id} initialized")
        logger.info(f"   📡 Redis: {self.redis_url}")
        logger.info(f"   📦 Queue: {self.queue_name}")
        logger.info(f"   🔄 Max concurrent jobs: {self.max_concurrent_jobs}")

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

            # Log system resources at start
            try:
                import psutil

                process = psutil.Process()
                mem_info = process.memory_info()
                logger.info(
                    f"🧠 [JOB {job_id}] Initial memory: {mem_info.rss / 1024 / 1024:.1f} MB"
                )
            except Exception as e:
                logger.warning(f"Could not get memory info: {e}")

            # Update job status: processing (MongoDB)
            self.db.pdf_chapter_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "processing",
                        "user_id": user_id,
                        "progress": 0,
                        "message": "Starting PDF processing...",
                        "updated_at": datetime.utcnow(),
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow(),
                    },
                },
                upsert=True,
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

            # Get content mode from job data (default: pdf_pages)
            content_mode = job_data.get("content_mode", "pdf_pages")
            logger.info(f"📄 Content mode: {content_mode}")

            # 2. Download PDF from R2 (only for pdf_pages mode)
            temp_pdf_path = None
            if content_mode == "pdf_pages":
                # Update progress: 10% (MongoDB)
                self.db.pdf_chapter_jobs.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "status": "processing",
                            "progress": 10,
                            "message": f"Downloading PDF: {file_doc.get('filename')}",
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

                r2_key = file_doc.get("r2_key")
                if not r2_key:
                    raise ValueError("PDF file has no R2 key")

                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".pdf"
                ) as tmp_file:
                    temp_pdf_path = tmp_file.name

                    file_obj = self.s3_client.get_object(
                        Bucket=os.getenv("R2_BUCKET_NAME", "wordai"), Key=r2_key
                    )
                    file_content = file_obj["Body"].read()
                    tmp_file.write(file_content)

                    logger.info(
                        f"✅ Downloaded {len(file_content)} bytes to {temp_pdf_path}"
                    )
            else:
                # pdf_file mode: Skip download
                logger.info(f"⏭️ Skipping download for pdf_file mode")

                # Update progress: 10% (MongoDB)
                self.db.pdf_chapter_jobs.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "status": "processing",
                            "progress": 10,
                            "message": "Using original PDF file...",
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

            try:
                # Update progress: 30% (MongoDB)
                self.db.pdf_chapter_jobs.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "status": "processing",
                            "progress": 30,
                            "message": (
                                "Processing PDF..."
                                if content_mode == "pdf_file"
                                else "Extracting pages from PDF..."
                            ),
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

                # 3. Process based on content mode
                chapter_id = str(uuid.uuid4())

                if content_mode == "pdf_file":
                    # Mode 1: Keep original PDF (no conversion)
                    # Get public URL directly from file_doc
                    public_url = file_doc.get("public_url")
                    if not public_url:
                        # Fallback: construct URL from R2
                        r2_key = file_doc.get("r2_key")
                        public_url = f"{os.getenv('R2_PUBLIC_URL', 'https://static.wordai.pro')}/{r2_key}"

                    logger.info(f"✅ Using original PDF: {public_url}")

                    # Get file size (already uploaded)
                    file_size = file_doc.get("file_size", 0)

                    result = {
                        "pdf_url": public_url,
                        "file_size": file_size,
                        "content_mode": "pdf_file",
                    }

                    # Update progress to 70%
                    self.db.pdf_chapter_jobs.update_one(
                        {"job_id": job_id},
                        {
                            "$set": {
                                "status": "processing",
                                "progress": 70,
                                "message": "PDF ready. Creating chapter...",
                                "updated_at": datetime.utcnow(),
                            }
                        },
                    )

                else:
                    # Mode 2: Convert to images (existing logic)
                    # Progress callback to update job status during batch processing
                    async def update_progress(current_page, total_pages):
                        # Map 30-70% progress to page extraction (40% range)
                        progress = 30 + int((current_page / total_pages) * 40)
                        self.db.pdf_chapter_jobs.update_one(
                            {"job_id": job_id},
                            {
                                "$set": {
                                    "status": "processing",
                                    "progress": progress,
                                    "message": f"Processed {current_page}/{total_pages} pages...",
                                    "updated_at": datetime.utcnow(),
                                }
                            },
                        )

                    result = await self.pdf_processor.process_pdf_to_pages(
                        pdf_path=temp_pdf_path,
                        user_id=user_id,
                        chapter_id=chapter_id,
                        dpi=150,  # A4 @ 150 DPI = 1240×1754px
                        batch_size=10,  # Process 10 pages at a time
                        progress_callback=update_progress,
                    )

                logger.info(
                    f"✅ PDF processed: {result.get('total_pages', 'N/A')} pages"
                )

                # Update progress: 70% (MongoDB)
                self.db.pdf_chapter_jobs.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "status": "processing",
                            "progress": 70,
                            "message": f"Processed {result.get('total_pages', 'PDF file')}. Creating chapter...",
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

                # 4. Create chapter document
                title = job_data.get("title")
                slug = job_data.get("slug")

                # Generate unique slug
                from src.services.book_chapter_manager import (
                    GuideBookBookChapterManager,
                )

                chapter_manager = GuideBookBookChapterManager(self.db)

                base_slug = slug or chapter_manager._generate_slug(title)
                unique_slug = chapter_manager._generate_unique_slug(book_id, base_slug)

                # Build chapter document based on content mode
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
                    "content_mode": content_mode,
                    "source_file_id": file_id,
                    "is_published": job_data.get("is_published", True),
                    "is_preview_free": job_data.get("is_preview_free", False),
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }

                # Add mode-specific fields
                if content_mode == "pdf_file":
                    chapter_doc.update(
                        {
                            "pdf_url": result["pdf_url"],
                            "file_size": result["file_size"],
                        }
                    )
                else:
                    chapter_doc.update(
                        {
                            "pages": result["pages"],
                            "total_pages": result["total_pages"],
                        }
                    )

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

                # Update job status: completed (MongoDB)
                success_message = (
                    f"Chapter created with {result['total_pages']} pages"
                    if content_mode == "pdf_pages"
                    else "Chapter created with original PDF file"
                )

                job_result = {
                    "chapter_id": chapter_id,
                }
                if content_mode == "pdf_pages":
                    job_result["total_pages"] = result["total_pages"]
                else:
                    job_result["pdf_url"] = result["pdf_url"]
                    job_result["file_size"] = result["file_size"]

                self.db.pdf_chapter_jobs.update_one(
                    {"job_id": job_id},
                    {
                        "$set": {
                            "status": "completed",
                            "progress": 100,
                            "message": success_message,
                            "result": job_result,
                            "updated_at": datetime.utcnow(),
                            "completed_at": datetime.utcnow(),
                        }
                    },
                )

                logger.info(f"✅ [JOB {job_id}] Completed successfully")

                # Log final memory usage
                try:
                    import psutil

                    process = psutil.Process()
                    mem_info = process.memory_info()
                    logger.info(
                        f"🧠 [JOB {job_id}] Final memory: {mem_info.rss / 1024 / 1024:.1f} MB"
                    )
                except Exception:
                    pass

            finally:
                # Cleanup temp file if downloaded
                if temp_pdf_path and os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
                    logger.info(f"🗑️ Cleaned up temp PDF file")

        except MemoryError as e:
            logger.error(f"💥 [JOB {job_id}] OUT OF MEMORY: {e}", exc_info=True)

            # Update job status: failed (MongoDB)
            self.db.pdf_chapter_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": f"Out of memory: {str(e)}",
                        "message": f"PDF processing failed: Out of memory. Try splitting the PDF into smaller files.",
                        "updated_at": datetime.utcnow(),
                        "failed_at": datetime.utcnow(),
                    }
                },
            )

            # Force exit to trigger worker restart with clean memory
            logger.critical(f"💀 [JOB {job_id}] Worker exiting due to memory error")
            import sys

            sys.exit(1)

        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"❌ [JOB {job_id}] Failed ({error_type}): {e}", exc_info=True)

            # Update job status: failed (MongoDB)
            self.db.pdf_chapter_jobs.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": str(e),
                        "message": f"PDF processing failed: {str(e)}",
                        "updated_at": datetime.utcnow(),
                        "failed_at": datetime.utcnow(),
                    }
                },
            )

    async def run(self):
        """Main worker loop with concurrent job processing"""
        self.running = True
        logger.info(f"🚀 Worker {self.worker_id} started")
        logger.info(f"   🔄 Max concurrent jobs: {self.max_concurrent_jobs}")

        try:
            await self.initialize()

            while self.running:
                try:
                    # Wait if we're at max concurrent jobs
                    while len(self.active_jobs) >= self.max_concurrent_jobs:
                        await asyncio.sleep(0.5)  # Check every 500ms
                        # Clean up completed tasks
                        self.active_jobs = {
                            job_id
                            for job_id in self.active_jobs
                            if job_id in self.active_jobs
                        }

                    # Get job from Redis queue (non-blocking with timeout)
                    result = await self.redis_client.brpop(
                        self.queue_name, timeout=self.poll_interval
                    )

                    if result:
                        queue_name, job_json = result
                        job_data = eval(job_json)  # Convert string to dict
                        job_id = job_data.get("job_id")

                        logger.info(
                            f"📥 Got job: {job_id} (active: {len(self.active_jobs)}/{self.max_concurrent_jobs})"
                        )

                        # Add to active jobs
                        self.active_jobs.add(job_id)

                        # Process job in background (non-blocking)
                        async def process_and_cleanup(job_data):
                            try:
                                await self.process_job(job_data)
                            finally:
                                # Remove from active jobs when done
                                job_id = job_data.get("job_id")
                                self.active_jobs.discard(job_id)
                                logger.info(
                                    f"✅ Job {job_id} completed. Active jobs: {len(self.active_jobs)}/{self.max_concurrent_jobs}"
                                )

                        # Create background task (don't await)
                        asyncio.create_task(process_and_cleanup(job_data))

                except KeyboardInterrupt:
                    logger.info("⚠️ Received shutdown signal")
                    break
                except Exception as e:
                    logger.error(f"❌ Worker error: {e}", exc_info=True)
                    await asyncio.sleep(1)

        finally:
            # Wait for active jobs to complete
            if self.active_jobs:
                logger.info(
                    f"⏳ Waiting for {len(self.active_jobs)} active jobs to complete..."
                )
                while self.active_jobs:
                    await asyncio.sleep(1)

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
