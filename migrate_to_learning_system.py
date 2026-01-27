"""
Migration Script: Old Category System → New Learning System
Migrates code_template_categories to new learning_categories + learning_topics structure
"""

import asyncio
from datetime import datetime
from src.database.db_manager import DBManager

# Default categories for code learning
DEFAULT_CATEGORIES = [
    {
        "id": "python",
        "name": "Python",
        "description": "Python programming language - beginner to advanced",
        "icon": "🐍",
        "order": 1,
    },
    {
        "id": "javascript",
        "name": "JavaScript",
        "description": "JavaScript for web development and Node.js",
        "icon": "⚡",
        "order": 2,
    },
    {
        "id": "html-css",
        "name": "HTML/CSS",
        "description": "Web design with HTML5 and CSS3",
        "icon": "🎨",
        "order": 3,
    },
    {
        "id": "sql",
        "name": "SQL",
        "description": "Database querying and management",
        "icon": "🗃️",
        "order": 4,
    },
    {
        "id": "software-architecture",
        "name": "Software Architecture",
        "description": "Design patterns, system design, best practices",
        "icon": "🏗️",
        "order": 5,
    },
    {
        "id": "ai",
        "name": "AI & Machine Learning",
        "description": "Artificial Intelligence and ML fundamentals",
        "icon": "🤖",
        "order": 6,
    },
]


async def migrate_categories_and_topics():
    """
    Migrate old code_template_categories to new structure

    Old structure:
      code_template_categories: { id, name, language, description, order }

    New structure:
      learning_categories: { id, name, description, icon, order }
      learning_topics: { id, category_id, name, description, level, grade, order }
    """
    print("=" * 80)
    print("MIGRATION: code_template_categories → learning_categories + learning_topics")
    print("=" * 80)

    db_manager = DBManager()
    db = db_manager.db

    # Step 1: Create new learning_categories collection
    print("\n📦 Step 1: Creating learning categories...")

    now = datetime.utcnow()
    created_categories = 0

    for category in DEFAULT_CATEGORIES:
        # Check if already exists
        existing = db.learning_categories.find_one({"id": category["id"]})
        if existing:
            print(f"  ⏭️  Category '{category['id']}' already exists, skipping...")
            continue

        # Create category
        category_doc = {
            **category,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        db.learning_categories.insert_one(category_doc)
        print(f"  ✅ Created category: {category['name']} ({category['id']})")
        created_categories += 1

    print(f"\n  📊 Created {created_categories} categories")

    # Step 2: Migrate old code_template_categories to learning_topics
    print("\n📦 Step 2: Migrating code_template_categories to learning_topics...")

    old_categories = list(db.code_template_categories.find())
    print(f"  Found {len(old_categories)} old categories to migrate")

    created_topics = 0
    skipped_topics = 0

    # Language mapping to new category IDs
    LANGUAGE_MAP = {
        "python": "python",
        "javascript": "javascript",
        "html": "html-css",
        "css": "html-css",
        "sql": "sql",
    }

    for old_cat in old_categories:
        # Map language to category_id
        language = old_cat.get("language", "").lower()
        category_id = LANGUAGE_MAP.get(language, "python")  # Default to python

        # Generate topic ID from old category ID
        topic_id = old_cat.get("id", f"topic-{old_cat['_id']}")

        # Check if already migrated
        existing = db.learning_topics.find_one({"id": topic_id})
        if existing:
            print(f"  ⏭️  Topic '{topic_id}' already exists, skipping...")
            skipped_topics += 1
            continue

        # Determine level and grade from category name
        name = old_cat.get("name", "")
        level = "student"
        grade = None

        if "lớp 10" in name.lower() or "grade 10" in name.lower():
            grade = "10"
        elif "lớp 11" in name.lower() or "grade 11" in name.lower():
            grade = "11"
        elif "lớp 12" in name.lower() or "grade 12" in name.lower():
            grade = "12"
        elif (
            "thực tế" in name.lower()
            or "professional" in name.lower()
            or "advanced" in name.lower()
        ):
            level = "professional"

        # Create topic
        topic_doc = {
            "id": topic_id,
            "category_id": category_id,
            "name": name,
            "description": old_cat.get("description"),
            "level": level,
            "grade": grade,
            "order": old_cat.get("order", created_topics + 1),
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        db.learning_topics.insert_one(topic_doc)
        print(f"  ✅ Migrated: {name} → {category_id} (level: {level}, grade: {grade})")
        created_topics += 1

    print(f"\n  📊 Migrated {created_topics} topics, skipped {skipped_topics} existing")

    # Step 3: Add topic_id to existing code_templates
    print("\n📦 Step 3: Updating existing code_templates with topic_id...")

    # For each template with old category, map to new topic
    templates = list(db.code_templates.find({"category": {"$exists": True}}))
    print(f"  Found {len(templates)} templates to update")

    updated_templates = 0
    for template in templates:
        old_category = template.get("category")
        if not old_category:
            continue

        # Find topic by ID (assuming old category ID matches topic ID)
        topic_id = old_category

        # Check if topic exists, if not use default topic
        topic = db.learning_topics.find_one({"id": topic_id})
        if not topic:
            # Fallback: try to find any topic with same language
            language = template.get("programming_language", "").lower()
            category_id = LANGUAGE_MAP.get(language, "python")
            topic = db.learning_topics.find_one(
                {"category_id": category_id}, sort=[("order", 1)]
            )

        if topic:
            db.code_templates.update_one(
                {"_id": template["_id"]},
                {
                    "$set": {
                        "topic_id": topic["id"],
                        "category_id": topic["category_id"],
                        "source_type": "wordai_team",
                        "is_published": True,
                        "is_featured": False,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            updated_templates += 1

    print(f"  ✅ Updated {updated_templates} templates")

    # Step 4: Add topic_id to existing code_exercises
    print("\n📦 Step 4: Updating existing code_exercises with topic_id...")

    exercises = list(db.code_exercises.find({"category": {"$exists": True}}))
    print(f"  Found {len(exercises)} exercises to update")

    updated_exercises = 0
    for exercise in exercises:
        old_category = exercise.get("category")
        if not old_category:
            continue

        # Find topic
        topic_id = old_category
        topic = db.learning_topics.find_one({"id": topic_id})
        if not topic:
            language = exercise.get("programming_language", "").lower()
            category_id = LANGUAGE_MAP.get(language, "python")
            topic = db.learning_topics.find_one(
                {"category_id": category_id}, sort=[("order", 1)]
            )

        if topic:
            db.code_exercises.update_one(
                {"_id": exercise["_id"]},
                {
                    "$set": {
                        "topic_id": topic["id"],
                        "category_id": topic["category_id"],
                        "source_type": "wordai_team",
                        "grading_type": "test_cases",  # Default to test cases
                        "is_published": True,
                        "is_featured": False,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            updated_exercises += 1

    print(f"  ✅ Updated {updated_exercises} exercises")

    # Summary
    print("\n" + "=" * 80)
    print("✅ MIGRATION COMPLETE!")
    print("=" * 80)
    print(f"📊 Summary:")
    print(f"  - Categories created: {created_categories}")
    print(f"  - Topics migrated: {created_topics}")
    print(f"  - Templates updated: {updated_templates}")
    print(f"  - Exercises updated: {updated_exercises}")
    print()
    print("🔍 Next steps:")
    print("  1. Run create_learning_system_indexes.py to create database indexes")
    print("  2. Deploy to production")
    print("  3. Test API endpoints")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(migrate_categories_and_topics())
