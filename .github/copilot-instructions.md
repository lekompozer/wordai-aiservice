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

**Deploy:** `./deploy-compose-with-rollback.sh` (full rebuild)
**Nginx only:** `./restart-nginx.sh` (fast reload)

### 5. MongoDB Access (Production)

```bash
docker exec mongodb mongosh ai_service_db \
  -u ai_service_user \
  -p ai_service_2025_secure_password \
  --authenticationDatabase admin
```

### 6. Redis Access (Production)

```bash
docker exec redis-server redis-cli

# Check job status
HGETALL "job:{job_id}"

# List all jobs
KEYS "job:*"
```

## When Implementing New Features

1. **Check SYSTEM_REFERENCE.md** for existing patterns
2. **Use DBManager** for database connections
3. **Use Redis pattern** for async job status
4. **Follow queue patterns** from existing workers
5. **SSH commands** must use `su - hoile -c` wrapper
6. **Test locally** before deploying to production

## Common Mistakes to Avoid

❌ MongoDB: `db.jobs.find_one()` for job status polling
✅ Redis: `await get_job_status(queue.redis_client, job_id)`

❌ Direct SSH: `ssh root@IP "cd /home/hoile/wordai && command"`
✅ With su: `ssh root@IP "su - hoile -c 'cd /home/hoile/wordai && command'"`

❌ Old import: `from src.services.online_test_utils import get_mongodb_service`
✅ New import: `from src.database.db_manager import DBManager`

❌ Wrong queue method: `await queue.enqueue(job_id, data)`
✅ Correct method: `await queue.enqueue_generic_task(task)`

❌ Direct field access: `test["time_limit_minutes"]` (may cause KeyError)
✅ Safe access: `test.get("time_limit_minutes", 60)` (with default)

## Quick Reference Links

- Full docs: `/SYSTEM_REFERENCE.md`
- Redis pattern: `/REDIS_STATUS_PATTERN.md`
- API docs: Server `/docs` endpoint
- Question types: `/QUESTION_TYPES_JSON_SCHEMA.md`

---

**Last Updated:** December 28, 2025
**For:** GitHub Copilot, Cursor AI, and other AI coding assistants
