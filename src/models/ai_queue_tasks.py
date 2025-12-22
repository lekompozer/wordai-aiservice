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

    # Slide-specific fields (for format type with slides)
    slide_index: Optional[int] = Field(None, description="Slide index (for slides)")
    elements: Optional[list] = Field(
        None, description="Slide elements (shapes, images, videos, text boxes)"
    )
    background: Optional[dict] = Field(
        None, description="Slide background (color, gradient, image)"
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


class SlideFormatTask(BaseModel):
    """Task for Slide AI Format queue - single slide processing"""

    task_id: str = Field(..., description="Unique task ID (same as job_id)")
    job_id: str = Field(..., description="Job ID for status tracking")
    user_id: str = Field(..., description="User ID")
    slide_index: int = Field(..., description="Slide index")
    current_html: str = Field(..., description="Current slide HTML")
    elements: list = Field(..., description="Current slide elements")
    background: dict = Field(..., description="Current slide background")
    user_instruction: Optional[str] = Field(None, description="User instruction")
    format_type: str = Field(..., description="'format' or 'edit'")

    # Batch tracking (if part of multi-slide job)
    is_batch: bool = Field(default=False, description="True if part of batch job")
    batch_job_id: Optional[str] = Field(None, description="Parent batch job ID")
    total_slides: Optional[int] = Field(None, description="Total slides in batch")
    slide_position: Optional[int] = Field(
        None, description="Position in batch (0-based)"
    )

    # Task metadata
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    priority: int = Field(default=1)
    max_retries: int = Field(default=3)
    retry_count: int = Field(default=0)


class ChapterTranslationTask(BaseModel):
    """Task for Chapter Translation queue"""

    task_id: str = Field(..., description="Unique task ID (same as job_id)")
    job_id: str = Field(..., description="Job ID for status tracking")
    user_id: str = Field(..., description="User ID")
    book_id: str = Field(..., description="Book ID")
    chapter_id: str = Field(..., description="Chapter ID to translate")
    source_language: str = Field(..., description="Source language")
    target_language: str = Field(..., description="Target language")
    content_html: str = Field(..., description="HTML content to translate")
    create_new_chapter: bool = Field(
        default=False, description="Create new chapter with translation"
    )
    new_chapter_title_suffix: Optional[str] = Field(
        None, description="Suffix for new chapter title"
    )

    # Task metadata
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    priority: int = Field(default=1)
    max_retries: int = Field(default=3)
    retry_count: int = Field(default=0)


class TranslationTask(BaseModel):
    """Task for Book Translation queue (full book translation job)"""

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
