#!/usr/bin/env python3
"""
Test Specific AI Models - Test với model cụ thể theo yêu cầu
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

# Model configuration theo yêu cầu
SELECTED_MODELS = {
    "openai": [
        {
            "id": "chatgpt_4o_latest",
            "name": "ChatGPT-4o Latest",
            "model": "chatgpt-4o-latest",
            "category": "latest",
        },
        {
            "id": "gpt_4o_realtime",
            "name": "GPT-4o Realtime Preview",
            "model": "gpt-4o-realtime-preview-2025-06-03",
            "category": "realtime",
        },
        {
            "id": "gpt_4o_search",
            "name": "GPT-4o Search Preview",
            "model": "gpt-4o-search-preview",
            "category": "search",
        },
    ],
    "gemini": [
        # {
        #     "id": "gemini_flash_image",
        #     "name": "Gemini 2.5 Flash Image Preview",
        #     "model": "gemini-2.5-flash-image-preview",
        #     "category": "image"
        # },
        {
            "id": "gemini_flash",
            "name": "Gemini 2.5 Flash",
            "model": "gemini-2.5-flash",
            "category": "fast",
        },
        {
            "id": "gemini_pro",
            "name": "Gemini 2.5 Pro",
            "model": "gemini-2.5-pro",
            "category": "advanced",
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
}

# Câu hỏi test về Vũng Tàu
TEST_QUESTION = """Bạn có thể giới thiệu cho tôi 5 địa điểm du lịch nổi tiếng ở Vũng Tàu không?
Hãy trả lời ngắn gọn, mỗi địa điểm chỉ cần 1-2 câu mô tả."""


async def test_openai_models():
    """Test OpenAI models"""
    print("🔍 Testing OpenAI Models...")

    try:
        import openai

        client = openai.AsyncOpenAI(api_key=os.getenv("CHATGPT_API_KEY"))

        results = []
        for model_info in SELECTED_MODELS["openai"]:
            try:
                print(f"  📝 Testing {model_info['name']} ({model_info['model']})...")

                response = await client.chat.completions.create(
                    model=model_info["model"],
                    messages=[{"role": "user", "content": TEST_QUESTION}],
                    max_tokens=300,
                    temperature=0.7,
                )

                answer = response.choices[0].message.content.strip()
                print(f"    ✅ Success: {answer[:100]}...")
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
        import openai

        client = openai.AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
        )

        results = []
        for model_info in SELECTED_MODELS["deepseek"]:
            try:
                print(f"  📝 Testing {model_info['name']} ({model_info['model']})...")

                response = await client.chat.completions.create(
                    model=model_info["model"],
                    messages=[{"role": "user", "content": TEST_QUESTION}],
                    max_tokens=300,
                    temperature=0.7,
                )

                answer = response.choices[0].message.content.strip()
                print(f"    ✅ Success: {answer[:100]}...")
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
        from cerebras.cloud.sdk import Cerebras

        client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))

        results = []
        for model_info in SELECTED_MODELS["cerebras"]:
            try:
                print(f"  📝 Testing {model_info['name']} ({model_info['model']})...")

                response = client.chat.completions.create(
                    model=model_info["model"],
                    messages=[{"role": "user", "content": TEST_QUESTION}],
                    max_tokens=300,
                    temperature=0.7,
                )

                answer = response.choices[0].message.content.strip()
                print(f"    ✅ Success: {answer[:100]}...")
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

                # Xử lý response phức tạp từ Gemini với try-catch riêng biệt
                answer = None

                # Thử cách 1: text trực tiếp
                try:
                    answer = response.text.strip()
                    print(f"    ✅ Method 1 (text): Success")
                except Exception as e1:
                    print(f"    ❌ Method 1 (text): {e1}")

                    # Thử cách 2: từ parts
                    try:
                        if len(response.parts) > 0:
                            answer = "".join(
                                part.text for part in response.parts
                            ).strip()
                            print(
                                f"    ✅ Method 2 (parts): Success - Length: {len(answer)}"
                            )
                        else:
                            print(f"    ⚠️ Method 2: parts is empty, trying method 3")
                            raise Exception("Empty parts, try method 3")

                    except Exception as e2:
                        print(f"    ❌ Method 2 (parts): {e2}")

                        # Thử cách 3: từ candidates
                        try:
                            parts = response.candidates[0].content.parts
                            if len(parts) > 0:
                                answer = "".join(part.text for part in parts).strip()
                                print(
                                    f"    ✅ Method 3 (candidates): Success - Length: {len(answer)}"
                                )
                            else:
                                print(f"    ⚠️ Method 3: candidate parts also empty")
                                print(
                                    f"    🔍 Debug: finish_reason = {response.candidates[0].finish_reason}"
                                )
                                answer = (
                                    "Empty response from Gemini (finish_reason issue)"
                                )
                        except Exception as e3:
                            print(f"    ❌ Method 3 (candidates): {e3}")
                            answer = "Failed to parse Gemini response"
                            answer = str(response)
                            print(f"    ⚠️ Using str(response)")

                if answer and answer.strip():
                    print(f"    ✅ Final Success: {len(answer)} characters")
                else:
                    print(f"    ⚠️ Empty response detected, using fallback")
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
    print("🚀 Testing Selected AI Models with Vũng Tàu Tourism Question")
    print("=" * 80)
    print(f"Question: {TEST_QUESTION}")
    print("=" * 80)

    # Test all providers
    all_results = []

    # openai_results = await test_openai_models()
    # all_results.extend(openai_results)

    # deepseek_results = await test_deepseek_models()
    # all_results.extend(deepseek_results)

    # cerebras_results = await test_cerebras_models()
    # all_results.extend(cerebras_results)

    gemini_results = await test_gemini_models()
    all_results.extend(gemini_results)

    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    successful_models = [r for r in all_results if r["status"] == "success"]
    failed_models = [r for r in all_results if r["status"] == "failed"]

    print(f"✅ Successful models: {len(successful_models)}")
    print(f"❌ Failed models: {len(failed_models)}")

    if successful_models:
        print("\n🎯 WORKING MODELS FOR FRONTEND:")
        print("-" * 60)
        for result in successful_models:
            model_info = result["model"]
            print(f"Provider: {result['provider'].upper()}")
            print(f"  ID: {model_info['id']}")
            print(f"  Name: {model_info['name']}")
            print(f"  Model: {model_info['model']}")
            print(f"  Category: {model_info['category']}")
            print(f"  Answer preview: {result['answer'][:150]}...")
            print()

    if failed_models:
        print("\n❌ FAILED MODELS:")
        print("-" * 60)
        for result in failed_models:
            model_info = result["model"]
            print(f"Provider: {result['provider'].upper()}")
            print(f"  Model: {model_info['name']} ({model_info['model']})")
            print(f"  Error: {result['error']}")
            print()

    # Generate final model list for documentation
    print("\n🔧 FINAL MODEL LIST FOR API DOCUMENTATION:")
    print("=" * 80)
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


if __name__ == "__main__":
    asyncio.run(main())
