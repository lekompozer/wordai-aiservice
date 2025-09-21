import os
import json
from typing import List, Dict, AsyncGenerator, Optional
from cerebras.cloud.sdk import Cerebras
import asyncio
from src.utils.logger import setup_logger

logger = setup_logger()


class CerebrasClient:
    """
    Cerebras AI client for chat completions and streaming
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = Cerebras(api_key=api_key)
        self.logger = logger
        self.default_model = "qwen-3-235b-a22b-instruct-2507"

    async def chat_completion(
        self,
        messages: List[Dict],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> str:
        """
        Non-streaming chat completion
        """
        try:
            if model is None:
                model = self.default_model

            self.logger.info(f"🧠 Cerebras: Starting chat completion with {model}")

            # Prepare the request
            request_params = {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "stream": stream,
            }

            if max_tokens:
                request_params["max_completion_tokens"] = max_tokens

            # Make the call
            response = self.client.chat.completions.create(**request_params)

            # Extract content
            if hasattr(response, "choices") and response.choices:
                content = response.choices[0].message.content
                self.logger.info(
                    f"🧠 Cerebras: Response received - {len(content)} characters"
                )
                return content
            else:
                raise Exception("No content in Cerebras response")

        except Exception as e:
            self.logger.error(f"🧠 Cerebras chat completion error: {e}")
            raise e

    async def chat_completion_stream(
        self,
        messages: List[Dict],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat completion
        """
        try:
            if model is None:
                model = self.default_model

            self.logger.info(f"🧠 Cerebras: Starting streaming with {model}")

            # Prepare the request
            request_params = {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "stream": True,
            }

            if max_tokens:
                request_params["max_completion_tokens"] = max_tokens

            # Create streaming response
            stream = self.client.chat.completions.create(**request_params)

            # Yield chunks
            for chunk in stream:
                if hasattr(chunk, "choices") and chunk.choices:
                    if hasattr(chunk.choices[0], "delta") and hasattr(
                        chunk.choices[0].delta, "content"
                    ):
                        content = chunk.choices[0].delta.content
                        if content:
                            yield content

        except Exception as e:
            self.logger.error(f"🧠 Cerebras streaming error: {e}")
            yield f"Cerebras streaming error: {str(e)}"

    async def chat_completion_stream_with_reasoning(
        self,
        messages: List[Dict],
        use_reasoning: bool = False,
        model: str = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming with reasoning support
        """
        try:
            if use_reasoning:
                messages = self._enhance_messages_for_reasoning(messages)

            async for chunk in self.chat_completion_stream(
                messages, model, temperature
            ):
                yield chunk

        except Exception as e:
            self.logger.error(f"🧠 Cerebras reasoning error: {e}")
            yield f"Cerebras reasoning error: {str(e)}"

    def _enhance_messages_for_reasoning(self, messages: List[Dict]) -> List[Dict]:
        """
        Enhance messages for better reasoning
        """
        enhanced_messages = messages.copy()

        # Add reasoning enhancement to the last user message
        if enhanced_messages and enhanced_messages[-1]["role"] == "user":
            original_content = enhanced_messages[-1]["content"]
            enhanced_content = f"""
{original_content}

Hãy suy nghĩ từng bước một cách logic và chi tiết:
1. Phân tích vấn đề hoặc câu hỏi
2. Xem xét các khía cạnh liên quan
3. Đưa ra kết luận hoặc giải pháp hợp lý
4. Giải thích lý do cho câu trả lời của bạn
"""
            enhanced_messages[-1]["content"] = enhanced_content

        return enhanced_messages

    def get_available_models(self) -> List[str]:
        """
        Get list of available Cerebras models
        """
        return [
            "qwen-3-235b-a22b-instruct-2507",
            "llama3.1-8b",
            "llama-3.3-70b",
            "llama-4-maverick-17b-128e-instruct",
            "qwen-3-32b",
            "qwen-3-235b-a22b",
            "qwen-3-235b-a22b-instruct-2507",
            "deepseek-r1-distill-llama-70b",  # private preview
        ]

    def get_current_model(self) -> str:
        """
        Get current default model
        """
        return self.default_model
