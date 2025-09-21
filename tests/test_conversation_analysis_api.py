"""
Test script for Conversation Analysis API with Google Gemini
Script test cho API phân tích cuộc trò chuyện với Google Gemini
"""

import asyncio
import json
import requests
from datetime import datetime
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
COMPANY_ID = "test_company_001"
TEST_SESSION_ID = "test_session_001"


class ConversationAnalysisAPITester:
    """
    Tester for new conversation analysis endpoints
    """

    def __init__(self, base_url: str = BASE_URL, company_id: str = COMPANY_ID):
        self.base_url = base_url
        self.company_id = company_id
        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "X-Company-Id": company_id}
        )

    def test_health_check(self) -> bool:
        """Test if API is running"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            print(f"🏥 Health Check: {response.status_code}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False

    def test_conversation_summary(
        self, conversation_id: str = TEST_SESSION_ID
    ) -> Dict[str, Any]:
        """
        Test conversation summary endpoint
        Test endpoint tóm tắt cuộc trò chuyện
        """
        try:
            print(f"\n📊 Testing Conversation Summary API")
            print(f"   Conversation ID: {conversation_id}")

            url = f"{self.base_url}/api/conversation/{conversation_id}/summary"
            response = self.session.get(url)

            print(f"   Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Summary retrieved successfully")
                print(f"   Message Count: {data.get('message_count', 0)}")
                print(f"   User Messages: {data.get('user_messages', 0)}")
                print(f"   AI Messages: {data.get('ai_messages', 0)}")
                print(f"   Status: {data.get('status', 'Unknown')}")
                return data
            elif response.status_code == 404:
                print(f"   ⚠️ Conversation not found")
                return {"error": "Conversation not found"}
            else:
                print(f"   ❌ Error: {response.text}")
                return {"error": response.text}

        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return {"error": str(e)}

    def test_conversation_deep_analysis(
        self, session_id: str = TEST_SESSION_ID
    ) -> Dict[str, Any]:
        """
        Test deep conversation analysis with Gemini
        Test phân tích chuyên sâu cuộc trò chuyện với Gemini
        """
        try:
            print(f"\n🤖 Testing Deep Conversation Analysis API (Gemini)")
            print(f"   Session ID: {session_id}")

            url = f"{self.base_url}/api/conversation/analyze"
            payload = {"session_id": session_id, "company_id": self.company_id}

            response = self.session.post(url, json=payload)

            print(f"   Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Analysis completed successfully")

                analysis = data.get("analysis", {})
                print(f"   AI Provider: {data.get('ai_provider', 'Unknown')}")
                print(f"   Primary Intent: {analysis.get('primary_intent', 'Unknown')}")
                print(
                    f"   Customer Satisfaction: {analysis.get('customer_satisfaction', 'Unknown')}"
                )
                print(
                    f"   Conversation Outcome: {analysis.get('conversation_outcome', 'Unknown')}"
                )

                remarketing_opps = analysis.get("remarketing_opportunities", [])
                print(f"   Remarketing Opportunities: {len(remarketing_opps)}")

                if remarketing_opps:
                    for i, opp in enumerate(remarketing_opps[:2]):  # Show first 2
                        print(
                            f"     {i+1}. {opp.get('type')} - {opp.get('priority')} priority"
                        )
                        print(f"        {opp.get('suggestion', '')[:100]}...")

                return data
            else:
                print(f"   ❌ Error: {response.text}")
                return {"error": response.text}

        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return {"error": str(e)}

    def test_conversation_list(self) -> Dict[str, Any]:
        """
        Test conversation list endpoint
        Test endpoint danh sách cuộc trò chuyện
        """
        try:
            print(f"\n📋 Testing Conversation List API")

            url = f"{self.base_url}/api/conversation/list"
            response = self.session.get(url)

            print(f"   Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                conversations = data.get("conversations", [])
                print(f"   ✅ List retrieved successfully")
                print(f"   Total Conversations: {data.get('total', 0)}")
                print(f"   Returned: {len(conversations)}")

                # Show first few conversations
                for i, conv in enumerate(conversations[:3]):
                    print(
                        f"     {i+1}. {conv.get('conversation_id')} - {conv.get('status')}"
                    )
                    print(
                        f"        Messages: {conv.get('message_count')}, Last: {conv.get('last_activity')}"
                    )

                return data
            else:
                print(f"   ❌ Error: {response.text}")
                return {"error": response.text}

        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return {"error": str(e)}

    def create_test_conversation(self) -> str:
        """
        Create a test conversation for testing analysis
        Tạo cuộc trò chuyện test để test phân tích
        """
        try:
            print(f"\n💬 Creating Test Conversation")

            # Create unified chat request
            url = f"{self.base_url}/api/unified/chat"

            test_messages = [
                "Chào bạn, tôi muốn tìm hiểu về sản phẩm vay mua nhà của ngân hàng",
                "Lãi suất hiện tại như thế nào? Có ưu đãi gì không?",
                "Tôi cần vay khoảng 2 tỷ, thu nhập 50 triệu/tháng. Có được duyệt không?",
                "Thủ tục phức tạp lắm không? Bao lâu thì có kết quả?",
                "Cảm ơn bạn. Tôi sẽ cân nhắc và liên hệ lại sau.",
            ]

            session_id = f"test_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            for i, message in enumerate(test_messages):
                payload = {
                    "message": message,
                    "user_info": {
                        "user_id": "test_user_001",
                        "name": "Nguyen Van Test",
                        "source": "web",
                    },
                    "session_id": session_id,
                    "company_id": self.company_id,
                    "industry": "BANKING",
                    "language": "VIETNAMESE",
                }

                print(f"   Sending message {i+1}: {message[:50]}...")
                response = self.session.post(url, json=payload)

                if response.status_code == 200:
                    print(f"     ✅ Message {i+1} sent successfully")
                else:
                    print(f"     ❌ Message {i+1} failed: {response.status_code}")

                # Small delay between messages
                import time

                time.sleep(0.5)

            print(f"   ✅ Test conversation created with session: {session_id}")
            return session_id

        except Exception as e:
            print(f"   ❌ Failed to create test conversation: {e}")
            return ""

    def run_comprehensive_test(self):
        """
        Run all tests in sequence
        Chạy tất cả test theo thứ tự
        """
        print("=" * 80)
        print("🚀 CONVERSATION ANALYSIS API COMPREHENSIVE TEST")
        print("=" * 80)

        # 1. Health check
        if not self.test_health_check():
            print("❌ API is not running. Please start the server first.")
            return

        # 2. Create test conversation
        test_session_id = self.create_test_conversation()
        if not test_session_id:
            print("❌ Failed to create test conversation. Using default session.")
            test_session_id = TEST_SESSION_ID

        # 3. Test conversation summary
        summary_result = self.test_conversation_summary(test_session_id)

        # 4. Test deep analysis with Gemini
        analysis_result = self.test_conversation_deep_analysis(test_session_id)

        # 5. Test conversation list
        list_result = self.test_conversation_list()

        # 6. Summary report
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY REPORT")
        print("=" * 80)

        print(f"✅ Health Check: Passed")
        print(f"✅ Test Conversation: {test_session_id}")

        if "error" not in summary_result:
            print(f"✅ Conversation Summary: Passed")
        else:
            print(
                f"❌ Conversation Summary: Failed - {summary_result.get('error', 'Unknown')}"
            )

        if "error" not in analysis_result:
            print(f"✅ Deep Analysis (Gemini): Passed")
            analysis = analysis_result.get("analysis", {})
            if analysis.get("primary_intent"):
                print(f"   Intent Detected: {analysis.get('primary_intent')}")
            if analysis.get("remarketing_opportunities"):
                print(
                    f"   Remarketing Ops: {len(analysis.get('remarketing_opportunities', []))}"
                )
        else:
            print(
                f"❌ Deep Analysis (Gemini): Failed - {analysis_result.get('error', 'Unknown')}"
            )

        if "error" not in list_result:
            print(f"✅ Conversation List: Passed")
            print(f"   Total Conversations: {list_result.get('total', 0)}")
        else:
            print(
                f"❌ Conversation List: Failed - {list_result.get('error', 'Unknown')}"
            )

        print("\n🎉 Testing completed!")
        print("=" * 80)


def main():
    """Main test runner"""
    tester = ConversationAnalysisAPITester()
    tester.run_comprehensive_test()


if __name__ == "__main__":
    main()
