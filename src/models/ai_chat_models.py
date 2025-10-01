"""
AI Chat Models
Data models for AI-powered chat with file context (streaming)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class ChatSelectedContent(BaseModel):
    """Selected text content from file"""
    text: str = Field(..., description="Plain text of selection")
    startLine: Optional[int] = Field(None, description="Start line number")
    endLine: Optional[int] = Field(None, description="End line number")


class ChatFileContext(BaseModel):
    """File context for chat"""
    fileId: str
    fileName: str
    fileType: Literal['docx', 'pdf', 'txt', 'md', 'html']
    fullContent: Optional[str] = Field(None, description="Full file content as text")
    filePath: Optional[str] = Field(None, description="File path or URL (for PDF with Gemini)")


class ChatAdditionalContext(BaseModel):
    """Additional context from other files"""
    fileId: str
    fileName: str
    content: str  # Plain text content
    startLine: Optional[int] = None
    endLine: Optional[int] = None


class AIChatRequest(BaseModel):
    """Request for AI chat with file context"""
    
    # AI Provider (required)
    provider: Literal['deepseek', 'chatgpt', 'gemini', 'qwen', 'cerebras']
    
    # User's message (required)
    userMessage: str = Field(..., description="User's chat message/question")
    
    # Selected content from file (optional)
    selectedContent: Optional[ChatSelectedContent] = None
    
    # Current file context (optional)
    currentFile: Optional[ChatFileContext] = None
    
    # Additional context files (optional)
    additionalContext: Optional[List[ChatAdditionalContext]] = None
    
    # Conversation history (optional)
    conversationHistory: Optional[List[dict]] = Field(
        None,
        description="Previous messages [{'role': 'user'|'assistant', 'content': '...'}]"
    )
    
    # Stream response (default: True)
    stream: bool = Field(True, description="Stream response or return all at once")


class AIChatChunk(BaseModel):
    """Streaming chat response chunk"""
    chunk: str = Field(..., description="Text chunk from AI")
    done: bool = Field(False, description="Whether this is the final chunk")
    metadata: Optional[dict] = Field(None, description="Metadata (only in final chunk)")


class AIChatResponse(BaseModel):
    """Complete chat response (non-streaming)"""
    success: bool = True
    response: str = Field(..., description="Complete AI response text")
    metadata: dict = Field(..., description="Response metadata")


class AIChatErrorResponse(BaseModel):
    """Error response for chat"""
    success: bool = False
    error: dict
