"""
Main router registration for Hybrid Search Strategy endpoints
Registers all new endpoints for hybrid search, callbacks, and CRUD operations
"""

from fastapi import APIRouter

# Import all routers
from src.api.callbacks.enhanced_callback_handler import router as callback_router
from src.api.hybrid_search.hybrid_search_routes import router as hybrid_search_router

# NOTE: CRUD routes moved to products_services_routes.py to avoid duplication
# from src.api.crud.crud_routes import router as crud_router

# Create main router
main_router = APIRouter()

# Register all routers
main_router.include_router(callback_router, prefix="", tags=["Enhanced Callbacks"])
main_router.include_router(hybrid_search_router, prefix="", tags=["Hybrid Search"])
# NOTE: CRUD operations now in products_services_routes.py
# main_router.include_router(crud_router, prefix="", tags=["CRUD Operations"])


# Health check endpoint
@main_router.get("/api/hybrid-strategy/health")
async def health_check():
    """Health check for hybrid strategy endpoints"""
    return {
        "status": "healthy",
        "message": "Hybrid Search Strategy endpoints operational",
        "features": [
            "Enhanced callbacks with AI categorization",
            "Hybrid search (category + semantic)",
            "Individual product/service CRUD",
            "Category management and analytics",
        ],
    }
