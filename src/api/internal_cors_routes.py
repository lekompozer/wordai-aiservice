"""
Internal API routes for CORS management
Handles domain updates from Backend for chat-plugin CORS configuration
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/cors", tags=["Internal CORS"])


class CORSUpdateRequest(BaseModel):
    """Request model for CORS domain updates"""

    pluginId: str
    allowedDomains: List[str]  # Match Backend payload format
    companyId: Optional[str] = (
        None  # Make optional since Backend might not always send it
    )


class CORSUpdateResponse(BaseModel):
    """Response model for CORS updates"""

    success: bool
    message: str
    pluginId: str
    domainsCount: int


# Global reference to CORS middleware (will be set by middleware itself)
_cors_middleware = None


def set_cors_middleware(middleware):
    """Set the global CORS middleware reference"""
    global _cors_middleware
    _cors_middleware = middleware


def get_cors_middleware():
    """Get the global CORS middleware reference"""
    return _cors_middleware


async def verify_internal_request(request: Request):
    """Verify that the request is from a trusted internal source"""
    import os

    # Check for X-Internal-Key header (consistent with other internal APIs)
    auth_header = request.headers.get("X-Internal-Key")
    expected_key = os.getenv("INTERNAL_API_KEY", "agent8x-backend-secret-key-2025")

    if not auth_header:
        raise HTTPException(
            status_code=401, detail="Unauthorized: X-Internal-Key header required"
        )

    if auth_header != expected_key:
        raise HTTPException(
            status_code=401, detail="Unauthorized: Invalid internal API key"
        )


@router.post("/update-domains", response_model=CORSUpdateResponse)
async def update_plugin_domains(
    update_request: CORSUpdateRequest,
    request: Request,
    _: None = Depends(verify_internal_request),
):
    """
    Update allowed domains for a specific plugin
    Called by Backend when domain settings change
    """
    try:
        cors_middleware = get_cors_middleware()
        if not cors_middleware:
            logger.error("CORS middleware not initialized")
            raise HTTPException(status_code=500, detail="CORS middleware not available")

        # Validate domains
        validated_domains = []
        for (
            domain
        ) in update_request.allowedDomains:  # Use allowedDomains instead of domains
            domain = domain.strip()
            if domain.startswith(("http://", "https://")):
                validated_domains.append(domain)
            else:
                logger.warning(f"Invalid domain format: {domain}")

        # Update CORS middleware cache
        await cors_middleware.update_plugin_domains(
            update_request.pluginId, validated_domains
        )

        logger.info(
            f"Updated CORS domains for plugin {update_request.pluginId}: "
            f"{validated_domains}"
        )

        return CORSUpdateResponse(
            success=True,
            message=f"Successfully updated {len(validated_domains)} domains",
            pluginId=update_request.pluginId,
            domainsCount=len(validated_domains),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating CORS domains: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update CORS domains: {str(e)}"
        )


@router.delete("/clear-cache/{plugin_id}")
async def clear_plugin_cache(
    plugin_id: str, request: Request, _: None = Depends(verify_internal_request)
):
    """
    Clear CORS cache for a specific plugin
    """
    try:
        cors_middleware = get_cors_middleware()
        if not cors_middleware:
            raise HTTPException(status_code=500, detail="CORS middleware not available")

        cors_middleware.clear_cache(plugin_id)

        logger.info(f"Cleared CORS cache for plugin: {plugin_id}")

        return {"success": True, "message": f"Cache cleared for plugin {plugin_id}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing CORS cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.delete("/clear-cache")
async def clear_all_cache(request: Request, _: None = Depends(verify_internal_request)):
    """
    Clear all CORS cache
    """
    try:
        cors_middleware = get_cors_middleware()
        if not cors_middleware:
            raise HTTPException(status_code=500, detail="CORS middleware not available")

        cors_middleware.clear_cache()

        logger.info("Cleared all CORS cache")

        return {"success": True, "message": "All CORS cache cleared"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing all CORS cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/status")
async def cors_status(request: Request, _: None = Depends(verify_internal_request)):
    """
    Get CORS middleware status and cache info
    """
    try:
        cors_middleware = get_cors_middleware()
        if not cors_middleware:
            return {"status": "error", "message": "CORS middleware not initialized"}

        cache_info = {
            "cached_plugins": list(cors_middleware.domain_cache.keys()),
            "cache_size": len(cors_middleware.domain_cache),
            "cache_ttl": cors_middleware.cache_ttl,
        }

        return {
            "status": "active",
            "message": "Dynamic CORS middleware is running",
            "cache_info": cache_info,
        }

    except Exception as e:
        logger.error(f"Error getting CORS status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")
