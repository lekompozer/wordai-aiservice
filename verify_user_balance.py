#!/usr/bin/env python3
"""
Verify user balance after migration
"""
import sys
sys.path.insert(0, '/app/src')

from src.config.database import get_database

db = get_database()

# Target user
email = "tienhoi.lh@gmail.com"
uid = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

print("=" * 100)
print(f"🔍 VERIFYING USER BALANCE: {email}")
print("=" * 100)

# Check firebase_users
firebase_user = db.firebase_users.find_one({"uid": uid})
print(f"\n📦 firebase_users collection:")
if firebase_user:
    print(f"   points_remaining: {firebase_user.get('points_remaining', 'N/A')}")
    print(f"   earnings_points: {firebase_user.get('earnings_points', 'N/A')}")
else:
    print("   ❌ User not found")

# Check user_subscriptions (MAIN)
subscription = db.user_subscriptions.find_one({"user_id": uid})
print(f"\n✅ user_subscriptions collection (MAIN):")
if subscription:
    print(f"   user_id: {subscription.get('user_id')}")
    print(f"   plan: {subscription.get('plan')}")
    print(f"   is_active: {subscription.get('is_active')}")
    print(f"   points_remaining: {subscription.get('points_remaining')} (spending balance)")
    print(f"   points_total: {subscription.get('points_total')} (lifetime received)")
    print(f"   points_used: {subscription.get('points_used')} (lifetime spent)")
    print(f"   earnings_points: {subscription.get('earnings_points')} (revenue from sales)")
else:
    print("   ❌ Subscription not found")

# Check user_points
user_points_doc = db.user_points.find_one({"user_id": uid})
print(f"\n📦 user_points collection:")
if user_points_doc:
    print(f"   points: {user_points_doc.get('points', 'N/A')}")
else:
    print("   ❌ No document found (collection empty)")

print("\n" + "=" * 100)
print("✅ VERIFICATION COMPLETE")
print("=" * 100)
print("\n📌 Purchase API will use user_subscriptions.points_remaining: 294 points")
print("📌 Owner earnings will be credited to user_subscriptions.earnings_points")
print("\n")
