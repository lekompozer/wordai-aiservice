# Tài liệu Phân biệt Luồng Xử lý Worker

Tài liệu này giải thích hai luồng xử lý song song được quản lý bởi `DocumentProcessingWorker` để tránh nhầm lẫn khi tích hợp.

## Tổng quan

`DocumentProcessingWorker` được thiết kế để xử lý hai loại tác vụ nền hoàn toàn riêng biệt, được kích hoạt bởi hai API endpoint khác nhau. Mỗi luồng có một mục đích, một mô hình dữ liệu (task model) và một phương thức xử lý riêng trong worker.

---

## 1. Luồng "File Upload" - Trích xuất Nội dung Thô

Luồng này tập trung vào việc xử lý các file tài liệu chung (PDF, DOCX, v.v.) để lấy nội dung văn bản và đưa vào cơ sở dữ liệu vector cho tìm kiếm ngữ nghĩa.

-   **API Kích hoạt:** `POST /api/admin/companies/{companyId}/files/upload`
-   **Mục đích:**
    -   Trích xuất **toàn bộ nội dung văn bản (raw text)** từ một file.
    -   Chia nhỏ (chunking) nội dung thành các đoạn văn bản hợp lý.
    -   Tạo vector embedding cho từng chunk.
    -   Lưu các chunk và vector vào Qdrant để phục vụ tìm kiếm ngữ nghĩa trên toàn bộ tài liệu.
-   **Task Model:** `DocumentProcessingTask` (`src/queue/task_models.py`)
-   **Phương thức xử lý chính trong Worker:** `process_task()` -> `_process_document_task()`
-   **Kết quả:** Nội dung của file được xử lý và sẵn sàng để được tìm kiếm thông qua các API search. Luồng này **không** trích xuất thông tin chi tiết về sản phẩm hay dịch vụ.

### Ví dụ sử dụng:
- Upload hợp đồng bảo hiểm dạng PDF.
- Upload tài liệu giới thiệu công ty.
- Upload file báo cáo tài chính.

---

## 2. Luồng "Extraction" - Bóc tách Sản phẩm & Dịch vụ

Luồng này được thiết kế chuyên biệt để bóc tách thông tin chi tiết về sản phẩm và dịch vụ từ các file như menu nhà hàng, bảng giá, danh mục sản phẩm.

-   **API Kích hoạt:** `POST /api/extract/process-async`
-   **Mục đích:**
    -   Sử dụng các **template chuyên biệt** theo từng ngành hàng (`industry`) để hướng dẫn AI.
    -   Trích xuất dữ liệu có cấu trúc (tên sản phẩm, giá, mô tả, đơn vị, v.v.).
    -   Tối ưu hóa việc chunking và embedding dựa trên các sản phẩm/dịch vụ đã được bóc tách.
    -   Lưu dữ liệu đã được cấu trúc hóa vào Qdrant.
-   **Task Model:** `ExtractionProcessingTask` (`src/queue/task_models.py`)
-   **Phương thức xử lý chính trong Worker:** `process_extraction_task()`
-   **Kết quả:** Một bộ dữ liệu có cấu trúc về sản phẩm/dịch vụ, sẵn sàng để sử dụng trong các tính năng chuyên biệt (hiển thị menu, so sánh sản phẩm, v.v.).

### Ví dụ sử dụng:
-   Upload menu nhà hàng dạng PDF để lấy danh sách món ăn và giá.
-   Upload bảng giá dịch vụ spa.
-   Upload danh mục sản phẩm từ một file excel.

---

## Sơ đồ Tóm tắt

| Tiêu chí | Luồng 1: File Upload | Luồng 2: Extraction API |
| :--- | :--- | :--- |
| **API Endpoint** | `POST /api/admin/companies/{companyId}/files/upload` | `POST /api/extract/process-async` |
| **Mục tiêu chính** | Lấy nội dung thô, tìm kiếm toàn văn | Bóc tách sản phẩm/dịch vụ |
| **Task Model** | `DocumentProcessingTask` | `ExtractionProcessingTask` |
| **Worker Method** | `process_task()` | `process_extraction_task()` |
| **Đầu ra** | Các chunk văn bản thô được embed | Dữ liệu JSON có cấu trúc về sản phẩm/dịch vụ |

Việc phân biệt rõ ràng hai luồng này là rất quan trọng để đảm bảo backend gọi đúng API cho đúng mục đích, giúp hệ thống hoạt động hiệu quả và chính xác.

---

## Ghi chú Kỹ thuật

### Vấn đề đã sửa (27/07/2025)
- **Lỗi:** `'DocumentProcessingWorker' object has no attribute 'run'`
- **Nguyên nhân:** Method `run()` bị thiếu trong class `DocumentProcessingWorker`
- **Giải pháp:** Đã thêm method `run()` để tạo main worker loop xử lý tasks từ Redis queue
- **Trạng thái:** ✅ Đã sửa xong

### Luồng xử lý chính trong Worker
1. Worker khởi động và kết nối Redis queue
2. Polling liên tục để tìm tasks mới
3. Phân loại task dựa trên cấu trúc dữ liệu:
   - Có `processing_metadata` → `ExtractionProcessingTask`
   - Không có → `DocumentProcessingTask`
4. Gọi method xử lý tương ứng
5. Xử lý kết quả và callback
