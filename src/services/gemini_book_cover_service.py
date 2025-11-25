"""
Gemini 3 Pro Image Service for Book Cover Generation
Uses gemini-3-pro-image-preview model
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import base64
from io import BytesIO
import uuid

try:
    from google import genai
    from google.genai import types
    from PIL import Image
    import boto3
    from botocore.client import Config

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class GeminiBookCoverService:
    """Service for generating book covers using Gemini 3 Pro Image"""

    # Aspect ratio for book covers (portrait orientation)
    BOOK_ASPECT_RATIO = "3:4"  # Standard book cover ratio (e.g., 6x8 inches)

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini Book Cover Service

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

        logger.info("✅ Gemini Book Cover Service initialized")

    def _build_cover_prompt(
        self, title: str, author: str, description: str, style: Optional[str] = None
    ) -> str:
        """
        Build optimized prompt for book cover generation

        Args:
            title: Book title
            author: Author name
            description: Cover design description
            style: Optional style modifier

        Returns:
            Complete prompt for Gemini
        """
        # Base prompt structure for book cover
        prompt_parts = [
            f"Create a professional book cover design with the following specifications:",
            f"",
            f'TITLE: "{title}"',
            f'AUTHOR: "{author}"',
            f"",
            f"DESIGN REQUIREMENTS:",
            f'- The title "{title}" must be clearly visible and legible in large, bold typography',
            f'- The author name "{author}" must be prominently displayed',
            f"- {description}",
        ]

        if style:
            prompt_parts.append(f"- Artistic style: {style}")

        prompt_parts.extend(
            [
                f"",
                f"TECHNICAL REQUIREMENTS:",
                f"- Professional book cover layout (portrait orientation 3:4 ratio)",
                f"- High-quality, print-ready design",
                f"- Balanced composition with clear hierarchy",
                f"- Ensure text (title and author) is legible and well-integrated into the design",
                f"- The cover should be visually striking and market-ready",
            ]
        )

        return "\n".join(prompt_parts)

    async def generate_book_cover(
        self,
        title: str,
        author: str,
        description: str,
        style: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate book cover using Gemini 3 Pro Image

        Args:
            title: Book title to display on cover
            author: Author name to display on cover
            description: Design description (visual elements, theme, colors, etc.)
            style: Optional style modifier

        Returns:
            Dict with:
                - image_base64: Base64 encoded PNG image
                - prompt_used: Full prompt sent to Gemini
                - title: Book title
                - author: Author name
                - style: Style used
                - model: "gemini-3-pro-image-preview"
                - aspect_ratio: "3:4"
                - timestamp: ISO 8601 timestamp

        Raises:
            ValueError: If API error
        """
        try:
            # Build prompt
            full_prompt = self._build_cover_prompt(title, author, description, style)

            logger.info(f"🎨 Generating book cover with Gemini 3 Pro Image")
            logger.info(f"   Title: {title}")
            logger.info(f"   Author: {author}")
            logger.info(f"   Aspect Ratio: {self.BOOK_ASPECT_RATIO}")

            # Generate image using Gemini
            # Note: image_size/resolution is not supported in google-genai 1.47.0 ImageConfig
            # Only aspect_ratio is supported.
            response = self.client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=self.BOOK_ASPECT_RATIO,
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
                    # Note: image is a google.genai.types.Image object, not PIL.Image
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
                "author": author,
                "style": style,
                "model": "gemini-3-pro-image-preview",
                "aspect_ratio": self.BOOK_ASPECT_RATIO,
                "timestamp": datetime.utcnow().isoformat(),
                "gemini_response_text": text_response,
            }

        except Exception as e:
            logger.error(f"❌ Gemini book cover generation failed: {e}", exc_info=True)
            raise ValueError(f"Book cover generation failed: {str(e)}")

    async def upload_to_r2(
        self, image_bytes: bytes, user_id: str, filename: str
    ) -> Dict[str, str]:
        """
        Upload generated book cover to R2 storage

        Args:
            image_bytes: Image data as bytes
            user_id: Firebase user ID
            filename: Filename for the image

        Returns:
            Dict with r2_key and file_url
        """
        try:
            # Generate R2 key for book covers
            unique_id = uuid.uuid4().hex[:12]
            r2_key = f"ai-generated-images/{user_id}/{unique_id}_{filename}"

            logger.info(f"☁️  Uploading book cover to R2: {r2_key}")

            # Upload to R2
            self.s3_client.put_object(
                Bucket=self.r2_bucket,
                Key=r2_key,
                Body=image_bytes,
                ContentType="image/png",
            )

            # Generate public URL
            file_url = f"{self.r2_public_url}/{r2_key}"

            logger.info(f"✅ Book cover uploaded to R2: {file_url}")

            return {"r2_key": r2_key, "file_url": file_url}

        except Exception as e:
            logger.error(f"❌ Failed to upload book cover to R2: {e}")
            raise Exception(f"R2 upload failed: {str(e)}")

    async def save_to_library(
        self,
        user_id: str,
        filename: str,
        file_size: int,
        r2_key: str,
        file_url: str,
        title: str,
        author: str,
        description: str,
        style: Optional[str],
        prompt_used: str,
        db,
    ) -> Dict[str, Any]:
        """
        Save generated book cover metadata to library_files collection

        Args:
            user_id: Firebase user ID
            filename: Image filename
            file_size: File size in bytes
            r2_key: R2 storage key
            file_url: Public URL
            title: Book title
            author: Author name
            description: Cover description
            style: Style used
            prompt_used: Full prompt sent to Gemini
            db: MongoDB database instance

        Returns:
            Library file document
        """
        try:
            from datetime import timezone

            library_id = f"lib_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)

            # Build metadata for book cover
            metadata = {
                "source": "gemini-3-pro-image-preview",
                "generation_type": "book_cover",
                "model_version": "gemini-3-pro-image-preview",
                "prompt": prompt_used,
                "aspect_ratio": self.BOOK_ASPECT_RATIO,
                "book_title": title,
                "book_author": author,
                "cover_description": description,
                "style": style,
            }

            library_doc = {
                "file_id": library_id,
                "library_id": library_id,
                "user_id": user_id,
                "filename": filename,
                "original_name": filename,
                "file_type": "image/png",
                "file_size": file_size,
                "folder_id": None,
                "r2_key": r2_key,
                "file_url": file_url,
                "category": "images",
                "description": f"Book cover for '{title}' by {author}",
                "tags": ["ai-generated", "book-cover", title, author],
                "metadata": metadata,
                "is_deleted": False,
                "deleted_at": None,
                "uploaded_at": now,
                "updated_at": now,
            }

            result = db["library_files"].insert_one(library_doc)

            if result.inserted_id:
                logger.info(f"📚 Book cover saved to library: {library_id}")
                return library_doc
            else:
                raise Exception("Failed to insert into library_files")

        except Exception as e:
            logger.error(f"❌ Failed to save book cover to library: {e}")
            raise Exception(f"Library save failed: {str(e)}")


# Singleton instance
_gemini_book_cover_service = None


def get_gemini_book_cover_service() -> GeminiBookCoverService:
    """Get or create GeminiBookCoverService singleton"""
    global _gemini_book_cover_service
    if _gemini_book_cover_service is None:
        _gemini_book_cover_service = GeminiBookCoverService()
    return _gemini_book_cover_service
