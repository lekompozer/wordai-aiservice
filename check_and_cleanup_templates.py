"""
Check and cleanup Python templates
- Check which templates have no code
- Check which templates have invalid topic_id
- Delete templates without code or invalid topic_id
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database.db_manager import DBManager

# Valid Python topic IDs (from current topics)
VALID_TOPIC_IDS = [
    # Lớp 10
    "python-lop10-gioi-thieu",
    "python-lop10-bien-kieu-du-lieu",
    "python-lop10-nhap-xuat",
    "python-lop10-dieu-kien",
    "python-lop10-vong-lap",
    "python-lop10-list-string",
    "python-lop10-ham",
    "python-lop10-bai-tap",
    # Lớp 11
    "python-lop11-co-ban",
    "python-lop11-chuoi-list",
    "python-lop11-file",
    "python-lop11-ham-nang-cao",
    "python-lop11-bai-tap",
    # Lớp 12
    "python-lop12-oop",
    "python-lop12-du-lieu",
    "python-lop12-thu-vien",
    "python-lop12-du-an",
]

DRY_RUN = True  # Set to False to actually delete


def check_templates():
    """Check all Python templates"""
    print("=" * 80)
    print("CHECKING PYTHON TEMPLATES")
    print("=" * 80)

    if DRY_RUN:
        print("\n⚠️  DRY RUN MODE - No changes will be made")
        print("Set DRY_RUN = False to execute cleanup\n")

    db_manager = DBManager()
    db = db_manager.db

    # Get all Python templates
    templates = list(db.code_templates.find({"category_id": "python"}))

    print(f"\nTotal Python templates: {len(templates)}\n")

    # Statistics
    stats = {
        "total": len(templates),
        "has_code": 0,
        "no_code": 0,
        "invalid_topic": 0,
        "valid": 0,
        "to_delete": [],
    }

    # Group by topic
    by_topic = {}

    for template in templates:
        topic_id = template.get("topic_id", "")
        code = template.get("code", "")
        title = template.get("title", "")
        template_id = template.get("id", "")

        # Initialize topic stats
        if topic_id not in by_topic:
            by_topic[topic_id] = {
                "total": 0,
                "has_code": 0,
                "no_code": 0,
                "templates": [],
            }

        by_topic[topic_id]["total"] += 1
        by_topic[topic_id]["templates"].append(
            {"id": template_id, "title": title, "has_code": bool(code and code.strip())}
        )

        # Check if has code
        has_code = bool(code and code.strip())
        if has_code:
            stats["has_code"] += 1
            by_topic[topic_id]["has_code"] += 1
        else:
            stats["no_code"] += 1
            by_topic[topic_id]["no_code"] += 1

        # Check if topic is valid
        is_valid_topic = topic_id in VALID_TOPIC_IDS

        if not is_valid_topic:
            stats["invalid_topic"] += 1

        # Mark for deletion if:
        # 1. No code OR
        # 2. Invalid topic_id
        if not has_code or not is_valid_topic:
            stats["to_delete"].append(
                {
                    "id": template_id,
                    "title": title,
                    "topic_id": topic_id,
                    "reason": "no_code" if not has_code else "invalid_topic",
                }
            )
        else:
            stats["valid"] += 1

    # Print summary by topic
    print("=" * 80)
    print("TEMPLATES BY TOPIC")
    print("=" * 80)

    for topic_id in sorted(by_topic.keys()):
        topic_data = by_topic[topic_id]
        is_valid = topic_id in VALID_TOPIC_IDS
        status = "✅" if is_valid else "❌"

        print(f"\n{status} {topic_id}:")
        print(f"   Total: {topic_data['total']}")
        print(f"   Has code: {topic_data['has_code']}")
        print(f"   No code: {topic_data['no_code']}")

        if topic_data["no_code"] > 0:
            print(f"   Templates without code:")
            for t in topic_data["templates"]:
                if not t["has_code"]:
                    print(f"      - {t['title']}")

    # Print deletion list
    print("\n" + "=" * 80)
    print("TEMPLATES TO DELETE")
    print("=" * 80)

    if stats["to_delete"]:
        for item in stats["to_delete"]:
            print(f"❌ [{item['reason']}] {item['topic_id']} - {item['title']}")
    else:
        print("✅ No templates to delete")

    # Print overall summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total templates: {stats['total']}")
    print(f"Valid templates (with code + valid topic): {stats['valid']}")
    print(f"Templates without code: {stats['no_code']}")
    print(f"Templates with invalid topic_id: {stats['invalid_topic']}")
    print(f"Templates to delete: {len(stats['to_delete'])}")
    print("=" * 80)

    # Delete if not dry run
    if not DRY_RUN and stats["to_delete"]:
        print("\n🗑️  Deleting templates...")
        ids_to_delete = [item["id"] for item in stats["to_delete"]]
        result = db.code_templates.delete_many({"id": {"$in": ids_to_delete}})
        print(f"✅ Deleted {result.deleted_count} templates")
    elif DRY_RUN and stats["to_delete"]:
        print(
            "\n⚠️  DRY RUN - Would delete {} templates".format(len(stats["to_delete"]))
        )
        print("Set DRY_RUN = False and run again to execute deletion")

    return stats


if __name__ == "__main__":
    try:
        check_templates()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
