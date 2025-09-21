# Backend Integration API Documentation

## Company Basic Info Update

### Issue Fixed
- **Problem**: Backend was sending payload with `company_name` field but AI service expected `name` field
- **Solution**: Created new endpoint `/api/admin/companies/{company_id}/context/basic-info/from-backend` to handle backend-specific payload format

### New Endpoint for Backend

**POST** `/api/admin/companies/{company_id}/context/basic-info/from-backend`

**Headers:**
```http
Content-Type: application/json
X-API-Key: your-internal-api-key
```

**Request Body:**
```json
{
  "company_name": "AIA",
  "contact_info": "Email: lekompozer@gmail.com | Address: Tầng 15, Tòa nhà Saigon Centre, 67 Lê Lợi, Q.1, TP. Hồ Chí Minh, Hồ Chí Minh, Việt Nam",
  "introduction": "AIA TẠI VIỆT NAM - Thành lập: Năm 2000 - Trụ sở chính: Tầng 15, Tòa nhà Saigon Centre...",
  "products_summary": "Doanh nghiệp hoạt động trong lĩnh vực insurance"
}
```

**Response:**
```json
{
  "id": "693409fd-c214-47db-a465-2e565b00be05",
  "name": "AIA",
  "industry": "insurance",
  "location": {
    "country": "Việt Nam",
    "city": "Hồ Chí Minh",
    "address": "Tầng 15, Tòa nhà Saigon Centre, 67 Lê Lợi, Q.1, TP. Hồ Chí Minh, Hồ Chí Minh, Việt Nam"
  },
  "description": "AIA TẠI VIỆT NAM - Thành lập: Năm 2000 - Trụ sở chính: Tầng 15, Tòa nhà Saigon Centre...",
  "logo": "",
  "email": "lekompozer@gmail.com",
  "phone": "",
  "website": "",
  "socialLinks": {
    "facebook": "",
    "twitter": "",
    "zalo": "",
    "whatsapp": "",
    "telegram": ""
  }
}
```

### Features

1. **Smart Field Mapping**:
   - `company_name` → `name`
   - `contact_info` → parsed to extract `email`, `phone`, `address`
   - `introduction` → `description`
   - `products_summary` → auto-detect `industry`

2. **Address Parsing**:
   - Automatically extracts city and country from address
   - Supports Vietnamese address formats

3. **Industry Detection**:
   - Auto-detects industry based on products_summary
   - Supports: insurance, banking, restaurant, hotel, other

### Error Handling

**422 Validation Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "company_name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

**500 Processing Error:**
```json
{
  "detail": "Failed to process backend payload: Error message"
}
```

### Migration Guide

**Old endpoint (causing 422 error):**
```
POST /api/admin/companies/{company_id}/context/basic-info
```

**New endpoint (recommended for backend):**
```
POST /api/admin/companies/{company_id}/context/basic-info/from-backend
```

### Example cURL

```bash
curl -X POST https://ai.aimoney.io.vn/api/admin/companies/693409fd-c214-47db-a465-2e565b00be05/context/basic-info/from-backend \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-internal-api-key" \
  -d '{
    "company_name": "AIA",
    "contact_info": "Email: lekompozer@gmail.com | Address: Tầng 15, Tòa nhà Saigon Centre, 67 Lê Lợi, Q.1, TP. Hồ Chí Minh, Hồ Chí Minh, Việt Nam",
    "introduction": "AIA TẠI VIỆT NAM - Thành lập: Năm 2000...",
    "products_summary": "Doanh nghiệp hoạt động trong lĩnh vực insurance"
  }'
```
