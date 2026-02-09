#!/usr/bin/env python3
"""
Clean test crawler for loidichvn.com song page
Extracts: title, artist, category, youtube URL, lyrics (English & Vietnamese)
Saves to JSON (no database yet)
"""

import json as json_module
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path


def extract_song_data(url: str) -> dict:
    """Extract complete song data from loidichvn.com"""

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

    html_file = debug_dir / "loidich_song_final.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"💾 Saved HTML to: {html_file}")

    song_data = {"url": url}

    # ========== BEST METHOD: Extract from Next.js JSON data ==========
    print("\n📌 Extracting from __NEXT_DATA__ JSON...")
    next_data_script = soup.find("script", id="__NEXT_DATA__")

    if next_data_script:
        try:
            next_data = json_module.loads(next_data_script.string)
            song = next_data.get("props", {}).get("pageProps", {}).get("song", {})

            if song:
                # Basic metadata
                song_data["title"] = song.get("SongName", "")
                song_data["external_id"] = song.get("Id")
                song_data["youtube_video_id"] = song.get("YoutubeId", "")
                song_data["view_count"] = song.get("SongCount", 0)

                # Artist
                artist_model = song.get("ArtistModel", {})
                song_data["artist"] = artist_model.get("ArtistName", "")
                song_data["artist_id"] = artist_model.get("Id")

                # Category
                category_model = song.get("CategoryModel", {})
                song_data["category"] = category_model.get("CategoryName", "")
                song_data["category_id"] = category_model.get("Id")

                # Lyrics (clean HTML tags)
                english_html = song.get("LyricAnh", "")
                vietnamese_html = song.get("LyricVietNam", "")

                # Convert <br> to newlines, remove other HTML
                english_clean = re.sub(r"<br\s*/?>", "\n", english_html)
                english_clean = re.sub(r"<[^>]+>", "", english_clean)
                english_clean = english_clean.strip()

                vietnamese_clean = re.sub(r"<br\s*/?>", "\n", vietnamese_html)
                vietnamese_clean = re.sub(r"<[^>]+>", "", vietnamese_clean)
                vietnamese_clean = vietnamese_clean.strip()

                song_data["lyrics_english"] = english_clean
                song_data["lyrics_vietnamese"] = vietnamese_clean

                print(f"  ✅ Title: {song_data['title']}")
                print(f"  ✅ Artist: {song_data['artist']}")
                print(f"  ✅ Category: {song_data['category']}")
                print(f"  ✅ YouTube ID: {song_data['youtube_video_id']}")
                print(f"  ✅ English lyrics: {len(english_clean)} chars")
                print(f"  ✅ Vietnamese lyrics: {len(vietnamese_clean)} chars")
                print(f"  ✅ View count: {song_data['view_count']}")

        except Exception as e:
            print(f"  ❌ JSON parsing failed: {e}")
            import traceback

            traceback.print_exc()

    # Construct YouTube URL
    if song_data.get("youtube_video_id"):
        song_data["youtube_url"] = f"https://youtu.be/{song_data['youtube_video_id']}"

    # Extract slug from URL
    url_match = re.search(r"/([^/]+)_n(\d+)\.song", url)
    if url_match:
        song_data["slug"] = url_match.group(1)

    return song_data


def main():
    test_url = "https://loidichvn.com/Baby-Girl__Blueface_n4.song"

    print("=" * 80)
    print("🎵 LoiDich Song Crawler - Clean Test")
    print("=" * 80)
    print(f"URL: {test_url}\n")

    try:
        # Extract data
        song_data = extract_song_data(test_url)

        # Save to JSON
        output_dir = Path(__file__).parent / "test_output"
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / "song_clean.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json_module.dump(song_data, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 80)
        print("✅ EXTRACTION COMPLETE")
        print("=" * 80)
        print(f"📄 Saved to: {output_file}\n")

        print("📊 Summary:")
        print(f"  Title: {song_data.get('title', 'NOT FOUND')}")
        print(f"  Artist: {song_data.get('artist', 'NOT FOUND')}")
        print(f"  Category: {song_data.get('category', 'NOT FOUND')}")
        print(f"  YouTube: {song_data.get('youtube_url', 'NOT FOUND')}")
        print(f"  English lyrics: {len(song_data.get('lyrics_english', ''))} chars")
        print(
            f"  Vietnamese lyrics: {len(song_data.get('lyrics_vietnamese', ''))} chars"
        )
        print(f"  View count: {song_data.get('view_count', 0)}")
        print("=" * 80)

        # Show first 200 chars of each lyrics
        if song_data.get("lyrics_english"):
            print("\n📝 English lyrics preview:")
            print(song_data["lyrics_english"][:200] + "...")

        if song_data.get("lyrics_vietnamese"):
            print("\n📝 Vietnamese lyrics preview:")
            print(song_data["lyrics_vietnamese"][:200] + "...")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
