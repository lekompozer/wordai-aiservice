"""
AI Chat Service with Multiple Providers
Service để chat với nhiều AI providers khác nhau
"""

import os
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
from enum import Enum
import json
from datetime import datetime

# AI Clients
import openai
from cerebras.cloud.sdk import Cerebras
import google.generativeai as genai
from openai import OpenAI

from src.utils.logger import setup_logger

logger = setup_logger()


class AIProvider(str, Enum):
    """Supported AI Providers"""

    # OpenAI Models
    CHATGPT_4O_LATEST = "chatgpt_4o_latest"

    # DeepSeek Models
    DEEPSEEK_CHAT = "deepseek_chat"
    DEEPSEEK_REASONER = "deepseek_reasoner"

    # Cerebras Models
    QWEN_235B_INSTRUCT = "qwen_235b_instruct"
    QWEN_235B_THINKING = "qwen_235b_thinking"
    QWEN_480B_CODER = "qwen_480b_coder"
    QWEN_32B = "qwen_32b"
    LLAMA_70B = "llama_70b"
    LLAMA_8B = "llama_8b"

    # Gemini Models
    GEMINI_FLASH_IMAGE = "gemini_flash_image"
    GEMINI_FLASH = "gemini_flash"
    GEMINI_PRO = "gemini_pro"


class AIChatService:
    """Service for chatting with multiple AI providers"""

    def __init__(self):
        self.providers = {}
        self.models = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize all AI providers"""
        try:
            # OpenAI
            if os.getenv("CHATGPT_API_KEY"):
                self.providers[AIProvider.CHATGPT_4O_LATEST] = openai.AsyncOpenAI(
                    api_key=os.getenv("CHATGPT_API_KEY")
                )
                self.models[AIProvider.CHATGPT_4O_LATEST] = "chatgpt-4o-latest"
                logger.info("✅ OpenAI client initialized")

            # DeepSeek (OpenAI compatible)
            if os.getenv("DEEPSEEK_API_KEY"):
                deepseek_client = openai.AsyncOpenAI(
                    api_key=os.getenv("DEEPSEEK_API_KEY"),
                    base_url="https://api.deepseek.com",
                )

                self.providers[AIProvider.DEEPSEEK_CHAT] = deepseek_client
                self.models[AIProvider.DEEPSEEK_CHAT] = "deepseek-chat"

                self.providers[AIProvider.DEEPSEEK_REASONER] = deepseek_client
                self.models[AIProvider.DEEPSEEK_REASONER] = "deepseek-reasoner"

                logger.info("✅ DeepSeek clients initialized")

            # Cerebras - All models
            if os.getenv("CEREBRAS_API_KEY"):
                cerebras_client = openai.AsyncOpenAI(
                    api_key=os.getenv("CEREBRAS_API_KEY"),
                    base_url="https://api.cerebras.ai/v1",
                )

                # Qwen models
                self.providers[AIProvider.QWEN_235B_INSTRUCT] = cerebras_client
                self.models[AIProvider.QWEN_235B_INSTRUCT] = (
                    "qwen-3-235b-a22b-instruct-2507"
                )

                self.providers[AIProvider.QWEN_235B_THINKING] = cerebras_client
                self.models[AIProvider.QWEN_235B_THINKING] = (
                    "qwen-3-235b-a22b-thinking-2507"
                )

                self.providers[AIProvider.QWEN_480B_CODER] = cerebras_client
                self.models[AIProvider.QWEN_480B_CODER] = "qwen-3-coder-480b"

                self.providers[AIProvider.QWEN_32B] = cerebras_client
                self.models[AIProvider.QWEN_32B] = "qwen-3-32b"

                # Llama models
                self.providers[AIProvider.LLAMA_70B] = cerebras_client
                self.models[AIProvider.LLAMA_70B] = "llama-3.3-70b"

                self.providers[AIProvider.LLAMA_8B] = cerebras_client
                self.models[AIProvider.LLAMA_8B] = "llama3.1-8b"

                logger.info("✅ Cerebras clients initialized (6 models)")

            # Gemini
            if os.getenv("GEMINI_API_KEY"):
                import google.generativeai as genai_new

                genai_new.configure(api_key=os.getenv("GEMINI_API_KEY"))

                # Gemini Flash Image Preview
                self.providers[AIProvider.GEMINI_FLASH_IMAGE] = genai_new
                self.models[AIProvider.GEMINI_FLASH_IMAGE] = (
                    "gemini-2.5-flash-image-preview"
                )

                # Gemini Flash
                self.providers[AIProvider.GEMINI_FLASH] = genai_new
                self.models[AIProvider.GEMINI_FLASH] = "gemini-2.5-flash"

                # Gemini Pro
                self.providers[AIProvider.GEMINI_PRO] = genai_new
                self.models[AIProvider.GEMINI_PRO] = "gemini-2.5-pro"

                logger.info("✅ Gemini clients initialized (3 models)")

        except Exception as e:
            logger.error(f"❌ Error initializing AI providers: {e}")

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Get list of available AI providers"""
        providers = []

        provider_info = {
            AIProvider.CHATGPT_4O_LATEST: {
                "name": "ChatGPT-4o Latest",
                "description": "Latest version of ChatGPT-4o with improved performance",
                "category": "latest",
            },
            AIProvider.DEEPSEEK_CHAT: {
                "name": "DeepSeek Chat",
                "description": "DeepSeek's general conversation model",
                "category": "general",
            },
            AIProvider.DEEPSEEK_REASONER: {
                "name": "DeepSeek Reasoner",
                "description": "DeepSeek's advanced reasoning model",
                "category": "reasoning",
            },
            AIProvider.QWEN_235B_INSTRUCT: {
                "name": "Qwen 235B Instruct",
                "description": "Large-scale instruction following model",
                "category": "instruct",
            },
            AIProvider.QWEN_235B_THINKING: {
                "name": "Qwen 235B Thinking",
                "description": "Step-by-step reasoning model",
                "category": "thinking",
            },
            AIProvider.QWEN_480B_CODER: {
                "name": "Qwen 480B Coder",
                "description": "Specialized programming and coding model",
                "category": "coding",
            },
            AIProvider.QWEN_32B: {
                "name": "Qwen 32B",
                "description": "Efficient general purpose model",
                "category": "general",
            },
            AIProvider.LLAMA_70B: {
                "name": "Llama 3.3 70B",
                "description": "Meta's powerful general purpose model",
                "category": "general",
            },
            AIProvider.LLAMA_8B: {
                "name": "Llama 3.1 8B",
                "description": "Lightweight and fast model",
                "category": "lightweight",
            },
            AIProvider.GEMINI_FLASH_IMAGE: {
                "name": "Gemini 2.5 Flash Image Preview",
                "description": "Google's multimodal model with image capabilities",
                "category": "image",
            },
            AIProvider.GEMINI_FLASH: {
                "name": "Gemini 2.5 Flash",
                "description": "Google's fast and efficient model",
                "category": "fast",
            },
            AIProvider.GEMINI_PRO: {
                "name": "Gemini 2.5 Pro",
                "description": "Google's advanced multimodal model",
                "category": "advanced",
            },
        }

        for provider in self.providers.keys():
            info = provider_info.get(provider, {})
            providers.append(
                {
                    "id": provider.value,
                    "name": info.get("name", provider.value),
                    "description": info.get(
                        "description", f"{provider.value} AI model"
                    ),
                    "category": info.get("category", "general"),
                    "model": self.models.get(provider, "unknown"),
                    "available": True,
                }
            )

        return providers

    async def chat(
        self,
        provider: AIProvider,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """Get complete chat response from specified AI provider (non-streaming)"""

        if provider not in self.providers:
            raise ValueError(f"Provider {provider} not available")

        try:
            if provider in [AIProvider.CHATGPT_4O_LATEST]:
                # OpenAI providers
                return await self._chat_openai_compatible(
                    provider, messages, temperature, max_tokens
                )

            elif provider in [AIProvider.DEEPSEEK_CHAT, AIProvider.DEEPSEEK_REASONER]:
                # DeepSeek providers (OpenAI-compatible)
                return await self._chat_openai_compatible(
                    provider, messages, temperature, max_tokens
                )

            elif provider in [
                AIProvider.QWEN_235B_INSTRUCT,
                AIProvider.QWEN_235B_THINKING,
                AIProvider.QWEN_480B_CODER,
                AIProvider.QWEN_32B,
                AIProvider.LLAMA_70B,
                AIProvider.LLAMA_8B,
            ]:
                # Cerebras providers (OpenAI-compatible)
                return await self._chat_openai_compatible(
                    provider, messages, temperature, max_tokens
                )

            elif provider in [
                AIProvider.GEMINI_FLASH_IMAGE,
                AIProvider.GEMINI_FLASH,
                AIProvider.GEMINI_PRO,
            ]:
                # Gemini models
                return await self._chat_gemini(
                    provider, messages, temperature, max_tokens
                )

        except Exception as e:
            logger.error(f"❌ Error chatting with {provider}: {e}")
            raise

    async def chat_stream(
        self,
        provider: AIProvider,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response from specified AI provider"""

        if provider not in self.providers:
            yield f"❌ Provider {provider} not available"
            return

        try:
            if provider in [AIProvider.CHATGPT_4O_LATEST]:
                # OpenAI providers
                async for chunk in self._stream_openai_compatible(
                    provider, messages, temperature, max_tokens
                ):
                    yield chunk

            elif provider in [AIProvider.DEEPSEEK_CHAT, AIProvider.DEEPSEEK_REASONER]:
                # DeepSeek providers (OpenAI-compatible)
                async for chunk in self._stream_openai_compatible(
                    provider, messages, temperature, max_tokens
                ):
                    yield chunk

            elif provider in [
                AIProvider.QWEN_235B_INSTRUCT,
                AIProvider.QWEN_235B_THINKING,
                AIProvider.QWEN_480B_CODER,
                AIProvider.QWEN_32B,
                AIProvider.LLAMA_70B,
                AIProvider.LLAMA_8B,
            ]:
                # Cerebras providers (OpenAI-compatible)
                async for chunk in self._stream_openai_compatible(
                    provider, messages, temperature, max_tokens
                ):
                    yield chunk

            elif provider in [
                AIProvider.GEMINI_FLASH_IMAGE,
                AIProvider.GEMINI_FLASH,
                AIProvider.GEMINI_PRO,
            ]:
                # Gemini models
                async for chunk in self._stream_gemini(
                    provider, messages, temperature, max_tokens
                ):
                    yield chunk

        except Exception as e:
            logger.error(f"❌ Error streaming from {provider}: {e}")
            yield f"❌ Error: {str(e)}"

    async def _chat_openai_compatible(
        self,
        provider: AIProvider,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        max_retries: int = 3,
    ) -> str:
        """Get complete response from OpenAI-compatible providers with retry logic"""

        client = self.providers[provider]
        model = self.models[provider]

        # Retry logic for transient errors
        for attempt in range(max_retries):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                return response.choices[0].message.content

            except Exception as e:
                error_str = str(e).lower()

                # Check if error is retryable (rate limit, server error, timeout, overload)
                is_retryable = any(
                    keyword in error_str
                    for keyword in [
                        "rate limit",
                        "429",
                        "too many requests",
                        "server error",
                        "500",
                        "502",
                        "503",
                        "504",
                        "timeout",
                        "connection",
                        "overload",
                        "529",
                    ]
                )

                if is_retryable and attempt < max_retries - 1:
                    wait_time = (2**attempt) + 1  # Exponential backoff: 2s, 5s, 9s
                    logger.warning(
                        f"⚠️ {provider} error (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time}s... Error: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Non-retryable or max retries reached
                    logger.error(f"❌ {provider} chat error: {e}")
                    raise

        # Should not reach here
        raise Exception(f"{provider} failed after {max_retries} retries")

    async def _chat_gemini(
        self,
        provider: AIProvider,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        max_retries: int = 3,
    ) -> str:
        """Get complete response from Gemini models with retry logic"""

        model_name = self.models[provider]

        # Retry logic for transient errors
        for attempt in range(max_retries):
            try:
                # Convert messages to Gemini format
                gemini_prompt = self._convert_messages_to_gemini(messages)

                # Get Gemini client for this request
                genai_client = self.providers[provider]

                # Create Gemini model
                model = genai_client.GenerativeModel(model_name)

                # Generate response
                response = model.generate_content(
                    gemini_prompt,
                    generation_config=genai_client.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )

                return response.text

            except Exception as e:
                error_str = str(e).lower()

                # Check if error is retryable
                is_retryable = any(
                    keyword in error_str
                    for keyword in [
                        "rate limit",
                        "429",
                        "quota",
                        "server error",
                        "500",
                        "502",
                        "503",
                        "504",
                        "timeout",
                        "deadline",
                        "unavailable",
                        "overload",
                        "529",
                        "resource_exhausted",
                    ]
                )

                if is_retryable and attempt < max_retries - 1:
                    wait_time = (2**attempt) + 1  # Exponential backoff: 2s, 5s, 9s
                    logger.warning(
                        f"⚠️ Gemini {provider} error (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time}s... Error: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Non-retryable or max retries reached
                    logger.error(f"❌ Gemini chat error: {e}")
                    raise

        # Should not reach here
        raise Exception(f"Gemini {provider} failed after {max_retries} retries")

    async def _stream_openai_compatible(
        self,
        provider: AIProvider,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Stream from OpenAI-compatible providers with retry logic"""

        client = self.providers[provider]
        model = self.models[provider]
        max_retries = 3

        # Retry logic for establishing the stream
        for attempt in range(max_retries):
            try:
                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                # Once stream is established, yield chunks
                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

                # Success, exit retry loop
                break

            except Exception as e:
                error_str = str(e).lower()
                provider_name = (
                    provider.value if hasattr(provider, "value") else str(provider)
                )

                # Check if error is retryable
                is_retryable = any(
                    keyword in error_str
                    for keyword in [
                        "rate limit",
                        "429",
                        "too many requests",
                        "server error",
                        "500",
                        "502",
                        "503",
                        "504",
                        "timeout",
                        "connection",
                        "overload",
                        "529",
                    ]
                )

                if is_retryable and attempt < max_retries - 1:
                    wait_time = (2**attempt) + 1  # 2s, 5s, 9s
                    logger.warning(
                        f"⚠️ {provider_name} streaming error (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"❌ {provider_name} streaming error after {attempt + 1} attempts: {e}"
                    )
                    yield f"❌ Streaming error: {str(e)}"
                    break

    async def _stream_gemini(
        self,
        provider: AIProvider,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Stream from Gemini models with retry logic"""

        model_name = self.models[provider]
        max_retries = 3

        # Retry logic for establishing the stream
        for attempt in range(max_retries):
            try:
                # Convert messages to Gemini format
                gemini_prompt = self._convert_messages_to_gemini(messages)

                # Get Gemini client for this request
                genai_client = self.providers[provider]

                # Create Gemini model
                model = genai_client.GenerativeModel(model_name)

                # Generate streaming response
                response = model.generate_content(
                    gemini_prompt,
                    generation_config=genai_client.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                    stream=True,
                )

                # Once stream is established, yield chunks
                for chunk in response:
                    if chunk.text:
                        yield chunk.text

                # Success, exit retry loop
                break

            except Exception as e:
                error_str = str(e).lower()

                # Check if error is retryable
                is_retryable = any(
                    keyword in error_str
                    for keyword in [
                        "rate limit",
                        "429",
                        "too many requests",
                        "server error",
                        "500",
                        "502",
                        "503",
                        "504",
                        "timeout",
                        "connection",
                        "overload",
                        "529",
                        "resource exhausted",
                        "deadline exceeded",
                    ]
                )

                if is_retryable and attempt < max_retries - 1:
                    wait_time = (2**attempt) + 1  # 2s, 5s, 9s
                    logger.warning(
                        f"⚠️ Gemini streaming error (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"❌ Gemini streaming error after {attempt + 1} attempts: {e}"
                    )
                    yield f"❌ Streaming error: {str(e)}"
                    break

    def _convert_messages_to_gemini(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI format messages to Gemini format"""

        gemini_prompt = ""

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                gemini_prompt += f"System: {content}\n\n"
            elif role == "user":
                gemini_prompt += f"Human: {content}\n\n"
            elif role == "assistant":
                gemini_prompt += f"Assistant: {content}\n\n"

        # Add final prompt for assistant response
        if not gemini_prompt.endswith("Assistant: "):
            gemini_prompt += "Assistant: "

        return gemini_prompt.strip()


# Global instance
ai_chat_service = AIChatService()
