#!/usr/bin/env python3
"""
POC Book Crawler - Test with 5 books from nhasachmienphi.com
Usage: python crawler/test_crawler.py
"""

import os
import re
import time
import asyncio
import uuid
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from unidecode import unidecode

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# WordAI imports
from src.database.db_manager import DBManager
from src.services.r2_storage_service import get_r2_service


class TestBookCrawler:
    """POC Crawler - Test 5 books from Văn Học Việt Nam category"""

    def __init__(self, download_dir: str = "/tmp/crawler_downloads"):
        self.base_url = "https://nhasachmienphi.com"
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Database setup
        db_manager = DBManager()
        self.db = db_manager.db
        self.r2_service = get_r2_service()

        # System user & author
        self.SYSTEM_USER_ID = "system_crawler_uid"
        self.FIXED_AUTHOR_ID = "@sachonline"

        # Selenium setup
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Run in background
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=options)

        print(f"🚀 Crawler initialized")
        print(f"   Download dir: {self.download_dir}")
        print(f"   System user: {self.SYSTEM_USER_ID}")
        print(f"   Author: {self.FIXED_AUTHOR_ID}")

    def crawl_test_books(self, limit: int = 5) -> List[str]:
        """
        Crawl test books from Văn Học Việt Nam category

        Returns:
            List of created book IDs
        """
        print(f"\n📚 Starting POC crawl: {limit} books from Văn Học Việt Nam")

        # Target category
        category_url = f"{self.base_url}/danh-muc/van-hoc-viet-nam"

        try:
            book_ids = []
            self.driver.get(category_url)
            time.sleep(2)  # Wait for page load

            # Find book links
            book_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "a[href*='/sach/']"
            )[:limit]

            if not book_elements:
                print("❌ No books found in category!")
                return []

            print(f"✅ Found {len(book_elements)} books to crawl\n")

            # Process each book
            for idx, elem in enumerate(book_elements, 1):
                book_url = elem.get_attribute("href")
                print(f"\n[{idx}/{limit}] Processing: {book_url}")

                try:
                    book_id = self.process_single_book(book_url)
                    if book_id:
                        book_ids.append(book_id)
                        print(f"   ✅ Success: {book_id}")
                    else:
                        print(f"   ❌ Failed to process book")
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    continue

                # Rate limiting
                time.sleep(2)

            return book_ids

        finally:
            self.driver.quit()

    def process_single_book(self, url: str) -> Optional[str]:
        """Process one book: crawl → download → upload → create book"""

        # 1. Crawl metadata
        book_data = self.crawl_book_detail(url)
        if not book_data:
            return None

        print(f"   📖 Title: {book_data['title']}")

        # 2. Download PDF/MOBI
        pdf_path = self.download_and_convert_book(book_data)
        if not pdf_path:
            return None

        print(f"   💾 Downloaded: {pdf_path.name}")

        # 3. Upload to WordAI
        book_id = asyncio.run(self.upload_book(book_data, pdf_path))

        # 4. Cleanup
        pdf_path.unlink()  # Delete local file

        return book_id

    def crawl_book_detail(self, url: str) -> Optional[Dict]:
        """Extract book metadata from detail page"""

        try:
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 10)

            # Extract metadata (adjust selectors based on actual site structure)
            title = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1, .book-title"))
            ).text

            # Try to get description
            try:
                description = self.driver.find_element(
                    By.CSS_SELECTOR, ".book-description, .summary, .content"
                ).text
            except NoSuchElementException:
                description = f"Sách {title}"

            # Try to get cover image
            try:
                cover_url = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "img[src*='cover'], .book-cover img, .thumbnail img",
                ).get_attribute("src")
            except NoSuchElementException:
                cover_url = None

            # Find download links
            download_links = {}

            # Check for Google Drive links
            try:
                gdrive_elements = self.driver.find_elements(
                    By.XPATH, "//a[contains(@href, 'drive.google.com')]"
                )
                if gdrive_elements:
                    download_links["google_drive"] = gdrive_elements[0].get_attribute(
                        "href"
                    )
            except:
                pass

            # Check for direct download buttons
            try:
                pdf_buttons = self.driver.find_elements(
                    By.XPATH, "//a[contains(text(), 'PDF') or contains(@href, '.pdf')]"
                )
                if pdf_buttons:
                    download_links["pdf"] = pdf_buttons[0].get_attribute("href")
            except:
                pass

            try:
                mobi_buttons = self.driver.find_elements(
                    By.XPATH,
                    "//a[contains(text(), 'MOBI') or contains(@href, '.mobi')]",
                )
                if mobi_buttons:
                    download_links["mobi"] = mobi_buttons[0].get_attribute("href")
            except:
                pass

            if not download_links:
                print("   ⚠️  No download links found")
                return None

            return {
                "title": title.strip(),
                "description": description.strip()[:500],  # Limit length
                "cover_url": cover_url,
                "download_links": download_links,
                "source_url": url,
                "category": "van-hoc-viet-nam",
            }

        except Exception as e:
            print(f"   ❌ Crawl error: {e}")
            return None

    def download_and_convert_book(self, book_data: Dict) -> Optional[Path]:
        """Download book file and convert to PDF if needed"""

        safe_title = self._slugify(book_data["title"])
        pdf_path = self.download_dir / f"{safe_title}.pdf"
        mobi_path = self.download_dir / f"{safe_title}.mobi"

        download_links = book_data["download_links"]

        # Priority: PDF > Google Drive > MOBI

        # Case 1: Direct PDF
        if "pdf" in download_links:
            if self._download_file(download_links["pdf"], pdf_path):
                return pdf_path

        # Case 2: Google Drive
        if "google_drive" in download_links:
            if self._download_from_google_drive(
                download_links["google_drive"], pdf_path
            ):
                return pdf_path

        # Case 3: MOBI (convert to PDF)
        if "mobi" in download_links:
            if self._download_file(download_links["mobi"], mobi_path):
                if self._convert_mobi_to_pdf(mobi_path, pdf_path):
                    return pdf_path

        return None

    def _download_file(self, url: str, output_path: Path) -> bool:
        """Download file via HTTP"""
        import requests

        try:
            print(f"   ⬇️  Downloading: {url[:50]}...")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return True
        except Exception as e:
            print(f"   ❌ Download failed: {e}")
            return False

    def _download_from_google_drive(self, url: str, output_path: Path) -> bool:
        """Download from Google Drive using gdown"""
        import gdown
        import tempfile
        import shutil

        try:
            # Extract file/folder ID
            file_match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
            folder_match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)

            if file_match:
                # Single file
                file_id = file_match.group(1)
                gdown_url = f"https://drive.google.com/uc?id={file_id}"
                gdown.download(gdown_url, str(output_path), quiet=False)
                return True

            elif folder_match:
                # Folder - get first PDF
                folder_id = folder_match.group(1)
                folder_url = f"https://drive.google.com/drive/folders/{folder_id}"

                with tempfile.TemporaryDirectory() as temp_dir:
                    gdown.download_folder(folder_url, output=temp_dir, quiet=False)

                    # Find first PDF
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if file.lower().endswith(".pdf"):
                                src_path = Path(root) / file
                                shutil.copy(src_path, output_path)
                                print(f"   ✅ Found PDF in folder: {file}")
                                return True

                print(f"   ❌ No PDF in Google Drive folder")
                return False

            return False

        except Exception as e:
            print(f"   ❌ Google Drive download failed: {e}")
            return False

    def _convert_mobi_to_pdf(self, mobi_path: Path, pdf_path: Path) -> bool:
        """Convert MOBI to PDF using Calibre"""

        try:
            # Check if Calibre installed
            subprocess.run(
                ["ebook-convert", "--version"], capture_output=True, check=True
            )

            print(f"   🔄 Converting MOBI to PDF...")
            result = subprocess.run(
                [
                    "ebook-convert",
                    str(mobi_path),
                    str(pdf_path),
                    "--paper-size",
                    "a4",
                    "--pdf-page-margin-left",
                    "36",
                    "--pdf-page-margin-right",
                    "36",
                    "--pdf-page-margin-top",
                    "36",
                    "--pdf-page-margin-bottom",
                    "36",
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                mobi_path.unlink()  # Delete MOBI
                return True
            else:
                print(f"   ❌ Conversion failed: {result.stderr}")
                return False

        except (subprocess.CalledProcessError, FileNotFoundError):
            print("   ❌ Calibre not installed. Install with: brew install calibre")
            return False
        except subprocess.TimeoutExpired:
            print("   ❌ Conversion timeout (>5 min)")
            return False

    async def upload_book(self, book_data: Dict, pdf_path: Path) -> str:
        """Upload book to WordAI database"""

        # 1. Upload PDF to R2
        file_id = await self._upload_pdf_to_r2(pdf_path, book_data["title"])

        # 2. Create book document
        book_id = await self._create_book(book_data, file_id)

        # 3. Create chapter
        chapter_id = await self._create_chapter(book_id, file_id, book_data["title"])

        return book_id

    async def _upload_pdf_to_r2(self, pdf_path: Path, title: str) -> str:
        """Upload PDF to R2 storage"""

        with open(pdf_path, "rb") as f:
            file_content = f.read()

        file_id = f"file_{uuid.uuid4().hex[:12]}"
        filename = f"{self._slugify(title)}.pdf"
        r2_key = f"files/{self.SYSTEM_USER_ID}/root/{file_id}/{filename}"

        await self.r2_service.upload_file(
            file_content=file_content, r2_key=r2_key, content_type="application/pdf"
        )

        public_url = f"https://static.wordai.pro/{r2_key}"

        # Save to user_files
        self.db.user_files.insert_one(
            {
                "file_id": file_id,
                "user_id": self.SYSTEM_USER_ID,
                "filename": filename,
                "original_name": filename,
                "file_type": ".pdf",
                "file_size": len(file_content),
                "r2_key": r2_key,
                "public_url": public_url,
                "is_deleted": False,
                "uploaded_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        return file_id

    async def _create_book(self, book_data: Dict, file_id: str) -> str:
        """Create book in online_books collection"""

        book_id = f"book_{uuid.uuid4().hex[:12]}"
        slug = self._slugify(book_data["title"])

        book_doc = {
            "_id": book_id,
            "book_id": book_id,
            "user_id": self.SYSTEM_USER_ID,
            # Basic info
            "title": book_data["title"],
            "description": book_data["description"],
            "slug": slug,
            # Author
            "authors": [self.FIXED_AUTHOR_ID],
            # Visibility & Access
            "visibility": "point_based",
            "is_published": True,
            "is_preview_free": False,
            # Pricing (1pt one-time, 3pt forever, no download)
            "access_pricing": {
                "one_time_points": 1,
                "forever_points": 3,
                "download_enabled": False,
            },
            # Category & Tags
            "category": book_data["category"],
            "tags": [book_data["category"], "văn học", "sách miễn phí"],
            # Cover
            "cover_url": book_data.get("cover_url"),
            # Stats
            "total_chapters": 1,
            "total_views": 0,
            "total_purchases": 0,
            # Source
            "source": {
                "crawler": "nhasachmienphi.com",
                "url": book_data["source_url"],
                "crawled_at": datetime.utcnow(),
            },
            # Timestamps
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        self.db.online_books.insert_one(book_doc)
        return book_id

    async def _create_chapter(self, book_id: str, file_id: str, title: str) -> str:
        """Create chapter with pdf_file mode"""

        chapter_id = f"chapter_{uuid.uuid4().hex[:12]}"

        # Get public URL from user_files
        file_doc = self.db.user_files.find_one({"file_id": file_id})
        public_url = file_doc["public_url"]

        chapter_doc = {
            "_id": chapter_id,
            "chapter_id": chapter_id,
            "book_id": book_id,
            "user_id": self.SYSTEM_USER_ID,
            # Chapter info
            "title": "Nội Dung Sách",
            "chapter_number": 1,
            "order_index": 0,
            # PDF file mode
            "content_mode": "pdf_file",
            "pdf_url": public_url,
            # No pages array (pdf_file mode)
            "total_pages": 0,
            # Visibility
            "is_published": True,
            "is_preview": False,
            # Timestamps
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        self.db.book_chapters.insert_one(chapter_doc)

        # Update file usage
        self.db.user_files.update_one(
            {"file_id": file_id}, {"$set": {"used_in_chapter": chapter_id}}
        )

        return chapter_id

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug"""
        text = unidecode(text).lower()
        text = re.sub(r"[^a-z0-9]+", "-", text)
        return text.strip("-")[:50]  # Limit length


def main():
    """Run POC crawler test"""

    print("=" * 60)
    print("📚 POC Book Crawler - Test 5 Books")
    print("=" * 60)

    crawler = TestBookCrawler()

    try:
        book_ids = crawler.crawl_test_books(limit=5)

        print("\n" + "=" * 60)
        print("📊 CRAWL SUMMARY")
        print("=" * 60)
        print(f"✅ Successfully crawled: {len(book_ids)} books")

        if book_ids:
            print(f"\n📖 Created Book IDs:")
            for book_id in book_ids:
                print(f"   - {book_id}")

            print(f"\n🔗 View in community marketplace:")
            print(f"   https://wordai.pro/community")
        else:
            print(f"❌ No books were successfully crawled")

        print("\n" + "=" * 60)

    except KeyboardInterrupt:
        print("\n\n⚠️  Crawler interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Crawler error: {e}")
        raise


if __name__ == "__main__":
    main()
