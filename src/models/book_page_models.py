"""
Pydantic models for Book Page Text & Audio API

Collections:
  book_page_texts  — per-page text + image data (crawled from LetsRead)
  book_page_audio  — generated TTS audio (per book × voice)

Endpoints covered:
  POST   /api/v1/books/{book_id}/pages/batch           → BatchSavePagesRequest
  GET    /api/v1/books/{book_id}/pages                 → BookPagesResponse
  POST   /api/v1/books/{book_id}/audio/generate        → AudioGenerateRequest
  GET    /api/v1/books/{book_id}/audio/generate/status/{job_id}
  GET    /api/v1/books/{book_id}/audio?voice=aoede     → BookAudioResponse
  DELETE /api/v1/books/{book_id}/audio/{voice}
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class AudioJobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Page models
# ---------------------------------------------------------------------------


class BookPage(BaseModel):
    """Single page of a book (text + image)."""

    page_number: int = Field(
        ..., description="1-based story page number (cover excluded)"
    )
    text_content: str = Field(default="", description="Page story text")
    image_url: str = Field(default="", description="Primary image URL (GCS)")
    image_url_cdn: Optional[str] = Field(None, description="CDN image URL (hamropatro)")
    image_url_hires: Optional[str] = Field(None, description="High-res image URL")
    image_name: Optional[str] = Field(None, description="Image filename")
    image_width: Optional[int] = Field(None, description="Image width in px")
    image_height: Optional[int] = Field(None, description="Image height in px")
    has_audio: bool = Field(default=False, description="Whether native audio exists")
    letsread_page_id: Optional[Union[str, int]] = Field(None, description="Native LetsRead page ID")

    class Config:
        from_attributes = True


class BatchSavePagesRequest(BaseModel):
    """
    Request body for POST /books/{book_id}/pages/batch

    Used by admin scripts / crawler to store page data.
    """

    letsread_book_id: str = Field(..., description="LetsRead masterBookId UUID")
    letsread_lang_id: str = Field(
        default="4846240843956224", description="LetsRead language ID"
    )
    language: str = Field(default="en", description="ISO language code")
    pages: List[BookPage] = Field(..., description="List of page objects")
    force: bool = Field(default=False, description="Overwrite existing pages if True")


class BatchSavePagesResponse(BaseModel):
    """Response from POST /books/{book_id}/pages/batch"""

    book_id: str
    letsread_book_id: str
    saved: int = Field(..., description="Number of pages saved / updated")
    total: int = Field(..., description="Total pages in request")
    message: str


class BookPagesResponse(BaseModel):
    """Response from GET /books/{book_id}/pages"""

    book_id: str
    total_pages: int
    language: str = "en"
    pages: List[BookPage]


# ---------------------------------------------------------------------------
# Audio job models
# ---------------------------------------------------------------------------


class AudioGenerateRequest(BaseModel):
    """Request body for POST /books/{book_id}/audio/generate"""

    voice: str = Field(
        default="auto",
        description=(
            "Voice name (e.g. 'Aoede', 'Algenib') or 'auto' to use the "
            "deterministic default for this book."
        ),
    )
    language: str = Field(default="en", description="ISO language code")
    force_regenerate: bool = Field(
        default=False,
        description="Delete existing audio and regenerate from scratch",
    )
    use_pro_model: bool = Field(
        default=False,
        description="Use gemini-2.5-pro-preview-tts instead of flash (slower, higher quality)",
    )


class AudioGenerateResponse(BaseModel):
    """Response from POST /books/{book_id}/audio/generate"""

    job_id: str
    book_id: str
    voice: str
    status: AudioJobStatus = AudioJobStatus.PENDING
    message: str
    total_pages: int
    estimated_time: str = "30-120 seconds"


class AudioJobStatusResponse(BaseModel):
    """Response from GET /books/{book_id}/audio/generate/status/{job_id}"""

    job_id: str
    book_id: str
    status: AudioJobStatus
    voice: Optional[str] = None
    progress: Optional[Dict[str, int]] = Field(
        None,
        description="E.g. {'done': 5, 'total': 14}",
    )
    audio_url: Optional[str] = Field(
        None, description="Final merged audio URL (set when status=completed)"
    )
    total_duration_seconds: Optional[float] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Page timestamp model (for frontend playback sync)
# ---------------------------------------------------------------------------


class PageTimestamp(BaseModel):
    """Audio timestamp for a single page."""

    page_number: int
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    duration: float = Field(..., description="Duration in seconds")


# ---------------------------------------------------------------------------
# Book audio response (MAIN frontend endpoint)
# ---------------------------------------------------------------------------


class BookAudioResponse(BaseModel):
    """
    Response from GET /books/{book_id}/audio?voice=aoede

    This is the primary endpoint the frontend uses for playback:
      1. Load audio_url into <audio> tag
      2. On timeupdate: binary search page_timestamps to find current page
      3. Display page image + text at page_timestamps[i].page_number
    """

    book_id: str
    voice: str
    version: int
    status: AudioJobStatus

    # Main audio URL (merged WAV from R2 CDN)
    audio_url: Optional[str] = None

    total_duration_seconds: Optional[float] = None
    total_pages: Optional[int] = None

    # Per-page timestamps for frontend sync
    page_timestamps: List[PageTimestamp] = Field(default_factory=list)

    # Book page data (optional, for combined response)
    pages: Optional[List[BookPage]] = None

    generated_at: Optional[str] = None
    model: Optional[str] = None


class DeleteAudioResponse(BaseModel):
    """Response from DELETE /books/{book_id}/audio/{voice}"""

    book_id: str
    voice: str
    deleted: bool
    message: str
