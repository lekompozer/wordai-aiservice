"""
Gemini Image Generation Service
Uses Gemini 2.5 Flash Image API for text-to-image and image+text workflows
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import base64
from io import BytesIO
import time
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

from src.models.image_generation_models import ImageGenerationMetadata

logger = logging.getLogger(__name__)

# Model name constant
GEMINI_MODEL = "gemini-3-pro-image-preview"


class GeminiImageService:
    """Service for generating images using Gemini 3 Pro Image"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini Image Service

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
        self.r2_bucket = os.getenv("R2_BUCKET_NAME", "wordai-documents")
        self.r2_public_url = os.getenv("R2_PUBLIC_URL", "https://cdn.wordai.vn")

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

        logger.info("✅ Gemini Image Service initialized")

    def _build_prompt(
        self,
        base_prompt: str,
        generation_type: str,
        user_options: Dict[str, Any],
    ) -> str:
        """
        Build optimized prompt for Gemini based on generation type

        Args:
            base_prompt: User's text prompt
            generation_type: photorealistic, stylized, logo, etc.
            user_options: Additional options (lighting, style, etc.)

        Returns:
            Enhanced prompt for Gemini
        """
        prompt_parts = [base_prompt]

        if generation_type == "photorealistic":
            prompt_parts.append(
                "Render in photorealistic style with 8k quality, highly detailed, professional photography."
            )
            if user_options.get("lighting"):
                prompt_parts.append(f"Lighting: {user_options['lighting']}.")
            if user_options.get("camera_angle"):
                prompt_parts.append(f"Camera angle: {user_options['camera_angle']}.")
            if user_options.get("negative_prompt"):
                prompt_parts.append(f"Avoid: {user_options['negative_prompt']}.")

        elif generation_type == "stylized":
            style = user_options.get("style_preset", "Anime")
            prompt_parts.append(f"Artistic style: {style}.")
            if user_options.get("sticker_mode"):
                prompt_parts.append(
                    "Die-cut sticker style with white background, clean outlines, vector art."
                )

        elif generation_type == "logo":
            brand_name = user_options.get("brand_name", "")
            prompt_parts.append(
                f'Create a logo for "{brand_name}". The text "{brand_name}" must be clearly visible and legible.'
            )
            if user_options.get("style"):
                prompt_parts.append(f"Logo style: {user_options['style']}.")
            if user_options.get("color_palette"):
                prompt_parts.append(f"Color palette: {user_options['color_palette']}.")

        elif generation_type == "background":
            if user_options.get("minimalist_mode"):
                position = user_options.get("negative_space_position", "Center")
                prompt_parts.append(
                    f"Minimalist composition with significant negative space on the {position} for text overlay."
                )
            if user_options.get("color_mood"):
                prompt_parts.append(f"Color mood: {user_options['color_mood']}.")

        elif generation_type == "mockup":
            prompt_parts.append(
                "Professional product photography with studio lighting and commercial quality."
            )

        elif generation_type == "sequential":
            style = user_options.get("style", "Comic Book")
            panel_count = user_options.get("panel_count", 1)
            prompt_parts.append(f"{panel_count}-panel comic strip in {style} style.")

        return " ".join(prompt_parts)

    async def generate_image(
        self,
        prompt: str,
        generation_type: str,
        user_options: Dict[str, Any],
        aspect_ratio: str = "16:9",
        reference_images: Optional[List[Image.Image]] = None,
    ) -> Dict[str, Any]:
        """
        Generate image using Gemini 3 Pro Image

        Args:
            prompt: User's text prompt
            generation_type: Type of generation (photorealistic, stylized, etc.)
            user_options: Additional user options
            aspect_ratio: Image aspect ratio
            reference_images: Optional list of PIL Images for reference

        Returns:
            Dict with image data and metadata
        """
        start_time = time.time()

        try:
            # Build enhanced prompt
            full_prompt = self._build_prompt(prompt, generation_type, user_options)

            # Prepare contents for API call
            contents = [full_prompt]
            if reference_images:
                contents.extend(reference_images)

            logger.info(f"🎨 Generating {generation_type} image with Gemini...")
            logger.info(f"   Prompt: {full_prompt[:100]}...")
            logger.info(f"   Aspect ratio: {aspect_ratio}")

            # Call Gemini API (same pattern as book_cover_service)
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                    ),
                ),
            )

            # Extract image from response (same pattern as book_cover_service)
            image_bytes = None
            text_response = None

            for part in response.parts:
                if part.text is not None:
                    text_response = part.text
                    logger.info(f"📝 Gemini response text: {text_response[:100]}...")
                elif image := part.as_image():
                    # Get bytes directly from Gemini Image object
                    image_bytes = image.image_bytes
                    logger.info(f"✅ Image generated ({len(image_bytes)} bytes)")
                    break

            if not image_bytes:
                raise Exception("No image returned from Gemini API")

            generation_time_ms = int((time.time() - start_time) * 1000)

            logger.info(f"✅ Image generated in {generation_time_ms}ms")

            return {
                "success": True,
                "image_bytes": image_bytes,
                "image_size": len(image_bytes),
                "format": "PNG",
                "prompt_used": full_prompt,
                "generation_time_ms": generation_time_ms,
                "reference_images_count": (
                    len(reference_images) if reference_images else 0
                ),
                "gemini_response_text": text_response,
            }

        except Exception as e:
            logger.error(f"❌ Failed to generate image: {e}")
            raise Exception(f"Image generation failed: {str(e)}")

    async def upload_to_r2(
        self, image_bytes: bytes, user_id: str, filename: str
    ) -> Dict[str, str]:
        """
        Upload generated image to R2 storage

        Args:
            image_bytes: Image data as bytes
            user_id: Firebase user ID
            filename: Filename for the image

        Returns:
            Dict with r2_key and file_url
        """
        try:
            # Generate R2 key
            unique_id = uuid.uuid4().hex[:12]
            r2_key = f"ai-generated-images/{user_id}/{unique_id}_{filename}"

            logger.info(f"☁️  Uploading to R2: {r2_key}")

            # Upload to R2
            self.s3_client.put_object(
                Bucket=self.r2_bucket,
                Key=r2_key,
                Body=image_bytes,
                ContentType="image/png",
            )

            # Generate public URL
            file_url = f"{self.r2_public_url}/{r2_key}"

            logger.info(f"✅ Uploaded to R2: {file_url}")

            return {"r2_key": r2_key, "file_url": file_url}

        except Exception as e:
            logger.error(f"❌ Failed to upload to R2: {e}")
            raise Exception(f"R2 upload failed: {str(e)}")

    async def save_to_library(
        self,
        user_id: str,
        filename: str,
        file_size: int,
        r2_key: str,
        file_url: str,
        generation_metadata: ImageGenerationMetadata,
        db,
    ) -> Dict[str, Any]:
        """
        Save generated image metadata to library_files collection

        Args:
            user_id: Firebase user ID
            filename: Image filename
            file_size: File size in bytes
            r2_key: R2 storage key
            file_url: Public URL
            generation_metadata: Metadata about generation
            db: MongoDB database instance

        Returns:
            Library file document
        """
        try:
            from datetime import timezone

            library_id = f"lib_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)

            # Update metadata model version to match actual model used
            generation_metadata.model_version = GEMINI_MODEL
            generation_metadata.source = GEMINI_MODEL

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
                "description": generation_metadata.prompt[
                    :200
                ],  # Truncate to 200 chars
                "tags": ["ai-generated", generation_metadata.generation_type],
                "metadata": generation_metadata.dict(),
                "is_deleted": False,
                "deleted_at": None,
                "uploaded_at": now,
                "updated_at": now,
            }

            result = db["library_files"].insert_one(library_doc)

            if result.inserted_id:
                logger.info(f"📚 Saved to library: {library_id}")
                return library_doc
            else:
                raise Exception("Failed to insert into library_files")

        except Exception as e:
            logger.error(f"❌ Failed to save to library: {e}")
            raise Exception(f"Library save failed: {str(e)}")


# Singleton instance
_gemini_image_service = None


def get_gemini_image_service() -> GeminiImageService:
    """Get or create GeminiImageService singleton"""
    global _gemini_image_service
    if _gemini_image_service is None:
        _gemini_image_service = GeminiImageService()
    return _gemini_image_service
