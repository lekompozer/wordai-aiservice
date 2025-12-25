"""
Slide Narration Service
Generate subtitles and audio narration for slide presentations
Uses 2-step flow similar to Listening Test
"""

import os
import logging
import json
import time
import re
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId
from html import unescape
from bs4 import BeautifulSoup

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger("chatbot")

# Initialize Gemini client
try:
    # Use GEMINI_API_KEY2 to avoid rate limiting
    api_key = os.getenv("GEMINI_API_KEY2") or os.getenv("GEMINI_API_KEY")
    gemini_client = genai.Client(api_key=api_key)
    logger.info("✅ Gemini client initialized for slide narration (using GEMINI_API_KEY2)")
except Exception as e:
    logger.error(f"❌ Failed to initialize Gemini client: {e}")
    gemini_client = None


class SlideNarrationService:
    """Service for generating slide narration subtitles and audio"""

    def __init__(self):
        """Initialize service"""
        self.gemini_client = gemini_client
        self.gemini_model = "gemini-3-pro-preview"

        # Initialize R2 and library services (same as listening test)
        from src.services.r2_storage_service import get_r2_service
        from src.services.library_manager import LibraryManager
        from src.database.db_manager import DBManager

        self.r2_service = get_r2_service()
        db_manager = DBManager()
        self.library_manager = LibraryManager(
            db=db_manager.db, s3_client=self.r2_service.s3_client
        )

    def _extract_slide_content(self, html: str) -> Dict[str, Any]:
        """
        Extract clean text and structure from slide HTML

        Args:
            html: Raw HTML of slide

        Returns:
            Dict with:
            - title: Slide title (if any)
            - text_content: Clean text content
            - headings: List of headings (h1-h6)
            - lists: Bullet points / numbered lists
            - visual_elements: Icons, images, shapes descriptions
        """
        if not html:
            return {
                "title": "",
                "text_content": "",
                "headings": [],
                "lists": [],
                "visual_elements": [],
            }

        soup = BeautifulSoup(html, "html.parser")

        # Extract title (largest heading or first h1-h3)
        title = ""
        for tag in ["h1", "h2", "h3"]:
            heading = soup.find(tag)
            if heading:
                title = heading.get_text(strip=True)
                break

        # Extract all headings with hierarchy
        headings = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            headings.append(
                {"level": int(tag.name[1]), "text": tag.get_text(strip=True)}
            )

        # Extract lists (ul/ol)
        lists = []
        for list_tag in soup.find_all(["ul", "ol"]):
            list_items = [li.get_text(strip=True) for li in list_tag.find_all("li")]
            if list_items:
                lists.append(
                    {
                        "type": "bullet" if list_tag.name == "ul" else "numbered",
                        "items": list_items,
                    }
                )

        # Extract visual elements (icons, emojis, symbols)
        visual_elements = []

        # Find icons/symbols (common patterns: single char with large font-size)
        for elem in soup.find_all(style=True):
            style = elem.get("style", "")
            text = elem.get_text(strip=True)

            # Detect large single characters (likely icons/emojis)
            if "font-size" in style and len(text) <= 3 and text:
                font_size_match = re.search(r"font-size:\s*(\d+)", style)
                if font_size_match and int(font_size_match.group(1)) > 40:
                    visual_elements.append(
                        {
                            "type": "icon/symbol",
                            "content": text,
                            "description": f"Large visual element: {text}",
                        }
                    )

        # Extract all clean text (remove scripts, styles)
        for script in soup(["script", "style"]):
            script.decompose()

        text_content = soup.get_text(separator=" ", strip=True)
        # Clean up multiple spaces
        text_content = re.sub(r"\s+", " ", text_content)

        return {
            "title": title,
            "text_content": text_content[:1000],  # Limit to 1000 chars
            "headings": headings[:10],  # Max 10 headings
            "lists": lists[:5],  # Max 5 lists
            "visual_elements": visual_elements[:10],  # Max 10 visual elements
        }

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

        # Extract clean slide content (no raw HTML)
        slide_overview = []
        for idx, slide in enumerate(slides):
            # Parse HTML to extract structured content
            slide_html = slide.get("html", "")
            parsed_content = self._extract_slide_content(slide_html)

            overview = {
                "slide_number": idx,
                "title": parsed_content["title"],
                "text_content": parsed_content["text_content"],
                "headings": parsed_content["headings"],
                "bullet_points": [
                    lst for lst in parsed_content["lists"] if lst["type"] == "bullet"
                ],
                "numbered_lists": [
                    lst for lst in parsed_content["lists"] if lst["type"] == "numbered"
                ],
                "visual_elements": parsed_content["visual_elements"],
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
- When narrating, reference visual elements ONLY when truly important to understanding
- AVOID mentioning decorative icons/emojis (🎯, 🚀, ⚙️, etc.) - focus on meaningful diagrams/images
- element_references should be SIMPLE STRINGS (element IDs), NOT objects
- Example CORRECT: "element_references": ["elem_0", "elem_1"]
- Example WRONG: "element_references": [{{"type": "icon", "content": "🚀"}}]
- Keep element_references minimal - only include when you explicitly reference that element in narration text

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
        }},
        {{
          "subtitle_index": 2,
          "start_time": 8.5,
          "end_time": 11.0,
          "duration": 2.5,
          "text": "Let's explore each stage in detail.",
          "speaker_index": 0,
          "element_references": []
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
7. Reference visual elements SPARINGLY - only meaningful diagrams/images, not decorative icons
8. element_references MUST be simple string array like ["elem_0"], NOT objects
9. Leave element_references EMPTY ([]) for most subtitles - only populate when explicitly referencing an element in the narration text

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

            tts_service = GoogleTTSService()

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

                # Upload to R2 and library_audio (same pattern as listening test)
                file_name = f"narr_{narration_id}_slide_{slide_index}.mp3"
                r2_key = f"narration/{user_id}/{narration_id}/slide_{slide_index}.mp3"

                # Upload to R2
                upload_result = await self.r2_service.upload_file(
                    file_content=audio_bytes, r2_key=r2_key, content_type="audio/mpeg"
                )
                audio_url = upload_result["public_url"]

                # Save to library
                audio_record = self.library_manager.save_library_file(
                    user_id=user_id,
                    filename=file_name,
                    file_type="audio",
                    category="audio",
                    r2_url=audio_url,
                    r2_key=r2_key,
                    file_size=len(audio_bytes),
                    mime_type="audio/mpeg",
                    metadata={
                        "source_type": "slide_narration",
                        "source_id": narration_id,
                        "voice_provider": voice_config.get("provider", "google"),
                        "voice_name": voice_name,
                        "language": language,
                        "duration_seconds": metadata.get("duration_seconds", 0),
                        "slide_index": slide_index,
                    },
                )

                library_file_id = audio_record.get(
                    "library_id", audio_record.get("file_id")
                )

                audio_files.append(
                    {
                        "slide_index": slide_index,
                        "audio_url": audio_url,
                        "library_audio_id": library_file_id,
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

    # ============================================================
    # MULTI-LANGUAGE NARRATION SYSTEM
    # ============================================================

    async def generate_subtitles_v2(
        self,
        presentation_id: str,
        language: str,
        mode: str,
        user_id: str,
        user_query: str = "",
    ) -> Dict[str, Any]:
        """
        Generate subtitles for specific language (multi-language system)

        Args:
            presentation_id: Presentation document ID
            language: Language code (vi, en, zh)
            mode: presentation | academy
            user_id: User ID
            user_query: Optional user instructions

        Returns:
            Dict with subtitle_id, version, slides, etc.
        """
        from src.database.db_manager import DBManager

        db_manager = DBManager()
        db = db_manager.db

        # Get presentation document
        presentation = db.documents.find_one({"_id": ObjectId(presentation_id)})
        if not presentation:
            raise ValueError("Presentation not found")

        # Verify document type
        if presentation.get("document_type") != "slide":
            raise ValueError("Document is not a slide presentation")

        # Get next version for this language
        existing_subtitles = list(
            db.presentation_subtitles.find(
                {"presentation_id": presentation_id, "language": language}
            ).sort("version", -1)
        )
        next_version = existing_subtitles[0]["version"] + 1 if existing_subtitles else 1

        # Parse slides from content_html
        content_html = presentation.get("content_html", "")
        slides = self._parse_slides_from_html(content_html)

        if not slides:
            raise ValueError("No slides found in presentation")

        # Generate subtitles using Gemini
        slides_with_subtitles = await self.generate_subtitles(
            slides=slides,
            mode=mode,
            language=language,
            user_query=user_query,
        )

        # Create subtitle document
        subtitle_doc = {
            "presentation_id": presentation_id,
            "user_id": user_id,
            "language": language,
            "version": next_version,
            "mode": mode,
            "slides": slides_with_subtitles,
            "status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "metadata": {
                "total_slides": len(slides_with_subtitles),
                "word_count": sum(
                    len(sub["text"].split())
                    for slide in slides_with_subtitles
                    for sub in slide.get("subtitles", [])
                ),
            },
        }

        result = db.presentation_subtitles.insert_one(subtitle_doc)
        subtitle_doc["_id"] = str(result.inserted_id)

        return subtitle_doc

    async def generate_audio_v2(
        self,
        subtitle_id: str,
        voice_config: Dict,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate audio for subtitle document (multi-language system)

        Args:
            subtitle_id: Subtitle document ID
            voice_config: Voice configuration dict
            user_id: User ID

        Returns:
            List of audio documents created
        """
        from src.database.db_manager import DBManager
        from src.services.google_tts_service import GoogleTTSService
        from src.services.r2_storage_service import get_r2_service
        from src.services.library_manager import LibraryManager

        db_manager = DBManager()
        db = db_manager.db
        r2_service = get_r2_service()
        library_manager = LibraryManager(db=db, s3_client=r2_service.s3_client)
        tts_service = GoogleTTSService()

        # Get subtitle document
        subtitle = db.presentation_subtitles.find_one({"_id": ObjectId(subtitle_id)})
        if not subtitle:
            raise ValueError("Subtitle document not found")

        # Verify ownership
        if subtitle["user_id"] != user_id:
            raise ValueError("Unauthorized access to subtitle document")

        # Extract data
        presentation_id = subtitle["presentation_id"]
        language = subtitle["language"]
        version = subtitle["version"]
        slides = subtitle.get("slides", [])

        # Parse voice config
        use_pro_model = voice_config.get("use_pro_model", True)
        voices = voice_config.get("voices", [])

        # Get voice preference from UI
        # If user explicitly provides voice_name, use it
        # Otherwise, use gender preference to select default voice
        if voices and voices[0].get("voice_name"):
            voice_name = voices[0].get("voice_name")
        else:
            # Map gender to default Gemini voices
            gender = voice_config.get("gender", "male")  # Default to male
            voice_name = "Enceladus" if gender.lower() == "male" else "Sulafat"

        logger.info(
            f"🎙️ Selected voice: {voice_name} (gender: {voice_config.get('gender', 'male')})"
        )

        audio_documents = []

        # Smart chunking: Group slides into chunks that fit Gemini TTS limit
        # Gemini limits: text <= 4000 bytes, text+prompt <= 8000 bytes, output <= 655s
        MAX_BYTES_PER_CHUNK = 3500  # Safe buffer (text limit is 4000 bytes)

        slide_chunks = []  # List of slide groups
        current_chunk = []
        current_chunk_text = ""

        logger.info(f"📊 Processing {len(slides)} slides for audio generation")

        for slide in slides:
            slide_index = slide["slide_index"]
            subtitles = slide.get("subtitles", [])

            if not subtitles:
                logger.info(f"   Slide {slide_index}: No subtitles, skipping")
                continue

            # Convert to TTS script dict
            script = self._convert_subtitles_to_script(subtitles)

            # Convert script dict to plain text for TTS
            slide_text = f"Slide {slide_index + 1}. [short pause] "
            for line in script["lines"]:
                speaker_idx = line["speaker"]
                speaker_role = script["speaker_roles"][speaker_idx]
                text = line["text"]
                slide_text += f"{speaker_role}: {text}. [short pause] "

            slide_text += "[long pause] "  # Dramatic pause between slides (~1000ms)

            # Calculate bytes for this slide
            slide_bytes = len(slide_text.encode("utf-8"))
            logger.info(
                f"   Slide {slide_index}: {len(subtitles)} subtitles, {slide_bytes} bytes"
            )

            # Check if adding this slide exceeds chunk limit
            test_text = current_chunk_text + slide_text
            test_bytes = len(test_text.encode("utf-8"))

            if test_bytes > MAX_BYTES_PER_CHUNK and current_chunk:
                # Start new chunk
                slide_chunks.append(
                    {
                        "slides": current_chunk,
                        "text": current_chunk_text,
                        "bytes": len(current_chunk_text.encode("utf-8")),
                    }
                )
                logger.info(
                    f"✂️  Chunk {len(slide_chunks)}: {len(current_chunk)} slides, "
                    f"{len(current_chunk_text.encode('utf-8'))} bytes"
                )
                current_chunk = []
                current_chunk_text = ""

            # Add slide to current chunk
            current_chunk.append(
                {"slide_index": slide_index, "subtitles": subtitles, "text": slide_text}
            )
            current_chunk_text += slide_text

        # Add last chunk
        if current_chunk:
            slide_chunks.append(
                {
                    "slides": current_chunk,
                    "text": current_chunk_text,
                    "bytes": len(current_chunk_text.encode("utf-8")),
                }
            )
            logger.info(
                f"✂️  Chunk {len(slide_chunks)}: {len(current_chunk)} slides, "
                f"{len(current_chunk_text.encode('utf-8'))} bytes"
            )

        if not slide_chunks:
            raise ValueError("No subtitle content to generate audio")

        logger.info(
            f"🎤 Generating {len(slide_chunks)} audio file(s) for {sum(len(c['slides']) for c in slide_chunks)} slides"
        )

        # Generate audio for each chunk
        for chunk_index, chunk in enumerate(slide_chunks):
            chunk_text = chunk["text"]
            chunk_slides = chunk["slides"]
            chunk_bytes = chunk["bytes"]

            logger.info(
                f"🔊 Chunk {chunk_index + 1}/{len(slide_chunks)}: "
                f"{len(chunk_slides)} slides, {chunk_bytes} bytes"
            )

            # Generate audio with retry logic (Gemini API can have intermittent 500 errors)
            max_retries = 5  # Increased retries to avoid breaking entire task
            retry_delay = 15  # Wait 15s between retries to avoid rate limits

            for attempt in range(max_retries):
                try:
                    audio_data, metadata = await tts_service.generate_audio(
                        text=chunk_text,
                        language=language,
                        voice_name=voice_name,
                        use_pro_model=use_pro_model,
                    )
                    break  # Success, exit retry loop

                except Exception as e:
                    error_msg = str(e)
                    is_retryable = (
                        "500" in error_msg
                        or "INTERNAL" in error_msg
                        or "429" in error_msg
                    )

                    if attempt < max_retries - 1 and is_retryable:
                        logger.warning(
                            f"⚠️  Chunk {chunk_index + 1} failed (attempt {attempt + 1}/{max_retries}): {error_msg}"
                        )
                        logger.info(f"   ⏳ Waiting {retry_delay}s before retry...")
                        await asyncio.sleep(retry_delay)
                    else:
                        # Final failure or non-retryable error
                        logger.error(
                            f"❌ Chunk {chunk_index + 1} failed after {attempt + 1} attempts"
                        )
                        raise

            # Upload audio file
            file_name = f"narration_{presentation_id}_{language}_v{version}_chunk_{chunk_index}.mp3"
            r2_key = f"narration/{user_id}/{presentation_id}/{language}_v{version}_chunk_{chunk_index}.mp3"

            upload_result = await r2_service.upload_file(
                file_content=audio_data,
                r2_key=r2_key,
                content_type="audio/mpeg",
            )
            audio_url = upload_result["public_url"]

            total_duration = metadata.get("duration", 0)

            # Calculate timestamps for slides in this chunk
            slide_timestamps = []
            current_position = 0

            for slide_info in chunk_slides:
                slide_text_len = len(slide_info["text"])
                # Proportional duration based on text length
                char_ratio = slide_text_len / len(chunk_text) if chunk_text else 0
                slide_duration = total_duration * char_ratio

                slide_timestamps.append(
                    {
                        "slide_index": slide_info["slide_index"],
                        "start_time": current_position,
                        "duration": slide_duration,
                        "end_time": current_position + slide_duration,
                    }
                )
                current_position += slide_duration

            # Save to library
            library_audio = library_manager.save_library_file(
                user_id=user_id,
                filename=file_name,
                file_type="audio",
                category="audio",
                r2_url=audio_url,
                r2_key=r2_key,
                file_size=len(audio_data),
                mime_type="audio/mpeg",
                metadata={
                    "source_type": "slide_narration",
                    "presentation_id": presentation_id,
                    "subtitle_id": subtitle_id,
                    "language": language,
                    "version": version,
                    "chunk_index": chunk_index,
                    "total_chunks": len(slide_chunks),
                    "chunk_slides": len(chunk_slides),
                    "total_duration_seconds": total_duration,
                    "slide_timestamps": slide_timestamps,
                },
            )

            # Create presentation_audio document for this chunk
            audio_doc = {
                "presentation_id": presentation_id,
                "subtitle_id": subtitle_id,
                "user_id": user_id,
                "language": language,
                "version": version,
                "audio_url": audio_url,
                "audio_type": (
                    "chunked" if len(slide_chunks) > 1 else "full_presentation"
                ),
                "chunk_index": chunk_index,
                "total_chunks": len(slide_chunks),
                "slide_count": len(chunk_slides),
                "slide_timestamps": slide_timestamps,
                "audio_metadata": {
                    "duration_seconds": total_duration,
                    "file_size_bytes": len(audio_data),
                    "format": "mp3",
                    "sample_rate": metadata.get("sample_rate", 24000),
                    "voice_name": metadata.get("voice_name", voice_name),
                    "model": metadata.get("model", "gemini-2.5-flash-preview-tts"),
                },
                "library_audio_id": str(library_audio),
                "generation_method": "ai_generated",
                "voice_config": voice_config,
                "status": "ready",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            result = db.presentation_audio.insert_one(audio_doc)
            audio_doc["_id"] = str(result.inserted_id)
            audio_documents.append(audio_doc)

            logger.info(
                f"   ✅ Chunk {chunk_index + 1}: {len(audio_data)} bytes, {total_duration}s, "
                f"{len(chunk_slides)} slides"
            )

        logger.info(
            f"✅ Generated {len(audio_documents)} audio file(s) for presentation {presentation_id}"
        )

        # 🔥 NEW: Merge chunks into single file if multiple chunks
        if len(audio_documents) > 1:
            logger.info(
                f"🎵 Merging {len(audio_documents)} audio chunks into 1 file..."
            )
            merged_audio_doc = await self._merge_audio_chunks(
                audio_documents=audio_documents,
                presentation_id=presentation_id,
                subtitle_id=subtitle_id,
                language=language,
                version=version,
                user_id=user_id,
                voice_config=voice_config,
            )
            # Return only the merged audio document
            return [merged_audio_doc]

        return audio_documents

    async def _merge_audio_chunks(
        self,
        audio_documents: List[Dict],
        presentation_id: str,
        subtitle_id: str,
        language: str,
        version: int,
        user_id: str,
        voice_config: Dict,
    ) -> Dict[str, Any]:
        """
        Merge multiple audio chunks into single file with global timestamps

        Args:
            audio_documents: List of chunk audio documents
            presentation_id: Presentation ID
            subtitle_id: Subtitle document ID
            language: Language code
            version: Subtitle version
            user_id: User ID
            voice_config: Voice configuration

        Returns:
            Merged audio document
        """
        import io
        import httpx
        from pydub import AudioSegment
        from src.database.db_manager import DBManager

        db_manager = DBManager()
        db = db_manager.db

        try:
            # Download all chunks and merge
            combined_audio = AudioSegment.empty()
            global_timestamps = []
            current_time = 0.0

            logger.info(f"   📥 Downloading {len(audio_documents)} chunks...")

            for chunk_idx, chunk_doc in enumerate(audio_documents):
                # Download chunk from R2
                audio_url = chunk_doc["audio_url"]
                async with httpx.AsyncClient() as client:
                    response = await client.get(audio_url)
                    response.raise_for_status()
                    audio_data = response.content

                # Load audio segment
                audio_segment = AudioSegment.from_mp3(io.BytesIO(audio_data))

                # Add chunk timestamps with offset
                chunk_timestamps = chunk_doc.get("slide_timestamps", [])
                for ts in chunk_timestamps:
                    global_timestamps.append(
                        {
                            "slide_index": ts["slide_index"],
                            "start_time": current_time + ts["start_time"],
                            "end_time": current_time + ts["end_time"],
                        }
                    )

                # Append to combined audio
                combined_audio += audio_segment
                current_time += len(audio_segment) / 1000.0  # pydub uses milliseconds

                logger.info(
                    f"   ✅ Merged chunk {chunk_idx + 1}/{len(audio_documents)}"
                )

            # Export merged audio
            logger.info("   💾 Exporting merged audio...")
            output_buffer = io.BytesIO()
            combined_audio.export(output_buffer, format="mp3", bitrate="192k")
            merged_audio_data = output_buffer.getvalue()

            # Upload to R2 and library
            file_name = f"narration_{presentation_id}_{language}_v{version}_merged.mp3"
            r2_key = f"narration/{user_id}/{presentation_id}/{file_name}"

            upload_result = await self.r2_service.upload_file(
                file_content=merged_audio_data,
                r2_key=r2_key,
                content_type="audio/mpeg",
            )

            # Upload to library_audio
            library_audio = self.library_manager.upload_audio(
                user_id=user_id,
                audio_data=merged_audio_data,
                file_name=file_name,
                content_type="audio/mpeg",
            )

            # Create merged audio document
            merged_doc = {
                "user_id": user_id,
                "presentation_id": presentation_id,
                "subtitle_id": subtitle_id,
                "language": language,
                "version": version,
                "slide_index": -1,  # -1 indicates merged/full presentation audio
                "audio_url": upload_result["url"],
                "audio_type": "merged_presentation",
                "chunk_index": 0,
                "total_chunks": 1,
                "slide_count": len(global_timestamps),
                "slide_timestamps": global_timestamps,
                "audio_metadata": {
                    "duration_seconds": len(combined_audio) / 1000.0,
                    "file_size_bytes": len(merged_audio_data),
                    "format": "mp3",
                    "sample_rate": combined_audio.frame_rate,
                    "voice_name": audio_documents[0]["audio_metadata"]["voice_name"],
                    "model": audio_documents[0]["audio_metadata"]["model"],
                    "merged_from_chunks": len(audio_documents),
                },
                "library_audio_id": str(library_audio),
                "generation_method": "ai_generated",
                "voice_config": voice_config,
                "status": "ready",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            result = db.presentation_audio.insert_one(merged_doc)
            merged_doc["_id"] = str(result.inserted_id)

            # Mark chunk documents as obsolete (keep for debugging but don't return to client)
            db.presentation_audio.update_many(
                {"_id": {"$in": [ObjectId(doc["_id"]) for doc in audio_documents]}},
                {
                    "$set": {
                        "status": "obsolete_chunk",
                        "replaced_by": str(result.inserted_id),
                    }
                },
            )

            logger.info(
                f"✅ Merged audio: {len(merged_audio_data)} bytes, "
                f"{len(combined_audio) / 1000.0:.1f}s, {len(global_timestamps)} slides"
            )

            return merged_doc

        except Exception as e:
            logger.error(f"❌ Failed to merge audio chunks: {e}", exc_info=True)
            # Fallback: return original chunks
            logger.warning("⚠️ Falling back to returning individual chunks")
            return audio_documents

    async def upload_audio(
        self,
        subtitle_id: str,
        slide_index: int,
        audio_file_data: bytes,
        audio_metadata: Dict,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Upload user-provided audio file

        Args:
            subtitle_id: Subtitle document ID
            slide_index: Slide index
            audio_file_data: Audio file bytes
            audio_metadata: Audio metadata (duration, format, etc.)
            user_id: User ID

        Returns:
            Audio document created
        """
        from src.database.db_manager import DBManager
        from src.services.r2_storage_service import get_r2_service
        from src.services.library_manager import LibraryManager

        db_manager = DBManager()
        db = db_manager.db
        r2_service = get_r2_service()
        library_manager = LibraryManager(db=db, s3_client=r2_service.s3_client)

        # Get subtitle document
        subtitle = db.presentation_subtitles.find_one({"_id": ObjectId(subtitle_id)})
        if not subtitle:
            raise ValueError("Subtitle document not found")

        # Verify ownership
        if subtitle["user_id"] != user_id:
            raise ValueError("Unauthorized access to subtitle document")

        # Extract data
        presentation_id = subtitle["presentation_id"]
        language = subtitle["language"]
        version = subtitle["version"]

        # Upload to R2 and library_audio
        file_format = audio_metadata.get("format", "mp3")
        file_name = f"uploaded_{presentation_id}_slide_{slide_index}_{language}_v{version}.{file_format}"
        r2_key = f"narration/{user_id}/{presentation_id}/uploaded_slide_{slide_index}_{language}_v{version}.{file_format}"

        upload_result = await r2_service.upload_file(
            file_content=audio_file_data,
            r2_key=r2_key,
            content_type=f"audio/{file_format}",
        )
        audio_url = upload_result["public_url"]

        library_audio = library_manager.save_library_file(
            user_id=user_id,
            filename=file_name,
            file_type="audio",
            category="audio",
            r2_url=audio_url,
            r2_key=r2_key,
            file_size=len(audio_file_data),
            mime_type=f"audio/{file_format}",
            metadata={
                "source_type": "slide_narration",
                "presentation_id": presentation_id,
                "subtitle_id": subtitle_id,
                "language": language,
                "version": version,
                "slide_index": slide_index,
                "duration_seconds": audio_metadata["duration_seconds"],
                "uploaded": True,
            },
        )

        # Create presentation_audio document
        audio_doc = {
            "presentation_id": presentation_id,
            "subtitle_id": subtitle_id,
            "user_id": user_id,
            "language": language,
            "version": version,
            "slide_index": slide_index,
            "audio_url": audio_url,
            "audio_metadata": audio_metadata,
            "generation_method": "user_uploaded",
            "voice_config": None,
            "status": "ready",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        result = db.presentation_audio.insert_one(audio_doc)
        audio_doc["_id"] = str(result.inserted_id)

        return audio_doc


# Singleton instance
_slide_narration_service = None


def get_slide_narration_service() -> SlideNarrationService:
    """Get singleton instance of SlideNarrationService"""
    global _slide_narration_service
    if _slide_narration_service is None:
        _slide_narration_service = SlideNarrationService()
    return _slide_narration_service
