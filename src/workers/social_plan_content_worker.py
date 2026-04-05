"""
Social Plan Content Worker
Consumes queue:social_plan_content_jobs and generates content for one day at a time.

Each job payload:
  {
    "task_type": "content_day",
    "job_id": "...",
    "plan_id": "...",
    "user_id": "...",
    "day_number": 1,          # which day of the plan (1-30)
    "batch_job_id": "...",    # shared ID for batch tracking (optional)
    "campaign_name": "...",   # for notification message
    "user_email": "...",      # for email notification
    "total_days_in_batch": 30 # how many days were enqueued in total (for completion check)
  }

Behavior per job:
  1. Fetch plan + posts for this day_number
  2. Skip day if ALL posts already have hook != None (resume capability)
  3. Generate content for each post using DeepSeek (1 call per post)
  4. Save each post result immediately to MongoDB
  5. Increment plan.content_generated
  6. If batch_job_id: check if all days in batch are done → notify (in-app + email)
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
from src.services.social_plan_service import SocialPlanService
from src.services.notification_manager import NotificationManager
from src.services.brevo_email_service import get_brevo_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

QUEUE_KEY = "queue:social_plan_content_jobs"
POLL_TIMEOUT = 5


class SocialPlanContentWorker:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
        self.redis: aioredis.Redis = None
        self.db = DBManager().db
        self.running = False
        self.plan_service = SocialPlanService()

    async def _reconnect(self):
        """Reconnect Redis after connection loss."""
        try:
            await self.redis.aclose()
        except Exception:
            pass
        await asyncio.sleep(2)
        self.redis = aioredis.from_url(
            self.redis_url, encoding="utf-8", decode_responses=True
        )
        logger.info("🔄 Redis reconnected")

    async def start(self):
        logger.info("🚀 Social Plan Content Worker starting...")

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

            except (
                aioredis.exceptions.ResponseError,
                aioredis.exceptions.ConnectionError,
            ) as e:
                logger.warning(f"Redis connection issue, reconnecting: {e}")
                await self._reconnect()
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(2)

        logger.info("Social Plan Content Worker stopped.")

    def _stop(self):
        logger.info("Shutdown signal received")
        self.running = False

    async def _process_job(self, job: dict):
        job_id = job.get("job_id")
        plan_id = job.get("plan_id")
        user_id = job.get("user_id")
        day_number = job.get("day_number")
        batch_job_id = job.get("batch_job_id")
        campaign_name = job.get("campaign_name", "Chiến dịch")
        user_email = job.get("user_email", "")
        total_days_in_batch = job.get("total_days_in_batch", 0)

        if not plan_id or not user_id or day_number is None:
            logger.error(f"Invalid job payload: {job}")
            return

        logger.info(f"📅 Processing day {day_number} for plan {plan_id} (job={job_id})")

        try:
            plan = self.db["social_plans"].find_one(
                {"plan_id": plan_id, "user_id": user_id},
                {
                    "posts": 1,
                    "brand_dna": 1,
                    "config": 1,
                    "content_generated": 1,
                    "content_quota": 1,
                },
            )
            if not plan:
                logger.warning(f"Plan {plan_id} not found, skipping job {job_id}")
                return

            all_posts = plan.get("posts", [])
            day_posts = [p for p in all_posts if p.get("day") == day_number]

            if not day_posts:
                logger.info(f"No posts for day {day_number}, skipping")
                await self._check_batch_completion(
                    plan_id,
                    user_id,
                    batch_job_id,
                    total_days_in_batch,
                    campaign_name,
                    user_email,
                )
                return

            # Resume: skip if all posts for this day already have content
            if all(p.get("hook") for p in day_posts):
                logger.info(f"Day {day_number} already fully generated, skipping")
                await self._check_batch_completion(
                    plan_id,
                    user_id,
                    batch_job_id,
                    total_days_in_batch,
                    campaign_name,
                    user_email,
                )
                return

            brand_dna = plan.get("brand_dna", {})
            config = plan.get("config", {})
            succeeded = 0

            for post in day_posts:
                if post.get("hook"):
                    # This specific post already has content, skip
                    continue
                try:
                    content = await self.plan_service.generate_post_content(
                        brand_dna, post, config
                    )
                    now = datetime.now(timezone.utc)
                    self.db["social_plans"].update_one(
                        {"plan_id": plan_id, "posts.post_id": post["post_id"]},
                        {
                            "$set": {
                                "posts.$.hook": content["hook"],
                                "posts.$.caption": content["caption"],
                                "posts.$.hashtags": content["hashtags"],
                                "posts.$.image_prompt": content["image_prompt"],
                                "posts.$.cta": content["cta"],
                                "updated_at": now,
                            }
                        },
                    )
                    succeeded += 1
                    logger.info(
                        f"✅ Generated content for post {post['post_id']} (day {day_number})"
                    )
                except Exception as e:
                    logger.error(
                        f"Content gen failed for post {post.get('post_id')}: {e}"
                    )

            # Increment content_generated counter atomically
            if succeeded > 0:
                self.db["social_plans"].update_one(
                    {"plan_id": plan_id},
                    {
                        "$inc": {"content_generated": succeeded},
                        "$set": {"updated_at": datetime.now(timezone.utc)},
                    },
                )

            logger.info(
                f"✅ Day {day_number}: {succeeded}/{len(day_posts)} posts generated"
            )

            # Check if entire batch is complete
            if batch_job_id:
                await self._check_batch_completion(
                    plan_id,
                    user_id,
                    batch_job_id,
                    total_days_in_batch,
                    campaign_name,
                    user_email,
                )

        except Exception as e:
            logger.error(
                f"Failed to process day {day_number} job {job_id}: {e}", exc_info=True
            )

    async def _check_batch_completion(
        self,
        plan_id: str,
        user_id: str,
        batch_job_id: str,
        total_days_in_batch: int,
        campaign_name: str,
        user_email: str,
    ):
        """
        Check if all days in a batch have been generated.
        Uses Redis INCR on a counter key to track completed jobs atomically.
        When counter reaches total_days_in_batch, send notifications.
        """
        if not batch_job_id or not total_days_in_batch:
            return

        counter_key = f"batch_content_done:{batch_job_id}"
        completed = await self.redis.incr(counter_key)
        # Set expiry so key doesn't linger forever (7 days)
        await self.redis.expire(counter_key, 7 * 24 * 3600)

        logger.info(
            f"Batch {batch_job_id}: {completed}/{total_days_in_batch} days done"
        )

        if completed >= total_days_in_batch:
            logger.info(f"🎉 Batch {batch_job_id} complete! Sending notifications...")
            await self._send_completion_notifications(
                plan_id, user_id, campaign_name, user_email, total_days_in_batch
            )

    async def _send_completion_notifications(
        self,
        plan_id: str,
        user_id: str,
        campaign_name: str,
        user_email: str,
        total_days: int,
    ):
        """Send in-app notification + email when content generation completes."""
        try:
            notif_manager = NotificationManager(self.db)
            notif_manager.create_social_plan_content_done_notification(
                user_id=user_id,
                plan_id=plan_id,
                campaign_name=campaign_name,
                total_days=total_days,
            )
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {e}")

        if user_email:
            try:
                brevo = get_brevo_service()
                brevo.send_social_plan_content_done_email(
                    to_email=user_email,
                    campaign_name=campaign_name,
                    total_days=total_days,
                    plan_url=f"https://wordai.pro/social-plan/{plan_id}",
                )
            except Exception as e:
                logger.error(f"Failed to send completion email: {e}")


async def main():
    worker = SocialPlanContentWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
