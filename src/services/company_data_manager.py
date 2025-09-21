"""
Company Data Management Service
Dịch vụ quản lý dữ liệu công ty
"""

import os
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json

from src.models.unified_models import (
    CompanyConfig,
    CompanyDataFile,
    FileType,
    IndustryDataType,
    DataExtractionStatus,
    DataExtractionRequest,
    CompanyDataStats,
    Industry,
    Language,
    QdrantDocumentChunk,
)
from src.services.ai_extraction_service import get_ai_service
from src.services.qdrant_company_service import get_qdrant_service
from src.utils.logger import setup_logger

logger = setup_logger()


class CompanyDataManager:
    """
    Main service for managing company data lifecycle
    Dịch vụ chính để quản lý vòng đời dữ liệu công ty
    """

    def __init__(self, storage_base_path: str = "./data/companies"):
        self.storage_base_path = Path(storage_base_path)
        self.storage_base_path.mkdir(parents=True, exist_ok=True)

        self.ai_extraction_service = get_ai_service()
        self.qdrant_service = get_qdrant_service()
        self.logger = logger

        # MongoDB storage for company persistence
        # Lưu trữ MongoDB cho tính bền vững của dữ liệu công ty
        from src.database.company_db_service import get_company_db_service

        self.company_db = get_company_db_service()

        # In-memory cache for fast access (loaded from MongoDB)
        # Cache trong memory để truy cập nhanh (được load từ MongoDB)
        self.companies: Dict[str, CompanyConfig] = {}
        self.files: Dict[str, CompanyDataFile] = {}

        # Load existing companies from MongoDB on startup
        # Load các công ty đã có từ MongoDB khi khởi động
        self._load_companies_from_db()

        # File type mappings / Ánh xạ loại file
        self.file_type_mappings = {
            ".jpg": FileType.IMAGE,
            ".jpeg": FileType.IMAGE,
            ".png": FileType.IMAGE,
            ".gif": FileType.IMAGE,
            ".webp": FileType.IMAGE,
            ".pdf": FileType.PDF,
            ".xlsx": FileType.EXCEL,
            ".xls": FileType.EXCEL,
            ".docx": FileType.WORD,
            ".doc": FileType.WORD,
            ".txt": FileType.TEXT,
            ".json": FileType.JSON,
            ".csv": FileType.CSV,
        }

        # Backend DataType mapping to IndustryDataType (unified for all industries)
        # Ánh xạ DataType từ backend sang IndustryDataType (thống nhất cho tất cả ngành)
        self.backend_data_type_mapping = {
            "company_info": IndustryDataType.COMPANY_INFO,
            "products": IndustryDataType.PRODUCTS,  # Unified products for all industries
            "services": IndustryDataType.SERVICES,  # Unified services for all industries
            "policies": IndustryDataType.POLICIES,
            "faq": IndustryDataType.FAQ,
            "knowledge_base": IndustryDataType.KNOWLEDGE_BASE,
            "other": IndustryDataType.OTHER,
        }

        # Industry data type suggestions for UI (same data types, different templates)
        # Gợi ý loại dữ liệu theo ngành cho UI (cùng data types, khác template)
        self.industry_data_suggestions = {
            Industry.RESTAURANT: [
                IndustryDataType.COMPANY_INFO,
                IndustryDataType.PRODUCTS,  # Menu items for restaurant
                IndustryDataType.SERVICES,  # Restaurant services
                IndustryDataType.POLICIES,
                IndustryDataType.FAQ,
                IndustryDataType.KNOWLEDGE_BASE,
            ],
            Industry.HOTEL: [
                IndustryDataType.COMPANY_INFO,
                IndustryDataType.PRODUCTS,  # Room types for hotel
                IndustryDataType.SERVICES,  # Hotel services
                IndustryDataType.POLICIES,
                IndustryDataType.FAQ,
                IndustryDataType.KNOWLEDGE_BASE,
            ],
            Industry.BANKING: [
                IndustryDataType.COMPANY_INFO,
                IndustryDataType.PRODUCTS,  # Loan products for banking
                IndustryDataType.SERVICES,  # Banking services
                IndustryDataType.POLICIES,
                IndustryDataType.FAQ,
                IndustryDataType.KNOWLEDGE_BASE,
            ],
            Industry.INSURANCE: [
                IndustryDataType.COMPANY_INFO,
                IndustryDataType.PRODUCTS,  # Insurance products
                IndustryDataType.SERVICES,  # Insurance services
                IndustryDataType.POLICIES,
                IndustryDataType.FAQ,
                IndustryDataType.KNOWLEDGE_BASE,
            ],
            Industry.EDUCATION: [
                IndustryDataType.COMPANY_INFO,
                IndustryDataType.PRODUCTS,  # Courses for education
                IndustryDataType.SERVICES,  # Education services
                IndustryDataType.POLICIES,
                IndustryDataType.FAQ,
                IndustryDataType.KNOWLEDGE_BASE,
            ],
            # Default for all other industries
            "default": [
                IndustryDataType.COMPANY_INFO,
                IndustryDataType.PRODUCTS,
                IndustryDataType.SERVICES,
                IndustryDataType.POLICIES,
                IndustryDataType.FAQ,
                IndustryDataType.KNOWLEDGE_BASE,
            ],
        }

    async def register_company(self, company_data: Dict[str, Any]) -> CompanyConfig:
        """
        Register a new company for data management
        Đăng ký công ty mới để quản lý dữ liệu
        """
        try:
            # Extract metadata for company info indexing / Trích xuất metadata để index thông tin công ty
            metadata = company_data.get("metadata", {})

            # Create company config / Tạo cấu hình công ty
            company_config = CompanyConfig(
                company_id=company_data.get("company_id", str(uuid.uuid4())),
                company_name=company_data["company_name"],
                industry=Industry(company_data["industry"]),
                languages=company_data.get("languages", [Language.VIETNAMESE]),
                qdrant_collection=f"company_{company_data.get('company_id', str(uuid.uuid4()))}_data",
                data_sources=company_data.get("data_sources", {}),
                ai_config=company_data.get("ai_config", {}),
                industry_config=company_data.get("industry_config", {}),
                business_hours=metadata.get("business_info", {}).get("business_hours"),
                contact_info={
                    "email": metadata.get("email"),
                    "phone": metadata.get("phone"),
                    "website": metadata.get("website"),
                    "address": metadata.get("location", {}).get("address"),
                    "social_links": metadata.get("social_links", {}),
                },
            )

            # Initialize Qdrant collection / Khởi tạo collection Qdrant
            collection_name = await self.qdrant_service.initialize_company_collection(
                company_config
            )
            company_config.qdrant_collection = collection_name

            # Index company basic info to Qdrant / Index thông tin cơ bản công ty vào Qdrant
            await self._index_company_basic_info(company_config, metadata)

            # Create storage directory / Tạo thư mục lưu trữ
            company_storage_path = self.storage_base_path / company_config.company_id
            company_storage_path.mkdir(parents=True, exist_ok=True)

            # Save to MongoDB / Lưu vào MongoDB
            success = self.company_db.save_company(company_config)
            if not success:
                self.logger.warning(
                    f"⚠️ Failed to save company to MongoDB: {company_config.company_id}"
                )
                # Continue anyway, we still have it in memory

            # Store company config in memory cache / Lưu cấu hình công ty vào cache memory
            self.companies[company_config.company_id] = company_config

            self.logger.info(
                f"✅ Registered company: {company_config.company_name} ({company_config.company_id})"
            )

            return company_config

        except Exception as e:
            self.logger.error(f"❌ Failed to register company: {e}")
            raise e

    async def upload_company_file(
        self,
        company_id: str,
        file_name: str,
        file_content: bytes,
        backend_data_type: str,  # Changed from IndustryDataType to string
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload and store a company data file
        Upload và lưu trữ file dữ liệu công ty
        """
        try:
            # Validate company exists / Kiểm tra công ty có tồn tại
            if company_id not in self.companies:
                raise ValueError(f"Company {company_id} not found")

            company_config = self.companies[company_id]

            # Map backend data type to industry data type / Ánh xạ data type từ backend sang industry data type
            industry_data_type = self.map_backend_data_type(
                backend_data_type, company_config.industry
            )

            # Generate file ID / Tạo ID file
            file_id = str(uuid.uuid4())

            # Determine file type / Xác định loại file
            file_extension = Path(file_name).suffix.lower()
            file_type = self.file_type_mappings.get(file_extension, FileType.TEXT)

            # Create storage path / Tạo đường dẫn lưu trữ
            company_storage_path = self.storage_base_path / company_id
            file_storage_path = company_storage_path / f"{file_id}_{file_name}"

            # Save file to storage / Lưu file vào storage
            with open(file_storage_path, "wb") as f:
                f.write(file_content)

            # Extract file_name, description, tags from metadata / Trích xuất file_name, description, tags từ metadata
            display_name = metadata.get("file_name") if metadata else None
            if not display_name:
                display_name = file_name

            # Create file record / Tạo record file
            file_data = CompanyDataFile(
                file_id=file_id,
                company_id=company_id,
                file_name=display_name,  # Use display name from metadata
                file_type=file_type,
                file_size=len(file_content),
                file_path=str(file_storage_path),
                industry=company_config.industry,
                data_type=industry_data_type,  # Use mapped industry data type
                extraction_status=DataExtractionStatus.PENDING,
                metadata={
                    **(metadata or {}),
                    "original_file_name": file_name,  # Keep original file name
                    "backend_data_type": backend_data_type,  # Keep backend data type for reference
                    "mapped_data_type": industry_data_type.value,  # Store mapped type
                    "tags": metadata.get("tags", []) if metadata else [],
                },
            )

            # Store file record / Lưu record file
            self.files[file_id] = file_data

            self.logger.info(
                f"📁 Uploaded file: {display_name} ({backend_data_type} -> {industry_data_type.value}) for company {company_id}"
            )

            # Return file info for response / Trả về thông tin file cho response
            return {
                "file_id": file_id,
                "file_name": display_name,
                "original_name": file_name,
                "backend_data_type": backend_data_type,
                "mapped_data_type": industry_data_type.value,
                "file_size": len(file_content),
                "extraction_status": DataExtractionStatus.PENDING.value,
                "tags": metadata.get("tags", []) if metadata else [],
                "extracted_items": 0,  # Will be updated after processing
                "chunks_created": 0,  # Will be updated after processing
                "processing_time": 0,  # Will be updated after processing
            }

        except Exception as e:
            self.logger.error(f"❌ Failed to upload file {file_name}: {e}")
            raise e

    async def process_data_extraction(
        self, extraction_request: DataExtractionRequest
    ) -> Dict[str, Any]:
        """
        Process data extraction for uploaded files
        Xử lý trích xuất dữ liệu cho các file đã upload
        """
        try:
            results = []

            for file_id in extraction_request.file_ids:
                # Get file data / Lấy dữ liệu file
                if file_id not in self.files:
                    results.append(
                        {
                            "file_id": file_id,
                            "status": "error",
                            "error": "File not found",
                        }
                    )
                    continue

                file_data = self.files[file_id]

                # Update status to processing / Cập nhật trạng thái thành đang xử lý
                file_data.extraction_status = DataExtractionStatus.PROCESSING

                try:
                    # Read file content / Đọc nội dung file
                    with open(file_data.file_path, "rb") as f:
                        file_content = f.read()

                    # Note: Data extraction is now handled directly in admin_routes.py using ai_extraction_service
                    # This legacy method is preserved for compatibility but not actively used
                    # Ghi chú: Trích xuất dữ liệu giờ được xử lý trực tiếp trong admin_routes.py sử dụng ai_extraction_service
                    # Method cũ này được giữ lại để tương thích nhưng không được sử dụng tích cực

                    self.logger.warning(
                        f"⚠️ Legacy extraction method called for file {file_id}. Consider using ai_extraction_service directly."
                    )

                    # For now, mark as completed and skip actual processing
                    # Hiện tại, đánh dấu là hoàn thành và bỏ qua xử lý thực tế
                    file_data.extraction_status = DataExtractionStatus.COMPLETED
                    file_data.processed_at = datetime.now()

                    results.append(
                        {
                            "file_id": file_id,
                            "status": "skipped_legacy",
                            "message": "Use ai_extraction_service for actual processing",
                        }
                    )

                except Exception as e:
                    # Processing failed / Xử lý thất bại
                    file_data.extraction_status = DataExtractionStatus.FAILED
                    file_data.extraction_error = str(e)

                    results.append(
                        {"file_id": file_id, "status": "error", "error": str(e)}
                    )

            self.logger.info(
                f"🔄 Processed extraction for {len(extraction_request.file_ids)} files"
            )

            return {
                "status": "completed",
                "total_files": len(extraction_request.file_ids),
                "results": results,
                "processed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"❌ Data extraction processing failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "processed_at": datetime.now().isoformat(),
            }

    async def search_company_data(
        self,
        company_id: str,
        query: str,
        content_types: Optional[
            List[str]
        ] = None,  # Changed from IndustryDataType to str
        language: str = "vi",  # Changed from Language enum to string
        limit: int = 10,
        filter_tags: Optional[List[str]] = None,  # Added tags filtering
    ) -> List[Dict[str, Any]]:
        """
        Search company data using RAG
        Tìm kiếm dữ liệu công ty sử dụng RAG
        """
        try:
            # Validate company exists / Kiểm tra công ty có tồn tại
            if company_id not in self.companies:
                raise ValueError(f"Company {company_id} not found")

            company_config = self.companies[company_id]

            # Map backend content types to industry data types if provided
            mapped_content_types = None
            if content_types:
                mapped_content_types = []
                for content_type in content_types:
                    mapped_type = self.map_backend_data_type(
                        content_type, company_config.industry
                    )
                    mapped_content_types.append(mapped_type)

            # Convert language string to enum if needed
            language_enum = (
                Language.VIETNAMESE if language == "vi" else Language.ENGLISH
            )

            # Search in Qdrant / Tìm kiếm trong Qdrant
            search_results = await self.qdrant_service.search_company_data(
                company_id=company_id,
                query=query,
                industry=company_config.industry,
                content_types=mapped_content_types,
                language=language_enum,
                limit=limit,
                filter_tags=filter_tags,
            )

            return search_results

        except Exception as e:
            self.logger.error(f"❌ Company data search failed: {e}")
            return []

    async def get_company_stats(self, company_id: str) -> Dict[str, Any]:
        """
        Get comprehensive statistics for company data
        Lấy thống kê toàn diện cho dữ liệu công ty
        """
        try:
            # Validate company exists / Kiểm tra công ty có tồn tại
            if company_id not in self.companies:
                raise ValueError(f"Company {company_id} not found")

            company_config = self.companies[company_id]

            # Get file statistics / Lấy thống kê file
            company_files = [
                f for f in self.files.values() if f.company_id == company_id
            ]

            file_stats = {
                "total_files": len(company_files),
                "processed_files": len(
                    [
                        f
                        for f in company_files
                        if f.extraction_status == DataExtractionStatus.COMPLETED
                    ]
                ),
                "failed_files": len(
                    [
                        f
                        for f in company_files
                        if f.extraction_status == DataExtractionStatus.FAILED
                    ]
                ),
                "total_file_size": sum(f.file_size for f in company_files),
                "pending_files": len(
                    [
                        f
                        for f in company_files
                        if f.extraction_status == DataExtractionStatus.PENDING
                    ]
                ),
                "processing_files": len(
                    [
                        f
                        for f in company_files
                        if f.extraction_status == DataExtractionStatus.PROCESSING
                    ]
                ),
            }

            # Get Qdrant statistics / Lấy thống kê Qdrant
            try:
                qdrant_stats = await self.qdrant_service.get_company_data_stats(
                    company_id
                )
                file_stats.update(
                    {
                        "total_chunks": qdrant_stats.get("total_chunks", 0),
                        "vector_points": qdrant_stats.get("total_chunks", 0),
                        "storage_used_mb": round(
                            file_stats["total_file_size"] / (1024 * 1024), 2
                        ),
                    }
                )
            except Exception as e:
                self.logger.warning(f"⚠️ Could not get Qdrant stats: {e}")
                file_stats.update(
                    {
                        "total_chunks": 0,
                        "vector_points": 0,
                        "storage_used_mb": round(
                            file_stats["total_file_size"] / (1024 * 1024), 2
                        ),
                    }
                )

            # Get data types distribution / Phân bố loại dữ liệu
            data_types = {}
            for file in company_files:
                backend_type = file.metadata.get("backend_data_type", "other")
                data_types[backend_type] = data_types.get(backend_type, 0) + 1

            # Get tags statistics / Thống kê tags
            all_tags = {}
            for file in company_files:
                file_tags = file.metadata.get("tags", [])
                for tag in file_tags:
                    if tag not in all_tags:
                        all_tags[tag] = {
                            "name": tag,
                            "file_count": 0,
                            "created_at": file.created_at.isoformat(),
                            "last_used": (
                                file.updated_at.isoformat()
                                if file.updated_at
                                else file.created_at.isoformat()
                            ),
                        }
                    all_tags[tag]["file_count"] += 1

            # Sort tags by usage / Sắp xếp tags theo mức sử dụng
            most_used_tags = sorted(
                [
                    {"name": tag, "file_count": info["file_count"]}
                    for tag, info in all_tags.items()
                ],
                key=lambda x: x["file_count"],
                reverse=True,
            )[:3]

            # Get company info status / Trạng thái thông tin công ty
            company_info_indexed = any(
                f.metadata.get("backend_data_type") == "company_info"
                for f in company_files
            ) or company_config.contact_info.get(
                "email"
            )  # Basic info from registration

            file_stats.update(
                {
                    "last_activity": max(
                        [f.updated_at or f.created_at for f in company_files],
                        default=company_config.created_at,
                    ).isoformat(),
                    "data_types": data_types,
                    "total_tags": len(all_tags),
                    "most_used_tags": most_used_tags,
                    "company_info_indexed": company_info_indexed,
                    "company_info_last_updated": (
                        company_config.updated_at.isoformat()
                        if company_config.updated_at
                        else company_config.created_at.isoformat()
                    ),
                    "language": (
                        company_config.languages[0].value
                        if company_config.languages
                        else "vi"
                    ),
                    "timezone": "Asia/Ho_Chi_Minh",  # Default timezone
                }
            )

            return file_stats

        except Exception as e:
            self.logger.error(f"❌ Failed to get company stats: {e}")
            return {
                "total_files": 0,
                "processed_files": 0,
                "failed_files": 0,
                "total_chunks": 0,
                "vector_points": 0,
                "storage_used_mb": 0,
                "data_types": {},
                "total_tags": 0,
                "most_used_tags": [],
                "company_info_indexed": False,
            }

    def get_company_files(self, company_id: str) -> List[CompanyDataFile]:
        """
        Get all files for a company
        Lấy tất cả file của một công ty
        """
        return [f for f in self.files.values() if f.company_id == company_id]

    def get_file_by_id(self, file_id: str) -> Optional[CompanyDataFile]:
        """
        Get file by ID
        Lấy file theo ID
        """
        return self.files.get(file_id)

    def get_company_by_id(self, company_id: str) -> Optional[CompanyConfig]:
        """
        Get company configuration by ID
        Lấy cấu hình công ty theo ID
        """
        # First check memory cache
        if company_id in self.companies:
            return self.companies[company_id]

        # If not in cache, try to load from MongoDB
        try:
            company_config = self.company_db.get_company(company_id)
            if company_config:
                # Add to cache for future access
                self.companies[company_id] = company_config
                self.logger.info(f"✅ Loaded company from MongoDB: {company_id}")
                return company_config
        except Exception as e:
            self.logger.error(f"❌ Failed to load company from MongoDB: {e}")

        return None

    def get_industry_data_types(self, industry: Industry) -> List[IndustryDataType]:
        """
        Get suggested data types for an industry (same types, different descriptions)
        Lấy các loại dữ liệu được gợi ý cho một ngành (cùng types, khác mô tả)
        """
        return self.industry_data_suggestions.get(
            industry, self.industry_data_suggestions["default"]
        )

    async def delete_company_file(self, file_id: str) -> Dict[str, Any]:
        """
        Delete a company file and its data
        Xóa file công ty và dữ liệu của nó
        """
        try:
            if file_id not in self.files:
                return {"status": "error", "error": "File not found"}

            file_data = self.files[file_id]

            # Delete from Qdrant / Xóa khỏi Qdrant
            await self.qdrant_service.delete_company_data(
                company_id=file_data.company_id, file_ids=[file_id]
            )

            # Delete physical file / Xóa file vật lý
            try:
                os.remove(file_data.file_path)
            except OSError:
                pass  # File might already be deleted / File có thể đã bị xóa

            # Get file info for response / Lấy thông tin file cho response
            chunks_deleted = file_data.processed_chunks or 0
            tags_removed = file_data.metadata.get("tags", [])

            # Remove from records / Xóa khỏi records
            del self.files[file_id]

            self.logger.info(f"🗑️ Deleted file {file_id}")

            return {
                "status": "success",
                "file_id": file_id,
                "file_name": file_data.file_name,
                "chunks_deleted": chunks_deleted,
                "vector_points_removed": chunks_deleted,
                "tags_removed": tags_removed,
            }

        except Exception as e:
            self.logger.error(f"❌ Failed to delete file {file_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def update_company_config(
        self, company_id: str, updates: Dict[str, Any]
    ) -> CompanyConfig:
        """
        Update company configuration
        Cập nhật cấu hình công ty
        """
        try:
            if company_id not in self.companies:
                raise ValueError(f"Company {company_id} not found")

            company_config = self.companies[company_id]

            # Update fields / Cập nhật các field
            for field, value in updates.items():
                if hasattr(company_config, field):
                    setattr(company_config, field, value)

            company_config.updated_at = datetime.now()

            self.logger.info(f"✅ Updated company config for {company_id}")

            return company_config

        except Exception as e:
            self.logger.error(f"❌ Failed to update company config: {e}")
            raise e

    def map_backend_data_type(
        self, backend_data_type: str, industry: Industry
    ) -> IndustryDataType:
        """
        Map backend DataType to IndustryDataType (unified for all industries)
        Ánh xạ DataType từ backend sang IndustryDataType (thống nhất cho tất cả ngành)

        All industries use the same data types:
        - company_info -> COMPANY_INFO
        - products -> PRODUCTS (menu for restaurant, rooms for hotel, loans for bank, etc.)
        - services -> SERVICES (restaurant services, hotel services, bank services, etc.)
        - policies -> POLICIES
        - faq -> FAQ
        - knowledge_base -> KNOWLEDGE_BASE
        - other -> OTHER

        The difference is in extraction templates and AI processing, not data types.
        """
        return self.backend_data_type_mapping.get(
            backend_data_type, IndustryDataType.OTHER
        )

    def get_supported_backend_data_types(self) -> List[str]:
        """
        Get list of supported backend data types
        Lấy danh sách các data type được hỗ trợ từ backend
        """
        return list(self.backend_data_type_mapping.keys())

    async def _index_company_basic_info(
        self, company_config: CompanyConfig, metadata: Dict[str, Any]
    ):
        """
        Index company basic information to Qdrant for AI reference
        Index thông tin cơ bản công ty vào Qdrant để AI tham khảo
        """
        try:
            # Create company info document / Tạo tài liệu thông tin công ty
            company_info_text = self._build_company_info_text(company_config, metadata)

            # Create document chunk for company info / Tạo chunk tài liệu cho thông tin công ty
            company_info_chunk = QdrantDocumentChunk(
                chunk_id=str(uuid.uuid4()),
                file_id="company_basic_info",
                file_name="Company Basic Information",
                company_id=company_config.company_id,
                industry=company_config.industry,
                data_type=IndustryDataType.COMPANY_INFO,
                content=company_info_text,
                content_type=IndustryDataType.COMPANY_INFO,  # Add required field
                language=Language.VIETNAMESE,
                chunk_index=0,
                total_chunks=1,
                metadata={
                    "data_source": "backend_registration",
                    "priority": "high",  # Cho AI ưu tiên thông tin công ty
                    "auto_generated": True,
                    "last_updated": datetime.now().isoformat(),
                    **metadata,
                },
            )

            # Add to Qdrant / Thêm vào Qdrant
            await self.qdrant_service.add_document_chunks(
                chunks=[company_info_chunk], company_id=company_config.company_id
            )

            self.logger.info(
                f"📄 Indexed company basic info for {company_config.company_id}"
            )

        except Exception as e:
            self.logger.error(f"❌ Failed to index company basic info: {e}")
            # Don't fail the entire registration process / Không làm thất bại toàn bộ quá trình đăng ký

    def _build_company_info_text(
        self, company_config: CompanyConfig, metadata: Dict[str, Any]
    ) -> str:
        """
        Build structured text from company information for AI processing
        Xây dựng văn bản có cấu trúc từ thông tin công ty để AI xử lý
        """
        info_parts = []

        # Company name and industry / Tên công ty và ngành
        info_parts.append(f"Tên công ty: {company_config.company_name}")
        info_parts.append(f"Ngành nghề: {company_config.industry.value}")

        # Contact information / Thông tin liên hệ
        if metadata.get("email"):
            info_parts.append(f"Email: {metadata['email']}")
        if metadata.get("phone"):
            info_parts.append(f"Số điện thoại: {metadata['phone']}")
        if metadata.get("website"):
            info_parts.append(f"Website: {metadata['website']}")

        # Address / Địa chỉ
        location = metadata.get("location", {})
        if location.get("address"):
            info_parts.append(f"Địa chỉ: {location['address']}")
        if location.get("city"):
            info_parts.append(f"Thành phố: {location['city']}")
        if location.get("country"):
            info_parts.append(f"Quốc gia: {location['country']}")

        # Description / Mô tả
        if metadata.get("description"):
            info_parts.append(f"Mô tả: {metadata['description']}")

        # Social links / Liên kết xã hội
        social_links = metadata.get("social_links", {})
        if social_links:
            social_info = []
            for platform, link in social_links.items():
                if link:
                    social_info.append(f"{platform}: {link}")
            if social_info:
                info_parts.append(f"Mạng xã hội: {', '.join(social_info)}")

        # Business info / Thông tin kinh doanh
        business_info = metadata.get("business_info", {})
        if business_info.get("language"):
            info_parts.append(f"Ngôn ngữ hỗ trợ: {business_info['language']}")
        if business_info.get("timezone"):
            info_parts.append(f"Múi giờ: {business_info['timezone']}")

        return "\n".join(info_parts)

    async def update_company_basic_info(
        self, company_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update company basic information and refresh in Qdrant
        Cập nhật thông tin cơ bản công ty và làm mới trong Qdrant
        """
        try:
            if company_id not in self.companies:
                raise ValueError(f"Company {company_id} not found")

            company_config = self.companies[company_id]
            updated_fields = []

            # Update company name / Cập nhật tên công ty
            if updates.get("company_name"):
                company_config.company_name = updates["company_name"]
                updated_fields.append("company_name")

            # Update industry / Cập nhật ngành nghề
            if updates.get("industry"):
                try:
                    # Validate industry enum
                    from src.models.unified_models import Industry

                    industry_value = updates["industry"].lower()
                    if industry_value in [industry.value for industry in Industry]:
                        company_config.industry = Industry(industry_value)
                        updated_fields.append("industry")
                    else:
                        self.logger.warning(f"Invalid industry value: {industry_value}")
                except Exception as e:
                    self.logger.warning(f"Failed to update industry: {e}")

            # Update contact info from metadata / Cập nhật thông tin liên hệ từ metadata
            metadata = updates.get("metadata", {})
            if metadata:
                if metadata.get("email"):
                    company_config.contact_info["email"] = metadata["email"]
                    updated_fields.append("email")
                if metadata.get("phone"):
                    company_config.contact_info["phone"] = metadata["phone"]
                    updated_fields.append("phone")
                if metadata.get("website"):
                    company_config.contact_info["website"] = metadata["website"]
                    updated_fields.append("website")

                # Update description / Cập nhật mô tả
                if metadata.get("description"):
                    company_config.contact_info["description"] = metadata["description"]
                    updated_fields.append("description")

                # Update location / Cập nhật địa chỉ
                location = metadata.get("location", {})
                if location:
                    if location.get("address"):
                        company_config.contact_info["address"] = location["address"]
                        updated_fields.append("address")
                    if location.get("country"):
                        company_config.contact_info["country"] = location["country"]
                        updated_fields.append("country")
                    if location.get("city"):
                        company_config.contact_info["city"] = location["city"]
                        updated_fields.append("city")

                # Update social links / Cập nhật liên kết xã hội
                social_links = metadata.get("social_links", {})
                if social_links:
                    company_config.contact_info["social_links"].update(social_links)
                    updated_fields.append("social_links")

                # Update language and timezone from business_info
                business_info = metadata.get("business_info", {})
                if business_info:
                    if business_info.get("language"):
                        # Store in contact_info or add separate field if needed
                        company_config.contact_info["language"] = business_info[
                            "language"
                        ]
                        updated_fields.append("language")
                    if business_info.get("timezone"):
                        company_config.contact_info["timezone"] = business_info[
                            "timezone"
                        ]
                        updated_fields.append("timezone")
                    if business_info.get("owner_firebase_uid"):
                        company_config.contact_info["owner_firebase_uid"] = (
                            business_info["owner_firebase_uid"]
                        )
                        updated_fields.append("owner_firebase_uid")
                    if business_info.get("created_at"):
                        company_config.contact_info["created_at"] = business_info[
                            "created_at"
                        ]
                        updated_fields.append("created_at")

            # Remove old company info from Qdrant / Xóa thông tin công ty cũ khỏi Qdrant
            await self.qdrant_service.delete_company_data(
                company_id=company_id, file_ids=["company_basic_info"]
            )

            # Re-index updated company info / Index lại thông tin công ty đã cập nhật
            await self._index_company_basic_info(company_config, metadata)

            company_config.updated_at = datetime.now()

            # Save updated company to MongoDB / Lưu công ty đã cập nhật vào MongoDB
            if updated_fields:
                try:
                    await self.company_db_service.save_company(company_config)
                    self.logger.info(
                        f"💾 Saved updated company to MongoDB: {company_id}"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to save company to MongoDB: {e}")

            self.logger.info(
                f"✅ Updated company basic info for {company_id}: {updated_fields}"
            )

            return {
                "company_id": company_id,
                "updated_fields": updated_fields,
                "vector_points_updated": 1,  # Company info is 1 vector point
            }

        except Exception as e:
            self.logger.error(f"❌ Failed to update company basic info: {e}")
            raise e

    async def delete_files_by_tag(
        self, company_id: str, tag_name: str
    ) -> Dict[str, Any]:
        """
        Delete all files with a specific tag
        Xóa tất cả files có tag cụ thể
        """
        try:
            # Validate company exists / Kiểm tra công ty có tồn tại
            if company_id not in self.companies:
                raise ValueError(f"Company {company_id} not found")

            # Find files with the tag / Tìm files có tag
            company_files = [
                f for f in self.files.values() if f.company_id == company_id
            ]
            files_to_delete = []

            for file in company_files:
                file_tags = file.metadata.get("tags", [])
                if tag_name in file_tags:
                    files_to_delete.append(file)

            if not files_to_delete:
                return {
                    "tag_name": tag_name,
                    "deleted_files": [],
                    "total_files_deleted": 0,
                    "total_chunks_deleted": 0,
                    "total_vector_points_removed": 0,
                }

            # Delete files one by one / Xóa từng file một
            deleted_files = []
            total_chunks_deleted = 0
            total_vector_points_removed = 0

            for file in files_to_delete:
                # Delete from Qdrant / Xóa khỏi Qdrant
                await self.qdrant_service.delete_company_data(
                    company_id=company_id, file_ids=[file.file_id]
                )

                # Delete physical file / Xóa file vật lý
                try:
                    os.remove(file.file_path)
                except OSError:
                    pass  # File might already be deleted

                # Count chunks / Đếm chunks
                chunks_count = file.processed_chunks or 0
                total_chunks_deleted += chunks_count
                total_vector_points_removed += chunks_count

                # Add to deleted list / Thêm vào danh sách đã xóa
                deleted_files.append(
                    {
                        "file_id": file.file_id,
                        "file_name": file.file_name,
                        "chunks_deleted": chunks_count,
                        "vector_points_removed": chunks_count,
                    }
                )

                # Remove from records / Xóa khỏi records
                del self.files[file.file_id]

            self.logger.info(
                f"🗑️ Deleted {len(deleted_files)} files with tag '{tag_name}' for company {company_id}"
            )

            return {
                "tag_name": tag_name,
                "deleted_files": deleted_files,
                "total_files_deleted": len(deleted_files),
                "total_chunks_deleted": total_chunks_deleted,
                "total_vector_points_removed": total_vector_points_removed,
            }

        except Exception as e:
            self.logger.error(f"❌ Failed to delete files by tag: {e}")
            raise e

    async def get_files_by_tag(
        self, company_id: str, tag_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get all files with a specific tag
        Lấy tất cả files có tag cụ thể
        """
        try:
            # Validate company exists / Kiểm tra công ty có tồn tại
            if company_id not in self.companies:
                raise ValueError(f"Company {company_id} not found")

            # Find files with the tag / Tìm files có tag
            company_files = [
                f for f in self.files.values() if f.company_id == company_id
            ]
            tagged_files = []

            for file in company_files:
                file_tags = file.metadata.get("tags", [])
                if tag_name in file_tags:
                    tagged_files.append(
                        {
                            "file_id": file.file_id,
                            "file_name": file.file_name,
                            "original_name": file.metadata.get(
                                "original_file_name", file.file_name
                            ),
                            "status": file.extraction_status.value,
                            "uploaded_at": file.created_at.isoformat(),
                            "chunks_count": file.processed_chunks or 0,
                            "tags": file_tags,
                        }
                    )

            return tagged_files

        except Exception as e:
            self.logger.error(f"❌ Failed to get files by tag: {e}")
            return []

    async def get_company_tags(self, company_id: str) -> List[Dict[str, Any]]:
        """
        Get all tags for a company with statistics
        Lấy tất cả tags của công ty với thống kê
        """
        try:
            # Validate company exists / Kiểm tra công ty có tồn tại
            if company_id not in self.companies:
                raise ValueError(f"Company {company_id} not found")

            # Collect all tags / Thu thập tất cả tags
            company_files = [
                f for f in self.files.values() if f.company_id == company_id
            ]
            tags_info = {}

            for file in company_files:
                file_tags = file.metadata.get("tags", [])
                for tag in file_tags:
                    if tag not in tags_info:
                        tags_info[tag] = {
                            "name": tag,
                            "file_count": 0,
                            "created_at": file.created_at.isoformat(),
                            "last_used": file.created_at.isoformat(),
                        }

                    tags_info[tag]["file_count"] += 1

                    # Update last used time / Cập nhật thời gian sử dụng cuối
                    file_time = file.updated_at or file.created_at
                    if file_time.isoformat() > tags_info[tag]["last_used"]:
                        tags_info[tag]["last_used"] = file_time.isoformat()

            # Convert to list and sort by usage / Chuyển thành list và sắp xếp theo usage
            tags_list = list(tags_info.values())
            tags_list.sort(key=lambda x: x["file_count"], reverse=True)

            return tags_list

        except Exception as e:
            self.logger.error(f"❌ Failed to get company tags: {e}")
            return []

    def _load_companies_from_db(self):
        """
        Load all companies from MongoDB into memory cache
        Load tất cả công ty từ MongoDB vào cache memory
        """
        try:
            companies_data = self.company_db.list_companies(limit=1000)

            for company_data in companies_data:
                company_config = self.company_db.get_company(company_data["company_id"])
                if company_config:
                    self.companies[company_config.company_id] = company_config

            self.logger.info(f"✅ Loaded {len(self.companies)} companies from MongoDB")

        except Exception as e:
            self.logger.error(f"❌ Failed to load companies from MongoDB: {e}")
            # Continue without companies if database fails
            pass


# Global service instance / Instance service toàn cục
company_data_manager = None


def get_company_data_manager() -> CompanyDataManager:
    """Get company data manager instance / Lấy instance manager dữ liệu công ty"""
    global company_data_manager
    if company_data_manager is None:
        from src.core.config import APP_CONFIG

        storage_path = APP_CONFIG.get("data_dir", "./data") + "/companies"
        company_data_manager = CompanyDataManager(storage_base_path=storage_path)

    return company_data_manager
