"""
Simple Test Script for 3 Companies
Test đơn giản cho 3 công ty: Golden Dragon, Ivy Fashion, VRB Bank
"""

import asyncio
import uuid
from datetime import datetime
from src.services.unified_chat_service import UnifiedChatService
from src.models.unified_models import UnifiedChatRequest, Industry, Language

async def test_companies_chat():
    """Test chat với 3 công ty"""
    print("🚀 Testing 3 Companies Chat System")
    print("=" * 60)
    
    chat_service = UnifiedChatService()
    
    # Test data cho 3 công ty
    companies = [
        {
            "id": "golden-dragon-restaurant",
            "name": "Nhà hàng Golden Dragon", 
            "industry": Industry.RESTAURANT,
            "test_messages": [
                "Tôi muốn đặt bàn cho 4 người vào tối mai lúc 7 giờ",
                "Cho tôi xem menu món chay có gì",
                "Nhà hàng có phòng VIP không?"
            ]
        },
        {
            "id": "ivy-fashion-store",
            "name": "Cửa hàng Ivy Fashion",
            "industry": Industry.RETAIL, 
            "test_messages": [
                "Tôi cần tìm váy dự tiệc size M màu đen",
                "Có áo sơ mi nam nào đang giảm giá không?",
                "Tôi muốn đặt 2 áo thun và 1 quần jeans"
            ]
        },
        {
            "id": "vrb-bank-financial",
            "name": "Ngân hàng VRB",
            "industry": Industry.FINANCE,
            "test_messages": [
                "Tôi muốn vay mua nhà 2 tỷ, thu nhập 30 triệu/tháng",
                "Lãi suất thẻ tín dụng VRB hiện tại là bao nhiêu?",
                "Điều kiện vay vốn kinh doanh là gì?"
            ]
        }
    ]
    
    # Test từng công ty
    for company in companies:
        print(f"\n🏢 Testing {company['name']}")
        print("=" * 50)
        
        session_id = f"test-{company['id']}-{int(datetime.now().timestamp())}"
        
        for i, message in enumerate(company['test_messages'], 1):
            print(f"\n💬 Test {i}: {message}")
            
            request = UnifiedChatRequest(
                message=message,
                company_id=company['id'],
                session_id=session_id,
                industry=company['industry'],
                language=Language.VIETNAMESE,
                context={"test_mode": True}
            )
            
            try:
                response = await chat_service.process_message(request)
                
                print(f"🤖 Response: {response.response}")
                print(f"📋 Intent: {response.intent.value}")
                print(f"📊 Confidence: {response.confidence:.2f}")
                
                # Generate relevant codes based on company and intent
                if company['industry'] == Industry.RESTAURANT and "đặt bàn" in message.lower():
                    booking_code = f"GD{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                    print(f"🎫 Booking Code: {booking_code}")
                    print(f"📅 Table: 4 people, {datetime.now().strftime('%Y-%m-%d')} 19:00")
                    
                elif company['industry'] == Industry.RETAIL and ("đặt" in message.lower() or "mua" in message.lower()):
                    order_code = f"IV{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                    print(f"🛒 Order Code: {order_code}")
                    print(f"📦 Items: Fashion products, delivery 3-5 days")
                    print(f"💰 Estimated: 500,000 - 1,500,000 VNĐ")
                    
                elif company['industry'] == Industry.FINANCE and "vay" in message.lower():
                    assessment_code = f"VRB{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                    print(f"📋 Assessment Code: {assessment_code}")
                    print(f"💵 Loan Amount: 2,000,000,000 VNĐ")
                    print(f"📈 Interest Rate: 8.5%/year")
                    print(f"⏰ Processing: 7-14 days")
                
            except Exception as e:
                print(f"❌ Error: {e}")

async def interactive_console():
    """Console tương tác cho test"""
    print("\n🖥️ Interactive Test Console")
    print("=" * 50)
    print("Available companies:")
    print("  1. golden-dragon: Nhà hàng Golden Dragon")
    print("  2. ivy-fashion: Cửa hàng Ivy Fashion") 
    print("  3. vrb-bank: Ngân hàng VRB")
    print("\nUsage: Enter 'company_key: your message'")
    print("Example: 'golden-dragon: tôi muốn đặt bàn'")
    print("Type 'quit' to exit\n")
    
    chat_service = UnifiedChatService()
    
    company_map = {
        "golden-dragon": {
            "id": "golden-dragon-restaurant",
            "name": "Nhà hàng Golden Dragon",
            "industry": Industry.RESTAURANT
        },
        "ivy-fashion": {
            "id": "ivy-fashion-store", 
            "name": "Cửa hàng Ivy Fashion",
            "industry": Industry.RETAIL
        },
        "vrb-bank": {
            "id": "vrb-bank-financial",
            "name": "Ngân hàng VRB", 
            "industry": Industry.FINANCE
        }
    }
    
    while True:
        try:
            user_input = input("💬 Enter command: ").strip()
            
            if user_input.lower() == 'quit':
                print("👋 Goodbye!")
                break
                
            if ':' not in user_input:
                print("❌ Format: 'company_key: your message'")
                continue
                
            company_key, message = user_input.split(':', 1)
            company_key = company_key.strip()
            message = message.strip()
            
            if company_key not in company_map:
                print(f"❌ Unknown company: {company_key}")
                continue
                
            company = company_map[company_key]
            session_id = f"console-{company_key}-{int(datetime.now().timestamp())}"
            
            request = UnifiedChatRequest(
                message=message,
                company_id=company["id"],
                session_id=session_id,
                industry=company["industry"],
                language=Language.VIETNAMESE,
                context={"console_test": True}
            )
            
            print(f"\n🏢 {company['name']}")
            print(f"💬 You: {message}")
            
            response = await chat_service.process_message(request)
            
            print(f"🤖 AI: {response.response}")
            print(f"📋 Intent: {response.intent.value} (confidence: {response.confidence:.2f})")
            
            # Generate codes
            if company_key == "golden-dragon" and "đặt bàn" in message.lower():
                code = f"GD{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                print(f"🎫 Booking Code: {code}")
            elif company_key == "ivy-fashion" and ("đặt" in message.lower() or "mua" in message.lower()):
                code = f"IV{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                print(f"🛒 Order Code: {code}")
            elif company_key == "vrb-bank" and "vay" in message.lower():
                code = f"VRB{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                print(f"📋 Assessment Code: {code}")
            
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

async def main():
    print("🎯 Choose test mode:")
    print("1. Automated test (run predefined conversations)")
    print("2. Interactive console (manual testing)")
    
    try:
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            await test_companies_chat()
        elif choice == "2":
            await interactive_console()
        else:
            print("❌ Invalid choice")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
