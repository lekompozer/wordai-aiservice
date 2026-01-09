# Phase 3: Migration & Cleanup - Deprecated Code Removal

## Overview

After migrating all `document` mode chapters to `inline` mode, this document outlines deprecated code that can be safely removed.

## Migration Status

✅ **Phase 1**: PDF Pages Support - Complete
✅ **Phase 2**: Image Pages & Manga - Complete
🔄 **Phase 3**: Migration & Cleanup - In Progress

## Files to Remove

### 1. Document Mode Code in book_chapter_manager.py

**Location**: `src/services/book_chapter_manager.py`

**Code to Remove**:
```python
# In get_chapter_with_content() method
# Remove this elif block:
elif content_mode == "document":
    document_id = chapter.get("document_id")
    if document_id:
        document = self.db.documents.find_one({"_id": document_id})
        if document:
            chapter["content"] = document.get("content", "")
            chapter["content_type"] = document.get("content_type", "html")
```

**Replace with**:
```python
# Only keep: inline, pdf_pages, image_pages
# Document mode no longer supported
else:
    # Fallback for inline mode
    pass  # Already has content in chapter doc
```

### 2. Document Reference in Models

**Location**: `src/models/book_chapter_models.py`

**Code to Update**:
```python
# BEFORE (deprecated)
class ChapterBase(BaseModel):
    content_mode: Literal["inline", "document", "pdf_pages", "image_pages"] = "inline"
    document_id: Optional[str] = None  # DEPRECATED

# AFTER (clean)
class ChapterBase(BaseModel):
    content_mode: Literal["inline", "pdf_pages", "image_pages"] = "inline"
    # document_id removed
```

### 3. Document Manager Integration

**Location**: `src/services/book_chapter_manager.py`

**Code to Remove**:
```python
# Remove this import if only used for document mode
from src.services.document_manager import DocumentManager

# Remove this initialization
self.document_manager = DocumentManager(db)
```

### 4. API Endpoints for Document Mode

**Location**: `src/api/book_chapter_routes.py`

**Code to Remove**:
- Any endpoints specifically for document mode chapters
- Document reference parameters in ChapterCreate
- Document mode validation

## Database Cleanup

### 1. Remove document_id Field

Run after verification:

```javascript
// MongoDB command
db.book_chapters.updateMany(
  { migrated_from_document: true },
  { $unset: { document_id: "" } }
)
```

### 2. Optional: Archive Documents Collection

If `documents` collection is no longer used:

```bash
# Export for backup
mongodump --db ai_service_db --collection documents --out /backup

# Then drop collection (CAREFUL!)
# db.documents.drop()
```

### 3. Indexes Cleanup

Remove indexes on deprecated fields:

```javascript
// List indexes
db.book_chapters.getIndexes()

// Drop document_id index if exists
db.book_chapters.dropIndex("document_id_1")
```

## Migration Script Usage

### 1. Dry Run (Recommended First)

```bash
python migrate_document_to_inline.py --dry-run
```

Output:
```
🔍 Searching for 'document' mode chapters...
✅ Found 150 document mode chapters
📦 Processing batch 1/2
🔧 [DRY RUN] Would migrate chapter abc123
...
📊 Migration Summary:
   Total chapters: 150
   ✅ Migrated: 0 (dry run)
   ⚠️ Skipped: 0
   ❌ Errors: 0
```

### 2. Live Migration

```bash
# Migrate all
python migrate_document_to_inline.py

# Migrate in smaller batches
python migrate_document_to_inline.py --batch-size 50
```

### 3. Verify Results

```bash
python migrate_document_to_inline.py --verify
```

Output:
```
🔍 Verifying migration...
📊 Verification Results:
   Remaining 'document' mode: 0
   Total 'inline' mode: 1523
   Migrated chapters: 150
✅ All document chapters migrated successfully!
```

## Rollback Plan

If issues occur during migration:

### 1. Identify Affected Chapters

```javascript
db.book_chapters.find({
  migrated_from_document: true,
  migrated_at: { $gte: ISODate("2026-01-09T00:00:00Z") }
})
```

### 2. Restore Document References

```javascript
// Restore document_id and revert mode
db.book_chapters.updateMany(
  {
    migrated_from_document: true,
    // Add conditions to target specific migration batch
  },
  {
    $set: {
      content_mode: "document",
      // Need to restore document_id from backup
    },
    $unset: {
      content: "",
      migrated_from_document: "",
      migrated_at: ""
    }
  }
)
```

### 3. Restore from Backup

```bash
# If you have MongoDB backup
mongorestore --db ai_service_db --collection book_chapters /backup/book_chapters.bson
```

## Testing Checklist

Before removing deprecated code:

- [ ] Run migration in staging environment
- [ ] Verify all chapters load correctly
- [ ] Test content editing works
- [ ] Check API responses match expected format
- [ ] Verify book navigation/tree structure
- [ ] Test chapter creation (should only allow inline/pdf_pages/image_pages)
- [ ] Monitor error logs for 24 hours
- [ ] Get user feedback on migrated content

## Timeline

**Week 1**: 
- Day 1-2: Dry run migration in staging
- Day 3-4: Live migration in staging
- Day 5: Verification & testing

**Week 2**:
- Day 1: Production dry run
- Day 2: Production migration (off-peak hours)
- Day 3-4: Monitor & verify
- Day 5: Code cleanup (if all good)

## Success Criteria

Migration is successful when:

1. ✅ All document chapters converted to inline
2. ✅ Zero `content_mode: "document"` in database
3. ✅ All migrated chapters render correctly
4. ✅ No increase in error rates
5. ✅ User reports no issues
6. ✅ Verification script shows 100% success

## Contact

Questions? Check:
- `/SYSTEM_REFERENCE.md` - System documentation
- `/BOOK_CHAPTER_PDF_ARCHITECTURE.md` - Architecture details
- Migration logs in `/logs/migration/`

---

**Last Updated**: January 9, 2026
**Status**: Phase 3 - Migration script ready, awaiting execution
