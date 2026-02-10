"""
Test crawler for loidichvn.com - 2 pages with MongoDB
Tests crawling and database insertion before full run

Usage:
    python crawler/test_loidich_2pages_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from bs4 import BeautifulSoup
import json
import time
import re
from typing import List, Dict, Any
from datetime import datetime
import logging

from src.database.db_manager import DBManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LoidichTestCrawler:
    """Test crawler for 2 pages only"""

    BASE_URL = "https://loidichvn.com"
    REQUEST_DELAY = 1.0  # seconds

    def __init__(self):
        self.db_manager = DBManager()
        self.db = self.db_manager.db
        self.collection = self.db.song_lyrics

        self.stats = {
            "total_found": 0,
            "total_inserted": 0,
            "total_skipped": 0,
            "total_errors": 0,
        }

    async def fetch_page(self, url: str) -> str:
        """Fetch page content"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def extract_youtube_id(self, youtube_url: str) -> str:
        """Extract YouTube video ID from various URL formats"""
        if not youtube_url:
            return ""

        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)",
            r"youtube\.com\/embed\/([^&\n?#]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)

        return youtube_url  # Return as-is if no pattern matches

    def clean_lyrics(self, html_content: str) -> str:
        """Clean lyrics HTML to plain text"""
        if not html_content:
            return ""

        # Replace <br> with newlines
        cleaned = re.sub(r"<br\s*/?>", "\n", html_content)
        # Remove all HTML tags
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        # Clean up multiple newlines
        cleaned = re.sub(r"\n\s*\n", "\n\n", cleaned)
        return cleaned.strip()

    async def extract_song_data(self, song_url: str) -> Dict[str, Any]:
        """Extract full song data from song page"""
        try:
            html = await self.fetch_page(song_url)
            soup = BeautifulSoup(html, "html.parser")

            # Find __NEXT_DATA__ script
            next_data_script = soup.find("script", id="__NEXT_DATA__")
            if not next_data_script:
                logger.error(f"No __NEXT_DATA__ found: {song_url}")
                return None

            next_data = json.loads(next_data_script.string)
            song = next_data.get("props", {}).get("pageProps", {}).get("song", {})

            if not song:
                logger.error(f"No song data: {song_url}")
                return None

            # Extract nested models
            artist_model = song.get("ArtistModel", {})
            category_model = song.get("CategoryModel", {})

            # Clean lyrics
            english_lyrics = self.clean_lyrics(song.get("LyricAnh", ""))
            vietnamese_lyrics = self.clean_lyrics(song.get("LyricVietNam", ""))

            # Calculate word count
            word_count = len(english_lyrics.split()) if english_lyrics else 0

            # Build YouTube data
            youtube_id = song.get("YoutubeId", "")
            youtube_url = f"https://youtu.be/{youtube_id}" if youtube_id else ""

            # Build song document
            song_data = {
                "song_id": str(song.get("Id", "")),
                "title": song.get("SongName", ""),
                "artist": artist_model.get("ArtistName", ""),
                "category": category_model.get("CategoryName", ""),
                "english_lyrics": english_lyrics,
                "vietnamese_lyrics": vietnamese_lyrics,
                "youtube_url": youtube_url,
                "youtube_id": youtube_id,
                "view_count": song.get("SongCount", 0),
                "source_url": song_url,
                "is_processed": False,
                "has_profanity": False,
                "word_count": word_count,
                "crawled_at": datetime.utcnow(),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            logger.info(f"✅ Extracted: {song_data['title']} - {song_data['artist']}")
            return song_data

        except Exception as e:
            logger.error(f"❌ Error extracting {song_url}: {e}")
            self.stats["total_errors"] += 1
            return None

    async def get_song_urls_from_page(self, category_url: str, page: int) -> List[str]:
        """Get all song URLs from a category page"""
        # All pages use /page/X format
        url = f"{category_url}/page/{page}"

        try:
            html = await self.fetch_page(url)
            soup = BeautifulSoup(html, "html.parser")

            # Find __NEXT_DATA__ script
            next_data_script = soup.find("script", id="__NEXT_DATA__")
            if not next_data_script:
                logger.error(f"No __NEXT_DATA__ on page {page}")
                return []

            next_data = json.loads(next_data_script.string)
            songs = next_data.get("props", {}).get("pageProps", {}).get("songs", [])

            if not songs:
                logger.warning(f"No songs on page {page}")
                return []

            # Build song URLs
            song_urls = []
            for song in songs:
                song_header = song.get("SongHeader", "")
                if song_header:
                    song_url = f"{self.BASE_URL}/{song_header}.song"
                    song_urls.append(song_url)

            logger.info(f"📄 Found {len(song_urls)} songs on page {page}")
            return song_urls

        except Exception as e:
            logger.error(f"❌ Error fetching page {page}: {e}")
            return []

    async def test_crawl_2_pages(self):
        """Crawl only 2 pages from /new category"""
        logger.info("=" * 80)
        logger.info("🧪 TEST CRAWL: 2 pages from /new category")
        logger.info("=" * 80)

        category_url = f"{self.BASE_URL}/new"

        for page in range(1, 3):  # Pages 1 and 2
            logger.info(f"\n📖 Processing page {page}/2...")

            # Get song URLs from page
            song_urls = await self.get_song_urls_from_page(category_url, page)

            if not song_urls:
                logger.warning(f"No songs found on page {page}")
                continue

            self.stats["total_found"] += len(song_urls)

            # Process each song
            for idx, song_url in enumerate(song_urls, 1):
                logger.info(f"\n  [{idx}/{len(song_urls)}] Processing: {song_url}")

                # Check if already exists
                existing = self.collection.find_one({"source_url": song_url})
                if existing:
                    logger.info(f"  ⏭️  Already exists, skipping")
                    self.stats["total_skipped"] += 1
                    continue

                # Extract song data
                song_data = await self.extract_song_data(song_url)

                if song_data:
                    # Insert to MongoDB
                    try:
                        self.collection.insert_one(song_data)
                        self.stats["total_inserted"] += 1
                        logger.info(f"  💾 Inserted to MongoDB")
                    except Exception as e:
                        logger.error(f"  ❌ MongoDB insert error: {e}")
                        self.stats["total_errors"] += 1

                # Rate limiting
                time.sleep(self.REQUEST_DELAY)

            logger.info(f"\n⏸️  Page {page} complete. Waiting before next page...")
            time.sleep(self.REQUEST_DELAY)

        # Print final stats
        logger.info("\n" + "=" * 80)
        logger.info("📊 TEST CRAWL COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total found: {self.stats['total_found']}")
        logger.info(f"Total inserted: {self.stats['total_inserted']}")
        logger.info(f"Total skipped: {self.stats['total_skipped']}")
        logger.info(f"Total errors: {self.stats['total_errors']}")
        logger.info("=" * 80)

        # Verify in database
        total_in_db = self.collection.count_documents({})
        logger.info(f"\n✅ Total songs in database: {total_in_db}")

        # Show sample
        sample_songs = list(self.collection.find().limit(3))
        if sample_songs:
            logger.info("\n📝 Sample songs in database:")
            for song in sample_songs:
                logger.info(
                    f"  • {song['title']} - {song['artist']} ({song['category']})"
                )
                logger.info(f"    Song ID: {song['song_id']}")
                logger.info(f"    Word count: {song['word_count']}")
                logger.info(f"    YouTube: {song['youtube_url']}")


async def main():
    """Main execution"""
    import asyncio

    crawler = LoidichTestCrawler()
    await crawler.test_crawl_2_pages()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
