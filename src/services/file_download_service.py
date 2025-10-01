"""
File Download and Parsing Service
Downloads files from R2 URLs, parses them to text, and manages temp files
"""

import os
import tempfile
import logging
import aiohttp
import asyncio
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class FileDownloadService:
    """
    Service for downloading and parsing files from R2 storage

    Supports:
    - TXT: Direct text (no parsing needed)
    - DOCX: Extract text using python-docx
    - PDF: Extract text using PyPDF2

    Special Cases:
    - PDF + Gemini: Can use file path directly (no parsing needed)
    """

    # Track temp files per user for cleanup
    _user_temp_files: dict = {}

    @classmethod
    async def download_and_parse_file(
        cls, file_url: str, file_type: str, user_id: str, provider: str = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Download file from R2 and parse to text

        Args:
            file_url: R2 URL of the file
            file_type: File extension (txt, docx, pdf)
            user_id: User ID for temp file tracking
            provider: AI provider name (for special cases like PDF+Gemini)

        Returns:
            (text_content, temp_file_path) or (None, None) if failed

        Note:
            - For PDF + Gemini: Returns (None, temp_file_path) - Gemini uses file directly
            - For other cases: Returns (text_content, temp_file_path)
        """
        try:
            file_type = file_type.lower().replace(".", "")

            # Cleanup old temp files for this user
            await cls._cleanup_user_temp_files(user_id)

            # Download file to temp directory
            logger.info(
                f"📥 Downloading {file_type.upper()} from R2: {file_url[:50]}..."
            )
            temp_file_path = await cls._download_file(file_url, file_type)

            if not temp_file_path:
                logger.error(f"❌ Failed to download file from {file_url}")
                return None, None

            # Track temp file for cleanup
            if user_id not in cls._user_temp_files:
                cls._user_temp_files[user_id] = []
            cls._user_temp_files[user_id].append(temp_file_path)

            logger.info(f"✅ Downloaded to: {temp_file_path}")

            # Special case: PDF + Gemini - return file path, no parsing
            if file_type == "pdf" and provider and provider.lower() == "gemini":
                logger.info(f"🔥 PDF + Gemini: Returning file path (no parsing)")
                return None, temp_file_path

            # Parse file to text
            logger.info(f"📝 Parsing {file_type.upper()} to text...")
            text_content = await cls._parse_file(temp_file_path, file_type)

            if text_content:
                logger.info(
                    f"✅ Parsed {len(text_content)} characters from {file_type.upper()}"
                )
                return text_content, temp_file_path
            else:
                logger.error(f"❌ Failed to parse {file_type.upper()} file")
                return None, None

        except Exception as e:
            logger.error(f"❌ Error downloading/parsing file: {e}")
            return None, None

    @classmethod
    async def _download_file(cls, url: str, file_type: str) -> Optional[str]:
        """
        Download file from URL to temp directory

        Returns:
            Path to downloaded temp file
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status != 200:
                        logger.error(f"❌ Failed to download: HTTP {response.status}")
                        return None

                    # Create temp file
                    temp_dir = tempfile.gettempdir()
                    temp_file = tempfile.NamedTemporaryFile(
                        delete=False, suffix=f".{file_type}", dir=temp_dir
                    )

                    # Write content
                    content = await response.read()
                    temp_file.write(content)
                    temp_file.close()

                    return temp_file.name

        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout downloading file from {url}")
            return None
        except Exception as e:
            logger.error(f"❌ Error downloading file: {e}")
            return None

    @classmethod
    async def _parse_file(cls, file_path: str, file_type: str) -> Optional[str]:
        """
        Parse file to text based on file type

        Args:
            file_path: Path to temp file
            file_type: File extension (txt, docx, pdf)

        Returns:
            Extracted text content
        """
        try:
            if file_type == "txt":
                return await cls._parse_txt(file_path)
            elif file_type == "docx":
                return await cls._parse_docx(file_path)
            elif file_type == "pdf":
                return await cls._parse_pdf(file_path)
            else:
                logger.error(f"❌ Unsupported file type: {file_type}")
                return None

        except Exception as e:
            logger.error(f"❌ Error parsing {file_type} file: {e}")
            return None

    @classmethod
    async def _parse_txt(cls, file_path: str) -> Optional[str]:
        """Parse TXT file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, "r", encoding="latin-1") as f:
                return f.read()

    @classmethod
    async def _parse_docx(cls, file_path: str) -> Optional[str]:
        """Parse DOCX file using python-docx"""
        try:
            from docx import Document

            doc = Document(file_path)

            # Extract text from paragraphs
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)

            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            text_parts.append(cell.text)

            return "\n".join(text_parts)

        except ImportError:
            logger.error("❌ python-docx not installed. Run: pip install python-docx")
            return None
        except Exception as e:
            logger.error(f"❌ Error parsing DOCX: {e}")
            return None

    @classmethod
    async def _parse_pdf(cls, file_path: str) -> Optional[str]:
        """Parse PDF file using PyPDF2"""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(file_path)

            # Extract text from all pages
            text_parts = []
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                if text.strip():
                    text_parts.append(text)

            return "\n".join(text_parts)

        except ImportError:
            logger.error("❌ PyPDF2 not installed. Run: pip install PyPDF2")
            return None
        except Exception as e:
            logger.error(f"❌ Error parsing PDF: {e}")
            return None

    @classmethod
    async def _cleanup_user_temp_files(cls, user_id: str):
        """
        Delete old temp files for user when they switch to a new file

        Args:
            user_id: User ID
        """
        if user_id not in cls._user_temp_files:
            return

        old_files = cls._user_temp_files[user_id]
        deleted_count = 0

        for file_path in old_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"⚠️ Failed to delete temp file {file_path}: {e}")

        if deleted_count > 0:
            logger.info(f"🗑️ Cleaned up {deleted_count} temp files for user {user_id}")

        # Clear list
        cls._user_temp_files[user_id] = []

    @classmethod
    async def cleanup_all_temp_files(cls):
        """
        Cleanup all temp files (call on shutdown)
        """
        total_deleted = 0

        for user_id in list(cls._user_temp_files.keys()):
            for file_path in cls._user_temp_files[user_id]:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        total_deleted += 1
                except Exception as e:
                    logger.warning(f"⚠️ Failed to delete temp file {file_path}: {e}")

        cls._user_temp_files.clear()

        if total_deleted > 0:
            logger.info(f"🗑️ Cleaned up {total_deleted} temp files on shutdown")
