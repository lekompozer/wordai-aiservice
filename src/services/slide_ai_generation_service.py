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
        self.model_name = "gemini-3-pro-preview"  # Gemini Pro 3 Preview

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
- Clean, readable typography (use system fonts: Arial, Helvetica, sans-serif)
- Generous white space for better focus
- Clear heading hierarchy: h1 (56px bold) → h2 (40px) → p (28px)
- Bullet points with check marks or arrows (✓ → ●)
- Color scheme options (CHOOSE ONE per slide):
  * **DARK THEME**: Background: #1a202c or #2d3748, Text: #ffffff or #f7fafc
  * **LIGHT THEME**: Background: #ffffff or #f7fafc, Text: #1a202c or #2d3748
  * **GRADIENT DARK**: Background: linear-gradient(135deg, #667eea, #764ba2), Text: #ffffff
  * **GRADIENT LIGHT**: Background: linear-gradient(135deg, #e0c3fc, #8ec5fc), Text: #1a202c
- **CRITICAL**: Text MUST have high contrast with background (never use mid-tone backgrounds)
- Emphasis on readability and comprehension
- Use flexbox for centering and layout
""",
            "business": """
BUSINESS STYLE GUIDELINES:
- Bold, modern sans-serif typography (Arial, Helvetica)
- Strong heading fonts: h1 (64px bold), h2 (48px), p (32px)
- Minimal text, maximum visual impact
- Color scheme options (CHOOSE ONE per slide):
  * **DARK THEME**: Background: #0f172a or #1e293b, Text: #ffffff or #f8fafc
  * **LIGHT THEME**: Background: #ffffff or #fafafa, Text: #0f172a or #1e293b
  * **GRADIENT DARK**: Background: linear-gradient(135deg, #0f2027, #203a43, #2c5364), Text: #ffffff
  * **GRADIENT LIGHT**: Background: linear-gradient(135deg, #ffecd2, #fcb69f), Text: #1e293b
- **CRITICAL**: Text MUST be clearly visible (white on dark, dark on light - NO exceptions)
- Professional appearance with strong contrast
- Use CSS Grid or Flexbox for modern layouts
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

1. **CRITICAL - Generate {len(slides_outline)} SEPARATE slides:**
   - You MUST create EXACTLY {len(slides_outline)} individual `<div class="slide">` elements
   - Each slide is a COMPLETE, STANDALONE HTML block
   - Do NOT merge slides together
   - Each slide should fill the entire viewport (use min-height: 100vh or height: 100%)

2. **Structure for EACH slide:**
   ```html
   <div class="slide" data-slide-index="X">
     <!-- Full slide content here -->
   </div>
   ```

3. **Inline CSS:** All styling must be inline (no external stylesheets)

4. **Color & Contrast (CRITICAL):**
   - ALWAYS choose either DARK theme or LIGHT theme for each slide
   - **DARK theme**: Background must be dark (#1a202c, #2d3748, or dark gradient), Text MUST be white/light (#ffffff, #f7fafc)
   - **LIGHT theme**: Background must be light (#ffffff, #f7fafc, or light gradient), Text MUST be dark (#1a202c, #2d3748)
   - **NEVER use mid-tone colors** (gray backgrounds with gray text, colored backgrounds without proper contrast)
   - Test: Can you read the text easily? If not, increase contrast!

5. **Layout & Spacing:**
   - Use flexbox/grid for centering: `display: flex; justify-content: center; align-items: center; height: 100%;`
   - Add generous padding: `padding: 4rem;`
   - Leave white space - don't cram content

6. **Typography:**
   - Headings: Large, bold, eye-catching (h1: 56-64px, h2: 40-48px)
   - Body text: Readable (28-32px for paragraphs)
   - Line height: 1.6-1.8 for readability

7. **Images (if provided):**
   - If `provided_image_url` exists, integrate it beautifully
   - Position: side-by-side with text OR full-width header
   - Style: `border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);`
   - Size: Proportional to content (max-width: 50% for side-by-side, 100% for full-width)

8. **Logo:** {f"Include at top-right of EACH slide: <img src='{logo_url}' style='position: absolute; top: 20px; right: 20px; width: 100px; height: auto; z-index: 10;' alt='Logo' />" if logo_url else "No logo to include"}

9. **Language:** All content MUST be in {language}

**OUTPUT FORMAT:**

Return ONLY raw HTML code. No markdown, no explanations, no ```html blocks. Just the HTML.

**EXAMPLE OUTPUT (for 3 slides):**

<div class="slide" data-slide-index="0" style="background: linear-gradient(135deg, #667eea, #764ba2); color: #ffffff; display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 100vh; padding: 4rem; position: relative;">
  {f'<img src="{logo_url}" style="position: absolute; top: 20px; right: 20px; width: 100px; height: auto; z-index: 10;" alt="Logo" />' if logo_url else ''}
  <h1 style="font-size: 64px; font-weight: bold; margin-bottom: 2rem; text-align: center; font-family: Arial, sans-serif;">First Slide Title</h1>
  <p style="font-size: 32px; text-align: center; max-width: 800px; line-height: 1.6;">Slide description or key message</p>
</div>

<div class="slide" data-slide-index="1" style="background: #ffffff; color: #1a202c; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 4rem; position: relative;">
  {f'<img src="{logo_url}" style="position: absolute; top: 20px; right: 20px; width: 100px; height: auto; z-index: 10;" alt="Logo" />' if logo_url else ''}
  <div style="max-width: 900px;">
    <h1 style="font-size: 56px; font-weight: bold; margin-bottom: 2rem; font-family: Arial, sans-serif;">Second Slide Title</h1>
    <ul style="font-size: 28px; line-height: 1.8; list-style: none; padding: 0;">
      <li style="margin-bottom: 1.5rem;">✓ First key point</li>
      <li style="margin-bottom: 1.5rem;">✓ Second key point</li>
      <li style="margin-bottom: 1.5rem;">✓ Third key point</li>
    </ul>
  </div>
</div>

<div class="slide" data-slide-index="2" style="background: #0f172a; color: #ffffff; display: flex; justify-content: space-between; align-items: center; min-height: 100vh; padding: 4rem; position: relative;">
  {f'<img src="{logo_url}" style="position: absolute; top: 20px; right: 20px; width: 100px; height: auto; z-index: 10;" alt="Logo" />' if logo_url else ''}
  <div style="flex: 1; padding-right: 2rem;">
    <h1 style="font-size: 56px; font-weight: bold; margin-bottom: 2rem; font-family: Arial, sans-serif;">Third Slide Title</h1>
    <p style="font-size: 28px; line-height: 1.6;">Content description here</p>
  </div>
  <img src="IMAGE_URL_HERE" style="flex: 1; max-width: 45%; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.3);" alt="Visual" />
</div>

**NOW GENERATE {len(slides_outline)} BEAUTIFUL, WELL-CONTRASTED, SEPARATE SLIDES:**"""

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
