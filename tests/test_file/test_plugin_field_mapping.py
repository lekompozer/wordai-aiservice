#!/usr/bin/env python3
"""
Test Plugin Field Mapping for camelCase → snake_case
"""
import json
from src.models.unified_models import UnifiedChatRequest, ChannelType


def test_plugin_field_mapping():
    """Test that frontend camelCase pluginId and customerDomain map to snake_case"""

    # Frontend payload with camelCase field names (như trong log)
    frontend_payload = {
        "message": "test message",
        "company_id": "test-company",
        "channel": "chat-plugin",
        "pluginId": "test-plugin-123",  # camelCase from frontend
        "customerDomain": "https://test-domain.com",  # camelCase from frontend
        "user_info": {
            "user_id": "test-user",
            "device_id": "test-device",
            "source": "chat-plugin",
        },
    }

    print("🧪 Testing Plugin Field Mapping...")
    print(f"Frontend payload: {json.dumps(frontend_payload, indent=2)}")

    try:
        # Parse với Pydantic model
        request = UnifiedChatRequest(**frontend_payload)

        print(f"\n✅ Successfully parsed request!")
        print(f"📋 Model field values:")
        print(f"   plugin_id: {request.plugin_id}")
        print(f"   customer_domain: {request.customer_domain}")
        print(f"   channel: {request.channel}")

        # Verify values are correctly mapped
        assert request.plugin_id == "test-plugin-123"
        assert request.customer_domain == "https://test-domain.com"
        assert request.channel == ChannelType.CHAT_PLUGIN

        print(f"\n✅ Field mapping test PASSED!")
        print(f"   camelCase 'pluginId' → snake_case 'plugin_id' ✅")
        print(f"   camelCase 'customerDomain' → snake_case 'customer_domain' ✅")

        return True

    except Exception as e:
        print(f"\n❌ Field mapping test FAILED: {e}")
        return False


def test_snake_case_compatibility():
    """Test that snake_case field names still work"""

    # Backend-style payload with snake_case field names
    backend_payload = {
        "message": "test message",
        "company_id": "test-company",
        "channel": "chat-plugin",
        "plugin_id": "backend-plugin-456",  # snake_case
        "customer_domain": "https://backend-domain.com",  # snake_case
        "user_info": {
            "user_id": "backend-user",
            "device_id": "backend-device",
            "source": "chat-plugin",
        },
    }

    print(f"\n🧪 Testing snake_case compatibility...")
    print(f"Backend payload: {json.dumps(backend_payload, indent=2)}")

    try:
        # Parse với Pydantic model
        request = UnifiedChatRequest(**backend_payload)

        print(f"\n✅ Successfully parsed request!")
        print(f"📋 Model field values:")
        print(f"   plugin_id: {request.plugin_id}")
        print(f"   customer_domain: {request.customer_domain}")
        print(f"   channel: {request.channel}")

        # Verify values are correctly mapped
        assert request.plugin_id == "backend-plugin-456"
        assert request.customer_domain == "https://backend-domain.com"
        assert request.channel == ChannelType.CHAT_PLUGIN

        print(f"\n✅ Snake_case compatibility test PASSED!")
        print(f"   snake_case 'plugin_id' → 'plugin_id' ✅")
        print(f"   snake_case 'customer_domain' → 'customer_domain' ✅")

        return True

    except Exception as e:
        print(f"\n❌ Snake_case compatibility test FAILED: {e}")
        return False


if __name__ == "__main__":
    print(
        "🧪 Testing Plugin Field Mapping with Frontend camelCase → Backend snake_case..."
    )

    success1 = test_plugin_field_mapping()
    success2 = test_snake_case_compatibility()

    if success1 and success2:
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"   Frontend camelCase fields will now map correctly to Backend")
        print(f"   pluginId → plugin_id ✅")
        print(f"   customerDomain → customer_domain ✅")
    else:
        print(f"\n❌ SOME TESTS FAILED!")
        exit(1)
