"""
Document Editor API Routes
API endpoints for document management with auto-save functionality
Using asyncio.to_thread to wrap synchronous PyMongo calls
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
import logging
import asyncio

from src.models.document_editor_models import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListItem,
)
from src.services.document_manager import DocumentManager
from src.services.file_download_service import FileDownloadService
from src.services.user_manager import UserManager
from src.middleware.auth import verify_firebase_token
from src.database.db_manager import DBManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["Document Editor"])

# Global instances
_document_manager = None
_user_manager = None


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
    Lấy hoặc tạo document từ file_id

    - **Nếu document đã tồn tại**: Trả về HTML từ MongoDB (fast!)
    - **Nếu document chưa tồn tại**: Download từ R2, parse, tạo mới

    Query Parameters:
    - document_type: Optional - "doc", "slide", or "note" (default: "doc")
                     Frontend can specify preferred document type

    Flow:
    1. Check if document exists in MongoDB by file_id
    2. If exists → return from MongoDB
    3. If not exists:
       - Get file info from user_files
       - Download from R2
       - Parse to HTML
       - Create document in MongoDB
       - Return new document
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()
    user_manager = get_user_manager()

    try:
        # Step 1: Try to get existing document by file_id
        document = await asyncio.to_thread(
            doc_manager.get_document_by_file_id, file_id, user_id
        )

        if document:
            logger.info(f"📄 Loaded existing document for file {file_id} from MongoDB")
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
            )

            logger.warning(
                f"🔍 FRONTEND DEBUG: File {file_id} → Document ID is: {response.document_id}"
            )
            logger.warning(
                f"🔍 FRONTEND MUST SAVE TO: PUT /api/documents/{response.document_id}/"
            )
            logger.warning(f"🔍 NOT: PUT /api/documents/{file_id}/")

            return response

        # Step 2: Document doesn't exist - this is first time opening
        logger.info(f"📥 First time opening file {file_id}, creating new document...")

        # Get file info from user_files collection
        file_info = await asyncio.to_thread(
            user_manager.get_file_by_id, file_id, user_id
        )

        if not file_info:
            raise HTTPException(status_code=404, detail="File not found in user_files")

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
            raise HTTPException(status_code=500, detail="Failed to parse file content")

        # Convert text to HTML (basic conversion with line breaks)
        # Frontend Tiptap editor will enhance this
        content_html = text_content.replace("\n", "<br>")
        content_text = text_content

        # Determine document_type: Use frontend value or default to "doc"
        final_document_type = (
            document_type if document_type in ["doc", "slide", "note"] else "doc"
        )

        # Create new document in MongoDB
        new_doc_id = await asyncio.to_thread(
            doc_manager.create_document,
            user_id=user_id,
            file_id=file_id,
            title=file_info.get("file_name", "Untitled Document"),
            content_html=content_html,
            content_text=content_text,
            original_r2_url=file_info["file_url"],
            original_file_type=file_info["file_type"],
            source_type="file",  # This is a file-based document
            document_type=final_document_type,  # Frontend specified or default "doc"
        )

        logger.info(
            f"✅ Created new document {new_doc_id} for file {file_id} (type: {final_document_type})"
        )

        # Get the newly created document
        document = await asyncio.to_thread(
            doc_manager.get_document, new_doc_id, user_id
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
        )

        logger.warning(
            f"🔍 FRONTEND DEBUG: File {file_id} → Document ID is: {response.document_id}"
        )
        logger.warning(
            f"🔍 FRONTEND MUST SAVE TO: PUT /api/documents/{response.document_id}/"
        )
        logger.warning(f"🔍 NOT: PUT /api/documents/{file_id}/")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting document by file: {e}")
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
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        # Extract plain text from HTML if not provided
        content_text = update_data.content_text
        if not content_text:
            # Simple HTML stripping (you can use BeautifulSoup for better results)
            import re

            content_text = re.sub(r"<[^>]+>", "", update_data.content_html)

        success = await asyncio.to_thread(
            doc_manager.update_document,
            document_id=document_id,
            user_id=user_id,
            content_html=update_data.content_html,
            content_text=content_text,
            title=update_data.title,
            is_auto_save=update_data.is_auto_save,
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


@router.get("/", response_model=List[DocumentListItem])
async def list_documents(
    limit: int = 20,
    offset: int = 0,
    source_type: Optional[str] = None,
    document_type: Optional[str] = None,
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

    Examples:
    - GET /api/documents?source_type=created&document_type=doc
    - GET /api/documents?source_type=file
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        logger.info(
            f"📋 Listing documents for user {user_id[:8]}... "
            f"(source_type={source_type}, document_type={document_type}, limit={limit}, offset={offset})"
        )

        documents = await asyncio.to_thread(
            doc_manager.list_user_documents,
            user_id=user_id,
            limit=limit,
            offset=offset,
            source_type=source_type,
            document_type=document_type,
        )

        logger.info(f"✅ Found {len(documents)} documents for user {user_id[:8]}...")

        return [
            DocumentListItem(
                document_id=doc["document_id"],
                title=doc["title"],
                last_saved_at=doc["last_saved_at"],
                last_opened_at=doc.get("last_opened_at"),
                version=doc["version"],
                file_size_bytes=doc["file_size_bytes"],
                source_type=doc.get("source_type", "file"),
                document_type=doc.get("document_type"),
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

    **Example:**
    - GET `/api/documents/doc_abc123/download/pdf`
    - GET `/api/documents/doc_abc123/download/docx`

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
            account_id=APP_CONFIG.r2_account_id,
            access_key_id=APP_CONFIG.r2_access_key_id,
            secret_access_key=APP_CONFIG.r2_secret_access_key,
            bucket_name=APP_CONFIG.r2_bucket_name,
        )

        db = get_mongodb()
        export_service = DocumentExportService(r2_client=r2_client, db=db)

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
