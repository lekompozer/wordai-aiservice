#!/usr/bin/env python3
"""
Check Available Gemini Models
Kiểm tra các model Gemini có sẵn
"""
import asyncio
import sys

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


async def check_available_models():
    """Check available Gemini models"""
    print("🤖 CHECKING AVAILABLE GEMINI MODELS")
    print("=" * 50)

    try:
        from google import genai

        # Get API key
        api_key = APP_CONFIG.get("gemini_api_key")
        if not api_key:
            print("❌ No Gemini API key found")
            return

        # Create client
        client = genai.Client(api_key=api_key)
        print("✅ Client created successfully")

        # List available models
        print("\n📋 LISTING AVAILABLE MODELS:")
        print("-" * 30)

        try:
            # Method 1: Try client.models.list() - sync
            if hasattr(client.models, "list"):
                print("🔍 Using client.models.list()...")
                models = client.models.list()

                print(f"Models type: {type(models)}")

                try:
                    model_list = list(models)
                    print(f"Found {len(model_list)} models:")
                    for i, model in enumerate(model_list):
                        print(
                            f"{i+1:2d}. {model.name if hasattr(model, 'name') else model}"
                        )
                        if hasattr(model, "description"):
                            print(f"    Description: {model.description}")
                        if hasattr(model, "display_name"):
                            print(f"    Display Name: {model.display_name}")
                        print()
                except Exception as list_err:
                    print(f"Failed to iterate models: {list_err}")

            # Method 2: Try direct model names
            print("\n🧪 TESTING SPECIFIC MODELS:")
            print("-" * 30)

            test_models = [
                "gemini-2.5-flash-lite",
                "gemini-2.5-flash",
                "gemini-2.0-flash-exp",
                "gemini-2.0-flash",
                "gemini-1.5-flash-latest",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
            ]

            for model_name in test_models:
                try:
                    print(f"Testing {model_name}...")
                    response = client.models.generate_content(
                        model=model_name, contents="Hello, test message"
                    )
                    print(f"✅ {model_name}: Working")
                    if hasattr(response, "text"):
                        print(f"    Response: {response.text[:50]}...")
                    print()
                except Exception as e:
                    print(f"❌ {model_name}: Failed - {str(e)[:100]}")
                    print()

        except Exception as e:
            print(f"❌ Failed to list models: {e}")

            # Alternative: Check client.models methods
            print(f"\n🔍 Available methods in client.models:")
            methods = [
                method for method in dir(client.models) if not method.startswith("_")
            ]
            for method in methods:
                print(f"  - {method}")

    except ImportError as e:
        print(f"❌ Import failed: {e}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"🔍 Error type: {type(e)}")


if __name__ == "__main__":
    asyncio.run(check_available_models())
