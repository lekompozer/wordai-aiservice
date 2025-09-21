"""
Test extraction with real AI service via API endpoints
Test extraction thực sử dụng API endpoints
"""

import asyncio
import os
import json
from typing import Dict, Any
import aiohttp


class RealAIExtractionTester:
    """Test extraction using real AI service via API"""

    def __init__(self):
        # API endpoint configuration
        self.base_url = "http://localhost:8000"
        self.test_scenarios = self._prepare_test_scenarios()

    def _prepare_test_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Prepare test scenarios for real AI extraction"""
        return {
            "hotel_services": {
                "text": """
                DỊCH VỤ KHÁCH SẠN PARADISE BAY RESORT & SPA
                
                1. AIRPORT TRANSFER SERVICE
                Giá: 800,000 VNĐ/chuyến (một chiều)
                - Xe Mercedes VIP đón tiễn sân bay Tân Sơn Nhất
                - Thời gian di chuyển: 45 phút
                - Bao gồm: nước uống, báo chí, WiFi miễn phí
                - Đặt trước 24h, hủy miễn phí trước 12h
                
                2. SPA & WELLNESS CENTER
                Giá: 1,500,000 - 3,000,000 VNĐ/liệu trình
                - Massage truyền thống Thái Lan (90 phút): 1,800,000 VNĐ
                - Liệu pháp đá nóng aromatherapy (120 phút): 2,500,000 VNĐ
                - Gói chăm sóc toàn thân VIP (180 phút): 3,000,000 VNĐ
                - Mở cửa: 9:00 - 22:00 hàng ngày
                
                3. ROOM SERVICE 24/7
                Phí dịch vụ: 50,000 VNĐ/đơn hàng
                - Menu đa dạng: Món Á, Âu, chay
                - Đồ uống: cocktail, rượu vang, nước ngọt
                - Thời gian giao: 30-45 phút
                - Phục vụ 24/7 tất cả các ngày
                
                4. CONFERENCE & MEETING ROOMS
                Giá: 2,000,000 - 5,000,000 VNĐ/ngày
                - Phòng họp nhỏ (20 người): 2,000,000 VNĐ/ngày
                - Phòng hội thảo (100 người): 3,500,000 VNĐ/ngày
                - Auditorium (300 người): 5,000,000 VNĐ/ngày
                - Bao gồm: projector, âm thanh, WiFi, coffee break
                """,
                "data_type": "services",
                "metadata": {
                    "extraction_mode": True,
                    "industry": "hotel",
                    "original_name": "hotel-services-2025.pdf",
                    "description": "Complete hotel services pricing and descriptions",
                    "tags": ["spa", "conference", "dining", "transport"],
                    "company_info": {
                        "company_id": "hotel-paradise-bay-001",
                        "industry": "hotel",
                        "name": "Paradise Bay Resort & Spa",
                    },
                    "language": "vi",
                },
            },
            "restaurant_products": {
                "text": """
                THỰC ĐƠN NHÀ HÀNG GOLDEN DRAGON
                ĐẶC SẢN VIỆT NAM TRUYỀN THỐNG
                
                === MÓN CHÍNH ===
                
                1. PHỞ BÒ ĐẶC BIỆT - 89,000 VNĐ
                Mã món: PHO-BO-001
                - Phở bò với đầy đủ: thịt bò tái, chín, gầu, gân, sách
                - Nước dùng hầm 24 giờ từ xương bò tươi
                - Bánh phở làm tươi hàng ngày
                - Kèm rau thơm: húng quế, ngò gai, hành lá
                - Khối lượng: 500g, phục vụ: 1 người
                
                2. BÚN CHẢ HÀ NỘI TRUYỀN THỐNG - 75,000 VNĐ
                Mã món: BUN-CHA-002
                - Bún tươi với chả nướng than hoa thơm phức
                - Thịt nướng ba chỉ ướp gia vị đặc biệt
                - Nước mắm chua ngọt truyền thống
                - Rau sống: xà lách, kinh giới, húng lũi
                - Khối lượng: 400g, độ cay: nhẹ
                
                3. CƠM TẤM SƯỜN NƯỚNG SÀI GÒN - 65,000 VNĐ
                Mã món: COM-TAM-003
                - Cơm tấm thơm dẻo, sườn nướng BBQ
                - Chả trứng, bì, mỡ hành
                - Dưa chua, nước mắm pha chấm
                - Canh súp hành tím kèm theo
                - Khối lượng: 450g, phục vụ: 1 người
                
                === TRÁNG MIỆNG ===
                
                4. CHÈ BÁ BA MÀU - 35,000 VNĐ
                Mã món: CHE-3M-004
                - Chè đậu xanh, đậu đỏ, khoai môn
                - Nước cốt dừa tươi, đá bào
                - Thạch rau câu, đậu phộng rang
                - Lạnh, ngọt vừa, không chất bảo quản
                """,
                "data_type": "products",
                "metadata": {
                    "extraction_mode": True,
                    "industry": "restaurant",
                    "original_name": "restaurant-menu-traditional-2025.pdf",
                    "description": "Vietnamese traditional restaurant menu with authentic dishes",
                    "tags": ["vietnamese", "traditional", "pho", "bun_cha", "com_tam"],
                    "company_info": {
                        "company_id": "restaurant-golden-dragon-001",
                        "industry": "restaurant",
                        "name": "Golden Dragon Restaurant",
                    },
                    "language": "vi",
                },
            },
            "banking_products": {
                "text": """
                NGÂN HÀNG TECHCOMBANK - SẢN PHẨM THẺ TÍN DỤNG 2025
                
                === THẺ VISA ===
                
                1. THẺ VISA CLASSIC
                Mã sản phẩm: VISA-CLS-001
                - Phí thường niên: 200,000 VNĐ (miễn phí năm đầu)
                - Hạn mức tín dụng: 5 - 50 triệu VNĐ
                - Lãi suất: 2.5%/tháng (30% năm)
                - Ưu đãi: Hoàn tiền 1% mua sắm, miễn phí rút tiền ATM Techcombank
                - Yêu cầu: Thu nhập từ 8 triệu/tháng
                - Thời gian duyệt: 7-10 ngày làm việc
                
                2. THẺ MASTERCARD PLATINUM
                Mã sản phẩm: MC-PLT-002  
                - Phí thường niên: 800,000 VNĐ
                - Hạn mức tín dụng: 50 - 500 triệu VNĐ
                - Lãi suất: 2.2%/tháng (26.4% năm)
                - Ưu đãi: Hoàn tiền 2%, phòng chờ sân bay, bảo hiểm du lịch
                - Yêu cầu: Thu nhập từ 25 triệu/tháng
                - Bảo hiểm: 1 tỷ VNĐ tai nạn du lịch
                
                3. THẺ WORLD ELITE MASTERCARD
                Mã sản phẩm: MC-WE-003
                - Phí thường niên: 3,500,000 VNĐ
                - Hạn mức tín dụng: 500 triệu - 2 tỷ VNĐ
                - Lãi suất: 2.0%/tháng (24% năm)
                - Ưu đãi: Hoàn tiền 3%, concierge 24/7, golf miễn phí
                - Yêu cầu: Thu nhập từ 100 triệu/tháng
                - Dịch vụ: Personal banker riêng
                """,
                "data_type": "products",
                "metadata": {
                    "extraction_mode": True,
                    "industry": "banking",
                    "original_name": "techcombank-credit-cards-2025.pdf",
                    "description": "Techcombank credit card products with detailed terms",
                    "tags": [
                        "credit_card",
                        "visa",
                        "mastercard",
                        "cashback",
                        "premium",
                    ],
                    "company_info": {
                        "company_id": "bank-techcombank-001",
                        "industry": "banking",
                        "name": "Techcombank",
                    },
                    "language": "vi",
                },
            },
        }

    async def test_real_ai_extraction(self):
        """Test extraction using real AI service via API"""
        print("🤖 TESTING WITH REAL AI SERVICE VIA API")
        print("=" * 80)
        print(f"🔗 API Endpoint: {self.base_url}")
        print("🌐 Server Status: Testing connection...")

        # Test server connection
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/health") as response:
                    if response.status == 200:
                        print("✅ Server is running!")
                    else:
                        print(f"⚠️ Server responded with status {response.status}")
            except Exception as e:
                print(f"❌ Cannot connect to server: {e}")
                return

        print()

        for scenario_name, scenario in self.test_scenarios.items():
            print(f"\n🧪 Testing: {scenario_name.upper()}")
            print("-" * 60)

            text = scenario["text"]
            data_type = scenario["data_type"]
            metadata = scenario["metadata"]

            # Get industry info
            industry = metadata.get("industry")
            company_name = metadata.get("company_info", {}).get("name", "Unknown")

            print(f"🏢 Company: {company_name}")
            print(f"🏭 Industry: {industry}")
            print(f"📊 Type: {data_type}")
            print(f"📝 Text Length: {len(text)} chars")

            try:
                # Prepare API request
                api_data = {
                    "text_content": text,
                    "data_type": data_type,
                    "metadata": metadata,
                }

                print("🤖 Calling AI extraction API...")

                # Call API endpoint
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/api/extract",
                        json=api_data,
                        headers={"Content-Type": "application/json"},
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            print("✅ AI response received!")
                        else:
                            error_text = await response.text()
                            print(
                                f"❌ API call failed: {response.status} - {error_text}"
                            )
                            continue

                # Show results
                items = result.get(data_type, [])
                count = len(items)

                print(f"📊 Extracted: {count} {data_type}")

                if count > 0:
                    print(f"\n📋 Sample {data_type.capitalize()}:")
                    for i, item in enumerate(items[:2], 1):
                        name = item.get("name", "N/A")
                        category = item.get("category", "N/A")

                        if data_type == "products":
                            price = item.get("price", "N/A")
                            currency = item.get("currency", "")
                            sku = item.get("sku", "N/A")
                            print(f"   {i}. {name}")
                            print(
                                f"      Category: {category} | Price: {price} {currency}"
                            )
                            print(f"      SKU: {sku}")
                        else:
                            price_type = item.get("price_type", "N/A")
                            service_code = item.get("service_code", "N/A")
                            print(f"   {i}. {name}")
                            print(f"      Category: {category} | Type: {price_type}")
                            print(f"      Code: {service_code}")

                # Save result for inspection
                await self._save_result(scenario_name, result)

            except Exception as e:
                print(f"❌ Extraction failed: {str(e)}")
                import traceback

                print(f"🔍 Debug info: {traceback.format_exc()}")

    async def _save_result(self, scenario_name: str, result: Dict[str, Any]):
        """Save extraction result to file"""
        output_dir = "real_ai_extraction_results"
        os.makedirs(output_dir, exist_ok=True)

        filename = f"{output_dir}/{scenario_name}_ai_result.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"💾 Result saved: {filename}")

    async def test_dual_storage_with_ai(self):
        """Test dual storage strategy with real AI extraction"""
        print("\n🗄️  TESTING DUAL STORAGE WITH REAL AI")
        print("=" * 80)

        # Use hotel services for this test
        scenario = self.test_scenarios["hotel_services"]
        text = scenario["text"]
        metadata = scenario["metadata"]

        print("🏨 Processing Hotel Services with Real AI...")
        print("-" * 50)

        try:
            # Get template and extract with AI
            template = self.template_factory.get_template_with_metadata(metadata)
            system_prompt = template.get_system_prompt("services")
            user_prompt = template.build_extraction_prompt(
                data_type="services",
                file_name=metadata.get("original_name"),
                language=metadata.get("language", "vi"),
            )

            full_prompt = f"{user_prompt}\n\nDocument content:\n{text}"

            # Call AI
            ai_result = await self.ai_service.generate_structured_response(
                system_prompt=system_prompt, user_prompt=full_prompt, temperature=0.1
            )

            # Parse and process
            if isinstance(ai_result, str):
                import json

                parsed_result = json.loads(ai_result)
            else:
                parsed_result = ai_result

            final_result = template.post_process(parsed_result, "services")
            services = final_result.get("services", [])

            print("💾 DUAL STORAGE SIMULATION:")
            print()

            # High priority - structured data
            print("📊 HIGH PRIORITY STORAGE (Structured JSON):")
            structured_chunks = []
            for idx, service in enumerate(services):
                chunk_data = {
                    "chunk_id": f"hotel_services_structured_{idx}",
                    "data_type": "services",
                    "priority": "high",
                    "content": json.dumps(service, ensure_ascii=False),
                    "metadata": {
                        "name": service.get("name"),
                        "category": service.get("category"),
                        "price_type": service.get("price_type"),
                        "service_code": service.get("service_code"),
                        "tags": service.get("tags", [])[:5],
                    },
                }
                structured_chunks.append(chunk_data)
                print(
                    f"   ✅ Chunk {idx+1}: {service.get('name')} ({service.get('category')})"
                )

            print()
            print("🗂️  LOW PRIORITY STORAGE (Raw Backup):")
            raw_chunk = {
                "chunk_id": "hotel_services_raw_backup",
                "data_type": "other",
                "priority": "low",
                "content": text,
                "metadata": {
                    "backup_for": "hotel_services_extraction",
                    "total_items_extracted": len(services),
                    "ai_provider": "deepseek" if self.deepseek_key else "chatgpt",
                    "raw_text_length": len(text),
                },
            }
            print(f"   ✅ Raw backup: {len(text)} chars")
            print(f"   ✅ Extraction metadata included")

            # Save dual storage simulation
            dual_storage_result = {
                "structured_storage": {
                    "chunks": structured_chunks,
                    "total_chunks": len(structured_chunks),
                    "priority": "high",
                },
                "raw_storage": {"chunk": raw_chunk, "priority": "low"},
                "extraction_info": {
                    "ai_provider": "deepseek" if self.deepseek_key else "chatgpt",
                    "template_used": template.__class__.__name__,
                    "total_services": len(services),
                },
            }

            await self._save_result("dual_storage_simulation", dual_storage_result)

            print()
            print("🎯 FRONTEND EDIT SIMULATION:")
            print("ID | Name | Category | JSON Preview")
            print("-" * 70)
            for i, chunk in enumerate(structured_chunks[:3], 1):
                metadata = chunk["metadata"]
                name = metadata["name"][:15]
                category = metadata["category"][:10]
                json_preview = chunk["content"][:30] + "..."
                print(f"{i:2d} | {name:15s} | {category:10s} | {json_preview}")

        except Exception as e:
            print(f"❌ Dual storage test failed: {str(e)}")


async def main():
    """Main test function"""
    tester = RealAIExtractionTester()

    print("🤖 REAL AI SERVICE EXTRACTION TESTING")
    print("=" * 80)
    print("Testing extraction with DeepSeek/ChatGPT API")
    print("This tests the complete flow that backend will use")
    print()

    # Test 1: Real AI extraction
    await tester.test_real_ai_extraction()

    # Test 2: Dual storage with AI
    await tester.test_dual_storage_with_ai()

    print("\n🎉 REAL AI EXTRACTION TESTS COMPLETED!")
    print("=" * 80)
    print("💡 This simulation shows:")
    print("   - Real AI service integration")
    print("   - Template-based extraction")
    print("   - Dual storage strategy")
    print("   - Frontend edit capabilities")
    print("   - Production-ready workflow")


if __name__ == "__main__":
    asyncio.run(main())
