#!/usr/bin/env python3
"""
Test Cerebras AI integration with unified chat service
Testing both intent detection and streaming responses
"""

import asyncio
import json
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_cerebras_integration():
    """Test Cerebras AI integration"""
    print("🧠 CEREBRAS AI INTEGRATION TEST")
    print("=" * 50)

    try:
        # Test 1: Direct Cerebras Client
        print("\n1. Testing Direct Cerebras Client")
        print("-" * 30)

        from src.clients.cerebras_client import CerebrasClient

        # Initialize client
        api_key = "csk-6535mtwp6j9v6f9825eewe432rc4j24xrcrw6tj5m2cx5f32"
        cerebras_client = CerebrasClient(api_key)

        # Test simple completion
        messages = [
            {
                "role": "user",
                "content": "Xin chào! Bạn có thể giới thiệu về AIA Việt Nam không?",
            }
        ]

        print("✅ Testing non-streaming completion...")
        response = await cerebras_client.chat_completion(messages)
        print(f"Response length: {len(response)} characters")
        print(f"First 200 chars: {response[:200]}...")

        # Test streaming
        print("\n✅ Testing streaming completion...")
        chunks = []
        async for chunk in cerebras_client.chat_completion_stream(messages):
            chunks.append(chunk)
            if len(chunks) <= 5:  # Show first few chunks
                print(f"Chunk {len(chunks)}: '{chunk}'")

        full_response = "".join(chunks)
        print(f"Stream complete - Total length: {len(full_response)} characters")

        # Test 2: AI Provider Manager Integration
        print("\n\n2. Testing AI Provider Manager Integration")
        print("-" * 40)

        from src.providers.ai_provider_manager import AIProviderManager

        ai_manager = AIProviderManager(
            deepseek_api_key="test", chatgpt_api_key="test", cerebras_api_key=api_key
        )

        # Test available providers
        providers = await ai_manager.get_available_providers()
        print(f"Available providers: {providers}")

        # Test Cerebras streaming through AI manager
        print("\n✅ Testing Cerebras through AI manager...")
        chunks = []
        async for chunk in ai_manager.chat_completion_stream_with_reasoning(
            messages, provider="cerebras"
        ):
            chunks.append(chunk)
            if len(chunks) <= 3:
                print(f"AI Manager Chunk {len(chunks)}: '{chunk}'")

        full_response = "".join(chunks)
        print(
            f"AI Manager stream complete - Total length: {len(full_response)} characters"
        )

        # Test 3: Unified Chat Service Integration
        print("\n\n3. Testing Unified Chat Service Integration")
        print("-" * 45)

        from src.models.unified_models import UnifiedChatRequest
        from src.services.unified_chat_service import UnifiedChatService

        # Create request
        request = UnifiedChatRequest(
            message="Hãy cho tôi biết về sản phẩm bảo hiểm của AIA Việt Nam",
            company_id="aia_vietnam",  # Add required company_id
            user_info={
                "user_id": "test_user",
                "session_id": "test_session",
                "language": "vi",
                "industry": "insurance",
            },
            provider="cerebras",  # Specify Cerebras provider
        )

        print(f"Request: {request.message}")
        print(f"Provider: {request.provider}")

        # Initialize service and test
        service = UnifiedChatService()

        print("\n✅ Testing streaming through unified service...")
        chunks = []
        async for chunk in service.stream_response(request):
            chunks.append(chunk)
            # Show first few chunks for debugging
            if len(chunks) <= 5:
                print(f"Service Chunk {len(chunks)}: '{chunk}'")

            # Break if we get [DONE] signal
            if chunk.strip() == "[DONE]":
                break

        print(f"Unified service complete - Total chunks: {len(chunks)}")

        # Test 4: Intent Detection with Cerebras
        print("\n\n4. Testing Intent Detection with Cerebras")
        print("-" * 42)

        from src.services.intent_detector import IntentDetector

        # Initialize intent detector
        intent_detector = IntentDetector()

        # Test intent detection
        intent_result = await intent_detector.detect_intent(
            "Tôi muốn tìm hiểu về gói bảo hiểm sức khỏe của AIA", provider="cerebras"
        )

        print(f"Intent detected: {intent_result}")

        print("\n🎉 ALL CEREBRAS TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 50)

        return True

    except Exception as e:
        print(f"\n❌ ERROR during Cerebras testing: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_cerebras_integration())

    if success:
        print("\n✅ Cerebras integration is working correctly!")
        sys.exit(0)
    else:
        print("\n❌ Cerebras integration test failed!")
        sys.exit(1)
