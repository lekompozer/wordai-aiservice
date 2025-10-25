"""
Migration Script: Rename collection document_templates → user_upload_files
==========================================================================

This script renames the MongoDB collection from 'document_templates' to 'user_upload_files'
to make the naming more meaningful and accurate.

Usage:
    python3 migrate_collection_name.py

What it does:
1. Connects to MongoDB
2. Renames collection: document_templates → user_upload_files
3. Verifies the migration was successful
4. Shows document count before/after

IMPORTANT: This is a MongoDB collection rename operation - it's instant and atomic.
All data, indexes, and references remain intact.
"""

import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from config import config


async def migrate_collection_name():
    """Migrate collection name from document_templates to user_upload_files"""

    print("=" * 80)
    print("Collection Migration: document_templates → user_upload_files")
    print("=" * 80)

    # Connect to MongoDB using config values
    mongo_uri = config.MONGODB_URI_AUTH
    db_name = config.MONGODB_NAME

    print(f"\n📡 Connecting to MongoDB: {mongo_uri[:50]}...")
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]

    try:
        # Check if old collection exists
        collections = await db.list_collection_names()

        if "document_templates" not in collections:
            print("\n❌ ERROR: Collection 'document_templates' does not exist!")
            print(f"Available collections: {collections}")
            return False

        if "user_upload_files" in collections:
            print("\n⚠️  WARNING: Collection 'user_upload_files' already exists!")

            # Count documents in both
            old_count = await db.document_templates.count_documents({})
            new_count = await db.user_upload_files.count_documents({})

            print(f"   - document_templates: {old_count} documents")
            print(f"   - user_upload_files: {new_count} documents")

            # Check for auto-yes flag
            import sys

            if "--auto-yes" not in sys.argv:
                response = input(
                    "\nDo you want to DROP 'user_upload_files' and proceed? (yes/no): "
                )
                if response.lower() != "yes":
                    print("❌ Migration cancelled by user")
                    return False
            else:
                print(
                    "\n✅ Auto-confirmation: Will DROP 'user_upload_files' and proceed"
                )

            print(f"\n🗑️  Dropping existing 'user_upload_files' collection...")
            await db.user_upload_files.drop()
            print("✅ Collection dropped")

        # Count documents before migration
        doc_count = await db.document_templates.count_documents({})
        print(f"\n📊 Documents in 'document_templates': {doc_count}")

        # Get sample document to verify
        sample = await db.document_templates.find_one()
        if sample:
            print(f"✅ Sample document ID: {sample.get('_id', 'N/A')}")
            print(f"   - name: {sample.get('name', 'N/A')}")
            print(f"   - user_id: {sample.get('user_id', 'N/A')}")

        # Perform the rename operation
        print(f"\n🔄 Renaming collection...")
        await db.document_templates.rename("user_upload_files")

        print("✅ Collection renamed successfully!")

        # Verify migration
        collections = await db.list_collection_names()

        if (
            "user_upload_files" in collections
            and "document_templates" not in collections
        ):
            new_count = await db.user_upload_files.count_documents({})
            print(f"\n✅ MIGRATION SUCCESSFUL!")
            print(f"   - Old collection 'document_templates': REMOVED")
            print(f"   - New collection 'user_upload_files': {new_count} documents")

            if new_count == doc_count:
                print(f"   - Document count matches: {doc_count} → {new_count} ✅")
            else:
                print(f"   - ⚠️  WARNING: Document count mismatch!")
                print(f"      Before: {doc_count}, After: {new_count}")

            # Verify sample document
            sample_after = (
                await db.user_upload_files.find_one({"_id": sample["_id"]})
                if sample
                else None
            )
            if sample_after:
                print(f"\n✅ Sample document verified in new collection:")
                print(f"   - ID: {sample_after.get('_id')}")
                print(f"   - name: {sample_after.get('name')}")

            return True
        else:
            print(f"\n❌ MIGRATION FAILED!")
            print(f"Collections after rename: {collections}")
            return False

    except Exception as e:
        print(f"\n❌ Migration failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        client.close()
        print("\n🔌 MongoDB connection closed")


async def verify_indexes():
    """Verify that indexes were preserved after rename"""

    # Connect to MongoDB using config values
    mongo_uri = config.MONGODB_URI_AUTH
    db_name = config.MONGODB_NAME

    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]

    try:
        print("\n" + "=" * 80)
        print("Verifying Indexes")
        print("=" * 80)

        # Get indexes
        indexes = await db.user_upload_files.list_indexes().to_list(length=None)

        print(f"\n📑 Indexes on 'user_upload_files' collection:")
        for idx in indexes:
            print(f"   - {idx['name']}: {idx.get('key', {})}")

        # Check required indexes exist
        required_indexes = ["type", "is_active", "user_id_1_type_1_is_active_1"]
        index_names = [idx["name"] for idx in indexes]

        missing = [idx for idx in required_indexes if idx not in index_names]
        if missing:
            print(f"\n⚠️  Missing indexes: {missing}")
            print("   Run the database initialization script to recreate them.")
        else:
            print(f"\n✅ All required indexes present")

    except Exception as e:
        print(f"\n❌ Error verifying indexes: {e}")
    finally:
        client.close()


async def main():
    """Main migration function"""

    print("\n🚀 Starting Collection Migration...")
    print("This will rename: document_templates → user_upload_files")
    print("\n⚠️  IMPORTANT:")
    print("   - This operation is INSTANT and ATOMIC")
    print("   - All data and indexes are preserved")
    print("   - Application MUST be updated to use new collection name")
    print("   - Code already updated in this deployment")

    # Check for --auto-yes flag
    import sys

    if "--auto-yes" not in sys.argv:
        response = input("\nProceed with migration? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Migration cancelled by user")
            return
    else:
        print("\n✅ Auto-confirmation enabled (--auto-yes flag)")

    # Perform migration
    success = await migrate_collection_name()

    if success:
        # Verify indexes
        await verify_indexes()

        print("\n" + "=" * 80)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 80)
        print("\nNext steps:")
        print("1. ✅ Collection renamed: document_templates → user_upload_files")
        print("2. ✅ Code already updated to use new collection name")
        print("3. 🔄 Restart application to apply changes")
        print("4. 🧪 Test upload and conversion endpoints")
        print("\nRestart command:")
        print("   bash deploy-compose-with-rollback.sh")
    else:
        print("\n❌ Migration failed. Please review errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
