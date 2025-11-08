"""
Document Export API Routes
Export documents to PDF, DOCX, TXT with pagination support
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum
from datetime import datetime

from src.middleware.firebase_auth import require_auth
from src.services.document_manager import document_manager
from src.services.document_export_service import DocumentExportService
from src.storage.r2_client import R2Client
from src.core.config import APP_CONFIG
from config.config import get_mongodb
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
    # Option 1: Current state from frontend (for real-time export with unsaved changes)
    content_html: Optional[str] = Field(
        None,
        description="Current HTML content (for unsaved changes, especially for slides)",
    )
    slide_elements: Optional[list] = Field(
        None,
        description="Current overlay elements for SLIDE documents (JSON array) - format: [{slideIndex: int, elements: []}]",
    )

    # Option 2: Document reference (for saved documents)
    document_id: Optional[str] = Field(
        None, description="Document ID to load from DB (if no current state provided)"
    )

    # Common fields
    title: Optional[str] = Field(None, description="Document title (optional)")
    document_type: Optional[str] = Field(
        None,
        description="Document type: doc/slide/note (optional, for proper page sizing)",
    )
    format: ExportFormat = Field(
        ..., description="Export format (pdf, docx, txt, html)"
    )

    # Page range (optional)
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

    **Two Export Modes:**
    1. **With current state** (content_html + slide_elements): Export without saving first
    2. **From database** (document_id): Export saved document

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

    **Example (with current state):**
    ```json
    {
      "content_html": "<div>...</div>",
      "slide_elements": [{"slideIndex": 0, "elements": [...]}],
      "title": "My Presentation",
      "document_type": "slide",
      "format": "pdf"
    }
    ```

    **Example (from database):**
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
            f"📥 Export request from user {user_info['uid']}: format={request.format}"
        )

        # Determine export mode: content_html provided (real-time) or document_id (from DB)
        if request.content_html:
            # Mode 1: Export with current state from frontend (may include unsaved changes)
            logger.info("📝 Export mode: Real-time with current state")
            content_html = request.content_html
            title = request.title or "Untitled"
            document_type = request.document_type or "doc"
            document_id = (
                request.document_id
                or f"temp_{user_info['uid']}_{int(datetime.now().timestamp())}"
            )

        elif request.document_id:
            # Mode 2: Export from database
            logger.info(
                f"💾 Export mode: From database (document_id={request.document_id})"
            )
            doc = document_manager.get_document(request.document_id, user_info["uid"])
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")

            content_html = doc.get("content_html", "")
            if not content_html:
                raise HTTPException(status_code=400, detail="Document has no content")

            title = doc.get("title", "Untitled")
            document_type = doc.get("document_type", "doc")
            document_id = request.document_id

            # Load slide_elements from database if not provided
            if not request.slide_elements:
                request.slide_elements = doc.get("slide_elements", [])
        else:
            raise HTTPException(
                status_code=400,
                detail="Either content_html or document_id must be provided",
            )

        # Validate format for document type
        if request.format == ExportFormat.TXT and document_type != "note":
            raise HTTPException(
                status_code=400, detail="TXT export is only supported for notes"
            )

        # Initialize R2 client and export service
        r2_client = R2Client(
            account_id=APP_CONFIG["r2_account_id"],
            access_key_id=APP_CONFIG["r2_access_key_id"],
            secret_access_key=APP_CONFIG["r2_secret_access_key"],
            bucket_name=APP_CONFIG["r2_bucket_name"],
        )

        db = get_mongodb()
        export_service = DocumentExportService(r2_client, db)

        # Reconstruct HTML with overlay elements if slide_elements provided (slide documents only)
        if request.slide_elements and document_type == "slide":
            # Count total elements
            total_elements = sum(
                len(slide.get("elements", [])) for slide in request.slide_elements
            )
            logger.info(
                f"🎨 [SLIDE_ELEMENTS_EXPORT] document_id={document_id}, "
                f"user_id={user_info['uid']}, slides={len(request.slide_elements)}, "
                f"total_overlay_elements={total_elements}, format={request.format}"
            )
            logger.info(
                f"🔧 Reconstructing HTML with {len(request.slide_elements)} slide overlay groups"
            )
            content_html = export_service.reconstruct_html_with_overlays(
                content_html, request.slide_elements
            )
        elif document_type == "slide":
            logger.info(
                f"📄 [SLIDE_ELEMENTS_EXPORT] document_id={document_id}, "
                f"user_id={user_info['uid']}, slide_elements=None or empty (no overlays to export)"
            )

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
            document_id=document_id,
            html_content=content_html,
            title=title,
            format=request.format.value,
            document_type=document_type,  # Pass document_type for proper page sizing
        )

        logger.info(f"✅ Export successful: {document_id} → {result['filename']}")

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
