#!/usr/bin/env python3
"""
Test script to convert a single MOBI file to PDF
Usage: python fix_single_mobi.py book_dfeca8d85b72
"""

import requests
import subprocess
from pathlib import Path
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import boto3
from datetime import datetime
import sys
from typing import Optional

# Load environment
load_dotenv()

# MongoDB connection - use authenticated connection from environment or hardcode for production
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI or "mongodb://" == MONGODB_URI[:10]:
    # Fallback to production authenticated connection
    MONGODB_URI = "mongodb://ai_service_user:ai_service_2025_secure_password@mongodb:27017/ai_service_db?authSource=admin"

client = MongoClient(MONGODB_URI)
db = client.ai_service_db

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


def is_mobi_file(url: str) -> bool:
    """Check if file is actually MOBI by reading header"""
    try:
        headers = {"Range": "bytes=0-99"}
        response = requests.get(url, headers=headers, timeout=10)

        print(f"   📄 File header: {response.content[:30]}")

        if b"BOOKMOBI" in response.content:
            print(f"   ⚠️  Detected: MOBI file!")
            return True

        if response.content.startswith(b"%PDF-"):
            print(f"   ✅ Detected: Valid PDF file")
            return False

        print(f"   ❓ Unknown file format")
        return False
    except Exception as e:
        print(f"  ❌ Error checking {url}: {e}")
        return False


def download_file(url: str, output_path: Path) -> bool:
    """Download file from URL"""
    try:
        print(f"   ⬇️  Downloading from: {url}")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ Downloaded: {size_mb:.2f} MB")
        return True
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False


def convert_mobi_to_pdf(mobi_path: Path) -> Optional[Path]:
    """Convert MOBI to PDF using Calibre ebook-convert"""
    try:
        pdf_path = mobi_path.with_suffix(".converted.pdf")

        print(f"   🔄 Converting MOBI → PDF with Calibre...")
        print(f"   Command: ebook-convert {mobi_path.name} {pdf_path.name}")

        # Set environment variables for headless operation
        env = os.environ.copy()
        env["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
        env["QT_QPA_PLATFORM"] = "offscreen"

        result = subprocess.run(
            ["ebook-convert", str(mobi_path), str(pdf_path), "--no-inline-toc"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        if result.returncode != 0:
            print(f"  ❌ Conversion failed!")
            print(f"  stderr: {result.stderr[:500]}")
            return None

        if pdf_path.exists():
            size_mb = pdf_path.stat().st_size / (1024 * 1024)
            print(f"   ✅ Conversion successful: {size_mb:.2f} MB")
            return pdf_path
        else:
            print(f"  ❌ PDF file not created")
            return None

    except Exception as e:
        print(f"  ❌ Conversion error: {e}")
        return None


def upload_to_r2(file_path: Path, r2_key: str) -> Optional[str]:
    """Upload file to R2 and return public URL"""
    try:
        print(f"   ⬆️  Uploading to R2: {r2_key}")

        with open(file_path, "rb") as f:
            s3_client.put_object(
                Bucket=R2_BUCKET,
                Key=r2_key,
                Body=f,
                ContentType="application/pdf",
            )

        url = f"https://static.wordai.pro/{r2_key}"
        print(f"   ✅ Upload successful!")
        print(f"   Public URL: {url}")
        return url
    except Exception as e:
        print(f"  ❌ Upload failed: {e}")
        return None


def process_book(book_id: str):
    """Process a single book - find its chapter and convert if needed"""

    print(f"\n{'='*70}")
    print(f"📖 Processing book: {book_id}")
    print(f"{'='*70}\n")

    # Find book
    book = db.online_books.find_one({"book_id": book_id})
    if not book:
        print(f"❌ Book not found!")
        return

    print(f"📚 Book found: {book['title']}")

    # Find chapter with PDF
    chapter = db.book_chapters.find_one(
        {"book_id": book_id, "pdf_url": {"$exists": True}},
        {"chapter_id": 1, "title": 1, "pdf_url": 1},
    )

    if not chapter:
        print(f"❌ No chapter with PDF found!")
        return

    chapter_id = chapter["chapter_id"]
    pdf_url = chapter["pdf_url"]
    chapter_title = chapter["title"]

    print(f"📄 Chapter: {chapter_title}")
    print(f"🔗 Current URL: {pdf_url}\n")

    # Check if file is actually MOBI
    print("🔍 Checking file format...")
    if not is_mobi_file(pdf_url):
        print(f"\n✅ File is already a valid PDF, no conversion needed!")
        return

    print(f"\n⚠️  File needs conversion!\n")

    # Create temp directory
    temp_dir = Path("temp_mobi_test")
    temp_dir.mkdir(exist_ok=True)

    # Download MOBI file
    mobi_path = temp_dir / f"{book_id}.mobi"
    if not download_file(pdf_url, mobi_path):
        return

    # Convert to PDF
    print()
    pdf_path = convert_mobi_to_pdf(mobi_path)
    if not pdf_path:
        mobi_path.unlink(missing_ok=True)
        return

    # Upload to R2
    print()
    timestamp = int(datetime.now().timestamp())
    r2_key = f"books/crawled-converted/{timestamp}_{book_id}.pdf"
    new_url = upload_to_r2(pdf_path, r2_key)

    if not new_url:
        mobi_path.unlink(missing_ok=True)
        pdf_path.unlink(missing_ok=True)
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

    print(f"   Modified: {result.modified_count} document(s)")

    # Cleanup temp files
    mobi_path.unlink(missing_ok=True)
    pdf_path.unlink(missing_ok=True)

    print(f"\n{'='*70}")
    print(f"✅ CONVERSION COMPLETE!")
    print(f"{'='*70}")
    print(f"📚 Book: {book['title']}")
    print(f"🔗 Old URL: {pdf_url}")
    print(f"🔗 New URL: {new_url}")
    print(f"\n🧪 Test the new URL:")
    print(f"   curl -I '{new_url}' | grep -i content-type")
    print(f"   curl -s '{new_url}' | head -c 10")
    print(f"\n📖 View in browser:")
    print(f"   https://ai.wordai.pro/read/{book['slug']}/full-book")


def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_single_mobi.py <book_id>")
        print("Example: python fix_single_mobi.py book_dfeca8d85b72")
        sys.exit(1)

    book_id = sys.argv[1]
    process_book(book_id)

    # Cleanup temp directory
    temp_dir = Path("temp_mobi_test")
    if temp_dir.exists():
        import shutil

        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
