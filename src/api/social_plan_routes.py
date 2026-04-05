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
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.client import Config
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
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

# VND price for each package (1 point = 1,000 VND)
PACKAGE_VND_MAP = {
    "30posts_0img": 100_000,
    "30posts_1img": 300_000,
    "30posts_2img": 500_000,
    "60posts_0img": 150_000,
    "60posts_1img": 600_000,
    "60posts_2img": 1_000_000,
    "60posts_3img": 1_400_000,
    "60posts_4img": 1_800_000,
}

# Content generation quota per package (how many posts can get content generated free)
PACKAGE_QUOTA_MAP = {
    "30posts_0img": 30,
    "30posts_1img": 30,
    "30posts_2img": 30,
    "60posts_0img": 60,
    "60posts_1img": 60,
    "60posts_2img": 60,
    "60posts_3img": 60,
    "60posts_4img": 60,
}

# Image generation quota per package (images_per_post × posts)
PACKAGE_IMAGE_QUOTA_MAP = {
    "30posts_0img": 0,
    "30posts_1img": 30,
    "30posts_2img": 60,
    "60posts_0img": 0,
    "60posts_1img": 60,
    "60posts_2img": 120,
    "60posts_3img": 180,
    "60posts_4img": 240,
}

POINTS_REGEN_IMAGE = 4
POINTS_REGEN_TEXT = 2
POINTS_RETRY_PLAN = 50

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
    campaign_name: Optional[str] = Form(None),
    goals: Optional[str] = Form(None),  # Free text: what the user wants to achieve
    comparison_id: Optional[str] = Form(None),  # bc_xxx from Social Audit (Phase 1)
    business_pdf_asset_id: Optional[str] = Form(None),  # asset_id of business info PDF
    product_pdf_asset_id: Optional[str] = Form(None),  # asset_id of product list PDF
    payment_order_id: Optional[str] = Form(
        None
    ),  # PLAN-xxx from SEPAY cash payment flow
    tiktok_data_file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new AI social marketing plan.
    Payment path A: Deducts package points upfront (default).
    Payment path B: Accepts payment_order_id (PLAN-xxx) from completed SEPAY cash payment
                    — skips points deduction when verified.
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

    # Payment gate — Path B: verify SEPAY order or Path A: deduct points
    if payment_order_id:
        # Verify the PLAN- order belongs to this user, matches the package, and is completed
        order = db["content_plan_orders"].find_one({"order_id": payment_order_id})
        if not order:
            raise HTTPException(status_code=402, detail="Đơn thanh toán không tồn tại.")
        if order.get("user_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Đơn thanh toán không thuộc về bạn."
            )
        if order.get("status") != "completed":
            raise HTTPException(
                status_code=402, detail="Đơn thanh toán chưa được xác nhận."
            )
        if order.get("plan_created"):
            raise HTTPException(
                status_code=400,
                detail="Đơn thanh toán này đã được sử dụng để tạo kế hoạch.",
            )
        if order.get("package") != package:
            raise HTTPException(
                status_code=400,
                detail=f"Gói trong đơn thanh toán ({order.get('package')}) không khớp với gói được chọn ({package}).",
            )
        # Mark order as used (will set plan_created=True after plan is created)
        logger.info(
            f"Content plan using SEPAY order {payment_order_id} for user {user_id}"
        )
    else:
        # Path A: deduct points
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
        # Content Engine v2
        "campaign_name": campaign_name or "",
        "goals": goals or "",
        "comparison_id": comparison_id or "",
        "business_pdf_asset_id": business_pdf_asset_id or "",
        "product_pdf_asset_id": product_pdf_asset_id or "",
        "package": package,
    }

    # Link asset drafts to this plan (brand images + brand docs + style refs + PDF assets)
    pdf_asset_ids = [x for x in [business_pdf_asset_id, product_pdf_asset_id] if x]
    all_asset_ids = asset_ids + brand_context_ids + style_ids + pdf_asset_ids
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
        "tiktok_data": tiktok_data,  # stored for retry capability
        "brand_data": {"websites": [], "tiktok_posts": []},
        "analysis_summaries": {},
        "brand_dna": {},
        "posts": [],
        "total_posts": 0,
        "images_generated": 0,
        "content_generated": 0,  # number of posts with content (hook/caption) generated
        "content_quota": PACKAGE_QUOTA_MAP[
            package
        ],  # free content gen quota from package
        "image_quota": PACKAGE_IMAGE_QUOTA_MAP[
            package
        ],  # free image gen quota from package
        "job_id": job_id,
        "points_spent": required_points if not payment_order_id else 0,
        "payment_order_id": payment_order_id or None,
    }
    db["social_plans"].insert_one(plan_doc)

    # If paid via SEPAY order, mark order as used
    if payment_order_id:
        db["content_plan_orders"].update_one(
            {"order_id": payment_order_id},
            {
                "$set": {
                    "plan_created": True,
                    "plan_id": plan_id,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

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
            "comparison_id": comparison_id or "",
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


# ── POST /assets/parse-pdf ─────────────────────────────────
class ParsePdfRequest(BaseModel):
    asset_id: str
    parse_type: str  # "business_info" | "product_list"


@router.post("/assets/parse-pdf", summary="Parse a PDF asset into structured data")
async def parse_pdf_asset(
    body: ParsePdfRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Parse a previously uploaded PDF asset (brand_doc type) using GPT-4.
    parse_type: "business_info" → brand/company info dict
                "product_list"  → {products: [...], total: N}
    Result is saved back to the asset document as `parsed_data`.
    """
    from src.services.pdf_parser import parse_asset_pdf
    from src.clients.chatgpt_client import ChatGPTClient

    user_id = current_user["uid"]
    db = _get_db()

    asset_doc = db["social_plan_assets"].find_one(
        {"asset_id": body.asset_id, "user_id": user_id}, {"_id": 0}
    )
    if not asset_doc:
        raise HTTPException(status_code=404, detail="Asset not found")

    if body.parse_type not in ("business_info", "product_list"):
        raise HTTPException(
            status_code=400,
            detail="parse_type must be 'business_info' or 'product_list'",
        )

    chatgpt = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY", ""))
    try:
        result = await parse_asset_pdf(asset_doc, body.parse_type, chatgpt)
    except Exception as e:
        logger.error(f"[parse-pdf] Failed for asset {body.asset_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"PDF parsing failed: {str(e)[:200]}"
        )

    db["social_plan_assets"].update_one(
        {"asset_id": body.asset_id},
        {"$set": {"parsed_data": result, "parse_type": body.parse_type}},
    )

    return {"asset_id": body.asset_id, "parse_type": body.parse_type, "result": result}


# ── GET /competitor-social/brand-comparisons/{comparison_id}/strategy-hint ──
@router.get(
    "/competitor-social/brand-comparisons/{comparison_id}/strategy-hint",
    summary="Return strategy hints from a Social Audit report",
)
async def get_strategy_hint(
    comparison_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Returns the strategic section of a brand comparison report:
    my_strengths, my_weaknesses, improvement_plan,
    content_strategy_recommendations, design_recommendations, summary.
    """
    user_id = current_user["uid"]
    db = _get_db()

    doc = db["brand_comparisons"].find_one(
        {"comparison_id": comparison_id, "user_id": user_id},
        {"_id": 0, "comparison_id": 1, "brand_comparison": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Social Audit report not found")

    bc = doc.get("brand_comparison") or {}
    return {
        "comparison_id": comparison_id,
        "strategy": {
            "my_strengths": bc.get("my_strengths", []),
            "my_weaknesses": bc.get("my_weaknesses", []),
            "improvement_plan": bc.get("improvement_plan", ""),
            "content_strategy_recommendations": bc.get(
                "content_strategy_recommendations", []
            ),
            "design_recommendations": bc.get("design_recommendations", []),
            "summary": bc.get("summary", ""),
        },
    }


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

POINTS_BRAND_COMPARE = (
    200  # cost per brand-compare job (3 competitors, 1 channel) = 9.9 USDT
)
AUDIT_PRICE_VND = 200_000  # cash price per audit (SePay)
ADMIN_EMAIL = "tienhoi.lh@gmail.com"


# ── Helper: enqueue brand-compare job (shared between points & cash flows) ──


def _normalize_engagement_metrics(em):
    """Normalize metrics to always use nested structure {all, has_pinned_split}.
    Old Facebook audits store flat metrics; this wraps them for consistent frontend access.
    """
    if em is None:
        return {"has_pinned_split": False, "all": {}}
    if isinstance(em, dict) and "has_pinned_split" in em:
        return em  # Already normalized (TikTok with pinned split)
    # Flat metrics from Facebook/Instagram → wrap under "all"
    return {"has_pinned_split": False, "all": em}


def _normalize_engagement_summary(summary: list) -> list:
    """Ensure each engagement_summary item has normalized metrics structure."""
    if not summary:
        return summary
    result = []
    for item in summary:
        item = dict(item)
        if "metrics" in item:
            item["metrics"] = _normalize_engagement_metrics(item["metrics"])
        result.append(item)
    return result


async def _enqueue_brand_compare(
    *,
    user_id: str,
    my_url: str,
    comp_urls: list,
    language: str,
    fc_map: dict,
    screenshot_urls_list: list,
    brand_names: dict = {},
) -> str:
    import json as _json

    job_id = f"bc_{uuid.uuid4().hex[:16]}"
    queue = await _get_social_plan_queue()
    await queue.redis_client.lpush(
        "queue:social_plan_jobs",
        _json.dumps(
            {
                "task_type": "brand_compare",
                "job_id": job_id,
                "user_id": user_id,
                "my_url": my_url,
                "competitor_urls": comp_urls,
                "language": language,
                "followers_counts": fc_map,
                "screenshot_urls": screenshot_urls_list,
                "brand_names": brand_names,
            }
        ),
    )
    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        my_url=my_url,
        competitor_urls=comp_urls,
    )
    return job_id


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT CASH PAYMENT FLOW  (SePay 100,000 VND → 1 audit credit)
# ══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/competitor-social/brand-compare-checkout",
    summary="Create a cash payment order for 1 brand-compare audit (100,000 VND)",
)
async def brand_compare_checkout(
    current_user: dict = Depends(get_current_user),
):
    """
    Step 1 of the cash payment flow.
    Creates an order in `audit_cash_orders` (status: pending) and returns order_id.
    Frontend then calls payment-service POST /api/payment/audit-purchase with this order_id
    to get the SePay checkout form.
    """
    import json as _json

    user_id = current_user["uid"]
    db = _get_db()

    timestamp = int(datetime.utcnow().timestamp())
    user_short = user_id[:8]
    order_id = f"AUDIT-{timestamp}-{user_short}"

    order_doc = {
        "order_id": order_id,
        "user_id": user_id,
        "user_email": current_user.get("email", ""),
        "price_vnd": AUDIT_PRICE_VND,
        "status": "pending",
        "credit_granted": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=24),
    }
    db["audit_cash_orders"].insert_one(order_doc)

    return {
        "order_id": order_id,
        "price_vnd": AUDIT_PRICE_VND,
        "message": "Order created. Call payment-service POST /api/payment/audit-purchase with this order_id.",
    }


@router.get(
    "/competitor-social/audit-credit",
    summary="Get current audit credit balance for the logged-in user",
)
async def get_audit_credit(current_user: dict = Depends(get_current_user)):
    """Returns available (unused) audit credits from completed SePay payments."""
    db = _get_db()
    credits = db["audit_cash_orders"].count_documents(
        {
            "user_id": current_user["uid"],
            "status": "completed",
            "credit_granted": True,
            "credit_used": {"$ne": True},
        }
    )
    return {"available_credits": credits}


@router.post(
    "/competitor-social/grant-audit-credit",
    summary="[INTERNAL] Grant 1 audit credit after SePay payment confirmed",
    include_in_schema=False,
)
async def grant_audit_credit(
    order_id: str,
    request: Request,
):
    """
    Called internally by the Node.js payment-service webhook after SePay confirms ORDER_PAID.
    Marks the order as credit_granted=True so the user can run 1 audit.
    Protected by X-Service-Secret header.
    """
    secret = request.headers.get("X-Service-Secret", "")
    expected = os.environ.get("API_SECRET_KEY", "")
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

    db = _get_db()
    order = db["audit_cash_orders"].find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.get("credit_granted"):
        return {"success": True, "message": "Already granted"}

    if order.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Order status is '{order.get('status')}', expected 'completed'",
        )

    db["audit_cash_orders"].update_one(
        {"order_id": order_id},
        {"$set": {"credit_granted": True, "updated_at": datetime.utcnow()}},
    )
    logger.info(
        f"✅ Audit credit granted for order {order_id}, user {order['user_id']}"
    )
    return {"success": True, "order_id": order_id, "user_id": order["user_id"]}


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT PLAN CASH PAYMENT FLOW  (SePay → skip points deduction in /create)
# ══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/content-plan-order",
    summary="Create a cash payment order for a Content Plan package",
)
async def create_content_plan_order(
    package: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Step 1 of the SEPAY payment flow for Content Plan.
    Creates an order in `content_plan_orders` (status: pending) and returns order_id.
    Frontend then calls payment-service POST /api/payment/content-plan/checkout with this order_id
    to get the SePay checkout form.
    After payment, poll GET /api/payment/status/PLAN-xxx until status = 'completed',
    then call POST /create with payment_order_id=PLAN-xxx to skip points deduction.
    """
    if package not in PACKAGE_VND_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid package: {package}. Valid: {list(PACKAGE_VND_MAP.keys())}",
        )

    user_id = current_user["uid"]
    db = _get_db()

    timestamp = int(datetime.utcnow().timestamp())
    user_short = user_id[:8]
    order_id = f"PLAN-{timestamp}-{user_short}"
    price_vnd = PACKAGE_VND_MAP[package]

    order_doc = {
        "order_id": order_id,
        "user_id": user_id,
        "user_email": current_user.get("email", ""),
        "package": package,
        "price_vnd": price_vnd,
        "status": "pending",
        "plan_created": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=24),
    }
    db["content_plan_orders"].insert_one(order_doc)

    return {
        "order_id": order_id,
        "package": package,
        "price_vnd": price_vnd,
        "message": "Order created. Call payment-service POST /api/payment/content-plan/checkout with this order_id.",
    }


@router.post(
    "/content-plan-order/complete",
    summary="[INTERNAL] Mark content plan order as completed after SePay webhook",
    include_in_schema=False,
)
async def complete_content_plan_order(
    order_id: str,
    request: Request,
):
    """
    Internal endpoint called by payment-service webhook after SePay IPN.
    Marks `content_plan_orders.status = 'completed'`.
    Requires X-Service-Secret header.
    """
    service_secret = os.getenv("API_SECRET_KEY", "")
    if not service_secret or request.headers.get("X-Service-Secret") != service_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db = _get_db()
    order = db["content_plan_orders"].find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.get("status") == "completed":
        return {"success": True, "message": "Already completed"}

    db["content_plan_orders"].update_one(
        {"order_id": order_id},
        {
            "$set": {
                "status": "completed",
                "paid_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        },
    )
    logger.info(f"✅ Content plan order completed: {order_id}, user {order['user_id']}")
    return {"success": True, "order_id": order_id, "user_id": order["user_id"]}


@router.post(
    "/competitor-social/brand-compare-with-credit",
    summary="[CREDIT] Run brand-compare using 1 purchased audit credit (no points deducted)",
)
async def brand_compare_with_credit(
    my_url: str = Form(...),
    competitor_urls: str = Form(
        ...,
        description="JSON array of 1–3 competitor URLs",
    ),
    language: str = Form("vi"),
    followers_counts: Optional[str] = Form(None),
    my_brand_name: Optional[str] = Form(
        None,
        description="Display name for your brand/page. Required for Facebook.",
    ),
    competitor_brand_names: Optional[str] = Form(
        None,
        description="JSON object mapping competitor URL → brand display name.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Run a brand-compare using 1 purchased audit credit (from SePay cash payment).
    Deducts 1 unused credit from audit_cash_orders.
    Same result as the points-based flow.
    """
    import json as _json

    user_id = current_user["uid"]
    db = _get_db()

    # Find and claim one unused credit
    result = db["audit_cash_orders"].find_one_and_update(
        {
            "user_id": user_id,
            "status": "completed",
            "credit_granted": True,
            "credit_used": {"$ne": True},
        },
        {
            "$set": {
                "credit_used": True,
                "credit_used_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        },
        sort=[("created_at", 1)],  # use oldest credit first
    )
    if not result:
        raise HTTPException(
            status_code=402,
            detail="No available audit credits. Please purchase an audit at /competitor-social/brand-compare-checkout.",
        )

    try:
        comp_urls: List[str] = _json.loads(competitor_urls)
        if not isinstance(comp_urls, list) or not comp_urls:
            raise ValueError
        comp_urls = comp_urls[:3]
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid competitor_urls JSON array"
        )

    fc_map = {}
    if followers_counts:
        try:
            fc_map = _json.loads(followers_counts)
        except Exception:
            pass

    # Build brand names map
    bn_map: dict = {}
    if my_brand_name:
        bn_map[my_url] = my_brand_name
    if competitor_brand_names:
        try:
            parsed_bn = _json.loads(competitor_brand_names)
            if isinstance(parsed_bn, dict):
                bn_map.update(parsed_bn)
        except Exception:
            pass

    all_urls = [my_url] + comp_urls

    job_id = await _enqueue_brand_compare(
        user_id=user_id,
        my_url=my_url,
        comp_urls=comp_urls,
        language=language,
        fc_map=fc_map,
        screenshot_urls_list=[None] * len(all_urls),
        brand_names=bn_map,
    )

    # Link job to the order
    db["audit_cash_orders"].update_one(
        {"order_id": result["order_id"]},
        {"$set": {"job_id": job_id}},
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "my_url": my_url,
        "competitor_urls": comp_urls,
        "credit_used": result["order_id"],
        "message": "Analysis queued. Poll /competitor-social/brand-compare/{job_id} for status.",
    }


@router.post(
    "/competitor-social/audit-register",
    summary="[FREE] Register business info and get 1 free social audit (1 competitor)",
)
async def audit_register(
    company_name: str = Form(..., description="Tên doanh nghiệp / thương hiệu"),
    job_title: str = Form(
        ...,
        description="Vị trí công việc (e.g. Social Media Manager, Marketing Director)",
    ),
    contact_email: str = Form(..., description="Email liên lạc"),
    contact_linkedin: Optional[str] = Form(None, description="LinkedIn URL (tùy chọn)"),
    my_url: str = Form(
        ..., description="URL trang social của doanh nghiệp (TikTok, FB, IG)"
    ),
    competitor_url: str = Form(..., description="URL 1 đối thủ cần phân tích"),
    language: str = Form("vi", description="Ngôn ngữ báo cáo: vi hoặc en"),
    followers_counts: Optional[str] = Form(
        None,
        description='JSON object mapping URL → follower count, e.g. {"https://fb.com/page": 50000, "https://fb.com/competitor": 120000}',
    ),
    competitor_brand_name: Optional[str] = Form(
        None, description="Display name of the competitor brand"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Đăng ký thông tin doanh nghiệp để nhận **1 lần phân tích Social Audit MIỄN PHÍ** (1 đối thủ).

    - Lưu thông tin đăng ký vào `audit_registrations`
    - Kiểm tra mỗi user chỉ được dùng free 1 lần
    - Gửi email thông báo đến admin (tienhoi.lh@gmail.com)
    - Enqueue job và trả về job_id để frontend poll kết quả

    **Nâng cấp lên 3 đối thủ:** dùng endpoint `/competitor-social/brand-compare` với 200 điểm.
    """
    import json as _json

    user_id = current_user["uid"]
    db = _get_db()

    # Check if user already used their free audit
    existing = db["audit_registrations"].find_one(
        {
            "user_id": user_id,
            "free_used": True,
        }
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Bạn đã sử dụng lượt phân tích miễn phí. Vui lòng dùng điểm hoặc mua audit để tiếp tục.",
        )

    # Enqueue the free job (1 competitor only)
    comp_urls = [competitor_url]
    import json as _json

    fc_map: dict = {}
    if followers_counts:
        try:
            fc_map = _json.loads(followers_counts)
        except Exception:
            pass

    # company_name doubles as brand display name for "my" page
    bn_map: dict = {my_url: company_name}
    if competitor_brand_name:
        bn_map[competitor_url] = competitor_brand_name

    job_id = await _enqueue_brand_compare(
        user_id=user_id,
        my_url=my_url,
        comp_urls=comp_urls,
        language=language,
        fc_map=fc_map,
        screenshot_urls_list=[None, None],
        brand_names=bn_map,
    )

    # Save registration
    now = datetime.utcnow()
    reg_doc = {
        "user_id": user_id,
        "user_email": current_user.get("email", ""),
        "company_name": company_name,
        "job_title": job_title,
        "contact_email": contact_email,
        "contact_linkedin": contact_linkedin or "",
        "my_url": my_url,
        "competitor_url": competitor_url,
        "language": language,
        "job_id": job_id,
        "free_used": True,
        "created_at": now,
    }
    db["audit_registrations"].insert_one(reg_doc)

    # Send admin notification (fire-and-forget)
    try:
        from src.services.brevo_email_service import get_brevo_service

        brevo = get_brevo_service()
        html_body = f"""
<h2>🔍 Đăng ký Social Audit mới</h2>
<table style="border-collapse:collapse;width:100%">
  <tr><td style="padding:6px;font-weight:bold">Doanh nghiệp</td><td style="padding:6px">{company_name}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">Vị trí</td><td style="padding:6px">{job_title}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">Email</td><td style="padding:6px"><a href="mailto:{contact_email}">{contact_email}</a></td></tr>
  <tr><td style="padding:6px;font-weight:bold">LinkedIn</td><td style="padding:6px">{contact_linkedin or "—"}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">Trang của họ</td><td style="padding:6px"><a href="{my_url}">{my_url}</a></td></tr>
  <tr><td style="padding:6px;font-weight:bold">Đối thủ</td><td style="padding:6px"><a href="{competitor_url}">{competitor_url}</a></td></tr>
  <tr><td style="padding:6px;font-weight:bold">Ngôn ngữ</td><td style="padding:6px">{language}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">Job ID</td><td style="padding:6px">{job_id}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">User ID</td><td style="padding:6px">{user_id}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">User Email</td><td style="padding:6px">{current_user.get("email", "")}</td></tr>
  <tr><td style="padding:6px;font-weight:bold">Thời gian</td><td style="padding:6px">{now.strftime("%Y-%m-%d %H:%M UTC")}</td></tr>
</table>
"""
        brevo.send_email(
            to_email=ADMIN_EMAIL,
            subject=f"[WordAI] Social Audit mới: {company_name} — {job_title}",
            html_body=html_body,
        )
    except Exception as e:
        logger.warning(f"Admin email failed (non-blocking): {e}")

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Đăng ký thành công! Phân tích đang được xử lý, poll kết quả tại /competitor-social/brand-compare-demo/{job_id}",
        "my_url": my_url,
        "competitor_url": competitor_url,
        "upgrade_hint": "Để phân tích 3 đối thủ, dùng /competitor-social/brand-compare (200 điểm).",
    }


@router.get(
    "/competitor-social/audit-register/check",
    summary="Check if current user has used their free audit",
)
async def audit_register_check(current_user: dict = Depends(get_current_user)):
    """Returns whether the user has already used their free social audit registration."""
    db = _get_db()
    reg = db["audit_registrations"].find_one(
        {"user_id": current_user["uid"], "free_used": True},
        {"_id": 0, "company_name": 1, "job_id": 1, "created_at": 1},
    )
    if reg:
        return {
            "free_used": True,
            "company_name": reg.get("company_name"),
            "job_id": reg.get("job_id"),
            "registered_at": reg.get("created_at"),
        }
    return {"free_used": False}


@router.post(
    "/competitor-social/brand-compare-demo",
    summary="[FREE TEST] Brand vs competitors — no auth, no points, just enqueues",
)
async def brand_compare_demo(
    my_url: str = Form(..., description="My own social page URL"),
    competitor_urls: str = Form(
        ...,
        description='JSON array of 1–3 competitor URLs, e.g. ["url1","url2","url3"]',
    ),
    language: str = Form("vi"),
):
    """
    No-auth demo: enqueues a brand-compare job using the existing social_plan_worker.
    Auto-screenshots all pages with SCREENSHOTAPI_API_KEY, then runs batch ChatGPT Vision
    + DeepSeek R1 comparative analysis.

    Poll with: GET /competitor-social/brand-compare-demo/{job_id}
    """
    import json as _json

    try:
        comp_urls: List[str] = _json.loads(competitor_urls)
        if not isinstance(comp_urls, list) or not comp_urls:
            raise ValueError("must be a non-empty JSON array")
        comp_urls = comp_urls[:3]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid competitor_urls: {e}")

    job_id = f"bcd_{uuid.uuid4().hex[:14]}"
    queue = await _get_social_plan_queue()
    await queue.redis_client.lpush(
        "queue:social_plan_jobs",
        _json.dumps(
            {
                "task_type": "brand_compare",
                "job_id": job_id,
                "user_id": "demo",
                "my_url": my_url,
                "competitor_urls": comp_urls,
                "language": language,
                "followers_counts": {},
                "screenshot_urls": [],
            }
        ),
    )
    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id="demo",
        my_url=my_url,
        competitor_urls=comp_urls,
    )
    return {
        "job_id": job_id,
        "status": "pending",
        "my_url": my_url,
        "competitor_urls": comp_urls,
        "poll_url": f"/api/v1/social-plan/competitor-social/brand-compare-demo/{job_id}",
    }


@router.get(
    "/competitor-social/brand-compare-demo/{job_id}",
    summary="[FREE] Poll demo brand-compare job status (no auth)",
)
async def brand_compare_demo_status(job_id: str):
    """Poll a demo brand-compare job by job_id (no auth required)."""
    queue = await _get_social_plan_queue()
    job = await get_job_status(queue.redis_client, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    return job


SHOWCASE_IDS = {
    "en": "bc_8709907e93af49f7",
    "vi": "bc_a3a0c534097c4722",
    "vi_facebook": "bc_1dbc7286f9594f6d",  # Chứng khoán SSI — Facebook demo
}


@router.get(
    "/competitor-social/brand-compare-showcase",
    summary="[PUBLIC] Get showcase brand-compare results (EN + VI) for landing page",
)
async def brand_compare_showcase():
    """
    Returns the two pre-computed showcase brand-compare reports (EN and VI).
    No authentication required — used for the /social-audit landing page demo.
    """
    db = _get_db()
    result = {}
    for lang, cid in SHOWCASE_IDS.items():
        doc = db["brand_comparisons"].find_one({"comparison_id": cid}, {"_id": 0})
        if doc:
            result[lang] = {"status": "completed", **doc}
    if not result:
        raise HTTPException(status_code=404, detail="Showcase data not available")
    return result


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

    # Recompute metrics with followers_count for engagement rate
    # For TikTok with pinned posts: recompute the split with followers included
    raw_metrics = scraped.get("engagement_metrics") or {}
    if effective_followers:
        posts = scraped["posts"]
        platform = scraped["platform"]
        has_pinned = any(p.get("is_pinned") for p in posts)
        if platform == "tiktok" and has_pinned:
            pinned_posts = [p for p in posts if p.get("is_pinned")]
            regular_posts = [p for p in posts if not p.get("is_pinned")]
            metrics = {
                "all": compute_engagement_metrics(
                    posts, followers_count=effective_followers
                ),
                "pinned": (
                    compute_engagement_metrics(
                        pinned_posts, followers_count=effective_followers
                    )
                    if pinned_posts
                    else None
                ),
                "regular": (
                    compute_engagement_metrics(
                        regular_posts, followers_count=effective_followers
                    )
                    if regular_posts
                    else None
                ),
                "has_pinned_split": True,
            }
        else:
            metrics = compute_engagement_metrics(
                posts, followers_count=effective_followers
            )
    else:
        metrics = raw_metrics

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


# ──────────────────────────────────────────────────────────────────────────────
# ③b BRAND vs COMPETITORS (my page + 3 competitor pages, queue-based)
#     100 pts — scrapes 4 pages + DeepSeek analysis + optional ChatGPT Vision
# ──────────────────────────────────────────────────────────────────────────────


@router.get(
    "/competitor-social/brand-compare",
    summary="List saved brand comparison reports for the current user (summary only)",
)
async def list_brand_comparisons_alias(
    page: int = 1,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """List brand comparisons for current user — summary fields only (no heavy analysis data)."""
    db = _get_db()
    skip = (page - 1) * limit
    # Only return lightweight summary fields for the list view
    projection = {
        "_id": 0,
        "comparison_id": 1,
        "job_id": 1,
        "language": 1,
        "my_url": 1,
        "competitor_urls": 1,
        "created_at": 1,
        "engagement_summary": 1,
    }
    items = list(
        db["brand_comparisons"]
        .find({"user_id": current_user["uid"]}, projection)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return {"page": page, "limit": limit, "items": items}


@router.post(
    "/competitor-social/brand-compare",
    summary="[100 pts] Analyze my brand vs up to 3 competitors with full report",
)
async def brand_compare_enqueue(
    my_url: str = Form(..., description="My own social page URL"),
    competitor_urls: str = Form(
        ...,
        description='JSON array of 1–3 competitor URLs (same or different platform), e.g. ["url1","url2"]',
    ),
    language: str = Form("vi", description="Response language: vi, en, fr, …"),
    followers_counts: Optional[str] = Form(
        None,
        description='Optional JSON object mapping URL → follower count for engagement rate, e.g. {"https://fb.com/page": 50000}',
    ),
    my_brand_name: Optional[str] = Form(
        None,
        description="Display name for your brand/page (e.g. 'WordAI'). Required for Facebook pages where followers cannot be auto-scraped.",
    ),
    competitor_brand_names: Optional[str] = Form(
        None,
        description='Optional JSON object mapping competitor URL → brand display name, e.g. {"https://fb.com/page": "BrandX"}',
    ),
    screenshots: Optional[List[UploadFile]] = File(
        None,
        description="Optional screenshots (1 image per page, ordered: my page first then competitors). Sent to ChatGPT Vision for design analysis.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Queue a brand competitiveness analysis job.

    The job:
    1. Scrapes my page + each competitor page via Apify (15 posts each)
    2. Analyzes each page individually with DeepSeek R1
    3. If screenshots uploaded → ChatGPT Vision analyzes design style per page
    4. Runs a final comparative analysis with DeepSeek R1:
       → my_strengths, my_weaknesses, competitor_advantages,
         strategic_gap, improvement_plan, content_strategy_recommendations,
         design_recommendations (if screenshots), summary

    Returns immediately with job_id. Poll GET /competitor-social/brand-compare/{job_id}.
    Cost: -100 points.
    """
    import json as _json

    user_id = current_user["uid"]

    # ── Parse inputs ─────────────────────────────────────────────────────────
    try:
        comp_urls: List[str] = _json.loads(competitor_urls)
        if not isinstance(comp_urls, list) or not comp_urls:
            raise ValueError("must be a non-empty JSON array")
        comp_urls = comp_urls[:3]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid competitor_urls: {e}")

    fc_map: dict = {}
    if followers_counts:
        try:
            fc_map = _json.loads(followers_counts)
        except Exception:
            pass

    # ── Build brand names map ─────────────────────────────────────────────────
    bn_map: dict = {}
    if my_brand_name:
        bn_map[my_url] = my_brand_name
    if competitor_brand_names:
        try:
            parsed_bn = _json.loads(competitor_brand_names)
            if isinstance(parsed_bn, dict):
                bn_map.update(parsed_bn)
        except Exception:
            pass

    # ── Deduct points ─────────────────────────────────────────────────────────
    points_svc = get_points_service()
    try:
        await points_svc.deduct_points(
            user_id=user_id,
            amount=POINTS_BRAND_COMPARE,
            service="brand_compare",
            description=f"Brand vs competitors analysis: {my_url}",
        )
    except InsufficientPointsError as e:
        raise HTTPException(status_code=402, detail=str(e))

    # ── Upload screenshots to R2 (before enqueue, files can't go through Redis) ─
    screenshot_urls_list: List[Optional[str]] = []
    if screenshots:
        s3_client = _get_s3_client()
        for i, upload in enumerate(screenshots[:4]):  # max 4 (1 my + 3 competitors)
            try:
                content_bytes = await upload.read()
                ext = (upload.filename or "").rsplit(".", 1)[-1].lower() or "jpg"
                r2_key = f"brand-compare/{user_id}/{uuid.uuid4().hex}.{ext}"
                s3_client.put_object(
                    Bucket=R2_BUCKET,
                    Key=r2_key,
                    Body=content_bytes,
                    ContentType=upload.content_type or "image/jpeg",
                )
                screenshot_urls_list.append(f"{R2_PUBLIC_URL}/{r2_key}")
            except Exception as e:
                logger.error("Screenshot upload failed (index %d): %s", i, e)
                screenshot_urls_list.append(None)

    # Pad to length of all_urls (my + competitors)
    all_urls = [my_url] + comp_urls
    while len(screenshot_urls_list) < len(all_urls):
        screenshot_urls_list.append(None)

    # ── Enqueue ───────────────────────────────────────────────────────────────
    job_id = await _enqueue_brand_compare(
        user_id=user_id,
        my_url=my_url,
        comp_urls=comp_urls,
        language=language,
        fc_map=fc_map,
        screenshot_urls_list=screenshot_urls_list,
        brand_names=bn_map,
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "my_url": my_url,
        "competitor_urls": comp_urls,
        "points_deducted": POINTS_BRAND_COMPARE,
        "message": "Analysis queued. Poll /competitor-social/brand-compare/{job_id} for status.",
    }


@router.get(
    "/competitor-social/brand-compare/{id}",
    summary="Get full detail of a brand-compare job (by job_id or comparison_id)",
)
async def brand_compare_status(
    id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get full detail of a brand-compare job.
    Accepts either job_id (e.g. bc_xxx / bcd_xxx) or comparison_id (e.g. bc_xxx).
    - If job is still in Redis (in-progress): returns live status.
    - If completed/expired from Redis: loads full result from MongoDB.
    """
    queue = await _get_social_plan_queue()
    # Try Redis first (job may still be processing)
    job = await get_job_status(queue.redis_client, id)

    if not job:
        # Load from MongoDB — accept both job_id and comparison_id
        db = _get_db()
        doc = db["brand_comparisons"].find_one(
            {
                "$or": [{"job_id": id}, {"comparison_id": id}],
                "user_id": current_user["uid"],
            },
            {"_id": 0},
        )
        if doc:
            # Normalize engagement_summary metrics for backward compat (old flat Facebook data)
            if "engagement_summary" in doc:
                doc["engagement_summary"] = _normalize_engagement_summary(
                    doc["engagement_summary"]
                )
            return {"status": "completed", **doc}
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("user_id") and job["user_id"] != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Not your job")

    # Normalize in-Redis job too (completed jobs cached in Redis)
    if job.get("engagement_summary"):
        job["engagement_summary"] = _normalize_engagement_summary(
            job["engagement_summary"]
        )

    return job


@router.get(
    "/competitor-social/brand-comparisons",
    summary="List saved brand comparison reports for the current user",
)
async def list_brand_comparisons(
    page: int = 1,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    db = _get_db()
    skip = (page - 1) * limit
    items = list(
        db["brand_comparisons"]
        .find({"user_id": current_user["uid"]}, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return {"page": page, "limit": limit, "items": items}


# ──────────────────────────────────────────────────────────
# ④ DYNAMIC ROUTES (plan_id param — MUST be AFTER static routes)
# ──────────────────────────────────────────────────────────


# ── GET /{plan_id}/config ───────────────────────────────────
@router.get("/{plan_id}/config", summary="Get editable plan config (before retry)")
async def get_plan_config(
    plan_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Return the editable config fields for a plan.
    Used to let the user review and modify plan settings before retrying.
    """
    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {
            "_id": 0,
            "plan_id": 1,
            "status": 1,
            "package": 1,
            "config": 1,
            "total_posts": 1,
            "points_spent": 1,
            "created_at": 1,
        },
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return {
        "plan_id": plan["plan_id"],
        "status": plan.get("status"),
        "package": plan.get("package"),
        "total_posts": plan.get("total_posts", 0),
        "points_spent": plan.get("points_spent", 0),
        "retry_cost": POINTS_RETRY_PLAN,
        "created_at": plan.get("created_at"),
        "config": plan.get("config", {}),
    }


# ── PATCH /{plan_id}/config ─────────────────────────────────
class UpdatePlanConfigRequest(BaseModel):
    business_name: Optional[str] = None
    campaign_name: Optional[str] = None
    campaign_description: Optional[str] = None
    goals: Optional[str] = None
    campaign_goal: Optional[str] = None
    industry: Optional[str] = None
    target_audience: Optional[str] = None
    language: Optional[str] = None
    tone: Optional[str] = None
    image_style: Optional[str] = None
    posts_per_week: Optional[int] = None
    start_date: Optional[str] = None
    platforms: Optional[List[str]] = None
    website_urls: Optional[List[str]] = None
    competitors: Optional[List[dict]] = None
    products: Optional[List[dict]] = None


@router.patch("/{plan_id}/config", summary="Update plan config before retry")
async def update_plan_config(
    plan_id: str,
    body: UpdatePlanConfigRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update editable config fields on a plan.
    Can be used before retrying a failed or plan_ready plan.
    Only updates fields explicitly provided in the request body.
    Free — no points deducted.
    """
    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {"_id": 0, "plan_id": 1, "status": 1, "config": 1},
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Build partial config update — only supplied fields
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    config_updates = {f"config.{k}": v for k, v in updates.items()}
    config_updates["updated_at"] = datetime.now(timezone.utc)

    db["social_plans"].update_one(
        {"plan_id": plan_id},
        {"$set": config_updates},
    )

    return {
        "plan_id": plan_id,
        "updated_fields": list(updates.keys()),
        "message": "Config cập nhật thành công. Gọi POST /retry để tạo lại kế hoạch.",
    }


# ── POST /{plan_id}/retry ──────────────────────────────────
@router.post("/{plan_id}/retry", summary="Retry a failed or stuck plan")
async def retry_social_plan(
    plan_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Re-enqueue a failed, stuck, or plan_ready plan using its (possibly updated) config.
    Costs 50 points per retry. Points deducted upfront.
    """
    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {
            "_id": 0,
            "plan_id": 1,
            "status": 1,
            "config": 1,
            "asset_ids": 1,
            "tiktok_data": 1,
            "package": 1,
        },
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    allowed_statuses = ("failed", "processing", "plan_ready")
    if plan.get("status") not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Plan không ở trạng thái có thể retry (status: {plan.get('status')}). Chỉ retry được khi status là: {', '.join(allowed_statuses)}",
        )

    # Deduct 50 points
    points_service = get_points_service()
    try:
        await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_RETRY_PLAN,
            service="social_plan_retry",
            description=f"Social Plan Retry - {plan_id}",
        )
    except InsufficientPointsError:
        raise HTTPException(
            status_code=402,
            detail=f"Không đủ điểm. Cần {POINTS_RETRY_PLAN} điểm để retry kế hoạch.",
        )

    new_job_id = f"job_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)

    # Reset plan to processing with new job_id
    db["social_plans"].update_one(
        {"plan_id": plan_id},
        {
            "$set": {
                "status": "processing",
                "job_id": new_job_id,
                "error": None,
                "updated_at": now,
                # Reset generated data so worker starts fresh
                "brand_data": {"websites": [], "tiktok_posts": []},
                "analysis_summaries": {},
                "brand_dna": {},
                "posts": [],
                "total_posts": 0,
                "content_generated": 0,
                "images_generated": 0,
            }
        },
    )

    # Re-enqueue with saved config and tiktok_data
    queue = await _get_social_plan_queue()
    config = plan.get("config", {})
    queue_payload = json.dumps(
        {
            "job_id": new_job_id,
            "plan_id": plan_id,
            "user_id": user_id,
            "config": config,
            "brand_asset_ids": plan.get("asset_ids", []),
            "tiktok_data": plan.get("tiktok_data"),
            "comparison_id": config.get("comparison_id", ""),
        }
    )
    await queue.redis_client.rpush("queue:social_plan_jobs", queue_payload)

    await set_job_status(
        queue.redis_client,
        new_job_id,
        status="pending",
        user_id=user_id,
        plan_id=plan_id,
        step="queued",
        progress=0,
        message="Đang chờ xử lý lại...",
    )

    logger.info(
        f"[Retry] Plan {plan_id} re-queued as job {new_job_id} by user {user_id}"
    )

    return {
        "plan_id": plan_id,
        "job_id": new_job_id,
        "status": "processing",
        "points_spent": POINTS_RETRY_PLAN,
        "message": "Plan đã được đưa vào hàng đợi để xử lý lại.",
    }


# ── POST /{plan_id}/generate-content ──────────────────────
class GenerateContentRequest(BaseModel):
    post_ids: Optional[List[str]] = (
        None  # subset; omit to generate for all without content
    )


@router.post(
    "/{plan_id}/generate-content",
    summary="Generate post content within plan quota (free)",
)
async def generate_content_batch(
    plan_id: str,
    body: GenerateContentRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate hook/caption/hashtags/cta for posts using the plan's content_quota.
    - Within quota: FREE (content_generated < content_quota)
    - Exceeds quota: 2 points per extra post (same as regenerate text)
    - post_ids: specific posts to generate; omit = all posts without content
    """
    from src.services.social_plan_service import SocialPlanService

    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id},
        {
            "posts": 1,
            "brand_dna": 1,
            "config": 1,
            "content_quota": 1,
            "content_generated": 1,
            "package": 1,
        },
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    all_posts = plan.get("posts", [])
    content_quota = plan.get("content_quota", 30)
    content_generated = plan.get("content_generated", 0)

    # Determine target posts
    if body.post_ids:
        target_posts = [p for p in all_posts if p["post_id"] in body.post_ids]
    else:
        # Default: all posts without content (hook is null/empty)
        target_posts = [p for p in all_posts if not p.get("hook")]

    if not target_posts:
        return {
            "generated": 0,
            "quota_used": content_generated,
            "quota_total": content_quota,
        }

    # Split into within-quota (free) vs over-quota (paid)
    remaining_quota = max(0, content_quota - content_generated)
    free_posts = target_posts[:remaining_quota]
    paid_posts = target_posts[remaining_quota:]

    # Deduct points for over-quota posts
    points_needed = len(paid_posts) * POINTS_REGEN_TEXT
    if points_needed > 0:
        points_service = get_points_service()
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_needed,
                service="social_plan_content_extra",
                description=f"Content gen {len(paid_posts)} extra posts for plan {plan_id}",
            )
        except InsufficientPointsError:
            if not free_posts:
                raise HTTPException(
                    status_code=402,
                    detail=f"Hết quota miễn phí. Cần {points_needed} điểm cho {len(paid_posts)} bài.",
                )
            # Generate only free posts if can't afford paid
            paid_posts = []

    posts_to_generate = free_posts + paid_posts
    plan_service = SocialPlanService()
    brand_dna = plan.get("brand_dna", {})
    config = plan.get("config", {})

    # Generate content in batches
    batch_size = 5
    max_parallel = 3
    batches = [
        posts_to_generate[i : i + batch_size]
        for i in range(0, len(posts_to_generate), batch_size)
    ]

    import asyncio as _asyncio

    async def process_batch(batch):
        results = []
        for post in batch:
            try:
                content = await plan_service.generate_post_content(
                    brand_dna, post, config
                )
                results.append((post["post_id"], content))
            except Exception as e:
                logger.error(f"Content gen failed for {post.get('post_id')}: {e}")
                results.append((post["post_id"], None))
        return results

    succeeded = 0
    for i in range(0, len(batches), max_parallel):
        parallel = batches[i : i + max_parallel]
        batch_results = await _asyncio.gather(
            *[process_batch(b) for b in parallel], return_exceptions=True
        )
        for batch_result in batch_results:
            if isinstance(batch_result, Exception):
                continue
            for post_id, content in batch_result:
                if not content:
                    continue
                now = datetime.now(timezone.utc)
                db["social_plans"].update_one(
                    {"plan_id": plan_id, "posts.post_id": post_id},
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

    # Update quota counter
    new_generated = content_generated + min(
        succeeded, len(free_posts) + len(paid_posts)
    )
    db["social_plans"].update_one(
        {"plan_id": plan_id},
        {
            "$set": {
                "content_generated": new_generated,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    return {
        "generated": succeeded,
        "free": len(free_posts),
        "paid": len([p for p in paid_posts if p]),
        "points_spent": len([p for p in paid_posts if p]) * POINTS_REGEN_TEXT,
        "quota_used": new_generated,
        "quota_total": content_quota,
    }


# ── PUT /{plan_id}/brand-dna ───────────────────────────────
class BrandDnaUpdateRequest(BaseModel):
    brand_voice: Optional[str] = None
    usp: Optional[str] = None
    common_hashtags: Optional[list] = None
    colors: Optional[dict] = None
    tone_keywords: Optional[list] = None
    content_pillars: Optional[list] = None
    forbidden_words: Optional[list] = None


@router.put("/{plan_id}/brand-dna", summary="Update brand DNA fields (free)")
async def update_brand_dna(
    plan_id: str,
    body: BrandDnaUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update specific brand DNA fields. No points cost."""
    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id}, {"_id": 0, "brand_dna": 1}
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    update_fields = {
        f"brand_dna.{k}": v for k, v in body.model_dump(exclude_none=True).items()
    }
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    db["social_plans"].update_one(
        {"plan_id": plan_id, "user_id": user_id},
        {
            "$set": {
                **update_fields,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return {
        "success": True,
        "plan_id": plan_id,
        "updated_fields": list(update_fields.keys()),
    }


# ── PATCH /{plan_id}/post/{post_id} ───────────────────────
class PostUpdateRequest(BaseModel):
    hook: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[list] = None
    cta: Optional[str] = None
    image_prompt: Optional[str] = None
    topic: Optional[str] = None
    content_pillar: Optional[str] = None
    scheduled_date: Optional[str] = None
    platform: Optional[str] = None


@router.patch("/{plan_id}/post/{post_id}", summary="Edit post fields (free)")
async def update_post(
    plan_id: str,
    post_id: str,
    body: PostUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Edit any field of a post. No points cost."""
    user_id = current_user["uid"]
    db = _get_db()

    plan = db["social_plans"].find_one(
        {"plan_id": plan_id, "user_id": user_id, "posts.post_id": post_id},
        {"_id": 0, "plan_id": 1},
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan or post not found")

    update_fields = {
        f"posts.$.{k}": v for k, v in body.model_dump(exclude_none=True).items()
    }
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    db["social_plans"].update_one(
        {"plan_id": plan_id, "user_id": user_id, "posts.post_id": post_id},
        {
            "$set": {
                **update_fields,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return {
        "success": True,
        "plan_id": plan_id,
        "post_id": post_id,
        "updated_fields": list(update_fields.keys()),
    }


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
        {
            "posts": 1,
            "brand_dna": 1,
            "config": 1,
            "content_quota": 1,
            "content_generated": 1,
        },
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

    # First-time text generation uses quota (free). Re-generation costs points.
    content_quota = plan.get("content_quota", 30)
    content_generated = plan.get("content_generated", 0)
    is_first_gen = not post.get("hook")  # post has no content yet
    quota_available = content_generated < content_quota
    use_quota = is_first_gen and quota_available and regen in ("text", "both")

    cost = 0
    if regen in ("text", "both") and not use_quota:
        cost += POINTS_REGEN_TEXT
    if regen in ("image", "both"):
        cost += POINTS_REGEN_IMAGE

    points_service = get_points_service()
    if cost > 0:
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
            raise HTTPException(
                status_code=402, detail=f"Không đủ điểm. Cần {cost} điểm."
            )

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
            # Increment quota counter if this was first-time generation within quota
            if use_quota:
                db["social_plans"].update_one(
                    {"plan_id": plan_id},
                    {"$inc": {"content_generated": 1}},
                )
            result["new_content"] = new_content
            result["used_quota"] = use_quota
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
