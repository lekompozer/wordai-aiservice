"""
Direct test for quote creation with corrected database configuration
"""

import asyncio
from src.services.document_generation_service import DocumentGenerationService
from src.models.document_generation_models import (
    QuoteRequest,
    CompanyInfo,
    CustomerInfo,
    ProductInfo,
    PaymentTerms,
)


async def test_quote_creation():
    """Test creating a quote directly with the service"""

    print("🔧 Testing Quote Creation...")

    # Initialize service
    service = DocumentGenerationService()
    print(f"📊 Connected to database: {service.db.name}")

    # Get available templates
    templates = await service.list_templates("quote")
    print(f"📄 Available quote templates: {len(templates)}")

    if not templates:
        print("❌ No quote templates found!")
        return

    template = templates[0]
    print(f"✅ Using template: {template.name} (ID: {template.id})")

    # Create quote request
    quote_request = QuoteRequest(
        template_id=str(template.id),
        company_info=CompanyInfo(
            name="Công ty TNHH ABC Technology",
            address="123 Đường ABC, Quận 1, TP.HCM",
            tax_code="0123456789",
            representative="Nguyễn Văn A",
            position="Giám đốc",
            phone="0901234567",
            email="info@abc-tech.com",
            website="https://abc-tech.com",
        ),
        customer_info=CustomerInfo(
            name="Công ty TNHH XYZ Solutions",
            address="456 Đường XYZ, Quận 3, TP.HCM",
            contact_person="Trần Thị B",
            position="Trưởng phòng IT",
            phone="0912345678",
            email="b.tran@xyz-solutions.com",
            tax_code="0987654321",
        ),
        products=[
            ProductInfo(
                name="Phần mềm quản lý kho",
                description="Hệ thống quản lý kho hàng tự động với AI",
                quantity=1,
                unit="bộ",
                unit_price=50000000,
                total_price=50000000,
                specifications={"version": "2.0", "database": "MongoDB"},
                warranty_period="12 tháng",
                delivery_time="30 ngày",
            )
        ],
        payment_terms=PaymentTerms(
            payment_method="Chuyển khoản ngân hàng",
            payment_schedule="50% tạm ứng, 50% sau khi nghiệm thu",
            currency="VND",
            advance_payment_percent=50.0,
        ),
        additional_terms="Báo giá có hiệu lực trong 30 ngày.",
        validity_period="30 ngày",
    )

    print("📝 Creating quote...")

    try:
        # Create quote
        result = await service.create_quote(quote_request, user_id="test_user")

        print(f"✅ Quote creation result:")
        print(f"   📄 Request ID: {result.request_id}")
        print(f"   📊 Status: {result.status}")
        print(f"   💬 Message: {result.message}")
        print(f"   📁 File URL: {result.file_url}")
        print(f"   ⏱️ Processing time: {result.processing_time:.2f}s")

        if result.status == "completed":
            print("🎉 Quote created successfully!")

            # Check file exists
            file_path = await service.get_file_path(result.request_id)
            if file_path:
                print(f"✅ File exists at: {file_path}")
            else:
                print("❌ File not found or expired")
        else:
            print(f"❌ Quote creation failed: {result.message}")

    except Exception as e:
        print(f"❌ Error creating quote: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_quote_creation())
