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

### 5. Production Deployment (MANDATORY)

**MUST use this command for ALL deployments:**
```bash
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && ./deploy-compose-with-rollback.sh'"
```

**Why this command is required:**
- ✅ Full Docker rebuild (ensures all code changes applied)
- ✅ Automatic rollback if deployment fails
- ✅ Zero-downtime deployment with health checks
- ✅ Pulls latest code from main branch
- ✅ Rebuilds all containers (app, workers, nginx)

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

### 8. API Endpoint Development (CRITICAL - AVOID 404 ERRORS)

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

4. **Deployment:**
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

## Quick Reference Links

- Full docs: `/SYSTEM_REFERENCE.md`
- Redis pattern: `/REDIS_STATUS_PATTERN.md`
- API docs: Server `/docs` endpoint
- Question types: `/QUESTION_TYPES_JSON_SCHEMA.md`

---

**Last Updated:** December 28, 2025
**For:** GitHub Copilot, Cursor AI, and other AI coding assistants
