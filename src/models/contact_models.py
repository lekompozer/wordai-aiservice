"""
Contact form models
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from enum import Enum


class ContactPurpose(str, Enum):
    """Contact purpose types"""

    BUSINESS_COOPERATION = "business_cooperation"  # Hợp tác kinh doanh
    INVESTMENT = "investment"  # Đầu tư
    TECHNICAL_SUPPORT = "technical_support"  # Hỗ trợ kỹ thuật
    OTHER = "other"  # Khác


class ContactRequest(BaseModel):
    """Contact form submission model"""

    full_name: str = Field(..., min_length=2, max_length=100, description="Họ và tên")
    email: EmailStr = Field(..., description="Email liên hệ")
    phone: Optional[str] = Field(None, max_length=20, description="Số điện thoại")
    company: Optional[str] = Field(
        None, max_length=100, description="Tên công ty/tổ chức"
    )
    purpose: ContactPurpose = Field(..., description="Mục đích liên hệ")
    message: str = Field(
        ..., min_length=10, max_length=2000, description="Nội dung tin nhắn"
    )
