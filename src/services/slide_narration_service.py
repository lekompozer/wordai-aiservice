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
    if not api_key:
        raise ValueError("GEMINI_API_KEY2 or GEMINI_API_KEY not found")

    gemini_client = genai.Client(api_key=api_key)
    logger.info("✅ Gemini client initialized for slide narration (GEMINI_API_KEY2)")
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

        # Map language code to full name (Gemini TTS supported languages)
        # BCP-47 codes: https://cloud.google.com/text-to-speech/docs/voices
        language_map = {
            "ar": "Arabic (العربية)",
            "bn": "Bangla (বাংলা)",
            "nl": "Dutch (Nederlands)",
            "en": "English",
            "fr": "French (Français)",
            "de": "German (Deutsch)",
            "hi": "Hindi (हिन्दी)",
            "id": "Indonesian (Bahasa Indonesia)",
            "it": "Italian (Italiano)",
            "ja": "Japanese (日本語)",
            "ko": "Korean (한국어)",
            "mr": "Marathi (मराठी)",
            "pl": "Polish (Polski)",
            "pt": "Portuguese (Português)",
            "ro": "Romanian (Română)",
            "ru": "Russian (Русский)",
            "es": "Spanish (Español)",
            "ta": "Tamil (தமிழ்)",
            "te": "Telugu (తెలుగు)",
            "th": "Thai (ภาษาไทย)",
            "tr": "Turkish (Türkçe)",
            "uk": "Ukrainian (Українська)",
            "vi": "Vietnamese (Tiếng Việt)",
            "zh": "Chinese (中文)",
        }

        # Map to BCP-47 codes for TTS
        bcp47_map = {
            "ar": "ar-EG",
            "bn": "bn-BD",
            "nl": "nl-NL",
            "en": "en-US",
            "fr": "fr-FR",
            "de": "de-DE",
            "hi": "hi-IN",
            "id": "id-ID",
            "it": "it-IT",
            "ja": "ja-JP",
            "ko": "ko-KR",
            "mr": "mr-IN",
            "pl": "pl-PL",
            "pt": "pt-BR",
            "ro": "ro-RO",
            "ru": "ru-RU",
            "es": "es-ES",
            "ta": "ta-IN",
            "te": "te-IN",
            "th": "th-TH",
            "tr": "tr-TR",
            "uk": "uk-UA",
            "vi": "vi-VN",
            "zh": "zh-CN",
        }

        language_name = language_map.get(language, language)
        bcp47_code = bcp47_map.get(language, language)

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
- Professional narration (40-60 seconds per slide)
- Generate 3-4 complete sentences per slide (increased from 2-3 for better pacing)
- Focus on key points with clear explanations
- Professional presentation tone with natural flow
- Clear transitions between slides
- Assume audience is viewing slides simultaneously
- Speaking rate: ~150 words per minute
- Target: 15-20 minutes total for 30 slides (30-40 seconds per slide average)
"""
        else:  # academy
            style_instructions = """
ACADEMY MODE:
- Detailed teaching narration (60-120 seconds per slide)
- Generate 5-6 complete sentences per slide (increased from 3-4 for thorough coverage)
- Explain concepts thoroughly with examples
- Teaching/instructional tone with context
- Provide real-world applications and explanations
- Assume audience is learning new material
- Speaking rate: ~130 words per minute (slower for clarity)
- Target: 20-30 minutes total for 30 slides (40-60 seconds per slide average)
"""

        # Language-specific examples (24 languages supported by Gemini TTS)
        example_texts = {
            "ar": '"مرحبا بكم جميعا. اليوم سوف نستكشف عالم الذكاء الاصطناعي التوليدي."',
            "bn": '"সবাইকে স্বাগতম। আজ আমরা জেনারেটিভ এআই এর জগৎ অন্বেষণ করব।"',
            "de": '"Willkommen allerseits. Heute werden wir die Welt der generativen KI erkunden."',
            "en": '"Welcome everyone. Today we will explore the world of Generative AI together."',
            "es": '"Bienvenidos a todos. Hoy exploraremos el mundo de la IA generativa."',
            "fr": "\"Bienvenue à tous. Aujourd'hui, nous allons explorer le monde de l'IA générative.\"",
            "hi": '"सभी का स्वागत है। आज हम जेनरेटिव एआई की दुनिया का पता लगाएंगे।"',
            "id": '"Selamat datang semuanya. Hari ini kita akan menjelajahi dunia AI generatif."',
            "it": '"Benvenuti a tutti. Oggi esploreremo il mondo dell\'IA generativa."',
            "ja": '"皆さん、ようこそ。今日は生成AIの世界を探求します。"',
            "ko": '"여러분 환영합니다. 오늘은 생성형 AI의 세계를 탐험하겠습니다."',
            "nl": '"Welkom allemaal. Vandaag gaan we de wereld van generatieve AI verkennen."',
            "pl": '"Witajcie wszystkich. Dziś będziemy odkrywać świat generatywnej sztucznej inteligencji."',
            "pt": '"Bem-vindos a todos. Hoje vamos explorar o mundo da IA generativa."',
            "ro": '"Bun venit tuturor. Astăzi vom explora lumea inteligenței artificiale generative."',
            "ru": '"Добро пожаловать всем. Сегодня мы исследуем мир генеративного ИИ."',
            "ta": '"அனைவருக்கும் வரவேற்பு. இன்று நாம் ஜெனரேட்டிவ் AI உலகை ஆராய்வோம்."',
            "te": '"అందరికీ స్వాగతం. ఈ రోజు మనం జెనరేటివ్ AI ప్రపంచాన్ని అన్వేషిస్తాము."',
            "th": '"ยินดีต้อนรับทุกคน วันนี้เราจะสำรวจโลกของ AI แบบสร้างสรรค์"',
            "tr": '"Herkese hoş geldiniz. Bugün üretken yapay zeka dünyasını keşfedeceğiz."',
            "uk": '"Ласкаво просимо всіх. Сьогодні ми досліджуватимемо світ генеративного ШІ."',
            "vi": '"Chào mừng các bạn. Hôm nay chúng ta sẽ cùng khám phá thế giới của Generative AI."',
            "zh": '"欢迎大家。今天我们将一起探索生成式AI的世界。"',
        }
        example_text = example_texts.get(
            language, f'"[Narration text in {language_name}]"'
        )

        prompt = f"""You are an expert presentation narrator. Generate natural, engaging narration for this presentation.

🌍 CRITICAL LANGUAGE REQUIREMENT:
**ALL subtitle text MUST be written in {language_name} (BCP-47: {bcp47_code})**
- Analyze slide content and generate subtitles in {language_name}
- Do NOT translate - narrate naturally in {language_name}
- Use proper grammar, idioms, and speaking style for {language_name}
- If slide content is in different language, translate it to {language_name} narration

SUPPORTED LANGUAGES (24 languages via Gemini TTS):
Arabic, Bangla, Dutch, English, French, German, Hindi, Indonesian, Italian,
Japanese, Korean, Marathi, Polish, Portuguese, Romanian, Russian, Spanish,
Tamil, Telugu, Thai, Turkish, Ukrainian, Vietnamese, Chinese

PRESENTATION OVERVIEW:
Title: {title}
Topic: {topic}
Total Slides: {len(slides)}
Target Language: {language_name} ({bcp47_code})
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

⚠️ CRITICAL 2-STEP PROCESS:
**STEP 1: Generate subtitle TEXT first**
- Write natural, engaging narration for each slide
- Presentation mode: 3-4 complete sentences per slide
- Academy mode: 5-6 complete sentences per slide
- Focus on content quality and natural flow

**STEP 2: Calculate TIMING for each subtitle**
CRITICAL: Timestamps must match actual audio generation timing.

Timing Formula (EXACT - no artificial pauses):
1. Count words in subtitle text you just wrote
2. base_duration = word_count / (speaking_rate / 60)
   - Presentation mode: 150 words/min = 2.5 words/sec
   - Academy mode: 130 words/min = 2.17 words/sec

3. Calculate timestamps with ONLY natural speaking pauses:
   - If first subtitle of entire presentation: start_time = 0
   - Otherwise: start_time = previous_subtitle.end_time + 0.3
   - end_time = start_time + base_duration
   - duration = base_duration

⚠️ IMPORTANT: DO NOT add 1.5s or 2s pause between slides!
- Audio generation creates continuous audio without slide gaps
- Only 0.3s pause between subtitles for natural breathing
- Slides transition smoothly without artificial silence
- This ensures timestamps perfectly match actual audio duration

Example calculation (Presentation mode, 150 wpm):
Slide 0, Subtitle 0: "Chào mừng các bạn đến với khóa học AI." (9 words)
  base_duration = 9 / 2.5 = 3.6s
  start_time = 0.0
  end_time = 0.0 + 3.6 = 3.6
  duration = 3.6

Slide 0, Subtitle 1: "Hôm nay chúng ta sẽ học về Machine Learning." (10 words)
  base_duration = 10 / 2.5 = 4.0s
  start_time = 3.6 + 0.3 = 3.9  (0.3s breathing pause)
  end_time = 3.9 + 4.0 = 7.9
  duration = 4.0

Slide 1, Subtitle 0: "Machine Learning là một nhánh của AI." (8 words)
  base_duration = 8 / 2.5 = 3.2s
  start_time = 7.9 + 0.3 = 8.2  (same 0.3s pause, NO slide gap!)
  end_time = 8.2 + 3.2 = 11.4
  duration = 3.2

OUTPUT FORMAT (JSON):
{{
  "narration": [
    {{
      "slide_index": 0,
      "subtitles": [
        {{
          "subtitle_index": 0,
          "start_time": 0.0,
          "end_time": 3.6,
          "duration": 3.6,
          "text": {example_text},
          "speaker_index": 0,
          "element_references": []
        }},
        {{
          "subtitle_index": 1,
          "start_time": 3.9,
          "end_time": 7.9,
          "duration": 4.0,
          "text": "[Second subtitle in {language_name}]",
          "speaker_index": 0,
          "element_references": []
        }}
      ]
    }},
    {{
      "slide_index": 1,
      "subtitles": [
        {{
          "subtitle_index": 0,
          "start_time": 8.2,
          "end_time": 11.4,
          "duration": 3.2,
          "text": "[First subtitle for slide 2 in {language_name}]",
          "speaker_index": 0,
          "element_references": []
        }}
      ]
    }}
  ]
}}

REQUIREMENTS:
1. Write ALL subtitle text in {language_name} - this is MANDATORY
2. Generate text FIRST, then calculate timing based on word count
3. Use EXACT formula: duration = words / (rate/60), then add 0.3s gaps
4. Presentation: 3-4 sentences/slide, Academy: 5-6 sentences/slide
5. Timestamps MUST be continuous across slides (no slide pauses in audio!)
6. Match narration style to mode (professional vs teaching)
7. Make content engaging and thorough in {language_name}
8. Reference visual elements SPARINGLY - only meaningful diagrams/images
9. element_references MUST be simple string array like ["elem_0"], NOT objects
10. Leave element_references EMPTY ([]) for most subtitles

Generate the complete narration in {language_name} now:"""

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
        presentation = db.documents.find_one({"document_id": presentation_id})
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

        # Parse slides from content_html (same as V1)
        content_html = presentation.get("content_html", "")
        if not content_html:
            raise ValueError("Document has no content")

        # Extract slides from HTML (split by slide divs) - copied from V1 routes
        import re

        # Split slides by <div class="slide">
        slide_pattern = r'<div[^>]*class="slide"[^>]*data-slide-index="(\d+)"[^>]*>(.*?)</div>(?=\s*(?:<div[^>]*class="slide"|$))'
        slide_matches = re.findall(
            slide_pattern, content_html, re.DOTALL | re.IGNORECASE
        )

        if not slide_matches:
            # Fallback: split by any div with data-slide-index
            slide_pattern_simple = r'<div[^>]*data-slide-index="(\d+)"[^>]*>(.*?)</div>'
            slide_matches = re.findall(
                slide_pattern_simple, content_html, re.DOTALL | re.IGNORECASE
            )

        if not slide_matches:
            raise ValueError(
                f"No slides found in document. Content length: {len(content_html)}"
            )

        # Build slides array with html content
        slides = []
        for idx, (slide_index, slide_html) in enumerate(slide_matches):
            slides.append(
                {
                    "index": int(slide_index),
                    "html": f'<div class="slide" data-slide-index="{slide_index}">{slide_html}</div>',
                    "elements": [],
                    "background": (
                        presentation.get("slide_backgrounds", [])[int(slide_index)]
                        if int(slide_index)
                        < len(presentation.get("slide_backgrounds", []))
                        else None
                    ),
                }
            )

        logger.info(
            f"📄 Extracted {len(slides)} slides from document {presentation_id}"
        )

        # Generate subtitles using Gemini (same signature as V1)
        subtitle_result = await self.generate_subtitles(
            presentation_id=presentation_id,
            slides=slides,
            mode=mode,
            language=language,
            user_query=user_query,
            title=presentation.get("title", "Untitled"),
            topic=presentation.get("metadata", {}).get("topic", ""),
            user_id=user_id,
        )

        slides_with_subtitles = subtitle_result["slides"]

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
        force_regenerate: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Generate audio for subtitle document (multi-language system)

        Args:
            subtitle_id: Subtitle document ID
            voice_config: Voice configuration dict
            user_id: User ID
            force_regenerate: Force regenerate all chunks (delete existing)

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

        # Convert language to BCP-47 for TTS API (MongoDB stores short codes)
        bcp47_map = {
            "ar": "ar-EG",
            "bn": "bn-BD",
            "nl": "nl-NL",
            "en": "en-US",
            "fr": "fr-FR",
            "de": "de-DE",
            "hi": "hi-IN",
            "id": "id-ID",
            "it": "it-IT",
            "ja": "ja-JP",
            "ko": "ko-KR",
            "mr": "mr-IN",
            "pl": "pl-PL",
            "pt": "pt-BR",
            "ro": "ro-RO",
            "ru": "ru-RU",
            "es": "es-ES",
            "ta": "ta-IN",
            "te": "te-IN",
            "th": "th-TH",
            "tr": "tr-TR",
            "uk": "uk-UA",
            "vi": "vi-VN",
            "zh": "zh-CN",
        }
        tts_language = bcp47_map.get(
            language, f"{language}-US"
        )  # Convert "en" → "en-US"
        logger.info(f"🌍 Language: {language} → {tts_language} (TTS API)")

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

            # Convert subtitles to clean text for TTS (NO markers, NO prefixes)
            # Gemini TTS only accepts plain text - no SSML, no pause markers
            slide_text_parts = []
            for subtitle in subtitles:
                text = subtitle["text"].strip()
                if text:
                    slide_text_parts.append(text)

            # Join with natural pauses (periods create natural pauses)
            slide_text = ". ".join(slide_text_parts)
            if slide_text and not slide_text.endswith("."):
                slide_text += "."

            # Add silence between slides using empty space (Gemini handles naturally)
            slide_text += " "  # Natural pause between slides

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

        # Track failed chunks for partial success handling
        failed_chunks = []

        # Generate audio for each chunk
        for chunk_index, chunk in enumerate(slide_chunks):
            chunk_text = chunk["text"]
            chunk_slides = chunk["slides"]
            chunk_bytes = chunk["bytes"]

            # Check if chunk already exists (from previous partial run)
            # Skip check if force_regenerate=True
            existing_chunk = None
            if not force_regenerate:
                existing_chunk = db.presentation_audio.find_one(
                    {
                        "presentation_id": presentation_id,
                        "subtitle_id": subtitle_id,
                        "user_id": user_id,
                        "language": language,
                        "version": version,
                        "chunk_index": chunk_index,
                        "status": "ready",
                    }
                )

            if existing_chunk:
                logger.info(
                    f"✅ Chunk {chunk_index + 1}/{len(slide_chunks)}: Already exists (skipping)"
                )
                audio_documents.append(existing_chunk)
                continue

            logger.info(
                f"🔊 Chunk {chunk_index + 1}/{len(slide_chunks)}: "
                f"{len(chunk_slides)} slides, {chunk_bytes} bytes, voice={voice_name}"
            )

            # Generate audio with retry logic (Gemini API can have intermittent 500 errors)
            max_retries = 5  # Increased retries to avoid breaking entire task
            retry_delay = (
                30  # Wait 30s between retries to avoid rate limits and 499 CANCELLED
            )

            audio_data = None  # Initialize to None
            metadata = None

            for attempt in range(max_retries):
                try:
                    audio_data, metadata = await tts_service.generate_audio(
                        text=chunk_text,
                        language=tts_language,  # Use BCP-47 code (e.g., "en-US")
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
                        or "499" in error_msg  # Vertex AI CANCELLED error
                        or "CANCELLED" in error_msg  # Vertex AI concurrent limit
                        or "ReadTimeout" in error_msg
                    )

                    if attempt < max_retries - 1 and is_retryable:
                        logger.warning(
                            f"⚠️  Chunk {chunk_index + 1} failed (attempt {attempt + 1}/{max_retries}): {error_msg}"
                        )
                        logger.info(
                            f"   ⏳ Waiting {retry_delay}s before retry (voice={voice_name})..."
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        # Final failure - track but don't raise (allow partial success)
                        logger.error(
                            f"❌ Chunk {chunk_index + 1} failed after {attempt + 1} attempts: {error_msg}"
                        )
                        failed_chunks.append(
                            {
                                "chunk_index": chunk_index,
                                "error": error_msg,
                                "slides": [s["slide_index"] for s in chunk_slides],
                            }
                        )
                        # Continue to next chunk instead of raising
                        break

            # Skip rest of chunk processing if generation failed
            if audio_data is None:
                logger.warning(
                    f"⚠️  Skipping chunk {chunk_index + 1} processing (generation failed)"
                )
                continue

            # Validate audio quality (detect silent/corrupt audio)
            try:
                from pydub import AudioSegment
                import io

                # Load audio to validate
                audio_format = metadata.get("format", "wav")
                if audio_format == "wav":
                    audio_segment = AudioSegment.from_wav(io.BytesIO(audio_data))
                else:
                    audio_segment = AudioSegment.from_file(
                        io.BytesIO(audio_data), format=audio_format
                    )

                # Check duration (too short = failed)
                duration_seconds = len(audio_segment) / 1000.0
                if duration_seconds < 0.5:
                    error_msg = f"Audio too short: {duration_seconds:.2f}s"
                    logger.error(
                        f"❌ Chunk {chunk_index + 1}: {error_msg} (expected ~{metadata.get('duration', 0):.1f}s)"
                    )
                    failed_chunks.append(
                        {
                            "chunk_index": chunk_index,
                            "error": error_msg,
                            "slides": [s["slide_index"] for s in chunk_slides],
                        }
                    )
                    continue

                # Check audio level (too quiet = silent/corrupt)
                rms = audio_segment.rms
                if rms < 10:  # RMS threshold for silent audio
                    error_msg = f"Audio silent/corrupt: RMS={rms} (too quiet)"
                    logger.error(f"❌ Chunk {chunk_index + 1}: {error_msg}")
                    failed_chunks.append(
                        {
                            "chunk_index": chunk_index,
                            "error": error_msg,
                            "slides": [s["slide_index"] for s in chunk_slides],
                        }
                    )
                    continue

                logger.info(
                    f"   ✅ Audio quality OK: {duration_seconds:.1f}s, RMS={rms:.1f}"
                )

            except Exception as e:
                logger.warning(
                    f"   ⚠️  Audio validation failed (continuing anyway): {e}"
                )
                # Continue with audio upload even if validation fails

            # Upload audio file as WAV (no conversion needed)
            file_name = f"narration_{presentation_id}_{language}_v{version}_chunk_{chunk_index}.wav"
            r2_key = f"narration/{user_id}/{presentation_id}/{language}_v{version}_chunk_{chunk_index}.wav"

            upload_result = await r2_service.upload_file(
                file_content=audio_data,
                r2_key=r2_key,
                content_type="audio/wav",
            )
            audio_url = upload_result["public_url"]

            total_duration = metadata.get("duration", 0)

            # Calculate timestamps using WORD COUNT ratio (more accurate than Gemini timestamps)
            # Example: Slide 1 has 40 words, total chunk has 200 words, total audio is 220s
            # → Slide 1 duration = (40/200) * 220s = 44s

            slide_timestamps = []
            current_position = 0

            # Count total words in chunk
            total_words = 0
            for slide_info in chunk_slides:
                slide_subtitles = slide_info["subtitles"]
                slide_words = sum(len(sub["text"].split()) for sub in slide_subtitles)
                slide_info["word_count"] = slide_words
                total_words += slide_words

            logger.info(
                f"   📊 Total words in chunk: {total_words}, Audio duration: {total_duration:.1f}s"
            )

            # Calculate duration for each slide based on word ratio
            for slide_info in chunk_slides:
                slide_word_count = slide_info.get("word_count", 0)

                if total_words > 0 and slide_word_count > 0:
                    # Word-based duration calculation
                    word_ratio = slide_word_count / total_words
                    slide_duration = total_duration * word_ratio
                else:
                    # Fallback: equal distribution
                    slide_duration = total_duration / len(chunk_slides)

                slide_timestamps.append(
                    {
                        "slide_index": slide_info["slide_index"],
                        "start_time": current_position,
                        "duration": slide_duration,
                        "end_time": current_position + slide_duration,
                        "word_count": slide_word_count,
                    }
                )

                logger.info(
                    f"      Slide {slide_info['slide_index']}: {slide_word_count} words "
                    f"= {slide_duration:.1f}s ({current_position:.1f}s → {current_position + slide_duration:.1f}s)"
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
        # Handle partial success/failure FIRST
        if failed_chunks:
            success_count = len(audio_documents)
            total_count = len(slide_chunks)
            logger.warning(
                f"⚠️  Partial success: {success_count}/{total_count} chunks generated. "
                f"Failed chunks: {[f['chunk_index'] + 1 for f in failed_chunks]}"
            )
            # Raise with partial result info
            raise Exception(
                f"Partial failure: {success_count}/{total_count} chunks completed. "
                f"Retry this job to generate remaining chunks: {[f['chunk_index'] + 1 for f in failed_chunks]}. "
                f"Failed slides: {sum([f['slides'] for f in failed_chunks], [])}"
            )

        # 🔥 Merge chunks into single file if ALL chunks succeeded
        if len(audio_documents) > 1:
            logger.info(
                f"🎵 Merging {len(audio_documents)} audio chunks into 1 file..."
            )
            try:
                merged_audio_doc = await self._merge_audio_chunks(
                    audio_documents=audio_documents,
                    presentation_id=presentation_id,
                    subtitle_id=subtitle_id,
                    language=language,
                    version=version,
                    user_id=user_id,
                    voice_config=voice_config,
                )
                # Return only the merged audio document if merge succeeded
                if merged_audio_doc and isinstance(merged_audio_doc, dict):
                    return [merged_audio_doc]
                else:
                    # Merge returned chunks (fallback case)
                    logger.warning("⚠️ Merge returned chunks, using individual chunks")
                    return audio_documents
            except Exception as e:
                logger.error(f"❌ Merge failed: {e}", exc_info=True)
                logger.warning("⚠️ Falling back to individual chunks")
                return audio_documents

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
                # Download chunk from R2 with retry logic
                audio_url = chunk_doc["audio_url"]
                max_retries = 3
                retry_delay = 2  # seconds
                audio_data = None

                for attempt in range(max_retries):
                    try:
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            response = await client.get(audio_url)
                            response.raise_for_status()
                            audio_data = response.content
                        break  # Success, exit retry loop
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code in [502, 503, 504]:  # Server errors
                            if attempt < max_retries - 1:
                                logger.warning(
                                    f"⚠️ Server error {e.response.status_code} downloading chunk {chunk_idx}, "
                                    f"retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})"
                                )
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                            else:
                                logger.error(
                                    f"❌ Failed after {max_retries} retries: {e}"
                                )
                                raise
                        else:
                            raise  # Non-retryable error (4xx, etc.)

                if not audio_data:
                    raise ValueError(
                        f"Failed to download chunk {chunk_idx} after {max_retries} attempts"
                    )

                # Validate audio data
                if len(audio_data) < 100:
                    raise ValueError(
                        f"Chunk {chunk_idx} has invalid audio data (size: {len(audio_data)} bytes)"
                    )

                # Load audio segment (WAV format)
                audio_segment = AudioSegment.from_wav(io.BytesIO(audio_data))

                # ✅ FIX: Recalculate timestamps based on actual audio duration
                # Chunk timestamps are AI predictions (from word count), NOT actual TTS output
                chunk_timestamps = chunk_doc.get("slide_timestamps", [])
                actual_chunk_duration = len(audio_segment) / 1000.0  # seconds

                if chunk_timestamps:
                    # Get predicted chunk duration from last timestamp
                    predicted_chunk_duration = chunk_timestamps[-1]["end_time"]

                    # Calculate scale factor to match actual audio
                    scale_factor = (
                        actual_chunk_duration / predicted_chunk_duration
                        if predicted_chunk_duration > 0
                        else 1.0
                    )

                    logger.info(
                        f"   📏 Chunk {chunk_idx}: predicted={predicted_chunk_duration:.1f}s, "
                        f"actual={actual_chunk_duration:.1f}s, scale={scale_factor:.3f}"
                    )

                    # Scale timestamps to match actual audio duration
                    for ts in chunk_timestamps:
                        scaled_start = ts["start_time"] * scale_factor
                        scaled_end = ts["end_time"] * scale_factor

                        global_timestamps.append(
                            {
                                "slide_index": ts["slide_index"],
                                "start_time": current_time + scaled_start,
                                "end_time": current_time + scaled_end,
                            }
                        )

                # Append to combined audio
                combined_audio += audio_segment
                current_time += actual_chunk_duration

                logger.info(
                    f"   ✅ Merged chunk {chunk_idx + 1}/{len(audio_documents)}"
                )

            # Export merged audio
            logger.info("   💾 Exporting merged audio...")
            output_buffer = io.BytesIO()
            combined_audio.export(output_buffer, format="wav")
            merged_audio_data = output_buffer.getvalue()

            # Upload to R2 and library
            file_name = f"narration_{presentation_id}_{language}_v{version}_merged.wav"
            r2_key = f"narration/{user_id}/{presentation_id}/{file_name}"

            upload_result = await self.r2_service.upload_file(
                file_content=merged_audio_data,
                r2_key=r2_key,
                content_type="audio/wav",
            )
            audio_url = upload_result["public_url"]

            # Save to library
            library_audio = self.library_manager.save_library_file(
                user_id=user_id,
                filename=file_name,
                file_type="audio",
                category="audio",
                r2_url=audio_url,
                r2_key=r2_key,
                file_size=len(merged_audio_data),
                mime_type="audio/wav",
                metadata={
                    "source_type": "slide_narration_merged",
                    "presentation_id": presentation_id,
                    "subtitle_id": subtitle_id,
                    "language": language,
                    "version": version,
                    "total_slides": len(global_timestamps),
                    "total_duration_seconds": current_time,
                },
            )

            # Create merged audio document
            merged_doc = {
                "user_id": user_id,
                "presentation_id": presentation_id,
                "subtitle_id": subtitle_id,
                "language": language,
                "version": version,
                "slide_index": -1,  # -1 indicates merged/full presentation audio
                "audio_url": audio_url,
                "audio_type": "merged_presentation",
                "chunk_index": 0,
                "total_chunks": 1,
                "slide_count": len(global_timestamps),
                "slide_timestamps": global_timestamps,
                "audio_metadata": {
                    "duration_seconds": len(combined_audio) / 1000.0,
                    "file_size_bytes": len(merged_audio_data),
                    "format": "wav",
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
            # Don't return chunks here - raise to let caller handle fallback
            raise Exception(f"Audio merge failed: {str(e)}")

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
