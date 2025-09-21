"""
Pydantic Models for Company Context
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ScenarioType(str, Enum):
    """
    Enum for different types of customer scenarios
    """

    SALES = "SALES"
    ASK_COMPANY_INFORMATION = "ASK_COMPANY_INFORMATION"
    SUPPORT = "SUPPORT"
    GENERAL_INFORMATION = "GENERAL_INFORMATION"


class SocialLinks(BaseModel):
    facebook: Optional[str] = Field(default="", description="Facebook page URL")
    twitter: Optional[str] = Field(default="", description="X (formerly Twitter) URL")
    zalo: Optional[str] = Field(default="", description="Zalo contact")
    whatsapp: Optional[str] = Field(default="", description="WhatsApp contact")
    telegram: Optional[str] = Field(default="", description="Telegram contact")


class Location(BaseModel):
    country: Optional[str] = Field(default="", description="Country")
    city: Optional[str] = Field(default="", description="City")
    address: Optional[str] = Field(default="", description="Full address")


class BasicInfo(BaseModel):
    """
    Basic company information that matches MongoDB structure
    Thông tin cơ bản công ty phù hợp với cấu trúc MongoDB
    """

    # Basic Info
    id: Optional[str] = Field(default=None, description="Company ID")
    name: str = Field(..., description="Company name")
    industry: Optional[str] = Field(default="", description="Company industry")
    location: Optional[Location] = Field(
        default_factory=Location, description="Company location"
    )
    description: Optional[str] = Field(default="", description="Company description")
    logo: Optional[str] = Field(default="", description="Logo image URL")

    # Contact Info
    email: Optional[str] = Field(default="", description="Contact email")
    phone: Optional[str] = Field(default="", description="Contact phone")
    website: Optional[str] = Field(default="", description="Company website")

    # Social Links
    socialLinks: Optional[SocialLinks] = Field(
        default_factory=SocialLinks, description="Social media links"
    )

    def to_formatted_string(self) -> str:
        """Convert BasicInfo to formatted string for AI context"""
        parts = []

        if self.name:
            parts.append(f"Tên công ty: {self.name}")

        if self.industry:
            parts.append(f"Ngành nghề: {self.industry}")

        if self.description:
            parts.append(f"Mô tả: {self.description}")

        if self.location and (
            self.location.address or self.location.city or self.location.country
        ):
            location_parts = []
            if self.location.address:
                location_parts.append(self.location.address)
            if self.location.city and self.location.city not in (
                self.location.address or ""
            ):
                location_parts.append(self.location.city)
            if self.location.country and self.location.country not in (
                self.location.address or ""
            ):
                location_parts.append(self.location.country)
            if location_parts:
                parts.append(f"Địa chỉ: {', '.join(location_parts)}")

        # Contact info
        contact_parts = []
        if self.phone:
            contact_parts.append(f"Điện thoại: {self.phone}")
        if self.email:
            contact_parts.append(f"Email: {self.email}")
        if self.website:
            contact_parts.append(f"Website: {self.website}")

        if contact_parts:
            parts.append("Thông tin liên hệ: " + ", ".join(contact_parts))

        # Social links
        if self.socialLinks:
            social_parts = []
            if self.socialLinks.facebook:
                social_parts.append(f"Facebook: {self.socialLinks.facebook}")
            if self.socialLinks.zalo:
                social_parts.append(f"Zalo: {self.socialLinks.zalo}")
            if self.socialLinks.whatsapp:
                social_parts.append(f"WhatsApp: {self.socialLinks.whatsapp}")
            if self.socialLinks.telegram:
                social_parts.append(f"Telegram: {self.socialLinks.telegram}")

            if social_parts:
                parts.append("Mạng xã hội: " + ", ".join(social_parts))

        return "\n".join(parts) if parts else ""


class FAQ(BaseModel):
    question: str = Field(..., description="FAQ question")
    answer: str = Field(..., description="FAQ answer")
    category: Optional[str] = Field(default="", description="FAQ category")


class Scenario(BaseModel):
    """
    Updated Scenario model with new structure for intent-based scenarios
    """

    type: ScenarioType = Field(
        ...,
        description="Type of scenario: SALES, ASK_COMPANY_INFORMATION, SUPPORT, GENERAL_INFORMATION",
    )
    name: str = Field(..., description="Scenario name/title")
    description: str = Field(..., description="Description of the scenario")
    reference_messages: List[str] = Field(
        default_factory=list,
        description="List of reference messages that trigger this scenario",
    )

    # Legacy support for old format (optional, for backward compatibility)
    situation: Optional[str] = Field(
        default="", description="Legacy: Customer situation description"
    )
    solution: Optional[str] = Field(
        default="", description="Legacy: Recommended solution/response"
    )
    category: Optional[str] = Field(default="", description="Legacy: Scenario category")
    steps: Optional[List[str]] = Field(
        default_factory=list, description="Legacy: scenario steps"
    )

    def to_formatted_string(self) -> str:
        """Convert Scenario to formatted string for AI context"""
        parts = []

        parts.append(f"Loại: {self.type.value}")
        parts.append(f"Tên kịch bản: {self.name}")
        parts.append(f"Mô tả: {self.description}")

        if self.reference_messages:
            parts.append("Tin nhắn tham khảo:")
            for i, msg in enumerate(self.reference_messages, 1):
                parts.append(f"  {i}. {msg}")

        return "\n".join(parts)


class CompanyContext(BaseModel):
    basic_info: Optional[BasicInfo] = None
    faqs: List[FAQ] = []
    scenarios: List[Scenario] = []


class BackendBasicInfoPayload(BaseModel):
    """
    Model for handling basic info payload from backend with different field structure
    Model để xử lý payload basic info từ backend với cấu trúc field khác
    """

    company_name: str = Field(..., description="Company name from backend")
    contact_info: Optional[str] = Field(default="", description="Contact information")
    introduction: Optional[str] = Field(default="", description="Company introduction")
    products_summary: Optional[str] = Field(
        default="", description="Products/services summary"
    )

    def to_basic_info(self, company_id: str) -> BasicInfo:
        """Convert backend payload to BasicInfo model"""
        # Parse contact_info to extract email, phone, address
        email = ""
        phone = ""
        address = ""

        if self.contact_info:
            contact_lines = self.contact_info.split("|")
            for line in contact_lines:
                line = line.strip()
                if line.startswith("Email:"):
                    email = line.replace("Email:", "").strip()
                elif line.startswith("Phone:"):
                    phone = line.replace("Phone:", "").strip()
                elif line.startswith("Address:"):
                    address = line.replace("Address:", "").strip()

        # Parse address for location
        location = Location()
        if address:
            location.address = address
            # Try to extract city and country from address
            if "Hồ Chí Minh" in address or "TP. Hồ Chí Minh" in address:
                location.city = "Hồ Chí Minh"
                location.country = "Việt Nam"
            elif "Hà Nội" in address:
                location.city = "Hà Nội"
                location.country = "Việt Nam"
            elif "Việt Nam" in address:
                location.country = "Việt Nam"

        # Determine industry from products_summary
        industry = ""
        if self.products_summary:
            summary_lower = self.products_summary.lower()
            if "insurance" in summary_lower or "bảo hiểm" in summary_lower:
                industry = "insurance"
            elif "banking" in summary_lower or "ngân hàng" in summary_lower:
                industry = "banking"
            elif "restaurant" in summary_lower or "nhà hàng" in summary_lower:
                industry = "restaurant"
            elif "hotel" in summary_lower or "khách sạn" in summary_lower:
                industry = "hotel"
            else:
                industry = "other"

        return BasicInfo(
            id=company_id,
            name=self.company_name,
            industry=industry,
            location=location,
            description=self.introduction or "",
            email=email,
            phone=phone,
        )
