"""
Test crawler for loidichvn.com category pages
Crawls song listings from category pages and extracts full song data
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from typing import List, Dict, Any


def get_song_urls_from_page(page_num: int) -> List[str]:
    """
    Extract song URLs from a category page

    Args:
        page_num: Page number (1, 2, 3, etc.)

    Returns:
        List of song URLs
    """
    url = f"https://loidichvn.com/new/page/{page_num}"
    print(f"\n📄 Fetching page {page_num}: {url}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Find __NEXT_DATA__ script tag
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if not next_data_script:
            print("❌ Could not find __NEXT_DATA__ script tag")
            return []

        next_data = json.loads(next_data_script.string)

        # Extract songs from pageProps
        songs = next_data.get("props", {}).get("pageProps", {}).get("songs", [])

        if not songs:
            print("❌ No songs found in page data")
            return []

        # Build song URLs
        song_urls = []
        for song in songs:
            # Use SongHeader which contains the full slug
            song_header = song.get("SongHeader", "")
            if song_header:
                song_url = f"https://loidichvn.com/{song_header}.song"
                song_urls.append(song_url)

        print(f"✅ Found {len(song_urls)} songs on page {page_num}")
        return song_urls

    except Exception as e:
        print(f"❌ Error fetching page {page_num}: {e}")
        return []


def extract_song_data(song_url: str) -> Dict[str, Any]:
    """
    Extract full song data from a song page

    Args:
        song_url: Full URL to song page

    Returns:
        Dictionary with song data
    """
    print(f"  🎵 Fetching: {song_url}")

    try:
        response = requests.get(song_url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Find __NEXT_DATA__ script tag
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if not next_data_script:
            print(f"  ❌ No __NEXT_DATA__ found")
            return None

        next_data = json.loads(next_data_script.string)
        song = next_data.get("props", {}).get("pageProps", {}).get("song", {})

        if not song:
            print(f"  ❌ No song data found")
            return None

        # Extract and clean lyrics
        def clean_lyrics(html_content):
            if not html_content:
                return ""
            # Replace <br> tags with newlines
            cleaned = re.sub(r"<br\s*/?>", "\n", html_content)
            # Remove all other HTML tags
            cleaned = re.sub(r"<[^>]+>", "", cleaned)
            # Clean up whitespace
            cleaned = re.sub(r"\n\s*\n", "\n\n", cleaned)
            return cleaned.strip()

        english_lyrics = clean_lyrics(song.get("LyricAnh", ""))
        vietnamese_lyrics = clean_lyrics(song.get("LyricVietNam", ""))

        # Build YouTube URL
        youtube_id = song.get("YoutubeId", "")
        youtube_url = f"https://youtu.be/{youtube_id}" if youtube_id else ""

        # Extract artist and category from nested models
        artist_model = song.get("ArtistModel", {})
        category_model = song.get("CategoryModel", {})

        song_data = {
            "song_id": song.get("Id"),
            "title": song.get("SongName", ""),
            "artist": artist_model.get("ArtistName", ""),
            "category": category_model.get("CategoryName", ""),
            "youtube_url": youtube_url,
            "youtube_id": youtube_id,
            "view_count": song.get("SongCount", 0),
            "english_lyrics": english_lyrics,
            "vietnamese_lyrics": vietnamese_lyrics,
            "english_lyrics_length": len(english_lyrics),
            "vietnamese_lyrics_length": len(vietnamese_lyrics),
            "url": song_url,
            "has_english_lyrics": len(english_lyrics) > 0,
            "has_vietnamese_lyrics": len(vietnamese_lyrics) > 0,
        }

        print(f"  ✅ {song_data['title']} by {song_data['artist']}")
        return song_data

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def crawl_category_pages(
    num_pages: int = 2, delay: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Crawl multiple category pages and extract all song data

    Args:
        num_pages: Number of pages to crawl
        delay: Delay between requests (seconds)

    Returns:
        List of song data dictionaries
    """
    all_songs = []

    print(f"\n{'='*60}")
    print(f"🚀 Starting crawl of {num_pages} pages")
    print(f"{'='*60}")

    for page_num in range(1, num_pages + 1):
        # Get song URLs from category page
        song_urls = get_song_urls_from_page(page_num)

        if not song_urls:
            print(f"⚠️  No songs found on page {page_num}, skipping...")
            continue

        # Extract data from each song
        for i, song_url in enumerate(song_urls, 1):
            print(f"\n  [{i}/{len(song_urls)}]", end=" ")

            song_data = extract_song_data(song_url)
            if song_data:
                all_songs.append(song_data)

            # Delay between requests to be polite
            if i < len(song_urls):  # Don't delay after last song
                time.sleep(delay)

        # Delay between pages
        if page_num < num_pages:
            print(f"\n⏸️  Waiting {delay}s before next page...")
            time.sleep(delay)

    return all_songs


def main():
    """Main execution"""

    # Crawl 2 pages
    songs = crawl_category_pages(num_pages=2, delay=1.0)

    print(f"\n{'='*60}")
    print(f"📊 CRAWL COMPLETE")
    print(f"{'='*60}")
    print(f"Total songs: {len(songs)}")

    if songs:
        # Calculate statistics
        with_english = sum(1 for s in songs if s["has_english_lyrics"])
        with_vietnamese = sum(1 for s in songs if s["has_vietnamese_lyrics"])
        with_youtube = sum(1 for s in songs if s["youtube_url"])

        print(f"With English lyrics: {with_english}/{len(songs)}")
        print(f"With Vietnamese lyrics: {with_vietnamese}/{len(songs)}")
        print(f"With YouTube link: {with_youtube}/{len(songs)}")

        # Save to JSON
        output_file = "crawler/test_output/loidich_songs_2pages.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(songs, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Saved to: {output_file}")

        # Show sample
        print(f"\n{'='*60}")
        print("📝 Sample songs:")
        print(f"{'='*60}")
        for song in songs[:3]:
            print(f"\n🎵 {song['title']}")
            print(f"   Artist: {song['artist']}")
            print(f"   Category: {song['category']}")
            print(f"   YouTube: {song['youtube_url']}")
            print(f"   Views: {song['view_count']:,}")
            print(
                f"   Lyrics: EN={song['english_lyrics_length']} chars, VI={song['vietnamese_lyrics_length']} chars"
            )
    else:
        print("❌ No songs crawled")


if __name__ == "__main__":
    main()
