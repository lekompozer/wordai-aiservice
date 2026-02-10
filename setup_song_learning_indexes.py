"""
Setup MongoDB Indexes for Song Learning Feature

Run this script to create all required indexes for the 5 collections:
- song_lyrics
- song_gaps
- user_song_progress
- user_song_subscription
- user_daily_free_songs

Usage:
    python setup_song_learning_indexes.py
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.database.db_manager import DBManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_song_lyrics_indexes(db):
    """Setup indexes for song_lyrics collection"""
    collection = db.song_lyrics
    
    logger.info("📚 Creating indexes for song_lyrics...")
    
    # Unique song_id
    collection.create_index("song_id", unique=True, name="song_id_unique")
    logger.info("  ✅ song_id (unique)")
    
    # Text search on artist and title
    collection.create_index(
        [("title", "text"), ("artist", "text")],
        name="title_artist_text"
    )
    logger.info("  ✅ title + artist (text search)")
    
    # Processing status
    collection.create_index("is_processed", name="is_processed_idx")
    logger.info("  ✅ is_processed")
    
    # Category
    collection.create_index("category", name="category_idx")
    logger.info("  ✅ category")
    
    # Artist for filtering
    collection.create_index("artist", name="artist_idx")
    logger.info("  ✅ artist")


def setup_song_gaps_indexes(db):
    """Setup indexes for song_gaps collection"""
    collection = db.song_gaps
    
    logger.info("🎯 Creating indexes for song_gaps...")
    
    # Compound unique: song_id + difficulty
    collection.create_index(
        [("song_id", 1), ("difficulty", 1)],
        unique=True,
        name="song_difficulty_unique"
    )
    logger.info("  ✅ song_id + difficulty (unique)")
    
    # Difficulty filter
    collection.create_index("difficulty", name="difficulty_idx")
    logger.info("  ✅ difficulty")
    
    # Gap count for analytics
    collection.create_index("gap_count", name="gap_count_idx")
    logger.info("  ✅ gap_count")


def setup_user_song_progress_indexes(db):
    """Setup indexes for user_song_progress collection"""
    collection = db.user_song_progress
    
    logger.info("📈 Creating indexes for user_song_progress...")
    
    # Compound: user_id + song_id + difficulty (unique per combination)
    collection.create_index(
        [("user_id", 1), ("song_id", 1), ("difficulty", 1)],
        unique=True,
        name="user_song_difficulty_unique"
    )
    logger.info("  ✅ user_id + song_id + difficulty (unique)")
    
    # User's completed songs
    collection.create_index(
        [("user_id", 1), ("is_completed", 1)],
        name="user_completed_idx"
    )
    logger.info("  ✅ user_id + is_completed")
    
    # User's recent progress
    collection.create_index(
        [("user_id", 1), ("last_attempt_at", -1)],
        name="user_recent_attempts_idx"
    )
    logger.info("  ✅ user_id + last_attempt_at")
    
    # User ID for all queries
    collection.create_index("user_id", name="user_id_idx")
    logger.info("  ✅ user_id")


def setup_user_subscription_indexes(db):
    """Setup indexes for user_song_subscription collection"""
    collection = db.user_song_subscription
    
    logger.info("💎 Creating indexes for user_song_subscription...")
    
    # Unique subscription_id
    collection.create_index("subscription_id", unique=True, name="subscription_id_unique")
    logger.info("  ✅ subscription_id (unique)")
    
    # User's active subscription
    collection.create_index(
        [("user_id", 1), ("is_active", 1)],
        name="user_active_subscription_idx"
    )
    logger.info("  ✅ user_id + is_active")
    
    # User's subscription expiry check
    collection.create_index(
        [("user_id", 1), ("end_date", -1)],
        name="user_expiry_idx"
    )
    logger.info("  ✅ user_id + end_date")
    
    # Active subscriptions
    collection.create_index("is_active", name="is_active_idx")
    logger.info("  ✅ is_active")


def setup_user_daily_free_songs_indexes(db):
    """Setup indexes for user_daily_free_songs collection"""
    collection = db.user_daily_free_songs
    
    logger.info("🎁 Creating indexes for user_daily_free_songs...")
    
    # Compound unique: user_id + date (one record per user per day)
    collection.create_index(
        [("user_id", 1), ("date", 1)],
        unique=True,
        name="user_date_unique"
    )
    logger.info("  ✅ user_id + date (unique)")
    
    # User's daily usage
    collection.create_index(
        [("user_id", 1), ("songs_count", 1)],
        name="user_count_idx"
    )
    logger.info("  ✅ user_id + songs_count")


def main():
    """Main setup function"""
    logger.info("=" * 60)
    logger.info("🎵 Song Learning Feature - MongoDB Indexes Setup")
    logger.info("=" * 60)
    
    try:
        # Connect to database
        db_manager = DBManager()
        db = db_manager.db
        
        logger.info(f"✅ Connected to database: {db.name}")
        logger.info("")
        
        # Setup indexes for each collection
        setup_song_lyrics_indexes(db)
        logger.info("")
        
        setup_song_gaps_indexes(db)
        logger.info("")
        
        setup_user_song_progress_indexes(db)
        logger.info("")
        
        setup_user_subscription_indexes(db)
        logger.info("")
        
        setup_user_daily_free_songs_indexes(db)
        logger.info("")
        
        logger.info("=" * 60)
        logger.info("✅ All indexes created successfully!")
        logger.info("=" * 60)
        
        # Show collection stats
        logger.info("")
        logger.info("📊 Collection Statistics:")
        for collection_name in ["song_lyrics", "song_gaps", "user_song_progress", 
                                "user_song_subscription", "user_daily_free_songs"]:
            count = db[collection_name].count_documents({})
            logger.info(f"  • {collection_name}: {count} documents")
        
    except Exception as e:
        logger.error(f"❌ Error setting up indexes: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
