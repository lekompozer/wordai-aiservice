"""
Extended Template Management API Routes
Bổ sung các endpoint để view, edit, và quản lý template metadata
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    status,
    Body,
)
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from src.config.database import get_async_database
from src.middleware.firebase_auth import get_current_user
from src.services.enhanced_template_upload_service import EnhancedTemplateUploadService
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/templates", tags=["Template Management"])


# ===== REQUEST/RESPONSE MODELS =====


class PlaceholderUpdateRequest(BaseModel):
    """Request để update placeholder metadata"""

    type: Optional[str] = None
    description: Optional[str] = None
    default_value: Optional[str] = None
    validation_rules: Optional[List[str]] = None
    section: Optional[str] = None
    auto_populate: Optional[bool] = None
    calculation_formula: Optional[str] = None
    formatting: Optional[Dict[str, Any]] = None


class SectionUpdateRequest(BaseModel):
    """Request để update section metadata"""

    name: Optional[str] = None
    description: Optional[str] = None
    placeholders: Optional[List[str]] = None
    order: Optional[int] = None
    is_repeatable: Optional[bool] = None
    required: Optional[bool] = None
    table_structure: Optional[Dict[str, Any]] = None


class TemplateMetadataUpdateRequest(BaseModel):
    """Request để update toàn bộ template metadata"""

    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    placeholders: Optional[Dict[str, PlaceholderUpdateRequest]] = None
    sections: Optional[List[SectionUpdateRequest]] = None
    business_logic: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None


class TemplatePreviewRequest(BaseModel):
    """Request để preview template với sample data"""

    sample_data: Dict[str, Any] = Field(
        ..., description="Sample data để fill placeholders"
    )


# ===== ENHANCED ENDPOINTS =====


@router.post("/upload", tags=["User Templates"])
async def upload_user_template(
    file: UploadFile = File(..., description="DOCX template file"),
    template_name: str = Form(..., description="Tên template"),
    description: str = Form(default="", description="Mô tả template"),
    category: str = Form(default="standard", description="Danh mục template"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    Upload DOCX template của USER (chỉ user đó thấy được)

    Workflow:
    1. Validate DOCX file
    2. Upload to R2 storage
    3. Convert to PDF
    4. Gemini Vision API analysis
    5. Save metadata to database với user_id và is_public=false
    """
    try:
        logger.info(
            f"📤 Enhanced template upload started by user: {current_user['uid']}"
        )

        # Initialize enhanced service
        upload_service = EnhancedTemplateUploadService()

        # Process upload với PDF workflow
        result = await upload_service.process_template_upload(
            file=file,
            template_name=template_name,
            description=description,
            category=category,
            user_id=current_user["uid"],
        )

        logger.info(f"✅ Enhanced template upload completed: {result['template_id']}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Enhanced template upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.get("/{template_id}/view")
async def view_template_content(
    template_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    View template content với placeholders và structure analysis
    """
    try:
        # Get template from database
        template = await db.document_templates.find_one({"_id": template_id})

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check user permission
        if template["user_id"] != current_user["uid"] and not template.get(
            "is_public", False
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        ai_analysis = template.get("ai_analysis", {})

        return {
            "template_id": template_id,
            "basic_info": {
                "name": template["name"],
                "description": template.get("description", ""),
                "category": template.get("category", ""),
                "created_at": template["created_at"],
                "updated_at": template["updated_at"],
            },
            "files": {
                "docx_url": template.get("files", {}).get("docx_url"),
                "pdf_url": template.get("files", {}).get("pdf_url"),
            },
            "document_structure": ai_analysis.get("document_structure", {}),
            "placeholders": ai_analysis.get("placeholders", {}),
            "sections": ai_analysis.get("sections", []),
            "business_logic": ai_analysis.get("business_logic", {}),
            "confidence_score": ai_analysis.get("confidence_score", 0.0),
            "validation": template.get("validation", {}),
            "usage_count": template.get("usage_count", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error viewing template content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}/metadata")
async def get_template_metadata(
    template_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    Get detailed template metadata cho editing
    """
    try:
        # Get template from database
        template = await db.document_templates.find_one({"_id": template_id})

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check user permission
        if template["user_id"] != current_user["uid"]:
            raise HTTPException(
                status_code=403, detail="Only template owner can view metadata"
            )

        ai_analysis = template.get("ai_analysis", {})

        return {
            "template_id": template_id,
            "editable_metadata": {
                "basic_info": {
                    "name": template["name"],
                    "description": template.get("description", ""),
                    "category": template.get("category", ""),
                    "is_public": template.get("is_public", False),
                },
                "placeholders": ai_analysis.get("placeholders", {}),
                "sections": ai_analysis.get("sections", []),
                "business_logic": ai_analysis.get("business_logic", {}),
                "document_structure": ai_analysis.get("document_structure", {}),
            },
            "read_only_info": {
                "confidence_score": ai_analysis.get("confidence_score", 0.0),
                "analysis_version": ai_analysis.get("analysis_version", "1.0"),
                "created_at": template["created_at"],
                "updated_at": template["updated_at"],
                "usage_count": template.get("usage_count", 0),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{template_id}/metadata")
async def update_template_metadata(
    template_id: str,
    update_request: TemplateMetadataUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    Update template metadata để customize template behavior
    """
    try:
        # Get template from database
        template = await db.document_templates.find_one({"_id": template_id})

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check ownership
        if template["user_id"] != current_user["uid"]:
            raise HTTPException(
                status_code=403, detail="Only template owner can edit metadata"
            )

        # Build update document
        update_doc = {"$set": {"updated_at": datetime.utcnow()}}

        # Update basic info
        if update_request.name:
            update_doc["$set"]["name"] = update_request.name
        if update_request.description is not None:
            update_doc["$set"]["description"] = update_request.description
        if update_request.category:
            update_doc["$set"]["category"] = update_request.category
        if update_request.is_public is not None:
            update_doc["$set"]["is_public"] = update_request.is_public

        # Update AI analysis metadata
        if update_request.placeholders:
            for (
                placeholder_name,
                placeholder_update,
            ) in update_request.placeholders.items():
                for field, value in placeholder_update.dict(exclude_none=True).items():
                    update_doc["$set"][
                        f"ai_analysis.placeholders.{placeholder_name}.{field}"
                    ] = value

        if update_request.sections:
            update_doc["$set"]["ai_analysis.sections"] = [
                section.dict(exclude_none=True) for section in update_request.sections
            ]

        if update_request.business_logic:
            update_doc["$set"][
                "ai_analysis.business_logic"
            ] = update_request.business_logic

        # Perform update
        result = await db.document_templates.update_one(
            {"_id": template_id}, update_doc
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500, detail="Failed to update template metadata"
            )

        # Get updated template
        updated_template = await db.document_templates.find_one({"_id": template_id})

        return {
            "success": True,
            "message": "Template metadata updated successfully",
            "template_id": template_id,
            "updated_fields": list(update_doc["$set"].keys()),
            "updated_metadata": {
                "name": updated_template["name"],
                "description": updated_template.get("description", ""),
                "category": updated_template.get("category", ""),
                "is_public": updated_template.get("is_public", False),
                "updated_at": updated_template["updated_at"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/preview")
async def preview_template_with_data(
    template_id: str,
    preview_request: TemplatePreviewRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    Preview template với sample data để test placeholder mapping
    """
    try:
        # Get template from database
        template = await db.document_templates.find_one({"_id": template_id})

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check user permission
        if template["user_id"] != current_user["uid"] and not template.get(
            "is_public", False
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        ai_analysis = template.get("ai_analysis", {})
        placeholders = ai_analysis.get("placeholders", {})

        # Map sample data to placeholders
        field_mapping = {}
        missing_fields = []

        for placeholder_name, placeholder_info in placeholders.items():
            # Try to find matching data in sample_data
            field_key = placeholder_name.replace("{{", "").replace("}}", "")

            if field_key in preview_request.sample_data:
                field_mapping[placeholder_name] = preview_request.sample_data[field_key]
            elif placeholder_info.get("auto_populate"):
                # Auto-generate values
                if placeholder_info["type"] == "date":
                    field_mapping[placeholder_name] = datetime.now().strftime(
                        "%d/%m/%Y"
                    )
                elif "number" in field_key.lower():
                    field_mapping[placeholder_name] = "001"
                else:
                    field_mapping[placeholder_name] = f"AUTO_{field_key.upper()}"
            elif placeholder_info.get("calculation_formula"):
                # Calculate based on formula (simplified)
                field_mapping[placeholder_name] = "CALCULATED_VALUE"
            else:
                field_mapping[placeholder_name] = placeholder_info.get(
                    "default_value", ""
                )
                if not field_mapping[placeholder_name]:
                    missing_fields.append(field_key)

        return {
            "template_id": template_id,
            "preview_data": {
                "field_mapping": field_mapping,
                "missing_fields": missing_fields,
                "auto_generated_fields": [
                    field
                    for field, info in placeholders.items()
                    if info.get("auto_populate")
                ],
                "calculated_fields": [
                    field
                    for field, info in placeholders.items()
                    if info.get("calculation_formula")
                ],
            },
            "placeholders_status": {
                "total_placeholders": len(placeholders),
                "filled_placeholders": len([f for f in field_mapping.values() if f]),
                "missing_placeholders": len(missing_fields),
                "completion_rate": (
                    (
                        len([f for f in field_mapping.values() if f])
                        / len(placeholders)
                        * 100
                    )
                    if placeholders
                    else 0
                ),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/duplicate")
async def duplicate_template(
    template_id: str,
    new_name: str = Body(..., description="Tên cho template mới"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    Duplicate template để tạo phiên bản mới cho customization
    """
    try:
        # Get original template
        original_template = await db.document_templates.find_one({"_id": template_id})

        if not original_template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check permission (allow duplication of public templates)
        if original_template["user_id"] != current_user[
            "uid"
        ] and not original_template.get("is_public", False):
            raise HTTPException(status_code=403, detail="Access denied")

        # Generate new template ID
        import uuid

        new_template_id = f"template_{uuid.uuid4().hex[:12]}"

        # Create duplicate template document
        duplicate_template = {
            "_id": new_template_id,
            "user_id": current_user["uid"],  # Assign to current user
            "name": new_name,
            "description": f"Duplicated from {original_template['name']}",
            "category": original_template.get("category", "standard"),
            "type": original_template.get("type", "quote"),
            "subtype": original_template.get("subtype", "business"),
            # Copy file information (would need to copy actual files in production)
            "files": {
                "docx_url": original_template.get("files", {}).get("docx_url"),
                "pdf_url": original_template.get("files", {}).get("pdf_url"),
                "thumbnail_urls": [],
            },
            # Copy AI analysis
            "ai_analysis": original_template.get("ai_analysis", {}),
            # New metadata
            "is_active": True,
            "is_public": False,  # Duplicates are private by default
            "usage_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            # Copy validation
            "validation": original_template.get("validation", {}),
            # Mark as duplicate
            "original_template_id": template_id,
        }

        # Insert duplicate
        result = await db.document_templates.insert_one(duplicate_template)

        return {
            "success": True,
            "message": "Template duplicated successfully",
            "original_template_id": template_id,
            "new_template_id": new_template_id,
            "new_name": new_name,
            "created_at": duplicate_template["created_at"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_user_templates(
    category: Optional[str] = None,
    include_public: bool = True,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    List user's templates với enhanced filtering và pagination
    """
    try:
        # Build query
        query = {
            "$or": [
                {"user_id": current_user["uid"]},
                (
                    {"is_public": True}
                    if include_public
                    else {"user_id": current_user["uid"]}
                ),
            ],
            "is_active": True,
        }

        if category:
            query["category"] = category

        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]

        # Count total documents
        total = await db.document_templates.count_documents(query)

        # Get templates with pagination
        skip = (page - 1) * limit
        cursor = (
            db.document_templates.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        templates = await cursor.to_list(length=limit)

        # Format response
        result = []
        for template in templates:
            ai_analysis = template.get("ai_analysis", {})
            result.append(
                {
                    "template_id": str(template["_id"]),
                    "name": template["name"],
                    "description": template.get("description", ""),
                    "category": template.get("category", ""),
                    "type": template.get("type", "quote"),
                    "is_public": template.get("is_public", False),
                    "is_owner": template["user_id"] == current_user["uid"],
                    "created_at": template["created_at"],
                    "updated_at": template["updated_at"],
                    "usage_count": template.get("usage_count", 0),
                    "ai_analysis_score": ai_analysis.get("confidence_score", 0.0),
                    "placeholders_count": len(ai_analysis.get("placeholders", {})),
                    "sections_count": len(ai_analysis.get("sections", [])),
                    "has_tables": ai_analysis.get("document_structure", {}).get(
                        "has_tables", False
                    ),
                    "files": {"pdf_preview": template.get("files", {}).get("pdf_url")},
                }
            )

        return {
            "success": True,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit,
            },
            "templates": result,
            "categories": ["standard", "premium", "business", "simple"],
            "filters": {
                "category": category,
                "search": search,
                "include_public": include_public,
            },
        }

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """
    Delete template (soft delete by marking as inactive)
    """
    try:
        # Get template
        template = await db.document_templates.find_one({"_id": template_id})

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Check ownership
        if template["user_id"] != current_user["uid"]:
            raise HTTPException(
                status_code=403, detail="Only template owner can delete"
            )

        # Check if template is being used
        usage_count = template.get("usage_count", 0)
        if usage_count > 0:
            # Soft delete to preserve quote generation history
            result = await db.document_templates.update_one(
                {"_id": template_id},
                {
                    "$set": {
                        "is_active": False,
                        "deleted_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            message = f"Template archived (was used {usage_count} times)"
        else:
            # Can safely mark as inactive
            result = await db.document_templates.update_one(
                {"_id": template_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
            )
            message = "Template deleted successfully"

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to delete template")

        return {
            "success": True,
            "message": message,
            "template_id": template_id,
            "was_used": usage_count > 0,
            "usage_count": usage_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        raise HTTPException(status_code=500, detail=str(e))
