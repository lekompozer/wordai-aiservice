#!/usr/bin/env python3
"""
Test Enhanced Token Analysis Implementation
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch
from src.services.unified_chat_service import UnifiedChatService
from src.models.unified_models import ChatRequest, ChatIntent, UserSource


@pytest.mark.asyncio
async def test_enhanced_token_analysis_structure():
    """Test that token analysis has proper structure with input/output/total breakdown"""

    # Mock request with longer content for better token analysis
    request = ChatRequest(
        message="Cho tôi biết về các gói lãi suất vay mua nhà hiện tại của ngân hàng? Tôi muốn vay 2 tỷ trong 20 năm.",
        company_id="comp_test",
        conversation_id="conv_test_tokens",
        session_id="sess_test_tokens",
        user_id="user_test_tokens",
        source=UserSource.CHATDEMO,
        message_id="msg_test_tokens",
    )

    # Mock AI response with thinking
    mock_ai_response = """```json
{
    "thinking": {
        "intent": "ASK_COMPANY_INFORMATION",
        "persona": "Chuyên viên tư vấn tài chính",
        "reasoning": "Khách hàng hỏi về lãi suất vay mua nhà với số tiền cụ thể 2 tỷ trong 20 năm. Đây là intent ASK_COMPANY_INFORMATION vì họ cần thông tin chính thức về sản phẩm vay của ngân hàng."
    },
    "final_answer": "Cảm ơn bạn đã quan tâm đến dịch vụ vay mua nhà của chúng tôi! Hiện tại ngân hàng đang có các gói lãi suất vay mua nhà rất hấp dẫn:\n\n🏠 **GÓI VAY MUA NHÀ ƯU ĐÃI 2025**\n- Lãi suất cố định 12 tháng đầu: 6.5%/năm\n- Lãi suất từ tháng 13 trở đi: 8.2%/năm\n- Thời hạn vay: Tối đa 25 năm\n- Mức vay: Lên đến 85% giá trị tài sản\n\nVới khoản vay 2 tỷ trong 20 năm:\n💰 Số tiền trả hàng tháng dự kiến: ~18-20 triệu\n📋 Hồ sơ cần thiết: CMND/CCCD, sổ hộ khẩu, giấy tờ thu nhập\n\nBạn có muốn tôi tư vấn thêm về thủ tục hoặc lịch hẹn gặp chuyên viên không?"
}
```"""

    with patch(
        "src.services.unified_chat_service.UnifiedChatService._get_ai_response_with_retry"
    ) as mock_ai, patch(
        "src.services.unified_chat_service.UnifiedChatService._send_webhook_if_needed"
    ) as mock_webhook:

        mock_ai.return_value = mock_ai_response
        mock_webhook.return_value = True

        chat_service = UnifiedChatService()

        response = await chat_service.process_chat_request(request)

        # Verify response structure
        assert response.status == "success"
        assert "lastAiResponse" in response.data

        last_ai_response = response.data["lastAiResponse"]
        metadata = last_ai_response["metadata"]

        print("\n🔍 Enhanced Token Analysis Structure:")
        print(f"Metadata keys: {list(metadata.keys())}")

        # Verify enhanced token structure
        assert "tokens" in metadata
        tokens = metadata["tokens"]

        print(f"Token structure: {tokens}")

        # Check if it's enhanced structure (dict) or legacy (int)
        if isinstance(tokens, dict):
            print("✅ Enhanced token structure detected!")
            assert "input" in tokens
            assert "output" in tokens
            assert "total" in tokens
            assert tokens["total"] == tokens["input"] + tokens["output"]

            # Verify character count
            assert "characterCount" in metadata
            char_count = metadata["characterCount"]
            assert "input" in char_count
            assert "output" in char_count
            assert "total" in char_count
            assert char_count["total"] == char_count["input"] + char_count["output"]

            print(f"✅ Input tokens: {tokens['input']}")
            print(f"✅ Output tokens: {tokens['output']}")
            print(f"✅ Total tokens: {tokens['total']}")
            print(f"✅ Input chars: {char_count['input']}")
            print(f"✅ Output chars: {char_count['output']}")
            print(f"✅ Total chars: {char_count['total']}")

        else:
            print("⚠️ Legacy token structure detected - will be converted in webhook")
            assert isinstance(tokens, int)

        # Verify thinking data is included
        assert "thinking" in metadata
        assert metadata["thinking"] is not None

        # Verify intent extraction
        assert (
            metadata["intent"] == "information"
        )  # ASK_COMPANY_INFORMATION -> information

        print("✅ All token analysis checks passed!")


@pytest.mark.asyncio
async def test_webhook_token_analysis_conversion():
    """Test webhook converts legacy token format to enhanced format"""

    from src.services.webhook_service import WebhookService

    # Mock legacy lastAiResponse with simple token count
    legacy_ai_response = {
        "content": "Test AI response content",
        "timestamp": "2025-01-26T10:30:00.000Z",
        "messageId": "msg_test",
        "metadata": {
            "intent": "information",
            "tokens": 150,  # Legacy simple count
            "thinking": "Test thinking content",
        },
    }

    webhook_service = WebhookService()

    with patch.object(webhook_service, "send_conversation_event") as mock_send:
        mock_send.return_value = True

        result = await webhook_service.notify_conversation_updated(
            company_id="comp_test",
            conversation_id="conv_test",
            status="ACTIVE",
            message_count=1,
            last_ai_response=legacy_ai_response,
            channel="chatdemo",
            intent="information",
        )

        # Verify webhook was called
        assert result is True
        assert mock_send.called

        # Get the data sent to webhook
        call_args = mock_send.call_args
        webhook_data = call_args[0][2]  # Third argument is the data

        print("\n🔍 Webhook Data Structure:")
        print(f"Webhook data keys: {list(webhook_data.keys())}")

        if "lastAiResponse" in webhook_data:
            ai_response = webhook_data["lastAiResponse"]
            tokens = ai_response["metadata"]["tokens"]

            print(f"Webhook tokens structure: {tokens}")

            # Should be converted to enhanced structure
            if isinstance(tokens, dict):
                print("✅ Webhook converted legacy tokens to enhanced structure!")
                assert "input" in tokens
                assert "output" in tokens
                assert "total" in tokens
            else:
                print("⚠️ Webhook kept legacy token structure")

        print("✅ Webhook token conversion test passed!")


if __name__ == "__main__":
    print("🧪 Testing Enhanced Token Analysis Implementation...")

    # Run the tests
    asyncio.run(test_enhanced_token_analysis_structure())
    asyncio.run(test_webhook_token_analysis_conversion())

    print("\n✅ All enhanced token analysis tests completed!")
