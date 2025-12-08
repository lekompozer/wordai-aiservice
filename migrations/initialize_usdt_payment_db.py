#!/usr/bin/env python3
"""
Initialize USDT Payment Database Collections and Indexes

Creates collections:
- usdt_payments: Payment records
- usdt_pending_transactions: Awaiting confirmation
- usdt_wallet_addresses: User wallet management

Creates indexes for optimal performance
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from pymongo import MongoClient, ASCENDING, DESCENDING
from src.utils.logger import setup_logger
from src import config

logger = setup_logger()


def initialize_usdt_payment_db():
    """Initialize USDT payment database collections and indexes"""

    try:
        logger.info("=" * 80)
        logger.info("🚀 Initializing USDT BEP20 Payment Database")
        logger.info("=" * 80)
        logger.info("")

        # Connect to MongoDB
        mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        db_name = getattr(config, "MONGODB_NAME", "wordai_db")

        logger.info(f"📡 Connecting to MongoDB: {db_name}")
        client = MongoClient(mongo_uri)
        db = client[db_name]

        # Test connection
        db.command("ping")
        logger.info(f"✅ Connected to database: {db_name}\n")

        # ====================================================================
        # COLLECTION 1: usdt_payments
        # ====================================================================
        logger.info("📦 Creating collection: usdt_payments")

        usdt_payments = db.usdt_payments

        # Create indexes
        logger.info("   Creating indexes...")

        # Primary indexes
        usdt_payments.create_index("payment_id", unique=True, name="idx_payment_id")
        usdt_payments.create_index(
            "order_invoice_number", unique=True, name="idx_order_invoice"
        )
        usdt_payments.create_index("user_id", name="idx_user_id")
        usdt_payments.create_index(
            "transaction_hash", sparse=True, name="idx_transaction_hash"
        )

        # Status and type indexes
        usdt_payments.create_index("status", name="idx_status")
        usdt_payments.create_index("payment_type", name="idx_payment_type")

        # Compound indexes for queries
        usdt_payments.create_index(
            [("user_id", ASCENDING), ("status", ASCENDING)], name="idx_user_status"
        )
        usdt_payments.create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_user_created",
        )
        usdt_payments.create_index(
            [("payment_type", ASCENDING), ("status", ASCENDING)], name="idx_type_status"
        )

        # Time-based indexes
        usdt_payments.create_index("created_at", name="idx_created_at")
        usdt_payments.create_index("confirmed_at", sparse=True, name="idx_confirmed_at")
        usdt_payments.create_index("expires_at", sparse=True, name="idx_expires_at")

        # Admin indexes
        usdt_payments.create_index("manually_processed", name="idx_manually_processed")

        logger.info("   ✅ 13 indexes created for usdt_payments")
        logger.info("")

        # ====================================================================
        # COLLECTION 2: usdt_pending_transactions
        # ====================================================================
        logger.info("📦 Creating collection: usdt_pending_transactions")

        usdt_pending = db.usdt_pending_transactions

        # Create indexes
        logger.info("   Creating indexes...")

        # Primary indexes
        usdt_pending.create_index("payment_id", name="idx_payment_id")
        usdt_pending.create_index(
            "transaction_hash", unique=True, name="idx_transaction_hash"
        )
        usdt_pending.create_index("user_id", name="idx_user_id")

        # Status and confirmation tracking
        usdt_pending.create_index("status", name="idx_status")
        usdt_pending.create_index(
            [("status", ASCENDING), ("last_checked_at", ASCENDING)],
            name="idx_status_checked",
        )

        # Compound for background job queries
        usdt_pending.create_index(
            [("status", ASCENDING), ("confirmation_count", ASCENDING)],
            name="idx_status_confirmations",
        )

        # Time-based indexes
        usdt_pending.create_index("first_seen_at", name="idx_first_seen")
        usdt_pending.create_index("last_checked_at", name="idx_last_checked")

        logger.info("   ✅ 8 indexes created for usdt_pending_transactions")
        logger.info("")

        # ====================================================================
        # COLLECTION 3: usdt_wallet_addresses
        # ====================================================================
        logger.info("📦 Creating collection: usdt_wallet_addresses")

        usdt_wallets = db.usdt_wallet_addresses

        # Create indexes
        logger.info("   Creating indexes...")

        # Primary indexes
        usdt_wallets.create_index("user_id", name="idx_user_id")
        usdt_wallets.create_index("wallet_address", name="idx_wallet_address")

        # Unique compound index: one wallet per user
        usdt_wallets.create_index(
            [("user_id", ASCENDING), ("wallet_address", ASCENDING)],
            unique=True,
            name="idx_user_wallet_unique",
        )

        # Verification status
        usdt_wallets.create_index("is_verified", name="idx_verified")

        # Time-based indexes
        usdt_wallets.create_index("last_used_at", name="idx_last_used")

        logger.info("   ✅ 5 indexes created for usdt_wallet_addresses")
        logger.info("")

        # ====================================================================
        # SUMMARY
        # ====================================================================
        logger.info("=" * 80)
        logger.info("🎉 USDT Payment Database Initialized Successfully!")
        logger.info("=" * 80)
        logger.info("")
        logger.info("📊 Summary:")
        logger.info("   • usdt_payments: 13 indexes")
        logger.info("   • usdt_pending_transactions: 8 indexes")
        logger.info("   • usdt_wallet_addresses: 5 indexes")
        logger.info("   • Total: 26 indexes")
        logger.info("")
        logger.info("✅ Ready to process USDT BEP20 payments!")
        logger.info("")

        # Close connection
        client.close()

        return True

    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = initialize_usdt_payment_db()
    sys.exit(0 if success else 1)
