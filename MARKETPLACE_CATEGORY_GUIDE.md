# Marketplace Category System Guide

## Tổng Quan

Marketplace sử dụng **category** để phân loại tests, giúp users dễ dàng tìm kiếm và lọc tests theo chủ đề.

**Lưu ý quan trọng:**
- `marketplace_config.category` (string) - Dùng cho hiển thị và filter marketplace
- `test_category` (academic/diagnostic) - Dùng cho logic grading và evaluation (field riêng biệt)

---

## Available Categories

Hiện tại hệ thống hỗ trợ **10 categories**:

| Category | Display Name | Mô tả | Ví dụ |
|----------|-------------|-------|-------|
| `programming` | Programming | Lập trình và code | Python, JavaScript, Algorithms, Data Structures |
| `language` | Language | Ngoại ngữ | English, TOEFL, IELTS, Tiếng Việt |
| `math` | Mathematics | Toán học | Calculus, Algebra, Statistics, Geometry |
| `science` | Science | Khoa học | Physics, Chemistry, Biology |
| `business` | Business | Kinh doanh | Marketing, Finance, Management |
| `technology` | Technology | Công nghệ | IT, Networking, Cybersecurity, Cloud |
| `self_development` | Self-Development | Phát triển bản thân | Personal Growth, Soft Skills, Leadership, Communication |
| `exam_prep` | Exam Preparation | Ôn thi | SAT, GRE, GMAT, Civil Service |
| `certification` | Certification | Chứng chỉ | AWS, Google Cloud, CompTIA, PMP |
| `other` | Other | Khác | Anything else |

**Default category:** `general` (khi không chọn hoặc missing)

---

## Publish Test - Category Selection

### Endpoint 1: `/api/v1/tests/{test_id}/publish` (marketplace_routes.py)

**Cách dùng:**
```bash
POST /api/v1/tests/{test_id}/publish
Content-Type: multipart/form-data

{
  "price_points": 100,
  "description": "...",
  "category": "programming",  # ← Optional, default: "general"
  "tags": "python,algorithms",
  "cover_image": <file>
}
```

**Validation:**
- `category` là **Optional[str]**
- Nếu không cung cấp → tự động set `"general"`
- Nếu cung cấp → không validate danh sách (accept bất kỳ string nào)

**Backend logic:**
```python
# Fallback to "general" if category not provided
final_category = category if category else "general"

marketplace_config = {
    "category": final_category,
    # ... other fields
}
```

---

### Endpoint 2: `/api/v1/tests/{test_id}/marketplace/publish` (test_marketplace_routes.py)

**Cách dùng:**
```bash
POST /api/v1/tests/{test_id}/marketplace/publish
Content-Type: multipart/form-data

{
  "title": "Python Advanced Course",
  "description": "...",
  "price_points": 100,
  "category": "programming",  # ← REQUIRED
  "tags": "python,advanced",
  "difficulty_level": "advanced",
  "cover_image": <file>
}
```

**Validation:**
- `category` là **Required** (Form(...))
- Không có validation list (accept bất kỳ string nào)

**Backend logic:**
```python
marketplace_config = {
    "category": category,  # Direct assignment, no validation
    # ... other fields
}
```

---

## Update Category - Config Modal

### Endpoint: `PATCH /api/v1/tests/{test_id}/marketplace/config`

**Mục đích:**
- Hiển thị category trong Config Modal (My Public Tests)
- Cho phép chỉnh sửa category

**Request:**
```bash
PATCH /api/v1/tests/{test_id}/marketplace/config
Content-Type: multipart/form-data

{
  "category": "programming",  # ← Optional, chỉ update khi cung cấp
  "title": "...",              # Optional
  "description": "...",        # Optional
  "price_points": 100,         # Optional
  # ... other fields
}
```

**Validation:**
- `category` là **Optional[str]**
- **Có validation danh sách** - chỉ accept 10 categories hợp lệ
- Nếu category invalid → HTTP 400 error

**Backend validation:**
```python
if category is not None:
    valid_categories = [
        "programming",
        "language",
        "math",
        "science",
        "business",
        "technology",
        "self_development",
        "exam_prep",
        "certification",
        "other",
    ]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Valid: {', '.join(valid_categories)}",
        )
    update_data["marketplace_config.category"] = category
```

**Auto-fix missing category:**
```python
# Nếu test đã publish nhưng thiếu category → tự động set "general"
if not marketplace_config.get("category"):
    fallback_category = "general"
    mongo_service.db["online_tests"].update_one(
        {"_id": ObjectId(test_id)},
        {"$set": {"marketplace_config.category": fallback_category}}
    )
    logger.info(f"✅ Set missing category to default: {fallback_category}")
```

---

## Frontend Implementation Guide

### 1. Category Selector (Publish Form)

```tsx
// Component: PublishTestModal.tsx
const CATEGORIES = [
  { value: "programming", label: "Programming", icon: "💻" },
  { value: "language", label: "Language", icon: "🌐" },
  { value: "math", label: "Mathematics", icon: "🔢" },
  { value: "science", label: "Science", icon: "🔬" },
  { value: "business", label: "Business", icon: "💼" },
  { value: "technology", label: "Technology", icon: "⚙️" },
  { value: "self_development", label: "Self-Development", icon: "🌱" },
  { value: "exam_prep", label: "Exam Preparation", icon: "📝" },
  { value: "certification", label: "Certification", icon: "🏆" },
  { value: "other", label: "Other", icon: "📚" },
];

<select name="category" defaultValue="other">
  {CATEGORIES.map(cat => (
    <option key={cat.value} value={cat.value}>
      {cat.icon} {cat.label}
    </option>
  ))}
</select>
```

### 2. Display Category (My Public Tests)

```tsx
// Component: MyPublicTestCard.tsx
interface Test {
  test_id: string;
  title: string;
  marketplace_config: {
    category: string;  // ← Always exists (auto-set to "general" if missing)
    price_points: number;
    // ... other fields
  };
}

const getCategoryLabel = (category: string) => {
  const labels = {
    programming: "💻 Programming",
    language: "🌐 Language",
    math: "🔢 Mathematics",
    science: "🔬 Science",
    business: "💼 Business",
    technology: "⚙️ Technology",
    self_development: "🌱 Self-Development",
    exam_prep: "📝 Exam Prep",
    certification: "🏆 Certification",
    other: "📚 Other",
    general: "📂 General",  // Fallback
  };
  return labels[category] || labels.general;
};

<div className="category-badge">
  {getCategoryLabel(test.marketplace_config.category)}
</div>
```

### 3. Update Category (Config Modal)

```tsx
// Component: UpdateMarketplaceConfigModal.tsx
const [selectedCategory, setSelectedCategory] = useState(
  test.marketplace_config.category || "other"
);

const handleUpdate = async () => {
  const formData = new FormData();
  formData.append("category", selectedCategory);
  // ... other fields

  const response = await fetch(
    `/api/v1/tests/${testId}/marketplace/config`,
    {
      method: "PATCH",
      body: formData,
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    const error = await response.json();
    // Handle validation error (invalid category)
    alert(error.detail);
  }
};

<select
  value={selectedCategory}
  onChange={(e) => setSelectedCategory(e.target.value)}
>
  {CATEGORIES.map(cat => (
    <option key={cat.value} value={cat.value}>
      {cat.icon} {cat.label}
    </option>
  ))}
</select>
```

### 4. Filter by Category (Browse Marketplace)

```tsx
// Component: MarketplaceFilters.tsx
const [selectedCategory, setSelectedCategory] = useState<string>("");

useEffect(() => {
  const params = new URLSearchParams({
    page: "1",
    page_size: "20",
  });

  if (selectedCategory) {
    params.append("category", selectedCategory);
  }

  fetch(`/api/v1/marketplace/tests?${params}`)
    .then(res => res.json())
    .then(data => setTests(data.data.tests));
}, [selectedCategory]);

<select
  value={selectedCategory}
  onChange={(e) => setSelectedCategory(e.target.value)}
>
  <option value="">All Categories</option>
  {CATEGORIES.map(cat => (
    <option key={cat.value} value={cat.value}>
      {cat.icon} {cat.label}
    </option>
  ))}
</select>
```

---

## API Response Examples

### GET Test Detail (includes category)

```json
{
  "test_id": "674d3f8a1234567890abcdef",
  "title": "Python Advanced Course",
  "marketplace_config": {
    "category": "programming",  // ✅ Always present
    "price_points": 100,
    "description": "...",
    "tags": ["python", "advanced"],
    "is_public": true
  }
}
```

### Browse Marketplace (filtered by category)

```bash
GET /api/v1/marketplace/tests?category=programming&page=1
```

```json
{
  "success": true,
  "data": {
    "tests": [
      {
        "test_id": "...",
        "title": "Python Advanced Course",
        "category": "programming",  // ✅ Included in response
        "price_points": 100,
        "total_purchases": 50
      }
    ],
    "pagination": {
      "page": 1,
      "total_pages": 5
    }
  }
}
```

---

## Database Structure

### Field trong MongoDB

```javascript
{
  "_id": ObjectId("..."),
  "title": "Python Advanced Course",
  "test_category": "academic",  // ← For grading logic (academic/diagnostic)
  "marketplace_config": {
    "is_public": true,
    "category": "programming",  // ← For marketplace display/filter
    "price_points": 100,
    "tags": ["python", "advanced"],
    // ... other fields
  }
}
```

**Quan trọng:**
- `test_category` (root level) ≠ `marketplace_config.category`
- Chúng phục vụ 2 mục đích khác nhau
- Filter marketplace dùng `marketplace_config.category`

---

## Validation Rules

### Publish (No Validation)
- Accept bất kỳ string nào
- Default: `"general"`

### Update (Strict Validation)
- Chỉ accept 10 categories hợp lệ
- Reject nếu không nằm trong danh sách
- Error message: `"Invalid category. Valid: programming, language, ..."`

### Auto-Fix
- Khi update config mà thiếu category → tự động set `"general"`
- Log: `✅ Set missing category to default: general`

---

## Testing Checklist

### Publish Test
- [ ] Publish test với category hợp lệ
- [ ] Publish test không có category (should default to "general")
- [ ] Verify category được lưu đúng vào `marketplace_config.category`

### Browse & Filter
- [ ] Filter by single category (programming, language, etc.)
- [ ] Filter case-insensitive (`category=Programming` works)
- [ ] Verify category hiển thị đúng trong response

### Update Config Modal
- [ ] Hiển thị category hiện tại trong dropdown
- [ ] Update category thành công với valid value
- [ ] Update category thất bại với invalid value (HTTP 400)
- [ ] Verify auto-fix cho tests thiếu category

### Edge Cases
- [ ] Test published cũ thiếu category (should auto-fix to "general")
- [ ] Category với whitespace hoặc special chars
- [ ] Empty category (should use "general")

---

## Summary

**✅ Categories hiện tại:** 10 categories (programming, language, math, science, business, technology, self_development, exam_prep, certification, other)

**✅ Default category:** `"general"` (khi missing hoặc not provided)

**✅ Publish endpoints:**
- `/api/v1/tests/{test_id}/publish` - category Optional, no validation
- `/api/v1/tests/{test_id}/marketplace/publish` - category Required, no validation

**✅ Update endpoint:**
- `PATCH /api/v1/tests/{test_id}/marketplace/config` - category Optional, **strict validation**

**✅ Frontend tasks:**
- Dropdown selector với 10 categories
- Display category badge trong test cards
- Update category trong Config Modal
- Filter tests by category trong Browse

**✅ Auto-fix:**
- Tests thiếu category sẽ tự động được set `"general"` khi update config
