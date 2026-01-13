# StudyHub Test Duplication - Technical Specification

## Overview

When a teacher adds a test to a StudyHub module, the system **duplicates the entire test** into the same collection (`online_tests`) with a new ID. This ensures complete data isolation while maintaining compatibility with all 67 existing test endpoints.

## Architecture Decision

### Why NOT Separate Collection?

❌ **Rejected Approach**: Create `studyhub_tests` collection
- Would require duplicating 67 endpoints
- test_creation_routes.py: 22 endpoints
- test_taking_routes.py: 13 endpoints
- test_marketplace_routes.py: 9 endpoints
- test_sharing_routes.py: 8 endpoints
- test_grading_routes.py: 6 endpoints
- test_evaluation_routes.py: 5 endpoints
- Others: 4 endpoints

### Why SAME Collection?

✅ **Implemented Approach**: Duplicate in `online_tests` with new ID
- All 67 endpoints work without changes
- Data isolation via separate test IDs
- No code duplication needed
- Simpler architecture and maintenance

## Implementation

### API Endpoint

```http
POST /api/studyhub/modules/{module_id}/content/tests
```

**Request Body:**
```json
{
  "test_id": "693a71f49084fe1017fda718",
  "title": "Custom Title for StudyHub",
  "passing_score": 70,
  "is_required": true,
  "is_preview": false
}
```

### Duplication Logic

```python
# 1. Get original test
original_test = db.online_tests.find_one(
    {"_id": ObjectId(test_id), "creator_id": user_id}
)

# 2. Copy ALL fields from original
studyhub_test = {
    **original_test,  # Spread operator - copies EVERYTHING
    "_id": None,
    
    # NEW StudyHub markers
    "is_studyhub_copy": True,
    "source_test_id": ObjectId(test_id),
    "studyhub_context": {
        "subject_id": module["subject_id"],
        "module_id": ObjectId(module_id),
        "passing_score": passing_score,
        "is_required": is_required,
        "is_preview": is_preview,
    },
    
    # Override specific fields
    "title": title,  # Customizable
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc),
}

# 3. Remove unwanted fields
studyhub_test.pop("_id", None)  # MongoDB generates new ID
studyhub_test.pop("marketplace_config", None)  # Not for sale
studyhub_test.pop("migration_metadata", None)  # Not needed

# 4. Insert into SAME collection
result = db.online_tests.insert_one(studyhub_test)
studyhub_test_id = result.inserted_id
```

### What Gets Copied

#### ✅ Core Fields (100% from original)
```json
{
  "title": "Original title (will be overridden)",
  "description": "Test description",
  "creator_name": "WordAI Team",
  "test_category": "academic",
  "test_type": "mcq",
  "user_query": "Original user query",
  "test_language": "en",
  "source_type": "general_knowledge",
  "source_document_id": null,
  "source_file_r2_key": "file_...",
  "topic": "Test topic",
  "creator_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "time_limit_minutes": 40,
  "num_questions": 40,
  "num_mcq_questions": 40,
  "num_essay_questions": 0,
  "mcq_points": null,
  "essay_points": null,
  "max_retries": 3,
  "passing_score": 55,
  "deadline": null,
  "show_answers_timing": "immediate",
  "creation_type": "ai_generated",
  "status": "ready",
  "progress_percent": 100
}
```

#### ✅ Questions Array (100% copied)
```json
{
  "questions": [
    {
      "question_text": "Full question text...",
      "options": [
        {"option_key": "A", "option_text": "..."},
        {"option_key": "B", "option_text": "..."}
      ],
      "correct_answer_keys": ["C"],
      "explanation": "Full explanation...",
      "max_points": 2,
      "correct_answer_key": "C",
      "question_id": "693a726f9084fe1017fda719",
      "question_type": "mcq",
      "correct_answers": ["C"]
    }
    // ... all 40 questions
  ]
}
```

#### ✅ NEW StudyHub Fields (Added)
```json
{
  "is_studyhub_copy": true,
  "source_test_id": ObjectId("693a71f49084fe1017fda718"),
  "studyhub_context": {
    "subject_id": ObjectId("..."),
    "module_id": ObjectId("..."),
    "passing_score": 70,
    "is_required": true,
    "is_preview": false
  }
}
```

#### 🔄 Overridden Fields
```json
{
  "title": "Custom StudyHub Title",  // From request
  "created_at": "2025-01-13T...",  // Reset
  "updated_at": "2025-01-13T..."   // Reset
}
```

#### ❌ Removed Fields
```json
{
  "_id": "...",  // Removed, new ID generated
  "marketplace_config": {...},  // Not for marketplace
  "migration_metadata": {...}   // Not needed
}
```

## Example: Complete Duplicated Test

### Original Test (Personal)
```json
{
  "_id": ObjectId("693a71f49084fe1017fda718"),
  "title": "PMP Practice Exam | 40 questions",
  "creator_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "questions": [...],  // 40 questions
  "marketplace_config": {
    "is_public": true,
    "price_points": 1
  }
}
```

### Duplicated Test (StudyHub)
```json
{
  "_id": ObjectId("NEW_ID_GENERATED"),
  "title": "Module 1: Project Management Fundamentals",  // Custom
  
  // NEW StudyHub markers
  "is_studyhub_copy": true,
  "source_test_id": ObjectId("693a71f49084fe1017fda718"),
  "studyhub_context": {
    "subject_id": ObjectId("..."),
    "module_id": ObjectId("..."),
    "passing_score": 70,
    "is_required": true,
    "is_preview": false
  },
  
  // ALL original content copied
  "creator_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "questions": [...],  // SAME 40 questions
  "time_limit_minutes": 40,
  "num_questions": 40,
  
  // Reset timestamps
  "created_at": "2025-01-13T...",
  "updated_at": "2025-01-13T...",
  
  // marketplace_config removed (not for sale)
}
```

## Data Isolation

### How It Works

Each test has a **unique `_id`**, so all progress/results are automatically isolated:

```javascript
// Personal test progress
{
  "test_id": ObjectId("693a71f49084fe1017fda718"),
  "user_id": "student123",
  "answers": {...}
}

// StudyHub test progress (different test_id)
{
  "test_id": ObjectId("NEW_STUDYHUB_TEST_ID"),
  "user_id": "student123",
  "answers": {...}
}
```

### Benefits

✅ **Complete Isolation**: Student's progress in StudyHub test ≠ Personal test progress
✅ **Independent Settings**: Each can have different passing scores, time limits
✅ **Separate Analytics**: StudyHub test stats don't affect personal test stats
✅ **No Code Changes**: All endpoints use `test_id`, work with both types

## Endpoint Compatibility

All 67 existing test endpoints work with both personal and StudyHub tests:

### Taking Tests
```http
POST /api/tests/{test_id}/start  # Works with any test_id
POST /api/tests/{test_id}/submit
GET /api/tests/{test_id}/results
```

### Grading
```http
POST /api/tests/{test_id}/grade-essay
GET /api/tests/{test_id}/grading-queue
```

### Marketplace (Filtered)
```http
GET /api/tests/marketplace/published  # Excludes is_studyhub_copy=true
```

### Management
```http
PUT /api/tests/{test_id}  # Update test
DELETE /api/tests/{test_id}  # Delete test
```

## Filtering StudyHub Tests

### List Only StudyHub Tests
```python
studyhub_tests = db.online_tests.find({
    "is_studyhub_copy": True,
    "creator_id": user_id
})
```

### List Only Personal Tests
```python
personal_tests = db.online_tests.find({
    "is_studyhub_copy": {"$ne": True},
    "creator_id": user_id
})
```

### Find Original Test
```python
original = db.online_tests.find_one({
    "_id": studyhub_test["source_test_id"]
})
```

## Database Indexes

Add indexes for efficient queries:

```javascript
db.online_tests.createIndex({"is_studyhub_copy": 1})
db.online_tests.createIndex({"source_test_id": 1})
db.online_tests.createIndex({
  "studyhub_context.module_id": 1
})
```

## Migration from Source (Future)

If source test is updated and needs to sync to StudyHub copies:

```python
# Find all copies of a test
copies = db.online_tests.find({
    "source_test_id": ObjectId(source_test_id)
})

# Update each copy (preserve studyhub_context)
for copy in copies:
    updated = {
        **source_test,
        "_id": copy["_id"],
        "is_studyhub_copy": True,
        "source_test_id": copy["source_test_id"],
        "studyhub_context": copy["studyhub_context"],  # Keep
        "title": copy["title"],  # Keep custom title
    }
    db.online_tests.replace_one({"_id": copy["_id"]}, updated)
```

## Common Queries

### Get StudyHub Test Details
```python
test = db.online_tests.find_one({
    "_id": ObjectId(studyhub_test_id),
    "is_studyhub_copy": True
})

# Access StudyHub settings
passing_score = test["studyhub_context"]["passing_score"]
module_id = test["studyhub_context"]["module_id"]
```

### Count Tests in Module
```python
count = db.online_tests.count_documents({
    "studyhub_context.module_id": ObjectId(module_id)
})
```

### Get Module's Tests
```python
tests = db.online_tests.find({
    "studyhub_context.module_id": ObjectId(module_id)
}).sort("created_at", 1)
```

## Error Handling

### Test Not Found
```python
if not original_test:
    raise HTTPException(
        status_code=404, 
        detail="Test not found or you don't have permission"
    )
```

### Already Added
```python
# Check if already added to module
existing = db.studyhub_module_contents.find_one({
    "module_id": ObjectId(module_id),
    "data.source_test_id": test_id
})

if existing:
    raise HTTPException(
        status_code=400,
        detail="Test already added to this module"
    )
```

## Performance Considerations

### Duplication Speed
- **Single test**: ~5ms (copy + insert)
- **With 40 questions**: ~20ms (full document copy)
- **Negligible overhead**: Spread operator is O(n) where n = fields

### Storage Impact
- **Average test size**: 50-100KB (with questions)
- **40-question test**: ~150KB
- **100 duplicates**: ~15MB
- **Minimal impact**: Tests are relatively small documents

## Best Practices

### 1. Always Check Permissions
```python
# Verify user owns original test
original_test = db.online_tests.find_one({
    "_id": ObjectId(test_id),
    "creator_id": user_id  # ✅ Permission check
})
```

### 2. Preserve All Fields
```python
# ✅ Correct: Use spread operator
studyhub_test = {**original_test, ...}

# ❌ Wrong: Manual field copy (incomplete)
studyhub_test = {
    "title": original_test["title"],
    "questions": original_test["questions"]
    # Missing: 20+ other fields!
}
```

### 3. Clean Up on Delete
```python
# When deleting a StudyHub module
# Also delete all duplicated tests
test_ids = db.studyhub_module_contents.find(
    {"module_id": ObjectId(module_id), "content_type": "test"},
    {"data.test_id": 1}
)

for item in test_ids:
    db.online_tests.delete_one({
        "_id": ObjectId(item["data"]["test_id"]),
        "is_studyhub_copy": True
    })
```

### 4. Prevent Marketplace Duplication
```python
# StudyHub tests should NOT appear in marketplace
marketplace_tests = db.online_tests.find({
    "marketplace_config.is_public": True,
    "is_studyhub_copy": {"$ne": True}  # ✅ Exclude StudyHub
})
```

## Summary

| Aspect | Decision | Reason |
|--------|----------|--------|
| **Collection** | Same (`online_tests`) | 67 endpoints compatible |
| **ID Strategy** | New ID for each copy | Data isolation |
| **Field Copy** | Spread operator (`**original`) | All fields copied |
| **Removed Fields** | `_id`, `marketplace_config`, `migration_metadata` | Clean duplication |
| **New Fields** | `is_studyhub_copy`, `source_test_id`, `studyhub_context` | StudyHub markers |
| **Override Fields** | `title`, timestamps | Customization |

---

**Last Updated**: January 13, 2026  
**Migration Version**: v2.3  
**Field Standardization**: Complete
