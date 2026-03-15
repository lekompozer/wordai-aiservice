"""
Blog Posts API
CRUD + listing for WordAI homepage & landing page blog posts.

Admin: tienhoi.lh@gmail.com only (create / update / delete / upload images)
Public: anyone can list and read published posts (no auth required)
"""

import logging
import os
import re
import uuid
from unidecode import unidecode
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user, get_current_user_optional
from src.services.r2_storage_service import R2StorageService

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/blog", tags=["Blog"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADMIN_EMAIL = "tienhoi.lh@gmail.com"

BLOG_CATEGORIES = [
    {
        "slug": "ai-code-studio",
        "name": "AI Code Studio",
        "description": "Code smarter with AI assistance",
    },
    {
        "slug": "community-tests",
        "name": "Community Tests",
        "description": "Create tests from any document",
    },
    {
        "slug": "ai-learning-assistant",
        "name": "AI Learning Assistant",
        "description": "Personalized AI learning assistant",
    },
    {
        "slug": "create-edit-documents",
        "name": "Create & Edit Documents",
        "description": "AI create, rewrite, translate",
    },
    {
        "slug": "reading-ai-chat",
        "name": "Reading & AI Chat",
        "description": "Read PDF · Chat AI beside document",
    },
    {
        "slug": "community-books",
        "name": "Community Books",
        "description": "Publish books · Earn 80% revenue",
    },
    {
        "slug": "ai-images",
        "name": "AI Images",
        "description": "10 tools for image creation & editing",
    },
    {
        "slug": "ai-audio",
        "name": "AI Audio",
        "description": "Text-to-speech · Podcast · Natural voice",
    },
    {
        "slug": "ai-slide-studio",
        "name": "AI Slide Studio",
        "description": "Create slides from PDF + Audio + Subtitles",
    },
    {
        "slug": "studyhub",
        "name": "StudyHub",
        "description": "Learn · Teach · Earn from courses",
    },
    {
        "slug": "ai-software-lab",
        "name": "AI Software Lab",
        "description": "Deploy apps without coding",
    },
    {
        "slug": "wordai-os",
        "name": "WordAI OS",
        "description": "Linux + Zero-Knowledge · Enterprise",
    },
    {
        "slug": "listen-learn",
        "name": "Listen & Learn",
        "description": "Listen & learn new languages",
    },
    {
        "slug": "wordai-appstore",
        "name": "WordAI Appstore",
        "description": "AI app store · Discover & share",
    },
    {
        "slug": "ai-agents",
        "name": "AI Agents",
        "description": "AI agents that automate your work",
    },
    {
        "slug": "secret-documents",
        "name": "Secret Documents",
        "description": "Zero-Knowledge · AES-256",
    },
]

VALID_CATEGORY_SLUGS = {c["slug"] for c in BLOG_CATEGORIES}

# 8 languages supported by Listen & Learn
SUPPORTED_LANGUAGES = [
    {"code": "vi", "name": "Tiếng Việt", "name_en": "Vietnamese", "flag": "🇻🇳"},
    {"code": "en", "name": "English", "name_en": "English", "flag": "🇬🇧"},
    {"code": "ja", "name": "日本語", "name_en": "Japanese", "flag": "🇯🇵"},
    {"code": "ko", "name": "한국어", "name_en": "Korean", "flag": "🇰🇷"},
    {"code": "zh", "name": "中文", "name_en": "Chinese", "flag": "🇨🇳"},
    {"code": "fr", "name": "Français", "name_en": "French", "flag": "🇫🇷"},
    {"code": "de", "name": "Deutsch", "name_en": "German", "flag": "🇩🇪"},
    {"code": "es", "name": "Español", "name_en": "Spanish", "flag": "🇪🇸"},
]
VALID_LANGUAGE_CODES = {l["code"] for l in SUPPORTED_LANGUAGES}

R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "wordai-documents")

# Shared services
_db_manager = DBManager()
_db = _db_manager.db
_r2 = R2StorageService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    text = unidecode(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:120]


def _require_admin(user: Optional[Dict]) -> None:
    if not user or user.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")


def _serialize_post(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CreatePostRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    slug: Optional[str] = Field(
        None,
        max_length=120,
        description="Custom slug (auto-generated from title if omitted)",
    )
    content: str = Field(..., description="Full post content (Markdown or HTML)")
    excerpt: Optional[str] = Field(
        None, max_length=2000, description="Short summary shown in listings"
    )
    cover_image: Optional[str] = Field(None, description="CDN URL of cover image")
    category: str = Field(
        ..., description="Category slug (must be one of the 16 valid slugs)"
    )
    language: str = Field(
        "vi",
        description="Language code: vi | en | ja | ko | zh | fr | de | es",
    )
    tags: List[str] = Field(default_factory=list, description="Free-form tags")
    status: str = Field("draft", pattern="^(draft|published)$")
    is_featured: bool = Field(
        False, description="Mark as featured (global or within category)"
    )
    seo_title: Optional[str] = Field(None, max_length=200)
    seo_description: Optional[str] = Field(None, max_length=500)


class UpdatePostRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    slug: Optional[str] = Field(
        None, max_length=120, description="Custom slug override"
    )
    content: Optional[str] = None
    excerpt: Optional[str] = Field(None, max_length=2000)
    cover_image: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = Field(
        None,
        description="Language code: vi | en | ja | ko | zh | fr | de | es",
    )
    tags: Optional[List[str]] = None
    status: Optional[str] = Field(None, pattern="^(draft|published)$")
    is_featured: Optional[bool] = Field(None, description="Mark as featured")
    seo_title: Optional[str] = Field(None, max_length=200)
    seo_description: Optional[str] = Field(None, max_length=500)


# ---------------------------------------------------------------------------
# Public: list + read
# ---------------------------------------------------------------------------


@router.get("/posts", summary="List blog posts (public)")
async def list_posts(
    category: Optional[str] = Query(None, description="Filter by category slug"),
    lang: Optional[str] = Query(
        "vi",
        description="Filter by language code (vi | en | ja | ko | zh | fr | de | es). Pass 'all' to skip filter.",
    ),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    q: Optional[str] = Query(None, description="Search in title (case-insensitive)"),
    status: Optional[str] = Query(
        "published", description="published | draft | all (admin only)"
    ),
    page: int = Query(1, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: Optional[Dict] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """
    List blog posts.

    - **Public** users only see `status=published` posts.
    - **Admin** can pass `status=draft` or `status=all` to see drafts too.
    - Filter by `lang` (language code, default `vi`), `category` (slug), `tag`,
      or free-text search `q` (title).
    - Pass `lang=all` to retrieve posts in all languages.
    - `page` is 1-based; `page=0` is accepted and treated as page 1.
    """
    page = max(page, 1)  # treat 0 as page 1 (frontend compat)
    is_admin = user and user.get("email") == ADMIN_EMAIL

    # Non-admin can only see published posts
    if not is_admin:
        status = "published"

    query: Dict[str, Any] = {}

    if status == "all":
        pass  # no status filter
    else:
        query["status"] = status

    # Language filter (default vi; pass 'all' to skip)
    if lang and lang != "all":
        if lang not in VALID_LANGUAGE_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language code: {lang}. Supported: {sorted(VALID_LANGUAGE_CODES)}",
            )
        query["language"] = lang

    if category:
        if category not in VALID_CATEGORY_SLUGS:
            raise HTTPException(
                status_code=400, detail=f"Invalid category slug: {category}"
            )
        query["category"] = category

    if tag:
        query["tags"] = tag  # MongoDB matches if array contains value

    if q:
        query["title"] = {"$regex": re.escape(q), "$options": "i"}

    skip = (page - 1) * limit
    total = _db.blog_posts.count_documents(query)
    posts = list(
        _db.blog_posts.find(query, {"content": 0})  # omit full content in listing
        .sort("published_at", -1)
        .skip(skip)
        .limit(limit)
    )

    return {
        "success": True,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "language": lang,
        "posts": [_serialize_post(p) for p in posts],
    }


@router.get("/posts/featured", summary="Get featured posts (public)")
async def get_featured_posts(
    category: Optional[str] = Query(None, description="Filter by category slug"),
    lang: Optional[str] = Query(
        "vi",
        description="Language filter. Pass 'all' to skip.",
    ),
    limit: int = Query(10, ge=1, le=50),
    user: Optional[Dict] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """
    Returns published featured posts, sorted by `published_at` desc.
    - Filter by `lang` (default `vi`) or `category`.
    - Pass `lang=all` to get featured posts across all languages.
    """
    query: Dict[str, Any] = {"status": "published", "is_featured": True}

    if lang and lang != "all":
        if lang not in VALID_LANGUAGE_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language code: {lang}. Supported: {sorted(VALID_LANGUAGE_CODES)}",
            )
        query["language"] = lang

    if category:
        if category not in VALID_CATEGORY_SLUGS:
            raise HTTPException(
                status_code=400, detail=f"Invalid category slug: {category}"
            )
        query["category"] = category

    posts = list(
        _db.blog_posts.find(query, {"content": 0}).sort("published_at", -1).limit(limit)
    )
    return {
        "success": True,
        "total": len(posts),
        "posts": [_serialize_post(p) for p in posts],
    }


@router.get("/posts/{slug}", summary="Get single post by slug (public)")
async def get_post(
    slug: str,
    user: Optional[Dict] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """
    Fetch full post by slug.
    Published posts are public. Drafts visible to admin only.
    """
    # Support lookup by either slug or post_id (for edit modals)
    doc = _db.blog_posts.find_one({"slug": slug})
    if not doc:
        doc = _db.blog_posts.find_one({"post_id": slug})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")

    is_admin = user and user.get("email") == ADMIN_EMAIL
    if doc["status"] != "published" and not is_admin:
        raise HTTPException(status_code=404, detail="Post not found")

    return {"success": True, "post": _serialize_post(doc)}


# ---------------------------------------------------------------------------
# Admin: CRUD
# ---------------------------------------------------------------------------


@router.post("/posts", summary="Create post (admin only)", status_code=201)
async def create_post(
    body: CreatePostRequest,
    user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(user)

    if body.category not in VALID_CATEGORY_SLUGS:
        raise HTTPException(
            status_code=400, detail=f"Invalid category slug: {body.category}"
        )

    language = body.language or "vi"
    if language not in VALID_LANGUAGE_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language code: {language}. Supported: {sorted(VALID_LANGUAGE_CODES)}",
        )

    base_slug = _slugify(body.slug) if body.slug else _slugify(body.title)
    slug = base_slug
    # Ensure slug uniqueness
    suffix = 1
    while _db.blog_posts.find_one({"slug": slug}):
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    now = datetime.now(timezone.utc)
    post_id = f"post_{uuid.uuid4().hex[:12]}"

    doc = {
        "post_id": post_id,
        "slug": slug,
        "title": body.title,
        "content": body.content,
        "excerpt": body.excerpt or "",
        "cover_image": body.cover_image or "",
        "category": body.category,
        "language": language,
        "tags": body.tags,
        "status": body.status,
        "author_email": ADMIN_EMAIL,
        "seo_title": body.seo_title or body.title,
        "seo_description": body.seo_description or body.excerpt or "",
        "is_featured": body.is_featured,
        "published_at": now if body.status == "published" else None,
        "created_at": now,
        "updated_at": now,
    }

    _db.blog_posts.insert_one(doc)
    logger.info(f"✅ Blog post created: {post_id} '{body.title}'")

    return {"success": True, "post": _serialize_post(doc)}


@router.put("/posts/{post_id}", summary="Update post (admin only)")
async def update_post(
    post_id: str,
    body: UpdatePostRequest,
    user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(user)

    doc = _db.blog_posts.find_one({"post_id": post_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")

    if body.category and body.category not in VALID_CATEGORY_SLUGS:
        raise HTTPException(
            status_code=400, detail=f"Invalid category slug: {body.category}"
        )

    if body.language and body.language not in VALID_LANGUAGE_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language code: {body.language}. Supported: {sorted(VALID_LANGUAGE_CODES)}",
        )

    now = datetime.now(timezone.utc)
    updates: Dict[str, Any] = {"updated_at": now}

    if body.slug is not None:
        base_slug = _slugify(body.slug)
        slug = base_slug
        suffix = 1
        while _db.blog_posts.find_one({"slug": slug, "post_id": {"$ne": post_id}}):
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        updates["slug"] = slug

    if body.title is not None:
        updates["title"] = body.title
        # Re-slug from title only when no explicit slug provided
        if body.slug is None:
            base_slug = _slugify(body.title)
            slug = base_slug
            suffix = 1
            while _db.blog_posts.find_one({"slug": slug, "post_id": {"$ne": post_id}}):
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            updates["slug"] = slug

    for field in (
        "content",
        "excerpt",
        "cover_image",
        "category",
        "language",
        "tags",
        "seo_title",
        "seo_description",
    ):
        val = getattr(body, field, None)
        if val is not None:
            updates[field] = val

    if body.is_featured is not None:
        updates["is_featured"] = body.is_featured

    if body.status is not None:
        updates["status"] = body.status
        if body.status == "published" and doc.get("status") != "published":
            updates["published_at"] = now

    _db.blog_posts.update_one({"post_id": post_id}, {"$set": updates})
    updated = _db.blog_posts.find_one({"post_id": post_id})
    logger.info(f"✅ Blog post updated: {post_id}")

    return {"success": True, "post": _serialize_post(updated)}


@router.delete("/posts/{post_id}", summary="Delete post (admin only)")
async def delete_post(
    post_id: str,
    user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(user)

    result = _db.blog_posts.delete_one({"post_id": post_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")

    logger.info(f"🗑️ Blog post deleted: {post_id}")
    return {"success": True, "message": f"Post {post_id} deleted"}


@router.patch("/posts/{post_id}/featured", summary="Set featured status (admin only)")
async def set_featured(
    post_id: str,
    is_featured: bool = Query(..., description="true to feature, false to unfeature"),
    user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Toggle the `is_featured` flag on a post. Admin only.

    A featured post appears in `GET /api/blog/posts/featured`.
    Filter by category on that endpoint to get per-category featured posts.
    """
    _require_admin(user)

    doc = _db.blog_posts.find_one({"post_id": post_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")

    _db.blog_posts.update_one(
        {"post_id": post_id},
        {
            "$set": {
                "is_featured": is_featured,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    action = "featured" if is_featured else "unfeatured"
    logger.info(f"⭐ Blog post {action}: {post_id}")
    return {"success": True, "post_id": post_id, "is_featured": is_featured}


# ---------------------------------------------------------------------------
# Admin: Image upload via Cloudflare Images (with R2 fallback)
# ---------------------------------------------------------------------------


@router.post(
    "/images/upload-url", summary="Get Cloudflare Images direct upload URL (admin only)"
)
async def get_image_upload_url(
    filename: str = Query(..., description="Original filename (e.g. hero.jpg)"),
    content_type: str = Query("image/jpeg", description="MIME type of the image"),
    user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns a **one-time Cloudflare Images direct upload URL** for browser-side upload.

    **Flow (Cloudflare Images):**
    1. Call this endpoint → get `upload_url` (one-time) + `public_url` (permanent CDN).
    2. Frontend: `POST upload_url` with the image as a multipart `file` field.
    3. Use `public_url` as `cover_image` when creating/updating a blog post.

    **Fallback (R2):** If Cloudflare Images is unavailable, returns a presigned
    `PUT` URL for direct R2 upload (same `upload_url` / `public_url` shape).

    **Auth:** Admin only (`tienhoi.lh@gmail.com`)
    """
    _require_admin(user)

    # --- Try Cloudflare Images Direct Creator Upload first ---
    try:
        from src.services.cloudflare_images_service import get_cloudflare_images_service

        cf = get_cloudflare_images_service()
        if cf.enabled:
            result = await cf.get_direct_upload_url(
                metadata={
                    "source": "blog",
                    "uploaded_by": user.get("email", "admin"),
                }
            )
            return {
                "success": True,
                "provider": "cloudflare",
                "image_id": result["id"],
                "upload_url": result["upload_url"],
                "public_url": result["public_url"],
                "expires_in": 3600,
                "instructions": (
                    "POST the image file to upload_url as multipart 'file' field, "
                    "then use public_url as cover_image in your post."
                ),
            }
    except Exception as cf_err:
        logger.warning(f"⚠️ CF Images unavailable, falling back to R2: {cf_err}")

    # --- Fallback: R2 presigned PUT URL ---
    safe_name = re.sub(r"[^\w.\-]", "_", filename)
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else "jpg"
    r2_key = f"blog/images/{uuid.uuid4().hex}.{ext}"

    upload_url = _r2.s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": R2_BUCKET_NAME,
            "Key": r2_key,
            "ContentType": content_type,
        },
        ExpiresIn=3600,
        HttpMethod="PUT",
    )
    public_url = _r2.get_public_url(r2_key)

    return {
        "success": True,
        "provider": "r2",
        "upload_url": upload_url,
        "public_url": public_url,
        "r2_key": r2_key,
        "expires_in": 3600,
        "instructions": "PUT the file bytes directly to upload_url, then use public_url in your post.",
    }


# ---------------------------------------------------------------------------
# Public: categories list
# ---------------------------------------------------------------------------


@router.get("/categories", summary="List all blog categories (public)")
async def list_categories() -> Dict[str, Any]:
    return {"success": True, "categories": BLOG_CATEGORIES}


# ---------------------------------------------------------------------------
# Public: languages list
# ---------------------------------------------------------------------------


@router.get("/languages", summary="List supported blog languages (public)")
async def list_languages() -> Dict[str, Any]:
    return {"success": True, "languages": SUPPORTED_LANGUAGES}
