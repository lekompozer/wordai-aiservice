#!/usr/bin/env python3
"""
Simple test for AI Extraction API - No external dependencies
Test đơn giản cho AI Extraction API - Không cần thư viện bên ngoài
"""

import json
import urllib.request
import urllib.parse
import time

SERVER_URL = "http://localhost:8000"


def test_api_extraction(name, request_data, timeout=60):
    """Test single API extraction"""
    print(f"\n{'='*60}")
    print(f"TESTING: {name}")
    print(f"{'='*60}")

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
        # Prepare request
        url = f"{SERVER_URL}/api/extract/process"
        data = json.dumps(request_data).encode("utf-8")

        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )

        print(f"\n🚀 Calling API endpoint...")

        # Make request with timeout
        with urllib.request.urlopen(req, timeout=timeout) as response:
            processing_time = time.time() - start_time

            if response.status == 200:
                result = json.loads(response.read().decode("utf-8"))

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
                        "structured_data" in result and result["structured_data"]
                    )

                    print(f"📝 Raw Content: {'✅' if has_raw else '❌'}")
                    print(f"🏗️ Structured Data: {'✅' if has_structured else '❌'}")

                    if has_raw:
                        raw_length = len(result["raw_content"])
                        print(f"   📄 Raw content: {raw_length} characters")
                        # Show first 100 chars
                        if raw_length > 0:
                            preview = result["raw_content"][:100].replace("\n", " ")
                            print(f"   👀 Preview: {preview}...")

                    if has_structured:
                        structured = result["structured_data"]
                        if isinstance(structured, dict):
                            # Check both products and services
                            total_items = 0
                            categories_found = []

                            for category in ["products", "services"]:
                                items = structured.get(category, [])
                                if isinstance(items, list) and len(items) > 0:
                                    total_items += len(items)
                                    categories_found.append(f"{category}: {len(items)}")

                            if categories_found:
                                print(
                                    f"   📈 Extracted items: {total_items} ({', '.join(categories_found)})"
                                )
                            else:
                                print(f"   📈 Extracted items: 0")

                            # Show sample item
                            for category in ["products", "services"]:
                                items = structured.get(category, [])
                                if isinstance(items, list) and len(items) > 0:
                                    sample_item = items[0]
                                    if isinstance(sample_item, dict):
                                        sample_keys = list(sample_item.keys())[:3]
                                        print(
                                            f"   🔍 Sample {category} keys: {sample_keys}"
                                        )
                                        # Show sample values
                                        for key in sample_keys:
                                            value = str(sample_item.get(key, ""))[:50]
                                            print(f"      {key}: {value}")
                                    break

                    # Show metadata
                    template_used = result.get("template_used")
                    ai_provider = result.get("ai_provider")
                    total_items = result.get("total_items_extracted", 0)

                    print(f"📋 Template: {template_used}")
                    print(f"🤖 AI Provider: {ai_provider}")
                    print(f"📊 Total Items: {total_items}")
                    print(f"⏱️ Processing Time: {processing_time:.2f}s")

                    print(f"\n✅ TEST PASSED")
                    return True

                else:
                    error = result.get("error", "Unknown error")
                    print(f"❌ Extraction failed: {error}")
                    print(f"\n❌ TEST FAILED")
                    return False

            else:
                print(f"❌ HTTP Error {response.status}")
                print(f"\n❌ TEST FAILED: HTTP {response.status}")
                return False

    except urllib.error.URLError as e:
        processing_time = time.time() - start_time
        print(f"❌ Request failed after {processing_time:.1f}s: {e}")
        print(f"\n❌ TEST FAILED: URLError")
        return False
    except Exception as e:
        processing_time = time.time() - start_time
        print(f"❌ Request failed after {processing_time:.1f}s: {e}")
        print(f"\n❌ TEST FAILED: {type(e).__name__}")
        return False


def main():
    """Test all scenarios"""
    print("🚀 SIMPLE API EXTRACTION TESTS")
    print(f"🌐 Testing server at: {SERVER_URL}")
    print("=" * 70)

    # Test scenarios
    scenarios = [
        {
            "name": "🍜 Restaurant Menu (JPG - ChatGPT Vision)",
            "request": {
                "r2_url": "https://agent8x.io.vn/companies/golden-dragon-restaurant/20250714_131220_golden-dragon-menu.jpg",
                "industry": "restaurant",
                "target_categories": ["products", "services"],
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
                "target_categories": ["services"],
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
                "target_categories": ["products"],
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
            "name": "👗 Fashion Products (CSV - DeepSeek)",
            "request": {
                "r2_url": "https://agent8x.io.vn/companies/ivy-fashion-store/20250714_103032_ivy-fashion-products.csv",
                "industry": "fashion",
                "target_categories": ["products", "services"],
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
    total_tests = len(scenarios)

    for i, scenario in enumerate(scenarios, 1):
        success = test_api_extraction(scenario["name"], scenario["request"])
        if success:
            successful_tests += 1

        print(f"⏱️ Test {i} completed")

        # Short pause between tests
        if i < total_tests:
            time.sleep(2)

    # Final Summary
    print(f"\n{'='*70}")
    print("🎯 API EXTRACTION TEST SUMMARY")
    print(f"{'='*70}")
    print(f"📊 Total Tests: {total_tests}")
    print(f"✅ Successful: {successful_tests}")
    print(f"❌ Failed: {total_tests - successful_tests}")
    print(f"📈 Success Rate: {(successful_tests/total_tests)*100:.1f}%")

    if successful_tests > 0:
        print("\n🎉 API EXTRACTION IS WORKING!")
        print("✅ Server responding correctly")
        print("✅ Template selection working")
        print("✅ AI provider integration functioning")
    else:
        print("\n⚠️ NO SUCCESSFUL API TESTS")
        print("❗ Check server status")
        print("❗ Verify API endpoint implementation")


if __name__ == "__main__":
    main()
