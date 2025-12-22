"""
AI Service Document Processing API Routes
Phase 1 Implementation - Complete Document Processing Pipeline

This module provides the main API endpoints for document processing:
- POST /api/documents/process - Process document from R2 storage
- GET /api/documents/user/{user_id}/search - Search user documents
- DELETE /api/documents/{user_id}/{document_id} - Delete document
- GET /api/health - Health check

Uses existing components:
- src/workers/document_processor.py - Core processing logic
- src/vector_store/qdrant_client.py - Vector storage
- src/models/document_models.py - Pydantic models
"""

import os
import time
import uuid
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

# Direct imports to avoid circular dependencies
from src.workers.document_processor import AIDocumentProcessor
from src.vector_store.qdrant_client import QdrantManager, create_qdrant_manager
from src.queue.queue_manager import QueueManager, IngestionTask
from src.models.document_models import (
    DocumentProcessRequest,
    DocumentProcessResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentSearchResult,
    DocumentDeleteRequest,
    DocumentDeleteResponse,
    HealthCheckResponse,
    ErrorResponse,
    ProcessingResult,
    CallbackPayload,
    validate_file_type,
)
from src.utils.logger import setup_logger

# ==============================================================================
# SETUP & CONFIGURATION
# ==============================================================================

router = APIRouter()
logger = setup_logger()

# Global instances (initialized once for efficiency)
doc_processor: Optional[AIDocumentProcessor] = None
qdrant_manager: Optional[QdrantManager] = None
queue_manager: Optional[QueueManager] = None


def get_document_processor() -> AIDocumentProcessor:
    """Dependency to get document processor instance"""
    global doc_processor
    if doc_processor is None:
        try:
            doc_processor = AIDocumentProcessor()
            logger.info("✅ AIDocumentProcessor initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AIDocumentProcessor: {e}")
            raise HTTPException(
                status_code=503, detail="Document processing service unavailable"
            )
    return doc_processor


def get_qdrant_manager() -> QdrantManager:
    """Dependency to get Qdrant manager instance"""
    global qdrant_manager
    if qdrant_manager is None:
        try:
            qdrant_manager = create_qdrant_manager()
            logger.info("✅ QdrantManager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize QdrantManager: {e}")
            raise HTTPException(
                status_code=503, detail="Vector database service unavailable"
            )
    return qdrant_manager


def get_queue_manager() -> QueueManager:
    """Dependency to get Queue manager instance"""
    global queue_manager
    if queue_manager is None:
        try:
            redis_url = os.getenv("REDIS_URL", "redis://redis-server:6379")
            queue_manager = QueueManager(redis_url=redis_url)
            logger.info("✅ QueueManager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize QueueManager: {e}")
            raise HTTPException(status_code=503, detail="Queue service unavailable")
    return queue_manager


# ==============================================================================
# BACKGROUND PROCESSING TASK
# ==============================================================================


async def process_document_background(
    request: DocumentProcessRequest, processor: AIDocumentProcessor
):
    """
    Complete document processing pipeline running in background:
    1. Download from R2
    2. Extract text (PDF, DOCX, TXT, etc.)
    3. Chunk document
    4. Generate embeddings
    5. Store in Qdrant
    6. Send callback to backend
    """
    task_id = f"task_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    start_time = time.time()

    logger.info(f"🚀 [BG-TASK] {task_id}: Starting document processing")
    logger.info(f"   📄 Document: {request.document_id}")
    logger.info(f"   👤 User: {request.user_id}")
    logger.info(f"   📁 File: {request.file_name}")
    logger.info(f"   🗂️ R2 Key: {request.r2_key}")

    try:
        # Step 1: Download file from R2
        logger.info(f"📥 [BG-TASK] {task_id}: Downloading from R2...")
        bucket_name = os.getenv("R2_BUCKET_NAME", "studynotes")  # ✅ Fix default
        file_content = await processor.download_from_r2(bucket_name, request.r2_key)
        logger.info(f"✅ [BG-TASK] {task_id}: Downloaded {len(file_content)} bytes")

        # Step 2: Extract text content
        logger.info(f"🔍 [BG-TASK] {task_id}: Extracting text content...")
        text_content = await processor.extract_text_content(
            file_content, request.content_type, request.file_name
        )

        if not text_content or len(text_content.strip()) < 50:
            raise Exception("Document appears to be empty or too short")

        logger.info(f"✅ [BG-TASK] {task_id}: Extracted {len(text_content)} characters")

        # Step 3: Chunk document
        logger.info(f"🔪 [BG-TASK] {task_id}: Chunking document...")
        chunks = processor.chunk_document(text_content)
        logger.info(f"✅ [BG-TASK] {task_id}: Created {len(chunks)} chunks")

        # Step 4: Generate embeddings
        logger.info(f"🧠 [BG-TASK] {task_id}: Generating embeddings...")
        embeddings = await processor.generate_embeddings(chunks)
        logger.info(f"✅ [BG-TASK] {task_id}: Generated {len(embeddings)} embeddings")

        # Step 5: Store in Qdrant - Use QdrantManager for consistent collection naming
        qdrant_manager = get_qdrant_manager()
        collection_name = qdrant_manager.get_collection_name(request.user_id)
        logger.info(
            f"💾 [BG-TASK] {task_id}: Storing in Qdrant collection: {collection_name}"
        )

        await processor.store_in_qdrant(
            collection_name=collection_name,
            chunks=chunks,
            embeddings=embeddings,
            task_data={
                "userId": request.user_id,
                "uploadId": request.document_id,  # Using document_id as uploadId
                "taskId": task_id,
                "fileName": request.file_name,
                "contentType": request.content_type,
                "metadata": request.processing_options,
            },
        )

        processing_time = time.time() - start_time

        # Step 6: Send SUCCESS callback to backend
        logger.info(f"📞 [BG-TASK] {task_id}: Sending success callback...")
        callback_success = await processor.send_callback(
            task_data={
                "callbackUrl": request.callback_url,
                "taskId": task_id,
                "uploadId": request.document_id,
                "userId": request.user_id,
            },
            status="completed",
            result={
                "message": "Document processing completed successfully",
                "chunksProcessed": len(chunks),
                "collectionName": collection_name,
                "documentLength": len(text_content),
                "processingTime": processing_time,
            },
            processing_time=processing_time,
            chunks_processed=len(chunks),
            collection_name=collection_name,
        )

        logger.info(f"✅ [BG-TASK] {task_id}: Processing completed successfully")
        logger.info(f"   📊 Chunks: {len(chunks)}")
        logger.info(f"   💾 Collection: {collection_name}")
        logger.info(f"   ⏱️ Time: {processing_time:.2f}s")
        logger.info(f"   📞 Callback: {'✅' if callback_success else '❌'}")

    except Exception as e:
        error_msg = str(e)
        processing_time = time.time() - start_time

        logger.error(f"❌ [BG-TASK] {task_id}: Processing failed: {error_msg}")
        logger.error(f"🔍 [BG-TASK] {task_id}: Traceback: {traceback.format_exc()}")

        # Send FAILED callback to backend
        await processor.send_callback(
            task_data={
                "callbackUrl": request.callback_url,
                "taskId": task_id,
                "uploadId": request.document_id,
                "userId": request.user_id,
            },
            status="failed",
            error=error_msg,
            processing_time=processing_time,
        )


# ==============================================================================
# API ENDPOINTS - PHASE 1
# ==============================================================================


@router.post("/api/documents/process", response_model=DocumentProcessResponse)
async def process_document(
    request: DocumentProcessRequest, queue: QueueManager = Depends(get_queue_manager)
):
    """
    ✅ PHASE 2: Main endpoint for document processing with Queue Manager

    This endpoint receives a request from the Node.js backend to process a document:
    1. Validates the request
    2. Creates an ingestion task
    3. Enqueues task to Redis queue
    4. Returns immediately with task ID
    5. Worker processes the task asynchronously
    6. Sends callback to backend when complete
    """
    task_id = f"task_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

    logger.info(f"📨 [API] Received document processing request")
    logger.info(f"   📄 Document ID: {request.document_id}")
    logger.info(f"   👤 User ID: {request.user_id}")
    logger.info(f"   📁 File: {request.file_name}")
    logger.info(f"   📋 Content Type: {request.content_type}")
    logger.info(f"   📞 Callback URL: {request.callback_url}")
    logger.info(f"   🆔 Task ID: {task_id}")

    # Validate supported file types
    if not validate_file_type(request.content_type):
        logger.error(f"❌ [API] Unsupported content type: {request.content_type}")
        raise HTTPException(
            status_code=415, detail=f"Unsupported content type: {request.content_type}"
        )

    try:
        # Create ingestion task
        ingestion_task = IngestionTask(
            task_id=task_id,
            user_id=request.user_id,
            document_id=request.document_id,
            file_path=request.r2_key,  # R2 key serves as file path
            filename=request.file_name,
            file_type=request.content_type,
            file_size=request.file_size or 0,  # Default to 0 if not provided
            upload_timestamp=datetime.utcnow().isoformat(),
            callback_url=request.callback_url,
            additional_metadata={
                "processing_options": request.processing_options,
                "r2_key": request.r2_key,
                "content_type": request.content_type,
            },
        )

        # Enqueue task
        success = await queue.enqueue_task(ingestion_task)

        if not success:
            logger.error(f"❌ [API] Failed to enqueue task {task_id}")
            raise HTTPException(
                status_code=503, detail="Failed to queue document processing task"
            )

        logger.info(f"✅ [API] Task {task_id} queued successfully")

        return DocumentProcessResponse(
            success=True,
            task_id=task_id,
            document_id=request.document_id,
            user_id=request.user_id,
            status="queued",
            message="Document processing task has been queued successfully",
            estimated_time=60,  # Estimate 1 minute processing time
        )

    except Exception as e:
        logger.error(f"❌ [API] Error processing request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get(
    "/api/documents/user/{user_id}/search", response_model=DocumentSearchResponse
)
async def search_user_documents(
    user_id: str,
    query: str,
    limit: int = 5,
    score_threshold: float = 0.3,
    qdrant: QdrantManager = Depends(get_qdrant_manager),
):
    """
    ✅ PHASE 1: Search documents for a specific user

    This endpoint performs RAG search across all documents in user's collection.
    Used for chatbot functionality and document retrieval.
    """
    start_time = time.time()

    logger.info(f"🔍 [SEARCH] User: {user_id}, Query: '{query[:50]}...'")

    try:
        # Validate parameters
        if limit < 1 or limit > 20:
            raise HTTPException(
                status_code=400, detail="Limit must be between 1 and 20"
            )

        if score_threshold < 0.0 or score_threshold > 1.0:
            raise HTTPException(
                status_code=400, detail="Score threshold must be between 0.0 and 1.0"
            )

        # Perform search using QdrantManager
        search_results = await qdrant.search_user_documents(
            user_id=user_id, query=query, limit=limit, score_threshold=score_threshold
        )

        # Convert to response format
        results = []
        for result in search_results:
            results.append(
                DocumentSearchResult(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    content=result.content,
                    score=result.score,
                    chunk_index=result.metadata.get("chunk_index", 0),
                    metadata=result.metadata,
                )
            )

        processing_time = time.time() - start_time

        logger.info(
            f"✅ [SEARCH] Found {len(results)} results in {processing_time:.3f}s"
        )

        return DocumentSearchResponse(
            success=True,
            user_id=user_id,
            query=query,
            results=results,
            total_found=len(results),
            processing_time=processing_time,
        )

    except Exception as e:
        logger.error(f"❌ [SEARCH] Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.delete(
    "/api/documents/{user_id}/{document_id}", response_model=DocumentDeleteResponse
)
async def delete_user_document(
    user_id: str, document_id: str, qdrant: QdrantManager = Depends(get_qdrant_manager)
):
    """
    ✅ PHASE 1: Delete a specific document from user's collection

    This endpoint removes all chunks of a document from Qdrant.
    Used for document management and cleanup.
    """
    logger.info(f"🗑️ [DELETE] User: {user_id}, Document: {document_id}")

    try:
        # Add debug logging
        collection_name = qdrant.get_collection_name(user_id)
        logger.info(f"🔍 [DELETE] Collection name: {collection_name}")

        # Delete document from Qdrant
        success = await qdrant.delete_user_document(user_id, document_id)

        logger.info(f"🔍 [DELETE] Delete operation result: {success}")

        if success:
            logger.info(f"✅ [DELETE] Document deleted successfully")
            return DocumentDeleteResponse(
                success=True,
                user_id=user_id,
                document_id=document_id,
                message="Document deleted successfully",
                chunks_deleted=None,  # Could be enhanced to return actual count
            )
        else:
            logger.warning(f"⚠️ [DELETE] Document not found or already deleted")
            return DocumentDeleteResponse(
                success=False,
                user_id=user_id,
                document_id=document_id,
                message="Document not found or already deleted",
            )

    except Exception as e:
        logger.error(f"❌ [DELETE] Deletion failed: {e}")
        logger.error(f"🔍 [DELETE] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.get("/api/health", response_model=HealthCheckResponse)
async def health_check():
    """
    ✅ PHASE 1: Health check endpoint

    This endpoint checks the health of all services:
    - Document processor availability
    - Qdrant connection
    - R2 connection
    - Embedding model status
    """
    logger.debug("🏥 [HEALTH] Running health check...")

    services = {}
    overall_status = "healthy"

    try:
        # Check document processor
        try:
            processor = get_document_processor()
            services["document_processor"] = True
        except:
            services["document_processor"] = False
            overall_status = "degraded"

        # Check Qdrant
        try:
            qdrant = get_qdrant_manager()
            qdrant_healthy = qdrant.health_check()
            services["qdrant"] = qdrant_healthy
            if not qdrant_healthy:
                overall_status = "degraded"
        except:
            services["qdrant"] = False
            overall_status = "degraded"

        # Check R2 (basic connection test)
        try:
            if doc_processor and doc_processor.r2_client:
                # Try to list buckets as a simple connection test
                doc_processor.r2_client.list_buckets()
                services["r2_storage"] = True
            else:
                services["r2_storage"] = False
                overall_status = "degraded"
        except:
            services["r2_storage"] = False
            overall_status = "degraded"

        # Check embedding model
        try:
            if doc_processor and doc_processor.embedder:
                # Try a simple embedding test
                test_embedding = doc_processor.embedder.encode(["test"])
                services["embedding_model"] = len(test_embedding) > 0
            else:
                services["embedding_model"] = False
                overall_status = "degraded"
        except:
            services["embedding_model"] = False
            overall_status = "degraded"

        logger.info(f"✅ [HEALTH] Status: {overall_status}")

        return HealthCheckResponse(
            status=overall_status, services=services, version="1.0.0"
        )

    except Exception as e:
        logger.error(f"❌ [HEALTH] Health check failed: {e}")
        return HealthCheckResponse(
            status="unhealthy", services={"error": str(e)}, version="1.0.0"
        )


@router.delete("/api/documents/user/{user_id}/collection")
async def delete_user_collection(
    user_id: str, qdrant: QdrantManager = Depends(get_qdrant_manager)
):
    """
    🧪 TEST ENDPOINT: Delete user's document collection

    This endpoint is for testing purposes to reset user's collection.
    WARNING: This will permanently delete all user documents!
    """
    logger.info(f"🗑️ [DELETE] Deleting collection for user: {user_id}")

    try:
        # Use QdrantManager for consistent collection naming
        collection_name = qdrant.get_collection_name(user_id)

        # Check if collection exists
        collections = qdrant.client.get_collections()
        existing_names = [col.name for col in collections.collections]

        if collection_name not in existing_names:
            logger.warning(f"⚠️ Collection {collection_name} does not exist")
            return {
                "success": False,
                "message": f"Collection for user {user_id} does not exist",
                "collection_name": collection_name,
            }

        # Delete collection
        qdrant.client.delete_collection(collection_name=collection_name)
        logger.info(f"✅ [DELETE] Successfully deleted collection: {collection_name}")

        return {
            "success": True,
            "message": f"Successfully deleted collection for user {user_id}",
            "collection_name": collection_name,
        }

    except Exception as e:
        logger.error(f"❌ [DELETE] Failed to delete collection for user {user_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete collection: {str(e)}"
        )


@router.get("/api/documents/task/{task_id}/status")
async def get_task_status(
    task_id: str, queue: QueueManager = Depends(get_queue_manager)
):
    """
    Get the status of a document processing task.

    Returns current status: pending, processing, completed, failed
    """
    try:
        status = await queue.get_task_status(task_id)

        if not status:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return {
            "task_id": status.task_id,
            "status": status.status,
            "user_id": status.user_id,
            "document_id": status.document_id,
            "created_at": status.created_at,
            "started_at": status.started_at,
            "completed_at": status.completed_at,
            "error_message": status.error_message,
            "retry_count": status.retry_count,
            "worker_id": status.worker_id,
        }

    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get task status: {str(e)}"
        )


@router.get("/api/documents/queue/stats")
async def get_queue_stats(queue: QueueManager = Depends(get_queue_manager)):
    """
    Get queue statistics including pending tasks, processing tasks, etc.
    """
    try:
        stats = await queue.get_queue_stats()
        return stats

    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get queue stats: {str(e)}"
        )


@router.post("/api/documents/task/{task_id}/retry")
async def retry_task(task_id: str, queue: QueueManager = Depends(get_queue_manager)):
    """
    Retry a failed task by re-queuing it.
    """
    try:
        success = await queue.retry_task(task_id)

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Task {task_id} not found or cannot be retried"
            )

        return {
            "success": True,
            "message": f"Task {task_id} has been re-queued for processing",
        }

    except Exception as e:
        logger.error(f"Error retrying task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retry task: {str(e)}")


@router.get("/api/documents/debug/collection/{user_id}")
async def debug_user_collection(
    user_id: str, qdrant: QdrantManager = Depends(get_qdrant_manager)
):
    """
    Debug endpoint to check collection and documents for a user
    """
    try:
        collection_name = qdrant.get_collection_name(user_id)
        logger.info(f"🔍 [DEBUG] Collection name: {collection_name}")

        # Check if collection exists
        collections = qdrant.client.get_collections()
        existing_names = [col.name for col in collections.collections]

        collection_exists = collection_name in existing_names
        logger.info(f"🔍 [DEBUG] Collection exists: {collection_exists}")

        result = {
            "user_id": user_id,
            "collection_name": collection_name,
            "collection_exists": collection_exists,
            "all_collections": existing_names,
        }

        if collection_exists:
            # Get some sample documents
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            points, _ = qdrant.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id))
                    ]
                ),
                limit=5,
                with_payload=True,
                with_vectors=False,
            )

            documents = []
            for point in points:
                documents.append(
                    {
                        "point_id": point.id,
                        "user_id": point.payload.get("user_id"),
                        "document_id": point.payload.get("document_id"),
                        "chunk_id": point.payload.get("chunk_id"),
                        "content_preview": point.payload.get("content", "")[:100],
                    }
                )

            result["documents"] = documents
            result["total_points"] = len(points)

        return result

    except Exception as e:
        logger.error(f"❌ [DEBUG] Debug failed: {e}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")
