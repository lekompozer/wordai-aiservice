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
    max_concurrent: int = 3


# ──────────────────────────────────────────────────────────
# ① STATIC ROUTES (must be before /{plan_id} param routes)
# ──────────────────────────────────────────────────────────

@router.post("/assets/upload", summary="Upload brand assets (logo, lifestyle, product photos)")
async def upload_brand_assets(
    plan_draft_id: str = Form(...),
    image_style: str = Form("flat-design"),
    images: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload brand images (logo, lifestyle, product) for a social plan.
    Returns list of asset objects with URLs.
    Files are stored on R2 at social-plan-assets/{draft_id}/.
    """
    user_id = current_user["uid"]
    db = _get_db()
    s3_client = _get_s3_client()

    assets = []
    for file in images[:10]:  # Max 10 images
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:  # 10MB limit
            continue

        # Determine asset type from filename hint
        name_lower = (file.filename or "").lower()
        if "logo" in name_lower:
            asset_type = "logo"
        elif "product" in name_lower:
            asset_type = "product"
        else:
            asset_type = "lifestyle"

        fname = file.filename or "asset.png"
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "png"
        asset_id = uuid.uuid4().hex[:12]
        r2_key = f"social-plan-assets/{plan_draft_id}/{asset_id}.{ext}"

        s3_client.put_object(
            Bucket=R2_BUCKET,
            Key=r2_key,
            Body=content,
            ContentType=file.content_type or "image/png",
        )
        file_url = f"{R2_PUBLIC_URL}/{r2_key}"

        assets.append({
            "asset_id": asset_id,
            "type": asset_type,
            "filename": file.filename,
            "r2_key": r2_key,
            "url": file_url,
            "product_name": None,
        })

    # Save to MongoDB
    now = datetime.now(timezone.utc)
    assets_doc = {
        "plan_draft_id": plan_draft_id,
        "plan_id": None,
        "user_id": user_id,
        "uploaded_at": now,
        "assets": assets,
        "image_style": image_style,
        "expires_at": datetime.fromtimestamp(
            now.timestamp() + 86400, tz=timezone.utc
        ),  # 24h draft expiry
    }
    db["social_plan_assets"].insert_one(assets_doc)

    return {"plan_draft_id": plan_draft_id, "assets": assets, "count": len(assets)}


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
    brand_asset_ids: Optional[str] = Form(None),  # JSON array of plan_draft_ids
    products: Optional[str] = Form(None),  # JSON array
    target_audience: Optional[str] = Form(None),
    campaign_description: Optional[str] = Form(None),
    tone: Optional[str] = Form(None),
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
        raise HTTPException(status_code=400, detail=f"Invalid package: {package}. Valid: {list(PACKAGE_POINT_MAP.keys())}")

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
        raise HTTPException(status_code=402, detail=f"Không đủ điểm. Cần {required_points} điểm cho gói {package}.")

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

    # Parse TikTok data file
    tiktok_data = None
    if tiktok_data_file:
        try:
            content = await tiktok_data_file.read()
            file_type = "json" if (tiktok_data_file.filename or "").endswith(".json") else "txt"
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
        "image_style": "flat-design",
        "target_audience": target_audience or "",
        "campaign_description": campaign_description or "",
        "start_date": start_date or now.strftime("%Y-%m-%d"),
        "products": products_list,
    }

    # Link asset draft to this plan
    if asset_ids:
        db["social_plan_assets"].update_many(
            {"plan_draft_id": {"$in": asset_ids}, "user_id": user_id},
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
        "brand_data": {"websites": [], "tiktok_posts": []},
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
    queue_payload = json.dumps({
        "job_id": job_id,
        "plan_id": plan_id,
        "user_id": user_id,
        "config": config,
        "brand_asset_ids": asset_ids,
        "tiktok_data": tiktok_data,
    })
    await queue.redis_client.rpush("queue:social_plan_jobs", queue_payload)

    await set_job_status(
        queue.redis_client, job_id,
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
# ② STATUS ENDPOINT (static path — before /{plan_id})
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


# ──────────────────────────────────────────────────────────
# ③ DYNAMIC ROUTES (plan_id param — MUST be AFTER static routes)
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


@router.post("/{plan_id}/post/{post_id}/generate-image", summary="Generate image for a post (4 pts)")
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
        raise HTTPException(status_code=402, detail=f"Không đủ điểm. Cần {POINTS_REGEN_IMAGE} điểm để tạo ảnh.")

    job_id = f"img_{uuid.uuid4().hex[:16]}"
    queue = await _get_social_image_queue()

    queue_payload = json.dumps({
        "job_id": job_id,
        "plan_id": plan_id,
        "post_id": post_id,
        "user_id": user_id,
    })
    await queue.redis_client.rpush("queue:social_image_jobs", queue_payload)

    await set_job_status(
        queue.redis_client, job_id,
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


@router.post("/{plan_id}/generate-images-batch", summary="Batch generate images for multiple posts")
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
        queue_payload = json.dumps({
            "job_id": job_id,
            "plan_id": plan_id,
            "post_id": post_id,
            "user_id": user_id,
        })
        await queue.redis_client.rpush("queue:social_image_jobs", queue_payload)
        await set_job_status(
            queue.redis_client, job_id,
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


@router.post("/{plan_id}/post/{post_id}/regenerate", summary="Regenerate content or image for a post (2-4 pts)")
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
        raise HTTPException(status_code=400, detail="regenerate must be 'text', 'image', or 'both'")

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
            service="social_plan_regenerate_text" if regen == "text" else "social_plan_regenerate_image",
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
                {"$set": {
                    "posts.$.hook": new_content["hook"],
                    "posts.$.caption": new_content["caption"],
                    "posts.$.hashtags": new_content["hashtags"],
                    "posts.$.image_prompt": new_content["image_prompt"],
                    "posts.$.cta": new_content["cta"],
                    "updated_at": now,
                }},
            )
            result["new_content"] = new_content
        except Exception as e:
            logger.error(f"Text regen failed for {post_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Content regeneration failed: {str(e)}")

    # Queue image generation
    if regen in ("image", "both"):
        job_id = f"img_{uuid.uuid4().hex[:16]}"
        queue = await _get_social_image_queue()
        queue_payload = json.dumps({
            "job_id": job_id,
            "plan_id": plan_id,
            "post_id": post_id,
            "user_id": user_id,
        })
        await queue.redis_client.rpush("queue:social_image_jobs", queue_payload)
        await set_job_status(
            queue.redis_client, job_id,
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
