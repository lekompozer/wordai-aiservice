#!/usr/bin/env python3
"""
Test gap generation on 20 songs to verify quality before full batch processing.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
from src.models.song_models import DifficultyLevel


def main():
    """Test gap generation on 20 random songs."""
    print("=" * 70)
    print("🧪 TEST GAP GENERATION - 20 SONGS")
    print("=" * 70)
    print()

    # Import generator class
    from generate_song_gaps_batch import GapGenerator

    # Initialize
    generator = GapGenerator()
    db = generator.db

    # Get 20 random songs
    print("📊 Selecting 20 random songs...")
    songs = list(
        db["song_lyrics"].aggregate(
            [
                {"$sample": {"size": 20}},
                {"$project": {"song_id": 1, "title": 1, "artist": 1, "word_count": 1}},
            ]
        )
    )

    print(f"✅ Selected {len(songs)} songs")
    print()

    # Process each song
    success_count = 0
    failed_songs = []

    for i, song in enumerate(songs, 1):
        print(
            f"[{i}/20] Processing: {song['title']} - {song['artist']} ({song['word_count']} words)"
        )

        # Generate gaps for all 3 difficulties
        gaps_created = generator.process_song(song["song_id"])

        if gaps_created == 3:
            print(f"   ✅ Created {gaps_created} gap sets (easy, medium, hard)")
            success_count += 1
        elif gaps_created > 0:
            print(f"   ⚠️  Only created {gaps_created}/3 gap sets")
            failed_songs.append((song["title"], gaps_created))
        else:
            print(f"   ❌ Failed to create any gaps")
            failed_songs.append((song["title"], 0))

        print()

    # Summary
    print("=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print(f"✅ Successful: {success_count}/20 songs ({success_count/20*100:.1f}%)")
    print(f"❌ Failed/Partial: {len(failed_songs)}/20")

    if failed_songs:
        print()
        print("Failed songs:")
        for title, gaps in failed_songs:
            print(f"   - {title}: {gaps}/3 gaps")

    print()
    print("🔍 Now run validate_gaps_quality.py to check quality!")


if __name__ == "__main__":
    main()
