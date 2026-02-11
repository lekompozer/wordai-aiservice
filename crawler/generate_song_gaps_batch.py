#!/usr/bin/env python3
"""
Generate gap-fill exercises for song lyrics with 3 difficulty levels.
Uses spaCy for POS tagging, wordfreq for difficulty scoring, better-profanity for filtering.

Phase 3: Gap Generation
- Difficulty levels: easy (1-5 gaps), medium (3-7 gaps), hard (5-10 gaps)
- Target POS: NOUN, VERB, ADJ (proper nouns preferred for easy)
- Zipf frequency: 0-8 scale (higher = more common)
- Max 10 gaps per difficulty level
- No profanity in gap words
"""

import sys
import os
import asyncio
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import uuid
from multiprocessing import Pool, cpu_count

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import spacy
from wordfreq import zipf_frequency
from better_profanity import profanity
from tqdm import tqdm

from src.database.db_manager import DBManager
from src.models.song_models import DifficultyLevel, POSTag, SongGaps, GapItem


class GapGenerator:
    """Generate gap-fill exercises from song lyrics."""

    def __init__(self):
        """Initialize NLP models and DB connection."""
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
            print("✅ Loaded spaCy model: en_core_web_sm")
        except OSError:
            print(
                "❌ spaCy model not found. Run: python -m spacy download en_core_web_sm"
            )
            sys.exit(1)

        # Initialize profanity filter
        profanity.load_censor_words()

        # Database
        self.db_manager = DBManager()
        self.db = self.db_manager.db

        # Collections
        self.song_lyrics_col = self.db["song_lyrics"]
        self.song_gaps_col = self.db["song_gaps"]

        # POS tags we want to target
        self.target_pos = {POSTag.NOUN, POSTag.VERB, POSTag.ADJ}

        # Difficulty configurations
        # Based on avg 53 lines/song: 1 gap per ~4-6 lines
        self.difficulty_configs = {
            DifficultyLevel.EASY: {
                "min_gaps": 8,
                "max_gaps": 10,
                "prefer_proper_nouns": True,
                "min_zipf": 5.0,  # Common words only (1 gap per 6 lines)
            },
            DifficultyLevel.MEDIUM: {
                "min_gaps": 12,
                "max_gaps": 15,
                "prefer_proper_nouns": False,
                "min_zipf": 3.0,  # Moderate difficulty (1 gap per 4 lines)
            },
            DifficultyLevel.HARD: {
                "min_gaps": 15,
                "max_gaps": 20,
                "prefer_proper_nouns": False,
                "min_zipf": 0.0,  # All words (1 gap per 3 lines)
            },
        }

    def calculate_word_difficulty(self, word: str) -> float:
        """
        Calculate difficulty score using Zipf frequency (0-8 scale).
        Higher Zipf = more common = easier.
        We invert it so higher score = harder.

        Returns: 0-10 difficulty score (10 = hardest)
        """
        # Get Zipf frequency (0-8, where 8 = most common)
        zipf = zipf_frequency(word.lower(), "en")

        # Invert: Zipf 8 → difficulty 0, Zipf 0 → difficulty 10
        difficulty = max(0, min(10, (8 - zipf) * 1.25))

        return round(difficulty, 2)

    def is_valid_gap_word(
        self, token, min_zipf: float = 0.0, prefer_proper_nouns: bool = False
    ) -> bool:
        """
        Check if a token is suitable for a gap.

        Args:
            token: spaCy Token object
            min_zipf: Minimum Zipf frequency (higher = more common)
            prefer_proper_nouns: If True, prioritize proper nouns (PROPN)

        Returns: True if token is valid for gap
        """
        # Must be alphabetic (no numbers, punctuation)
        if not token.is_alpha:
            return False

        # Must be longer than 2 characters
        if len(token.text) < 3:
            return False

        # Check if word is profane
        if profanity.contains_profanity(token.text.lower()):
            return False

        # Check POS tag
        pos_tag = token.pos_

        # For easy level, prioritize proper nouns (names, places)
        if prefer_proper_nouns and pos_tag == "PROPN":
            return True

        # Otherwise check if it's one of our target POS
        if pos_tag not in ["NOUN", "VERB", "ADJ"]:
            return False

        # Check Zipf frequency (word commonness)
        zipf = zipf_frequency(token.text.lower(), "en")
        if zipf < min_zipf:
            return False

        return True

    def select_gaps(
        self,
        doc,
        min_gaps: int,
        max_gaps: int,
        min_zipf: float = 0.0,
        prefer_proper_nouns: bool = False,
    ) -> List[Dict]:
        """
        Select words to be gaps based on difficulty config.

        Returns: List of gap dictionaries with position, word, POS, difficulty
        """
        # Find all candidate tokens
        candidates = []

        # Track line numbers
        current_line = 0
        word_in_line = 0

        for i, token in enumerate(doc):
            # Count lines (newlines increase line number)
            if i > 0 and doc[i - 1].text_with_ws.endswith("\n"):
                current_line += 1
                word_in_line = 0

            if self.is_valid_gap_word(token, min_zipf, prefer_proper_nouns):
                difficulty = self.calculate_word_difficulty(token.text)

                # Check if end of line
                is_eol = token.text_with_ws.endswith("\n") or i == len(doc) - 1

                candidates.append(
                    {
                        "position": i,
                        "word": token.text,
                        "pos": token.pos_,
                        "difficulty": difficulty,
                        "line_number": current_line,
                        "word_index": word_in_line,
                        "lemma": token.lemma_,
                        "char_count": len(token.text),
                        "is_end_of_line": is_eol,
                    }
                )

            word_in_line += 1

        # If not enough candidates, return what we have
        if len(candidates) < min_gaps:
            return candidates

        # Sort by difficulty (for easy: prefer easier words, for hard: prefer harder)
        if prefer_proper_nouns:
            # Easy: Proper nouns first, then by easiness (lower difficulty)
            candidates.sort(key=lambda x: (x["pos"] != "PROPN", x["difficulty"]))
        else:
            # Medium/Hard: Sort by difficulty score (higher = harder)
            candidates.sort(key=lambda x: -x["difficulty"])

        # Distribute gaps evenly throughout lyrics
        total_tokens = len(doc)
        selected = []

        # Calculate ideal spacing
        num_gaps = min(max_gaps, len(candidates))
        spacing = total_tokens / (num_gaps + 1)

        # Select gaps with even distribution
        for gap_num in range(num_gaps):
            ideal_pos = int((gap_num + 1) * spacing)

            # Find closest candidate to ideal position
            closest = min(
                [c for c in candidates if c not in selected],
                key=lambda x: abs(x["position"] - ideal_pos),
                default=None,
            )

            if closest:
                selected.append(closest)

        # Ensure minimum gaps
        while len(selected) < min_gaps and candidates:
            remaining = [c for c in candidates if c not in selected]
            if not remaining:
                break
            selected.append(remaining[0])

        # Sort by position for final output
        selected.sort(key=lambda x: x["position"])

        return selected[:max_gaps]  # Ensure max limit

    def create_lyrics_with_gaps(self, lyrics: str, gaps: List[Dict]) -> str:
        """
        Replace gap words with ___ blanks.

        Args:
            lyrics: Original lyrics text
            gaps: List of gap dictionaries with position, word

        Returns: Lyrics with gaps replaced by ___
        """
        doc = self.nlp(lyrics)

        # Create lookup for gap positions
        gap_positions = {g["position"]: g["word"] for g in gaps}

        # Rebuild lyrics with gaps
        result = []
        for i, token in enumerate(doc):
            if i in gap_positions:
                result.append("___")
            else:
                result.append(token.text_with_ws)

        return "".join(result)

    def generate_gaps_for_song(
        self, song: Dict, difficulty: DifficultyLevel
    ) -> Optional[SongGaps]:
        """
        Generate gap-fill exercise for one song at specified difficulty.

        Args:
            song: Song document from song_lyrics collection
            difficulty: Difficulty level (easy/medium/hard)

        Returns: SongGaps object or None if generation failed
        """
        lyrics = song.get("english_lyrics", "")
        if not lyrics or len(lyrics) < 100:
            return None

        # Get difficulty config
        config = self.difficulty_configs[difficulty]

        # Process lyrics with spaCy
        doc = self.nlp(lyrics)

        # Select gaps
        gaps = self.select_gaps(
            doc,
            min_gaps=config["min_gaps"],
            max_gaps=config["max_gaps"],
            min_zipf=config["min_zipf"],
            prefer_proper_nouns=config.get("prefer_proper_nouns", False),
        )

        if len(gaps) < config["min_gaps"]:
            return None  # Not enough valid gaps

        # Create lyrics with gaps
        lyrics_with_gaps = self.create_lyrics_with_gaps(lyrics, gaps)

        # Convert to GapItem objects
        gap_items = [
            GapItem(
                line_number=g["line_number"],
                word_index=g["word_index"],
                original_word=g["word"].lower(),
                lemma=g["lemma"].lower(),
                pos_tag=g["pos"],  # Already a string
                difficulty_score=g["difficulty"],
                char_count=g["char_count"],
                is_end_of_line=g.get("is_end_of_line", False),
            )
            for g in gaps
        ]

        # Calculate average difficulty
        avg_difficulty = round(sum(g["difficulty"] for g in gaps) / len(gaps), 2)

        # Create SongGaps object
        return SongGaps(
            gap_id=str(uuid.uuid4()),
            song_id=song["song_id"],
            difficulty=difficulty,
            gaps=gap_items,
            lyrics_with_gaps=lyrics_with_gaps,
            gap_count=len(gap_items),
            avg_difficulty_score=avg_difficulty,
        )

    def process_song(self, song_id: str) -> int:
        """
        Process one song: generate gaps for all 3 difficulty levels.

        Returns: Number of gap documents created (0-3)
        """
        # Fetch song
        song = self.song_lyrics_col.find_one({"song_id": song_id})
        if not song:
            return 0

        # Generate gaps for all 3 difficulties
        created = 0
        for difficulty in [
            DifficultyLevel.EASY,
            DifficultyLevel.MEDIUM,
            DifficultyLevel.HARD,
        ]:
            gaps_doc = self.generate_gaps_for_song(song, difficulty)

            if gaps_doc:
                # Insert into database
                self.song_gaps_col.update_one(
                    {"song_id": song_id, "difficulty": difficulty.value},
                    {"$set": gaps_doc.model_dump()},
                    upsert=True,
                )
                created += 1

        return created

    def process_batch(self, batch_size: int = 100):
        """
        Process all songs in batches with progress bar.

        Args:
            batch_size: Number of songs to process before showing progress
        """
        # Get all unprocessed songs
        total_songs = self.song_lyrics_col.count_documents({})
        processed_song_ids = self.song_gaps_col.distinct("song_id")

        # Get songs that need processing
        unprocessed = self.song_lyrics_col.find(
            {"song_id": {"$nin": processed_song_ids}}, {"song_id": 1}
        )

        song_ids = [s["song_id"] for s in unprocessed]

        print(f"📊 Total songs: {total_songs}")
        print(f"✅ Already processed: {len(processed_song_ids)}")
        print(f"⏳ To process: {len(song_ids)}")
        print()

        if not song_ids:
            print("✅ All songs already have gaps generated!")
            return

        # Process with progress bar
        total_gaps = 0
        with tqdm(total=len(song_ids), desc="Generating gaps") as pbar:
            for i in range(0, len(song_ids), batch_size):
                batch = song_ids[i : i + batch_size]

                for song_id in batch:
                    gaps_created = self.process_song(song_id)
                    total_gaps += gaps_created
                    pbar.update(1)

        print()
        print(f"✅ Gap generation complete!")
        print(f"   Songs processed: {len(song_ids)}")
        print(f"   Gap documents created: {total_gaps}")
        print(f"   Expected: {len(song_ids) * 3} (3 per song)")


def main():
    """Main entry point."""
    print("=" * 70)
    print("🎵 SONG LEARNING - GAP GENERATION (PHASE 3)")
    print("=" * 70)
    print()

    generator = GapGenerator()
    generator.process_batch(batch_size=100)

    print()
    print("✅ All done!")


if __name__ == "__main__":
    main()
