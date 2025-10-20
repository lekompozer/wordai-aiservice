"""
File Converter Utilities
Convert files between formats for AI processing
"""

import io
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import mimetypes

try:
    import PyPDF2

    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    from docx import Document

    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

from src.utils.logger import setup_logger

logger = setup_logger()


class FileConverter:
    """Convert files between formats and extract content"""

    @staticmethod
    def get_file_type(file_path: str) -> str:
        """
        Determine file type from path

        Returns: "pdf", "docx", "txt", "unknown"
        """
        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            return "pdf"
        elif ext in [".docx", ".doc"]:
            return "docx"
        elif ext == ".txt":
            return "txt"
        else:
            # Try to guess from mime type
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type:
                if "pdf" in mime_type:
                    return "pdf"
                elif "word" in mime_type or "document" in mime_type:
                    return "docx"
                elif "text" in mime_type:
                    return "txt"

        return "unknown"

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> Tuple[str, int]:
        """
        Extract text from PDF file

        Returns:
            (extracted_text, page_count)
        """
        try:
            # Try pdfplumber first (better extraction)
            if PDFPLUMBER_AVAILABLE:
                logger.info("📄 Using pdfplumber for PDF extraction")
                with pdfplumber.open(file_path) as pdf:
                    pages = []
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            pages.append(text)

                    full_text = "\n\n".join(pages)
                    page_count = len(pdf.pages)

                    logger.info(
                        f"✅ Extracted {len(full_text)} chars from {page_count} pages"
                    )
                    return full_text, page_count

            # Fallback to PyPDF2
            elif PYPDF2_AVAILABLE:
                logger.info("📄 Using PyPDF2 for PDF extraction")
                with open(file_path, "rb") as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    page_count = len(pdf_reader.pages)

                    pages = []
                    for page in pdf_reader.pages:
                        text = page.extract_text()
                        if text:
                            pages.append(text)

                    full_text = "\n\n".join(pages)
                    logger.info(
                        f"✅ Extracted {len(full_text)} chars from {page_count} pages"
                    )
                    return full_text, page_count

            else:
                logger.error(
                    "❌ No PDF library available (install PyPDF2 or pdfplumber)"
                )
                return "", 0

        except Exception as e:
            logger.error(f"❌ PDF extraction error: {e}")
            return "", 0

    @staticmethod
    def extract_text_from_docx(file_path: str) -> Tuple[str, int]:
        """
        Extract text from DOCX file

        Returns:
            (extracted_text, estimated_page_count)
        """
        try:
            if not PYTHON_DOCX_AVAILABLE:
                logger.error("❌ python-docx not available")
                return "", 0

            logger.info("📄 Extracting text from DOCX")
            doc = Document(file_path)

            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)

            full_text = "\n\n".join(paragraphs)

            # Estimate pages (500 words per page)
            word_count = len(full_text.split())
            estimated_pages = max(1, word_count // 500)

            logger.info(
                f"✅ Extracted {len(full_text)} chars (~{estimated_pages} pages)"
            )
            return full_text, estimated_pages

        except Exception as e:
            logger.error(f"❌ DOCX extraction error: {e}")
            return "", 0

    @staticmethod
    def extract_text_from_txt(file_path: str) -> Tuple[str, int]:
        """
        Read text from TXT file

        Returns:
            (text_content, estimated_page_count)
        """
        try:
            logger.info("📄 Reading TXT file")

            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

            # Estimate pages (500 words per page)
            word_count = len(text.split())
            estimated_pages = max(1, word_count // 500)

            logger.info(f"✅ Read {len(text)} chars (~{estimated_pages} pages)")
            return text, estimated_pages

        except UnicodeDecodeError:
            # Try different encoding
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    text = f.read()
                word_count = len(text.split())
                estimated_pages = max(1, word_count // 500)
                logger.info(f"✅ Read {len(text)} chars with latin-1 encoding")
                return text, estimated_pages
            except Exception as e:
                logger.error(f"❌ TXT read error: {e}")
                return "", 0
        except Exception as e:
            logger.error(f"❌ TXT read error: {e}")
            return "", 0

    @staticmethod
    def extract_text(file_path: str) -> Tuple[str, int]:
        """
        Auto-detect and extract text from file

        Returns:
            (extracted_text, page_count)
        """
        file_type = FileConverter.get_file_type(file_path)

        logger.info(f"🔍 Detected file type: {file_type}")

        if file_type == "pdf":
            return FileConverter.extract_text_from_pdf(file_path)
        elif file_type == "docx":
            return FileConverter.extract_text_from_docx(file_path)
        elif file_type == "txt":
            return FileConverter.extract_text_from_txt(file_path)
        else:
            logger.error(f"❌ Unsupported file type: {file_type}")
            return "", 0

    @staticmethod
    def docx_to_pdf(docx_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Convert DOCX to PDF using LibreOffice

        Note: Requires LibreOffice installed on system

        Returns:
            Path to converted PDF or None if failed
        """
        try:
            import subprocess

            if output_path is None:
                # Create temp file
                output_path = docx_path.replace(".docx", ".pdf")

            # Try LibreOffice conversion
            logger.info(f"📄 Converting DOCX to PDF: {docx_path}")

            result = subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    os.path.dirname(output_path),
                    docx_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"✅ Converted to PDF: {output_path}")
                return output_path
            else:
                logger.error(f"❌ LibreOffice conversion failed: {result.stderr}")
                return None

        except FileNotFoundError:
            logger.error(
                "❌ LibreOffice not found. Install with: brew install libreoffice"
            )
            return None
        except subprocess.TimeoutExpired:
            logger.error("❌ LibreOffice conversion timeout")
            return None
        except Exception as e:
            logger.error(f"❌ DOCX to PDF conversion error: {e}")
            return None

    @staticmethod
    def txt_to_pdf(txt_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Convert TXT to PDF using reportlab

        Note: Requires reportlab library

        Returns:
            Path to converted PDF or None if failed
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

            if output_path is None:
                output_path = txt_path.replace(".txt", ".pdf")

            logger.info(f"📄 Converting TXT to PDF: {txt_path}")

            # Read text
            with open(txt_path, "r", encoding="utf-8") as f:
                text = f.read()

            # Create PDF
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            # Split into paragraphs
            paragraphs = text.split("\n\n")
            for para in paragraphs:
                if para.strip():
                    p = Paragraph(para, styles["Normal"])
                    story.append(p)
                    story.append(Spacer(1, 12))

            doc.build(story)

            logger.info(f"✅ Converted to PDF: {output_path}")
            return output_path

        except ImportError:
            logger.error(
                "❌ reportlab not available. Install with: pip install reportlab"
            )
            return None
        except Exception as e:
            logger.error(f"❌ TXT to PDF conversion error: {e}")
            return None


# Utility functions for easy import
def extract_text(file_path: str) -> Tuple[str, int]:
    """Extract text from file (PDF, DOCX, TXT)"""
    return FileConverter.extract_text(file_path)


def convert_to_pdf(file_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """Convert DOCX or TXT to PDF"""
    file_type = FileConverter.get_file_type(file_path)

    if file_type == "pdf":
        return file_path  # Already PDF
    elif file_type == "docx":
        return FileConverter.docx_to_pdf(file_path, output_path)
    elif file_type == "txt":
        return FileConverter.txt_to_pdf(file_path, output_path)
    else:
        logger.error(f"❌ Cannot convert {file_type} to PDF")
        return None


def estimate_tokens(text: str) -> int:
    """Estimate token count (1 token ≈ 4 characters)"""
    return len(text) // 4


def estimate_pdf_tokens(page_count: int) -> int:
    """Estimate tokens for PDF based on page count"""
    # Average: ~500 tokens per page
    return page_count * 500
