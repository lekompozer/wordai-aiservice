"""
Test Generator Service - Phase 1
Generate multiple-choice tests from documents or files using Gemini AI with JSON Mode.
"""

import logging
import asyncio
import json
import re
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
        self.max_retries = 2  # Reduced to 2 retries, then fallback to ChatGPT

    def _fix_json_string(self, json_str: str) -> str:
        """
        Fix common JSON formatting issues, especially with Vietnamese text

        Args:
            json_str: Potentially malformed JSON string

        Returns:
            Fixed JSON string
        """
        try:
            # Remove any markdown code blocks
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            # Fix common issues:
            # 1. Replace smart quotes with regular quotes
            json_str = json_str.replace('"', '"').replace('"', '"')
            json_str = json_str.replace(""", "'").replace(""", "'")

            # 2. Fix unescaped quotes within strings (simple heuristic)
            # This is a basic fix - more sophisticated parsing may be needed

            # 3. Remove any BOM or invisible characters
            json_str = json_str.strip("\ufeff\u200b")

            return json_str
        except Exception as e:
            logger.warning(f"Error in _fix_json_string: {e}")
            return json_str
        logger.info(
            "🤖 Test Generator Service initialized (Gemini 2.5 Pro with ChatGPT fallback)"
        )

    def _build_generation_prompt(
        self,
        user_query: str,
        num_questions: int,
        document_content: str,
        language: str = "vi",
        difficulty: Optional[str] = None,
        num_options: int = 4,
        num_correct_answers: int = 1,
    ) -> str:
        """Build prompt for test generation with language support and flexible answer options"""

        # Language instruction - now supports ANY language dynamically
        lang_instruction = (
            f"Generate all questions, options, and explanations in {language} language."
        )

        # Difficulty instructions
        difficulty_map = {
            "easy": "Create EASY questions that test basic understanding and recall of straightforward facts from the document. Questions should be simple and clear.",
            "medium": "Create MEDIUM difficulty questions that test comprehension and application of concepts. Questions should require understanding relationships between ideas.",
            "hard": "Create HARD questions that test deep analysis, synthesis, and critical thinking. Questions should be challenging and require thorough understanding of complex concepts.",
        }
        difficulty_instruction = ""
        if difficulty and difficulty.lower() in difficulty_map:
            difficulty_instruction = (
                f"\n10. DIFFICULTY LEVEL: {difficulty_map[difficulty.lower()]}"
            )

        # Generate option keys dynamically (A, B, C, D, E, F, G, H, I, J)
        option_keys = [chr(65 + i) for i in range(num_options)]  # 65 is ASCII for 'A'
        option_examples = [
            f'{{"option_key": "{key}", "option_text": "string"}}' for key in option_keys
        ]
        options_example = ",\n           ".join(option_examples)

        # Correct answer instruction
        if num_correct_answers == 1:
            correct_answer_instruction = 'The "correct_answer_keys" field must be an array with exactly ONE correct option key.'
            correct_answer_example = f'"correct_answer_keys": ["{option_keys[0]}"]'
        else:
            correct_answer_instruction = f'The "correct_answer_keys" field must be an array with exactly {num_correct_answers} correct option keys.'
            correct_answer_example = (
                f'"correct_answer_keys": {option_keys[:num_correct_answers]}'
            )

        prompt = f"""You are an expert in creating educational assessments. Your task is to generate a multiple-choice quiz based on the provided document and user query.

**CRITICAL INSTRUCTIONS:**
1. Your output MUST be a single, valid JSON object.
2. **IMPORTANT: Properly escape all special characters in JSON strings:**
   - Use \\" for double quotes inside strings
   - Use \\n for newlines inside strings
   - Use \\\\ for backslashes inside strings
3. {lang_instruction}
4. **IMPORTANT: If the user query specifies different requirements (e.g., number of options, correct answers, topics to focus on), follow the user's specifications FIRST, then use these defaults as fallback.**
5. The JSON object must conform to the following structure:
   {{
     "questions": [
       {{
         "question_text": "string",
         "options": [
           {options_example}
         ],
         {correct_answer_example},
         "explanation": "string (Explain WHY the correct answer(s) are right, based on the document)."
       }}
     ]
   }}
6. Generate exactly {num_questions} questions (unless user query specifies otherwise).
7. The questions must be relevant to the user's query: "{user_query}".
8. All information used to create questions, answers, and explanations must come directly from the provided document.
9. Each question should have {num_options} options by default ({", ".join(option_keys)}), but adjust if user query indicates otherwise.
10. {correct_answer_instruction} However, if the question complexity requires it or user query specifies, you may adjust.
11. Explanations should be clear and reference specific information from the document.{difficulty_instruction}
12. **VALIDATE your JSON output before returning it. Make sure all strings are properly escaped and all brackets are balanced.**

**DOCUMENT CONTENT:**
---
{document_content}
---

Now, generate the quiz based on the instructions and the document provided. Return ONLY the JSON object, no additional text, no markdown code blocks."""

        return prompt

    async def _generate_questions_with_ai(
        self,
        content: str,
        user_query: str,
        language: str,
        difficulty: Optional[str],
        num_questions: int,
        gemini_pdf_bytes: Optional[bytes] = None,
        num_options: int = 4,
        num_correct_answers: int = 1,
    ) -> list:
        """
        Generate questions using AI (used by background job)

        Returns:
            list of question dictionaries
        """
        # Build prompt
        prompt = self._build_generation_prompt(
            user_query,
            num_questions,
            content if not gemini_pdf_bytes else "",
            language,
            difficulty=difficulty,
            num_options=num_options,
            num_correct_answers=num_correct_answers,
        )

        # Generate with retry logic
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"   Attempt {attempt + 1}/{self.max_retries}: Calling Gemini..."
                )

                # Prepare content for API call
                if gemini_pdf_bytes:
                    logger.info(f"   Using PDF bytes: {len(gemini_pdf_bytes)} bytes")
                    pdf_part = types.Part.from_bytes(
                        data=gemini_pdf_bytes, mime_type="application/pdf"
                    )
                    contents = [pdf_part, prompt]
                else:
                    contents = [prompt]

                # Call Gemini with JSON Mode
                response = self.client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        max_output_tokens=8000,
                        temperature=0.3,
                        response_mime_type="application/json",
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

                # ✅ Clean JSON response (fix common issues with Vietnamese text)
                try:
                    # Try to parse directly first
                    questions_json = json.loads(response_text)
                    logger.info(f"   ✅ JSON parsed successfully on first attempt")
                except json.JSONDecodeError as e:
                    logger.warning(f"   ⚠️ Initial JSON parse failed: {e}")
                    logger.warning(f"   Attempting to fix JSON formatting...")

                    # Apply JSON fixes
                    fixed_json = self._fix_json_string(response_text)

                    # Try parsing again
                    try:
                        questions_json = json.loads(fixed_json)
                        logger.info(f"   ✅ JSON parsing successful after cleanup")
                    except json.JSONDecodeError as e2:
                        # Log the problematic part of JSON for debugging
                        error_pos = e2.pos if hasattr(e2, "pos") else 0
                        snippet_start = max(0, error_pos - 200)
                        snippet_end = min(len(fixed_json), error_pos + 200)
                        problematic_snippet = fixed_json[snippet_start:snippet_end]

                        logger.error(
                            f"   ❌ JSON parsing error at position {error_pos}"
                        )
                        logger.error(f"   Error message: {str(e2)}")
                        logger.error(f"   Problematic snippet:")
                        logger.error(f"   ...{problematic_snippet}...")

                        # Save the full response for debugging
                        debug_file = f"/tmp/gemini_response_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        try:
                            with open(debug_file, "w", encoding="utf-8") as f:
                                f.write(f"Original response:\n{response_text}\n\n")
                                f.write(f"Fixed response:\n{fixed_json}\n\n")
                                f.write(f"Error: {str(e2)}\n")
                            logger.error(f"   Full response saved to {debug_file}")
                        except Exception as save_error:
                            logger.error(f"   Could not save debug file: {save_error}")

                        raise e2

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
                    # Check for required fields (support both old and new format)
                    has_correct_answer_key = "correct_answer_key" in q
                    has_correct_answer_keys = "correct_answer_keys" in q

                    if not all(
                        k in q for k in ["question_text", "options", "explanation"]
                    ):
                        raise ValueError(f"Question {idx + 1} missing required fields")

                    if not has_correct_answer_key and not has_correct_answer_keys:
                        raise ValueError(
                            f"Question {idx + 1} missing correct_answer_key or correct_answer_keys"
                        )

                    if len(q["options"]) < 2:
                        raise ValueError(
                            f"Question {idx + 1} must have at least 2 options"
                        )

                    # Normalize to correct_answer_keys array format
                    if has_correct_answer_key and not has_correct_answer_keys:
                        q["correct_answer_keys"] = [q["correct_answer_key"]]
                    elif has_correct_answer_keys:
                        if isinstance(q["correct_answer_keys"], str):
                            q["correct_answer_keys"] = [q["correct_answer_keys"]]

                    # Keep backwards compatibility
                    q["correct_answer_key"] = (
                        q["correct_answer_keys"][0]
                        if q["correct_answer_keys"]
                        else None
                    )

                    # Add question_id
                    q["question_id"] = str(ObjectId())

                logger.info(f"   ✅ Generated {len(questions_list)} valid questions")
                return questions_list

            except json.JSONDecodeError as e:
                logger.error(f"   ❌ JSON parsing error: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = (2**attempt) + 1
                    logger.warning(f"   ⚠️ Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
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
                else:
                    logger.error(f"   ❌ Gemini generation failed: {e}")
                    raise

        # All Gemini attempts failed, try ChatGPT as fallback
        logger.warning("⚠️ All Gemini attempts failed. Trying ChatGPT as fallback...")
        try:
            return await self._generate_with_chatgpt(
                prompt=prompt,
                gemini_pdf_bytes=gemini_pdf_bytes,
                num_questions=num_questions,
            )
        except Exception as chatgpt_error:
            logger.error(f"❌ ChatGPT fallback also failed: {chatgpt_error}")
            raise Exception(
                f"Both Gemini and ChatGPT failed to generate questions. Last error: {chatgpt_error}"
            )

    async def _generate_with_chatgpt(
        self,
        prompt: str,
        gemini_pdf_bytes: Optional[bytes],
        num_questions: int,
    ) -> list:
        """
        Fallback method using ChatGPT (GPT-4o) when Gemini fails
        Supports PDF via base64 encoding (GPT-4o supports PDF inputs)
        """
        import base64
        from openai import AsyncOpenAI

        # Get OpenAI API key from config
        openai_api_key = getattr(config, "OPENAI_API_KEY", None)
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not configured for fallback")

        client = AsyncOpenAI(api_key=openai_api_key)

        logger.info("🤖 Calling ChatGPT (GPT-4o) as fallback...")

        try:
            messages = []

            if gemini_pdf_bytes:
                # Encode PDF as base64 for GPT-4o
                logger.info(f"   Encoding PDF as base64: {len(gemini_pdf_bytes)} bytes")

                pdf_base64 = base64.b64encode(gemini_pdf_bytes).decode("utf-8")

                # GPT-4o supports PDF via document understanding
                # Send both PDF data and prompt
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"I have attached a PDF document. {prompt}",
                            },
                            {
                                "type": "image_url",  # GPT-4o treats PDF as document/image
                                "image_url": {
                                    "url": f"data:application/pdf;base64,{pdf_base64}"
                                },
                            },
                        ],
                    }
                ]

                logger.info("   ✅ PDF encoded and attached to request")
            else:
                # Text only
                messages = [{"role": "user", "content": prompt}]

            # Call ChatGPT with JSON mode
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=8000,
            )

            response_text = response.choices[0].message.content
            logger.info(f"   ✅ ChatGPT response: {len(response_text)} characters")

            # Parse and validate JSON (same for both paths)
            questions_json = json.loads(response_text)

            if (
                not isinstance(questions_json, dict)
                or "questions" not in questions_json
            ):
                raise ValueError("Invalid JSON structure from ChatGPT")

            questions_list = questions_json["questions"]

            if not isinstance(questions_list, list) or len(questions_list) == 0:
                raise ValueError("No questions in ChatGPT response")

            # Validate and normalize questions
            for idx, q in enumerate(questions_list):
                has_correct_answer_key = "correct_answer_key" in q
                has_correct_answer_keys = "correct_answer_keys" in q

                if not all(k in q for k in ["question_text", "options", "explanation"]):
                    raise ValueError(f"Question {idx + 1} missing required fields")

                if not has_correct_answer_key and not has_correct_answer_keys:
                    raise ValueError(f"Question {idx + 1} missing correct answer")

                # Normalize to array format
                if has_correct_answer_key and not has_correct_answer_keys:
                    q["correct_answer_keys"] = [q["correct_answer_key"]]
                elif has_correct_answer_keys:
                    if isinstance(q["correct_answer_keys"], str):
                        q["correct_answer_keys"] = [q["correct_answer_keys"]]

                q["correct_answer_key"] = (
                    q["correct_answer_keys"][0] if q["correct_answer_keys"] else None
                )
                q["question_id"] = str(ObjectId())

            logger.info(
                f"   ✅ ChatGPT generated {len(questions_list)} valid questions"
            )
            return questions_list

        except Exception as e:
            logger.error(f"   ❌ ChatGPT generation failed: {e}")
            raise

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
        gemini_pdf_bytes: Optional[bytes] = None,  # NEW: PDF content as bytes
        num_options: int = 4,  # NEW: Number of options per question (2-10)
        num_correct_answers: int = 1,  # NEW: Number of correct answers (1-num_options)
    ) -> Tuple[str, Dict]:
        """
        Generate test from text content OR PDF bytes using Gemini AI with JSON Mode

        Args:
            content: Text content to generate questions from (or placeholder for PDF)
            title: Test title
            user_query: User's description of what to test
            language: Language code (vi/en/zh)
            num_questions: Number of questions to generate (1-100)
            creator_id: User ID of test creator
            source_type: "document" or "file"
            source_id: Document ID or R2 file key
            time_limit_minutes: Time limit for test (1-300 minutes)
            gemini_pdf_bytes: PDF content as bytes (for NEW API)

        Returns:
            Tuple of (test_id, metadata)
        """
        try:
            # Validate inputs
            if not 1 <= num_questions <= 100:
                raise ValueError("num_questions must be between 1 and 100")
            if not 1 <= time_limit_minutes <= 300:
                raise ValueError("time_limit_minutes must be between 1 and 300")

            # For PDF files, use Gemini with PDF bytes
            if gemini_pdf_bytes:
                logger.info(f"📄 Using PDF bytes: {len(gemini_pdf_bytes)} bytes")
            else:
                # Text content validation (skip for PDFs which may be image-based)
                if not gemini_pdf_bytes and len(content) < 100:
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

            logger.info(f"📝 Generating {num_questions} questions")
            logger.info(f"   Title: {title}")
            logger.info(f"   User query: {user_query}")
            logger.info(f"   Language: {language}")

            # Build prompt with language parameter
            prompt = self._build_generation_prompt(
                user_query,
                num_questions,
                content if not gemini_pdf_bytes else "",
                language,
                num_options=num_options,
                num_correct_answers=num_correct_answers,
            )

            # Generate with retry logic
            questions_json = None
            for attempt in range(self.max_retries):
                try:
                    logger.info(
                        f"   Attempt {attempt + 1}/{self.max_retries}: Calling Gemini..."
                    )

                    # Prepare content for API call
                    if gemini_pdf_bytes:
                        # Use PDF bytes directly with NEW API
                        logger.info(
                            f"   Using PDF bytes: {len(gemini_pdf_bytes)} bytes"
                        )

                        # Create Part from PDF bytes
                        pdf_part = types.Part.from_bytes(
                            data=gemini_pdf_bytes, mime_type="application/pdf"
                        )
                        contents = [pdf_part, prompt]
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
                        # Check for required fields (support both old and new format)
                        has_correct_answer_key = "correct_answer_key" in q
                        has_correct_answer_keys = "correct_answer_keys" in q

                        if not all(
                            k in q
                            for k in [
                                "question_text",
                                "options",
                                "explanation",
                            ]
                        ):
                            raise ValueError(
                                f"Question {idx + 1} missing required fields"
                            )

                        if not has_correct_answer_key and not has_correct_answer_keys:
                            raise ValueError(
                                f"Question {idx + 1} missing correct_answer_key or correct_answer_keys"
                            )

                        if len(q["options"]) < 2:
                            raise ValueError(
                                f"Question {idx + 1} must have at least 2 options"
                            )

                        # Normalize to correct_answer_keys array format
                        if has_correct_answer_key and not has_correct_answer_keys:
                            # Convert old format (string) to new format (array)
                            q["correct_answer_keys"] = [q["correct_answer_key"]]
                        elif has_correct_answer_keys:
                            # Ensure it's an array
                            if isinstance(q["correct_answer_keys"], str):
                                q["correct_answer_keys"] = [q["correct_answer_keys"]]

                        # Keep backwards compatibility: also store as correct_answer_key (first correct answer)
                        q["correct_answer_key"] = (
                            q["correct_answer_keys"][0]
                            if q["correct_answer_keys"]
                            else None
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
        # Get MongoDB client directly
        from pymongo import MongoClient
        import config.config as config

        mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        client = MongoClient(mongo_uri)
        db_name = getattr(config, "MONGODB_NAME", "wordai_db")
        db = client[db_name]
        collection = db["online_tests"]

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
        # Get MongoDB client directly
        from pymongo import MongoClient
        import config.config as config

        mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        client = MongoClient(mongo_uri)
        db_name = getattr(config, "MONGODB_NAME", "wordai_db")
        db = client[db_name]
        collection = db["online_tests"]

        # Get test from database
        test_doc = collection.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise ValueError(f"Test not found: {test_id}")

        if not test_doc.get("is_active", False):
            raise ValueError(f"Test is not active: {test_id}")

        # Remove correct answers and explanations
        questions_for_user = []
        for q in test_doc["questions"]:
            # Get question_type (default to 'mcq' for backward compatibility)
            q_type = q.get("question_type", "mcq")

            question_data = {
                "question_id": q["question_id"],
                "question_text": q["question_text"],
                "question_type": q_type,  # Include question type (mcq/essay)
                # Do NOT include: correct_answer_key, explanation
            }

            # MCQ-specific fields
            if q_type == "mcq":
                question_data["options"] = q.get("options", [])

            # Essay-specific fields
            if q_type == "essay":
                question_data["max_points"] = q.get("max_points", 1)
                # Optionally include grading rubric for students to see expectations
                if q.get("grading_rubric"):
                    question_data["grading_rubric"] = q.get("grading_rubric")

            # Include media if present (for both MCQ and Essay)
            if q.get("media_type"):
                question_data["media_type"] = q["media_type"]
                question_data["media_url"] = q.get("media_url")
                question_data["media_description"] = q.get("media_description", "")

            questions_for_user.append(question_data)

        # Get attachments (reading comprehension materials)
        attachments = test_doc.get("attachments", [])

        # Format attachments for response (remove internal IDs, keep public info)
        formatted_attachments = []
        for att in attachments:
            formatted_attachments.append(
                {
                    "attachment_id": att.get("attachment_id"),
                    "title": att.get("title"),
                    "description": att.get("description"),
                    "file_url": att.get("file_url"),
                }
            )

        return {
            "test_id": test_id,
            "title": test_doc["title"],
            "time_limit_minutes": test_doc["time_limit_minutes"],
            "num_questions": len(questions_for_user),
            "questions": questions_for_user,
            "attachments": formatted_attachments,  # NEW: PDF attachments for reading comprehension
        }


# Singleton instance
_test_generator_service = None


def get_test_generator_service() -> TestGeneratorService:
    """Get singleton instance of TestGeneratorService"""
    global _test_generator_service
    if _test_generator_service is None:
        _test_generator_service = TestGeneratorService()
    return _test_generator_service
