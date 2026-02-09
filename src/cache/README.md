# Redis Cache System - Community Books

## 📦 Quick Start

### 1. Deploy với Docker Compose

Cache đã được tích hợp sẵn trong `docker-compose.yml`:

```bash
# Deploy toàn bộ system (bao gồm redis-community-book)
./deploy-compose-with-rollback.sh
```

Container `redis-community-book` sẽ tự động khởi động với:
- **RAM limit**: 512MB
- **Port**: 6380 (external), 6379 (internal)
- **Policy**: allkeys-lru (tự động xóa data cũ khi đầy)
- **Persistence**: ❌ NO (cache không lưu xuống disk)

### 2. Cache Warmup (Tự động)

Khi app khởi động, cache sẽ **TỰ ĐỘNG rebuild** các data quan trọng:

```
🚀 Starting AI Chatbot RAG Service...
🔥 Starting cache warmup...
🔥 Warming up: Category tree...
  ✅ Category tree cached: 11 parents, 368 books
🔥 Warming up: Top 5 books per category...
  ✅ business: 5 books cached
  ✅ education: 4 books cached
  ...
✅ Cached top books for 11/11 categories
🔥 Warming up: Trending books today...
  ✅ Trending today cached: 5 books
📊 CACHE WARMUP COMPLETED
  Memory used: 5.2MB
  Total keys: 13
```

### 3. Khi Nào Cache Bị Mất?

**Cache sẽ MẤT khi:**
- ✅ Docker container restart (`docker restart redis-community-book`)
- ✅ Server reboot
- ✅ Deploy mới (chạy `deploy-compose-with-rollback.sh`)

**Cache SẼ TỰ ĐỘNG REBUILD:**
- ✅ App startup tự động chạy cache warmup
- ✅ Các cache khác sẽ rebuild on-demand khi user request

**KHÔNG CẦN LO LẮNG VÌ:**
- Cache chỉ là "copy" của data trong MongoDB
- Data gốc vẫn còn nguyên trong database
- Cache miss → Query database → Set cache lại

---

## 🔧 Configuration

### Environment Variables

Đã được config sẵn trong `docker-compose.yml`:

```yaml
environment:
  - REDIS_CACHE_URL=redis://redis-community-book:6379
  - REDIS_CACHE_HOST=redis-community-book
  - REDIS_CACHE_PORT=6379
```

### Cache TTL (Time to Live)

| Cache Type | TTL | Rebuild Strategy |
|------------|-----|------------------|
| Category Tree | 10 min | Auto warmup on startup |
| Top 5 per Category | 30 min | Auto warmup on startup |
| Trending Today | 15 min | Auto warmup on startup |
| Featured Week | 30 min | On-demand |
| Search Results | 10 min | On-demand |

---

## 📊 Monitoring Cache

### Check Cache Status

```bash
# SSH vào server
ssh root@104.248.147.155

# Kiểm tra Redis cache container
docker exec redis-community-book redis-cli INFO memory

# Xem tất cả cache keys
docker exec redis-community-book redis-cli KEYS "*"

# Xem một cache cụ thể
docker exec redis-community-book redis-cli GET "categories:tree:all"

# Xem bao nhiêu keys đang cached
docker exec redis-community-book redis-cli DBSIZE
```

### Cache Hit/Miss Logs

Trong app logs (production):

```
✅ Cache HIT: categories:tree:all
❌ Cache MISS: books:top:category:education
💾 Cache SET: books:top:category:education (TTL: 1800s)
```

---

## 🧹 Clear Cache (Manual)

### Clear All Cache

```bash
# ⚠️ DANGER: Xóa toàn bộ cache
docker exec redis-community-book redis-cli FLUSHDB
```

### Clear Specific Cache

```bash
# Xóa category tree cache
docker exec redis-community-book redis-cli DEL "categories:tree:all"

# Xóa tất cả cache của category books
docker exec redis-community-book redis-cli KEYS "books:top:category:*" | xargs docker exec redis-community-book redis-cli DEL
```

### Rebuild Cache After Clear

Cache sẽ tự động rebuild khi:
1. User request endpoint → Cache miss → Query DB → Set cache
2. Restart app → Auto warmup

Hoặc chạy manual:

```bash
# Chạy cache warmup script
docker exec ai-chatbot-rag python -m src.cache.cache_warmup
```

---

## 🚀 Usage in Code

### Get Cached Data

```python
from src.cache.redis_client import get_cache_client

cache = get_cache_client()
await cache.connect()

# Get cache
data = await cache.get("categories:tree:all")

if data:
    # Cache HIT
    return data
else:
    # Cache MISS - query from database
    data = query_from_database()

    # Set cache for next time
    await cache.set("categories:tree:all", data, ttl=600)
    return data
```

### Invalidate Cache on Data Change

```python
# Khi có sách mới được publish
await cache.delete("categories:tree:all")
await cache.delete(f"books:top:category:{parent_category}")
await cache.delete("books:newest:all")
```

---

## 📈 Performance Benefits

### Before Cache

```
GET /book-categories/
  → 33 MongoDB count queries
  → 600-800ms response time
```

### After Cache

```
GET /book-categories/
  → 1 Redis lookup
  → 10ms response time
  → 60x faster! 🚀
```

---

## 🔥 Cache Warmup Details

### Automatic Warmup on Startup

File: `src/cache/cache_warmup.py`

**Warmed Caches:**
1. `categories:tree:all` - Category tree (33 children)
2. `books:top:category:{id}` - Top 5 books × 11 categories
3. `books:trending:today` - 5 trending books today

**Total Keys:** ~13 keys
**Total Memory:** ~5-10MB
**Time:** ~2-5 seconds

### Manual Warmup

```bash
# Run warmup script standalone
docker exec ai-chatbot-rag python -m src.cache.cache_warmup
```

---

## ⚠️ Troubleshooting

### Cache Not Working?

1. **Check container running:**
   ```bash
   docker ps | grep redis-community-book
   ```

2. **Check connection:**
   ```bash
   docker exec redis-community-book redis-cli PING
   # Expected: PONG
   ```

3. **Check app logs:**
   ```bash
   docker logs ai-chatbot-rag | grep -i cache
   ```

### Out of Memory?

Redis sẽ TỰ ĐỘNG evict (xóa) cache cũ theo policy `allkeys-lru`.

Check memory usage:
```bash
docker exec redis-community-book redis-cli INFO memory | grep used_memory_human
```

If needed, tăng limit trong `docker-compose.yml`:
```yaml
command: redis-server --maxmemory 1024mb  # Tăng từ 512mb
deploy:
  resources:
    limits:
      memory: 1024M  # Tăng từ 512M
```

---

## 📝 Next Steps

- [ ] Implement cache for `/books/trending-today`
- [ ] Implement cache for `/books/featured-week`
- [ ] Add cache invalidation on book publish/update
- [ ] Setup background cronjob for cache refresh (every 30 min)
- [ ] Monitor cache hit rate (target: > 95%)

---

## 🔗 Related Docs

- [REDIS_CACHING_STRATEGY.md](../REDIS_CACHING_STRATEGY.md) - Full caching strategy
- [SYSTEM_REFERENCE.md](../SYSTEM_REFERENCE.md) - System architecture
