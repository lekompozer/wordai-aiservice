# Redis Job Status Pattern - System Standard

## 📋 Overview

**All async jobs MUST use Redis for real-time status tracking**, except slide generation which uses MongoDB document status.

## ✅ Correct Pattern

### 1. Status Storage (Workers)

Workers update job status using **standalone function** `set_job_status()`:

```python
from src.queue.queue_manager import set_job_status

await set_job_status(
    redis_client=queue_manager.redis_client,
    job_id=job_id,
    status="processing",  # pending/processing/completed/failed
    user_id=user_id,
    # Additional fields based on status
    started_at=datetime.utcnow().isoformat(),  # when processing
    completed_at=datetime.utcnow().isoformat(),  # when completed/failed
    # Result fields
    formatted_html="...",  # result data
    error_message="...",  # error info if failed
)
```

**Redis Key Pattern:** `job:{job_id}`
- Type: Hash (HSET)
- TTL: 24 hours
- Contains: All job data as hash fields

### 2. Status Retrieval (API Endpoints)

Endpoints check Redis using **standalone function** `get_job_status()`:

```python
from src.queue.queue_manager import get_job_status
from src.queue.queue_dependencies import get_QUEUE_NAME_queue

# Get queue manager (provides redis_client)
queue = await get_QUEUE_NAME_queue()

# Get job from Redis
job = await get_job_status(queue.redis_client, job_id)

if not job:
    # Job expired (24h TTL) or not found
    return {"status": "pending", ...}

# Use job data
status = job.get("status")
result = job.get("formatted_html")
```

**Redis Key Pattern:** `job:{job_id}` (same as storage)

### 3. Legacy QueueManager Pattern (Deprecated)

⚠️ **DO NOT USE for new code**

Old pattern uses `self.task_status_key()`:
```python
# ❌ DEPRECATED - Only exists for backward compatibility
redis_key = f"status:{queue_name}:{task_id}"
```

## 🔄 System Workers & Endpoints

### ✅ Using Correct Pattern

| Worker | Queue Name | Status Endpoint | Pattern |
|--------|-----------|----------------|---------|
| `slide_format_worker.py` | `slide_format` | `/api/slides/jobs/{job_id}` | ✅ `get_job_status()` |
| `chapter_translation_worker.py` | `chapter_translation` | `/api/books/{book_id}/chapters/translation-jobs/{job_id}` | ✅ `get_job_status()` |

### ⚠️ Needs Verification/Fix

| Worker | Queue Name | Status Endpoint | Current Pattern |
|--------|-----------|----------------|-----------------|
| `slide_narration_audio_worker.py` | `slide_narration_audio` | `/api/presentations/{id}/subtitles/v2/{subtitle_id}/audio/status/{job_id}` | ⚠️ **Mixed** (MongoDB + Redis fallback) |
| `ai_editor_worker.py` | `ai_editor` | `/api/editor/jobs/{job_id}` | ❓ Need to check |
| `extraction_processing_worker.py` | `extraction` | `/api/extraction/status/{task_id}` | ❓ Need to check |
| `translation_worker.py` | `translation` | `/api/translation/status/{job_id}` | ❓ Need to check |

### 📝 MongoDB Only (Exception)

| Worker | Storage | Reason |
|--------|---------|--------|
| `slide_generation_worker.py` | MongoDB `documents` collection | Document-centric, long-term persistence needed |

## 🛠️ Implementation Checklist

When creating new async job:

### Worker Side:
- [ ] Import `set_job_status` from `src.queue.queue_manager`
- [ ] Call `set_job_status()` at each stage:
  - [ ] `status="pending"` when queued
  - [ ] `status="processing"` when worker starts
  - [ ] `status="completed"` with result fields
  - [ ] `status="failed"` with error_message
- [ ] Store result data in same Redis job (no separate DB writes for status)

### API Endpoint Side:
- [ ] Import `get_job_status` from `src.queue.queue_manager`
- [ ] Import queue getter: `get_{queue_name}_queue` from `src.queue.queue_dependencies`
- [ ] Check Redis first: `job = await get_job_status(queue.redis_client, job_id)`
- [ ] Handle `job is None` → return "pending" or "not found"
- [ ] Verify ownership: `job.get("user_id") == current_user["uid"]`
- [ ] Return job data from Redis (no MongoDB queries)

## 🔍 Why Redis?

1. **Real-time updates**: Workers update instantly, frontend sees immediately
2. **No DB load**: No MongoDB queries during polling
3. **Auto cleanup**: 24h TTL removes old jobs automatically
4. **Atomic updates**: Hash operations are atomic
5. **Fast reads**: Single Redis GET vs MongoDB query + indexes

## 🚫 Anti-Patterns

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
db.jobs.update_one(...)    # MongoDB - unnecessary!
```

## ✅ Exception: Slide Narration Audio

Audio generation has **hybrid approach** due to historical reasons:

1. **Redis** (primary): Real-time status during processing
2. **MongoDB** (backup): Persistent record after completion

Status endpoint checks **both**:
```python
# 1. Try Redis first (worker updates here during processing)
redis_data = await queue.redis_client.get(f"status:slide_narration_audio:{job_id}")

# 2. Try new job pattern
job = await get_job_status(queue.redis_client, job_id)

# 3. Fallback to MongoDB (after Redis expires)
job = db.narration_audio_jobs.find_one({"_id": job_id})
```

**Why?** Audio jobs can take 3-5 minutes, users might poll after Redis TTL.

## 📊 Monitoring

Check Redis keys:
```bash
# List all jobs
redis-cli KEYS "job:*"

# Check specific job
redis-cli HGETALL "job:abc-123"

# Check TTL
redis-cli TTL "job:abc-123"
```

## 🔧 Migration Guide

To migrate existing MongoDB-based status to Redis:

1. **Keep MongoDB writes** for now (dual-write)
2. **Add Redis writes** using `set_job_status()`
3. **Update endpoint** to check Redis first
4. **Test thoroughly** with real jobs
5. **Remove MongoDB status writes** after verification
6. **Keep MongoDB for final results only** (optional long-term storage)

---

**Last Updated:** December 28, 2025
**Pattern Version:** 2.0 (Pure Redis with `get_job_status/set_job_status`)
