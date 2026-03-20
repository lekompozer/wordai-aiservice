"""
Image Generation Sessions API

Maintains image history for consistent multi-image generation, mirroring
Google's Gemini conversation-based image flow.

Session flow:
  1. POST /sessions                          — Create session
  2. POST /sessions/{id}/references          — (Optional) Upload character/object reference images
  3. POST /sessions/{id}/generate            — Generate image (auto-uses session history)
  4. Repeat step 3 — each generation references all previous images
  5. DELETE /sessions/{id}/images/{index}    — Remove unwanted images from history
  6. DELETE /sessions/{id}                   — Delete session

Gemini Flash 3.1 limits (auto-enforced):
  - Up to 4  character images (role="character")
  - Up to 10 object/generated images (role="object" | "generated")
  - Total:   14 reference images per prompt
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import asyncio
from io import BytesIO

from src.middleware.firebase_auth import get_current_user
from src.models.image_generation_models import ImageGenerationMetadata
from src.services.gemini_image_service import get_gemini_image_service
from src.services.points_service import get_points_service
from src.database.db_manager import DBManager
from src.utils.logger import setup_logger

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = setup_logger()

router = APIRouter(prefix="/api/v1/images/sessions", tags=["AI Image Sessions"])

db_manager = DBManager()
db = db_manager.db

POINTS_PER_GENERATION = 2
COLLECTION = "image_generation_sessions"

# Gemini Flash 3.1 hard limits
MAX_CHARACTER_IMAGES = 4
MAX_OBJECT_IMAGES = 10
MAX_TOTAL_IMAGES = MAX_CHARACTER_IMAGES + MAX_OBJECT_IMAGES  # 14


# ── Helpers ─────────────────────────────────────────────────────────────────


def _sid() -> str:
    return f"igs_{uuid.uuid4().hex[:16]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_404(session_id: str, user_id: str) -> dict:
    doc = db[COLLECTION].find_one({"session_id": session_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return doc


async def _download_pil(url: str) -> Optional["Image.Image"]:
    """Download image from a public URL and return as PIL Image. Returns None on failure."""
    import urllib.request

    loop = asyncio.get_event_loop()
    try:

        def _fetch():
            with urllib.request.urlopen(url, timeout=15) as resp:
                return resp.read()

        data = await loop.run_in_executor(None, _fetch)
        return Image.open(BytesIO(data)).convert("RGB")
    except Exception as exc:
        logger.warning(f"⚠️ Could not download image {url}: {exc}")
        return None


def _select_references(session_images: list) -> list:
    """
    Select up to 14 session images as references for the next generation.
    - Most recent 4  character images (role="character")
    - Most recent 10 object/generated images (role="object" | "generated")
    Characters are placed first so Gemini processes them with highest priority.
    """
    chars = [img for img in session_images if img.get("role") == "character"]
    others = [img for img in session_images if img.get("role") != "character"]
    return chars[-MAX_CHARACTER_IMAGES:] + others[-MAX_OBJECT_IMAGES:]


# ── CREATE SESSION ──────────────────────────────────────────────────────────


@router.post("", status_code=201, summary="Create a new image generation session")
async def create_session(
    title: str = Form("Untitled Session", description="Session title"),
    current_user: dict = Depends(get_current_user),
):
    """
    Create an empty session. Then:
    1. Optionally upload reference images via `POST /{id}/references`
    2. Start generating via `POST /{id}/generate`
    """
    user_id = current_user["uid"]
    session_id = _sid()
    now = _now()
    doc = {
        "session_id": session_id,
        "user_id": user_id,
        "title": title,
        "images": [],
        "created_at": now,
        "updated_at": now,
    }
    db[COLLECTION].insert_one(doc)
    doc.pop("_id", None)
    logger.info(f"✅ Created session {session_id}")
    return doc


# ── ADD REFERENCE IMAGES ─────────────────────────────────────────────────────


@router.post(
    "/{session_id}/references",
    summary="Add reference images (character / object) to session",
)
async def add_references(
    session_id: str,
    files: List[UploadFile] = File(
        ..., description="1–14 reference images (PNG/JPEG/WebP/HEIC)"
    ),
    role: str = Form(
        "object",
        description="'character' — person to keep consistent | 'object' — product/scene element",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload reference images that will be automatically included in every
    subsequent generation within this session.

    **role options:**
    - `character` — face/person images for identity consistency (≤4 total in session)
    - `object` — product, style, or scene images (≤10 total in session)

    Images are converted to PNG and stored in R2.
    """
    user_id = current_user["uid"]
    doc = _get_or_404(session_id, user_id)

    if not PIL_AVAILABLE:
        raise HTTPException(status_code=500, detail="PIL library not installed")

    if role not in ("object", "character"):
        raise HTTPException(
            status_code=422, detail="role must be 'object' or 'character'"
        )

    if len(files) > MAX_TOTAL_IMAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {MAX_TOTAL_IMAGES} images per upload batch",
        )

    gemini_service = get_gemini_image_service()
    base_index = len(doc.get("images", []))
    added: list = []

    for i, uploaded in enumerate(files):
        raw = await uploaded.read()
        try:
            img = Image.open(BytesIO(raw)).convert("RGB")
        except Exception:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid image file: {uploaded.filename}",
            )

        png_buf = BytesIO()
        img.save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()

        fname = f"ref_{role}_{uuid.uuid4().hex[:8]}.png"
        upload_result = await gemini_service.upload_to_r2(
            image_bytes=png_bytes,
            user_id=user_id,
            filename=fname,
        )

        added.append(
            {
                "index": base_index + i,
                "file_id": None,
                "file_url": upload_result["file_url"],
                "r2_key": upload_result["r2_key"],
                "prompt": None,
                "role": role,
                "aspect_ratio": None,
                "created_at": _now(),
            }
        )

    db[COLLECTION].update_one(
        {"session_id": session_id},
        {"$push": {"images": {"$each": added}}, "$set": {"updated_at": _now()}},
    )
    updated = db[COLLECTION].find_one({"session_id": session_id}) or {}
    updated.pop("_id", None)
    logger.info(f"➕ Added {len(added)} ref(s) [{role}] to session {session_id}")
    return updated


# ── GENERATE IN SESSION ─────────────────────────────────────────────────────


@router.post(
    "/{session_id}/generate",
    summary="Generate next image using session history as references",
)
async def generate_in_session(
    session_id: str,
    prompt: str = Form(..., description="Describe the image to generate"),
    aspect_ratio: str = Form(
        "1:1",
        description="Supported: 1:1 | 16:9 | 9:16 | 4:3 | 3:4 | 3:2 | 2:3 | 21:9",
    ),
    negative_prompt: Optional[str] = Form(None, description="Elements to avoid"),
    extra_images: List[UploadFile] = File(
        default=[],
        description="Extra images for this turn only — NOT saved to session history",
    ),
    extra_role: str = Form(
        "object",
        description="Role for extra_images: 'object' | 'character'",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Generate the next image in the session.

    **How references are picked (auto):**
    - All images in session (references + previously generated) are candidates
    - Gemini Flash 3.1 limits are enforced automatically:
      - ≤4 most-recent **character** images
      - ≤10 most-recent **object / generated** images
      - Total: ≤14 reference images
    - Characters are always placed first in the prompt for highest fidelity

    **extra_images:** One-time images for this generation only. Useful for
    per-turn object swaps without polluting the session history.

    Generated image is appended to session history (role=`generated`) so it
    can be referenced by the next generation automatically.

    Costs **2 points**.
    """
    user_id = current_user["uid"]
    doc = _get_or_404(session_id, user_id)

    if not PIL_AVAILABLE:
        raise HTTPException(status_code=500, detail="PIL library not installed")

    # ── Points check ────────────────────────────────────────────────────────
    points_service = get_points_service()
    check = await points_service.check_sufficient_points(
        user_id=user_id,
        points_needed=POINTS_PER_GENERATION,
        service="ai_image_generation",
    )
    if not check["has_points"]:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_points",
                "message": f"Không đủ điểm. Cần: {POINTS_PER_GENERATION}, Còn: {check['points_available']}",
                "points_needed": POINTS_PER_GENERATION,
                "points_available": check["points_available"],
            },
        )

    # ── Select references from session history ───────────────────────────────
    session_images = doc.get("images", [])
    selected = _select_references(session_images)
    logger.info(
        f"🔗 Session {session_id}: {len(selected)} refs selected from {len(session_images)} total"
    )

    # ── Download session images concurrently ─────────────────────────────────
    downloaded = await asyncio.gather(
        *[_download_pil(img["file_url"]) for img in selected]
    )

    char_refs: List["Image.Image"] = []
    other_refs: List["Image.Image"] = []
    for img_info, pil in zip(selected, downloaded):
        if pil is None:
            continue
        if img_info.get("role") == "character":
            char_refs.append(pil)
        else:
            other_refs.append(pil)

    # ── Process extra_images (this turn only, not saved to session) ──────────
    extra_chars: List["Image.Image"] = []
    extra_others: List["Image.Image"] = []
    for uploaded in extra_images:
        raw = await uploaded.read()
        try:
            pil = Image.open(BytesIO(raw)).convert("RGB")
            if extra_role == "character":
                extra_chars.append(pil)
            else:
                extra_others.append(pil)
        except Exception as e:
            logger.warning(f"⚠️ Skipping invalid extra image {uploaded.filename}: {e}")

    # Merge, respecting hard limits — characters always first
    all_chars = (char_refs + extra_chars)[:MAX_CHARACTER_IMAGES]
    all_others = (other_refs + extra_others)[:MAX_OBJECT_IMAGES]
    pil_refs = all_chars + all_others

    reference_count = len(pil_refs)
    logger.info(
        f"📸 {reference_count} refs total: {len(all_chars)} character + {len(all_others)} object/generated"
    )

    # ── Generate ─────────────────────────────────────────────────────────────
    gemini_service = get_gemini_image_service()
    result = await gemini_service.generate_image(
        prompt=prompt,
        generation_type="general",
        user_options={"negative_prompt": negative_prompt},
        aspect_ratio=aspect_ratio,
        reference_images=pil_refs if pil_refs else None,
    )

    # ── Upload to R2 ─────────────────────────────────────────────────────────
    filename = f"session_{session_id[-8:]}_{uuid.uuid4().hex[:8]}.png"
    upload_result = await gemini_service.upload_to_r2(
        image_bytes=result["image_bytes"],
        user_id=user_id,
        filename=filename,
    )

    # ── Save to user library ─────────────────────────────────────────────────
    metadata = ImageGenerationMetadata(
        source="gemini-3.1-flash-image-preview",
        generation_type="session_generate",
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        generation_time_ms=result["generation_time_ms"],
        model_version="gemini-3.1-flash-image-preview",
        reference_images_count=reference_count,
        user_options={"session_id": session_id, "negative_prompt": negative_prompt},
    )
    library_doc = await gemini_service.save_to_library(
        user_id=user_id,
        filename=filename,
        file_size=result["image_size"],
        r2_key=upload_result["r2_key"],
        file_url=upload_result["file_url"],
        generation_metadata=metadata,
        db=db,
    )

    # ── Append generated image to session history ─────────────────────────────
    new_entry = {
        "index": len(session_images),
        "file_id": library_doc["file_id"],
        "file_url": upload_result["file_url"],
        "r2_key": upload_result["r2_key"],
        "prompt": prompt,
        "role": "generated",
        "aspect_ratio": aspect_ratio,
        "created_at": _now(),
    }
    db[COLLECTION].update_one(
        {"session_id": session_id},
        {"$push": {"images": new_entry}, "$set": {"updated_at": _now()}},
    )

    # ── Deduct points ─────────────────────────────────────────────────────────
    await points_service.deduct_points(
        user_id=user_id,
        amount=POINTS_PER_GENERATION,
        service="ai_image_generation",
        description=f"Session [{session_id[-8:]}]: {prompt[:40]}",
    )

    logger.info(f"✅ Session {session_id}: generated {library_doc['file_id']}")

    return {
        "success": True,
        "session_id": session_id,
        "file_id": library_doc["file_id"],
        "file_url": upload_result["file_url"],
        "r2_key": upload_result["r2_key"],
        "prompt_used": result["prompt_used"],
        "aspect_ratio": aspect_ratio,
        "reference_images_count": reference_count,
        "session_images_count": len(session_images) + 1,
        "generation_time_ms": result["generation_time_ms"],
        "points_deducted": POINTS_PER_GENERATION,
        "metadata": metadata.dict(),
    }


# ── GET SESSION ──────────────────────────────────────────────────────────────


@router.get("/{session_id}", summary="Get session details and full image history")
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["uid"]
    doc = _get_or_404(session_id, user_id)
    doc.pop("_id", None)
    return doc


# ── LIST SESSIONS ─────────────────────────────────────────────────────────────


@router.get("", summary="List all image generation sessions for current user")
async def list_sessions(current_user: dict = Depends(get_current_user)):
    user_id = current_user["uid"]
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$project": {
                "_id": 0,
                "session_id": 1,
                "title": 1,
                "images_count": {"$size": "$images"},
                "preview_url": {"$arrayElemAt": ["$images.file_url", -1]},
                "created_at": 1,
                "updated_at": 1,
            }
        },
        {"$sort": {"updated_at": -1}},
        {"$limit": 50},
    ]
    return list(db[COLLECTION].aggregate(pipeline))


# ── REMOVE IMAGE FROM SESSION ─────────────────────────────────────────────────


@router.delete(
    "/{session_id}/images/{image_index}",
    summary="Remove a specific image from session history by index",
)
async def remove_image(
    session_id: str,
    image_index: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Remove an image from the session's reference history by its 0-based index.
    Remaining images are re-indexed automatically.
    """
    user_id = current_user["uid"]
    doc = _get_or_404(session_id, user_id)
    images = doc.get("images", [])

    if not (0 <= image_index < len(images)):
        raise HTTPException(status_code=404, detail=f"No image at index {image_index}")

    images.pop(image_index)
    for i, img in enumerate(images):
        img["index"] = i

    db[COLLECTION].update_one(
        {"session_id": session_id},
        {"$set": {"images": images, "updated_at": _now()}},
    )
    return {
        "success": True,
        "session_id": session_id,
        "images_remaining": len(images),
    }


# ── DELETE SESSION ────────────────────────────────────────────────────────────


@router.delete("/{session_id}", summary="Delete image generation session")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["uid"]
    _get_or_404(session_id, user_id)  # ownership check
    db[COLLECTION].delete_one({"session_id": session_id, "user_id": user_id})
    logger.info(f"🗑️ Deleted session {session_id}")
    return {"success": True, "session_id": session_id}
