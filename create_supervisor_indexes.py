"""
Create MongoDB indexes for Phase 5 Supervisor System.

Collections:
- supervisors
- affiliates         (new index: supervisor_id)
- supervisor_commissions
- supervisor_withdrawals

Run:
    python create_supervisor_indexes.py
Or on production via docker copy pattern:
    docker cp create_supervisor_indexes.py ai-chatbot-rag:/app/
    docker exec ai-chatbot-rag python3 /app/create_supervisor_indexes.py
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from pymongo import MongoClient, ASCENDING, DESCENDING

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB_NAME", "ai_service_db")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


def create_indexes():
    print(f"📦 Connected to MongoDB: {DB_NAME}")

    # ------------------------------------------------------------------
    # supervisors collection
    # ------------------------------------------------------------------
    print("\n🔧 Collection: supervisors")

    idx = db["supervisors"].create_index([("code", ASCENDING)], unique=True)
    print(f"  ✅ {idx}")

    idx = db["supervisors"].create_index([("user_id", ASCENDING)])
    print(f"  ✅ {idx}")

    # ------------------------------------------------------------------
    # affiliates collection — new supervisor_id index
    # ------------------------------------------------------------------
    print("\n🔧 Collection: affiliates (new index)")

    idx = db["affiliates"].create_index([("supervisor_id", ASCENDING)])
    print(f"  ✅ {idx}")

    # ------------------------------------------------------------------
    # supervisor_commissions collection
    # ------------------------------------------------------------------
    print("\n🔧 Collection: supervisor_commissions")

    idx = db["supervisor_commissions"].create_index(
        [("supervisor_id", ASCENDING), ("created_at", DESCENDING)]
    )
    print(f"  ✅ {idx}")

    idx = db["supervisor_commissions"].create_index([("affiliate_id", ASCENDING)])
    print(f"  ✅ {idx}")

    idx = db["supervisor_commissions"].create_index([("user_id", ASCENDING)])
    print(f"  ✅ {idx}")

    idx = db["supervisor_commissions"].create_index(
        [("supervisor_id", ASCENDING), ("status", ASCENDING)]
    )
    print(f"  ✅ {idx}")

    # ------------------------------------------------------------------
    # supervisor_withdrawals collection
    # ------------------------------------------------------------------
    print("\n🔧 Collection: supervisor_withdrawals")

    idx = db["supervisor_withdrawals"].create_index(
        [("supervisor_id", ASCENDING), ("status", ASCENDING)]
    )
    print(f"  ✅ {idx}")

    idx = db["supervisor_withdrawals"].create_index(
        [("status", ASCENDING), ("created_at", DESCENDING)]
    )
    print(f"  ✅ {idx}")

    print("\n✨ All supervisor indexes created successfully!")


if __name__ == "__main__":
    create_indexes()
