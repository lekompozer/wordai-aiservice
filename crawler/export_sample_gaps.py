#!/usr/bin/env python3
"""
Export 20 sample gap documents to JSON for review.
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager


def serialize_doc(doc):
    """Convert MongoDB doc to JSON-serializable format."""
    if isinstance(doc, dict):
        return {k: serialize_doc(v) for k, v in doc.items() if k != "_id"}
    elif isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    elif isinstance(doc, datetime):
        return doc.isoformat()
    return doc


def main():
    """Export 20 gap samples."""
    db_manager = DBManager()
    db = db_manager.db

    print("📊 Exporting 20 gap samples...")

    # Get 20 gap documents with song info
    gaps_col = db["song_gaps"]
    songs_col = db["song_lyrics"]

    # Sample gaps
    gaps = list(
        gaps_col.aggregate(
            [
                {"$sample": {"size": 20}},
                {"$sort": {"difficulty": 1}},  # Sort by difficulty
            ]
        )
    )

    # Enrich with song info
    samples = []
    for gap_doc in gaps:
        # Get song
        song = songs_col.find_one({"song_id": gap_doc["song_id"]})

        sample = {
            "song_id": gap_doc["song_id"],
            "song_title": song["title"] if song else "Unknown",
            "artist": song["artist"] if song else "Unknown",
            "difficulty": gap_doc["difficulty"],
            "gap_count": gap_doc["gap_count"],
            "avg_difficulty_score": gap_doc["avg_difficulty_score"],
            "gaps": gap_doc["gaps"][:3],  # First 3 gaps only for brevity
            "lyrics_with_gaps_preview": (
                gap_doc["lyrics_with_gaps"][:300] + "..."
                if len(gap_doc["lyrics_with_gaps"]) > 300
                else gap_doc["lyrics_with_gaps"]
            ),
        }

        samples.append(serialize_doc(sample))

    # Save to JSON
    output_file = "gap_samples_20.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)

    print(f"✅ Exported to {output_file}")
    print(f"📊 Total samples: {len(samples)}")

    # Print summary
    by_difficulty = {}
    for sample in samples:
        diff = sample["difficulty"]
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1

    print("\n📈 By difficulty:")
    for diff, count in sorted(by_difficulty.items()):
        print(f"   {diff}: {count} samples")

    # Print first sample as preview
    print("\n🔍 Preview (first sample):")
    print(json.dumps(samples[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
