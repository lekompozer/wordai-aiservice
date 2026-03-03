#!/usr/bin/env python3
"""
Batch audio generator for all LetsRead books.
Generates EN + VI audio for each book, alternating between Aoede (female) and Algenib (male) voices.

Voice assignment: book index 0, 2, 4... → Aoede | 1, 3, 5... → Algenib

Usage:
    # Generate both EN + VI for all books (skip already done)
    python3 generate_audio_batch_letsread.py

    # Only English
    python3 generate_audio_batch_letsread.py --lang en

    # Only Vietnamese
    python3 generate_audio_batch_letsread.py --lang vi

    # Resume from book index 50 (0-based)
    python3 generate_audio_batch_letsread.py --from-index 50

    # Force regenerate even if audio exists
    python3 generate_audio_batch_letsread.py --force

    # Dry-run: show what would be generated
    python3 generate_audio_batch_letsread.py --dry-run

    # Limit to N books (for testing)
    python3 generate_audio_batch_letsread.py --limit 5
"""

import asyncio
import sys
import argparse
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

VOICES = ["Aoede", "Algenib"]  # index % 2: 0 → Aoede, 1 → Algenib


async def generate_audio_for_book(
    svc,
    book_id: str,
    voice: str,
    language: str,
    force: bool = False,
    dry_run: bool = False,
) -> str:
    """Generate audio for one book+language. Returns 'ok', 'skip', or 'err'."""
    try:
        # Check if already exists
        if not force:
            existing = svc.get_latest_audio(book_id, voice, language=language)
            if existing and existing.get("status") == "completed":
                log.info(f"    ⏭️  [{language.upper()}] Already done (voice={voice})")
                return "skip"

        if dry_run:
            log.info(f"    [DRY-RUN] Would generate: lang={language}, voice={voice}")
            return "skip"

        log.info(f"    🎙️  [{language.upper()}] Generating (voice={voice})...")
        job_id = await svc.generate_book_audio(book_id, voice, language=language)

        db = svc._get_db()
        doc = db.book_page_audio.find_one({"job_id": job_id})
        if doc and doc.get("status") == "completed":
            dur_s = (doc.get("total_duration_ms") or 0) / 1000
            pages = len(doc.get("page_timestamps") or [])
            log.info(f"    ✅ [{language.upper()}] Done — {dur_s:.1f}s, {pages} pages")
            return "ok"
        else:
            status = (doc or {}).get("status", "not_found")
            err = (doc or {}).get("error_message", "")
            log.error(f"    ❌ [{language.upper()}] Failed: status={status} err={err}")
            return "err"

    except Exception as e:
        log.error(f"    ❌ [{language.upper()}] Exception: {e}")
        return "err"


async def main():
    parser = argparse.ArgumentParser(description="Batch audio generator for LetsRead books")
    parser.add_argument("--lang", choices=["en", "vi", "both"], default="both",
                        help="Which language(s) to generate (default: both)")
    parser.add_argument("--from-index", type=int, default=0,
                        help="Start from this book index (0-based, for resuming)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max number of books to process (0 = all)")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate audio even if already exists")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, no audio generation")
    args = parser.parse_args()

    languages = ["en", "vi"] if args.lang == "both" else [args.lang]

    from src.services.book_page_audio_service import BookPageAudioService
    from src.database.db_manager import DBManager

    db_manager = DBManager()
    db = db_manager.db
    svc = BookPageAudioService()

    # Get all letsread books, ordered by created_at (oldest first → consistent voice assignment)
    books = list(db.online_books.find(
        {"metadata.source": "letsreadasia.org"},
        {"title": 1, "created_at": 1}
    ).sort("created_at", 1))

    total = len(books)
    log.info(f"Found {total} LetsRead books")
    log.info(f"Languages: {languages} | From index: {args.from_index} | Force: {args.force}")
    log.info("")

    stats = {"ok": 0, "skip": 0, "err": 0}
    processed = 0

    for i, book in enumerate(books):
        if i < args.from_index:
            continue

        book_id = str(book["_id"])
        title = book.get("title", "?")
        voice = VOICES[i % 2]  # alternating: 0=Aoede, 1=Algenib

        log.info(f"[{i+1}/{total}] '{title}' | voice={voice}")

        for lang in languages:
            result = await generate_audio_for_book(
                svc, book_id, voice, lang,
                force=args.force,
                dry_run=args.dry_run,
            )
            stats[result] += 1

        processed += 1
        if args.limit and processed >= args.limit:
            log.info(f"\n⏹️  Reached limit of {args.limit} books")
            break

        log.info("")

    log.info("=" * 60)
    log.info(f"BATCH AUDIO COMPLETE")
    log.info(f"  Generated: {stats['ok']}")
    log.info(f"  Skipped:   {stats['skip']}")
    log.info(f"  Errors:    {stats['err']}")
    if args.dry_run:
        log.info("  (dry-run — no audio was generated)")
    log.info("=" * 60)


asyncio.run(main())
