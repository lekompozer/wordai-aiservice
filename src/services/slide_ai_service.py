"""
Slide AI Service
AI-powered slide formatting and editing using:
- Claude 3.5 Sonnet for Format mode (layout optimization)
- Gemini 2.0 Pro 3 Preview for Edit mode (content rewriting)
"""

import os
import logging
import time
import json
from typing import Dict, Any
import anthropic

from src.models.slide_ai_models import SlideAIFormatRequest

logger = logging.getLogger("chatbot")

# Initialize AI clients
try:
    from google import genai
    from google.genai import types as genai_types

    gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    logger.info("✅ Gemini client initialized for Edit mode")
except Exception as e:
    logger.error(f"❌ Failed to initialize Gemini client: {e}")
    gemini_client = None

try:
    claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    logger.info("✅ Claude client initialized for Format mode")
except Exception as e:
    logger.error(f"❌ Failed to initialize Claude client: {e}")
    claude_client = None


class SlideAIService:
    """Service for AI-powered slide formatting and editing"""

    def __init__(self):
        """Initialize AI clients"""
        self.gemini_client = gemini_client
        self.claude_client = claude_client
        self.gemini_model = "gemini-3-pro-preview"  # Gemini Pro 3 Preview
        self.claude_model = "claude-sonnet-4-5-20250929"  # Claude Sonnet 4.5

    async def format_slide(
        self, request: SlideAIFormatRequest, user_id: str
    ) -> Dict[str, Any]:
        """
        Format slide with AI assistance

        Args:
            request: Slide formatting request
            user_id: User ID

        Returns:
            Dict with formatted_html, suggested_elements, ai_explanation, processing_time_ms
        """
        try:
            start_time = time.time()

            logger.info(f"🎨 Formatting slide {request.slide_index} for user {user_id}")
            logger.info(f"   Format type: {request.format_type}")
            logger.info(f"   Current HTML length: {len(request.current_html)} chars")
            logger.info(f"   Elements: {len(request.elements or [])}")
            logger.info(f"   Has background: {request.background is not None}")

            # Route to appropriate AI model
            if request.format_type == "format":
                # Claude 3.5 Sonnet - Better for layout/design
                ai_result = await self._format_with_claude(request)
            else:  # edit
                # Gemini Pro 3 - Better for creative writing
                ai_result = await self._edit_with_gemini(request)

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(f"✅ Slide formatted successfully in {processing_time}ms")

            return {
                "formatted_html": ai_result["formatted_html"],
                "suggested_elements": ai_result.get("suggested_elements", []),
                "suggested_background": ai_result.get("suggested_background"),
                "ai_explanation": ai_result["ai_explanation"],
                "processing_time_ms": processing_time,
            }

        except Exception as e:
            logger.error(f"❌ Failed to format slide: {e}", exc_info=True)
            raise

    async def _format_with_claude(
        self, request: SlideAIFormatRequest
    ) -> Dict[str, Any]:
        """Format slide using Claude 3.5 Sonnet (layout optimization)"""
        if not self.claude_client:
            raise ValueError("Claude client not initialized")

        prompt = self._build_format_prompt(request)

        response = self.claude_client.messages.create(
            model=self.claude_model,
            max_tokens=4096,
            temperature=0.7,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        # Parse Claude response
        response_text = response.content[0].text

        # Claude returns JSON
        result = json.loads(response_text)

        return result

    async def _edit_with_gemini(self, request: SlideAIFormatRequest) -> Dict[str, Any]:
        """Edit slide content using Gemini Pro 3 (content rewriting)"""
        if not self.gemini_client:
            raise ValueError("Gemini client not initialized")

        prompt = self._build_edit_prompt(request)

        response = self.gemini_client.models.generate_content(
            model=self.gemini_model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.8,  # Higher for creative writing
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )

        # Parse Gemini response
        result = json.loads(response.text)

        return result

    def _build_format_prompt(self, request: SlideAIFormatRequest) -> str:
        """Build prompt for Format mode (Claude 3.5 Sonnet)"""

        # Build context
        elements_info = ""
        if request.elements:
            elements_info = f"\n\nCurrent Elements ({len(request.elements)}):\n"
            for i, elem in enumerate(request.elements):
                elements_info += f"  {i+1}. {elem.type} at ({elem.position['x']}, {elem.position['y']}) - {elem.position['width']}x{elem.position['height']}\n"
                if elem.properties:
                    elements_info += f"     Properties: {elem.properties}\n"

        background_info = ""
        if request.background:
            bg = request.background
            if bg.type == "color":
                background_info = f"\n\nCurrent Background: Solid color {bg.value}"
            elif bg.type == "gradient":
                background_info = f"\n\nCurrent Background: {bg.gradient['type']} gradient with colors {bg.gradient['colors']}"
                if bg.overlayOpacity:
                    background_info += f"\n  Overlay: {bg.overlayColor or '#000000'} at {bg.overlayOpacity} opacity"
            elif bg.type == "image":
                background_info = f"\n\nCurrent Background: Image {bg.value}"
                if bg.overlayOpacity:
                    background_info += f"\n  Overlay: {bg.overlayColor or '#000000'} at {bg.overlayOpacity} opacity"

        instruction = request.user_instruction or "Improve the slide design"

        prompt = f"""You are an expert presentation designer. Your task is to improve the layout, typography, and visual hierarchy of this slide WITHOUT changing the content.

Current Slide HTML:
```html
{request.current_html}
```
{elements_info}{background_info}

User Instruction: {instruction}

Design Principles to Apply:
1. **Visual Hierarchy**: Use proper heading sizes (h1 > h2 > h3 > p), font weights, and spacing
2. **White Space**: Add appropriate margins, padding, and line-height for readability
3. **Consistency**: Maintain consistent spacing, alignment, and styling throughout
4. **Readability**: Ensure text is easy to read (font size, line height, color contrast)
5. **Modern Design**: Apply modern design patterns (semantic HTML, clean structure)

Your Response (JSON format):
{{
  "formatted_html": "Improved HTML with better structure, classes, and inline styles",
  "suggested_elements": [
    {{
      "type": "shape|image|icon|text",
      "position": {{"x": 100, "y": 200, "width": 300, "height": 50}},
      "properties": {{"color": "#667eea", "borderRadius": 12}}
    }}
  ],
  "suggested_background": {{
    "type": "gradient",
    "gradient": {{
      "type": "linear",
      "colors": ["#667eea", "#764ba2", "#f093fb"]
    }},
    "overlayOpacity": 0.15
  }},
  "ai_explanation": "Detailed explanation of layout improvements made"
}}

IMPORTANT:
- Keep ALL original text content unchanged
- Only improve HTML structure, spacing, typography
- suggested_elements and suggested_background are OPTIONAL (omit if no suggestions)
- Use semantic HTML (header, section, div with meaningful classes)
- Add inline styles or suggest CSS classes for better presentation
- Focus on visual hierarchy and readability"""

        return prompt

    def _build_edit_prompt(self, request: SlideAIFormatRequest) -> str:
        """Build prompt for Edit mode (Gemini Pro 3)"""

        instruction = request.user_instruction or "Improve the slide content"

        prompt = f"""You are an expert content writer and presentation specialist. Your task is to rewrite the slide content to make it more compelling, clear, and engaging.

Current Slide HTML:
```html
{request.current_html}
```

User Instruction: {instruction}

Content Principles:
1. **Clarity**: Make content clear and easy to understand
2. **Engagement**: Use compelling language that captures attention
3. **Structure**: Organize content logically with proper hierarchy
4. **Brevity**: Keep content concise but informative
5. **Impact**: Use power words, statistics, and specific examples

Your Response (JSON format):
{{
  "formatted_html": "Rewritten HTML with improved content",
  "ai_explanation": "Explanation of content changes made"
}}

IMPORTANT:
- Rewrite content based on user instruction
- Maintain HTML structure (keep tags like h1, p, ul, li)
- Make content more compelling and professional
- You CAN and SHOULD change the text content
- suggested_elements and suggested_background not needed for edit mode"""

        return prompt


# Singleton instance
_slide_ai_service = None


def get_slide_ai_service() -> SlideAIService:
    """Get singleton instance of SlideAIService"""
    global _slide_ai_service
    if _slide_ai_service is None:
        _slide_ai_service = SlideAIService()
    return _slide_ai_service
