# Multi-Language Narration System - Implementation Checklist

**Architecture**: Option 1 - Separate Collections
**Date**: December 24, 2025
**Status**: ✅ **IMPLEMENTATION COMPLETE** - Ready for Testing

---

## Overview

Redesign slide narration system to support:
- ✅ Multi-language subtitles (vi, en, zh, etc.)
- ✅ Version management per language
- ✅ Audio files tagged by language + version
- ✅ Audio upload capability (not just AI generation)
- ✅ Public sharing (no authentication required)
- ✅ Configurable sharing (include/exclude subtitles, audio)
- ✅ Default to latest version for public access

---

## Phase 1: Database Schema Design ✅ COMPLETE

### 1.1 Create New Collections

**Collection: `presentation_subtitles`**
```javascript
{
  _id: ObjectId,
  presentation_id: String,          // References documents._id
  user_id: String,                  // Owner who generated
  language: String,                 // "vi", "en", "zh", etc.
  version: Number,                  // 1, 2, 3... per language
  mode: String,                     // "presentation" | "academy"
  slides: [{
    slide_index: Number,
    subtitles: [{
      text: String,
      element_references: String | Dict,  // Flexible validation
      timestamp: Number (optional)
    }]
  }],
  status: String,                   // "completed", "processing", "failed"
  created_at: DateTime,
  updated_at: DateTime,
  metadata: {
    total_slides: Number,
    word_count: Number,
    generation_time_seconds: Number
  }
}

// Indexes:
- { presentation_id: 1, language: 1, version: -1 }  // Get latest version
- { presentation_id: 1, user_id: 1 }                 // User's subtitles
- { language: 1, created_at: -1 }                    // Browse by language
```

**Collection: `presentation_audio`**
```javascript
{
  _id: ObjectId,
  presentation_id: String,          // References documents._id
  subtitle_id: ObjectId,            // References presentation_subtitles._id
  user_id: String,                  // Owner who generated/uploaded
  language: String,                 // Must match subtitle language
  version: Number,                  // Must match subtitle version
  slide_index: Number,              // Which slide this audio is for
  audio_url: String,                // Storage path
  audio_metadata: {
    duration_seconds: Float,
    file_size_bytes: Number,
    format: String,                 // "mp3", "wav", etc.
    sample_rate: Number
  },
  generation_method: String,        // "ai_generated" | "user_uploaded"
  voice_config: {                   // Only if ai_generated
    provider: String,               // "google", "openai", etc.
    voice: String,                  // Voice ID
    rate: Float,
    pitch: Float (optional)
  },
  status: String,                   // "ready", "processing", "failed"
  created_at: DateTime,
  updated_at: DateTime
}

// Indexes:
- { presentation_id: 1, language: 1, version: 1, slide_index: 1 }
- { subtitle_id: 1, slide_index: 1 }
- { user_id: 1, created_at: -1 }
- { audio_url: 1 }  // For cleanup/deduplication
```

**Collection: `presentation_sharing_config`**
```javascript
{
  _id: ObjectId,
  presentation_id: String,          // References documents._id (unique)
  user_id: String,                  // Owner
  is_public: Boolean,               // Public access enabled
  public_token: String,             // Unique token for public URL
  sharing_settings: {
    include_content: Boolean,       // Show slide HTML content
    include_subtitles: Boolean,     // Show subtitles
    include_audio: Boolean,         // Provide audio playback
    allowed_languages: [String],    // [] = all, ["vi", "en"] = specific
    default_language: String,       // Default language for public view
    require_attribution: Boolean    // Show "Created by..." on public view
  },
  shared_with_users: [{             // Private sharing with specific users
    user_id: String,
    permission: String,             // "view" | "comment" | "edit"
    granted_at: DateTime
  }],
  access_stats: {
    total_views: Number,
    unique_visitors: Number,
    last_accessed: DateTime
  },
  created_at: DateTime,
  updated_at: DateTime,
  expires_at: DateTime (optional)   // Auto-disable public access
}

// Indexes:
- { presentation_id: 1 }  // Unique
- { public_token: 1 }     // Unique, for public URL lookup
- { user_id: 1 }
- { is_public: 1, created_at: -1 }
```

### 1.2 Migration Strategy

**Task**: Migrate existing `slide_narrations` data
- Current data: 3 narrations for test document
- Map old structure to new collections:
  ```
  slide_narrations → presentation_subtitles (language from old doc)
                   → presentation_audio (extract audio_files array)
  ```
- Create default sharing configs (is_public=false)
- Preserve version numbers
- **Script**: `migrate_narrations_to_multilang.py`

---

## Phase 2: Pydantic Models ✅ COMPLETE

### 2.1 Create Models (`src/models/slide_narration_models.py`)

**Add/Update Models**:
```python
# Subtitle Models
class SubtitleEntryV2(BaseModel):
    """Single subtitle entry"""
    text: str
    element_references: Union[str, Dict] = ""
    timestamp: Optional[float] = None

class SlideSubtitles(BaseModel):
    """Subtitles for one slide"""
    slide_index: int
    subtitles: List[SubtitleEntryV2]

class PresentationSubtitle(BaseModel):
    """Complete subtitle document"""
    id: str = Field(alias="_id")
    presentation_id: str
    user_id: str
    language: str  # ISO 639-1 code
    version: int
    mode: str = "presentation"  # "presentation" | "academy"
    slides: List[SlideSubtitles]
    status: str = "completed"
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict] = None

# Audio Models
class AudioMetadata(BaseModel):
    duration_seconds: float
    file_size_bytes: int
    format: str = "mp3"
    sample_rate: int = 44100

class PresentationAudio(BaseModel):
    """Audio file for one slide"""
    id: str = Field(alias="_id")
    presentation_id: str
    subtitle_id: str
    user_id: str
    language: str
    version: int
    slide_index: int
    audio_url: str
    audio_metadata: AudioMetadata
    generation_method: str  # "ai_generated" | "user_uploaded"
    voice_config: Optional[VoiceConfig] = None
    status: str = "ready"
    created_at: datetime
    updated_at: datetime

# Sharing Models
class SharingSettings(BaseModel):
    include_content: bool = True
    include_subtitles: bool = True
    include_audio: bool = True
    allowed_languages: List[str] = []  # Empty = all
    default_language: str = "vi"
    require_attribution: bool = True

class SharedWithUser(BaseModel):
    user_id: str
    permission: str = "view"  # "view" | "comment" | "edit"
    granted_at: datetime

class PresentationSharingConfig(BaseModel):
    """Sharing configuration"""
    id: str = Field(alias="_id")
    presentation_id: str
    user_id: str
    is_public: bool = False
    public_token: Optional[str] = None
    sharing_settings: SharingSettings
    shared_with_users: List[SharedWithUser] = []
    access_stats: Dict = {}
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None

# Request/Response Models
class GenerateSubtitlesRequest(BaseModel):
    language: str  # "vi", "en", "zh"
    mode: str = "presentation"

class GenerateAudioRequest(BaseModel):
    subtitle_id: str
    voice_config: VoiceConfig

class UploadAudioRequest(BaseModel):
    subtitle_id: str
    slide_index: int
    audio_file: str  # Base64 or URL
    audio_metadata: AudioMetadata

class UpdateSharingConfigRequest(BaseModel):
    is_public: Optional[bool] = None
    sharing_settings: Optional[SharingSettings] = None
```

### 2.2 Update DocumentResponse Model

**File**: `src/models/document_editor_models.py`

```python
class NarrationInfo(BaseModel):
    """Multi-language narration info"""
    total_languages: int = 0
    languages: List[str] = []  # ["vi", "en", "zh"]
    latest_versions: Dict[str, int] = {}  # {"vi": 3, "en": 1}
    has_audio: Dict[str, bool] = {}  # {"vi": True, "en": False}

class DocumentResponse(BaseModel):
    # ... existing fields ...

    # Replace old fields:
    # has_narration: bool = False
    # narration_count: int = 0

    # With new field:
    narration_info: Optional[NarrationInfo] = None
```

---

## Phase 3: API Endpoints ✅ COMPLETE

### 3.1 Subtitle Endpoints

**File**: `src/api/slide_narration_routes.py`

#### Endpoint: Generate Subtitles
```python
POST /api/presentations/{presentation_id}/subtitles
Body: { language: "vi", mode: "presentation" }
Response: PresentationSubtitle

- Auto-increment version per language
- Deduct 2 points from user
- Store in presentation_subtitles collection
- Return new subtitle document
```

#### Endpoint: List Subtitles
```python
GET /api/presentations/{presentation_id}/subtitles
Query: ?language=vi (optional)
Response: { subtitles: [PresentationSubtitle] }

- List all subtitle versions for presentation
- Filter by language if specified
- Order by version DESC (latest first)
```

#### Endpoint: Get Specific Subtitle
```python
GET /api/presentations/{presentation_id}/subtitles/{subtitle_id}
Response: PresentationSubtitle

- Get one subtitle document by ID
- Verify user has access
```

#### Endpoint: Delete Subtitle
```python
DELETE /api/presentations/{presentation_id}/subtitles/{subtitle_id}
Response: { success: true }

- Delete subtitle document
- Delete associated audio files
- Verify user is owner
```

### 3.2 Audio Endpoints

#### Endpoint: Generate Audio
```python
POST /api/presentations/{presentation_id}/subtitles/{subtitle_id}/audio
Body: { voice_config: {...} }
Response: { audio_files: [PresentationAudio] }

- Generate audio for all slides in subtitle
- Deduct 2 points from user
- Store in presentation_audio collection
- Also store in library_audio (existing behavior)
- Return array of audio documents
```

#### Endpoint: Upload Audio
```python
POST /api/presentations/{presentation_id}/subtitles/{subtitle_id}/audio/upload
Body: { slide_index: 0, audio_file: "base64...", metadata: {...} }
Response: PresentationAudio

- Upload user-provided audio file
- Store file to storage service
- Create presentation_audio record
- generation_method = "user_uploaded"
- No points deduction
```

#### Endpoint: List Audio
```python
GET /api/presentations/{presentation_id}/audio
Query: ?language=vi&version=1 (optional)
Response: { audio_files: [PresentationAudio] }

- List all audio files for presentation
- Filter by language/version if specified
- Group by slide_index
```

#### Endpoint: Delete Audio
```python
DELETE /api/presentations/{presentation_id}/audio/{audio_id}
Response: { success: true }

- Delete audio file from storage
- Delete presentation_audio record
- Verify user is owner
```

### 3.3 Sharing Configuration Endpoints

#### Endpoint: Get Sharing Config
```python
GET /api/presentations/{presentation_id}/sharing
Response: PresentationSharingConfig

- Get sharing config for presentation
- Create default if not exists
- Verify user is owner
```

#### Endpoint: Update Sharing Config
```python
PUT /api/presentations/{presentation_id}/sharing
Body: { is_public: true, sharing_settings: {...} }
Response: PresentationSharingConfig

- Update sharing configuration
- Generate public_token if enabling public access
- Verify user is owner
```

#### Endpoint: Share with User
```python
POST /api/presentations/{presentation_id}/sharing/users
Body: { user_id: "...", permission: "view" }
Response: { success: true }

- Add user to shared_with_users array
- Verify user is owner
```

### 3.4 Public View Endpoints (NO AUTHENTICATION)

#### Endpoint: Get Public Presentation
```python
GET /api/public/presentations/{public_token}
Response: {
  presentation: {...},  // Document metadata + content
  subtitles: {...},     // Latest version of default language
  audio_files: [...],   // Audio for latest subtitle version
  sharing_settings: {...}
}

- No authentication required
- Lookup by public_token
- Check is_public = true
- Respect sharing_settings (include_content, include_subtitles, include_audio)
- Get latest version of default_language
- Filter allowed_languages
- Increment access_stats
```

#### Endpoint: Get Public Subtitles
```python
GET /api/public/presentations/{public_token}/subtitles
Query: ?language=vi&version=latest
Response: PresentationSubtitle

- No authentication required
- Get specific language/version subtitles
- Default to latest version if not specified
- Check allowed_languages
```

#### Endpoint: Get Public Audio
```python
GET /api/public/presentations/{public_token}/audio
Query: ?language=vi&version=latest
Response: { audio_files: [PresentationAudio] }

- No authentication required
- Get audio files for language/version
- Check include_audio in sharing_settings
```

---

## Phase 4: Service Layer Updates ✅ COMPLETE

### 4.1 SlideNarrationService

**File**: `src/services/slide_narration_service.py`

**Update Methods**:
```python
# New method
async def generate_subtitles_v2(
    presentation_id: str,
    language: str,
    mode: str,
    user_id: str
) -> Dict:
    """Generate subtitles for specific language"""
    # Get next version number for this language
    # Generate subtitles using Gemini
    # Store in presentation_subtitles
    # Return subtitle document

# Update existing
async def generate_audio(
    subtitle_id: str,           # Reference subtitle document
    slides_with_subtitles: List[Dict],
    voice_config: Dict,
    user_id: str,
    language: str,              # Add language param
    version: int                # Add version param
) -> Dict:
    """Generate audio for subtitle document"""
    # Generate audio for each slide
    # Store in presentation_audio with language/version tags
    # Also store in library_audio (existing behavior)
    # Return array of audio documents

# New method
async def upload_audio(
    subtitle_id: str,
    slide_index: int,
    audio_file: bytes,
    metadata: Dict,
    user_id: str
) -> Dict:
    """Upload user-provided audio"""
    # Upload file to storage
    # Create presentation_audio record
    # generation_method = "user_uploaded"
    # Return audio document
```

### 4.2 SharingService (NEW)

**File**: `src/services/sharing_service.py` (create new)

```python
class SharingService:
    """Manage presentation sharing"""

    async def get_or_create_config(
        presentation_id: str,
        user_id: str
    ) -> Dict:
        """Get sharing config, create default if not exists"""

    async def update_config(
        presentation_id: str,
        user_id: str,
        updates: Dict
    ) -> Dict:
        """Update sharing configuration"""

    def generate_public_token(self) -> str:
        """Generate unique public token"""

    async def get_public_presentation(
        public_token: str
    ) -> Dict:
        """Get presentation by public token (no auth)"""

    async def increment_access_stats(
        config_id: str
    ):
        """Track access statistics"""
```

---

## Phase 5: Immediate Bug Fixes ✅ COMPLETE

### 5.1 Fix Audio Generation Parameter Mismatch

**File**: `src/api/slide_narration_routes.py`
**Line**: 382-387

**Current (BROKEN)**:
```python
result = await narration_service.generate_audio(
    narration_id=narration_id,
    slides=narration["slides"],           # ❌
    language=narration["language"],       # ❌
    voice_config=request.voice_config,    # ❌
    user_id=user_id,
)
```

**Fix to**:
```python
result = await narration_service.generate_audio(
    narration_id=narration_id,
    slides_with_subtitles=narration["slides"],  # ✅ Correct param name
    voice_config=request.voice_config.dict(),   # ✅ Convert to dict
    user_id=user_id,
    # Remove language parameter - doesn't exist in service method
)
```

---

## Phase 6: Migration Script ✅ COMPLETE

### 6.1 Create Migration Script

**File**: `migrate_narrations_to_multilang.py`

```python
"""
Migrate existing slide_narrations to new multi-language structure
"""

# For each document in slide_narrations:
#   1. Create presentation_subtitles document
#      - Extract language, version, slides, mode
#      - Copy metadata
#
#   2. Create presentation_audio documents
#      - For each audio_file in audio_files array
#      - Tag with language and version
#      - Link to subtitle_id
#
#   3. Create presentation_sharing_config
#      - Default: is_public=false
#      - Default: all settings enabled
#
#   4. Mark old document as migrated (add flag)
#      - Don't delete yet (keep for rollback)

# Verification:
#   - Count documents before/after
#   - Verify all audio files migrated
#   - Check no data loss
```

---

## Phase 7: Testing Checklist

### 7.1 Subtitle Generation
- [ ] Generate subtitles in Vietnamese (vi)
- [ ] Generate subtitles in English (en)
- [ ] Generate multiple versions same language
- [ ] Verify version auto-increment per language
- [ ] Check points deduction (2 points)
- [ ] Verify subtitle quality and structure

### 7.2 Audio Generation
- [ ] Generate audio for Vietnamese subtitles
- [ ] Generate audio for English subtitles
- [ ] Verify audio stored in presentation_audio
- [ ] Verify audio also in library_audio
- [ ] Check language/version tags correct
- [ ] Check points deduction (2 points)

### 7.3 Audio Upload
- [ ] Upload MP3 file for slide
- [ ] Upload WAV file for slide
- [ ] Verify no points deduction
- [ ] Check generation_method="user_uploaded"
- [ ] Verify audio playback works

### 7.4 Public Sharing
- [ ] Enable public access for presentation
- [ ] Verify public_token generated
- [ ] Access via public URL (no auth)
- [ ] Verify content visible
- [ ] Verify subtitles visible (latest version)
- [ ] Verify audio playback works
- [ ] Check allowed_languages filter
- [ ] Check default_language selection
- [ ] Verify access_stats increment

### 7.5 Sharing Settings
- [ ] Disable content (only show title)
- [ ] Disable subtitles (no subtitle panel)
- [ ] Disable audio (no audio playback)
- [ ] Set allowed_languages to ["vi"]
- [ ] Change default_language to "en"
- [ ] Set expiration date
- [ ] Verify settings respected on public view

### 7.6 Private Sharing
- [ ] Share with specific user (view permission)
- [ ] Share with edit permission
- [ ] Verify shared user can access
- [ ] Verify non-shared user cannot access
- [ ] Remove shared user access

### 7.7 Migration
- [ ] Run migration script
- [ ] Verify all 3 existing narrations migrated
- [ ] Check subtitle documents created
- [ ] Check audio documents created
- [ ] Check sharing configs created
- [ ] Verify no data loss
- [ ] Test old endpoints still work (backward compat)

### 7.8 Document Endpoint
- [ ] GET /api/presentations/{id}
- [ ] Verify narration_info present
- [ ] Check total_languages count
- [ ] Check languages array
- [ ] Check latest_versions map
- [ ] Check has_audio map

---

## Phase 8: Deployment

### 8.1 Pre-Deployment
- [ ] Review all code changes
- [ ] Run migration script on staging
- [ ] Test all endpoints on staging
- [ ] Verify public access works
- [ ] Check database indexes created
- [ ] Performance test with 100+ slides

### 8.2 Deployment Steps
1. [ ] Backup production database
2. [ ] Deploy new code (API + models + services)
3. [ ] Create database indexes
4. [ ] Run migration script
5. [ ] Verify migration success
6. [ ] Test critical endpoints
7. [ ] Monitor error logs
8. [ ] Test public sharing URLs

### 8.3 Post-Deployment
- [ ] Monitor API response times
- [ ] Check error rates
- [ ] Verify points deduction working
- [ ] Test frontend integration
- [ ] Gather user feedback
- [ ] Document any issues

---

## Phase 9: Documentation

### 9.1 API Documentation
- [ ] Update API docs with new endpoints
- [ ] Document request/response schemas
- [ ] Add authentication requirements
- [ ] Document public endpoints (no auth)
- [ ] Add code examples
- [ ] Document error codes

### 9.2 Frontend Integration Guide
- [ ] Document new narration_info structure
- [ ] Explain language selection UI
- [ ] Explain version management UI
- [ ] Document audio upload flow
- [ ] Document sharing configuration UI
- [ ] Document public view embedding

### 9.3 User Guide
- [ ] How to generate subtitles
- [ ] How to generate audio
- [ ] How to upload audio files
- [ ] How to enable public sharing
- [ ] How to configure sharing settings
- [ ] How to share with specific users

---

## Critical Notes

### Audio in Library
- ✅ Generated audio is ALREADY stored in library_audio
- ✅ Current behavior: SlideNarrationService.generate_audio() calls LibraryAudioService
- ✅ NEW: Also store reference in presentation_audio with language/version tags
- ✅ Two-way link: presentation_audio.audio_url → library_audio document

### Public Access Requirements
- ✅ NO authentication required for public endpoints
- ✅ Content: Slide HTML visible if include_content=true
- ✅ Subtitles: Latest version of default_language if include_subtitles=true
- ✅ Audio: Latest version audio if include_audio=true
- ✅ Language filter: Only show allowed_languages
- ✅ Auto-select: Default to latest version per language

### Version Management
- ✅ Version numbers are PER LANGUAGE
- ✅ Example: vi v1, vi v2, en v1 (not global v1, v2, v3)
- ✅ Auto-increment: Get max version for language, add 1
- ✅ Latest version: ORDER BY version DESC LIMIT 1 per language

### Backward Compatibility
- ⚠️ Keep old slide_narrations endpoints for transition period
- ⚠️ Frontend should migrate to new narration_info structure
- ⚠️ Old endpoints can proxy to new collections
- ⚠️ Plan deprecation timeline (3-6 months)

---

## Estimated Timeline

- **Phase 1 (Database)**: 2 hours
- **Phase 2 (Models)**: 2 hours
- **Phase 3 (Endpoints)**: 8 hours
- **Phase 4 (Services)**: 4 hours
- **Phase 5 (Bug Fixes)**: 1 hour
- **Phase 6 (Migration)**: 3 hours
- **Phase 7 (Testing)**: 6 hours
- **Phase 8 (Deployment)**: 2 hours
- **Phase 9 (Documentation)**: 3 hours

**Total**: ~31 hours of development work

---

## Success Criteria

✅ Multi-language support working (vi, en, zh)
✅ Version management per language functional
✅ Audio generation + upload both working
✅ Public sharing accessible without login
✅ Sharing settings respected (content/subtitles/audio)
✅ Migration completed without data loss
✅ All existing features still functional
✅ Points system working correctly
✅ No performance degradation
✅ Frontend successfully integrated

---

## Rollback Plan

If critical issues found:
1. Disable new endpoints (feature flag)
2. Restore old slide_narrations endpoints
3. Keep migrated data (don't delete)
4. Investigate and fix issues
5. Re-deploy when ready

**Rollback trigger**: >5% error rate OR data loss detected OR performance degradation >50%
