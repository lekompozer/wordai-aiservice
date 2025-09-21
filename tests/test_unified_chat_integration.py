"""
Test Unified Chat with Company Data Search
Kiểm tra Unified Cha            # Prepare unified chat request
            chat_request = {
                "message": test_case["message"],
                "company_id": "golden-dragon-test-2025",
                "industry": "restaurant",
                "language": "vi",  # Use correct enum value
                "user_info": {
                    "user_id": f"test_user_{i}",
                    "source": "web_device",  # Use correct enum value
                    "name": f"Test User {i}"
                },
                "session_id": f"test_session_{i}_{int(datetime.now().timestamp())}",
                "context": {"test_mode": True}
            } dữ liệu công ty
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
    "X-Company-Id": "golden-dragon-test-2025",  # Company from previous test
}


async def test_unified_chat_with_search():
    """Test unified chat with company data search integration"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🧪 Testing Unified Chat with Company Data Search")
        print("=" * 60)

        # Test queries with different intents
        test_queries = [
            {
                "message": "có món phở bò không?",
                "intent_expected": "information",
                "description": "Product inquiry - should search company data",
            },
            {
                "message": "giá cả như thế nào?",
                "intent_expected": "sales_inquiry",
                "description": "Sales inquiry - should search products/services",
            },
            {
                "message": "tôi muốn đặt món ăn",
                "intent_expected": "sales_inquiry",
                "description": "Order intent - should show available products",
            },
            {
                "message": "có món ăn nào dưới 80000 đồng không?",
                "intent_expected": "information",
                "description": "Price-based search - should find affordable dishes",
            },
            {
                "message": "đồ uống có gì?",
                "intent_expected": "information",
                "description": "Category search - should find beverages",
            },
            {
                "message": "nhà hàng mở cửa mấy giờ?",
                "intent_expected": "information",
                "description": "General info - should search company data",
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
                "language": "vietnamese",
                "user_info": {
                    "user_id": f"test_user_{i}",
                    "source": "web_chat",
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
                    print(f"   Response: {result.get('message', '')[:200]}...")

                    # Check if response contains company data
                    response_text = result.get("message", "").lower()
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


async def test_intent_detection():
    """Test intent detection endpoint"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n🔍 Testing Intent Detection")
        print("=" * 40)

        test_messages = [
            "có món phở bò không?",
            "tôi muốn mua sản phẩm",
            "giá cả như thế nào?",
            "xin chào",
            "cần hỗ trợ",
        ]

        for message in test_messages:
            print(f"\n📝 Message: '{message}'")

            request_data = {
                "message": message,
                "company_id": "golden-dragon-test-2025",
                "industry": "restaurant",
                "language": "vi",  # Use correct enum value
                "user_info": {
                    "user_id": "test_user",
                    "source": "web_device",  # Use correct enum value
                },
            }

            try:
                response = await client.post(
                    f"{API_BASE_URL}/api/unified/detect-intent",
                    headers=HEADERS,
                    json=request_data,
                )

                if response.status_code == 200:
                    result = response.json()

                    lang_detection = result.get("language_detection", {})
                    intent_detection = result.get("intent_detection", {})

                    print(
                        f"   Language: {lang_detection.get('language')} (confidence: {lang_detection.get('confidence', 0):.2f})"
                    )
                    print(
                        f"   Intent: {intent_detection.get('intent')} (confidence: {intent_detection.get('confidence', 0):.2f})"
                    )
                    print(f"   Reasoning: {intent_detection.get('reasoning', 'N/A')}")

                else:
                    print(f"   ❌ Failed: {response.status_code}")

            except Exception as e:
                print(f"   ❌ Error: {e}")


async def main():
    """Main test runner"""
    print("🚀 Unified Chat Integration Tests")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Company: golden-dragon-test-2025")

    await test_unified_chat_with_search()
    await test_intent_detection()


if __name__ == "__main__":
    asyncio.run(main())
