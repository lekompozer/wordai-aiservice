#!/usr/bin/env python3
"""
Test optimized company data retrieval - products/services vs other content
Test tối ưu retrieval dữ liệu company - products/services vs nội dung khác
"""

import asyncio
import json
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.unified_chat_service import UnifiedChatService
from src.models.unified_models import Industry
from src.config.settings import get_settings


async def test_optimized_retrieval():
    """Test optimized data retrieval based on content_type"""
    print("🧪 Testing Optimized Company Data Retrieval")
    print("=" * 60)

    try:
        settings = get_settings()
        chat_service = UnifiedChatService()

        # Test company
        test_company = "aia"
        test_query = "điều hòa"

        print(f"🔍 Testing search for: {test_query}")
        print(f"📢 Company: {test_company}")

        # Perform hybrid search
        results = await chat_service._hybrid_search_company_data(
            company_id=test_company,
            query=test_query,
            limit=10,
            score_threshold=0.1,  # Low threshold to get more results
            industry=Industry.OTHER,
        )

        print(f"\n📊 Search Results: {len(results)} chunks found")
        print("-" * 50)

        # Analyze results by content_type
        product_service_count = 0
        other_content_count = 0

        for i, result in enumerate(results, 1):
            content_type = result.get("content_type", "unknown")
            structured_data = result.get("structured_data", {})
            content_for_rag = result.get("content_for_rag", "")[:100]

            print(f"\n{i}. Content Type: {content_type}")
            print(f"   Score: {result.get('score', 0):.3f}")
            print(f"   Source: {result.get('search_source', 'unknown')}")

            if content_type in ["extracted_product", "extracted_service"]:
                product_service_count += 1
                print(f"   🎯 OPTIMIZED - Product/Service Data:")
                print(f"   - Product ID: {structured_data.get('product_id', 'N/A')}")
                print(
                    f"   - Retrieval Context: {structured_data.get('retrieval_context', 'N/A')[:80]}..."
                )
                print(f"   - Structured Data Keys: {list(structured_data.keys())}")
            else:
                other_content_count += 1
                print(f"   📄 FULL DATA - Other Content:")
                print(f"   - Content preview: {content_for_rag}...")
                print(f"   - Structured Data Keys: {list(structured_data.keys())}")

            print(f"   - Data Type: {result.get('data_type', 'N/A')}")

        print(f"\n📈 Summary:")
        print(f"   🎯 Optimized (Products/Services): {product_service_count}")
        print(f"   📄 Full Data (Other Content): {other_content_count}")
        print(f"   📊 Total Results: {len(results)}")

        # Test data size reduction
        if product_service_count > 0:
            print(f"\n💡 Optimization Benefits:")
            print(
                f"   - Products/services use minimal fields (product_id + retrieval_context)"
            )
            print(f"   - Other content maintains full structured_data")
            print(
                f"   - Reduced data transfer and prompt size for {product_service_count} product/service chunks"
            )

        return results

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return None


async def main():
    """Main test function"""
    results = await test_optimized_retrieval()

    if results:
        print(f"\n✅ Test completed successfully!")
        print(
            f"   Found {len(results)} search results with content_type-based optimization"
        )
    else:
        print(f"\n❌ Test failed - no results or error occurred")


if __name__ == "__main__":
    asyncio.run(main())
