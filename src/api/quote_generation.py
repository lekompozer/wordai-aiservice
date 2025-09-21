"""
API endpoints cho luồng xử lý quote mới
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Dict, Any, List

from ..services.quote_generation_service import QuoteGenerationService
from ..models.document_generation_models import (
    SaveQuoteSettingsRequest,
    QuoteGenerationRequest,
    QuoteGenerationResponse,
    GetUserQuoteDataResponse,
)
from ..middleware.firebase_auth import get_current_user
from ..utils.response_utils import create_success_response, create_error_response
from ..utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(prefix="/api/quotes", tags=["Quote Generation"])

# Initialize service
# Remove global service instance - will create per request
# quote_service = QuoteGenerationService()


async def get_quote_service() -> QuoteGenerationService:
    """Get initialized quote service instance"""
    service = QuoteGenerationService()
    await service.initialize()
    return service


# Remove the startup event since we initialize per request
# @router.on_event("startup")
# async def startup_event():
#     """Initialize service on startup"""
#     await quote_service.initialize()


@router.post("/test/generate", response_model=Dict[str, Any])
async def test_generate_quote_no_auth() -> Dict[str, Any]:
    """
    Test endpoint để tạo quote không cần authentication
    """
    try:
        # Mock user data
        user_id = "test_user_123"
        firebase_uid = "test_firebase_uid_123"

        # Mock settings request
        mock_request = SaveQuoteSettingsRequest(
            company_info={
                "name": "Công ty TNHH Công nghệ AI Vũng Tàu",
                "address": "123 Đường Lê Lợi, TP. Vũng Tàu, BR-VT",
                "phone": "0254.123.4567",
                "email": "contact@aivungtau.com",
                "website": "https://aivungtau.com",
                "tax_code": "3600123456",
            },
            customer_info={
                "name": "Khách hàng ABC Corporation",
                "address": "456 Đường Nguyễn Thị Minh Khai, Quận 1, TP.HCM",
                "phone": "028.987.6543",
                "email": "procurement@abc-corp.com",
                "contact_person": "Bà Nguyễn Thị Lan",
            },
            payment_terms={
                "method": "Chuyển khoản ngân hàng",
                "duration": 30,
                "bank_info": "Ngân hàng TMCP Công Thương Việt Nam (VietinBank) - CN Vũng Tàu - STK: 1234567890123",
                "notes": "Thanh toán trong vòng 30 ngày kể từ ngày xuất hóa đơn",
            },
        )

        # Save settings
        settings_id = await quote_service.save_quote_settings(
            user_id=user_id, firebase_uid=firebase_uid, request=mock_request
        )

        # Mock quote generation request
        quote_request = QuoteGenerationRequest(
            settings_id=settings_id,
            template_id=None,  # Sẽ dùng template mặc định
            user_query="Tạo báo giá cho dịch vụ phát triển website thương mại điện tử với tổng giá trị 55.000.000 VND",
            items=[
                {
                    "name": "Phát triển website thương mại điện tử",
                    "description": "Xây dựng website bán hàng online với đầy đủ tính năng",
                    "quantity": 1,
                    "unit": "dự án",
                    "unit_price": 55000000,
                    "total": 55000000,
                }
            ],
        )

        # Generate quote
        result = await quote_service.generate_quote(user_id, quote_request)

        return create_success_response(
            data=result,
            message=f"Test quote generation successful!",
        )

    except Exception as e:
        print(f"❌ Test quote generation error: {e}")
        import traceback

        traceback.print_exc()
        return create_error_response(f"Test quote generation failed: {str(e)}")


@router.post("/settings/save", response_model=Dict[str, Any])
async def save_quote_settings(
    request: SaveQuoteSettingsRequest, current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Lưu settings ban đầu cho quote
    """
    try:
        print(f"🔍 DEBUG current_user: {current_user}")
        user_id = current_user.get("user_id") or current_user.get("uid")
        firebase_uid = current_user.get("uid")

        if not user_id or not firebase_uid:
            raise HTTPException(status_code=400, detail="Thiếu thông tin user ID")

        quote_service = await get_quote_service()
        settings_id = await quote_service.save_quote_settings(
            user_id=user_id, firebase_uid=firebase_uid, request=request
        )

        return create_success_response(
            data={"settings_id": settings_id}, message="Settings đã được lưu thành công"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=List[Dict[str, Any]])
async def get_templates(
    current_user: dict = Depends(get_current_user),
    service: QuoteGenerationService = Depends(get_quote_service),
) -> List[Dict[str, Any]]:
    """
    Lấy danh sách templates có sẵn từ database
    """
    try:
        # Get templates from database
        await service.initialize()
        templates_cursor = service.db.document_templates.find({"is_active": True})
        templates_docs = await templates_cursor.to_list(None)

        # Convert to API response format
        templates = []
        for doc in templates_docs:
            templates.append(
                {
                    "id": doc["_id"],
                    "name": doc["name"],
                    "type": doc["type"],
                    "description": doc["description"],
                    "is_active": doc["is_active"],
                    "category": doc.get("category", "general"),
                    "created_at": doc.get("created_at", "2025-01-01T00:00:00Z"),
                }
            )

        logger.info(f"✅ Retrieved {len(templates)} templates from database")
        return templates

    except Exception as e:
        logger.error(f"❌ Error fetching templates: {str(e)}")
        # Fallback to mock templates if database fails
        templates = [
            {
                "id": "template_quote_001",
                "name": "Mẫu báo giá chuẩn",
                "type": "quote",
                "description": "Template chuẩn cho báo giá dịch vụ",
                "is_active": True,
                "category": "general",
                "created_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": "template_quote_002",
                "name": "Mẫu báo giá công nghệ",
                "type": "quote",
                "description": "Template chuyên dụng cho dự án công nghệ",
                "is_active": True,
                "category": "technology",
                "created_at": "2025-01-01T00:00:00Z",
            },
        ]
        logger.warning(f"⚠️ Using fallback templates due to error: {str(e)}")
        return templates


@router.get("/user-data", response_model=GetUserQuoteDataResponse)
async def get_user_quote_data(
    current_user: dict = Depends(get_current_user),
    service: QuoteGenerationService = Depends(get_quote_service),
) -> GetUserQuoteDataResponse:
    """
    Lấy dữ liệu quote gần nhất của user để frontend sử dụng
    Bao gồm: settings gần nhất, quotes gần đây, templates có sẵn
    """
    try:
        user_id = current_user.get("user_id")
        firebase_uid = current_user.get("uid")

        return await service.get_user_quote_data(
            user_id=user_id, firebase_uid=firebase_uid
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_quote_history(
    current_user: dict = Depends(get_current_user),
    service: QuoteGenerationService = Depends(get_quote_service),
) -> Dict[str, Any]:
    """
    Lấy lịch sử các quotes đã tạo của user
    """
    try:
        user_id = current_user.get("user_id")
        firebase_uid = current_user.get("uid")

        # Get quote history from service
        quotes = await service.get_quote_history(
            user_id=user_id, firebase_uid=firebase_uid
        )

        return {"success": True, "count": len(quotes), "quotes": quotes}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=QuoteGenerationResponse)
async def generate_quote(
    request: QuoteGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    service: QuoteGenerationService = Depends(get_quote_service),
) -> QuoteGenerationResponse:
    """
    Tạo quote mới với template đã chọn và R2 storage

    Flow:
    1. User chọn template từ /api/quotes/templates
    2. User điền thông tin và gửi request này
    3. Backend sẽ tạo file DOCX in-memory và upload lên R2
    4. Trả về pre-signed URL để download (30 phút)

    Body example:
    {
        "template_id": "template_quote_001",
        "company_name": "Công ty ABC",
        "user_query": "Tôi cần báo giá dịch vụ phát triển website",
        "project_details": {
            "budget": "50000000",
            "timeline": "3 tháng"
        }
    }
    """
    try:
        user_id = current_user.get("firebase_uid", current_user.get("uid"))
        firebase_uid = current_user.get("firebase_uid", current_user.get("uid"))

        # Validate template_id
        if not request.template_id:
            raise HTTPException(
                status_code=400,
                detail="template_id is required. Use GET /api/quotes/templates to get available templates.",
            )

        # Create or get settings_id if not provided
        if not request.settings_id:
            # Create minimal settings from request data
            from ..models.document_generation_models import (
                SaveQuoteSettingsRequest,
                CompanyInfo,
                CustomerInfo,
                PaymentTerms,
            )

            minimal_settings = SaveQuoteSettingsRequest(
                company_info=CompanyInfo(
                    name=request.company_name or "Công ty ABC",
                    address="Địa chỉ công ty",
                    phone="0901234567",
                    email="contact@company.com",
                ),
                customer_info=CustomerInfo(
                    name=request.customer_name or "Khách hàng",
                    email="customer@email.com",
                ),
                payment_terms=PaymentTerms(
                    payment_schedule="Báo giá có hiệu lực trong 30 ngày",
                    payment_method="Chuyển khoản",
                ),
            )

            settings_id = await service.save_quote_settings(
                user_id, firebase_uid, minimal_settings
            )
            request.settings_id = settings_id

        # Generate quote
        response = await service.generate_quote(
            user_id=user_id, firebase_uid=firebase_uid, request=request
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in generate_quote: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi tạo quote: {str(e)}")


@router.get("/download/{quote_id}")
async def download_quote_file(
    quote_id: str,
    current_user: dict = Depends(get_current_user),
    service: QuoteGenerationService = Depends(get_quote_service),
):
    """
    Download file quote đã tạo (Deprecated - use R2 pre-signed URLs instead)
    """
    try:
        user_id = current_user.get("user_id")

        file_path = await service.get_quote_file(quote_id, user_id)

        if not file_path:
            raise HTTPException(
                status_code=404,
                detail="File không tồn tại hoặc đã hết hạn. Sử dụng pre-signed URL để download.",
            )

        return FileResponse(
            path=file_path,
            filename=f"quote_{quote_id}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== TEST ENDPOINTS (Không cần authentication) =====


@router.post("/test/generate-without-auth", response_model=Dict[str, Any])
async def test_generate_quote_without_auth(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test endpoint để tạo quote không cần authentication
    Dùng để debug và test AI generation
    """
    try:
        # Mock user data
        user_id = "test_user"
        firebase_uid = "test_firebase_uid"

        # Create test settings
        from ..models.document_generation_models import (
            CompanyInfo,
            CustomerInfo,
            PaymentTerms,
            SaveQuoteSettingsRequest,
        )

        test_settings_request = SaveQuoteSettingsRequest(
            company_info=CompanyInfo(
                name=request.get("company_name", "Công ty Test"),
                address=request.get("company_address", "123 Test Street"),
                tax_code="1234567890",
                representative="Nguyễn Văn A",
                phone="0123456789",
                email="test@company.com",
            ),
            customer_info=CustomerInfo(
                name=request.get("customer_name", "Khách hàng Test"),
                address=request.get("customer_address", "456 Customer St"),
                contact_person="Trần Thị B",
                phone="0987654321",
                email="customer@test.com",
            ),
            payment_terms=PaymentTerms(
                payment_method="Chuyển khoản",
                payment_schedule="30% trước - 70% sau",
                currency="VND",
            ),
        )

        # Save test settings
        settings_id = await quote_service.save_quote_settings(
            user_id=user_id, firebase_uid=firebase_uid, request=test_settings_request
        )

        # Create generation request
        gen_request = QuoteGenerationRequest(
            settings_id=settings_id,
            user_query=request.get(
                "user_query", "Tạo báo giá cho 10 máy tính xách tay Dell Inspiron 15"
            ),
            generation_type="new",
        )

        # Generate quote
        response = await quote_service.generate_quote(
            user_id=user_id, firebase_uid=firebase_uid, request=gen_request
        )

        return create_success_response(
            data={
                "quote_response": response.dict(),
                "settings_id": settings_id,
                "test_mode": True,
            },
            message="Test quote generation completed",
        )

    except Exception as e:
        return create_error_response(
            message=f"Test generation failed: {str(e)}",
            error_code="TEST_GENERATION_ERROR",
        )


@router.get("/test/health")
async def test_quote_service_health(
    service: QuoteGenerationService = Depends(get_quote_service),
) -> Dict[str, Any]:
    """
    Test health của quote service
    """
    try:
        # Test database connection
        await service.initialize()

        # Test Gemini client
        gemini_status = "OK" if service.gemini_client else "NOT_INITIALIZED"

        return create_success_response(
            data={
                "service_status": "OK",
                "gemini_client": gemini_status,
                "database": "Connected",
            },
            message="Quote service is healthy",
        )

    except Exception as e:
        return create_error_response(
            message=f"Health check failed: {str(e)}", error_code="HEALTH_CHECK_ERROR"
        )
