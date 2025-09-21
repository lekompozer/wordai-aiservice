#!/usr/bin/env python3
"""
Debug API signatures
Kiểm tra API signatures đúng
"""
import sys

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


def debug_api_signatures():
    """Debug API signatures"""
    print("🔍 DEBUGGING API SIGNATURES")
    print("=" * 50)

    try:
        from google import genai
        from google.genai import types

        # Get API key
        api_key = APP_CONFIG.get("gemini_api_key")
        client = genai.Client(api_key=api_key)

        print("📋 CLIENT FILES METHODS:")
        files_methods = [
            method for method in dir(client.files) if not method.startswith("_")
        ]
        for method in files_methods:
            try:
                func = getattr(client.files, method)
                if callable(func):
                    import inspect

                    sig = inspect.signature(func)
                    print(f"  {method}{sig}")
            except Exception as e:
                print(f"  {method}: Error getting signature - {e}")

        print("\n📋 CLIENT MODELS METHODS:")
        models_methods = [
            method for method in dir(client.models) if not method.startswith("_")
        ]
        for method in models_methods:
            try:
                func = getattr(client.models, method)
                if callable(func):
                    import inspect

                    sig = inspect.signature(func)
                    print(f"  {method}{sig}")
            except Exception as e:
                print(f"  {method}: Error getting signature - {e}")

        print("\n📋 TYPES AVAILABLE:")
        types_attrs = [attr for attr in dir(types) if not attr.startswith("_")]
        for attr in types_attrs[:10]:  # First 10
            print(f"  {attr}")
        print(f"  ... and {len(types_attrs)-10} more")

    except Exception as e:
        print(f"❌ Debug failed: {e}")


if __name__ == "__main__":
    debug_api_signatures()
