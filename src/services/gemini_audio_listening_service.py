"""
Gemini Audio Listening Test Service (Phase 8)
Use Gemini 2.5 Flash Audio Understanding API for YouTube-based listening tests
- Transcribe audio with speaker diarization
- Generate questions in ONE API call
- Support timestamps and emotion detection
"""

import logging
import json
import uuid
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

from google import genai
from google.genai import types
import config.config as config

logger = logging.getLogger(__name__)


class GeminiAudioListeningTestService:
    """Generate listening test from YouTube URL using Gemini 2.5 Flash Audio"""

    def __init__(self):
        """Initialize Gemini client"""
        self.gemini_api_key = config.GEMINI_API_KEY
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        self.client = genai.Client(api_key=self.gemini_api_key)
        self.model = "gemini-2.0-flash-exp"  # Supports audio understanding

    def _is_valid_youtube_url(self, url: str) -> bool:
        """Check if URL is valid YouTube URL"""
        youtube_regex = (
            r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/"
        )
        return re.match(youtube_regex, url) is not None

    def _build_audio_understanding_prompt(
        self,
        language: str,
        difficulty: str,
        num_questions: int,
        user_query: str,
    ) -> str:
        """
        Build comprehensive prompt for Gemini Audio Understanding
        Combines transcription + question generation in ONE prompt
        """

        difficulty_map = {
            "easy": "EASY level - simple vocabulary, clear concepts",
            "medium": "MEDIUM level - moderate vocabulary, standard complexity",
            "hard": "HARD level - advanced vocabulary, complex ideas",
        }
        difficulty_desc = difficulty_map.get(difficulty, difficulty_map["medium"])

        return f"""You are an IELTS listening test creator with audio understanding capabilities.

🎯 **YOUR TASK:** Analyze this audio and create a complete IELTS listening test.

---

## PART 1: AUDIO TRANSCRIPTION (Required)

1. **Transcribe** the entire audio accurately
2. **Identify speakers** (Speaker 1, Speaker 2, etc. or names if context allows)
3. **Add timestamps** for each segment (Format: MM:SS - MM:SS)
4. **Detect primary emotion** for each segment (choose ONE: happy, sad, angry, neutral)
5. **Provide summary** of the entire audio content (2-3 sentences)

---

## PART 2: QUESTION GENERATION (Required)

Generate **EXACTLY {num_questions} IELTS listening questions** based on the transcribed audio.

**Requirements:**
- Language: {language}
- Difficulty: {difficulty_desc}
- Question types: Mix of MCQ, Matching, Completion, Sentence Completion, Short Answer
- Questions MUST be answerable from the audio content only
- Follow IELTS standards (word limits, clear instructions)
- User requirements: {user_query}

**Distribution Guidelines (Flexible - AI decides):**
- MCQ (Multiple Choice): 30-40% (with 3-4 options each)
- Matching: 15-20% (match items/names with descriptions)
- Completion (fill blanks): 20-25% (NO MORE THAN TWO WORDS)
- Sentence Completion: 15-20% (complete sentences with key info)
- Short Answer: 10-15% (brief answers, max 3 words)

**🎯 CRITICAL REQUIREMENT:**
- You MUST generate EXACTLY {num_questions} questions
- Each question must have proper structure for its type
- MCQ must have at least 3 options + correct_answer_keys array
- Completion must have template + blanks array
- Matching must have left_items + right_options arrays
- All questions must have question_id field

---

## OUTPUT FORMAT

Return ONLY valid JSON (no markdown, no extra text):

{{
  "audio_summary": "Brief summary of audio content (2-3 sentences)",
  "duration_seconds": <estimated duration>,
  "num_speakers": <number of distinct speakers>,
  "transcript": {{
    "speaker_roles": ["Speaker 1", "Speaker 2"],
    "segments": [
      {{
        "speaker_index": 0,
        "timestamp": "00:00 - 00:15",
        "text": "Transcribed text here",
        "emotion": "neutral"
      }}
    ]
  }},
  "questions": [
    {{
      "question_id": "q1",
      "question_type": "mcq",
      "question_text": "What is the main topic?",
      "instructions": "Choose the correct answer",
      "options": [
        {{"option_key": "A", "option_text": "Option A"}},
        {{"option_key": "B", "option_text": "Option B"}},
        {{"option_key": "C", "option_text": "Option C"}}
      ],
      "correct_answer_keys": ["B"],
      "timestamp_hint": "00:10-00:20",
      "explanation": "The speaker mentions..."
    }}
  ]
}}

**VALIDATION BEFORE RETURNING:**
1. Count questions - must be EXACTLY {num_questions}
2. Check each MCQ has options + correct_answer_keys
3. Check each Completion has template + blanks
4. Check each Matching has left_items + right_options
5. Verify all timestamps are in MM:SS format
6. Ensure JSON is valid (no trailing commas, proper quotes)

Now, analyze the audio and generate the test. Return ONLY the JSON object."""

    def _get_response_schema(self) -> types.Schema:
        """
        Define structured output schema for Gemini
        Ensures consistent JSON response format
        """

        return types.Schema(
            type=types.Type.OBJECT,
            properties={
                "audio_summary": types.Schema(
                    type=types.Type.STRING,
                    description="A concise summary of the audio content (2-3 sentences)",
                ),
                "duration_seconds": types.Schema(
                    type=types.Type.INTEGER,
                    description="Estimated duration of audio in seconds",
                ),
                "num_speakers": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of distinct speakers detected",
                ),
                "transcript": types.Schema(
                    type=types.Type.OBJECT,
                    description="Structured transcript with speaker diarization",
                    properties={
                        "speaker_roles": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(type=types.Type.STRING),
                            description="List of speaker names/roles",
                        ),
                        "segments": types.Schema(
                            type=types.Type.ARRAY,
                            description="Array of transcribed segments",
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                properties={
                                    "speaker_index": types.Schema(
                                        type=types.Type.INTEGER,
                                        description="Index in speaker_roles array",
                                    ),
                                    "timestamp": types.Schema(
                                        type=types.Type.STRING,
                                        description="Time range (MM:SS - MM:SS)",
                                    ),
                                    "text": types.Schema(
                                        type=types.Type.STRING,
                                        description="Transcribed text for this segment",
                                    ),
                                    "emotion": types.Schema(
                                        type=types.Type.STRING,
                                        enum=["happy", "sad", "angry", "neutral"],
                                        description="Primary emotion detected",
                                    ),
                                },
                                required=[
                                    "speaker_index",
                                    "timestamp",
                                    "text",
                                    "emotion",
                                ],
                            ),
                        ),
                    },
                    required=["speaker_roles", "segments"],
                ),
                "questions": types.Schema(
                    type=types.Type.ARRAY,
                    description="Array of IELTS listening questions",
                    items=types.Schema(
                        type=types.Type.OBJECT,
                    ),
                ),
            },
            required=[
                "audio_summary",
                "duration_seconds",
                "num_speakers",
                "transcript",
                "questions",
            ],
        )

    def _validate_questions(self, questions: List[Dict]) -> List[Dict]:
        """
        Validate and filter generated questions
        Same validation logic as existing listening test generator
        """

        valid_questions = []

        for q in questions:
            q_type = q.get("question_type")

            # Validate MCQ
            if q_type == "mcq":
                if not q.get("options") or len(q["options"]) < 2:
                    logger.warning(f"Skipping MCQ without valid options")
                    continue
                if not q.get("correct_answer_keys"):
                    logger.warning(f"Skipping MCQ without correct_answer_keys")
                    continue

            # Validate Matching
            elif q_type == "matching":
                if not q.get("left_items") or not q.get("right_options"):
                    logger.warning(f"Skipping matching without left/right items")
                    continue

            # Validate Completion
            elif q_type == "completion":
                if not q.get("template") or not q.get("blanks"):
                    logger.warning(f"Skipping completion without template/blanks")
                    continue

            # Validate Sentence Completion
            elif q_type == "sentence_completion":
                if not q.get("sentences"):
                    logger.warning(f"Skipping sentence_completion without sentences")
                    continue

            # Validate Short Answer
            elif q_type == "short_answer":
                if not q.get("questions"):
                    logger.warning(f"Skipping short_answer without questions array")
                    continue

            # Ensure question_id exists
            if "question_id" not in q:
                q["question_id"] = str(uuid.uuid4())

            valid_questions.append(q)

        return valid_questions

    async def generate_from_youtube(
        self,
        youtube_url: str,
        title: Optional[str],
        language: str,
        difficulty: str,
        num_questions: int,
        user_query: str,
    ) -> Dict:
        """
        Generate listening test from YouTube URL using Gemini Audio API

        🎯 ONE API CALL does EVERYTHING:
        - Transcribe audio with speaker diarization
        - Extract timestamps
        - Detect emotions
        - Generate questions

        Steps:
        1. Validate YouTube URL
        2. Send URL directly to Gemini (no download needed!)
        3. Get structured response: transcript + questions
        4. Validate and return

        Returns:
        {
          "title": str,
          "transcript": {...},
          "questions": [...],
          "audio_url": youtube_url,
          "duration_seconds": int,
          "num_speakers": int,
          "source_type": "youtube"
        }
        """

        # Step 1: Validate URL
        if not self._is_valid_youtube_url(youtube_url):
            raise ValueError("Invalid YouTube URL")

        # Step 2: Build comprehensive prompt
        prompt = self._build_audio_understanding_prompt(
            language=language,
            difficulty=difficulty,
            num_questions=num_questions,
            user_query=user_query,
        )

        # Step 3: Call Gemini with YouTube URL (ONE API CALL!)
        logger.info(f"🎯 Calling Gemini 2.5 Flash with YouTube URL...")
        logger.info(f"   URL: {youtube_url}")
        logger.info(f"   Requested questions: {num_questions}")

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part(
                                file_data=types.FileData(
                                    file_uri=youtube_url  # YouTube URL directly!
                                )
                            ),
                            types.Part(text=prompt),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=self._get_response_schema(),
                    max_output_tokens=25000,
                    temperature=0.4,
                ),
            )

            # Step 4: Parse response
            result = json.loads(response.text)

            # Step 5: Validate questions
            validated_questions = self._validate_questions(result["questions"])

            logger.info(f"✅ Gemini Audio processing complete!")
            logger.info(f"   - Audio summary: {result['audio_summary'][:100]}...")
            logger.info(f"   - Duration: {result['duration_seconds']}s")
            logger.info(f"   - Speakers: {result['num_speakers']}")
            logger.info(
                f"   - Valid questions: {len(validated_questions)}/{len(result['questions'])}"
            )

            # Check minimum question count (80% threshold)
            min_required = int(num_questions * 0.8)
            if len(validated_questions) < min_required:
                raise ValueError(
                    f"Insufficient valid questions: got {len(validated_questions)}, "
                    f"expected at least {min_required} (80% of {num_questions})"
                )

            return {
                "title": title or result.get("audio_summary", "YouTube Listening Test"),
                "transcript": result["transcript"],
                "questions": validated_questions,
                "audio_url": youtube_url,  # Use YouTube URL directly
                "duration_seconds": result.get("duration_seconds", 0),
                "num_speakers": result.get("num_speakers", 1),
                "source_type": "youtube",
                "source_url": youtube_url,
                "audio_summary": result["audio_summary"],
            }

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse Gemini response as JSON: {e}")
            raise ValueError(f"Gemini returned invalid JSON: {e}")

        except Exception as e:
            logger.error(f"❌ Gemini Audio processing failed: {e}", exc_info=True)
            raise


# Singleton instance
_gemini_audio_service = None


def get_gemini_audio_listening_service() -> GeminiAudioListeningTestService:
    """Get singleton instance"""
    global _gemini_audio_service
    if _gemini_audio_service is None:
        _gemini_audio_service = GeminiAudioListeningTestService()
    return _gemini_audio_service
