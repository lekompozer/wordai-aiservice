"""
Slide AI Generation Service
Service layer for AI-powered slide generation
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from google import genai
from google.genai import types
import config.config as config

logger = logging.getLogger("chatbot")


class SlideAIGenerationService:
    """Service for AI-powered slide generation"""

    def __init__(self):
        """Initialize with Gemini client"""
        self.gemini_api_key = config.GEMINI_API_KEY
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        self.client = genai.Client(api_key=self.gemini_api_key)
        self.model_name = "gemini-2.0-flash-exp"  # Gemini 2.0 Flash

    def build_analysis_prompt(
        self,
        title: str,
        target_goal: str,
        slide_type: str,
        num_slides_range: dict,
        language: str,
        user_query: str,
    ) -> str:
        """
        Build AI prompt for slide analysis (Step 1)

        Returns structured JSON with slide outline
        """

        mode_instructions = {
            "academy": """
ACADEMY MODE (Educational/Training Presentation):
- Detailed, informative content for learning
- Clear learning objectives and explanations
- Step-by-step breakdowns with examples
- Practice questions or exercises where appropriate
- 2-3 minutes per slide (comprehensive coverage)
- Focus on knowledge transfer and understanding
- Use diagrams, charts, code examples when relevant
""",
            "business": """
BUSINESS MODE (Corporate/Sales Presentation):
- Concise, impactful messaging for decision-makers
- Data-driven insights with clear metrics
- Strong call-to-action and value propositions
- Professional visuals (charts, graphs, infographics)
- 30-60 seconds per slide (fast-paced)
- Focus on persuasion, ROI, and business outcomes
- Emphasize competitive advantages and results
""",
        }

        language_names = {
            "vi": "Vietnamese (Tiếng Việt)",
            "en": "English",
            "zh": "Chinese (中文)",
        }

        return f"""You are an expert presentation designer and content strategist. Analyze the following requirements and create a detailed, structured outline for a professional slide presentation.

**PRESENTATION REQUIREMENTS:**

Title: {title}
Target Goal: {target_goal}
Presentation Type: {slide_type.upper()}
Desired Slides: {num_slides_range['min']}-{num_slides_range['max']} slides
Language: {language_names.get(language, language)}

{mode_instructions[slide_type]}

**USER CONTENT REQUIREMENTS:**
{user_query}

**YOUR TASK:**

1. Determine the optimal number of slides (MUST be between {num_slides_range['min']} and {num_slides_range['max']})
2. Create a comprehensive outline with these details for EACH slide:
   - Slide number (1-indexed)
   - Compelling slide title
   - 2-4 main content points (bullet points)
   - Suggested visual types (icons, charts, diagrams, etc.)
   - Image suggestion (topic/type of image that would enhance this slide)
   - Estimated duration in seconds (for academy mode)

3. Write a 2-3 sentence presentation summary

**OUTPUT FORMAT:**

Return ONLY valid JSON with this EXACT structure (no markdown, no code blocks):

{{
  "presentation_summary": "Brief 2-3 sentence overview of the presentation",
  "num_slides": <number between {num_slides_range['min']} and {num_slides_range['max']}>,
  "slides": [
    {{
      "slide_number": 1,
      "title": "Engaging Slide Title",
      "content_points": [
        "First key point",
        "Second key point",
        "Third key point"
      ],
      "suggested_visuals": ["icon-type", "chart-type"],
      "image_suggestion": "Description of relevant image (e.g., 'team collaboration photo', 'product mockup', 'data visualization')",
      "estimated_duration": 45
    }}
  ]
}}

**CRITICAL REQUIREMENTS:**
- Output MUST be valid JSON (no markdown formatting, no ```json blocks)
- All content MUST be in {language_names.get(language, language)}
- Follow {slide_type} mode guidelines strictly
- Be specific and actionable
- Total output under 30,000 characters
- Slide count MUST be within range: {num_slides_range['min']}-{num_slides_range['max']}

Generate the JSON now:"""

    def build_html_generation_prompt(
        self,
        slides_outline: List[dict],
        slide_type: str,
        language: str,
        title: str,
        logo_url: Optional[str],
        slide_images: Dict[int, str],  # slide_number -> image_url
        user_query: Optional[str],
        batch_number: int,
        total_batches: int,
    ) -> str:
        """
        Build AI prompt for HTML generation (Step 2)

        User query comes FIRST, then config/requirements
        Similar to test generation pattern
        """

        # Prepare slides with image URLs
        slides_with_images = []
        for slide in slides_outline:
            slide_copy = slide.copy()
            slide_num = slide["slide_number"]
            if slide_num in slide_images:
                slide_copy["provided_image_url"] = slide_images[slide_num]
            slides_with_images.append(slide_copy)

        slides_json = json.dumps(slides_with_images, ensure_ascii=False, indent=2)

        style_guidelines = {
            "academy": """
ACADEMY STYLE GUIDELINES:
- Clean, readable typography (use system fonts or web-safe fonts)
- Generous white space for better focus
- Clear heading hierarchy: h1 (48px) → h2 (36px) → p (24px)
- Bullet points with icons or emoji
- Code blocks with monospace font if applicable
- Tables for data comparison
- Color scheme: Blues (#667eea, #4c51bf) and greens (#48bb78) for trust and learning
- Emphasis on readability and comprehension
- Use flexbox for layouts
""",
            "business": """
BUSINESS STYLE GUIDELINES:
- Bold, modern sans-serif typography
- Data-driven visuals (use Unicode symbols for charts/metrics)
- Strong color contrasts for impact
- Minimal text, maximum visual impact
- Professional color palette: Navy (#1a202c), Gray (#4a5568), Accent (#667eea)
- Statistics prominently displayed with large fonts
- Gradient backgrounds for modern look
- Call-to-action elements highlighted
- Use CSS Grid or Flexbox for professional layouts
""",
        }

        # USER QUERY FIRST (like test generation)
        user_query_section = ""
        if user_query:
            user_query_section = f"""
**PRIMARY USER INSTRUCTIONS:**
{user_query}

**IMPORTANT:** Follow the user's instructions above as the PRIMARY guidance for content generation.
"""

        return f"""You are an expert HTML/CSS developer specializing in beautiful presentation slides. Generate semantic, visually appealing HTML for the following slides.

{user_query_section}

**GENERATION CONFIG:**

Batch: {batch_number} of {total_batches}
Presentation Title: {title}
Slide Type: {slide_type.upper()}
Language: {language}
{f"Logo URL: {logo_url}" if logo_url else "Logo: None provided"}

{style_guidelines[slide_type]}

**SLIDES TO GENERATE:**

```json
{slides_json}
```

**HTML GENERATION REQUIREMENTS:**

1. **Structure:** Each slide wrapped in `<div class="slide" data-slide-index="X">...</div>`
2. **Semantic HTML:** Use h1, h2, p, ul, li, blockquote, etc.
3. **Inline CSS:** All styling must be inline (no external stylesheets)
4. **Responsive:** Use flexbox/grid for layouts, percentage-based widths
5. **Visual Appeal:**
   - Use gradient backgrounds for headers
   - Add subtle shadows for depth
   - Use emoji/Unicode symbols for icons
   - Colorful accent boxes for emphasis
6. **Images:**
   - If `provided_image_url` exists, use it with proper styling
   - Position images aesthetically (side-by-side with text, full-width headers, etc.)
   - Add rounded corners, shadows to images
7. **Logo:** {f"Include logo at top-right corner of each slide using: {logo_url}" if logo_url else "No logo to include"}
8. **Language:** All content MUST be in {language}

**OUTPUT FORMAT:**

Return ONLY the HTML code. No explanations, no markdown blocks, just pure HTML.

Example structure:

<div class="slide" data-slide-index="0">
  {f'<img src="{logo_url}" style="position: absolute; top: 20px; right: 20px; width: 80px; height: auto;" alt="Logo" />' if logo_url else ''}
  <div style="display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100%; padding: 3rem;">
    <h1 style="font-size: 48px; color: #667eea; margin-bottom: 1rem; text-align: center;">Slide Title</h1>
    <ul style="font-size: 24px; line-height: 1.8; list-style: none; padding: 0;">
      <li style="margin-bottom: 1rem;">✓ First point</li>
      <li style="margin-bottom: 1rem;">✓ Second point</li>
    </ul>
  </div>
</div>

Generate beautiful, professional HTML for all slides now:"""

    async def analyze_slide_requirements(
        self,
        title: str,
        target_goal: str,
        slide_type: str,
        num_slides_range: dict,
        language: str,
        user_query: str,
    ) -> dict:
        """
        Step 1: Analyze requirements and generate structured outline

        Returns:
            dict with keys: presentation_summary, num_slides, slides
        """
        prompt = self.build_analysis_prompt(
            title=title,
            target_goal=target_goal,
            slide_type=slide_type,
            num_slides_range=num_slides_range,
            language=language,
            user_query=user_query,
        )

        logger.info(f"🤖 Calling Gemini for slide analysis...")
        logger.info(f"   Model: {self.model_name}")
        logger.info(
            f"   Slides range: {num_slides_range['min']}-{num_slides_range['max']}"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                    response_mime_type="application/json",  # Force JSON output
                ),
            )

            result_text = response.text.strip()
            logger.info(f"✅ Gemini analysis completed: {len(result_text)} chars")

            # Parse JSON
            result = json.loads(result_text)

            # Validate structure
            if "slides" not in result or "num_slides" not in result:
                raise ValueError("Invalid analysis structure")

            if len(result["slides"]) != result["num_slides"]:
                logger.warning(
                    f"⚠️ Slide count mismatch: {len(result['slides'])} vs {result['num_slides']}"
                )
                result["num_slides"] = len(result["slides"])

            logger.info(f"✅ Analysis parsed: {result['num_slides']} slides")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON: {e}")
            logger.error(f"   Response text: {result_text[:500]}...")
            raise ValueError(f"AI returned invalid JSON: {str(e)}")

        except Exception as e:
            logger.error(f"❌ Gemini analysis failed: {e}")
            raise

    async def generate_slide_html_batch(
        self,
        slides_outline: List[dict],
        slide_type: str,
        language: str,
        title: str,
        logo_url: Optional[str],
        slide_images: Dict[int, str],
        user_query: Optional[str],
        batch_number: int,
        total_batches: int,
    ) -> List[str]:
        """
        Step 2: Generate HTML for a batch of slides (up to 15)

        Returns:
            List of HTML strings for each slide
        """
        prompt = self.build_html_generation_prompt(
            slides_outline=slides_outline,
            slide_type=slide_type,
            language=language,
            title=title,
            logo_url=logo_url,
            slide_images=slide_images,
            user_query=user_query,
            batch_number=batch_number,
            total_batches=total_batches,
        )

        logger.info(
            f"🎨 Generating HTML batch {batch_number}/{total_batches} ({len(slides_outline)} slides)"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.8,  # More creative for HTML
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                ),
            )

            html_output = response.text.strip()
            logger.info(f"✅ HTML generated: {len(html_output)} chars")

            # Parse HTML into individual slides
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_output, "html.parser")
            slide_divs = soup.find_all("div", class_="slide")

            if not slide_divs:
                logger.warning("⚠️ No slides found in HTML output, using raw output")
                # Wrap in slide div if not found
                slide_divs = [
                    BeautifulSoup(
                        f'<div class="slide" data-slide-index="{i}">{html_output}</div>',
                        "html.parser",
                    ).find("div")
                    for i, _ in enumerate(slides_outline)
                ]

            # Extract and update slide indexes
            batch_start_index = slides_outline[0]["slide_number"] - 1
            slide_htmls = []

            for i, div in enumerate(slide_divs):
                div["data-slide-index"] = str(batch_start_index + i)
                slide_htmls.append(str(div))

            logger.info(f"✅ Parsed {len(slide_htmls)} slides from batch")
            return slide_htmls

        except Exception as e:
            logger.error(f"❌ HTML generation failed: {e}")
            raise


# Singleton instance
_slide_ai_service = None


def get_slide_ai_service() -> SlideAIGenerationService:
    """Get singleton instance of SlideAIGenerationService"""
    global _slide_ai_service
    if _slide_ai_service is None:
        _slide_ai_service = SlideAIGenerationService()
    return _slide_ai_service
