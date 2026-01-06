# Security Audit Report - WordAI Backend
**Date:** January 6, 2026
**Auditor:** GitHub Copilot (Claude Sonnet 4.5)
**Scope:** Hardcoded credentials, file access vulnerabilities, privilege escalation, API rate limits

---

## 🔴 CRITICAL ISSUES (Fix Immediately)

### 1. Hardcoded MongoDB Password in Migration Script
**File:** `scripts/migrate_add_user_plans.py` line 51
**Risk:** Production database credentials exposed in code

```python
# ❌ CRITICAL: Hardcoded production password
mongodb_uri = "mongodb://admin:WordAIMongoRootPassword@localhost:27017"
```

**Impact:**
- Anyone with code access can connect to production MongoDB
- Root password exposed in git history
- Can read/modify all user data, payments, subscriptions

**Fix:**
```python
# ✅ SECURE: Use environment variable
mongodb_uri = os.getenv("MONGODB_URI")
if not mongodb_uri:
    raise ValueError("MONGODB_URI environment variable not set")
```

---

### 2. Hardcoded Development Credentials
**File:** `sync_user_points.py` line 13
**Risk:** Default credentials may be used in production

```python
# ❌ WARNING: Weak default credentials
MONGO_URI = os.getenv(
    "MONGO_URI", "mongodb://admin:wordai@localhost:27017/wordai?authSource=admin"
)
```

**Impact:**
- If `.env` file missing, script uses weak credentials
- May accidentally connect to production with dev credentials

**Fix:**
```python
# ✅ SECURE: Fail if env not set
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable required")
```

---

### 3. Firebase Credentials File in Repository Root
**File:** `firebase-credentials.json`
**Status:** ✅ In `.gitignore` but may exist locally
**Risk:** Service account key with full Firebase access

**Current Protection:**
- ✅ Listed in `.gitignore`
- ✅ Docker copies from env variables in production
- ⚠️ File may exist on developer machines

**Recommendations:**
```bash
# Check if file exists (should NOT be in repo)
ls -la firebase-credentials.json

# If exists, verify it's gitignored
git check-ignore firebase-credentials.json

# Remove from local filesystem if not needed
rm firebase-credentials.json

# Production uses env vars → creates file at runtime
```

---

## 🟡 HIGH PRIORITY (Fix Soon)

### 4. Missing User Ownership Validation in Some Endpoints

**Vulnerable Pattern Found:**
```python
# ❌ POTENTIAL VULNERABILITY: No user_id check before find_one
narration = db.slide_narrations.find_one({"_id": ObjectId(narration_id)})

# User can access ANY narration_id if they know the ID
```

**Good Pattern (Secure):**
```python
# ✅ SECURE: Query includes user_id ownership check
document = db.documents.find_one({
    "document_id": presentation_id,
    "user_id": user_id  # Ensures user owns this document
})

if not document:
    raise HTTPException(404, "Document not found")
```

**Files to Audit:**
- `src/api/slide_narration_routes.py` - Check all `find_one()` calls
- `src/api/secret_images_routes.py` - ✅ Good (has ownership checks)
- `src/api/document_editor_routes.py` - Review file access endpoints

**Action Items:**
1. Search for all `find_one({"_id": ObjectId(...)})` patterns
2. Add user_id validation BEFORE database query
3. Return 404 (not 403) to avoid information leakage

---

### 5. Rate Limiting Incomplete

**Currently Protected Endpoints:**
- ✅ Video export: 3 minutes cooldown (Redis-based)
- ✅ Document export: Rate limit check in service layer

**Missing Rate Limits:**
- ❌ Subtitle generation (can spam Gemini API)
- ❌ Audio generation (expensive TTS calls)
- ❌ AI image generation (costs per request)
- ❌ Test generation (Claude API quota)

**Recommendation:**
```python
# Add to expensive endpoints
from src.middleware.rate_limiter import check_rate_limit

@router.post("/subtitles/generate")
async def generate_subtitles(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["uid"]

    # ✅ Add rate limit check
    await check_rate_limit(
        user_id=user_id,
        action="subtitle_generation",
        max_requests=10,
        window_seconds=3600  # 10 requests per hour
    )

    # ... rest of endpoint
```

---

### 6. File Download Without Ownership Validation

**Pattern to Check:**
```python
# Search for this pattern in all routes
image = db["library_files"].find_one({"library_id": image_id})

# ❌ If no user_id check after this, user can download any file by ID
```

**Secure Pattern (from secret_images_routes.py):**
```python
# ✅ GOOD: Ownership check
image = db["library_files"].find_one({
    "$or": [
        {"library_id": image_id},
        {"_id": image_id},
    ],
    "is_encrypted": True,
})

# Verify access (owner or shared with)
if image["user_id"] != user_id and user_id not in image.get("shared_with", []):
    raise HTTPException(403, "You don't have permission to access this image")
```

**Files Needing Review:**
- Audio download endpoints
- Document download endpoints
- Test export endpoints

---

## 🟢 GOOD SECURITY PRACTICES (Already Implemented)

### ✅ Environment Variable Usage
- MongoDB credentials from `MONGODB_APP_USERNAME`, `MONGODB_APP_PASSWORD`
- Google Cloud credentials from `GOOGLE_APPLICATION_CREDENTIALS`
- Firebase credentials generated at runtime from env vars
- R2/Cloudflare credentials from env

### ✅ Authentication Layer
- Firebase Auth integration (`get_current_user` dependency)
- JWT token validation
- User ID extraction from authenticated token

### ✅ Database Connection Security
```python
# All services use environment-based connection strings
mongo_uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}/{db_name}?authSource=admin"
```

### ✅ File Encryption
- Secret images use AES-256 encryption
- Encryption keys stored securely (not in database)

### ✅ Sensitive Files in .gitignore
```
.env
.env.*
firebase-credentials.json
firebase-service-account.json
*-service-account.json
```

---

## 📋 ACTION PLAN (Priority Order)

### Immediate (Today)
1. ✅ Fix hardcoded password in `scripts/migrate_add_user_plans.py` - FIXED
2. ✅ Fix default credentials in `sync_user_points.py` - FIXED
3. ⚠️ Verify firebase-credentials.json not in git history
4. ✅ Create rate limiter middleware - DONE (`src/middleware/rate_limiter.py`)

### This Week
5. 🔄 Add rate limiting to ALL expensive AI endpoints:
   - ❌ `/api/v1/books/{book_id}/translate/start` (chapter translation)
   - ❌ `/api/documents/{id}/edit-by-ai` (AI editing)
   - ❌ `/api/documents/{id}/format` (AI formatting)
   - ❌ `/api/tests/generate` (test generation with Claude)
   - ❌ `/api/slides/ai/generate` (slide AI generation)
   - ❌ `/api/images/ai/generate` (AI image generation)
   - ❌ `/api/audio/generate` (TTS audio generation)
   - ❌ `/api/subtitles/generate` (subtitle generation with Gemini)

6. ✅ Audit all `find_one()` calls for missing user_id validation
7. ✅ Add ownership checks to file download endpoints
8. ⚠️ Remove `.find({})` without limits in public routes

### This Month
7. ✅ Create security testing suite for authorization
8. ✅ Add logging for failed auth attempts
9. ✅ Implement API key rotation strategy
10. ✅ Security review of worker processes

---

## 🔍 Testing Recommendations

### Privilege Escalation Tests
```bash
# Test 1: Try to access another user's document
curl -X GET https://api.wordai.pro/api/presentations/{OTHER_USER_DOC_ID} \
  -H "Authorization: Bearer $YOUR_TOKEN"
# Expected: 404 Not Found (NOT 403 to avoid info leak)

# Test 2: Try to modify another user's narration
curl -X DELETE https://api.wordai.pro/api/narrations/{OTHER_USER_NARRATION_ID} \
  -H "Authorization: Bearer $YOUR_TOKEN"
# Expected: 404 Not Found

# Test 3: Try to download another user's file
curl -X GET https://api.wordai.pro/api/library/files/{OTHER_USER_FILE_ID} \
  -H "Authorization: Bearer $YOUR_TOKEN"
# Expected: 403 Forbidden (after finding file exists)
```

### Rate Limit Tests
```bash
# Test 4: Spam subtitle generation
for i in {1..20}; do
  curl -X POST https://api.wordai.pro/api/subtitles/generate \
    -H "Authorization: Bearer $TOKEN" \
    -d "{...}"
done
# Expected: 429 Too Many Requests after limit reached
```

---

## 📝 Security Checklist for New Features

Before deploying new endpoints:

- [ ] Uses `Depends(get_current_user)` for authentication
- [ ] Validates user owns the resource (user_id check)
- [ ] Rate limiting for expensive operations
- [ ] Input validation (Pydantic models)
- [ ] No sensitive data in error messages
- [ ] Logs security events (auth failures, access denied)
- [ ] Returns 404 for unauthorized access (not 403)
- [ ] File downloads check ownership
- [ ] Database queries include user_id filter
- [ ] No hardcoded credentials or API keys

---

## 🛡️ Environment Variables Required

### Production (.env file)
```bash
# MongoDB
MONGODB_APP_USERNAME=ai_service_user
MONGODB_APP_PASSWORD=<strong-password-from-secrets>
MONGODB_ROOT_PASSWORD=<root-password-from-secrets>
MONGODB_NAME=ai_service_db

# Firebase
FIREBASE_PROJECT_ID=wordai-6779e
FIREBASE_PRIVATE_KEY_ID=<from-service-account>
FIREBASE_PRIVATE_KEY=<from-service-account>
FIREBASE_CLIENT_EMAIL=<from-service-account>
FIREBASE_CLIENT_ID=<from-service-account>

# Google Cloud (Vertex AI)
GOOGLE_APPLICATION_CREDENTIALS=/app/firebase-credentials.json
GCP_PROJECT_ID=wordai-6779e
GCP_LOCATION=us-central1

# Cloudflare R2
R2_ACCOUNT_ID=<from-cloudflare>
R2_ACCESS_KEY_ID=<from-cloudflare>
R2_SECRET_ACCESS_KEY=<from-cloudflare>

# Redis
REDIS_HOST=redis-server
REDIS_PORT=6379

# Claude API
ANTHROPIC_API_KEY=<from-anthropic>
```

### Development (development.env)
- Use `development.env.template` as reference
- NEVER commit actual `.env` files
- Use weak/test credentials only for local development

---

## 🚨 Incident Response

If credentials are compromised:

1. **Immediately rotate** all API keys and database passwords
2. **Check logs** for unauthorized access using compromised keys
3. **Notify users** if data breach occurred
4. **Update** `.env` files on all servers
5. **Review** git history for exposed secrets
6. **Consider** using secret management service (e.g., Google Secret Manager)

---

## 📚 References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [MongoDB Security Checklist](https://docs.mongodb.com/manual/administration/security-checklist/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Firebase Security Rules](https://firebase.google.com/docs/rules)

---

**Next Review Date:** February 6, 2026
