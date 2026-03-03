"""
Let's Read Asia Crawler - Test Script
Crawls children's books from letsreadasia.org and saves to MongoDB

Features:
- Selenium for JavaScript rendering and popup handling
- Extract book metadata (title, cover, book_id)
- Download PDF from Google Cloud Storage using window_handles tracking
- Upload to R2
- Save to "Truyện thiếu nhi" category
- Duplicate detection by title
- Tags: nature, letsreadasia

Usage:
    python crawler/letsread_crawler.py

Test URL: https://www.letsreadasia.org/category/5726225838374912 (Nature)
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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from botocore.client import Config

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database.db_manager import DBManager


class LetsReadCrawler:
    """Crawler for letsreadasia.org children's books"""

    def __init__(self):
        """Initialize crawler with DB and R2 connections"""
        # Database connection
        self.db_manager = DBManager()
        self.db = self.db_manager.db

        # Get Michael user_id (owner) — only required for crawl mode
        michael = self.db.authors.find_one({"author_id": "@michael"})
        if michael and michael.get("user_id"):
            self.OWNER_USER_ID = michael["user_id"]
            print(f"   Owner: {self.OWNER_USER_ID}")
        else:
            self.OWNER_USER_ID = None
            print("   ⚠️  @michael not found — inspect mode only (crawl will fail)")
        self.AUTHOR_ID = "@letsreadasia"

        print(f"🚀 Let's Read Asia Crawler initialized")
        print(f"   Author: {self.AUTHOR_ID}")

        # R2/S3 connection (sync client)
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        self.r2_bucket = os.getenv("R2_BUCKET_NAME", "wordai-documents")

        # Fixed category: Truyện thiếu nhi > Cổ Tích - Thần Thoại
        self.CHILD_CATEGORY = "Cổ Tích - Thần Thoại"
        self.PARENT_CATEGORY = "children-stories"

        # Stats
        self.stats = {
            "total_found": 0,
            "skipped_existing": 0,
            "downloaded_new": 0,
            "failed": 0,
        }

    def check_book_exists(self, book_title: str) -> bool:
        """Check if book already exists in database by title"""
        title_exists = self.db.online_books.find_one(
            {"title": {"$regex": f"^{re.escape(book_title)}$", "$options": "i"}}
        )
        return title_exists is not None

    def create_slug(self, text: str) -> str:
        """Create URL-friendly slug from text"""
        text = text.lower()
        # Remove special characters, keep alphanumeric and spaces
        text = re.sub(r"[^a-z0-9\s-]", "", text)
        # Replace spaces with hyphens
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
                ext = "jpg"

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
            r2_key = f"books/letsread/{timestamp}_{pdf_path.name}"

            with open(pdf_path, "rb") as f:
                self.s3_client.put_object(
                    Bucket=self.r2_bucket,
                    Key=r2_key,
                    Body=f.read(),
                    ContentType="application/pdf",
                )

            r2_url = f"https://static.wordai.pro/{r2_key}"
            print(f"  ✅ PDF uploaded to R2: {r2_url}")
            return r2_url

        except Exception as e:
            print(f"  ❌ PDF upload failed: {e}")
            raise

    def download_pdf(self, pdf_url: str, slug: str) -> Optional[Path]:
        """Download PDF from Google Cloud Storage"""
        try:
            download_dir = Path(__file__).parent / "downloads" / "letsread"
            download_dir.mkdir(parents=True, exist_ok=True)

            pdf_path = download_dir / f"{slug}.pdf"

            print(f"  📥 Downloading PDF: {pdf_url}")
            response = requests.get(pdf_url, stream=True, timeout=60)
            response.raise_for_status()

            with open(pdf_path, "wb") as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)

            print(f"  ✅ PDF downloaded: {pdf_path.name}")
            return pdf_path

        except Exception as e:
            print(f"  ❌ PDF download failed: {e}")
            return None

    def extract_books_from_page(self, driver) -> List[Dict[str, Any]]:
        """Extract book metadata from Let's Read Asia page"""
        books = []

        try:
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img[alt]"))
            )
            time.sleep(2)

            # Find all book cards - images with alt text (book titles)
            book_images = driver.find_elements(By.CSS_SELECTOR, "img[alt]")

            print(f"  Found {len(book_images)} images on page")

            for img in book_images:
                try:
                    title = img.get_attribute("alt")
                    cover_url = img.get_attribute("src")

                    if not title or len(title) < 3:
                        continue

                    if not cover_url:
                        continue

                    # Skip logos and app store badges
                    title_lower = title.lower()
                    if any(
                        skip in title_lower
                        for skip in [
                            "logo",
                            "let's read",
                            "get it on",
                            "app store",
                            "google play",
                        ]
                    ):
                        continue

                    # Only accept book cover images from hamropatro CDN
                    # (Category banners "Nature" etc come from appspot.com - skip those)
                    if "hamropatro.com" not in cover_url:
                        print(f"      ⏭️  Skip (not book CDN): {title}")
                        continue

                    # Generate slug from title (matches actual URL pattern on letsreadasia.org)
                    book_slug = self.create_slug(title)

                    # Try to extract book_id UUID from CDN URL
                    book_id = None
                    uuid_match = re.search(
                        r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
                        cover_url,
                    )
                    if uuid_match:
                        book_id = uuid_match.group(1)

                    print(f"    ✅ Found book: {title} (slug={book_slug})")

                    books.append(
                        {
                            "title": title,
                            "cover_url": cover_url,
                            "book_id": book_id,
                            "book_slug": book_slug,
                        }
                    )

                except Exception as e:
                    print(f"    ⚠️  Error extracting book: {e}")
                    continue

        except Exception as e:
            print(f"  ❌ Error extracting books: {e}")

        return books

    def get_book_pdf_url(
        self, driver, book_title: str, book_slug: str
    ) -> Dict[str, Any]:
        """
        Navigate to book detail page, extract description + PDF URL.
        Returns dict: {"pdf_url": str|None, "description": str}
        """
        result = {"pdf_url": None, "description": ""}
        try:
            print(f"  🔍 Getting PDF URL for: {book_title}")

            # Step 1: Navigate directly to book detail page using real slug from href
            book_url = f"https://www.letsreadasia.org/book/{book_slug}?bookLang=4846240843956224"

            print(f"    Step 1: Navigating to book detail page...")
            print(f"       {book_url}")
            driver.get(book_url)
            time.sleep(5)  # Wait for page to load

            # Save original window handle
            original_window = driver.current_window_handle

            # Extract description from page (grab longest paragraph-like text blocks)
            try:
                paras = driver.find_elements(By.CSS_SELECTOR, "p")
                desc_parts = []
                for p in paras:
                    txt = p.text.strip()
                    if len(txt) > 60 and not txt.startswith("http"):
                        desc_parts.append(txt)
                if desc_parts:
                    result["description"] = " ".join(desc_parts[:4])  # max 4 paragraphs
                    print(f"    📝 Description: {result['description'][:80]}...")
            except:
                pass

            # Step 2: Click Download button
            print(f"    Step 2: Clicking Download button...")
            try:
                wait = WebDriverWait(driver, 5)
                download_btn = wait.until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, 'span[aria-label="Open download pop up"]')
                    )
                )
                download_btn.click()
                print(f"    ✅ Clicked Download button")
            except TimeoutException as e:
                print(f"    ❌ Download button not found: {e}")
                return None

            # Wait for download popup to appear
            time.sleep(2.5)

            # Step 3: Click PDF option
            print(f"    Step 3: Looking for PDF option in popup...")
            pdf_clicked = False

            try:
                # Find element containing text "PDF"
                pdf_elements = driver.find_elements(
                    By.XPATH, "//*[contains(text(), 'PDF')]"
                )
                if pdf_elements:
                    pdf_elements[0].click()
                    pdf_clicked = True
                    print(f"    ✅ Clicked PDF option")
                    time.sleep(1)
            except:
                pass

            if not pdf_clicked:
                print(f"    ⚠️  PDF option not found, trying Portrait directly...")

            # Step 4: Click Portrait and track new tab with window_handles
            print(f"    Step 4: Getting PDF URL from Portrait link...")

            try:
                # Get count of windows before clicking
                windows_before = driver.window_handles
                print(f"    🪟 Windows before click: {len(windows_before)}")

                # Find and click Portrait
                print(f"    📍 Clicking Portrait...")
                portrait_elements = driver.find_elements(
                    By.XPATH, "//*[contains(text(), 'Portrait')]"
                )
                if not portrait_elements:
                    print(f"    ❌ Portrait option not found")
                    return None

                portrait_elements[0].click()
                print(f"    ✅ Clicked Portrait, waiting for new tab...")

                # Wait for new window to open
                time.sleep(3)

                # Get windows after click
                windows_after = driver.window_handles
                print(f"    🪟 Windows after click: {len(windows_after)}")

                # Find new window
                new_windows = set(windows_after) - set(windows_before)

                if new_windows:
                    new_window = new_windows.pop()
                    print(f"    ✅ New window detected: {new_window}")

                    # Switch to new window
                    driver.switch_to.window(new_window)
                    time.sleep(2)  # Wait for navigation

                    # Get PDF URL from new window
                    pdf_url = driver.current_url
                    print(f"    🔍 New window URL: {pdf_url}")

                    # Close new window
                    driver.close()

                    # Switch back to original window
                    driver.switch_to.window(original_window)

                    if (
                        pdf_url
                        and "lets-read-asia/pdfs" in pdf_url
                        and ".pdf" in pdf_url
                    ):
                        print(f"    ✅ Got PDF URL from new tab!")
                        print(f"       {pdf_url}")
                        result["pdf_url"] = pdf_url
                        return result
                    else:
                        print(
                            f"    ⚠️  New tab URL doesn't match PDF pattern: {pdf_url}"
                        )
                else:
                    print(f"    ⚠️  No new window detected")

                return result

            except Exception as e:
                print(f"    ⚠️  Failed to get PDF URL: {e}")
                import traceback

                traceback.print_exc()
                return result

        except Exception as e:
            print(f"  ❌ Error in get_book_pdf_url: {e}")
            return result

    def create_book_and_chapter(
        self, metadata: Dict[str, Any], pdf_r2_url: str, cover_r2_url: str
    ):
        """Create book and chapter documents in MongoDB - Truyện thiếu nhi category"""
        try:
            slug = self.create_slug(metadata["title"])
            book_id = f"book_{uuid.uuid4().hex[:12]}"
            chapter_id = str(uuid.uuid4())

            # Description: use crawled description or fallback
            full_desc = (
                metadata.get("description")
                or f"{metadata['title']} - Children's story from Let's Read Asia"
            )
            short_desc = full_desc[:200] if len(full_desc) > 200 else full_desc

            # Tags: nature + letsreadasia
            tags = ["nature", "letsread-asia", "english-books"]

            # Book document - same schema as category_crawler.py
            book_doc = {
                "book_id": book_id,
                "user_id": self.OWNER_USER_ID,
                "title": metadata["title"],
                "slug": slug,
                "description": full_desc,
                "visibility": "point_based",
                "is_published": True,
                "published_at": datetime.utcnow(),
                "is_deleted": False,
                "authors": [self.AUTHOR_ID],
                "metadata": {
                    "original_author": "Let's Read Asia",
                    "source": "letsreadasia.org",
                    "source_url": metadata.get("source_url", ""),
                    "source_category": "Nature",
                    "language": "English",
                },
                "community_config": {
                    "is_public": True,
                    "category": self.CHILD_CATEGORY,  # Cổ Tích - Thần Thoại
                    "parent_category": self.PARENT_CATEGORY,  # children-stories
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
                "access_config": {
                    "one_time_view_points": 2,
                    "forever_view_points": 5,
                    "download_pdf_points": 0,
                    "is_one_time_enabled": True,
                    "is_forever_enabled": True,
                    "is_download_enabled": False,
                },
                "stats": {
                    "total_revenue_points": 0,
                    "owner_reward_points": 0,
                    "system_fee_points": 0,
                    "one_time_purchases": 0,
                    "forever_purchases": 0,
                    "pdf_downloads": 0,
                },
                "cover_image_url": cover_r2_url or "",
                "logo_url": None,
                "primary_color": "#4F46E5",
                "is_indexed": True,
                "meta_title": None,
                "meta_description": None,
                "custom_domain": None,
                "view_count": 0,
                "unique_visitors": 0,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_published_at": datetime.utcnow(),
            }

            # Chapter document
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
            print(f"     Category: {self.CHILD_CATEGORY} ({self.PARENT_CATEGORY})")
            print(f"     Tags: {', '.join(tags)}")

            return book_id

        except Exception as e:
            print(f"  ❌ Database insert failed: {e}")
            import traceback

            traceback.print_exc()
            raise

    def find_letsread_uuid_from_slug(
        self, driver, book_slug: str, lang_id: str = "4846240843956224"
    ) -> Optional[str]:
        """
        Navigate to book detail page and extract the letsread UUID.
        Tries multiple strategies:
          1. href containing /read/{uuid}
          2. img src from hamropatro CDN (contains UUID in path)
          3. any href/src on page containing a UUID
          4. entire page source scan
          5. fallback: scan category page for this book's cover UUID
        Returns UUID string or None.
        """
        UUID_PATTERN = r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})"

        book_url = f"https://www.letsreadasia.org/book/{book_slug}?bookLang={lang_id}"
        print(f"    🔗 Navigating to book detail: {book_url}")
        driver.get(book_url)
        time.sleep(4)

        # Save HTML for debugging
        html_path = f"/tmp/detail_{book_slug[:20]}.html"
        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"    💾 Detail HTML saved: {html_path}")
        except Exception:
            pass

        source = driver.page_source

        # Strategy 1: find <a href="/read/{uuid}..."> link
        try:
            for link in driver.find_elements(By.TAG_NAME, "a"):
                href = link.get_attribute("href") or ""
                m = re.search(UUID_PATTERN, href)
                if m and "/read/" in href:
                    print(f"    ✅ [S1] UUID from /read/ link: {m.group(1)}")
                    return m.group(1)
        except Exception as e:
            print(f"    ⚠️  S1 error: {e}")

        # Strategy 2: img src from hamropatro CDN (UUID is in path)
        try:
            for img in driver.find_elements(By.TAG_NAME, "img"):
                src = img.get_attribute("src") or ""
                if "hamropatro.com" in src or "letsreadasia" in src:
                    m = re.search(UUID_PATTERN, src)
                    if m:
                        print(f"    ✅ [S2] UUID from CDN img src: {m.group(1)}")
                        return m.group(1)
        except Exception as e:
            print(f"    ⚠️  S2 error: {e}")

        # Strategy 3: any href on page containing a UUID
        try:
            for link in driver.find_elements(By.TAG_NAME, "a"):
                href = link.get_attribute("href") or ""
                m = re.search(UUID_PATTERN, href)
                if m:
                    print(
                        f"    ✅ [S3] UUID from any link href: {m.group(1)} (href={href[:80]})"
                    )
                    return m.group(1)
        except Exception as e:
            print(f"    ⚠️  S3 error: {e}")

        # Strategy 4: entire page source scan (catches JS vars, data attrs, etc.)
        m = re.search(UUID_PATTERN, source)
        if m:
            print(f"    ✅ [S4] UUID from page source: {m.group(1)}")
            return m.group(1)

        # Strategy 5: navigate to category page and find cover UUID by title match
        print(f"    ⚠️  Strategies 1-4 failed, trying category page...")
        try:
            category_url = "https://www.letsreadasia.org/category/5726225838374912"
            driver.get(category_url)
            time.sleep(4)
            for img in driver.find_elements(By.CSS_SELECTOR, "img[alt]"):
                img_alt = (img.get_attribute("alt") or "").strip()
                img_slug = self.create_slug(img_alt)
                if img_slug == book_slug:
                    src = img.get_attribute("src") or ""
                    m = re.search(UUID_PATTERN, src)
                    if m:
                        print(f"    ✅ [S5] UUID from category cover img: {m.group(1)}")
                        return m.group(1)
        except Exception as e:
            print(f"    ⚠️  S5 error: {e}")

        print(f"    ❌ Could not find letsread UUID for slug: {book_slug}")
        return None

    def inspect_viewer_html(
        self,
        driver,
        letsread_uuid: str,
        lang_id: str = "4846240843956224",
        book_title: str = "unknown",
    ):
        """
        Navigate to the Read viewer, save full HTML, and probe for CSS selectors
        needed by the page crawler (text, image, next button, page indicator).
        Saves HTML to /tmp/viewer_{uuid[:8]}.html
        """
        read_url = (
            f"https://www.letsreadasia.org/read/{letsread_uuid}?bookLang={lang_id}"
        )
        print(f"\n  🔍 Inspecting viewer: {read_url}")
        driver.get(read_url)

        # Wait up to 20s for actual book content to appear (not just error boundary)
        # Looking for: page images (googleapis CDN), canvas, or any img from letsread CDN
        print(f"  ⏳ Waiting for book content to load (max 20s)...")
        content_loaded = False
        for attempt in range(4):
            time.sleep(5)
            src = driver.page_source
            if "SomethingWentWrong" not in src:
                content_loaded = True
                print(f"  ✅ Content loaded after {(attempt+1)*5}s")
                break
            # Check if we see googleapis storage links (book images)
            if "storage.googleapis.com/lets-read-asia" in src:
                content_loaded = True
                print(f"  ✅ googleapis image found after {(attempt+1)*5}s")
                break
            print(f"     [{(attempt+1)*5}s] Still loading...")

        if not content_loaded:
            print(
                f"  ⚠️  Viewer may require login or more load time — saving HTML anyway"
            )

        # Save full HTML
        html_path = f"/tmp/viewer_{letsread_uuid[:8]}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"  💾 HTML saved: {html_path}")

        print(f"\n  📋 CSS selector probe for: '{book_title}'")
        print(f"  {'─'*60}")

        # --- Text content candidates ---
        text_candidates = [
            ("p", "Generic <p>"),
            (".book-text", ".book-text"),
            (".page-text", ".page-text"),
            (".text-content", ".text-content"),
            ("[class*='text']", "[class*='text'] (any)"),
            ("[class*='page']", "[class*='page'] (any)"),
            ("[class*='content']", "[class*='content'] (any)"),
            ("[class*='story']", "[class*='story'] (any)"),
        ]
        print(f"  🔤 Text content selectors:")
        found_text_selector = None
        for selector, label in text_candidates:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, selector)
                visible = [e for e in els if e.is_displayed() and e.text.strip()]
                if visible:
                    sample = visible[0].text.strip()[:80]
                    print(
                        f'     ✅ {label:35s} → {len(visible)} found | sample: "{sample}"'
                    )
                    if found_text_selector is None:
                        found_text_selector = (selector, label)
                else:
                    print(
                        f"     ⬜ {label:35s} → {len(els)} els, none visible with text"
                    )
            except Exception as e:
                print(f"     ❌ {label:35s} → error: {e}")

        # --- Image candidates ---
        img_candidates = [
            ("img[class*='page']", "img[class*='page']"),
            ("img[class*='book']", "img[class*='book']"),
            ("img[class*='illustration']", "img[class*='illustration']"),
            (".page-image img", ".page-image img"),
            (".book-page img", ".book-page img"),
            ("img[src*='storage.googleapis']", "img[src*=googleapis]"),
            ("img[src*='hamropatro']", "img[src*=hamropatro]"),
            ("img[alt]", "img[alt] (any)"),
        ]
        print(f"\n  🖼️  Page image selectors:")
        found_img_selector = None
        for selector, label in img_candidates:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, selector)
                visible = [e for e in els if e.is_displayed()]
                if visible:
                    src = (visible[0].get_attribute("src") or "")[:80]
                    print(f"     ✅ {label:38s} → {len(visible)} found | src: {src}")
                    if found_img_selector is None:
                        found_img_selector = (selector, label)
                else:
                    print(f"     ⬜ {label:38s} → {len(els)} els, none visible")
            except Exception as e:
                print(f"     ❌ {label:38s} → error: {e}")

        # --- Navigation button candidates ---
        nav_candidates = [
            ("button[aria-label*='next']", "button[aria-label*=next]"),
            ("button[aria-label*='Next']", "button[aria-label*=Next]"),
            ("[class*='next']", "[class*='next']"),
            ("[class*='arrow']", "[class*='arrow']"),
            ("button[class*='nav']", "button[class*=nav]"),
            (".navigation button", ".navigation button"),
            ("button", "button (all)"),
        ]
        print(f"\n  ⏭️  Next page button selectors:")
        found_nav_selector = None
        for selector, label in nav_candidates:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, selector)
                visible = [e for e in els if e.is_displayed()]
                if visible:
                    aria = visible[0].get_attribute("aria-label") or ""
                    cls = (visible[0].get_attribute("class") or "")[:40]
                    print(
                        f"     ✅ {label:38s} → {len(visible)} found | aria={aria!r} class={cls!r}"
                    )
                    if found_nav_selector is None:
                        found_nav_selector = (selector, label)
                else:
                    print(f"     ⬜ {label:38s} → {len(els)} els, none visible")
            except Exception as e:
                print(f"     ❌ {label:38s} → error: {e}")

        # --- Page number / indicator ---
        page_candidates = [
            ("[class*='page-number']", "[class*='page-number']"),
            ("[class*='indicator']", "[class*='indicator']"),
            ("[class*='counter']", "[class*='counter']"),
            ("span[class*='page']", "span[class*='page']"),
        ]
        print(f"\n  🔢 Page indicator selectors:")
        for selector, label in page_candidates:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, selector)
                visible = [e for e in els if e.is_displayed() and e.text.strip()]
                if visible:
                    txt = visible[0].text.strip()
                    print(f'     ✅ {label:35s} → text: "{txt}"')
                else:
                    print(f"     ⬜ {label:35s} → not found")
            except Exception:
                pass

        # --- Try clicking next and check for change ---
        print(f"\n  🧪 Testing next-page navigation...")
        if found_nav_selector and found_text_selector:
            try:
                text_before = driver.find_element(
                    By.CSS_SELECTOR, found_text_selector[0]
                ).text
                nav_els = [
                    e
                    for e in driver.find_elements(
                        By.CSS_SELECTOR, found_nav_selector[0]
                    )
                    if e.is_displayed()
                ]
                if nav_els:
                    nav_els[-1].click()  # click last (usually "next")
                    time.sleep(2)
                    text_after = driver.find_element(
                        By.CSS_SELECTOR, found_text_selector[0]
                    ).text
                    changed = text_before != text_after
                    print(
                        f"     {'✅ Text changed after click — navigation WORKS!' if changed else '⚠️  Text did NOT change after click'}"
                    )
                    print(f'     Before: "{text_before[:60]}"')
                    print(f'     After:  "{text_after[:60]}"')
            except Exception as e:
                print(f"     ⚠️  Nav test error: {e}")
        else:
            print(f"     ⚠️  Skipped (no text/nav selector found above)")

        print(f"\n  {'─'*60}")
        print(f"  📌 RECOMMENDED SELECTORS for '{book_title}':")
        print(
            f"     Text:  {found_text_selector[0] if found_text_selector else 'NOT FOUND'}"
        )
        print(
            f"     Image: {found_img_selector[0] if found_img_selector else 'NOT FOUND'}"
        )
        print(
            f"     Next:  {found_nav_selector[0] if found_nav_selector else 'NOT FOUND'}"
        )
        print(f"  {'─'*60}\n")

        return {
            "uuid": letsread_uuid,
            "html_path": html_path,
            "text_selector": found_text_selector[0] if found_text_selector else None,
            "img_selector": found_img_selector[0] if found_img_selector else None,
            "nav_selector": found_nav_selector[0] if found_nav_selector else None,
        }

    def inspect_existing_books(self, limit: int = 3):
        """
        Query first N letsread books from MongoDB, navigate to their read viewers,
        and save HTML + print CSS selector findings for each.
        """
        print(f"\n{'='*80}")
        print(f"Inspecting Read Viewer HTML — first {limit} letsread books from DB")
        print(f"{'='*80}\n")

        # Query DB for letsread books
        books_cursor = self.db.online_books.find(
            {"metadata.source": "letsreadasia.org", "is_deleted": False},
            {"book_id": 1, "title": 1, "slug": 1, "metadata": 1},
        ).limit(limit)
        books = list(books_cursor)

        if not books:
            print("❌ No letsread books found in DB. Run crawl_test() first.")
            return

        print(f"✅ Found {len(books)} books in DB:\n")
        for b in books:
            print(f"   - {b['title']} (slug={b.get('slug','?')})")

        # Setup Chrome — NOT headless for inspection (viewer may block headless)
        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # OFF: viewer blocks headless
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        driver = webdriver.Chrome(options=chrome_options)
        results = []

        try:
            for book in books:
                title = book["title"]
                slug = book.get("slug") or self.create_slug(title)
                lang_id = "4846240843956224"

                print(f"\n[{'─'*76}]")
                print(f"  Book: {title}")
                print(f"  Slug: {slug}")

                # Step 1: get UUID from book detail page
                letsread_uuid = self.find_letsread_uuid_from_slug(driver, slug, lang_id)

                if not letsread_uuid:
                    print(f"  ❌ Skipping — could not retrieve UUID")
                    continue

                # Step 2: update online_books with the letsread_book_id (bonus)
                try:
                    self.db.online_books.update_one(
                        {"book_id": book["book_id"]},
                        {
                            "$set": {
                                "metadata.letsread_book_id": letsread_uuid,
                                "metadata.letsread_lang_id": lang_id,
                                "updated_at": datetime.utcnow(),
                            }
                        },
                    )
                    print(f"  💾 Saved letsread_book_id to DB: {letsread_uuid}")
                except Exception as e:
                    print(f"  ⚠️  DB update failed: {e}")

                # Step 3: inspect the viewer HTML
                result = self.inspect_viewer_html(driver, letsread_uuid, lang_id, title)
                result["title"] = title
                result["book_id"] = book["book_id"]
                results.append(result)

        finally:
            driver.quit()

        # Final summary
        print(f"\n{'='*80}")
        print(f"INSPECTION COMPLETE — {len(results)}/{len(books)} books inspected")
        print(f"{'='*80}")
        for r in results:
            print(f"\n  📖 {r['title']}")
            print(f"     UUID:  {r['uuid']}")
            print(f"     HTML:  {r['html_path']}")
            print(f"     Text:  {r.get('text_selector')}")
            print(f"     Image: {r.get('img_selector')}")
            print(f"     Next:  {r.get('nav_selector')}")
        print(f"\n{'='*80}\n")
        return results

    def crawl_test(self, category_url: str):
        """Test crawler - extract books from first page only (no Load More)"""
        print(f"\n{'='*80}")
        print(f"Let's Read Asia Test Crawler")
        print(f"URL: {category_url}")
        print(f"Category: Truyện thiếu nhi > {self.CHILD_CATEGORY}")
        print(f"{'='*80}\n")

        # Store URL for navigate back
        self.category_url = category_url

        # Setup Selenium Chrome
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # headless for production
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "--disable-popup-blocking"
        )  # CRITICAL: allow new tab in headless

        driver = webdriver.Chrome(options=chrome_options)

        try:
            print(f"Step 1: Loading page...")
            driver.get(category_url)
            time.sleep(5)  # Wait for JS to load

            # Debug: Save page HTML for analysis
            print(f"\n🔍 Saving page HTML for debugging...")
            page_html = driver.page_source
            with open("/tmp/letsread_page.html", "w", encoding="utf-8") as f:
                f.write(page_html)
            print(f"   Saved to: /tmp/letsread_page.html")

            print(f"\nStep 2: Extracting book metadata...")
            books = self.extract_books_from_page(driver)
            self.stats["total_found"] = len(books)

            print(f"\n✅ Found {len(books)} books on first page")

            # Process first 4 books for testing
            TEST_LIMIT = 4
            books = books[:TEST_LIMIT]
            total_books = len(books)
            print(f"\n📊 Processing {total_books} books (test mode)...\n")

            for idx, book in enumerate(books, 1):
                print(f"\n[{idx}/{total_books}] Processing: {book['title']}")
                try:

                    # Check if exists
                    if self.check_book_exists(book["title"]):
                        print(f"  ⏭️  Book already exists: {book['title']}")
                        self.stats["skipped_existing"] += 1
                        continue

                    # Download cover and upload to R2
                    book_slug = book.get("book_slug") or self.create_slug(book["title"])
                    cover_r2_url = self.download_and_upload_cover(
                        book["cover_url"], book_slug
                    )

                    # Get PDF URL + description by navigating to book detail page
                    print(
                        f"  🖱️  Getting PDF URL + description from book detail page..."
                    )
                    book_details = self.get_book_pdf_url(
                        driver, book["title"], book_slug
                    )
                    pdf_url = book_details["pdf_url"]
                    if book_details.get("description"):
                        book["description"] = book_details["description"]

                    # Check if we have a complete PDF URL
                    if not pdf_url or pdf_url.endswith("/"):
                        print(f"  ⚠️  No complete PDF URL - skipping")
                        print(f"     - Title: {book['title']}, Slug: {book_slug}")
                        self.stats["failed"] += 1
                        continue

                    # Download PDF to local path
                    print(f"  📥 Downloading PDF from: {pdf_url}")
                    pdf_local_path = self.download_pdf(pdf_url, book_slug)

                    if not pdf_local_path:
                        print(f"  ❌ PDF download failed - skipping")
                        self.stats["failed"] += 1
                        continue

                    # Upload local PDF to R2
                    print(f"  ☁️  Uploading PDF to R2...")
                    pdf_r2_url = self.upload_pdf_to_r2(pdf_local_path)

                    if not pdf_r2_url:
                        print(f"  ❌ PDF upload failed - skipping")
                        self.stats["failed"] += 1
                        continue

                    # Create book and chapter in database
                    print(f"  💾 Creating book in database...")
                    success = self.create_book_and_chapter(
                        metadata=book,
                        pdf_r2_url=pdf_r2_url,
                        cover_r2_url=cover_r2_url,
                    )

                    if success:
                        print(f"  ✅ Book created successfully!")
                        self.stats["downloaded_new"] += 1
                    else:
                        print(f"  ❌ Failed to create book in database")
                        self.stats["failed"] += 1

                except Exception as e:
                    print(f"  ❌ Failed to process book: {e}")
                    import traceback

                    traceback.print_exc()
                    self.stats["failed"] += 1
                    raise SystemExit(
                        f"Exiting due to error on book '{book['title']}': {e}"
                    )

                finally:
                    # Navigate back to category page for next book (except last one)
                    if idx < total_books:
                        print(f"  ⬅️  Navigating back to category page...")
                        try:
                            driver.get(self.category_url)
                            time.sleep(2)
                        except Exception as e:
                            print(f"  ⚠️  Failed to navigate back: {e}")

            # Summary message (browser will auto-close)
            print(f"\n{'='*80}")
            print(f"✅ Browser closing... (removed input() for production)")
            print(f"{'='*80}")

        finally:
            driver.quit()
        print(f"Total found: {self.stats['total_found']}")
        print(f"Skipped (existing): {self.stats['skipped_existing']}")
        print(f"Downloaded (new): {self.stats['downloaded_new']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    crawler = LetsReadCrawler()

    mode = sys.argv[1] if len(sys.argv) > 1 else "crawl"

    if mode == "inspect":
        # Inspect Read viewer HTML for first N books already in DB
        # Usage: python crawler/letsread_crawler.py inspect [limit]
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        crawler.inspect_existing_books(limit=limit)

    elif mode == "inspect_slugs":
        # Inspect specific book slugs directly, no DB lookup needed
        # Usage: python crawler/letsread_crawler.py inspect_slugs slug1 slug2 slug3
        slugs = sys.argv[2:]
        if not slugs:
            print(
                "Usage: python crawler/letsread_crawler.py inspect_slugs <slug1> [slug2] ..."
            )
            sys.exit(1)
        lang_id = "4846240843956224"
        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # OFF for inspection
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        from selenium import webdriver as _wd

        driver = _wd.Chrome(options=chrome_options)
        try:
            for slug in slugs:
                print(f"\n{'='*70}")
                print(f"Slug: {slug}")
                uuid_val = crawler.find_letsread_uuid_from_slug(driver, slug, lang_id)
                if uuid_val:
                    crawler.inspect_viewer_html(driver, uuid_val, lang_id, slug)
                else:
                    print(f"  ❌ Could not get UUID for slug: {slug}")
        finally:
            driver.quit()

    else:
        # Default: crawl new books from category page
        # Usage: python crawler/letsread_crawler.py
        category_url = "https://www.letsreadasia.org/category/5726225838374912"
        crawler.crawl_test(category_url)
