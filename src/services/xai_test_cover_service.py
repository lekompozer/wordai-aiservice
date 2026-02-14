"""
xAI Grok Imagine Image Service for Online Test Cover Generation
Uses grok-imagine-image model with 16:9 aspect ratio and 1K resolution
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import base64

try:
    import xai_sdk
    import boto3
    from botocore.client import Config

    XAI_AVAILABLE = True
except ImportError:
    XAI_AVAILABLE = False

logger = logging.getLogger("chatbot")


class XAITestCoverService:
    """Service for generating online test covers using xAI Grok Imagine Image"""

    # Configuration for test covers
    ASPECT_RATIO = "16:9"  # Wide format for online tests
    RESOLUTION = "1k"  # 1K resolution

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize xAI Test Cover Service

        Args:
            api_key: xAI API key (defaults to XAI_API_KEY env var)

        Raises:
            ImportError: If xai_sdk package not installed
            ValueError: If API key not provided
        """
        if not XAI_AVAILABLE:
            raise ImportError("xai_sdk package not installed. Run: pip install xai-sdk")

        self.api_key = api_key or os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "XAI_API_KEY not found in environment variables. "
                "Please set XAI_API_KEY in your .env file."
            )

        # Initialize xAI client
        self.client = xai_sdk.Client(api_key=self.api_key)

        # Initialize R2 client for storage
        self.r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
        self.r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.r2_endpoint = os.getenv("R2_ENDPOINT")
        self.r2_bucket = os.getenv("R2_BUCKET_NAME", "wordai")
        self.r2_public_url = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")

        if not all([self.r2_access_key, self.r2_secret_key, self.r2_endpoint]):
            raise ValueError("R2 storage credentials not configured")

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.r2_endpoint,
            aws_access_key_id=self.r2_access_key,
            aws_secret_access_key=self.r2_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

        logger.info("✅ xAI Test Cover Service initialized")

    def _build_cover_prompt(
        self, title: str, description: str, style: Optional[str] = None
    ) -> str:
        """
        Build optimized prompt for test cover generation

        Args:
            title: Test title to display on cover
            description: Cover design description
            style: Optional style modifier

        Returns:
            Complete prompt for xAI Grok Imagine
        """
        # Compact prompt structure for test cover with text overlay
        prompt_parts = [
            f"Create a professional online test cover image in landscape 16:9 format.",
            f"",
            f"The cover must include these text elements:",
            f'1. Main title (large, bold): "{title}"',
            f'2. Subtitle (smaller, below title): "Vocabulary & Grammar Test"',
            f'3. Publisher (bottom right corner): "WordAI Team"',
            f"",
            f"Design requirements:",
            f"- {description}",
        ]

        if style:
            prompt_parts.append(f"- Visual style: {style}")

        prompt_parts.extend(
            [
                f"- Modern, clean, educational design",
                f"- Professional layout for online learning platform",
                f"- All text must be clearly legible and prominent",
                f"- Use educational color scheme (blues, greens, soft tones)",
            ]
        )

        return "\n".join(prompt_parts)

    async def generate_test_cover(
        self,
        title: str,
        description: str,
        style: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate test cover using xAI Grok Imagine Image

        Args:
            title: Test title to display on cover
            description: Design description (visual elements, theme, colors, etc.)
            style: Optional style modifier

        Returns:
            Dict with:
                - image_base64: Base64 encoded image
                - prompt_used: Full prompt sent to xAI
                - title: Test title
                - style: Style used
                - model: "grok-imagine-image"
                - aspect_ratio: "16:9"
                - resolution: "1k"
                - timestamp: ISO 8601 timestamp

        Raises:
            ValueError: If API error
        """
        try:
            # Build prompt
            full_prompt = self._build_cover_prompt(title, description, style)

            logger.info(f"🎨 Generating test cover with xAI Grok Imagine")
            logger.info(f"   Title: {title}")
            logger.info(f"   Aspect Ratio: {self.ASPECT_RATIO}")
            logger.info(f"   Resolution: {self.RESOLUTION}")

            # Generate image using xAI (synchronous call, wrap in async)
            import asyncio

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.image.sample(
                    prompt=full_prompt,
                    model="grok-imagine-image",
                    aspect_ratio=self.ASPECT_RATIO,
                    resolution=self.RESOLUTION,
                    image_format="base64",  # Request base64 directly
                ),
            )

            # Response.image contains the base64-decoded bytes already
            # We need to re-encode to base64 string for consistency
            image_base64 = base64.b64encode(response.image).decode("utf-8")

            logger.info(f"✅ Image generated successfully ({len(image_base64)} chars)")

            # Check moderation
            if not response.respect_moderation:
                logger.warning("⚠️  Image flagged by moderation but proceeding")

            return {
                "image_base64": image_base64,
                "prompt_used": full_prompt,
                "title": title,
                "style": style,
                "model": response.model,
                "aspect_ratio": self.ASPECT_RATIO,
                "resolution": self.RESOLUTION,
                "timestamp": datetime.utcnow().isoformat(),
                "moderation_passed": response.respect_moderation,
            }

        except Exception as e:
            logger.error(f"❌ xAI test cover generation failed: {e}", exc_info=True)
            raise ValueError(f"Test cover generation failed: {str(e)}")

    async def upload_to_r2(
        self, image_bytes: bytes, user_id: str, filename: str
    ) -> Dict[str, str]:
        """
        Upload generated test cover to R2 storage

        Args:
            image_bytes: Image data (PNG/JPEG)
            user_id: User ID for organizing files
            filename: Original filename

        Returns:
            Dict with r2_key and file_url
        """
        try:
            # Generate R2 key for test covers
            r2_key = f"test_covers/{user_id}/{filename}"

            # Upload to R2
            self.s3_client.put_object(
                Bucket=self.r2_bucket,
                Key=r2_key,
                Body=image_bytes,
                ContentType="image/jpeg",  # xAI returns JPEG
            )

            # Build public URL
            file_url = f"{self.r2_public_url}/{r2_key}"

            logger.info(f"☁️  Uploaded test cover to R2: {r2_key}")

            return {
                "r2_key": r2_key,
                "file_url": file_url,
            }

        except Exception as e:
            logger.error(f"❌ R2 upload failed: {e}", exc_info=True)
            raise ValueError(f"Failed to upload to R2: {str(e)}")


# Singleton instance
_xai_test_cover_service: Optional[XAITestCoverService] = None


def get_xai_test_cover_service() -> XAITestCoverService:
    """Get or create XAI Test Cover Service singleton"""
    global _xai_test_cover_service
    if _xai_test_cover_service is None:
        _xai_test_cover_service = XAITestCoverService()
        logger.info("✅ Created XAITestCoverService singleton")
    return _xai_test_cover_service
