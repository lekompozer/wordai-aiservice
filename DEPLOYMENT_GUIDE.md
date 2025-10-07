# 🚀 Hướng Dẫn Deployment Scripts

## 📋 Tổng Quan

Dự án này có nhiều script deployment khác nhau, mỗi script phục vụ một mục đích cụ thể. Tài liệu này giúp bạn hiểu rõ khi nào nên dùng script nào.

---

## 🎯 Lựa Chọn Script Phù Hợp

### ✅ Khuyến Nghị Sử Dụng (Docker Compose với Rollback)

| Script | Khi Nào Dùng | Ưu Điểm | Thời Gian Build |
|--------|--------------|---------|-----------------|
| **`deploy-compose-with-rollback.sh`** | Deploy thường xuyên, chỉ thay đổi code | • Nhanh nhất<br>• Tự động rollback<br>• Dùng cache | ⚡ 1-3 phút |
| **`deploy-compose-with-rollback-no-cache.sh`** | Cập nhật thư viện, dependencies | • Rebuild hoàn toàn<br>• Tự động rollback<br>• Đảm bảo clean build | 🐢 5-10 phút |

### ⚙️ Script Legacy (Dùng Docker Run)

| Script | Khi Nào Dùng | Nhược Điểm |
|--------|--------------|------------|
| `deploy-manual.sh` | Chỉ dùng khi cần debug hoặc tương thích với quy trình cũ | ❌ Không có rollback<br>❌ Khó quản lý |
| `deploy-no-cache.sh` | Legacy version của no-cache | ❌ Không có rollback |

---

## 📖 Chi Tiết Các Script

### 🎯 1. `deploy-compose-with-rollback.sh` (KHUYẾN NGHỊ)

**Mục đích:** Deploy nhanh với Docker Compose, có cơ chế rollback tự động

**Khi nào dùng:**
- ✅ Deploy code mới hàng ngày
- ✅ Thay đổi logic nghiệp vụ
- ✅ Fix bugs
- ✅ Cập nhật nhỏ không liên quan đến dependencies

**Đặc điểm:**
- ⚡ **Nhanh:** Sử dụng Docker build cache
- 🛡️ **An toàn:** Tự động rollback nếu version mới lỗi
- 📦 **Versioning:** Tag image bằng Git commit hash
- 🔄 **Health Check:** Kiểm tra sức khỏe với retry mechanism

**Cách dùng:**
```bash
# Cách 1: Chạy trực tiếp
./deploy-compose-with-rollback.sh

# Cách 2: Make executable trước (chỉ cần 1 lần)
chmod +x deploy-compose-with-rollback.sh
./deploy-compose-with-rollback.sh
```

**Quy trình tự động:**
1. Lấy code mới nhất từ Git
2. Lưu version đang chạy để rollback
3. Build image mới với cache
4. Deploy với docker-compose
5. Kiểm tra health check (3 lần retry)
6. **Nếu fail:** Tự động rollback về version cũ
7. **Nếu success:** Hoàn tất deployment

---

### 🔥 2. `deploy-compose-with-rollback-no-cache.sh` (Clean Build)

**Mục đích:** Rebuild hoàn toàn từ đầu, cài lại tất cả dependencies

**Khi nào dùng:**
- ✅ Cập nhật `requirements.txt`
- ✅ Thay đổi Python version
- ✅ Thêm/xóa thư viện
- ✅ Nghi ngờ cache bị lỗi
- ✅ Sau khi merge code lớn
- ✅ Release version mới quan trọng

**Đặc điểm:**
- 🐢 **Chậm:** Không dùng cache, build từ đầu
- 🧹 **Sạch sẽ:** Cài lại toàn bộ dependencies
- 🛡️ **An toàn:** Vẫn có rollback tự động
- 📦 **Versioning:** Tag image bằng Git commit hash

**Cách dùng:**
```bash
# Khi bạn vừa cập nhật requirements.txt
./deploy-compose-with-rollback-no-cache.sh

# Hoặc
chmod +x deploy-compose-with-rollback-no-cache.sh
./deploy-compose-with-rollback-no-cache.sh
```

**Thời gian ước tính:**
- ⏱️ Build: 5-10 phút (tùy tốc độ mạng và CPU)
- ⏱️ Health check: 30-60 giây
- **Tổng:** ~6-11 phút

---

### 🔧 3. `deploy-manual.sh` (Legacy - Docker Run)

**Mục đích:** Script cũ sử dụng `docker run` thay vì `docker-compose`

**Khi nào dùng:**
- ⚠️ Chỉ dùng khi cần debug chi tiết
- ⚠️ Hoặc để tương thích với quy trình cũ đã quen

**Nhược điểm:**
- ❌ Không có rollback tự động
- ❌ Nếu deploy lỗi, hệ thống sẽ DOWN
- ❌ Phải can thiệp thủ công khi có sự cố

**Cách dùng:**
```bash
./deploy-manual.sh
```

---

## 🎬 Workflow Deployment Thực Tế

### Deployment Hàng Ngày (Code Changes)

```bash
# 1. Commit code của bạn
git add .
git commit -m "feat: add new feature"
git push origin main

# 2. Trên server, chạy script cached
./deploy-compose-with-rollback.sh

# 3. Xem logs nếu cần
docker-compose logs -f ai-chatbot-rag
```

### Deployment Sau Khi Cập Nhật Dependencies

```bash
# 1. Cập nhật requirements.txt
echo "new-package==1.0.0" >> requirements.txt

# 2. Commit và push
git add requirements.txt
git commit -m "deps: add new package"
git push origin main

# 3. Trên server, dùng no-cache build
./deploy-compose-with-rollback-no-cache.sh

# 4. Uống cafe và chờ 6-10 phút ☕
```

---

## 🚨 Xử Lý Sự Cố

### Nếu Deployment Thất Bại

**Script tự động rollback sẽ làm gì:**
1. Phát hiện health check fail
2. Dừng container lỗi
3. Khởi động lại version cũ đã lưu
4. In ra logs để bạn debug

**Bạn cần làm gì:**
```bash
# 1. Xem logs để tìm nguyên nhân
docker logs ai-chatbot-rag --tail=100

# 2. Fix code
vim src/app.py  # Hoặc file nào đó

# 3. Commit và thử lại
git add .
git commit -m "fix: resolve deployment issue"
git push origin main

# 4. Deploy lại
./deploy-compose-with-rollback.sh
```

### Nếu Rollback Cũng Thất Bại

**Trường hợp nghiêm trọng - cần can thiệp thủ công:**

```bash
# 1. Kiểm tra các container đang chạy
docker ps -a

# 2. Kiểm tra network
docker network ls
docker network inspect ai-chatbot-network

# 3. Thử khởi động lại manual
docker-compose up -d

# 4. Hoặc dùng script legacy
./deploy-manual.sh

# 5. Cuối cùng: fresh start (XÓA TOÀN BỘ DỮ LIỆU)
./deploy-fresh-start.sh  # ⚠️ CHỈ DÙNG KHI TUYỆT VỌNG
```

---

## 📊 So Sánh Nhanh

| Tình Huống | Script Khuyến Nghị | Lý Do |
|------------|-------------------|-------|
| Deploy code mới | `deploy-compose-with-rollback.sh` | Nhanh, an toàn |
| Cập nhật thư viện | `deploy-compose-with-rollback-no-cache.sh` | Rebuild clean |
| Debug vấn đề | `deploy-manual.sh` | Chi tiết hơn |
| Lần đầu setup | `deploy-fresh-start.sh` | Khởi tạo từ đầu |

---

## 🔐 Yêu Cầu Môi Trường

Trước khi chạy bất kỳ script nào, đảm bảo:

1. **File `.env` tồn tại** với đầy đủ credentials:
```bash
MONGODB_ROOT_USERNAME=...
MONGODB_ROOT_PASSWORD=...
MONGODB_APP_USERNAME=...
MONGODB_APP_PASSWORD=...
DEEPSEEK_API_KEY=...
# ... các biến khác
```

2. **Network Docker đã được tạo** (script sẽ tự tạo nếu chưa có):
```bash
docker network ls | grep ai-chatbot-network
```

3. **Quyền thực thi cho scripts**:
```bash
chmod +x deploy-*.sh
```

---

## 🎓 Tips & Best Practices

### ✅ Nên Làm

- ✅ Luôn test code ở local trước khi deploy lên production
- ✅ Dùng version cached (`deploy-compose-with-rollback.sh`) cho deploys thường xuyên
- ✅ Dùng no-cache khi cập nhật dependencies
- ✅ Commit code trước khi deploy (để có version tag)
- ✅ Theo dõi logs sau mỗi lần deploy

### ❌ Không Nên

- ❌ Deploy trực tiếp lên production mà không test
- ❌ Dùng no-cache cho mọi lần deploy (lãng phí thời gian)
- ❌ Deploy khi có uncommitted changes (version tag sẽ không chính xác)
- ❌ Bỏ qua health check logs khi deployment fail

---

## 📞 Hỗ Trợ

Nếu gặp vấn đề:

1. Xem logs: `docker logs ai-chatbot-rag -f`
2. Check health: `curl http://localhost:8000/health`
3. Review script output để biết bước nào fail
4. Liên hệ team DevOps nếu cần

---

**Cập nhật lần cuối:** October 7, 2025
