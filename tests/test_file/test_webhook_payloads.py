#!/usr/bin/env python3
"""
Test script to generate actual webhook payloads for PLACE_ORDER, UPDATE_ORDER, CHECK_QUANTITY
Script kiểm tra tạo payload webhook thực tế cho 3 intent
"""
import json
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from services.unified_chat_service import unified_chat_service


def test_json_parsing():
    """Test JSON parsing with webhook_data extraction"""
    print("🧪 [TEST] Testing JSON parsing with webhook_data extraction...")

    # Test PLACE_ORDER payload
    test_place_order = """{
  "thinking": {
    "intent": "PLACE_ORDER",
    "persona": "Lễ tân khách sạn",
    "reasoning": "Khách hàng đã cung cấp đầy đủ thông tin đặt phòng và xác nhận"
  },
  "final_answer": "Dạ em cảm ơn anh Hội. Em đã xác nhận đặt phòng Superior Standard Room cho anh từ ngày mai. Thông tin: Tên: anh Hội, SĐT: 0908097470, Email: hoi.tran@gmail.com. Phòng sẽ sẵn sàng lúc 14:00. Em có gửi thông tin xác nhận qua email cho anh không ạ?",
  "webhook_data": {
    "order_data": {
      "complete": true,
      "items": [
        {
          "product_id": "room_001",
          "service_id": null,
          "name": "Superior Standard Room",
          "quantity": 1,
          "unit_price": 754691,
          "notes": "Phòng view biển"
        }
      ],
      "customer": {
        "name": "Hội Trần",
        "phone": "0908097470",
        "email": "hoi.tran@gmail.com",
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
}"""

    # Test UPDATE_ORDER payload
    test_update_order = """{
  "thinking": {
    "intent": "UPDATE_ORDER",
    "persona": "Nhân viên hỗ trợ",
    "reasoning": "Khách hàng muốn thay đổi thông tin đơn hàng và đã xác nhận"
  },
  "final_answer": "Dạ em đã cập nhật thông tin đơn hàng DH001 cho anh. Thay đổi: từ 2 phòng xuống 1 phòng, ngày check-in từ 15/08 thành 20/08. Lý do: thay đổi kế hoạch du lịch. Em có gửi thông tin cập nhật qua email cho anh không ạ?",
  "webhook_data": {
    "update_data": {
      "complete": true,
      "order_code": "DH001",
      "changes": {
        "items": [
          {
            "name": "Superior Standard Room",
            "quantity": 1,
            "old_quantity": 2,
            "notes": "Giảm từ 2 phòng xuống 1 phòng"
          }
        ],
        "delivery": {
          "check_in_date": "2024-08-20",
          "old_check_in_date": "2024-08-15",
          "notes": "Thay đổi ngày check-in"
        }
      },
      "customer": {
        "name": "Hội Trần",
        "phone": "0908097470",
        "email": "hoi.tran@gmail.com"
      },
      "notes": "Khách hàng thay đổi kế hoạch du lịch"
    }
  }
}"""

    # Test CHECK_QUANTITY payload
    test_check_quantity = """{
  "thinking": {
    "intent": "CHECK_QUANTITY",
    "persona": "Nhân viên bán hàng",
    "reasoning": "Khách hàng hỏi tình trạng tồn kho và đã đồng ý để shop kiểm tra"
  },
  "final_answer": "Dạ cảm ơn anh Minh. Em đã gửi yêu cầu kiểm tra tình trạng phòng Superior Standard Room cho ngày 25/08 đến bộ phận đặt phòng. Họ sẽ kiểm tra và liên hệ lại với anh qua số 0909123456 trong vòng 30 phút ạ. Em có gửi thông báo qua email cho anh không ạ?",
  "webhook_data": {
    "check_quantity_data": {
      "complete": true,
      "product_id": "room_001",
      "service_id": null,
      "item_name": "Superior Standard Room",
      "item_type": "Service",
      "customer": {
        "name": "Minh Nguyễn",
        "phone": "0909123456",
        "email": "minh.nguyen@gmail.com"
      },
      "specifications": {
        "date": "2024-08-25",
        "quantity": 1,
        "check_in_time": "14:00",
        "check_out_time": "12:00"
      },
      "notes": "Khách hàng cần kiểm tra tình trạng phòng trống cho ngày 25/08"
    }
  }
}"""

    # Parse and test each payload
    payloads = [
        ("PLACE_ORDER", test_place_order),
        ("UPDATE_ORDER", test_update_order),
        ("CHECK_QUANTITY", test_check_quantity),
    ]

    for intent_name, payload_str in payloads:
        print(f"\n🔍 [TEST] Testing {intent_name} payload...")
        try:
            # Parse JSON
            result = unified_chat_service._parse_ai_json_response(payload_str)
            print(f"✅ [PARSED] Result keys: {list(result.keys())}")

            if "webhook_data" in result:
                webhook_data = result["webhook_data"]
                print(f"✅ [WEBHOOK_DATA] Keys: {list(webhook_data.keys())}")

                # Check specific structure for each intent
                if intent_name == "PLACE_ORDER":
                    if "order_data" in webhook_data:
                        order_data = webhook_data["order_data"]
                        print(
                            f"✅ [ORDER_DATA] Complete: {order_data.get('complete', 'Missing!')}"
                        )
                        print(
                            f"✅ [ORDER_DATA] Customer: {order_data.get('customer', {}).get('name', 'Missing!')}"
                        )
                        print(
                            f"✅ [ORDER_DATA] Items count: {len(order_data.get('items', []))}"
                        )

                        # Test order webhook readiness
                        is_ready = unified_chat_service._is_order_ready_for_webhook(
                            result
                        )
                        print(f"✅ [WEBHOOK_READY] Is order ready: {is_ready}")

                elif intent_name == "UPDATE_ORDER":
                    if "update_data" in webhook_data:
                        update_data = webhook_data["update_data"]
                        print(
                            f"✅ [UPDATE_DATA] Complete: {update_data.get('complete', 'Missing!')}"
                        )
                        print(
                            f"✅ [UPDATE_DATA] Order code: {update_data.get('order_code', 'Missing!')}"
                        )
                        print(
                            f"✅ [UPDATE_DATA] Changes: {list(update_data.get('changes', {}).keys())}"
                        )

                elif intent_name == "CHECK_QUANTITY":
                    if "check_quantity_data" in webhook_data:
                        quantity_data = webhook_data["check_quantity_data"]
                        print(
                            f"✅ [QUANTITY_DATA] Complete: {quantity_data.get('complete', 'Missing!')}"
                        )
                        print(
                            f"✅ [QUANTITY_DATA] Item: {quantity_data.get('item_name', 'Missing!')}"
                        )
                        print(
                            f"✅ [QUANTITY_DATA] Customer: {quantity_data.get('customer', {}).get('name', 'Missing!')}"
                        )

                        # Test quantity webhook readiness
                        is_ready = (
                            unified_chat_service._is_check_quantity_webhook_ready(
                                result, "test query"
                            )
                        )
                        print(f"✅ [WEBHOOK_READY] Is quantity check ready: {is_ready}")

            else:
                print("❌ [ERROR] No webhook_data found in parsed result")

        except Exception as e:
            print(f"❌ [ERROR] Failed to parse {intent_name}: {e}")


def generate_backend_payloads():
    """Generate actual backend webhook payloads"""
    print("\n🚀 [BACKEND] Generating actual backend payloads...")

    # PLACE_ORDER backend payload
    place_order_payload = {
        "conversationId": "conv_12345",
        "companyId": "hotel_paradise_bay",
        "leadId": "lead_67890",
        "userId": "ai_service_chatbot",
        "summary": "Hội Trần đặt 1 Superior Standard Room với tổng giá trị 754,691 VND. Khách đến lấy, thanh toán COD.",
        "customer": {
            "name": "Hội Trần",
            "phone": "0908097470",
            "email": "hoi.tran@gmail.com",
            "address": "TP.HCM",
            "company": "",
        },
        "items": [
            {
                "productId": "room_001",
                "serviceId": None,
                "itemType": "Service",
                "name": "Superior Standard Room",
                "quantity": 1,
                "unitPrice": 754691,
                "totalPrice": 754691,
                "description": "Phòng superior với view biển",
                "notes": "Phòng view biển",
                "product_code": "SUP_001",
                "unit": "Phòng",
            }
        ],
        "channel": {"type": "chatdemo", "pluginId": None},
        "payment": {
            "method": "COD",
            "status": "PENDING",
            "timing": "on_delivery",
            "notes": "",
        },
        "delivery": {
            "method": "pickup",
            "address": "Khách sạn Paradise Bay",
            "recipientName": "Hội Trần",
            "recipientPhone": "0908097470",
            "notes": "",
        },
        "notes": "Đặt phòng qua AI chatbot",
        "metadata": {
            "source": "ai_conversation",
            "aiModel": "qwen-3-235b-a22b-instruct-2507",
            "processingTime": 1250,
            "extractedFrom": "conversation",
        },
    }

    # UPDATE_ORDER backend payload
    update_order_payload = {
        "orderCode": "DH001",
        "updateType": "change_quantity",
        "changes": {
            "items": [
                {
                    "name": "Superior Standard Room",
                    "quantity": 1,
                    "old_quantity": 2,
                    "notes": "Giảm từ 2 phòng xuống 1 phòng",
                }
            ],
            "checkInDate": "2024-08-20",
            "oldCheckInDate": "2024-08-15",
            "notes": "Thay đổi ngày check-in",
        },
        "customer": {
            "name": "Hội Trần",
            "phone": "0908097470",
            "email": "hoi.tran@gmail.com",
        },
        "companyId": "hotel_paradise_bay",
        "metadata": {
            "source": "ai_conversation",
            "aiModel": "qwen-3-235b-a22b-instruct-2507",
            "processingTime": 890,
            "extractedFrom": "conversation",
        },
    }

    # CHECK_QUANTITY backend payload
    check_quantity_payload = {
        "itemName": "Superior Standard Room",
        "itemType": "Service",
        "productId": "room_001",
        "serviceId": None,
        "customer": {
            "name": "Minh Nguyễn",
            "phone": "0909123456",
            "email": "minh.nguyen@gmail.com",
        },
        "specifications": {
            "date": "2024-08-25",
            "quantity": 1,
            "checkInTime": "14:00",
            "checkOutTime": "12:00",
        },
        "notes": "Khách hàng cần kiểm tra tình trạng phòng trống cho ngày 25/08",
        "conversationId": "conv_12345",
        "channel": {"type": "chatdemo", "pluginId": None},
        "companyId": "hotel_paradise_bay",
        "metadata": {
            "source": "ai_conversation",
            "aiModel": "qwen-3-235b-a22b-instruct-2507",
            "processingTime": 650,
            "extractedFrom": "conversation",
        },
    }

    # Print formatted payloads
    print("\n📋 [PLACE_ORDER] Backend webhook payload:")
    print("=" * 50)
    print(json.dumps(place_order_payload, indent=2, ensure_ascii=False))

    print("\n📋 [UPDATE_ORDER] Backend webhook payload:")
    print("=" * 50)
    print(json.dumps(update_order_payload, indent=2, ensure_ascii=False))

    print("\n📋 [CHECK_QUANTITY] Backend webhook payload:")
    print("=" * 50)
    print(json.dumps(check_quantity_payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    test_json_parsing()
    generate_backend_payloads()
    print("\n✅ [COMPLETE] All webhook payload tests completed!")
