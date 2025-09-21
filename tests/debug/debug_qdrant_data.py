#!/usr/bin/env python3
"""
Debug script to check Qdrant data for AIA company
"""

import asyncio
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue


async def debug_qdrant_data():
    """Debug Qdrant data for specific company"""

    # Initialize Qdrant client (Cloud)
    qdrant_url = os.getenv(
        "QDRANT_URL",
        "https://f9614d10-66f5-4669-9629-617c14876551.us-east4-0.gcp.cloud.qdrant.io",
    )
    qdrant_api_key = os.getenv(
        "QDRANT_API_KEY",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.gNFcCArqNFnAASKS1MHxTvsiVBmwvClDKE5o6mhX2eg",
    )

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    collection_name = "multi_company_data"
    company_id = "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f"

    print(f"🔍 Debugging Qdrant data for collection: {collection_name}")
    print(f"📊 Company ID: {company_id}")
    print("=" * 80)

    try:
        # Step 1: Check if collection exists
        collections = client.get_collections()
        collection_names = [col.name for col in collections.collections]
        print(f"📂 Available collections: {collection_names}")

        if collection_name not in collection_names:
            print(f"❌ Collection '{collection_name}' not found!")
            return

        # Step 2: Get collection info
        collection_info = client.get_collection(collection_name)
        print(f"📋 Collection info:")
        print(f"   Points count: {collection_info.points_count}")
        print(f"   Vector size: {collection_info.config.params.vectors.size}")
        print()

        # Step 3: Check for any data from this company
        company_filter = Filter(
            must=[FieldCondition(key="company_id", match=MatchValue(value=company_id))]
        )

        # Scroll through company data
        company_results = client.scroll(
            collection_name=collection_name,
            scroll_filter=company_filter,
            limit=10,
            with_payload=True,
            with_vectors=False,
        )

        company_points = company_results[0] if company_results else []
        print(f"🏢 Found {len(company_points)} points for company {company_id}")

        if company_points:
            print("📄 Sample company data:")
            for i, point in enumerate(company_points[:3], 1):
                payload = point.payload or {}
                print(f"   {i}. Point ID: {point.id}")
                print(f"      Content type: {payload.get('content_type', 'unknown')}")
                print(f"      Data type: {payload.get('data_type', 'unknown')}")
                print(f"      Industry: {payload.get('industry', 'unknown')}")
                print(f"      Language: {payload.get('language', 'unknown')}")
                print(f"      Content preview: {payload.get('content', '')[:100]}...")
                print()
        else:
            print("❌ No data found for this company!")

            # Check for any data at all
            all_results = client.scroll(
                collection_name=collection_name,
                limit=5,
                with_payload=True,
                with_vectors=False,
            )

            all_points = all_results[0] if all_results else []
            print(f"📊 Total points in collection: {len(all_points)}")

            if all_points:
                print("📋 Sample data from collection:")
                for i, point in enumerate(all_points[:2], 1):
                    payload = point.payload or {}
                    print(f"   {i}. Company ID: {payload.get('company_id', 'unknown')}")
                    print(
                        f"      Content type: {payload.get('content_type', 'unknown')}"
                    )
                    print(f"      Industry: {payload.get('industry', 'unknown')}")
                    print()

        # Step 4: Check for AIA-related data by content search
        print("🔍 Searching for AIA-related content...")
        aia_results = client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False,
        )

        aia_points = []
        all_points_to_check = aia_results[0] if aia_results else []

        for point in all_points_to_check:
            payload = point.payload or {}
            content = payload.get("content", "").lower()
            if "aia" in content:
                aia_points.append(point)

        print(f"🔍 Found {len(aia_points)} points containing 'AIA'")

        if aia_points:
            print("📋 AIA-related data:")
            for i, point in enumerate(aia_points[:3], 1):
                payload = point.payload or {}
                print(f"   {i}. Company ID: {payload.get('company_id', 'unknown')}")
                print(f"      Content preview: {payload.get('content', '')[:200]}...")
                print()

    except Exception as e:
        print(f"❌ Error checking Qdrant data: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_qdrant_data())
