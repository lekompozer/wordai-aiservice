#!/usr/bin/env python3
"""
Test script for conversation history and deduplication improvements
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.services.unified_chat_service import UnifiedChatService


async def test_deduplication():
    """Test the new deduplication function"""
    print("🧪 Testing deduplication function...")

    service = UnifiedChatService()

    # Create mock search results with duplicates
    mock_results = [
        {
            "content_for_rag": "AIA – Khỏe Trọn Vẹn. Bảo hiểm liên kết chung. Bảo vệ tài chính trước rủi ro tử vong.",
            "data_type": "bao_hiem",
            "score": 0.749,
        },
        {
            "content_for_rag": "AIA – Khỏe Trọn Vẹn. Bảo hiểm liên kết chung. Bảo vệ tài chính trước rủi ro tử vong.",
            "data_type": "bao_hiem",
            "score": 0.736,
        },
        {
            "content_for_rag": "AIA Vitality - Chương trình thưởng cho lối sống khỏe mạnh",
            "data_type": "chuong_trinh",
            "score": 0.720,
        },
        {
            "content_for_rag": "AIA – Khỏe Trọn Vẹn Bảo hiểm liên kết chung Bảo vệ tài chính trước rủi ro tử vong",
            "data_type": "bao_hiem",
            "score": 0.722,
        },
        {
            "content_for_rag": "Bảo hiểm xe máy AIA - Bảo vệ phương tiện giao thông",
            "data_type": "bao_hiem_xe",
            "score": 0.680,
        },
    ]

    print(f"📥 Input: {len(mock_results)} results")
    for i, result in enumerate(mock_results):
        print(
            f"   {i+1}. [{result['data_type']}] {result['content_for_rag'][:50]}... (score: {result['score']})"
        )

    # Test deduplication
    deduplicated = service._deduplicate_search_results(
        mock_results, similarity_threshold=0.7
    )

    print(f"\n📤 Output: {len(deduplicated)} results after deduplication")
    for i, result in enumerate(deduplicated):
        print(
            f"   {i+1}. [{result['data_type']}] {result['content_for_rag'][:50]}... (score: {result['score']})"
        )

    print(
        f"\n✅ Deduplication test completed: {len(mock_results)} -> {len(deduplicated)} results"
    )


def test_user_identification():
    """Test user identification logic"""
    print("\n🧪 Testing user identification logic...")

    # Mock request objects with different user info scenarios
    test_cases = [
        {
            "name": "Authenticated user",
            "user_info": {
                "user_id": "auth_user_123",
                "device_id": "device_456",
                "session_id": "session_789",
            },
            "expected_priority": "user_id",
        },
        {
            "name": "Anonymous user with session",
            "user_info": {
                "user_id": "unknown",
                "device_id": "device_456",
                "session_id": "session_789",
            },
            "expected_priority": "session_id",
        },
        {
            "name": "Anonymous user device only",
            "user_info": {
                "user_id": "unknown",
                "device_id": "device_456",
                "session_id": "unknown",
            },
            "expected_priority": "device_id",
        },
        {
            "name": "No valid identifiers",
            "user_info": {
                "user_id": "unknown",
                "device_id": "unknown",
                "session_id": "unknown",
            },
            "expected_priority": "none",
        },
    ]

    for case in test_cases:
        print(f"\n📋 Test case: {case['name']}")
        user_info = case["user_info"]

        # Simulate priority logic
        conversation_keys = []
        if user_info["user_id"] != "unknown":
            conversation_keys.append(("user_id", user_info["user_id"]))
        if user_info["session_id"] != "unknown":
            conversation_keys.append(("session_id", user_info["session_id"]))
        if user_info["device_id"] != "unknown":
            conversation_keys.append(("device_id", user_info["device_id"]))

        if conversation_keys:
            primary_key = conversation_keys[0]
            print(f"   ✅ Primary key: {primary_key[0]} = {primary_key[1]}")
            print(f"   📝 All keys: {conversation_keys}")
        else:
            print(f"   ❌ No valid keys found")

    print(f"\n✅ User identification test completed")


if __name__ == "__main__":
    asyncio.run(test_deduplication())
    test_user_identification()
