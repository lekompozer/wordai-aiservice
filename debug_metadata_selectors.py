#!/usr/bin/env python3
"""Debug HTML structure for metadata extraction"""

import sys

sys.path.insert(0, "/app")

from playwright.sync_api import sync_playwright

if __name__ == "__main__":
    book_url = "https://nhasachmienphi.com/de-xay-dung-doanh-nghiep-hieu-qua.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"\n📖 Loading: {book_url}\n")
        page.goto(book_url, wait_until="networkidle", timeout=30000)

        # Test title selectors
        print("=" * 80)
        print("TITLE SELECTORS:")
        print("=" * 80)

        h1_all = page.query_selector_all("h1")
        print(f"Total h1 tags: {len(h1_all)}")
        for i, h1 in enumerate(h1_all):
            print(f"  [{i}] text: {h1.inner_text()[:80]}")
            print(f"      class: {h1.get_attribute('class')}")

        # Test author selectors
        print("\n" + "=" * 80)
        print("AUTHOR SELECTORS:")
        print("=" * 80)

        divs_with_mg_t_10 = page.query_selector_all("div.mg-t-10")
        print(f"Total div.mg-t-10: {len(divs_with_mg_t_10)}")
        for i, div in enumerate(divs_with_mg_t_10):
            text = div.inner_text().strip()[:100]
            print(f"  [{i}] {text}")

        # Test cover image selectors
        print("\n" + "=" * 80)
        print("COVER IMAGE SELECTORS:")
        print("=" * 80)

        # Try first method
        cover_img = page.query_selector(
            ".col-xs-12.col-sm-4 img[src*='wp-content/uploads']"
        )
        print(
            f"Selector '.col-xs-12.col-sm-4 img[src*=wp-content/uploads]': {cover_img}"
        )

        # Try all images
        all_imgs = page.query_selector_all("img[src*='wp-content/uploads']")
        print(f"\nTotal images with wp-content/uploads: {len(all_imgs)}")
        for i, img in enumerate(all_imgs):
            src = img.get_attribute("src")
            print(f"  [{i}] {src[:100]}...")

        # Test description selectors
        print("\n" + "=" * 80)
        print("DESCRIPTION SELECTORS:")
        print("=" * 80)

        content_div = page.query_selector(".content_p.content_p_al")
        print(f"Selector '.content_p.content_p_al': {content_div is not None}")

        if content_div:
            paragraphs = content_div.query_selector_all("p")
            print(f"  Total <p> tags: {len(paragraphs)}")
            for i, p in enumerate(paragraphs[:5]):  # First 5
                text = p.inner_text().strip()[:80]
                has_link = p.query_selector("a.postTitle") is not None
                print(f"  [{i}] has_link={has_link}: {text}...")

        # Test category selector
        print("\n" + "=" * 80)
        print("CATEGORY SELECTORS:")
        print("=" * 80)

        category_link = page.query_selector("a[href*='/category/']")
        if category_link:
            href = category_link.get_attribute("href")
            text = category_link.inner_text()
            print(f"First category link:")
            print(f"  href: {href}")
            print(f"  text: {text}")
        else:
            print("No category link found!")

        browser.close()
