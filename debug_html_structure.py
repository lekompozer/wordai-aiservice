#!/usr/bin/env python3
"""Debug: Check HTML structure of book page"""

from playwright.sync_api import sync_playwright


def debug_page():
    url = "https://nhasachmienphi.com/de-xay-dung-doanh-nghiep-hieu-qua.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)

        print("=" * 80)
        print("🔍 HTML Structure Debug")
        print("=" * 80)

        # Check title
        title = page.query_selector("h1")
        print(f"\n✅ Title: {title.inner_text() if title else 'NOT FOUND'}")

        # Check .entry-content
        content_div = page.query_selector(".entry-content")
        print(f"\n✅ .entry-content found: {content_div is not None}")

        # Try alternative selectors
        article = page.query_selector("article")
        print(f"✅ <article> found: {article is not None}")

        post_content = page.query_selector(".post-content")
        print(f"✅ .post-content found: {post_content is not None}")

        content_area = page.query_selector(".content-area")
        print(f"✅ .content-area found: {content_area is not None}")

        main_content = page.query_selector("main")
        print(f"✅ <main> found: {main_content is not None}")

        # Find working selector
        working_selector = None
        if content_div:
            working_selector = ".entry-content"
        elif article:
            working_selector = "article"
        elif post_content:
            working_selector = ".post-content"
        elif content_area:
            working_selector = ".content-area"
        elif main_content:
            working_selector = "main"

        if not working_selector:
            print("\n❌ No content container found!")
            # Save page HTML for inspection
            html = page.content()
            print(f"\n📄 Saving HTML to /tmp/debug_page.html")
            with open("/tmp/debug_page.html", "w") as f:
                f.write(html)
            browser.close()
            return

        print(f"\n✅ Using selector: {working_selector}")
        content_div = page.query_selector(working_selector)

        if content_div:
            # Count paragraphs
            paragraphs = content_div.query_selector_all("p")
            print(f"   • Total <p> tags: {len(paragraphs)}")

            # Print first 3 paragraphs
            print(f"\n   📝 First 3 paragraphs:")
            for idx, p in enumerate(paragraphs[:3], 1):
                text = p.inner_text().strip()
                print(f"      {idx}. {text[:80]}...")

            # Check images
            images = content_div.query_selector_all("img")
            print(f"\n   🖼️  Total images: {len(images)}")
            for idx, img in enumerate(images[:3], 1):
                src = img.get_attribute("src")
                alt = img.get_attribute("alt")
                classes = img.get_attribute("class")
                print(f"      {idx}. src={src[:60]}...")
                print(f"         alt={alt}")
                print(f"         class={classes}")

        browser.close()


if __name__ == "__main__":
    debug_page()
