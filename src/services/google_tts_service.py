"""
Google Cloud Text-to-Speech Service
Uses Vertex AI with google-genai SDK (Gemini TTS)
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GoogleTTSService:
    """Service for Google Cloud Text-to-Speech via Gemini API"""

    def __init__(self):
        """Initialize Gemini client with API key"""
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("VERTEX_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY or VERTEX_API_KEY not found")

        # Initialize Gemini client with API key
        self.client = genai.Client(api_key=self.api_key)

        logger.info("Gemini TTS initialized with API key")

        # Supported languages
        self.language_codes = {
            "vi": "vi-VN",
            "en": "en-US",
            "zh": "cmn-CN",
            "ja": "ja-JP",
            "ko": "ko-KR",
            "th": "th-TH",
            "fr": "fr-FR",
            "de": "de-DE",
            "es": "es-ES",
            "it": "it-IT",
            "pt": "pt-BR",
            "ru": "ru-RU",
            "ar": "ar-XA",
            "hi": "hi-IN",
            "id": "id-ID",
            "ms": "ms-MY",
            "tl": "fil-PH",
        }

    def get_language_code(self, lang: str) -> str:
        """Convert 2-letter code to Google format"""
        return self.language_codes.get(lang, "en-US")

    async def get_available_voices(self, language: str = "vi") -> List[Dict]:
        """
        Get available Gemini TTS voices

        Gemini TTS uses predefined voices: Kore, Aoede, Charon, Puck, Fenrir
        """
        # Predefined Gemini TTS voices
        all_voices = {
            "vi": [
                {
                    "name": "Despina",
                    "gender": "female",
                    "description": "Vietnamese female voice",
                },
                {
                    "name": "Enceladus",
                    "gender": "male",
                    "description": "Vietnamese male voice",
                },
                {
                    "name": "Orus",
                    "gender": "male",
                    "description": "Vietnamese male voice",
                },
                {
                    "name": "Alnilam",
                    "gender": "male",
                    "description": "Vietnamese male voice",
                },
                {
                    "name": "Gacrux",
                    "gender": "female",
                    "description": "Vietnamese female voice",
                },
                {
                    "name": "Leda",
                    "gender": "female",
                    "description": "Vietnamese female voice",
                },
                {
                    "name": "Sulafat",
                    "gender": "female",
                    "description": "Vietnamese female voice",
                },
            ],
            "en": [
                {
                    "name": "Kore",
                    "gender": "female",
                    "description": "Warm and friendly",
                },
                {"name": "Aoede", "gender": "female", "description": "Professional"},
                {"name": "Charon", "gender": "male", "description": "Authoritative"},
                {"name": "Puck", "gender": "neutral", "description": "Conversational"},
                {
                    "name": "Fenrir",
                    "gender": "male",
                    "description": "Deep and resonant",
                },
            ],
        }

        language_code = self.get_language_code(language)
        voices = all_voices.get(language, all_voices["en"])

        # Format for API response
        formatted_voices = []
        for voice in voices:
            formatted_voices.append(
                {
                    "name": voice["name"],
                    "language_codes": [language_code],
                    "gender": voice["gender"],
                    "natural_sample_rate_hertz": 24000,
                    "description": voice.get("description", ""),
                }
            )

        logger.info(f"Found {len(formatted_voices)} voices for {language}")
        return formatted_voices

    def extract_text_from_html(self, html_content: str, max_length: int = 8000) -> str:
        """
        Extract plain text from HTML

        Args:
            html_content: HTML string
            max_length: Max bytes (Gemini TTS limit is 8000)

        Returns:
            Plain text
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text(separator=" ", strip=True)
            text = " ".join(text.split())

            if len(text) > max_length:
                text = text[:max_length]
                logger.warning(f"Text truncated to {max_length} bytes")

            return text

        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            raise ValueError(f"Failed to extract text: {e}")

    async def generate_audio(
        self,
        text: str,
        language: str = "vi",
        voice_name: Optional[str] = None,
        speaking_rate: float = 1.0,
        pitch: float = 0.0,
        prompt: Optional[str] = None,
        use_pro_model: bool = False,
    ) -> Tuple[bytes, Dict]:
        """
        Generate audio using Gemini TTS

        Args:
            text: Text to convert
            language: 2-letter code
            voice_name: Voice (Kore, Aoede, Charon, Puck, Fenrir)
            speaking_rate: Not used in Gemini TTS (kept for compatibility)
            pitch: Not used in Gemini TTS (kept for compatibility)
            prompt: Optional style prompt (e.g., "Say in a curious way")

        Returns:
            (audio_bytes, metadata)
        """
        try:
            if not text or len(text.strip()) == 0:
                raise ValueError("Text cannot be empty")

            if len(text.encode("utf-8")) > 8000:
                raise ValueError("Text too long (max 8000 bytes)")

            language_code = self.get_language_code(language)

            # Build content with optional prompt
            if prompt:
                contents = f"{prompt}: {text}"
            else:
                contents = text

            # Speech config
            speech_config = types.SpeechConfig(
                language_code=language_code,
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name or "Despina"  # Default Vietnamese voice
                    )
                ),
            )

            # Choose model (pro for higher quality, flash for faster)
            model = (
                "gemini-2.5-pro-preview-tts"
                if use_pro_model
                else "gemini-2.5-flash-preview-tts"
            )

            # Generate audio
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],  # Required for TTS models
                    speech_config=speech_config,
                ),
            )

            # Extract audio data (WAV format)
            audio_data = response.candidates[0].content.parts[0].inline_data.data

            # Calculate duration
            word_count = len(text.split())
            estimated_duration = (word_count / 150) * 60

            metadata = {
                "format": "wav",
                "sample_rate": 24000,
                "duration": round(estimated_duration, 2),
                "voice_name": voice_name or "Despina",
                "language_code": language_code,
                "text_length": len(text),
                "word_count": word_count,
                "model": model,
                "prompt": prompt,
            }

            logger.info(
                f"Generated audio: {word_count} words, ~{estimated_duration:.1f}s, voice={voice_name or 'Despina'}, model={model}"
            )
            return audio_data, metadata

        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            raise

    async def generate_audio_from_html(
        self,
        html_content: str,
        language: str = "vi",
        voice_name: Optional[str] = None,
        speaking_rate: float = 1.0,
        pitch: float = 0.0,
        prompt: Optional[str] = None,
        use_pro_model: bool = False,
    ) -> Tuple[bytes, Dict]:
        """Generate audio from HTML content"""
        text = self.extract_text_from_html(html_content, max_length=8000)

        if not text:
            raise ValueError("No text found in HTML")

        return await self.generate_audio(
            text=text,
            language=language,
            voice_name=voice_name,
            speaking_rate=speaking_rate,
            pitch=pitch,
            prompt=prompt,
            use_pro_model=use_pro_model,
        )

    async def save_audio_to_file(self, audio_content: bytes, output_path: str) -> None:
        """Save audio bytes to file"""
        try:
            with open(output_path, "wb") as f:
                f.write(audio_content)
            logger.info(f"Audio saved to: {output_path}")
        except Exception as e:
            logger.error(f"Error saving audio: {e}")
            raise
