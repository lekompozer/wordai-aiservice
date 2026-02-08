# Book Categories API Documentation

## Overview
WordAI Book Categories structure with **11 Parent Categories** and **33 Child Categories**.

Books from nhasachmienphi.com are automatically mapped to the appropriate categories.

## Category Structure

### Parent Categories (11)

| ID | Name (EN) | Name (VI) | Icon | Order |
|----|-----------|-----------|------|-------|
| `education` | Education | Giáo dục | GraduationCap | 1 |
| `business` | Business | Kinh doanh | Briefcase | 2 |
| `technology` | Technology | Công nghệ | Code | 3 |
| `health` | Health | Sức khỏe | Heart | 4 |
| `lifestyle` | Lifestyle | Lối sống | Sparkles | 5 |
| `entertainment` | Entertainment | Giải trí | Film | 6 |
| `literature-art` | Literature & Art | Văn học & Nghệ thuật | BookOpen | 7 |
| `children-stories` | Children Stories | Truyện thiếu nhi | Baby | 8 |
| `comics` | Comics | Truyện tranh | Book | 9 |
| `audiobooks` | Audiobooks | Sách nói | Headphones | 10 |
| `other` | Other | Khác | MoreHorizontal | 11 |

### Child Categories (33)

Organized by parent category:

**Education (7)**
- Sách Giáo Khoa (`sach-giao-khoa`)
- Học Ngoại Ngữ (`hoc-ngoai-ngu`)
- Khoa Học - Kỹ Thuật (`khoa-hoc-ky-thuat`)
- Kiến Trúc - Xây Dựng (`kien-truc-xay-dung`)
- Nông - Lâm - Ngư (`nong-lam-ngu`)
- Thư Viện Pháp Luật (`thu-vien-phap-luat`)
- Triết Học (`triet-hoc`)

**Business (3)**
- Kinh Tế - Quản Lý (`kinh-te-quan-ly`)
- Marketing - Bán hàng (`marketing-ban-hang`)
- Tâm Lý - Kỹ Năng Sống (`tam-ly-ky-nang-song`)

**Technology (1)**
- Công Nghệ Thông Tin (`cong-nghe-thong-tin`)

**Health (2)**
- Y Học - Sức Khỏe (`y-hoc-suc-khoe`)
- Tử Vi - Phong Thủy (`tu-vi-phong-thuy`)

**Lifestyle (2)**
- Ẩm thực - Nấu ăn (`am-thuc-nau-an`)
- Thể Thao - Nghệ Thuật (`the-thao-nghe-thuat`)

**Entertainment (4)**
- Truyện Cười - Tiếu Lâm (`truyen-cuoi-tieu-lam`)
- Phiêu Lưu - Mạo Hiểm (`phieu-luu-mao-hiem`)
- Trinh Thám - Hình Sự (`trinh-tham-hinh-su`)
- Truyện Ma - Truyện Kinh Dị (`truyen-ma-truyen-kinh-di`)

**Literature & Art (8)**
- Văn Học Việt Nam (`van-hoc-viet-nam`)
- Tiểu Thuyết Phương Tây (`tieu-thuyet-phuong-tay`)
- Tiểu Thuyết Trung Quốc (`tieu-thuyet-trung-quoc`)
- Truyện Ngắn - Ngôn Tình (`truyen-ngan-ngon-tinh`)
- Kiếm Hiệp - Tiên Hiệp (`kiem-hiep-tien-hiep`)
- Hồi Ký - Tuỳ Bút (`hoi-ky-tuy-but`)
- Thơ Hay (`tho-hay`)
- Văn Hóa - Tôn Giáo (`van-hoa-ton-giao`)

**Children Stories (3)**
- Cổ Tích - Thần Thoại (`co-tich-than-thoai`)
- Truyên Teen - Tuổi Học Trò (`truyen-teen-tuoi-hoc-tro`)
- Huyền bí - Giả Tưởng (`huyen-bi-gia-tuong`)

**Comics (1)**
- Truyện Tranh (`truyen-tranh`)

**Audiobooks (1)**
- Sách nói miễn phí (`sach-noi-mien-phi`)

**Other (1)**
- Lịch Sử - Chính Trị (`lich-su-chinh-tri`)

---

## API Endpoints

Base URL: `https://wordai.pro/api/v1/book-categories`

### 1. Get All Categories Tree

**GET** `/`

Returns full category tree with book counts.

**Response:**
```json
{
  "categories": [
    {
      "id": "business",
      "name": "Business",
      "name_vi": "Kinh doanh",
      "icon": "Briefcase",
      "order": 2,
      "total_books": 138,
      "children": [
        {
          "name": "Kinh Tế - Quản Lý",
          "slug": "kinh-te-quan-ly",
          "parent": "business",
          "books_count": 134
        },
        {
          "name": "Marketing - Bán hàng",
          "slug": "marketing-ban-hang",
          "parent": "business",
          "books_count": 0
        },
        {
          "name": "Tâm Lý - Kỹ Năng Sống",
          "slug": "tam-ly-ky-nang-song",
          "parent": "business",
          "books_count": 4
        }
      ]
    },
    // ... other categories
  ],
  "total_parents": 11,
  "total_children": 33,
  "total_books": 163
}
```

**Use Case:** Homepage category navigation, sidebar menu

---

### 2. Get Books by Parent Category

**GET** `/parent/{parent_id}`

Get all books under a parent category (includes all child categories).

**Parameters:**
- `parent_id` (path): Parent category ID (e.g., `business`)
- `skip` (query): Pagination offset (default: 0)
- `limit` (query): Items per page (default: 20, max: 100)
- `sort_by` (query): Sort order - `newest`, `views`, `rating` (default: `newest`)

**Example:**
```
GET /parent/business?skip=0&limit=20&sort_by=views
```

**Response:**
```json
{
  "books": [
    {
      "book_id": "book_abc123",
      "title": "Từ Tơ Lụa Đến Silicon",
      "slug": "tu-to-lua-den-silicon",
      "cover_url": "https://static.wordai.pro/books/covers/...",
      "authors": ["@sachonline"],
      "author_names": ["Sách Online"],
      "child_category": "Kinh Tế - Quản Lý",
      "parent_category": "business",
      "total_views": 150,
      "average_rating": 4.5,
      "access_points": {
        "one_time": 2,
        "forever": 5
      },
      "published_at": "2026-02-08T00:00:00Z"
    }
    // ... more books
  ],
  "category_name": "Kinh doanh",
  "category_type": "parent",
  "total": 138,
  "skip": 0,
  "limit": 20
}
```

**Use Case:** Category page showing all business books (all child categories combined)

---

### 3. Get Books by Child Category

**GET** `/child/{child_slug}`

Get books in a specific child category.

**Parameters:**
- `child_slug` (path): Child category slug (e.g., `kinh-te-quan-ly`)
- `skip` (query): Pagination offset (default: 0)
- `limit` (query): Items per page (default: 20, max: 100)
- `sort_by` (query): Sort order - `newest`, `views`, `rating` (default: `newest`)

**Example:**
```
GET /child/kinh-te-quan-ly?skip=0&limit=20&sort_by=newest
```

**Response:**
```json
{
  "books": [
    {
      "book_id": "book_abc123",
      "title": "Từ Tơ Lụa Đến Silicon",
      "slug": "tu-to-lua-den-silicon",
      "cover_url": "https://static.wordai.pro/books/covers/...",
      "authors": ["@sachonline"],
      "author_names": ["Sách Online"],
      "child_category": "Kinh Tế - Quản Lý",
      "parent_category": "business",
      "total_views": 150,
      "average_rating": 4.5,
      "access_points": {
        "one_time": 2,
        "forever": 5
      },
      "published_at": "2026-02-08T00:00:00Z"
    }
    // ... more books
  ],
  "category_name": "Kinh Tế - Quản Lý",
  "category_type": "child",
  "total": 134,
  "skip": 0,
  "limit": 20
}
```

**Use Case:** Specific subcategory page (e.g., only Economics books, not all Business)

---

## Frontend Implementation Guide

### 1. Homepage - Category Navigation

```typescript
// Fetch all categories with book counts
const response = await fetch('https://wordai.pro/api/v1/book-categories/');
const data = await response.json();

// Display parent categories with book counts
data.categories.forEach(parent => {
  console.log(`${parent.name_vi}: ${parent.total_books} books`);

  // Show child categories
  parent.children.forEach(child => {
    console.log(`  - ${child.name}: ${child.books_count} books`);
  });
});
```

### 2. Category Page - Load Books

```typescript
// Option 1: Show all books in parent category (e.g., all Business books)
const loadParentCategory = async (parentId: string, page = 1) => {
  const skip = (page - 1) * 20;
  const response = await fetch(
    `https://wordai.pro/api/v1/book-categories/parent/${parentId}?skip=${skip}&limit=20&sort_by=newest`
  );
  const data = await response.json();
  return data; // { books: [...], total: 138, ... }
};

// Option 2: Show books in specific child category
const loadChildCategory = async (childSlug: string, page = 1) => {
  const skip = (page - 1) * 20;
  const response = await fetch(
    `https://wordai.pro/api/v1/book-categories/child/${childSlug}?skip=${skip}&limit=20&sort_by=newest`
  );
  const data = await response.json();
  return data; // { books: [...], total: 134, ... }
};
```

### 3. Pagination Example

```typescript
const CategoryPage = ({ parentId }) => {
  const [books, setBooks] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    loadParentCategory(parentId, page).then(data => {
      setBooks(data.books);
      setTotal(data.total);
    });
  }, [parentId, page]);

  const totalPages = Math.ceil(total / 20);

  return (
    <div>
      <BookGrid books={books} />
      <Pagination page={page} total={totalPages} onChange={setPage} />
    </div>
  );
};
```

---

## Testing the API

### Test Category Tree
```bash
curl https://wordai.pro/api/v1/book-categories/
```

### Test Business Category Books
```bash
curl "https://wordai.pro/api/v1/book-categories/parent/business?skip=0&limit=5"
```

### Test Kinh Tế Child Category
```bash
curl "https://wordai.pro/api/v1/book-categories/child/kinh-te-quan-ly?skip=0&limit=5"
```

---

## Notes

1. **All endpoints are public** - No authentication required
2. **Pagination**: Use `skip` and `limit` for pagination
3. **Sorting**: `newest` (default), `views`, `rating`
4. **Book counts**: Real-time from database
5. **Access points**: Shows pricing (2 điểm/1 lần, 5 điểm/mãi mãi)

## Migration Notes

Old categories will be automatically migrated:
- Old: `"category": "kinh-te-quan-ly"` or `"category": "business"`
- New: `"category": "Kinh Tế - Quản Lý"`, `"parent_category": "business"`

All existing books have been updated with the new structure.
