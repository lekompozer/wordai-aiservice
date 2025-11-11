"""
Test Cover Image Upload Service
Handles cover image upload, validation, and thumbnail generation for marketplace tests

Features:
- Upload cover images to R2 storage
- Validate image dimensions (min 800x600)
- Validate file size (max 5MB)
- Generate thumbnails (300x200)
- Return CDN URLs
"""

import os
import io
import logging
import uuid
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    logging.warning("Pillow not available for image processing")
    PIL_AVAILABLE = False

from src.storage.r2_client import R2Client
import config.config as config

logger = logging.getLogger(__name__)


class TestCoverImageService:
    """Service for handling test cover image uploads"""

    # Image validation constraints
    MIN_WIDTH = 800
    MIN_HEIGHT = 600
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
    ALLOWED_FORMATS = ["JPEG", "JPG", "PNG"]
    THUMBNAIL_SIZE = (300, 200)

    def __init__(self):
        """Initialize cover image service with R2 client"""
        if not PIL_AVAILABLE:
            raise ImportError(
                "Pillow required for image processing. Install: pip install Pillow"
            )

        # Initialize R2 client
        self.r2_client = R2Client(
            account_id=getattr(config, "R2_ACCOUNT_ID", ""),
            access_key_id=getattr(config, "R2_ACCESS_KEY_ID", ""),
            secret_access_key=getattr(config, "R2_SECRET_ACCESS_KEY", ""),
            bucket_name=getattr(config, "R2_BUCKET_NAME", ""),
            region="auto",
        )

        # CDN base URL (public access to R2 bucket)
        self.cdn_base_url = getattr(
            config, "R2_PUBLIC_URL", f"https://pub-{config.R2_ACCOUNT_ID}.r2.dev"
        )

        logger.info("✅ TestCoverImageService initialized")

    async def validate_image(
        self, image_bytes: bytes, filename: str
    ) -> Tuple[bool, Optional[str], Optional[Image.Image]]:
        """
        Validate uploaded image

        Args:
            image_bytes: Raw image bytes
            filename: Original filename

        Returns:
            Tuple of (is_valid, error_message, PIL_Image)
        """
        # Check file size
        if len(image_bytes) > self.MAX_FILE_SIZE:
            size_mb = len(image_bytes) / (1024 * 1024)
            return False, f"File too large: {size_mb:.2f}MB (max 5MB)", None

        try:
            # Try to open image
            image = Image.open(io.BytesIO(image_bytes))

            # Check format
            if image.format not in self.ALLOWED_FORMATS:
                return (
                    False,
                    f"Invalid format: {image.format}. Allowed: {', '.join(self.ALLOWED_FORMATS)}",
                    None,
                )

            # Check dimensions
            width, height = image.size
            if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                return (
                    False,
                    f"Image too small: {width}x{height}. Minimum: {self.MIN_WIDTH}x{self.MIN_HEIGHT}",
                    None,
                )

            logger.info(
                f"✅ Image validation passed: {filename} ({width}x{height}, {image.format})"
            )
            return True, None, image

        except Exception as e:
            logger.error(f"❌ Image validation failed: {e}")
            return False, f"Invalid image file: {str(e)}", None

    def generate_thumbnail(self, image: Image.Image) -> bytes:
        """
        Generate thumbnail from image

        Args:
            image: PIL Image object

        Returns:
            Thumbnail image bytes (JPEG)
        """
        try:
            # Create thumbnail (maintains aspect ratio)
            thumbnail = image.copy()
            thumbnail.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            # Convert to RGB if necessary (for PNG with transparency)
            if thumbnail.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", thumbnail.size, (255, 255, 255))
                if thumbnail.mode == "P":
                    thumbnail = thumbnail.convert("RGBA")
                background.paste(
                    thumbnail,
                    mask=thumbnail.split()[-1] if thumbnail.mode == "RGBA" else None,
                )
                thumbnail = background

            # Save to bytes
            thumbnail_bytes = io.BytesIO()
            thumbnail.save(thumbnail_bytes, format="JPEG", quality=85, optimize=True)
            thumbnail_bytes.seek(0)

            logger.info(f"✅ Generated thumbnail: {thumbnail.size}")
            return thumbnail_bytes.getvalue()

        except Exception as e:
            logger.error(f"❌ Thumbnail generation failed: {e}")
            raise

    def optimize_image(self, image: Image.Image, max_dimension: int = 1920) -> bytes:
        """
        Optimize image for web (resize if too large, compress)

        Args:
            image: PIL Image object
            max_dimension: Maximum width or height

        Returns:
            Optimized image bytes (JPEG)
        """
        try:
            # Resize if too large
            width, height = image.size
            if width > max_dimension or height > max_dimension:
                ratio = min(max_dimension / width, max_dimension / height)
                new_size = (int(width * ratio), int(height * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(
                    f"🔽 Resized image: {width}x{height} → {new_size[0]}x{new_size[1]}"
                )

            # Convert to RGB if necessary
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(
                    image, mask=image.split()[-1] if image.mode == "RGBA" else None
                )
                image = background

            # Compress
            optimized_bytes = io.BytesIO()
            image.save(optimized_bytes, format="JPEG", quality=90, optimize=True)
            optimized_bytes.seek(0)

            logger.info(
                f"✅ Optimized image: {len(optimized_bytes.getvalue()) / 1024:.0f}KB"
            )
            return optimized_bytes.getvalue()

        except Exception as e:
            logger.error(f"❌ Image optimization failed: {e}")
            raise

    async def upload_cover_image(
        self, image_bytes: bytes, test_id: str, version: str, filename: str
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Upload cover image and generate thumbnail

        Args:
            image_bytes: Raw image bytes
            test_id: Test MongoDB ObjectId
            version: Test version (e.g., "v1")
            filename: Original filename

        Returns:
            Tuple of (success, error_message, cover_url, thumbnail_url)
        """
        try:
            # Validate image
            is_valid, error_msg, image = await self.validate_image(
                image_bytes, filename
            )
            if not is_valid:
                return False, error_msg, None, None

            # Generate unique filenames
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            ext = "jpg"  # Always save as JPEG

            cover_filename = (
                f"test-covers/{test_id}/{version}/cover_{timestamp}_{unique_id}.{ext}"
            )
            thumbnail_filename = (
                f"test-covers/{test_id}/{version}/thumb_{timestamp}_{unique_id}.{ext}"
            )

            # Optimize main image
            optimized_bytes = self.optimize_image(image)

            # Generate thumbnail
            thumbnail_bytes = self.generate_thumbnail(image)

            # Upload to R2
            logger.info(f"📤 Uploading cover image to R2: {cover_filename}")
            cover_success = await self.r2_client.upload_file_from_bytes(
                file_bytes=optimized_bytes,
                remote_path=cover_filename,
                content_type="image/jpeg",
            )

            if not cover_success:
                return False, "Failed to upload cover image to R2", None, None

            logger.info(f"📤 Uploading thumbnail to R2: {thumbnail_filename}")
            thumbnail_success = await self.r2_client.upload_file_from_bytes(
                file_bytes=thumbnail_bytes,
                remote_path=thumbnail_filename,
                content_type="image/jpeg",
            )

            if not thumbnail_success:
                # Cover uploaded but thumbnail failed - still return success with cover only
                logger.warning(
                    f"⚠️  Thumbnail upload failed, but cover uploaded successfully"
                )

            # Generate CDN URLs
            cover_url = f"{self.cdn_base_url}/{cover_filename}"
            thumbnail_url = (
                f"{self.cdn_base_url}/{thumbnail_filename}"
                if thumbnail_success
                else cover_url
            )

            logger.info(f"✅ Cover image uploaded successfully")
            logger.info(f"   Cover URL: {cover_url}")
            logger.info(f"   Thumbnail URL: {thumbnail_url}")

            return True, None, cover_url, thumbnail_url

        except Exception as e:
            logger.error(f"❌ Cover image upload failed: {e}")
            import traceback

            traceback.print_exc()
            return False, f"Upload error: {str(e)}", None, None

    async def delete_cover_image(self, cover_url: str, thumbnail_url: str) -> bool:
        """
        Delete cover image and thumbnail from R2

        Args:
            cover_url: Cover image CDN URL
            thumbnail_url: Thumbnail CDN URL

        Returns:
            True if deletion successful
        """
        try:
            # Extract R2 paths from URLs
            cover_path = cover_url.replace(f"{self.cdn_base_url}/", "")
            thumbnail_path = thumbnail_url.replace(f"{self.cdn_base_url}/", "")

            # Delete from R2
            logger.info(f"🗑️  Deleting cover image: {cover_path}")
            await self.r2_client.delete_file(cover_path)

            if thumbnail_path != cover_path:
                logger.info(f"🗑️  Deleting thumbnail: {thumbnail_path}")
                await self.r2_client.delete_file(thumbnail_path)

            logger.info(f"✅ Cover images deleted successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Cover image deletion failed: {e}")
            return False


# Singleton instance
_cover_image_service: Optional[TestCoverImageService] = None


def get_cover_image_service() -> TestCoverImageService:
    """Get singleton instance of TestCoverImageService"""
    global _cover_image_service
    if _cover_image_service is None:
        _cover_image_service = TestCoverImageService()
    return _cover_image_service
