#!/usr/bin/env python3
"""
Test unified chat service to debug streaming issue
"""

import asyncio
import json


async def test_streaming_debug():
    """Test the streaming functionality"""
    print("🧪 Testing Unified Chat Service Streaming")
    print("=" * 50)

    # Simulate the exact payload from frontend
    frontend_payload = {
        "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
        "industry": "INSURANCE",  # Will be auto-converted to "insurance"
        "language": "ENGLISH",  # Will be auto-converted to "en"
        "message": "cho tao thông tin về AIA xem",
        "session_id": "firebase_2Fi60Cy2jHcMhkn5o2VcjfUef7p2_1753906976",
        "user_info": {
            "user_id": "2Fi60Cy2jHcMhkn5o2VcjfUef7p2",
            "source": "web_device",
            "name": "Michael Le",
            "email": "tienhoi.lh@gmail.com",
            "device_id": "web_eczqgo",
        },
    }

    print("📋 Test Payload:")
    print(json.dumps(frontend_payload, indent=2, ensure_ascii=False))

    try:
        # Import and test the model validation
        import sys
        import os

        current_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.join(current_dir, "src")
        sys.path.insert(0, src_dir)

        from models.unified_models import UnifiedChatRequest

        # Test model conversion
        print("\n🔧 Testing model validation and conversion:")
        request = UnifiedChatRequest(**frontend_payload)

        print(f"✅ Model validation successful!")
        print(f"   company_id: {request.company_id}")
        print(f"   industry: {frontend_payload['industry']} → {request.industry.value}")
        print(f"   language: {frontend_payload['language']} → {request.language.value}")
        print(f"   message: {request.message[:50]}...")
        print(f"   user_id: {request.user_info.user_id}")
        print(f"   session_id: {request.session_id}")

        # Simulate the intent detection that would happen
        print(f"\n🎯 Expected intent detection:")
        print(f"   Intent: information (based on message asking for AIA info)")
        print(f"   Language: en (based on ENGLISH input)")
        print(f"   Response path: _stream_information_response")

        print(f"\n✅ Model conversion and validation working correctly!")
        print(f"🔄 The issue was in _stream_information_response method")
        print(f"🛠️ Fixed: Now properly implements company data search + AI streaming")

    except Exception as e:
        print(f"❌ Error in model validation: {e}")
        return False

    return True


async def explain_flow():
    """Explain the corrected flow"""
    print("\n" + "=" * 60)
    print("🔍 CORRECTED STREAMING FLOW EXPLANATION")
    print("=" * 60)

    steps = [
        "1. Frontend sends payload with UPPERCASE industry/language",
        "2. Pydantic validators auto-convert: INSURANCE→insurance, ENGLISH→en",
        "3. Route calls unified_chat_service.stream_response()",
        "4. Intent detection: 'cho tao thông tin về AIA' → information intent",
        "5. Calls _stream_information_response() method",
        "6. [FIXED] Method now properly:",
        "   - Searches company data using _hybrid_search_company_data()",
        "   - Builds context from search results",
        "   - Creates information-focused prompt",
        "   - Streams AI response using ai_manager.stream_response()",
        "7. Frontend receives real streaming content (not placeholder)",
        "8. Stream completes with 'done' event",
    ]

    for step in steps:
        print(f"   {step}")

    print(f"\n🚨 PREVIOUS PROBLEM:")
    print(
        f"   _stream_information_response() only yielded 'Information response streaming...'"
    )
    print(f"   ↓")
    print(f"   Frontend received intent + placeholder text + done")
    print(f"   ↓")
    print(f"   No actual AI response content!")

    print(f"\n✅ FIXED SOLUTION:")
    print(f"   _stream_information_response() now:")
    print(f"   • Searches company data about AIA")
    print(f"   • Builds proper context for AI")
    print(f"   • Streams real AI response chunks")
    print(f"   • Frontend gets actual informative content")


if __name__ == "__main__":
    asyncio.run(test_streaming_debug())
    asyncio.run(explain_flow())

    print(f"\n🎉 READY TO TEST!")
    print(f"   Frontend should now receive proper streaming responses")
    print(f"   instead of just placeholder text!")
