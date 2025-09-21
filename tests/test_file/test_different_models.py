#!/usr/bin/env python3
"""
Test different models với file
Test các model khác nhau
"""
import sys
import requests
import tempfile
import os

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


def test_different_models_with_file():
    """Test different models với file"""
    print("🧪 TESTING DIFFERENT MODELS WITH FILE")
    print("=" * 50)

    try:
        from google import genai
        from google.genai import types

        # Get API key
        api_key = APP_CONFIG.get("gemini_api_key")
        client = genai.Client(api_key=api_key)

        # Download R2 file
        r2_file_url = "https://static.agent8x.io.vn/company/1e789800-b402-41b0-99d6-2e8d494a3beb/files/d528420e-8119-45b5-b76e-fddcbe798ac3.docx"

        print(f"📥 Downloading file...")
        response = requests.get(r2_file_url, timeout=30)
        response.raise_for_status()

        file_content = response.content
        print(f"✅ File downloaded: {len(file_content)} bytes")

        # Create temp file and upload
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name

        try:
            # Upload file
            uploaded_file = client.files.upload(
                file=tmp_file_path,
                config=types.UploadFileConfig(
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    display_name="r2_test_file.docx",
                ),
            )
            print(f"✅ File uploaded: {uploaded_file.name}")

            # Test với các models khác nhau
            models_to_test = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-2.5-flash",
                "gemini-2.0-flash",
            ]

            for model_name in models_to_test:
                print(f"\n🤖 Testing model: {model_name}")
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[
                            "Analyze this document and tell me what you see",
                            uploaded_file,
                        ],
                    )
                    print(f"✅ {model_name}: {response.text[:100]}...")
                    break  # If successful, stop testing
                except Exception as e:
                    print(f"❌ {model_name}: {e}")

            # Clean up
            try:
                client.files.delete(name=uploaded_file.name)
                print("✅ File cleaned up")
            except Exception as e:
                print(f"⚠️ Cleanup error: {e}")

        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"🔍 Error type: {type(e)}")


if __name__ == "__main__":
    test_different_models_with_file()
