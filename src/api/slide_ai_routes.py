"""
Slide AI Routes
API endpoints for AI-powered slide formatting and editing
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import logging

from src.middleware.firebase_auth import get_current_user
from src.services.slide_ai_service import get_slide_ai_service
from src.services.points_service import get_points_service
from src.models.slide_ai_models import (
    SlideAIFormatRequest,
    SlideAIFormatResponse,
)

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/slides", tags=["Slide AI"])

# Points cost
POINTS_COST_FORMAT = 2  # Layout optimization with Claude Sonnet 4.5
POINTS_COST_EDIT = 2  # Content rewriting with Gemini 3 Pro


@router.post(
    "/ai-format",
    response_model=SlideAIFormatResponse,
    summary="Format slide with AI assistance",
)
async def ai_format_slide(
    request: SlideAIFormatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Format slide with AI to improve layout, typography, and visual hierarchy

    **Authentication:** Required

    **Cost:**
    - Format (improve layout/design): 2 points
    - Edit (rewrite content): 2 points

    **Request Body:**
    - slide_index: Slide index to format
    - current_html: Current slide HTML content
    - elements: Current slide elements (shapes, images)
    - background: Current slide background
    - user_instruction: Optional instruction (e.g., "Make it more professional")
    - format_type: "format" or "edit"

    **Returns:**
    - formatted_html: AI-improved HTML content
    - suggested_elements: Optional element position/addition suggestions
    - suggested_background: Optional background suggestions
    - ai_explanation: What AI changed and why
    - processing_time_ms: AI processing time
    - points_deducted: Points cost

    **Example:**
    ```json
    {
      "slide_index": 0,
      "current_html": "<h1>My Title</h1><p>Some content</p>",
      "elements": [
        {
          "type": "shape",
          "position": {"x": 100, "y": 200, "width": 300, "height": 50},
          "properties": {"color": "#667eea"}
        }
      ],
      "background": {
        "type": "gradient",
        "gradient": {
          "type": "linear",
          "colors": ["#667eea", "#764ba2"]
        }
      },
      "user_instruction": "Make it more modern and professional",
      "format_type": "format"
    }
    ```

    **Errors:**
    - 402: Insufficient points
    - 500: AI processing failed
    """
    try:
        user_id = current_user["uid"]

        # Determine points cost based on format type
        points_cost = (
            POINTS_COST_EDIT if request.format_type == "edit" else POINTS_COST_FORMAT
        )

        # Check points availability (but don't deduct yet)
        points_service = get_points_service()
        check = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=points_cost,
            service="slide_ai_formatting",
        )

        if not check["has_points"]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để format slide. Cần: {points_cost}, Còn: {check['points_available']}",
                    "points_needed": points_cost,
                    "points_available": check["points_available"],
                },
            )

        logger.info(f"🎨 User {user_id} formatting slide {request.slide_index}")
        logger.info(f"   Format type: {request.format_type}")
        logger.info(f"   Points cost: {points_cost}")

        # Call AI service
        ai_service = get_slide_ai_service()
        result = await ai_service.format_slide(request, user_id)

        # Deduct points AFTER successful formatting
        await points_service.deduct_points(
            user_id=user_id,
            amount=points_cost,
            service="slide_ai_formatting",
            resource_id=f"slide_{request.slide_index}",
            description=f"AI {request.format_type}: {request.user_instruction or 'Auto format'}",
        )

        logger.info(
            f"✅ Slide formatted successfully ({result['processing_time_ms']}ms)"
        )

        return SlideAIFormatResponse(
            success=True,
            formatted_html=result["formatted_html"],
            suggested_elements=result.get("suggested_elements", []),
            suggested_background=result.get("suggested_background"),
            ai_explanation=result["ai_explanation"],
            processing_time_ms=result["processing_time_ms"],
            points_deducted=points_cost,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to format slide: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI formatting failed: {str(e)}",
        )
