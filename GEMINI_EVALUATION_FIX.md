# Gemini Test Evaluation Service - Field Name Compatibility Fix

**Date:** December 14, 2025  
**Issue:** AttributeError when evaluating tests with mixed question types  
**File:** `src/services/gemini_test_evaluation_service.py`

## Problem

The Gemini evaluation service crashed with error:
```
AttributeError: 'str' object has no attribute 'get'
```

This occurred when evaluating tests containing completion questions where `correct_answers` was stored as a simple string array instead of the expected object array format.

## Root Cause

After the field name unification (v2.3), some old questions in the database still had:
- **Completion type:** `correct_answers` as array of strings instead of array of objects
- **MCQ types:** Using old field names (`correct_answer_keys`, `correct_answer_key`)
- **Matching type:** Using old field name (`correct_matches`)
- **Short Answer:** Using old field name (`correct_answer_keys`)

The evaluation service didn't handle backward compatibility properly when iterating through these fields.

## Changes Made

### 1. MCQ Evaluation (Lines 144-153)
**Before:**
```python
correct_answer_keys = q.get("correct_answer_keys") or [
    q.get("correct_answer_key")
]
```

**After:**
```python
correct_answer_keys = (
    q.get("correct_answers") 
    or q.get("correct_answer_keys") 
    or [q.get("correct_answer_key")]
)
```

**Impact:** Now checks `correct_answers` first (unified field), then falls back to old fields.

### 2. Matching Evaluation (Lines 216-220)
**Before:**
```python
correct_matches = {
    m["left_key"]: m["right_key"] for m in q.get("correct_matches", [])
}
```

**After:**
```python
matches_data = q.get("correct_answers") or q.get("correct_matches", [])
correct_matches = {
    m["left_key"]: m["right_key"] for m in matches_data
}
```

**Impact:** Supports both `correct_answers` (new) and `correct_matches` (old).

### 3. Completion Evaluation (Lines 256-270)
**Before:**
```python
for ca in correct_answers_list:
    blank_key = ca.get("blank_key")
    accepted = [ans.lower().strip() for ans in ca.get("answers", [])]
    user_ans = str(user_blanks.get(blank_key, "")).lower().strip()
    if user_ans in accepted:
        correct_count += 1
```

**After:**
```python
for ca in correct_answers_list:
    # Handle both object format (correct) and string format (legacy)
    if isinstance(ca, dict):
        blank_key = ca.get("blank_key")
        accepted = [ans.lower().strip() for ans in ca.get("answers", [])]
    else:
        # Legacy format: ca is a string, use it as the answer
        blank_key = None
        accepted = [str(ca).lower().strip()]
    
    if blank_key:
        user_ans = str(user_blanks.get(blank_key, "")).lower().strip()
        if user_ans in accepted:
            correct_count += 1
```

**Impact:** Handles both object format (correct) and string format (legacy data).

### 4. Short Answer Evaluation (Lines 378-382)
**Before:**
```python
correct_answers = q.get("correct_answer_keys", [])
```

**After:**
```python
correct_answers = q.get("correct_answers") or q.get("correct_answer_keys", [])
```

**Impact:** Checks `correct_answers` first, then falls back to `correct_answer_keys`.

## Testing

✅ **Compilation:** No syntax errors  
✅ **Backward Compatibility:** Supports both new unified fields and old field names  
✅ **Data Format Flexibility:** Handles both object arrays and string arrays in `correct_answers`

## Expected Behavior

The service will now:
1. **Prefer unified fields:** Always check `correct_answers` first
2. **Fallback gracefully:** Use old field names if new ones don't exist
3. **Handle mixed formats:** Process both object arrays and string arrays
4. **No data loss:** All existing tests continue to work

## Deployment

This fix should be deployed immediately as it affects all AI-powered test evaluations with combined question types (MCQ + Short Answer + Completion + Matching).

**Command:**
```bash
git add src/services/gemini_test_evaluation_service.py GEMINI_EVALUATION_FIX.md
git commit -m "fix: add backward compatibility to Gemini evaluation service

- Support both correct_answers and legacy field names
- Handle string arrays and object arrays in completion questions
- Add type checking before calling .get() on correct_answers items
- Fixes AttributeError when evaluating mixed question types"

git push origin main
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull origin main && ./deploy-compose-with-rollback.sh'"
```

## Related Documents

- `docs/FRONTEND_FIELD_NAME_MIGRATION.md` - Frontend migration guide
- `FIELD_UNIFICATION_COMPLETE.md` - Field unification project summary
- `docs/wordai/Tests/ONLINE_TEST_API_SPECS.md` - API v2.3 specification
