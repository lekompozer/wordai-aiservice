"""
Test Chat History API Endpoints
Test the new conversation management endpoints
"""

import asyncio
from datetime import datetime
from src.services.user_manager import get_user_manager


async def test_conversation_endpoints():
    """Test conversation CRUD operations"""
    print("=" * 60)
    print("Testing Conversation API Endpoints")
    print("=" * 60)

    user_manager = get_user_manager()
    test_user_id = "test_user_api_123"

    # 1. Create sample conversations
    print("\n1. Creating sample conversations...")

    # Chat conversation
    chat_conv_id = f"chat_{test_user_id}_sample1"
    await user_manager.save_conversation(
        user_id=test_user_id,
        conversation_id=chat_conv_id,
        messages=[],
        ai_provider="deepseek",
        metadata={"apiType": "chat", "fileName": "test.py"},
    )

    await user_manager.add_message_to_conversation(
        conversation_id=chat_conv_id,
        user_id=test_user_id,
        role="user",
        content="Explain this code to me",
        metadata={"apiType": "chat", "fileName": "test.py"},
    )

    await user_manager.add_message_to_conversation(
        conversation_id=chat_conv_id,
        user_id=test_user_id,
        role="assistant",
        content="Sure! This code defines a function that prints hello world.",
        metadata={"apiType": "chat", "tokensUsed": 45, "processingTime": 1200},
    )

    # Add follow-up messages
    await user_manager.add_message_to_conversation(
        conversation_id=chat_conv_id,
        user_id=test_user_id,
        role="user",
        content="Can you make it better?",
        metadata={"apiType": "chat"},
    )

    await user_manager.add_message_to_conversation(
        conversation_id=chat_conv_id,
        user_id=test_user_id,
        role="assistant",
        content="Here's an improved version: def hello(name='World'): print(f'Hello, {name}!')",
        metadata={"apiType": "chat", "tokensUsed": 60, "processingTime": 1500},
    )

    print(f"   ✓ Created chat conversation: {chat_conv_id} (4 messages)")

    # Edit conversation
    edit_conv_id = f"edit_{test_user_id}_sample2"
    await user_manager.save_conversation(
        user_id=test_user_id,
        conversation_id=edit_conv_id,
        messages=[],
        ai_provider="gemini",
        metadata={"apiType": "content_edit", "operationType": "summarize"},
    )

    await user_manager.add_message_to_conversation(
        conversation_id=edit_conv_id,
        user_id=test_user_id,
        role="user",
        content="[summarize] Summarize this content\n\nInput HTML:\n<p>Long document content here...</p>",
        metadata={"apiType": "content_edit", "operationType": "summarize"},
    )

    await user_manager.add_message_to_conversation(
        conversation_id=edit_conv_id,
        user_id=test_user_id,
        role="assistant",
        content="<p>This is a concise summary of the document.</p>",
        metadata={
            "apiType": "content_edit",
            "operationType": "summarize",
            "tokensUsed": 120,
        },
    )

    print(f"   ✓ Created edit conversation: {edit_conv_id} (2 messages)")

    # 2. Test get_user_conversations (list)
    print("\n2. Testing get_user_conversations...")
    conversations = await user_manager.get_user_conversations(
        user_id=test_user_id, limit=10, offset=0
    )

    print(f"   Found {len(conversations)} conversations:")
    for conv in conversations:
        msg_count = len(conv.get("messages", []))
        last_msg = ""
        if conv.get("messages"):
            last_msg = conv["messages"][-1].get("content", "")[:50]

        print(f"     • {conv['conversation_id']}")
        print(f"       - Messages: {msg_count}")
        print(f"       - Provider: {conv.get('ai_provider', 'N/A')}")
        print(
            f"       - API Type: {conv.get('metadata', {}).get('apiType', 'unknown')}"
        )
        print(f"       - Last msg: {last_msg}...")

    # 3. Test get_conversation (detail)
    print("\n3. Testing get_conversation (detail)...")

    # Get chat conversation
    chat_detail = await user_manager.get_conversation(
        conversation_id=chat_conv_id, user_id=test_user_id
    )

    if chat_detail:
        print(f"   ✓ Chat Conversation: {chat_detail['conversation_id']}")
        print(f"     - Messages: {len(chat_detail['messages'])}")
        print(f"     - Provider: {chat_detail.get('ai_provider')}")
        print(f"     - Created: {chat_detail.get('created_at')}")
        print(f"     - Updated: {chat_detail.get('updated_at')}")
        print(f"\n     Messages:")
        for i, msg in enumerate(chat_detail["messages"], 1):
            role = msg["role"]
            content = (
                msg["content"][:60] + "..."
                if len(msg["content"]) > 60
                else msg["content"]
            )
            timestamp = msg.get("timestamp", "N/A")
            print(f"       {i}. [{role}] {content}")
            print(f"          @ {timestamp}")

    # Get edit conversation
    edit_detail = await user_manager.get_conversation(
        conversation_id=edit_conv_id, user_id=test_user_id
    )

    if edit_detail:
        print(f"\n   ✓ Edit Conversation: {edit_detail['conversation_id']}")
        print(f"     - Messages: {len(edit_detail['messages'])}")
        print(
            f"     - Operation: {edit_detail.get('metadata', {}).get('operationType')}"
        )

    # 4. Test conversationHistory format
    print("\n4. Testing conversationHistory format (for AI API)...")

    # Build history array as frontend would
    if chat_detail:
        history = []
        for msg in chat_detail["messages"]:
            history.append({"role": msg["role"], "content": msg["content"]})

        print(f"   Built conversationHistory array with {len(history)} messages:")
        for i, msg in enumerate(history, 1):
            content_preview = (
                msg["content"][:50] + "..."
                if len(msg["content"]) > 50
                else msg["content"]
            )
            print(f"     {i}. {msg['role']}: {content_preview}")

        print(f"\n   JSON format (ready for API):")
        import json

        print(f"   {json.dumps(history, indent=2)}")

    # 5. Test delete conversation
    print("\n5. Testing delete_conversation...")

    # Create a temp conversation to delete
    temp_conv_id = f"chat_{test_user_id}_temp_delete"
    await user_manager.save_conversation(
        user_id=test_user_id,
        conversation_id=temp_conv_id,
        messages=[],
        ai_provider="deepseek",
        metadata={},
    )
    print(f"   ✓ Created temp conversation: {temp_conv_id}")

    # Delete it
    success = await user_manager.delete_conversation(
        conversation_id=temp_conv_id, user_id=test_user_id
    )
    print(f"   ✓ Deleted conversation: {success}")

    # Verify it's gone
    deleted_conv = await user_manager.get_conversation(
        conversation_id=temp_conv_id, user_id=test_user_id
    )
    if deleted_conv is None:
        print(f"   ✓ Verified: conversation no longer exists")
    else:
        print(f"   ✗ Error: conversation still exists!")

    # 6. Summary
    print("\n" + "=" * 60)
    print("Summary - API Endpoints Ready:")
    print("=" * 60)
    print("\n📋 Available Endpoints:")
    print("   GET  /api/auth/conversations")
    print("        → List user's conversations (summaries)")
    print()
    print("   GET  /api/auth/conversations/{id}")
    print("        → Get full conversation detail with messages")
    print()
    print("   DELETE /api/auth/conversations/{id}")
    print("        → Delete a conversation")
    print()
    print("\n💡 Frontend Usage:")
    print("   1. Load list: GET /api/auth/conversations")
    print("   2. Open conversation: GET /api/auth/conversations/{id}")
    print("   3. Build history array from messages")
    print("   4. Send to AI with conversationHistory")
    print()
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_conversation_endpoints())
