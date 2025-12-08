#!/usr/bin/env python3
"""
Migration: Unify points system to single 'points' field

PHASE 1: Add 'points' field and sync with 'points_remaining'
- Copy points_remaining → points for all users
- Keep both fields during transition
- Update code to read from 'points' but write to both

PHASE 2 (Future): Deprecate 'points_remaining'
- Remove all references to points_remaining in code
- Drop field from database

This script implements PHASE 1 only.
"""
import sys

sys.path.insert(0, "/app/src")

from src.config.database import get_database
from datetime import datetime, timezone


def migrate_points_field():
    """
    Add 'points' field to firebase_users collection and sync with points_remaining
    """
    db = get_database()

    print("=" * 80)
    print("🔄 MIGRATION: Unify Points System")
    print("=" * 80)

    # Get all users
    users = list(db.firebase_users.find({}))
    total_users = len(users)

    print(f"\n📊 Found {total_users} users in firebase_users collection")

    if total_users == 0:
        print("⚠️  No users found. Nothing to migrate.")
        return

    # Statistics
    migrated = 0
    skipped = 0
    errors = 0

    print("\n🔄 Starting migration...\n")

    for user in users:
        uid = user.get("uid", "unknown")
        email = user.get("email", "no-email")

        try:
            # Get current points_remaining value
            points_remaining = user.get("points_remaining", 0)
            current_points = user.get("points", None)

            # Skip if 'points' already exists and matches
            if current_points is not None:
                if current_points == points_remaining:
                    skipped += 1
                    print(
                        f"⏭️  {uid[:20]}... - Already synced (points={current_points})"
                    )
                    continue
                else:
                    print(
                        f"⚠️  {uid[:20]}... - Mismatch! points_remaining={points_remaining}, points={current_points}"
                    )

            # Add 'points' field with same value as 'points_remaining'
            result = db.firebase_users.update_one(
                {"uid": uid},
                {
                    "$set": {
                        "points": points_remaining,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            if result.modified_count > 0:
                migrated += 1
                print(
                    f"✅ {uid[:20]}... ({email[:30]}...) - Migrated: points={points_remaining}"
                )
            else:
                errors += 1
                print(f"❌ {uid[:20]}... - Failed to update")

        except Exception as e:
            errors += 1
            print(f"❌ {uid[:20]}... - Error: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("📊 MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Total users:     {total_users}")
    print(f"✅ Migrated:      {migrated}")
    print(f"⏭️  Skipped:       {skipped}")
    print(f"❌ Errors:        {errors}")
    print("=" * 80)

    if errors == 0:
        print("\n✅ Migration completed successfully!")
        print("\n📝 Next steps:")
        print("1. Update code to use 'points' instead of 'points_remaining'")
        print("2. Test all points-related features")
        print("3. In future, deprecate 'points_remaining' field")
    else:
        print(f"\n⚠️  Migration completed with {errors} errors. Please investigate.")

    return migrated, skipped, errors


if __name__ == "__main__":
    try:
        migrate_points_field()
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
