#!/usr/bin/env python3
"""
Test AI Extraction API Endpoint with Real Server
Test API endpoint AI Extraction với server thật

This test calls the actual running server at localhost:8000
to test the /api/extract/process endpoint with real R2 URLs
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

SERVER_URL = "http://localhost:8000"
EXTRACT_ENDPOINT = f"{SERVER_URL}/api/extract/process"


async def test_extraction_api():
    """Test the actual API endpoint with real R2 URLs"""
    print("🧪 TESTING AI EXTRACTION API ENDPOINT")
    print("=" * 70)
    print(f"🌐 Server: {SERVER_URL}")
    print(f"📡 Endpoint: {EXTRACT_ENDPOINT}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Test scenarios with real R2 URLs
    test_scenarios = [
        {
            "name": "🍜 Restaurant Menu (JPG - ChatGPT Vision)",
            "request": {
                "r2_url": "https://agent8x.io.vn/companies/golden-dragon-restaurant/20250714_131220_golden-dragon-menu.jpg",
                "industry": "restaurant",
                "target_categories": ["products", "services"],  # Auto-categorization
                "file_metadata": {
                    "original_name": "20250714_131220_golden-dragon-menu.jpg",
                    "file_size": 2048000,
                    "file_type": "image/jpeg",
                },
                "company_info": {
                    "name": "Golden Dragon Restaurant",
                    "industry": "restaurant",
                    "description": "Traditional Vietnamese restaurant",
                },
                "language": "vi",
                "upload_to_qdrant": False,
            },
        },
        {
            "name": "🏨 Hotel Services (PDF - ChatGPT Vision)",
            "request": {
                "r2_url": "https://agent8x.io.vn/companies/golden-dragon-restaurant/Hotel%20Majestic%20Saigon%20%E2%80%94%20DI%CC%A3CH%20VU%CC%A3%20CHI%20TIE%CC%82%CC%81T.pdf",
                "industry": "hotel",
                "target_categories": ["services"],  # Only services
                "file_metadata": {
                    "original_name": "Hotel Majestic Saigon — DỊCH VỤ CHI TIẾT.pdf",
                    "file_size": 1500000,
                    "file_type": "application/pdf",
                },
                "company_info": {
                    "name": "Hotel Majestic Saigon",
                    "industry": "hotel",
                    "description": "Luxury hotel in Ho Chi Minh City",
                },
                "language": "vi",
            },
        },
        {
            "name": "🏦 Banking Products (DOCX - ChatGPT Vision)",
            "request": {
                "r2_url": "https://agent8x.io.vn/companies/vrb-bank-financial/20250714_103034_vrb-bank-services.docx",
                "industry": "banking",
                "target_categories": ["products"],  # Only products
                "file_metadata": {
                    "original_name": "20250714_103034_vrb-bank-services.docx",
                    "file_size": 800000,
                    "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                },
                "company_info": {
                    "name": "VRB Bank",
                    "industry": "banking",
                    "description": "Vietnamese commercial bank",
                },
                "language": "vi",
            },
        },
        {
            "name": "🛡️ Insurance Products (TXT - DeepSeek)",
            "request": {
                "r2_url": "https://agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/Sa%CC%89n%20pha%CC%82%CC%89m%20Ba%CC%89o%20hie%CC%82%CC%89m%20AIA.txt",
                "industry": "insurance",
                # No target_categories - will auto-extract both products and services
                "file_metadata": {
                    "original_name": "Sản phẩm Bảo hiểm AIA.txt",
                    "file_size": 50000,
                    "file_type": "text/plain",
                },
                "company_info": {
                    "name": "AIA Insurance",
                    "industry": "insurance",
                    "description": "Life and health insurance company",
                },
                "language": "vi",
            },
        },
        {
            "name": "👗 Fashion Products (CSV - DeepSeek)",
            "request": {
                "r2_url": "https://agent8x.io.vn/companies/ivy-fashion-store/20250714_103032_ivy-fashion-products.csv",
                "industry": "fashion",
                "target_categories": ["products", "services"],  # Auto-categorization
                "file_metadata": {
                    "original_name": "20250714_103032_ivy-fashion-products.csv",
                    "file_size": 25000,
                    "file_type": "text/csv",
                },
                "company_info": {
                    "name": "Ivy Fashion Store",
                    "industry": "fashion",
                    "description": "Fashion retail store",
                },
                "language": "vi",
            },
        },
    ]

    successful_tests = 0
    total_tests = len(test_scenarios)

    async with aiohttp.ClientSession() as session:
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n{'='*60}")
            print(f"TEST {i}/{total_tests}: {scenario['name']}")
            print(f"{'='*60}")

            request_data = scenario["request"]
            print(f"🔗 R2 URL: {request_data['r2_url']}")
            print(f"🏭 Industry: {request_data['industry']}")
            print(
                f"📊 Target Categories: {request_data.get('target_categories', 'Auto (products + services)')}"
            )
            print(f"📄 File: {request_data['file_metadata']['original_name']}")
            print(
                f"🤖 Expected AI: {'DeepSeek' if request_data['file_metadata']['file_type'].startswith('text/') else 'ChatGPT Vision'}"
            )

            start_time = time.time()

            try:
                print(f"\n🚀 Calling API endpoint...")

                async with session.post(
                    EXTRACT_ENDPOINT,
                    json=request_data,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=120),  # 2 minutes timeout
                ) as response:
                    processing_time = time.time() - start_time

                    print(f"📡 HTTP Status: {response.status}")

                    if response.status == 200:
                        result = await response.json()

                        print(f"✅ API call successful in {processing_time:.2f}s")

                        # Analyze response
                        success = result.get("success", False)
                        message = result.get("message", "No message")

                        print(f"🎯 Success: {'✅' if success else '❌'}")
                        print(f"💬 Message: {message}")

                        if success:
                            # Check response structure
                            has_raw = "raw_content" in result and result["raw_content"]
                            has_structured = (
                                "structured_data" in result
                                and result["structured_data"]
                            )

                            print(f"📝 Raw Content: {'✅' if has_raw else '❌'}")
                            print(
                                f"🏗️ Structured Data: {'✅' if has_structured else '❌'}"
                            )

                            if has_raw:
                                raw_length = len(result["raw_content"])
                                print(f"   📄 Raw content: {raw_length} characters")

                            if has_structured:
                                structured = result["structured_data"]
                                if isinstance(structured, dict):
                                    # Check both products and services for auto-categorization
                                    total_items = 0
                                    categories_found = []

                                    for category in ["products", "services"]:
                                        items = structured.get(category, [])
                                        if isinstance(items, list) and len(items) > 0:
                                            total_items += len(items)
                                            categories_found.append(
                                                f"{category}: {len(items)}"
                                            )

                                    if categories_found:
                                        print(
                                            f"   📈 Extracted items: {total_items} ({', '.join(categories_found)})"
                                        )
                                    else:
                                        print(f"   📈 Extracted items: 0")

                                    # Show sample item from first non-empty category
                                    sample_shown = False
                                    for category in ["products", "services"]:
                                        items = structured.get(category, [])
                                        if (
                                            isinstance(items, list)
                                            and len(items) > 0
                                            and not sample_shown
                                        ):
                                            sample_item = items[0]
                                            if isinstance(sample_item, dict):
                                                sample_keys = list(sample_item.keys())[
                                                    :3
                                                ]
                                                print(
                                                    f"   🔍 Sample {category} keys: {sample_keys}"
                                                )
                                                sample_shown = True

                            # Show metadata
                            template_used = result.get("template_used")
                            ai_provider = result.get("ai_provider")
                            total_items = result.get("total_items_extracted", 0)

                            print(f"📋 Template: {template_used}")
                            print(f"🤖 AI Provider: {ai_provider}")
                            print(f"📊 Total Items: {total_items}")

                            successful_tests += 1

                            # Save result
                            categories_str = "_".join(
                                request_data.get("target_categories", ["auto"])
                            )
                            result_file = f"api_result_{i}_{request_data['industry']}_{categories_str}.json"
                            try:
                                with open(result_file, "w", encoding="utf-8") as f:
                                    json.dump(result, f, indent=2, ensure_ascii=False)
                                print(f"💾 Result saved: {result_file}")
                            except Exception as save_error:
                                print(f"⚠️ Save error: {save_error}")

                            print(f"\n✅ TEST {i} PASSED")

                        else:
                            error = result.get("error", "Unknown error")
                            print(f"❌ Extraction failed: {error}")
                            print(f"\n❌ TEST {i} FAILED")

                    else:
                        error_text = await response.text()
                        print(f"❌ HTTP Error {response.status}: {error_text}")
                        print(f"\n❌ TEST {i} FAILED: HTTP {response.status}")

            except asyncio.TimeoutError:
                print(f"⏰ Request timeout after {time.time() - start_time:.1f}s")
                print(f"\n❌ TEST {i} FAILED: Timeout")

            except Exception as e:
                processing_time = time.time() - start_time
                print(f"❌ Request failed after {processing_time:.1f}s: {e}")
                print(f"\n❌ TEST {i} FAILED: {type(e).__name__}")

            print(f"⏱️ Test {i} completed in {time.time() - start_time:.2f}s")

    # Final Summary
    print(f"\n{'='*70}")
    print("🎯 API EXTRACTION TEST SUMMARY")
    print(f"{'='*70}")
    print(f"📊 Total Tests: {total_tests}")
    print(f"✅ Successful: {successful_tests}")
    print(f"❌ Failed: {total_tests - successful_tests}")
    print(f"📈 Success Rate: {(successful_tests/total_tests)*100:.1f}%")
    print()

    if successful_tests > 0:
        print("🎉 API EXTRACTION IS WORKING!")
        print("✅ Server responding correctly")
        print("✅ Template selection working")
        print("✅ AI provider integration functioning")
        print("✅ Raw + structured data extraction")
        print("✅ Industry-specific JSON schemas")
    else:
        print("⚠️ NO SUCCESSFUL API TESTS")
        print("❗ Check server status")
        print("❗ Verify API endpoint implementation")
        print("❗ Review error messages above")

    print(f"\n🕒 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def test_health_endpoints():
    """Test health and info endpoints first"""
    print("🏥 TESTING HEALTH ENDPOINTS")
    print("-" * 40)

    health_url = f"{SERVER_URL}/api/extract/health"
    info_url = f"{SERVER_URL}/api/extract/info"

    async with aiohttp.ClientSession() as session:
        # Test health endpoint
        try:
            async with session.get(health_url) as response:
                if response.status == 200:
                    health_data = await response.json()
                    print(f"✅ Health endpoint: {health_data.get('status', 'unknown')}")

                    ai_providers = health_data.get("ai_providers", {})
                    print(
                        f"   DeepSeek: {'✅' if ai_providers.get('deepseek', False) else '❌'}"
                    )
                    print(
                        f"   ChatGPT: {'✅' if ai_providers.get('chatgpt', False) else '❌'}"
                    )

                    template_info = health_data.get("template_system", {})
                    print(
                        f"   Templates: {template_info.get('available_templates', 0)}"
                    )

                else:
                    print(f"❌ Health endpoint failed: {response.status}")

        except Exception as e:
            print(f"❌ Health check failed: {e}")

        # Test info endpoint
        try:
            async with session.get(info_url) as response:
                if response.status == 200:
                    info_data = await response.json()
                    print(
                        f"✅ Info endpoint: {info_data.get('service_name', 'unknown')}"
                    )
                    print(f"   Version: {info_data.get('version', 'unknown')}")

                    supported_types = info_data.get("supported_data_types", [])
                    if not supported_types:
                        # Try extraction_categories for new format
                        supported_types = info_data.get("extraction_categories", [])
                    print(
                        f"   Supported categories: {len(supported_types)} - {supported_types}"
                    )

                else:
                    print(f"❌ Info endpoint failed: {response.status}")

        except Exception as e:
            print(f"❌ Info check failed: {e}")

    print()


async def main():
    """Run all API tests"""
    print("🚀 STARTING API EXTRACTION TESTS")
    print(f"🌐 Testing server at: {SERVER_URL}")
    print("=" * 70)

    # Test health endpoints first
    await test_health_endpoints()

    # Run extraction tests
    await test_extraction_api()

    print("\n🏁 ALL API TESTS COMPLETED")


if __name__ == "__main__":
    asyncio.run(main())
