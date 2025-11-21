"""
Additional endpoints for Gemini Image Generation (Phase 2)
Background, Mockup, and Sequential Art generation
"""

from fastapi import APIRouter, HTTPException, Depends, status
import logging

from src.middleware.firebase_auth import get_current_user
from src.models.image_generation_models import (
    BackgroundRequest,
    BackgroundResponse,
    MockupRequest,
    MockupResponse,
    SequentialRequest,
    SequentialResponse,
    ImageGenerationMetadata,
)
from src.services.gemini_image_service import get_gemini_image_service
from src.services.points_service import get_points_service
from src.database.db_manager import DBManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/images/generate", tags=["AI Image Generation - Phase 2"])

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Constants
POINTS_PER_GENERATION = 2


@router.post(
    "/background",
    response_model=BackgroundResponse,
    summary="Generate thematic background",
)
async def generate_background_image(
    request: BackgroundRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Generate thematic backgrounds for presentations or designs**

    Creates backgrounds with optional negative space for text overlay.
    Perfect for slides, social media posts, or website headers.

    **Authentication:** Required (costs 2 points per generation)
    """
    user_id = current_user.get("uid")

    try:
        points_service = get_points_service()
        success = await points_service.deduct_points(
            user_id=user_id,
            points=POINTS_PER_GENERATION,
            action="ai_image_generation",
            description=f"Background: {request.theme[:50]}",
        )

        if not success:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient points. Need {POINTS_PER_GENERATION} points.",
            )

        user_options = {
            "minimalist_mode": request.minimalist_mode,
            "negative_space_position": request.negative_space_position,
            "color_mood": request.color_mood,
        }

        gemini_service = get_gemini_image_service()
        result = await gemini_service.generate_image(
            prompt=request.theme,
            generation_type="background",
            user_options=user_options,
            aspect_ratio=request.aspect_ratio,
        )

        filename = f"background_{request.aspect_ratio.replace(':', 'x')}.png"
        upload_result = await gemini_service.upload_to_r2(
            image_bytes=result["image_bytes"],
            user_id=user_id,
            filename=filename,
        )

        metadata = ImageGenerationMetadata(
            source="gemini-3-pro-image-preview",
            generation_type="background",
            prompt=request.theme,
            aspect_ratio=request.aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            model_version="gemini-3-pro-image-preview",
            reference_images_count=0,
            user_options=user_options,
        )

        library_doc = await gemini_service.save_to_library(
            user_id=user_id,
            filename=filename,
            file_size=result["image_size"],
            r2_key=upload_result["r2_key"],
            file_url=upload_result["file_url"],
            generation_metadata=metadata,
            db=db,
        )

        return BackgroundResponse(
            success=True,
            file_id=library_doc["file_id"],
            filename=filename,
            file_url=upload_result["file_url"],
            r2_key=upload_result["r2_key"],
            prompt_used=result["prompt_used"],
            theme=request.theme,
            minimalist_mode=request.minimalist_mode,
            aspect_ratio=request.aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            points_deducted=POINTS_PER_GENERATION,
            metadata=metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating background: {e}")
        try:
            await points_service.add_points(
                user_id=user_id,
                points=POINTS_PER_GENERATION,
                action="ai_image_generation_refund",
                description="Refund for failed image generation",
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")


@router.post(
    "/mockup",
    response_model=MockupResponse,
    summary="Generate product mockup",
)
async def generate_mockup_image(
    request: MockupRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Generate product mockups in realistic scenes**

    Creates professional product photography with various placements.
    Ideal for e-commerce, marketing materials, or presentations.

    **Authentication:** Required (costs 2 points per generation)
    """
    user_id = current_user.get("uid")

    try:
        points_service = get_points_service()
        success = await points_service.deduct_points(
            user_id=user_id,
            points=POINTS_PER_GENERATION,
            action="ai_image_generation",
            description=f"Mockup: {request.scene_description[:50]}",
        )

        if not success:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient points. Need {POINTS_PER_GENERATION} points.",
            )

        user_options = {
            "placement_type": request.placement_type,
        }

        gemini_service = get_gemini_image_service()
        result = await gemini_service.generate_image(
            prompt=request.scene_description,
            generation_type="mockup",
            user_options=user_options,
            aspect_ratio=request.aspect_ratio,
        )

        filename = f"mockup_{request.aspect_ratio.replace(':', 'x')}.png"
        upload_result = await gemini_service.upload_to_r2(
            image_bytes=result["image_bytes"],
            user_id=user_id,
            filename=filename,
        )

        metadata = ImageGenerationMetadata(
            source="gemini-3-pro-image-preview",
            generation_type="mockup",
            prompt=request.scene_description,
            aspect_ratio=request.aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            model_version="gemini-3-pro-image-preview",
            reference_images_count=0,
            user_options=user_options,
        )

        library_doc = await gemini_service.save_to_library(
            user_id=user_id,
            filename=filename,
            file_size=result["image_size"],
            r2_key=upload_result["r2_key"],
            file_url=upload_result["file_url"],
            generation_metadata=metadata,
            db=db,
        )

        return MockupResponse(
            success=True,
            file_id=library_doc["file_id"],
            filename=filename,
            file_url=upload_result["file_url"],
            r2_key=upload_result["r2_key"],
            prompt_used=result["prompt_used"],
            scene_description=request.scene_description,
            placement_type=request.placement_type,
            aspect_ratio=request.aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            points_deducted=POINTS_PER_GENERATION,
            metadata=metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating mockup: {e}")
        try:
            await points_service.add_points(
                user_id=user_id,
                points=POINTS_PER_GENERATION,
                action="ai_image_generation_refund",
                description="Refund for failed image generation",
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")


@router.post(
    "/sequential",
    response_model=SequentialResponse,
    summary="Generate sequential art (comic panels)",
)
async def generate_sequential_image(
    request: SequentialRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Generate sequential art for storytelling**

    Creates comic-style panels or storyboard sequences.
    Supports 1-4 panels in various artistic styles.

    **Authentication:** Required (costs 2 points per generation)
    """
    user_id = current_user.get("uid")

    try:
        points_service = get_points_service()
        success = await points_service.deduct_points(
            user_id=user_id,
            points=POINTS_PER_GENERATION,
            action="ai_image_generation",
            description=f"Sequential art: {request.story_script[:50]}",
        )

        if not success:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient points. Need {POINTS_PER_GENERATION} points.",
            )

        user_options = {
            "style": request.style,
            "panel_count": request.panel_count,
        }

        gemini_service = get_gemini_image_service()
        result = await gemini_service.generate_image(
            prompt=request.story_script,
            generation_type="sequential",
            user_options=user_options,
            aspect_ratio=request.aspect_ratio,
        )

        filename = f"sequential_{request.panel_count}panel_{request.aspect_ratio.replace(':', 'x')}.png"
        upload_result = await gemini_service.upload_to_r2(
            image_bytes=result["image_bytes"],
            user_id=user_id,
            filename=filename,
        )

        metadata = ImageGenerationMetadata(
            source="gemini-3-pro-image-preview",
            generation_type="sequential",
            prompt=request.story_script,
            aspect_ratio=request.aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            model_version="gemini-3-pro-image-preview",
            reference_images_count=0,
            user_options=user_options,
        )

        library_doc = await gemini_service.save_to_library(
            user_id=user_id,
            filename=filename,
            file_size=result["image_size"],
            r2_key=upload_result["r2_key"],
            file_url=upload_result["file_url"],
            generation_metadata=metadata,
            db=db,
        )

        return SequentialResponse(
            success=True,
            file_id=library_doc["file_id"],
            filename=filename,
            file_url=upload_result["file_url"],
            r2_key=upload_result["r2_key"],
            prompt_used=result["prompt_used"],
            story_script=request.story_script,
            panel_count=request.panel_count,
            style=request.style,
            aspect_ratio=request.aspect_ratio,
            generation_time_ms=result["generation_time_ms"],
            points_deducted=POINTS_PER_GENERATION,
            metadata=metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating sequential art: {e}")
        try:
            await points_service.add_points(
                user_id=user_id,
                points=POINTS_PER_GENERATION,
                action="ai_image_generation_refund",
                description="Refund for failed image generation",
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")
