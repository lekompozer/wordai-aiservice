#!/usr/bin/env python3
"""
Batch convert MOBI files to EPUB format.
Reads mobi_books_list.json and converts all identified MOBI files.

Usage:
    python3 batch_convert_mobi_to_epub.py --input mobi_books_list.json
    python3 batch_convert_mobi_to_epub.py --input mobi_books_list.json --limit 10  # Test mode
    python3 batch_convert_mobi_to_epub.py --resume  # Resume from last checkpoint
"""
import asyncio
import json
import sys
import subprocess
import requests
from datetime import datetime
from pathlib import Path
import boto3
from typing import List, Dict, Optional
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.database.db_manager import DBManager
import os
from dotenv import load_dotenv

load_dotenv()

# R2 Configuration - use correct env var names
R2_ENDPOINT = os.getenv("R2_ENDPOINT")  # Fixed: was R2_ENDPOINT_URL
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET_NAME", "wordai")

s3_client = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    region_name="auto",
)


def convert_mobi_to_epub(mobi_path: str, epub_path: str, timeout: int = 120) -> bool:
    """
    Convert MOBI file to EPUB using Calibre ebook-convert.

    Args:
        mobi_path: Path to input MOBI file
        epub_path: Path to output EPUB file
        timeout: Conversion timeout in seconds

    Returns:
        True if conversion successful, False otherwise
    """
    try:
        result = subprocess.run(
            ["ebook-convert", mobi_path, epub_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            print(f"  ❌ Conversion failed: {result.stderr[:200]}")
            return False

        # Verify output file exists and has content
        if Path(epub_path).exists() and Path(epub_path).stat().st_size > 0:
            return True
        else:
            print(f"  ❌ Output file empty or missing")
            return False

    except subprocess.TimeoutExpired:
        print(f"  ❌ Conversion timeout (>{timeout}s)")
        return False
    except Exception as e:
        print(f"  ❌ Conversion error: {e}")
        return False


def upload_to_r2(local_file: str, r2_key: str) -> Optional[str]:
    """
    Upload file to R2 storage.

    Args:
        local_file: Path to local file
        r2_key: Key in R2 bucket (e.g., "books/crawled-epub/xxx.epub")

    Returns:
        Public URL if successful, None otherwise
    """
    try:
        with open(local_file, "rb") as f:
            s3_client.upload_fileobj(
                f, R2_BUCKET, r2_key, ExtraArgs={"ContentType": "application/epub+zip"}
            )

        # Return public URL
        public_url = f"https://static.wordai.pro/{r2_key}"
        return public_url

    except Exception as e:
        print(f"  ❌ R2 upload error: {e}")
        return None


async def convert_single_book(db, book_info: Dict, temp_dir: Path, stats: Dict) -> bool:
    """
    Convert a single MOBI file to EPUB.

    Args:
        db: MongoDB database connection
        book_info: Book information from scan results
        temp_dir: Temporary directory for conversion
        stats: Statistics dictionary to update

    Returns:
        True if successful, False otherwise
    """
    book_id = book_info["book_id"]
    chapter_id = book_info["chapter_id"]
    mobi_url = book_info["pdf_url"]  # Actually MOBI file
    book_title = book_info.get("book_title", "Unknown")

    print(f"\n📖 {book_title}")
    print(f"   Book ID: {book_id}")
    print(f"   Chapter: {chapter_id}")

    # Check if already converted
    existing = db.book_chapters.find_one(
        {"chapter_id": chapter_id, "epub_url": {"$exists": True, "$ne": None}}
    )

    if existing and existing.get("epub_url"):
        print(f"  ⏭️  Already converted, skipping")
        stats["skipped"] += 1
        return True

    # Download MOBI file
    temp_mobi = temp_dir / f"{chapter_id}.mobi"
    temp_epub = temp_dir / f"{chapter_id}.epub"

    try:
        print(f"  📥 Downloading MOBI...")
        response = requests.get(mobi_url, timeout=30)
        response.raise_for_status()

        with open(temp_mobi, "wb") as f:
            f.write(response.content)

        print(f"  📥 Downloaded {len(response.content):,} bytes")

    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        stats["download_errors"] += 1
        return False

    # Convert MOBI → EPUB
    print(f"  🔄 Converting MOBI → EPUB...")
    success = convert_mobi_to_epub(str(temp_mobi), str(temp_epub))

    if not success:
        stats["conversion_errors"] += 1
        temp_mobi.unlink()  # Cleanup
        return False

    epub_size = temp_epub.stat().st_size
    print(f"  ✅ Converted to EPUB ({epub_size:,} bytes)")

    # Upload to R2
    timestamp = int(datetime.utcnow().timestamp())
    r2_key = f"books/crawled-epub/{timestamp}_{book_id}_{chapter_id}.epub"

    print(f"  📤 Uploading to R2...")
    epub_url = upload_to_r2(str(temp_epub), r2_key)

    if not epub_url:
        stats["upload_errors"] += 1
        temp_mobi.unlink()
        temp_epub.unlink()
        return False

    print(f"  ✅ Uploaded: {epub_url}")

    # Update MongoDB
    try:
        db.book_chapters.update_one(
            {"chapter_id": chapter_id},
            {
                "$set": {
                    "epub_url": epub_url,
                    "original_mobi_url": mobi_url,
                    "chapter_type": "epub",
                    "content_mode": "epub_file",
                    "converted_at": datetime.utcnow(),
                    "conversion_tool": "calibre-ebook-convert-8.5.0",
                }
            },
        )
        print(f"  ✅ Database updated")
        stats["successful"] += 1

    except Exception as e:
        print(f"  ❌ Database update failed: {e}")
        stats["db_errors"] += 1
        return False

    finally:
        # Cleanup temp files
        if temp_mobi.exists():
            temp_mobi.unlink()
        if temp_epub.exists():
            temp_epub.unlink()

    return True


async def batch_convert(input_file: str, limit: Optional[int] = None):
    """
    Batch convert all MOBI files from scan results.

    Args:
        input_file: Path to mobi_books_list.json
        limit: Maximum number of books to convert (for testing)
    """
    # Load scan results
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    books = data["books"]
    total = len(books)

    if limit:
        books = books[:limit]
        print(f"🧪 TEST MODE: Converting {len(books)} of {total} books")
    else:
        print(f"🚀 FULL MODE: Converting {total} books")

    print(f"📅 Scan date: {data['scan_date']}")
    print("=" * 60)

    # Initialize
    db_manager = DBManager()
    db = db_manager.db
    temp_dir = Path("/tmp/mobi_conversion")
    temp_dir.mkdir(exist_ok=True)

    # Statistics
    stats = {
        "total": len(books),
        "successful": 0,
        "skipped": 0,
        "download_errors": 0,
        "conversion_errors": 0,
        "upload_errors": 0,
        "db_errors": 0,
    }

    start_time = datetime.now()

    # Process books
    for idx, book_info in enumerate(books, 1):
        print(f"\n{'='*60}")
        print(f"📊 Progress: {idx}/{len(books)}")
        print(f"{'='*60}")

        await convert_single_book(db, book_info, temp_dir, stats)

        # Progress report every 10 books
        if idx % 10 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = idx / elapsed * 60  # books per minute
            remaining = (len(books) - idx) / rate if rate > 0 else 0

            print(f"\n{'='*60}")
            print(f"📊 PROGRESS REPORT")
            print(f"{'='*60}")
            print(f"Completed: {idx}/{len(books)} ({idx/len(books)*100:.1f}%)")
            print(f"Successful: {stats['successful']}")
            print(f"Skipped: {stats['skipped']}")
            print(
                f"Errors: {stats['download_errors'] + stats['conversion_errors'] + stats['upload_errors'] + stats['db_errors']}"
            )
            print(f"Rate: {rate:.1f} books/min")
            print(f"Estimated remaining: {remaining:.0f} minutes")
            print(f"{'='*60}\n")

    # Final report
    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n{'='*60}")
    print(f"🎉 CONVERSION COMPLETE!")
    print(f"{'='*60}")
    print(f"Total processed: {stats['total']}")
    print(f"✅ Successful: {stats['successful']}")
    print(f"⏭️  Skipped (already converted): {stats['skipped']}")
    print(f"❌ Download errors: {stats['download_errors']}")
    print(f"❌ Conversion errors: {stats['conversion_errors']}")
    print(f"❌ Upload errors: {stats['upload_errors']}")
    print(f"❌ Database errors: {stats['db_errors']}")
    print(f"⏱️  Total time: {elapsed/60:.1f} minutes")
    print(f"📈 Average rate: {stats['total']/elapsed*60:.1f} books/min")
    print(f"{'='*60}\n")

    # Save results
    results_file = f"conversion_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "completed_at": datetime.utcnow().isoformat(),
                "stats": stats,
                "elapsed_seconds": elapsed,
            },
            f,
            indent=2,
        )

    print(f"💾 Results saved to {results_file}")


async def main():
    parser = argparse.ArgumentParser(description="Batch convert MOBI files to EPUB")
    parser.add_argument(
        "--input",
        default="mobi_books_list.json",
        help="Input JSON file from scan (default: mobi_books_list.json)",
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of books to convert (for testing)"
    )

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"❌ Input file not found: {args.input}")
        print(f"💡 Run scan_mobi_books.py first to generate the list")
        return

    await batch_convert(args.input, args.limit)


if __name__ == "__main__":
    asyncio.run(main())
