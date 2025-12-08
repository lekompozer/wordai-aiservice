#!/usr/bin/env python3
"""
Migration Script: Add slug and meta_description to existing published tests

This script:
1. Finds all published tests (marketplace_config.is_public = true)
2. Generates slug from title (Vietnamese-safe)
3. Generates meta_description from description
4. Updates tests with unique slugs
5. Creates database index for slug field

Run: python migrate_add_test_slugs.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.online_test_utils import get_mongodb_service
from src.utils.slug_generator import generate_slug, generate_meta_description
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_slug_exists(db, slug, exclude_id=None):
    """Check if slug already exists in database"""
    query = {"slug": slug}
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}
    return db.online_tests.count_documents(query) > 0


def generate_unique_test_slug(db, title, test_id):
    """Generate unique slug for test"""
    base_slug = generate_slug(title)

    # Truncate if too long
    if len(base_slug) > 96:  # Leave room for suffix
        base_slug = base_slug[:96]

    # Check uniqueness
    slug = base_slug
    if not check_slug_exists(db, slug, test_id):
        return slug

    # Append number
    counter = 2
    while counter < 100:
        slug = f"{base_slug}-{counter}"
        if not check_slug_exists(db, slug, test_id):
            return slug
        counter += 1

    # Fallback to timestamp
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    return f"{base_slug}-{timestamp}"


def migrate_tests():
    """Main migration function"""
    try:
        mongo_service = get_mongodb_service()
        db = mongo_service.db

        logger.info("=" * 70)
        logger.info("🚀 Starting test slug migration...")
        logger.info("=" * 70)

        # Find all published tests
        published_tests = list(
            db.online_tests.find({"marketplace_config.is_public": True})
        )

        logger.info(f"\n📊 Found {len(published_tests)} published tests to migrate")

        if len(published_tests) == 0:
            logger.info("✅ No tests to migrate!")
            return

        # Process each test
        success_count = 0
        error_count = 0
        skipped_count = 0

        for idx, test in enumerate(published_tests, 1):
            test_id = test["_id"]
            title = test.get("title", "Untitled Test")
            marketplace_config = test.get("marketplace_config", {})
            description = marketplace_config.get("description", "")

            logger.info(f"\n[{idx}/{len(published_tests)}] Processing test: {test_id}")
            logger.info(f"   Title: {title}")

            try:
                # ✅ REGENERATE: Always regenerate slug (even if exists) to fix đ/Đ bug
                old_slug = test.get("slug")
                if old_slug:
                    logger.info(f"   🔄 Regenerating slug (old: '{old_slug}')")

                # Generate slug
                slug = generate_unique_test_slug(db, title, test_id)
                logger.info(f"   ✨ New slug: {slug}")

                # Generate meta description
                meta = generate_meta_description(description, max_length=160)
                logger.info(f"   📝 Meta: {meta[:50]}...")

                # Update test document
                result = db.online_tests.update_one(
                    {"_id": test_id},
                    {
                        "$set": {
                            "slug": slug,
                            "meta_description": meta,
                            "marketplace_config.slug": slug,
                            "marketplace_config.meta_description": meta,
                        }
                    },
                )

                if result.modified_count > 0:
                    logger.info(f"   ✅ Successfully updated!")
                    success_count += 1
                else:
                    logger.warning(f"   ⚠️  Update returned 0 modified count")
                    error_count += 1

            except Exception as e:
                logger.error(f"   ❌ Error processing test {test_id}: {e}")
                error_count += 1
                continue

        # Create index for slug
        logger.info(f"\n{'=' * 70}")
        logger.info("📇 Creating database index for slug field...")
        try:
            db.online_tests.create_index(
                [("slug", 1)], unique=True, sparse=True, name="slug_unique_index"
            )
            logger.info("✅ Index created successfully!")
        except Exception as e:
            logger.error(f"❌ Failed to create index: {e}")

        # Summary
        logger.info(f"\n{'=' * 70}")
        logger.info("📊 MIGRATION SUMMARY")
        logger.info(f"{'=' * 70}")
        logger.info(f"✅ Successfully migrated: {success_count}")
        logger.info(f"⏭️  Skipped (already has slug): {skipped_count}")
        logger.info(f"❌ Errors: {error_count}")
        logger.info(f"📊 Total processed: {len(published_tests)}")
        logger.info(f"{'=' * 70}")

        if error_count == 0:
            logger.info("\n🎉 Migration completed successfully!")
        else:
            logger.warning(f"\n⚠️  Migration completed with {error_count} errors")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    logger.info("\n" + "=" * 70)
    logger.info("TEST SLUG MIGRATION SCRIPT")
    logger.info("=" * 70)
    logger.info("\nThis script will:")
    logger.info("1. Find all published tests")
    logger.info("2. Generate slugs from titles (Vietnamese-safe)")
    logger.info("3. Generate SEO meta descriptions")
    logger.info("4. Update test documents")
    logger.info("5. Create database index")

    input("\nPress ENTER to continue or Ctrl+C to cancel...")

    migrate_tests()
