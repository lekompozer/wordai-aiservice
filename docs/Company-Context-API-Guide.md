# Tài Liệu API - Company Context Management

Tài liệu này mô tả chi tiết tất cả các endpoints để quản lý ngữ cảnh công ty (Company Context) trong hệ thống AI Chatbot RAG.

## 🎯 Mục Đích

Company Context API cho phép backend quản lý thông tin ngữ cảnh của từng công ty để AI có thể:
- Hiểu rõ hơn về công ty khi trả lời khách hàng
- Nhập vai phù hợp (Sales, Support, etc.)
- Cung cấp thông tin chính xác về sản phẩm/dịch vụ
- Giải quyết các câu hỏi thường gặp (FAQs)

## 🌐 Luồng Xử Lý

```
Frontend (UI cho user nhập) → Backend API → AI Service API → AI Provider (Cerebras)
```

## 🔐 Authentication

Tất cả endpoints yêu cầu **Admin Access** với header:
```http
X-API-Key: your-internal-api-key
```

## 📋 Base URL

```
POST/GET/PUT/DELETE /api/admin/companies/{company_id}/context
```

---

## 📑 1. BASIC INFO MANAGEMENT

### 1.1 Tạo/Cập Nhật Thông Tin Cơ Bản

**Endpoint:** `POST /api/admin/companies/{company_id}/context/basic-info`

**Mô tả:** Tạo hoặc cập nhật thông tin cơ bản của công ty. dataType: company_info

**Request Body:**
```json
{
  "name": "Công ty TNHH ABC",
  "industry": "insurance",
  "description": "Chúng tôi là công ty hàng đầu trong lĩnh vực thương mại điện tử...",
  "location": {
    "country": "Việt Nam",
    "city": "Hồ Chí Minh",
    "address": "123 ABC Street, District 1, Ho Chi Minh City"
  },
  "email": "contact@abc.com",
  "phone": "1900-xxx-xxx",
  "website": "https://abc.com",
  "socialLinks": {
    "facebook": "https://facebook.com/abc",
    "zalo": "0123456789"
  }
}
```

**Response:**
```json
{
  "id": "company_id_123",
  "name": "Công ty TNHH ABC",
  "industry": "insurance",
  "description": "Chúng tôi là công ty hàng đầu trong lĩnh vực thương mại điện tử...",
  "location": {
    "country": "Việt Nam",
    "city": "Hồ Chí Minh",
    "address": "123 ABC Street, District 1, Ho Chi Minh City"
  },
  "logo": "",
  "email": "contact@abc.com",
  "phone": "1900-xxx-xxx",
  "website": "https://abc.com",
  "socialLinks": {
    "facebook": "https://facebook.com/abc",
    "twitter": "",
    "zalo": "0123456789",
    "whatsapp": "",
    "telegram": ""
  }
}
```

### 1.2 Lấy Thông Tin Cơ Bản

**Endpoint:** `GET /api/admin/companies/{company_id}/context/basic-info`

**Response:**
```json
{
  "id": "company_id_123",
  "name": "Công ty TNHH ABC",
  "industry": "insurance",
  "description": "Chúng tôi là công ty hàng đầu trong lĩnh vực thương mại điện tử...",
  "location": {
    "country": "Việt Nam",
    "city": "Hồ Chí Minh",
    "address": "123 ABC Street, District 1, Ho Chi Minh City"
  },
  "logo": "",
  "email": "contact@abc.com",
  "phone": "1900-xxx-xxx",
  "website": "https://abc.com",
  "socialLinks": {
    "facebook": "https://facebook.com/abc",
    "twitter": "",
    "zalo": "0123456789",
    "whatsapp": "",
    "telegram": ""
  }
}
```

**Error Response (404):**
```json
{
  "detail": "No basic info found for company_id 'abc123'"
}
```

### 1.3 Cập Nhật Thông Tin Cơ Bản

**Endpoint:** `PUT /api/admin/companies/{company_id}/context/basic-info`

**Request Body:** Giống POST

### 1.4 Xóa Thông Tin Cơ Bản

**Endpoint:** `DELETE /api/admin/companies/{company_id}/context/basic-info`

**Response:**
```json
{
  "message": "Basic info deleted successfully"
}
```

---

## ❓ 2. FAQs MANAGEMENT

### 2.1 Tạo/Thay Thế Tất Cả FAQs

**Endpoint:** `POST /api/admin/companies/{company_id}/context/faqs`

**Mô tả:** Thay thế hoàn toàn danh sách FAQs hiện tại. -> dataType: faq

**Request Body:**
```json
[
  {
    "question": "Làm thế nào để đặt hàng?",
    "answer": "Bạn có thể đặt hàng qua website hoặc gọi hotline 1900-xxx-xxx"
  },
  {
    "question": "Chính sách đổi trả như thế nào?",
    "answer": "Chúng tôi hỗ trợ đổi trả trong vòng 30 ngày với điều kiện sản phẩm còn nguyên vẹn"
  },
  {
    "question": "How to place an order?",
    "answer": "You can place an order through our website or call hotline 1900-xxx-xxx"
  }
]
```

**Response:** Trả về danh sách FAQs đã được cập nhật.

### 2.2 Lấy Tất Cả FAQs

**Endpoint:** `GET /api/admin/companies/{company_id}/context/faqs`

**Response:**
```json
[
  {
    "question": "Làm thế nào để đặt hàng?",
    "answer": "Bạn có thể đặt hàng qua website hoặc gọi hotline 1900-xxx-xxx"
  },
  {
    "question": "Chính sách đổi trả như thế nào?",
    "answer": "Chúng tôi hỗ trợ đổi trả trong vòng 30 ngày với điều kiện sản phẩm còn nguyên vẹn"
  }
]
```

### 2.3 Cập Nhật FAQs

**Endpoint:** `PUT /api/admin/companies/{company_id}/context/faqs`

**Request Body:** Giống POST

### 2.4 Thêm FAQ Đơn Lẻ

**Endpoint:** `POST /api/admin/companies/{company_id}/context/faqs/add`

**Request Body:**
```json
{
  "question": "Thời gian giao hàng bao lâu?",
  "answer": "Thời gian giao hàng từ 2-5 ngày làm việc tùy theo khu vực"
}
```

**Response:** Trả về danh sách FAQs sau khi thêm.

### 2.5 Xóa Tất Cả FAQs

**Endpoint:** `DELETE /api/admin/companies/{company_id}/context/faqs`

**Response:**
```json
{
  "message": "All FAQs deleted successfully"
}
```

---

## 🎭 3. SCENARIOS MANAGEMENT

### 3.1 Tạo/Thay Thế Tất Cả Scenarios

**Endpoint:** `POST /api/admin/companies/{company_id}/context/scenarios` - dataType: knowledge_base

**Mô tả:** Quản lý các kịch bản xử lý tình huống dựa trên intent của khách hàng

**Request Body:**
```json
[
  {
    "type": "SALES",
    "name": "Khách hàng muốn tư vấn sản phẩm bảo hiểm",
    "description": "Kịch bản khi khách hàng có ý định mua sản phẩm bảo hiểm và cần tư vấn chi tiết",
    "reference_messages": [
      "Tôi muốn mua bảo hiểm nhân thọ",
      "Cho tôi xem các gói bảo hiểm",
      "Tư vấn bảo hiểm cho gia đình",
      "I want to buy life insurance",
      "Show me insurance packages"
    ]
  },
  {
    "type": "ASK_COMPANY_INFORMATION",
    "name": "Khách hàng hỏi thông tin về công ty",
    "description": "Kịch bản khi khách hàng muốn tìm hiểu về công ty, lịch sử, dịch vụ tổng quan",
    "reference_messages": [
      "AIA là công ty gì?",
      "Giới thiệu về công ty của bạn",
      "Công ty hoạt động từ khi nào?",
      "What is AIA company?",
      "Tell me about your company"
    ]
  },
  {
    "type": "SUPPORT",
    "name": "Khách hàng cần hỗ trợ khiếu nại",
    "description": "Kịch bản xử lý khi khách hàng có vấn đề cần hỗ trợ hoặc khiếu nại",
    "reference_messages": [
      "Tôi muốn khiếu nại về dịch vụ",
      "Có vấn đề với đơn bảo hiểm",
      "Cần hỗ trợ gấp",
      "I have a complaint",
      "Need urgent support"
    ]
  },
  {
    "type": "GENERAL_INFORMATION",
    "name": "Khách hàng hỏi thông tin chung",
    "description": "Kịch bản cho các câu hỏi thông tin chung, không thuộc các loại trên",
    "reference_messages": [
      "Xin chào",
      "Làm thế nào để liên hệ?",
      "Giờ làm việc ra sao?",
      "Hello",
      "How to contact?"
    ]
  }
]
```

**Response:** Trả về danh sách scenarios đã được cập nhật.

### 3.2 Lấy Tất Cả Scenarios

**Endpoint:** `GET /api/admin/companies/{company_id}/context/scenarios`

**Response:**
```json
[
  {
    "type": "SALES",
    "name": "Khách hàng muốn tư vấn sản phẩm bảo hiểm",
    "description": "Kịch bản khi khách hàng có ý định mua sản phẩm bảo hiểm và cần tư vấn chi tiết",
    "reference_messages": [
      "Tôi muốn mua bảo hiểm nhân thọ",
      "Cho tôi xem các gói bảo hiểm",
      "Tư vấn bảo hiểm cho gia đình"
    ]
  },
  {
    "type": "ASK_COMPANY_INFORMATION",
    "name": "Khách hàng hỏi thông tin về công ty",
    "description": "Kịch bản khi khách hàng muốn tìm hiểu về công ty, lịch sử, dịch vụ tổng quan",
    "reference_messages": [
      "AIA là công ty gì?",
      "Giới thiệu về công ty của bạn",
      "Công ty hoạt động từ khi nào?"
    ]
  }
]
```

### 3.3 Cập Nhật Scenarios

**Endpoint:** `PUT /api/admin/companies/{company_id}/context/scenarios`

**Request Body:** Giống POST

### 3.4 Thêm Scenario Đơn Lẻ

**Endpoint:** `POST /api/admin/companies/{company_id}/context/scenarios/add`

**Request Body:**
```json
{
  "type": "SUPPORT",
  "name": "Khách hàng hủy đơn hàng",
  "description": "Kịch bản xử lý khi khách hàng muốn hủy đơn bảo hiểm đã mua",
  "reference_messages": [
    "Tôi muốn hủy đơn bảo hiểm",
    "Làm sao để hủy hợp đồng?",
    "Không muốn mua nữa",
    "I want to cancel my policy",
    "How to cancel insurance?"
  ]
}
```

### 3.5 Xóa Tất Cả Scenarios

**Endpoint:** `DELETE /api/admin/companies/{company_id}/context/scenarios`

**Response:**
```json
{
  "message": "All scenarios deleted successfully"
}
```

### 3.6 Cấu Trúc Dữ Liệu Scenarios

**Scenario Types (Required):**
- `SALES`: Kịch bản bán hàng, tư vấn sản phẩm
- `ASK_COMPANY_INFORMATION`: Kịch bản hỏi thông tin về công ty
- `SUPPORT`: Kịch bản hỗ trợ, khiếu nại
- `GENERAL_INFORMATION`: Kịch bản thông tin chung

**Fields:**
- `type` (required): Loại kịch bản (enum)
- `name` (required): Tên kịch bản
- `description` (required): Mô tả chi tiết kịch bản
- `reference_messages` (required): Danh sách tin nhắn mẫu để AI nhận diện intent

**Ví dụ Reference Messages:**
- Nên bao gồm cả tiếng Việt và tiếng Anh
- Đa dạng cách diễn đạt của khách hàng
- Từ 3-10 messages cho mỗi scenario
- Bao gồm cả formal và informal language

---

## 🌍 4. FULL CONTEXT MANAGEMENT

### 4.1 Lấy Toàn Bộ Context

**Endpoint:** `GET /api/admin/companies/{company_id}/context/`

**Mô tả:** Lấy toàn bộ ngữ cảnh công ty (được sử dụng bởi AI service).

**Response:**
```json
{
  "company_id": "abc123",
  "context_data": {
    "basic_info": {
      "id": "abc123",
      "name": "Công ty TNHH ABC",
      "industry": "insurance",
      "description": "Chúng tôi là công ty hàng đầu trong lĩnh vực thương mại điện tử...",
      "location": {
        "country": "Việt Nam",
        "city": "Hồ Chí Minh",
        "address": "123 ABC Street, District 1, Ho Chi Minh City"
      },
      "logo": "",
      "email": "contact@abc.com",
      "phone": "1900-xxx-xxx",
      "website": "https://abc.com",
      "socialLinks": {
        "facebook": "https://facebook.com/abc",
        "twitter": "",
        "zalo": "0123456789",
        "whatsapp": "",
        "telegram": ""
      }
    },
    "faqs": [
      {
        "question": "Làm thế nào để đặt hàng?",
        "answer": "Bạn có thể đặt hàng qua website..."
      }
    ],
    "scenarios": [
      {
        "type": "SALES",
        "name": "Khách hàng muốn tư vấn sản phẩm bảo hiểm",
        "description": "Kịch bản khi khách hàng có ý định mua sản phẩm bảo hiểm",
        "reference_messages": [
          "Tôi muốn mua bảo hiểm nhân thọ",
          "Cho tôi xem các gói bảo hiểm"
        ]
      }
    ]
  },
  "formatted_context": "### Company Information:\n- Company Name: Công ty TNHH ABC\n- Industry: insurance\n- Description: Chúng tôi là công ty hàng đầu...\n- Address: 123 ABC Street, District 1, Ho Chi Minh City, Hồ Chí Minh, Việt Nam\n- Contact: Phone: 1900-xxx-xxx, Email: contact@abc.com, Website: https://abc.com\n\n### Frequently Asked Questions (FAQs):\n- Q: Làm thế nào để đặt hàng?\n  A: Bạn có thể đặt hàng qua website...\n\n### Scenarios by Intent Type:\n\n#### SALES Scenarios:\n- Scenario: Khách hàng muốn tư vấn sản phẩm bảo hiểm\n  Description: Kịch bản khi khách hàng có ý định mua sản phẩm bảo hiểm\n  Reference Messages:\n    • Tôi muốn mua bảo hiểm nhân thọ\n    • Cho tôi xem các gói bảo hiểm"
}
```

### 4.2 Xóa Toàn Bộ Context

**Endpoint:** `DELETE /api/admin/companies/{company_id}/context/`

**Response:**
```json
{
  "message": "All company context deleted successfully"
}
```

---

## 💡 5. INTEGRATION EXAMPLES

### 5.1 Backend Integration (Node.js/Express)

```javascript
// Setup company context for a new company
async function setupCompanyContext(companyId, contextData) {
  const baseUrl = process.env.AI_SERVICE_URL;
  const apiKey = process.env.AI_SERVICE_API_KEY;

  try {
    // 1. Set basic info
    await fetch(`${baseUrl}/api/admin/companies/${companyId}/context/basic-info`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey
      },
      body: JSON.stringify(contextData.basicInfo)
    });

    // 2. Set FAQs
    if (contextData.faqs && contextData.faqs.length > 0) {
      await fetch(`${baseUrl}/api/admin/companies/${companyId}/context/faqs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey
        },
        body: JSON.stringify(contextData.faqs)
      });
    }

    // 3. Set scenarios
    if (contextData.scenarios && contextData.scenarios.length > 0) {
      await fetch(`${baseUrl}/api/admin/companies/${companyId}/context/scenarios`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey
        },
        body: JSON.stringify(contextData.scenarios)
      });
    }

    console.log(`Company context setup completed for ${companyId}`);
  } catch (error) {
    console.error('Failed to setup company context:', error);
    throw error;
  }
}
```

### 5.2 Frontend Integration (React)

```typescript
// Company Context Management Component
interface CompanyContextFormData {
  basicInfo: {
    name: string;
    industry: string;
    description: string;
    location: {
      country: string;
      city: string;
      address: string;
    };
    email: string;
    phone: string;
    website: string;
    socialLinks: {
      facebook: string;
      twitter: string;
      zalo: string;
      whatsapp: string;
      telegram: string;
    };
  };
  faqs: Array<{
    question: string;
    answer: string;
  }>;
  scenarios: Array<{
    type: 'SALES' | 'ASK_COMPANY_INFORMATION' | 'SUPPORT' | 'GENERAL_INFORMATION';
    name: string;
    description: string;
    reference_messages: string[];
  }>;
}

const CompanyContextManager: React.FC = () => {
  const [formData, setFormData] = useState<CompanyContextFormData>({
    basicInfo: {
      name: '',
      industry: '',
      description: '',
      location: {
        country: '',
        city: '',
        address: ''
      },
      email: '',
      phone: '',
      website: '',
      socialLinks: {
        facebook: '',
        twitter: '',
        zalo: '',
        whatsapp: '',
        telegram: ''
      }
    },
    faqs: [],
    scenarios: []
  });

  const saveCompanyContext = async () => {
    try {
      // Send to backend API
      const response = await fetch('/api/company-context/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          company_id: companyId,
          context_data: formData
        })
      });

      if (response.ok) {
        alert('Company context saved successfully!');
      }
    } catch (error) {
      console.error('Failed to save company context:', error);
    }
  };

  return (
    <form onSubmit={saveCompanyContext}>
      {/* Form fields for basic info, FAQs, scenarios */}
    </form>
  );
};
```

---

## 🚨 6. ERROR HANDLING

### Common Error Responses

**401 Unauthorized:**
```json
{
  "detail": "API key required. Please include X-API-Key header."
}
```

**404 Not Found:**
```json
{
  "detail": "No basic info found for company_id 'abc123'"
}
```

**422 Validation Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "company_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## 📝 7. BEST PRACTICES

### 7.1 Data Organization

1. **Basic Info:** Giữ thông tin ngắn gọn, súc tích
2. **FAQs:** Bao gồm cả tiếng Việt và tiếng Anh nếu có khách hàng quốc tế
3. **Scenarios:**
   - Phân loại đúng intent type (SALES, ASK_COMPANY_INFORMATION, SUPPORT, GENERAL_INFORMATION)
   - Reference messages đa dạng, bao gồm cả formal và informal
   - Mô tả scenario chi tiết, rõ ràng
   - Ít nhất 3-5 reference messages cho mỗi scenario

### 7.2 Scenarios Guidelines

**Intent Type Selection:**
- `SALES`: Khi khách hàng có ý định mua, đặt hàng, tư vấn sản phẩm/dịch vụ
- `ASK_COMPANY_INFORMATION`: Khi khách hàng hỏi về công ty, lịch sử, tầm nhìn, sứ mệnh
- `SUPPORT`: Khi khách hàng cần hỗ trợ, khiếu nại, giải quyết vấn đề
- `GENERAL_INFORMATION`: Thông tin chung, chào hỏi, hỏi đường, giờ làm việc

**Reference Messages Best Practices:**
- Bao gồm cả tiếng Việt và tiếng Anh
- Đa dạng cách diễn đạt (formal, informal, slang)
- Bao gồm cả câu hỏi trực tiếp và gián tiếp
- Tránh trùng lặp giữa các scenarios

**Ví dụ Reference Messages tốt:**
```json
{
  "type": "SALES",
  "reference_messages": [
    "Tôi muốn mua bảo hiểm",
    "Cho xem gói bảo hiểm nào tốt",
    "Tư vấn bảo hiểm cho em",
    "I want to buy insurance",
    "Show me insurance plans",
    "Which insurance is good?",
    "Bảo hiểm nào phù hợp với tôi?"
  ]
}
```

### 7.2 Security

1. Luôn sử dụng HTTPS
2. Bảo mật API key
3. Validate dữ liệu trước khi gửi

### 7.3 Performance

1. Cache context data ở backend
2. Batch updates thay vì nhiều API calls riêng lẻ
3. Kiểm tra kích thước dữ liệu (tránh quá lớn)

---

## 🔗 8. RELATED APIS

Sau khi setup Company Context, AI service sẽ sử dụng trong:

- `POST /api/unified/chat-stream` - Main chat endpoint
- `POST /api/unified/chat` - Non-streaming chat
- Internal: `_get_company_context_optimized()` trong luồng 7 bước

---

## 📞 Support

Nếu có vấn đề khi tích hợp, vui lòng kiểm tra:

1. API key có đúng không
2. Company ID có tồn tại không
3. Format dữ liệu có đúng schema không
4. Network connectivity

**Logs Location:** `src/utils/logger.py` - check for detailed error messages.
