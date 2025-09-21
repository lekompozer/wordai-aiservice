"""
Test Hybrid Strategy /process-async endpoint with real data
"""

import json
import os
import time
from datetime import datetime
from typing import Any, Dict
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import pytest

# Import the function to test using relative import
# from src.api.extraction_routes import process_extraction_async_hybrid
# Test endpoint /process-async với Hybrid Strategy workflow và dữ liệu
# Prepare async payload based on sync_payload structure


class CallbackServer:
    """Simple HTTP server to capture callback requests"""

    def __init__(self, port=8000):
        self.port = port
        self.captured_requests = []
        self.server = None
        self.thread = None

    def start(self):
        """Start the callback server"""
        handler = self.create_handler()
        self.server = HTTPServer(("localhost", self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        print(f"📞 Callback server started on http://localhost:{self.port}")

    def stop(self):
        """Stop the callback server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

    def create_handler(self):
        """Create request handler class"""
        captured_requests = self.captured_requests

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                # Read request body
                content_length = int(self.headers.get("Content-Length", 0))
                post_data = self.rfile.read(content_length)

                # Capture request details
                request_data = {
                    "timestamp": datetime.now().isoformat(),
                    "method": self.command,
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": post_data.decode("utf-8") if post_data else "",
                    "client_address": self.client_address,
                }

                captured_requests.append(request_data)
                print(f"📞 Callback received: {self.path}")

                # Send response
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok", "message": "Callback received"}')

            def log_message(self, format, *args):
                # Suppress default logging
                pass

        return CallbackHandler


class TestExtractionRoutesAsync:
    """Test class for async extraction routes"""

    # Test configuration
    BASE_URL = "http://localhost:8000"
    TEST_FILE_URL = "https://static.agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/SanPham-AIA.txt"
    COMPANY_ID = "test-async-timing"

    # Correct API endpoint
    EXTRACT_ENDPOINT = "/api/extract/process-async"

    # Output directory for test results
    OUTPUT_DIR = "test_outputs"

    @classmethod
    def setup_class(cls):
        """Setup test class - create output directory"""
        os.makedirs(cls.OUTPUT_DIR, exist_ok=True)
        print(f"📁 Created output directory: {cls.OUTPUT_DIR}")

    def save_test_result(self, filename: str, data: Any, description: str = ""):
        """Save test result to file"""
        filepath = os.path.join(self.OUTPUT_DIR, filename)

        try:
            if isinstance(data, (dict, list)):
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(str(data))

            if description:
                print(f"💾 Saved {description}: {filepath}")
            else:
                print(f"💾 Saved result: {filepath}")

        except Exception as e:
            print(f"❌ Error saving {filename}: {str(e)}")

    def test_process_async_with_callback(self):
        """Test /process-async endpoint with callback server"""
        print("\n🎯 Testing /process-async endpoint with callback capture")
        print("=" * 60)

        # Start callback server
        callback_server = CallbackServer(port=8899)
        callback_server.start()

        try:
            # Prepare async payload based on sync_payload structure
            async_payload = {
                "r2_url": self.TEST_FILE_URL,
                "company_id": self.COMPANY_ID + "-async",
                "industry": "insurance",
                "data_type": "products",  # Use string format for async (not list)
                "file_name": "SanPham-AIA.txt",
                "file_type": "text/plain",
                "file_size": 1024000,
                "language": "vi",  # Use 'vi' instead of 'vietnamese'
                "target_categories": ["products", "services"],
                "callback_url": "http://localhost:8899/callback",
                "company_info": {
                    "name": "AIA Insurance Test",
                    "description": "Test company for async extraction",
                },
            }

            # Save request payload
            self.save_test_result(
                "async_request_payload.json", async_payload, "async request payload"
            )

            print(
                f"📤 Sending async request to: {self.BASE_URL}/api/extraction/process-async"
            )
            print(f"🏢 Company ID: {async_payload['company_id']}")
            print(f"🔗 R2 URL: {async_payload['r2_url']}")
            print(f"📞 Callback URL: {async_payload['callback_url']}")

            # Send request to /process-async endpoint
            response = requests.post(
                f"{self.BASE_URL}/api/extraction/process-async",
                json=async_payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "TestScript/1.0",
                },
                timeout=30,
            )

            print(f"📊 Response Status: {response.status_code}")

            # Save response
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
            }

            self.save_test_result(
                "async_response.json", response_data, "async endpoint response"
            )

            if response.status_code == 200:
                result = response.json()
                task_id = result.get("task_id")
                print(f"✅ Task queued successfully!")
                print(f"🆔 Task ID: {task_id}")
                print(f"📊 Status: {result.get('status')}")
                print(f"⏱️ Estimated time: {result.get('estimated_time')} seconds")

                # Wait for callback with timeout
                print(f"\n⏳ Waiting for callback (max 60 seconds)...")
                wait_time = 0
                max_wait = 60

                while wait_time < max_wait:
                    if callback_server.captured_requests:
                        break
                    time.sleep(2)
                    wait_time += 2
                    if wait_time % 10 == 0:
                        print(f"⏳ Still waiting... ({wait_time}s)")

                # Save callback data
                if callback_server.captured_requests:
                    print(
                        f"📞 Callback received! ({len(callback_server.captured_requests)} requests)"
                    )

                    for i, callback_data in enumerate(
                        callback_server.captured_requests
                    ):
                        # Save full callback details
                        self.save_test_result(
                            f"callback_request_{i+1}.json",
                            callback_data,
                            f"callback request {i+1}",
                        )

                        # Parse and save callback payload separately
                        if callback_data.get("body"):
                            try:
                                callback_payload = json.loads(callback_data["body"])
                                self.save_test_result(
                                    f"callback_payload_{i+1}.json",
                                    callback_payload,
                                    f"callback payload {i+1}",
                                )

                                # Display callback summary
                                print(f"📞 Callback {i+1} Summary:")
                                print(
                                    f"   🆔 Task ID: {callback_payload.get('task_id')}"
                                )
                                print(f"   📊 Status: {callback_payload.get('status')}")
                                print(
                                    f"   🏢 Company: {callback_payload.get('company_id')}"
                                )

                                if "items_processed" in callback_payload:
                                    items = callback_payload["items_processed"]
                                    print(f"   📦 Items processed: {len(items)}")

                                    # Show sample items
                                    for j, item in enumerate(
                                        items[:3]
                                    ):  # Show first 3 items
                                        print(
                                            f"   📋 Item {j+1}: {item.get('title', 'No title')} ({item.get('category', 'No category')})"
                                        )

                                if "summary" in callback_payload:
                                    summary = callback_payload["summary"]
                                    print(f"   📊 Summary: {summary}")

                            except json.JSONDecodeError as e:
                                print(f"❌ Failed to parse callback body as JSON: {e}")

                        # Save callback headers separately
                        headers_data = {
                            "timestamp": callback_data["timestamp"],
                            "method": callback_data["method"],
                            "path": callback_data["path"],
                            "headers": callback_data["headers"],
                            "client_ip": callback_data["client_address"][0],
                        }

                        self.save_test_result(
                            f"callback_headers_{i+1}.json",
                            headers_data,
                            f"callback headers {i+1}",
                        )
                else:
                    print(f"⚠️ No callback received within {max_wait} seconds")

            else:
                print(f"❌ Request failed with status {response.status_code}")
                print(f"❌ Response: {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {str(e)}")
            error_data = {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "endpoint": f"{self.BASE_URL}/api/extraction/process-async",
            }
            self.save_test_result(
                "async_request_error.json", error_data, "request error"
            )

        finally:
            # Stop callback server
            callback_server.stop()
            print("🔴 Callback server stopped")

    def test_process_async_validation_errors(self):
        """Test /process-async endpoint with invalid payloads"""
        print("\n🧪 Testing /process-async validation errors")
        print("=" * 60)

        test_cases = [
            {
                "name": "missing_required_fields",
                "payload": {},
                "description": "Empty payload",
            },
            {
                "name": "invalid_industry",
                "payload": {
                    "r2_url": self.TEST_FILE_URL,
                    "company_id": "test-validation",
                    "industry": "invalid_industry",
                },
                "description": "Invalid industry value",
            },
            {
                "name": "invalid_data_type",
                "payload": {
                    "r2_url": self.TEST_FILE_URL,
                    "company_id": "test-validation",
                    "industry": "insurance",
                    "data_type": "invalid_type",
                },
                "description": "Invalid data_type value",
            },
        ]

        validation_results = []

        for i, test_case in enumerate(test_cases):
            print(f"\n🧪 Test case {i+1}: {test_case['description']}")

            try:
                response = requests.post(
                    f"{self.BASE_URL}/api/extraction/process-async",
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
                print(f"   📝 Response: {result['response']}")

            except Exception as e:
                error_result = {
                    "test_name": test_case["name"],
                    "description": test_case["description"],
                    "payload": test_case["payload"],
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
                validation_results.append(error_result)
                print(f"   ❌ Error: {str(e)}")

        # Save all validation results
        self.save_test_result(
            "async_validation_tests.json", validation_results, "validation test results"
        )

    def test_check_server_status(self):
        """Test if the server is running and accessible"""
        print("\n🔍 Checking server status")
        print("=" * 60)

        try:
            # Test basic health check
            response = requests.get(f"{self.BASE_URL}/health", timeout=5)
            print(f"✅ Server is running: {response.status_code}")

        except requests.exceptions.ConnectionError:
            print(f"❌ Server not running at {self.BASE_URL}")
            print("   Please start the server first: python serve.py")
            return False

        except Exception as e:
            print(f"⚠️ Server check failed: {str(e)}")
            return False

        return True


def run_tests():
    """Run all tests"""
    test_instance = TestExtractionRoutesAsync()
    test_instance.setup_class()

    # Check server status first
    if not test_instance.test_check_server_status():
        return

    # Run main tests
    test_instance.test_process_async_with_callback()
    test_instance.test_process_async_validation_errors()

    print(f"\n🎉 Tests completed! Check results in: {test_instance.OUTPUT_DIR}/")


if __name__ == "__main__":
    run_tests()
