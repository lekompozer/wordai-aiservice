"""
Pydantic Models for Gemini Image Editing API

Supports 4 editing operations:
1. Style Transfer - Apply artistic styles
2. Object Edit - Modify specific objects
3. Inpainting - Add/remove elements in masked areas
4. Composition - Combine multiple images
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============================================================================
# Style Transfer Models
# ============================================================================


class StyleTransferRequest(BaseModel):
    """Request for style transfer operation"""

    target_style: str = Field(
        ...,
        description="Target artistic style (e.g., 'Van Gogh', 'Cyberpunk', 'Watercolor', 'Line Art')",
    )
    strength: Optional[int] = Field(
        default=80,
        ge=0,
        le=100,
        description="Style strength (0-100). Higher = more stylized, lower = closer to original",
    )
    preserve_structure: Optional[bool] = Field(
        default=True,
        description="Whether to maintain original composition and structure",
    )
    aspect_ratio: str = Field(
        default="1:1", description="Output aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4"
    )
    negative_prompt: Optional[str] = Field(
        default=None, description="Elements to avoid in the output"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_style": "Van Gogh Starry Night",
                "strength": 85,
                "preserve_structure": True,
                "aspect_ratio": "1:1",
                "negative_prompt": "blur, distortion",
            }
        }


class StyleTransferResponse(BaseModel):
    """Response from style transfer operation"""

    image_url: str = Field(..., description="URL of the style-transferred image")
    file_id: str = Field(..., description="Library file ID")
    edit_type: str = Field(
        default="style_transfer", description="Type of edit operation"
    )
    metadata: dict = Field(..., description="Edit operation metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "image_url": "https://static.wordai.pro/ai-edited-images/user123/image.jpg",
                "file_id": "file_abc123",
                "edit_type": "style_transfer",
                "metadata": {
                    "target_style": "Van Gogh",
                    "strength": 85,
                    "model": "gemini-3-pro-image-preview",
                    "generation_time": 4.2,
                    "points_used": 2,
                },
            }
        }


# ============================================================================
# Object Edit Models
# ============================================================================


class ObjectEditRequest(BaseModel):
    """Request for object editing operation"""

    target_object: str = Field(
        ...,
        description="Description of the object to edit (e.g., 'the red car', 'the person's shirt')",
    )
    modification: str = Field(
        ...,
        description="How to modify the object (e.g., 'make it blue', 'turn into a sports car')",
    )
    preserve_background: Optional[bool] = Field(
        default=True, description="Whether to keep the rest of the image unchanged"
    )
    aspect_ratio: str = Field(
        default="1:1", description="Output aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4"
    )
    negative_prompt: Optional[str] = Field(
        default=None, description="Elements to avoid"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_object": "the blue sofa",
                "modification": "change it to a vintage brown leather chesterfield sofa",
                "preserve_background": True,
                "aspect_ratio": "16:9",
                "negative_prompt": "blur, unrealistic",
            }
        }


class ObjectEditResponse(BaseModel):
    """Response from object editing operation"""

    image_url: str = Field(..., description="URL of the edited image")
    file_id: str = Field(..., description="Library file ID")
    edit_type: str = Field(default="object_edit", description="Type of edit operation")
    metadata: dict = Field(..., description="Edit operation metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "image_url": "https://static.wordai.pro/ai-edited-images/user123/image.jpg",
                "file_id": "file_def456",
                "edit_type": "object_edit",
                "metadata": {
                    "target_object": "the blue sofa",
                    "modification": "changed to brown leather",
                    "model": "gemini-3-pro-image-preview",
                    "generation_time": 3.8,
                    "points_used": 3,
                },
            }
        }


# ============================================================================
# Inpainting Models
# ============================================================================


class InpaintingRequest(BaseModel):
    """Request for inpainting operation"""

    prompt: str = Field(
        ..., description="What to add/replace in the masked area (or 'remove' to erase)"
    )
    action: str = Field(
        default="add",
        description="Action type: 'add' (add new element), 'remove' (erase), 'replace' (change existing)",
    )
    aspect_ratio: str = Field(
        default="1:1", description="Output aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4"
    )
    blend_mode: Optional[str] = Field(
        default="natural", description="How to blend: 'natural', 'seamless', 'artistic'"
    )
    negative_prompt: Optional[str] = Field(
        default=None, description="Elements to avoid"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "a small knitted wizard hat",
                "action": "add",
                "aspect_ratio": "1:1",
                "blend_mode": "natural",
                "negative_prompt": "blur, unrealistic",
            }
        }


class InpaintingResponse(BaseModel):
    """Response from inpainting operation"""

    image_url: str = Field(..., description="URL of the inpainted image")
    file_id: str = Field(..., description="Library file ID")
    edit_type: str = Field(default="inpainting", description="Type of edit operation")
    metadata: dict = Field(..., description="Edit operation metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "image_url": "https://static.wordai.pro/ai-edited-images/user123/image.jpg",
                "file_id": "file_ghi789",
                "edit_type": "inpainting",
                "metadata": {
                    "prompt": "wizard hat added",
                    "action": "add",
                    "model": "gemini-3-pro-image-preview",
                    "generation_time": 4.5,
                    "points_used": 3,
                },
            }
        }


# ============================================================================
# Composition Models
# ============================================================================


class CompositionRequest(BaseModel):
    """Request for advanced composition operation"""

    prompt: str = Field(
        ...,
        description="How to combine the images (e.g., 'model wearing the dress in a garden')",
    )
    composition_style: Optional[str] = Field(
        default="realistic",
        description="Composition style: 'realistic', 'artistic', 'professional', 'collage'",
    )
    lighting_adjustment: Optional[bool] = Field(
        default=True, description="Whether to adjust lighting and shadows for realism"
    )
    aspect_ratio: str = Field(
        default="1:1", description="Output aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4"
    )
    negative_prompt: Optional[str] = Field(
        default=None, description="Elements to avoid"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "professional fashion photo of model wearing the dress in an outdoor garden",
                "composition_style": "professional",
                "lighting_adjustment": True,
                "aspect_ratio": "4:3",
                "negative_prompt": "blur, bad lighting",
            }
        }


class CompositionResponse(BaseModel):
    """Response from composition operation"""

    image_url: str = Field(..., description="URL of the composed image")
    file_id: str = Field(..., description="Library file ID")
    edit_type: str = Field(default="composition", description="Type of edit operation")
    metadata: dict = Field(..., description="Edit operation metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "image_url": "https://static.wordai.pro/ai-edited-images/user123/image.jpg",
                "file_id": "file_jkl012",
                "edit_type": "composition",
                "metadata": {
                    "prompt": "fashion composition",
                    "images_combined": 2,
                    "composition_style": "professional",
                    "model": "gemini-3-pro-image-preview",
                    "generation_time": 5.1,
                    "points_used": 5,
                },
            }
        }


# ============================================================================
# Shared Metadata Model
# ============================================================================


class ImageEditMetadata(BaseModel):
    """Metadata for image editing operations"""

    prompt: str = Field(..., description="Full prompt sent to Gemini")
    edit_type: str = Field(
        ...,
        description="Type of edit: style_transfer, object_edit, inpainting, composition",
    )
    aspect_ratio: str = Field(..., description="Output aspect ratio")
    model: str = Field(
        default="gemini-3-pro-image-preview", description="Gemini model used"
    )
    generation_time: float = Field(..., description="Time taken to generate (seconds)")
    file_size: int = Field(..., description="File size in bytes")
    points_used: int = Field(..., description="Points deducted for this operation")
    original_image_count: int = Field(default=1, description="Number of input images")
    request_params: dict = Field(..., description="Original request parameters")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Transform this image in Van Gogh style...",
                "edit_type": "style_transfer",
                "aspect_ratio": "1:1",
                "model": "gemini-3-pro-image-preview",
                "generation_time": 4.2,
                "file_size": 245678,
                "points_used": 2,
                "original_image_count": 1,
                "request_params": {"target_style": "Van Gogh", "strength": 85},
                "created_at": "2025-11-22T10:30:00Z",
            }
        }
