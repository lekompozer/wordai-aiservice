"""
PDF Split Service - Handles PDF manipulation (split, merge, extract pages)
"""

import os
import io
from typing import List, Tuple, Optional, Dict
from pathlib import Path
import logging

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


class PDFSplitService:
    """Service for splitting and merging PDFs"""

    def __init__(self):
        self.max_chunk_size = 50  # Maximum pages per chunk

    def get_pdf_info(self, pdf_path: str) -> Dict:
        """
        Get PDF metadata and info

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with PDF info
        """
        try:
            with open(pdf_path, "rb") as f:
                reader = PdfReader(f)

                info = {
                    "total_pages": len(reader.pages),
                    "file_size": os.path.getsize(pdf_path),
                    "version": reader.pdf_header,
                    "encrypted": reader.is_encrypted,
                }

                # Try to get metadata
                if reader.metadata:
                    info["title"] = reader.metadata.get("/Title", "")
                    info["author"] = reader.metadata.get("/Author", "")
                    info["subject"] = reader.metadata.get("/Subject", "")

                return info

        except Exception as e:
            logger.error(f"Error getting PDF info: {str(e)}")
            raise ValueError(f"Failed to read PDF file: {str(e)}")

    def split_pdf_to_chunks(
        self, pdf_path: str, chunk_size: int = 10, output_dir: Optional[str] = None
    ) -> List[str]:
        """
        Split PDF into equal-sized chunks

        Args:
            pdf_path: Path to source PDF
            chunk_size: Pages per chunk (default: 10)
            output_dir: Directory to save chunks (default: temp dir)

        Returns:
            List of paths to chunk files
        """
        try:
            # Validate chunk size
            if chunk_size <= 0 or chunk_size > self.max_chunk_size:
                raise ValueError(
                    f"Chunk size must be between 1 and {self.max_chunk_size}"
                )

            # Get PDF info
            with open(pdf_path, "rb") as f:
                reader = PdfReader(f)
                total_pages = len(reader.pages)

                if total_pages == 0:
                    raise ValueError("PDF has no pages")

                # Create output directory
                if output_dir is None:
                    output_dir = os.path.join(os.path.dirname(pdf_path), "chunks")
                os.makedirs(output_dir, exist_ok=True)

                # Calculate number of chunks
                num_chunks = (total_pages + chunk_size - 1) // chunk_size

                chunk_files = []
                base_name = Path(pdf_path).stem

                logger.info(
                    f"Splitting PDF: {total_pages} pages into {num_chunks} chunks"
                )

                # Split into chunks
                for chunk_idx in range(num_chunks):
                    start_page = chunk_idx * chunk_size
                    end_page = min((chunk_idx + 1) * chunk_size, total_pages)

                    chunk_path = os.path.join(
                        output_dir, f"{base_name}_chunk_{chunk_idx + 1}.pdf"
                    )

                    self.extract_page_range(
                        pdf_path, start_page + 1, end_page, chunk_path  # 1-indexed
                    )

                    chunk_files.append(chunk_path)
                    logger.info(
                        f"Created chunk {chunk_idx + 1}/{num_chunks}: "
                        f"pages {start_page + 1}-{end_page}"
                    )

                return chunk_files

        except Exception as e:
            logger.error(f"Error splitting PDF: {str(e)}")
            raise

    def extract_page_range(
        self, pdf_path: str, start_page: int, end_page: int, output_path: str
    ) -> str:
        """
        Extract specific page range from PDF

        Args:
            pdf_path: Source PDF path
            start_page: Starting page (1-indexed)
            end_page: Ending page (inclusive, 1-indexed)
            output_path: Output file path

        Returns:
            Path to extracted PDF
        """
        try:
            with open(pdf_path, "rb") as f:
                reader = PdfReader(f)
                total_pages = len(reader.pages)

                # Validate page range
                if start_page < 1 or end_page > total_pages:
                    raise ValueError(
                        f"Invalid page range: {start_page}-{end_page} "
                        f"(total pages: {total_pages})"
                    )

                if start_page > end_page:
                    raise ValueError(
                        f"Start page ({start_page}) must be <= end page ({end_page})"
                    )

                # Create writer and add pages
                writer = PdfWriter()

                for page_num in range(start_page - 1, end_page):
                    writer.add_page(reader.pages[page_num])

                # Write to output file
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as out_f:
                    writer.write(out_f)

                logger.info(f"Extracted pages {start_page}-{end_page} to {output_path}")

                return output_path

        except Exception as e:
            logger.error(f"Error extracting page range: {str(e)}")
            raise

    def merge_pdfs(self, pdf_paths: List[str], output_path: str) -> str:
        """
        Merge multiple PDFs into one

        Args:
            pdf_paths: List of PDF paths to merge
            output_path: Output file path

        Returns:
            Path to merged PDF
        """
        try:
            if not pdf_paths:
                raise ValueError("No PDF files to merge")

            writer = PdfWriter()

            # Add all pages from all PDFs
            for pdf_path in pdf_paths:
                if not os.path.exists(pdf_path):
                    raise FileNotFoundError(f"PDF not found: {pdf_path}")

                with open(pdf_path, "rb") as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        writer.add_page(page)

                logger.info(f"Added {pdf_path} to merge")

            # Write merged PDF
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as out_f:
                writer.write(out_f)

            logger.info(f"Merged {len(pdf_paths)} PDFs into {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"Error merging PDFs: {str(e)}")
            raise

    def calculate_split_suggestions(
        self, pdf_path: str, chunk_size: int = 10
    ) -> List[Dict]:
        """
        Calculate split suggestions for a PDF

        Args:
            pdf_path: Path to PDF file
            chunk_size: Desired pages per chunk

        Returns:
            List of split suggestions with metadata
        """
        try:
            info = self.get_pdf_info(pdf_path)
            total_pages = info["total_pages"]
            file_size = info["file_size"]

            num_chunks = (total_pages + chunk_size - 1) // chunk_size
            avg_page_size = file_size / total_pages if total_pages > 0 else 0

            suggestions = []

            for chunk_idx in range(num_chunks):
                start_page = chunk_idx * chunk_size + 1
                end_page = min((chunk_idx + 1) * chunk_size, total_pages)
                pages_count = end_page - start_page + 1
                estimated_size = avg_page_size * pages_count

                suggestions.append(
                    {
                        "part": chunk_idx + 1,
                        "title": f"Part {chunk_idx + 1}",
                        "start_page": start_page,
                        "end_page": end_page,
                        "pages_count": pages_count,
                        "estimated_size_bytes": int(estimated_size),
                        "estimated_size_mb": round(estimated_size / 1024 / 1024, 2),
                    }
                )

            return suggestions

        except Exception as e:
            logger.error(f"Error calculating split suggestions: {str(e)}")
            raise

    def validate_split_ranges(
        self, total_pages: int, split_ranges: List[Dict]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate custom split ranges

        Args:
            total_pages: Total pages in PDF
            split_ranges: List of ranges with start_page, end_page

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not split_ranges:
            return False, "No split ranges provided"

        # Check each range
        covered_pages = set()

        for idx, range_info in enumerate(split_ranges):
            start = range_info.get("start_page")
            end = range_info.get("end_page")

            if start is None or end is None:
                return False, f"Range {idx + 1}: Missing start_page or end_page"

            if start < 1 or end > total_pages:
                return False, (
                    f"Range {idx + 1}: Pages {start}-{end} out of bounds "
                    f"(1-{total_pages})"
                )

            if start > end:
                return False, (
                    f"Range {idx + 1}: Start page ({start}) > end page ({end})"
                )

            # Check for overlaps
            range_pages = set(range(start, end + 1))
            overlap = covered_pages.intersection(range_pages)

            if overlap:
                return False, (
                    f"Range {idx + 1}: Overlaps with previous ranges "
                    f"(pages {sorted(overlap)})"
                )

            covered_pages.update(range_pages)

        # Optional: Check if all pages are covered
        # (Not required - user might want to split only part of PDF)

        return True, None


# Singleton instance
_pdf_split_service = None


def get_pdf_split_service() -> PDFSplitService:
    """Get singleton instance of PDFSplitService"""
    global _pdf_split_service
    if _pdf_split_service is None:
        _pdf_split_service = PDFSplitService()
    return _pdf_split_service
