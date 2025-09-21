"""
Test script for Document Generation Phase 1
"""

import asyncio
import sys
import os

sys.path.append("/Users/user/Code/ai-chatbot-rag")

from src.models.document_generation_models import (
    QuoteRequest,
    CompanyInfo,
    CustomerInfo,
    ProductInfo,
    PaymentTerms,
)
from src.services.document_generation_service import DocumentGenerationService


async def test_phase_1():
    """Test Phase 1 implementation"""
    print("🚀 Testing Document Generation Phase 1...")

    # Test data
    company_info = CompanyInfo(
        name="Công ty TNHH ABC Technology",
        address="123 Đường ABC, Quận 1, TP.HCM",
        tax_code="0123456789",
        representative="Nguyễn Văn A",
        position="Giám đốc",
        phone="0901234567",
        email="info@abc-tech.com",
        website="https://abc-tech.com",
        bank_account="123456789",
        bank_name="Ngân hàng ABC",
    )

    customer_info = CustomerInfo(
        name="Công ty TNHH XYZ Solutions",
        address="456 Đường XYZ, Quận 3, TP.HCM",
        contact_person="Trần Thị B",
        position="Trưởng phòng IT",
        phone="0912345678",
        email="b.tran@xyz-solutions.com",
        tax_code="0987654321",
    )

    products = [
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
        ),
        ProductInfo(
            name="Đào tạo sử dụng phần mềm",
            description="Khóa đào tạo toàn diện cho 10 nhân viên",
            quantity=10,
            unit="người",
            unit_price=2000000,
            total_price=20000000,
            warranty_period="3 tháng hỗ trợ",
            delivery_time="7 ngày sau khi cài đặt",
        ),
    ]

    payment_terms = PaymentTerms(
        payment_method="Chuyển khoản ngân hàng",
        payment_schedule="50% tạm ứng, 50% sau khi nghiệm thu",
        currency="VND",
        advance_payment_percent=50.0,
    )

    # Create quote request
    quote_request = QuoteRequest(
        template_id="default_quote_template",  # We'll need to create this
        company_info=company_info,
        customer_info=customer_info,
        products=products,
        payment_terms=payment_terms,
        additional_terms="Báo giá này có hiệu lực trong 30 ngày.",
        validity_period="30 ngày",
    )

    print("✅ Test data created successfully")

    # Test service initialization
    try:
        service = DocumentGenerationService()
        print("✅ DocumentGenerationService initialized")
    except Exception as e:
        print(f"❌ Error initializing service: {e}")
        return

    # Test template variables preparation
    try:
        from src.models.document_generation_models import DocumentRequest

        doc_request = DocumentRequest(
            type="quote",
            template_id="test_template",
            company_info=company_info,
            customer_info=customer_info,
            products=products,
            payment_terms=payment_terms,
            additional_terms="Test terms",
        )

        template_vars = await service.prepare_template_variables(
            doc_request, {"quote_number": "BG-2025-001"}
        )
        print("✅ Template variables prepared:")
        print(f"   - Company: {template_vars['company']['name']}")
        print(f"   - Customer: {template_vars['customer']['name']}")
        print(f"   - Products count: {len(template_vars['products'])}")
        print(f"   - Total amount: {template_vars['total_amount']}")

    except Exception as e:
        print(f"❌ Error preparing template variables: {e}")

    # Test database connection
    try:
        from src.config.database import get_database

        db = get_database()
        await db.command("ping")
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

    # Test AI client
    try:
        from src.config.ai_config import get_ai_client

        ai_client = get_ai_client()
        response = await ai_client.generate_text("Test prompt", max_tokens=100)
        print("✅ AI client initialized:")
        print(f"   - Response: {response.get('content', 'No content')[:50]}...")
    except Exception as e:
        print(f"❌ AI client error: {e}")

    print("\n🎉 Phase 1 testing completed!")
    print("\n📋 Next steps for Phase 2:")
    print("1. Create default templates in database")
    print("2. Test API endpoints")
    print("3. Implement actual AI text generation")
    print("4. Set up file serving and download")


if __name__ == "__main__":
    asyncio.run(test_phase_1())
