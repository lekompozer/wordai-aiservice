"""
Claude (Anthropic) Service
Provides Claude AI integration for chat, editing, and document processing
"""

import os
import httpx
from typing import List, Dict, Optional, AsyncGenerator
from config import config
from src.utils.logger import setup_logger

logger = setup_logger()


class ClaudeService:
    """Service for Claude AI (Anthropic API)"""

    def __init__(self):
        """Initialize Claude service"""
        self.api_key = config.ANTHROPIC_API_KEY
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured")

        self.api_url = "https://api.anthropic.com/v1/messages"
        self.api_version = "2023-06-01"
        self.default_model = config.CLAUDE_MODEL  # Haiku 4.5
        self.sonnet_model = config.CLAUDE_SONNET_MODEL

        logger.info(f"✅ ClaudeService initialized with model: {self.default_model}")

    async def chat(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        max_tokens: int = 16000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """
        Send chat request to Claude (non-streaming) with retry logic

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Claude model to use (default: Haiku 4.5)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt
            max_retries: Maximum number of retries for transient errors

        Returns:
            Response text from Claude
        """
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        model = model or self.default_model

        # Convert messages format if needed (handle 'system' role)
        claude_messages = []
        system_content = system_prompt or ""

        for msg in messages:
            if msg["role"] == "system":
                # Extract system message
                system_content = msg["content"]
            else:
                # Keep user/assistant messages
                claude_messages.append({"role": msg["role"], "content": msg["content"]})

        # Build request payload
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": claude_messages,
        }

        # Add system prompt if provided
        if system_content:
            payload["system"] = system_content

        logger.info(f"🤖 Calling Claude API: {model}, {len(claude_messages)} messages")

        # Retry logic for transient errors (429, 529, 500, 503)
        import asyncio

        for attempt in range(max_retries):
            try:
                # Timeout: 300 seconds (5 minutes) for large content
                async with httpx.AsyncClient(timeout=300.0) as client:
                    response = await client.post(
                        self.api_url,
                        headers={
                            "x-api-key": self.api_key,
                            "anthropic-version": self.api_version,
                            "content-type": "application/json",
                        },
                        json=payload,
                    )

                    response.raise_for_status()
                    result = response.json()

                    # Extract text from response
                    content = result.get("content", [])
                    if content and len(content) > 0:
                        text = content[0].get("text", "")
                        logger.info(f"✅ Claude response: {len(text)} chars")
                        return text
                    else:
                        logger.error("❌ No content in Claude response")
                        return ""

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                error_text = e.response.text

                # Retryable errors: 429 (rate limit), 500 (server error), 503 (unavailable), 529 (overloaded)
                if status_code in [429, 500, 503, 529] and attempt < max_retries - 1:
                    wait_time = (2**attempt) + 1  # Exponential backoff: 2s, 5s, 9s
                    logger.warning(
                        f"⚠️ Claude API error {status_code} (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time}s... Error: {error_text}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Non-retryable error or max retries reached
                    logger.error(f"❌ Claude API error: {status_code} - {error_text}")
                    raise

            except httpx.ReadTimeout as e:
                logger.error(
                    f"❌ Claude request timeout after 300s (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) + 1
                    logger.info(f"⏳ Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error("❌ Max retries exceeded for timeout")
                    raise

            except Exception as e:
                logger.error(f"❌ Claude request failed: {type(e).__name__}: {e}")
                raise

        # Should not reach here
        raise Exception("Claude API failed after max retries")

    async def chat_stream(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        max_tokens: int = 16000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send streaming chat request to Claude

        Args:
            messages: List of message dicts
            model: Claude model to use
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            system_prompt: Optional system prompt

        Yields:
            Text chunks from Claude
        """
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        model = model or self.default_model

        # Convert messages format
        claude_messages = []
        system_content = system_prompt or ""

        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                claude_messages.append({"role": msg["role"], "content": msg["content"]})

        # Build request payload
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": claude_messages,
            "stream": True,  # Enable streaming
        }

        if system_content:
            payload["system"] = system_content

        logger.info(f"🤖 Calling Claude API (streaming): {model}")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    self.api_url,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": self.api_version,
                        "content-type": "application/json",
                    },
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    # Process SSE stream
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        # Parse SSE format: "data: {...}"
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix

                            # Skip ping events
                            if data.strip() == "[DONE]":
                                break

                            try:
                                import json

                                event = json.loads(data)

                                # Handle content_block_delta events
                                if event.get("type") == "content_block_delta":
                                    delta = event.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        text = delta.get("text", "")
                                        if text:
                                            yield text

                            except json.JSONDecodeError:
                                continue

                    logger.info("✅ Claude streaming completed")

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Claude streaming error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"❌ Claude streaming failed: {e}")
            raise

    async def edit_html(
        self,
        html_content: str,
        user_instruction: str,
        document_type: str = "doc",  # "doc" or "slide"
        model: Optional[str] = None,
    ) -> str:
        """
        Edit HTML content based on user instruction
        Optimized for document editing use case with document type awareness

        Args:
            html_content: HTML to edit
            user_instruction: User's editing instruction
            document_type: "doc" for A4 documents, "slide" for presentations
            model: Claude model (default: Haiku 4.5)

        Returns:
            Edited HTML content
        """
        # Context-aware system prompt based on document type
        if document_type == "slide":
            system_prompt = """You are an expert HTML editor specializing in presentation slides. Your task is to apply the user's instruction to the provided HTML snippet.

IMPORTANT CONTEXT:
- This is a presentation slide (16:9 format, 1920x1080px)
- Keep content concise and visually impactful
- Use short sentences and bullet points
- Maintain slide-appropriate formatting

EDITING RULES:
- ONLY return the modified HTML content
- Preserve slide structure (width: 1920px, height: 1080px)
- Maintain inline styles and positioning
- Keep text sizes appropriate for presentation (large fonts)
- Do not add explanations, markdown, or extra text
- Do not wrap output in code blocks or backticks
- Return clean HTML only"""
        else:  # doc (A4)
            system_prompt = """You are an expert HTML editor specializing in A4 documents for TipTap editor. Your task is to apply the user's instruction to the provided HTML snippet.

IMPORTANT CONTEXT:
- This is an A4 document (210mm x 297mm)
- Maintain professional document formatting
- Preserve document structure and readability

CRITICAL STYLING RULES (TipTap Compatibility):
- Apply styles ONLY on BLOCK elements: <p>, <h1>, <h2>, <h3>, <h4>, <h5>, <h6>, <ul>, <ol>, <li>, <blockquote>, <div>
- NEVER add style attributes to text marks: <strong>, <em>, <u>, <s>, <code>, <a>, <span>
- Use semantic HTML for text formatting:
  * Bold text: <strong>text</strong> (NO style attribute)
  * Italic text: <em>text</em> (NO style attribute)
  * Underline: <u>text</u> (NO style attribute)
  * Strikethrough: <s>text</s> (NO style attribute)
- Block element styles can include: text-align, margin, padding, line-height, color, background-color, font-size, font-family
- Example CORRECT formatting:
  * <p style="text-align: center; color: #333;">This is <strong>bold</strong> and <em>italic</em> text.</p>
  * <h2 style="color: #1a73e8; margin-bottom: 16px;">Heading with <strong>emphasis</strong></h2>
- Example WRONG formatting (DO NOT DO THIS):
  * <p>This is <strong style="color: red;">bold</strong> text.</p> ❌
  * <em style="font-size: 18px;">Italic</em> ❌

EDITING RULES:
- ONLY return the modified HTML content
- Preserve A4 page structure (width: 210mm, height: 297mm)
- Apply styles ONLY to block elements
- Use clean semantic markup for text marks (no style attributes)
- Keep fonts and spacing appropriate for printed documents
- Do not add explanations, markdown, or extra text
- Do not wrap output in code blocks or backticks
- Return clean HTML only"""

        user_prompt = f"""Instruction: '{user_instruction}'

HTML to edit:
{html_content}"""

        messages = [{"role": "user", "content": user_prompt}]

        # Use Haiku for fast editing
        result = await self.chat(
            messages=messages,
            model=model or self.default_model,
            max_tokens=16384,
            temperature=0.7,
            system_prompt=system_prompt,
        )

        return result.strip()

    async def format_document_html(
        self,
        html_content: str,
        user_query: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Format and beautify document (A4) HTML content
        Optimized for standard document formatting

        Args:
            html_content: HTML to format
            user_query: Optional additional user instruction
            model: Claude model (default: Haiku 4.5)

        Returns:
            Formatted HTML content
        """
        system_prompt = """You are an expert document formatter. Your task is to format and beautify document content for TipTap editor.

FORMATTING RULES FOR DOCUMENTS:
- Correct grammar, spelling, and punctuation
- Ensure consistent spacing and capitalization
- Fix paragraph alignment and indentation
- Standardize heading hierarchy (H1, H2, H3)
- Improve sentence structure for clarity and readability
- Format lists with proper numbering/bullets
- Maintain professional document styling
- Clean up extra whitespace and line breaks
- Preserve the original meaning and intent

CRITICAL STYLING RULES (TipTap Compatibility):
- Apply styles ONLY on BLOCK elements: <p>, <h1>, <h2>, <h3>, <h4>, <h5>, <h6>, <ul>, <ol>, <li>, <blockquote>, <div>
- NEVER add style attributes to text marks: <strong>, <em>, <u>, <s>, <code>, <a>, <span>
- Use semantic HTML for text formatting:
  * Bold text: <strong>text</strong> (NO style attribute)
  * Italic text: <em>text</em> (NO style attribute)
  * Underline: <u>text</u> (NO style attribute)
  * Strikethrough: <s>text</s> (NO style attribute)
- Block element styles can include: text-align, margin, padding, line-height, color, background-color, font-size, font-family
- Example CORRECT formatting:
  * <p style="text-align: center; color: #333;">This is <strong>bold</strong> and <em>italic</em> text.</p>
  * <h2 style="color: #1a73e8; margin-bottom: 16px;">Heading with <strong>emphasis</strong></h2>
- Example WRONG formatting (DO NOT DO THIS):
  * <p>This is <strong style="color: red;">bold</strong> text.</p> ❌
  * <em style="font-size: 18px;">Italic</em> ❌

OUTPUT REQUIREMENTS:
- Return ONLY the formatted HTML
- Preserve HTML structure with block elements
- Apply styles ONLY to block elements
- Use clean semantic markup for text marks (no style attributes)
- Do not add explanations or markdown
- Do not wrap in code blocks or backticks
- Return clean, well-formatted HTML only"""

        user_prompt = "Format and beautify this document content"
        if user_query:
            user_prompt += f". Additional instruction: {user_query}"

        user_prompt += f":\n\n{html_content}"

        messages = [{"role": "user", "content": user_prompt}]

        result = await self.chat(
            messages=messages,
            model=model or self.default_model,
            max_tokens=16384,
            temperature=0.3,  # Lower temp for consistent formatting
            system_prompt=system_prompt,
        )

        return result.strip()

    async def format_slide_html(
        self,
        html_content: str,
        user_query: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Format and beautify presentation slide HTML content
        Optimized for slide formatting (concise, visual)
        Automatically chunks large content to avoid timeouts

        Args:
            html_content: Slide HTML to format
            user_query: Optional additional user instruction
            model: Claude model (default: Haiku 4.5)

        Returns:
            Formatted slide HTML content
        """
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        estimated_tokens = len(html_content) // 4
        MAX_TOKENS_PER_CHUNK = 60000  # ~240KB chars, leaves room for output

        logger.info(
            f"📊 Content size: {len(html_content):,} chars (~{estimated_tokens:,} tokens)"
        )

        # If content is too large, split by slides
        if estimated_tokens > MAX_TOKENS_PER_CHUNK:
            logger.warning(f"⚠️ Content too large, splitting into chunks...")
            return await self._format_slide_html_chunked(
                html_content, user_query, model
            )

        # Normal formatting for smaller content
        return await self._format_slide_html_single(html_content, user_query, model)

    async def _format_slide_html_single(
        self,
        html_content: str,
        user_query: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Format slide HTML in a single request
        """
        system_prompt = """You are an expert presentation formatter. Your task is to format and beautify slide content for TipTap editor.

FORMATTING RULES FOR SLIDES:
- Keep content concise and impactful
- Use short, punchy sentences (avoid long paragraphs)
- Create clear bullet points with proper hierarchy
- Optimize text placement for 16:9 slide layout (1920x1080)
- Use appropriate spacing and margins
- Maintain professional slide aesthetics
- Remove unnecessary words (slides should be scannable)
- Use parallel structure in bullet points

ANIMATION & TIMING REQUIREMENTS (CRITICAL):
- BACKGROUND/CONTAINER: Always visible immediately (NO animation)
  * Slide container (.slide div): opacity: 1, no animation
  * Background colors/gradients: visible from start
  * Logo & slide numbers: visible immediately (no animation)
- CONTENT ELEMENTS: Animate with stagger delays
  * Text: h1, h2, h3, p, li (animated with opacity: 0 initially)
  * Visuals: images, icons, decorative divs (animated)
- ALL content MUST be fully visible within 2-3 seconds (OPTIMAL: 2.5s)
- Use FAST animations only: fade-in (0.3-0.5s), slide-in (0.4-0.6s)
- Stagger text reveals with 0.2s delay between elements
- AVOID slow animations (>1s per element)
- Total animation sequence: MAXIMUM 2.5 seconds
- CSS animation syntax: animation: fadeIn 0.5s ease-out forwards; animation-delay: 0.2s;
- Include @keyframes fadeIn definition in <style> tag within slide
- Set initial opacity: 0 ONLY on animated content elements (NOT on container)
- ⚠️ CRITICAL: ALWAYS use 'forwards' fill-mode so content STAYS VISIBLE after appearing
- ⚠️ NEVER use infinite, alternate, or reverse animations - content must appear ONCE and STAY
- ⚠️ Once content appears, it NEVER disappears or repeats animation (no blinking effect)

CRITICAL STYLING RULES (TipTap Compatibility):
- Apply styles ONLY on BLOCK elements: <p>, <h1>, <h2>, <h3>, <h4>, <h5>, <h6>, <ul>, <ol>, <li>, <blockquote>, <div>
- NEVER add style attributes to text marks: <strong>, <em>, <u>, <s>, <code>, <a>, <span>
- Use semantic HTML for text formatting:
  * Bold text: <strong>text</strong> (NO style attribute)
  * Italic text: <em>text</em> (NO style attribute)
  * Underline: <u>text</u> (NO style attribute)
  * Strikethrough: <s>text</s> (NO style attribute)
- Block element styles can include: text-align, margin, padding, line-height, color, background-color, font-size, font-family, position, width, height, top, left
- For slide positioning, use styles on block elements (p, div, h1-6) NOT on inline marks
- Example CORRECT formatting:
  * <p style="text-align: center; font-size: 32px; color: #1a73e8;">Title with <strong>bold</strong> word</p>
  * <div style="position: absolute; top: 100px; left: 50px;"><h2>Positioned heading with <em>italic</em></h2></div>
- Example WRONG formatting (DO NOT DO THIS):
  * <p>Text with <strong style="color: red; font-size: 24px;">styled bold</strong></p> ❌
  * <span style="position: absolute; top: 50px;">Positioned text</span> ❌

OUTPUT REQUIREMENTS:
- Return ONLY the formatted HTML
- Preserve positioning styles on block elements
- Apply styles ONLY to block elements (p, div, h1-6, etc.)
- Use clean semantic markup for text marks (no style attributes)
- Maintain width/height/position styles for slide layout
- Do not add explanations or markdown
- Do not wrap in code blocks or backticks
- Return clean, well-formatted slide HTML only"""

        user_prompt = "Format and beautify this presentation slide content"
        if user_query:
            user_prompt += f". Additional instruction: {user_query}"

        user_prompt += f":\n\n{html_content}"

        messages = [{"role": "user", "content": user_prompt}]

        result = await self.chat(
            messages=messages,
            model=model or self.default_model,
            max_tokens=64000,  # Allow large slide content (64k tokens)
            temperature=0.3,  # Lower temp for consistent formatting
            system_prompt=system_prompt,
        )

        return result.strip()

    async def _format_slide_html_chunked(
        self,
        html_content: str,
        user_query: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Format large slide HTML by splitting into chunks
        Splits by individual slides to maintain coherence
        """
        from bs4 import BeautifulSoup

        logger.info("🔪 Splitting slides for chunked formatting...")

        # Parse HTML and find all slides
        soup = BeautifulSoup(html_content, "html.parser")
        slide_divs = soup.find_all("div", class_="slide")

        if not slide_divs:
            logger.warning("⚠️ No slides found, treating as single chunk")
            return await self._format_slide_html_single(html_content, user_query, model)

        logger.info(f"📄 Found {len(slide_divs)} slides, processing in chunks...")

        # Process slides in chunks of 5
        SLIDES_PER_CHUNK = 5
        formatted_slides = []

        for i in range(0, len(slide_divs), SLIDES_PER_CHUNK):
            chunk_slides = slide_divs[i : i + SLIDES_PER_CHUNK]
            chunk_html = "\n\n".join(str(slide) for slide in chunk_slides)

            logger.info(
                f"🎨 Formatting slides {i+1}-{min(i+SLIDES_PER_CHUNK, len(slide_divs))} of {len(slide_divs)}..."
            )

            formatted_chunk = await self._format_slide_html_single(
                chunk_html, user_query, model
            )

            formatted_slides.append(formatted_chunk)
            logger.info(f"✅ Chunk {i//SLIDES_PER_CHUNK + 1} formatted")

        # Combine all formatted chunks
        result = "\n\n".join(formatted_slides)
        logger.info(f"✅ All {len(slide_divs)} slides formatted successfully")

        return result


# Singleton instance
_claude_service = None


def get_claude_service() -> ClaudeService:
    """Get Claude service singleton"""
    global _claude_service
    if _claude_service is None:
        _claude_service = ClaudeService()
    return _claude_service
