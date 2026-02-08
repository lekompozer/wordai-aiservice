#!/usr/bin/env python3
"""
POC Book Crawler - nhasachmienphi.com với Playwright
Crawl test 5 sách từ category Văn Học Việt Nam
"""

import os
import re
import time
import asyncio
import uuid
import requests
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from unidecode import unidecode

# Playwright imports
from playwright.sync_api import sync_playwright

# WordAI imports
from src.database.db_manager import DBManager
from src.services.r2_storage_service import get_r2_service


class TestBookCrawler:
    """POC Crawler - Crawl sách từ nhasachmienphi.com"""

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

        print(f"🚀 Crawler initialized")
        print(f"   Download dir: {self.download_dir}")
        print(f"   System user: {self.SYSTEM_USER_ID}")
        print(f"   Author: {self.FIXED_AUTHOR_ID}")

    def crawl_test_books(self, limit: int = 5) -> List[str]:
        """
        Crawl test books from Văn Học Việt Nam category

        Args:
            limit: Số sách cần crawl (mặc định 5)

        Returns:
            List of created book IDs
        """
        print(f"\n📚 Starting POC crawl: {limit} books from Văn Học Việt Nam")

        print("   🔧 Initializing Playwright...")
        with sync_playwright() as p:
            print("   ✅ Playwright started")
            browser = p.chromium.launch(headless=True)
            print("   ✅ Browser launched")
            page = browser.new_page()
            print("   ✅ Page created")
                elements = page.query_selector_all("a[href$='.html']")

                for elem in elements:
                    href = elem.get_attribute("href")
                    if href and not href.startswith("http"):
                        href = f"{self.base_url}{href}"
                    if href and href not in book_links:
                        book_links.append(href)

                if not book_links:
                    print("❌ No books found in category!")
                    return []

                # Giới hạn số sách
                book_links = book_links[:limit]
                print(f"✅ Found {len(book_links)} books to crawl\n")

                # Process từng sách
                for idx, book_url in enumerate(book_links, 1):
                    print(f"\n[{idx}/{limit}] Processing: {book_url}")

                    try:
                        book_id = self.process_single_book(page, book_url)
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

            except Exception as e:
                print(f"❌ Fatal error: {e}")
                import traceback

                traceback.print_exc()
                return []
            finally:
                browser.close()

    def process_single_book(self, page, url: str) -> Optional[str]:
        """Process một sách: crawl → download PDF → upload → create book"""

        # 1. Crawl metadata từ trang sách
        book_data = self.crawl_book_detail(page, url)
        if not book_data:
            return None

        print(f"   📖 Title: {book_data['title']}")

        # 2. Download PDF
        pdf_path = self.download_pdf(book_data["pdf_url"], book_data["slug"])
        if not pdf_path:
            print(f"   ❌ Failed to download PDF")
            return None

        print(f"   ✅ Downloaded: {pdf_path.name}")

        # 3. Upload to R2
        r2_key = self.upload_to_r2(pdf_path)
        if not r2_key:
            print(f"   ❌ Failed to upload to R2")
            return None

        print(f"   ✅ Uploaded to R2: {r2_key}")

        # 4. Create book + chapter
        book_id = self.create_book_and_chapter(book_data, r2_key)

        # 5. Cleanup
        pdf_path.unlink(missing_ok=True)

        return book_id

    def crawl_book_detail(self, page, url: str) -> Optional[Dict]:
        """Crawl metadata từ trang chi tiết sách"""

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(1)

            # Lấy title (h1 hoặc title tag)
            title_elem = page.query_selector("h1")
            title = title_elem.inner_text().strip() if title_elem else page.title()

            # Lấy description
            desc_elem = page.query_selector(".entry-content p, .summary, article p")
            description = desc_elem.inner_text().strip() if desc_elem else ""

            # Lấy PDF download link (pattern: https://file.nhasachmienphi.com/pdf/...)
            pdf_link = None
            pdf_elements = page.query_selector_all(
                "a[href*='.pdf'], a[href*='file.nhasachmienphi.com']"
            )

            for elem in pdf_elements:
                href = elem.get_attribute("href")
                if href and ".pdf" in href:
                    pdf_link = href
                    break

            if not pdf_link:
                print(f"   ⚠️ No PDF link found")
                return None

            # Tạo slug từ URL hoặc title
            slug = url.split("/")[-1].replace(".html", "")

            return {
                "title": title,
                "description": description[:500] if description else f"Sách {title}",
                "pdf_url": pdf_link,
                "slug": slug,
                "source_url": url,
            }

        except Exception as e:
            print(f"   ❌ Failed to crawl book detail: {e}")
            return None

    def download_pdf(self, pdf_url: str, slug: str) -> Optional[Path]:
        """Download PDF file"""

        try:
            response = requests.get(pdf_url, stream=True, timeout=60)
            response.raise_for_status()

            # Save to temp file
            pdf_path = self.download_dir / f"{slug}.pdf"

            with open(pdf_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return pdf_path

        except Exception as e:
            print(f"   ❌ Download failed: {e}")
            return None

    def upload_to_r2(self, pdf_path: Path) -> Optional[str]:
        """Upload PDF to R2 storage"""

        try:
            # Generate R2 key
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            r2_key = f"books/crawled/{timestamp}_{pdf_path.name}"

            # Upload
            with open(pdf_path, "rb") as f:
                file_content = f.read()

            # Call async upload
            asyncio.run(self.r2_service.upload_file(
                file_content=file_content, r2_key=r2_key, content_type="application/pdf"
            ))

            return r2_key

        except Exception as e:
            print(f"   ❌ R2 upload failed: {e}")
            return None

    def create_book_and_chapter(self, book_data: Dict, r2_key: str) -> Optional[str]:
        """Create book và chapter trong database"""

        try:
            book_id = str(uuid.uuid4())
            chapter_id = str(uuid.uuid4())

            # Public URL
            public_url = f"https://static.wordai.pro/{r2_key}"

            # Create book document
            book_doc = {
                "_id": book_id,
                "title": book_data["title"],
                "description": book_data["description"],
                "author_id": self.FIXED_AUTHOR_ID,
                "category_slugs": ["van-hoc-viet-nam"],
                "cover_image_url": None,  # TODO: crawl cover image
                "is_published": True,
                "is_featured": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": self.SYSTEM_USER_ID,
                "source": "nhasachmienphi.com",
                "source_url": book_data["source_url"],
            }

            # Create chapter document
            chapter_doc = {
                "_id": chapter_id,
                "book_id": book_id,
                "chapter_number": 1,
                "title": "Full Book",
                "content_type": "pdf_file",
                "pdf_file": {
                    "r2_key": r2_key,
                    "public_url": public_url,
                    "filename": Path(r2_key).name,
                    "file_size": 0,  # TODO: get actual size
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": self.SYSTEM_USER_ID,
            }

            # Insert vào DB
            self.db.online_books.insert_one(book_doc)
            self.db.book_chapters.insert_one(chapter_doc)

            return book_id

        except Exception as e:
            print(f"   ❌ Failed to create book: {e}")
            return None


def main():
    """Main entry point"""
    print("=" * 60)
    print("📚 POC Book Crawler - Test 5 Books")
    print("=" * 60)

    crawler = TestBookCrawler()
    book_ids = crawler.crawl_test_books(limit=5)

    print("\n" + "=" * 60)
    print("📊 CRAWL SUMMARY")
    print("=" * 60)

    if book_ids:
        print(f"✅ Successfully crawled: {len(book_ids)} books")
        for idx, book_id in enumerate(book_ids, 1):
            print(f"   {idx}. {book_id}")
    else:
        print("❌ No books were successfully crawled")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
