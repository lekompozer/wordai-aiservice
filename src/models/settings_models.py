"""Models for quote settings management"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class CompanyInfo(BaseModel):
    """Company information for quotes"""

    name: str = Field(..., description="Tên công ty")
    address: str = Field(..., description="Địa chỉ công ty")
    phone: str = Field(..., description="Số điện thoại")
    email: str = Field(..., description="Email")
    website: Optional[str] = Field(None, description="Website")
    representative: str = Field(..., description="Tên người đại diện")
    position: str = Field(..., description="Chức vụ người đại diện")
    logo_url: Optional[str] = Field(None, description="URL logo công ty")


class QuoteNotes(BaseModel):
    """Default notes for quotes"""

    default_notes: Optional[str] = Field(
        None, description="Ghi chú mặc định cho báo giá"
    )
    payment_terms: Optional[str] = Field(
        None, description="Điều khoản thanh toán mặc định"
    )


class UserQuoteSettings(BaseModel):
    """User's quote settings"""

    id: Optional[str] = Field(None, alias="_id")
    user_id: str = Field(..., description="User ID")
    company_info: CompanyInfo = Field(..., description="Thông tin công ty")
    quote_notes: QuoteNotes = Field(
        default_factory=QuoteNotes, description="Ghi chú mặc định"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = {"populate_by_name": True}


class UpdateQuoteSettingsRequest(BaseModel):
    """Request model for updating quote settings"""

    company_info: CompanyInfo = Field(..., description="Thông tin công ty")
    quote_notes: Optional[QuoteNotes] = Field(None, description="Ghi chú mặc định")


class QuoteSettingsResponse(BaseModel):
    """Response model for quote settings"""

    success: bool = Field(..., description="Trạng thái thành công")
    message: str = Field(..., description="Thông báo")
    data: Optional[UserQuoteSettings] = Field(None, description="Dữ liệu settings")
