#!/usr/bin/env python3
"""
Script to inspect Qdrant points for a specific company in detail
Script để kiểm tra chi tiết các point trong Qdrant cho một company cụ thể
"""

import os
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Qdrant configuration from .env
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "multi_company_data")

# Company to inspect
TARGET_COMPANY_ID = "1e789800-b402-41b0-99d6-2e8d494a3beb"


async def inspect_company_points():
    """Inspect all points for the target company in detail"""

    print("🔍 QDRANT COMPANY DATA INSPECTION")
    print("=" * 60)
    print(f"🎯 Target Company: {TARGET_COMPANY_ID}")
    print(f"🏭 Collection: {COLLECTION_NAME}")
    print("=" * 60)

    try:
        # Initialize Qdrant client
        print("🔌 Connecting to Qdrant...")
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )

        # Create filter for the target company
        company_filter = Filter(
            must=[
                FieldCondition(
                    key="company_id", match=MatchValue(value=TARGET_COMPANY_ID)
                )
            ]
        )

        # Get all points with full payload
        print("📊 Retrieving all company points with full payload...")
        scroll_result = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=company_filter,
            limit=1000,
            with_payload=True,  # Get full payload
            with_vectors=False,  # We don't need vectors for analysis
        )

        points = scroll_result[0]
        next_page_offset = scroll_result[1]

        # Continue scrolling if there are more points
        while next_page_offset is not None:
            scroll_result = client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=company_filter,
                offset=next_page_offset,
                limit=1000,
                with_payload=True,
                with_vectors=False,
            )
            batch_points = scroll_result[0]
            next_page_offset = scroll_result[1]
            points.extend(batch_points)

        print(f"📊 Found {len(points)} points for company {TARGET_COMPANY_ID}")
        print("=" * 60)

        # Analyze point structure and categorize
        product_points = []
        service_points = []
        file_points = []
        other_points = []

        # Group by different criteria
        by_file_id = {}
        by_data_type = {}
        by_item_type = {}

        for i, point in enumerate(points, 1):
            payload = point.payload
            point_id = point.id

            print(f"\n🔍 POINT #{i}")
            print(f"   🆔 Point ID: {point_id}")
            print(f"   🏢 Company ID: {payload.get('company_id', 'N/A')}")

            # Categorize by data_type
            data_type = payload.get("data_type", "unknown")
            if data_type not in by_data_type:
                by_data_type[data_type] = []
            by_data_type[data_type].append(point_id)

            # Categorize by file_id
            file_id = payload.get("file_id", "unknown")
            if file_id not in by_file_id:
                by_file_id[file_id] = []
            by_file_id[file_id].append(point_id)

            # Categorize by item_type (product/service)
            item_type = payload.get("item_type", payload.get("type", "unknown"))
            if item_type not in by_item_type:
                by_item_type[item_type] = []
            by_item_type[item_type].append(point_id)

            # Key fields analysis
            print(f"   📂 Data Type: {data_type}")
            print(f"   📄 File ID: {file_id}")
            print(f"   🏷️  Item Type: {item_type}")

            # Check for product/service specific fields
            product_id = payload.get("product_id", payload.get("item_id"))
            service_id = payload.get("service_id", payload.get("item_id"))

            if product_id:
                print(f"   📦 Product ID: {product_id}")
                product_points.append(
                    {
                        "point_id": point_id,
                        "product_id": product_id,
                        "file_id": file_id,
                        "data_type": data_type,
                    }
                )

            if service_id and not product_id:  # Avoid double counting
                print(f"   🔧 Service ID: {service_id}")
                service_points.append(
                    {
                        "point_id": point_id,
                        "service_id": service_id,
                        "file_id": file_id,
                        "data_type": data_type,
                    }
                )

            # Check for important metadata
            name = payload.get("name", payload.get("title", "N/A"))
            print(f"   📝 Name/Title: {name}")

            # Check for tags
            tags = payload.get("tags", [])
            if tags:
                print(f"   🏷️  Tags: {tags}")

            # Check for source info
            source = payload.get("source", payload.get("source_file", "N/A"))
            print(f"   📍 Source: {source}")

            # Check timestamp
            timestamp = payload.get("timestamp", payload.get("created_at", "N/A"))
            print(f"   ⏰ Timestamp: {timestamp}")

        # Summary analysis
        print("\n" + "=" * 60)
        print("📊 ANALYSIS SUMMARY")
        print("=" * 60)

        print(f"📦 Products found: {len(product_points)}")
        print(f"🔧 Services found: {len(service_points)}")
        print(f"📄 Total points: {len(points)}")

        print(f"\n📂 By Data Type:")
        for data_type, point_ids in by_data_type.items():
            print(f"   {data_type}: {len(point_ids)} points")

        print(f"\n📄 By File ID:")
        for file_id, point_ids in by_file_id.items():
            print(f"   {file_id}: {len(point_ids)} points")

        print(f"\n🏷️  By Item Type:")
        for item_type, point_ids in by_item_type.items():
            print(f"   {item_type}: {len(point_ids)} points")

        # Show products and services for deletion analysis
        if product_points:
            print(f"\n📦 PRODUCT POINTS DETAILS:")
            for prod in product_points:
                print(
                    f"   Point: {prod['point_id']} | Product: {prod['product_id']} | File: {prod['file_id']}"
                )

        if service_points:
            print(f"\n🔧 SERVICE POINTS DETAILS:")
            for serv in service_points:
                print(
                    f"   Point: {serv['point_id']} | Service: {serv['service_id']} | File: {serv['file_id']}"
                )

        # Analysis for deletion issues
        print(f"\n🔍 DELETION ANALYSIS:")
        print(f"   ❓ Why delete operations might fail:")
        print(f"   1. Points may not have proper product_id/service_id fields")
        print(f"   2. Delete logic may be filtering on wrong fields")
        print(f"   3. Field values may not match expected format")
        print(f"   4. Qdrant indexes may not exist for filtered fields")

        # Check if we can identify index requirements
        print(f"\n🔧 REQUIRED FIELDS FOR DELETION:")
        unique_product_ids = set()
        unique_service_ids = set()
        unique_file_ids = set()

        for point in points:
            payload = point.payload
            if payload.get("product_id"):
                unique_product_ids.add(payload["product_id"])
            if payload.get("service_id"):
                unique_service_ids.add(payload["service_id"])
            if payload.get("file_id"):
                unique_file_ids.add(payload["file_id"])

        print(
            f"   📦 Unique product_ids: {len(unique_product_ids)} -> {list(unique_product_ids)[:5]}"
        )
        print(
            f"   🔧 Unique service_ids: {len(unique_service_ids)} -> {list(unique_service_ids)[:5]}"
        )
        print(
            f"   📄 Unique file_ids: {len(unique_file_ids)} -> {list(unique_file_ids)[:5]}"
        )

    except Exception as e:
        print(f"❌ Error during inspection: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(inspect_company_points())
