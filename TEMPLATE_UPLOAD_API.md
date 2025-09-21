# Template Upload API - Quick Start Guide

## Tổng quan
API endpoint upload template DOCX với phân tích AI tự động để phát hiện placeholders và cấu trúc template.

## Endpoints

### 1. Upload Template
```http
POST /api/templates/upload
Content-Type: multipart/form-data

Form Fields:
- file: DOCX file (required)
- template_name: string (required)
- description: string (optional)
- category: string (default: "standard")
```

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/templates/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@template.docx" \
  -F "template_name=Premium Quote Template" \
  -F "description=Template cao cấp cho báo giá doanh nghiệp" \
  -F "category=premium"
```

**Response:**
```json
{
  "success": true,
  "template_id": "template_abc123",
  "status": "completed",
  "message": "Template uploaded and analyzed successfully",
  "urls": {
    "docx": "https://r2.dev/templates/user123/template_abc123/original.docx",
    "pdf_preview": "https://r2.dev/templates/user123/template_abc123/preview.pdf",
    "status_check": "/api/templates/template_abc123/status"
  },
  "analysis_summary": {
    "placeholders_found": 15,
    "sections_identified": 4,
    "confidence_score": 0.92,
    "processing_time": 3.5
  },
  "warnings": []
}
```

### 2. Get Template Status
```http
GET /api/templates/{template_id}/status
```

### 3. Get Template Metadata
```http
GET /api/templates/{template_id}/metadata
```

### 4. List User Templates
```http
GET /api/templates/
```

### 5. Delete Template
```http
DELETE /api/templates/{template_id}
```

## AI Analysis Features

### Placeholder Detection
Tự động phát hiện các placeholder patterns:
- `{{field_name}}` - Primary format
- `[field_name]` - Alternative format
- `__field_name__` - Underscore format
- `{field_name}` - Simple braces

### Field Type Classification
- **text**: Tên, địa chỉ, mô tả
- **currency**: Số tiền, giá trị
- **number**: Số lượng, số thứ tự
- **date**: Ngày tháng, thời gian
- **email**: Địa chỉ email
- **phone**: Số điện thoại

### Section Analysis
- **company_info**: Thông tin công ty
- **customer_info**: Thông tin khách hàng
- **products**: Sản phẩm/dịch vụ
- **financial**: Tính toán tài chính
- **terms**: Điều khoản

### Business Logic
- **auto_fill_fields**: Tự động điền (ngày, số báo giá)
- **calculation_fields**: Tính toán (tổng tiền, VAT)
- **conditional_fields**: Điều kiện hiển thị

## Integration với Quote Generation

```python
# Sử dụng template đã upload
POST /api/quotes/generate
{
  "template_id": "template_abc123",
  "user_query": "Tạo báo giá cho dự án website 50 triệu",
  "settings_id": "settings_xyz789"
}
```

## Error Handling

### Common Errors
- **400**: File validation failed
- **403**: Access denied
- **404**: Template not found
- **413**: File too large (>10MB)
- **500**: Processing error

### Error Response Format
```json
{
  "detail": "Error message",
  "error_code": "TEMPLATE_VALIDATION_FAILED",
  "errors": ["Specific error details"]
}
```

## Testing

### Run Tests
```bash
cd /Users/user/Code/ai-chatbot-rag
python -m pytest test_template_upload.py -v
```

### Test with Sample File
```bash
# Create test DOCX file
python -c "
from docx import Document
doc = Document()
doc.add_heading('TEST TEMPLATE', 0)
doc.add_paragraph('Company: {{company_name}}')
doc.add_paragraph('Customer: {{customer_name}}')
doc.add_paragraph('Total: {{total_amount}}')
doc.save('test_template.docx')
"

# Test upload
curl -X POST "http://localhost:8000/api/templates/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_template.docx" \
  -F "template_name=Test Template"
```

## Performance Notes

- **File Size Limit**: 10MB per template
- **Processing Time**: 2-5 seconds typical
- **Concurrent Uploads**: 10 per user
- **AI Analysis**: Gemini 2.5 Flash model
- **Fallback**: Pattern-based analysis if AI fails

## Security

- **Authentication**: Firebase JWT required
- **File Validation**: DOCX format only
- **Virus Scanning**: Planned for production
- **Access Control**: User-owned templates only
- **Rate Limiting**: 100 requests per hour

## Monitoring

### Key Metrics
- Upload success rate
- AI analysis accuracy
- Processing time
- Error rates by type
- Template usage statistics

### Logging
```json
{
  "event": "template_upload",
  "user_id": "user123",
  "template_id": "template_abc123",
  "placeholders_found": 15,
  "confidence_score": 0.92,
  "processing_time": 3.5,
  "file_size": 2048000
}
```
