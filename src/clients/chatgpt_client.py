import openai
from typing import List, Dict, AsyncGenerator
import json
import asyncio
from src.utils.logger import setup_logger

logger = setup_logger()


class ChatGPTClient:
    def __init__(self, api_key: str, model: str = "gpt-5.4"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.reasoning_model = "o1-preview"  # Text-only reasoning
        self.vision_reasoning_model = "gpt-5.4"  # Multimodal reasoning
        self.logger = logger

        # Test API key
        try:
            test_response = self.client.models.list()
            self.logger.debug(
                f"ChatGPT client initialized successfully. Available models: {len(test_response.data)}"
            )
        except Exception as e:
            self.logger.error(f"ChatGPT client initialization failed: {e}")

    def _should_use_vision_model(self, messages: List[Dict]) -> bool:
        """Kiểm tra có cần dùng vision model không"""
        for message in messages:
            if isinstance(message.get("content"), list):
                for content in message["content"]:
                    if content.get("type") == "image_url":
                        return True
        return False

    def _prepare_messages_for_o1(self, messages: List[Dict]) -> List[Dict]:
        """Chuẩn bị messages cho o1 model (text-only, không hỗ trợ system role)"""
        prepared_messages = []
        system_content = ""

        for message in messages:
            if message["role"] == "system":
                # Gộp system prompt vào user message đầu tiên
                system_content = message["content"]
            elif message["role"] == "user":
                if isinstance(message["content"], list):
                    # Extract text only từ multimodal content
                    text_content = ""
                    for item in message["content"]:
                        if item["type"] == "text":
                            text_content = item["text"]
                            break

                    if system_content:
                        combined_content = f"{system_content}\n\n{text_content}"
                        system_content = ""
                    else:
                        combined_content = text_content

                    prepared_messages.append(
                        {"role": "user", "content": combined_content}
                    )
                else:
                    # Text only content
                    if system_content:
                        combined_content = f"{system_content}\n\n{message['content']}"
                        system_content = ""
                    else:
                        combined_content = message["content"]

                    prepared_messages.append(
                        {"role": "user", "content": combined_content}
                    )
            else:
                prepared_messages.append(message)

        return prepared_messages

    async def chat_completion_stream_with_reasoning(
        self, messages: List[Dict], use_reasoning: bool = False
    ) -> AsyncGenerator[str, None]:
        """Streaming với reasoning support - Sử dụng gpt-4-vision-preview cho multimodal reasoning"""
        try:
            has_images = self._should_use_vision_model(messages)

            # Smart model selection
            if use_reasoning:
                if has_images:
                    # Use gpt-4-vision-preview for multimodal reasoning
                    model_to_use = self.vision_reasoning_model
                    prepared_messages = self._enhance_messages_for_vision_reasoning(
                        messages
                    )
                    is_streaming = True
                    self.logger.info(f"Using {model_to_use} for multimodal reasoning")
                else:
                    # Use o1-preview for text-only reasoning
                    model_to_use = self.reasoning_model
                    prepared_messages = self._prepare_messages_for_o1(messages)
                    is_streaming = False  # o1 doesn't support streaming
                    self.logger.info(f"Using {model_to_use} for text-only reasoning")
            else:
                # Standard mode
                model_to_use = self.model
                prepared_messages = messages
                is_streaming = True

            self.logger.info(
                f"ChatGPT request - Model: {model_to_use}, Reasoning: {use_reasoning}, Has Images: {has_images}, Messages: {len(prepared_messages)}"
            )

            if not is_streaming:
                # o1 models không hỗ trợ streaming
                result = await self._chat_completion_reasoning(prepared_messages)
                # Simulate streaming
                chunk_size = 50
                for i in range(0, len(result), chunk_size):
                    chunk = result[i : i + chunk_size]
                    yield chunk
                    await asyncio.sleep(0.05)
            else:
                # Regular streaming cho gpt-4o và gpt-4-vision-preview
                stream = self.client.chat.completions.create(
                    model=model_to_use,
                    messages=prepared_messages,
                    max_completion_tokens=32000,
                    temperature=0.2,
                    stream=True,
                )

                chunk_count = 0
                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        chunk_count += 1
                        yield chunk.choices[0].delta.content

                self.logger.info(
                    f"ChatGPT streaming completed. Total chunks: {chunk_count}"
                )

        except Exception as e:
            self.logger.error(f"ChatGPT streaming error: {e}")
            import traceback

            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            yield "Xin lỗi, tôi đang gặp sự cố khi xử lý câu hỏi của bạn."

    def _enhance_messages_for_vision_reasoning(
        self, messages: List[Dict]
    ) -> List[Dict]:
        """Enhance messages cho gpt-4-vision-preview với reasoning prompt"""
        enhanced_messages = []

        for msg in messages:
            if msg["role"] == "system":
                # Enhanced system prompt cho vision reasoning
                enhanced_content = (
                    msg["content"]
                    + """

                🧠 PHƯƠNG PHÁP REASONING CHO ĐỊNH GIÁ BẤT ĐỘNG SẢN VỚI HÌNH ẢNH:

                Hãy thực hiện reasoning từng bước chi tiết:

                🔍 BƯỚC 1: QUAN SÁT HÌNH ẢNH CHI TIẾT
                - Đọc và phân tích tất cả văn bản trong hình ảnh
                - Trích xuất thông tin: địa chỉ, diện tích, loại hình, pháp lý
                - Đánh giá chất lượng và tính đầy đủ của tài liệu
                - Ghi nhận các chi tiết đặc biệt ảnh hưởng đến giá trị

                📊 BƯỚC 2: PHÂN TÍCH THỊ TRƯỜNG 2025
                - So sánh với giá khu vực tương tự
                - Đánh giá xu hướng thị trường bất động sản
                - Phân tích tiềm năng phát triển khu vực
                - Xem xét các yếu tố vĩ mô ảnh hưởng

                💰 BƯỚC 3: TÍNH TOÁN GIÁ TRỊ CHÍNH XÁC
                - Ước tính giá trị thị trường hiện tại
                - Tính giá trị thẩm định ngân hàng (LTV 70-80%)
                - Xác định số tiền vay thế chấp tối đa
                - So sánh với nhiều phương pháp định giá

                ⚠️ BƯỚC 4: ĐÁNH GIÁ RỦI RO TOÀN DIỆN
                - Rủi ro pháp lý và tính thanh khoản
                - Rủi ro biến động giá và lãi suất
                - Rủi ro tín dụng và khả năng thu hồi nợ
                - Đánh giá tác động kinh tế vĩ mô

                🎯 BƯỚC 5: KHUYẾN NGHỊ CHIẾN LƯỢC
                - Phương thức tài trợ tối ưu
                - Kế hoạch thẩm định thực tế
                - Chiến lược quản lý rủi ro
                - Timeline thực hiện cụ thể

                📋 YÊU CẦU ĐẦU RA:
                - Trình bày reasoning logic từng bước
                - Cung cấp số liệu định lượng cụ thể
                - Đưa ra khuyến nghị thực tế và khả thi
                - Highlight các điểm quan trọng cần lưu ý
                """
                )
                enhanced_messages.append(
                    {"role": "system", "content": enhanced_content}
                )
            else:
                enhanced_messages.append(msg)

        return enhanced_messages

    async def _chat_completion_reasoning(self, messages: List[Dict]) -> str:
        """Non-streaming completion cho o1 reasoning model"""
        try:
            # o1 models có parameters khác
            response = self.client.chat.completions.create(
                model=self.reasoning_model,
                messages=messages,
                # Không có temperature, max_tokens cho o1
            )

            result = response.choices[0].message.content
            self.logger.info(f"ChatGPT reasoning response length: {len(result)}")
            return result

        except Exception as e:
            self.logger.error(f"ChatGPT reasoning error: {e}")
            raise e

    # BACKWARD COMPATIBILITY METHODS
    async def chat_completion(self, messages: List[Dict]) -> str:
        """Original chat completion method"""
        try:
            model_to_use = self.model
            if self._should_use_vision_model(messages):
                model_to_use = self.model

            self.logger.info(
                f"ChatGPT request - Model: {model_to_use}, Messages count: {len(messages)}"
            )

            response = self.client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                max_completion_tokens=32000,
                temperature=0.2,
            )

            result = response.choices[0].message.content
            self.logger.info(f"ChatGPT response length: {len(result)}")
            return result

        except Exception as e:
            self.logger.error(f"ChatGPT API error: {e}")
            import traceback

            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            raise e

    async def chat_completion_stream(
        self, messages: List[Dict]
    ) -> AsyncGenerator[str, None]:
        """Original streaming method"""
        async for chunk in self.chat_completion_stream_with_reasoning(
            messages, use_reasoning=False
        ):
            yield chunk
