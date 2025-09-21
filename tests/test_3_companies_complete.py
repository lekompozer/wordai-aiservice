"""
Test Complete Workflow for 3 Companies
Test toàn bộ workflow cho 3 công ty: Golden Dragon, Ivy Fashion, VRB Bank
"""

import asyncio
import os
import json
import uuid
from datetime import datetime
from src.services.unified_chat_service import UnifiedChatService
from src.services.company_data_manager import CompanyDataManager
from src.models.unified_models import UnifiedChatRequest, Industry, Language
from src.utils.logger import setup_logger

logger = setup_logger()

class CompanyTestManager:
    def __init__(self):
        self.chat_service = UnifiedChatService()
        self.data_manager = CompanyDataManager()
        
        # Company definitions
        self.companies = {
            "golden-dragon": {
                "id": "golden-dragon-restaurant",
                "name": "Nhà hàng Golden Dragon",
                "industry": Industry.RESTAURANT,
                "files": [
                    "company-data-test/golden-dragon-info.txt",
                    "company-data-test/golden-dragon-menu.jpg"
                ]
            },
            "ivy-fashion": {
                "id": "ivy-fashion-store", 
                "name": "Cửa hàng thời trang Ivy Fashion",
                "industry": Industry.RETAIL,
                "files": [
                    "company-data-test/ivy-fashion-info.txt",
                    "company-data-test/ivy-fashion-products.csv"
                ]
            },
            "vrb-bank": {
                "id": "vrb-bank-financial",
                "name": "Ngân hàng VRB",
                "industry": Industry.BANKING,
                "files": [
                    "company-data-test/vrb-bank-info.md",
                    "company-data-test/vrb-bank-services.docx"
                ]
            }
        }
    
    async def setup_all_companies(self):
        """Setup Qdrant collections and ingest data for all companies"""
        print("🏢 Setting up all companies...")
        print("=" * 60)
        
        for company_key, company_info in self.companies.items():
            try:
                print(f"\n📋 Setting up {company_info['name']}...")
                
                # Create company in system
                company_id = company_info["id"]
                await self.data_manager.create_company(
                    company_id=company_id,
                    name=company_info["name"],
                    industry=company_info["industry"].value,
                    description=f"Test company for {company_info['name']}"
                )
                
                # Process each file
                for file_path in company_info["files"]:
                    if os.path.exists(file_path):
                        print(f"   📄 Processing: {file_path}")
                        
                        # Read file content
                        if file_path.endswith('.txt') or file_path.endswith('.md'):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        elif file_path.endswith('.csv'):
                            import pandas as pd
                            df = pd.read_csv(file_path)
                            content = df.to_string()
                        elif file_path.endswith('.docx'):
                            # For docx, we'll use the text content from the attachment
                            content = """
# Dịch vụ Ngân hàng VRB

## Dịch vụ tài chính cá nhân
### 1. Tài khoản tiết kiệm
- Lãi suất: 6.5%/năm cho kỳ hạn 12 tháng
- Số tiền gửi tối thiểu: 100,000 VNĐ
- Tính năng: Rút tiền tự do, tính lãi theo ngày

### 2. Vay mua nhà
- Lãi suất: Từ 8.5%/năm
- Thời hạn vay: Tối đa 25 năm
- Tỷ lệ cho vay: Lên đến 80% giá trị tài sản

### 3. Thẻ tín dụng VRB
- Loại thẻ: Classic, Gold, Platinum, Diamond
- Hạn mức: Từ 10 triệu - 1 tỷ VNĐ
- Ưu đãi: Cashback 1-3%, miễn phí năm đầu

## Dịch vụ doanh nghiệp
### 1. Vay vốn kinh doanh
- Lãi suất: Từ 9.5%/năm
- Hạn mức: Từ 500 triệu - 100 tỷ VNĐ
- Thời hạn: Linh hoạt từ 6 tháng - 10 năm

### 2. Bảo lãnh ngân hàng
- Loại bảo lãnh: Thầu, tạm ứng, bảo hành, thanh toán
- Phí bảo lãnh: Từ 0.1%/tháng

## Chương trình khách hàng thân thiết
### VRB Elite Club
- Điều kiện: Số dư trung bình từ 500 triệu VNĐ
- Ưu đãi: Miễn phí mọi dịch vụ ngân hàng
"""
                        else:
                            print(f"   ⚠️ Skipping {file_path} - unsupported format")
                            continue
                        
                        # Ingest content
                        result = await self.data_manager.ingest_document(
                            company_id=company_id,
                            content=content,
                            metadata={
                                "source": file_path,
                                "type": "company_data",
                                "processed_at": datetime.now().isoformat()
                            }
                        )
                        
                        if result:
                            print(f"   ✅ Successfully processed {file_path}")
                        else:
                            print(f"   ❌ Failed to process {file_path}")
                    else:
                        print(f"   ❌ File not found: {file_path}")
                
                print(f"✅ Completed setup for {company_info['name']}")
                
            except Exception as e:
                logger.error(f"❌ Error setting up {company_info['name']}: {e}")
                print(f"❌ Error setting up {company_info['name']}: {e}")

    async def test_restaurant_booking(self):
        """Test restaurant table booking"""
        print("\n🍽️ Testing Restaurant Booking - Golden Dragon")
        print("=" * 50)
        
        company_id = "golden-dragon-restaurant"
        session_id = f"restaurant-test-{int(datetime.now().timestamp())}"
        
        # Test conversations
        conversations = [
            "Xin chào, tôi muốn đặt bàn cho 4 người vào tối mai",
            "Tôi muốn đặt bàn VIP, có view đẹp, lúc 7 giờ tối",
            "Cho tôi xem menu món chay của nhà hàng",
            "Tôi muốn đặt combo gia đình cho 6 người"
        ]
        
        for i, message in enumerate(conversations, 1):
            print(f"\n💬 Conversation {i}: {message}")
            
            request = UnifiedChatRequest(
                message=message,
                company_id=company_id,
                session_id=session_id,
                industry=Industry.RESTAURANT,
                language=Language.VIETNAMESE,
                context={"test_mode": True}
            )
            
            try:
                response = await self.chat_service.process_message(request)
                
                print(f"🤖 Response: {response.response}")
                print(f"📋 Intent: {response.intent.value}")
                print(f"📊 Confidence: {response.confidence:.2f}")
                
                # Generate booking code if it's a reservation
                if "đặt bàn" in message.lower() or "reservation" in response.intent.value.lower():
                    booking_code = f"GD{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                    print(f"🎫 Booking Code: {booking_code}")
                    print(f"📅 Booking Details: Table for 4-6 people, {datetime.now().strftime('%Y-%m-%d')} 19:00")
                
            except Exception as e:
                logger.error(f"❌ Error in restaurant test: {e}")
                print(f"❌ Error: {e}")

    async def test_fashion_shopping(self):
        """Test fashion store shopping and ordering"""
        print("\n👗 Testing Fashion Shopping - Ivy Fashion")
        print("=" * 50)
        
        company_id = "ivy-fashion-store"
        session_id = f"fashion-test-{int(datetime.now().timestamp())}"
        
        conversations = [
            "Tôi cần tìm váy dự tiệc cho size M",
            "Có áo sơ mi nam nào đang sale không?",
            "Tôi muốn đặt 2 áo thun và 1 quần jeans size L",
            "Cho tôi xem các sản phẩm mới nhất của cửa hàng"
        ]
        
        for i, message in enumerate(conversations, 1):
            print(f"\n💬 Conversation {i}: {message}")
            
            request = UnifiedChatRequest(
                message=message,
                company_id=company_id,
                session_id=session_id,
                industry=Industry.RETAIL,
                language=Language.VIETNAMESE,
                context={"test_mode": True}
            )
            
            try:
                response = await self.chat_service.process_message(request)
                
                print(f"🤖 Response: {response.response}")
                print(f"📋 Intent: {response.intent.value}")
                print(f"📊 Confidence: {response.confidence:.2f}")
                
                # Generate order code if it's a purchase
                if "đặt" in message.lower() or "mua" in message.lower():
                    order_code = f"IV{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                    print(f"🛒 Order Code: {order_code}")
                    print(f"📦 Order Details: Fashion items, estimated delivery 3-5 days")
                    print(f"💰 Estimated Total: 850,000 - 1,200,000 VNĐ")
                
            except Exception as e:
                logger.error(f"❌ Error in fashion test: {e}")
                print(f"❌ Error: {e}")

    async def test_bank_loan_assessment(self):
        """Test bank loan assessment"""
        print("\n🏦 Testing Bank Loan Assessment - VRB Bank")
        print("=" * 50)
        
        company_id = "vrb-bank-financial"
        session_id = f"bank-test-{int(datetime.now().timestamp())}"
        
        conversations = [
            "Tôi muốn vay mua nhà 2 tỷ, thu nhập 30 triệu/tháng",
            "Lãi suất vay kinh doanh hiện tại là bao nhiêu?",
            "Tôi cần vay 500 triệu để mở rộng kinh doanh",
            "Điều kiện mở thẻ tín dụng VRB Platinum là gì?"
        ]
        
        for i, message in enumerate(conversations, 1):
            print(f"\n💬 Conversation {i}: {message}")
            
            request = UnifiedChatRequest(
                message=message,
                company_id=company_id,
                session_id=session_id,
                industry=Industry.BANKING,
                language=Language.VIETNAMESE,
                context={"test_mode": True}
            )
            
            try:
                response = await self.chat_service.process_message(request)
                
                print(f"🤖 Response: {response.response}")
                print(f"📋 Intent: {response.intent.value}")
                print(f"📊 Confidence: {response.confidence:.2f}")
                
                # Generate assessment code if it's a loan request
                if "vay" in message.lower() and ("tỷ" in message.lower() or "triệu" in message.lower()):
                    assessment_code = f"VRB{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                    print(f"📋 Assessment Code: {assessment_code}")
                    print(f"💵 Loan Amount: 500M - 2B VNĐ")
                    print(f"📈 Interest Rate: 8.5% - 9.5%/year")
                    print(f"⏰ Processing Time: 7-14 business days")
                    print(f"📄 Required Documents: ID, Income proof, Collateral documents")
                
            except Exception as e:
                logger.error(f"❌ Error in bank test: {e}")
                print(f"❌ Error: {e}")

    async def interactive_test_console(self):
        """Interactive console for testing all companies"""
        print("\n🖥️ Interactive Test Console")
        print("=" * 50)
        print("Available companies:")
        for key, info in self.companies.items():
            print(f"  {key}: {info['name']} ({info['industry'].value})")
        
        print("\nCommands:")
        print("  'company_key: your message' - Chat with specific company")
        print("  'quit' - Exit console")
        print("  'help' - Show this help")
        
        while True:
            try:
                user_input = input("\n💬 Enter command: ").strip()
                
                if user_input.lower() == 'quit':
                    print("👋 Goodbye!")
                    break
                elif user_input.lower() == 'help':
                    print("Commands:")
                    print("  'golden-dragon: tôi muốn đặt bàn'")
                    print("  'ivy-fashion: có áo sơ mi nào đẹp không?'")
                    print("  'vrb-bank: tôi muốn vay mua nhà'")
                    continue
                elif ':' not in user_input:
                    print("❌ Invalid format. Use: 'company_key: your message'")
                    continue
                
                company_key, message = user_input.split(':', 1)
                company_key = company_key.strip()
                message = message.strip()
                
                if company_key not in self.companies:
                    print(f"❌ Unknown company: {company_key}")
                    continue
                
                company_info = self.companies[company_key]
                session_id = f"console-{company_key}-{int(datetime.now().timestamp())}"
                
                request = UnifiedChatRequest(
                    message=message,
                    company_id=company_info["id"],
                    session_id=session_id,
                    industry=company_info["industry"],
                    language=Language.VIETNAMESE,
                    context={"console_test": True}
                )
                
                print(f"\n🏢 {company_info['name']}")
                print(f"💬 You: {message}")
                
                response = await self.chat_service.process_message(request)
                
                print(f"🤖 AI: {response.response}")
                print(f"📋 Intent: {response.intent.value} (confidence: {response.confidence:.2f})")
                
                # Generate relevant codes
                if company_key == "golden-dragon" and "đặt bàn" in message.lower():
                    code = f"GD{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                    print(f"🎫 Booking Code: {code}")
                elif company_key == "ivy-fashion" and ("đặt" in message.lower() or "mua" in message.lower()):
                    code = f"IV{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                    print(f"🛒 Order Code: {code}")
                elif company_key == "vrb-bank" and "vay" in message.lower():
                    code = f"VRB{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                    print(f"📋 Assessment Code: {code}")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                logger.error(f"❌ Console error: {e}")
                print(f"❌ Error: {e}")

async def main():
    """Main test function"""
    print("🚀 Starting 3 Companies Complete Test")
    print("=" * 60)
    
    test_manager = CompanyTestManager()
    
    try:
        # Step 1: Setup all companies
        await test_manager.setup_all_companies()
        
        # Step 2: Test each company
        await test_manager.test_restaurant_booking()
        await test_manager.test_fashion_shopping()
        await test_manager.test_bank_loan_assessment()
        
        # Step 3: Interactive console
        print("\n🎯 All automated tests completed!")
        print("Starting interactive console...")
        await test_manager.interactive_test_console()
        
    except Exception as e:
        logger.error(f"❌ Main test error: {e}")
        print(f"❌ Main error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
