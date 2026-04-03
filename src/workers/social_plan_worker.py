"""
Social Plan Worker
Consumes queue:social_plan_jobs and runs the full plan generation pipeline:
  Phase 1:  Brand Extraction (Playwright crawl)
  Phase 2:  TikTok Data Parsing
  Phase 2b: Layer 1 parallel analyzers (new):
              - CompetitorAnalyzer → per-competitor summaries
              - BrandDocAnalyzer   → PDF/doc summaries
              - ProductAnalyzer    → product catalog summary
  Phase 3:  Brand DNA Generation (ChatGPT gpt-5.4) — uses all Layer 1 summaries
  Phase 4:  Plan Structure (ChatGPT gpt-5.4) — informed by product + competitors
  Phase 5:  Content Generation per Post (DeepSeek)
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
from src.services.competitor_analyzer import analyze_all_competitors
from src.services.brand_doc_analyzer import fetch_and_analyze_brand_docs
from src.services.product_analyzer import analyze_products

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
        task_type = job.get("task_type", "social_plan")

        if task_type == "brand_compare":
            await self._process_brand_compare_job(job)
            return

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

            # ── Phase 2b: Layer 1 Parallel Analyzers ───────────────
            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                step="analyzing_inputs",
                progress=30,
                message="Đang phân tích đối thủ, tài liệu và sản phẩm...",
            )

            competitors = config.get("competitors", [])
            brand_context_asset_ids = config.get("brand_context_asset_ids", [])
            products_list = config.get("products", [])

            async def _empty_list():
                return []

            async def _empty_str():
                return ""

            # Run all Layer 1 analyzers in parallel
            competitor_coro = (
                analyze_all_competitors(competitors, self.plan_service.deepseek)
                if competitors
                else _empty_list()
            )
            brand_doc_coro = (
                fetch_and_analyze_brand_docs(
                    brand_context_asset_ids, self.db, self.plan_service.deepseek
                )
                if brand_context_asset_ids
                else _empty_str()
            )

            # product_analyzer is sync — wrap in executor
            loop = asyncio.get_event_loop()
            product_task = loop.run_in_executor(None, analyze_products, products_list)

            competitor_summaries, brand_doc_summary, product_analysis = (
                await asyncio.gather(
                    competitor_coro,
                    brand_doc_coro,
                    product_task,
                    return_exceptions=True,
                )
            )

            # Safely handle any analyzer failures (non-fatal)
            if isinstance(competitor_summaries, Exception):
                logger.error(f"Competitor analysis failed: {competitor_summaries}")
                competitor_summaries = []
            if isinstance(brand_doc_summary, Exception):
                logger.error(f"Brand doc analysis failed: {brand_doc_summary}")
                brand_doc_summary = ""
            if isinstance(product_analysis, Exception):
                logger.error(f"Product analysis failed: {product_analysis}")
                product_analysis = None

            # Save analysis summaries to MongoDB
            self.db["social_plans"].update_one(
                {"plan_id": plan_id},
                {
                    "$set": {
                        "analysis_summaries": {
                            "competitors": competitor_summaries or [],
                            "brand_docs": brand_doc_summary or "",
                            "products": (product_analysis or {}).get("summary", ""),
                        },
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
                brand_data,
                tiktok_insights,
                config,
                competitor_summaries=competitor_summaries or [],
                brand_doc_summary=brand_doc_summary or "",
                product_summary=(product_analysis or {}).get("summary", ""),
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

            posts = await self.plan_service.generate_plan_structure(
                brand_dna, config, product_analysis=product_analysis
            )

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

    async def _process_brand_compare_job(self, job: dict):
        """
        Process a brand_compare job:
          1. Scrape my page + competitors (Apify)
          2. Analyze each page with DeepSeek R1
          3. If screenshots provided → ChatGPT Vision design analysis
          4. Run comparative analysis (DeepSeek R1)
          5. Save to brand_comparisons collection, set Redis completed
        """
        job_id = job.get("job_id")
        user_id = job.get("user_id") or ""
        my_url = job.get("my_url", "")
        competitor_urls = job.get("competitor_urls", [])
        language = job.get("language", "vi")
        fc_map: dict = job.get("followers_counts") or {}
        screenshot_urls: list = job.get("screenshot_urls") or []
        brand_names: dict = job.get("brand_names") or {}

        if not job_id or not my_url:
            logger.error(f"Invalid brand_compare payload: {job}")
            return

        logger.info(f"🔍 Processing brand_compare job: {job_id} | my_url: {my_url}")

        apify_token = os.getenv("APIFY_API_TOKEN")

        try:
            from src.services.apify_scraper import (
                fetch_social_posts,
                compute_engagement_metrics,
            )
            from src.services.social_competitor_analyzer import analyze_social_posts
            from src.services.brand_comparison_service import (
                analyze_design_with_chatgpt,
                run_brand_comparison,
            )

            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                step="scraping",
                progress=5,
                message=f"Đang scrape {1 + len(competitor_urls)} trang...",
            )

            all_urls = [my_url] + competitor_urls
            scraped_all = []
            for i, url in enumerate(all_urls):
                await set_job_status(
                    self.redis,
                    job_id,
                    "processing",
                    user_id=user_id,
                    step="scraping",
                    progress=5 + i * 10,
                    message=f"Đang scrape trang {i + 1}/{len(all_urls)}: {url}",
                )
                try:
                    scraped = await fetch_social_posts(
                        url, limit=15, apify_token=apify_token
                    )
                    # Apply followers_count for engagement rate
                    fc = fc_map.get(url) or scraped.get("page_followers")
                    if fc:
                        posts = scraped["posts"]
                        platform = scraped["platform"]
                        has_pinned = any(p.get("is_pinned") for p in posts)
                        if platform == "tiktok" and has_pinned:
                            pinned_posts = [p for p in posts if p.get("is_pinned")]
                            regular_posts = [p for p in posts if not p.get("is_pinned")]
                            scraped["engagement_metrics"] = {
                                "all": compute_engagement_metrics(
                                    posts, followers_count=fc
                                ),
                                "pinned": (
                                    compute_engagement_metrics(
                                        pinned_posts, followers_count=fc
                                    )
                                    if pinned_posts
                                    else None
                                ),
                                "regular": (
                                    compute_engagement_metrics(
                                        regular_posts, followers_count=fc
                                    )
                                    if regular_posts
                                    else None
                                ),
                                "has_pinned_split": True,
                            }
                        else:
                            # Non-TikTok (Facebook, Instagram, etc.): wrap flat metrics
                            scraped["engagement_metrics"] = {
                                "has_pinned_split": False,
                                "all": compute_engagement_metrics(
                                    posts, followers_count=fc
                                ),
                            }
                        scraped["page_followers"] = fc
                    else:
                        # No followers count provided; still normalize flat metrics
                        # so structure is always consistent (wrap under "all")
                        existing_em = scraped.get("engagement_metrics")
                        if existing_em and not isinstance(existing_em, dict):
                            pass  # unexpected type, leave as is
                        elif existing_em and "has_pinned_split" not in existing_em:
                            scraped["engagement_metrics"] = {
                                "has_pinned_split": False,
                                "all": existing_em,
                            }
                    scraped_all.append(scraped)
                except Exception as e:
                    logger.error(f"Scrape failed for {url}: {e}")
                    scraped_all.append(
                        {
                            "url": url,
                            "platform": "unknown",
                            "posts": [],
                            "posts_count": 0,
                            "_error": str(e),
                        }
                    )

            # ── Step 2: Analyze each page ──────────────────────────
            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                step="analyzing_pages",
                progress=50,
                message=f"Đang phân tích {len(scraped_all)} trang với DeepSeek R1...",
            )

            page_analyses = []
            for i, scraped in enumerate(scraped_all):
                if not scraped.get("posts"):
                    page_analyses.append(
                        {
                            "_url": scraped["url"],
                            "_error": scraped.get("_error", "No posts scraped"),
                        }
                    )
                    continue
                try:
                    analysis = await analyze_social_posts(
                        competitor_url=scraped["url"],
                        platform=scraped.get("platform", "unknown"),
                        posts=scraped["posts"],
                        language=language,
                        engagement_metrics=scraped.get("engagement_metrics"),
                        followers_count=scraped.get("page_followers"),
                        brand_name=brand_names.get(scraped["url"]),
                    )
                    page_analyses.append(analysis)
                except Exception as e:
                    logger.error(f"Analysis failed for {scraped['url']}: {e}")
                    page_analyses.append({"_url": scraped["url"], "_error": str(e)})

            my_analysis = page_analyses[0] if page_analyses else {}
            competitor_analyses = page_analyses[1:]

            # ── Step 3: Design analysis via Apify post thumbnails ─────
            # Use post cover URLs (TikTok coverUrl / Instagram displayUrl)
            # already scraped — no CAPTCHA, better content insight.
            from src.services.brand_comparison_service import (
                analyze_all_designs_from_thumbnails,
                run_brand_comparison,
                upload_thumbnails_to_r2,
            )

            def _get_thumbnail_urls(scraped_data: dict) -> list:
                em = scraped_data.get("engagement_metrics", {})
                if not isinstance(em, dict):
                    return []
                # Check nested sub-dicts first (covers pinned-split and nested 'all')
                for key in ("regular", "all"):
                    urls = em.get(key, {}).get("thumbnail_urls")
                    if urls:
                        return urls
                return em.get("thumbnail_urls", [])

            def _set_thumbnail_urls(scraped_data: dict, r2_urls: list) -> None:
                """Replace thumbnail_urls in scraped_data with R2 URLs."""
                em = scraped_data.get("engagement_metrics", {})
                if not isinstance(em, dict):
                    return
                for key in ("regular", "all"):
                    sub = em.get(key, {})
                    if isinstance(sub, dict) and sub.get("thumbnail_urls"):
                        sub["thumbnail_urls"] = r2_urls
                        return
                if "thumbnail_urls" in em:
                    em["thumbnail_urls"] = r2_urls

            page_thumbnail_urls = [_get_thumbnail_urls(s) for s in scraped_all]
            taken = sum(1 for t in page_thumbnail_urls if t)
            logger.info(
                f"[BrandCompare] Thumbnail URLs collected: {taken}/{len(all_urls)} pages"
            )

            # ── Upload thumbnails to R2 for permanent storage ─────
            # Facebook/Instagram CDN URLs expire; store permanently on R2.
            r2_page_thumbnail_urls = []
            for i, urls in enumerate(page_thumbnail_urls):
                if urls:
                    r2_urls = await upload_thumbnails_to_r2(
                        urls,
                        prefix=f"social-audit-thumbs/{job_id}",
                    )
                    r2_page_thumbnail_urls.append(r2_urls)
                    _set_thumbnail_urls(scraped_all[i], r2_urls)
                else:
                    r2_page_thumbnail_urls.append(urls)
            page_thumbnail_urls = r2_page_thumbnail_urls
            logger.info(f"[BrandCompare] Thumbnails uploaded to R2 for {taken} pages")

            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                step="design_analysis",
                progress=70,
                message="Đang phân tích phong cách thiết kế với ChatGPT Vision (thumbnails)...",
            )

            design_by_url = await analyze_all_designs_from_thumbnails(
                page_urls=all_urls,
                page_thumbnail_urls=page_thumbnail_urls,
                language=language,
            )
            # Stamp each design analysis with _url so frontend can identify per page
            design_analyses = []
            for url in all_urls:
                d = design_by_url.get(url)
                if d and isinstance(d, dict):
                    d["_url"] = url
                design_analyses.append(d)

            my_design = design_analyses[0] if design_analyses else None
            competitor_designs = design_analyses[1:]

            # ── Step 4: Comparative analysis ──────────────────────
            await set_job_status(
                self.redis,
                job_id,
                "processing",
                user_id=user_id,
                step="comparative_analysis",
                progress=80,
                message="Đang tổng hợp phân tích cạnh tranh toàn diện...",
            )

            brand_comparison = await run_brand_comparison(
                my_url=my_url,
                my_analysis=my_analysis,
                competitor_analyses=competitor_analyses,
                my_design=my_design,
                competitor_designs=competitor_designs,
                language=language,
            )

            # ── Step 5: Persist ────────────────────────────────────
            comparison_id = f"bc_{uuid.uuid4().hex[:16]}"
            doc = {
                "comparison_id": comparison_id,
                "job_id": job_id,
                "user_id": user_id,
                "language": language,
                "my_url": my_url,
                "competitor_urls": competitor_urls,
                "brand_names": brand_names,
                "my_analysis": my_analysis,
                "competitor_analyses": competitor_analyses,
                "design_analyses": [d for d in design_analyses if d],
                "brand_comparison": brand_comparison,
                "engagement_summary": [
                    {
                        "url": s["url"],
                        "brand_name": brand_names.get(s["url"]) or "",
                        "platform": s.get("platform") or "",
                        "metrics": s.get("engagement_metrics"),
                        "followers": s.get("page_followers"),
                    }
                    for s in scraped_all
                ],
                "created_at": datetime.now(timezone.utc),
            }
            self.db["brand_comparisons"].insert_one(doc)

            await set_job_status(
                self.redis,
                job_id,
                "completed",
                user_id=user_id,
                comparison_id=comparison_id,
                step="done",
                progress=100,
                message="Phân tích hoàn tất!",
                my_analysis=my_analysis,
                competitor_analyses=competitor_analyses,
                design_analyses=[d for d in design_analyses if d],
                brand_comparison=brand_comparison,
                engagement_summary=doc["engagement_summary"],
            )

            logger.info(f"✅ brand_compare job {job_id} completed → {comparison_id}")

        except Exception as e:
            logger.error(f"❌ brand_compare job {job_id} failed: {e}", exc_info=True)
            try:
                await set_job_status(
                    self.redis,
                    job_id,
                    "failed",
                    user_id=user_id,
                    step="failed",
                    progress=0,
                    message=f"Lỗi: {str(e)[:200]}",
                )
            except Exception as inner_e:
                logger.error(f"Failed to update error status: {inner_e}")


if __name__ == "__main__":
    worker = SocialPlanWorker()
    asyncio.run(worker.start())
