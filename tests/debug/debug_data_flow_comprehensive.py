#!/usr/bin/env python3
"""
Debug script để kiểm tra data flow comprehensive
Test từng service một cách riêng biệt để tìm lỗi
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_admin_service():
    """Test AdminService search"""
    try:
        logger.info("🔧 Testing AdminService...")
        from src.services.admin_service import AdminService

        admin_service = AdminService()
        company_id = "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f"

        # Test search
        results = await admin_service.search_company_data(
            company_id=company_id,
            query="AIA insurance information",
            limit=3,
            score_threshold=0.1,
        )

        logger.info(f"📊 AdminService results: {len(results) if results else 0}")
        if results:
            for i, result in enumerate(results):
                content = result.get("content_for_rag", "")
                score = result.get("score", 0)
                logger.info(
                    f"   {i+1}. Score: {score:.3f}, Content: {content[:100]}..."
                )

        return results

    except Exception as e:
        logger.error(f"❌ AdminService test failed: {e}")
        return None


async def test_qdrant_service():
    """Test QdrantService comprehensive search"""
    try:
        logger.info("🔧 Testing QdrantService...")
        from src.services.qdrant_company_service import get_qdrant_service

        qdrant_service = get_qdrant_service()
        company_id = "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f"

        # Test comprehensive search
        results = await qdrant_service.comprehensive_hybrid_search(
            company_id=company_id,
            query="AIA insurance information",
            industry=None,
            data_types=None,
            score_threshold=0.1,
            max_chunks=5,
        )

        logger.info(f"📊 QdrantService results: {len(results) if results else 0}")
        if results:
            for i, result in enumerate(results):
                content = result.get("content_for_rag", "")
                score = result.get("score", 0)
                data_type = result.get("data_type", "")
                logger.info(
                    f"   {i+1}. Score: {score:.3f}, Type: {data_type}, Content: {content[:100]}..."
                )

        return results

    except Exception as e:
        logger.error(f"❌ QdrantService test failed: {e}")
        return None


async def test_conversation_manager():
    """Test ConversationManager MongoDB connection"""
    try:
        logger.info("🔧 Testing ConversationManager...")
        from src.database.db_manager import DBManager
        from src.database.conversation_manager import ConversationManager

        db_manager = DBManager()
        conversation_manager = ConversationManager(db_manager)

        # Test getting messages
        device_id = "test_device_123"
        messages = conversation_manager.get_optimized_messages(
            user_id=device_id, rag_context="", current_query=""
        )

        logger.info(
            f"📊 ConversationManager results: {len(messages) if messages else 0} messages"
        )
        if messages:
            for i, msg in enumerate(messages[-3:]):  # Last 3 messages
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                logger.info(f"   {i+1}. {role}: {content[:100]}...")

        return messages

    except Exception as e:
        logger.error(f"❌ ConversationManager test failed: {e}")
        return None


async def test_unified_chat_service():
    """Test UnifiedChatService optimized methods"""
    try:
        logger.info("🔧 Testing UnifiedChatService optimized methods...")
        from src.services.unified_chat_service import UnifiedChatService

        service = UnifiedChatService()
        company_id = "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f"
        device_id = "test_device_123"
        query = "Tell me about AIA insurance"

        # Test each optimized method
        logger.info("🔍 Testing _hybrid_search_company_data_optimized...")
        company_data = await service._hybrid_search_company_data_optimized(
            company_id, query
        )
        logger.info(f"📊 Company data result: {len(company_data)} chars")
        logger.info(f"📊 Company data preview: {company_data[:200]}...")

        logger.info("👤 Testing _get_user_context_optimized...")
        user_context = await service._get_user_context_optimized(device_id)
        logger.info(f"📊 User context result: {len(user_context)} chars")
        logger.info(f"📊 User context preview: {user_context[:200]}...")

        logger.info("🏢 Testing _get_company_context_optimized...")
        company_context = await service._get_company_context_optimized(company_id)
        logger.info(f"📊 Company context result: {len(company_context)} chars")
        logger.info(f"📊 Company context preview: {company_context[:200]}...")

        return {
            "company_data": company_data,
            "user_context": user_context,
            "company_context": company_context,
        }

    except Exception as e:
        logger.error(f"❌ UnifiedChatService test failed: {e}")
        return None


async def main():
    """Run comprehensive data flow tests"""
    logger.info("🚀 Starting comprehensive data flow debugging...")
    logger.info("=" * 80)

    # Test each service individually
    admin_results = await test_admin_service()
    logger.info("=" * 80)

    qdrant_results = await test_qdrant_service()
    logger.info("=" * 80)

    conversation_results = await test_conversation_manager()
    logger.info("=" * 80)

    unified_results = await test_unified_chat_service()
    logger.info("=" * 80)

    # Summary
    logger.info("📋 SUMMARY:")
    logger.info(f"   AdminService: {'✅ Working' if admin_results else '❌ Failed'}")
    logger.info(f"   QdrantService: {'✅ Working' if qdrant_results else '❌ Failed'}")
    logger.info(
        f"   ConversationManager: {'✅ Working' if conversation_results else '❌ Failed'}"
    )
    logger.info(
        f"   UnifiedChatService: {'✅ Working' if unified_results else '❌ Failed'}"
    )

    if unified_results:
        logger.info("📊 UNIFIED SERVICE DETAILS:")
        logger.info(f"   Company Data: {len(unified_results['company_data'])} chars")
        logger.info(f"   User Context: {len(unified_results['user_context'])} chars")
        logger.info(
            f"   Company Context: {len(unified_results['company_context'])} chars"
        )


if __name__ == "__main__":
    asyncio.run(main())
