#!/usr/bin/env python3
"""
Test Live AI Models - Kiểm tra trực tiếp các model có sẵn từ từng provider
"""

import os
import asyncio
import sys

sys.path.append("src")

# Load environment variables
with open(".env", "r") as f:
    for line in f:
        if line.strip() and not line.startswith("#") and "=" in line:
            key, value = line.strip().split("=", 1)
            value = value.strip("\"'")
            os.environ[key] = value


async def test_openai_models():
    """Test OpenAI models"""
    print("🔍 Testing OpenAI Models...")
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=os.getenv("CHATGPT_API_KEY"))

        # List available models
        models = await client.models.list()

        # Filter for chat models
        chat_models = []
        for model in models.data:
            model_id = model.id
            if any(
                keyword in model_id.lower()
                for keyword in ["gpt-4", "gpt-3.5", "chatgpt"]
            ):
                chat_models.append(
                    {
                        "id": model_id,
                        "created": model.created,
                        "owned_by": model.owned_by,
                    }
                )

        print(f"  ✅ Found {len(chat_models)} OpenAI chat models:")
        for model in sorted(chat_models, key=lambda x: x["id"]):
            print(f"    📝 {model['id']} (by {model['owned_by']})")

        return chat_models

    except Exception as e:
        print(f"  ❌ OpenAI Error: {e}")
        return []


async def test_deepseek_models():
    """Test DeepSeek models"""
    print("\n🔍 Testing DeepSeek Models...")
    try:
        import openai

        client = openai.AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
        )

        # List available models
        models = await client.models.list()

        deepseek_models = []
        for model in models.data:
            deepseek_models.append(
                {"id": model.id, "created": model.created, "owned_by": model.owned_by}
            )

        print(f"  ✅ Found {len(deepseek_models)} DeepSeek models:")
        for model in sorted(deepseek_models, key=lambda x: x["id"]):
            print(f"    📝 {model['id']} (by {model['owned_by']})")

        return deepseek_models

    except Exception as e:
        print(f"  ❌ DeepSeek Error: {e}")
        return []


async def test_cerebras_models():
    """Test Cerebras models"""
    print("\n🔍 Testing Cerebras Models...")
    try:
        from cerebras.cloud.sdk import Cerebras

        client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))

        # List available models
        models = client.models.list()

        cerebras_models = []
        for model in models.data:
            cerebras_models.append(
                {
                    "id": model.id,
                    "created": getattr(model, "created", "unknown"),
                    "owned_by": getattr(model, "owned_by", "cerebras"),
                }
            )

        print(f"  ✅ Found {len(cerebras_models)} Cerebras models:")
        for model in sorted(cerebras_models, key=lambda x: x["id"]):
            print(f"    📝 {model['id']} (by {model['owned_by']})")

        return cerebras_models

    except Exception as e:
        print(f"  ❌ Cerebras Error: {e}")
        return []


async def test_gemini_models():
    """Test Gemini models"""
    print("\n🔍 Testing Gemini Models...")
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

        # List available models
        models = genai.list_models()

        gemini_models = []
        for model in models:
            # Only include models that support generateContent
            if "generateContent" in model.supported_generation_methods:
                gemini_models.append(
                    {
                        "id": model.name.split("/")[-1],  # Extract model name
                        "display_name": model.display_name,
                        "description": (
                            model.description[:100] + "..."
                            if len(model.description) > 100
                            else model.description
                        ),
                    }
                )

        print(f"  ✅ Found {len(gemini_models)} Gemini models:")
        for model in sorted(gemini_models, key=lambda x: x["id"]):
            print(f"    📝 {model['id']} - {model['display_name']}")
            print(f"      📋 {model['description']}")

        return gemini_models

    except Exception as e:
        print(f"  ❌ Gemini Error: {e}")
        return []


async def test_simple_chat_requests():
    """Test simple chat requests to verify models work"""
    print("\n🧪 Testing Simple Chat Requests...")

    test_message = "Hello, please respond with just 'OK' to confirm you work."

    # Test OpenAI
    print("\n  Testing OpenAI...")
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=os.getenv("CHATGPT_API_KEY"))

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": test_message}],
            max_tokens=10,
        )
        print(f"    ✅ GPT-4o: {response.choices[0].message.content.strip()}")

    except Exception as e:
        print(f"    ❌ OpenAI test failed: {e}")

    # Test DeepSeek
    print("\n  Testing DeepSeek...")
    try:
        import openai

        client = openai.AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
        )

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": test_message}],
            max_tokens=10,
        )
        print(f"    ✅ DeepSeek Chat: {response.choices[0].message.content.strip()}")

    except Exception as e:
        print(f"    ❌ DeepSeek test failed: {e}")

    # Test Cerebras
    print("\n  Testing Cerebras...")
    try:
        from cerebras.cloud.sdk import Cerebras

        client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))

        response = client.chat.completions.create(
            model="qwen-3-235b-a22b-instruct-2507",
            messages=[{"role": "user", "content": test_message}],
            max_tokens=10,
        )
        print(f"    ✅ Qwen 235B: {response.choices[0].message.content.strip()}")

    except Exception as e:
        print(f"    ❌ Cerebras test failed: {e}")

    # Test Gemini
    print("\n  Testing Gemini...")
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(test_message)
        print(f"    ✅ Gemini 2.0 Flash: {response.text.strip()}")

    except Exception as e:
        print(f"    ❌ Gemini test failed: {e}")


async def main():
    """Main function"""
    print("🚀 Live AI Models Test")
    print("=" * 60)
    print("This script will check what models are actually available")
    print("from each AI provider using their APIs directly.")
    print("=" * 60)

    # Test each provider
    openai_models = await test_openai_models()
    deepseek_models = await test_deepseek_models()
    cerebras_models = await test_cerebras_models()
    gemini_models = await test_gemini_models()

    # Test simple requests
    await test_simple_chat_requests()

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"OpenAI Models: {len(openai_models)}")
    print(f"DeepSeek Models: {len(deepseek_models)}")
    print(f"Cerebras Models: {len(cerebras_models)}")
    print(f"Gemini Models: {len(gemini_models)}")

    # Generate recommended model list
    print("\n🎯 RECOMMENDED MODEL LIST FOR FRONTEND:")
    print("=" * 60)

    recommended = []

    if openai_models:
        # Recommend latest GPT-4 models
        gpt4_models = [m for m in openai_models if "gpt-4" in m["id"].lower()]
        if gpt4_models:
            latest_gpt4 = sorted(gpt4_models, key=lambda x: x["id"])[-1]
            recommended.append(
                {
                    "id": "openai",
                    "name": "GPT-4o",
                    "model": latest_gpt4["id"],
                    "category": "General AI",
                }
            )

    if deepseek_models:
        recommended.append(
            {
                "id": "deepseek",
                "name": "DeepSeek Chat",
                "model": "deepseek-chat",
                "category": "Fast & Efficient",
            }
        )

    if cerebras_models:
        # Find Qwen models
        qwen_models = [m for m in cerebras_models if "qwen" in m["id"].lower()]
        if qwen_models:
            for model in qwen_models:
                if "instruct" in model["id"]:
                    recommended.append(
                        {
                            "id": "qwen_235b_instruct",
                            "name": "Qwen 235B Instruct",
                            "model": model["id"],
                            "category": "Large Scale",
                        }
                    )
                elif "coder" in model["id"]:
                    recommended.append(
                        {
                            "id": "qwen_480b_coder",
                            "name": "Qwen 480B Coder",
                            "model": model["id"],
                            "category": "Programming",
                        }
                    )
                elif "thinking" in model["id"]:
                    recommended.append(
                        {
                            "id": "qwen_235b_thinking",
                            "name": "Qwen 235B Thinking",
                            "model": model["id"],
                            "category": "Reasoning",
                        }
                    )

    if gemini_models:
        # Find latest Gemini models
        flash_models = [m for m in gemini_models if "flash" in m["id"].lower()]
        if flash_models:
            latest_flash = sorted(flash_models, key=lambda x: x["id"])[-1]
            recommended.append(
                {
                    "id": "gemini_flash",
                    "name": "Gemini 2.0 Flash",
                    "model": latest_flash["id"],
                    "category": "Multimodal",
                }
            )

    for rec in recommended:
        print(f"  📝 {rec['id']}: {rec['name']} ({rec['model']}) - {rec['category']}")


if __name__ == "__main__":
    asyncio.run(main())
