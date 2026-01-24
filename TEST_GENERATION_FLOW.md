# Test Generation Flow - Complete Reference

**Date:** January 24, 2026
**Version:** 16542a2

## Architecture Overview

All test generation now uses **Redis Worker Pattern** with max 5 concurrent tasks.

```
┌─────────────┐      ┌──────────┐      ┌─────────────┐      ┌──────────┐
│  Frontend   │─────>│   API    │─────>│    Redis    │─────>│  Worker  │
│  (React)    │<─────│ Endpoint │      │    Queue    │      │Container │
└─────────────┘      └──────────┘      └─────────────┘      └──────────┘
       │                   │                                        │
       │                   │                                        ▼
       │                   │                                  ┌──────────┐
       │                   │                                  │ MongoDB  │
       │                   └─────────────────────────────────>│  (poll)  │
       └──────────────────────────────────────────────────────┘
                    (Polling: GET /tests/{id}/status)
```

---

## 1. LISTENING TEST GENERATION

### Endpoint
```
POST /api/v1/tests/generate/listening
```

### Flow

#### Step 1: API Endpoint Creates MongoDB Record
**File:** `src/api/test_creation_routes.py` (Line 3574)

```python
# Create test document with status="pending"
test_doc = {
    "title": request.title,
    "test_type": "listening",
    "status": "pending",           # ← Initial state
    "progress_percent": 0,
    "questions": [],                # ← Empty
    "audio_sections": [],           # ← Empty
    "created_at": datetime.now(),
}
collection.insert_one(test_doc)
test_id = str(result.inserted_id)
```

#### Step 2: API Enqueues Task to Redis
```python
job_id = str(uuid.uuid4())
queue = await get_test_generation_queue()

# Set Redis job status
await set_job_status(
    redis_client=queue.redis_client,
    job_id=job_id,
    status="pending",
    test_id=test_id,
)

# Create task
task = TestGenerationTask(
    task_id=job_id,
    job_id=job_id,
    task_type="listening",
    test_id=test_id,  # ← MongoDB test ID
    # ... other fields
)

# Enqueue to worker
await queue.enqueue_generic_task(task)
```

#### Step 3: Worker Processes Task
**File:** `src/workers/test_generation_worker.py`

```python
async def process_listening_test(self, task_data: dict):
    test_id = task_data.get("test_id")

    # 1. Update Redis status
    await set_job_status(status="processing", ...)

    # 2. Generate test
    result = await generator.generate_listening_test(...)

    # 3. UPDATE MONGODB (CRITICAL!)
    update_data = {
        "status": "ready",          # ← Status change
        "progress_percent": 100,
        "questions": result["questions"],
        "audio_sections": result["audio_sections"],
        "generated_at": datetime.utcnow(),
    }

    self.db["online_tests"].update_one(
        {"_id": ObjectId(test_id)},
        {"$set": update_data}
    )

    # 4. Update Redis status
    await set_job_status(status="completed", ...)
```

#### Step 4: Frontend Polls Status
```javascript
// Poll every 3 seconds
const interval = setInterval(async () => {
  const response = await fetch(`/api/v1/tests/${testId}/status`);
  const data = await response.json();

  if (data.status === 'ready') {
    clearInterval(interval);
    loadTest(testId);  // Load questions
  }
}, 3000);
```

**Polling endpoint checks MongoDB:**
```python
@router.get("/{test_id}/status")
async def get_test_status(test_id: str):
    test = collection.find_one({"_id": ObjectId(test_id)})
    status = test.get("status")  # ← MongoDB status

    if status == "ready":
        return {
            "status": "ready",
            "title": test["title"],
            "num_questions": test["num_questions"],
            "questions": test["questions"],  # ← From MongoDB
        }
```

---

## 2. PDF/DOCUMENT TEST GENERATION

### Endpoint
```
POST /api/v1/tests/generate
```

### Flow

#### Step 1-2: Same as Listening Test
API creates MongoDB doc and enqueues to Redis.

#### Step 3: Worker Calls `generate_test_background()`
**File:** `src/workers/test_generation_worker.py`

```python
async def process_pdf_test(self, task_data: dict):
    test_id = task_data.get("test_id")

    # Update Redis status
    await set_job_status(status="processing", ...)

    # Call background function (UPDATES MONGODB INTERNALLY!)
    from src.services.online_test_utils import generate_test_background

    await generate_test_background(
        test_id=test_id,
        content=content,
        # ... other params
    )
    # ↑ This function ALREADY updates MongoDB with status="ready"

    # Update Redis status
    await set_job_status(status="completed", ...)
```

**`generate_test_background()` updates MongoDB:**
```python
# File: src/services/online_test_utils.py
async def generate_test_background(test_id: str, ...):
    collection = mongo_service.db["online_tests"]

    # Update to "generating"
    collection.update_one(
        {"_id": ObjectId(test_id)},
        {"$set": {"status": "generating"}}
    )

    # Generate questions with AI
    result = await test_generator._generate_questions_with_ai(...)

    # Update to "ready" with questions
    collection.update_one(
        {"_id": ObjectId(test_id)},
        {"$set": {
            "questions": result["questions"],
            "status": "ready",           # ← MongoDB updated
            "progress_percent": 100,
            "generated_at": datetime.now(),
        }}
    )
```

#### Step 4: Frontend Polls (Same as Listening)

---

## 3. GENERAL KNOWLEDGE TEST GENERATION

### Endpoint
```
POST /api/v1/tests/generate/general
```

### Flow

**IDENTICAL to PDF test** - also uses `generate_test_background()`.

```python
async def process_general_test(self, task_data: dict):
    # Same as PDF test
    await generate_test_background(
        test_id=test_id,
        content=f"Topic: {topic}\nInstructions: {user_query}",
        is_general_knowledge=True,
        # ...
    )
```

---

## Key Differences

| Test Type | MongoDB Update Location | Service Function |
|-----------|------------------------|------------------|
| **Listening** | Worker (`process_listening_test`) | `generate_listening_test()` - Returns data only |
| **PDF** | Service (`generate_test_background`) | `generate_test_background()` - Updates MongoDB |
| **General** | Service (`generate_test_background`) | `generate_test_background()` - Updates MongoDB |

---

## Common Bug: Missing MongoDB Update

### Symptom
- Worker logs show "✅ Test generated successfully"
- Redis status shows "completed"
- But frontend polling shows `status: "pending"` forever
- Questions array is empty: `questions: []`

### Root Cause
Worker updated **Redis only**, not **MongoDB**.

### How Polling Works
```python
# Polling endpoint CHECKS MONGODB, not Redis!
test = collection.find_one({"_id": ObjectId(test_id)})
return {"status": test.get("status")}  # ← From MongoDB
```

### Fix
**Listening test worker MUST update MongoDB:**
```python
self.db["online_tests"].update_one(
    {"_id": ObjectId(test_id)},
    {"$set": {
        "status": "ready",
        "questions": result["questions"],
        "audio_sections": result["audio_sections"],
    }}
)
```

**PDF/General tests:** Already handled by `generate_test_background()`.

---

## Status Flow

### MongoDB Status Progression

**Listening Test:**
```
pending → ready (updated by worker)
```

**PDF/General Test:**
```
pending → generating → ready (updated by generate_test_background)
```

### Redis Job Status
```
pending → processing → completed/failed
```

**Redis is for job tracking only.** Frontend never checks Redis directly.

---

## Testing Checklist

### After Deployment, Verify:

1. **Create Test**
   ```bash
   curl -X POST https://wordai.pro/api/v1/tests/generate/listening \
     -H "Authorization: Bearer $TOKEN" \
     -d '{...}'
   ```

2. **Check MongoDB Status**
   ```bash
   docker exec mongodb mongosh ai_service_db \
     --eval "db.online_tests.findOne({_id: ObjectId('$TEST_ID')})"
   ```

   Should show:
   - `status: "ready"` (not "pending")
   - `questions: [...]` (not empty)
   - `audio_sections: [...]` (for listening)

3. **Check Redis Job**
   ```bash
   docker exec redis-server redis-cli HGETALL "job:$JOB_ID"
   ```

   Should show:
   - `status: "completed"`
   - `test_id: "$TEST_ID"`

4. **Poll Status Endpoint**
   ```bash
   curl https://wordai.pro/api/v1/tests/$TEST_ID/status
   ```

   Should return:
   ```json
   {
     "status": "ready",
     "title": "Test Title",
     "num_questions": 20,
     "questions": [...]
   }
   ```

---

## Deployment Version

**Current:** `16542a2`

**Changes:**
- ✅ Listening test worker now updates MongoDB
- ✅ All 3 test types use Redis Worker Pattern
- ✅ Max 5 concurrent test generations
- ✅ Multi-speaker TTS via Google AI API

**Deployed:** January 24, 2026
