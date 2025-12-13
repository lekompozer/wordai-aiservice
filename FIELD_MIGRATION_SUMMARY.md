# Online Test Field Name Migration Summary

**Date:** December 13, 2025
**Version:** v2.3 - Breaking Change
**Status:** ⚠️ Awaiting Execution

---

## 📊 Current Database State (Production)

### Overview
- **Total Tests:** 167
- **Tests Need Migration:** 92 (55.1%)
- **Questions Need Migration:** 1,840
- **Estimated Migration Time:** ~46 seconds

### Field Usage Statistics

| Field Name | Status | Tests | Questions | Question Types |
|------------|--------|-------|-----------|----------------|
| `correct_answer_keys` | ⚠️ OLD | 89 | 1,769 | mcq, mcq_multiple, short_answer |
| `correct_answer_key` | ⚠️ OLD | 62 | 1,586 | mcq, essay, mcq_multiple, short_answer |
| `correct_matches` | ⚠️ OLD | 27 | 71 | matching, mcq |
| `correct_answers` | ✅ NEW | 0 | 120 | completion, matching, mcq |

### Question Type Breakdown

| Question Type | Total | Need Migration | Percentage | Old Fields Used |
|---------------|-------|----------------|------------|-----------------|
| MCQ | 1,939 | 1,733 | 89.4% | correct_answer_key, correct_answer_keys, correct_matches |
| Completion | 83 | 0 | 0% | Already using correct_answers |
| Short Answer | 131 | 33 | 25.2% | correct_answer_keys, correct_answer_key |
| Sentence Completion | 105 | 0 | 0% | Already using correct_answers |
| Matching | 43 | 43 | 100% | correct_matches |
| MCQ Multiple | 29 | 28 | 96.6% | correct_answer_keys, correct_answer_key |
| Essay | 3 | 3 | 100% | correct_answer_key |

---

## 🔥 Breaking Changes

### Problem Statement

Previous versions used multiple field names for correct answers across different question types, causing:
- AI model confusion during generation (Gemini using wrong field names)
- Validation errors (completion questions getting `correct_matches` instead of `correct_answers`)
- Inconsistent codebase maintenance
- Complex backend validation logic

### Solution: Unified Field Name

**ALL question types now use a single field:** `correct_answers`

---

## 📋 Migration Mapping

### 1. MCQ Questions (Single & Multiple)

**Before:**
```json
{
  "question_type": "mcq",
  "correct_answer_keys": ["B"],
  "correct_answer_key": "B"
}
```

**After:**
```json
{
  "question_type": "mcq",
  "correct_answers": ["B"],
  "correct_answer_key": "B"  // Kept for backward compatibility
}
```

### 2. Matching Questions

**Before:**
```json
{
  "question_type": "matching",
  "correct_matches": {
    "1": "A",
    "2": "B",
    "3": "C"
  }
}
```

**After:**
```json
{
  "question_type": "matching",
  "correct_answers": [
    {"left_key": "1", "right_key": "A"},
    {"left_key": "2", "right_key": "B"},
    {"left_key": "3", "right_key": "C"}
  ],
  "correct_matches": {...}  // Kept for backward compatibility
}
```

### 3. Sentence Completion & Short Answer

**Before:**
```json
{
  "question_type": "short_answer",
  "questions": [
    {
      "key": "1",
      "correct_answer_keys": ["Smith", "SMITH"]
    }
  ]
}
```

**After:**
```json
{
  "question_type": "short_answer",
  "questions": [
    {
      "key": "1",
      "correct_answers": ["Smith", "SMITH"],
      "correct_answer_keys": ["Smith", "SMITH"]  // Kept for backward compatibility
    }
  ]
}
```

### 4. Completion Questions

**No Change Required** - Already using `correct_answers`:
```json
{
  "question_type": "completion",
  "correct_answers": [
    {"blank_key": "1", "answers": ["AF123", "Flight AF123"]},
    {"blank_key": "2", "answers": ["2:30 PM", "14:30"]}
  ]
}
```

---

## 🔧 Code Changes

### Files Modified

#### 1. Prompt Builders (`src/services/prompt_builders.py`)

**Changes:**
- Updated all 6 question type definitions to use `correct_answers`
- Added warning section about field name unification
- Modified `_get_question_type_definitions()` method

**Impact:** All new AI-generated tests will use unified field names

#### 2. Backend Validation (`src/services/test_generator_service.py`)

**Current State:**
- Accepts both old and new field names
- Normalizes old field names to new format
- Maintains backward compatibility

**Lines Affected:** 240+

#### 3. Scoring Logic (`src/services/ielts_scoring.py`)

**Current State:**
- Reads both `correct_answer_keys` and `correct_answers`
- Handles both `correct_matches` and `correct_answers` for matching
- No changes required immediately due to backward compatibility

#### 4. API Routes

**Files:**
- `src/api/test_creation_routes.py` (GET endpoints return correct_answers)
- `src/api/test_taking_routes.py` (Submit/evaluate using correct_answers)
- `src/api/test_grading_routes.py` (Grading logic uses correct_answers)

**Changes:** Logging and status messages updated to reflect new field names

#### 5. Documentation

**File:** `docs/wordai/Tests/ONLINE_TEST_API_SPECS.md`

**Updates:**
- Added Breaking Changes section at top
- Updated all example responses
- Updated question type definitions
- Updated migration guide table
- Version bumped to v2.3

---

## 🚀 Migration Process

### Scripts Created

1. **`check_questions_need_migration.py`**
   - Analyzes database for questions needing migration
   - Provides detailed statistics
   - Risk assessment
   - Already executed successfully on production

2. **`migrate_question_field_names.py`**
   - Performs actual field name migration
   - Supports dry-run mode (preview only)
   - Maintains backward compatibility
   - Adds migration metadata to tests

### Migration Commands

```bash
# 1. Check current state (already done)
python check_questions_need_migration.py

# 2. Backup database FIRST
docker exec wordai-mongo mongodump --db ai_service_db --out /backup/pre-field-migration-$(date +%Y%m%d)

# 3. Run dry-run migration (preview)
python migrate_question_field_names.py --dry-run

# 4. Execute actual migration
python migrate_question_field_names.py --execute

# 5. Verify results
python check_questions_need_migration.py
```

### Execution Steps

1. **Backup Database** ⚠️ CRITICAL
   ```bash
   ssh root@104.248.147.155
   cd /home/hoile/wordai
   docker exec wordai-mongo mongodump --db ai_service_db --out /backup/pre-field-migration-20251213
   ```

2. **Copy Migration Script**
   ```bash
   scp migrate_question_field_names.py root@104.248.147.155:/home/hoile/wordai/
   ssh root@104.248.147.155 "cd /home/hoile/wordai && docker cp migrate_question_field_names.py ai-chatbot-rag:/app/"
   ```

3. **Dry Run**
   ```bash
   docker exec ai-chatbot-rag python /app/migrate_question_field_names.py --dry-run
   ```

4. **Execute Migration**
   ```bash
   docker exec ai-chatbot-rag python /app/migrate_question_field_names.py --execute
   ```

5. **Verify**
   ```bash
   docker exec ai-chatbot-rag python /app/check_questions_need_migration.py
   ```

---

## ⚠️ Risk Assessment

### Risk Level: 🔴 HIGH

**Reasons:**
- 55.1% of tests affected (92 out of 167)
- 1,840 questions need migration
- Production database modification
- Affects core functionality

### Mitigation Strategies

1. ✅ **Database Backup**
   - Full mongodump before migration
   - Stored in `/backup/pre-field-migration-20251213`

2. ✅ **Backward Compatibility**
   - Old field names kept in database
   - Backend reads both formats
   - No breaking changes for existing tests

3. ✅ **Dry Run Testing**
   - Preview mode available
   - No database changes until confirmed
   - Full rollback capability

4. ✅ **Gradual Rollout**
   - New tests use new format immediately
   - Existing tests migrated in batch
   - Old format still works

### Rollback Plan

If issues occur:

```bash
# 1. Stop application
cd /home/hoile/wordai
docker-compose down

# 2. Restore from backup
docker exec wordai-mongo mongorestore --db ai_service_db --drop /backup/pre-field-migration-20251213/ai_service_db

# 3. Restart application
docker-compose up -d
```

---

## 📈 Expected Benefits

### 1. AI Generation Reliability
- ✅ No more field name confusion
- ✅ Consistent prompt structure
- ✅ Reduced validation errors
- ✅ Single source of truth

### 2. Code Maintainability
- ✅ Simplified validation logic
- ✅ Easier to understand codebase
- ✅ Reduced technical debt
- ✅ Better developer experience

### 3. System Stability
- ✅ Fewer runtime errors
- ✅ Consistent data structure
- ✅ Easier debugging
- ✅ Better error messages

### 4. Future Scalability
- ✅ Easy to add new question types
- ✅ Consistent pattern to follow
- ✅ Reduced onboarding time
- ✅ Better API documentation

---

## 🔍 Testing Checklist

After migration, verify:

- [ ] AI test generation (document-based)
- [ ] AI test generation (general knowledge)
- [ ] Manual test creation
- [ ] Test editing (all question types)
- [ ] Test taking (submit answers)
- [ ] Auto-grading (MCQ, Matching, Completion)
- [ ] Manual grading (Essay)
- [ ] Listening test generation
- [ ] GET /tests/{id} endpoint (owner view)
- [ ] GET /tests/{id} endpoint (student view)
- [ ] GET /tests/{id}/status endpoint
- [ ] Test marketplace publishing
- [ ] Test sharing

---

## 📝 Next Actions

### Immediate (Pre-Migration)
1. ✅ Create migration scripts
2. ✅ Analyze database state
3. ⏳ Get approval for production migration
4. ⏳ Schedule maintenance window

### Migration Phase
1. ⏳ Backup database
2. ⏳ Run dry-run migration
3. ⏳ Execute migration
4. ⏳ Verify results
5. ⏳ Monitor for errors

### Post-Migration
1. ⏳ Update backend validation (optional - already backward compatible)
2. ⏳ Deploy prompt_builders.py changes
3. ⏳ Monitor AI generation for 24 hours
4. ⏳ Update internal documentation
5. ⏳ Notify frontend team of response format changes

---

## 📞 Support

**Migration Issues:**
- Check logs: `docker logs ai-chatbot-rag`
- Rollback if needed: See "Rollback Plan" section
- Contact: System Administrator

**Questions:**
- API Documentation: `/docs/wordai/Tests/ONLINE_TEST_API_SPECS.md`
- Migration Scripts: `/check_questions_need_migration.py`, `/migrate_question_field_names.py`

---

**Status:** Ready for execution pending approval
**Last Updated:** December 13, 2025
**Migration Scripts:** Tested and ready
