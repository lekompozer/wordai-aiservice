#!/usr/bin/env python3
"""
Test individual components of chat stream endpoint
Kiểm tra từng component của endpoint chat stream
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.models.unified_models import (
    UnifiedChatRequest,
    Industry,
    Language,
    UserInfo,
    UserSource,
)
from src.services.unified_chat_service import unified_chat_service


async def test_comprehensive_hybrid_search():
    """Test comprehensive hybrid search function"""
    print("🔍 Testing comprehensive hybrid search...")

    try:
        company_id = "abc_insurance_001"
        query = "bảo hiểm xe ô tô"

        # Test the hybrid search method directly
        search_results = await unified_chat_service._hybrid_search_company_data(
            company_id=company_id, query=query, limit=3, score_threshold=0.6
        )

        print(f"✅ Search completed: {len(search_results)} results")
        for i, result in enumerate(search_results, 1):
            print(f"   {i}. Content: {result.get('content_for_rag', '')[:100]}...")
            print(f"      Score: {result.get('score', 0):.3f}")
            print(f"      Type: {result.get('data_type', 'unknown')}")
            print()

        return True

    except Exception as e:
        print(f"❌ Hybrid search test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_company_basic_info():
    """Test company basic info retrieval"""
    print("🏢 Testing company basic info retrieval...")

    try:
        company_id = "abc_insurance_001"

        basic_info = await unified_chat_service._get_company_basic_info(company_id)

        print(f"✅ Basic info retrieved: {len(basic_info)} characters")
        if basic_info:
            print("📄 Basic info content:")
            print("-" * 40)
            print(basic_info)
            print("-" * 40)
        else:
            print("⚠️ No basic info found")

        return True

    except Exception as e:
        print(f"❌ Basic info test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_user_context():
    """Test user context retrieval"""
    print("👤 Testing user context retrieval...")

    try:
        device_id = "test_device_001"

        user_context = await unified_chat_service._get_user_context_optimized(device_id)

        print(f"✅ User context retrieved: {len(user_context)} characters")
        print(f"📄 User context: {user_context}")

        return True

    except Exception as e:
        print(f"❌ User context test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_company_context():
    """Test company context retrieval"""
    print("🏭 Testing company context retrieval...")

    try:
        company_id = "abc_insurance_001"

        company_context = await unified_chat_service._get_company_context_optimized(
            company_id
        )

        print(f"✅ Company context retrieved: {len(company_context)} characters")
        if company_context and len(company_context) > 50:
            print("📄 Company context preview:")
            print("-" * 40)
            print(
                company_context[:300] + "..."
                if len(company_context) > 300
                else company_context
            )
            print("-" * 40)
        else:
            print(f"📄 Company context: {company_context}")

        return True

    except Exception as e:
        print(f"❌ Company context test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_prompt_building():
    """Test prompt building with logging"""
    print("📝 Testing prompt building with logging...")

    try:
        # Mock data
        user_context = "New user - no previous conversation history."
        company_data = "Sample company data from hybrid search"
        company_context = "Sample company context"
        user_query = "Tôi muốn hỏi về bảo hiểm xe ô tô"
        industry = "insurance"
        company_id = "abc_insurance_001"
        session_id = "test_session_001"

        prompt = unified_chat_service._build_unified_prompt_with_intent(
            user_context=user_context,
            company_data=company_data,
            company_context=company_context,
            user_query=user_query,
            industry=industry,
            company_id=company_id,
            session_id=session_id,
        )

        print(f"✅ Prompt built: {len(prompt)} characters")
        print("📄 Prompt preview:")
        print("-" * 40)
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        print("-" * 40)

        # Check if log file was created
        import glob

        log_files = glob.glob(
            "/Users/user/Code/ai-chatbot-rag/logs/prompt/prompt_*.txt"
        )
        if log_files:
            latest_log = max(log_files, key=os.path.getctime)
            print(f"📂 Prompt logged to: {os.path.basename(latest_log)}")
        else:
            print("⚠️ No prompt log file found")

        return True

    except Exception as e:
        print(f"❌ Prompt building test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_full_request_object():
    """Test with a full UnifiedChatRequest object"""
    print("📦 Testing with full UnifiedChatRequest object...")

    try:
        # Create a proper request object
        request = UnifiedChatRequest(
            message="Tôi muốn hỏi về gói bảo hiểm xe hơi",
            company_id="abc_insurance_001",
            industry=Industry.INSURANCE,
            language=Language.VIETNAMESE,
            session_id="test_session_full",
            user_info=UserInfo(
                user_id="test_user_001",
                name="Test User",
                device_id="test_device_001",
                source=UserSource.CHATDEMO,
            ),
            context={},
        )

        print(f"✅ Request object created")
        print(f"   Company: {request.company_id}")
        print(f"   Industry: {request.industry.value}")
        print(f"   Message: {request.message}")
        print(f"   Session: {request.session_id}")

        # Test parallel data fetching (Step 1-3)
        print("\n📊 Testing parallel data fetching...")

        company_data, user_context, company_context = await asyncio.gather(
            unified_chat_service._hybrid_search_company_data_optimized(
                request.company_id, request.message
            ),
            unified_chat_service._get_user_context_optimized(
                request.user_info.device_id
            ),
            unified_chat_service._get_company_context_optimized(request.company_id),
            return_exceptions=True,
        )

        print(f"✅ Parallel fetching completed")
        print(f"   Company data: {len(str(company_data))} chars")
        print(f"   User context: {len(str(user_context))} chars")
        print(f"   Company context: {len(str(company_context))} chars")

        # Handle exceptions
        if isinstance(company_data, Exception):
            print(f"   ⚠️ Company data error: {company_data}")
            company_data = "No relevant company data found."

        if isinstance(user_context, Exception):
            print(f"   ⚠️ User context error: {user_context}")
            user_context = "New user - no previous conversation history."

        if isinstance(company_context, Exception):
            print(f"   ⚠️ Company context error: {company_context}")
            company_context = "No company context available."

        # Test prompt building
        print("\n📝 Testing prompt building...")
        prompt = unified_chat_service._build_unified_prompt_with_intent(
            user_context=user_context,
            company_data=company_data,
            company_context=company_context,
            user_query=request.message,
            industry=request.industry.value,
            company_id=request.company_id,
            session_id=request.session_id,
        )

        print(f"✅ Full pipeline test completed")
        print(f"   Final prompt: {len(prompt)} characters")

        return True

    except Exception as e:
        print(f"❌ Full request test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all component tests"""
    print("=" * 80)
    print("TESTING CHAT STREAM ENDPOINT COMPONENTS")
    print("=" * 80)

    tests = [
        ("Comprehensive Hybrid Search", test_comprehensive_hybrid_search),
        ("Company Basic Info", test_company_basic_info),
        ("User Context", test_user_context),
        ("Company Context", test_company_context),
        ("Prompt Building", test_prompt_building),
        ("Full Request Pipeline", test_full_request_object),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
        print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
        if result:
            passed += 1

    print(f"\nTotal: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("\n🎉 All tests passed! Endpoint should work correctly.")
    else:
        print(f"\n⚠️ {len(results) - passed} tests failed. Check logs above.")

    # Check prompt logs
    print(f"\n📂 Prompt logs location: /Users/user/Code/ai-chatbot-rag/logs/prompt/")


if __name__ == "__main__":
    asyncio.run(main())
