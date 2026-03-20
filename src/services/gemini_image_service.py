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
GEMINI_MODEL = "gemini-3.1-flash-image-preview"


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

        elif generation_type == "general":
            reference_mode = user_options.get("reference_mode", "object")

            if user_options.get("has_reference_images"):
                if reference_mode in ["face", "character"]:
                    prompt_parts.insert(
                        0,
                        "[CRITICAL INSTRUCTION: EDIT HUMAN CHARACTER & SCENE]\n"
                        "You must STRICTLY preserve the reference image. Keep the human character's face, identity, exact clothing/outfit, pose, "
                        "AND the entire surrounding environment/background EXACTLY the same as the reference. "
                        "Do NOT generate a different person, do NOT change the background or clothes unless explicitly requested. "
                        "ONLY modify or add details according to the specific user input below.\n"
                        "USER INPUT TO APPLY:",
                    )
                else:
                    prompt_parts.insert(
                        0,
                        "[CRITICAL INSTRUCTION: EDIT OBJECT/CARTOON & SCENE]\n"
                        "You must STRICTLY preserve the reference image. Keep the object, cartoon character, textures, patterns, shapes, "
                        "AND the entire surrounding environment/background EXACTLY the same as the reference. "
                        "Do NOT hallucinate a new background or redesign the main subjects unless explicitly requested. "
                        "ONLY modify or add details according to the specific user input below.\n"
                        "USER INPUT TO APPLY:",
                    )

            if user_options.get("negative_prompt"):
                prompt_parts.append(f"Avoid: {user_options['negative_prompt']}.")

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

            # Prepare contents for API call.
            # Per official Gemini docs: text prompt FIRST, then PIL Image objects directly.
            # Reference: https://ai.google.dev/gemini-api/docs/imagen
            # contents = [prompt_text, Image.open(...), Image.open(...), ...]
            # PIL Image objects are natively supported — no conversion needed.
            contents: list = [full_prompt]
            if reference_images:
                # Ensure RGBA/palette images are converted to RGB (PNG/JPEG compatible)
                for i, pil_img in enumerate(reference_images):
                    img_rgb = (
                        pil_img.convert("RGB") if pil_img.mode != "RGB" else pil_img
                    )
                    contents.append(img_rgb)
                    logger.info(
                        f"   📎 ref_image[{i}]: mode={pil_img.mode} size={pil_img.size}"
                    )

            logger.info(f"🎨 Generating {generation_type} image with Gemini...")
            logger.info(f"   Prompt (first 200 chars): {full_prompt[:200]}")
            logger.info(f"   Aspect ratio: {aspect_ratio}")
            logger.info(
                f"   Contents: 1 prompt + {len(reference_images) if reference_images else 0} reference images"
                f" = {len(contents)} parts total"
            )

            import asyncio

            loop = asyncio.get_event_loop()

            # Retry logic — face/person images can occasionally hit safety filters
            max_retries = 2
            response = None
            for attempt in range(max_retries):
                try:
                    response = await loop.run_in_executor(
                        None,
                        lambda: self.client.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                response_modalities=["TEXT", "IMAGE"],
                                image_config=types.ImageConfig(
                                    aspect_ratio=aspect_ratio,
                                ),
                                safety_settings=[
                                    types.SafetySetting(
                                        category="HARM_CATEGORY_HATE_SPEECH",
                                        threshold="BLOCK_ONLY_HIGH",
                                    ),
                                    types.SafetySetting(
                                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                                        threshold="BLOCK_ONLY_HIGH",
                                    ),
                                    types.SafetySetting(
                                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                        threshold="BLOCK_ONLY_HIGH",
                                    ),
                                    types.SafetySetting(
                                        category="HARM_CATEGORY_HARASSMENT",
                                        threshold="BLOCK_ONLY_HIGH",
                                    ),
                                ],
                            ),
                        ),
                    )
                    if response.candidates and response.candidates[0].content:
                        logger.info(f"✅ Gemini responded on attempt {attempt+1}")
                        break
                    finish_reason = (
                        response.candidates[0].finish_reason
                        if response.candidates
                        else "UNKNOWN"
                    )
                    logger.warning(
                        f"⚠️ Attempt {attempt+1} no content, finish_reason={finish_reason}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"❌ Attempt {attempt+1} exception: {e}")
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(1)

            # Guard: all retries exhausted without valid content
            if (
                response is None
                or not response.candidates
                or not response.candidates[0].content
            ):
                finish = (
                    response.candidates[0].finish_reason
                    if response and response.candidates
                    else "NO_RESPONSE"
                )
                raise Exception(
                    f"Gemini returned no image content after {max_retries} attempts. finish_reason={finish}"
                )

            # Extract image from response
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
