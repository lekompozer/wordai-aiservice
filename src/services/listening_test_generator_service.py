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

        questions_per_section = num_questions // num_audio_sections
        remainder = num_questions % num_audio_sections

        logger.info(
            f"📡 Calling Gemini API (gemini-3-pro-preview) for IELTS test with {num_questions} questions across {num_audio_sections} sections..."
        )
        logger.info(
            f"   Target distribution: ~{questions_per_section} questions per section (total must be exactly {num_questions})"
        )
        logger.info(
            f"   Supported question types: MCQ, Matching, Completion, Sentence Completion, Short Answer (5 types)"
        )
        import sys
        import asyncio

        sys.stdout.flush()

        # Run blocking Gemini API call in thread pool to avoid blocking event loop
        response = await asyncio.to_thread(
            self.client.models.generate_content,
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

        # Validate gender diversity for 2-speaker sections
        if num_speakers == 2:
            self._validate_gender_diversity(result["audio_sections"])

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

    def _validate_gender_diversity(self, audio_sections: List[Dict]) -> None:
        """
        Validate that each 2-speaker section has different genders (one male + one female)

        This ensures Gemini TTS can generate distinct voices.
        Same-gender pairs will sound identical!
        """
        male_keywords = [
            "male",
            "man",
            "men",
            "boy",
            "mr",
            "sir",
            "gentleman",
            "father",
            "dad",
            "brother",
            "son",
            "husband",
            "him",
            "he",
        ]
        female_keywords = [
            "female",
            "woman",
            "women",
            "girl",
            "ms",
            "mrs",
            "miss",
            "lady",
            "mother",
            "mom",
            "sister",
            "daughter",
            "wife",
            "her",
            "she",
        ]

        for section in audio_sections:
            section_num = section.get("section_number", "unknown")
            speaker_roles = section.get("script", {}).get("speaker_roles", [])

            if len(speaker_roles) != 2:
                continue  # Only validate 2-speaker dialogues

            # Detect gender for each speaker
            genders = []
            for role in speaker_roles:
                role_lower = role.lower()

                # Use word boundary check to match whole words only
                # This prevents "male" from matching inside "female"
                import re

                is_male = any(
                    re.search(rf"\b{re.escape(word)}\b", role_lower)
                    for word in male_keywords
                )
                is_female = any(
                    re.search(rf"\b{re.escape(word)}\b", role_lower)
                    for word in female_keywords
                )

                if is_male:
                    genders.append("male")
                elif is_female:
                    genders.append("female")
                else:
                    genders.append("unknown")

            # Check if both speakers have same gender
            if genders[0] == genders[1] and genders[0] != "unknown":
                logger.warning(
                    f"⚠️ Section {section_num} has SAME-GENDER speakers: {speaker_roles} → voices will sound identical!"
                )
                logger.warning(
                    f"   Detected genders: {genders[0]}/{genders[1]} - This will confuse listeners!"
                )

                # Auto-fix: change second speaker to opposite gender
                if genders[0] == "male":
                    # Change second speaker from Male to Female
                    original_role = speaker_roles[1]
                    fixed_role = (
                        original_role.replace("Male", "Female")
                        .replace("male", "female")
                        .replace("Man", "Woman")
                        .replace("man", "woman")
                    )
                    speaker_roles[1] = fixed_role
                    logger.info(f"   🔧 Auto-fixed: '{original_role}' → '{fixed_role}'")
                else:
                    # Change second speaker from Female to Male
                    original_role = speaker_roles[1]
                    fixed_role = (
                        original_role.replace("Female", "Male")
                        .replace("female", "male")
                        .replace("Woman", "Man")
                        .replace("woman", "man")
                    )
                    speaker_roles[1] = fixed_role
                    logger.info(f"   🔧 Auto-fixed: '{original_role}' → '{fixed_role}'")

            elif "unknown" in genders:
                logger.warning(
                    f"⚠️ Section {section_num} has ambiguous gender in roles: {speaker_roles}"
                )
                logger.info(
                    f"   Detected genders: {genders[0]}/{genders[1]} - will use alternating male/female voices"
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

            # Check for gender keywords (expanded list for better detection)
            male_keywords = [
                "male",
                "man",
                "men",
                "boy",
                "mr",
                "sir",
                "gentleman",
                "gentlemen",
                "father",
                "dad",
                "brother",
                "son",
                "uncle",
                "grandfather",
                "husband",
                "him",
                "he",
                "his",
            ]
            female_keywords = [
                "female",
                "woman",
                "women",
                "girl",
                "ms",
                "mrs",
                "miss",
                "lady",
                "ladies",
                "mother",
                "mom",
                "sister",
                "daughter",
                "aunt",
                "grandmother",
                "wife",
                "her",
                "she",
            ]

            # Use word boundary check to match whole words only
            import re

            is_male = any(
                re.search(rf"\b{re.escape(word)}\b", role_lower)
                for word in male_keywords
            )
            is_female = any(
                re.search(rf"\b{re.escape(word)}\b", role_lower)
                for word in female_keywords
            )

            if is_male:
                # Prefer male voice
                if male_voices:
                    selected_voices.append(
                        male_voices[len(selected_voices) % len(male_voices)]["name"]
                    )
                else:
                    selected_voices.append(available_voices[0]["name"])
                logger.info(f"   👨 Detected male role: {role}")

            elif is_female:
                # Prefer female voice
                if female_voices:
                    selected_voices.append(
                        female_voices[len(selected_voices) % len(female_voices)]["name"]
                    )
                else:
                    selected_voices.append(available_voices[0]["name"])
                logger.info(f"   👩 Detected female role: {role}")

            else:
                # No gender hint - FORCE alternating male/female to ensure differentiation
                # IMPORTANT: Alternate based on CURRENT position, not fixed Male=0
                if male_voices and female_voices:
                    current_position = len(selected_voices)

                    # For 2-speaker dialogues, we need to ensure male/female alternation
                    # But we should NOT assume Male is always first!
                    # Instead, we alternate: even positions get one gender, odd get the other
                    if len(speaker_roles) == 2:
                        # Check if the OTHER speaker has gender hint
                        other_index = 1 - current_position  # 0→1, 1→0
                        if other_index < len(speaker_roles):
                            other_role_lower = speaker_roles[other_index].lower()
                            import re

                            other_is_male = any(
                                re.search(rf"\b{re.escape(word)}\b", other_role_lower)
                                for word in male_keywords
                            )
                            other_is_female = any(
                                re.search(rf"\b{re.escape(word)}\b", other_role_lower)
                                for word in female_keywords
                            )

                            # If other speaker is male, this one should be female (and vice versa)
                            if other_is_male:
                                selected_voices.append(female_voices[0]["name"])
                                logger.info(
                                    f"   👩 No gender detected for '{role}', assigning FEMALE (other speaker is male)"
                                )
                            elif other_is_female:
                                selected_voices.append(male_voices[0]["name"])
                                logger.info(
                                    f"   👨 No gender detected for '{role}', assigning MALE (other speaker is female)"
                                )
                            else:
                                # Both unknown - use alternating pattern
                                if current_position % 2 == 0:
                                    selected_voices.append(male_voices[0]["name"])
                                    logger.info(
                                        f"   👨 No gender detected for '{role}', assigning MALE (position {current_position})"
                                    )
                                else:
                                    selected_voices.append(female_voices[0]["name"])
                                    logger.info(
                                        f"   👩 No gender detected for '{role}', assigning FEMALE (position {current_position})"
                                    )
                        else:
                            # Fallback: alternate
                            if current_position % 2 == 0:
                                selected_voices.append(male_voices[0]["name"])
                                logger.info(
                                    f"   👨 No gender detected for '{role}', assigning MALE (fallback)"
                                )
                            else:
                                selected_voices.append(female_voices[0]["name"])
                                logger.info(
                                    f"   👩 No gender detected for '{role}', assigning FEMALE (fallback)"
                                )
                    else:
                        # Single speaker or >2 speakers: simple alternation
                        if current_position % 2 == 0:
                            selected_voices.append(male_voices[0]["name"])
                            logger.info(
                                f"   👨 No gender detected for '{role}', assigning MALE (position {current_position})"
                            )
                        else:
                            selected_voices.append(female_voices[0]["name"])
                            logger.info(
                                f"   👩 No gender detected for '{role}', assigning FEMALE (position {current_position})"
                            )
                else:
                    selected_voices.append(
                        available_voices[len(selected_voices) % len(available_voices)][
                            "name"
                        ]
                    )
                    logger.info(
                        f"   🎙️ No gender voices available for '{role}', using default"
                    )

        return selected_voices if selected_voices else None

    async def _generate_section_audio(
        self,
        script: Dict,
        voice_names: List[str],
        language: str,
        speaking_rate: float,
        use_pro_model: bool,
        force_num_speakers: Optional[int] = None,
    ) -> Tuple[bytes, int]:
        """
        Step 2: Generate audio for one section

        Uses multi-speaker TTS only if:
        1. Script has 2+ speaker_roles
        2. force_num_speakers is None OR > 1

        Args:
            force_num_speakers: If provided, override script's num_speakers (from audio_config)

        Returns:
            Tuple of (audio_bytes, duration_seconds)
        """

        script_num_speakers = len(script.get("speaker_roles", []))

        # Use force_num_speakers if provided (from audio_config), otherwise use script's num_speakers
        effective_num_speakers = (
            force_num_speakers
            if force_num_speakers is not None
            else script_num_speakers
        )

        logger.info(
            f"   Generating audio: script has {script_num_speakers} speaker(s), config requires {effective_num_speakers} speaker(s), {len(script.get('lines', []))} lines"
        )

        # Use multi-speaker TTS only if:
        # 1. Script has 2+ speakers AND
        # 2. Config allows 2+ speakers (or no config restriction)
        if script_num_speakers > 1 and effective_num_speakers > 1:
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

    def _parse_user_transcript(
        self,
        transcript_text: str,
        num_speakers: int,
        language: str,
    ) -> Dict:
        """
        Parse user-provided transcript text to structured format

        Supports formats:
        1. Plain text (single speaker)
        2. "Speaker 1: text\nSpeaker 2: text" format
        3. "A: text\nB: text" format

        Returns structured script for TTS
        """

        lines_parsed = []
        speaker_roles = []

        # Try to detect speaker format
        text_lines = transcript_text.strip().split("\n")

        # Check if format has speaker labels (e.g., "Speaker 1:" or "A:")
        has_speaker_labels = any(":" in line for line in text_lines)

        if has_speaker_labels and num_speakers > 1:
            # Parse with speaker labels
            current_speaker_map = {}  # Map speaker label to index

            for line in text_lines:
                line = line.strip()
                if not line or ":" not in line:
                    continue

                parts = line.split(":", 1)
                if len(parts) != 2:
                    continue

                speaker_label = parts[0].strip()
                text = parts[1].strip()

                # Map speaker to index
                if speaker_label not in current_speaker_map:
                    if len(current_speaker_map) >= num_speakers:
                        # Reuse existing speakers
                        speaker_idx = len(current_speaker_map) % num_speakers
                    else:
                        speaker_idx = len(current_speaker_map)
                        current_speaker_map[speaker_label] = speaker_idx
                        speaker_roles.append(speaker_label)
                else:
                    speaker_idx = current_speaker_map[speaker_label]

                lines_parsed.append({"speaker": speaker_idx, "text": text})
        else:
            # Plain text or single speaker
            if num_speakers == 1:
                speaker_roles = ["Speaker"]
                for line in text_lines:
                    line = line.strip()
                    if line:
                        lines_parsed.append({"speaker": 0, "text": line})
            else:
                # Split into 2 speakers alternating
                speaker_roles = ["Speaker 1", "Speaker 2"]
                for idx, line in enumerate(text_lines):
                    line = line.strip()
                    if line:
                        lines_parsed.append({"speaker": idx % 2, "text": line})

        # Fallback if no speakers detected
        if not speaker_roles:
            speaker_roles = (
                ["Speaker"] if num_speakers == 1 else ["Speaker 1", "Speaker 2"]
            )

        logger.info(
            f"   Parsed transcript: {len(lines_parsed)} lines, {len(speaker_roles)} speakers"
        )

        return {"speaker_roles": speaker_roles, "lines": lines_parsed}

    async def _generate_questions_from_transcript(
        self,
        script: Dict,
        language: str,
        difficulty: str,
        num_questions: int,
        user_query: str,
    ) -> List[Dict]:
        """
        Generate questions from user-provided transcript using Gemini

        Similar to _generate_script_and_questions but only generates questions
        (script is already provided by user)
        """

        # Convert script to readable text for prompt
        transcript_lines = []
        for line in script["lines"]:
            speaker_role = script["speaker_roles"][line["speaker"]]
            transcript_lines.append(f"{speaker_role}: {line['text']}")
        transcript_text = "\n".join(transcript_lines)

        prompt = f"""You are an IELTS listening test creator. Generate {num_questions} questions based on the following transcript.

**TRANSCRIPT:**
{transcript_text}

**REQUIREMENTS:**
- Generate EXACTLY {num_questions} questions
- Mix question types: MCQ, Matching, Completion, Sentence Completion, Short Answer
- Questions MUST be answerable from the transcript only
- Difficulty: {difficulty}
- Language: {language}
- User requirements: {user_query}

**DISTRIBUTION (Flexible - AI decides):**
- MCQ: 30-40% (with 3-4 options each)
- Matching: 15-20%
- Completion: 20-25% (NO MORE THAN TWO WORDS)
- Sentence Completion: 15-20%
- Short Answer: 10-15% (max 3 words)

**OUTPUT FORMAT:** JSON array of questions

**CRITICAL:**
- MUST generate EXACTLY {num_questions} questions
- Each question must have proper structure
- MCQ needs: options + correct_answer_keys
- Matching needs: left_items + right_options
- Completion needs: template + blanks

Return ONLY the questions array in JSON format."""

        logger.info(
            f"   📡 Generating {num_questions} questions from user transcript..."
        )

        response = self.client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                max_output_tokens=15000,
                temperature=0.4,
                response_mime_type="application/json",
            ),
        )

        questions = json.loads(response.text)

        # Validate and filter
        self._convert_gemini_arrays_to_objects(
            {"audio_sections": [{"questions": questions}]}
        )

        valid_questions = questions

        # Check minimum count
        min_required = int(num_questions * 0.8)
        if len(valid_questions) < min_required:
            raise ValueError(
                f"Insufficient questions from transcript: got {len(valid_questions)}, "
                f"expected at least {min_required} (80% of {num_questions})"
            )

        logger.info(f"   ✅ Generated {len(valid_questions)} valid questions")

        return valid_questions

    def _format_transcript_text(self, transcript: Dict) -> str:
        """Format transcript dict to readable text"""
        lines = []

        if "segments" in transcript:
            # YouTube format (with timestamps)
            for segment in transcript["segments"]:
                speaker = transcript["speaker_roles"][segment["speaker_index"]]
                lines.append(f"{speaker}: {segment['text']}")
        else:
            # User transcript format
            for line in transcript.get("lines", []):
                speaker = transcript["speaker_roles"][line["speaker"]]
                lines.append(f"{speaker}: {line['text']}")

        return "\n".join(lines)

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
        # ========== PHASE 7 & 8: New parameters ==========
        user_transcript: Optional[str] = None,
        youtube_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main method to generate complete listening test

        Supports 3 generation modes:
        1. AI Generated (default): AI creates script + questions + TTS audio
        2. User Transcript (Phase 7): User provides transcript → AI generates questions + TTS audio (parallel)
        3. YouTube URL (Phase 8): Gemini 2.5 Flash transcribes + generates questions (ONE call)

        Returns:
        {
          "test_id": "test_123",
          "audio_sections": [...],
          "questions": [...],
          "status": "ready"
        }
        """

        try:
            # ========== PHASE 8: YouTube URL mode ==========
            if youtube_url:
                logger.info(f"🎥 Mode: YouTube URL - Using Gemini 2.5 Flash Audio")
                logger.info(f"   URL: {youtube_url}")

                from src.services.gemini_audio_listening_service import (
                    get_gemini_audio_listening_service,
                )

                gemini_audio_service = get_gemini_audio_listening_service()

                result = await gemini_audio_service.generate_from_youtube(
                    youtube_url=youtube_url,
                    title=title,
                    language=language,
                    difficulty=difficulty,
                    num_questions=num_questions,
                    user_query=user_query,
                )

                # Format response to match expected structure
                audio_sections = [
                    {
                        "section_number": 1,
                        "section_title": result["title"],
                        "audio_url": result["audio_url"],
                        "duration_seconds": result["duration_seconds"],
                        "transcript": self._format_transcript_text(
                            result["transcript"]
                        ),
                        "voice_config": {
                            "source": "youtube",
                            "num_speakers": result["num_speakers"],
                        },
                        "questions": result["questions"],
                    }
                ]

                # Add question numbers
                questions = []
                for idx, q in enumerate(result["questions"], 1):
                    q["question_number"] = idx
                    q["audio_section"] = 1
                    q["max_points"] = 1
                    questions.append(q)

                logger.info(f"✅ YouTube test generated successfully!")
                logger.info(f"   - Duration: {result['duration_seconds']}s")
                logger.info(f"   - Speakers: {result['num_speakers']}")
                logger.info(f"   - Questions: {len(questions)}")

                return {
                    "audio_sections": audio_sections,
                    "questions": questions,
                    "status": "ready",
                }

            # ========== PHASE 7: User Transcript mode ==========
            if user_transcript:
                logger.info(f"📝 Mode: User Transcript - Parallel processing")
                logger.info(f"   Transcript length: {len(user_transcript)} chars")

                # Parse transcript to structured format
                parsed_script = self._parse_user_transcript(
                    transcript_text=user_transcript,
                    num_speakers=audio_config.get("num_speakers", 1),
                    language=language,
                )

                logger.info(f"   Parsed: {len(parsed_script['lines'])} lines")

                # Create script_result format for compatibility
                script_result = {
                    "audio_sections": [
                        {
                            "section_number": 1,
                            "section_title": title,
                            "script": parsed_script,
                            "questions": [],  # Will be filled by parallel task
                        }
                    ]
                }

                # PARALLEL PROCESSING: Generate questions + audio simultaneously ⚡
                logger.info(f"⚡ Starting parallel processing: Questions + Audio...")

                questions_task = self._generate_questions_from_transcript(
                    script=parsed_script,
                    language=language,
                    difficulty=difficulty,
                    num_questions=num_questions,
                    user_query=user_query,
                )

                audio_task = self._generate_section_audio(
                    script=parsed_script,
                    voice_names=audio_config.get("voice_names")
                    or await self._select_voices_by_gender(
                        parsed_script.get("speaker_roles", []), language
                    ),
                    language=language,
                    speaking_rate=audio_config.get("speaking_rate", 1.0),
                    use_pro_model=use_pro_model,
                    force_num_speakers=audio_config.get("num_speakers"),
                )

                # Wait for both tasks to complete
                questions_result, (audio_bytes, duration) = await asyncio.gather(
                    questions_task, audio_task
                )

                logger.info(f"✅ Parallel processing complete!")
                logger.info(f"   - Questions: {len(questions_result)}")
                logger.info(f"   - Audio: {len(audio_bytes)} bytes, ~{duration}s")

                # Upload audio to R2
                temp_test_id = f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                audio_url, file_id = await self._upload_audio_to_r2(
                    audio_bytes=audio_bytes,
                    creator_id=creator_id,
                    test_id=temp_test_id,
                    section_num=1,
                )

                # Build transcript text using lines format
                transcript_dict = {
                    "speaker_roles": parsed_script["speaker_roles"],
                    "lines": parsed_script["lines"],
                }
                transcript_text = self._format_transcript_text(transcript_dict)

                # Format audio section
                audio_sections = [
                    {
                        "section_number": 1,
                        "section_title": title,
                        "audio_url": audio_url,
                        "audio_file_id": file_id,
                        "duration_seconds": duration,
                        "transcript": transcript_text,
                        "voice_config": {
                            "voice_names": audio_config.get("voice_names"),
                            "num_speakers": audio_config.get("num_speakers"),
                        },
                        "questions": questions_result,
                    }
                ]

                # Add question numbers
                questions = []
                for idx, q in enumerate(questions_result, 1):
                    q["question_number"] = idx
                    q["audio_section"] = 1
                    q["max_points"] = 1
                    questions.append(q)

                logger.info(f"✅ User transcript test generated successfully!")
                logger.info(f"   - Questions: {len(questions)}")

                return {
                    "audio_sections": audio_sections,
                    "questions": questions,
                    "status": "ready",
                }

            # ========== DEFAULT: AI Generated mode ==========
            logger.info(f"🤖 Mode: AI Generated (default)")

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
                    # Extract gender from speaker_roles to ensure male/female differentiation
                    speaker_roles = section["script"].get("speaker_roles", [])
                    voice_names = await self._select_voices_by_gender(
                        speaker_roles, language
                    )
                    logger.info(
                        f"   🎙️ Auto-selected voices for roles {speaker_roles}: {voice_names}"
                    )
                else:
                    logger.info(f"   🎙️ Using user-provided voices: {voice_names}")

                # Generate audio
                logger.info(f"   🔊 Generating audio for section {section_num}...")
                audio_bytes, duration = await self._generate_section_audio(
                    script=section["script"],
                    voice_names=voice_names,
                    language=language,
                    speaking_rate=audio_config.get("speaking_rate", 1.0),
                    use_pro_model=use_pro_model,
                    force_num_speakers=audio_config.get("num_speakers"),
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
