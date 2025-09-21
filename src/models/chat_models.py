"""
💬 CHAT MODELS
Models cho chat và file processing
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class QuestionRequest(BaseModel):
    """Basic question request"""
    question: str
    userId: Optional[str] = None
    deviceId: Optional[str] = None

class ChatWithFilesRequest(BaseModel):
    """Chat request với files đính kèm"""
    question: str
    userId: Optional[str] = None
    deviceId: Optional[str] = None
    files: Optional[List[Dict[str, Any]]] = None
    context: Optional[str] = None
    ai_provider: Optional[str] = "deepseek"
    use_backend_ocr: Optional[bool] = True
    url_image: Optional[str] = None