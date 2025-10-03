from typing import List, Dict, AsyncGenerator, Optional
from src.clients.chatgpt_client import ChatGPTClient
from src.clients.gemini_client import GeminiClient
from src.clients.cerebras_client import CerebrasClient
from src.utils.logger import setup_logger
import requests
import json
import asyncio

logger = setup_logger()


class AIProviderManager:
    def __init__(
        self,
        deepseek_api_key: str,
        chatgpt_api_key: str,
        gemini_api_key: str = None,
        cerebras_api_key: str = None,
    ):
        self.deepseek_api_key = deepseek_api_key
        self.chatgpt_api_key = chatgpt_api_key  # Store for later use
        self.gemini_api_key = gemini_api_key  # Store for later use
        self.cerebras_api_key = cerebras_api_key  # Store for later use
        self.deepseek_api_url = "https://api.deepseek.com/v1/chat/completions"

        # Initialize ChatGPT client với reasoning support
        self.chatgpt_client = (
            ChatGPTClient(chatgpt_api_key) if chatgpt_api_key else None
        )

        # Initialize Gemini client
        self.gemini_client = GeminiClient(gemini_api_key) if gemini_api_key else None

        # Initialize Cerebras client
        self.cerebras_client = (
            CerebrasClient(cerebras_api_key) if cerebras_api_key else None
        )

        self.logger = logger

    async def chat_completion_stream_with_reasoning(
        self,
        messages: List[Dict],
        provider: str = "deepseek",
        use_reasoning: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Unified streaming với reasoning support
        """
        try:
            if provider == "chatgpt" and self.chatgpt_client:
                # ChatGPT với reasoning
                async for (
                    chunk
                ) in self.chatgpt_client.chat_completion_stream_with_reasoning(
                    messages, use_reasoning
                ):
                    yield chunk
            elif provider == "gemini" and self.gemini_client:
                # Gemini với reasoning
                async for (
                    chunk
                ) in self.gemini_client.chat_completion_stream_with_reasoning(
                    messages, use_reasoning
                ):
                    yield chunk
            elif provider == "cerebras" and self.cerebras_client:
                # Cerebras với reasoning
                async for (
                    chunk
                ) in self.cerebras_client.chat_completion_stream_with_reasoning(
                    messages, use_reasoning
                ):
                    yield chunk
            elif provider == "deepseek":
                # DeepSeek với reasoning prompt enhancement
                if use_reasoning:
                    messages = self._enhance_messages_for_reasoning(messages)

                # Truncate messages cho DeepSeek để tránh vượt quá token limit
                messages = self._truncate_messages_for_deepseek(messages)

                async for chunk in self._deepseek_completion_stream_async(messages):
                    yield chunk
            else:
                yield f"Provider {provider} không được hỗ trợ."

        except Exception as e:
            self.logger.error(f"Error in chat_completion_stream_with_reasoning: {e}")
            yield f"Lỗi {provider}: {str(e)}"

    def _truncate_messages_for_deepseek(self, messages: List[Dict]) -> List[Dict]:
        """Truncate messages để phù hợp với DeepSeek token limit"""
        # Ước tính: 1 token ≈ 4 characters (tiếng Việt)
        MAX_TOKENS = 50000  # Để lại buffer cho completion
        MAX_CHARS = MAX_TOKENS * 4

        truncated_messages = []
        total_chars = 0

        for msg in messages:
            content = msg.get("content", "")

            if msg["role"] == "system":
                # Rút gọn system prompt nhưng giữ thông tin quan trọng
                if len(content) > 2000:
                    content = (
                        content[:2000]
                        + "\n\nHãy phân tích bất động sản và đưa ra định giá cùng khả năng thế chấp."
                    )

            elif msg["role"] == "user":
                # Rút gọn user content nếu quá dài
                if len(content) > MAX_CHARS - total_chars - 1000:  # Để lại buffer
                    available_chars = MAX_CHARS - total_chars - 1000
                    if available_chars > 1000:
                        content = (
                            content[:available_chars]
                            + "\n\n... (nội dung đã được rút gọn)"
                        )
                    else:
                        # Nếu không đủ chỗ, chỉ giữ phần đầu quan trọng
                        content = content[:1000] + "\n\nHãy định giá bất động sản này."

            total_chars += len(content)
            truncated_messages.append({"role": msg["role"], "content": content})

            # Break nếu đã gần đến giới hạn
            if total_chars > MAX_CHARS - 1000:
                break

        self.logger.info(f"DeepSeek messages truncated - Total chars: {total_chars}")
        return truncated_messages

    async def loan_assessment_completion_non_stream(
        self, messages: List[Dict], provider: str = "deepseek"
    ) -> str:
        """
        ✅ DEDICATED non-streaming method for loan assessment - Returns complete response
        """
        try:
            self.logger.info(
                f"🏦 Loan Assessment: Starting {provider} call with {len(messages)} messages"
            )

            if provider == "chatgpt" and self.chatgpt_client:
                # ChatGPT non-streaming với loan assessment enhancement
                enhanced_messages = self._enhance_messages_for_loan_assessment(messages)
                return await self.chatgpt_client.chat_completion(enhanced_messages)
            elif provider == "cerebras" and self.cerebras_client:
                # Cerebras non-streaming với loan assessment enhancement
                enhanced_messages = self._enhance_messages_for_loan_assessment(messages)
                return await self.cerebras_client.chat_completion(
                    enhanced_messages,
                    temperature=0.1,  # Low temperature for consistent assessment
                    max_tokens=3000,
                )
            elif provider == "deepseek":
                # ✅ ENHANCE MESSAGES FOR LOAN ASSESSMENT
                enhanced_messages = self._enhance_messages_for_loan_assessment(messages)

                # ✅ TRUNCATE FOR DEEPSEEK
                truncated_messages = self._truncate_messages_for_deepseek(
                    enhanced_messages
                )

                self.logger.info(
                    f"🏦 Loan Assessment: Messages prepared - Enhanced: {len(enhanced_messages)}, Truncated: {len(truncated_messages)}"
                )

                # ✅ CALL DEEPSEEK NON-STREAMING
                validated_messages = self._validate_deepseek_messages(
                    truncated_messages
                )

                headers = {
                    "Authorization": f"Bearer {self.deepseek_api_key}",
                    "Content-Type": "application/json",
                }

                payload = {
                    "model": "deepseek-chat",
                    "messages": validated_messages,
                    "temperature": 0.1,  # Low temperature for consistent loan assessment
                    "max_tokens": 3000,  # Enough for detailed assessment JSON
                    "stream": False,  # Non-streaming for complete response
                }

                self.logger.info(f"🏦 Loan Assessment: Sending request to DeepSeek")

                # ✅ SYNCHRONOUS CALL
                import requests

                response = requests.post(
                    self.deepseek_api_url, headers=headers, json=payload, timeout=120
                )

                if response.status_code != 200:
                    error_text = response.text
                    self.logger.error(
                        f"🏦 Loan Assessment: DeepSeek API error {response.status_code}: {error_text}"
                    )
                    raise Exception(
                        f"DeepSeek API error {response.status_code}: {error_text}"
                    )

                response.raise_for_status()
                result = response.json()

                # ✅ EXTRACT CONTENT
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    self.logger.info(
                        f"🏦 Loan Assessment: DeepSeek response received - {len(content)} characters"
                    )
                    return content
                else:
                    raise Exception("No content in DeepSeek response")
            else:
                raise Exception(
                    f"Provider {provider} không được hỗ trợ cho loan assessment"
                )

        except Exception as e:
            self.logger.error(
                f"🏦 Loan Assessment: Error in loan_assessment_completion_non_stream - {e}"
            )
            raise e

    def _enhance_messages_for_loan_assessment(self, messages: List[Dict]) -> List[Dict]:
        """
        ✅ Enhance messages cho DeepSeek loan assessment mode - VRB Bank Standards
        """
        enhanced_messages = []

        for msg in messages:
            if msg["role"] == "system":
                # ✅ COMPACT LOAN ASSESSMENT REASONING PROMPT
                enhanced_content = (
                    msg["content"]
                    + """

    🏦 **PHƯƠNG PHÁP THẨM ĐỊNH TÍN DỤNG VRB:**

    **BƯỚC 1 - PHÂN TÍCH KHẢ NĂNG TÀI CHÍNH:**
    - DTI (Debt-to-Income): Tỷ lệ nợ/thu nhập ≤ 50%
    - Dòng tiền hàng tháng sau trả nợ ≥ 15 triệu VNĐ
    - Thu nhập ổn định ≥ 12 tháng

    **BƯỚC 2 - ĐÁNH GIÁ TÀI SẢN ĐẢM BẢO:**
    - LTV (Loan-to-Value): Tỷ lệ cho vay/giá trị tài sản ≤ 80%
    - Định giá tài sản theo thị trường hiện tại
    - Tính thanh khoản và rủi ro pháp lý

    **BƯỚC 3 - RỦI RO TÍN DỤNG:**
    - CIC Score: Nhóm 1-2 (tốt), Nhóm 3+ (cảnh báo)
    - Lịch sử trả nợ và cam kết tài chính
    - Độ ổn định công việc và thu nhập

    **BƯỚC 4 - QUYẾT ĐỊNH PHÂN LOẠI:**
    - APPROVED: DTI ≤ 40%, LTV ≤ 70%, CIC Nhóm 1-2
    - NEEDS_REVIEW: DTI 40-50%, LTV 70-80%, cần bổ sung
    - REJECTED: DTI > 50%, LTV > 80%, CIC Nhóm 3+

    **BƯỚC 5 - ĐIỀU KIỆN & KHUYẾN NGHỊ:**
    - Lãi suất dựa trên profile rủi ro
    - Điều kiện bổ sung (nếu cần)
    - Timeline và yêu cầu pháp lý

    📊 **YÊU CẦU JSON RESPONSE:**
    Phải có đầy đủ: status, confidence, creditScore, reasoning (≥200 từ),
    riskFactors, recommendations, approvedAmount, interestRate, conditions.

    🎯 **TRÌNH BÀY:** Logic từng bước, căn cứ số liệu, quyết định rõ ràng.
    """
                )
                enhanced_messages.append(
                    {"role": "system", "content": enhanced_content}
                )
            else:
                enhanced_messages.append(msg)

        return enhanced_messages

    def _enhance_messages_for_reasoning(self, messages: List[Dict]) -> List[Dict]:
        """Enhance messages cho DeepSeek reasoning mode - COMPACT VERSION"""
        enhanced_messages = []

        for msg in messages:
            if msg["role"] == "system":
                # Compact reasoning prompt
                enhanced_content = (
                    msg["content"]
                    + """

                PHƯƠNG PHÁP REASONING:
                1. Phân tích thông tin: diện tích, vị trí, pháp lý
                2. Định giá thị trường 2025
                3. Tính khả năng thế chấp (LTV 70-80%)
                4. Đánh giá rủi ro
                5. Khuyến nghị cụ thể

                Trình bày từng bước với số liệu cụ thể.
                """
                )
                enhanced_messages.append(
                    {"role": "system", "content": enhanced_content}
                )
            else:
                enhanced_messages.append(msg)

        return enhanced_messages

    def _validate_deepseek_messages(self, messages: List[Dict]) -> List[Dict]:
        """Validate và clean messages cho DeepSeek API"""
        validated_messages = []

        for msg in messages:
            # Đảm bảo role hợp lệ
            if msg["role"] not in ["system", "user", "assistant"]:
                continue

            # Đảm bảo content không None và có dạng string cho DeepSeek
            content = msg.get("content", "")
            if isinstance(content, list):
                # DeepSeek không hỗ trợ multimodal, extract text only
                text_content = ""
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_content += item.get("text", "")
                content = text_content

            if not content or not isinstance(content, str):
                content = "Nội dung trống"

            validated_messages.append({"role": msg["role"], "content": content})

        return validated_messages

    async def _deepseek_completion_stream_async(
        self, messages: List[Dict]
    ) -> AsyncGenerator[str, None]:
        """DeepSeek streaming async version"""

        def sync_generator():
            yield from self._deepseek_completion_stream_sync(messages)

        loop = asyncio.get_event_loop()
        generator = await loop.run_in_executor(None, lambda: list(sync_generator()))
        for chunk in generator:
            yield chunk

    def _deepseek_completion_stream_sync(self, messages: List[Dict]):
        """DeepSeek streaming completion - SYNC generator"""
        # Validate messages trước khi gửi
        validated_messages = self._validate_deepseek_messages(messages)

        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": validated_messages,
            "temperature": 0.2,
            "max_tokens": 2000,  # GIẢM TỪ 4000 XUỐNG 2000
            "stream": True,
        }

        try:
            self.logger.info(f"DeepSeek request - Messages: {len(validated_messages)}")

            with requests.post(
                self.deepseek_api_url,
                headers=headers,
                json=payload,
                timeout=120,
                stream=True,
            ) as response:

                if response.status_code != 200:
                    error_text = response.text
                    self.logger.error(
                        f"DeepSeek API error {response.status_code}: {error_text}"
                    )
                    yield f"DeepSeek API Error: {error_text}"
                    return

                response.raise_for_status()

                for line in response.iter_lines():
                    if line:
                        line = line.decode("utf-8")
                        if line.startswith("data: "):
                            line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                chunk_data = json.loads(line)
                                if (
                                    "choices" in chunk_data
                                    and len(chunk_data["choices"]) > 0
                                ):
                                    delta = chunk_data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                continue

        except requests.exceptions.RequestException as e:
            self.logger.error(f"DeepSeek streaming error: {e}")
            yield "Xin lỗi, tôi đang gặp sự cố khi xử lý câu hỏi của bạn."
        except Exception as e:
            self.logger.error(f"DeepSeek unexpected error: {e}")
            yield "Xin lỗi, tôi đang gặp sự cố khi xử lý câu hỏi của bạn."

    # THÊM CÁC METHODS CŨ ĐỂ BACKWARD COMPATIBILITY
    async def chat_completion(
        self, messages: List[Dict], provider: str = "deepseek"
    ) -> str:
        """Non-streaming chat completion - USES PROVEN STREAMING METHOD"""
        try:
            if provider == "chatgpt" and self.chatgpt_client:
                return await self.chatgpt_client.chat_completion(messages)
            elif provider == "gemini" and self.gemini_client:
                return await self.gemini_client.chat_completion(messages)
            else:
                # Use the proven streaming method that works well in other routes
                # Collect all chunks into a single response
                chunks = []
                async for chunk in self.chat_completion_stream_with_reasoning(
                    messages, provider, use_reasoning=False
                ):
                    chunks.append(chunk)

                raw_response = "".join(chunks)
                logger.info(
                    f"✅ {provider} chat_completion: Response length: {len(raw_response)} chars"
                )
                return raw_response
        except Exception as e:
            logger.error(f"❌ Error in chat_completion: {e}")
            raise e

    async def chat_completion_stream(
        self, messages: List[Dict], provider: str = "deepseek"
    ) -> AsyncGenerator[str, None]:
        """Original streaming method - backward compatibility"""
        async for chunk in self.chat_completion_stream_with_reasoning(
            messages, provider, use_reasoning=False
        ):
            yield chunk

    def _deepseek_completion_sync(self, messages: List[Dict]) -> str:
        """
        Synchronous DeepSeek completion
        """
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4000,
            "stream": False,
        }

        try:
            response = requests.post(
                self.deepseek_api_url, headers=headers, json=data, timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                return f"DeepSeek API Error: {response.status_code} - {response.text}"

        except Exception as e:
            return f"DeepSeek request failed: {str(e)}"

    async def _deepseek_completion_async(self, messages: List[Dict]) -> str:
        """
        Asynchronous DeepSeek completion (non-streaming) - ENHANCED DEBUG VERSION
        """
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.1,  # Lower temperature for more consistent results
            "max_tokens": 2000,  # Reduced from 4000 to prevent timeout
            "stream": False,
        }

        self.logger.info(
            f"DeepSeek async call - {len(messages)} messages, total chars: {sum(len(str(m.get('content', ''))) for m in messages)}"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.deepseek_api_url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(
                        total=120
                    ),  # Increased timeout to 120s
                ) as response:
                    self.logger.info(f"DeepSeek response status: {response.status}")

                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        self.logger.info(
                            f"DeepSeek success - response length: {len(content)} chars"
                        )
                        return content
                    else:
                        error_text = await response.text()
                        self.logger.error(
                            f"DeepSeek API Error: {response.status} - {error_text}"
                        )
                        return f"DeepSeek API Error: {response.status} - {error_text}"

        except Exception as e:
            self.logger.error(f"DeepSeek async exception: {str(e)}")
            import traceback

            self.logger.error(f"DeepSeek traceback: {traceback.format_exc()}")
            return f"DeepSeek request failed: {str(e)}"

    # ===== ADDITIONAL METHODS FOR API COMPATIBILITY =====

    async def get_available_providers(self) -> List[str]:
        """
        ✅ Get list of available AI providers
        """
        providers = ["deepseek"]
        if self.chatgpt_client:
            providers.append("chatgpt")
        if self.gemini_client:
            providers.append("gemini")
        if self.cerebras_client:
            providers.append("cerebras")
        return providers

    def get_current_provider(self) -> str:
        """
        ✅ Get current default provider
        """
        return "deepseek"  # Default provider

    async def get_response(
        self,
        question: str,
        user_id: Optional[str] = None,
        provider: str = "deepseek",
    ) -> str:
        """
        ✅ Get single response from AI provider (non-streaming)
        """
        try:
            messages = [{"role": "user", "content": question}]

            if provider == "chatgpt" and self.chatgpt_client:
                return await self.chatgpt_client.get_completion(messages)
            elif provider == "cerebras" and self.cerebras_client:
                return await self.cerebras_client.chat_completion(messages)
            elif provider == "gemini" and self.gemini_client:
                # Note: Gemini client would need a non-streaming method
                return await self.gemini_client.get_completion(messages)
            else:
                # Use DeepSeek
                return await self._deepseek_completion_async(messages)

        except Exception as e:
            self.logger.error(f"Error in get_response: {e}")
            return f"Xin lỗi, đã có lỗi xảy ra: {str(e)}"

    async def stream_response(
        self,
        question: str,
        user_id: Optional[str] = None,
        provider: str = "deepseek",
    ) -> AsyncGenerator[str, None]:
        """
        ✅ Stream response from AI provider
        """
        try:
            messages = [{"role": "user", "content": question}]

            async for chunk in self.chat_completion_stream_with_reasoning(
                messages, provider
            ):
                yield chunk

        except Exception as e:
            self.logger.error(f"Error in stream_response: {e}")
            yield f"Xin lỗi, đã có lỗi xảy ra: {str(e)}"

    async def clear_history(self, user_id: Optional[str] = None):
        """
        ✅ Clear chat history for user (simplified without session_id)
        """
        self.logger.info(f"History cleared for user: {user_id or 'anonymous'}")
        # TODO: Implement actual history storage and clearing based on user_id
        return True

    # ===== END ADDITIONAL METHODS =====

    async def chat_with_file_stream(
        self,
        messages: List[Dict],
        file_content: bytes,
        file_name: str,
        provider: str = "gemini",
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat with file upload support.
        Currently only supports Gemini provider.
        """
        try:
            if provider == "gemini" and self.gemini_client:
                async for chunk in self.gemini_client.chat_with_file_stream(
                    messages, file_content, file_name, temperature
                ):
                    yield chunk
            elif provider == "chatgpt" and self.chatgpt_client:
                # ChatGPT doesn't have direct file upload, could implement URL-based approach
                yield f"ChatGPT file upload chưa được hỗ trợ trong phương thức này."
            else:
                yield f"Provider {provider} không hỗ trợ chat với file upload."

        except Exception as e:
            self.logger.error(f"❌ Error in chat_with_file_stream: {e}")
            yield f"Lỗi {provider} file processing: {str(e)}"

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using sentence-transformers (768 dimensions)
        Tạo vector embedding cho text sử dụng sentence-transformers (768 dimensions)
        """
        try:
            # Import EmbeddingService to use 768-dimension model
            from src.services.embedding_service import get_embedding_service

            # Use singleton embedding service instance
            embedding_service = get_embedding_service()

            # Generate embedding using sentence-transformers
            embedding = await embedding_service.generate_embedding(text)

            self.logger.info(f"✅ Generated embedding with {len(embedding)} dimensions")
            return embedding

        except Exception as e:
            self.logger.error(f"Failed to generate embedding: {e}")
            return []

    async def generate_embeddings_batch(
        self, texts: List[str], max_batch_size: int = 20, timeout_seconds: int = 300
    ) -> List[List[float]]:
        """
        Generate embedding vectors for multiple texts efficiently using batch processing
        Tạo vector embedding cho nhiều text hiệu quả sử dụng batch processing
        """
        try:
            # Import EmbeddingService to use 768-dimension model
            from src.services.embedding_service import get_embedding_service

            # Use singleton embedding service instance
            embedding_service = get_embedding_service()

            # Generate embeddings using batch processing with timeout and size limits
            embeddings = await embedding_service.generate_embeddings_batch(
                texts=texts,
                max_batch_size=max_batch_size,
                timeout_seconds=timeout_seconds,
            )

            self.logger.info(f"✅ Generated {len(embeddings)} embeddings in batch mode")
            return embeddings

        except Exception as e:
            self.logger.error(f"Failed to generate batch embeddings: {e}")
            # Return zero vectors as fallback
            return [[0.0] * 768] * len(texts)

    async def stream_chat_completion(
        self,
        messages: List[Dict],
        provider: str = "deepseek",
        use_reasoning: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Alias method for backward compatibility.
        Delegates to chat_completion_stream_with_reasoning.
        """
        async for chunk in self.chat_completion_stream_with_reasoning(
            messages=messages, provider=provider, use_reasoning=use_reasoning
        ):
            yield chunk
