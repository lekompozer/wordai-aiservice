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

try:
    from google import genai
    from google.genai import types
    from PIL import Image

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class GeminiBookCoverService:
    """Service for generating book covers using Gemini 3 Pro Image"""

    # Aspect ratio for book covers (portrait orientation)
    BOOK_ASPECT_RATIO = "3:4"  # Standard book cover ratio (e.g., 6x8 inches)

    # Available resolutions
    RESOLUTION_1K = "1K"  # 896x1200 pixels
    RESOLUTION_2K = "2K"  # 1792x2400 pixels

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
        resolution: str = "1K",
    ) -> Dict[str, Any]:
        """
        Generate book cover using Gemini 3 Pro Image

        Args:
            title: Book title to display on cover
            author: Author name to display on cover
            description: Design description (visual elements, theme, colors, etc.)
            style: Optional style modifier
            resolution: "1K" (896x1200) or "2K" (1792x2400)

        Returns:
            Dict with:
                - image_base64: Base64 encoded PNG image
                - prompt_used: Full prompt sent to Gemini
                - title: Book title
                - author: Author name
                - style: Style used
                - model: "gemini-3-pro-image-preview"
                - aspect_ratio: "3:4"
                - resolution: "1K" or "2K"
                - timestamp: ISO 8601 timestamp

        Raises:
            ValueError: If invalid resolution or API error
        """
        try:
            # Validate resolution
            if resolution not in [self.RESOLUTION_1K, self.RESOLUTION_2K]:
                raise ValueError(
                    f"Invalid resolution: {resolution}. Must be '1K' or '2K'"
                )

            # Build prompt
            full_prompt = self._build_cover_prompt(title, author, description, style)

            logger.info(f"🎨 Generating book cover with Gemini 3 Pro Image")
            logger.info(f"   Title: {title}")
            logger.info(f"   Author: {author}")
            logger.info(f"   Resolution: {resolution}")
            logger.info(f"   Aspect Ratio: {self.BOOK_ASPECT_RATIO}")

            # Generate image using Gemini
            response = self.client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=self.BOOK_ASPECT_RATIO,
                        image_size=resolution,
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
                    # Convert PIL Image to base64
                    buffered = BytesIO()
                    image.save(buffered, format="PNG")
                    image_bytes = buffered.getvalue()
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
                "resolution": resolution,
                "timestamp": datetime.utcnow().isoformat(),
                "gemini_response_text": text_response,
            }

        except Exception as e:
            logger.error(f"❌ Gemini book cover generation failed: {e}", exc_info=True)
            raise ValueError(f"Book cover generation failed: {str(e)}")
