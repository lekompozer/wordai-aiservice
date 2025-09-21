#!/usr/bin/env python3
"""
Test exact prompt với DeepSeek để debug response
"""
import asyncio
import json
import sys

sys.path.append("/Users/user/Code/ai-chatbot-rag")

from src.providers.ai_provider_manager import AIProviderManager
from dotenv import load_dotenv
import os


async def test_exact_prompt():
    """Test exact prompt with DeepSeek"""

    print("🧪 TESTING EXACT PROMPT WITH DEEPSEEK")
    print("=" * 60)

    # Load environment
    load_dotenv("development.env")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    chatgpt_api_key = os.getenv("CHATGPT_API_KEY")

    # Load messages from file
    try:
        with open("deepseek_prompt_test.json", "r", encoding="utf-8") as f:
            messages = json.load(f)
        print(f"📋 Loaded {len(messages)} messages from deepseek_prompt_test.json")
    except FileNotFoundError:
        print(
            "❌ deepseek_prompt_test.json not found. Run debug_prompt_reconstruction.py first"
        )
        return

    # Initialize AI Manager
    ai_manager = AIProviderManager(deepseek_api_key, chatgpt_api_key)

    print(f"📝 Message sizes:")
    for i, msg in enumerate(messages):
        print(f"  {i+1}. {msg['role']}: {len(msg['content'])} chars")

    print(f"\n🚀 Calling DeepSeek with exact prompt...")

    try:
        # Call DeepSeek async
        response = await ai_manager._deepseek_completion_async(messages)

        print(f"✅ Response received: {len(response)} characters")
        print("📄 Raw response:")
        print(response[:1000] + "..." if len(response) > 1000 else response)

        # Try parsing JSON
        try:
            # Clean response first
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            elif cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # Find JSON boundaries
            start_idx = cleaned_response.find("{")
            end_idx = cleaned_response.rfind("}")
            if start_idx != -1 and end_idx != -1:
                cleaned_response = cleaned_response[start_idx : end_idx + 1]

            print(f"\n🧽 Cleaned response: {len(cleaned_response)} chars")

            json_data = json.loads(cleaned_response)
            print("✅ Valid JSON response!")
            print(f"📊 Top-level keys: {list(json_data.keys())}")

            if "structured_data" in json_data:
                structured = json_data["structured_data"]
                print(f"📊 Structured data keys: {list(structured.keys())}")

                if "products" in structured:
                    products = structured["products"]
                    print(f"🛍️ Found {len(products)} products")

                    if products:
                        print("📦 First 3 products:")
                        for i, product in enumerate(products[:3]):
                            name = product.get("name", "N/A")
                            price = product.get("price", 0)
                            category = product.get("category", "N/A")
                            print(f"  {i+1}. {name} - {price:,} VND ({category})")
                    else:
                        print("📦 Products array is empty")

            if "raw_content" in json_data:
                raw_content = json_data["raw_content"]
                print(f"📄 Raw content: {len(str(raw_content))} chars")
                if raw_content:
                    print(f"📄 Raw content preview: {str(raw_content)[:200]}...")
                else:
                    print("📄 Raw content is empty!")

        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {e}")
            print(f"📄 Response preview: {response[:500]}...")

        # Save response for analysis
        with open("deepseek_test_response.txt", "w", encoding="utf-8") as f:
            f.write(response)
        print(f"\n💾 Saved response to deepseek_test_response.txt")

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback

        print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(test_exact_prompt())
