"""
Migration Script: Add User Plans and Subscription System

This script:
1. Creates new collections: user_subscriptions, payments, points_transactions
2. Creates indexes for performance
3. Adds subscription fields to existing users collection
4. Creates free subscription for all existing users
5. Initializes points balance for all users

Run with: python scripts/migrate_add_user_plans.py [--dry-run] [--production]
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING, IndexModel
from bson import ObjectId
import argparse
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Free plan configuration
FREE_PLAN_CONFIG = {
    "plan": "free",
    "duration": None,
    "price": 0,
    "points_total": 0,
    "points_used": 0,
    "points_remaining": 0,
    "storage_limit_mb": 50,
    "upload_files_limit": 10,
    "documents_limit": 10,
    "secret_files_limit": 1,
    "daily_chat_limit": 15,
}


def get_mongodb_client(use_production: bool = False):
    """Get MongoDB client"""
    if use_production:
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            raise ValueError("MONGODB_URI environment variable not set")
    else:
        mongodb_uri = "mongodb://admin:WordAIMongoRootPassword@localhost:27017"

    logger.info(f"Connecting to MongoDB...")
    client = MongoClient(mongodb_uri)

    # Test connection
    client.admin.command("ping")
    logger.info("✅ Connected to MongoDB successfully")

    return client


def create_collections_and_indexes(db, dry_run: bool = False):
    """Create collections and indexes"""
    logger.info("\n📦 Creating collections and indexes...")

    collections_to_create = ["user_subscriptions", "payments", "points_transactions"]

    for collection_name in collections_to_create:
        if collection_name not in db.list_collection_names():
            if not dry_run:
                db.create_collection(collection_name)
            logger.info(f"  ✅ Created collection: {collection_name}")
        else:
            logger.info(f"  ⏭️  Collection already exists: {collection_name}")

    # Create indexes for user_subscriptions
    logger.info("\n🔍 Creating indexes for user_subscriptions...")
    subscriptions = db["user_subscriptions"]

    subscription_indexes = [
        IndexModel([("user_id", ASCENDING)], unique=True, name="idx_user_id_unique"),
        IndexModel([("expires_at", ASCENDING)], name="idx_expires_at"),
        IndexModel([("is_active", ASCENDING)], name="idx_is_active"),
        IndexModel(
            [("plan", ASCENDING), ("is_active", ASCENDING)], name="idx_plan_active"
        ),
        IndexModel([("created_at", DESCENDING)], name="idx_created_at"),
        IndexModel([("payment_id", ASCENDING)], sparse=True, name="idx_payment_id"),
    ]

    if not dry_run:
        subscriptions.create_indexes(subscription_indexes)
    logger.info(
        f"  ✅ Created {len(subscription_indexes)} indexes for user_subscriptions"
    )

    # Create indexes for payments
    logger.info("\n🔍 Creating indexes for payments...")
    payments = db["payments"]

    payment_indexes = [
        IndexModel(
            [("order_invoice_number", ASCENDING)],
            unique=True,
            name="idx_order_invoice_unique",
        ),
        IndexModel(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_user_created",
        ),
        IndexModel([("status", ASCENDING)], name="idx_status"),
        IndexModel(
            [("sepay_transaction_id", ASCENDING)], sparse=True, name="idx_sepay_txn"
        ),
        IndexModel([("created_at", DESCENDING)], name="idx_created_at"),
    ]

    if not dry_run:
        payments.create_indexes(payment_indexes)
    logger.info(f"  ✅ Created {len(payment_indexes)} indexes for payments")

    # Create indexes for points_transactions
    logger.info("\n🔍 Creating indexes for points_transactions...")
    transactions = db["points_transactions"]

    transaction_indexes = [
        IndexModel(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_user_created",
        ),
        IndexModel([("subscription_id", ASCENDING)], name="idx_subscription_id"),
        IndexModel(
            [("service", ASCENDING), ("created_at", DESCENDING)],
            name="idx_service_created",
        ),
        IndexModel([("transaction_type", ASCENDING)], name="idx_type"),
        IndexModel([("created_at", DESCENDING)], name="idx_created_at"),
    ]

    if not dry_run:
        transactions.create_indexes(transaction_indexes)
    logger.info(
        f"  ✅ Created {len(transaction_indexes)} indexes for points_transactions"
    )


def add_subscription_fields_to_users(db, dry_run: bool = False):
    """Add subscription-related fields to existing users collection"""
    logger.info("\n👥 Adding subscription fields to users collection...")

    users = db["users"]

    # Count users without subscription fields
    users_to_update = users.count_documents(
        {
            "$or": [
                {"current_plan": {"$exists": False}},
                {"subscription_id": {"$exists": False}},
            ]
        }
    )

    if users_to_update == 0:
        logger.info("  ⏭️  All users already have subscription fields")
        return 0

    logger.info(f"  📊 Found {users_to_update} users to update")

    if not dry_run:
        result = users.update_many(
            {
                "$or": [
                    {"current_plan": {"$exists": False}},
                    {"subscription_id": {"$exists": False}},
                ]
            },
            {
                "$set": {
                    "current_plan": "free",
                    "subscription_id": None,
                    "subscription_expires_at": None,
                    "points_remaining": 0,
                    "storage_limit_mb": FREE_PLAN_CONFIG["storage_limit_mb"],
                    "plan_updated_at": datetime.utcnow(),
                }
            },
        )
        logger.info(
            f"  ✅ Updated {result.modified_count} users with subscription fields"
        )
        return result.modified_count
    else:
        logger.info(f"  🔍 [DRY RUN] Would update {users_to_update} users")
        return users_to_update


def create_free_subscriptions(db, dry_run: bool = False):
    """Create free subscriptions for all existing users"""
    logger.info("\n🎁 Creating free subscriptions for existing users...")

    users = db["users"]
    subscriptions = db["user_subscriptions"]

    # Get all users who don't have a subscription yet
    all_users = list(users.find({"uid": {"$exists": True}}))

    logger.info(f"  📊 Found {len(all_users)} total users")

    created_count = 0
    skipped_count = 0

    for user in all_users:
        user_id = user["uid"]

        # Check if subscription already exists
        existing = subscriptions.find_one({"user_id": user_id})
        if existing:
            skipped_count += 1
            continue

        # Create free subscription
        subscription_doc = {
            "user_id": user_id,
            "plan": FREE_PLAN_CONFIG["plan"],
            "duration": FREE_PLAN_CONFIG["duration"],
            "price": FREE_PLAN_CONFIG["price"],
            "points_total": FREE_PLAN_CONFIG["points_total"],
            "points_used": FREE_PLAN_CONFIG["points_used"],
            "points_remaining": FREE_PLAN_CONFIG["points_remaining"],
            "started_at": datetime.utcnow(),
            "expires_at": None,  # Free never expires
            "is_active": True,
            "auto_renew": False,
            "payment_id": None,
            "payment_method": None,
            "storage_used_mb": 0.0,
            "storage_limit_mb": FREE_PLAN_CONFIG["storage_limit_mb"],
            "upload_files_count": 0,
            "upload_files_limit": FREE_PLAN_CONFIG["upload_files_limit"],
            "documents_count": 0,
            "documents_limit": FREE_PLAN_CONFIG["documents_limit"],
            "secret_files_count": 0,
            "secret_files_limit": FREE_PLAN_CONFIG["secret_files_limit"],
            "daily_chat_count": 0,
            "daily_chat_limit": FREE_PLAN_CONFIG["daily_chat_limit"],
            "last_chat_reset": datetime.utcnow(),
            "manually_activated": False,
            "activated_by_admin": None,
            "notes": "Initial free subscription created by migration script",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        if not dry_run:
            result = subscriptions.insert_one(subscription_doc)
            subscription_id = result.inserted_id

            # Update user document with subscription reference
            users.update_one(
                {"uid": user_id},
                {
                    "$set": {
                        "subscription_id": str(subscription_id),
                        "current_plan": "free",
                        "points_remaining": 0,
                        "storage_limit_mb": FREE_PLAN_CONFIG["storage_limit_mb"],
                    }
                },
            )

            created_count += 1

            if created_count % 10 == 0:
                logger.info(f"  ⏳ Created {created_count} subscriptions...")
        else:
            created_count += 1

    logger.info(f"  ✅ Created {created_count} free subscriptions")
    logger.info(f"  ⏭️  Skipped {skipped_count} users (already have subscription)")

    return created_count


def verify_migration(db):
    """Verify the migration was successful"""
    logger.info("\n🔍 Verifying migration...")

    users = db["users"]
    subscriptions = db["user_subscriptions"]

    # Check collections exist
    collections = db.list_collection_names()
    required_collections = ["user_subscriptions", "payments", "points_transactions"]

    for collection in required_collections:
        if collection in collections:
            logger.info(f"  ✅ Collection exists: {collection}")
        else:
            logger.error(f"  ❌ Collection missing: {collection}")
            return False

    # Check users have subscription fields
    users_without_plan = users.count_documents({"current_plan": {"$exists": False}})
    total_users = users.count_documents({})

    logger.info(f"  📊 Total users: {total_users}")
    logger.info(
        f"  📊 Users with subscription fields: {total_users - users_without_plan}"
    )

    if users_without_plan > 0:
        logger.warning(
            f"  ⚠️  {users_without_plan} users still missing subscription fields"
        )

    # Check subscriptions created
    total_subscriptions = subscriptions.count_documents({})
    free_subscriptions = subscriptions.count_documents({"plan": "free"})

    logger.info(f"  📊 Total subscriptions: {total_subscriptions}")
    logger.info(f"  📊 Free subscriptions: {free_subscriptions}")

    # Check indexes
    subscription_indexes = subscriptions.list_indexes()
    index_count = len(list(subscription_indexes))
    logger.info(f"  📊 Subscription indexes: {index_count}")

    logger.info("\n✅ Migration verification complete!")
    return True


def rollback_migration(db, dry_run: bool = False):
    """Rollback the migration (use with caution!)"""
    logger.warning("\n⚠️  ROLLBACK: This will delete all subscription data!")

    if not dry_run:
        confirmation = input(
            "Are you sure you want to rollback? Type 'YES' to confirm: "
        )
        if confirmation != "YES":
            logger.info("Rollback cancelled")
            return

    logger.info("Rolling back migration...")

    # Drop collections
    collections_to_drop = ["user_subscriptions", "payments", "points_transactions"]

    for collection_name in collections_to_drop:
        if not dry_run:
            db.drop_collection(collection_name)
        logger.info(f"  ✅ Dropped collection: {collection_name}")

    # Remove subscription fields from users
    users = db["users"]

    if not dry_run:
        result = users.update_many(
            {},
            {
                "$unset": {
                    "current_plan": "",
                    "subscription_id": "",
                    "subscription_expires_at": "",
                    "points_remaining": "",
                    "plan_updated_at": "",
                }
            },
        )
        logger.info(
            f"  ✅ Removed subscription fields from {result.modified_count} users"
        )
    else:
        logger.info("  🔍 [DRY RUN] Would remove subscription fields from users")

    logger.info("\n✅ Rollback complete!")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate database to add user plans and subscriptions"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without making changes"
    )
    parser.add_argument(
        "--production", action="store_true", help="Run on production database"
    )
    parser.add_argument(
        "--rollback", action="store_true", help="Rollback the migration (DANGEROUS!)"
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made\n")

    if args.production:
        logger.warning(
            "⚠️  PRODUCTION MODE - Changes will be made to production database!\n"
        )
        if not args.dry_run:
            confirmation = input("Are you sure? Type 'PRODUCTION' to confirm: ")
            if confirmation != "PRODUCTION":
                logger.info("Migration cancelled")
                return

    try:
        # Connect to MongoDB
        client = get_mongodb_client(use_production=args.production)
        db = client[os.getenv("MONGODB_DATABASE", "ai_service_db")]

        logger.info(f"📚 Using database: {db.name}\n")

        if args.rollback:
            rollback_migration(db, dry_run=args.dry_run)
        else:
            # Run migration steps
            logger.info("🚀 Starting migration...\n")

            # Step 1: Create collections and indexes
            create_collections_and_indexes(db, dry_run=args.dry_run)

            # Step 2: Add subscription fields to users
            users_updated = add_subscription_fields_to_users(db, dry_run=args.dry_run)

            # Step 3: Create free subscriptions
            subscriptions_created = create_free_subscriptions(db, dry_run=args.dry_run)

            # Step 4: Verify migration
            if not args.dry_run:
                verify_migration(db)

            # Summary
            logger.info("\n" + "=" * 50)
            logger.info("📊 MIGRATION SUMMARY")
            logger.info("=" * 50)
            logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
            logger.info(f"Database: {db.name}")
            logger.info(f"Users updated: {users_updated}")
            logger.info(f"Subscriptions created: {subscriptions_created}")
            logger.info("=" * 50)

            if args.dry_run:
                logger.info(
                    "\n✅ Dry run complete! Run without --dry-run to apply changes."
                )
            else:
                logger.info("\n✅ Migration complete!")

        client.close()

    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
