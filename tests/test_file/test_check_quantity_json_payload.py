#!/usr/bin/env python3
"""
Test JSON Payload cho CHECK_QUANTITY với Prompt mới
"""
import asyncio
import json
from datetime import datetime

# Add src to path
import sys

sys.path.append("src")

from services.unified_chat_service import UnifiedChatService


async def test_check_quantity_prompt_webhook():
    """Test CHECK_QUANTITY prompt có tạo webhook_data đúng không"""
    print("🧪 TESTING CHECK_QUANTITY JSON PAYLOAD GENERATION")
    print("=" * 70)

    # Create chat service
    chat_service = UnifiedChatService()

    # Test scenarios
    test_cases = [
        {
            "name": "CHECK_QUANTITY - Customer đồng ý check với thông tin liên hệ",
            "query": "Anh tôi muốn check iPhone 15 Pro Max còn hàng không? Tên tôi là Nguyễn Văn A, SĐT: 0909123456",
            "expected_intent": "CHECK_QUANTITY",
            "should_have_webhook_data": True,
        },
        {
            "name": "CHECK_QUANTITY - Customer chỉ hỏi, chưa đồng ý check",
            "query": "iPhone 15 Pro Max còn hàng không?",
            "expected_intent": "CHECK_QUANTITY",
            "should_have_webhook_data": False,  # Chưa có thông tin liên hệ
        },
        {
            "name": "PLACE_ORDER - Customer đặt hàng",
            "query": "Tôi muốn đặt 2 iPhone 15 Pro Max. Tên: Trần Thị B, SĐT: 0908888999",
            "expected_intent": "PLACE_ORDER",
            "should_have_webhook_data": True,
        },
        {
            "name": "ASK_COMPANY_INFORMATION - Không cần webhook",
            "query": "Công ty bạn là gì?",
            "expected_intent": "ASK_COMPANY_INFORMATION",
            "should_have_webhook_data": False,
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print("-" * 50)

        # Test case setup
        print(f"🤔 Query: {test_case['query']}")

        try:
            # Call chat service directly (simplified)
            response = await chat_service.chat_with_context_async(
                user_query=test_case["query"],
                company_id="TEST_COMPANY",
                session_id=f"test_session_{i}",
                user_name="Test User",
            )

            if response and response.get("success"):
                # Parse AI response to check structure
                try:
                    # The response might be in response["answer"]
                    ai_answer = response.get("answer", "")

                    # Try to parse as JSON (AI should return JSON)
                    if ai_answer.strip().startswith("{"):
                        parsed_ai = json.loads(ai_answer)

                        # Check intent
                        detected_intent = parsed_ai.get("thinking", {}).get("intent")
                        print(f"🎯 Detected Intent: {detected_intent}")

                        if detected_intent == test_case["expected_intent"]:
                            print("✅ Intent detection: CORRECT")
                        else:
                            print(
                                f"❌ Intent detection: WRONG (expected {test_case['expected_intent']})"
                            )

                        # Check webhook_data
                        webhook_data = parsed_ai.get("webhook_data")
                        if test_case["should_have_webhook_data"]:
                            if webhook_data:
                                print("✅ Webhook data: PRESENT")
                                print(
                                    f"📄 Webhook structure: {list(webhook_data.keys())}"
                                )

                                # For CHECK_QUANTITY, verify structure
                                if (
                                    detected_intent == "CHECK_QUANTITY"
                                    and "check_quantity_data" in webhook_data
                                ):
                                    check_data = webhook_data["check_quantity_data"]
                                    required_fields = [
                                        "item_name",
                                        "customer",
                                        "item_type",
                                    ]
                                    missing_fields = [
                                        f
                                        for f in required_fields
                                        if f not in check_data
                                    ]
                                    if not missing_fields:
                                        print(
                                            "✅ CHECK_QUANTITY webhook structure: COMPLETE"
                                        )
                                    else:
                                        print(f"❌ Missing fields: {missing_fields}")

                            else:
                                print("❌ Webhook data: MISSING (should be present)")
                        else:
                            if webhook_data:
                                print("⚠️  Webhook data: PRESENT (not expected, but ok)")
                            else:
                                print("✅ Webhook data: ABSENT (as expected)")

                        # Show final answer
                        final_answer = parsed_ai.get("final_answer", "")[:150]
                        print(f"💬 Final answer: {final_answer}...")

                    else:
                        print(f"❌ AI response is not JSON: {ai_answer[:100]}...")

                except json.JSONDecodeError as e:
                    print(f"❌ Could not parse AI response as JSON: {e}")
                    print(f"Raw response: {ai_answer[:200]}...")

            else:
                print(f"❌ Chat service failed: {response}")

        except Exception as e:
            print(f"❌ Test case failed: {e}")

    print("\n🏁 TEST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_check_quantity_prompt_webhook())
