#!/usr/bin/env python3
"""
Create Qdrant collection for Ivy Fashion Store
Tạo collection Qdrant cho Ivy Fashion Store
"""

import asyncio
import os
from src.services.qdrant_company_service import QdrantCompanyDataService
from src.models.unified_models import Industry, CompanyConfig

async def create_ivy_fashion_collection():
    """Create Qdrant collection for ivy-fashion-store"""
    
    print("🏗️ Creating Qdrant collection for Ivy Fashion Store...")
    
    # Load environment
    from src.core.config import load_environment
    load_environment()
    
    print(f"🔧 Qdrant URL: {os.getenv('QDRANT_URL', 'Not set')[:50]}...")
    print(f"� Qdrant API Key: {'✅ Set' if os.getenv('QDRANT_API_KEY') else '❌ Missing'}")
    
    # Initialize Qdrant service with cloud credentials
    qdrant_service = QdrantCompanyDataService(
        qdrant_url=os.getenv('QDRANT_URL'),
        qdrant_api_key=os.getenv('QDRANT_API_KEY')
    )
    
    company_id = "ivy-fashion-store"
    industry = Industry.FASHION
    
    # Create company config
    company_config = CompanyConfig(
        company_id=company_id,
        company_name="Ivy Fashion Store",
        industry=industry,
        qdrant_collection=f"{industry.value}_{company_id}"
    )
    
    try:
        # Initialize company collection
        collection_name = await qdrant_service.initialize_company_collection(company_config)
        
        print(f"✅ Collection created successfully!")
        print(f"   📝 Collection name: {collection_name}")
        print(f"   🏭 Industry: {industry}")
        print(f"   🏢 Company: {company_id}")
        
        # Verify collection exists
        try:
            stats = await qdrant_service.get_company_data_stats(company_id)
            print(f"🔍 Collection verification:")
            print(f"   📏 Total chunks: {stats.total_chunks}")
            print(f"   💾 Collection size: {stats.qdrant_collection_size}")
        except Exception as e:
            print(f"⚠️ Could not verify collection stats: {e}")
        
    except Exception as e:
        print(f"❌ Failed to create collection: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(create_ivy_fashion_collection())
