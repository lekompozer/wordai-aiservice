"""
Fix Binary UUID to String UUID in templates
MongoDB UUID() function creates Binary, we need plain strings
"""

from src.database.db_manager import DBManager
from bson import Binary
import uuid as uuid_lib


def fix_binary_uuid_to_string():
    """Convert all Binary UUID ids to string UUIDs"""
    db_manager = DBManager()
    db = db_manager.db

    # Find all templates with id field
    all_templates = list(db.code_templates.find({"id": {"$exists": True}}))

    print(f"Found {len(all_templates)} templates with id field")
    print("=" * 80)

    fixed = 0
    already_string = 0

    for template in all_templates:
        template_id = template["id"]

        # Check if it's valid UUID string (36 chars with hyphens)
        is_valid_uuid_string = (
            isinstance(template_id, str)
            and len(template_id) == 36
            and template_id.count("-") == 4
        )

        if is_valid_uuid_string:
            already_string += 1
            continue

        # Need to fix - try multiple approaches
        uuid_str = None
        try:
            if isinstance(template_id, Binary):
                # BSON Binary type
                uuid_str = str(uuid_lib.UUID(bytes=bytes(template_id)))
            elif isinstance(template_id, bytes):
                # Pure bytes
                uuid_str = str(uuid_lib.UUID(bytes=template_id))
            elif isinstance(template_id, str):
                # Binary data stored as string - convert via raw bytes
                # Get raw bytes from string
                try:
                    # Template id might be corrupted UTF-8
                    uuid_bytes = template["_id"].binary  # Get from _id if possible
                except:
                    # Last resort: try to interpret as bytes
                    uuid_bytes = template_id.encode("raw_unicode_escape")[:16]

                uuid_str = str(uuid_lib.UUID(bytes=uuid_bytes))

            if uuid_str:
                # Update to proper UUID string
                result = db.code_templates.update_one(
                    {"_id": template["_id"]}, {"$set": {"id": uuid_str}}
                )

                if result.modified_count > 0:
                    fixed += 1
                    print(f"✅ {template.get('title', 'Untitled')}")
                    print(f"   Fixed → {uuid_str}")
                    print()
            else:
                print(f"⚠️ Could not fix: {template.get('title')}")

        except Exception as e:
            # Generate new UUID as last resort
            new_uuid = str(uuid_lib.uuid4())
            result = db.code_templates.update_one(
                {"_id": template["_id"]}, {"$set": {"id": new_uuid}}
            )
            if result.modified_count > 0:
                fixed += 1
                print(f"🔧 Generated new UUID: {template.get('title')}")
                print(f"   New → {new_uuid}")
                print()

    print("=" * 80)
    print(f"✅ FIX COMPLETE")
    print(f"Fixed: {fixed}")
    print(f"Already valid UUID string: {already_string}")
    print(f"Total: {len(all_templates)}")


if __name__ == "__main__":
    fix_binary_uuid_to_string()
