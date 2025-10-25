"""
Document generation API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from typing import Optional, List
import os
from datetime import datetime
from pathlib import Path

from ..models.document_generation_models import (
    QuoteRequest,
    ContractRequest,
    AppendixRequest,
    DocumentResponse,
    TemplateListResponse,
    DocumentTemplate,
    AITemplateRequest,
    AITemplateResponse,
)
from ..services.document_generation_service import DocumentGenerationService
from ..middleware.firebase_auth import get_current_user_optional

router = APIRouter(prefix="/api/documents", tags=["document-generation"])

# Initialize service
doc_service = DocumentGenerationService()


@router.post("/quotes", response_model=DocumentResponse)
async def create_quote(
    request: QuoteRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Tạo báo giá
    Create quote document
    """
    try:
        user_id = current_user.get("user_id") if current_user else None
        result = await doc_service.create_quote(request, user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo báo giá: {str(e)}")


@router.post("/contracts", response_model=DocumentResponse)
async def create_contract(
    request: ContractRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Tạo hợp đồng
    Create contract document
    """
    try:
        user_id = current_user.get("user_id") if current_user else None
        result = await doc_service.create_contract(request, user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo hợp đồng: {str(e)}")


@router.post("/appendices", response_model=DocumentResponse)
async def create_appendix(
    request: AppendixRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Tạo phụ lục hợp đồng
    Create contract appendix
    """
    try:
        user_id = current_user.get("user_id") if current_user else None
        result = await doc_service.create_appendix(request, user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo phụ lục: {str(e)}")


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(doc_type: Optional[str] = None):
    """
    Danh sách templates có sẵn
    List available templates
    """
    try:
        templates = await doc_service.list_templates(doc_type)
        return TemplateListResponse(templates=templates, total=len(templates))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Lỗi lấy danh sách template: {str(e)}"
        )


@router.get("/status/{request_id}")
async def get_document_status(request_id: str):
    """
    Kiểm tra trạng thái tạo tài liệu
    Check document generation status
    """
    try:
        doc_request = await doc_service.get_document_status(request_id)
        if not doc_request:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu")

        return {
            "request_id": request_id,
            "status": doc_request.status,
            "type": doc_request.type,
            "created_at": doc_request.created_at,
            "updated_at": doc_request.updated_at,
            "file_url": doc_request.file_url,
            "expires_at": doc_request.expires_at,
            "error_message": doc_request.error_message,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Lỗi kiểm tra trạng thái: {str(e)}"
        )


@router.get("/download/{request_id}")
async def download_document(request_id: str):
    """
    Tải xuống tài liệu đã tạo
    Download generated document
    """
    try:
        file_path = await doc_service.get_file_path(request_id)
        if not file_path:
            raise HTTPException(
                status_code=404, detail="File không tồn tại hoặc đã hết hạn"
            )

        # Get document info for filename
        doc_request = await doc_service.get_document_status(request_id)
        if not doc_request:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy thông tin tài liệu"
            )

        # Create appropriate filename
        type_names = {"quote": "BaoGia", "contract": "HopDong", "appendix": "PhuLuc"}
        type_name = type_names.get(doc_request.type, "TaiLieu")
        filename = f"{type_name}_{doc_request.created_at.strftime('%Y%m%d')}.docx"

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải file: {str(e)}")


@router.post("/templates")
async def create_template(
    template_data: DocumentTemplate,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Tạo template mới (Admin only)
    Create new template (Admin only)
    """
    try:
        # Check admin permission
        if not current_user or not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=403, detail="Chỉ admin mới có thể tạo template"
            )

        # Save template to database
        from ..config.database import get_database

        db = get_database()

        result = await db.user_upload_files.insert_one(
            template_data.dict(by_alias=True)
        )
        template_data.id = result.inserted_id

        return {
            "message": "Template đã được tạo thành công",
            "template_id": str(template_data.id),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo template: {str(e)}")


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    template_data: DocumentTemplate,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Cập nhật template (Admin only)
    Update template (Admin only)
    """
    try:
        # Check admin permission
        if not current_user or not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=403, detail="Chỉ admin mới có thể cập nhật template"
            )

        from ..config.database import get_database
        from bson import ObjectId

        db = get_database()

        # Update template
        template_dict = template_data.dict(by_alias=True, exclude={"id"})
        template_dict["updated_at"] = datetime.utcnow()

        result = await db.user_upload_files.update_one(
            {"_id": ObjectId(template_id)}, {"$set": template_dict}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Template không tồn tại")

        return {"message": "Template đã được cập nhật thành công"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật template: {str(e)}")


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str, current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Xóa template (Admin only)
    Delete template (Admin only)
    """
    try:
        # Check admin permission
        if not current_user or not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=403, detail="Chỉ admin mới có thể xóa template"
            )

        from ..config.database import get_database
        from bson import ObjectId

        db = get_database()

        # Soft delete - mark as inactive
        result = await db.user_upload_files.update_one(
            {"_id": ObjectId(template_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Template không tồn tại")

        return {"message": "Template đã được xóa thành công"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa template: {str(e)}")


@router.post("/templates/upload/{template_id}")
async def upload_template_file(
    template_id: str,
    file: UploadFile = File(...),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Upload file template Word (Admin only)
    Upload Word template file (Admin only)
    """
    try:
        # Check admin permission
        if not current_user or not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=403, detail="Chỉ admin mới có thể upload template"
            )

        # Validate file type
        if not file.filename.endswith((".docx", ".doc")):
            raise HTTPException(
                status_code=400, detail="Chỉ chấp nhận file Word (.docx, .doc)"
            )

        # Save file
        template_dir = Path("templates/documents")
        template_dir.mkdir(exist_ok=True)

        file_path = template_dir / f"{template_id}_{file.filename}"

        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Update template with file path
        from ..config.database import get_database
        from bson import ObjectId

        db = get_database()

        await db.user_upload_files.update_one(
            {"_id": ObjectId(template_id)},
            {"$set": {"file_path": str(file_path), "updated_at": datetime.utcnow()}},
        )

        return {
            "message": "File template đã được upload thành công",
            "file_path": str(file_path),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi upload file: {str(e)}")


# Health check endpoint
@router.get("/health")
async def health_check():
    """
    Health check cho document generation service
    Health check for document generation service
    """
    try:
        # Test database connection
        from ..config.database import get_database

        db = get_database()
        await db.command("ping")

        # Test template directory
        template_dir = Path("templates/documents")
        template_dir.mkdir(exist_ok=True)

        # Test output directory
        output_dir = Path("generated_documents")
        output_dir.mkdir(exist_ok=True)

        return {
            "status": "healthy",
            "service": "document-generation",
            "database": "connected",
            "directories": "ready",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")


@router.post("/ai-template/generate", response_model=AITemplateResponse)
async def generate_ai_template(
    request: AITemplateRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Generate template structure using AI
    Tạo cấu trúc template bằng AI với lựa chọn model:
    - deepseek (default)
    - qwen-2.5b-instruct
    - gemini-2.5-pro
    """
    try:
        # Convert to dict for processing
        request_dict = request.dict()
        result = await doc_service.generate_ai_template(request_dict)
        return AITemplateResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"AI template generation failed: {str(e)}"
        )


@router.get("/ai-models")
async def get_available_ai_models():
    """
    Get list of available AI models for template generation
    Lấy danh sách các AI models có thể sử dụng
    """
    return {
        "models": [
            {
                "id": "deepseek",
                "name": "DeepSeek Chat",
                "description": "DeepSeek's advanced reasoning model (default)",
                "provider": "DeepSeek",
                "default": True,
            },
            {
                "id": "qwen-2.5b-instruct",
                "name": "Qwen 2.5B Instruct",
                "description": "Alibaba's Qwen 2.5B instruction-following model",
                "provider": "Alibaba Cloud",
                "default": False,
            },
            {
                "id": "gemini-2.5-pro",
                "name": "Gemini 2.5 Pro",
                "description": "Google's latest and most powerful Gemini model",
                "provider": "Google",
                "default": False,
            },
        ],
        "default_model": "deepseek",
    }


@router.post("/ai-documents/create")
async def create_ai_document(
    request: dict,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Create document using AI-generated template
    """
    try:
        # First generate AI template if needed
        if request.get("template_option") == "create_new":
            ai_template = await doc_service.generate_ai_template(request)
            request["ai_template"] = ai_template

        # Create document based on type
        doc_type = request.get("document_type", "quote")
        user_id = current_user.get("user_id") if current_user else None

        if doc_type == "quote":
            # Convert to QuoteRequest format
            quote_request = _convert_to_quote_request(request)
            result = await doc_service.create_quote(quote_request, user_id)
        elif doc_type == "contract":
            # Convert to ContractRequest format
            contract_request = _convert_to_contract_request(request)
            result = await doc_service.create_contract(contract_request, user_id)
        elif doc_type == "appendix":
            # Convert to AppendixRequest format
            appendix_request = _convert_to_appendix_request(request)
            result = await doc_service.create_appendix(appendix_request, user_id)
        else:
            raise ValueError(f"Unsupported document type: {doc_type}")

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"AI document creation failed: {str(e)}"
        )


def _convert_to_quote_request(request: dict) -> "QuoteRequest":
    """Convert AI request to QuoteRequest"""
    from ..models.document_generation_models import (
        QuoteRequest,
        CompanyInfo,
        CustomerInfo,
        ProductInfo,
        PaymentTerms,
    )

    return QuoteRequest(
        template_id=request.get("base_template_id", "default"),
        company_info=CompanyInfo(**(request.get("company_info") or {})),
        customer_info=CustomerInfo(**(request.get("customer_info") or {})),
        products=[ProductInfo(**p) for p in request.get("products", [])],
        total_amount=request.get("total_amount", 0),
        total_quantity=request.get("total_quantity", 0),
        payment_terms=PaymentTerms(**(request.get("payment_terms") or {})),
        additional_terms=request.get("additional_terms"),
        vat_rate=request.get("vat_rate", 10.0),
        notes=request.get("notes"),
    )


def _convert_to_contract_request(request: dict) -> "ContractRequest":
    """Convert AI request to ContractRequest"""
    from ..models.document_generation_models import (
        ContractRequest,
        CompanyInfo,
        CustomerInfo,
        ProductInfo,
        PaymentTerms,
    )

    return ContractRequest(
        template_id=request.get("base_template_id", "default"),
        company_info=CompanyInfo(**(request.get("company_info") or {})),
        customer_info=CustomerInfo(**(request.get("customer_info") or {})),
        products=[ProductInfo(**p) for p in request.get("products", [])],
        payment_terms=PaymentTerms(**(request.get("payment_terms") or {})),
        additional_terms=request.get("additional_terms"),
        contract_duration=request.get("contract_duration"),
        effective_date=request.get("effective_date"),
    )


def _convert_to_appendix_request(request: dict) -> "AppendixRequest":
    """Convert AI request to AppendixRequest"""
    from ..models.document_generation_models import (
        AppendixRequest,
        CompanyInfo,
        CustomerInfo,
        ProductInfo,
    )

    return AppendixRequest(
        template_id=request.get("base_template_id", "default"),
        parent_contract_id=request.get("parent_contract_id"),
        company_info=CompanyInfo(**(request.get("company_info") or {})),
        customer_info=CustomerInfo(**(request.get("customer_info") or {})),
        products=[ProductInfo(**p) for p in request.get("products", [])],
        changes_description=request.get("changes_description", ""),
        additional_terms=request.get("additional_terms"),
    )
