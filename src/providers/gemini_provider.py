"""
Google Gemini Provider
AI Provider sử dụng Google Gemini API
"""

import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from src.core.config import get_config

logger = logging.getLogger(__name__)


class GeminiProvider:
    """
    Google Gemini AI Provider for conversation analysis
    Nhà cung cấp AI Google Gemini cho phân tích cuộc trò chuyện
    """

    def __init__(self):
        self.config = get_config()
        self.api_key = self.config.get("GEMINI_API_KEY")
        self.model_name = self.config.get("GEMINI_MODEL", "gemini-1.5-pro")
        self.enabled = GEMINI_AVAILABLE and bool(self.api_key)

        if not GEMINI_AVAILABLE:
            logger.warning(
                "❌ Google Gemini not available. Install: pip install google-generativeai"
            )
            return

        if not self.api_key:
            logger.warning("❌ GEMINI_API_KEY not found in configuration")
            return

        try:
            # Configure Gemini
            genai.configure(api_key=self.api_key)

            # Initialize model
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=4000,
                ),
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                },
            )

            logger.info(f"✅ Gemini Provider initialized with model: {self.model_name}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini Provider: {e}")
            self.enabled = False

    async def get_completion(
        self,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> str:
        """
        Get completion from Gemini
        Lấy phản hồi từ Gemini
        """
        if not self.enabled:
            raise Exception("Gemini Provider not available or not configured")

        try:
            logger.info(f"🤖 Sending request to Gemini (model: {self.model_name})")
            logger.debug(f"   Prompt length: {len(prompt)} chars")
            logger.debug(f"   Max tokens: {max_tokens}, Temperature: {temperature}")

            start_time = datetime.now()

            # Update generation config if different from default
            if temperature != 0.3 or max_tokens != 4000:
                generation_config = genai.GenerationConfig(
                    temperature=temperature,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=max_tokens,
                )

                # Create temporary model with new config
                temp_model = genai.GenerativeModel(
                    model_name=self.model_name,
                    generation_config=generation_config,
                    safety_settings=self.model._safety_settings,
                )

                response = await asyncio.wait_for(
                    asyncio.create_task(temp_model.generate_content_async(prompt)),
                    timeout=timeout,
                )
            else:
                response = await asyncio.wait_for(
                    asyncio.create_task(self.model.generate_content_async(prompt)),
                    timeout=timeout,
                )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            if response.parts:
                content = response.text
                logger.info(f"✅ Gemini response received in {duration:.2f}s")
                logger.debug(f"   Response length: {len(content)} chars")

                # Log token usage if available
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    usage = response.usage_metadata
                    logger.info(
                        f"   Token usage - Input: {usage.prompt_token_count}, Output: {usage.candidates_token_count}"
                    )

                return content
            else:
                logger.warning("⚠️ Gemini returned empty response")
                return "No response generated"

        except asyncio.TimeoutError:
            logger.error(f"❌ Gemini request timed out after {timeout}s")
            raise Exception(f"Gemini request timed out after {timeout} seconds")

        except Exception as e:
            logger.error(f"❌ Gemini API error: {e}")

            # Handle specific Gemini errors
            if "quota" in str(e).lower():
                raise Exception("Gemini API quota exceeded. Please check your billing.")
            elif "invalid" in str(e).lower() and "key" in str(e).lower():
                raise Exception(
                    "Invalid Gemini API key. Please check your configuration."
                )
            elif "safety" in str(e).lower():
                raise Exception("Content blocked by Gemini safety filters.")
            else:
                raise Exception(f"Gemini API error: {str(e)}")

    async def analyze_conversation(
        self,
        conversation_text: str,
        company_context: Optional[str] = None,
        analysis_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """
        Specialized method for conversation analysis
        Phương thức chuyên biệt cho phân tích cuộc trò chuyện
        """
        if not self.enabled:
            raise Exception("Gemini Provider not available")

        try:
            # Build analysis prompt based on type
            if analysis_type == "comprehensive":
                prompt = self._build_comprehensive_analysis_prompt(
                    conversation_text, company_context
                )
            elif analysis_type == "sentiment":
                prompt = self._build_sentiment_analysis_prompt(conversation_text)
            elif analysis_type == "intent":
                prompt = self._build_intent_analysis_prompt(conversation_text)
            else:
                prompt = conversation_text

            # Get analysis from Gemini
            response = await self.get_completion(
                prompt=prompt,
                max_tokens=4000,
                temperature=0.2,  # Lower temperature for analysis consistency
            )

            # Try to parse as JSON
            try:
                analysis_result = json.loads(self._clean_json_response(response))
                return analysis_result
            except json.JSONDecodeError:
                # Return structured fallback
                return {
                    "analysis_type": analysis_type,
                    "raw_response": response,
                    "parsed": False,
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"❌ Conversation analysis failed: {e}")
            raise

    def _build_comprehensive_analysis_prompt(
        self, conversation: str, company_context: str = None
    ) -> str:
        """Build comprehensive analysis prompt"""
        context_section = (
            f"\nNGỮ CẢNH CÔNG TY:\n{company_context}\n" if company_context else ""
        )

        return f"""
BẠN LÀ CHUYÊN GIA PHÂN TÍCH CUỘC TRÒ CHUYỆN CHUYÊN NGHIỆP.

{context_section}
CUỘC TRÒ CHUYỆN CẦN PHÂN TÍCH:
{conversation}

Hãy phân tích cuộc trò chuyện này và trả về JSON với các thông tin sau:
- intent: Ý định chính của khách hàng
- sentiment: Cảm xúc tổng thể (positive/neutral/negative)
- satisfaction: Mức độ hài lòng (high/medium/low)
- key_points: Những điểm chính trong cuộc trò chuyện
- next_actions: Hành động tiếp theo nên thực hiện
- business_value: Giá trị kinh doanh tiềm năng

Trả về JSON hợp lệ, không có text bổ sung.
"""

    def _build_sentiment_analysis_prompt(self, conversation: str) -> str:
        """Build sentiment analysis prompt"""
        return f"""
Phân tích cảm xúc của cuộc trò chuyện sau và trả về JSON:

{conversation}

JSON format:
{{
    "overall_sentiment": "positive/neutral/negative",
    "customer_mood": "happy/neutral/frustrated/angry",
    "confidence": 0.0-1.0,
    "emotional_indicators": ["chỉ báo cảm xúc"]
}}
"""

    def _build_intent_analysis_prompt(self, conversation: str) -> str:
        """Build intent analysis prompt"""
        return f"""
Phân tích ý định của khách hàng trong cuộc trò chuyện và trả về JSON:

{conversation}

JSON format:
{{
    "primary_intent": "sales/support/information/complaint",
    "confidence": 0.0-1.0,
    "intent_evolution": [
        {{"turn": 1, "intent": "information", "confidence": 0.8}}
    ],
    "key_requirements": ["yêu cầu chính"]
}}
"""

    def _clean_json_response(self, response: str) -> str:
        """Clean JSON response from Gemini"""
        try:
            # Remove markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            # Remove extra whitespace
            response = response.strip()

            # Find JSON object bounds
            start_idx = response.find("{")
            end_idx = response.rfind("}")

            if start_idx != -1 and end_idx != -1:
                response = response[start_idx : end_idx + 1]

            return response

        except Exception as e:
            logger.warning(f"⚠️ JSON cleaning failed: {e}")
            return response

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "provider": "google_gemini",
            "model": self.model_name,
            "enabled": self.enabled,
            "available": GEMINI_AVAILABLE,
            "features": [
                "conversation_analysis",
                "sentiment_analysis",
                "intent_detection",
                "json_output",
                "safety_filters",
            ],
        }

    async def test_connection(self) -> bool:
        """Test Gemini connection"""
        if not self.enabled:
            return False

        try:
            test_response = await self.get_completion(
                "Respond with: 'Connection successful'", max_tokens=10, timeout=10
            )

            return "successful" in test_response.lower()

        except Exception as e:
            logger.error(f"❌ Gemini connection test failed: {e}")
            return False


# Global instance
gemini_provider = GeminiProvider()
