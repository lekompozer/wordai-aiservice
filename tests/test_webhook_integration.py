"""
Test Webhook Service Integration
Test tích hợp Webhook Service
"""

import asyncio
import uuid
from datetime import datetime
from src.services.webhook_service import webhook_service
from src.utils.logger import setup_logger

logger = setup_logger()

async def test_webhook_integration():
    """Test full webhook integration workflow"""
    print("🧪 Testing Webhook Service Integration")
    print("=" * 50)
    
    # Test data
    company_id = "test-company-123"
    session_id = f"test-session-{int(datetime.now().timestamp())}"
    conversation_id = str(uuid.uuid4())
    
    try:
        # Test 1: Test connection
        print("\n📡 Testing webhook connection...")
        connection_ok = await webhook_service.test_webhook_connection()
        print(f"   Connection test: {'✅ SUCCESS' if connection_ok else '❌ FAILED'}")
        
        # Test 2: Conversation created
        print("\n🆕 Testing conversation created webhook...")
        conv_created = await webhook_service.notify_conversation_created(
            company_id=company_id,
            conversation_id=conversation_id,
            session_id=session_id,
            channel="WEB",
            intent="MENU_INQUIRY",
            metadata={
                "industry": "restaurant",
                "language": "vi",
                "test_mode": True
            }
        )
        print(f"   Conversation created: {'✅ SUCCESS' if conv_created else '❌ FAILED'}")
        
        # Test 3: User message
        print("\n💬 Testing user message webhook...")
        user_msg_id = str(uuid.uuid4())
        user_msg = await webhook_service.notify_message_created(
            company_id=company_id,
            conversation_id=conversation_id,
            message_id=user_msg_id,
            role="user",
            content="Cho tôi xem menu món chay",
            metadata={
                "session_id": session_id,
                "test_mode": True
            }
        )
        print(f"   User message: {'✅ SUCCESS' if user_msg else '❌ FAILED'}")
        
        # Test 4: Assistant message
        print("\n🤖 Testing assistant message webhook...")
        assistant_msg_id = str(uuid.uuid4())
        assistant_msg = await webhook_service.notify_message_created(
            company_id=company_id,
            conversation_id=conversation_id,
            message_id=assistant_msg_id,
            role="assistant",
            content="Dưới đây là menu món chay của chúng tôi:\n1. Cơm chay nấm - 85,000đ\n2. Phở chay - 75,000đ",
            metadata={
                "intent": "MENU_INQUIRY",
                "confidence": 0.95,
                "processing_time": 1.234,
                "test_mode": True
            }
        )
        print(f"   Assistant message: {'✅ SUCCESS' if assistant_msg else '❌ FAILED'}")
        
        # Test 5: Conversation updated
        print("\n🔄 Testing conversation updated webhook...")
        conv_updated = await webhook_service.notify_conversation_updated(
            company_id=company_id,
            conversation_id=conversation_id,
            status="COMPLETED",
            message_count=2,
            ended_at=datetime.now(),
            summary="User inquired about vegetarian menu options",
            satisfaction_score=4.5
        )
        print(f"   Conversation updated: {'✅ SUCCESS' if conv_updated else '❌ FAILED'}")
        
        # Test 6: File processed
        print("\n📄 Testing file processed webhook...")
        file_processed = await webhook_service.notify_file_processed(
            company_id=company_id,
            file_id=str(uuid.uuid4()),
            status="PROCESSED",
            extracted_items=25,
            chunks_created=15,
            processing_time=12.5
        )
        print(f"   File processed: {'✅ SUCCESS' if file_processed else '❌ FAILED'}")
        
        # Summary
        total_tests = 6
        passed_tests = sum([
            connection_ok, conv_created, user_msg, 
            assistant_msg, conv_updated, file_processed
        ])
        
        print(f"\n📊 Test Results: {passed_tests}/{total_tests} passed")
        if passed_tests == total_tests:
            print("🎉 All webhook tests passed!")
        else:
            print("⚠️ Some tests failed. Check backend webhook endpoint.")
            
    except Exception as e:
        logger.error(f"❌ Webhook test error: {e}")
        print(f"❌ Test failed with error: {e}")
    
    finally:
        # Clean up
        await webhook_service.close()

async def test_unified_chat_with_webhooks():
    """Test unified chat service with webhook integration"""
    print("\n🗣️ Testing Unified Chat with Webhooks")
    print("=" * 50)
    
    from src.services.unified_chat_service import UnifiedChatService
    from src.models.unified_models import UnifiedChatRequest, Industry, Language
    
    chat_service = UnifiedChatService()
    
    # Create test request
    request = UnifiedChatRequest(
        message="Tôi muốn xem menu món chay của nhà hàng",
        company_id="test-restaurant-456",
        session_id=f"chat-test-{int(datetime.now().timestamp())}",
        industry=Industry.RESTAURANT,
        language=Language.VIETNAMESE,
        context={
            "user_agent": "Test/1.0",
            "test_mode": True
        }
    )
    
    try:
        print(f"   User message: {request.message}")
        print(f"   Company: {request.company_id}")
        print(f"   Industry: {request.industry.value}")
        
        # Process message (this should trigger webhooks)
        response = await chat_service.process_message(request)
        
        print(f"✅ Chat processed successfully")
        print(f"   Response: {response.response[:100]}...")
        print(f"   Intent: {response.intent.value}")
        print(f"   Confidence: {response.confidence:.2f}")
        
        # Get conversation stats
        stats = chat_service.get_conversation_stats(request.session_id)
        print(f"   Conversation ID: {stats.get('conversation_id', 'N/A')}")
        print(f"   Message count: {stats.get('message_count', 0)}")
        
        # End conversation (should trigger webhook)
        ended = await chat_service.end_conversation(
            request.session_id,
            "Test conversation completed successfully"
        )
        print(f"   Conversation ended: {'✅ SUCCESS' if ended else '❌ FAILED'}")
        
    except Exception as e:
        logger.error(f"❌ Chat test error: {e}")
        print(f"❌ Chat test failed: {e}")

if __name__ == "__main__":
    async def main():
        await test_webhook_integration()
        await test_unified_chat_with_webhooks()
    
    asyncio.run(main())
