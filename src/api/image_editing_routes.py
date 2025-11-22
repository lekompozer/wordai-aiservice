"""
Image Editing API Routes

Provides 4 image editing endpoints using Google Gemini 3 Pro Image:
1. Style Transfer - Apply artistic styles to images
2. Object Edit - Modify specific objects in images
3. Inpainting - Add/remove elements in masked areas
4. Composition - Combine multiple images cohesively

All endpoints require authentication and deduct points from user's subscription.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional, List
import json
from src.middleware.firebase_auth import get_current_user
from src.services.gemini_image_edit_service import GeminiImageEditService
from src.services.subscription_service import SubscriptionService
from src.models.image_editing_models import (
    StyleTransferRequest,
    StyleTransferResponse,
    ObjectEditRequest,
    ObjectEditResponse,
    InpaintingRequest,
    InpaintingResponse,
    CompositionRequest,
    CompositionResponse,
)


router = APIRouter(prefix="/api/v1/images/edit")


# ============================================================================
# Style Transfer Endpoint
# ============================================================================


@router.post(
    "/style-transfer",
    response_model=StyleTransferResponse,
    summary="Apply artistic style to image",
    description="Transform an image using artistic styles (Van Gogh, Cyberpunk, Watercolor, etc.)",
    tags=["Image Editing"],
)
async def style_transfer_image(
    original_image: UploadFile = File(..., description="Original image to transform"),
    target_style: str = Form(..., description="Target artistic style"),
    strength: Optional[int] = Form(
        80, ge=0, le=100, description="Style strength (0-100)"
    ),
    preserve_structure: Optional[bool] = Form(
        True, description="Preserve original composition"
    ),
    aspect_ratio: str = Form(
        "1:1", description="Output aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4"
    ),
    negative_prompt: Optional[str] = Form(None, description="Elements to avoid"),
    current_user: dict = Depends(get_current_user),
):
    """
    Apply artistic style transfer to an uploaded image

    **Points Cost:** 2 points

    **Popular Styles:**
    - Van Gogh Starry Night
    - Picasso Cubism
    - Monet Impressionism
    - Cyberpunk neon
    - Watercolor painting
    - Oil painting
    - Line art / sketch
    - Anime / manga
    - Pixel art
    - Abstract geometric
    """
    user_id = current_user["user_id"]

    # Check and deduct points
    subscription_service = SubscriptionService()
    points_required = 2

    if not await subscription_service.check_and_deduct_points(
        user_id, points_required, "style_transfer_image"
    ):
        raise HTTPException(
            status_code=402,
            detail="Insufficient points. Please upgrade your subscription.",
        )

    try:
        # Initialize service
        edit_service = GeminiImageEditService()

        # Prepare parameters
        params = {
            "target_style": target_style,
            "strength": strength,
            "preserve_structure": preserve_structure,
            "aspect_ratio": aspect_ratio,
            "negative_prompt": negative_prompt,
        }

        # Edit image
        result = await edit_service.edit_image(
            edit_type="style_transfer",
            user_id=user_id,
            original_image=original_image,
            params=params,
        )

        return StyleTransferResponse(**result)

    except Exception as e:
        # Refund points on failure
        await subscription_service.refund_points(
            user_id, points_required, "style_transfer_image_failed"
        )
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Object Edit Endpoint
# ============================================================================


@router.post(
    "/object-edit",
    response_model=ObjectEditResponse,
    summary="Edit specific objects in image",
    description="Modify specific objects in an image without changing the rest",
    tags=["Image Editing"],
)
async def edit_object_in_image(
    original_image: UploadFile = File(..., description="Original image to edit"),
    target_object: str = Form(..., description="Object to edit (e.g., 'the red car')"),
    modification: str = Form(..., description="How to modify (e.g., 'make it blue')"),
    preserve_background: Optional[bool] = Form(
        True, description="Keep background unchanged"
    ),
    aspect_ratio: str = Form("1:1", description="Output aspect ratio"),
    negative_prompt: Optional[str] = Form(None, description="Elements to avoid"),
    current_user: dict = Depends(get_current_user),
):
    """
    Edit specific objects in an image semantically

    **Points Cost:** 3 points

    **Example Modifications:**
    - Change color: "make it red/blue/green"
    - Transform object: "turn it into a sports car"
    - Modify style: "make it look vintage/modern"
    - Add details: "add racing stripes"
    - Change material: "make it wooden/metallic"
    """
    user_id = current_user["user_id"]

    # Check and deduct points
    subscription_service = SubscriptionService()
    points_required = 3

    if not await subscription_service.check_and_deduct_points(
        user_id, points_required, "object_edit_image"
    ):
        raise HTTPException(
            status_code=402,
            detail="Insufficient points. Please upgrade your subscription.",
        )

    try:
        # Initialize service
        edit_service = GeminiImageEditService()

        # Prepare parameters
        params = {
            "target_object": target_object,
            "modification": modification,
            "preserve_background": preserve_background,
            "aspect_ratio": aspect_ratio,
            "negative_prompt": negative_prompt,
        }

        # Edit image
        result = await edit_service.edit_image(
            edit_type="object_edit",
            user_id=user_id,
            original_image=original_image,
            params=params,
        )

        return ObjectEditResponse(**result)

    except Exception as e:
        # Refund points on failure
        await subscription_service.refund_points(
            user_id, points_required, "object_edit_image_failed"
        )
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Inpainting Endpoint
# ============================================================================


@router.post(
    "/inpainting",
    response_model=InpaintingResponse,
    summary="Add or remove elements in image",
    description="Add, remove, or replace elements in specific areas of an image",
    tags=["Image Editing"],
)
async def inpaint_image(
    original_image: UploadFile = File(..., description="Original image to edit"),
    prompt: str = Form(..., description="What to add/replace or 'remove' to erase"),
    action: str = Form("add", description="Action: 'add', 'remove', or 'replace'"),
    mask_image: Optional[UploadFile] = File(
        None, description="Optional mask image (white = edit area)"
    ),
    aspect_ratio: str = Form("1:1", description="Output aspect ratio"),
    blend_mode: Optional[str] = Form(
        "natural", description="Blend mode: 'natural', 'seamless', 'artistic'"
    ),
    negative_prompt: Optional[str] = Form(None, description="Elements to avoid"),
    current_user: dict = Depends(get_current_user),
):
    """
    Add, remove, or replace elements in an image

    **Points Cost:** 3 points

    **Actions:**
    - **add**: Add new element to the image
    - **remove**: Erase element and fill with background
    - **replace**: Replace existing element with new one

    **Mask Image (Optional):**
    - Upload a black/white image where white indicates the area to edit
    - If no mask provided, Gemini will automatically detect the area

    **Use Cases:**
    - Add accessories to a person (hat, glasses, etc.)
    - Remove unwanted objects
    - Replace elements (change a shirt, swap objects)
    - Fill empty areas with new content
    """
    user_id = current_user["user_id"]

    # Check and deduct points
    subscription_service = SubscriptionService()
    points_required = 3

    if not await subscription_service.check_and_deduct_points(
        user_id, points_required, "inpainting_image"
    ):
        raise HTTPException(
            status_code=402,
            detail="Insufficient points. Please upgrade your subscription.",
        )

    try:
        # Initialize service
        edit_service = GeminiImageEditService()

        # Prepare parameters
        params = {
            "prompt": prompt,
            "action": action,
            "aspect_ratio": aspect_ratio,
            "blend_mode": blend_mode,
            "negative_prompt": negative_prompt,
        }

        # Edit image
        result = await edit_service.edit_image(
            edit_type="inpainting",
            user_id=user_id,
            original_image=original_image,
            params=params,
            mask_image=mask_image,
        )

        return InpaintingResponse(**result)

    except Exception as e:
        # Refund points on failure
        await subscription_service.refund_points(
            user_id, points_required, "inpainting_image_failed"
        )
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Composition Endpoint
# ============================================================================


@router.post(
    "/composition",
    response_model=CompositionResponse,
    summary="Combine multiple images",
    description="Combine multiple images into a cohesive composition with realistic lighting",
    tags=["Image Editing"],
)
async def compose_images(
    base_image: UploadFile = File(
        ..., description="Base image (e.g., model, background)"
    ),
    overlay_images: List[UploadFile] = File(
        ..., description="Images to combine (e.g., clothing, products)"
    ),
    prompt: str = Form(..., description="How to combine the images"),
    composition_style: Optional[str] = Form(
        "realistic",
        description="Style: 'realistic', 'artistic', 'professional', 'collage'",
    ),
    lighting_adjustment: Optional[bool] = Form(
        True, description="Adjust lighting and shadows"
    ),
    aspect_ratio: str = Form("1:1", description="Output aspect ratio"),
    negative_prompt: Optional[str] = Form(None, description="Elements to avoid"),
    current_user: dict = Depends(get_current_user),
):
    """
    Combine multiple images into a cohesive composition

    **Points Cost:** 5 points

    **Composition Styles:**
    - **realistic**: Photorealistic integration with proper lighting
    - **artistic**: Creative, stylized composition
    - **professional**: E-commerce/marketing quality
    - **collage**: Artistic collage style

    **Use Cases:**
    - Virtual try-on (model + clothing)
    - Product in scene (product + environment)
    - Fashion e-commerce (model + dress + background)
    - Marketing collages (multiple products/elements)
    - Complex compositions (multiple layers)

    **Tips:**
    - Upload base image first (background/model)
    - Then upload overlay images (clothing/products)
    - Be specific in prompt about placement and integration
    """
    user_id = current_user["user_id"]

    # Validate: at least 2 images total (base + 1 overlay)
    if not overlay_images or len(overlay_images) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one overlay image is required for composition",
        )

    # Check and deduct points
    subscription_service = SubscriptionService()
    points_required = 5

    if not await subscription_service.check_and_deduct_points(
        user_id, points_required, "compose_images"
    ):
        raise HTTPException(
            status_code=402,
            detail="Insufficient points. Please upgrade your subscription.",
        )

    try:
        # Initialize service
        edit_service = GeminiImageEditService()

        # Prepare parameters
        params = {
            "prompt": prompt,
            "composition_style": composition_style,
            "lighting_adjustment": lighting_adjustment,
            "aspect_ratio": aspect_ratio,
            "negative_prompt": negative_prompt,
        }

        # Edit image (composition)
        result = await edit_service.edit_image(
            edit_type="composition",
            user_id=user_id,
            original_image=base_image,
            params=params,
            additional_images=overlay_images,
        )

        return CompositionResponse(**result)

    except Exception as e:
        # Refund points on failure
        await subscription_service.refund_points(
            user_id, points_required, "compose_images_failed"
        )
        raise HTTPException(status_code=500, detail=str(e))
