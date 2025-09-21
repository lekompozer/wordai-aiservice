#!/usr/bin/env python3
"""
Test All Selected AI Models - Complete List
Test all 12 verified working models with Vũng Tàu tourism question
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test question
TEST_QUESTION = """Bạn có thể giới thiệu cho tôi 5 địa điểm du lịch nổi tiếng ở Vũng Tàu không?
Hãy trả lời ngắn gọn, mỗi địa điểm chỉ cần 1-2 câu mô tả."""

# All 12 verified working models
SELECTED_MODELS = {
    "openai": [
        {
            "id": "chatgpt_4o_latest",
            "name": "ChatGPT-4o Latest",
            "model": "chatgpt-4o-latest",
            "category": "latest",
        },
        {
            "id": "gpt_4o_mini_2024_07_18",
            "name": "GPT-4o Mini 2024-07-18",
            "model": "gpt-4o-mini-2024-07-18",
            "category": "fast",
        },
        {
            "id": "o1_preview_2024_09_12",
            "name": "o1-preview 2024-09-12",
            "model": "o1-preview-2024-09-12",
            "category": "reasoning",
        },
    ],
    "deepseek": [
        {
            "id": "deepseek_chat",
            "name": "DeepSeek Chat",
            "model": "deepseek-chat",
            "category": "general",
        },
        {
            "id": "deepseek_reasoner",
            "name": "DeepSeek Reasoner",
            "model": "deepseek-reasoner",
            "category": "reasoning",
        },
    ],
    "cerebras": [
        {
            "id": "qwen_235b_instruct",
            "name": "Qwen 235B Instruct",
            "model": "qwen-3-235b-a22b-instruct-2507",
            "category": "instruct",
        },
        {
            "id": "qwen_235b_thinking",
            "name": "Qwen 235B Thinking",
            "model": "qwen-3-235b-a22b-thinking-2507",
            "category": "thinking",
        },
        {
            "id": "qwen_480b_coder",
            "name": "Qwen 480B Coder",
            "model": "qwen-3-coder-480b",
            "category": "coding",
        },
        {
            "id": "qwen_32b",
            "name": "Qwen 32B",
            "model": "qwen-3-32b",
            "category": "general",
        },
        {
            "id": "llama_70b",
            "name": "Llama 3.3 70B",
            "model": "llama-3.3-70b",
            "category": "general",
        },
        {
            "id": "llama_8b",
            "name": "Llama 3.1 8B",
            "model": "llama3.1-8b",
            "category": "lightweight",
        },
    ],
    "gemini": [
        {
            "id": "gemini_flash",
            "name": "Gemini 2.5 Flash",
            "model": "gemini-2.5-flash",
            "category": "fast",
        }
    ],
}


async def test_openai_models():
    """Test OpenAI models"""
    print("\n🔍 Testing OpenAI Models...")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.getenv("CHATGPT_API_KEY"))

        results = []
        for model_info in SELECTED_MODELS["openai"]:
            try:
                print(f"  📝 Testing {model_info['name']} ({model_info['model']})...")

                response = await client.chat.completions.create(
                    model=model_info["model"],
                    messages=[{"role": "user", "content": TEST_QUESTION}],
                    temperature=0.7,
                    max_tokens=1000,
                )

                answer = response.choices[0].message.content.strip()
                print(f"    ✅ Success: {len(answer)} characters")

                results.append(
                    {
                        "provider": "openai",
                        "model": model_info,
                        "status": "success",
                        "answer": answer,
                    }
                )

            except Exception as e:
                print(f"    ❌ Failed: {e}")
                results.append(
                    {
                        "provider": "openai",
                        "model": model_info,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        return results

    except Exception as e:
        print(f"  ❌ OpenAI setup error: {e}")
        return []


async def test_deepseek_models():
    """Test DeepSeek models"""
    print("\n🔍 Testing DeepSeek Models...")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com"
        )

        results = []
        for model_info in SELECTED_MODELS["deepseek"]:
            try:
                print(f"  📝 Testing {model_info['name']} ({model_info['model']})...")

                response = await client.chat.completions.create(
                    model=model_info["model"],
                    messages=[{"role": "user", "content": TEST_QUESTION}],
                    temperature=0.7,
                    max_tokens=1000,
                )

                answer = response.choices[0].message.content.strip()
                print(f"    ✅ Success: {len(answer)} characters")

                results.append(
                    {
                        "provider": "deepseek",
                        "model": model_info,
                        "status": "success",
                        "answer": answer,
                    }
                )

            except Exception as e:
                print(f"    ❌ Failed: {e}")
                results.append(
                    {
                        "provider": "deepseek",
                        "model": model_info,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        return results

    except Exception as e:
        print(f"  ❌ DeepSeek setup error: {e}")
        return []


async def test_cerebras_models():
    """Test Cerebras models"""
    print("\n🔍 Testing Cerebras Models...")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=os.getenv("CEREBRAS_API_KEY"), base_url="https://api.cerebras.ai/v1"
        )

        results = []
        for model_info in SELECTED_MODELS["cerebras"]:
            try:
                print(f"  📝 Testing {model_info['name']} ({model_info['model']})...")

                response = await client.chat.completions.create(
                    model=model_info["model"],
                    messages=[{"role": "user", "content": TEST_QUESTION}],
                    temperature=0.7,
                    max_tokens=1000,
                )

                answer = response.choices[0].message.content.strip()
                print(f"    ✅ Success: {len(answer)} characters")

                results.append(
                    {
                        "provider": "cerebras",
                        "model": model_info,
                        "status": "success",
                        "answer": answer,
                    }
                )

            except Exception as e:
                print(f"    ❌ Failed: {e}")
                results.append(
                    {
                        "provider": "cerebras",
                        "model": model_info,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        return results

    except Exception as e:
        print(f"  ❌ Cerebras setup error: {e}")
        return []


async def test_gemini_models():
    """Test Gemini models"""
    print("\n🔍 Testing Gemini Models...")

    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

        results = []
        for model_info in SELECTED_MODELS["gemini"]:
            try:
                print(f"  📝 Testing {model_info['name']} ({model_info['model']})...")

                model = genai.GenerativeModel(model_info["model"])
                response = model.generate_content(
                    TEST_QUESTION,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=2000,
                    ),
                )

                # Handle Gemini response parsing
                answer = None
                try:
                    answer = response.text.strip()
                    print(f"    ✅ Method 1 (text): Success")
                except Exception as e1:
                    try:
                        if len(response.parts) > 0:
                            answer = "".join(
                                part.text for part in response.parts
                            ).strip()
                            print(f"    ✅ Method 2 (parts): Success")
                        else:
                            parts = response.candidates[0].content.parts
                            answer = "".join(part.text for part in parts).strip()
                            print(f"    ✅ Method 3 (candidates): Success")
                    except Exception as e2:
                        print(f"    ❌ All parsing methods failed: {e1}, {e2}")
                        answer = "Failed to parse Gemini response"

                if answer and answer.strip():
                    print(f"    ✅ Final Success: {len(answer)} characters")
                else:
                    answer = "No response content found"

                results.append(
                    {
                        "provider": "gemini",
                        "model": model_info,
                        "status": "success",
                        "answer": answer,
                    }
                )

            except Exception as e:
                print(f"    ❌ Failed: {e}")
                results.append(
                    {
                        "provider": "gemini",
                        "model": model_info,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        return results

    except Exception as e:
        print(f"  ❌ Gemini setup error: {e}")
        return []


async def main():
    """Main function"""
    print("🚀 Testing All 12 Selected AI Models")
    print("=" * 80)
    print(f"Question: {TEST_QUESTION}")
    print("=" * 80)

    # Test all providers
    openai_results = await test_openai_models()
    deepseek_results = await test_deepseek_models()
    cerebras_results = await test_cerebras_models()
    gemini_results = await test_gemini_models()

    # Combine all results
    all_results = openai_results + deepseek_results + cerebras_results + gemini_results

    # Print summary
    print("\n" + "=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)

    successful_models = [r for r in all_results if r["status"] == "success"]
    failed_models = [r for r in all_results if r["status"] == "failed"]

    print(f"✅ Successful models: {len(successful_models)}")
    print(f"❌ Failed models: {len(failed_models)}")

    if successful_models:
        print("\n🎯 WORKING MODELS FOR CHAT_ROUTES.PY:")
        print("-" * 60)

        # Group by provider for clean output
        provider_groups = {}
        for result in successful_models:
            provider = result["provider"]
            if provider not in provider_groups:
                provider_groups[provider] = []
            provider_groups[provider].append(result["model"])

        for provider, models in provider_groups.items():
            print(f"\n{provider.upper()}:")
            for model in models:
                print(f"  - {model['id']}: {model['name']} ({model['model']})")

    if failed_models:
        print("\n❌ FAILED MODELS:")
        print("-" * 60)
        for result in failed_models:
            model_info = result["model"]
            print(f"Provider: {result['provider'].upper()}")
            print(f"  Model: {model_info['name']} ({model_info['model']})")
            print(f"  Error: {result['error']}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
