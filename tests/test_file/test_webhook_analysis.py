#!/usr/bin/env python3
"""
Test script to demonstrate webhook data extraction and backend sending flow
Script demo luồng extract webhook data và gửi backend cho cả 3 intent
"""
import json
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))


def test_order_code_generation():
    """Test how order code is generated in place_order flow"""
    print("🔍 [ORDER_CODE] Analyzing order code generation in PLACE_ORDER flow...")
    print("=" * 60)

    print("📋 [ANALYSIS] Order code generation flow:")
    print("1. AI tạo webhook_data với order_data (không có orderCode)")
    print("2. Extract order_data từ AI response")
    print("3. Gửi POST /api/webhooks/orders/ai với payload")
    print("4. Backend trả về response.data.order.orderCode")
    print("5. Log success với orderCode nhận được từ backend")

    print("\n📋 [BACKEND_RESPONSE] Expected response structure:")
    backend_response = {
        "success": True,
        "message": "Order created successfully",
        "data": {
            "order": {
                "orderCode": "ORD20240827001",  # Backend generates this
                "status": "PENDING",
                "totalAmount": 754691,
                "createdAt": "2024-08-27T10:30:00.000Z",
            }
        },
    }
    print(json.dumps(backend_response, indent=2, ensure_ascii=False))

    print("\n🔧 [CODE_PATH] Where orderCode is extracted:")
    code_snippet = """
# In _send_order_created_webhook method:
response_data = response.json()
order_info = response_data.get("data", {}).get("order", {})
order_code = order_info.get("orderCode", "Unknown")  # <-- HERE
logger.info(f"✅ [ORDER_WEBHOOK] Order created successfully: {order_code}")
"""
    print(code_snippet)


def demonstrate_webhook_data_flow():
    """Demonstrate complete webhook data extraction and sending flow"""
    print("\n🚀 [WEBHOOK_FLOW] Complete webhook data extraction & sending flow:")
    print("=" * 60)

    print("📊 [STEP 1] AI Response Parsing:")
    print("   • _parse_ai_json_response() extracts webhook_data field")
    print("   • Validates complete flag for each intent")
    print("   • Logs structure details")

    print("\n📊 [STEP 2] Intent-Specific Processing:")

    print("\n🛒 [PLACE_ORDER]:")
    print("   • Check: _is_order_ready_for_webhook()")
    print("   • Extract: webhook_data.order_data")
    print("   • Send: _send_order_created_webhook() -> /api/webhooks/orders/ai")
    print("   • Receive: orderCode from backend response")

    print("\n🔄 [UPDATE_ORDER]:")
    print("   • Extract: webhook_data.update_data")
    print("   • Validate: orderCode != 'UNKNOWN'")
    print("   • Send: _handle_update_order_webhook() -> webhook_service")
    print("   • Process: Backend update response")

    print("\n📊 [CHECK_QUANTITY]:")
    print("   • Check: _is_check_quantity_webhook_ready()")
    print("   • Extract: webhook_data.check_quantity_data")
    print("   • Send: _handle_check_quantity_webhook() -> webhook_service")
    print("   • Process: Availability response")


def show_actual_payload_structures():
    """Show actual payload structures sent to backend"""
    print("\n📋 [PAYLOAD_STRUCTURES] Actual backend payloads:")
    print("=" * 60)

    print("\n🛒 [PLACE_ORDER] -> POST /api/webhooks/orders/ai:")
    place_order_structure = """
{
  "conversationId": "session_id",
  "companyId": "company_id",
  "leadId": "user_id",
  "userId": "ai_service_chatbot",
  "summary": "Customer order summary",
  "customer": { "name": "...", "phone": "...", "email": "..." },
  "items": [{ "name": "...", "quantity": 1, "unitPrice": 100000 }],
  "channel": { "type": "chatdemo" },
  "payment": { "method": "COD", "status": "PENDING" },
  "delivery": { "method": "pickup" },
  "metadata": { "source": "ai_conversation", "aiModel": "..." }
}
    """
    print(place_order_structure)

    print("\n🔄 [UPDATE_ORDER] -> webhook_service.send_update_order_webhook():")
    update_order_structure = """
{
  "orderCode": "DH001",
  "updateType": "change_quantity",
  "changes": { "items": [...], "delivery": {...} },
  "customer": { "name": "...", "phone": "...", "email": "..." },
  "companyId": "company_id",
  "metadata": { "source": "ai_conversation" }
}
    """
    print(update_order_structure)

    print("\n📊 [CHECK_QUANTITY] -> webhook_service.send_check_quantity_webhook():")
    check_quantity_structure = """
{
  "itemName": "Product Name",
  "itemType": "Product|Service",
  "productId": "prod_001",
  "customer": { "name": "...", "phone": "...", "email": "..." },
  "specifications": { "date": "2024-08-27", "quantity": 1 },
  "conversationId": "session_id",
  "channel": { "type": "chatdemo" },
  "companyId": "company_id"
}
    """
    print(check_quantity_structure)


def show_complete_flag_validation():
    """Show how complete flag is validated for each intent"""
    print("\n🎯 [COMPLETE_FLAG] Validation logic for complete flag:")
    print("=" * 60)

    print("\n🛒 [PLACE_ORDER] complete validation:")
    place_order_validation = """
# In _is_order_ready_for_webhook():
complete = order_data.get("complete", False)  # Must be True
has_items = order_data.get("items") and len(order_data["items"]) > 0
has_customer = order_data.get("customer", {}).get("name") and order_data.get("customer", {}).get("phone")

return complete and has_items and has_customer
    """
    print(place_order_validation)

    print("\n🔄 [UPDATE_ORDER] complete validation:")
    update_order_validation = """
# In webhook processing:
if update_data and update_data.get("orderCode") != "UNKNOWN":
    # Implied: complete flag should be True to have valid orderCode
    # Also need: update_data.get("complete", False) == True
    """
    print(update_order_validation)

    print("\n📊 [CHECK_QUANTITY] complete validation:")
    check_quantity_validation = """
# In _is_check_quantity_webhook_ready():
quantity_data = parsed_response.get("webhook_data", {}).get("check_quantity_data", {})
complete = quantity_data.get("complete", False)  # Must be True
has_customer = quantity_data.get("customer", {}).get("name") and quantity_data.get("customer", {}).get("phone")

return complete and has_customer and quantity_data.get("item_name")
    """
    print(check_quantity_validation)


def show_email_confirmation_requirement():
    """Show email confirmation requirement in AI responses"""
    print("\n📧 [EMAIL_CONFIRMATION] Email confirmation requirements:")
    print("=" * 60)

    print("📋 [REQUIREMENT] For all 3 intents when complete=true:")
    print(
        "   • PLACE_ORDER: 'Em có gửi thông tin xác nhận đơn hàng qua email cho anh/chị không ạ?'"
    )
    print(
        "   • UPDATE_ORDER: 'Em có gửi thông tin cập nhật đơn hàng qua email cho anh/chị không ạ?'"
    )
    print(
        "   • CHECK_QUANTITY: 'Em có gửi thông báo kết quả kiểm tra qua email cho anh/chị không ạ?'"
    )

    print("\n📋 [IMPLEMENTATION] In prompt template:")
    email_examples = """
- **BẮT BUỘC**: Khi complete=true, luôn hỏi khách hàng về gửi email:
  * PLACE_ORDER: "Em có gửi thông tin xác nhận đơn hàng qua email cho anh/chị không ạ?"
  * UPDATE_ORDER: "Em có gửi thông tin cập nhật đơn hàng qua email cho anh/chị không ạ?"
  * CHECK_QUANTITY: "Em có gửi thông báo kết quả kiểm tra qua email cho anh/chị không ạ?"
    """
    print(email_examples)


if __name__ == "__main__":
    test_order_code_generation()
    demonstrate_webhook_data_flow()
    show_actual_payload_structures()
    show_complete_flag_validation()
    show_email_confirmation_requirement()
    print("\n✅ [COMPLETE] Webhook data extraction & sending analysis completed!")
