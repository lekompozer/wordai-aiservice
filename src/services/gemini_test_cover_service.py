"""
Gemini 3 Pro Image Service for Online Test Cover Generation
Uses gemini-3.1-flash-image-preview model with 16:9 aspect ratio
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import base64
import uuid

try:
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
    import boto3
    from botocore.client import Config

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger("chatbot")


class GeminiTestCoverService:
    """Service for generating online test covers using Gemini 3 Pro Image"""

    # Aspect ratio for test covers (landscape orientation)
    TEST_ASPECT_RATIO = "16:9"  # Wide format for online tests

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini Test Cover Service

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)

        Raises:
            ImportError: If google-genai package not installed
            ValueError: If API key not provided
        """
        if not GENAI_AVAILABLE:
            raise ImportError(
                "google-genai package not installed. Run: pip install google-genai"
            )

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not found in environment variables. "
                "Please set GEMINI_API_KEY in your .env file."
            )

        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)

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

        logger.info("✅ Gemini Test Cover Service initialized")

    def _build_cover_prompt(
        self, title: str, description: str, style: Optional[str] = None
    ) -> str:
        """
        Build optimized prompt for test cover generation

        Args:
            title: Test title
            description: Cover design description
            style: Optional style modifier

        Returns:
            Complete prompt for Gemini
        """
        # Base prompt structure for test cover
        prompt_parts = [
            f"Create a professional online test/exam cover image with the following specifications:",
            f"",
            f'TITLE: "{title}"',
            f"",
            f"DESIGN REQUIREMENTS:",
            f'- The title "{title}" must be clearly visible and legible in large, bold typography',
            f"- {description}",
        ]

        if style:
            prompt_parts.append(f"- Artistic style: {style}")

        prompt_parts.extend(
            [
                f"",
                f"TECHNICAL REQUIREMENTS:",
                f"- Professional test/exam cover layout (landscape orientation 16:9 ratio)",
                f"- Modern, clean, and educational design",
                f"- Suitable for online learning platform",
                f"- Ensure text (title) is legible and prominent",
                f"- The cover should look professional and engaging for students",
                f"- Use educational themes (books, pencils, graduation, learning, knowledge)",
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
        Generate test cover using Gemini 3 Pro Image

        Args:
            title: Test title to display on cover
            description: Design description (visual elements, theme, colors, etc.)
            style: Optional style modifier

        Returns:
            Dict with:
                - image_base64: Base64 encoded PNG image
                - prompt_used: Full prompt sent to Gemini
                - title: Test title
                - style: Style used
                - model: "gemini-3.1-flash-image-preview"
                - aspect_ratio: "16:9"
                - timestamp: ISO 8601 timestamp

        Raises:
            ValueError: If API error
        """
        try:
            # Build prompt
            full_prompt = self._build_cover_prompt(title, description, style)

            logger.info(f"🎨 Generating test cover with Gemini 3 Pro Image")
            logger.info(f"   Title: {title}")
            logger.info(f"   Aspect Ratio: {self.TEST_ASPECT_RATIO}")

            # Generate image using Gemini
            # Run in thread pool to avoid blocking event loop
            import asyncio

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model="gemini-3.1-flash-image-preview",
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                        image_config=types.ImageConfig(
                            aspect_ratio=self.TEST_ASPECT_RATIO,
                        ),
                    ),
                ),
            )

            # Extract image from response
            image_data = None
            text_response = None

            for part in response.parts:
                if part.text is not None:
                    text_response = part.text
                    logger.info(f"📝 Gemini response text: {text_response[:100]}...")
                elif image := part.as_image():
                    # Get bytes directly from Gemini Image object
                    image_bytes = image.image_bytes
                    image_data = base64.b64encode(image_bytes).decode("utf-8")
                    logger.info(
                        f"✅ Image generated successfully ({len(image_data)} bytes)"
                    )

            if not image_data:
                raise ValueError("No image generated in response")

            return {
                "image_base64": image_data,
                "prompt_used": full_prompt,
                "title": title,
                "style": style,
                "model": "gemini-3.1-flash-image-preview",
                "aspect_ratio": self.TEST_ASPECT_RATIO,
                "timestamp": datetime.utcnow().isoformat(),
                "gemini_response_text": text_response,
            }

        except Exception as e:
            logger.error(f"❌ Gemini test cover generation failed: {e}", exc_info=True)
            raise ValueError(f"Test cover generation failed: {str(e)}")

    async def upload_to_r2(
        self, image_bytes: bytes, user_id: str, filename: str
    ) -> Dict[str, str]:
        """
        Upload generated test cover — Cloudflare Images first, R2 fallback.

        Returns dict with keys: file_url, cf_image_id (or None), r2_key (or None)
        """
        # --- Cloudflare Images (preferred) ---
        try:
            from src.services.cloudflare_images_service import (
                get_cloudflare_images_service,
            )

            cf = get_cloudflare_images_service()
            if cf.enabled:
                cf_result = await cf.upload_image(image_bytes)
                logger.info(
                    f"✅ Test cover uploaded to Cloudflare Images: {cf_result['id']}"
                )
                return {
                    "file_url": cf_result["public_url"],
                    "cf_image_id": cf_result["id"],
                    "r2_key": None,
                }
        except Exception as cf_err:
            logger.warning(f"⚠️ CF Images upload failed, falling back to R2: {cf_err}")

        # --- R2 fallback ---
        try:
            r2_key = f"test_covers/{user_id}/{filename}"

            self.s3_client.put_object(
                Bucket=self.r2_bucket,
                Key=r2_key,
                Body=image_bytes,
                ContentType="image/png",
            )

            file_url = f"{self.r2_public_url}/{r2_key}"
            logger.info(f"☁️  Uploaded test cover to R2: {r2_key}")

            return {"r2_key": r2_key, "file_url": file_url, "cf_image_id": None}

        except Exception as e:
            logger.error(f"❌ R2 upload failed: {e}", exc_info=True)
            raise ValueError(f"Failed to upload: {str(e)}")

    async def save_to_library(
        self,
        user_id: str,
        filename: str,
        file_size: int,
        r2_key: Optional[str],
        file_url: str,
        title: str,
        description: str,
        style: Optional[str],
        prompt_used: str,
        db: Any,
        cf_image_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save generated test cover metadata to library_files collection

        Args:
            user_id: User ID
            filename: Filename
            file_size: File size in bytes
            r2_key: R2 storage key
            file_url: Public URL
            title: Test title
            description: Design description
            style: Style used
            prompt_used: Full prompt
            db: MongoDB database instance

        Returns:
            Library document
        """
        try:
            file_id = f"file_{uuid.uuid4().hex[:16]}"
            now = datetime.utcnow()

            library_doc = {
                "file_id": file_id,
                "user_id": user_id,
                "filename": filename,
                "file_size": file_size,
                "mime_type": "image/png",
                "file_type": "test-cover",  # New type for test covers
                "r2_key": r2_key,
                "file_url": file_url,
                "cf_image_id": cf_image_id,
                "is_public": False,
                "created_at": now,
                "updated_at": now,
                # AI generation metadata
                "metadata": {
                    "title": title,
                    "description": description,
                    "style": style,
                    "prompt_used": prompt_used,
                    "model": "gemini-3.1-flash-image-preview",
                    "aspect_ratio": self.TEST_ASPECT_RATIO,
                    "generation_method": "ai",
                },
                "tags": ["ai-generated", "test-cover", title],
            }

            db.library_files.insert_one(library_doc)

            logger.info(f"📚 Saved test cover to library: {file_id}")

            return library_doc

        except Exception as e:
            logger.error(f"❌ Failed to save to library: {e}", exc_info=True)
            raise ValueError(f"Failed to save to library: {str(e)}")


# Singleton instance
_test_cover_service_instance = None


def get_gemini_test_cover_service() -> GeminiTestCoverService:
    """Get or create GeminiTestCoverService singleton"""
    global _test_cover_service_instance

    if _test_cover_service_instance is None:
        try:
            _test_cover_service_instance = GeminiTestCoverService()
            logger.info("✅ Created GeminiTestCoverService singleton")
        except Exception as e:
            logger.error(f"❌ Failed to create GeminiTestCoverService: {e}")
            raise

    return _test_cover_service_instance
