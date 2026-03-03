"""
LetsRead Asia - Category Crawler (REST API only, no Selenium)
=============================================================
Crawls up to 100 books per category using cursor-based pagination from:
  GET https://letsreadasia.org/api/tag/get-books/{cat_id}?limit=20&lId={lang_id}&cursor=

For each book:
  - If already in DB (by masterBookId):  adds any new category tags
  - If new: downloads portrait PDF + cover → uploads to R2 → creates book+chapter →
            fetches pages via Preview API → saves (skipping cover + last promo page)

Usage:
    # Dry-run on one category (no DB writes)
    python crawler/letsread_category_crawler.py --dry-run --cat 5726225838374912

    # Real crawl of one category
    python crawler/letsread_category_crawler.py --cat 5726225838374912

    # All 15 categories (background / full run)
    python crawler/letsread_category_crawler.py

    # Preview pages only (already crawled books, re-fetch pages)
    python crawler/letsread_category_crawler.py --pages-only --cat 5726225838374912
"""

import os
import re
import sys
import time
import uuid
import logging
import requests
import boto3
from botocore.client import Config
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import quote

# -------------------------------------------------------------------
# Setup path + imports
# -------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env before DB init
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.database.db_manager import DBManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

LANG_ID = "4846240843956224"   # English

# 15 categories (deduplicated — 5728283396145152 appeared twice in the list)
CATEGORIES = [
    "5726225838374912",
    "5760672340115456",
    "5765598403362816",
    "5728125824532480",
    "5715808797851648",
    "5765734416252928",
    "5699190361423872",
    "5728283396145152",
    "5737789366730752",
    "5730992178331648",
    "5643342180253696",
    "5765642095427584",
    "5697992333983744",
    "5745057659355136",
]

MAX_BOOKS_PER_CATEGORY = 100
PAGE_SIZE = 20

TAG_API = "https://letsreadasia.org/api/tag/get-books/{cat_id}?limit={limit}&lId={lang_id}&cursor={cursor}"
PREVIEW_API = "https://letsreadasia.org/api/v5/book/preview/language/{lang_id}/book/{book_uuid}"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://letsreadasia.org/",
}

# Category → child category in online_books
CHILD_CATEGORY = "Cổ Tích - Thần Thoại"
PARENT_CATEGORY = "children-stories"

# Base tags for all LetsRead books
BASE_TAGS = ["letsread-asia", "english-books"]


# -------------------------------------------------------------------
# R2 / S3
# -------------------------------------------------------------------

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

R2_BUCKET = os.getenv("R2_BUCKET_NAME", "wordai-documents")


# -------------------------------------------------------------------
# API helpers
# -------------------------------------------------------------------

def fetch_category_books(cat_id: str, max_books: int = MAX_BOOKS_PER_CATEGORY) -> Tuple[List[Dict], str]:
    """
    Fetch up to max_books books from the Tag API for a given category.
    Returns (books_list, tag_name).
    """
    all_books: List[Dict] = []
    cursor = ""
    tag_name = cat_id  # fallback until first API call

    while len(all_books) < max_books:
        url = TAG_API.format(cat_id=cat_id, limit=PAGE_SIZE, lang_id=LANG_ID, cursor=cursor)
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            log.error(f"  Tag API error (cat={cat_id}, cursor={cursor[:20]}...): {e}")
            break

        data = resp.json()

        # Extract tag name from first page response
        if not all_books and data.get("tag"):
            tag_name = data["tag"].get("name", cat_id)

        page_books = data.get("books") or []
        if not page_books:
            break

        all_books.extend(page_books)
        log.info(f"  Fetched {len(all_books)} books so far (cat={cat_id})")

        # Check cursor for next page
        cursor = data.get("cursorWebSafeString") or ""
        if not cursor:
            break  # no more pages

        # Respect limit
        if len(all_books) >= max_books:
            break

        time.sleep(0.5)  # polite delay

    return all_books[:max_books], tag_name


def fetch_book_pages(master_book_id: str) -> Optional[Dict]:
    """Fetch page content via Preview API. Returns API response dict or None."""
    url = PREVIEW_API.format(lang_id=LANG_ID, book_uuid=master_book_id)
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"  Preview API error for {master_book_id}: {e}")
        return None


# -------------------------------------------------------------------
# Page parsing (skip cover + last promo page)
# -------------------------------------------------------------------

def parse_story_pages(api_data: Dict) -> List[Dict]:
    """
    Parse pages from Preview API response.
    - Skip cover (pageNum = "1")
    - Skip last page (LetsRead promo page)
    - Return renumbered pages starting from 1
    """
    raw_pages = api_data.get("pages") or []

    # Filter out cover
    story_raw = [p for p in raw_pages if str(p.get("pageNum", "")) != "1"]

    # Strip last page (promo)
    if story_raw:
        story_raw = story_raw[:-1]

    pages = []
    for idx, raw in enumerate(story_raw):
        try:
            page_num_int = int(raw.get("pageNum", idx + 2))
        except (ValueError, TypeError):
            page_num_int = idx + 2

        pages.append({
            "page_number": idx + 1,        # 1-based story page
            "api_page_num": page_num_int,
            "text_content": raw.get("extractedLongContentValue") or "",
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
        })

    return pages


# -------------------------------------------------------------------
# DB helpers
# -------------------------------------------------------------------

def find_book_by_master_id(db, master_book_id: str) -> Optional[Dict]:
    """Look up online_books by letsread masterBookId."""
    return db.online_books.find_one({"metadata.letsread_book_id": master_book_id})


def find_book_by_title(db, title: str) -> Optional[Dict]:
    """Fallback: look up by title (case-insensitive exact match)."""
    return db.online_books.find_one(
        {"title": {"$regex": f"^{re.escape(title)}$", "$options": "i"}}
    )


def add_tag_to_book(db, mongo_id, tag_slug: str) -> bool:
    """Add a tag to community_config.tags if not already present. Returns True if added."""
    book = db.online_books.find_one({"_id": mongo_id}, {"community_config": 1})
    existing_tags = (book.get("community_config") or {}).get("tags") or []
    if tag_slug in existing_tags:
        return False
    db.online_books.update_one(
        {"_id": mongo_id},
        {"$addToSet": {"community_config.tags": tag_slug}, "$set": {"updated_at": datetime.utcnow()}},
    )
    return True


def save_pages_to_db(db, book_id: str, master_book_id: str, pages: List[Dict], force: bool = False) -> int:
    """Upsert pages to book_page_texts. Returns count saved."""
    saved = 0
    for page in pages:
        doc = {
            "book_id": book_id,
            "letsread_book_id": master_book_id,
            "letsread_lang_id": LANG_ID,
            "language": "en",
            "updated_at": datetime.utcnow(),
            **page,
        }
        filter_q = {"book_id": book_id, "page_number": page["page_number"], "language": "en"}
        if force:
            db.book_page_texts.replace_one(filter_q, doc, upsert=True)
            saved += 1
        else:
            if db.book_page_texts.find_one(filter_q):
                continue
            doc["created_at"] = datetime.utcnow()
            db.book_page_texts.insert_one(doc)
            saved += 1
    return saved


# -------------------------------------------------------------------
# R2 helpers
# -------------------------------------------------------------------

def create_slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text.strip("-")


def upload_cover(s3, cover_url: str, slug: str) -> str:
    """Download cover image and upload to R2. Returns public URL."""
    try:
        resp = requests.get(cover_url, timeout=30)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "").lower()
        ext = "webp" if "webp" in ct else ("png" if "png" in ct else "jpg")
        ts = int(time.time())
        key = f"books/covers/{ts}_{slug}.{ext}"
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=resp.content, ContentType=ct or "image/jpeg")
        url = f"https://static.wordai.pro/{key}"
        log.info(f"  ✅ Cover → R2: {url}")
        return url
    except Exception as e:
        log.warning(f"  ⚠️  Cover upload failed: {e} — using original URL")
        return cover_url


def upload_pdf(s3, pdf_url: str, slug: str) -> Optional[str]:
    """Download portrait PDF and upload to R2. Returns public URL or None."""
    try:
        log.info(f"  📥 Downloading PDF: {pdf_url[:80]}...")
        resp = requests.get(pdf_url, stream=True, timeout=120)
        resp.raise_for_status()
        pdf_bytes = resp.content
        ts = int(time.time())
        key = f"books/letsread/{ts}_{slug}.pdf"
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=pdf_bytes, ContentType="application/pdf")
        url = f"https://static.wordai.pro/{key}"
        log.info(f"  ✅ PDF → R2: {url}")
        return url
    except Exception as e:
        log.error(f"  ❌ PDF upload failed: {e}")
        return None


# -------------------------------------------------------------------
# Book creation
# -------------------------------------------------------------------

def create_book_in_db(
    db,
    owner_user_id: str,
    title: str,
    description: str,
    cover_r2_url: str,
    pdf_r2_url: str,
    master_book_id: str,
    letsread_slug: str,
    tag_name: str,
    cat_id: str,
    reading_level: int,
) -> str:
    """
    Insert online_books + book_chapters documents.
    Returns the new book's _id as string.
    """
    slug = create_slug(title)
    book_id = f"book_{uuid.uuid4().hex[:12]}"
    chapter_id = str(uuid.uuid4())

    # Build tag list: base + category
    cat_tag = create_slug(tag_name)  # e.g. "nature", "animals-and-nature"
    tags = list(set(BASE_TAGS + [cat_tag]))

    short_desc = description[:200] if len(description) > 200 else description

    # Difficulty from reading level
    level_map = {1: "beginner", 2: "beginner", 3: "elementary", 4: "intermediate", 5: "intermediate"}
    difficulty = level_map.get(reading_level, "beginner")

    book_doc = {
        "book_id": book_id,
        "user_id": owner_user_id,
        "title": title,
        "slug": slug,
        "description": description or f"{title} - Children's story from Let's Read Asia",
        "visibility": "point_based",
        "is_published": True,
        "published_at": datetime.utcnow(),
        "is_deleted": False,
        "authors": ["@Storybook"],
        "metadata": {
            "original_author": "Let's Read Asia",
            "source": "letsreadasia.org",
            "source_url": f"https://www.letsreadasia.org/book/{letsread_slug}?bookLang={LANG_ID}",
            "source_category": tag_name,
            "letsread_category_id": cat_id,
            "language": "English",
            "letsread_book_id": master_book_id,
            "letsread_lang_id": LANG_ID,
            "uploaded_by": "@Storybook",
        },
        "community_config": {
            "is_public": True,
            "category": CHILD_CATEGORY,
            "parent_category": PARENT_CATEGORY,
            "tags": tags,
            "short_description": short_desc,
            "difficulty_level": difficulty,
            "cover_image_url": cover_r2_url or "",
            "total_views": 0,
            "total_downloads": 0,
            "total_purchases": 0,
            "total_saves": 0,
            "average_rating": 0.0,
            "rating_count": 0,
            "version": "1.0.0",
            "published_at": datetime.utcnow(),
        },
        "access_config": {
            "one_time_view_points": 2,
            "forever_view_points": 5,
            "download_pdf_points": 0,
            "is_one_time_enabled": True,
            "is_forever_enabled": True,
            "is_download_enabled": False,
        },
        "stats": {
            "total_revenue_points": 0, "owner_reward_points": 0,
            "system_fee_points": 0, "one_time_purchases": 0,
            "forever_purchases": 0, "pdf_downloads": 0,
        },
        "cover_image_url": cover_r2_url or "",
        "logo_url": None,
        "primary_color": "#4F46E5",
        "is_indexed": True,
        "view_count": 0,
        "unique_visitors": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "last_published_at": datetime.utcnow(),
    }

    chapter_doc = {
        "_id": chapter_id,
        "chapter_id": chapter_id,
        "book_id": book_id,
        "chapter_number": 1,
        "title": "Full Book",
        "slug": "full-book",
        "chapter_type": "pdf",
        "content_mode": "pdf_file",
        "pdf_url": pdf_r2_url,
        "order_index": 0,
        "depth": 0,
        "is_published": True,
        "is_preview_free": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = db.online_books.insert_one(book_doc)
    db.book_chapters.insert_one(chapter_doc)
    return str(result.inserted_id)


# -------------------------------------------------------------------
# Main crawl logic
# -------------------------------------------------------------------

def crawl_category(
    cat_id: str,
    db,
    s3,
    owner_user_id: str,
    dry_run: bool = False,
    pages_only: bool = False,
    force_pages: bool = False,
    max_books: int = MAX_BOOKS_PER_CATEGORY,
) -> Dict[str, Any]:
    """
    Crawl one category: fetch up to 100 books, process each.
    Returns summary stats dict.
    """
    log.info(f"\n{'='*70}")
    log.info(f"Category: {cat_id}")
    log.info(f"  dry_run={dry_run}, pages_only={pages_only}")

    stats = {
        "category": cat_id,
        "tag_name": cat_id,
        "total_api": 0,
        "already_exists": 0,
        "tags_added": 0,
        "new_created": 0,
        "pages_saved": 0,
        "failed": 0,
    }

    # Step 1: Fetch books list from Tag API
    log.info(f"  Fetching up to {max_books} books from Tag API...")
    books, tag_name = fetch_category_books(cat_id, max_books)
    stats["tag_name"] = tag_name
    stats["total_api"] = len(books)
    cat_tag_slug = create_slug(tag_name)

    log.info(f"  Tag: {tag_name!r} (slug: {cat_tag_slug})")
    log.info(f"  Got {len(books)} books from API")

    if dry_run:
        log.info(f"  [DRY-RUN] Books:")
        for i, b in enumerate(books, 1):
            title = b.get("name", "?")
            mid = b.get("masterBookId", "?")
            pages_count = b.get("totalPages", "?")
            existing = find_book_by_master_id(db, mid) or find_book_by_title(db, title)
            status = "EXISTS" if existing else "NEW"
            log.info(f"    {i:3d}. [{status}] {title} (uuid={mid[:8]}..., pages={pages_count})")
        return stats

    # Step 2: Process each book
    for idx, book in enumerate(books, 1):
        title = book.get("name", "")
        master_book_id = book.get("masterBookId", "")
        letsread_slug = book.get("slug", create_slug(title))
        description = book.get("description") or ""
        reading_level = book.get("readingLevel") or 1
        cover_url = book.get("thumborCoverImageUrl") or book.get("coverImageUrl") or ""
        pdf_info = book.get("pdfUrl") or {}
        portrait_pdf_url = (
            pdf_info.get("potraitUrl")      # Note: API typo is "potrait" not "portrait"
            or pdf_info.get("bookletUrl")    # fallback to booklet
            or ""
        )

        if not title or not master_book_id:
            log.warning(f"  [{idx}] Skipping: missing title or masterBookId")
            stats["failed"] += 1
            continue

        log.info(f"\n  [{idx}/{len(books)}] {title!r}")

        # Check if book already exists
        existing = find_book_by_master_id(db, master_book_id) or find_book_by_title(db, title)

        if existing:
            book_id = str(existing["_id"])
            log.info(f"    ✅ Exists in DB (id={book_id[:12]}...)")
            stats["already_exists"] += 1

            # Ensure it has the letsread_book_id set (might be missing on old books)
            if not existing.get("metadata", {}).get("letsread_book_id"):
                db.online_books.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "metadata.letsread_book_id": master_book_id,
                        "metadata.letsread_lang_id": LANG_ID,
                    }}
                )

            # Add new category tag if missing
            added = add_tag_to_book(db, existing["_id"], cat_tag_slug)
            if added:
                log.info(f"    🏷️  Added tag: {cat_tag_slug}")
                stats["tags_added"] += 1

            # Save pages if pages_only mode or pages not yet saved
            if pages_only or not db.book_page_texts.find_one({"book_id": book_id}):
                _fetch_and_save_pages(db, book_id, master_book_id, force_pages)
                stats["pages_saved"] += 1

            continue

        # New book — create it
        if pages_only:
            log.info(f"    ⏭️  --pages-only: skipping new book creation")
            continue

        if not portrait_pdf_url:
            log.error(f"    ❌ No PDF URL — skipping {title!r}")
            stats["failed"] += 1
            continue

        try:
            # Upload cover
            cover_r2_url = upload_cover(s3, cover_url, create_slug(title)) if cover_url else ""

            # Download + Upload PDF
            log.info(f"    📄 PDF: {portrait_pdf_url[:60]}...")
            pdf_r2_url = upload_pdf(s3, portrait_pdf_url, create_slug(title))
            if not pdf_r2_url:
                stats["failed"] += 1
                continue

            # Create book in DB
            book_id = create_book_in_db(
                db=db,
                owner_user_id=owner_user_id,
                title=title,
                description=description,
                cover_r2_url=cover_r2_url,
                pdf_r2_url=pdf_r2_url,
                master_book_id=master_book_id,
                letsread_slug=letsread_slug,
                tag_name=tag_name,
                cat_id=cat_id,
                reading_level=reading_level,
            )
            log.info(f"    ✅ Created book: id={book_id[:12]}...")
            stats["new_created"] += 1

            # Fetch + save pages
            _fetch_and_save_pages(db, book_id, master_book_id, force=False)
            stats["pages_saved"] += 1

            time.sleep(1)  # polite delay between new books

        except Exception as e:
            log.exception(f"    ❌ Failed to process {title!r}: {e}")
            stats["failed"] += 1

    log.info(f"\n  📊 Category {tag_name!r} done:")
    log.info(f"     total={stats['total_api']}, new={stats['new_created']}, "
             f"existing={stats['already_exists']}, tags_added={stats['tags_added']}, "
             f"failed={stats['failed']}")
    return stats


def _fetch_and_save_pages(db, book_id: str, master_book_id: str, force: bool = False) -> int:
    """Fetch Preview API pages and save to book_page_texts. Returns pages saved."""
    log.info(f"    📖 Fetching pages for {master_book_id[:8]}...")
    api_data = fetch_book_pages(master_book_id)
    if not api_data:
        log.error(f"    ❌ Preview API failed for masterBookId={master_book_id}")
        return 0

    pages = parse_story_pages(api_data)
    total_raw = api_data.get("totalPages", 0)
    log.info(f"    📄 API totalPages={total_raw}, story pages (excl cover+promo)={len(pages)}")

    saved = save_pages_to_db(db, book_id, master_book_id, pages, force=force)
    log.info(f"    ✅ Saved {saved}/{len(pages)} pages")

    # Update online_books metadata
    try:
        import bson
        db.online_books.update_one(
            {"_id": bson.ObjectId(book_id)},
            {"$set": {
                "metadata.letsread_book_id": master_book_id,
                "metadata.letsread_lang_id": LANG_ID,
                "metadata.has_page_texts": True,
                "metadata.total_pages": len(pages),
                "updated_at": datetime.utcnow(),
            }},
        )
    except Exception:
        pass

    return saved


# -------------------------------------------------------------------
# CLI entry point
# -------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="LetsRead Category Crawler")
    parser.add_argument("--cat", nargs="+", help="One or more category IDs to crawl", default=None)
    parser.add_argument("--dry-run", action="store_true", help="No DB writes, just list books")
    parser.add_argument("--pages-only", action="store_true", help="Only fetch/save pages, no new book creation")
    parser.add_argument("--force-pages", action="store_true", help="Re-fetch pages even if already saved")
    parser.add_argument("--max", type=int, default=MAX_BOOKS_PER_CATEGORY, help="Max books per category")
    args = parser.parse_args()

    max_books = args.max

    # Init DB
    db_manager = DBManager()
    db = db_manager.db

    # Get owner user_id
    michael = db.authors.find_one({"author_id": "@michael"})
    if not michael or not michael.get("user_id"):
        log.error("❌ @michael author not found in DB — cannot create books")
        sys.exit(1)
    owner_user_id = michael["user_id"]
    log.info(f"Owner: {owner_user_id}")

    # Init R2
    s3 = get_s3_client()

    categories = args.cat if args.cat else CATEGORIES

    all_stats = []
    for cat_id in categories:
        try:
            stats = crawl_category(
                cat_id=cat_id,
                db=db,
                s3=s3,
                owner_user_id=owner_user_id,
                dry_run=args.dry_run,
                pages_only=args.pages_only,
                force_pages=args.force_pages,
                max_books=max_books,
            )
            all_stats.append(stats)
        except Exception as e:
            log.exception(f"Category {cat_id} failed: {e}")

    # Final summary
    print(f"\n{'='*70}")
    print(f"FINAL SUMMARY — {len(all_stats)} categories processed")
    print(f"{'='*70}")
    total_new = total_existing = total_fails = total_pages = 0
    for s in all_stats:
        print(f"  [{s['tag_name']:25s}]  api={s['total_api']:3d}  "
              f"new={s['new_created']:3d}  exists={s['already_exists']:3d}  "
              f"tags_added={s['tags_added']:3d}  pages={s['pages_saved']:3d}  "
              f"fail={s['failed']:3d}")
        total_new += s["new_created"]
        total_existing += s["already_exists"]
        total_fails += s["failed"]
        total_pages += s["pages_saved"]
    print(f"{'─'*70}")
    print(f"  TOTAL: new_books={total_new}, existing={total_existing}, "
          f"pages_saved={total_pages}, failed={total_fails}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
