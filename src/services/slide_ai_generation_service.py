"""
Slide AI Generation Service
Service layer for AI-powered slide generation
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import os

from google import genai  # type: ignore
from google.genai import types  # type: ignore
from anthropic import AnthropicVertex, Anthropic
import config.config as config

logger = logging.getLogger("chatbot")


class SlideAIGenerationService:
    """Service for AI-powered slide generation"""

    def __init__(self):
        """Initialize with Gemini (Step 1) and Claude (Step 2) clients"""
        # Gemini for outline generation (Step 1)
        self.gemini_api_key = config.GEMINI_API_KEY
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        self.gemini_model = "gemini-3-pro-preview"  # Gemini Pro 3 Preview

        # Claude for HTML generation (Step 2) - Try Vertex AI first, fallback to API
        try:
            # Try Vertex AI first (cheaper: 2 points/batch)
            project_id = os.getenv("FIREBASE_PROJECT_ID", "wordai-6779e")
            region = os.getenv("VERTEX_AI_REGION", "asia-southeast1")

            # Check for credentials file
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not credentials_path:
                credentials_path = "/app/wordai-6779e-ed6189c466f1.json"
                if os.path.exists(credentials_path):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

            self.claude_client = AnthropicVertex(project_id=project_id, region=region)
            self.claude_provider = "vertex"
            self.claude_model = "claude-sonnet-4-5@20250929"  # Vertex AI format
            logger.info(
                f"✅ Claude Vertex AI initialized for slide generation (project={project_id}, region={region})"
            )

        except Exception as vertex_error:
            logger.warning(f"⚠️ Failed to initialize Claude Vertex AI: {vertex_error}")
            logger.info("🔄 Falling back to Claude API for slide generation...")

            # Fallback to direct Anthropic API (5 points/batch)
            self.claude_api_key = os.getenv("ANTHROPIC_API_KEY")
            if not self.claude_api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured and Vertex AI unavailable")
            
            self.claude_client = Anthropic(api_key=self.claude_api_key)
            self.claude_provider = "api"
            self.claude_model = "claude-sonnet-4-5-20250929"  # Standard API format
            logger.info("✅ Claude API initialized for slide generation (fallback mode)")

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
        first_slide_sample: Optional[str] = None,  # Style reference from batch 1
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

        # Determine topic-based theme recommendation
        topic_lower = title.lower() + " " + target_goal.lower() + " " + (user_query or "").lower()
        is_tech_topic = any(keyword in topic_lower for keyword in [
            "technology", "tech", "ai", "machine learning", "artificial intelligence",
            "programming", "coding", "software", "cybersecurity", "security",
            "crypto", "blockchain", "encryption", "data science", "cloud computing",
            "digital", "innovation", "automation", "robotics"
        ])

        style_guidelines = {
            "academy": f"""
ACADEMY STYLE GUIDELINES:
- Clean, readable typography (use system fonts: Arial, Helvetica, sans-serif)
- Generous white space for better focus
- Clear heading hierarchy: h1 (56px bold) → h2 (40px) → p (28px)
- Bullet points with check marks or arrows (✓ → ●)
- **THEME SELECTION - IMPORTANT:**
  * **DEFAULT (RECOMMENDED)**: LIGHT THEME - Best for educational content
  * **LIGHT THEME**: Background: #ffffff or #f7fafc, Text: #1a202c or #2d3748
  * **GRADIENT LIGHT**: Background: linear-gradient(135deg, #e0c3fc, #8ec5fc), Text: #1a202c
  * DARK THEME ONLY IF: Technology, programming, security, or crypto topics
  * **DARK THEME**: Background: #1a202c or #2d3748, Text: #ffffff or #f7fafc
- **CRITICAL**: Text MUST have high contrast with background (never use mid-tone backgrounds)
- Emphasis on readability and comprehension
- Use flexbox for centering and layout
""",
            "business": f"""
BUSINESS STYLE GUIDELINES:
- Bold, modern sans-serif typography (Arial, Helvetica)
- Strong heading fonts: h1 (64px bold), h2 (48px), p (32px)
- Minimal text, maximum visual impact
- **THEME SELECTION - CRITICAL:**
  * **STRONGLY PREFER LIGHT THEME** for business/economics/management content
  * **LIGHT THEME (DEFAULT)**: Background: #ffffff or #fafafa, Text: #0f172a or #1e293b
  * **GRADIENT LIGHT (PROFESSIONAL)**: Background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%), Text: #1e293b
  * ✅ Use LIGHT for: Business strategy, finance, economics, management, marketing, sales
  * ❌ DARK THEME ONLY for: Technology, cybersecurity, crypto, blockchain, AI/ML topics
  * **DARK THEME**: Background: #0f172a or #1e293b, Text: #ffffff (RARE - tech topics only)
  * **Current presentation topic**: {'Technology-related - Dark theme OK' if is_tech_topic else 'Business/Academic - PREFER LIGHT THEME'}
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

        # STYLE CONSISTENCY: If batch > 1, show example from batch 1
        style_reference = ""
        if batch_number > 1 and first_slide_sample:
            style_reference = f"""
**CRITICAL - STYLE CONSISTENCY:**
This is batch {batch_number} of {total_batches}. You MUST maintain the EXACT SAME visual style as the previous batch.

Here is a sample slide from batch 1 for reference:
```html
{first_slide_sample[:2000]}
```

**EXTRACT AND REPLICATE:**
- Background color/gradient (MUST be identical)
- Text colors and font sizes
- Layout spacing and padding
- Element positioning style
- Slide number position and format

DO NOT change the visual style - only the content should be different!
"""

        return f"""You are an expert HTML/CSS developer specializing in beautiful presentation slides. Generate semantic, visually appealing HTML for the following slides.

{user_query_section}

{style_reference}

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
   - **DIMENSIONS (FULL HD 16:9)**: Each slide MUST be exactly 1920px width × 1080px height
   - Use: `width: 1920px; height: 1080px; min-height: 1080px; max-height: 1080px; overflow: hidden;`
   - All content must fit within this 1920×1080 canvas - use absolute positioning for precise layout
   - **CRITICAL - VERTICAL CENTERING**:
     * Content MUST be vertically centered within the 1080px height
     * Use flexbox: `display: flex; flex-direction: column; justify-content: center; align-items: center;`
     * Do NOT just ensure 25px from bottom - the content should be CENTERED vertically
     * Minimum 25px clearance from bottom edge is a safety measure, not the primary goal
     * Example: Content should be roughly y=200-880px (centered in 1080px), not starting at y=100 and ending at y=1055
   - **LAYOUT SYMMETRY & SPACING**:
     * Total padding-left + margin-left MUST EQUAL total padding-right + margin-right
     * Content must be centered horizontally within the 1920px width
     * All content height must fit within 1080px with minimum 25px bottom clearance
     * Example: If padding: 60px 80px, then left (80px) = right (80px) ✅

2. **Structure for EACH slide:**
   ```html
   <div class="slide" data-slide-index="X">
     <!-- Full slide content here -->
   </div>
   ```

3. **Inline CSS:** All styling must be inline (no external stylesheets)

4. **Color & Background (CRITICAL - Consistency):**
   - **CHOOSE ONE THEME** for ALL slides: Either DARK or LIGHT (don't mix)
   - **DARK theme**: Background #0f172a or #1a202c (solid dark), Text white (#ffffff, #f7fafc)
   - **LIGHT theme**: Background #ffffff or #f7fafc (solid light), Text dark (#1a202c, #2d3748)
   - ❌ **FORBIDDEN**: Purple/blue gradients (#667eea, #764ba2), mid-tone colors, multiple different backgrounds
   - ✅ **ALLOWED**: Use same background for ALL content slides, optionally different for title slide & thank you slide only
   - Example: Dark (#0f172a) for all slides, or Light (#ffffff) for content + gradient for title/thank-you
   - Test: Can you read the text easily? Ensure high contrast!

5. **Slide Numbers (REQUIRED):**
   - Add slide number to top-right or bottom-right corner of EVERY slide
   - **SKIP slide number on**: Title slide (slide 0) only
   - Format: `<div style="position: absolute; top: 40px; right: 60px; font-size: 24px; opacity: 0.6;">02</div>`
   - Or bottom-right: `<div style="position: absolute; bottom: 40px; right: 60px; font-size: 24px; opacity: 0.6;">02</div>`
   - Use 2-digit format: 01, 02, 03, etc.

6. **Layout & Spacing (CRITICAL - Content Must Fit Within Slide):**
   - **CONTENT CONTAINMENT**: ALL text and visuals MUST fit within 1920x1080 canvas - NO overflow
   - **Horizontal spacing**: Total padding + margin should be approximately 180px (combined left + right)
     * Example: padding: 80px 100px; (180px total horizontal spacing)
     * Or: margin-left: 100px; padding: 60px 80px; (also ~180px total)
     * Avoid excessive left spacing that cuts off right side content
   - **Vertical spacing**: Ensure content doesn't extend beyond slide bottom
   - **Overflow prevention**: Use `overflow: hidden;` on slide container
   - Use flexbox/grid for centering: `display: flex; justify-content: center; align-items: center; height: 100%;`
   - **CRITICAL - Vertically Center Content**: Use flexbox to center content in the middle of the slide, not just add padding from bottom
   - Leave white space - don't cram content, but ensure all text is visible
   - **ADAPTIVE SIZING**: Automatically adjust font sizes for long content to ensure everything fits

7. **Typography & Visual Balance:**
   - Font Family: Use 'Inter', 'SF Pro Display', 'Segoe UI', Arial, sans-serif (prefer Inter for modern look)
   - **Headings & Body Text**: Choose appropriate sizes based on content length
   - Line height: 1.4-1.6 for readability (adjust for content density)
   - **Text alignment**: Left-aligned for readability (centered only for titles)
   - **IMPORTANT - VISUAL ELEMENTS**: Include icons, emojis, colored divs, shapes to make slides engaging
   - **Balance text with visuals**: Don't make slides all text - add visual interest
   - Use decorative elements: colored accent bars, icon bullets, background shapes
   - Keep content concise - avoid overly long text blocks (max 4-5 bullet points per slide)

8. **PREFERRED CONTENT LAYOUT (2-Column):**
   - **FOR CONTENT SLIDES**: Strongly prefer text on LEFT + visual element on RIGHT layout
   - Use 2-column grid: 60% text column (left) + 40% visual column (right)
   - Visual elements can be: icons, illustrations, decorative shapes, colored boxes, diagrams
   - Example structure:
     ```html
     <div style="display: grid; grid-template-columns: 1.5fr 1fr; gap: 60px; align-items: center;">
       <div><!-- Text content here --></div>
       <div><!-- Visual element here: large icon, illustration, or decorative div --></div>
     </div>
     ```
   - Single-column text-only layout should be RARE - only for very text-heavy content
   - Even for text-heavy slides, try to include small visual accents or icons

9. **Images (if provided):**
   - If `provided_image_url` exists, integrate it beautifully
   - Position: side-by-side with text OR full-width header
   - Style: `border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);`
   - Size: Proportional to content (max-width: 50% for side-by-side, 100% for full-width)

9. **Logo:** {f"Include at top-right or top-left of EACH slide: <img src='{logo_url}' style='position: absolute; top: 30px; right: 60px; width: 100px; height: auto; z-index: 10;' alt='Logo' />" if logo_url else "No logo to include"}

10. **ANIMATION & TIMING REQUIREMENTS** (CREATIVE FREEDOM):
   - **BACKGROUND/CONTAINER**: Always visible immediately (NO animation)
     * Slide container (.slide div): opacity: 1, no animation
     * Background colors/gradients: visible from start
   - **CONTENT ELEMENTS**: Animate creatively - you have freedom!
     * Text: h1, h2, h3, p, li (animated)
     * Visuals: images, icons, decorative divs (animated)
     * Logo & slide numbers: visible immediately (no animation)
   - **TIMING GOAL**: ALL content should be fully visible within 2-3 seconds (OPTIMAL: 2.5s)
   - **⚠️ CRITICAL ANIMATION RULES** (MUST FOLLOW):
     * **ALWAYS use 'forwards' fill-mode**: Content MUST STAY VISIBLE after animation completes
     * **NO looping animations**: animation-iteration-count MUST be 1 (default, never use 'infinite')
     * **NO reverse/alternate**: Never use animation-direction: alternate or reverse
     * **Content persistence**: Once appeared, content NEVER disappears or repeats animation
     * Example: `animation: fadeIn 0.5s ease-out forwards;` ✅ CORRECT
     * Example: `animation: fadeIn 0.5s ease-out infinite;` ❌ WRONG - content will disappear!
   - **ANIMATION VARIETY** - Be creative with different styles:
     * fadeIn, slideInUp, slideInLeft, slideInRight, scaleIn, bounceIn
     * Combine effects: opacity + transform for richer animations
     * Different animations for different slides - keep it interesting!
   - **GUIDELINES** (not strict rules):
     * Individual animation duration: 0.3-0.8s recommended
     * Stagger delays: 0.1-0.3s between elements
     * Total sequence should be under 3 seconds
     * Use easing functions: ease-out, ease-in-out, cubic-bezier for smoothness
   - **CREATIVE EXAMPLES**:
     ```css
     /* Fade + slide up */
     @keyframes fadeInUp {{
       from {{ opacity: 0; transform: translateY(30px); }}
       to {{ opacity: 1; transform: translateY(0); }}
     }}

     /* Slide from left */
     @keyframes slideInLeft {{
       from {{ opacity: 0; transform: translateX(-50px); }}
       to {{ opacity: 1; transform: translateX(0); }}
     }}

     /* Scale in */
     @keyframes scaleIn {{
       from {{ opacity: 0; transform: scale(0.8); }}
       to {{ opacity: 1; transform: scale(1); }}
     }}

     /* Bounce in */
     @keyframes bounceIn {{
       0% {{ opacity: 0; transform: scale(0.3); }}
       50% {{ opacity: 1; transform: scale(1.05); }}
       70% {{ transform: scale(0.95); }}
       100% {{ transform: scale(1); }}
     }}
     ```
   - **USAGE EXAMPLES**:
     ```html
     <!-- Title with bounce -->
     <h1 style="opacity: 0; animation: bounceIn 0.6s ease-out forwards;">Title</h1>

     <!-- Bullets sliding from left with stagger -->
     <li style="opacity: 0; animation: slideInLeft 0.5s ease-out 0.2s forwards;">Point 1</li>
     <li style="opacity: 0; animation: slideInLeft 0.5s ease-out 0.4s forwards;">Point 2</li>

     <!-- Image scaling in -->
     <img style="opacity: 0; animation: scaleIn 0.6s ease-out 0.6s forwards;" src="..." />
     ```
   - **IMPORTANT**: Vary animations across slides for visual interest, but keep timing under 3s total

11. **Language:** All content MUST be in {language}

12. **CONTENT DEVELOPMENT (CRITICAL - Creative Expansion & Visual Elements):**
   - **You have CREATIVE FREEDOM** - expand outline into detailed, engaging content
   - DO NOT copy outline word-for-word - INTERPRET the intent and create compelling content
   - Keep the MEANING and PURPOSE of each outline point, but write it better for slides
   - Write content that aligns with the user's target goal: {user_query or title}
   - **VISUAL ELEMENTS ARE ESSENTIAL** - Don't make slides all text!
   - Include relevant icons/emojis to illustrate points (e.g., ✓ ✗ → ★ 💡 🎯 📊 💰 🚀 🎨 ⚡ 🔥)
   - Add visual elements: decorative divs, colored accent bars, background shapes, icon bullets
   - Use CSS to position visual elements: colored boxes, circles, dividers, accent bars
   - Balance text with visuals: charts, diagrams, illustrations, decorative elements
   - Make content ACTIONABLE and CLEAR - avoid vague, generic statements
   - You can adjust wording, add examples, use better phrasing - just maintain outline's core message

   **SPECIAL SLIDES:**
   - **Slide 0 (Title Slide - MUST BE CREATIVE & IMPRESSIVE)**: First impression is CRITICAL!
     - **LAYOUT REQUIREMENT**: 2-COLUMN layout - Text LEFT + Visual/Placeholder RIGHT
     - **LEFT COLUMN (60%)**: Title, subtitle, author info
       * Large title (64-80px, bold, eye-catching)
       * Engaging subtitle (28-32px)
       * Author/date info (20-24px)
     - **RIGHT COLUMN (40%)**: Visual element or colored placeholder
       * Large decorative shape, icon, or colored div (400-500px size)
       * Geometric shapes, circles, hexagons with topic-related styling
       * Background patterns or gradient fills
       * Creative visual that matches the presentation topic
     - **FORBIDDEN**: Centered text only layout (boring, overused)
     - Creative background matching the theme
     - NO slide number on this slide
     - **MUST include <style> tag with @keyframes** for animations
     - Examples by topic:
       * Tech: Modern geometric shapes, circuit patterns, abstract tech visuals
       * Business: Professional charts placeholder, growth graphs, building icons
       * Creative: Artistic shapes, vibrant colors, dynamic patterns
       * Education: Book icons, graduation elements, learning symbols
     - The goal: Make the audience want to see what comes next!

   - **Slide 1 (Table of Contents - REQUIRED)**: Overview of all main topics
     - Title: "Agenda" or "Table of Contents" or "Overview" in {language}
     - List ALL main sections/topics from the outline (3-7 items)
     - Each item with icon and brief description
     - Include slide number "01" in corner
     - Use numbered list or icon bullets
     - **MUST include <style> tag with @keyframes**

   - **Content Slides (Slide 2+)**: Each slide should have 3-5 specific points with examples
     - Use concrete data, statistics, or real-world examples
     - Add visual hierarchy: main point → supporting details
     - Include icons or visual markers for each point
     - Include slide number (02, 03, 04...)
     - **CRITICAL**: EVERY slide MUST have <style> tag with @keyframes definitions
     - **CRITICAL**: ALL animations MUST use 'forwards' fill-mode (content stays visible)

   - **Last Slide (Thank You)**: Engaging closing with visual elements
     - "Thank You" message in large text
     - Optional: Contact info, call-to-action, or summary
     - Include slide number
     - Optional: Different background from content slides (gradient allowed here)
     - Decorative visual: shapes or celebratory icons (🎉 ✨)

**OUTPUT FORMAT:**

Return ONLY raw HTML code. No markdown, no explanations, no ```html blocks. Just the HTML.

**REMINDER - ANIMATION TIMING:**
- ALL animations MUST complete within 2.5 seconds MAX
- Use staggered delays: 0s, 0.2s, 0.4s, 0.6s, 0.8s
- Fast durations: 0.3-0.5s per element
- Include `<style>` tag with @keyframes fadeIn in each slide

**EXAMPLE OUTPUT (for 4 slides showing all special slide types with proper animation):**

<!-- Slide 0: Title Slide (NO slide number) - 2-COLUMN LAYOUT -->
<div class="slide" data-slide-index="0" style="width: 1920px; height: 1080px; min-height: 1080px; max-height: 1080px; overflow: hidden; background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%); color: #1e293b; display: flex; justify-content: center; align-items: center; padding: 80px 120px; position: relative;">
  <style>
    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(20px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes scaleIn {{
      from {{ opacity: 0; transform: scale(0.8); }}
      to {{ opacity: 1; transform: scale(1); }}
    }}
  </style>
  {f'<img src="{logo_url}" style="position: absolute; top: 40px; right: 80px; width: 120px; height: auto; z-index: 10;" alt="Logo" />' if logo_url else ''}
  
  <!-- 2-COLUMN GRID: Text Left + Visual Right -->
  <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 80px; align-items: center; width: 100%; max-width: 1680px;">
    <!-- LEFT: Text Content -->
    <div>
      <h1 style="font-size: 72px; font-weight: bold; margin-bottom: 30px; font-family: 'Inter', 'SF Pro Display', sans-serif; line-height: 1.2; opacity: 0; animation: fadeIn 0.6s ease-out forwards;">Presentation Title Here</h1>
      <p style="font-size: 28px; line-height: 1.5; margin-bottom: 40px; color: #64748b; opacity: 0; animation: fadeIn 0.6s ease-out 0.2s forwards;">Compelling subtitle explaining the presentation purpose and value proposition</p>
      <p style="font-size: 22px; color: #94a3b8; opacity: 0; animation: fadeIn 0.6s ease-out 0.4s forwards;">By Author Name | January 2026</p>
    </div>
    
    <!-- RIGHT: Visual Element (colored shape placeholder) -->
    <div style="display: flex; justify-content: center; align-items: center; opacity: 0; animation: scaleIn 0.8s ease-out 0.6s forwards;">
      <div style="width: 420px; height: 420px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); border-radius: 24px; display: flex; justify-content: center; align-items: center; box-shadow: 0 20px 50px rgba(0,0,0,0.15);">
        <div style="font-size: 120px; color: rgba(255,255,255,0.9);">📊</div>
      </div>
    </div>
  </div>
</div>

<!-- Slide 1: Table of Contents (WITH slide number 01, WITH <style>) -->
<div class="slide" data-slide-index="1" style="width: 1920px; height: 1080px; min-height: 1080px; max-height: 1080px; overflow: hidden; background: #ffffff; color: #1e293b; display: flex; justify-content: center; align-items: center; padding: 80px 120px; position: relative;">
  <style>
    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(20px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
  </style>
  {f'<img src="{logo_url}" style="position: absolute; top: 40px; right: 80px; width: 100px; height: auto; z-index: 10;" alt="Logo" />' if logo_url else ''}
  <div style="position: absolute; top: 50px; right: 80px; font-size: 28px; color: #94a3b8; opacity: 0.6;">01</div>
  <div style="max-width: 1200px; width: 100%;">
    <h1 style="font-size: 64px; font-weight: bold; margin-bottom: 60px; font-family: 'Inter', 'SF Pro Display', sans-serif; opacity: 0; animation: fadeIn 0.5s ease-out forwards;">Agenda</h1>
    <ul style="font-size: 32px; line-height: 2.2; list-style: none; padding: 0;">
      <li style="margin-bottom: 30px; opacity: 0; animation: fadeIn 0.5s ease-out 0.2s forwards;">📊 <strong>1.</strong> Introduction to the Topic</li>
      <li style="margin-bottom: 30px; opacity: 0; animation: fadeIn 0.5s ease-out 0.4s forwards;">💡 <strong>2.</strong> Key Concepts and Framework</li>
      <li style="margin-bottom: 30px; opacity: 0; animation: fadeIn 0.5s ease-out 0.6s forwards;">🎯 <strong>3.</strong> Practical Applications</li>
      <li style="margin-bottom: 30px; opacity: 0; animation: fadeIn 0.5s ease-out 0.8s forwards;">📈 <strong>4.</strong> Results and Impact</li>
      <li style="margin-bottom: 30px; opacity: 0; animation: fadeIn 0.5s ease-out 1.0s forwards;">🚀 <strong>5.</strong> Next Steps</li>
    </ul>
  </div>
</div>

<!-- Slide 2: Content slide (WITH slide number 02, WITH <style>, WITH forwards) -->
<div class="slide" data-slide-index="2" style="width: 1920px; height: 1080px; min-height: 1080px; max-height: 1080px; overflow: hidden; background: #ffffff; color: #1e293b; display: flex; justify-content: center; align-items: center; padding: 80px 120px; position: relative;">
  <style>
    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(20px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
  </style>
  {f'<img src="{logo_url}" style="position: absolute; top: 40px; right: 80px; width: 100px; height: auto; z-index: 10;" alt="Logo" />' if logo_url else ''}
  <div style="position: absolute; top: 50px; right: 80px; font-size: 28px; color: #94a3b8; opacity: 0.6;">02</div>
  <div style="max-width: 1600px; width: 100%;">
    <h1 style="font-size: 56px; font-weight: bold; margin-bottom: 50px; font-family: 'Inter', 'SF Pro Display', sans-serif; border-left: 6px solid #3b82f6; padding-left: 30px; opacity: 0; animation: fadeIn 0.5s ease-out forwards; text-align: left;">Main Topic with Specific Details</h1>
    <ul style="font-size: 28px; line-height: 1.8; list-style: none; padding: 0;">
      <li style="margin-bottom: 28px; display: flex; align-items: flex-start; opacity: 0; animation: fadeIn 0.5s ease-out 0.2s forwards;"><span style="margin-right: 20px; font-size: 32px;">🎯</span><span><strong>Specific Point 1:</strong> Detailed explanation with concrete example or data</span></li>
      <li style="margin-bottom: 28px; display: flex; align-items: flex-start; opacity: 0; animation: fadeIn 0.5s ease-out 0.4s forwards;"><span style="margin-right: 20px; font-size: 32px;">💡</span><span><strong>Actionable Insight 2:</strong> Clear, specific guidance with real-world application</span></li>
      <li style="margin-bottom: 28px; display: flex; align-items: flex-start; opacity: 0; animation: fadeIn 0.5s ease-out 0.6s forwards;"><span style="margin-right: 20px; font-size: 32px;">📊</span><span><strong>Measurable Result 3:</strong> Include statistics, numbers, or tangible outcomes</span></li>
      <li style="margin-bottom: 28px; display: flex; align-items: flex-start; opacity: 0; animation: fadeIn 0.5s ease-out 0.8s forwards;"><span style="margin-right: 20px; font-size: 32px;">🚀</span><span><strong>Best Practice 4:</strong> Proven strategies and implementation tips</span></li>
    </ul>
  </div>
</div>

<!-- Last Slide: Thank You (WITH slide number, gradient allowed, WITH <style>) -->
<div class="slide" data-slide-index="3" style="width: 1920px; height: 1080px; min-height: 1080px; max-height: 1080px; overflow: hidden; background: linear-gradient(135deg, #0f172a, #1e3a8a); color: #ffffff; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 80px; position: relative;">
  <style>
    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(20px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes scaleIn {{
      from {{ opacity: 0; transform: scale(0.5); }}
      to {{ opacity: 1; transform: scale(1); }}
    }}
  </style>
  {f'<img src="{logo_url}" style="position: absolute; top: 40px; right: 80px; width: 100px; height: auto; z-index: 10;" alt="Logo" />' if logo_url else ''}
  <div style="position: absolute; top: 50px; right: 80px; font-size: 28px; opacity: 0.6;">03</div>
  <div style="font-size: 80px; margin-bottom: 40px; opacity: 0; animation: scaleIn 0.6s ease-out forwards;">🎉</div>
  <h1 style="font-size: 72px; font-weight: bold; margin-bottom: 30px; text-align: center; font-family: 'Inter', 'SF Pro Display', sans-serif; opacity: 0; animation: fadeIn 0.6s ease-out 0.2s forwards;">Thank You!</h1>
  <p style="font-size: 32px; text-align: center; max-width: 800px; line-height: 1.6; opacity: 0; animation: fadeIn 0.6s ease-out 0.4s forwards;">Questions? Let's discuss!</p>
  <div style="margin-top: 50px; font-size: 24px; opacity: 0.8; opacity: 0; animation: fadeIn 0.6s ease-out 0.6s forwards;">contact@example.com | @yourhandle</div>
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

        logger.info(f"🤖 Calling Gemini for slide analysis (Step 1)...")
        logger.info(f"   Model: {self.gemini_model}")
        logger.info(
            f"   Slides range: {num_slides_range['min']}-{num_slides_range['max']}"
        )

        try:
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
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

    async def analyze_slide_requirements_from_pdf(
        self,
        title: str,
        target_goal: str,
        slide_type: str,
        num_slides_range: dict,
        language: str,
        user_query: str,
        pdf_path: str,
    ) -> dict:
        """
        Step 1 (PDF variant): Analyze PDF content and generate structured outline

        Similar to analyze_slide_requirements() but includes PDF document analysis.

        Args:
            title: Presentation title
            target_goal: Presentation goal
            slide_type: "academy" or "business"
            num_slides_range: {"min": int, "max": int}
            language: "vi", "en", "zh"
            user_query: Additional user instructions
            pdf_path: Local path to PDF file

        Returns:
            dict with keys: presentation_summary, num_slides, slides
        """
        import time
        import google.generativeai as genai  # type: ignore

        logger.info(f"📄 Calling Gemini for PDF slide analysis (Step 1)...")
        logger.info(f"   Model: {self.gemini_model}")
        logger.info(f"   PDF: {pdf_path}")
        logger.info(
            f"   Slides range: {num_slides_range['min']}-{num_slides_range['max']}"
        )

        uploaded_file = None
        try:
            # Configure genai (legacy API for file upload)
            genai.configure(api_key=self.gemini_api_key)  # type: ignore

            # Upload PDF to Gemini Files API
            logger.info(f"📤 Uploading PDF to Gemini Files API...")
            uploaded_file = genai.upload_file(pdf_path)  # type: ignore
            logger.info(f"✅ PDF uploaded: {uploaded_file.uri}")

            # Wait for file processing
            while uploaded_file.state.name == "PROCESSING":
                logger.info("⏳ Waiting for PDF processing...")
                time.sleep(2)
                uploaded_file = genai.get_file(uploaded_file.name)  # type: ignore

            if uploaded_file.state.name == "FAILED":
                raise Exception("PDF processing failed in Gemini")

            logger.info(f"✅ PDF ready: {uploaded_file.state.name}")

            # Build prompt using SAME method as text analysis for consistency
            base_prompt = self.build_analysis_prompt(
                title=title,
                target_goal=target_goal,
                slide_type=slide_type,
                num_slides_range=num_slides_range,
                language=language,
                user_query=user_query,
            )

            # Prepend PDF-specific instruction
            pdf_analysis_prompt = f"""**IMPORTANT: You are analyzing a PDF document. Extract all content from the uploaded PDF file.**

{base_prompt}"""

            # Call Gemini with PDF using legacy API
            model = genai.GenerativeModel(self.gemini_model)  # type: ignore

            # Increase max_output_tokens for large slide counts
            max_slides = num_slides_range["max"]
            # Estimate: ~500 tokens per slide, add buffer
            estimated_tokens = min(max_slides * 600 + 1000, 32000)

            response = model.generate_content(
                [uploaded_file, pdf_analysis_prompt],
                generation_config={  # type: ignore
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": estimated_tokens,
                    "response_mime_type": "application/json",
                },
            )

            result_text = response.text.strip()
            logger.info(f"✅ Gemini PDF analysis completed: {len(result_text)} chars")

            # Parse JSON with error handling
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError as e:
                # Try to repair truncated JSON
                logger.warning(
                    f"⚠️ JSON parse error at position {e.pos}, attempting repair..."
                )

                # If JSON is truncated, try to close it properly
                if "slides" in result_text and result_text.count(
                    "["
                ) > result_text.count("]"):
                    logger.info("🔧 Attempting to close truncated JSON array...")
                    # Add missing closing brackets
                    missing_close_brackets = result_text.count("[") - result_text.count(
                        "]"
                    )
                    missing_close_braces = result_text.count("{") - result_text.count(
                        "}"
                    )

                    repaired_text = result_text
                    for _ in range(missing_close_braces):
                        repaired_text += "}"
                    for _ in range(missing_close_brackets):
                        repaired_text += "]"

                    try:
                        result = json.loads(repaired_text)
                        logger.info(f"✅ Successfully repaired JSON")
                    except:
                        logger.error(f"❌ Failed to parse JSON: {e}")
                        logger.error(f"   Response text: {result_text[:500]}...")
                        raise ValueError(f"AI returned invalid JSON: {str(e)}")
                else:
                    logger.error(f"❌ Failed to parse JSON: {e}")
                    logger.error(f"   Response text: {result_text[:500]}...")
                    raise ValueError(f"AI returned invalid JSON: {str(e)}")

            # Validate structure
            if "slides" not in result or "num_slides" not in result:
                raise ValueError("Invalid analysis structure")

            if len(result["slides"]) != result["num_slides"]:
                logger.warning(
                    f"⚠️ Slide count mismatch: {len(result['slides'])} vs {result['num_slides']}"
                )
                result["num_slides"] = len(result["slides"])

            logger.info(f"✅ PDF analysis parsed: {result['num_slides']} slides")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON: {e}")
            logger.error(f"   Response text: {result_text[:500]}...")
            raise ValueError(f"AI returned invalid JSON: {str(e)}")

        except Exception as e:
            logger.error(f"❌ Gemini PDF analysis failed: {e}")
            raise

        finally:
            # Delete file from Gemini after processing
            if uploaded_file:
                try:
                    genai.delete_file(uploaded_file.name)  # type: ignore
                    logger.info(f"🗑️ Deleted file from Gemini: {uploaded_file.name}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to delete Gemini file: {e}")

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
        first_slide_sample: Optional[
            str
        ] = None,  # Sample from batch 1 for style consistency
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
            first_slide_sample=first_slide_sample,  # Pass style reference
        )

        logger.info(
            f"🎨 Generating HTML batch {batch_number}/{total_batches} ({len(slides_outline)} slides) with Claude (Step 2)..."
        )

        try:
            # Use streaming to get real-time progress and avoid timeouts
            logger.info(
                f"🌊 Starting Claude streaming for batch {batch_number}/{total_batches}..."
            )

            # ⚠️ CRITICAL FIX: Run blocking streaming in thread to avoid blocking event loop
            # Claude's sync streaming blocks entire async event loop, causing all API requests to timeout
            import asyncio

            def _stream_claude_sync():
                """Synchronous streaming function to run in thread"""
                html_output = ""
                with self.claude_client.messages.stream(
                    model=self.claude_model,
                    max_tokens=36864,  # 36K tokens (faster than 64K, sufficient for 8 slides)
                    temperature=0.8,  # More creative for HTML content
                    timeout=1800.0,  # 30 minutes timeout (default is 600s/10min)
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                ) as stream:
                    for text in stream.text_stream:
                        html_output += text
                return html_output

            # Run sync streaming in thread pool to prevent blocking
            html_output = await asyncio.to_thread(_stream_claude_sync)

            logger.info(f"✅ HTML streaming completed: {len(html_output)} chars")

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
                if div:  # Type guard
                    div["data-slide-index"] = str(batch_start_index + i)  # type: ignore
                    slide_htmls.append(str(div))

            logger.info(f"✅ Parsed {len(slide_htmls)} slides from batch")

            # Log slide count (don't fail if mismatch - let user decide)
            expected_count = len(slides_outline)
            actual_count = len(slide_htmls)

            if actual_count != expected_count:
                logger.warning(
                    f"⚠️ SLIDE COUNT MISMATCH! Expected {expected_count} slides, but Claude generated {actual_count} slides"
                )
                logger.warning(
                    f"   Batch {batch_number}/{total_batches}: Expected slides {batch_start_index} to {batch_start_index + expected_count - 1}"
                )
                logger.warning(f"   Claude output length: {len(html_output)} chars")
                logger.warning(f"   Output preview: {html_output[:500]}...")
                logger.warning(
                    f"   ⚠️ Continuing with {actual_count} slides - user can retry if needed"
                )
            else:
                logger.info(
                    f"✅ Slide count match: {actual_count}/{expected_count} slides"
                )

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
