#!/usr/bin/env python3
"""
Check user points balance in database
"""
import sys

sys.path.insert(0, "/app/src")

from src.config.database import get_database

db = get_database()

# Find user by checking recent book purchases or use a known user_id
# Let's check the structure of user_points collection first

print("🔍 Checking user_points collection structure...")
print("=" * 80)

# Get a sample document
sample = db.user_points.find_one()
if sample:
    print("📦 Sample user_points document:")
    print(f"   Keys: {list(sample.keys())}")
    print()
    for key, value in sample.items():
        print(f"   • {key}: {value} (type: {type(value).__name__})")
else:
    print("⚠️ No documents in user_points collection!")

print("\n" + "=" * 80)
print("\n🔍 Looking for users with ~294 points...")

# Search for user with 294 points in various fields
for field_name in ["balance", "points", "total_points", "available_points"]:
    user = db.user_points.find_one({field_name: {"$gte": 290, "$lte": 300}})
    if user:
        print(f"\n✅ Found user with {field_name} ≈ 294:")
        print(f"   user_id: {user.get('user_id')}")
        print(f"   All fields:")
        for key, value in user.items():
            if key != "_id":
                print(f"      {key}: {value}")
        break

print("\n" + "=" * 80)

# Also check firebase_users collection for balance
print("\n🔍 Checking firebase_users collection...")
firebase_user = db.firebase_users.find_one({"balance": {"$gte": 290, "$lte": 300}})
if firebase_user:
    print(f"\n✅ Found in firebase_users:")
    print(f"   uid: {firebase_user.get('uid')}")
    print(f"   email: {firebase_user.get('email')}")
    print(f"   balance: {firebase_user.get('balance')}")
    print(f"   points: {firebase_user.get('points')}")
else:
    print("   No user with ~294 points in firebase_users")

print("\n" + "=" * 80)
print("\n💡 CONCLUSION:")
print("The purchase endpoint checks: db.user_points.find_one({'user_id': user_id})")
print("Then gets: user_points_doc.get('balance', 0)")
print("\nIf user has 294 points showing in frontend but 0 in user_points.balance,")
print("the points might be in a different collection or field.")
