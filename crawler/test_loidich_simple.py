#!/usr/bin/env python3
"""
Simple test crawler using requests + BeautifulSoup
Faster and simpler than Playwright for static content
"""

import json
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path


def extract_song_data(url: str) -> dict:
    """Extract song data using requests + BeautifulSoup"""

    print(f"🔍 Fetching: {url}")

    # Fetch HTML
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # Save HTML for debugging
    debug_dir = Path(__file__).parent / "debug_html"
    debug_dir.mkdir(exist_ok=True)

    html_file = debug_dir / "loidich_song.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"💾 Saved HTML to: {html_file}")

    song_data = {
        "url": url,
    }

    # Extract title
    print("\n📌 Extracting title...")
    title = soup.find("title")
    if title:
        # Clean title (remove " - Lời Dịch VN" suffix)
        title_text = title.get_text().strip()
        title_text = re.sub(r"\s*-\s*Lời Dịch.*$", "", title_text)
        song_data["title"] = title_text
        print(f"  ✅ Title: {title_text}")

    # Extract from URL pattern
    print("\n📌 Extracting from URL...")
    url_match = re.search(r"/([^/]+)__([^_]+)_n(\d+)\.song", url)
    if url_match:
        song_slug = url_match.group(1).replace("-", " ")
        artist_slug = url_match.group(2).replace("-", " ")
        song_id = int(url_match.group(3))

        song_data["title_from_url"] = song_slug
        song_data["artist"] = artist_slug
        song_data["external_id"] = song_id
        song_data["slug"] = url_match.group(1)

        print(f"  ✅ Song (from URL): {song_slug}")
        print(f"  ✅ Artist (from URL): {artist_slug}")
        print(f"  ✅ ID: {song_id}")

    # Find YouTube link
    print("\n📌 Extracting YouTube URL...")
    youtube_patterns = [
        r"https?://(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})",
        r"https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]

    for pattern in youtube_patterns:
        match = re.search(pattern, html)
        if match:
            video_id = match.group(1)
            youtube_url = f"https://youtu.be/{video_id}"
            song_data["youtube_url"] = youtube_url
            song_data["youtube_video_id"] = video_id
            print(f"  ✅ YouTube: {youtube_url}")
            break

    # Find category
    print("\n📌 Searching for category...")
    # Look for category in HTML
    category_match = re.search(r"Thể loại:\s*([^<\n]+)", html, re.IGNORECASE)
    if category_match:
        category = category_match.group(1).strip()
        song_data["category"] = category
        print(f"  ✅ Category: {category}")
    else:
        song_data["category"] = "Unknown Category"
        print(f"  ⚠️  Category not found")

    # Extract lyrics - look for specific structures
    print("\n📌 Extracting lyrics...")

    # Method 1: Find all <p> tags in main content
    lyrics_containers = soup.find_all(
        ["div", "pre"], class_=re.compile(r"lyric|content")
    )

    if lyrics_containers:
        print(f"  Found {len(lyrics_containers)} potential lyrics containers")

    # Method 2: Find all paragraphs that might contain lyrics
    all_paragraphs = soup.find_all("p")

    # Collect text content
    english_parts = []
    vietnamese_parts = []

    # Try to find lyrics by looking for large text blocks
    for p in all_paragraphs:
        text = p.get_text().strip()
        if len(text) > 50:  # Likely lyrics if > 50 chars
            # Heuristic: if contains Vietnamese characters, it's Vietnamese lyrics
            if re.search(
                r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
                text,
            ):
                vietnamese_parts.append(text)
            else:
                english_parts.append(text)

    song_data["lyrics_english"] = "\n\n".join(english_parts)
    song_data["lyrics_vietnamese"] = "\n\n".join(vietnamese_parts)

    print(f"  English lyrics: {len(song_data['lyrics_english'])} chars")
    print(f"  Vietnamese lyrics: {len(song_data['lyrics_vietnamese'])} chars")

    # Print all found tags for debugging
    print("\n🔍 HTML Structure Analysis:")
    print(f"  Total <p> tags: {len(all_paragraphs)}")
    print(f"  Total <div> tags: {len(soup.find_all('div'))}")
    print(f"  Total <pre> tags: {len(soup.find_all('pre'))}")

    # Find unique classes
    all_classes = set()
    for tag in soup.find_all(True):
        if tag.get("class"):
            all_classes.update(tag["class"])

    print(f"\n  Unique classes found: {len(all_classes)}")
    print(f"  Sample classes: {list(all_classes)[:20]}")

    return song_data


def main():
    test_url = "https://loidichvn.com/Baby-Girl__Blueface_n4.song"

    print("=" * 80)
    print("🎵 LoiDich Song Crawler (Simple Test)")
    print("=" * 80)
    print(f"URL: {test_url}\n")

    try:
        # Extract data
        song_data = extract_song_data(test_url)

        # Save to JSON
        output_dir = Path(__file__).parent / "test_output"
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / "loidich_song_simple.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(song_data, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 80)
        print("✅ EXTRACTION COMPLETE")
        print("=" * 80)
        print(f"📄 Saved to: {output_file}")
        print("\n📊 Summary:")
        print(f"  Title: {song_data.get('title', 'NOT FOUND')}")
        print(f"  Artist: {song_data.get('artist', 'NOT FOUND')}")
        print(f"  Category: {song_data.get('category', 'NOT FOUND')}")
        print(f"  YouTube: {song_data.get('youtube_url', 'NOT FOUND')}")
        print(f"  External ID: {song_data.get('external_id', 'NOT FOUND')}")
        print("=" * 80)

        print("\n📋 Full JSON:")
        print(json.dumps(song_data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
