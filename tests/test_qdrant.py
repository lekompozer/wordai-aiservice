#!/usr/bin/env python3
"""
Test script để kiểm tra kết nối Qdrant
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv('development.env')
    logger.info("✅ Loaded development.env")
except ImportError:
    logger.warning("⚠️ python-dotenv not installed. Loading from system environment.")

async def test_qdrant_connection():
    """Test kết nối Qdrant"""
    print("🔍 Testing Qdrant connection...")
    print(f"📍 Qdrant URL: {os.getenv('QDRANT_URL')}")
    print(f"🔑 API Key: {os.getenv('QDRANT_API_KEY')[:20]}...")
    
    try:
        # Import and test Qdrant client
        from qdrant_client import QdrantClient
        
        # Initialize client
        client = QdrantClient(
            url=os.getenv('QDRANT_URL'),
            api_key=os.getenv('QDRANT_API_KEY'),
            timeout=30
        )
        
        print("⏳ Connecting to Qdrant...")
        
        # Test connection by getting collections
        collections = client.get_collections()
        
        print("✅ Qdrant connection successful!")
        print(f"📚 Available collections: {len(collections.collections)}")
        
        if collections.collections:
            for collection in collections.collections:
                print(f"  - {collection.name} ({collection.points_count} points)")
        else:
            print("  - No collections found (this is normal for new instances)")
        
        # Test collection creation
        test_collection = "test_connection"
        try:
            from qdrant_client.models import Distance, VectorParams
            
            # Try to create a test collection
            client.create_collection(
                collection_name=test_collection,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            print(f"✅ Successfully created test collection: {test_collection}")
            
            # Clean up - delete test collection
            client.delete_collection(collection_name=test_collection)
            print(f"🧹 Cleaned up test collection: {test_collection}")
            
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"⚠️ Test collection already exists: {test_collection}")
            else:
                print(f"❌ Error creating test collection: {e}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Please install qdrant-client: pip install qdrant-client")
        return False
        
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        print("💡 Please check your Qdrant URL and API key")
        return False

async def test_qdrant_manager():
    """Test QdrantManager class"""
    print("\n🔍 Testing QdrantManager class...")
    
    try:
        from src.vector_store.qdrant_client import create_qdrant_manager
        
        # Create manager
        qdrant_manager = create_qdrant_manager()
        
        # Test health check
        is_healthy = qdrant_manager.health_check()
        
        if is_healthy:
            print("✅ QdrantManager health check passed!")
            
            # Test user collection creation
            test_user_id = "test_user_123"
            success = await qdrant_manager.ensure_user_collection(test_user_id)
            
            if success:
                print(f"✅ Successfully created user collection for: {test_user_id}")
                
                # Get collection info
                info = await qdrant_manager.get_user_documents_info(test_user_id)
                print(f"📊 Collection info: {info}")
                
                # Clean up
                await qdrant_manager.delete_user_collection(test_user_id)
                print(f"🧹 Cleaned up user collection for: {test_user_id}")
                
            else:
                print(f"❌ Failed to create user collection for: {test_user_id}")
                
        else:
            print("❌ QdrantManager health check failed!")
            
        return is_healthy
        
    except Exception as e:
        print(f"❌ QdrantManager Error: {e}")
        return False

async def test_embedding_model():
    """Test embedding model"""
    print("\n🔍 Testing embedding model...")
    
    try:
        from src.vector_store.qdrant_client import create_qdrant_manager
        
        qdrant_manager = create_qdrant_manager()
        
        # Test embedding
        test_text = "This is a test document for embedding."
        embedding = qdrant_manager.embed_text(test_text)
        
        print(f"✅ Embedding successful!")
        print(f"📏 Embedding dimension: {len(embedding)}")
        print(f"📊 Embedding sample: {embedding[:5]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Embedding Error: {e}")
        return False

def check_environment():
    """Check environment variables"""
    print("🔍 Checking environment variables...")
    
    required_vars = [
        'QDRANT_URL',
        'QDRANT_API_KEY',
        'QDRANT_HOST',
        'QDRANT_PORT',
        'EMBEDDING_MODEL',
        'VECTOR_SIZE'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if 'KEY' in var:
                print(f"✅ {var}: {value[:20]}...")
            else:
                print(f"✅ {var}: {value}")
        else:
            missing_vars.append(var)
            print(f"❌ {var}: NOT SET")
    
    if missing_vars:
        print(f"\n⚠️ Missing environment variables: {missing_vars}")
        return False
    else:
        print("\n✅ All required environment variables are set!")
        return True

async def main():
    """Main test function"""
    print("🚀 Starting Qdrant Connection Test")
    print("=" * 50)
    
    # Check environment
    env_ok = check_environment()
    if not env_ok:
        print("\n❌ Environment check failed!")
        return
    
    # Test basic connection
    connection_ok = await test_qdrant_connection()
    if not connection_ok:
        print("\n❌ Basic connection test failed!")
        return
    
    # Test QdrantManager
    manager_ok = await test_qdrant_manager()
    if not manager_ok:
        print("\n❌ QdrantManager test failed!")
        return
    
    # Test embedding
    embedding_ok = await test_embedding_model()
    if not embedding_ok:
        print("\n❌ Embedding test failed!")
        return
    
    print("\n" + "=" * 50)
    print("🎉 All tests passed! Qdrant is ready for use.")
    print("🚀 You can now start using the RAG system.")

if __name__ == "__main__":
    asyncio.run(main())
