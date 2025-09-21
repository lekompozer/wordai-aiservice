"""
Unified models for multi-industry AI platform
Mô hình dữ liệu thống nhất cho nền tảng AI đa ngành
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Dict, Any, List, Union
from enum import Enum
from datetime import datetime


class Language(str, Enum):
    """Supported languages / Ngôn ngữ hỗ trợ"""

    VIETNAMESE = "vi"
    ENGLISH = "en"
    AUTO_DETECT = "auto"


class UserSource(str, Enum):
    """User source platforms / Các nền tảng nguồn người dùng"""

    MESSENGER = "messenger"  # Facebook Messenger
    INSTAGRAM = "instagram"  # Instagram Direct
    WHATSAPP = "whatsapp"  # WhatsApp Business
    ZALO = "zalo"  # Zalo Official Account
    CHAT_PLUGIN = "chat-plugin"  # Website Chat Widget

    # Frontend-processed channel (1)
    CHATDEMO = "chatdemo"  # Frontend Chat Demo


class Industry(str, Enum):
    """Supported industries / Các ngành nghề hỗ trợ"""

    BANKING = "banking"
    INSURANCE = "insurance"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    RETAIL = "retail"
    FASHION = "fashion"
    INDUSTRIAL = "industrial"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    REAL_ESTATE = "real_estate"
    AUTOMOTIVE = "automotive"
    TECHNOLOGY = "technology"
    CONSULTING = "consulting"
    LOGISTICS = "logistics"
    MANUFACTURING = "manufacturing"
    OTHER = "other"


class ChatIntent(str, Enum):
    """User intent classification / Phân loại ý định người dùng"""

    INFORMATION = "information"  # Hỏi thông tin công ty/sản phẩm/dịch vụ
    SALES_INQUIRY = "sales_inquiry"  # Có nhu cầu mua/đặt hàng/vay
    SUPPORT = "support"  # Hỗ trợ kỹ thuật/khiếu nại
    GENERAL_CHAT = "general_chat"  # Trò chuyện thông thường
    PLACE_ORDER = "place_order"  # Đặt hàng trực tiếp
    UPDATE_ORDER = "update_order"  # Cập nhật đơn hàng đã tồn tại
    CHECK_QUANTITY = "check_quantity"  # Kiểm tra tồn kho/khả dụng


class ChannelType(str, Enum):
    """Communication channel types / Loại kênh giao tiếp"""

    # Backend-processed channels (5)
    MESSENGER = "messenger"  # Facebook Messenger
    INSTAGRAM = "instagram"  # Instagram Direct
    WHATSAPP = "whatsapp"  # WhatsApp Business
    ZALO = "zalo"  # Zalo Official Account
    CHAT_PLUGIN = "chat-plugin"  # Website Chat Widget

    # Frontend-processed channel (1)
    CHATDEMO = "chatdemo"  # Frontend Chat Demo


class PlatformSpecificData(BaseModel):
    """
    Platform-specific user data
    Dữ liệu người dùng theo nền tảng
    """

    browser: Optional[str] = Field(None, description="Browser name / Tên trình duyệt")
    user_agent: Optional[str] = Field(
        None, description="User agent string / Chuỗi user agent"
    )
    platform: Optional[str] = Field(
        None, description="Operating system platform / Nền tảng hệ điều hành"
    )
    language: Optional[str] = Field(
        None, description="Browser language / Ngôn ngữ trình duyệt"
    )
    screen_resolution: Optional[str] = Field(
        None, description="Screen resolution / Độ phân giải màn hình"
    )
    timezone: Optional[str] = Field(
        None, description="User timezone / Múi giờ người dùng"
    )


class LeadSourceInfo(BaseModel):
    """Lead source information for marketing attribution"""

    id: str = Field(..., description="Lead source ID / Mã nguồn lead")
    name: str = Field(..., description="Lead source name / Tên nguồn lead")
    sourceCode: str = Field(..., description="Source code / Mã nguồn")
    category: str = Field(..., description="Category / Danh mục")


class UserInfo(BaseModel):
    """
    User information from different platforms
    Thông tin người dùng từ các nền tảng khác nhau
    """

    user_id: Optional[str] = Field(
        None,
        description="Firebase UID or Platform Account ID / Firebase UID hoặc ID tài khoản nền tảng",
    )
    source: UserSource = Field(
        UserSource.CHATDEMO, description="Source platform / Nền tảng nguồn"
    )
    name: Optional[str] = Field(
        None, description="User display name / Tên hiển thị người dùng"
    )
    email: Optional[str] = Field(
        None, description="User email address / Địa chỉ email người dùng"
    )
    avatar_url: Optional[str] = Field(
        None, description="User avatar URL / URL avatar người dùng"
    )
    device_id: Optional[str] = Field(
        None,
        description="Unique device fingerprint for user tracking / Dấu vết thiết bị duy nhất để theo dõi người dùng",
    )
    platform_specific_data: Optional[PlatformSpecificData] = Field(
        None,
        description="Platform-specific user data / Dữ liệu người dùng theo nền tảng",
    )

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, v):
        """Convert string source to enum, support legacy formats - will be auto-set from channel"""
        if isinstance(v, str):
            # Legacy compatibility mappings (for old webhooks)
            source_map = {
                "web_device": UserSource.CHATDEMO,
                "facebook_messenger": UserSource.MESSENGER,
                "whatsapp": UserSource.WHATSAPP,
                "zalo": UserSource.ZALO,
                "instagram": UserSource.INSTAGRAM,
                "chat_plugin": UserSource.CHAT_PLUGIN,
                # Legacy compatibility mappings
                "website": UserSource.CHAT_PLUGIN,
                "website_plugin": UserSource.CHAT_PLUGIN,
            }
            return source_map.get(v, UserSource.CHATDEMO)
        return v


class ContextData(BaseModel):
    """
    Context data for conversation
    Dữ liệu ngữ cảnh cho cuộc hội thoại
    """

    page_url: Optional[str] = Field(
        None, description="Current page URL / URL trang hiện tại"
    )
    referrer: Optional[str] = Field(None, description="Referrer URL / URL giới thiệu")
    timestamp: Optional[str] = Field(
        None, description="Request timestamp / Thời gian yêu cầu"
    )
    session_duration: Optional[int] = Field(
        None, description="Session duration in seconds / Thời gian phiên tính bằng giây"
    )
    previous_intent: Optional[str] = Field(
        None, description="Previous detected intent / Ý định được phát hiện trước đó"
    )


class MetadataInfo(BaseModel):
    """
    Metadata information for tracking and analytics
    Thông tin metadata để theo dõi và phân tích
    """

    source: Optional[str] = Field(
        None, description="Application source / Nguồn ứng dụng"
    )
    version: Optional[str] = Field(
        None, description="Application version / Phiên bản ứng dụng"
    )
    request_id: Optional[str] = Field(
        None, description="Unique request ID / ID yêu cầu duy nhất"
    )
    correlation_id: Optional[str] = Field(
        None, description="Correlation ID for tracking / ID tương quan để theo dõi"
    )


class UnifiedChatRequest(BaseModel):
    """
    Unified chat request for all industries
    Yêu cầu chat thống nhất cho tất cả ngành nghề
    """

    message: str = Field(..., description="User message / Tin nhắn người dùng")
    message_id: Optional[str] = Field(
        None,
        description="Message ID from backend (auto-generated if not provided) / Mã tin nhắn từ backend (tự động tạo nếu không có)",
    )
    company_id: str = Field(
        ..., description="Company identifier / Mã định danh công ty"
    )
    industry: Union[Industry, str] = Field(
        Industry.OTHER, description="Company industry / Ngành nghề công ty"
    )
    user_info: Optional[UserInfo] = Field(
        None, description="User information / Thông tin người dùng"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID (auto-generated if not provided) / Mã phiên (tự động tạo nếu không có)",
    )
    language: Union[Language, str] = Field(
        Language.AUTO_DETECT, description="Preferred language / Ngôn ngữ ưa thích"
    )
    provider: Optional[str] = Field(
        None,
        description="AI provider (deepseek, chatgpt, gemini, cerebras) / Nhà cung cấp AI",
    )
    context: Optional[ContextData] = Field(
        None, description="Conversation context / Ngữ cảnh hội thoại"
    )
    metadata: Optional[MetadataInfo] = Field(
        None, description="Additional metadata / Dữ liệu bổ sung"
    )

    # NEW FIELDS - Các trường mới
    channel: Optional[ChannelType] = Field(
        ChannelType.CHATDEMO,
        description="Communication channel - determines response routing / Kênh giao tiếp - quyết định routing response",
    )
    lead_source: Optional[LeadSourceInfo] = Field(
        None,
        description="Lead source information for marketing attribution / Thông tin nguồn lead cho phân tích marketing",
    )

    # 🆕 CHAT PLUGIN FIELDS - Trường dành cho chat plugin
    plugin_id: Optional[str] = Field(
        None,
        alias="pluginId",  # Frontend gửi camelCase
        description="Plugin ID for chat-plugin channel / Mã plugin cho kênh chat-plugin",
    )
    customer_domain: Optional[str] = Field(
        None,
        alias="customerDomain",  # Frontend gửi camelCase
        description="Customer domain for CORS and tracking / Domain khách hàng cho CORS và tracking",
    )

    # Pydantic config to allow field aliases from frontend
    model_config = ConfigDict()

    @staticmethod
    def get_source_from_channel(channel: ChannelType) -> UserSource:
        """
        Auto-map channel to user_info.source for unified processing
        Tự động map channel sang user_info.source để xử lý thống nhất
        """
        channel_to_source_map = {
            ChannelType.CHATDEMO: UserSource.CHATDEMO,
            ChannelType.MESSENGER: UserSource.MESSENGER,
            ChannelType.INSTAGRAM: UserSource.INSTAGRAM,
            ChannelType.WHATSAPP: UserSource.WHATSAPP,
            ChannelType.ZALO: UserSource.ZALO,
            ChannelType.CHAT_PLUGIN: UserSource.CHAT_PLUGIN,
        }
        return channel_to_source_map.get(channel, UserSource.CHATDEMO)

    @field_validator("industry", mode="before")
    @classmethod
    def validate_industry(cls, v):
        """Convert string industry to enum, support both UPPERCASE and lowercase"""
        if isinstance(v, str):
            # Convert to lowercase for enum matching
            industry_str = v.lower()
            try:
                return Industry(industry_str)
            except ValueError:
                # If invalid industry, default to OTHER
                return Industry.OTHER
        return v

    @field_validator("language", mode="before")
    @classmethod
    def validate_language(cls, v):
        """Convert string language to enum, support both UPPERCASE and lowercase"""
        if isinstance(v, str):
            # Language mapping for frontend compatibility
            lang_map = {
                "ENGLISH": Language.ENGLISH,
                "VIETNAMESE": Language.VIETNAMESE,
                "AUTO": Language.AUTO_DETECT,
                "en": Language.ENGLISH,
                "vi": Language.VIETNAMESE,
                "auto": Language.AUTO_DETECT,
            }
            return lang_map.get(v, Language.AUTO_DETECT)
        return v

    def __init__(self, **data):
        super().__init__(**data)

        # Auto-generate message_id if not provided (for frontend requests)
        if not self.message_id:
            import uuid

            timestamp = int(datetime.now().timestamp())
            self.message_id = f"msg_{timestamp}_{str(uuid.uuid4())[:8]}"

        # Create default user_info if not provided (ONLY if frontend doesn't send user_info)
        if not self.user_info:
            # Generate anonymous user info with defaults
            timestamp = int(datetime.now().timestamp())
            self.user_info = UserInfo(
                user_id=f"anonymous_{timestamp}",
                source=UserSource.CHATDEMO,  # Will be overridden below
                device_id=f"device_{timestamp}",
            )

        # ✨ AUTO-SET SOURCE FROM CHANNEL - Tự động set source từ channel
        # This ensures consistency and eliminates need for separate source validation
        if self.channel:
            correct_source = self.get_source_from_channel(self.channel)
            if self.user_info:
                # ALWAYS set source from channel to ensure consistency
                self.user_info.source = correct_source
            else:
                # Fallback: create user_info with correct source (only if no user_info from frontend)
                timestamp = int(datetime.now().timestamp())
                self.user_info = UserInfo(
                    user_id=f"anonymous_{timestamp}",
                    source=correct_source,
                    device_id=f"device_{timestamp}",
                )

        # Auto-generate session_id if not provided
        if not self.session_id:
            # Generate session ID based on user_id and timestamp for uniqueness
            timestamp = int(datetime.now().timestamp())
            user_id = (
                self.user_info.user_id
                if self.user_info and self.user_info.user_id
                else f"anonymous_{timestamp}"
            )
            self.session_id = f"{user_id}_{timestamp}"


class IntentDetectionResult(BaseModel):
    """
    Intent detection result
    Kết quả phát hiện ý định
    """

    intent: ChatIntent = Field(
        ..., description="Detected intent / Ý định được phát hiện"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score / Điểm tin cậy"
    )
    language: Language = Field(
        ..., description="Detected language / Ngôn ngữ phát hiện"
    )
    extracted_info: Dict[str, Any] = Field(
        default_factory=dict, description="Extracted information / Thông tin trích xuất"
    )
    reasoning: str = Field(
        ..., description="Reasoning for the decision / Lý do quyết định"
    )


class UnifiedChatResponse(BaseModel):
    """
    Unified chat response
    Phản hồi chat thống nhất
    """

    response: str = Field(..., description="AI response / Phản hồi AI")
    message_id: str = Field(
        ..., description="Message ID from request / Mã tin nhắn từ request"
    )
    intent: ChatIntent = Field(..., description="Detected intent / Ý định phát hiện")
    confidence: float = Field(..., description="Intent confidence / Độ tin cậy ý định")
    language: Language = Field(..., description="Response language / Ngôn ngữ phản hồi")
    sources: Optional[List[Dict[str, Any]]] = Field(
        None, description="Information sources / Nguồn thông tin"
    )
    suggestions: Optional[List[str]] = Field(
        None, description="Follow-up suggestions / Gợi ý tiếp theo"
    )
    session_id: str = Field(..., description="Session ID / Mã phiên")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Response timestamp / Thời gian phản hồi",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Response metadata / Dữ liệu phản hồi"
    )
    attachments: Optional[List[Dict[str, Any]]] = Field(
        None, description="Media attachments (images, files) / Tệp đính kèm (ảnh, file)"
    )


class CompanyConfig(BaseModel):
    """
    Company configuration for multi-industry support
    Cấu hình công ty cho hỗ trợ đa ngành
    """

    company_id: str = Field(..., description="Unique company ID / Mã công ty duy nhất")
    company_name: str = Field(..., description="Company name / Tên công ty")
    industry: Industry = Field(..., description="Primary industry / Ngành chính")
    languages: List[Language] = Field(
        default=[Language.VIETNAMESE],
        description="Supported languages / Ngôn ngữ hỗ trợ",
    )

    # Data configuration / Cấu hình dữ liệu
    qdrant_collection: str = Field(
        ..., description="Qdrant collection name / Tên collection Qdrant"
    )
    data_sources: Dict[str, str] = Field(
        default_factory=dict, description="Data source paths / Đường dẫn nguồn dữ liệu"
    )

    # AI configuration / Cấu hình AI
    ai_config: Dict[str, Any] = Field(
        default_factory=dict, description="AI behavior settings / Cài đặt hành vi AI"
    )
    industry_config: Dict[str, Any] = Field(
        default_factory=dict, description="Industry-specific config / Cấu hình ngành"
    )

    # Business configuration / Cấu hình kinh doanh
    business_hours: Optional[Dict[str, Any]] = Field(
        None, description="Business operating hours / Giờ hoạt động"
    )
    contact_info: Optional[Dict[str, Any]] = Field(
        None, description="Contact information / Thông tin liên hệ"
    )

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class LanguageDetectionResult(BaseModel):
    """
    Language detection result
    Kết quả phát hiện ngôn ngữ
    """

    language: Language = Field(
        ..., description="Detected language / Ngôn ngữ phát hiện"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Detection confidence / Độ tin cậy phát hiện"
    )
    indicators: List[str] = Field(
        default_factory=list,
        description="Language indicators found / Dấu hiệu ngôn ngữ tìm thấy",
    )


class ConversationHistory(BaseModel):
    """
    Conversation history entry
    Mục lịch sử hội thoại
    """

    role: str = Field(
        ..., description="Message role (user/assistant) / Vai trò tin nhắn"
    )
    content: str = Field(..., description="Message content / Nội dung tin nhắn")
    intent: Optional[ChatIntent] = Field(
        None, description="Message intent / Ý định tin nhắn"
    )
    language: Optional[Language] = Field(
        None, description="Message language / Ngôn ngữ tin nhắn"
    )
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = Field(None)


class FileType(str, Enum):
    """Supported file types for data extraction / Loại file hỗ trợ trích xuất dữ liệu"""

    IMAGE = "image"  # Menu images, room photos, product catalogs
    PDF = "pdf"  # Documents, price lists, brochures
    EXCEL = "excel"  # Data sheets, pricing tables
    WORD = "word"  # Service descriptions, policies
    TEXT = "text"  # Simple text files
    JSON = "json"  # Structured data
    CSV = "csv"  # Data tables


class DataExtractionStatus(str, Enum):
    """Data extraction status / Trạng thái trích xuất dữ liệu"""

    PENDING = "pending"  # Waiting for processing
    PROCESSING = "processing"  # Currently being processed
    COMPLETED = "completed"  # Successfully processed
    FAILED = "failed"  # Failed to process
    REJECTED = "rejected"  # Rejected due to validation


class IndustryDataType(str, Enum):
    """Industry-specific data types / Loại dữ liệu theo ngành"""

    # Restaurant / Nhà hàng
    MENU_ITEMS = "menu_items"
    RESTAURANT_INFO = "restaurant_info"
    RESTAURANT_SERVICES = "restaurant_services"
    PROMOTIONS = "promotions"

    # Hotel / Khách sạn
    ROOM_TYPES = "room_types"
    ROOM_PRICING = "room_pricing"
    HOTEL_SERVICES = "hotel_services"
    HOTEL_AMENITIES = "hotel_amenities"

    # Banking / Ngân hàng
    LOAN_PRODUCTS = "loan_products"
    BANK_SERVICES = "bank_services"
    INTEREST_RATES = "interest_rates"
    BRANCH_INFO = "branch_info"

    # Education / Giáo dục
    COURSES = "courses"
    EDUCATION_SERVICES = "education_services"
    TUITION_FEES = "tuition_fees"
    SCHEDULES = "schedules"
    FACULTY_INFO = "faculty_info"

    # Healthcare / Y tế
    MEDICAL_SERVICES = "medical_services"
    DOCTOR_INFO = "doctor_info"
    APPOINTMENT_PRICING = "appointment_pricing"

    # Insurance / Bảo hiểm
    INSURANCE_PRODUCTS = "insurance_products"
    INSURANCE_SERVICES = "insurance_services"
    CLAIMS_INFO = "claims_info"

    # Retail / Bán lẻ
    PRODUCTS = "products"  # For general product data
    SERVICES = "services"  # For general service data
    PRODUCT_CATALOG = "product_catalog"
    PRICING_INFO = "pricing_info"
    INVENTORY = "inventory"

    # Fashion / Thời trang
    FASHION_PRODUCTS = "fashion_products"
    FASHION_SERVICES = "fashion_services"
    COLLECTIONS = "collections"

    # Real Estate / Bất động sản
    PROPERTY_LISTINGS = "property_listings"
    REAL_ESTATE_SERVICES = "real_estate_services"

    # Automotive / Ô tô
    VEHICLE_LISTINGS = "vehicle_listings"
    AUTOMOTIVE_SERVICES = "automotive_services"

    # Technology / Công nghệ
    TECH_PRODUCTS = "tech_products"
    TECH_SERVICES = "tech_services"
    SOFTWARE_LICENSING = "software_licensing"

    # General / Chung
    COMPANY_INFO = "company_info"
    CONTACT_INFO = "contact_info"
    POLICIES = "policies"
    FAQ = "faq"
    KNOWLEDGE_BASE = "knowledge_base"
    OTHER = "other"  # For miscellaneous data types


class CompanyDataFile(BaseModel):
    """
    Company data file information
    Thông tin file dữ liệu công ty
    """

    file_id: str = Field(..., description="Unique file ID / Mã file duy nhất")
    company_id: str = Field(..., description="Company ID / Mã công ty")
    file_name: str = Field(..., description="Original file name / Tên file gốc")
    file_type: FileType = Field(..., description="File type / Loại file")
    file_size: int = Field(..., description="File size in bytes / Kích thước file")
    file_path: str = Field(..., description="Storage path / Đường dẫn lưu trữ")

    industry: Industry = Field(..., description="Company industry / Ngành công ty")
    data_type: IndustryDataType = Field(
        ..., description="Expected data type / Loại dữ liệu dự kiến"
    )

    extraction_status: DataExtractionStatus = Field(DataExtractionStatus.PENDING)
    extraction_result: Optional[Dict[str, Any]] = Field(
        None, description="Extracted data / Dữ liệu trích xuất"
    )
    extraction_error: Optional[str] = Field(
        None, description="Extraction error / Lỗi trích xuất"
    )

    processed_chunks: int = Field(
        0, description="Number of processed chunks / Số chunk đã xử lý"
    )
    total_chunks: int = Field(0, description="Total chunks / Tổng số chunk")

    uploaded_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = Field(None)

    metadata: Optional[Dict[str, Any]] = Field(None)


class QdrantDocumentChunk(BaseModel):
    """
    Document chunk for Qdrant storage
    Chunk tài liệu để lưu trữ Qdrant
    """

    chunk_id: str = Field(..., description="Unique chunk ID / Mã chunk duy nhất")
    company_id: str = Field(..., description="Company ID / Mã công ty")
    file_id: str = Field(..., description="Source file ID / Mã file nguồn")

    content: str = Field(..., description="Original chunk content / Nội dung chunk gốc")
    content_for_embedding: str = Field(
        ...,
        description="Optimized content for AI embedding and reading / Nội dung tối ưu cho AI embedding và đọc",
    )
    content_type: IndustryDataType = Field(
        ..., description="Content type / Loại nội dung"
    )

    embedding_vector: Optional[List[float]] = Field(
        None, description="Vector embedding / Vector nhúng"
    )

    # Industry-specific structured data / Dữ liệu có cấu trúc theo ngành
    structured_data: Optional[Dict[str, Any]] = Field(None)

    # Metadata for search and filtering / Metadata cho tìm kiếm và lọc
    language: Language = Field(Language.VIETNAMESE)
    industry: Industry = Field(...)

    # Geographic and temporal metadata / Metadata địa lý và thời gian
    location: Optional[str] = Field(
        None, description="Location reference / Tham chiếu vị trí"
    )
    valid_from: Optional[datetime] = Field(
        None, description="Valid from date / Có hiệu lực từ"
    )
    valid_until: Optional[datetime] = Field(
        None, description="Valid until date / Có hiệu lực đến"
    )

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class DataExtractionRequest(BaseModel):
    """
    Request for data extraction from uploaded files
    Yêu cầu trích xuất dữ liệu từ file đã upload
    """

    file_ids: List[str] = Field(
        ..., description="List of file IDs to process / Danh sách mã file cần xử lý"
    )
    company_id: str = Field(..., description="Company ID / Mã công ty")
    industry: Industry = Field(..., description="Company industry / Ngành công ty")

    # Extraction preferences / Ưa thích trích xuất
    target_language: Language = Field(
        Language.VIETNAMESE, description="Target language / Ngôn ngữ đích"
    )
    extraction_mode: str = Field(
        "auto",
        description="auto, manual, or guided / tự động, thủ công, hoặc hướng dẫn",
    )

    # Industry-specific extraction hints / Gợi ý trích xuất theo ngành
    extraction_hints: Optional[Dict[str, Any]] = Field(None)

    # Processing options / Tùy chọn xử lý
    chunk_size: int = Field(
        1000, description="Chunk size for processing / Kích thước chunk xử lý"
    )
    overlap_size: int = Field(
        200, description="Overlap between chunks / Overlap giữa các chunk"
    )


class CompanyDataStats(BaseModel):
    """
    Company data statistics
    Thống kê dữ liệu công ty
    """

    company_id: str = Field(..., description="Company ID / Mã công ty")
    industry: Industry = Field(..., description="Company industry / Ngành công ty")

    # File statistics / Thống kê file
    total_files: int = Field(0)
    total_file_size: int = Field(
        0, description="Total file size in bytes / Tổng kích thước file"
    )

    # Processing statistics / Thống kê xử lý
    pending_files: int = Field(0)
    processing_files: int = Field(0)
    completed_files: int = Field(0)
    failed_files: int = Field(0)

    # Qdrant statistics / Thống kê Qdrant
    total_chunks: int = Field(
        0, description="Total chunks in Qdrant / Tổng chunk trong Qdrant"
    )
    qdrant_collection_size: int = Field(
        0, description="Collection size / Kích thước collection"
    )

    # Data type breakdown / Phân tích theo loại dữ liệu
    data_type_counts: Dict[IndustryDataType, int] = Field(default_factory=dict)

    last_updated: datetime = Field(default_factory=datetime.now)


class IndustrySpecificData(BaseModel):
    """
    Base class for industry-specific structured data
    Lớp cơ sở cho dữ liệu có cấu trúc theo ngành
    """

    industry: Industry = Field(..., description="Industry type / Loại ngành")
    language: Language = Field(Language.VIETNAMESE)
    last_updated: datetime = Field(default_factory=datetime.now)


class RestaurantMenuItem(IndustrySpecificData):
    """Restaurant menu item / Món ăn trong menu nhà hàng"""

    industry: Industry = Field(default=Industry.RESTAURANT)

    item_name: str = Field(..., description="Dish name / Tên món")
    item_name_en: Optional[str] = Field(
        None, description="English name / Tên tiếng Anh"
    )

    category: str = Field(..., description="Food category / Danh mục món ăn")
    sub_category: Optional[str] = Field(None, description="Sub category / Danh mục phụ")
    price: float = Field(..., description="Price / Giá")
    currency: str = Field("VND", description="Currency / Tiền tệ")
    price_unit: str = Field("per_serving", description="Price unit / Đơn vị giá")

    description: Optional[str] = Field(None, description="Description / Mô tả")
    ingredients: Optional[List[str]] = Field(
        None, description="Ingredients / Nguyên liệu"
    )

    spicy_level: Optional[int] = Field(
        None, ge=0, le=5, description="Spicy level / Độ cay"
    )
    is_vegetarian: bool = Field(False, description="Vegetarian option / Lựa chọn chay")
    is_available: bool = Field(True, description="Currently available / Hiện có sẵn")

    cooking_time: Optional[int] = Field(
        None, description="Cooking time in minutes / Thời gian nấu"
    )
    image_url: Optional[str] = Field(None, description="Image URL / URL hình ảnh")

    # Additional fields from template
    sku: Optional[str] = Field(None, description="Dish code / Mã món")
    tags: Optional[List[str]] = Field(None, description="Tags / Thẻ tag")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class HotelRoomType(IndustrySpecificData):
    """Hotel room type information / Thông tin loại phòng khách sạn"""

    industry: Industry = Field(default=Industry.HOTEL)

    room_type: str = Field(..., description="Room type name / Tên loại phòng")
    room_type_en: Optional[str] = Field(
        None, description="English name / Tên tiếng Anh"
    )

    capacity: int = Field(..., description="Maximum occupancy / Sức chứa tối đa")
    bed_type: str = Field(..., description="Bed configuration / Cấu hình giường")

    # Pricing / Giá cả
    hourly_rate: Optional[float] = Field(None, description="Hourly rate / Giá theo giờ")
    daily_rate: float = Field(..., description="Daily rate / Giá theo ngày")
    weekend_rate: Optional[float] = Field(
        None, description="Weekend rate / Giá cuối tuần"
    )
    currency: str = Field("VND", description="Currency / Tiền tệ")

    # Room features / Tiện nghi phòng
    amenities: List[str] = Field(
        default_factory=list, description="Room amenities / Tiện nghi phòng"
    )
    room_size: Optional[float] = Field(
        None, description="Room size in m2 / Diện tích phòng"
    )

    # Availability / Tình trạng
    is_available: bool = Field(True, description="Currently available / Hiện có sẵn")
    total_rooms: int = Field(
        ..., description="Total rooms of this type / Tổng số phòng loại này"
    )

    image_urls: List[str] = Field(
        default_factory=list, description="Room images / Hình ảnh phòng"
    )

    # Additional fields from template
    sku: Optional[str] = Field(None, description="Room code / Mã phòng")
    view_type: Optional[str] = Field(None, description="View type / Loại view")


class BankLoanProduct(IndustrySpecificData):
    """Bank loan product information / Thông tin sản phẩm vay ngân hàng"""

    industry: Industry = Field(default=Industry.BANKING)

    product_name: str = Field(..., description="Loan product name / Tên sản phẩm vay")
    product_name_en: Optional[str] = Field(
        None, description="English name / Tên tiếng Anh"
    )

    loan_type: str = Field(..., description="Loan type / Loại vay")
    category: str = Field(..., description="Product category / Danh mục sản phẩm")

    # Interest rates / Lãi suất
    interest_rate_min: float = Field(
        ..., description="Minimum interest rate / Lãi suất tối thiểu"
    )
    interest_rate_max: float = Field(
        ..., description="Maximum interest rate / Lãi suất tối đa"
    )

    # Loan limits / Giới hạn vay
    min_amount: float = Field(
        ..., description="Minimum loan amount / Số tiền vay tối thiểu"
    )
    max_amount: float = Field(
        ..., description="Maximum loan amount / Số tiền vay tối đa"
    )
    currency: str = Field("VND", description="Currency / Tiền tệ")

    # Terms / Điều khoản
    min_term_months: int = Field(
        ..., description="Minimum term in months / Thời hạn tối thiểu"
    )
    max_term_months: int = Field(
        ..., description="Maximum term in months / Thời hạn tối đa"
    )

    # Requirements / Yêu cầu
    requirements: List[str] = Field(
        default_factory=list, description="Loan requirements / Yêu cầu vay"
    )
    collateral_required: bool = Field(
        False, description="Collateral required / Yêu cầu tài sản đảm bảo"
    )

    # Additional info / Thông tin bổ sung
    processing_fee: Optional[float] = Field(
        None, description="Processing fee / Phí xử lý"
    )
    description: Optional[str] = Field(
        None, description="Product description / Mô tả sản phẩm"
    )

    # Additional fields from template
    sku: Optional[str] = Field(None, description="Product code / Mã sản phẩm")
    availability: str = Field("available", description="Availability / Tình trạng")


class EducationCourse(IndustrySpecificData):
    """Education course information / Thông tin khóa học giáo dục"""

    industry: Industry = Field(default=Industry.EDUCATION)

    course_name: str = Field(..., description="Course name / Tên khóa học")
    course_name_en: Optional[str] = Field(
        None, description="English name / Tên tiếng Anh"
    )

    course_code: Optional[str] = Field(None, description="Course code / Mã khóa học")
    level: str = Field(..., description="Course level / Cấp độ khóa học")
    category: str = Field(..., description="Course category / Danh mục khóa học")

    # Pricing / Học phí
    tuition_fee: float = Field(..., description="Tuition fee / Học phí")
    currency: str = Field("VND", description="Currency / Tiền tệ")

    # Schedule / Lịch trình
    duration_hours: int = Field(
        ..., description="Course duration in hours / Thời lượng khóa học"
    )
    schedule: str = Field(..., description="Class schedule / Lịch học")
    start_date: Optional[datetime] = Field(
        None, description="Start date / Ngày bắt đầu"
    )
    end_date: Optional[datetime] = Field(None, description="End date / Ngày kết thúc")

    # Course details / Chi tiết khóa học
    description: Optional[str] = Field(
        None, description="Course description / Mô tả khóa học"
    )
    prerequisites: List[str] = Field(
        default_factory=list, description="Prerequisites / Điều kiện tiên quyết"
    )
    learning_outcomes: List[str] = Field(
        default_factory=list, description="Learning outcomes / Kết quả học tập"
    )

    # Instructor / Giảng viên
    instructor: Optional[str] = Field(
        None, description="Instructor name / Tên giảng viên"
    )
    max_students: Optional[int] = Field(
        None, description="Maximum students / Số học viên tối đa"
    )

    is_available: bool = Field(True, description="Currently available / Hiện có sẵn")

    # Additional fields from template
    sku: Optional[str] = Field(None, description="Course SKU / Mã khóa học")
    sub_category: Optional[str] = Field(None, description="Sub category / Danh mục phụ")


class GenericProduct(IndustrySpecificData):
    """Generic product for industries without specific models"""

    industry: Industry = Field(...)

    name: str = Field(..., description="Product name / Tên sản phẩm")
    name_en: Optional[str] = Field(None, description="English name / Tên tiếng Anh")
    description: Optional[str] = Field(None, description="Description / Mô tả")
    sku: Optional[str] = Field(None, description="Product SKU / Mã sản phẩm")

    category: str = Field(..., description="Main category / Danh mục chính")
    sub_category: Optional[str] = Field(None, description="Sub category / Danh mục phụ")

    price: Optional[float] = Field(None, description="Price / Giá")
    currency: str = Field("VND", description="Currency / Tiền tệ")
    price_unit: Optional[str] = Field(None, description="Price unit / Đơn vị giá")

    availability: str = Field("available", description="Availability / Tình trạng")
    tags: Optional[List[str]] = Field(None, description="Tags / Thẻ tag")

    brand: Optional[str] = Field(None, description="Brand / Thương hiệu")
    model: Optional[str] = Field(None, description="Model / Mẫu mã")

    specifications: Optional[Dict[str, Any]] = Field(
        None, description="Specifications / Thông số kỹ thuật"
    )
    features: Optional[List[str]] = Field(None, description="Features / Tính năng")

    image_urls: Optional[List[str]] = Field(
        None, description="Image URLs / URL hình ảnh"
    )
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
