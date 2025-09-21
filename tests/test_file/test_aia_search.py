#!/usr/bin/env python3
"""
Test AIA company search in Qdrant Cloud
"""

import os
import sys
import asyncio
import numpy as np
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_aia_search():
    """Test searching for AIA company data"""
    print("🔍 TESTING AIA SEARCH IN QDRANT")
    print("=" * 40)

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # Load environment
        load_dotenv()

        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        collection_name = "multi_company_data"
        company_id = "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f"

        print(f"🌐 Connecting to: {qdrant_url}")
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

        # Check collection info
        collection_info = client.get_collection(collection_name)
        print(f"📦 Collection: {collection_name}")
        print(f"   📊 Points count: {collection_info.points_count}")
        print(f"   🧮 Vectors count: {collection_info.vectors_count}")

        # Search for AIA company specifically
        aia_filter = Filter(
            must=[FieldCondition(key="company_id", match=MatchValue(value=company_id))]
        )

        # Get all AIA points
        print(f"\n🔍 Searching for AIA company data...")

        # Use scroll to get all points for AIA
        points, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=aia_filter,
            limit=10,
            with_payload=True,
            with_vectors=False,
        )

        if points:
            print(f"   🎯 Found {len(points)} AIA documents:")
            for i, point in enumerate(points, 1):
                title = point.payload.get("title", "No title")
                content_type = point.payload.get("content_type", "unknown")
                data_type = point.payload.get("data_type", "unknown")
                content_preview = point.payload.get("content", "")[:100] + "..."

                print(f"   {i}. {title}")
                print(f"      Type: {content_type} | Category: {data_type}")
                print(f"      Content: {content_preview}")
                print()
        else:
            print(f"   ❌ No AIA documents found!")

        # Test search by content
        print(f"🔍 Testing content search...")
        search_queries = [
            "bảo hiểm sức khỏe",
            "AIA Việt Nam",
            "dịch vụ khách hàng",
            "sản phẩm bảo hiểm",
        ]

        for query in search_queries:
            print(f"\n   🔎 Query: '{query}'")

            # Create dummy query vector (in real app, use embedding service)
            query_vector = np.random.uniform(-1, 1, 768).tolist()

            # Search with company filter
            try:
                results = client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    query_filter=aia_filter,
                    limit=3,
                    with_payload=True,
                ).points

                if results:
                    print(f"      ✅ Found {len(results)} results:")
                    for result in results:
                        title = result.payload.get("title", "No title")
                        score = result.score if hasattr(result, "score") else "N/A"
                        print(f"         - {title} (Score: {score})")
                else:
                    print(f"      ❌ No results")

            except Exception as e:
                print(f"      ❌ Search error: {e}")

        # Summary
        print(f"\n📊 SUMMARY:")
        print(f"   🏢 Company: AIA")
        print(f"   🆔 ID: {company_id}")
        print(f"   📄 Documents: {len(points) if points else 0}")
        print(f"   📦 Collection: {collection_name}")
        print(f"   🌐 Status: Connected to Qdrant Cloud")

        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_aia_search())
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    sys.exit(0 if success else 1)
