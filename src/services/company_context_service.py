"""
Service for managing Company Context data.
"""

from typing import Dict, List, Optional
import uuid
from datetime import datetime
from src.models.company_context import BasicInfo, FAQ, Scenario, CompanyContext, ScenarioType
from src.models.unified_models import (
    QdrantDocumentChunk,
    IndustryDataType,
    Language,
    Industry,
)
from src.services.qdrant_company_service import get_qdrant_service
from src.utils.logger import setup_logger

# In-memory database for simplicity
# In a real application, this would be a connection to Redis, MongoDB, or a relational DB.
_context_db: Dict[str, CompanyContext] = {}

logger = setup_logger(__name__)


class CompanyContextService:
    def __init__(self, db: Dict[str, CompanyContext]):
        self.db = db
        self.qdrant_service = None  # Lazy initialization

    async def _get_qdrant_service(self):
        """Lazy initialize Qdrant service"""
        if self.qdrant_service is None:
            self.qdrant_service = get_qdrant_service()
        return self.qdrant_service

    async def _index_context_to_qdrant(self, company_id: str):
        """Index company context to Qdrant for hybrid search with proper data types"""
        try:
            context = await self._get_or_create_context(company_id)
            qdrant_service = await self._get_qdrant_service()

            chunks_to_index = []

            # 1. Index basic info as company_info (but this won't be searched in Qdrant)
            if context.basic_info:
                basic_info_text = context.basic_info.to_formatted_string()
                if basic_info_text.strip():
                    basic_chunk = QdrantDocumentChunk(
                        chunk_id=f"basic_info_{company_id}_{uuid.uuid4()}",
                        company_id=company_id,
                        file_id="company_basic_info",
                        content=basic_info_text,
                        content_for_embedding=basic_info_text,
                        content_type=IndustryDataType.COMPANY_INFO,
                        language=Language.VIETNAMESE,
                        industry=Industry.OTHER,
                    )
                    chunks_to_index.append(basic_chunk)

            # 2. Index FAQs with data_type: "faq"
            if context.faqs:
                for i, faq in enumerate(context.faqs):
                    faq_text = f"Câu hỏi: {faq.question}\nTrả lời: {faq.answer}"
                    if faq.category:
                        faq_text = f"Danh mục: {faq.category}\n{faq_text}"
                    
                    faq_chunk = QdrantDocumentChunk(
                        chunk_id=f"faq_{company_id}_{i}_{uuid.uuid4()}",
                        company_id=company_id,
                        file_id=f"company_faqs",
                        content=faq_text,
                        content_for_embedding=faq_text,
                        content_type=IndustryDataType.FAQ,  # t3. dataType: faq
                        language=Language.VIETNAMESE,
                        industry=Industry.OTHER,
                    )
                    chunks_to_index.append(faq_chunk)

            # 3. Index scenarios with data_type: "knowledge_base"
            if context.scenarios:
                for i, scenario in enumerate(context.scenarios):
                    scenario_text = f"Tình huống: {scenario.situation}\nGiải pháp: {scenario.solution}"
                    if scenario.category:
                        scenario_text = f"Danh mục: {scenario.category}\n{scenario_text}"
                    
                    scenario_chunk = QdrantDocumentChunk(
                        chunk_id=f"scenario_{company_id}_{i}_{uuid.uuid4()}",
                        company_id=company_id,
                        file_id=f"company_scenarios",
                        content=scenario_text,
                        content_for_embedding=scenario_text,
                        content_type=IndustryDataType.KNOWLEDGE_BASE,  # t4. dataType: knowledge_base
                        language=Language.VIETNAMESE,
                        industry=Industry.OTHER,
                    )
                    chunks_to_index.append(scenario_chunk)

            # Add all chunks to Qdrant
            if chunks_to_index:
                result = await qdrant_service.add_document_chunks(
                    chunks=chunks_to_index, company_id=company_id
                )
                
                logger.info(f"✅ Indexed {len(chunks_to_index)} context chunks to Qdrant for {company_id}")
                logger.info(f"   � Basic info: {1 if context.basic_info else 0}")
                logger.info(f"   📋 FAQs: {len(context.faqs) if context.faqs else 0}")
                logger.info(f"   🎭 Scenarios: {len(context.scenarios) if context.scenarios else 0}")
                return result
            else:
                logger.info(f"📝 No context to index for company {company_id}")

        except Exception as e:
            logger.error(f"❌ Failed to index company context to Qdrant: {e}")

    def _format_basic_info_to_string(self, basic_info: BasicInfo) -> str:
        """
        DEPRECATED: Use basic_info.to_formatted_string() instead
        Format basic info to string for embedding
        """
        return basic_info.to_formatted_string()

    async def _get_or_create_context(self, company_id: str) -> CompanyContext:
        if company_id not in self.db:
            self.db[company_id] = CompanyContext()
        return self.db[company_id]

    async def set_basic_info(self, company_id: str, info: BasicInfo) -> BasicInfo:
        context = await self._get_or_create_context(company_id)
        context.basic_info = info

        # Auto-index to Qdrant
        await self._index_context_to_qdrant(company_id)

        return context.basic_info

    async def get_basic_info(self, company_id: str) -> Optional[BasicInfo]:
        context = await self._get_or_create_context(company_id)
        return context.basic_info

    async def set_faqs(self, company_id: str, faqs: List[FAQ]) -> List[FAQ]:
        context = await self._get_or_create_context(company_id)
        context.faqs = faqs

        # Auto-index to Qdrant
        await self._index_context_to_qdrant(company_id)

        return context.faqs

    async def get_faqs(self, company_id: str) -> List[FAQ]:
        context = await self._get_or_create_context(company_id)
        return context.faqs

    async def add_faq(self, company_id: str, faq: FAQ) -> List[FAQ]:
        """Add a single FAQ to existing FAQs"""
        context = await self._get_or_create_context(company_id)
        context.faqs.append(faq)

        # Auto-index to Qdrant
        await self._index_context_to_qdrant(company_id)

        return context.faqs

    async def delete_faqs(self, company_id: str) -> bool:
        """Delete all FAQs for a company"""
        if company_id not in self.db:
            return False
        context = self.db[company_id]
        context.faqs = []
        return True

    async def set_scenarios(
        self, company_id: str, scenarios: List[Scenario]
    ) -> List[Scenario]:
        context = await self._get_or_create_context(company_id)
        context.scenarios = scenarios

        # Auto-index to Qdrant
        await self._index_context_to_qdrant(company_id)

        return context.scenarios

    async def get_scenarios(self, company_id: str) -> List[Scenario]:
        context = await self._get_or_create_context(company_id)
        return context.scenarios

    async def add_scenario(self, company_id: str, scenario: Scenario) -> List[Scenario]:
        """Add a single scenario to existing scenarios"""
        context = await self._get_or_create_context(company_id)
        context.scenarios.append(scenario)

        # Auto-index to Qdrant
        await self._index_context_to_qdrant(company_id)

        return context.scenarios

    async def delete_scenarios(self, company_id: str) -> bool:
        """Delete all scenarios for a company"""
        if company_id not in self.db:
            return False
        context = self.db[company_id]
        context.scenarios = []
        return True

    async def delete_basic_info(self, company_id: str) -> bool:
        """Delete basic info for a company"""
        if company_id not in self.db:
            return False
        context = self.db[company_id]
        context.basic_info = None
        return True

    async def delete_full_context(self, company_id: str) -> bool:
        """Delete all context data for a company"""
        if company_id not in self.db:
            return False
        del self.db[company_id]
        return True

    def _format_context_to_string(self, context: CompanyContext) -> str:
        """
        Formats the company context into a single string for the LLM prompt.
        Updated to handle new scenario structure with types and reference messages.
        """
        parts = []
        if context.basic_info:
            parts.append("### Company Information:")
            basic_info_str = context.basic_info.to_formatted_string()
            if basic_info_str:
                # Split by lines and add proper formatting
                for line in basic_info_str.split('\n'):
                    if line.strip():
                        parts.append(f"- {line}")

        if context.faqs:
            parts.append("\n### Frequently Asked Questions (FAQs):")
            for faq in context.faqs:
                parts.append(f"- Q: {faq.question}")
                parts.append(f"  A: {faq.answer}")

        if context.scenarios:
            parts.append("\n### Scenarios by Intent Type:")
            
            # Group scenarios by type
            scenarios_by_type = {}
            for scenario in context.scenarios:
                scenario_type = scenario.type.value if hasattr(scenario, 'type') else 'GENERAL'
                if scenario_type not in scenarios_by_type:
                    scenarios_by_type[scenario_type] = []
                scenarios_by_type[scenario_type].append(scenario)
            
            # Format each type group
            for scenario_type, scenarios in scenarios_by_type.items():
                parts.append(f"\n#### {scenario_type} Scenarios:")
                for scenario in scenarios:
                    parts.append(f"- Scenario: {scenario.name}")
                    parts.append(f"  Description: {scenario.description}")
                    if hasattr(scenario, 'reference_messages') and scenario.reference_messages:
                        parts.append("  Reference Messages:")
                        for msg in scenario.reference_messages:
                            parts.append(f"    • {msg}")
                    
                    # Legacy support for old format
                    elif hasattr(scenario, 'steps') and scenario.steps:
                        parts.append("  Steps:")
                        for i, step in enumerate(scenario.steps, 1):
                            parts.append(f"    {i}. {step}")

        return "\n".join(parts)

    async def get_full_company_context(self, company_id: str) -> Dict:
        """
        Retrieves all context for a company and the formatted string version.
        """
        if company_id not in self.db:
            return {"error": "Company not found"}

        context = self.db[company_id]
        formatted_context = self._format_context_to_string(context)

        return {
            "company_id": company_id,
            "context_data": context.dict(),
            "formatted_context": formatted_context,
        }


# Dependency-injection function
def get_company_context_service() -> CompanyContextService:
    return CompanyContextService(db=_context_db)
