"""
AI Client service for multiple providers
"""

from typing import Dict, Any, Optional
import asyncio
import json
import httpx
from ..config.ai_config import get_ai_client


class MultiAIClient:
    """Client for handling multiple AI providers"""

    def __init__(self):
        self.default_client = get_ai_client()
        self.providers = {
            "deepseek": {
                "endpoint": "https://api.deepseek.com/v1/chat/completions",
                "model": "deepseek-chat",
                "api_key_env": "DEEPSEEK_API_KEY",
            },
            "qwen-2.5b-instruct": {
                "endpoint": "https://api.qwen.com/v1/chat/completions",
                "model": "qwen-2.5b-instruct",
                "api_key_env": "QWEN_API_KEY",
            },
            "gemini-2.5-pro": {
                "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent",
                "model": "gemini-2.5-pro",
                "api_key_env": "GEMINI_API_KEY",
            },
        }

    async def generate_text(
        self,
        prompt: str,
        model: str = "deepseek",
        max_tokens: int = 8000,
        temperature: float = 0.8,
    ) -> str:
        """Generate text using specified AI model"""

        if model not in self.providers:
            # Fallback to default client
            return await self._use_default_client(prompt, max_tokens, temperature)

        try:
            if model == "deepseek":
                return await self._call_deepseek(prompt, max_tokens, temperature)
            elif model == "qwen-2.5b-instruct":
                return await self._call_qwen(prompt, max_tokens, temperature)
            elif model == "gemini-2.5-pro":
                return await self._call_gemini(prompt, max_tokens, temperature)
            else:
                return await self._use_default_client(prompt, max_tokens, temperature)

        except Exception as e:
            print(f"Error with {model}: {e}")
            # Fallback to default client
            return await self._use_default_client(prompt, max_tokens, temperature)

    async def _call_deepseek(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> str:
        """Call DeepSeek API"""
        import os

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not found")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": False,
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                raise Exception(
                    f"DeepSeek API error: {response.status_code} - {response.text}"
                )

    async def _call_qwen(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Call Qwen API"""
        import os

        api_key = os.getenv("QWEN_API_KEY")
        if not api_key:
            raise ValueError("QWEN_API_KEY not found")

        # Note: This is a placeholder - adjust endpoint based on actual Qwen API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "qwen-max",
                    "input": {"prompt": prompt},
                    "parameters": {
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                result = response.json()
                return result["output"]["text"]
            else:
                raise Exception(
                    f"Qwen API error: {response.status_code} - {response.text}"
                )

    async def _call_gemini(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> str:
        """Call Gemini API"""
        import os

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": temperature,
                    },
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                result = response.json()
                return result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                raise Exception(
                    f"Gemini API error: {response.status_code} - {response.text}"
                )

    async def _use_default_client(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> str:
        """Use default AI client as fallback"""
        try:
            return await self.default_client.generate_text(
                prompt=prompt, max_tokens=max_tokens, temperature=temperature
            )
        except Exception as e:
            # Ultimate fallback - return a basic template structure
            return self._get_fallback_response(prompt)

    def _get_fallback_response(self, prompt: str) -> str:
        """Generate fallback response when all AI services fail"""
        if "báo giá" in prompt.lower() or "quote" in prompt.lower():
            return """
{
    "title": "BÁO GIÁ",
    "sections": [
        {
            "name": "header",
            "content": {
                "company_logo": true,
                "company_info": true,
                "document_title": "BÁO GIÁ"
            }
        },
        {
            "name": "document_info",
            "content": {
                "quote_number": "[Số báo giá]",
                "date": "[Ngày lập]",
                "validity": "30 ngày"
            }
        },
        {
            "name": "customer_info",
            "content": {
                "customer_name": "[Tên khách hàng]",
                "address": "[Địa chỉ]",
                "contact": "[Người liên hệ]"
            }
        },
        {
            "name": "products_table",
            "content": {
                "headers": ["STT", "Sản phẩm/Dịch vụ", "Số lượng", "Đơn vị", "Đơn giá", "Thành tiền"],
                "show_total": true,
                "show_vat": true
            }
        },
        {
            "name": "payment_terms",
            "content": {
                "payment_method": "[Phương thức thanh toán]",
                "payment_schedule": "[Lịch thanh toán]"
            }
        },
        {
            "name": "signature",
            "content": {
                "company_signature": true,
                "date_location": true
            }
        }
    ]
}
            """
        else:
            return """
{
    "title": "TÀI LIỆU",
    "sections": ["header", "content", "signature"],
    "layout": "standard"
}
            """


# Global instance
multi_ai_client = MultiAIClient()
