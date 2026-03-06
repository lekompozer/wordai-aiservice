"""
Create indexes for song_lyrics collection to optimize search performance

Run this script to create indexes for:
- Text search on title and artist (for fast search)
- song_id (unique identifier)
- category, first_letter, artist (for filtering)
- view_count (for trending/hot songs)
"""

from src.database.db_manager import DBManager


def create_song_lyrics_indexes():
    """Create all necessary indexes for song_lyrics collection"""

    db_manager = DBManager()
    db = db_manager.db

    song_lyrics_col = db["song_lyrics"]

    print("Creating indexes for song_lyrics collection...")

    # 1. Text index for fast search on title and artist
    print("1. Creating text index on title and artist...")
    song_lyrics_col.create_index(
        [("title", "text"), ("artist", "text")],
        name="title_artist_text",
        default_language="english",
        weights={"title": 2, "artist": 1},  # Title has higher weight
    )

    # 2. Unique index on song_id
    print("2. Creating unique index on song_id...")
    song_lyrics_col.create_index("song_id", unique=True, name="song_id_unique")

    # 3. Index on category for filtering
    print("3. Creating index on category...")
    song_lyrics_col.create_index("category", name="category_idx")

    # 4. Index on artist for exact artist filtering
    print("4. Creating index on artist...")
    song_lyrics_col.create_index("artist", name="artist_idx")

    # 5. Index on view_count for trending/hot songs
    print("5. Creating index on view_count (descending)...")
    song_lyrics_col.create_index([("view_count", -1)], name="view_count_desc")

    # 6. Compound index for first_letter filtering
    print("6. Creating index on title (for first_letter queries)...")
    song_lyrics_col.create_index([("title", 1)], name="title_asc")

    # 7. Index on updated_at for recently played
    print("7. Creating index on updated_at (descending)...")
    song_lyrics_col.create_index([("updated_at", -1)], name="updated_at_desc")

    print("\n✅ All indexes created successfully!")

    # List all indexes
    print("\nCurrent indexes:")
    for idx in song_lyrics_col.list_indexes():
        print(f"  - {idx['name']}: {idx.get('key', {})}")


if __name__ == "__main__":
    create_song_lyrics_indexes()
