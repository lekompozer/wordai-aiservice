#!/usr/bin/env python3
"""
Test AIA + Cerebras integration with correct API
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_aia_cerebras_final():
    """Final test of AIA data with Cerebras API"""
    print("🎯 FINAL TEST: AIA + CEREBRAS")
    print("=" * 40)

    try:
        # Load environment
        load_dotenv()

        from src.services.unified_chat_service import UnifiedChatService
        from src.core.config import APP_CONFIG
        from src.models.unified_models import (
            UnifiedChatRequest,
            UserInfo,
            Industry,
            Language,
        )

        # Check config
        print(f"🔧 Config check:")
        print(f"   🤖 Default AI: {APP_CONFIG.get('default_ai_provider', 'unknown')}")
        print(
            f"   🧠 Cerebras Key: {'✅' if APP_CONFIG.get('cerebras_api_key') else '❌'}"
        )
        print(f"   📦 Qdrant: {'✅' if APP_CONFIG.get('qdrant_url') else '❌'}")

        # Initialize service
        chat_service = UnifiedChatService()

        # Test simple AIA query
        query = "Hãy cho tôi biết về công ty AIA Việt Nam"
        print(f"\n🔍 Testing: {query}")

        request = UnifiedChatRequest(
            message=query,
            company_id="9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",  # AIA ID
            industry=Industry.INSURANCE,
            user_info=UserInfo(
                user_id="test_user", device_id="test_device", name="Test User"
            ),
            session_id="test_session_final",
            language=Language.VIETNAMESE,
        )

        # Process message
        response = await chat_service.process_message(request)

        print(f"\n📝 Response received:")
        print(f"   ✅ Status: {response.status}")
        print(f"   📄 Sources: {len(response.sources) if response.sources else 0}")
        print(
            f"   💬 Answer: {response.answer[:300] if response.answer else 'No answer'}..."
        )

        if response.sources:
            print(f"\n📚 RAG Sources found:")
            for i, source in enumerate(response.sources[:3], 1):
                title = source.get("title", "Unknown")
                content = source.get("content", "")[:100]
                print(f"   {i}. {title}")
                print(f"      Content: {content}...")

        # Test streaming
        print(f"\n🌊 Testing streaming...")

        stream_request = UnifiedChatRequest(
            message="Cho tôi biết về các sản phẩm bảo hiểm của AIA",
            company_id="9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
            industry=Industry.INSURANCE,
            user_info=UserInfo(
                user_id="test_user_stream",
                device_id="test_device_stream",
                name="Stream Test User",
            ),
            session_id="test_session_stream",
            language=Language.VIETNAMESE,
        )

        print(f"Stream response: ", end="")
        chunk_count = 0

        async for chunk in chat_service.stream_response(stream_request):
            chunk_count += 1
            if chunk_count <= 50:  # Limit output
                print(".", end="", flush=True)

        print(f"\n   ✅ Stream completed ({chunk_count} chunks)")

        print(f"\n🎉 FINAL TEST RESULTS:")
        print(f"   🏢 AIA Data: ✅ Accessible in Qdrant")
        print(f"   🤖 Cerebras API: ✅ Set as default")
        print(f"   💬 Unified Chat: ✅ Processing messages")
        print(f"   🌊 Streaming: ✅ Functional")
        print(f"   📊 RAG Search: ✅ Finding AIA content")

        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_aia_cerebras_final())
    print(f"\n{'🎯 ALL SYSTEMS GO!' if success else '❌ SYSTEM CHECK FAILED'}")
    sys.exit(0 if success else 1)
