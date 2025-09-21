"""
Interactive Chat Testing Script for ABC Insurance & Xuan Phuong Hotel
Script test chat tương tác cho công ty bảo hiểm ABC và khách sạn Xuân Phương
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Configuration
AI_SERVICE_URL = "http://localhost:8000"
COMPANIES = {
    "abc_insurance": {
        "company_id": "abc_insurance_001",
        "industry": "insurance",
        "name": "ABC Insurance",
    },
    "xuan_phuong_hotel": {
        "company_id": "xuan_phuong_hotel_001",
        "industry": "hotel",
        "name": "Xuân Phương Hotel",
    },
}

# Chat test scenarios
CHAT_SCENARIOS = {
    "abc_insurance": {
        "vietnamese": [
            {
                "type": "basic_info",
                "message": "Xin chào, tôi muốn tìm hiểu về công ty bảo hiểm ABC và các sản phẩm mà các bạn cung cấp?",
                "description": "Hỏi thông tin cơ bản về công ty",
            },
            {
                "type": "faq",
                "message": "Làm thế nào để mua bảo hiểm ABC và thời gian xử lý bồi thường mất bao lâu?",
                "description": "Hỏi câu hỏi thường gặp",
            },
            {
                "type": "sales_health",
                "message": "Tôi đang quan tâm đến bảo hiểm sức khỏe cho gia đình 4 người, có những gói nào phù hợp và giá cả như thế nào?",
                "description": "Tư vấn bảo hiểm sức khỏe",
            },
            {
                "type": "sales_car",
                "message": "Tôi có xe Honda Civic 2022, muốn mua bảo hiểm xe ô tô toàn diện. Anh chị tư vấn giúp em với.",
                "description": "Tư vấn bảo hiểm xe ô tô",
            },
        ],
        "english": [
            {
                "type": "basic_info",
                "message": "Hello, could you please tell me about ABC Insurance company and what insurance products you offer?",
                "description": "Company information in English",
            },
            {
                "type": "support_claim",
                "message": "I had a car accident yesterday and need to claim my insurance. What documents do I need to prepare and how long does the process take?",
                "description": "Insurance claim support",
            },
            {
                "type": "sales_life",
                "message": "What are the differences between your life insurance products and which one would you recommend for a 35-year-old software engineer?",
                "description": "Life insurance consultation",
            },
            {
                "type": "faq_online",
                "message": "Can I purchase insurance online? What payment methods do you accept and is there any discount for online purchases?",
                "description": "Online purchase inquiry",
            },
        ],
    },
    "xuan_phuong_hotel": {
        "vietnamese": [
            {
                "type": "basic_info",
                "message": "Cho tôi biết thông tin về khách sạn Xuân Phương Vũng Tàu và các dịch vụ tiện ích mà khách sạn cung cấp?",
                "description": "Hỏi thông tin cơ bản về khách sạn",
            },
            {
                "type": "faq_checkin",
                "message": "Khách sạn có chính sách check-in và check-out như thế nào? Có thể check-in sớm không?",
                "description": "Hỏi về chính sách check-in/out",
            },
            {
                "type": "sales_room",
                "message": "Tôi muốn đặt phòng Superior view biển cho 2 người từ ngày 15-17/8, giá phòng bao nhiêu và có ưu đãi gì không?",
                "description": "Đặt phòng nghỉ dưỡng",
            },
            {
                "type": "sales_restaurant",
                "message": "Tôi muốn đặt bàn nhà hàng hải sản cho 8 người vào tối thứ 7 tuần sau để ăn mừng sinh nhật. Có menu gì đặc biệt không?",
                "description": "Đặt bàn nhà hàng",
            },
        ],
        "english": [
            {
                "type": "basic_info",
                "message": "Hello, I'm planning a trip to Vung Tau. Could you tell me about Xuan Phuong Hotel facilities and services?",
                "description": "Hotel information in English",
            },
            {
                "type": "sales_event",
                "message": "I'm interested in organizing a small wedding reception for about 80 guests at your hotel. What packages do you offer?",
                "description": "Wedding event planning",
            },
            {
                "type": "sales_restaurant",
                "message": "I want to make a reservation at your Sky Bar for 6 people this Saturday evening. Do you have availability and what are your signature cocktails?",
                "description": "Sky Bar reservation",
            },
            {
                "type": "services_spa",
                "message": "I'm staying at your hotel next week and I'm interested in your spa services. What treatments do you offer and what are the prices?",
                "description": "Spa services inquiry",
            },
        ],
    },
}


async def test_single_chat(
    session: aiohttp.ClientSession, company_info: dict, scenario: dict, language: str
):
    """Test a single chat scenario"""
    company_id = company_info["company_id"]
    industry = company_info["industry"]
    company_name = company_info["name"]

    print(f"\n{'='*80}")
    print(f"🏢 COMPANY: {company_name}")
    print(f"🌐 LANGUAGE: {language.upper()}")
    print(f"📝 SCENARIO: {scenario['description']}")
    print(f"💬 MESSAGE: {scenario['message']}")
    print(f"{'='*80}")

    # Prepare chat request
    timestamp = int(datetime.now().timestamp())
    chat_request = {
        "message": scenario["message"],
        "company_id": company_id,
        "industry": industry,
        "language": "auto_detect",
        "user_info": {
            "user_id": f"test_user_{timestamp}",
            "device_id": f"test_device_{timestamp}",
            "source": "chatdemo",
            "name": f"Test User {language.title()}",
        },
        "session_id": f"test_session_{company_id}_{timestamp}",
        "context": {"page_url": "https://test.com", "disable_webhooks": True},
    }

    try:
        print(f"🚀 Sending request to /api/unified/chat-stream...")

        # Call streaming chat endpoint
        async with session.post(
            f"{AI_SERVICE_URL}/api/unified/chat-stream",
            headers={"Content-Type": "application/json"},
            json=chat_request,
        ) as response:
            if response.status == 200:
                print(f"✅ Connection established - Status: {response.status}")
                print(f"📡 Streaming response:")
                print("-" * 60)

                # Read and display streaming response
                content_chunks = []
                metadata_received = False

                async for line in response.content:
                    if line:
                        try:
                            data_line = line.decode("utf-8").strip()
                            if data_line.startswith("data: "):
                                chunk_data = json.loads(data_line[6:])

                                if (
                                    chunk_data.get("type") == "metadata"
                                    and not metadata_received
                                ):
                                    print(
                                        f"🎯 Intent: {chunk_data.get('intent', 'Unknown')}"
                                    )
                                    print(
                                        f"🌍 Language: {chunk_data.get('language', 'Unknown')}"
                                    )
                                    print(
                                        f"📊 Confidence: {chunk_data.get('confidence', 0):.2f}"
                                    )
                                    print(
                                        f"🤖 Agent: {chunk_data.get('agent_type', 'Unknown')}"
                                    )
                                    print("-" * 60)
                                    metadata_received = True

                                elif chunk_data.get("type") == "content":
                                    content = chunk_data.get("content", "")
                                    print(content, end="", flush=True)
                                    content_chunks.append(content)

                                elif chunk_data.get("type") == "done":
                                    print(f"\n\n✅ Response completed")
                                    full_response = "".join(content_chunks)
                                    print(
                                        f"📏 Total response length: {len(full_response)} characters"
                                    )
                                    break

                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            print(f"⚠️ Error parsing chunk: {e}")

                print("-" * 60)

            else:
                print(f"❌ Request failed - Status: {response.status}")
                error_text = await response.text()
                print(f"Error details: {error_text}")

    except Exception as e:
        print(f"❌ Error during chat test: {e}")


async def run_company_tests(session: aiohttp.ClientSession, company_key: str):
    """Run all test scenarios for a specific company"""
    company_info = COMPANIES[company_key]
    scenarios = CHAT_SCENARIOS[company_key]

    print(f"\n🎯 TESTING COMPANY: {company_info['name'].upper()}")
    print(f"🏭 Industry: {company_info['industry']}")
    print(f"🆔 Company ID: {company_info['company_id']}")

    # Test Vietnamese scenarios
    print(f"\n🇻🇳 VIETNAMESE SCENARIOS:")
    for i, scenario in enumerate(scenarios["vietnamese"], 1):
        print(f"\n[{i}/4] Testing Vietnamese scenario...")
        await test_single_chat(session, company_info, scenario, "vietnamese")
        await asyncio.sleep(2)  # Wait between tests

    # Test English scenarios
    print(f"\n🇺🇸 ENGLISH SCENARIOS:")
    for i, scenario in enumerate(scenarios["english"], 1):
        print(f"\n[{i}/4] Testing English scenario...")
        await test_single_chat(session, company_info, scenario, "english")
        await asyncio.sleep(2)  # Wait between tests


async def run_interactive_test():
    """Run interactive chat testing"""
    print("🎭 INTERACTIVE CHAT TESTING")
    print("=" * 80)
    print("Testing optimized chat stream endpoint for 2 companies:")
    print("1. ABC Insurance Company (Bảo hiểm)")
    print("2. Xuân Phương Hotel Vũng Tàu (Khách sạn 5 sao)")
    print("=" * 80)

    async with aiohttp.ClientSession() as session:
        # Test ABC Insurance
        await run_company_tests(session, "abc_insurance")

        print("\n" + "=" * 100)

        # Test Xuan Phuong Hotel
        await run_company_tests(session, "xuan_phuong_hotel")

    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETED!")
    print("📊 Summary:")
    print("- Tested 2 companies with different industries")
    print("- 4 scenarios per language (Vietnamese + English)")
    print("- Total: 16 chat interactions")
    print("- Endpoint: /api/unified/chat-stream")
    print("=" * 80)


# Quick test function for single scenario
async def quick_test(company_key: str, language: str, scenario_index: int = 0):
    """Quick test for a single scenario"""
    if company_key not in COMPANIES:
        print(
            f"❌ Company '{company_key}' not found. Available: {list(COMPANIES.keys())}"
        )
        return

    if language not in ["vietnamese", "english"]:
        print(f"❌ Language '{language}' not supported. Use 'vietnamese' or 'english'")
        return

    company_info = COMPANIES[company_key]
    scenarios = CHAT_SCENARIOS[company_key][language]

    if scenario_index >= len(scenarios):
        print(
            f"❌ Scenario index {scenario_index} not found. Available: 0-{len(scenarios)-1}"
        )
        return

    scenario = scenarios[scenario_index]

    async with aiohttp.ClientSession() as session:
        await test_single_chat(session, company_info, scenario, language)


if __name__ == "__main__":
    print("Choose test mode:")
    print("1. Full test (all scenarios)")
    print("2. Quick test (single scenario)")

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        asyncio.run(run_interactive_test())
    elif choice == "2":
        print("\nAvailable companies:")
        for key, info in COMPANIES.items():
            print(f"- {key}: {info['name']}")

        company = input("\nEnter company key: ").strip()
        language = input("Enter language (vietnamese/english): ").strip()
        scenario_idx = int(input("Enter scenario index (0-3): ").strip())

        asyncio.run(quick_test(company, language, scenario_idx))
    else:
        print("Invalid choice. Running full test...")
        asyncio.run(run_interactive_test())
