"""
Category Crawler with Pagination and Duplicate Detection
Crawls all books from a nhasachmienphi.com category with:
- Pagination support
- Duplicate checking by book name
- Skip existing books
"""

import os
import sys
import re
import time
import boto3
import hashlib
import requests
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from playwright.sync_api import sync_playwright, Page, Browser
from botocore.client import Config

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database.db_manager import DBManager
from src.constants.book_categories import map_nhasachmienphi_category


class CategoryCrawler:
    """Crawler for nhasachmienphi.com with pagination and duplicate detection"""

    def __init__(self):
        """Initialize crawler with DB and R2 connections"""
        # Database connection
        self.db_manager = DBManager()
        self.db = self.db_manager.db

        # Get Michael user_id (owner)
        michael = self.db.authors.find_one({"author_id": "@michael"})
        if not michael or not michael.get("user_id"):
            raise ValueError("❌ @michael not found!")

        self.OWNER_USER_ID = michael["user_id"]
        self.AUTHOR_ID = "@sachonline"

        print(f"🚀 Crawler initialized")
        print(f"   Owner: {self.OWNER_USER_ID}")
        print(f"   Author: {self.AUTHOR_ID}")

        # R2/S3 connection (sync client) - use env vars
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        self.r2_bucket = os.getenv("R2_BUCKET_NAME", "wordai-documents")

        # Stats
        self.stats = {
            "total_found": 0,
            "skipped_existing": 0,
            "downloaded_new": 0,
            "failed": 0,
        }

    def check_book_exists(
        self, book_title: str, book_slug: Optional[str] = None
    ) -> bool:
        """Check if book already exists in database by title AND slug"""
        # Check by title (case-insensitive, exact match)
        title_exists = self.db.online_books.find_one(
            {"title": {"$regex": f"^{re.escape(book_title)}$", "$options": "i"}}
        )

        # Also check by slug if provided (more reliable)
        if book_slug:
            slug_exists = self.db.online_books.find_one({"slug": book_slug})
            if slug_exists:
                return True

        return title_exists is not None

    def create_slug(self, text: str) -> str:
        """Create URL-friendly slug from text"""
        # Vietnamese character mapping
        replacements = {
            "à": "a",
            "á": "a",
            "ả": "a",
            "ã": "a",
            "ạ": "a",
            "ă": "a",
            "ằ": "a",
            "ắ": "a",
            "ẳ": "a",
            "ẵ": "a",
            "ặ": "a",
            "â": "a",
            "ầ": "a",
            "ấ": "a",
            "ẩ": "a",
            "ẫ": "a",
            "ậ": "a",
            "è": "e",
            "é": "e",
            "ẻ": "e",
            "ẽ": "e",
            "ẹ": "e",
            "ê": "e",
            "ề": "e",
            "ế": "e",
            "ể": "e",
            "ễ": "e",
            "ệ": "e",
            "ì": "i",
            "í": "i",
            "ỉ": "i",
            "ĩ": "i",
            "ị": "i",
            "ò": "o",
            "ó": "o",
            "ỏ": "o",
            "õ": "o",
            "ọ": "o",
            "ô": "o",
            "ồ": "o",
            "ố": "o",
            "ổ": "o",
            "ỗ": "o",
            "ộ": "o",
            "ơ": "o",
            "ờ": "o",
            "ớ": "o",
            "ở": "o",
            "ỡ": "o",
            "ợ": "o",
            "ù": "u",
            "ú": "u",
            "ủ": "u",
            "ũ": "u",
            "ụ": "u",
            "ư": "u",
            "ừ": "u",
            "ứ": "u",
            "ử": "u",
            "ữ": "u",
            "ự": "u",
            "ỳ": "y",
            "ý": "y",
            "ỷ": "y",
            "ỹ": "y",
            "ỵ": "y",
            "đ": "d",
            "Đ": "d",
        }

        text = text.lower()
        for viet, eng in replacements.items():
            text = text.replace(viet, eng)

        text = re.sub(r"[^a-z0-9\s-]", "", text)
        text = re.sub(r"[\s-]+", "-", text)
        text = text.strip("-")

        return text

    def download_and_upload_cover(self, cover_url: str, slug: str) -> str:
        """Download cover image and upload to R2"""
        try:
            response = requests.get(cover_url, timeout=30)
            response.raise_for_status()

            # Auto-detect image format
            content_type = response.headers.get("content-type", "").lower()
            if "webp" in content_type:
                ext = "webp"
            elif "jpeg" in content_type or "jpg" in content_type:
                ext = "jpg"
            elif "png" in content_type:
                ext = "png"
            else:
                ext = "jpg"  # default

            # Upload to R2
            timestamp = int(time.time())
            r2_key = f"books/covers/{timestamp}_{slug}.{ext}"

            self.s3_client.put_object(
                Bucket=self.r2_bucket,
                Key=r2_key,
                Body=response.content,
                ContentType=content_type,
            )

            r2_url = f"https://static.wordai.pro/{r2_key}"
            print(f"  ✅ Cover uploaded: {r2_url}")
            return r2_url

        except Exception as e:
            print(f"  ⚠️  Cover upload failed: {e}")
            return cover_url  # Fallback to original URL

    def upload_pdf_to_r2(self, pdf_path: Path) -> str:
        """Upload PDF to R2 and return public URL"""
        try:
            timestamp = int(time.time())
            r2_key = f"books/crawled/{timestamp}_{pdf_path.name}"

            with open(pdf_path, "rb") as f:
                self.s3_client.put_object(
                    Bucket=self.r2_bucket,
                    Key=r2_key,
                    Body=f.read(),
                    ContentType="application/pdf",
                )

            r2_url = f"https://static.wordai.pro/{r2_key}"
            print(f"  ✅ PDF uploaded: {r2_url}")
            return r2_url

        except Exception as e:
            print(f"  ❌ PDF upload failed: {e}")
            raise

    def convert_mobi_to_pdf(self, mobi_path: Path) -> Optional[Path]:
        """Convert MOBI to PDF using Calibre ebook-convert"""
        try:
            pdf_path = mobi_path.with_suffix(".pdf")

            # Use Calibre's ebook-convert command
            import subprocess

            result = subprocess.run(
                ["ebook-convert", str(mobi_path), str(pdf_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                print(f"  ❌ MOBI conversion failed: {result.stderr}")
                return None

            # Delete MOBI file after successful conversion
            mobi_path.unlink()

            print(f"  ✅ MOBI converted to PDF: {pdf_path.name}")
            return pdf_path

        except Exception as e:
            print(f"  ❌ MOBI conversion failed: {e}")
            return None

    def download_pdf(
        self, download_url: str, slug: str, file_type: str = "pdf"
    ) -> Optional[Path]:
        """Download PDF from nhasachmienphi using requests (not Playwright)"""
        try:
            # Create download directory
            download_dir = Path(__file__).parent / "downloads"
            download_dir.mkdir(exist_ok=True)

            pdf_path = download_dir / f"{slug}.pdf"

            # Download PDF using requests (avoids anti-bot detection)
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            with open(pdf_path, "wb") as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)

            print(f"  ✅ PDF downloaded: {pdf_path.name}")
            return pdf_path

        except Exception as e:
            print(f"  ❌ PDF download failed: {e}")
            return None

    def extract_book_metadata(
        self, page: Page, book_url: str
    ) -> Optional[Dict[str, Any]]:
        """Extract metadata from book detail page"""
        try:
            page.goto(book_url, wait_until="networkidle", timeout=60000)
            time.sleep(1)

            # Extract title - h1.tblue.fs-20
            title_elem = page.query_selector("h1.tblue.fs-20")
            if not title_elem:
                title_elem = page.query_selector("h1")
            title = title_elem.inner_text().strip() if title_elem else page.title()

            # Extract slug from URL FIRST (for better duplicate check)
            slug = book_url.split("/")[-1].replace(".html", "")

            # Check if exists BEFORE downloading (use both title and slug)
            if self.check_book_exists(title, slug):
                print(f"  ⏭️  Book already exists: {title}")
                self.stats["skipped_existing"] += 1
                return None

            # Extract author - "Tác giả: ..."
            author_name = "Unknown"
            author_divs = page.query_selector_all("div.mg-t-10")
            for div in author_divs:
                text = div.inner_text().strip()
                if text.startswith("Tác giả:"):
                    author_name = text.replace("Tác giả:", "").strip()
                    break

            # Extract category from page - in div.mg-tb-10 containing "Thể loại:"
            nhasach_category_slug = None
            category_divs = page.query_selector_all("div.mg-tb-10")
            for div in category_divs:
                text = div.inner_text().strip()
                if "Thể loại:" in text or "Thể Loại:" in text:
                    category_link = div.query_selector("a[href*='/category/']")
                    if category_link:
                        href = category_link.get_attribute("href")
                        if href:
                            parts = href.rstrip("/").split("/")
                            if parts:
                                nhasach_category_slug = parts[-1]
                    break

            # Map to WordAI categories (child + parent)
            if nhasach_category_slug:
                child_category, parent_category = map_nhasachmienphi_category(
                    nhasach_category_slug
                )
            else:
                child_category = "Khác"
                parent_category = "other"

            # Extract cover image - prioritize /images/thumbnail/ (actual book cover)
            cover_url = None

            # Method 1: Find image with /images/thumbnail/ in src (BEST - actual cover)
            thumbnail_img = page.query_selector("img[src*='/images/thumbnail/']")
            if thumbnail_img:
                cover_url = thumbnail_img.get_attribute("src")

            # Method 2: Fallback to .col-xs-12.col-sm-4 area
            if not cover_url:
                cover_img = page.query_selector(".col-xs-12.col-sm-4 img")
                if cover_img:
                    src = cover_img.get_attribute("src")
                    # Only accept if it's from /images/thumbnail/ (not ads)
                    if src and "/images/thumbnail/" in src:
                        cover_url = src

            # Extract description from .content_p.content_p_al
            description_parts = []
            content_div = page.query_selector(".content_p.content_p_al")
            if content_div:
                paragraphs = content_div.query_selector_all("p")
                for p in paragraphs:
                    # Skip inline related posts
                    if p.query_selector("a.postTitle"):
                        continue

                    text = p.inner_text().strip()
                    if text and len(text) > 30:
                        description_parts.append(text)

            description = "\n\n".join(description_parts) if description_parts else ""

            # Find PDF or MOBI link using regex
            html_content = page.content()
            pdf_matches = re.findall(r'href=["\']([^"\']*\.pdf)["\']', html_content)
            mobi_matches = re.findall(r'href=["\']([^"\']*\.mobi)["\']', html_content)

            download_url = None
            file_type = None

            if pdf_matches:
                download_url = pdf_matches[0]
                file_type = "pdf"
            elif mobi_matches:
                download_url = mobi_matches[0]
                file_type = "mobi"

            if not download_url:
                print(f"  ❌ No PDF/MOBI link found")
                return None

            return {
                "title": title,
                "description": description,
                "cover_url": cover_url,
                "author_name": author_name,
                "child_category": child_category,
                "parent_category": parent_category,
                "download_url": download_url,
                "file_type": file_type,
                "slug": slug,
                "source_url": book_url,
            }

        except Exception as e:
            print(f"  ❌ Metadata extraction failed: {e}")
            return None

    def create_book_and_chapter(
        self, metadata: Dict[str, Any], pdf_r2_url: str, cover_r2_url: str
    ):
        """Create book and chapter documents in MongoDB - EXACT schema from test_crawler_clean.py"""
        try:
            slug = self.create_slug(metadata["title"])
            book_id = f"book_{uuid.uuid4().hex[:12]}"
            chapter_id = str(uuid.uuid4())

            # Generate short description
            short_desc = (
                metadata["description"][:200]
                if metadata["description"]
                else metadata["title"]
            )

            # Generate tags
            tags = []
            if metadata.get("author_name"):
                tags.append(
                    f"tac-gia-{metadata['author_name'].lower().replace(' ', '-')[:30]}"
                )

            # EXACT schema from test_crawler_clean.py create_book()
            book_doc = {
                "book_id": book_id,
                "user_id": self.OWNER_USER_ID,  # Michael's user_id
                "title": metadata["title"],
                "slug": slug,
                "description": metadata["description"],
                "visibility": "point_based",
                "is_published": True,
                "published_at": datetime.utcnow(),
                "is_deleted": False,
                # Authors list (QUAN TRỌNG!)
                "authors": [self.AUTHOR_ID],
                # Book metadata
                "metadata": {
                    "original_author": metadata.get("author_name"),
                    "source": "nhasachmienphi.com",
                    "source_url": metadata.get("source_url"),
                    "source_category": metadata.get("child_category"),
                },
                # Community config with FULL metadata
                "community_config": {
                    "is_public": True,  # PUBLIC để hiện trên author profile!
                    "category": metadata["child_category"],  # Child category name
                    "parent_category": metadata[
                        "parent_category"
                    ],  # Parent category ID
                    "tags": tags,
                    "short_description": short_desc,
                    "difficulty_level": "beginner",
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
                # Access config (pricing)
                "access_config": {
                    "one_time_view_points": 2,  # 2 điểm cho 1 lần đọc
                    "forever_view_points": 5,  # 5 điểm cho đọc mãi mãi
                    "download_pdf_points": 0,
                    "is_one_time_enabled": True,
                    "is_forever_enabled": True,
                    "is_download_enabled": False,
                },
                # Stats
                "stats": {
                    "total_revenue_points": 0,
                    "owner_reward_points": 0,
                    "system_fee_points": 0,
                    "one_time_purchases": 0,
                    "forever_purchases": 0,
                    "pdf_downloads": 0,
                },
                # Branding
                "cover_image_url": cover_r2_url or "",
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
                "last_published_at": datetime.utcnow(),
            }

            # Chapter document - EXACT schema
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

            # Insert to MongoDB
            self.db.online_books.insert_one(book_doc)
            self.db.book_chapters.insert_one(chapter_doc)

            print(f"  ✅ Book created: {metadata['title']}")
            print(f"     Book ID: {book_id}")
            print(f"     Slug: {slug}")
            print(
                f"     Category: {metadata['child_category']} ({metadata['parent_category']})"
            )

            return book_id

        except Exception as e:
            print(f"  ❌ Database insert failed: {e}")
            import traceback

            traceback.print_exc()
            raise

    def crawl_category_page(
        self, page: Page, category_url: str, limit: int = 500
    ) -> List[str]:
        """Extract book URLs from category page with pagination (20 books per page)"""
        book_urls = []
        page_num = 1
        base_url = "https://nhasachmienphi.com"

        while len(book_urls) < limit:
            try:

                # Navigate to page - format: /category/slug/page/2
                if page_num > 1:
                    # Remove trailing slash if exists
                    base_category_url = category_url.rstrip("/")
                    paginated_url = f"{base_category_url}/page/{page_num}"
                else:
                    paginated_url = category_url

                print(f"\n📄 Crawling page {page_num}: {paginated_url}")

                page.goto(paginated_url, wait_until="networkidle", timeout=60000)
                time.sleep(2)

                # Extract book links (all links ending with .html)
                book_elements = page.query_selector_all("a[href$='.html']")

                if not book_elements:
                    print(f"  ⚠️  No books found on page {page_num} - End of category")
                    break

                page_count = 0
                for element in book_elements:
                    if len(book_urls) >= limit:
                        break

                    href = element.get_attribute("href")
                    if href:
                        # Convert relative to absolute URL
                        if not href.startswith("http"):
                            href = f"{base_url}{href}"

                        if href not in book_urls:
                            book_urls.append(href)
                            page_count += 1

                print(f"  ✅ Found {page_count} new books on page {page_num}")
                print(f"  📊 Total collected: {len(book_urls)}/{limit}")

                # Check if we have enough
                if len(book_urls) >= limit:
                    print(f"  🎯 Reached limit of {limit} books")
                    break

                # If we got less than 20 books, probably last page
                if page_count < 20:
                    print(f"  ⚠️  Got {page_count} < 20 books - probably last page")
                    break

                page_num += 1

            except Exception as e:
                print(f"  ❌ Error on page {page_num}: {e}")
                break

        return book_urls[:limit]

    def crawl_category(self, category_url: str, limit: int = 500):
        """Main crawler function with pagination and duplicate detection"""
        print(f"\n{'='*80}")
        print(f"Starting Category Crawler")
        print(f"URL: {category_url}")
        print(f"Limit: {limit} books")
        print(f"{'='*80}\n")

        with sync_playwright() as p:
            # Launch browser
            browser: Browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            )
            page: Page = context.new_page()

            try:
                # Step 1: Get book URLs from category with pagination
                print(f"Step 1: Extracting book URLs from category...")
                book_urls = self.crawl_category_page(page, category_url, limit)
                self.stats["total_found"] = len(book_urls)

                print(f"\n✅ Found {len(book_urls)} book URLs")

                # Step 2: Process each book
                for idx, book_url in enumerate(book_urls, 1):
                    try:
                        print(f"\n[{idx}/{len(book_urls)}] Processing: {book_url}")

                        # Extract metadata
                        metadata = self.extract_book_metadata(page, book_url)
                        if not metadata:
                            continue  # Skip if exists or failed

                        print(f"  📚 Title: {metadata['title']}")
                        print(f"  ✍️  Author: {metadata['author_name']}")
                        print(
                            f"  📂 Category: {metadata['child_category']} ({metadata['parent_category']})"
                        )

                        # Download cover and upload to R2
                        slug = self.create_slug(metadata["title"])
                        cover_r2_url = self.download_and_upload_cover(
                            metadata["cover_url"], slug
                        )

                        # Download PDF/MOBI using requests (not Playwright)
                        pdf_path = self.download_pdf(
                            metadata["download_url"],
                            slug,
                            metadata.get("file_type", "pdf"),
                        )
                        if not pdf_path:
                            self.stats["failed"] += 1
                            continue

                        # Upload PDF to R2
                        pdf_r2_url = self.upload_pdf_to_r2(pdf_path)

                        # Create book and chapter in database
                        self.create_book_and_chapter(metadata, pdf_r2_url, cover_r2_url)

                        # Clean up local PDF
                        pdf_path.unlink()

                        self.stats["downloaded_new"] += 1
                        print(
                            f"  ✅ Success! ({self.stats['downloaded_new']} new books)"
                        )

                    except Exception as e:
                        print(f"  ❌ Failed to process book: {e}")
                        self.stats["failed"] += 1
                        continue

            finally:
                browser.close()

        # Print summary
        print(f"\n{'='*80}")
        print(f"Crawling Complete!")
        print(f"{'='*80}")
        print(f"Total found: {self.stats['total_found']}")
        print(f"Skipped (existing): {self.stats['skipped_existing']}")
        print(f"Downloaded (new): {self.stats['downloaded_new']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    import sys

    # Default values
    category_url = "https://nhasachmienphi.com/category/kinh-te-quan-ly"
    limit = 500  # Default: crawl all books (500 should be enough for most categories)

    # Parse command line arguments
    # Usage: python category_crawler.py [category_url] [limit]
    if len(sys.argv) > 1:
        category_url = sys.argv[1]
    if len(sys.argv) > 2:
        limit = int(sys.argv[2])

    print(f"🎯 Configuration:")
    print(f"   Category: {category_url}")
    print(f"   Limit: {limit} books\n")

    crawler = CategoryCrawler()
    crawler.crawl_category(category_url, limit=limit)
