#!/usr/bin/env python3
"""
Test Gemini với file R2 có sẵn
Test với file thật từ R2 storage
"""
import asyncio
import sys
import requests
import tempfile
import os

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


async def test_gemini_with_r2_file():
    """Test Gemini với file R2 thật"""
    print("🧪 TESTING GEMINI WITH R2 FILE")
    print("=" * 50)

    # R2 file URL
    r2_file_url = "https://static.agent8x.io.vn/company/1e789800-b402-41b0-99d6-2e8d494a3beb/files/d528420e-8119-45b5-b76e-fddcbe798ac3.docx"

    try:
        from google import genai
        from google.genai import types

        # Get API key
        api_key = APP_CONFIG.get("gemini_api_key")
        if not api_key:
            print("❌ No Gemini API key found")
            return

        # Create client
        client = genai.Client(api_key=api_key)
        print("✅ Client created successfully")

        # Download file from R2
        print(f"📥 Downloading file from R2: {r2_file_url}")
        response = requests.get(r2_file_url, timeout=30)
        response.raise_for_status()

        file_content = response.content
        file_size = len(file_content)
        print(f"✅ File downloaded: {file_size} bytes")

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name

        try:
            print(f"📁 Created temporary file: {tmp_file_path}")

            # Test file upload using new API
            print("🚀 Uploading file to Gemini...")

            # Use new API structure
            uploaded_file = client.files.upload(
                file=tmp_file_path,  # Change from 'path' to 'file'
                config=types.UploadFileConfig(
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    display_name="r2_test_file.docx",
                ),
            )
            print(f"✅ File uploaded successfully: {uploaded_file.name}")
            print(f"   File URI: {uploaded_file.uri}")
            print(f"   File State: {uploaded_file.state.name}")

            # Wait for file processing
            import time

            timeout_start = time.time()
            timeout = 60  # 60 seconds timeout

            while uploaded_file.state.name == "PROCESSING":
                if time.time() - timeout_start > timeout:
                    raise Exception("File processing timeout")
                print(f"⏳ Processing... ({uploaded_file.state.name})")
                time.sleep(2)
                # Refresh file status
                uploaded_file = client.files.get(uploaded_file.name)

            print(f"✅ File processed: {uploaded_file.state.name}")

            # Test content generation with uploaded file
            print("🤖 Generating content with uploaded file...")

            prompt = "Hãy phân tích file này và trích xuất thông tin chi tiết về sản phẩm, dịch vụ và giá cả. Trả lời bằng tiếng Việt."

            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=prompt),
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

            print("=" * 50)
            print("🎯 GEMINI RESPONSE:")
            print("=" * 50)
            print(response.text)
            print("=" * 50)

            # Clean up uploaded file
            try:
                client.files.delete(uploaded_file.name)
                print("✅ Uploaded file cleaned up successfully")
            except Exception as cleanup_error:
                print(f"⚠️ Could not cleanup uploaded file: {cleanup_error}")

        finally:
            # Clean up temp file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                print("✅ Temporary file cleaned up")

    except requests.RequestException as e:
        print(f"❌ Failed to download R2 file: {e}")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"🔍 Error type: {type(e)}")


async def test_updated_gemini_client():
    """Test updated Gemini client với R2 file"""
    print("\n🧪 TESTING UPDATED GEMINI CLIENT")
    print("=" * 50)

    try:
        from src.clients.gemini_client import GeminiClient

        # Get API key
        api_key = APP_CONFIG.get("gemini_api_key")
        if not api_key:
            print("❌ No Gemini API key found")
            return

        # Create Gemini client
        gemini_client = GeminiClient(api_key=api_key)
        print("✅ Gemini client created")

        # Download R2 file
        r2_file_url = "https://static.agent8x.io.vn/company/1e789800-b402-41b0-99d6-2e8d494a3beb/files/d528420e-8119-45b5-b76e-fddcbe798ac3.docx"

        print(f"📥 Downloading R2 file...")
        response = requests.get(r2_file_url, timeout=30)
        response.raise_for_status()

        file_content = response.content
        print(f"✅ File downloaded: {len(file_content)} bytes")

        # Test upload_file_and_analyze
        print("🚀 Testing upload_file_and_analyze...")

        result = await gemini_client.upload_file_and_analyze(
            file_content=file_content,
            file_name="r2_test_file.docx",
            prompt="Hãy phân tích file này và trích xuất thông tin về sản phẩm, dịch vụ, giá cả. Trả lời bằng tiếng Việt.",
        )

        print("=" * 50)
        print("🎯 GEMINI CLIENT RESPONSE:")
        print("=" * 50)
        print(result)
        print("=" * 50)

    except Exception as e:
        print(f"❌ Gemini client test failed: {e}")
        print(f"🔍 Error type: {type(e)}")


if __name__ == "__main__":
    # Test both direct API and client
    asyncio.run(test_gemini_with_r2_file())
    asyncio.run(test_updated_gemini_client())
