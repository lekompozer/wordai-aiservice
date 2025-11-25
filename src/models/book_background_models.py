"""
Book Background Models
Pydantic models for book and chapter background configuration
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime


class AIMetadata(BaseModel):
    """AI generation metadata for AI-generated backgrounds"""

    prompt: str = Field(..., description="Original user prompt")
    model: str = Field(
        default="gemini-3-pro-image-preview", description="AI model used"
    )
    generated_at: datetime = Field(..., description="Generation timestamp")
    generation_time_ms: int = Field(..., description="Time taken to generate (ms)")
    cost_points: int = Field(default=2, description="Points deducted for generation")


class BackgroundConfig(BaseModel):
    """Background configuration for book or chapter"""

    # Background type
    type: Literal["solid", "gradient", "theme", "ai_image", "custom_image"] = Field(
        ..., description="Type of background"
    )

    # Type: solid
    color: Optional[str] = Field(
        None,
        pattern="^#[0-9A-Fa-f]{6}$",
        description="Hex color for solid background",
    )

    # Type: gradient
    gradient_colors: Optional[List[str]] = Field(
        None,
        min_length=2,
        max_length=4,
        description="Array of hex colors for gradient",
    )
    gradient_direction: Optional[
        Literal["to-br", "to-tr", "to-bl", "to-tl", "to-r", "to-b", "to-t", "to-l"]
    ] = Field(None, description="Tailwind gradient direction")

    # Type: theme
    theme_id: Optional[
        Literal[
            "ocean",
            "forest",
            "sunset",
            "minimal",
            "dark",
            "light",
            "tech",
            "vintage",
        ]
    ] = Field(None, description="Preset theme ID")

    # Type: ai_image or custom_image
    image_url: Optional[str] = Field(None, description="Image URL")
    image_opacity: Optional[float] = Field(
        0.3, ge=0.0, le=1.0, description="Image overlay opacity"
    )
    image_size: Optional[Literal["cover", "contain", "auto"]] = Field(
        "cover", description="CSS background-size"
    )

    # Text overlay
    show_text_overlay: bool = Field(
        False, description="Show text overlay on background"
    )
    overlay_text: Optional[str] = Field(None, max_length=200)
    overlay_position: Optional[
        Literal[
            "center",
            "top",
            "bottom",
            "top-left",
            "top-right",
            "bottom-left",
            "bottom-right",
        ]
    ] = Field("center")
    overlay_text_color: Optional[str] = Field("#FFFFFF", pattern="^#[0-9A-Fa-f]{6}$")
    overlay_text_size: Optional[
        Literal["sm", "base", "lg", "xl", "2xl", "3xl", "4xl"]
    ] = Field("2xl")
    overlay_font_weight: Optional[Literal["normal", "medium", "semibold", "bold"]] = (
        Field("bold")
    )

    # Page settings
    page_size: Optional[Literal["A4", "A5", "Letter", "Legal"]] = Field("A4")
    orientation: Optional[Literal["portrait", "landscape"]] = Field("portrait")

    # AI metadata (only for ai_image type)
    ai_metadata: Optional[AIMetadata] = None

    @field_validator("gradient_colors")
    @classmethod
    def validate_gradient_colors(cls, v):
        """Validate gradient colors are valid hex codes"""
        if v is not None:
            import re

            hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
            for color in v:
                if not hex_pattern.match(color):
                    raise ValueError(f"Invalid hex color: {color}")
        return v


class GenerateBackgroundRequest(BaseModel):
    """Request to generate AI background"""

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed description for background generation",
    )
    aspect_ratio: str = Field(
        "3:4", description="A4 portrait ratio (3:4 approximation)"
    )
    style: Optional[str] = Field(
        None, description="Style modifier (minimalist, modern, abstract, etc.)"
    )


class UpdateBookBackgroundRequest(BaseModel):
    """Update book background"""

    background_config: BackgroundConfig = Field(
        ..., description="Background configuration"
    )


class UpdateChapterBackgroundRequest(BaseModel):
    """Update chapter background"""

    use_book_background: bool = Field(
        True,
        description="If true, use book background. If false, use custom background",
    )
    background_config: Optional[BackgroundConfig] = Field(
        None,
        description="Custom background config (required if use_book_background=false)",
    )

    @field_validator("background_config")
    @classmethod
    def validate_background_config(cls, v, info):
        """Validate background_config is provided when use_book_background=false"""
        if not info.data.get("use_book_background") and v is None:
            raise ValueError(
                "background_config is required when use_book_background=false"
            )
        return v


class BackgroundResponse(BaseModel):
    """Response with background info"""

    success: bool = Field(..., description="Operation success status")
    background_config: Optional[BackgroundConfig] = Field(
        None, description="Background configuration"
    )
    message: Optional[str] = Field(None, description="Response message")


class GenerateBackgroundResponse(BaseModel):
    """Response from AI background generation"""

    success: bool = Field(..., description="Generation success status")
    image_url: Optional[str] = Field(None, description="R2 public URL")
    r2_key: Optional[str] = Field(None, description="R2 storage key")
    file_id: Optional[str] = Field(None, description="Library file ID")
    prompt_used: Optional[str] = Field(None, description="Full prompt sent to AI")
    generation_time_ms: Optional[int] = Field(
        None, description="Time taken to generate (milliseconds)"
    )
    points_deducted: Optional[int] = Field(
        None, description="Points deducted for generation"
    )
    ai_metadata: Optional[AIMetadata] = Field(
        None, description="AI generation metadata"
    )


class ThemeItem(BaseModel):
    """Preset theme item"""

    id: str = Field(..., description="Theme ID")
    name: str = Field(..., description="Theme display name")
    preview_colors: List[str] = Field(..., description="Preview colors")
    type: Literal["solid", "gradient"] = Field(..., description="Theme type")
    direction: Optional[str] = Field(None, description="Gradient direction")


class ThemesResponse(BaseModel):
    """Response with available themes"""

    themes: List[ThemeItem] = Field(..., description="List of available themes")
