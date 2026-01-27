"""
Create Database Indexes for Learning System
Creates indexes for learning_categories, learning_topics, knowledge_articles, and updates code_templates/code_exercises indexes
"""

from src.database.db_manager import DBManager
from datetime import datetime


def create_learning_system_indexes():
    """
    Create all indexes for the learning system collections
    """
    print("=" * 80)
    print("CREATE INDEXES: Learning System")
    print("=" * 80)
    print(f"Started at: {datetime.utcnow().isoformat()}\n")

    db_manager = DBManager()
    db = db_manager.db

    # ==================== LEARNING CATEGORIES ====================
    print("📦 Creating indexes for learning_categories...")

    try:
        # Unique ID index
        db.learning_categories.create_index("id", unique=True, name="idx_category_id")
        print("  ✅ Created: idx_category_id (unique)")

        # Order + active index for sorting
        db.learning_categories.create_index(
            [("order", 1), ("is_active", 1)], name="idx_category_order_active"
        )
        print("  ✅ Created: idx_category_order_active")

    except Exception as e:
        print(f"  ⚠️  Error creating category indexes: {e}")

    # ==================== LEARNING TOPICS ====================
    print("\n📦 Creating indexes for learning_topics...")

    try:
        # Unique ID index
        db.learning_topics.create_index("id", unique=True, name="idx_topic_id")
        print("  ✅ Created: idx_topic_id (unique)")

        # Category + order index
        db.learning_topics.create_index(
            [("category_id", 1), ("order", 1)], name="idx_topic_category_order"
        )
        print("  ✅ Created: idx_topic_category_order")

        # Category + active index
        db.learning_topics.create_index(
            [("category_id", 1), ("is_active", 1)], name="idx_topic_category_active"
        )
        print("  ✅ Created: idx_topic_category_active")

        # Level + grade index (for filtering student topics)
        db.learning_topics.create_index(
            [("level", 1), ("grade", 1)], name="idx_topic_level_grade"
        )
        print("  ✅ Created: idx_topic_level_grade")

    except Exception as e:
        print(f"  ⚠️  Error creating topic indexes: {e}")

    # ==================== KNOWLEDGE ARTICLES ====================
    print("\n📦 Creating indexes for knowledge_articles...")

    try:
        # Unique ID index
        db.knowledge_articles.create_index("id", unique=True, name="idx_knowledge_id")
        print("  ✅ Created: idx_knowledge_id (unique)")

        # Topic + published index
        db.knowledge_articles.create_index(
            [("topic_id", 1), ("is_published", 1)], name="idx_knowledge_topic_published"
        )
        print("  ✅ Created: idx_knowledge_topic_published")

        # Category + published index
        db.knowledge_articles.create_index(
            [("category_id", 1), ("is_published", 1)],
            name="idx_knowledge_category_published",
        )
        print("  ✅ Created: idx_knowledge_category_published")

        # Source type + published index
        db.knowledge_articles.create_index(
            [("source_type", 1), ("is_published", 1)],
            name="idx_knowledge_source_published",
        )
        print("  ✅ Created: idx_knowledge_source_published")

        # Created by + created at (for user's articles)
        db.knowledge_articles.create_index(
            [("created_by", 1), ("created_at", -1)], name="idx_knowledge_user_created"
        )
        print("  ✅ Created: idx_knowledge_user_created")

        # Text search index
        db.knowledge_articles.create_index(
            [("title", "text"), ("content", "text"), ("tags", "text")],
            name="idx_knowledge_text_search",
            default_language="english",
        )
        print("  ✅ Created: idx_knowledge_text_search (text)")

    except Exception as e:
        print(f"  ⚠️  Error creating knowledge indexes: {e}")

    # ==================== UPDATE CODE_TEMPLATES ====================
    print("\n📦 Creating additional indexes for code_templates...")

    try:
        # Topic + published index
        db.code_templates.create_index(
            [("topic_id", 1), ("is_published", 1)], name="idx_template_topic_published"
        )
        print("  ✅ Created: idx_template_topic_published")

        # Source type + published index
        db.code_templates.create_index(
            [("source_type", 1), ("is_published", 1)],
            name="idx_template_source_published",
        )
        print("  ✅ Created: idx_template_source_published")

        # Created by + created at
        db.code_templates.create_index(
            [("created_by", 1), ("created_at", -1)], name="idx_template_user_created"
        )
        print("  ✅ Created: idx_template_user_created")

    except Exception as e:
        print(f"  ⚠️  Error creating template indexes: {e}")

    # ==================== UPDATE CODE_EXERCISES ====================
    print("\n📦 Creating additional indexes for code_exercises...")

    try:
        # Topic + published index
        db.code_exercises.create_index(
            [("topic_id", 1), ("is_published", 1)], name="idx_exercise_topic_published"
        )
        print("  ✅ Created: idx_exercise_topic_published")

        # Grading type + published index
        db.code_exercises.create_index(
            [("grading_type", 1), ("is_published", 1)],
            name="idx_exercise_grading_published",
        )
        print("  ✅ Created: idx_exercise_grading_published")

        # Source type + published index
        db.code_exercises.create_index(
            [("source_type", 1), ("is_published", 1)],
            name="idx_exercise_source_published",
        )
        print("  ✅ Created: idx_exercise_source_published")

        # Created by + created at
        db.code_exercises.create_index(
            [("created_by", 1), ("created_at", -1)], name="idx_exercise_user_created"
        )
        print("  ✅ Created: idx_exercise_user_created")

    except Exception as e:
        print(f"  ⚠️  Error creating exercise indexes: {e}")

    # ==================== LEARNING COMMENTS ====================
    print("\n📦 Creating indexes for learning_comments (like/comment system)...")

    try:
        # Content type + content ID (for fetching comments)
        db.learning_comments.create_index(
            [("content_type", 1), ("content_id", 1), ("created_at", -1)],
            name="idx_comment_content_created",
        )
        print("  ✅ Created: idx_comment_content_created")

        # User comments
        db.learning_comments.create_index(
            [("user_id", 1), ("created_at", -1)], name="idx_comment_user_created"
        )
        print("  ✅ Created: idx_comment_user_created")

        # Parent comment ID (for replies)
        db.learning_comments.create_index(
            "parent_comment_id", name="idx_comment_parent"
        )
        print("  ✅ Created: idx_comment_parent")

    except Exception as e:
        print(f"  ⚠️  Error creating comment indexes: {e}")

    # ==================== LEARNING LIKES ====================
    print("\n📦 Creating indexes for learning_likes...")

    try:
        # Content type + content ID + user ID (unique like)
        db.learning_likes.create_index(
            [("content_type", 1), ("content_id", 1), ("user_id", 1)],
            unique=True,
            name="idx_like_unique",
        )
        print("  ✅ Created: idx_like_unique (unique)")

        # User likes
        db.learning_likes.create_index(
            [("user_id", 1), ("created_at", -1)], name="idx_like_user_created"
        )
        print("  ✅ Created: idx_like_user_created")

    except Exception as e:
        print(f"  ⚠️  Error creating like indexes: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("✅ ALL INDEXES CREATED!")
    print("=" * 80)

    # List all indexes
    print("\n📊 Index Summary:\n")

    collections = [
        "learning_categories",
        "learning_topics",
        "knowledge_articles",
        "code_templates",
        "code_exercises",
        "learning_comments",
        "learning_likes",
    ]

    total_indexes = 0
    for coll_name in collections:
        indexes = list(db[coll_name].list_indexes())
        print(f"  {coll_name}: {len(indexes)} indexes")
        for idx in indexes:
            print(f"    - {idx['name']}")
        total_indexes += len(indexes)
        print()

    print(f"📊 Total indexes: {total_indexes}")
    print(f"Completed at: {datetime.utcnow().isoformat()}")
    print("=" * 80)


if __name__ == "__main__":
    create_learning_system_indexes()
