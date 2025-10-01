"""
Test New Chat Flow
Demonstrates how "New Chat" button works (like VS Code or ChatGPT)
"""

import asyncio
from src.services.user_manager import get_user_manager


async def test_new_chat_flow():
    """
    Simulate user clicking "New Chat" button multiple times
    Each click creates a fresh conversation with no history
    """
    print("=" * 60)
    print("Testing New Chat Flow (+ Button)")
    print("=" * 60)
    print()

    user_manager = get_user_manager()
    test_user_id = "test_new_chat_user_001"

    # Scenario 1: First Chat
    print("📝 Scenario 1: User starts first chat")
    print("-" * 60)

    # Frontend state
    conversation_id_1 = None  # ← null for new chat
    conversation_history_1 = []  # ← empty for new chat

    print(f"Frontend state:")
    print(f"  conversationId: {conversation_id_1}")
    print(f"  conversationHistory: {conversation_history_1}")
    print()

    # Simulate sending first message
    print("User sends: 'What is Python?'")
    conversation_id_1 = f"chat_{test_user_id}_first"

    await user_manager.save_conversation(
        user_id=test_user_id,
        conversation_id=conversation_id_1,
        messages=[],
        ai_provider="deepseek",
        metadata={"apiType": "chat"},
    )

    await user_manager.add_message_to_conversation(
        conversation_id=conversation_id_1,
        user_id=test_user_id,
        role="user",
        content="What is Python?",
    )

    await user_manager.add_message_to_conversation(
        conversation_id=conversation_id_1,
        user_id=test_user_id,
        role="assistant",
        content="Python is a high-level programming language...",
    )

    print(f"✅ Created conversation: {conversation_id_1}")
    print()

    # Continue same conversation
    print("User continues same chat: 'How do I install it?'")
    print(f"Frontend state:")
    print(f"  conversationId: {conversation_id_1}  ← Same ID")
    print(f"  conversationHistory: [user, assistant, ...]  ← Has context")
    print()

    await user_manager.add_message_to_conversation(
        conversation_id=conversation_id_1,
        user_id=test_user_id,
        role="user",
        content="How do I install it?",
    )

    await user_manager.add_message_to_conversation(
        conversation_id=conversation_id_1,
        user_id=test_user_id,
        role="assistant",
        content="You can install Python from python.org...",
    )

    print("✅ Added to same conversation (with context)")
    print()
    print()

    # Scenario 2: New Chat Button
    print("📝 Scenario 2: User clicks [+ New Chat] button")
    print("-" * 60)

    # Frontend resets state
    conversation_id_2 = None  # ← Reset to null
    conversation_history_2 = []  # ← Clear history

    print(f"Frontend resets:")
    print(f"  conversationId: {conversation_id_2}  ← Reset to null")
    print(f"  conversationHistory: {conversation_history_2}  ← Clear history")
    print(f"  UI: Clear chat messages")
    print()

    # User starts completely new topic
    print("User sends: 'What is JavaScript?' (NEW TOPIC)")
    conversation_id_2 = f"chat_{test_user_id}_second"

    await user_manager.save_conversation(
        user_id=test_user_id,
        conversation_id=conversation_id_2,
        messages=[],
        ai_provider="deepseek",
        metadata={"apiType": "chat"},
    )

    await user_manager.add_message_to_conversation(
        conversation_id=conversation_id_2,
        user_id=test_user_id,
        role="user",
        content="What is JavaScript?",
    )

    await user_manager.add_message_to_conversation(
        conversation_id=conversation_id_2,
        user_id=test_user_id,
        role="assistant",
        content="JavaScript is a programming language for web browsers...",
    )

    print(f"✅ Created NEW conversation: {conversation_id_2}")
    print(f"   (No context from previous Python chat)")
    print()
    print()

    # Scenario 3: Another New Chat
    print("📝 Scenario 3: User clicks [+ New Chat] again")
    print("-" * 60)

    conversation_id_3 = None
    conversation_history_3 = []

    print(f"Frontend resets again:")
    print(f"  conversationId: {conversation_id_3}")
    print(f"  conversationHistory: {conversation_history_3}")
    print()

    print("User sends: 'Explain Docker' (ANOTHER NEW TOPIC)")
    conversation_id_3 = f"chat_{test_user_id}_third"

    await user_manager.save_conversation(
        user_id=test_user_id,
        conversation_id=conversation_id_3,
        messages=[],
        ai_provider="deepseek",
        metadata={"apiType": "chat"},
    )

    await user_manager.add_message_to_conversation(
        conversation_id=conversation_id_3,
        user_id=test_user_id,
        role="user",
        content="Explain Docker",
    )

    await user_manager.add_message_to_conversation(
        conversation_id=conversation_id_3,
        user_id=test_user_id,
        role="assistant",
        content="Docker is a containerization platform...",
    )

    print(f"✅ Created ANOTHER NEW conversation: {conversation_id_3}")
    print()
    print()

    # Show all conversations
    print("📋 Scenario 4: View all conversations (sidebar)")
    print("-" * 60)
    conversations = await user_manager.get_user_conversations(
        user_id=test_user_id, limit=10, offset=0
    )

    print(f"Found {len(conversations)} conversations:")
    for i, conv in enumerate(conversations, 1):
        print(f"\n  {i}. {conv['conversation_id']}")
        print(f"     Messages: {len(conv.get('messages', []))}")
        last_msg = conv.get("messages", [])[-1] if conv.get("messages") else {}
        last_content = last_msg.get("content", "N/A")
        print(f"     Last: {last_content[:50]}...")

    print()
    print()

    # Summary
    print("=" * 60)
    print("Summary - New Chat Flow")
    print("=" * 60)
    print()
    print("✅ Key Points:")
    print("   1. New Chat → Set conversationId = null")
    print("   2. New Chat → Set conversationHistory = []")
    print("   3. Backend auto-generates new conversationId")
    print("   4. Each chat is independent (no cross-context)")
    print("   5. Works exactly like VS Code / ChatGPT")
    print()
    print("📝 Frontend Implementation:")
    print("   function handleNewChatButton() {")
    print("     currentConversationId = null;")
    print("     conversationHistory = [];")
    print("     clearChatUI();")
    print("   }")
    print()


if __name__ == "__main__":
    asyncio.run(test_new_chat_flow())
