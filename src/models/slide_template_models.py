"""
Pydantic models for Slide Template System
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CreateTemplateRequest(BaseModel):
    """Request to save a slide as template"""

    document_id: str = Field(..., description="Source document ID")
    slide_index: int = Field(..., ge=0, description="Slide index (0-based)")
    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    description: Optional[str] = Field(
        None, max_length=500, description="Template description"
    )
    category: str = Field(
        default="custom",
        description="Template category: title, content, conclusion, custom",
    )
    tags: List[str] = Field(default_factory=list, description="Template tags")


class UpdateTemplateRequest(BaseModel):
    """Request to update template metadata"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class ApplyTemplateRequest(BaseModel):
    """Request to apply template to a slide"""

    document_id: str = Field(..., description="Target document ID")
    slide_index: int = Field(..., ge=0, description="Target slide index (0-based)")
    preserve_content: bool = Field(
        default=True,
        description="If true, keep existing content and only apply styles",
    )


class SlideTemplate(BaseModel):
    """Slide template model"""

    template_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    category: str
    tags: List[str] = Field(default_factory=list)

    # Template data
    template_html: str
    thumbnail_url: Optional[str] = None

    # Extracted styles
    background: Optional[str] = None
    font_family: Optional[str] = None
    primary_color: Optional[str] = None
    layout_type: Optional[str] = None

    # Usage tracking
    usage_count: int = 0
    last_used_at: Optional[datetime] = None

    # Source tracking
    source_document_id: Optional[str] = None
    source_slide_index: Optional[int] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TemplateListResponse(BaseModel):
    """Response for listing templates"""

    success: bool = True
    templates: List[SlideTemplate]
    total: int
    limit: int
    offset: int
    has_more: bool


class TemplateDetailResponse(BaseModel):
    """Response for template details"""

    success: bool = True
    template: SlideTemplate


class CreateTemplateResponse(BaseModel):
    """Response for creating template"""

    success: bool = True
    template_id: str
    name: str
    thumbnail_url: Optional[str] = None
    created_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UpdateTemplateResponse(BaseModel):
    """Response for updating template"""

    success: bool = True
    template_id: str
    updated_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DeleteTemplateResponse(BaseModel):
    """Response for deleting template"""

    success: bool = True
    message: str = "Template deleted successfully"


class ApplyTemplateResponse(BaseModel):
    """Response for applying template"""

    success: bool = True
    slide_updated: bool = True
    slide_index: int
    message: str = "Template applied successfully"
