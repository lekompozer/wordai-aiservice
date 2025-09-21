"""
API Routes for Company Context Management (Admin) - FAQs and Scenarios only
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List

from src.models.company_context import FAQ, Scenario
from src.database.company_db_service import get_company_db_service, CompanyDBService
from src.middleware.auth import verify_internal_api_key

router = APIRouter(
    prefix="/api/admin/companies/{company_id}/context",
    tags=["Admin - Company Context"],
    dependencies=[Depends(verify_internal_api_key)],
)


# ===== FAQs CRUD =====
@router.post("/faqs", response_model=List[FAQ])
async def set_faqs(
    company_id: str,
    faqs: List[FAQ],
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Create or replace all FAQs for the company"""
    try:
        # Update company document with FAQs in metadata
        faq_data = [faq.dict() for faq in faqs]
        update_data = {"metadata.faqs": faq_data}

        success = service.update_company_metadata(company_id, update_data)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Company {company_id} not found"
            )

        return faqs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update FAQs: {str(e)}")


@router.get("/faqs", response_model=List[FAQ])
async def get_faqs(
    company_id: str,
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Retrieve all FAQs for the company"""
    try:
        company_data = service.companies.find_one({"company_id": company_id})
        if not company_data:
            raise HTTPException(
                status_code=404, detail=f"Company {company_id} not found"
            )

        faq_data = company_data.get("metadata", {}).get("faqs", [])
        faqs = [FAQ(**faq) for faq in faq_data]
        return faqs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get FAQs: {str(e)}")


@router.put("/faqs", response_model=List[FAQ])
async def update_faqs(
    company_id: str,
    faqs: List[FAQ],
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Update all FAQs for the company"""
    return await set_faqs(company_id, faqs, service)


@router.post("/faqs/add", response_model=List[FAQ])
async def add_faq(
    company_id: str,
    faq: FAQ,
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Add a single FAQ to existing FAQs"""
    try:
        # Get existing FAQs
        existing_faqs = await get_faqs(company_id, service)
        # Add new FAQ
        existing_faqs.append(faq)
        # Update with all FAQs
        return await set_faqs(company_id, existing_faqs, service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add FAQ: {str(e)}")


@router.delete("/faqs")
async def delete_all_faqs(
    company_id: str,
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Delete all FAQs for the company"""
    try:
        update_data = {"$unset": {"metadata.faqs": ""}}
        result = service.companies.update_one({"company_id": company_id}, update_data)

        if result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail=f"Company {company_id} not found"
            )

        return {"message": "All FAQs deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete FAQs: {str(e)}")


# ===== SCENARIOS CRUD =====
@router.post("/scenarios", response_model=List[Scenario])
async def set_scenarios(
    company_id: str,
    scenarios: List[Scenario],
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Create or replace all scenarios for the company"""
    try:
        # Update company document with scenarios in metadata
        scenario_data = [scenario.dict() for scenario in scenarios]
        update_data = {"metadata.scenarios": scenario_data}

        success = service.update_company_metadata(company_id, update_data)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Company {company_id} not found"
            )

        return scenarios
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update scenarios: {str(e)}"
        )


@router.get("/scenarios", response_model=List[Scenario])
async def get_scenarios(
    company_id: str,
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Retrieve all scenarios for the company"""
    try:
        company_data = service.companies.find_one({"company_id": company_id})
        if not company_data:
            raise HTTPException(
                status_code=404, detail=f"Company {company_id} not found"
            )

        scenario_data = company_data.get("metadata", {}).get("scenarios", [])
        scenarios = [Scenario(**scenario) for scenario in scenario_data]
        return scenarios
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get scenarios: {str(e)}"
        )


@router.put("/scenarios", response_model=List[Scenario])
async def update_scenarios(
    company_id: str,
    scenarios: List[Scenario],
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Update all scenarios for the company"""
    return await set_scenarios(company_id, scenarios, service)


@router.post("/scenarios/add", response_model=List[Scenario])
async def add_scenario(
    company_id: str,
    scenario: Scenario,
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Add a single scenario to existing scenarios"""
    try:
        # Get existing scenarios
        existing_scenarios = await get_scenarios(company_id, service)
        # Add new scenario
        existing_scenarios.append(scenario)
        # Update with all scenarios
        return await set_scenarios(company_id, existing_scenarios, service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add scenario: {str(e)}")


@router.delete("/scenarios")
async def delete_all_scenarios(
    company_id: str,
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Delete all scenarios for the company"""
    try:
        update_data = {"$unset": {"metadata.scenarios": ""}}
        result = service.companies.update_one({"company_id": company_id}, update_data)

        if result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail=f"Company {company_id} not found"
            )

        return {"message": "All scenarios deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete scenarios: {str(e)}"
        )


# ===== FULL CONTEXT =====
@router.get("/", response_model=dict)
async def get_full_context(
    company_id: str,
    service: CompanyDBService = Depends(get_company_db_service),
):
    """
    Gets the entire company context, including FAQs and scenarios.
    This is the endpoint the chat service will call.
    """
    try:
        company_data = service.companies.find_one({"company_id": company_id})
        if not company_data:
            raise HTTPException(
                status_code=404, detail=f"Company {company_id} not found"
            )

        # Extract FAQs and scenarios from metadata
        metadata = company_data.get("metadata", {})
        faqs = metadata.get("faqs", [])
        scenarios = metadata.get("scenarios", [])

        # Format context string for AI
        formatted_context = f"=== THÔNG TIN CÔNG TY ===\n"
        formatted_context += (
            f"Tên công ty: {company_data.get('company_name', 'Chưa có thông tin')}\n"
        )
        formatted_context += (
            f"Ngành nghề: {company_data.get('industry', 'Chưa có thông tin')}\n"
        )

        if faqs:
            formatted_context += f"\n=== CÂU HỎI THƯỜNG GẶP ({len(faqs)} câu) ===\n"
            for i, faq in enumerate(faqs, 1):
                formatted_context += f"{i}. Q: {faq.get('question', '')}\n"
                formatted_context += f"   A: {faq.get('answer', '')}\n"

        if scenarios:
            formatted_context += (
                f"\n=== KỊCH BẢN XỬ LÝ ({len(scenarios)} kịch bản) ===\n"
            )
            for i, scenario in enumerate(scenarios, 1):
                formatted_context += f"{i}. {scenario.get('name', '')}: {scenario.get('description', '')}\n"

        return {
            "company_id": company_id,
            "company_name": company_data.get("company_name", ""),
            "industry": company_data.get("industry", ""),
            "faqs": faqs,
            "scenarios": scenarios,
            "formatted_context": formatted_context,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get full context: {str(e)}"
        )


@router.delete("/")
async def delete_full_context(
    company_id: str,
    service: CompanyDBService = Depends(get_company_db_service),
):
    """Delete all context data (FAQs and scenarios) for the company"""
    try:
        update_data = {"$unset": {"metadata.faqs": "", "metadata.scenarios": ""}}
        result = service.companies.update_one({"company_id": company_id}, update_data)

        if result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail=f"Company {company_id} not found"
            )

        return {"message": "All company context deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete context: {str(e)}"
        )
