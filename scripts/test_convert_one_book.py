#!/usr/bin/env python3
"""
Test script to convert one MOBI book to PDF
Usage: python test_convert_one_book.py book_dfeca8d85b72
"""

import sys
import requests
import subprocess
from pathlib import Path
import os
import boto3
from datetime import datetime

# Use DBManager pattern from existing code
from src.database.db_manager import DBManager

# MongoDB connection
db_manager = DBManager()
db = db_manager.db

# R2 Configuration
R2_ENDPOINT = os.getenv("R2_ENDPOINT_URL")
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


def is_mobi_file(url):
    """Check if file is MOBI by reading header"""
    try:
        headers = {"Range": "bytes=0-99"}
        response = requests.get(url, headers=headers, timeout=10)

        content = response.content
        print(f"   File header: {content[:20]}")

        if b"BOOKMOBI" in content:
            print(f"   ✅ Confirmed MOBI file")
            return True

        if content.startswith(b"%PDF-"):
            print(f"   ✅ Already valid PDF")
            return False

        print(f"   ⚠️  Unknown format")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def convert_book(book_id):
    """Convert one book from MOBI to PDF"""
    print(f"\n{'='*70}")
    print(f"📖 Processing book: {book_id}")

    # Find chapter
    chapter = db.book_chapters.find_one(
        {"book_id": book_id, "chapter_type": "pdf"},
        {"chapter_id": 1, "pdf_url": 1, "title": 1},
    )

    if not chapter:
        print(f"❌ No PDF chapter found for book {book_id}")
        return

    chapter_id = chapter["chapter_id"]
    pdf_url = chapter["pdf_url"]
    title = chapter.get("title", "Unknown")

    print(f"📄 Chapter: {title}")
    print(f"🔗 Current URL: {pdf_url}")

    # Check if MOBI
    print(f"\n🔍 Checking file format...")
    if not is_mobi_file(pdf_url):
        print(f"✅ No conversion needed - already valid PDF")
        return

    # Create temp directory
    temp_dir = Path("/tmp/mobi_test")
    temp_dir.mkdir(exist_ok=True)

    # Download MOBI
    mobi_path = temp_dir / f"{chapter_id}.mobi"
    print(f"\n⬇️  Downloading MOBI file...")

    try:
        response = requests.get(pdf_url, stream=True, timeout=60)
        response.raise_for_status()

        with open(mobi_path, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

        print(f"   ✅ Downloaded: {mobi_path} ({mobi_path.stat().st_size} bytes)")
    except Exception as e:
        print(f"   ❌ Download failed: {e}")
        return

    # Convert to PDF
    pdf_path = temp_dir / f"{chapter_id}.pdf"
    print(f"\n🔄 Converting MOBI → PDF using Calibre...")

    try:
        result = subprocess.run(
            ["ebook-convert", str(mobi_path), str(pdf_path), "--no-inline-toc"],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            print(f"   ❌ Conversion failed!")
            print(f"   STDERR: {result.stderr[:500]}")
            return

        print(f"   ✅ Converted: {pdf_path} ({pdf_path.stat().st_size} bytes)")
    except Exception as e:
        print(f"   ❌ Conversion error: {e}")
        return

    # Upload to R2
    timestamp = int(datetime.now().timestamp())
    r2_key = f"books/crawled-converted/{timestamp}_{book_id}_{chapter_id}.pdf"

    print(f"\n⬆️  Uploading to R2: {r2_key}")

    try:
        with open(pdf_path, "rb") as f:
            s3_client.put_object(
                Bucket=R2_BUCKET,
                Key=r2_key,
                Body=f,
                ContentType="application/pdf",
            )

        new_url = f"https://static.wordai.pro/{r2_key}"
        print(f"   ✅ Uploaded: {new_url}")
    except Exception as e:
        print(f"   ❌ Upload failed: {e}")
        return

    # Update MongoDB
    print(f"\n💾 Updating MongoDB...")

    result = db.book_chapters.update_one(
        {"chapter_id": chapter_id},
        {
            "$set": {
                "pdf_url": new_url,
                "original_mobi_url": pdf_url,
                "converted_at": datetime.utcnow(),
            }
        },
    )

    print(f"   ✅ Updated {result.modified_count} document(s)")

    # Cleanup
    mobi_path.unlink(missing_ok=True)
    pdf_path.unlink(missing_ok=True)

    print(f"\n{'='*70}")
    print(f"✅ SUCCESS! Book converted and updated")
    print(f"📖 Old URL: {pdf_url}")
    print(f"🆕 New URL: {new_url}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_convert_one_book.py <book_id>")
        print("Example: python test_convert_one_book.py book_dfeca8d85b72")
        sys.exit(1)

    book_id = sys.argv[1]
    convert_book(book_id)
