"""
LetsRead Page Crawler
Fetches per-page text + image data from letsreadasia.org REST API.

NO Selenium needed — the Preview API returns all pages at once:
  GET https://letsreadasia.org/api/v5/book/preview/language/{lang_id}/book/{book_uuid}

Key field names discovered from API:
  - extractedLongContentValue : page text
  - pageNum                   : page number as string (cover = "1", story starts at "2")
  - imageUrl                  : GCS image URL
  - thumborImageUrl            : CDN image URL (hamropatro)
  - imageServingUrl            : high-res image (lh3.googleusercontent.com)
  - audio                     : audio field (usually null / empty)

Usage:
    python crawler/letsread_page_crawler.py                    -- crawl all 4 books
    python crawler/letsread_page_crawler.py --book-id <id>    -- crawl one book
    python crawler/letsread_page_crawler.py --dry-run         -- print pages, don't save
"""

import sys
import os
import requests
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LETSREAD_PREVIEW_API = (
    "https://letsreadasia.org/api/v5/book/preview/language/{lang_id}/book/{book_uuid}"
)
LETSREAD_TAG_API = (
    "https://letsreadasia.org/api/tag/get-books/{cat_id}?limit=20&lId={lang_id}&cursor="
)

DEFAULT_LANG_ID = "4846240843956224"  # English
DEFAULT_LANG_CODE = "en"

# Fixed headers to avoid bot-detection
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://letsreadasia.org/",
    "Origin": "https://letsreadasia.org",
}

# Known masterBookIds for the 4 books already in DB
# These were discovered via Chrome DevTools network capture
KNOWN_BOOKS = [
    {
        "title": "The Protectors",
        "letsread_book_id": "61b2f862-f64b-443b-9f6c-73f71024b538",
        "letsread_lang_id": DEFAULT_LANG_ID,
        "lang_code": DEFAULT_LANG_CODE,
    },
    {
        "title": "The Spirit of Ocean Nights",
        "letsread_book_id": "eb4d3602-f4fb-4cae-a574-a838980af834",
        "letsread_lang_id": DEFAULT_LANG_ID,
        "lang_code": DEFAULT_LANG_CODE,
    },
    {
        "title": "Roots Are Stronger Than Steel",
        "letsread_book_id": "617336b6-6033-4a2d-9ac9-72587cb75574",
        "letsread_lang_id": DEFAULT_LANG_ID,
        "lang_code": DEFAULT_LANG_CODE,
    },
    {
        "title": "Children of the Sun and Stars",
        "letsread_book_id": "830e07c9-9c5e-4c12-9f5a-b2e538554be1",
        "letsread_lang_id": DEFAULT_LANG_ID,
        "lang_code": DEFAULT_LANG_CODE,
    },
]


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def fetch_book_pages(
    book_uuid: str,
    lang_id: str = DEFAULT_LANG_ID,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Fetch full page data for a book from the LetsRead Preview API.

    Returns the full API response dict with keys:
        totalPages, pages, epubUrl, hasAudio, ...
    """
    url = LETSREAD_PREVIEW_API.format(lang_id=lang_id, book_uuid=book_uuid)
    logger.info(f"Fetching: {url}")
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def parse_page(raw: Dict[str, Any], story_page_index: int) -> Dict[str, Any]:
    """
    Convert a raw API page object to our internal format.

    Args:
        raw            : single page dict from API pages array
        story_page_index: 0-based index among story pages (cover excluded)

    Returns:
        Normalized page dict
    """
    # pageNum is a string like "2" (cover = "1", story starts at "2")
    page_num_raw = raw.get("pageNum", "")
    try:
        page_num_int = int(page_num_raw)
    except (ValueError, TypeError):
        page_num_int = story_page_index + 1  # fallback

    return {
        # Our 1-based story page number (cover excluded)
        "page_number": story_page_index + 1,
        # Native pageNum from API (cover = 1, story page 1 = 2, etc.)
        "api_page_num": page_num_int,
        "text_content": raw.get("extractedLongContentValue") or "",
        # Best-quality image URL chain: GCS > CDN > hi-res
        "image_url": (
            raw.get("imageUrl")
            or raw.get("thumborImageUrl")
            or raw.get("imageServingUrl")
            or ""
        ),
        "image_url_hires": raw.get("imageServingUrl") or "",
        "image_url_cdn": raw.get("thumborImageUrl") or "",
        "image_name": raw.get("imageName") or "",
        "image_width": int(raw.get("imageWidth") or 0),
        "image_height": int(raw.get("imageHeight") or 0),
        "has_audio": bool(raw.get("audio")),
        "letsread_page_id": raw.get("id") or "",
    }


def extract_story_pages(api_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Filter out the cover page and return only story pages, normalized.

    LetsRead pageNum "1" is usually the title/cover page without story text.
    We skip it and renumber remaining pages starting at 1.
    """
    raw_pages = api_data.get("pages") or []
    story_pages = []
    story_idx = 0

    for raw in raw_pages:
        page_num_str = str(raw.get("pageNum", ""))
        # Skip cover (pageNum = "1") — typically no story text
        if page_num_str == "1":
            logger.debug(f"  Skipping cover page (pageNum=1)")
            continue

        parsed = parse_page(raw, story_idx)
        story_pages.append(parsed)
        story_idx += 1

    return story_pages


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def find_online_book(db, title_hint: str) -> Optional[Dict[str, Any]]:
    """
    Find an online_books document by title (case-insensitive partial match).
    """
    import re

    pattern = re.compile(re.escape(title_hint), re.IGNORECASE)
    book = db.online_books.find_one({"title": {"$regex": pattern}})
    return book


def save_pages_to_db(
    db,
    book_id: str,
    letsread_book_id: str,
    letsread_lang_id: str,
    lang_code: str,
    pages: List[Dict[str, Any]],
    force: bool = False,
) -> int:
    """
    Upsert pages into the book_page_texts collection.

    Returns number of pages saved/updated.
    """
    saved = 0
    for page in pages:
        doc = {
            "book_id": book_id,
            "letsread_book_id": letsread_book_id,
            "letsread_lang_id": letsread_lang_id,
            "language": lang_code,
            **page,
            "updated_at": datetime.utcnow(),
        }
        filter_q = {"book_id": book_id, "page_number": page["page_number"]}

        if force:
            db.book_page_texts.replace_one(filter_q, doc, upsert=True)
        else:
            # Only set if not already present
            existing = db.book_page_texts.find_one(filter_q)
            if existing:
                logger.debug(
                    f"  Page {page['page_number']} already exists, skipping (use --force to overwrite)"
                )
                continue
            doc["created_at"] = datetime.utcnow()
            db.book_page_texts.insert_one(doc)

        saved += 1

    return saved


def update_online_book_metadata(
    db,
    book_id: str,
    letsread_book_id: str,
    letsread_lang_id: str,
    total_pages: int,
) -> None:
    """
    Update online_books with letsread IDs and page count.
    """
    db.online_books.update_one(
        {"_id": __import__("bson").ObjectId(book_id)},
        {
            "$set": {
                "metadata.letsread_book_id": letsread_book_id,
                "metadata.letsread_lang_id": letsread_lang_id,
                "metadata.has_page_texts": True,
                "metadata.total_pages": total_pages,
                "updated_at": datetime.utcnow(),
            }
        },
    )


# ---------------------------------------------------------------------------
# Main crawler logic
# ---------------------------------------------------------------------------


def crawl_book(
    db,
    book_meta: Dict[str, Any],
    force: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Crawl a single book and optionally save to DB.

    Returns a result summary dict.
    """
    title = book_meta["title"]
    letsread_book_id = book_meta["letsread_book_id"]
    letsread_lang_id = book_meta.get("letsread_lang_id", DEFAULT_LANG_ID)
    lang_code = book_meta.get("lang_code", DEFAULT_LANG_CODE)

    logger.info(f"\n{'='*60}")
    logger.info(f"Book: {title}")
    logger.info(f"UUID: {letsread_book_id}")

    # Fetch pages from API
    try:
        api_data = fetch_book_pages(letsread_book_id, lang_id=letsread_lang_id)
    except requests.HTTPError as e:
        logger.error(f"  API error for {title}: {e}")
        return {"title": title, "status": "error", "error": str(e)}

    story_pages = extract_story_pages(api_data)
    total_pages = len(story_pages)
    logger.info(
        f"  API totalPages: {api_data.get('totalPages')} | story pages: {total_pages}"
    )

    if dry_run:
        for p in story_pages[:3]:
            text_preview = (p["text_content"] or "")[:60]
            logger.info(
                f"  [DRY] Page {p['page_number']}: {text_preview!r} | img: {p['image_url'][:50]}"
            )
        logger.info(f"  [DRY] ... ({total_pages} pages total, not saved)")
        return {"title": title, "status": "dry_run", "total_pages": total_pages}

    # Find corresponding online_books document
    online_book = find_online_book(db, title)
    if not online_book:
        logger.warning(
            f"  ⚠️  online_books entry not found for '{title}' — saving pages without book_id"
        )
        book_id = letsread_book_id  # use letsread UUID as fallback
    else:
        book_id = str(online_book["_id"])
        logger.info(f"  Found online_books entry: {book_id}")

    # Save pages
    saved = save_pages_to_db(
        db=db,
        book_id=book_id,
        letsread_book_id=letsread_book_id,
        letsread_lang_id=letsread_lang_id,
        lang_code=lang_code,
        pages=story_pages,
        force=force,
    )

    # Update online_books metadata
    if online_book:
        update_online_book_metadata(
            db=db,
            book_id=book_id,
            letsread_book_id=letsread_book_id,
            letsread_lang_id=letsread_lang_id,
            total_pages=total_pages,
        )
        logger.info(f"  Updated online_books metadata")

    logger.info(f"  ✅ Saved {saved}/{total_pages} pages to book_page_texts")
    return {
        "title": title,
        "status": "ok",
        "book_id": book_id,
        "total_pages": total_pages,
        "saved": saved,
        "letsread_book_id": letsread_book_id,
    }


def crawl_all(
    books: Optional[List[Dict[str, Any]]] = None,
    force: bool = False,
    dry_run: bool = False,
    target_book_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Crawl all (or a specific subset of) LetsRead books.

    Args:
        books         : list of book metadata dicts (defaults to KNOWN_BOOKS)
        force         : overwrite existing page records
        dry_run       : print pages without saving
        target_book_id: online_books _id to restrict crawl to one book

    Returns:
        List of per-book result summaries
    """
    books = books or KNOWN_BOOKS
    db_manager = DBManager()
    db = db_manager.db

    results = []
    for book_meta in books:
        # If --book-id specified, filter by matching online_books ID or title
        if target_book_id:
            online_book = find_online_book(db, book_meta["title"])
            if not online_book or str(online_book["_id"]) != target_book_id:
                continue

        result = crawl_book(db, book_meta, force=force, dry_run=dry_run)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Crawl LetsRead book pages via REST API"
    )
    parser.add_argument(
        "--book-id",
        help="Only crawl the book with this online_books _id",
        default=None,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing page records in DB",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print pages without saving to DB",
    )
    args = parser.parse_args()

    results = crawl_all(
        force=args.force,
        dry_run=args.dry_run,
        target_book_id=args.book_id,
    )

    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(results)} book(s) processed")
    for r in results:
        status = r.get("status", "?")
        pages = r.get("total_pages", "-")
        saved = r.get("saved", "-")
        title = r.get("title", "?")
        if status == "error":
            print(f"  ❌ {title}: {r.get('error')}")
        elif status == "dry_run":
            print(f"  🔍 {title}: {pages} pages (dry run)")
        else:
            print(f"  ✅ {title}: {saved}/{pages} pages saved")


if __name__ == "__main__":
    main()
