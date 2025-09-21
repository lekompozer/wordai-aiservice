#!/usr/bin/env python3
"""
Test script to verify Qdrant upload and search functionality
Script test để kiểm tra chức năng upload và tìm kiếm Qdrant
"""

import asyncio
import json
import aiohttp
from datetime import datetime
import sys
from pathlib import Path
from qdrant_client import QdrantClient

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.services.qdrant_company_service import QdrantCompanyDataService

# Direct Qdrant credentials
QDRANT_URL = (
    "https://f9614d10-66f5-4669-9629-617c14876551.us-east4-0.gcp.cloud.qdrant.io"
)
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.gNFcCArqNFnAASKS1MHxTvsiVBmwvClDKE5o6mhX2eg"

# Test company data
COMPANY_ID = "ivy-fashion-store"
COMPANY_INFO = {
    "id": "ivy-fashion-store",
    "name": "Ivy Fashion Store",
    "industry": "fashion",
    "description": "Modern fashion retailer specializing in trendy clothing",
}

# Admin API authentication
ADMIN_API_KEY = "agent8x-backend-secret-key-2025"


async def test_qdrant_upload_status():
    """Check if data was uploaded to Qdrant successfully"""
    print("🔍 CHECKING QDRANT UPLOAD STATUS")
    print("=" * 60)

    # First, trigger an extraction with Qdrant upload
    extraction_payload = {
        "r2_url": "https://agent8x.io.vn/companies/ivy-fashion-store/ivy-fashion-products-clean.csv",
        "company_id": COMPANY_ID,
        "industry": "fashion",
        "target_categories": ["products"],
        "file_metadata": {
            "original_name": "ivy-fashion-products-clean.csv",
            "file_size": 245760,
            "file_type": "text/csv",
            "uploaded_at": datetime.now().isoformat(),
        },
        "company_info": COMPANY_INFO,
        "language": "vi",
        "upload_to_qdrant": True,
    }

    print(f"📤 Triggering extraction with Qdrant upload...")
    print(f"🏢 Company: {COMPANY_ID}")
    print(f"📄 File: ivy-fashion-products-clean.csv")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8000/api/extract/process",
                json=extraction_payload,
                headers={"Content-Type": "application/json"},
            ) as response:

                if response.status == 200:
                    result = await response.json()
                    print("✅ EXTRACTION COMPLETED")
                    print(f"   🤖 AI Provider: {result.get('ai_provider')}")
                    print(
                        f"   📊 Total items: {result.get('total_items_extracted', 0)}"
                    )
                    print(
                        f"   📦 Products: {len(result.get('structured_data', {}).get('products', []))}"
                    )
                    print(
                        f"   💾 Qdrant upload: {'✅ Scheduled' if extraction_payload['upload_to_qdrant'] else '❌ Skipped'}"
                    )

                    # Wait a moment for background processing
                    print("\n⏳ Waiting 5 seconds for background Qdrant upload...")
                    await asyncio.sleep(5)

                    return True

                else:
                    print(f"❌ EXTRACTION FAILED: {response.status}")
                    error_text = await response.text()
                    print(f"Error: {error_text}")
                    return False

    except Exception as e:
        print(f"❌ EXTRACTION ERROR: {str(e)}")
        return False


async def test_company_data_search():
    """Test searching company data using search_company_data endpoint"""
    print("\n🔍 TESTING COMPANY DATA SEARCH")
    print("=" * 60)

    # Test various search queries
    search_queries = [
        {"query": "áo blazer", "description": "Search for blazer products"},
        {"query": "đầm shirt dress", "description": "Search for shirt dress"},
        {"query": "chân váy tulle", "description": "Search for tulle skirt"},
        {"query": "cotton", "description": "Search by material"},
        {"query": "1380000", "description": "Search by price"},
        {"query": "IVY Fashion", "description": "Search by brand"},
    ]

    results_found = 0

    for i, search_test in enumerate(search_queries, 1):
        query = search_test["query"]
        description = search_test["description"]

        print(f"\n🔎 Test {i}: {description}")
        print(f"   Query: '{query}'")

        # Prepare search payload
        search_payload = {
            "company_id": COMPANY_ID,
            "query": query,
            "content_types": ["products"],  # Search for products only
            "language": "vi",
            "limit": 5,
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Create URL with query parameters for GET request
                url = f"http://localhost:8000/api/admin/companies/{COMPANY_ID}/search"

                async with session.post(
                    url,
                    json=search_payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": ADMIN_API_KEY,
                    },
                ) as response:

                    if response.status == 200:
                        search_results = await response.json()

                        if search_results and len(search_results) > 0:
                            results_found += 1
                            print(f"   ✅ Found {len(search_results)} results")

                            # Show top result details
                            top_result = search_results[0]
                            print(
                                f"   📦 Top result: {top_result.get('content', 'N/A')[:100]}..."
                            )
                            print(f"   🎯 Score: {top_result.get('score', 0):.3f}")
                            print(
                                f"   📊 Content type: {top_result.get('content_type', 'N/A')}"
                            )

                            # Show structured data if available
                            structured_data = top_result.get("structured_data", {})
                            if structured_data and structured_data.get("product_data"):
                                product = structured_data["product_data"]
                                print(
                                    f"   📝 Product: {product.get('name', 'N/A')} - {product.get('price', 'N/A')}"
                                )
                        else:
                            print(f"   ❌ No results found")

                    else:
                        print(f"   ❌ Search failed: {response.status}")
                        error_text = await response.text()
                        print(f"   Error: {error_text}")

        except Exception as e:
            print(f"   ❌ Search error: {str(e)}")

    print(f"\n📊 SEARCH SUMMARY:")
    print(f"   Total tests: {len(search_queries)}")
    print(f"   Successful searches: {results_found}")
    print(f"   Success rate: {(results_found/len(search_queries)*100):.1f}%")

    return results_found > 0


async def test_qdrant_collection_info():
    """Check Qdrant collection information and data"""
    print("\n🗄️ CHECKING QDRANT COLLECTION INFO")
    print("=" * 60)

    try:
        # Try to get company statistics which should show Qdrant data
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://localhost:8000/api/admin/companies/{COMPANY_ID}/stats",
                headers={"X-API-Key": ADMIN_API_KEY},
            ) as response:

                if response.status == 200:
                    stats = await response.json()
                    print("✅ COMPANY STATS RETRIEVED")
                    print(f"   🏢 Company ID: {stats.get('company_id', 'N/A')}")
                    print(f"   🏭 Industry: {stats.get('industry', 'N/A')}")
                    print(
                        f"   📊 Total files: {stats.get('file_stats', {}).get('total_files', 0)}"
                    )
                    print(
                        f"   📈 Processed files: {stats.get('file_stats', {}).get('processed_files', 0)}"
                    )

                    # Check Qdrant specific stats
                    qdrant_stats = stats.get("qdrant_stats", {})
                    if qdrant_stats:
                        print(
                            f"   🗄️ Qdrant collection size: {qdrant_stats.get('qdrant_collection_size', 0)}"
                        )
                        print(
                            f"   📦 Total chunks: {qdrant_stats.get('total_chunks', 0)}"
                        )

                        # Show data type distribution
                        data_type_counts = qdrant_stats.get("data_type_counts", {})
                        if data_type_counts:
                            print(f"   📋 Data type distribution:")
                            for data_type, count in data_type_counts.items():
                                print(f"      {data_type}: {count} chunks")
                    else:
                        print(f"   ⚠️ No Qdrant stats available")

                    return qdrant_stats.get("total_chunks", 0) > 0
                else:
                    print(f"❌ STATS RETRIEVAL FAILED: {response.status}")
                    return False

    except Exception as e:
        print(f"❌ STATS ERROR: {str(e)}")
        return False


async def test_chat_with_ivy_fashion():
    """Test chat functionality with Ivy Fashion Store data"""
    print("\n💬 TESTING CHAT WITH IVY FASHION STORE")
    print("=" * 60)

    # Test chat queries about the uploaded products
    chat_queries = [
        "Có áo blazer nào không?",
        "Tôi muốn tìm đầm shirt dress",
        "Chân váy tulle giá bao nhiêu?",
        "Sản phẩm nào làm từ cotton?",
        "Áo blazer kẻ có những màu gì?",
        "Các sản phẩm của thương hiệu IVY Fashion",
    ]

    successful_chats = 0

    for i, query in enumerate(chat_queries, 1):
        print(f"\n💬 Chat Test {i}: '{query}'")

        # Prepare chat payload
        chat_payload = {
            "message": query,
            "company_id": COMPANY_ID,
            "industry": "fashion",
            "language": "vi",
            "session_id": f"test_session_{datetime.now().timestamp()}",
            "context": {"company_info": COMPANY_INFO, "search_context": "products"},
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:8000/api/unified/chat",
                    json=chat_payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Company-Id": COMPANY_ID,
                    },
                ) as response:

                    if response.status == 200:
                        chat_result = await response.json()

                        message = chat_result.get("message", "")
                        intent = chat_result.get("intent", "unknown")
                        confidence = chat_result.get("confidence", 0)

                        if message and len(message) > 10:  # Valid response
                            successful_chats += 1
                            print(f"   ✅ Response received")
                            print(
                                f"   🎯 Intent: {intent} (confidence: {confidence:.2f})"
                            )
                            print(f"   📝 Response: {message[:150]}...")

                            # Check if response contains relevant product info
                            relevant_keywords = [
                                "blazer",
                                "đầm",
                                "váy",
                                "cotton",
                                "IVY",
                                "giá",
                                "màu",
                            ]
                            if any(
                                keyword.lower() in message.lower()
                                for keyword in relevant_keywords
                            ):
                                print(
                                    f"   🎉 Response contains relevant product information!"
                                )
                        else:
                            print(f"   ⚠️ Empty or short response")

                    else:
                        print(f"   ❌ Chat failed: {response.status}")
                        error_text = await response.text()
                        print(f"   Error: {error_text}")

        except Exception as e:
            print(f"   ❌ Chat error: {str(e)}")

    print(f"\n📊 CHAT TEST SUMMARY:")
    print(f"   Total queries: {len(chat_queries)}")
    print(f"   Successful responses: {successful_chats}")
    print(f"   Success rate: {(successful_chats/len(chat_queries)*100):.1f}%")

    return successful_chats > 0


async def main():
    """Main test function"""
    print("🧪 COMPREHENSIVE IVY FASHION STORE QDRANT TEST")
    print("=" * 60)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Step 1: Upload data to Qdrant
    upload_success = await test_qdrant_upload_status()

    # Step 2: Check collection info
    collection_has_data = await test_qdrant_collection_info()

    # Step 3: Test data search
    search_success = await test_company_data_search()

    # Step 4: Test chat functionality
    chat_success = await test_chat_with_ivy_fashion()

    # Final summary
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)

    print(f"✅ Data Upload: {'PASSED' if upload_success else 'FAILED'}")
    print(
        f"✅ Qdrant Collection: {'HAS DATA' if collection_has_data else 'EMPTY/MISSING'}"
    )
    print(f"✅ Data Search: {'WORKING' if search_success else 'NOT WORKING'}")
    print(f"✅ Chat Integration: {'WORKING' if chat_success else 'NOT WORKING'}")

    overall_success = (
        upload_success and collection_has_data and search_success and chat_success
    )

    print(
        f"\n🎯 OVERALL STATUS: {'🎉 ALL SYSTEMS WORKING' if overall_success else '⚠️ SOME ISSUES DETECTED'}"
    )

    if overall_success:
        print("\n✨ Ivy Fashion Store data is successfully integrated!")
        print("   📊 Products are searchable in Qdrant")
        print("   💬 Chat system can access and respond with product data")
        print("   🔍 Search functionality is working correctly")
    else:
        print("\n🔧 Issues to investigate:")
        if not upload_success:
            print("   ❌ Data upload failed - check extraction API")
        if not collection_has_data:
            print("   ❌ Qdrant collection empty - check background upload process")
        if not search_success:
            print("   ❌ Search not working - check search API and indexing")
        if not chat_success:
            print("   ❌ Chat not working - check unified chat API and RAG integration")

    print(f"\n🕐 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
