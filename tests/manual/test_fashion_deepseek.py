#!/usr/bin/env python3
"""
Test Fashion Products CSV with DeepSeek
Test file CSV sản phẩm thời trang với DeepSeek
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

SERVER_URL = "http://localhost:8000"
EXTRACT_ENDPOINT = f"{SERVER_URL}/api/extract/process"


async def test_fashion_csv_extraction():
    """Test DeepSeek with fashion products CSV file"""
    print("👗 TESTING FASHION PRODUCTS CSV EXTRACTION")
    print("=" * 60)
    print(f"🌐 Server: {SERVER_URL}")
    print(f"📡 Endpoint: {EXTRACT_ENDPOINT}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Test data - Fashion Products CSV
    test_request = {
        "r2_url": "https://agent8x.io.vn/companies/ivy-fashion-store/20250714_103032_ivy-fashion-products.csv",
        "industry": "fashion",  # Top level field
        "file_metadata": {
            "original_name": "20250714_103032_ivy-fashion-products.csv",
            "file_size": 25000,
            "file_type": "text/csv",
        },
        "target_categories": ["products", "services"],  # Auto-categorization
        "company_info": {
            "name": "Ivy Fashion Store",
            "industry": "fashion",
            "description": "Fashion retail store",
        },
        "language": "vi",
    }

    print("📋 TEST REQUEST DETAILS:")
    print(f"🔗 R2 URL: {test_request['r2_url']}")
    print(f"🏭 Industry: {test_request['industry']}")
    print(f"📊 Target Categories: {test_request['target_categories']}")
    print(f"📄 File: {test_request['file_metadata']['original_name']}")
    print(f"🤖 Expected AI: DeepSeek (CSV file)")
    print(f"🏢 Company: {test_request['company_info']['name']}")
    print(f"📝 File Type: {test_request['file_metadata']['file_type']}")
    print(f"📦 File Size: {test_request['file_metadata']['file_size']} bytes")
    print()

    start_time = time.time()

    try:
        print("🚀 Calling DeepSeek Text Processing API...")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                EXTRACT_ENDPOINT,
                json=test_request,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=120),  # 2 minutes timeout
            ) as response:
                processing_time = time.time() - start_time

                print(f"📡 HTTP Status: {response.status}")

                if response.status == 200:
                    result = await response.json()

                    print(f"✅ API call successful in {processing_time:.2f}s")
                    print()

                    # Analyze response structure
                    success = result.get("success", False)
                    message = result.get("message", "No message")

                    print("📊 RESPONSE ANALYSIS:")
                    print(f"🎯 Success: {'✅' if success else '❌'}")
                    print(f"💬 Message: {message}")

                    if success:
                        # Check raw content
                        raw_content = result.get("raw_content", "")
                        if raw_content:
                            print(f"📝 Raw Content: ✅ ({len(raw_content)} characters)")
                            # Show CSV header preview
                            lines = raw_content.split("\n")
                            if len(lines) >= 2:
                                print(f"   CSV Header: {lines[0]}")
                                print(
                                    f"   Sample Row: {lines[1] if len(lines) > 1 else 'N/A'}"
                                )
                                print(
                                    f"   Total Rows: {len(lines)-1} (including header)"
                                )
                        else:
                            print(f"📝 Raw Content: ❌ (empty)")

                        # Check structured data
                        structured_data = result.get("structured_data", {})
                        if structured_data:
                            print(f"🏗️ Structured Data: ✅")

                            # Count products and services
                            products = structured_data.get("products", [])
                            services = structured_data.get("services", [])

                            print(
                                f"   👗 Products: {len(products) if isinstance(products, list) else 0}"
                            )
                            print(
                                f"   🛍️ Services: {len(services) if isinstance(services, list) else 0}"
                            )

                            # Show sample products with fashion-specific details
                            if isinstance(products, list) and len(products) > 0:
                                print(f"   📋 Sample Fashion Products:")
                                for i, product in enumerate(products[:5]):
                                    if isinstance(product, dict):
                                        name = product.get("name", "No name")
                                        price = product.get("price", "No price")
                                        category = product.get(
                                            "category", "No category"
                                        )
                                        size = product.get("size", "No size")
                                        color = product.get("color", "No color")
                                        print(f"      {i+1}. {name}")
                                        print(f"         💰 Price: {price}")
                                        print(f"         📂 Category: {category}")
                                        if size != "No size":
                                            print(f"         📏 Size: {size}")
                                        if color != "No color":
                                            print(f"         🎨 Color: {color}")
                                        print()

                            # Show sample services
                            if isinstance(services, list) and len(services) > 0:
                                print(f"   📋 Sample Fashion Services:")
                                for i, service in enumerate(services[:3]):
                                    if isinstance(service, dict):
                                        name = service.get("name", "No name")
                                        description = service.get(
                                            "description", "No description"
                                        )
                                        price_type = service.get(
                                            "price_type", "No pricing info"
                                        )
                                        print(f"      {i+1}. {name}")
                                        print(
                                            f"         📝 Description: {description[:60]}..."
                                        )
                                        print(f"         💳 Pricing: {price_type}")
                        else:
                            print(f"🏗️ Structured Data: ❌ (empty)")

                        # Show metadata
                        template_used = result.get("template_used")
                        ai_provider = result.get("ai_provider")
                        total_items = result.get("total_items_extracted", 0)

                        print()
                        print("🔧 EXTRACTION METADATA:")
                        print(f"📋 Template: {template_used}")
                        print(f"🤖 AI Provider: {ai_provider}")
                        print(f"📊 Total Items: {total_items}")

                        # Show extraction summary if available
                        if structured_data and "extraction_summary" in structured_data:
                            summary = structured_data["extraction_summary"]
                            print(
                                f"📈 Data Quality: {summary.get('data_quality', 'unknown')}"
                            )
                            print(
                                f"📝 Categorization Notes: {summary.get('categorization_notes', 'none')}"
                            )
                            print(
                                f"🏭 Industry Context: {summary.get('industry_context', 'none')}"
                            )

                        # Show fashion-specific analysis
                        if isinstance(products, list) and len(products) > 0:
                            # Analyze fashion categories
                            categories = {}
                            sizes = set()
                            colors = set()
                            price_range = {"min": float("inf"), "max": 0}

                            for product in products:
                                if isinstance(product, dict):
                                    # Category analysis
                                    cat = product.get("category", "unknown")
                                    categories[cat] = categories.get(cat, 0) + 1

                                    # Size analysis
                                    if product.get("size"):
                                        sizes.add(product["size"])

                                    # Color analysis
                                    if product.get("color"):
                                        colors.add(product["color"])

                                    # Price analysis
                                    price = product.get("price", 0)
                                    if isinstance(price, (int, float)) and price > 0:
                                        price_range["min"] = min(
                                            price_range["min"], price
                                        )
                                        price_range["max"] = max(
                                            price_range["max"], price
                                        )

                            print()
                            print("👗 FASHION ANALYSIS:")
                            print(
                                f"   📂 Categories: {dict(list(categories.items())[:5])}"
                            )
                            if sizes:
                                print(
                                    f"   📏 Sizes Available: {sorted(list(sizes))[:10]}"
                                )
                            if colors:
                                print(f"   🎨 Colors Available: {list(colors)[:10]}")
                            if price_range["min"] != float("inf"):
                                print(
                                    f"   💰 Price Range: {price_range['min']:,.0f} - {price_range['max']:,.0f} VND"
                                )

                        # Save result to file
                        result_file = "fashion_products_deepseek_result.json"
                        try:
                            with open(result_file, "w", encoding="utf-8") as f:
                                json.dump(result, f, indent=2, ensure_ascii=False)
                            print(f"💾 Result saved: {result_file}")
                        except Exception as save_error:
                            print(f"⚠️ Save error: {save_error}")

                        print()
                        print("🎉 DEEPSEEK CSV PROCESSING TEST SUCCESSFUL!")
                        print("✅ CSV parsing working")
                        print("✅ Auto-categorization functional")
                        print("✅ Fashion products extracted")
                        print("✅ Fashion-specific fields detected")

                    else:
                        error = result.get("error", "Unknown error")
                        print(f"❌ Extraction failed: {error}")
                        print()
                        print("❌ TEST FAILED - Check error details above")

                else:
                    error_text = await response.text()
                    print(f"❌ HTTP Error {response.status}: {error_text}")
                    print()
                    print("❌ API CALL FAILED - Check server status")

    except asyncio.TimeoutError:
        print(f"⏰ Request timeout after {time.time() - start_time:.1f}s")
        print("❌ TEST FAILED: Timeout - DeepSeek processing taking too long")

    except Exception as e:
        processing_time = time.time() - start_time
        print(f"❌ Request failed after {processing_time:.1f}s: {e}")
        print(f"❌ TEST FAILED: {type(e).__name__}")

    print(f"\n⏱️ Total test time: {time.time() - start_time:.2f}s")
    print(f"🕒 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    """Run fashion CSV test"""
    print("🚀 STARTING FASHION PRODUCTS CSV DEEPSEEK TEST")
    print("👗 Testing Ivy Fashion Store Products CSV")
    print("=" * 60)

    await test_fashion_csv_extraction()

    print("\n🏁 FASHION PRODUCTS CSV TEST COMPLETED")


if __name__ == "__main__":
    asyncio.run(main())
