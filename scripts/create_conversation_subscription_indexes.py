"""
Create indexes for new collections introduced by Phase 1 + Phase 2
of the Conversation Learning subscription system.
"""

from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db

print("Creating indexes for conversation subscription system...")

# user_conversation_subscription
db.user_conversation_subscription.create_index([("user_id", 1)])
db.user_conversation_subscription.create_index(
    [("user_id", 1), ("is_active", 1), ("end_date", -1)]
)
print("✅ user_conversation_subscription indexes created")

# user_daily_submits (unique per user per date)
db.user_daily_submits.create_index([("user_id", 1), ("date", 1)], unique=True)
print("✅ user_daily_submits indexes created")

# affiliates (lookup by code)
db.affiliates.create_index([("code", 1)], unique=True, sparse=True)
db.affiliates.create_index([("user_id", 1)])
print("✅ affiliates indexes created")

# affiliate_commissions
db.affiliate_commissions.create_index([("affiliate_id", 1), ("created_at", -1)])
db.affiliate_commissions.create_index([("user_id", 1)])
db.affiliate_commissions.create_index([("subscription_id", 1)])
print("✅ affiliate_commissions indexes created")

print("\n✅ All indexes created successfully!")
