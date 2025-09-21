"""
Admin API routes for managing companies.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.models.unified_models import Industry, CompanyConfig, IndustryDataType
from src.services.admin_service import get_admin_service, AdminService
from src.middleware.auth import verify_internal_api_key
from src.utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/companies", tags=["Admin - Companies"])


class CompanyRegistrationRequest(BaseModel):
    company_id: str = Field(..., description="Unique identifier for the company")
    company_name: str = Field(..., description="Display name of the company")
    industry: Industry = Field(..., description="Primary industry of the company")


class LocationInfo(BaseModel):
    """Location information structure"""

    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None


class SocialLinks(BaseModel):
    """Social media links structure"""

    facebook: Optional[str] = None
    twitter: Optional[str] = None
    zalo: Optional[str] = None
    whatsapp: Optional[str] = None
    telegram: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None


class BasicInfoData(BaseModel):
    """Basic info data structure matching backend payload"""

    company_name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    introduction: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    location: Optional[LocationInfo] = None
    logo: Optional[str] = None
    socialLinks: Optional[SocialLinks] = None
    products_summary: Optional[str] = None
    contact_info: Optional[str] = None


class LegacyCompanyBasicInfoUpdateRequest(BaseModel):
    """
    Legacy format for backward compatibility
    Direct fields without basic_info wrapper
    """

    company_name: Optional[str] = None
    industry: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CompanyBasicInfoUpdateRequest(BaseModel):
    """
    New format with basic_info wrapper
    Payload structure: { "basic_info": { ... } }
    """

    basic_info: BasicInfoData = Field(..., description="Basic company information")

    class Config:
        json_schema_extra = {
            "example": {
                "basic_info": {
                    "company_name": "AIA Vietnam Insurance",
                    "industry": "insurance",
                    "description": "Công ty bảo hiểm hàng đầu Việt Nam",
                    "introduction": "Công ty bảo hiểm hàng đầu Việt Nam, cung cấp các giải pháp bảo hiểm và đầu tư toàn diện",
                    "email": "contact@aia.com.vn",
                    "phone": "+84 28 3520 2468",
                    "website": "https://www.aia.com.vn",
                    "location": {
                        "country": "VN",
                        "city": "Ho Chi Minh City",
                        "address": "Unit 1501, 15th Floor, Saigon Trade Center, 37 Ton Duc Thang Street, Ben Nghe Ward, District 1",
                    },
                    "logo": "https://storage.company.com/logos/aia-logo.png",
                    "socialLinks": {
                        "facebook": "https://facebook.com/AIAVietnam",
                        "twitter": "",
                        "zalo": "0123456789",
                        "whatsapp": "",
                        "telegram": "",
                        "instagram": "https://instagram.com/aiavietnam",
                        "linkedin": "https://linkedin.com/company/aia-vietnam",
                    },
                    "products_summary": "Doanh nghiệp hoạt động trong lĩnh vực insurance",
                    "contact_info": "Email: contact@aia.com.vn | Phone: +84 28 3520 2468 | Website: https://www.aia.com.vn | Address: Unit 1501, 15th Floor, Saigon Trade Center, Ho Chi Minh City, VN",
                }
            }
        }


class CompanySearchRequest(BaseModel):
    """Search request for company data"""

    query: str = Field(..., description="Search query text")
    data_types: Optional[List[str]] = Field(
        None, description="Filter by data types (products, services, etc.)"
    )
    limit: int = Field(10, description="Maximum number of results")
    score_threshold: float = Field(0.7, description="Minimum similarity score")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "phở bò",
                "data_types": ["products"],
                "limit": 5,
                "score_threshold": 0.7,
            }
        }


@router.post(
    "/register",
    response_model=CompanyConfig,
    dependencies=[Depends(verify_internal_api_key)],
)
async def register_company(
    request: CompanyRegistrationRequest,
    admin_service: AdminService = Depends(get_admin_service),
):
    """Registers a new company and creates its data collection."""
    try:
        company = await admin_service.register_company(
            company_id=request.company_id,
            company_name=request.company_name,
            industry=request.industry,
        )
        return company
    except Exception as e:
        logger.error(f"Failed to register company {request.company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{company_id}", dependencies=[Depends(verify_internal_api_key)])
async def get_company(
    company_id: str, admin_service: AdminService = Depends(get_admin_service)
):
    """Gets information and stats for a specific company."""
    info = await admin_service.get_company_info(company_id)
    if not info:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"success": True, "data": info}


@router.put("/{company_id}/basic-info", dependencies=[Depends(verify_internal_api_key)])
async def update_company_basic_info(
    company_id: str,
    request: Dict[str, Any],  # Accept raw dict to handle both formats
    admin_service: AdminService = Depends(get_admin_service),
):
    """Updates a company's basic information. Supports both legacy and new format."""
    try:
        # Check if request has 'basic_info' key (new format) or direct fields (legacy)
        if "basic_info" in request:
            # New format with basic_info wrapper
            logger.info(
                f"Using new format with basic_info wrapper for company {company_id}"
            )
            try:
                validated_request = CompanyBasicInfoUpdateRequest(**request)
                basic_info = validated_request.basic_info
            except Exception as e:
                logger.error(f"New format validation failed: {e}")
                raise HTTPException(status_code=422, detail=f"Invalid new format: {e}")
        else:
            # Legacy format - direct fields
            logger.info(f"Using legacy format (direct fields) for company {company_id}")
            try:
                legacy_request = LegacyCompanyBasicInfoUpdateRequest(**request)
                # Convert legacy to new format
                basic_info = BasicInfoData()
                if legacy_request.company_name:
                    basic_info.company_name = legacy_request.company_name
                if legacy_request.industry:
                    basic_info.industry = legacy_request.industry

                # Extract fields from metadata for legacy format
                if legacy_request.metadata:
                    metadata = legacy_request.metadata
                    basic_info.email = metadata.get("email")
                    basic_info.phone = metadata.get("phone")
                    basic_info.website = metadata.get("website")
                    basic_info.description = metadata.get("description")
                    basic_info.logo = metadata.get("logo")

                    # Handle location
                    if "location" in metadata:
                        loc_data = metadata["location"]
                        basic_info.location = LocationInfo(
                            country=loc_data.get("country"),
                            city=loc_data.get("city"),
                            address=loc_data.get("address"),
                        )

                    # Handle social links
                    if "social_links" in metadata:
                        social_data = metadata["social_links"]
                        basic_info.socialLinks = SocialLinks(
                            facebook=social_data.get("facebook"),
                            twitter=social_data.get("twitter"),
                            zalo=social_data.get("zalo"),
                            whatsapp=social_data.get("whatsapp"),
                            telegram=social_data.get("telegram"),
                            instagram=social_data.get("instagram"),
                            linkedin=social_data.get("linkedin"),
                        )

            except Exception as e:
                logger.error(f"Legacy format validation failed: {e}")
                raise HTTPException(
                    status_code=422, detail=f"Invalid legacy format: {e}"
                )

        # Prepare update data with proper mapping (same logic for both formats)
        update_data = {}

        # Map direct fields
        if basic_info.company_name:
            update_data["company_name"] = basic_info.company_name
        if basic_info.industry:
            update_data["industry"] = basic_info.industry

        # Prepare metadata object
        metadata = {}

        # Map basic info fields to metadata
        if basic_info.email:
            metadata["email"] = basic_info.email
        if basic_info.phone:
            metadata["phone"] = basic_info.phone
        if basic_info.website:
            metadata["website"] = basic_info.website
        if basic_info.description:
            metadata["description"] = basic_info.description
        if basic_info.introduction:
            metadata["introduction"] = basic_info.introduction
        if basic_info.logo:
            metadata["logo"] = basic_info.logo
        if basic_info.products_summary:
            metadata["products_summary"] = basic_info.products_summary
        if basic_info.contact_info:
            metadata["contact_info"] = basic_info.contact_info

        # Map nested objects
        if basic_info.location:
            metadata["location"] = basic_info.location.dict(exclude_unset=True)
        if basic_info.socialLinks:
            metadata["social_links"] = basic_info.socialLinks.dict(exclude_unset=True)

        # Add metadata to update_data if not empty
        if metadata:
            update_data["metadata"] = metadata

        logger.info(f"Updating company {company_id} with data: {update_data}")

        result = await admin_service.update_company_basic_info(company_id, update_data)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{company_id}/basic-info", dependencies=[Depends(verify_internal_api_key)]
)
async def create_or_update_company_basic_info(
    company_id: str,
    request: Dict[str, Any],  # Accept raw dict to handle both formats
    admin_service: AdminService = Depends(get_admin_service),
):
    """Creates or updates a company's basic information (POST method). Supports both legacy and new format."""
    # Same logic as PUT method
    return await update_company_basic_info(company_id, request, admin_service)


@router.delete("/{company_id}", dependencies=[Depends(verify_internal_api_key)])
async def delete_company(
    company_id: str, admin_service: AdminService = Depends(get_admin_service)
):
    """Deletes a company and all its associated data."""
    try:
        await admin_service.delete_company(company_id)
        return {
            "success": True,
            "message": f"Company {company_id} and all its data have been deleted.",
        }
    except Exception as e:
        logger.error(f"Failed to delete company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{company_id}/search", dependencies=[Depends(verify_internal_api_key)])
async def search_company_data(
    company_id: str,
    request: CompanySearchRequest,
    admin_service: AdminService = Depends(get_admin_service),
):
    """Search company data using semantic vector search."""
    try:
        # Convert string data_types to IndustryDataType enums
        data_types = None
        if request.data_types:
            data_types = []
            for dt_str in request.data_types:
                try:
                    # Try lowercase first (enum values are lowercase)
                    data_type = IndustryDataType(dt_str.lower())
                    data_types.append(data_type)
                except ValueError:
                    try:
                        # Try as-is
                        data_type = IndustryDataType(dt_str)
                        data_types.append(data_type)
                    except ValueError:
                        logger.warning(
                            f"Invalid data type: {dt_str} - will search all data types"
                        )
                        # Don't break - continue without this filter

            # If no valid data types found, clear the filter to search all
            if not data_types:
                logger.info(
                    "No valid data types specified - searching all company data"
                )
                data_types = None

        results = await admin_service.search_company_data(
            company_id=company_id,
            query=request.query,
            data_types=data_types,
            limit=request.limit,
            score_threshold=request.score_threshold,
        )

        return {
            "success": True,
            "query": request.query,
            "total_results": len(results),
            "data": results,
        }
    except Exception as e:
        logger.error(f"Failed to search company {company_id} data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
