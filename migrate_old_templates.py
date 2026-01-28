"""
Migrate old templates to new Learning System schema
- Add UUID `id` field
- Add `topic_id` (from `category`)
- Add `category_id` (extract from topic_id pattern)
- Add `is_published: true`
"""

import uuid
from src.database.db_manager import DBManager


def migrate_old_templates():
    """Migrate templates without UUID to new schema"""
    db_manager = DBManager()
    db = db_manager.db

    # Find all templates without `id` field (old schema)
    old_templates = list(db.code_templates.find({"id": {"$exists": False}}))

    print(f"Found {len(old_templates)} old templates to migrate")
    print("=" * 80)

    migrated = 0
    for template in old_templates:
        # Generate UUID STRING (not Binary)
        template_id = str(uuid.uuid4())

        # Extract category_id from category/topic_id pattern
        # e.g., "python-lop10-gioi-thieu" -> "python"
        category = template.get("category", "")
        category_id = category.split("-")[0] if category else "python"

        # Prepare update - ensure id is STRING
        update_fields = {
            "id": template_id,  # STRING UUID, not Binary
            "topic_id": category,  # Old `category` becomes `topic_id`
            "category_id": category_id,
            "is_published": template.get("is_active", True),
        }

        # Update document
        result = db.code_templates.update_one(
            {"_id": template["_id"]}, {"$set": update_fields}
        )

        if result.modified_count > 0:
            migrated += 1
            print(f"✅ {template.get('title', 'Untitled')}")
            print(f"   ID: {template_id}")
            print(f"   Topic: {category} -> {category_id}")
            print()

    print("=" * 80)
    print(f"✅ MIGRATION COMPLETE")
    print(f"Total migrated: {migrated}/{len(old_templates)}")


if __name__ == "__main__":
    migrate_old_templates()
