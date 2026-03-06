"""
Desktop License Models
======================
Pydantic models for WordAI Desktop App licensing:
  - Individual license (149,000 VND/year)
  - Enterprise license (Small Team / Business / Custom)
    with user management and Security & Customization Settings
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# ENUMS
# ==============================================================================


class DesktopLicenseProduct(str, Enum):
    INDIVIDUAL = "individual"
    ENTERPRISE_SMALL_TEAM = "enterprise_small_team"
    ENTERPRISE_BUSINESS = "enterprise_business"
    ENTERPRISE_CUSTOM = "enterprise_custom"


class EnterpriseUserRole(str, Enum):
    BILLING_ADMIN = "billing_admin"  # Person who purchased the enterprise plan
    IT_ADMIN = "it_admin"  # IT/config admin (assigned by billing_admin)
    MEMBER = "member"  # Regular employee


class LicenseStatus(str, Enum):
    PENDING = "pending"  # Payment not yet confirmed
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OrderStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"


class SidebarMode(str, Enum):
    FULL = "full"
    LOCAL_FILES_ONLY = "local_files_only"


# ==============================================================================
# PRICING CONSTANTS
# ==============================================================================

DESKTOP_PRICES_VND: Dict[str, int] = {
    DesktopLicenseProduct.INDIVIDUAL: 149_000,
    DesktopLicenseProduct.ENTERPRISE_SMALL_TEAM: 499_000,
    DesktopLicenseProduct.ENTERPRISE_BUSINESS: 1_499_000,
    DesktopLicenseProduct.ENTERPRISE_CUSTOM: 99_000,  # per user
}

ENTERPRISE_MAX_USERS: Dict[str, Optional[int]] = {
    DesktopLicenseProduct.ENTERPRISE_SMALL_TEAM: 5,
    DesktopLicenseProduct.ENTERPRISE_BUSINESS: 20,
    DesktopLicenseProduct.ENTERPRISE_CUSTOM: None,  # set via custom_user_count
}

ENTERPRISE_PLAN_DISPLAY: Dict[str, str] = {
    DesktopLicenseProduct.ENTERPRISE_SMALL_TEAM: "Small Team (5 users)",
    DesktopLicenseProduct.ENTERPRISE_BUSINESS: "Business (20 users)",
    DesktopLicenseProduct.ENTERPRISE_CUSTOM: "Custom",
}


# ==============================================================================
# NESTED SETTINGS MODELS
# ==============================================================================


class ModuleVisibility(BaseModel):
    """Controls which app modules are visible to enterprise users."""

    documents: bool = Field(True, description="Documents module visible")
    online_tests: bool = Field(True, description="Online Tests module visible")
    online_books: bool = Field(
        True, description="Online Books (LetsRead) module visible"
    )
    studyhub: bool = Field(True, description="StudyHub module visible")
    listen_and_learn: bool = Field(True, description="Listen & Learn module visible")
    code_editor: bool = Field(True, description="Code Editor module visible")
    software_lab: bool = Field(True, description="Software Lab module visible")


class HeaderNavVisibility(BaseModel):
    """Controls which header navigation items are visible."""

    usage_and_plan: bool = Field(True, description="Usage & Plan nav item visible")
    community: bool = Field(True, description="Community nav item visible")
    ai_tools: bool = Field(True, description="AI Tools nav item visible")
    feedback: bool = Field(True, description="Feedback nav item visible")


class AIModelConfig(BaseModel):
    """Controls which AI models are enabled for enterprise users."""

    gemini: bool = Field(True)
    chatgpt: bool = Field(True)
    deepseek: bool = Field(True)
    qwen: bool = Field(True)


class CustomizationSettings(BaseModel):
    """
    Enterprise-only Security & Customization Settings.
    Applied org-wide to all enterprise users.
    """

    modules: ModuleVisibility = Field(default_factory=ModuleVisibility)
    header_nav: HeaderNavVisibility = Field(default_factory=HeaderNavVisibility)
    sidebar_mode: SidebarMode = Field(SidebarMode.FULL)
    ai_models: AIModelConfig = Field(default_factory=AIModelConfig)

    @classmethod
    def defaults(cls) -> "CustomizationSettings":
        return cls(
            modules=ModuleVisibility(),
            header_nav=HeaderNavVisibility(),
            sidebar_mode=SidebarMode.FULL,
            ai_models=AIModelConfig(),
        )


# ==============================================================================
# REQUEST MODELS
# ==============================================================================


class CreateIndividualOrderRequest(BaseModel):
    plan_years: int = Field(1, ge=1, le=3, description="License duration in years")


class CreateEnterpriseOrderRequest(BaseModel):
    product: DesktopLicenseProduct = Field(
        ..., description="Enterprise plan type (not individual)"
    )
    organization_name: str = Field(
        ..., min_length=2, max_length=200, description="Company/organization name"
    )
    plan_years: int = Field(1, ge=1, le=3)
    custom_user_count: Optional[int] = Field(
        None,
        ge=2,
        description="Required when product=enterprise_custom. Min 2 users.",
    )

    @field_validator("product")
    @classmethod
    def must_be_enterprise(cls, v: DesktopLicenseProduct) -> DesktopLicenseProduct:
        if v == DesktopLicenseProduct.INDIVIDUAL:
            raise ValueError(
                "Use /individual/create-payment-order for individual license"
            )
        return v

    @field_validator("custom_user_count")
    @classmethod
    def validate_custom_count(cls, v: Optional[int], info: Any) -> Optional[int]:
        # 'values' in v2 Pydantic is accessed via info
        data = info.data if hasattr(info, "data") else {}
        product = data.get("product")
        if product == DesktopLicenseProduct.ENTERPRISE_CUSTOM and not v:
            raise ValueError("custom_user_count is required for enterprise_custom plan")
        if product != DesktopLicenseProduct.ENTERPRISE_CUSTOM and v is not None:
            raise ValueError(
                "custom_user_count is only valid for enterprise_custom plan"
            )
        return v


class AddUsersRequest(BaseModel):
    emails: List[str] = Field(
        ..., min_length=1, description="Email addresses to add to the enterprise"
    )
    role: EnterpriseUserRole = Field(
        EnterpriseUserRole.MEMBER,
        description="Role to assign (member or it_admin). billing_admin cannot be assigned here.",
    )

    @field_validator("role")
    @classmethod
    def cannot_assign_billing_admin(cls, v: EnterpriseUserRole) -> EnterpriseUserRole:
        if v == EnterpriseUserRole.BILLING_ADMIN:
            raise ValueError("Cannot assign billing_admin role via this endpoint")
        return v

    @field_validator("emails")
    @classmethod
    def validate_emails(cls, v: List[str]) -> List[str]:
        if len(v) > 100:
            raise ValueError("Cannot add more than 100 users at a time")
        return [e.strip().lower() for e in v]


class UpdateUserRoleRequest(BaseModel):
    role: EnterpriseUserRole = Field(
        ..., description="New role for the user (member or it_admin)"
    )

    @field_validator("role")
    @classmethod
    def cannot_assign_billing_admin(cls, v: EnterpriseUserRole) -> EnterpriseUserRole:
        if v == EnterpriseUserRole.BILLING_ADMIN:
            raise ValueError("Cannot assign billing_admin role")
        return v


class UpdateCustomizationRequest(BaseModel):
    modules: Optional[ModuleVisibility] = None
    header_nav: Optional[HeaderNavVisibility] = None
    sidebar_mode: Optional[SidebarMode] = None
    ai_models: Optional[AIModelConfig] = None


class GrantLicenseRequest(BaseModel):
    """Internal: called by Node.js payment-service after SePay payment confirmed."""

    order_id: str


# ==============================================================================
# RESPONSE MODELS
# ==============================================================================


class DesktopFeatures(BaseModel):
    """Feature flags returned to the desktop app."""

    documents: bool = True
    online_tests: bool = True
    online_books: bool = True
    studyhub: bool = True
    code_editor: bool = True
    software_lab: bool = True
    ai_tools: bool = True
    listen_and_learn: bool = False  # Requires separate subscription
    music: bool = False  # Requires separate subscription
    learn_conversations: bool = False  # Requires separate subscription


class DesktopLicenseStatusResponse(BaseModel):
    """
    Returned by GET /api/v1/desktop/license/status.
    The Tauri app uses this to determine feature access and UI customization.
    """

    has_license: bool
    license_type: Optional[str] = Field(
        None, description="individual | enterprise | null"
    )
    status: str = Field("none", description="active | expired | none")
    expires_at: Optional[datetime] = None
    days_remaining: Optional[int] = None
    features: DesktopFeatures = Field(default_factory=DesktopFeatures)

    # Enterprise specific
    is_enterprise_admin: bool = False  # True if billing_admin OR it_admin
    is_billing_admin: bool = False
    enterprise_id: Optional[str] = None
    organization_name: Optional[str] = None
    enterprise_key: Optional[str] = Field(
        None, description="Only returned to billing_admin and it_admin users"
    )
    customization: Optional[CustomizationSettings] = Field(
        None, description="Enterprise customization settings (enterprise users only)"
    )


class IndividualOrderResponse(BaseModel):
    success: bool
    order_id: str
    product: str = "individual"
    price_vnd: int
    currency: str = "VND"
    payment_method: str = "SEPAY_BANK_TRANSFER"
    message: str
    expires_at: datetime


class EnterpriseOrderResponse(BaseModel):
    success: bool
    order_id: str
    product: str
    organization_name: str
    max_users: int
    price_vnd: int
    currency: str = "VND"
    payment_method: str = "SEPAY_BANK_TRANSFER"
    message: str
    expires_at: datetime


class EnterpriseUserItem(BaseModel):
    email: str
    user_id: Optional[str] = Field(
        None, description="Firebase UID (null if not yet activated)"
    )
    role: EnterpriseUserRole
    status: str = Field(..., description="pending | active | removed")
    invited_at: datetime
    activated_at: Optional[datetime] = None


class EnterpriseDetailResponse(BaseModel):
    enterprise_id: str
    organization_name: str
    plan: str
    max_users: int
    current_users: int
    status: LicenseStatus
    expires_at: Optional[datetime]
    days_remaining: Optional[int]
    activated_at: Optional[datetime]
    created_at: datetime
    # Sensitive fields (only returned to billing_admin or it_admin)
    enterprise_key: Optional[str] = Field(
        None, description="Only returned to billing_admin and it_admin"
    )
    customization: Optional[CustomizationSettings] = None
    billing_admin_email: Optional[str] = None
    caller_role: str = Field(..., description="Caller's role in this enterprise")


class EnterpriseListItem(BaseModel):
    """Condensed view for list endpoints."""

    enterprise_id: str
    organization_name: str
    plan: str
    max_users: int
    current_users: int
    status: LicenseStatus
    expires_at: Optional[datetime]
    days_remaining: Optional[int]
    activated_at: Optional[datetime]
    created_at: datetime


class EnterpriseListResponse(BaseModel):
    enterprises: List[EnterpriseListItem]
    total: int


class EnterpriseUsersResponse(BaseModel):
    enterprise_id: str
    users: List[EnterpriseUserItem]
    total: int


class AddUsersResponse(BaseModel):
    added: int
    already_in_enterprise: int
    emails_added: List[str]
    emails_skipped: List[str]


class CustomizationPublicResponse(BaseModel):
    """
    Returned by GET /api/v1/desktop/enterprise/config/{enterprise_key}.
    No auth required — used by the Tauri app to fetch org settings.
    """

    enterprise_id: str
    organization_name: str
    customization: CustomizationSettings


class OrderStatusResponse(BaseModel):
    order_id: str
    product: str
    status: OrderStatus
    price_vnd: int
    access_granted: bool
    license_id: Optional[str] = None
    created_at: datetime
    expires_at: datetime


class OrderListResponse(BaseModel):
    orders: List[OrderStatusResponse]
    total: int
