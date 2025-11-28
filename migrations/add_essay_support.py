#!/usr/bin/env python3
"""
Migration Script: Add Essay and Mixed-format Question Support
=====================================================

This script migrates the database to support Essay and Mixed-format questions
while maintaining backward compatibility with existing MCQ tests.

Changes:
1. Add `question_type: "mcq"` (default) to all existing questions
2. Add `max_points: 1` to questions without it
3. Add `grading_status: "auto_graded"` to all existing test submissions
4. Create `grading_queue` collection with indexes
5. Verify migration with sample queries

Usage:
    python migrations/add_essay_support.py [--dry-run] [--rollback]

Options:
    --dry-run    Show what would be changed without making changes
    --rollback   Revert the migration (remove new fields)

Safety:
- Creates backup before migration
- Validates data integrity after migration
- Provides rollback capability
"""

import sys
import os
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import config.config as config
except ImportError:
    print("❌ Error: Cannot import config. Make sure you're in the project root.")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EssayMigration:
    """Handles migration to add essay question support"""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        self.db_name = getattr(config, "MONGODB_NAME", "wordai_db")
        self.client = None
        self.db = None

    def connect(self):
        """Connect to MongoDB"""
        try:
            logger.info(f"Connecting to MongoDB: {self.db_name}")
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            # Test connection
            self.db.command("ping")
            logger.info("✅ Connected to MongoDB successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            return False

    def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    def create_backup(self):
        """Create backup of collections before migration"""
        if self.dry_run:
            logger.info("🔍 DRY RUN: Would create backup")
            return True

        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_prefix = f"backup_{timestamp}_"

            collections_to_backup = ["online_tests", "test_submissions"]

            for collection_name in collections_to_backup:
                backup_name = f"{backup_prefix}{collection_name}"
                logger.info(f"Creating backup: {backup_name}")

                # Copy collection
                pipeline = [{"$out": backup_name}]
                self.db[collection_name].aggregate(pipeline)

                logger.info(f"✅ Backed up {collection_name} -> {backup_name}")

            logger.info(f"✅ All backups created with prefix: {backup_prefix}")
            return True

        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return False

    def migrate_online_tests(self):
        """Add essay support fields to online_tests collection"""
        collection = self.db["online_tests"]

        # Count tests that need migration
        tests_needing_migration = collection.count_documents(
            {"questions.question_type": {"$exists": False}}
        )

        logger.info(f"📊 Found {tests_needing_migration} tests needing migration")

        if tests_needing_migration == 0:
            logger.info("✅ No tests need migration")
            return True

        if self.dry_run:
            logger.info(f"🔍 DRY RUN: Would update {tests_needing_migration} tests")
            return True

        try:
            # Update all questions without question_type to set it as "mcq"
            # Also add max_points: 1 if not present
            result = collection.update_many(
                {"questions": {"$exists": True}},
                [
                    {
                        "$set": {
                            "questions": {
                                "$map": {
                                    "input": "$questions",
                                    "as": "q",
                                    "in": {
                                        "$mergeObjects": [
                                            "$$q",
                                            {
                                                "question_type": {
                                                    "$ifNull": [
                                                        "$$q.question_type",
                                                        "mcq",
                                                    ]
                                                },
                                                "max_points": {
                                                    "$ifNull": ["$$q.max_points", 1]
                                                },
                                            },
                                        ]
                                    },
                                }
                            }
                        }
                    }
                ],
            )

            logger.info(
                f"✅ Updated {result.modified_count} tests with default question_type and max_points"
            )

            # Verify migration
            remaining = collection.count_documents(
                {"questions": {"$elemMatch": {"question_type": {"$exists": False}}}}
            )

            if remaining > 0:
                logger.warning(
                    f"⚠️ {remaining} tests still have questions without question_type"
                )
                return False

            logger.info("✅ All tests migrated successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to migrate online_tests: {e}")
            return False

    def migrate_test_submissions(self):
        """Add grading_status to test_submissions collection"""
        collection = self.db["test_submissions"]

        # Count submissions that need migration
        submissions_needing_migration = collection.count_documents(
            {"grading_status": {"$exists": False}}
        )

        logger.info(
            f"📊 Found {submissions_needing_migration} submissions needing migration"
        )

        if submissions_needing_migration == 0:
            logger.info("✅ No submissions need migration")
            return True

        if self.dry_run:
            logger.info(
                f"🔍 DRY RUN: Would update {submissions_needing_migration} submissions"
            )
            return True

        try:
            # Add grading_status: "auto_graded" to all existing submissions
            result = collection.update_many(
                {"grading_status": {"$exists": False}},
                {
                    "$set": {
                        "grading_status": "auto_graded",
                        "mcq_score": "$score",  # Preserve original score
                        "mcq_correct_count": "$correct_answers",
                    }
                },
            )

            logger.info(
                f"✅ Updated {result.modified_count} submissions with grading_status"
            )

            # Verify migration
            remaining = collection.count_documents(
                {"grading_status": {"$exists": False}}
            )

            if remaining > 0:
                logger.warning(
                    f"⚠️ {remaining} submissions still without grading_status"
                )
                return False

            logger.info("✅ All submissions migrated successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to migrate test_submissions: {e}")
            return False

    def create_grading_queue_collection(self):
        """Create grading_queue collection with indexes"""
        if self.dry_run:
            logger.info(
                "🔍 DRY RUN: Would create grading_queue collection with indexes"
            )
            return True

        try:
            # Check if collection exists
            if "grading_queue" in self.db.list_collection_names():
                logger.info("⚠️ grading_queue collection already exists")
            else:
                # Create collection (implicitly created on first insert)
                logger.info("Creating grading_queue collection")

            collection = self.db["grading_queue"]

            # Create indexes
            logger.info("Creating indexes on grading_queue...")

            # Index on submission_id (unique)
            collection.create_index([("submission_id", ASCENDING)], unique=True)
            logger.info("✅ Created unique index on submission_id")

            # Index on test_id (for filtering by test)
            collection.create_index([("test_id", ASCENDING)])
            logger.info("✅ Created index on test_id")

            # Compound index on status + submitted_at (for queue ordering)
            collection.create_index(
                [("status", ASCENDING), ("submitted_at", DESCENDING)]
            )
            logger.info("✅ Created compound index on (status, submitted_at)")

            # Index on assigned_to (for grader workload)
            collection.create_index([("assigned_to", ASCENDING)])
            logger.info("✅ Created index on assigned_to")

            # Compound index on status + priority (for prioritized grading)
            collection.create_index([("status", ASCENDING), ("priority", DESCENDING)])
            logger.info("✅ Created compound index on (status, priority)")

            logger.info("✅ grading_queue collection and indexes created successfully")
            return True

        except DuplicateKeyError as e:
            logger.warning(f"⚠️ Index already exists: {e}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create grading_queue: {e}")
            return False

    def verify_migration(self):
        """Verify migration was successful"""
        logger.info("🔍 Verifying migration...")

        try:
            # Check online_tests
            tests_collection = self.db["online_tests"]
            sample_test = tests_collection.find_one({"questions": {"$exists": True}})

            if sample_test and "questions" in sample_test:
                first_question = sample_test["questions"][0]
                if "question_type" in first_question and "max_points" in first_question:
                    logger.info(
                        "✅ online_tests: Sample test has question_type and max_points"
                    )
                else:
                    logger.error("❌ online_tests: Sample test missing new fields")
                    return False

            # Check test_submissions
            submissions_collection = self.db["test_submissions"]
            sample_submission = submissions_collection.find_one()

            if sample_submission:
                if "grading_status" in sample_submission:
                    logger.info(
                        "✅ test_submissions: Sample submission has grading_status"
                    )
                else:
                    logger.error(
                        "❌ test_submissions: Sample submission missing grading_status"
                    )
                    return False

            # Check grading_queue
            if "grading_queue" in self.db.list_collection_names():
                logger.info("✅ grading_queue collection exists")

                # Verify indexes
                grading_queue = self.db["grading_queue"]
                indexes = list(grading_queue.list_indexes())
                index_names = [idx["name"] for idx in indexes]

                expected_indexes = [
                    "_id_",  # Default index
                    "submission_id_1",
                    "test_id_1",
                    "status_1_submitted_at_-1",
                    "assigned_to_1",
                    "status_1_priority_-1",
                ]

                for expected in expected_indexes:
                    if expected in index_names:
                        logger.info(f"✅ Index exists: {expected}")
                    else:
                        logger.warning(f"⚠️ Missing index: {expected}")
            else:
                logger.error("❌ grading_queue collection not found")
                return False

            logger.info("✅ Migration verification complete")
            return True

        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return False

    def rollback(self):
        """Rollback migration by removing new fields"""
        if self.dry_run:
            logger.info("🔍 DRY RUN: Would rollback migration")
            return True

        logger.info("⚠️ Starting rollback...")

        try:
            # Remove new fields from online_tests
            tests_collection = self.db["online_tests"]
            result1 = tests_collection.update_many(
                {},
                [
                    {
                        "$set": {
                            "questions": {
                                "$map": {
                                    "input": "$questions",
                                    "as": "q",
                                    "in": {
                                        "$arrayToObject": {
                                            "$filter": {
                                                "input": {"$objectToArray": "$$q"},
                                                "as": "field",
                                                "cond": {
                                                    "$not": {
                                                        "$in": [
                                                            "$$field.k",
                                                            [
                                                                "question_type",
                                                                "max_points",
                                                                "grading_rubric",
                                                            ],
                                                        ]
                                                    }
                                                },
                                            }
                                        }
                                    },
                                }
                            }
                        }
                    }
                ],
            )
            logger.info(f"✅ Rolled back {result1.modified_count} tests")

            # Remove new fields from test_submissions
            submissions_collection = self.db["test_submissions"]
            result2 = submissions_collection.update_many(
                {},
                {
                    "$unset": {
                        "grading_status": "",
                        "essay_grades": "",
                        "mcq_score": "",
                        "mcq_correct_count": "",
                    }
                },
            )
            logger.info(f"✅ Rolled back {result2.modified_count} submissions")

            # Drop grading_queue collection
            if "grading_queue" in self.db.list_collection_names():
                self.db["grading_queue"].drop()
                logger.info("✅ Dropped grading_queue collection")

            logger.info("✅ Rollback complete")
            return True

        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            return False

    def run(self, rollback=False):
        """Run the migration"""
        if not self.connect():
            return False

        try:
            if rollback:
                logger.info("=" * 60)
                logger.info("ROLLING BACK ESSAY SUPPORT MIGRATION")
                logger.info("=" * 60)
                return self.rollback()

            logger.info("=" * 60)
            logger.info("STARTING ESSAY SUPPORT MIGRATION")
            logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
            logger.info("=" * 60)

            # Step 1: Create backup
            logger.info("\n📦 Step 1: Creating backup...")
            if not self.create_backup():
                logger.error("❌ Backup failed. Aborting migration.")
                return False

            # Step 2: Migrate online_tests
            logger.info("\n📝 Step 2: Migrating online_tests collection...")
            if not self.migrate_online_tests():
                logger.error("❌ online_tests migration failed. Aborting.")
                return False

            # Step 3: Migrate test_submissions
            logger.info("\n📋 Step 3: Migrating test_submissions collection...")
            if not self.migrate_test_submissions():
                logger.error("❌ test_submissions migration failed. Aborting.")
                return False

            # Step 4: Create grading_queue
            logger.info("\n🔄 Step 4: Creating grading_queue collection...")
            if not self.create_grading_queue_collection():
                logger.error("❌ grading_queue creation failed. Aborting.")
                return False

            # Step 5: Verify migration
            if not self.dry_run:
                logger.info("\n✅ Step 5: Verifying migration...")
                if not self.verify_migration():
                    logger.error("❌ Verification failed.")
                    return False

            logger.info("\n" + "=" * 60)
            logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)

            if not self.dry_run:
                logger.info("\n📊 Summary:")
                logger.info(
                    "- Existing MCQ tests now have question_type='mcq' and max_points=1"
                )
                logger.info(
                    "- Existing submissions now have grading_status='auto_graded'"
                )
                logger.info("- grading_queue collection created with indexes")
                logger.info("\n⚠️ Next steps:")
                logger.info("1. Deploy new backend code with essay support")
                logger.info("2. Test creating essay questions")
                logger.info("3. Test submitting and grading essay answers")

            return True

        finally:
            self.disconnect()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate database to support Essay and Mixed-format questions"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Revert the migration (remove new fields)",
    )

    args = parser.parse_args()

    if args.rollback and args.dry_run:
        print("❌ Error: Cannot use --rollback with --dry-run")
        sys.exit(1)

    migration = EssayMigration(dry_run=args.dry_run)
    success = migration.run(rollback=args.rollback)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
