#!/usr/bin/env python3
"""
Test script for comprehensive hybrid search functionality
Script test cho chức năng tìm kiếm hybrid toàn diện
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.services.qdrant_company_service import get_qdrant_service
from src.services.company_context_service import get_company_context_service
from src.models.unified_models import Industry, IndustryDataType, Language
from src.models.company_context import BasicInfo, FAQ, Scenario, SocialLinks, Location
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_comprehensive_hybrid_search():
    """Test comprehensive hybrid search with real data"""
    try:
        logger.info("🚀 Starting comprehensive hybrid search test...")

        # Step 1: Set up test company context
        company_id = "test_company_001"
        context_service = get_company_context_service()
        qdrant_service = get_qdrant_service()

        # Step 2: Create test basic info with new structure
        basic_info = BasicInfo(
            name="Công ty Test ABC",
            industry="financial_services",
            description="Công ty chuyên cung cấp dịch vụ tư vấn tài chính và bảo hiểm",
            location=Location(
                country="Việt Nam",
                city="TP.HCM",
                address="123 Đường Test, Quận 1, TP.HCM",
            ),
            email="contact@test-abc.com",
            phone="0123456789",
            website="https://test-abc.com",
            socialLinks=SocialLinks(
                facebook="https://facebook.com/test-abc",
                zalo="0123456789",
                whatsapp="+84123456789",
            ),
        )

        # Step 3: Create test FAQs
        test_faqs = [
            FAQ(
                question="Lãi suất vay mua nhà hiện tại là bao nhiêu?",
                answer="Lãi suất vay mua nhà hiện tại từ 8.5% - 12% tùy theo thời hạn vay và khả năng tài chính.",
                category="Vay mua nhà",
            ),
            FAQ(
                question="Điều kiện vay mua xe ô tô như thế nào?",
                answer="Khách hàng cần có thu nhập ổn định từ 15 triệu/tháng, thời hạn vay tối đa 7 năm.",
                category="Vay mua xe",
            ),
            FAQ(
                question="Bảo hiểm nhân thọ có những gói nào?",
                answer="Chúng tôi có 3 gói: Gói cơ bản (2 triệu/năm), Gói nâng cao (5 triệu/năm), Gói VIP (10 triệu/năm).",
                category="Bảo hiểm",
            ),
        ]

        # Step 4: Create test scenarios
        test_scenarios = [
            Scenario(
                situation="Khách hàng muốn vay tiền để mua nhà đầu tiên",
                solution="Hướng dẫn khách hàng chuẩn bị hồ sơ: CMND, sổ hộ khẩu, giấy tờ thu nhập, hợp đồng mua bán sơ bộ. Tư vấn các gói vay ưu đãi cho người mua nhà lần đầu với lãi suất từ 8.5%.",
                category="Vay mua nhà",
            ),
            Scenario(
                situation="Khách hàng có nhu cầu bảo hiểm sức khỏe cho gia đình",
                solution="Phân tích nhu cầu gia đình, tư vấn gói bảo hiểm phù hợp với ngân sách. Ưu tiên các gói có bảo hiểm toàn diện cho trẻ em và người cao tuổi.",
                category="Bảo hiểm sức khỏe",
            ),
        ]

        # Step 5: Set context data (this will auto-index to Qdrant)
        logger.info("📝 Setting up company context...")
        await context_service.set_basic_info(company_id, basic_info)
        await context_service.set_faqs(company_id, test_faqs)
        await context_service.set_scenarios(company_id, test_scenarios)

        # Step 6: Wait a bit for indexing to complete
        await asyncio.sleep(2)

        # Step 7: Test comprehensive hybrid search with different queries
        test_queries = [
            "Tôi muốn vay tiền mua nhà",
            "Lãi suất vay mua xe ô tô",
            "Gói bảo hiểm nào phù hợp cho gia đình",
            "Điều kiện vay mua nhà đầu tiên",
            "Thông tin liên hệ công ty",
        ]

        for i, query in enumerate(test_queries, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 Test {i}: Query = '{query}'")
            logger.info(f"{'='*60}")

            # Test comprehensive hybrid search
            results = await qdrant_service.comprehensive_hybrid_search(
                company_id=company_id,
                query=query,
                industry=Industry.BANKING,
                data_types=[
                    IndustryDataType.FAQ,
                    IndustryDataType.KNOWLEDGE_BASE,
                    IndustryDataType.COMPANY_INFO,
                ],
                score_threshold=0.6,
                max_chunks=10,
            )

            logger.info(f"📊 Found {len(results)} chunks above threshold 0.6:")
            for j, result in enumerate(results, 1):
                logger.info(
                    f"   {j}. {result['data_type']} (score: {result['score']:.3f}, source: {result['search_source']})"
                )
                logger.info(f"      Content: {result['content_for_rag'][:100]}...")

            if not results:
                logger.warning(f"⚠️ No results found for query: '{query}'")

        logger.info(f"\n{'='*60}")
        logger.info("✅ Comprehensive hybrid search test completed!")
        logger.info(f"{'='*60}")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_comprehensive_hybrid_search())
