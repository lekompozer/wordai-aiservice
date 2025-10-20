"""
R2 File Downloader
Download files from Cloudflare R2 storage to local cache
"""

import os
import httpx
from pathlib import Path
from typing import Optional, Dict, Any
from src.utils.logger import setup_logger
from src.config.r2_storage import AIVungtauR2StorageConfig

logger = setup_logger()

# WordAI R2 Configuration (for simple-files)
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "wordai")
R2_ENDPOINT = os.getenv(
    "R2_ENDPOINT", "https://1a04e5e9c39583f1c8657fb9e52ba27a.r2.cloudflarestorage.com"
)
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")


class R2FileDownloader:
    """Download files from R2 storage to local cache"""

    def __init__(self):
        # Initialize R2 client for WordAI files
        self.wordai_r2_client = None
        self._init_wordai_client()

        # Initialize AIVungtau R2 client
        self.aivungtau_r2 = AIVungtauR2StorageConfig()

    def _init_wordai_client(self):
        """Initialize boto3 client for WordAI R2"""
        try:
            if not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
                logger.warning("⚠️ WordAI R2 credentials not configured")
                return

            import boto3

            self.wordai_r2_client = boto3.client(
                "s3",
                endpoint_url=R2_ENDPOINT,
                aws_access_key_id=R2_ACCESS_KEY_ID,
                aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                region_name="auto",
            )

            logger.info("✅ WordAI R2 client initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize WordAI R2 client: {e}")
            self.wordai_r2_client = None

    async def download_from_r2(
        self, r2_key: str, local_path: str, bucket_type: str = "wordai"
    ) -> bool:
        """
        Download file from R2 to local path

        Args:
            r2_key: R2 object key (path in bucket)
            local_path: Local file path to save
            bucket_type: "wordai" or "aivungtau"

        Returns:
            True if downloaded successfully
        """
        try:
            logger.info(f"⬇️ Downloading from R2: {r2_key}")

            # Ensure parent directory exists
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            if bucket_type == "wordai":
                return await self._download_wordai_file(r2_key, local_path)
            elif bucket_type == "aivungtau":
                return await self._download_aivungtau_file(r2_key, local_path)
            else:
                logger.error(f"❌ Unknown bucket type: {bucket_type}")
                return False

        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            return False

    async def _download_wordai_file(self, r2_key: str, local_path: str) -> bool:
        """Download from WordAI R2 bucket"""
        try:
            if not self.wordai_r2_client:
                logger.error("❌ WordAI R2 client not initialized")
                return False

            # Download from R2
            response = self.wordai_r2_client.get_object(
                Bucket=R2_BUCKET_NAME, Key=r2_key
            )

            # Write to local file
            with open(local_path, "wb") as f:
                f.write(response["Body"].read())

            file_size = os.path.getsize(local_path)
            logger.info(
                f"✅ Downloaded WordAI file: {r2_key} → {local_path} "
                f"({file_size:,} bytes)"
            )
            return True

        except Exception as e:
            logger.error(f"❌ WordAI download error: {e}")
            return False

    async def _download_aivungtau_file(self, r2_key: str, local_path: str) -> bool:
        """Download from AIVungtau R2 bucket"""
        try:
            if not self.aivungtau_r2.s3_client:
                logger.error("❌ AIVungtau R2 client not initialized")
                return False

            # Download from R2
            response = self.aivungtau_r2.s3_client.get_object(
                Bucket=self.aivungtau_r2.bucket_name, Key=r2_key
            )

            # Write to local file
            with open(local_path, "wb") as f:
                f.write(response["Body"].read())

            file_size = os.path.getsize(local_path)
            logger.info(
                f"✅ Downloaded AIVungtau file: {r2_key} → {local_path} "
                f"({file_size:,} bytes)"
            )
            return True

        except Exception as e:
            logger.error(f"❌ AIVungtau download error: {e}")
            return False

    async def download_from_url(
        self, url: str, local_path: str, timeout: int = 60
    ) -> bool:
        """
        Download file from public URL

        Fallback method if R2 credentials not available

        Args:
            url: Public file URL
            local_path: Local path to save
            timeout: Request timeout in seconds

        Returns:
            True if downloaded successfully
        """
        try:
            logger.info(f"⬇️ Downloading from URL: {url}")

            # Ensure parent directory exists
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Write to file
                with open(local_path, "wb") as f:
                    f.write(response.content)

            file_size = os.path.getsize(local_path)
            logger.info(f"✅ Downloaded from URL: {local_path} ({file_size:,} bytes)")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error downloading file: {e.response.status_code}")
            return False
        except httpx.TimeoutException:
            logger.error(f"❌ Timeout downloading file from {url}")
            return False
        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            return False

    def get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename"""
        return Path(filename).suffix.lower()

    def detect_bucket_type(self, r2_key: str, file_url: Optional[str] = None) -> str:
        """
        Detect which R2 bucket the file belongs to

        Args:
            r2_key: R2 object key
            file_url: File URL (optional)

        Returns:
            "wordai" or "aivungtau"
        """
        try:
            # Check by URL
            if file_url:
                if "aivungtau" in file_url.lower():
                    return "aivungtau"
                elif "wordai" in file_url.lower():
                    return "wordai"

            # Check by key pattern
            if r2_key.startswith("quotes/") or r2_key.startswith("aivungtau/"):
                return "aivungtau"

            # Default to wordai
            return "wordai"

        except Exception as e:
            logger.error(f"❌ Error detecting bucket type: {e}")
            return "wordai"


# Global downloader instance
r2_downloader = R2FileDownloader()


# Utility functions
async def download_r2_file(
    r2_key: str, local_path: str, file_url: Optional[str] = None
) -> bool:
    """
    Download file from R2

    Auto-detects bucket type and downloads file
    """
    bucket_type = r2_downloader.detect_bucket_type(r2_key, file_url)
    return await r2_downloader.download_from_r2(r2_key, local_path, bucket_type)


async def download_from_url(url: str, local_path: str) -> bool:
    """Download file from URL"""
    return await r2_downloader.download_from_url(url, local_path)
