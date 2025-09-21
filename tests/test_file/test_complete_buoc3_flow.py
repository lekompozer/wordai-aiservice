#!/usr/bin/env python3
"""
Test Complete Bước 3 Flow: Upload → Extraction → Catalog → Chat với Real-time Inventory
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path

# Add src to path
import sys

sys.path.append("src")

from services.product_catalog_service import (
    ProductCatalogService,
    get_product_catalog_service,
)
from services.unified_chat_service import UnifiedChatService
from api.callbacks.enhanced_callback_handler import EnhancedCallbackHandler


async def test_complete_flow():
    """Test toàn bộ flow Bước 3"""
    print("🚀 TESTING COMPLETE BƯỚC 3 FLOW")
    print("=" * 60)

    # 1. Test ProductCatalogService
    print("\n1️⃣ TESTING PRODUCT CATALOG SERVICE")
    catalog_service = get_product_catalog_service()

    # Test data - giả lập dữ liệu từ extraction
    test_products = [
        {
            "name": "iPhone 15 Pro Max",
            "description": "Smartphone cao cấp với chip A17 Pro, camera 48MP",
            "price": "29,990,000",
            "quantity": "15",
            "category": "Smartphone",
        },
        {
            "name": "Samsung Galaxy S24 Ultra",
            "description": "Flagship Android với S Pen, màn hình 6.8 inch",
            "price": "31,990,000",
            "quantity": "8",
            "category": "Smartphone",
        },
        {
            "name": "MacBook Air M3",
            "description": "Laptop siêu nhẹ với chip Apple M3",
            "price": "28,990,000",
            "quantity": "12",
            "category": "Laptop",
        },
    ]

    # Register products và lấy IDs
    product_ids = {}
    for product in test_products:
        try:
            result = await catalog_service.register_product(
                company_id="TESTCO123",
                name=product["name"],
                description=product["description"],
                price=product["price"],
                quantity=product["quantity"],
                category=product["category"],
            )
            product_ids[product["name"]] = result["product_id"]
            print(f"✅ Registered: {product['name']} → {result['product_id']}")
        except Exception as e:
            print(f"❌ Failed to register {product['name']}: {e}")

    # 2. Test Enhanced Callback Handler
    print(f"\n2️⃣ TESTING ENHANCED CALLBACK HANDLER")
    handler = EnhancedCallbackHandler()

    # Simulate extraction result
    extraction_result = {
        "extracted_data": {
            "products": [
                {
                    "name": "AirPods Pro Gen 3",
                    "price": "6,990,000 VNĐ",
                    "description": "Tai nghe không dây với chống ồn chủ động",
                    "quantity": "25 chiếc",
                    "category": "Audio",
                }
            ],
            "services": [
                {
                    "name": "Bảo hành Premium",
                    "price": "2,990,000 VNĐ",
                    "description": "Bảo hành mở rộng 3 năm cho tất cả sản phẩm",
                    "availability": "Có sẵn",
                }
            ],
        },
        "company_id": "TESTCO123",
        "session_id": "test_session_123",
    }

    try:
        # Test callback với ProductCatalogService integration
        await handler.handle_extraction_complete(
            extraction_result,
            webhook_url="http://localhost:8000/test-webhook",  # Fake URL for testing
            company_id="TESTCO123",
        )
        print("✅ Callback handler processed successfully")
    except Exception as e:
        print(f"❌ Callback handler error: {e}")

    # 3. Test UnifiedChatService with Catalog Integration
    print(f"\n3️⃣ TESTING UNIFIED CHAT SERVICE WITH CATALOG")
    chat_service = UnifiedChatService()

    # Test queries về inventory
    test_queries = [
        "iPhone 15 Pro Max còn hàng không? Giá bao nhiêu?",
        "So sánh giá iPhone 15 Pro Max và Samsung Galaxy S24 Ultra",
        "MacBook Air M3 còn mấy chiếc?",
        "Sản phẩm nào đang có sẵn trong kho?",
    ]

    for query in test_queries:
        print(f"\n🤔 Query: {query}")
        try:
            response = await chat_service.chat_with_context_async(
                user_query=query,
                company_id="TESTCO123",
                session_id="test_session_123",
                user_name="Test User",
            )

            if response and response.get("success"):
                answer = response["answer"]
                print(f"🤖 Response: {answer[:200]}...")

                # Check for catalog data integration
                if "[DỮ LIỆU TỒN KHO" in answer:
                    print("✅ Catalog data được tích hợp trong response")
                else:
                    print("⚠️  Không thấy catalog data trong response")

            else:
                print(f"❌ Chat failed: {response}")

        except Exception as e:
            print(f"❌ Chat error: {e}")

    # 4. Test Hybrid Search trực tiếp
    print(f"\n4️⃣ TESTING HYBRID SEARCH WITH CATALOG PRIORITY")
    try:
        search_result = await chat_service._hybrid_search_company_data_optimized(
            query="iPhone 15 Pro Max giá", company_id="TESTCO123"
        )
        print(f"📊 Hybrid search result: {len(search_result)} characters")

        # Check priority structure
        if "[DỮ LIỆU TỒN KHO - CHÍNH XÁC NHẤT]" in search_result:
            print("✅ Catalog data có priority cao nhất")
        if "[DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]" in search_result:
            print("✅ RAG data được bao gồm như supplementary")

    except Exception as e:
        print(f"❌ Hybrid search error: {e}")

    print(f"\n🎯 BƯỚC 3 TESTING COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_complete_flow())
