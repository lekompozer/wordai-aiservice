"""
Admin API routes for managing company files and tags.
Implements file upload with AI processing using Queue Manager for async processing.
"""

import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Path
from pydantic import BaseModel, Field

from src.models.unified_models import Industry, Language
from src.services.admin_service import get_admin_service, AdminService
from src.services.ai_extraction_service import get_ai_service
from src.middleware.auth import verify_internal_api_key
from src.utils.logger import setup_logger
from src.queue.queue_dependencies import get_document_queue
from src.queue.task_models import DocumentProcessingTask, FileUploadTaskResponse
import os

logger = setup_logger(__name__)
router = APIRouter(tags=["Admin - Files & Tags"])


class FileUploadRequest(BaseModel):
    """
    File upload request matching exact Backend specification
    Data types: 'document', 'image', 'video', 'audio', 'other'
    """

    r2_url: str = Field(..., description="Public R2 URL of the uploaded file")
    data_type: str = Field(
        "document", description="Type of file: document, image, video, audio, other"
    )
    industry: Industry = Field(..., description="Company industry for context")
    metadata: Dict[str, Any] = Field(
        ..., description="File metadata exactly as sent from Backend"
    )
    language: Optional[Language] = Field(
        None, description="Target language for AI processing (from Frontend)"
    )
    upload_to_qdrant: bool = Field(
        True, description="Whether to process and upload to Qdrant"
    )
    callback_url: Optional[str] = Field(
        None, description="Callback URL for processing notifications"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "r2_url": "https://pub-xyz.r2.dev/companies/company-123/documents/file.pdf",
                "data_type": "document",
                "industry": "REAL_ESTATE",
                "metadata": {
                    "original_name": "company_profile.pdf",
                    "file_id": "file_123456789",
                    "file_name": "company_profile_processed.pdf",
                    "file_size": 1024000,
                    "file_type": "application/pdf",
                    "uploaded_by": "user_uid_123",
                    "description": "Company profile document",
                    "tags": ["profile", "company_info", "overview"],
                },
                "upload_to_qdrant": True,
                "callback_url": "https://backend.example.com/api/webhooks/file-processed",
            }
        }


class FileUploadResponse(BaseModel):
    """File upload response with processing status"""

    success: bool
    message: str
    file_id: str
    company_id: str
    raw_content: Optional[str] = None
    processing_status: str = "uploaded"
    ai_provider: Optional[str] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None


# ===== DEPENDENCY =====


async def get_ai_extraction_service():
    """Get AI extraction service instance for file processing"""
    return get_ai_service()


@router.post(
    "/companies/{companyId}/files/upload",
    response_model=FileUploadTaskResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def upload_file(
    request: FileUploadRequest,
    company_id: str = Path(..., alias="companyId"),
    queue_manager=Depends(get_document_queue),
) -> FileUploadTaskResponse:
    """
    Upload and process a generic company file with AI extraction (ASYNC VERSION).

    NEW ASYNC WORKFLOW / LUỒNG XỬ LÝ BẤT ĐỒNG BỘ MỚI:
    1. ✅ Receive file upload request with R2 URL
    2. ✅ Generate unique task_id
    3. ✅ Enqueue DocumentProcessingTask to Redis queue
    4. ✅ Return immediate response with task_id for status tracking
    5. 🔄 Background worker will:
       - Select appropriate AI provider based on file type
       - Extract raw text content from file
       - Generate content_for_embedding in same AI call
       - Create embeddings using unified model
       - Store raw text and metadata
       - Upload to Qdrant with tags and metadata
    """
    start_time = datetime.now()
    task_id = str(uuid.uuid4())

    try:
        logger.info(f"🚀 Queueing file upload task for company {company_id}")
        logger.info(f"   🆔 Task ID: {task_id}")
        logger.info(f"   🔗 R2 URL: {request.r2_url}")
        logger.info(f"   📁 File Type: {request.data_type}")
        logger.info(f"   🏭 Industry: {request.industry}")
        logger.info(f"   📄 File: {request.metadata.get('original_name', 'unknown')}")

        # Use language from request, fallback to metadata, default to English
        if request.language:
            language_enum = request.language
        else:
            # Check metadata for language, default to auto-detect
            language_str = request.metadata.get("language", "auto")
            if language_str.lower() in ["vi", "vietnamese", "vn"]:
                language_enum = Language.VIETNAMESE
            elif language_str.lower() in ["en", "english"]:
                language_enum = Language.ENGLISH
            else:
                language_enum = Language.AUTO_DETECT

        # Create DocumentProcessingTask for queue
        task = DocumentProcessingTask(
            task_id=task_id,
            company_id=company_id,
            r2_url=request.r2_url,
            industry=request.industry,
            language=language_enum,
            data_type=request.data_type,
            upload_to_qdrant=request.upload_to_qdrant,
            metadata=request.metadata,  # Fixed: metadata instead of file_metadata
            callback_url=request.callback_url,
            priority=1,  # Normal priority
            max_retries=3,
            created_at=datetime.now().isoformat(),
        )

        # Enqueue task to Redis
        success = await queue_manager.enqueue_generic_task(task)

        if not success:
            raise HTTPException(
                status_code=503,
                detail="Queue service unavailable. Please try again later.",
            )

        # Calculate queueing time
        processing_time = (datetime.now() - start_time).total_seconds()

        # Return immediate response
        logger.info(
            f"✅ File upload task {task_id} queued successfully in {processing_time:.2f}s"
        )

        return FileUploadTaskResponse(
            task_id=task_id,
            status="queued",
            message="File upload task queued successfully. Use task_id to check processing status.",
            company_id=company_id,
            status_check_url=f"/api/admin/tasks/document/{task_id}/status",
            file_type=request.metadata.get("file_type", "unknown"),
            data_type=request.data_type,
            estimated_processing_time="30-60 seconds",
            created_at=datetime.now().isoformat(),
        )

    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ File upload task queueing failed: {str(e)}")

        # Return error response
        return FileUploadTaskResponse(
            task_id=task_id,
            status="failed",
            message=f"Failed to queue file upload task: {str(e)}",
            company_id=company_id,
            status_check_url=f"/api/admin/tasks/document/{task_id}/status",
            file_type="unknown",
            data_type=request.data_type,
            error=str(e),
            created_at=datetime.now().isoformat(),
        )


# ===== BACKGROUND TASK (similar to products_services_routes.py) =====


async def schedule_file_qdrant_upload(
    file_data_json: str,
    metadata_json: str,
    company_id: str,
    industry: str,
    language: Optional[str] = None,
    callback_url: Optional[str] = None,
):
    """
    Schedule Qdrant upload for uploaded files with tags and metadata
    Similar to schedule_qdrant_upload but for general file uploads
    """
    try:
        # Deserialize the JSON strings back into dictionaries
        file_data = json.loads(file_data_json)
        metadata = json.loads(metadata_json)

        logger.info("📤 Processing file Qdrant upload via background worker")
        logger.info(f"📄 File: {file_data.get('file_id')}")
        logger.info(f"📁 File type: {file_data.get('data_type')}")
        logger.info(f"🏷️ Tags: {metadata.get('tags', [])}")
        logger.info(f"🏭 Industry: {industry}")
        logger.info(f"📊 Raw content length: {len(file_data.get('raw_content', ''))}")

        # Get AI service instance
        ai_service = get_ai_service()

        # Convert string enums to proper enum types with error handling
        from src.models.unified_models import Industry, Language

        try:
            industry_enum = (
                Industry(industry) if isinstance(industry, str) else industry
            )
            logger.info(f"✅ Industry enum converted: {industry_enum}")
        except ValueError as e:
            logger.warning(f"⚠️ Unknown industry '{industry}', using OTHER. Error: {e}")
            industry_enum = Industry.OTHER

        try:
            if language:
                language_enum = (
                    Language(language) if isinstance(language, str) else language
                )
            else:
                # Default to English if no language specified
                language_enum = Language.ENGLISH
            logger.info(f"✅ Language enum converted: {language_enum}")
        except ValueError as e:
            logger.warning(
                f"⚠️ Unknown language '{language}', using ENGLISH. Error: {e}"
            )
            language_enum = Language.ENGLISH

        # Prepare file data for Qdrant ingestion - Skip AI service method, do direct chunking
        # Since this is company info documents, we don't need structured JSON extraction
        # Just chunk the raw content and upload to Qdrant directly

        # Direct Qdrant upload implementation
        try:
            from src.services.qdrant_company_service import QdrantCompanyDataService
            from src.models.unified_models import CompanyConfig
            from src.providers.ai_provider_manager import AIProviderManager

            # Initialize AI manager for embeddings
            ai_manager = AIProviderManager(
                deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
                chatgpt_api_key=os.getenv("CHATGPT_API_KEY", ""),
                gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            )

            # Initialize Qdrant service
            qdrant_service = QdrantCompanyDataService(
                qdrant_url=os.getenv("QDRANT_URL"),
                qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            )

            # ✅ Use unified collection name consistently
            UNIFIED_COLLECTION_NAME = "multi_company_data"

            # Ensure collection exists
            try:
                collections = qdrant_service.client.get_collections()
                existing_names = [col.name for col in collections.collections]

                if UNIFIED_COLLECTION_NAME not in existing_names:
                    # Create master collection if it doesn't exist
                    from qdrant_client.models import Distance, VectorParams

                    qdrant_service.client.create_collection(
                        collection_name=UNIFIED_COLLECTION_NAME,
                        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                    )
                    logger.info(
                        f"✅ Created new unified collection: {UNIFIED_COLLECTION_NAME}"
                    )
                else:
                    logger.info(
                        f"✅ Unified collection exists: {UNIFIED_COLLECTION_NAME}"
                    )

                collection_name = UNIFIED_COLLECTION_NAME

            except Exception as collection_error:
                logger.error(
                    f"❌ Failed to ensure master collection: {collection_error}"
                )
                raise

            # Create document chunks for file content with optimized chunking
            file_chunks = []
            raw_content = file_data.get("raw_content", "")

            if raw_content and raw_content.strip():
                # Smart chunking based on content length
                # For company documents: 2000-5000 chars per chunk (equivalent to 5-10 pages)
                content_length = len(raw_content)

                if content_length <= 2000:
                    # Small document: single chunk
                    chunk_size = content_length
                elif content_length <= 10000:
                    # Medium document: 2-3 chunks
                    chunk_size = 3000
                else:
                    # Large document: multiple chunks of ~5000 chars (5-10 pages)
                    chunk_size = 5000

                logger.info(
                    f"📄 Content length: {content_length} chars, using chunk size: {chunk_size}"
                )

                # Create overlapping chunks for better context
                overlap = min(200, chunk_size // 10)  # 10% overlap or 200 chars max
                content_chunks = []

                for i in range(0, len(raw_content), chunk_size - overlap):
                    chunk_end = min(i + chunk_size, len(raw_content))
                    chunk_content = raw_content[i:chunk_end].strip()

                    if chunk_content:  # Only add non-empty chunks
                        content_chunks.append(chunk_content)

                    if chunk_end >= len(raw_content):
                        break

                logger.info(f"📊 Created {len(content_chunks)} chunks from document")

                for i, chunk_content in enumerate(content_chunks):
                    # Generate embedding for chunk
                    try:
                        embedding = await ai_manager.get_embedding(text=chunk_content)

                        # Create point data for Qdrant following exact Backend specification
                        point_data = {
                            "id": f"{file_data['file_id']}_chunk_{i}",
                            "payload": {
                                "file_id": file_data["file_id"],
                                "company_id": company_id,
                                "content": chunk_content,
                                "content_type": "file_document",  # Company info document
                                "data_type": file_data.get("data_type", "document"),
                                "industry": industry_enum.value,
                                "language": language_enum.value,
                                "tags": metadata.get("tags", []),
                                # File metadata exactly as specified in Backend spec
                                "original_name": metadata.get("original_name"),
                                "file_name": metadata.get(
                                    "file_name", metadata.get("original_name")
                                ),
                                "file_size": metadata.get("file_size"),
                                "file_type": metadata.get("file_type"),
                                "uploaded_by": metadata.get("uploaded_by"),
                                "description": metadata.get("description"),
                                "ai_provider": file_data.get("ai_provider"),
                                "chunk_index": i,
                                "total_chunks": len(content_chunks),
                                "chunk_size": len(chunk_content),
                                "created_at": file_data.get("created_at"),
                                "r2_url": file_data.get("r2_url"),
                            },
                            "vector": embedding,
                        }
                        file_chunks.append(point_data)

                    except Exception as embedding_error:
                        logger.warning(
                            f"⚠️ Failed to create embedding for chunk {i}: {embedding_error}"
                        )

                        # Create point without embedding (fallback)
                        point_data = {
                            "id": f"{file_data['file_id']}_chunk_{i}",
                            "payload": {
                                "file_id": file_data["file_id"],
                                "company_id": company_id,
                                "content": chunk_content,
                                "content_type": "file_document",
                                "data_type": file_data.get("data_type", "document"),
                                "industry": industry_enum.value,
                                "language": language_enum.value,
                                "tags": metadata.get("tags", []),
                                # File metadata exactly as specified in Backend spec
                                "original_name": metadata.get("original_name"),
                                "file_name": metadata.get(
                                    "file_name", metadata.get("original_name")
                                ),
                                "file_size": metadata.get("file_size"),
                                "file_type": metadata.get("file_type"),
                                "uploaded_by": metadata.get("uploaded_by"),
                                "description": metadata.get("description"),
                                "ai_provider": file_data.get("ai_provider"),
                                "chunk_index": i,
                                "total_chunks": len(content_chunks),
                                "chunk_size": len(chunk_content),
                                "created_at": file_data.get("created_at"),
                                "r2_url": file_data.get("r2_url"),
                                "embedding_failed": True,
                            },
                        }
                        file_chunks.append(point_data)

            # Upload chunks to Qdrant
            if file_chunks:
                logger.info(f"📤 Uploading {len(file_chunks)} file chunks to Qdrant")
                await qdrant_service.upsert_points(collection_name, file_chunks)
                logger.info(f"✅ Successfully uploaded {len(file_chunks)} file chunks")

                # Log chunk details
                total_content_size = sum(
                    len(chunk["payload"]["content"]) for chunk in file_chunks
                )
                avg_chunk_size = (
                    total_content_size // len(file_chunks) if file_chunks else 0
                )
                logger.info(f"   📊 Total content: {total_content_size} chars")
                logger.info(f"   📄 Average chunk size: {avg_chunk_size} chars")
                logger.info(f"   🏷️ Tags: {metadata.get('tags', [])}")
            else:
                logger.warning("⚠️ No valid chunks to upload")

        except Exception as qdrant_error:
            logger.error(f"❌ Failed to upload file to Qdrant: {str(qdrant_error)}")
            # Don't raise here, just log the error

        logger.info("✅ File Qdrant upload completed successfully")
        logger.info(f"   🏢 Company: {company_id}")
        logger.info(f"   📄 File: {file_data.get('file_id')}")
        logger.info(f"   🏭 Industry: {industry_enum.value}")
        logger.info(
            f"   📊 Total chunks: {len(file_chunks) if 'file_chunks' in locals() else 0}"
        )
        logger.info(f"   🏷️ Tags: {metadata.get('tags', [])}")

        # Send callback notification if provided
        if callback_url:
            try:
                callback_data = {
                    "event": "file.uploaded",
                    "companyId": company_id,
                    "data": {
                        "fileId": file_data.get("file_id"),
                        "status": "completed",
                        "chunksCreated": (
                            len(file_chunks) if "file_chunks" in locals() else 0
                        ),
                        "processingTime": file_data.get("processing_time", 0),
                        "processedAt": datetime.now().isoformat(),
                        "tags": metadata.get("tags", []),
                        # ✅ ADD RAW CONTENT for backend database storage
                        "raw_content": file_data.get("raw_content", ""),
                        "file_metadata": {
                            "original_name": metadata.get("original_name"),
                            "file_name": metadata.get(
                                "file_name", metadata.get("original_name")
                            ),
                            "file_size": metadata.get("file_size"),
                            "file_type": metadata.get("file_type"),
                            "uploaded_by": metadata.get("uploaded_by"),
                            "description": metadata.get("description"),
                            "r2_url": file_data.get("r2_url"),
                        },
                    },
                    "timestamp": datetime.now().isoformat(),
                }
                logger.info(f"📞 File upload callback prepared for: {callback_url}")

                # Implement webhook callback to Backend
                try:
                    import aiohttp
                    import json

                    # Simple webhook authentication using WEBHOOK_SECRET in header
                    webhook_secret = os.getenv(
                        "WEBHOOK_SECRET", "webhook-secret-for-signature"
                    )

                    headers = {
                        "Content-Type": "application/json",
                        "X-Webhook-Source": "ai-service",
                        "X-Webhook-Secret": webhook_secret,
                        "User-Agent": "Agent8x-AI-Service/1.0",
                    }

                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            callback_url,
                            json=callback_data,
                            timeout=aiohttp.ClientTimeout(total=30),
                            headers=headers,
                        ) as response:
                            response_text = await response.text()

                            if response.status == 200:
                                logger.info(
                                    f"✅ File upload callback sent successfully"
                                )
                                logger.info(f"📞 Response: {response_text}")
                            else:
                                logger.warning(
                                    f"⚠️ File upload callback returned status {response.status}"
                                )
                                logger.warning(f"📞 Response: {response_text}")

                except Exception as http_error:
                    logger.error(
                        f"❌ HTTP request failed for file upload callback: {http_error}"
                    )

            except Exception as callback_error:
                logger.error(f"📞 File upload callback failed: {callback_error}")

    except Exception as e:
        logger.error(f"❌ Failed to schedule file Qdrant upload: {str(e)}")

        # Send error callback if provided
        if callback_url:
            try:
                error_callback = {
                    "event": "file.uploaded",
                    "companyId": company_id,
                    "data": {
                        "fileId": file_data.get("file_id", "unknown"),
                        "status": "failed",
                        "error": str(e),
                        "failedAt": datetime.now().isoformat(),
                        # ✅ ADD RAW CONTENT even for failed uploads (partial content may still be useful)
                        "raw_content": file_data.get("raw_content", ""),
                        "file_metadata": {
                            "original_name": metadata.get("original_name"),
                            "file_name": metadata.get(
                                "file_name", metadata.get("original_name")
                            ),
                            "file_size": metadata.get("file_size"),
                            "file_type": metadata.get("file_type"),
                            "uploaded_by": metadata.get("uploaded_by"),
                            "description": metadata.get("description"),
                            "r2_url": file_data.get("r2_url"),
                        },
                    },
                    "timestamp": datetime.now().isoformat(),
                }
                logger.error(
                    f"📞 File upload error callback prepared for: {callback_url}"
                )

                # Implement webhook callback to Backend
                try:
                    import aiohttp
                    import json

                    # Simple webhook authentication using WEBHOOK_SECRET in header
                    webhook_secret = os.getenv(
                        "WEBHOOK_SECRET", "webhook-secret-for-signature"
                    )

                    headers = {
                        "Content-Type": "application/json",
                        "X-Webhook-Source": "ai-service",
                        "X-Webhook-Secret": webhook_secret,
                        "User-Agent": "Agent8x-AI-Service/1.0",
                    }

                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            callback_url,
                            json=error_callback,
                            timeout=aiohttp.ClientTimeout(total=30),
                            headers=headers,
                        ) as response:
                            response_text = await response.text()

                            if response.status == 200:
                                logger.info(
                                    f"✅ File upload error callback sent successfully"
                                )
                                logger.info(f"📞 Response: {response_text}")
                            else:
                                logger.warning(
                                    f"⚠️ File upload error callback returned status {response.status}"
                                )
                                logger.warning(f"📞 Response: {response_text}")

                except Exception as http_error:
                    logger.error(
                        f"❌ HTTP request failed for file upload error callback: {http_error}"
                    )

            except Exception as callback_error:
                logger.error(
                    f"📞 File upload error callback preparation failed: {callback_error}"
                )
                # await send_webhook_notification(callback_url, error_callback)
            except:
                pass


# ===== FILE DELETION ENDPOINTS =====


@router.delete(
    "/companies/{company_id}/files/{file_id}",
    dependencies=[Depends(verify_internal_api_key)],
)
async def delete_file(
    company_id: str = Path(..., description="Company ID"),
    file_id: str = Path(..., description="File ID to delete"),
    admin_service: AdminService = Depends(get_admin_service),
):
    """Deletes a specific file and its associated data from Qdrant."""
    logger.info(f"🗑️ Request to delete file {file_id} for company {company_id}")

    try:
        # Get AI service for Qdrant operations
        ai_service = get_ai_service()

        # Use unified collection name from qdrant_company_service
        UNIFIED_COLLECTION_NAME = "multi_company_data"

        # Delete points with file_id filter
        deleted_count = await ai_service.delete_file_from_qdrant(
            collection_name=UNIFIED_COLLECTION_NAME, file_id=file_id
        )

        if deleted_count > 0:
            logger.info(
                f"✅ Deleted {deleted_count} points for file {file_id} from Qdrant collection {UNIFIED_COLLECTION_NAME}"
            )
            return {
                "success": True,
                "message": f"File {file_id} deleted successfully",
                "deleted_points": deleted_count,
                "collection": UNIFIED_COLLECTION_NAME,
            }
        else:
            # File not found in Qdrant
            logger.warning(
                f"📭 File {file_id} not found in collection {UNIFIED_COLLECTION_NAME}"
            )
            return {
                "success": False,
                "message": f"File {file_id} not found in company {company_id}",
                "deleted_points": 0,
                "collection": UNIFIED_COLLECTION_NAME,
                "company_id": company_id,
                "file_id": file_id,
                "error": "FILE_NOT_FOUND",
                "details": "No data found for this file in the vector database. File may have been already deleted or never uploaded.",
            }

    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete file {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.delete(
    "/companies/{company_id}/files/tags/{tag_name}",
    dependencies=[Depends(verify_internal_api_key)],
)
async def delete_files_by_tag(
    company_id: str = Path(..., description="Company ID"),
    tag_name: str = Path(..., description="Tag name to delete all associated files"),
    admin_service: AdminService = Depends(get_admin_service),
):
    """Deletes all files associated with a specific tag."""
    logger.info(
        f"🗑️ Request to delete files with tag '{tag_name}' for company {company_id}"
    )

    try:
        # Get AI service for Qdrant operations
        ai_service = get_ai_service()

        # Use unified collection name from qdrant_company_service
        UNIFIED_COLLECTION_NAME = "multi_company_data"

        # TODO: Implement delete by tag logic in AI service
        # This would require a different filter condition

        logger.warning(f"⚠️ Delete by tag not yet implemented for tag '{tag_name}'")

        return {
            "success": False,
            "message": f"Delete by tag '{tag_name}' not yet implemented",
            "collection": UNIFIED_COLLECTION_NAME,
        }

    except Exception as e:
        logger.error(f"❌ Failed to delete files by tag '{tag_name}': {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete files by tag: {str(e)}"
        )


# ===== FILE STATUS CHECK ENDPOINT =====


@router.get(
    "/companies/{company_id}/files/{file_id}/status",
    dependencies=[Depends(verify_internal_api_key)],
)
async def check_file_status(
    company_id: str = Path(..., description="Company ID"),
    file_id: str = Path(..., description="File ID to check"),
    admin_service: AdminService = Depends(get_admin_service),
):
    """
    Check if a file exists in Qdrant and get its details
    Kiểm tra file có tồn tại trong Qdrant và lấy thông tin chi tiết
    """
    logger.info(f"🔍 Checking status of file {file_id} for company {company_id}")

    try:
        # Get AI service for Qdrant operations
        ai_service = get_ai_service()

        # Use unified collection name consistently
        UNIFIED_COLLECTION_NAME = "multi_company_data"

        # Initialize Qdrant client for checking
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        import config.config as config

        qdrant_client = (
            QdrantClient(
                url=config.QDRANT_URL,
                api_key=config.QDRANT_API_KEY,
            )
            if config.QDRANT_URL
            else None
        )

        if not qdrant_client:
            raise HTTPException(status_code=503, detail="Qdrant service not available")

        # Check if collection exists
        collections = qdrant_client.get_collections().collections
        collection_exists = any(c.name == UNIFIED_COLLECTION_NAME for c in collections)

        if not collection_exists:
            return {
                "success": False,
                "message": f"Collection {UNIFIED_COLLECTION_NAME} does not exist",
                "file_found": False,
                "collection": UNIFIED_COLLECTION_NAME,
                "company_id": company_id,
                "file_id": file_id,
            }

        # Search for file with file_id filter
        file_filter = Filter(
            must=[
                FieldCondition(
                    key="file_id",
                    match=MatchValue(value=file_id),
                )
            ]
        )

        file_result = qdrant_client.scroll(
            collection_name=UNIFIED_COLLECTION_NAME,
            scroll_filter=file_filter,
            limit=100,  # Get up to 100 points for this file
            with_payload=True,
        )

        file_points = file_result[0] if file_result else []

        # Also search with company_id + file_id filter
        company_file_filter = Filter(
            must=[
                FieldCondition(
                    key="company_id",
                    match=MatchValue(value=company_id),
                ),
                FieldCondition(
                    key="file_id",
                    match=MatchValue(value=file_id),
                ),
            ]
        )

        company_file_result = qdrant_client.scroll(
            collection_name=UNIFIED_COLLECTION_NAME,
            scroll_filter=company_file_filter,
            limit=100,
            with_payload=True,
        )

        company_file_points = company_file_result[0] if company_file_result else []

        # Get file details from points
        file_details = {}
        all_points = list(file_points) + list(company_file_points)

        if all_points:
            # Get details from first point
            first_point = all_points[0]
            payload = first_point.payload or {}

            file_details = {
                "file_id": payload.get("file_id"),
                "company_id": payload.get("company_id"),
                "content_type": payload.get("content_type"),
                "data_type": payload.get("data_type"),
                "industry": payload.get("industry"),
                "language": payload.get("language"),
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
                "metadata": payload.get("metadata", {}),
                "tags": payload.get("tags", []),
            }

        logger.info(f"📊 File status check results:")
        logger.info(f"   🔍 File ID search: {len(file_points)} points")
        logger.info(f"   🏢 Company+File search: {len(company_file_points)} points")
        logger.info(f"   📄 Total unique points: {len(set(p.id for p in all_points))}")

        return {
            "success": True,
            "message": f"File status check completed",
            "file_found": len(all_points) > 0,
            "collection": UNIFIED_COLLECTION_NAME,
            "company_id": company_id,
            "file_id": file_id,
            "points_found": {
                "by_file_id": len(file_points),
                "by_company_and_file_id": len(company_file_points),
                "total_unique": len(set(p.id for p in all_points)),
            },
            "file_details": file_details if all_points else None,
            "sample_point_ids": [p.id for p in all_points[:5]],  # First 5 point IDs
        }

    except Exception as e:
        logger.error(f"❌ Failed to check file status {file_id}: {str(e)}")
        import traceback

        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"Failed to check file status: {str(e)}"
        )
