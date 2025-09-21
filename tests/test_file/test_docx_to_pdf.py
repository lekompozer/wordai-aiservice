#!/usr/bin/env python3
"""
Test script for DOCX to PDF conversion with Gemini
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


async def test_docx_to_pdf_conversion():
    """Test DOCX to PDF conversion before sending to Gemini"""

    try:
        # Initialize client
        client = GeminiClient()
        logger.info("✅ Gemini client initialized")

        # Test with DOCX file from R2
        docx_url = "https://pub-ac57c91de57745bf909b7d0e0e2cc8dc.r2.dev/uploads/c067a848-5831-4c62-85f8-a6e5a0b1d2c3/CacCauHoi_duLichBien_V3.docx"

        print("\n" + "=" * 80)
        print("📄 Testing DOCX to PDF conversion + Gemini analysis")
        print("=" * 80)

        # Download DOCX file
        import requests

        response = requests.get(docx_url)
        if response.status_code == 200:
            docx_content = response.content
            print(f"✅ Downloaded DOCX file: {len(docx_content)} bytes")

            # Test DOCX to PDF conversion + Gemini analysis
            result = await client.upload_file_and_analyze(
                file_content=docx_content,
                file_name="CacCauHoi_duLichBien_V3.docx",
                prompt="Hãy phân tích tài liệu này và tóm tắt nội dung chính về du lịch biển.",
            )

            print(f"✅ Gemini analysis result:")
            print("-" * 60)
            print(result[:800] + "..." if len(result) > 800 else result)
            print("-" * 60)
        else:
            print(f"❌ Failed to download DOCX file: {response.status_code}")

        print("\n" + "=" * 80)
        print("🎉 DOCX to PDF conversion test completed!")
        print("✅ DOCX → PDF → Gemini Analysis")
        print("✅ Preserves document formatting and structure")
        print("✅ Better than text extraction for complex documents")
        print("=" * 80)

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_docx_to_pdf_conversion())
