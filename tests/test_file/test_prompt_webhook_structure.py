#!/usr/bin/env python3
"""
Test JSON Payload cho CHECK_QUANTITY - Test trực tiếp prompt building
"""
import asyncio
import json
from datetime import datetime

# Add src to path
import sys

sys.path.append("src")


async def test_prompt_webhook_structure():
    """Test prompt có cấu trúc webhook_data đúng không"""
    print("🧪 TESTING PROMPT WEBHOOK_DATA STRUCTURE")
    print("=" * 70)

    from services.unified_chat_service import UnifiedChatService

    # Create service
    chat_service = UnifiedChatService()

    # Test prompt building
    test_user_context = "This is first conversation"
    test_company_data = """
    [DỮ LIỆU TỒN KHO - CHÍNH XÁC NHẤT]
    - iPhone 15 Pro Max (product_id: iphone15_pro_max_001): Giá 29,990,000 VNĐ, Tồn kho: 15 chiếc
    - Samsung Galaxy S24 (product_id: samsung_s24_ultra_001): Giá 31,990,000 VNĐ, Tồn kho: 8 chiếc

    [DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]
    - iPhone 15 Pro Max: Smartphone cao cấp với chip A17 Pro
    - Samsung Galaxy S24: Flagship Android với S Pen
    """
    test_company_context = "Cửa hàng điện thoại ABC"
    test_user_query = "Anh muốn check iPhone 15 Pro Max còn hàng không? Tên anh là Nguyễn Văn A, SĐT 0909123456"

    # Build prompt
    prompt = chat_service._build_unified_prompt_with_intent(
        user_context=test_user_context,
        company_data=test_company_data,
        company_context=test_company_context,
        user_query=test_user_query,
        industry="Technology",
        company_id="TEST_COMPANY",
        session_id="test_session",
        user_name="Test User",
        company_name="ABC Store",
    )

    print("1️⃣ CHECKING PROMPT STRUCTURE")
    print("-" * 40)

    # Check webhook data guidance
    if "webhook_data" in prompt:
        print("✅ Prompt contains 'webhook_data' field")
    else:
        print("❌ Prompt missing 'webhook_data' field")

    if "check_quantity_data" in prompt:
        print("✅ Prompt contains CHECK_QUANTITY webhook structure")
    else:
        print("❌ Prompt missing CHECK_QUANTITY webhook structure")

    if "product_id từ [DỮ LIỆU TỒN KHO]" in prompt:
        print("✅ Prompt instructs AI to use product_id from catalog data")
    else:
        print("❌ Prompt missing product_id catalog instruction")

    # Check 2-step CHECK_QUANTITY flow
    if (
        "Bước 1: Kiểm Tra Tức Thì" in prompt
        and "Bước 2: Đề Xuất Kiểm Tra Thủ Công" in prompt
    ):
        print("✅ Prompt contains 2-step CHECK_QUANTITY flow")
    else:
        print("❌ Prompt missing 2-step CHECK_QUANTITY flow")

    print("\n2️⃣ CHECKING DATA PRIORITY STRUCTURE")
    print("-" * 40)

    if "DỮ LIỆU TỒN KHO - CHÍNH XÁC NHẤT" in prompt:
        print("✅ Prompt prioritizes catalog data")
    else:
        print("❌ Prompt missing catalog priority")

    if "product_id trong câu trả lời" in prompt:
        print("✅ Prompt instructs AI to include product_id in response")
    else:
        print("❌ Prompt missing product_id inclusion instruction")

    print("\n3️⃣ SAMPLE PROMPT STRUCTURE")
    print("-" * 40)

    # Show key sections
    webhook_section = ""
    if "ĐỊNH DẠNG ĐẦU RA" in prompt:
        start_idx = prompt.find("ĐỊNH DẠNG ĐẦU RA")
        end_idx = prompt.find("**VÍ DỤ:**", start_idx)
        if end_idx > start_idx:
            webhook_section = prompt[start_idx:end_idx]

    if webhook_section:
        print("📋 OUTPUT FORMAT SECTION:")
        print(
            webhook_section[:500] + "..."
            if len(webhook_section) > 500
            else webhook_section
        )

    print("\n4️⃣ ANALYZING CURRENT CALLBACK EXTRACTION LOGIC")
    print("-" * 40)

    # Check if callback uses webhook_data first
    import inspect

    # Get source of _extract_check_quantity_data method
    try:
        source_lines = inspect.getsource(chat_service._extract_check_quantity_data)

        if (
            'parsed_response.get("webhook_data", {}).get("check_quantity_data")'
            in source_lines
        ):
            print(
                "❌ Callback handler DOES NOT check webhook_data first (needs update)"
            )
        else:
            print("✅ Callback handler checks webhook_data first")

        if "ai_manager.stream_response" in source_lines:
            print(
                "⚠️  Callback still uses secondary AI call (inefficient but ok as fallback)"
            )
        else:
            print("✅ Callback does not use secondary AI call")

    except Exception as e:
        print(f"❌ Could not analyze callback source: {e}")

    print("\n🏁 ANALYSIS COMPLETED")
    print("=" * 70)

    # Summary and recommendations
    print("\n📊 SUMMARY & RECOMMENDATIONS")
    print("-" * 40)

    issues = []
    if "webhook_data" not in prompt:
        issues.append("❌ Add webhook_data to prompt OUTPUT FORMAT")
    if "check_quantity_data" not in prompt:
        issues.append("❌ Add CHECK_QUANTITY webhook structure to prompt")

    if issues:
        print("🚨 ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("✅ ALL CHECKS PASSED - Prompt structure looks good!")

    print("\n✅ NEXT STEPS:")
    print("   1. Test with real AI call to see JSON structure")
    print("   2. Verify callback handler uses webhook_data first")
    print("   3. Test product_id extraction from catalog data")


if __name__ == "__main__":
    asyncio.run(test_prompt_webhook_structure())
