#!/usr/bin/env python3
"""
Migration Script: Convert 'document' mode chapters to 'inline' mode
Phase 3: Cleanup deprecated document reference mode

This script migrates chapters using deprecated 'document' reference mode
to the new 'inline' content mode by copying document content directly into chapter.

Usage:
    python migrate_document_to_inline.py [--dry-run] [--batch-size 100]
"""

import sys
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("migration")


class DocumentToInlineMigration:
    """Migrate document mode chapters to inline mode"""

    def __init__(self, db):
        """
        Initialize migration

        Args:
            db: PyMongo Database object
        """
        self.db = db
        self.chapters_collection = db["book_chapters"]
        self.documents_collection = db["documents"]

    async def find_document_chapters(self) -> List[Dict[str, Any]]:
        """
        Find all chapters using 'document' content mode

        Returns:
            List of chapter documents
        """
        try:
            logger.info("🔍 Searching for 'document' mode chapters...")

            # Find chapters with content_mode = "document"
            chapters = list(
                self.chapters_collection.find(
                    {"content_mode": "document"},
                    {
                        "_id": 1,
                        "book_id": 1,
                        "title": 1,
                        "document_id": 1,
                        "user_id": 1,
                    },
                )
            )

            logger.info(f"✅ Found {len(chapters)} document mode chapters")

            return chapters

        except Exception as e:
            logger.error(f"❌ Failed to find document chapters: {e}")
            raise

    async def migrate_chapter(
        self, chapter_id: str, document_id: str, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Migrate single chapter from document to inline mode

        Args:
            chapter_id: Chapter ID
            document_id: Document ID to copy content from
            dry_run: If True, only simulate migration

        Returns:
            Migration result dict
        """
        try:
            # 1. Get document content
            document = self.documents_collection.find_one({"_id": document_id})

            if not document:
                logger.warning(
                    f"⚠️ Document {document_id} not found, skipping chapter {chapter_id}"
                )
                return {
                    "chapter_id": chapter_id,
                    "status": "skipped",
                    "reason": "document_not_found",
                }

            # 2. Extract content
            content = document.get("content", "")
            content_type = document.get("content_type", "html")

            logger.info(
                f"📄 Chapter {chapter_id}: {len(content)} chars ({content_type})"
            )

            if dry_run:
                logger.info(f"🔧 [DRY RUN] Would migrate chapter {chapter_id}")
                return {
                    "chapter_id": chapter_id,
                    "status": "dry_run",
                    "content_length": len(content),
                    "content_type": content_type,
                }

            # 3. Update chapter to inline mode
            result = self.chapters_collection.update_one(
                {"_id": chapter_id},
                {
                    "$set": {
                        "content_mode": "inline",  # Change mode
                        "content": content,  # Copy document content
                        "content_type": content_type,
                        "migrated_from_document": True,  # Migration flag
                        "migrated_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    },
                    "$unset": {
                        "document_id": "",  # Remove document reference
                    },
                },
            )

            if result.modified_count == 1:
                logger.info(f"✅ Migrated chapter {chapter_id} to inline mode")
                return {
                    "chapter_id": chapter_id,
                    "status": "success",
                    "content_length": len(content),
                    "content_type": content_type,
                }
            else:
                logger.warning(f"⚠️ Chapter {chapter_id} not updated")
                return {
                    "chapter_id": chapter_id,
                    "status": "no_change",
                }

        except Exception as e:
            logger.error(f"❌ Failed to migrate chapter {chapter_id}: {e}")
            return {
                "chapter_id": chapter_id,
                "status": "error",
                "error": str(e),
            }

    async def migrate_all(
        self, dry_run: bool = False, batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Migrate all document chapters to inline mode

        Args:
            dry_run: If True, only simulate migration
            batch_size: Process in batches

        Returns:
            Migration summary
        """
        try:
            logger.info("🚀 Starting migration: document → inline")
            logger.info(f"   Mode: {'DRY RUN' if dry_run else 'LIVE'}")
            logger.info(f"   Batch size: {batch_size}")

            # 1. Find all document chapters
            chapters = await self.find_document_chapters()

            if not chapters:
                logger.info("✅ No document chapters to migrate")
                return {
                    "total_chapters": 0,
                    "migrated": 0,
                    "skipped": 0,
                    "errors": 0,
                }

            # 2. Migrate in batches
            total = len(chapters)
            migrated = 0
            skipped = 0
            errors = 0
            results = []

            for i in range(0, total, batch_size):
                batch = chapters[i : i + batch_size]
                logger.info(
                    f"📦 Processing batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}"
                )

                for chapter in batch:
                    chapter_id = chapter["_id"]
                    document_id = chapter.get("document_id")

                    if not document_id:
                        logger.warning(
                            f"⚠️ Chapter {chapter_id} has no document_id, skipping"
                        )
                        skipped += 1
                        continue

                    result = await self.migrate_chapter(
                        chapter_id=chapter_id, document_id=document_id, dry_run=dry_run
                    )

                    results.append(result)

                    if result["status"] == "success":
                        migrated += 1
                    elif result["status"] == "skipped":
                        skipped += 1
                    elif result["status"] == "error":
                        errors += 1

                logger.info(
                    f"   Progress: {i + len(batch)}/{total} "
                    f"(✅ {migrated} | ⚠️ {skipped} | ❌ {errors})"
                )

            # 3. Summary
            logger.info("=" * 80)
            logger.info("📊 Migration Summary:")
            logger.info(f"   Total chapters: {total}")
            logger.info(f"   ✅ Migrated: {migrated}")
            logger.info(f"   ⚠️ Skipped: {skipped}")
            logger.info(f"   ❌ Errors: {errors}")
            logger.info("=" * 80)

            if not dry_run and migrated > 0:
                logger.info("🎉 Migration completed successfully!")
                logger.info("💡 Next steps:")
                logger.info("   1. Verify migrated chapters in production")
                logger.info("   2. Remove deprecated 'document' mode code")
                logger.info("   3. Consider removing unused documents collection")

            return {
                "total_chapters": total,
                "migrated": migrated,
                "skipped": skipped,
                "errors": errors,
                "results": results,
            }

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise

    async def verify_migration(self) -> Dict[str, Any]:
        """
        Verify migration results

        Returns:
            Verification summary
        """
        try:
            logger.info("🔍 Verifying migration...")

            # Count remaining document chapters
            remaining_document = self.chapters_collection.count_documents(
                {"content_mode": "document"}
            )

            # Count inline chapters
            inline_count = self.chapters_collection.count_documents(
                {"content_mode": "inline"}
            )

            # Count migrated chapters
            migrated_count = self.chapters_collection.count_documents(
                {"migrated_from_document": True}
            )

            logger.info("📊 Verification Results:")
            logger.info(f"   Remaining 'document' mode: {remaining_document}")
            logger.info(f"   Total 'inline' mode: {inline_count}")
            logger.info(f"   Migrated chapters: {migrated_count}")

            if remaining_document == 0:
                logger.info("✅ All document chapters migrated successfully!")
            else:
                logger.warning(
                    f"⚠️ Still {remaining_document} document chapters remaining"
                )

            return {
                "remaining_document": remaining_document,
                "inline_count": inline_count,
                "migrated_count": migrated_count,
            }

        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            raise


async def main():
    """Main migration entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate document mode chapters to inline mode"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without making changes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Process chapters in batches (default: 100)",
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify migration results only"
    )

    args = parser.parse_args()

    try:
        # Initialize database
        from src.database.db_manager import DBManager

        db_manager = DBManager()
        db = db_manager.db

        logger.info("🗄️ Connected to database")

        # Create migration instance
        migration = DocumentToInlineMigration(db)

        # Run migration or verification
        if args.verify:
            await migration.verify_migration()
        else:
            result = await migration.migrate_all(
                dry_run=args.dry_run, batch_size=args.batch_size
            )

            # Verify after migration
            if not args.dry_run and result["migrated"] > 0:
                logger.info("")
                await migration.verify_migration()

    except Exception as e:
        logger.error(f"❌ Migration script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
