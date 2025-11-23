"""
Migration Script: Copy content from documents to chapters

This script migrates chapters from document-linking mode to inline mode:
1. Find all chapters with content_source="document"
2. Copy content_html from linked document to chapter
3. Update content_source to "inline"
4. Set document_id to None

Run: python migrate_chapters_to_inline.py
"""

import sys
from datetime import datetime, timezone
from src.database.db_manager import DBManager


def migrate_chapters_to_inline():
    """Migrate all chapters from document-linking mode to inline mode"""

    print("=" * 70)
    print("📦 Chapter Migration: Document Linking → Inline Mode")
    print("=" * 70 + "\n")

    # Initialize database
    db_manager = DBManager()
    db = db_manager.db

    # Find chapters using document linking
    chapters_cursor = db.book_chapters.find(
        {"content_source": "document", "document_id": {"$ne": None}, "deleted_at": None}
    )

    chapters = list(chapters_cursor)
    total = len(chapters)

    print(f"📊 Found {total} chapters using document linking mode\n")

    if total == 0:
        print("✅ No chapters to migrate!")
        return

    # Ask for confirmation
    print("⚠️  This will:")
    print("   1. Copy content_html from documents to chapters")
    print("   2. Change content_source from 'document' to 'inline'")
    print("   3. Set document_id to None")
    print("\nOriginal documents will NOT be deleted.\n")

    confirm = input(f"Migrate {total} chapters? (yes/no): ").strip().lower()

    if confirm != "yes":
        print("❌ Migration cancelled")
        return

    print("\n" + "=" * 70)
    print("🚀 Starting Migration...")
    print("=" * 70 + "\n")

    success_count = 0
    error_count = 0
    empty_count = 0

    for idx, chapter in enumerate(chapters, 1):
        chapter_id = chapter["chapter_id"]
        title = chapter.get("title", "Untitled")
        document_id = chapter.get("document_id")

        print(f"[{idx}/{total}] {title} (chapter: {chapter_id})")

        # Find linked document
        document = db.documents.find_one(
            {"document_id": document_id}, {"_id": 0, "content_html": 1}
        )

        if not document:
            print(f"   ❌ Document {document_id} not found!")
            error_count += 1
            continue

        content_html = document.get("content_html", "")

        if not content_html:
            print(f"   ⚠️  Document has no content (empty)")
            empty_count += 1
            # Still update to inline mode, just with empty content

        # Update chapter to inline mode
        result = db.book_chapters.update_one(
            {"chapter_id": chapter_id},
            {
                "$set": {
                    "content_source": "inline",
                    "content_html": content_html,
                    "document_id": None,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        if result.modified_count > 0:
            print(f"   ✅ Migrated: {len(content_html):,} chars copied")
            success_count += 1
        else:
            print(f"   ❌ Failed to update chapter")
            error_count += 1

    # Summary
    print("\n" + "=" * 70)
    print("📊 Migration Summary")
    print("=" * 70)
    print(f"   ✅ Successfully migrated: {success_count}")
    print(f"   ⚠️  Empty content: {empty_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"   📦 Total processed: {total}")
    print()

    # Verify
    remaining = db.book_chapters.count_documents(
        {"content_source": "document", "deleted_at": None}
    )

    print(f"🔍 Verification: {remaining} chapters still use document linking")

    if remaining == 0:
        print("✅ All chapters successfully migrated to inline mode!")
    else:
        print(f"⚠️  {remaining} chapters still need migration")

    print()


if __name__ == "__main__":
    try:
        migrate_chapters_to_inline()
    except KeyboardInterrupt:
        print("\n\n❌ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
