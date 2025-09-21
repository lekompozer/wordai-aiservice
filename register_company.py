#!/usr/bin/env python3

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.qdrant_service import QdrantService
from src.core.config import config
from src.core.models import CompanyConfig


def register_company():
    try:
        # Initialize Qdrant service
        qdrant = QdrantService()

        # Company configuration
        company_config = CompanyConfig(
            company_id="async-timing-test",
            company_name="Async Timing Test Company",
            industry="insurance",
            languages=["vi"],
            qdrant_collection="multi_company_data",
            database_name="ai_service_dev_db",
            model_name="paraphrase-multilingual-mpnet-base-v2",
            vector_size=768,
        )

        print(f"🔧 Registering company: {company_config.company_id}")
        print(f"   Industry: {company_config.industry}")
        print(f"   Collection: {company_config.qdrant_collection}")
        print(f"   Vector size: {company_config.vector_size}")

        result = qdrant.register_company(company_config)
        print(f"✅ Company registration result: {result}")

    except Exception as e:
        print(f"❌ Error registering company: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    register_company()
