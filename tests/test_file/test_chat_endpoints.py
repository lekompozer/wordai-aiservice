#!/usr/bin/env python3
"""
Test Chat Endpoints
Test script cho các AI chat endpoints với Firebase authentication
"""

import asyncio
import aiohttp
import json
import uuid
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
AUTH_TOKEN = "dev-token"  # Development token from firebase_auth.py


async def test_get_providers():
    """Test get available providers endpoint"""
    print("\n🔍 Testing GET /api/chat/providers")

    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with session.get(
                f"{BASE_URL}/api/chat/providers", headers=headers
            ) as response:
                print(f"Status: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Available providers: {len(data['providers'])}")

                    for provider in data["providers"]:
                        print(
                            f"   - {provider['name']} ({provider['id']}) - {provider['category']}"
                        )

                    return data["providers"]
                else:
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    return []

        except Exception as e:
            print(f"❌ Request failed: {e}")
            return []


async def test_chat_stream(provider_id: str):
    """Test streaming chat endpoint"""
    print(f"\n💬 Testing POST /api/chat/stream with {provider_id}")

    # Test messages
    test_messages = [
        {
            "role": "system",
            "content": "You are a helpful AI assistant. Keep responses concise and friendly.",
        },
        {
            "role": "user",
            "content": "Hello! Can you tell me about artificial intelligence in a few sentences?",
        },
    ]

    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Content-Type": "application/json",
        }

        payload = {
            "provider": provider_id,
            "messages": test_messages,
            "conversation_id": None,  # Will create new conversation
            "temperature": 0.7,
            "max_tokens": 200,
            "stream": True,
        }

        try:
            async with session.post(
                f"{BASE_URL}/api/chat/stream", headers=headers, json=payload
            ) as response:
                print(f"Status: {response.status}")

                if response.status == 200:
                    print("✅ Streaming response:")
                    full_response = ""
                    conversation_id = None

                    async for line in response.content:
                        if line:
                            line_text = line.decode("utf-8").strip()

                            if line_text.startswith("data: "):
                                data_text = line_text[6:]  # Remove 'data: '

                                if data_text == "[DONE]":
                                    print("\n✅ Stream completed")
                                    break

                                try:
                                    data = json.loads(data_text)

                                    if data.get("type") == "metadata":
                                        conversation_id = data.get("conversation_id")
                                        print(f"📝 Conversation ID: {conversation_id}")

                                    elif data.get("type") == "content":
                                        content = data.get("content", "")
                                        print(content, end="", flush=True)
                                        full_response += content

                                    elif data.get("type") == "complete":
                                        print(
                                            f"\n💾 Conversation saved: {data.get('saved')}"
                                        )

                                    elif data.get("type") == "error":
                                        print(f"\n❌ Error: {data.get('message')}")

                                except json.JSONDecodeError:
                                    continue

                    print(f"\n📊 Full response length: {len(full_response)} characters")
                    return conversation_id

                else:
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    return None

        except Exception as e:
            print(f"❌ Request failed: {e}")
            return None


async def test_get_conversations():
    """Test get conversations endpoint"""
    print("\n📚 Testing GET /api/chat/conversations")

    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with session.get(
                f"{BASE_URL}/api/chat/conversations?limit=10", headers=headers
            ) as response:
                print(f"Status: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Found {data['total']} conversations")

                    for conv in data["conversations"]:
                        print(
                            f"   - {conv['conversation_id'][:8]}... "
                            f"({conv['message_count']} messages, "
                            f"{conv['last_message'][:50] if conv['last_message'] else 'No messages'}...)"
                        )

                    return data["conversations"]
                else:
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    return []

        except Exception as e:
            print(f"❌ Request failed: {e}")
            return []


async def test_get_conversation_detail(conversation_id: str):
    """Test get conversation detail endpoint"""
    print(f"\n📖 Testing GET /api/chat/conversations/{conversation_id}")

    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with session.get(
                f"{BASE_URL}/api/chat/conversations/{conversation_id}", headers=headers
            ) as response:
                print(f"Status: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Conversation detail retrieved")
                    print(f"   - Messages: {len(data.get('messages', []))}")
                    print(f"   - AI Provider: {data.get('ai_provider')}")
                    print(f"   - Updated: {data.get('updated_at')}")

                    return data
                else:
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    return None

        except Exception as e:
            print(f"❌ Request failed: {e}")
            return None


async def test_chat_stats():
    """Test chat statistics endpoint"""
    print("\n📊 Testing GET /api/chat/stats")

    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with session.get(
                f"{BASE_URL}/api/chat/stats", headers=headers
            ) as response:
                print(f"Status: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Chat statistics:")
                    print(
                        f"   - Total conversations: {data.get('total_conversations', 0)}"
                    )

                    if data.get("longest_conversation"):
                        longest = data["longest_conversation"]
                        print(
                            f"   - Longest conversation: {longest.get('message_count')} messages "
                            f"({longest.get('ai_provider')})"
                        )

                    if data.get("provider_usage"):
                        print("   - Provider usage:")
                        for provider, count in data["provider_usage"].items():
                            print(f"     * {provider}: {count} conversations")

                    return data
                else:
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    return None

        except Exception as e:
            print(f"❌ Request failed: {e}")
            return None


async def main():
    """Run all tests"""
    print("🚀 Starting AI Chat Endpoints Test")
    print(f"Base URL: {BASE_URL}")
    print(f"Using auth token: {AUTH_TOKEN}")
    print("=" * 60)

    # Test 1: Get available providers
    providers = await test_get_providers()

    if not providers:
        print("\n❌ No providers available, stopping tests")
        return

    # Test 2: Test streaming chat with first available provider
    provider = providers[0]
    conversation_id = await test_chat_stream(provider["id"])

    # Test 3: Get conversations
    conversations = await test_get_conversations()

    # Test 4: Get conversation detail (if we have a conversation)
    if conversation_id:
        await test_get_conversation_detail(conversation_id)
    elif conversations:
        await test_get_conversation_detail(conversations[0]["conversation_id"])

    # Test 5: Get chat statistics
    await test_chat_stats()

    print("\n" + "=" * 60)
    print("✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
