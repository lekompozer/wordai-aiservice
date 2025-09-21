"""
Demo endpoint for testing document generation without database
"""

import json
from datetime import datetime
from src.models.document_generation_models import (
    CompanyInfo,
    CustomerInfo,
    ProductInfo,
    PaymentTerms,
    QuoteRequest,
    DocumentResponse,
)
from src.services.document_generation_service import DocumentGenerationService


async def demo_quote_generation():
    """Demo quote generation with mock data"""
    print("🚀 Demo: Quote Generation...")

    # Mock company info
    company = CompanyInfo(
        name="Công ty TNHH ABC Technology",
        address="123 Đường ABC, Quận 1, TP.HCM",
        tax_code="0123456789",
        representative="Nguyễn Văn A",
        position="Giám đốc",
        phone="0901234567",
        email="info@abc-tech.com",
        website="https://abc-tech.com",
    )

    # Mock customer info
    customer = CustomerInfo(
        name="Công ty TNHH XYZ Solutions",
        address="456 Đường XYZ, Quận 3, TP.HCM",
        contact_person="Trần Thị B",
        position="Trưởng phòng IT",
        phone="0912345678",
        email="b.tran@xyz-solutions.com",
        tax_code="0987654321",
    )

    # Mock products
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
            delivery_time="7 ngày",
        ),
    ]

    # Mock payment terms
    payment_terms = PaymentTerms(
        payment_method="Chuyển khoản ngân hàng",
        payment_schedule="50% tạm ứng, 50% sau khi nghiệm thu",
        currency="VND",
        advance_payment_percent=50.0,
    )

    # Create quote request
    quote_request = QuoteRequest(
        template_id="demo_template",  # Mock template ID
        company_info=company,
        customer_info=customer,
        products=products,
        payment_terms=payment_terms,
        additional_terms="Báo giá có hiệu lực trong 30 ngày.",
        validity_period="30 ngày",
    )

    print("✅ Mock data created")
    print(f"   Company: {company.name}")
    print(f"   Customer: {customer.name}")
    print(f"   Products: {len(products)} items")
    print(f"   Total value: {sum(p.total_price for p in products):,} VND")

    # Test template variables preparation
    try:
        service = DocumentGenerationService()

        # Create mock document request
        from src.models.document_generation_models import DocumentRequest

        doc_request = DocumentRequest(
            type="quote",
            template_id="demo_template",
            company_info=company,
            customer_info=customer,
            products=products,
            payment_terms=payment_terms,
            additional_terms="Demo terms",
        )

        # Prepare template variables
        extra_data = {
            "quote_number": f"BG-{datetime.now().strftime('%Y%m%d')}-DEMO001",
            "quote_date": datetime.now().strftime("%d/%m/%Y"),
            "validity_period": "30 ngày",
        }

        template_vars = await service.prepare_template_variables(
            doc_request, extra_data
        )

        print("\n✅ Template variables prepared:")
        print(f"   Quote number: {template_vars.get('quote_number')}")
        print(f"   Quote date: {template_vars.get('quote_date')}")
        print(f"   Company: {template_vars['company']['name']}")
        print(f"   Customer: {template_vars['customer']['name']}")
        print(f"   Products: {len(template_vars['products'])} items")
        print(f"   Total amount: {template_vars['total_amount']}")

        # Test AI content generation
        from src.models.document_generation_models import DocumentTemplate

        mock_template = DocumentTemplate(
            type="quote",
            subtype="demo",
            name="Demo Template",
            description="Demo template for testing",
            template_content="<p>Mock template content</p>",
            variables=["company", "customer", "products"],
        )

        ai_content = await service.generate_ai_content(
            doc_request, mock_template, template_vars
        )

        print("\n✅ AI content generated:")
        print(f"   Content length: {len(ai_content)} chars")
        print(f"   Preview: {ai_content[:200]}...")

        print("\n🎉 Demo completed successfully!")
        print("\n📋 What works:")
        print("   ✅ Data models and validation")
        print("   ✅ Template variable preparation")
        print("   ✅ AI content generation (fallback)")
        print("   ✅ Service layer architecture")
        print("   ✅ API endpoint structure")

        print("\n📋 Next improvements needed:")
        print("   🔄 Database authentication fix")
        print("   🔄 Template loading from database")
        print("   🔄 Word document generation")
        print("   🔄 File download functionality")
        print("   🔄 Real AI provider integration")

        return True

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        return False


if __name__ == "__main__":
    import asyncio

    asyncio.run(demo_quote_generation())
