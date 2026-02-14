#!/usr/bin/env python3
"""
Generate gap-fill exercises for conversation dialogues with 3 difficulty levels.
Uses spaCy for POS tagging and wordfreq for difficulty scoring.

Difficulty levels:
- Easy: 15% of words (prefer NOUNS and proper nouns)
- Medium: 25% of words (NOUNS, VERBS, ADJECTIVES)
- Hard: 35% of words (NOUNS, VERBS, ADJECTIVES, ADVERBS)
"""

import sys
import os
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import spacy
from wordfreq import zipf_frequency
from tqdm import tqdm

from src.database.db_manager import DBManager


class ConversationGapGenerator:
    """Generate gap-fill exercises from conversation dialogues."""

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

        # Database
        self.db_manager = DBManager()
        self.db = self.db_manager.db

        # Collections
        self.conv_library_col = self.db["conversation_library"]
        self.conv_gaps_col = self.db["conversation_gaps"]

        # Difficulty configurations (percentage of total words)
        self.difficulty_configs = {
            "easy": {
                "percentage": 0.15,  # 15% of words
                "target_pos": {
                    "NOUN"
                },  # Only common nouns (exclude PROPN like "Ben", "Anna")
                "min_zipf": 4.0,  # Common words only
                "hint_type": "none",  # "_____" no hints
            },
            "medium": {
                "percentage": 0.25,  # 25% of words
                "target_pos": {"NOUN", "VERB", "ADJ"},
                "min_zipf": 2.0,  # Moderate difficulty
                "hint_type": "none",  # "_____" no hints
            },
            "hard": {
                "percentage": 0.35,  # 35% of words
                "target_pos": {"NOUN", "VERB", "ADJ", "ADV"},
                "min_zipf": 0.0,  # All words
                "hint_type": "none",  # "_____" no hints
            },
        }

    def calculate_word_difficulty(self, word: str) -> float:
        """
        Calculate difficulty score using Zipf frequency (0-8 scale).
        Higher Zipf = more common = easier.
        Inverted so higher score = harder.

        Returns: 0-10 difficulty score (10 = hardest)
        """
        zipf = zipf_frequency(word.lower(), "en")
        difficulty = max(0, min(10, (8 - zipf) * 1.25))
        return round(difficulty, 2)

    def is_valid_gap_word(
        self, token, min_zipf: float = 0.0, target_pos: set = None
    ) -> bool:
        """Check if a token is suitable for a gap."""
        # Must be alphabetic (no numbers, punctuation)
        if not token.is_alpha:
            return False

        # Must be longer than 2 characters
        if len(token.text) < 3:
            return False

        # Check POS tag
        if target_pos and token.pos_ not in target_pos:
            return False

        # Check Zipf frequency (word commonness)
        zipf = zipf_frequency(token.text.lower(), "en")
        if zipf < min_zipf:
            return False

        return True

    def extract_full_text(self, conversation: Dict) -> str:
        """Extract full English dialogue text from conversation."""
        dialogue = conversation.get("dialogue", [])
        if not dialogue:
            return conversation.get("full_text_en", "")

        # Combine all dialogue turns
        texts = []
        for turn in dialogue:
            text = turn.get("text_en", "").strip()
            if text:
                texts.append(text)

        return " ".join(texts)

    def create_hint(self, word: str, hint_type: str) -> str:
        """Create hint based on hint type."""
        word_len = len(word)

        if hint_type == "first_letter_count":
            # "h____ (5)" for "hello"
            first = word[0].lower()
            blanks = "_" * (word_len - 1)
            return f"{first}{blanks} ({word_len})"

        elif hint_type == "char_count":
            # "_____ (5)"
            blanks = "_" * word_len
            return f"{blanks} ({word_len})"

        else:  # none
            # "_____"
            return "_" * word_len

    def select_gaps(
        self,
        doc,
        target_count: int,
        min_zipf: float = 0.0,
        target_pos: set = None,
    ) -> List[Dict]:
        """
        Select words to be gaps based on difficulty config.

        Returns: List of gap dictionaries
        """
        # Find all candidate tokens
        candidates = []

        for i, token in enumerate(doc):
            if self.is_valid_gap_word(token, min_zipf, target_pos):
                difficulty = self.calculate_word_difficulty(token.text)

                candidates.append(
                    {
                        "position": i,
                        "word": token.text,
                        "pos": token.pos_,
                        "difficulty": difficulty,
                        "lemma": token.lemma_,
                        "char_count": len(token.text),
                    }
                )

        # If not enough candidates, return what we have
        if len(candidates) < target_count:
            return candidates

        # Sort by difficulty (easier words first for easy level)
        if min_zipf > 3.0:  # Easy level
            candidates.sort(key=lambda x: x["difficulty"])
        else:  # Medium/Hard levels
            candidates.sort(key=lambda x: -x["difficulty"])

        # Distribute gaps evenly throughout text
        total_tokens = len(doc)
        selected = []

        # Calculate ideal spacing
        num_gaps = min(target_count, len(candidates))
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

        # Sort by position for final output
        selected.sort(key=lambda x: x["position"])

        return selected[:target_count]

    def create_text_with_gaps(self, text: str, gaps: List[Dict], hint_type: str) -> str:
        """Replace gap words with hints."""
        doc = self.nlp(text)

        # Create lookup for gap positions
        gap_positions = {g["position"]: g for g in gaps}

        # Rebuild text with gaps
        result = []
        for i, token in enumerate(doc):
            if i in gap_positions:
                gap = gap_positions[i]
                hint = self.create_hint(gap["word"], hint_type)
                result.append(hint)
            else:
                result.append(token.text_with_ws)

        return "".join(result)

    def create_dialogue_with_gaps(
        self, conversation: Dict, gaps: List[Dict], hint_type: str
    ) -> List[Dict]:
        """Create dialogue turns with gaps embedded in each turn's text."""
        dialogue_with_gaps = []

        # Get dialogue turns
        dialogue = conversation.get("dialogue", [])

        # Build full text to track cumulative character positions
        full_text = self.extract_full_text(conversation)
        full_doc = self.nlp(full_text)

        # Create gap lookup by actual word text and position
        gap_words = {}
        for g in gaps:
            gap_words[g["position"]] = {
                "word": g["word"],
                "hint": self.create_hint(g["word"], hint_type),
            }

        # Process each dialogue turn
        token_offset = 0

        for turn in dialogue:
            speaker = turn.get("speaker", "Unknown")
            original_text = turn.get("text_en", "").strip()  # Use text_en from database

            if not original_text:
                dialogue_with_gaps.append(
                    {
                        "speaker": speaker,
                        "text": original_text,
                        "text_with_gaps": original_text,
                    }
                )
                continue

            # Process this turn's tokens
            turn_doc = self.nlp(original_text)

            # Build text with gaps for this turn
            result = []
            for i, token in enumerate(turn_doc):
                global_pos = token_offset + i

                if global_pos in gap_words:
                    # Preserve whitespace after hint
                    hint = gap_words[global_pos]["hint"]
                    # Add trailing whitespace from original token
                    if token.whitespace_:
                        hint += token.whitespace_
                    result.append(hint)
                else:
                    result.append(token.text_with_ws)

            text_with_gaps = "".join(result).strip()

            dialogue_with_gaps.append(
                {
                    "speaker": speaker,
                    "text": original_text,
                    "text_with_gaps": text_with_gaps,
                }
            )

            # Update offset for next turn
            token_offset += len(turn_doc)

        return dialogue_with_gaps

    def generate_gaps_for_conversation(
        self, conversation: Dict, difficulty: str
    ) -> Optional[Dict]:
        """
        Generate gap-fill exercise for one conversation at specified difficulty.

        Args:
            conversation: Conversation document from conversation_library
            difficulty: Difficulty level ("easy"/"medium"/"hard")

        Returns: Gap document dict or None if generation failed
        """
        # Extract full text
        full_text = self.extract_full_text(conversation)
        if not full_text or len(full_text) < 50:
            return None

        # Get difficulty config
        config = self.difficulty_configs[difficulty]

        # Process text with spaCy
        doc = self.nlp(full_text)

        # Calculate target gap count based on percentage
        total_words = len([t for t in doc if t.is_alpha])
        target_count = int(total_words * config["percentage"])

        if target_count < 3:  # Minimum 3 gaps
            target_count = 3

        # Select gaps
        gaps = self.select_gaps(
            doc,
            target_count=target_count,
            min_zipf=config["min_zipf"],
            target_pos=config["target_pos"],
        )

        if len(gaps) < 3:
            return None  # Not enough valid gaps

        # Create text with gaps
        text_with_gaps = self.create_text_with_gaps(
            full_text, gaps, config["hint_type"]
        )

        # Create dialogue with gaps (structured by turns)
        dialogue_with_gaps = self.create_dialogue_with_gaps(
            conversation, gaps, config["hint_type"]
        )

        # Create gap definitions
        gap_definitions = []
        for idx, g in enumerate(gaps, start=1):
            hint = self.create_hint(g["word"], config["hint_type"])
            gap_definitions.append(
                {
                    "gap_number": idx,
                    "correct_answer": g["word"].lower(),
                    "hint": hint,
                    "pos_tag": g["pos"],
                    "difficulty_score": g["difficulty"],
                }
            )

        # Calculate average difficulty
        avg_difficulty = round(sum(g["difficulty"] for g in gaps) / len(gaps), 2)

        # Create gap document
        return {
            "gap_id": f"gap_{conversation['conversation_id']}_{difficulty}",
            "conversation_id": conversation["conversation_id"],
            "difficulty": difficulty,
            "text_with_gaps": text_with_gaps,  # Full text with gaps (legacy)
            "dialogue_with_gaps": dialogue_with_gaps,  # Structured dialogue turns
            "gap_definitions": gap_definitions,
            "gap_count": len(gap_definitions),
            "avg_difficulty_score": avg_difficulty,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

    def process_conversation(self, conversation_id: str) -> int:
        """
        Process one conversation: generate gaps for all 3 difficulty levels.

        Returns: Number of gap documents created (0-3)
        """
        # Fetch conversation
        conversation = self.conv_library_col.find_one(
            {"conversation_id": conversation_id}
        )
        if not conversation:
            return 0

        # Generate gaps for all 3 difficulties
        created = 0
        for difficulty in ["easy", "medium", "hard"]:
            # Check if already exists
            existing = self.conv_gaps_col.find_one(
                {"conversation_id": conversation_id, "difficulty": difficulty}
            )
            if existing:
                continue

            # Generate gaps
            gaps_doc = self.generate_gaps_for_conversation(conversation, difficulty)

            if gaps_doc:
                # Insert to database
                self.conv_gaps_col.insert_one(gaps_doc)
                created += 1

        return created


async def main():
    """Main execution function."""
    print("=" * 80)
    print("🎯 GENERATE CONVERSATION GAP-FILL EXERCISES")
    print("=" * 80)

    generator = ConversationGapGenerator()

    # Get all conversations
    conversations = list(generator.conv_library_col.find({}, {"conversation_id": 1}))
    total_conversations = len(conversations)

    print(f"\n📊 Total conversations: {total_conversations}")

    # Check existing gaps
    existing_gaps = generator.conv_gaps_col.count_documents({})
    print(f"📚 Existing gaps: {existing_gaps}")

    # Calculate how many conversations already have gaps
    conversations_with_gaps = len(generator.conv_gaps_col.distinct("conversation_id"))
    need_generation = total_conversations - conversations_with_gaps

    print(f"🆕 Need generation: {need_generation} conversations")

    if need_generation == 0:
        print("\n✅ All conversations already have gaps!")
        return

    # Process conversations
    print(f"\n🚀 Processing {need_generation} conversations...")
    print("   Generating 3 difficulty levels per conversation...")

    created_total = 0
    failed = 0

    with tqdm(total=need_generation, desc="Processing") as pbar:
        for conv in conversations:
            conversation_id = conv["conversation_id"]

            # Skip if already has gaps
            has_gaps = generator.conv_gaps_col.count_documents(
                {"conversation_id": conversation_id}
            )
            if has_gaps >= 3:
                continue

            # Generate gaps
            created = generator.process_conversation(conversation_id)
            created_total += created

            if created < 3:
                failed += 1

            pbar.update(1)
            pbar.set_postfix({"created": created_total, "failed": failed})

    print("\n" + "=" * 80)
    print("📊 GENERATION COMPLETE")
    print("=" * 80)
    print(f"✅ Created: {created_total} gap documents")
    print(f"❌ Failed: {failed} conversations")
    print(f"📈 Success rate: {(1 - failed / need_generation) * 100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
