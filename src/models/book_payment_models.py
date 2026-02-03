"""
Book Payment Models - SePay Payment System
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class PaymentMethod(str, Enum):
    """Payment methods for book purchases"""

    POINTS = "POINTS"
    SEPAY_BANK_TRANSFER = "SEPAY_BANK_TRANSFER"


class OrderStatus(str, Enum):
    """Order status values"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PurchaseType(str, Enum):
    """Types of book purchases"""

    ONE_TIME = "one_time"
    FOREVER = "forever"
    PDF_DOWNLOAD = "pdf_download"


# ==============================================================================
# REQUEST MODELS
# ==============================================================================


class CreatePaymentOrderRequest(BaseModel):
    """Request to create payment order (before SePay checkout)"""

    purchase_type: PurchaseType = Field(
        ..., description="Type of purchase: one_time | forever | pdf_download"
    )


class GrantAccessRequest(BaseModel):
    """Request to grant access from completed order (internal)"""

    order_id: str = Field(..., description="Order ID from book_cash_orders")


class ConfirmOrderRequest(BaseModel):
    """Admin request to manually confirm order"""

    transaction_id: Optional[str] = Field(
        None, description="Optional bank transaction ID"
    )


# ==============================================================================
# RESPONSE MODELS
# ==============================================================================


class BankAccountInfo(BaseModel):
    """Bank account information for transfer"""

    bank_name: str = Field(..., description="Bank name (e.g., Vietcombank)")
    account_number: str = Field(..., description="Bank account number")
    account_name: str = Field(..., description="Account holder name")
    transfer_content: str = Field(
        ..., description="Required transfer content for matching"
    )
    branch_name: Optional[str] = Field(None, description="Bank branch name")


class QROrderResponse(BaseModel):
    """Response after creating QR order"""

    order_id: str = Field(..., description="Unique order ID")
    book_id: str = Field(..., description="Book ID")
    book_title: str = Field(..., description="Book title")
    purchase_type: PurchaseType = Field(..., description="Purchase type")

    # Pricing
    price_vnd: int = Field(..., description="Price in VND")
    currency: str = Field(default="VND", description="Currency")

    # QR Code
    qr_code_url: str = Field(..., description="QR code image URL (base64 or hosted)")
    qr_code_data: str = Field(..., description="Raw QR code content")

    # Bank account info
    bank_account: BankAccountInfo = Field(..., description="Bank account for transfer")

    # Status
    status: OrderStatus = Field(..., description="Order status")
    expires_at: datetime = Field(..., description="Order expiry time (30 minutes)")
    created_at: datetime = Field(..., description="Order creation time")


class OrderStatusResponse(BaseModel):
    """Response for order status check"""

    order_id: str
    book_id: str
    purchase_type: PurchaseType
    status: OrderStatus

    # Payment info
    price_vnd: int
    transaction_id: Optional[str] = None
    paid_at: Optional[datetime] = None

    # Access info
    access_granted: bool
    book_purchase_id: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class GrantAccessResponse(BaseModel):
    """Response after granting access"""

    success: bool
    message: str
    order_id: str
    purchase_id: Optional[str] = None
    user_id: str
    book_id: str


class CashOrderItem(BaseModel):
    """Single cash order item in list"""

    order_id: str
    book_id: str
    book_title: str
    purchase_type: PurchaseType
    price_vnd: int
    status: OrderStatus
    access_granted: bool
    created_at: datetime
    expires_at: datetime


class CashOrderListResponse(BaseModel):
    """Response for listing cash orders"""

    total: int = Field(..., description="Total number of orders")
    orders: list[CashOrderItem] = Field(..., description="List of orders")
    page: int = Field(default=1, description="Current page")
    limit: int = Field(default=20, description="Items per page")


# ==============================================================================
# DATABASE DOCUMENT MODELS (for reference, not API models)
# ==============================================================================


class BookCashOrderDocument(BaseModel):
    """Database document for book_cash_orders collection"""

    order_id: str
    user_id: str
    book_id: str

    # Pricing
    purchase_type: PurchaseType
    price_vnd: int
    currency: str = "VND"

    # Payment info
    payment_method: str = "BANK_TRANSFER_QR"
    payment_provider: str = "VIETQR"
    qr_code_url: str
    qr_code_data: str

    # Bank account (snapshot)
    admin_bank_account: Dict[str, Any]

    # Status tracking
    status: OrderStatus
    transaction_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    confirmed_by: Optional[str] = None  # Admin user_id if manual

    # Access granting
    access_granted: bool = False
    book_purchase_id: Optional[str] = None

    # Metadata
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Timestamps
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        use_enum_values = True
