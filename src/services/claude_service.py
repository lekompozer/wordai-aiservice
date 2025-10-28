"""
Claude (Anthropic) Service
Provides Claude AI integration for chat, editing, and document processing
"""

import os
import httpx
from typing import List, Dict, Optional, AsyncGenerator
from config import config
from src.utils.logger import setup_logger

logger = setup_logger()


class ClaudeService:
    """Service for Claude AI (Anthropic API)"""

    def __init__(self):
        """Initialize Claude service"""
        self.api_key = config.ANTHROPIC_API_KEY
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured")

        self.api_url = "https://api.anthropic.com/v1/messages"
        self.api_version = "2023-06-01"
        self.default_model = config.CLAUDE_MODEL  # Haiku 4.5
        self.sonnet_model = config.CLAUDE_SONNET_MODEL

        logger.info(f"✅ ClaudeService initialized with model: {self.default_model}")

    async def chat(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        max_tokens: int = 16000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Send chat request to Claude (non-streaming)

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Claude model to use (default: Haiku 4.5)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt

        Returns:
            Response text from Claude
        """
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        model = model or self.default_model

        # Convert messages format if needed (handle 'system' role)
        claude_messages = []
        system_content = system_prompt or ""

        for msg in messages:
            if msg["role"] == "system":
                # Extract system message
                system_content = msg["content"]
            else:
                # Keep user/assistant messages
                claude_messages.append({"role": msg["role"], "content": msg["content"]})

        # Build request payload
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": claude_messages,
        }

        # Add system prompt if provided
        if system_content:
            payload["system"] = system_content

        logger.info(f"🤖 Calling Claude API: {model}, {len(claude_messages)} messages")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": self.api_version,
                        "content-type": "application/json",
                    },
                    json=payload,
                )

                response.raise_for_status()
                result = response.json()

                # Extract text from response
                content = result.get("content", [])
                if content and len(content) > 0:
                    text = content[0].get("text", "")
                    logger.info(f"✅ Claude response: {len(text)} chars")
                    return text
                else:
                    logger.error("❌ No content in Claude response")
                    return ""

        except httpx.HTTPStatusError as e:
            logger.error(
                f"❌ Claude API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"❌ Claude request failed: {e}")
            raise

    async def chat_stream(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        max_tokens: int = 16000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send streaming chat request to Claude

        Args:
            messages: List of message dicts
            model: Claude model to use
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            system_prompt: Optional system prompt

        Yields:
            Text chunks from Claude
        """
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        model = model or self.default_model

        # Convert messages format
        claude_messages = []
        system_content = system_prompt or ""

        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                claude_messages.append({"role": msg["role"], "content": msg["content"]})

        # Build request payload
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": claude_messages,
            "stream": True,  # Enable streaming
        }

        if system_content:
            payload["system"] = system_content

        logger.info(f"🤖 Calling Claude API (streaming): {model}")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    self.api_url,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": self.api_version,
                        "content-type": "application/json",
                    },
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    # Process SSE stream
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        # Parse SSE format: "data: {...}"
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix

                            # Skip ping events
                            if data.strip() == "[DONE]":
                                break

                            try:
                                import json

                                event = json.loads(data)

                                # Handle content_block_delta events
                                if event.get("type") == "content_block_delta":
                                    delta = event.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        text = delta.get("text", "")
                                        if text:
                                            yield text

                            except json.JSONDecodeError:
                                continue

                    logger.info("✅ Claude streaming completed")

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Claude streaming error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"❌ Claude streaming failed: {e}")
            raise

    async def edit_html(
        self,
        html_content: str,
        user_instruction: str,
        model: Optional[str] = None,
    ) -> str:
        """
        Edit HTML content based on user instruction
        Optimized for document editing use case

        Args:
            html_content: HTML to edit
            user_instruction: User's editing instruction
            model: Claude model (default: Haiku 4.5)

        Returns:
            Edited HTML content
        """
        system_prompt = """You are an expert HTML editor. Your task is to apply the user's instruction to the provided HTML snippet.
- ONLY return the modified HTML content.
- Preserve the original HTML structure and tags.
- Maintain inline styles and attributes.
- Do not add any explanations, markdown, or extra text.
- Do not wrap output in code blocks or backticks.
- Return clean HTML only."""

        user_prompt = f"""Instruction: '{user_instruction}'

HTML to edit:
{html_content}"""

        messages = [{"role": "user", "content": user_prompt}]

        # Use Haiku for fast editing
        result = await self.chat(
            messages=messages,
            model=model or self.default_model,
            max_tokens=16000,
            temperature=0.7,
            system_prompt=system_prompt,
        )

        return result.strip()


# Singleton instance
_claude_service = None


def get_claude_service() -> ClaudeService:
    """Get Claude service singleton"""
    global _claude_service
    if _claude_service is None:
        _claude_service = ClaudeService()
    return _claude_service
