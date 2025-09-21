"""
Test Unified Chat with Company Data Search
Kiểm tra Unified Chat với tìm kiếm dữ liệu công ty
"""

import asyncio
import httpx
from datetime import datetime

# Test Configuration
API_BASE_URL = "http://localhost:8000"
API_KEY = "agent8x-backend-secret-key-2025"

# Test Headers
HEADERS = {
    "X-API-Key": API_KEY,
    "X-API-Version": "1.0",
    "Content-Type": "application/json",
    "X-Company-Id": "golden-dragon-test-2025",
}


async def test_unified_chat_with_search():
    """Test unified chat with company data search integration"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🧪 Testing Unified Chat with Company Data Search")
        print("=" * 60)

        # Test queries
        test_queries = [
            {
                "message": "có món phở bò không?",
                "description": "Product inquiry - should search company data",
            },
            {
                "message": "giá cả như thế nào?",
                "description": "Sales inquiry - should search products/services",
            },
            {
                "message": "tôi muốn đặt món ăn",
                "description": "Order intent - should show available products",
            },
            {
                "message": "có món ăn nào dưới 80000 đồng không?",
                "description": "Price-based search - should find affordable dishes",
            },
            {
                "message": "đồ uống có gì?",
                "description": "Category search - should find beverages",
            },
        ]

        for i, test_case in enumerate(test_queries, 1):
            print(f"\n📝 Test {i}: {test_case['description']}")
            print(f"   Query: '{test_case['message']}'")

            # Prepare unified chat request
            chat_request = {
                "message": test_case["message"],
                "company_id": "golden-dragon-test-2025",
                "industry": "restaurant",
                "language": "vi",
                "user_info": {
                    "user_id": f"test_user_{i}",
                    "source": "web_device",
                    "name": f"Test User {i}",
                },
                "session_id": f"test_session_{i}_{int(datetime.now().timestamp())}",
                "context": {"test_mode": True},
            }

            try:
                # Call unified chat endpoint
                response = await client.post(
                    f"{API_BASE_URL}/api/unified/chat",
                    headers=HEADERS,
                    json=chat_request,
                )

                if response.status_code == 200:
                    result = response.json()

                    print(f"   ✅ Success!")
                    print(
                        f"   Intent: {result.get('intent', 'unknown')} (confidence: {result.get('confidence', 0):.2f})"
                    )
                    print(f"   Language: {result.get('language', 'unknown')}")

                    response_message = result.get("message", "")
                    print(f"   Response: {response_message[:300]}...")

                    # Check if response contains company data
                    response_text = response_message.lower()
                    has_product_info = any(
                        keyword in response_text
                        for keyword in [
                            "phở",
                            "bò",
                            "gà",
                            "cơm",
                            "bánh",
                            "nước",
                            "cà phê",
                            "giá",
                            "đồng",
                            "vnd",
                            "bánh xèo",
                            "gỏi cuốn",
                            "75000",
                            "120000",
                            "80000",
                        ]
                    )

                    if has_product_info:
                        print(f"   🎯 Contains company data: YES")
                    else:
                        print(f"   ⚠️  Contains company data: NO")

                else:
                    print(f"   ❌ Failed: {response.status_code}")
                    print(f"   Error: {response.text}")

            except Exception as e:
                print(f"   ❌ Error: {e}")

            # Small delay between requests
            await asyncio.sleep(1)

        print(f"\n🎯 Unified Chat Integration Test Completed!")


async def main():
    """Main test runner"""
    print("🚀 Unified Chat Integration Tests")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Company: golden-dragon-test-2025")

    await test_unified_chat_with_search()


if __name__ == "__main__":
    asyncio.run(main())
