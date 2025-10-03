"""
Document Editor API Routes
API endpoints for document management with auto-save functionality
Using asyncio.to_thread to wrap synchronous PyMongo calls
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
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


@router.get("/file/{file_id}", response_model=DocumentResponse)
async def get_document_by_file(
    file_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Lấy hoặc tạo document từ file_id

    - **Nếu document đã tồn tại**: Trả về HTML từ MongoDB (fast!)
    - **Nếu document chưa tồn tại**: Download từ R2, parse, tạo mới

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
            return DocumentResponse(
                document_id=document["document_id"],
                title=document["title"],
                content_html=document["content_html"],
                version=document["version"],
                last_saved_at=document["last_saved_at"],
                file_size_bytes=document["file_size_bytes"],
                auto_save_count=document["auto_save_count"],
                manual_save_count=document["manual_save_count"],
            )

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

        # Download and parse file from R2
        text_content, temp_file_path = (
            await FileDownloadService.download_and_parse_file(
                file_url=file_info["file_url"],
                file_type=file_info["file_type"],
                user_id=user_id,
                provider=None,  # Parse to text for all files
            )
        )

        if not text_content:
            raise HTTPException(status_code=500, detail="Failed to parse file content")

        # Convert text to HTML (basic conversion with line breaks)
        # Frontend Tiptap editor will enhance this
        content_html = text_content.replace("\n", "<br>")
        content_text = text_content

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
        )

        logger.info(f"✅ Created new document {new_doc_id} for file {file_id}")

        # Get the newly created document
        document = await asyncio.to_thread(
            doc_manager.get_document, new_doc_id, user_id
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
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting document by file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentResponse)
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
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{document_id}")
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
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Lấy danh sách documents của user
    Sắp xếp theo last_opened_at (documents mở gần nhất sẽ lên đầu)
    """
    user_id = user_data.get("uid")
    doc_manager = get_document_manager()

    try:
        documents = await asyncio.to_thread(
            doc_manager.list_user_documents, user_id=user_id, limit=limit, offset=offset
        )

        return [
            DocumentListItem(
                document_id=doc["document_id"],
                title=doc["title"],
                last_saved_at=doc["last_saved_at"],
                last_opened_at=doc.get("last_opened_at"),
                version=doc["version"],
                file_size_bytes=doc["file_size_bytes"],
            )
            for doc in documents
        ]

    except Exception as e:
        logger.error(f"❌ Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
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
