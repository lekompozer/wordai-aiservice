"""
Create indexes for book QR payment system

Collection: book_cash_orders
Indexes needed for efficient queries and TTL expiration
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv("development.env")


def create_book_payment_indexes():
    """Create MongoDB indexes for book_cash_orders collection"""

    # MongoDB connection
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "ai_service_db")

    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]

    print(f"🔗 Connected to MongoDB: {DATABASE_NAME}")
    print(f"📊 Creating indexes for book_cash_orders collection...")

    collection = db.book_cash_orders

    # 1. Unique index on order_id (primary key)
    print("\n1️⃣  Creating unique index on order_id...")
    collection.create_index(
        [("order_id", ASCENDING)], unique=True, name="idx_order_id_unique"
    )
    print("   ✅ idx_order_id_unique")

    # 2. Compound index on user_id + status (for listing user's orders)
    print("\n2️⃣  Creating compound index on user_id + status...")
    collection.create_index(
        [("user_id", ASCENDING), ("status", ASCENDING)], name="idx_user_status"
    )
    print("   ✅ idx_user_status")

    # 3. Compound index on user_id + created_at (for pagination)
    print("\n3️⃣  Creating compound index on user_id + created_at...")
    collection.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)], name="idx_user_created"
    )
    print("   ✅ idx_user_created")

    # 4. Compound index on book_id + status (for book sales stats)
    print("\n4️⃣  Creating compound index on book_id + status...")
    collection.create_index(
        [("book_id", ASCENDING), ("status", ASCENDING)], name="idx_book_status"
    )
    print("   ✅ idx_book_status")

    # 5. Index on transaction_id (for webhook matching)
    print("\n5️⃣  Creating index on transaction_id...")
    collection.create_index(
        [("transaction_id", ASCENDING)], sparse=True, name="idx_transaction_id"
    )
    print("   ✅ idx_transaction_id (sparse)")

    # 6. TTL index on expires_at (auto-delete expired orders after 7 days)
    print("\n6️⃣  Creating TTL index on expires_at...")
    collection.create_index(
        [("expires_at", ASCENDING)],
        expireAfterSeconds=604800,  # 7 days (60*60*24*7)
        name="idx_expires_at_ttl",
    )
    print("   ✅ idx_expires_at_ttl (expires after 7 days)")

    # 7. Index on created_at (for admin queries)
    print("\n7️⃣  Creating index on created_at...")
    collection.create_index([("created_at", DESCENDING)], name="idx_created_at")
    print("   ✅ idx_created_at")

    # 8. Index on status + created_at (for admin dashboard)
    print("\n8️⃣  Creating compound index on status + created_at...")
    collection.create_index(
        [("status", ASCENDING), ("created_at", DESCENDING)], name="idx_status_created"
    )
    print("   ✅ idx_status_created")

    # 9. Index on admin_bank_account.transfer_content (for webhook matching)
    print("\n9️⃣  Creating index on transfer_content...")
    collection.create_index(
        [("admin_bank_account.transfer_content", ASCENDING)],
        name="idx_transfer_content",
    )
    print("   ✅ idx_transfer_content")

    # List all indexes
    print("\n" + "=" * 70)
    print("📋 All indexes on book_cash_orders:")
    print("=" * 70)

    for index in collection.list_indexes():
        print(f"   • {index['name']}")
        if "key" in index:
            for field, direction in index["key"].items():
                dir_str = "ASC" if direction == 1 else "DESC"
                print(f"     - {field} ({dir_str})")
        if "unique" in index and index["unique"]:
            print("     - UNIQUE")
        if "sparse" in index and index["sparse"]:
            print("     - SPARSE")
        if "expireAfterSeconds" in index:
            print(f"     - TTL: {index['expireAfterSeconds']} seconds")
        print()

    print("=" * 70)
    print("✅ All indexes created successfully!")
    print("=" * 70)

    # Also update book_purchases collection to support cash orders
    print("\n📊 Adding index to book_purchases for order_id...")

    db.book_purchases.create_index(
        [("order_id", ASCENDING)], sparse=True, name="idx_order_id"
    )
    print("   ✅ idx_order_id (sparse) on book_purchases")

    # Close connection
    client.close()
    print("\n🔌 Closed MongoDB connection")


if __name__ == "__main__":
    create_book_payment_indexes()
