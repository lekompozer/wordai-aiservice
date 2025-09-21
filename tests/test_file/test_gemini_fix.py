#!/usr/bin/env python3
"""
Test Gemini -> ChatGPT Fallback Fix
Test fix cho lỗi Gemini upload_file với fallback sang ChatGPT
"""
import asyncio
import sys
import os

# Add src to path
sys.path.append("src")

from services.ai_extraction_service import AIExtractionService
from core.config import APP_CONFIG

async def test_extraction_fallback():
    """Test AI extraction service với Gemini -> ChatGPT fallback"""
    print("🧪 TESTING EXTRACTION SERVICE FALLBACK")
    print("=" * 60)

    # Test URL from the production error
    test_r2_url = "https://static.agent8x.io.vn/company/1e789800-b402-41b0-99d6-2e8d494a3beb/files/d528420e-8119-45b5-b76e-fddcbe798ac3.docx"
    company_id = "1e789800-b402-41b0-99d6-2e8d494a3beb"

    try:
        # Create AI extraction service
        ai_service = AIExtractionService()
        print("✅ AIExtractionService initialized")

        # Test metadata
        metadata = {
            "filename": "Mermaid Seaside Hotel Vũng Tàu-Gia Phong.docx",
            "industry": "hotel",
            "language": "vi",
            "data_type": "products"
        }

        target_categories = ["products", "services"]

        print(f"🎯 Testing extraction from: {test_r2_url}")
        print(f"🏢 Company ID: {company_id}")
        print(f"📋 Categories: {target_categories}")
        print("🚀 Starting extraction (Gemini -> ChatGPT fallback)...")

        # Test extraction with fallback
        result = await ai_service.extract_from_r2_url(
            r2_url=test_r2_url,
            company_id=company_id,
            metadata=metadata,
            target_categories=target_categories,
            ai_provider="gemini"  # Will fallback to ChatGPT if fails
        )

        print("✅ Extraction successful!")
        print(f"📊 Result keys: {list(result.keys())}")

        if "structured_data" in result:
            structured = result["structured_data"]
            print(f"📈 Structured data keys: {list(structured.keys())}")

            for category in target_categories:
                if category in structured:
                    items = structured[category]
                    print(f"� {category.upper()}: {len(items)} items")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"🔍 Error type: {type(e)}")

        # Check if it's still the upload_file error
        if "upload_file" in str(e):
            print("🚨 Still having Gemini upload_file API issue")
        elif "Gemini upload failed, fallback to ChatGPT" in str(e):
            print("✅ Fallback logic is working (Gemini failed, ChatGPT should be tried)")
        else:
            print("🔄 Different error, investigating...")

if __name__ == "__main__":
    asyncio.run(test_extraction_fallback())
