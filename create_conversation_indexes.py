"""
Create indexes for Conversation Learning collections

Collections:
- conversation_library
- conversation_vocabulary  
- conversation_gaps
- user_conversation_progress

Run in Docker:
    docker exec ai-chatbot-rag python create_conversation_indexes.py
"""

from src.database.db_manager import DBManager
from pymongo import ASCENDING, DESCENDING, TEXT


def create_conversation_indexes():
    """Create all indexes for conversation learning"""
    
    db_manager = DBManager()
    db = db_manager.db
    
    print("=" * 80)
    print("CREATING CONVERSATION LEARNING INDEXES")
    print("=" * 80)
    print(f"Database: {db.name}")
    print()
    
    # ========================================================================
    # conversation_library
    # ========================================================================
    print("📚 Creating indexes for: conversation_library")
    
    collection = db.conversation_library
    
    # Drop existing indexes (except _id)
    try:
        collection.drop_indexes()
        print("  ✓ Dropped existing indexes")
    except Exception as e:
        print(f"  ⚠ No existing indexes to drop: {e}")
    
    # Primary key
    collection.create_index(
        [("conversation_id", ASCENDING)],
        unique=True,
        name="idx_conversation_id"
    )
    print("  ✓ idx_conversation_id (unique)")
    
    # Search by level
    collection.create_index(
        [("level", ASCENDING)],
        name="idx_level"
    )
    print("  ✓ idx_level")
    
    # Search by topic
    collection.create_index(
        [("topic_slug", ASCENDING)],
        name="idx_topic_slug"
    )
    print("  ✓ idx_topic_slug")
    
    # Search by level + topic
    collection.create_index(
        [("level", ASCENDING), ("topic_slug", ASCENDING)],
        name="idx_level_topic"
    )
    print("  ✓ idx_level_topic")
    
    # Search by difficulty
    collection.create_index(
        [("difficulty_score", ASCENDING)],
        name="idx_difficulty"
    )
    print("  ✓ idx_difficulty")
    
    # Sort by created date
    collection.create_index(
        [("created_at", DESCENDING)],
        name="idx_created_at"
    )
    print("  ✓ idx_created_at")
    
    # Text search on title and situation
    collection.create_index(
        [("title.en", TEXT), ("title.vi", TEXT), ("situation", TEXT)],
        name="idx_text_search"
    )
    print("  ✓ idx_text_search (full-text)")
    
    print()
    
    # ========================================================================
    # conversation_vocabulary
    # ========================================================================
    print("📖 Creating indexes for: conversation_vocabulary")
    
    collection = db.conversation_vocabulary
    
    # Drop existing indexes
    try:
        collection.drop_indexes()
        print("  ✓ Dropped existing indexes")
    except Exception as e:
        print(f"  ⚠ No existing indexes to drop: {e}")
    
    # Primary key
    collection.create_index(
        [("vocab_id", ASCENDING)],
        unique=True,
        name="idx_vocab_id"
    )
    print("  ✓ idx_vocab_id (unique)")
    
    # Link to conversation
    collection.create_index(
        [("conversation_id", ASCENDING)],
        unique=True,
        name="idx_conversation_id"
    )
    print("  ✓ idx_conversation_id (unique)")
    
    print()
    
    # ========================================================================
    # conversation_gaps
    # ========================================================================
    print("📝 Creating indexes for: conversation_gaps")
    
    collection = db.conversation_gaps
    
    # Drop existing indexes
    try:
        collection.drop_indexes()
        print("  ✓ Dropped existing indexes")
    except Exception as e:
        print(f"  ⚠ No existing indexes to drop: {e}")
    
    # Primary key
    collection.create_index(
        [("gap_id", ASCENDING)],
        unique=True,
        name="idx_gap_id"
    )
    print("  ✓ idx_gap_id (unique)")
    
    # Link to conversation
    collection.create_index(
        [("conversation_id", ASCENDING)],
        name="idx_conversation_id"
    )
    print("  ✓ idx_conversation_id")
    
    # Search by difficulty
    collection.create_index(
        [("difficulty", ASCENDING)],
        name="idx_difficulty"
    )
    print("  ✓ idx_difficulty")
    
    # Search by conversation + difficulty
    collection.create_index(
        [("conversation_id", ASCENDING), ("difficulty", ASCENDING)],
        name="idx_conversation_difficulty"
    )
    print("  ✓ idx_conversation_difficulty")
    
    print()
    
    # ========================================================================
    # user_conversation_progress
    # ========================================================================
    print("👤 Creating indexes for: user_conversation_progress")
    
    collection = db.user_conversation_progress
    
    # Drop existing indexes
    try:
        collection.drop_indexes()
        print("  ✓ Dropped existing indexes")
    except Exception as e:
        print(f"  ⚠ No existing indexes to drop: {e}")
    
    # Primary key
    collection.create_index(
        [("progress_id", ASCENDING)],
        unique=True,
        name="idx_progress_id"
    )
    print("  ✓ idx_progress_id (unique)")
    
    # User's conversations
    collection.create_index(
        [("user_id", ASCENDING)],
        name="idx_user_id"
    )
    print("  ✓ idx_user_id")
    
    # Conversation progress
    collection.create_index(
        [("conversation_id", ASCENDING)],
        name="idx_conversation_id"
    )
    print("  ✓ idx_conversation_id")
    
    # User + Conversation (unique progress per user per conversation)
    collection.create_index(
        [("user_id", ASCENDING), ("conversation_id", ASCENDING)],
        unique=True,
        name="idx_user_conversation"
    )
    print("  ✓ idx_user_conversation (unique)")
    
    # Sort by last attempt
    collection.create_index(
        [("last_attempt_at", DESCENDING)],
        name="idx_last_attempt"
    )
    print("  ✓ idx_last_attempt")
    
    # Search by completion status
    collection.create_index(
        [("is_completed", ASCENDING)],
        name="idx_is_completed"
    )
    print("  ✓ idx_is_completed")
    
    # User's completed conversations
    collection.create_index(
        [("user_id", ASCENDING), ("is_completed", ASCENDING)],
        name="idx_user_completed"
    )
    print("  ✓ idx_user_completed")
    
    print()
    print("=" * 80)
    print("✅ ALL INDEXES CREATED SUCCESSFULLY")
    print("=" * 80)
    print()
    
    # Show summary
    print("📊 Index Summary:")
    print()
    
    for coll_name in ["conversation_library", "conversation_vocabulary", 
                      "conversation_gaps", "user_conversation_progress"]:
        coll = db[coll_name]
        indexes = list(coll.list_indexes())
        print(f"  {coll_name}: {len(indexes)} indexes")
        for idx in indexes:
            if idx["name"] != "_id_":
                print(f"    - {idx['name']}")
    
    print()


if __name__ == "__main__":
    create_conversation_indexes()
