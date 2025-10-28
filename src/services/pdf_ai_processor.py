"""
PDF AI Processor - Process PDF chunks with Gemini AI
Uses Gemini 2.5 Pro with native PDF support (no image conversion needed)
"""

import os
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json

from google import genai
from google.genai import types
import config.config as config

logger = logging.getLogger(__name__)


# ===== AI PROMPTS =====

DOCUMENT_EXTRACTION_PROMPT = """
You are an expert document converter. Convert this PDF content into clean, structured HTML for an A4 document editor.

**TARGET FORMAT: A4 Document (210mm x 297mm)**

**CRITICAL: SEPARATE PAGES**
This PDF chunk contains multiple pages. You MUST create a SEPARATE `<div class="a4-page">` for EACH PDF page.
If the chunk has 10 PDF pages, output 10 separate `<div class="a4-page">` containers.

**REQUIREMENTS:**
1. Maintain document structure (headings, paragraphs, lists)
2. Preserve text formatting (bold, italic, underline)
3. Keep tables structured with proper borders
4. Extract images and reference them with proper sizing
5. Maintain reading order and flow
6. Use A4-appropriate styling (margins, font sizes)
7. **Each PDF page = One `<div class="a4-page">` container**

**⚠️ CRITICAL OUTPUT RULES:**
- Return ONLY the `<div class="a4-page">` elements
- DO NOT include `<!DOCTYPE html>`, `<html>`, `<head>`, or `<body>` tags
- DO NOT wrap in any outer container except the a4-page divs themselves
- Start directly with first `<div class="a4-page" data-page-number="1">`
- All styles must be INLINE (no `<style>` tags)

**OUTPUT FORMAT:**
Return valid HTML with ONE `<div class="a4-page">` per PDF page:

```html
<div class="a4-page" data-page-number="1" style="width:210mm; height:297mm; padding:20mm; background:white; box-sizing:border-box; margin-bottom:10mm; page-break-after:always;">
  <h1 style="font-size:24pt; margin-bottom:12pt;">Document Title</h1>
  <p style="font-size:11pt; line-height:1.5; text-align:justify;">Introduction paragraph with <strong>bold</strong> and <em>italic</em> text. This is standard A4 body text with proper spacing.</p>

  <h2 style="font-size:18pt; margin-top:18pt; margin-bottom:10pt;">Section 1</h2>
  <p style="font-size:11pt; line-height:1.5; text-align:justify;">Content from first page...</p>
</div>

<div class="a4-page" data-page-number="2" style="width:210mm; height:297mm; padding:20mm; background:white; box-sizing:border-box; margin-bottom:10mm; page-break-after:always;">
  <p style="font-size:11pt; line-height:1.5; text-align:justify;">Content continuing on second page...</p>

  <ul style="margin-left:20pt; font-size:11pt;">
    <li>Item 1</li>
    <li>Item 2</li>
  </ul>

  <table style="width:100%; border-collapse:collapse; margin:10pt 0; font-size:10pt;">
    <tr style="background:#f0f0f0;">
      <th style="border:1pt solid #ccc; padding:6pt;">Header 1</th>
      <th style="border:1pt solid #ccc; padding:6pt;">Header 2</th>
    </tr>
    <tr>
      <td style="border:1pt solid #ccc; padding:6pt;">Data 1</td>
      <td style="border:1pt solid #ccc; padding:6pt;">Data 2</td>
    </tr>
  </table>
</div>

<div class="a4-page" data-page-number="3" style="width:210mm; height:297mm; padding:20mm; background:white; box-sizing:border-box; margin-bottom:10mm; page-break-after:always;">
  <img src="image1.jpg" alt="Chart" style="max-width:170mm; height:auto; margin:10pt 0;">
  <p style="font-size:11pt; line-height:1.5; text-align:justify;">Content from third page...</p>
</div>
```

**A4 STYLING RULES:**
- Page container: 210mm x 297mm (A4 standard)
- Margins: 20mm all sides (printable area: 170mm x 257mm)
- Body text: 11pt, line-height 1.5, justified
- H1: 24pt, H2: 18pt, H3: 14pt
- Tables: Full width with borders, 10pt font
- Images: Max width 170mm (fit in printable area)
- Page spacing: 10mm margin-bottom between pages
- Use millimeters (mm) and points (pt) for measurements
- Add `page-break-after:always` for print support
- Add `data-page-number` attribute for page tracking

**RULES:**
- NO markdown formatting (use HTML only)
- NO code blocks or backticks in output
- Keep ALL content from the PDF
- Maintain visual hierarchy appropriate for A4 printing
- Clean, semantic HTML with inline styles
- **CRITICAL**: Create separate `<div class="a4-page">` for each PDF page in this chunk
- Number pages sequentially with `data-page-number` attribute

Convert the following PDF chunk into A4-formatted HTML (remember: one PDF page = one `<div class="a4-page">`):
"""

SLIDE_EXTRACTION_PROMPT = """
You are an expert presentation converter. Convert this PDF presentation into clean HTML slides in FullHD format.

**TARGET FORMAT: FullHD Slides (1920px x 1080px, 16:9 aspect ratio)**

**CRITICAL REQUIREMENT:**
Each PDF page = ONE slide. Process ALL pages in this PDF as individual slides.

**⚠️ CRITICAL OUTPUT STRUCTURE:**
- Each slide MUST use class="slide-page" (NOT "slide")
- Add data-slide-number attribute for easy parsing
- Return ONLY the slide-page divs
- DO NOT include DOCTYPE, html, head, or body tags
- All styles MUST be inline (no style tags or external CSS)

**OUTPUT FORMAT:**
Return valid HTML with one slide per PDF page using the slide-page class:

```html
<div class="slide-page" data-slide-number="1" style="width:1920px; height:1080px; position:relative; background:white; padding:60px; box-sizing:border-box; page-break-after:always;">
  <h1 style="font-size:64px; font-weight:bold; margin-bottom:40px; color:#1a1a1a;">Slide Title</h1>
  <h2 style="font-size:36px; color:#666; margin-bottom:50px;">Subtitle or tagline</h2>

  <div style="font-size:28px; line-height:1.6;">
    <ul style="list-style-type:disc; margin-left:60px;">
      <li style="margin-bottom:20px;">Bullet point 1 with adequate spacing</li>
      <li style="margin-bottom:20px;">Bullet point 2 with clear hierarchy</li>
      <li style="margin-bottom:20px;">Bullet point 3 with readable text</li>
    </ul>
  </div>

  <img src="image1.jpg" alt="Chart" style="max-width:1200px; max-height:600px; margin:30px auto; display:block;">
</div>

<div class="slide-page" data-slide-number="2" style="width:1920px; height:1080px; position:relative; background:white; padding:60px; box-sizing:border-box; page-break-after:always;">
  <h1 style="font-size:64px; font-weight:bold; margin-bottom:40px;">Next Slide Title</h1>
  <p style="font-size:32px; line-height:1.5; color:#333;">Content for second slide goes here...</p>
</div>

<div class="slide-page" data-slide-number="3" style="width:1920px; height:1080px; position:relative; background:#f5f5f5; padding:60px; box-sizing:border-box; page-break-after:always;">
  <h1 style="font-size:64px; font-weight:bold; margin-bottom:40px;">Another Slide</h1>
  <table style="width:100%; border-collapse:collapse; font-size:24px;">
    <tr style="background:#333; color:white;">
      <th style="padding:15px; border:1px solid #ccc;">Header 1</th>
      <th style="padding:15px; border:1px solid #ccc;">Header 2</th>
    </tr>
    <tr>
      <td style="padding:15px; border:1px solid #ccc;">Data 1</td>
      <td style="padding:15px; border:1px solid #ccc;">Data 2</td>
    </tr>
  </table>
</div>
```

**FULLHD STYLING RULES:**
- Slide container: 1920px x 1080px (FullHD 16:9)
- Padding: 60px all sides (safe area: 1800px x 960px)
- Slide title (H1): 64px, bold, high contrast
- Subtitle (H2): 36px, medium weight
- Body text: 28-32px, line-height 1.5-1.6
- Bullet points: 28px with 20px spacing
- Images: Max 1200px wide or 600px tall
- Tables: 24px font, proper borders and padding
- Use pixels (px) for all measurements
- High contrast colors for projection

**LAYOUT PATTERNS:**
- Title slide: Centered title + subtitle
- Content slide: Title at top + content below
- Image slide: Title + large image
- Bullet slide: Title + bulleted list
- Split slide: Title + two columns
- Table slide: Title + data table

**RULES:**
- Each slide MUST have class="slide-page" (this makes frontend parsing easier)
- Each slide MUST have data-slide-number attribute starting from 1
- Each slide MUST be 1920x1080 px exactly
- NO markdown formatting (use HTML only)
- NO code blocks or backticks in output
- NO DOCTYPE, html, head, body tags (output starts directly with first slide-page div)
- Maintain visual hierarchy from original
- Use inline styles for ALL formatting (no external CSS or style tags)
- Preserve colors, fonts, and layouts from original PDF
- Extract ALL slides from the PDF (one PDF page = one HTML slide-page)

Convert ALL pages from this PDF presentation into FullHD slides with slide-page class:
"""


class PDFAIProcessor:
    """Process PDF chunks with Gemini AI for document/slide conversion"""

    def __init__(self):
        """Initialize AI processor"""
        self.gemini_api_key = config.GEMINI_API_KEY
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        self.client = genai.Client(api_key=self.gemini_api_key)
        self.max_retries = 3
        self.retry_delay = 2  # seconds

        logger.info("🤖 PDF AI Processor initialized (Gemini 2.5 Pro)")

    async def process_pdf_chunks(
        self, pdf_chunks: List[str], document_type: str = "doc", progress_callback=None
    ) -> Tuple[str, Dict]:
        """
        Process multiple PDF chunks with Gemini AI (FOR DOCUMENTS ONLY)
        This method splits large documents into chunks for processing.

        Args:
            pdf_chunks: List of PDF file paths (chunks)
            document_type: Must be "doc" (use process_pdf_slides for slides)
            progress_callback: Optional callback(current, total, chunk_result)

        Returns:
            Tuple of (merged_html_content, metadata)
        """
        if document_type == "slide":
            raise ValueError(
                "Use process_pdf_slides() for slide conversion, not process_pdf_chunks()"
            )

        try:
            total_chunks = len(pdf_chunks)
            logger.info(
                f"📄 Processing {total_chunks} DOCUMENT chunks with Gemini 2.5 Pro "
                f"(A4 format, chunked processing)"
            )

            system_prompt = DOCUMENT_EXTRACTION_PROMPT

            # Process chunks
            chunk_results = []
            processing_times = []

            for idx, chunk_path in enumerate(pdf_chunks):
                logger.info(f"Processing chunk {idx + 1}/{total_chunks}: {chunk_path}")

                start_time = datetime.now()

                try:
                    # Process single chunk with Gemini
                    html_content = await self._process_single_chunk(
                        chunk_path, system_prompt
                    )

                    chunk_results.append(
                        {
                            "chunk_index": idx + 1,
                            "chunk_path": chunk_path,
                            "html_content": html_content,
                            "success": True,
                            "error": None,
                        }
                    )

                    processing_time = (datetime.now() - start_time).total_seconds()
                    processing_times.append(processing_time)

                    logger.info(
                        f"✅ Chunk {idx + 1} processed in {processing_time:.2f}s"
                    )

                except Exception as e:
                    logger.error(f"❌ Failed to process chunk {idx + 1}: {str(e)}")
                    chunk_results.append(
                        {
                            "chunk_index": idx + 1,
                            "chunk_path": chunk_path,
                            "html_content": None,
                            "success": False,
                            "error": str(e),
                        }
                    )

                # Progress callback
                if progress_callback:
                    progress_callback(idx + 1, total_chunks, chunk_results[-1])

            # Merge results for document
            merged_html = self._merge_document_chunks(chunk_results)

            # Count A4 pages in output
            total_a4_pages = merged_html.count('class="a4-page"')

            # Metadata
            successful_chunks = sum(1 for r in chunk_results if r["success"])
            avg_processing_time = (
                sum(processing_times) / len(processing_times) if processing_times else 0
            )

            metadata = {
                "total_chunks": total_chunks,
                "successful_chunks": successful_chunks,
                "failed_chunks": total_chunks - successful_chunks,
                "total_a4_pages": total_a4_pages,
                "ai_provider": "gemini",
                "document_type": "doc",
                "format": "A4",
                "total_processing_time": sum(processing_times),
                "avg_chunk_time": avg_processing_time,
                "processed_at": datetime.now().isoformat(),
                "chunk_results": chunk_results,
            }

            logger.info(
                f"✅ All document chunks processed: {successful_chunks}/{total_chunks} successful, "
                f"{total_a4_pages} A4 pages created"
            )

            return merged_html, metadata

        except Exception as e:
            logger.error(f"Error processing document chunks: {str(e)}")
            raise

    async def process_pdf_slides(
        self, pdf_path: str, progress_callback=None
    ) -> Tuple[str, Dict]:
        """
        Process entire PDF as slides with Gemini AI (FOR PRESENTATIONS ONLY)
        This method processes the ENTIRE PDF at once, with each page becoming a slide.
        NO CHUNKING - all slides in one API call.

        Args:
            pdf_path: Path to PDF presentation file (complete, not chunked)
            progress_callback: Optional callback(status_message)

        Returns:
            Tuple of (html_slides_content, metadata)
        """
        try:
            logger.info(
                f"🎬 Processing PRESENTATION with Gemini 2.5 Pro "
                f"(FullHD slides, entire PDF at once)"
            )

            start_time = datetime.now()

            # Get PDF info
            from src.services.pdf_split_service import get_pdf_split_service

            pdf_service = get_pdf_split_service()
            pdf_info = pdf_service.get_pdf_info(pdf_path)
            total_pages = pdf_info["total_pages"]

            logger.info(
                f"📊 PDF has {total_pages} pages → will create {total_pages} slides"
            )

            if progress_callback:
                progress_callback(f"Processing {total_pages} slides with AI...")

            # Process entire PDF as slides (no chunking)
            html_content = await self._process_single_chunk(
                pdf_path, SLIDE_EXTRACTION_PROMPT
            )

            processing_time = (datetime.now() - start_time).total_seconds()

            # Count slides in output (support both old "slide" and new "slide-page" classes)
            slide_count = html_content.count('class="slide-page"')
            if slide_count == 0:
                # Fallback to old class name for backward compatibility
                slide_count = html_content.count('class="slide"')

            # Extract slide numbers for verification (new format)
            import re

            slide_numbers = re.findall(r'data-slide-number="(\d+)"', html_content)
            if slide_numbers:
                logger.info(f"  📊 Extracted slide numbers: {slide_numbers}")

            # Metadata
            metadata = {
                "total_pages": total_pages,
                "total_slides": slide_count,
                "slide_numbers": slide_numbers if slide_numbers else None,
                "ai_provider": "gemini",
                "document_type": "slide",
                "format": "FullHD_1920x1080",
                "processing_method": "entire_pdf_at_once",
                "processing_time_seconds": processing_time,
                "processed_at": datetime.now().isoformat(),
                "success": True,
            }

            logger.info(
                f"✅ Presentation processed: {slide_count} slides created in {processing_time:.2f}s"
            )

            if slide_count != total_pages:
                logger.warning(
                    f"⚠️ Slide count mismatch: PDF has {total_pages} pages but output has {slide_count} slides"
                )

            return html_content, metadata

        except Exception as e:
            logger.error(f"Error processing slides: {str(e)}")
            raise

    async def _process_single_chunk(self, pdf_path: str, system_prompt: str) -> str:
        """
        Process single PDF chunk with Gemini AI

        Args:
            pdf_path: Path to PDF chunk
            system_prompt: Prompt for AI

        Returns:
            HTML content extracted by AI
        """
        # Try with retries
        for attempt in range(self.max_retries):
            try:
                result = await self._process_with_gemini(pdf_path, system_prompt)
                return result

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {str(e)}"
                )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise

    async def _process_with_gemini(self, pdf_path: str, system_prompt: str) -> str:
        """Process PDF with Gemini 2.5 Pro (native PDF support)"""
        try:
            logger.info(f"Processing {pdf_path} with Gemini 2.5 Pro...")

            # Read PDF content
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()

            # Create PDF part from bytes
            pdf_part = types.Part.from_bytes(
                data=pdf_content, mime_type="application/pdf"
            )

            # Generate response with inline PDF
            response = self.client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[pdf_part, system_prompt],
                config=types.GenerateContentConfig(
                    max_output_tokens=8000,
                    temperature=0.1,  # Low temperature for accurate conversion
                    response_mime_type="text/plain",
                ),
            )

            # Get response text
            if hasattr(response, "text") and response.text:
                html_content = response.text
                logger.info(f"✅ Gemini response: {len(html_content)} characters")
            else:
                raise Exception("No text response from Gemini API")

            # Log token usage
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                logger.info(
                    f"📊 Tokens - Prompt: {response.usage_metadata.prompt_token_count}, "
                    f"Response: {response.usage_metadata.candidates_token_count}"
                )

            # Clean HTML
            html_content = self._clean_html_response(html_content)

            return html_content

        except Exception as e:
            logger.error(f"Gemini processing error: {str(e)}")
            raise

    def _clean_html_response(self, html: str) -> str:
        """Clean AI response to extract pure HTML (strip unwanted wrappers)"""
        import re

        # Remove markdown code blocks
        html = html.strip()

        # Remove ```html and ``` markers
        if html.startswith("```html"):
            html = html[7:]
        elif html.startswith("```"):
            html = html[3:]

        if html.endswith("```"):
            html = html[:-3]

        html = html.strip()

        # ⚠️ CRITICAL: Strip full HTML document wrappers if AI returns them
        # We only want the content inside <body>, not <!DOCTYPE>, <html>, <head>, etc.

        # Remove <!DOCTYPE ...>
        html = re.sub(r"<!DOCTYPE[^>]*>", "", html, flags=re.IGNORECASE)

        # If wrapped in <html>...</html>, extract body content
        html_match = re.search(
            r"<html[^>]*>(.*?)</html>", html, flags=re.IGNORECASE | re.DOTALL
        )
        if html_match:
            html = html_match.group(1)

        # Remove <head>...</head> entirely
        html = re.sub(
            r"<head[^>]*>.*?</head>", "", html, flags=re.IGNORECASE | re.DOTALL
        )

        # If wrapped in <body>...</body>, extract body content
        body_match = re.search(
            r"<body[^>]*>(.*?)</body>", html, flags=re.IGNORECASE | re.DOTALL
        )
        if body_match:
            html = body_match.group(1)

        # Remove any remaining <html> or </html> tags
        html = re.sub(r"</?html[^>]*>", "", html, flags=re.IGNORECASE)

        html = html.strip()

        logger.info(
            f"🧹 Cleaned HTML: {len(html)} chars (removed DOCTYPE/html/head/body wrappers)"
        )

        return html

    def _merge_document_chunks(self, chunk_results: List[Dict]) -> str:
        """Merge document chunk results into single A4 document with continuous page numbering"""
        import re

        successful_results = [
            r for r in chunk_results if r["success"] and r["html_content"]
        ]

        if not successful_results:
            return '<div class="a4-page" data-page-number="1" style="width:210mm; height:297mm; padding:20mm; background:white; box-sizing:border-box;"><p>Error: No content could be extracted</p></div>'

        # Debug: Log individual chunk sizes BEFORE merge
        for idx, r in enumerate(successful_results):
            chunk_size = len(r["html_content"])
            # Extract original page numbers from this chunk (before renumbering)
            original_pages = re.findall(r'data-page-number="(\d+)"', r["html_content"])
            logger.info(
                f"  📦 Chunk {idx + 1}: {chunk_size} chars, "
                f"{len(original_pages)} pages (original numbers: {original_pages})"
            )

        # Renumber pages continuously across chunks
        html_parts = []
        current_page_number = 1

        for chunk_idx, chunk_result in enumerate(successful_results):
            chunk_html = chunk_result["html_content"]

            # Track page numbers BEFORE and AFTER renumbering for this chunk
            old_page_numbers = re.findall(r'data-page-number="(\d+)"', chunk_html)
            chunk_start_page = current_page_number

            # Find all page divs and renumber them
            # Pattern matches: data-page-number="X" where X is any number
            def replace_page_number(match):
                nonlocal current_page_number
                replacement = f'data-page-number="{current_page_number}"'
                current_page_number += 1
                return replacement

            # Replace page numbers in this chunk
            renumbered_chunk = re.sub(
                r'data-page-number="\d+"', replace_page_number, chunk_html
            )

            chunk_end_page = current_page_number - 1
            new_page_numbers = list(range(chunk_start_page, current_page_number))

            logger.info(
                f"  🔢 Chunk {chunk_idx + 1} renumbered: {old_page_numbers} → {new_page_numbers}"
            )

            html_parts.append(renumbered_chunk)

        # Wrap all chunks in document container
        merged = (
            '<div class="a4-document" style="background:#f5f5f5; padding:20px;">\n'
            + "\n\n".join(html_parts)
            + "\n</div>"
        )

        # Count total A4 pages (should equal current_page_number - 1)
        page_count = merged.count('class="a4-page"')
        total_pages = current_page_number - 1

        logger.info(
            f"📄 Merged {len(successful_results)} chunks into {total_pages} A4 pages "
            f"(verified: {page_count} page divs), total size: {len(merged)} chars"
        )
        return merged

    async def convert_existing_document(
        self, pdf_path: str, target_type: str = "doc", chunk_size: int = 10
    ) -> Tuple[str, Dict]:
        """
        Convert existing PDF document with Gemini AI

        Args:
            pdf_path: Path to PDF file
            target_type: "doc" (A4 document) or "slide" (FullHD presentation)
            chunk_size: Pages per chunk (only used for "doc", ignored for "slide")

        Returns:
            Tuple of (html_content, metadata)
        """
        try:
            if target_type == "slide":
                # SLIDE: Process entire PDF at once (no chunking)
                logger.info(f"🎬 Converting to SLIDES: {pdf_path} (no chunking)")
                html_content, metadata = await self.process_pdf_slides(pdf_path)
                return html_content, metadata

            elif target_type == "doc":
                # DOCUMENT: Split into chunks for processing
                from src.services.pdf_split_service import get_pdf_split_service

                pdf_service = get_pdf_split_service()

                logger.info(
                    f"📄 Converting to DOCUMENT: {pdf_path} (chunk_size: {chunk_size})"
                )
                chunks = pdf_service.split_pdf_to_chunks(pdf_path, chunk_size)

                # Process chunks with Gemini
                html_content, metadata = await self.process_pdf_chunks(
                    chunks, document_type="doc"
                )

                # Cleanup chunks
                for chunk_path in chunks:
                    try:
                        os.remove(chunk_path)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup chunk {chunk_path}: {e}")

                return html_content, metadata

            else:
                raise ValueError(
                    f"Invalid target_type: {target_type}. Must be 'doc' or 'slide'"
                )

        except Exception as e:
            logger.error(f"Error converting document: {str(e)}")
            raise


# Singleton instance
_pdf_ai_processor = None


def get_pdf_ai_processor() -> PDFAIProcessor:
    """Get singleton instance of PDFAIProcessor"""
    global _pdf_ai_processor
    if _pdf_ai_processor is None:
        _pdf_ai_processor = PDFAIProcessor()
    return _pdf_ai_processor
