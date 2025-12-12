"""
Gemini Audio Listening Test Service (Phase 8)
Use Gemini 3 Pro Preview Audio Understanding API for audio file-based listening tests
- User uploads audio file (mp3, m4a, wav)
- Upload to Gemini File API
- Transcribe audio with speaker diarization
- Generate questions in ONE API call
- Support timestamps and emotion detection
"""

import logging
import json
import uuid
import re
import os
import tempfile
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from google import genai
from google.genai import types
import config.config as config

logger = logging.getLogger("chatbot")


class GeminiAudioListeningTestService:
    """Generate listening test from audio file using Gemini 3 Pro Preview Audio"""

    def __init__(self):
        """Initialize Gemini client"""
        self.gemini_api_key = config.GEMINI_API_KEY
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        self.client = genai.Client(api_key=self.gemini_api_key)
        self.model = "gemini-3-pro-preview"  # Latest model with audio understanding

    def _validate_audio_file(self, file_path: str) -> bool:
        """Check if file is valid audio file"""
        if not os.path.exists(file_path):
            return False

        # Check file extension
        valid_extensions = (".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac")
        return file_path.lower().endswith(valid_extensions)

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
You MUST generate EXACTLY {num_questions} questions. Each question type has SPECIFIC REQUIRED FIELDS:

### 1. MCQ (Multiple Choice)
**REQUIRED FIELDS:**
- `question_type`: "mcq"
- `question_text`: Full question text
- `instructions`: "Choose the correct letter, A, B, C or D"
- `options`: Array with EXACTLY 4 options (A, B, C, D)
  - Each option: `{{"option_key": "A", "option_text": "..."}}`
- `correct_answer_keys`: Array of correct keys, e.g., ["B"]
- `timestamp_hint`: "MM:SS-MM:SS"
- `explanation`: Why this answer

### 2. COMPLETION (Fill in Blanks)
**REQUIRED FIELDS:**
- `question_type`: "completion"
- `question_text`: Context/title (e.g., "Complete the registration form")
- `instructions`: "Write NO MORE THAN TWO WORDS AND/OR A NUMBER for each answer"
- `template`: Text with _____(1)_____, _____(2)_____ placeholders
  - Example: "Name: _____(1)_____\\nPhone: _____(2)_____"
- `blanks`: Array of blank definitions
  - Each: `{{"key": "1", "position": "Name", "word_limit": 2}}`
- `correct_answers`: Array of answer sets
  - Each: `{{"blank_key": "1", "answers": ["John Smith", "john smith"]}}`
- `timestamp_hint`: "MM:SS-MM:SS"
- `explanation`: Context from audio

### 3. MATCHING (Match Items)
**REQUIRED FIELDS:**
- `question_type`: "matching"
- `question_text`: "Match each [item] to its [attribute]"
- `instructions`: "Write the correct letter A-E next to questions 1-3"
- `left_items`: Array of items to match (numbered keys)
  - Each: `{{"key": "1", "text": "Item description"}}`
- `right_options`: Array of options (letter keys, MORE than left items)
  - Each: `{{"key": "A", "text": "Option text"}}`
- `correct_matches`: Array of correct pairs
  - Each: `{{"left_key": "1", "right_key": "B"}}`
- `timestamp_hint`: "MM:SS-MM:SS"
- `explanation`: Why these matches

### 4. SENTENCE COMPLETION
**REQUIRED FIELDS:**
- `question_type`: "sentence_completion"
- `question_text`: "Complete the sentences below"
- `instructions`: "Write NO MORE THAN TWO WORDS for each answer"
- `sentences`: Array of incomplete sentences
  - Each: `{{
      "key": "1",
      "template": "The library opens at _____.",
      "word_limit": 2,
      "correct_answers": ["8 AM", "8:00 AM", "eight o'clock"]
    }}`
- `timestamp_hint`: "MM:SS-MM:SS"
- `explanation`: Context

### 5. SHORT ANSWER
**REQUIRED FIELDS:**
- `question_type`: "short_answer"
- `question_text`: "Answer the questions"
- `instructions`: "Write NO MORE THAN THREE WORDS for each answer"
- `questions`: Array of questions
  - Each: `{{
      "key": "1",
      "text": "What is the speaker's occupation?",
      "word_limit": 3,
      "correct_answers": ["software engineer", "Software Engineer"]
    }}`
- `timestamp_hint`: "MM:SS-MM:SS"
- `explanation`: Context

---

## OUTPUT FORMAT

Return ONLY valid JSON (no markdown, no extra text). Here's a COMPLETE EXAMPLE showing ALL 5 question types:

{{
  "audio_summary": "Conversation between a student and librarian about library membership registration and available facilities.",
  "duration_seconds": 120,
  "num_speakers": 2,
  "transcript": {{
    "speaker_roles": ["Student", "Librarian"],
    "segments": [
      {{
        "speaker_index": 0,
        "timestamp": "00:00 - 00:05",
        "text": "Hi, I'd like to register for a library card.",
        "emotion": "neutral"
      }},
      {{
        "speaker_index": 1,
        "timestamp": "00:05 - 00:12",
        "text": "Sure! Can I have your name and student ID?",
        "emotion": "happy"
      }},
      {{
        "speaker_index": 0,
        "timestamp": "00:12 - 00:18",
        "text": "My name is John Smith and my ID is A12345.",
        "emotion": "neutral"
      }}
    ]
  }},
  "questions": [
    {{
      "question_id": "q1",
      "question_type": "mcq",
      "question_text": "What is the main purpose of the conversation?",
      "instructions": "Choose the correct letter, A, B, C or D",
      "options": [
        {{"option_key": "A", "option_text": "To borrow books"}},
        {{"option_key": "B", "option_text": "To register for a library card"}},
        {{"option_key": "C", "option_text": "To return books"}},
        {{"option_key": "D", "option_text": "To ask for directions"}}
      ],
      "correct_answer_keys": ["B"],
      "timestamp_hint": "00:00-00:10",
      "explanation": "Student explicitly states wanting to register for a library card."
    }},
    {{
      "question_id": "q2",
      "question_type": "completion",
      "question_text": "Complete the registration form",
      "instructions": "Write NO MORE THAN TWO WORDS AND/OR A NUMBER for each answer",
      "template": "Name: _____(1)_____\\nStudent ID: _____(2)_____\\nPhone: _____(3)_____",
      "blanks": [
        {{"key": "1", "position": "Name", "word_limit": 2}},
        {{"key": "2", "position": "Student ID", "word_limit": 3}},
        {{"key": "3", "position": "Phone", "word_limit": 3}}
      ],
      "correct_answers": [
        {{"blank_key": "1", "answers": ["John Smith", "john smith", "JOHN SMITH"]}},
        {{"blank_key": "2", "answers": ["A12345", "a12345", "A 12345"]}},
        {{"blank_key": "3", "answers": ["0412 555 678", "0412555678"]}}
      ],
      "timestamp_hint": "00:10-00:30",
      "explanation": "Student provides personal details during registration."
    }},
    {{
      "question_id": "q3",
      "question_type": "matching",
      "question_text": "Match each facility to its location",
      "instructions": "Write the correct letter A-E next to questions 1-3",
      "left_items": [
        {{"key": "1", "text": "Reading room"}},
        {{"key": "2", "text": "Computer lab"}},
        {{"key": "3", "text": "Study rooms"}}
      ],
      "right_options": [
        {{"key": "A", "text": "Ground floor"}},
        {{"key": "B", "text": "First floor"}},
        {{"key": "C", "text": "Second floor"}},
        {{"key": "D", "text": "Third floor"}},
        {{"key": "E", "text": "Basement"}}
      ],
      "correct_matches": [
        {{"left_key": "1", "right_key": "B"}},
        {{"left_key": "2", "right_key": "B"}},
        {{"left_key": "3", "right_key": "C"}}
      ],
      "timestamp_hint": "00:45-01:10",
      "explanation": "Librarian describes locations of various facilities."
    }},
    {{
      "question_id": "q4",
      "question_type": "sentence_completion",
      "question_text": "Complete the sentences below",
      "instructions": "Write NO MORE THAN TWO WORDS for each answer",
      "sentences": [
        {{
          "key": "1",
          "template": "The library's opening hours on weekdays are from _____.",
          "word_limit": 2,
          "correct_answers": ["8 AM", "8:00 AM", "eight o'clock"]
        }},
        {{
          "key": "2",
          "template": "Members can borrow a maximum of _____ books.",
          "word_limit": 2,
          "correct_answers": ["5 books", "five books", "5"]
        }}
      ],
      "timestamp_hint": "01:20-01:40",
      "explanation": "Librarian mentions operating hours and borrowing limits."
    }},
    {{
      "question_id": "q5",
      "question_type": "short_answer",
      "question_text": "Answer the questions",
      "instructions": "Write NO MORE THAN THREE WORDS for each answer",
      "questions": [
        {{
          "key": "1",
          "text": "What type of card is being issued?",
          "word_limit": 3,
          "correct_answers": ["library card", "student library card", "Library Card"]
        }},
        {{
          "key": "2",
          "text": "What floor is the computer lab on?",
          "word_limit": 3,
          "correct_answers": ["first floor", "First Floor", "1st floor"]
        }}
      ],
      "timestamp_hint": "01:50-02:00",
      "explanation": "Context from the entire conversation."
    }}
  ]
}}

---

## VALIDATION CHECKLIST (VERIFY BEFORE RETURNING)

Before submitting your JSON, verify each point:

✅ **Question Count:**
   - Total questions in "questions" array = {num_questions}

✅ **MCQ Questions (if any):**
   - Has `options` array with EXACTLY 4 items (A, B, C, D)
   - Each option has both `option_key` and `option_text`
   - Has `correct_answer_keys` array (NOT empty)

✅ **Completion Questions (if any):**
   - Has `template` string with _____(1)_____, _____(2)_____ format
   - Has `blanks` array (matches number of blanks in template)
   - Has `correct_answers` array with `blank_key` matching blanks

✅ **Matching Questions (if any):**
   - Has `left_items` array (numbered keys: "1", "2", "3")
   - Has `right_options` array (letter keys: "A", "B", "C") - MORE options than items
   - Has `correct_matches` array with valid left_key and right_key

✅ **Sentence Completion Questions (if any):**
   - Has `sentences` array
   - Each sentence has: `key`, `template` (with _____), `word_limit`, `correct_answers` array

✅ **Short Answer Questions (if any):**
   - Has `questions` array
   - Each question has: `key`, `text`, `word_limit`, `correct_answers` array

✅ **General:**
   - All timestamps in "MM:SS-MM:SS" format
   - JSON is valid (no trailing commas, proper quotes, proper escaping)
   - All question_id values are unique

---

Now, analyze the audio file and generate the complete IELTS listening test. Return ONLY the JSON object (no markdown code blocks, no extra text)."""

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
                        properties={
                            "question_type": types.Schema(
                                type=types.Type.STRING,
                                description="Type: mcq, completion, short_answer, matching",
                            ),
                            "question_text": types.Schema(
                                type=types.Type.STRING,
                                description="The question text",
                            ),
                            "options": types.Schema(
                                type=types.Type.ARRAY,
                                description="Options for MCQ (optional)",
                                items=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "option_key": types.Schema(
                                            type=types.Type.STRING
                                        ),
                                        "option_text": types.Schema(
                                            type=types.Type.STRING
                                        ),
                                    },
                                    required=["option_key", "option_text"],
                                ),
                            ),
                            "correct_answer_keys": types.Schema(
                                type=types.Type.ARRAY,
                                description="Array of correct answers",
                                items=types.Schema(type=types.Type.STRING),
                            ),
                            "template": types.Schema(
                                type=types.Type.STRING,
                                description="Template for completion questions (optional)",
                            ),
                            "explanation": types.Schema(
                                type=types.Type.STRING,
                                description="Explanation of the answer",
                            ),
                            "audio_timestamp": types.Schema(
                                type=types.Type.STRING,
                                description="Where answer appears in audio (MM:SS)",
                            ),
                            "max_points": types.Schema(
                                type=types.Type.INTEGER,
                                description="Points for this question",
                            ),
                        },
                        required=["question_type", "question_text", "explanation"],
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

        for idx, q in enumerate(questions, 1):
            q_type = q.get("question_type")
            q_text = q.get("question_text", "")[:60]

            # Validate MCQ
            if q_type == "mcq":
                if not q.get("options") or len(q["options"]) < 2:
                    logger.warning(
                        f"❌ Question {idx} INVALID: MCQ without valid options - '{q_text}...'"
                    )
                    continue
                if not q.get("correct_answer_keys"):
                    logger.warning(
                        f"❌ Question {idx} INVALID: MCQ without correct_answer_keys - '{q_text}...'"
                    )
                    continue

            # Validate Matching
            elif q_type == "matching":
                if not q.get("left_items") or not q.get("right_options"):
                    logger.warning(
                        f"❌ Question {idx} INVALID: Matching without left/right items - '{q_text}...'"
                    )
                    continue

            # Validate Completion
            elif q_type == "completion":
                if not q.get("template") or not q.get("blanks"):
                    logger.warning(
                        f"❌ Question {idx} INVALID: Completion without template/blanks - '{q_text}...'"
                    )
                    continue

            # Validate Sentence Completion
            elif q_type == "sentence_completion":
                if not q.get("sentences"):
                    logger.warning(
                        f"❌ Question {idx} INVALID: Sentence completion without sentences - '{q_text}...'"
                    )
                    continue

            # Validate Short Answer
            elif q_type == "short_answer":
                if not q.get("questions"):
                    logger.warning(
                        f"❌ Question {idx} INVALID: Short answer without questions array - '{q_text}...'"
                    )
                    continue

            # Unknown type
            else:
                logger.warning(
                    f"❌ Question {idx} INVALID: Unknown question_type '{q_type}' - '{q_text}...'"
                )
                continue

            # Ensure question_id exists
            if "question_id" not in q:
                q["question_id"] = str(uuid.uuid4())

            logger.info(f"✅ Question {idx} VALID: {q_type} - '{q_text}...'")
            valid_questions.append(q)

        return valid_questions

    async def generate_from_audio_file(
        self,
        audio_file_path: str,
        title: Optional[str],
        language: str,
        difficulty: str,
        num_questions: int,
        user_query: str,
    ) -> Dict:
        """
        Generate listening test from audio file using Gemini Audio API

        🎯 ONE API CALL does EVERYTHING:
        - Transcribe audio with speaker diarization
        - Extract timestamps
        - Detect emotions
        - Generate questions

        Steps:
        1. Validate audio file
        2. Upload to Gemini File API
        3. Send to Gemini for processing
        4. Get structured response: transcript + questions
        5. Validate and return

        Returns:
        {
          "title": str,
          "transcript": {...},
          "questions": [...],
          "audio_url": str,
          "duration_seconds": int,
          "num_speakers": int,
          "source_type": "audio_file"
        }
        """

        logger.info(f"🎵 === AUDIO FILE LISTENING TEST GENERATION STARTED ===")
        logger.info(f"   Audio file: {audio_file_path}")
        logger.info(f"   Title: {title}")
        logger.info(f"   Language: {language}")
        logger.info(f"   Difficulty: {difficulty}")
        logger.info(f"   Num Questions: {num_questions}")
        logger.info(f"   Model: {self.model}")

        # Step 1: Validate audio file
        if not self._validate_audio_file(audio_file_path):
            logger.error(f"❌ Invalid audio file: {audio_file_path}")
            raise ValueError("Invalid audio file or unsupported format")

        logger.info(f"✅ Audio file validated successfully")

        # Step 2: Build comprehensive prompt
        prompt = self._build_audio_understanding_prompt(
            language=language,
            difficulty=difficulty,
            num_questions=num_questions,
            user_query=user_query,
        )

        # Step 3: Get file information
        try:
            file_size_bytes = os.path.getsize(audio_file_path)
            file_size_mb = file_size_bytes / (1024 * 1024)
            logger.info(f"📁 Audio file ready for upload")
            logger.info(f"   File path: {audio_file_path}")
            logger.info(
                f"   File size: {file_size_mb:.2f} MB ({file_size_bytes:,} bytes)"
            )

            # Step 4: Upload to Gemini File API
            logger.info(f"☁️ Uploading audio to Gemini File API...")
            logger.info(f"   Uploading {file_size_mb:.2f} MB to Gemini...")

            # Upload file
            audio_file = await asyncio.to_thread(
                self.client.files.upload, file=audio_file_path
            )

            logger.info(f"✅ Audio uploaded to Gemini successfully!")
            logger.info(f"   📎 Gemini File URI: {audio_file.uri}")
            logger.info(f"   🆔 File name: {audio_file.name}")

            # Step 5: Call Gemini with audio file (ONE API CALL!)
            logger.info(f"🎯 Calling Gemini {self.model} with audio...")
            logger.info(f"   Requested questions: {num_questions}")
            logger.info(f"   Audio file ready for processing...")

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part(
                                file_data=types.FileData(
                                    file_uri=audio_file.uri  # Gemini File URI
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
                "title": title or result.get("audio_summary", "Audio Listening Test"),
                "transcript": result["transcript"],
                "questions": validated_questions,
                "audio_file_path": audio_file_path,  # Return file path for later use
                "duration_seconds": result.get("duration_seconds", 0),
                "num_speakers": result.get("num_speakers", 1),
                "source_type": "audio_file",
                "audio_summary": result["audio_summary"],
            }

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse Gemini response as JSON: {e}")
            raise ValueError(f"Gemini returned invalid JSON: {e}")

        except Exception as e:
            logger.error(f"❌ Gemini Audio processing failed: {e}")
            raise

    async def _download_youtube_audio(self, youtube_url: str) -> str:
        """
        Download audio from YouTube URL using yt-dlp

        Returns:
            Path to downloaded audio file (mp3)
        """
        try:
            import yt_dlp

            # Create temp file
            temp_dir = tempfile.gettempdir()
            temp_filename = f"yt_audio_{uuid.uuid4().hex}"
            output_template = os.path.join(temp_dir, temp_filename)

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": output_template,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "128",
                    }
                ],
                "quiet": True,
                "no_warnings": True,
                # Add headers to avoid bot detection
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-us,en;q=0.5",
                    "Sec-Fetch-Mode": "navigate",
                },
            }

            # Check for cookies file
            cookies_path = os.path.join(
                os.getcwd(), "data", "www.youtube.com_cookies.txt"
            )
            if os.path.exists(cookies_path):
                logger.info(f"🍪 Using YouTube cookies from: {cookies_path}")
                ydl_opts["cookiefile"] = cookies_path
            else:
                logger.warning(f"⚠️ YouTube cookies file not found at: {cookies_path}")
                logger.info(
                    "💡 Tip: Export cookies from browser using extension like 'Get cookies.txt LOCALLY'"
                )

            # Download in thread pool to avoid blocking
            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])
                return f"{output_template}.mp3"

            audio_path = await asyncio.to_thread(download)

            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Failed to download audio from {youtube_url}")

            return audio_path

        except ImportError:
            raise ImportError("yt-dlp not installed. Run: pip install yt-dlp")
        except Exception as e:
            logger.error(f"Failed to download YouTube audio: {e}")
            raise


# Singleton instance
_gemini_audio_service = None


def get_gemini_audio_listening_service() -> GeminiAudioListeningTestService:
    """Get singleton instance"""
    global _gemini_audio_service
    if _gemini_audio_service is None:
        _gemini_audio_service = GeminiAudioListeningTestService()
    return _gemini_audio_service
