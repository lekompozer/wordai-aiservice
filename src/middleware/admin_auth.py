"""
Admin Authentication Middleware
"""

import logging
from fastapi import HTTPException, status, Depends
from typing import Dict, Any

from src.middleware.firebase_auth import get_current_user

logger = logging.getLogger(__name__)

# List of admin UIDs - có thể move vào env variable
ADMIN_UIDS = [
    "AcWSN7kEWQfB6zvb9vrzPWNYyqT2",  # Your main admin UID
    # Add more admin UIDs here
]


async def admin_required(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Dependency để check admin permission
    """
    try:
        user_uid = current_user.get("uid")

        if not user_uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User UID not found"
            )

        if user_uid not in ADMIN_UIDS:
            logger.warning(f"⚠️ Non-admin user {user_uid} attempted admin action")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin permission required",
            )

        logger.info(f"✅ Admin access granted for user: {user_uid}")
        return current_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error checking admin permission: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking admin permission",
        )
