#!/usr/bin/env python3
"""
Analyze lyrics structure to determine optimal gap counts.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager


def main():
    """Analyze song lyrics structure."""
    db_manager = DBManager()
    db = db_manager.db

    print("📊 Analyzing song lyrics structure...")

    # Sample 100 random songs
    songs = list(db["song_lyrics"].aggregate([{"$sample": {"size": 100}}]))

    line_counts = []
    word_counts = []

    for song in songs:
        lyrics = song.get("english_lyrics", "")
        lines = [line for line in lyrics.split("\n") if line.strip()]
        words = lyrics.split()

        line_counts.append(len(lines))
        word_counts.append(len(words))

    # Statistics
    avg_lines = sum(line_counts) / len(line_counts)
    min_lines = min(line_counts)
    max_lines = max(line_counts)

    avg_words = sum(word_counts) / len(word_counts)
    min_words = min(word_counts)
    max_words = max(word_counts)

    print(f"\n📈 Line Statistics (100 songs):")
    print(f"   Average: {avg_lines:.1f} lines")
    print(f"   Min: {min_lines} lines")
    print(f"   Max: {max_lines} lines")

    print(f"\n📈 Word Statistics:")
    print(f"   Average: {avg_words:.1f} words")
    print(f"   Min: {min_words} words")
    print(f"   Max: {max_words} words")

    # Recommended gap counts (1 gap per ~3-5 lines)
    print(f"\n💡 Recommended gap counts (1 gap per ~4 lines):")
    print(f"   Easy: {int(avg_lines / 6)} gaps (1 gap per 6 lines)")
    print(f"   Medium: {int(avg_lines / 4)} gaps (1 gap per 4 lines)")
    print(f"   Hard: {int(avg_lines / 3)} gaps (1 gap per 3 lines)")


if __name__ == "__main__":
    main()
