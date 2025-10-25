"""
Admin Template Management Routes - System Templates Only
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config.database import get_async_database
from src.middleware.admin_auth import admin_required
from src.services.enhanced_template_upload_service import EnhancedTemplateUploadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/templates")


@router.post("/system/upload", tags=["Admin - System Templates"])
async def upload_system_template(
    file: UploadFile = File(...),
    template_name: str = Form(...),
    description: str = Form(""),
    category: str = Form("system"),
    admin_user: Dict[str, Any] = Depends(admin_required),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    Upload template cho toàn hệ thống (System Template)
    - Chỉ admin mới có quyền upload
    - Template sẽ hiển thị cho tất cả users
    - user_id = "system", is_public = true
    """
    try:
        # Validate file type
        if not file.filename.endswith(".docx"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Chỉ hỗ trợ file .docx"
            )

        # Read file content
        file_content = await file.read()

        # Initialize upload service
        upload_service = EnhancedTemplateUploadService()

        # Process template upload với system user
        result = await upload_service.process_template_upload(
            file_content=file_content,
            filename=file.filename,
            template_name=template_name,
            description=description,
            category=category,
            user_id="system",  # ✅ System template
            is_system_template=True,  # ✅ Flag để identify system template
        )

        logger.info(
            f"✅ Admin {admin_user['uid']} uploaded system template: {template_name}"
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "message": f"System template '{template_name}' uploaded successfully",
                "template_id": result["template_id"],
                "template_name": template_name,
                "category": category,
                "is_system_template": True,
                "uploaded_by_admin": admin_user["uid"],
                "urls": result.get("urls", {}),
                "analysis_summary": result.get("analysis_summary", {}),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading system template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi upload system template: {str(e)}",
        )


@router.get("/system", tags=["Admin - System Templates"])
async def list_system_templates(
    category: Optional[str] = None,
    admin_user: Dict[str, Any] = Depends(admin_required),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    List tất cả system templates (chỉ admin)
    """
    try:
        # Build query for system templates only
        query = {
            "user_id": {"$in": [None, "system"]},
            "is_public": True,
            "is_active": True,
        }

        if category:
            query["category"] = category

        # Get system templates
        cursor = db.document_templates.find(query).sort("created_at", -1)
        templates = await cursor.to_list(length=None)

        # Format response
        result = []
        for template in templates:
            result.append(
                {
                    "template_id": str(template["_id"]),
                    "name": template["name"],
                    "description": template.get("description", ""),
                    "category": template.get("category", "system"),
                    "type": template.get("type", "quote"),
                    "is_active": template.get("is_active", True),
                    "is_public": template.get("is_public", True),
                    "user_id": template.get("user_id", "system"),
                    "created_at": template.get("created_at"),
                    "usage_count": template.get("usage_count", 0),
                }
            )

        return {
            "success": True,
            "message": f"Found {len(result)} system templates",
            "templates": result,
            "total": len(result),
            "admin_user": admin_user["uid"],
        }

    except Exception as e:
        logger.error(f"❌ Error listing system templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy danh sách system templates: {str(e)}",
        )


@router.delete("/system/{template_id}", tags=["Admin - System Templates"])
async def delete_system_template(
    template_id: str,
    admin_user: Dict[str, Any] = Depends(admin_required),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    Xóa system template (chỉ admin)
    """
    try:
        # Verify it's a system template
        template = await db.document_templates.find_one(
            {
                "_id": template_id,
                "user_id": {"$in": [None, "system"]},
                "is_public": True,
            }
        )

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="System template không tìm thấy",
            )

        # Soft delete (set is_active = false)
        await db.document_templates.update_one(
            {"_id": template_id},
            {"$set": {"is_active": False, "deleted_by_admin": admin_user["uid"]}},
        )

        logger.info(
            f"✅ Admin {admin_user['uid']} deleted system template: {template_id}"
        )

        return {
            "success": True,
            "message": f"System template '{template['name']}' deleted successfully",
            "template_id": template_id,
            "deleted_by_admin": admin_user["uid"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting system template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xóa system template: {str(e)}",
        )
