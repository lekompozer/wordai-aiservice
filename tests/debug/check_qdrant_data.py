#!/usr/bin/env python3
"""
Quick test to check Qdrant collections and data
"""

import os
import asyncio

# Set environment
os.environ['ENV'] = 'development'
os.environ['DEVELOPMENT_ENV'] = 'true'

# Import config to trigger environment loading
import config.config

from src.vector_store.qdrant_client import create_qdrant_manager

async def check_qdrant_data():
    print("🔍 Checking Qdrant Collections and Data...")
    
    try:
        qdrant = create_qdrant_manager()
        
        # List all collections
        collections = qdrant.client.get_collections()
        print(f"\n📚 Available Collections: ({len(collections.collections)} total)")
        
        for col in collections.collections:
            print(f"   - {col.name}")
            
            # Get collection info
            try:
                collection_info = qdrant.client.get_collection(col.name)
                points_count = collection_info.points_count
                print(f"     📊 Points: {points_count}")
                
                if points_count > 0:
                    # Get some sample points
                    points, _ = qdrant.client.scroll(
                        collection_name=col.name,
                        limit=3,
                        with_payload=True,
                        with_vectors=False
                    )
                    
                    print(f"     📄 Sample points:")
                    for i, point in enumerate(points):
                        user_id = point.payload.get('user_id', 'N/A')
                        document_id = point.payload.get('document_id', 'N/A') 
                        content_preview = point.payload.get('content', '')[:50]
                        print(f"       [{i+1}] User: {user_id} | Doc: {document_id}")
                        print(f"           Content: '{content_preview}...'")
                        
            except Exception as e:
                print(f"     ❌ Error getting collection info: {e}")
        
        print(f"\n🎯 Specific Test: Check for recent e2e user")
        
        # Check if our recent test user has a collection
        recent_collections = [col.name for col in collections.collections if 'e2e_user' in col.name]
        
        if recent_collections:
            print(f"✅ Found e2e test collections: {recent_collections}")
            
            for col_name in recent_collections:
                try:
                    user_id = col_name.replace('user_', '').replace('_documents', '')
                    user_info = await qdrant.get_user_documents_info(user_id)
                    print(f"   📊 {col_name}: {user_info}")
                except Exception as e:
                    print(f"   ❌ Error getting user info: {e}")
        else:
            print(f"⚠️ No e2e test collections found")
            
    except Exception as e:
        print(f"❌ Error checking Qdrant: {e}")

if __name__ == "__main__":
    asyncio.run(check_qdrant_data())
