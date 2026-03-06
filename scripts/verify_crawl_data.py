"""
Verify Crawled Song Data

Checks data quality and provides statistics after crawling

Usage:
    python verify_crawl_data.py
"""

import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.database.db_manager import DBManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_crawl_data():
    """Verify crawled song data quality"""
    logger.info("=" * 80)
    logger.info("🔍 VERIFYING CRAWLED SONG DATA")
    logger.info("=" * 80)
    logger.info("")

    # Connect to database
    db_manager = DBManager()
    db = db_manager.db
    collection = db.song_lyrics

    # Total count
    total_songs = collection.count_documents({})
    logger.info(f"📊 Total Songs: {total_songs:,}")
    logger.info("")

    # Check for required fields
    logger.info("🔎 Checking Required Fields:")
    required_fields = [
        "song_id",
        "title",
        "artist",
        "category",
        "english_lyrics",
        "vietnamese_lyrics",
        "youtube_url",
        "youtube_id",
        "source_url",
    ]

    for field in required_fields:
        missing = collection.count_documents({field: {"$in": [None, ""]}})
        percentage = (missing / total_songs * 100) if total_songs > 0 else 0
        status = "✅" if missing == 0 else "⚠️"
        logger.info(f"  {status} {field}: {missing:,} missing ({percentage:.1f}%)")

    logger.info("")

    # Check for duplicates
    logger.info("🔍 Checking for Duplicates:")

    # Duplicate song_ids
    pipeline = [
        {"$group": {"_id": "$song_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$count": "total"},
    ]
    duplicate_ids = list(collection.aggregate(pipeline))
    dup_count = duplicate_ids[0]["total"] if duplicate_ids else 0
    status = "✅" if dup_count == 0 else "⚠️"
    logger.info(f"  {status} Duplicate song_ids: {dup_count}")

    # Duplicate source_urls
    pipeline[0]["$group"]["_id"] = "$source_url"
    duplicate_urls = list(collection.aggregate(pipeline))
    dup_url_count = duplicate_urls[0]["total"] if duplicate_urls else 0
    status = "✅" if dup_url_count == 0 else "⚠️"
    logger.info(f"  {status} Duplicate source_urls: {dup_url_count}")

    logger.info("")

    # Category distribution
    logger.info("📂 Category Distribution:")
    categories = collection.aggregate(
        [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
    )

    for cat in categories:
        category_name = cat["_id"] or "(no category)"
        count = cat["count"]
        percentage = (count / total_songs * 100) if total_songs > 0 else 0
        logger.info(f"  • {category_name}: {count:,} ({percentage:.1f}%)")

    logger.info("")

    # Artist distribution (top 10)
    logger.info("🎤 Top 10 Artists:")
    artists = collection.aggregate(
        [
            {"$group": {"_id": "$artist", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
    )

    for artist in artists:
        artist_name = artist["_id"] or "(no artist)"
        count = artist["count"]
        logger.info(f"  • {artist_name}: {count:,} songs")

    logger.info("")

    # Lyrics length statistics
    logger.info("📝 Lyrics Statistics:")

    songs_with_lyrics = list(
        collection.find(
            {"english_lyrics": {"$ne": ""}}, {"english_lyrics": 1, "word_count": 1}
        ).limit(1000)
    )  # Sample

    if songs_with_lyrics:
        word_counts = [s.get("word_count", 0) for s in songs_with_lyrics]
        avg_words = sum(word_counts) / len(word_counts)
        min_words = min(word_counts)
        max_words = max(word_counts)

        logger.info(f"  • Average word count: {avg_words:.0f} words")
        logger.info(f"  • Min word count: {min_words} words")
        logger.info(f"  • Max word count: {max_words} words")

    logger.info("")

    # YouTube URL coverage
    logger.info("🎥 YouTube Coverage:")
    with_youtube = collection.count_documents({"youtube_id": {"$ne": ""}})
    percentage = (with_youtube / total_songs * 100) if total_songs > 0 else 0
    status = "✅" if percentage > 90 else "⚠️"
    logger.info(f"  {status} Songs with YouTube: {with_youtube:,} ({percentage:.1f}%)")

    logger.info("")

    # Processing status
    logger.info("⚙️ Processing Status:")
    processed = collection.count_documents({"is_processed": True})
    unprocessed = collection.count_documents({"is_processed": False})
    logger.info(f"  • Processed (gaps generated): {processed:,}")
    logger.info(f"  • Unprocessed: {unprocessed:,}")

    logger.info("")

    # Data quality score
    logger.info("🎯 Data Quality Score:")

    quality_checks = {
        "Has title": collection.count_documents({"title": {"$ne": ""}}),
        "Has artist": collection.count_documents({"artist": {"$ne": ""}}),
        "Has category": collection.count_documents({"category": {"$ne": ""}}),
        "Has English lyrics": collection.count_documents(
            {"english_lyrics": {"$ne": ""}}
        ),
        "Has Vietnamese lyrics": collection.count_documents(
            {"vietnamese_lyrics": {"$ne": ""}}
        ),
        "Has YouTube": collection.count_documents({"youtube_id": {"$ne": ""}}),
    }

    total_checks = len(quality_checks)
    passed_checks = sum(
        1 for count in quality_checks.values() if count / total_songs > 0.95
    )
    quality_score = passed_checks / total_checks * 100

    for check_name, count in quality_checks.items():
        percentage = (count / total_songs * 100) if total_songs > 0 else 0
        status = "✅" if percentage > 95 else "⚠️"
        logger.info(f"  {status} {check_name}: {percentage:.1f}%")

    logger.info("")
    logger.info(f"Overall Quality Score: {quality_score:.0f}/100")

    logger.info("")
    logger.info("=" * 80)

    # Recommendations
    if dup_count > 0:
        logger.warning("⚠️ RECOMMENDATION: Remove duplicate song_ids")

    if with_youtube / total_songs < 0.9:
        logger.warning("⚠️ RECOMMENDATION: Many songs missing YouTube links")

    if quality_score < 80:
        logger.warning("⚠️ RECOMMENDATION: Data quality needs improvement")
    else:
        logger.info("✅ Data quality is good!")

    logger.info("")


if __name__ == "__main__":
    verify_crawl_data()
