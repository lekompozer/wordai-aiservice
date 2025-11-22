"""
Image Generation Routes - Gemini 2.5 Flash Image API
Endpoints for generating images using AI
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import Optional, List
import logging

# Authentication
from src.middleware.firebase_auth import get_current_user

# Models
from src.models.image_generation_models import (
    PhotorealisticRequest,
    PhotorealisticResponse,
    StylizedRequest,
    StylizedResponse,
    LogoRequest,
    LogoResponse,
    ImageGenerationMetadata,
)

# Services
from src.services.gemini_image_service import get_gemini_image_service
from src.services.points_service import get_points_service
from src.database.db_manager import DBManager

# PIL for image processing
try:
    from PIL import Image
    from io import BytesIO

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/images/generate", tags=["AI Image Generation"])

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Constants
POINTS_PER_GENERATION = 2


@router.post(
    "/photorealistic",
    response_model=PhotorealisticResponse,
    summary="Generate photorealistic image",
)
async def generate_photorealistic_image(
    prompt: str = Form(..., description="Detailed scene description"),
    aspect_ratio: str = Form("16:9", description="Image aspect ratio"),
    lighting: Optional[str] = Form(None, description="Lighting style"),
    camera_angle: Optional[str] = Form(None, description="Camera angle"),
    negative_prompt: Optional[str] = Form(None, description="Elements to exclude"),
    current_user: dict = Depends(get_current_user),
):
    """
    **Generate photorealistic, photograph-like images using Gemini 2.5 Flash Image**

    Creates highly realistic images with professional photography quality.
    Supports advanced options for lighting and camera angles.

    **Authentication:** Required (costs 2 points per generation)

    **Request Body:**
    ```json
    {
        "prompt": "A beautiful mountain landscape at sunset",
        "negative_prompt": "blur, distortion",
        "aspect_ratio": "16:9",
        "lighting": "Golden Hour",
        "camera_angle": "Wide Angle"
    }
    ```

    **Required Fields:**
    - `prompt`: Detailed scene description

    **Optional Fields:**
    - `negative_prompt`: Elements to exclude
    - `aspect_ratio`: "1:1", "3:4", "4:3", "16:9", "9:16" (default: "16:9")
    - `lighting`: "Natural", "Studio", "Cinematic", "Golden Hour"
    - `camera_angle`: "Wide Angle", "Macro", "Drone View", "Eye Level"

    **Response:**
    - `success`: True if generation succeeded
    - `file_id`: Library file ID for accessing the image later
    - `file_url`: Direct URL to download the image
    - `prompt_used`: Full prompt sent to Gemini
    - `generation_time_ms`: Time taken in milliseconds
    - `points_deducted`: Points charged (2)

    **Re-generation:**
    - Frontend can call this endpoint again with modified parameters
    - Each call costs 2 points (no free retries)
    - User can adjust prompt, lighting, or camera angle for different results
    """
    user_id = current_user.get("uid")

    try:
        # Check and deduct points BEFORE generation
        points_service = get_points_service()
        transaction = await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_PER_GENERATION,
            service="ai_image_generation",
            description=f"Photorealistic image: {prompt[:50]}",
        )

        logger.info(f"✅ Deducted {POINTS_PER_GENERATION} points from {user_id}")

        # Prepare user options for prompt building
        user_options = {
            "lighting": lighting,
            "camera_angle": camera_angle,
            "negative_prompt": negative_prompt,
        }

        # Generate image using Gemini service
        gemini_service = get_gemini_image_service()
        result = await gemini_service.generate_image(
            prompt=prompt,
            generation_type="photorealistic",
            user_options=user_options,
            aspect_ratio=aspect_ratio,
        )

        # Upload to R2
        filename = f"photorealistic_{aspect_ratio.replace(':', 'x')}.png"
        upload_result = await gemini_service.upload_to_r2(
            image_bytes=result["image_bytes"],
            user_id=user_id,
            filename=filename,
        )

        # Create metadata
        metadata = ImageGenerationMetadata(
            source="gemini-3-pro-image-preview",
            generation_type="photorealistic",
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            model_version="gemini-3-pro-image-preview",
            reference_images_count=0,
            user_options={
                "lighting": lighting,
                "camera_angle": camera_angle,
                "negative_prompt": negative_prompt,
            },
        )

        # Save to library
        library_doc = await gemini_service.save_to_library(
            user_id=user_id,
            filename=filename,
            file_size=result["image_size"],
            r2_key=upload_result["r2_key"],
            file_url=upload_result["file_url"],
            generation_metadata=metadata,
            db=db,
        )

        logger.info(f"✅ Photorealistic image generated: {library_doc['file_id']}")

        return PhotorealisticResponse(
            success=True,
            file_id=library_doc["file_id"],
            filename=filename,
            file_url=upload_result["file_url"],
            r2_key=upload_result["r2_key"],
            prompt_used=result["prompt_used"],
            aspect_ratio=aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            points_deducted=POINTS_PER_GENERATION,
            metadata=metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating photorealistic image: {e}")

        # Refund points on failure
        try:
            await points_service.refund_points(
                user_id=user_id,
                amount=POINTS_PER_GENERATION,
                reason="Refund for failed logo generation",
                original_transaction_id=str(transaction.id) if transaction else None,
            )
            logger.info(f"💰 Refunded {POINTS_PER_GENERATION} points to {user_id}")
        except Exception as refund_error:
            logger.error(f"❌ Failed to refund points: {refund_error}")

        raise HTTPException(
            status_code=500, detail=f"Image generation failed: {str(e)}"
        )


@router.post(
    "/stylized",
    response_model=StylizedResponse,
    summary="Generate stylized illustration or sticker",
)
async def generate_stylized_image(
    prompt: str = Form(..., description="Subject description"),
    style_preset: str = Form(
        ...,
        description="Anime|Watercolor|Oil Painting|Flat Design|3D Render|Sticker Art",
    ),
    sticker_mode: bool = Form(
        False, description="Enable sticker style (white bg, die-cut)"
    ),
    aspect_ratio: str = Form("1:1", description="Image aspect ratio"),
    reference_image: Optional[UploadFile] = File(
        None, description="Optional reference image"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    **Generate stylized illustrations or sticker-style images**

    Creates artistic illustrations in various styles: Anime, Watercolor, 3D Render, etc.
    Supports optional reference image to influence the style.

    **Authentication:** Required (costs 2 points per generation)

    **Request Body (form-data):**
    - `prompt` (text): Subject description
    - `style_preset` (text): "Anime"|"Watercolor"|"Oil Painting"|"Flat Design"|"3D Render"|"Sticker Art"
    - `sticker_mode` (boolean): Enable sticker style (white bg, die-cut)
    - `aspect_ratio` (text): Default "1:1"
    - `reference_image` (file, optional): Image to influence the style

    **Response:**
    - Similar to photorealistic endpoint
    - Includes `style_preset` and `sticker_mode` in response

    **Re-generation:**
    - Can re-generate with different style presets or sticker mode
    - Each generation costs 2 points
    """
    user_id = current_user.get("uid")

    try:
        # Check and deduct points
        points_service = get_points_service()
        transaction = await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_PER_GENERATION,
            service="ai_image_generation",
            description=f"Stylized image ({style_preset}): {prompt[:50]}",
        )

        logger.info(f"✅ Deducted {POINTS_PER_GENERATION} points from {user_id}")

        # Process reference image if provided
        reference_images = None
        if reference_image:
            if not PIL_AVAILABLE:
                raise HTTPException(
                    status_code=500, detail="PIL not installed for image processing"
                )

            image_bytes = await reference_image.read()
            pil_image = Image.open(BytesIO(image_bytes))
            reference_images = [pil_image]
            logger.info("📸 Reference image provided")

        # Prepare user options
        user_options = {
            "style_preset": style_preset,
            "sticker_mode": sticker_mode,
        }

        # Generate image
        gemini_service = get_gemini_image_service()
        result = await gemini_service.generate_image(
            prompt=prompt,
            generation_type="stylized",
            user_options=user_options,
            aspect_ratio=aspect_ratio,
            reference_images=reference_images,
        )

        # Upload to R2
        filename = f"stylized_{style_preset.lower().replace(' ', '_')}_{aspect_ratio.replace(':', 'x')}.png"
        upload_result = await gemini_service.upload_to_r2(
            image_bytes=result["image_bytes"],
            user_id=user_id,
            filename=filename,
        )

        # Create metadata
        metadata = ImageGenerationMetadata(
            source="gemini-3-pro-image-preview",
            generation_type="stylized",
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            model_version="gemini-3-pro-image-preview",
            reference_images_count=result["reference_images_count"],
            user_options=user_options,
        )

        # Save to library
        library_doc = await gemini_service.save_to_library(
            user_id=user_id,
            filename=filename,
            file_size=result["image_size"],
            r2_key=upload_result["r2_key"],
            file_url=upload_result["file_url"],
            generation_metadata=metadata,
            db=db,
        )

        logger.info(f"✅ Stylized image generated: {library_doc['file_id']}")

        return StylizedResponse(
            success=True,
            file_id=library_doc["file_id"],
            filename=filename,
            file_url=upload_result["file_url"],
            r2_key=upload_result["r2_key"],
            prompt_used=result["prompt_used"],
            style_preset=style_preset,
            sticker_mode=sticker_mode,
            aspect_ratio=aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            points_deducted=POINTS_PER_GENERATION,
            metadata=metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating stylized image: {e}")

        # Refund points
        try:
            await points_service.refund_points(
                user_id=user_id,
                amount=POINTS_PER_GENERATION,
                reason="Refund for failed stylized generation",
                original_transaction_id=str(transaction.id) if transaction else None,
            )
            logger.info(f"💰 Refunded {POINTS_PER_GENERATION} points to {user_id}")
        except Exception as refund_error:
            logger.error(f"❌ Failed to refund points: {refund_error}")

        raise HTTPException(
            status_code=500, detail=f"Image generation failed: {str(e)}"
        )


@router.post(
    "/logo",
    response_model=LogoResponse,
    summary="Generate logo with text rendering",
)
async def generate_logo_image(
    brand_name: str = Form(..., description="Brand name to render"),
    industry: str = Form(..., description="Type of business"),
    style: str = Form("Modern", description="Logo style"),
    aspect_ratio: str = Form("1:1", description="Image aspect ratio"),
    tagline: Optional[str] = Form(None, description="Optional tagline"),
    color_palette: Optional[str] = Form(None, description="Color scheme"),
    visual_elements: Optional[str] = Form(None, description="Icons/symbols to include"),
    current_user: dict = Depends(get_current_user),
):
    """
    **Generate logos with accurate text rendering**

    Creates professional logos with clear, legible text.
    Supports various styles: Minimalist, Vintage, Modern, Luxury.

    **Authentication:** Required (costs 2 points per generation)

    **Request Body:**
    ```json
    {
        "brand_name": "The Daily Grind",
        "tagline": "Coffee & Community",
        "industry": "Coffee Shop",
        "visual_elements": "coffee bean",
        "style": "Modern",
        "color_palette": "black and white",
        "aspect_ratio": "1:1"
    }
    ```

    **Required Fields:**
    - `brand_name`: Brand name to render in logo
    - `industry`: Type of business

    **Optional Fields:**
    - `tagline`: Secondary text
    - `visual_elements`: Icons or symbols to include
    - `style`: "Minimalist"|"Vintage"|"Modern"|"Luxury"
    - `color_palette`: Color scheme description or hex codes
    - `aspect_ratio`: Default "1:1"

    **Re-generation:**
    - Adjust style, colors, or visual elements
    - Each generation costs 2 points
    """
    user_id = current_user.get("uid")

    try:
        # Check and deduct points
        points_service = get_points_service()
        transaction = await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_PER_GENERATION,
            service="ai_image_generation",
            description=f"Logo: {brand_name}",
        )

        logger.info(f"✅ Deducted {POINTS_PER_GENERATION} points from {user_id}")

        # Build prompt for logo
        prompt_parts = [f"Create a professional logo for {industry} business."]
        if visual_elements:
            prompt_parts.append(f"Include visual elements: {visual_elements}.")
        if tagline:
            prompt_parts.append(f'Optional tagline: "{tagline}".')

        prompt = " ".join(prompt_parts)

        # Prepare user options
        user_options = {
            "brand_name": brand_name,
            "style": style,
            "color_palette": color_palette,
        }

        # Generate image
        gemini_service = get_gemini_image_service()
        result = await gemini_service.generate_image(
            prompt=prompt,
            generation_type="logo",
            user_options=user_options,
            aspect_ratio=aspect_ratio,
        )

        # Upload to R2
        filename = f"logo_{brand_name.lower().replace(' ', '_')}.png"
        upload_result = await gemini_service.upload_to_r2(
            image_bytes=result["image_bytes"],
            user_id=user_id,
            filename=filename,
        )

        # Create metadata
        metadata = ImageGenerationMetadata(
            source="gemini-3-pro-image-preview",
            generation_type="logo",
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            model_version="gemini-3-pro-image-preview",
            reference_images_count=0,
            user_options=user_options,
        )

        # Save to library
        library_doc = await gemini_service.save_to_library(
            user_id=user_id,
            filename=filename,
            file_size=result["image_size"],
            r2_key=upload_result["r2_key"],
            file_url=upload_result["file_url"],
            generation_metadata=metadata,
            db=db,
        )

        logger.info(f"✅ Logo generated: {library_doc['file_id']}")

        return LogoResponse(
            success=True,
            file_id=library_doc["file_id"],
            filename=filename,
            file_url=upload_result["file_url"],
            r2_key=upload_result["r2_key"],
            prompt_used=result["prompt_used"],
            brand_name=brand_name,
            style=style,
            aspect_ratio=aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            points_deducted=POINTS_PER_GENERATION,
            metadata=metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating logo: {e}")

        # Refund points
        try:
            await points_service.refund_points(
                user_id=user_id,
                amount=POINTS_PER_GENERATION,
                reason="Refund for failed logo generation",
                original_transaction_id=str(transaction.id) if transaction else None,
            )
            logger.info(f"💰 Refunded {POINTS_PER_GENERATION} points to {user_id}")
        except Exception as refund_error:
            logger.error(f"❌ Failed to refund points: {refund_error}")

        raise HTTPException(
            status_code=500, detail=f"Image generation failed: {str(e)}"
        )
