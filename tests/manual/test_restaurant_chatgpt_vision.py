#!/usr/bin/env python3
"""
Test Single Restaurant Menu JPG with ChatGPT Vision
Test riêng file menu nhà hàng JPG với ChatGPT Vision
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

SERVER_URL = "http://localhost:8000"
EXTRACT_ENDPOINT = f"{SERVER_URL}/api/extract/process"


async def test_restaurant_menu_extraction():
    """Test ChatGPT Vision with restaurant menu JPG"""
    print("🍜 TESTING RESTAURANT MENU EXTRACTION")
    print("=" * 60)
    print(f"🌐 Server: {SERVER_URL}")
    print(f"📡 Endpoint: {EXTRACT_ENDPOINT}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Test data - Restaurant Menu JPG
    test_request = {
        "r2_url": "https://agent8x.io.vn/companies/golden-dragon-restaurant/20250714_131220_golden-dragon-menu.jpg",
        "industry": "restaurant",  # Top level field
        "file_metadata": {
            "original_name": "20250714_131220_golden-dragon-menu.jpg",
            "content_type": "image/jpeg",
            "file_size": 2048000,
        },
        "target_categories": ["products", "services"],  # Auto-categorization
        "company_info": {
            "name": "Golden Dragon Restaurant",
            "industry": "restaurant",
            "description": "Traditional Vietnamese restaurant",
        },
        "language": "vi",
        "upload_to_qdrant": False,
    }

    print("📋 TEST REQUEST DETAILS:")
    print(f"🔗 R2 URL: {test_request['r2_url']}")
    print(f"🏭 Industry: {test_request['industry']}")
    print(f"📊 Target Categories: {test_request['target_categories']}")
    print(f"📄 File: {test_request['file_metadata']['original_name']}")
    print(f"🤖 Expected AI: ChatGPT Vision (JPG file)")
    print(f"🏢 Company: {test_request['company_info']['name']}")
    print()

    start_time = time.time()

    try:
        print("🚀 Calling ChatGPT Vision API...")

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
                            print(
                                f"   Preview: {raw_content[:100]}..."
                                if len(raw_content) > 100
                                else f"   Content: {raw_content}"
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
                                f"   🍽️ Products: {len(products) if isinstance(products, list) else 0}"
                            )
                            print(
                                f"   🛎️ Services: {len(services) if isinstance(services, list) else 0}"
                            )

                            # Show sample products
                            if isinstance(products, list) and len(products) > 0:
                                print(f"   📋 Sample Products:")
                                for i, product in enumerate(products[:3]):
                                    if isinstance(product, dict):
                                        name = product.get("name", "No name")
                                        price = product.get("price", "No price")
                                        print(f"      {i+1}. {name} - {price}")

                            # Show sample services
                            if isinstance(services, list) and len(services) > 0:
                                print(f"   📋 Sample Services:")
                                for i, service in enumerate(services[:3]):
                                    if isinstance(service, dict):
                                        name = service.get("name", "No name")
                                        description = service.get(
                                            "description", "No description"
                                        )
                                        print(
                                            f"      {i+1}. {name} - {description[:50]}..."
                                        )
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
                                f"📝 Notes: {summary.get('extraction_notes', 'none')}"
                            )

                        # Save result to file
                        result_file = "restaurant_menu_chatgpt_vision_result.json"
                        try:
                            with open(result_file, "w", encoding="utf-8") as f:
                                json.dump(result, f, indent=2, ensure_ascii=False)
                            print(f"💾 Result saved: {result_file}")
                        except Exception as save_error:
                            print(f"⚠️ Save error: {save_error}")

                        print()
                        print("🎉 CHATGPT VISION TEST SUCCESSFUL!")
                        print("✅ Image analysis working")
                        print("✅ Auto-categorization functional")
                        print("✅ Restaurant menu extracted")

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
        print("❌ TEST FAILED: Timeout - ChatGPT Vision taking too long")

    except Exception as e:
        processing_time = time.time() - start_time
        print(f"❌ Request failed after {processing_time:.1f}s: {e}")
        print(f"❌ TEST FAILED: {type(e).__name__}")

    print(f"\n⏱️ Total test time: {time.time() - start_time:.2f}s")
    print(f"🕒 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    """Run restaurant menu test"""
    print("🚀 STARTING RESTAURANT MENU CHATGPT VISION TEST")
    print("🍜 Testing Golden Dragon Restaurant Menu JPG")
    print("=" * 60)

    await test_restaurant_menu_extraction()

    print("\n🏁 RESTAURANT MENU TEST COMPLETED")


if __name__ == "__main__":
    asyncio.run(main())
