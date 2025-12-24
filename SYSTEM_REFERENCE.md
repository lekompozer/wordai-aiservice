# System Reference - Backend Infrastructure

**Last Updated:** December 14, 2025
**Purpose:** Complete reference for AI agents and developers working with the backend system

---

## 🐳 Docker Configuration

### Container Names

| Container Name | Service | Purpose |
|---------------|---------|---------|
| `ai-chatbot-rag` | Backend API | Main FastAPI application |
| `mongodb` | Database | MongoDB 7.0 database server |
| `qdrant` | Vector DB | Qdrant vector search (if used) |
| `redis` | Cache | Redis cache server (if used) |

ssh root@104.248.147.155 "docker ps"
CONTAINER ID   IMAGE                                       COMMAND                  CREATED          STATUS                      PORTS                                                                          NAMES
3c2925a0d1d5   nginx:1.26-alpine                           "/docker-entrypoint.…"   32 minutes ago   Up 32 minutes (healthy)     0.0.0.0:80->80/tcp, [::]:80->80/tcp, 0.0.0.0:443->443/tcp, [::]:443->443/tcp   nginx-gateway
2024f7a23300   lekompozer/wordai-payment-service:146b3b9   "docker-entrypoint.s…"   32 minutes ago   Up 32 minutes (unhealthy)   0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp                                    payment-service
483413e29907   lekompozer/wordai-aiservice:146b3b9         "uvicorn serve:app -…"   32 minutes ago   Up 32 minutes (healthy)     0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp                                    ai-chatbot-rag
219741c4aee7   mongo:7.0                                   "docker-entrypoint.s…"   32 minutes ago   Up 32 minutes               0.0.0.0:27017->27017/tcp, [::]:27017->27017/tcp                                mongodb
632bfacd8496   redis:7-alpine                              "docker-entrypoint.s…"   32 minutes ago   Up 32 minutes (healthy)     0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp                                    redis-server

### Docker Commands

```bash
# List running containers
docker ps

# View logs
docker logs ai-chatbot-rag
docker logs ai-chatbot-rag -f --tail 100

# Execute commands inside container
docker exec ai-chatbot-rag <command>

# Access container shell
docker exec -it ai-chatbot-rag /bin/bash

# Check files inside container
docker exec ai-chatbot-rag ls -lh /tmp/
```

---

## 🗄️ MongoDB Database

### Connection Information

**Database Name:** `wordai_db` ✅ (UNIFIED - All code must use this)

**Connection String Format:**
```
mongodb://<username>:<password>@mongodb:27017/?authSource=admin
```

**Alternative Connection (from inside Docker network):**
```
mongodb://<username>:<password>@mongodb:27017/wordai_db?authSource=admin
```

**Environment Variables:**
- `MONGODB_NAME`: Database name (default: `wordai_db` - MUST USE THIS)
- `MONGODB_URI_AUTH`: Full connection string with authentication (PRODUCTION - REQUIRED on server)
- `MONGODB_URI`: Full connection string without auth (LOCAL DEVELOPMENT ONLY)
- `MONGO_INITDB_ROOT_USERNAME`: Admin username
- `MONGO_INITDB_ROOT_PASSWORD`: Admin password

**Important:**
- Production server MUST use `MONGODB_URI_AUTH`
- Local development uses `MONGODB_URI`
- Backend code checks `MONGODB_URI_AUTH` first, falls back to `MONGODB_URI`

### ⚙️ Database Connection Pattern (CRITICAL - MANDATORY FOR ALL CODE)

**ALL new code MUST follow this pattern. Do NOT use any other method.**

#### ✅ CORRECT: DBManager Pattern (USE THIS)

```python
from src.database.db_manager import DBManager

# In API routes (module-level initialization)
db_manager = DBManager()
db = db_manager.db

# Usage in endpoints
@router.get("/api/example")
async def example_endpoint():
    result = db.collection_name.find_one({"_id": ObjectId(id)})
    return result

# In Service classes (lazy initialization)
class MyService:
    def __init__(self):
        db_manager = DBManager()
        self.db = db_manager.db
        self.collection = self.db.collection_name

    def my_method(self):
        return self.collection.find_one({"field": "value"})

# In standalone functions (local initialization)
def process_data():
    from src.database.db_manager import DBManager

    db_manager = DBManager()
    db = db_manager.db

    # Use db here
    result = db.collection.find(...)
    return result
```

**Why DBManager?**
- ✅ Singleton pattern - efficient connection pooling
- ✅ Auto-handles authentication (MONGODB_URI_AUTH → MONGODB_URI)
- ✅ Environment-aware (production vs development)
- ✅ Built-in connection testing and error handling
- ✅ Consistent across entire codebase

#### ❌ INCORRECT: Legacy Patterns (DO NOT USE)

```python
# ❌ WRONG - Direct MongoClient
from pymongo import MongoClient
client = MongoClient(uri)
db = client[db_name]

# ❌ WRONG - get_mongodb_service (deprecated utility)
from src.services.online_test_utils import get_mongodb_service
db = get_mongodb_service()

# ❌ WRONG - Non-existent imports
from src.database.mongodb_service import get_mongodb_service  # Does not exist!

# ❌ WRONG - config.get_mongodb (legacy)
from config.config import get_mongodb
db = get_mongodb()
```

#### 📋 Migration Checklist

When updating existing code:
- [ ] Replace `get_mongodb_service()` with `DBManager()`
- [ ] Update import: `from src.database.db_manager import DBManager`
- [ ] Change `db = get_mongodb_service()` to `db_manager = DBManager(); db = db_manager.db`
- [ ] Remove `.db` suffix if using old pattern: `get_mongodb_service().db` → `db_manager.db`
- [ ] Test database operations still work
- [ ] Commit with message: `fix: Use DBManager pattern for MongoDB connection`

#### 🔍 Examples from Production Code

**API Routes** (see `src/api/book_routes.py`, `src/api/document_editor_routes.py`):
```python
from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db

# Initialize services with db
book_manager = UserBookManager(db)
document_manager = DocumentManager(db)
```

**Services** (see `src/services/sharing_service.py`):
```python
from src.database.db_manager import DBManager

class SharingService:
    def __init__(self):
        db_manager = DBManager()
        self.db = db_manager.db
        self.sharing_configs = self.db.presentation_sharing_config
```

**Standalone Functions** (see `src/services/slide_narration_service.py`):
```python
async def generate_subtitles_v2(self, presentation_id, language, mode, user_id):
    from src.database.db_manager import DBManager

    db_manager = DBManager()
    db = db_manager.db

    # Use db for operations
    presentation = db.documents.find_one({"_id": ObjectId(presentation_id)})
```

#### ⚠️ Legacy Pattern (Test System Only - NOT RECOMMENDED for new code)

**`get_mongodb_service()` from `src.services.online_test_utils`:**

```python
from src.services.online_test_utils import get_mongodb_service

# Usage
mongo_service = get_mongodb_service()
db = mongo_service.db

# Access collections
tests = db.online_tests.find(...)
```

**Why still exists:**
- Used extensively in test system (test_creation, test_sharing, test_evaluation, etc.)
- Migration to DBManager requires updating 100+ endpoints
- **Differences from DBManager**:
  - ✅ Uses `MONGODB_URI_AUTH` → `MONGODB_URI` (same priority as DBManager)
  - ✅ Default db_name: `ai_service_db` (FIXED - was `wordai_db`)
  - ❌ No connection testing (`ping`)
  - ❌ No index creation
  - ❌ Minimal error handling

**When to use:**
- ✅ Only when maintaining existing test system code
- ❌ NOT for new code (use DBManager instead)
- ❌ NOT for slides, documents, or books (use DBManager)

---

### 🎵 Audio/TTS Service Patterns

#### Google TTS Service (Text-to-Speech)

**CORRECT Import Path:**
```python
from src.services.google_tts_service import GoogleTTSService

# Initialize
tts_service = GoogleTTSService()

# Generate audio
audio_bytes = tts_service.synthesize_speech(
    text="Hello world",
    language_code="en-US",
    voice_name="en-US-Standard-A",
    speaking_rate=1.0
)
```

**❌ WRONG Import (DO NOT USE):**
```python
# This path does NOT exist:
from src.services.tts.google_tts_service import GoogleTTSService  # ❌ NO 'tts' subfolder
```

#### Library Manager (R2 + MongoDB Integration)

**CORRECT Pattern - No Singleton Function:**
```python
from src.database.db_manager import DBManager
from src.services.library_manager import LibraryManager
from src.services.r2_storage_service import get_r2_service

# Initialize with db + s3_client
db_manager = DBManager()
r2_service = get_r2_service()
library_manager = LibraryManager(db=db_manager.db, s3_client=r2_service.s3_client)

# Save file to library
library_id = library_manager.save_library_file(
    user_id="user123",
    file_name="audio.mp3",
    r2_url="https://cdn.r2.wordai.vn/audio/abc.mp3",
    file_type="audio/mpeg",
    file_size=123456,
    category="audio",  # auto-detected from file_type
    metadata={"duration": 15.5, "voice": "Kore"}
)
```

**❌ WRONG Pattern (Function doesn't exist):**
```python
# This function does NOT exist in library_manager.py:
from src.services.library_manager import get_library_manager  # ❌ NO SUCH FUNCTION
library_manager = get_library_manager()  # ❌ ImportError
```

**Complete Example (Slide Narration Service):**
```python
class SlideNarrationService:
    def __init__(self):
        from src.services.r2_storage_service import get_r2_service
        from src.services.library_manager import LibraryManager
        from src.database.db_manager import DBManager

        self.r2_service = get_r2_service()
        db_manager = DBManager()
        self.library_manager = LibraryManager(
            db=db_manager.db,
            s3_client=self.r2_service.s3_client
        )

    async def generate_audio(self, text: str, language: str, voice_name: str):
        from src.services.google_tts_service import GoogleTTSService

        tts = GoogleTTSService()

        # ✅ CORRECT: generate_audio returns (bytes, dict)
        audio_bytes, metadata = await tts.generate_audio(
            text=text,
            language=language,
            voice_name=voice_name,
            use_pro_model=True
        )

        # metadata contains: format, sample_rate, duration, voice_name, etc.
        duration = metadata.get("duration", 0)

        # Upload to R2
        upload_result = await self.r2_service.upload_file(
            file_content=audio_bytes,
            r2_key="narration/user123/audio.wav",
            content_type="audio/wav"
        )
        r2_url = upload_result["public_url"]

        # Save to library
        library_id = self.library_manager.save_library_file(
            user_id="user123",
            filename="narration.wav",
            r2_url=r2_url,
            file_type="audio",
            file_size=len(audio_bytes),
            metadata={"duration": duration, "voice": voice_name}
        )
        return library_id
```

**❌ WRONG TTS Usage:**
```python
# Don't use these parameter names:
audio_data = await tts.generate_audio(script=text, voice_config=config)  # ❌ TypeError

# Don't expect dict return:
audio_bytes = tts.generate_audio(text)["audio_bytes"]  # ❌ Can't subscript bytes
            file_type="audio/mpeg",
            file_size=len(audio_bytes),
            category="audio"
        )
        return library_id
```

---

### 📚 Library Collections Reference

#### Audio Library (`library_audio` collection)

**Add Audio to Library** (after AI generation or user upload):

```python
from src.database.db_manager import DBManager
from datetime import datetime

db_manager = DBManager()
db = db_manager.db

audio_doc = {
    "_id": ObjectId(),  # Generate new ID
    "user_id": user_id,
    "file_name": "narration_slide_0.mp3",
    "r2_url": "https://cdn.r2.wordai.vn/audio/abc123.mp3",
    "duration": 15.5,  # seconds
    "file_size": 245678,  # bytes
    "format": "mp3",
    "source_type": "narration",  # or "test_audio", "user_upload"
    "created_at": datetime.utcnow(),
    "metadata": {
        "presentation_id": "doc_123",
        "slide_index": 0,
        "voice": "Kore",
        "language": "vi-VN"
    }
}

result = db.library_audio.insert_one(audio_doc)
audio_id = str(result.inserted_id)
```

**Query Audio Library**:
```python
# List user's audio files
audio_files = db.library_audio.find(
    {"user_id": user_id}
).sort("created_at", -1).limit(20)

# Search by name
audio_files = db.library_audio.find({
    "user_id": user_id,
    "file_name": {"$regex": "search_term", "$options": "i"}
})

# Filter by source type
test_audio = db.library_audio.find({
    "user_id": user_id,
    "source_type": "test_audio"
})
```

#### Image Library (`library_images` collection)

**Add Image to Library**:

```python
image_doc = {
    "_id": ObjectId(),
    "user_id": user_id,
    "file_name": "diagram.png",
    "r2_url": "https://cdn.r2.wordai.vn/images/xyz789.png",
    "width": 1920,
    "height": 1080,
    "file_size": 524288,
    "format": "png",
    "source_type": "ai_generated",  # or "user_upload", "stock"
    "created_at": datetime.utcnow(),
    "metadata": {
        "prompt": "modern tech diagram",
        "style": "minimalist"
    }
}

result = db.library_images.insert_one(image_doc)
image_id = str(result.inserted_id)
```

#### Video Library (`library_videos` collection)

**Add Video to Library**:

```python
video_doc = {
    "_id": ObjectId(),
    "user_id": user_id,
    "file_name": "presentation.mp4",
    "r2_url": "https://cdn.r2.wordai.vn/videos/def456.mp4",
    "duration": 120.0,  # seconds
    "width": 1920,
    "height": 1080,
    "file_size": 15728640,  # bytes
    "format": "mp4",
    "source_type": "screen_recording",  # or "ai_generated", "user_upload"
    "created_at": datetime.utcnow(),
    "metadata": {
        "fps": 30,
        "codec": "h264",
        "bitrate": "1M"
    }
}

result = db.library_videos.insert_one(video_doc)
video_id = str(result.inserted_id)
```

**Common Library Patterns**:
- Always include `user_id` for access control
- Use `r2_url` for CDN storage (Cloudflare R2)
- Include `created_at` for sorting
- Use `source_type` to track origin
- Store additional context in `metadata` field

---

### 💰 Points Management Pattern (MANDATORY)

**All AI operations MUST check and deduct points before execution.**

#### Standard Points Flow

```python
from src.services.points_service import get_points_service
from fastapi import HTTPException

# 1. Get points service
points_service = get_points_service()

# 2. Define operation cost
POINTS_COST = 2  # See SERVICE_POINTS_COST in points_service.py

# 3. Check balance BEFORE operation
try:
    has_points = points_service.check_points(user_id, POINTS_COST)
    if not has_points:
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient points. Need {POINTS_COST}, have 0"
        )
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Failed to check points: {e}")

# 4. Perform AI operation
result = await ai_operation(...)  # Your AI logic here

# 5. Deduct points AFTER successful operation
try:
    points_service.deduct_points(
        user_id=user_id,
        points=POINTS_COST,
        service_type="ai_operation_name",  # e.g., "slide_generation", "ai_chat_gemini"
        description="Generate presentation narration",
        metadata={
            "presentation_id": presentation_id,
            "operation": "generate_narration"
        }
    )
except Exception as e:
    logger.error(f"Failed to deduct points: {e}")
    # Continue - operation already completed

# 6. Return result with points info
return {
    "success": True,
    "result": result,
    "points_deducted": POINTS_COST
}
```

#### Points Service Costs (from `SERVICE_POINTS_COST`)

**Chat Operations:**
- DeepSeek: 1 point (`ai_chat_deepseek`, `ai_document_chat_deepseek`)
- Claude/ChatGPT/Gemini/Cerebras: 2 points each
- Default: 2 points

**Document AI:**
- Edit/Translate/Format: 2 points each
- Document generation: 2 points

**Slides & Files:**
- Slide generation: 2 points
- File conversions: 2 points
- File analysis: 2 points

**Other:**
- Quote generation: 2 points
- Test generation: 2 points
- **Narration generation**: 2 points (subtitle + audio each)

#### Points Service API

```python
from src.services.points_service import get_points_service

points_service = get_points_service()

# Check balance
has_points = points_service.check_points(user_id, required_points)

# Deduct points
points_service.deduct_points(
    user_id=user_id,
    points=amount,
    service_type="operation_name",  # Must match SERVICE_POINTS_COST keys
    description="Human readable description",
    metadata={}  # Optional context
)

# Get balance
balance = points_service.get_balance(user_id)

# Get transaction history
transactions = points_service.get_transactions(user_id, limit=50)
```

#### Error Handling

```python
from src.exceptions import InsufficientPointsError

try:
    has_points = points_service.check_points(user_id, POINTS_COST)
    if not has_points:
        raise InsufficientPointsError(
            user_id=user_id,
            required=POINTS_COST,
            available=points_service.get_balance(user_id)
        )
except InsufficientPointsError as e:
    raise HTTPException(
        status_code=403,
        detail=f"Insufficient points. Need {e.required}, have {e.available}"
    )
```

**CRITICAL Rules:**
- ✅ **ALWAYS** check points BEFORE AI operation
- ✅ **ALWAYS** deduct points AFTER successful operation
- ✅ Use correct `service_type` from `SERVICE_POINTS_COST`
- ✅ Include descriptive `description` for user transaction history
- ✅ Return `points_deducted` in response
- ❌ **NEVER** deduct points if operation fails
- ❌ **NEVER** skip points check for AI operations

---

### Collections Structure

#### 1. **online_tests**
Test documents and questions

**Fields:**
- `_id`: ObjectId (test ID)
- `title`: String
- `description`: String
- `creator_id`: String (Firebase UID)
- `creator_name`: String
- `test_type`: String (`mcq`, `listening`, `merged`)
- `test_category`: String (`academic`, `diagnostic`)
- `status`: String (`ready`, `generating`, `failed`)
- `is_active`: Boolean
- `questions`: Array of question objects
  - `question_id`: String
  - `question_type`: String (`mcq`, `mcq_multiple`, `matching`, `completion`, `sentence_completion`, `short_answer`, `essay`)
  - `question_text`: String
  - `correct_answers`: Array (unified field)
  - `explanation`: String
  - `max_points`: Integer
  - `options`: Array (for MCQ)
  - `template`: String (for completion/sentence_completion)
  - `sentences`: Array (for IELTS sentence_completion)
  - `left_items`, `right_options`: Arrays (for matching)
- `audio_sections`: Array (for listening tests)
- `attachments`: Array (for reading comprehension PDFs)
- `time_limit_minutes`: Integer
- `max_retries`: Integer
- `passing_score`: Integer
- `deadline`: DateTime
- `show_answers_timing`: String (`immediate`, `after_deadline`)
- `marketplace_config`: Object (for published tests)
- `evaluation_criteria`: Object (for diagnostic tests)
- `created_at`: DateTime
- `updated_at`: DateTime
- `generated_at`: DateTime

**Indexes:**
- `_id`: Primary key
- `creator_id`: For user's tests
- `status`: For filtering ready tests

#### 2. **test_submissions**
User test submissions and results

**Fields:**
- `_id`: ObjectId (submission ID)
- `test_id`: String
- `user_id`: String (Firebase UID)
- `user_email`: String
- `user_answers`: Array of answer objects
- `grading_status`: String (`auto_graded`, `pending_grading`, `partially_graded`, `fully_graded`)
- `score`: Float (out of 10)
- `score_percentage`: Float (0-100)
- `mcq_score`: Float (MCQ points only)
- `essay_score`: Float (essay points only)
- `mcq_correct_count`: Integer
- `correct_answers`: Integer (total correct)
- `total_questions`: Integer
- `is_passed`: Boolean
- `time_taken_seconds`: Integer
- `attempt_number`: Integer
- `essay_grades`: Array (for essay questions)
- `submitted_at`: DateTime
- `is_diagnostic_test`: Boolean
- `has_ai_evaluation`: Boolean

**Indexes:**
- `_id`: Primary key
- `test_id`: For test results
- `user_id`: For user submissions
- `{test_id, user_id}`: Compound for user's attempts

#### 3. **test_shares**
Test sharing permissions

**Fields:**
- `_id`: ObjectId
- `test_id`: String
- `owner_id`: String (Firebase UID)
- `shared_with`: Array of user objects
  - `user_id`: String
  - `email`: String
  - `shared_at`: DateTime
  - `can_edit`: Boolean
- `created_at`: DateTime

**Indexes:**
- `test_id`: For test sharing
- `shared_with.user_id`: For user's shared tests

#### 4. **users**
User profiles and settings

**Fields:**
- `_id`: ObjectId
- `firebase_uid`: String (unique)
- `email`: String
- `display_name`: String
- `photo_url`: String
- `subscription_tier`: String
- `points_balance`: Integer
- `created_at`: DateTime
- `last_login`: DateTime

**Indexes:**
- `firebase_uid`: Unique, for authentication
- `email`: For lookups

#### 5. **grading_queue**
Essay grading queue

**Fields:**
- `_id`: ObjectId
- `submission_id`: String
- `test_id`: String
- `user_id`: String
- `total_essays`: Integer
- `graded_count`: Integer
- `status`: String (`pending`, `in_progress`, `completed`)
- `created_at`: DateTime

**Indexes:**
- `submission_id`: Unique
- `status`: For queue processing

#### 6. **test_purchases**
Marketplace test purchases

**Fields:**
- `_id`: ObjectId
- `test_id`: String
- `buyer_id`: String (Firebase UID)
- `seller_id`: String (test creator)
- `price_points`: Integer
- `purchased_at`: DateTime

**Indexes:**
- `{test_id, buyer_id}`: Compound, unique
- `buyer_id`: For user purchases
- `seller_id`: For seller earnings

#### 7. **test_ratings**
Test ratings and reviews

**Fields:**
- `_id`: ObjectId
- `test_id`: String
- `user_id`: String
- `rating`: Integer (1-5)
- `review`: String
- `created_at`: DateTime

**Indexes:**
- `{test_id, user_id}`: Compound, unique
- `test_id`: For test ratings

#### 8. **conversations**
Chat conversations

**Fields:**
- `_id`: ObjectId
- `user_id`: String
- `title`: String
- `messages`: Array
- `created_at`: DateTime
- `updated_at`: DateTime

**Indexes:**
- `user_id`: For user conversations

#### 9. **notifications**
User notifications

**Fields:**
- `_id`: ObjectId
- `user_id`: String
- `type`: String
- `title`: String
- `message`: String
- `is_read`: Boolean
- `created_at`: DateTime

**Indexes:**
- `user_id`: For user notifications
- `is_read`: For unread count

#### 10. **ai_evaluations** ⭐ NEW
AI-powered test evaluations (Gemini)

**Fields:**
- `_id`: ObjectId (evaluation ID)
- `submission_id`: String
- `test_id`: String
- `user_id`: String (Firebase UID)
- `test_title`: String
- `test_category`: String
- `overall_evaluation`: Object
  - `overall_rating`: Float (0-10)
  - `strengths`: Array[String]
  - `weaknesses`: Array[String]
  - `recommendations`: Array[String]
  - `study_plan`: String
- `question_evaluations`: Array
  - `question_id`: String
  - `question_type`: String
  - `user_answer`: String
  - `ai_feedback`: String
- `model`: String (e.g., "gemini-2.5-pro")
- `generation_time_ms`: Integer
- `points_cost`: Integer (default: 1)
- `language`: String ("vi" or "en")
- `created_at`: DateTime

**Indexes:**
- `submission_id`: For submission evaluations
- `{user_id, created_at}`: For user's evaluation history (sorted)
- `{test_id, user_id}`: For filtering by test

**Security:**
- User must own submission to view evaluations
- Test owner can view all students' evaluations
- Evaluations stored permanently for history

---

## 📁 File System Structure

### Temporary Files (Inside Docker Container)

```
/tmp/
├── gemini_test_responses/     # Full Gemini API responses (JSON)
│   └── test_gen_YYYYMMDD_HHMMSS_ffffff.json
├── gemini_parsed_json/        # Parsed JSON before validation
│   └── parsed_YYYYMMDD_HHMMSS_ffffff.json
└── gemini_prompts/            # Prompts sent to Gemini
    └── prompt_YYYYMMDD_HHMMSS_ffffff.txt
```

**Note:** These directories are created dynamically when tests are generated.

### Application Structure

```
/app/                          # Inside Docker container
├── src/
│   ├── api/                   # FastAPI route handlers
│   │   ├── test_creation_routes.py
│   │   ├── test_taking_routes.py
│   │   ├── test_grading_routes.py
│   │   ├── marketplace_routes.py
│   │   └── test_sharing_routes.py
│   ├── services/
│   │   ├── test_generator_service.py
│   │   ├── prompt_builders.py
│   │   └── online_test_utils.py
│   └── models/                # Pydantic models
├── serve.py                   # FastAPI app entry point
└── requirements.txt
```

---

## 🚀 Deployment Process

### Deployment Script

**Location:** `/home/hoile/wordai/deploy-compose-with-rollback.sh`

**Standard Deployment Commands:**

```bash
# 1. SSH to production server
ssh root@<server-ip>

# 2. Switch to deployment user
su - hoile

# 3. Navigate to project directory
cd /home/hoile/wordai

# 4. Pull latest code
git pull origin main

# 5. Deploy with rollback capability
./deploy-compose-with-rollback.sh
```

### Deployment Flow

1. **Pull latest code** from GitHub
2. **Build new Docker image** with latest commit hash as tag
3. **Stop current container** (ai-chatbot-rag)
4. **Start new container** with new image
5. **Health check** (wait for /health endpoint)
6. **Rollback** if health check fails (restore previous image)

### Docker Image Naming

Format: `lekompozer/wordai-aiservice:<commit-hash>`

Example: `lekompozer/wordai-aiservice:7757d9c`

### Check Current Version

```bash
# Check running container image
docker inspect ai-chatbot-rag --format "{{.Config.Image}}"

# Check when container was created
docker inspect ai-chatbot-rag --format "{{.Created}}"
```

---

## 🔧 MongoDB Access

### From Production Server

```bash
# SSH to server
ssh root@<server-ip>

# Access MongoDB shell
docker exec mongodb mongosh -u <username> -p <password> \
  --authenticationDatabase admin ai_service_db
```

### Common MongoDB Operations

```javascript
// Switch to database
use ai_service_db

// List all collections
show collections

// Count documents
db.online_tests.countDocuments()

// Find test by ID (as ObjectId)
db.online_tests.findOne({_id: ObjectId("693eb0d83456aa028c4ee7fe")})

// Find tests by user
db.online_tests.find({creator_id: "firebase-uid"}).limit(10)

// Find submissions for a test
db.test_submissions.find({test_id: "693eb0d83456aa028c4ee7fe"})

// Check test status
db.online_tests.find({status: "ready"}).count()

// Get recent tests
db.online_tests.find().sort({created_at: -1}).limit(5)
```

### Query from Command Line (One-liner)

```bash
# Example: Check test questions
docker exec mongodb mongosh -u <username> -p <password> \
  --authenticationDatabase admin ai_service_db --quiet --eval '
var test = db.online_tests.findOne({_id: ObjectId("test-id-here")});
if (test) {
    print("Title: " + test.title);
    print("Questions: " + test.questions.length);
    test.questions.forEach((q, i) => {
        print((i+1) + ". " + q.question_type + " - " + q.question_text.substring(0, 50));
    });
}
'
```

---

## 🔍 Debugging & Logging

### View Application Logs

```bash
# Real-time logs
docker logs ai-chatbot-rag -f

# Last 100 lines
docker logs ai-chatbot-rag --tail 100

# Search for specific test
docker logs ai-chatbot-rag 2>&1 | grep "test-id-here"

# Filter by timestamp
docker logs ai-chatbot-rag 2>&1 | grep "2025-12-14 19:43"
```

### Log Patterns to Search

```bash
# Test generation
grep "🎯 Starting test generation"
grep "✅ Generated.*questions"
grep "💾 Saved full response"

# Test retrieval
grep "📖 Get test request"
grep "🔑 Owner view"
grep "👥 Shared view"

# Errors
grep "❌"
grep "ERROR"
grep "Exception"
```

### Check Gemini Response Files

```bash
# List saved responses
docker exec ai-chatbot-rag ls -lth /tmp/gemini_test_responses/

# View a response
docker exec ai-chatbot-rag cat /tmp/gemini_test_responses/test_gen_*.json

# Copy response file to local machine
docker cp ai-chatbot-rag:/tmp/gemini_test_responses/test_gen_20251214_194300.json ./
```

---

## 📊 API Endpoints Reference

### Test Creation
- `POST /api/v1/tests/generate` - Generate test from PDF
- `POST /api/v1/tests/generate/general` - Generate general knowledge test
- `GET /api/v1/tests/{test_id}/status` - Check generation status

### Test Taking
- `GET /api/v1/tests/{test_id}` - Get test (owner/shared/public view)
- `POST /api/v1/tests/{test_id}/start` - Start test session
- `POST /api/v1/tests/{test_id}/submit` - Submit test answers

### Test Results
- `GET /api/v1/me/submissions` - List user submissions
- `GET /api/v1/me/submissions/{submission_id}` - Get submission results

### Test Grading
- `GET /api/v1/grading/tests/{test_id}/queue` - Get grading queue
- `POST /api/v1/grading/submissions/{submission_id}/grade-essay` - Grade single essay
- `POST /api/v1/grading/submissions/{submission_id}/grade-all-essays` - Grade all essays

### Marketplace
- `GET /api/marketplace/tests` - Browse marketplace tests
- `GET /api/marketplace/tests/{test_id}` - Get marketplace test details
- `POST /api/marketplace/tests/{test_id}/purchase` - Purchase test

---

## 🔐 Authentication

### Firebase Authentication

All API requests require Firebase ID token in header:

```
Authorization: Bearer <firebase-id-token>
```

### User Context

Backend extracts user info from token:
- `uid`: Firebase user ID (used as `creator_id`, `user_id`)
- `email`: User email
- `name`: Display name

---

## 🔐 Security Considerations

### Media File Access (Student Answer Attachments)

**Current Status:**
- Files stored in Cloudflare R2 bucket
- URLs are **PUBLIC** by default: `https://static.wordai.pro/attachments/...`
- Anyone with the URL can access files

**Security Risks:**
- ❌ Student answers may contain sensitive information
- ❌ URLs can be shared outside platform
- ❌ No expiration on access
- ❌ Search engines may index files

**Recommended Solution: Signed URLs**
- ✅ Implemented: `generate_presigned_download_url()` in `R2StorageService`
- ✅ URLs expire after 7 days (configurable)
- ✅ Cannot access after expiration
- ✅ Unique token per generation

**Implementation Status:**
- 🟡 **Signed URL method available** (not yet used by default)
- 🔴 **Action Required:** Update upload endpoints to use signed URLs
- 🔴 **R2 Bucket:** Should be set to private (no public read)

**Migration Plan:**
1. Set R2 bucket to **private** (Cloudflare dashboard)
2. Update `generate_presigned_upload_url()` to return signed URLs
3. Update `upload_file()` to use `generate_presigned_download_url()`
4. Regenerate signed URLs on-demand when expired
5. Add endpoint: `GET /media/refresh-url/{media_id}` for expired URLs

**Example Usage:**
```python
# Generate signed URL (7 days expiration)
signed_url = r2_service.generate_presigned_download_url(
    key="attachments/file.png",
    expiration=604800  # 7 days in seconds
)
```

---

## 🐛 Common Issues & Solutions

### Issue: Test not found
**Solution:** Use ObjectId format in MongoDB queries
```javascript
// ✅ Correct
db.online_tests.findOne({_id: ObjectId("693eb0d83456aa028c4ee7fe")})

// ❌ Wrong
db.online_tests.findOne({_id: "693eb0d83456aa028c4ee7fe"})
```

### Issue: correct_answers empty
**Check:**
1. View test in database: `db.online_tests.findOne({_id: ObjectId("test-id")})`
2. Check if questions have `correct_answers` field
3. Verify normalization didn't clear it (fixed in commit 7757d9c)

### Issue: Frontend not showing results
**Check:**
1. User access type (owner/shared/public)
2. GET /api/v1/tests/{test_id} response includes questions
3. Questions include correct_answers for owner view

### Issue: Gemini response files missing
**Check:**
1. Test was created AFTER deployment of logging code
2. Directory exists: `docker exec ai-chatbot-rag ls /tmp/gemini_test_responses/`
3. Permissions: Container has write access to /tmp/

---

## 📝 Code Conventions

### Question Types

All question types use unified `correct_answers` field:

| Type | correct_answers Format |
|------|----------------------|
| `mcq` | `["A"]` |
| `mcq_multiple` | `["A", "C"]` |
| `matching` | `[{"left_key": "1", "right_key": "A"}]` |
| `completion` | `[{"blank_key": "1", "answers": ["text"]}]` |
| `sentence_completion` | `["word", "variation"]` |
| `short_answer` | `["answer", "variation"]` |

### Legacy Fields (Deprecated)

- ❌ `correct_answer_key` (single MCQ)
- ❌ `correct_answer_keys` (multiple MCQ)
- ❌ `correct_matches` (matching)

**Note:** Backend still accepts these for backward compatibility but converts to `correct_answers`.

---

## 🔄 State Machine

### Test Status Flow

```
creating → generating → ready
         ↓
       failed
```

### Grading Status Flow

```
auto_graded (MCQ only)
     ↓
pending_grading (has essays)
     ↓
partially_graded (some graded)
     ↓
fully_graded (all graded)
```

---

## 📚 Related Documentation

- **Question Types:** See `QUESTION_TYPES_JSON_SCHEMA.md`
- **API Docs:** Available at `/docs` endpoint
- **Environment:** See `.env` file (not in repo)

---

## 🆘 Emergency Rollback

If deployment fails:

```bash
# 1. Check previous image
docker images | grep wordai-aiservice

# 2. Stop current container
docker stop ai-chatbot-rag
docker rm ai-chatbot-rag

# 3. Start with previous image
docker run -d --name ai-chatbot-rag \
  --network wordai-network \
  -p 8000:8000 \
  lekompozer/wordai-aiservice:<previous-commit-hash>

# 4. Verify health
curl http://localhost:8000/health
```

---

## 📞 Key Commands Cheat Sheet

```bash
# Quick health check
curl http://localhost:8000/health

# Check container status
docker ps | grep ai-chatbot-rag

# Count tests in database
docker exec mongodb mongosh -u <user> -p <pass> \
  --authenticationDatabase admin ai_service_db --quiet --eval \
  'db.online_tests.countDocuments()'

# Find test by title
docker exec mongodb mongosh -u <user> -p <pass> \
  --authenticationDatabase admin ai_service_db --quiet --eval \
  'db.online_tests.find({title: {$regex: "search-term", $options: "i"}}).limit(5).forEach(t => print(t._id + " - " + t.title))'

# Check recent submissions
docker exec mongodb mongosh -u <user> -p <pass> \
  --authenticationDatabase admin ai_service_db --quiet --eval \
  'db.test_submissions.find().sort({submitted_at: -1}).limit(5).forEach(s => print(s._id + " - " + s.test_id + " - " + s.score))'
```

---

**End of System Reference**
