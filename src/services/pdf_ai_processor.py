"""
PDF AI Processor - Process PDF chunks with AI (Gemini/GPT-4)
"""
import os
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json

from src.providers.ai_provider_manager import AIProviderManager
import config.config as config

logger = logging.getLogger(__name__)


# ===== AI PROMPTS =====

DOCUMENT_EXTRACTION_PROMPT = """
You are an expert document converter. Convert this PDF content into clean, structured HTML for a document editor.

**REQUIREMENTS:**
1. Maintain document structure (headings, paragraphs, lists)
2. Preserve text formatting (bold, italic, underline)
3. Keep tables structured
4. Extract images and reference them
5. Maintain reading order

**OUTPUT FORMAT:**
Return valid HTML with proper semantic tags:
- <h1>, <h2>, <h3> for headings
- <p> for paragraphs
- <ul>/<ol> for lists
- <table> for tables
- <strong>, <em> for emphasis
- <img> for images (with alt text)

**EXAMPLE OUTPUT:**
```html
<h1>Document Title</h1>
<p>Introduction paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
<h2>Section 1</h2>
<p>Content here...</p>
<ul>
  <li>Item 1</li>
  <li>Item 2</li>
</ul>
<table>
  <tr><th>Header 1</th><th>Header 2</th></tr>
  <tr><td>Data 1</td><td>Data 2</td></tr>
</table>
```

**RULES:**
- NO markdown formatting (use HTML only)
- NO code blocks or backticks
- Keep ALL content from the PDF
- Maintain visual hierarchy
- Clean, semantic HTML only

Convert the following PDF content:
"""

SLIDE_EXTRACTION_PROMPT = """
You are an expert presentation converter. Convert this PDF slide content into clean HTML slides.

**REQUIREMENTS:**
1. Each slide is a separate <div> with class="slide"
2. Maintain slide layout and structure
3. Preserve visual hierarchy
4. Extract images and position them correctly
5. Keep bullet points and lists

**OUTPUT FORMAT:**
Return valid HTML with one slide per <div>:

```html
<div class="slide" style="width:1920px;height:1080px;">
  <h1>Slide Title</h1>
  <p>Subtitle or content</p>
  <ul>
    <li>Bullet point 1</li>
    <li>Bullet point 2</li>
  </ul>
  <img src="image1.jpg" alt="Chart" style="width:800px;height:600px;">
</div>

<div class="slide" style="width:1920px;height:1080px;">
  <h1>Next Slide</h1>
  <p>Content...</p>
</div>
```

**RULES:**
- Each slide MUST have class="slide"
- Use inline styles for positioning
- Standard slide size: 1920x1080 (FullHD 16:9)
- NO markdown formatting
- Clean, semantic HTML only
- Separate slides with blank lines

Convert the following PDF slides:
"""


class PDFAIProcessor:
    """Process PDF chunks with AI for document/slide conversion"""
    
    def __init__(self):
        """Initialize AI processor"""
        self.ai_manager = AIProviderManager(
            deepseek_api_key=config.DEEPSEEK_API_KEY,
            chatgpt_api_key=config.CHATGPT_API_KEY,
            gemini_api_key=config.GEMINI_API_KEY,
        )
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        logger.info("🤖 PDF AI Processor initialized")
    
    async def process_pdf_chunks(
        self,
        pdf_chunks: List[str],
        document_type: str = "doc",
        ai_provider: str = "gemini",
        progress_callback = None
    ) -> Tuple[str, Dict]:
        """
        Process multiple PDF chunks with AI
        
        Args:
            pdf_chunks: List of PDF file paths (chunks)
            document_type: "doc" or "slide"
            ai_provider: "gemini" or "gpt4"
            progress_callback: Optional callback(current, total, chunk_result)
            
        Returns:
            Tuple of (merged_html_content, metadata)
        """
        try:
            total_chunks = len(pdf_chunks)
            logger.info(
                f"Processing {total_chunks} PDF chunks with {ai_provider} "
                f"(type: {document_type})"
            )
            
            # Select prompt based on document type
            if document_type == "slide":
                system_prompt = SLIDE_EXTRACTION_PROMPT
            else:
                system_prompt = DOCUMENT_EXTRACTION_PROMPT
            
            # Process chunks
            chunk_results = []
            processing_times = []
            
            for idx, chunk_path in enumerate(pdf_chunks):
                logger.info(f"Processing chunk {idx + 1}/{total_chunks}: {chunk_path}")
                
                start_time = datetime.now()
                
                try:
                    # Process single chunk
                    html_content = await self._process_single_chunk(
                        chunk_path,
                        system_prompt,
                        ai_provider
                    )
                    
                    chunk_results.append({
                        'chunk_index': idx + 1,
                        'chunk_path': chunk_path,
                        'html_content': html_content,
                        'success': True,
                        'error': None
                    })
                    
                    processing_time = (datetime.now() - start_time).total_seconds()
                    processing_times.append(processing_time)
                    
                    logger.info(
                        f"✅ Chunk {idx + 1} processed in {processing_time:.2f}s"
                    )
                    
                except Exception as e:
                    logger.error(f"❌ Failed to process chunk {idx + 1}: {str(e)}")
                    chunk_results.append({
                        'chunk_index': idx + 1,
                        'chunk_path': chunk_path,
                        'html_content': None,
                        'success': False,
                        'error': str(e)
                    })
                
                # Progress callback
                if progress_callback:
                    progress_callback(idx + 1, total_chunks, chunk_results[-1])
            
            # Merge results
            merged_html = self._merge_chunk_results(chunk_results, document_type)
            
            # Metadata
            successful_chunks = sum(1 for r in chunk_results if r['success'])
            avg_processing_time = (
                sum(processing_times) / len(processing_times)
                if processing_times else 0
            )
            
            metadata = {
                'total_chunks': total_chunks,
                'successful_chunks': successful_chunks,
                'failed_chunks': total_chunks - successful_chunks,
                'ai_provider': ai_provider,
                'document_type': document_type,
                'total_processing_time': sum(processing_times),
                'avg_chunk_time': avg_processing_time,
                'processed_at': datetime.now().isoformat(),
                'chunk_results': chunk_results
            }
            
            logger.info(
                f"✅ All chunks processed: {successful_chunks}/{total_chunks} successful"
            )
            
            return merged_html, metadata
            
        except Exception as e:
            logger.error(f"Error processing PDF chunks: {str(e)}")
            raise
    
    async def _process_single_chunk(
        self,
        pdf_path: str,
        system_prompt: str,
        ai_provider: str = "gemini"
    ) -> str:
        """
        Process single PDF chunk with AI
        
        Args:
            pdf_path: Path to PDF chunk
            system_prompt: Prompt for AI
            ai_provider: "gemini" or "gpt4"
            
        Returns:
            HTML content extracted by AI
        """
        # Try with retries
        for attempt in range(self.max_retries):
            try:
                # Use Gemini file upload API (supports PDFs directly)
                if ai_provider == "gemini":
                    result = await self._process_with_gemini(
                        pdf_path,
                        system_prompt
                    )
                else:
                    result = await self._process_with_gpt4(
                        pdf_path,
                        system_prompt
                    )
                
                return result
                
            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {str(e)}"
                )
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise
    
    async def _process_with_gemini(
        self,
        pdf_path: str,
        system_prompt: str
    ) -> str:
        """Process PDF with Gemini AI"""
        try:
            # Upload PDF to Gemini
            logger.info(f"Uploading {pdf_path} to Gemini...")
            
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            # Use Gemini file API
            response = await self.ai_manager.generate_content_with_file(
                provider="gemini",
                file_content=pdf_content,
                file_type="application/pdf",
                prompt=system_prompt,
                model="gemini-1.5-pro"  # Supports PDFs
            )
            
            # Extract text from response
            if isinstance(response, dict):
                html_content = response.get('text', '')
            else:
                html_content = str(response)
            
            # Clean HTML
            html_content = self._clean_html_response(html_content)
            
            return html_content
            
        except Exception as e:
            logger.error(f"Gemini processing error: {str(e)}")
            raise
    
    async def _process_with_gpt4(
        self,
        pdf_path: str,
        system_prompt: str
    ) -> str:
        """Process PDF with GPT-4"""
        try:
            # GPT-4 doesn't support PDF directly
            # Need to convert PDF pages to images first
            from pdf2image import convert_from_path
            
            logger.info(f"Converting {pdf_path} to images for GPT-4...")
            
            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=150)
            
            # Process each image
            results = []
            for idx, image in enumerate(images):
                logger.info(f"Processing page {idx + 1}/{len(images)}")
                
                # Save image to bytes
                import io
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
                
                # Send to GPT-4 Vision
                response = await self.ai_manager.generate_content_with_vision(
                    provider="chatgpt",
                    image_content=img_bytes,
                    prompt=system_prompt,
                    model="gpt-4-vision-preview"
                )
                
                if isinstance(response, dict):
                    page_html = response.get('text', '')
                else:
                    page_html = str(response)
                
                results.append(page_html)
            
            # Merge pages
            merged_html = '\n\n'.join(results)
            
            # Clean HTML
            merged_html = self._clean_html_response(merged_html)
            
            return merged_html
            
        except Exception as e:
            logger.error(f"GPT-4 processing error: {str(e)}")
            raise
    
    def _clean_html_response(self, html: str) -> str:
        """Clean AI response to extract pure HTML"""
        # Remove markdown code blocks
        html = html.strip()
        
        # Remove ```html and ``` markers
        if html.startswith('```html'):
            html = html[7:]
        elif html.startswith('```'):
            html = html[3:]
        
        if html.endswith('```'):
            html = html[:-3]
        
        html = html.strip()
        
        return html
    
    def _merge_chunk_results(
        self,
        chunk_results: List[Dict],
        document_type: str
    ) -> str:
        """Merge chunk results into single HTML"""
        successful_results = [
            r for r in chunk_results if r['success'] and r['html_content']
        ]
        
        if not successful_results:
            return "<p>Error: No content could be extracted</p>"
        
        if document_type == "slide":
            # For slides, just concatenate
            html_parts = [r['html_content'] for r in successful_results]
            merged = '\n\n'.join(html_parts)
        else:
            # For docs, wrap in container
            html_parts = [r['html_content'] for r in successful_results]
            merged = '<div class="document-content">\n' + '\n\n'.join(html_parts) + '\n</div>'
        
        return merged
    
    async def convert_existing_document(
        self,
        pdf_path: str,
        target_type: str = "doc",
        chunk_size: int = 10,
        ai_provider: str = "gemini"
    ) -> Tuple[str, Dict]:
        """
        Convert existing PDF document with AI
        
        Args:
            pdf_path: Path to PDF file
            target_type: "doc" or "slide"
            chunk_size: Pages per chunk
            ai_provider: "gemini" or "gpt4"
            
        Returns:
            Tuple of (html_content, metadata)
        """
        try:
            # Split PDF into chunks
            from src.services.pdf_split_service import get_pdf_split_service
            
            pdf_service = get_pdf_split_service()
            
            logger.info(f"Splitting PDF: {pdf_path} (chunk_size: {chunk_size})")
            chunks = pdf_service.split_pdf_to_chunks(pdf_path, chunk_size)
            
            # Process chunks with AI
            html_content, metadata = await self.process_pdf_chunks(
                chunks,
                document_type=target_type,
                ai_provider=ai_provider
            )
            
            # Cleanup chunks
            for chunk_path in chunks:
                try:
                    os.remove(chunk_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup chunk {chunk_path}: {e}")
            
            return html_content, metadata
            
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
