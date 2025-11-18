#!/usr/bin/env python3
"""
Fix: Drop legacy guide_id_unique index that causes duplicate key errors

The online_books collection has a legacy unique index on guide_id field (now null).
This causes errors when creating new books. Need to drop this index.
"""
import sys
sys.path.insert(0, '/app/src')

from src.config.database import get_database

db = get_database()

print("=" * 100)
print("🔧 FIX: Drop legacy guide_id_unique index")
print("=" * 100)

# Check existing indexes
print("\n📋 Current indexes on online_books collection:")
indexes = list(db.online_books.list_indexes())
for idx in indexes:
    print(f"   - {idx['name']}: {idx.get('key', {})}")

# Check if guide_id_unique exists
has_guide_id_index = any(idx['name'] == 'guide_id_unique' for idx in indexes)

if has_guide_id_index:
    print("\n⚠️  Found legacy guide_id_unique index")
    print("   This index causes duplicate key errors for guide_id: null")
    print("   Dropping index...")
    
    try:
        result = db.online_books.drop_index('guide_id_unique')
        print(f"✅ Successfully dropped guide_id_unique index")
    except Exception as e:
        print(f"❌ Failed to drop index: {e}")
        sys.exit(1)
else:
    print("\n✅ No guide_id_unique index found (already removed or never existed)")

# Verify indexes after drop
print("\n📋 Indexes after cleanup:")
indexes_after = list(db.online_books.list_indexes())
for idx in indexes_after:
    print(f"   - {idx['name']}: {idx.get('key', {})}")

print("\n" + "=" * 100)
print("✅ FIX COMPLETE")
print("=" * 100)
print("\n📌 Books can now be created without guide_id duplicate key errors")
print("\n")
