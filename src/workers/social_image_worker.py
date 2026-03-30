"""
Social Image Worker
Consumes queue:social_image_jobs and generates images for social plan posts.
Saves images to R2 and updates MongoDB + user's Image Library.
"""

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone

import aioredis

from src.database.db_manager import DBManager
from src.queue.queue_manager import set_job_status
from src.services.social_image_service import SocialImageService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

QUEUE_KEY = "queue:social_image_jobs"
POLL_TIMEOUT = 5


class SocialImageWorker:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        self.redis: aioredis.Redis = None
        self.db = DBManager().db
        self.running = False
        self.image_service = SocialImageService()

    async def start(self):
        logger.info("🚀 Social Image Worker starting...")

        self.redis = aioredis.from_url(
            self.redis_url, encoding="utf-8", decode_responses=True
        )
        self.running = True

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

        logger.info("Social Image Worker stopped.")

    def _stop(self):
        logger.info("Shutdown signal received")
        self.running = False

    async def _process_job(self, job: dict):
        job_id = job.get("job_id") or ""
        plan_id = job.get("plan_id") or ""
        post_id = job.get("post_id") or ""
        user_id = job.get("user_id") or ""

        if not job_id or not plan_id or not post_id:
            logger.error(f"Invalid image job payload: {job}")
            return

        logger.info(f"🎨 Processing image job: {job_id} | post: {post_id}")

        try:
            await set_job_status(
                self.redis, job_id, "processing",
                user_id=user_id,
                plan_id=plan_id,
                post_id=post_id,
                step="loading_assets",
                message="Đang tải brand assets...",
            )

            # Load plan data from MongoDB
            plan = self.db["social_plans"].find_one({"plan_id": plan_id})
            if not plan:
                raise ValueError(f"Plan {plan_id} not found")

            # Find the specific post
            post = next(
                (p for p in plan.get("posts", []) if p["post_id"] == post_id),
                None,
            )
            if not post:
                raise ValueError(f"Post {post_id} not found in plan {plan_id}")

            brand_dna = plan.get("brand_dna", {})
            image_style = plan.get("config", {}).get("image_style", "flat-design")

            # Load brand assets
            asset_ids = plan.get("asset_ids", [])
            assets_doc = self.db["social_plan_assets"].find_one(
                {"$or": [
                    {"plan_id": plan_id},
                    {"plan_draft_id": {"$in": asset_ids}},
                    {"asset_id": {"$in": asset_ids}},
                ]}
            )
            assets = []
            if assets_doc:
                assets = assets_doc.get("assets", [])

            # Generate image
            await set_job_status(
                self.redis, job_id, "processing",
                user_id=user_id,
                step="generating_image",
                message="Đang tạo ảnh với Gemini...",
            )

            result = await self.image_service.generate_post_image(
                plan_id=plan_id,
                post_id=post_id,
                post=post,
                brand_dna=brand_dna,
                assets=assets,
                image_style=image_style,
                user_id=user_id,
                db=self.db,
            )

            image_url = result["image_url"]
            now = datetime.now(timezone.utc)

            # Update MongoDB: social_plans.posts[].image_url
            self.db["social_plans"].update_one(
                {"plan_id": plan_id, "posts.post_id": post_id},
                {"$set": {
                    "posts.$.image_url": image_url,
                    "posts.$.image_job_id": job_id,
                    "posts.$.image_generated_at": now,
                    "updated_at": now,
                }},
            )

            # Increment images_generated counter
            self.db["social_plans"].update_one(
                {"plan_id": plan_id},
                {"$inc": {"images_generated": 1}},
            )

            await set_job_status(
                self.redis, job_id, "completed",
                user_id=user_id,
                plan_id=plan_id,
                post_id=post_id,
                image_url=image_url,
                step="done",
                message="Ảnh đã được tạo thành công!",
            )

            logger.info(f"✅ Image generated for post {post_id}: {image_url}")

        except Exception as e:
            logger.error(f"❌ Image job {job_id} failed: {e}", exc_info=True)

            try:
                await set_job_status(
                    self.redis, job_id, "failed",
                    user_id=user_id,
                    plan_id=plan_id,
                    post_id=post_id,
                    step="failed",
                    message=f"Lỗi tạo ảnh: {str(e)[:200]}",
                )
                # Update post to clear pending state
                self.db["social_plans"].update_one(
                    {"plan_id": plan_id, "posts.post_id": post_id},
                    {"$set": {
                        "posts.$.image_job_id": None,
                        "updated_at": datetime.now(timezone.utc),
                    }},
                )
            except Exception as inner_e:
                logger.error(f"Failed to update error status: {inner_e}")


if __name__ == "__main__":
    worker = SocialImageWorker()
    asyncio.run(worker.start())
