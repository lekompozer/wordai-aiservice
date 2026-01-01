"""
Video Export Models
Pydantic models for video export jobs and requests
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class VideoQuality(str, Enum):
    """Video quality presets"""

    LOW = "low"  # CRF 30, ~400 kbps, ~60 MB @ 15 min
    MEDIUM = "medium"  # CRF 28, ~500 kbps, ~76 MB @ 15 min (default)
    HIGH = "high"  # CRF 26, ~700 kbps, ~95 MB @ 15 min


class VideoResolution(str, Enum):
    """Video resolution options"""

    HD_720 = "720p"  # 1280x720
    FULL_HD_1080 = "1080p"  # 1920x1080 (default)
    UHD_4K = "4k"  # 3840x2160 (not recommended - huge files)


class ExportStatus(str, Enum):
    """Export job status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportPhase(str, Enum):
    """Current processing phase"""

    LOAD = "load"  # Loading presentation data
    SCREENSHOT = "screenshot"  # Capturing slides
    ENCODE = "encode"  # FFmpeg processing
    UPLOAD = "upload"  # Uploading to S3


class ExportMode(str, Enum):
    """Export mode (affects file size and quality)"""

    OPTIMIZED = "optimized"  # Static slideshow (~48 MB, 2.5 min generation)
    ANIMATED = "animated"  # 5s animation intro per slide (~61 MB, 8 min generation)


class VideoExportRequest(BaseModel):
    """Request model for video export"""

    language: str = Field(
        default="vi",
        description="Language code for narration (vi/en/ja/etc)",
        pattern="^[a-z]{2}$",
    )
    export_mode: ExportMode = Field(
        default=ExportMode.OPTIMIZED,
        description="Export mode: optimized (48MB, fast) or animated (61MB, quality)",
    )
    resolution: VideoResolution = Field(
        default=VideoResolution.FULL_HD_1080,
        description="Video resolution (720p/1080p/4k)",
    )
    quality: VideoQuality = Field(
        default=VideoQuality.MEDIUM, description="Video quality preset"
    )
    include_subtitles: bool = Field(
        default=False, description="Embed subtitles in video (future feature)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "language": "vi",
                "export_mode": "optimized",
                "resolution": "1080p",
                "quality": "medium",
                "include_subtitles": False,
            }
        }


class VideoExportSettings(BaseModel):
    """Video export settings (internal)"""

    # Export mode
    export_mode: ExportMode

    # Video settings
    resolution: VideoResolution
    width: int  # Calculated from resolution
    height: int
    fps: int  # 24 FPS for static, 30 FPS for animated
    crf: int  # Constant Rate Factor (quality) - calculated from quality preset
    preset: str = "medium"  # FFmpeg preset (fast/medium/slow)

    # Audio settings
    audio_bitrate: str = "192k"  # AAC audio bitrate
    audio_codec: str = "aac"

    # Compression settings
    video_codec: str = "libx264"
    pix_fmt: str = "yuv420p"  # Compatibility
    fade_duration: float = 0.5  # Transition duration (seconds)

    @staticmethod
    def from_request(request: VideoExportRequest) -> "VideoExportSettings":
        """Create settings from request"""
        # Resolution mapping
        resolution_map = {
            VideoResolution.HD_720: (1280, 720),
            VideoResolution.FULL_HD_1080: (1920, 1080),
            VideoResolution.UHD_4K: (3840, 2160),
        }

        # Quality mapping (CRF values)
        # Lower CRF for static (better compression), higher for animated
        if request.export_mode == ExportMode.OPTIMIZED:
            quality_map = {
                VideoQuality.LOW: 30,
                VideoQuality.MEDIUM: 28,
                VideoQuality.HIGH: 26,
            }
            fps = 24
        else:  # ANIMATED
            quality_map = {
                VideoQuality.LOW: 28,
                VideoQuality.MEDIUM: 25,
                VideoQuality.HIGH: 23,
            }
            fps = 30

        width, height = resolution_map[request.resolution]
        crf = quality_map[request.quality]

        return VideoExportSettings(
            export_mode=request.export_mode,
            resolution=request.resolution,
            width=width,
            height=height,
            fps=fps,
            crf=crf,
            preset="medium",
            audio_bitrate="192k" if request.quality != VideoQuality.LOW else "128k",
            audio_codec="aac",
            video_codec="libx264",
            pix_fmt="yuv420p",
            fade_duration=0.5,
        )


class VideoExportJob(BaseModel):
    """Video export job document (MongoDB)"""

    job_id: str = Field(..., description="Unique job ID")
    presentation_id: str = Field(..., description="Presentation document ID")
    user_id: str = Field(..., description="User ID")
    language: str = Field(..., description="Language code")

    # Settings
    settings: Dict[str, Any] = Field(
        ..., description="Export settings (resolution, quality, etc)"
    )

    # Status tracking
    status: ExportStatus = Field(default=ExportStatus.PENDING)
    progress: int = Field(default=0, ge=0, le=100, description="Progress 0-100%")
    current_phase: Optional[ExportPhase] = Field(None, description="Current phase")

    # Output
    output_url: Optional[str] = Field(None, description="S3/R2 download URL")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    duration: Optional[float] = Field(None, description="Video duration in seconds")

    # Error handling
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Number of retries")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # Auto-delete after 7 days

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "export_12345",
                "presentation_id": "doc_abc123",
                "user_id": "user_xyz",
                "language": "vi",
                "settings": {
                    "resolution": "1080p",
                    "quality": "medium",
                    "fps": 24,
                    "crf": 28,
                },
                "status": "processing",
                "progress": 45,
                "current_phase": "encode",
                "output_url": None,
                "created_at": "2026-01-01T10:00:00Z",
            }
        }


class VideoExportJobResponse(BaseModel):
    """API response for job status"""

    job_id: str
    status: ExportStatus
    progress: int
    current_phase: Optional[ExportPhase] = None

    # Output (only when completed)
    download_url: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None

    # Error (only when failed)
    error: Optional[str] = None

    # Metadata
    presentation_id: str
    language: str
    export_mode: Optional[str] = None
    estimated_size_mb: Optional[int] = None
    created_at: datetime
    estimated_time_remaining: Optional[int] = Field(
        None, description="Estimated seconds remaining"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "export_12345",
                "status": "processing",
                "progress": 65,
                "current_phase": "encode",
                "download_url": None,
                "file_size": None,
                "duration": None,
                "error": None,
                "presentation_id": "doc_abc123",
                "language": "vi",
                "created_at": "2026-01-01T10:00:00Z",
                "estimated_time_remaining": 25,
            }
        }


class VideoExportCreateResponse(BaseModel):
    """Response when creating export job"""

    job_id: str = Field(..., description="Job ID for polling")
    status: ExportStatus = Field(default=ExportStatus.PENDING)
    message: str = Field(default="Export job created successfully")
    polling_url: str = Field(..., description="URL to poll for status")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "export_12345",
                "status": "pending",
                "message": "Export job created successfully",
                "polling_url": "/api/export-jobs/export_12345",
            }
        }
