#!/usr/bin/env python3
"""
Script to create necessary Qdrant indexes for filter operations
Script để tạo các index cần thiết trong Qdrant cho các thao tác filter
"""

import os
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Qdrant configuration from .env
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "multi_company_data")


async def create_qdrant_indexes():
    """Create necessary indexes for Qdrant filter operations"""

    print("🔧 QDRANT INDEX CREATION")
    print("=" * 50)
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

        print(f"\n📊 Current collection info:")
        collection_info = client.get_collection(COLLECTION_NAME)
        print(f"   Points: {collection_info.points_count:,}")
        print(f"   Vector size: {collection_info.config.params.vectors.size}")

        # List current indexes
        try:
            collection_info = client.get_collection(COLLECTION_NAME)
            # Check payload schema if available (Qdrant Cloud feature)
            print(f"\n🔍 Checking existing indexes...")
        except Exception as e:
            print(f"⚠️ Could not retrieve detailed collection info: {e}")

        # Define indexes needed for our delete operations
        indexes_to_create = [
            {
                "field_name": "product_id",
                "schema_type": PayloadSchemaType.KEYWORD,
                "description": "Product ID index for product deletion",
            },
            {
                "field_name": "service_id",
                "schema_type": PayloadSchemaType.KEYWORD,
                "description": "Service ID index for service deletion",
            },
            {
                "field_name": "file_id",
                "schema_type": PayloadSchemaType.KEYWORD,
                "description": "File ID index for file-based deletion",
            },
            {
                "field_name": "company_id",
                "schema_type": PayloadSchemaType.KEYWORD,
                "description": "Company ID index for filtering by company",
            },
            {
                "field_name": "content_type",
                "schema_type": PayloadSchemaType.KEYWORD,
                "description": "Content type index for filtering by type",
            },
            {
                "field_name": "item_type",
                "schema_type": PayloadSchemaType.KEYWORD,
                "description": "Item type index for filtering product vs service",
            },
            {
                "field_name": "data_type",
                "schema_type": PayloadSchemaType.KEYWORD,
                "description": "Data type index for filtering by data category",
            },
        ]

        print(f"\n🔧 Creating {len(indexes_to_create)} payload indexes...")

        created_count = 0
        failed_count = 0

        for index_config in indexes_to_create:
            try:
                field_name = index_config["field_name"]
                schema_type = index_config["schema_type"]
                description = index_config["description"]

                print(f"   📝 Creating index: {field_name} ({schema_type.value})")

                # Create payload index
                client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name=field_name,
                    field_schema=schema_type,
                )

                print(f"   ✅ Created: {field_name}")
                created_count += 1

            except Exception as e:
                error_msg = str(e).lower()
                if "already exist" in error_msg or "already_exists" in error_msg:
                    print(f"   ⚠️ Already exists: {field_name}")
                    created_count += 1  # Count as success
                else:
                    print(f"   ❌ Failed to create {field_name}: {e}")
                    failed_count += 1

        print(f"\n📊 INDEX CREATION SUMMARY")
        print(f"   ✅ Created/Existing: {created_count}")
        print(f"   ❌ Failed: {failed_count}")
        print(f"   📊 Total attempted: {len(indexes_to_create)}")

        if failed_count == 0:
            print(f"\n🎉 All indexes created successfully!")
            print(f"   🗑️ Delete operations should now work properly")
            print(f"   🔍 Filter-based queries will be more efficient")
        else:
            print(f"\n⚠️ Some indexes failed to create. Check the errors above.")

        # Verify indexes by listing them
        print(f"\n🔍 Verifying created indexes...")
        try:
            # Try to get collection info again to see if indexes are visible
            updated_info = client.get_collection(COLLECTION_NAME)
            print(f"✅ Collection still accessible after index creation")
        except Exception as e:
            print(f"⚠️ Could not verify indexes: {e}")

        print(f"\n✅ Index creation process completed!")

    except Exception as e:
        print(f"❌ Error during index creation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(create_qdrant_indexes())
