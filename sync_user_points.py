#!/usr/bin/env python3
"""
Sync points from user_subscriptions to users collection for a specific user
This script fixes the points mismatch issue where users have points in subscription but not in users collection
"""

import os
from pymongo import MongoClient
from datetime import datetime

# MongoDB connection
MONGO_URI = os.getenv(
    "MONGO_URI", "mongodb://admin:wordai@localhost:27017/wordai?authSource=admin"
)

client = MongoClient(MONGO_URI)
db = client["wordai"]

users_collection = db["users"]
subscriptions_collection = db["user_subscriptions"]


def sync_user_points(email: str = None, firebase_uid: str = None):
    """
    Sync points from subscription to users collection for a specific user

    Args:
        email: User email to sync (optional)
        firebase_uid: Firebase UID to sync (optional)

    At least one parameter must be provided.
    """
    if not email and not firebase_uid:
        print("❌ Error: Must provide either email or firebase_uid")
        return

    # Find user
    if email:
        user_doc = users_collection.find_one({"email": email})
        if not user_doc:
            print(f"❌ User not found with email: {email}")
            return
        firebase_uid = user_doc.get("firebase_uid")
    else:
        user_doc = users_collection.find_one({"firebase_uid": firebase_uid})
        if not user_doc:
            print(f"❌ User not found with firebase_uid: {firebase_uid}")
            return

    print(f"\n🔍 Found user:")
    print(f"   Email: {user_doc.get('email', 'N/A')}")
    print(f"   Firebase UID: {firebase_uid}")
    print(f"   Current points in users: {user_doc.get('points', 0)}")

    # Find subscription
    subscription_doc = subscriptions_collection.find_one({"user_id": firebase_uid})
    if not subscription_doc:
        print(f"❌ No subscription found for user: {firebase_uid}")
        return

    subscription_points = subscription_doc.get("points_remaining", 0)
    print(f"   Points in subscription: {subscription_points}")

    if subscription_points == user_doc.get("points", 0):
        print("\n✅ Points already in sync! No action needed.")
        return

    # Sync points
    result = users_collection.update_one(
        {"firebase_uid": firebase_uid},
        {
            "$set": {
                "points": subscription_points,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    if result.modified_count > 0:
        print(f"\n✅ SUCCESS! Points synced:")
        print(f"   Old: {user_doc.get('points', 0)} points")
        print(f"   New: {subscription_points} points")
        print(f"   User can now start tests!")
    else:
        print("\n❌ Failed to sync points")


def sync_all_users():
    """
    Sync points for ALL users in the system
    This is useful for migrating existing users
    """
    print("\n🔄 Syncing points for ALL users...")

    # Get all users
    users = users_collection.find()
    total_users = 0
    synced_users = 0
    already_synced = 0
    no_subscription = 0

    for user_doc in users:
        total_users += 1
        firebase_uid = user_doc.get("firebase_uid")
        email = user_doc.get("email", "N/A")
        current_points = user_doc.get("points", 0)

        # Find subscription
        subscription_doc = subscriptions_collection.find_one({"user_id": firebase_uid})
        if not subscription_doc:
            no_subscription += 1
            continue

        subscription_points = subscription_doc.get("points_remaining", 0)

        # Skip if already synced
        if subscription_points == current_points:
            already_synced += 1
            continue

        # Only sync if subscription has MORE points (don't overwrite if user already spent)
        if subscription_points > current_points:
            users_collection.update_one(
                {"firebase_uid": firebase_uid},
                {
                    "$set": {
                        "points": subscription_points,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            print(
                f"   ✅ Synced {email}: {current_points} → {subscription_points} points"
            )
            synced_users += 1

    print(f"\n📊 Sync Summary:")
    print(f"   Total users: {total_users}")
    print(f"   Synced: {synced_users}")
    print(f"   Already synced: {already_synced}")
    print(f"   No subscription: {no_subscription}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  1. Sync specific user by email:")
        print("     python sync_user_points.py lekompozer@gmail.com")
        print()
        print("  2. Sync specific user by firebase_uid:")
        print("     python sync_user_points.py --uid <firebase_uid>")
        print()
        print("  3. Sync ALL users (migration):")
        print("     python sync_user_points.py --all")
        sys.exit(1)

    if sys.argv[1] == "--all":
        sync_all_users()
    elif sys.argv[1] == "--uid" and len(sys.argv) > 2:
        sync_user_points(firebase_uid=sys.argv[2])
    else:
        sync_user_points(email=sys.argv[1])
