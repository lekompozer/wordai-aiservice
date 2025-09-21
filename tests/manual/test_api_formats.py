#!/usr/bin/env python3
"""
Debug API request để xem server nhận metadata như thế nào
"""
import asyncio
import json
import httpx


async def test_different_formats():
    """Test different request formats"""

    print("🔍 TESTING DIFFERENT API REQUEST FORMATS")
    print("=" * 60)

    # Test cases with different metadata structures
    test_cases = [
        {
            "name": "Ivy Fashion CSV - Correct Format",
            "payload": {
                "r2_url": "https://agent8x.io.vn/companies/ivy-fashion-store/20250714_103032_ivy-fashion-products.csv",
                "industry": "fashion",
                "original_name": "20250714_103032_ivy-fashion-products.csv",
                "file_metadata": {
                    "filename": "20250714_103032_ivy-fashion-products.csv",
                    "content_type": "text/csv",
                    "size": 3668,
                },
                "target_categories": ["products"],
            },
        }
    ]

    url = "http://localhost:8000/api/extract/process"
    headers = {"Content-Type": "application/json"}

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 TEST {i}: {test_case['name']}")
        print("-" * 40)

        payload = test_case["payload"]

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:  # Tăng timeout
                print("🚀 Making API call...")
                response = await client.post(url, headers=headers, json=payload)

                print(f"📊 Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()

                    # Print full response for debugging
                    print("📄 FULL RESPONSE:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))

                    # Key metrics
                    success = data.get("success", False)
                    ai_provider = data.get("ai_provider")
                    total_items = data.get("total_items_extracted", 0)
                    raw_content_len = len(str(data.get("raw_content", "")))
                    processing_time = data.get("processing_time", 0)

                    print(f"\n📊 SUMMARY:")
                    print(f"✅ Success: {success}")
                    print(f"🤖 AI Provider: {ai_provider}")
                    print(f"📊 Items Extracted: {total_items}")
                    print(f"📄 Raw Content Length: {raw_content_len} chars")
                    print(f"⏱️ Processing Time: {processing_time:.2f}s")

                    if data.get("error"):
                        print(f"❌ Error: {data['error']}")

                    # Check structured data
                    structured = data.get("structured_data", {})
                    if structured and isinstance(structured, dict):
                        products = structured.get("products", [])
                        if products:
                            print(f"🛍️ First product: {products[0]}")
                        else:
                            print("📦 No products found")

                else:
                    print(f"❌ HTTP Error: {response.status_code}")
                    print(f"📄 Response: {response.text[:500]}...")

        except Exception as e:
            print(f"❌ Exception: {e}")


if __name__ == "__main__":
    asyncio.run(test_different_formats())
