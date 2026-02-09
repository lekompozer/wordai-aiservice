#!/usr/bin/env python3
"""
Test crawler for single song from loidichvn.com
Extract: title, artist, category, youtube URL, english lyrics, vietnamese lyrics
Output: JSON file for inspection
"""

import json
import time
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, Page


def extract_song_data(page: Page, song_url: str) -> dict:
    """
    Extract all song data from loidichvn.com song page

    Args:
        page: Playwright page object
        song_url: Full URL to song page (e.g., https://loidichvn.com/Baby-Girl__Blueface_n4.song)

    Returns:
        Dict with song metadata and lyrics
    """
    print(f"🔍 Navigating to: {song_url}")
    page.goto(song_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)  # Wait for dynamic content to load

    # Get full HTML for debugging
    html_content = page.content()

    # Save raw HTML for inspection
    debug_dir = Path(__file__).parent / "debug_html"
    debug_dir.mkdir(exist_ok=True)

    html_file = debug_dir / "song_page.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"💾 Saved HTML to: {html_file}")

    # Extract song data
    song_data = {
        "url": song_url,
        "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Extract title - try multiple selectors
    print("\n📌 Extracting title...")
    title_selectors = ["h1.tblue", "h1", ".song-title", "title"]

    for selector in title_selectors:
        try:
            elem = page.query_selector(selector)
            if elem:
                text = elem.inner_text().strip()
                if text:
                    song_data["title"] = text
                    print(f"  ✅ Title (from {selector}): {text}")
                    break
        except:
            pass

    # Extract artist - look for pattern "Tên ca sĩ:" or similar
    print("\n📌 Extracting artist...")
    artist_patterns = [
        r"Ca sĩ:\s*(.+?)(?:\n|$)",
        r"Nghệ sĩ:\s*(.+?)(?:\n|$)",
        r"Artist:\s*(.+?)(?:\n|$)",
    ]

    for pattern in artist_patterns:
        match = re.search(pattern, html_content, re.IGNORECASE)
        if match:
            artist = match.group(1).strip()
            song_data["artist"] = artist
            print(f"  ✅ Artist: {artist}")
            break

    # Try to extract artist from URL pattern: {song}__{artist}_n{id}.song
    if "artist" not in song_data:
        url_match = re.search(r"__([^_]+)_n\d+\.song", song_url)
        if url_match:
            artist = url_match.group(1).replace("-", " ").title()
            song_data["artist"] = artist
            print(f"  ✅ Artist (from URL): {artist}")

    # Extract category
    print("\n📌 Extracting category...")
    category_selectors = [".category", ".genre", "span.category"]

    # Also search in HTML for category patterns
    category_match = re.search(
        r"Thể loại:\s*(.+?)(?:\n|<)", html_content, re.IGNORECASE
    )
    if category_match:
        category = category_match.group(1).strip()
        song_data["category"] = category
        print(f"  ✅ Category: {category}")
    else:
        song_data["category"] = "Unknown Category"
        print(f"  ⚠️  Category not found, using default")

    # Extract YouTube URL
    print("\n📌 Extracting YouTube URL...")
    youtube_patterns = [
        r"https?://(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})",
        r"https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]

    for pattern in youtube_patterns:
        match = re.search(pattern, html_content)
        if match:
            video_id = match.group(1)
            youtube_url = f"https://youtu.be/{video_id}"
            song_data["youtube_url"] = youtube_url
            song_data["youtube_video_id"] = video_id
            print(f"  ✅ YouTube: {youtube_url}")
            break

    # Extract English lyrics
    print("\n📌 Extracting English lyrics...")
    english_lyrics_selectors = [
        "#lyrics-en",
        ".lyrics-english",
        ".en-lyrics",
        "div[id*='english']",
        "div[class*='english']",
    ]

    english_text = extract_lyrics_by_selectors(
        page, english_lyrics_selectors, "English"
    )

    # If not found, try to find in HTML structure
    if not english_text:
        # Look for lyrics in divs/pre tags
        lyrics_divs = page.query_selector_all("div.lyrics, pre, .lyric-content")
        if lyrics_divs and len(lyrics_divs) >= 2:
            # Usually first one is English, second is Vietnamese
            english_text = lyrics_divs[0].inner_text().strip()
            print(f"  ✅ English lyrics found (structural): {len(english_text)} chars")

    song_data["lyrics_english"] = english_text or ""

    # Extract Vietnamese lyrics
    print("\n📌 Extracting Vietnamese lyrics...")
    vietnamese_lyrics_selectors = [
        "#lyrics-vi",
        ".lyrics-vietnamese",
        ".vi-lyrics",
        "div[id*='vietnamese']",
        "div[class*='vietnamese']",
    ]

    vietnamese_text = extract_lyrics_by_selectors(
        page, vietnamese_lyrics_selectors, "Vietnamese"
    )

    # If not found, try second lyrics div
    if not vietnamese_text:
        lyrics_divs = page.query_selector_all("div.lyrics, pre, .lyric-content")
        if lyrics_divs and len(lyrics_divs) >= 2:
            vietnamese_text = lyrics_divs[1].inner_text().strip()
            print(
                f"  ✅ Vietnamese lyrics found (structural): {len(vietnamese_text)} chars"
            )

    song_data["lyrics_vietnamese"] = vietnamese_text or ""

    # Extract from URL pattern for ID and slug
    print("\n📌 Extracting metadata from URL...")
    url_pattern = r"/([^/]+)_n(\d+)\.song$"
    url_match = re.search(url_pattern, song_url)
    if url_match:
        song_data["slug"] = url_match.group(1)
        song_data["external_id"] = int(url_match.group(2))
        print(f"  ✅ Slug: {song_data['slug']}")
        print(f"  ✅ ID: {song_data['external_id']}")

    return song_data


def extract_lyrics_by_selectors(page: Page, selectors: list, label: str) -> str:
    """Try multiple selectors to find lyrics"""
    for selector in selectors:
        try:
            elem = page.query_selector(selector)
            if elem:
                text = elem.inner_text().strip()
                if text and len(text) > 50:  # Validate minimum length
                    print(
                        f"  ✅ {label} lyrics found (selector: {selector}): {len(text)} chars"
                    )
                    return text
        except:
            pass
    return ""


def main():
    # Test URL
    test_url = "https://loidichvn.com/Baby-Girl__Blueface_n4.song"

    print("=" * 80)
    print("🎵 LoiDich Song Crawler Test")
    print("=" * 80)
    print(f"URL: {test_url}\n")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)  # headless mode for testing
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        page = context.new_page()

        try:
            # Extract song data
            song_data = extract_song_data(page, test_url)

            # Save to JSON
            output_dir = Path(__file__).parent / "test_output"
            output_dir.mkdir(exist_ok=True)

            output_file = output_dir / "song_data.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(song_data, f, indent=2, ensure_ascii=False)

            # Print summary
            print("\n" + "=" * 80)
            print("✅ EXTRACTION COMPLETE")
            print("=" * 80)
            print(f"📄 Saved to: {output_file}")
            print("\n📊 Summary:")
            print(f"  Title: {song_data.get('title', 'NOT FOUND')}")
            print(f"  Artist: {song_data.get('artist', 'NOT FOUND')}")
            print(f"  Category: {song_data.get('category', 'NOT FOUND')}")
            print(f"  YouTube: {song_data.get('youtube_url', 'NOT FOUND')}")
            print(f"  English lyrics: {len(song_data.get('lyrics_english', ''))} chars")
            print(
                f"  Vietnamese lyrics: {len(song_data.get('lyrics_vietnamese', ''))} chars"
            )
            print(f"  External ID: {song_data.get('external_id', 'NOT FOUND')}")
            print("=" * 80)

            # Pretty print JSON
            print("\n📋 Full JSON data:")
            print(json.dumps(song_data, indent=2, ensure_ascii=False))

        finally:
            browser.close()


if __name__ == "__main__":
    main()
