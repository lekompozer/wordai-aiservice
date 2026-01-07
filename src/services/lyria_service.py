"""
Lyria Music Generation Service
Uses Google Vertex AI Lyria-002 model for instrumental music generation
"""

import os
import logging
import base64
import asyncio
from typing import Dict, Optional, Tuple
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class LyriaService:
    """Service for Lyria music generation via Vertex AI"""

    def __init__(self):
        """Initialize Lyria service with Vertex AI credentials"""
        # Use Vertex AI with credentials file (same pattern as TTS)
        project_id = os.getenv("FIREBASE_PROJECT_ID", "wordai-6779e")
        location = "us-central1"  # Lyria available in us-central1

        # Check for credentials file
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            credentials_path = "/app/wordai-6779e-ed6189c466f1.json"
            if os.path.exists(credentials_path):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
                logger.info(f"📁 Using credentials file: {credentials_path}")

        # Initialize Gemini client with Vertex AI
        self.client = genai.Client(vertexai=True, project=project_id, location=location)
        self.model = "lyria-002"

        logger.info(
            f"✅ Lyria service initialized with Vertex AI (project={project_id}, location={location})"
        )
        logger.info(f"   Model: {self.model}")
        logger.info("   No API key limit - using Vertex AI project quota")

    async def generate_music(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        max_retries: int = 3,
    ) -> Tuple[bytes, Dict]:
        """
        Generate instrumental music from text prompt

        Args:
            prompt: Text description of music (English)
            negative_prompt: What to exclude from music (optional)
            seed: Random seed for deterministic generation (optional)
            max_retries: Max retry attempts for quota errors (default: 3)

        Returns:
            Tuple of (audio_bytes, metadata)
            - audio_bytes: MP3 audio data
            - metadata: Dict with duration, format, etc.
        """

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"🎵 Generating music with Lyria (attempt {attempt + 1}/{max_retries})"
                )
                logger.info(f"   Prompt: {prompt[:100]}...")

                # Build generation config
                config = types.GenerateContentConfig(
                    temperature=1.0,  # Default for music generation
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=1024,
                )

                # Build prompt parts
                prompt_parts = [prompt]

                if negative_prompt:
                    prompt_parts.append(f"\nNegative prompt: {negative_prompt}")
                    logger.info(f"   Negative prompt: {negative_prompt}")

                if seed is not None:
                    logger.info(f"   Seed: {seed}")
                    # Note: Lyria may not support seed via genai SDK
                    # Will use temperature=0 for more deterministic output
                    config.temperature = 0.0

                logger.info(f"   🔄 Calling Vertex AI Lyria API...")

                # Generate music using Vertex AI SDK
                response = self.client.models.generate_content(
                    model=self.model,
                    contents="\n".join(prompt_parts),
                    config=config,
                )

                # Extract audio data
                # Lyria returns audio in response parts
                audio_bytes = None

                if hasattr(response, "parts"):
                    for part in response.parts:
                        if hasattr(part, "inline_data"):
                            # Audio data is in inline_data
                            audio_bytes = part.inline_data.data
                            break
                        elif hasattr(part, "data"):
                            audio_bytes = part.data
                            break

                if not audio_bytes:
                    # Fallback: Check if response has audio attribute
                    if hasattr(response, "audio"):
                        audio_bytes = response.audio
                    elif hasattr(response, "text"):
                        # May be base64 encoded
                        audio_bytes = base64.b64decode(response.text)
                    else:
                        raise ValueError(
                            f"No audio data in response. Response type: {type(response)}"
                        )

                # Ensure audio_bytes is bytes
                if isinstance(audio_bytes, str):
                    audio_bytes = base64.b64decode(audio_bytes)

                # Extract metadata
                metadata = {
                    "model": self.model,
                    "format": "mp3",  # Lyria outputs MP3
                    "duration_seconds": 30,  # Lyria generates ~30s music
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "seed": seed,
                }

                logger.info(f"✅ Music generated successfully")
                logger.info(f"   Size: {len(audio_bytes)} bytes")
                logger.info(f"   Duration: ~{metadata['duration_seconds']}s")

                return audio_bytes, metadata

            except Exception as e:
                error_msg = str(e)

                # Check if quota/rate limit error
                is_quota_error = (
                    "429" in error_msg
                    or "RESOURCE_EXHAUSTED" in error_msg
                    or "quota" in error_msg.lower()
                    or "rate limit" in error_msg.lower()
                )

                if is_quota_error and attempt < max_retries - 1:
                    # Exponential backoff: 10s, 30s, 60s
                    # Longer wait because quota is per minute
                    wait_time = 10 * (3**attempt)
                    logger.warning(
                        f"⚠️ Quota/rate limit exceeded (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time}s... (Quota resets every minute)"
                    )
                    logger.warning(f"   Error: {error_msg}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Not quota error or final attempt - raise
                    logger.error(f"❌ Lyria generation failed: {e}", exc_info=True)

                    if is_quota_error:
                        raise Exception(
                            f"Lyria quota exceeded. Google Cloud has very low default quota "
                            f"for Lyria (1-2 requests/min). Please request quota increase at: "
                            f"https://console.cloud.google.com/iam-admin/quotas?project=wordai-6779e"
                        )
                    raise


# Singleton instance
_lyria_service = None


def get_lyria_service() -> LyriaService:
    """Get singleton Lyria service instance"""
    global _lyria_service
    if _lyria_service is None:
        _lyria_service = LyriaService()
    return _lyria_service
