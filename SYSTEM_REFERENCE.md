# System Reference - Backend Infrastructure

**Last Updated:** January 10, 2026
**Purpose:** Complete reference for AI agents and developers working with the backend system

**Related Documentation:**
- **R2_STORAGE_GUIDELINES.md** - Cloudflare R2 storage patterns and CDN usage (✅ READ THIS FOR R2!)
- **REDIS_STATUS_PATTERN.md** - Redis job status tracking patterns
- **BOOK_CHAPTER_API_SPECS.md** - Book chapter API specifications

---

## 🤖 AI Model Configuration

### Claude Sonnet 4.5 - MANDATORY VERSION

**⚠️ CRITICAL RULE:** The entire system MUST use Claude Sonnet 4.5 version `20250929` ONLY.

**Model Names by Provider:**
- **Vertex AI:** `claude-sonnet-4-5@20250929` (with `@` symbol)
- **Claude API:** `claude-sonnet-4-5-20250929` (with dashes `-`)

**Environment Variables:**
```bash
CLAUDE_MODEL=claude-sonnet-4-5-20250929
CLAUDE_SONNET_MODEL=claude-sonnet-4-5-20250929
```

**DO NOT use:**
- ❌ Claude 3.5 Sonnet (any version)
- ❌ `claude-3-5-sonnet-20241022`
- ❌ Any other Claude version

**Configuration Files:**
- `config/config.py` - Default model settings
- `.env` - Production environment variables
- `development.env.template` - Development template

**Services using Claude:**
- `slide_ai_service.py` - Slide formatting (Vertex AI primary, API fallback)
- `slide_ai_generation_service.py` - Slide generation
- `claude_service.py` - General Claude operations

**Vertex AI Configuration:**
- Project: `wordai-6779e`
- Region: `asia-southeast1`
- Credentials: `/app/wordai-6779e-ed6189c466f1.json`
- Fallback: Anthropic API key on 429 quota errors

---

## 🐳 Docker Configuration

### Container Names

| Container Name | Service | Purpose |
|---------------|---------|---------|
| `nginx-gateway` | Reverse Proxy | Nginx 1.26 - HTTPS, rate limiting, security |
| `ai-chatbot-rag` | Backend API | Main FastAPI application |
| `payment-service` | Payment API | Node.js payment service |
| `mongodb` | Database | MongoDB 7.0 database server |
| `redis-server` | Cache/Queue | Redis 7 - job queue, caching |
| `slide-format-worker` | Worker | Slide formatting background worker |
| `slide-generation-worker` | Worker | Slide generation background worker |
| `ai-editor-worker` | Worker | AI editor background worker |
| `slide-narration-subtitle-worker` | Worker | Subtitle generation background worker |
| `slide-narration-audio-worker` | Worker | Audio narration generation worker |
| `chapter-translation-worker` | Worker | Chapter translation worker |

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

### Nginx Configuration Updates

**When to deploy:**
- **Nginx config changes ONLY** → Use `./restart-nginx.sh` (5 seconds, no rebuild)
- **Python code changes** → Use `./deploy-compose-with-rollback.sh` (2-3 minutes, full rebuild)

**Update nginx config (fast path):**
```bash
# Local: Edit nginx/conf.d/ai-wordai.conf
# Then run:
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && ./restart-nginx.sh'"

# What it does:
# 1. git pull (get latest config)
# 2. nginx -t (test config syntax)
# 3. nginx -s reload (graceful reload, no downtime)
```

**Manual nginx commands:**
```bash
# Test nginx config (ALWAYS do this before reload)
docker exec nginx-gateway nginx -t

# Reload nginx (graceful, no dropped connections)
docker exec nginx-gateway nginx -s reload

# View nginx logs
docker logs nginx-gateway -f --tail 100

# Check nginx status
docker ps --filter name=nginx-gateway
```

**Nginx config locations:**
- Main config: `nginx/nginx.conf`
- Site config: `nginx/conf.d/ai-wordai.conf`
- SSL certs: `/etc/letsencrypt/live/ai.wordai.pro/`

**Common nginx operations:**
```bash
# Check which routes are configured
docker exec nginx-gateway cat /etc/nginx/conf.d/ai-wordai.conf | grep "location"

# Check rate limiting zones
docker exec nginx-gateway cat /etc/nginx/conf.d/ai-wordai.conf | grep "limit_req_zone"

# View real-time access logs
docker exec nginx-gateway tail -f /var/log/nginx/access.log

# Count 404 errors by IP
docker logs nginx-gateway 2>&1 | grep "404" | awk '{print $1}' | sort | uniq -c | sort -rn
```

---

## � Production Server Access (SSH)

### Server Information

**Server IP:** `104.248.147.155`
**SSH User:** `root` (login as root, then switch to `hoile`)
**Working Directory:** `/home/hoile/wordai`
**User for Operations:** `hoile`

### SSH Connection Pattern

**Standard SSH command template:**
```bash
ssh root@104.248.147.155 "su - hoile -c 'COMMAND_HERE'"
```

**Common Operations:**

```bash
# Deploy latest code
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull origin main && ./deploy-compose-with-rollback.sh'"

# Quick restart nginx only (no rebuild)
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && ./restart-nginx.sh'"

# Check Docker containers
ssh root@104.248.147.155 "docker ps"

# View logs
ssh root@104.248.147.155 "docker logs ai-chatbot-rag -f --tail 100"

# Execute command in container
ssh root@104.248.147.155 "docker exec ai-chatbot-rag COMMAND"

# Access MongoDB
ssh root@104.248.147.155 "su - hoile -c 'docker exec mongodb mongosh ai_service_db -u ai_service_user -p ai_service_2025_secure_password --authenticationDatabase admin'"

# Access Redis
ssh root@104.248.147.155 "docker exec redis-server redis-cli"
```

**File Operations:**

```bash
# Check credentials file (production)
ssh root@104.248.147.155 "su - hoile -c 'ls -lh /home/hoile/wordai/wordai-6779e-ed6189c466f1.json'"

# View env file (production)
ssh root@104.248.147.155 "su - hoile -c 'cat /home/hoile/wordai/.env | grep MONGODB'"

# Check container file
ssh root@104.248.147.155 "docker exec ai-chatbot-rag ls -lh /app/wordai-6779e-ed6189c466f1.json"
```

### Deployment Scripts

**Location:** `/home/hoile/wordai/`

| Script | Purpose | Rebuild | Duration | When to Use |
|--------|---------|---------|----------|-------------|
| `deploy-compose-with-rollback.sh` | Full deployment | Yes | 2-3 min | Code changes, new features |
| `restart-nginx.sh` | Nginx reload only | No | 5 sec | Nginx config changes only |
| `deploy.sh` | Simple deploy | Yes | 2-3 min | Legacy, use deploy-compose instead |

**deploy-compose-with-rollback.sh workflow:**
1. Tags current image as backup
2. Builds new image
3. Stops old containers
4. Starts new containers
5. Waits 10s for health check
6. Auto-rollback if health check fails

---

## �🗄️ MongoDB Database

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
- [ ] If using `get_mongodb()` from config.config: Use `DBManager()` instead
- [ ] If undefined `db` variable: Use `doc_manager.db` or create `DBManager()`
- [ ] Test database operations still work
- [ ] Commit with message: `fix: Use DBManager pattern for MongoDB connection`

#### 🐛 Common Migration Errors & Fixes

**Error: `name 'get_mongodb_service' is not defined`**
```python
# ❌ WRONG - Missing import or using in wrong context
cursor = get_mongodb_service().db.slide_narrations.find(...)

# ✅ CORRECT - Use existing db variable (already initialized globally)
# In most API files: db = DBManager().db at top
cursor = db.slide_narrations.find(...)

# ✅ ALTERNATIVE - If no global db, create DBManager
db_manager = DBManager()
cursor = db_manager.db.slide_narrations.find(...)
```

**Error: `name 'db' is not defined`**
```python
# ❌ WRONG - Using undefined db variable
narration_count = db.slide_narrations.count_documents(...)

# ✅ CORRECT - Use manager's db instance
# If you have doc_manager already:
narration_count = doc_manager.db.slide_narrations.count_documents(...)

# If you have db_manager already:
narration_count = db_manager.db.slide_narrations.count_documents(...)
```

**Error: `ModuleNotFoundError: No module named 'src.database.mongodb_service'`**
```python
# ❌ WRONG - Non-existent module
from src.database.mongodb_service import get_mongodb_service

# ✅ CORRECT - Use DBManager
from src.database.db_manager import DBManager
db_manager = DBManager()
```

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
    presentation = db.documents.find_one({"document_id": presentation_id})
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
    r2_url="https://static.wordai.pro/audio/abc.mp3",
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

**🐛 Common LibraryManager Errors:**

**Error: `ImportError: cannot import name 'get_library_manager'`**
```python
# ❌ WRONG - No singleton function exists
from src.services.library_manager import get_library_manager
library_manager = get_library_manager()

# ✅ CORRECT - Create instance with dependencies
from src.services.library_manager import LibraryManager
from src.database.db_manager import DBManager
from src.services.r2_storage_service import get_r2_service

db_manager = DBManager()
r2_service = get_r2_service()
library_manager = LibraryManager(
    db=db_manager.db,
    s3_client=r2_service.s3_client
)
```

**Error: `TypeError: __init__() missing required positional argument: 's3_client'`**
```python
# ❌ WRONG - Missing s3_client parameter
library_manager = LibraryManager(db=db)

# ✅ CORRECT - Both db and s3_client required
library_manager = LibraryManager(
    db=db_manager.db,
    s3_client=r2_service.s3_client
)
```

**Error: `AttributeError: 'R2StorageService' object has no attribute 'cdn_url'`**
```python
# ❌ WRONG - Property name is public_url, not cdn_url
from src.services.r2_storage_service import get_r2_service
r2_service = get_r2_service()
cdn_url = f"{r2_service.cdn_url}/{object_key}"  # ❌ AttributeError!

# ✅ CORRECT - Use public_url property
cdn_url = f"{r2_service.public_url}/{object_key}"  # ✅ Works!

# Available R2 service properties:
r2_service.s3_client        # boto3 S3 client
r2_service.bucket_name      # "wordai"
r2_service.public_url       # "https://static.wordai.pro" ← USE THIS!
r2_service.endpoint_url     # Cloudflare R2 endpoint

# Note: cdn_url is OK as LOCAL VARIABLE name
cdn_url = f"{r2_service.public_url}/{key}"  # ✅ Variable name is fine
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
    "r2_url": "https://static.wordai.pro/audio/abc123.mp3",
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
    "r2_url": "https://static.wordai.pro/images/xyz789.png",
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
    "r2_url": "https://static.wordai.pro/videos/def456.mp4",
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

### 📚 Book Collections Structure (CRITICAL)

**⚠️ IMPORTANT:** The system uses `online_books` collection, NOT `guide_books` (legacy/deprecated).

#### Core Collections

##### 1. `online_books` - Book Metadata ✅ (PRIMARY)

**Purpose:** Store book information (title, description, settings)

**Key Fields:**
```python
{
    "_id": ObjectId("..."),
    "book_id": "book_79fff2603ee4",      # ✅ Use this for queries!
    "user_id": "firebase_uid",           # Owner
    "title": "Introduction to AI",
    "description": "Learn AI basics",
    "cover_image": "https://static.wordai.pro/covers/abc.jpg",
    "language": "vi",                    # Primary language
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
    "is_deleted": False,
    "settings": {
        "reading_mode": "scroll",        # scroll | page
        "font_size": "medium",
        "theme": "light"
    }
}
```

**Query Patterns:**
```python
from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db

# ✅ CORRECT: Query by book_id
book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})

# ✅ CORRECT: List user's books
books = db.online_books.find({"user_id": user_id, "is_deleted": False})

# ❌ WRONG: Using _id field
book = db.online_books.find_one({"_id": book_id})  # Won't work!

# ❌ WRONG: Using guide_books collection
book = db.guide_books.find_one({"_id": book_id})   # Deprecated!
```

##### 2. `book_chapters` - Chapter Content

**Purpose:** Store chapter structure and content in multiple formats

**Content Modes:**
- `inline` - HTML/JSON text content (legacy)
- `pdf_pages` - PDF extracted as A4 JPG pages (1240×1754px @ 150 DPI)
- `image_pages` - Image sequences (manga, scanned books)

**Schema:**
```python
{
    "_id": "chapter_abc123",
    "book_id": "book_79fff2603ee4",      # Links to online_books
    "user_id": "firebase_uid",
    "title": "Chapter 1: Introduction",
    "chapter_number": 1,
    "content_mode": "pdf_pages",         # inline | pdf_pages | image_pages

    # PDF/Image pages mode
    "pages": [
        {
            "page_number": 1,
            "image_url": "https://static.wordai.pro/studyhub/chapters/chapter_abc123/page-1.jpg",
            "width": 1240,
            "height": 1754,
            "thumbnail_url": "https://.../page-1-thumb.jpg"
        },
        # ... more pages
    ],

    # Inline mode (legacy)
    "content": "<p>Chapter content...</p>",

    # Manga-specific settings
    "manga_settings": {
        "reading_direction": "rtl",      # rtl (right-to-left) | ltr
        "page_layout": "single"          # single | double
    },

    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
}
```

##### 3. `user_files` - File Uploads (PDFs, ZIPs)

**Purpose:** Store uploaded files before processing

**Schema:**
```python
{
    "_id": ObjectId("..."),
    "file_id": "file_1da6ba240601_part1_1767932029",  # ✅ Use this for queries!
    "user_id": "firebase_uid",
    "filename": "textbook.pdf",
    "original_name": "AI Textbook.pdf",
    "file_type": ".pdf",                 # File extension with dot
    "file_url": "https://r2.wordai.vn/files/user123/root/file_abc/textbook.pdf",
    "file_size": 5242880,                # Bytes
    "uploaded_at": datetime.utcnow(),
    "is_deleted": False,
    "r2_key": "files/user123/root/file_abc/textbook.pdf",
    "folder_id": "root"                  # Folder location
}
```

**Query Pattern:**
```python
# ✅ CORRECT
file_doc = db.user_files.find_one({
    "file_id": file_id,
    "user_id": user_id,
    "is_deleted": False
})

# Access fields
file_type = file_doc.get("file_type")  # e.g., ".pdf"
file_url = file_doc.get("file_url")     # R2 URL
```
```

**Upload Flow:**
```python
# 1. User uploads PDF via POST /api/files/upload
# 2. File saved to user_files collection
# 3. Create chapter from PDF:

from src.services.book_chapter_manager import BookChapterManager

chapter_manager = BookChapterManager()
chapter = await chapter_manager.create_chapter_from_pdf(
    book_id="book_79fff2603ee4",
    file_id="file_1da6ba240601_part1_1767932029",
    user_id=user_id,
    chapter_title="Chapter 1"
)
# 4. PDF pages extracted as JPG images to R2
# 5. Chapter saved with pages array
```

#### Common Patterns

**Create Book:**
```python
from src.services.book_manager import UserBookManager

book_manager = UserBookManager(db)
book = book_manager.create_book(
    user_id=user_id,
    title="My Book",
    description="Book description",
    language="vi"
)
book_id = book["book_id"]
```

**Validate Book Ownership:**
```python
# ✅ CORRECT: Use online_books with book_id
book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})
if not book:
    raise HTTPException(403, "Book not found or access denied")

# ❌ WRONG: Using guide_books
book = db.guide_books.find_one({"_id": book_id, "user_id": user_id})
```

**Storage Paths:**
- PDFs: `files/{user_id}/root/{file_id}/{filename}.pdf` (private)
- Chapter pages: `studyhub/chapters/{chapter_id}/page-{N}.jpg` (public CDN)
- Thumbnails: `studyhub/chapters/{chapter_id}/page-{N}-thumb.jpg` (public CDN)

---

### � File Upload & Gemini Integration Pattern (CRITICAL)

**When implementing features that:**
1. Accept user file uploads (PDF, images, etc.)
2. Send files to Gemini API for processing
3. Need to retrieve uploaded files

**⚠️ MANDATORY: Use `user_manager.get_file_by_id()` pattern**

#### ✅ CORRECT: Standard File Upload Workflow

```python
from src.services.user_manager import get_user_manager
from src.services.file_download_service import FileDownloadService
import google.generativeai as genai

# 1. Get file metadata from database
user_manager = get_user_manager()
file_doc = user_manager.get_file_by_id(file_id, user_id)

if not file_doc:
    raise HTTPException(
        status_code=404,
        detail="File not found. Please upload file first via /api/files/upload"
    )

# 2. Validate file type
file_type = file_doc.get("file_type", "").lower()
if file_type != ".pdf":
    raise HTTPException(
        status_code=400,
        detail=f"Invalid file type: {file_type}. Only PDF files are supported."
    )

# 3. Check file size (optional but recommended)
file_size = file_doc.get("file_size_bytes", 0)
max_size = 20 * 1024 * 1024  # 20MB
if file_size > max_size:
    raise HTTPException(
        status_code=400,
        detail=f"File too large: {file_size/1024/1024:.1f}MB. Maximum allowed: 20MB"
    )

# 4. Download file from R2 storage
file_download_service = FileDownloadService()
r2_key = file_doc.get("r2_key")

file_bytes = await file_download_service.download_file_from_r2(r2_key)

if not file_bytes:
    raise HTTPException(
        status_code=500,
        detail="Failed to download file from storage"
    )

# 5. Upload to Gemini Files API (for PDF analysis)
genai.configure(api_key=APP_CONFIG["gemini_api_key"])

# Create a temporary file for Gemini upload
import tempfile
import os

with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
    temp_file.write(file_bytes)
    temp_pdf_path = temp_file.name

try:
    # Upload to Gemini
    gemini_file = genai.upload_file(
        path=temp_pdf_path,
        display_name=file_doc.get("original_name", "document.pdf")
    )

    logger.info(f"✅ Uploaded to Gemini: {gemini_file.uri}")

    # Wait for processing
    import time
    while gemini_file.state.name == "PROCESSING":
        time.sleep(2)
        gemini_file = genai.get_file(gemini_file.name)

    if gemini_file.state.name == "FAILED":
        raise Exception(f"Gemini file processing failed: {gemini_file.state}")

    # 6. Use file with Gemini model
    model = genai.GenerativeModel("gemini-2.0-flash-exp")

    response = model.generate_content([
        gemini_file,
        "Analyze this PDF and extract key information..."
    ])

    result = response.text

finally:
    # Cleanup temporary file
    if os.path.exists(temp_pdf_path):
        os.unlink(temp_pdf_path)

# 7. Return result
return {"analysis": result}
```

#### File Collections Structure

**Collection:** `user_files` (primary) or `library_files` (library manager)

**`user_manager.get_file_by_id()` searches:**
- Collection: `user_files`
- Filter: `{"file_id": file_id, "user_id": user_id, "is_deleted": False}`
- Returns: File document or `None`

**File Document Schema:**
```python
{
    "_id": ObjectId("..."),
    "file_id": "file_abc123",           # Unique file identifier
    "user_id": "firebase_uid",          # Owner
    "original_name": "document.pdf",    # Original filename
    "file_type": ".pdf",                # Extension with dot
    "file_size_bytes": 1048576,         # Size in bytes
    "r2_key": "files/user123/doc.pdf",  # R2 storage path
    "r2_url": "https://...",            # Public/signed URL
    "is_deleted": False,                # Soft delete flag
    "uploaded_at": ISODate("..."),
    "metadata": {
        "mime_type": "application/pdf",
        "source": "upload"
    }
}
```

#### ❌ WRONG: Direct Collection Query

```python
# ❌ NEVER do this - collection 'files' doesn't exist
files_collection = db["files"]
file_doc = files_collection.find_one({
    "file_id": file_id,
    "user_id": user_id
})
```

#### Working Examples in Codebase

**Example 1: Slide Analysis from PDF** (`slide_ai_generation_routes.py`)
```python
@router.post("/analyze-from-pdf")
async def analyze_slide_from_pdf(request: AnalyzeSlideFromPdfRequest):
    # ✅ CORRECT
    user_manager = get_user_manager()
    file_doc = user_manager.get_file_by_id(request.file_id, user_info["uid"])

    # Download and process...
```

**Example 2: Online Test from File** (`test_creation_routes.py`)
```python
@router.post("/generate-test-from-file")
async def generate_test_from_file(request: TestGenerationRequest):
    # ✅ CORRECT
    user_manager = get_user_manager()
    file_info = user_manager.get_file_by_id(request.source_id, user_info["uid"])

    # Process file...
```

#### Key Points

1. **Always use `user_manager.get_file_by_id()`** - Never query `db["files"]` directly
2. **Collection is `user_files`** - Managed by user_manager service
3. **Include user_id** - Ensures users can only access their own files
4. **Check `is_deleted`** - get_file_by_id filters out soft-deleted files automatically
5. **Download via FileDownloadService** - Handles R2 authentication and errors
6. **Cleanup temp files** - Always delete temporary files after Gemini upload

---

### �💰 Points Management Pattern (MANDATORY)

**All AI operations MUST check and deduct points before execution.**

#### ⚠️ CRITICAL: Points Storage Architecture

**The system uses TWO separate collections for points - DO NOT confuse them!**

##### 1. `users` Collection - Display Only (❌ DO NOT use for payment validation)
```javascript
{
  email: "user@example.com",
  firebase_uid: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  points: 2005,  // ← Frontend display ONLY, NOT source of truth!
  subscription_plan: "vip"  // ← Also display only
}
```
**Purpose:** Frontend UI display, legacy compatibility
**DO NOT USE FOR:** Payment validation, points checking, deduction operations

##### 2. `user_subscriptions` Collection - SOURCE OF TRUTH (✅ ALWAYS use this)
```javascript
{
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  plan: "vip",  // ← Real subscription tier
  points_total: 2515,  // ← Total points purchased
  points_used: 510,  // ← Total points consumed
  points_remaining: 2005,  // ← ACTUAL balance (SOURCE OF TRUTH!)
  is_active: true,
  started_at: ISODate("2025-11-06T18:55:40.177Z"),
  expires_at: ISODate("2026-02-04T18:55:40.176Z"),
  storage_limit_mb: 51200,
  // ... other subscription limits
}
```
**Purpose:** Payment validation, points checking, subscription management
**ALWAYS USE FOR:** All payment operations, points deduction, subscription checks

##### Why Two Collections?

**Historical Reason:** `users.points` existed first for UI display. Payment system evolved to use separate `user_subscriptions` for transaction tracking and subscription management.

**CRITICAL Rules:**
- ✅ **PointsService** (`src/services/points_service.py`) ALWAYS queries `user_subscriptions.points_remaining`
- ✅ **Payment validation** ALWAYS checks `user_subscriptions.plan` and `user_subscriptions.is_active`
- ✅ **Admin user updates** MUST update BOTH collections:
  - `users.points` (for frontend display)
  - `user_subscriptions.points_remaining` (for actual payment validation)
- ❌ **NEVER** check `users.points` for payment validation
- ❌ **NEVER** assume updating `users.points` alone will work

**Example Admin Update (CORRECT):**
```bash
# Update BOTH collections!
# 1. Update users collection (frontend display)
db.users.updateOne(
  {email: "user@example.com"},
  {$set: {points: 2005, subscription_plan: "vip"}}
)

# 2. Update user_subscriptions collection (actual payment check)
db.user_subscriptions.updateOne(
  {user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2"},
  {$set: {points_remaining: 2005, plan: "vip", updated_at: new Date()}}
)
```

---

#### Standard Points Flow

```python
from src.services.points_service import get_points_service
from fastapi import HTTPException

# 1. Get points service (automatically uses user_subscriptions collection)
points_service = get_points_service()

# 2. Define operation cost
POINTS_COST = 2  # See SERVICE_POINTS_COST in points_service.py

# 3. Check balance BEFORE operation (checks user_subscriptions.points_remaining)
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

### MongoDB Commands (Production)

**Access MongoDB shell:**
```bash
# From SSH
ssh root@104.248.147.155 "su - hoile -c 'docker exec mongodb mongosh ai_service_db -u ai_service_user -p ai_service_2025_secure_password --authenticationDatabase admin'"

# Or short version after SSH
docker exec mongodb mongosh ai_service_db -u ai_service_user -p ai_service_2025_secure_password --authenticationDatabase admin
```

**Credentials:**
- Database: `ai_service_db`
- Username: `ai_service_user`
- Password: `ai_service_2025_secure_password`
- Auth Database: `admin`

**Common Queries:**

```javascript
// Count documents in collection
db.narration_audio_jobs.countDocuments()

// Find recent jobs
db.narration_audio_jobs.find().sort({created_at: -1}).limit(5).pretty()

// Find specific job
db.narration_audio_jobs.find({_id: "job-id-here"}).pretty()

// Find jobs by user
db.narration_audio_jobs.find({user_id: "user-id-here"}).pretty()

// Find jobs by status
db.narration_audio_jobs.find({status: "processing"}).pretty()

// Delete old jobs
db.narration_audio_jobs.deleteMany({status: "queued", created_at: {$lt: new Date("2025-12-28")}})

// Delete specific job
db.narration_audio_jobs.deleteOne({_id: "job-id-here"})

// Update job status
db.narration_audio_jobs.updateOne(
  {_id: "job-id-here"},
  {$set: {status: "failed", error: "Manual intervention"}}
)

// List all collections
db.getCollectionNames()

// Count presentations
db.documents.countDocuments()

// Find presentation by ID
db.documents.findOne({document_id: "doc_abc123"})

// Find user's presentations
db.documents.find({user_id: "user-id-here"}).sort({created_at: -1}).limit(10)

// Check subtitle documents
db.presentation_subtitles.find({presentation_id: "doc_abc123"}).pretty()

// Check audio files
db.presentation_audio.find({subtitle_id: "subtitle-id-here"}).pretty()

// List indexes for collection
db.narration_audio_jobs.getIndexes()

// Explain query performance
db.narration_audio_jobs.find({status: "processing"}).explain("executionStats")
```

**One-line Commands (from SSH):**

```bash
# Count jobs
ssh root@104.248.147.155 "su - hoile -c 'docker exec mongodb mongosh ai_service_db -u ai_service_user -p ai_service_2025_secure_password --authenticationDatabase admin --eval \"db.narration_audio_jobs.countDocuments()\"'"

# Find jobs
ssh root@104.248.147.155 "su - hoile -c 'docker exec mongodb mongosh ai_service_db -u ai_service_user -p ai_service_2025_secure_password --authenticationDatabase admin --eval \"db.narration_audio_jobs.find().limit(5).pretty()\"'"

# Delete specific job
ssh root@104.248.147.155 "su - hoile -c 'docker exec mongodb mongosh ai_service_db -u ai_service_user -p ai_service_2025_secure_password --authenticationDatabase admin --eval \"db.narration_audio_jobs.deleteOne({_id: \\\"job-id-here\\\"})\"'"
```

---

## 📚 Slide Narration System - Database Structure

### Overview

The narration system supports **multi-language** subtitles and audio for presentations. Each language can have multiple versions, and each version links to merged audio with slide timestamps.

**Key Collections:**
1. `documents` - Presentation metadata and slide data
2. `presentation_subtitles` - Subtitle versions per language
3. `presentation_audio` - Audio files with slide timestamps
4. `video_export_jobs` - Video export jobs

### Critical Understanding

⚠️ **IMPORTANT:** Presentations using outline versions store slides in `slide_content` (JSON string), NOT in `slide_backgrounds` array!

**DO NOT use `slide_backgrounds` for slide count!**
- `slide_backgrounds` may only be `[{}]` (1 element)
- Actual slide count comes from `audio.slide_timestamps` array
- Each timestamp represents one slide's duration

### Collection Relationships

```
documents (presentation)
    ↓
    ├── presentation_subtitles (multiple: per language × version)
    │       ↓ (via merged_audio_id)
    │       └── presentation_audio (merged audio with timestamps)
    │
    └── slide_outline_versions (optional: if using outline version)
            └── slides array in slide_content (JSON)
```

### 1. documents Collection

**Purpose:** Presentation metadata and slide structure

**Key Fields:**
```javascript
{
  "_id": ObjectId("..."),
  "document_id": "doc_c49e8af18c03",  // ✅ Use this for queries!
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "document_type": "slide",
  "title": "Giới thiệu về Generative AI...",

  // ══════════════════════════════════════════════════
  // SLIDE ELEMENTS - UPDATED 2026-01-06
  // ══════════════════════════════════════════════════

  // ✅ PRIMARY FIELD: Complete slide elements (ALL slides)
  "slide_elements": [  // Array of slide with visual elements
    {
      "slideIndex": 0,  // Slide number (0-based)
      "elements": [     // Visual elements on this slide
        {
          "id": "image-1767635679829-dmvrlcmx9",
          "type": "image",  // "image" | "text" | "shape" | "chart"
          "x": 91.66666666666667,     // Position X (pixels)
          "y": 33.33333333333333,     // Position Y (pixels)
          "width": 190,               // Width (pixels)
          "height": 143,              // Height (pixels)
          "zIndex": 100,              // Layer order
          "src": "data:image/png;base64,...",  // Image data/URL
          "objectFit": "contain",
          "opacity": 1
        }
        // ... more elements
      ]
    },
    // ... up to 43 slides (all slides with elements)
  ],

  // ❌ LEGACY/SECONDARY: AI-formatted slides only (SUBSET!)
  "slide_backgrounds": [  // ⚠️ Only slides that went through AI formatting
    {
      "slideIndex": 8,   // May have gaps! Not all slides!
      "elements": [],    // Usually empty or minimal
      "formatted_html": "...",  // AI-generated HTML
      "background_type": "gradient"
    },
    {
      "slideIndex": 37,  // ⚠️ Sparse array!
      "elements": []
    }
    // ⚠️ Only 3 entries vs 18+ in slide_elements!
  ],

  // ⚠️ WARNING: DO NOT use slide_backgrounds for:
  //   - Slide count (incomplete!)
  //   - Element rendering (use slide_elements!)
  //   - Public API responses (use slide_elements!)

  // Outline version (if using new system)
  "outline_version_id": "version_abc123",  // Link to slide_outline_versions

  // Slide data (if using outline version)
  "slide_content": "{\"slides\": [{...}, {...}, ...]}", // JSON string

  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

**Query Examples:**
```javascript
// Get presentation by document_id
db.documents.findOne({document_id: "doc_c49e8af18c03"})

// ══════════════════════════════════════════════════
// SLIDE ELEMENTS - CORRECT USAGE (Updated 2026-01-06)
// ══════════════════════════════════════════════════

// ✅ CORRECT - Get all slide elements
const doc = db.documents.findOne({document_id: "doc_06de72fea3d7"})
const allElements = doc.slide_elements  // Returns 18+ slides
console.log(`Total slides with elements: ${allElements.length}`)

// ✅ CORRECT - Get elements for specific slide
const slide5Elements = doc.slide_elements.find(s => s.slideIndex === 5)
if (slide5Elements) {
  console.log(`Slide 5 has ${slide5Elements.elements.length} elements`)
}

// ❌ WRONG - Don't use slide_backgrounds for elements!
const wrongElements = doc.slide_backgrounds  // Only 3 slides! Incomplete!

// ❌ WRONG - Don't use slide_backgrounds for count
const slideCount = presentation.slide_backgrounds.length  // Returns 3 instead of 43!

// ✅ CORRECT - Get from audio timestamps
const audio = db.presentation_audio.findOne({...})
const slideCount = audio.slide_timestamps.length  // Returns 30!

// ✅ CORRECT - For public API responses
const publicData = {
  slide_elements: doc.slide_elements,  // ✅ Complete data (18+ slides)
  slide_backgrounds: doc.slide_backgrounds  // ❌ Legacy/AI-only (3 slides)
}
```

### 2. presentation_subtitles Collection

**Purpose:** Subtitle versions for each language

**Key Fields:**
```javascript
{
  "_id": ObjectId("676cb85f8476e22e03e05fb7"),  // ✅ subtitle_id
  "presentation_id": "doc_c49e8af18c03",
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",

  // Language & Version
  "language": "vi",  // ISO 639-1: vi, en, zh, ja, etc.
  "version": 1,      // Increments for each regeneration

  // Link to merged audio
  "merged_audio_id": "676cb88e8476e22e03e05fc3",  // ✅ ObjectId as string

  // Subtitle data per slide
  "slides": [
    {
      "slide_index": 0,
      "subtitle": "Xin chào các bạn...",
      "start_time": 0.0,
      "end_time": 15.5,
      "narration_text": "Xin chào các bạn..."
    },
    {
      "slide_index": 1,
      "subtitle": "Hôm nay chúng ta sẽ tìm hiểu...",
      "start_time": 15.5,
      "end_time": 32.8,
      "narration_text": "Hôm nay chúng ta sẽ tìm hiểu..."
    }
    // ... 30 slides total
  ],

  "total_slides": 30,
  "created_at": ISODate("2024-12-25T17:00:00.000Z")
}
```

**Query Patterns:**
```javascript
// Get latest subtitle for language
db.presentation_subtitles.findOne(
  {presentation_id: "doc_c49e8af18c03", language: "vi"},
  {sort: {version: -1}}  // ✅ Latest version
)

// List all language versions
db.presentation_subtitles.find(
  {presentation_id: "doc_c49e8af18c03"}
).sort({language: 1, version: -1})

// Get specific subtitle by ID
db.presentation_subtitles.findOne({_id: ObjectId("676cb85f8476e22e03e05fb7")})
```

**Indexes:**
- `{presentation_id, language, version}` - For finding latest version
- `{user_id}` - For user's subtitles

### 3. presentation_audio Collection

**Purpose:** Merged audio files with slide timestamps

⚠️ **CRITICAL:** This is the **SOURCE OF TRUTH** for slide count and durations!

**Key Fields:**
```javascript
{
  "_id": ObjectId("676cb88e8476e22e03e05fc3"),  // ✅ Referenced by subtitle.merged_audio_id
  "presentation_id": "doc_c49e8af18c03",
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",

  // Language & Version (matches subtitle)
  "language": "vi",
  "version": 1,

  // Audio file
  "audio_url": "https://static.wordai.pro/audio/narrations/...",
  "audio_type": "merged_presentation",  // Full merged presentation audio (NOT "merged"!)

  // ✅ CRITICAL: Slide timestamps array
  "slide_timestamps": [
    {
      "slide_index": 0,
      "start_time": 0.0,      // Seconds from start
      "end_time": 15.5,       // Seconds from start
      "duration": 15.5        // Slide duration
    },
    {
      "slide_index": 1,
      "start_time": 15.5,
      "end_time": 32.8,
      "duration": 17.3
    }
    // ... 30 slides total
  ],

  // ✅ Use this for slide count!
  "slide_count": 30,  // = slide_timestamps.length

  // Audio metadata
  "audio_metadata": {
    "duration_seconds": 484.844,  // Total audio duration
    "format": "mp3",
    "sample_rate": 24000,
    "channels": 1,
    "bitrate": "128k"
  },

  "status": "completed",
  "created_at": ISODate("2024-12-25T17:01:00.000Z")
}
```

**Query Examples:**
```javascript
// ✅ Get merged audio by merged_audio_id (from subtitle)
db.presentation_audio.findOne({
  _id: ObjectId("69515c9484db69188e87611c")
})

// ✅ Get merged audio by presentation (with filter)
db.presentation_audio.findOne({
  presentation_id: "doc_c49e8af18c03",
  language: "vi",
  audio_type: "merged_presentation"  // ⚠️ Important: NOT "merged"!
})

// Get slide timestamps (for video export)
const audio = db.presentation_audio.findOne({...})
const slideCount = audio.slide_timestamps.length  // 30
const totalDuration = audio.audio_metadata.duration_seconds  // 875.735

// Get specific slide timing
const slide5 = audio.slide_timestamps[5]
// → {slide_index: 5, start_time: 154.8, end_time: 187.5}

// ⚠️ Production Verified (Jan 2, 2026):
// - audio_type: "merged_presentation" (NOT "merged")
// - slide_count: 30 ✅
// - slide_timestamps: 30 items ✅
// - Audio type "chunked" also exists (obsolete chunks)
```

**Indexes:**
- `{presentation_id, language, version}` - For finding audio
- `{user_id}` - For user's audio files

### 4. video_export_jobs Collection

**Purpose:** Track video export background jobs

**Key Fields:**
```javascript
{
  "_id": "export_AP4TevZWHzJXH6mr",
  "job_id": "export_AP4TevZWHzJXH6mr",
  "presentation_id": "doc_c49e8af18c03",
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",

  // Input data
  "language": "vi",
  "subtitle_id": "676cb85f8476e22e03e05fb7",  // ✅ Link to subtitle
  "audio_id": "676cb88e8476e22e03e05fc3",     // ✅ Link to audio

  // Export settings
  "export_mode": "animated",  // "optimized" or "animated"
  "settings": {
    "resolution": "1080p",
    "fps": 30,
    "crf": 25,
    "quality": "medium"
  },

  // Status tracking
  "status": "completed",  // pending → processing → completed/failed
  "progress": 100,        // 0-100
  "current_phase": "completed",  // load → screenshot → encode → upload → completed

  // Output
  "output_url": "https://static.wordai.pro/videos/exports/...",
  "library_video_id": "lib_4d702416028b",
  "file_size": 948736,  // bytes
  "duration": 33.4,     // seconds

  "created_at": ISODate("2026-01-02T13:45:23.000Z"),
  "started_at": ISODate("2026-01-02T13:45:24.000Z"),
  "completed_at": ISODate("2026-01-02T13:48:09.000Z")
}
```

### Code Patterns

#### ✅ CORRECT: Get slide count from audio (MUST use this pattern!)

```python
from src.database.db_manager import DBManager
from bson import ObjectId

db_manager = DBManager()
db = db_manager.db

# 1. Get LATEST subtitle for language (critical: sort by version DESC)
subtitle = db.presentation_subtitles.find_one(
    {"presentation_id": presentation_id, "language": "vi"},
    sort=[("version", -1)]  # ⚠️ MUST sort to get latest!
)

if not subtitle:
    raise ValueError("No subtitle found")

# 2. Check merged_audio_id exists
if not subtitle.get("merged_audio_id"):
    raise ValueError("No merged audio for this subtitle")

# 3. Get merged audio by ObjectId
audio = db.presentation_audio.find_one(
    {"_id": ObjectId(subtitle["merged_audio_id"])}
)

if not audio:
    raise ValueError("Merged audio not found")

# 4. Verify audio type (should be "merged_presentation")
if audio.get("audio_type") != "merged_presentation":
    raise ValueError(f"Wrong audio type: {audio.get('audio_type')}")

# 5. ✅ Get slide count from timestamps array
slide_timestamps = audio["slide_timestamps"]
slide_count = len(slide_timestamps)  # 30

# 6. Get total duration
audio_duration = audio["audio_metadata"]["duration_seconds"]  # 484.844

# ⚠️ Production Verified:
# - Latest subtitle version may change (v1, v2, v3...)
# - Each version has different merged_audio_id
# - MUST always query latest to get current audio
# - Timestamps may have gaps/overlaps (audio merge issues)
```

#### ❌ WRONG: Get slide count from presentation

```python
# ❌ WRONG - May return 1 instead of 30!
presentation = db.documents.find_one({"document_id": presentation_id})
slide_count = len(presentation.get("slide_backgrounds", []))  # Returns 1!
```

#### Video Export Worker Pattern

```python
async def process_task(self, task: VideoExportTask):
    # 1. Load presentation (for public token only)
    presentation = self.db.documents.find_one(
        {"document_id": task.presentation_id}
    )

    # 2. Load subtitle
    subtitle = self.db.presentation_subtitles.find_one(
        {"_id": ObjectId(task.subtitle_id)}
    )

    # 3. Load audio
    audio = self.db.presentation_audio.find_one(
        {"_id": ObjectId(task.audio_id)}
    )

    # 4. ✅ Get slide count from audio timestamps
    slide_timestamps = audio["slide_timestamps"]
    slide_count = len(slide_timestamps)  # 30
    audio_duration = audio["audio_metadata"]["duration_seconds"]

    # 5. Capture screenshots (slide_count iterations)
    for slide_idx in range(slide_count):
        await page.evaluate(f"window.goToSlide({slide_idx})")
        # ... capture screenshot

    # 6. Encode video with slide durations
    for idx, timestamp in enumerate(slide_timestamps):
        duration = timestamp["end_time"] - timestamp["start_time"]
        # ... add slide to video with correct duration
```

### Migration Notes

**Old System (Deprecated):**
- Used `slide_backgrounds` array for slide count
- Single audio file per presentation
- No language versioning

**New System (Current):**
- Use `slide_timestamps` array for slide count
- Multiple languages supported
- Version history for each language
- Merged audio with precise timestamps

**When to Use Each Field:**

| Need | Use This | Don't Use |
|------|----------|-----------|
| Slide count | `audio.slide_timestamps.length` | `slide_backgrounds.length` |
| Slide duration | `slide_timestamps[i].duration` | Calculate manually |
| Total duration | `audio_metadata.duration_seconds` | Sum of slides |
| Presentation ID | `document_id` (doc_xxx) | `_id` (ObjectId) |
| Subtitle ID | `_id` (ObjectId as string) | Custom ID |
| Audio ID | `merged_audio_id` | Direct lookup |

### Common Queries

```javascript
// Get complete narration data for presentation
const presentation_id = "doc_c49e8af18c03"
const language = "vi"

// 1. Get latest subtitle
const subtitle = db.presentation_subtitles.findOne(
  {presentation_id: presentation_id, language: language},
  {sort: {version: -1}}
)

// 2. Get merged audio
const audio = db.presentation_audio.findOne({
  _id: ObjectId(subtitle.merged_audio_id)
})

// 3. Get slide count and timestamps
const slideCount = audio.slide_timestamps.length
const totalDuration = audio.audio_metadata.duration_seconds

printjson({
  presentation_id: presentation_id,
  language: language,
  subtitle_id: subtitle._id,
  audio_id: audio._id,
  audio_url: audio.audio_url,
  slide_count: slideCount,
  total_duration: totalDuration,
  slides: audio.slide_timestamps.slice(0, 3)  // First 3 slides
})
```

**Expected Output:**
```javascript
{
  presentation_id: "doc_c49e8af18c03",
  language: "vi",
  subtitle_id: ObjectId("676cb85f8476e22e03e05fb7"),
  audio_id: ObjectId("676cb88e8476e22e03e05fc3"),
  audio_url: "https://static.wordai.pro/audio/narrations/...",
  slide_count: 30,
  total_duration: 484.844,
  slides: [
    {slide_index: 0, start_time: 0.0, end_time: 15.5, duration: 15.5},
    {slide_index: 1, start_time: 15.5, end_time: 32.8, duration: 17.3},
    {slide_index: 2, start_time: 32.8, end_time: 48.1, duration: 15.3}
  ]
}
```

---

### Redis Commands (Production)

**Access Redis CLI:**
```bash
# From SSH
ssh root@104.248.147.155 "docker exec redis-server redis-cli"

# Or after SSH to server
docker exec redis-server redis-cli
```

**Job Status Pattern (Standard for Workers):**

Redis uses key pattern: `job:{job_id}` (Hash data structure)

**Common Redis Commands:**

```bash
# List all job keys
KEYS "job:*"

# Get specific job status
HGETALL "job:abc-123-def-456"

# Check job TTL (24 hours = 86400 seconds)
TTL "job:abc-123-def-456"

# Delete specific job
DEL "job:abc-123-def-456"

# Check if job exists
EXISTS "job:abc-123-def-456"

# Get specific field from job
HGET "job:abc-123-def-456" "status"
HGET "job:abc-123-def-456" "error"

# List all keys (WARNING: slow on production)
KEYS "*"

# Count all keys
DBSIZE

# Get memory usage
INFO memory

# Check queue length
LLEN "slide_narration_audio"
LLEN "slide_format"
LLEN "chapter_translation"
LLEN "ai_editor"

# View queue items (first 5)
LRANGE "slide_narration_audio" 0 4

# Clear specific queue (DANGER!)
DEL "slide_narration_audio"

# Find jobs by pattern
KEYS "job:*abc*"

# Delete all jobs (DANGER - production data loss!)
# KEYS "job:*" | xargs redis-cli DEL  # DO NOT RUN without confirmation

# Check Redis info
INFO server
INFO stats
INFO keyspace
```

**One-line Commands (from SSH):**

```bash
# List all job keys
ssh root@104.248.147.155 "docker exec redis-server redis-cli KEYS 'job:*'"

# Get specific job
ssh root@104.248.147.155 "docker exec redis-server redis-cli HGETALL 'job:abc-123'"

# Delete job
ssh root@104.248.147.155 "docker exec redis-server redis-cli DEL 'job:abc-123'"

# Check queue length
ssh root@104.248.147.155 "docker exec redis-server redis-cli LLEN 'slide_narration_audio'"

# Get job status field
ssh root@104.248.147.155 "docker exec redis-server redis-cli HGET 'job:abc-123' 'status'"
```

**Legacy Pattern (Deprecated):**

Old workers might use: `status:{queue_name}:{task_id}` (String with JSON)
- Example: `status:slide_narration_audio:abc-123`
- Data type: String (JSON encoded)
- Use: `GET "status:slide_narration_audio:abc-123"` to retrieve

**Migration Note:**
All workers should now use `job:{job_id}` pattern with `set_job_status()` / `get_job_status()` functions.
See **Redis Worker Pattern** section below for details.

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

## � Queue Manager Patterns

### ✅ CORRECT: Queue-Based Background Processing

**Redis Queue System** (for long-running tasks like AI generation, audio processing):

```python
from src.queue.queue_dependencies import (
    get_slide_narration_audio_queue,
    get_slide_generation_queue,
    get_chapter_translation_queue,
    get_ai_editor_queue
)
from src.models.ai_queue_tasks import SlideNarrationAudioTask, SlideGenerationTask

# In API route - Queue a background task
async def generate_audio_endpoint(request: AudioRequest):
    # 1. Create job in MongoDB
    job_id = str(uuid.uuid4())
    db.narration_audio_jobs.insert_one({
        "_id": job_id,
        "status": "queued",
        "user_id": user_id,
        "created_at": datetime.utcnow()
    })

    # 2. Create task model
    task = SlideNarrationAudioTask(
        task_id=job_id,
        job_id=job_id,
        user_id=user_id,
        presentation_id=presentation_id,
        subtitle_id=subtitle_id,
        voice_config=request.voice_config.dict()
    )

    # 3. Enqueue task - ✅ CORRECT method
    queue = await get_slide_narration_audio_queue()
    success = await queue.enqueue_generic_task(task)

    if not success:
        raise HTTPException(500, "Failed to queue task")

    # 4. Return job_id for polling
    return {"job_id": job_id, "status": "queued"}
```

### ❌ INCORRECT: Queue Patterns

```python
# ❌ WRONG - enqueue() does not exist
await queue.enqueue(job_id, task.dict())
# Error: 'QueueManager' object has no attribute 'enqueue'

# ❌ WRONG - enqueue_task() is for IngestionTask only
await queue.enqueue_task(task)
# Use enqueue_generic_task() for BaseModel tasks

# ❌ WRONG - Not checking success
await queue.enqueue_generic_task(task)
# Always check: success = await queue.enqueue_generic_task(task)
```

### 📋 Queue Method Reference

| Method | Use Case | Parameter Type |
|--------|----------|----------------|
| `enqueue_generic_task(task)` | ✅ Most tasks (AI, audio, slides) | `BaseModel` |
| `enqueue_task(task)` | Document ingestion only | `IngestionTask` |
| `dequeue_task(batch_size)` | Worker processing | Returns `List[Task]` |

### 🔄 Queue-Based Flow Pattern

**1. API Endpoint (Immediate Return)**
```python
@router.post("/generate")
async def start_generation(request: Request):
    # Create job + enqueue
    job_id = create_job()
    task = GenerationTask(...)
    await queue.enqueue_generic_task(task)
    return {"job_id": job_id, "status": "queued"}
```

**2. Polling Endpoint (Check Status)**
```python
@router.get("/status/{job_id}")
async def check_status(job_id: str):
    job = db.jobs.find_one({"_id": job_id})
    if job["status"] == "completed":
        return {"status": "completed", "result": job["result"]}
    return {"status": job["status"]}
```

**3. Worker (Background Processing with Redis Status)**
```python
from src.queue.queue_manager import set_job_status

async def run():
    while True:
        task_data = await queue.dequeue_generic_task(worker_id=worker_id, timeout=5)

        if not task_data:
            await asyncio.sleep(2)
            continue

        job_id = task_data["job_id"]

        # ✅ CRITICAL: Update Redis status for realtime polling
        await set_job_status(
            redis_client=self.queue_manager.redis_client,  # ← MUST be first param
            job_id=job_id,
            status="processing",
            user_id=task_data["user_id"],
            started_at=datetime.utcnow().isoformat(),
        )

        # Also update MongoDB for persistence
        db.jobs.update_one(
            {"_id": job_id},
            {"$set": {"status": "processing"}}
        )

        try:
            # Process task
            result = await process_task(task_data)

            # ✅ Update Redis: completed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="completed",
                user_id=task_data["user_id"],
                result=result,
            )

            # Update MongoDB
            db.jobs.update_one(
                {"_id": job_id},
                {"$set": {"status": "completed", "result": result}}
            )

        except Exception as e:
            # ✅ Update Redis: failed
            await set_job_status(
                redis_client=self.queue_manager.redis_client,
                job_id=job_id,
                status="failed",
                user_id=task_data["user_id"],
                error=str(e),
            )

            db.jobs.update_one(
                {"_id": job_id},
                {"$set": {"status": "failed", "error": str(e)}}
            )
```

**⚠️ CRITICAL: Redis Status Updates**

**Why Update Redis:**
- Frontend polls Redis every 2s for realtime status
- MongoDB too slow for realtime updates
- Redis has TTL (auto-cleanup old jobs)

**❌ WRONG: Only MongoDB**
```python
# Frontend won't see updates!
db.jobs.update_one({"_id": job_id}, {"$set": {"status": "processing"}})
```

**✅ CORRECT: Both Redis (realtime) + MongoDB (persistence)**
```python
await set_job_status(redis_client=self.queue_manager.redis_client, ...)
db.jobs.update_one(...)
```

### 🎯 Common Queue Issues & Fixes

**Issue 1: AttributeError: 'QueueManager' object has no attribute 'enqueue'**
```python
# ❌ WRONG
await queue.enqueue(job_id, task.dict())

# ✅ CORRECT
success = await queue.enqueue_generic_task(task)
```

**Issue 2: Task not processing in worker**
```python
# Check queue name matches
# API: get_slide_narration_audio_queue() → queue: slide_narration_audio
# Worker: QueueManager("slide_narration_audio") → same queue name

# Verify worker is running
docker ps | grep narration-audio-worker
```

**Issue 3: Job stuck in "queued" status**
```python
# Check worker logs
docker logs slide-narration-audio-worker -f

# Verify Redis connection
docker exec redis-server redis-cli KEYS "slide_narration_audio*"
```

**Issue 4: AttributeError: 'QueueManager' object has no attribute 'redis'**
```python
# ❌ WRONG - Attribute name is redis_client
await set_job_status(
    redis_client=self.queue_manager.redis,  # ❌ NO 'redis' attribute
    ...
)

# ✅ CORRECT - Use redis_client
await set_job_status(
    redis_client=self.queue_manager.redis_client,  # ✅ Correct attribute
    job_id=job_id,
    status="processing",
    user_id=user_id,
)
```

**Issue 5: TypeError: set_job_status() got multiple values for argument 'redis_client'**
```python
# ❌ WRONG - redis_client must be FIRST positional argument
await set_job_status(
    job_id=job_id,
    status="processing",
    redis_client=self.queue_manager.redis_client,  # ❌ Wrong order
)

# ✅ CORRECT - redis_client FIRST
await set_job_status(
    redis_client=self.queue_manager.redis_client,  # ✅ First param
    job_id=job_id,
    status="processing",
    user_id=user_id,
)

---

## 🔄 Redis Worker Pattern - System Standard

**Last Updated:** December 28, 2025

### Overview

**ALL async jobs MUST use Redis for real-time status tracking**, except:
- Slide generation (uses MongoDB `documents` collection)
- Translation jobs (uses MongoDB `translation_jobs` collection - long-running)

### ✅ Standard Pattern: `set_job_status()` / `get_job_status()`

**Redis Key Pattern:** `job:{job_id}` (Hash data structure, 24h TTL)

### Worker Implementation (Status Updates)

**Import:**
```python
from src.queue.queue_manager import set_job_status
```

**Usage in Worker:**
```python
async def process_task(self, task):
    job_id = task.job_id

    # 1. Status: processing
    await set_job_status(
        redis_client=self.queue_manager.redis_client,  # ✅ MUST be first param
        job_id=job_id,
        status="processing",
        user_id=task.user_id,
        started_at=datetime.utcnow().isoformat(),
        # Add any task-specific fields
        presentation_id=task.presentation_id,
        subtitle_id=task.subtitle_id,
    )

    try:
        # Process task
        result = await self.service.generate_something(...)

        # 2. Status: completed
        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=job_id,
            status="completed",
            user_id=task.user_id,
            # Add result fields
            formatted_html=result["html"],
            audio_count=len(result["files"]),
            completed_at=datetime.utcnow().isoformat(),
        )

        return True

    except Exception as e:
        # 3. Status: failed
        await set_job_status(
            redis_client=self.queue_manager.redis_client,
            job_id=job_id,
            status="failed",
            user_id=task.user_id,
            error=str(e),
            failed_at=datetime.utcnow().isoformat(),
        )

        return False
```

### API Endpoint Implementation (Status Polling)

**Import:**
```python
from src.queue.queue_manager import get_job_status
from src.queue.queue_dependencies import get_QUEUE_NAME_queue
```

**Usage in Endpoint:**
```python
@router.get("/jobs/{job_id}")
async def get_job_status_endpoint(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Poll job status - check Redis first for real-time updates"""
    try:
        user_id = current_user["uid"]

        # Get queue manager (provides redis_client)
        queue = await get_slide_format_queue()  # or get_chapter_translation_queue(), etc.

        # Get job from Redis (real-time status)
        job = await get_job_status(queue.redis_client, job_id)

        if not job:
            # Job expired (24h TTL) or not found
            # Optional: Check MongoDB backup
            job = db.jobs.find_one({"_id": job_id})

            if not job:
                raise HTTPException(404, "Job not found")

        # Verify ownership
        if job.get("user_id") != user_id:
            raise HTTPException(403, "Access denied")

        # Return job data
        return {
            "job_id": job["job_id"],
            "status": job["status"],  # pending/processing/completed/failed
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            # Include result fields based on status
            "result": job.get("formatted_html") if job["status"] == "completed" else None,
            "error": job.get("error") if job["status"] == "failed" else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(500, str(e))
```

### System Workers Status

| Worker | Queue Name | Status Endpoint | Pattern |
|--------|-----------|----------------|---------|
| `slide_format_worker.py` | `slide_format` | `/api/slides/jobs/{job_id}` | ✅ Redis |
| `chapter_translation_worker.py` | `chapter_translation` | `/api/books/{book_id}/chapters/translation-jobs/{job_id}` | ✅ Redis |
| `ai_editor_worker.py` | `ai_editor` | `/api/editor/jobs/{job_id}` | ✅ Redis |
| `slide_narration_audio_worker.py` | `slide_narration_audio` | `/api/presentations/{id}/subtitles/v2/{sid}/audio/status/{jid}` | ✅ Redis |
| `extraction_processing_worker.py` | `extraction` | `/api/extraction/status/{task_id}` | ✅ Redis (custom TaskStatusService) |

### Exceptions (MongoDB-based)

| Worker | Storage | Reason |
|--------|---------|--------|
| `slide_generation_worker.py` | MongoDB `documents` | Document-centric, long-term persistence |
| `translation_worker.py` | MongoDB `translation_jobs` | Multi-chapter jobs, complex progress tracking |

### Why Redis?

1. **Real-time updates:** Workers update instantly, frontend sees immediately (2s polling)
2. **No DB load:** No MongoDB queries during polling (Redis is in-memory)
3. **Auto cleanup:** 24h TTL removes old jobs automatically
4. **Atomic updates:** Hash operations are atomic
5. **Fast reads:** Single Redis HGETALL vs MongoDB query + indexes

### Implementation Checklist

**Worker Side:**
- [ ] Import `set_job_status` from `src.queue.queue_manager`
- [ ] Call `set_job_status()` at each stage (processing/completed/failed)
- [ ] Pass `redis_client=self.queue_manager.redis_client` as **first parameter**
- [ ] Store result data in Redis job
- [ ] Optional: Also update MongoDB for long-term persistence

**API Endpoint Side:**
- [ ] Import `get_job_status` from `src.queue.queue_manager`
- [ ] Import queue getter from `src.queue.queue_dependencies`
- [ ] Check Redis first: `job = await get_job_status(queue.redis_client, job_id)`
- [ ] Handle `job is None` → check MongoDB fallback or return 404
- [ ] Verify ownership: `job.get("user_id") == current_user["uid"]`
- [ ] Return job data from Redis (no MongoDB queries unless expired)

### Anti-Patterns (DO NOT USE)

❌ **Checking MongoDB for job status:**
```python
# BAD - MongoDB is too slow for real-time polling
job = db.jobs.find_one({"_id": job_id})
```

❌ **Using old task_status_key pattern:**
```python
# BAD - Deprecated pattern
redis_key = f"status:{queue_name}:{task_id}"
```

❌ **Storing status in MongoDB and Redis separately:**
```python
# BAD - Duplicate data, sync issues
await set_job_status(...)  # Redis
db.jobs.update_one(...)    # MongoDB - unnecessary for status polling!
```

### Monitoring Redis Jobs

```bash
# List all jobs
ssh root@104.248.147.155 "docker exec redis-server redis-cli KEYS 'job:*'"

# Check specific job
ssh root@104.248.147.155 "docker exec redis-server redis-cli HGETALL 'job:abc-123'"

# Check job TTL (should be ~86400 seconds = 24h)
ssh root@104.248.147.155 "docker exec redis-server redis-cli TTL 'job:abc-123'"

# Delete stuck job
ssh root@104.248.147.155 "docker exec redis-server redis-cli DEL 'job:abc-123'"
```

---

## 📊 Slide Elements Storage & Retrieval

**Updated:** January 6, 2026
**Purpose:** Clarify slide_elements vs slide_backgrounds structure

### Database Fields

**documents Collection:**

```javascript
{
  // ✅ PRIMARY: Complete slide elements (ALL slides with custom elements)
  "slide_elements": [
    {
      "slideIndex": 0,      // Slide number (0-based)
      "elements": [         // Visual elements array
        {
          "id": "image-1767635679829",
          "type": "image",  // image|text|shape|chart
          "x": 91.67,       // Position X
          "y": 33.33,       // Position Y
          "width": 190,     // Width
          "height": 143,    // Height
          "zIndex": 100,    // Layer order
          "src": "data:image/png;base64,...",
          "objectFit": "contain",
          "opacity": 1
        }
      ]
    }
    // Total: 18+ slides (all slides with custom elements)
  ],

  // ❌ SECONDARY: AI-formatted slides only (SPARSE!)
  "slide_backgrounds": [
    {
      "slideIndex": 8,         // Only AI-formatted slides
      "elements": [],          // Usually empty
      "formatted_html": "...", // AI-generated HTML
      "background_type": "gradient"
    }
    // Total: 3 slides (only slides formatted by AI worker)
  ]
}
```

### Key Differences

| Field | Purpose | Count | Use Case |
|-------|---------|-------|----------|
| `slide_elements` | **User-created elements** | 18+ slides | ✅ Public API, rendering, element display |
| `slide_backgrounds` | **AI-formatted slides** | 3 slides | ❌ Worker output only, incomplete data |

### Critical Rules

**✅ DO:**
- Use `slide_elements` for public API responses
- Use `slide_elements` for slide count with elements
- Use `slide_elements` for element rendering
- Query specific slide: `doc.slide_elements.find(s => s.slideIndex === 5)`

**❌ DON'T:**
- Use `slide_backgrounds` for slide count (only has AI-formatted slides!)
- Use `slide_backgrounds` for element rendering (incomplete data!)
- Assume `slide_backgrounds` has all slides (sparse array!)

### API Implementation

**Public Presentation Endpoint:**

```python
@router.get("/public/presentations/{public_token}")
async def get_public_presentation(public_token: str):
    # ... get presentation from MongoDB ...

    if sharing_settings.get("include_content", True):
        # ✅ CORRECT: Use slide_elements for frontend
        slide_elements = presentation.get("slide_elements")
        presentation_data["slide_elements"] = slide_elements

        # Keep slide_backgrounds for backward compatibility only
        presentation_data["slide_backgrounds"] = presentation.get("slide_backgrounds")
```

**MongoDB Queries:**

```javascript
// ✅ Get all slides with elements
const doc = db.documents.findOne({document_id: "doc_06de72fea3d7"})
const allSlides = doc.slide_elements  // 18 slides

// ✅ Find specific slide
const slide5 = doc.slide_elements.find(s => s.slideIndex === 5)

// ✅ Count slides with elements
const count = doc.slide_elements.length  // 18

// ❌ WRONG: Using slide_backgrounds
const wrongCount = doc.slide_backgrounds.length  // Only 3!
```

### Element Structure

```typescript
type SlideElement = {
  slideIndex: number,
  elements: Element[]
}

type Element = {
  id: string,
  type: "image" | "text" | "shape" | "chart",
  x: number,
  y: number,
  width: number,
  height: number,
  zIndex: number,

  // Type-specific fields
  src?: string,           // Image URL/data
  content?: string,       // Text content
  fontSize?: number,      // Text size
  color?: string,         // Text/shape color
  backgroundColor?: string,
  opacity?: number,
  rotation?: number
}
```

### Frontend Integration

```typescript
// ✅ CORRECT: Access slide elements
const response = await fetch(`/api/public/presentations/${token}`)
const data = await response.json()

const slideElements = data.presentation.slide_elements  // 18+ slides

// Find elements for current slide
const currentSlide = slideElements.find(s => s.slideIndex === currentIndex)
const elements = currentSlide?.elements || []

// Render elements
elements.forEach(el => {
  if (el.type === 'image') {
    renderImage(el)
  } else if (el.type === 'text') {
    renderText(el)
  }
})
```

### Migration Notes

**Before (2026-01-05):**
```python
# ❌ Was using slide_backgrounds (incomplete!)
presentation_data["slide_elements"] = presentation.get("slide_backgrounds")
```

**After (2026-01-06):**
```python
# ✅ Now using slide_elements (complete!)
presentation_data["slide_elements"] = presentation.get("slide_elements")
```

**Commit:** `1b70a6a` - Fixed field mapping for public API

---

### Related Documentation

See: **REDIS_STATUS_PATTERN.md** for detailed implementation guide, migration checklist, and examples.

---

## �📚 Related Documentation

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
