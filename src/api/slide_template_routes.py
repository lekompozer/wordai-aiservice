"""
API routes for Slide Template System
Phase 1 MVP endpoints
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query

from src.models.slide_template_models import (
    CreateTemplateRequest,
    CreateTemplateResponse,
    UpdateTemplateRequest,
    UpdateTemplateResponse,
    ApplyTemplateRequest,
    ApplyTemplateResponse,
    TemplateListResponse,
    TemplateDetailResponse,
    DeleteTemplateResponse,
    SlideTemplate,
)
from src.services.slide_template_service import get_slide_template_service
from src.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slides/templates", tags=["Slide Templates"])


@router.post(
    "",
    response_model=CreateTemplateResponse,
    summary="Save slide as template",
    description="""
    Save a slide from a document as a reusable template.
    
    **Requirements:**
    - User must own the source document
    - Slide index must exist in document
    
    **Returns:**
    - Template ID, name, and metadata
    - Thumbnail URL (Phase 2)
    
    **Limits:**
    - Free users: 50 templates (future)
    - Premium users: 200 templates (future)
    - VIP users: Unlimited (future)
    """,
)
async def create_template(
    request: CreateTemplateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new template from a slide"""
    try:
        user_id = current_user["uid"]
        service = get_slide_template_service()

        result = await service.create_template(user_id, request)

        return CreateTemplateResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create template: {e}")


@router.get(
    "",
    response_model=TemplateListResponse,
    summary="List user templates",
    description="""
    Get list of user's saved templates with filtering and pagination.
    
    **Filters:**
    - `category`: Filter by category (title, content, conclusion, custom)
    - `tags`: Filter by tags (comma-separated, any match)
    - `search`: Search in name and description (case-insensitive)
    
    **Pagination:**
    - `limit`: Results per page (default 20, max 100)
    - `offset`: Skip N results (default 0)
    
    **Sorting:**
    - Always sorted by created_at DESC (newest first)
    
    **Returns:**
    - List of templates with metadata
    - Total count and pagination info
    """,
)
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: dict = Depends(get_current_user),
):
    """List user's templates with filtering"""
    try:
        user_id = current_user["uid"]
        service = get_slide_template_service()

        # Parse tags from comma-separated string
        tags_list = None
        if tags:
            tags_list = [t.strip() for t in tags.split(",") if t.strip()]

        result = await service.list_templates(
            user_id=user_id,
            category=category,
            tags=tags_list,
            search=search,
            limit=limit,
            offset=offset,
        )

        # Convert template dicts to SlideTemplate models
        templates = [SlideTemplate(**t) for t in result["templates"]]

        return TemplateListResponse(
            templates=templates,
            total=result["total"],
            limit=result["limit"],
            offset=result["offset"],
            has_more=result["has_more"],
        )

    except Exception as e:
        logger.error(f"Error listing templates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {e}")


@router.get(
    "/{template_id}",
    response_model=TemplateDetailResponse,
    summary="Get template details",
    description="""
    Get full details of a specific template including HTML content.
    
    **Requirements:**
    - User must own the template
    
    **Returns:**
    - Complete template data including template_html
    - Style properties (background, fonts, colors)
    - Usage statistics
    """,
)
async def get_template(
    template_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get template details by ID"""
    try:
        user_id = current_user["uid"]
        service = get_slide_template_service()

        template_data = await service.get_template(user_id, template_id)

        if not template_data:
            raise HTTPException(status_code=404, detail="Template not found")

        template = SlideTemplate(**template_data)

        return TemplateDetailResponse(template=template)

    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        elif "permission" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get template: {e}")


@router.patch(
    "/{template_id}",
    response_model=UpdateTemplateResponse,
    summary="Update template metadata",
    description="""
    Update template name, description, category, or tags.
    
    **Requirements:**
    - User must own the template
    
    **Updatable fields:**
    - name: Template name (1-100 chars)
    - description: Template description (max 500 chars)
    - category: Category (title, content, conclusion, custom)
    - tags: Array of tags
    
    **Note:** Template HTML cannot be updated. Create a new template instead.
    """,
)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update template metadata"""
    try:
        user_id = current_user["uid"]
        service = get_slide_template_service()

        result = await service.update_template(user_id, template_id, request)

        return UpdateTemplateResponse(**result)

    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        elif "permission" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update template: {e}")


@router.delete(
    "/{template_id}",
    response_model=DeleteTemplateResponse,
    summary="Delete template",
    description="""
    Permanently delete a template.
    
    **Requirements:**
    - User must own the template
    
    **Warning:**
    - This action cannot be undone
    - Deleting a template does not affect slides that used it
    """,
)
async def delete_template(
    template_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a template"""
    try:
        user_id = current_user["uid"]
        service = get_slide_template_service()

        success = await service.delete_template(user_id, template_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete template")

        return DeleteTemplateResponse()

    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        elif "permission" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {e}")


@router.post(
    "/{template_id}/apply",
    response_model=ApplyTemplateResponse,
    summary="Apply template to slide",
    description="""
    Apply a template to a specific slide in a document.
    
    **Requirements:**
    - User must own both the template and target document
    - Target slide must exist in document
    
    **Options:**
    - `preserve_content: true` (default): Keep existing text/images, only apply styles
    - `preserve_content: false`: Replace entire slide with template
    
    **What gets applied:**
    - Background gradient/color
    - Layout structure (Phase 2)
    - Font styles (Phase 2)
    - Colors (Phase 2)
    
    **Cost:** Free (no points deducted)
    """,
)
async def apply_template(
    template_id: str,
    request: ApplyTemplateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Apply template to a slide"""
    try:
        user_id = current_user["uid"]
        service = get_slide_template_service()

        result = await service.apply_template(user_id, template_id, request)

        return ApplyTemplateResponse(**result)

    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        elif "permission" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to apply template: {e}")
