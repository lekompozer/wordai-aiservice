#!/usr/bin/env python3
"""
Debug Content For Embedding Field Generation
Test AI extraction to ensure content_for_embedding field is generated correctly
"""

import asyncio
import json
import requests
from datetime import datetime
import sys
import os

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_FILE_URL = "https://static.agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/SanPham-AIA.txt"
COMPANY_ID = 1


def save_debug_response(response_data, test_type):
    """Save response to file for debugging"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"debug_content_embedding_{test_type}_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(response_data, f, indent=2, ensure_ascii=False)

    print(f"📁 Saved debug response to: {filename}")
    return filename


def analyze_content_embedding_fields(data, data_type):
    """Analyze if content_for_embedding fields are present"""
    results = {
        "data_type": data_type,
        "total_items": 0,
        "items_with_content_embedding": 0,
        "items_missing_content_embedding": 0,
        "missing_items": [],
        "analysis": {},
    }

    if (
        "structured_data" in data
        and data_type in data["structured_data"]
        and isinstance(data["structured_data"][data_type], list)
    ):
        items = data["structured_data"][data_type]
        results["total_items"] = len(items)

        for i, item in enumerate(items):
            if "content_for_embedding" in item and item["content_for_embedding"]:
                results["items_with_content_embedding"] += 1
            else:
                results["items_missing_content_embedding"] += 1
                results["missing_items"].append(
                    {
                        "index": i,
                        "name": item.get("name", f"Item {i+1}"),
                        "id": item.get("id", "No ID"),
                        "available_fields": list(item.keys()),
                    }
                )

    # Analysis
    results["analysis"] = {
        "completion_rate": f"{(results['items_with_content_embedding'] / max(results['total_items'], 1)) * 100:.1f}%",
        "has_missing_fields": results["items_missing_content_embedding"] > 0,
        "is_template_compliant": results["items_missing_content_embedding"] == 0,
    }

    return results


def test_sync_extraction():
    """Test synchronous extraction endpoint"""
    print("🧪 Testing Sync Extraction for content_for_embedding...")

    payload = {
        "r2_url": TEST_FILE_URL,
        "company_id": str(COMPANY_ID),
        "industry": "insurance",
        "data_type": "products",
        "file_metadata": {
            "original_name": "SanPham-AIA.txt",
            "file_size": 1024000,
            "file_type": "text/plain",
            "uploaded_at": "2025-07-26T10:00:00Z",
        },
    }

    try:
        print(f"📤 Sending request to: {BASE_URL}/api/extract/process")
        response = requests.post(
            f"{BASE_URL}/api/extract/process", json=payload, timeout=300
        )

        print(f"📨 Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Save full response
            filename = save_debug_response(data, "sync_products")

            # Analyze content_for_embedding fields
            analysis = analyze_content_embedding_fields(data, "products")

            print("\n🔍 CONTENT_FOR_EMBEDDING ANALYSIS:")
            print("=" * 50)
            print(f"Data Type: {analysis['data_type']}")
            print(f"Total Items: {analysis['total_items']}")
            print(
                f"Items WITH content_for_embedding: {analysis['items_with_content_embedding']}"
            )
            print(
                f"Items MISSING content_for_embedding: {analysis['items_missing_content_embedding']}"
            )
            print(f"Completion Rate: {analysis['analysis']['completion_rate']}")
            print(
                f"Template Compliant: {analysis['analysis']['is_template_compliant']}"
            )

            if analysis["missing_items"]:
                print("\n❌ MISSING CONTENT_FOR_EMBEDDING ITEMS:")
                for item in analysis["missing_items"]:
                    print(f"  - Item {item['index']+1}: {item['name']}")
                    print(f"    ID: {item['id']}")
                    print(
                        f"    Available fields: {', '.join(item['available_fields'])}"
                    )
                    print()

            # Show sample content_for_embedding if any exist
            if analysis["items_with_content_embedding"] > 0:
                print("\n✅ SAMPLE CONTENT_FOR_EMBEDDING:")
                products = data.get("structured_data", {}).get("products", [])
                for product in products:
                    if (
                        "content_for_embedding" in product
                        and product["content_for_embedding"]
                    ):
                        print(f"Product: {product.get('name', 'Unknown')}")
                        print(f"Content: {product['content_for_embedding'][:200]}...")
                        break

            return analysis

        else:
            error_msg = response.text
            print(f"❌ Request failed: {error_msg}")
            return None

    except requests.exceptions.Timeout:
        print("⏰ Request timed out (300s)")
        return None
    except Exception as e:
        print(f"💥 Error: {str(e)}")
        return None


def test_services_extraction():
    """Test services extraction for content_for_embedding"""
    print("\n🧪 Testing Services Extraction for content_for_embedding...")

    payload = {
        "r2_url": TEST_FILE_URL,
        "company_id": str(COMPANY_ID),
        "industry": "insurance",
        "data_type": "services",
        "file_metadata": {
            "original_name": "SanPham-AIA.txt",
            "file_size": 1024000,
            "file_type": "text/plain",
            "uploaded_at": "2025-07-26T10:00:00Z",
        },
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/extract/process", json=payload, timeout=300
        )

        print(f"📨 Services Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Save full response
            filename = save_debug_response(data, "sync_services")

            # Analyze content_for_embedding fields
            analysis = analyze_content_embedding_fields(data, "services")

            print("\n🔍 SERVICES CONTENT_FOR_EMBEDDING ANALYSIS:")
            print("=" * 50)
            print(f"Total Services: {analysis['total_items']}")
            print(
                f"Services WITH content_for_embedding: {analysis['items_with_content_embedding']}"
            )
            print(
                f"Services MISSING content_for_embedding: {analysis['items_missing_content_embedding']}"
            )
            print(f"Completion Rate: {analysis['analysis']['completion_rate']}")

            return analysis

        else:
            print(f"❌ Services request failed: {response.text}")
            return None

    except Exception as e:
        print(f"💥 Services error: {str(e)}")
        return None


def test_async_extraction():
    """Test asynchronous extraction endpoint"""
    print("\n🧪 Testing ASYNC Extraction endpoint...")

    payload = {
        "r2_url": TEST_FILE_URL,
        "company_id": str(COMPANY_ID),
        "industry": "insurance",
        "data_type": "products",
        "file_name": "SanPham-AIA.txt",
        "file_size": 1024000,
        "file_type": "text/plain",
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/extract/process-async", json=payload, timeout=60
        )

        print(f"📨 Async Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Save async response
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"debug_async_response_{timestamp}.json"

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"📁 Saved async response to: {filename}")

            print("\n🔍 ASYNC ENDPOINT ANALYSIS:")
            print("=" * 50)
            print(f"Success: {data.get('success')}")
            print(f"Task ID: {data.get('task_id')}")
            print(f"Status: {data.get('status')}")
            print(f"Message: {data.get('message')}")
            print(f"Estimated Time: {data.get('estimated_time')}s")

            if data.get("success"):
                return "✅ Successfully queued"
            else:
                return f"❌ Failed: {data.get('error', 'Unknown error')}"

        else:
            print(f"❌ Async request failed: {response.text}")
            return f"❌ HTTP {response.status_code}"

    except Exception as e:
        print(f"💥 Async error: {str(e)}")
        return f"💥 Exception: {str(e)}"


def main():
    """Main test function"""
    print("🚀 Starting Content For Embedding Debug Test")
    print("=" * 60)

    # Test products extraction (SYNC)
    products_analysis = test_sync_extraction()

    # Test services extraction (SYNC)
    services_analysis = test_services_extraction()

    # Test ASYNC endpoint
    async_analysis = test_async_extraction()

    # Summary
    print("\n📊 FINAL SUMMARY:")
    print("=" * 60)

    if products_analysis:
        print(
            f"Products (SYNC): {products_analysis['analysis']['completion_rate']} complete"
        )
        if not products_analysis["analysis"]["is_template_compliant"]:
            print(
                "⚠️  Products are NOT template compliant - missing content_for_embedding fields"
            )

    if services_analysis:
        print(
            f"Services (SYNC): {services_analysis['analysis']['completion_rate']} complete"
        )
        if not services_analysis["analysis"]["is_template_compliant"]:
            print(
                "⚠️  Services are NOT template compliant - missing content_for_embedding fields"
            )

    if async_analysis:
        print(f"Async Endpoint: {async_analysis}")

    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    if products_analysis and not products_analysis["analysis"]["is_template_compliant"]:
        print("1. Enhance AI prompt to emphasize content_for_embedding field")
        print("2. Add field validation in response processing")
        print("3. Consider post-processing to generate missing content_for_embedding")

    if services_analysis and not services_analysis["analysis"]["is_template_compliant"]:
        print("4. Apply same fixes to services extraction")


if __name__ == "__main__":
    main()
