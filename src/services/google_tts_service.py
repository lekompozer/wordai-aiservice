"""
Google Cloud Text-to-Speech Service
Uses Vertex AI with google-genai SDK (Gemini TTS)
"""

import os
import logging
import struct
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

        # Supported languages (24 languages from Gemini TTS)
        self.supported_languages = {
            "ar": "Arabic (Egyptian)",
            "de": "German",
            "en": "English (US)",
            "es": "Spanish (US)",
            "fr": "French",
            "hi": "Hindi",
            "id": "Indonesian",
            "it": "Italian",
            "ja": "Japanese",
            "ko": "Korean",
            "pt": "Portuguese (Brazil)",
            "ru": "Russian",
            "nl": "Dutch",
            "pl": "Polish",
            "th": "Thai",
            "tr": "Turkish",
            "vi": "Vietnamese",
            "ro": "Romanian",
            "uk": "Ukrainian",
            "bn": "Bengali",
            "mr": "Marathi",
            "ta": "Tamil",
            "te": "Telugu",
            "zh": "Chinese",  # Additional common language
        }

        # All 30 available voices from Gemini TTS
        self.all_voices = {
            "Zephyr": "Bright",
            "Puck": "Upbeat",
            "Charon": "Informative",
            "Kore": "Firm",
            "Fenrir": "Excitable",
            "Leda": "Youthful",
            "Orus": "Firm",
            "Aoede": "Breezy",
            "Callirrhoe": "Easy-going",
            "Autonoe": "Bright",
            "Enceladus": "Breathy",
            "Iapetus": "Clear",
            "Umbriel": "Easy-going",
            "Algieba": "Smooth",
            "Despina": "Smooth",
            "Erinome": "Clear",
            "Algenib": "Gravelly",
            "Rasalgethi": "Informative",
            "Laomedeia": "Upbeat",
            "Achernar": "Soft",
            "Alnilam": "Firm",
            "Schedar": "Even",
            "Gacrux": "Mature",
            "Pulcherrima": "Forward",
            "Achird": "Friendly",
            "Zubenelgenubi": "Casual",
            "Vindemiatrix": "Gentle",
            "Sadachbia": "Lively",
            "Sadaltager": "Knowledgeable",
            "Sulafat": "Warm",
        }

    def _convert_pcm_to_wav(
        self,
        pcm_data: bytes,
        sample_rate: int = 24000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> bytes:
        """
        Convert raw PCM data to WAV format with proper header

        Args:
            pcm_data: Raw PCM audio data
            sample_rate: Sample rate (default: 24000 Hz from Gemini)
            channels: Number of channels (default: 1 for mono)
            sample_width: Sample width in bytes (default: 2 for 16-bit)

        Returns:
            WAV file bytes with header
        """
        # WAV file header structure
        # Reference: http://soundfile.sapp.org/doc/WaveFormat/

        data_size = len(pcm_data)

        # RIFF header
        riff_header = b"RIFF"
        file_size = data_size + 36  # 36 bytes for header
        riff_size = struct.pack("<I", file_size)
        wave_header = b"WAVE"

        # Format chunk
        fmt_header = b"fmt "
        fmt_size = struct.pack("<I", 16)  # PCM format chunk size
        audio_format = struct.pack("<H", 1)  # 1 = PCM
        num_channels = struct.pack("<H", channels)
        sample_rate_packed = struct.pack("<I", sample_rate)
        byte_rate = struct.pack("<I", sample_rate * channels * sample_width)
        block_align = struct.pack("<H", channels * sample_width)
        bits_per_sample = struct.pack("<H", sample_width * 8)

        # Data chunk
        data_header = b"data"
        data_size_packed = struct.pack("<I", data_size)

        # Combine all parts
        wav_file = (
            riff_header
            + riff_size
            + wave_header
            + fmt_header
            + fmt_size
            + audio_format
            + num_channels
            + sample_rate_packed
            + byte_rate
            + block_align
            + bits_per_sample
            + data_header
            + data_size_packed
            + pcm_data
        )

        logger.info(f"Converted PCM to WAV: {len(pcm_data)} -> {len(wav_file)} bytes")
        return wav_file

    def get_language_code(self, lang: str) -> str:
        """Convert 2-letter code to BCP-47 format for Gemini TTS"""
        language_codes = {
            "ar": "ar-EG",  # Arabic (Egyptian)
            "de": "de-DE",  # German
            "en": "en-US",  # English (US)
            "es": "es-US",  # Spanish (US)
            "fr": "fr-FR",  # French
            "hi": "hi-IN",  # Hindi
            "id": "id-ID",  # Indonesian
            "it": "it-IT",  # Italian
            "ja": "ja-JP",  # Japanese
            "ko": "ko-KR",  # Korean
            "pt": "pt-BR",  # Portuguese (Brazil)
            "ru": "ru-RU",  # Russian
            "nl": "nl-NL",  # Dutch
            "pl": "pl-PL",  # Polish
            "th": "th-TH",  # Thai
            "tr": "tr-TR",  # Turkish
            "vi": "vi-VN",  # Vietnamese
            "ro": "ro-RO",  # Romanian
            "uk": "uk-UA",  # Ukrainian
            "bn": "bn-BD",  # Bengali
            "mr": "mr-IN",  # Marathi
            "ta": "ta-IN",  # Tamil
            "te": "te-IN",  # Telugu
            "zh": "cmn-CN",  # Chinese (Mandarin)
        }
        return language_codes.get(lang, "en-US")

    async def get_available_voices(self, language: str = "vi") -> List[Dict]:
        """
        Get all 30 available Gemini TTS voices

        All voices work with all languages (Gemini auto-detects language)
        """
        voices = []
        for voice_name, description in self.all_voices.items():
            voices.append(
                {
                    "name": voice_name,
                    "description": description,
                    "language_codes": list(self.supported_languages.keys()),
                    "natural_sample_rate_hertz": 24000,
                }
            )

        logger.info(
            f"Found {len(voices)} voices (all support {len(self.supported_languages)} languages)"
        )
        return voices

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

            # Generate audio (run in thread pool to avoid blocking event loop)
            import asyncio

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],  # Required for TTS models
                    speech_config=speech_config,
                ),
            )

            # Extract audio data (raw PCM format from Gemini)
            audio_data = response.candidates[0].content.parts[0].inline_data.data

            # Check if audio_data is base64 string or bytes
            if isinstance(audio_data, str):
                import base64

                audio_data = base64.b64decode(audio_data)
                logger.info(f"Decoded base64 audio data: {len(audio_data)} bytes")
            elif isinstance(audio_data, bytes):
                logger.info(f"Audio data is already bytes: {len(audio_data)} bytes")
            else:
                raise ValueError(f"Unexpected audio data type: {type(audio_data)}")

            # Convert raw PCM to WAV format with header
            wav_data = self._convert_pcm_to_wav(
                audio_data, sample_rate=24000, channels=1, sample_width=2
            )

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
            return wav_data, metadata

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

    async def generate_multi_speaker_audio(
        self,
        script: Dict,
        voice_names: List[str],
        language: str = "en",
        speaking_rate: float = 1.0,
        use_pro_model: bool = False,
    ) -> Tuple[bytes, Dict]:
        """
        Generate multi-speaker audio using Gemini TTS

        Args:
            script: Dict with 'speaker_roles' (list of names) and 'lines' (list of {speaker: int, text: str})
            voice_names: List of voice names for each speaker (up to 2 speakers)
            language: Language code
            speaking_rate: Not used (kept for compatibility)
            use_pro_model: Use pro model for higher quality

        Returns:
            (audio_bytes, metadata)

        Example:
            script = {
                "speaker_roles": ["Joe", "Jane"],
                "lines": [
                    {"speaker": 0, "text": "How's it going today Jane?"},
                    {"speaker": 1, "text": "Not too bad, how about you?"}
                ]
            }
            voice_names = ["Kore", "Puck"]
        """
        try:
            speaker_roles = script.get("speaker_roles", [])
            lines = script.get("lines", [])

            if not speaker_roles or not lines:
                raise ValueError("Script must have speaker_roles and lines")

            if len(speaker_roles) > 2:
                raise ValueError("Gemini TTS supports maximum 2 speakers")

            # Build prompt with conversation format
            conversation = []
            for line in lines:
                speaker_idx = line["speaker"]
                speaker_name = speaker_roles[speaker_idx]
                text = line["text"]
                conversation.append(f"{speaker_name}: {text}")

            prompt_text = (
                f"TTS the following conversation between {' and '.join(speaker_roles)}:\n"
                + "\n".join(conversation)
            )

            language_code = self.get_language_code(language)

            # Build multi-speaker voice config
            speaker_voice_configs = []
            for i, speaker_name in enumerate(speaker_roles):
                voice_name = voice_names[i] if i < len(voice_names) else "Aoede"

                speaker_voice_configs.append(
                    types.SpeakerVoiceConfig(
                        speaker=speaker_name,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name
                            )
                        ),
                    )
                )

            # Multi-speaker speech config
            speech_config = types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=speaker_voice_configs
                )
            )

            # Choose model
            model = (
                "gemini-2.5-pro-preview-tts"
                if use_pro_model
                else "gemini-2.5-flash-preview-tts"
            )

            logger.info(
                f"🎙️ Generating multi-speaker audio: {len(speaker_roles)} speakers, {len(lines)} lines"
            )

            # Generate audio (run in thread pool to avoid blocking event loop)
            import asyncio

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=model,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=speech_config,
                ),
            )

            # Extract audio data
            audio_data = response.candidates[0].content.parts[0].inline_data.data

            # Check if audio_data is base64 string or bytes
            if isinstance(audio_data, str):
                import base64

                audio_data = base64.b64decode(audio_data)
                logger.info(f"Decoded base64 audio data: {len(audio_data)} bytes")
            elif isinstance(audio_data, bytes):
                logger.info(f"Audio data is already bytes: {len(audio_data)} bytes")
            else:
                raise ValueError(f"Unexpected audio data type: {type(audio_data)}")

            # Convert raw PCM to WAV format
            wav_data = self._convert_pcm_to_wav(
                audio_data, sample_rate=24000, channels=1, sample_width=2
            )

            # Calculate duration
            total_words = sum(len(line["text"].split()) for line in lines)
            estimated_duration = (total_words / 150) * 60

            metadata = {
                "format": "wav",
                "sample_rate": 24000,
                "duration_seconds": round(estimated_duration, 2),
                "num_speakers": len(speaker_roles),
                "speaker_roles": speaker_roles,
                "voice_names": voice_names[: len(speaker_roles)],
                "num_lines": len(lines),
                "total_words": total_words,
                "model": model,
                "language_code": language_code,
            }

            logger.info(
                f"✅ Generated multi-speaker audio: {len(speaker_roles)} speakers, {len(lines)} lines, ~{estimated_duration:.1f}s"
            )
            return wav_data, metadata

        except Exception as e:
            logger.error(f"❌ Error generating multi-speaker audio: {e}")
            raise

    async def save_audio_to_file(self, audio_content: bytes, output_path: str) -> None:
        """Save audio bytes to file"""
        try:
            with open(output_path, "wb") as f:
                f.write(audio_content)
            logger.info(f"Audio saved to: {output_path}")
        except Exception as e:
            logger.error(f"Error saving audio: {e}")
            raise
