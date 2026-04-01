# WordAI TikTok Collector

Chrome extension để thu thập captions, stats và ngày đăng từ TikTok để upload lên WordAI Content Engine.

## Cài đặt (Developer Mode)

1. Mở Chrome → `chrome://extensions/`
2. Bật **Developer mode** (góc phải trên)
3. Click **Load unpacked** → chọn thư mục này
4. Done! Icon xuất hiện trên toolbar.

## Cách dùng

1. Mở `https://www.tiktok.com` trong 1 tab và đăng nhập
2. Click icon extension → tự động connect
3. Chọn tab:
   - **❤️ Likes** — các video bạn đã like
   - **🔖 Saved** — các post đã save/collect
   - **👤 My Posts** — các bài đăng của tài khoản bạn đang dùng
   - **👥 Following** — bài đăng từ các acc bạn follow
4. Click **Load** để tải danh sách
5. **Following tab (2 bước)**:
   - Load danh sách accounts đang follow → tick chọn accounts muốn lấy
   - Click **Load Posts from Selected** → tải bài đăng từ các acc đó
6. Chọn posts (checkbox):
   - **All** — chọn tất cả
   - **New Only** — chỉ chọn posts chưa từng export
   - **None** — bỏ chọn hết
7. Click **⬇ JSON** hoặc **⬇ TXT** để tải file
8. Posts được chọn tự động đánh dấu **collected** → lần sau "New Only" sẽ bỏ qua

## Output formats

### JSON (`tiktok_export_*.json`)
```json
{
  "version": "1.0",
  "source": "likes",
  "profile": { "username": "wordaivn", "nickname": "WordAI VN" },
  "summary": { "total": 50, "videos": 45, "images": 5, "date_range": {...} },
  "posts": [
    {
      "id": "7123...",
      "desc": "Học tiếng Anh với WordAI 🇻🇳 #EnglishLearning",
      "created_date": "2024-03-15",
      "created_at": "2024-03-15T08:30:00.000Z",
      "media_type": "video",
      "stats": { "likes": 1234, "comments": 56, "shares": 78, "plays": 90000 },
      "author": { "username": "wordaivn" },
      "url": "https://www.tiktok.com/@wordaivn/video/7123..."
    }
  ]
}
```

### TXT (`tiktok_export_*.txt`)
```
===== WordAI TikTok Export =====
Source: likes
Account: @wordaivn (WordAI VN)
...

---
DATE: 2024-03-15  |  TYPE: VIDEO  |  ❤️ 1.2K  |  ▶️ 90.0K  |  💬 56
DESC: Học tiếng Anh với WordAI 🇻🇳 #EnglishLearning
URL: https://www.tiktok.com/@wordaivn/video/7123...
```

## Lưu ý

- Extension chỉ hoạt động khi có tab tiktok.com mở và đã đăng nhập
- Following tab: tối đa 20 accounts / lần fetch (để tránh rate limit)
- Collected IDs được lưu trong `chrome.storage.local` (per-browser)
- Không download video/ảnh — chỉ collect metadata + captions để phân tích
