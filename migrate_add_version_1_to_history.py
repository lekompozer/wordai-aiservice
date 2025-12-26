#!/usr/bin/env python3
"""
Migration: Add version 1 to version_history for existing documents

Problem: Documents created before this fix don't have version 1 in their version_history.
Solution: For documents at version >= 2 with empty/missing version 1, create a version 1 snapshot.
"""

import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from services.online_test_utils import get_mongodb_service


def migrate_version_history():
    """Add version 1 snapshot to documents missing it"""

    mongo = get_mongodb_service()
    db = mongo.db

    # Find documents at version >= 2
    documents = db.documents.find({"is_deleted": False, "version": {"$gte": 2}})

    fixed_count = 0
    skipped_count = 0

    for doc in documents:
        document_id = doc["document_id"]
        version_history = doc.get("version_history", [])

        # Check if version 1 exists in history
        has_version_1 = any(v.get("version") == 1 for v in version_history)

        if has_version_1:
            print(f"✅ {document_id}: Already has version 1")
            skipped_count += 1
            continue

        # Find the oldest version in history (should be version 2)
        if version_history:
            oldest_version = min(version_history, key=lambda v: v.get("version", 999))
            oldest_version_num = oldest_version.get("version", 2)

            # Create version 1 snapshot based on version 2
            version_1_snapshot = {
                "version": 1,
                "created_at": doc.get("created_at", datetime.utcnow()),
                "description": "Initial version (reconstructed)",
                "content_html": oldest_version.get("content_html", ""),
                "slides_outline": oldest_version.get("slides_outline", []),
                "slide_backgrounds": oldest_version.get("slide_backgrounds", []),
                "slide_elements": oldest_version.get("slide_elements", []),
                "slide_count": len(oldest_version.get("slides_outline", [])),
            }
        else:
            # No history at all, create from current state
            version_1_snapshot = {
                "version": 1,
                "created_at": doc.get("created_at", datetime.utcnow()),
                "description": "Initial version (reconstructed from current)",
                "content_html": doc.get("content_html", ""),
                "slides_outline": doc.get("slides_outline", []),
                "slide_backgrounds": doc.get("slide_backgrounds", []),
                "slide_elements": doc.get("slide_elements", []),
                "slide_count": len(doc.get("slides_outline", [])),
            }

        # Add version 1 to the beginning of version_history
        new_history = [version_1_snapshot] + version_history

        # Update document
        db.documents.update_one(
            {"document_id": document_id}, {"$set": {"version_history": new_history}}
        )

        print(
            f"🔧 {document_id}: Added version 1 to history (current version: {doc.get('version')})"
        )
        fixed_count += 1

    print(f"\n✅ Migration complete!")
    print(f"   Fixed: {fixed_count} documents")
    print(f"   Skipped: {skipped_count} documents (already had version 1)")


if __name__ == "__main__":
    print("🔍 Checking documents for missing version 1...")
    migrate_version_history()
