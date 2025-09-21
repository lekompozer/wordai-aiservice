"""
FastAPI route handlers for basic endpoints (health, status, ping)
"""

from fastapi import APIRouter
from datetime import datetime
import time
import os
from src.core.models import HealthResponse, StatusResponse
from src.providers.ai_provider_manager import AIProviderManager
from src.core.config import APP_CONFIG

router = APIRouter()

# Global variables for uptime tracking
startup_time = time.time()

@router.get("/ping")
def ping():
    """
    ✅ Simple ping endpoint to check if server is alive
    """
    return {
        "message": "pong",
        "timestamp": datetime.now().isoformat(),
        "status": "healthy"
    }

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    ✅ Comprehensive health check endpoint
    """
    current_time = time.time()
    uptime = current_time - startup_time
    
    # Check AI providers
    providers_status = {}
    
    try:
        from config.config import DEEPSEEK_API_KEY, CHATGPT_API_KEY
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY,
            chatgpt_api_key=CHATGPT_API_KEY
        )
        available_providers = await ai_manager.get_available_providers()
        for provider in available_providers:
            providers_status[provider] = {
                "status": "available",
                "last_check": datetime.now().isoformat()
            }
    except Exception as e:
        providers_status["error"] = str(e)
    
    # Database status (mock for now)
    database_status = {
        "status": "connected",
        "last_check": datetime.now().isoformat()
    }
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        environment=os.getenv("ENV", "production"),
        version="1.0.0",
        uptime=uptime,
        providers=providers_status,
        database=database_status
    )

@router.get("/status", response_model=StatusResponse)
async def status():
    """
    ✅ Basic status endpoint
    """
    uptime_seconds = time.time() - startup_time
    uptime_str = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m {int(uptime_seconds % 60)}s"
    
    return StatusResponse(
        server="AI Chatbot RAG Service",
        environment=os.getenv("ENV", "production"),
        timestamp=datetime.now().isoformat(),
        uptime=uptime_str
    )
