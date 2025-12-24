# Database Connection Migration Checklist

**Objective:** Migrate all endpoints to use standardized `DBManager` pattern
**Target Database:** `ai_service_db` (production verified: 17.77 MB, 60+ collections)
**Date:** December 24, 2025

---

## 📊 Migration Status Overview

| Priority | Category | Files | Status |
|----------|----------|-------|--------|
| **P0** | Direct MongoClient (WRONG) | 3 | 🔴 Not Started |
| **P1** | Mixed Usage (Cleanup) | 3 | 🔴 Not Started |
| **P2** | Slides/Narration | 3 | 🔴 Not Started |
| **P3** | Public Routes | 1 | 🔴 Not Started |
| **P4** | Test System | 6+ | 🔴 Not Started |

**Total Files to Migrate:** 16 files
**Completed:** 0/16 (0%)

---

## 🔴 Priority 0: Fix Direct MongoClient (CRITICAL)

### 1. marketplace_routes.py
- **Pattern:** Direct `MongoClient`
- **Lines:** 34, 53
- **Usage:** Custom `get_mongodb()` function
- **Action:**
  - [ ] Replace `from pymongo import MongoClient` with `from src.database.db_manager import DBManager`
  - [ ] Remove custom `get_mongodb()` function
  - [ ] Replace `mongo_client = MongoClient(mongo_uri)` with `db_manager = DBManager(); db = db_manager.db`
  - [ ] Update all `db` references
  - [ ] Test marketplace listing endpoints
- **Estimated Time:** 15 minutes
- **Risk:** Medium (marketplace critical feature)

### 2. marketplace_transactions_routes.py
- **Pattern:** Direct `MongoClient`
- **Lines:** 17, 36
- **Usage:** Custom `get_mongodb()` function
- **Action:**
  - [ ] Replace `from pymongo import MongoClient` with `from src.database.db_manager import DBManager`
  - [ ] Remove custom `get_mongodb()` function
  - [ ] Replace initialization pattern
  - [ ] Update transaction handling
  - [ ] Test purchase flows
- **Estimated Time:** 15 minutes
- **Risk:** HIGH (payment-related)

### 3. test_statistics_routes.py
- **Pattern:** Direct `MongoClient` + Custom `get_mongodb_service()`
- **Lines:** 10, 23-30
- **Usage:** Custom implementation (not from online_test_utils)
- **Action:**
  - [ ] Replace `from pymongo import MongoClient` with `from src.database.db_manager import DBManager`
  - [ ] Remove custom `get_mongodb_service()` function (lines 23-35)
  - [ ] Update all endpoint usages
  - [ ] Test statistics endpoints
- **Estimated Time:** 20 minutes
- **Risk:** Low (statistics only)

---

## 🟡 Priority 1: Clean Mixed Usage

### 4. ai_editor_routes.py
- **Current:** Uses BOTH `DBManager` + `get_mongodb_service`
- **Lines:**
  - Import DBManager: line 31
  - Import get_mongodb_service: line 20
  - Usage get_mongodb_service: line 42
- **Action:**
  - [ ] Remove `from src.services.online_test_utils import get_mongodb_service`
  - [ ] Find line 42 usage: `mongo_service = get_mongodb_service()`
  - [ ] Replace with existing `DBManager` pattern
  - [ ] Remove `mongo_service` variable
  - [ ] Update references to use `db_manager.db`
  - [ ] Test AI editor endpoints
- **Estimated Time:** 10 minutes
- **Risk:** Low

### 5. book_advanced_routes.py
- **Current:** Uses BOTH `DBManager` + `get_mongodb_service`
- **Lines:**
  - Import DBManager: line 29
  - Import get_mongodb_service: line 24
- **Action:**
  - [ ] Remove `from src.services.online_test_utils import get_mongodb_service`
  - [ ] Search for `get_mongodb_service()` calls
  - [ ] Replace with `DBManager` pattern
  - [ ] Test advanced book features
- **Estimated Time:** 10 minutes
- **Risk:** Low

### 6. document_editor_routes.py
- **Current:** Uses BOTH `DBManager` + `get_mongodb_service`
- **Lines:**
  - Import DBManager: line 31
  - Import get_mongodb_service: line 29
  - Usage: line 1111 (narration count check)
- **Action:**
  - [ ] Remove `from src.services.online_test_utils import get_mongodb_service`
  - [ ] Line 1111: Replace `get_mongodb_service().db.slide_narrations.count_documents(...)` with `db_manager.db.slide_narrations.count_documents(...)`
  - [ ] Ensure `db_manager` is available in that scope (may need to pass as parameter or init locally)
  - [ ] Test document get endpoint
- **Estimated Time:** 10 minutes
- **Risk:** Low

---

## 🟠 Priority 2: Migrate Slides/Narration

### 7. slide_narration_routes.py
- **Current:** Pure `get_mongodb_service` (20+ usages)
- **Line:** 50 import
- **Usages:** Lines 152, 153, 268, 375, 404, 467, 478, 521, 558, 635, 675, 738, 771, 839, 843, 923, 945, 974, 1032, 1056...
- **Action:**
  - [ ] Add `from src.database.db_manager import DBManager` at top
  - [ ] Remove `from src.services.online_test_utils import get_mongodb_service`
  - [ ] Add module-level initialization: `db_manager = DBManager(); db = db_manager.db`
  - [ ] Replace ALL `get_mongodb_service().db` with `db`
  - [ ] Test:
    - [ ] Generate subtitles
    - [ ] Generate audio
    - [ ] List narrations
    - [ ] Delete narrations
    - [ ] Library audio list
- **Estimated Time:** 30 minutes
- **Risk:** HIGH (narration system critical)

### 8. slide_ai_generation_routes.py
- **Current:** Pure `get_mongodb_service`
- **Line:** 31 import
- **Action:**
  - [ ] Replace import
  - [ ] Add module-level DBManager
  - [ ] Replace all usages
  - [ ] Test slide AI generation
- **Estimated Time:** 20 minutes
- **Risk:** Medium

### 9. listening_audio_routes.py
- **Current:** Pure `get_mongodb_service` (test audio generation)
- **Lines:** 15, 96, 235, 416
- **Action:**
  - [ ] Replace import
  - [ ] Add module-level DBManager
  - [ ] Replace all usages
  - [ ] Test listening test audio generation
- **Estimated Time:** 20 minutes
- **Risk:** Medium

---

## 🔵 Priority 3: Public Routes

### 10. public_routes.py
- **Current:** Pure `get_mongodb_service`
- **Lines:** 11, 55
- **Usage:** Public test access (no auth)
- **Action:**
  - [ ] Replace import with DBManager
  - [ ] Update initialization
  - [ ] Test public test access
- **Estimated Time:** 10 minutes
- **Risk:** Low

---

## 🟣 Priority 4: Test System (Long-term)

### 11. test_translation_routes.py
- **Lines:** 16, 68
- **Estimated Time:** 15 minutes

### 12. test_creation_routes.py
- **Usage:** 20+ endpoints
- **Estimated Time:** 60+ minutes
- **Risk:** HIGH

### 13. test_grading_routes.py
- **Estimated Time:** 30 minutes

### 14. test_marketplace_routes.py
- **Estimated Time:** 30 minutes

### 15. test_taking_routes.py
- **Current:** Mixed (has DBManager at lines 2527, 2644)
- **Estimated Time:** 45 minutes

### 16. test_evaluation_routes.py
- **Estimated Time:** 30 minutes

### 17. test_sharing_routes.py
- **Estimated Time:** 30 minutes

**Test System Total:** 240+ minutes (4+ hours)
**Strategy:** Dedicate separate session for test system migration

---

## ✅ Migration Procedure (Per File)

### Pre-Migration Checklist
- [ ] Read current file to understand structure
- [ ] Identify all `get_mongodb_service()` or `MongoClient` usages
- [ ] Check if file already has `DBManager` import
- [ ] Note any special patterns (e.g., function-scoped vs module-level)

### Migration Steps
1. **Update Imports**
   ```python
   # Remove:
   from src.services.online_test_utils import get_mongodb_service
   # OR
   from pymongo import MongoClient

   # Add (if not exists):
   from src.database.db_manager import DBManager
   ```

2. **Initialize DBManager**

   **Module-level (preferred for routes):**
   ```python
   # After imports
   db_manager = DBManager()
   db = db_manager.db
   ```

   **Function-level (if needed):**
   ```python
   def endpoint():
       db_manager = DBManager()
       db = db_manager.db
   ```

3. **Replace Usages**
   ```python
   # Old:
   mongo_service = get_mongodb_service()
   db = mongo_service.db
   result = db.collection.find(...)

   # New:
   result = db.collection.find(...)  # Use module-level db
   ```

4. **Test Endpoints**
   - Run affected endpoints locally
   - Check logs for connection issues
   - Verify database operations work

5. **Commit**
   ```bash
   git add <file>
   git commit -m "fix: Migrate <file> to DBManager pattern"
   ```

### Post-Migration Checklist
- [ ] All imports updated
- [ ] No `get_mongodb_service` references remain
- [ ] No direct `MongoClient` references remain
- [ ] Endpoints tested and working
- [ ] Committed with descriptive message
- [ ] Update this checklist status

---

## 🧪 Testing Strategy

### Local Testing
```bash
# Start local services
docker-compose up -d

# Test endpoint
curl -X POST http://localhost:8000/api/endpoint \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### Production Testing (After Deploy)
```bash
# Check logs
ssh root@104.248.147.155 "docker logs ai-chatbot-rag --tail 100 | grep -i 'mongodb\|database\|connection'"

# Verify database connection
ssh root@104.248.147.155 "docker exec mongodb mongosh -u admin -p <pass> --authenticationDatabase admin ai_service_db --quiet --eval 'db.stats()'"
```

---

## 📝 Notes & Decisions

### Database Name Standardization
- ✅ **Production:** `ai_service_db` (verified 17.77 MB)
- ✅ **Environment Variable:** `MONGODB_NAME=ai_service_db`
- ✅ **DBManager Default:** `ai_service_db` ✅
- ✅ **online_test_utils Default:** `ai_service_db` (fixed from `wordai_db`)

### Connection Pattern
```python
# MONGODB_URI_AUTH (has credentials) → MONGODB_URI (fallback)
# Both DBManager and get_mongodb_service use this priority
```

### Why Not Migrate Test System Immediately?
- 6+ files, 100+ endpoints
- High risk (test creation, grading, taking)
- Needs dedicated testing session
- Current pattern works (using correct db via env)
- Focus on critical bugs first

---

## 🚀 Deployment Plan

### Phase 1: Critical Fixes (P0)
1. Fix 3 Direct MongoClient files
2. Test locally
3. Commit + push
4. Deploy to production
5. Monitor logs for 30 minutes

### Phase 2: Cleanup (P1)
1. Clean 3 mixed files
2. Test locally
3. Commit + push
4. Deploy

### Phase 3: Slides/Narration (P2)
1. Migrate slide_narration_routes
2. Test narration features thoroughly
3. Migrate other 2 files
4. Deploy

### Phase 4: Test System (P4)
1. Create separate migration plan
2. Schedule dedicated session
3. Migrate in batches (2-3 files per deploy)

---

## 📊 Success Metrics

- [ ] All Direct MongoClient removed (0/3 remaining)
- [ ] All mixed usage cleaned (0/3 remaining)
- [ ] Slides/narration migrated (0/3 done)
- [ ] No database connection errors in production logs
- [ ] All existing features working
- [ ] SYSTEM_REFERENCE.md updated with final status

---

**Last Updated:** December 24, 2025
**Next Action:** Start Priority 0 migrations
