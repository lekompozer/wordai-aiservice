#!/usr/bin/env python3
"""
Test script for Folder-Prioritized Image Search System
Kiểm tra hệ thống tìm kiếm hình ảnh ưu tiên folder

This test validates the new logic:
1. Search folders first (limit 2)
2. AI Provider selects best folder
3. Search unlimited images in selected folder
4. Fallback to direct image search if no folders found
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

from src.services.admin_service import get_admin_service
from src.services.unified_chat_service import UnifiedChatService
from src.models.unified_models import UnifiedChatRequest, UserInfo, Source

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f'test_folder_search_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        ),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


class FolderPrioritizedImageSearchTester:
    """Test class for folder-prioritized image search"""

    def __init__(self):
        self.admin_service = get_admin_service()
        self.chat_service = UnifiedChatService()
        self.test_company_id = "test_company_001"

    async def test_folder_search_logic(self) -> Dict[str, Any]:
        """Test the new folder search logic directly"""
        logger.info("🧪 Testing folder search logic...")

        test_queries = [
            "sản phẩm áo thun",
            "quần jean nam",
            "giày sneaker",
            "túi xách nữ",
            "đồng hồ thông minh",
        ]

        results = {}

        for query in test_queries:
            logger.info(f"\n📝 Testing query: '{query}'")

            try:
                # Test with folder prioritization
                search_result = await self.admin_service.search_images_by_description(
                    company_id=self.test_company_id,
                    query=query,
                    limit=5,
                    score_threshold=0.6,
                    prefer_folders=True,
                )

                result_type = search_result.get("type", "unknown")
                data = search_result.get("data", [])

                results[query] = {
                    "result_type": result_type,
                    "count": len(data),
                    "data": data,
                }

                if result_type == "folders":
                    logger.info(f"   🗂️ Found {len(data)} folders:")
                    for folder in data:
                        logger.info(
                            f"      📁 {folder['folder_name']} (score: {folder['score']:.3f})"
                        )
                        logger.info(f"         Description: {folder['description']}")

                elif result_type == "images":
                    logger.info(f"   🖼️ Found {len(data)} images:")
                    for img in data[:3]:  # Show first 3
                        logger.info(
                            f"      📸 {img['description'][:50]}... (score: {img['score']:.3f})"
                        )
                        logger.info(f"         Folder: {img.get('folder_name', 'N/A')}")

                # Simulate delay between searches
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"❌ Error testing query '{query}': {e}")
                results[query] = {"error": str(e)}

        return results

    async def test_full_chat_integration(self) -> Dict[str, Any]:
        """Test the complete chat integration with image search"""
        logger.info("\n🧪 Testing full chat integration...")

        test_messages = [
            "Tôi muốn xem một số sản phẩm áo thun đẹp",
            "Có thể cho tôi xem hình ảnh quần jean không?",
            "Bạn có thể gửi cho tôi một số mẫu giày sneaker?",
            "Hiển thị cho tôi hình ảnh túi xách nữ",
        ]

        results = {}

        for i, message in enumerate(test_messages):
            logger.info(f"\n📱 Testing message {i+1}: '{message}'")

            try:
                # Create chat request
                chat_request = UnifiedChatRequest(
                    message=message,
                    session_id=f"test_session_{i+1}",
                    company_id=self.test_company_id,
                    user_info=UserInfo(user_id=f"test_user_{i+1}", source=Source.WEB),
                    conversation_id=f"test_conv_{i+1}",
                    industry="fashion",
                    context={},
                )

                # Process message
                response = await self.chat_service.process_message(chat_request)

                # Extract results
                has_attachments = bool(response.attachments)
                attachment_count = (
                    len(response.attachments) if response.attachments else 0
                )

                results[f"message_{i+1}"] = {
                    "message": message,
                    "has_attachments": has_attachments,
                    "attachment_count": attachment_count,
                    "response_content": (
                        response.content[:200] + "..."
                        if len(response.content) > 200
                        else response.content
                    ),
                    "attachments": response.attachments,
                }

                logger.info(f"   ✅ Response generated")
                logger.info(f"   📎 Has attachments: {has_attachments}")
                logger.info(f"   📸 Attachment count: {attachment_count}")

                if response.attachments:
                    for j, attachment in enumerate(
                        response.attachments[:3]
                    ):  # Show first 3
                        method = attachment.get("metadata", {}).get(
                            "selection_method", "unknown"
                        )
                        folder = attachment.get("metadata", {}).get(
                            "folder_name", "N/A"
                        )
                        score = attachment.get("metadata", {}).get("score", 0)
                        logger.info(
                            f"      📸 Image {j+1}: {attachment.get('description', 'No description')[:40]}..."
                        )
                        logger.info(
                            f"         Method: {method}, Folder: {folder}, Score: {score:.3f}"
                        )

                # Simulate delay between tests
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"❌ Error testing message '{message}': {e}")
                results[f"message_{i+1}"] = {"error": str(e)}

        return results

    async def test_ai_folder_selection(self) -> Dict[str, Any]:
        """Test AI Provider folder selection logic"""
        logger.info("\n🧪 Testing AI folder selection...")

        # Mock folder data for testing
        mock_folders = [
            {
                "folder_name": "ao_thun_nam",
                "description": "Bộ sưu tập áo thun nam cao cấp, nhiều màu sắc và kích cỡ",
                "score": 0.85,
            },
            {
                "folder_name": "ao_thun_nu",
                "description": "Áo thun nữ thời trang, thiết kế trẻ trung và năng động",
                "score": 0.82,
            },
        ]

        test_query = "áo thun nam màu đen"

        # Test folder selection prompt
        folder_selection_prompt = f"""
Dựa trên truy vấn của người dùng: "{test_query}"

Các thư mục hình ảnh có liên quan:
{chr(10).join([f"- {folder['folder_name']}: {folder['description']} (score: {folder['score']:.3f})" for folder in mock_folders])}

Hãy chọn 1 thư mục phù hợp nhất dựa trên:
1. Tên thư mục
2. Mô tả thư mục  
3. Độ liên quan với truy vấn

Chỉ trả lời tên thư mục được chọn, không giải thích thêm.
"""

        try:
            # Test AI selection (if AI manager is available)
            if hasattr(self.chat_service, "ai_manager"):
                selected_folder = await self.chat_service.ai_manager.generate_response(
                    prompt=folder_selection_prompt,
                    model_type="chatgpt",
                    temperature=0.3,
                    max_tokens=50,
                )

                logger.info(f"   🤖 AI selected folder: '{selected_folder.strip()}'")

                return {
                    "query": test_query,
                    "available_folders": mock_folders,
                    "ai_selection": selected_folder.strip(),
                    "prompt_used": folder_selection_prompt,
                }
            else:
                logger.warning(
                    "   ⚠️ AI Manager not available, skipping AI selection test"
                )
                return {"error": "AI Manager not available"}

        except Exception as e:
            logger.error(f"❌ Error testing AI folder selection: {e}")
            return {"error": str(e)}

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return comprehensive results"""
        logger.info("🚀 Starting Folder-Prioritized Image Search Tests")
        logger.info("=" * 60)

        test_results = {
            "test_start_time": datetime.now().isoformat(),
            "test_company_id": self.test_company_id,
            "tests": {},
        }

        # Test 1: Folder search logic
        logger.info("\n1️⃣ TESTING FOLDER SEARCH LOGIC")
        test_results["tests"]["folder_search"] = await self.test_folder_search_logic()

        # Test 2: Full chat integration
        logger.info("\n2️⃣ TESTING FULL CHAT INTEGRATION")
        test_results["tests"][
            "chat_integration"
        ] = await self.test_full_chat_integration()

        # Test 3: AI folder selection
        logger.info("\n3️⃣ TESTING AI FOLDER SELECTION")
        test_results["tests"]["ai_selection"] = await self.test_ai_folder_selection()

        test_results["test_end_time"] = datetime.now().isoformat()

        logger.info("\n" + "=" * 60)
        logger.info("🏁 Test Summary:")
        logger.info(
            f"   ✅ Folder search tests: {len([k for k, v in test_results['tests']['folder_search'].items() if 'error' not in v])}"
        )
        logger.info(
            f"   ✅ Chat integration tests: {len([k for k, v in test_results['tests']['chat_integration'].items() if 'error' not in v])}"
        )
        logger.info(
            f"   ✅ AI selection test: {'✅ Passed' if 'error' not in test_results['tests']['ai_selection'] else '❌ Failed'}"
        )

        return test_results


async def main():
    """Main test execution function"""
    print("🧪 Folder-Prioritized Image Search System Test")
    print("=" * 60)

    tester = FolderPrioritizedImageSearchTester()

    try:
        results = await tester.run_all_tests()

        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"test_results_folder_search_{timestamp}.json"

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n📄 Test results saved to: {results_file}")

        # Print summary
        print("\n📊 QUICK SUMMARY:")
        for test_name, test_data in results["tests"].items():
            if isinstance(test_data, dict):
                if test_name == "folder_search":
                    success_count = len(
                        [k for k, v in test_data.items() if "error" not in v]
                    )
                    print(f"   {test_name}: {success_count} successful queries")
                elif test_name == "chat_integration":
                    success_count = len(
                        [k for k, v in test_data.items() if "error" not in v]
                    )
                    print(f"   {test_name}: {success_count} successful chats")
                elif test_name == "ai_selection":
                    status = "✅ Success" if "error" not in test_data else "❌ Failed"
                    print(f"   {test_name}: {status}")

    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
