#!/usr/bin/env python3
"""POC Book Crawler - nhasachmienphi.com - Clean Version"""

import time, uuid, requests, os, re
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
from src.database.db_manager import DBManager
import boto3
from botocore.client import Config

# Category mapping: nhasachmienphi slug → WordAI category_id
CATEGORY_MAP = {
    "kinh-te-quan-ly": "kinh-te-quan-ly",
    "van-hoc-viet-nam": "van-hoc-viet-nam",
    "tam-ly-ky-nang-song": "tam-ly-ky-nang-song",
    "hoc-ngoai-ngu": "hoc-ngoai-ngu",
    "khoa-hoc-ky-thuat": "khoa-hoc-ky-thuat",
    "marketing-ban-hang": "marketing-ban-hang",
    "lich-su-chinh-tri": "lich-su-chinh-tri",
}


class TestBookCrawler:
    def __init__(self, download_dir="/tmp/crawler_downloads"):
        self.base_url = "https://nhasachmienphi.com"
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        db_manager = DBManager()
        self.db = db_manager.db

        # Init boto3 S3 client
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        self.bucket_name = os.getenv("R2_BUCKET_NAME", "wordai-documents")

        # Get Michael user_id (owner)
        michael = self.db.authors.find_one({"author_id": "@michael"})
        if not michael or not michael.get("user_id"):
            raise ValueError("❌ @michael not found!")

        self.OWNER_USER_ID = michael["user_id"]
        self.AUTHOR_ID = "@sachonline"

        print(f"🚀 Crawler initialized")
        print(f"   Owner: {self.OWNER_USER_ID}")
        print(f"   Author: {self.AUTHOR_ID}")

    def crawl_test_books(self, category_slug="kinh-te-quan-ly", limit=5):
        print(f"\n📚 Starting POC crawl: {limit} books from {category_slug}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                url = f"{self.base_url}/category/{category_slug}"
                print(f"   Fetching: {url}")
                page.goto(url, wait_until="networkidle", timeout=30000)

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

                book_ids = []
                for idx, book_url in enumerate(book_links, 1):
                    print(f"\n[{idx}/{limit}] {book_url}")

                    try:
                        book_id = self.process_single_book(
                            page, book_url, category_slug
                        )
                        if book_id:
                            book_ids.append(book_id)
                            print(f"   ✅ Success: {book_id}")
                        else:
                            print(f"   ❌ Skipped")
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

    def process_single_book(self, page, url, category_slug):
        book_data = self.crawl_book_detail(page, url)
        if not book_data:
            return None

        print(f"   📖 {book_data['title']}")

        # Download and upload cover to R2
        cover_r2_url = None
        if book_data.get("cover_url"):
            cover_r2_url = self.download_and_upload_cover(
                book_data["cover_url"], book_data["slug"]
            )

        # Download and upload PDF
        pdf_path = self.download_pdf(book_data["pdf_url"], book_data["slug"])
        if not pdf_path:
            return None

        print(f"   ✅ Downloaded: {pdf_path.name}")

        pdf_r2_url = self.upload_to_r2(pdf_path)
        if not pdf_r2_url:
            return None

        print(f"   ✅ PDF R2: {pdf_r2_url}")

        book_id = self.create_book(book_data, pdf_r2_url, cover_r2_url, category_slug)
        pdf_path.unlink(missing_ok=True)

        return book_id

    def crawl_book_detail(self, page, url):
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(1)

            # Extract title - h1.tblue.fs-20
            title_elem = page.query_selector("h1.tblue.fs-20")
            if not title_elem:
                title_elem = page.query_selector("h1")
            title = title_elem.inner_text().strip() if title_elem else page.title()

            # Extract author - "Tác giả: ..."
            author_text = None
            author_divs = page.query_selector_all("div.mg-t-10")
            for div in author_divs:
                text = div.inner_text().strip()
                if text.startswith("Tác giả:"):
                    author_text = text.replace("Tác giả:", "").strip()
                    break

            # Extract cover image - first img in .col-xs-12.col-sm-4
            cover_url = None
            cover_img = page.query_selector(
                ".col-xs-12.col-sm-4 img[src*='wp-content/uploads']"
            )
            if cover_img:
                cover_url = cover_img.get_attribute("src")

            # Fallback: any image with wp-content/uploads
            if not cover_url:
                all_imgs = page.query_selector_all("img[src*='wp-content/uploads']")
                for img in all_imgs:
                    src = img.get_attribute("src")
                    # Skip ads/banners
                    if src and not any(
                        x in src.lower() for x in ["banner", "ads", "voucher", ".gif"]
                    ):
                        cover_url = src
                        break

            # Extract description from .content_p.content_p_al
            description_parts = []
            content_div = page.query_selector(".content_p.content_p_al")
            if content_div:
                paragraphs = content_div.query_selector_all("p")
                for p in paragraphs:
                    # Skip inline related posts (they have links inside)
                    if p.query_selector("a.postTitle"):
                        continue

                    text = p.inner_text().strip()
                    # Skip empty or very short lines
                    if text and len(text) > 30:
                        description_parts.append(text)

            description = "\n\n".join(description_parts) if description_parts else ""

            # Extract category from page - in div.mg-tb-10 containing "Thể loại:"
            category_slug_from_page = None
            category_divs = page.query_selector_all("div.mg-tb-10")
            for div in category_divs:
                text = div.inner_text().strip()
                if "Thể loại:" in text or "Thể Loại:" in text:
                    category_link = div.query_selector("a[href*='/category/']")
                    if category_link:
                        href = category_link.get_attribute("href")
                        if href:
                            # Extract: https://nhasachmienphi.com/category/kinh-te-quan-ly
                            parts = href.rstrip("/").split("/")
                            if parts:
                                category_slug_from_page = parts[-1]
                    break

            # Tìm PDF link trong HTML content bằng regex
            html_content = page.content()
            pdf_matches = re.findall(r'href=["\']([^"\']*\.pdf)["\']', html_content)

            pdf_link = pdf_matches[0] if pdf_matches else None

            if not pdf_link:
                print("   ⚠️  No PDF/MOBI link")
                return None

            slug = url.split("/")[-1].replace(".html", "")

            return {
                "title": title,
                "description": description,
                "cover_url": cover_url,
                "author": author_text,
                "category_slug": category_slug_from_page,
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

    def download_and_upload_cover(self, cover_url, slug):
        """Download cover image from nhasachmienphi.com and upload to R2"""
        if not cover_url:
            return None

        try:
            # Download cover image
            r = requests.get(cover_url, timeout=30)
            r.raise_for_status()

            # Detect image format from URL or content-type
            content_type = r.headers.get("content-type", "image/jpeg")
            ext = "jpg"
            if "png" in content_type or cover_url.lower().endswith(".png"):
                ext = "png"
            elif "webp" in content_type or cover_url.lower().endswith(".webp"):
                ext = "webp"

            # Upload to R2
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            r2_key = f"books/covers/{ts}_{slug}.{ext}"

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=r2_key,
                Body=r.content,
                ContentType=content_type,
            )

            # Generate public URL
            cover_r2_url = f"https://static.wordai.pro/{r2_key}"
            print(f"   ✅ Cover uploaded: {r2_key}")
            return cover_r2_url

        except Exception as e:
            print(f"   ⚠️  Cover upload failed: {e}")
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

            # Generate public URL (matching R2StorageService pattern)
            pdf_r2_url = f"https://static.wordai.pro/{r2_key}"
            return pdf_r2_url

        except Exception as e:
            print(f"   ❌ R2 failed: {e}")
            return None

    def create_book(self, book_data, pdf_r2_url, cover_r2_url, category_slug):
        try:
            book_id = f"book_{uuid.uuid4().hex[:12]}"
            chapter_id = str(uuid.uuid4())

            # Map category (use category from book page, fallback to crawl category)
            book_category_slug = book_data.get("category_slug") or category_slug
            wordai_category = CATEGORY_MAP.get(book_category_slug, book_category_slug)

            # Generate short description
            short_desc = (
                book_data["description"][:200]
                if book_data["description"]
                else book_data["title"]
            )

            # Generate tags
            tags = [book_category_slug] if book_category_slug else []
            if book_data.get("author"):
                tags.append(
                    f"tac-gia-{book_data['author'].lower().replace(' ', '-')[:30]}"
                )

            # Follow schema như book "Tiểu Sử Các Quốc Gia..." - ĐÚNG SCHEMA!
            book_doc = {
                "book_id": book_id,
                "user_id": self.OWNER_USER_ID,  # Michael's user_id
                "title": book_data["title"],
                "slug": book_data["slug"],
                "description": book_data["description"],
                "visibility": "point_based",
                "is_published": True,
                "published_at": datetime.utcnow(),
                "is_deleted": False,
                # Authors list (QUAN TRỌNG!)
                "authors": [self.AUTHOR_ID],
                # Book metadata
                "metadata": {
                    "original_author": book_data.get(
                        "author"
                    ),  # Tác giả gốc từ trang sách
                    "source": "nhasachmienphi.com",
                    "source_url": book_data.get("source_url"),
                    "source_category": book_category_slug,
                },
                # Community config with FULL metadata
                "community_config": {
                    "is_public": True,  # PUBLIC để hiện trên author profile!
                    "category": wordai_category,  # WordAI category_id
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
                    "one_time_view_points": 1,
                    "forever_view_points": 3,
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

            chapter_doc = {
                "_id": chapter_id,
                "chapter_id": chapter_id,  # Use same chapter_id
                "book_id": book_id,
                "chapter_number": 1,
                "title": "Full Book",
                "slug": "full-book",  # Required for API response!
                "chapter_type": "pdf",
                "content_mode": "pdf_file",  # Frontend checks this field!
                "pdf_url": pdf_r2_url,
                "order_index": 0,  # Required for sorting!
                "depth": 0,  # Required for ChapterResponse model!
                "is_published": True,  # Required for API to return chapters!
                "is_preview_free": False,  # Not free preview
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
    book_ids = crawler.crawl_test_books(category_slug="kinh-te-quan-ly", limit=5)

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
