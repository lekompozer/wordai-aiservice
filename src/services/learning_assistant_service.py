"""
AI Learning Assistant Service
Uses Gemini Flash (gemini-3.1-flash-lite-preview) for:
  1. Solve Homework  — step-by-step solution with explanations
  2. Grade & Tips    — score student work + personalised study plan
"""

import os
import base64
import json
import logging
from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger(__name__)

# Prompt language helpers
_LANG_INSTRUCTION = {
    "vi": "Trả lời **bằng tiếng Việt**.",
    "en": "Respond **in English**.",
}


def _lang_hint(language: Optional[str]) -> str:
    return _LANG_INSTRUCTION.get(language or "vi", _LANG_INSTRUCTION["vi"])


class LearningAssistantService:
    """Thin wrapper around google-genai Client for learning assistant tasks."""

    FLASH_MODEL = "gemini-3.1-flash-lite-preview"

    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set in environment")

        from google import genai

        self.client = genai.Client(api_key=api_key)
        logger.info(f"LearningAssistantService initialised (model={self.FLASH_MODEL})")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_parts(
        self,
        text_parts: List[str],
        images: List[Dict[str, str]],  # [{"b64": ..., "mime": ...}]
    ) -> list:
        """Build a list of genai_types.Part for multimodal content."""
        from google.genai import types as t

        parts = []
        for img in images:
            if img.get("b64"):
                try:
                    raw = base64.b64decode(img["b64"])
                    parts.append(
                        t.Part.from_bytes(
                            data=raw,
                            mime_type=img.get("mime", "image/jpeg"),
                        )
                    )
                except Exception as exc:
                    logger.warning(f"⚠️ Could not decode image: {exc}")

        for txt in text_parts:
            if txt:
                parts.append(t.Part.from_text(text=txt))

        return parts

    def _generate(
        self,
        parts: list,
        response_schema: Dict[str, Any],
        max_tokens: int = 8192,
        temperature: float = 0.4,
    ) -> Dict[str, Any]:
        """Run synchronous generate_content and return {content, tokens}."""
        from google.genai import types as t

        config = t.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_schema,
        )

        response = self.client.models.generate_content(
            model=self.FLASH_MODEL,
            contents=parts,
            config=config,
        )

        raw_text = response.text or ""

        try:
            content = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("⚠️ Flash response is not valid JSON — returning as string")
            content = raw_text

        tokens = {}
        if response.usage_metadata:
            tokens = {
                "input": response.usage_metadata.prompt_token_count or 0,
                "output": response.usage_metadata.candidates_token_count or 0,
                "total": response.usage_metadata.total_token_count or 0,
            }

        return {"content": content, "tokens": tokens}

    # ------------------------------------------------------------------
    # Feature 1: Solve Homework
    # ------------------------------------------------------------------

    def solve_homework(
        self,
        question_text: Optional[str],
        question_image_b64: Optional[str],
        image_mime_type: str,
        subject: str,
        grade_level: str,
        language: str = "vi",
    ) -> Dict[str, Any]:
        """
        Returns a structured solution for a homework question.
        Output schema: {solution_steps, final_answer, explanation, key_formulas, study_tips}
        """
        lang = _lang_hint(language)

        system_prompt = f"""Bạn là gia sư AI chuyên nghiệp, giải bài tập cho học sinh cấp {grade_level} môn {subject}.
{lang}

QUAN TRỌNG — ĐỊNH DẠNG TOÁN HỌC:
- Viết TẤT CẢ ký hiệu toán học, công thức, phương trình dưới dạng KaTeX.
- Công thức inline (trong câu): dùng $...$ (ví dụ: $x^2 + 1$, $\\int_0^1 f(x)dx$)
- Công thức block (dòng riêng): dùng $$...$$ (ví dụ: $$\\frac{{a^2 + b^2}}{{c}}$$)
- Không dùng ký hiệu ASCII thuần như x^2, a/b, sqrt(x) — luôn dùng KaTeX.
- Áp dụng cho mọi môn: Toán, Vật lý, Hoá học, Sinh học, ...

Nhiệm vụ: Giải bài tập / câu hỏi được cung cấp. Trình bày rõ ràng, dễ hiểu cho học sinh.

Yêu cầu đầu ra JSON (nghiêm ngặt):
- solution_steps: mảng các bước giải, mỗi bước là một chuỗi (ít nhất 3 bước)
- final_answer: đáp án / kết luận cuối cùng (string)
- explanation: giải thích tại sao phương pháp này đúng (string)
- key_formulas: các công thức / định lý / quy tắc đã dùng (mảng string, dùng KaTeX)
- study_tips: mẹo ghi nhớ hoặc tránh lỗi thường gặp (mảng string)
"""

        images: List[Dict[str, str]] = []
        if question_image_b64:
            images.append({"b64": question_image_b64, "mime": image_mime_type})

        text_parts = [system_prompt]
        if question_text:
            text_parts.append(f"Câu hỏi:\n{question_text}")

        parts = self._build_parts(text_parts=text_parts, images=images)

        response_schema = {
            "type": "object",
            "properties": {
                "solution_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "final_answer": {"type": "string"},
                "explanation": {"type": "string"},
                "key_formulas": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "study_tips": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["solution_steps", "final_answer", "explanation"],
        }

        result = self._generate(
            parts=parts,
            response_schema=response_schema,
            max_tokens=4096,
            temperature=0.3,
        )

        if isinstance(result["content"], dict):
            return {
                "solution_steps": result["content"].get("solution_steps", []),
                "final_answer": result["content"].get("final_answer", ""),
                "explanation": result["content"].get("explanation", ""),
                "key_formulas": result["content"].get("key_formulas", []),
                "study_tips": result["content"].get("study_tips", []),
                "tokens": result["tokens"],
            }

        # Fallback — plain text response
        return {
            "solution_steps": [str(result["content"])],
            "final_answer": "",
            "explanation": "",
            "key_formulas": [],
            "study_tips": [],
            "tokens": result["tokens"],
        }

    # ------------------------------------------------------------------
    # Feature 2: Grade & Tips
    # ------------------------------------------------------------------

    def grade_and_tips(
        self,
        assignment_image_b64: Optional[str],
        assignment_image_mime: str,
        assignment_text: Optional[str],
        student_work_image_b64: Optional[str],
        student_work_mime: str,
        student_answer_text: Optional[str],
        subject: str,
        grade_level: str,
        language: str = "vi",
    ) -> Dict[str, Any]:
        """
        Grades student's work and returns structured feedback + study plan.
        Output schema: {score, score_breakdown, overall_feedback, strengths, weaknesses,
                        correct_solution, improvement_plan, study_plan, recommended_materials}
        """
        lang = _lang_hint(language)

        system_prompt = f"""Bạn là giáo viên AI chuyên nghiệp, chấm bài và tư vấn học tập cho học sinh cấp {grade_level} môn {subject}.
{lang}

QUAN TRỌNG — ĐỊNH DẠNG TOÁN HỌC:
- Viết TẤT CẢ ký hiệu toán học, công thức, phương trình dưới dạng KaTeX.
- Công thức inline (trong câu): dùng $...$ (ví dụ: $x^2 + 1$, $F = ma$)
- Công thức block (dòng riêng): dùng $$...$$ (ví dụ: $$E = mc^2$$)
- Không dùng ký hiệu ASCII thuần như x^2, a/b, sqrt(x) — luôn dùng KaTeX.
- Áp dụng cho mọi môn: Toán, Vật lý, Hoá học, Sinh học, ...

Nhiệm vụ: Chấm bài của học sinh DỰA TRÊN đề bài / câu hỏi được cung cấp. Cho điểm theo thang 10.

Yêu cầu đầu ra JSON (nghiêm ngặt):
- score: số thực 0-10 (ví dụ 7.5)
- score_breakdown: object với các hạng mục chấm điểm (ví dụ {{"hiểu đề": 2, "phương pháp": 4, "tính toán": 3, "trình bày": 1}})
- overall_feedback: nhận xét tổng thể về bài làm (string)
- strengths: danh sách điểm mạnh của học sinh (mảng string)
- weaknesses: danh sách lỗi sai / điểm yếu (mảng string)
- correct_solution: đáp án đúng để học sinh tham khảo (string, tóm tắt, dùng KaTeX)
- improvement_plan: các bước cụ thể học sinh cần làm để cải thiện (mảng string)
- study_plan: kế hoạch học tập theo tuần (mảng object: week, focus, activities[])
- recommended_materials: tài liệu tham khảo (mảng object: title, type, description)
"""

        images: List[Dict[str, str]] = []
        if assignment_image_b64:
            images.append({"b64": assignment_image_b64, "mime": assignment_image_mime})
        if student_work_image_b64:
            images.append({"b64": student_work_image_b64, "mime": student_work_mime})

        text_parts = [system_prompt]
        if assignment_text:
            text_parts.append(f"ĐỀ BÀI / CÂU HỎI:\n{assignment_text}")
        if student_answer_text:
            text_parts.append(f"BÀI LÀM CỦA HỌC SINH:\n{student_answer_text}")

        parts = self._build_parts(text_parts=text_parts, images=images)

        response_schema = {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "score_breakdown": {"type": "object"},
                "overall_feedback": {"type": "string"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
                "correct_solution": {"type": "string"},
                "improvement_plan": {"type": "array", "items": {"type": "string"}},
                "study_plan": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "week": {"type": "integer"},
                            "focus": {"type": "string"},
                            "activities": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
                "recommended_materials": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "type": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                },
            },
            "required": [
                "score",
                "overall_feedback",
                "strengths",
                "weaknesses",
                "improvement_plan",
            ],
        }

        result = self._generate(
            parts=parts,
            response_schema=response_schema,
            max_tokens=6144,
            temperature=0.3,
        )

        if isinstance(result["content"], dict):
            c = result["content"]
            return {
                "score": c.get("score", 0),
                "score_breakdown": c.get("score_breakdown", {}),
                "overall_feedback": c.get("overall_feedback", ""),
                "strengths": c.get("strengths", []),
                "weaknesses": c.get("weaknesses", []),
                "correct_solution": c.get("correct_solution", ""),
                "improvement_plan": c.get("improvement_plan", []),
                "study_plan": c.get("study_plan", []),
                "recommended_materials": c.get("recommended_materials", []),
                "tokens": result["tokens"],
            }

        return {
            "score": 0,
            "score_breakdown": {},
            "overall_feedback": str(result["content"]),
            "strengths": [],
            "weaknesses": [],
            "correct_solution": "",
            "improvement_plan": [],
            "study_plan": [],
            "recommended_materials": [],
            "tokens": result["tokens"],
        }
