"""
Social Image Service
Handles image generation for social marketing plan posts using GeminiImageService.
Downloads brand assets from R2, builds prompt, generates and uploads images.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Dict, Any, List, Optional

import boto3
from botocore.client import Config

from src.services.gemini_image_service import GeminiImageService, GEMINI_MODEL
from src.models.image_generation_models import ImageGenerationMetadata

logger = logging.getLogger(__name__)

# Map content pillar → number of reference images to use
PILLAR_ASSET_STRATEGY = {
    "promotional": ["logo", "product", "lifestyle"],
    "educational": ["logo", "lifestyle"],
    "engagement": ["logo", "lifestyle"],
    "entertaining": ["logo"],
}


class SocialImageService:
    """
    Generates images for social plan posts with brand consistency.
    Uses GeminiImageService with brand asset reference images.
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini = GeminiImageService(
            api_key=gemini_api_key or os.getenv("GEMINI_API_KEY")
        )

        self.r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
        self.r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.r2_endpoint = os.getenv("R2_ENDPOINT")
        self.r2_bucket = os.getenv("R2_BUCKET_NAME", "wordai")
        self.r2_public_url = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.r2_endpoint,
            aws_access_key_id=self.r2_access_key,
            aws_secret_access_key=self.r2_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    async def _download_image_from_r2(self, r2_key: str):
        """Download image from R2 and return as PIL Image."""
        try:
            from PIL import Image as PILImage

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.s3_client.get_object(Bucket=self.r2_bucket, Key=r2_key),
            )
            image_bytes = response["Body"].read()
            return PILImage.open(BytesIO(image_bytes))
        except Exception as e:
            logger.warning(f"Failed to download asset from R2 ({r2_key}): {e}")
            return None

    async def _load_brand_assets(
        self,
        assets: List[Dict[str, Any]],
        content_pillar: str,
        product_ref: Optional[str],
    ):
        """
        Load brand reference images from R2 based on content pillar strategy.
        Returns list of PIL images (max 3).
        """
        strategy = PILLAR_ASSET_STRATEGY.get(content_pillar, ["logo", "lifestyle"])
        reference_images = []

        # Categorize assets
        logo_assets = [a for a in assets if a.get("type") == "logo"]
        lifestyle_assets = [a for a in assets if a.get("type") == "lifestyle"]
        product_assets = [
            a
            for a in assets
            if a.get("type") == "product"
            and (
                not product_ref
                or product_ref.lower() in (a.get("product_name", "") or "").lower()
            )
        ]

        asset_map = {
            "logo": logo_assets[0] if logo_assets else None,
            "lifestyle": lifestyle_assets[0] if lifestyle_assets else None,
            "product": product_assets[0] if product_assets else None,
        }

        for asset_type in strategy:
            asset = asset_map.get(asset_type)
            if not asset:
                continue
            r2_key = asset.get("r2_key")
            if not r2_key:
                continue

            pil_img = await self._download_image_from_r2(r2_key)
            if pil_img:
                reference_images.append(pil_img)

            if len(reference_images) >= 3:
                break

        logger.info(
            f"📎 Loaded {len(reference_images)} reference images for pillar '{content_pillar}'"
        )
        return reference_images

    def _build_image_prompt(
        self,
        post: Dict[str, Any],
        brand_dna: Dict[str, Any],
        assets: List[Dict[str, Any]],
        image_style: str = "flat-design",
    ) -> str:
        """Build full image prompt from post image_prompt + brand DNA."""
        colors = brand_dna.get("colors", {})
        primary_color = colors.get("primary", "#000000")
        secondary_color = colors.get("secondary", "#ffffff")
        base_prompt = post.get(
            "image_prompt", f"TikTok post about: {post.get('topic', '')}"
        )
        pillar = post.get("content_pillar", "educational")

        system_context = (
            f"Visual style: {image_style}. "
            f"Brand primary color: {primary_color}. "
            f"Brand secondary color: {secondary_color}. "
            f"Aspect ratio: 9:16 (TikTok vertical format). "
            f"High quality, professional, vibrant colors. "
        )

        logo_assets = [a for a in assets if a.get("type") == "logo"]
        logo_instruction = ""
        if logo_assets:
            logo_instruction = (
                "The first reference image is the brand logo. Place it at bottom-right corner, "
                "small (max 15% of width), with white or transparent background. Do NOT distort the logo. "
            )

        product_instruction = ""
        if pillar == "promotional" and post.get("product_ref"):
            product_instruction = (
                f"Feature the product '{post['product_ref']}' as the hero of the composition. "
                "Show it clearly in an attractive, natural context matching the brand aesthetic. "
            )

        pillar_hints = {
            "educational": "Bold text overlay zones, clear visual hierarchy, numbered steps, informative infographic style. ",
            "promotional": "Product hero shot, clean composition, attractive lifestyle context. ",
            "engagement": "Relatable scene, warm inviting tones, question-style text overlay area. ",
            "entertaining": "Fun bold colors, expressive, eye-catching, meme-ready composition. ",
        }
        pillar_hint = pillar_hints.get(pillar, "")

        return f"{system_context}{logo_instruction}{product_instruction}{pillar_hint}{base_prompt}"

    async def generate_post_image(
        self,
        plan_id: str,
        post_id: str,
        post: Dict[str, Any],
        brand_dna: Dict[str, Any],
        assets: List[Dict[str, Any]],
        image_style: str,
        user_id: str,
        db,
    ) -> Dict[str, Any]:
        """
        Generate image for a single post and save to R2 + MongoDB + user library.

        Returns:
            Dict with image_url, r2_key, library_id
        """
        pillar = post.get("content_pillar", "educational")
        product_ref = post.get("product_ref")

        # Load brand reference images
        reference_images = await self._load_brand_assets(assets, pillar, product_ref)

        # Build prompt
        full_prompt = self._build_image_prompt(post, brand_dna, assets, image_style)
        logger.info(f"🎨 Generating image for post {post_id} (pillar={pillar})")

        # Generate image via Gemini
        gen_result = await self.gemini.generate_image(
            prompt=full_prompt,
            generation_type="general",
            user_options={
                "has_reference_images": len(reference_images) > 0,
                "reference_mode": "object",
            },
            aspect_ratio="9:16",
            reference_images=reference_images if reference_images else None,
        )

        image_bytes = gen_result["image_bytes"]
        image_size = len(image_bytes)

        # Upload to R2 with social-plan-images path
        r2_key = f"social-plan-images/{plan_id}/{post_id}.png"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.s3_client.put_object(
                Bucket=self.r2_bucket,
                Key=r2_key,
                Body=image_bytes,
                ContentType="image/png",
            ),
        )
        image_url = f"{self.r2_public_url}/{r2_key}"
        logger.info(f"☁️  Uploaded to R2: {image_url}")

        # Save to user's Image Library (library_files collection)
        library_id = f"lib_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        filename = f"social-plan-{plan_id[:8]}-{post_id[:8]}.png"
        topic = post.get("topic", "")

        library_doc = {
            "file_id": library_id,
            "library_id": library_id,
            "user_id": user_id,
            "filename": filename,
            "original_name": filename,
            "file_type": "image/png",
            "file_size": image_size,
            "folder_id": None,
            "r2_key": r2_key,
            "file_url": image_url,
            "category": "images",
            "description": f"Social plan image: {topic[:150]}",
            "tags": ["ai-generated", "social-plan", GEMINI_MODEL],
            "metadata": {
                "plan_id": plan_id,
                "post_id": post_id,
                "content_pillar": pillar,
                "generation_type": "social_plan",
                "model_version": GEMINI_MODEL,
                "source": "social-plan-worker",
            },
            "is_deleted": False,
            "deleted_at": None,
            "uploaded_at": now,
            "updated_at": now,
        }
        db["library_files"].insert_one(library_doc)
        logger.info(f"📚 Image saved to user library: {library_id}")

        return {
            "image_url": image_url,
            "r2_key": r2_key,
            "library_id": library_id,
            "image_size": image_size,
            "generation_time_ms": gen_result.get("generation_time_ms", 0),
        }
