#!/usr/bin/env python3
"""
Test supported file formats
Test các định dạng file được hỗ trợ
"""
import sys
import requests
import tempfile
import os
import io

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


def test_supported_formats():
    """Test supported file formats"""
    print("🧪 TESTING SUPPORTED FILE FORMATS")
    print("=" * 50)

    try:
        from google import genai
        from google.genai import types

        # Get API key
        api_key = APP_CONFIG.get("gemini_api_key")
        client = genai.Client(api_key=api_key)

        # Test 1: Text file
        print("📝 Test 1: Plain text file")
        try:
            test_text = """SAMPLE HOTEL DATA

MERMAID SEASIDE HOTEL VUNG TAU
===============================

ROOMS AVAILABLE:
- Deluxe Sea View Room: 2,500,000 VND/night
  * King bed, sea view balcony
  * Free WiFi, minibar, safe
  * 40 sqm area

- Superior Room: 1,800,000 VND/night
  * Queen bed, city view
  * Free WiFi, minibar
  * 30 sqm area

- Standard Room: 1,200,000 VND/night
  * Double bed, garden view
  * Free WiFi
  * 25 sqm area

HOTEL SERVICES:
- Spa & Wellness Center: 800,000 VND per session
- City Tour Package: 500,000 VND per person
- Seafood Restaurant: 300,000 VND per meal
- Airport Transfer: 200,000 VND per trip

CONTACT INFORMATION:
Phone: +84 254 123 4567
Email: booking@mermaidseaside.vn
Address: 123 Seaside Street, Vung Tau, Vietnam"""

            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".txt", encoding="utf-8"
            ) as tmp_file:
                tmp_file.write(test_text)
                tmp_file_path = tmp_file.name

            try:
                uploaded_file = client.files.upload(
                    file=tmp_file_path,
                    config=types.UploadFileConfig(
                        mime_type="text/plain", display_name="hotel_data.txt"
                    ),
                )
                print(f"✅ Text file uploaded: {uploaded_file.name}")

                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=[
                        "Phân tích file này và trích xuất thông tin về phòng nghỉ, giá cả và dịch vụ. Trả lời bằng tiếng Việt.",
                        uploaded_file,
                    ],
                )
                print("🎯 TEXT FILE RESPONSE:")
                print("=" * 30)
                print(response.text)
                print("=" * 30)

                client.files.delete(name=uploaded_file.name)

            finally:
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)

        except Exception as e:
            print(f"❌ Text file test failed: {e}")

        # Test 2: Try extract text from DOCX first
        print(f"\n📄 Test 2: Extract text from DOCX then process")
        try:
            # Download R2 file
            r2_file_url = "https://static.agent8x.io.vn/company/1e789800-b402-41b0-99d6-2e8d494a3beb/files/d528420e-8119-45b5-b76e-fddcbe798ac3.docx"

            print(f"📥 Downloading DOCX...")
            response = requests.get(r2_file_url, timeout=30)
            response.raise_for_status()

            file_content = response.content
            print(f"✅ DOCX downloaded: {len(file_content)} bytes")

            # Try extract text using python-docx
            try:
                from docx import Document

                # Create temp DOCX file
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".docx"
                ) as tmp_file:
                    tmp_file.write(file_content)
                    tmp_docx_path = tmp_file.name

                try:
                    # Extract text
                    doc = Document(tmp_docx_path)
                    extracted_text = ""

                    for paragraph in doc.paragraphs:
                        if paragraph.text.strip():
                            extracted_text += paragraph.text.strip() + "\n"

                    print(f"✅ Extracted text: {len(extracted_text)} characters")
                    print(f"Preview: {extracted_text[:200]}...")

                    # Upload extracted text
                    with tempfile.NamedTemporaryFile(
                        mode="w", delete=False, suffix=".txt", encoding="utf-8"
                    ) as tmp_text_file:
                        tmp_text_file.write(extracted_text)
                        tmp_text_path = tmp_text_file.name

                    try:
                        uploaded_text = client.files.upload(
                            file=tmp_text_path,
                            config=types.UploadFileConfig(
                                mime_type="text/plain",
                                display_name="extracted_docx.txt",
                            ),
                        )
                        print(f"✅ Extracted text uploaded: {uploaded_text.name}")

                        response = client.models.generate_content(
                            model="gemini-2.5-flash-lite",
                            contents=[
                                "Hãy phân tích file này và trích xuất thông tin chi tiết về sản phẩm, dịch vụ và giá cả. Trả lời bằng tiếng Việt.",
                                uploaded_text,
                            ],
                        )
                        print("🎯 EXTRACTED DOCX RESPONSE:")
                        print("=" * 30)
                        print(response.text)
                        print("=" * 30)

                        client.files.delete(name=uploaded_text.name)

                    finally:
                        if os.path.exists(tmp_text_path):
                            os.unlink(tmp_text_path)

                finally:
                    if os.path.exists(tmp_docx_path):
                        os.unlink(tmp_docx_path)

            except ImportError:
                print("❌ python-docx not installed, trying alternative method...")

                # Alternative: Send raw text to ChatGPT-style processing
                print("🔄 Falling back to direct text processing...")
                simple_response = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=f"Tôi có một file DOCX chứa thông tin về khách sạn nhưng không thể upload được. File có kích thước {len(file_content)} bytes. Hãy đưa ra hướng dẫn về cách xử lý file DOCX với Gemini API.",
                )
                print("🎯 FALLBACK RESPONSE:")
                print("=" * 30)
                print(simple_response.text)
                print("=" * 30)

        except Exception as e:
            print(f"❌ DOCX processing failed: {e}")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"🔍 Error type: {type(e)}")


if __name__ == "__main__":
    test_supported_formats()
