#!/usr/bin/env python3
"""
Simple test for /process-async endpoint
Test đơn giản cho endpoint /process-async - chỉ test endpoint và in kết quả
Hệ thống sẽ tự động gọi callback về https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback
"""

import json
import os
import time
from datetime import datetime
import requests

# Configuration
BASE_URL = "http://localhost:8000"
EXTRACT_ENDPOINT = "/api/extract/process-async"
TEST_FILE_URL = "https://static.agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/SanPham-AIA.txt"
COMPANY_ID = "test-async-timing"
OUTPUT_DIR = "test_outputs"

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_json(filename, data, description=""):
    """Save data to JSON file"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved {description}: {filepath}")
    except Exception as e:
        print(f"❌ Error saving {filename}: {str(e)}")


def test_async_endpoint():
    """Test the async endpoint - chỉ gọi và in kết quả"""
    print("🎯 Testing /process-async endpoint")
    print("=" * 60)
    print(
        "📋 Hệ thống sẽ tự động gọi callback về: https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback"
    )
    print("")

    # Prepare payload theo format đã test thành công
    async_payload = {
        "r2_url": TEST_FILE_URL,
        "company_id": COMPANY_ID + "-async",
        "industry": "insurance",
        "data_type": "products",  # String format (đã test OK)
        "file_name": "SanPham-AIA.txt",
        "file_type": "text/plain",
        "file_size": 1024000,
        "language": "vi",  # Use 'vi' (đã test OK)
        "target_categories": ["products", "services"],
        # KHÔNG cần callback_url vì hệ thống tự động gọi về https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback
        "company_info": {
            "name": "AIA Insurance Test",
            "description": "Test company for async extraction",
        },
    }

    # Save request payload
    save_json("async_request_payload.json", async_payload, "request payload")

    print(f"📤 Sending request to: {BASE_URL}{EXTRACT_ENDPOINT}")
    print(f"🏢 Company ID: {async_payload['company_id']}")
    print(f"🔗 R2 URL: {async_payload['r2_url']}")
    print(f"🏭 Industry: {async_payload['industry']}")
    print(f"📊 Data Type: {async_payload['data_type']}")
    print(f"🌐 Language: {async_payload['language']}")
    print("")

    try:
        # Send request
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}{EXTRACT_ENDPOINT}",
            json=async_payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TestScript/1.0",
            },
            timeout=30,
        )
        request_time = time.time() - start_time

        print(f"📊 Response Status: {response.status_code}")
        print(f"⏱️ Request Time: {request_time:.2f}s")

        # Save response details
        response_data = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else response.text
            ),
            "request_time": datetime.now().isoformat(),
            "response_time_seconds": request_time,
        }

        save_json("async_response.json", response_data, "endpoint response")

        if response.status_code == 200:
            result = response.json()
            task_id = result.get("task_id")

            print("✅ SUCCESS - Task queued successfully!")
            print("=" * 40)
            print(f"🆔 Task ID: {task_id}")
            print(f"📊 Status: {result.get('status')}")
            print(f"🏢 Company ID: {result.get('company_id')}")
            print(f"💬 Message: {result.get('message')}")
            print(f"⏱️ Estimated Time: {result.get('estimated_time')} seconds")
            print(f"❌ Error: {result.get('error') or 'None'}")
            print("")

            # Save just the result for easy inspection
            save_json("async_result_summary.json", result, "task result summary")

            print("📋 WORKFLOW INFO:")
            print("1. ✅ Task được đưa vào Redis queue")
            print("2. 🔄 ExtractionProcessingWorker sẽ xử lý AI extraction")
            print("3. 🔄 StorageProcessingWorker sẽ lưu vào Qdrant")
            print("4. 📞 Hệ thống sẽ tự động gọi callback về:")
            print("   https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback")
            print("")
            print("📁 Kiểm tra kết quả trong thư mục: test_outputs/")

        else:
            print("❌ FAILED - Request failed!")
            print("=" * 40)
            print(f"📊 Status Code: {response.status_code}")
            print(f"📝 Response Text: {response.text}")

            # Try to parse as JSON for better error display
            try:
                error_json = response.json()
                print(f"📋 Error Details:")
                if "detail" in error_json:
                    if isinstance(error_json["detail"], list):
                        for i, error in enumerate(error_json["detail"]):
                            print(f"   {i+1}. {error}")
                    else:
                        print(f"   {error_json['detail']}")
                save_json("async_error_response.json", error_json, "error response")
            except:
                save_json("async_error_text.txt", response.text, "error text")

    except requests.exceptions.RequestException as e:
        print(f"❌ REQUEST ERROR: {str(e)}")
        error_data = {
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "endpoint": f"{BASE_URL}{EXTRACT_ENDPOINT}",
        }
        save_json("async_request_error.json", error_data, "request error")


def test_validation_errors():
    """Test validation errors"""
    print("\n🧪 Testing validation errors")
    print("=" * 60)

    test_cases = [
        {
            "name": "missing_required_fields",
            "payload": {},
            "description": "Empty payload - should fail",
        },
        {
            "name": "invalid_industry",
            "payload": {
                "r2_url": TEST_FILE_URL,
                "company_id": "test-validation",
                "industry": "invalid_industry",
            },
            "description": "Invalid industry value",
        },
        {
            "name": "invalid_language",
            "payload": {
                "r2_url": TEST_FILE_URL,
                "company_id": "test-validation",
                "industry": "insurance",
                "data_type": "products",
                "language": "invalid_language",
            },
            "description": "Invalid language value",
        },
        {
            "name": "missing_file_name",
            "payload": {
                "r2_url": TEST_FILE_URL,
                "company_id": "test-validation",
                "industry": "insurance",
                "data_type": "products",
                "language": "vi",
                # Missing file_name
            },
            "description": "Missing required file_name field",
        },
    ]

    validation_results = []

    for i, test_case in enumerate(test_cases):
        print(f"\n🧪 Test case {i+1}: {test_case['description']}")

        try:
            response = requests.post(
                f"{BASE_URL}{EXTRACT_ENDPOINT}",
                json=test_case["payload"],
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            result = {
                "test_name": test_case["name"],
                "description": test_case["description"],
                "payload": test_case["payload"],
                "status_code": response.status_code,
                "response": (
                    response.json()
                    if response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else response.text
                ),
                "timestamp": datetime.now().isoformat(),
            }

            validation_results.append(result)

            print(f"   📊 Status: {response.status_code}")
            if response.status_code != 200:
                print(f"   ✅ Expected error response: {result['response']}")
            else:
                print(f"   ⚠️ Unexpected success: {result['response']}")

        except Exception as e:
            error_result = {
                "test_name": test_case["name"],
                "description": test_case["description"],
                "payload": test_case["payload"],
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            validation_results.append(error_result)
            print(f"   ❌ Request Error: {str(e)}")

    # Save all validation results
    save_json(
        "async_validation_tests.json", validation_results, "validation test results"
    )


def check_server_status():
    """Check if server is running"""
    print("🔍 Checking server status")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Server is running: {response.status_code}")

        # Show server info
        if response.status_code == 200:
            health_data = response.json()
            print(f"📊 Environment: {health_data.get('environment')}")
            print(f"📈 Uptime: {health_data.get('uptime', 0):.1f}s")
            print(f"🤖 AI Providers: {list(health_data.get('providers', {}).keys())}")

        return True

    except requests.exceptions.ConnectionError:
        print(f"❌ Server not running at {BASE_URL}")
        print("   Please start server: python serve.py")
        return False

    except Exception as e:
        print(f"⚠️ Server check failed: {str(e)}")
        return False


if __name__ == "__main__":
    print("🚀 Starting async endpoint tests")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print("")

    # Check server status first
    if not check_server_status():
        exit(1)

    print("")

    # Test main endpoint
    test_async_endpoint()

    # Test validation
    test_validation_errors()

    print(f"\n🎉 Tests completed!")
    print(f"📁 Check results in: {OUTPUT_DIR}/")
    print("")
    print("📋 Expected workflow after successful test:")
    print("1. Task được queue thành công")
    print("2. Workers sẽ xử lý AI extraction + Qdrant storage")
    print("3. Callback sẽ được gọi về backend API:")
    print("   https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback")
