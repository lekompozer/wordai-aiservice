"""
Demo Script - Test Bước 2: Callback Handler Integration
Kiể        ],
        raw_content="--- MENU NHÀ HÀNG PHỞ 24 ---\n\n1. Phở Bò Tái - 65,000đ\n2. Bún Chả - 70,000đ\n\nDịch vụ giao hàng 24/7",
        extraction_metadata={
            "company_id": "restaurant_pho_24_test",  # ✅ FIX: Add company_id here
            "file_name": "menu-pho24.txt",
            "file_size": 1234,
            "ai_provider": "gemini",
            "template_used": "RestaurantExtractionTemplate"
        },llback handler với ProductCatalogService integration

Usage:
python demo_callback_integration.py
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.callbacks.enhanced_callback_handler import enhanced_extraction_callback
from src.api.callbacks.enhanced_callback_handler import CallbackRequest


async def test_callback_integration():
    """Test callback handler với ProductCatalogService integration"""
    print("🧪 Testing Callback Handler Integration - Bước 2")
    print("=" * 60)

    # Mock request data giống thật
    mock_request = CallbackRequest(
        task_id="extract_test_20250819_demo",
        status="completed",
        structured_data={
            "products": [
                {
                    "name": "Phở Bò Tái",
                    "description": "Phở bò tái nạm chín với bánh phở tươi",
                    "price": "65,000 VND",
                    "quantity": 50,
                    "category": "Món chính",
                    "tags": ["phở", "bò", "nước dùng"],
                    "type": "Food",
                },
                {
                    "name": "Bún Chả",
                    "description": "Bún chả Hà Nội với thịt nướng thơm",
                    "price": 70000,
                    "quantity": 25,
                    "category": "Món chính",
                    "tags": ["bún", "thịt nướng"],
                    "type": "Food",
                },
            ],
            "services": [
                {
                    "name": "Giao hàng tận nơi",
                    "description": "Dịch vụ giao hàng trong vòng 30 phút",
                    "price": 15000,
                    "availability": "24/7",
                    "category": "Delivery",
                    "tags": ["giao hàng", "nhanh"],
                    "type": "Delivery Service",
                }
            ],
        },
        raw_content="--- MENU NHÀ HÀNG PHỞ 24 ---\n\n1. Phở Bò Tái - 65,000đ\n2. Bún Chả - 70,000đ\n\nDịch vụ giao hàng 24/7",
        extraction_metadata={
            "file_name": "menu-pho24.txt",
            "file_size": 1234,
            "ai_provider": "gemini",
            "template_used": "RestaurantExtractionTemplate",
        },
        processing_time=18.5,
        timestamp=datetime.now().isoformat(),
    )

    # Mock FastAPI request và background tasks
    mock_fastapi_request = MagicMock()
    mock_fastapi_request.headers = {"x-company-id": "restaurant_pho_24_test"}

    mock_background_tasks = MagicMock()

    print("📋 Test Data:")
    print(f"   Company ID: restaurant_pho_24_test")
    print(f"   Products: {len(mock_request.structured_data['products'])}")
    print(f"   Services: {len(mock_request.structured_data['services'])}")
    print(f"   Task ID: {mock_request.task_id}")

    try:
        # Call enhanced callback handler
        print("\n🔄 Calling enhanced_extraction_callback...")

        response = await enhanced_extraction_callback(
            request=mock_request,
            background_tasks=mock_background_tasks,  # ✅ FIX: Only 2 params needed
        )

        print("✅ Callback processing completed!")
        print(f"   Success: {response.get('success', False)}")
        print(f"   Message: {response.get('message', 'N/A')}")

        if "data_stored" in response:
            stored_data = response["data_stored"]
            print(f"   Products stored: {stored_data.get('products', 0)}")
            print(f"   Services stored: {stored_data.get('services', 0)}")

        # Print enhanced data structure
        print("\n📊 Expected Enhanced Data Structure:")
        print("   Products should have:")
        print("   - product_id: prod_xxxxx-xxx-xxx")
        print("   - catalog_price: extracted clean price")
        print("   - catalog_quantity: extracted quantity")
        print("   - qdrant_point_id: vector storage ID")

        print("   Services should have:")
        print("   - service_id: serv_xxxxx-xxx-xxx")
        print("   - catalog_price: extracted clean price")
        print("   - catalog_quantity: -1 (not tracked)")
        print("   - qdrant_point_id: vector storage ID")

    except Exception as e:
        print(f"❌ Callback integration test failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False

    return True


async def test_data_transformation():
    """Test data transformation với ProductCatalogService"""
    print("\n🔬 Testing Data Transformation")
    print("-" * 40)

    from src.services.product_catalog_service import get_product_catalog_service

    try:
        # Get catalog service
        catalog_service = await get_product_catalog_service()

        # Test data transformation
        sample_ai_data = {
            "name": "Test Product",
            "description": "Test description",
            "price": "100,000 VND",
            "quantity": 10,
            "category": "Test Category",
        }

        print("📝 Original AI Data:")
        print(json.dumps(sample_ai_data, indent=2, ensure_ascii=False))

        # Transform through catalog service
        enriched_data = await catalog_service.register_item(
            item_data=sample_ai_data, company_id="test_company_123", item_type="product"
        )

        print("\n✨ Enriched Data:")
        print(json.dumps(enriched_data, indent=2, ensure_ascii=False))

        # Verify transformations
        assert "product_id" in enriched_data
        assert enriched_data["product_id"].startswith("prod_")
        assert "catalog_price" in enriched_data
        assert "catalog_quantity" in enriched_data

        print("✅ Data transformation successful!")

        # Test clean data for prompts
        catalog_data = await catalog_service.get_catalog_for_prompt(
            company_id="test_company_123", query="test", limit=1
        )

        print("\n📋 Clean Data for AI Prompts:")
        print(json.dumps(catalog_data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ Data transformation test failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False

    return True


async def main():
    """Run all integration tests"""
    print("🚀 Callback Handler Integration Tests - Bước 2")
    print("=" * 60)

    success_count = 0
    total_tests = 2

    # Test 1: Callback Integration
    print("\n🧪 TEST 1: Callback Handler Integration")
    if await test_callback_integration():
        success_count += 1
        print("   ✅ PASSED")
    else:
        print("   ❌ FAILED")

    # Test 2: Data Transformation
    print("\n🧪 TEST 2: Data Transformation")
    if await test_data_transformation():
        success_count += 1
        print("   ✅ PASSED")
    else:
        print("   ❌ FAILED")

    # Results summary
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS: {success_count}/{total_tests} PASSED")

    if success_count == total_tests:
        print("🎉 ALL TESTS PASSED - Bước 2 Integration Successful!")
        print("\n🔜 Ready for Bước 3: Chat Service Integration")
    else:
        print("⚠️  Some tests failed - Review integration code")

    print("\n📋 Next Steps:")
    print("1. Verify MongoDB data contains product_id/service_id")
    print("2. Check webhook payloads have enhanced data structure")
    print("3. Test end-to-end with real file upload")


if __name__ == "__main__":
    # Run async tests
    asyncio.run(main())
