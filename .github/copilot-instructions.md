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

**MUST use Claude Sonnet 4.6 — model string `claude-sonnet-4-6`**
- Vertex AI: `claude-sonnet-4-6`
- Claude API: `claude-sonnet-4-6`
- DO NOT use Claude 3.5 Sonnet, claude-sonnet-4-5, or any other version

### 1c. ChatGPT / OpenAI Model Version (MANDATORY)

**MUST use `gpt-5.4`** — latest ChatGPT model in production
- Default in `src/clients/chatgpt_client.py`: `model = "gpt-5.4"`
- Used for: brand analysis, 30-day social marketing plan structure, test generation fallback
- DO NOT use `gpt-4o`, `gpt-4o-latest`, `gpt-4-turbo`, or any older version
```python
from src.clients.chatgpt_client import ChatGPTClient

# Default usage (uses gpt-5.4)
client = ChatGPTClient(api_key=openai_key)

# Explicit
client = ChatGPTClient(api_key=openai_key, model="gpt-5.4")
```

### 1b. Gemini Model Version (MANDATORY)

**MUST use `gemini-3.1-flash-lite-preview`** — latest Gemini model in production
- Audio input: use `google.genai` new SDK (`genai.Client` + `client.models.generate_content`)
- DO NOT use `google.generativeai` (old SDK) for new code
- DO NOT use `gemini-2.5-flash`, `gemini-2.5-flash-lite-preview-06-17`, or any older version
```python
from google import genai
from google.genai import types as genai_types

client = genai.Client(api_key=gemini_key)
response = client.models.generate_content(
    model="gemini-3.1-flash-lite-preview",
    contents=[
        genai_types.Part.from_bytes(data=audio_bytes, mime_type="audio/webm"),
        prompt_text,
    ],
)
```

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

**Python-only deployment (FASTER — only when `src/` code changed in `ai-chatbot-rag` ONLY, e.g. API routes, services):**
```bash
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && ./deploy-app-only.sh'"
```
- ✅ Only recreates `ai-chatbot-rag` container, all other containers untouched
- ✅ Initial delay 30s (vs 150s for full deploy)
- ✅ Automatic rollback if health check fails
- ❌ DO NOT use for: **worker code changes** (`src/workers/`), payment-service changes, docker-compose changes, new workers, nginx changes
- ⚠️ **CRITICAL:** If ANY worker file (`src/workers/*.py`) was changed → MUST use full deploy `./deploy-compose-with-rollback.sh` because workers run in separate containers and `deploy-app-only.sh` does NOT restart them!

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
## Server Operations (DevOps only)

```bash
# Build / rebuild 500 daily sets in Redis (required once after deploy)
scp scripts/build_daily_sets.py root@104.248.147.155:/tmp/
ssh root@104.248.147.155 "docker cp /tmp/build_daily_sets.py ai-chatbot-rag:/app/ && \
  docker exec ai-chatbot-rag python3 /app/build_daily_sets.py"

# Force rebuild
ssh root@104.248.147.155 "docker exec ai-chatbot-rag python3 /app/build_daily_sets.py --rebuild"

# Check status
ssh root@104.248.147.155 "docker exec ai-chatbot-rag python3 /app/build_daily_sets.py --check"

# Add to cron (every 25 days at 3am)
ssh root@104.248.147.155 "crontab -l | { cat; echo '0 3 */25 * * docker exec ai-chatbot-rag python3 /app/build_daily_sets.py'; } | crontab -"
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

### 12. Scripts Management (MANDATORY — NEVER git push scripts)

**All utility/admin scripts MUST live in `scripts/` folder (git-ignored).**

**Why:**
- Scripts often contain hardcoded credentials or DB mutations
- One-off scripts don't belong in the application repo history
- `scripts/` is in `.gitignore` — will never be committed

**Correct workflow:**
```bash
# 1. Create/edit script locally in scripts/
vim scripts/my_migration.py

# 2. Copy & run on server WITHOUT git push
./copy-and-run.sh scripts/my_migration.py --bg --deps

# Or manually:
scp scripts/my_migration.py root@104.248.147.155:/tmp/
ssh root@104.248.147.155 "docker cp /tmp/my_migration.py ai-chatbot-rag:/app/ && docker exec ai-chatbot-rag python3 /app/my_migration.py"
```

**NEVER do:**
```bash
# ❌ WRONG: pushing scripts to git
git add scripts/
git push
# ❌ WRONG: running deploy just to run a script
./deploy-compose-with-rollback.sh  # for a script change
```

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

❌ Full deploy when ONLY `src/api/` or `src/services/` changed (slow, 150s wait)
✅ `./deploy-app-only.sh` when only API/service code changed (30s) — NOT for worker changes

❌ `./deploy-app-only.sh` when `src/workers/*.py` changed (workers won't get new code!)
✅ `./deploy-compose-with-rollback.sh` when ANY worker file changed (rebuilds all containers)

❌ MongoDB projection missing fields: `{"code": 1, "is_active": 1}` → `doc.get("user_id")` always None
✅ Always include every field you access in the projection!

❌ New standalone Python worker container for lightweight event handling
✅ Merge into `learning-events-worker` using multi-key brpop (saves ~350MB RAM)

❌ Checking logs of `payment-events-worker` (container removed, merged)
✅ `docker logs learning-events-worker --tail=50` handles both learning + payment events

❌ Push utility/admin scripts to git (they contain DB credentials & one-off logic)
✅ Keep scripts in `scripts/` folder (git-ignored) and copy manually: `./copy-and-run.sh script.py --bg --deps`

❌ Commit scripts that run against production DB directly to the repo
✅ Use `scripts/` folder locally, deploy only `src/` application code via git

### 13. Pronunciation Assessment API

**Endpoints:**
- `POST /api/v1/pronunciation/transcribe` — Transcribe audio to text (FREE, 10/day per user)
- `POST /api/v1/pronunciation/score` — Full phoneme-level scoring (FREE, 10/day per user)

**Input format:**
```json
{"audio_base64": "<base64>", "expected_text": "hello world", "audio_mime_type": "audio/webm"}
```

**Models (lazy-loaded in `ai-chatbot-rag` container):**
- `faster-whisper tiny (int8)` — already cached, used for transcription
- `facebook/wav2vec2-lv-60-espeak-cv-ft` — phoneme recognition (~370MB, loads on first `/score` request)

**Key dependency:** `eng_to_ipa>=0.0.2` — must be in `requirements.txt` for English→IPA reference pronunciation

**Service file:** `src/services/pronunciation_service.py`
**Routes file:** `src/api/pronunciation_routes.py`

**Score output:** `overall_score` (0.0–1.0) + per-word + per-phoneme alignment (correct/substitution/deletion/insertion)

**RAM impact:** Wav2Vec2 adds ~370MB to `ai-chatbot-rag` (limit 7GB, container typically ~2GB loaded)

**Supports:** single word, phrase, or full sentence in English

**Common mistakes:**
- ❌ Using old `google.generativeai` SDK for Wav2Vec2 — it's a HuggingFace model loaded via `transformers`
- ❌ Forgetting `eng_to_ipa` in requirements.txt — causes ImportError on first `/score` request
- ✅ Models are lazy-loaded (singletons) — only loaded on first request, no startup cost

## Cloudflare Worker — Community API (`/Users/user/Code/db-wordai-community`)

### ⚠️ CRITICAL: Always deploy after pushing

**`git push` alone does NOT deploy the worker.** Cloudflare Workers has NO CI/CD configured.

After EVERY code change to `db-wordai-community`, you MUST run both:
```bash
cd /Users/user/Code/db-wordai-community
git add -A && git commit -m "..." && git push
npx wrangler deploy
```

**NEVER skip `npx wrangler deploy`** — without it, pushed code never goes live on Cloudflare.

### Worker details
- **URL**: `https://db-wordai-community.hoangnguyen358888.workers.dev`
- **D1 Database**: `wordai_community` (id: `2059665e-e2a0-4dee-98f0-6f8e28f500b7`) — binding: `DB`
- **Auth secret**: Cloudflare Secrets Store binding `SECRET`, store `76480feff5ab4442b3c347bb824b7654`, secret name `wordai` (see `wrangler.jsonc → secrets_store_secrets`)

### ⚠️ CRITICAL: Worker secret env var

All scripts that call `/query` or `/rest/*` on this worker **MUST** use `COMMUNITY_WORKER_SECRET` as the env var name:

```bash
# ✅ Correct — used by ALL community worker scripts
COMMUNITY_WORKER_SECRET=<value> node scripts/seed-d1.js
COMMUNITY_WORKER_SECRET=<value> node scripts/generate-fake-comments.js
```

The value to use is stored in Cloudflare Secrets Store. Retrieve it with:
```bash
cd /Users/user/Code/db-wordai-community
npx wrangler secrets-store secret get --store-id 76480feff5ab4442b3c347bb824b7654 wordai
```

**NEVER use `D1_SECRET`, `WORKER_SECRET`, or any other name** — always `COMMUNITY_WORKER_SECRET`.

The worker checks auth with:
```ts
const secret = await env.SECRET.get(); // fetched from Cloudflare Secrets Store at runtime
if (token !== secret) return c.json({ error: 'Unauthorized' }, 401);
```


## Quick Reference Links

- Full docs: `/SYSTEM_REFERENCE.md`
- Redis pattern: `/REDIS_STATUS_PATTERN.md`
- API docs: Server `/docs` endpoint
- Question types: `/QUESTION_TYPES_JSON_SCHEMA.md`

---

**Last Updated:** March 26, 2026
**For:** GitHub Copilot, Cursor AI, and other AI coding assistants
