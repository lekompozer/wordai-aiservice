"""
Authentication middleware for AI Service
Xác thực middleware cho AI Service
"""

from fastapi import Header, HTTPException, Request, Depends
from typing import Optional
import os
from functools import wraps

# Get API key from environment
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "agent8x-backend-secret-key-2025")


async def verify_internal_api_key(
    x_internal_key: Optional[str] = Header(None, alias="X-Internal-Key")
):
    """
    Verify internal API key for backend integration
    Xác thực API key nội bộ cho tích hợp backend
    """
    if not x_internal_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Please include X-Internal-Key header.",
        )

    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key. Access denied.")

    return True


async def verify_admin_access(
    x_internal_key: Optional[str] = Header(None, alias="X-Internal-Key")
):
    """
    Verify admin access for company context management
    Currently uses the same internal API key, but can be extended for role-based access
    Xác thực quyền admin cho quản lý ngữ cảnh công ty
    """
    # For now, reuse the internal API key verification
    # In production, implement proper admin role verification
    return await verify_internal_api_key(x_internal_key)


async def verify_company_access(x_company_id: Optional[str] = Header(None)):
    """
    Verify company ID header for frontend access
    Xác thực company ID header cho truy cập frontend
    """
    if not x_company_id:
        raise HTTPException(
            status_code=400,
            detail="Company ID required. Please include X-Company-Id header.",
        )

    # In production, you might want to verify this company exists in database
    # TODO: Add company existence validation
    return x_company_id


async def verify_webhook_signature(request: Request):
    """
    Verify webhook signature for incoming webhooks
    Xác thực chữ ký webhook cho các webhook đến
    """
    signature = request.headers.get("X-Webhook-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Webhook signature required")

    # TODO: Implement signature verification
    # This should verify HMAC SHA256 signature
    return True


# Dependency combinations for different use cases
class AuthDependencies:
    """Combined authentication dependencies"""

    @staticmethod
    async def backend_only(api_key_valid: bool = Depends(verify_internal_api_key)):
        """For admin endpoints - backend only"""
        return api_key_valid

    @staticmethod
    async def frontend_chat(company_id: str = Depends(verify_company_access)):
        """For chat endpoints - frontend with company ID"""
        return company_id

    @staticmethod
    async def webhook_only(signature_valid: bool = Depends(verify_webhook_signature)):
        """For webhook endpoints"""
        return signature_valid


# Rate limiting helper (placeholder)
class RateLimiter:
    """Rate limiting for API endpoints"""

    @staticmethod
    async def check_rate_limit(request: Request, limit_type: str = "default"):
        """Check if request is within rate limits"""
        # TODO: Implement rate limiting logic
        # Could use Redis for distributed rate limiting
        pass


# Logging helper for authentication events
def log_auth_event(event_type: str, details: dict):
    """Log authentication events for monitoring"""
    import logging

    logger = logging.getLogger("auth")

    log_message = f"[AUTH] {event_type}: {details}"

    if event_type in ["FAILED_AUTH", "INVALID_API_KEY"]:
        logger.warning(log_message)
    else:
        logger.info(log_message)
