"""
Font Models

Models for custom font upload and management
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class FontFormat(str, Enum):
    """Supported font formats"""

    TTF = "ttf"
    WOFF = "woff"
    WOFF2 = "woff2"


class FontFamily(str, Enum):
    """Font family categories"""

    SERIF = "serif"
    SANS_SERIF = "sans-serif"
    MONOSPACE = "monospace"
    DISPLAY = "display"
    HANDWRITING = "handwriting"


class FontUploadRequest(BaseModel):
    """Request model for font upload (multipart/form-data)"""

    font_name: str = Field(..., description="Display name for the font")
    font_family: Optional[FontFamily] = Field(
        FontFamily.SANS_SERIF, description="Font family category"
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Font description"
    )


class FontMetadata(BaseModel):
    """Font metadata stored in database"""

    font_id: str = Field(..., description="Unique font ID (UUID)")
    user_id: str = Field(..., description="Owner's Firebase UID")
    font_name: str = Field(..., description="Display name")
    font_family: FontFamily = Field(..., description="Font family category")
    description: Optional[str] = None

    # File information
    original_filename: str = Field(..., description="Original uploaded filename")
    format: FontFormat = Field(..., description="Font file format")
    file_size: int = Field(..., description="File size in bytes")

    # Storage information
    r2_key: str = Field(..., description="R2 storage key")
    r2_url: str = Field(..., description="Public R2 URL")

    # Metadata
    is_active: bool = Field(True, description="Whether font is active")
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class FontResponse(BaseModel):
    """Response model for font operations"""

    font_id: str
    font_name: str
    font_family: FontFamily
    description: Optional[str]
    format: FontFormat
    file_size: int
    r2_url: str
    is_active: bool
    created_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class FontListResponse(BaseModel):
    """Response model for listing user fonts"""

    fonts: List[FontResponse]
    total: int
    user_id: str


class FontDeleteResponse(BaseModel):
    """Response model for font deletion"""

    success: bool
    message: str
    font_id: str


class FontFaceRule(BaseModel):
    """CSS @font-face rule for frontend injection"""

    font_id: str
    font_name: str
    font_family: FontFamily
    css_rule: str = Field(..., description="Complete @font-face CSS rule")


class FontFaceResponse(BaseModel):
    """Response model for @font-face rules"""

    css_rules: List[str] = Field(..., description="Array of CSS @font-face rules")
    fonts: List[FontFaceRule] = Field(..., description="Font metadata with CSS rules")
