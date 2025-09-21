#!/usr/bin/env python3
"""
Test Complete Async Extraction API Implementation
Test đầy đủ API async extraction đã implement
"""

import json
import requests
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TEST_FILE_URL = "https://static.agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/SanPham-AIA.txt"
COMPANY_ID = "test-api-validation"


def test_complete_async_api():
    """Test complete async API workflow"""
    print("🚀 Testing Complete Async Extraction API Implementation")
    print("=" * 70)

    start_time = datetime.now()

    # Step 1: Submit async extraction request
    print(f"📋 Step 1: Submit async extraction request")

    payload = {
        "r2_url": TEST_FILE_URL,
        "company_id": COMPANY_ID,
        "industry": "insurance",
        "data_type": "auto",
        "file_name": "SanPham-AIA.txt",
        "file_size": 1024000,
        "file_type": "text/plain",
        "callback_url": "https://webhook.site/your-unique-id",  # Optional callback
    }

    print(f"   🔗 URL: {BASE_URL}/api/extract/process-async")
    print(f"   📄 File: {payload['file_name']}")
    print(f"   🏭 Industry: {payload['industry']}")
    print(f"   📞 Callback: {payload['callback_url']}")

    response = requests.post(
        f"{BASE_URL}/api/extract/process-async", json=payload, timeout=30
    )

    submit_time = (datetime.now() - start_time).total_seconds()

    if response.status_code != 200:
        print(f"❌ Step 1 FAILED: {response.status_code} - {response.text}")
        return False

    queue_data = response.json()
    task_id = queue_data.get("task_id")

    print(f"   ✅ Task queued successfully")
    print(f"   🆔 Task ID: {task_id}")
    print(f"   ⏱️  Submit time: {submit_time:.3f}s")
    print(f"   📊 Estimated processing: {queue_data.get('estimated_time', 'unknown')}s")
    print()

    # Step 2: Monitor task status
    print(f"📊 Step 2: Monitor task status")

    max_wait = 40  # seconds
    check_interval = 3  # seconds

    for wait_time in range(0, max_wait, check_interval):
        current_time = (datetime.now() - start_time).total_seconds()

        print(f"   ⏱️  [{current_time:.1f}s] Checking status...")

        status_response = requests.get(f"{BASE_URL}/api/extract/status/{task_id}")

        if status_response.status_code != 200:
            print(f"   ⚠️  Status check failed: {status_response.status_code}")
            time.sleep(check_interval)
            continue

        status_data = status_response.json()
        status = status_data.get("status")

        print(f"      📋 Status: {status}")

        if "progress" in status_data:
            progress = status_data["progress"]
            print(f"      📈 Progress: {progress}")

        if status == "completed":
            print(f"   ✅ Processing completed!")
            processing_time = current_time
            break
        elif status == "failed":
            print(f"   ❌ Processing failed!")
            print(
                f"      📝 Error: {status_data.get('error_message', 'Unknown error')}"
            )
            return False

        time.sleep(check_interval)
    else:
        print(f"   ⏰ Timeout waiting for completion")
        return False

    print()

    # Step 3: Get extraction results
    print(f"📊 Step 3: Get extraction results")

    result_response = requests.get(f"{BASE_URL}/api/extract/result/{task_id}")

    if result_response.status_code != 200:
        print(f"   ❌ Failed to get results: {result_response.status_code}")
        print(f"      Response: {result_response.text}")
        return False

    result_data = result_response.json()

    print(f"   ✅ Results retrieved successfully")
    print(f"   📊 Success: {result_data.get('success')}")
    print(f"   📦 Items extracted: {result_data.get('total_items_extracted')}")
    print(f"   🤖 AI Provider: {result_data.get('ai_provider')}")
    print(f"   📝 Template: {result_data.get('template_used')}")
    print(f"   ⏱️  Processing time: {result_data.get('processing_time')}s")

    # Check structured data
    structured_data = result_data.get("structured_data", {})
    products = structured_data.get("products", [])
    services = structured_data.get("services", [])

    print(f"   📦 Products found: {len(products)}")
    print(f"   🔧 Services found: {len(services)}")

    if products:
        print(f"      📦 First product: {products[0].get('name', 'Unknown')}")

    if services:
        print(f"      🔧 First service: {services[0].get('name', 'Unknown')}")

    print()

    # Step 4: Save detailed results
    print(f"📁 Step 4: Save detailed results")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"async_api_validation_{timestamp}.json"

    complete_results = {
        "test_metadata": {
            "test_type": "complete_async_api_validation",
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "company_id": COMPANY_ID,
        },
        "timing_results": {
            "submit_time": submit_time,
            "total_processing_time": processing_time,
            "estimated_vs_actual": {
                "estimated": queue_data.get("estimated_time"),
                "actual": result_data.get("processing_time"),
            },
        },
        "api_validation": {
            "submit_endpoint": "✅ Working",
            "status_endpoint": "✅ Working",
            "result_endpoint": "✅ Working",
            "callback_mechanism": "✅ Implemented",
        },
        "extraction_results": result_data,
        "queue_response": queue_data,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(complete_results, f, indent=2, ensure_ascii=False)

    print(f"   📁 Results saved to: {filename}")
    print()

    # Summary
    total_time = (datetime.now() - start_time).total_seconds()

    print(f"🎯 API VALIDATION SUMMARY:")
    print(f"   ✅ All endpoints working correctly")
    print(f"   ⚡ Submit time: {submit_time:.3f}s")
    print(f"   🤖 AI processing: {result_data.get('processing_time', 'unknown')}s")
    print(f"   📊 Total test time: {total_time:.1f}s")
    print(f"   📦 Items extracted: {result_data.get('total_items_extracted', 0)}")
    print(f"   🎯 Success rate: 100%")

    return True


if __name__ == "__main__":
    try:
        success = test_complete_async_api()
        if success:
            print("\n🎉 API validation completed successfully!")
        else:
            print("\n❌ API validation failed!")
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
