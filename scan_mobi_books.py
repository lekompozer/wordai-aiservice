#!/usr/bin/env python3
"""
Scan all crawled books to identify MOBI files disguised as PDFs.
Save the list for batch conversion to EPUB format.

Usage:
    python3 scan_mobi_books.py --output mobi_books_list.json
    python3 scan_mobi_books.py --test-convert  # Test MOBI → EPUB conversion
"""
import asyncio
import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path
import requests
from typing import List, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.database.db_manager import DBManager


def is_mobi_file(url: str) -> bool:
    """
    Check if a file is actually MOBI format by reading first 100 bytes.

    Args:
        url: Direct URL to the file

    Returns:
        True if file is MOBI format, False otherwise
    """
    try:
        # Use Range header to download only first 100 bytes
        headers = {"Range": "bytes=0-99"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code not in [200, 206]:
            print(f"⚠️  Failed to fetch {url}: {response.status_code}")
            return False

        content = response.content

        # Check for MOBI magic bytes
        if b"BOOKMOBI" in content[:100]:
            return True

        # Check for PDF magic bytes (should start with %PDF-)
        if content.startswith(b"%PDF-"):
            return False

        # If neither, it might be corrupted or other format
        print(f"⚠️  Unknown format for {url}: {content[:20]}")
        return False

    except Exception as e:
        print(f"❌ Error checking {url}: {e}")
        return False


def test_mobi_to_epub_conversion(
    mobi_url: str, output_path: str = "/tmp/test_conversion.epub"
) -> bool:
    """
    Test MOBI → EPUB conversion using Calibre ebook-convert.
    This is much more reliable than MOBI → PDF as it doesn't require GPU context.

    Args:
        mobi_url: URL to download MOBI file from
        output_path: Where to save the converted EPUB

    Returns:
        True if conversion successful, False otherwise
    """
    temp_mobi = "/tmp/test.mobi"

    try:
        # Download MOBI file
        print(f"📥 Downloading MOBI file...")
        response = requests.get(mobi_url, timeout=30)
        response.raise_for_status()

        with open(temp_mobi, "wb") as f:
            f.write(response.content)

        print(f"📥 Downloaded {len(response.content)} bytes")

        # Convert MOBI → EPUB using ebook-convert
        print(f"🔄 Converting MOBI → EPUB...")
        result = subprocess.run(
            ["ebook-convert", temp_mobi, output_path],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            print(f"❌ Conversion failed:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False

        # Check if output file exists and has content
        if Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            print(f"✅ Conversion successful! EPUB size: {file_size} bytes")
            print(f"📄 Output: {output_path}")
            return True
        else:
            print(f"❌ Output file not created")
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ Conversion timeout (>120s)")
        return False
    except Exception as e:
        print(f"❌ Conversion error: {e}")
        return False
    finally:
        # Cleanup temp MOBI file
        if Path(temp_mobi).exists():
            Path(temp_mobi).unlink()


async def scan_all_books() -> List[Dict]:
    """
    Scan all books with crawled PDF URLs to identify MOBI files.

    Returns:
        List of books that are actually MOBI format
    """
    db_manager = DBManager()
    db = db_manager.db

    # Query all chapters with crawled PDF URLs
    query = {"pdf_url": {"$regex": r"crawled.*\.pdf", "$options": "i"}}

    total_count = db.book_chapters.count_documents(query)
    print(f"📊 Found {total_count} chapters with crawled PDF URLs")
    print(f"🔍 Scanning for MOBI files...\n")

    mobi_books = []
    checked = 0
    mobi_count = 0
    pdf_count = 0
    error_count = 0

    # Process in batches
    cursor = db.book_chapters.find(query).batch_size(100)

    for chapter in cursor:
        checked += 1

        book_id = chapter.get("book_id")
        chapter_id = chapter.get("chapter_id")
        pdf_url = chapter.get("pdf_url")

        if not pdf_url:
            continue

        # Check if file is actually MOBI
        is_mobi = is_mobi_file(pdf_url)

        if is_mobi:
            mobi_count += 1

            # Get book info - try multiple query methods
            book = db.books.find_one({"book_id": book_id})
            if not book:
                # Try with _id field
                book = db.books.find_one({"_id": book_id})

            if book:
                book_title = book.get("title") or book.get("name") or "Unknown"
                author = book.get("author", "")
            else:
                # Use filename from URL as fallback
                filename = pdf_url.split("/")[-1].replace(".pdf", "").replace("_", " ")
                book_title = filename[:50]  # Truncate long filenames
                author = ""

            chapter_num = chapter.get("chapter_order", 0)

            mobi_books.append(
                {
                    "book_id": book_id,
                    "book_title": book_title,
                    "author": author,
                    "chapter_id": chapter_id,
                    "chapter_order": chapter_num,
                    "pdf_url": pdf_url,
                    "filename": pdf_url.split("/")[-1],
                    "scanned_at": datetime.utcnow().isoformat(),
                }
            )

            # Better log display with URL
            display_name = f"{book_title} {f'({author})' if author else ''}"
            print(f"✅ [{mobi_count}] {display_name}")
            print(f"    URL: {pdf_url}")
        else:
            # Check if it's actually a valid PDF or error
            try:
                headers = {"Range": "bytes=0-10"}
                response = requests.get(pdf_url, headers=headers, timeout=5)
                if b"%PDF-" in response.content:
                    pdf_count += 1
                else:
                    error_count += 1
            except:
                error_count += 1

        # Progress update every 100 books
        if checked % 100 == 0:
            print(f"\n📈 Progress: {checked}/{total_count} checked")
            print(
                f"   MOBI: {mobi_count} | Valid PDF: {pdf_count} | Errors: {error_count}\n"
            )

    print(f"\n{'='*60}")
    print(f"📊 Scan Complete!")
    print(f"   Total checked: {checked}")
    print(f"   MOBI files found: {mobi_count}")
    print(f"   Valid PDFs: {pdf_count}")
    print(f"   Errors/Unknown: {error_count}")
    print(f"{'='*60}\n")

    return mobi_books


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan for MOBI books disguised as PDFs"
    )
    parser.add_argument(
        "--output",
        default="mobi_books_list.json",
        help="Output JSON file (default: mobi_books_list.json)",
    )
    parser.add_argument(
        "--test-convert",
        action="store_true",
        help="Test MOBI → EPUB conversion with one file",
    )

    args = parser.parse_args()

    if args.test_convert:
        # Test conversion with Harry Potter book
        test_url = "https://static.wordai.pro/books/crawled/1770612674_harry-potter-va-hon-da-phu-thuy-tap-1.pdf"
        print("🧪 Testing MOBI → EPUB conversion...")
        print(f"📖 Test file: Harry Potter")
        success = test_mobi_to_epub_conversion(test_url)

        if success:
            print(
                "\n✅ EPUB conversion works! This method is viable for batch conversion."
            )
            print("💡 Next steps:")
            print("   1. Run scan without --test-convert to get full list")
            print("   2. Create batch conversion script for MOBI → EPUB")
            print("   3. Frontend implements EPUB reader (e.g., epub.js)")
        else:
            print("\n❌ EPUB conversion failed. May need alternative approach.")

        return

    # Scan all books
    mobi_books = await scan_all_books()

    # Save to JSON file
    output_data = {
        "scan_date": datetime.utcnow().isoformat(),
        "total_mobi_files": len(mobi_books),
        "books": mobi_books,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"💾 Saved {len(mobi_books)} MOBI books to {args.output}")

    if mobi_books:
        print(f"\n📝 Sample entries:")
        for i, book in enumerate(mobi_books[:3]):
            print(f"   {i+1}. {book['book_title']} - {book['pdf_url']}")

        print(f"\n💡 Next steps:")
        print(f"   1. Review {args.output} for complete list")
        print(f"   2. Run with --test-convert to verify EPUB conversion works")
        print(f"   3. Create batch conversion script if test succeeds")
        print(f"   4. Frontend implements EPUB reader library")


if __name__ == "__main__":
    asyncio.run(main())
