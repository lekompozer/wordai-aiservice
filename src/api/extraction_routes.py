"""
AI Extraction Routes - Single Endpoint for R2 URL Processing
AI Extraction API - Endpoint duy nhất cho xử lý R2 URL

WORKFLOW / LUỒNG XỬ LÝ:
1. Backend uploads files to R2 and gets public URL
   Backend upload file lên R2 và lấy public URL
2. Backend calls /api/extract/process with R2 URL + metadata
   Backend gọi /api/extract/process với R2 URL + metadata
3. AI Service processes with template-based extraction
   AI Service xử lý với extraction dựa trên template
4. Returns raw data + structured JSON according to industry template
   Trả về raw data + structured JSON theo template industry
5. Optionally uploads to Qdrant via worker
   Tùy chọn upload lên Qdrant qua worker

CALLBACK URL PATTERNS / MẪU CALLBACK URL:
- File Upload: /api/webhooks/file-processed (raw content processing)
- AI Extraction: /api/webhooks/ai/extraction-callback (structured data extraction)

IMPLEMENTED FLOW / LUỒNG ĐÃ TRIỂN KHAI:
- Template selection based on Industry + DataType (✅ ai_extraction_service.py)
- JSON schema integration from templates (✅ ai_extraction_service.py)
- AI provider selection (ChatGPT Vision/DeepSeek) (✅ ai_extraction_service.py)
- Raw + structured data extraction (✅ ai_extraction_service.py)
- Qdrant worker integration ready (✅ ai_extraction_service.py)
"""

import json
import requests
import time
import redis
import uuid
import os
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from src.models.unified_models import Industry, Language
from src.services.ai_extraction_service import get_ai_service
from src.services.task_status_service import TaskStatusService, CallbackService
from src.utils.logger import setup_logger
from src.queue.queue_dependencies import (
    get_extraction_queue,
)  # Use extraction queue for ExtractionProcessingTask
from src.queue.queue_manager import QueueManager
from src.queue.task_models import ExtractionProcessingTask

# ✅ HYBRID STRATEGY: Import only necessary callback handler
from src.api.callbacks.enhanced_callback_handler import send_backend_callback

# Initialize router and logger
router = APIRouter(prefix="/api/extract")
logger = setup_logger(__name__)

# Global queue manager (initialized once for efficiency)
queue_manager: Optional[QueueManager] = None

# Redis client for task status tracking
redis_client = None


def get_redis_client():
    """Get Redis client for task status tracking"""
    global redis_client
    if redis_client is None:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
    return redis_client


# ===== REQUEST MODEL =====


class ExtractionRequest(BaseModel):
    """
    Single extraction request for R2 URL processing
    Yêu cầu extraction duy nhất cho xử lý R2 URL
    """

    # Required fields / Trường bắt buộc
    r2_url: str = Field(..., description="Public R2 URL of the uploaded file")
    company_id: str = Field(..., description="Company ID for Qdrant storage")
    industry: Industry = Field(
        ..., description="Company industry for template selection"
    )

    # Optional extraction targeting / Nhắm mục tiêu extraction tùy chọn
    target_categories: Optional[List[str]] = Field(
        None,
        description="Target categories for extraction. If None, extracts both products and services automatically",
        example=["products", "services"],
    )

    # Data type specification for backend tracking
    data_type: Optional[str] = Field(
        None,
        description="Specific data type for backend tracking (products, services, or auto)",
        example="products",
    )

    # File metadata / Metadata file
    file_metadata: Dict[str, Any] = Field(
        ...,
        description="File metadata (original_name, file_size, etc.)",
        example={
            "original_name": "golden_dragon_menu.pdf",
            "file_size": 1024000,
            "file_type": "application/pdf",
            "uploaded_at": "2025-07-16T10:00:00Z",
        },
    )

    # Optional company context / Context công ty tùy chọn
    company_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Company information for extraction context",
        example={
            "id": "golden-dragon-restaurant",
            "name": "Golden Dragon Restaurant",
            "industry": "restaurant",
            "description": "Traditional Vietnamese restaurant",
        },
    )

    # Processing options / Tùy chọn xử lý
    language: Optional[Language] = Field(
        None, description="Target language for extraction results (from Frontend)"
    )
    upload_to_qdrant: bool = Field(
        False, description="Whether to upload results to Qdrant via background worker"
    )
    callback_url: Optional[str] = Field(
        None,
        description="Callback URL for async processing notifications",
        example="https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback",
    )


# ===== RESPONSE MODEL =====


class ExtractionResponse(BaseModel):
    """
    Complete extraction response with raw and structured data
    Response extraction hoàn chỉnh với raw và structured data
    """

    # Status / Trạng thái
    success: bool = Field(..., description="Whether extraction was successful")
    message: str = Field(..., description="Processing status message")

    # Core extraction results / Kết quả extraction chính
    raw_content: Optional[str] = Field(
        None, description="Complete raw extracted content"
    )
    structured_data: Optional[Dict[str, Any]] = Field(
        None, description="Structured data according to industry template"
    )

    # Processing metadata / Metadata xử lý
    template_used: Optional[str] = Field(
        None, description="Industry template used for extraction"
    )
    ai_provider: Optional[str] = Field(
        None, description="AI provider used (ChatGPT Vision/DeepSeek)"
    )
    industry: Optional[str] = Field(None, description="Industry classification")
    data_type: Optional[str] = Field(None, description="Data type processed")

    # Performance metrics / Metrics hiệu suất
    processing_time: Optional[float] = Field(
        None, description="Processing time in seconds"
    )
    total_items_extracted: Optional[int] = Field(
        None, description="Number of items extracted"
    )

    # Additional metadata / Metadata bổ sung
    extraction_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Detailed extraction metadata"
    )

    # Error handling / Xử lý lỗi
    error: Optional[str] = Field(None, description="Error message if extraction failed")
    error_details: Optional[Dict[str, Any]] = Field(
        None, description="Detailed error information"
    )


# ===== QUEUE-BASED REQUEST MODEL =====


class ExtractionQueueRequest(BaseModel):
    """
    Queue-based extraction request for async processing
    Yêu cầu extraction dựa trên queue cho xử lý bất đồng bộ
    """

    # Required fields / Trường bắt buộc
    r2_url: str = Field(..., description="Public R2 URL of the uploaded file")
    company_id: str = Field(..., description="Company ID for Qdrant storage")
    industry: Industry = Field(
        ..., description="Company industry for template selection"
    )

    # File metadata / Metadata file
    file_name: str = Field(..., description="Original file name")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    file_type: Optional[str] = Field(None, description="MIME type of the file")
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata including file_id",
        example={"file_id": "file_uuid_123"},
    )

    # Backend tracking / Theo dõi backend
    data_type: Optional[str] = Field(
        None,
        description="Specific data type for backend tracking (products, services, or auto)",
        example="products",
    )
    target_categories: Optional[List[str]] = Field(
        None,
        description="Target categories for extraction",
        example=["products", "services"],
    )

    # Processing options / Tùy chọn xử lý
    language: Optional[Language] = Field(
        None, description="Target language for extraction (from Frontend)"
    )
    callback_url: Optional[str] = Field(
        None,
        description="Callback URL for extraction completion notifications",
        example="https://api.agent8x.io.vn/api/webhooks/ai/extraction-callback",
    )

    # Optional company context / Context công ty tùy chọn
    company_info: Optional[Dict[str, Any]] = Field(
        None, description="Company information"
    )


class ExtractionQueueResponse(BaseModel):
    """
    Queue-based extraction response with task ID
    Response extraction dựa trên queue với task ID
    """

    success: bool = Field(..., description="Whether task was queued successfully")
    task_id: str = Field(..., description="Unique task ID for tracking")
    company_id: str = Field(..., description="Company ID")
    status: str = Field(..., description="Task status (queued)")
    message: str = Field(..., description="Status message")
    estimated_time: int = Field(..., description="Estimated processing time in seconds")

    # Error handling / Xử lý lỗi
    error: Optional[str] = Field(None, description="Error message if queueing failed")


# ===== TASK STATUS MODELS =====


class TaskStatusResponse(BaseModel):
    """Task status response model"""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(
        ..., description="Task status: queued, processing, completed, failed"
    )
    progress: Optional[Dict[str, Any]] = Field(None, description="Progress information")
    submitted_at: str = Field(..., description="Task submission timestamp")
    completed_at: Optional[str] = Field(None, description="Task completion timestamp")
    processing_time: Optional[float] = Field(
        None, description="Processing time in seconds"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")


class TaskResultResponse(BaseModel):
    """Task result response model"""

    task_id: str = Field(..., description="Unique task identifier")
    success: bool = Field(..., description="Whether extraction was successful")
    message: str = Field(..., description="Processing result message")
    processing_time: Optional[float] = Field(
        None, description="Processing time in seconds"
    )
    total_items_extracted: Optional[int] = Field(
        None, description="Number of items extracted"
    )
    ai_provider: Optional[str] = Field(None, description="AI provider used")
    template_used: Optional[str] = Field(
        None, description="Template used for extraction"
    )
    industry: Optional[str] = Field(None, description="Industry classification")
    data_type: Optional[str] = Field(None, description="Data type processed")

    # Full extraction data
    raw_content: Optional[str] = Field(
        None, description="Complete raw extracted content"
    )
    structured_data: Optional[Dict[str, Any]] = Field(
        None, description="Structured extraction results"
    )
    extraction_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Detailed extraction metadata"
    )

    # Error handling
    error: Optional[str] = Field(None, description="Error message if extraction failed")
    error_details: Optional[Dict[str, Any]] = Field(
        None, description="Detailed error information"
    )


# ===== DEPENDENCY =====


async def get_extraction_service():
    """Get AI extraction service instance"""
    return get_ai_service()


async def get_queue_manager():
    """Get queue manager instance"""
    global queue_manager
    if queue_manager is None:
        try:
            queue_manager = QueueManager()
            await queue_manager.connect()
            logger.info("✅ Queue manager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize queue manager: {str(e)}")
            raise HTTPException(status_code=503, detail="Queue service unavailable")
    return queue_manager


# Global task status service
task_status_service = None


def get_task_status_service():
    """Get task status service instance"""
    global task_status_service
    if task_status_service is None:
        redis_client = get_redis_client()
        task_status_service = TaskStatusService(redis_client)
    return task_status_service


# ===== MAIN ENDPOINT REMOVED =====
#
# ⚠️ ENDPOINT /process ĐÃ ĐƯỢC BACKUP VÀ GỠ BỎ
#
# Sync endpoint /process đã được backup vào: /src/api/extraction_routes_sync_backup.py
# Giờ chỉ sử dụng queue-based async endpoint /process-async với Hybrid Strategy
#
# Để khôi phục sync endpoint, copy từ backup file và uncomment


# ===== BACKGROUND TASK =====


async def schedule_qdrant_upload(
    extraction_result_json: str,
    metadata_json: str,
    company_id: str,
    industry: str,
    language: str = "auto",  # Default to auto-detect
    callback_url: Optional[str] = None,
):
    """
    Schedule Qdrant upload via ingestion worker
    Lên lịch upload Qdrant qua ingestion worker

    Uses ai_extraction_service.prepare_for_qdrant_ingestion()
    Sử dụng ai_extraction_service.prepare_for_qdrant_ingestion()
    """
    try:
        # Deserialize the JSON strings back into dictionaries
        extraction_result = json.loads(extraction_result_json)
        metadata = json.loads(metadata_json)

        logger.info("📤 Processing Qdrant upload via background worker")
        logger.info(
            f"📊 Deserialized extraction result with {len(extraction_result.get('products', []))} products"
        )
        logger.info(f"📦 Products found: {len(extraction_result.get('products', []))}")
        logger.info(f"🔧 Services found: {len(extraction_result.get('services', []))}")
        logger.info(f"🏭 Industry input: '{industry}' (type: {type(industry)})")
        logger.info(f"🌐 Language input: '{language}' (type: {type(language)})")
        logger.info(f"📊 Extraction result size: {len(extraction_result_json)} chars")
        logger.info(f"📋 Metadata size: {len(metadata_json)} chars")

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
                # Default to English if no language specified from frontend
                language_enum = Language.ENGLISH
            logger.info(f"✅ Language enum converted: {language_enum}")
        except ValueError as e:
            logger.warning(
                f"⚠️ Unknown language '{language}', using ENGLISH. Error: {e}"
            )
            language_enum = Language.ENGLISH

        # Use implemented method to prepare data for worker with proper parameters
        ingestion_data = await ai_service.prepare_for_qdrant_ingestion(
            extraction_result=extraction_result,
            user_id=metadata.get("user_id", "system"),
            document_id=metadata.get("file_id", metadata.get("document_id", "unknown")),
            company_id=company_id,
            industry=industry_enum,
            language=language_enum,
            callback_url=callback_url,
        )

        ingestion_metadata = ingestion_data.get("ingestion_metadata", {})
        logger.info("✅ Qdrant company ingestion scheduled successfully")
        logger.info(f"   🏢 Company: {company_id}")
        logger.info(f"   🏭 Industry: {industry}")
        logger.info(f"   📊 Total chunks: {ingestion_metadata.get('total_chunks', 0)}")

        # 📞 STANDARD CALLBACK: Use enhanced_callback_handler với webhook signature
        if callback_url:
            try:
                callback_payload = {
                    "task_id": metadata.get("file_id", "background_task"),
                    "company_id": company_id,
                    "status": "completed",
                    "processing_type": "background_qdrant_upload",
                    "results": {
                        "products_count": len(extraction_result.get("products", [])),
                        "services_count": len(extraction_result.get("services", [])),
                        "total_chunks": ingestion_metadata.get("total_chunks", 0),
                    },
                    "timestamp": datetime.now().isoformat(),
                }

                logger.info(
                    f"📞 Sending background callback via enhanced_callback_handler"
                )
                logger.info(f"   🔗 Callback URL: {callback_url}")

                # ✅ USE ENHANCED_CALLBACK_HANDLER: With webhook signature and proper error handling
                callback_success = await send_backend_callback(
                    callback_url=callback_url,
                    callback_payload=callback_payload,
                    event_type="background_qdrant_upload_completed",
                    timeout=30,
                )

                if callback_success:
                    logger.info(
                        f"✅ Background callback sent successfully via enhanced_callback_handler"
                    )
                else:
                    logger.warning(
                        f"⚠️ Background callback failed via enhanced_callback_handler"
                    )

            except Exception as callback_error:
                logger.error(f"❌ Failed to send background callback: {callback_error}")

    except Exception as e:
        logger.error(f"❌ Failed to schedule Qdrant upload: {str(e)}")

        # 📞 STANDARD ERROR CALLBACK: Use enhanced_callback_handler với webhook signature
        if callback_url:
            try:
                error_callback_payload = {
                    "task_id": (
                        metadata.get("file_id", "background_task")
                        if "metadata" in locals()
                        else "background_task"
                    ),
                    "company_id": company_id,
                    "status": "failed",
                    "processing_type": "background_qdrant_upload",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

                logger.info(
                    f"📞 Sending background error callback via enhanced_callback_handler"
                )
                logger.info(f"   🔗 Callback URL: {callback_url}")

                # ✅ USE ENHANCED_CALLBACK_HANDLER: With webhook signature and proper error handling
                callback_success = await send_backend_callback(
                    callback_url=callback_url,
                    callback_payload=error_callback_payload,
                    event_type="background_qdrant_upload_failed",
                    timeout=30,
                )

                if callback_success:
                    logger.info(
                        f"✅ Background error callback sent successfully via enhanced_callback_handler"
                    )
                else:
                    logger.warning(
                        f"⚠️ Background error callback failed via enhanced_callback_handler"
                    )

            except Exception as callback_error:
                logger.error(
                    f"❌ Failed to send background error callback: {callback_error}"
                )


# ===== HYBRID STRATEGY QUEUE-BASED ENDPOINT =====


@router.post("/process-async", response_model=ExtractionQueueResponse)
async def process_extraction_async_hybrid(
    request: ExtractionQueueRequest,
    queue: QueueManager = Depends(
        get_extraction_queue
    ),  # Use extraction queue for /process-async
    status_service: TaskStatusService = Depends(get_task_status_service),
) -> ExtractionQueueResponse:
    """
    🎯 **HYBRID STRATEGY QUEUE-BASED WORKFLOW**: Process extraction với AI Auto-Categorization + Individual Storage + Enhanced Callback

    **QUEUE WORKFLOW với HYBRID STRATEGY:**

    1. ✅ **API receives request and validates parameters**
       API nhận request và validate parameters

    2. ✅ **Create ExtractionProcessingTask với HYBRID STRATEGY flags**
       Tạo task với các cờ chỉ dẫn worker sử dụng Hybrid Strategy

    3. ✅ **Push task to Redis queue (document_processing)**
       Đẩy task vào Redis queue với metadata đầy đủ

    4. ✅ **Return task_id immediately to backend**
       Trả về task_id ngay lập tức cho backend

    5. 🔄 **Worker processes task với HYBRID STRATEGY:**
       - **AI Extraction**: Gọi AIExtractionService với generic prompts (auto-categorization)
       - **Individual Processing**: Xử lý từng product/service riêng biệt:
         * Generate embedding cho từng item
         * Tạo Qdrant point riêng với rich metadata (category, tags, target_audience)
         * Upsert vào collection "multi_company_data"
       - **Enhanced Callback**: Gọi callback với qdrant_point_id + category cho từng item

    **HYBRID STRATEGY FEATURES được enable trong task:**
    ✅ **AI Auto-Categorization**: Generic prompts, không cần examples cụ thể
    ✅ **Individual Storage**: Mỗi product/service = 1 Qdrant point riêng biệt
    ✅ **Metadata Filtering**: Rich metadata (category, sub_category, tags, target_audience)
    ✅ **Vector Search**: Semantic similarity search trên embeddings
    ✅ **Enhanced Callback**: Callback chứa qdrant_point_id cho individual CRUD
    """

    # Generate unique task ID với prefix hybrid
    task_id = f"hybrid_extract_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

    logger.info(
        "🎯 [HYBRID QUEUE-API] Received Hybrid Strategy extraction queue request"
    )
    logger.info(f"   🆔 Task ID: {task_id}")
    logger.info(f"   🔗 R2 URL: {request.r2_url}")
    logger.info(f"   🏢 Company ID: {request.company_id}")
    logger.info(f"   🏭 Industry: {request.industry}")
    logger.info(
        f"   🎯 Strategy: Queue-based Hybrid Search (Metadata Filtering + Vector Search + Individual Storage)"
    )

    # DETAILED REQUEST TRACKING - Same as sync endpoint
    backend_data_type = request.data_type or "auto"  # String for data_type field
    target_categories_specified = request.target_categories or ["products", "services"]

    logger.info("=" * 60)
    logger.info("📊 HYBRID STRATEGY QUEUE REQUEST ANALYSIS:")
    logger.info(f"   📋 Backend Data Type: '{backend_data_type}'")
    logger.info(f"   📊 Target Categories: {target_categories_specified}")
    logger.info(f"   📄 File: {request.file_name}")
    logger.info(f"   📦 File Size: {request.file_size or 'unknown'} bytes")
    logger.info(f"   📝 File Type: {request.file_type or 'unknown'}")
    logger.info(f"   📞 Callback URL: {request.callback_url or 'None'}")
    logger.info(f"   🎯 Processing Mode: Hybrid Strategy với Individual Storage")
    logger.info("=" * 60)

    try:
        # ✅ CREATE EXTRACTION PROCESSING TASK với HYBRID STRATEGY FLAGS
        processing_task = ExtractionProcessingTask(
            task_id=task_id,
            company_id=request.company_id,
            r2_url=request.r2_url,
            file_name=request.file_name,
            file_type=request.file_type or "text/plain",
            file_size=request.file_size or 0,
            industry=request.industry,
            language=request.language or Language.AUTO_DETECT,  # Default to auto-detect
            data_type=backend_data_type,
            target_categories=target_categories_specified,
            callback_url=request.callback_url,
            company_info=request.company_info or {},
            created_at=datetime.utcnow(),
            # 🎯 HYBRID STRATEGY: Enhanced processing metadata với worker instructions
            processing_metadata={
                # === FILE INFORMATION (for catalog service) ===
                "file_id": (
                    request.metadata.get("file_id") if request.metadata else None
                ),
                "file_name": request.file_name,
                "original_filename": request.file_name,
                # === HYBRID STRATEGY FLAGS ===
                "hybrid_strategy_enabled": True,
                "individual_storage_mode": True,
                "ai_auto_categorization": True,
                "enhanced_callback_mode": True,
                # === WORKER INSTRUCTIONS ===
                "extraction_mode": "hybrid_search_ready",
                "processing_type": "hybrid_extraction_workflow",
                "storage_strategy": "individual_points_with_metadata",
                "callback_strategy": "enhanced_with_qdrant_ids",
                # === AI PROCESSING SETTINGS ===
                "use_generic_prompts": True,  # No industry-specific examples
                "auto_categorization_fields": [
                    "category",
                    "sub_category",
                    "tags",
                    "target_audience",
                    "coverage_type",
                    "service_type",
                ],
                # === QDRANT STORAGE SETTINGS ===
                "collection_name": "multi_company_data",
                "point_strategy": "one_product_one_point",
                "metadata_filtering_enabled": True,
                "vector_search_enabled": True,
                # === EMBEDDING & CHUNKING ===
                "embedding_strategy": "individual_item_embeddings",
                "chunking_strategy": "per_item_chunking",
                "content_for_embedding_required": True,
                # === CALLBACK REQUIREMENTS ===
                "callback_includes_qdrant_ids": True,
                "callback_includes_categories": True,
                "callback_handler": "enhanced_callback_handler",
                # === PERFORMANCE SETTINGS ===
                "min_items_per_chunk": 1,  # Individual processing
                "chunk_by_categories": False,  # Individual items, not chunks
                "upload_to_qdrant": True,
                # === SEARCH CAPABILITIES ===
                "search_capabilities": {
                    "metadata_filtering_fields": [
                        "category",
                        "sub_category",
                        "tags",
                        "target_audience",
                        "coverage_type",
                        "service_type",
                        "industry",
                        "item_type",
                    ],
                    "vector_search_enabled": True,
                    "individual_item_crud": True,
                    "filter_then_search": True,  # Hybrid approach
                },
            },
        )

        # Enqueue task với Hybrid Strategy flags
        logger.info(
            f"📤 [HYBRID QUEUE-API] Enqueueing Hybrid Strategy extraction task {task_id}"
        )
        logger.info(
            f"   🎯 Worker sẽ thực hiện: AI Auto-Categorization + Individual Storage + Enhanced Callback"
        )
        success = await queue.enqueue_generic_task(processing_task)

        if not success:
            logger.error(f"❌ [HYBRID QUEUE-API] Failed to enqueue task {task_id}")
            return ExtractionQueueResponse(
                success=False,
                task_id=task_id,
                company_id=request.company_id,
                status="failed",
                message="Failed to queue Hybrid Strategy extraction task",
                estimated_time=0,
                error="Queue service unavailable",
            )

        # Create task status tracking
        await status_service.create_task(task_id, request.company_id, datetime.now())

        logger.info(
            f"✅ [HYBRID QUEUE-API] Task {task_id} queued successfully với Hybrid Strategy"
        )
        logger.info(
            f"   📊 Worker sẽ xử lý: {len(target_categories_specified)} categories"
        )
        logger.info(
            f"   🎯 Strategy: Metadata Filtering + Vector Search + Individual Storage"
        )
        logger.info(
            f"   📞 Enhanced Callback: Sẽ bao gồm qdrant_point_id + category cho từng item"
        )

        return ExtractionQueueResponse(
            success=True,
            task_id=task_id,
            company_id=request.company_id,
            status="queued",
            message=f"✅ HYBRID STRATEGY: Task queued successfully for {backend_data_type} extraction với AI auto-categorization + individual storage",
            estimated_time=30,  # Hybrid Strategy có thể mất nhiều thời gian hơn do individual processing
        )

    except Exception as e:
        logger.error(
            f"❌ [HYBRID QUEUE-API] Failed to queue Hybrid Strategy extraction task: {str(e)}"
        )
        return ExtractionQueueResponse(
            success=False,
            task_id=task_id,
            company_id=request.company_id,
            status="error",
            message="Failed to queue Hybrid Strategy extraction task",
            estimated_time=0,
            error=str(e),
        )

    # ===== HYBRID STRATEGY WORKER SUPPORT FUNCTION =====
    #
    # ⚠️ HÀM NÀY ĐÃ LỖI THỜI VÀ ĐƯỢC GỠ BỎ
    #
    # Logic xử lý (embedding, lưu Qdrant) đã được chuyển hoàn toàn sang
    # function chuyên dụng trong `src/api/callbacks/enhanced_callback_handler.py`.
    #
    # Worker bây giờ sẽ gọi AIExtractionService, sau đó gọi trực tiếp function
    # `process_extraction_with_hybrid_strategy()` thay vì gọi hàm này.
    #
    # ✅ KIẾN TRÚC MỚI:
    # Worker → AIExtractionService → enhanced_callback_handler.process_extraction_with_hybrid_strategy()
    #
    # async def schedule_hybrid_qdrant_upload_with_enhanced_callback(...):
    #    ... (TOÀN BỘ CODE CỦA HÀM NÀY ĐÃ BỊ XÓA VÀ CHUYỂN SANG enhanced_callback_handler.py)

    # ===== STATUS & RESULT ENDPOINTS =====
    """
    🎯 **HYBRID STRATEGY WORKER FUNCTION**: Schedule individual Qdrant upload với enhanced callback

    **HYBRID STRATEGY WORKFLOW:**
    1. ✅ **Individual Processing**: Xử lý từng product/service riêng biệt
    2. ✅ **Rich Metadata Generation**: Tạo metadata đầy đủ cho filtering
    3. ✅ **Individual Qdrant Points**: Mỗi item = 1 point với embedding riêng
    4. ✅ **Enhanced Callback**: Callback chứa qdrant_point_id + category cho từng item

    **CALLBACK FORMAT:**
    ```json
    {
        "task_id": "hybrid_extract_xxx",
        "company_id": "company_123",
        "status": "completed",
        "processing_type": "hybrid_individual_storage",
        "items_processed": [
            {
                "item_id": "item_1",
                "qdrant_point_id": "uuid_xxx",
                "category": "products",
                "sub_category": "main_course",
                "item_type": "food_item",
                "title": "Phở Bò",
                "metadata": { ... }
            },
            ...
        ],
        "summary": {
            "total_items": 25,
            "products_count": 15,
            "services_count": 10,
            "collection": "multi_company_data"
        }
    }
    ```
    """
    try:
        # Deserialize input data
        extraction_result = json.loads(extraction_result_json)
        metadata = json.loads(metadata_json)
        processing_metadata = processing_metadata or {}

        logger.info(
            "🎯 [HYBRID WORKER] Starting individual Qdrant upload with enhanced callback"
        )
        logger.info(f"   🏢 Company: {company_id}")
        logger.info(f"   🏭 Industry: {industry}")
        logger.info(f"   📦 Products: {len(extraction_result.get('products', []))}")
        logger.info(f"   🔧 Services: {len(extraction_result.get('services', []))}")
        logger.info(f"   📞 Callback URL: {callback_url or 'None'}")
        logger.info(f"   🎯 Mode: Individual Storage + Enhanced Callback")

        # Get services
        ai_service = get_ai_service()
        embedding_service = get_embedding_service()
        qdrant_manager = create_qdrant_manager()

        # Get MongoDB catalog service for dual storage
        from src.services.product_catalog_service import get_product_catalog_service

        catalog_service = await get_product_catalog_service()

        # Convert enums
        from src.models.unified_models import Industry, Language

        industry_enum = Industry(industry) if isinstance(industry, str) else industry
        language_enum = Language(language) if isinstance(language, str) else language

        # Collection name for Hybrid Strategy
        collection_name = processing_metadata.get(
            "collection_name", "multi_company_data"
        )

        # Process each item individually
        processed_items = []
        total_items = 0

        # Process products individually
        products = extraction_result.get("products", [])
        for idx, product in enumerate(products):
            try:
                logger.info(
                    f"🎯 [HYBRID WORKER] Processing product {idx+1}/{len(products)}: {product.get('name', 'Unknown')}"
                )

                # Generate rich metadata for filtering
                product_metadata = {
                    "company_id": company_id,
                    "industry": str(industry_enum),
                    "item_type": "product",
                    "category": "products",
                    "sub_category": product.get("category", "uncategorized"),
                    "tags": product.get("tags", []),
                    "target_audience": product.get("target_audience", "general"),
                    "coverage_type": product.get("coverage_type", "standard"),
                    "item_id": f"prod_{company_id}_{idx}",
                    "source_document": metadata.get("original_name", "unknown"),
                    "extraction_timestamp": datetime.now().isoformat(),
                    "hybrid_strategy": True,
                    "individual_storage": True,
                }

                # Generate content for embedding
                content_for_embedding = f"""
                Name: {product.get('name', '')}
                Description: {product.get('description', '')}
                Category: {product.get('category', '')}
                Price: {product.get('price', '')}
                Tags: {', '.join(product.get('tags', []))}
                Company: {company_id}
                Industry: {industry}
                """.strip()

                # Generate embedding
                embedding = await embedding_service.generate_embedding(
                    content_for_embedding
                )

                # Create Qdrant point ID
                point_id = str(uuid.uuid4())

                # Upsert to Qdrant
                await qdrant_manager.upsert_points(
                    collection_name=collection_name,
                    points=[
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": {
                                **product_metadata,
                                "content": content_for_embedding,
                                "raw_data": product,
                            },
                        }
                    ],
                )

                # 🔥 DUAL STORAGE: Also save to MongoDB ProductCatalogService
                enriched_product = await catalog_service.register_item(
                    item_data=product, company_id=company_id, item_type="product"
                )

                # Get MongoDB product_id for tracking
                mongo_product_id = enriched_product.get("product_id", "N/A")

                # Track processed item
                processed_items.append(
                    {
                        "item_id": product_metadata["item_id"],
                        "qdrant_point_id": point_id,
                        "mongo_product_id": mongo_product_id,  # Track MongoDB ID
                        "category": "products",
                        "sub_category": product.get("category", "uncategorized"),
                        "item_type": "product",
                        "title": product.get("name", "Unknown Product"),
                        "metadata": product_metadata,
                    }
                )

                total_items += 1
                logger.info(
                    f"   ✅ Product saved to Qdrant: {point_id} & MongoDB: {mongo_product_id}"
                )

            except Exception as e:
                logger.error(f"   ❌ Failed to process product {idx}: {e}")

        # Process services individually
        services = extraction_result.get("services", [])
        for idx, service in enumerate(services):
            try:
                logger.info(
                    f"🎯 [HYBRID WORKER] Processing service {idx+1}/{len(services)}: {service.get('name', 'Unknown')}"
                )

                # Generate rich metadata for filtering
                service_metadata = {
                    "company_id": company_id,
                    "industry": str(industry_enum),
                    "item_type": "service",
                    "category": "services",
                    "sub_category": service.get("category", "uncategorized"),
                    "tags": service.get("tags", []),
                    "target_audience": service.get("target_audience", "general"),
                    "service_type": service.get("service_type", "standard"),
                    "coverage_type": service.get("coverage_type", "standard"),
                    "item_id": f"serv_{company_id}_{idx}",
                    "source_document": metadata.get("original_name", "unknown"),
                    "extraction_timestamp": datetime.now().isoformat(),
                    "hybrid_strategy": True,
                    "individual_storage": True,
                }

                # Generate content for embedding
                content_for_embedding = f"""
                Name: {service.get('name', '')}
                Description: {service.get('description', '')}
                Category: {service.get('category', '')}
                Price: {service.get('price', '')}
                Duration: {service.get('duration', '')}
                Tags: {', '.join(service.get('tags', []))}
                Company: {company_id}
                Industry: {industry}
                """.strip()

                # Generate embedding
                embedding = await embedding_service.generate_embedding(
                    content_for_embedding
                )

                # Create Qdrant point ID
                point_id = str(uuid.uuid4())

                # Upsert to Qdrant
                await qdrant_manager.upsert_points(
                    collection_name=collection_name,
                    points=[
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": {
                                **service_metadata,
                                "content": content_for_embedding,
                                "raw_data": service,
                            },
                        }
                    ],
                )

                # 🔥 DUAL STORAGE: Also save to MongoDB ProductCatalogService
                enriched_service = await catalog_service.register_item(
                    item_data=service, company_id=company_id, item_type="service"
                )

                # Get MongoDB service_id for tracking
                mongo_service_id = enriched_service.get("service_id", "N/A")

                # Track processed item
                processed_items.append(
                    {
                        "item_id": service_metadata["item_id"],
                        "qdrant_point_id": point_id,
                        "mongo_service_id": mongo_service_id,  # Track MongoDB ID
                        "category": "services",
                        "sub_category": service.get("category", "uncategorized"),
                        "item_type": "service",
                        "title": service.get("name", "Unknown Service"),
                        "metadata": service_metadata,
                    }
                )

                total_items += 1
                logger.info(
                    f"   ✅ Service saved to Qdrant: {point_id} & MongoDB: {mongo_service_id}"
                )

            except Exception as e:
                logger.error(f"   ❌ Failed to process service {idx}: {e}")

        logger.info(
            f"🎯 [HYBRID WORKER] Dual storage (Qdrant + MongoDB) processing completed"
        )
        logger.info(f"   📊 Total items processed: {total_items}")
        logger.info(
            f"   📦 Products: {len([i for i in processed_items if i['category'] == 'products'])}"
        )
        logger.info(
            f"   🔧 Services: {len([i for i in processed_items if i['category'] == 'services'])}"
        )
        logger.info(f"   🗂️ Qdrant Collection: {collection_name}")
        logger.info(f"   💾 MongoDB Collection: internal_products_catalog")

        # 📞 ENHANCED CALLBACK: Use enhanced_callback_handler với webhook signature
        if callback_url:
            try:
                enhanced_callback_payload = {
                    "task_id": metadata.get("file_id", "hybrid_background_task"),
                    "company_id": company_id,
                    "status": "completed",
                    "processing_type": "hybrid_individual_storage",
                    "items_processed": processed_items,
                    "summary": {
                        "total_items": total_items,
                        "products_count": len(
                            [i for i in processed_items if i["category"] == "products"]
                        ),
                        "services_count": len(
                            [i for i in processed_items if i["category"] == "services"]
                        ),
                        "collection": collection_name,
                        "individual_storage": True,
                        "hybrid_strategy": True,
                    },
                    "qdrant_info": {
                        "collection_name": collection_name,
                        "total_points_created": total_items,
                        "individual_crud_enabled": True,
                    },
                    "timestamp": datetime.now().isoformat(),
                }

                logger.info(
                    f"📞 [HYBRID WORKER] Sending enhanced callback via enhanced_callback_handler"
                )
                logger.info(f"   🔗 Callback URL: {callback_url}")
                logger.info(
                    f"   📊 Callback includes {len(processed_items)} items with qdrant_point_id"
                )

                # ✅ USE ENHANCED_CALLBACK_HANDLER: With webhook signature and proper error handling
                callback_success = await send_backend_callback(
                    callback_url=callback_url,
                    callback_payload=enhanced_callback_payload,
                    event_type="hybrid_individual_storage_completed",
                    timeout=30,
                )

                if callback_success:
                    logger.info(
                        f"✅ [HYBRID WORKER] Enhanced callback sent successfully via enhanced_callback_handler"
                    )
                else:
                    logger.warning(
                        f"⚠️ [HYBRID WORKER] Enhanced callback failed via enhanced_callback_handler"
                    )

            except Exception as callback_error:
                logger.error(
                    f"❌ [HYBRID WORKER] Failed to send enhanced callback: {callback_error}"
                )

    except Exception as e:
        logger.error(
            f"❌ [HYBRID WORKER] Failed to process hybrid individual storage: {str(e)}"
        )

        # 📞 ENHANCED ERROR CALLBACK: Use enhanced_callback_handler với webhook signature
        if callback_url:
            try:
                error_callback_payload = {
                    "task_id": (
                        metadata.get("file_id", "hybrid_background_task")
                        if "metadata" in locals()
                        else "hybrid_background_task"
                    ),
                    "company_id": company_id,
                    "status": "failed",
                    "processing_type": "hybrid_individual_storage",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

                logger.info(
                    f"📞 [HYBRID WORKER] Sending error callback via enhanced_callback_handler"
                )
                logger.info(f"   🔗 Callback URL: {callback_url}")

                # ✅ USE ENHANCED_CALLBACK_HANDLER: With webhook signature and proper error handling
                callback_success = await send_backend_callback(
                    callback_url=callback_url,
                    callback_payload=error_callback_payload,
                    event_type="hybrid_individual_storage_failed",
                    timeout=30,
                )

                if callback_success:
                    logger.info(
                        f"✅ [HYBRID WORKER] Error callback sent successfully via enhanced_callback_handler"
                    )
                else:
                    logger.warning(
                        f"⚠️ [HYBRID WORKER] Error callback failed via enhanced_callback_handler"
                    )

            except Exception as callback_error:
                logger.error(
                    f"❌ [HYBRID WORKER] Failed to send error callback: {callback_error}"
                )


# ===== STATUS & RESULT ENDPOINTS =====


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str, status_service: TaskStatusService = Depends(get_task_status_service)
) -> TaskStatusResponse:
    """
    Get current status of an extraction task
    Lấy trạng thái hiện tại của task extraction
    """
    try:
        logger.info(f"📊 Checking status for task: {task_id}")

        task_data = await status_service.get_task_status(task_id)

        if not task_data:
            logger.warning(f"⚠️ Task not found: {task_id}")
            raise HTTPException(
                status_code=404, detail=f"Task {task_id} not found or expired"
            )

        # Check if task is still in Redis queue (processing)
        redis_client = get_redis_client()
        queue_length = redis_client.llen("document_processing")

        # If status is queued but queue is empty, update to processing
        if task_data["status"] == "queued" and queue_length == 0:
            # Check if this is likely processing by looking at timing
            submitted_time = datetime.fromisoformat(task_data["submitted_at"])
            time_elapsed = (datetime.now() - submitted_time).total_seconds()

            if time_elapsed > 5:  # If more than 5 seconds, likely processing
                task_data["status"] = "processing"
                task_data["progress"] = {
                    "stage": "ai_extraction",
                    "estimated_remaining": "10-20 seconds",
                }
                await status_service.update_task_status(
                    task_id, "processing", task_data.get("progress")
                )

        response = TaskStatusResponse(
            task_id=task_data["task_id"],
            status=task_data["status"],
            progress=task_data.get("progress"),
            submitted_at=task_data["submitted_at"],
            completed_at=task_data.get("completed_at"),
            processing_time=task_data.get("processing_time"),
            error_message=task_data.get("error_message"),
        )

        logger.info(f"✅ Status retrieved for {task_id}: {response.status}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get task status for {task_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve task status: {str(e)}"
        )


@router.get("/result/{task_id}", response_model=TaskResultResponse)
async def get_task_result(
    task_id: str, status_service: TaskStatusService = Depends(get_task_status_service)
) -> TaskResultResponse:
    """
    Get extraction results for a completed task
    Lấy kết quả extraction cho task đã hoàn thành
    """
    try:
        logger.info(f"📊 Retrieving results for task: {task_id}")

        # Check task status first
        task_data = await status_service.get_task_status(task_id)

        if not task_data:
            logger.warning(f"⚠️ Task not found: {task_id}")
            raise HTTPException(
                status_code=404, detail=f"Task {task_id} not found or expired"
            )

        if task_data["status"] not in ["completed", "failed"]:
            logger.warning(
                f"⚠️ Task {task_id} not completed yet, status: {task_data['status']}"
            )
            raise HTTPException(
                status_code=202,  # Accepted but not ready
                detail=f"Task {task_id} is still {task_data['status']}. Please check status endpoint first.",
            )

        # Get result data
        result_data = await status_service.get_task_result(task_id)

        if not result_data:
            logger.warning(f"⚠️ No result data found for task: {task_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Result data for task {task_id} not found or expired",
            )

        response = TaskResultResponse(
            task_id=task_id,
            success=result_data.get("success", False),
            message=result_data.get("message", ""),
            processing_time=result_data.get("processing_time"),
            total_items_extracted=result_data.get("total_items_extracted"),
            ai_provider=result_data.get("ai_provider"),
            template_used=result_data.get("template_used"),
            industry=result_data.get("industry"),
            data_type=result_data.get("data_type"),
            raw_content=result_data.get("raw_content"),
            structured_data=result_data.get("structured_data"),
            extraction_metadata=result_data.get("extraction_metadata"),
            error=result_data.get("error"),
            error_details=result_data.get("error_details"),
        )

        logger.info(f"✅ Results retrieved for {task_id}: {response.success}")
        logger.info(f"   📊 Items extracted: {response.total_items_extracted}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get task result for {task_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve task result: {str(e)}"
        )
