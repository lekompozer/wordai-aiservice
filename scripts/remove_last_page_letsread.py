#!/usr/bin/env python3
"""
Remove the last page (LetsRead promo page) from existing LetsRead books
that were crawled before the auto-strip logic was added.

Usage:
    python3 remove_last_page_letsread.py [--dry-run] [--book-id <id>]
"""

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

from src.database.db_manager import DBManager


def remove_last_page_for_book(
    db, book_id: str, title: str, dry_run: bool = False
) -> bool:
    """Find and delete the last page of a book in book_page_texts. Returns True if deleted."""
    # Find all pages for this book, sorted by page_number
    pages = list(
        db.book_page_texts.find(
            {"book_id": book_id, "language": "en"},
            {"_id": 1, "page_number": 1, "text": 1},
        )
        .sort("page_number", -1)
        .limit(1)
    )

    if not pages:
        log.warning(f"  ⚠️  No EN pages found for '{title}' (id={book_id})")
        return False

    last_page = pages[0]
    page_num = last_page.get("page_number", "?")
    text_preview = (last_page.get("text") or "")[:80].replace("\n", " ")

    log.info(f"  📄 Last page: page_number={page_num} | text: '{text_preview}...'")

    if dry_run:
        log.info(f"  [DRY-RUN] Would delete page_number={page_num}")
        return True

    result = db.book_page_texts.delete_one({"_id": last_page["_id"]})
    if result.deleted_count == 1:
        log.info(f"  ✅ Deleted last page (page_number={page_num})")
        return True
    else:
        log.error(f"  ❌ Delete failed for page_number={page_num}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Remove last (promo) page from LetsRead books"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview only, no DB writes"
    )
    parser.add_argument(
        "--book-id", help="Process only this specific book ID", default=None
    )
    args = parser.parse_args()

    db_manager = DBManager()
    db = db_manager.db

    if args.book_id:
        # Process single book
        book = db.online_books.find_one(
            {"_id": __import__("bson").ObjectId(args.book_id)}, {"title": 1}
        )
        if not book:
            log.error(f"Book {args.book_id} not found")
            sys.exit(1)
        books = [
            {
                "_id": book["_id"],
                "title": book.get("title", "?"),
                "id_str": args.book_id,
            }
        ]
    else:
        # Find all LetsRead books by source
        raw = list(
            db.online_books.find(
                {"metadata.source": "letsreadasia.org"},
                {"title": 1, "metadata.letsread_book_id": 1},
            )
        )
        books = [
            {"_id": b["_id"], "title": b.get("title", "?"), "id_str": str(b["_id"])}
            for b in raw
        ]

    log.info(
        f"{'[DRY-RUN] ' if args.dry_run else ''}Processing {len(books)} letsread books..."
    )
    log.info("")

    removed = 0
    skipped = 0

    for book in books:
        book_id = book["id_str"]
        title = book["title"]

        # Count pages
        total_pages = db.book_page_texts.count_documents(
            {"book_id": book_id, "language": "en"}
        )
        log.info(f"📖 '{title}' (id={book_id[:12]}..., pages={total_pages})")

        if total_pages == 0:
            log.warning(f"  ⚠️  No pages — skipping")
            skipped += 1
            continue

        ok = remove_last_page_for_book(db, book_id, title, dry_run=args.dry_run)
        if ok:
            removed += 1
        else:
            skipped += 1

        log.info("")

    log.info("=" * 60)
    log.info(f"DONE: removed={removed}, skipped={skipped}")
    if args.dry_run:
        log.info("(dry-run — no changes made)")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
