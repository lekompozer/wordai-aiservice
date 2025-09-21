#!/usr/bin/env python3
"""
Script to delete all Qdrant points for a specific company_id
Script để xóa tất cả các point trong Qdrant cho một company_id cụ thể
"""

import os
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Qdrant configuration from .env
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "multi_company_data")

# Company to delete
TARGET_COMPANY_ID = "1e789800-b402-41b0-99d6-2e8d494a3beb"


async def delete_company_data():
    """Delete all points for the target company"""

    print("🗑️ QDRANT COMPANY DATA DELETION")
    print("=" * 50)
    print(f"🎯 Target Company: {TARGET_COMPANY_ID}")
    print(f"🏭 Collection: {COLLECTION_NAME}")
    print(f"🌐 Qdrant URL: {QDRANT_URL}")
    print("=" * 50)

    try:
        # Initialize Qdrant client
        print("🔌 Connecting to Qdrant...")
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )

        # Test connection
        collections = client.get_collections()
        print(
            f"✅ Connected to Qdrant! Found {len(collections.collections)} collections"
        )

        # Check if collection exists
        collection_exists = False
        for collection in collections.collections:
            if collection.name == COLLECTION_NAME:
                collection_exists = True
                break

        if not collection_exists:
            print(f"❌ Collection '{COLLECTION_NAME}' not found!")
            return

        # Get collection info
        collection_info = client.get_collection(COLLECTION_NAME)
        total_points = collection_info.points_count
        print(f"📊 Collection '{COLLECTION_NAME}' has {total_points:,} total points")

        # Step 1: Count points for this company
        print(f"\n🔍 Counting points for company {TARGET_COMPANY_ID}...")

        # Create filter for the target company
        company_filter = Filter(
            must=[
                FieldCondition(
                    key="company_id", match=MatchValue(value=TARGET_COMPANY_ID)
                )
            ]
        )

        # Count points using scroll (since count API might not be available)
        print("📊 Scrolling to count company points...")
        scroll_result = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=company_filter,
            limit=1000,  # Get up to 1000 at a time
            with_payload=False,
            with_vectors=False,
        )

        company_points = scroll_result[0]
        next_page_offset = scroll_result[1]
        total_company_points = len(company_points)

        # Continue scrolling if there are more points
        while next_page_offset is not None:
            scroll_result = client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=company_filter,
                offset=next_page_offset,
                limit=1000,
                with_payload=False,
                with_vectors=False,
            )
            batch_points = scroll_result[0]
            next_page_offset = scroll_result[1]
            total_company_points += len(batch_points)
            company_points.extend(batch_points)

        print(
            f"📊 Found {total_company_points:,} points for company {TARGET_COMPANY_ID}"
        )

        if total_company_points == 0:
            print("✅ No points found for this company. Nothing to delete.")
            return

        # Step 2: Confirm deletion
        print(f"\n⚠️  CONFIRMATION REQUIRED")
        print(f"   🎯 Company: {TARGET_COMPANY_ID}")
        print(f"   🗑️  Points to delete: {total_company_points:,}")
        print(f"   📊 Total points in collection: {total_points:,}")
        print(
            f"   📈 Percentage to delete: {(total_company_points/total_points*100):.1f}%"
        )

        confirm = input(
            f"\n🚨 Type 'DELETE {total_company_points}' to confirm deletion: "
        )

        if confirm != f"DELETE {total_company_points}":
            print("❌ Deletion cancelled - confirmation text didn't match")
            return

        # Step 3: Delete points
        print(f"\n🗑️  Starting deletion of {total_company_points:,} points...")

        # Use filter-based deletion (more efficient)
        print("🔄 Deleting points using filter...")
        delete_result = client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=company_filter,
            wait=True,  # Wait for operation to complete
        )

        print(f"✅ Deletion completed!")
        print(f"   🗑️  Operation ID: {delete_result.operation_id}")
        print(f"   ⏱️  Status: {delete_result.status}")

        # Step 4: Verify deletion
        print(f"\n🔍 Verifying deletion...")

        # Check remaining points
        verify_scroll = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=company_filter,
            limit=10,
            with_payload=False,
            with_vectors=False,
        )

        remaining_points = len(verify_scroll[0])

        if remaining_points == 0:
            print("✅ Verification successful - No points remain for this company")
        else:
            print(f"⚠️  Verification found {remaining_points} remaining points")

        # Final collection stats
        final_collection_info = client.get_collection(COLLECTION_NAME)
        final_total_points = final_collection_info.points_count

        print(f"\n📊 FINAL STATISTICS")
        print(f"   🏭 Collection: {COLLECTION_NAME}")
        print(f"   📊 Points before: {total_points:,}")
        print(f"   📊 Points after: {final_total_points:,}")
        print(f"   🗑️  Points deleted: {total_points - final_total_points:,}")
        print(f"   🎯 Target company points: {total_company_points:,}")

        print(f"\n🎉 Company data deletion completed successfully!")

    except Exception as e:
        print(f"❌ Error during deletion: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(delete_company_data())
