#!/usr/bin/env python3
"""
Check and sync Firebase user to MongoDB
"""
import sys

sys.path.insert(0, "/app/src")

from src.config.database import get_database
from datetime import datetime, timezone

db = get_database()

# User email to check
user_email = "tienhoi.lh@gmail.com"

print(f"🔍 Checking user: {user_email}")
print("=" * 80)

# Try to find user in firebase_users collection
user = db.firebase_users.find_one({"email": user_email})

if user:
    print("✅ User EXISTS in firebase_users collection:")
    print(f"   uid: {user.get('uid')}")
    print(f"   email: {user.get('email')}")
    print(f"   points_remaining: {user.get('points_remaining', 0)}")
    print(f"   points_total: {user.get('points_total', 0)}")
    print(f"   earnings_points: {user.get('earnings_points', 0)}")
    print(f"   bonus_points: {user.get('bonus_points', 0)}")
    print(f"   created_at: {user.get('created_at')}")

    # Check if user needs points
    if user.get("points_remaining", 0) == 0:
        print("\n⚠️ User has 0 points!")
        print("Would you like to add bonus points? (This script only checks)")
else:
    print("❌ User NOT FOUND in firebase_users collection!")
    print("\nPossible reasons:")
    print("1. User logged in via Firebase Auth but never called any API")
    print("2. User record not created during registration")
    print("\nTo fix this, we need the Firebase UID from authentication.")

    # Try to find in users collection (legacy)
    legacy_user = db.users.find_one({"email": user_email})
    if legacy_user:
        print("\n✅ Found in legacy 'users' collection:")
        print(f"   user_id: {legacy_user.get('user_id')}")
        print(f"   email: {legacy_user.get('email')}")
        print("\nNeed to create firebase_users record for this user.")

print("\n" + "=" * 80)

# Check all firebase_users to see the structure
print("\n📊 Firebase Users Collection Stats:")
total_users = db.firebase_users.count_documents({})
print(f"   Total users: {total_users}")

# Sample user structure
sample = db.firebase_users.find_one()
if sample:
    print(f"\n📦 Sample user structure:")
    for key in sample.keys():
        if key != "_id":
            print(f"   • {key}: {type(sample[key]).__name__}")

print("\n" + "=" * 80)
print("\n💡 SOLUTION:")
print("If user not found, we need to:")
print("1. Get Firebase UID from frontend (user is logged in)")
print("2. Create firebase_users record with:")
print(
    """
   {
     "uid": "firebase_uid_from_auth",
     "email": "tienhoi.lh@gmail.com",
     "points_remaining": 10,  // Bonus points
     "points_total": 10,
     "earnings_points": 0,
     "bonus_points": 10,
     "created_at": datetime.now(timezone.utc)
   }
"""
)
print("3. User can then purchase books")
