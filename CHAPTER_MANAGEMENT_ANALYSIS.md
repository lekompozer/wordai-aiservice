# 📊 Chapter Management API - Analysis & Summary

## 🎯 Yêu Cầu Từ Frontend

1. **Tạo Chapter Mới:**
   - Tạo root chapter (level 0)
   - Tạo child chapter từ context menu (right-click)
   - Support tối đa 3 levels (0, 1, 2)

2. **Hiển Thị Tree Structure:**
   - Danh sách dạng tree hierarchy
   - Bỏ text "Có nội dung" dưới title
   - Hiển thị nested chapters

3. **Context Menu Actions:**
   - Add child chapter (khi click chuột phải vào chapter)

---

## ✅ API Endpoints Hiện Tại

### 1. **POST /api/v1/books/{book_id}/chapters** - Tạo Chapter Mới

**Status:** ✅ **FULLY SUPPORTED**

**Request Model:**
```json
{
  "title": "Chapter Title",           // REQUIRED
  "slug": "chapter-slug",             // OPTIONAL - auto-generated
  "document_id": "doc_xxx",           // OPTIONAL - auto-created
  "parent_id": "chapter_xxx",         // OPTIONAL - null = root, có giá trị = child
  "order_index": 0,                   // OPTIONAL - default 0
  "order": 0,                         // OPTIONAL - alias for order_index
  "is_published": true                // OPTIONAL - default true
}
```

**Features:**
- ✅ **Auto-generate slug** từ title (Vietnamese-safe)
- ✅ **Auto-create document** nếu không provide
- ✅ **Support parent_id** - tạo child chapter
- ✅ **Validate max depth** - max 3 levels (0, 1, 2)
- ✅ **Verify parent exists** và thuộc cùng book
- ✅ **Unique slug** per book

**Response Model:**
```json
{
  "chapter_id": "chapter_xxx",
  "book_id": "book_xxx",
  "title": "Chapter Title",
  "slug": "chapter-slug",
  "document_id": "doc_xxx",
  "parent_id": "chapter_parent",      // null nếu root
  "order_index": 0,
  "depth": 0,                         // 0, 1, or 2
  "is_published": true,
  "created_at": "2025-11-16T...",
  "updated_at": "2025-11-16T..."
}
```

**Validation:**
- ✅ Max depth: 3 levels (0, 1, 2)
- ✅ Parent must exist in same book
- ✅ Slug unique within book
- ✅ Owner only

**Frontend Usage:**
```typescript
// Tạo root chapter
POST /api/v1/books/{book_id}/chapters
Body: { title: "My Chapter", order: 0 }

// Tạo child chapter (từ context menu)
POST /api/v1/books/{book_id}/chapters
Body: {
  title: "Sub Chapter",
  parent_id: "chapter_parent_xxx",  // ← Set parent_id
  order: 0
}
```

---

### 2. **GET /api/v1/books/{book_id}/chapters** - Lấy Chapter Tree

**Status:** ✅ **FULLY SUPPORTED**

**Query Parameters:**
```
?include_unpublished=false  // Owner always sees all
```

**Response Structure:**
```json
{
  "book_id": "book_xxx",
  "total_chapters": 5,
  "chapters": [
    {
      "chapter_id": "chapter_1",
      "title": "Chapter 1",
      "slug": "chapter-1",
      "document_id": "doc_xxx",
      "order_index": 0,
      "depth": 0,                    // Level 0 (root)
      "is_published": true,
      "children": [                  // ← Nested children
        {
          "chapter_id": "chapter_1_1",
          "title": "Chapter 1.1",
          "slug": "chapter-1-1",
          "document_id": "doc_yyy",
          "order_index": 0,
          "depth": 1,                // Level 1
          "is_published": true,
          "children": [              // ← Nested children
            {
              "chapter_id": "chapter_1_1_1",
              "title": "Chapter 1.1.1",
              "depth": 2,            // Level 2 (max)
              "children": []         // No more nesting
            }
          ]
        }
      ]
    }
  ]
}
```

**Features:**
- ✅ **Hierarchical tree structure** (recursive nesting)
- ✅ **Max 3 levels** (depth 0, 1, 2)
- ✅ **Sorted by order_index** at each level
- ✅ **No MongoDB ObjectId** (already fixed)
- ✅ **Owner sees unpublished** chapters

**Tree Building Logic:**
```python
# src/services/book_chapter_manager.py
def get_chapter_tree(book_id, include_unpublished):
    # 1. Query all chapters
    chapters = find({"book_id": book_id}, {"_id": 0})

    # 2. Build chapter map with children array
    chapter_map = {ch["chapter_id"]: {...ch, "children": []} }

    # 3. Build tree by linking parent-child
    for chapter in chapters:
        if parent_id is None:
            tree.append(chapter)  # Root level
        else:
            parent["children"].append(chapter)  # Nested

    # 4. Sort recursively by order_index
    return sorted_tree
```

---

## 🎨 Frontend Implementation Guide

### 1. **Hiển Thị Tree Structure**

```typescript
interface ChapterTreeNode {
  chapter_id: string;
  title: string;
  slug: string;
  document_id?: string;
  order_index: number;
  depth: number;
  is_published: boolean;
  children: ChapterTreeNode[];  // ← Recursive
}

// Render component (recursive)
const ChapterTreeItem = ({ chapter, onAddChild }) => {
  return (
    <div className={`chapter-item depth-${chapter.depth}`}>
      {/* Title only - NO "Có nội dung" text */}
      <h4>{chapter.title}</h4>

      {/* Context Menu */}
      <ContextMenu>
        <MenuItem onClick={() => onAddChild(chapter.chapter_id)}>
          Add Child Chapter
        </MenuItem>
      </ContextMenu>

      {/* Recursive children */}
      {chapter.children.map(child => (
        <ChapterTreeItem
          key={child.chapter_id}
          chapter={child}
          onAddChild={onAddChild}
        />
      ))}
    </div>
  );
};
```

### 2. **Tạo Child Chapter từ Context Menu**

```typescript
const handleAddChildChapter = async (parentChapterId: string) => {
  const response = await fetch(
    `/api/v1/books/${bookId}/chapters`,
    {
      method: 'POST',
      body: JSON.stringify({
        title: "New Child Chapter",
        parent_id: parentChapterId,  // ← Set parent
        order: 0
      })
    }
  );

  if (response.ok) {
    // Reload chapter tree
    refreshChapterTree();
  }
};
```

### 3. **Validation: Max Depth**

```typescript
const canAddChild = (chapter: ChapterTreeNode): boolean => {
  // Max depth is 2 (0, 1, 2)
  // So depth 2 cannot have children
  return chapter.depth < 2;
};

// In context menu
<MenuItem
  onClick={() => onAddChild(chapter.chapter_id)}
  disabled={!canAddChild(chapter)}  // ← Disable if depth >= 2
>
  Add Child Chapter
</MenuItem>
```

---

## 📋 Backend Configuration

### Max Depth Settings

```python
# src/services/book_chapter_manager.py
class GuideBookBookChapterManager:
    MAX_DEPTH = 2  # 0, 1, 2 = 3 levels total
```

**Depth Levels:**
- **Level 0** (depth=0): Root chapters
- **Level 1** (depth=1): Sub chapters
- **Level 2** (depth=2): Sub-sub chapters (MAX - no children allowed)

### Depth Calculation

```python
def _calculate_depth(parent_chapter_id: Optional[str]) -> int:
    if parent_chapter_id is None:
        return 0  # Root

    parent = get_chapter(parent_chapter_id)
    return parent["depth"] + 1  # Increment parent depth
```

### Validation in Create Chapter

```python
# Auto-calculate depth from parent
depth = self._calculate_depth(chapter_data.parent_id)

# Validate max depth
if depth > self.MAX_DEPTH:  # > 2
    raise ValueError("Maximum nesting depth (3 levels) exceeded")
```

---

## ✅ Summary: Hỗ Trợ Yêu Cầu Frontend

| Yêu Cầu | Status | API Support | Notes |
|---------|--------|-------------|-------|
| Tạo root chapter | ✅ SUPPORTED | `POST /chapters` với `parent_id=null` | Auto-generates slug & document |
| Tạo child chapter | ✅ SUPPORTED | `POST /chapters` với `parent_id=<parent>` | Validates parent exists & max depth |
| Context menu "Add child" | ✅ SUPPORTED | Frontend implement context menu | Backend đã có API sẵn |
| Max 3 levels | ✅ ENFORCED | `MAX_DEPTH = 2` (0, 1, 2) | Backend validates automatically |
| Hiển thị tree structure | ✅ SUPPORTED | `GET /chapters` returns nested tree | Recursive `children` array |
| Bỏ text "Có nội dung" | ⚠️ FRONTEND | Frontend không render text này | Backend không gửi text này |
| Sort by order_index | ✅ SUPPORTED | Backend sorts recursively | Each level sorted independently |

---

## 🎯 Kết Luận

### ✅ Backend ĐÃ HỖ TRỢ ĐẦY ĐỦ:

1. **Tạo child chapter:**
   - Set `parent_id` trong request body
   - Backend validate parent tồn tại
   - Backend validate max depth (3 levels)
   - Backend tự động calculate depth

2. **Tree structure:**
   - Response trả về recursive tree với `children` array
   - Sorted by `order_index` at each level
   - Include `depth` field để frontend render indentation

3. **Validation:**
   - Max depth = 2 (3 levels: 0, 1, 2)
   - Parent must exist in same book
   - Unique slug per book
   - Owner only

### 📝 Frontend Cần Làm:

1. **Render tree structure:**
   - Recursive component cho `children` array
   - Hiển thị indentation dựa vào `depth`
   - **BỎ text "Có nội dung"** - chỉ show `title`

2. **Context menu:**
   - Add "Add Child Chapter" option
   - Check `depth < 2` để disable nếu max depth
   - Call `POST /chapters` với `parent_id`

3. **UI/UX:**
   - Show nested levels with indentation
   - Drag-drop để reorder (optional)
   - Collapse/expand tree nodes (optional)

---

## 🚀 Example API Calls

### Tạo Root Chapter
```bash
POST /api/v1/books/book_f1fa41574c92/chapters
{
  "title": "Getting Started",
  "order": 0
}
# Response: depth = 0
```

### Tạo Child Chapter (Level 1)
```bash
POST /api/v1/books/book_f1fa41574c92/chapters
{
  "title": "Installation",
  "parent_id": "chapter_root_xxx",
  "order": 0
}
# Response: depth = 1
```

### Tạo Sub-Child Chapter (Level 2 - MAX)
```bash
POST /api/v1/books/book_f1fa41574c92/chapters
{
  "title": "Windows Installation",
  "parent_id": "chapter_child_xxx",
  "order": 0
}
# Response: depth = 2 (MAX)
```

### Tạo Level 3 - ❌ WILL FAIL
```bash
POST /api/v1/books/book_f1fa41574c92/chapters
{
  "title": "Will Fail",
  "parent_id": "chapter_level2_xxx",
  "order": 0
}
# Response: 400 Bad Request - "Maximum nesting depth (3 levels) exceeded"
```

---

## 📌 Action Items

### Backend: ✅ COMPLETED
- [x] Create chapter với parent_id support
- [x] Max depth validation (3 levels)
- [x] Auto-generate slug và document
- [x] Return tree structure with children
- [x] Fix MongoDB ObjectId serialization

### Frontend: ⏳ TODO
- [ ] Implement recursive tree rendering
- [ ] Add context menu "Add Child Chapter"
- [ ] Remove "Có nội dung" text from UI
- [ ] Disable "Add Child" when depth >= 2
- [ ] Add visual indentation for nested levels
- [ ] Test with 3-level deep chapters

---

**Tóm lại:** Backend đã implement đầy đủ tất cả API cần thiết. Frontend chỉ cần:
1. Render tree recursive với `children` array
2. Add context menu để call API với `parent_id`
3. Bỏ text "Có nội dung" trong UI

🎉 **Ready to implement!**
