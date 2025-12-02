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

            if q_type == "mcq":
                correct_answer = q.get("correct_answer_key", "N/A")
                # For diagnostic tests, there is no "correct" answer
                is_correct = (
                    user_answer == correct_answer if not is_diagnostic_test else None
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
            if qa.get("question_type") == "mcq":
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
            elif qa.get("question_type") == "essay":
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

        # Add evaluation instructions based on test category
        if is_diagnostic_test:
            evaluation_instructions = [
                "**EVALUATION APPROACH FOR DIAGNOSTIC/QUIZ TEST:**",
                "1. This is a diagnostic or fun quiz test - provide lighthearted, objective commentary",
                "2. Focus on analyzing the pattern of choices and what they reveal",
                "3. Avoid being judgmental - diagnostic tests have no 'wrong' answers",
                "4. Provide interesting insights about the user's choices",
                "5. Keep the tone friendly, engaging, and entertaining",
                "6. Don't provide 'study plans' or 'improvement recommendations' - this isn't a knowledge test",
                "7. Instead, provide fun observations and what their results might say about them",
                "8. **Calculate an 'overall_rating' (0-10)** representing how 'strong' or 'distinct' their personality/result type is.",
                "9. **CRITICAL:** You MUST provide specific 'ai_feedback' for EACH question in the 'question_evaluations' array. Explain what their specific choice for that question implies about them.",
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

        Returns:
            Dict with evaluation results
        """
        try:
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

            logger.info(f"🤖 Evaluating test result with Gemini AI")
            logger.info(f"   Test: {test_title}")
            logger.info(f"   Category: {test_category}")
            logger.info(f"   Questions: {len(questions)}")
            logger.info(f"   Score: {score_percentage:.1f}%")
            logger.info(f"   Language: {language}")

            # Call Gemini API
            response = self.client.models.generate_content(
                model="gflashemini-2.5-",
                contents=prompt,
            )

            # Extract response text
            response_text = response.text

            logger.info(f"✅ Gemini evaluation received")
            logger.info(f"📝 Response preview (first 500 chars): {response_text[:500]}")

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
                "model": "gemini-2.5-flash",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Gemini evaluation failed: {e}", exc_info=True)
            raise ValueError(f"Test evaluation failed: {str(e)}")


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
