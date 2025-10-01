"""
Gemini PDF Handler Service
Special service for handling PDF files with Gemini API

IMPORTANT: Only PDF files can be sent directly to Gemini.
Other formats (DOCX, TXT, MD) must be parsed to text first.
"""

import logging
from typing import Optional, Dict, Any, Tuple
import os
import tempfile
import httpx

logger = logging.getLogger(__name__)

# Check if Gemini is available
try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed")


class GeminiPDFHandler:
    """
    Handler for PDF files with Gemini API

    ONLY PDF files are supported for direct upload to Gemini.
    Other file formats (DOCX, TXT, MD) must be converted to text before processing.
    """

    # Gemini 2.5 Pro limits
    MAX_INPUT_TOKENS = 1048576  # 1M+ tokens
    MAX_OUTPUT_TOKENS = 65536  # 65k tokens

    # Estimate: 1 page PDF ≈ 500-800 tokens (varies by content density)
    TOKENS_PER_PAGE_LOW = 500  # Simple text
    TOKENS_PER_PAGE_HIGH = 800  # Dense content

    @classmethod
    def estimate_pdf_tokens(cls, num_pages: int, is_dense: bool = False) -> int:
        """
        Estimate tokens for a PDF file

        Args:
            num_pages: Number of pages in PDF
            is_dense: Whether content is dense (tables, complex layout)

        Returns:
            Estimated token count
        """
        tokens_per_page = (
            cls.TOKENS_PER_PAGE_HIGH if is_dense else cls.TOKENS_PER_PAGE_LOW
        )
        return num_pages * tokens_per_page

    @classmethod
    def calculate_max_pdf_pages(cls, additional_context_tokens: int = 0) -> int:
        """
        Calculate maximum PDF pages that can be processed

        Args:
            additional_context_tokens: Tokens used by additional context

        Returns:
            Maximum number of pages
        """
        available_tokens = (
            cls.MAX_INPUT_TOKENS - additional_context_tokens - cls.MAX_OUTPUT_TOKENS
        )
        max_pages = (
            available_tokens // cls.TOKENS_PER_PAGE_HIGH
        )  # Use high estimate for safety

        return max_pages

    @classmethod
    def is_pdf_file(cls, file_path: str) -> bool:
        """
        Check if file is a PDF

        Args:
            file_path: File path or URL

        Returns:
            True if file is PDF, False otherwise
        """
        return file_path.lower().endswith(".pdf")

    @classmethod
    async def process_pdf_with_gemini(
        cls,
        pdf_file_path: str,
        user_query: str,
        highlighted_text: Optional[str] = None,
        operation_type: str = "general_edit",
        parameters: Optional[Dict] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Process PDF file directly with Gemini API

        ONLY PDF FILES ARE SUPPORTED!
        Do not call this for DOCX, TXT, MD - they must be parsed to text first.

        Args:
            pdf_file_path: Path to PDF file (local or R2 URL) - MUST be .pdf
            user_query: User's editing request
            highlighted_text: Text that user selected/highlighted
            operation_type: Type of operation
            parameters: Additional parameters

        Returns:
            (success, generated_html, metadata)
        """
        if not GEMINI_AVAILABLE:
            return False, "", {"error": "Gemini not available"}

        # Validate that this is actually a PDF
        if not cls.is_pdf_file(pdf_file_path):
            logger.error(f"Not a PDF file: {pdf_file_path}")
            return (
                False,
                "",
                {"error": "Only PDF files are supported for direct Gemini upload"},
            )

        try:
            # Initialize Gemini
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return False, "", {"error": "GEMINI_API_KEY not found"}

            genai.configure(api_key=api_key)

            # Upload PDF file to Gemini
            logger.info(f"📄 Uploading PDF to Gemini: {pdf_file_path}")

            # For local files
            if os.path.exists(pdf_file_path):
                uploaded_file = genai.upload_file(pdf_file_path)
            else:
                # For R2 URLs, download first
                logger.info(f"   Downloading PDF from URL...")
                async with httpx.AsyncClient() as client:
                    response = await client.get(pdf_file_path)
                    if response.status_code != 200:
                        return (
                            False,
                            "",
                            {
                                "error": f"Failed to download PDF: {response.status_code}"
                            },
                        )

                    # Save temporarily
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".pdf"
                    ) as tmp_file:
                        tmp_file.write(response.content)
                        tmp_path = tmp_file.name

                    uploaded_file = genai.upload_file(tmp_path)
                    os.unlink(tmp_path)  # Clean up

            logger.info(f"   ✅ PDF uploaded: {uploaded_file.name}")

            # Build prompt
            prompt_parts = [
                _build_operation_prompt(operation_type, parameters),
                f"\nUser Request: {user_query}",
            ]

            if highlighted_text:
                prompt_parts.append(f"\n=== HIGHLIGHTED TEXT ===\n{highlighted_text}")
                prompt_parts.append(
                    "\nPlease focus on the highlighted section in the PDF."
                )

            prompt_parts.append("\n=== INSTRUCTIONS ===")
            prompt_parts.append("1. Analyze the PDF document")
            if highlighted_text:
                prompt_parts.append("2. Pay special attention to the highlighted text")
            prompt_parts.append("3. Perform the requested operation")
            prompt_parts.append("4. Return result as clean HTML")
            prompt_parts.append(
                "5. Do NOT include any explanation, just the HTML output"
            )

            prompt = "\n".join(prompt_parts)

            # Create model (use gemini-2.5-pro as configured)
            model = genai.GenerativeModel("gemini-2.5-pro")

            # Generate content
            logger.info("   🤖 Generating content with Gemini...")
            response = model.generate_content(
                [uploaded_file, prompt],
                generation_config=genai.GenerationConfig(
                    max_output_tokens=cls.MAX_OUTPUT_TOKENS,
                    temperature=0.3,
                ),
            )

            generated_text = response.text

            logger.info(f"   ✅ Gemini response: {len(generated_text)} characters")

            # Extract HTML from response
            from src.services.prompt_engineering_service import PromptEngineeringService

            generated_html = PromptEngineeringService.extract_html_from_response(
                generated_text
            )

            metadata = {
                "tokens_used": (
                    response.usage_metadata.total_token_count
                    if hasattr(response, "usage_metadata")
                    else None
                ),
                "pdf_processed": True,
                "highlighted": bool(highlighted_text),
            }

            return True, generated_html, metadata

        except Exception as e:
            logger.error(f"Gemini PDF processing failed: {e}", exc_info=True)
            return False, "", {"error": str(e)}


def _build_operation_prompt(
    operation_type: str, parameters: Optional[Dict] = None
) -> str:
    """Build operation-specific prompt for Gemini PDF processing"""

    base_prompts = {
        "summarize": "Summarize the content of this PDF document. Focus on key points and main ideas.",
        "change_tone": "Rewrite the content to match the requested tone while preserving meaning.",
        "fix_grammar": "Fix any spelling and grammar errors in the text.",
        "translate": "Translate the content to the target language.",
        "expand_content": "Expand the content with additional details and explanations.",
        "simplify": "Simplify the content to make it easier to understand.",
        "create_table": "Convert the data into a well-structured HTML table.",
        "general_edit": "Perform the requested editing task.",
    }

    prompt = base_prompts.get(operation_type, base_prompts["general_edit"])

    # Add parameters
    if parameters:
        if parameters.get("tone"):
            prompt += f" Use a {parameters['tone']} tone."
        if parameters.get("language"):
            prompt += f" Target language: {parameters['language']}."
        if parameters.get("maxLength"):
            prompt += f" Maximum length: {parameters['maxLength']} words."

    return prompt
