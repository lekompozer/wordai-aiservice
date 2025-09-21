"""
Direct Test with Unified Chat Service
Test trực tiếp với UnifiedChatService mà không cần setup Qdrant trước
"""

import asyncio
import uuid
from datetime import datetime
from src.services.unified_chat_service import UnifiedChatService
from src.models.unified_models import UnifiedChatRequest, Industry, Language

async def test_companies_direct():
    """Test trực tiếp với UnifiedChatService"""
    print("🚀 Direct Test with 3 Companies")
    print("=" * 60)
    
    chat_service = UnifiedChatService()
    
    # Test scenarios cho 3 công ty
    test_scenarios = [
        {
            "company": "Golden Dragon Restaurant",
            "company_id": "golden-dragon-restaurant",
            "industry": Industry.RESTAURANT,
            "tests": [
                "Tôi muốn đặt bàn cho 4 người vào tối mai lúc 7 giờ",
                "Nhà hàng có món chay không?",
                "Menu đặc biệt của nhà hàng là gì?"
            ]
        },
        {
            "company": "Ivy Fashion Store", 
            "company_id": "ivy-fashion-store",
            "industry": Industry.RETAIL,
            "tests": [
                "Tôi cần tìm váy dự tiệc màu đen size M",
                "Có áo sơ mi nào đang sale không?",
                "Tôi muốn đặt 2 áo thun và 1 quần jeans"
            ]
        },
        {
            "company": "VRB Bank",
            "company_id": "vrb-bank-financial", 
            "industry": Industry.BANKING,
            "tests": [
                "Tôi muốn vay mua nhà 2 tỷ, thu nhập 30 triệu/tháng",
                "Lãi suất thẻ tín dụng VRB là bao nhiêu?",
                "Điều kiện vay vốn kinh doanh như thế nào?"
            ]
        }
    ]
    
    # Test từng công ty
    for scenario in test_scenarios:
        print(f"\n🏢 Testing: {scenario['company']}")
        print("=" * 50)
        
        session_id = f"test-{scenario['company_id']}-{int(datetime.now().timestamp())}"
        
        for i, message in enumerate(scenario['tests'], 1):
            print(f"\n💬 Test {i}: {message}")
            
            request = UnifiedChatRequest(
                message=message,
                company_id=scenario['company_id'],
                session_id=session_id,
                industry=scenario['industry'],
                language=Language.VIETNAMESE,
                context={"test_mode": True}
            )
            
            try:
                response = await chat_service.process_message(request)
                
                print(f"🤖 Response: {response.response}")
                print(f"📋 Intent: {response.intent.value}")
                print(f"📊 Confidence: {response.confidence:.2f}")
                
                # Generate codes based on company and intent
                if scenario['industry'] == Industry.RESTAURANT and "đặt bàn" in message.lower():
                    booking_code = f"GD{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                    print(f"🎫 Booking Code: {booking_code}")
                    print(f"📅 Reservation: Table for 4, {datetime.now().strftime('%Y-%m-%d')} 19:00")
                    print(f"📞 Contact: 1900 888 999 for confirmation")
                    
                elif scenario['industry'] == Industry.RETAIL and ("đặt" in message.lower() or "mua" in message.lower()):
                    order_code = f"IV{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                    print(f"🛒 Order Code: {order_code}")
                    print(f"📦 Items: Fashion products (áo thun, quần jeans)")
                    print(f"💰 Estimated Total: 890,000 - 1,450,000 VNĐ")
                    print(f"🚚 Delivery: 3-5 business days")
                    
                elif scenario['industry'] == Industry.BANKING and "vay" in message.lower():
                    assessment_code = f"VRB{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                    print(f"📋 Assessment Code: {assessment_code}")
                    print(f"💵 Loan Amount: 2,000,000,000 VNĐ")
                    print(f"📈 Interest Rate: 8.5%/year (home loan)")
                    print(f"⏰ Processing Time: 7-14 business days")
                    print(f"📄 Required: ID, Income proof, Property documents")
                
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()

async def interactive_console():
    """Console tương tác đơn giản"""
    print("\n🖥️ Interactive Console for 3 Companies")
    print("=" * 50)
    
    companies = {
        "1": {"id": "golden-dragon-restaurant", "name": "Golden Dragon Restaurant", "industry": Industry.RESTAURANT},
        "2": {"id": "ivy-fashion-store", "name": "Ivy Fashion Store", "industry": Industry.RETAIL},
        "3": {"id": "vrb-bank-financial", "name": "VRB Bank", "industry": Industry.BANKING}
    }
    
    print("Select company:")
    for key, company in companies.items():
        print(f"  {key}. {company['name']} ({company['industry'].value})")
    
    choice = input("\nEnter company number (1-3): ").strip()
    
    if choice not in companies:
        print("❌ Invalid choice")
        return
    
    company = companies[choice]
    chat_service = UnifiedChatService()
    session_id = f"console-{company['id']}-{int(datetime.now().timestamp())}"
    
    print(f"\n💬 Chatting with {company['name']}")
    print("Type 'quit' to exit\n")
    
    while True:
        try:
            message = input("You: ").strip()
            
            if message.lower() == 'quit':
                print("👋 Goodbye!")
                break
            
            request = UnifiedChatRequest(
                message=message,
                company_id=company['id'],
                session_id=session_id,
                industry=company['industry'],
                language=Language.VIETNAMESE,
                context={"console_test": True}
            )
            
            response = await chat_service.process_message(request)
            
            print(f"AI: {response.response}")
            print(f"Intent: {response.intent.value} (confidence: {response.confidence:.2f})")
            
            # Generate codes
            if company['industry'] == Industry.RESTAURANT and "đặt bàn" in message.lower():
                code = f"GD{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                print(f"🎫 Booking Code: {code}")
            elif company['industry'] == Industry.RETAIL and ("đặt" in message.lower() or "mua" in message.lower()):
                code = f"IV{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
                print(f"🛒 Order Code: {code}")
            elif company['industry'] == Industry.BANKING and "vay" in message.lower():
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
    print("1. Automated test (predefined conversations)")
    print("2. Interactive console (manual chat)")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        await test_companies_direct()
    elif choice == "2":
        await interactive_console()
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    asyncio.run(main())
