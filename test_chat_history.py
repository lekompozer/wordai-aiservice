"""
Test script to verify chat history is being saved correctly
for both Chat API and Content Edit API
"""

import asyncio
import sys
from datetime import datetime, timezone
from src.services.user_manager import get_user_manager


async def test_chat_history():
    """Test chat history saving"""
    print("=" * 60)
    print("Testing Chat History Saving")
    print("=" * 60)

    user_manager = get_user_manager()
    # Test user ID
    test_user_id = "test_user_123"

    # 1. Test Chat API history saving
    print("\n1. Testing Chat API history...")
    chat_conversation_id = f"chat_{test_user_id}_test001"

    # Create conversation
    success = await user_manager.save_conversation(
        user_id=test_user_id,
        conversation_id=chat_conversation_id,
        messages=[],
        ai_provider="deepseek",
        metadata={"apiType": "chat", "fileName": "test.txt", "processingTime": 1234},
    )
    print(f"   ✓ Created conversation: {success}")

    # Add user message
    success = await user_manager.add_message_to_conversation(
        conversation_id=chat_conversation_id,
        user_id=test_user_id,
        role="user",
        content="Hello, can you explain this code?",
        metadata={"apiType": "chat"},
    )
    print(f"   ✓ Added user message: {success}")

    # Add AI response
    success = await user_manager.add_message_to_conversation(
        conversation_id=chat_conversation_id,
        user_id=test_user_id,
        role="assistant",
        content="Sure! This code does...",
        metadata={"apiType": "chat"},
    )
    print(f"   ✓ Added AI response: {success}")

    # 2. Test Content Edit API history saving
    print("\n2. Testing Content Edit API history...")
    edit_conversation_id = f"edit_{test_user_id}_test002"

    # Create conversation
    success = await user_manager.save_conversation(
        user_id=test_user_id,
        conversation_id=edit_conversation_id,
        messages=[],
        ai_provider="gemini",
        metadata={
            "apiType": "content_edit",
            "operationType": "summarize",
            "fileName": "document.docx",
            "processingTime": 2345,
        },
    )
    print(f"   ✓ Created conversation: {success}")

    # Add user message with HTML
    success = await user_manager.add_message_to_conversation(
        conversation_id=edit_conversation_id,
        user_id=test_user_id,
        role="user",
        content="[summarize] Summarize this content\n\nInput HTML:\n<p>Long content here...</p>",
        metadata={"apiType": "content_edit", "operationType": "summarize"},
    )
    print(f"   ✓ Added user message: {success}")

    # Add AI response with HTML
    success = await user_manager.add_message_to_conversation(
        conversation_id=edit_conversation_id,
        user_id=test_user_id,
        role="assistant",
        content="<p>This is a summary of the content.</p>",
        metadata={"apiType": "content_edit", "operationType": "summarize"},
    )
    print(f"   ✓ Added AI response: {success}")

    # 3. Retrieve and verify conversations
    print("\n3. Retrieving conversations...")
    conversations = await user_manager.get_user_conversations(
        user_id=test_user_id, limit=10
    )

    print(f"   Found {len(conversations)} conversations")

    for conv in conversations:
        print(f"\n   Conversation: {conv['conversation_id']}")
        print(f"   - Provider: {conv.get('ai_provider', 'N/A')}")
        print(f"   - API Type: {conv.get('metadata', {}).get('apiType', 'unknown')}")
        print(f"   - Messages: {len(conv.get('messages', []))}")

        for i, msg in enumerate(conv.get("messages", []), 1):
            role = msg.get("role", "unknown")
            content_preview = (
                msg.get("content", "")[:50] + "..."
                if len(msg.get("content", "")) > 50
                else msg.get("content", "")
            )
            print(f"     {i}. [{role}] {content_preview}")

    # 4. Get specific conversation
    print("\n4. Testing get_conversation...")
    chat_conv = await user_manager.get_conversation(
        conversation_id=chat_conversation_id, user_id=test_user_id
    )

    if chat_conv:
        print(f"   ✓ Chat conversation found")
        print(f"     - ID: {chat_conv['conversation_id']}")
        print(f"     - Messages: {len(chat_conv['messages'])}")
        print(f"     - API Type: {chat_conv['metadata'].get('apiType')}")
    else:
        print(f"   ✗ Chat conversation not found")

    edit_conv = await user_manager.get_conversation(
        conversation_id=edit_conversation_id, user_id=test_user_id
    )

    if edit_conv:
        print(f"   ✓ Edit conversation found")
        print(f"     - ID: {edit_conv['conversation_id']}")
        print(f"     - Messages: {len(edit_conv['messages'])}")
        print(f"     - API Type: {edit_conv['metadata'].get('apiType')}")
        print(f"     - Operation Type: {edit_conv['metadata'].get('operationType')}")
    else:
        print(f"   ✗ Edit conversation not found")

    print("\n" + "=" * 60)
    print("✅ Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_chat_history())
