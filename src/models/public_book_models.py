"""
Public Guide Models - Phase 5
Public view API models for sharing guides without authentication
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class PublicAuthorInfo(BaseModel):
    """Author information for public guides"""

    user_id: str
    display_name: str
    avatar_url: Optional[str] = None


class PublicChapterSummary(BaseModel):
    """Chapter summary for public guide TOC"""

    chapter_id: str
    title: str
    slug: str
    order: int
    description: Optional[str] = None
    icon: Optional[str] = None


class BookStats(BaseModel):
    """Guide statistics"""

    total_chapters: int
    total_views: int = 0
    last_updated: datetime


class SEOMetadata(BaseModel):
    """SEO metadata for social sharing"""

    title: str
    description: str
    og_image: Optional[str] = None
    og_url: str
    twitter_card: str = "summary_large_image"


class GuideBranding(BaseModel):
    """Guide branding/customization"""

    primary_color: Optional[str] = None
    font_family: Optional[str] = "Inter"
    custom_css: Optional[str] = None


class PublicBookResponse(BaseModel):
    """Public guide response (NO AUTH required)"""

    book_id: str
    title: str
    slug: str
    description: Optional[str] = None
    visibility: str
    custom_domain: Optional[str] = None
    is_indexed: bool = True
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    author: PublicAuthorInfo
    chapters: List[PublicChapterSummary]
    stats: BookStats
    seo: SEOMetadata
    branding: Optional[GuideBranding] = None
    created_at: datetime
    updated_at: datetime


class ChapterNavigation(BaseModel):
    """Navigation for prev/next chapters"""

    previous: Optional[PublicChapterSummary] = None
    next: Optional[PublicChapterSummary] = None


class PublicGuideInfo(BaseModel):
    """Basic guide info for chapter pages"""

    book_id: str
    title: str
    slug: str
    logo_url: Optional[str] = None
    custom_domain: Optional[str] = None


class PublicChapterResponse(BaseModel):
    """Public chapter response (NO AUTH required)"""

    chapter_id: str
    book_id: str
    title: str
    slug: str
    order: int
    description: Optional[str] = None
    icon: Optional[str] = None
    content: Dict[str, Any]
    guide_info: PublicGuideInfo
    navigation: ChapterNavigation
    seo: SEOMetadata
    created_at: datetime
    updated_at: datetime


class ViewTrackingRequest(BaseModel):
    """Request body for tracking guide views"""

    chapter_slug: Optional[str] = None
    referrer: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None


class ViewTrackingResponse(BaseModel):
    """Response for view tracking"""

    success: bool
    view_id: str
    guide_views: int
    chapter_views: Optional[int] = None


class BookDomainResponse(BaseModel):
    """Response for domain lookup (for Next.js middleware)"""

    book_id: str
    slug: str
    title: str
    custom_domain: str
    visibility: str
    is_active: bool = True
