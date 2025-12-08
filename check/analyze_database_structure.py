#!/usr/bin/env python3
"""
Analyze current database structure for user points and subscriptions
"""
import sys

sys.path.insert(0, "/app/src")

from src.config.database import get_database

db = get_database()

print("=" * 100)
print("📊 DATABASE STRUCTURE ANALYSIS - USER POINTS & SUBSCRIPTIONS")
print("=" * 100)

# Check all collections
collections = {
    "firebase_users": db.firebase_users,
    "user_subscriptions": db.user_subscriptions,
    "user_points": db.user_points,
    "users": db.users,
}

for name, collection in collections.items():
    count = collection.count_documents({})
    print(f"\n📦 Collection: {name}")
    print(f"   Documents: {count}")

    if count > 0:
        sample = collection.find_one()
        print(f"   Fields:")
        for key in sample.keys():
            if key != "_id":
                value = sample[key]
                print(
                    f"      • {key}: {type(value).__name__} = {value if not isinstance(value, (dict, list)) else '...'}"
                )

print("\n" + "=" * 100)
print("\n🔍 SPECIFIC USER CHECK: tienhoi.lh@gmail.com")
print("=" * 100)

# Check user in all collections
email = "tienhoi.lh@gmail.com"
uid = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

# firebase_users
fu = db.firebase_users.find_one({"email": email})
if fu:
    print(f"\n✅ firebase_users:")
    print(f"   points_remaining: {fu.get('points_remaining')}")
    print(f"   earnings_points: {fu.get('earnings_points')}")
    print(f"   bonus_points: {fu.get('bonus_points')}")

# user_subscriptions
us = db.user_subscriptions.find_one({"user_id": uid})
if us:
    print(f"\n✅ user_subscriptions:")
    print(f"   plan: {us.get('plan')}")
    print(f"   points_remaining: {us.get('points_remaining')}")
    print(f"   points_total: {us.get('points_total')}")
    print(f"   is_active: {us.get('is_active')}")

# user_points
up = db.user_points.find_one({"user_id": uid})
if up:
    print(f"\n✅ user_points:")
    print(f"   balance: {up.get('balance')}")
else:
    print(f"\n❌ user_points: Not found")

print("\n" + "=" * 100)
print("\n💡 RECOMMENDATION:")
print("=" * 100)
print(
    """
CURRENT PROBLEM:
- firebase_users: Has points_remaining (used by books purchase)
- user_subscriptions: Has points_remaining (used by subscription service)
- user_points: Empty collection (not used)

SOLUTION OPTIONS:

Option 1: USE firebase_users AS SINGLE SOURCE OF TRUTH (RECOMMENDED ✅)
  Pros:
    - Already has uid, email, profile data
    - Natural place for user-specific data
    - Simple schema
  Cons:
    - Need to migrate user_subscriptions data
    - Need to update subscription_service

Option 2: USE user_subscriptions AS SINGLE SOURCE
  Pros:
    - Already used by subscription_service
    - Has plan info
  Cons:
    - Redundant with firebase_users
    - More complex queries

RECOMMENDED APPROACH:
1. Keep firebase_users as main collection
2. Add subscription fields to firebase_users:
   - plan: str (free, basic, premium)
   - subscription_expires_at: datetime
   - points_remaining: int (spending balance)
   - earnings_points: int (revenue from sales - withdrawable)
   - bonus_points: int (promotional points)
3. Deprecate user_subscriptions collection
4. Update all APIs to use firebase_users only
"""
)
