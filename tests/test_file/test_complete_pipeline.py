#!/usr/bin/env python3
"""
Final test to verify webhook data extraction, validation and backend sending
Test cuối cùng để verify extract, validation và gửi backend cho cả 3 intent
"""
import json
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from services.unified_chat_service import unified_chat_service


def test_complete_webhook_pipeline():
    """Test complete webhook pipeline for all 3 intents"""
    print("🧪 [PIPELINE_TEST] Testing complete webhook pipeline...")
    print("=" * 70)

    # Test cases with complete=true and complete=false
    test_cases = [
        {
            "intent": "PLACE_ORDER",
            "ai_response": """{
  "thinking": {
    "intent": "PLACE_ORDER",
    "persona": "Lễ tân khách sạn",
    "reasoning": "Khách hàng đã cung cấp đầy đủ thông tin và xác nhận đặt phòng"
  },
  "final_answer": "Dạ cảm ơn anh Minh. Em đã xác nhận đặt phòng Superior Standard Room từ ngày mai lúc 14:00. Thông tin: Tên: Minh Trần, SĐT: 0909123456, Email: minh.tran@gmail.com. Em có gửi thông tin xác nhận đơn hàng qua email cho anh không ạ?",
  "webhook_data": {
    "order_data": {
      "complete": true,
      "items": [
        {
          "product_id": null,
          "service_id": "room_001",
          "name": "Superior Standard Room",
          "quantity": 1,
          "unit_price": 1200000,
          "notes": "Check-in ngày mai 14:00"
        }
      ],
      "customer": {
        "name": "Minh Trần",
        "phone": "0909123456",
        "email": "minh.tran@gmail.com",
        "address": "TP.HCM"
      },
      "delivery": {
        "method": "pickup",
        "address": "Khách sạn Paradise Bay"
      },
      "payment": {
        "method": "COD"
      },
      "notes": "Đặt phòng qua AI chatbot"
    }
  }
}""",
            "should_send_webhook": True,
        },
        {
            "intent": "UPDATE_ORDER",
            "ai_response": """{
  "thinking": {
    "intent": "UPDATE_ORDER",
    "persona": "Nhân viên hỗ trợ",
    "reasoning": "Khách hàng có mã đơn hàng và muốn thay đổi ngày check-in"
  },
  "final_answer": "Dạ em đã cập nhật đơn hàng DH20240827001 cho anh. Thay đổi ngày check-in từ 28/08 thành 30/08. Lý do: thay đổi lịch trình công tác. Em có gửi thông tin cập nhật đơn hàng qua email cho anh không ạ?",
  "webhook_data": {
    "update_data": {
      "complete": true,
      "order_code": "DH20240827001",
      "changes": {
        "delivery": {
          "check_in_date": "2024-08-30",
          "old_check_in_date": "2024-08-28",
          "notes": "Thay đổi ngày check-in"
        }
      },
      "customer": {
        "name": "Minh Trần",
        "phone": "0909123456",
        "email": "minh.tran@gmail.com"
      },
      "notes": "Khách hàng thay đổi lịch trình công tác"
    }
  }
}""",
            "should_send_webhook": True,
        },
        {
            "intent": "CHECK_QUANTITY",
            "ai_response": """{
  "thinking": {
    "intent": "CHECK_QUANTITY",
    "persona": "Nhân viên bán hàng",
    "reasoning": "Khách hàng đồng ý để kiểm tra tồn kho và đã cung cấp thông tin liên hệ"
  },
  "final_answer": "Dạ cảm ơn anh Long. Em đã gửi yêu cầu kiểm tra tình trạng phòng Deluxe Sea View cho ngày 01/09 đến bộ phận đặt phòng. Họ sẽ kiểm tra và liên hệ lại với anh qua số 0912345678 trong 30 phút. Em có gửi thông báo kết quả kiểm tra qua email cho anh không ạ?",
  "webhook_data": {
    "check_quantity_data": {
      "complete": true,
      "product_id": null,
      "service_id": "room_002",
      "item_name": "Deluxe Sea View Room",
      "item_type": "Service",
      "customer": {
        "name": "Long Nguyễn",
        "phone": "0912345678",
        "email": "long.nguyen@gmail.com"
      },
      "specifications": {
        "date": "2024-09-01",
        "quantity": 1,
        "check_in_time": "14:00",
        "check_out_time": "12:00"
      },
      "notes": "Khách hàng cần kiểm tra phòng trống ngày 01/09"
    }
  }
}""",
            "should_send_webhook": True,
        },
        {
            "intent": "PLACE_ORDER",
            "ai_response": """{
  "thinking": {
    "intent": "PLACE_ORDER",
    "persona": "Lễ tân khách sạn",
    "reasoning": "Khách hàng quan tâm đặt phòng nhưng chưa cung cấp đủ thông tin"
  },
  "final_answer": "Dạ cảm ơn anh quan tâm đến phòng Superior Standard Room. Để em hỗ trợ anh đặt phòng, anh vui lòng cho em biết tên đầy đủ và số điện thoại liên hệ ạ?",
  "webhook_data": {
    "order_data": {
      "complete": false,
      "items": [
        {
          "name": "Superior Standard Room",
          "quantity": 1
        }
      ],
      "customer": {},
      "notes": "Chưa đủ thông tin khách hàng"
    }
  }
}""",
            "should_send_webhook": False,
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*50}")
        # Get complete flag from webhook_data
        try:
            parsed_data = json.loads(test_case["ai_response"])
            webhook_data = parsed_data.get("webhook_data", {})
            if test_case["intent"] == "PLACE_ORDER":
                complete_flag = webhook_data.get("order_data", {}).get(
                    "complete", "Not found"
                )
            elif test_case["intent"] == "UPDATE_ORDER":
                complete_flag = webhook_data.get("update_data", {}).get(
                    "complete", "Not found"
                )
            else:  # CHECK_QUANTITY
                complete_flag = webhook_data.get("check_quantity_data", {}).get(
                    "complete", "Not found"
                )
        except:
            complete_flag = "Parse error"

        print(f"🧪 [TEST {i}] {test_case['intent']} - Complete: {complete_flag}")
        print(f"{'='*50}")

        try:
            # Parse AI response
            print(f"📝 [STEP 1] Parsing AI response...")
            parsed_response = unified_chat_service._parse_ai_json_response(
                test_case["ai_response"]
            )
            print(f"✅ [PARSED] Keys: {list(parsed_response.keys())}")

            # Check webhook_data extraction
            if "webhook_data" in parsed_response:
                webhook_data = parsed_response["webhook_data"]
                print(f"✅ [WEBHOOK_DATA] Found: {list(webhook_data.keys())}")

                # Test intent-specific validation
                if test_case["intent"] == "PLACE_ORDER":
                    print(f"📝 [STEP 2] Testing order webhook readiness...")
                    is_ready = unified_chat_service._is_order_ready_for_webhook(
                        parsed_response
                    )
                    print(
                        f"🎯 [VALIDATION] Order ready: {is_ready} (Expected: {test_case['should_send_webhook']})"
                    )

                    if is_ready:
                        order_data = webhook_data.get("order_data", {})
                        print(
                            f"🛒 [ORDER_INFO] Customer: {order_data.get('customer', {}).get('name', 'Missing')}"
                        )
                        print(
                            f"🛒 [ORDER_INFO] Items: {len(order_data.get('items', []))}"
                        )
                        print(
                            f"🛒 [ORDER_INFO] Complete: {order_data.get('complete', False)}"
                        )

                elif test_case["intent"] == "UPDATE_ORDER":
                    print(f"📝 [STEP 2] Testing update order validation...")
                    update_data = webhook_data.get("update_data", {})
                    is_valid = (
                        update_data.get("complete", False) == True
                        and update_data.get("order_code")
                        and update_data.get("order_code") != "UNKNOWN"
                    )
                    print(
                        f"🎯 [VALIDATION] Update valid: {is_valid} (Expected: {test_case['should_send_webhook']})"
                    )

                    if is_valid:
                        print(
                            f"🔄 [UPDATE_INFO] Order code: {update_data.get('order_code', 'Missing')}"
                        )
                        print(
                            f"🔄 [UPDATE_INFO] Changes: {list(update_data.get('changes', {}).keys())}"
                        )
                        print(
                            f"🔄 [UPDATE_INFO] Complete: {update_data.get('complete', False)}"
                        )

                elif test_case["intent"] == "CHECK_QUANTITY":
                    print(f"📝 [STEP 2] Testing check quantity webhook readiness...")
                    is_ready = unified_chat_service._is_check_quantity_webhook_ready(
                        parsed_response, "test query"
                    )
                    print(
                        f"🎯 [VALIDATION] Quantity check ready: {is_ready} (Expected: {test_case['should_send_webhook']})"
                    )

                    if is_ready:
                        quantity_data = webhook_data.get("check_quantity_data", {})
                        print(
                            f"📊 [QUANTITY_INFO] Item: {quantity_data.get('item_name', 'Missing')}"
                        )
                        print(
                            f"📊 [QUANTITY_INFO] Customer: {quantity_data.get('customer', {}).get('name', 'Missing')}"
                        )
                        print(
                            f"📊 [QUANTITY_INFO] Complete: {quantity_data.get('complete', False)}"
                        )

                # Show email confirmation check
                final_answer = parsed_response.get("final_answer", "")
                has_email_question = any(
                    phrase in final_answer.lower()
                    for phrase in [
                        "gửi thông tin",
                        "qua email",
                        "email cho",
                        "thông báo",
                    ]
                )
                print(
                    f"📧 [EMAIL_CHECK] Contains email confirmation: {has_email_question}"
                )

            else:
                print("❌ [ERROR] No webhook_data found")

            print(f"✅ [TEST {i}] Completed successfully")

        except Exception as e:
            print(f"❌ [TEST {i}] Failed: {e}")


def show_backend_payload_mapping():
    """Show how webhook_data maps to backend payloads"""
    print(f"\n{'='*70}")
    print("📋 [BACKEND_MAPPING] How webhook_data maps to backend payloads:")
    print(f"{'='*70}")

    mapping_info = """
🛒 [PLACE_ORDER] webhook_data.order_data → Backend /api/webhooks/orders/ai:
   ✓ order_data.items → payload.items (với productId/serviceId)
   ✓ order_data.customer → payload.customer
   ✓ order_data.delivery → payload.delivery
   ✓ order_data.payment → payload.payment
   ✓ order_data.notes → payload.notes
   ✓ Backend generates orderCode and returns in response

🔄 [UPDATE_ORDER] webhook_data.update_data → webhook_service.send_update_order_webhook():
   ✓ update_data.order_code → payload.orderCode
   ✓ update_data.changes → payload.changes
   ✓ update_data.customer → payload.customer
   ✓ update_data.notes → payload.notes
   ✓ complete flag must be true to proceed

📊 [CHECK_QUANTITY] webhook_data.check_quantity_data → webhook_service.send_check_quantity_webhook():
   ✓ check_quantity_data.item_name → payload.itemName
   ✓ check_quantity_data.product_id → payload.productId
   ✓ check_quantity_data.customer → payload.customer
   ✓ check_quantity_data.specifications → payload.specifications
   ✓ complete flag must be true to proceed
    """
    print(mapping_info)


if __name__ == "__main__":
    test_complete_webhook_pipeline()
    show_backend_payload_mapping()
    print(f"\n✅ [COMPLETE] All webhook pipeline tests completed!")
