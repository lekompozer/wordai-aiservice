"""
Pydantic models for Slide Narration API
2-step flow: Subtitles (2 points) → Audio (2 points)
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================================
# STEP 1: SUBTITLE GENERATION
# ============================================================


class SubtitleEntry(BaseModel):
    """Single subtitle entry with timing and element references"""

    subtitle_index: int = Field(..., description="Index within slide")
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    duration: float = Field(..., description="Duration in seconds")
    text: str = Field(..., description="Subtitle text")
    speaker_index: int = Field(0, description="Speaker index (for multi-voice)")
    element_references: List[str] = Field(
        default_factory=list, description="Element IDs referenced in this subtitle"
    )


class SlideSubtitleData(BaseModel):
    """Subtitle data for one slide"""

    slide_index: int = Field(..., description="Slide index")
    slide_duration: float = Field(..., description="Total slide duration in seconds")
    subtitles: List[SubtitleEntry] = Field(..., description="List of subtitles")
    auto_advance: bool = Field(True, description="Auto-advance to next slide")
    transition_delay: float = Field(2.0, description="Delay before advancing (seconds)")


class SubtitleGenerateRequest(BaseModel):
    """Request to generate subtitles for presentation"""

    presentation_id: str = Field(..., description="Presentation ID")
    mode: str = Field(..., description="Narration mode: 'presentation' or 'academy'")
    language: str = Field(..., description="Language code: 'vi', 'en', 'zh'")
    user_query: str = Field("", description="User instructions for narration style")

    class Config:
        json_schema_extra = {
            "example": {
                "presentation_id": "507f1f77bcf86cd799439011",
                "mode": "presentation",
                "language": "vi",
                "user_query": "Focus on key benefits, keep it concise",
            }
        }


class SubtitleGenerateResponse(BaseModel):
    """Response with generated subtitles"""

    success: bool = Field(..., description="Success status")
    narration_id: str = Field(..., description="Generated narration ID")
    version: int = Field(..., description="Version number")
    slides: List[SlideSubtitleData] = Field(..., description="Slides with subtitles")
    total_duration: float = Field(
        ..., description="Total presentation duration (seconds)"
    )
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    points_deducted: int = Field(2, description="Points deducted (always 2)")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "narration_id": "507f1f77bcf86cd799439099",
                "version": 1,
                "slides": [
                    {
                        "slide_index": 0,
                        "slide_duration": 15.5,
                        "subtitles": [
                            {
                                "subtitle_index": 0,
                                "start_time": 0.0,
                                "end_time": 3.5,
                                "duration": 3.5,
                                "text": "Chào mừng đến với bài thuyết trình này.",
                                "speaker_index": 0,
                                "element_references": [],
                            },
                            {
                                "subtitle_index": 1,
                                "start_time": 4.0,
                                "end_time": 8.2,
                                "duration": 4.2,
                                "text": "Như bạn thấy trong biểu đồ, quy trình có ba giai đoạn chính.",
                                "speaker_index": 0,
                                "element_references": ["elem_0"],
                            },
                        ],
                        "auto_advance": True,
                        "transition_delay": 2.0,
                    }
                ],
                "total_duration": 45.8,
                "processing_time_ms": 3200,
                "points_deducted": 2,
            }
        }


# ============================================================
# STEP 2: AUDIO GENERATION
# ============================================================


class VoiceConfig(BaseModel):
    """Voice configuration for audio generation"""

    provider: str = Field(
        "google", description="TTS provider: 'google', 'openai', 'elevenlabs'"
    )
    voices: List[Dict[str, Any]] = Field(
        ..., description="List of voice configurations"
    )
    use_pro_model: bool = Field(True, description="Use premium voice model")

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "google",
                "voices": [
                    {
                        "voice_name": "vi-VN-Neural2-A",
                        "language": "vi-VN",
                        "speaking_rate": 1.0,
                        "pitch": 0.0,
                    }
                ],
                "use_pro_model": True,
            }
        }


class AudioGenerateRequest(BaseModel):
    """Request to generate audio from subtitles"""

    narration_id: str = Field(..., description="Narration ID from Step 1")
    voice_config: VoiceConfig = Field(..., description="Voice configuration")

    class Config:
        json_schema_extra = {
            "example": {
                "narration_id": "507f1f77bcf86cd799439099",
                "voice_config": {
                    "provider": "google",
                    "voices": [
                        {
                            "voice_name": "vi-VN-Neural2-A",
                            "language": "vi-VN",
                            "speaking_rate": 1.0,
                        }
                    ],
                    "use_pro_model": True,
                },
            }
        }


class AudioFile(BaseModel):
    """Audio file metadata"""

    slide_index: int = Field(..., description="Slide index")
    audio_url: str = Field(..., description="R2 CDN URL")
    library_audio_id: str = Field(..., description="Library audio record ID")
    file_size: int = Field(..., description="File size in bytes")
    format: str = Field("mp3", description="Audio format")
    duration: float = Field(..., description="Duration in seconds")
    speaker_count: int = Field(1, description="Number of speakers")


class AudioGenerateResponse(BaseModel):
    """Response with generated audio files"""

    success: bool = Field(..., description="Success status")
    narration_id: str = Field(..., description="Narration ID")
    audio_files: List[AudioFile] = Field(..., description="Generated audio files")
    total_duration: float = Field(..., description="Total audio duration (seconds)")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    points_deducted: int = Field(2, description="Points deducted (always 2)")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "narration_id": "507f1f77bcf86cd799439099",
                "audio_files": [
                    {
                        "slide_index": 0,
                        "audio_url": "https://cdn.r2.com/narr_507f_slide_0.mp3",
                        "library_audio_id": "507f1f77bcf86cd799439088",
                        "file_size": 245678,
                        "format": "mp3",
                        "duration": 15.5,
                        "speaker_count": 1,
                    }
                ],
                "total_duration": 45.8,
                "processing_time_ms": 8500,
                "points_deducted": 2,
            }
        }


# ============================================================
# CRUD OPERATIONS
# ============================================================


class NarrationDetailResponse(BaseModel):
    """Detailed narration response (for GET by ID)"""

    success: bool = Field(True, description="Success status")
    narration_id: str = Field(..., description="Narration ID")
    presentation_id: str = Field(..., description="Presentation ID")
    version: int = Field(..., description="Version number")
    status: str = Field(..., description="Status")
    mode: str = Field(..., description="Narration mode")
    language: str = Field(..., description="Language code")
    user_query: str = Field("", description="User instructions")
    slides: List[SlideSubtitleData] = Field(..., description="Slides with subtitles")
    audio_files: List["AudioFile"] = Field(
        default_factory=list, description="Audio files (if generated)"
    )
    voice_config: Optional[VoiceConfig] = Field(
        None, description="Voice config (if audio generated)"
    )
    total_duration: float = Field(..., description="Total duration (seconds)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class UpdateSubtitlesRequest(BaseModel):
    """Request to update subtitles before audio generation"""

    slides: List[SlideSubtitleData] = Field(
        ..., description="Updated slides with subtitles"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "slides": [
                    {
                        "slide_index": 0,
                        "slide_duration": 15.5,
                        "subtitles": [
                            {
                                "subtitle_index": 0,
                                "start_time": 0.0,
                                "end_time": 3.5,
                                "duration": 3.5,
                                "text": "Chào mừng đến với bài thuyết trình này.",
                                "speaker_index": 0,
                                "element_references": [],
                            }
                        ],
                        "auto_advance": True,
                        "transition_delay": 2.0,
                    }
                ]
            }
        }


class UpdateSubtitlesResponse(BaseModel):
    """Response after updating subtitles"""

    success: bool = Field(True, description="Success status")
    narration_id: str = Field(..., description="Narration ID")
    slides: List[SlideSubtitleData] = Field(..., description="Updated slides")
    total_duration: float = Field(..., description="Recalculated total duration")
    updated_at: datetime = Field(..., description="Update timestamp")


class DeleteNarrationResponse(BaseModel):
    """Response after deleting narration"""

    success: bool = Field(True, description="Success status")
    narration_id: str = Field(..., description="Deleted narration ID")
    message: str = Field(..., description="Confirmation message")


# ============================================================
# VERSION MANAGEMENT
# ============================================================


class NarrationVersion(BaseModel):
    """Narration version metadata"""

    narration_id: str = Field(..., description="Narration ID")
    version: int = Field(..., description="Version number")
    status: str = Field(
        ..., description="Status: 'subtitles_only', 'completed', 'failed'"
    )
    mode: str = Field(..., description="Narration mode")
    language: str = Field(..., description="Language code")
    total_duration: float = Field(..., description="Total duration (seconds)")
    created_at: datetime = Field(..., description="Creation timestamp")
    audio_ready: bool = Field(False, description="Audio generation completed")


class NarrationListResponse(BaseModel):
    """List of narration versions"""

    success: bool = Field(True, description="Success status")
    narrations: List[NarrationVersion] = Field(
        ..., description="List of narration versions"
    )
    total_count: int = Field(..., description="Total number of narrations")


# ============================================================
# LIBRARY AUDIO INTEGRATION
# ============================================================


class LibraryAudioItem(BaseModel):
    """Library audio item metadata"""

    audio_id: str = Field(..., description="Library audio ID")
    file_name: str = Field(..., description="Audio file name")
    r2_url: str = Field(..., description="R2 CDN URL")
    duration: float = Field(..., description="Duration in seconds")
    file_size: int = Field(..., description="File size in bytes")
    format: str = Field("mp3", description="Audio format")
    source_type: str = Field(
        ..., description="Source type (slide_narration, listening_test, upload)"
    )
    created_at: datetime = Field(..., description="Upload timestamp")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class AssignAudioRequest(BaseModel):
    """Request to assign library audio to slides"""

    audio_assignments: List[Dict[str, Any]] = Field(
        ..., description="Audio assignments for slides"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "audio_assignments": [
                    {
                        "slide_index": 0,
                        "library_audio_id": "507f1f77bcf86cd799439088",
                    },
                    {
                        "slide_index": 1,
                        "library_audio_id": "507f1f77bcf86cd799439089",
                    },
                ]
            }
        }


class AssignAudioResponse(BaseModel):
    """Response after assigning audio"""

    success: bool = Field(True, description="Success status")
    narration_id: str = Field(..., description="Narration ID")
    audio_files: List[AudioFile] = Field(..., description="Updated audio files")
    message: str = Field(..., description="Success message")


class LibraryAudioListRequest(BaseModel):
    """Request to list library audio files"""

    source_type: Optional[str] = Field(None, description="Filter by source type")
    search_query: Optional[str] = Field(None, description="Search in file names")
    limit: int = Field(50, description="Max results", ge=1, le=100)
    offset: int = Field(0, description="Pagination offset", ge=0)


class LibraryAudioListResponse(BaseModel):
    """Response with library audio files"""

    success: bool = Field(True, description="Success status")
    audio_files: List[LibraryAudioItem] = Field(..., description="List of audio files")
    total_count: int = Field(..., description="Total number of files")
    has_more: bool = Field(..., description="More results available")
