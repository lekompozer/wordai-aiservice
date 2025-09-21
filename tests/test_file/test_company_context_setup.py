"""
Test Data Setup for Company Context - Insurance & Hotel Industries
File test thiết lập dữ liệu ngữ cảnh công ty cho ngành bảo hiểm và khách sạn
"""

import asyncio
import aiohttp
import json
import os
from typing import Dict, Any
from datetime import datetime

# Base configuration
AI_SERVICE_URL = "http://localhost:8000"  # Adjust as needed
API_KEY = "agent8x-backend-secret-key-2025"  # Your internal API key

# Create debug output directory
DEBUG_OUTPUT_DIR = "debug_chat_responses"
os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)

# Create debug output directory
DEBUG_DIR = "debug_chat_responses"
os.makedirs(DEBUG_DIR, exist_ok=True)

# ===== COMPANY 1: ABC INSURANCE =====
ABC_INSURANCE_DATA = {
    "company_id": "abc_insurance_001",
    "industry": "insurance",
    "basic_info": {
        "company_name": "Công ty Bảo hiểm ABC",
        "introduction": "ABC Insurance là công ty bảo hiểm hàng đầu Việt Nam với hơn 20 năm kinh nghiệm, chuyên cung cấp các sản phẩm bảo hiểm nhân thọ, sức khỏe, và tài sản toàn diện. Chúng tôi cam kết bảo vệ an toàn tài chính cho hơn 2 triệu khách hàng trên toàn quốc.",
        "products_summary": "Bảo hiểm nhân thọ, bảo hiểm sức khỏe, bảo hiểm xe ô tô, bảo hiểm nhà ở, bảo hiểm du lịch, bảo hiểm doanh nghiệp, bảo hiểm giáo dục, quỹ hưu trí. Đặc biệt có gói bảo hiểm ung thư và bảo hiểm thai sản cao cấp.",
        "contact_info": "Hotline: 1900-1234-ABC (24/7), Email: support@abcinsurance.vn, Website: www.abcinsurance.vn, Địa chỉ: 123 Nguyễn Huệ, Quận 1, TP.HCM. Hơn 200 chi nhánh toàn quốc.",
    },
    "faqs": [
        {
            "question": "Làm thế nào để mua bảo hiểm ABC?",
            "answer": "Quý khách có thể mua bảo hiểm qua: 1) Website www.abcinsurance.vn, 2) Gọi hotline 1900-1234-ABC, 3) Đến trực tiếp 200+ chi nhánh, 4) Qua đại lý bảo hiểm ABC, 5) Ứng dụng mobile ABC Insurance. Chúng tôi hỗ trợ tư vấn miễn phí 24/7.",
        },
        {
            "question": "Thời gian chờ bồi thường bao lâu?",
            "answer": "ABC Insurance cam kết xử lý bồi thường nhanh chóng: Bồi thường nhanh trong 1-3 ngày làm việc cho các trường hợp đơn giản, tối đa 15 ngày làm việc cho các trường hợp phức tạp. Khách hàng được thông báo tiến độ xử lý thường xuyên qua SMS/email.",
        },
        {
            "question": "Có thể mua bảo hiểm online không?",
            "answer": "Có, ABC Insurance hỗ trợ mua bảo hiểm online 100% qua website và app mobile. Quy trình đơn giản: Chọn sản phẩm → Điền thông tin → Thanh toán online → Nhận giấy chứng nhận qua email. Hỗ trợ thanh toán qua thẻ ATM, VISA, MasterCard, ví điện tử.",
        },
        {
            "question": "How to claim insurance benefits?",
            "answer": "To claim insurance benefits with ABC Insurance: 1) Call hotline 1900-1234-ABC immediately, 2) Submit required documents (claim form, medical reports, invoices), 3) Our team will verify within 24-48 hours, 4) Receive compensation within 1-15 working days. We support English-speaking customers with dedicated international service team.",
        },
        {
            "question": "What insurance products do you offer?",
            "answer": "ABC Insurance offers comprehensive coverage: Life Insurance, Health Insurance, Car Insurance, Home Insurance, Travel Insurance, Business Insurance, Education Insurance, Retirement Funds. Special products include Cancer Insurance and Premium Maternity Insurance with international standard benefits.",
        },
    ],
    "scenarios": [
        {
            "name": "Khách hàng muốn mua bảo hiểm sức khỏe",
            "steps": [
                "Chào hỏi thân thiện và xác định nhu cầu bảo hiểm cụ thể (cá nhân/gia đình)",
                "Tìm hiểu độ tuổi, nghề nghiệp, tình trạng sức khỏe hiện tại",
                "Xác định ngân sách mong muốn và mức bảo hiểm cần thiết",
                "Giới thiệu 2-3 gói bảo hiểm sức khỏe phù hợp (Cơ bản, Toàn diện, Cao cấp)",
                "Giải thích chi tiết quyền lợi, điều khoản, và quy trình bồi thường",
                "Tư vấn thêm các sản phẩm bổ trợ (bảo hiểm ung thư, thai sản)",
                "Hướng dẫn quy trình mua và thanh toán online/offline",
            ],
        },
        {
            "name": "Khách hàng cần hỗ trợ bồi thường",
            "steps": [
                "Thể hiện sự thấu hiểu và hỗ trợ tích cực",
                "Xác nhận thông tin hợp đồng bảo hiểm và loại yêu cầu bồi thường",
                "Hướng dẫn chi tiết các giấy tờ cần chuẩn bị",
                "Giải thích quy trình xử lý và thời gian dự kiến",
                "Cung cấp mã số hồ sơ và thông tin liên hệ chuyên viên phụ trách",
                "Cam kết theo dõi và cập nhật tiến độ xử lý",
                "Hỗ trợ thêm nếu cần gia hạn hoặc nâng cấp bảo hiểm",
            ],
        },
        {
            "name": "Tư vấn bảo hiểm xe ô tô",
            "steps": [
                "Xác định thông tin xe: loại xe, năm sản xuất, giá trị xe",
                "Tìm hiểu mục đích sử dụng và khu vực di chuyển chính",
                "Giải thích sự khác biệt giữa bảo hiểm bắt buộc và tự nguyện",
                "Đề xuất gói bảo hiểm phù hợp (Cơ bản, Mở rộng, Toàn diện)",
                "Tính toán phí bảo hiểm và các ưu đãi hiện có",
                "Hướng dẫn quy trình giám định và bồi thường khi có sự cố",
                "Hỗ trợ hoàn tất thủ tục và giao hợp đồng",
            ],
        },
    ],
}

# ===== COMPANY 2: XUAN PHUONG HOTEL =====
XUAN_PHUONG_HOTEL_DATA = {
    "company_id": "xuan_phuong_hotel_001",
    "industry": "hotel",
    "basic_info": {
        "company_name": "Khách sạn 5 sao Xuân Phương Vũng Tàu",
        "introduction": "Xuân Phương Hotel là khách sạn 5 sao đẳng cấp quốc tế tại trung tâm Vũng Tàu, sở hữu vị trí đắc địa view biển tuyệt đẹp. Với 200 phòng cao cấp, 3 nhà hàng đa dạng ẩm thực, spa thư giãn, và hồ bơi vô cực, chúng tôi mang đến trải nghiệm nghỉ dưỡng hoàn hảo cho khách du lịch và doanh nhân.",
        "products_summary": "Phòng nghỉ cao cấp (Superior, Deluxe, Suite, Presidential), Nhà hàng Á-Âu (buffet sáng, à la carte), Nhà hàng hải sản tươi sống, Sky Bar tầng thượng, Spa & Massage, Hồ bơi infinity, Phòng gym 24/7, Hội trường sự kiện (50-500 khách), Dịch vụ wedding, Tour du lịch, Xe đưa đón sân bay.",
        "contact_info": "Địa chỉ: 88 Trần Phú, Phường 1, Vũng Tàu, Hotline: 0254-123-4567 (24/7), Email: booking@xuanphuonghotel.vn, Website: www.xuanphuonghotel.vn, WhatsApp: +84 90-123-4567",
    },
    "faqs": [
        {
            "question": "Làm thế nào để đặt phòng khách sạn?",
            "answer": "Quý khách có thể đặt phòng qua: 1) Website www.xuanphuonghotel.vn, 2) Gọi hotline 0254-123-4567, 3) Email booking@xuanphuonghotel.vn, 4) Các app Booking.com, Agoda, Traveloka. Chúng tôi có chính sách giá tốt nhất và free cancellation đến 18h ngày check-in.",
        },
        {
            "question": "Khách sạn có những tiện ích gì?",
            "answer": "Xuân Phương Hotel cung cấp đầy đủ tiện ích 5 sao: WiFi miễn phí toàn khách sạn, hồ bơi vô cực view biển, spa & massage, phòng gym 24/7, 3 nhà hàng đa dạng ẩm thực, sky bar, dịch vụ giặt ủi, room service 24h, xe đưa đón sân bay, concierge tư vấn tour.",
        },
        {
            "question": "Chính sách check-in và check-out?",
            "answer": "Check-in: 14:00, Check-out: 12:00. Early check-in và late check-out tùy thuộc vào tình trạng phòng trống (có thể phụ thu). Khách có thể gửi hành lý miễn phí trước và sau giờ quy định. Yêu cầu CMND/Passport khi làm thủ tục check-in.",
        },
        {
            "question": "How to make restaurant reservations?",
            "answer": "You can make restaurant reservations through: 1) Hotel concierge desk, 2) Call directly 0254-123-4567, 3) Book online via our website, 4) WhatsApp +84 90-123-4567. We have 3 restaurants: Asian-European cuisine, Fresh seafood restaurant, and Sky Bar. Advance booking recommended, especially for weekend dinners and special occasions.",
        },
        {
            "question": "What are the hotel's special packages?",
            "answer": "Xuan Phuong Hotel offers attractive packages: Honeymoon Package (romantic dinner, spa couple, room decoration), Family Package (connecting rooms, kids activities, buffet), Business Package (meeting room, airport transfer, late checkout), Weekend Getaway (2D1N with breakfast and dinner), Long-stay Package (7+ nights with spa credits).",
        },
    ],
    "scenarios": [
        {
            "name": "Khách muốn đặt phòng nghỉ dưỡng",
            "steps": [
                "Chào hỏi thân thiện và xác định ngày checkin/checkout dự kiến",
                "Tìm hiểu số lượng khách, mục đích lưu trú (du lịch/công tác/sự kiện)",
                "Đề xuất loại phòng phù hợp (Superior sea view, Deluxe, Suite)",
                "Giới thiệu các tiện ích và dịch vụ đặc biệt của khách sạn",
                "Tư vấn thêm gói combo (phòng + ăn sáng + spa/massage)",
                "Báo giá chi tiết và các ưu đãi hiện có",
                "Hỗ trợ hoàn tất booking và xác nhận qua email",
            ],
        },
        {
            "name": "Khách muốn đặt bàn nhà hàng và bar",
            "steps": [
                "Xác định thời gian, số lượng khách và dịp đặc biệt (nếu có)",
                "Tư vấn lựa chọn giữa 3 nhà hàng: Á-Âu, Hải sản, Sky Bar",
                "Giới thiệu menu đặc trưng và món signature của từng nhà hàng",
                "Tư vấn set menu hoặc à la carte tùy theo ngân sách",
                "Đề xuất combo đặc biệt (romantic dinner, birthday celebration)",
                "Xác nhận yêu cầu đặc biệt (dietary restrictions, decoration)",
                "Hoàn tất reservation và gửi confirmation detail",
            ],
        },
        {
            "name": "Tư vấn tổ chức sự kiện và tiệc cưới",
            "steps": [
                "Tìm hiểu loại sự kiện, quy mô và ngân sách dự kiến",
                "Giới thiệu các hội trường và không gian sự kiện available",
                "Tư vấn menu buffet hoặc set menu cho sự kiện",
                "Đề xuất gói dịch vụ toàn diện (âm thanh, ánh sáng, decor)",
                "Tư vấn dịch vụ wedding planning và photography",
                "Lập báo giá chi tiết và timeline thực hiện",
                "Sắp xếp site visit và ký hợp đồng",
            ],
        },
    ],
}

# Test scenarios for chat endpoint
CHAT_TEST_SCENARIOS = {
    "abc_insurance": [
        {
            "language": "vi",
            "message": "Xin chào, tôi muốn tìm hiểu về công ty bảo hiểm ABC và các sản phẩm mà các bạn cung cấp?",
            "expected_intent": "ASK_COMPANY_INFORMATION",
            "description": "Vietnamese - Company information inquiry",
        },
        {
            "language": "vi",
            "message": "Tôi đang quan tâm đến bảo hiểm sức khỏe cho gia đình, có những gói nào phù hợp và giá cả như thế nào?",
            "expected_intent": "SALES",
            "description": "Vietnamese - Health insurance sales inquiry",
        },
        {
            "language": "en",
            "message": "Hello, I had an accident and need to claim my car insurance. What documents do I need to prepare?",
            "expected_intent": "SUPPORT",
            "description": "English - Insurance claim support",
        },
        {
            "language": "en",
            "message": "What are the differences between your life insurance products and which one would you recommend for a 35-year-old professional?",
            "expected_intent": "SALES",
            "description": "English - Life insurance consultation",
        },
    ],
    "xuan_phuong_hotel": [
        {
            "language": "vi",
            "message": "Cho tôi biết thông tin về khách sạn Xuân Phương và các dịch vụ tiện ích mà khách sạn cung cấp?",
            "expected_intent": "ASK_COMPANY_INFORMATION",
            "description": "Vietnamese - Hotel information inquiry",
        },
        {
            "language": "vi",
            "message": "Tôi muốn đặt phòng Superior view biển cho 2 người vào cuối tuần này, giá phòng bao nhiêu và có ưu đãi gì không?",
            "expected_intent": "SALES",
            "description": "Vietnamese - Room booking inquiry",
        },
        {
            "language": "en",
            "message": "I want to make a reservation at your seafood restaurant for 6 people this Saturday evening. Do you have availability and what are your signature dishes?",
            "expected_intent": "SALES",
            "description": "English - Restaurant reservation",
        },
        {
            "language": "en",
            "message": "I'm staying at your hotel next week and I'm interested in your spa services and Sky Bar. What are the operating hours and prices?",
            "expected_intent": "GENERAL_INFORMATION",
            "description": "English - Hotel services inquiry",
        },
    ],
}


async def setup_company_context(
    session: aiohttp.ClientSession, company_data: Dict[str, Any]
):
    """Set up company context via API calls"""
    company_id = company_data["company_id"]
    headers = {"Content-Type": "application/json", "X-API-Key": API_KEY}

    try:
        # 1. Set basic info
        print(f"Setting up basic info for {company_id}...")
        async with session.post(
            f"{AI_SERVICE_URL}/api/admin/companies/{company_id}/context/basic-info",
            headers=headers,
            json=company_data["basic_info"],
        ) as response:
            if response.status == 200:
                print(f"✅ Basic info set successfully")
            else:
                print(f"❌ Failed to set basic info: {response.status}")

        # 2. Set FAQs
        print(f"Setting up FAQs for {company_id}...")
        async with session.post(
            f"{AI_SERVICE_URL}/api/admin/companies/{company_id}/context/faqs",
            headers=headers,
            json=company_data["faqs"],
        ) as response:
            if response.status == 200:
                print(f"✅ FAQs set successfully")
            else:
                print(f"❌ Failed to set FAQs: {response.status}")

        # 3. Set scenarios
        print(f"Setting up scenarios for {company_id}...")
        async with session.post(
            f"{AI_SERVICE_URL}/api/admin/companies/{company_id}/context/scenarios",
            headers=headers,
            json=company_data["scenarios"],
        ) as response:
            if response.status == 200:
                print(f"✅ Scenarios set successfully")
            else:
                print(f"❌ Failed to set scenarios: {response.status}")

        # 4. Verify full context
        print(f"Verifying full context for {company_id}...")
        async with session.get(
            f"{AI_SERVICE_URL}/api/admin/companies/{company_id}/context/",
            headers=headers,
        ) as response:
            if response.status == 200:
                context_data = await response.json()
                print(
                    f"✅ Full context verified - formatted_context length: {len(context_data.get('formatted_context', ''))}"
                )
            else:
                print(f"❌ Failed to verify context: {response.status}")

    except Exception as e:
        print(f"❌ Error setting up {company_id}: {e}")


async def test_chat_scenarios(
    session: aiohttp.ClientSession, company_id: str, industry: str, scenarios: list
):
    """Test chat scenarios for a company"""
    print(f"\n🧪 Testing chat scenarios for {company_id}...")

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n--- Test {i}: {scenario['description']} ---")
        print(f"Message: {scenario['message']}")

        # Prepare chat request
        chat_request = {
            "message": scenario["message"],
            "company_id": company_id,
            "industry": industry,
            "language": scenario["language"],  # Use specific language from scenario
            "user_info": {
                "user_id": f"test_user_{i}",
                "device_id": f"test_device_{i}",
                "source": "chatdemo",
                "name": f"Test User {i}",
            },
            "session_id": f"test_session_{company_id}_{i}",
            "context": {"page_url": "https://test.com", "disable_webhooks": True},
        }

        # Prepare debug data
        debug_data = {
            "test_info": {
                "test_number": i,
                "company_id": company_id,
                "industry": industry,
                "scenario": scenario,
                "timestamp": datetime.now().isoformat(),
            },
            "request": chat_request,
            "response_chunks": [],
            "full_response": "",
            "status": "unknown",
        }

        try:
            # Test streaming chat endpoint
            async with session.post(
                f"{AI_SERVICE_URL}/api/unified/chat-stream",
                headers={"Content-Type": "application/json"},
                json=chat_request,
            ) as response:
                debug_data["status"] = response.status

                if response.status == 200:
                    print(f"✅ Chat stream initiated successfully")
                    print(f"Expected intent: {scenario['expected_intent']}")

                    # Read all streaming response chunks
                    chunk_count = 0
                    full_response_text = ""

                    async for line in response.content:
                        if line:
                            try:
                                data_line = line.decode("utf-8").strip()
                                if data_line.startswith("data: "):
                                    chunk_data = json.loads(data_line[6:])
                                    debug_data["response_chunks"].append(chunk_data)

                                    if chunk_data.get("type") == "content":
                                        content = chunk_data.get("content", "")
                                        full_response_text += content

                                        # Show first few chunks
                                        if chunk_count < 5:
                                            print(
                                                f"AI Response chunk {chunk_count + 1}: {content}"
                                            )
                                            chunk_count += 1
                                    elif chunk_data.get("type") == "done":
                                        print(f"✅ Response completed")
                                        break
                            except Exception as parse_error:
                                print(f"⚠️ Failed to parse chunk: {parse_error}")

                    debug_data["full_response"] = full_response_text
                    print(
                        f"📝 Full response length: {len(full_response_text)} characters"
                    )

                else:
                    print(f"❌ Chat stream failed: {response.status}")
                    error_text = await response.text()
                    debug_data["error"] = error_text
                    print(f"Error: {error_text}")

        except Exception as e:
            print(f"❌ Error testing scenario {i}: {e}")
            debug_data["error"] = str(e)

        # Save debug data to file
        debug_filename = (
            f"{DEBUG_OUTPUT_DIR}/test_{company_id}_{i}_{scenario['language']}.json"
        )
        with open(debug_filename, "w", encoding="utf-8") as f:
            json.dump(debug_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Debug data saved to: {debug_filename}")

        # Wait between tests
        await asyncio.sleep(2)


async def debug_search_functionality(session: aiohttp.ClientSession):
    """Debug search functionality specifically"""
    print("\n🔍 DEBUGGING SEARCH FUNCTIONALITY")
    print("=" * 60)

    # Test queries in both languages
    test_queries = [
        {
            "company_id": "abc_insurance_001",
            "queries": [
                "bảo hiểm sức khỏe",  # Vietnamese - should find
                "health insurance",  # English - might not find
                "life insurance products",  # English - specific
                "sản phẩm bảo hiểm nhân thọ",  # Vietnamese - specific
                "dịch vụ bồi thường",  # Vietnamese - service
                "claim service",  # English - service
            ],
        },
        {
            "company_id": "xuan_phuong_hotel_001",
            "queries": [
                "nhà hàng khách sạn",  # Vietnamese - should find
                "restaurant hotel",  # English - might not find
                "spa services",  # English - service
                "dịch vụ spa massage",  # Vietnamese - service
                "sky bar",  # English - specific
                "phòng superior view biển",  # Vietnamese - specific
            ],
        },
    ]

    headers = {"Content-Type": "application/json", "X-API-Key": API_KEY}

    for company_test in test_queries:
        company_id = company_test["company_id"]
        print(f"\n🏢 Testing company: {company_id}")

        for i, query in enumerate(company_test["queries"]):
            print(f"\n--- Query {i+1}: '{query}' ---")

            # Test hybrid search endpoint directly
            search_request = {
                "query": query,
                "mode": "hybrid",
                "categories": ["products", "services", "company_info"],
                "max_results": 10,
            }

            try:
                async with session.post(
                    f"{AI_SERVICE_URL}/api/chat/hybrid-search/{company_id}",
                    headers=headers,
                    json=search_request,
                ) as response:
                    if response.status == 200:
                        search_result = await response.json()
                        chunks_found = len(search_result.get("results", []))
                        print(f"✅ Search found {chunks_found} chunks")

                        # Save detailed search results
                        debug_filename = (
                            f"{DEBUG_DIR}/search_debug_{company_id}_{i+1}.json"
                        )
                        debug_data = {
                            "query": query,
                            "company_id": company_id,
                            "request": search_request,
                            "response": search_result,
                            "chunks_found": chunks_found,
                            "timestamp": datetime.now().isoformat(),
                        }

                        with open(debug_filename, "w", encoding="utf-8") as f:
                            json.dump(debug_data, f, indent=2, ensure_ascii=False)

                        # Show first few results
                        for j, result in enumerate(
                            search_result.get("results", [])[:3]
                        ):
                            content = result.get("content", "")[:100]
                            score = result.get("score", 0)
                            content_type = result.get("content_type", "unknown")
                            print(
                                f"   {j+1}. [{content_type}] Score: {score:.3f} - {content}..."
                            )

                    else:
                        print(f"❌ Search failed: {response.status}")
                        error_text = await response.text()
                        print(f"Error: {error_text}")

            except Exception as e:
                print(f"❌ Search error: {e}")

            await asyncio.sleep(1)


async def main():
    """Main test function"""
    print("🚀 Starting Company Context Setup and Chat Testing...")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        # Setup company contexts
        print("\n📝 Setting up company contexts...")
        await setup_company_context(session, ABC_INSURANCE_DATA)
        print()
        await setup_company_context(session, XUAN_PHUONG_HOTEL_DATA)

        # Debug search functionality first
        await debug_search_functionality(session)

        # Test chat scenarios
        print("\n" + "=" * 60)
        print("🧪 TESTING CHAT SCENARIOS")
        print("=" * 60)

        # Test ABC Insurance scenarios
        await test_chat_scenarios(
            session,
            "abc_insurance_001",
            "insurance",
            CHAT_TEST_SCENARIOS["abc_insurance"],
        )

        # Test Xuan Phuong Hotel scenarios
        await test_chat_scenarios(
            session,
            "xuan_phuong_hotel_001",
            "hotel",
            CHAT_TEST_SCENARIOS["xuan_phuong_hotel"],
        )

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print(f"📁 Debug files saved in: {DEBUG_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
