"""
Gemini AI Service for Test Result Evaluation
Uses Gemini 2.5 Flash to evaluate test performance and provide feedback
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

try:
    from google import genai

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger("chatbot")


class GeminiTestEvaluationService:
    """Service for evaluating test results using Gemini AI"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini Test Evaluation Service

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)

        Raises:
            ImportError: If google-genai package not installed
            ValueError: If API key not provided
        """
        if not GENAI_AVAILABLE:
            raise ImportError(
                "google-genai package not installed. Run: pip install google-genai"
            )

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not found in environment variables. "
                "Please set GEMINI_API_KEY in your .env file."
            )

        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)

        logger.info("✅ Gemini Test Evaluation Service initialized")

    def _build_evaluation_prompt(
        self,
        test_title: str,
        test_description: str,
        questions: List[Dict[str, Any]],
        user_answers: Dict[str, str],
        score_percentage: float,
        is_passed: bool,
        evaluation_criteria: Optional[str] = None,
        language: str = "vi",
        test_category: str = "academic",
    ) -> str:
        """
        Build comprehensive prompt for test evaluation

        Args:
            test_title: Test title
            test_description: Test description
            questions: List of questions with correct answers
            user_answers: User's answers {question_id: answer}
            score_percentage: User's score percentage
            is_passed: Whether user passed
            evaluation_criteria: Custom evaluation criteria from test creator
            language: Language for AI feedback (default: "vi")
            test_category: "academic" or "personality"

        Returns:
            Complete prompt for Gemini
        """
        # Detect test type based on questions
        has_mcq = any(q.get("question_type", "mcq") == "mcq" for q in questions)
        has_essay = any(q.get("question_type") == "essay" for q in questions)

        if has_mcq and has_essay:
            test_type = "Mixed (MCQ + Essay)"
        elif has_essay:
            test_type = "Essay only"
        else:
            test_type = "MCQ only"

        # Detect test category based on description and title if not provided or default
        # Handle None values for test_description
        test_lower = (test_title + " " + (test_description or "")).lower()

        # Detect IQ test
        is_iq_test = any(
            keyword in test_lower
            for keyword in [
                "iq",
                "intelligence quotient",
                "chỉ số thông minh",
                "kiểm tra iq",
                "đo iq",
            ]
        )

        is_diagnostic_test = test_category == "diagnostic"

        # Fallback detection if category is academic but keywords suggest diagnostic
        if test_category == "academic" and any(
            keyword in test_lower
            for keyword in [
                "personality",
                "tính cách",
                "mbti",
                "16 personalities",
                "funny",
                "quiz",
                "phong cách",
                "sở thích",
                "yêu thích",
                "bạn là ai",
                "bạn thuộc típ",
                "diagnostic",
                "chẩn đoán",
            ]
        ):
            is_diagnostic_test = True

        # Calculate scoring information
        total_max_points = sum(q.get("max_points", 1) for q in questions)
        user_earned_points = 0

        # Build question analysis
        question_analysis = []
        for q in questions:
            question_id = q["question_id"]
            q_type = q.get("question_type", "mcq")
            user_answer = user_answers.get(question_id, "No answer")
            q_max_points = q.get("max_points", 1)

            if q_type == "mcq" or q_type == "mcq_multiple":
                # Get correct answer(s) - use correct_answers as primary, fallback to old fields
                correct_answer_keys = (
                    q.get("correct_answers")
                    or q.get("correct_answer_keys")
                    or [q.get("correct_answer_key")]
                )
                correct_answer = (
                    correct_answer_keys[0]
                    if len(correct_answer_keys) == 1
                    else correct_answer_keys
                )

                # For diagnostic tests, there is no "correct" answer
                # Check if user answer matches any correct answer (for single or multiple)
                if isinstance(correct_answer, list):
                    is_correct = (
                        user_answer in correct_answer
                        if not is_diagnostic_test
                        else None
                    )
                else:
                    is_correct = (
                        user_answer == correct_answer
                        if not is_diagnostic_test
                        else None
                    )

                # Track earned points
                if is_correct and not is_diagnostic_test:
                    user_earned_points += q_max_points

                # Extract options for context
                options_text = []
                for opt in q.get("options", []):
                    # Database stores as option_key/option_text (from Gemini schema)
                    key = opt.get("option_key") or opt.get("key", "")
                    text = opt.get("option_text") or opt.get("text", "")
                    options_text.append(f"{key}: {text}")

                question_analysis.append(
                    {
                        "question_id": question_id,
                        "question_type": "mcq",
                        "question_text": q["question_text"],
                        "options": options_text,
                        "user_answer": user_answer,
                        "correct_answer": (
                            correct_answer
                            if not is_diagnostic_test
                            else "N/A (Diagnostic)"
                        ),
                        "is_correct": is_correct,
                        "max_points": q_max_points,
                        "points_earned": q_max_points if is_correct else 0,
                        "explanation": q.get("explanation", "No explanation provided"),
                    }
                )
            elif q_type == "essay":
                question_analysis.append(
                    {
                        "question_id": question_id,
                        "question_type": "essay",
                        "question_text": q["question_text"],
                        "user_answer": user_answer,
                        "max_points": q_max_points,
                        "grading_rubric": q.get("grading_rubric", "No rubric provided"),
                    }
                )

            elif q_type == "true_false_multiple":
                # True/False Multiple: Multiple statements, each marked as true or false
                user_selections = user_answer if isinstance(user_answer, list) else []

                # Support both formats: options (new) and statements (legacy)
                if "options" in q and "correct_answers" in q:
                    # New format: options array with correct_answers keys
                    options = q["options"]
                    correct_keys = q["correct_answers"]

                    # Count correctness
                    correct_count = sum(
                        1 for key in user_selections if key in correct_keys
                    )
                    total_statements = len(options)

                    # Build display data
                    statements_display = []
                    for opt in options:
                        key = opt.get("option_key")
                        text = opt.get("option_text")
                        is_correct_answer = key in correct_keys
                        user_selected = key in user_selections
                        statements_display.append(
                            {
                                "key": key,
                                "text": text,
                                "correct_value": is_correct_answer,
                                "user_selected": user_selected,
                            }
                        )

                elif "statements" in q:
                    # Legacy format: statements array with correct_value fields
                    statements = q["statements"]

                    # Count correctness
                    correct_count = 0
                    for stmt in statements:
                        key = stmt.get("key")
                        correct_value = stmt.get("correct_value")
                        user_selected = key in user_selections
                        # Correct if (true statement and selected) or (false statement and not selected)
                        if (correct_value and user_selected) or (
                            not correct_value and not user_selected
                        ):
                            correct_count += 1

                    total_statements = len(statements)
                    statements_display = statements
                else:
                    # No valid format
                    logger.warning(
                        f"⚠️ Question {question_id} has no options or statements for true_false_multiple"
                    )
                    total_statements = 0
                    correct_count = 0
                    statements_display = []

                points_earned = (
                    (correct_count / total_statements * q_max_points)
                    if total_statements > 0
                    else 0
                )
                user_earned_points += points_earned

                question_analysis.append(
                    {
                        "question_id": question_id,
                        "question_type": "true_false_multiple",
                        "question_text": q["question_text"],
                        "statements": statements_display,
                        "user_selections": user_selections,
                        "correct_count": f"{correct_count}/{total_statements}",
                        "max_points": q_max_points,
                        "points_earned": round(points_earned, 2),
                        "explanation": q.get("explanation", "No explanation provided"),
                    }
                )

            # ========== IELTS QUESTION TYPES ==========
            elif q_type == "matching":
                # Matching: Match left items to right options
                user_matches = user_answer if isinstance(user_answer, dict) else {}
                # Use correct_answers as primary field, fallback to correct_matches for backward compatibility
                matches_data = q.get("correct_answers") or q.get("correct_matches", [])
                correct_matches = {m["left_key"]: m["right_key"] for m in matches_data}

                # Calculate correctness
                correct_count = sum(
                    1 for k, v in user_matches.items() if correct_matches.get(k) == v
                )
                total_items = len(q.get("left_items", []))
                points_earned = (
                    (correct_count / total_items * q_max_points)
                    if total_items > 0
                    else 0
                )
                user_earned_points += points_earned

                question_analysis.append(
                    {
                        "question_id": question_id,
                        "question_type": "matching",
                        "question_text": q["question_text"],
                        "left_items": q.get("left_items", []),
                        "right_options": q.get("right_options", []),
                        "user_matches": user_matches,
                        "correct_matches": correct_matches,
                        "correct_count": f"{correct_count}/{total_items}",
                        "max_points": q_max_points,
                        "points_earned": round(points_earned, 2),
                        "explanation": q.get("explanation", "No explanation provided"),
                    }
                )

            elif q_type == "completion":
                # Completion: Fill in blanks
                user_blanks = user_answer if isinstance(user_answer, dict) else {}
                correct_answers_list = q.get("correct_answers", [])

                # Calculate correctness (check each blank)
                correct_count = 0
                total_blanks = len(q.get("blanks", []))
                for ca in correct_answers_list:
                    # Handle both object format (correct) and string format (legacy)
                    if isinstance(ca, dict):
                        blank_key = ca.get("blank_key")
                        accepted = [
                            ans.lower().strip() for ans in ca.get("answers", [])
                        ]
                    else:
                        # Legacy format: ca is a string, use it as the answer
                        # Try to match with any blank key
                        blank_key = None
                        accepted = [str(ca).lower().strip()]

                    if blank_key:
                        user_ans = str(user_blanks.get(blank_key, "")).lower().strip()
                        if user_ans in accepted:
                            correct_count += 1

                points_earned = (
                    (correct_count / total_blanks * q_max_points)
                    if total_blanks > 0
                    else 0
                )
                user_earned_points += points_earned

                question_analysis.append(
                    {
                        "question_id": question_id,
                        "question_type": "completion",
                        "question_text": q["question_text"],
                        "template": q.get("template", ""),
                        "blanks": q.get("blanks", []),
                        "user_answers": user_blanks,
                        "correct_answers": correct_answers_list,
                        "correct_count": f"{correct_count}/{total_blanks}",
                        "max_points": q_max_points,
                        "points_earned": round(points_earned, 2),
                        "explanation": q.get("explanation", "No explanation provided"),
                    }
                )

            elif q_type == "sentence_completion":
                # Sentence completion: Complete multiple sentences
                user_sentences = user_answer if isinstance(user_answer, dict) else {}
                sentences = q.get("sentences", [])

                correct_count = 0
                for sent in sentences:
                    key = sent.get("key")
                    accepted = [
                        ans.lower().strip() for ans in sent.get("correct_answers", [])
                    ]
                    user_ans = str(user_sentences.get(key, "")).lower().strip()
                    if user_ans in accepted:
                        correct_count += 1

                total_sentences = len(sentences)
                points_earned = (
                    (correct_count / total_sentences * q_max_points)
                    if total_sentences > 0
                    else 0
                )
                user_earned_points += points_earned

                question_analysis.append(
                    {
                        "question_id": question_id,
                        "question_type": "sentence_completion",
                        "question_text": q["question_text"],
                        "sentences": sentences,
                        "user_answers": user_sentences,
                        "correct_count": f"{correct_count}/{total_sentences}",
                        "max_points": q_max_points,
                        "points_earned": round(points_earned, 2),
                        "explanation": q.get("explanation", "No explanation provided"),
                    }
                )

            elif q_type == "short_answer":
                # Short answer: Can have either questions array (IELTS) or correct_answer_keys (legacy)
                if "questions" in q:
                    # IELTS format with multiple sub-questions
                    user_short_answers = (
                        user_answer if isinstance(user_answer, dict) else {}
                    )
                    questions_list = q.get("questions", [])

                    correct_count = 0
                    for sq in questions_list:
                        key = sq.get("key")
                        accepted = [
                            ans.lower().strip() for ans in sq.get("correct_answers", [])
                        ]
                        user_ans = str(user_short_answers.get(key, "")).lower().strip()
                        if user_ans in accepted:
                            correct_count += 1

                    total_questions = len(questions_list)
                    points_earned = (
                        (correct_count / total_questions * q_max_points)
                        if total_questions > 0
                        else 0
                    )
                    user_earned_points += points_earned

                    question_analysis.append(
                        {
                            "question_id": question_id,
                            "question_type": "short_answer",
                            "question_text": q["question_text"],
                            "questions": questions_list,
                            "user_answers": user_short_answers,
                            "correct_count": f"{correct_count}/{total_questions}",
                            "max_points": q_max_points,
                            "points_earned": round(points_earned, 2),
                            "explanation": q.get(
                                "explanation", "No explanation provided"
                            ),
                        }
                    )
                else:
                    # Legacy format with single answer
                    # Use correct_answers as primary field, fallback to correct_answer_keys for backward compatibility
                    correct_answers = q.get("correct_answers") or q.get(
                        "correct_answer_keys", []
                    )
                    accepted = [ans.lower().strip() for ans in correct_answers]
                    user_ans = str(user_answer).lower().strip()
                    is_correct = user_ans in accepted

                    points_earned = q_max_points if is_correct else 0
                    user_earned_points += points_earned

                    question_analysis.append(
                        {
                            "question_id": question_id,
                            "question_type": "short_answer",
                            "question_text": q["question_text"],
                            "user_answer": user_answer,
                            "correct_answers": correct_answers,
                            "is_correct": is_correct,
                            "max_points": q_max_points,
                            "points_earned": points_earned,
                            "explanation": q.get(
                                "explanation", "No explanation provided"
                            ),
                        }
                    )

        # Build prompt based on test type
        score_display = (
            f"{score_percentage:.1f}%"
            if score_percentage is not None
            else "Pending (essay grading in progress)"
        )

        # Calculate actual score based on max_points
        actual_score_display = (
            f"{user_earned_points}/{total_max_points} points ({score_percentage:.1f}%)"
            if score_percentage is not None
            else "Pending"
        )

        prompt_parts = [
            "You are an expert educational assessment evaluator. Your task is to provide detailed, constructive feedback on a student's test performance.",
            f"**IMPORTANT:** You MUST provide your response in the following language: **{language}**.",
            "",
            "## TEST INFORMATION",
            f"**Title:** {test_title}",
            f"**Description:** {test_description or 'No description provided'}",
            f"**Test Type:** {test_type}",
            f"**Test Category:** {'Diagnostic/Quiz Test' if is_diagnostic_test else ('IQ Test' if is_iq_test else 'Knowledge Assessment')}",
            f"**Total Questions:** {len(questions)}",
            f"**Total Max Points:** {total_max_points} (each question may have different max_points)",
            f"**User Score:** {actual_score_display}",
            f"**Result:** {'PASSED ✅' if is_passed else 'FAILED ❌'}",
            "",
            "**IMPORTANT SCORING NOTE:**",
            "- Each question has a 'max_points' value (shown below)",
            "- User's final score is calculated by: (sum of earned points) / (sum of all max_points) × 100%",
            "- This is NOT a simple correct/total questions percentage!",
            "",
        ]

        # Add evaluation criteria if provided
        if evaluation_criteria:
            prompt_parts.extend(
                [
                    "## EVALUATION CRITERIA (from test creator)",
                    evaluation_criteria,
                    "",
                ]
            )

        # Add question-by-question analysis
        prompt_parts.extend(
            [
                "## DETAILED QUESTION ANALYSIS",
                "",
            ]
        )

        for idx, qa in enumerate(question_analysis, 1):
            q_type = qa.get("question_type")

            if q_type in ("mcq", "mcq_multiple"):
                status = "✅ CORRECT" if qa["is_correct"] else "❌ INCORRECT"
                points_info = (
                    f"({qa.get('points_earned', 0)}/{qa.get('max_points', 1)} points)"
                )
                prompt_parts.extend(
                    [
                        f"### Question {idx} (MCQ) {status} {points_info}",
                        f"**ID:** {qa['question_id']}",
                        f"**Question:** {qa['question_text']}",
                        f"**Options:** {'; '.join(qa.get('options', []))}",
                        f"**User's Answer:** {qa['user_answer']}",
                        f"**Correct Answer:** {qa['correct_answer']}",
                        f"**Max Points:** {qa.get('max_points', 1)}",
                        f"**Points Earned:** {qa.get('points_earned', 0)}",
                        f"**Explanation:** {qa['explanation']}",
                        "",
                    ]
                )

            elif q_type == "essay":
                prompt_parts.extend(
                    [
                        f"### Question {idx} (Essay) ⏳ PENDING OFFICIAL GRADING",
                        f"**ID:** {qa['question_id']}",
                        f"**Question:** {qa['question_text']}",
                        f"**User's Answer:** {qa['user_answer']}",
                        f"**Max Points:** {qa.get('max_points', 1)}",
                        f"**Grading Rubric:** {qa['grading_rubric']}",
                        f"**Note:** This essay answer is awaiting official scoring by the test owner. Provide informal feedback on the response quality, relevance, and content.",
                        "",
                    ]
                )

            elif q_type == "true_false_multiple":
                points_info = (
                    f"({qa.get('points_earned', 0)}/{qa.get('max_points', 1)} points)"
                )
                # Format statements
                statements_str = "; ".join(
                    [
                        f"{s.get('key')}: {s.get('text') or s.get('statement_text', '')} "
                        f"({'TRUE' if s.get('correct_value') else 'FALSE'}, "
                        f"User: {'SELECTED' if s.get('user_selected') else 'NOT SELECTED'})"
                        for s in qa.get("statements", [])
                    ]
                )

                prompt_parts.extend(
                    [
                        f"### Question {idx} (True/False Multiple) {qa['correct_count']} correct {points_info}",
                        f"**ID:** {qa['question_id']}",
                        f"**Question:** {qa['question_text']}",
                        f"**Statements:** {statements_str}",
                        f"**User's Selections:** {qa['user_selections']}",
                        f"**Score:** {qa['correct_count']}",
                        f"**Max Points:** {qa.get('max_points', 1)}",
                        f"**Points Earned:** {qa.get('points_earned', 0)}",
                        f"**Explanation:** {qa['explanation']}",
                        "",
                    ]
                )

            elif q_type == "matching":
                points_info = (
                    f"({qa.get('points_earned', 0)}/{qa.get('max_points', 1)} points)"
                )
                # Format left items and right options
                left_items_str = ", ".join(
                    [
                        f"{item['key']}: {item['text']}"
                        for item in qa.get("left_items", [])
                    ]
                )
                right_opts_str = ", ".join(
                    [
                        f"{opt['key']}: {opt['text']}"
                        for opt in qa.get("right_options", [])
                    ]
                )

                prompt_parts.extend(
                    [
                        f"### Question {idx} (Matching) {qa['correct_count']} correct {points_info}",
                        f"**ID:** {qa['question_id']}",
                        f"**Question:** {qa['question_text']}",
                        f"**Left Items:** {left_items_str}",
                        f"**Right Options:** {right_opts_str}",
                        f"**User's Matches:** {qa['user_matches']}",
                        f"**Correct Matches:** {qa['correct_matches']}",
                        f"**Score:** {qa['correct_count']}",
                        f"**Max Points:** {qa.get('max_points', 1)}",
                        f"**Points Earned:** {qa.get('points_earned', 0)}",
                        f"**Explanation:** {qa['explanation']}",
                        "",
                    ]
                )

            elif q_type == "completion":
                points_info = (
                    f"({qa.get('points_earned', 0)}/{qa.get('max_points', 1)} points)"
                )
                prompt_parts.extend(
                    [
                        f"### Question {idx} (Completion) {qa['correct_count']} correct {points_info}",
                        f"**ID:** {qa['question_id']}",
                        f"**Question:** {qa['question_text']}",
                        f"**Template:** {qa['template']}",
                        f"**User's Answers:** {qa['user_answers']}",
                        f"**Correct Answers:** {qa['correct_answers']}",
                        f"**Score:** {qa['correct_count']}",
                        f"**Max Points:** {qa.get('max_points', 1)}",
                        f"**Points Earned:** {qa.get('points_earned', 0)}",
                        f"**Explanation:** {qa['explanation']}",
                        "",
                    ]
                )

            elif q_type == "sentence_completion":
                points_info = (
                    f"({qa.get('points_earned', 0)}/{qa.get('max_points', 1)} points)"
                )
                # Format sentences
                sentences_str = ", ".join(
                    [f"{s['key']}: {s['template']}" for s in qa.get("sentences", [])]
                )

                prompt_parts.extend(
                    [
                        f"### Question {idx} (Sentence Completion) {qa['correct_count']} correct {points_info}",
                        f"**ID:** {qa['question_id']}",
                        f"**Question:** {qa['question_text']}",
                        f"**Sentences:** {sentences_str}",
                        f"**User's Answers:** {qa['user_answers']}",
                        f"**Score:** {qa['correct_count']}",
                        f"**Max Points:** {qa.get('max_points', 1)}",
                        f"**Points Earned:** {qa.get('points_earned', 0)}",
                        f"**Explanation:** {qa['explanation']}",
                        "",
                    ]
                )

            elif q_type == "short_answer":
                if "questions" in qa:
                    # IELTS format
                    points_info = f"({qa.get('points_earned', 0)}/{qa.get('max_points', 1)} points)"
                    # Format sub-questions
                    subqs_str = ", ".join(
                        [f"{sq['key']}: {sq['text']}" for sq in qa.get("questions", [])]
                    )

                    prompt_parts.extend(
                        [
                            f"### Question {idx} (Short Answer) {qa['correct_count']} correct {points_info}",
                            f"**ID:** {qa['question_id']}",
                            f"**Question:** {qa['question_text']}",
                            f"**Sub-questions:** {subqs_str}",
                            f"**User's Answers:** {qa['user_answers']}",
                            f"**Score:** {qa['correct_count']}",
                            f"**Max Points:** {qa.get('max_points', 1)}",
                            f"**Points Earned:** {qa.get('points_earned', 0)}",
                            f"**Explanation:** {qa['explanation']}",
                            "",
                        ]
                    )
                else:
                    # Legacy format
                    status = "✅ CORRECT" if qa.get("is_correct") else "❌ INCORRECT"
                    points_info = f"({qa.get('points_earned', 0)}/{qa.get('max_points', 1)} points)"
                    correct_ans_str = ", ".join(qa.get("correct_answers", []))

                    prompt_parts.extend(
                        [
                            f"### Question {idx} (Short Answer) {status} {points_info}",
                            f"**ID:** {qa['question_id']}",
                            f"**Question:** {qa['question_text']}",
                            f"**User's Answer:** {qa['user_answer']}",
                            f"**Correct Answers:** {correct_ans_str}",
                            f"**Max Points:** {qa.get('max_points', 1)}",
                            f"**Points Earned:** {qa.get('points_earned', 0)}",
                            f"**Explanation:** {qa['explanation']}",
                            "",
                        ]
                    )

        # Add evaluation instructions based on test category
        if is_diagnostic_test:
            evaluation_instructions = [
                "**EVALUATION APPROACH FOR DIAGNOSTIC/QUIZ TEST:**",
                "1. **CRITICAL - ANSWER THE MAIN QUESTION:** Look at the 'Title' of the test. If the title asks a question (e.g., 'Which Harry Potter House are you?', 'What is your spirit animal?', 'Which Zodiac sign matches you?'), your 'result_description' MUST start with a direct answer (e.g., 'You are a GRYFFINDOR!', 'Your spirit animal is a WOLF', 'You are a LEO').",
                "2. **Analyze the User's Choices:** Based on the specific options the user selected, determine the most fitting outcome/archetype/personality for them. Do not just summarize the answers; synthesize them into a specific result.",
                "3. **Structure of Feedback:**",
                "   - **Headline:** Start with the specific result (The 'Diagnosis').",
                "   - **Analysis:** Explain WHY they got this result based on their answers (e.g., 'Because you chose X and Y, it shows you value bravery...').",
                "   - **General Insight:** Add fun, lighthearted observations about this personality type.",
                "4. **Tone:** Friendly, engaging, entertaining, and non-judgmental.",
                "5. **No Study Plans:** Do NOT provide improvement recommendations.",
                "6. **Calculate an 'overall_rating' (0-10)** representing how 'strong' or 'distinct' their match to this result is.",
                "7. **Question Feedback:** In 'question_evaluations', explain what EACH specific choice reveals about their personality.",
            ]
        elif is_iq_test:
            evaluation_instructions = [
                "**EVALUATION APPROACH FOR IQ TEST:**",
                "1. This is an IQ (Intelligence Quotient) assessment test",
                "2. **CALCULATE SPECIFIC IQ SCORE:** You MUST estimate a specific integer IQ score (e.g., 105, 122, 138) based on the user's percentage score and the difficulty of questions.",
                "3. **MAPPING GUIDE:** Use this guide to map percentage to IQ range, then pick a specific number within that range based on question difficulty:",
                "   - Score < 40%: IQ 70-85 (Below Average)",
                "   - Score 40-60%: IQ 85-100 (Average)",
                "   - Score 60-75%: IQ 100-115 (Above Average)",
                "   - Score 75-85%: IQ 115-130 (Superior)",
                "   - Score 85-95%: IQ 130-145 (Very Superior/Gifted)",
                "   - Score > 95%: IQ 145+ (Highly Gifted)",
                "4. **MANDATORY:** You MUST provide at least 2 items for 'strengths', 'weaknesses', and 'recommendations'. Do not return empty arrays.",
                "5. Provide insights about cognitive strengths shown in correct answers",
                "6. Identify areas for cognitive development from incorrect answers",
                "7. Be encouraging but realistic about the IQ assessment",
                "8. **IMPORTANT: Use 'iq_score' field instead of 'overall_rating' for IQ tests**",
                "9. **Remember: Score is calculated as (earned_points / total_max_points) × 100%, not simple question count!**",
            ]
        else:
            evaluation_instructions = [
                "**EVALUATION APPROACH FOR KNOWLEDGE TEST:**",
                "1. Focus on knowledge gaps and areas needing improvement",
                "2. Provide specific study recommendations for incorrect answers",
                "3. Suggest topics and concepts to review for better performance",
                "4. Create a practical study plan to improve scores on similar tests",
                "5. Be constructive and encouraging",
                "6. For correct answers, suggest deeper understanding of concepts",
                "7. **For essay questions pending grading:** Provide informal feedback on content quality, relevance, structure, and areas to improve. Note that official scoring will be done by the test owner.",
                "8. **Calculate an 'overall_rating' (0-10)** based on their performance, question difficulty, and quality of answers.",
                "9. **Remember: Score is calculated as (earned_points / total_max_points) × 100%, not simple question count!**",
            ]

        prompt_parts.extend(
            [
                "---",
                "",
                "## YOUR TASK",
                "",
            ]
            + evaluation_instructions
            + [
                "",
                "Provide a comprehensive evaluation in JSON format with the following structure:",
                "",
                "```json",
                "{",
                '  "overall_evaluation": {',
            ]
        )

        # Different JSON structure for IQ tests
        if is_iq_test:
            prompt_parts.extend(
                [
                    '    "iq_score": 100, // REQUIRED: Specific integer IQ score (e.g., 85, 100, 115, 138). MUST NOT BE NULL.',
                    '    "iq_category": "Category name (e.g., Average, Above Average, Superior, Gifted)",',
                    '    "overall_rating": null, // Not used for IQ tests',
                ]
            )

        elif is_diagnostic_test:
            prompt_parts.extend(
                [
                    '    "result_title": "A catchy title for their result (e.g., \'The Creative Visionary\')",',
                    '    "result_description": "A detailed description of their diagnostic type or result (3-5 sentences)",',
                    '    "personality_traits": [',
                    '      "Trait 1",',
                    '      "Trait 2",',
                    '      "Trait 3"',
                    "    ],",
                    '    "advice": [',
                    '      "Fun advice item 1",',
                    '      "Fun advice item 2"',
                    "    ],",
                    '    "strengths": [],',
                    '    "weaknesses": [],',
                    '    "recommendations": [],',
                    '    "study_plan": "",',
                    '    "iq_score": null,',
                    '    "iq_category": null',
                ]
            )
        elif is_iq_test:
            prompt_parts.extend(
                [
                    '    "strengths": [',
                    '      "List 2-4 cognitive strengths demonstrated (e.g., logical reasoning, pattern recognition)",',
                    '      "Be specific about which types of problems they excelled at"',
                    "    ],",
                    '    "weaknesses": [',
                    '      "List 2-4 areas for cognitive development",',
                    '      "Be specific about which types of problems they struggled with"',
                    "    ],",
                    '    "recommendations": [',
                    '      "Provide 3-5 suggestions for improving cognitive abilities",',
                    '      "Suggest specific mental exercises, puzzle types, or learning strategies"',
                    "    ],",
                    '    "study_plan": "A practical plan for cognitive development (2-3 sentences)",',
                    '    "result_title": null,',
                    '    "result_description": null,',
                    '    "personality_traits": [],',
                    '    "advice": null',
                ]
            )
        else:
            prompt_parts.extend(
                [
                    '    "overall_rating": 0.0, // Score from 0-10 (float)',
                    '    "strengths": [',
                    '      "List 2-4 specific knowledge areas where the student performed well",',
                    '      "Be specific about which concepts they mastered"',
                    "    ],",
                    '    "weaknesses": [',
                    '      "List 2-4 specific knowledge gaps that need attention",',
                    '      "Be specific about which concepts they struggled with"',
                    "    ],",
                    '    "recommendations": [',
                    '      "Provide 3-5 actionable study recommendations",',
                    '      "Suggest specific topics to review, resources, and practice strategies"',
                    "    ],",
                    '    "study_plan": "A practical 2-3 sentence study plan to improve their score",',
                    '    "result_title": null,',
                    '    "result_description": null,',
                    '    "personality_traits": [],',
                    '    "advice": null,',
                    '    "iq_score": null,',
                    '    "iq_category": null',
                ]
            )

        prompt_parts.extend(
            [
                "  },",
                '  "question_evaluations": [',
                "    {",
                '      "question_id": "MUST_MATCH_EXACT_ID_FROM_ABOVE",',
                '      "ai_feedback": "'
                + (
                    "Fun insight about their choice (2-3 sentences)"
                    if is_diagnostic_test
                    else "Why they got it wrong/right and what to study (2-3 sentences)"
                )
                + '"',
                "    },",
                "    // ... for each question",
                "  ]",
                "}",
                "```",
                "",
                f"**CRITICAL:** This is a **{('DIAGNOSTIC/QUIZ TEST' if is_diagnostic_test else ('IQ TEST' if is_iq_test else 'KNOWLEDGE ASSESSMENT'))}**. Adjust your tone and feedback accordingly.",
                "**SCORING REMINDER:** User's score is NOT (correct_count/total_questions)%. It is calculated as (sum_of_earned_points / sum_of_max_points) × 100%.",
                "**IMPORTANT:** In 'question_evaluations', you MUST use the exact 'ID' provided for each question in the 'question_id' field. Do not use 'question_1', 'question_2', etc.",
                "**Return ONLY the JSON object, no additional text.**",
                "",
                "Now provide your evaluation:",
            ]
        )

        return "\n".join(prompt_parts)

    async def evaluate_test_result(
        self,
        test_title: str,
        test_description: str,
        questions: List[Dict[str, Any]],
        user_answers: Dict[str, str],
        score_percentage: float,
        is_passed: bool,
        evaluation_criteria: Optional[str] = None,
        language: str = "vi",
        test_category: str = "academic",
        media_attachments: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate test result using Gemini AI

        Args:
            test_title: Test title
            test_description: Test description
            questions: List of questions with answers
            user_answers: User's answers
            score_percentage: User's score percentage
            is_passed: Whether user passed
            evaluation_criteria: Optional evaluation criteria from creator
            language: Language for AI feedback (default: "vi")
            test_category: "academic" or "personality"
            media_attachments: Dict mapping question_id to list of media files
                               Format: {question_id: [{media_type, media_url, filename, ...}]}

        Returns:
            Dict with evaluation results
        """
        try:
            # Detect if test has essay questions
            has_essay = any(q.get("question_type") == "essay" for q in questions)
            has_media = media_attachments and len(media_attachments) > 0

            logger.info(f"🤖 Evaluating test result with Gemini AI")
            logger.info(f"   Test: {test_title}")
            logger.info(f"   Category: {test_category}")
            logger.info(f"   Questions: {len(questions)}")
            logger.info(f"   Has essay: {has_essay}")
            logger.info(f"   Has media: {has_media}")
            logger.info(f"   Score: {score_percentage:.1f}%")
            logger.info(f"   Language: {language}")

            # Use different evaluation path for essay tests with media
            if has_essay and has_media:
                logger.info(f"   🎯 Using essay-specific evaluation with media files")
                return await self._evaluate_essay_with_media(
                    test_title=test_title,
                    test_description=test_description,
                    questions=questions,
                    user_answers=user_answers,
                    score_percentage=score_percentage,
                    is_passed=is_passed,
                    evaluation_criteria=evaluation_criteria,
                    language=language,
                    test_category=test_category,
                    media_attachments=media_attachments,
                )

            # Standard evaluation (no media files)
            # Build prompt
            prompt = self._build_evaluation_prompt(
                test_title=test_title,
                test_description=test_description,
                questions=questions,
                user_answers=user_answers,
                score_percentage=score_percentage,
                is_passed=is_passed,
                evaluation_criteria=evaluation_criteria,
                language=language,
                test_category=test_category,
            )

            # Call Gemini API with Pro model for higher quality evaluation
            # Run in thread pool to avoid blocking event loop
            import asyncio

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=prompt,
                ),
            )

            # Extract response text
            response_text = response.text

            logger.info(f"✅ Gemini evaluation received")
            logger.info(f"📊 Response length: {len(response_text)} characters")
            logger.info(f"📝 First 500 chars: {response_text[:500]}")
            logger.info(f"📝 Last 500 chars: {response_text[-500:]}")

            # Parse JSON response
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            response_text = response_text.strip()

            try:
                evaluation_result = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini response as JSON: {e}")
                logger.error(f"Response text: {response_text[:500]}...")
                raise ValueError(f"Failed to parse AI evaluation response: {str(e)}")

            return {
                "overall_evaluation": evaluation_result.get("overall_evaluation", {}),
                "question_evaluations": evaluation_result.get(
                    "question_evaluations", []
                ),
                "model": "gemini-2.5-pro",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Gemini evaluation failed: {e}", exc_info=True)
            raise ValueError(f"Test evaluation failed: {str(e)}")

    def _build_essay_evaluation_prompt(
        self,
        test_title: str,
        test_description: str,
        questions: List[Dict[str, Any]],
        user_answers: Dict[str, str],
        score_percentage: float,
        is_passed: bool,
        evaluation_criteria: Optional[str] = None,
        language: str = "vi",
        files_by_question: Dict[str, List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Build prompt for essay evaluation with media files

        Clearly maps each file to its question for proper AI assessment.
        """
        # Detect question types
        essay_questions = [q for q in questions if q.get("question_type") == "essay"]
        mcq_questions = [
            q for q in questions if q.get("question_type") in ("mcq", "mcq_multiple")
        ]

        is_mixed = len(essay_questions) > 0 and len(mcq_questions) > 0
        test_type = "Mixed (MCQ + Essay)" if is_mixed else "Essay Only"

        # Build file reference section
        file_references = "\n\n## 📎 MEDIA FILES PROVIDED:\n\n"
        file_index = 1

        for question_id, question_files in (files_by_question or {}).items():
            # Find question details
            question_obj = next(
                (q for q in questions if q["question_id"] == question_id), None
            )
            if not question_obj:
                continue

            q_text = question_obj.get("question_text", "")[:100]
            file_references += f"**Question {question_id}** ('{q_text}...'):\n"

            for file_info in question_files:
                file_references += f"  - File #{file_index}: {file_info['filename']} ({file_info['media_type']}, {file_info['size_mb']:.2f}MB)\n"
                file_index += 1

            file_references += "\n"

        # Build question analysis section
        question_analysis_text = ""

        for idx, q in enumerate(questions, 1):
            question_id = q["question_id"]
            q_type = q.get("question_type", "mcq")
            user_answer = user_answers.get(question_id, "No answer")
            q_max_points = q.get("max_points", 1)

            question_analysis_text += f"\n### Question {idx} (ID: {question_id}, Type: {q_type}, Max Points: {q_max_points})\n\n"
            question_analysis_text += (
                f"**Question Text:**\n{q.get('question_text', 'N/A')}\n\n"
            )

            if q_type == "essay":
                grading_rubric = q.get("grading_rubric", "No rubric provided")
                question_analysis_text += f"**Grading Rubric:**\n{grading_rubric}\n\n"
                question_analysis_text += f"**Student's Answer:**\n{user_answer}\n\n"

                # Reference attached files
                if question_id in (files_by_question or {}):
                    num_files = len(files_by_question[question_id])
                    question_analysis_text += f"**📎 {num_files} file(s) attached** (see Media Files section above)\n\n"
                    question_analysis_text += f"**IMPORTANT:** When grading this essay, carefully review ALL {num_files} attached file(s). These files are part of the student's answer and must be evaluated according to the grading rubric.\n\n"

            elif q_type in ("mcq", "mcq_multiple"):
                correct_answer_keys = (
                    q.get("correct_answers")
                    or q.get("correct_answer_keys")
                    or [q.get("correct_answer_key")]
                )
                correct_answer = (
                    correct_answer_keys[0]
                    if len(correct_answer_keys) == 1
                    else correct_answer_keys
                )

                options_text = []
                for opt in q.get("options", []):
                    key = opt.get("option_key") or opt.get("key", "")
                    text = opt.get("option_text") or opt.get("text", "")
                    options_text.append(f"  {key}: {text}")

                question_analysis_text += (
                    f"**Options:**\n" + "\n".join(options_text) + "\n\n"
                )
                question_analysis_text += f"**User Selected:** {user_answer}\n"
                question_analysis_text += f"**Correct Answer:** {correct_answer}\n"
                question_analysis_text += (
                    f"**Explanation:** {q.get('explanation', 'N/A')}\n\n"
                )

        # Build language-specific instructions
        if language == "vi":
            lang_instruction = "Vui lòng phản hồi bằng tiếng Việt."
            grading_instruction = """
## YÊU CẦU CHẤM ĐIỂM:

1. **Đánh giá từng câu hỏi:**
   - MCQ: Đã được chấm tự động
   - Essay: BẠN PHẢI chấm điểm dựa trên:
     * Grading Rubric (tiêu chí chấm điểm)
     * Nội dung văn bản của học sinh
     * **TẤT CẢ CÁC FILE ĐÍNH KÈM** (hình ảnh, tài liệu, âm thanh)

2. **Cách chấm Essay:**
   - Đọc kỹ Grading Rubric
   - Xem xét câu trả lời văn bản
   - **QUAN TRỌNG:** Xem và phân tích TẤT CẢ các file đính kèm
   - Cho điểm từ 0 đến max_points
   - Giải thích rõ ràng tại sao cho điểm đó
   - Nêu điểm mạnh và điểm yếu cụ thể

3. **Tổng kết:**
   - Tính tổng điểm essay
   - Kết hợp với điểm MCQ (nếu có)
   - Đưa ra nhận xét tổng quan
"""
        else:
            lang_instruction = "Please respond in English."
            grading_instruction = """
## GRADING REQUIREMENTS:

1. **Evaluate each question:**
   - MCQ: Already auto-graded
   - Essay: YOU MUST grade based on:
     * Grading Rubric (grading criteria)
     * Student's written answer
     * **ALL ATTACHED FILES** (images, documents, audio)

2. **How to grade Essays:**
   - Read the Grading Rubric carefully
   - Review the written answer
   - **IMPORTANT:** View and analyze ALL attached files
   - Award points from 0 to max_points
   - Explain clearly why you gave that score
   - List specific strengths and weaknesses

3. **Summary:**
   - Calculate total essay score
   - Combine with MCQ score (if any)
   - Provide overall evaluation
"""

        # Evaluation criteria section
        criteria_section = ""
        if evaluation_criteria:
            criteria_section = f"\n## 📋 EVALUATION CRITERIA FROM TEST CREATOR:\n\n{evaluation_criteria}\n"

        # Build complete prompt
        prompt = f"""# TEST RESULT EVALUATION WITH MEDIA FILES

{lang_instruction}

You are an expert educator evaluating a student's test performance.

## TEST INFORMATION:
- **Title:** {test_title}
- **Description:** {test_description or 'N/A'}
- **Type:** {test_type}
- **Total Questions:** {len(questions)} ({len(essay_questions)} essay, {len(mcq_questions)} MCQ)
- **Student Score:** {score_percentage:.1f}%
- **Pass Status:** {'Passed ✅' if is_passed else 'Failed ❌'}

{file_references}

{grading_instruction}

{criteria_section}

## QUESTIONS AND ANSWERS:

{question_analysis_text}

---

## OUTPUT FORMAT (JSON):

Provide a comprehensive evaluation in the following JSON format:

```json
{{
  "overall_evaluation": {{
    "overall_rating": 0.0,  // Score from 0-10 (float number, e.g., 7.5)
    "strengths": ["strength 1", "strength 2", ...],
    "weaknesses": ["weakness 1", "weakness 2", ...],
    "recommendations": ["recommendation 1", "recommendation 2", ...],
    "study_plan": "Detailed study plan based on performance..."
  }},
  "question_evaluations": [
    {{
      "question_id": "question_id_here",
      "ai_feedback": "Detailed feedback for this specific question. For essay questions with files, MUST reference and evaluate the attached files. For MCQ, explain why the answer was correct/incorrect."
    }},
    ...
  ]
}}
```

**CRITICAL:** For essay questions with attached files, your feedback MUST include:
- Analysis of ALL attached files (images, documents, audio)
- How the files relate to the grading rubric
- Specific comments on the quality and relevance of the files
- The points awarded and justification

Begin evaluation:
"""

        return prompt

    async def _evaluate_essay_with_media(
        self,
        test_title: str,
        test_description: str,
        questions: List[Dict[str, Any]],
        user_answers: Dict[str, str],
        score_percentage: float,
        is_passed: bool,
        evaluation_criteria: Optional[str] = None,
        language: str = "vi",
        test_category: str = "academic",
        media_attachments: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate essay test with media attachments using Gemini AI

        Downloads media files and sends them with prompt for comprehensive evaluation.
        Supports multiple files per question (max 10 files/question, 50MB total).

        Args:
            Same as evaluate_test_result() but requires media_attachments

        Returns:
            Dict with evaluation results including essay-specific grading
        """
        try:
            # Download and prepare media files
            import httpx
            from google import genai
            from google.genai import types
            import io
            import asyncio

            logger.info(f"📎 Downloading media files for essay evaluation...")

            # Organize files by question
            files_by_question = {}  # {question_id: [Part objects]}
            total_size_mb = 0

            for question_id, media_list in (media_attachments or {}).items():
                question_files = []

                for idx, media in enumerate(
                    media_list[:10]
                ):  # Max 10 files per question
                    media_url = media.get("media_url")
                    media_type = media.get("media_type", "image")
                    filename = media.get("filename", f"file_{idx}")
                    file_size_mb = media.get("file_size_mb", 0)

                    # Check total size limit (50MB)
                    if total_size_mb + file_size_mb > 50:
                        logger.warning(
                            f"⚠️ Skipping file {filename}: Would exceed 50MB limit"
                        )
                        continue

                    try:
                        # Download file
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            response = await client.get(media_url)
                            response.raise_for_status()
                            file_bytes = response.content

                        # Determine MIME type
                        mime_type_map = {
                            "image": "image/jpeg",  # Default, will detect from extension
                            "audio": "audio/mpeg",
                            "document": "application/pdf",
                        }

                        # Detect from filename extension
                        if filename.lower().endswith((".png", ".PNG")):
                            mime_type = "image/png"
                        elif filename.lower().endswith(
                            (".jpg", ".jpeg", ".JPG", ".JPEG")
                        ):
                            mime_type = "image/jpeg"
                        elif filename.lower().endswith((".gif", ".GIF")):
                            mime_type = "image/gif"
                        elif filename.lower().endswith((".webp", ".WEBP")):
                            mime_type = "image/webp"
                        elif filename.lower().endswith((".mp3", ".MP3")):
                            mime_type = "audio/mpeg"
                        elif filename.lower().endswith((".wav", ".WAV")):
                            mime_type = "audio/wav"
                        elif filename.lower().endswith((".m4a", ".M4A")):
                            mime_type = "audio/mp4"
                        elif filename.lower().endswith((".pdf", ".PDF")):
                            mime_type = "application/pdf"
                        elif filename.lower().endswith((".docx", ".DOCX")):
                            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        else:
                            mime_type = mime_type_map.get(
                                media_type, "application/octet-stream"
                            )

                        # Create Gemini Part
                        part = types.Part.from_bytes(
                            data=file_bytes, mime_type=mime_type
                        )

                        question_files.append(
                            {
                                "part": part,
                                "filename": filename,
                                "media_type": media_type,
                                "size_mb": file_size_mb,
                            }
                        )

                        total_size_mb += file_size_mb
                        logger.info(
                            f"   ✅ Downloaded: {filename} ({file_size_mb:.2f}MB, {mime_type})"
                        )

                    except Exception as e:
                        logger.error(f"   ❌ Failed to download {filename}: {e}")
                        continue

                if question_files:
                    files_by_question[question_id] = question_files

            logger.info(
                f"📎 Downloaded {sum(len(f) for f in files_by_question.values())} files ({total_size_mb:.2f}MB total)"
            )

            # Build essay-specific prompt
            prompt = self._build_essay_evaluation_prompt(
                test_title=test_title,
                test_description=test_description,
                questions=questions,
                user_answers=user_answers,
                score_percentage=score_percentage,
                is_passed=is_passed,
                evaluation_criteria=evaluation_criteria,
                language=language,
                files_by_question=files_by_question,
            )

            # Prepare content for API call: [file1, file2, ..., prompt_text]
            contents = []

            # Add all files first, with clear labels
            for question_id, question_files in files_by_question.items():
                for file_info in question_files:
                    contents.append(file_info["part"])

            # Add prompt text last
            contents.append(prompt)

            logger.info(f"   🎯 Calling Gemini with {len(contents)-1} files + prompt")

            # Call Gemini API
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=contents,
                ),
            )

            # Extract and parse response
            response_text = response.text

            logger.info(f"✅ Essay evaluation with media completed")
            logger.info(f"📊 Response length: {len(response_text)} characters")

            # Parse JSON response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            response_text = response_text.strip()

            try:
                evaluation_result = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini response as JSON: {e}")
                logger.error(f"Response text: {response_text[:500]}...")
                raise ValueError(f"Failed to parse AI evaluation response: {str(e)}")

            return {
                "overall_evaluation": evaluation_result.get("overall_evaluation", {}),
                "question_evaluations": evaluation_result.get(
                    "question_evaluations", []
                ),
                "model": "gemini-2.5-pro",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Essay evaluation with media failed: {e}", exc_info=True)
            raise ValueError(f"Essay evaluation failed: {str(e)}")


# Singleton instance
_evaluation_service_instance = None


def get_gemini_evaluation_service() -> GeminiTestEvaluationService:
    """Get or create GeminiTestEvaluationService singleton"""
    global _evaluation_service_instance

    if _evaluation_service_instance is None:
        try:
            _evaluation_service_instance = GeminiTestEvaluationService()
            logger.info("✅ Created GeminiTestEvaluationService singleton")
        except Exception as e:
            logger.error(f"❌ Failed to create GeminiTestEvaluationService: {e}")
            raise

    return _evaluation_service_instance
