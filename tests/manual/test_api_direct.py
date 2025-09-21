#!/usr/bin/env python3
"""
Test API endpoint trực tiếp để debug
"""
import asyncio
import json
import httpx


async def test_api_direct():
    """Test API endpoint trực tiếp"""

    print("🚀 TESTING API ENDPOINT DIRECTLY")
    print("=" * 50)

    # API endpoint
    url = "http://localhost:8000/api/extract/process"

    # Request payload - sử dụng URL đúng từ test file
    payload = {
        "r2_url": "https://agent8x.io.vn/companies/ivy-fashion-store/ivy-fashion-products-clean.csv",
        "industry": "fashion",
        "file_metadata": {
            "filename": "20250714_103032_ivy-fashion-products.csv",
            "content_type": "text/csv",
            "size": 3668,
        },
        "target_categories": ["products"],
    }

    print("📋 Request payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print()

    headers = {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            print("🚀 Making API call...")
            response = await client.post(url, headers=headers, json=payload)

            print(f"📊 Status Code: {response.status_code}")
            print(f"📄 Headers: {dict(response.headers)}")

            if response.status_code == 200:
                data = response.json()
                print("✅ Success response!")
                print("📋 Response keys:", list(data.keys()))

                # Print full response first for debugging
                print("\n📄 FULL RESPONSE:")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                if "structured_data" in data and data["structured_data"] is not None:
                    structured = data["structured_data"]
                    print(f"📊 Structured data keys: {list(structured.keys())}")

                    if "products" in structured:
                        products = structured["products"]
                        print(f"🛍️ Found {len(products)} products")

                        if products:
                            print("📦 First 3 products:")
                            for i, product in enumerate(products[:3]):
                                print(
                                    f"  {i+1}. {product.get('name', 'N/A')} - {product.get('price', 0):,} VND"
                                )
                    else:
                        print("❌ No 'products' in structured_data")
                        print(f"Available keys: {list(structured.keys())}")
                else:
                    print("❌ structured_data is None or missing")

                if "raw_content" in data:
                    raw_content = data["raw_content"]
                    print(f"📄 Raw content length: {len(str(raw_content))} chars")

            else:
                print(f"❌ Error response: {response.status_code}")
                print(f"📄 Response text: {response.text}")

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback

        print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(test_api_direct())
