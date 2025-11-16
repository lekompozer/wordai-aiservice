# 📚 Publish Book to Community - API Specification

## 🎯 Endpoint

```
POST /api/v1/books/{book_id}/publish-community
```

**Authentication:** Required (Bearer Token)

---

## 📋 Request Body Fields

### ✅ **REQUIRED FIELDS**

#### 1. **Author Information**

```typescript
author_id: string  // REQUIRED
```
- **Format:** Must start with `@` (e.g., `@michael`, `@john_doe`)
- **Auto-create:** Nếu author chưa tồn tại → tự động tạo mới
- **Existing:** Nếu author đã tồn tại → verify ownership
- **Example:** `"@michael"`

---

#### 2. **Visibility & Pricing**

```typescript
visibility: "public" | "point_based"  // REQUIRED
```
- **public:** Free book - ai cũng đọc được
- **point_based:** Paid book - cần trả points để đọc

**If visibility = "point_based", cần thêm:**

```typescript
access_config: {  // REQUIRED khi visibility="point_based"
  // Pricing (at least one must be > 0):
  one_time_view_points: number,      // Points for 1 lần xem
  forever_view_points: number,       // Points for xem mãi mãi
  download_pdf_points: number,       // Points to download PDF

  // Enable/disable options (default: true):
  is_one_time_enabled: boolean,      // Show "One-time view" option
  is_forever_enabled: boolean,       // Show "Forever view" option
  is_download_enabled: boolean       // Show "Download PDF" option
}
```

**Example - Free Book:**
```json
{
  "visibility": "public"
}
```

**Example - Paid Book:**
```json
{
  "visibility": "point_based",
  "access_config": {
    "one_time_view_points": 50,
    "forever_view_points": 200,
    "download_pdf_points": 100,
    "is_one_time_enabled": true,
    "is_forever_enabled": true,
    "is_download_enabled": true
  }
}
```

---

#### 3. **Community Metadata**

```typescript
category: string  // REQUIRED
```
- **Description:** Book category for filtering
- **Examples:**
  - `"programming"`
  - `"business"`
  - `"marketing"`
  - `"design"`
  - `"data_science"`
  - `"ai_ml"`
  - `"web_development"`
- **Validation:** Min 1 char, max 100 chars

```typescript
tags: string[]  // REQUIRED
```
- **Description:** Search tags (1-10 tags)
- **Min:** 1 tag
- **Max:** 10 tags
- **Examples:** `["python", "tutorial", "beginner"]`

```typescript
difficulty_level: string  // REQUIRED
```
- **Values:**
  - `"beginner"` - Người mới bắt đầu
  - `"intermediate"` - Trung cấp
  - `"advanced"` - Nâng cao
  - `"expert"` - Chuyên gia

```typescript
short_description: string  // REQUIRED
```
- **Description:** Short summary of the book
- **Min:** 10 chars
- **Max:** 200 chars
- **Example:** `"A comprehensive guide to Python for beginners with hands-on examples"`

---

### 🔧 **OPTIONAL FIELDS**

#### 1. **Author Information (for new author)**

```typescript
author_name?: string  // Optional (auto-generated if not provided)
```
- **When:** Khi tạo author mới (author_id chưa tồn tại)
- **Auto-generate:** Nếu không có, backend sẽ tạo từ:
  1. User's display name
  2. Extract từ email: `user@example.com` → `"user"`
  3. Clean @username: `"@john_doe"` → `"John Doe"`
- **Example:** `"Michael Nguyen"`

```typescript
author_bio?: string  // Optional
```
- **Max:** 500 chars
- **Example:** `"Full-stack developer with 10+ years of experience"`

```typescript
author_avatar_url?: string  // Optional
```
- **Format:** Full URL
- **Example:** `"https://example.com/avatar.jpg"`

---

#### 2. **Book Branding**

```typescript
cover_image_url?: string  // Optional
```
- **Format:** Full URL to cover image
- **Recommended:** 1200x630px (16:9 ratio)
- **Example:** `"https://example.com/cover.jpg"`

---

## 📝 Complete Request Examples

### Example 1: Free Book (Public)

```json
{
  "author_id": "@michael",
  "visibility": "public",
  "category": "programming",
  "tags": ["python", "tutorial", "beginner"],
  "difficulty_level": "beginner",
  "short_description": "Learn Python from scratch with practical examples and exercises"
}
```

### Example 2: Paid Book (Point-based)

```json
{
  "author_id": "@michael",
  "author_name": "Michael Nguyen",
  "author_bio": "Senior Python Developer",
  "author_avatar_url": "https://example.com/avatar.jpg",

  "visibility": "point_based",
  "access_config": {
    "one_time_view_points": 50,
    "forever_view_points": 200,
    "download_pdf_points": 100,
    "is_one_time_enabled": true,
    "is_forever_enabled": true,
    "is_download_enabled": true
  },

  "category": "programming",
  "tags": ["python", "advanced", "async"],
  "difficulty_level": "advanced",
  "short_description": "Master asynchronous programming in Python with real-world projects",
  "cover_image_url": "https://example.com/cover.jpg"
}
```

### Example 3: Minimal Request (All Optional Fields Auto)

```json
{
  "author_id": "@michael",
  "visibility": "public",
  "category": "programming",
  "tags": ["python"],
  "difficulty_level": "beginner",
  "short_description": "A simple Python guide"
}
```

---

## ✅ Response

### Success Response (200 OK)

```json
{
  "book_id": "book_f1fa41574c92",
  "user_id": "user_xxx",
  "title": "Python for Beginners",
  "slug": "python-for-beginners",
  "description": "...",
  "visibility": "public",
  "is_published": true,

  "access_config": {
    "one_time_view_points": 0,
    "forever_view_points": 0,
    "download_pdf_points": 0,
    "is_one_time_enabled": true,
    "is_forever_enabled": true,
    "is_download_enabled": true
  },

  "community_config": {
    "is_public": true,
    "category": "programming",
    "tags": ["python", "tutorial", "beginner"],
    "difficulty_level": "beginner",
    "short_description": "Learn Python from scratch...",
    "cover_image_url": null,
    "total_views": 0,
    "total_downloads": 0,
    "total_purchases": 0,
    "average_rating": 0.0,
    "rating_count": 0,
    "version": "1.0.0",
    "published_at": "2025-11-16T10:30:00Z",
    "author_id": "@michael",
    "author_name": "Michael"
  },

  "created_at": "2025-11-15T08:00:00Z",
  "updated_at": "2025-11-16T10:30:00Z"
}
```

---

## ❌ Error Responses

### 400 Bad Request
```json
{
  "detail": "access_config is required when visibility is point_based"
}
```

### 403 Forbidden
```json
{
  "detail": "You don't own this author profile"
}
```

### 404 Not Found
```json
{
  "detail": "Book not found or you don't have access"
}
```

---

## 🎨 Frontend Form Fields

### **Tab 1: Author Information**

```typescript
interface AuthorFields {
  author_id: string;           // Input: @username (required)
  author_name?: string;        // Input: Display name (optional)
  author_bio?: string;         // Textarea: Bio (optional)
  author_avatar_url?: string;  // File upload or URL (optional)
}
```

**UI:**
```html
<input
  type="text"
  placeholder="@username"
  pattern="@[a-zA-Z0-9_-]+"
  required
/>
<input type="text" placeholder="Display Name (optional)" />
<textarea placeholder="Author bio (optional)" maxlength="500"></textarea>
<input type="url" placeholder="Avatar URL (optional)" />
```

---

### **Tab 2: Visibility & Pricing**

```typescript
interface VisibilityFields {
  visibility: "public" | "point_based";  // Radio buttons (required)

  // Show only if visibility === "point_based":
  access_config?: {
    one_time_view_points: number;      // Number input (min: 0)
    forever_view_points: number;       // Number input (min: 0)
    download_pdf_points: number;       // Number input (min: 0)
    is_one_time_enabled: boolean;      // Checkbox
    is_forever_enabled: boolean;       // Checkbox
    is_download_enabled: boolean;      // Checkbox
  }
}
```

**UI:**
```html
<!-- Visibility -->
<label>
  <input type="radio" name="visibility" value="public" required />
  Free (Public)
</label>
<label>
  <input type="radio" name="visibility" value="point_based" />
  Paid (Point-based)
</label>

<!-- Show only if point_based selected -->
<div v-if="visibility === 'point_based'">
  <input type="number" placeholder="One-time view points" min="0" />
  <input type="number" placeholder="Forever view points" min="0" />
  <input type="number" placeholder="Download PDF points" min="0" />

  <label>
    <input type="checkbox" checked /> Enable one-time view
  </label>
  <label>
    <input type="checkbox" checked /> Enable forever view
  </label>
  <label>
    <input type="checkbox" checked /> Enable PDF download
  </label>
</div>
```

---

### **Tab 3: Book Metadata**

```typescript
interface MetadataFields {
  category: string;              // Dropdown (required)
  tags: string[];                // Tag input (1-10 tags, required)
  difficulty_level: string;      // Dropdown (required)
  short_description: string;     // Textarea (required, 10-200 chars)
  cover_image_url?: string;      // File upload or URL (optional)
}
```

**UI:**
```html
<!-- Category -->
<select required>
  <option value="">Select category...</option>
  <option value="programming">Programming</option>
  <option value="business">Business</option>
  <option value="marketing">Marketing</option>
  <option value="design">Design</option>
  <!-- ... more categories -->
</select>

<!-- Tags -->
<input
  type="text"
  placeholder="Add tags (press Enter)"
  @keypress.enter="addTag"
/>
<div class="tags">
  <span v-for="tag in tags" :key="tag">
    {{ tag }} <button @click="removeTag(tag)">×</button>
  </span>
</div>
<small>{{ tags.length }} / 10 tags (min: 1)</small>

<!-- Difficulty -->
<select required>
  <option value="">Select difficulty...</option>
  <option value="beginner">Beginner</option>
  <option value="intermediate">Intermediate</option>
  <option value="advanced">Advanced</option>
  <option value="expert">Expert</option>
</select>

<!-- Description -->
<textarea
  placeholder="Short description (10-200 characters)"
  minlength="10"
  maxlength="200"
  required
></textarea>
<small>{{ description.length }} / 200</small>

<!-- Cover Image -->
<input type="url" placeholder="Cover image URL (optional)" />
<!-- OR -->
<input type="file" accept="image/*" />
```

---

## 🔄 Frontend Validation

```typescript
interface PublishBookForm {
  // Author (required)
  author_id: string;                    // Must start with @
  author_name?: string;                 // 2-100 chars
  author_bio?: string;                  // Max 500 chars
  author_avatar_url?: string;           // Valid URL

  // Visibility (required)
  visibility: "public" | "point_based"; // Required

  // Pricing (required if point_based)
  access_config?: {
    one_time_view_points: number;       // >= 0
    forever_view_points: number;        // >= 0
    download_pdf_points: number;        // >= 0
    is_one_time_enabled: boolean;       // Default: true
    is_forever_enabled: boolean;        // Default: true
    is_download_enabled: boolean;       // Default: true
  };

  // Metadata (required)
  category: string;                     // Required
  tags: string[];                       // 1-10 items
  difficulty_level: string;             // beginner|intermediate|advanced|expert
  short_description: string;            // 10-200 chars
  cover_image_url?: string;             // Valid URL
}

// Validation function
function validatePublishForm(form: PublishBookForm): string[] {
  const errors: string[] = [];

  // Author ID
  if (!form.author_id) {
    errors.push("Author ID is required");
  } else if (!form.author_id.startsWith("@")) {
    errors.push("Author ID must start with @");
  }

  // Visibility
  if (!form.visibility) {
    errors.push("Visibility is required");
  }

  // Access config (if point_based)
  if (form.visibility === "point_based") {
    if (!form.access_config) {
      errors.push("Access config is required for paid books");
    } else {
      const { one_time_view_points, forever_view_points, download_pdf_points } = form.access_config;
      if (one_time_view_points === 0 && forever_view_points === 0 && download_pdf_points === 0) {
        errors.push("At least one pricing option must be > 0");
      }
    }
  }

  // Category
  if (!form.category) {
    errors.push("Category is required");
  }

  // Tags
  if (!form.tags || form.tags.length === 0) {
    errors.push("At least 1 tag is required");
  } else if (form.tags.length > 10) {
    errors.push("Maximum 10 tags allowed");
  }

  // Difficulty
  if (!form.difficulty_level) {
    errors.push("Difficulty level is required");
  } else if (!["beginner", "intermediate", "advanced", "expert"].includes(form.difficulty_level)) {
    errors.push("Invalid difficulty level");
  }

  // Description
  if (!form.short_description) {
    errors.push("Short description is required");
  } else if (form.short_description.length < 10) {
    errors.push("Description must be at least 10 characters");
  } else if (form.short_description.length > 200) {
    errors.push("Description must be at most 200 characters");
  }

  return errors;
}
```

---

## 📊 Field Summary Table

| Field | Type | Required | Default | Validation | Example |
|-------|------|----------|---------|------------|---------|
| `author_id` | string | ✅ Yes | - | Must start with @ | `"@michael"` |
| `author_name` | string | ❌ No | Auto-generated | 2-100 chars | `"Michael Nguyen"` |
| `author_bio` | string | ❌ No | `""` | Max 500 chars | `"Developer..."` |
| `author_avatar_url` | string | ❌ No | `""` | Valid URL | `"https://..."` |
| `visibility` | enum | ✅ Yes | - | `public` or `point_based` | `"public"` |
| `access_config` | object | ⚠️ If paid | - | Required if `point_based` | See below |
| `category` | string | ✅ Yes | - | Min 1 char | `"programming"` |
| `tags` | array | ✅ Yes | - | 1-10 items | `["python"]` |
| `difficulty_level` | enum | ✅ Yes | - | 4 values | `"beginner"` |
| `short_description` | string | ✅ Yes | - | 10-200 chars | `"Learn..."` |
| `cover_image_url` | string | ❌ No | `null` | Valid URL | `"https://..."` |

### AccessConfig Fields (if visibility = "point_based")

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| `one_time_view_points` | number | ✅ Yes | - | >= 0 |
| `forever_view_points` | number | ✅ Yes | - | >= 0 |
| `download_pdf_points` | number | ✅ Yes | - | >= 0 |
| `is_one_time_enabled` | boolean | ❌ No | `true` | - |
| `is_forever_enabled` | boolean | ❌ No | `true` | - |
| `is_download_enabled` | boolean | ❌ No | `true` | - |

---

## 🎯 Common Mistakes to Avoid

❌ **Wrong:**
```json
{
  "author_id": "michael",  // Missing @
  "visibility": "paid",    // Wrong value (should be "point_based")
  "tags": "python",        // Should be array
  "difficulty_level": "easy"  // Wrong value (should be "beginner")
}
```

✅ **Correct:**
```json
{
  "author_id": "@michael",
  "visibility": "point_based",
  "tags": ["python"],
  "difficulty_level": "beginner",
  "short_description": "A comprehensive guide",
  "category": "programming"
}
```

---

## 🚀 Quick Start

**Minimum fields to publish free book:**
```json
{
  "author_id": "@michael",
  "visibility": "public",
  "category": "programming",
  "tags": ["python"],
  "difficulty_level": "beginner",
  "short_description": "Learn Python basics"
}
```

**Minimum fields to publish paid book:**
```json
{
  "author_id": "@michael",
  "visibility": "point_based",
  "access_config": {
    "one_time_view_points": 0,
    "forever_view_points": 100,
    "download_pdf_points": 0,
    "is_one_time_enabled": false,
    "is_forever_enabled": true,
    "is_download_enabled": false
  },
  "category": "programming",
  "tags": ["python"],
  "difficulty_level": "beginner",
  "short_description": "Learn Python basics"
}
```

---

**Đây là tất cả các fields cần thiết! Frontend chỉ cần implement form theo spec này là đủ.** 🎉
