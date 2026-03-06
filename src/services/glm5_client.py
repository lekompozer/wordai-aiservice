"""
GLM-5 Client via Vertex AI (Service Account Auth)

Model: zai-org/glm-5-maas
Endpoint: https://aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/global/endpoints/openapi/
Auth: Google Service Account JSON (same as used for TTS/Vertex AI)

NOTE: GLM-5 is a thinking model - responses come in reasoning_content (thinking)
      and content (final answer). We collect only the final content.
"""

import os
import asyncio
import logging
import httpx
import json
import time
from typing import Dict, Any, Optional

logger = logging.getLogger("chatbot")

# Vertex AI endpoint for GLM-5 (REGION=global, /v1/)
GLM5_BASE_URL = "https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/global/endpoints/openapi/chat/completions"
GLM5_MODEL = "zai-org/glm-5-maas"

_glm5_client: Optional["GLM5Client"] = None


class GLM5Client:
    """GLM-5 client via Vertex AI with cached service account token refresh"""

    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID", "wordai-6779e")
        self.creds_path = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS",
            "/app/wordai-6779e-ed6189c466f1.json",
        )
        self._token: Optional[str] = None
        self._token_expiry: float = 0  # unix timestamp
        self.endpoint = GLM5_BASE_URL.format(project_id=self.project_id)

        if not os.path.exists(self.creds_path):
            logger.warning(
                f"⚠️ GLM5Client: credentials file not found: {self.creds_path}"
            )
        else:
            logger.info(f"✅ GLM5Client initialized (project={self.project_id})")

    async def _get_token(self) -> str:
        """Get or refresh service account bearer token (cached for 55 minutes)"""
        now = time.time()
        if self._token and now < self._token_expiry:
            return self._token

        def _refresh_sync():
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request

            creds = service_account.Credentials.from_service_account_file(
                self.creds_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            creds.refresh(Request())
            return creds.token

        token = await asyncio.to_thread(_refresh_sync)
        self._token = token
        self._token_expiry = now + 55 * 60  # refresh 5 minutes before expiry
        logger.info("🔑 GLM5 token refreshed")
        return token

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8000,
        temperature: float = 0.3,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        """
        Call GLM-5 via Vertex AI (non-streaming, collects full response)

        Returns same format as vertex_ai_service.call_claude():
        {
            "content": str,
            "tokens": {"input": int, "output": int, "total": int},
            "model": str,
            "stop_reason": str
        }
        """
        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GLM5_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        logger.info(f"🤖 Calling GLM-5 (non-stream, max_tokens={max_tokens})...")

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        message = choice["message"]

        # GLM-5: final answer in 'content', thinking in 'reasoning_content'
        content = message.get("content") or message.get("reasoning_content") or ""

        usage = data.get("usage", {})
        tokens = {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "total": usage.get("total_tokens", 0),
        }

        logger.info(
            f"✅ GLM-5 response: {len(content)} chars, tokens={tokens['total']}"
        )
        return {
            "content": content,
            "tokens": tokens,
            "model": GLM5_MODEL,
            "stop_reason": choice.get("finish_reason", "stop"),
        }

    async def call_streaming(
        self,
        prompt: str,
        max_tokens: int = 36864,
        temperature: float = 0.8,
        timeout: float = 600.0,
    ) -> str:
        """
        Call GLM-5 with streaming - collects full response.
        Used for slide HTML generation (long outputs).
        System prompt is embedded in user prompt for slide generation.

        Returns full content string (reasoning_content skipped).
        """
        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GLM5_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        logger.info(f"🌊 GLM-5 streaming request (max_tokens={max_tokens})...")

        content = ""
        reasoning = ""

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", self.endpoint, json=payload, headers=headers
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0]["delta"]
                        # Accumulate final content separately from reasoning
                        if delta.get("content"):
                            content += delta["content"]
                        if delta.get("reasoning_content"):
                            reasoning += delta["reasoning_content"]
                    except Exception:
                        continue

        # Use final content; fall back to reasoning if content empty
        result = content if content.strip() else reasoning
        logger.info(
            f"✅ GLM-5 stream complete: content={len(content)} chars, reasoning={len(reasoning)} chars"
        )
        return result


def get_glm5_client() -> GLM5Client:
    """Get singleton GLM5Client"""
    global _glm5_client
    if _glm5_client is None:
        _glm5_client = GLM5Client()
    return _glm5_client
