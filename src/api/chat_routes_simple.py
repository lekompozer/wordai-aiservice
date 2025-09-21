"""
Chat API Routes - Simple Version
API endpoints for AI chat with streaming support
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

# Simple router first
router = APIRouter(tags=["chat"])


# Basic Pydantic Models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None


class ProvidersResponse(BaseModel):
    providers: List[Dict[str, Any]]
    total: int


@router.get("/providers")
async def get_available_providers():
    """Get list of available AI providers"""

    providers = [
        {
            "id": "openai",
            "name": "GPT-4o",
            "description": "OpenAI GPT-4o - Advanced reasoning and multimodal",
            "category": "general",
            "available": True,
        }
    ]

    return ProvidersResponse(providers=providers, total=len(providers))


@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify chat routes work"""
    return {"message": "Chat routes working!", "timestamp": datetime.now()}
