"""
Document generation models for quotes, contracts, and appendices
"""

from datetime import datetime
from typing import Dict, List, Optional, Literal, Any, Union
from pydantic import BaseModel, Field, validator
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, handler=None):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")
        return field_schema


class CompanyInfo(BaseModel):
    """Thông tin công ty"""

    name: Optional[str] = Field(None, description="Tên công ty")
    address: Optional[str] = Field(None, description="Địa chỉ công ty")
    city: Optional[str] = Field(None, description="Thành phố")
    tax_code: Optional[str] = Field(None, description="Mã số thuế")
    representative: Optional[str] = Field(None, description="Người đại diện")
    position: Optional[str] = Field(None, description="Chức vụ người đại diện")
    phone: Optional[str] = Field(None, description="Số điện thoại")
    email: Optional[str] = Field(None, description="Email liên hệ")
    fax: Optional[str] = Field(None, description="Số fax")
    website: Optional[str] = Field(None, description="Website công ty")
    social_link: Optional[str] = Field(None, description="Liên kết mạng xã hội")
    logo: Optional[str] = Field(None, description="Logo công ty (base64 hoặc URL)")
    bank_account: Optional[str] = Field(None, description="Số tài khoản ngân hàng")
    bank_name: Optional[str] = Field(None, description="Tên ngân hàng")

    @validator("email")
    def validate_email(cls, v):
        if v and "@" not in v:
            raise ValueError("Email không hợp lệ")
        return v

    @validator("tax_code")
    def validate_tax_code(cls, v):
        if v and len(v) < 10:
            raise ValueError("Mã số thuế phải có ít nhất 10 ký tự")
        return v


class CustomerInfo(BaseModel):
    """Thông tin khách hàng"""

    name: Optional[str] = Field(None, description="Tên khách hàng/công ty")
    address: Optional[str] = Field(None, description="Địa chỉ")
    contact_person: Optional[str] = Field(None, description="Người liên hệ")
    position: Optional[str] = Field(None, description="Chức vụ")
    phone: Optional[str] = Field(None, description="Số điện thoại")
    email: Optional[str] = Field(None, description="Email")
    tax_code: Optional[str] = Field(
        None, description="Mã số thuế (nếu là doanh nghiệp)"
    )

    @validator("email")
    def validate_email(cls, v):
        if v and "@" not in v:
            raise ValueError("Email không hợp lệ")
        return v


class ProductInfo(BaseModel):
    """Thông tin sản phẩm/dịch vụ"""

    name: str = Field(..., description="Tên sản phẩm/dịch vụ")
    description: str = Field(..., description="Mô tả chi tiết")
    quantity: int = Field(..., gt=0, description="Số lượng")
    unit: str = Field(..., description="Đơn vị tính (cái, bộ, tháng, ...)")
    unit_price: float = Field(..., gt=0, description="Đơn giá")
    total_price: float = Field(..., gt=0, description="Thành tiền")
    specifications: Optional[Dict[str, Any]] = Field(
        None, description="Thông số kỹ thuật"
    )
    warranty_period: Optional[str] = Field(None, description="Thời hạn bảo hành")
    delivery_time: Optional[str] = Field(None, description="Thời gian giao hàng")

    @validator("total_price")
    def validate_total_price(cls, v, values):
        if "quantity" in values and "unit_price" in values:
            expected_total = values["quantity"] * values["unit_price"]
            if abs(v - expected_total) > 0.01:  # Allow small floating point differences
                raise ValueError("Thành tiền phải bằng số lượng x đơn giá")
        return v


class PaymentTerms(BaseModel):
    """Điều khoản thanh toán"""

    payment_method: Optional[str] = Field(None, description="Phương thức thanh toán")
    payment_schedule: Optional[str] = Field(None, description="Lịch thanh toán")
    currency: str = Field(default="VND", description="Đơn vị tiền tệ")
    advance_payment_percent: Optional[float] = Field(
        None, ge=0, le=100, description="% tạm ứng"
    )
    final_payment_terms: Optional[str] = Field(
        None, description="Điều kiện thanh toán cuối"
    )


class DocumentTemplate(BaseModel):
    """Template tài liệu"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    type: Literal["quote", "contract", "appendix"] = Field(
        ..., description="Loại tài liệu"
    )
    subtype: str = Field(
        ..., description="Phân loại con (standard, premium, enterprise, ...)"
    )
    name: str = Field(..., description="Tên template")
    description: str = Field(..., description="Mô tả template")
    template_content: str = Field(..., description="Nội dung template (HTML/Markdown)")
    variables: List[str] = Field(..., description="Danh sách biến trong template")
    file_path: Optional[str] = Field(None, description="Đường dẫn file template Word")
    is_active: bool = Field(default=True, description="Trạng thái hoạt động")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"arbitrary_types_allowed": True}


class DocumentRequest(BaseModel):
    """Yêu cầu tạo tài liệu"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: Optional[str] = Field(None, description="ID người dùng")
    firebase_uid: Optional[str] = Field(None, description="Firebase UID")
    type: Literal["quote", "contract", "appendix"] = Field(
        ..., description="Loại tài liệu"
    )
    template_id: Union[str, PyObjectId] = Field(..., description="ID template sử dụng")

    # Input data
    company_info: CompanyInfo = Field(..., description="Thông tin công ty")
    customer_info: CustomerInfo = Field(..., description="Thông tin khách hàng")
    products: List[ProductInfo] = Field(..., description="Danh sách sản phẩm/dịch vụ")
    payment_terms: Optional[PaymentTerms] = Field(
        None, description="Điều khoản thanh toán"
    )
    additional_terms: Optional[str] = Field(None, description="Điều khoản bổ sung")

    # Processing info
    generated_content: Optional[str] = Field(None, description="Nội dung được tạo")
    ai_processing_time: Optional[float] = Field(
        None, description="Thời gian xử lý AI (giây)"
    )
    file_url: Optional[str] = Field(None, description="URL file tải về")
    file_path: Optional[str] = Field(None, description="Đường dẫn file trên server")

    # Status tracking
    status: Literal["processing", "completed", "failed", "expired"] = Field(
        default="processing", description="Trạng thái xử lý"
    )
    error_message: Optional[str] = Field(None, description="Thông báo lỗi nếu có")
    expires_at: Optional[datetime] = Field(None, description="Thời hạn file")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("products")
    def validate_products(cls, v):
        if not v or len(v) == 0:
            raise ValueError("Phải có ít nhất 1 sản phẩm/dịch vụ")
        return v

    @property
    def total_amount(self) -> float:
        """Tính tổng tiền của tất cả sản phẩm"""
        return sum(product.total_price for product in self.products)

    @property
    def total_quantity(self) -> int:
        """Tính tổng số lượng sản phẩm"""
        return sum(product.quantity for product in self.products)

    model_config = {"arbitrary_types_allowed": True}


class DocumentResponse(BaseModel):
    """Response cho API tạo tài liệu"""

    request_id: str = Field(..., description="ID yêu cầu")
    status: str = Field(..., description="Trạng thái")
    message: str = Field(..., description="Thông báo")
    file_url: Optional[str] = Field(None, description="URL tải file")
    expires_at: Optional[datetime] = Field(None, description="Thời hạn file")
    processing_time: Optional[float] = Field(None, description="Thời gian xử lý")


class TemplateListResponse(BaseModel):
    """Response danh sách templates"""

    templates: List[DocumentTemplate] = Field(..., description="Danh sách templates")
    total: int = Field(..., description="Tổng số templates")


# Request models for API endpoints
class QuoteRequest(BaseModel):
    """Request tạo báo giá"""

    template_id: str = Field(..., description="ID template")
    company_info: CompanyInfo
    customer_info: CustomerInfo
    products: List[ProductInfo]
    payment_terms: Optional[PaymentTerms] = None
    additional_terms: Optional[str] = None
    validity_period: Optional[str] = Field(
        None, description="Thời hạn hiệu lực báo giá"
    )
    vat_rate: Optional[float] = Field(
        default=10.0, description="Tỷ lệ VAT (%) - mặc định 10%"
    )
    notes: Optional[str] = Field(None, description="Ghi chú báo giá")

    @validator("vat_rate")
    def validate_vat_rate(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Tỷ lệ VAT phải từ 0% đến 100%")
        return v


class ContractRequest(BaseModel):
    """Request tạo hợp đồng"""

    template_id: str = Field(..., description="ID template")
    company_info: CompanyInfo
    customer_info: CustomerInfo
    products: List[ProductInfo]
    payment_terms: PaymentTerms
    additional_terms: Optional[str] = None
    contract_duration: Optional[str] = Field(None, description="Thời hạn hợp đồng")
    effective_date: Optional[datetime] = Field(None, description="Ngày hiệu lực")


class AppendixRequest(BaseModel):
    """Request tạo phụ lục"""

    template_id: str = Field(..., description="ID template")
    parent_contract_id: Optional[str] = Field(None, description="ID hợp đồng gốc")
    company_info: CompanyInfo
    customer_info: CustomerInfo
    products: List[ProductInfo]
    changes_description: str = Field(..., description="Mô tả thay đổi")
    additional_terms: Optional[str] = None


class AITemplateRequest(BaseModel):
    """Request AI tạo/điều chỉnh template"""

    document_type: Literal["quote", "contract", "appendix"] = Field(
        ..., description="Loại tài liệu"
    )
    template_option: Literal["use_existing", "create_new"] = Field(
        ..., description="Lựa chọn template"
    )
    base_template_id: Optional[str] = Field(
        None, description="ID template gốc (nếu dùng existing)"
    )

    # AI Model selection
    ai_model: Literal["deepseek", "qwen-2.5b-instruct", "gemini-2.5-flash"] = Field(
        default="deepseek", description="AI model để tạo template"
    )

    # Data để AI hiểu context
    company_info: Optional[CompanyInfo] = None
    customer_info: Optional[CustomerInfo] = None
    products: Optional[List[ProductInfo]] = None
    payment_terms: Optional[PaymentTerms] = None
    additional_terms: Optional[str] = None

    # Custom requirements cho AI
    custom_requirements: Optional[str] = Field(
        None, description="Yêu cầu đặc biệt cho template"
    )
    language: str = Field(default="vi", description="Ngôn ngữ tài liệu")
    style: str = Field(default="professional", description="Phong cách tài liệu")


class AITemplateResponse(BaseModel):
    """Response từ AI với template structure"""

    template_structure: Dict[str, Any] = Field(
        ..., description="Cấu trúc template được AI tạo"
    )
    placeholders: Dict[str, str] = Field(
        ..., description="Các placeholder và giá trị mặc định"
    )
    sections: List[Dict[str, Any]] = Field(..., description="Các phần của tài liệu")
    styling: Dict[str, Any] = Field(..., description="Thông tin về style và format")
    metadata: Dict[str, Any] = Field(..., description="Metadata về template")


# NEW QUOTE WORKFLOW MODELS
class QuoteSettings(BaseModel):
    """Settings ban đầu cho quote - lưu trong database"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str = Field(..., description="ID người dùng")
    firebase_uid: str = Field(..., description="Firebase UID")

    # Thông tin cơ bản
    company_info: CompanyInfo = Field(..., description="Thông tin công ty")
    customer_info: CustomerInfo = Field(..., description="Thông tin khách hàng")
    payment_terms: PaymentTerms = Field(..., description="Điều khoản thanh toán")

    # Template
    template_id: Optional[str] = Field(None, description="ID template được chọn")
    template_content: Optional[str] = Field(None, description="Nội dung template")

    # Metadata
    is_active: bool = Field(default=True, description="Trạng thái hoạt động")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"arbitrary_types_allowed": True}


class QuoteGenerationRequest(BaseModel):
    """Request tạo quote mới hoặc chỉnh sửa quote"""

    # Template selection (REQUIRED for new flow)
    template_id: str = Field(..., description="ID của template được chọn")

    # Settings reference (optional for backward compatibility)
    settings_id: Optional[str] = Field(None, description="ID của quote settings")

    # Company and customer info (can be passed directly)
    company_name: Optional[str] = Field(None, description="Tên công ty")
    customer_name: Optional[str] = Field(None, description="Tên khách hàng")

    # Project details (can be passed as structured data)
    project_details: Optional[Dict[str, Any]] = Field(
        None, description="Chi tiết dự án"
    )

    # User query
    user_query: str = Field(
        ..., description="Yêu cầu của người dùng để tạo/chỉnh sửa quote"
    )

    # Optional: File hiện tại (cho chỉnh sửa)
    current_file_path: Optional[str] = Field(
        None, description="Đường dẫn file docx hiện tại (nếu chỉnh sửa)"
    )

    # AI model choice
    ai_model: Literal["gemini-pro-2.5"] = Field(
        default="gemini-pro-2.5", description="AI model để xử lý"
    )

    # Generation type
    generation_type: Literal["new", "edit"] = Field(
        default="new", description="Tạo mới hoặc chỉnh sửa"
    )


class QuoteGenerationResponse(BaseModel):
    """Response sau khi tạo quote"""

    quote_id: str = Field(..., description="ID của quote được tạo")
    file_path: str = Field(..., description="Đường dẫn file docx được tạo")
    download_url: str = Field(..., description="URL để download file")
    ai_generated_content: Dict[str, Any] = Field(
        ..., description="Nội dung được AI tạo ra"
    )
    processing_time: float = Field(..., description="Thời gian xử lý")
    status: Literal["success", "error"] = Field(..., description="Trạng thái")
    message: str = Field(..., description="Thông báo kết quả")


class QuoteRecord(BaseModel):
    """Record lưu trữ quote đã tạo"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    quote_id: str = Field(..., description="Unique quote identifier")
    user_id: str = Field(..., description="ID người dùng")
    firebase_uid: str = Field(..., description="Firebase UID")
    settings_id: str = Field(..., description="ID của quote settings")

    # Quote data
    user_query: str = Field(..., description="Query của user")
    generation_type: Literal["new", "edit"] = Field(..., description="Loại tạo quote")
    template_id: Optional[str] = Field(None, description="Template ID đã sử dụng")
    ai_generated_content: Dict[str, Any] = Field(..., description="Nội dung AI tạo")

    # File storage info (R2)
    r2_file_key: str = Field(..., description="R2 file key")
    file_name: str = Field(..., description="Tên file hiển thị")
    download_url: str = Field(..., description="Pre-signed download URL")
    url_expires_at: datetime = Field(..., description="URL expiry time")
    file_size_bytes: int = Field(default=0, description="File size in bytes")

    # Legacy file path (deprecated, keep for backward compatibility)
    file_path: Optional[str] = Field("", description="Legacy file path (deprecated)")
    file_size: Optional[int] = Field(None, description="Legacy file size (deprecated)")

    # Version tracking
    version: int = Field(default=1, description="Phiên bản của quote")
    parent_quote_id: Optional[str] = Field(
        None, description="ID quote gốc (nếu là chỉnh sửa)"
    )

    # Processing info
    ai_model: str = Field(default="gemini-2.5-pro", description="AI model đã sử dụng")
    processing_time: float = Field(..., description="Thời gian xử lý")

    # Status
    status: Literal["completed", "processing", "failed", "archived", "deleted"] = Field(
        default="completed"
    )
    download_count: int = Field(default=0, description="Số lần download")
    expires_at: Optional[datetime] = Field(None, description="Thời hạn file")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"arbitrary_types_allowed": True}


class QuoteGenerationRequest(BaseModel):
    """Request tạo quote"""

    settings_id: str = Field(..., description="ID của settings đã lưu")
    template_id: Optional[str] = Field(None, description="ID template được chọn")
    user_query: str = Field(..., description="Yêu cầu của user")
    generation_type: str = Field(
        default="new", description="Loại generation: new hoặc edit"
    )
    items: List[Dict[str, Any]] = Field(
        default=[], description="Danh sách items trong quote"
    )


class SaveQuoteSettingsRequest(BaseModel):
    """Request lưu settings ban đầu"""

    company_info: CompanyInfo = Field(..., description="Thông tin công ty")
    customer_info: CustomerInfo = Field(..., description="Thông tin khách hàng")
    payment_terms: PaymentTerms = Field(..., description="Điều khoản thanh toán")
    template_id: Optional[str] = Field(None, description="ID template được chọn")


# Đã xóa định nghĩa QuoteSettings thứ hai - sử dụng định nghĩa ở trên với template_content field


class DocumentTemplate(BaseModel):
    """Template document cho quote generation - Updated với tất cả fields cần thiết"""

    # Basic identification
    id: str = Field(..., alias="_id", description="Template unique identifier")
    name: str = Field(..., description="Tên template")
    description: Optional[str] = Field(None, description="Mô tả template")
    type: str = Field(default="quote", description="Loại template")
    subtype: Optional[str] = Field(None, description="Phân loại chi tiết template")
    category: Optional[str] = Field(None, description="Danh mục template")

    # Status and permissions
    is_active: bool = Field(default=True, description="Template có đang hoạt động")
    user_id: Optional[str] = Field(
        None, description="User ID hoặc 'system' cho system templates"
    )
    is_public: bool = Field(default=False, description="Template có public không")
    is_system_template: bool = Field(
        default=False, description="Có phải system template không"
    )

    # 🔥 FILES - Quan trọng nhất!
    files: Optional[Dict[str, Any]] = Field(
        None,
        description="File URLs và metadata",
        example={
            "docx_url": "https://static.example.com/template.docx",
            "pdf_url": "https://static.example.com/template.pdf",
            "thumbnail_urls": [],
        },
    )

    # 🧠 AI ANALYSIS - Chứa placeholders, sections, etc.
    ai_analysis: Optional[Dict[str, Any]] = Field(
        None,
        description="Kết quả phân tích AI của template",
        example={
            "confidence_score": 0.95,
            "analysis_version": "1.0",
            "placeholders": {},
            "sections": [],
            "document_structure": {},
            "business_logic": {},
        },
    )

    # 📊 VALIDATION và METADATA
    validation: Optional[Dict[str, Any]] = Field(
        None,
        description="Validation results",
        example={"is_valid": True, "errors": [], "warnings": []},
    )

    # 📈 USAGE TRACKING
    usage_count: int = Field(default=0, description="Số lần template được sử dụng")

    # 🕒 TIMESTAMPS
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(None, description="Thời gian cập nhật")

    model_config = {"populate_by_name": True, "extra": "allow"}


class GetUserQuoteDataResponse(BaseModel):
    """Response trả về dữ liệu quote gần nhất của user"""

    settings: Optional[QuoteSettings] = Field(None, description="Settings gần nhất")
    recent_quotes: List[QuoteRecord] = Field(
        default=[], description="Các quote gần đây"
    )
    available_templates: List[DocumentTemplate] = Field(
        default=[], description="Templates có sẵn"
    )


class QuoteGenerationRequest(BaseModel):
    """Request model for quote generation"""

    settings_id: str = Field(..., description="ID của quote settings")
    user_query: str = Field(..., description="User query hoặc instruction")
    template_id: Optional[str] = Field(None, description="Template ID to use")
    generation_type: str = Field(default="new", description="Type: new or edit")

    # Optional fields for direct quote data
    company_name: Optional[str] = Field(None, description="Tên công ty")
    customer_name: Optional[str] = Field(None, description="Tên khách hàng")
    customer_company: Optional[str] = Field(None, description="Công ty khách hàng")
    services: Optional[List[Dict[str, Any]]] = Field(
        None, description="Danh sách dịch vụ"
    )
    total_amount: Optional[float] = Field(None, description="Tổng tiền")
    valid_until: Optional[str] = Field(None, description="Hiệu lực đến ngày")
    additional_terms: Optional[str] = Field(None, description="Điều khoản bổ sung")
    user_notes: Optional[str] = Field(
        None, description="Ghi chú từ người dùng nhập vào"
    )


class QuoteGenerationResponse(BaseModel):
    """Response model for quote generation"""

    quote_id: str = Field(..., description="ID của quote đã tạo")
    status: str = Field(..., description="Trạng thái: success/error")
    message: str = Field(..., description="Thông báo kết quả")
    ai_content: Optional[str] = Field(None, description="Nội dung AI đã tạo")
    file_path: Optional[str] = Field(None, description="Đường dẫn file DOCX")

    # R2 storage fields
    file_key: Optional[str] = Field(None, description="R2 file key")
    download_url: Optional[str] = Field(None, description="Pre-signed download URL")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")
    url_expires_at: Optional[datetime] = Field(None, description="URL expiry time")

    # Metadata
    generation_time_seconds: Optional[float] = Field(None, description="Thời gian tạo")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Thời gian hoàn thành"
    )
