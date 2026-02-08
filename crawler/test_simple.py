#!/usr/bin/env python3
"""POC Book Crawler - nhasachmienphi.com"""

import time, uuid, requests, os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from playwright.sync_api import sync_playwright
from src.database.db_manager import DBManager
import boto3
from botocore.client import Config


class TestBookCrawler:
    def __init__(self, download_dir="/tmp/crawler_downloads"):
        self.base_url = "https://nhasachmienphi.com"
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        db_manager = DBManager()
        self.db = db_manager.db

        # Init boto3 S3 client trực tiếp (sync)
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        self.bucket_name = os.getenv("R2_BUCKET_NAME", "wordai-documents")

        # Get @sachonline author và user_id của owner
        author = self.db.authors.find_one({"author_id": "@sachonline"})
        if not author:
            raise ValueError("❌ Author @sachonline not found! Run setup_crawler_system_user.py first")

        # Tìm user_id của @michael (owner system) để làm owner cho books
        michael = self.db.authors.find_one({"author_id": "@michael"})
        if not michael or not michael.get("user_id"):
            raise ValueError("❌ @michael user_id not found!")

        self.OWNER_USER_ID = michael["user_id"]  # Owner của books (index requirement)
        self.AUTHOR_ID = "@sachonline"  # Author hiển thị

        print(f"🚀 Crawler initialized")
        print(f"   Owner: @michael ({self.OWNER_USER_ID})")
        print(f"   Author: {self.AUTHOR_ID}")
                book_links = []
                for elem in page.query_selector_all("a[href$='.html']"):
                    href = elem.get_attribute("href")
                    if href and not href.startswith("http"):
                        href = f"{self.base_url}{href}"
                    if href and href not in book_links:
                        book_links.append(href)

                if not book_links:
                    print("❌ No books found!")
                    return []

                book_links = book_links[:limit]
                print(f"✅ Found {len(book_links)} books\n")

                for idx, book_url in enumerate(book_links, 1):
                    print(f"\n[{idx}/{limit}] {book_url}")

                    try:
                        book_id = self.process_single_book(page, book_url)
                        if book_id:
                            book_ids.append(book_id)
                            print(f"   ✅ Success: {book_id}")
                        else:
                            print(f"   ❌ Failed")
                    except Exception as e:
                        print(f"   ❌ Error: {e}")

                    time.sleep(2)

                return book_ids

            except Exception as e:
                print(f"❌ Fatal: {e}")
                import traceback

                traceback.print_exc()
                return []
            finally:
                browser.close()

    def process_single_book(self, page, url):
        book_data = self.crawl_book_detail(page, url)
        if not book_data:
            return None

        print(f"   📖 {book_data['title']}")

        pdf_path = self.download_pdf(book_data["pdf_url"], book_data["slug"])
        if not pdf_path:
            return None

        print(f"   ✅ Downloaded: {pdf_path.name}")

        r2_key = self.upload_to_r2(pdf_path)
        if not r2_key:
            return None

        print(f"   ✅ R2: {r2_key}")

        book_id = self.create_book(book_data, r2_key)
        pdf_path.unlink(missing_ok=True)

        return book_id

    def crawl_book_detail(self, page, url):
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(1)

            title_elem = page.query_selector("h1")
            title = title_elem.inner_text().strip() if title_elem else page.title()

            desc_elem = page.query_selector(".entry-content p")
            description = desc_elem.inner_text().strip() if desc_elem else ""

            # Tìm PDF link trong HTML content bằng regex
            import re

            html_content = page.content()
            pdf_matches = re.findall(
                r'href=["\']([^"\']*/[^"\']*.pdf)["\']', html_content
            )

            pdf_link = pdf_matches[0] if pdf_matches else None

            if not pdf_link:
                print("   ⚠️ No PDF link")
                return None

            slug = url.split("/")[-1].replace(".html", "")

            return {
                "title": title,
                "description": description[:500],
                "pdf_url": pdf_link,
                "slug": slug,
                "source_url": url,
            }

        except Exception as e:
            print(f"   ❌ Crawl failed: {e}")
            return None

    def download_pdf(self, pdf_url, slug):
        try:
            r = requests.get(pdf_url, stream=True, timeout=60)
            r.raise_for_status()

            pdf_path = self.download_dir / f"{slug}.pdf"

            with open(pdf_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

            return pdf_path

        except Exception as e:
            print(f"   ❌ Download failed: {e}")
            return None

    def upload_to_r2(self, pdf_path):
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            r2_key = f"books/crawled/{ts}_{pdf_path.name}"

            with open(pdf_path, "rb") as f:
                content = f.read()

            # Upload trực tiếp bằng boto3 (sync)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=r2_key,
                Body=content,
                ContentType="application/pdf",
            )

            return r2_key

        except Exception as e:
            print(f"   ❌ R2 failed: {e}")
            return None

    def create_book(self, book_data, r2_key):
        try:
            book_id = f"book_{uuid.uuid4().hex[:12]}"
            chapter_id = str(uuid.uuid4())
            pub_url = f"https://static.wordai.pro/{r2_key}"

            # Tạo slug từ source slug (unique per user)
            slug = book_data["slug"]

            # Follow BookManager.create_book() schema
            book_doc = {
                "book_id": book_id,
                "user_id": self.OWNER_USER_ID,  # REQUIRED by unique index
                "title": book_data["title"],
                "slug": slug,  # REQUIRED by unique index
                "description": book_data["description"],
                "visibility": "public",
                "is_published": False,  # Chưa publish community
                "is_deleted": False,

                # Authors list (for community display)
                "authors": [self.AUTHOR_ID],

                # Community config
                "community_config": {
                    "is_public": False,
                    "category": None,
                    "tags": ["nhasachmienphi"],
                    "short_description": book_data["description"][:200] if book_data["description"] else None,
                    "difficulty_level": None,
                    "cover_image_url": None,
                    "total_views": 0,
                    "total_downloads": 0,
                    "total_purchases": 0,
                    "average_rating": 0.0,
                    "rating_count": 0,
                    "version": "1.0.0",
                    "published_at": None,
                },

                # Stats
                "stats": {
                    "total_revenue_points": 0,
                    "owner_reward_points": 0,
                    "system_fee_points": 0,
                },

                # Branding
                "cover_image_url": None,
                "logo_url": None,
                "primary_color": "#4F46E5",
                "is_indexed": True,
                "meta_title": None,
                "meta_description": None,
                "custom_domain": None,

                # Analytics
                "view_count": 0,
                "unique_visitors": 0,

                # Timestamps
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_published_at": None,

                # Crawler metadata
                "source": "nhasachmienphi.com",
                "source_url": book_data["source_url"],
            }

            chapter_doc = {
                "_id": chapter_id,
                "book_id": book_id,
                "chapter_number": 1,
                "title": "Full Book",
                "content_type": "pdf_file",
                "pdf_file": {
                    "r2_key": r2_key,
                    "public_url": pub_url,
                    "filename": Path(r2_key).name,
                    "file_size": 0,
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            self.db.online_books.insert_one(book_doc)
            self.db.book_chapters.insert_one(chapter_doc)

            return book_id

        except Exception as e:
            print(f"   ❌ Create failed: {e}")
            return None


def main():
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
