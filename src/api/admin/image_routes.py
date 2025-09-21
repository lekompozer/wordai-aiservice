"""
Admin API routes for managing Images and Folders.
Based on Backend-AI-Data-Document.md specification for image management.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field

from src.services.admin_service import get_admin_service, AdminService
from src.utils.logger import setup_logger
from src.middleware.auth import verify_internal_api_key

# Initialize router and logger
router = APIRouter(tags=["Admin - Images"])
logger = setup_logger(__name__)

# ===== REQUEST & RESPONSE MODELS =====


class ImageUploadRequest(BaseModel):
    r2_url: str = Field(..., description="Public R2 URL of the uploaded image")
    folder_name: Optional[str] = Field(None, description="Folder name for organization")
    ai_instruction: Optional[str] = Field(
        None, description="AI processing instructions for the image"
    )
    metadata: Dict[str, Any] = Field(..., description="Image metadata")


class ImageUpdateRequest(BaseModel):
    ai_instruction: Optional[str] = Field(None, description="Updated AI instructions")
    description: Optional[str] = Field(None, description="Updated description")
    alt_text: Optional[str] = Field(None, description="Updated alt text")
    status: Optional[str] = Field(None, description="Updated status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class FolderCreateRequest(BaseModel):
    folder_name: str = Field(..., description="Name of the folder")
    description: Optional[str] = Field(None, description="Folder description")
    parent_folder_id: Optional[str] = Field(
        None, description="Parent folder ID for nested structure"
    )


class FolderUpdateRequest(BaseModel):
    folder_name: Optional[str] = Field(None, description="Updated folder name")
    description: Optional[str] = Field(None, description="Updated description")
    parent_folder_id: Optional[str] = Field(None, description="Updated parent folder")


# ===== IMAGE MANAGEMENT ENDPOINTS =====


@router.post(
    "/companies/{company_id}/images/upload",
    dependencies=[Depends(verify_internal_api_key)],
)
async def upload_image(
    company_id: str,
    request: ImageUploadRequest,
    background_tasks: BackgroundTasks,
    admin_service: AdminService = Depends(get_admin_service),
):
    """
    Upload images with AI instructions for processing.
    """
    try:
        logger.info(f"🖼️ Uploading image for company {company_id}")
        logger.info(f"   🔗 R2 URL: {request.r2_url}")
        logger.info(f"   📁 Folder: {request.folder_name}")
        logger.info(f"   🤖 AI Instructions: {request.ai_instruction}")

        # Add image metadata with processing instructions
        image_data = {
            "r2_url": request.r2_url,
            "folder_name": request.folder_name,
            "ai_instruction": request.ai_instruction,
            "content_type": "image",
            "status": "uploaded",
            "uploaded_at": datetime.now().isoformat(),
            **request.metadata,
        }

        # If AI instructions provided, schedule background processing
        if request.ai_instruction:
            background_tasks.add_task(
                process_image_with_ai, company_id=company_id, image_data=image_data
            )
            image_data["status"] = "processing"

        result = await admin_service.add_image(company_id, image_data)

        logger.info(f"✅ Image uploaded for company {company_id}")
        return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"❌ Image upload failed for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/companies/{company_id}/images", dependencies=[Depends(verify_internal_api_key)]
)
async def get_images(
    company_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    folder_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    admin_service: AdminService = Depends(get_admin_service),
):
    """
    Get list of images with filtering options.
    """
    try:
        logger.info(f"📋 Fetching images for company {company_id}")

        offset = (page - 1) * limit

        # Apply filters based on query parameters
        filters = {}
        if folder_id:
            filters["folder_id"] = folder_id
        if search:
            filters["search"] = search
        if status:
            filters["status"] = status

        images = await admin_service.get_company_images(
            company_id, limit=limit, offset=offset, filters=filters
        )

        return {
            "success": True,
            "data": images,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": len(images),  # This should be actual count from service
            },
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch images for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/companies/{company_id}/images/{image_id}",
    dependencies=[Depends(verify_internal_api_key)],
)
async def update_image(
    company_id: str,
    image_id: str,
    request: ImageUpdateRequest,
    background_tasks: BackgroundTasks,
    admin_service: AdminService = Depends(get_admin_service),
):
    """
    Update image information and AI instructions.
    """
    try:
        logger.info(f"✏️ Updating image {image_id} for company {company_id}")

        update_data = {}
        if request.ai_instruction is not None:
            update_data["ai_instruction"] = request.ai_instruction
        if request.description is not None:
            update_data["description"] = request.description
        if request.alt_text is not None:
            update_data["alt_text"] = request.alt_text
        if request.status is not None:
            update_data["status"] = request.status
        if request.metadata:
            update_data["metadata"] = request.metadata

        update_data["updated_at"] = datetime.now().isoformat()

        # If AI instructions changed, schedule reprocessing
        if request.ai_instruction and request.ai_instruction.strip():
            background_tasks.add_task(
                process_image_with_ai,
                company_id=company_id,
                image_data={
                    "image_id": image_id,
                    "ai_instruction": request.ai_instruction,
                },
            )
            update_data["status"] = "reprocessing"

        result = await admin_service.update_image(company_id, image_id, update_data)

        logger.info(f"✅ Image {image_id} updated for company {company_id}")
        return {"success": True, "data": result}

    except Exception as e:
        logger.error(
            f"❌ Failed to update image {image_id} for company {company_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/companies/{company_id}/images/{image_id}",
    dependencies=[Depends(verify_internal_api_key)],
)
async def delete_image(
    company_id: str,
    image_id: str,
    admin_service: AdminService = Depends(get_admin_service),
):
    """
    Delete an image and its vectors from Qdrant.
    """
    try:
        logger.info(f"🗑️ Deleting image {image_id} for company {company_id}")

        await admin_service.delete_image(company_id, image_id)

        logger.info(f"✅ Image {image_id} deleted for company {company_id}")
        return {"success": True, "message": "Image deleted successfully"}

    except Exception as e:
        logger.error(
            f"❌ Failed to delete image {image_id} for company {company_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


# ===== FOLDER MANAGEMENT ENDPOINTS =====


@router.post(
    "/companies/{company_id}/images/folders",
    dependencies=[Depends(verify_internal_api_key)],
)
async def create_folder(
    company_id: str,
    request: FolderCreateRequest,
    admin_service: AdminService = Depends(get_admin_service),
):
    """
    Create a new image folder.
    """
    try:
        logger.info(
            f"📁 Creating folder '{request.folder_name}' for company {company_id}"
        )

        folder_data = {
            "folder_name": request.folder_name,
            "description": request.description,
            "parent_folder_id": request.parent_folder_id,
            "created_at": datetime.now().isoformat(),
            "content_type": "folder",
            "status": "active",
        }

        result = await admin_service.create_image_folder(company_id, folder_data)

        logger.info(
            f"✅ Folder '{request.folder_name}' created for company {company_id}"
        )
        return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"❌ Failed to create folder for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/companies/{company_id}/images/folders",
    dependencies=[Depends(verify_internal_api_key)],
)
async def get_folders(
    company_id: str, admin_service: AdminService = Depends(get_admin_service)
):
    """
    Get list of image folders.
    """
    try:
        logger.info(f"📂 Fetching folders for company {company_id}")

        folders = await admin_service.get_image_folders(company_id)

        return {"success": True, "data": folders}

    except Exception as e:
        logger.error(f"❌ Failed to fetch folders for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/companies/{company_id}/images/folders/{folder_id}",
    dependencies=[Depends(verify_internal_api_key)],
)
async def update_folder(
    company_id: str,
    folder_id: str,
    request: FolderUpdateRequest,
    admin_service: AdminService = Depends(get_admin_service),
):
    """
    Update folder information.
    """
    try:
        logger.info(f"✏️ Updating folder {folder_id} for company {company_id}")

        update_data = {}
        if request.folder_name is not None:
            update_data["folder_name"] = request.folder_name
        if request.description is not None:
            update_data["description"] = request.description
        if request.parent_folder_id is not None:
            update_data["parent_folder_id"] = request.parent_folder_id

        update_data["updated_at"] = datetime.now().isoformat()

        result = await admin_service.update_image_folder(
            company_id, folder_id, update_data
        )

        logger.info(f"✅ Folder {folder_id} updated for company {company_id}")
        return {"success": True, "data": result}

    except Exception as e:
        logger.error(
            f"❌ Failed to update folder {folder_id} for company {company_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/companies/{company_id}/images/folders/{folder_id}",
    dependencies=[Depends(verify_internal_api_key)],
)
async def delete_folder(
    company_id: str,
    folder_id: str,
    admin_service: AdminService = Depends(get_admin_service),
):
    """
    Delete folder and all contained images.
    """
    try:
        logger.info(
            f"🗑️ Deleting folder {folder_id} and all images for company {company_id}"
        )

        await admin_service.delete_image_folder(company_id, folder_id)

        logger.info(
            f"✅ Folder {folder_id} and all images deleted for company {company_id}"
        )
        return {
            "success": True,
            "message": "Folder and all images deleted successfully",
        }

    except Exception as e:
        logger.error(
            f"❌ Failed to delete folder {folder_id} for company {company_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


# ===== BACKGROUND TASKS =====


async def process_image_with_ai(company_id: str, image_data: Dict[str, Any]):
    """
    Background task to process images with AI instructions.
    """
    try:
        logger.info(f"🤖 Processing image with AI for company {company_id}")
        logger.info(f"   📝 Instructions: {image_data.get('ai_instruction', 'None')}")

        # Here you would integrate with AI vision services to:
        # 1. Process the image according to AI instructions
        # 2. Generate embeddings for the image
        # 3. Store results in Qdrant
        # 4. Update image status

        admin_service = get_admin_service()

        # Simulate AI processing
        processing_result = {
            "ai_analysis": "Processed with AI instructions",
            "embedding_created": True,
            "processed_at": datetime.now().isoformat(),
            "status": "completed",
        }

        # Update image with processing results
        image_id = image_data.get("image_id", "unknown")
        if image_id != "unknown":
            await admin_service.update_image(company_id, image_id, processing_result)

        logger.info(f"✅ AI image processing completed for company {company_id}")

    except Exception as e:
        logger.error(f"❌ AI image processing failed for company {company_id}: {e}")
        # Update image status to failed
        try:
            admin_service = get_admin_service()
            image_id = image_data.get("image_id", "unknown")
            if image_id != "unknown":
                await admin_service.update_image(
                    company_id,
                    image_id,
                    {
                        "status": "failed",
                        "error": str(e),
                        "failed_at": datetime.now().isoformat(),
                    },
                )
        except:
            pass  # Avoid cascading errors
