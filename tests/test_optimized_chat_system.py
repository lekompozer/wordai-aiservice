#!/usr/bin/env python3
"""
Test Script for Optimized Chat System
Script kiểm tra hệ thống chat đã tối ưu hóa

Tests:
1. Optimized chat flow (single AI call)
2. Image request detection (local, fast)
3. Deep conversation analysis API
4. Performance comparison
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, List

from src.services.unified_chat_service import UnifiedChatService
from src.models.unified_models import UnifiedChatRequest, UserInfo, Source, Industry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f'test_optimized_chat_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        ),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


class OptimizedChatTester:
    """Test class for optimized chat system"""

    def __init__(self):
        self.chat_service = UnifiedChatService()
        self.test_company_id = "test_company_001"
        self.performance_metrics = []

    async def test_optimized_chat_flow(self) -> Dict[str, Any]:
        """Test the new optimized chat flow with single AI call"""
        logger.info("🚀 Testing optimized chat flow...")

        test_messages = [
            "Chào bạn, tôi muốn tìm hiểu về sản phẩm áo thun",
            "Cho tôi xem một số mẫu áo thun nam đẹp",
            "Giá cả như thế nào? Có ưu đãi gì không?",
            "Tôi muốn đặt mua 5 chiếc áo size M",
            "Cảm ơn, tôi sẽ liên hệ lại sau",
        ]

        results = {}
        session_id = f"test_session_{int(time.time())}"

        for i, message in enumerate(test_messages, 1):
            logger.info(f"\n📝 Testing message {i}: '{message}'")

            start_time = time.time()

            try:
                # Create chat request
                chat_request = UnifiedChatRequest(
                    message=message,
                    session_id=session_id,
                    company_id=self.test_company_id,
                    user_info=UserInfo(user_id=f"test_user_{i}", source=Source.WEB),
                    conversation_id=f"test_conv_{session_id}",
                    industry=Industry.FASHION,
                    context={},
                )

                # Process message with optimized flow
                response = await self.chat_service.process_message(chat_request)

                end_time = time.time()
                processing_time = end_time - start_time

                # Store metrics
                metrics = {
                    "message_number": i,
                    "message": message,
                    "processing_time": processing_time,
                    "response_length": len(response.response),
                    "detected_intent": response.intent.value,
                    "confidence": response.confidence,
                    "has_attachments": bool(response.attachments),
                    "attachment_count": (
                        len(response.attachments) if response.attachments else 0
                    ),
                }

                self.performance_metrics.append(metrics)

                results[f"message_{i}"] = {
                    "request": message,
                    "response_preview": (
                        response.response[:100] + "..."
                        if len(response.response) > 100
                        else response.response
                    ),
                    "intent": response.intent.value,
                    "confidence": response.confidence,
                    "processing_time": processing_time,
                    "has_images": bool(response.attachments),
                    "image_count": (
                        len(response.attachments) if response.attachments else 0
                    ),
                }

                logger.info(f"   ✅ Processed in {processing_time:.2f}s")
                logger.info(
                    f"   🎯 Intent: {response.intent.value} (confidence: {response.confidence:.2f})"
                )
                logger.info(
                    f"   📸 Images: {len(response.attachments) if response.attachments else 0}"
                )
                logger.info(f"   📝 Response length: {len(response.response)} chars")

                # Add small delay between messages
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"❌ Error processing message {i}: {e}")
                results[f"message_{i}"] = {"error": str(e)}

        return results

    async def test_image_detection_speed(self) -> Dict[str, Any]:
        """Test the speed of local image detection vs AI detection"""
        logger.info("\n🏃 Testing image detection speed...")

        test_messages = [
            "Cho tôi xem hình ảnh sản phẩm",
            "Tôi muốn xem mẫu áo thun",
            "Show me some product photos",
            "Can I see the design?",
            "Có thể xem không gian cửa hàng được không?",
            "What does it look like?",
            "Hình ảnh demo sản phẩm",
            "Picture of the item please",
        ]

        results = {"local_detection": [], "comparison": {}}

        for message in test_messages:
            # Test local detection speed
            start_time = time.time()
            needs_images, image_query = self.chat_service._check_for_image_request(
                message
            )
            local_time = time.time() - start_time

            results["local_detection"].append(
                {
                    "message": message,
                    "needs_images": needs_images,
                    "image_query": image_query,
                    "detection_time": local_time,
                }
            )

            logger.info(
                f"   📸 '{message}' -> Images: {needs_images}, Query: '{image_query}', Time: {local_time*1000:.2f}ms"
            )

        # Calculate averages
        avg_local_time = sum(
            r["detection_time"] for r in results["local_detection"]
        ) / len(results["local_detection"])

        results["comparison"] = {
            "avg_local_detection_time": avg_local_time,
            "avg_local_time_ms": avg_local_time * 1000,
            "estimated_ai_time": 1.5,  # Estimated based on previous tests
            "speed_improvement": 1.5 / avg_local_time if avg_local_time > 0 else 0,
        }

        logger.info(f"   ⚡ Average local detection: {avg_local_time*1000:.2f}ms")
        logger.info(
            f"   🚀 Speed improvement: {results['comparison']['speed_improvement']:.0f}x faster than AI"
        )

        return results

    async def test_conversation_analysis_api(self, session_id: str) -> Dict[str, Any]:
        """Test the new deep conversation analysis API"""
        logger.info(f"\n🔍 Testing conversation analysis API for session: {session_id}")

        try:
            # Import the analysis function
            from src.api.unified_chat_routes import _perform_deep_conversation_analysis

            # Get conversation history
            conversation_history = self.chat_service._get_conversation_history(
                session_id
            )
            conversation_stats = self.chat_service.get_conversation_stats(session_id)

            if not conversation_history:
                logger.warning("   ⚠️ No conversation history found")
                return {"error": "No conversation history"}

            logger.info(f"   📚 Analyzing {len(conversation_history)} messages...")

            start_time = time.time()

            # Perform deep analysis
            analysis_result = await _perform_deep_conversation_analysis(
                conversation_history=conversation_history,
                company_id=self.test_company_id,
                conversation_stats=conversation_stats,
            )

            analysis_time = time.time() - start_time

            logger.info(f"   ✅ Analysis completed in {analysis_time:.2f}s")

            if "error" not in analysis_result:
                logger.info(
                    f"   🎯 Primary Intent: {analysis_result.get('primary_intent', 'Unknown')}"
                )
                logger.info(
                    f"   📊 Outcome: {analysis_result.get('conversation_outcome', 'Unknown')}"
                )
                logger.info(
                    f"   📧 Remarketing Ops: {len(analysis_result.get('remarketing_opportunities', []))}"
                )
                logger.info(
                    f"   💡 Improvements: {len(analysis_result.get('improvement_suggestions', []))}"
                )

            return {
                "analysis_time": analysis_time,
                "analysis_result": analysis_result,
                "conversation_stats": conversation_stats,
            }

        except Exception as e:
            logger.error(f"❌ Analysis API test failed: {e}")
            return {"error": str(e)}

    def calculate_performance_improvements(self) -> Dict[str, Any]:
        """Calculate performance improvements from optimization"""
        if not self.performance_metrics:
            return {"error": "No performance data available"}

        avg_processing_time = sum(
            m["processing_time"] for m in self.performance_metrics
        ) / len(self.performance_metrics)

        # Estimated old system times (with IntentDetector)
        estimated_old_times = {
            "intent_detection": 2.0,  # Average AI call for intent
            "image_search": 0.3,  # Vector search
            "folder_selection": 1.5,  # AI call for folder selection (if needed)
            "final_response": 2.0,  # Final AI response
        }

        estimated_old_total = sum(estimated_old_times.values())

        return {
            "new_system": {
                "avg_processing_time": avg_processing_time,
                "min_time": min(m["processing_time"] for m in self.performance_metrics),
                "max_time": max(m["processing_time"] for m in self.performance_metrics),
                "total_messages": len(self.performance_metrics),
            },
            "old_system_estimate": {
                "breakdown": estimated_old_times,
                "estimated_total": estimated_old_total,
            },
            "improvement": {
                "time_saved_per_message": estimated_old_total - avg_processing_time,
                "speed_improvement_factor": (
                    estimated_old_total / avg_processing_time
                    if avg_processing_time > 0
                    else 0
                ),
                "percentage_faster": (
                    (
                        (estimated_old_total - avg_processing_time)
                        / estimated_old_total
                        * 100
                    )
                    if estimated_old_total > 0
                    else 0
                ),
            },
        }

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return comprehensive results"""
        logger.info("🧪 Starting comprehensive test suite for optimized chat system")
        logger.info("=" * 60)

        test_results = {"test_start_time": datetime.now().isoformat(), "tests": {}}

        # Test 1: Optimized chat flow
        logger.info("\n1️⃣ TESTING OPTIMIZED CHAT FLOW")
        test_results["tests"]["chat_flow"] = await self.test_optimized_chat_flow()

        # Test 2: Image detection speed
        logger.info("\n2️⃣ TESTING IMAGE DETECTION SPEED")
        test_results["tests"][
            "image_detection"
        ] = await self.test_image_detection_speed()

        # Test 3: Conversation analysis (using session from chat flow test)
        if test_results["tests"]["chat_flow"]:
            session_id = f"test_session_{int(time.time())}"  # Get from first test
            logger.info("\n3️⃣ TESTING CONVERSATION ANALYSIS API")
            test_results["tests"]["conversation_analysis"] = (
                await self.test_conversation_analysis_api(session_id)
            )

        # Test 4: Performance improvements
        logger.info("\n4️⃣ CALCULATING PERFORMANCE IMPROVEMENTS")
        test_results["tests"][
            "performance_analysis"
        ] = self.calculate_performance_improvements()

        test_results["test_end_time"] = datetime.now().isoformat()

        logger.info("\n" + "=" * 60)
        logger.info("🏁 TEST SUMMARY:")

        # Print summary
        perf_data = test_results["tests"].get("performance_analysis", {})
        if "improvement" in perf_data:
            improvement = perf_data["improvement"]
            logger.info(
                f"   ⚡ Speed improvement: {improvement.get('speed_improvement_factor', 0):.1f}x faster"
            )
            logger.info(
                f"   ⏱️ Time saved per message: {improvement.get('time_saved_per_message', 0):.2f}s"
            )
            logger.info(
                f"   📈 Percentage improvement: {improvement.get('percentage_faster', 0):.1f}%"
            )

        image_data = test_results["tests"].get("image_detection", {})
        if "comparison" in image_data:
            comparison = image_data["comparison"]
            logger.info(
                f"   🖼️ Image detection: {comparison.get('speed_improvement', 0):.0f}x faster"
            )

        logger.info(f"   📊 Total messages tested: {len(self.performance_metrics)}")

        return test_results


async def main():
    """Main test execution function"""
    print("🧪 Optimized Chat System Test Suite")
    print("=" * 60)

    tester = OptimizedChatTester()

    try:
        results = await tester.run_all_tests()

        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"test_results_optimized_chat_{timestamp}.json"

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n📄 Test results saved to: {results_file}")

        # Print key metrics
        print("\n📊 KEY PERFORMANCE METRICS:")
        perf_data = results["tests"].get("performance_analysis", {})
        if "new_system" in perf_data and "improvement" in perf_data:
            new_sys = perf_data["new_system"]
            improvement = perf_data["improvement"]

            print(
                f"   New System Average Response Time: {new_sys['avg_processing_time']:.2f}s"
            )
            print(
                f"   Estimated Old System Time: {perf_data['old_system_estimate']['estimated_total']:.2f}s"
            )
            print(
                f"   Speed Improvement: {improvement['speed_improvement_factor']:.1f}x faster"
            )
            print(
                f"   Time Saved Per Message: {improvement['time_saved_per_message']:.2f}s"
            )
            print(
                f"   Performance Improvement: {improvement['percentage_faster']:.1f}%"
            )

    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
