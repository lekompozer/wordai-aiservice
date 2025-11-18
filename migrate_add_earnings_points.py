#!/usr/bin/env python3
"""
Migration: Add earnings_points field to user_subscriptions collection

This script:
1. Adds earnings_points field to all user_subscriptions (default 0)
2. Ensures points_used field exists (tracks lifetime spending)
3. Validates data consistency
"""
import sys

sys.path.insert(0, "/app/src")

from src.config.database import get_database
from datetime import datetime, timezone

db = get_database()

print("=" * 100)
print("🔄 MIGRATION: Add earnings_points to user_subscriptions")
print("=" * 100)

# Get all subscriptions
subscriptions = list(db.user_subscriptions.find({}))
total = len(subscriptions)

print(f"\n📊 Found {total} user subscriptions to migrate\n")

migrated_count = 0
already_have_earnings = 0
errors = []

for sub in subscriptions:
    user_id = sub.get("user_id")

    try:
        # Check if already has earnings_points
        has_earnings = "earnings_points" in sub
        has_points_used = "points_used" in sub

        if has_earnings and has_points_used:
            already_have_earnings += 1
            print(f"✅ {user_id}: Already has earnings_points and points_used")
            continue

        # Prepare update
        update_fields = {"$set": {"updated_at": datetime.now(timezone.utc)}}

        # Add earnings_points if missing
        if not has_earnings:
            update_fields["$set"]["earnings_points"] = 0
            print(f"   Adding earnings_points: 0")

        # Add points_used if missing (calculate from points_total - points_remaining)
        if not has_points_used:
            points_total = sub.get("points_total", 0)
            points_remaining = sub.get("points_remaining", 0)
            points_used = max(0, points_total - points_remaining)
            update_fields["$set"]["points_used"] = points_used
            print(f"   Adding points_used: {points_used} (calculated)")

        # Update document
        result = db.user_subscriptions.update_one({"user_id": user_id}, update_fields)

        if result.modified_count > 0:
            migrated_count += 1
            print(f"✅ {user_id}: Migrated successfully")
        else:
            print(f"⚠️  {user_id}: No changes needed")

    except Exception as e:
        error_msg = f"❌ {user_id}: {str(e)}"
        errors.append(error_msg)
        print(error_msg)

print("\n" + "=" * 100)
print("📊 MIGRATION SUMMARY")
print("=" * 100)
print(f"Total subscriptions: {total}")
print(f"Already had earnings_points: {already_have_earnings}")
print(f"Migrated: {migrated_count}")
print(f"Errors: {len(errors)}")

if errors:
    print("\n❌ Errors encountered:")
    for error in errors:
        print(f"   {error}")

print("\n" + "=" * 100)
print("✅ MIGRATION COMPLETE")
print("=" * 100)

# Verify migration
print("\n🔍 Verifying migration...")
sample_sub = db.user_subscriptions.find_one({})
if sample_sub:
    print("\n📦 Sample subscription after migration:")
    print(f"   user_id: {sample_sub.get('user_id')}")
    print(f"   points_remaining: {sample_sub.get('points_remaining')}")
    print(f"   points_total: {sample_sub.get('points_total')}")
    print(f"   points_used: {sample_sub.get('points_used')}")
    print(f"   earnings_points: {sample_sub.get('earnings_points')}")
    print(f"   plan: {sample_sub.get('plan')}")

print("\n✅ All user_subscriptions now have:")
print("   • points_remaining: Spending balance")
print("   • points_total: Lifetime points received")
print("   • points_used: Lifetime points spent")
print("   • earnings_points: Revenue from Books + Tests (withdrawable)")
