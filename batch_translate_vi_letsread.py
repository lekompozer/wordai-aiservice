#!/usr/bin/env python3
"""
Batch translate EN→VI for all LetsRead books missing VI page_texts.
Uses DeepSeek via BookPageAudioService.translate_pages_to_vi().

Usage:
    python3 batch_translate_vi_letsread.py
    python3 batch_translate_vi_letsread.py --from-index 50
    python3 batch_translate_vi_letsread.py --dry-run
"""

import asyncio
import sys
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description="Batch VI translation for LetsRead books"
    )
    parser.add_argument(
        "--from-index", type=int, default=0, help="Start from book index (0-based)"
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Max books to process (0=all)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-translate even if VI pages exist"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview only, no writes"
    )
    args = parser.parse_args()

    from src.services.book_page_audio_service import BookPageAudioService
    from src.database.db_manager import DBManager

    db_manager = DBManager()
    db = db_manager.db
    svc = BookPageAudioService()
    # Inject the single shared db_manager into service to avoid per-call reconnects
    BookPageAudioService._db_manager = db_manager

    # All letsread books ordered by created_at (same order as audio batch)
    books = list(
        db.online_books.find(
            {"metadata.source": "letsreadasia.org"}, {"title": 1, "created_at": 1}
        ).sort("created_at", 1)
    )

    total = len(books)
    log.info(f"Total LetsRead books: {total}")
    log.info(
        f"From index: {args.from_index} | Force: {args.force} | Dry-run: {args.dry_run}"
    )
    log.info("")

    stats = {"translated": 0, "skipped": 0, "err": 0}
    processed = 0

    for i, book in enumerate(books):
        if i < args.from_index:
            continue

        book_id = str(book["_id"])
        title = book.get("title", "?")

        # Check VI pages
        vi_count = db.book_page_texts.count_documents(
            {"book_id": book_id, "language": "vi"}
        )
        en_count = db.book_page_texts.count_documents(
            {"book_id": book_id, "language": "en"}
        )

        if vi_count > 0 and not args.force:
            log.info(
                f"[{i+1}/{total}] ⏭️  Skip '{title}' — VI already has {vi_count} pages"
            )
            stats["skipped"] += 1
            processed += 1
            if args.limit and processed >= args.limit:
                break
            continue

        if en_count == 0:
            log.warning(f"[{i+1}/{total}] ⚠️  Skip '{title}' — no EN pages found")
            stats["err"] += 1
            processed += 1
            if args.limit and processed >= args.limit:
                break
            continue

        log.info(
            f"[{i+1}/{total}] 🌐 Translating '{title}' ({en_count} EN pages → VI)..."
        )

        if args.dry_run:
            log.info(f"         [DRY-RUN] Would translate {en_count} pages")
            stats["skipped"] += 1
            processed += 1
            if args.limit and processed >= args.limit:
                break
            continue

        try:
            result = await svc.translate_pages_to_vi(book_id, force=args.force)
            saved = result.get("saved", 0)
            log.info(f"         ✅ Saved {saved} VI pages")
            stats["translated"] += 1
        except Exception as e:
            log.error(f"         ❌ Error: {e}")
            stats["err"] += 1

        processed += 1
        if args.limit and processed >= args.limit:
            log.info(f"\n⏹️  Reached limit of {args.limit} books")
            break

        log.info("")

    log.info("=" * 60)
    log.info("DONE")
    log.info(f"  Translated : {stats['translated']}")
    log.info(f"  Skipped    : {stats['skipped']}")
    log.info(f"  Errors     : {stats['err']}")
    log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
