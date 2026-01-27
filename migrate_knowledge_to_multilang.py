"""
Migration Script: Knowledge Articles to Multi-Language System
Adds multilang fields (title_multilang, content_multilang, excerpt_multilang) to existing knowledge articles
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database.db_manager import DBManager

# Dry run mode
DRY_RUN = False  # Set to True to preview changes without executing


def migrate_knowledge_to_multilang():
    """
    Add multilang fields to existing knowledge articles

    Transformation:
    - title → title_multilang = {"vi": title}
    - content → content_multilang = {"vi": content}
    - excerpt → excerpt_multilang = {"vi": excerpt}
    - Add available_languages = ["vi"]
    """

    print("=" * 80)
    print("MIGRATION: Knowledge Articles → Multi-Language System")
    print("=" * 80)

    if DRY_RUN:
        print("\n⚠️  DRY RUN MODE - No changes will be made")
        print("Set DRY_RUN = False to execute migration\n")

    db_manager = DBManager()
    db = db_manager.db

    collection = db.knowledge_articles

    # Statistics
    stats = {
        "total_articles": 0,
        "already_migrated": 0,
        "migrated": 0,
        "errors": 0,
    }

    # Get all knowledge articles
    articles = list(collection.find({}))
    stats["total_articles"] = len(articles)

    print(f"\nFound {stats['total_articles']} knowledge articles\n")

    for article in articles:
        try:
            article_id = article["id"]
            title = article.get("title", "")
            content = article.get("content", "")
            excerpt = article.get("excerpt", "")

            # Check if already migrated
            if "title_multilang" in article:
                print(f"⏭️  Article {article_id}: Already migrated")
                stats["already_migrated"] += 1
                continue

            print(f"Migrating article {article_id}...")
            print(f"  Title: {title[:50]}...")

            # Prepare multilang fields
            update_data = {
                "title_multilang": {"vi": title} if title else {},
                "content_multilang": {"vi": content} if content else {},
                "excerpt_multilang": {"vi": excerpt} if excerpt else {},
                "available_languages": ["vi"],
                "updated_at": datetime.utcnow(),
            }

            # Update document
            if not DRY_RUN:
                collection.update_one({"id": article_id}, {"$set": update_data})

            print(f"  ✅ Migrated with Vietnamese content")
            stats["migrated"] += 1

        except Exception as e:
            print(
                f"  ❌ Error migrating article {article.get('id', 'unknown')}: {str(e)}"
            )
            stats["errors"] += 1

    # Print summary
    print("\n" + "=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Total articles:      {stats['total_articles']}")
    print(f"Already migrated:    {stats['already_migrated']}")
    print(f"Newly migrated:      {stats['migrated']}")
    print(f"Errors:              {stats['errors']}")
    print("=" * 80)

    if DRY_RUN:
        print("\n⚠️  DRY RUN COMPLETE - No changes were made")
        print("Set DRY_RUN = False to execute migration")
    else:
        print("\n✅ MIGRATION COMPLETE")


if __name__ == "__main__":
    try:
        migrate_knowledge_to_multilang()
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Migration failed: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
