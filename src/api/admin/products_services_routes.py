"""
Admin API routes for managing and extracting Products & Services data.
This file contains the logic from `extraction_routes.py` and implements the complete


COMPLETE ASYNC WORKFLOW / LUỒNG XỬ LÝ BẤT ĐỒNG BỘ HOÀN CHỈNH:
1. Backend uploads file to R2 st        # Handle background Qdrant upload if requested
        if request.upload_to_qdrant:
            logger.info("📤 Scheduling HYBRID STRATEGY Qdrant upload via background worker")

            # Debug log before serialization
            logger.info(f"📊 Pre-serialize debug:")
            logger.info(
                f"   📦 Products before serialize: {len(result.get('products', []))}"
            )
            logger.info(
                f"   🔧 Services before serialize: {len(result.get('services', []))}"
            )ts public URL
2. Backend calls /api/admin/companies/{company_id}/extract with R2 URL + metadata
3. API immediately enqueues ProductsExtractionTask to Redis queue
4. API returns task_id for status tracking
5. Background worker processes task:
   - AI Service processes file with industry-specific templates
   - AI Service extracts structured Products & Services data + content_for_embedding
   - AI Service generates embeddings using unified model
   - AI Service uploads vectors to Qdrant
6. Worker sends webhook callback to Backend when complete
"""

import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Path, Query
from pydantic import BaseModel, Field

from src.models.unified_models import Industry, Language
from src.services.ai_extraction_service import get_ai_service
from src.services.admin_service import get_admin_service, AdminService
from src.utils.logger import setup_logger
from src.middleware.auth import verify_internal_api_key
from src.queue.queue_dependencies import get_extraction_queue
from src.queue.task_models import ProductsExtractionTask, ExtractionTaskResponse

# ✅ ADDED: CRUD operations dependencies
from src.vector_store.qdrant_client import create_qdrant_manager
from src.services.embedding_service import get_embedding_service
from src.services.product_catalog_service import get_product_catalog_service  # ✅ ADD catalog service
from config.config import QDRANT_COLLECTION_NAME

import os

# ✅ ADDED: Hybrid Search Strategy dependencies
from src.services.embedding_service import EmbeddingService, get_embedding_service
from src.vector_store.qdrant_client import create_qdrant_manager
from qdrant_client.models import (
    PointStruct,
    UpdateStatus,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
)
import httpx

# ===== CRUD REQUEST/RESPONSE MODELS =====


class ProductCreateRequest(BaseModel):
    """Request to create new product with industry template and metadata"""

    # ===== CORE REQUIRED FIELDS =====
    name: str = Field(..., description="Product name - REQUIRED")
    type: str = Field(..., description="Product type - REQUIRED")
    category: str = Field(..., description="Product category - REQUIRED")
    description: str = Field(..., description="Product description - REQUIRED")
    price: str = Field(..., description="Product price/premium - REQUIRED")

    # ===== OPTIONAL BASIC FIELDS =====
    currency: Optional[str] = Field("VND", description="Currency - Optional")
    price_unit: Optional[str] = Field("per item", description="Price unit - Optional")
    sku: Optional[str] = Field(None, description="Product SKU - Optional")
    status: Optional[str] = Field("draft", description="Product status - Optional")
    tags: Optional[List[str]] = Field(default=[], description="Product tags - Optional")
    target_audience: Optional[List[str]] = Field(
        default=[], description="Target audience - Optional"
    )
    image_urls: Optional[List[str]] = Field(
        default=[], description="Product image URLs - Optional"
    )

    # ===== INDUSTRY TEMPLATE DATA =====
    industry_data: Optional[Dict[str, Any]] = Field(
        default={},
        description="Industry-specific data from template (industry, template, country, language, etc.)",
    )

    # ===== AI METADATA =====
    metadata: Optional[Dict[str, Any]] = Field(
        default={},
        description="AI metadata including content_for_embedding, ai_industry, ai_type, etc.",
    )

    # ===== ADDITIONAL FIELDS =====
    additional_fields: Optional[Dict[str, Any]] = Field(
        default={}, description="Additional custom fields from user input"
    )


class ProductUpdateRequest(BaseModel):
    """Request to completely replace product information - Only basic fields required"""

    # ===== CORE REQUIRED FIELDS (Frontend must provide) =====
    name: str = Field(..., description="Product name - REQUIRED")
    type: str = Field(..., description="Product type - REQUIRED")
    category: str = Field(..., description="Product category - REQUIRED")
    description: str = Field(..., description="Product description - REQUIRED")

    # Price field (can be premium, pricing, etc.)
    price: str = Field(..., description="Product price/premium - REQUIRED")

    # ===== OPTIONAL BASIC FIELDS =====
    sku: Optional[str] = Field(None, description="Product SKU - Optional")
    status: Optional[str] = Field(
        "available", description="Product status (available/out_of_stock) - Optional"
    )
    tags: Optional[List[str]] = Field(default=[], description="Product tags - Optional")
    target_audience: Optional[List[str]] = Field(
        default=[], description="Target audience - Optional"
    )
    image_urls: Optional[List[str]] = Field(
        default=[],
        description="Product image URLs - Optional (upload or external URLs)",
    )

    # ===== FLEXIBLE JSON FIELDS (Frontend can edit freely) =====
    additional_fields: Optional[Dict[str, Any]] = Field(
        default={},
        description="Additional product fields as JSON - Frontend can edit freely",
    )

    # ===== INDUSTRY TEMPLATE DATA =====
    industry_data: Optional[Dict[str, Any]] = Field(
        default={},
        description="Industry-specific data from template (industry, template, country, language, etc.)",
    )

    # ===== AI METADATA =====
    metadata: Optional[Dict[str, Any]] = Field(
        default={},
        description="AI metadata including content_for_embedding, ai_industry, ai_type, etc.",
    )

    # Note: company_id, file_id, qdrant_point_id are IMMUTABLE and preserved from original


class ServiceUpdateRequest(BaseModel):
    """Request to completely replace service information - Only basic fields required"""

    # ===== CORE REQUIRED FIELDS (Frontend must provide) =====
    name: str = Field(..., description="Service name - REQUIRED")
    type: str = Field(..., description="Service type - REQUIRED")
    category: str = Field(..., description="Service category - REQUIRED")
    description: str = Field(..., description="Service description - REQUIRED")

    # Price field
    price: str = Field(..., description="Service price/pricing - REQUIRED")

    # ===== OPTIONAL BASIC FIELDS =====
    sku: Optional[str] = Field(None, description="Service SKU - Optional")
    status: Optional[str] = Field(
        "available", description="Service status (available/unavailable) - Optional"
    )
    tags: Optional[List[str]] = Field(default=[], description="Service tags - Optional")
    target_audience: Optional[List[str]] = Field(
        default=[], description="Target audience - Optional"
    )
    image_urls: Optional[List[str]] = Field(
        default=[],
        description="Service image URLs - Optional (upload or external URLs)",
    )

    # ===== FLEXIBLE JSON FIELDS (Frontend can edit freely) =====
    additional_fields: Optional[Dict[str, Any]] = Field(
        default={},
        description="Additional service fields as JSON - Frontend can edit freely",
    )

    # Note: company_id, file_id, qdrant_point_id are IMMUTABLE and preserved from original


class CRUDResponse(BaseModel):
    """Standard CRUD response"""

    success: bool
    message: str
    item_id: str
    qdrant_point_id: Optional[str] = None
    changes_made: Dict[str, Any] = {}


class ProductServiceListResponse(BaseModel):
    """Response for listing products and services with Qdrant point IDs"""

    success: bool
    message: str
    company_id: str
    data: Dict[str, Any]
    total_count: int
    summary: Dict[str, Any]


# Initialize router and logger
router = APIRouter(tags=["Admin - Products & Services"])
logger = setup_logger(__name__)


# ===== REQUEST MODEL (EXACT COPY FROM extraction_routes.py) =====


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
    language: Language = Field(
        Language.AUTO_DETECT,
        description="Target language for extraction results (auto-detect recommended)",
    )
    upload_to_qdrant: bool = Field(
        False, description="Whether to upload results to Qdrant via background worker"
    )
    callback_url: Optional[str] = Field(
        None, description="Callback URL for async processing notifications"
    )


# ===== RESPONSE MODELS =====


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


# ===== DEPENDENCIES =====


async def get_extraction_service():
    """Get AI extraction service instance"""
    return get_ai_service()


# ===== MAIN EXTRACTION ENDPOINT =====


@router.post(
    "/companies/{companyId}/extract",
    response_model=ExtractionResponse,
    dependencies=[Depends(verify_internal_api_key)],
    summary="✅ HYBRID SEARCH STRATEGY: Extract & Categorize Products/Services with Individual Storage",
)
async def process_extraction(
    request: ExtractionRequest,
    background_tasks: BackgroundTasks,
    company_id: str = Path(..., alias="companyId"),
    ai_service=Depends(get_ai_service),
) -> ExtractionResponse:
    """
    🎯 **HYBRID SEARCH STRATEGY**: Extract Products & Services with AI Categorization + Individual Qdrant Storage

    **KEY FEATURES:**
    ✅ **AI Auto-Categorization**: AI tự động phân loại products/services dựa trên content, industry, company context
    ✅ **Individual Storage**: Mỗi product/service được lưu thành 1 point riêng biệt trong Qdrant
    ✅ **Metadata Filtering**: Rich metadata cho filtering (category, tags, target_audience, etc.)
    ✅ **Vector Search**: Semantic similarity search on embeddings
    ✅ **Enhanced Callback**: Callback chứa qdrant_point_id cho từng item để Backend quản lý
    ✅ **Individual CRUD**: Update/delete specific products/services by point ID

    **HYBRID SEARCH WORKFLOW:**
    1. ✅ AI extracts structured data với auto-categorization (generic prompts, không cần examples)
    2. ✅ Generate embeddings cho từng product/service riêng biệt
    3. ✅ Create individual Qdrant points với rich metadata payload
    4. ✅ Send callback với qdrant_point_id cho từng item
    5. 🎯 **Frontend có thể**:
       - Filter by metadata (category, industry, tags, target_audience)
       - Semantic search trong filtered results
       - CRUD operations on individual items
       - User feedback & item management

    **AI CATEGORIZATION APPROACH:**
    - **Generic Prompts**: AI tự phân loại dựa trên content, industry, company name
    - **No Examples**: Không cung cấp examples cụ thể để avoid bias cho industries khác
    - **Context-Aware**: AI sử dụng industry + company context để categorize chính xác
    - **Rich Metadata**: category, sub_category, tags, target_audience, coverage_type, service_type

    **METADATA FILTERING FIELDS:**
    - `category`: Main category (snake_case Vietnamese)
    - `sub_category`: Detailed sub-category
    - `tags`: Searchable tags array
    - `target_audience`: Target demographics
    - `coverage_type`: For insurance products
    - `service_type`: For service offerings
    - `industry`, `item_type`, `company_id`: System fields
    """
    start_time = datetime.now()

    try:
        logger.info(
            "🚀 HYBRID STRATEGY: Starting AI auto-categorization extraction with individual storage"
        )
        logger.info(f"   🔗 R2 URL: {request.r2_url}")
        logger.info(f"   🏭 Industry: {request.industry}")
        logger.info(f"   🏢 Company: {company_id}")
        logger.info(
            f"   📊 Target Categories: {request.target_categories or 'Auto (products + services)'}"
        )
        logger.info(
            f"   📄 File: {request.file_metadata.get('original_name', 'unknown')}"
        )
        logger.info(
            f"   🎯 Strategy: Metadata Filtering + Vector Search + Individual CRUD"
        )

        # Override company_id from path parameter
        request.company_id = company_id

        # Prepare metadata for AI service
        metadata = {
            **request.file_metadata,
            "industry": request.industry,
            "language": request.language,
            "extraction_timestamp": datetime.now().isoformat(),
        }

        # Call the implemented AI extraction service with auto-categorization
        logger.info("🤖 Calling AI extraction service with auto-categorization")
        result = await ai_service.extract_from_r2_url(
            r2_url=request.r2_url,
            metadata=metadata,
            company_info=request.company_info,
            target_categories=request.target_categories,
        )

        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()

        # Extract results from AI service response
        extraction_metadata = result.get("extraction_metadata", {})

        # Handle background Qdrant upload if requested
        if request.upload_to_qdrant:
            logger.info("� Scheduling Qdrant upload via background worker")

            # Debug log before serialization
            logger.info(f"� Pre-serialize debug:")
            logger.info(
                f"   📦 Products before serialize: {len(result.get('products', []))}"
            )
            logger.info(
                f"   � Services before serialize: {len(result.get('services', []))}"
            )

            # Serialize the result to JSON string for safe passing
            extraction_result_json = json.dumps(result)
            metadata_json = json.dumps(metadata)

            # Debug log after serialization
            logger.info(
                f"🔄 Serialized extraction result: {len(extraction_result_json)} chars"
            )

            background_tasks.add_task(
                schedule_hybrid_qdrant_upload_and_callback,
                extraction_result_json=extraction_result_json,
                metadata_json=metadata_json,
                company_id=company_id,
                industry=request.industry.value,
                language=request.language.value,
                callback_url=request.callback_url,
            )

        # Build successful response
        response = ExtractionResponse(
            success=True,
            message="✅ HYBRID STRATEGY: Auto-categorization extraction completed with individual item storage",
            # Core results / Kết quả chính
            raw_content=result.get("raw_content"),
            structured_data=result.get(
                "structured_data",
                {
                    "products": result.get("products", []),
                    "services": result.get("services", []),
                    "extraction_summary": result.get("extraction_summary", {}),
                },
            ),
            # Processing info / Thông tin xử lý
            template_used=extraction_metadata.get("template_used"),
            ai_provider=extraction_metadata.get("ai_provider"),
            industry=str(request.industry),
            data_type="hybrid_search_ready",  # Indicate hybrid search capabilities
            # Performance / Hiệu suất
            processing_time=processing_time,
            total_items_extracted=extraction_metadata.get("total_items", 0),
            # Full metadata / Metadata đầy đủ
            extraction_metadata={
                **extraction_metadata,
                "hybrid_search_enabled": True,
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
                "individual_item_storage": True,
                "ai_categorization": True,
            },
        )

        logger.info(
            "✅ HYBRID STRATEGY: Auto-categorization extraction completed successfully"
        )
        logger.info(f"   📋 Template: {response.template_used}")
        logger.info(f"   🤖 AI Provider: {response.ai_provider}")
        logger.info(f"   📊 Total Items: {response.total_items_extracted}")
        logger.info(f"   📦 Products: {len(result.get('products', []))}")
        logger.info(f"   🔧 Services: {len(result.get('services', []))}")
        logger.info(f"   ⏱️ Time: {processing_time:.2f}s")
        logger.info(
            f"   🎯 Ready for: Metadata Filtering + Vector Search + Individual CRUD"
        )

        return response

    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ Extraction failed: {str(e)}")

        # Return error response
        return ExtractionResponse(
            success=False,
            message="❌ HYBRID STRATEGY: Auto-categorization extraction failed",
            processing_time=processing_time,
            industry=str(request.industry),
            data_type="hybrid_search_failed",
            error=str(e),
            error_details={
                "r2_url": request.r2_url,
                "industry": str(request.industry),
                "target_categories": request.target_categories
                or ["products", "services"],
                "file_name": request.file_metadata.get("original_name", "unknown"),
                "error_type": type(e).__name__,
                "processing_time": processing_time,
                "hybrid_search_enabled": False,
            },
        )


# ===== HYBRID SEARCH STRATEGY BACKGROUND TASK =====


async def schedule_hybrid_qdrant_upload_and_callback(
    extraction_result_json: str,
    metadata_json: str,
    company_id: str,
    industry: str,
    language: str = "vi",
    callback_url: Optional[str] = None,
):
    """
    ✅ HYBRID SEARCH STRATEGY: Individual Product/Service Storage + AI Categorization + Enhanced Callback

    WORKFLOW:
    1. ✅ Deserialize extraction results (products + services with AI categorization)
    2. ✅ Generate embeddings for each individual item's content_for_embedding
    3. ✅ Create individual Qdrant points with rich metadata payload
    4. ✅ Upsert each product/service as separate point in Qdrant
    5. ✅ Send enhanced callback with qdrant_point_id for each item

    This enables:
    - Metadata Filtering: Filter by category, tags, target_audience, etc.
    - Vector Search: Semantic similarity search within filtered results
    - Individual CRUD: Update/delete specific products/services by point ID
    - User Feedback: Backend can track and modify individual items
    """
    start_time = datetime.now()
    logger.info(
        "� HYBRID STRATEGY: Starting individual product/service upload with AI categorization"
    )

    try:
        # === STEP 1: Initialize Dependencies ===
        embedding_service = get_embedding_service()
        qdrant_manager = create_qdrant_manager()
        # ✅ FIXED: Use unified collection for all companies
        collection_name = "multi_company_data"

        # === STEP 2: Deserialize Data ===
        extraction_result = json.loads(extraction_result_json)
        metadata = json.loads(metadata_json)

        products = extraction_result.get("products", [])
        services = extraction_result.get("services", [])

        logger.info(
            f"📊 Processing {len(products)} products and {len(services)} services"
        )
        logger.info(f"� Target collection: {collection_name}")
        logger.info(f"🏭 Industry: {industry}")
        logger.info(f"🏢 Company: {company_id}")

        # === STEP 3: Process Each Item Individually ===
        points_to_upsert = []
        processed_products = []
        processed_services = []

        # Process all items (products + services)
        all_items = [("product", p) for p in products] + [
            ("service", s) for s in services
        ]

        for item_type, item in all_items:
            try:
                # Get content for embedding (required for vector search)
                content_to_embed = item.get("content_for_embedding")
                if not content_to_embed:
                    logger.warning(
                        f"⚠️ Skipping {item_type} '{item.get('name', 'unknown')}' - missing content_for_embedding"
                    )
                    continue

                # Generate embedding for this specific item
                logger.debug(
                    f"🧠 Generating embedding for {item_type}: {item.get('name', 'unknown')}"
                )
                embedding = await embedding_service.generate_embeddings(
                    [content_to_embed]
                )

                if not embedding or not embedding[0]:
                    logger.warning(
                        f"⚠️ Skipping {item_type} '{item.get('name', 'unknown')}' - empty embedding"
                    )
                    continue

                # Create unique point ID for this item
                point_id = str(uuid.uuid4())

                # Build rich metadata payload for hybrid search
                payload = {
                    # === Core Identification ===
                    "document_type": "structured_item",
                    "item_type": item_type,  # "product" or "service"
                    "company_id": company_id,
                    "file_id": metadata.get(
                        "file_id", metadata.get("original_name", "unknown")
                    ),
                    # === AI Categorization Fields (for Metadata Filtering) ===
                    "category": item.get("category", "uncategorized"),
                    "sub_category": item.get("sub_category", ""),
                    "tags": item.get("tags", []),
                    "target_audience": item.get("target_audience", []),
                    # === Item-specific categorization ===
                    "coverage_type": (
                        item.get("coverage_type", []) if item_type == "product" else []
                    ),
                    "service_type": (
                        item.get("service_type", []) if item_type == "service" else []
                    ),
                    # === Business Context ===
                    "industry": industry,
                    "language": language,
                    "company_name": metadata.get("company_name", ""),
                    # === Complete Item Data ===
                    "item_name": item.get("name", ""),
                    "item_description": item.get("description", ""),
                    "item_data": item,  # Full structured data
                    # === File Context ===
                    "file_metadata": metadata,
                    "extraction_timestamp": datetime.now().isoformat(),
                    # === Search Optimization ===
                    "searchable_content": f"{item.get('name', '')} {item.get('description', '')} {' '.join(item.get('tags', []))}",
                }

                # Create Qdrant point
                point = PointStruct(id=point_id, vector=embedding[0], payload=payload)
                points_to_upsert.append(point)

                # Prepare item for callback (with Qdrant ID)
                item_with_qdrant_id = item.copy()
                item_with_qdrant_id["qdrant_point_id"] = point_id
                item_with_qdrant_id["collection_name"] = collection_name

                if item_type == "product":
                    processed_products.append(item_with_qdrant_id)
                else:
                    processed_services.append(item_with_qdrant_id)

                logger.debug(
                    f"✅ Prepared {item_type} '{item.get('name', 'unknown')}' for upload (Point ID: {point_id})"
                )

            except Exception as item_error:
                logger.error(
                    f"❌ Failed to process {item_type} '{item.get('name', 'unknown')}': {item_error}"
                )
                continue

        # === STEP 4: Bulk Upsert to Qdrant ===
        if points_to_upsert:
            logger.info(
                f"📤 Upserting {len(points_to_upsert)} individual points to Qdrant collection '{collection_name}'"
            )

            # Ensure collection exists
            qdrant_manager.ensure_collection_exists(collection_name)

            # Upsert all points
            upsert_result = qdrant_manager.client.upsert(
                collection_name=collection_name, points=points_to_upsert
            )
            logger.info(
                f"✅ Successfully upserted {len(points_to_upsert)} points to Qdrant"
            )

        else:
            logger.warning("⚠️ No points were generated for Qdrant upload")
            upsert_result = None

        # === STEP 5: Send Enhanced Callback ===
        processing_time = (datetime.now() - start_time).total_seconds()

        if callback_url:
            callback_payload = {
                "event": "ai.extraction.completed",
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                # === Core Data ===
                "company_id": company_id,
                "file_metadata": metadata,
                "collection_name": collection_name,
                # === Processed Items with Qdrant IDs ===
                "data": {
                    "products": processed_products,  # Each includes qdrant_point_id
                    "services": processed_services,  # Each includes qdrant_point_id
                },
                # === Processing Summary ===
                "summary": {
                    "total_products_processed": len(processed_products),
                    "total_services_processed": len(processed_services),
                    "total_points_created": len(points_to_upsert),
                    "processing_time_seconds": processing_time,
                    "industry": industry,
                    "language": language,
                },
                # === Hybrid Search Capabilities ===
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
                    "collection_name": collection_name,
                },
            }

            # Send callback
            try:
                import aiohttp
                import json
                import os

                # Simple webhook secret as header (no signature generation)
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
                        json=callback_payload,
                        timeout=aiohttp.ClientTimeout(total=30),
                        headers=headers,
                    ) as response:
                        if response.status == 200:
                            logger.info("✅ Enhanced callback sent successfully")
                        else:
                            logger.warning(
                                f"⚠️ Callback response status: {response.status}"
                            )

            except Exception as callback_error:
                logger.error(f"❌ Failed to send callback: {callback_error}")

        # === Final Summary ===
        logger.info("🎉 HYBRID STRATEGY: Upload completed successfully")
        logger.info(f"   📊 Products processed: {len(processed_products)}")
        logger.info(f"   🔧 Services processed: {len(processed_services)}")
        logger.info(f"   📤 Qdrant points created: {len(points_to_upsert)}")
        logger.info(f"   🗄️ Collection: {collection_name}")
        logger.info(f"   ⏱️ Total time: {processing_time:.2f}s")
        logger.info(
            f"   � Ready for hybrid search (metadata filtering + vector similarity)"
        )

    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ HYBRID STRATEGY: Upload failed after {processing_time:.2f}s")
        logger.error(f"❌ Error: {str(e)}")
        logger.error(f"❌ Company: {company_id}, Industry: {industry}")

        # Send error callback
        if callback_url:
            error_callback = {
                "event": "ai.extraction.failed",
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "company_id": company_id,
                "error": str(e),
                "processing_time_seconds": processing_time,
            }

            try:
                import aiohttp
                import json
                import os

                # Simple webhook secret as header (no signature generation)
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
                        timeout=aiohttp.ClientTimeout(total=10),
                        headers=headers,
                    ) as response:
                        logger.info("📞 Error callback sent")
            except Exception as callback_error:
                logger.error(f"❌ Failed to send error callback: {callback_error}")


# ===== ENHANCED CRUD for Products & Services =====


@router.get(
    "/companies/{company_id}/products-services",
    response_model=ProductServiceListResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def get_all_products_services(
    company_id: str = Path(..., description="Company ID"),
    limit: int = Query(100, description="Maximum number of items to return"),
    offset: int = Query(0, description="Number of items to skip"),
):
    """
    📋 Get ALL Products & Services for a company with Qdrant Point IDs

    Returns complete list of products and services with their Qdrant point IDs
    for easy management and CRUD operations.
    """
    try:
        logger.info(f"📋 Getting all products & services for company {company_id}")

        # Initialize Qdrant manager
        qdrant_manager = create_qdrant_manager()

        # Search for all company items in unified collection
        collection_name = QDRANT_COLLECTION_NAME or "multi_company_data"

        # Get all points for this company (products and services)
        points, _ = qdrant_manager.client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="company_id", match=MatchValue(value=company_id)
                    ),
                    FieldCondition(
                        key="content_type",
                        match=MatchAny(any=["extracted_product", "extracted_service"]),
                    ),
                ]
            ),
            limit=limit + offset,  # Get more to handle offset
            with_payload=True,
            with_vectors=False,
        )

        # Separate products and services
        products = []
        services = []

        for point in points[offset : offset + limit]:  # Apply offset/limit
            payload = point.payload
            content_type = payload.get("content_type")

            item_data = {
                "qdrant_point_id": point.id,
                "item_id": payload.get(
                    "product_id"
                    if content_type == "extracted_product"
                    else "service_id"
                ),
                "name": payload.get(
                    "product_name"
                    if content_type == "extracted_product"
                    else "service_name"
                ),
                "type": payload.get(
                    "product_type"
                    if content_type == "extracted_product"
                    else "service_type_primary"
                ),
                "category": payload.get("category"),
                "description": payload.get("description"),
                "price": payload.get(
                    "price", payload.get("premium", payload.get("pricing"))
                ),
                "sku": payload.get("sku"),
                "status": payload.get("status", "available"),
                "tags": payload.get("tags", []),
                "target_audience": payload.get("target_audience", []),
                "image_urls": payload.get("image_urls", []),
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
                "file_id": payload.get("file_id"),
                "additional_fields": {
                    k: v
                    for k, v in payload.items()
                    if k
                    not in [
                        "company_id",
                        "qdrant_point_id",
                        "content_type",
                        "product_id",
                        "service_id",
                        "product_name",
                        "service_name",
                        "product_type",
                        "service_type_primary",
                        "category",
                        "description",
                        "price",
                        "premium",
                        "pricing",
                        "sku",
                        "status",
                        "tags",
                        "target_audience",
                        "image_urls",
                        "created_at",
                        "updated_at",
                        "file_id",
                    ]
                },
            }

            if content_type == "extracted_product":
                products.append(item_data)
            else:
                services.append(item_data)

        logger.info(
            f"✅ Retrieved {len(products)} products and {len(services)} services"
        )

        return ProductServiceListResponse(
            success=True,
            message=f"Retrieved all products and services for company {company_id}",
            company_id=company_id,
            data={"products": products, "services": services},
            total_count=len(products) + len(services),
            summary={
                "total_products": len(products),
                "total_services": len(services),
                "collection_name": collection_name,
                "offset": offset,
                "limit": limit,
            },
        )

    except Exception as e:
        logger.error(f"❌ Failed to get products & services: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve data: {str(e)}"
        )


@router.put(
    "/companies/{company_id}/products/{qdrant_point_id}",
    response_model=CRUDResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def update_product(
    request: ProductUpdateRequest,
    company_id: str = Path(..., description="Company ID"),
    qdrant_point_id: str = Path(
        ..., description="Qdrant Point ID from listing endpoint"
    ),
):
    """
    🔄 COMPLETE PRODUCT REPLACEMENT: Direct Qdrant Point ID approach

    Strategy:
    1. Receive qdrant_point_id directly from Backend (no search needed)
    2. COMPLETELY REPLACE all product data with new payload
    3. Re-generate embedding from scratch with new content
    4. Update Qdrant with same Point ID but fresh data

    This ensures maximum performance and data consistency.
    """
    try:
        logger.info(
            f"🔄 Completely replacing product at Qdrant point {qdrant_point_id} for company {company_id}"
        )

        # Initialize services
        qdrant_manager = create_qdrant_manager()
        embedding_service = get_embedding_service()
        collection_name = QDRANT_COLLECTION_NAME or "multi_company_data"

        # No search needed - work directly with the Qdrant Point ID
        logger.info(f"🎯 Direct operation using Qdrant Point ID: {qdrant_point_id}")

        # 🚨 COMPLETE REPLACEMENT: Build entirely new payload from scratch
        logger.info(f"🆕 Building fresh product payload from backend data")

        # Build completely new payload
        fresh_payload = {
            # ===== SYSTEM FIELDS =====
            "company_id": company_id,
            "content_type": "extracted_product",
            "updated_at": datetime.now().isoformat(),
            # ===== CORE REQUIRED FIELDS (COMPLETELY REPLACED) =====
            "product_name": request.name,
            "product_type": request.type,
            "category": request.category,
            "description": request.description,
            "price": request.price,  # Unified price field
            # ===== OPTIONAL BASIC FIELDS =====
            "sku": request.sku,
            "status": request.status or "available",
            "tags": request.tags or [],
            "target_audience": request.target_audience or [],
            "image_urls": request.image_urls or [],
            # ===== INDUSTRY TEMPLATE DATA =====
            **request.industry_data,
            # ===== FLEXIBLE ADDITIONAL FIELDS =====
            **request.additional_fields,
        }

        # Generate content for embedding from metadata or fallback
        if request.metadata and request.metadata.get("content_for_embedding"):
            fresh_content = request.metadata["content_for_embedding"]
        else:
            # Fallback: create content from basic fields
            fresh_content = f"""
{fresh_payload['product_name']} - {fresh_payload['product_type']}
{fresh_payload['description']}
Danh mục: {fresh_payload['category']}
Giá: {fresh_payload['price']}
Trạng thái: {fresh_payload['status']}
SKU: {fresh_payload.get('sku', 'N/A')}
Đối tượng: {', '.join(fresh_payload['target_audience'])}
Từ khóa: {', '.join(fresh_payload['tags'])}
            """.strip()

        # Generate fresh embedding
        logger.info(f"🤖 Generating fresh embedding for completely new content")
        fresh_embedding = await embedding_service.generate_embedding(fresh_content)

        # Add content fields to payload
        fresh_payload["content"] = fresh_content
        fresh_payload["searchable_text"] = (
            f"{fresh_payload['product_name']} {fresh_payload['product_type']} "
            f"{fresh_payload['description']} {fresh_payload['category']} "
            f"{' '.join(fresh_payload['tags'])} {' '.join(fresh_payload['target_audience'])}"
        )

        # COMPLETELY REPLACE the point in Qdrant (same ID, fresh everything)
        logger.info(
            f"💾 Replacing Qdrant point {qdrant_point_id} with completely fresh data"
        )

        from qdrant_client.models import PointStruct

        point = PointStruct(
            id=qdrant_point_id,  # Use the exact point ID from Backend
            vector=fresh_embedding,
            payload=fresh_payload,
        )

        operation_info = qdrant_manager.client.upsert(
            collection_name=collection_name, points=[point], wait=True
        )

        logger.info(
            f"✅ Product at point {qdrant_point_id} COMPLETELY REPLACED successfully"
        )
        logger.info(f"   📦 New name: {fresh_payload['product_name']}")
        logger.info(f"   🏷️ New category: {fresh_payload['category']}")
        logger.info(f"   💰 New price: {fresh_payload['price']}")
        logger.info(f"   📊 New tags: {', '.join(fresh_payload['tags'])}")
        logger.info(f"   🎯 Fresh embedding generated and stored")

        return CRUDResponse(
            success=True,
            message="Product completely replaced successfully",
            item_id="N/A",  # Backend manages item_id mapping
            qdrant_point_id=qdrant_point_id,
            changes_made={
                "operation": "complete_replacement",
                "new_name": fresh_payload["product_name"],
                "fresh_embedding": True,
                "fresh_content": True,
                "industry_template": (
                    request.industry_data.get("template", "N/A")
                    if request.industry_data
                    else "N/A"
                ),
                "industry": (
                    request.industry_data.get("industry", "N/A")
                    if request.industry_data
                    else "N/A"
                ),
                "required_fields_updated": [
                    "name",
                    "type",
                    "category",
                    "description",
                    "price",
                ],
                "optional_fields_count": len(request.additional_fields),
                "industry_fields_count": (
                    len(request.industry_data) if request.industry_data else 0
                ),
                "metadata_provided": bool(
                    request.metadata and request.metadata.get("content_for_embedding")
                ),
                "additional_fields_keys": (
                    list(request.additional_fields.keys())
                    if request.additional_fields
                    else []
                ),
            },
        )

    except Exception as e:
        logger.error(f"❌ Product replacement error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Product replacement failed: {str(e)}"
        )


@router.put(
    "/companies/{company_id}/services/{qdrant_point_id}",
    response_model=CRUDResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def update_service(
    request: ServiceUpdateRequest,
    company_id: str = Path(..., description="Company ID"),
    qdrant_point_id: str = Path(
        ..., description="Qdrant Point ID from listing endpoint"
    ),
):
    """
    🔄 COMPLETE SERVICE REPLACEMENT: Direct Qdrant Point ID approach

    Strategy:
    1. Receive qdrant_point_id directly from Backend (no search needed)
    2. COMPLETELY REPLACE all service data with new payload
    3. Re-generate embedding from scratch with new content
    4. Update Qdrant with same Point ID but fresh data

    This ensures maximum performance and data consistency.
    """
    try:
        logger.info(
            f"🔄 Completely replacing service at Qdrant point {qdrant_point_id} for company {company_id}"
        )

        # Initialize services
        qdrant_manager = create_qdrant_manager()
        embedding_service = get_embedding_service()
        collection_name = QDRANT_COLLECTION_NAME or "multi_company_data"

        # No search needed - work directly with the Qdrant Point ID
        logger.info(f"🎯 Direct operation using Qdrant Point ID: {qdrant_point_id}")

        # 🚨 COMPLETE REPLACEMENT: Build entirely new payload from scratch
        logger.info(f"🆕 Building fresh service payload from backend data")

        # Build completely new payload
        fresh_payload = {
            # ===== SYSTEM FIELDS =====
            "company_id": company_id,
            "content_type": "extracted_service",
            "updated_at": datetime.now().isoformat(),
            # ===== CORE REQUIRED FIELDS (COMPLETELY REPLACED) =====
            "service_name": request.name,
            "service_type_primary": request.type,
            "category": request.category,
            "description": request.description,
            "price": request.price,  # Unified price field
            # ===== OPTIONAL BASIC FIELDS =====
            "sku": request.sku,
            "status": request.status or "available",
            "tags": request.tags or [],
            "target_audience": request.target_audience or [],
            "image_urls": request.image_urls or [],
            # ===== FLEXIBLE ADDITIONAL FIELDS =====
            **request.additional_fields,
        }

        # Generate completely fresh content for embedding
        fresh_content = f"""
{fresh_payload['service_name']} - {fresh_payload['service_type_primary']}
{fresh_payload['description']}
Danh mục: {fresh_payload['category']}
Giá: {fresh_payload['price']}
Trạng thái: {fresh_payload['status']}
SKU: {fresh_payload.get('sku', 'N/A')}
Đối tượng: {', '.join(fresh_payload['target_audience'])}
Từ khóa: {', '.join(fresh_payload['tags'])}
        """.strip()

        # Generate fresh embedding
        logger.info(f"🤖 Generating fresh embedding for completely new content")
        fresh_embedding = await embedding_service.generate_embedding(fresh_content)

        # Add content fields to payload
        fresh_payload["content"] = fresh_content
        fresh_payload["searchable_text"] = (
            f"{fresh_payload['service_name']} {fresh_payload['service_type_primary']} "
            f"{fresh_payload['description']} {fresh_payload['category']} "
            f"{' '.join(fresh_payload['tags'])} {' '.join(fresh_payload['target_audience'])}"
        )

        # COMPLETELY REPLACE the point in Qdrant (same ID, fresh everything)
        logger.info(
            f"💾 Replacing Qdrant point {qdrant_point_id} with completely fresh data"
        )

        from qdrant_client.models import PointStruct

        point = PointStruct(
            id=qdrant_point_id,  # Use the exact point ID from Backend
            vector=fresh_embedding,
            payload=fresh_payload,
        )

        operation_info = qdrant_manager.client.upsert(
            collection_name=collection_name, points=[point], wait=True
        )

        logger.info(
            f"✅ Service at point {qdrant_point_id} COMPLETELY REPLACED successfully"
        )
        logger.info(f"   🔧 New name: {fresh_payload['service_name']}")
        logger.info(f"   🏷️ New category: {fresh_payload['category']}")
        logger.info(f"   💰 New price: {fresh_payload['price']}")
        logger.info(f"   📊 New tags: {', '.join(fresh_payload['tags'])}")
        logger.info(f"   🎯 Fresh embedding generated and stored")

        return CRUDResponse(
            success=True,
            message="Service completely replaced successfully",
            item_id="N/A",  # Backend manages item_id mapping
            qdrant_point_id=qdrant_point_id,
            changes_made={
                "operation": "complete_replacement",
                "new_name": fresh_payload["service_name"],
                "fresh_embedding": True,
                "fresh_content": True,
                "required_fields_updated": [
                    "name",
                    "type",
                    "category",
                    "description",
                    "price",
                ],
                "optional_fields_count": len(request.additional_fields),
                "additional_fields_keys": (
                    list(request.additional_fields.keys())
                    if request.additional_fields
                    else []
                ),
            },
        )

    except Exception as e:
        logger.error(f"❌ Service replacement error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Service replacement failed: {str(e)}"
        )


@router.delete(
    "/companies/{company_id}/products/{product_id}",
    response_model=CRUDResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def delete_product(
    company_id: str = Path(..., description="Company ID"),
    product_id: str = Path(
        ..., description="Product ID from Backend (consistent with create/update)"
    ),
):
    """
    🗑️ PRODUCT DELETION: Complete cleanup from all storage systems (MongoDB + Qdrant)

    Strategy:
    1. Receive product_id directly from Backend (consistent with create/update endpoints)
    2. Delete from MongoDB catalog service first
    3. Find and delete all associated Qdrant points by product_id
    4. Return comprehensive deletion summary

    This ensures complete data consistency across all storage systems and is easier for Backend.
    """
    try:
        logger.info(
            f"🗑️ Deleting product {product_id} for company {company_id} from ALL storage systems"
        )

        # Initialize services
        qdrant_manager = create_qdrant_manager()
        catalog_service = await get_product_catalog_service()  # ✅ Add catalog service
        collection_name = QDRANT_COLLECTION_NAME or "multi_company_data"

        # Step 1: Delete from MongoDB catalog service first
        catalog_deleted = False
        try:
            logger.info(f"�️ Deleting from MongoDB catalog: {product_id}")

            # Delete from catalog service (MongoDB)
            delete_result = await catalog_service.collection.delete_one({
                "product_id": product_id,
                "company_id": company_id
            })

            if delete_result.deleted_count > 0:
                catalog_deleted = True
                logger.info(f"✅ Deleted from MongoDB catalog: {product_id}")
            else:
                logger.warning(f"⚠️ Product not found in MongoDB catalog: {product_id}")

        except Exception as catalog_error:
            logger.error(f"❌ Failed to delete from catalog: {catalog_error}")
            # Continue with Qdrant deletion even if catalog deletion fails

        # Step 2: Find and delete from Qdrant by product_id
        qdrant_deleted_count = 0
        try:
            logger.info(f"🎯 Searching and deleting from Qdrant by product_id: {product_id}")

            # Use filter to find all points with this product_id
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            filter_condition = Filter(
                must=[
                    FieldCondition(key="company_id", match=MatchValue(value=company_id)),
                    FieldCondition(key="product_id", match=MatchValue(value=product_id)),
                    FieldCondition(key="content_type", match=MatchValue(value="extracted_product"))
                ]
            )

            # Delete by filter (more efficient than scroll + delete)
            delete_result = qdrant_manager.client.delete(
                collection_name=collection_name,
                points_selector=filter_condition,
                wait=True,
            )

            # Note: Qdrant delete by filter doesn't return count, so we assume success if no exception
            qdrant_deleted_count = 1  # Assume at least 1 point deleted
            logger.info(f"✅ Deleted from Qdrant using filter: {product_id}")

        except Exception as qdrant_error:
            logger.error(f"❌ Failed to delete from Qdrant: {qdrant_error}")

        # Summary
        success = catalog_deleted or qdrant_deleted_count > 0
        message = f"Product {product_id} deletion completed"

        if catalog_deleted and qdrant_deleted_count > 0:
            message += " (removed from both MongoDB catalog and Qdrant)"
        elif catalog_deleted:
            message += " (removed from MongoDB catalog only)"
        elif qdrant_deleted_count > 0:
            message += " (removed from Qdrant only)"
        else:
            message += " (not found in any storage system)"

        logger.info(f"✅ {message}")

        return CRUDResponse(
            success=success,
            message=message,
            item_id=product_id,  # Return the product_id for reference
            qdrant_point_id=None,  # Not using qdrant_point_id anymore
            changes_made={
                "operation": "complete_deletion",
                "product_id": product_id,
                "company_id": company_id,
                "mongodb_catalog_deleted": catalog_deleted,
                "qdrant_points_deleted": qdrant_deleted_count,
                "storage_systems_cleaned": [
                    system for system, deleted in [
                        ("mongodb_catalog", catalog_deleted),
                        ("qdrant", qdrant_deleted_count > 0)
                    ] if deleted
                ]
            },
        )

    except Exception as e:
        logger.error(f"❌ Product deletion error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Product deletion failed: {str(e)}"
        )


@router.delete(
    "/companies/{company_id}/services/{service_id}",
    response_model=CRUDResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def delete_service(
    company_id: str = Path(..., description="Company ID"),
    service_id: str = Path(
        ..., description="Service ID from Backend (consistent with create/update)"
    ),
):
    """
    🗑️ SERVICE DELETION: Complete cleanup from all storage systems (MongoDB + Qdrant)

    Strategy:
    1. Receive service_id directly from Backend (consistent with create/update endpoints)
    2. Delete from MongoDB catalog service first
    3. Find and delete all associated Qdrant points by service_id
    4. Return comprehensive deletion summary

    This ensures complete data consistency across all storage systems and is easier for Backend.
    """
    try:
        logger.info(
            f"🗑️ Deleting service {service_id} for company {company_id} from ALL storage systems"
        )

        # Initialize services
        qdrant_manager = create_qdrant_manager()
        catalog_service = await get_product_catalog_service()  # ✅ Add catalog service
        collection_name = QDRANT_COLLECTION_NAME or "multi_company_data"

        # Step 1: Delete from MongoDB catalog service first
        catalog_deleted = False
        try:
            logger.info(f"🗂️ Deleting from MongoDB catalog: {service_id}")

            # Delete from catalog service (MongoDB)
            delete_result = await catalog_service.collection.delete_one({
                "service_id": service_id,
                "company_id": company_id
            })

            if delete_result.deleted_count > 0:
                catalog_deleted = True
                logger.info(f"✅ Deleted from MongoDB catalog: {service_id}")
            else:
                logger.warning(f"⚠️ Service not found in MongoDB catalog: {service_id}")

        except Exception as catalog_error:
            logger.error(f"❌ Failed to delete from catalog: {catalog_error}")
            # Continue with Qdrant deletion even if catalog deletion fails

        # Step 2: Find and delete from Qdrant by service_id
        qdrant_deleted_count = 0
        try:
            logger.info(f"🎯 Searching and deleting from Qdrant by service_id: {service_id}")

            # Use filter to find all points with this service_id
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            filter_condition = Filter(
                must=[
                    FieldCondition(key="company_id", match=MatchValue(value=company_id)),
                    FieldCondition(key="service_id", match=MatchValue(value=service_id)),
                    FieldCondition(key="content_type", match=MatchValue(value="extracted_service"))
                ]
            )

            # Delete by filter (more efficient than scroll + delete)
            delete_result = qdrant_manager.client.delete(
                collection_name=collection_name,
                points_selector=filter_condition,
                wait=True,
            )

            # Note: Qdrant delete by filter doesn't return count, so we assume success if no exception
            qdrant_deleted_count = 1  # Assume at least 1 point deleted
            logger.info(f"✅ Deleted from Qdrant using filter: {service_id}")

        except Exception as qdrant_error:
            logger.error(f"❌ Failed to delete from Qdrant: {qdrant_error}")

        # Summary
        success = catalog_deleted or qdrant_deleted_count > 0
        message = f"Service {service_id} deletion completed"

        if catalog_deleted and qdrant_deleted_count > 0:
            message += " (removed from both MongoDB catalog and Qdrant)"
        elif catalog_deleted:
            message += " (removed from MongoDB catalog only)"
        elif qdrant_deleted_count > 0:
            message += " (removed from Qdrant only)"
        else:
            message += " (not found in any storage system)"

        logger.info(f"✅ {message}")

        return CRUDResponse(
            success=success,
            message=message,
            item_id=service_id,  # Return the service_id for reference
            qdrant_point_id=None,  # Not using qdrant_point_id anymore
            changes_made={
                "operation": "complete_deletion",
                "service_id": service_id,
                "company_id": company_id,
                "mongodb_catalog_deleted": catalog_deleted,
                "qdrant_points_deleted": qdrant_deleted_count,
                "storage_systems_cleaned": [
                    system for system, deleted in [
                        ("mongodb_catalog", catalog_deleted),
                        ("qdrant", qdrant_deleted_count > 0)
                    ] if deleted
                ]
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Service deletion error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Service deletion failed: {str(e)}"
        )


# ===== FILE DELETION WITH PRODUCTS & SERVICES =====


@router.delete(
    "/companies/{company_id}/extractions/{file_id}",
    dependencies=[Depends(verify_internal_api_key)],
)
async def delete_file_with_products_services(
    company_id: str = Path(..., description="Company ID"),
    file_id: str = Path(
        ..., description="File ID to delete with all its products and services"
    ),
    admin_service: AdminService = Depends(get_admin_service),
):
    """
    Delete a file and ALL its associated products & services from ALL storage systems
    Xóa file và TẤT CẢ products & services liên quan từ TẤT CẢ hệ thống lưu trữ

    ⚠️ ENDPOINT CHANGED TO AVOID CONFLICT: /companies/{company_id}/extractions/{file_id}
    ⚠️ ĐÃ THAY ĐỔI ENDPOINT ĐỂ TRÁNH XUNG ĐỘT: /companies/{company_id}/extractions/{file_id}

    This endpoint will now:
    1. Delete from MongoDB catalog service (all products/services from this file_id)
    2. Delete from Qdrant (all vector embeddings and metadata)
    3. Complete cleanup across all storage systems

    Endpoint này giờ sẽ:
    1. Xóa từ MongoDB catalog service (tất cả products/services từ file_id này)
    2. Xóa từ Qdrant (tất cả vector embeddings và metadata)
    3. Dọn dẹp hoàn toàn trên tất cả hệ thống lưu trữ
    """
    logger.info(
        f"🗑️ Request to delete file {file_id} with all products/services for company {company_id} from ALL storage systems"
    )

    try:
        # Initialize services
        ai_service = get_ai_service()
        catalog_service = await get_product_catalog_service()  # ✅ Add catalog service

        # Use unified collection name consistently
        UNIFIED_COLLECTION_NAME = "multi_company_data"

        # Step 1: Delete from MongoDB catalog service first (by file_id if available)
        catalog_deleted_count = 0
        try:
            logger.info(f"🗂️ Deleting from MongoDB catalog by file_id: {file_id}")

            # Delete all items with this file_id from catalog service
            # Note: This assumes file_id is stored in catalog documents, might need adjustment
            delete_result = await catalog_service.collection.delete_many({
                "company_id": company_id,
                "raw_ai_data.file_id": file_id  # Assuming file_id is stored in raw_ai_data
            })

            catalog_deleted_count = delete_result.deleted_count
            if catalog_deleted_count > 0:
                logger.info(f"✅ Deleted {catalog_deleted_count} items from MongoDB catalog")
            else:
                logger.info(f"📭 No items found in MongoDB catalog for file {file_id}")

        except Exception as catalog_error:
            logger.error(f"❌ Failed to delete from catalog: {catalog_error}")
            # Continue with Qdrant deletion even if catalog deletion fails

        # Step 2: Delete all points with file_id filter from Qdrant
        # This includes products, services, and file metadata
        deleted_count = await ai_service.delete_file_from_qdrant(
            collection_name=UNIFIED_COLLECTION_NAME, file_id=file_id
        )

        # Step 3: Also delete with company_id + file_id filter for extra safety
        # Some points might have different metadata structure
        try:
            additional_deleted = await ai_service.delete_file_with_company_filter(
                collection_name=UNIFIED_COLLECTION_NAME,
                company_id=company_id,
                file_id=file_id,
            )

            if additional_deleted > 0:
                logger.info(
                    f"🧹 Deleted {additional_deleted} additional points with company+file filter"
                )
                deleted_count += additional_deleted

        except Exception as additional_delete_error:
            logger.warning(
                f"⚠️ Additional deletion with company filter failed: {additional_delete_error}"
            )
            # Continue even if additional deletion fails

        # Response based on deletion results
        total_deleted = catalog_deleted_count + deleted_count
        if total_deleted > 0:
            logger.info(
                f"✅ Successfully deleted file {file_id} and all associated data from ALL storage systems"
            )
            logger.info(f"   📊 MongoDB catalog items deleted: {catalog_deleted_count}")
            logger.info(f"   📊 Qdrant points deleted: {deleted_count}")
            logger.info(f"   📊 Total items deleted: {total_deleted}")
            logger.info(f"   🏢 Company: {company_id}")
            logger.info(f"   📄 File: {file_id}")
            logger.info(f"   🗄️ Collections: MongoDB catalog + {UNIFIED_COLLECTION_NAME}")

            return {
                "success": True,
                "message": f"File {file_id} and all associated products/services deleted successfully from ALL storage systems",
                "deleted_points": deleted_count,
                "deleted_catalog_items": catalog_deleted_count,
                "total_deleted": total_deleted,
                "collection": UNIFIED_COLLECTION_NAME,
                "company_id": company_id,
                "file_id": file_id,
                "details": {
                    "mongodb_catalog_deleted": catalog_deleted_count,
                    "qdrant_points_deleted": deleted_count,
                    "storage_systems_cleaned": ["mongodb_catalog", "qdrant"],
                    "complete_cleanup": True,
                },
            }
        else:
            # File not found in any storage system
            logger.warning(
                f"📭 File {file_id} not found in any storage system for company {company_id}"
            )
            return {
                "success": False,
                "message": f"File {file_id} with extraction data not found in company {company_id}",
                "deleted_points": deleted_count,
                "deleted_catalog_items": catalog_deleted_count,
                "total_deleted": total_deleted,
                "collection": UNIFIED_COLLECTION_NAME,
                "company_id": company_id,
                "file_id": file_id,
                "error": "EXTRACTION_DATA_NOT_FOUND",
                "details": "No extraction data (products/services) found for this file in any storage system. File may have been already deleted, never processed for extraction, or only contains raw content.",
            }

    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error(
            f"❌ Failed to delete file {file_id} with products/services: {str(e)}"
        )
        import traceback

        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete file with products/services: {str(e)}",
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


# ===== PRODUCT CREATE ENDPOINT =====


@router.post(
    "/companies/{company_id}/products/{product_id}",
    response_model=CRUDResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def create_product(
    request: ProductCreateRequest,
    company_id: str = Path(..., description="Company ID"),
    product_id: str = Path(..., description="Product ID from Backend"),
):
    """
    🆕 CREATE NEW PRODUCT: Generate Qdrant Point ID approach

    Strategy:
    1. Receive product_id from Backend (new product creation)
    2. Generate new qdrant_point_id
    3. Create vector embeddings from metadata.content_for_embedding
    4. Store in Qdrant with full payload including industry_data
    5. Return qdrant_point_id for Backend to store

    This creates a new product with industry template support.
    """
    try:
        logger.info(f"🆕 Creating new product {product_id} for company {company_id}")

        # Initialize services
        qdrant_manager = create_qdrant_manager()
        embedding_service = get_embedding_service()
        collection_name = QDRANT_COLLECTION_NAME or "multi_company_data"

        # Generate new qdrant_point_id for this product
        import uuid

        qdrant_point_id = str(uuid.uuid4())

        logger.info(f"🎯 Generated new Qdrant Point ID: {qdrant_point_id}")

        # Build complete payload for new product
        logger.info(f"🆕 Building fresh product payload for creation")

        # Build payload with all data from request
        fresh_payload = {
            # ===== SYSTEM FIELDS =====
            "company_id": company_id,
            "content_type": "extracted_product",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            # ===== CORE PRODUCT FIELDS =====
            "product_name": request.name,
            "product_type_primary": request.type,
            "category": request.category,
            "description": request.description,
            "price": request.price,
            "currency": getattr(request, "currency", "VND"),
            "price_unit": getattr(request, "price_unit", "per item"),
            # ===== OPTIONAL FIELDS =====
            "sku": request.sku,
            "status": request.status or "draft",
            "tags": request.tags or [],
            "target_audience": request.target_audience or [],
            "image_urls": request.image_urls or [],
            # ===== INDUSTRY TEMPLATE DATA =====
            **request.industry_data,
            # ===== ADDITIONAL FIELDS =====
            **request.additional_fields,
        }

        # Generate content for embedding from metadata
        if request.metadata and request.metadata.get("content_for_embedding"):
            content_for_embedding = request.metadata["content_for_embedding"]
        else:
            # Fallback: create content from basic fields
            content_for_embedding = f"""
{fresh_payload['product_name']} - {fresh_payload['product_type_primary']}
{fresh_payload['description']}
Danh mục: {fresh_payload['category']}
Giá: {fresh_payload['price']} {fresh_payload['currency']}
Trạng thái: {fresh_payload['status']}
SKU: {fresh_payload.get('sku', 'N/A')}
Đối tượng: {', '.join(fresh_payload['target_audience'])}
Từ khóa: {', '.join(fresh_payload['tags'])}
            """.strip()

        # Generate embedding
        logger.info(f"🤖 Generating embedding for new product content")
        fresh_embedding = await embedding_service.generate_embedding(
            content_for_embedding
        )

        # Add final content fields to payload
        fresh_payload["content"] = content_for_embedding
        fresh_payload["searchable_text"] = (
            f"{fresh_payload['product_name']} {fresh_payload['product_type_primary']} "
            f"{fresh_payload['description']} {fresh_payload['category']} "
            f"{' '.join(fresh_payload['tags'])} {' '.join(fresh_payload['target_audience'])}"
        )

        # Create new point in Qdrant
        logger.info(f"💾 Creating new Qdrant point {qdrant_point_id}")

        from qdrant_client.models import PointStruct

        point = PointStruct(
            id=qdrant_point_id, vector=fresh_embedding, payload=fresh_payload
        )

        operation_info = qdrant_manager.client.upsert(
            collection_name=collection_name, points=[point], wait=True
        )

        logger.info(f"✅ Product {product_id} created successfully in Qdrant")
        logger.info(f"   🆔 New Qdrant Point ID: {qdrant_point_id}")
        logger.info(f"   🏷️ Product name: {fresh_payload['product_name']}")
        logger.info(f"   📊 Category: {fresh_payload['category']}")
        logger.info(f"   💰 Price: {fresh_payload['price']}")
        logger.info(f"   🎯 Fresh embedding generated and stored")

        return CRUDResponse(
            success=True,
            message="Product created successfully",
            item_id="N/A",  # Backend manages item_id mapping
            qdrant_point_id=qdrant_point_id,
            changes_made={
                "operation": "creation",
                "new_name": fresh_payload["product_name"],
                "fresh_embedding": True,
                "fresh_content": True,
                "industry_template": (
                    request.industry_data.get("template", "N/A")
                    if request.industry_data
                    else "N/A"
                ),
                "industry": (
                    request.industry_data.get("industry", "N/A")
                    if request.industry_data
                    else "N/A"
                ),
                "required_fields_created": [
                    "name",
                    "type",
                    "category",
                    "description",
                    "price",
                ],
                "optional_fields_count": len(request.additional_fields),
                "industry_fields_count": (
                    len(request.industry_data) if request.industry_data else 0
                ),
            },
        )

    except Exception as e:
        logger.error(f"❌ Product creation error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Product creation failed: {str(e)}"
        )


# ===== PRODUCT UPDATE ENDPOINT =====
