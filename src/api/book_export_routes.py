"""
Book Export API Routes
Export books (full or selected chapters) to PDF, DOCX, TXT, HTML
Supports both single-chapter and multi-chapter exports
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from enum import Enum
from datetime import datetime

from src.middleware.firebase_auth import require_auth
from src.services.book_chapter_manager import GuideBookBookChapterManager
from src.services.document_export_service import DocumentExportService
from src.storage.r2_client import R2Client
from src.core.config import APP_CONFIG
from config.config import get_mongodb
from src.utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(prefix="/api/v1/books", tags=["Book Export"])


# ============ HELPER FUNCTIONS ============


def render_background_css(background_config: Optional[Dict[str, Any]]) -> str:
    """
    Render CSS styles for background configuration
    
    Args:
        background_config: BackgroundConfig dict from database
        
    Returns:
        CSS string for inline styles
    """
    if not background_config:
        return "background: white;"
    
    bg_type = background_config.get("type")
    
    # Type: solid
    if bg_type == "solid":
        color = background_config.get("color", "#ffffff")
        return f"background-color: {color};"
    
    # Type: gradient
    elif bg_type == "gradient":
        gradient = background_config.get("gradient", {})
        colors = gradient.get("colors", ["#ffffff", "#f0f0f0"])
        gradient_type = gradient.get("type", "linear")
        angle = gradient.get("angle", 135)
        
        if gradient_type == "linear":
            return f"background: linear-gradient({angle}deg, {colors[0]}, {colors[1]});"
        elif gradient_type == "radial":
            return f"background: radial-gradient(circle, {colors[0]}, {colors[1]});"
        elif gradient_type == "conic":
            return f"background: conic-gradient(from {angle}deg, {colors[0]}, {colors[1]});"
    
    # Type: theme (use simple background - frontend handles full theme rendering)
    elif bg_type == "theme":
        theme = background_config.get("theme", "")
        # Simple theme mapping for PDF export
        theme_colors = {
            "ocean": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "forest": "linear-gradient(135deg, #134e5e 0%, #71b280 100%)",
            "sunset": "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
            "midnight": "linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)",
            "newspaper": "background-color: #f5f1e8; background-image: repeating-linear-gradient(0deg, transparent, transparent 35px, rgba(0,0,0,.05) 35px, rgba(0,0,0,.05) 36px);",
            "book_page": "background-color: #faf8f3;",
            "leather": "background: linear-gradient(135deg, #8b4513 0%, #654321 100%);",
            "modern": "background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);",
        }
        theme_style = theme_colors.get(theme, "background-color: #ffffff;")
        return theme_style
    
    # Type: ai_image or custom_image
    elif bg_type in ["ai_image", "custom_image"]:
        image = background_config.get("image", {})
        image_url = image.get("url")
        overlay_opacity = image.get("overlay_opacity", 0)
        overlay_color = image.get("overlay_color", "#000000")
        
        if not image_url:
            return "background: white;"
        
        # Base image style
        style = f"background-image: url('{image_url}'); background-size: cover; background-position: center; background-repeat: no-repeat;"
        
        # Add overlay if specified
        if overlay_opacity and overlay_opacity > 0:
            # Note: CSS doesn't support overlay easily in inline styles
            # We'll use a semi-transparent background-color blend
            # For better results, need to use pseudo-elements (not possible in inline)
            hex_color = overlay_color.lstrip('#')
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            style += f" background-blend-mode: overlay; background-color: rgba({r}, {g}, {b}, {overlay_opacity});"
        
        return style
    
    # Default: white background
    return "background: white;"


# ============ ENUMS ============


class ExportFormat(str, Enum):
    """Supported export formats"""

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"


class ExportScope(str, Enum):
    """Export scope"""

    FULL_BOOK = "full_book"  # All published chapters
    SELECTED_CHAPTERS = "selected_chapters"  # Only specified chapters


# ============ MODELS ============


class BookExportRequest(BaseModel):
    """Request model for book export"""

    format: ExportFormat = Field(
        ..., description="Export format (pdf, docx, txt, html)"
    )

    scope: ExportScope = Field(
        ExportScope.FULL_BOOK,
        description="Export scope: full_book or selected_chapters",
    )

    chapter_ids: Optional[List[str]] = Field(
        None,
        description="List of chapter IDs to export (required if scope=selected_chapters)",
    )

    include_cover: bool = Field(True, description="Include book cover page in export")

    include_toc: bool = Field(True, description="Include table of contents in export")

    include_metadata: bool = Field(
        True, description="Include book metadata (author, description, etc.)"
    )


class BookExportResponse(BaseModel):
    """Response model for book export"""

    success: bool = Field(..., description="Whether export was successful")
    download_url: str = Field(..., description="Presigned URL to download the file")
    filename: str = Field(..., description="Name of the exported file")
    file_size: int = Field(..., description="File size in bytes")
    format: str = Field(..., description="Export format")
    expires_in: int = Field(..., description="Seconds until download link expires")
    expires_at: str = Field(..., description="ISO timestamp when link expires")
    chapters_exported: int = Field(..., description="Number of chapters included")
    book_title: str = Field(..., description="Book title")


# ============ ENDPOINTS ============


@router.post("/{book_id}/export", response_model=BookExportResponse)
async def export_book(
    book_id: str,
    request: BookExportRequest,
    user_info: dict = Depends(require_auth),
):
    """
    **Export book to PDF, DOCX, TXT, or HTML**

    Export entire book or selected chapters with customizable options.

    **Features:**
    - ✅ Full book export with all published chapters
    - ✅ Selective chapter export
    - ✅ Optional cover page, TOC, and metadata
    - ✅ Multiple formats: PDF, DOCX, TXT, HTML
    - ✅ Owner access (free) or paid PDF download access
    - ✅ Points-based payment for non-owners

    **Export Scope:**
    1. **Full Book** (`scope: "full_book"`):
       - Exports all published chapters
       - Maintains chapter order (by order_index)
       - Includes nested chapters (respects hierarchy)

    2. **Selected Chapters** (`scope: "selected_chapters"`):
       - Exports only specified chapter_ids
       - Must provide chapter_ids array
       - Maintains specified order

    **Document Structure:**
    ```
    [Cover Page] (optional)
    [Metadata Page] (optional)
      - Title
      - Author
      - Description
      - Published date

    [Table of Contents] (optional)
      - Chapter 1
        - Subchapter 1.1
        - Subchapter 1.2
      - Chapter 2

    [Chapters Content]
      - Chapter 1 content
      - Subchapter 1.1 content
      - ...
    ```

    **Authentication:** Required (Owner or user with sufficient points for PDF purchase)

    **Path Parameters:**
    - `book_id`: Book UUID

    **Request Body:**
    ```json
    {
      "format": "pdf",
      "scope": "full_book",
      "include_cover": true,
      "include_toc": true,
      "include_metadata": true
    }
    ```

    **Or for selected chapters:**
    ```json
    {
      "format": "pdf",
      "scope": "selected_chapters",
      "chapter_ids": ["chapter_123", "chapter_456"],
      "include_cover": false,
      "include_toc": true,
      "include_metadata": false
    }
    ```

    **Returns:**
    - 200: Export successful with download URL
    - 400: Invalid request (e.g., no chapters specified, insufficient points)
    - 403: No access permission (not owner and insufficient points)
    - 404: Book or chapters not found
    - 500: Export failed

    **Download URL:** Expires in 1 hour
    """
    try:
        user_id = user_info["uid"]
        db = get_mongodb()

        logger.info(
            f"📚 Book export request: book_id={book_id}, "
            f"user_id={user_id}, format={request.format}, scope={request.scope}"
        )

        # Get book (don't filter by user_id yet - we'll check access separately)
        book = db.online_books.find_one({"book_id": book_id, "is_deleted": False})

        if not book:
            raise HTTPException(
                status_code=404,
                detail="Book not found",
            )

        book_owner_id = book.get("user_id")
        is_owner = book_owner_id == user_id

        # Case 1: Owner can export for free
        if is_owner:
            logger.info(f"✅ Owner {user_id} exporting book {book_id} (free)")

        # Case 2: Non-owner must pay with points
        else:
            access_config = book.get("access_config", {})
            pdf_price = access_config.get("download_pdf_points", 0)

            # Check if PDF download is enabled and has a price
            if pdf_price <= 0 or not access_config.get("is_download_enabled", False):
                raise HTTPException(
                    status_code=403,
                    detail="PDF download is not available for this book",
                )

            # Check if user already purchased PDF access
            existing_purchase = db.book_purchases.find_one(
                {
                    "user_id": user_id,
                    "book_id": book_id,
                    "purchase_type": "pdf_download",
                }
            )

            if existing_purchase:
                logger.info(
                    f"✅ User {user_id} already purchased PDF access to book {book_id}"
                )
            else:
                # Need to purchase - check balance and deduct points
                subscription = db.user_subscriptions.find_one({"user_id": user_id})
                if not subscription:
                    raise HTTPException(
                        status_code=404,
                        detail="User subscription not found",
                    )

                user_balance = subscription.get("points_remaining", 0)

                if user_balance < pdf_price:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient points. Required: {pdf_price} points, Available: {user_balance}",
                    )

                # Calculate revenue split (80% owner, 20% platform)
                owner_reward = int(pdf_price * 0.8)
                system_fee = pdf_price - owner_reward

                # Deduct points from buyer
                from datetime import timezone

                result = db.user_subscriptions.update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {
                            "points_remaining": -pdf_price,
                            "points_used": pdf_price,
                        },
                        "$set": {"updated_at": datetime.now(timezone.utc)},
                    },
                )

                if result.modified_count == 0:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to deduct points",
                    )

                # Create purchase record
                import uuid

                purchase_id = f"purchase_{uuid.uuid4().hex[:16]}"
                purchase_time = datetime.utcnow()

                purchase_record = {
                    "purchase_id": purchase_id,
                    "user_id": user_id,
                    "book_id": book_id,
                    "purchase_type": "pdf_download",
                    "points_spent": pdf_price,
                    "access_expires_at": None,  # PDF download never expires
                    "purchased_at": purchase_time,
                }

                db.book_purchases.insert_one(purchase_record)

                # Update book stats
                db.online_books.update_one(
                    {"book_id": book_id},
                    {
                        "$inc": {
                            "stats.total_revenue_points": pdf_price,
                            "stats.owner_reward_points": owner_reward,
                            "stats.system_fee_points": system_fee,
                            "stats.pdf_downloads": 1,
                            "stats.pdf_revenue": pdf_price,
                            "community_config.total_purchases": 1,
                            "community_config.total_downloads": 1,
                        }
                    },
                )

                logger.info(
                    f"💰 User {user_id} purchased PDF access to book {book_id} "
                    f"for {pdf_price} points (owner: {owner_reward}, fee: {system_fee})"
                )

        book_title = book.get("title", "Untitled Book")
        book_description = book.get("description", "")
        book_cover_url = book.get("cover_image_url")
        book_authors = book.get("authors", [])

        # Get chapters to export
        chapter_manager = GuideBookBookChapterManager(db)

        if request.scope == ExportScope.FULL_BOOK:
            # Export all published chapters
            chapters_cursor = db.book_chapters.find(
                {"book_id": book_id, "is_published": True}
            ).sort("order_index", 1)

            chapters = list(chapters_cursor)

            if not chapters:
                raise HTTPException(
                    status_code=400, detail="No published chapters found in this book"
                )

            logger.info(f"📖 Exporting full book: {len(chapters)} chapters")

        else:  # SELECTED_CHAPTERS
            if not request.chapter_ids:
                raise HTTPException(
                    status_code=400,
                    detail="chapter_ids required when scope=selected_chapters",
                )

            chapters = []
            for chapter_id in request.chapter_ids:
                chapter = db.book_chapters.find_one(
                    {"chapter_id": chapter_id, "book_id": book_id}
                )

                if chapter:
                    chapters.append(chapter)
                else:
                    logger.warning(f"⚠️ Chapter {chapter_id} not found, skipping")

            if not chapters:
                raise HTTPException(
                    status_code=404, detail="None of the specified chapters were found"
                )

            logger.info(
                f"📑 Exporting selected chapters: {len(chapters)}/{len(request.chapter_ids)}"
            )

        # Build combined HTML content
        html_parts = []

        # 1. Cover page (optional)
        if request.include_cover:
            cover_html = f"""
            <div class="book-cover" style="
                page-break-after: always;
                text-align: center;
                padding: 4em 2em;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                min-height: 80vh;
            ">
                {f'<img src="{book_cover_url}" style="max-width: 400px; margin-bottom: 2em;" />' if book_cover_url else ''}
                <h1 style="font-size: 3em; margin-bottom: 0.5em;">{book_title}</h1>
                {f'<p style="font-size: 1.2em; color: #666;">{book_description}</p>' if book_description else ''}
            </div>
            """
            html_parts.append(cover_html)

        # 2. Metadata page (optional)
        if request.include_metadata:
            community_config = book.get("community_config", {})
            published_at = community_config.get("published_at")

            metadata_html = f"""
            <div class="book-metadata" style="page-break-after: always; padding: 2em;">
                <h2>Book Information</h2>
                <table style="width: 100%; margin-top: 2em; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 0.5em; font-weight: bold; width: 30%;">Title:</td>
                        <td style="padding: 0.5em;">{book_title}</td>
                    </tr>
                    {f'<tr><td style="padding: 0.5em; font-weight: bold;">Author:</td><td style="padding: 0.5em;">{", ".join(book_authors)}</td></tr>' if book_authors else ''}
                    {f'<tr><td style="padding: 0.5em; font-weight: bold;">Description:</td><td style="padding: 0.5em;">{book_description}</td></tr>' if book_description else ''}
                    {f'<tr><td style="padding: 0.5em; font-weight: bold;">Published:</td><td style="padding: 0.5em;">{published_at.strftime("%B %d, %Y") if published_at else "N/A"}</td></tr>' if published_at else ''}
                    <tr>
                        <td style="padding: 0.5em; font-weight: bold;">Chapters:</td>
                        <td style="padding: 0.5em;">{len(chapters)}</td>
                    </tr>
                </table>
            </div>
            """
            html_parts.append(metadata_html)

        # 3. Table of contents (optional)
        if request.include_toc:
            toc_html = '<div class="table-of-contents" style="page-break-after: always; padding: 2em;">'
            toc_html += "<h2>Table of Contents</h2>"
            toc_html += (
                '<ul style="list-style: none; padding-left: 0; margin-top: 2em;">'
            )

            for idx, chapter in enumerate(chapters, 1):
                depth = chapter.get("depth", 0)
                indent = depth * 2  # 2em per level

                toc_html += f"""
                <li style="
                    padding: 0.5em 0;
                    margin-left: {indent}em;
                    {f'font-weight: bold;' if depth == 0 else ''}
                ">
                    {idx}. {chapter["title"]}
                </li>
                """

            toc_html += "</ul></div>"
            html_parts.append(toc_html)

        # 4. Chapter contents
        book_background_config = book.get("background_config")
        
        for idx, chapter in enumerate(chapters, 1):
            chapter_id = chapter["chapter_id"]

            # Get chapter content with full HTML
            chapter_with_content = chapter_manager.get_chapter_with_content(chapter_id)

            if not chapter_with_content:
                logger.warning(f"⚠️ Could not load content for chapter {chapter_id}")
                continue

            content_html = chapter_with_content.get("content_html", "")

            if not content_html:
                logger.warning(f"⚠️ Chapter {chapter_id} has no content")
                content_html = "<p><em>No content</em></p>"

            # Get background config (chapter overrides book)
            chapter_background = chapter_with_content.get("background_config")
            effective_background = chapter_background if chapter_background else book_background_config
            
            # Render background CSS
            background_style = render_background_css(effective_background)

            # Wrap chapter content
            depth = chapter.get("depth", 0)
            heading_level = min(depth + 1, 6)  # H1-H6

            chapter_html = f"""
            <div class="chapter" id="chapter-{chapter_id}" style="
                page-break-before: {'always' if idx > 1 else 'auto'};
                padding: 2em;
                {background_style}
                min-height: 100vh;
            ">
                <h{heading_level} style="
                    font-size: {3 - (depth * 0.3)}em;
                    margin-bottom: 1em;
                    color: #1a1a1a;
                ">
                    Chapter {idx}: {chapter["title"]}
                </h{heading_level}>

                <div class="chapter-content">
                    {content_html}
                </div>
            </div>
            """

            html_parts.append(chapter_html)

        # Combine all HTML
        combined_html = "\n".join(html_parts)

        # Wrap in document structure
        final_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{book_title}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 210mm;
                    margin: 0 auto;
                    padding: 20mm;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    margin-top: 1em;
                    margin-bottom: 0.5em;
                    line-height: 1.2;
                }}
                p {{
                    margin-bottom: 1em;
                }}
                @media print {{
                    body {{
                        max-width: 100%;
                    }}
                }}
            </style>
        </head>
        <body>
            {combined_html}
        </body>
        </html>
        """

        # Initialize export service
        r2_client = R2Client(
            account_id=APP_CONFIG["r2_account_id"],
            access_key_id=APP_CONFIG["r2_access_key_id"],
            secret_access_key=APP_CONFIG["r2_secret_access_key"],
            bucket_name=APP_CONFIG["r2_bucket_name"],
        )

        export_service = DocumentExportService(r2_client, db)

        # Generate filename
        safe_title = "".join(
            c for c in book_title if c.isalnum() or c in (" ", "-", "_")
        ).strip()
        safe_title = safe_title.replace(" ", "_")
        export_id = f"book_{book_id}_{int(datetime.now().timestamp())}"

        # Export and upload
        result = await export_service.export_and_upload(
            user_id=user_id,
            document_id=export_id,
            html_content=final_html,
            title=safe_title,
            format=request.format.value,
            document_type="doc",  # Books are treated as documents for export
        )

        logger.info(
            f"✅ Book export successful: {book_id} → {result['filename']} "
            f"({len(chapters)} chapters, {result['file_size']} bytes)"
        )

        return BookExportResponse(
            success=True,
            download_url=result["download_url"],
            filename=result["filename"],
            file_size=result["file_size"],
            format=result["format"],
            expires_in=result["expires_in"],
            expires_at=result["expires_at"],
            chapters_exported=len(chapters),
            book_title=book_title,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Book export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Book export failed: {str(e)}")


@router.get("/{book_id}/export/formats")
async def get_book_export_formats(
    book_id: str, user_info: dict = Depends(require_auth)
):
    """
    **Get supported export formats for books**

    Returns information about available export formats with descriptions.

    **Authentication:** Required
    """
    return {
        "formats": [
            {
                "format": "pdf",
                "name": "PDF",
                "description": "Best for printing and sharing - preserves all formatting",
                "extension": ".pdf",
                "mime_type": "application/pdf",
                "features": [
                    "Professional appearance",
                    "Universal support",
                    "Non-editable",
                    "Perfect for distribution",
                ],
            },
            {
                "format": "docx",
                "name": "Word Document",
                "description": "Editable format for Microsoft Word",
                "extension": ".docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "features": [
                    "Fully editable",
                    "Compatible with MS Word",
                    "Preserves structure",
                    "Good for collaboration",
                ],
            },
            {
                "format": "html",
                "name": "HTML",
                "description": "Web-compatible format with full styling",
                "extension": ".html",
                "mime_type": "text/html",
                "features": [
                    "Web-ready",
                    "All styling preserved",
                    "Can be hosted online",
                    "View in any browser",
                ],
            },
            {
                "format": "txt",
                "name": "Plain Text",
                "description": "Simple text format without styling",
                "extension": ".txt",
                "mime_type": "text/plain",
                "features": [
                    "Plain text only",
                    "No formatting",
                    "Smallest file size",
                    "Universal compatibility",
                ],
            },
        ],
        "export_options": {
            "scope": {
                "full_book": "Export all published chapters",
                "selected_chapters": "Export only selected chapters",
            },
            "optional_sections": {
                "cover": "Include cover page with title and image",
                "metadata": "Include book information page",
                "toc": "Include table of contents",
            },
        },
    }
