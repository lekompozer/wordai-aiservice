#!/usr/bin/env python3
"""
Test Token Management for Chat History
Kiểm tra logic giới hạn token cho lịch sử chat
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


# Import the function từ chat_routes
def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation: 1 token ≈ 4 characters)"""
    return len(text) // 4


def limit_conversation_history(
    existing_messages,
    new_messages,
    max_history_tokens: int = 24000,
    reserved_tokens: int = 8000,
):
    """
    Limit conversation history to fit within token constraints
    """
    # Calculate tokens for new messages (these are mandatory)
    new_tokens = sum(estimate_tokens(msg.get("content", "")) for msg in new_messages)

    # Available tokens for existing history
    available_history_tokens = max_history_tokens - min(
        new_tokens, reserved_tokens // 2
    )

    if available_history_tokens <= 0:
        print(f"⚠️ New messages too long ({new_tokens} tokens), using minimal history")
        return new_messages

    # Work backwards through existing messages to fit within token limit
    limited_history = []
    current_tokens = 0

    # Start from most recent messages and work backwards
    for message in reversed(existing_messages):
        message_tokens = estimate_tokens(message.get("content", ""))

        if current_tokens + message_tokens <= available_history_tokens:
            limited_history.insert(0, message)  # Insert at beginning to maintain order
            current_tokens += message_tokens
        else:
            break

    # Combine limited history with new messages
    final_messages = limited_history + new_messages

    total_tokens = sum(
        estimate_tokens(msg.get("content", "")) for msg in final_messages
    )

    print(
        f"📊 Token management: History={len(limited_history)} msgs ({current_tokens} tokens), "
        f"New={len(new_messages)} msgs ({new_tokens} tokens), "
        f"Total={total_tokens} tokens"
    )

    return final_messages


def test_token_management():
    """Test different scenarios of token management"""

    print("🧪 Testing Token Management Logic\n")

    # Scenario 1: Normal conversation with manageable history
    print("🔹 Scenario 1: Normal conversation")
    existing_messages = [
        {"role": "user", "content": "Hello, how are you today?"},
        {
            "role": "assistant",
            "content": "I'm doing well, thank you for asking! How can I help you?",
        },
        {"role": "user", "content": "Can you tell me about Python programming?"},
        {
            "role": "assistant",
            "content": "Python is a versatile programming language known for its simplicity and readability. It's great for beginners and widely used in web development, data science, AI, and automation.",
        },
        {"role": "user", "content": "What are some popular Python frameworks?"},
        {
            "role": "assistant",
            "content": "Some popular Python frameworks include Django and Flask for web development, FastAPI for building APIs, NumPy and Pandas for data science, and TensorFlow/PyTorch for machine learning.",
        },
    ]

    new_messages = [{"role": "user", "content": "How do I install Python packages?"}]

    result = limit_conversation_history(existing_messages, new_messages)
    print(f"Result: {len(result)} total messages\n")

    # Scenario 2: Very long conversation history
    print("🔹 Scenario 2: Very long conversation history")
    long_content = (
        "This is a very long message that contains lots of information about various topics. "
        * 200
    )  # ~25k characters = ~6k tokens

    long_existing_messages = [
        {"role": "user", "content": long_content},
        {"role": "assistant", "content": long_content},
        {"role": "user", "content": long_content},
        {"role": "assistant", "content": long_content},
        {"role": "user", "content": long_content},
        {"role": "assistant", "content": long_content},
    ]

    new_messages = [{"role": "user", "content": "Quick question about the above"}]

    result = limit_conversation_history(long_existing_messages, new_messages)
    print(
        f"Result: {len(result)} total messages (truncated from {len(long_existing_messages)} history)\n"
    )

    # Scenario 3: Very long new message
    print("🔹 Scenario 3: Very long new message")
    existing_messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    very_long_new_message = (
        "This is an extremely long user query that goes on and on. " * 500
    )  # ~35k characters = ~8.7k tokens

    new_messages = [{"role": "user", "content": very_long_new_message}]

    result = limit_conversation_history(existing_messages, new_messages)
    print(f"Result: {len(result)} total messages\n")

    # Scenario 4: Empty history
    print("🔹 Scenario 4: Empty history")
    existing_messages = []

    new_messages = [{"role": "user", "content": "This is the first message"}]

    result = limit_conversation_history(existing_messages, new_messages)
    print(f"Result: {len(result)} total messages\n")

    print("✅ Token management tests completed!")


if __name__ == "__main__":
    test_token_management()
