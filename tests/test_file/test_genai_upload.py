#!/usr/bin/env python3
"""
Test Google GenAI File Upload
Test file upload với API mới
"""
import asyncio
import sys
import os
import tempfile

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


async def test_genai_file_upload():
    """Test file upload với google-genai mới"""
    print("🧪 TESTING GOOGLE-GENAI FILE UPLOAD")
    print("=" * 50)

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

        # Create test content
        test_content = """Sample content for testing hotel products:

MERMAID SEASIDE HOTEL VUNG TAU
===============================

ROOMS:
- Deluxe Sea View: 2,500,000 VND/night, beautiful sea view
- Superior Room: 1,800,000 VND/night, convenient room
- Standard Room: 1,200,000 VND/night, basic room

SERVICES:
- Spa relaxation: 800,000 VND/session
- Tourism tour: 500,000 VND/person
- Seafood restaurant: 300,000 VND/meal

Contact: 0123456789
Email: booking@mermaidhotel.vn
"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt", mode="w", encoding="utf-8"
        ) as tmp_file:
            tmp_file.write(test_content)
            tmp_file_path = tmp_file.name

        try:
            print(f"📁 Testing file upload: {tmp_file_path}")

            # Test file upload using new API
            print("🚀 Uploading file...")

            # Method 1: Try client.files.upload
            if hasattr(client.files, "upload"):
                print("✅ Using client.files.upload")
                uploaded_file = await client.files.upload(
                    path=tmp_file_path,
                    mime_type="text/plain",
                    display_name="test_hotel_data.txt",
                )
                print(f"✅ File uploaded: {uploaded_file}")

                # Test generate content with uploaded file
                print("🤖 Testing content generation with uploaded file...")

                # Try generate content
                if hasattr(client.models, "generate_content"):
                    response = await client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=[
                            types.Content(
                                role="user",
                                parts=[
                                    types.Part(
                                        text="Hãy phân tích file này và trích xuất thông tin về các phòng nghỉ và dịch vụ."
                                    ),
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
                    print(f"✅ Content generated: {response.text[:200]}...")
                else:
                    print("❌ generate_content method not found")

            else:
                print("❌ client.files.upload not found")

                # Try alternative methods
                print("🔍 Exploring alternative upload methods...")
                files_methods = [
                    method for method in dir(client.files) if not method.startswith("_")
                ]
                print(f"Available files methods: {files_methods}")

        finally:
            # Clean up temp file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except ImportError as e:
        print(f"❌ Import failed: {e}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"🔍 Error type: {type(e)}")


if __name__ == "__main__":
    asyncio.run(test_genai_file_upload())
