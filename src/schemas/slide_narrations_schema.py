"""
MongoDB Schema for slide_narrations collection
Created: 2025

INDEXES:
1. {presentation_id: 1, user_id: 1} - Query by presentation and user
2. {presentation_id: 1, version: -1} - Get latest version
3. {user_id: 1, created_at: -1} - User's narrations sorted by date
4. {status: 1, created_at: -1} - Filter by status
"""

from pymongo import IndexModel, ASCENDING, DESCENDING


COLLECTION_NAME = "slide_narrations"


# Schema definition (for documentation)
SCHEMA = {
    "_id": "ObjectId - Primary key",
    "presentation_id": "ObjectId - Reference to presentations collection",
    "user_id": "ObjectId - Reference to users collection",
    "version": "int - Version number (starts at 1, increments each regeneration)",
    "status": "str - Status: 'subtitles_only', 'completed', 'failed'",
    "mode": "str - Narration mode: 'presentation' or 'academy'",
    "language": "str - Language code: 'vi', 'en', 'zh'",
    "user_query": "str - User instructions for narration",
    "slides": [
        {
            "slide_index": "int - Slide index",
            "slide_duration": "float - Total slide duration in seconds",
            "subtitles": [
                {
                    "subtitle_index": "int - Subtitle index within slide",
                    "start_time": "float - Start time in seconds",
                    "end_time": "float - End time in seconds",
                    "duration": "float - Duration in seconds",
                    "text": "str - Subtitle text",
                    "speaker_index": "int - Speaker index (0 for single speaker)",
                    "element_references": ["str - Element IDs referenced"],
                }
            ],
            "auto_advance": "bool - Auto-advance to next slide",
            "transition_delay": "float - Delay before advancing (seconds)",
        }
    ],
    "audio_files": [
        {
            "slide_index": "int - Slide index",
            "audio_url": "str - R2 CDN URL",
            "library_audio_id": "str - Reference to library_audio collection",
            "file_size": "int - File size in bytes",
            "format": "str - Audio format (mp3)",
            "duration": "float - Duration in seconds",
            "speaker_count": "int - Number of speakers",
        }
    ],
    "voice_config": {
        "provider": "str - TTS provider: 'google', 'openai', 'elevenlabs'",
        "voices": [
            {
                "voice_name": "str - Voice ID",
                "language": "str - Language code",
                "speaking_rate": "float - Speaking rate (0.5-2.0)",
                "pitch": "float - Voice pitch (-20.0 to 20.0)",
            }
        ],
        "use_pro_model": "bool - Use premium voice model",
    },
    "total_duration": "float - Total presentation duration in seconds",
    "created_at": "datetime - Creation timestamp",
    "updated_at": "datetime - Last update timestamp",
}


# Indexes
INDEXES = [
    # Query by presentation and user
    IndexModel(
        [("presentation_id", ASCENDING), ("user_id", ASCENDING)],
        name="presentation_user_idx",
    ),
    # Get latest version for presentation
    IndexModel(
        [("presentation_id", ASCENDING), ("version", DESCENDING)],
        name="presentation_version_idx",
    ),
    # User's narrations sorted by date
    IndexModel(
        [("user_id", ASCENDING), ("created_at", DESCENDING)],
        name="user_created_idx",
    ),
    # Filter by status
    IndexModel(
        [("status", ASCENDING), ("created_at", DESCENDING)],
        name="status_created_idx",
    ),
]


async def create_indexes(db):
    """Create all indexes for slide_narrations collection"""
    collection = db[COLLECTION_NAME]
    await collection.create_indexes(INDEXES)
    print(f"✅ Created {len(INDEXES)} indexes for {COLLECTION_NAME}")


# Example documents
EXAMPLE_SUBTITLES_ONLY = {
    "presentation_id": "ObjectId('507f1f77bcf86cd799439011')",
    "user_id": "ObjectId('507f1f77bcf86cd799439022')",
    "version": 1,
    "status": "subtitles_only",
    "mode": "presentation",
    "language": "vi",
    "user_query": "Make it engaging and concise",
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
    "audio_files": [],
    "voice_config": {},
    "total_duration": 45.8,
    "created_at": "datetime.now()",
    "updated_at": "datetime.now()",
}


EXAMPLE_COMPLETED = {
    "presentation_id": "ObjectId('507f1f77bcf86cd799439011')",
    "user_id": "ObjectId('507f1f77bcf86cd799439022')",
    "version": 1,
    "status": "completed",
    "mode": "presentation",
    "language": "vi",
    "user_query": "Make it engaging and concise",
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
    ],
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
    "voice_config": {
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
    },
    "total_duration": 45.8,
    "created_at": "datetime.now()",
    "updated_at": "datetime.now()",
}
