# Book Translation Feature - Technical Analysis

## 📋 Tổng Quan

Phân tích tính năng **Dịch Book** (Book Translation) với khả năng:
- **Multi-Language Support**: Hỗ trợ nhiều ngôn ngữ cho cùng một book
- **Language Versions**: Lưu trữ nhiều phiên bản ngôn ngữ (vi, en, zh, ja, ko, etc.)
- **Preserve Structure**: Giữ nguyên định dạng HTML, background, và cấu trúc
- **AI Translation**: Sử dụng Gemini 2.5 Pro để dịch nội dung chất lượng cao
- **Selective Translation**: Dịch từng chapter hoặc toàn bộ book

---

## 🎯 Yêu Cầu Tính Năng

### 1. Cấu Trúc Dữ Liệu Hiện Tại

#### Book Schema (online_books collection)
```javascript
{
  book_id: "book_abc123",
  user_id: "firebase_uid",
  title: "Introduction to Programming",  // ← CẦN DỊCH
  description: "Learn programming basics",  // ← CẦN DỊCH
  slug: "intro-programming",

  // Branding & Media
  cover_image_url: "https://...",
  logo_url: "https://...",
  primary_color: "#4F46E5",

  // Background (GIỮ NGUYÊN hoặc cho phép edit riêng)
  background_config: {
    type: "ai_image",
    image: {
      url: "https://...",
      overlay_opacity: 0.3
    }
  },

  // Metadata
  visibility: "public",
  is_published: true,
  created_at: ISODate("..."),
  updated_at: ISODate("...")
}
```

#### Chapter Schema (book_chapters collection)
```javascript
{
  chapter_id: "chapter_xyz789",
  book_id: "book_abc123",
  parent_id: null,

  title: "Chapter 1: Variables",  // ← CẦN DỊCH
  slug: "chapter-1-variables",
  description: "Learn about variables",  // ← CẦN DỊCH (optional)
  order_index: 0,
  depth: 0,

  // Content (CẦN DỊCH - giữ nguyên HTML structure)
  content_source: "inline",  // or "document"
  content_html: "<h1>Variables</h1><p>Variables store data...</p>",  // ← CẦN DỊCH
  content_json: {...},  // TipTap format (optional)

  // Background (GIỮ NGUYÊN hoặc cho phép edit riêng)
  use_book_background: true,  // true = dùng background của book
  background_config: null,    // null khi use_book_background = true

  // Metadata
  is_published: true,
  created_at: ISODate("..."),
  updated_at: ISODate("...")
}
```

---

## 🌍 Giải Pháp: Multi-Language Version System

### Approach 1: Language Fields in Same Document (RECOMMENDED)

Thêm các field ngôn ngữ trực tiếp vào document hiện tại:

#### Book Schema với Multi-Language Support
```javascript
{
  book_id: "book_abc123",
  user_id: "firebase_uid",

  // ==================== LANGUAGE SYSTEM ====================

  // Ngôn ngữ gốc và hiện tại
  default_language: "vi",  // Ngôn ngữ gốc khi tạo book
  current_language: "vi",  // Ngôn ngữ đang active (frontend sẽ dùng để hiển thị)
  available_languages: ["vi", "en", "zh"],  // Danh sách ngôn ngữ đã dịch

  // ==================== ORIGINAL CONTENT (default_language) ====================
  title: "Lập Trình Cơ Bản",  // Ngôn ngữ gốc (vi)
  description: "Học lập trình từ đầu",

  // ==================== TRANSLATIONS ====================
  translations: {
    en: {
      title: "Introduction to Programming",
      description: "Learn programming from scratch",
      translated_at: ISODate("2025-12-04T10:00:00Z"),
      translated_by: "gemini-2.5-pro",
      translation_cost_points: 2
    },
    zh: {
      title: "编程入门",
      description: "从零开始学习编程",
      translated_at: ISODate("2025-12-05T14:30:00Z"),
      translated_by: "gemini-2.5-pro",
      translation_cost_points: 2
    }
  },

  // ==================== BACKGROUND (SHARED BY DEFAULT) ====================
  background_config: {
    type: "gradient",
    gradient: {
      colors: ["#667eea", "#764ba2"],
      type: "linear",
      angle: 135
    }
  },

  // Background per language (optional - nếu user muốn custom)
  background_translations: {
    en: {
      type: "ai_image",
      image: {
        url: "https://r2.../en-background.webp",
        overlay_opacity: 0.3
      }
    }
  },

  // Metadata
  slug: "intro-programming",  // Slug KHÔNG thay đổi theo ngôn ngữ
  visibility: "public",
  is_published: true,
  created_at: ISODate("..."),
  updated_at: ISODate("...")
}
```

#### Chapter Schema với Multi-Language Support
```javascript
{
  chapter_id: "chapter_xyz789",
  book_id: "book_abc123",
  parent_id: null,

  // ==================== LANGUAGE SYSTEM ====================
  default_language: "vi",  // Kế thừa từ book
  available_languages: ["vi", "en", "zh"],

  // ==================== ORIGINAL CONTENT ====================
  title: "Chương 1: Biến Số",
  description: "Tìm hiểu về biến số",
  slug: "chuong-1-bien-so",

  content_source: "inline",
  content_html: "<h1>Biến Số</h1><p>Biến số lưu trữ dữ liệu...</p>",

  // ==================== TRANSLATIONS ====================
  translations: {
    en: {
      title: "Chapter 1: Variables",
      description: "Learn about variables",
      content_html: "<h1>Variables</h1><p>Variables store data...</p>",
      translated_at: ISODate("2025-12-04T10:05:00Z"),
      translated_by: "gemini-2.5-pro",
      translation_cost_points: 2
    },
    zh: {
      title: "第一章：变量",
      description: "学习变量",
      content_html: "<h1>变量</h1><p>变量存储数据...</p>",
      translated_at: ISODate("2025-12-05T14:35:00Z"),
      translated_by: "gemini-2.5-pro",
      translation_cost_points: 2
    }
  },

  // ==================== BACKGROUND (SHARED BY DEFAULT) ====================
  use_book_background: true,
  background_config: null,  // null = sử dụng background của book

  // Background per language (optional)
  background_translations: {
    en: {
      use_book_background: false,
      background_config: {
        type: "theme",
        theme: "ocean"
      }
    }
  },

  // Metadata
  order_index: 0,
  depth: 0,
  is_published: true,
  created_at: ISODate("..."),
  updated_at: ISODate("...")
}
```

---

## 🔧 API Endpoints Design

### 1. Translate Entire Book

**Endpoint:**
```
POST /api/v1/books/{book_id}/translate
```

**Request Body:**
```json
{
  "target_language": "en",
  "source_language": "vi",
  "translate_chapters": true,
  "preserve_background": true,
  "custom_background": null
}
```

**Response:**
```json
{
  "success": true,
  "book_id": "book_abc123",
  "target_language": "en",
  "translated_fields": {
    "title": "Introduction to Programming",
    "description": "Learn programming from scratch"
  },
  "chapters_translated": 10,
  "total_cost_points": 22,
  "message": "Book translated successfully to English"
}
```

**Cost:**
- Book metadata translation: **2 points**
- Each chapter translation: **2 points**
- Total: 2 + (số chapter × 2) points

---

### 2. Translate Single Chapter

**Endpoint:**
```
POST /api/v1/books/{book_id}/chapters/{chapter_id}/translate
```

**Request Body:**
```json
{
  "target_language": "en",
  "source_language": "vi",
  "preserve_background": true,
  "custom_background": null
}
```

**Response:**
```json
{
  "success": true,
  "chapter_id": "chapter_xyz789",
  "book_id": "book_abc123",
  "target_language": "en",
  "translated_fields": {
    "title": "Chapter 1: Variables",
    "description": "Learn about variables",
    "content_html": "<h1>Variables</h1><p>Variables store data...</p>"
  },
  "translation_cost_points": 2,
  "message": "Chapter translated successfully to English"
}
```

**Cost:** **2 points** per chapter

---

### 3. Get Book in Specific Language

**Endpoint:**
```
GET /api/v1/books/{book_id}?language=en
```

**Query Parameters:**
- `language` (string, optional): Language code (vi, en, zh, etc.)
  - Default: book's `default_language`
  - If translation doesn't exist → fallback to default language

**Response:**
```json
{
  "book_id": "book_abc123",
  "title": "Introduction to Programming",
  "description": "Learn programming from scratch",
  "default_language": "vi",
  "current_language": "en",
  "available_languages": ["vi", "en", "zh"],
  "background_config": {
    "type": "gradient",
    "gradient": {
      "colors": ["#667eea", "#764ba2"],
      "type": "linear",
      "angle": 135
    }
  },
  "chapters": [...],
  "...": "other fields"
}
```

---

### 4. Get Chapter in Specific Language

**Endpoint:**
```
GET /api/v1/books/{book_id}/chapters/{chapter_id}?language=en
```

**Response:**
```json
{
  "chapter_id": "chapter_xyz789",
  "book_id": "book_abc123",
  "title": "Chapter 1: Variables",
  "description": "Learn about variables",
  "content_html": "<h1>Variables</h1><p>Variables store data...</p>",
  "current_language": "en",
  "available_languages": ["vi", "en", "zh"],
  "use_book_background": true,
  "background_config": null,
  "...": "other fields"
}
```

---

### 5. List Available Languages

**Endpoint:**
```
GET /api/v1/books/{book_id}/languages
```

**Response:**
```json
{
  "book_id": "book_abc123",
  "default_language": "vi",
  "available_languages": [
    {
      "code": "vi",
      "name": "Tiếng Việt",
      "is_default": true,
      "translated_at": null
    },
    {
      "code": "en",
      "name": "English",
      "is_default": false,
      "translated_at": "2025-12-04T10:00:00Z"
    },
    {
      "code": "zh",
      "name": "中文",
      "is_default": false,
      "translated_at": "2025-12-05T14:30:00Z"
    }
  ]
}
```

---

### 6. Update Background for Specific Language

**Endpoint:**
```
PUT /api/v1/books/{book_id}/background/{language}
```

**Request Body:**
```json
{
  "background_config": {
    "type": "ai_image",
    "image": {
      "url": "https://r2.../en-background.webp",
      "overlay_opacity": 0.3
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "book_id": "book_abc123",
  "language": "en",
  "background_config": {
    "type": "ai_image",
    "image": {
      "url": "https://r2.../en-background.webp",
      "overlay_opacity": 0.3
    }
  },
  "message": "Background updated for English version"
}
```

---

### 7. Delete Translation

**Endpoint:**
```
DELETE /api/v1/books/{book_id}/translations/{language}
```

**Response:**
```json
{
  "success": true,
  "book_id": "book_abc123",
  "language_deleted": "zh",
  "remaining_languages": ["vi", "en"],
  "message": "Chinese translation deleted successfully"
}
```

---

## 🤖 AI Translation Prompt Design

### Translation Prompt for Book Metadata

```python
def generate_book_metadata_translation_prompt(
    title: str,
    description: str,
    source_language: str,
    target_language: str
) -> str:
    """
    Generate prompt for translating book metadata (title + description)
    """

    return f"""You are a professional translator specializing in {target_language}.

**TASK:**
Translate the following book metadata from {source_language} to {target_language}.

**RULES:**
1. Maintain the same tone and style
2. Keep technical terms accurate
3. Adapt cultural references appropriately
4. Return ONLY valid JSON format (no markdown, no explanations)

**INPUT (in {source_language}):**
- Title: "{title}"
- Description: "{description}"

**OUTPUT FORMAT (JSON only):**
{{
  "title": "translated title in {target_language}",
  "description": "translated description in {target_language}"
}}

Return only the JSON object:"""
```

**Example Usage:**
```python
# Input (Vietnamese)
title = "Lập Trình Cơ Bản"
description = "Học lập trình từ đầu cho người mới bắt đầu"

# Output (English)
{
  "title": "Introduction to Programming",
  "description": "Learn programming from scratch for beginners"
}
```

---

### Translation Prompt for Chapter Content (HTML)

```python
def generate_chapter_translation_prompt(
    title: str,
    description: str,
    content_html: str,
    source_language: str,
    target_language: str
) -> str:
    """
    Generate prompt for translating chapter content (title + description + HTML)
    """

    return f"""You are a professional translator specializing in {target_language}.

**TASK:**
Translate chapter content from {source_language} to {target_language}.

**CRITICAL RULES FOR HTML TRANSLATION:**
1. PRESERVE HTML STRUCTURE: Keep ALL HTML tags, attributes, classes, IDs intact
2. TRANSLATE ONLY TEXT CONTENT: Only translate text inside HTML tags
3. DO NOT translate:
   - HTML tag names (<div>, <p>, <h1>, etc.)
   - CSS classes and IDs (class="text-blue-500", id="intro")
   - Inline styles (style="color: red;")
   - URLs in href and src attributes
   - Data attributes (data-*)
4. PRESERVE FORMATTING: Keep line breaks, indentation, spacing
5. HANDLE SPECIAL CONTENT:
   - Code blocks (<pre>, <code>): Keep code unchanged, translate only comments
   - Links: Translate link text but NOT the URL
   - Images: Translate alt text but NOT src
6. Return ONLY valid JSON (no markdown code blocks, no explanations)

**INPUT (in {source_language}):**
```json
{{
  "title": "{title}",
  "description": "{description}",
  "content_html": "{content_html}"
}}
```

**OUTPUT FORMAT (JSON only):**
```json
{{
  "title": "translated title in {target_language}",
  "description": "translated description in {target_language}",
  "content_html": "translated HTML content with preserved structure"
}}
```

Return only the JSON object:"""
```

**Example Translation:**

**Input (Vietnamese):**
```html
<div class="chapter-content">
  <h1 class="text-2xl font-bold">Biến Số</h1>
  <p>Biến số là nơi lưu trữ dữ liệu trong chương trình.</p>
  <pre><code class="language-python">
# Khai báo biến
x = 10
print(x)
  </code></pre>
  <a href="/docs/variables">Xem thêm tài liệu</a>
</div>
```

**Output (English):**
```html
<div class="chapter-content">
  <h1 class="text-2xl font-bold">Variables</h1>
  <p>Variables are storage locations for data in a program.</p>
  <pre><code class="language-python">
# Declare variable
x = 10
print(x)
  </code></pre>
  <a href="/docs/variables">View more documentation</a>
</div>
```

---

## 📊 Database Schema Changes

### Migration Script

```javascript
// Migration: Add language support to existing books and chapters

// 1. Update online_books collection
db.online_books.updateMany(
  {
    default_language: { $exists: false }
  },
  {
    $set: {
      default_language: "vi",  // Giả sử ngôn ngữ gốc là Tiếng Việt
      current_language: "vi",
      available_languages: ["vi"],
      translations: {},
      background_translations: {}
    }
  }
);

// 2. Update book_chapters collection
db.book_chapters.updateMany(
  {
    default_language: { $exists: false }
  },
  {
    $set: {
      default_language: "vi",
      available_languages: ["vi"],
      translations: {},
      background_translations: {}
    }
  }
);

// 3. Create indexes for language queries
db.online_books.createIndex({ "available_languages": 1 });
db.book_chapters.createIndex({ "available_languages": 1 });
```

---

## 🎨 Frontend Integration

### Language Switcher Component

```typescript
// LanguageSwitcher.tsx
import { useBook } from '@/hooks/useBook'
import { Select } from '@/components/ui/select'

export function LanguageSwitcher({ bookId }: { bookId: string }) {
  const { book, changeLanguage, isLoading } = useBook(bookId)

  return (
    <Select
      value={book.current_language}
      onChange={(lang) => changeLanguage(lang)}
      disabled={isLoading}
    >
      {book.available_languages.map((lang) => (
        <option key={lang} value={lang}>
          {LANGUAGE_NAMES[lang]}
        </option>
      ))}
    </Select>
  )
}

const LANGUAGE_NAMES = {
  vi: '🇻🇳 Tiếng Việt',
  en: '🇺🇸 English',
  zh: '🇨🇳 中文',
  ja: '🇯🇵 日本語',
  ko: '🇰🇷 한국어',
}
```

### API Hook Usage

```typescript
// hooks/useBook.ts
import { useState, useEffect } from 'react'
import { api } from '@/lib/api'

export function useBook(bookId: string, initialLanguage = 'vi') {
  const [book, setBook] = useState(null)
  const [currentLanguage, setCurrentLanguage] = useState(initialLanguage)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    fetchBook(currentLanguage)
  }, [bookId, currentLanguage])

  const fetchBook = async (language: string) => {
    setIsLoading(true)
    try {
      const response = await api.get(`/books/${bookId}?language=${language}`)
      setBook(response.data)
    } finally {
      setIsLoading(false)
    }
  }

  const changeLanguage = async (newLanguage: string) => {
    setCurrentLanguage(newLanguage)
  }

  const translateBook = async (targetLanguage: string) => {
    setIsLoading(true)
    try {
      await api.post(`/books/${bookId}/translate`, {
        target_language: targetLanguage,
        source_language: currentLanguage,
        translate_chapters: true,
        preserve_background: true
      })

      // Reload book with new language
      await fetchBook(targetLanguage)
      setCurrentLanguage(targetLanguage)
    } finally {
      setIsLoading(false)
    }
  }

  return {
    book,
    currentLanguage,
    isLoading,
    changeLanguage,
    translateBook
  }
}
```

---

## ⚙️ Implementation Checklist

## ⚙️ Implementation Checklist

### Phase 1: Database Schema
- [x] Add language fields to `online_books` collection
- [x] Add language fields to `book_chapters` collection
- [x] Create migration script for existing data
- [x] Add indexes for language queries

### Phase 2: Backend Models
- [x] Update `BookResponse` model with language fields
- [x] Update `ChapterResponse` model with language fields
- [x] Create `TranslateBookRequest` model
- [x] Create `TranslateChapterRequest` model
- [x] Create `LanguageListResponse` model

### Phase 3: Backend Services
- [x] Create `BookTranslationService` class
- [x] Implement `translate_book_metadata()` method
- [x] Implement `translate_chapter_content()` method
- [x] Implement `translate_entire_book()` method
- [x] Add language parameter to `get_book()` method (TODO: Update existing services)
- [x] Add language parameter to `get_chapter()` method (TODO: Update existing services)

### Phase 4: API Endpoints
- [x] `POST /api/v1/books/{book_id}/translate`
- [x] `POST /api/v1/books/{book_id}/chapters/{chapter_id}/translate`
- [ ] `GET /api/v1/books/{book_id}?language=xx` (TODO: Update existing endpoint)
- [ ] `GET /api/v1/books/{book_id}/chapters/{chapter_id}?language=xx` (TODO: Update existing endpoint)
- [x] `GET /api/v1/books/{book_id}/languages`
- [x] `PUT /api/v1/books/{book_id}/background/{language}`
- [x] `DELETE /api/v1/books/{book_id}/translations/{language}`

### Phase 5: AI Integration
- [x] Create translation prompt templates
- [x] Implement HTML structure preservation logic
- [x] Add translation quality validation
- [x] Handle translation errors gracefully
- [x] Add retry mechanism for failed translations

### Phase 6: Frontend Integration
- [ ] Create `LanguageSwitcher` component
- [ ] Update book viewer to use language parameter
- [ ] Update chapter viewer to use language parameter
- [ ] Add translation button in book settings
- [ ] Show translation progress indicator
- [ ] Display available languages list

### Phase 7: Testing
- [ ] Test translation with various HTML structures
- [ ] Test with nested chapters
- [ ] Test with code blocks and special content
- [ ] Test background preservation
- [ ] Test language switching
- [ ] Test fallback to default language

### Phase 8: Documentation
- [x] API documentation for translation endpoints (in code comments)
- [ ] User guide for translating books
- [ ] Developer guide for language system
- [x] Migration guide for existing books (migrate_add_language_support.py)

---

## 💡 Advanced Features (Future)

### 1. Automatic Translation on Publish
- Tự động dịch sang các ngôn ngữ phổ biến khi publish book
- User chọn target languages trước khi publish

### 2. Translation Quality Rating
- User có thể đánh giá chất lượng bản dịch
- AI học từ feedback để cải thiện

### 3. Collaborative Translation
- Cho phép nhiều user cùng dịch/review
- Version history cho translations

### 4. Translation Memory
- Lưu các cụm từ đã dịch để tái sử dụng
- Đảm bảo tính nhất quán trong cùng một book

### 5. Context-Aware Translation
- Dịch dựa trên context của chapter trước/sau
- Giữ tính liên kết và logic của nội dung

---

## 🔐 Security & Performance

### Points System
- **Book metadata translation**: 2 points
- **Chapter translation**: 2 points
- **Bulk translation**: Discounted (e.g., 10 chapters = 15 points instead of 20)

### Caching
- Cache translated content để tránh gọi API nhiều lần
- Cache timeout: 7 days (có thể refresh manually)

### Rate Limiting
- Max 10 translations per hour per user
- Max 50 chapters per batch translation

### Error Handling
- Graceful fallback to default language nếu translation fail
- Retry với exponential backoff
- Detailed error messages cho user

---

## 📝 Example API Usage

### Complete Translation Workflow

```python
# 1. Translate entire book
response = requests.post(
    "https://api.wordai.pro/api/v1/books/book_abc123/translate",
    headers={"Authorization": "Bearer <token>"},
    json={
        "target_language": "en",
        "source_language": "vi",
        "translate_chapters": True,
        "preserve_background": True
    }
)

# 2. Get book in English
book = requests.get(
    "https://api.wordai.pro/api/v1/books/book_abc123?language=en",
    headers={"Authorization": "Bearer <token>"}
).json()

# 3. Get specific chapter in English
chapter = requests.get(
    "https://api.wordai.pro/api/v1/books/book_abc123/chapters/chapter_xyz789?language=en",
    headers={"Authorization": "Bearer <token>"}
).json()

# 4. List available languages
languages = requests.get(
    "https://api.wordai.pro/api/v1/books/book_abc123/languages",
    headers={"Authorization": "Bearer <token>"}
).json()

# 5. Custom background for English version
requests.put(
    "https://api.wordai.pro/api/v1/books/book_abc123/background/en",
    headers={"Authorization": "Bearer <token>"},
    json={
        "background_config": {
            "type": "theme",
            "theme": "ocean"
        }
    }
)
```

---

## 🎯 Summary

### Key Points
1. **Multi-language support** bằng cách thêm fields vào document hiện tại (không tạo document mới)
2. **Preserve HTML structure** khi dịch content_html
3. **Shared background by default** nhưng cho phép custom per language
4. **AI-powered translation** với Gemini 2.5 Pro
5. **Points-based pricing**: 2 points per chapter
6. **Graceful fallback** về default language nếu translation không tồn tại

### Advantages
✅ Không duplicate data (giữ nguyên book_id và chapter_id)
✅ Dễ query và filter theo language
✅ Hỗ trợ unlimited languages
✅ Background sharing linh hoạt
✅ API simple và consistent

### Trade-offs
⚠️ Document size tăng khi có nhiều ngôn ngữ (giải quyết: pagination, lazy loading)
⚠️ Translation cost cao nếu book lớn (giải quyết: batch discount, caching)
⚠️ HTML translation phức tạp (giải quyết: robust prompt engineering)

---

## 📞 Next Steps

1. **Review & Approve**: Team review document này
2. **Database Migration**: Chạy migration script trên staging
3. **Implement Backend**: Code backend services và endpoints
4. **Test Translation**: Test với various HTML structures
5. **Frontend Integration**: Implement language switcher
6. **Deploy & Monitor**: Deploy lên production và monitor usage

---

**Document Version**: 1.0
**Last Updated**: 2025-12-04
**Author**: GitHub Copilot (Claude Sonnet 4.5)
