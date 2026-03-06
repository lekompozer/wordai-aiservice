#!/usr/bin/env python3
"""
Test Google GenAI New Package
Khám phá API mới của google-genai package
"""
import asyncio
import sys
import os

# Add src to path
sys.path.append("src")


async def explore_google_genai():
    """Khám phá google-genai API mới"""
    print("🧪 EXPLORING GOOGLE-GENAI NEW API")
    print("=" * 50)

    try:
        from google import genai
        from google.genai import types

        print("✅ Import successful!")

        # Show available attributes
        print("\n📋 Available in genai:")
        genai_attrs = [attr for attr in dir(genai) if not attr.startswith("_")]
        for attr in genai_attrs:
            print(f"   - {attr}")

        print("\n📋 Available in types:")
        types_attrs = [attr for attr in dir(types) if not attr.startswith("_")]
        for attr in types_attrs:
            print(f"   - {attr}")

        # Test client creation
        print("\n🔧 Testing Client creation:")
        try:
            # Try different ways to create client
            client = genai.Client(api_key="test_key")
            print("✅ genai.Client() works!")
            print(f"📍 Client type: {type(client)}")

            # Show client methods
            client_methods = [
                method for method in dir(client) if not method.startswith("_")
            ]
            print("📋 Client methods:")
            for method in client_methods[:10]:  # Show first 10
                print(f"   - {method}")
            if len(client_methods) > 10:
                print(f"   ... and {len(client_methods) - 10} more")

        except Exception as e:
            print(f"❌ Client creation failed: {e}")

        # Test models
        print("\n🤖 Testing Models:")
        try:
            # Check if there's a models attribute
            if hasattr(genai, "models"):
                print("✅ genai.models found!")
                models_attrs = [
                    attr for attr in dir(genai.models) if not attr.startswith("_")
                ]
                print("📋 Models methods:")
                for attr in models_attrs:
                    print(f"   - {attr}")
        except Exception as e:
            print(f"❌ Models exploration failed: {e}")

        # Test file upload
        print("\n📁 Testing File Upload:")
        try:
            if hasattr(genai, "upload_file"):
                print("✅ genai.upload_file found!")
            elif hasattr(genai, "files"):
                print("✅ genai.files found!")
                files_attrs = [
                    attr for attr in dir(genai.files) if not attr.startswith("_")
                ]
                print("📋 Files methods:")
                for attr in files_attrs:
                    print(f"   - {attr}")
            else:
                print("❓ No direct file upload method found")
        except Exception as e:
            print(f"❌ File upload exploration failed: {e}")

    except ImportError as e:
        print(f"❌ Import failed: {e}")
    except Exception as e:
        print(f"❌ Exploration failed: {e}")


if __name__ == "__main__":
    asyncio.run(explore_google_genai())
