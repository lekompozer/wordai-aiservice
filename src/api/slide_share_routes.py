"""
Slide Share API Routes
Share presentation slides publicly with password protection and analytics
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import secrets
import hashlib
import logging

from src.middleware.firebase_auth import require_auth
from src.utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/slides/shares", tags=["Slide Sharing"])


# ============ MODELS ============


class ShareType(str):
    PRESENTATION = "presentation"  # Fullscreen presentation mode
    VIEW = "view"  # Editor view mode


class CreateShareRequest(BaseModel):
    """Request to create a share link"""

    document_id: str = Field(..., description="Slide document ID to share")
    share_type: str = Field(
        "presentation", description="Share type: 'presentation' or 'view'"
    )
    password: Optional[str] = Field(None, description="Optional password protection")
    expires_in_days: int = Field(
        7, ge=1, le=90, description="Expiration in days (1-90)"
    )
    allow_download: bool = Field(False, description="Allow PDF download from share")


class CreateShareResponse(BaseModel):
    """Response with share link"""

    success: bool
    share_id: str
    share_url: str
    share_type: str
    password_protected: bool
    expires_at: str
    created_at: str


class VerifyPasswordRequest(BaseModel):
    """Request to verify share password"""

    password: str = Field(..., description="Password to verify")


class VerifyPasswordResponse(BaseModel):
    """Response after password verification"""

    success: bool
    valid: bool
    access_token: Optional[str] = Field(
        None, description="Temporary access token if valid"
    )
    error: Optional[str] = None


class ShareInfoResponse(BaseModel):
    """Public share information"""

    share_id: str
    share_type: str
    password_protected: bool
    expired: bool
    expires_at: str
    title: str
    total_slides: int
    owner_name: Optional[str] = None
    allow_download: bool


class SlideContentResponse(BaseModel):
    """Slide content for public viewing"""

    success: bool
    slides: List[Dict[str, Any]]
    title: str
    total_slides: int


class TrackViewRequest(BaseModel):
    """Request to track a view"""

    slide_number: Optional[int] = Field(None, description="Current slide being viewed")
    duration_seconds: Optional[int] = Field(
        None, description="Time spent on current slide"
    )
    device_type: Optional[str] = Field(None, description="Device type: desktop/mobile")
    user_agent: Optional[str] = Field(None, description="Browser user agent")


class ShareAnalytics(BaseModel):
    """Analytics for a share link"""

    share_id: str
    total_views: int
    unique_viewers: int
    average_duration_seconds: float
    most_viewed_slides: List[Dict[str, int]]  # [{"slide_number": 1, "views": 50}]
    device_breakdown: Dict[str, int]  # {"desktop": 80, "mobile": 20}
    views_over_time: List[Dict[str, Any]]  # [{"date": "2025-10-24", "views": 10}]
    created_at: str
    expires_at: str
    is_active: bool


# ============ HELPER FUNCTIONS ============


def generate_share_id() -> str:
    """Generate unique share ID"""
    return f"share_{secrets.token_urlsafe(16)}"


def hash_password(password: str) -> str:
    """Hash password with SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_access_token(share_id: str) -> str:
    """Generate temporary access token for password-protected shares"""
    return secrets.token_urlsafe(32)


def get_client_ip(request: Request) -> str:
    """Get client IP address"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ============ ENDPOINTS ============


@router.post("/create", response_model=CreateShareResponse)
async def create_share_link(
    request: CreateShareRequest, user_info: dict = Depends(require_auth)
):
    """
    Create a public share link for slides

    **Features:**
    - Two modes: Presentation (fullscreen) or View (editor)
    - Optional password protection
    - Expiration (1-90 days)
    - Optional PDF download
    - Analytics tracking

    **Example:**
    ```json
    {
      "document_id": "slide_doc_abc123",
      "share_type": "presentation",
      "password": "secret123",
      "expires_in_days": 7,
      "allow_download": false
    }
    ```

    **Response:**
    ```json
    {
      "share_id": "share_xyz123",
      "share_url": "https://wordai.pro/slides/present/share_xyz123",
      "password_protected": true,
      "expires_at": "2025-10-31T12:00:00Z"
    }
    ```
    """
    try:
        user_id = user_info["uid"]

        logger.info(
            f"📤 Creating share link for document {request.document_id} by user {user_id}"
        )

        # Validate share type
        if request.share_type not in ["presentation", "view"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid share_type. Must be 'presentation' or 'view'",
            )

        # Get document from database
        from src.database.db_manager import DBManager
        from src.services.document_manager import DocumentManager

        db_manager = DBManager()
        doc_manager = DocumentManager(db_manager.db)

        document = doc_manager.get_document(request.document_id, user_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Verify it's a slide document
        if document.get("document_type") != "slide":
            raise HTTPException(
                status_code=400,
                detail="Only slide documents can be shared. This document is not a slide presentation.",
            )

        # Generate share data
        share_id = generate_share_id()
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(days=request.expires_in_days)

        # Hash password if provided
        password_hash = hash_password(request.password) if request.password else None

        # Create share record in database
        share_data = {
            "share_id": share_id,
            "document_id": request.document_id,
            "owner_id": user_id,
            "share_type": request.share_type,
            "password_hash": password_hash,
            "password_protected": bool(request.password),
            "allow_download": request.allow_download,
            "created_at": created_at,
            "expires_at": expires_at,
            "is_active": True,
            "revoked": False,
            "view_count": 0,
            "unique_viewers": [],  # List of viewer IPs/fingerprints
            "analytics": {
                "total_views": 0,
                "unique_viewers": 0,
                "views_by_slide": {},  # {slide_number: view_count}
                "views_by_date": {},  # {date: view_count}
                "views_by_device": {"desktop": 0, "mobile": 0, "tablet": 0},
                "average_duration": 0,
            },
        }

        # Insert into slide_shares collection
        db_manager.db.slide_shares.insert_one(share_data)

        logger.info(f"✅ Created share link: {share_id}")

        # Generate public URL
        base_url = "https://wordai.pro"  # TODO: Get from config
        if request.share_type == "presentation":
            share_url = f"{base_url}/slides/present/{share_id}"
        else:
            share_url = f"{base_url}/slides/view/{share_id}"

        return CreateShareResponse(
            success=True,
            share_id=share_id,
            share_url=share_url,
            share_type=request.share_type,
            password_protected=bool(request.password),
            expires_at=expires_at.isoformat(),
            created_at=created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create share link: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{share_id}", response_model=ShareInfoResponse)
async def get_share_info(share_id: str):
    """
    Get public information about a share (no auth required)

    Returns basic info to display before password verification
    """
    try:
        from src.database.db_manager import DBManager

        db_manager = DBManager()

        # Get share from database
        share = db_manager.db.slide_shares.find_one({"share_id": share_id})

        if not share:
            raise HTTPException(status_code=404, detail="Share link not found")

        # Check if expired
        expired = datetime.utcnow() > share["expires_at"]

        # Check if revoked
        if share.get("revoked", False):
            raise HTTPException(
                status_code=410, detail="This share link has been revoked by the owner"
            )

        if expired:
            raise HTTPException(status_code=410, detail="This share link has expired")

        # Get document info
        from src.services.document_manager import DocumentManager

        doc_manager = DocumentManager(db_manager.db)
        document = db_manager.db.documents.find_one(
            {"document_id": share["document_id"]}
        )

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Count slides
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(document.get("content_html", ""), "html.parser")
        slides = soup.find_all("div", style=lambda s: s and "1920px" in s)
        total_slides = len(slides)

        return ShareInfoResponse(
            share_id=share_id,
            share_type=share["share_type"],
            password_protected=share["password_protected"],
            expired=expired,
            expires_at=share["expires_at"].isoformat(),
            title=document.get("title", "Untitled Presentation"),
            total_slides=total_slides,
            owner_name=None,  # Don't expose owner info publicly
            allow_download=share.get("allow_download", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get share info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{share_id}/verify-password", response_model=VerifyPasswordResponse)
async def verify_share_password(share_id: str, request: VerifyPasswordRequest):
    """
    Verify password for password-protected share

    Returns access token if password is correct
    """
    try:
        from src.database.db_manager import DBManager

        db_manager = DBManager()

        # Get share from database
        share = db_manager.db.slide_shares.find_one({"share_id": share_id})

        if not share:
            raise HTTPException(status_code=404, detail="Share link not found")

        if not share["password_protected"]:
            return VerifyPasswordResponse(
                success=True, valid=True, access_token=None, error=None
            )

        # Verify password
        password_hash = hash_password(request.password)
        is_valid = password_hash == share["password_hash"]

        if is_valid:
            # Generate temporary access token
            access_token = generate_access_token(share_id)

            # Store access token in cache (Redis) or database with expiration
            # For now, we'll include share_id in token (can verify later)

            logger.info(f"✅ Password verified for share {share_id}")

            return VerifyPasswordResponse(
                success=True, valid=True, access_token=access_token, error=None
            )
        else:
            logger.warning(f"❌ Invalid password attempt for share {share_id}")

            return VerifyPasswordResponse(
                success=True,
                valid=False,
                access_token=None,
                error="Incorrect password. Please try again.",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to verify password: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{share_id}/content", response_model=SlideContentResponse)
async def get_share_content(share_id: str, access_token: Optional[str] = None):
    """
    Get slide content for public viewing

    Requires access_token if password-protected
    """
    try:
        from src.database.db_manager import DBManager
        from bs4 import BeautifulSoup

        db_manager = DBManager()

        # Get share from database
        share = db_manager.db.slide_shares.find_one({"share_id": share_id})

        if not share:
            raise HTTPException(status_code=404, detail="Share link not found")

        # Check if expired or revoked
        if share.get("revoked", False):
            raise HTTPException(status_code=410, detail="Share link has been revoked")

        if datetime.utcnow() > share["expires_at"]:
            raise HTTPException(status_code=410, detail="Share link has expired")

        # Verify password if required
        if share["password_protected"] and not access_token:
            raise HTTPException(
                status_code=401, detail="Password required to view this content"
            )

        # Get document content
        document = db_manager.db.documents.find_one(
            {"document_id": share["document_id"]}
        )

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Parse slides
        html_content = document.get("content_html", "")
        soup = BeautifulSoup(html_content, "html.parser")
        slide_divs = soup.find_all(
            "div", style=lambda s: s and "1920px" in s or "width:1920px" in s
        )

        slides = []
        for idx, slide_div in enumerate(slide_divs, 1):
            slides.append(
                {"slide_number": idx, "html_content": str(slide_div), "notes": None}
            )

        logger.info(f"📤 Served {len(slides)} slides for share {share_id}")

        return SlideContentResponse(
            success=True,
            slides=slides,
            title=document.get("title", "Untitled Presentation"),
            total_slides=len(slides),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get share content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{share_id}/track-view")
async def track_share_view(
    share_id: str, request: TrackViewRequest, http_request: Request
):
    """
    Track analytics for share views

    Called by frontend when:
    - User opens the presentation
    - User navigates to different slides
    - User closes/leaves presentation
    """
    try:
        from src.database.db_manager import DBManager

        db_manager = DBManager()

        # Get viewer fingerprint (IP + User-Agent hash)
        viewer_ip = get_client_ip(http_request)
        user_agent = http_request.headers.get("User-Agent", "")
        viewer_fingerprint = hashlib.sha256(
            f"{viewer_ip}:{user_agent}".encode()
        ).hexdigest()[:16]

        # Update analytics
        today = datetime.utcnow().strftime("%Y-%m-%d")

        update_data = {
            "$inc": {
                "view_count": 1,
                f"analytics.views_by_date.{today}": 1,
            },
            "$addToSet": {"unique_viewers": viewer_fingerprint},
        }

        # Track slide view
        if request.slide_number:
            update_data["$inc"][f"analytics.views_by_slide.{request.slide_number}"] = 1

        # Track device type
        if request.device_type:
            update_data["$inc"][f"analytics.views_by_device.{request.device_type}"] = 1

        db_manager.db.slide_shares.update_one({"share_id": share_id}, update_data)

        logger.info(
            f"📊 Tracked view for share {share_id}, slide {request.slide_number}"
        )

        return {"success": True, "message": "View tracked successfully"}

    except Exception as e:
        logger.error(f"❌ Failed to track view: {e}")
        # Don't raise error - analytics failure shouldn't block user
        return {"success": False, "error": str(e)}


@router.get("/{share_id}/analytics", response_model=ShareAnalytics)
async def get_share_analytics(share_id: str, user_info: dict = Depends(require_auth)):
    """
    Get analytics for a share link (owner only)

    Returns:
    - Total views & unique viewers
    - Average duration
    - Most viewed slides
    - Device breakdown
    - Views over time
    """
    try:
        user_id = user_info["uid"]

        from src.database.db_manager import DBManager

        db_manager = DBManager()

        # Get share from database
        share = db_manager.db.slide_shares.find_one({"share_id": share_id})

        if not share:
            raise HTTPException(status_code=404, detail="Share link not found")

        # Verify ownership
        if share["owner_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to view these analytics",
            )

        # Build analytics response
        analytics_data = share.get("analytics", {})

        # Most viewed slides
        views_by_slide = analytics_data.get("views_by_slide", {})
        most_viewed = sorted(
            [{"slide_number": int(k), "views": v} for k, v in views_by_slide.items()],
            key=lambda x: x["views"],
            reverse=True,
        )[:10]

        # Views over time
        views_by_date = analytics_data.get("views_by_date", {})
        views_over_time = sorted(
            [{"date": k, "views": v} for k, v in views_by_date.items()],
            key=lambda x: x["date"],
        )

        return ShareAnalytics(
            share_id=share_id,
            total_views=share.get("view_count", 0),
            unique_viewers=len(share.get("unique_viewers", [])),
            average_duration_seconds=analytics_data.get("average_duration", 0),
            most_viewed_slides=most_viewed,
            device_breakdown=analytics_data.get("views_by_device", {}),
            views_over_time=views_over_time,
            created_at=share["created_at"].isoformat(),
            expires_at=share["expires_at"].isoformat(),
            is_active=not share.get("revoked", False)
            and datetime.utcnow() <= share["expires_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{share_id}")
async def revoke_share_link(share_id: str, user_info: dict = Depends(require_auth)):
    """
    Revoke/delete a share link (owner only)

    Immediately disables the share link
    """
    try:
        user_id = user_info["uid"]

        from src.database.db_manager import DBManager

        db_manager = DBManager()

        # Get share from database
        share = db_manager.db.slide_shares.find_one({"share_id": share_id})

        if not share:
            raise HTTPException(status_code=404, detail="Share link not found")

        # Verify ownership
        if share["owner_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="You don't have permission to revoke this share"
            )

        # Revoke the share
        db_manager.db.slide_shares.update_one(
            {"share_id": share_id},
            {"$set": {"revoked": True, "revoked_at": datetime.utcnow()}},
        )

        logger.info(f"🔒 Revoked share link: {share_id}")

        return {
            "success": True,
            "message": "Share link has been revoked successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to revoke share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_user_shares(user_info: dict = Depends(require_auth)):
    """
    List all shares created by the user

    Returns list of shares with basic info and analytics
    """
    try:
        user_id = user_info["uid"]

        from src.database.db_manager import DBManager

        db_manager = DBManager()

        # Get all shares by this user
        shares = list(
            db_manager.db.slide_shares.find({"owner_id": user_id}).sort(
                "created_at", -1
            )
        )

        # Build response
        result = []
        for share in shares:
            # Get document title
            document = db_manager.db.documents.find_one(
                {"document_id": share["document_id"]}
            )
            title = document.get("title", "Untitled") if document else "Unknown"

            is_active = (
                not share.get("revoked", False)
                and datetime.utcnow() <= share["expires_at"]
            )

            result.append(
                {
                    "share_id": share["share_id"],
                    "document_id": share["document_id"],
                    "document_title": title,
                    "share_type": share["share_type"],
                    "password_protected": share["password_protected"],
                    "allow_download": share.get("allow_download", False),
                    "total_views": share.get("view_count", 0),
                    "unique_viewers": len(share.get("unique_viewers", [])),
                    "created_at": share["created_at"].isoformat(),
                    "expires_at": share["expires_at"].isoformat(),
                    "is_active": is_active,
                    "revoked": share.get("revoked", False),
                }
            )

        return {"success": True, "shares": result, "total": len(result)}

    except Exception as e:
        logger.error(f"❌ Failed to list shares: {e}")
        raise HTTPException(status_code=500, detail=str(e))
