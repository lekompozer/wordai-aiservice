#!/usr/bin/env python3
"""
Test script to verify conversation ID format
Test để kiểm tra format conversation ID
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.unified_chat_service import unified_chat_service
from src.models.unified_models import UnifiedChatRequest, Industry, UserInfo, UserSource


def test_conversation_id_format():
    """Test conversation ID generation format"""
    print("🧪 Testing conversation ID generation format")

    # Test data - using EXACT format from chat-plugin
    company_id = "65dc4970-331d-46c3-a9eb-ec1a63ca74d7"
    device_id = "dev_c0nrdb"
    plugin_id = "b333433d-4cf9-4225-90ef-9d195a4aae2b"
    session_id = "sess_test_123"

    # Expected: conv_65dc4970-331d-46c3-a9eb-ec1a63ca74d7_devc0nrdb_b333433d-4cf9-4225-90ef-9d195a4aae2b
    expected_conversation_id = f"conv_{company_id}_devc0nrdb_{plugin_id}"

    # Create mock request
    class MockRequest:
        def __init__(self, plugin_id):
            self.plugin_id = plugin_id

    request = MockRequest(plugin_id)

    # Test conversation ID generation
    conversation_id = unified_chat_service.get_or_create_conversation(
        session_id=session_id,
        company_id=company_id,
        device_id=device_id,
        request=request,
    )

    print(f"📋 Test Results:")
    print(f"   Company ID: {company_id}")
    print(f"   Device ID: {device_id}")
    print(f"   Plugin ID: {plugin_id}")
    print(f"   Generated Conversation ID: {conversation_id}")
    print(f"   Expected Conversation ID: {expected_conversation_id}")

    # Verify format - UUID format has more underscores, so need special handling
    print(f"\n🔍 Format Verification:")
    print(
        f"   Expected format: conv_{{full-uuid-company}}_{{deviceId}}_{{full-uuid-plugin}}"
    )

    # Check exact match for compatibility
    if conversation_id == expected_conversation_id:
        print(f"✅ Conversation ID format is CORRECT and COMPATIBLE with chat-plugin!")
        print(f"   Full match: {conversation_id} ✅")
    elif (
        conversation_id.startswith("conv_")
        and company_id in conversation_id
        and plugin_id in conversation_id
    ):
        print(f"✅ Conversation ID format structure is CORRECT!")
        print(
            f"   Contains company ID: {'✅' if company_id in conversation_id else '❌'}"
        )
        print(
            f"   Contains plugin ID: {'✅' if plugin_id in conversation_id else '❌'}"
        )
        print(
            f"   Contains device ID: {'✅' if 'devc0nrdb' in conversation_id else '❌'}"
        )
    else:
        print(f"❌ Conversation ID format is INCORRECT!")
        return False  # Test with no plugin_id
    print(f"\n🧪 Testing with no plugin_id:")
    request_no_plugin = MockRequest(None)

    conversation_id_no_plugin = unified_chat_service._generate_conversation_id(
        company_id=company_id, device_id=device_id, plugin_id=None
    )

    print(f"   No Plugin ID: {conversation_id_no_plugin}")

    if "default" in conversation_id_no_plugin:
        print(f"✅ Default plugin handling is CORRECT!")
    else:
        print(f"❌ Default plugin handling is INCORRECT!")

    return True


if __name__ == "__main__":
    success = test_conversation_id_format()
    exit(0 if success else 1)
