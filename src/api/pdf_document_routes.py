"""
PDF Document Routes - Upload, Split, Merge, and AI Conversion
"""

import os
import logging
import tempfile
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form, Query
from fastapi.responses import JSONResponse

from src.models.pdf_models import (
    UploadPDFResponse,
    PreviewSplitResponse,
    SplitSuggestion,
    SplitDocumentRequest,
    SplitDocumentResponse,
    SplitDocumentPart,
    ConvertWithAIRequest,
    ConvertWithAIResponse,
    SplitInfoResponse,
    SplitInfoDetail,
    SplitInfoSibling,
    MergeDocumentsRequest,
    MergeDocumentsResponse,
    MergedFromInfo,
)
from src.services.pdf_split_service import get_pdf_split_service
from src.services.pdf_ai_processor import get_pdf_ai_processor
from src.services.document_manager import DocumentManager
from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from config.config import R2_BUCKET_NAME

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["PDF Documents"])

# Initialize services
pdf_split_service = get_pdf_split_service()
pdf_ai_processor = get_pdf_ai_processor()
db_manager = DBManager()
document_manager = DocumentManager(db=db_manager.db)


# Helper function to get R2 client (same pattern as gemini_slide_parser)
def _get_r2_client():
    """Initialize R2Client with full config"""
    from src.storage.r2_client import R2Client
    from src.core.config import APP_CONFIG

    return R2Client(
        account_id=APP_CONFIG["r2_account_id"],
        access_key_id=APP_CONFIG["r2_access_key_id"],
        secret_access_key=APP_CONFIG["r2_secret_access_key"],
        bucket_name=APP_CONFIG["r2_bucket_name"],
        region=APP_CONFIG["r2_region"],
    )


# ❌ ENDPOINT REMOVED: /upload-pdf-ai
# This endpoint was redundant - users should upload via /api/simple-files/upload
# Then convert using /api/documents/{document_id}/convert-with-ai


@router.get("/{document_id}/preview-split", response_model=PreviewSplitResponse)
async def preview_document_split(
    document_id: str,
    chunk_size: int = Query(10, ge=1, le=50),
    user_data: dict = Depends(get_current_user),
):
    """
    Preview how document will be split

    Args:
        document_id: Document ID
        chunk_size: Pages per chunk (1-50, default: 10)

    Returns:
        PreviewSplitResponse with split suggestions
    """
    try:
        user_id = user_data["uid"]

        logger.info(
            f"🔍 Preview split request: doc={document_id}, chunk_size={chunk_size}"
        )

        # Get document from database
        document = db_manager.db.documents.find_one(
            {"document_id": document_id, "user_id": user_id}
        )

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Check if document has PDF
        pdf_r2_path = document.get("pdf_r2_path")
        if not pdf_r2_path:
            raise HTTPException(
                status_code=400, detail="Document does not have PDF file"
            )

        # Download PDF from R2
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            r2_client = _get_r2_client()
            pdf_content = r2_client.download_file(pdf_r2_path)
            temp_pdf.write(pdf_content)
            temp_pdf_path = temp_pdf.name

        try:
            # Calculate split suggestions
            suggestions = pdf_split_service.calculate_split_suggestions(
                temp_pdf_path, chunk_size
            )

            # Calculate total size
            total_size_mb = sum(s["estimated_size_mb"] for s in suggestions)

            # Convert to Pydantic models
            split_suggestions = [
                SplitSuggestion(**suggestion) for suggestion in suggestions
            ]

            response = PreviewSplitResponse(
                success=True,
                document_id=document_id,
                document_title=document.get("title", "Untitled"),
                total_pages=document.get("total_pages", 0),
                chunk_size=chunk_size,
                suggested_splits=split_suggestions,
                total_parts=len(suggestions),
                total_estimated_size_mb=round(total_size_mb, 2),
            )

            logger.info(
                f"✅ Preview generated: {len(suggestions)} parts, "
                f"{total_size_mb:.2f}MB total"
            )

            return response

        finally:
            # Cleanup temp file
            try:
                os.remove(temp_pdf_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file: {e}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Preview split failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


@router.post("/{document_id}/split", response_model=SplitDocumentResponse)
async def split_document(
    document_id: str,
    request: SplitDocumentRequest,
    user_data: dict = Depends(get_current_user),
):
    """
    Split document into multiple parts

    Args:
        document_id: Document ID to split
        request: Split configuration (auto or manual mode)

    Returns:
        SplitDocumentResponse with created document parts
    """
    try:
        start_time = datetime.now()
        user_id = user_data["uid"]

        logger.info(
            f"✂️ Split request: doc={document_id}, mode={request.mode}, "
            f"keep_original={request.keep_original}"
        )

        # Get document from database
        document = db_manager.db.documents.find_one(
            {"document_id": document_id, "user_id": user_id}
        )

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Check if document has PDF
        pdf_r2_path = document.get("pdf_r2_path")
        if not pdf_r2_path:
            raise HTTPException(
                status_code=400, detail="Document does not have PDF file"
            )

        total_pages = document.get("total_pages", 0)

        # Download PDF from R2
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            r2_client = _get_r2_client()
            pdf_content = r2_client.download_file(pdf_r2_path)
            temp_pdf.write(pdf_content)
            temp_pdf_path = temp_pdf.name

        try:
            split_parts = []

            if request.mode == "auto":
                # Auto split with equal chunks
                chunk_size = request.chunk_size or 10

                logger.info(f"🤖 Auto split mode: chunk_size={chunk_size}")

                # Split PDF
                chunk_files = pdf_split_service.split_pdf_to_chunks(
                    temp_pdf_path, chunk_size
                )

                # Create documents for each chunk
                for idx, chunk_path in enumerate(chunk_files):
                    part_num = idx + 1
                    start_page = (idx * chunk_size) + 1
                    end_page = min((idx + 1) * chunk_size, total_pages)
                    pages_count = end_page - start_page + 1

                    # Generate part document ID
                    part_doc_id = f"{document_id}_part{part_num}"
                    part_title = f"{document['title']} - Part {part_num}"

                    # Upload chunk to R2
                    with open(chunk_path, "rb") as f:
                        chunk_content = f.read()

                    part_r2_path = f"documents/{user_id}/{part_doc_id}.pdf"
                    r2_client = _get_r2_client()
                    r2_client.upload_file_object(
                        file_obj=chunk_content,
                        remote_path=part_r2_path,
                        content_type="application/pdf",
                    )

                    # Create part document in database
                    part_document = {
                        "document_id": part_doc_id,
                        "user_id": user_id,
                        "title": part_title,
                        "description": f"Part {part_num} of {document['title']}",
                        "document_type": document["document_type"],
                        "content_html": f"<p>Pages {start_page}-{end_page}</p>",
                        "created_at": datetime.now(),
                        "updated_at": datetime.now(),
                        # PDF info
                        "total_pages": pages_count,
                        "pdf_r2_path": part_r2_path,
                        "pdf_file_size": len(chunk_content),
                        # Split info
                        "is_split_part": True,
                        "original_document_id": document_id,
                        "parent_document_id": document_id,
                        "split_info": {
                            "start_page": start_page,
                            "end_page": end_page,
                            "part_number": part_num,
                            "total_parts": len(chunk_files),
                            "split_mode": "auto",
                        },
                        # AI processing (not done yet for parts)
                        "ai_processed": False,
                    }

                    db_manager.db.documents.insert_one(part_document)

                    split_parts.append(
                        SplitDocumentPart(
                            document_id=part_doc_id,
                            title=part_title,
                            pages=f"{start_page}-{end_page}",
                            pages_count=pages_count,
                            r2_path=part_r2_path,
                            file_size_mb=round(len(chunk_content) / (1024 * 1024), 2),
                            created_at=datetime.now().isoformat(),
                        )
                    )

                    logger.info(f"✅ Created part {part_num}: {part_doc_id}")

                # Cleanup chunk files
                for chunk_path in chunk_files:
                    try:
                        os.remove(chunk_path)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup chunk: {e}")

            else:
                # Manual split with custom ranges
                logger.info(f"✋ Manual split mode: {len(request.split_ranges)} ranges")

                # Validate ranges
                is_valid, error_msg = pdf_split_service.validate_split_ranges(
                    total_pages, [r.dict() for r in request.split_ranges]
                )

                if not is_valid:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid split ranges: {error_msg}"
                    )

                # Extract each range
                for idx, range_info in enumerate(request.split_ranges):
                    part_num = idx + 1

                    # Extract pages
                    part_pdf_path = os.path.join(
                        tempfile.gettempdir(), f"{document_id}_part{part_num}.pdf"
                    )

                    pdf_split_service.extract_page_range(
                        temp_pdf_path,
                        range_info.start_page,
                        range_info.end_page,
                        part_pdf_path,
                    )

                    # Generate part document ID
                    part_doc_id = f"{document_id}_part{part_num}"
                    part_title = range_info.title

                    # Upload to R2
                    with open(part_pdf_path, "rb") as f:
                        part_content = f.read()

                    part_r2_path = f"documents/{user_id}/{part_doc_id}.pdf"
                    r2_client = _get_r2_client()
                    r2_client.upload_file_object(
                        file_obj=part_content,
                        remote_path=part_r2_path,
                        content_type="application/pdf",
                    )

                    pages_count = range_info.end_page - range_info.start_page + 1

                    # Create part document
                    part_document = {
                        "document_id": part_doc_id,
                        "user_id": user_id,
                        "title": part_title,
                        "description": range_info.description
                        or f"Pages {range_info.start_page}-{range_info.end_page}",
                        "document_type": document["document_type"],
                        "content_html": f"<p>Pages {range_info.start_page}-{range_info.end_page}</p>",
                        "created_at": datetime.now(),
                        "updated_at": datetime.now(),
                        # PDF info
                        "total_pages": pages_count,
                        "pdf_r2_path": part_r2_path,
                        "pdf_file_size": len(part_content),
                        # Split info
                        "is_split_part": True,
                        "original_document_id": document_id,
                        "parent_document_id": document_id,
                        "split_info": {
                            "start_page": range_info.start_page,
                            "end_page": range_info.end_page,
                            "part_number": part_num,
                            "total_parts": len(request.split_ranges),
                            "split_mode": "manual",
                        },
                        "ai_processed": False,
                    }

                    db_manager.db.documents.insert_one(part_document)

                    split_parts.append(
                        SplitDocumentPart(
                            document_id=part_doc_id,
                            title=part_title,
                            pages=f"{range_info.start_page}-{range_info.end_page}",
                            pages_count=pages_count,
                            r2_path=part_r2_path,
                            file_size_mb=round(len(part_content) / (1024 * 1024), 2),
                            created_at=datetime.now().isoformat(),
                        )
                    )

                    # Cleanup part file
                    try:
                        os.remove(part_pdf_path)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup part: {e}")

                    logger.info(f"✅ Created part {part_num}: {part_doc_id}")

            # Update original document with child IDs
            child_ids = [part.document_id for part in split_parts]
            db_manager.db.documents.update_one(
                {"document_id": document_id},
                {
                    "$set": {
                        "child_document_ids": child_ids,
                        "updated_at": datetime.now(),
                    }
                },
            )

            # Delete original if not keeping
            original_kept = request.keep_original
            if not request.keep_original:
                db_manager.db.documents.delete_one({"document_id": document_id})
                logger.info(f"🗑️ Deleted original document: {document_id}")

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            response = SplitDocumentResponse(
                success=True,
                original_document_id=document_id,
                original_kept=original_kept,
                split_documents=split_parts,
                total_parts=len(split_parts),
                processing_time_seconds=round(processing_time, 2),
            )

            logger.info(
                f"✅ Split complete: {len(split_parts)} parts created "
                f"({processing_time:.2f}s)"
            )

            return response

        finally:
            # Cleanup temp file
            try:
                os.remove(temp_pdf_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file: {e}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Split failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Split failed: {str(e)}")


@router.post("/{document_id}/convert-with-ai", response_model=ConvertWithAIResponse)
async def convert_document_with_ai(
    document_id: str,
    request: ConvertWithAIRequest,
    user_data: dict = Depends(get_current_user),
):
    """
    Convert existing document with Gemini AI

    Supports:
    - Full PDF conversion (no page_range specified)
    - Partial PDF conversion (with page_range selection)

    Args:
        document_id: Document ID to convert
        request: Conversion configuration (includes optional page_range)

    Returns:
        ConvertWithAIResponse with processing results
    """
    logger.info(
        f"🚀 CONVERT ENDPOINT CALLED: document_id={document_id}, user={user_data.get('uid', 'unknown')}"
    )

    try:
        start_time = datetime.now()
        user_id = user_data["uid"]

        page_range_str = (
            f"{request.page_range.start_page}-{request.page_range.end_page}"
            if request.page_range
            else "all"
        )

        logger.info(
            f"🤖 Convert with AI request: doc={document_id}, "
            f"target={request.target_type}, pages={page_range_str}, "
            f"chunk_size={request.chunk_size}, force={request.force_reprocess}"
        )

        # Get file from database
        # Try user_files first (where simple file uploads are stored)
        file_doc = db_manager.db.user_files.find_one(
            {"file_id": document_id, "user_id": user_id}
        )

        if not file_doc:
            # Also try using _id field for backward compatibility
            file_doc = db_manager.db.user_files.find_one(
                {"_id": document_id, "user_id": user_id}
            )

        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found in user_files")

        logger.info(
            f"✅ Found file in 'user_files' collection: {file_doc.get('filename')}"
        )

        # Get PDF path from R2
        r2_key = file_doc.get("r2_key")
        if not r2_key:
            raise HTTPException(status_code=400, detail="File does not have R2 key")

        # Check if file is PDF
        file_type = file_doc.get("file_type", "")
        if file_type.lower() != ".pdf":
            raise HTTPException(
                status_code=400,
                detail=f"Only PDF files supported for AI conversion, got: {file_type}",
            )

        # Check if document already exists for this file (caching logic from slide parser)
        existing_doc = db_manager.db.documents.find_one(
            {"file_id": document_id, "user_id": user_id}
        )

        # Try to use cached content (fast path)
        cached_html = None
        if existing_doc and existing_doc.get("ai_processed"):
            prev_html = existing_doc.get("content_html")

            # Validate cached content has actual data (same as slide parser)
            if prev_html and prev_html.strip():
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(prev_html, "html.parser")
                text_content = soup.get_text(strip=True)

                if text_content and len(text_content) > 100:  # At least 100 chars
                    if not request.force_reprocess:
                        # Cache is valid! Return cached document
                        logger.info(
                            f"♻️ Reusing cached document (fast path - no Gemini call needed!)"
                        )
                        logger.info(
                            f"♻️ Cached HTML: {len(prev_html)} chars, Text: {len(text_content)} chars"
                        )

                        # Return existing document info
                        # Format pages_converted properly
                        if existing_doc.get("ai_page_range"):
                            page_range = existing_doc.get("ai_page_range", {})
                            start = page_range.get("start_page")
                            end = page_range.get("end_page")
                            if start and end:
                                pages_converted_str = f"{start}-{end}"
                            else:
                                pages_converted_str = "all"
                        else:
                            pages_converted_str = "all"

                        # Format updated_at properly
                        updated_at_val = existing_doc.get("updated_at", datetime.now())
                        if isinstance(updated_at_val, datetime):
                            updated_at_str = updated_at_val.isoformat()
                        else:
                            updated_at_str = str(updated_at_val)

                        return ConvertWithAIResponse(
                            success=True,
                            document_id=existing_doc["document_id"],
                            document_type=existing_doc.get(
                                "document_type", request.target_type
                            ),
                            ai_processed=True,
                            ai_provider=existing_doc.get("ai_provider", "gemini"),
                            chunks_processed=existing_doc.get("ai_chunks_count", 0),
                            total_pages=existing_doc.get("total_pages", 0),
                            pages_converted=pages_converted_str,
                            processing_time_seconds=0.0,  # Cached, no processing time
                            reprocessed=False,  # Using cached content
                            updated_at=updated_at_str,
                        )
                    else:
                        logger.info(
                            f"⚠️ Cached content exists but force_reprocess=true, will re-parse"
                        )
                else:
                    text_len = len(text_content) if text_content else 0
                    logger.warning(
                        f"⚠️ Previous document has empty text content (HTML: {len(prev_html)} chars, Text: {text_len} chars), will re-process"
                    )
            else:
                logger.warning(
                    f"⚠️ Previous document has empty or no content_html, will re-process"
                )

        # Slow path: Download from R2 and process with Gemini (first time or cache invalid)
        logger.info(f"📥 Downloading file from R2: {r2_key}")

        # Download file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_path = tmp_file.name

            # Initialize R2Client
            r2_client = _get_r2_client()

            file_obj = r2_client.get_file(r2_key)
            if not file_obj:
                raise HTTPException(
                    status_code=500, detail="Failed to download file from R2"
                )

            # Write to temp file
            file_content = file_obj["Body"].read()
            tmp_file.write(file_content)
            logger.info(f"✅ Downloaded {len(file_content)} bytes to {tmp_path}")

        temp_pdf_path = tmp_path

        # Get PDF info
        pdf_info = pdf_split_service.get_pdf_info(temp_pdf_path)
        total_pages = pdf_info["total_pages"]

        # Validate page_range if provided
        if request.page_range:
            if request.page_range.start_page < 1:
                raise HTTPException(status_code=400, detail="start_page must be >= 1")
            if request.page_range.end_page > total_pages:
                raise HTTPException(
                    status_code=400,
                    detail=f"end_page ({request.page_range.end_page}) exceeds total pages ({total_pages})",
                )

        try:
            # Extract page range if specified
            pdf_to_process = temp_pdf_path
            temp_extracted_path = None

            if request.page_range:
                logger.info(
                    f"📄 Extracting pages {request.page_range.start_page}-{request.page_range.end_page}..."
                )
                temp_extracted_path = temp_pdf_path.replace(".pdf", "_extracted.pdf")
                pdf_split_service.extract_page_range(
                    pdf_path=temp_pdf_path,
                    start_page=request.page_range.start_page,
                    end_page=request.page_range.end_page,
                    output_path=temp_extracted_path,
                )
                pdf_to_process = temp_extracted_path

            # Process with AI
            logger.info(f"🚀 Processing with Gemini AI...")

            html_content, metadata = await pdf_ai_processor.convert_existing_document(
                pdf_path=pdf_to_process,
                target_type=request.target_type,
                chunk_size=request.chunk_size,
            )

            chunks_processed = metadata["total_chunks"]
            processing_time = metadata["total_processing_time"]

            logger.info(
                f"✅ AI processing complete: {chunks_processed} chunks, "
                f"{processing_time:.2f}s"
            )

            # Generate document ID if creating new, or use existing
            if existing_doc:
                doc_id = existing_doc["document_id"]
                is_update = True
            else:
                doc_id = f"{request.target_type}_{uuid.uuid4().hex[:12]}"
                is_update = False

            # Prepare document data
            document_data = {
                "document_id": doc_id,
                "user_id": user_id,
                "file_id": document_id,  # Link to user_files
                "title": file_doc.get("filename", "Untitled"),
                "document_type": request.target_type,
                "content_html": html_content,
                "created_at": (
                    existing_doc["created_at"] if existing_doc else datetime.now()
                ),
                "updated_at": datetime.now(),
                "last_opened_at": datetime.now(),
                "last_saved_at": datetime.now(),  # Required by document_editor
                "version": existing_doc.get("version", 1) if existing_doc else 1,
                "file_size_bytes": len(html_content.encode("utf-8")),
                "source_type": "ai_conversion",  # Mark as AI-converted
                "auto_save_count": 0,  # No auto-saves yet
                "manual_save_count": 0,  # No manual saves yet
                # PDF specific
                "total_pages": total_pages,
                # AI processing metadata
                "ai_processed": True,
                "ai_provider": "gemini",
                "ai_chunks_count": chunks_processed,
                "ai_processing_time": processing_time,
                "ai_chunk_size": request.chunk_size,
                "ai_processed_at": datetime.now(),
                # Other fields
                "is_deleted": False,
                "folder_id": None,
            }

            # Store page range info if partial conversion
            if request.page_range:
                document_data["ai_page_range"] = {
                    "start_page": request.page_range.start_page,
                    "end_page": request.page_range.end_page,
                }

            # Save or update document
            if is_update:
                db_manager.db.documents.update_one(
                    {"document_id": doc_id}, {"$set": document_data}
                )
                logger.info(f"💾 Updated document: {doc_id}")
            else:
                db_manager.db.documents.insert_one(document_data)
                logger.info(f"💾 Created new document: {doc_id}")

            # Calculate total time
            total_time = (datetime.now() - start_time).total_seconds()

            response = ConvertWithAIResponse(
                success=True,
                document_id=doc_id,
                document_type=request.target_type,
                ai_processed=True,
                ai_provider="gemini",
                chunks_processed=chunks_processed,
                total_pages=total_pages,
                pages_converted=page_range_str,
                processing_time_seconds=round(total_time, 2),
                reprocessed=is_update,
                updated_at=datetime.now().isoformat(),
            )

            logger.info(
                f"✅ Convert complete: {page_range_str} pages ({total_time:.2f}s)"
            )

            return response

        finally:
            # Cleanup temp files
            try:
                os.remove(temp_pdf_path)
                if temp_extracted_path and os.path.exists(temp_extracted_path):
                    os.remove(temp_extracted_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp files: {e}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Convert failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Convert failed: {str(e)}")


@router.get("/{document_id}/split-info", response_model=SplitInfoResponse)
async def get_document_split_info(
    document_id: str, user_data: dict = Depends(get_current_user)
):
    """
    Get split information for a document

    Args:
        document_id: Document ID

    Returns:
        SplitInfoResponse with split metadata and siblings
    """
    try:
        user_id = user_data["uid"]

        logger.info(f"ℹ️ Split info request: doc={document_id}")

        # Get document from database
        document = db_manager.db.documents.find_one(
            {"document_id": document_id, "user_id": user_id}
        )

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Check if this is a split part
        is_split_part = document.get("is_split_part", False)

        if not is_split_part:
            # Not a split part
            return SplitInfoResponse(
                success=True,
                document_id=document_id,
                is_split_part=False,
                can_merge=False,
            )

        # Get split info
        split_info_data = document.get("split_info", {})
        original_doc_id = document.get("original_document_id")

        # Get all sibling documents
        siblings_docs = list(
            db_manager.db.documents.find(
                {
                    "original_document_id": original_doc_id,
                    "user_id": user_id,
                    "document_id": {"$ne": document_id},  # Exclude current document
                }
            )
        )

        # Build siblings list
        siblings = [
            SplitInfoSibling(
                document_id=sib["document_id"],
                title=sib["title"],
                pages=f"{sib['split_info']['start_page']}-{sib['split_info']['end_page']}",
            )
            for sib in siblings_docs
        ]

        # Build split info detail
        split_info = SplitInfoDetail(
            start_page=split_info_data.get("start_page", 0),
            end_page=split_info_data.get("end_page", 0),
            total_pages_in_part=document.get("total_pages", 0),
            part_number=split_info_data.get("part_number", 0),
            total_parts=split_info_data.get("total_parts", 0),
        )

        # Can merge if there are siblings
        can_merge = len(siblings) > 0

        response = SplitInfoResponse(
            success=True,
            document_id=document_id,
            is_split_part=True,
            original_document_id=original_doc_id,
            split_info=split_info,
            siblings=siblings,
            can_merge=can_merge,
        )

        logger.info(
            f"✅ Split info: part {split_info.part_number}/{split_info.total_parts}, "
            f"{len(siblings)} siblings"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get split info failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Get split info failed: {str(e)}")


@router.post("/merge", response_model=MergeDocumentsResponse)
async def merge_documents(
    request: MergeDocumentsRequest, user_data: dict = Depends(get_current_user)
):
    """
    Merge multiple documents into one

    Args:
        request: Merge configuration with document IDs

    Returns:
        MergeDocumentsResponse with merged document info
    """
    try:
        start_time = datetime.now()
        user_id = user_data["uid"]

        logger.info(
            f"🔗 Merge request: {len(request.document_ids)} documents, "
            f"title='{request.title}'"
        )

        # Get all documents
        documents = list(
            db_manager.db.documents.find(
                {"document_id": {"$in": request.document_ids}, "user_id": user_id}
            )
        )

        if len(documents) != len(request.document_ids):
            raise HTTPException(
                status_code=404, detail="One or more documents not found"
            )

        # Check all documents have PDFs
        pdf_paths = []
        merged_from_info = []

        for doc in documents:
            pdf_r2_path = doc.get("pdf_r2_path")
            if not pdf_r2_path:
                raise HTTPException(
                    status_code=400,
                    detail=f"Document {doc['document_id']} does not have PDF file",
                )
            pdf_paths.append(pdf_r2_path)

            # Build merged from info
            if doc.get("is_split_part") and doc.get("split_info"):
                pages = (
                    f"{doc['split_info']['start_page']}-{doc['split_info']['end_page']}"
                )
            else:
                pages = f"1-{doc.get('total_pages', 0)}"

            merged_from_info.append(
                MergedFromInfo(document_id=doc["document_id"], pages=pages)
            )

        # Download all PDFs to temp files
        temp_pdf_files = []
        r2_client = _get_r2_client()
        for pdf_r2_path in pdf_paths:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                pdf_content = r2_client.download_file(pdf_r2_path)
                temp_pdf.write(pdf_content)
                temp_pdf_files.append(temp_pdf.name)

        try:
            # Merge PDFs
            merged_pdf_path = os.path.join(
                tempfile.gettempdir(), f"merged_{uuid.uuid4().hex[:8]}.pdf"
            )

            logger.info(f"🔗 Merging {len(temp_pdf_files)} PDFs...")

            pdf_split_service.merge_pdfs(temp_pdf_files, merged_pdf_path)

            # Get merged PDF info
            merged_info = pdf_split_service.get_pdf_info(merged_pdf_path)
            total_pages = merged_info["total_pages"]

            # Upload merged PDF to R2
            with open(merged_pdf_path, "rb") as f:
                merged_content = f.read()

            # Generate merged document ID
            merged_doc_id = f"doc_{uuid.uuid4().hex[:12]}"
            merged_r2_path = f"documents/{user_id}/{merged_doc_id}.pdf"

            r2_client = _get_r2_client()
            r2_client.upload_file_object(
                file_obj=merged_content,
                remote_path=merged_r2_path,
                content_type="application/pdf",
            )

            logger.info(f"☁️ Uploaded merged PDF: {merged_r2_path}")

            # Create merged document in database
            merged_document = {
                "document_id": merged_doc_id,
                "user_id": user_id,
                "title": request.title,
                "description": f"Merged from {len(documents)} documents",
                "document_type": documents[0]["document_type"],
                "content_html": f"<p>Merged document ({total_pages} pages)</p>",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                # PDF info
                "total_pages": total_pages,
                "pdf_r2_path": merged_r2_path,
                "pdf_file_size": len(merged_content),
                # Merge info
                "is_merged": True,
                "merged_from": [
                    {"document_id": info.document_id, "pages": info.pages}
                    for info in merged_from_info
                ],
                "merged_at": datetime.now(),
                # Not split part
                "is_split_part": False,
                "ai_processed": False,
            }

            db_manager.db.documents.insert_one(merged_document)

            logger.info(f"💾 Created merged document: {merged_doc_id}")

            # Delete originals if not keeping
            originals_deleted = not request.keep_originals
            if not request.keep_originals:
                result = db_manager.db.documents.delete_many(
                    {"document_id": {"$in": request.document_ids}}
                )
                logger.info(f"🗑️ Deleted {result.deleted_count} original documents")

            # Cleanup temp files
            for temp_file in temp_pdf_files + [merged_pdf_path]:
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file: {e}")

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            response = MergeDocumentsResponse(
                success=True,
                merged_document_id=merged_doc_id,
                title=request.title,
                total_pages=total_pages,
                merged_from=merged_from_info,
                originals_deleted=originals_deleted,
                r2_path=merged_r2_path,
                created_at=datetime.now().isoformat(),
            )

            logger.info(
                f"✅ Merge complete: {merged_doc_id} ({total_pages} pages, "
                f"{processing_time:.2f}s)"
            )

            return response

        finally:
            pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Merge failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")
