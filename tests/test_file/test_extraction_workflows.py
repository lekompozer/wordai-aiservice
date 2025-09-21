#!/usr/bin/env python3
"""
Test script for both extraction workflows:
1. Sync extraction (immediate response) - /api/extract/process
2. Async extraction (queue-based) - /api/extract/process-async

Tests backend data_type tracking and optimized chunking strategy
"""

import asyncio
import json
import os
import requests
import sys
import time
from typing import Dict, Any

# Test configuration
TEST_API_BASE = "http://localhost:8000"
TEST_FILE_URL = "https://static.agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/SanPham-AIA.txt"
COMPANY_ID = "5a44b799-4783-448f-b6a8-b9a51ed7ab76"
INDUSTRY = "insurance"

# Results storage
RESULTS_DIR = "test_results"
os.makedirs(RESULTS_DIR, exist_ok=True)


def log_step(step: str, status: str = "INFO"):
    """Log test steps with formatting"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {status}: {step}")


def save_response_to_file(response_data: dict, scenario_name: str, endpoint_type: str):
    """Save full response to file for comparison"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{RESULTS_DIR}/response_{endpoint_type}_{scenario_name.replace(' ', '_')}_{timestamp}.json"

    # Clean filename
    filename = filename.replace(":", "_").replace("/", "_").replace("\\", "_")

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)
        log_step(f"💾 Response saved to: {filename}")
        return filename
    except Exception as e:
        log_step(f"❌ Failed to save response: {str(e)}", "ERROR")
        return None


def test_sync_extraction():
    """Test the sync extraction endpoint /api/extract/process"""
    log_step("=" * 60)
    log_step("🔄 TESTING SYNC EXTRACTION ENDPOINT")
    log_step("=" * 60)

    # Test different data_type scenarios
    test_scenarios = [
        {
            "name": "Backend specifies 'products' only",
            "data_type": "products",
            "target_categories": ["products"],
        },
        {
            "name": "Backend specifies 'services' only",
            "data_type": "services",
            "target_categories": ["services"],
        },
        {
            "name": "Backend specifies 'auto' for both",
            "data_type": "auto",
            "target_categories": ["products", "services"],
        },
        {
            "name": "INCONSISTENCY: Backend says 'products' but includes services",
            "data_type": "products",
            "target_categories": ["products", "services"],
        },
    ]

    for scenario in test_scenarios:
        log_step(f"📋 Scenario: {scenario['name']}")

        payload = {
            "r2_url": TEST_FILE_URL,
            "company_id": COMPANY_ID,
            "industry": INDUSTRY,
            "data_type": scenario["data_type"],
            "target_categories": scenario["target_categories"],
            "file_metadata": {
                "original_name": "test_insurance_products.txt",
                "file_size": 50000,
                "file_type": "text/plain",
                "uploaded_at": "2025-07-25T15:30:00Z",
            },
            "language": "vi",
            "upload_to_qdrant": True,  # Enable Qdrant upload for full testing
        }

        try:
            log_step(f"🚀 Calling sync extraction endpoint...")
            response = requests.post(
                f"{TEST_API_BASE}/api/extract/process", json=payload, timeout=120
            )

            if response.status_code == 200:
                result = response.json()

                # Save full response to file for comparison
                save_response_to_file(result, scenario["name"], "sync")

                log_step("✅ Sync extraction successful!", "SUCCESS")

                # Check if extraction was successful
                if result.get("success"):
                    # Log key results
                    if "structured_data" in result and result["structured_data"]:
                        structured = result["structured_data"]
                        products_count = len(structured.get("products", []))
                        services_count = len(structured.get("services", []))
                        log_step(f"   📦 Products extracted: {products_count}")
                        log_step(f"   🔧 Services extracted: {services_count}")
                    else:
                        log_step("   ⚠️ No structured_data in response", "WARNING")

                    log_step(
                        f"   ⏱️ Processing time: {result.get('processing_time', 0):.2f}s"
                    )
                    log_step(f"   🤖 AI Provider: {result.get('ai_provider')}")
                    log_step(f"   📋 Template: {result.get('template_used')}")
                else:
                    log_step(
                        f"   ❌ Extraction failed: {result.get('message', 'Unknown error')}",
                        "ERROR",
                    )
                    if result.get("error"):
                        log_step(f"   ❌ Error details: {result.get('error')}", "ERROR")

            else:
                log_step(f"❌ Sync extraction failed: {response.status_code}", "ERROR")
                log_step(f"Response: {response.text}", "ERROR")

        except Exception as e:
            log_step(f"❌ Error: {str(e)}", "ERROR")

        log_step("-" * 40)


def test_async_extraction():
    """Test the async extraction endpoint /api/extract/process-async"""
    log_step("=" * 60)
    log_step("🔄 TESTING ASYNC EXTRACTION ENDPOINT (QUEUE-BASED)")
    log_step("=" * 60)

    # Test queue-based workflow
    payload = {
        "r2_url": TEST_FILE_URL,
        "company_id": COMPANY_ID,
        "industry": INDUSTRY,
        "file_name": "test_insurance_products.txt",
        "file_size": 50000,
        "file_type": "text/plain",
        "data_type": "products",
        "target_categories": ["products"],
        "language": "vi",
        "callback_url": "https://webhook.site/test-callback",  # Test callback
    }

    try:
        log_step("🚀 Calling async extraction endpoint...")
        response = requests.post(
            f"{TEST_API_BASE}/api/extract/process-async",
            json=payload,
            timeout=30,  # Should return quickly with task_id
        )

        if response.status_code == 200:
            result = response.json()

            # Save full response to file for comparison
            save_response_to_file(result, "async_queue", "async")

            if result.get("success"):
                log_step("✅ Async extraction queued successfully!", "SUCCESS")
                log_step(f"   🆔 Task ID: {result.get('task_id')}")
                log_step(f"   📊 Status: {result.get('status')}")
                log_step(f"   ⏱️ Estimated time: {result.get('estimated_time')}s")
                log_step(f"   📞 Callback URL: {payload['callback_url']}")

                # Instructions for monitoring
                log_step("📝 MONITORING INSTRUCTIONS:")
                log_step("   1. Check worker logs for processing status")
                log_step("   2. Monitor callback URL for completion notification")
                log_step("   3. Check Qdrant for uploaded chunks")

                return result.get("task_id")
            else:
                log_step(f"❌ Queue failed: {result.get('error')}", "ERROR")
        else:
            log_step(f"❌ Async extraction failed: {response.status_code}", "ERROR")
            log_step(f"Response: {response.text}", "ERROR")

    except Exception as e:
        log_step(f"❌ Error: {str(e)}", "ERROR")

    return None


def test_health_endpoints():
    """Test health and info endpoints"""
    log_step("=" * 60)
    log_step("🏥 TESTING HEALTH ENDPOINTS")
    log_step("=" * 60)

    # Test health endpoint
    try:
        response = requests.get(f"{TEST_API_BASE}/api/extract/health")
        if response.status_code == 200:
            health = response.json()
            log_step("✅ Health check successful!", "SUCCESS")
            log_step(f"   📊 Status: {health.get('status')}")
            log_step(f"   🤖 AI Providers: {health.get('ai_providers', {})}")
            log_step(
                f"   📋 Templates: {health.get('template_system', {}).get('available_templates', 0)}"
            )
        else:
            log_step(f"❌ Health check failed: {response.status_code}", "ERROR")
    except Exception as e:
        log_step(f"❌ Health check error: {str(e)}", "ERROR")

    # Test info endpoint
    try:
        response = requests.get(f"{TEST_API_BASE}/api/extract/info")
        if response.status_code == 200:
            info = response.json()
            log_step("✅ Service info successful!", "SUCCESS")
            log_step(f"   📋 Version: {info.get('version')}")
            log_step(f"   🏭 Industries: {len(info.get('supported_industries', []))}")
            log_step(f"   📄 File types: {len(info.get('supported_file_types', []))}")
        else:
            log_step(f"❌ Service info failed: {response.status_code}", "ERROR")
    except Exception as e:
        log_step(f"❌ Service info error: {str(e)}", "ERROR")


def check_qdrant_data(company_id: str):
    """Check what data was saved to Qdrant for the company"""
    log_step("=" * 60)
    log_step("🔍 CHECKING QDRANT DATA")
    log_step("=" * 60)

    try:
        # Check if we can query Qdrant for company data
        import sys

        sys.path.append(".")
        from src.vector_store.qdrant_client import QdrantClient

        qdrant = QdrantClient()

        # Search for documents with this company_id
        results = qdrant.search_documents(
            query="AIA insurance products services",
            filters={"company_id": company_id},
            limit=20,
        )

        log_step(f"📊 Found {len(results)} chunks in Qdrant for company {company_id}")

        for i, result in enumerate(results[:5]):  # Show first 5 results
            log_step(f"   📄 Chunk {i+1}:")
            log_step(f"      📋 Data Type: {result.get('data_type', 'N/A')}")
            log_step(f"      📊 Category: {result.get('category', 'N/A')}")
            log_step(
                f"      📝 Content Preview: {str(result.get('content', ''))[:100]}..."
            )
            log_step(f"      🎯 Score: {result.get('score', 0):.3f}")

        return len(results)

    except Exception as e:
        log_step(f"❌ Error checking Qdrant: {str(e)}", "ERROR")
        return 0


def test_full_workflow():
    """Test complete workflow including Qdrant verification"""
    log_step("=" * 60)
    log_step("🔄 TESTING FULL WORKFLOW WITH QDRANT")
    log_step("=" * 60)

    # Test with products extraction and Qdrant upload
    payload = {
        "r2_url": TEST_FILE_URL,
        "company_id": COMPANY_ID,
        "industry": INDUSTRY,
        "data_type": "auto",  # Auto-detect both products and services
        "target_categories": ["products", "services"],
        "file_metadata": {
            "original_name": "SanPham-AIA.txt",
            "file_size": 50000,
            "file_type": "text/plain",
            "uploaded_at": "2025-07-26T12:00:00Z",
        },
        "language": "vi",
        "upload_to_qdrant": True,  # Full workflow with Qdrant
    }

    try:
        log_step("🚀 Calling extraction endpoint with Qdrant upload...")
        response = requests.post(
            f"{TEST_API_BASE}/api/extract/process", json=payload, timeout=180
        )

        if response.status_code == 200:
            result = response.json()

            # Save FULL response to file for comparison
            save_response_to_file(result, "FULL_WORKFLOW_AIA", "complete")

            log_step("✅ Full workflow extraction successful!", "SUCCESS")

            # Detailed analysis of response
            if result.get("success"):
                log_step("📊 EXTRACTION RESULTS:")

                # Check structured data
                if "structured_data" in result and result["structured_data"]:
                    structured = result["structured_data"]
                    products = structured.get("products", [])
                    services = structured.get("services", [])

                    log_step(f"   📦 Products extracted: {len(products)}")
                    log_step(f"   🔧 Services extracted: {len(services)}")

                    # Show sample products
                    if products:
                        log_step("   📦 Sample Products:")
                        for i, product in enumerate(products[:3]):
                            log_step(f"      {i+1}. {product.get('name', 'N/A')}")
                            log_step(
                                f"         💰 Price: {product.get('price', 'N/A')}"
                            )
                    else:
                        log_step(
                            "   📦 No products found in structured data", "WARNING"
                        )

                    # Show sample services
                    if services:
                        log_step("   🔧 Sample Services:")
                        for i, service in enumerate(services[:3]):
                            log_step(f"      {i+1}. {service.get('name', 'N/A')}")
                            log_step(
                                f"         💰 Price: {service.get('price', 'N/A')}"
                            )
                    else:
                        log_step(
                            "   🔧 No services found in structured data", "WARNING"
                        )

                # Check Qdrant upload results
                if "qdrant_results" in result:
                    qdrant_info = result["qdrant_results"]
                    log_step(
                        f"   🔗 Qdrant Upload: {qdrant_info.get('success', False)}"
                    )
                    log_step(
                        f"   📊 Chunks uploaded: {qdrant_info.get('chunks_count', 0)}"
                    )

                log_step(
                    f"   ⏱️ Processing time: {result.get('processing_time', 0):.2f}s"
                )
                log_step(f"   🤖 AI Provider: {result.get('ai_provider')}")
                log_step(f"   📋 Template: {result.get('template_used')}")

                # Wait a moment then check Qdrant
                log_step("⏳ Waiting 3 seconds then checking Qdrant...")
                time.sleep(3)
                chunks_count = check_qdrant_data(COMPANY_ID)

                return result
            else:
                log_step(
                    f"❌ Extraction failed: {result.get('message', 'Unknown error')}",
                    "ERROR",
                )
                if result.get("error"):
                    log_step(f"❌ Error details: {result.get('error')}", "ERROR")

        else:
            log_step(f"❌ Full workflow failed: {response.status_code}", "ERROR")
            log_step(f"Response: {response.text}", "ERROR")

    except Exception as e:
        log_step(f"❌ Error: {str(e)}", "ERROR")

    return None


def main():
    """Main test function"""
    print("🧪" * 30)
    print("🧪 EXTRACTION WORKFLOWS COMPREHENSIVE TEST")
    print("🧪" * 30)
    print(f"🎯 Testing against: {TEST_API_BASE}")
    print(f"📄 Test file: {TEST_FILE_URL}")
    print(f"🏢 Company: {COMPANY_ID}")
    print(f"🏭 Industry: {INDUSTRY}")
    print("🧪" * 30)

    # Test 1: Health endpoints
    test_health_endpoints()

    # Test 2: Sync extraction with data_type tracking
    test_sync_extraction()

    # Test 3: Async extraction (queue-based)
    task_id = test_async_extraction()

    # Test 4: Full workflow with Qdrant verification
    full_workflow_result = test_full_workflow()

    print("🧪" * 30)
    log_step("✅ All tests completed!", "SUCCESS")

    if task_id:
        log_step("📝 NEXT STEPS:")
        log_step("   1. Monitor worker logs for task processing")
        log_step("   2. Check callback URL for completion notification")
        log_step(f"   3. Verify task {task_id} results in Qdrant")

    if full_workflow_result and full_workflow_result.get("success"):
        log_step("✅ Full workflow completed successfully!", "SUCCESS")
    else:
        log_step("❌ Full workflow encountered issues", "ERROR")

    print("🧪" * 30)


if __name__ == "__main__":
    main()
