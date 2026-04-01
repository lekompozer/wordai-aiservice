"""
Social Plan API Routes
WordAI TikTok AI Social Marketing Plan feature.

IMPORTANT: Static paths (/list, /assets/*) MUST be registered BEFORE dynamic
           path parameters (/{plan_id}) to avoid FastAPI catching them as plan_id.
"""

import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import boto3
from botocore.client import Config
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.queue.queue_manager import get_job_status, set_job_status
from src.services.points_service import get_points_service
from src.exceptions import InsufficientPointsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/social-plan", tags=["AI Social Marketing Plan"])

# ──────────────────────────────────────────────────────────
# Package pricing (points)
# ──────────────────────────────────────────────────────────
PACKAGE_POINT_MAP = {
    "30posts_0img": 100,
    "30posts_1img": 300,
    "30posts_2img": 500,
    "60posts_0img": 150,
    "60posts_1img": 600,
    "60posts_2img": 1000,
    "60posts_3img": 1400,
    "60posts_4img": 1800,
}

POINTS_REGEN_IMAGE = 4
POINTS_REGEN_TEXT = 2

# ──────────────────────────────────────────────────────────
# R2 Helper
# ──────────────────────────────────────────────────────────


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


R2_BUCKET = os.getenv("R2_BUCKET_NAME", "wordai")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")


def _get_db():
    return DBManager().db


async def _get_social_plan_queue():
    from src.queue.queue_dependencies import get_social_plan_queue

    return await get_social_plan_queue()


async def _get_social_image_queue():
    from src.queue.queue_dependencies import get_social_image_queue

    return await get_social_image_queue()


# ──────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────


class RegenerateRequest(BaseModel):
    regenerate: str = "text"  # "text" | "image" | "both"
    instruction: Optional[str] = None


class PostContentRegenRequest(BaseModel):
    instruction: Optional[str] = None


class BatchImageRequest(BaseModel):
    post_ids: Optional[List[str]] = None


class CompetitorInput(BaseModel):
    name: str
    description: Optional[str] = None
    website_url: Optional[str] = None
    facebook_url: Optional[str] = None
    example_posts_text: Optional[str] = None
    max_concurrent: int = 3


# ──────────────────────────────────────────────────────────
# ① STATIC ROUTES (must be before /{plan_id} param routes)
# ──────────────────────────────────────────────────────────

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_DOC_TYPES = {"application/pdf", "text/plain"}
ASSET_TYPES = {"brand", "product", "style_reference", "competitor_example", "brand_doc"}


@router.post(
    "/assets/upload",
    summary="Upload brand assets (images, PDFs, style references)",
)
async def upload_brand_assets(
    plan_draft_id: str = Form(...),
    asset_type: str = Form(
        "brand"
    ),  # brand | product | style_reference | competitor_example | brand_doc
    image_style: str = Form("flat-design"),
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload brand assets for a social plan wizard.

    asset_type values:
      - brand: logo/lifestyle images used in Brand DNA
      - product: product images (linked to products[].image_asset_id)
      - style_reference: reference images for image style
      - competitor_example: competitor content screenshots
      - brand_doc: PDF/text brand documents (brand guide, product catalog, etc.)

    Files are stored on R2 at social-plan-assets/{draft_id}/.
    """
    if asset_type not in ASSET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid asset_type. Must be one of: {sorted(ASSET_TYPES)}",
        )

    user_id = current_user["uid"]
    db = _get_db()
    s3_client = _get_s3_client()

    is_doc_type = asset_type == "brand_doc"
    max_size = 20 * 1024 * 1024 if is_doc_type else 10 * 1024 * 1024  # 20MB for PDFs

    assets = []
    for file in files[:10]:  # Max 10 files per upload call
        content = await file.read()
        if len(content) > max_size:
            continue

        content_type = file.content_type or ""
        fname = file.filename or "asset"
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "bin"

        # Validate MIME type
        if is_doc_type:
            # Allow PDF or plain text
            if content_type not in ALLOWED_DOC_TYPES and ext not in (
                "pdf",
                "txt",
                "md",
            ):
                continue
        else:
            if content_type not in ALLOWED_IMAGE_TYPES and ext not in (
                "jpg",
                "jpeg",
                "png",
                "webp",
                "gif",
            ):
                continue

        asset_id = uuid.uuid4().hex[:12]
        r2_key = f"social-plan-assets/{plan_draft_id}/{asset_type}/{asset_id}.{ext}"

        s3_client.put_object(
            Bucket=R2_BUCKET,
            Key=r2_key,
            Body=content,
            ContentType=content_type
            or ("application/pdf" if ext == "pdf" else "application/octet-stream"),
        )
        file_url = f"{R2_PUBLIC_URL}/{r2_key}"

        asset_doc = {
            "asset_id": asset_id,
            "type": asset_type,
            "filename": fname,
            "file_type": ext,
            "r2_key": r2_key,
            "url": file_url,
            "plan_draft_id": plan_draft_id,
            "plan_id": None,
            "user_id": user_id,
            "uploaded_at": datetime.now(timezone.utc),
            "expires_at": datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + 86400, tz=timezone.utc
            ),
        }

        db["social_plan_assets"].insert_one({**asset_doc, "_id": uuid.uuid4().hex})

        assets.append(
            {
                "asset_id": asset_id,
                "type": asset_type,
                "filename": fname,
                "url": file_url,
            }
        )

    return {
        "plan_draft_id": plan_draft_id,
        "asset_type": asset_type,
        "assets": assets,
        "count": len(assets),
    }


@router.get("/packages", summary="List available packages and pricing")
async def list_packages(
    current_user: dict = Depends(get_current_user),
):
    """Return available package options with point costs and descriptions."""
    packages = [
        {
            "id": pkg_id,
            "posts": int(
                pkg_id.split("posts_")[0].replace("60", "60").replace("30", "30")
            ),
            "images_per_post": int(pkg_id.split("img")[0].rsplit("_", 1)[-1]),
            "points_required": pts,
            "label": _package_label(pkg_id),
        }
        for pkg_id, pts in PACKAGE_POINT_MAP.items()
    ]
    return {"packages": packages}


def _package_label(pkg_id: str) -> str:
    parts = pkg_id.split("_")
    posts = parts[0]  # "30posts" or "60posts"
    imgs = parts[1]  # "0img"..."4img"
    img_count = imgs.replace("img", "")
    posts_count = posts.replace("posts", "")
    if img_count == "0":
        return f"{posts_count} bài viết (không có ảnh AI)"
    return f"{posts_count} bài viết + {img_count} ảnh AI/bài"


@router.get("/list", summary="List user's social plans")
async def list_social_plans(
    page: int = 1,
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
):
    """List all social plans for the authenticated user."""
    user_id = current_user["uid"]
    db = _get_db()

    skip = (page - 1) * limit
    plans = list(
        db["social_plans"]
        .find(
            {"user_id": user_id},
            {
                "_id": 0,
                "plan_id": 1,
                "status": 1,
                "config": 1,
                "total_posts": 1,
                "images_generated": 1,
                "created_at": 1,
                "updated_at": 1,
            },
        )
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

    total = db["social_plans"].count_documents({"user_id": user_id})

    return {"plans": plans, "total": total, "page": page, "limit": limit}


@router.post("/create", summary="Create new social marketing plan")
async def create_social_plan(
    business_name: str = Form(...),
    website_urls: str = Form(...),  # JSON array string
    language: str = Form("vi"),
    posts_per_week: int = Form(5),
    campaign_goal: str = Form("awareness"),
    package: str = Form("30posts_0img"),
    industry: Optional[str] = Form(None),  # NEW: ngành nghề
    platforms: Optional[str] = Form(None),  # NEW: JSON array ["tiktok","facebook",...]
    brand_asset_ids: Optional[str] = Form(None),  # JSON array of asset_ids (type=brand)
    brand_context_asset_ids: Optional[str] = Form(
        None
    ),  # NEW: JSON array of asset_ids (type=brand_doc)
    style_attachment_ids: Optional[str] = Form(
        None
    ),  # NEW: JSON array of asset_ids (type=style_reference)
    products: Optional[str] = Form(None),  # JSON array with optional image_asset_id
    competitors: Optional[str] = Form(None),  # NEW: JSON array of CompetitorInput
    target_audience: Optional[str] = Form(None),
    campaign_description: Optional[str] = Form(None),
    tone: Optional[str] = Form(None),
    image_style: Optional[str] = Form("flat-design"),
    start_date: Optional[str] = Form(None),
    tiktok_data_file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new AI social marketing plan.
    Deducts package points upfront, then enqueues background processing.
    """
    user_id = current_user["uid"]
    db = _get_db()

    # Validate package
    if package not in PACKAGE_POINT_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid package: {package}. Valid: {list(PACKAGE_POINT_MAP.keys())}",
        )

    required_points = PACKAGE_POINT_MAP[package]

    # Deduct points
    points_service = get_points_service()
    try:
        await points_service.deduct_points(
            user_id=user_id,
            amount=required_points,
            service="social_plan_package",
            description=f"Social Marketing Plan - {package}",
        )
    except InsufficientPointsError:
        raise HTTPException(
            status_code=402,
            detail=f"Không đủ điểm. Cần {required_points} điểm cho gói {package}.",
        )

    # Parse fields
    try:
        urls = json.loads(website_urls) if website_urls else []
    except Exception:
        urls = [u.strip() for u in website_urls.split(",") if u.strip()]

    products_list = []
    if products:
        try:
            products_list = json.loads(products)
        except Exception:
            pass

    asset_ids = []
    if brand_asset_ids:
        try:
            asset_ids = json.loads(brand_asset_ids)
        except Exception:
            asset_ids = [brand_asset_ids]

    brand_context_ids = []
    if brand_context_asset_ids:
        try:
            brand_context_ids = json.loads(brand_context_asset_ids)
        except Exception:
            brand_context_ids = [brand_context_asset_ids]

    style_ids = []
    if style_attachment_ids:
        try:
            style_ids = json.loads(style_attachment_ids)
        except Exception:
            style_ids = [style_attachment_ids]

    platforms_list = []
    if platforms:
        try:
            platforms_list = json.loads(platforms)
        except Exception:
            platforms_list = [p.strip() for p in platforms.split(",") if p.strip()]

    competitors_list = []
    if competitors:
        try:
            raw = json.loads(competitors)
            # Accept both list of dicts and list of CompetitorInput-compatible objects
            competitors_list = [
                {
                    "name": c.get("name", "") if isinstance(c, dict) else str(c),
                    "description": (
                        c.get("description") if isinstance(c, dict) else None
                    ),
                    "website_url": (
                        c.get("website_url") if isinstance(c, dict) else None
                    ),
                    "facebook_url": (
                        c.get("facebook_url") if isinstance(c, dict) else None
                    ),
                    "example_posts_text": (
                        c.get("example_posts_text") if isinstance(c, dict) else None
                    ),
                }
                for c in raw
                if c
            ]
        except Exception:
            pass

    # Parse TikTok data file
    tiktok_data = None
    if tiktok_data_file:
        try:
            content = await tiktok_data_file.read()
            file_type = (
                "json" if (tiktok_data_file.filename or "").endswith(".json") else "txt"
            )
            tiktok_data = {
                "bytes_b64": base64.b64encode(content).decode(),
                "file_type": file_type,
            }
        except Exception as e:
            logger.warning(f"Failed to read TikTok file: {e}")

    # Create plan document
    plan_id = f"plan_{uuid.uuid4().hex[:16]}"
    job_id = f"job_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)

    config = {
        "business_name": business_name,
        "website_urls": urls,
        "language": language,
        "posts_per_week": posts_per_week,
        "campaign_goal": campaign_goal,
        "tone": tone or "casual",
        "image_style": image_style or "flat-design",
        "target_audience": target_audience or "",
        "campaign_description": campaign_description or "",
        "start_date": start_date or now.strftime("%Y-%m-%d"),
        "products": products_list,
        # New fields
        "industry": industry or "",
        "platforms": platforms_list,
        "competitors": competitors_list,
        "brand_context_asset_ids": brand_context_ids,
        "style_attachment_ids": style_ids,
    }

    # Link asset drafts to this plan (brand images + brand docs + style refs)
    all_asset_ids = asset_ids + brand_context_ids + style_ids
    if all_asset_ids:
        db["social_plan_assets"].update_many(
            {"asset_id": {"$in": all_asset_ids}, "user_id": user_id},
            {"$set": {"plan_id": plan_id}},
        )

    plan_doc = {
        "plan_id": plan_id,
        "user_id": user_id,
        "created_at": now,
        "updated_at": now,
        "status": "processing",
        "package": package,
        "config": config,
        "products": products_list,
        "asset_ids": asset_ids,
        "brand_context_asset_ids": brand_context_ids,
        "style_attachment_ids": style_ids,
        "brand_data": {"websites": [], "tiktok_posts": []},
        "analysis_summaries": {},
        "brand_dna": {},
        "posts": [],
        "total_posts": 0,
        "images_generated": 0,
        "job_id": job_id,
        "points_spent": required_points,
    }
    db["social_plans"].insert_one(plan_doc)

    # Enqueue to Redis
    queue = await _get_social_plan_queue()
    queue_payload = json.dumps(
        {
            "job_id": job_id,
            "plan_id": plan_id,
            "user_id": user_id,
            "config": config,
            "brand_asset_ids": asset_ids,
            "tiktok_data": tiktok_data,
        }
    )
    await queue.redis_client.rpush("queue:social_plan_jobs", queue_payload)

    await set_job_status(
        queue.redis_client,
        job_id,
        status="pending",
        user_id=user_id,
        plan_id=plan_id,
        step="queued",
        progress=0,
        message="Đang chờ xử lý...",
    )

    return {
        "plan_id": plan_id,
        "job_id": job_id,
        "status": "processing",
        "package": package,
        "points_spent": required_points,
    }


# ──────────────────────────────────────────────────────────
# ② ANALYZE WEBSITE + BRAND PROFILES (static paths — before /{plan_id})
# ──────────────────────────────────────────────────────────


class BrandProfileUpdateRequest(BaseModel):
    brand_name: Optional[str] = None
    description: Optional[str] = None
    problem_solved: Optional[str] = None
    solution: Optional[str] = None
    target_audience: Optional[str] = None
    use_cases: Optional[List[str]] = None
    key_features: Optional[List[str]] = None
    competitive_advantages: Optional[List[str]] = None
    competitors: Optional[List[dict]] = None
    industry: Optional[str] = None
    colors: Optional[dict] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None


@router.post(
    "/analyze-website", summary="Analyze a brand website and save Brand Profile"
)
async def analyze_brand_website(
    website_url: str = Form(...),
    language: str = Form("vi"),
    extra_hint: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Crawl a website URL, auto-discover sub-pages (About/Products/Pricing/Team),
    then use GPT-5.4 to extract a structured Brand Profile card — similar to Cremyx
    Content Engine's website analysis.

    The profile is saved to the user's brand_profiles collection and can be edited.

    Returns the full brand profile including:
      brand_name, description, problem_solved, solution, target_audience,
      use_cases, key_features, competitive_advantages, competitors (auto-detected),
      industry, colors, logo_url, website_url
    """
    import uuid
    from src.services.brand_analyzer import analyze_website_url

    user_id = current_user["uid"]
    db = _get_db()

    try:
        brand_profile = await analyze_website_url(
            url=website_url,
            language=language,
            extra_hint=extra_hint,
        )
    except Exception as e:
        logger.error(f"[analyze-website] Failed for {website_url}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Phân tích website thất bại: {str(e)}"
        )

    now = datetime.now(timezone.utc)
    profile_id = f"bp_{uuid.uuid4().hex[:16]}"

    doc = {
        "_id": uuid.uuid4().hex,
        "profile_id": profile_id,
        "user_id": user_id,
        "created_at": now,
        "updated_at": now,
        # Core brand fields (all editable)
        "brand_name": brand_profile.get("brand_name", ""),
        "website_url": brand_profile.get("website_url", website_url),
        "logo_url": brand_profile.get("logo_url", ""),
        "industry": brand_profile.get("industry", ""),
        "description": brand_profile.get("description", ""),
        "problem_solved": brand_profile.get("problem_solved", ""),
        "solution": brand_profile.get("solution", ""),
        "target_audience": brand_profile.get("target_audience", ""),
        "use_cases": brand_profile.get("use_cases", []),
        "key_features": brand_profile.get("key_features", []),
        "competitive_advantages": brand_profile.get("competitive_advantages", []),
        "competitors": brand_profile.get("competitors", []),
        "colors": brand_profile.get(
            "colors", {"primary": "#000000", "secondary": "", "tertiary": ""}
        ),
        # Analysis metadata
        "_crawled_urls": brand_profile.get("_crawled_urls", [website_url]),
        "_crawled_pages_count": brand_profile.get("_crawled_pages_count", 1),
        "language": language,
    }
    db["brand_profiles"].insert_one(doc)

    return {k: v for k, v in doc.items() if not k.startswith("_id")}


@router.post(
    "/analyze-website/compare",
    summary="Compare GPT-5.4 vs DeepSeek R1 on same brand website",
)
async def compare_brand_analysis(
    website_url: str = Form(...),
    extra_hint: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Crawl the website once, then run both GPT-5.4 and DeepSeek R1 (thinking)
    in parallel and return both results for side-by-side comparison.

    Returns: { "gpt54": {...}, "deepseek_r1": {...}, "_crawled_urls": [...] }
    """
    from src.services.brand_analyzer import analyze_website_url_compare

    try:
        result = await analyze_website_url_compare(
            url=website_url, extra_hint=extra_hint
        )
    except Exception as e:
        logger.error("compare_brand_analysis error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.get("/brand-profiles", summary="List user's saved brand profiles")
async def list_brand_profiles(
    page: int = 1,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """Return all brand profiles the user has analyzed and saved."""
    user_id = current_user["uid"]
    db = _get_db()
    skip = (page - 1) * limit
    profiles = list(
        db["brand_profiles"]
        .find(
            {"user_id": user_id},
            {"_id": 0},
        )
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    total = db["brand_profiles"].count_documents({"user_id": user_id})
    return {"profiles": profiles, "total": total, "page": page, "limit": limit}


@router.get("/brand-profiles/{profile_id}", summary="Get a single brand profile")
async def get_brand_profile(
    profile_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve a saved brand profile by ID."""
    user_id = current_user["uid"]
    db = _get_db()
    profile = db["brand_profiles"].find_one(
        {"profile_id": profile_id, "user_id": user_id}, {"_id": 0}
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return profile


@router.put("/brand-profiles/{profile_id}", summary="Update / edit a brand profile")
async def update_brand_profile(
    profile_id: str,
    body: BrandProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Edit any field of a saved brand profile.
    Only the fields provided in the request body are updated.
    """
    user_id = current_user["uid"]
    db = _get_db()

    profile = db["brand_profiles"].find_one(
        {"profile_id": profile_id, "user_id": user_id}
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Brand profile not found")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc)
    db["brand_profiles"].update_one(
        {"profile_id": profile_id, "user_id": user_id},
        {"$set": updates},
    )

    updated = db["brand_profiles"].find_one(
        {"profile_id": profile_id, "user_id": user_id}, {"_id": 0}
    )
    return updated


@router.delete("/brand-profiles/{profile_id}", summary="Delete a brand profile")
async def delete_brand_profile(
    profile_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a saved brand profile."""
    user_id = current_user["uid"]
    db = _get_db()
    result = db["brand_profiles"].delete_one(
        {"profile_id": profile_id, "user_id": user_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return {"deleted": True, "profile_id": profile_id}


# ──────────────────────────────────────────────────────────
# ③ STATUS ENDPOINT (static path — before /{plan_id})
# ──────────────────────────────────────────────────────────


@router.get("/status/{job_id}", summary="Check plan or image job status")
async def get_plan_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Poll Redis for job progress. Used for both plan generation and image generation jobs."""
    queue = await _get_social_plan_queue()
    job = await get_job_status(queue.redis_client, job_id)

    if not job:
        # Try image queue as fallback
        image_queue = await _get_social_image_queue()
        job = await get_job_status(image_queue.redis_client, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    return {
        "job_id": job_id,
        "status": job.get("status"),
        "step": job.get("step"),
        "progress": int(job.get("progress", 0)),
        "message": job.get("message", ""),
        "plan_id": job.get("plan_id"),
        "post_id": job.get("post_id"),
        "image_url": job.get("image_url"),
    }


# ──────────────────────────────────────────────────────────────────────────────
# ③ COMPETITOR SOCIAL ANALYSIS  (Apify + DeepSeek R1)
#    All static paths — must stay BEFORE /{plan_id} dynamic route
# ──────────────────────────────────────────────────────────────────────────────


@router.post(
    "/competitor-social/demo",
    summary="[FREE] Fetch & analyze 10 latest posts from 1 social page",
)
async def competitor_social_demo(
    social_url: str = Form(
        ..., description="URL of a Facebook / Instagram / TikTok page"
    ),
    language: str = Form("vi", description="Response language: vi, en, fr, …"),
    followers_count: Optional[int] = Form(
        None,
        description="Optional: follower count of the page (for engagement rate calculation)",
    ),
):
    """
    Demo endpoint — no auth required.
    Fetches the 10 most recent text posts from the given page and returns a
    DeepSeek R1 competitive-intelligence analysis so prospects can see value
    before they subscribe.

    Cost: ~$0.05 (10 posts × $5/1,000).
    """
    from src.services.apify_scraper import (
        compute_engagement_metrics,
        fetch_social_posts,
    )
    from src.services.social_competitor_analyzer import analyze_social_posts

    apify_token = os.getenv("APIFY_API_TOKEN")
    if not apify_token:
        raise HTTPException(status_code=503, detail="Apify integration not configured")

    try:
        scraped = await fetch_social_posts(
            social_url, limit=10, apify_token=apify_token
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("competitor_social_demo scrape error: %s", e)
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e}")

    # TikTok: followers auto-scraped from authorMeta, no need to pass manually
    effective_followers = followers_count or scraped.get("page_followers")

    # Recompute metrics including followers_count for engagement rate
    metrics = scraped.get("engagement_metrics") or {}
    if effective_followers:
        metrics = compute_engagement_metrics(
            scraped["posts"], followers_count=effective_followers
        )

    analysis = await analyze_social_posts(
        competitor_url=social_url,
        platform=scraped["platform"],
        posts=scraped["posts"],
        language=language,
        engagement_metrics=metrics,
        followers_count=effective_followers,
    )

    return {
        "demo": True,
        "platform": scraped["platform"],
        "url": social_url,
        "followers_count": effective_followers,
        "posts_fetched": scraped["posts_count"],
        "engagement_metrics": metrics,
        "posts": scraped["posts"],  # raw posts for UI display
        "analysis": analysis,
    }


@router.post(
    "/competitor-social/analyze",
    summary="Fetch & analyze 15 posts × up to 3 competitors on one channel",
)
async def competitor_social_analyze(
    social_urls: str = Form(
        ...,
        description='JSON array of up to 3 social URLs on the SAME platform, e.g. ["url1","url2","url3"]',
    ),
    language: str = Form("vi"),
    followers_counts: Optional[str] = Form(
        None,
        description='Optional JSON object mapping URL → follower count, e.g. {"https://fb.com/page": 316000}',
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Paid analysis: scrape 15 posts from each URL (max 3), analyze with DeepSeek R1.
    All URLs must be on the same platform (Facebook, Instagram, or TikTok).

    Cost: ~$0.225 (15 posts × 3 competitors × $5/1,000).
    Results are saved to `competitor_social_analyses` MongoDB collection.
    """
    import json as _json

    from src.services.apify_scraper import fetch_multiple_competitors
    from src.services.social_competitor_analyzer import analyze_multiple_social

    apify_token = os.getenv("APIFY_API_TOKEN")
    if not apify_token:
        raise HTTPException(status_code=503, detail="Apify integration not configured")

    try:
        urls: List[str] = _json.loads(social_urls)
        if not isinstance(urls, list) or not urls:
            raise ValueError("social_urls must be a non-empty JSON array")
        urls = urls[:3]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid social_urls: {e}")

    fc_map: dict = {}
    if followers_counts:
        try:
            fc_map = _json.loads(followers_counts)
        except Exception:
            pass  # followers_counts is optional, ignore parse errors

    user_id = current_user["uid"]
    db = _get_db()

    # ── Scrape ──────────────────────────────────────────────────────────────
    try:
        scraped_list = await fetch_multiple_competitors(
            urls, limit_per_url=15, apify_token=apify_token
        )
    except Exception as e:
        logger.error("competitor_social_analyze scrape error: %s", e)
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e}")

    # ── Analyze ─────────────────────────────────────────────────────────────
    analyses = await analyze_multiple_social(scraped_list, language=language)

    # ── Persist ─────────────────────────────────────────────────────────────
    import uuid as _uuid
    import datetime as _dt

    analysis_id = f"ca_{_uuid.uuid4().hex[:16]}"
    doc = {
        "analysis_id": analysis_id,
        "user_id": user_id,
        "language": language,
        "platform": scraped_list[0].get("platform") if scraped_list else "unknown",
        "competitors": analyses,
        "raw_posts": [
            {"url": s["url"], "posts": s["posts"], "posts_count": s["posts_count"]}
            for s in scraped_list
        ],
        "created_at": _dt.datetime.utcnow(),
    }
    db["competitor_social_analyses"].insert_one(doc)

    return {
        "analysis_id": analysis_id,
        "competitors_analyzed": len(analyses),
        "competitors": analyses,
        "raw_posts": doc["raw_posts"],
        "engagement_summary": [
            {"url": s["url"], "metrics": s.get("engagement_metrics")}
            for s in scraped_list
        ],
    }


@router.get(
    "/competitor-social/analyses",
    summary="List saved competitor social analyses for the current user",
)
async def list_competitor_analyses(
    page: int = 1,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()
    skip = (page - 1) * limit
    items = list(
        db["competitor_social_analyses"]
        .find({"user_id": user_id}, {"_id": 0, "raw_posts": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return {"page": page, "limit": limit, "items": items}


@router.get(
    "/competitor-social/analyses/{analysis_id}",
    summary="Get a specific competitor social analysis",
)
async def get_competitor_analysis(
    analysis_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = _get_db()
    doc = db["competitor_social_analyses"].find_one(
        {"analysis_id": analysis_id, "user_id": current_user["uid"]},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return doc


# ──────────────────────────────────────────────────────────
# ④ DYNAMIC ROUTES (plan_id param — MUST be AFTER static routes)
# ──────────────────────────────────────────────────────────


@router.get("/{plan_id}", summary="Get social plan with all posts")
async def get_social_plan(
    plan_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get full plan data including all posts, brand DNA, config."""
    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {"_id": 0},
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return plan


@router.post("/{plan_id}/duplicate", summary="Duplicate a social plan")
async def duplicate_social_plan(
    plan_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a copy of an existing plan with all posts, brand DNA, and config.
    The duplicate starts with status='draft' and does NOT deduct points.
    """
    user_id = current_user["uid"]
    db = _get_db()

    original = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {"_id": 0},
    )
    if not original:
        raise HTTPException(status_code=404, detail="Plan not found")

    now = datetime.now(timezone.utc)
    new_plan_id = f"plan_{uuid.uuid4().hex[:16]}"

    new_plan = {
        **original,
        "plan_id": new_plan_id,
        "created_at": now,
        "updated_at": now,
        "status": "draft",
        "job_id": None,
        "points_spent": 0,
    }

    # Re-generate post_ids to avoid duplicates
    import copy

    new_posts = []
    for p in original.get("posts", []):
        new_p = copy.deepcopy(p)
        new_p["post_id"] = f"post_{uuid.uuid4().hex[:12]}"
        new_p["image_url"] = None
        new_p["image_job_id"] = None
        new_p["custom_image_url"] = None
        new_posts.append(new_p)
    new_plan["posts"] = new_posts

    db["social_plans"].insert_one(new_plan)

    return {
        "plan_id": new_plan_id,
        "original_plan_id": plan_id,
        "status": "draft",
        "total_posts": len(new_posts),
    }


@router.get("/{plan_id}/export/csv", summary="Export plan posts as CSV")
async def export_plan_csv(
    plan_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Export all posts from a plan as a CSV file.
    Columns: day, date, platform, content_pillar, topic, hook, caption, hashtags, cta, image_url
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse

    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {"_id": 0, "posts": 1, "config": 1},
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    posts = plan.get("posts", [])
    business_name = plan.get("config", {}).get("business_name", "plan")

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "day",
            "date",
            "platform",
            "content_pillar",
            "topic",
            "hook",
            "caption",
            "hashtags",
            "cta",
            "image_url",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    for p in posts:
        row = dict(p)
        if isinstance(row.get("hashtags"), list):
            row["hashtags"] = " ".join(row["hashtags"])
        writer.writerow(row)

    output.seek(0)
    filename = f"{business_name.replace(' ', '_')}_{plan_id}_posts.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post(
    "/{plan_id}/post/{post_id}/upload-image",
    summary="Upload a custom image for a post",
)
async def upload_post_custom_image(
    plan_id: str,
    post_id: str,
    image: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a custom image for a specific post (replaces AI-generated image).
    Stored at social-plan-assets/{plan_id}/custom-images/{post_id}.{ext}
    No points deducted.
    """
    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {"posts.post_id": 1},
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    post_exists = any(p["post_id"] == post_id for p in plan.get("posts", []))
    if not post_exists:
        raise HTTPException(status_code=404, detail="Post not found in plan")

    content = await image.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    content_type = image.content_type or "image/jpeg"
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image type")

    fname = image.filename or "custom.jpg"
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "jpg"
    r2_key = f"social-plan-assets/{plan_id}/custom-images/{post_id}.{ext}"

    s3_client = _get_s3_client()
    s3_client.put_object(
        Bucket=R2_BUCKET,
        Key=r2_key,
        Body=content,
        ContentType=content_type,
    )
    image_url = f"{R2_PUBLIC_URL}/{r2_key}"

    db["social_plans"].update_one(
        {"plan_id": plan_id, "posts.post_id": post_id},
        {
            "$set": {
                "posts.$.custom_image_url": image_url,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    return {"post_id": post_id, "custom_image_url": image_url}


@router.post(
    "/{plan_id}/post/{post_id}/generate-image",
    summary="Generate image for a post (4 pts)",
)
async def generate_post_image(
    plan_id: str,
    post_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Queue image generation for a single post.
    Costs 4 points per call.
    """
    user_id = current_user["uid"]
    db = _get_db()

    # Verify plan ownership
    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {"posts": 1, "status": 1},
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    post = next((p for p in plan.get("posts", []) if p["post_id"] == post_id), None)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found in plan")

    # Deduct points
    points_service = get_points_service()
    try:
        await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_REGEN_IMAGE,
            service="social_plan_regenerate_image",
            description=f"Generate image for post {post_id}",
        )
    except InsufficientPointsError:
        raise HTTPException(
            status_code=402,
            detail=f"Không đủ điểm. Cần {POINTS_REGEN_IMAGE} điểm để tạo ảnh.",
        )

    job_id = f"img_{uuid.uuid4().hex[:16]}"
    queue = await _get_social_image_queue()

    queue_payload = json.dumps(
        {
            "job_id": job_id,
            "plan_id": plan_id,
            "post_id": post_id,
            "user_id": user_id,
        }
    )
    await queue.redis_client.rpush("queue:social_image_jobs", queue_payload)

    await set_job_status(
        queue.redis_client,
        job_id,
        status="pending",
        user_id=user_id,
        plan_id=plan_id,
        post_id=post_id,
        step="queued",
        message="Đang chờ tạo ảnh...",
    )

    # Mark post as image generation in progress
    db["social_plans"].update_one(
        {"plan_id": plan_id, "posts.post_id": post_id},
        {"$set": {"posts.$.image_job_id": job_id}},
    )

    return {"job_id": job_id, "status": "queued", "points_spent": POINTS_REGEN_IMAGE}


@router.post(
    "/{plan_id}/generate-images-batch",
    summary="Batch generate images for multiple posts",
)
async def generate_images_batch(
    plan_id: str,
    body: BatchImageRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Queue image generation for multiple posts.
    Each image costs 4 points.
    """
    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {"posts": 1},
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    all_posts = plan.get("posts", [])

    # Filter to requested post_ids or all posts without images
    if body.post_ids:
        posts_to_gen = [p for p in all_posts if p["post_id"] in body.post_ids]
    else:
        posts_to_gen = [p for p in all_posts if not p.get("image_url")]

    if not posts_to_gen:
        return {"job_ids": [], "total": 0, "message": "No posts to generate"}

    total_cost = len(posts_to_gen) * POINTS_REGEN_IMAGE
    points_service = get_points_service()
    try:
        await points_service.deduct_points(
            user_id=user_id,
            amount=total_cost,
            service="social_plan_regenerate_image",
            description=f"Batch generate {len(posts_to_gen)} images for plan {plan_id}",
        )
    except InsufficientPointsError:
        raise HTTPException(
            status_code=402,
            detail=f"Không đủ điểm. Cần {total_cost} điểm cho {len(posts_to_gen)} ảnh.",
        )

    queue = await _get_social_image_queue()
    job_ids = []

    for post in posts_to_gen:
        post_id = post["post_id"]
        job_id = f"img_{uuid.uuid4().hex[:16]}"
        queue_payload = json.dumps(
            {
                "job_id": job_id,
                "plan_id": plan_id,
                "post_id": post_id,
                "user_id": user_id,
            }
        )
        await queue.redis_client.rpush("queue:social_image_jobs", queue_payload)
        await set_job_status(
            queue.redis_client,
            job_id,
            status="pending",
            user_id=user_id,
            plan_id=plan_id,
            post_id=post_id,
            step="queued",
            message="Đang chờ tạo ảnh...",
        )
        db["social_plans"].update_one(
            {"plan_id": plan_id, "posts.post_id": post_id},
            {"$set": {"posts.$.image_job_id": job_id}},
        )
        job_ids.append(job_id)

    return {
        "job_ids": job_ids,
        "total": len(job_ids),
        "points_spent": total_cost,
    }


@router.post(
    "/{plan_id}/post/{post_id}/regenerate",
    summary="Regenerate content or image for a post (2-4 pts)",
)
async def regenerate_post(
    plan_id: str,
    post_id: str,
    body: RegenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Regenerate text content or image for a post.
    - regenerate='text': 2 points (DeepSeek rewrites content)
    - regenerate='image': 4 points (Gemini generates new image)
    - regenerate='both': 6 points
    """
    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {"posts": 1, "brand_dna": 1, "config": 1},
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    post = next((p for p in plan.get("posts", []) if p["post_id"] == post_id), None)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found in plan")

    regen = body.regenerate
    if regen not in ("text", "image", "both"):
        raise HTTPException(
            status_code=400, detail="regenerate must be 'text', 'image', or 'both'"
        )

    cost = 0
    if regen in ("text", "both"):
        cost += POINTS_REGEN_TEXT
    if regen in ("image", "both"):
        cost += POINTS_REGEN_IMAGE

    points_service = get_points_service()
    try:
        await points_service.deduct_points(
            user_id=user_id,
            amount=cost,
            service=(
                "social_plan_regenerate_text"
                if regen == "text"
                else "social_plan_regenerate_image"
            ),
            description=f"Regenerate {regen} for post {post_id}",
        )
    except InsufficientPointsError:
        raise HTTPException(status_code=402, detail=f"Không đủ điểm. Cần {cost} điểm.")

    result = {"post_id": post_id, "points_spent": cost}

    # Regenerate text content synchronously (fast, ~2s)
    if regen in ("text", "both"):
        try:
            from src.services.social_plan_service import SocialPlanService

            plan_service = SocialPlanService()
            new_content = await plan_service.generate_post_content(
                brand_dna=plan.get("brand_dna", {}),
                post=post,
                config=plan.get("config", {}),
                custom_instruction=body.instruction,
            )
            now = datetime.now(timezone.utc)
            db["social_plans"].update_one(
                {"plan_id": plan_id, "posts.post_id": post_id},
                {
                    "$set": {
                        "posts.$.hook": new_content["hook"],
                        "posts.$.caption": new_content["caption"],
                        "posts.$.hashtags": new_content["hashtags"],
                        "posts.$.image_prompt": new_content["image_prompt"],
                        "posts.$.cta": new_content["cta"],
                        "updated_at": now,
                    }
                },
            )
            result["new_content"] = new_content
        except Exception as e:
            logger.error(f"Text regen failed for {post_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Content regeneration failed: {str(e)}"
            )

    # Queue image generation
    if regen in ("image", "both"):
        job_id = f"img_{uuid.uuid4().hex[:16]}"
        queue = await _get_social_image_queue()
        queue_payload = json.dumps(
            {
                "job_id": job_id,
                "plan_id": plan_id,
                "post_id": post_id,
                "user_id": user_id,
            }
        )
        await queue.redis_client.rpush("queue:social_image_jobs", queue_payload)
        await set_job_status(
            queue.redis_client,
            job_id,
            status="pending",
            user_id=user_id,
            plan_id=plan_id,
            post_id=post_id,
            step="queued",
            message="Đang chờ tạo ảnh...",
        )
        db["social_plans"].update_one(
            {"plan_id": plan_id, "posts.post_id": post_id},
            {"$set": {"posts.$.image_job_id": job_id}},
        )
        result["image_job_id"] = job_id

    return result


@router.delete("/{plan_id}", summary="Delete a social plan")
async def delete_social_plan(
    plan_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Soft-delete a social plan."""
    user_id = current_user["uid"]
    db = _get_db()

    result = db["social_plans"].update_one(
        {"plan_id": plan_id, "user_id": user_id},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found")

    return {"success": True, "plan_id": plan_id}
