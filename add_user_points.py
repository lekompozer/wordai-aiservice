#!/usr/bin/env python3
"""
Add points to a specific user in both users and user_subscriptions collections
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime
from urllib.parse import urlparse

# MongoDB connection - will use MONGO_URI from environment
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("❌ Error: MONGO_URI environment variable not set")
    sys.exit(1)

client = MongoClient(MONGO_URI)

# Parse database name from URI
parsed_uri = urlparse(MONGO_URI)
db_name = parsed_uri.path.lstrip('/').split('?')[0]
if not db_name:
    print("❌ Error: No database name in MONGO_URI")
    sys.exit(1)

print(f"📊 Using database: {db_name}")
db = client[db_name]

users_collection = db["users"]
subscriptions_collection = db["user_subscriptions"]


def add_user_points(email: str, points_to_add: int):
    """
    Add points to a specific user in both users and user_subscriptions collections

    Args:
        email: User email
        points_to_add: Number of points to add
    """
    if points_to_add <= 0:
        print(f"❌ Error: Points must be positive number, got: {points_to_add}")
        return

    # Find user
    user_doc = users_collection.find_one({"email": email})
    if not user_doc:
        print(f"❌ User not found with email: {email}")
        return

    firebase_uid = user_doc.get("firebase_uid")
    current_points_users = user_doc.get("points", 0)

    print(f"\n🔍 Found user:")
    print(f"   Email: {email}")
    print(f"   Firebase UID: {firebase_uid}")
    print(f"   Current points in users: {current_points_users}")

    # Find subscription
    subscription_doc = subscriptions_collection.find_one({"user_id": firebase_uid})
    if not subscription_doc:
        print(f"❌ No subscription found for user: {firebase_uid}")
        print(f"   Creating new subscription with {points_to_add} points...")
        
        # Create new subscription
        subscriptions_collection.insert_one({
            "user_id": firebase_uid,
            "plan_type": "points",
            "points_remaining": points_to_add,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
        
        # Update users collection
        users_collection.update_one(
            {"firebase_uid": firebase_uid},
            {
                "$set": {
                    "points": points_to_add,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        
        print(f"\n✅ SUCCESS! Created subscription and added {points_to_add} points")
        print(f"   New total: {points_to_add} points")
        return

    current_points_subscription = subscription_doc.get("points_remaining", 0)
    print(f"   Current points in subscription: {current_points_subscription}")

    # Calculate new points
    new_points_users = current_points_users + points_to_add
    new_points_subscription = current_points_subscription + points_to_add

    # Update users collection
    result_users = users_collection.update_one(
        {"firebase_uid": firebase_uid},
        {
            "$inc": {"points": points_to_add},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )

    # Update subscription collection
    result_subscription = subscriptions_collection.update_one(
        {"user_id": firebase_uid},
        {
            "$inc": {"points_remaining": points_to_add},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )

    if result_users.modified_count > 0 and result_subscription.modified_count > 0:
        print(f"\n✅ SUCCESS! Added {points_to_add} points to user:")
        print(f"   Users collection:")
        print(f"      Old: {current_points_users} points")
        print(f"      New: {new_points_users} points")
        print(f"   Subscription collection:")
        print(f"      Old: {current_points_subscription} points")
        print(f"      New: {new_points_subscription} points")
    else:
        print("\n❌ Failed to add points")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python add_user_points.py <email> <points>")
        print("Example: python add_user_points.py user@example.com 1000")
        sys.exit(1)

    email = sys.argv[1]
    try:
        points = int(sys.argv[2])
    except ValueError:
        print(f"❌ Error: Points must be a number, got: {sys.argv[2]}")
        sys.exit(1)

    add_user_points(email, points)
