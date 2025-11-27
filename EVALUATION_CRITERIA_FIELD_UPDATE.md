# Evaluation Criteria Field - Complete API Update

**Date:** 2025-11-11
**Status:** ✅ Completed
**Cost:** AI Evaluation = 1 point per evaluation

---

## Overview

Added `evaluation_criteria` field to all relevant GET and PATCH endpoints for Online Test Marketplace. This ensures test creators can set, view, and update AI evaluation criteria, and users can see the criteria before taking paid tests.

---

## Changes Summary

### 1. Backend API Updates

#### ✅ GET `/{test_id}/marketplace/details`
**File:** `src/api/online_test_routes.py` (Lines ~4930)

**Change:** Added `evaluation_criteria` to response
```python
# AI Evaluation
"evaluation_criteria": marketplace_config.get("evaluation_criteria"),
```

**Purpose:** Users can see AI evaluation criteria before purchasing/taking test

---

#### ✅ GET `/me/tests`
**File:** `src/api/online_test_routes.py` (Lines ~2350-2390)

**Change:** Added marketplace info including `evaluation_criteria` for published tests
```python
# Add marketplace info if published
if is_public:
    test_info["is_public"] = True
    test_info["marketplace"] = {
        "price_points": marketplace_config.get("price_points", 0),
        "category": marketplace_config.get("category"),
        "difficulty_level": marketplace_config.get("difficulty_level"),
        "total_participants": marketplace_config.get("total_participants", 0),
        "average_rating": marketplace_config.get("average_rating", 0.0),
        "evaluation_criteria": marketplace_config.get("evaluation_criteria"),
    }
else:
    test_info["is_public"] = False
```

**Purpose:** Test creators can see their evaluation criteria in the test list

---

#### ✅ PATCH `/{test_id}/config`
**File:** `src/api/online_test_routes.py`

**Change 1:** Added field to UpdateTestConfigRequest model (Lines ~2814-2842)
```python
evaluation_criteria: Optional[str] = Field(
    None,
    description="AI evaluation criteria for test results (max 5000 chars)",
    max_length=5000,
)
```

**Change 2:** Added logic to update marketplace_config (Lines ~2980+)
```python
if request.evaluation_criteria is not None:
    # Update in marketplace_config if test is published
    marketplace_config = test_doc.get("marketplace_config", {})
    if marketplace_config.get("is_public", False):
        update_data["marketplace_config.evaluation_criteria"] = request.evaluation_criteria
        logger.info(f"📝 Updating evaluation_criteria for published test {test_id}")
```

**Purpose:** Test creators can update evaluation criteria through general config endpoint

---

### 2. Documentation Updates

#### ✅ GET `/api/v1/marketplace/tests/{test_id}`
**File:** `docs/ONLINE_TEST_MARKETPLACE_API_PHASE5.md` (Lines ~850)

**Added to Response Example:**
```json
"evaluation_criteria": "Đánh giá dựa trên:\n- Độ chính xác của các khái niệm Python\n- Khả năng áp dụng kiến thức vào bài tập thực tế\n- Hiểu biết về OOP và error handling\n- Tốc độ làm bài và quản lý thời gian",
```

---

#### ✅ GET `/api/v1/marketplace/me/tests`
**File:** `docs/ONLINE_TEST_MARKETPLACE_API_PHASE5.md` (Lines ~1210)

**Added to Response Example:**
```json
"evaluation_criteria": "Đánh giá dựa trên độ chính xác, hiểu biết về Python OOP, và khả năng áp dụng vào bài tập thực tế.",
```

---

#### ✅ PATCH `/api/v1/tests/{test_id}/marketplace/config`
**File:** `docs/ONLINE_TEST_MARKETPLACE_API_PHASE5.md` (Lines ~475)

**Added to Form Data:**
```
evaluation_criteria: string - AI evaluation criteria (max 5000 chars)
```

**Added to Response Example:**
```json
"evaluation_criteria": "Đánh giá dựa trên độ chính xác, hiểu biết về Python, và khả năng áp dụng vào thực tế."
```

---

#### ✅ NEW: PATCH `/api/v1/tests/{test_id}/config`
**File:** `docs/ONLINE_TEST_MARKETPLACE_API_PHASE5.md` (Section 3B - NEW)

**Complete New Section Added:**
- Endpoint documentation for general config update
- Request body with evaluation_criteria field
- Response example
- Business rules (only updates marketplace_config if published)
- Error responses

---

## API Endpoints Summary

| Endpoint | Method | evaluation_criteria Support | Status |
|----------|--------|----------------------------|---------|
| `/tests/{test_id}/marketplace/publish` | POST | ✅ Create | Already had it |
| `/tests/{test_id}/marketplace/config` | PATCH | ✅ Update | Already had it |
| `/tests/{test_id}/marketplace/details` | GET | ✅ View | ✅ NEW |
| `/tests/me/tests` | GET | ✅ View in list | ✅ NEW |
| `/tests/{test_id}/config` | PATCH | ✅ Update | ✅ NEW |
| `/tests/submissions/evaluate` | POST | Uses criteria | Already works |

---

## Testing Checklist

### Backend Testing
- [ ] Verify GET marketplace details returns evaluation_criteria
- [ ] Verify GET my tests includes evaluation_criteria for published tests
- [ ] Verify GET my tests excludes evaluation_criteria for unpublished tests
- [ ] Verify PATCH config can update evaluation_criteria (published tests only)
- [ ] Verify PATCH config ignores evaluation_criteria for unpublished tests
- [ ] Verify max length validation (5000 chars)
- [ ] Verify evaluation still works with custom criteria

### Frontend Integration
- [ ] Display evaluation_criteria on test details page (before purchase)
- [ ] Display evaluation_criteria in "My Tests" list for published tests
- [ ] Add evaluation_criteria input field in test config form
- [ ] Show warning that evaluation_criteria only applies to published tests
- [ ] Test updating evaluation_criteria through config endpoint

---

## Key Business Rules

1. **evaluation_criteria** field is optional (max 5000 characters)
2. Only applies to **published marketplace tests** (is_public = true)
3. Can be set during:
   - Initial publish (POST marketplace/publish)
   - Marketplace config update (PATCH marketplace/config)
   - General config update (PATCH config) - only if published
4. Visible in:
   - Public test details (before purchase)
   - Creator's test list (for published tests)
   - Test evaluation API (used by AI)
5. Cost: **1 point** per AI evaluation (updated from FREE)

---

## Related Files

### Backend
- `src/api/online_test_routes.py` - Main API routes
- `src/api/test_evaluation_routes.py` - AI evaluation endpoint
- `src/services/gemini_test_evaluation_service.py` - Gemini service
- `src/models/test_evaluation_models.py` - Evaluation models

### Documentation
- `docs/ONLINE_TEST_MARKETPLACE_API_PHASE5.md` - Complete API documentation
- `EVALUATION_CRITERIA_FIELD_UPDATE.md` - This file

---

## Deployment Notes

1. No database migration needed (field already exists in marketplace_config)
2. No breaking changes (field is optional)
3. Existing tests without evaluation_criteria will return null
4. Frontend can handle null values gracefully

---

## Next Steps

1. Test all endpoints in Postman/Bruno
2. Update frontend to display evaluation_criteria
3. Add evaluation_criteria input in test config UI
4. Update user documentation
5. Deploy to staging for QA testing

---

**Completed By:** GitHub Copilot
**Review Status:** ✅ Ready for Testing
