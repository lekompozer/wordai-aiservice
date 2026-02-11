#!/usr/bin/env python3
"""
Validate quality of generated gap-fill exercises.
Checks: max 10 gaps, no profanity, difficulty distribution, score accuracy.

Phase 3-4: Gap Quality Validation
"""

import sys
import os
from collections import Counter, defaultdict
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
from src.models.song_models import DifficultyLevel, POSTag
from better_profanity import profanity


class GapQualityValidator:
    """Validate quality of gap-fill exercises."""

    def __init__(self):
        """Initialize DB connection."""
        self.db_manager = DBManager()
        self.db = self.db_manager.db

        self.song_lyrics_col = self.db["song_lyrics"]
        self.song_gaps_col = self.db["song_gaps"]

        # Load profanity filter
        profanity.load_censor_words()

    def check_required_fields(self, gap_doc: Dict) -> List[str]:
        """Check if gap document has all required fields."""
        required = [
            "gap_id",
            "song_id",
            "difficulty",
            "gaps",
            "lyrics_with_gaps",
            "gap_count",
            "avg_difficulty_score",
        ]

        missing = []
        for field in required:
            if field not in gap_doc or gap_doc[field] is None:
                missing.append(field)

        return missing

    def check_gap_items(self, gaps: List[Dict]) -> Dict[str, any]:
        """
        Validate individual gap items.

        Returns: Dict with validation results
        """
        issues = []
        pos_distribution = Counter()
        difficulty_scores = []

        for i, gap in enumerate(gaps):
            # Check required gap fields (matching new GapItem model)
            if "line_number" not in gap:
                issues.append(f"Gap {i}: Missing 'line_number'")
            if "word_index" not in gap:
                issues.append(f"Gap {i}: Missing 'word_index'")
            if "original_word" not in gap:
                issues.append(f"Gap {i}: Missing 'original_word'")
            if "lemma" not in gap:
                issues.append(f"Gap {i}: Missing 'lemma'")
            if "pos_tag" not in gap:
                issues.append(f"Gap {i}: Missing 'pos_tag'")
            if "difficulty_score" not in gap:
                issues.append(f"Gap {i}: Missing 'difficulty_score'")
                continue
            if "char_count" not in gap:
                issues.append(f"Gap {i}: Missing 'char_count'")

            # Check word validity
            word = gap.get("original_word", "")
            if not word:
                issues.append(f"Gap {i}: Empty original_word")
            elif not word.replace(" ", "").isalpha():
                issues.append(f"Gap {i}: Word '{word}' contains non-alphabetic chars")

            # Check for profanity
            if profanity.contains_profanity(word):
                issues.append(f"Gap {i}: Word '{word}' contains profanity")

            # Track POS distribution
            pos_tag = gap.get("pos_tag", "UNKNOWN")
            pos_distribution[pos_tag] += 1

            # Track difficulty scores
            difficulty = gap.get("difficulty_score")
            if difficulty is not None:
                difficulty_scores.append(difficulty)
                if difficulty < 0 or difficulty > 10:
                    issues.append(
                        f"Gap {i}: Difficulty {difficulty} out of range [0-10]"
                    )

        return {
            "issues": issues,
            "pos_distribution": dict(pos_distribution),
            "difficulty_scores": difficulty_scores,
            "avg_difficulty": (
                round(sum(difficulty_scores) / len(difficulty_scores), 2)
                if difficulty_scores
                else 0
            ),
        }

    def validate_document(self, gap_doc: Dict) -> Dict[str, any]:
        """
        Validate a single gap document.

        Returns: Dict with validation results
        """
        result = {
            "song_id": gap_doc.get("song_id", "UNKNOWN"),
            "difficulty": gap_doc.get("difficulty", "UNKNOWN"),
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        # Check required fields
        missing_fields = self.check_required_fields(gap_doc)
        if missing_fields:
            result["is_valid"] = False
            result["errors"].append(f"Missing fields: {', '.join(missing_fields)}")
            return result

        # Check gap count
        gap_count = gap_doc.get("gap_count", 0)
        actual_gaps = len(gap_doc.get("gaps", []))

        if gap_count != actual_gaps:
            result["warnings"].append(
                f"Gap count mismatch: {gap_count} vs {actual_gaps} actual"
            )

        if gap_count > 20:
            result["errors"].append(f"Too many gaps: {gap_count} (max 20)")
            result["is_valid"] = False

        if gap_count < 1:
            result["errors"].append(f"No gaps generated")
            result["is_valid"] = False

        # Check difficulty-specific gap counts
        difficulty = gap_doc.get("difficulty")
        if difficulty == DifficultyLevel.EASY.value:
            if gap_count < 8 or gap_count > 10:
                result["warnings"].append(
                    f"Easy should have 8-10 gaps, got {gap_count}"
                )
        elif difficulty == DifficultyLevel.MEDIUM.value:
            if gap_count < 12 or gap_count > 15:
                result["warnings"].append(
                    f"Medium should have 12-15 gaps, got {gap_count}"
                )
        elif difficulty == DifficultyLevel.HARD.value:
            if gap_count < 15 or gap_count > 20:
                result["warnings"].append(
                    f"Hard should have 15-20 gaps, got {gap_count}"
                )

        # Validate gap items
        gap_validation = self.check_gap_items(gap_doc.get("gaps", []))

        if gap_validation["issues"]:
            result["errors"].extend(gap_validation["issues"])
            result["is_valid"] = False

        result["stats"] = {
            "gap_count": gap_count,
            "pos_distribution": gap_validation["pos_distribution"],
            "avg_difficulty_score": gap_validation["avg_difficulty"],
            "declared_avg_difficulty": gap_doc.get("avg_difficulty_score", 0),
        }

        # Check if declared avg matches calculated
        declared_avg = gap_doc.get("avg_difficulty_score", 0)
        calculated_avg = gap_validation["avg_difficulty"]
        if abs(declared_avg - calculated_avg) > 0.1:
            result["warnings"].append(
                f"Avg difficulty mismatch: declared {declared_avg} vs calculated {calculated_avg}"
            )

        # Check lyrics_with_gaps has the right number of ___
        lyrics_with_gaps = gap_doc.get("lyrics_with_gaps", "")
        blank_count = lyrics_with_gaps.count("___")
        if blank_count != gap_count:
            result["errors"].append(
                f"Lyrics has {blank_count} blanks (___) but gap_count is {gap_count}"
            )
            result["is_valid"] = False

        return result

    def run_validation(self, sample_size: int = None) -> Dict:
        """
        Run validation on all (or sample of) gap documents.

        Args:
            sample_size: If provided, validate only this many random documents

        Returns: Validation report
        """
        print("=" * 70)
        print("🔍 GAP QUALITY VALIDATION")
        print("=" * 70)
        print()

        # Get gap documents
        total_gaps = self.song_gaps_col.count_documents({})
        print(f"📊 Total gap documents: {total_gaps}")

        if total_gaps == 0:
            print("❌ No gap documents found!")
            return {"total": 0, "valid": 0, "invalid": 0}

        # Sample if requested
        if sample_size and sample_size < total_gaps:
            print(f"🎲 Sampling {sample_size} random documents...")
            gap_docs = list(
                self.song_gaps_col.aggregate([{"$sample": {"size": sample_size}}])
            )
        else:
            gap_docs = list(self.song_gaps_col.find({}))

        print(f"✅ Validating {len(gap_docs)} documents...")
        print()

        # Validate each document
        results = []
        difficulty_stats = defaultdict(
            lambda: {
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "avg_gaps": [],
                "pos_distributions": [],
            }
        )

        for gap_doc in gap_docs:
            validation = self.validate_document(gap_doc)
            results.append(validation)

            difficulty = validation["difficulty"]
            difficulty_stats[difficulty]["total"] += 1

            if validation["is_valid"]:
                difficulty_stats[difficulty]["valid"] += 1
                difficulty_stats[difficulty]["avg_gaps"].append(
                    validation["stats"]["gap_count"]
                )
                difficulty_stats[difficulty]["pos_distributions"].append(
                    validation["stats"]["pos_distribution"]
                )
            else:
                difficulty_stats[difficulty]["invalid"] += 1

        # Calculate summary statistics
        total_valid = sum(1 for r in results if r["is_valid"])
        total_invalid = len(results) - total_valid

        print("=" * 70)
        print("📊 VALIDATION SUMMARY")
        print("=" * 70)
        print()
        print(
            f"✅ Valid documents: {total_valid}/{len(results)} ({total_valid/len(results)*100:.1f}%)"
        )
        print(
            f"❌ Invalid documents: {total_invalid}/{len(results)} ({total_invalid/len(results)*100:.1f}%)"
        )
        print()

        # Per-difficulty statistics
        print("=" * 70)
        print("📈 DIFFICULTY BREAKDOWN")
        print("=" * 70)
        print()

        for difficulty in [
            DifficultyLevel.EASY.value,
            DifficultyLevel.MEDIUM.value,
            DifficultyLevel.HARD.value,
        ]:
            stats = difficulty_stats[difficulty]
            if stats["total"] == 0:
                continue

            print(f"🎯 {difficulty.upper()}:")
            print(f"   Total: {stats['total']}")
            print(
                f"   Valid: {stats['valid']} ({stats['valid']/stats['total']*100:.1f}%)"
            )
            print(f"   Invalid: {stats['invalid']}")

            if stats["avg_gaps"]:
                avg_gap_count = sum(stats["avg_gaps"]) / len(stats["avg_gaps"])
                print(f"   Avg gap count: {avg_gap_count:.1f}")

                # Aggregate POS distribution
                pos_total = Counter()
                for pos_dist in stats["pos_distributions"]:
                    pos_total.update(pos_dist)

                print(f"   POS distribution:")
                for pos, count in pos_total.most_common():
                    pct = count / sum(pos_total.values()) * 100
                    print(f"      {pos}: {count} ({pct:.1f}%)")

            print()

        # Show sample errors
        invalid_samples = [r for r in results if not r["is_valid"]][:5]
        if invalid_samples:
            print("=" * 70)
            print("⚠️  SAMPLE ERRORS (first 5)")
            print("=" * 70)
            print()

            for i, sample in enumerate(invalid_samples, 1):
                print(
                    f"{i}. Song: {sample['song_id']}, Difficulty: {sample['difficulty']}"
                )
                for error in sample["errors"][:3]:  # Show first 3 errors
                    print(f"   ❌ {error}")
                print()

        # Quality score
        quality_score = round(total_valid / len(results) * 100) if results else 0

        print("=" * 70)
        print(f"🏆 QUALITY SCORE: {quality_score}/100")
        print("=" * 70)
        print()

        return {
            "total": len(results),
            "valid": total_valid,
            "invalid": total_invalid,
            "quality_score": quality_score,
            "difficulty_stats": dict(difficulty_stats),
        }


def main():
    """Main entry point."""
    validator = GapQualityValidator()

    # Check if we should sample
    import sys

    sample_size = None
    if len(sys.argv) > 1:
        try:
            sample_size = int(sys.argv[1])
            print(f"🎲 Using sample size: {sample_size}")
        except ValueError:
            print("⚠️  Invalid sample size, validating all documents")

    validator.run_validation(sample_size=sample_size)


if __name__ == "__main__":
    main()
