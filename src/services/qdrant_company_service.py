"""
Qdrant Integration Service for Company Data Management
Dịch vụ tích hợp Qdrant cho quản lý dữ liệu công ty
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import numpy as np

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
)

from src.models.unified_models import (
    CompanyConfig,
    Industry,
    QdrantDocumentChunk,
    CompanyDataStats,
    IndustryDataType,
    Language,
)
from src.services.ai_service import get_ai_service
from src.utils.logger import setup_logger
from config.config import VECTOR_SIZE

logger = setup_logger()


class QdrantCompanyDataService:
    """
    Service for managing company data in Qdrant vector database
    Dịch vụ quản lý dữ liệu công ty trong cơ sở dữ liệu vector Qdrant
    """

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        qdrant_url: str = None,
        qdrant_api_key: str = None,
    ):
        # Initialize Qdrant client with URL or host/port
        if qdrant_url and qdrant_api_key:
            # Qdrant Cloud connection
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        elif qdrant_url:
            # Local Qdrant with custom URL
            self.client = QdrantClient(url=qdrant_url)
        else:
            # Local Qdrant with host/port
            self.client = QdrantClient(host=qdrant_host, port=qdrant_port)

        # Initialize unified AI service for embeddings
        self.ai_service = get_ai_service()
        self.logger = logger

        # Collection configuration / Cấu hình collection
        self.vector_size = VECTOR_SIZE  # paraphrase-multilingual-mpnet-base-v2 size

        # Single collection for all companies (Qdrant Free Plan optimization)
        self.unified_collection_name = "multi_company_data"
        self.company_collections = {}  # Cache for company metadata

    async def initialize_company_collection(self, company_config: CompanyConfig) -> str:
        """
        Initialize unified Qdrant collection for all companies (Free Plan Optimization)
        Khởi tạo collection Qdrant chung cho tất cả công ty (Tối ưu cho Free Plan)
        """
        try:
            collection_name = self.unified_collection_name

            self.logger.info(
                f"🚀 Initializing unified Qdrant collection: {collection_name}"
            )

            # Check if unified collection exists / Kiểm tra collection chung có tồn tại
            collections = self.client.get_collections()
            existing_names = [col.name for col in collections.collections]

            if collection_name not in existing_names:
                # Create unified collection for all companies / Tạo collection chung cho tất cả công ty
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size, distance=Distance.COSINE
                    ),
                )

                # Create payload indexes for multi-tenant filtering / Tạo index payload cho lọc đa công ty
                self._create_payload_indexes(collection_name)

                self.logger.info(
                    f"✅ Created unified Qdrant collection: {collection_name}"
                )
            else:
                self.logger.info(
                    f"📋 Unified collection already exists: {collection_name}"
                )

            # Cache company info with unified collection / Cache thông tin công ty với collection chung
            self.company_collections[company_config.company_id] = {
                "collection_name": collection_name,
                "industry": company_config.industry.value,
                "company_name": company_config.company_name,
                "created_at": datetime.now().isoformat(),
            }

            return collection_name

        except Exception as e:
            self.logger.error(
                f"❌ Failed to initialize collection for company {company_config.company_id}: {e}"
            )
            raise e

    async def ensure_unified_collection_exists(self) -> str:
        """
        Ensure unified collection exists for all companies (simplified version for registration)
        Đảm bảo collection chung tồn tại cho tất cả công ty (phiên bản đơn giản cho đăng ký)
        """
        try:
            collection_name = self.unified_collection_name

            self.logger.info(
                f"🔍 Ensuring unified collection exists: {collection_name}"
            )

            # Check if unified collection exists
            collections = self.client.get_collections()
            existing_names = [col.name for col in collections.collections]

            if collection_name not in existing_names:
                # Create unified collection for all companies
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size, distance=Distance.COSINE
                    ),
                )

                # Create payload indexes for multi-tenant filtering
                self._create_payload_indexes(collection_name)

                self.logger.info(f"✅ Created unified collection: {collection_name}")
            else:
                self.logger.info(
                    f"📋 Unified collection already exists: {collection_name}"
                )

            return collection_name

        except Exception as e:
            self.logger.error(f"❌ Failed to ensure unified collection exists: {e}")
            raise e

    def _generate_collection_name(self, company_config: CompanyConfig) -> str:
        """Generate collection name for company / Tạo tên collection cho công ty"""
        prefix = self.collection_prefixes.get(company_config.industry, "other")
        # Clean company_id for collection name / Làm sạch company_id cho tên collection
        clean_id = company_config.company_id.replace("-", "_").replace(" ", "_").lower()
        return f"{prefix}_{clean_id}"

    def _create_payload_indexes(self, collection_name: str):
        """Create payload indexes for efficient filtering / Tạo index payload để lọc hiệu quả"""
        try:
            # Create indexes for common filter fields / Tạo index cho các field lọc thường dùng
            indexes = [
                ("company_id", "keyword"),
                ("industry", "keyword"),
                ("data_type", "keyword"),  # Đổi từ content_type thành data_type
                ("language", "keyword"),
                ("file_id", "keyword"),
                ("created_at", "datetime"),
            ]

            for field, field_type in indexes:
                try:
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field,
                        field_schema=field_type,
                    )
                except Exception as e:
                    # Index might already exist / Index có thể đã tồn tại
                    self.logger.debug(f"Index {field} might already exist: {e}")

        except Exception as e:
            self.logger.warning(f"Failed to create payload indexes: {e}")

    async def add_document_chunks(
        self, chunks: List[QdrantDocumentChunk], company_id: str
    ) -> Dict[str, Any]:
        """
        Add document chunks to unified Qdrant collection (Multi-tenant)
        Thêm các chunk tài liệu vào collection Qdrant chung (Đa công ty)
        """
        try:
            # Use unified collection for all companies / Sử dụng collection chung cho tất cả công ty
            collection_name = self.unified_collection_name

            # Ensure unified collection exists (auto-create if needed)
            await self.ensure_unified_collection_exists()

            self.logger.info(
                f"📤 Adding {len(chunks)} chunks to unified collection for company: {company_id}"
            )

            # Generate embeddings for chunks / Tạo embedding cho các chunk
            points = []
            for chunk in chunks:
                # **THAY ĐỔI 1: Sử dụng content_for_embedding để tạo vector**
                text_for_embedding = (
                    chunk.content_for_embedding
                    if hasattr(chunk, "content_for_embedding")
                    and chunk.content_for_embedding
                    else chunk.content
                )
                embedding = await self._generate_embedding(text_for_embedding)

                # Create point for Qdrant / Tạo point cho Qdrant
                point = PointStruct(
                    id=chunk.chunk_id,
                    vector=embedding,
                    payload={
                        "company_id": chunk.company_id,
                        "file_id": chunk.file_id,
                        "content": chunk.content,  # Nội dung gốc
                        # **THAY ĐỔI 2: Đổi tên `content_type` thành `data_type` cho nhất quán**
                        "data_type": chunk.content_type.value,
                        # **THAY ĐỔI 3: Thêm `content_for_embedding` vào payload để debug và tham khảo**
                        "content_for_embedding": text_for_embedding,
                        "structured_data": chunk.structured_data,
                        "language": chunk.language.value,
                        "industry": chunk.industry.value,
                        "location": chunk.location,
                        "valid_from": (
                            chunk.valid_from.isoformat() if chunk.valid_from else None
                        ),
                        "valid_until": (
                            chunk.valid_until.isoformat() if chunk.valid_until else None
                        ),
                        "created_at": chunk.created_at.isoformat(),
                        "updated_at": chunk.updated_at.isoformat(),
                    },
                )
                points.append(point)

            # Upload points to Qdrant / Upload points lên Qdrant
            operation_info = self.client.upsert(
                collection_name=collection_name, points=points
            )

            self.logger.info(f"✅ Successfully added {len(points)} chunks to Qdrant")

            return {
                "status": "success",
                "collection_name": collection_name,
                "points_added": len(points),
                "operation_id": (
                    operation_info.operation_id
                    if hasattr(operation_info, "operation_id")
                    else None
                ),
            }

        except Exception as e:
            self.logger.error(f"❌ Failed to add chunks to Qdrant: {e}")
            return {"status": "error", "error": str(e), "points_attempted": len(chunks)}

    async def search_company_data(
        self,
        company_id: str,
        query: str,
        industry: Industry,
        # **THAY ĐỔI 4: Đổi tên tham số cho nhất quán**
        data_types: Optional[List[IndustryDataType]] = None,
        language: Language = Language.AUTO_DETECT,
        limit: int = 10,
        score_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Search company data using vector similarity
        Tìm kiếm dữ liệu công ty sử dụng độ tương đồng vector
        """
        try:
            # Only search within specific company data / Chỉ tìm kiếm trong dữ liệu công ty cụ thể
            if not company_id:
                self.logger.warning("Company ID is required for multi-tenant search")
                return []

            # Use unified collection / Sử dụng collection chung
            collection_name = self.unified_collection_name

            # Verify company exists / Kiểm tra công ty có tồn tại
            # NOTE: Temporarily disable this check for debugging
            # if company_id not in self.company_collections:
            #     self.logger.warning(
            #         f"Company {company_id} not found in registered companies"
            #     )
            #     return []

            self.logger.info(
                f"🔍 Multi-tenant search in {collection_name} for company {company_id}: {query[:50]}..."
            )

            # Debug logging
            self.logger.info(
                f"DEBUG: Searching for company_id='{company_id}' in multi_company_data collection"
            )
            self.logger.info(
                f"DEBUG: company_collections = {list(self.company_collections.keys())}"
            )
            self.logger.info(
                f"DEBUG: Query='{query}', data_types={data_types}, score_threshold={score_threshold}, limit={limit}"
            )

            # Generate query embedding / Tạo embedding cho query
            query_embedding = await self._generate_embedding(query)

            # Enhanced filter conditions for multi-tenant / Điều kiện lọc nâng cao cho đa công ty
            must_conditions = [
                FieldCondition(
                    key="company_id", match=MatchValue(value=company_id)
                ),  # PRIMARY FILTER
                FieldCondition(key="industry", match=MatchValue(value=industry.value)),
            ]

            if language != Language.AUTO_DETECT:
                must_conditions.append(
                    FieldCondition(
                        key="language", match=MatchValue(value=language.value)
                    )
                )

            # **THAY ĐỔI 5: Sử dụng `should` để ưu tiên data_type thay vì bắt buộc**
            should_conditions = []
            if data_types:
                data_type_values = [dt.value for dt in data_types]
                should_conditions.append(
                    FieldCondition(
                        # Đổi tên trường thành `data_type`
                        key="data_type",
                        match=MatchAny(any=data_type_values),
                    )
                )

            # Perform search / Thực hiện tìm kiếm
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                # **THAY ĐỔI 6: Xây dựng filter với cả `must` và `should`**
                query_filter=Filter(must=must_conditions, should=should_conditions),
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
            )

            # Format results with content_type optimization / Định dạng kết quả với tối ưu content_type
            formatted_results = []
            for result in search_results:
                payload = result.payload
                content_type = payload.get("content_type", "")

                if content_type in ["extracted_product", "extracted_service"]:
                    # OPTIMIZED: Minimal data for products/services
                    # TỐI ỦU: Dữ liệu tối thiểu cho sản phẩm/dịch vụ
                    structured_data = payload.get("structured_data", {})
                    product_id = structured_data.get("product_id", "")
                    retrieval_context = structured_data.get("retrieval_context", "")

                    # Fallback to content_for_embedding if retrieval_context is empty
                    if not retrieval_context:
                        retrieval_context = payload.get("content_for_embedding", "")

                    formatted_result = {
                        "chunk_id": result.id,
                        "score": result.score,
                        "content_for_rag": retrieval_context,  # Use retrieval_context only
                        "data_type": payload.get("data_type", ""),
                        "content_type": content_type,
                        "structured_data": {
                            "product_id": product_id,
                            "retrieval_context": retrieval_context,
                        },  # Only essential fields
                        "file_id": payload.get("file_id", ""),
                        "language": payload.get("language", ""),
                        "created_at": payload.get("created_at", ""),
                    }
                else:
                    # Full data for other content types
                    # Dữ liệu đầy đủ cho các loại nội dung khác
                    formatted_result = {
                        "chunk_id": result.id,
                        "score": result.score,
                        "content_for_rag": payload.get("content_for_embedding", ""),
                        "data_type": payload.get("data_type", ""),
                        "content_type": content_type,
                        "structured_data": payload.get("structured_data", {}),
                        "file_id": payload.get("file_id", ""),
                        "language": payload.get("language", ""),
                        "created_at": payload.get("created_at", ""),
                    }

                formatted_results.append(formatted_result)

            self.logger.info(f"🎯 Found {len(formatted_results)} relevant chunks")
            return formatted_results

        except Exception as e:
            self.logger.error(f"❌ Search failed for company {company_id}: {e}")
            return []

    async def get_company_data_stats(self, company_id: str) -> CompanyDataStats:
        """
        Get statistics for company data in unified Qdrant collection
        Lấy thống kê dữ liệu công ty trong collection Qdrant chung
        """
        try:
            # Use unified collection / Sử dụng collection chung
            collection_name = self.unified_collection_name

            # Verify company exists / Kiểm tra công ty có tồn tại
            if company_id not in self.company_collections:
                return CompanyDataStats(
                    company_id=company_id,
                    industry=Industry.OTHER,
                    total_chunks=0,
                    qdrant_collection_size=0,
                )

            # Get collection info / Lấy thông tin collection
            collection_info = self.client.get_collection(collection_name)

            # Count documents by data type for this company / Đếm tài liệu theo loại cho công ty này
            data_type_counts = {}

            # Scroll through company-specific points / Scroll qua các points của công ty cụ thể
            scroll_result = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="company_id", match=MatchValue(value=company_id)
                        )
                    ]
                ),
                limit=1000,
                with_payload=["data_type"],
            )

            for point in scroll_result[0]:
                data_type = point.payload.get("data_type", "unknown")
                data_type_counts[data_type] = data_type_counts.get(data_type, 0) + 1

            # Convert to IndustryDataType enum / Chuyển đổi sang enum IndustryDataType
            enum_data_type_counts = {}
            for data_type_str, count in data_type_counts.items():
                try:
                    data_type_enum = IndustryDataType(data_type_str)
                    enum_data_type_counts[data_type_enum] = count
                except ValueError:
                    # Skip unknown data types / Bỏ qua loại dữ liệu không xác định
                    self.logger.warning(f"Unknown data type: {data_type_str}")

            company_info = self.company_collections.get(company_id, {})
            stats = CompanyDataStats(
                company_id=company_id,
                industry=Industry(company_info.get("industry", "other")),
                total_chunks=len(scroll_result[0]),
                qdrant_collection_size=collection_info.points_count,
                data_type_counts=enum_data_type_counts,
            )

            return stats

        except Exception as e:
            self.logger.error(f"❌ Failed to get stats for company {company_id}: {e}")
            return CompanyDataStats(
                company_id=company_id,
                industry=Industry.OTHER,
                total_chunks=0,
                qdrant_collection_size=0,
            )

            # Scroll through all points to get statistics / Scroll qua tất cả points để lấy thống kê
            scroll_result = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="company_id", match=MatchValue(value=company_id)
                        )
                    ]
                ),
                limit=1000,  # Adjust based on data size / Điều chỉnh dựa trên kích thước dữ liệu
                with_payload=["content_type"],
            )

            for point in scroll_result[0]:
                content_type = point.payload.get("content_type", "unknown")
                content_type_counts[content_type] = (
                    content_type_counts.get(content_type, 0) + 1
                )

            # Convert to IndustryDataType enum / Chuyển đổi sang enum IndustryDataType
            data_type_counts = {}
            for content_type_str, count in content_type_counts.items():
                try:
                    data_type = IndustryDataType(content_type_str)
                    data_type_counts[data_type] = count
                except ValueError:
                    # Skip invalid content types / Bỏ qua loại nội dung không hợp lệ
                    pass

            stats = CompanyDataStats(
                company_id=company_id,
                industry=Industry.OTHER,  # Will be updated by caller / Sẽ được cập nhật bởi caller
                total_chunks=len(scroll_result[0]),
                qdrant_collection_size=collection_info.points_count,
                data_type_counts=data_type_counts,
            )

            return stats

        except Exception as e:
            self.logger.error(f"❌ Failed to get stats for company {company_id}: {e}")
            return CompanyDataStats(
                company_id=company_id,
                industry=Industry.OTHER,
                total_chunks=0,
                qdrant_collection_size=0,
            )

    async def delete_company_data(
        self, company_id: str, file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Delete company data from unified Qdrant collection
        Xóa dữ liệu công ty khỏi collection Qdrant chung
        """
        try:
            # Use unified collection / Sử dụng collection chung
            collection_name = self.unified_collection_name

            # Verify company exists / Kiểm tra công ty có tồn tại
            if company_id not in self.company_collections:
                return {"status": "error", "error": "Company not found"}

            if file_ids:
                # Delete specific files for this company / Xóa file cụ thể của công ty này
                for file_id in file_ids:
                    filter_condition = Filter(
                        must=[
                            FieldCondition(
                                key="company_id", match=MatchValue(value=company_id)
                            ),
                            FieldCondition(
                                key="file_id", match=MatchValue(value=file_id)
                            ),
                        ]
                    )

                    self.client.delete(
                        collection_name=collection_name,
                        points_selector=models.FilterSelector(filter=filter_condition),
                    )

                return {
                    "status": "success",
                    "message": f"Deleted {len(file_ids)} files for company {company_id}",
                    "deleted_files": file_ids,
                }
            else:
                # Delete all data for this company / Xóa tất cả dữ liệu của công ty này
                filter_condition = Filter(
                    must=[
                        FieldCondition(
                            key="company_id", match=MatchValue(value=company_id)
                        )
                    ]
                )

                self.client.delete(
                    collection_name=collection_name,
                    points_selector=models.FilterSelector(filter=filter_condition),
                )

                # Remove company from cache / Xóa công ty khỏi cache
                if company_id in self.company_collections:
                    del self.company_collections[company_id]

                return {
                    "status": "success",
                    "message": f"Deleted all data for company {company_id}",
                }

        except Exception as e:
            self.logger.error(f"❌ Failed to delete data for company {company_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def update_document_chunk(
        self, chunk: QdrantDocumentChunk, company_id: str
    ) -> Dict[str, Any]:
        """
        Update a document chunk in unified Qdrant collection
        Cập nhật chunk tài liệu trong collection Qdrant chung
        """
        try:
            # Use unified collection / Sử dụng collection chung
            collection_name = self.unified_collection_name

            # Verify company exists / Kiểm tra công ty có tồn tại
            if company_id not in self.company_collections:
                return {"status": "error", "error": "Company not found"}

            # Generate new embedding / Tạo embedding mới
            embedding = await self._generate_embedding(chunk.content)

            # Update the point / Cập nhật point
            point = PointStruct(
                id=chunk.chunk_id,
                vector=embedding,
                payload={
                    "company_id": chunk.company_id,
                    "file_id": chunk.file_id,
                    "content": chunk.content,
                    "content_type": chunk.content_type.value,
                    "structured_data": chunk.structured_data,
                    "language": chunk.language.value,
                    "industry": chunk.industry.value,
                    "location": chunk.location,
                    "valid_from": (
                        chunk.valid_from.isoformat() if chunk.valid_from else None
                    ),
                    "valid_until": (
                        chunk.valid_until.isoformat() if chunk.valid_until else None
                    ),
                    "created_at": chunk.created_at.isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
            )

            self.client.upsert(collection_name=collection_name, points=[point])

            self.logger.info(
                f"✅ Updated chunk {chunk.chunk_id} in {collection_name} for company {company_id}"
            )
            return {"status": "success", "chunk_id": chunk.chunk_id}

        except Exception as e:
            self.logger.error(f"❌ Failed to update chunk {chunk.chunk_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def upsert_points(self, collection_name: str, points: List[Dict[str, Any]]):
        """
        Directly upsert points to Qdrant collection
        """
        try:
            # Convert dict points to PointStruct objects
            qdrant_points = []
            for point in points:
                qdrant_point = PointStruct(
                    id=point["id"], vector=point["vector"], payload=point["payload"]
                )
                qdrant_points.append(qdrant_point)

            # Upsert to Qdrant
            operation_info = self.client.upsert(
                collection_name=collection_name, points=qdrant_points
            )

            self.logger.info(
                f"✅ Upserted {len(qdrant_points)} points to collection {collection_name}"
            )
            return operation_info

        except Exception as e:
            self.logger.error(f"❌ Failed to upsert points: {e}")
            raise

    async def scroll_points(
        self,
        collection_name: str,
        scroll_filter: Optional[Any] = None,
        limit: int = 100,
        offset: Optional[str] = None,
    ):
        """
        Scroll through points in a collection with optional filtering
        """
        try:
            from qdrant_client.models import ScrollRequest

            result = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=scroll_filter,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            self.logger.info(
                f"✅ Scrolled {len(result.points) if result else 0} points from collection {collection_name}"
            )
            return result

        except Exception as e:
            self.logger.error(f"❌ Failed to scroll points: {e}")
            raise

    async def delete_points(self, collection_name: str, point_ids: List[str]):
        """
        Delete points from a collection by their IDs
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchAny

            if not point_ids:
                self.logger.warning("No point IDs provided for deletion")
                return

            # Delete points by IDs
            delete_result = self.client.delete(
                collection_name=collection_name, points_selector=point_ids
            )

            self.logger.info(
                f"✅ Deleted {len(point_ids)} points from collection {collection_name}"
            )
            return delete_result

        except Exception as e:
            self.logger.error(f"❌ Failed to delete points: {e}")
            raise

    async def comprehensive_hybrid_search(
        self,
        company_id: str,
        query: str,
        industry: Industry,
        data_types: Optional[List[IndustryDataType]] = None,
        language: Language = Language.AUTO_DETECT,
        score_threshold: float = 0.6,
        max_chunks: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Comprehensive hybrid search that combines vector similarity with scrolling through large datasets
        Tìm kiếm hybrid toàn diện kết hợp tương tự vector với duyệt qua datasets lớn

        This function:
        1. Performs vector similarity search to get semantically relevant chunks
        2. Scrolls through ALL company data to find chunks above score_threshold
        3. Combines and deduplicates results
        4. Returns all chunks with score > 0.6 for comprehensive context
        """
        try:
            if not company_id:
                self.logger.warning("Company ID is required for comprehensive search")
                return []

            collection_name = self.unified_collection_name
            self.logger.info(
                f"🔍 Starting comprehensive hybrid search for company {company_id}: {query[:50]}..."
            )

            # Step 1: Generate query embedding for semantic search
            query_embedding = await self._generate_embedding(query)

            # Step 2: Primary vector similarity search (high-recall, lower threshold)
            # Primary search conditions - More flexible industry matching
            must_conditions = [
                FieldCondition(key="company_id", match=MatchValue(value=company_id)),
            ]

            # Add industry filter only if it's not OTHER/unknown
            if industry and industry != Industry.OTHER:
                must_conditions.append(
                    FieldCondition(
                        key="industry", match=MatchValue(value=industry.value)
                    )
                )

            self.logger.info(
                f"🔍 Search filters: company_id={company_id}, industry={industry.value if industry else 'any'}"
            )

            if language != Language.AUTO_DETECT:
                must_conditions.append(
                    FieldCondition(
                        key="language", match=MatchValue(value=language.value)
                    )
                )

            # Prefer specific data types if provided
            should_conditions = []
            if data_types:
                data_type_values = [dt.value for dt in data_types]
                should_conditions.append(
                    FieldCondition(
                        key="data_type", match=MatchAny(any=data_type_values)
                    )
                )

            search_filter = Filter(must=must_conditions, should=should_conditions)

            # Perform vector search with lower threshold for broader recall
            vector_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=max_chunks * 2,  # Get more than needed
                score_threshold=0.3,  # Lower threshold for initial search
                with_payload=True,
                with_vectors=False,
            )

            self.logger.info(
                f"📊 Vector search found {len(vector_results)} initial chunks"
            )

            # Step 3: Scroll through ALL company data for comprehensive coverage
            scroll_chunks = []
            scroll_filter = Filter(must=must_conditions)

            # Start scrolling from beginning
            next_page_offset = None
            total_scrolled = 0
            scroll_batch_size = 500  # Process in batches of 500

            while len(scroll_chunks) < max_chunks * 3:  # Prevent infinite loops
                try:
                    scroll_result = self.client.scroll(
                        collection_name=collection_name,
                        scroll_filter=scroll_filter,
                        limit=scroll_batch_size,
                        offset=next_page_offset,
                        with_payload=True,
                        with_vectors=True,  # Need vectors to calculate similarity
                    )

                    if not scroll_result or not scroll_result[0]:
                        break  # No more data

                    batch_points = scroll_result[0]
                    next_page_offset = (
                        scroll_result[1] if len(scroll_result) > 1 else None
                    )
                    total_scrolled += len(batch_points)

                    # Calculate similarity for each scrolled point
                    for point in batch_points:
                        if hasattr(point, "vector") and point.vector:
                            # Calculate cosine similarity
                            similarity = self._calculate_cosine_similarity(
                                query_embedding, point.vector
                            )

                            if similarity >= score_threshold:
                                scroll_chunks.append(
                                    {"point": point, "similarity": similarity}
                                )

                    # Check if we have next page
                    if not next_page_offset:
                        break

                except Exception as e:
                    self.logger.warning(f"Scroll batch failed: {e}")
                    break

            self.logger.info(
                f"📈 Scrolled through {total_scrolled} total points, "
                f"found {len(scroll_chunks)} chunks above threshold {score_threshold}"
            )

            # Step 4: Combine and deduplicate results
            all_chunks = {}  # Use dict to deduplicate by chunk_id

            # Add vector search results
            for result in vector_results:
                if result.score >= score_threshold:
                    chunk_id = str(result.id)
                    all_chunks[chunk_id] = {
                        "result": result,
                        "score": float(result.score),
                        "source": "vector_search",
                    }

            # Add scroll results
            for scroll_item in scroll_chunks:
                point = scroll_item["point"]
                chunk_id = str(point.id)

                # Keep higher score if already exists
                if chunk_id in all_chunks:
                    if scroll_item["similarity"] > all_chunks[chunk_id]["score"]:
                        all_chunks[chunk_id]["score"] = float(scroll_item["similarity"])
                        all_chunks[chunk_id]["source"] = "scroll_search"
                else:
                    all_chunks[chunk_id] = {
                        "result": point,
                        "score": float(scroll_item["similarity"]),
                        "source": "scroll_search",
                    }

            # Step 5: Format and sort results
            formatted_results = []
            for chunk_id, chunk_data in all_chunks.items():
                try:
                    result = chunk_data["result"]
                    payload = result.payload

                    if not payload or not isinstance(payload, dict):
                        self.logger.warning(f"Invalid payload for chunk {chunk_id}")
                        continue

                    # Apply priority boost for important content types
                    adjusted_score = chunk_data["score"]
                    content_type = payload.get("content_type", "")
                    data_type = payload.get("data_type", "")

                    if content_type in ["extracted_product", "extracted_service"]:
                        adjusted_score *= 1.3  # 30% boost for extracted content
                    elif data_type in ["products", "services"]:
                        adjusted_score *= 1.2  # 20% boost for product/service data
                    elif content_type == "company_info":
                        adjusted_score *= 1.1  # 10% boost for company info

                    # OPTIMIZED: For products/services, only return essential fields
                    # TỐI ỦU: Cho products/services, chỉ trả về các field cần thiết
                    content_type = payload.get("content_type", "")

                    if content_type in ["extracted_product", "extracted_service"]:
                        # Minimal data for products/services - only retrieval_context and product_id
                        # Dữ liệu tối thiểu cho sản phẩm/dịch vụ - chỉ retrieval_context và product_id
                        structured_data = payload.get("structured_data", {})
                        product_id = structured_data.get("product_id", "")
                        retrieval_context = structured_data.get("retrieval_context", "")

                        # Fallback to content_for_rag if retrieval_context is empty
                        if not retrieval_context:
                            retrieval_context = payload.get(
                                "content_for_embedding", payload.get("content", "")
                            )

                        formatted_result = {
                            "chunk_id": chunk_id,
                            "score": adjusted_score,
                            "original_score": chunk_data["score"],
                            "search_source": chunk_data["source"],
                            "content_for_rag": retrieval_context,  # Use retrieval_context only
                            "data_type": payload.get("data_type", ""),
                            "content_type": content_type,
                            "structured_data": {
                                "product_id": product_id,
                                "retrieval_context": retrieval_context,
                            },  # Only essential fields
                            "file_id": payload.get("file_id", ""),
                            "language": payload.get("language", ""),
                            "created_at": payload.get("created_at", ""),
                            "categories": [],  # Empty to save space
                            "tags": [],  # Empty to save space
                        }
                    else:
                        # Full data for other content types (company info, documents, etc.)
                        # Dữ liệu đầy đủ cho các loại nội dung khác (thông tin công ty, tài liệu, v.v.)
                        formatted_result = {
                            "chunk_id": chunk_id,
                            "score": adjusted_score,
                            "original_score": chunk_data["score"],
                            "search_source": chunk_data["source"],
                            "content_for_rag": payload.get(
                                "content_for_embedding", payload.get("content", "")
                            ),
                            "data_type": payload.get("data_type", ""),
                            "content_type": content_type,
                            "structured_data": payload.get("structured_data", {}),
                            "file_id": payload.get("file_id", ""),
                            "language": payload.get("language", ""),
                            "created_at": payload.get("created_at", ""),
                            "categories": payload.get("categories", []),
                            "tags": payload.get("tags", []),
                        }
                    formatted_results.append(formatted_result)

                except Exception as e:
                    self.logger.warning(f"Failed to format chunk {chunk_id}: {e}")
                    continue

            # Step 6: Sort by adjusted score and limit results
            formatted_results.sort(key=lambda x: x["score"], reverse=True)
            final_results = formatted_results[:max_chunks]

            self.logger.info(
                f"🎯 Comprehensive hybrid search completed: {len(final_results)} chunks "
                f"(vector: {len([r for r in final_results if r['search_source'] == 'vector_search'])}, "
                f"scroll: {len([r for r in final_results if r['search_source'] == 'scroll_search'])})"
            )

            # Log top results for debugging
            for i, result in enumerate(final_results[:5], 1):
                self.logger.info(
                    f"   {i}. {result['content_type']} (score: {result['score']:.3f}, "
                    f"original: {result['original_score']:.3f}, source: {result['search_source']})"
                )

            return final_results

        except Exception as e:
            self.logger.error(
                f"❌ Comprehensive hybrid search failed for company {company_id}: {e}"
            )
            # Fallback to basic search
            return await self.search_company_data(
                company_id=company_id,
                query=query,
                industry=industry,
                data_types=data_types,
                language=language,
                score_threshold=score_threshold,
                limit=max_chunks,
            )

    def _calculate_cosine_similarity(
        self, vec1: List[float], vec2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two vectors
        Tính độ tương tự cosine giữa hai vector
        """
        try:
            import numpy as np

            vec1_np = np.array(vec1)
            vec2_np = np.array(vec2)

            # Calculate cosine similarity
            dot_product = np.dot(vec1_np, vec2_np)
            norm1 = np.linalg.norm(vec1_np)
            norm2 = np.linalg.norm(vec2_np)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return float(similarity)

        except Exception as e:
            self.logger.warning(f"Failed to calculate cosine similarity: {e}")
            return 0.0

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using unified AI service
        Tạo vector embedding cho text sử dụng dịch vụ AI thống nhất
        """
        try:
            return await self.ai_service.generate_embedding(text)
        except Exception as e:
            self.logger.error(
                f"❌ Failed to generate embedding for text '{text[:50]}...': {e}"
            )
            raise e


# Global service instance
qdrant_service = None


def get_qdrant_service() -> QdrantCompanyDataService:
    """Get Qdrant service instance / Lấy instance service Qdrant"""
    global qdrant_service
    if qdrant_service is None:
        from src.core.config import APP_CONFIG

        qdrant_service = QdrantCompanyDataService(
            qdrant_host=APP_CONFIG.get("qdrant_host", "localhost"),
            qdrant_port=APP_CONFIG.get("qdrant_port", 6333),
            qdrant_url=APP_CONFIG.get("qdrant_url"),
            qdrant_api_key=APP_CONFIG.get("qdrant_api_key"),
        )

    return qdrant_service
