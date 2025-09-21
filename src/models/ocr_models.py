"""
📸 OCR MODELS
Models cho CCCD OCR và document processing
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class CCCDImageRequest(BaseModel):
    """Request model cho CCCD OCR"""
    images: List[Dict[str, Any]]  # [{"url": "...", "type": "front/back", "fileName": "..."}]
    requestId: Optional[str] = None
    userId: Optional[str] = None

class CCCDOCRResponse(BaseModel):
    """Response model cho CCCD OCR"""
    success: bool
    requestId: Optional[str] = None
    extractedData: Optional[Dict[str, Any]] = None
    processingDetails: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class OCRRequest(BaseModel):
    """Request model cho general OCR"""
    files: Optional[List[Dict[str, Any]]] = None