"""
Admin Authentication Middleware

Supports two authentication methods for the partners.wordai.pro admin panel:

1. Firebase Bearer token — Admin logs in with their Gmail/Google account.
   The Firebase UID must be listed in the ADMIN_UIDS environment variable.

2. X-Service-Secret header — Backend-to-backend calls (internal services).

Usage in routes:
    from src.middleware.admin_auth import verify_admin

    @router.get("/")
    async def endpoint(_: dict = Depends(verify_admin)):
        ...

Environment variable:
    ADMIN_UIDS  — Comma-separated Firebase UIDs of admin users.
                  e.g. "17BeaeikPBQYk8OWeDUkqm0Ov8e2,AcWSN7kEWQfB6zvb9vrzPWNYyqT2"
"""

import os
import logging
from typing import Dict, Any, Optional

from fastapi import Depends, Header, HTTPException, Request, status

from src.middleware.firebase_auth import get_current_user

logger = logging.getLogger(__name__)

# ── Service secret (backend-to-backend calls) ──────────────────────────────
SERVICE_SECRET = os.getenv(
    "API_SECRET_KEY", "wordai-payment-service-secret-2025-secure-key"
)

# ── Admin UID allowlist ─────────────────────────────────────────────────────
# Comma-separated Firebase UIDs that have admin access.
# Update ADMIN_UIDS env var on the server to add more admins without redeploy.
_raw = os.getenv(
    "ADMIN_UIDS",
    # Defaults: tienhoi.lh@gmail.com + original admin UID
    "17BeaeikPBQYk8OWeDUkqm0Ov8e2,AcWSN7kEWQfB6zvb9vrzPWNYyqT2",
)
ADMIN_UIDS: set = {uid.strip() for uid in _raw.split(",") if uid.strip()}


# ── Legacy dependency (Firebase-only, used by other parts of the codebase) ─
async def admin_required(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Dependency: require Firebase auth AND admin UID.
    Kept for backward compatibility.
    """
    user_uid = current_user.get("uid")
    if not user_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User UID not found"
        )
    if user_uid not in ADMIN_UIDS:
        logger.warning(f"⚠️ Non-admin user {user_uid} attempted admin action")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này không có quyền Admin.",
        )
    logger.info(f"✅ Admin access granted (Firebase): uid={user_uid}")
    return current_user


# ── Primary dependency for partners.wordai.pro ─────────────────────────────
async def verify_admin(
    request: Request,
    x_service_secret: Optional[str] = Header(default=None, alias="X-Service-Secret"),
) -> dict:
    """
    FastAPI dependency that accepts either:
      - Firebase Bearer token from a whitelisted admin UID (partners.wordai.pro)
      - X-Service-Secret header (backend-to-backend / legacy calls)

    Returns {"method": "firebase", "uid": "...", "email": "..."}
         or {"method": "service_secret"}
    """

    # 1. X-Service-Secret (fast path — internal backend calls)
    if x_service_secret and x_service_secret == SERVICE_SECRET:
        return {"method": "service_secret"}

    # 2. Firebase Bearer token (admin web panel)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            from firebase_admin import auth as fb_auth
            from src.config.firebase_config import FirebaseConfig

            FirebaseConfig()  # ensure SDK initialized
            decoded = fb_auth.verify_id_token(token)
            uid = decoded.get("uid") or decoded.get("user_id", "")
            email = decoded.get("email", "")

            if uid not in ADMIN_UIDS:
                logger.warning(
                    f"🚫 Admin access denied: uid={uid} ({email}) not in ADMIN_UIDS"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tài khoản này không có quyền Admin.",
                )

            logger.info(f"✅ Admin authenticated via Firebase: uid={uid} ({email})")
            return {"method": "firebase", "uid": uid, "email": email}

        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"❌ Admin Firebase token error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token không hợp lệ hoặc đã hết hạn.",
            )

    # 3. Nothing matched
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Yêu cầu xác thực: Firebase Bearer token hoặc X-Service-Secret.",
    )
