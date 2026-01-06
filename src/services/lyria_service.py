"""
Lyria Music Generation Service
Uses Google Vertex AI Lyria-002 model for instrumental music generation
"""

import os
import logging
import base64
import httpx
from typing import Dict, Optional, Tuple
from google.auth import default
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)


class LyriaService:
    """Service for Lyria music generation via Vertex AI"""

    def __init__(self):
        """Initialize Lyria service with Vertex AI credentials"""
        self.project_id = os.getenv("FIREBASE_PROJECT_ID", "wordai-6779e")
        self.location = "us-central1"  # Lyria available in us-central1
        self.model = "lyria-002"

        # Build Vertex AI endpoint
        self.endpoint = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}/"
            f"publishers/google/models/{self.model}:predict"
        )

        # Get credentials
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            credentials_path = "/app/wordai-6779e-ed6189c466f1.json"
            if os.path.exists(credentials_path):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

        logger.info(
            f"✅ Lyria service initialized (project={self.project_id}, location={self.location})"
        )
        logger.info(f"   Model: {self.model}")
        logger.info(f"   Endpoint: {self.endpoint}")

    def _get_access_token(self) -> str:
        """Get Google Cloud access token for authentication"""
        credentials, _ = default()
        credentials.refresh(Request())
        return credentials.token

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

            # Build request payload
            request_body = {
                "instances": [
                    {
                        "prompt": prompt,
                    }
                ],
                "parameters": {"sample_count": 1},
            }

            # Add optional parameters
            if negative_prompt:
                request_body["instances"][0]["negative_prompt"] = negative_prompt
                logger.info(f"   Negative prompt: {negative_prompt}")

            if seed is not None:
                # If seed is provided, remove sample_count (cannot use both)
                request_body["instances"][0]["seed"] = seed
                del request_body["parameters"]["sample_count"]
                logger.info(f"   Seed: {seed}")

            # Get access token
            access_token = self._get_access_token()

            # Make request to Vertex AI
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            logger.info(f"   🔄 Calling Vertex AI Lyria API...")

            async with httpx.AsyncClient(
                timeout=120.0
            ) as client:  # 2 min timeout (music generation takes ~30-60s)
                response = await client.post(
                    self.endpoint, json=request_body, headers=headers
                )

                response.raise_for_status()
                result = response.json()

            # Parse response
            # Lyria returns base64-encoded audio data
            if "predictions" not in result or not result["predictions"]:
                raise ValueError("No predictions in Lyria response")

            prediction = result["predictions"][0]

            # Audio data is in base64 format
            if "audio" in prediction:
                audio_base64 = prediction["audio"]
                audio_bytes = base64.b64decode(audio_base64)
            elif "audioContent" in prediction:
                audio_base64 = prediction["audioContent"]
                audio_bytes = base64.b64decode(audio_base64)
            else:
                raise ValueError(
                    f"No audio data in response. Keys: {prediction.keys()}"
                )

            # Extract metadata
            metadata = {
                "model": self.model,
                "format": "mp3",  # Lyria outputs MP3
                "duration_seconds": 30,  # Lyria generates ~30s music
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "seed": seed,
            }

            # Add any additional metadata from response
            if "metadata" in prediction:
                metadata.update(prediction["metadata"])

            logger.info(f"✅ Music generated successfully")
            logger.info(f"   Size: {len(audio_bytes)} bytes")
            logger.info(f"   Duration: ~{metadata['duration_seconds']}s")

            return audio_bytes, metadata

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            logger.error(
                f"❌ Lyria API error ({e.response.status_code}): {error_detail}"
            )
            raise Exception(
                f"Lyria API failed: {e.response.status_code} - {error_detail}"
            )

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
