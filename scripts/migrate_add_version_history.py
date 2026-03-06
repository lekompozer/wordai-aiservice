"""
Migration: Add version_history field to all documents
Run once to migrate existing documents in production

Usage:
    python migrate_add_version_history.py

This script:
1. Finds all documents without version_history field
2. Creates initial version snapshot from current state
3. Adds version_history array with initial version
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

# Load environment variables
env_var = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
env_file = "development.env" if env_var == "development" else ".env"
load_dotenv(env_file)

from src.services.online_test_utils import get_mongodb_service


def migrate_version_history():
    """Add version_history to all documents without it"""

    print("🔧 Starting migration: Add version_history to documents...")

    mongo = get_mongodb_service()
    db = mongo.db

    # Find all documents without version_history
    query = {"version_history": {"$exists": False}}
    documents = db.documents.find(query)

    migrated_count = 0
    skipped_count = 0
    error_count = 0

    for doc in documents:
        try:
            # Create initial version from current state
            initial_version = {
                "version": doc.get("version", 1),
                "created_at": doc.get("created_at", datetime.utcnow()),
                "description": "Initial version (migrated from existing document)",
                "content_html": doc.get("content_html", ""),
                "slides_outline": doc.get("slides_outline", []),
                "slide_backgrounds": doc.get("slide_backgrounds", []),
                "slide_elements": doc.get("slide_elements", []),
                "slide_count": len(doc.get("slides_outline", [])),
            }

            # Update document with version_history
            result = db.documents.update_one(
                {"_id": doc["_id"]}, {"$set": {"version_history": [initial_version]}}
            )

            if result.modified_count > 0:
                migrated_count += 1

                # Log progress every 10 documents
                if migrated_count % 10 == 0:
                    print(f"   ✅ Migrated {migrated_count} documents...")
            else:
                skipped_count += 1

        except Exception as e:
            error_count += 1
            print(f"   ❌ Error migrating document {doc.get('document_id')}: {e}")

    print("\n" + "=" * 60)
    print("📊 Migration Summary:")
    print(f"   ✅ Migrated: {migrated_count} documents")
    print(f"   ⏭️  Skipped:  {skipped_count} documents")
    print(f"   ❌ Errors:   {error_count} documents")
    print("=" * 60)

    if error_count > 0:
        print("\n⚠️  Some documents failed migration. Check logs above for details.\n")
    else:
        print("\n🎉 Migration completed successfully!\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  MIGRATION: Add version_history to documents")
    print("=" * 60 + "\n")

    # Confirm before running
    confirm = input("⚠️  This will modify all documents. Continue? (yes/no): ")

    if confirm.lower() == "yes":
        migrate_version_history()
    else:
        print("\n❌ Migration cancelled.\n")
