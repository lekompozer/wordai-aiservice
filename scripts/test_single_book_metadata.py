#!/usr/bin/env python3
"""Test crawler with single book to verify metadata extraction"""

import sys

sys.path.insert(0, "/app")

from crawler.test_crawler_clean import TestBookCrawler

if __name__ == "__main__":
    crawler = TestBookCrawler()

    # Test với 1 book cụ thể
    book_url = "https://nhasachmienphi.com/de-xay-dung-doanh-nghiep-hieu-qua.html"

    print("\n" + "=" * 80)
    print("TEST SINGLE BOOK METADATA EXTRACTION")
    print("=" * 80)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"\n📖 Testing: {book_url}\n")

        try:
            book_data = crawler.crawl_book_detail(page, book_url)

            if book_data:
                print("\n✅ METADATA EXTRACTED:")
                print(f"   Title: {book_data['title']}")
                print(f"   Author: {book_data.get('author') or 'N/A'}")
                print(f"   Category: {book_data.get('category_slug') or 'N/A'}")

                cover = book_data.get("cover_url")
                if cover:
                    print(f"   Cover: {cover[:80]}...")
                else:
                    print(f"   Cover: N/A")

                desc = book_data.get("description", "")
                print(f"   Description length: {len(desc)} chars")

                pdf = book_data.get("pdf_url")
                if pdf:
                    print(f"   PDF: {pdf[:80]}...")
                else:
                    print(f"   PDF: N/A")

                print(f"   Slug: {book_data['slug']}")

                # Show first 500 chars of description
                if desc:
                    print(f"\n📝 DESCRIPTION PREVIEW:")
                    print(f"   {desc[:500]}...")

            else:
                print("❌ Failed to extract metadata")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback

            traceback.print_exc()
        finally:
            browser.close()

    print("\n" + "=" * 80)
