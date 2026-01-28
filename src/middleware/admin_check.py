"""
Admin middleware for WordAI Team
Only tienhoi.lh@gmail.com can access admin endpoints
"""

from fastapi import HTTPException, Depends
from src.middleware.firebase_auth import get_current_user

# WordAI Team admin emails
ADMIN_EMAILS = ["tienhoi.lh@gmail.com"]


async def check_admin_access(current_user: dict = Depends(get_current_user)):
    """
    Verify user has admin access to manage templates
    Only WordAI Team members can create/edit templates
    """
    user_email = current_user.get("email", "")

    if user_email not in ADMIN_EMAILS:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Only WordAI Team admins can manage templates. Your email: {user_email}",
        )

    return current_user
