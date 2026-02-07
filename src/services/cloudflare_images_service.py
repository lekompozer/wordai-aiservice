"""
Cloudflare Images Service - Auto-optimized image hosting
$5/month for 100,000 images with variants, transforms, auto-optimization

Features:
- Auto-optimization (WebP, AVIF, size reduction)
- On-demand variants (thumbnails, responsive)
- Transform URL parameters (width, height, quality, format)
- CDN delivery via imagedelivery.net
- No storage limits (pay per image count)

Docs: https://developers.cloudflare.com/images/
"""

import os
import httpx
import logging
from typing import Dict, Any, Optional
from io import BytesIO

logger = logging.getLogger("chatbot")


class CloudflareImagesService:
    """Service for uploading and managing images via Cloudflare Images API"""

    def __init__(self):
        """Initialize Cloudflare Images service with credentials from environment"""
        self.account_id = os.getenv("CLOUDFLARE_IMAGES_ACCOUNT_ID")
        self.api_token = os.getenv("CLOUDFLARE_IMAGES_API_TOKEN")
        self.account_hash = os.getenv("CLOUDFLARE_IMAGES_ACCOUNT_HASH")
        self.delivery_url = os.getenv(
            "CLOUDFLARE_IMAGES_DELIVERY_URL",
            f"https://imagedelivery.net/{self.account_hash}",
        )
        self.enabled = os.getenv("CLOUDFLARE_IMAGES_ENABLED", "false").lower() == "true"

        # Check if credentials are configured
        if not self.enabled:
            logger.warning(
                "⚠️ Cloudflare Images is disabled (CLOUDFLARE_IMAGES_ENABLED=false)"
            )
            return

        missing_vars = []
        if not self.account_id:
            missing_vars.append("CLOUDFLARE_IMAGES_ACCOUNT_ID")
        if not self.api_token:
            missing_vars.append("CLOUDFLARE_IMAGES_API_TOKEN")
        if not self.account_hash:
            missing_vars.append("CLOUDFLARE_IMAGES_ACCOUNT_HASH")

        if missing_vars:
            error_msg = f"Missing Cloudflare Images env vars: {', '.join(missing_vars)}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        # API base URL (Cloudflare Images Upload API)
        # Docs: https://developers.cloudflare.com/images/upload-images/upload-via-url/
        self.api_base_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/images/v1"
        )

        logger.info(
            f"✅ CloudflareImagesService initialized (Account: {self.account_id})"
        )
        logger.info(f"   Delivery URL: {self.delivery_url}")

    async def upload_image(
        self,
        image_bytes: bytes,
        image_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        require_signed_urls: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload image to Cloudflare Images

        Args:
            image_bytes: Image binary content
            image_id: Custom image ID (optional, auto-generated if not provided)
            metadata: Custom metadata dict (optional, max 10 key-value pairs)
            require_signed_urls: If True, image requires signed URLs to access

        Returns:
            {
                "id": "image_id",
                "filename": "original_filename",
                "uploaded": "2026-02-07T12:00:00.000Z",
                "requireSignedURLs": False,
                "variants": [
                    "https://imagedelivery.net/hash/id/public",
                    "https://imagedelivery.net/hash/id/thumbnail"
                ],
                "public_url": "https://imagedelivery.net/hash/id/public"
            }

        Raises:
            Exception: If upload fails
        """
        if not self.enabled:
            raise ValueError("Cloudflare Images is not enabled")

        try:
            # Prepare multipart form data
            files = {"file": ("image.webp", BytesIO(image_bytes), "image/webp")}

            data = {}
            if image_id:
                data["id"] = image_id
            if metadata:
                # Metadata must be a valid JSON string
                import json

                data["metadata"] = json.dumps(metadata)
            if require_signed_urls:
                data["requireSignedURLs"] = "true"

            # Upload via API
            headers = {"Authorization": f"Bearer {self.api_token}"}

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_base_url, headers=headers, files=files, data=data
                )

                if response.status_code != 200:
                    error_detail = response.json() if response.text else "Unknown error"
                    raise Exception(
                        f"Cloudflare Images upload failed: {response.status_code} - {error_detail}"
                    )

                result = response.json()

                if not result.get("success"):
                    errors = result.get("errors", [])
                    raise Exception(f"Upload failed: {errors}")

                # Extract image data
                image_data = result["result"]
                image_id = image_data["id"]

                # Build public URL (using 'public' variant by default)
                public_url = f"{self.delivery_url}/{image_id}/public"

                logger.info(f"✅ Uploaded to Cloudflare Images: {image_id}")
                logger.info(f"   URL: {public_url}")

                return {
                    "id": image_id,
                    "filename": image_data.get("filename", ""),
                    "uploaded": image_data.get("uploaded", ""),
                    "requireSignedURLs": image_data.get("requireSignedURLs", False),
                    "variants": image_data.get("variants", []),
                    "public_url": public_url,
                }

        except Exception as e:
            logger.error(f"❌ Failed to upload to Cloudflare Images: {e}")
            raise

    async def delete_image(self, image_id: str) -> bool:
        """
        Delete image from Cloudflare Images

        Args:
            image_id: Image ID to delete

        Returns:
            True if successful

        Raises:
            Exception: If deletion fails
        """
        if not self.enabled:
            raise ValueError("Cloudflare Images is not enabled")

        try:
            headers = {"Authorization": f"Bearer {self.api_token}"}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.api_base_url}/{image_id}", headers=headers
                )

                if response.status_code != 200:
                    error_detail = response.json() if response.text else "Unknown error"
                    raise Exception(
                        f"Delete failed: {response.status_code} - {error_detail}"
                    )

                result = response.json()

                if not result.get("success"):
                    errors = result.get("errors", [])
                    raise Exception(f"Delete failed: {errors}")

                logger.info(f"✅ Deleted image from Cloudflare Images: {image_id}")
                return True

        except Exception as e:
            logger.error(f"❌ Failed to delete from Cloudflare Images: {e}")
            raise

    def get_image_url(
        self,
        image_id: str,
        variant: str = "public",
        width: Optional[int] = None,
        height: Optional[int] = None,
        quality: Optional[int] = None,
        format: Optional[str] = None,
    ) -> str:
        """
        Get image URL with optional transforms

        Args:
            image_id: Image ID
            variant: Variant name (default: "public" for original)
            width: Resize width (optional)
            height: Resize height (optional)
            quality: Quality 1-100 (optional)
            format: Output format: auto, webp, avif, json (optional)

        Returns:
            Image URL with transforms

        Examples:
            # Original
            get_image_url("abc123", "public")
            # → https://imagedelivery.net/hash/abc123/public

            # Thumbnail variant
            get_image_url("abc123", "thumbnail")
            # → https://imagedelivery.net/hash/abc123/thumbnail

            # Custom width
            get_image_url("abc123", "public", width=800)
            # → https://imagedelivery.net/hash/abc123/w=800

            # Custom size + quality
            get_image_url("abc123", "public", width=1200, quality=85)
            # → https://imagedelivery.net/hash/abc123/w=1200,q=85
        """
        # Base URL
        url = f"{self.delivery_url}/{image_id}/{variant}"

        # Add transforms if specified
        transforms = []
        if width:
            transforms.append(f"w={width}")
        if height:
            transforms.append(f"h={height}")
        if quality:
            transforms.append(f"q={quality}")
        if format:
            transforms.append(f"f={format}")

        if transforms:
            # Replace variant with transform parameters
            url = f"{self.delivery_url}/{image_id}/{','.join(transforms)}"

        return url


# Singleton instance
_cloudflare_images_service: Optional[CloudflareImagesService] = None


def get_cloudflare_images_service() -> CloudflareImagesService:
    """Get singleton instance of CloudflareImagesService"""
    global _cloudflare_images_service
    if _cloudflare_images_service is None:
        _cloudflare_images_service = CloudflareImagesService()
    return _cloudflare_images_service
