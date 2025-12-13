"""
Test Generator Service - Phase 1
Generate multiple-choice tests from documents or files using Gemini AI with JSON Mode.
"""

import logging
import asyncio
import json
import re
import os
import sys
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from bson import ObjectId

from google import genai
from google.genai import types
import config.config as config

from src.services.prompt_builders import prompt_builder

# Increase integer string conversion limit to handle potential large numbers from AI
# This prevents "Exceeds the limit" errors when AI returns malformed responses
sys.set_int_max_str_digits(100000)

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

            # 4. Check for incomplete JSON (missing closing brackets)
            # Count opening and closing brackets - they must match
            open_braces = json_str.count("{")
            close_braces = json_str.count("}")
            open_brackets = json_str.count("[")
            close_brackets = json_str.count("]")

            if open_braces != close_braces or open_brackets != close_brackets:
                logger.error(f"   ❌ Incomplete JSON detected:")
                logger.error(
                    f"      Opening {{ : {open_braces}, Closing }} : {close_braces}"
                )
                logger.error(
                    f"      Opening [ : {open_brackets}, Closing ] : {close_brackets}"
                )
                logger.error(
                    f"      Response likely truncated due to token limit or huge numbers"
                )
                raise ValueError(
                    f"Incomplete JSON: {open_braces} {{ vs {close_braces} }}, "
                    f"{open_brackets} [ vs {close_brackets} ]"
                )

            # 5. Fix unescaped newlines within JSON string VALUES only
            # Match pattern: "key": "value with\n newline(s)"
            # Only fix newlines that appear INSIDE quoted values after a colon
            def fix_string_newlines(match):
                # match.group(0) is the full match including colon and quotes
                return match.group(0).replace("\n", "\\n")

            # Match quoted strings that are values (come after :) and contain ANY number of newlines
            # Pattern: : "any content with newlines"
            # Uses [^"\\]|\\.  to match: any char except " and \, OR any escaped char
            # This properly handles multi-line strings with multiple newlines
            json_str = re.sub(
                r':\s*"(?:[^"\\\n]|\\.|\n)*?"',
                lambda m: (
                    m.group(0).replace("\n", "\\n")
                    if "\n" in m.group(0)
                    else m.group(0)
                ),
                json_str,
            )

            return json_str
        except Exception as e:
            logger.warning(f"Error in _fix_json_string: {e}")
            return json_str

    def _build_generation_prompt(
        self,
        user_query: str,
        num_questions: int,
        document_content: str,
        language: str = "vi",
        difficulty: Optional[str] = None,
        num_options: int = 4,
        num_correct_answers: int = 1,
        test_category: str = "academic",
        mcq_type_config: Optional[Dict] = None,
        title: str = "",
        topic: str = "",
        is_general_knowledge: bool = False,
    ) -> str:
        """
        Build prompt for test generation

        Routes to appropriate prompt builder based on test_category and source type:
        - academic + document → Academic Document Prompt
        - academic + general → Academic General Prompt
        - diagnostic → Diagnostic Prompt
        """

        # Ensure difficulty is set
        if not difficulty:
            difficulty = "medium"

        # Route to appropriate prompt builder
        if test_category == "diagnostic":
            logger.info("🎭 Using DIAGNOSTIC prompt builder")
            return prompt_builder.build_diagnostic_prompt(
                title=title,
                topic=topic,
                num_questions=num_questions,
                language=language,
                user_query=user_query,
                num_options=num_options,
            )
        elif is_general_knowledge:
            logger.info("🧠 Using ACADEMIC GENERAL prompt builder (no document)")
            return prompt_builder.build_academic_general_prompt(
                title=title,
                topic=topic,
                num_questions=num_questions,
                language=language,
                difficulty=difficulty,
                user_query=user_query,
                mcq_type_config=mcq_type_config,
            )
        else:
            logger.info("📄 Using ACADEMIC DOCUMENT prompt builder")
            return prompt_builder.build_academic_document_prompt(
                title=title,
                topic=topic,
                num_questions=num_questions,
                language=language,
                difficulty=difficulty,
                user_query=user_query,
                document_content=document_content,
                mcq_type_config=mcq_type_config,
            )

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
        test_category: str = "academic",
        mcq_type_config: Optional[Dict] = None,
        title: str = "",
        topic: str = "",
        is_general_knowledge: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate questions using AI (used by background job)

        Returns:
            dict with 'questions' (list) and optionally 'diagnostic_criteria' (dict)
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
            test_category=test_category,
            mcq_type_config=mcq_type_config,
            title=title,
            topic=topic,
            is_general_knowledge=is_general_knowledge,
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

                # Define response schema for structured output
                # This forces Gemini to output properly formatted JSON
                is_diagnostic = test_category == "diagnostic"

                if is_diagnostic:
                    # Schema for diagnostic tests (no correct_answer_keys)
                    response_schema = {
                        "type": "object",
                        "properties": {
                            "questions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "question_text": {"type": "string"},
                                        "options": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "option_key": {"type": "string"},
                                                    "option_text": {"type": "string"},
                                                },
                                                "required": [
                                                    "option_key",
                                                    "option_text",
                                                ],
                                            },
                                        },
                                        "explanation": {"type": "string"},
                                    },
                                    "required": [
                                        "question_text",
                                        "options",
                                        "explanation",
                                    ],
                                },
                            },
                            "diagnostic_criteria": {
                                "type": "object",
                                "properties": {
                                    "result_types": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "type_id": {"type": "string"},
                                                "title": {"type": "string"},
                                                "description": {"type": "string"},
                                                "traits": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                            "required": [
                                                "type_id",
                                                "title",
                                                "description",
                                                "traits",
                                            ],
                                        },
                                    },
                                    "mapping_rules": {"type": "string"},
                                },
                                "required": ["result_types", "mapping_rules"],
                            },
                        },
                        "required": ["questions", "diagnostic_criteria"],
                    }
                else:
                    # Schema for academic tests

                    # Check if we are in mixed mode (Auto/Manual)
                    is_mixed_mode = mcq_type_config and mcq_type_config.get(
                        "distribution_mode"
                    ) in ["manual", "auto"]

                    if is_mixed_mode:
                        # Relaxed schema for mixed question types
                        response_schema = {
                            "type": "object",
                            "properties": {
                                "questions": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "question_type": {"type": "string"},
                                            "question_text": {"type": "string"},
                                            "options": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "option_key": {
                                                            "type": "string"
                                                        },
                                                        "option_text": {
                                                            "type": "string"
                                                        },
                                                    },
                                                    "required": [
                                                        "option_key",
                                                        "option_text",
                                                    ],
                                                },
                                            },
                                            "correct_answer_keys": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                            "template": {"type": "string"},
                                            "left_items": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                            "right_options": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                            "correct_matches": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "key": {"type": "string"},
                                                        "value": {"type": "string"},
                                                    },
                                                    "required": ["key", "value"],
                                                },
                                            },
                                            "explanation": {"type": "string"},
                                            "points": {
                                                "type": "integer",
                                                "minimum": 1,
                                                "maximum": 5,
                                            },
                                        },
                                        "required": [
                                            "question_type",
                                            "question_text",
                                            "explanation",
                                        ],
                                    },
                                }
                            },
                            "required": ["questions"],
                        }
                    else:
                        # Strict schema for traditional MCQ
                        response_schema = {
                            "type": "object",
                            "properties": {
                                "questions": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "question_type": {"type": "string"},
                                            "question_text": {"type": "string"},
                                            "options": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "option_key": {
                                                            "type": "string"
                                                        },
                                                        "option_text": {
                                                            "type": "string"
                                                        },
                                                    },
                                                    "required": [
                                                        "option_key",
                                                        "option_text",
                                                    ],
                                                },
                                            },
                                            "correct_answer_keys": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                            "explanation": {"type": "string"},
                                            "points": {
                                                "type": "integer",
                                                "minimum": 1,
                                                "maximum": 5,
                                            },
                                        },
                                        "required": [
                                            "question_text",
                                            "options",
                                            "correct_answer_keys",
                                            "explanation",
                                        ],
                                    },
                                }
                            },
                            "required": ["questions"],
                        }

                # 🐛 DEBUG: Save prompt for analysis
                try:
                    debug_dir = "/tmp/gemini_prompts"
                    os.makedirs(debug_dir, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    prompt_file = f"{debug_dir}/prompt_{timestamp}.txt"
                    with open(prompt_file, "w", encoding="utf-8") as f:
                        f.write("=== PROMPT ===\n")
                        f.write(prompt)
                        f.write(f"\n\n=== CONFIG ===\n")
                        f.write(f"num_questions: {num_questions}\n")
                        f.write(f"max_output_tokens: 25000\n")
                        f.write(f"temperature: 0.3\n")
                    logger.info(f"   💾 Saved prompt to {prompt_file}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not save prompt: {e}")

                # Call Gemini with JSON Mode and response schema
                # Run blocking Gemini call in thread pool to avoid blocking event loop
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model="gemini-3-pro-preview",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            max_output_tokens=25000,
                            temperature=0.3,
                            response_mime_type="application/json",
                            response_schema=response_schema,
                        ),
                    ),
                )

                # Get response text
                response_text = ""

                # Try standard text accessor
                try:
                    if hasattr(response, "text") and response.text:
                        response_text = response.text
                except Exception as e:
                    logger.warning(f"   ⚠️ Error accessing response.text: {e}")

                # Fallback: Iterate through candidates and parts if text is empty
                if (
                    not response_text
                    and hasattr(response, "candidates")
                    and response.candidates
                ):
                    try:
                        candidate = response.candidates[0]

                        # Log finish reason if not STOP
                        if (
                            hasattr(candidate, "finish_reason")
                            and candidate.finish_reason != "STOP"
                        ):
                            logger.warning(
                                f"   ⚠️ Gemini finish reason: {candidate.finish_reason}"
                            )

                        if hasattr(candidate, "content") and hasattr(
                            candidate.content, "parts"
                        ):
                            # Extract text from parts, ignoring non-text parts (like thought_signature)
                            text_parts = []
                            for part in candidate.content.parts:
                                if hasattr(part, "text") and part.text:
                                    text_parts.append(part.text)

                            if text_parts:
                                response_text = "".join(text_parts)
                                logger.info(
                                    "   ✅ Extracted text from response parts (fallback)"
                                )
                    except Exception as e:
                        logger.warning(f"   ⚠️ Error extracting text from parts: {e}")

                if response_text:
                    logger.info(
                        f"   ✅ Gemini response: {len(response_text)} characters"
                    )

                    # 💾 Save full response for debugging (always save for analysis)
                    try:
                        debug_dir = "/tmp/gemini_test_responses"
                        os.makedirs(debug_dir, exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        response_file = f"{debug_dir}/test_gen_{timestamp}.json"
                        with open(response_file, "w", encoding="utf-8") as f:
                            f.write(response_text)
                        logger.info(f"   💾 Saved full response to {response_file}")
                    except Exception as save_error:
                        logger.warning(
                            f"   ⚠️ Could not save response file: {save_error}"
                        )
                else:
                    # Log full response for debugging
                    logger.error(
                        f"   ❌ Empty response from Gemini. Response object: {response}"
                    )
                    raise Exception("No text response from Gemini API")

                # ✅ Clean JSON response (fix common issues with Vietnamese text)
                try:
                    # Try to parse directly first
                    questions_json = json.loads(response_text)
                    logger.info(f"   ✅ JSON parsed successfully on first attempt")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"   ⚠️ Initial JSON parse failed: {e}")

                    # If it's an integer conversion error, log response preview
                    if "integer string conversion" in str(e):
                        logger.error(
                            f"   ❌ Gemini returned malformed response with huge integer"
                        )
                        logger.error(f"   First 1000 chars: {response_text[:1000]}")
                        logger.error(f"   Last 1000 chars: {response_text[-1000:]}")
                        raise Exception(
                            f"Gemini returned invalid integer in response: {e}"
                        )

                    logger.warning(f"   Attempting to fix JSON formatting...")

                    # Apply JSON fixes
                    fixed_json = self._fix_json_string(response_text)

                    # Try parsing again
                    try:
                        questions_json = json.loads(fixed_json)
                        logger.info(f"   ✅ JSON parsing successful after cleanup")
                    except (json.JSONDecodeError, ValueError) as e2:
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

                # Validate each question (skip correct_answer validation for diagnostic)
                is_diagnostic = test_category == "diagnostic"

                for idx, q in enumerate(questions_list):
                    # Check for required fields (support both old and new format)
                    has_correct_answer_key = "correct_answer_key" in q
                    has_correct_answer_keys = "correct_answer_keys" in q
                    question_type = q.get("question_type", "mcq")

                    # Different question types have different required fields
                    if question_type in ["completion", "sentence_completion"]:
                        # Completion questions ONLY use IELTS format (like listening test)
                        # Format: template + blanks + correct_answers
                        if not all(
                            k in q for k in ["question_text", "template", "explanation"]
                        ):
                            logger.error(
                                f"❌ VALIDATION FAILED - Question {idx + 1} ({question_type})"
                            )
                            logger.error(
                                f"   IELTS format requires: question_text, template, explanation"
                            )
                            logger.error(f"   Question keys present: {list(q.keys())}")
                            logger.error(f"   RAW QUESTION DATA: {q}")
                            raise ValueError(
                                f"Question {idx + 1} missing required fields for {question_type}"
                            )
                    elif question_type == "matching":
                        # Matching questions need left_items and right_options
                        if not all(
                            k in q
                            for k in [
                                "question_text",
                                "left_items",
                                "right_options",
                                "explanation",
                            ]
                        ):
                            logger.error(
                                f"❌ VALIDATION FAILED - Question {idx + 1} (matching)"
                            )
                            logger.error(
                                f"   Required fields: question_text, left_items, right_options, explanation"
                            )
                            logger.error(f"   Question keys present: {list(q.keys())}")
                            logger.error(f"   RAW QUESTION DATA: {q}")
                            raise ValueError(
                                f"Question {idx + 1} missing required fields for matching"
                            )
                    elif question_type == "short_answer":
                        # Short answer questions don't need options
                        if not all(k in q for k in ["question_text", "explanation"]):
                            logger.error(
                                f"❌ VALIDATION FAILED - Question {idx + 1} (short_answer)"
                            )
                            logger.error(
                                f"   Required fields: question_text, explanation"
                            )
                            logger.error(f"   Question keys present: {list(q.keys())}")
                            logger.error(f"   RAW QUESTION DATA: {q}")
                            raise ValueError(
                                f"Question {idx + 1} missing required fields for short_answer"
                            )
                    else:
                        # Standard MCQ questions need options
                        if not all(
                            k in q for k in ["question_text", "options", "explanation"]
                        ):
                            logger.error(
                                f"❌ VALIDATION FAILED - Question {idx + 1} ({question_type})"
                            )
                            logger.error(
                                f"   Required fields: question_text, options, explanation"
                            )
                            logger.error(f"   Question keys present: {list(q.keys())}")
                            logger.error(f"   RAW QUESTION DATA: {q}")
                            raise ValueError(
                                f"Question {idx + 1} missing required fields"
                            )

                    # Skip correct_answer validation for diagnostic tests
                    if not is_diagnostic:
                        if question_type == "matching":
                            if "correct_matches" not in q:
                                raise ValueError(
                                    f"Question {idx + 1} missing correct_matches for matching question"
                                )
                        elif question_type == "completion":
                            # Completion questions ONLY use IELTS format
                            # Must have correct_answers array with blank_key and answers variations
                            if "correct_answers" not in q:
                                logger.error(
                                    f"❌ ANSWER VALIDATION FAILED - Question {idx + 1} (completion)"
                                )
                                logger.error(
                                    f"   Expected: correct_answers array with blank_key and answers"
                                )
                                logger.error(
                                    f'   Example: [{{"blank_key": "1", "answers": ["answer", "variation"]}}]'
                                )
                                logger.error(
                                    f"   Question keys present: {list(q.keys())}"
                                )
                                logger.error(f"   RAW QUESTION DATA: {q}")
                                raise ValueError(
                                    f"Question {idx + 1} missing correct_answers for completion question"
                                )
                        elif question_type == "sentence_completion":
                            # Sentence completion uses sentences array with correct_answers
                            if "sentences" not in q:
                                raise ValueError(
                                    f"Question {idx + 1} missing sentences for sentence_completion question"
                                )
                        elif question_type == "short_answer":
                            # Short answer can use questions array OR correct_answer_keys
                            if (
                                "questions" not in q
                                and not has_correct_answer_key
                                and not has_correct_answer_keys
                            ):
                                raise ValueError(
                                    f"Question {idx + 1} missing questions array or correct_answer_keys for short_answer question"
                                )
                        elif not has_correct_answer_key and not has_correct_answer_keys:
                            # Standard MCQ questions need correct_answer_keys
                            raise ValueError(
                                f"Question {idx + 1} missing correct_answer_key or correct_answer_keys"
                            )

                    # Validate options only for standard MCQ questions
                    if question_type in ["mcq", "mcq_multiple"] and "options" in q:
                        if len(q["options"]) < 2:
                            raise ValueError(
                                f"Question {idx + 1} must have at least 2 options"
                            )

                    # Normalize to correct_answer_keys array format
                    # Skip normalization for IELTS question types (matching, completion, sentence_completion, short_answer)
                    should_skip_normalization = (
                        question_type == "matching"
                        or question_type == "completion"
                        or question_type == "sentence_completion"
                        or (question_type == "short_answer" and "questions" in q)
                    )

                    if not is_diagnostic and not should_skip_normalization:
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

                        # 🔥 CRITICAL: Auto-correct question_type based on number of correct answers
                        if question_type in ["mcq", "mcq_multiple"]:
                            num_correct = len(q.get("correct_answer_keys", []))
                            if num_correct == 1 and question_type != "mcq":
                                logger.warning(
                                    f"Question {idx + 1}: Correcting question_type from '{question_type}' to 'mcq' (1 correct answer)"
                                )
                                q["question_type"] = "mcq"
                            elif num_correct > 1 and question_type != "mcq_multiple":
                                logger.warning(
                                    f"Question {idx + 1}: Correcting question_type from '{question_type}' to 'mcq_multiple' ({num_correct} correct answers)"
                                )
                                q["question_type"] = "mcq_multiple"

                    # Add question_id
                    q["question_id"] = str(ObjectId())

                # Extract diagnostic_criteria if present
                diagnostic_criteria = questions_json.get("diagnostic_criteria")

                logger.info(f"   ✅ Generated {len(questions_list)} valid questions")
                if diagnostic_criteria:
                    logger.info(
                        f"   ✅ Extracted diagnostic criteria with {len(diagnostic_criteria.get('result_types', []))} result types"
                    )

                return {
                    "questions": questions_list,
                    "diagnostic_criteria": diagnostic_criteria,
                }

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
                max_tokens=25000,
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
        topic: str = "",  # NEW: Topic/description for prompt context
        is_general_knowledge: bool = False,  # NEW: Flag for general vs document-based
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
            logger.info(f"   Is General Knowledge: {is_general_knowledge}")

            # Build prompt with language parameter
            prompt = self._build_generation_prompt(
                user_query,
                num_questions,
                content if not gemini_pdf_bytes else "",
                language,
                num_options=num_options,
                num_correct_answers=num_correct_answers,
                title=title,
                topic=topic if topic else title,
                is_general_knowledge=is_general_knowledge,
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
                    # Run blocking Gemini call in thread pool to avoid blocking event loop
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: self.client.models.generate_content(
                            model="gemini-3-pro-preview",
                            contents=contents,
                            config=types.GenerateContentConfig(
                                max_output_tokens=25000,
                                temperature=0.3,  # Low temperature for consistent output
                                response_mime_type="application/json",  # JSON Mode
                            ),
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
                        question_type = q.get("question_type", "mcq")

                        # Different question types have different required fields
                        if question_type in ["completion", "sentence_completion"]:
                            # Completion questions ONLY use IELTS format (like listening test)
                            # Format: template + blanks + correct_answers
                            if not all(
                                k in q
                                for k in ["question_text", "template", "explanation"]
                            ):
                                logger.error(
                                    f"❌ VALIDATION FAILED - Question {idx + 1} ({question_type})"
                                )
                                logger.error(
                                    f"   IELTS format requires: question_text, template, explanation"
                                )
                                logger.error(
                                    f"   Question keys present: {list(q.keys())}"
                                )
                                logger.error(f"   RAW QUESTION DATA: {q}")
                                raise ValueError(
                                    f"Question {idx + 1} missing required fields for {question_type}"
                                )
                        elif question_type == "matching":
                            # Matching questions need left_items and right_options
                            if not all(
                                k in q
                                for k in [
                                    "question_text",
                                    "left_items",
                                    "right_options",
                                    "explanation",
                                ]
                            ):
                                logger.error(
                                    f"❌ VALIDATION FAILED - Question {idx + 1} (matching)"
                                )
                                logger.error(
                                    f"   Required fields: question_text, left_items, right_options, explanation"
                                )
                                logger.error(
                                    f"   Question keys present: {list(q.keys())}"
                                )
                                logger.error(f"   RAW QUESTION DATA: {q}")
                                raise ValueError(
                                    f"Question {idx + 1} missing required fields for matching"
                                )
                        elif question_type == "short_answer":
                            # Short answer questions don't need options
                            if not all(
                                k in q for k in ["question_text", "explanation"]
                            ):
                                logger.error(
                                    f"❌ VALIDATION FAILED - Question {idx + 1} (short_answer)"
                                )
                                logger.error(
                                    f"   Required fields: question_text, explanation"
                                )
                                logger.error(
                                    f"   Question keys present: {list(q.keys())}"
                                )
                                logger.error(f"   RAW QUESTION DATA: {q}")
                                raise ValueError(
                                    f"Question {idx + 1} missing required fields for short_answer"
                                )
                        else:
                            # Standard MCQ questions need options
                            if not all(
                                k in q
                                for k in ["question_text", "options", "explanation"]
                            ):
                                raise ValueError(
                                    f"Question {idx + 1} missing required fields"
                                )

                        if question_type == "matching":
                            if "correct_matches" not in q:
                                raise ValueError(
                                    f"Question {idx + 1} missing correct_matches for matching question"
                                )
                        elif question_type == "completion":
                            # Completion questions ONLY use IELTS format
                            # Must have correct_answers array with blank_key and answers variations
                            if "correct_answers" not in q:
                                logger.error(
                                    f"❌ ANSWER VALIDATION FAILED - Question {idx + 1} (completion)"
                                )
                                logger.error(
                                    f"   Expected: correct_answers array with blank_key and answers"
                                )
                                logger.error(
                                    f'   Example: [{{"blank_key": "1", "answers": ["answer", "variation"]}}]'
                                )
                                logger.error(
                                    f"   Question keys present: {list(q.keys())}"
                                )
                                logger.error(f"   RAW QUESTION DATA: {q}")
                                raise ValueError(
                                    f"Question {idx + 1} missing correct_answers for completion question"
                                )
                        elif question_type == "sentence_completion":
                            # Sentence completion uses sentences array with correct_answers
                            if "sentences" not in q:
                                raise ValueError(
                                    f"Question {idx + 1} missing sentences for sentence_completion question"
                                )
                        elif question_type == "short_answer":
                            # Short answer can use questions array OR correct_answer_keys
                            if (
                                "questions" not in q
                                and not has_correct_answer_key
                                and not has_correct_answer_keys
                            ):
                                raise ValueError(
                                    f"Question {idx + 1} missing questions array or correct_answer_keys for short_answer question"
                                )
                        elif not has_correct_answer_key and not has_correct_answer_keys:
                            # Standard MCQ questions need correct_answer_keys
                            raise ValueError(
                                f"Question {idx + 1} missing correct_answer_key or correct_answer_keys"
                            )

                        # Validate options only for standard MCQ questions
                        if question_type in ["mcq", "mcq_multiple"] and "options" in q:
                            if len(q["options"]) < 2:
                                raise ValueError(
                                    f"Question {idx + 1} must have at least 2 options"
                                )

                        # Normalize to correct_answer_keys array format
                        # Skip normalization for IELTS question types (matching, completion, sentence_completion, short_answer)
                        should_skip_normalization = (
                            question_type == "matching"
                            or question_type == "completion"
                            or question_type == "sentence_completion"
                            or (question_type == "short_answer" and "questions" in q)
                        )

                        if not should_skip_normalization:
                            if has_correct_answer_key and not has_correct_answer_keys:
                                # Convert old format (string) to new format (array)
                                q["correct_answer_keys"] = [q["correct_answer_key"]]
                            elif has_correct_answer_keys:
                                # Ensure it's an array
                                if isinstance(q["correct_answer_keys"], str):
                                    q["correct_answer_keys"] = [
                                        q["correct_answer_keys"]
                                    ]

                            # Keep backwards compatibility: also store as correct_answer_key (first correct answer)
                            q["correct_answer_key"] = (
                                q["correct_answer_keys"][0]
                                if q["correct_answer_keys"]
                                else None
                            )

                            # 🔥 CRITICAL: Auto-correct question_type based on number of correct answers
                            if question_type in ["mcq", "mcq_multiple"]:
                                num_correct = len(q.get("correct_answer_keys", []))
                                if num_correct == 1 and question_type != "mcq":
                                    logger.warning(
                                        f"Question {idx + 1}: Correcting question_type from '{question_type}' to 'mcq' (1 correct answer)"
                                    )
                                    q["question_type"] = "mcq"
                                elif (
                                    num_correct > 1 and question_type != "mcq_multiple"
                                ):
                                    logger.warning(
                                        f"Question {idx + 1}: Correcting question_type from '{question_type}' to 'mcq_multiple' ({num_correct} correct answers)"
                                    )
                                    q["question_type"] = "mcq_multiple"

                        # Add question_id to each question
                        q["question_id"] = str(ObjectId())

                        # Map AI's "points" (1-5) → "max_points" for DB storage
                        if "points" in q and "max_points" not in q:
                            q["max_points"] = q.pop("points")

                    # 🔥 CRITICAL: Validate question count
                    if len(questions_list) != num_questions:
                        logger.error(
                            f"   ❌ Wrong question count: Expected {num_questions}, got {len(questions_list)}"
                        )
                        if attempt < self.max_retries - 1:
                            wait_time = (2**attempt) + 1
                            logger.warning(f"   ⚠️ Retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # Adjust to requested count
                            if len(questions_list) > num_questions:
                                logger.warning(
                                    f"   ⚠️ Truncating to {num_questions} questions"
                                )
                                questions_list = questions_list[:num_questions]
                            else:
                                logger.warning(
                                    f"   ⚠️ Continuing with {len(questions_list)} questions (less than requested {num_questions})"
                                )
                            questions_json["questions"] = questions_list

                    # 🔥 CRITICAL: Detect duplicate questions (AI hallucination)
                    question_texts = [
                        q.get("question_text", "") for q in questions_list
                    ]
                    unique_questions = len(set(question_texts))
                    if unique_questions < len(questions_list) * 0.8:  # >20% duplicates
                        logger.error(
                            f"   ❌ Duplicate questions detected: {len(questions_list)} total, only {unique_questions} unique"
                        )
                        if attempt < self.max_retries - 1:
                            wait_time = (2**attempt) + 1
                            logger.warning(
                                f"   ⚠️ Retrying with clearer prompt in {wait_time}s..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # Remove duplicates and continue with unique questions
                            logger.warning(
                                "   ⚠️ Removing duplicates and continuing with unique questions"
                            )
                            seen = set()
                            unique_list = []
                            for q in questions_list:
                                q_text = q.get("question_text", "")
                                if q_text not in seen:
                                    seen.add(q_text)
                                    unique_list.append(q)
                            questions_list = unique_list
                            questions_json["questions"] = questions_list

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
        # Use shared MongoDB connection (not a new client!)
        from src.services.online_test_utils import get_mongodb_service

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
        # Use shared MongoDB connection (not a new client!)
        from src.services.online_test_utils import get_mongodb_service

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
            # Get question_type (default to 'mcq' for backward compatibility)
            q_type = q.get("question_type", "mcq")

            question_data = {
                "question_id": q["question_id"],
                "question_text": q["question_text"],
                "question_type": q_type,
                "max_points": q.get("max_points", 1),
                # Do NOT include: correct_answer_key, explanation, correct_answers, correct_matches, correct_labels
            }

            # Add instruction if present (IELTS questions)
            if q.get("instruction"):
                question_data["instruction"] = q["instruction"]

            # MCQ-specific fields (both single and multiple answer)
            if q_type in ("mcq", "mcq_multiple"):
                question_data["options"] = q.get("options", [])

            # Matching-specific fields
            elif q_type == "matching":
                question_data["left_items"] = q.get("left_items", [])
                question_data["right_options"] = q.get("right_options", [])

            # Map Labeling-specific fields
            elif q_type == "map_labeling":
                question_data["diagram_url"] = q.get("diagram_url")
                question_data["diagram_description"] = q.get("diagram_description")
                question_data["label_positions"] = q.get("label_positions", [])
                question_data["options"] = q.get("options", [])

            # Completion-specific fields
            elif q_type == "completion":
                question_data["template"] = q.get("template")
                question_data["blanks"] = q.get("blanks", [])

            # Sentence Completion-specific fields
            elif q_type == "sentence_completion":
                # Remove correct_answers from sentences
                sentences = q.get("sentences", [])
                question_data["sentences"] = [
                    {
                        "key": s.get("key"),
                        "template": s.get("template"),
                        "word_limit": s.get("word_limit"),
                    }
                    for s in sentences
                ]

            # Short Answer-specific fields
            elif q_type == "short_answer":
                # Remove correct_answers from questions
                questions_list = q.get("questions", [])
                question_data["questions"] = [
                    {
                        "key": qq.get("key"),
                        "text": qq.get("text"),
                        "word_limit": qq.get("word_limit"),
                    }
                    for qq in questions_list
                ]

            # Essay-specific fields
            elif q_type == "essay":
                # Optionally include grading rubric for students to see expectations
                if q.get("grading_rubric"):
                    question_data["grading_rubric"] = q.get("grading_rubric")

            # Include media if present (for all question types)
            if q.get("media_type"):
                question_data["media_type"] = q["media_type"]
                question_data["media_url"] = q.get("media_url")
                question_data["media_description"] = q.get("media_description", "")

            # Include audio_section for listening tests
            if q.get("audio_section"):
                question_data["audio_section"] = q["audio_section"]

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

        # Get audio sections for listening tests
        audio_sections = test_doc.get("audio_sections", [])

        # Format audio sections for response (include audio_url, hide script/transcript)
        formatted_audio_sections = []
        for section in audio_sections:
            formatted_audio_sections.append(
                {
                    "section_number": section.get("section_number"),
                    "section_title": section.get("section_title"),
                    "audio_url": section.get("audio_url"),
                    "duration_seconds": section.get("duration_seconds"),
                    # Do NOT include: script, transcript (owner-only)
                }
            )

        return {
            "test_id": test_id,
            "title": test_doc["title"],
            "time_limit_minutes": test_doc["time_limit_minutes"],
            "num_questions": len(questions_for_user),
            "questions": questions_for_user,
            "attachments": formatted_attachments,  # PDF attachments for reading comprehension
            "audio_sections": formatted_audio_sections,  # Audio files for listening tests
        }

    def _build_essay_generation_prompt(
        self,
        user_query: str,
        num_questions: int,
        document_content: str,
        language: str = "vi",
        difficulty: Optional[str] = None,
    ) -> str:
        """Build prompt for essay question generation"""

        # Language instruction
        lang_instruction = f"Generate all questions, rubrics, and sample answers in {language} language."

        # Difficulty instructions
        difficulty_map = {
            "easy": "Create EASY essay questions that test basic understanding with straightforward prompts.",
            "medium": "Create MEDIUM difficulty essay questions that require analysis and explanation of concepts.",
            "hard": "Create HARD essay questions that demand critical thinking, synthesis, and in-depth analysis.",
        }
        difficulty_instruction = ""
        if difficulty and difficulty.lower() in difficulty_map:
            difficulty_instruction = (
                f"\n\n**DIFFICULTY LEVEL:** {difficulty_map[difficulty.lower()]}"
            )

        prompt = f"""You are an expert in creating educational essay assessments. Your task is to generate essay questions based on the provided document and user query.

**CRITICAL INSTRUCTIONS:**
1. Your output MUST be a single, valid JSON object.
2. {lang_instruction}
3. **⚠️ CRITICAL - QUESTION COUNT:** Generate EXACTLY {num_questions} essay questions. NO MORE, NO LESS. This is an ABSOLUTE requirement.
4. The questions must be relevant to the user's query: "{user_query}".
5. All information used to create questions must come from the provided document.
6. The JSON object must conform to the following structure:
   {{
     "questions": [
       {{
         "question_type": "essay",
         "question_text": "Essay question prompt (clear and specific)",
         "grading_rubric": "Detailed grading criteria (e.g., Content: 40%, Organization: 30%, Grammar: 30%). Specify what students should include in their answers.",
         "sample_answer": "A comprehensive sample answer demonstrating expected quality and depth."
       }}
     ]
   }}
7. Each essay question should have:
   - Clear question_text (prompt)
   - grading_rubric (detailed criteria for evaluation)
   - sample_answer (model answer for reference){difficulty_instruction}
8. Questions should test deep understanding, not just recall.
9. **VALIDATE your JSON output before returning it.**

**DOCUMENT CONTENT:**
---
{document_content}
---

Now, generate the essay questions based on the instructions and the document provided. Return ONLY the JSON object, no additional text, no markdown code blocks."""

        return prompt

    def _build_mixed_generation_prompt(
        self,
        user_query: str,
        num_mcq_questions: int,
        num_essay_questions: int,
        document_content: str,
        language: str = "vi",
        difficulty: Optional[str] = None,
        num_options: int = 4,
        num_correct_answers: int = 1,
        mcq_type_config: Optional[Dict] = None,
    ) -> str:
        """Build prompt for mixed test generation (MCQ + Essay) with MCQ type distribution support"""

        # Language instruction
        lang_instruction = f"Generate all questions, options, explanations, rubrics in {language} language."

        # Difficulty instructions
        difficulty_map = {
            "easy": "MCQ: Test basic facts. Essay: Simple explanations.",
            "medium": "MCQ: Test comprehension. Essay: Analysis and application.",
            "hard": "MCQ: Test deep analysis. Essay: Critical thinking and synthesis.",
        }
        difficulty_instruction = ""
        if difficulty and difficulty.lower() in difficulty_map:
            difficulty_instruction = (
                f"\n\n**DIFFICULTY LEVEL:** {difficulty_map[difficulty.lower()]}"
            )

        # Generate option keys
        option_keys = [chr(65 + i) for i in range(num_options)]
        option_examples = [
            f'{{"option_key": "{key}", "option_text": "string"}}' for key in option_keys
        ]
        options_example = ",\n           ".join(option_examples)

        # Correct answer instruction
        if num_correct_answers == 1:
            correct_answer_instruction = 'The "correct_answer_keys" field must be an array with exactly ONE correct option key.'
            correct_answer_example = f'"correct_answer_keys": ["{option_keys[0]}"]'
        else:
            correct_answer_instruction = f'The "correct_answer_keys" field must be an array with {num_correct_answers} correct option keys (or adjust based on question complexity).'
            correct_answer_example = (
                f'"correct_answer_keys": {option_keys[:num_correct_answers]}'
            )

        # MCQ Type Distribution Instructions (NEW)
        logger.info(f"🎯 Mixed test - MCQ type config: {mcq_type_config}")

        # Default to AUTO mode unless explicitly set to traditional/none
        if not mcq_type_config or mcq_type_config.get("distribution_mode") is None:
            # No config provided -> Default to AUTO mode
            mcq_type_config = {"distribution_mode": "auto"}
            logger.info("⚙️ Mixed test: No MCQ type config -> Defaulting to AUTO mode")

        distribution_mode = mcq_type_config.get("distribution_mode")

        # Check if using advanced MCQ type config (manual or auto)
        has_mcq_type_config = distribution_mode in ["manual", "auto"]

        mcq_type_instruction = ""
        if distribution_mode == "manual":
            # User specified exact MCQ type distribution
            type_counts = []

            if mcq_type_config.get("num_single_answer_mcq"):
                type_counts.append(
                    f"{mcq_type_config['num_single_answer_mcq']} standard MCQ with 1 correct answer"
                )

            if mcq_type_config.get("num_multiple_answer_mcq"):
                type_counts.append(
                    f"{mcq_type_config['num_multiple_answer_mcq']} MCQ with 2+ correct answers (select all that apply)"
                )

            if mcq_type_config.get("num_matching"):
                type_counts.append(
                    f"{mcq_type_config['num_matching']} matching questions (match left items to right options)"
                )

            if mcq_type_config.get("num_completion"):
                type_counts.append(
                    f"{mcq_type_config['num_completion']} completion questions (fill blanks in form/note/table)"
                )

            if mcq_type_config.get("num_sentence_completion"):
                type_counts.append(
                    f"{mcq_type_config['num_sentence_completion']} sentence completion questions"
                )

            if mcq_type_config.get("num_short_answer"):
                type_counts.append(
                    f"{mcq_type_config['num_short_answer']} short answer questions (1-3 words)"
                )

            if type_counts:
                mcq_type_instruction = f"""

**MCQ TYPE DISTRIBUTION (USER SPECIFIED):**
The {num_mcq_questions} MCQ questions should be distributed as follows:
{chr(10).join(f"- {tc}" for tc in type_counts)}

**IMPORTANT:**
- For standard MCQ with 1 correct answer: Use "question_type": "mcq" with "correct_answer_keys": ["A"]
- For MCQ with multiple correct answers: Use "question_type": "mcq_multiple" with "correct_answer_keys": ["A", "B", ...] (2+ answers)
- For matching: Use "question_type": "matching" with "left_items", "right_options", "correct_matches" fields
- For completion: Use "question_type": "completion" with "template" field containing blanks like _____(1)_____, _____(2)_____
- For sentence completion: Use "question_type": "sentence_completion" with "template" field
- For short answer: Use "question_type": "short_answer" with "correct_answer_keys" as array of acceptable answers (1-3 words)

Each MCQ question MUST include a "question_type" field to identify its type."""
                logger.info(f"✅ Manual MCQ distribution for mixed test: {type_counts}")
        elif distribution_mode == "auto":
            # AI decides optimal distribution of MCQ question types
            logger.info(
                f"🤖 Auto mode for mixed test: AI will decide MCQ type distribution"
            )
            mcq_type_instruction = f"""

**MCQ TYPE DISTRIBUTION (AI AUTO MODE):**
For the {num_mcq_questions} MCQ questions, you have flexibility to use a variety of question types:

**Available MCQ types:**
1. **Standard MCQ** ("question_type": "mcq"): Single correct answer with {num_options} options
2. **Multiple-answer MCQ** ("question_type": "mcq_multiple"): 2+ correct answers
3. **Matching** ("question_type": "matching"): Match items using "left_items", "right_options", "correct_matches"
4. **Completion** ("question_type": "completion"): Fill blanks using "template" field
5. **Sentence completion** ("question_type": "sentence_completion"): Complete sentences using "template"
6. **Short answer** ("question_type": "short_answer"): 1-3 word answers

**GUIDELINES:**
- **CRITICAL: If the user query specifies particular question formats/types, follow those specifications exactly. User requirements override these guidelines.**
- Vary MCQ question types to assess different skills
- Choose types that best fit the content (e.g., short_answer for phonetics/pronunciation/error correction, completion for cloze test)
- When user query does not specify formats, Standard MCQ can be the primary type
- Each MCQ question MUST include a "question_type" field"""
        else:
            # Traditional format: Only when explicitly set to "none" or "traditional"
            logger.info(
                f"⚙️ Traditional format for mixed test (distribution_mode={distribution_mode})"
            )
            mcq_type_instruction = f"""

**MCQ FORMAT:**
- Generate traditional multiple-choice questions with "question_type": "mcq"
- Each MCQ has {num_options} options and {num_correct_answers} correct answer(s)
- All MCQ questions follow the same format"""

        # MCQ options and correct answer instructions - adjust based on MCQ type config
        if has_mcq_type_config:
            # When MCQ type config is present, don't specify fixed num_options/num_correct_answers
            mcq_format_instruction = f"MCQ questions: {num_mcq_questions} questions. The number of options and correct answers will vary based on question type (see MCQ TYPE DISTRIBUTION section below)."
        else:
            # Traditional mode: fixed num_options and num_correct_answers
            mcq_format_instruction = f"MCQ questions: {num_mcq_questions} questions with {num_options} options each. {correct_answer_instruction}"

        prompt = f"""You are an expert in creating educational assessments. Your task is to generate a MIXED test (Multiple-Choice + Essay) based on the provided document and user query.

**🎯 PRIMARY DIRECTIVE - USER QUERY ANALYSIS:**
BEFORE generating questions, carefully analyze the user query:
"{user_query}"

**If the user query specifies particular question formats or structured sections (e.g., "PART 1: PHONETICS", "error identification", "cloze test"), you MUST:**
1. Follow those specifications EXACTLY - they override the general instructions below
2. Choose appropriate "question_type" based on format:
   - **PHONETICS / PRONUNCIATION / WORD STRESS / ERROR IDENTIFICATION**: Use "mcq" (4 options, 1 correct)
   - **CLOZE TEST**: Use "completion" (fill-in-the-blank)
   - **SENTENCE TRANSFORMATION**: Use "short_answer" (free-text with variations)
   - **READING COMPREHENSION / VOCABULARY / GRAMMAR / COMMUNICATION**: Use "mcq"
3. Structure questions according to the user's requested layout

**CRITICAL INSTRUCTIONS:**
1. Your output MUST be a single, valid JSON object.
2. {lang_instruction}
3. **⚠️ CRITICAL - QUESTION COUNT:** Generate EXACTLY {num_mcq_questions} MCQ questions AND EXACTLY {num_essay_questions} essay questions. NO MORE, NO LESS.
   - Total questions: {num_mcq_questions} + {num_essay_questions} = {num_mcq_questions + num_essay_questions}
   - These counts are ABSOLUTE and CANNOT be changed
   - NEVER generate duplicate questions - each question must be unique
4. The questions must be relevant to the user's query.
5. All information must come from the provided document.
6. The JSON object must conform to the following structure:
   {{
     "questions": [
       {{
         "question_type": "mcq",
         "question_text": "string",
         "options": [
           {options_example}
         ],
         {correct_answer_example},
         "explanation": "Explain WHY the correct answer(s) are right."
       }},
       {{
         "question_type": "essay",
         "question_text": "Essay prompt",
         "grading_rubric": "Detailed grading criteria",
         "sample_answer": "Model answer"
       }}
     ]
   }}
7. {mcq_format_instruction}
8. Essay questions: {num_essay_questions} questions with grading rubrics and sample answers.{difficulty_instruction}
10. **VALIDATE your JSON output before returning it.**
{mcq_type_instruction}

**DOCUMENT CONTENT:**
---
{document_content}
---

Now, generate the mixed test based on the instructions and the document provided. Return ONLY the JSON object, no additional text, no markdown code blocks."""

        return prompt

    async def _generate_essay_questions_with_ai(
        self,
        content: str,
        user_query: str,
        language: str,
        difficulty: Optional[str],
        num_questions: int,
        gemini_pdf_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Generate essay questions using AI"""

        prompt = self._build_essay_generation_prompt(
            user_query=user_query,
            num_questions=num_questions,
            document_content=content if not gemini_pdf_bytes else "",
            language=language,
            difficulty=difficulty,
        )

        # Response schema for essay questions
        response_schema = {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question_type": {"type": "string", "enum": ["essay"]},
                            "question_text": {"type": "string"},
                            "grading_rubric": {"type": "string"},
                            "sample_answer": {"type": "string"},
                        },
                        "required": [
                            "question_type",
                            "question_text",
                            "grading_rubric",
                        ],
                    },
                }
            },
            "required": ["questions"],
        }

        # Generate with retry
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"   Attempt {attempt + 1}/{self.max_retries}: Calling Gemini for essay questions..."
                )

                if gemini_pdf_bytes:
                    pdf_part = types.Part.from_bytes(
                        data=gemini_pdf_bytes, mime_type="application/pdf"
                    )
                    contents = [pdf_part, prompt]
                else:
                    contents = [prompt]

                # Run blocking Gemini call in thread pool to avoid blocking event loop
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model="gemini-3-pro-preview",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            max_output_tokens=25000,
                            temperature=0.3,
                            response_mime_type="application/json",
                            response_schema=response_schema,
                        ),
                    ),
                )

                if hasattr(response, "text") and response.text:
                    response_text = response.text
                    logger.info(
                        f"   ✅ Essay questions generated: {len(response_text)} characters"
                    )

                    questions_json = json.loads(response_text)
                    return questions_json
                else:
                    raise Exception("No text response from Gemini API")

            except Exception as e:
                logger.warning(f"   ⚠️ Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep((2**attempt) + 1)
                else:
                    raise

        raise Exception("Failed to generate essay questions after all retries")

    async def _generate_mixed_questions_with_ai(
        self,
        content: str,
        user_query: str,
        language: str,
        difficulty: Optional[str],
        num_mcq_questions: int,
        num_essay_questions: int,
        gemini_pdf_bytes: Optional[bytes] = None,
        num_options: int = 4,
        num_correct_answers: int = 1,
        mcq_type_config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Generate mixed questions (MCQ + Essay) using AI"""

        prompt = self._build_mixed_generation_prompt(
            user_query=user_query,
            num_mcq_questions=num_mcq_questions,
            num_essay_questions=num_essay_questions,
            document_content=content if not gemini_pdf_bytes else "",
            language=language,
            difficulty=difficulty,
            num_options=num_options,
            num_correct_answers=num_correct_answers,
            mcq_type_config=mcq_type_config,
        )

        # Response schema for mixed questions
        response_schema = {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question_type": {
                                "type": "string",
                                "enum": ["mcq", "essay"],
                            },
                            "question_text": {"type": "string"},
                            "options": {"type": "array"},
                            "correct_answer_keys": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "explanation": {"type": "string"},
                            "grading_rubric": {"type": "string"},
                            "sample_answer": {"type": "string"},
                        },
                        "required": ["question_type", "question_text"],
                    },
                }
            },
            "required": ["questions"],
        }

        # Generate with retry
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"   Attempt {attempt + 1}/{self.max_retries}: Calling Gemini for mixed questions..."
                )

                if gemini_pdf_bytes:
                    pdf_part = types.Part.from_bytes(
                        data=gemini_pdf_bytes, mime_type="application/pdf"
                    )
                    contents = [pdf_part, prompt]
                else:
                    contents = [prompt]

                # Run blocking Gemini call in thread pool to avoid blocking event loop
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model="gemini-3-pro-preview",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            max_output_tokens=25000,
                            temperature=0.3,
                            response_mime_type="application/json",
                            response_schema=response_schema,
                        ),
                    ),
                )

                if hasattr(response, "text") and response.text:
                    response_text = response.text
                    logger.info(
                        f"   ✅ Mixed questions generated: {len(response_text)} characters"
                    )

                    questions_json = json.loads(response_text)
                    return questions_json
                else:
                    raise Exception("No text response from Gemini API")

            except Exception as e:
                logger.warning(f"   ⚠️ Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep((2**attempt) + 1)
                else:
                    raise

        raise Exception("Failed to generate mixed questions after all retries")


# Singleton instance
_test_generator_service = None


def get_test_generator_service() -> TestGeneratorService:
    """Get singleton instance of TestGeneratorService"""
    global _test_generator_service
    if _test_generator_service is None:
        _test_generator_service = TestGeneratorService()
    return _test_generator_service
