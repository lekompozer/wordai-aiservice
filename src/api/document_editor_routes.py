"""
Document Editor API Routes
API endpoints for document management with auto-save functionality
Using asyncio.to_thread to wrap synchronous PyMongo calls
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import asyncio

from src.models.document_editor_models import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListItem,
    FolderCreate,
    FolderUpdate,
    FolderResponse,
    DocumentsByFolderResponse,
    FolderWithDocuments,
)
from src.models.subscription import SubscriptionUsageUpdate
from src.services.document_manager import DocumentManager
from src.services.file_download_service import FileDownloadService
from src.services.user_manager import UserManager
from src.services.subscription_service import get_subscription_service
from src.services.online_test_utils import get_mongodb_service
from src.middleware.auth import verify_firebase_token
from src.database.db_manager import DBManager

# Use 'chatbot' logger to match app.py logging configuration
logger = logging.getLogger("chatbot")
router = APIRouter(prefix="/api/documents", tags=["Document Editor"])

# Global instances
_document_manager = None
_user_manager = None


def format_content_for_document_type(text_content: str, document_type: str) -> str:
    """
    Format text content to HTML with appropriate styling for document type

    Args:
        text_content: Plain text content (with [PAGE_BREAK] markers from PDF parser)
        document_type: "doc", "slide", or "note"

    Returns:
        Formatted HTML with document-type-specific wrapper and styling
    """
    # Split by page breaks if present (from PDF/Word)
    if "[PAGE_BREAK]" in text_content:
        pages = text_content.split("[PAGE_BREAK]")
    else:
        # No page breaks - treat as single page
        pages = [text_content]

    if document_type == "doc":
        # Standard document: A4 size, preserve pages
        html_parts = [
            '<div class="document-content" style="max-width: 210mm; margin: 0 auto; padding: 20mm; background: white;">'
        ]

        for page_num, page_content in enumerate(pages, 1):
            # Remove [PAGE X] markers
            clean_content = page_content.replace(f"[PAGE {page_num}]", "").strip()

            if not clean_content:
                continue

            # Add page container
            html_parts.append(f'<div class="page" data-page="{page_num}">')

            # Split into paragraphs
            paragraphs = clean_content.split("\n\n")
            for para in paragraphs:
                if para.strip():
                    # Preserve inline HTML tags (like <span style="font-size...">) from DOCX
                    # Replace newlines with <br> but keep existing HTML
                    para_html = para.replace("\n", "<br>")
                    html_parts.append(
                        f'<p style="margin-bottom: 1em; line-height: 1.6;">{para_html}</p>'
                    )

            html_parts.append("</div>")  # Close page div

            # Add page break separator (except for last page)
            if page_num < len(pages):
                html_parts.append(
                    '<div class="page-break" style="page-break-after: always; margin: 2em 0; border-top: 2px dashed #ccc;"></div>'
                )

        html_parts.append("</div>")
        return "\n".join(html_parts)

    elif document_type == "slide":
        # Presentation slides: Each page = 1 slide, 16:9 Full HD (1920x1080)
        html_parts = []

        for slide_num, page_content in enumerate(pages, 1):
            # Remove [PAGE X] markers
            clean_content = page_content.replace(f"[PAGE {slide_num}]", "").strip()

            if not clean_content:
                continue

            # Split into paragraphs
            paragraphs = [p.strip() for p in clean_content.split("\n\n") if p.strip()]

            # First paragraph = title, rest = content
            title = paragraphs[0] if paragraphs else f"Slide {slide_num}"
            content_paras = paragraphs[1:] if len(paragraphs) > 1 else []

            # Create slide
            html_parts.append(
                f'<div class="slide" data-slide="{slide_num}" style="'
                f"width: 100%; aspect-ratio: 16/9; max-width: 1920px; margin: 2em auto; "
                f"padding: 3em; background: white; border: 1px solid #ddd; "
                f'display: flex; flex-direction: column; justify-content: center; align-items: center;">'
            )

            # Add title
            html_parts.append(
                f'<h2 style="font-size: 2em; margin-bottom: 0.5em; text-align: center;">{title}</h2>'
            )

            # Add content
            for para in content_paras:
                para_html = para.replace("\n", "<br>")
                html_parts.append(
                    f'<p style="font-size: 1.2em; line-height: 1.8; text-align: center; max-width: 90%;">{para_html}</p>'
                )

            html_parts.append("</div>")

        return (
            "\n".join(html_parts)
            if html_parts
            else '<div class="slide" style="width: 100%; aspect-ratio: 16/9; max-width: 1920px; margin: 2em auto; padding: 3em; background: white; display: flex; justify-content: center; align-items: center;"><p>Empty slide</p></div>'
        )

        return (
            "\n".join(html_parts)
            if html_parts
            else '<div class="slide" style="width: 100%; aspect-ratio: 16/9; max-width: 1280px; margin: 2em auto; padding: 3em; background: white; display: flex; justify-content: center; align-items: center;"><p>Empty slide</p></div>'
        )

    elif document_type == "note":
        # Quick notes: Compact layout, merge all pages, detect bullet points
        # Remove page markers and merge all content
        clean_content = text_content
        for page_num in range(1, 100):  # Remove up to 100 page markers
            clean_content = clean_content.replace(f"[PAGE {page_num}]", "")
        clean_content = clean_content.replace("[PAGE_BREAK]", "\n\n")

        html_parts = [
            '<div class="note-content" style="max-width: 800px; margin: 0 auto; padding: 1em; background: #fffef0; border-left: 4px solid #ffd700;">'
        ]

        paragraphs = clean_content.split("\n\n")
        for para in paragraphs:
            if para.strip():
                # Check if it's a list item (starts with -, *, or number)
                lines = para.split("\n")
                has_list_items = any(
                    line.strip().startswith(("-", "*", "•"))
                    or (line.strip() and line.strip()[0].isdigit() and ". " in line[:5])
                    for line in lines
                )

                if has_list_items:
                    # Format as list
                    html_parts.append(
                        '<ul style="margin: 0.5em 0; padding-left: 1.5em;">'
                    )
                    for line in lines:
                        if line.strip():
                            # Remove list markers
                            clean_line = line.strip().lstrip("-*•").strip()
                            if clean_line and clean_line[0].isdigit():
                                clean_line = clean_line.split(". ", 1)[-1]
                            html_parts.append(
                                f'<li style="margin: 0.3em 0;">{clean_line}</li>'
                            )
                    html_parts.append("</ul>")
                else:
                    # Regular paragraph
                    para_html = para.replace("\n", "<br>")
                    html_parts.append(
                        f'<p style="margin: 0.5em 0; line-height: 1.5;">{para_html}</p>'
                    )

        html_parts.append("</div>")
        return "\n".join(html_parts)

    else:
        # Fallback: simple conversion
        return text_content.replace("\n", "<br>")


def get_document_manager() -> DocumentManager:
    """Get or create DocumentManager instance"""
    global _document_manager

    if _document_manager is None:
        db_manager = DBManager()
        _document_manager = DocumentManager(db_manager.db)
        logger.info("✅ DocumentManager initialized")

    return _document_manager


def get_user_manager() -> UserManager:
    """Get or create UserManager instance"""
    global _user_manager

    if _user_manager is None:
        db_manager = DBManager()
        _user_manager = UserManager(db_manager)
        logger.info("✅ UserManager initialized for documents API")

    return _user_manager


@router.post("/initialize")
@router.post("/initialize/")
async def initialize_indexes(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Initialize database indexes for documents collection
    Chỉ cần gọi 1 lần khi deploy lần đầu
    """
    doc_manager = get_document_manager()

    try:
        # Wrap synchronous call in thread
        await asyncio.to_thread(doc_manager.create_indexes)
        return {"success": True, "message": "Document indexes initialized successfully"}
    except Exception as e:
        logger.error(f"❌ Error initializing indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_model=DocumentResponse)
@router.post("/create/", response_model=DocumentResponse)
async def create_new_document(
    request: DocumentCreate, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Tạo document mới từ đầu (không cần upload file)

    Hỗ trợ 3 loại document:
    - **doc**: Văn bản A4 chuẩn
    - **slide**: Presentation 16:9
    - **note**: Ghi chú tự do

    Request Body:
    ```json
    {
        "title": "My Document",
        "source_type": "created",
        "document_type": "doc",  // "doc" | "slide" | "note"
        "content_html": "",      // Optional, empty cho document mới
        "content_text": ""       // Optional
    }
    ```
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        # === CHECK DOCUMENT LIMIT (NO POINTS DEDUCTION) ===
        subscription_service = get_subscription_service()

        # Check if user can create more documents
        if not await subscription_service.check_documents_limit(user_id):
            subscription = await subscription_service.get_or_create_subscription(
                user_id
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "document_limit_exceeded",
                    "message": f"Bạn đã đạt giới hạn {subscription.documents_limit} documents. Nâng cấp để tạo thêm!",
                    "current_count": subscription.documents_count,
                    "limit": subscription.documents_limit,
                    "upgrade_url": "/pricing",
                },
            )

        logger.info(f"✅ Document limit check passed for user {user_id}")

        # Validate document type for created documents
        if request.source_type == "created":
            if not request.document_type:
                raise HTTPException(
                    status_code=400,
                    detail="document_type is required for created documents",
                )

            if request.document_type not in ["doc", "slide", "note"]:
                raise HTTPException(
                    status_code=400, detail="document_type must be: doc, slide, or note"
                )

        # Create document
        document_id = await asyncio.to_thread(
            doc_manager.create_document,
            user_id=user_id,
            title=request.title,
            content_html=request.content_html or "",
            content_text=request.content_text or "",
            source_type=request.source_type,
            document_type=request.document_type,
            file_id=request.file_id,
            original_r2_url=request.original_r2_url,
            original_file_type=request.original_file_type,
            folder_id=request.folder_id,
        )

        # Get created document
        document = await asyncio.to_thread(
            doc_manager.get_document, document_id, user_id
        )

        if not document:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created document"
            )

        logger.info(
            f"✅ Created {request.source_type} document: {document_id} "
            f"(type: {request.document_type})"
        )

        # === INCREMENT DOCUMENT COUNTER (NO POINTS DEDUCTION) ===
        try:
            await subscription_service.update_usage(
                user_id=user_id, update=SubscriptionUsageUpdate(documents=1)
            )
            logger.info(f"📊 Incremented document counter for user {user_id}")
        except Exception as usage_error:
            logger.error(f"❌ Error updating document counter: {usage_error}")
            # Don't fail the request if counter update fails

        return DocumentResponse(
            document_id=document["document_id"],
            title=document["title"],
            content_html=document["content_html"],
            version=document["version"],
            last_saved_at=document["last_saved_at"],
            file_size_bytes=document["file_size_bytes"],
            auto_save_count=document["auto_save_count"],
            manual_save_count=document["manual_save_count"],
            source_type=document.get("source_type", "file"),
            document_type=document.get("document_type"),
            file_id=document.get("file_id"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/{file_id}", response_model=DocumentResponse)
@router.get("/file/{file_id}/", response_model=DocumentResponse)
async def get_document_by_file(
    file_id: str,
    document_type: Optional[str] = None,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Tạo document mới từ file_id mỗi lần gọi (như "Make a Copy")

    **EVERY EDIT = NEW DOCUMENT**
    - Lần 1 Edit: "Contract.pdf (Copy 1)"
    - Lần 2 Edit: "Contract.pdf (Copy 2)"
    - Lần 3 Edit: "Contract.pdf (Copy 3)"

    **Frontend mở mỗi document trong tab riêng biệt**

    Query Parameters:
    - document_type: Optional - "doc", "slide", or "note" (default: "doc")
                     Frontend can specify preferred document type

    Flow:
    1. Get file info from user_files
    2. Count existing copies of this file
    3. Download from R2 and parse (or reuse cached content)
    4. Create NEW document with incremented copy number
    5. Return new document
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()
    user_manager = get_user_manager()

    try:
        # Step 1: Get file info from user_files collection
        logger.info(f"� Creating NEW document copy from file {file_id}...")

        # Step 1: Get file info from user_files collection
        logger.info(f"📥 Creating NEW document copy from file {file_id}...")

        file_info = await asyncio.to_thread(
            user_manager.get_file_by_id, file_id, user_id
        )

        if not file_info:
            raise HTTPException(status_code=404, detail="File not found in user_files")

        # Get original filename (not the safe filename with timestamp)
        original_filename = file_info.get("original_name") or file_info.get(
            "filename", "Untitled Document"
        )
        logger.info(f"📥 File: {original_filename}")

        # Step 2: Count existing documents from this file_id to generate copy number
        existing_count = await asyncio.to_thread(
            doc_manager.count_documents_by_file_id, file_id, user_id
        )
        copy_number = existing_count + 1

        # Generate title with "Doc{N}" suffix and remove file extension
        # "Contract.pdf" → "Contract Doc1"
        # "Contract.pdf" → "Contract Doc2" on second edit
        # Remove file extensions like .pdf, .docx, .pptx, etc.
        import os

        base_name, ext = os.path.splitext(original_filename)
        new_title = f"{base_name} Doc{copy_number}"
        logger.info(
            f"📝 Creating document copy #{copy_number}: {new_title} (removed extension: {ext})"
        )

        # Step 3: Try to reuse cached content from previous document for speed
        cached_content = None
        if existing_count > 0:
            # Try to get the most recent document's content
            previous_doc = await asyncio.to_thread(
                doc_manager.get_latest_document_by_file_id, file_id, user_id
            )
            if previous_doc:
                prev_html = previous_doc.get("content_html")
                prev_text = previous_doc.get("content_text")

                # Only use cache if content exists and has actual text content
                # Check both HTML length and stripped text content
                if prev_html and prev_html.strip():
                    # Additional check: HTML should have meaningful content, not just empty tags
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(prev_html, "html.parser")
                    text_content = soup.get_text(strip=True)

                    if (
                        text_content and len(text_content) > 10
                    ):  # At least 10 chars of actual text
                        cached_content = {
                            "html": prev_html,
                            "text": prev_text,
                            "type": previous_doc.get("document_type", "doc"),
                        }
                        logger.info(
                            f"♻️ Reusing cached content from previous document (fast path!)"
                        )
                        logger.info(
                            f"♻️ Cached HTML length: {len(prev_html)} chars, Text length: {len(text_content)} chars"
                        )
                    else:
                        text_len = len(text_content) if text_content else 0
                        logger.warning(
                            f"⚠️ Previous document has empty text content (HTML: {len(prev_html)} chars, Text: {text_len} chars), will re-parse file"
                        )
                else:
                    logger.warning(
                        f"⚠️ Previous document has empty or no content_html, will re-parse file"
                    )

        # Step 4: Get content (from cache or parse file)
        if cached_content:
            # Fast path: Reuse content from previous copy
            content_html = cached_content["html"]
            content_text = cached_content["text"]
            final_document_type = (
                document_type
                if document_type in ["doc", "slide", "note"]
                else cached_content["type"]
            )
            logger.info(f"✅ Reused cached content ({len(content_html)} chars)")
        else:
            # Slow path: Download and parse from R2 (first edit)
            logger.info(
                f"📥 Downloading file from R2: {file_info.get('file_name', 'unknown')}"
            )

            # Get r2_key to download directly using boto3 (server has credentials)
            r2_key = file_info.get("r2_key")
            if not r2_key:
                raise HTTPException(
                    status_code=500, detail="File R2 key not found in database"
                )

            logger.info(
                f"🔐 Downloading from R2 using boto3 with credentials (key: {r2_key})"
            )

            # Download and parse file from R2 using r2_key (not URL)
            text_content, temp_file_path = (
                await FileDownloadService.download_and_parse_file_from_r2(
                    r2_key=r2_key,
                    file_type=file_info["file_type"],
                    user_id=user_id,
                )
            )

            if not text_content:
                raise HTTPException(
                    status_code=500, detail="Failed to parse file content"
                )

            # Determine document_type: Use frontend value or default to "doc"
            final_document_type = (
                document_type if document_type in ["doc", "slide", "note"] else "doc"
            )

            # Convert text to HTML with document-type-specific formatting
            logger.info(
                f"📝 Formatting content for document type: {final_document_type}"
            )
            content_html = format_content_for_document_type(
                text_content, final_document_type
            )
            content_text = text_content

            logger.info(
                f"✅ Generated HTML: {len(content_html)} chars for {final_document_type}"
            )

        # Step 5: Create NEW document in MongoDB with unique title
        new_doc_id = await asyncio.to_thread(
            doc_manager.create_document,
            user_id=user_id,
            file_id=file_id,
            title=new_title,  # "Contract.pdf (Copy 1)"
            content_html=content_html,
            content_text=content_text,
            original_r2_url=file_info.get("file_url"),
            original_file_type=file_info.get("file_type"),
            source_type="file",  # This is a file-based document
            document_type=final_document_type,  # Frontend specified or default "doc"
        )

        logger.info(
            f"✅ Created NEW document {new_doc_id} (Copy #{copy_number}) from file {file_id}"
        )

        # Get the newly created document
        document = await asyncio.to_thread(
            doc_manager.get_document, new_doc_id, user_id
        )

        # Log slide_elements info if present
        slide_elements = document.get("slide_elements", [])
        slide_backgrounds = document.get("slide_backgrounds", [])
        if slide_elements:
            total_elements = sum(
                len(slide.get("elements", [])) for slide in slide_elements
            )
            logger.info(
                f"🎨 [SLIDE_ELEMENTS_API_LOAD] document_id={new_doc_id}, file_id={file_id}, "
                f"slides={len(slide_elements)}, total_overlay_elements={total_elements}, "
                f"slide_backgrounds={len(slide_backgrounds)}"
            )

        response = DocumentResponse(
            document_id=document["document_id"],
            title=document["title"],
            content_html=document["content_html"],
            version=document["version"],
            last_saved_at=document["last_saved_at"],
            file_size_bytes=document["file_size_bytes"],
            auto_save_count=document["auto_save_count"],
            manual_save_count=document["manual_save_count"],
            source_type=document.get("source_type", "file"),
            document_type=document.get("document_type"),
            file_id=document.get("file_id"),
            slide_elements=document.get(
                "slide_elements", []
            ),  # ✅ Return overlay elements
            slide_backgrounds=document.get(
                "slide_backgrounds", []
            ),  # ✅ Return slide backgrounds
        )

        logger.warning(f"🔍 FRONTEND: Created NEW document copy #{copy_number}")
        logger.warning(
            f"🔍 FRONTEND: File {file_id} → Document ID: {response.document_id}"
        )
        logger.warning(f"🔍 FRONTEND: Title: {response.title}")
        logger.warning(f"🔍 FRONTEND: Open in NEW TAB - each Edit = new tab!")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting document by file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ FOLDER MANAGEMENT ============
# NOTE: These routes MUST be before /{document_id} to avoid route conflicts


@router.post("/folders", response_model=FolderResponse)
async def create_folder(
    folder: FolderCreate,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Create new folder for documents

    Headers:
        Authorization: Bearer <firebase_token>

    Body:
        {
            "name": "My Documents",
            "description": "Folder for important documents",
            "parent_id": null
        }

    Returns:
        {
            "id": "folder_abc123",
            "name": "My Documents",
            "description": "Folder for important documents",
            "parent_id": null,
            "user_id": "firebase_uid_123",
            "created_at": "2025-10-17T10:30:00",
            "updated_at": "2025-10-17T10:30:00",
            "document_count": 0
        }
    """
    try:
        user_id = user_data.get("uid")
        import uuid

        folder_id = f"folder_{uuid.uuid4().hex[:12]}"
        user_manager = get_user_manager()

        # Create folder in MongoDB (document_folders collection)
        success = await asyncio.to_thread(
            user_manager.create_document_folder,
            folder_id=folder_id,
            user_id=user_id,
            name=folder.name,
            description=folder.description,
            parent_id=folder.parent_id,
        )

        if not success:
            raise HTTPException(
                status_code=400, detail="Failed to create folder (may already exist)"
            )

        # Retrieve the created folder (from document_folders collection)
        folder_doc = await asyncio.to_thread(
            user_manager.get_document_folder,
            folder_id=folder_id,
            user_id=user_id,
        )

        if not folder_doc:
            raise HTTPException(status_code=500, detail="Folder created but not found")

        logger.info(f"✅ Created folder '{folder.name}' for user {user_id}")

        return FolderResponse(
            folder_id=folder_doc.get("folder_id"),
            name=folder_doc.get("name"),
            description=folder_doc.get("description"),
            parent_id=folder_doc.get("parent_id"),
            user_id=folder_doc.get("user_id"),
            created_at=folder_doc.get("created_at"),
            updated_at=folder_doc.get("updated_at"),
            document_count=folder_doc.get("file_count", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to create folder")


@router.get("/folders", response_model=List[FolderResponse])
async def list_folders(
    parent_id: Optional[str] = None,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    List folders for user

    Headers:
        Authorization: Bearer <firebase_token>

    Query Parameters:
        parent_id: Parent folder ID (null for root folders)

    Example:
        GET /api/documents/folders
        GET /api/documents/folders?parent_id=folder_abc123

    Returns:
        [
            {
                "id": "folder_abc123",
                "name": "My Documents",
                "description": "Important files",
                "parent_id": null,
                "user_id": "firebase_uid_123",
                "created_at": "2025-10-17T10:30:00",
                "updated_at": "2025-10-17T10:30:00",
                "document_count": 5
            }
        ]
    """
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        folders_docs = await asyncio.to_thread(
            user_manager.list_document_folders,
            user_id=user_id,
            parent_id=parent_id,
        )

        folders = []
        for doc in folders_docs:
            folders.append(
                FolderResponse(
                    folder_id=doc.get("folder_id"),
                    name=doc.get("name"),
                    description=doc.get("description"),
                    parent_id=doc.get("parent_id"),
                    user_id=doc.get("user_id"),
                    created_at=doc.get("created_at"),
                    updated_at=doc.get("updated_at"),
                    document_count=doc.get("file_count", 0),
                )
            )

        logger.info(
            f"✅ Found {len(folders)} folders for user {user_id} (parent: {parent_id or 'root'})"
        )
        return folders

    except Exception as e:
        logger.error(f"❌ Failed to list folders: {e}")
        raise HTTPException(status_code=500, detail="Failed to list folders")


@router.get("/folders/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get folder details

    Headers:
        Authorization: Bearer <firebase_token>

    Path Parameters:
        folder_id: Folder ID

    Example:
        GET /api/documents/folders/folder_abc123

    Returns:
        {
            "id": "folder_abc123",
            "name": "My Documents",
            "description": "Important files",
            "parent_id": null,
            "user_id": "firebase_uid_123",
            "created_at": "2025-10-17T10:30:00",
            "updated_at": "2025-10-17T10:30:00",
            "document_count": 5
        }
    """
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        folder_doc = await asyncio.to_thread(
            user_manager.get_folder,
            folder_id=folder_id,
            user_id=user_id,
        )

        if not folder_doc:
            raise HTTPException(status_code=404, detail="Folder not found")

        return FolderResponse(
            folder_id=folder_doc.get("folder_id"),
            name=folder_doc.get("name"),
            description=folder_doc.get("description"),
            parent_id=folder_doc.get("parent_id"),
            user_id=folder_doc.get("user_id"),
            created_at=folder_doc.get("created_at"),
            updated_at=folder_doc.get("updated_at"),
            document_count=folder_doc.get("file_count", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get folder: {e}")
        raise HTTPException(status_code=404, detail="Folder not found")


@router.put("/folders/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str,
    folder_update: FolderUpdate,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Update folder

    Headers:
        Authorization: Bearer <firebase_token>

    Path Parameters:
        folder_id: Folder ID

    Body:
        {
            "name": "Updated Folder Name",
            "description": "Updated description"
        }

    Example:
        PUT /api/documents/folders/folder_abc123

    Returns:
        {
            "id": "folder_abc123",
            "name": "Updated Folder Name",
            "description": "Updated description",
            "parent_id": null,
            "user_id": "firebase_uid_123",
            "created_at": "2025-10-17T10:30:00",
            "updated_at": "2025-10-17T12:45:00",
            "document_count": 5
        }
    """
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        success = await asyncio.to_thread(
            user_manager.update_folder,
            folder_id=folder_id,
            user_id=user_id,
            name=folder_update.name,
            description=folder_update.description,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Folder not found")

        # Get updated folder
        folder_doc = await asyncio.to_thread(
            user_manager.get_folder,
            folder_id=folder_id,
            user_id=user_id,
        )

        if not folder_doc:
            raise HTTPException(status_code=500, detail="Folder updated but not found")

        logger.info(f"✅ Updated folder {folder_id} for user {user_id}")

        return FolderResponse(
            folder_id=folder_doc.get("folder_id"),
            name=folder_doc.get("name"),
            description=folder_doc.get("description"),
            parent_id=folder_doc.get("parent_id"),
            user_id=folder_doc.get("user_id"),
            created_at=folder_doc.get("created_at"),
            updated_at=folder_doc.get("updated_at"),
            document_count=folder_doc.get("file_count", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to update folder")


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Delete folder (only if empty)

    Headers:
        Authorization: Bearer <firebase_token>

    Path Parameters:
        folder_id: Folder ID

    Example:
        DELETE /api/documents/folders/folder_abc123

    ⚠️ Important: Folder must be empty (no documents and no subfolders)

    Returns:
        {
            "success": true,
            "message": "Folder deleted successfully"
        }
    """
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        success = await asyncio.to_thread(
            user_manager.delete_folder,
            folder_id=folder_id,
            user_id=user_id,
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete folder: folder not found or contains documents/subfolders",
            )

        logger.info(f"✅ Deleted folder {folder_id} for user {user_id}")

        return {"success": True, "message": "Folder deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete folder")


# ============ END FOLDER MANAGEMENT ============


@router.get("/grouped-by-folders", response_model=DocumentsByFolderResponse)
async def get_documents_by_folders(
    source_type: Optional[str] = None,
    document_type: Optional[str] = None,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Lấy toàn bộ Edited Documents nhóm theo folders

    Trả về tất cả documents được tổ chức theo từng folder:
    - Documents không có folder (ungrouped) sẽ xuất hiện đầu tiên với folder_id = null
    - Sau đó là documents trong các folders

    Query Parameters:
    - **source_type**: Lọc theo nguồn: "file" | "created" (optional)
    - **document_type**: Lọc theo loại: "doc" | "slide" | "note" (optional)

    Response Example:
    ```json
    {
      "folders": [
        {
          "folder_id": null,
          "folder_name": null,
          "folder_description": null,
          "document_count": 3,
          "documents": [
            {
              "document_id": "doc_abc123",
              "title": "Ungrouped Doc",
              "last_saved_at": "2025-10-17T10:30:00Z",
              ...
            }
          ]
        },
        {
          "folder_id": "folder_abc123",
          "folder_name": "Work Documents",
          "folder_description": "Professional docs",
          "document_count": 5,
          "documents": [...]
        }
      ],
      "total_documents": 8
    }
    ```

    Examples:
    - GET /api/documents/grouped-by-folders
    - GET /api/documents/grouped-by-folders?source_type=created
    - GET /api/documents/grouped-by-folders?source_type=created&document_type=doc
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        logger.info(
            f"📁 Getting documents by folders for user {user_id[:8]}... "
            f"(source_type={source_type}, document_type={document_type})"
        )

        # Get documents grouped by folders
        folders_data = await asyncio.to_thread(
            doc_manager.get_documents_by_folders,
            user_id=user_id,
            source_type=source_type,
            document_type=document_type,
        )

        # Convert to response model
        folders_response = []
        total_documents = 0

        for folder_data in folders_data:
            documents = [
                DocumentListItem(
                    document_id=doc["document_id"],
                    title=doc["title"],
                    last_saved_at=doc.get(
                        "last_saved_at", doc.get("updated_at", datetime.now())
                    ),
                    last_opened_at=doc.get("last_opened_at"),
                    version=doc.get("version", 1),
                    file_size_bytes=doc.get("file_size_bytes", 0),
                    source_type=doc.get("source_type", "file"),
                    document_type=doc.get("document_type"),
                    folder_id=doc.get("folder_id"),
                )
                for doc in folder_data["documents"]
            ]

            folders_response.append(
                FolderWithDocuments(
                    folder_id=folder_data["folder_id"],
                    folder_name=folder_data["folder_name"],
                    folder_description=folder_data["folder_description"],
                    document_count=folder_data["document_count"],
                    documents=documents,
                )
            )

            total_documents += folder_data["document_count"]

        logger.info(
            f"✅ Grouped {total_documents} documents into {len(folders_response)} folders "
            f"for user {user_id[:8]}..."
        )

        return DocumentsByFolderResponse(
            folders=folders_response,
            total_documents=total_documents,
        )

    except Exception as e:
        logger.error(f"❌ Error getting documents by folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentResponse)
@router.get(
    "/{document_id}/", response_model=DocumentResponse
)  # Support trailing slash
async def get_document(
    document_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Lấy document theo document_id
    Sử dụng khi đã có document_id (ví dụ từ danh sách documents)
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        document = await asyncio.to_thread(
            doc_manager.get_document, document_id, user_id
        )

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Check if slide narrations exist (for slides only)
        has_narration = False
        narration_count = 0
        if document.get("document_type") == "slide":
            try:
                narration_count = (
                    get_mongodb_service().db.slide_narrations.count_documents(
                        {"presentation_id": document_id, "user_id": user_id}
                    )
                )
                has_narration = narration_count > 0
            except Exception as e:
                logger.warning(f"⚠️ Failed to check narrations: {e}")

        # Log slide_elements info when returning document
        slide_elements = document.get("slide_elements", [])
        slide_backgrounds = document.get("slide_backgrounds", [])
        if slide_elements:
            total_elements = sum(
                len(slide.get("elements", [])) for slide in slide_elements
            )
            logger.info(
                f"🎨 [SLIDE_ELEMENTS_API_LOAD] document_id={document_id}, user_id={user_id}, "
                f"slides={len(slide_elements)}, total_overlay_elements={total_elements}, "
                f"slide_backgrounds={len(slide_backgrounds)}, "
                f"document_type={document.get('document_type')}, "
                f"has_narration={has_narration}, narration_count={narration_count}"
            )
        else:
            logger.info(
                f"📄 [SLIDE_ELEMENTS_API_LOAD] document_id={document_id}, user_id={user_id}, "
                f"slide_elements=[] (empty), document_type={document.get('document_type')}, "
                f"has_narration={has_narration}, narration_count={narration_count}"
            )

        response = DocumentResponse(
            document_id=document["document_id"],
            title=document.get("title", "Untitled"),
            content_html=document.get("content_html", ""),
            version=document.get("version", 1),
            last_saved_at=document.get(
                "last_saved_at", document.get("updated_at", datetime.now())
            ),
            file_size_bytes=document.get("file_size_bytes", 0),
            auto_save_count=document.get("auto_save_count", 0),
            manual_save_count=document.get("manual_save_count", 0),
            source_type=document.get("source_type", "file"),
            document_type=document.get("document_type"),
            file_id=document.get("file_id"),
            slide_elements=document.get(
                "slide_elements", []
            ),  # ✅ Return overlay elements
            slide_backgrounds=document.get(
                "slide_backgrounds", []
            ),  # ✅ Return slide backgrounds
            slides_outline=(
                document.get("slides_outline")
                if document.get("document_type") == "slide"
                else None
            ),  # ✅ Return outline for slides
            outline_id=document.get("outline_id"),  # ✅ Reference to analysis
            has_outline=bool(
                document.get("slides_outline")
            ),  # ✅ Quick check for frontend
            has_narration=has_narration,  # ✅ Quick check if narrations exist
            narration_count=narration_count,  # ✅ Number of narration versions
        )

        # Log response payload for debugging
        response_dict = response.model_dump()
        logger.info(
            f"📤 [RESPONSE] document_id={document_id}, "
            f"has_narration={response.has_narration}, narration_count={response.narration_count}, "
            f"has_outline={response.has_outline}"
        )
        logger.info(f"📦 [RAW_RESPONSE_JSON] {response_dict}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{document_id}")
@router.put("/{document_id}/")  # Support trailing slash
async def save_document(
    document_id: str,
    update_data: DocumentUpdate,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Lưu nội dung document (auto-save hoặc manual save)

    - **is_auto_save=true**: Auto-save từ frontend (mỗi 10s)
    - **is_auto_save=false**: Manual save (user click Save button)

    Auto-save sẽ:
    - Tăng auto_save_count
    - Update last_auto_save_at

    Manual save sẽ:
    - Tăng manual_save_count
    - Update last_manual_save_at

    Cả 2 đều tăng version number
    """
    # 🔍 CRITICAL DEBUG: First line of function
    logger.info(f"🔥 [SAVE_DOCUMENT_CALLED] document_id={document_id}")

    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        # 🔍 DEBUG: Log incoming request data
        logger.info(
            f"📥 [PUT_REQUEST_DEBUG] document_id={document_id}, user_id={user_id}, "
            f"has_slide_elements={update_data.slide_elements is not None}, "
            f"has_slide_backgrounds={update_data.slide_backgrounds is not None}, "
            f"slide_elements_type={type(update_data.slide_elements)}, "
            f"is_auto_save={update_data.is_auto_save}"
        )

        # Extract plain text from HTML if not provided
        content_text = update_data.content_text
        if not content_text:
            # Simple HTML stripping (you can use BeautifulSoup for better results)
            import re

            content_text = re.sub(r"<[^>]+>", "", update_data.content_html)

        # Log slide_elements and slide_backgrounds info before saving
        if update_data.slide_elements or update_data.slide_backgrounds:
            total_elements = sum(
                len(slide.get("elements", []))
                for slide in (update_data.slide_elements or [])
            )
            total_backgrounds = len(update_data.slide_backgrounds or [])
            logger.info(
                f"🎨 [SLIDE_DATA_API_SAVE] document_id={document_id}, user_id={user_id}, "
                f"slides_with_elements={len(update_data.slide_elements or [])}, "
                f"total_overlay_elements={total_elements}, "
                f"slides_with_backgrounds={total_backgrounds}, "
                f"is_auto_save={update_data.is_auto_save}"
            )
        else:
            logger.info(
                f"📄 [SLIDE_DATA_API_SAVE] document_id={document_id}, user_id={user_id}, "
                f"slide_elements=None, slide_backgrounds=None, is_auto_save={update_data.is_auto_save}"
            )

        success = await asyncio.to_thread(
            doc_manager.update_document,
            document_id=document_id,
            user_id=user_id,
            content_html=update_data.content_html,
            content_text=content_text,
            title=update_data.title,
            is_auto_save=update_data.is_auto_save,
            slide_elements=update_data.slide_elements,  # ✅ Pass slide_elements for slides
            slide_backgrounds=update_data.slide_backgrounds,  # ✅ NEW: Pass slide_backgrounds
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="Document not found or not modified"
            )

        save_type = "auto-saved" if update_data.is_auto_save else "saved"
        logger.info(f"💾 Document {document_id} {save_type}")

        return {
            "success": True,
            "message": f"Document {save_type} successfully",
            "is_auto_save": update_data.is_auto_save,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error saving document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{document_id}/move-to-folder")
@router.patch("/{document_id}/move-to-folder/")
async def move_document_to_folder(
    document_id: str,
    folder_id: Optional[str] = None,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Di chuyển document sang folder khác

    Query Parameters:
    - **folder_id**: ID của folder đích (optional)
      - Nếu có giá trị: move document vào folder đó
      - Nếu null hoặc không truyền: move document về root (ungrouped)

    Examples:
    - PATCH /api/documents/{document_id}/move-to-folder?folder_id=folder_abc123
    - PATCH /api/documents/{document_id}/move-to-folder  (move to root)

    Response:
    ```json
    {
      "success": true,
      "message": "Document moved to folder folder_abc123",
      "document_id": "doc_abc123",
      "folder_id": "folder_abc123"
    }
    ```
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        success = await asyncio.to_thread(
            doc_manager.move_document_to_folder,
            document_id=document_id,
            user_id=user_id,
            folder_id=folder_id,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="Document not found or already in target folder"
            )

        folder_info = f"to folder {folder_id}" if folder_id else "to root (ungrouped)"
        logger.info(f"📁 Document {document_id} moved {folder_info}")

        return {
            "success": True,
            "message": f"Document moved {folder_info}",
            "document_id": document_id,
            "folder_id": folder_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error moving document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[DocumentListItem])
async def list_documents(
    limit: int = 20,
    offset: int = 0,
    source_type: Optional[str] = None,
    document_type: Optional[str] = None,
    folder_id: Optional[str] = None,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Lấy danh sách documents của user
    Sắp xếp theo last_opened_at (documents mở gần nhất sẽ lên đầu)

    Query Parameters:
    - **limit**: Số lượng documents trả về (default: 20)
    - **offset**: Vị trí bắt đầu (default: 0)
    - **source_type**: Lọc theo nguồn: "file" | "created" (optional)
    - **document_type**: Lọc theo loại: "doc" | "slide" | "note" (optional)
    - **folder_id**: Lọc theo folder (optional)

    Examples:
    - GET /api/documents?source_type=created&document_type=doc
    - GET /api/documents?source_type=file
    - GET /api/documents?folder_id=folder_abc123
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        logger.info(
            f"📋 Listing documents for user {user_id[:8]}... "
            f"(source_type={source_type}, document_type={document_type}, folder_id={folder_id}, limit={limit}, offset={offset})"
        )

        documents = await asyncio.to_thread(
            doc_manager.list_user_documents,
            user_id=user_id,
            limit=limit,
            offset=offset,
            source_type=source_type,
            document_type=document_type,
            folder_id=folder_id,
        )

        logger.info(f"✅ Found {len(documents)} documents for user {user_id[:8]}...")

        return [
            DocumentListItem(
                document_id=doc["document_id"],
                title=doc["title"],
                last_saved_at=doc.get(
                    "last_saved_at", doc.get("updated_at", datetime.now())
                ),
                last_opened_at=doc.get("last_opened_at"),
                version=doc.get("version", 1),
                file_size_bytes=doc.get("file_size_bytes", 0),
                source_type=doc.get("source_type", "file"),
                document_type=doc.get("document_type"),
                folder_id=doc.get("folder_id"),
            )
            for doc in documents
        ]

    except Exception as e:
        logger.error(f"❌ Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
@router.delete("/{document_id}/")  # Support trailing slash
async def delete_document(
    document_id: str,
    hard_delete: bool = False,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Xóa document

    - **hard_delete=false** (default): Soft delete (đánh dấu is_deleted=true)
    - **hard_delete=true**: Permanent delete (xóa khỏi database)
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        success = await asyncio.to_thread(
            doc_manager.delete_document,
            document_id=document_id,
            user_id=user_id,
            soft_delete=not hard_delete,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        delete_type = "permanently deleted" if hard_delete else "moved to trash"
        return {"success": True, "message": f"Document {delete_type}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/storage")
@router.get("/stats/storage/")
async def get_storage_stats(user_data: Dict[str, Any] = Depends(verify_firebase_token)):
    """
    Lấy thống kê storage của user
    Trả về tổng số documents, dung lượng, số lần save, etc.
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        stats = await asyncio.to_thread(doc_manager.get_storage_stats, user_id)
        return {"success": True, "data": stats}

    except Exception as e:
        logger.error(f"❌ Error getting storage stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trash/list")
@router.get("/trash/list/")
async def list_trash(
    limit: int = 100,
    offset: int = 0,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Lấy danh sách documents trong trash
    Documents được soft-deleted (is_deleted=true)
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        documents = await asyncio.to_thread(
            doc_manager.list_trash_documents, user_id, limit, offset
        )

        # Convert to response format
        items = [
            {
                "document_id": doc["document_id"],
                "title": doc["title"],
                "deleted_at": doc.get("deleted_at"),
                "file_size_bytes": doc.get("file_size_bytes", 0),
                "version": doc.get("version", 1),
                "last_saved_at": doc.get("last_saved_at"),
            }
            for doc in documents
        ]

        return {
            "success": True,
            "data": {
                "documents": items,
                "total": len(items),
                "limit": limit,
                "offset": offset,
            },
        }

    except Exception as e:
        logger.error(f"❌ Error listing trash: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trash/restore/{document_id}")
@router.post("/trash/restore/{document_id}/")
async def restore_from_trash(
    document_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Khôi phục document từ trash
    Set is_deleted=false, deleted_at=null
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        success = await asyncio.to_thread(
            doc_manager.restore_document, document_id, user_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Document not found in trash")

        return {
            "success": True,
            "message": f"Document {document_id} restored from trash",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error restoring document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/trash/empty")
@router.delete("/trash/empty/")
async def empty_trash(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Xóa vĩnh viễn TẤT CẢ documents trong trash
    ⚠️ CẢNH BÁO: Không thể khôi phục sau khi xóa!
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        deleted_count = await asyncio.to_thread(doc_manager.empty_trash, user_id)

        return {
            "success": True,
            "message": f"Permanently deleted {deleted_count} documents from trash",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        logger.error(f"❌ Error emptying trash: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EXPORT / DOWNLOAD ENDPOINTS
# ============================================================================


@router.get("/{document_id}/download/{format}")
@router.get("/{document_id}/download/{format}/")
async def download_document(
    document_id: str,
    format: str,
    document_type: Optional[str] = None,  # Query parameter for page sizing
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Download document in specified format (PDF, DOCX, TXT, HTML)

    **Single endpoint để frontend gọi - Backend tự động:**
    1. Lấy latest HTML content từ MongoDB
    2. Convert sang format yêu cầu (PDF/DOCX/TXT/HTML)
    3. Upload file lên R2
    4. Trả về presigned download URL (1 hour expiry)

    **Supported formats:**
    - `pdf` - Convert HTML → PDF (weasyprint)
    - `docx` - Convert HTML → DOCX (python-docx)
    - `txt` - Strip HTML tags → Plain text
    - `html` - Raw HTML with styling

    **Query Parameters:**
    - `document_type` (optional): Override document type for PDF page sizing
      - `doc` - A4 portrait (210×297mm) with 20mm margins
      - `slide` - FullHD landscape (1920×1080px, 16:9) with 0 margin
      - `note` - A4 portrait (210×297mm) with 20mm margins
      - If not provided, auto-detects from MongoDB document_type field

    **Example:**
    - GET `/api/documents/doc_abc123/download/pdf`
    - GET `/api/documents/slide_123/download/pdf?document_type=slide`

    **Response:**
    ```json
    {
        "download_url": "https://r2.wordai.pro/exports/...",
        "filename": "My_Document_20251009_153045.pdf",
        "file_size": 123456,
        "format": "pdf",
        "expires_in": 3600,
        "expires_at": "2025-10-09T16:30:45Z"
    }
    ```

    Frontend chỉ cần trigger download:
    ```javascript
    window.open(response.download_url, '_blank');
    ```
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    # Validate format
    valid_formats = ["pdf", "docx", "txt", "html"]
    if format.lower() not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format. Supported formats: {', '.join(valid_formats)}",
        )

    try:
        # Step 1: Get document from MongoDB
        document = await asyncio.to_thread(
            doc_manager.get_document, document_id, user_id
        )

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Step 2: Extract data
        html_content = document["content_html"]
        title = document["title"]
        slide_elements = document.get("slide_elements", [])  # Get overlay elements

        # Determine document type: Use query param if provided, otherwise fallback to MongoDB field
        detected_document_type = document_type or document.get("document_type", "doc")

        logger.info(
            f"📄 Document type: {detected_document_type} "
            f"(query param: {document_type}, MongoDB: {document.get('document_type', 'N/A')})"
        )

        if not html_content or html_content.strip() == "":
            raise HTTPException(
                status_code=400, detail="Document content is empty, cannot export"
            )

        # Step 3: Import export service and R2 client
        from src.services.document_export_service import DocumentExportService
        from src.storage.r2_client import R2Client
        from src.core.config import APP_CONFIG
        from config.config import get_mongodb

        # Initialize services
        r2_client = R2Client(
            account_id=APP_CONFIG["r2_account_id"],
            access_key_id=APP_CONFIG["r2_access_key_id"],
            secret_access_key=APP_CONFIG["r2_secret_access_key"],
            bucket_name=APP_CONFIG["r2_bucket_name"],
        )

        db = get_mongodb()
        export_service = DocumentExportService(r2_client=r2_client, db=db)

        # Reconstruct HTML with overlay elements for slides
        if detected_document_type == "slide" and slide_elements:
            logger.info(
                f"🎨 Reconstructing HTML with {len(slide_elements)} overlay element groups"
            )
            html_content = export_service.reconstruct_html_with_overlays(
                html_content, slide_elements
            )
            logger.info(
                f"✅ HTML reconstructed with overlays ({len(html_content)} chars)"
            )

        # Step 4: Check rate limits
        can_export, error_message = await asyncio.to_thread(
            export_service.check_rate_limits, user_id, document_id
        )

        if not can_export:
            raise HTTPException(status_code=429, detail=error_message)

        # Step 5: Export and upload to R2
        logger.info(
            f"📥 Exporting document {document_id} to {format.upper()} for user {user_id}"
        )

        result = await export_service.export_and_upload(
            user_id=user_id,
            document_id=document_id,
            html_content=html_content,
            title=title,
            format=format.lower(),
            document_type=detected_document_type,  # Pass document_type for PDF page sizing
        )

        logger.info(
            f"✅ Export successful: {result['filename']} ({result['file_size']} bytes)"
        )

        return {
            "success": True,
            "message": f"Document exported to {format.upper()} successfully",
            **result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error downloading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
