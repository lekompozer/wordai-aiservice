"""
Documents History API Routes
Handles user document history and recent activities
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from src.config.firebase_config import firebase_config
from src.middleware.auth import verify_firebase_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents History"])


class DocumentHistoryItem(BaseModel):
    """Document history item model"""

    id: str
    title: str
    type: str  # "chat", "document", "template", "quote"
    created_at: datetime
    updated_at: datetime
    status: str  # "completed", "processing", "failed"
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    preview_text: Optional[str] = None


class DocumentHistoryResponse(BaseModel):
    """Document history response model"""

    success: bool
    documents: List[DocumentHistoryItem]
    total_count: int
    page: int
    page_size: int
    message: str


@router.get("/history", response_model=DocumentHistoryResponse)
async def get_documents_history(
    page: int = 1,
    page_size: int = 20,
    document_type: Optional[str] = None,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get document history for the authenticated user
    """
    try:
        user_id = user_data.get("uid")
        user_email = user_data.get("email", user_id)

        # Mock data for now - in a real app, you'd fetch from database
        mock_documents = [
            DocumentHistoryItem(
                id="doc_001",
                title="Báo cáo phân tích thị trường bất động sản",
                type="document",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status="completed",
                file_url="https://example.com/docs/doc_001.pdf",
                file_size=2048576,
                preview_text="Báo cáo phân tích tình hình thị trường bất động sản quý 3/2024...",
            ),
            DocumentHistoryItem(
                id="chat_002",
                title="Tư vấn vay mua nhà",
                type="chat",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status="completed",
                preview_text="Cuộc trò chuyện về tư vấn vay mua nhà với lãi suất ưu đãi...",
            ),
            DocumentHistoryItem(
                id="quote_003",
                title="Báo giá dịch vụ tư vấn đầu tư",
                type="quote",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status="completed",
                file_url="https://example.com/quotes/quote_003.pdf",
                file_size=1024768,
                preview_text="Báo giá chi tiết cho dịch vụ tư vấn đầu tư bất động sản...",
            ),
        ]

        # Filter by type if specified
        if document_type:
            mock_documents = [
                doc for doc in mock_documents if doc.type == document_type
            ]

        # Pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_docs = mock_documents[start_idx:end_idx]

        logger.info(
            f"✅ Retrieved {len(paginated_docs)} documents for user: {user_email}"
        )

        return DocumentHistoryResponse(
            success=True,
            documents=paginated_docs,
            total_count=len(mock_documents),
            page=page,
            page_size=page_size,
            message="Document history retrieved successfully",
        )

    except Exception as e:
        logger.error(f"❌ Failed to get document history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document history",
        )


@router.get("/history/{document_id}")
async def get_document_detail(
    document_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Get detailed information about a specific document
    """
    try:
        user_id = user_data.get("uid")
        user_email = user_data.get("email", user_id)

        # Mock data for now
        mock_document = DocumentHistoryItem(
            id=document_id,
            title=f"Document {document_id}",
            type="document",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            status="completed",
            file_url=f"https://example.com/docs/{document_id}.pdf",
            file_size=2048576,
            preview_text="Document content preview...",
        )

        logger.info(f"✅ Retrieved document {document_id} for user: {user_email}")

        return {
            "success": True,
            "document": mock_document,
            "message": "Document detail retrieved successfully",
        }

    except Exception as e:
        logger.error(f"❌ Failed to get document detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document detail",
        )


@router.delete("/history/{document_id}")
async def delete_document(
    document_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Delete a document from user's history
    """
    try:
        user_id = user_data.get("uid")
        user_email = user_data.get("email", user_id)

        # In a real app, you'd delete from database here
        logger.info(f"✅ Deleted document {document_id} for user: {user_email}")

        return {"success": True, "message": "Document deleted successfully"}

    except Exception as e:
        logger.error(f"❌ Failed to delete document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        )
