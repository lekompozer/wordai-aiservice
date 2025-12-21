"""
Slide Narration Service
Generate subtitles and audio narration for slide presentations
Uses 2-step flow similar to Listening Test
"""

import os
import logging
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger("chatbot")

# Initialize Gemini client
try:
    gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    logger.info("✅ Gemini client initialized for slide narration")
except Exception as e:
    logger.error(f"❌ Failed to initialize Gemini client: {e}")
    gemini_client = None


class SlideNarrationService:
    """Service for generating slide narration subtitles and audio"""

    def __init__(self):
        """Initialize service"""
        self.gemini_client = gemini_client
        self.gemini_model = "gemini-3-pro-preview"

    async def generate_subtitles(
        self,
        presentation_id: str,
        slides: List[Dict],
        mode: str,
        language: str,
        user_query: str,
        title: str,
        topic: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Step 1: Generate subtitles with timestamps for all slides

        Args:
            presentation_id: Presentation ID
            slides: List of slide dicts with html, elements, background
            mode: "presentation" or "academy"
            language: Language code (vi/en/zh)
            user_query: User instructions
            title: Presentation title
            topic: Presentation topic
            user_id: User ID

        Returns:
            Dict with narration_id, slides with subtitles, metadata
        """
        try:
            start_time = time.time()

            logger.info(f"🎙️ Generating subtitles for presentation {presentation_id}")
            logger.info(f"   Mode: {mode}, Language: {language}")
            logger.info(f"   Slides: {len(slides)}, User query: {user_query}")

            # Build AI prompt
            prompt = self._build_subtitle_prompt(
                slides=slides,
                mode=mode,
                language=language,
                user_query=user_query,
                title=title,
                topic=topic,
            )

            # Call Gemini
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=25000,
                    response_mime_type="application/json",
                ),
            )

            # Parse response
            result = json.loads(response.text)

            # Validate and process subtitles
            processed_slides = self._process_subtitle_response(result, slides)

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                f"✅ Generated subtitles for {len(processed_slides)} slides ({processing_time}ms)"
            )

            return {
                "slides": processed_slides,
                "processing_time_ms": processing_time,
            }

        except Exception as e:
            logger.error(f"❌ Failed to generate subtitles: {e}", exc_info=True)
            raise

    def _build_subtitle_prompt(
        self,
        slides: List[Dict],
        mode: str,
        language: str,
        user_query: str,
        title: str,
        topic: str,
    ) -> str:
        """Build Gemini prompt for subtitle generation"""

        # Extract slide overview WITH element details
        slide_overview = []
        for idx, slide in enumerate(slides):
            # Include element types and positions for context
            element_details = []
            for elem in slide.get("elements", []):
                element_details.append(
                    {
                        "id": elem.get("id", f"elem_{idx}"),
                        "type": elem.get("type", "unknown"),
                        "position": elem.get("position", {}),
                    }
                )

            overview = {
                "index": idx,
                "html": slide.get("html", ""),
                "elements": element_details,
                "background_type": (
                    slide.get("background", {}).get("type")
                    if slide.get("background")
                    else None
                ),
            }
            slide_overview.append(overview)

        # Mode-specific instructions
        if mode == "presentation":
            style_instructions = """
PRESENTATION MODE:
- Concise and engaging narration (30-60 seconds per slide)
- Focus on key points only
- Professional presentation tone
- Clear transitions between slides
- Assume audience is viewing slides simultaneously
- Speaking rate: ~150 words per minute
"""
        else:  # academy
            style_instructions = """
ACADEMY MODE:
- Detailed explanatory narration (60-180 seconds per slide)
- Explain concepts thoroughly
- Teaching/instructional tone
- Provide examples and context
- Assume audience is learning new material
- Speaking rate: ~130 words per minute (slower for clarity)
"""

        prompt = f"""You are an expert presentation narrator. Generate natural, engaging narration with accurate timestamps for this presentation.

PRESENTATION OVERVIEW:
Title: {title}
Topic: {topic}
Total Slides: {len(slides)}
Language: {language}
User Requirements: {user_query}

SLIDES CONTENT (Including Visual Elements):
{json.dumps(slide_overview, indent=2, ensure_ascii=False)}

{style_instructions}

IMPORTANT - Element References:
- When narrating, REFERENCE visual elements when appropriate
- Example: "As you can see in the diagram on the left..." (for shape/image)
- Example: "Notice the three icons representing..." (for icons)
- Include element_references array in subtitle JSON for animation sync

TIMING GUIDELINES:
- Speaking rate: ~150 words per minute (presentation) or ~130 wpm (academy)
- Pause between sentences: 0.3-0.5 seconds
- Pause between paragraphs: 0.8-1.0 seconds
- Transition to next slide: 1.5-2.0 seconds

OUTPUT FORMAT (JSON):
{{
  "narration": [
    {{
      "slide_index": 0,
      "subtitles": [
        {{
          "subtitle_index": 0,
          "start_time": 0.0,
          "end_time": 3.5,
          "duration": 3.5,
          "text": "Welcome to this presentation.",
          "speaker_index": 0,
          "element_references": []
        }},
        {{
          "subtitle_index": 1,
          "start_time": 4.0,
          "end_time": 8.2,
          "duration": 4.2,
          "text": "As shown in this diagram, the process has three main stages.",
          "speaker_index": 0,
          "element_references": ["elem_0"]
        }}
      ]
    }}
  ]
}}

REQUIREMENTS:
1. Create coherent narration that flows naturally across all slides
2. Calculate accurate start_time and end_time based on text length and speaking rate
3. Add natural pauses between sentences and slides
4. Ensure timestamps don't overlap within each slide
5. Match narration style to mode (presentation vs academy)
6. Make content engaging and easy to follow
7. Reference visual elements when appropriate
8. Include element_references array when mentioning visual elements

Generate the complete narration now:"""

        return prompt

    def _process_subtitle_response(
        self,
        result: Dict,
        original_slides: List[Dict],
    ) -> List[Dict]:
        """Process and validate AI subtitle response"""

        processed_slides = []

        for narration_slide in result.get("narration", []):
            slide_index = narration_slide["slide_index"]
            subtitles = narration_slide.get("subtitles", [])

            # Validate timestamps don't overlap
            for i in range(len(subtitles) - 1):
                current = subtitles[i]
                next_sub = subtitles[i + 1]

                if current["end_time"] > next_sub["start_time"]:
                    # Fix overlap: add 0.3s gap
                    next_sub["start_time"] = current["end_time"] + 0.3
                    next_sub["end_time"] = next_sub["start_time"] + next_sub["duration"]

            # Calculate slide duration
            if subtitles:
                last_subtitle = max(subtitles, key=lambda s: s["end_time"])
                slide_duration = last_subtitle["end_time"] + 2.0  # Add 2s buffer
            else:
                slide_duration = 5.0  # Default for empty slides

            processed_slides.append(
                {
                    "slide_index": slide_index,
                    "slide_duration": slide_duration,
                    "subtitles": subtitles,
                    "auto_advance": True,
                    "transition_delay": 2.0,
                }
            )

        return processed_slides

    async def generate_audio(
        self,
        narration_id: str,
        slides_with_subtitles: List[Dict],
        voice_config: Dict,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Step 2: Generate audio from subtitles
        Reuses GoogleTTSService from Listening Test

        Args:
            narration_id: Narration record ID
            slides_with_subtitles: Slides with subtitle data
            voice_config: Voice configuration (provider, voices, rate)
            user_id: User ID

        Returns:
            Dict with audio_files array
        """
        try:
            start_time = time.time()

            logger.info(f"🔊 Generating audio for narration {narration_id}")
            logger.info(f"   Slides: {len(slides_with_subtitles)}")
            logger.info(f"   Voice provider: {voice_config.get('provider', 'google')}")

            # Import TTS service
            from src.services.google_tts_service import GoogleTTSService
            from src.services.library_audio_service import LibraryAudioService

            tts_service = GoogleTTSService()
            audio_service = LibraryAudioService()

            audio_files = []

            # Generate audio for each slide
            for slide in slides_with_subtitles:
                slide_index = slide["slide_index"]
                subtitles = slide.get("subtitles", [])

                if not subtitles:
                    logger.warning(f"   Slide {slide_index} has no subtitles, skipping")
                    continue

                # Convert subtitles to script format (same as Listening Test)
                script = self._convert_subtitles_to_script(subtitles)

                # Generate audio
                voices = voice_config.get("voices", [])
                voice_name = voices[0]["voice_name"] if voices else "vi-VN-Neural2-A"
                language = voices[0].get("language", "vi-VN")
                speaking_rate = voices[0].get("speaking_rate", 1.0)
                use_pro_model = voice_config.get("use_pro_model", True)

                audio_bytes, metadata = await tts_service.generate_multi_speaker_audio(
                    script=script,
                    voice_names=[voice_name],
                    language=language,
                    speaking_rate=speaking_rate,
                    use_pro_model=use_pro_model,
                )

                # Upload to library_audio (same collection as Listening Test)
                file_name = f"narr_{narration_id}_slide_{slide_index}.mp3"

                audio_record = await audio_service.upload_audio(
                    user_id=user_id,
                    audio_bytes=audio_bytes,
                    file_name=file_name,
                    source_type="slide_narration",  # NEW source type
                    source_id=narration_id,
                    metadata={
                        "voice_provider": voice_config.get("provider", "google"),
                        "voice_name": voice_name,
                        "language": language,
                        "duration_seconds": metadata.get("duration_seconds", 0),
                        "slide_index": slide_index,
                    },
                )

                audio_files.append(
                    {
                        "slide_index": slide_index,
                        "audio_url": audio_record["r2_url"],
                        "library_audio_id": str(audio_record["_id"]),
                        "file_size": len(audio_bytes),
                        "format": "mp3",
                        "duration": metadata.get("duration_seconds", 0),
                        "speaker_count": 1,
                    }
                )

                logger.info(
                    f"   ✅ Slide {slide_index}: {metadata.get('duration_seconds', 0)}s audio"
                )

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                f"✅ Generated audio for {len(audio_files)} slides ({processing_time}ms)"
            )

            return {
                "audio_files": audio_files,
                "processing_time_ms": processing_time,
            }

        except Exception as e:
            logger.error(f"❌ Failed to generate audio: {e}", exc_info=True)
            raise

    def _convert_subtitles_to_script(self, subtitles: List[Dict]) -> Dict:
        """Convert subtitles to TTS script format (same as Listening Test)"""

        script = {"speaker_roles": ["Narrator"], "lines": []}

        for subtitle in subtitles:
            script["lines"].append(
                {
                    "speaker": subtitle.get("speaker_index", 0),
                    "text": subtitle["text"],
                }
            )

        return script


# Singleton instance
_slide_narration_service = None


def get_slide_narration_service() -> SlideNarrationService:
    """Get singleton instance of SlideNarrationService"""
    global _slide_narration_service
    if _slide_narration_service is None:
        _slide_narration_service = SlideNarrationService()
    return _slide_narration_service
