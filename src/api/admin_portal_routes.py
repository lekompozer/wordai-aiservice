"""
Admin Portal Routes — /api/v1/admin

Entry-point endpoints for the partners.wordai.pro admin panel.
Authentication: Firebase Bearer token (ADMIN_UIDS) or X-Service-Secret.
"""

import logging
from fastapi import APIRouter, Depends

from src.middleware.admin_auth import verify_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin Portal"],
)


@router.get("/me")
async def admin_me(admin: dict = Depends(verify_admin)):
    """
    Verify admin identity and return basic info.
    Called by partners.wordai.pro on login to confirm admin access.

    Returns 200 with admin info if authenticated.
    Returns 401/403 if not authenticated or not an admin.
    """
    if admin.get("method") == "firebase":
        return {
            "authenticated": True,
            "method": "firebase",
            "uid": admin.get("uid"),
            "email": admin.get("email"),
            "role": "admin",
        }
    # X-Service-Secret (backend calls)
    return {
        "authenticated": True,
        "method": "service_secret",
        "role": "admin",
    }
