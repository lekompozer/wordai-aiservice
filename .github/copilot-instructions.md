# GitHub Copilot Instructions - WordAI Backend System

## Primary Reference

**ALWAYS read and follow:** `/SYSTEM_REFERENCE.md` - Complete system documentation

This file contains:
- Production server SSH access patterns
- MongoDB/Redis connection patterns and commands
- Docker container management
- Redis Worker Pattern (standard for all async jobs)
- Queue Manager patterns
- Database collections structure
- API endpoints reference
- Common issues and solutions

## Critical Rules

### 1. Claude Model Version (MANDATORY)

**MUST use Claude Sonnet 4.5 version `20250929` ONLY**
- Vertex AI: `claude-sonnet-4-5@20250929`
- Claude API: `claude-sonnet-4-5-20250929`
- DO NOT use Claude 3.5 Sonnet or any other version

### 2. Database Connection (MANDATORY)

**MUST use DBManager pattern:**
```python
from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db
```

**NEVER use:**
- ❌ Direct MongoClient
- ❌ get_mongodb_service()
- ❌ config.get_mongodb()

### 3. Redis Worker Pattern (MANDATORY for async jobs)

**Workers MUST use:**
```python
from src.queue.queue_manager import set_job_status

await set_job_status(
    redis_client=self.queue_manager.redis_client,  # First param!
    job_id=job_id,
    status="processing",  # pending/processing/completed/failed
    user_id=user_id,
    # ... additional fields
)
```

**API endpoints MUST use:**
```python
from src.queue.queue_manager import get_job_status

queue = await get_QUEUE_NAME_queue()
job = await get_job_status(queue.redis_client, job_id)
```

**Exceptions:** Only `slide_generation_worker` and `translation_worker` use MongoDB.

### 4. Production Server Access

**SSH Pattern:**
```bash
ssh root@104.248.147.155 "su - hoile -c 'COMMAND'"
```

**Working Directory:** `/home/hoile/wordai`

**Production Domain:** `ai.wordai.pro` (NOT wordai.chat or direct IP)

### 4.1. API Testing (CRITICAL)

**NEVER test API using:**
- ❌ Direct IP: `http://104.248.147.155/api/v1/...`
- ❌ Wrong domain: `https://wordai.chat/api/v1/...`
- ❌ External domain: `https://ai.wordai.pro/api/v1/...` (requires authentication)

**ALWAYS test API using SSH + localhost:**
```bash
# Correct pattern - SSH into docker container
ssh root@104.248.147.155 "docker exec ai-chatbot-rag curl -s http://localhost:8000/api/v1/ENDPOINT"

# Example: Test conversation topics (PUBLIC)
ssh root@104.248.147.155 "docker exec ai-chatbot-rag curl -s http://localhost:8000/api/v1/conversations/topics | python3 -m json.tool"

# Example: Test browse conversations (PUBLIC)
ssh root@104.248.147.155 "docker exec ai-chatbot-rag curl -s 'http://localhost:8000/api/v1/conversations/list?level=beginner&limit=5' | python3 -m json.tool"

# Example: Test with authentication
ssh root@104.248.147.155 'docker exec ai-chatbot-rag curl -s http://localhost:8000/api/v1/conversations/conv_beginner_greetings_01_001 -H "Authorization: Bearer YOUR_TOKEN"'
```

**Why localhost only works:**
- Nginx requires proper domain routing
- External access needs Firebase authentication
- Internal docker network uses localhost:8000

**Public Endpoints (No auth required):**
- `GET /api/v1/conversations/topics` - List all topics
- `GET /api/v1/conversations/list` - Browse conversations

### 5. Production Deployment (MANDATORY)

**MUST use this command for ALL deployments (full stack):**
```bash
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && ./deploy-compose-with-rollback.sh'"
```

**Why this command is required:**
- ✅ Full Docker rebuild (ensures all code changes applied)
- ✅ Automatic rollback if deployment fails
- ✅ Zero-downtime deployment with health checks
- ✅ Pulls latest code from main branch
- ✅ Rebuilds all containers (app, workers, nginx)

**Python-only deployment (FASTER — only when `src/` Python code changed, NOT payment-service/docker-compose):**
```bash
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && ./deploy-app-only.sh'"
```
- ✅ Only recreates `ai-chatbot-rag` container, all other containers untouched
- ✅ Initial delay 30s (vs 150s for full deploy)
- ✅ Automatic rollback if health check fails
- ❌ DO NOT use for: payment-service changes, docker-compose changes, new workers, nginx changes

**Alternative (ONLY for nginx config changes):**
```bash
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && ./restart-nginx.sh'"
```

**NEVER use:**
- ❌ `./restart-nginx.sh` for code changes (only reloads nginx, not Python code)
- ❌ Manual docker commands without rollback safety
- ❌ Direct git pull without rebuild

### 6. MongoDB Access (Production)

**Database Name:** `ai_service_db` (NOT wordai_db)

```bash
docker exec mongodb mongosh ai_service_db \
  -u ai_service_user \
  -p ai_service_2025_secure_password \
  --authenticationDatabase admin
```

### 7. Redis Access (Production)

```bash
docker exec redis-server redis-cli

# Check job status
HGETALL "job:{job_id}"

# List all jobs
KEYS "job:*"
```

### 8. Running One-Off Scripts (CRITICAL - No Rebuild Needed)

**NEVER rebuild Docker just to run a script!**

**Pattern: Copy script into running container and execute:**
```bash
# Copy script from host to container
docker cp /home/hoile/wordai/script.py ai-chatbot-rag:/app/

# Run script inside container
docker exec ai-chatbot-rag python3 /app/script.py

# Or do both in one command:
docker cp /home/hoile/wordai/script.py ai-chatbot-rag:/app/ && \
  docker exec ai-chatbot-rag python3 /app/script.py
```

**SSH Combined Command:**
```bash
ssh root@104.248.147.155 "docker cp /home/hoile/wordai/create_indexes.py ai-chatbot-rag:/app/ && docker exec ai-chatbot-rag python3 /app/create_indexes.py"
```

**When to use:**
- ✅ Running index creation scripts
- ✅ Database migration scripts
- ✅ One-time data fixes
- ✅ Testing new utilities
- ❌ Don't use for code changes to src/ (need full rebuild)

**Why this works:**
- Container has all Python packages installed
- Has access to MongoDB/Redis
- Loads environment variables from .env
- No downtime, no rebuild time

### 9. API Endpoint Development (CRITICAL - AVOID 404 ERRORS)

**Common 404 Errors and How to Avoid:**

1. **Database Connection:**
   - ✅ MUST use: `from src.database.db_manager import DBManager`
   - ✅ Database: `ai_service_db` (NOT `wordai_db`)
   - ❌ NEVER: Direct MongoClient or get_mongodb_service()

2. **Collection Names:**
   - ✅ Use exact collection names from SYSTEM_REFERENCE.md
   - ❌ Don't assume collection names - always verify first

3. **API Response Structure:**
   - ✅ **Return empty list/dict for empty results** (NOT 404):
     ```python
     # ✅ CORRECT: Return empty array
     playlists = list(db.collection.find({"user_id": user_id}))
     return playlists  # Returns [] if no data - status 200

     # ❌ WRONG: Raise 404 for empty results
     if not playlists:
         raise HTTPException(status_code=404, detail="No playlists found")
     ```

   - ✅ **Use 404 ONLY for resource that SHOULD exist:**
     ```python
     # ✅ CORRECT: 404 when fetching specific ID that doesn't exist
     playlist = db.collection.find_one({"playlist_id": playlist_id})
     if not playlist:
         raise HTTPException(status_code=404, detail="Playlist not found")
     ```

   - ✅ **Pattern for list endpoints:**
     ```python
     @router.get("/items", response_model=List[ItemResponse])
     async def get_items(current_user: dict = Depends(get_current_user)):
         items = list(db.items.find({"user_id": current_user["uid"]}))
         return items  # Always return list, even if empty []
     ```

   - ❌ **Don't return generic "not found" without context**

4. **FastAPI Route Order (CRITICAL - Fix for 404 Conflicts):**

   **Problem Pattern:**
   ```python
   # ❌ WRONG ORDER - Causes 404 on /playlists
   @router.get("/{song_id}")  # Generic route catches everything first!
   async def get_song(song_id: str):
       return {"song_id": song_id}  # "playlists" becomes song_id

   @router.get("/playlists")  # Never reached - caught by above route
   async def get_playlists():
       return []
   ```

   **Result:** GET `/playlists` → Returns `{"song_id": "playlists"}` instead of calling the playlists endpoint

   **Solution Pattern:**
   ```python
   # ✅ CORRECT ORDER - Specific routes BEFORE generic routes
   @router.get("/playlists")  # Specific route first
   async def get_playlists():
       return []

   @router.get("/favorites")  # Another specific route
   async def get_favorites():
       return []

   @router.get("/{song_id}")  # Generic route LAST
   async def get_song(song_id: str):
       return {"song_id": song_id}
   ```

   **Route Order Checklist:**
   - ✅ Static paths (exact strings) MUST come before path parameters
   - ✅ `/playlists`, `/favorites`, `/search` → BEFORE `/{song_id}`
   - ✅ More specific patterns before less specific: `/{song_id}/comments` → BEFORE `/{song_id}`
   - ❌ Path parameters like `/{id}`, `/{song_id}` act as catch-all - put them LAST
   - ❌ Moving generic routes up causes 404 on specific endpoints

   **When Adding New Routes:**
   1. Check existing routes for path parameters (`/{variable}`)
   2. Place new static routes ABOVE all path parameter routes
   3. Test both the new route AND existing routes after reordering
   4. Deploy and verify in production

   **Real Example (Fixed):**
   ```python
   # Playlist Management - Line 520 (BEFORE generic routes)
   @router.get("/playlists")
   @router.post("/playlists")
   @router.put("/playlists/{playlist_id}")
   @router.delete("/playlists/{playlist_id}")

   # Generic Song Routes - Line 600+ (AFTER specific routes)
   @router.get("/{song_id}")  # Matches anything not caught above
   ```

5. **Deployment:**
   - ✅ ALWAYS deploy after adding new routes
   - ✅ Test endpoint after deployment: `curl http://localhost:8000/api/v1/...`
   - ❌ Don't assume routes work without testing

5. **Firebase Authentication:**
   - ✅ Use `get_current_user` dependency:
     ```python
     from src.middleware.firebase_auth import get_current_user

     @router.get("/endpoint")
     async def endpoint(current_user: dict = Depends(get_current_user)):
         user_id = current_user["uid"]
         email = current_user.get("email")
     ```

   - ✅ Use `get_db()` for database access:
     ```python
     def get_db():
         db_manager = DBManager()
         return db_manager.db

     @router.get("/endpoint")
     async def endpoint(
         current_user: dict = Depends(get_current_user),
         db = Depends(get_db)
     ):
         user_id = current_user["uid"]
         data = db.collection.find_one({"user_id": user_id})
     ```

   - ❌ Don't use hardcoded user IDs or test tokens in production
   - ❌ Don't use direct `DBManager()` in endpoint body (use dependency)

**Testing New Endpoints:**
```bash
# 1. Deploy first
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && ./deploy-compose-with-rollback.sh'"

# 2. Test on server
ssh root@104.248.147.155 "curl -s http://localhost:8000/api/v1/YOUR_ENDPOINT"

# 3. Check logs if 404
ssh root@104.248.147.155 "docker logs ai-chatbot-rag --tail 50"
```

### 10. Payment Service (Node.js) — CRITICAL NOTES

**Location:** `payment-service/` (Node.js/Express app)
**Container:** `payment-service` (port 3000 internal)
**Nginx routing:** `location ^~ /api/payment/` → rewrites to `/api/v1/payments/` → proxied to Node.js

**File structure:**
```
payment-service/
  src/
    controllers/paymentController.js  ← checkout + IPN handling
    routes/                           ← Express routes
    middleware/
  Dockerfile
  package.json
```

**After IPN webhook (payment completed), Node.js:**
1. Marks payment `status: completed` in MongoDB `payments` collection
2. Sets `subscription_queued: true` on the record
3. Pushes event to Redis: `LPUSH queue:payment_events {...}`
4. Python `learning-events-worker` consumes and activates subscription

**Known issue fixed:** `payment-events-worker` WAS a separate container but caused:
- High CPU 25%+ crash-loop (no logs output despite PYTHONUNBUFFERED)
- Wasted 256MB RAM on 7.8GB constrained server
- **Fix:** Merged into `learning-events-worker` — single worker now handles both `queue:learning_events` AND `queue:payment_events` via `brpop([key1, key2], timeout=1)`

**Affiliate validation in paymentController.js (MANDATORY):**
```javascript
// ALWAYS validate affiliate before creating payment:
const aff = await affiliatesCollection.findOne(
    { code: affiliate_code.toUpperCase() },
    { projection: { is_active: 1, user_id: 1 } }  // MUST include ALL fields you access
);
if (!aff) throw new AppError('Mã đại lý không tồn tại.', 404);
if (!aff.is_active) throw new AppError('Đại lý chưa được kích hoạt.', 403);
if (!aff.user_id) throw new AppError('Đại lý chưa đăng nhập hệ thống.', 403);
// ❌ BUG: projection missing user_id → aff.user_id always undefined → always 403
```

**Testing payment-service:**
```bash
# Checkout endpoint
ssh root@104.248.147.155 "docker exec payment-service curl -s http://localhost:3000/health"

# Check payment logs
ssh root@104.248.147.155 "docker logs payment-service --tail=50"

# Check pending payment jobs in Redis:
ssh root@104.248.147.155 "docker exec redis-server redis-cli LLEN queue:payment_events"
ssh root@104.248.147.155 "docker exec redis-server redis-cli LRANGE queue:payment_events 0 -1"
```

**Diagnose subscription not activated:**
```bash
# 1. Check payment record in MongoDB
docker exec mongodb mongosh ai_service_db ... --eval \
  "db.payments.find({user_email:'...'}).sort({created_at:-1}).limit(3).toArray()"
# Look for: status=completed, subscription_queued=true, subscription_activated=true/false

# 2. Check subscription record
db.user_conversation_subscription.findOne({user_id: 'firebase_uid'})

# 3. Check Redis queue (should be 0 if worker processed it)
docker exec redis-server redis-cli LLEN queue:payment_events

# 4. Check worker logs
docker logs learning-events-worker --tail=50
```

### 11. Server Resource Constraints (CRITICAL)

**Server:** `104.248.147.155` — 2 vCPUs, 7.8GB RAM, NO SWAP
**RAM usage:** ~7.0GB used (very tight — each Python worker ≈ 350-420MB)

**To save RAM:**
- ✅ Merge lightweight workers with similar event-driven workers
- ✅ Each Python worker uses brpop multi-key: `brpop([queue1, queue2], timeout=1)`
- ❌ Do NOT add new standalone worker containers unless absolutely necessary
- ❌ Do NOT increase memory limits without checking total budget

**Worker RAM budget:**
- Each Python worker: ~350-420MB (hits 512MB limit)
- `pdf-chapter-worker` / `ai-editor-worker`: 2GB limit
- `payment-service` (Node.js): ~70MB only
- Total containers: ~15+ services

## When Implementing New Features

1. **Check SYSTEM_REFERENCE.md** for existing patterns
2. **Use DBManager** for database connections
3. **Use correct database:** `ai_service_db` (NOT wordai_db)
4. **Use Redis pattern** for async job status
5. **Follow queue patterns** from existing workers
6. **SSH commands** must use `su - hoile -c` wrapper
7. **Test locally** before deploying to production
8. **Deploy and test** on production before marking complete

## Common Mistakes to Avoid

❌ MongoDB: `db.jobs.find_one()` for job status polling
✅ Redis: `await get_job_status(queue.redis_client, job_id)`

❌ Direct SSH: `ssh root@IP "cd /home/hoile/wordai && command"`
✅ With su: `ssh root@IP "su - hoile -c 'cd /home/hoile/wordai && command'"`

❌ Old import: `from src.services.online_test_utils import get_mongodb_service`
✅ New import: `from src.database.db_manager import DBManager`

❌ Wrong database: `wordai_db`
✅ Correct database: `ai_service_db`

❌ Wrong queue method: `await queue.enqueue(job_id, data)`
✅ Correct method: `await queue.enqueue_generic_task(task)`

❌ Direct field access: `test["time_limit_minutes"]` (may cause KeyError)
✅ Safe access: `test.get("time_limit_minutes", 60)` (with default)

❌ New endpoint without deployment
✅ Deploy first, then test: `curl http://localhost:8000/api/v1/...`

❌ Full deploy for Python-only changes (slow, 150s wait)
✅ `./deploy-app-only.sh` when only `src/` Python changed (30s, no worker restart)

❌ MongoDB projection missing fields: `{"code": 1, "is_active": 1}` → `doc.get("user_id")` always None
✅ Always include every field you access in the projection!

❌ New standalone Python worker container for lightweight event handling
✅ Merge into `learning-events-worker` using multi-key brpop (saves ~350MB RAM)

❌ Checking logs of `payment-events-worker` (container removed, merged)
✅ `docker logs learning-events-worker --tail=50` handles both learning + payment events

## Quick Reference Links

- Full docs: `/SYSTEM_REFERENCE.md`
- Redis pattern: `/REDIS_STATUS_PATTERN.md`
- API docs: Server `/docs` endpoint
- Question types: `/QUESTION_TYPES_JSON_SCHEMA.md`

---

**Last Updated:** February 23, 2026
**For:** GitHub Copilot, Cursor AI, and other AI coding assistants
