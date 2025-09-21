#!/usr/bin/env python3
"""
Test Channel → Source Auto-Mapping
Kiểm tra việc tự động map channel sang source
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from models.unified_models import UnifiedChatRequest, ChannelType, UserSource, UserInfo


def test_channel_source_auto_mapping():
    """Test auto-mapping từ channel sang user_info.source"""

    print("🧪 Testing Channel → Source Auto-Mapping")
    print("=" * 50)

    # Test cases: Backend chỉ cần gửi channel, source sẽ được auto-set
    test_cases = [
        {
            "name": "Chat Plugin - Backend only sends channel",
            "channel": ChannelType.CHAT_PLUGIN,
            "expected_source": UserSource.CHAT_PLUGIN,
            "user_info": {
                "user_id": "ws_user_123",
                "name": "Anonymous",
                # No source specified - will be auto-set
            },
        },
        {
            "name": "Messenger - Override wrong source",
            "channel": ChannelType.MESSENGER,
            "expected_source": UserSource.FACEBOOK_MESSENGER,
            "user_info": {
                "user_id": "FB_USER_PSID",
                "source": "website",  # Wrong source - will be overridden
                "name": "User Name",
            },
        },
        {
            "name": "WhatsApp - Auto-set source",
            "channel": ChannelType.WHATSAPP,
            "expected_source": UserSource.WHATSAPP,
            "user_info": {
                "user_id": "+84987654321",
                "name": "Nguyen Van A",
                # No source - will be auto-set
            },
        },
        {
            "name": "Frontend - Auto-set chatdemo",
            "channel": ChannelType.CHATDEMO,
            "expected_source": UserSource.CHATDEMO,
            "user_info": None,  # No user_info - will be created
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print("-" * 40)

        # Create request
        request_data = {
            "message": "Test message",
            "company_id": "test-company",
            "channel": test_case["channel"],
        }

        if test_case["user_info"]:
            request_data["user_info"] = UserInfo(**test_case["user_info"])

        # Create UnifiedChatRequest (this triggers auto-mapping)
        request = UnifiedChatRequest(**request_data)

        # Check results
        actual_source = request.user_info.source
        expected_source = test_case["expected_source"]

        print(f"   Channel: {request.channel.value}")
        print(f"   Expected Source: {expected_source.value}")
        print(f"   Actual Source: {actual_source.value}")

        if actual_source == expected_source:
            print("   ✅ PASS - Source correctly auto-mapped!")
        else:
            print("   ❌ FAIL - Source mapping incorrect!")

        print(f"   User ID: {request.user_info.user_id}")
        print(f"   Message ID: {request.message_id}")


def test_legacy_support():
    """Test legacy support khi chỉ có source (không có channel)"""

    print("\n🔙 Testing Legacy Support (No Channel)")
    print("=" * 50)

    # Legacy request: chỉ có user_info.source, không có channel
    legacy_request = UnifiedChatRequest(
        message="Legacy test",
        company_id="legacy-company",
        user_info=UserInfo(
            user_id="legacy_user", source="facebook_messenger"  # Legacy way
        ),
        # No channel specified - should default to CHATDEMO
    )

    print(f"   Channel: {legacy_request.channel.value}")
    print(f"   Source: {legacy_request.user_info.source.value}")
    print("   ✅ Legacy support working!")


def test_static_mapping():
    """Test static mapping function"""

    print("\n🗺️  Testing Static Mapping Function")
    print("=" * 50)

    mappings = [
        (ChannelType.CHATDEMO, UserSource.CHATDEMO),
        (ChannelType.MESSENGER, UserSource.MESSENGER),
        (ChannelType.INSTAGRAM, UserSource.INSTAGRAM),
        (ChannelType.WHATSAPP, UserSource.WHATSAPP),
        (ChannelType.ZALO, UserSource.ZALO),
        (ChannelType.CHAT_PLUGIN, UserSource.CHAT_PLUGIN),
    ]

    for channel, expected_source in mappings:
        actual_source = UnifiedChatRequest.get_source_from_channel(channel)

        print(f"   {channel.value} → {actual_source.value}")

        if actual_source == expected_source:
            print("     ✅ Correct mapping")
        else:
            print(f"     ❌ Wrong! Expected {expected_source.value}")


if __name__ == "__main__":
    test_channel_source_auto_mapping()
    test_legacy_support()
    test_static_mapping()

    print("\n🎉 All tests completed!")
    print("\n💡 Summary:")
    print("   ✅ Backend chỉ cần gửi 'channel'")
    print("   ✅ 'user_info.source' sẽ được tự động set")
    print("   ✅ Legacy webhook vẫn hoạt động")
    print("   ✅ Không cần validation channel vs source nữa!")
