"""
Pydantic Models for Gemini Image Generation API
Supports text-to-image and image+text-to-image workflows
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== SHARED MODELS ====================


class ImageGenerationMetadata(BaseModel):
    """Metadata stored with generated images in library_files"""

    source: str = "gemini-2.5-flash-image"
    generation_type: str  # photorealistic, stylized, logo, etc.
    prompt: str
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    generation_time_ms: Optional[int] = None
    model_version: str = "gemini-2.5-flash-image"
    reference_images_count: int = 0
    user_options: dict = {}  # Stores lighting, camera_angle, style_preset, etc.


# ==================== PHOTOREALISTIC GENERATION ====================


class PhotorealisticRequest(BaseModel):
    """Request to generate photorealistic image"""

    prompt: str = Field(..., description="Detailed scene description")
    negative_prompt: Optional[str] = Field(
        None, description="Elements to exclude (blur, distortion, etc.)"
    )
    aspect_ratio: str = Field("16:9", description="Image aspect ratio")
    resolution: str = Field("2K", description="Image resolution (1K, 2K, 4K)")
    lighting: Optional[str] = Field(
        None, description="Natural|Studio|Cinematic|Golden Hour"
    )
    camera_angle: Optional[str] = Field(
        None, description="Wide Angle|Macro|Drone View|Eye Level"
    )


class PhotorealisticResponse(BaseModel):
    """Response from photorealistic generation"""

    success: bool
    file_id: str  # Library file ID
    filename: str
    file_url: str  # R2 URL
    r2_key: str
    prompt_used: str  # Full prompt sent to Gemini
    aspect_ratio: str
    resolution: str
    generation_time_ms: int
    points_deducted: int = 2
    metadata: ImageGenerationMetadata


# ==================== STYLIZED GENERATION ====================


class StylizedRequest(BaseModel):
    """Request to generate stylized illustration or sticker"""

    prompt: str = Field(..., description="Subject description")
    style_preset: str = Field(
        ...,
        description="Anime|Watercolor|Oil Painting|Flat Design|3D Render|Sticker Art",
    )
    sticker_mode: bool = Field(
        False, description="Enable sticker style (white bg, die-cut)"
    )
    aspect_ratio: str = Field("1:1", description="Image aspect ratio")
    resolution: str = Field("2K", description="Image resolution")


class StylizedResponse(BaseModel):
    """Response from stylized generation"""

    success: bool
    file_id: str
    filename: str
    file_url: str
    r2_key: str
    prompt_used: str
    style_preset: str
    sticker_mode: bool
    aspect_ratio: str
    resolution: str
    generation_time_ms: int
    points_deducted: int = 2
    metadata: ImageGenerationMetadata


# ==================== LOGO GENERATION ====================


class LogoRequest(BaseModel):
    """Request to generate logo with text rendering"""

    brand_name: str = Field(..., description="Brand name to render")
    tagline: Optional[str] = Field(None, description="Optional tagline text")
    industry: str = Field(..., description="Coffee Shop|Tech Startup|etc")
    visual_elements: Optional[str] = Field(
        None, description="coffee bean|circuit board|etc"
    )
    style: str = Field("Modern", description="Minimalist|Vintage|Modern|Luxury")
    color_palette: Optional[str] = Field(
        None, description="Hex codes or description (e.g., 'black and white')"
    )
    aspect_ratio: str = Field("1:1", description="Image aspect ratio")


class LogoResponse(BaseModel):
    """Response from logo generation"""

    success: bool
    file_id: str
    filename: str
    file_url: str
    r2_key: str
    prompt_used: str
    brand_name: str
    style: str
    aspect_ratio: str
    generation_time_ms: int
    points_deducted: int = 2
    metadata: ImageGenerationMetadata


# ==================== BACKGROUND GENERATION ====================


class BackgroundRequest(BaseModel):
    """Request to generate thematic background"""

    theme: str = Field(..., description="Cyberpunk city|Calm nature|etc")
    minimalist_mode: bool = Field(False, description="Clean composition with space")
    negative_space_position: str = Field(
        "Center", description="Center|Left|Right|Top - where text will go"
    )
    color_mood: str = Field("Dark", description="Dark|Light|Pastel|Vibrant")
    aspect_ratio: str = Field("16:9", description="Image aspect ratio")
    resolution: str = Field("2K", description="Image resolution")


class BackgroundResponse(BaseModel):
    """Response from background generation"""

    success: bool
    file_id: str
    filename: str
    file_url: str
    r2_key: str
    prompt_used: str
    theme: str
    minimalist_mode: bool
    aspect_ratio: str
    generation_time_ms: int
    points_deducted: int = 2
    metadata: ImageGenerationMetadata


# ==================== PRODUCT MOCKUP GENERATION ====================


class MockupRequest(BaseModel):
    """Request to generate product mockup"""

    scene_description: str = Field(
        ..., description="On a wooden table in sunlit cafe, etc"
    )
    placement_type: str = Field(
        "Tabletop", description="Tabletop|Model Wearing|Outdoor|Studio Backdrop"
    )
    aspect_ratio: str = Field("4:3", description="Image aspect ratio")
    resolution: str = Field("2K", description="Image resolution")


class MockupResponse(BaseModel):
    """Response from mockup generation"""

    success: bool
    file_id: str
    filename: str
    file_url: str
    r2_key: str
    prompt_used: str
    scene_description: str
    placement_type: str
    aspect_ratio: str
    generation_time_ms: int
    points_deducted: int = 2
    metadata: ImageGenerationMetadata


# ==================== SEQUENTIAL ART GENERATION ====================


class SequentialRequest(BaseModel):
    """Request to generate sequential art (comic panels)"""

    story_script: str = Field(..., description="Description of the sequence")
    panel_count: int = Field(1, ge=1, le=4, description="Number of panels (1-4)")
    style: str = Field("Comic Book", description="Comic Book|Manga|Storyboard Sketch")
    aspect_ratio: str = Field("16:9", description="Image aspect ratio")
    resolution: str = Field("2K", description="Image resolution")


class SequentialResponse(BaseModel):
    """Response from sequential art generation"""

    success: bool
    file_id: str
    filename: str
    file_url: str
    r2_key: str
    prompt_used: str
    story_script: str
    panel_count: int
    style: str
    aspect_ratio: str
    generation_time_ms: int
    points_deducted: int = 2
    metadata: ImageGenerationMetadata
