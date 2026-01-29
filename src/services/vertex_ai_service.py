"""
Vertex AI Service
Wrapper for Claude 4.5 Sonnet and Gemini 3 Pro via Vertex AI
"""

import os
import logging
import json
from typing import Dict, Any, Optional, List
from anthropic import AnthropicVertex

logger = logging.getLogger("chatbot")


class VertexAIService:
    """Service for interacting with Vertex AI models (Claude 4.5 and Gemini 3 Pro)"""

    def __init__(self):
        """Initialize Vertex AI with project configuration"""
        self.project_id = os.getenv("GCP_PROJECT_ID", "wordai-6779e")
        self.location = os.getenv("GCP_REGION", "asia-southeast1")

        # Model configurations
        self.claude_model_name = "claude-sonnet-4-5@20250929"
        self.gemini_model_name = "gemini-3-pro-preview"

        # Initialize clients
        self._init_claude_client()
        self._init_gemini_client()

        logger.info(f"✅ Vertex AI Service initialized")
        logger.info(f"   📍 Project: {self.project_id}, Region: {self.location}")
        logger.info(f"   🤖 Claude: {self.claude_model_name}")
        logger.info(f"   🤖 Gemini: {self.gemini_model_name}")

    def _init_claude_client(self):
        """Initialize Claude client via Vertex AI"""
        try:
            self.claude_client = AnthropicVertex(
                region=self.location, project_id=self.project_id
            )
            logger.info(f"✅ Claude 4.5 client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Claude client: {e}")
            self.claude_client = None

    def _init_gemini_client(self):
        """Initialize Gemini client using google-genai"""
        try:
            from google import genai

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in environment")

            self.gemini_client = genai.Client(api_key=api_key)
            logger.info(f"✅ Gemini 3 Pro client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
            self.gemini_client = None

    # ========================================================================
    # Claude 4.5 Sonnet Methods (for Generate, Explain, Transform)
    # ========================================================================

    async def call_claude(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 32000,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Call Claude 4.5 Sonnet via Vertex AI

        Args:
            system_prompt: System instructions
            user_prompt: User message
            max_tokens: Maximum output tokens (32K for Claude 4.5)
            temperature: 0.0-1.0, lower = more deterministic

        Returns:
            {
                "content": str,  # AI response
                "tokens": {
                    "input": int,
                    "output": int,
                    "total": int
                },
                "model": str,
                "stop_reason": str
            }
        """
        if not self.claude_client:
            raise Exception("Claude client not initialized")

        try:
            logger.info(f"🤖 Calling Claude 4.5 Sonnet...")
            logger.info(f"   📊 Max tokens: {max_tokens}, Temperature: {temperature}")

            # Call Claude via Vertex AI (with extended timeout for long operations)
            response = self.claude_client.messages.create(
                model=self.claude_model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                timeout=600.0,  # 10 minutes timeout
            )

            # Extract response
            content = response.content[0].text

            # Token usage
            tokens = {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
                "total": response.usage.input_tokens + response.usage.output_tokens,
            }

            logger.info(f"✅ Claude response received")
            logger.info(
                f"   📊 Tokens: {tokens['input']} input + {tokens['output']} output = {tokens['total']} total"
            )

            return {
                "content": content,
                "tokens": tokens,
                "model": self.claude_model_name,
                "stop_reason": response.stop_reason,
            }

        except Exception as e:
            logger.error(f"❌ Claude API error: {e}")
            raise

    # ========================================================================
    # Gemini 3 Pro Methods (for Architecture, Scaffold)
    # ========================================================================

    async def call_gemini(
        self,
        prompt: str,
        max_tokens: int = 32000,
        temperature: float = 0.7,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Call Gemini 3 Pro using google-genai client

        Args:
            prompt: Combined system + user prompt
            max_tokens: Maximum output tokens (32K for Gemini 3 Pro)
            temperature: 0.0-1.0, higher = more creative
            response_schema: Optional JSON schema for structured output

        Returns:
            {
                "content": str or dict,  # AI response (string or parsed JSON)
                "tokens": {
                    "input": int,
                    "output": int,
                    "total": int
                },
                "model": str
            }
        """
        if not self.gemini_client:
            raise Exception("Gemini client not initialized")

        try:
            from google.genai import types as genai_types

            logger.info(f"🤖 Calling Gemini 3 Pro...")
            logger.info(f"   📊 Max tokens: {max_tokens}, Temperature: {temperature}")

            # Build generation config
            config_params = {
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            }

            # Add response schema if provided (for structured output)
            if response_schema:
                config_params["response_mime_type"] = "application/json"
                config_params["response_schema"] = response_schema

            generation_config = genai_types.GenerateContentConfig(**config_params)

            # Call Gemini
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model_name,
                contents=prompt,
                config=generation_config,
            )

            # Extract response
            content = response.text

            # Parse JSON if schema was provided
            if response_schema:
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    logger.warning(
                        "⚠️ Failed to parse Gemini JSON response, returning as string"
                    )

            # Token usage
            tokens = {
                "input": (
                    response.usage_metadata.prompt_token_count
                    if response.usage_metadata
                    else 0
                ),
                "output": (
                    response.usage_metadata.candidates_token_count
                    if response.usage_metadata
                    else 0
                ),
                "total": (
                    response.usage_metadata.total_token_count
                    if response.usage_metadata
                    else 0
                ),
            }

            logger.info(f"✅ Gemini response received")
            logger.info(
                f"   📊 Tokens: {tokens['input']} input + {tokens['output']} output = {tokens['total']} total"
            )

            return {
                "content": content,
                "tokens": tokens,
                "model": self.gemini_model_name,
            }

        except Exception as e:
            logger.error(f"❌ Gemini API error: {e}")
            raise

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def estimate_tokens(self, text: str) -> int:
        """
        Rough token estimate (1 token ≈ 4 characters)

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        return len(text) // 4

    def truncate_context(self, context: str, max_tokens: int = 150000) -> str:
        """
        Truncate context to fit within token limit

        Args:
            context: Context text
            max_tokens: Maximum allowed tokens

        Returns:
            Truncated context
        """
        estimated_tokens = self.estimate_tokens(context)

        if estimated_tokens <= max_tokens:
            return context

        # Truncate to fit
        max_chars = max_tokens * 4
        truncated = context[:max_chars]

        logger.warning(
            f"⚠️ Context truncated from {estimated_tokens} to ~{max_tokens} tokens"
        )

        return truncated + "\n\n... (context truncated)"


# Singleton instance
_vertex_ai_service: Optional[VertexAIService] = None


def get_vertex_ai_service() -> VertexAIService:
    """Get or create singleton Vertex AI service instance"""
    global _vertex_ai_service

    if _vertex_ai_service is None:
        _vertex_ai_service = VertexAIService()

    return _vertex_ai_service
