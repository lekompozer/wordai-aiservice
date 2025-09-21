"""
HTML to DOCX Conversion API Routes
FastAPI routes for document conversion services
"""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from src.services.conversion_service import ConversionService
from src.middleware.firebase_auth import get_current_user
from src.utils.response_utils import create_success_response, create_error_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/convert", tags=["conversion"])

# Initialize conversion service
conversion_service = ConversionService()


class HTMLToDocxRequest(BaseModel):
    """Request model for HTML to DOCX conversion"""

    html_content: str
    file_name: Optional[str] = None
    upload_to_r2: bool = True


class TemplateUpdateRequest(BaseModel):
    """Request model for template content update"""

    template_id: str
    html_content: str


@router.post("/html-to-docx")
async def convert_html_to_docx(
    request: HTMLToDocxRequest, current_user: dict = Depends(get_current_user)
):
    """
    Convert HTML content to DOCX file

    Args:
        request: HTML content and conversion options
        current_user: Authenticated user info

    Returns:
        Conversion result with download URL
    """
    try:
        logger.info(
            f"HTML to DOCX conversion requested by user: {current_user.get('uid')}"
        )

        # Validate input
        if not request.html_content or not request.html_content.strip():
            raise HTTPException(
                status_code=400, detail="HTML content is required and cannot be empty"
            )

        # Convert HTML to DOCX
        result = await conversion_service.html_to_docx(
            html_content=request.html_content,
            file_name=request.file_name,
            upload_to_r2=request.upload_to_r2,
        )

        logger.info(f"HTML to DOCX conversion completed: {result.get('file_name')}")

        return create_success_response(
            data=result, message="HTML successfully converted to DOCX"
        )

    except Exception as e:
        logger.error(f"HTML to DOCX conversion failed: {e}")
        return create_error_response(
            message=f"Conversion failed: {str(e)}", status_code=500
        )


@router.post("/docx-to-html")
async def convert_docx_to_html(
    file: UploadFile = File(...), current_user: dict = Depends(get_current_user)
):
    """
    Convert DOCX file to HTML content

    Args:
        file: DOCX file to convert
        current_user: Authenticated user info

    Returns:
        HTML content
    """
    try:
        logger.info(
            f"DOCX to HTML conversion requested by user: {current_user.get('uid')}"
        )

        # Validate file type
        if not file.filename.lower().endswith(".docx"):
            raise HTTPException(status_code=400, detail="Only DOCX files are supported")

        # Read file content
        docx_content = await file.read()

        if not docx_content:
            raise HTTPException(status_code=400, detail="File is empty or corrupted")

        # Convert DOCX to HTML
        html_content = await conversion_service.docx_to_html(docx_content)

        logger.info(f"DOCX to HTML conversion completed: {file.filename}")

        return create_success_response(
            data={
                "html_content": html_content,
                "original_filename": file.filename,
                "content_length": len(html_content),
            },
            message="DOCX successfully converted to HTML",
        )

    except Exception as e:
        logger.error(f"DOCX to HTML conversion failed: {e}")
        return create_error_response(
            message=f"Conversion failed: {str(e)}", status_code=500
        )


@router.put("/template/update-content")
async def update_template_content(
    request: TemplateUpdateRequest, current_user: dict = Depends(get_current_user)
):
    """
    Update template content with new HTML and regenerate DOCX

    Args:
        request: Template ID and new HTML content
        current_user: Authenticated user info

    Returns:
        Updated template info
    """
    try:
        logger.info(f"Template content update requested: {request.template_id}")

        # Validate input
        if not request.template_id or not request.template_id.strip():
            raise HTTPException(status_code=400, detail="Template ID is required")

        if not request.html_content or not request.html_content.strip():
            raise HTTPException(status_code=400, detail="HTML content is required")

        # Update template
        result = await conversion_service.update_template_content(
            template_id=request.template_id,
            html_content=request.html_content,
            user_id=current_user.get("uid"),
        )

        logger.info(f"Template {request.template_id} updated successfully")

        return create_success_response(
            data=result, message="Template content updated successfully"
        )

    except Exception as e:
        logger.error(f"Template update failed: {e}")
        return create_error_response(
            message=f"Template update failed: {str(e)}", status_code=500
        )


@router.get("/health")
async def conversion_health_check():
    """Health check endpoint for conversion service"""
    try:
        return create_success_response(
            data={
                "service": "conversion",
                "status": "healthy",
                "features": ["html-to-docx", "docx-to-html", "template-update"],
            },
            message="Conversion service is healthy",
        )
    except Exception as e:
        logger.error(f"Conversion health check failed: {e}")
        return create_error_response(
            message=f"Service unhealthy: {str(e)}", status_code=503
        )
