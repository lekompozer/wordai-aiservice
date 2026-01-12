# Collections Usage Analysis: simple_files vs user_files

**Date:** January 12, 2026
**Status:** INCONSISTENT - Need migration to unify

## Overview

Hệ thống đang dùng **2 collections** để lưu file metadata:
- `simple_files` - NEW standard (9 usages)
- `user_files` - OLD pattern (78 usages)

**Vấn đề:** Không nhất quán, gây lỗi khi rename/delete split files.

---

## Collection Structures

### simple_files (NEW Standard)
```javascript
{
  file_id: "file_abc123",
  user_id: "uid_xxx",
  filename: "20260112_143000_document.pdf",      // Timestamp-prefixed
  original_name: "document.pdf",
  file_type: "application/pdf",
  file_size: 1024000,
  folder_id: "folder_xxx" or null,              // null = root
  created_at: ISODate("2026-01-12T14:30:00Z"),
  updated_at: ISODate("2026-01-12T14:30:00Z"),

  // R2 path pattern: files/{user_id}/{folder_id}/{file_id}/{filename}
}
```

**R2 Storage Pattern:**
```
files/{user_id}/root/{file_id}/20260112_143000_document.pdf
files/{user_id}/folder_abc/{file_id}/20260112_143000_document.pdf
```

### user_files (OLD Pattern)
```javascript
{
  file_id: "file_abc123",
  user_id: "uid_xxx",
  filename: "document.pdf",
  original_name: "document.pdf",
  file_type: ".pdf",
  file_size: 1024000,
  r2_key: "uploads/uid_xxx/file_abc123.pdf",    // OLD pattern
  file_url: "r2://wordai/uploads/...",
  is_deleted: false,
  deleted_at: null,
  uploaded_at: ISODate("..."),
  updated_at: ISODate("..."),
  folder_id: null,
}
```

**R2 Storage Pattern (OLD):**
```
uploads/{user_id}/{file_id}.pdf
```

---

## Files Using user_files Collection

### 1. src/api/simple_file_routes.py
**Purpose:** File upload/download/manage API
**Operations:**
- Line 721, 774, 806: `user_manager.list_user_files()` (read)
- Line 875: Comment về user_files collection

**Status:** ✅ Uses UserManager abstraction (good)

### 2. src/api/pdf_document_routes.py
**Purpose:** PDF operations (split, merge, analyze)
**Operations:**

**READ from user_files:**
- Line 205: Get file for split operation
- Line 611, 617: Get file for import from file_id
- Line 942: Get file for audio extraction
- Line 1129: Get file for merge PDFs

**WRITE to simple_files (NEW):**
- Line 338: Insert split part (auto mode)
- Line 445: Insert split part (manual mode)

**UPDATE:**
- Line 487: Update in simple_files (try first)
- Line 499: Fallback to user_files (backward compat)

**DELETE:**
- Line 525: Delete from user_files (cleanup)

**Status:** ⚠️ MIXED - Reading user_files, writing simple_files

### 3. src/services/user_manager.py
**Purpose:** Core file management service
**Operations:**
- Line 26: Initialize `self.user_files` collection
- Line 64: List indexes
- Line 113, 119, 125: Create indexes
- Line 846, 852: Get file
- Line 910: Insert file
- Line 943: Update file (mark deleted)
- Line 1008, 1021, 1028: List files
- Line 1062: Update metadata
- Line 1103: Move file to folder
- Line 1163: List deleted files
- Line 1281, 1285: Get file for delete
- Line 1311: Hard delete file
- Line 1445, 1470: Count files
- Line 1664, 1686: Get statistics
- Line 1767, 1773: Count by folder

**Status:** ❌ ONLY user_files - Core service NOT updated

### 4. src/services/book_chapter_manager.py
**Purpose:** Book/chapter file handling
**Operations:**
- Line 1513: Find audio file
- Line 1616: Update audio file metadata

**Status:** ❌ ONLY user_files

### 5. src/services/share_manager.py
**Purpose:** File sharing
**Operations:**
- Line 37: Initialize user_files collection
- Line 115: Get file for sharing
- Line 321: Get file for share link

**Status:** ❌ ONLY user_files

### 6. src/api/gemini_slide_parser_routes.py
**Purpose:** Parse slides from uploaded files
**References:**
- Line 39: Field description mentions user_files
- Line 244: Comment about user_files
- Line 334: Error message mentions user_files

**Status:** ⚠️ Documentation only

---

## Files Using simple_files Collection

### 1. src/api/pdf_document_routes.py
**Purpose:** Split PDF new standard
**Operations:**
- Line 338: Insert split part (auto mode) ✅ NEW
- Line 445: Insert split part (manual mode) ✅ NEW
- Line 487: Update parent file with child IDs ✅ NEW
- Line 481, 486: Comments about simple_files

**Status:** ✅ NEW standard for split files

---

## Endpoint Analysis

### API Endpoints Using user_files

#### simple_file_routes.py
- `GET /api/simple-files/files` - List files (via UserManager)
- `GET /api/simple-files/folders/{folder_id}/files` - List folder files (via UserManager)
- `GET /api/simple-files/files/{file_id}` - Get file info (tries user_files via UserManager)

#### pdf_document_routes.py
- `POST /api/pdf-documents/split` - Get source file from user_files ❌
- `POST /api/pdf-documents/import-from-file` - Get file from user_files ❌
- `POST /api/pdf-documents/extract-audio-from-file` - Get file from user_files ❌
- `POST /api/pdf-documents/merge-pdfs` - Get files from user_files ❌

### API Endpoints Using simple_files
- `POST /api/pdf-documents/split` - Save split parts to simple_files ✅

---

## R2 Storage Patterns

### Pattern 1: simple_files (NEW STANDARD)
```
files/{user_id}/{folder_id}/{file_id}/{timestamp_filename}

Examples:
files/uid_xxx/root/file_abc123/20260112_143000_document.pdf
files/uid_xxx/folder_123/file_def456/20260112_143000_report.pdf
```

**Search Pattern in simple_file_routes.py:**
```python
prefix = f"files/{user_id}/"
# Then filter: if f"/{file_id}/" in key or f"/{file_id}_" in key
```

### Pattern 2: user_files (OLD)
```
uploads/{user_id}/{file_id}.pdf

Examples:
uploads/uid_xxx/file_abc123.pdf
uploads/uid_xxx/file_1da6ba240601_part1_1768224166.pdf
```

**Problem:** simple_file_routes endpoints CANNOT find these files!

---

## Issues Summary

### Critical Issues

1. **Split PDFs Not Rename-able**
   - Split files NOW save to simple_files (NEW)
   - OLD split files in user_files (cannot rename)
   - Endpoint searches `files/` prefix only

2. **UserManager Only Uses user_files**
   - Core service: `src/services/user_manager.py`
   - ALL file operations: list, get, update, delete
   - Does NOT read simple_files

3. **Dual Collection Confusion**
   - Upload → user_files (via UserManager)
   - Split → simple_files (direct insert)
   - List files → user_files only
   - Result: Split files invisible in file list!

4. **R2 Path Inconsistency**
   - simple_files: `files/{user_id}/{folder}/{file_id}/{filename}`
   - user_files: `uploads/{user_id}/{file_id}.pdf`
   - Search endpoints fail cross-pattern

### Data Inconsistency

**MongoDB Count (Production):**
```bash
db.user_files.countDocuments({})        # OLD data
db.simple_files.countDocuments({})      # NEW data (split files only)
```

**Example Issue:**
```
User uploads file → user_files
User splits file → simple_files (NEW)
User lists files → Only sees original (user_files)
User tries rename split → 404 Not Found (searches files/ prefix)
```

---

## Migration Strategy

### Phase 1: URGENT - Fix Current Code

1. **Update UserManager to read BOTH collections**
   ```python
   # In list_user_files():
   files_from_user_files = self.user_files.find(query)
   files_from_simple_files = self.simple_files.find(query)
   return merge_and_deduplicate(files_from_user_files, files_from_simple_files)
   ```

2. **Update simple_file_routes search to check BOTH paths**
   ```python
   # Try files/ prefix first (simple_files)
   prefix1 = f"files/{user_id}/"
   # Fallback to uploads/ prefix (user_files)
   prefix2 = f"uploads/{user_id}/"
   ```

3. **Fix pdf_document_routes to read from BOTH**
   ```python
   # Try simple_files first
   file_doc = db.simple_files.find_one({"file_id": file_id})
   if not file_doc:
       # Fallback to user_files
       file_doc = db.user_files.find_one({"file_id": file_id})
   ```

### Phase 2: Data Migration

1. **Migrate user_files → simple_files**
   ```python
   # For each file in user_files:
   # 1. Copy to R2 with new pattern (files/{user_id}/root/{file_id}/{filename})
   # 2. Insert to simple_files with new schema
   # 3. Keep old record for rollback
   ```

2. **Update R2 Storage**
   - Copy `uploads/` files → `files/` structure
   - Preserve old files for rollback
   - Update metadata

### Phase 3: Cleanup (After 30 days)

1. Mark user_files as deprecated
2. Delete old R2 uploads/ files
3. Drop user_files collection

---

## Recommended Actions (PRIORITY ORDER)

### 🔥 HIGH PRIORITY (Fix Today)

1. **Fix UserManager to read BOTH collections**
   - File: `src/services/user_manager.py`
   - Method: `list_user_files()`, `get_file()`, `update_file()`, `delete_file()`
   - Add simple_files queries with fallback

2. **Fix simple_file_routes R2 search**
   - File: `src/api/simple_file_routes.py`
   - Methods: `update_file()`, `delete_file()`, `download_file()`
   - Search BOTH `files/` and `uploads/` prefixes

3. **Fix pdf_document_routes file reads**
   - File: `src/api/pdf_document_routes.py`
   - Lines: 205, 611, 617, 942, 1129
   - Try simple_files first, fallback to user_files

### ⚠️ MEDIUM PRIORITY (This Week)

4. **Add collection field to file metadata**
   ```python
   {
       "_source_collection": "simple_files",  # or "user_files"
       # ... rest of fields
   }
   ```

5. **Create migration script**
   - Script: `migrate_user_files_to_simple_files.py`
   - Test on staging first

### 📊 LOW PRIORITY (Next Sprint)

6. **Update documentation**
7. **Add monitoring for dual-collection queries**
8. **Plan deprecation timeline**

---

## Testing Checklist

- [ ] Upload regular file → Appears in list
- [ ] Upload → Rename → Works
- [ ] Upload → Delete → Works
- [ ] Upload → Split → Parts appear in list
- [ ] Split parts → Rename → Works
- [ ] Split parts → Delete → Works
- [ ] OLD user_files data → Still accessible
- [ ] NEW simple_files data → Accessible
- [ ] Migration script → No data loss

---

## Files Requiring Updates

### CRITICAL (Must Fix)
- ✅ `src/api/pdf_document_routes.py` - Split already uses simple_files
- ❌ `src/services/user_manager.py` - Add simple_files support
- ❌ `src/api/simple_file_routes.py` - Search both R2 patterns

### IMPORTANT (Should Fix)
- ❌ `src/services/share_manager.py` - Read both collections
- ❌ `src/services/book_chapter_manager.py` - Read both collections

### OPTIONAL (Nice to Have)
- ℹ️ `src/api/gemini_slide_parser_routes.py` - Update docs

---

## Conclusion

**Current State:** BROKEN for split files
**Root Cause:** Dual collection system without unified access layer
**Fix Required:** Update ALL file readers to check BOTH collections
**Timeline:** URGENT (production users affected)

**Next Step:** Start with UserManager fix (highest impact)
