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
from config.config import get_r2_client, R2_BUCKET_NAME

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["PDF Documents"])

# Initialize services
pdf_split_service = get_pdf_split_service()
pdf_ai_processor = get_pdf_ai_processor()
db_manager = DBManager()
document_manager = DocumentManager(db=db_manager.db)
r2_client = get_r2_client()


@router.post("/upload-pdf-ai", response_model=UploadPDFResponse)
async def upload_pdf_with_ai(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    document_type: str = Form(...),
    use_ai: bool = Form(True),
    chunk_size: int = Form(10),
    description: Optional[str] = Form(None),
    user_data: dict = Depends(get_current_user),
):
    """
    Upload PDF and convert with Gemini AI

    Args:
        file: PDF file to upload
        title: Document title (optional, uses filename if not provided)
        document_type: "doc" or "slide"
        use_ai: Whether to use Gemini AI for conversion (default: True)
        chunk_size: Pages per AI processing chunk (1-10, default: 10)
        description: Document description (optional)

    Returns:
        UploadPDFResponse with document info and processing metadata
    """
    try:
        start_time = datetime.now()
        user_id = user_data["uid"]

        logger.info(
            f"📄 Upload PDF request: user={user_id}, type={document_type}, "
            f"use_ai={use_ai}, chunk_size={chunk_size}"
        )

        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Validate file size (100MB limit)
        file_content = await file.read()
        file_size_mb = len(file_content) / (1024 * 1024)

        if file_size_mb > 100:
            raise HTTPException(
                status_code=400,
                detail=f"PDF must be less than 100MB (uploaded: {file_size_mb:.1f}MB)",
            )

        # Validate document type
        if document_type not in ["doc", "slide"]:
            raise HTTPException(
                status_code=400, detail="document_type must be 'doc' or 'slide'"
            )

        # Validate chunk size
        if not (1 <= chunk_size <= 10):
            raise HTTPException(
                status_code=400, detail="chunk_size must be between 1 and 10"
            )

        # Generate document ID
        document_id = f"{document_type}_{uuid.uuid4().hex[:12]}"

        # Use filename as title if not provided
        if not title:
            title = os.path.splitext(file.filename)[0]

        # Save PDF to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(file_content)
            temp_pdf_path = temp_pdf.name

        try:
            # Get PDF info
            pdf_info = pdf_split_service.get_pdf_info(temp_pdf_path)
            total_pages = pdf_info["total_pages"]

            logger.info(f"📊 PDF info: {total_pages} pages, {file_size_mb:.1f}MB")

            # Check page count
            if total_pages == 0:
                raise HTTPException(status_code=400, detail="PDF has no pages")

            # Process with AI if requested
            html_content = None
            chunks_processed = 0
            processing_time = 0.0

            if use_ai:
                logger.info(f"🤖 Processing with Gemini AI (chunks: {chunk_size})")

                # Process PDF with AI
                html_content, metadata = (
                    await pdf_ai_processor.convert_existing_document(
                        pdf_path=temp_pdf_path,
                        target_type=document_type,
                        chunk_size=chunk_size,
                    )
                )

                chunks_processed = metadata["total_chunks"]
                processing_time = metadata["total_processing_time"]

                logger.info(
                    f"✅ AI processing complete: {chunks_processed} chunks, "
                    f"{processing_time:.2f}s"
                )
            else:
                # No AI processing, just create placeholder
                html_content = f"<p>PDF uploaded: {title} ({total_pages} pages)</p>"
                logger.info("⏭️ Skipping AI processing (use_ai=False)")

            # Upload PDF to R2
            r2_path = f"documents/{user_id}/{document_id}.pdf"
            r2_client.upload_file_object(
                file_obj=file_content,
                remote_path=r2_path,
                content_type="application/pdf",
            )

            logger.info(f"☁️ Uploaded to R2: {r2_path}")

            # Save to database
            document_data = {
                "document_id": document_id,
                "user_id": user_id,
                "title": title,
                "description": description or "",
                "document_type": document_type,
                "content_html": html_content,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                # PDF specific fields
                "total_pages": total_pages,
                "pdf_r2_path": r2_path,
                "pdf_file_size": len(file_content),
                "pdf_version": pdf_info.get("version", "unknown"),
                # AI processing metadata
                "ai_processed": use_ai,
                "ai_provider": "gemini" if use_ai else None,
                "ai_chunks_count": chunks_processed if use_ai else 0,
                "ai_processing_time": processing_time if use_ai else 0,
                "ai_chunk_size": chunk_size if use_ai else None,
                "ai_processed_at": datetime.now() if use_ai else None,
                # Split info (not split yet)
                "is_split_part": False,
                "original_document_id": None,
                "split_info": None,
                "parent_document_id": None,
                "child_document_ids": [],
            }

            db_manager.db.documents.insert_one(document_data)

            logger.info(f"💾 Saved to database: {document_id}")

            # Calculate total processing time
            total_time = (datetime.now() - start_time).total_seconds()

            # Prepare response
            content_preview = None
            if html_content:
                # Extract first 500 characters
                content_preview = html_content[:500]
                if len(html_content) > 500:
                    content_preview += "..."

            response = UploadPDFResponse(
                success=True,
                document_id=document_id,
                document_type=document_type,
                title=title,
                total_pages=total_pages,
                chunks_processed=chunks_processed,
                ai_used=use_ai,
                ai_provider="gemini" if use_ai else "none",
                processing_time_seconds=round(total_time, 2),
                created_at=datetime.now().isoformat(),
                content_preview=content_preview,
            )

            logger.info(f"✅ Upload complete: {document_id} ({total_time:.2f}s total)")

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
        logger.error(f"❌ Upload failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


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

        # Get document from database
        # Try user_upload_files first (this is where uploads are stored)
        document = db_manager.db.user_upload_files.find_one(
            {"_id": document_id, "user_id": user_id}
        )

        is_from_template = False
        if document:
            logger.info(f"✅ Found in 'user_upload_files' collection")
            is_from_template = True
            # Normalize old structure to new format
            document["document_id"] = document["_id"]

            # Extract PDF path from old structure: files.pdf_url
            if "files" in document and "pdf_url" in document["files"]:
                pdf_url = document["files"]["pdf_url"]
                # Extract R2 path from URL (remove bucket domain)
                # Example: https://r2.domain.com/path/file.pdf -> path/file.pdf
                if "://" in pdf_url:
                    document["pdf_r2_path"] = pdf_url.split("/", 3)[-1]
                else:
                    document["pdf_r2_path"] = pdf_url

            # Extract total_pages from ai_analysis if available
            if "ai_analysis" in document:
                doc_struct = document["ai_analysis"].get("document_structure", {})
                document["total_pages"] = doc_struct.get("total_pages", 0)
        else:
            # Fallback: try new documents collection
            document = db_manager.db.documents.find_one(
                {"document_id": document_id, "user_id": user_id}
            )
            if document:
                logger.info(f"✅ Found in 'documents' collection")

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Check if already AI processed
        if document.get("ai_processed") and not request.force_reprocess:
            raise HTTPException(
                status_code=400,
                detail="Document already AI-processed. Use force_reprocess=true to reprocess.",
            )

        # Check if document has PDF
        pdf_r2_path = document.get("pdf_r2_path")
        if not pdf_r2_path:
            raise HTTPException(
                status_code=400, detail="Document does not have PDF file"
            )

        # Validate page_range if provided
        total_pages = document.get("total_pages", 0)
        if request.page_range:
            if request.page_range.start_page < 1:
                raise HTTPException(status_code=400, detail="start_page must be >= 1")
            if request.page_range.end_page > total_pages:
                raise HTTPException(
                    status_code=400,
                    detail=f"end_page ({request.page_range.end_page}) exceeds total pages ({total_pages})",
                )

        # Download PDF from R2
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            pdf_content = r2_client.download_file(pdf_r2_path)
            temp_pdf.write(pdf_content)
            temp_pdf_path = temp_pdf.name

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

            # Update document in database
            update_data = {
                "content_html": html_content,
                "document_type": request.target_type,
                "ai_processed": True,
                "ai_provider": "gemini",
                "ai_chunks_count": chunks_processed,
                "ai_processing_time": processing_time,
                "ai_chunk_size": request.chunk_size,
                "ai_processed_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            # Store page range info if partial conversion
            if request.page_range:
                update_data["ai_page_range"] = {
                    "start_page": request.page_range.start_page,
                    "end_page": request.page_range.end_page,
                }

            # Update in correct collection
            if is_from_template:
                # Update user_upload_files collection
                db_manager.db.user_upload_files.update_one(
                    {"_id": document_id, "user_id": user_id}, {"$set": update_data}
                )
                logger.info(f"💾 Updated in user_upload_files: {document_id}")
            else:
                # Update documents collection
                db_manager.db.documents.update_one(
                    {"document_id": document_id}, {"$set": update_data}
                )
                logger.info(f"💾 Updated in documents: {document_id}")

            # Calculate total time
            total_time = (datetime.now() - start_time).total_seconds()

            response = ConvertWithAIResponse(
                success=True,
                document_id=document_id,
                document_type=request.target_type,
                ai_processed=True,
                ai_provider="gemini",
                chunks_processed=chunks_processed,
                total_pages=document.get("total_pages", 0),
                pages_converted=page_range_str,
                processing_time_seconds=round(total_time, 2),
                reprocessed=document.get("ai_processed", False),
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
