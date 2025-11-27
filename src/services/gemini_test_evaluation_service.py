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

logger = logging.getLogger(__name__)


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
    ) -> str:
        """
        Build comprehensive prompt for test evaluation

        Args:
            test_title: Test title
            test_description: Test description
            questions: List of questions with correct answers
            user_answers: User's answers {question_id: answer_key}
            score_percentage: User's score percentage
            is_passed: Whether user passed
            evaluation_criteria: Custom evaluation criteria from test creator

        Returns:
            Complete prompt for Gemini
        """
        # Build question analysis
        question_analysis = []
        for q in questions:
            question_id = q["question_id"]
            user_answer = user_answers.get(question_id)
            correct_answer = q["correct_answer_key"]
            is_correct = user_answer == correct_answer

            question_analysis.append(
                {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "user_answer": user_answer or "Not answered",
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                    "explanation": q.get("explanation", "No explanation provided"),
                }
            )

        # Build prompt
        prompt_parts = [
            "You are an expert educational assessment evaluator. Your task is to provide detailed, constructive feedback on a student's test performance.",
            "",
            "## TEST INFORMATION",
            f"**Title:** {test_title}",
            f"**Description:** {test_description}",
            f"**Total Questions:** {len(questions)}",
            f"**Score:** {score_percentage:.1f}%",
            f"**Result:** {'PASSED ✅' if is_passed else 'FAILED ❌'}",
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
            status = "✅ CORRECT" if qa["is_correct"] else "❌ INCORRECT"
            prompt_parts.extend(
                [
                    f"### Question {idx} {status}",
                    f"**Question:** {qa['question_text']}",
                    f"**User's Answer:** {qa['user_answer']}",
                    f"**Correct Answer:** {qa['correct_answer']}",
                    f"**Explanation:** {qa['explanation']}",
                    "",
                ]
            )

        # Add evaluation instructions
        prompt_parts.extend(
            [
                "---",
                "",
                "## YOUR TASK",
                "",
                "Based on the above information, provide a comprehensive evaluation in JSON format with the following structure:",
                "",
                "```json",
                "{",
                '  "overall_evaluation": {',
                '    "strengths": [',
                '      "List 2-4 specific areas where the student performed well",',
                '      "Be specific about which types of questions they excelled at"',
                "    ],",
                '    "weaknesses": [',
                '      "List 2-4 specific areas that need improvement",',
                '      "Be specific about which concepts they struggled with"',
                "    ],",
                '    "recommendations": [',
                '      "Provide 3-5 actionable recommendations for improvement",',
                '      "Be specific - mention resources, topics to review, practice strategies"',
                "    ],",
                '    "study_plan": "A brief 2-3 sentence study plan based on their performance"',
                "  },",
                '  "question_evaluations": [',
                "    {",
                '      "question_id": "question_1",',
                '      "ai_feedback": "Brief feedback on why they got it wrong/right and what to focus on (2-3 sentences)"',
                "    },",
                "    // ... for each question",
                "  ]",
                "}",
                "```",
                "",
                "**IMPORTANT GUIDELINES:**",
                "1. Be constructive and encouraging, even for poor performance",
                "2. Focus on specific concepts and skills, not generic advice",
                "3. For correct answers, briefly praise and suggest deeper understanding",
                "4. For incorrect answers, explain the misconception and how to correct it",
                f"5. Consider the evaluation criteria provided by the test creator: {evaluation_criteria or 'general educational standards'}",
                "6. Tailor recommendations to the test topic and difficulty level",
                "7. Return ONLY the JSON object, no additional text",
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
            )

            logger.info(f"🤖 Evaluating test result with Gemini AI")
            logger.info(f"   Test: {test_title}")
            logger.info(f"   Questions: {len(questions)}")
            logger.info(f"   Score: {score_percentage:.1f}%")

            # Call Gemini API
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )

            # Extract response text
            response_text = response.text

            logger.info(f"✅ Gemini evaluation received")

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
