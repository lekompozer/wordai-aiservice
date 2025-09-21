#!/usr/bin/env python3
"""
Test Correct File Upload API
Kiểm tra cách upload file đúng với API mới
"""
import asyncio
import sys
import tempfile
import os

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


async def test_correct_file_upload():
    """Test đúng cách upload file"""
    print("🧪 TESTING CORRECT FILE UPLOAD API")
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
        test_content = """SAMPLE HOTEL DATA FOR TESTING

MERMAID SEASIDE HOTEL VUNG TAU
===============================

ROOMS AVAILABLE:
- Deluxe Sea View Room: 2,500,000 VND/night
- Superior Room: 1,800,000 VND/night
- Standard Room: 1,200,000 VND/night

HOTEL SERVICES:
- Spa & Wellness Center: 800,000 VND per session
- City Tour Package: 500,000 VND per person
- Seafood Restaurant: 300,000 VND per meal
"""

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt", mode="w", encoding="utf-8"
        ) as tmp_file:
            tmp_file.write(test_content)
            tmp_file_path = tmp_file.name

        try:
            print(f"📁 Testing file upload: {tmp_file_path}")

            # Check available methods in client.files
            print("🔍 Available methods in client.files:")
            files_methods = [
                method for method in dir(client.files) if not method.startswith("_")
            ]
            for method in files_methods:
                print(f"  - {method}")

            # Method 1: Try upload with file-like object
            print("\n🚀 Trying upload with file object...")
            try:
                with open(tmp_file_path, "rb") as f:
                    uploaded_file = client.files.upload(
                        file=f,
                        mime_type="text/plain",
                        display_name="test_hotel_data.txt",
                    )
                    print(f"✅ File uploaded with file object: {uploaded_file.name}")

                    # Wait for processing
                    import time

                    while uploaded_file.state.name == "PROCESSING":
                        print("⏳ Waiting for processing...")
                        time.sleep(1)
                        uploaded_file = client.files.get(uploaded_file.name)

                    print(f"✅ File processing complete: {uploaded_file.state.name}")

                    # Try generate content
                    response = client.models.generate_content(
                        model="gemini-2.5-flash-lite",
                        contents=[
                            types.Content(
                                role="user",
                                parts=[
                                    types.Part(
                                        text="Hãy phân tích file này và trích xuất thông tin về các phòng nghỉ và dịch vụ. Trả lời bằng tiếng Việt."
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
                    print("✅ Content generation successful!")
                    print("📄 Response:")
                    print("-" * 30)
                    print(response.text[:300] + "...")

                    # Clean up
                    client.files.delete(uploaded_file.name)
                    print("✅ File cleaned up")

            except Exception as e:
                print(f"❌ Upload with file object failed: {e}")

                # Method 2: Try different parameters
                print("\n🚀 Trying upload with different parameters...")
                try:
                    # Check upload method signature
                    import inspect

                    upload_sig = inspect.signature(client.files.upload)
                    print(f"Upload method signature: {upload_sig}")

                except Exception as sig_error:
                    print(f"Could not get signature: {sig_error}")

        finally:
            # Clean up temp file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_correct_file_upload())
