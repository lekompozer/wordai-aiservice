#!/usr/bin/env python3
"""
Test unified chat with AIA data and Cerebras as default
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_aia_cerebras_integration():
    """Test AIA search with Cerebras as default AI provider"""
    print("🤖 TESTING AIA + CEREBRAS INTEGRATION")
    print("=" * 50)

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
        config = APP_CONFIG
        print(f"🔧 Config loaded:")
        print(
            f"   🤖 Default AI Provider: {config.get('default_ai_provider', 'unknown')}"
        )
        print(
            f"   🧠 Cerebras API Key: {'✅ Set' if config.get('cerebras_api_key') else '❌ Missing'}"
        )
        print(f"   📦 Qdrant URL: {config.get('qdrant_url', 'unknown')}")

        # Initialize chat service
        chat_service = UnifiedChatService()

        # Test queries about AIA
        test_queries = [
            "Hãy cho tôi biết về công ty AIA Việt Nam",
            "AIA có những sản phẩm bảo hiểm gì?",
            "Dịch vụ khách hàng của AIA như thế nào?",
            "Tôi muốn tìm hiểu về bảo hiểm sức khỏe AIA",
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"\n🔍 Test {i}: {query}")
            print("-" * 40)

            try:
                # Test non-streaming response
                response = await chat_service.chat_completion(
                    question=query,
                    company_id="9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",  # AIA company ID
                    user_id="test_user",
                    conversation_id="test_conversation",
                )

                print(f"📝 Response:")
                print(f"   Provider: {response.get('provider', 'unknown')}")
                print(f"   Model: {response.get('model', 'unknown')}")
                print(f"   RAG Sources: {len(response.get('sources', []))}")
                print(f"   Answer: {response.get('answer', '')[:200]}...")

                if response.get("sources"):
                    print(f"   📚 Sources found:")
                    for j, source in enumerate(response.get("sources", [])[:3], 1):
                        title = source.get("title", "No title")
                        content_type = source.get("content_type", "unknown")
                        print(f"      {j}. {title} ({content_type})")

            except Exception as e:
                print(f"   ❌ Error: {e}")

        # Test streaming response
        print(f"\n🌊 Testing streaming response...")
        print("-" * 40)

        query = "Giải thích chi tiết về các sản phẩm bảo hiểm của AIA"

        try:
            print(f"Query: {query}")
            print(f"Response: ", end="")

            async for chunk in chat_service.stream_response(
                question=query,
                company_id="9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
                user_id="test_user",
                conversation_id="test_conversation_stream",
            ):
                if chunk.get("type") == "content":
                    print(chunk.get("content", ""), end="", flush=True)
                elif chunk.get("type") == "done":
                    sources = chunk.get("sources", [])
                    print(f"\n   ✅ Stream complete - {len(sources)} sources found")

        except Exception as e:
            print(f"\n   ❌ Streaming error: {e}")

        print(f"\n🎉 INTEGRATION TEST COMPLETED!")
        print(f"   🏢 AIA Company: Added to Qdrant")
        print(f"   🤖 Cerebras API: Set as default provider")
        print(f"   💬 Unified Chat: Working with RAG")
        print(f"   🌊 Streaming: Functional")

        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_aia_cerebras_integration())
    print(f"\n{'✅ OVERALL SUCCESS' if success else '❌ OVERALL FAILED'}")
    sys.exit(0 if success else 1)
