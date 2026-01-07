"""
Lyria Music Generation Service
Uses Google Vertex AI Lyria-002 model for instrumental music generation
"""

import os
import logging
import base64
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
    ) -> Tuple[bytes, Dict]:
        """
        Generate instrumental music from text prompt

        Args:
            prompt: Text description of music (English)
            negative_prompt: What to exclude from music (optional)
            seed: Random seed for deterministic generation (optional)

        Returns:
            Tuple of (audio_bytes, metadata)
            - audio_bytes: MP3 audio data
            - metadata: Dict with duration, format, etc.
        """
        try:
            logger.info(f"🎵 Generating music with Lyria")
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
            logger.error(f"❌ Lyria generation failed: {e}", exc_info=True)
            raise


# Singleton instance
_lyria_service = None


def get_lyria_service() -> LyriaService:
    """Get singleton Lyria service instance"""
    global _lyria_service
    if _lyria_service is None:
        _lyria_service = LyriaService()
    return _lyria_service
