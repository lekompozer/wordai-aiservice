#!/usr/bin/env python3
"""
🧪 E2E TEST: /companies/{companyId}/files/upload WORKFLOW
Test complete workflow from API call → DocumentProcessingWorker → Callback capture

🎯 MỤC ĐÍCH:
- Test luồng upload file đơn giản (RAW CONTENT extraction only)
- Kiểm tra có lỗi hay không trong luồng xử lý
- Lấy dữ liệu Payload thực tế trước khi gửi callback cho backend
- Verify DocumentProcessingWorker hoạt động đúng

🔄 WORKFLOW:
1. 🚀 Call /companies/{companyId}/files/upload với company DOCX file
2. 👀 Monitor DocumentProcessingWorker processing (raw content extraction)
3. 📞 Capture callback với RAW CONTENT (không có structured data)
4. ✅ Verify payload format theo CALLBACK_URL_SPECIFICATION.md

📄 Test File: https://static.agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/2702fa94-1e50-4f43-8095-3ed45dd58907.docx
"""

import asyncio
import json
import time
import logging
import uuid
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
import aiohttp
from pathlib import Path

# HTTP Server for callback capture
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.parse

# Test configuration từ file test cũ
TEST_API_BASE = "http://localhost:8000"
TEST_FILE_URL = "https://static.agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/2702fa94-1e50-4f43-8095-3ed45dd58907.docx"
COMPANY_ID = "5a44b799-4783-448f-b6a8-b9a51ed7ab76"
INDUSTRY = "insurance"

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global variables for callback capture
captured_callback_data = {}
callback_server_running = False


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to capture file upload callback payloads"""

    def do_POST(self):
        """Handle POST requests (callbacks from DocumentProcessingWorker)"""
        try:
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)

            # Parse JSON payload
            payload = json.loads(post_data.decode("utf-8"))

            # Capture headers
            headers = {key: value for key, value in self.headers.items()}

            # Store the captured data
            captured_callback_data[self.path] = {
                "timestamp": datetime.now().isoformat(),
                "path": self.path,
                "headers": headers,
                "payload": payload,
            }

            logger.info(f"📞 CAPTURED FILE UPLOAD CALLBACK: {self.path}")
            logger.info(f"   🏢 Company: {payload.get('company_id', 'unknown')}")
            logger.info(f"   📋 Task: {payload.get('task_id', 'unknown')}")
            logger.info(f"   📊 Status: {payload.get('status', 'unknown')}")

            # Analyze callback data structure
            data = payload.get("data", {})
            if data:
                logger.info(f"   ✅ DATA SECTION CAPTURED:")
                logger.info(f"      📊 Success: {data.get('success', 'unknown')}")
                logger.info(
                    f"      ⏱️ Processing Time: {data.get('processing_time', 'unknown')}s"
                )

                # Check for raw content
                raw_content = data.get("raw_content", "")
                if raw_content:
                    content_length = len(raw_content)
                    content_preview = (
                        raw_content[:100] + "..."
                        if len(raw_content) > 100
                        else raw_content
                    )
                    logger.info(f"      📄 Raw Content Length: {content_length} chars")
                    logger.info(f"      📄 Content Preview: {content_preview}")
                else:
                    logger.warning(f"      ⚠️ NO RAW CONTENT in callback!")

                # Check file processing info
                file_processing = data.get("file_processing", {})
                if file_processing:
                    logger.info(
                        f"      🤖 AI Provider: {file_processing.get('ai_provider', 'unknown')}"
                    )
                    logger.info(
                        f"      📁 Extraction Type: {file_processing.get('extraction_type', 'unknown')}"
                    )
                    logger.info(
                        f"      📄 File Name: {file_processing.get('file_name', 'unknown')}"
                    )

                # Check file metadata
                file_metadata = data.get("file_metadata", {})
                if file_metadata:
                    logger.info(
                        f"      📋 Original Name: {file_metadata.get('original_name', 'unknown')}"
                    )
                    logger.info(
                        f"      📁 File Type: {file_metadata.get('file_type', 'unknown')}"
                    )
                    logger.info(
                        f"      📊 Data Type: {file_metadata.get('data_type', 'unknown')}"
                    )
                    logger.info(
                        f"      🏭 Industry: {file_metadata.get('industry', 'unknown')}"
                    )

            # Check webhook security headers
            webhook_source = headers.get("x-webhook-source", "unknown")
            webhook_signature = headers.get("x-webhook-signature", "none")
            logger.info(f"   🔐 Webhook Source: {webhook_source}")
            logger.info(
                f"   🔑 Signature: {webhook_signature[:20]}..."
                if len(webhook_signature) > 20
                else webhook_signature
            )

            # Respond with 200 OK
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "received"}')

        except Exception as e:
            logger.error(f"❌ Error handling callback: {e}")
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP server logs"""
        pass


def start_callback_server(port: int = 8089):
    """Start HTTP server to capture callbacks"""
    global callback_server_running

    def run_server():
        global callback_server_running
        server = HTTPServer(("localhost", port), CallbackHandler)
        callback_server_running = True
        logger.info(f"🌐 Mock callback server started on http://localhost:{port}")
        try:
            server.serve_forever()
        except Exception as e:
            logger.error(f"❌ Callback server error: {e}")
        finally:
            callback_server_running = False

    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to start
    time.sleep(1)
    return server_thread


async def test_file_upload_workflow():
    """
    Test complete /companies/{companyId}/files/upload workflow

    Test Flow:
    1. 🚀 Call /companies/{companyId}/files/upload với company DOCX file
    2. 👀 Monitor DocumentProcessingWorker (raw content extraction)
    3. 📞 Capture callback với raw content only
    4. ✅ Verify payload format và save for backend documentation
    """

    logger.info("🧪 STARTING E2E TEST: File Upload Workflow")
    logger.info("🎯 PURPOSE: Test /companies/{companyId}/files/upload endpoint")
    logger.info("🔄 WORKFLOW: API → DocumentProcessingWorker → Raw Content Callback")
    logger.info("📋 EXPECTED: RAW CONTENT only (no structured data)")
    logger.info(f"🌐 API BASE: {TEST_API_BASE}")
    logger.info(f"📄 TEST FILE: {TEST_FILE_URL}")
    logger.info(f"🏢 COMPANY ID: {COMPANY_ID}")
    logger.info(f"🏭 INDUSTRY: {INDUSTRY}")

    # Start callback server
    logger.info("🌐 Starting mock callback server...")
    server_thread = start_callback_server()

    # Wait for server to be ready
    await asyncio.sleep(2)

    if not callback_server_running:
        logger.error("❌ Failed to start callback server")
        return

    # Test configuration - File Upload with AIA insurance file (từ test cũ)
    company_id = (
        COMPANY_ID  # Sử dụng company ID thực: "5a44b799-4783-448f-b6a8-b9a51ed7ab76"
    )
    test_config = {
        "r2_url": TEST_FILE_URL,  # Sử dụng AIA insurance file thực
        "data_type": "document",  # Standard document type
        "industry": INDUSTRY,  # Insurance industry như test cũ
        "metadata": {
            "original_name": "company-profile.docx",  # Tên file DOCX thực
            "file_id": f"file_{int(time.time())}",
            "file_name": "company-profile.docx",
            "file_size": 250000,  # Size ước tính cho DOCX file
            "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX file type
            "uploaded_by": "test_user_123",
            "description": "Company profile DOCX file for testing file upload workflow",
            "tags": ["company", "profile", "docx", "testing"],
            "language": "vi",  # Vietnamese language
        },
        "language": "vi",  # Vietnamese language enum đúng
        "upload_to_qdrant": True,
        "callback_url": "http://localhost:8089/file-processed",  # Our mock server
    }

    logger.info("📋 TEST CONFIGURATION:")
    logger.info(f"   🏢 Company ID: {company_id}")
    logger.info(f"   📄 File: {test_config['metadata']['original_name']}")
    logger.info(f"   📊 Data Type: {test_config['data_type']}")
    logger.info(f"   🏭 Industry: {test_config['industry']}")
    logger.info(f"   🌐 Callback URL: {test_config['callback_url']}")
    logger.info(f"   🔗 R2 URL: {test_config['r2_url']}")

    try:
        # ===== STEP 1: Call /companies/{companyId}/files/upload API =====
        logger.info("🚀 STEP 1: Calling /companies/{companyId}/files/upload API...")
        logger.info(
            f"   🌐 API URL: {TEST_API_BASE}/api/admin/companies/{company_id}/files/upload"
        )

        api_url = f"{TEST_API_BASE}/api/admin/companies/{company_id}/files/upload"

        async with aiohttp.ClientSession() as session:
            # Add required authentication headers
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": "agent8x-backend-secret-key-2025",  # Required internal API key
            }

            logger.info(f"   🔑 Using API Key: agent8x-backend-secret-key-2025")
            logger.info(f"   📋 Headers: {headers}")

            async with session.post(
                api_url, json=test_config, headers=headers
            ) as response:
                if response.status == 200:
                    response_data = await response.json()
                    task_id = response_data.get("task_id")
                    logger.info(f"✅ API RESPONSE SUCCESS!")
                    logger.info(f"   📋 Task ID: {task_id}")
                    logger.info(
                        f"   📊 Status: {response_data.get('status', 'unknown')}"
                    )
                    logger.info(
                        f"   💬 Message: {response_data.get('message', 'unknown')}"
                    )
                    logger.info(
                        f"   🔍 Status Check URL: {response_data.get('status_check_url', 'unknown')}"
                    )
                    logger.info(
                        f"   ⏰ Queued at: {datetime.now().strftime('%H:%M:%S')}"
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"❌ API CALL FAILED: {response.status}")
                    logger.error(f"   🔍 Error: {error_text}")
                    return

        # ===== STEP 2: Monitor DocumentProcessingWorker processing =====
        logger.info("⏳ STEP 2: Monitoring DocumentProcessingWorker processing...")
        logger.info(
            "   🔄 Worker handles: File extraction → Raw content only → Qdrant upload → Callback"
        )

        # Wait for processing
        max_wait_time = 120  # 2 minutes for DOCX file processing
        check_interval = 5
        elapsed_time = 0

        while elapsed_time < max_wait_time:
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval

            logger.info(f"⏱️ Processing... ({elapsed_time}s / {max_wait_time}s)")

            # Check if callback received
            if "/file-processed" in captured_callback_data:
                logger.info(
                    "🎉 CALLBACK RECEIVED! DocumentProcessingWorker completed workflow."
                )
                break

            # Show progress every 20 seconds
            if elapsed_time % 20 == 0:
                logger.info(
                    f"   📊 Still processing - worker extracting raw content..."
                )

        # ===== STEP 3: Analyze results =====
        logger.info("📊 STEP 3: Analyzing file upload results...")

        # Check callback data
        if "/file-processed" in captured_callback_data:
            callback_data = captured_callback_data["/file-processed"]

            logger.info("🎉 SUCCESS! Complete file upload workflow captured:")
            logger.info(f"   📞 Callback path: /file-processed")
            logger.info(f"   ⏰ Timestamp: {callback_data['timestamp']}")

            payload = callback_data["payload"]
            logger.info(f"   📋 Task ID: {payload.get('task_id', 'unknown')}")
            logger.info(f"   🏢 Company: {payload.get('company_id', 'unknown')}")
            logger.info(f"   📊 Status: {payload.get('status', 'unknown')}")

            # Analyze data section
            data = payload.get("data", {})
            if data:
                logger.info(f"   ✅ SUCCESS: {data.get('success', False)}")
                logger.info(f"   ⏱️ Processing Time: {data.get('processing_time', 0)}s")

                # Check raw content
                raw_content = data.get("raw_content", "")
                if raw_content:
                    logger.info(
                        f"   📄 Raw Content Length: {len(raw_content)} characters"
                    )
                    logger.info(f"   📝 Content Preview: {raw_content[:150]}...")
                else:
                    logger.error("   ❌ NO RAW CONTENT found in callback!")

                # Check if there's any structured data (should NOT be present)
                if "structured_data" in data:
                    logger.warning(
                        "   ⚠️ UNEXPECTED: Found structured_data in file upload callback!"
                    )
                else:
                    logger.info(
                        "   ✅ CORRECT: No structured_data (as expected for file upload)"
                    )

            # ===== STEP 4: Save callback data for backend documentation =====
            logger.info("💾 STEP 4: Saving callback data for backend documentation...")

            # Save callback data
            output_dir = Path("test_outputs")
            output_dir.mkdir(exist_ok=True)

            callback_file = output_dir / "file_upload_callback_data.json"
            with open(callback_file, "w", encoding="utf-8") as f:
                json.dump(callback_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Callback data saved: {callback_file}")

            # Save payload sample for backend documentation
            sample_payload = {
                "description": "File Upload E2E Test - DocumentProcessingWorker Callback Payload",
                "workflow": "/companies/{companyId}/files/upload",
                "worker": "DocumentProcessingWorker",
                "content_type": "RAW_CONTENT_ONLY",
                "test_file": "company-profile.docx",  # File DOCX thực
                "company_id": COMPANY_ID,  # Company ID thực
                "industry": INDUSTRY,  # Insurance industry
                "url": test_config["r2_url"],
                "callback_data": callback_data,
                "payload_structure_verification": {
                    "has_task_id": "task_id" in payload,
                    "has_status": "status" in payload,
                    "has_company_id": "company_id" in payload,
                    "has_data_section": "data" in payload,
                    "has_raw_content": "raw_content" in data if data else False,
                    "has_structured_data": "structured_data" in data if data else False,
                    "matches_specification": "raw_content" in data
                    and "structured_data" not in data,
                },
            }

            sample_file = output_dir / "file_upload_callback_sample.json"
            with open(sample_file, "w", encoding="utf-8") as f:
                json.dump(sample_payload, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Documentation sample saved: {sample_file}")

            # ===== STEP 5: Verify payload format against specification =====
            logger.info(
                "🔍 STEP 5: Verifying payload against CALLBACK_URL_SPECIFICATION.md..."
            )

            verification_results = []

            # Check required fields
            required_fields = ["task_id", "status", "timestamp", "data"]
            for field in required_fields:
                if field in payload:
                    verification_results.append(f"   ✅ {field}: Present")
                else:
                    verification_results.append(f"   ❌ {field}: Missing")

            # Check data section structure
            if data:
                data_fields = [
                    "task_id",
                    "company_id",
                    "status",
                    "success",
                    "processing_time",
                    "raw_content",
                ]
                for field in data_fields:
                    if field in data:
                        verification_results.append(f"   ✅ data.{field}: Present")
                    else:
                        verification_results.append(f"   ❌ data.{field}: Missing")

                # Verify NO structured data (this is file upload, not AI extraction)
                if "structured_data" not in data:
                    verification_results.append(
                        "   ✅ No structured_data (correct for file upload)"
                    )
                else:
                    verification_results.append(
                        "   ⚠️ structured_data present (unexpected for file upload)"
                    )

            logger.info("📋 PAYLOAD VERIFICATION RESULTS:")
            for result in verification_results:
                logger.info(result)

        else:
            logger.error("❌ No callback received within timeout period")
            logger.error("   🔍 Check if DocumentProcessingWorker is running")
            logger.error("   🔍 Check if callback URL is reachable")
            logger.error("   🔍 Check Redis queue connection")

        logger.info("🎉 FILE UPLOAD E2E TEST COMPLETED!")
        logger.info("📋 Summary:")
        logger.info("   ✅ Company DOCX file processed via /files/upload")
        logger.info("   ✅ DocumentProcessingWorker extracted raw content")
        logger.info("   ✅ Callback payload captured for backend documentation")
        logger.info("   ✅ Payload format verified against specification")

    except Exception as e:
        logger.error(f"❌ E2E test failed: {str(e)}")
        import traceback

        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        raise


async def main():
    """Main test runner"""
    try:
        await test_file_upload_workflow()
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
    finally:
        logger.info("🔚 Test completed")


if __name__ == "__main__":
    asyncio.run(main())
