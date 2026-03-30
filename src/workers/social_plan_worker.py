"""
Social Plan Worker
Consumes queue:social_plan_jobs and runs the full plan generation pipeline:
  Phase 1: Brand Extraction (Playwright crawl)
  Phase 2: TikTok Data Parsing
  Phase 3: Brand DNA Generation (ChatGPT gpt-5.4)
  Phase 4: Plan Structure (ChatGPT gpt-5.4)
  Phase 5: Content Generation per Post (DeepSeek)
"""

import asyncio
import json
import logging
import os
import signal
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

from src.database.db_manager import DBManager
from src.queue.queue_manager import set_job_status
from src.services.brand_crawler import crawl_brand_urls, merge_brand_data
from src.services.tiktok_parser import parse_tiktok_export, extract_tiktok_insights
from src.services.social_plan_service import SocialPlanService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

QUEUE_KEY = "queue:social_plan_jobs"
POLL_TIMEOUT = 5


class SocialPlanWorker:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        self.redis: aioredis.Redis = None
        self.db = DBManager().db
        self.running = False
        self.plan_service = SocialPlanService()

    async def start(self):
        logger.info("🚀 Social Plan Worker starting...")

        self.redis = aioredis.from_url(
            self.redis_url, encoding="utf-8", decode_responses=True
        )
        self.running = True

        # Graceful shutdown handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._stop)

        logger.info(f"👂 Listening on {QUEUE_KEY}")

        while self.running:
            try:
                result = await self.redis.brpop(QUEUE_KEY, timeout=POLL_TIMEOUT)
                if result is None:
                    continue

                _, payload = result
                job = json.loads(payload)
                await self._process_job(job)

            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(2)

        logger.info("Social Plan Worker stopped.")

    def _stop(self):
        logger.info("Shutdown signal received")
        self.running = False

    async def _process_job(self, job: dict):
        job_id = job.get("job_id")
        plan_id = job.get("plan_id")
        user_id = job.get("user_id") or ""

        if not job_id or not plan_id:
            logger.error(f"Invalid job payload: {job}")
            return

        logger.info(f"📋 Processing plan job: {job_id} | plan: {plan_id}")

        try:
            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                plan_id=plan_id,
                step="starting",
                progress=5,
                message="Bắt đầu xử lý...",
            )

            config = job.get("config", {})
            brand_asset_ids = job.get("brand_asset_ids", [])
            tiktok_data = job.get("tiktok_data")  # {"bytes_b64": ..., "file_type": ...}

            # ── Phase 1: Brand Extraction ──────────────────────────
            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                step="brand_extraction",
                progress=10,
                message=f"Đang crawl {len(config.get('website_urls', []))} websites...",
            )

            website_urls = config.get("website_urls", [])
            crawl_results = []
            if website_urls:
                try:
                    crawl_results = await crawl_brand_urls(website_urls)
                except Exception as e:
                    logger.warning(f"Crawl failed (non-fatal): {e}")

            brand_data = merge_brand_data(crawl_results)

            # ── Phase 2: TikTok Parsing ─────────────────────────────
            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                step="tiktok_analysis",
                progress=25,
                message="Đang phân tích dữ liệu TikTok...",
            )

            tiktok_posts = []
            if tiktok_data:
                try:
                    import base64

                    raw_bytes = base64.b64decode(tiktok_data["bytes_b64"])
                    tiktok_posts = parse_tiktok_export(
                        raw_bytes, tiktok_data["file_type"]
                    )
                except Exception as e:
                    logger.warning(f"TikTok parsing failed (non-fatal): {e}")

            tiktok_insights = extract_tiktok_insights(tiktok_posts)

            # Save raw data to MongoDB
            self.db["social_plans"].update_one(
                {"plan_id": plan_id},
                {
                    "$set": {
                        "brand_data.websites": brand_data.get("websites", []),
                        "brand_data.tiktok_posts": tiktok_posts[:50],
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            # ── Phase 3: Brand DNA ──────────────────────────────────
            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                step="brand_dna",
                progress=40,
                message="Đang tạo Brand DNA...",
            )

            brand_dna = await self.plan_service.generate_brand_dna(
                brand_data, tiktok_insights, config
            )

            # Merge primary_color from crawl data if brand_dna lacks it
            if brand_data.get("primary_color") and not brand_dna.get("colors", {}).get(
                "primary"
            ):
                brand_dna.setdefault("colors", {})["primary"] = brand_data[
                    "primary_color"
                ]

            self.db["social_plans"].update_one(
                {"plan_id": plan_id},
                {
                    "$set": {
                        "brand_dna": brand_dna,
                        "status": "brand_dna_ready",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            # ── Phase 4: Plan Structure ─────────────────────────────
            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                step="plan_structure",
                progress=60,
                message="Đang tạo cấu trúc kế hoạch 30 ngày...",
            )

            posts = await self.plan_service.generate_plan_structure(brand_dna, config)

            self.db["social_plans"].update_one(
                {"plan_id": plan_id},
                {
                    "$set": {
                        "posts": posts,
                        "total_posts": len(posts),
                        "status": "plan_ready",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            # ── Phase 5: Content Generation per Post ───────────────
            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                step="content_generation",
                progress=75,
                message=f"Đang viết nội dung cho {len(posts)} posts...",
            )

            posts_with_content = await self.plan_service.generate_all_content(
                brand_dna, posts, config
            )

            self.db["social_plans"].update_one(
                {"plan_id": plan_id},
                {
                    "$set": {
                        "posts": posts_with_content,
                        "status": "content_ready",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            # ── Done ────────────────────────────────────────────────
            await set_job_status(
                self.redis,
                job_id,
                "completed",
                user_id=user_id,
                plan_id=plan_id,
                step="done",
                progress=100,
                message="Kế hoạch đã sẵn sàng!",
            )

            logger.info(f"✅ Plan {plan_id} completed successfully")

        except Exception as e:
            logger.error(f"❌ Plan job {job_id} failed: {e}", exc_info=True)

            try:
                self.db["social_plans"].update_one(
                    {"plan_id": plan_id},
                    {
                        "$set": {
                            "status": "failed",
                            "error": str(e),
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )
                await set_job_status(
                    self.redis,
                    job_id,
                    "failed",
                    user_id=user_id,
                    plan_id=plan_id,
                    step="failed",
                    progress=0,
                    message=f"Lỗi: {str(e)[:200]}",
                )
            except Exception as inner_e:
                logger.error(f"Failed to update error status: {inner_e}")


if __name__ == "__main__":
    worker = SocialPlanWorker()
    asyncio.run(worker.start())
