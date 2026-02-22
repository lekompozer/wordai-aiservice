"""
Create MongoDB indexes for Phase 5 Supervisor System.

Collections:
- supervisors
- affiliates         (new index: supervisor_id)
- supervisor_commissions
- supervisor_withdrawals

Run on production:
    docker cp create_supervisor_indexes.py ai-chatbot-rag:/app/
    docker exec ai-chatbot-rag python3 /app/create_supervisor_indexes.py
"""

from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db

print("Creating indexes for Supervisor system (Phase 5)...")

# supervisors collection
db.supervisors.create_index([("code", 1)], unique=True)
db.supervisors.create_index([("user_id", 1)])
print("✅ supervisors indexes created")

# affiliates — new supervisor_id index
db.affiliates.create_index([("supervisor_id", 1)])
print("✅ affiliates.supervisor_id index created")

# supervisor_commissions
db.supervisor_commissions.create_index([("supervisor_id", 1), ("created_at", -1)])
db.supervisor_commissions.create_index([("affiliate_id", 1)])
db.supervisor_commissions.create_index([("user_id", 1)])
db.supervisor_commissions.create_index([("supervisor_id", 1), ("status", 1)])
print("✅ supervisor_commissions indexes created")

# supervisor_withdrawals
db.supervisor_withdrawals.create_index([("supervisor_id", 1), ("status", 1)])
db.supervisor_withdrawals.create_index([("status", 1), ("created_at", -1)])
print("✅ supervisor_withdrawals indexes created")

print("\n✨ All supervisor indexes created successfully!")

