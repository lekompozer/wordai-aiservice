"""
AI Queue Task Models
Pydantic models for AI tasks in Redis queue
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AIEditorTask(BaseModel):
    """Task for AI Editor queue (Edit/Format/Bilingual operations)"""

    task_id: str = Field(..., description="Unique task ID (same as job_id in MongoDB)")
    job_id: str = Field(..., description="Job ID for status tracking in MongoDB")
    user_id: str = Field(..., description="User ID who requested the task")
    document_id: str = Field(..., description="Document or chapter ID")
    job_type: str = Field(..., description="'edit', 'format', or 'bilingual'")
    content_type: str = Field(..., description="'document', 'slide', 'chapter', etc.")
    content: str = Field(..., description="HTML content to process")
    user_query: Optional[str] = Field(None, description="User instruction/prompt")

    # Bilingual-specific fields
    source_language: Optional[str] = Field(
        None, description="Source language for bilingual"
    )
    target_language: Optional[str] = Field(
        None, description="Target language for bilingual"
    )
    bilingual_style: Optional[str] = Field(
        None, description="'slash_separated' or 'line_break'"
    )

    # Task metadata
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    priority: int = Field(default=1, description="1=normal, 2=high, 3=urgent")
    max_retries: int = Field(default=3)
    retry_count: int = Field(default=0)


class SlideGenerationTask(BaseModel):
    """Task for Slide Generation queue"""

    task_id: str = Field(..., description="Unique task ID")
    document_id: str = Field(..., description="Slide document ID")
    user_id: str = Field(..., description="User ID")
    step: int = Field(..., description="Generation step (1 or 2)")

    # Step 1: Analysis
    outline: Optional[str] = Field(None, description="Slide outline (for step 1)")

    # Step 2: HTML Generation
    analysis_id: Optional[str] = Field(
        None, description="Analysis ID from step 1 (for step 2)"
    )

    # Task metadata
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    priority: int = Field(default=1)
    max_retries: int = Field(default=3)
    retry_count: int = Field(default=0)


class TranslationTask(BaseModel):
    """Task for Translation queue"""

    task_id: str = Field(..., description="Unique task ID")
    job_id: str = Field(..., description="Translation job ID")
    book_id: str = Field(..., description="Book ID to translate")
    user_id: str = Field(..., description="User ID")
    target_language: str = Field(..., description="Target language")
    source_language: str = Field(..., description="Source language")
    preserve_background: bool = Field(default=True)
    custom_background: Optional[str] = Field(None)

    # Task metadata
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    priority: int = Field(default=1)
    max_retries: int = Field(default=2, description="Lower retries for translation")
    retry_count: int = Field(default=0)
