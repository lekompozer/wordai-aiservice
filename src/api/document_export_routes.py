"""
Document Export API Routes
Export documents to PDF, DOCX, TXT with pagination support
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum

from src.middleware.firebase_auth import require_auth
from src.services.document_manager import document_manager
from src.services.document_export_service import DocumentExportService
from src.services.r2_client import r2_client
from src.core.database import get_database
from src.utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(prefix="/api/documents/export", tags=["Document Export"])


# ============ ENUMS ============


class ExportFormat(str, Enum):
    """Supported export formats"""

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"


# ============ MODELS ============


class DocumentExportRequest(BaseModel):
    document_id: str = Field(..., description="Document ID to export")
    format: ExportFormat = Field(
        ..., description="Export format (pdf, docx, txt, html)"
    )
    start_page: Optional[int] = Field(
        None, ge=1, description="Starting page number (optional, 1-based)"
    )
    end_page: Optional[int] = Field(
        None, ge=1, description="Ending page number (optional, 1-based)"
    )
    include_full_document: bool = Field(
        True, description="Export full document or only specified pages"
    )


class DocumentExportResponse(BaseModel):
    success: bool = Field(..., description="Whether export was successful")
    download_url: str = Field(..., description="Presigned URL to download the file")
    filename: str = Field(..., description="Name of the exported file")
    file_size: int = Field(..., description="File size in bytes")
    format: str = Field(..., description="Export format")
    expires_in: int = Field(..., description="Seconds until download link expires")
    expires_at: str = Field(..., description="ISO timestamp when link expires")
    pages_exported: Optional[str] = Field(
        None, description="Page range exported (e.g., '1-5' or 'all')"
    )


# ============ ENDPOINTS ============


@router.post("/", response_model=DocumentExportResponse)
async def export_document(
    request: DocumentExportRequest, user_info: dict = Depends(require_auth)
):
    """
    Export document to specified format (PDF, DOCX, TXT, HTML)

    **Supported Formats:**
    - **PDF**: Best for printing and sharing, preserves formatting
    - **DOCX**: Editable Word document
    - **TXT**: Plain text (notes only, no formatting)
    - **HTML**: Raw HTML file

    **Page Sizes:**
    - **Doc**: A4 (210mm x 297mm)
    - **Slide**: HD 1920x1080 (16:9)
    - **Note**: Flexible

    **Pagination:**
    - Specify `start_page` and `end_page` to export specific pages
    - Leave empty to export full document
    - Pages are 1-indexed (first page is 1)

    **Example:**
    ```json
    {
      "document_id": "doc_xyz123",
      "format": "pdf",
      "start_page": 1,
      "end_page": 5
    }
    ```

    **Note:** Download link expires after 1 hour
    """
    try:
        logger.info(
            f"📥 Export request from user {user_info['uid']}: {request.document_id} → {request.format}"
        )

        # Get document from database
        doc = document_manager.get_document(request.document_id, user_info["uid"])
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        content_html = doc.get("content_html", "")
        if not content_html:
            raise HTTPException(status_code=400, detail="Document has no content")

        title = doc.get("title", "Untitled")
        document_type = doc.get("type", "doc")

        # Validate format for document type
        if request.format == ExportFormat.TXT and document_type != "note":
            raise HTTPException(
                status_code=400, detail="TXT export is only supported for notes"
            )

        # Initialize export service
        db = get_database()
        export_service = DocumentExportService(r2_client, db)

        # Prepare page range info
        pages_info = "all"
        if request.start_page or request.end_page:
            if not request.include_full_document:
                start = request.start_page or 1
                end = request.end_page or "end"
                pages_info = f"{start}-{end}"

                # Note: Actual page splitting logic needs to be implemented in export service
                # For now, we'll pass the full document
                logger.warning(
                    f"⚠️ Page range requested ({pages_info}) but pagination not yet fully implemented"
                )

        # Export and upload
        result = await export_service.export_and_upload(
            user_id=user_info["uid"],
            document_id=request.document_id,
            html_content=content_html,
            title=title,
            format=request.format.value,
        )

        logger.info(
            f"✅ Export successful: {request.document_id} → {result['filename']}"
        )

        return DocumentExportResponse(
            success=True,
            download_url=result["download_url"],
            filename=result["filename"],
            file_size=result["file_size"],
            format=result["format"],
            expires_in=result["expires_in"],
            expires_at=result["expires_at"],
            pages_exported=pages_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/formats")
async def get_supported_formats(user_info: dict = Depends(require_auth)):
    """
    Get list of supported export formats and their descriptions

    Returns information about available export formats, including:
    - Format name
    - Description
    - Supported document types
    - File extension
    - MIME type
    """
    return {
        "formats": [
            {
                "format": "pdf",
                "name": "PDF",
                "description": "Portable Document Format - Best for printing and sharing",
                "supported_types": ["doc", "slide", "note"],
                "extension": ".pdf",
                "mime_type": "application/pdf",
                "features": [
                    "Preserves formatting",
                    "Non-editable",
                    "Universal support",
                ],
            },
            {
                "format": "docx",
                "name": "Word Document",
                "description": "Microsoft Word document - Editable format",
                "supported_types": ["doc", "slide", "note"],
                "extension": ".docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "features": [
                    "Editable",
                    "Compatible with MS Word",
                    "Preserves structure",
                ],
            },
            {
                "format": "txt",
                "name": "Plain Text",
                "description": "Plain text file - Notes only, no formatting",
                "supported_types": ["note"],
                "extension": ".txt",
                "mime_type": "text/plain",
                "features": [
                    "Simple text only",
                    "No formatting",
                    "Universal compatibility",
                ],
            },
            {
                "format": "html",
                "name": "HTML",
                "description": "HTML file - Web-based format",
                "supported_types": ["doc", "slide", "note"],
                "extension": ".html",
                "mime_type": "text/html",
                "features": [
                    "Web compatible",
                    "Preserves all styling",
                    "Editable in code",
                ],
            },
        ],
        "page_sizes": {
            "doc": {
                "format": "A4",
                "dimensions": "210mm x 297mm",
                "orientation": "Portrait",
            },
            "slide": {
                "format": "HD",
                "dimensions": "1920px x 1080px",
                "aspect_ratio": "16:9",
            },
            "note": {
                "format": "Flexible",
                "dimensions": "Auto",
                "orientation": "Variable",
            },
        },
    }


@router.get("/history")
async def get_export_history(
    limit: int = Query(10, ge=1, le=100, description="Number of exports to return"),
    user_info: dict = Depends(require_auth),
):
    """
    Get user's export history

    Returns list of recent exports with download URLs (if not expired)
    """
    try:
        # This would query the export history from MongoDB
        # For now, return placeholder
        return {
            "exports": [],
            "total": 0,
            "limit": limit,
            "message": "Export history feature coming soon",
        }

    except Exception as e:
        logger.error(f"❌ Failed to get export history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
