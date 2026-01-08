"""
StudyHub Marketplace Routes
12 APIs for public marketplace discovery and browsing
Pattern: Similar to Community Books marketplace (read-only)
"""

from fastapi import APIRouter, Query
from typing import Optional

from src.services.studyhub_marketplace_manager import StudyHubMarketplaceManager
from src.models.studyhub_models import (
    MarketplaceSubjectsResponse,
    FeaturedSubjectsResponse,
    TrendingSubjectsResponse,
    FeaturedCreatorsResponse,
    PopularTagsResponse,
    CategoriesResponse,
    SubjectPublicViewResponse,
    RelatedSubjectsResponse,
    CreatorProfileResponse,
)

router = APIRouter(
    prefix="/api/studyhub/marketplace", tags=["StudyHub Marketplace"]
)

manager = StudyHubMarketplaceManager()


# ==================== SEARCH & BROWSE APIs ====================


@router.get(
    "/subjects/search",
    response_model=MarketplaceSubjectsResponse,
    summary="Search & filter subjects (API-27)",
)
async def search_subjects(
    q: Optional[str] = Query(None, description="Search by title or creator name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    level: Optional[str] = Query(None, description="Filter by level: beginner/intermediate/advanced"),
    sort_by: str = Query(
        "updated",
        description="Sort by: updated/views/rating/newest",
    ),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    **Search and filter marketplace subjects**

    - Full-text search on title
    - Filter by category, tags, level
    - Sort options: updated, views, rating, newest
    - Public endpoint (no auth required)
    """
    return await manager.search_subjects(q, category, tags, level, sort_by, skip, limit)


@router.get(
    "/subjects/latest",
    response_model=MarketplaceSubjectsResponse,
    summary="Latest updated subjects (API-28)",
)
async def get_latest_subjects(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100, description="Default 20 for 2x10 grid"),
):
    """
    **Get latest updated subjects**

    - Sorted by last_updated_at DESC
    - Default: 20 subjects for 2x10 grid
    - Optional filter by category and tags
    - Public endpoint
    """
    return await manager.get_latest_subjects(category, tags, skip, limit)


@router.get(
    "/subjects/top",
    response_model=MarketplaceSubjectsResponse,
    summary="Top viewed subjects (API-29)",
)
async def get_top_subjects(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    limit: int = Query(10, ge=1, le=50, description="Default 10"),
):
    """
    **Get top most viewed subjects**

    - Sorted by total_views DESC
    - Default: 10 subjects
    - Optional filter by category and tags
    - Public endpoint
    """
    return await manager.get_top_subjects(category, tags, limit)


# ==================== FEATURED & TRENDING APIs ====================


@router.get(
    "/subjects/featured-week",
    response_model=FeaturedSubjectsResponse,
    summary="Featured subjects of week (API-30)",
)
async def get_featured_week():
    """
    **Get 3 featured subjects of the week**

    Selection criteria:
    - 2 subjects with highest views in last 7 days
    - 1 subject with most enrollments in last 7 days

    Public endpoint
    """
    return await manager.get_featured_week()


@router.get(
    "/subjects/trending-today",
    response_model=TrendingSubjectsResponse,
    summary="Trending subjects today (API-31)",
)
async def get_trending_today():
    """
    **Get 5 trending subjects today**

    - Most viewed in last 24 hours
    - Includes today's view count
    - Public endpoint
    """
    return await manager.get_trending_today()


@router.get(
    "/creators/featured",
    response_model=FeaturedCreatorsResponse,
    summary="Featured creators (API-32)",
)
async def get_featured_creators():
    """
    **Get 10 featured creators for homepage**

    Selection criteria:
    - 3 creators with highest total reads (sum of all subject views)
    - 3 creators with best reviews (high average rating)
    - 4 creators with highest-viewed subjects

    Public endpoint
    """
    return await manager.get_featured_creators()


# ==================== TAGS & CATEGORIES APIs ====================


@router.get(
    "/tags/popular",
    response_model=PopularTagsResponse,
    summary="Popular tags (API-33)",
)
async def get_popular_tags():
    """
    **Get 25 most popular tags**

    - Sorted by subject count
    - Aggregated from all public subjects
    - Public endpoint
    """
    return await manager.get_popular_tags()


@router.get(
    "/categories/popular",
    response_model=CategoriesResponse,
    summary="Popular categories (API-34)",
)
async def get_popular_categories():
    """
    **Get all categories with subject count**

    - All categories sorted by count
    - Includes category icons
    - Public endpoint
    """
    return await manager.get_popular_categories()


# ==================== SUBJECT VIEW APIs ====================


@router.get(
    "/subjects/{subject_id}",
    response_model=SubjectPublicViewResponse,
    summary="Public subject view (API-35)",
)
async def get_subject_public_view(subject_id: str):
    """
    **Get public subject details for marketplace**

    - Full subject info with modules preview
    - First 2 modules shown as preview
    - Tracks view count
    - Public endpoint
    """
    return await manager.get_subject_public_view(subject_id)


@router.get(
    "/subjects/{subject_id}/related",
    response_model=RelatedSubjectsResponse,
    summary="Related subjects (API-36)",
)
async def get_related_subjects(
    subject_id: str,
    limit: int = Query(5, ge=1, le=20, description="Number of related subjects"),
):
    """
    **Get related subjects**

    - Based on same category or matching tags
    - Sorted by relevance and views
    - Public endpoint
    """
    return await manager.get_related_subjects(subject_id, limit)


# ==================== CREATOR PROFILE APIs ====================


@router.get(
    "/creators/{creator_id}/profile",
    response_model=CreatorProfileResponse,
    summary="Creator profile (API-37)",
)
async def get_creator_profile(creator_id: str):
    """
    **Get public creator profile**

    - Creator info and statistics
    - Total subjects, students, views
    - Top 3 featured subjects
    - Public endpoint
    """
    return await manager.get_creator_profile(creator_id)


@router.get(
    "/creators/{creator_id}/subjects",
    response_model=MarketplaceSubjectsResponse,
    summary="Creator subjects (API-38)",
)
async def get_creator_subjects(
    creator_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("views", description="Sort by: views/rating/newest"),
):
    """
    **Get all public subjects by creator**

    - Paginated list of creator's subjects
    - Sort options: views, rating, newest
    - Public endpoint
    """
    return await manager.get_creator_subjects(creator_id, skip, limit, sort_by)
