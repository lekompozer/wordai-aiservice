#!/usr/bin/env python3
"""
Script to detect and convert MOBI files disguised as PDF
Checks file header to identify real format, then converts MOBI → PDF
"""

import requests
import subprocess
from pathlib import Path
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import boto3
from datetime import datetime

# Load environment
load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI")
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
        # Download first 100 bytes to check magic number
        headers = {"Range": "bytes=0-99"}
        response = requests.get(url, headers=headers, timeout=10)

        # MOBI files start with "BOOKMOBI"
        if b"BOOKMOBI" in response.content:
            return True

        # PDF files start with "%PDF-"
        if response.content.startswith(b"%PDF-"):
            return False

        return False
    except Exception as e:
        print(f"  ❌ Error checking {url}: {e}")
        return False


def download_file(url: str, output_path: Path) -> bool:
    """Download file from URL"""
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

        return True
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False


def convert_mobi_to_pdf(mobi_path: Path) -> Path | None:
    """Convert MOBI to PDF using Calibre ebook-convert"""
    try:
        pdf_path = mobi_path.with_suffix(".converted.pdf")

        result = subprocess.run(
            ["ebook-convert", str(mobi_path), str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            print(f"  ❌ Conversion failed: {result.stderr}")
            return None

        return pdf_path
    except Exception as e:
        print(f"  ❌ Conversion error: {e}")
        return None


def upload_to_r2(file_path: Path, r2_key: str) -> str | None:
    """Upload file to R2 and return public URL"""
    try:
        with open(file_path, "rb") as f:
            s3_client.put_object(
                Bucket=R2_BUCKET,
                Key=r2_key,
                Body=f,
                ContentType="application/pdf",
            )

        url = f"https://static.wordai.pro/{r2_key}"
        return url
    except Exception as e:
        print(f"  ❌ Upload failed: {e}")
        return None


def process_chapter(chapter):
    """Process a single chapter - check if MOBI and convert if needed"""
    chapter_id = chapter["chapter_id"]
    pdf_url = chapter["pdf_url"]
    book_id = chapter["book_id"]

    print(f"\n📖 Processing chapter {chapter_id} (book: {book_id})")
    print(f"   URL: {pdf_url}")

    # Check if file is actually MOBI
    if not is_mobi_file(pdf_url):
        print(f"   ✅ Already valid PDF, skipping")
        return {"status": "skip", "reason": "valid_pdf"}

    print(f"   ⚠️  Detected MOBI file disguised as PDF!")

    # Create temp directory
    temp_dir = Path("temp_mobi_conversion")
    temp_dir.mkdir(exist_ok=True)

    # Download MOBI file
    mobi_path = temp_dir / f"{chapter_id}.mobi"
    print(f"   ⬇️  Downloading MOBI...")
    if not download_file(pdf_url, mobi_path):
        return {"status": "error", "reason": "download_failed"}

    # Convert to PDF
    print(f"   🔄 Converting MOBI → PDF...")
    pdf_path = convert_mobi_to_pdf(mobi_path)
    if not pdf_path:
        mobi_path.unlink(missing_ok=True)
        return {"status": "error", "reason": "conversion_failed"}

    # Upload to R2
    timestamp = int(datetime.now().timestamp())
    r2_key = f"books/crawled-converted/{timestamp}_{book_id}_{chapter_id}.pdf"
    print(f"   ⬆️  Uploading to R2...")
    new_url = upload_to_r2(pdf_path, r2_key)

    # Cleanup temp files
    mobi_path.unlink(missing_ok=True)
    pdf_path.unlink(missing_ok=True)

    if not new_url:
        return {"status": "error", "reason": "upload_failed"}

    # Update MongoDB
    print(f"   💾 Updating MongoDB...")
    db.book_chapters.update_one(
        {"chapter_id": chapter_id},
        {
            "$set": {
                "pdf_url": new_url,
                "original_mobi_url": pdf_url,
                "converted_at": datetime.utcnow(),
            }
        },
    )

    print(f"   ✅ Successfully converted and updated!")
    print(f"   New URL: {new_url}")

    return {"status": "success", "new_url": new_url, "old_url": pdf_url}


def main():
    """Main function to process all chapters"""
    print("🔍 Finding chapters with PDF URLs from crawled books...")

    # Get all chapters with crawled PDF URLs
    chapters = list(
        db.book_chapters.find(
            {"pdf_url": {"$regex": "crawled.*\\.pdf"}},
            {"chapter_id": 1, "book_id": 1, "pdf_url": 1},
        )
    )

    total = len(chapters)
    print(f"📊 Found {total} chapters to check\n")

    stats = {
        "total": total,
        "valid_pdf": 0,
        "converted": 0,
        "errors": 0,
    }

    for i, chapter in enumerate(chapters, 1):
        print(f"\n{'='*70}")
        print(f"Progress: {i}/{total} ({i*100//total}%)")

        result = process_chapter(chapter)

        if result["status"] == "skip":
            stats["valid_pdf"] += 1
        elif result["status"] == "success":
            stats["converted"] += 1
        else:
            stats["errors"] += 1

        # Print progress summary every 10 items
        if i % 10 == 0:
            print(f"\n📈 Progress Summary:")
            print(f"   Valid PDFs: {stats['valid_pdf']}")
            print(f"   Converted: {stats['converted']}")
            print(f"   Errors: {stats['errors']}")

    # Final summary
    print(f"\n{'='*70}")
    print(f"✅ CONVERSION COMPLETE!")
    print(f"\n📊 Final Statistics:")
    print(f"   Total checked: {stats['total']}")
    print(f"   Valid PDFs (no action needed): {stats['valid_pdf']}")
    print(f"   Successfully converted: {stats['converted']}")
    print(f"   Errors: {stats['errors']}")

    # Cleanup temp directory
    temp_dir = Path("temp_mobi_conversion")
    if temp_dir.exists():
        temp_dir.rmdir()


if __name__ == "__main__":
    main()
