"""
Demo and Test Script for Unified Chat System
Script demo và test cho hệ thống chat thống nhất
"""

import asyncio
import json
from typing import Dict, Any
from datetime import datetime

from src.models.unified_models import (
    UnifiedChatRequest, Industry, Language, ChatIntent
)
from src.services.unified_chat_service import unified_chat_service

class UnifiedChatDemo:
    """
    Demo class for testing unified chat system
    Lớp demo để test hệ thống chat thống nhất
    """
    
    def __init__(self):
        self.test_scenarios = self._create_test_scenarios()
    
    def _create_test_scenarios(self) -> Dict[str, list]:
        """
        Create test scenarios for different industries and languages
        Tạo các scenario test cho các ngành và ngôn ngữ khác nhau
        """
        return {
            "banking_vietnamese": [
                {
                    "message": "Chào bạn, tôi muốn tìm hiểu về dịch vụ vay của ngân hàng",
                    "expected_intent": ChatIntent.INFORMATION,
                    "description": "Hỏi thông tin chung về dịch vụ vay"
                },
                {
                    "message": "Tôi cần vay 500 triệu để mua nhà, lãi suất bao nhiêu?",
                    "expected_intent": ChatIntent.SALES_INQUIRY,
                    "description": "Có nhu cầu vay cụ thể"
                },
                {
                    "message": "Cho tôi biết chi nhánh gần nhất",
                    "expected_intent": ChatIntent.INFORMATION,
                    "description": "Hỏi thông tin chi nhánh"
                },
                {
                    "message": "Tôi muốn đăng ký vay thế chấp",
                    "expected_intent": ChatIntent.SALES_INQUIRY,
                    "description": "Đăng ký sản phẩm vay"
                }
            ],
            "banking_english": [
                {
                    "message": "Hello, I would like to know about your loan services",
                    "expected_intent": ChatIntent.INFORMATION,
                    "description": "General inquiry about loan services"
                },
                {
                    "message": "I need to borrow 500 million VND to buy a house, what's the interest rate?",
                    "expected_intent": ChatIntent.SALES_INQUIRY,
                    "description": "Specific loan need"
                },
                {
                    "message": "Can you tell me about your interest rates?",
                    "expected_intent": ChatIntent.INFORMATION,
                    "description": "Information about rates"
                },
                {
                    "message": "I want to apply for a mortgage loan",
                    "expected_intent": ChatIntent.SALES_INQUIRY,
                    "description": "Loan application intent"
                }
            ],
            "restaurant_vietnamese": [
                {
                    "message": "Chào bạn, menu của nhà hàng có món gì?",
                    "expected_intent": ChatIntent.INFORMATION,
                    "description": "Hỏi về thực đơn"
                },
                {
                    "message": "Tôi muốn đặt bàn cho 4 người vào tối nay",
                    "expected_intent": ChatIntent.SALES_INQUIRY,
                    "description": "Đặt bàn"
                },
                {
                    "message": "Nhà hàng có giao hàng không?",
                    "expected_intent": ChatIntent.INFORMATION,
                    "description": "Hỏi dịch vụ giao hàng"
                },
                {
                    "message": "Tôi muốn gọi món takeaway",
                    "expected_intent": ChatIntent.SALES_INQUIRY,
                    "description": "Đặt món mang về"
                }
            ],
            "restaurant_english": [
                {
                    "message": "Hello, what's on your menu?",
                    "expected_intent": ChatIntent.INFORMATION,
                    "description": "Menu inquiry"
                },
                {
                    "message": "I'd like to book a table for 4 people tonight",
                    "expected_intent": ChatIntent.SALES_INQUIRY,
                    "description": "Table reservation"
                },
                {
                    "message": "Do you offer delivery service?",
                    "expected_intent": ChatIntent.INFORMATION,
                    "description": "Delivery information"
                },
                {
                    "message": "I want to place an order for pickup",
                    "expected_intent": ChatIntent.SALES_INQUIRY,
                    "description": "Order placement"
                }
            ]
        }
    
    async def run_comprehensive_demo(self):
        """
        Run comprehensive demo of all features
        Chạy demo toàn diện của tất cả tính năng
        """
        print("🚀 UNIFIED CHAT SYSTEM DEMO")
        print("=" * 50)
        
        # Test language detection / Test phát hiện ngôn ngữ
        await self._test_language_detection()
        
        # Test intent detection / Test phát hiện ý định
        await self._test_intent_detection()
        
        # Test banking scenarios / Test kịch bản ngân hàng
        await self._test_banking_scenarios()
        
        # Test restaurant scenarios / Test kịch bản nhà hàng
        await self._test_restaurant_scenarios()
        
        # Test session management / Test quản lý phiên
        await self._test_session_management()
        
        print("\n✅ DEMO COMPLETED SUCCESSFULLY")
        print("=" * 50)
    
    async def _test_language_detection(self):
        """Test language detection capabilities / Test khả năng phát hiện ngôn ngữ"""
        print("\n📝 TESTING LANGUAGE DETECTION")
        print("-" * 30)
        
        from src.services.language_detector import language_detector
        
        test_messages = [
            ("Xin chào, tôi muốn vay tiền", "Vietnamese"),
            ("Hello, I need a loan", "English"),
            ("Tôi need to borrow money", "Mixed - should detect Vietnamese"),
            ("I want vay tiền", "Mixed - should detect English"),
            ("500 triệu VNĐ", "Vietnamese (currency)"),
            ("500 USD", "English (currency)")
        ]
        
        for message, expected in test_messages:
            result = language_detector.detect_language(message)
            print(f"Message: '{message}'")
            print(f"  Detected: {result.language.value} (confidence: {result.confidence:.2f})")
            print(f"  Expected: {expected}")
            print(f"  Indicators: {result.indicators[:3]}")  # Show first 3 indicators
            print()
    
    async def _test_intent_detection(self):
        """Test intent detection capabilities / Test khả năng phát hiện ý định"""
        print("\n🎯 TESTING INTENT DETECTION")
        print("-" * 30)
        
        from src.services.intent_detector import intent_detector
        
        test_cases = [
            {
                "message": "Tôi muốn vay 500 triệu",
                "industry": Industry.BANKING,
                "expected": ChatIntent.SALES_INQUIRY
            },
            {
                "message": "Lãi suất vay là bao nhiêu?",
                "industry": Industry.BANKING,
                "expected": ChatIntent.INFORMATION
            },
            {
                "message": "I want to book a table",
                "industry": Industry.RESTAURANT,
                "expected": ChatIntent.SALES_INQUIRY
            },
            {
                "message": "What's on the menu?",
                "industry": Industry.RESTAURANT,
                "expected": ChatIntent.INFORMATION
            }
        ]
        
        for case in test_cases:
            result = await intent_detector.detect_intent(
                message=case["message"],
                industry=case["industry"],
                company_id="demo_company"
            )
            
            print(f"Message: '{case['message']}'")
            print(f"  Industry: {case['industry'].value}")
            print(f"  Detected: {result.intent.value} (confidence: {result.confidence:.2f})")
            print(f"  Expected: {case['expected'].value}")
            print(f"  Match: {'✅' if result.intent == case['expected'] else '❌'}")
            print(f"  Reasoning: {result.reasoning}")
            print()
    
    async def _test_banking_scenarios(self):
        """Test banking conversation scenarios / Test kịch bản hội thoại ngân hàng"""
        print("\n🏦 TESTING BANKING SCENARIOS")
        print("-" * 30)
        
        # Test Vietnamese banking conversation / Test hội thoại ngân hàng tiếng Việt
        await self._test_conversation_flow(
            scenarios=self.test_scenarios["banking_vietnamese"],
            industry=Industry.BANKING,
            language=Language.VIETNAMESE,
            title="Vietnamese Banking Conversation"
        )
        
        # Test English banking conversation / Test hội thoại ngân hàng tiếng Anh
        await self._test_conversation_flow(
            scenarios=self.test_scenarios["banking_english"],
            industry=Industry.BANKING,
            language=Language.ENGLISH,
            title="English Banking Conversation"
        )
    
    async def _test_restaurant_scenarios(self):
        """Test restaurant conversation scenarios / Test kịch bản hội thoại nhà hàng"""
        print("\n🍽️ TESTING RESTAURANT SCENARIOS")
        print("-" * 30)
        
        # Test Vietnamese restaurant conversation / Test hội thoại nhà hàng tiếng Việt
        await self._test_conversation_flow(
            scenarios=self.test_scenarios["restaurant_vietnamese"],
            industry=Industry.RESTAURANT,
            language=Language.VIETNAMESE,
            title="Vietnamese Restaurant Conversation"
        )
        
        # Test English restaurant conversation / Test hội thoại nhà hàng tiếng Anh
        await self._test_conversation_flow(
            scenarios=self.test_scenarios["restaurant_english"],
            industry=Industry.RESTAURANT,
            language=Language.ENGLISH,
            title="English Restaurant Conversation"
        )
    
    async def _test_conversation_flow(
        self,
        scenarios: list,
        industry: Industry,
        language: Language,
        title: str
    ):
        """Test a complete conversation flow / Test luồng hội thoại hoàn chỉnh"""
        print(f"\n📋 {title}")
        print("." * 25)
        
        session_id = f"demo_{industry.value}_{language.value}_{int(datetime.now().timestamp())}"
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\nStep {i}: {scenario['description']}")
            print(f"User: {scenario['message']}")
            
            # Create request / Tạo request
            request = UnifiedChatRequest(
                message=scenario['message'],
                company_id=f"demo_{industry.value}",
                industry=industry,
                session_id=session_id,
                user_id="demo_user",
                language=language
            )
            
            try:
                # Process message / Xử lý tin nhắn
                response = await unified_chat_service.process_message(request)
                
                # Display results / Hiển thị kết quả
                print(f"AI: {response.response[:200]}{'...' if len(response.response) > 200 else ''}")
                print(f"Intent: {response.intent.value} (confidence: {response.confidence:.2f})")
                print(f"Language: {response.language.value}")
                print(f"Expected Intent: {scenario['expected_intent'].value}")
                print(f"Match: {'✅' if response.intent == scenario['expected_intent'] else '❌'}")
                
                if response.suggestions:
                    print(f"Suggestions: {', '.join(response.suggestions[:2])}")
                
            except Exception as e:
                print(f"❌ Error: {e}")
            
            print("-" * 40)
    
    async def _test_session_management(self):
        """Test session management features / Test tính năng quản lý phiên"""
        print("\n💾 TESTING SESSION MANAGEMENT")
        print("-" * 30)
        
        session_id = f"demo_session_{int(datetime.now().timestamp())}"
        
        # Send multiple messages to build session history / Gửi nhiều tin nhắn để tạo lịch sử phiên
        messages = [
            "Chào bạn!",
            "Tôi muốn tìm hiểu về vay mua nhà",
            "Lãi suất thế nào?",
            "Tôi có thể vay tối đa bao nhiêu?"
        ]
        
        print("Building conversation history...")
        for msg in messages:
            request = UnifiedChatRequest(
                message=msg,
                company_id="demo_banking",
                industry=Industry.BANKING,
                session_id=session_id,
                user_id="demo_user",
                language=Language.AUTO_DETECT
            )
            
            response = await unified_chat_service.process_message(request)
            print(f"User: {msg}")
            print(f"AI: {response.response[:100]}...")
            print()
        
        # Check session data / Kiểm tra dữ liệu phiên
        session_data = unified_chat_service._get_session_data(session_id)
        conversation_history = unified_chat_service._get_conversation_history(session_id)
        
        print(f"Session ID: {session_id}")
        print(f"Session Data: {session_data}")
        print(f"Conversation History Length: {len(conversation_history)}")
        print(f"Last Message: {conversation_history[-1].content if conversation_history else 'None'}")
    
    async def interactive_demo(self):
        """
        Interactive demo where user can input messages
        Demo tương tác nơi người dùng có thể nhập tin nhắn
        """
        print("🤖 INTERACTIVE UNIFIED CHAT DEMO")
        print("=" * 40)
        print("Available industries:", [industry.value for industry in Industry])
        print("Available languages: vi, en, auto")
        print("Type 'quit' to exit")
        print("-" * 40)
        
        # Get user preferences / Lấy ưa thích người dùng
        industry_input = input("Choose industry (banking/restaurant/hotel): ").strip().lower()
        language_input = input("Choose language (vi/en/auto): ").strip().lower()
        
        # Map inputs / Ánh xạ inputs
        industry_map = {
            "banking": Industry.BANKING,
            "restaurant": Industry.RESTAURANT,
            "hotel": Industry.HOTEL
        }
        
        language_map = {
            "vi": Language.VIETNAMESE,
            "en": Language.ENGLISH,
            "auto": Language.AUTO_DETECT
        }
        
        industry = industry_map.get(industry_input, Industry.BANKING)
        language = language_map.get(language_input, Language.AUTO_DETECT)
        
        session_id = f"interactive_{int(datetime.now().timestamp())}"
        
        print(f"\n🎯 Selected: {industry.value} | {language.value}")
        print("=" * 40)
        
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                
                if not user_input:
                    continue
                
                # Create request / Tạo request
                request = UnifiedChatRequest(
                    message=user_input,
                    company_id=f"demo_{industry.value}",
                    industry=industry,
                    session_id=session_id,
                    user_id="interactive_user",
                    language=language
                )
                
                # Process message / Xử lý tin nhắn
                response = await unified_chat_service.process_message(request)
                
                # Display response / Hiển thị phản hồi
                print(f"🤖 AI: {response.response}")
                print(f"   📊 Intent: {response.intent.value} | Confidence: {response.confidence:.2f}")
                print(f"   🌐 Language: {response.language.value}")
                
                if response.suggestions:
                    print(f"   💡 Suggestions: {', '.join(response.suggestions)}")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("\n👋 Thank you for using Unified Chat Demo!")

async def main():
    """Main demo function / Hàm demo chính"""
    demo = UnifiedChatDemo()
    
    print("Choose demo mode:")
    print("1. Comprehensive automated demo")
    print("2. Interactive demo")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        await demo.run_comprehensive_demo()
    elif choice == "2":
        await demo.interactive_demo()
    else:
        print("Invalid choice. Running comprehensive demo...")
        await demo.run_comprehensive_demo()

if __name__ == "__main__":
    asyncio.run(main())
