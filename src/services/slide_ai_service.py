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

        # Log prompt size for debugging
        logger.info(
            f"📊 Prompt size: {len(prompt)} chars, HTML size: {len(request.current_html)} chars"
        )

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

        # Debug: Log response for troubleshooting
        logger.debug(f"Claude response length: {len(response_text)} chars")
        if not response_text or not response_text.strip():
            logger.error("❌ Claude returned empty response")
            logger.error(f"Full response object: {response}")
            raise ValueError("Claude API returned empty response")

        # Try to parse JSON with better error handling
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse Claude response as JSON: {e}")
            logger.error(f"Response text (first 500 chars): {response_text[:500]}")
            # Try to extract JSON from markdown code blocks if present
            import re

            # Try different patterns
            # Pattern 1: ```json ... ```
            json_match = re.search(
                r"```json\s*(\{.+?\})\s*```", response_text, re.DOTALL
            )
            if not json_match:
                # Pattern 2: ``` ... ``` (without json keyword)
                json_match = re.search(
                    r"```\s*(\{.+?\})\s*```", response_text, re.DOTALL
                )
            if not json_match:
                # Pattern 3: Look for content between ```json and ``` without requiring { }
                json_match = re.search(
                    r"```json\s*(.+?)\s*```", response_text, re.DOTALL
                )
            if not json_match:
                # Pattern 4: Any content between ``` markers
                json_match = re.search(r"```\s*(.+?)\s*```", response_text, re.DOTALL)

            if json_match:
                logger.info("✅ Found JSON in markdown code block, extracting...")
                extracted_json = json_match.group(1).strip()
                logger.debug(f"Extracted JSON length: {len(extracted_json)} chars")
                try:
                    result = json.loads(extracted_json)
                except json.JSONDecodeError as e2:
                    logger.error(f"❌ Failed to parse extracted JSON: {e2}")
                    raise
            else:
                logger.error("❌ No JSON found in markdown code blocks either")
                raise

        # Post-process: Ensure formatted_html has proper wrapper structure
        if "formatted_html" in result:
            html = result["formatted_html"]
            # Check if HTML already has slide-page wrapper
            if not html.strip().startswith('<div class="slide-page">'):
                logger.warning("⚠️ Claude response missing wrapper, adding manually...")
                # Wrap the HTML in proper structure
                result["formatted_html"] = (
                    f'<div class="slide-page">\n  <div class="slide-wrapper">\n{html}\n  </div>\n</div>'
                )
                logger.info("✅ Added slide-page wrapper to formatted HTML")

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

        # Check if this is a batch with multiple slides
        import re

        slide_markers = re.findall(r"<!-- Slide (\d+) -->", request.current_html)
        is_batch = len(slide_markers) > 1

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

        # Different prompt for batch vs single slide
        if is_batch:
            prompt = f"""You are an expert presentation designer. Your task is to improve the layout, typography, and visual hierarchy of MULTIPLE SLIDES WITHOUT changing the content.

I'm providing {len(slide_markers)} slides separated by markers like "<!-- Slide 0 -->", "<!-- Slide 1 -->", etc.

Current Slides HTML:
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
6. **Background (Consistency)**: Keep existing background theme consistent across all slides
   - ❌ FORBIDDEN: Purple gradients (#667eea, #764ba2), multiple different backgrounds per slide
   - ✅ PRESERVE: Use same background for all content slides (dark or light)
7. **DIMENSIONS (Full HD 16:9)**: Each slide-wrapper MUST be exactly 1920px × 1080px
   - Use: `width: 1920px; height: 1080px; min-height: 1080px; max-height: 1080px; overflow: hidden; position: relative;`
   - All content must fit within this 1920×1080 canvas
8. **Typography**: Prefer 'Inter', 'SF Pro Display', 'Segoe UI', Arial, sans-serif for modern, clean look

REQUIRED OUTPUT STRUCTURE for each slide:
```html
<!-- Slide X -->
<div class="slide-page">
  <div class="slide-wrapper" style="width: 1920px; height: 1080px; min-height: 1080px; max-height: 1080px; overflow: hidden; position: relative; font-family: 'Inter', 'SF Pro Display', sans-serif;">
    <!-- Your improved content here -->
  </div>
</div>
```

Your Response (JSON format):
{{
  "formatted_html": "Improved HTML with ALL {len(slide_markers)} slides wrapped in proper containers",
  "ai_explanation": "Summary of layout improvements made across all slides"
}}

CRITICAL REQUIREMENTS - FORMAT MODE (PRESERVE CONTENT):
- Process ALL {len(slide_markers)} slides in the input
- ⚠️ **CRITICAL**: Keep ALL original text content UNCHANGED - only improve layout and styling
- DO NOT rewrite, add, or remove any text content from the slides
- PRESERVE the "<!-- Slide X -->" markers to separate slides
- WRAP each slide's content in: <div class="slide-page"><div class="slide-wrapper" style="font-family: 'Inter', 'SF Pro Display', sans-serif;">...content...</div></div>
- Output format: <!-- Slide 0 -->\n<div class="slide-page"><div class="slide-wrapper">...improved html...</div></div>\n\n<!-- Slide 1 -->\n<div class="slide-page"><div class="slide-wrapper">...improved html...</div></div>\n...
- Only improve HTML structure, spacing, typography inside the slide-wrapper
- Use semantic HTML, Inter font family, and inline styles for better presentation

FORBIDDEN ELEMENTS (DO NOT USE):
- ❌ NO <svg> tags or SVG elements (use CSS shapes with div/borders instead)
- ❌ NO <polygon>, <path>, <circle> in SVG (causes parsing errors)
- ❌ NO percentage values in SVG attributes (e.g., points="80%,10%")
- ❌ NO complex decorative SVG graphics
- ✅ USE: Simple <div> with border, border-radius, transform for shapes
- ✅ USE: CSS gradients, box-shadow for visual effects"""
        else:
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
6. **Background (Consistency)**: Keep existing background theme (dark/light), avoid changing to purple/blue gradients
   - ❌ FORBIDDEN: Purple gradients (#667eea, #764ba2), changing dark to light or vice versa
   - ✅ PRESERVE: Existing background color scheme
7. **DIMENSIONS (Full HD 16:9)**: Ensure slide-wrapper is exactly 1920px × 1080px
   - Use: `width: 1920px; height: 1080px; min-height: 1080px; max-height: 1080px; overflow: hidden; position: relative;`
   - All content must fit within this 1920×1080 canvas
8. **Typography**: Prefer 'Inter', 'SF Pro Display', 'Segoe UI', Arial, sans-serif for modern, clean look

REQUIRED OUTPUT STRUCTURE:
```html
<div class="slide-page">
  <div class="slide-wrapper" style="width: 1920px; height: 1080px; min-height: 1080px; max-height: 1080px; overflow: hidden; position: relative; font-family: 'Inter', 'SF Pro Display', sans-serif;">
    <!-- Your improved content here -->
  </div>
</div>
```

Your Response (JSON format):
{{
  "formatted_html": "Improved HTML wrapped in <div class='slide-page'><div class='slide-wrapper'>...improved content...</div></div>",
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

IMPORTANT - FORMAT MODE (PRESERVE CONTENT):
- ⚠️ **CRITICAL**: Keep ALL original text content UNCHANGED - only improve layout, spacing, and styling
- DO NOT rewrite, add, or remove any text content
- MUST wrap output in: <div class="slide-page"><div class="slide-wrapper" style="font-family: 'Inter', 'SF Pro Display', sans-serif;">...content...</div></div>
- Only improve HTML structure, spacing, typography INSIDE the slide-wrapper
- suggested_elements and suggested_background are OPTIONAL (omit if no suggestions)
- Use semantic HTML (header, section, div with meaningful classes)
- Add inline styles for better presentation (colors, spacing, typography)
- Focus on visual hierarchy and readability
- Make the slide look professional and modern with Inter font family

FORBIDDEN ELEMENTS (DO NOT USE):
- ❌ NO <svg> tags or any SVG elements (causes parsing errors)
- ❌ NO <polygon>, <path>, <circle>, or any SVG shapes
- ❌ NO percentage values in any attributes (e.g., points="80%,10%")
- ❌ NO complex decorative SVG graphics or inline event handlers
- ✅ USE: Simple <div> elements with CSS styling (border, border-radius, transform)
- ✅ USE: CSS for shapes (e.g., border + transform: rotate() for triangles)
- ✅ USE: background gradients, box-shadow, and other CSS effects
- ✅ EXAMPLE: <div style="width: 100px; height: 100px; border: 2px solid #ccc; transform: rotate(45deg);"></div>"""

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
