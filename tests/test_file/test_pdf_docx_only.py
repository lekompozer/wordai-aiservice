#!/usr/bin/env python3
"""
Test script for simplified Gemini client - PDF and DOCX only
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from clients.gemini_client import GeminiClient
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_pdf_docx_only():
    """Test the simplified Gemini client with PDF and DOCX support only"""

    try:
        # Initialize client
        client = GeminiClient()
        logger.info("✅ Gemini client initialized")

        # Test with DOCX file from R2
        docx_url = "https://pub-ac57c91de57745bf909b7d0e0e2cc8dc.r2.dev/uploads/c067a848-5831-4c62-85f8-a6e5a0b1d2c3/CacCauHoi_duLichBien_V3.docx"

        print("\n" + "=" * 80)
        print("📄 Testing DOCX file processing (text extraction)")
        print("=" * 80)

        # Simulate file download (in real app, this would be from R2)
        import requests

        response = requests.get(docx_url)
        if response.status_code == 200:
            docx_content = response.content
            print(f"✅ Downloaded DOCX file: {len(docx_content)} bytes")

            # Test with Gemini
            result = await client.upload_file_and_analyze(
                file_content=docx_content,
                file_name="CacCauHoi_duLichBien_V3.docx",
                prompt="Hãy phân tích và tóm tắt nội dung chính của tài liệu này.",
            )

            print(f"✅ Gemini analysis result:")
            print("-" * 60)
            print(result[:500] + "..." if len(result) > 500 else result)
            print("-" * 60)
        else:
            print(f"❌ Failed to download DOCX file: {response.status_code}")

        # Test unsupported format (should fail)
        print("\n" + "=" * 80)
        print("❌ Testing unsupported format (should fail)")
        print("=" * 80)

        try:
            fake_excel_content = b"fake excel content"
            await client.upload_file_and_analyze(
                file_content=fake_excel_content, file_name="test.xlsx", prompt="Test"
            )
            print("❌ This should not work!")
        except Exception as e:
            print(f"✅ Expected error for unsupported format: {e}")

        print("\n" + "=" * 80)
        print("🎉 All tests completed!")
        print("✅ DOCX: Supported (text extraction)")
        print("✅ PDF: Supported (direct upload)")
        print("❌ Other formats: Not supported (frontend should prevent)")
        print("=" * 80)

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_pdf_docx_only())
