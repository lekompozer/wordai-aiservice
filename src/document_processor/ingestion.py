"""
Document Ingestion Pipeline for processing and chunking documents.
Handles various document formats and prepares them for vector storage.
"""

import os
import logging
import uuid
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import asyncio

# Document processing imports
try:
    import PyPDF2
    import docx
    from bs4 import BeautifulSoup

    # import fitz  # PyMuPDF - REMOVED: Now using Gemini for PDF extraction
    PDF_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Document processing dependencies not available: {e}")
    PDF_AVAILABLE = False

# Internal imports
from src.vector_store.qdrant_client import QdrantManager, DocumentChunk

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """Metadata for a document being processed"""

    filename: str
    file_size: int
    file_type: str
    upload_timestamp: str
    user_id: str
    document_id: str
    additional_metadata: Optional[Dict[str, Any]] = None


class DocumentProcessor:
    """
    Handles extraction of text content from various document formats.
    """

    def __init__(self):
        if not PDF_AVAILABLE:
            logger.warning("Document processing dependencies not fully available")

    def extract_text_from_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """
        ⚠️ DEPRECATED: PDF extraction now uses Gemini AI instead of PyMuPDF
        This method should not be called anymore - use Gemini AI for PDF extraction
        """
        logger.warning(
            "❌ extract_text_from_pdf called but PyMuPDF is removed. Use Gemini AI for PDF extraction."
        )
        return [
            {
                "page_number": 1,
                "content": "⚠️ PDF extraction via PyMuPDF is deprecated. Use Gemini AI for document extraction instead.",
                "char_count": 0,
                "extraction_method": "deprecated",
            }
        ]

        # OLD CODE - REMOVED PyMuPDF implementation:
        # try:
        #     doc = fitz.open(file_path)
        #     for page_num in range(len(doc)):
        #         page = doc.load_page(page_num)
        #         text = page.get_text()
        #         ... [PyMuPDF processing code removed] ...
        # except Exception as e:
        #     # Fallback to PyPDF2 ...
        #     ... [Fallback code removed] ...

    def extract_text_from_docx(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract text from DOCX file.

        Args:
            file_path: Path to DOCX file

        Returns:
            List with document content
        """
        try:
            doc = docx.Document(file_path)

            # Extract all paragraphs
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text.strip())

            content = "\n\n".join(paragraphs)

            return [
                {
                    "page_number": 1,
                    "content": content,
                    "char_count": len(content),
                    "extraction_method": "python-docx",
                }
            ]

        except Exception as e:
            logger.error(f"Failed to extract DOCX content: {e}")
            return []

    def extract_text_from_txt(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract text from plain text file.

        Args:
            file_path: Path to text file

        Returns:
            List with file content
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()

            return [
                {
                    "page_number": 1,
                    "content": content.strip(),
                    "char_count": len(content),
                    "extraction_method": "plain_text",
                }
            ]

        except Exception as e:
            logger.error(f"Failed to extract text content: {e}")
            return []

    def extract_text_from_html(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract text from HTML file.

        Args:
            file_path: Path to HTML file

        Returns:
            List with extracted text content
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                html = file.read()

            soup = BeautifulSoup(html, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text content
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            return [
                {
                    "page_number": 1,
                    "content": text,
                    "char_count": len(text),
                    "extraction_method": "beautifulsoup",
                }
            ]

        except Exception as e:
            logger.error(f"Failed to extract HTML content: {e}")
            return []

    def extract_content(self, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        """
        Extract content from file based on type.

        Args:
            file_path: Path to file
            file_type: MIME type or file extension

        Returns:
            List of content dictionaries with page/section information
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()

        if extension == ".pdf" or "pdf" in file_type.lower():
            return self.extract_text_from_pdf(str(file_path))
        elif extension == ".docx" or "docx" in file_type.lower():
            return self.extract_text_from_docx(str(file_path))
        elif extension in [".txt", ".md"] or "text" in file_type.lower():
            return self.extract_text_from_txt(str(file_path))
        elif extension in [".html", ".htm"] or "html" in file_type.lower():
            return self.extract_text_from_html(str(file_path))
        else:
            logger.warning(f"Unsupported file type: {file_type} ({extension})")
            return []


class TextChunker:
    """
    Handles chunking of text content for vector storage.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        """
        Initialize text chunker.

        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Overlap between adjacent chunks
            min_chunk_size: Minimum size for a chunk to be kept
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_text(
        self, text: str, metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text content to chunk
            metadata: Additional metadata to include with each chunk

        Returns:
            List of text chunks with metadata
        """
        if not text or len(text) < self.min_chunk_size:
            return []

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            # Calculate end position
            end = start + self.chunk_size

            # If this is not the last chunk, try to find a good breaking point
            if end < len(text):
                # Look for sentence boundaries within the last 100 characters
                search_start = max(end - 100, start)
                sentence_end = text.rfind(".", search_start, end)
                if sentence_end != -1:
                    end = sentence_end + 1
                else:
                    # Look for other good breaking points
                    for delimiter in [". ", "!\n", "?\n", "\n\n", "\n"]:
                        break_point = text.rfind(delimiter, search_start, end)
                        if break_point != -1:
                            end = break_point + len(delimiter)
                            break

            # Extract chunk
            chunk_text = text[start:end].strip()

            if len(chunk_text) >= self.min_chunk_size:
                chunk_data = {
                    "content": chunk_text,
                    "chunk_index": chunk_index,
                    "start_position": start,
                    "end_position": end,
                    "char_count": len(chunk_text),
                }

                # Add provided metadata
                if metadata:
                    chunk_data.update(metadata)

                chunks.append(chunk_data)
                chunk_index += 1

            # Move start position for next chunk
            start = end - self.chunk_overlap

            # Ensure we don't go backwards
            if start <= 0:
                start = end

        return chunks


class DocumentIngestionPipeline:
    """
    Complete pipeline for document ingestion into vector database.
    """

    def __init__(
        self,
        qdrant_manager: QdrantManager,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """
        Initialize ingestion pipeline.

        Args:
            qdrant_manager: QdrantManager instance for vector storage
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self.qdrant_manager = qdrant_manager
        self.processor = DocumentProcessor()
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    async def process_document(
        self, file_path: str, document_metadata: DocumentMetadata
    ) -> bool:
        """
        Process a document through the complete ingestion pipeline.

        Args:
            file_path: Path to the document file
            document_metadata: Metadata about the document

        Returns:
            True if processing successful
        """
        try:
            logger.info(
                f"Starting ingestion for document {document_metadata.document_id}"
            )

            # Step 1: Extract content from document
            content_pages = self.processor.extract_content(
                file_path, document_metadata.file_type
            )

            if not content_pages:
                logger.error(f"No content extracted from {file_path}")
                return False

            logger.info(f"Extracted content from {len(content_pages)} pages/sections")

            # Step 2: Chunk content from all pages
            all_chunks = []
            global_chunk_index = 0

            for page_info in content_pages:
                page_chunks = self.chunker.chunk_text(
                    page_info["content"],
                    metadata={
                        "page_number": page_info.get("page_number", 1),
                        "extraction_method": page_info.get(
                            "extraction_method", "unknown"
                        ),
                        "source_char_count": page_info.get("char_count", 0),
                    },
                )

                # Create DocumentChunk objects
                for chunk_data in page_chunks:
                    chunk = DocumentChunk(
                        chunk_id=f"{document_metadata.document_id}_{global_chunk_index}",
                        document_id=document_metadata.document_id,
                        user_id=document_metadata.user_id,
                        content=chunk_data["content"],
                        metadata={
                            "filename": document_metadata.filename,
                            "file_type": document_metadata.file_type,
                            "file_size": document_metadata.file_size,
                            "upload_timestamp": document_metadata.upload_timestamp,
                            "page_number": chunk_data.get("page_number"),
                            "extraction_method": chunk_data.get("extraction_method"),
                            "start_position": chunk_data.get("start_position"),
                            "end_position": chunk_data.get("end_position"),
                            "char_count": chunk_data.get("char_count"),
                            **(document_metadata.additional_metadata or {}),
                        },
                        page_number=chunk_data.get("page_number"),
                        chunk_index=global_chunk_index,
                    )

                    all_chunks.append(chunk)
                    global_chunk_index += 1

            logger.info(f"Created {len(all_chunks)} chunks for ingestion")

            # Step 3: Ingest chunks into Qdrant
            success = await self.qdrant_manager.ingest_document_chunks(
                user_id=document_metadata.user_id,
                document_id=document_metadata.document_id,
                chunks=all_chunks,
            )

            if success:
                logger.info(
                    f"Successfully ingested document {document_metadata.document_id}"
                )
                return True
            else:
                logger.error(
                    f"Failed to ingest document {document_metadata.document_id}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Error processing document {document_metadata.document_id}: {e}"
            )
            return False

    async def process_document_from_content(
        self,
        content: str,
        document_metadata: DocumentMetadata,
        content_type: str = "text/plain",
    ) -> bool:
        """
        Process document content directly without file extraction.

        Args:
            content: Raw document content
            document_metadata: Document metadata
            content_type: Content type (for metadata)

        Returns:
            True if processing successful
        """
        try:
            logger.info(
                f"Processing content for document {document_metadata.document_id}"
            )

            # Chunk the content
            chunks_data = self.chunker.chunk_text(
                content,
                metadata={
                    "content_type": content_type,
                    "total_char_count": len(content),
                },
            )

            # Create DocumentChunk objects
            chunks = []
            for i, chunk_data in enumerate(chunks_data):
                chunk = DocumentChunk(
                    chunk_id=f"{document_metadata.document_id}_{i}",
                    document_id=document_metadata.document_id,
                    user_id=document_metadata.user_id,
                    content=chunk_data["content"],
                    metadata={
                        "filename": document_metadata.filename,
                        "file_type": document_metadata.file_type,
                        "file_size": document_metadata.file_size,
                        "upload_timestamp": document_metadata.upload_timestamp,
                        "content_type": content_type,
                        "start_position": chunk_data.get("start_position"),
                        "end_position": chunk_data.get("end_position"),
                        "char_count": chunk_data.get("char_count"),
                        **(document_metadata.additional_metadata or {}),
                    },
                    chunk_index=i,
                )
                chunks.append(chunk)

            # Ingest into Qdrant
            success = await self.qdrant_manager.ingest_document_chunks(
                user_id=document_metadata.user_id,
                document_id=document_metadata.document_id,
                chunks=chunks,
            )

            if success:
                logger.info(
                    f"Successfully processed content for document {document_metadata.document_id}"
                )
                return True
            else:
                logger.error(
                    f"Failed to ingest content for document {document_metadata.document_id}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Error processing content for document {document_metadata.document_id}: {e}"
            )
            return False


# Factory function
def create_ingestion_pipeline(
    qdrant_manager: QdrantManager,
) -> DocumentIngestionPipeline:
    """
    Create DocumentIngestionPipeline with default settings.

    Args:
        qdrant_manager: Configured QdrantManager instance

    Returns:
        DocumentIngestionPipeline instance
    """
    chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
    chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))

    return DocumentIngestionPipeline(
        qdrant_manager=qdrant_manager,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
