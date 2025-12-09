"""
Listening Test Generator Service
Generate listening tests with TTS audio using Gemini AI
Now supports 6 IELTS question types
"""

import logging
import json
import asyncio
import uuid
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime
from bson import ObjectId

from google import genai
from google.genai import types
import config.config as config

from src.services.google_tts_service import GoogleTTSService
from src.services.r2_storage_service import R2StorageService
from src.services.library_manager import LibraryManager
from src.services.online_test_utils import get_mongodb_service
from src.services.ielts_question_schemas import (
    get_ielts_question_schema,
    get_ielts_prompt,
)

logger = logging.getLogger(__name__)


class ListeningTestGeneratorService:
    """Generate listening comprehension tests with audio"""

    def __init__(self):
        """Initialize services"""
        self.gemini_api_key = config.GEMINI_API_KEY
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        self.client = genai.Client(api_key=self.gemini_api_key)
        self.google_tts = GoogleTTSService()
        self.r2_service = R2StorageService()
        mongo_service = get_mongodb_service()
        self.library_manager = LibraryManager(
            db=mongo_service.db, s3_client=self.r2_service.s3_client
        )

    def _build_listening_prompt(
        self,
        language: str,
        topic: str,
        difficulty: str,
        num_questions: int,
        num_audio_sections: int,
        num_speakers: int,
        user_query: str,
    ) -> str:
        """Build prompt for listening test generation"""

        difficulty_map = {
            "easy": "EASY: Simple vocabulary, clear pronunciation, slow pace",
            "medium": "MEDIUM: Moderate vocabulary, natural pace, some idioms",
            "hard": "HARD: Advanced vocabulary, fast pace, complex structures",
        }
        difficulty_desc = difficulty_map.get(difficulty, difficulty_map["medium"])

        speaker_instruction = ""
        if num_speakers == 1:
            speaker_instruction = "Generate a MONOLOGUE (single speaker)."
        elif num_speakers == 2:
            speaker_instruction = "Generate a DIALOGUE (two speakers). Alternate between speakers naturally. Include speaker roles (e.g., Customer/Agent, Student/Teacher)."

        prompt = f"""You are an expert in creating listening comprehension tests (IELTS/TOEFL-style).

**TASK:** Generate a listening test with audio scripts and multiple-choice questions.

**SPECIFICATIONS:**
- Language: {language}
- Topic: {topic}
- Difficulty: {difficulty_desc}
- Number of speakers: {num_speakers}
- Number of audio sections: {num_audio_sections}
- Number of questions: {num_questions} (distribute across sections)
- User requirements: {user_query}

**SPEAKER CONFIGURATION:**
{speaker_instruction}

**OUTPUT FORMAT (JSON):**
{{
  "audio_sections": [
    {{
      "section_number": 1,
      "section_title": "Conversation at Travel Agency",
      "script": {{
        "speaker_roles": ["Customer", "Travel Agent"],
        "lines": [
          {{"speaker": 0, "text": "Good morning, I'd like to book a flight to Paris."}},
          {{"speaker": 1, "text": "Of course! When would you like to travel?"}}
        ]
      }},
      "questions": [
        {{
          "question_text": "What destination does the customer want to visit?",
          "options": [
            {{"option_key": "A", "option_text": "London"}},
            {{"option_key": "B", "option_text": "Paris"}},
            {{"option_key": "C", "option_text": "Rome"}},
            {{"option_key": "D", "option_text": "Berlin"}}
          ],
          "correct_answer_keys": ["B"],
          "timestamp_hint": "0:05-0:08",
          "explanation": "The customer says 'I'd like to book a flight to Paris' at the beginning."
        }}
      ]
    }}
  ]
}}

**CRITICAL INSTRUCTIONS:**
1. Your output MUST be valid JSON.
2. Generate exactly {num_audio_sections} audio sections.
3. Distribute {num_questions} questions across sections.
4. Script lines must be natural and conversational.
5. Each question must be answerable from audio only.
6. Include timestamp hints for each question (approximate time in audio).
7. Mix question types: detail questions, main idea, inference.
8. Ensure logical flow in conversation/monologue.
9. All content in {language} language.
10. VALIDATE your JSON output before returning.

Now, generate the listening test. Return ONLY the JSON object, no additional text."""

        return prompt

    async def _generate_script_and_questions(
        self,
        language: str,
        topic: str,
        difficulty: str,
        num_questions: int,
        num_audio_sections: int,
        num_speakers: int,
        user_query: str,
    ) -> Dict:
        """Step 1: Generate script and questions using Gemini with IELTS question types"""

        # Use new IELTS prompt supporting 6 question types
        prompt = get_ielts_prompt(
            language=language,
            topic=topic,
            difficulty=difficulty,
            num_questions=num_questions,
            num_audio_sections=num_audio_sections,
            num_speakers=num_speakers,
            user_query=user_query,
        )

        # Use new IELTS schema supporting 6 question types
        response_schema = get_ielts_question_schema()

        logger.info(
            f"📡 Calling Gemini API (gemini-3-pro-preview) for IELTS test with {num_questions} questions across {num_audio_sections} sections..."
        )
        logger.info(
            f"   Supported question types: MCQ, Matching, Map Labeling, Completion, Sentence Completion, Short Answer"
        )
        import sys

        sys.stdout.flush()

        response = self.client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                max_output_tokens=25000,
                temperature=0.4,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )

        result = json.loads(response.text)

        # Convert Gemini array format to object format for storage
        self._convert_gemini_arrays_to_objects(result)

        # Count total questions after validation
        total_questions = sum(
            len(s.get("questions", [])) for s in result["audio_sections"]
        )

        logger.info(
            f"✅ Generated {len(result['audio_sections'])} audio sections with {total_questions} valid questions"
        )

        # Check if we have enough questions (allow 80% threshold)
        min_required = int(num_questions * 0.8)  # At least 80% of requested
        if total_questions < min_required:
            logger.error(
                f"❌ Insufficient questions: got {total_questions}, expected at least {min_required} (80% of {num_questions})"
            )
            raise ValueError(
                f"AI generated only {total_questions} valid questions, but {num_questions} were requested. Please try again."
            )

        if total_questions < num_questions:
            logger.warning(
                f"⚠️ Generated {total_questions} questions instead of {num_questions} (some may have been filtered out)"
            )

        return result

    def _convert_gemini_arrays_to_objects(self, result: Dict) -> None:
        """
        Convert Gemini array format to object format for MongoDB storage

        Gemini API returns:
        - correct_matches: [{left_key, right_key}]
        - correct_answers: [{blank_key, answers: []}]

        Convert to:
        - correct_matches: {"item1": "option_a", ...}
        - correct_answers: {"blank_1": ["word1", "word2"], ...}
        """
        for section in result.get("audio_sections", []):
            questions_to_keep = []
            for question in section.get("questions", []):
                # Validate and filter out broken questions
                q_type = question.get("question_type")

                # MCQ validation
                if q_type == "mcq":
                    if (
                        not question.get("options")
                        or len(question.get("options", [])) < 2
                    ):
                        logger.warning(
                            f"⚠️ Skipping broken MCQ question: {question.get('question_text', 'No text')[:50]}... - Missing or invalid options"
                        )
                        continue
                    if not question.get("correct_answer_keys"):
                        logger.warning(
                            f"⚠️ Skipping MCQ question without correct answers: {question.get('question_text', 'No text')[:50]}..."
                        )
                        continue

                # Matching validation
                elif q_type == "matching":
                    if not question.get("left_items") or not question.get(
                        "right_options"
                    ):
                        logger.warning(
                            f"⚠️ Skipping broken matching question: {question.get('question_text', 'No text')[:50]}..."
                        )
                        continue

                # Completion validation
                elif q_type == "completion":
                    if not question.get("template") or not question.get("blanks"):
                        logger.warning(
                            f"⚠️ Skipping broken completion question: {question.get('question_text', 'No text')[:50]}..."
                        )
                        continue

                # Sentence completion validation
                elif q_type == "sentence_completion":
                    if (
                        not question.get("sentences")
                        or len(question.get("sentences", [])) == 0
                    ):
                        logger.warning(
                            f"⚠️ Skipping broken sentence_completion question: {question.get('question_text', 'No text')[:50]}..."
                        )
                        continue

                # Short answer validation
                elif q_type == "short_answer":
                    if (
                        not question.get("questions")
                        or len(question.get("questions", [])) == 0
                    ):
                        logger.warning(
                            f"⚠️ Skipping broken short_answer question: {question.get('question_text', 'No text')[:50]}..."
                        )
                        continue

                # Convert correct_matches array to object
                if "correct_matches" in question and isinstance(
                    question["correct_matches"], list
                ):
                    matches_dict = {}
                    for match in question["correct_matches"]:
                        matches_dict[match["left_key"]] = match["right_key"]
                    question["correct_matches"] = matches_dict

                # Convert correct_answers array to object
                if "correct_answers" in question and isinstance(
                    question["correct_answers"], list
                ):
                    answers_dict = {}
                    for answer in question["correct_answers"]:
                        answers_dict[answer["blank_key"]] = answer["answers"]
                    question["correct_answers"] = answers_dict

                # Question passed validation
                questions_to_keep.append(question)

            # Replace questions array with validated questions
            section["questions"] = questions_to_keep
            logger.info(
                f"   ✅ Section {section.get('section_number')}: Kept {len(questions_to_keep)} valid questions"
            )

    async def _select_voices_by_gender(
        self, speaker_roles: List[str], language: str
    ) -> List[str]:
        """
        Auto-select appropriate voices based on speaker roles with gender hints

        Examples:
        - "Male Customer" → male voice
        - "Female Agent" → female voice
        - "Customer" → random voice
        """
        available_voices = await self.google_tts.get_available_voices(language)
        if not available_voices:
            return None

        # Separate by gender
        male_voices = [v for v in available_voices if v.get("gender") == "MALE"]
        female_voices = [v for v in available_voices if v.get("gender") == "FEMALE"]

        selected_voices = []
        for role in speaker_roles:
            role_lower = role.lower()

            # Check for gender keywords
            if any(
                word in role_lower
                for word in [
                    "male",
                    "man",
                    "boy",
                    "mr",
                    "sir",
                    "father",
                    "brother",
                    "son",
                ]
            ):
                # Prefer male voice
                if male_voices:
                    selected_voices.append(
                        male_voices[len(selected_voices) % len(male_voices)]["name"]
                    )
                else:
                    selected_voices.append(available_voices[0]["name"])

            elif any(
                word in role_lower
                for word in [
                    "female",
                    "woman",
                    "girl",
                    "ms",
                    "mrs",
                    "miss",
                    "lady",
                    "mother",
                    "sister",
                    "daughter",
                ]
            ):
                # Prefer female voice
                if female_voices:
                    selected_voices.append(
                        female_voices[len(selected_voices) % len(female_voices)]["name"]
                    )
                else:
                    selected_voices.append(available_voices[0]["name"])

            else:
                # No gender hint - alternate between available voices
                if male_voices and female_voices:
                    # Alternate male/female
                    if len(selected_voices) % 2 == 0 and male_voices:
                        selected_voices.append(male_voices[0]["name"])
                    elif female_voices:
                        selected_voices.append(female_voices[0]["name"])
                    else:
                        selected_voices.append(male_voices[0]["name"])
                else:
                    selected_voices.append(
                        available_voices[len(selected_voices) % len(available_voices)][
                            "name"
                        ]
                    )

        return selected_voices if selected_voices else None

    async def _generate_section_audio(
        self,
        script: Dict,
        voice_names: List[str],
        language: str,
        speaking_rate: float,
        use_pro_model: bool,
    ) -> Tuple[bytes, int]:
        """
        Step 2: Generate audio for one section

        Uses multi-speaker TTS if 2+ speakers detected

        Returns:
            Tuple of (audio_bytes, duration_seconds)
        """

        num_speakers = len(script.get("speaker_roles", []))

        logger.info(
            f"   Generating audio: {num_speakers} speaker(s), {len(script.get('lines', []))} lines"
        )

        if num_speakers > 1:
            # Use multi-speaker TTS
            audio_content, metadata = (
                await self.google_tts.generate_multi_speaker_audio(
                    script=script,
                    voice_names=voice_names,
                    language=language,
                    speaking_rate=speaking_rate,
                    use_pro_model=use_pro_model,
                )
            )
            duration_seconds = metadata.get("duration_seconds", 0)
            logger.info(
                f"   ✅ Multi-speaker audio: {len(audio_content)} bytes, ~{duration_seconds}s"
            )
        else:
            # Use single-speaker TTS
            full_text = ""
            for line in script["lines"]:
                speaker_idx = line["speaker"]
                speaker_role = script["speaker_roles"][speaker_idx]
                text = line["text"]
                full_text += f"{speaker_role}: {text}\n\n"

            voice_name = voice_names[0] if voice_names else None

            audio_content, metadata = await self.google_tts.generate_audio(
                text=full_text,
                language=language,
                voice_name=voice_name,
                speaking_rate=speaking_rate,
                use_pro_model=use_pro_model,
            )

            # Estimate duration
            word_count = len(full_text.split())
            duration_seconds = int((word_count / 150) * 60 * speaking_rate)

            logger.info(
                f"   ✅ Single-speaker audio: {len(audio_content)} bytes, ~{duration_seconds}s"
            )

        return audio_content, duration_seconds

    async def _upload_audio_to_r2(
        self,
        audio_bytes: bytes,
        creator_id: str,
        test_id: str,
        section_num: int,
    ) -> Tuple[str, str]:
        """
        Step 3: Upload audio to R2 and return URL + file_id

        Returns:
            Tuple of (public_url, library_file_id)
        """

        # Generate R2 key
        key = f"listening-tests/{creator_id}/{test_id}/section_{section_num}.wav"

        # Upload to R2
        upload_result = await self.r2_service.upload_file(
            file_content=audio_bytes,
            r2_key=key,
            content_type="audio/wav",
        )

        # Get public URL from upload result
        public_url = upload_result["public_url"]

        # Save to user library
        file_record = self.library_manager.save_library_file(
            user_id=creator_id,
            filename=f"listening_test_section_{section_num}.wav",
            file_type="audio",
            category="audio",
            r2_url=public_url,
            r2_key=key,
            file_size=len(audio_bytes),
            mime_type="audio/wav",
            metadata={
                "audio_type": "listening_test",
                "section_number": section_num,
                "test_id": test_id,
            },
        )

        library_file_id = file_record.get("library_id", file_record.get("file_id"))

        logger.info(f"   ✅ Uploaded to R2: {public_url}")

        return public_url, library_file_id

    async def generate_listening_test(
        self,
        title: str,
        description: Optional[str],
        language: str,
        topic: str,
        difficulty: str,
        num_questions: int,
        num_audio_sections: int,
        audio_config: Dict,
        user_query: str,
        time_limit_minutes: int,
        passing_score: int,
        use_pro_model: bool,
        creator_id: str,
    ) -> Dict[str, Any]:
        """
        Main method to generate complete listening test

        Returns:
        {
          "test_id": "test_123",
          "audio_sections": [...],
          "questions": [...],
          "status": "ready"
        }
        """

        try:
            # Step 1: Generate script and questions with AI
            logger.info(f"🎙️ Step 1: Generating script and questions...")
            import sys

            sys.stdout.flush()  # Force flush logs

            script_result = await self._generate_script_and_questions(
                language=language,
                topic=topic,
                difficulty=difficulty,
                num_questions=num_questions,
                num_audio_sections=num_audio_sections,
                num_speakers=audio_config.get("num_speakers", 2),
                user_query=user_query,
            )

            # Step 2: Generate audio for each section
            logger.info(
                f"🔊 Step 2: Generating audio for {num_audio_sections} sections..."
            )
            audio_sections_with_urls = []

            # Create temporary test ID (will be replaced after DB insert)
            temp_test_id = f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            for section in script_result["audio_sections"]:
                section_num = section["section_number"]
                logger.info(
                    f"   🎵 Processing section {section_num}: {section.get('section_title', 'Untitled')}..."
                )

                # Auto-select voices based on speaker roles if not provided
                voice_names = audio_config.get("voice_names")
                if not voice_names:
                    voice_names = await self._select_voices_by_gender(
                        section["script"].get("speaker_roles", []), language
                    )
                    logger.info(f"   🎙️ Auto-selected voices: {voice_names}")

                # Generate audio
                logger.info(f"   🔊 Generating audio for section {section_num}...")
                audio_bytes, duration = await self._generate_section_audio(
                    script=section["script"],
                    voice_names=voice_names,
                    language=language,
                    speaking_rate=audio_config.get("speaking_rate", 1.0),
                    use_pro_model=use_pro_model,
                )
                logger.info(
                    f"   ✅ Audio generated: {len(audio_bytes)} bytes, ~{duration}s"
                )

                # Upload to R2
                logger.info(f"   ☁️ Uploading audio to R2...")
                audio_url, file_id = await self._upload_audio_to_r2(
                    audio_bytes=audio_bytes,
                    creator_id=creator_id,
                    test_id=temp_test_id,
                    section_num=section_num,
                )
                logger.info(f"   ✅ Uploaded: {audio_url}")

                # Build transcript
                transcript_lines = []
                for line in section["script"]["lines"]:
                    speaker_idx = line["speaker"]
                    speaker_role = section["script"]["speaker_roles"][speaker_idx]
                    transcript_lines.append(f"{speaker_role}: {line['text']}")
                transcript = "\n".join(transcript_lines)

                # Add audio info to section
                section["audio_url"] = audio_url
                section["audio_file_id"] = file_id
                section["duration_seconds"] = duration
                section["transcript"] = transcript
                section["voice_config"] = {
                    "voice_names": voice_names,
                    "num_speakers": audio_config.get("num_speakers"),
                }

                audio_sections_with_urls.append(section)

            # Step 3: Flatten questions from all sections
            logger.info(f"💾 Step 3: Formatting test data...")
            questions = []
            question_num = 1

            for section in audio_sections_with_urls:
                for q in section["questions"]:
                    q["question_id"] = f"q{question_num}"  # Add unique question ID
                    q["question_number"] = question_num

                    # Don't override question_type - keep what AI generated
                    # AI now generates: mcq, matching, completion, sentence_completion, short_answer
                    if "question_type" not in q:
                        q["question_type"] = (
                            "mcq"  # Fallback for backward compatibility
                        )

                    q["audio_section"] = section["section_number"]
                    q["max_points"] = 1  # Default points, can be adjusted later
                    questions.append(q)
                    question_num += 1

            logger.info(f"✅ Listening test generated successfully!")
            logger.info(f"   - Audio sections: {len(audio_sections_with_urls)}")
            logger.info(f"   - Questions: {len(questions)}")

            # Log question type distribution
            type_counts = {}
            for q in questions:
                qtype = q.get("question_type", "unknown")
                type_counts[qtype] = type_counts.get(qtype, 0) + 1
            logger.info(f"   - Question types: {type_counts}")

            return {
                "audio_sections": audio_sections_with_urls,
                "questions": questions,
                "status": "ready",
            }

        except Exception as e:
            logger.error(f"❌ Listening test generation failed: {e}", exc_info=True)
            raise


# Singleton instance
_listening_test_generator = None


def get_listening_test_generator() -> ListeningTestGeneratorService:
    """Get singleton instance"""
    global _listening_test_generator
    if _listening_test_generator is None:
        _listening_test_generator = ListeningTestGeneratorService()
    return _listening_test_generator
