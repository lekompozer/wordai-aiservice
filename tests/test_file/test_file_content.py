#!/usr/bin/env python3
"""
Test file content generation
Test generate content với file
"""
import sys
import requests
import tempfile
import os

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


def test_file_content_generation():
    """Test file content generation"""
    print("🧪 TESTING FILE CONTENT GENERATION")
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
            print(f"   File URI: {uploaded_file.uri}")
            print(f"   File MIME type: {uploaded_file.mime_type}")

            # Test 1: Simple file reference
            print("\n📝 Test 1: Simple file reference in contents")
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=["Analyze this file", uploaded_file],
                )
                print(f"✅ Simple file response: {response.text[:100]}...")
            except Exception as e:
                print(f"❌ Simple file test failed: {e}")

            # Test 2: FileData structure
            print("\n📝 Test 2: Using FileData structure")
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part(text="Analyze this document"),
                                types.Part(
                                    file_data=types.FileData(
                                        file_uri=uploaded_file.uri,
                                        mime_type=uploaded_file.mime_type,
                                    )
                                ),
                            ],
                        )
                    ],
                )
                print(f"✅ FileData response: {response.text[:100]}...")
            except Exception as e:
                print(f"❌ FileData test failed: {e}")

            # Test 3: Different FileData approach
            print("\n📝 Test 3: Alternative FileData approach")
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {"text": "What's in this document?"},
                                {
                                    "file_data": {
                                        "file_uri": uploaded_file.uri,
                                        "mime_type": uploaded_file.mime_type,
                                    }
                                },
                            ],
                        }
                    ],
                )
                print(f"✅ Alternative FileData response: {response.text[:100]}...")
            except Exception as e:
                print(f"❌ Alternative FileData test failed: {e}")

            # Clean up
            client.files.delete(uploaded_file.name)
            print("✅ File cleaned up")

        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"🔍 Error type: {type(e)}")


if __name__ == "__main__":
    test_file_content_generation()
