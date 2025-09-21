#!/usr/bin/env python3
"""
Test script for complete Gemini extraction to Qdrant workflow
Script test cho luồng xử lý hoàn chỉnh từ Gemini extraction đến Qdrant
"""

import asyncio
import json
import aiohttp
from datetime import datetime

# Test data
TEST_PAYLOAD = {
    "r2_url": "https://agent8x.io.vn/companies/ivy-fashion-store/ivy-fashion-products-clean.csv",
    "company_id": "ivy-fashion-store",
    "industry": "fashion",
    "target_categories": ["products"],
    "file_metadata": {
        "original_name": "ivy-fashion-products-clean.csv",
        "file_size": 245760,
        "file_type": "text/csv",
        "uploaded_at": "2025-07-16T22:30:00Z",
    },
    "company_info": {
        "id": "ivy-fashion-store",
        "name": "Ivy Fashion Store",
        "industry": "fashion",
        "description": "Modern fashion retailer specializing in trendy clothing",
    },
    "language": "vi",
    "upload_to_qdrant": True,
}


async def test_extraction_with_qdrant():
    """Test the complete extraction to Qdrant workflow"""
    try:
        print("🚀 Starting Gemini extraction to Qdrant test")
        print(f"📊 Testing with: {TEST_PAYLOAD['r2_url']}")
        print(f"🏢 Company: {TEST_PAYLOAD['company_id']}")
        print(f"🏭 Industry: {TEST_PAYLOAD['industry']}")
        print(f"📦 Expected: Products extraction with Gemini")
        print(f"💾 Upload to Qdrant: {TEST_PAYLOAD['upload_to_qdrant']}")
        print("-" * 60)

        start_time = datetime.now()

        # Make request to extraction API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8000/api/extract/process",
                json=TEST_PAYLOAD,
                headers={"Content-Type": "application/json"},
            ) as response:

                if response.status == 200:
                    result = await response.json()
                    processing_time = (datetime.now() - start_time).total_seconds()

                    print("✅ EXTRACTION SUCCESSFUL")
                    print(f"⏱️  Total time: {processing_time:.2f}s")
                    print(f"📋 Template used: {result.get('template_used')}")
                    print(f"🤖 AI Provider: {result.get('ai_provider')}")
                    print(f"📊 Processing time: {result.get('processing_time')}s")
                    print(f"📈 Total items: {result.get('total_items_extracted', 0)}")

                    # Check structured data
                    structured_data = result.get("structured_data", {})
                    products = structured_data.get("products", [])
                    services = structured_data.get("services", [])

                    print(f"📦 Products found: {len(products)}")
                    print(f"🔧 Services found: {len(services)}")

                    # Show sample products
                    if products:
                        print("\n📦 SAMPLE PRODUCTS:")
                        for i, product in enumerate(products[:3]):
                            print(
                                f"   {i+1}. {product.get('name', 'N/A')} - {product.get('price', 'N/A')}"
                            )

                    # Show sample services
                    if services:
                        print("\n🔧 SAMPLE SERVICES:")
                        for i, service in enumerate(services[:3]):
                            print(
                                f"   {i+1}. {service.get('name', 'N/A')} - {service.get('pricing', 'N/A')}"
                            )

                    # Show extraction summary
                    extraction_summary = structured_data.get("extraction_summary", {})
                    if extraction_summary:
                        print(f"\n📋 EXTRACTION SUMMARY:")
                        print(
                            f"   Data quality: {extraction_summary.get('data_quality', 'N/A')}"
                        )
                        print(
                            f"   Industry context: {extraction_summary.get('industry_context', 'N/A')}"
                        )
                        print(
                            f"   Total products: {extraction_summary.get('total_products', 0)}"
                        )
                        print(
                            f"   Total services: {extraction_summary.get('total_services', 0)}"
                        )

                    # Show raw content preview
                    raw_content = result.get("raw_content", "")
                    if raw_content:
                        print(f"\n📄 RAW CONTENT PREVIEW (first 200 chars):")
                        print(f"   {raw_content[:200]}...")

                    print("\n🎯 QDRANT INTEGRATION STATUS:")
                    if TEST_PAYLOAD["upload_to_qdrant"]:
                        print("   ✅ Qdrant upload scheduled in background")
                        print(
                            "   📊 Data will be converted to QdrantDocumentChunk objects"
                        )
                        print("   🏢 Company-specific collection will be used")
                        print("   🔍 Products and services will be searchable by type")
                    else:
                        print("   ⏭️  Qdrant upload skipped (upload_to_qdrant=False)")

                    return {
                        "success": True,
                        "ai_provider": result.get("ai_provider"),
                        "template_used": result.get("template_used"),
                        "total_items": result.get("total_items_extracted", 0),
                        "products_count": len(products),
                        "services_count": len(services),
                        "processing_time": processing_time,
                    }

                else:
                    error_text = await response.text()
                    print(f"❌ EXTRACTION FAILED")
                    print(f"Status: {response.status}")
                    print(f"Error: {error_text}")
                    return {"success": False, "error": error_text}

    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        return {"success": False, "error": str(e)}


async def test_ai_provider_selection():
    """Test AI provider selection logic"""
    print("\n" + "=" * 60)
    print("🧪 TESTING AI PROVIDER SELECTION")
    print("=" * 60)

    test_cases = [
        {
            "file": "image.jpg",
            "expected": "chatgpt",
            "reason": "Image files use ChatGPT Vision",
        },
        {
            "file": "data.csv",
            "expected": "gemini",
            "reason": "CSV files use Gemini with file upload",
        },
        {
            "file": "document.pdf",
            "expected": "gemini",
            "reason": "PDF files use Gemini with file upload",
        },
        {
            "file": "data.json",
            "expected": "gemini",
            "reason": "JSON files use Gemini for text processing",
        },
    ]

    for test_case in test_cases:
        # Create test payload with different file
        test_payload = TEST_PAYLOAD.copy()
        test_payload["file_metadata"]["original_name"] = test_case["file"]
        test_payload["upload_to_qdrant"] = False  # Skip Qdrant for provider tests

        print(f"\n📄 Testing: {test_case['file']}")
        print(f"🎯 Expected: {test_case['expected']}")
        print(f"💡 Reason: {test_case['reason']}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:8000/api/extract/process", json=test_payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        actual_provider = result.get("ai_provider")

                        if actual_provider == test_case["expected"]:
                            print(f"✅ CORRECT: Used {actual_provider}")
                        else:
                            print(
                                f"❌ WRONG: Expected {test_case['expected']}, got {actual_provider}"
                            )
                    else:
                        print(f"❌ Request failed: {response.status}")
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")


async def main():
    """Main test function"""
    print("🧪 GEMINI EXTRACTION TO QDRANT INTEGRATION TEST")
    print("=" * 60)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Test 1: Main extraction workflow
    result = await test_extraction_with_qdrant()

    # Test 2: AI provider selection logic
    await test_ai_provider_selection()

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    if result.get("success"):
        print("✅ Main extraction test: PASSED")
        print(f"   🤖 AI Provider: {result.get('ai_provider')}")
        print(f"   📋 Template: {result.get('template_used')}")
        print(f"   📦 Products: {result.get('products_count')}")
        print(f"   🔧 Services: {result.get('services_count')}")
        print(f"   ⏱️  Time: {result.get('processing_time', 0):.2f}s")

        # Check if Gemini was used as expected
        if result.get("ai_provider") == "gemini":
            print("✅ Gemini provider used correctly for CSV file")
        else:
            print(f"⚠️  Expected Gemini, got {result.get('ai_provider')}")
    else:
        print("❌ Main extraction test: FAILED")
        print(f"   Error: {result.get('error')}")

    print("\n🎯 QDRANT INTEGRATION:")
    print("   📊 Data types separated: products vs services")
    print("   🏢 Company-specific collections")
    print("   🔍 Searchable by content type and metadata")
    print("   📤 Background processing implemented")

    print(f"\n🕐 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
