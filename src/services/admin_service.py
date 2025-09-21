"""
Admin Service Layer
Service layer to handle business logic for admin operations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from src.utils.logger import setup_logger
from src.services.qdrant_company_service import get_qdrant_service
from src.core.config import APP_CONFIG
from src.providers.ai_provider_manager import AIProviderManager
from src.models.unified_models import (
    CompanyConfig,
    Industry,
    QdrantDocumentChunk,
    IndustryDataType,
    Language,
)
from src.services.company_data_manager import get_company_data_manager
from src.database.company_db_service import CompanyDBService
from src.utils.content_processor import ContentForEmbeddingProcessor

logger = setup_logger(__name__)


class AdminService:
    def __init__(self):
        self.qdrant_service = get_qdrant_service()
        self.company_db_service = CompanyDBService()
        logger.info("✅ AdminService initialized with database support")

    def _get_collection_name(self, company_id: str) -> Optional[str]:
        """Helper method to get collection name for a company."""
        # Use unified collection for all companies (Free Plan optimization)
        return "multi_company_data"

    async def register_company(
        self, company_id: str, company_name: str, industry: Industry
    ) -> CompanyConfig:
        """Registers a new company in the unified multi-company collection."""
        logger.info(
            f"Registering company {company_id} ({company_name}) in industry {industry.value}"
        )

        # Use unified collection name for all companies
        unified_collection = "multi_company_data"

        company_config = CompanyConfig(
            company_id=company_id,
            company_name=company_name,
            industry=industry,
            qdrant_collection=unified_collection,  # All companies use same collection
        )

        # Ensure unified collection exists (create if needed)
        await self.qdrant_service.ensure_unified_collection_exists()

        # Save to database (persistent storage)
        success = self.company_db_service.save_company(company_config)
        if not success:
            logger.error(f"❌ Failed to save company {company_id} to database")
            raise Exception(f"Failed to save company {company_id} to database")

            # Also save to memory for immediate access
        data_manager = get_company_data_manager()
        data_manager.companies[company_id] = company_config

        logger.info(f"✅ Company {company_id} registered and saved to database.")
        return company_config

    async def get_company_info(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Gets company information and collection stats from database."""
        logger.info(f"Getting info for company {company_id}")

        # First try to get from database (persistent storage)
        company_config = self.company_db_service.get_company(company_id)
        if not company_config:
            logger.warning(f"⚠️ Company {company_id} not found in database")
            return None

        # Also load to memory for immediate access if not already there
        data_manager = get_company_data_manager()
        if company_id not in data_manager.companies:
            data_manager.companies[company_id] = company_config
            logger.info(f"📝 Loaded company {company_id} from database to memory")

        collection_name = company_config.qdrant_collection

        try:
            # Simple approach: just check if company exists in data manager
            data_manager = get_company_data_manager()
            if company_id in data_manager.companies:
                company_config = data_manager.companies[company_id]
                # Return comprehensive info including company details
                return {
                    "company_id": company_id,
                    "company_name": company_config.company_name,
                    "industry": company_config.industry.value,
                    "collection_name": collection_name,
                    "vector_count": "available",  # Indicate data exists
                    "indexed_fields": ["content", "metadata"],
                }
            else:
                return {
                    "company_id": company_id,
                    "company_name": None,
                    "industry": None,
                    "collection_name": collection_name,
                    "vector_count": 0,
                    "indexed_fields": [],
                }
        except Exception as e:
            logger.warning(f"Could not get stats for company {company_id}: {e}")
            return {
                "company_id": company_id,
                "collection_name": collection_name,
                "vector_count": 0,
                "indexed_fields": [],
            }

    async def delete_company(self, company_id: str) -> bool:
        """Deletes a company and its Qdrant collection."""
        logger.info(f"Deleting company {company_id}")
        try:
            await self.qdrant_service.delete_company_data(company_id)
            logger.info(f"✅ Deleted Qdrant collection for company {company_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete company {company_id}: {e}")
            return False

    # Placeholder methods for other functionalities
    async def update_company_basic_info(
        self, company_id: str, info: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info(f"Updating basic info for company {company_id}")

        try:
            # Update company info in companies collection
            updated_company = await self.company_db_service.update_company_basic_info(
                company_id, info
            )

            logger.info(f"✅ Successfully updated company {company_id}")
            return {
                "status": "success",
                "updated_fields": list(info.keys()),
                "company": updated_company,
            }

        except Exception as e:
            logger.error(f"❌ Failed to update company {company_id}: {e}")
            raise e

    async def get_company_products(
        self, company_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        logger.info(f"Fetching products for company {company_id}")

        collection_name = self._get_collection_name(company_id)
        if not collection_name:
            return []

        # Get company industry to determine correct content types
        data_manager = get_company_data_manager()
        if company_id not in data_manager.companies:
            logger.warning(f"Company {company_id} not found in data manager")
            return []

        company_config = data_manager.companies[company_id]
        industry = company_config.industry

        try:
            # **CẬP NHẬT: Sử dụng data_type thống nhất cho tất cả industries**
            product_data_types = [IndustryDataType.PRODUCTS]

            logger.info(
                f"Searching for data types: {[dt.value for dt in product_data_types]} in industry: {industry.value}"
            )

            from qdrant_client.http.models import (
                Filter,
                FieldCondition,
                MatchValue,
                MatchAny,
            )

            # Build filter với data_type thay vì content_type
            data_type_conditions = []
            for data_type in product_data_types:
                data_type_conditions.append(
                    FieldCondition(
                        key="data_type", match=MatchValue(value=data_type.value)
                    )
                )

            filter_obj = Filter(
                must=[
                    FieldCondition(
                        key="company_id", match=MatchValue(value=company_id)
                    ),
                ],
                should=data_type_conditions,  # OR condition for data types
            )

            # Use scroll to get products
            scroll_result = self.qdrant_service.client.scroll(
                collection_name=collection_name,
                scroll_filter=filter_obj,
                limit=limit,
                offset=offset,
                with_payload=True,
            )

            products = []
            if scroll_result and len(scroll_result) > 0:
                points = scroll_result[0]  # First element is points list
                for point in points:
                    if hasattr(point, "payload") and point.payload:
                        payload = point.payload
                        logger.debug(
                            f"Found point with data_type: {payload.get('data_type')}"
                        )

                        # Extract product data from structured_data
                        structured_data = payload.get("structured_data", {})
                        if structured_data.get("item_type") == "product":
                            product_data = structured_data.get("product_data", {})
                            # Merge payload metadata with product data
                            product_info = {
                                **product_data,
                                "id": point.id,
                                "company_id": payload.get("company_id"),
                                "file_id": payload.get("file_id"),
                                "created_at": payload.get("created_at"),
                            }
                            products.append(product_info)
                        else:
                            # Fallback: return raw payload for non-product items
                            products.append(payload)

            logger.info(
                f"Found {len(products)} products for company {company_id} in industry {industry.value}"
            )

            # Debug: Log first product structure
            if products:
                logger.info(f"Sample product structure: {list(products[0].keys())}")

            return products

        except Exception as e:
            logger.error(f"Failed to fetch products for company {company_id}: {e}")
            return []

    async def update_product(
        self, company_id: str, product_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info(f"Updating product {product_id} for company {company_id}")
        # Logic to update a specific point in Qdrant
        return {"status": "success", "product_id": product_id}

    async def delete_product(self, company_id: str, product_id: str) -> bool:
        logger.info(f"Deleting product {product_id} for company {company_id}")
        # Logic to delete a specific point from Qdrant
        return True

    async def get_company_services(
        self, company_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        logger.info(f"Fetching services for company {company_id}")

        collection_name = self._get_collection_name(company_id)
        if not collection_name:
            return []

        # Get company industry to determine correct content types
        data_manager = get_company_data_manager()
        if company_id not in data_manager.companies:
            logger.warning(f"Company {company_id} not found in data manager")
            return []

        company_config = data_manager.companies[company_id]
        industry = company_config.industry

        try:
            # **CẬP NHẬT: Sử dụng data_type thống nhất cho tất cả industries**
            service_data_types = [IndustryDataType.SERVICES]

            logger.info(
                f"Searching for service data types: {[dt.value for dt in service_data_types]} in industry: {industry.value}"
            )

            from qdrant_client.http.models import Filter, FieldCondition, MatchValue

            # Build filter với data_type thay vì content_type
            data_type_conditions = []
            for data_type in service_data_types:
                data_type_conditions.append(
                    FieldCondition(
                        key="data_type", match=MatchValue(value=data_type.value)
                    )
                )

            filter_obj = Filter(
                must=[
                    FieldCondition(
                        key="company_id", match=MatchValue(value=company_id)
                    ),
                ],
                should=data_type_conditions,  # OR condition for data types
            )

            # Use scroll to get services
            scroll_result = self.qdrant_service.client.scroll(
                collection_name=collection_name,
                scroll_filter=filter_obj,
                limit=limit,
                offset=offset,
                with_payload=True,
            )

            services = []
            if scroll_result and len(scroll_result) > 0:
                points = scroll_result[0]  # First element is points list
                for point in points:
                    if hasattr(point, "payload") and point.payload:
                        payload = point.payload
                        logger.debug(
                            f"Found service point with content_type: {payload.get('content_type')}"
                        )
                        services.append(payload)

            logger.info(
                f"Found {len(services)} services for company {company_id} in industry {industry.value}"
            )
            return services

        except Exception as e:
            logger.error(f"Failed to fetch services for company {company_id}: {e}")
            return []

    async def update_service(
        self, company_id: str, service_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info(f"Updating service {service_id} for company {company_id}")
        return {"status": "success", "service_id": service_id}

    async def delete_service(self, company_id: str, service_id: str) -> bool:
        logger.info(f"Deleting service {service_id} for company {company_id}")
        return True

    async def get_company_images(
        self,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Get images for a company with filtering options."""
        logger.info(f"Fetching images for company {company_id} with filters: {filters}")
        # Logic to query Qdrant for points with content_type='image'
        # Apply filters for folder_id, search, status
        collection_name = self._get_collection_name(company_id)
        if not collection_name:
            return []

        # Build Qdrant filter conditions
        qdrant_filter = {
            "must": [
                {"key": "content_type", "match": {"value": "image"}},
                {"key": "company_id", "match": {"value": company_id}},
            ]
        }

        if filters:
            if filters.get("folder_id"):
                qdrant_filter["must"].append(
                    {"key": "folder_id", "match": {"value": filters["folder_id"]}}
                )
            if filters.get("status"):
                qdrant_filter["must"].append(
                    {"key": "status", "match": {"value": filters["status"]}}
                )

        # Query Qdrant with scroll/search
        try:
            results = await self.qdrant_service.scroll_points(
                collection_name=collection_name,
                scroll_filter=qdrant_filter,
                limit=limit,
                offset=offset,
            )
            return [point.payload for point in results.points] if results else []
        except Exception as e:
            logger.error(f"Failed to fetch images from Qdrant: {e}")
            return []

    async def add_image(
        self, company_id: str, image_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a new image to the company's collection."""
        logger.info(f"Adding image to company {company_id}")

        # Generate unique image ID
        import uuid

        image_id = image_data.get("image_id", str(uuid.uuid4()))

        # Prepare point data for Qdrant
        point_data = {
            "id": image_id,
            "payload": {
                **image_data,
                "image_id": image_id,
                "company_id": company_id,
                "content_type": "image",
                "created_at": image_data.get("created_at", datetime.now().isoformat()),
            },
        }

        # If image has AI instructions, generate embeddings
        if image_data.get("ai_instruction"):
            try:
                # Generate embedding for AI instruction text
                embedding = await self.qdrant_service.ai_manager.get_embedding(
                    text=image_data["ai_instruction"]
                )
                point_data["vector"] = embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding for image: {e}")

        # Add to Qdrant
        collection_name = self._get_collection_name(company_id)
        if collection_name:
            await self.qdrant_service.upsert_points(collection_name, [point_data])

        return {"status": "success", "image_id": image_id}

    async def update_image(
        self, company_id: str, image_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing image."""
        logger.info(f"Updating image {image_id} for company {company_id}")

        collection_name = self._get_collection_name(company_id)
        if not collection_name:
            raise ValueError(f"Collection not found for company {company_id}")

        # Get existing point
        try:
            existing_point = await self.qdrant_service.retrieve_point(
                collection_name, image_id
            )
            if not existing_point:
                raise ValueError(f"Image {image_id} not found")

            # Update payload
            updated_payload = {**existing_point.payload, **data}

            # If AI instruction updated, regenerate embedding
            new_vector = existing_point.vector
            if data.get("ai_instruction"):
                try:
                    new_vector = await self.qdrant_service.ai_manager.get_embedding(
                        text=data["ai_instruction"]
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate new embedding: {e}")

            # Update point in Qdrant
            point_data = {
                "id": image_id,
                "payload": updated_payload,
                "vector": new_vector,
            }
            await self.qdrant_service.upsert_points(collection_name, [point_data])

            return {"status": "success", "image_id": image_id}

        except Exception as e:
            logger.error(f"Failed to update image {image_id}: {e}")
            raise

    async def delete_image(self, company_id: str, image_id: str) -> bool:
        """Delete an image from Qdrant."""
        logger.info(f"Deleting image {image_id} for company {company_id}")

        collection_name = self._get_collection_name(company_id)
        if collection_name:
            await self.qdrant_service.delete_points(collection_name, [image_id])
        return True

    async def create_image_folder(
        self, company_id: str, folder_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new image folder."""
        logger.info(f"Creating image folder for company {company_id}")

        import uuid

        folder_id = str(uuid.uuid4())

        point_data = {
            "id": folder_id,
            "payload": {
                **folder_data,
                "folder_id": folder_id,
                "company_id": company_id,
                "content_type": "folder",
            },
        }

        # Generate embedding for folder name and description
        folder_text = (
            f"{folder_data['folder_name']} {folder_data.get('description', '')}"
        )
        try:
            embedding = await self.qdrant_service.ai_manager.get_embedding(
                text=folder_text
            )
            point_data["vector"] = embedding
        except Exception as e:
            logger.warning(f"Failed to generate folder embedding: {e}")

        collection_name = self._get_collection_name(company_id)
        if collection_name:
            await self.qdrant_service.upsert_points(collection_name, [point_data])

        return {"status": "success", "folder_id": folder_id}

    async def get_image_folders(self, company_id: str) -> List[Dict[str, Any]]:
        """Get all image folders for a company."""
        logger.info(f"Fetching image folders for company {company_id}")

        collection_name = self._get_collection_name(company_id)
        if not collection_name:
            return []

        qdrant_filter = {
            "must": [
                {"key": "content_type", "match": {"value": "folder"}},
                {"key": "company_id", "match": {"value": company_id}},
            ]
        }

        try:
            results = await self.qdrant_service.scroll_points(
                collection_name=collection_name, scroll_filter=qdrant_filter, limit=100
            )
            return [point.payload for point in results.points] if results else []
        except Exception as e:
            logger.error(f"Failed to fetch folders from Qdrant: {e}")
            return []

    async def update_image_folder(
        self, company_id: str, folder_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing image folder."""
        logger.info(f"Updating folder {folder_id} for company {company_id}")

        collection_name = self._get_collection_name(company_id)
        if not collection_name:
            raise ValueError(f"Collection not found for company {company_id}")

        try:
            existing_point = await self.qdrant_service.retrieve_point(
                collection_name, folder_id
            )
            if not existing_point:
                raise ValueError(f"Folder {folder_id} not found")

            updated_payload = {**existing_point.payload, **data}

            # Regenerate embedding if name or description changed
            new_vector = existing_point.vector
            if data.get("folder_name") or data.get("description"):
                folder_text = f"{updated_payload.get('folder_name', '')} {updated_payload.get('description', '')}"
                try:
                    new_vector = await self.qdrant_service.ai_manager.get_embedding(
                        text=folder_text
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate new folder embedding: {e}")

            point_data = {
                "id": folder_id,
                "payload": updated_payload,
                "vector": new_vector,
            }
            await self.qdrant_service.upsert_points(collection_name, [point_data])

            return {"status": "success", "folder_id": folder_id}

        except Exception as e:
            logger.error(f"Failed to update folder {folder_id}: {e}")
            raise

    async def delete_image_folder(self, company_id: str, folder_id: str) -> bool:
        """Delete a folder and all its contained images."""
        logger.info(
            f"Deleting folder {folder_id} and all images for company {company_id}"
        )

        collection_name = self._get_collection_name(company_id)
        if not collection_name:
            return True

        try:
            # First, delete all images in this folder
            folder_filter = {
                "must": [
                    {"key": "folder_id", "match": {"value": folder_id}},
                    {"key": "content_type", "match": {"value": "image"}},
                    {"key": "company_id", "match": {"value": company_id}},
                ]
            }

            # Get all images in folder
            images_result = await self.qdrant_service.scroll_points(
                collection_name=collection_name,
                scroll_filter=folder_filter,
                limit=1000,  # Assume max 1000 images per folder
            )

            # Delete all images
            if images_result and images_result.points:
                image_ids = [point.id for point in images_result.points]
                await self.qdrant_service.delete_points(collection_name, image_ids)
                logger.info(f"Deleted {len(image_ids)} images from folder {folder_id}")

            # Delete the folder itself
            await self.qdrant_service.delete_points(collection_name, [folder_id])

            return True

        except Exception as e:
            logger.error(f"Failed to delete folder {folder_id}: {e}")
            raise

    async def upload_file(
        self, company_id: str, file_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Upload a general file and store metadata in Qdrant."""
        logger.info(f"Uploading file for company {company_id}")

        import uuid

        file_id = file_data.get("file_id", str(uuid.uuid4()))

        # Prepare point data for Qdrant
        point_data = {
            "id": file_id,
            "payload": {
                **file_data,
                "file_id": file_id,
                "company_id": company_id,
                "content_type": file_data.get("data_type", "document"),
                "uploaded_at": datetime.now().isoformat(),
            },
        }

        # Generate embeddings for file metadata
        file_text = f"{file_data.get('metadata', {}).get('original_name', '')} {file_data.get('metadata', {}).get('description', '')}"
        if file_text.strip():
            try:
                embedding = await self.qdrant_service.ai_manager.get_embedding(
                    text=file_text
                )
                point_data["vector"] = embedding
            except Exception as e:
                logger.warning(f"Failed to generate file embedding: {e}")

        # Add to Qdrant
        collection_name = self._get_collection_name(company_id)
        if collection_name:
            await self.qdrant_service.upsert_points(collection_name, [point_data])

        return {"status": "success", "file_id": file_id}

    async def delete_file(self, company_id: str, file_id: str) -> bool:
        """Delete a file and its vectors from Qdrant."""
        logger.info(f"Deleting file {file_id} for company {company_id}")

        collection_name = self._get_collection_name(company_id)
        if collection_name:
            await self.qdrant_service.delete_points(collection_name, [file_id])
        return True

    async def delete_files_by_tag(self, company_id: str, tag_name: str) -> bool:
        """Delete all files with a specific tag."""
        logger.info(f"Deleting files with tag '{tag_name}' for company {company_id}")

        collection_name = self._get_collection_name(company_id)
        if not collection_name:
            return True

        try:
            # Find all files with the specified tag
            tag_filter = {
                "must": [
                    {"key": "company_id", "match": {"value": company_id}},
                    {"key": "metadata.tags", "match": {"any": [tag_name]}},
                ]
            }

            results = await self.qdrant_service.scroll_points(
                collection_name=collection_name, scroll_filter=tag_filter, limit=1000
            )

            if results and results.points:
                file_ids = [point.id for point in results.points]
                await self.qdrant_service.delete_points(collection_name, file_ids)
                logger.info(f"Deleted {len(file_ids)} files with tag '{tag_name}'")

            return True

        except Exception as e:
            logger.error(f"Failed to delete files by tag '{tag_name}': {e}")
            raise

    async def create_document_chunks_from_extracted_data(
        self,
        company_id: str,
        file_id: str,
        extracted_data: List[Dict[str, Any]],
        data_type: IndustryDataType,
        industry: Industry,
        language: Language = Language.AUTO_DETECT,
    ) -> List[QdrantDocumentChunk]:
        """
        Create QdrantDocumentChunk objects from extracted data with optimized content_for_embedding
        Tạo QdrantDocumentChunk từ dữ liệu đã extract với content_for_embedding tối ưu
        """
        chunks = []

        for item in extracted_data:
            # Generate unique chunk ID
            chunk_id = f"{company_id}_{file_id}_{data_type.value}_{len(chunks)}"

            # Lấy content_for_embedding từ AI response hoặc tạo mới
            content_for_embedding = item.get("content_for_embedding")
            if not content_for_embedding:
                # Fallback: sử dụng ContentForEmbeddingProcessor nếu AI không tạo
                content_for_embedding = (
                    ContentForEmbeddingProcessor.create_content_for_embedding(
                        original_content=str(item),
                        structured_data=item,
                        content_type=data_type,
                        industry=industry,
                    )
                )

            # Tạo chunk
            chunk = QdrantDocumentChunk(
                chunk_id=chunk_id,
                company_id=company_id,
                file_id=file_id,
                content=str(item),  # Raw content
                content_for_embedding=content_for_embedding,  # Optimized for AI
                content_type=data_type,
                structured_data=item,
                language=language,
                industry=industry,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            chunks.append(chunk)

        logger.info(f"Created {len(chunks)} document chunks for {data_type.value}")
        return chunks

    async def search_company_data(
        self,
        company_id: str,
        query: str,
        data_types: Optional[List[IndustryDataType]] = None,
        limit: int = 10,
        score_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Search company data using semantic vector search
        Tìm kiếm dữ liệu công ty sử dụng vector search
        """
        logger.info(f"Searching company {company_id} for query: '{query}'")

        try:
            # Get company to determine industry
            data_manager = get_company_data_manager()
            if company_id not in data_manager.companies:
                logger.warning(f"Company {company_id} not found")
                return []

            company_config = data_manager.companies[company_id]
            industry = company_config.industry

            # Use QdrantCompanyDataService for search
            results = await self.qdrant_service.search_company_data(
                company_id=company_id,
                query=query,
                industry=industry,
                data_types=data_types,
                limit=limit,
                score_threshold=score_threshold,
            )

            logger.info(f"Found {len(results)} search results for company {company_id}")
            return results

        except Exception as e:
            logger.error(f"Failed to search company {company_id} data: {e}")
            return []

    async def search_images_by_description(
        self,
        company_id: str,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.7,
        folder_name: Optional[str] = None,
        prefer_folders: bool = True,
    ) -> Dict[str, Any]:
        """
        Search images by description using semantic vector search
        Tìm kiếm hình ảnh theo mô tả sử dụng vector search

        Args:
            company_id: ID của công ty
            query: Truy vấn tìm kiếm (mô tả hình ảnh)
            limit: Số lượng kết quả tối đa cho hình ảnh (mặc định 5)
            score_threshold: Ngưỡng điểm để lọc kết quả
            folder_name: Tên thư mục để lọc (tùy chọn)
            prefer_folders: Ưu tiên tìm kiếm folder trước (mặc định True)

        Returns:
            Dict với "type": "folders" hoặc "images" và "data": danh sách kết quả
        """
        logger.info(
            f"🔍 Searching images for company {company_id} with query: '{query}'"
        )

        try:
            collection_name = self._get_collection_name(company_id)
            if not collection_name:
                logger.warning(f"No collection found for company {company_id}")
                return {"type": "images", "data": []}

            # Generate embedding for the query
            query_embedding = await self.qdrant_service.ai_manager.get_embedding(query)

            from qdrant_client.http.models import (
                Filter,
                FieldCondition,
                MatchValue,
            )

            # Step 1: Try to find relevant folders first if prefer_folders is True
            if prefer_folders and not folder_name:
                logger.info("🗂️ Searching for relevant folders first...")

                # Search for folders
                folder_filter = Filter(
                    must=[
                        FieldCondition(
                            key="company_id", match=MatchValue(value=company_id)
                        ),
                        FieldCondition(
                            key="content_type", match=MatchValue(value="folder")
                        ),
                    ]
                )

                folder_results = self.qdrant_service.client.search(
                    collection_name=collection_name,
                    query_vector=query_embedding,
                    query_filter=folder_filter,
                    limit=2,  # Tối đa 2 folders
                    score_threshold=score_threshold,
                    with_payload=True,
                )

                if folder_results:
                    folders = []
                    for scored_point in folder_results:
                        payload = scored_point.payload
                        folder_info = {
                            "folder_id": scored_point.id,
                            "folder_name": payload.get("folder_name", ""),
                            "description": payload.get("description", ""),
                            "score": scored_point.score,
                            "status": payload.get("status", "unknown"),
                        }
                        folders.append(folder_info)

                    logger.info(f"   📁 Found {len(folders)} relevant folders")
                    for folder in folders:
                        logger.info(
                            f"      📁 {folder['folder_name']} (score: {folder['score']:.3f})"
                        )

                    return {"type": "folders", "data": folders}

            # Step 2: Search for individual images
            logger.info("🖼️ Searching for individual images...")

            # Build filter for images only
            filter_conditions = [
                FieldCondition(key="company_id", match=MatchValue(value=company_id)),
                FieldCondition(key="content_type", match=MatchValue(value="image")),
            ]

            # Add folder filter if specified
            if folder_name:
                filter_conditions.append(
                    FieldCondition(
                        key="folder_name", match=MatchValue(value=folder_name)
                    )
                )

            search_filter = Filter(must=filter_conditions)

            # Perform vector search
            search_result = self.qdrant_service.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )

            # Process results
            images = []
            for scored_point in search_result:
                payload = scored_point.payload

                # Extract image information
                image_info = {
                    "image_id": scored_point.id,
                    "r2_url": payload.get("r2_url", ""),
                    "description": payload.get("description", ""),
                    "ai_instruction": payload.get("ai_instruction", ""),
                    "alt_text": payload.get("alt_text", ""),
                    "folder_name": payload.get("folder_name", ""),
                    "metadata": payload.get("metadata", {}),
                    "score": scored_point.score,
                    "status": payload.get("status", "unknown"),
                }

                # Only include images with valid R2 URLs
                if image_info["r2_url"]:
                    images.append(image_info)

            logger.info(f"✅ Found {len(images)} relevant images for query: '{query}'")

            # Log found images for debugging
            for img in images:
                logger.info(
                    f"   📸 Image: {img['description'][:50]}... (score: {img['score']:.3f})"
                )

            return {"type": "images", "data": images}

        except Exception as e:
            logger.error(f"❌ Failed to search images for company {company_id}: {e}")
            return {"type": "images", "data": []}


# Singleton instance
_admin_service_instance = None


def get_admin_service():
    global _admin_service_instance
    if _admin_service_instance is None:
        _admin_service_instance = AdminService()
    return _admin_service_instance
