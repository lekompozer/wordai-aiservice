"""
AI Content Edit Models
Data models for AI-powered content editing
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class SelectedContent(BaseModel):
    """Selected text content from editor"""

    html: str = Field(..., description="HTML content of selection")
    text: str = Field(..., description="Plain text version")
    startLine: Optional[int] = Field(None, description="Start line number")
    endLine: Optional[int] = Field(None, description="End line number")


class CurrentFile(BaseModel):
    """Current file being edited"""

    fileId: str
    fileName: str
    fileType: Literal["docx", "pdf", "txt", "md", "html"]
    fullContent: Optional[str] = Field(None, description="Entire document for context")
    filePath: Optional[str] = Field(
        None, description="File path or URL (for PDF direct upload to Gemini)"
    )


class AdditionalContext(BaseModel):
    """Additional context from other files"""

    fileId: str
    fileName: str
    content: str  # HTML or plain text
    startLine: Optional[int] = None
    endLine: Optional[int] = None
    excerpt: Optional[str] = None


class OperationParameters(BaseModel):
    """Optional parameters for specific operations"""

    tone: Optional[
        Literal["professional", "friendly", "formal", "casual", "academic"]
    ] = None
    language: Optional[Literal["vi", "en", "auto"]] = "auto"
    outputFormat: Optional[Literal["paragraph", "list", "table", "heading", "auto"]] = (
        "auto"
    )
    maxLength: Optional[int] = None
    tableColumns: Optional[List[str]] = None


class EditorContext(BaseModel):
    """Editor state context"""

    cursorPosition: int
    documentLength: int
    surroundingText: Optional[str] = None


class AIContentEditRequest(BaseModel):
    """Main request model for content editing"""

    provider: Literal["deepseek", "chatgpt", "gemini", "qwen", "cerebras"] = "deepseek"
    userQuery: str = Field(..., min_length=1, max_length=2000)
    selectedContent: SelectedContent
    currentFile: CurrentFile
    additionalContext: Optional[List[AdditionalContext]] = []
    operationType: Literal[
        "continue_writing",
        "summarize",
        "change_tone",
        "fix_grammar",
        "create_table",
        "transform_format",
        "create_structure",
        "general_edit",
        "expand_content",
        "simplify",
        "translate",
        "custom",
    ] = "general_edit"
    parameters: Optional[OperationParameters] = None
    editorContext: Optional[EditorContext] = None


class AlternativeSuggestion(BaseModel):
    """Alternative content suggestion"""

    html: str
    confidence: float = Field(..., ge=0, le=1)
    description: Optional[str] = None


class SourceAttribution(BaseModel):
    """Source file attribution"""

    fileId: str
    fileName: str
    relevance: float = Field(..., ge=0, le=1)


class ResponseMetadata(BaseModel):
    """Response metadata"""

    provider: str
    operationType: str
    processingTime: int  # milliseconds
    tokensUsed: Optional[int] = None
    model: Optional[str] = None
    contentWasTruncated: Optional[bool] = False
    pdfDirectUpload: Optional[bool] = False  # True if PDF was sent directly to Gemini


class AIContentEditResponse(BaseModel):
    """Success response model"""

    success: bool = True
    generatedHTML: str
    metadata: ResponseMetadata
    alternatives: Optional[List[AlternativeSuggestion]] = []
    warnings: Optional[List[str]] = []
    sources: Optional[List[SourceAttribution]] = []


class AIContentEditErrorResponse(BaseModel):
    """Error response model"""

    success: bool = False
    error: Dict[str, Any]
    fallback: Optional[Dict[str, str]] = None
