"""
Hybrid Search Implementation với Metadata Filtering + Vector Search
Combines category-based filtering with semantic similarity ranking
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field
import asyncio

from src.utils.logger import setup_logger
from src.vector_store.qdrant_client import create_qdrant_manager
from src.services.embedding_service import get_embedding_service
from config.config import QDRANT_COLLECTION_NAME

router = APIRouter(tags=["Hybrid Search"])
logger = setup_logger(__name__)

# ===== REQUEST/RESPONSE MODELS =====


class HybridSearchRequest(BaseModel):
    """Hybrid search request với multiple search modes"""

    query: Optional[str] = None
    mode: str = Field(
        default="hybrid", description="Search mode: 'category', 'hybrid', 'semantic'"
    )
    categories: List[str] = Field(default=[], description="Filter by categories")
    sub_categories: List[str] = Field(
        default=[], description="Filter by sub-categories"
    )
    tags: List[str] = Field(default=[], description="Filter by tags")
    target_audience: List[str] = Field(
        default=[], description="Filter by target audience"
    )
    content_types: List[str] = Field(
        default=["extracted_product", "extracted_service"],
        description="Content types to search",
    )
    limit: int = Field(default=20, description="Maximum results to return")


class SearchResult(BaseModel):
    """Individual search result"""

    id: str
    content: str
    score: float
    metadata: Dict[str, Any]


class HybridSearchResponse(BaseModel):
    """Hybrid search response"""

    success: bool
    mode: str
    total_found: int
    query_used: Optional[str]
    filters_applied: Dict[str, Any]
    results: List[SearchResult]
    processing_time: float


# ===== HYBRID SEARCH ENDPOINT =====


@router.post("/api/chat/hybrid-search/{company_id}")
async def hybrid_search(
    request: HybridSearchRequest,
    company_id: str = Path(..., description="Company ID to search within"),
) -> HybridSearchResponse:
    """
    🎯 HYBRID SEARCH: Kết hợp Metadata Filtering (category-based) với Vector Search (similarity ranking)

    Modes:
    - 'category': Pure metadata filtering, returns ALL items in categories
    - 'hybrid': Metadata filtering first, then vector similarity ranking
    - 'semantic': Pure vector search with company filter
    """
    start_time = datetime.now()

    try:
        logger.info(f"🔍 Hybrid search request for company {company_id}")
        logger.info(f"   🎯 Mode: {request.mode}")
        logger.info(f"   📝 Query: {request.query}")
        logger.info(f"   📂 Categories: {request.categories}")
        logger.info(f"   🏷️ Tags: {request.tags}")

        # Initialize services
        qdrant_manager = create_qdrant_manager()
        embedding_service = get_embedding_service()

        search_results = []

        if request.mode in ["category", "hybrid"]:
            # 🔍 STEP 1: Metadata Filtering để get items trong categories
            filters = {
                "must": [
                    {"key": "company_id", "match": {"value": company_id}},
                    {"key": "content_type", "match": {"any": request.content_types}},
                ]
            }

            # Add category filters
            if request.categories:
                filters["must"].append(
                    {"key": "category", "match": {"any": request.categories}}
                )

            if request.sub_categories:
                filters["must"].append(
                    {"key": "sub_category", "match": {"any": request.sub_categories}}
                )

            # Add tag filters
            if request.tags:
                filters["must"].append({"key": "tags", "match": {"any": request.tags}})

            # Add target audience filters
            if request.target_audience:
                filters["must"].append(
                    {
                        "key": "target_audience",
                        "match": {"any": request.target_audience},
                    }
                )

            logger.info(f"📋 Applying metadata filters: {filters}")

            if request.mode == "category":
                # Pure category mode: scroll all matching items without vector search
                metadata_results = await qdrant_manager.scroll_points(
                    collection_name=QDRANT_COLLECTION_NAME,
                    scroll_filter=filters,
                    limit=min(request.limit * 5, 1000),  # Get more results để có đủ
                    with_payload=True,
                    with_vector=False,
                )

                search_results = [
                    SearchResult(
                        id=point.id,
                        content=point.payload.get("content", ""),
                        score=1.0,  # No similarity score in pure category mode
                        metadata=point.payload,
                    )
                    for point in metadata_results
                ]

                logger.info(f"📂 Category mode found {len(search_results)} items")

            else:
                # Hybrid mode: metadata filtering first, then vector ranking
                if request.query:
                    # Generate query embedding
                    query_embedding = await embedding_service.generate_embedding(
                        request.query
                    )

                    # Vector search với metadata filtering
                    vector_results = await qdrant_manager.search_points(
                        collection_name=QDRANT_COLLECTION_NAME,
                        query_vector=query_embedding,
                        search_filter=filters,
                        limit=min(request.limit * 2, 100),
                        score_threshold=0.6,
                    )

                    search_results = [
                        SearchResult(
                            id=result.id,
                            content=result.payload.get("content", ""),
                            score=result.score,
                            metadata=result.payload,
                        )
                        for result in vector_results
                    ]

                    logger.info(
                        f"🎯 Hybrid mode ranked {len(search_results)} items by similarity"
                    )

                else:
                    # No query provided, fallback to metadata filtering
                    metadata_results = await qdrant_manager.scroll_points(
                        collection_name=QDRANT_COLLECTION_NAME,
                        scroll_filter=filters,
                        limit=request.limit,
                        with_payload=True,
                        with_vector=False,
                    )

                    search_results = [
                        SearchResult(
                            id=point.id,
                            content=point.payload.get("content", ""),
                            score=1.0,
                            metadata=point.payload,
                        )
                        for point in metadata_results
                    ]

        elif request.mode == "semantic":
            # Pure semantic search
            if request.query:
                query_embedding = await embedding_service.generate_embedding(
                    request.query
                )

                # Basic company filter only
                semantic_filters = {
                    "must": [
                        {"key": "company_id", "match": {"value": company_id}},
                        {
                            "key": "content_type",
                            "match": {"any": request.content_types},
                        },
                    ]
                }

                vector_results = await qdrant_manager.search_points(
                    collection_name=QDRANT_COLLECTION_NAME,
                    query_vector=query_embedding,
                    search_filter=semantic_filters,
                    limit=request.limit,
                    score_threshold=0.5,
                )

                search_results = [
                    SearchResult(
                        id=result.id,
                        content=result.payload.get("content", ""),
                        score=result.score,
                        metadata=result.payload,
                    )
                    for result in vector_results
                ]

                logger.info(f"🧠 Semantic mode found {len(search_results)} items")
            else:
                raise HTTPException(
                    status_code=400, detail="Query is required for semantic search mode"
                )

        # Remove duplicates by grouping by product/service ID
        grouped_results = {}
        for result in search_results:
            product_id = result.metadata.get("product_id")
            service_id = result.metadata.get("service_id")
            key = f"product_{product_id}" if product_id else f"service_{service_id}"

            # Keep highest scoring result for each product/service
            if key not in grouped_results or result.score > grouped_results[key].score:
                grouped_results[key] = result

        final_results = list(grouped_results.values())

        # Sort by score descending và apply final limit
        final_results.sort(key=lambda x: x.score, reverse=True)
        final_results = final_results[: request.limit]

        processing_time = (datetime.now() - start_time).total_seconds()

        logger.info(f"✅ Hybrid search completed in {processing_time:.3f}s")
        logger.info(f"   📊 Final results: {len(final_results)}")

        return HybridSearchResponse(
            success=True,
            mode=request.mode,
            total_found=len(final_results),
            query_used=request.query,
            filters_applied={
                "categories": request.categories,
                "sub_categories": request.sub_categories,
                "tags": request.tags,
                "target_audience": request.target_audience,
                "content_types": request.content_types,
            },
            results=final_results,
            processing_time=processing_time,
        )

    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ Hybrid search error: {str(e)}")

        return HybridSearchResponse(
            success=False,
            mode=request.mode,
            total_found=0,
            query_used=request.query,
            filters_applied={},
            results=[],
            processing_time=processing_time,
        )


# ===== CATEGORY MANAGEMENT ENDPOINTS =====


class CategoryUpdateRequest(BaseModel):
    """Request to update category information"""

    item_type: str = Field(..., description="'product' or 'service'")
    item_id: str = Field(..., description="Product or service ID")
    new_category: str
    new_sub_category: str
    new_tags: List[str] = []
    new_target_audience: List[str] = []
    new_coverage_type: Optional[List[str]] = None  # For products
    new_service_type: Optional[List[str]] = None  # For services


@router.post("/api/management/update-category/{company_id}")
async def update_category(
    request: CategoryUpdateRequest,
    company_id: str = Path(..., description="Company ID"),
):
    """
    ✏️ USER FEEDBACK LOOP: Update category information cho product/service
    Updates both Qdrant metadata và prepares data for Backend database sync
    """
    try:
        logger.info(f"✏️ Updating category for {request.item_type} {request.item_id}")
        logger.info(
            f"   📂 New category: {request.new_category} -> {request.new_sub_category}"
        )
        logger.info(f"   🏷️ New tags: {', '.join(request.new_tags)}")

        # Initialize Qdrant manager
        qdrant_manager = create_qdrant_manager()

        # Determine point ID based on item type
        point_id = f"{request.item_type}_{request.item_id}"

        # Get current point data
        current_points = await qdrant_manager.retrieve_points(
            collection_name=QDRANT_COLLECTION_NAME, point_ids=[point_id]
        )

        if not current_points:
            raise HTTPException(
                status_code=404, detail=f"{request.item_type} not found in Qdrant"
            )

        current_point = current_points[0]
        current_payload = current_point.payload

        # Update payload với new categorization
        updated_payload = {
            **current_payload,
            "category": request.new_category,
            "sub_category": request.new_sub_category,
            "tags": request.new_tags,
            "target_audience": request.new_target_audience,
            "updated_at": datetime.now().isoformat(),
        }

        # Add type-specific fields
        if request.item_type == "product" and request.new_coverage_type:
            updated_payload["coverage_type"] = request.new_coverage_type
        elif request.item_type == "service" and request.new_service_type:
            updated_payload["service_type"] = request.new_service_type

        # Update searchable text
        item_name = current_payload.get("product_name") or current_payload.get(
            "service_name"
        )
        item_type = current_payload.get("product_type") or current_payload.get(
            "service_type_primary"
        )
        content = current_payload.get("content", "")

        updated_payload["searchable_text"] = (
            f"{item_name} {item_type} {content} {' '.join(request.new_tags)}"
        )

        # Upsert với updated payload (keep same vector)
        success = await qdrant_manager.upsert_points(
            collection_name=QDRANT_COLLECTION_NAME,
            points=[
                {
                    "id": point_id,
                    "vector": current_point.vector,  # Keep existing embedding
                    "payload": updated_payload,
                }
            ],
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update Qdrant point")

        logger.info(
            f"✅ Updated {request.item_type} {request.item_id} category successfully"
        )

        return {
            "success": True,
            "message": f"{request.item_type} categorization updated successfully",
            "updated_record": {
                "id": request.item_id,
                "qdrant_point_id": point_id,
                "category": request.new_category,
                "sub_category": request.new_sub_category,
                "tags": request.new_tags,
                "target_audience": request.new_target_audience,
                "coverage_type": request.new_coverage_type,
                "service_type": request.new_service_type,
            },
        }

    except Exception as e:
        logger.error(f"❌ Category update error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Category update failed: {str(e)}")


# ===== CATEGORY ANALYTICS ENDPOINT =====


@router.get("/api/analytics/categories/{company_id}")
async def get_category_analytics(company_id: str = Path(..., description="Company ID")):
    """
    📊 CATEGORY ANALYTICS: Understanding distribution của categories và tags
    Returns real-time analytics from Qdrant data
    """
    try:
        logger.info(f"📊 Generating category analytics for company {company_id}")

        # Initialize Qdrant manager
        qdrant_manager = create_qdrant_manager()

        # Get all points for company
        all_points = await qdrant_manager.scroll_points(
            collection_name=QDRANT_COLLECTION_NAME,
            scroll_filter={
                "must": [
                    {"key": "company_id", "match": {"value": company_id}},
                    {
                        "key": "content_type",
                        "match": {"any": ["extracted_product", "extracted_service"]},
                    },
                ]
            },
            limit=1000,
            with_payload=True,
            with_vector=False,
        )

        # Initialize analytics counters
        category_stats = {}
        tag_stats = {}
        type_stats = {"products": 0, "services": 0}
        target_audience_stats = {}

        for point in all_points:
            payload = point.payload

            # Count by type
            if payload.get("content_type") == "extracted_product":
                type_stats["products"] += 1
            elif payload.get("content_type") == "extracted_service":
                type_stats["services"] += 1

            # Count by category
            category = payload.get("category", "uncategorized")
            if category not in category_stats:
                category_stats[category] = {"count": 0, "sub_categories": {}}
            category_stats[category]["count"] += 1

            # Count by sub_category
            sub_category = payload.get("sub_category", "other")
            if sub_category not in category_stats[category]["sub_categories"]:
                category_stats[category]["sub_categories"][sub_category] = 0
            category_stats[category]["sub_categories"][sub_category] += 1

            # Count by tags
            tags = payload.get("tags", [])
            for tag in tags:
                if tag not in tag_stats:
                    tag_stats[tag] = 0
                tag_stats[tag] += 1

            # Count by target audience
            audiences = payload.get("target_audience", [])
            for audience in audiences:
                if audience not in target_audience_stats:
                    target_audience_stats[audience] = 0
                target_audience_stats[audience] += 1

        # Sort top tags và audiences
        top_tags = sorted(tag_stats.items(), key=lambda x: x[1], reverse=True)[:20]
        top_audiences = sorted(
            target_audience_stats.items(), key=lambda x: x[1], reverse=True
        )[:10]

        logger.info(f"📊 Analytics generated: {len(all_points)} total items")
        logger.info(f"   📦 Products: {type_stats['products']}")
        logger.info(f"   🔧 Services: {type_stats['services']}")
        logger.info(f"   📂 Categories: {len(category_stats)}")

        return {
            "success": True,
            "total_items": len(all_points),
            "type_distribution": type_stats,
            "category_distribution": category_stats,
            "top_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
            "top_target_audiences": [
                {"audience": audience, "count": count}
                for audience, count in top_audiences
            ],
            "analytics_timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Category analytics error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Category analytics failed: {str(e)}"
        )
