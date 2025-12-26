"""
Slide Outline Management API
CRUD operations for slide outlines and version management
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from src.services.document_manager import DocumentManager
from src.services.online_test_utils import get_mongodb_service
from src.middleware.firebase_auth import get_current_user

logger = logging.getLogger("chatbot")

router = APIRouter()


# ============ REQUEST/RESPONSE MODELS ============


class OutlineSlideItem(BaseModel):
    """Single slide outline item"""

    slide_index: int
    slide_type: str = Field(..., description="title|agenda|content|thankyou")
    title: str
    subtitle: Optional[str] = None
    bullets: Optional[List[str]] = None
    notes: Optional[str] = None
    image_url: Optional[str] = None
    keywords: Optional[List[str]] = None


class UpdateOutlineRequest(BaseModel):
    """Request to update full outline"""

    document_id: str
    slides_outline: List[OutlineSlideItem]
    change_description: Optional[str] = "Manual outline update"


class AddSlideRequest(BaseModel):
    """Request to add a new slide to outline"""

    document_id: str
    insert_after_index: int
    new_slide: OutlineSlideItem


class DeleteSlideRequest(BaseModel):
    """Request to delete a slide from outline"""

    document_id: str
    slide_index: int
    reason: Optional[str] = None


class SwitchVersionRequest(BaseModel):
    """Request to switch to a different version"""

    document_id: str
    target_version: int


# ============ OUTLINE MANAGEMENT ENDPOINTS ============


@router.get("/slides/outline")
async def get_outline(
    document_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get current outline for a slide document"""
    user_id = current_user["uid"]

    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    doc = doc_manager.get_document(document_id, user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    slides_outline = doc.get("slides_outline", [])

    logger.info(f"📋 Retrieved outline for {document_id}: {len(slides_outline)} slides")

    return {
        "success": True,
        "document_id": document_id,
        "version": doc.get("version", 1),
        "slide_count": len(slides_outline),
        "slides_outline": slides_outline,
    }


@router.put("/slides/outline")
async def update_outline(
    request: UpdateOutlineRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update outline for a slide document"""

    user_id = current_user["uid"]
    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    # Get current document to preserve content_html
    doc = doc_manager.get_document(request.document_id, user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Save current version to history BEFORE updating
    try:
        new_version = doc_manager.save_version_snapshot(
            document_id=request.document_id,
            user_id=user_id,
            description=f"Before outline edit: {request.change_description}",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Update outline (keep existing content_html)
    success = doc_manager.update_document(
        document_id=request.document_id,
        user_id=user_id,
        content_html=doc.get("content_html", ""),
        slides_outline=[s.dict() for s in request.slides_outline],
        is_auto_save=False,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update outline",
        )

    logger.info(
        f"✏️ Updated outline for {request.document_id}: "
        f"{len(request.slides_outline)} slides (version {new_version})"
    )

    return {
        "success": True,
        "message": "Outline updated successfully",
        "document_id": request.document_id,
        "updated_slides": len(request.slides_outline),
        "new_version": new_version,
        "can_regenerate": True,
    }


@router.post("/slides/outline/add")
async def add_slide_to_outline(
    request: AddSlideRequest, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Add a new slide to outline"""

    user_id = current_user["uid"]
    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    # Get current outline
    doc = doc_manager.get_document(request.document_id, user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    current_outline = doc.get("slides_outline", [])

    # Insert new slide
    insert_position = request.insert_after_index + 1
    new_slide_dict = request.new_slide.dict()
    new_slide_dict["slide_index"] = insert_position

    # Reindex slides after insertion point
    updated_outline = []
    for slide in current_outline:
        if slide["slide_index"] <= request.insert_after_index:
            updated_outline.append(slide)
        else:
            slide["slide_index"] += 1
            updated_outline.append(slide)

    updated_outline.insert(insert_position, new_slide_dict)

    # Save version snapshot
    doc_manager.save_version_snapshot(
        document_id=request.document_id,
        user_id=user_id,
        description=f"Before adding slide at position {insert_position}",
    )

    # Update document (keep existing content_html)
    doc_manager.update_document(
        document_id=request.document_id,
        user_id=user_id,
        content_html=doc.get("content_html", ""),
        slides_outline=updated_outline,
        is_auto_save=False,
    )

    logger.info(
        f"➕ Added slide at index {insert_position} to {request.document_id} "
        f"(total: {len(updated_outline)})"
    )

    return {
        "success": True,
        "message": "Slide added successfully",
        "new_slide_index": insert_position,
        "total_slides": len(updated_outline),
    }


@router.delete("/slides/outline/slide")
async def delete_slide_from_outline(
    request: DeleteSlideRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a slide from outline"""

    user_id = current_user["uid"]
    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    # Get current outline
    doc = doc_manager.get_document(request.document_id, user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    current_outline = doc.get("slides_outline", [])

    # Remove slide and reindex
    updated_outline = []
    for slide in current_outline:
        if slide["slide_index"] < request.slide_index:
            updated_outline.append(slide)
        elif slide["slide_index"] > request.slide_index:
            slide["slide_index"] -= 1
            updated_outline.append(slide)
        # Skip slide_index == request.slide_index (delete it)

    # Save version snapshot
    doc_manager.save_version_snapshot(
        document_id=request.document_id,
        user_id=user_id,
        description=f"Before deleting slide {request.slide_index}: {request.reason or 'No reason'}",
    )

    # Update document (keep existing content_html)
    doc_manager.update_document(
        document_id=request.document_id,
        user_id=user_id,
        content_html=doc.get("content_html", ""),
        slides_outline=updated_outline,
        is_auto_save=False,
    )

    logger.info(
        f"🗑️ Deleted slide {request.slide_index} from {request.document_id} "
        f"(remaining: {len(updated_outline)})"
    )

    return {
        "success": True,
        "message": f"Slide {request.slide_index} deleted from outline",
        "remaining_slides": len(updated_outline),
    }


# ============ VERSION MANAGEMENT ENDPOINTS ============


@router.get("/slides/versions")
async def get_version_history(
    document_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get version history for a document"""

    user_id = current_user["uid"]
    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    doc = doc_manager.get_document(document_id, user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    history = doc_manager.get_version_history(document_id, user_id)
    current_version = doc.get("version", 1)

    logger.info(
        f"📜 Retrieved version history for {document_id}: "
        f"{len(history)} versions (current: v{current_version})"
    )

    return {
        "success": True,
        "document_id": document_id,
        "current_version": current_version,
        "total_versions": len(history),
        "versions": history,
    }


@router.post("/slides/versions/switch")
async def switch_version(
    request: SwitchVersionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Switch to a different version"""

    user_id = current_user["uid"]
    mongo = get_mongodb_service()
    doc_manager = DocumentManager(mongo.db)

    try:
        doc_manager.restore_version(
            document_id=request.document_id,
            user_id=user_id,
            target_version=request.target_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Get updated document
    doc = doc_manager.get_document(request.document_id, user_id)

    logger.info(f"⏮️ Switched {request.document_id} to version {request.target_version}")

    return {
        "success": True,
        "message": f"Switched to version {request.target_version}",
        "document_id": request.document_id,
        "current_version": doc.get("version"),
        "slide_count": len(doc.get("slides_outline", [])),
        "switched_at": datetime.utcnow().isoformat(),
    }
