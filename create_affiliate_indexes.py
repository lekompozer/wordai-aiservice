"""
Create indexes for affiliate withdrawal collection (Phase 3).
"""
from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db

print("Creating indexes for affiliate withdrawal system...")

db.affiliate_withdrawals.create_index([("affiliate_id", 1), ("status", 1)])
db.affiliate_withdrawals.create_index([("status", 1), ("created_at", -1)])
db.affiliate_withdrawals.create_index([("user_id", 1)])
print("✅ affiliate_withdrawals indexes created")

print("\n✅ All indexes created successfully!")
