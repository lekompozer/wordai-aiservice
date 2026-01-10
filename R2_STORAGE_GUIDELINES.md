# Cloudflare R2 Storage - Official Guidelines

**Last Updated:** January 10, 2026
**Purpose:** Standardized R2 storage patterns for WordAI backend system

---

## 📊 Quick Reference: R2 Storage Types

| Storage Type | Path Pattern | Access Method | URL Type | Use Case |
|-------------|-------------|---------------|----------|----------|
| **Public CDN** | `studyhub/chapters/...`<br>`audio/...`<br>`images/...` | Direct HTTPS | `https://static.wordai.pro/...` | Chapter pages, covers, public assets |
| **Private S3** | `files/{user_id}/root/...` | S3 `get_object()` | `r2://wordai/...` (URI) | PDF uploads, documents |
| **Private Presigned** | `library/{user_id}/...`<br>`encrypted-library/...` | Presigned URL (1h expiry) | Temporary HTTPS | Library files, secret images |

**Key Principle:**
- **Public paths** → Store CDN URL in database → Direct access
- **Private paths** → Store `r2_key` in database → Generate access on demand

---

## ☁️ R2 Public URL (CDN)

### Official CDN Domain

**✅ CORRECT Domain:** `https://static.wordai.pro`

**Environment Variable:**
```bash
R2_PUBLIC_URL=https://static.wordai.pro
```

### ❌ NEVER USE These Domains

- `https://cdn.wordai.com` - WRONG, outdated
- `https://cdn.wordai.vn` - WRONG, outdated
- `https://cdn.r2.wordai.vn` - WRONG, not configured
- Any other `cdn.*` variations

---

## 📁 R2 Storage Patterns

### 1. Private Files - S3 Direct Download

**Use Case:** User documents requiring access control and authentication

#### 1A. PDF Files (r2:// URI Pattern)

**Storage Path:**
```
files/{user_id}/root/{file_id}/{filename}.pdf
```

**Database Collection:** `user_files`

**Database Fields:**
```python
{
    "file_id": "abc123",
    "file_name": "document.pdf",
    "file_type": "application/pdf",
    "file_url": "r2://wordai/files/user123/root/abc123/document.pdf",  # R2 URI (NOT public URL)
    "r2_key": "files/user123/root/abc123/document.pdf",                # Use this for s3_client
    "r2_bucket": "wordai",
    "file_size": 2456789,
    "user_id": "user123",
    "created_at": datetime.utcnow()
}
```

**Download Method:**
```python
from src.database.db_manager import DBManager
from src.services.r2_storage_service import get_r2_service

db_manager = DBManager()
r2_service = get_r2_service()

# Get file metadata
file_doc = db_manager.db.user_files.find_one({"file_id": file_id, "user_id": user_id})

# Download using r2_key
r2_key = file_doc.get("r2_key")
file_obj = r2_service.s3_client.get_object(Bucket="wordai", Key=r2_key)
file_content = file_obj["Body"].read()
```

#### 1B. Library Files (Presigned URL Pattern)

**Storage Path:**
```
library/{user_id}/{uuid}.{ext}           # Regular library files
encrypted-library/{user_id}/{uuid}.enc   # Encrypted secret images
```

**Database Collection:** `library_files` (regular), `secret_images` (encrypted)

**Database Fields:**
```python
{
    "library_id": "lib_abc123",
    "user_id": "user123",
    "filename": "photo.jpg",
    "file_type": "image/jpeg",
    "file_size": 1024000,
    "r2_key": "library/user123/a1b2c3d4.jpg",                    # R2 storage key
    "file_url": "https://...presigned_url...",                   # Temporary presigned URL (expires in 1 hour)
    "category": "images",  # documents/images/videos/audio
    "tags": ["reference", "design"],
    "uploaded_at": datetime.utcnow()
}
```

**Upload & Generate Presigned URL:**
```python
from src.services.r2_storage_service import get_r2_service
import uuid

r2_service = get_r2_service()

# 1. Upload to R2 (private)
file_extension = "jpg"
r2_key = f"library/{user_id}/{uuid.uuid4().hex}.{file_extension}"

r2_service.s3_client.put_object(
    Bucket=r2_service.bucket_name,
    Key=r2_key,
    Body=file_content,
    ContentType="image/jpeg"
)

# 2. Generate presigned URL (temporary access, expires in 1 hour)
file_url = r2_service.s3_client.generate_presigned_url(
    "get_object",
    Params={"Bucket": r2_service.bucket_name, "Key": r2_key},
    ExpiresIn=3600  # 1 hour
)

# 3. Save to database
library_doc = {
    "library_id": f"lib_{uuid.uuid4().hex[:12]}",
    "user_id": user_id,
    "filename": "photo.jpg",
    "r2_key": r2_key,          # Store key for future access
    "file_url": file_url,      # Presigned URL (temporary)
    "category": "images"
}
```

**Refresh Expired Presigned URL:**
```python
# When presigned URL expires, generate new one from r2_key
library_file = db.library_files.find_one({"library_id": library_id})
r2_key = library_file["r2_key"]

new_presigned_url = r2_service.s3_client.generate_presigned_url(
    "get_object",
    Params={"Bucket": r2_service.bucket_name, "Key": r2_key},
    ExpiresIn=3600
)
```

**⚠️ Important Notes:**
- **Presigned URLs expire** (typically 1 hour) - must regenerate when needed
- Library files are **private by default** - require presigned URL to access
- Secret images use **encryption** (`encrypted-library/`) with same presigned pattern
- DO NOT store presigned URLs permanently - they expire!

---

### 2. Public Files (CDN URL)

**Use Case:** Chapter page images, slide backgrounds, cover images - publicly accessible

**Storage Path Patterns:**
```
studyhub/chapters/{chapter_id}/page-{N}.jpg      # Book chapter pages
studyhub/covers/{book_id}/cover.jpg              # Book covers
audio/{audio_id}.mp3                             # Audio narrations
images/{image_id}.png                            # Generated images
videos/{video_id}.mp4                            # Video exports
author-avatars/{author_id}/avatar.jpg            # Author avatars
```

**Public URL Format:**
```python
cdn_base_url = "https://static.wordai.pro"
r2_key = f"studyhub/chapters/{chapter_id}/page-1.jpg"
public_url = f"{cdn_base_url}/{r2_key}"
# Result: https://static.wordai.pro/studyhub/chapters/abc123/page-1.jpg
```

**How to Upload Public Files:**
```python
from src.services.r2_storage_service import get_r2_service

r2_service = get_r2_service()

# Upload file
object_key = f"studyhub/chapters/{chapter_id}/page-{page_num}.jpg"
r2_service.s3_client.put_object(
    Bucket=r2_service.bucket_name,  # "wordai"
    Key=object_key,
    Body=image_bytes,
    ContentType="image/jpeg"
)

# Generate public CDN URL
cdn_url = f"{r2_service.public_url}/{object_key}"
# Result: https://static.wordai.pro/studyhub/chapters/abc123/page-1.jpg

# Store in database
page_doc = {
    "page_number": page_num,
    "background_url": cdn_url,  # Store full CDN URL
    "width": 1240,
    "height": 1754
}
```

---

## � Complete R2 Path Reference

### Public CDN Paths (Accessible via https://static.wordai.pro)

| Path Pattern | Purpose | Access | Example |
|-------------|---------|---------|---------|
| `studyhub/chapters/{chapter_id}/page-{N}.jpg` | Book chapter pages | Public CDN | `https://static.wordai.pro/studyhub/chapters/abc/page-1.jpg` |
| `studyhub/covers/{book_id}/cover.jpg` | Book cover images | Public CDN | `https://static.wordai.pro/studyhub/covers/abc/cover.jpg` |
| `audio/{audio_id}.mp3` | Audio narrations | Public CDN | `https://static.wordai.pro/audio/abc123.mp3` |
| `images/{image_id}.png` | Generated images | Public CDN | `https://static.wordai.pro/images/abc123.png` |
| `videos/{video_id}.mp4` | Video exports | Public CDN | `https://static.wordai.pro/videos/abc123.mp4` |
| `author-avatars/{author_id}/avatar.jpg` | Author avatars | Public CDN | `https://static.wordai.pro/author-avatars/abc/avatar.jpg` |

### Private Paths (Require S3 get_object or Presigned URL)

| Path Pattern | Purpose | Access Method | Storage Type |
|-------------|---------|---------------|--------------|
| `files/{user_id}/root/{file_id}/{filename}` | PDF uploads, documents | S3 `get_object()` | Private S3 |
| `files/{user_id}/{folder_id}/{file_id}/{filename}` | Organized files | S3 `get_object()` | Private S3 |
| `library/{user_id}/{uuid}.{ext}` | Library uploads (images, videos, docs) | Presigned URL (1h) | Private Presigned |
| `encrypted-library/{user_id}/{uuid}.enc` | Secret images (encrypted) | Presigned URL (1h) | Private Presigned |
| `files/{user_id}/slide_import/{file_id}/page-{N}.png` | PDF slide imports | S3 `get_object()` | Private S3 |

**Storage Type Meanings:**
- **Public CDN:** Files accessible directly via `https://static.wordai.pro/{path}` - store full URL in DB
- **Private S3:** Files require `s3_client.get_object(Bucket, Key)` - store `r2_key` in DB
- **Private Presigned:** Files require temporary presigned URL (expires 1h) - store `r2_key`, generate URL on demand

---

## �🔧 R2 Service Usage Patterns

### Initialize R2 Service

```python
from src.services.r2_storage_service import get_r2_service

r2_service = get_r2_service()

# Available properties:
r2_service.s3_client        # boto3 S3 client
r2_service.bucket_name      # "wordai"
r2_service.public_url       # "https://static.wordai.pro"
r2_service.endpoint_url     # Cloudflare R2 endpoint
```

### Upload with Auto-CDN

```python
# Example from book_chapter_manager.py
r2_config = {
    "bucket": r2_service.bucket_name,
    "cdn_base_url": r2_service.public_url,  # ✅ Use public_url from service
}

chapter_manager = GuideBookBookChapterManager(
    db=db,
    book_manager=book_manager,
    s3_client=r2_service.s3_client,
    r2_config=r2_config
)
```

### Delete Files from R2

```python
# Extract R2 key from CDN URL
cdn_url = "https://static.wordai.pro/studyhub/chapters/abc/page-1.jpg"
cdn_base = "https://static.wordai.pro/"

if cdn_url.startswith(cdn_base):
    r2_key = cdn_url[len(cdn_base):]  # "studyhub/chapters/abc/page-1.jpg"

    r2_service.s3_client.delete_object(
        Bucket=r2_service.bucket_name,
        Key=r2_key
    )
```

---

## ❌ Common R2 Mistakes to Avoid

### 1. Using Wrong CDN Domain

```python
# ❌ WRONG
cdn_url = f"https://cdn.wordai.com/{object_key}"
cdn_url = f"https://cdn.r2.wordai.vn/{object_key}"

# ✅ CORRECT
cdn_url = f"https://static.wordai.pro/{object_key}"
cdn_url = f"{r2_service.public_url}/{object_key}"  # Best - uses env var
```

### 2. Trying to Download r2:// URIs with HTTP

```python
# ❌ WRONG - file_url is r2:// not https://
file_url = file_doc.get("file_url")  # "r2://wordai/files/..."
async with aiohttp.get(file_url):    # ❌ Will crash!

# ✅ CORRECT - use r2_key with s3_client
r2_key = file_doc.get("r2_key")
file_obj = s3_client.get_object(Bucket="wordai", Key=r2_key)
```

### 3. Storing Presigned URLs Permanently

```python
# ❌ WRONG - presigned URLs expire after 1 hour!
library_doc["file_url"] = presigned_url  # Saved to DB, will expire!
# Later: use file_url directly → 403 Forbidden after expiry

# ✅ CORRECT - store r2_key, generate presigned URL on demand
library_doc["r2_key"] = r2_key  # Permanent storage key
library_doc["file_url"] = presigned_url  # Temporary (ok for immediate use)

# When fetching, check if expired and regenerate:
if is_presigned_url_expired(library_file["file_url"]):
    library_file["file_url"] = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": library_file["r2_key"]},
        ExpiresIn=3600
    )
```

### 4. Confusing Library Files with Public CDN Files

```python
# ❌ WRONG - Library files are PRIVATE, not public CDN
r2_key = f"library/{user_id}/photo.jpg"
cdn_url = f"https://static.wordai.pro/{r2_key}"  # ❌ Returns 403 Forbidden!

# ✅ CORRECT - Use presigned URL for library files
presigned_url = s3_client.generate_presigned_url(
    "get_object",
    Params={"Bucket": "wordai", "Key": r2_key},
    ExpiresIn=3600
)

# Note: Only studyhub/, audio/, images/ paths are public CDN
# Library files (library/, encrypted-library/, files/) are PRIVATE
```

# ✅ CORRECT - use r2_key with s3_client
r2_key = file_doc.get("r2_key")
file_obj = s3_client.get_object(Bucket="wordai", Key=r2_key)
```

### 3. Hardcoding CDN URLs

```python
# ❌ WRONG - hardcoded
cdn_base = "https://cdn.wordai.com"

# ✅ CORRECT - from config
from src.services.r2_storage_service import get_r2_service
r2_service = get_r2_service()
cdn_base = r2_service.public_url  # From R2_PUBLIC_URL env var
```

### 4. Using Old Default Values

```python
# ❌ WRONG - outdated defaults in code
cdn_base_url = self.r2_config.get("cdn_base_url", "https://cdn.wordai.vn")

# ✅ CORRECT - use official domain
cdn_base_url = self.r2_config.get("cdn_base_url", "https://static.wordai.pro")
```

---

## 🔑 R2 Environment Variables Reference

```bash
# Primary R2 bucket (wordai)
R2_ACCESS_KEY_ID=e6b5744fb686007c7f5d68051229d985
R2_SECRET_ACCESS_KEY=20f97c20fec535b06d8d919b374213a751438b4fd0f5a5911d021c01d99a6aa8
R2_BUCKET_NAME=wordai
R2_ENDPOINT=https://e13905a34ac218147b74fceb669e53c8.r2.cloudflarestorage.com
R2_PUBLIC_URL=https://static.wordai.pro  # ✅ OFFICIAL CDN DOMAIN

# Secondary R2 bucket (aivungtau - different project)
AIVUNGTAU_R2_ACCESS_KEY_ID=...
AIVUNGTAU_R2_BUCKET_NAME=aivungtau
AIVUNGTAU_R2_PUBLIC_URL=https://pub-aabd4cf5ec1246b3919d154ea540e4c6.r2.dev
AIVUNGTAU_R2_STATIC_DOMAIN=https://static.aivungtau.com
```

**Note:** The `static.wordai.pro` domain is configured as a custom domain in Cloudflare R2 settings.

---

## 📝 Code Examples by Use Case

### 1. Book Chapter Pages (Public CDN)

```python
from src.services.r2_storage_service import get_r2_service

r2_service = get_r2_service()

# Upload page image
page_key = f"studyhub/chapters/{chapter_id}/page-{page_num}.jpg"
r2_service.s3_client.put_object(
    Bucket=r2_service.bucket_name,
    Key=page_key,
    Body=jpg_bytes,
    ContentType="image/jpeg"
)

# Generate CDN URL for database
cdn_url = f"{r2_service.public_url}/{page_key}"
# Result: https://static.wordai.pro/studyhub/chapters/abc/page-1.jpg
```

### 2. PDF File Download (Private - S3 Direct)

```python
from src.database.db_manager import DBManager
from src.services.r2_storage_service import get_r2_service

db_manager = DBManager()
r2_service = get_r2_service()

# Get PDF metadata
file_doc = db_manager.db.user_files.find_one({
    "file_id": file_id,
    "user_id": user_id,
    "is_deleted": False
})

# Download using r2_key
r2_key = file_doc["r2_key"]  # "files/user123/root/abc/doc.pdf"
file_obj = r2_service.s3_client.get_object(
    Bucket=r2_service.bucket_name,
    Key=r2_key
)
pdf_bytes = file_obj["Body"].read()
```

### 3. Library Image Upload (Private - Presigned URL)

```python
from src.services.r2_storage_service import get_r2_service
import uuid

r2_service = get_r2_service()

# Upload to R2
file_extension = "jpg"
r2_key = f"library/{user_id}/{uuid.uuid4().hex}.{file_extension}"

r2_service.s3_client.put_object(
    Bucket=r2_service.bucket_name,
    Key=r2_key,
    Body=image_bytes,
    ContentType="image/jpeg"
)

# Generate presigned URL (expires in 1 hour)
presigned_url = r2_service.s3_client.generate_presigned_url(
    "get_object",
    Params={"Bucket": r2_service.bucket_name, "Key": r2_key},
    ExpiresIn=3600
)

# Save to database
library_doc = {
    "library_id": f"lib_{uuid.uuid4().hex[:12]}",
    "user_id": user_id,
    "filename": "photo.jpg",
    "r2_key": r2_key,              # Permanent storage key
    "file_url": presigned_url,     # Temporary access URL
    "category": "images"
}
db.library_files.insert_one(library_doc)
```

### 4. Secret Image Upload (Encrypted - Presigned URL)

```python
from src.services.encrypted_library_manager import EncryptedLibraryManager

manager = EncryptedLibraryManager(db, s3_client)

# Encrypt and upload
unique_id = uuid.uuid4().hex
file_extension = "jpg"
r2_key = f"encrypted-library/{user_id}/{unique_id}.{file_extension}.enc"

# Encrypt image bytes
encrypted_bytes = manager.encrypt_data(image_bytes)

# Upload encrypted file
s3_client.put_object(
    Bucket="wordai",
    Key=r2_key,
    Body=encrypted_bytes,
    ContentType="application/octet-stream"
)

# Generate presigned URL for encrypted file
presigned_url = s3_client.generate_presigned_url(
    "get_object",
    Params={"Bucket": "wordai", "Key": r2_key},
    ExpiresIn=3600
)

# Note: Frontend must decrypt after downloading via presigned URL
```

### 5. Cover Image Upload (Public CDN)

```python
cover_key = f"studyhub/covers/{book_id}/cover.jpg"
r2_service.s3_client.put_object(
    Bucket=r2_service.bucket_name,
    Key=cover_key,
    Body=cover_bytes,
    ContentType="image/jpeg"
)

cover_url = f"{r2_service.public_url}/{cover_key}"
# Update book document
db.online_books.update_one(
    {"book_id": book_id},
    {"$set": {"cover_image": cover_url}}
)
```

---

## 🚫 Migration Notes

### Replacing Old CDN URLs

If you find old CDN URLs in the codebase or database:

**Search Patterns to Replace:**
```bash
# In code
grep -r "cdn.wordai.com" src/
grep -r "cdn.wordai.vn" src/
grep -r "cdn.r2.wordai" src/

# Replace with
https://static.wordai.pro
```

**Database Updates (if needed):**
```javascript
// MongoDB - Update old CDN URLs in documents
db.online_books.updateMany(
  { cover_image: /^https:\/\/cdn\.wordai\.(com|vn)/ },
  [{
    $set: {
      cover_image: {
        $replaceOne: {
          input: "$cover_image",
          find: /^https:\/\/cdn\.wordai\.(com|vn)/,
          replacement: "https://static.wordai.pro"
        }
      }
    }
  }]
)
```

---

## 📚 Related Documentation

- **SYSTEM_REFERENCE.md** - Complete system documentation
- **BOOK_CHAPTER_API_SPECS.md** - Book chapter API specifications
- **.env** - Production environment variables
- **development.env.template** - Development template

---

**Last Updated:** January 10, 2026
**Maintained by:** WordAI Development Team
