#!/usr/bin/env python3
"""
Debug: Check if purchase API actually deducted from correct collection
"""
import sys

sys.path.insert(0, "/app/src")

from src.config.database import get_database

db = get_database()

# Target user
uid = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

print("=" * 100)
print(f"🔍 CHECKING PURCHASE TRANSACTION FOR USER")
print("=" * 100)

# Check user_subscriptions (CORRECT SOURCE)
subscription = db.user_subscriptions.find_one({"user_id": uid})
print("\n✅ user_subscriptions (MAIN - CORRECT):")
if subscription:
    print(f"   points_remaining: {subscription.get('points_remaining')}")
    print(f"   points_used: {subscription.get('points_used')}")
    print(f"   points_total: {subscription.get('points_total')}")
    print(f"   earnings_points: {subscription.get('earnings_points')}")
else:
    print("   ❌ Not found")

# Check firebase_users (OLD - DEPRECATED)
firebase_user = db.firebase_users.find_one({"uid": uid})
print("\n📦 firebase_users (OLD - DEPRECATED):")
if firebase_user:
    print(f"   points_remaining: {firebase_user.get('points_remaining')}")
    print(f"   earnings_points: {firebase_user.get('earnings_points')}")
else:
    print("   ❌ Not found")

# Check recent purchases
purchases = list(
    db.book_purchases.find({"user_id": uid}).sort("purchased_at", -1).limit(5)
)
print(f"\n📚 Recent book purchases: {len(purchases)}")
for i, purchase in enumerate(purchases, 1):
    print(f"\n   Purchase {i}:")
    print(f"   - Book ID: {purchase.get('book_id')}")
    print(f"   - Type: {purchase.get('purchase_type')}")
    print(f"   - Points spent: {purchase.get('points_spent')}")
    print(f"   - Time: {purchase.get('purchased_at')}")

print("\n" + "=" * 100)
print("🔍 DIAGNOSIS:")
print("=" * 100)

if subscription:
    if (
        subscription.get("points_remaining") == 293
    ):  # If user had 294 and bought 1-point book
        print("✅ CORRECT: Points deducted from user_subscriptions (294 → 293)")
        print("✅ Backend is working correctly!")
        print("⚠️  Frontend might be showing cached data or reading from wrong field")
    elif subscription.get("points_remaining") == 294:
        print("❌ WRONG: Points NOT deducted! Still showing 294")
        print("❌ Purchase transaction may have failed")
    else:
        print(f"ℹ️  Current balance: {subscription.get('points_remaining')}")
        print(
            f"ℹ️  Last purchase: {purchases[0].get('points_spent') if purchases else 'N/A'} points"
        )

if firebase_user:
    if firebase_user.get("points_remaining") == 9:
        print("\n⚠️  WARNING: firebase_users shows 9 points (10 → 9)")
        print(
            "⚠️  Frontend might be reading from firebase_users instead of user_subscriptions!"
        )
        print("⚠️  This is the OLD deprecated collection!")

print("\n")
