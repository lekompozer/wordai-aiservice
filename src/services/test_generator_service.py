"""
Test Generator Service - Phase 1
Generate multiple-choice tests from documents or files using Gemini AI with JSON Mode.
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId

from google import genai
from google.genai import types
import config.config as config

logger = logging.getLogger(__name__)


class TestGeneratorService:
    """Service to generate online tests from documents using Gemini AI"""

    def __init__(self):
        """Initialize test generator with Gemini client"""
        self.gemini_api_key = config.GEMINI_API_KEY
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        self.client = genai.Client(api_key=self.gemini_api_key)
        self.max_retries = 3
        logger.info(
            "🤖 Test Generator Service initialized (Gemini 2.5 Pro with JSON Mode)"
        )

    def _build_generation_prompt(
        self,
        user_query: str,
        num_questions: int,
        document_content: str,
        language: str = "vi",
    ) -> str:
        """Build prompt for test generation with language support"""

        # Language instructions
        language_map = {
            "vi": "Generate all questions, options, and explanations in Vietnamese.",
            "en": "Generate all questions, options, and explanations in English.",
            "zh": "Generate all questions, options, and explanations in Chinese (Simplified).",
        }
        lang_instruction = language_map.get(language, language_map["vi"])

        prompt = f"""You are an expert in creating educational assessments. Your task is to generate a multiple-choice quiz based on the provided document and user query.

**CRITICAL INSTRUCTIONS:**
1. Your output MUST be a single, valid JSON object.
2. {lang_instruction}
3. The JSON object must conform to the following structure:
   {{
     "questions": [
       {{
         "question_text": "string",
         "options": [
           {{"option_key": "A", "option_text": "string"}},
           {{"option_key": "B", "option_text": "string"}},
           {{"option_key": "C", "option_text": "string"}},
           {{"option_key": "D", "option_text": "string"}}
         ],
         "correct_answer_key": "string",
         "explanation": "string (Explain WHY the correct answer is right, based on the document)."
       }}
     ]
   }}
4. Generate exactly {num_questions} questions.
5. The questions must be relevant to the user's query: "{user_query}".
6. All information used to create questions, answers, and explanations must come directly from the provided document.
7. Each question must have exactly 4 options (A, B, C, D).
8. Only ONE option should be correct per question.
9. Explanations should be clear and reference specific information from the document.

**DOCUMENT CONTENT:**
---
{document_content}
---

Now, generate the quiz based on the instructions and the document provided. Return ONLY the JSON object, no additional text."""

        return prompt

    async def generate_test_from_content(
        self,
        content: str,
        title: str,
        user_query: str,
        language: str,
        num_questions: int,
        creator_id: str,
        source_type: str,
        source_id: str,
        time_limit_minutes: int = 30,
        gemini_file_name: Optional[str] = None,  # NEW: For PDF uploads
    ) -> Tuple[str, Dict]:
        """
        Generate test from text content OR Gemini uploaded file using Gemini AI with JSON Mode

        Args:
            content: Text content to generate questions from (or placeholder for file)
            title: Test title
            user_query: User's description of what to test
            language: Language code (vi/en/zh)
            num_questions: Number of questions to generate (1-100)
            creator_id: User ID of test creator
            source_type: "document" or "file"
            source_id: Document ID or R2 file key
            time_limit_minutes: Time limit for test (1-300 minutes)
            gemini_file_name: Gemini file name (for PDF files)

        Returns:
            Tuple of (test_id, metadata)
        """
        try:
            # Validate inputs
            if not 1 <= num_questions <= 100:
                raise ValueError("num_questions must be between 1 and 100")
            if not 1 <= time_limit_minutes <= 300:
                raise ValueError("time_limit_minutes must be between 1 and 300")
            
            # For PDF files, use Gemini file upload
            if gemini_file_name:
                logger.info(f"📄 Using Gemini uploaded file: {gemini_file_name}")
            else:
                # Text content validation
                if len(content) < 100:
                    raise ValueError("Content too short (minimum 100 characters)")

                # Truncate content if too long (max ~1M characters / ~250K tokens)
                max_content_length = 1_000_000
                if len(content) > max_content_length:
                    logger.warning(
                        f"⚠️ Content truncated from {len(content)} to {max_content_length} chars"
                    )
                    content = (
                        content[:max_content_length]
                        + "\n\n[Content truncated for processing]"
                    )

            logger.info(
                f"📝 Generating {num_questions} questions"
            )
            logger.info(f"   Title: {title}")
            logger.info(f"   User query: {user_query}")
            logger.info(f"   Language: {language}")

            # Build prompt with language parameter
            prompt = self._build_generation_prompt(
                user_query, num_questions, content if not gemini_file_name else "", language
            )

            # Generate with retry logic
            questions_json = None
            for attempt in range(self.max_retries):
                try:
                    logger.info(
                        f"   Attempt {attempt + 1}/{self.max_retries}: Calling Gemini..."
                    )

                    # Prepare content for API call
                    if gemini_file_name:
                        # Use Gemini uploaded file + prompt
                        logger.info(f"   Using uploaded PDF file: {gemini_file_name}")
                        gemini_file = genai.get_file(name=gemini_file_name)
                        contents = [gemini_file, prompt]
                    else:
                        # Use text prompt only
                        contents = [prompt]

                    # Call Gemini with JSON Mode
                    response = self.client.models.generate_content(
                        model="gemini-2.5-pro",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            max_output_tokens=8000,
                            temperature=0.3,  # Low temperature for consistent output
                            response_mime_type="application/json",  # JSON Mode
                        ),
                    )

                    # Get response text
                    if hasattr(response, "text") and response.text:
                        response_text = response.text
                        logger.info(
                            f"   ✅ Gemini response: {len(response_text)} characters"
                        )
                    else:
                        raise Exception("No text response from Gemini API")

                    # Parse JSON
                    questions_json = json.loads(response_text)

                    # Validate structure
                    if (
                        not isinstance(questions_json, dict)
                        or "questions" not in questions_json
                    ):
                        raise ValueError(
                            "Invalid JSON structure: missing 'questions' field"
                        )

                    questions_list = questions_json["questions"]
                    if not isinstance(questions_list, list) or len(questions_list) == 0:
                        raise ValueError(
                            "Invalid JSON: 'questions' must be a non-empty array"
                        )

                    # Validate each question
                    for idx, q in enumerate(questions_list):
                        if not all(
                            k in q
                            for k in [
                                "question_text",
                                "options",
                                "correct_answer_key",
                                "explanation",
                            ]
                        ):
                            raise ValueError(
                                f"Question {idx + 1} missing required fields"
                            )
                        if len(q["options"]) < 2:
                            raise ValueError(
                                f"Question {idx + 1} must have at least 2 options"
                            )

                        # Add question_id to each question
                        q["question_id"] = str(ObjectId())

                    logger.info(
                        f"   ✅ Generated {len(questions_list)} valid questions"
                    )
                    break  # Success

                except json.JSONDecodeError as e:
                    logger.error(f"   ❌ JSON parsing error: {e}")
                    if attempt < self.max_retries - 1:
                        wait_time = (2**attempt) + 1
                        logger.warning(f"   ⚠️ Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise ValueError(
                            f"Failed to parse JSON after {self.max_retries} attempts: {e}"
                        )

                except Exception as e:
                    error_str = str(e).lower()
                    is_retryable = any(
                        keyword in error_str
                        for keyword in [
                            "rate limit",
                            "429",
                            "server error",
                            "500",
                            "502",
                            "503",
                            "504",
                            "timeout",
                            "overload",
                            "529",
                            "resource exhausted",
                        ]
                    )

                    if is_retryable and attempt < self.max_retries - 1:
                        wait_time = (2**attempt) + 1
                        logger.warning(
                            f"   ⚠️ Gemini error (attempt {attempt + 1}/{self.max_retries}): {e}"
                        )
                        logger.warning(f"   Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"   ❌ Gemini generation failed: {e}")
                        raise

            if not questions_json:
                raise Exception("Failed to generate questions after all retries")

            # Save to database
            test_id = await self._save_test_to_db(
                questions=questions_json["questions"],
                title=title,
                user_query=user_query,
                language=language,
                creator_id=creator_id,
                source_type=source_type,
                source_id=source_id,
                time_limit_minutes=time_limit_minutes,
            )

            metadata = {
                "test_id": test_id,
                "title": title,
                "num_questions": len(questions_json["questions"]),
                "time_limit_minutes": time_limit_minutes,
                "language": language,
                "created_at": datetime.now().isoformat(),
                "source_type": source_type,
            }

            logger.info(f"✅ Test generated successfully: {test_id}")
            return test_id, metadata

        except Exception as e:
            logger.error(f"❌ Test generation failed: {e}")
            raise

    async def _save_test_to_db(
        self,
        questions: List[Dict],
        title: str,
        user_query: str,
        language: str,
        creator_id: str,
        source_type: str,
        source_id: str,
        time_limit_minutes: int,
    ) -> str:
        """Save generated test to MongoDB"""
        from src.services.mongodb_service import get_mongodb_service

        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        # Prepare document
        test_doc = {
            "title": title,
            "user_query": user_query,  # Store original query for reference
            "language": language,  # Store language for future filtering
            "source_type": source_type,  # "document" or "file"
            "source_document_id": source_id if source_type == "document" else None,
            "source_file_r2_key": source_id if source_type == "file" else None,
            "creator_id": creator_id,
            "time_limit_minutes": time_limit_minutes,
            "questions": questions,
            "max_retries": 1,  # Default: 1 attempt (Phase 3 will make this configurable)
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        # Insert to database
        result = collection.insert_one(test_doc)
        test_id = str(result.inserted_id)

        logger.info(f"💾 Saved test to database: {test_id}")
        return test_id

    async def get_test_for_taking(self, test_id: str, user_id: str) -> Dict:
        """
        Get test details for taking (without correct answers)

        Args:
            test_id: Test ID
            user_id: User ID (for access control)

        Returns:
            Test details (questions without correct answers)
        """
        from src.services.mongodb_service import get_mongodb_service

        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        # Get test from database
        test_doc = collection.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise ValueError(f"Test not found: {test_id}")

        if not test_doc.get("is_active", False):
            raise ValueError(f"Test is not active: {test_id}")

        # Remove correct answers and explanations
        questions_for_user = []
        for q in test_doc["questions"]:
            questions_for_user.append(
                {
                    "question_id": q["question_id"],
                    "question_text": q["question_text"],
                    "options": q["options"],
                    # Do NOT include: correct_answer_key, explanation
                }
            )

        return {
            "test_id": test_id,
            "title": test_doc["title"],
            "time_limit_minutes": test_doc["time_limit_minutes"],
            "num_questions": len(questions_for_user),
            "questions": questions_for_user,
        }


# Singleton instance
_test_generator_service = None


def get_test_generator_service() -> TestGeneratorService:
    """Get singleton instance of TestGeneratorService"""
    global _test_generator_service
    if _test_generator_service is None:
        _test_generator_service = TestGeneratorService()
    return _test_generator_service
