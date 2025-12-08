"""
Fix duplicate authors with case-insensitive author_id
Merge duplicates and ensure all author_id are lowercase
"""

import sys
from config.config import get_mongodb
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_duplicate_authors():
    """Find and merge duplicate authors with different cases"""
    db = get_mongodb()
    authors_collection = db["book_authors"]

    # Get all authors
    all_authors = list(
        authors_collection.find(
            {},
            {
                "_id": 1,
                "author_id": 1,
                "user_id": 1,
                "total_books": 1,
                "books": 1,
                "created_at": 1,
            },
        )
    )

    logger.info(f"📊 Found {len(all_authors)} total authors")

    # Group by lowercase author_id
    grouped = defaultdict(list)
    for author in all_authors:
        lowercase_id = author["author_id"].lower()
        grouped[lowercase_id].append(author)

    # Find duplicates
    duplicates = {k: v for k, v in grouped.items() if len(v) > 1}

    if not duplicates:
        logger.info("✅ No duplicates found!")
        return

    logger.warning(f"⚠️  Found {len(duplicates)} duplicate groups:")

    for lowercase_id, authors in duplicates.items():
        logger.info(f"\n🔍 Duplicate group: {lowercase_id}")
        for author in authors:
            logger.info(
                f"   - {author['author_id']} (user: {author['user_id']}, books: {author.get('total_books', 0)})"
            )

        # Keep the oldest one (by created_at) with correct lowercase
        authors_sorted = sorted(authors, key=lambda x: x.get("created_at", ""))
        primary = authors_sorted[0]
        duplicates_to_remove = authors_sorted[1:]

        # Collect all books from duplicates
        all_books = set(primary.get("books", []))
        for dup in duplicates_to_remove:
            all_books.update(dup.get("books", []))

        # Update primary author with correct lowercase and merged books
        update_result = authors_collection.update_one(
            {"_id": primary["_id"]},
            {
                "$set": {
                    "author_id": lowercase_id,  # Ensure lowercase
                    "books": list(all_books),
                    "total_books": len(all_books),
                }
            },
        )
        logger.info(
            f"✅ Updated primary author: {lowercase_id} (merged {len(all_books)} books)"
        )

        # Remove duplicates
        for dup in duplicates_to_remove:
            delete_result = authors_collection.delete_one({"_id": dup["_id"]})
            logger.info(f"🗑️  Removed duplicate: {dup['author_id']}")

    # Also fix any remaining authors that aren't lowercase
    logger.info("\n🔧 Fixing remaining non-lowercase author_ids...")

    non_lowercase = authors_collection.find(
        {"author_id": {"$regex": "^@[A-Z]"}}  # Contains uppercase after @
    )

    count = 0
    for author in non_lowercase:
        lowercase_id = author["author_id"].lower()

        # Check if lowercase version already exists
        existing = authors_collection.find_one({"author_id": lowercase_id})
        if existing and str(existing["_id"]) != str(author["_id"]):
            logger.warning(
                f"⚠️  Cannot lowercase {author['author_id']} - lowercase version exists. Skipping."
            )
            continue

        # Update to lowercase
        authors_collection.update_one(
            {"_id": author["_id"]}, {"$set": {"author_id": lowercase_id}}
        )
        count += 1
        logger.info(f"✅ Lowercased: {author['author_id']} → {lowercase_id}")

    logger.info(f"\n✅ Fixed {count} non-lowercase author_ids")

    # Summary
    final_count = authors_collection.count_documents({})
    logger.info(f"\n📊 Final author count: {final_count}")


if __name__ == "__main__":
    try:
        fix_duplicate_authors()
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)
