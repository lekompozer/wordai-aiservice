"""
Full Crawler for loidichvn.com

Crawls all ~23,000 songs from loidichvn.com and saves to MongoDB collection: song_lyrics

Features:
- Pagination support for all category pages
- Batch insert (100 songs/batch)
- Retry logic with exponential backoff
- Detailed logging (success, errors, skipped)
- Resume capability (skip existing songs)

Usage:
    python crawler/loidich_full_crawler.py

Expected time: 4-6 hours with 1s delay/request
"""

import sys
from pathlib import Path
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup
import httpx
from src.database.db_manager import DBManager
from tqdm import tqdm

# Setup logging
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / f"full_crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class LoidichCrawler:
    """Full crawler for loidichvn.com"""

    BASE_URL = "https://loidichvn.com"
    CATEGORY_URL = f"{BASE_URL}/category"
    REQUEST_DELAY = 1  # seconds between requests
    BATCH_SIZE = 100  # songs per batch insert
    MAX_RETRIES = 3

    def __init__(self):
        self.db_manager = DBManager()
        self.db = self.db_manager.db
        self.collection = self.db.song_lyrics

        self.stats = {
            "total_found": 0,
            "total_crawled": 0,
            "total_skipped": 0,
            "total_errors": 0,
            "categories_processed": 0,
        }

    async def fetch_page(self, url: str, retry_count: int = 0) -> str:
        """Fetch a page with retry logic"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text

        except Exception as e:
            if retry_count < self.MAX_RETRIES:
                wait_time = 2**retry_count  # Exponential backoff
                logger.warning(
                    f"  Retry {retry_count + 1}/{self.MAX_RETRIES} after {wait_time}s: {url}"
                )
                await asyncio.sleep(wait_time)
                return await self.fetch_page(url, retry_count + 1)
            else:
                logger.error(f"  Failed after {self.MAX_RETRIES} retries: {url}")
                raise

    def extract_youtube_id(self, youtube_url: str) -> str:
        """Extract YouTube video ID from URL"""
        if not youtube_url:
            return ""

        # Pattern: youtube.com/watch?v=VIDEO_ID or youtu.be/VIDEO_ID
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)

        return ""

    async def extract_song_data(self, song_url: str) -> Dict[str, Any]:
        """Extract song data from song page"""
        try:
            html = await self.fetch_page(song_url)
            soup = BeautifulSoup(html, "html.parser")

            # Find __NEXT_DATA__ script tag
            script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if not script_tag:
                logger.error(f"  No __NEXT_DATA__ found: {song_url}")
                return None

            import json

            data = json.loads(script_tag.string)

            # Navigate to song data
            props = data.get("props", {})
            page_props = props.get("pageProps", {})
            song_detail = page_props.get("songDetail", {})

            if not song_detail:
                logger.error(f"  No songDetail in data: {song_url}")
                return None

            # Extract fields
            song_id = song_detail.get("Id", "")
            title = song_detail.get("Title", "")

            # Artist from ArtistModel
            artist_model = song_detail.get("ArtistModel", {})
            artist = artist_model.get("ArtistName", "") if artist_model else ""

            # Category from CategoryModel
            category_model = song_detail.get("CategoryModel", {})
            category = category_model.get("CategoryName", "") if category_model else ""

            # Lyrics
            english_lyrics = song_detail.get("Lyric", "")
            vietnamese_lyrics = song_detail.get("MeanLyric", "")

            # YouTube
            youtube_url = song_detail.get("Youtube", "")
            youtube_id = self.extract_youtube_id(youtube_url)

            # View count
            view_count = song_detail.get("ViewCount", 0)

            # Word count (rough estimate)
            word_count = len(english_lyrics.split()) if english_lyrics else 0

            return {
                "song_id": str(song_id),
                "title": title,
                "artist": artist,
                "category": category,
                "english_lyrics": english_lyrics,
                "vietnamese_lyrics": vietnamese_lyrics,
                "youtube_url": youtube_url,
                "youtube_id": youtube_id,
                "view_count": view_count,
                "source_url": song_url,
                "word_count": word_count,
                "is_processed": False,
                "has_profanity": False,
                "crawled_at": datetime.utcnow(),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

        except Exception as e:
            logger.error(f"  Error extracting song data from {song_url}: {e}")
            return None

    async def get_song_urls_from_page(self, category_url: str, page: int) -> List[str]:
        """Get all song URLs from a category page"""
        try:
            # All pages use /page/X format
            url = f"{category_url}/page/{page}"
            html = await self.fetch_page(url)
            soup = BeautifulSoup(html, "html.parser")

            # Find __NEXT_DATA__ script tag
            script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
            if not script_tag:
                return []

            import json

            data = json.loads(script_tag.string)

            # Navigate to song list
            props = data.get("props", {})
            page_props = props.get("pageProps", {})
            song_list = page_props.get("SongList", [])

            # Extract URLs
            urls = []
            for song in song_list:
                url_slug = song.get("Url", "")
                if url_slug:
                    full_url = f"{self.BASE_URL}{url_slug}"
                    urls.append(full_url)

            return urls

        except Exception as e:
            logger.error(f"  Error getting URLs from page {page}: {e}")
            return []

    async def crawl_category(self, category_name: str, category_url: str):
        """Crawl all songs in a category"""
        logger.info(f"📂 Category: {category_name}")
        logger.info(f"   URL: {category_url}")

        page = 1
        category_total = 0
        batch = []

        while True:
            # Get song URLs from page
            song_urls = await self.get_song_urls_from_page(category_url, page)

            if not song_urls:
                logger.info(f"   Page {page}: No more songs, stopping")
                break

            logger.info(f"   Page {page}: Found {len(song_urls)} songs")
            self.stats["total_found"] += len(song_urls)

            # Process each song
            for song_url in tqdm(song_urls, desc=f"  Page {page}", leave=False):
                await asyncio.sleep(self.REQUEST_DELAY)  # Rate limiting

                # Check if already exists
                song_id = song_url.split("/")[-1]
                if self.collection.find_one({"source_url": song_url}):
                    self.stats["total_skipped"] += 1
                    continue

                # Extract song data
                song_data = await self.extract_song_data(song_url)

                if song_data:
                    batch.append(song_data)
                    category_total += 1
                    self.stats["total_crawled"] += 1

                    # Batch insert
                    if len(batch) >= self.BATCH_SIZE:
                        try:
                            self.collection.insert_many(batch, ordered=False)
                            logger.info(f"   ✅ Inserted batch of {len(batch)} songs")
                            batch = []
                        except Exception as e:
                            logger.error(f"   ❌ Batch insert error: {e}")
                            self.stats["total_errors"] += len(batch)
                            batch = []
                else:
                    self.stats["total_errors"] += 1

            page += 1

        # Insert remaining batch
        if batch:
            try:
                self.collection.insert_many(batch, ordered=False)
                logger.info(f"   ✅ Inserted final batch of {len(batch)} songs")
            except Exception as e:
                logger.error(f"   ❌ Final batch insert error: {e}")
                self.stats["total_errors"] += len(batch)

        logger.info(f"   Category total: {category_total} songs crawled")
        self.stats["categories_processed"] += 1

    async def run(self):
        """Run full crawler"""
        logger.info("=" * 80)
        logger.info("🎵 LOIDICHVN.COM FULL CRAWLER")
        logger.info("=" * 80)
        logger.info(f"Started at: {datetime.now()}")
        logger.info(f"Log file: {log_file}")
        logger.info("")

        # Define categories to crawl
        categories = [
            ("US-UK", f"{self.CATEGORY_URL}/us-uk"),
            ("Vpop", f"{self.CATEGORY_URL}/vpop"),
            ("Kpop", f"{self.CATEGORY_URL}/kpop"),
            ("Nhạc Hoa", f"{self.CATEGORY_URL}/nhac-hoa"),
            # Add more categories as needed
        ]

        # Crawl each category
        for category_name, category_url in categories:
            try:
                await self.crawl_category(category_name, category_url)
                logger.info("")
            except Exception as e:
                logger.error(f"❌ Category error: {category_name}: {e}")
                logger.info("")

        # Final stats
        logger.info("=" * 80)
        logger.info("📊 FINAL STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Categories processed: {self.stats['categories_processed']}")
        logger.info(f"Total songs found: {self.stats['total_found']}")
        logger.info(f"Successfully crawled: {self.stats['total_crawled']}")
        logger.info(f"Skipped (existing): {self.stats['total_skipped']}")
        logger.info(f"Errors: {self.stats['total_errors']}")
        logger.info("")
        logger.info(f"Finished at: {datetime.now()}")
        logger.info(f"Log saved to: {log_file}")
        logger.info("=" * 80)


async def main():
    """Main entry point"""
    crawler = LoidichCrawler()
    await crawler.run()


if __name__ == "__main__":
    asyncio.run(main())
