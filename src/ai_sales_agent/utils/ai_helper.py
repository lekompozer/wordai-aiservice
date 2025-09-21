"""
Helper function to get AI response from provider manager
"""

from src.providers.ai_provider_manager import AIProviderManager
from src.core.config import APP_CONFIG

# Global AI provider manager instance
_ai_manager = None

def get_ai_provider_manager():
    """Get or create AI provider manager instance"""
    global _ai_manager
    
    if _ai_manager is None:
        try:
            _ai_manager = AIProviderManager(
                deepseek_api_key=APP_CONFIG.get('deepseek_api_key', ''),
                chatgpt_api_key=APP_CONFIG.get('chatgpt_api_key', '')
            )
        except Exception as e:
            print(f"Failed to initialize AI provider manager: {e}")
            return None
    
    return _ai_manager

async def get_ai_response(prompt: str, provider: str = "deepseek") -> str:
    """Get AI response from specified provider"""
    
    ai_manager = get_ai_provider_manager()
    if not ai_manager:
        raise Exception("AI provider manager not available")
    
    try:
        messages = [{"role": "user", "content": prompt}]
        return await ai_manager.chat_completion(messages, provider)
    except Exception as e:
        raise Exception(f"AI response failed: {str(e)}")

async def get_ai_response_stream(prompt: str, provider: str = "deepseek"):
    """Get streaming AI response from specified provider"""
    
    ai_manager = get_ai_provider_manager()
    if not ai_manager:
        raise Exception("AI provider manager not available")
    
    try:
        messages = [{"role": "user", "content": prompt}]
        async for chunk in ai_manager.chat_completion_stream(messages, provider):
            yield chunk
    except Exception as e:
        yield f"AI stream failed: {str(e)}"
