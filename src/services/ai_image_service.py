"""
AI Image Generation Service
Uses OpenAI gpt-image-1 model to generate book cover images
"""

import os
import base64
import logging
from typing import Optional, Dict, Any
from datetime import datetime

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI not available for image generation")

logger = logging.getLogger(__name__)


class AIImageService:
    """Service for generating images using OpenAI gpt-image-1"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize AI Image Service

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not installed. Run: pip install openai")

        # Try multiple env var names for OpenAI API key
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("CHATGPT_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY or CHATGPT_API_KEY not found in environment variables")

        self.client = OpenAI(api_key=self.api_key)

    async def generate_book_cover(
        self,
        prompt: str,
        style: Optional[str] = None,
        model: str = "gpt-4.1-mini",
    ) -> Dict[str, Any]:
        """
        Generate book cover image using OpenAI gpt-image-1

        Args:
            prompt: Text description of the book cover to generate
            style: Optional style modifier (e.g., "fantasy art", "minimalist", "photorealistic")
            model: OpenAI model to use (default: gpt-4.1-mini)

        Returns:
            Dict containing:
                - image_base64: Base64 encoded image data
                - prompt_used: The full prompt sent to API
                - timestamp: Generation timestamp
                - model: Model used

        Raises:
            Exception: If image generation fails
        """
        try:
            # Build enhanced prompt with style
            full_prompt = prompt
            if style:
                full_prompt = f"{prompt} (Style: {style})"

            logger.info(f"Generating book cover with prompt: {full_prompt[:100]}...")

            # Call OpenAI API with Responses endpoint
            response = self.client.responses.create(
                model=model,
                input=full_prompt,
                tools=[{"type": "image_generation"}],
            )

            # Extract image data from response
            image_data = [
                output.result
                for output in response.output
                if output.type == "image_generation_call"
            ]

            if not image_data:
                raise Exception("No image generated in response")

            image_base64 = image_data[0]

            logger.info(
                f"Successfully generated book cover image ({len(image_base64)} bytes)"
            )

            return {
                "image_base64": image_base64,
                "prompt_used": full_prompt,
                "timestamp": datetime.utcnow().isoformat(),
                "model": model,
                "style": style,
            }

        except Exception as e:
            logger.error(f"Failed to generate book cover: {str(e)}")
            raise Exception(f"Image generation failed: {str(e)}")

    def decode_image(self, image_base64: str) -> bytes:
        """
        Decode base64 image to bytes

        Args:
            image_base64: Base64 encoded image string

        Returns:
            bytes: Decoded image data
        """
        return base64.b64decode(image_base64)

    def save_image(self, image_base64: str, filepath: str) -> None:
        """
        Save base64 image to file

        Args:
            image_base64: Base64 encoded image string
            filepath: Path to save image
        """
        image_bytes = self.decode_image(image_base64)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        logger.info(f"Saved image to {filepath}")
