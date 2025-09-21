# AI Extraction Prompt Templates cho Hybrid Search Strategy

## Overview

Tài liệu này cung cấp các template prompts để AI extraction service có thể generate đầy đủ categorization metadata cho hybrid search strategy. Các prompts này đảm bảo AI sẽ categorize products/services một cách consistent và comprehensive.

## 📋 **Categorization Schema**

### Core Fields
- **category**: Main category (required) - ví dụ: "bảo_hiểm", "dịch_vụ_tài_chính", "sản_phẩm_công_nghệ"
- **sub_category**: Sub-category (required) - ví dụ: "bảo_hiểm_nhân_thọ", "bảo_hiểm_sức_khỏe"
- **tags**: Array of relevant tags - ví dụ: ["gia_đình", "trẻ_em", "người_cao_tuổi"]
- **target_audience**: Array of target demographics - ví dụ: ["gia_đình_trẻ", "chuyên_gia", "doanh_nghiệp_nhỏ"]
- **coverage_type** (for insurance): Array of coverage types - ví dụ: ["tai_nạn", "bệnh_tật", "tử_vong"]
- **service_type** (for services): Array of service types - ví dụ: ["tư_vấn", "hỗ_trợ", "đào_tạo"]

## 🤖 **Enhanced AI Extraction Prompts**

### 1. **Product Extraction Prompt Template**

```
Bạn là một AI expert trong việc phân tích và categorize các sản phẩm/dịch vụ từ tài liệu tiếng Việt. 

**NHIỆM VỤ**: Trích xuất và categorize tất cả products từ tài liệu sau đây với metadata đầy đủ cho hybrid search.

**OUTPUT FORMAT**: JSON với structure sau đây

{
  "products": [
    {
      "name": "Tên chính xác của sản phẩm",
      "type": "Loại sản phẩm (ví dụ: Bảo hiểm nhân thọ)",
      "description": "Mô tả chi tiết sản phẩm",
      "coverage_period": "Thời gian bảo hiểm",
      "age_range": "Độ tuổi áp dụng",
      "coverage_area": "Phạm vi bảo hiểm", 
      "premium": "Phí bảo hiểm",
      "terms_and_conditions": "Điều kiện và điều khoản",
      
      // ===== AI CATEGORIZATION (REQUIRED) =====
      "category": "Danh mục chính (snake_case tiếng Việt)",
      "sub_category": "Danh mục phụ (snake_case tiếng Việt)", 
      "tags": ["tag1", "tag2", "tag3"], // Các từ khóa liên quan
      "target_audience": ["audience1", "audience2"], // Đối tượng mục tiêu
      "coverage_type": ["type1", "type2"] // Loại bảo hiểm (nếu applicable)
    }
  ]
}

**CATEGORIZATION GUIDELINES**:

📂 **Category Examples**:
- "bảo_hiểm" (cho các sản phẩm bảo hiểm)
- "đầu_tư" (cho các sản phẩm đầu tư) 
- "tiết_kiệm" (cho các sản phẩm tiết kiệm)
- "tín_dụng" (cho các sản phẩm vay/tín dụng)
- "thanh_toán" (cho các sản phẩm thanh toán)
- "công_nghệ" (cho các sản phẩm công nghệ)

🔸 **Sub_category Examples**:
- "bảo_hiểm_nhân_thọ", "bảo_hiểm_sức_khỏe", "bảo_hiểm_xe_cộ"
- "đầu_tư_chứng_khoán", "đầu_tư_bất_động_sản", "đầu_tư_vàng"
- "tiết_kiệm_ngân_hàng", "tiết_kiệm_bưu_điện"

🏷️ **Tags Guidelines** (chọn relevant tags):
- **Đối tượng**: "gia_đình", "cá_nhân", "doanh_nghiệp", "trẻ_em", "người_cao_tuổi"
- **Đặc điểm**: "linh_hoạt", "dài_hạn", "ngắn_hạn", "lợi_nhuận_cao", "rủi_ro_thấp"
- **Loại hình**: "trực_tuyến", "offline", "kết_hợp", "tự_động", "thủ_công"

👥 **Target_audience Examples**:
- "gia_đình_trẻ", "chuyên_gia", "doanh_nghiệp_nhỏ", "sinh_viên", "người_lao_động"
- "khách_hàng_vip", "khách_hàng_thường", "người_mới_bắt_đầu"

🛡️ **Coverage_type Examples** (for insurance):
- "tai_nạn", "bệnh_tật", "tử_vong", "thương_tật", "điều_trị"
- "nằm_viện", "phẫu_thuật", "khám_chữa_bệnh"

**CRITICAL REQUIREMENTS**:
1. ✅ Tất cả products PHẢI có đầy đủ category, sub_category, tags, target_audience
2. ✅ Sử dụng snake_case cho tất cả categorization fields
3. ✅ Tags phải relevant và specific, tránh generic words
4. ✅ Nếu không rõ thông tin, hãy extrapolate based on context
5. ✅ Ensure consistency trong naming convention

**INPUT DOCUMENT**:
```

### 2. **Service Extraction Prompt Template**

```
Bạn là một AI expert trong việc phân tích và categorize các dịch vụ từ tài liệu tiếng Việt.

**NHIỆM VỤ**: Trích xuất và categorize tất cả services từ tài liệu sau đây với metadata đầy đủ cho hybrid search.

**OUTPUT FORMAT**: JSON với structure sau đây

{
  "services": [
    {
      "name": "Tên chính xác của dịch vụ",
      "type": "Loại dịch vụ",
      "description": "Mô tả chi tiết dịch vụ",
      "pricing": "Thông tin về giá/phí dịch vụ",
      "availability": "Thời gian/địa điểm cung cấp dịch vụ",
      
      // ===== AI CATEGORIZATION (REQUIRED) =====
      "category": "Danh mục chính (snake_case tiếng Việt)",
      "sub_category": "Danh mục phụ (snake_case tiếng Việt)",
      "tags": ["tag1", "tag2", "tag3"], // Các từ khóa liên quan
      "target_audience": ["audience1", "audience2"], // Đối tượng mục tiêu  
      "service_type": ["type1", "type2"] // Loại hình dịch vụ
    }
  ]
}

**CATEGORIZATION GUIDELINES**:

📂 **Service Category Examples**:
- "tư_vấn" (consultation services)
- "hỗ_trợ" (support services)
- "đào_tạo" (training services)
- "bảo_trì" (maintenance services)
- "thiết_kế" (design services)
- "phát_triển" (development services)
- "quản_lý" (management services)

🔸 **Service Sub_category Examples**:
- "tư_vấn_tài_chính", "tư_vấn_pháp_lý", "tư_vấn_công_nghệ"
- "hỗ_trợ_kỹ_thuật", "hỗ_trợ_khách_hàng", "hỗ_trợ_triển_khai"
- "đào_tạo_nhân_viên", "đào_tạo_kỹ_năng", "đào_tạo_công_nghệ"

🏷️ **Service Tags Guidelines**:
- **Phương thức**: "trực_tuyến", "tại_chỗ", "từ_xa", "24/7", "theo_lịch"
- **Cấp độ**: "cơ_bản", "nâng_cao", "chuyên_sâu", "tùy_chỉnh"
- **Thời gian**: "nhanh_chóng", "dài_hạn", "liên_tục", "một_lần"

👥 **Service Target_audience Examples**:
- "doanh_nghiệp_lớn", "startup", "cá_nhân", "tổ_chức_phi_lợi_nhuận"
- "quản_lý_cấp_cao", "nhân_viên_kỹ_thuật", "người_dùng_cuối"

⚙️ **Service_type Examples**:
- "tư_vấn", "triển_khai", "bảo_trì", "đào_tạo", "hỗ_trợ"
- "thiết_kế", "phát_triển", "kiểm_thử", "tối_ưu_hóa"

**CRITICAL REQUIREMENTS**:
1. ✅ Tất cả services PHẢI có đầy đủ category, sub_category, tags, target_audience, service_type
2. ✅ Sử dụng snake_case cho tất cả categorization fields  
3. ✅ Tags phải specific và actionable
4. ✅ Service_type phải reflect actual service delivery method
5. ✅ Maintain consistency trong terminology

**INPUT DOCUMENT**:
```

### 3. **Combined Product + Service Extraction Prompt**

```
Bạn là một AI expert trong việc phân tích comprehensive và categorize cả products LẪN services từ tài liệu tiếng Việt.

**NHIỆM VỤ**: Trích xuất và categorize TẤT CẢ products và services từ tài liệu với metadata đầy đủ cho hybrid search strategy.

**OUTPUT FORMAT**: JSON với structure đầy đủ

{
  "products": [
    {
      "name": "...",
      "type": "...", 
      "description": "...",
      "coverage_period": "...",
      "age_range": "...",
      "coverage_area": "...",
      "premium": "...",
      "terms_and_conditions": "...",
      "category": "...",
      "sub_category": "...",
      "tags": [...],
      "target_audience": [...],
      "coverage_type": [...]
    }
  ],
  "services": [
    {
      "name": "...",
      "type": "...",
      "description": "...", 
      "pricing": "...",
      "availability": "...",
      "category": "...",
      "sub_category": "...",
      "tags": [...],
      "target_audience": [...],
      "service_type": [...]
    }
  ]
}

**🎯 HYBRID SEARCH OPTIMIZATION**:

Để tối ưu cho hybrid search (category filtering + vector similarity), hãy ensure:

1. **📂 Category Consistency**: Sử dụng same category names cho similar items
2. **🏷️ Tag Richness**: Include diverse, searchable tags
3. **👥 Audience Clarity**: Clear target audience definition
4. **🔍 Search-friendly Content**: Description should be comprehensive

**CATEGORY MAPPING GUIDELINES**:

| Business Domain | Main Categories | Sub-categories |
|-----------------|----------------|----------------|
| **Bảo hiểm** | bảo_hiểm | bảo_hiểm_nhân_thọ, bảo_hiểm_sức_khỏe, bảo_hiểm_tài_sản |
| **Ngân hàng** | tài_chính_ngân_hàng | tiết_kiệm, tín_dụng, thanh_toán, đầu_tư |
| **Công nghệ** | công_nghệ | phần_mềm, phần_cứng, cloud, AI, blockchain |
| **Giáo dục** | giáo_dục | đào_tạo, tư_vấn, chứng_chỉ, học_trực_tuyến |
| **Y tế** | y_tế_sức_khỏe | khám_bệnh, điều_trị, tư_vấn_sức_khỏe, dược_phẩm |

**EXAMPLE COMPLETE EXTRACTION**:

```json
{
  "products": [
    {
      "name": "Bảo hiểm sức khỏe gia đình FamilyCare Plus",
      "type": "Bảo hiểm sức khỏe",
      "description": "Gói bảo hiểm toàn diện cho gia đình với phạm vi bảo hiểm từ khám bệnh đến phẫu thuật",
      "coverage_period": "1 năm", 
      "age_range": "0-70 tuổi",
      "coverage_area": "Toàn quốc",
      "premium": "2.5 triệu VND/năm",
      "terms_and_conditions": "Chờ 30 ngày, không bảo hiểm bệnh có sẵn",
      "category": "bảo_hiểm",
      "sub_category": "bảo_hiểm_sức_khỏe", 
      "tags": ["gia_đình", "toàn_diện", "phẫu_thuật", "nằm_viện"],
      "target_audience": ["gia_đình_trẻ", "gia_đình_có_trẻ_nhỏ"],
      "coverage_type": ["khám_bệnh", "nằm_viện", "phẫu_thuật", "thai_sản"]
    }
  ],
  "services": [
    {
      "name": "Tư vấn tài chính cá nhân",
      "type": "Dịch vụ tư vấn",
      "description": "Tư vấn comprehensive về đầu tư, tiết kiệm và quy hoạch tài chính",
      "pricing": "500,000 VND/session",
      "availability": "Thứ 2-6, 8h-17h",
      "category": "tư_vấn",
      "sub_category": "tư_vấn_tài_chính",
      "tags": ["cá_nhân", "đầu_tư", "tiết_kiệm", "quy_hoạch"],
      "target_audience": ["cá_nhân", "gia_đình_trẻ", "chuyên_gia"],
      "service_type": ["tư_vấn", "quy_hoạch", "phân_tích"]
    }
  ]
}
```

**INPUT DOCUMENT**:
```

## 🔧 **Implementation Guidelines**

### 1. **AI Service Integration**

```javascript
// Example API call to AI service with enhanced prompt
const aiExtractionRequest = {
  prompt: enhancedProductExtractionPrompt,
  document_content: rawFileContent,
  extraction_type: "products_and_services",
  categorization_level: "comprehensive",
  output_format: "json",
  language: "vietnamese"
};

const aiResponse = await aiService.extract(aiExtractionRequest);

// Validate categorization completeness
function validateCategorization(extractedData) {
  const requiredFields = ['category', 'sub_category', 'tags', 'target_audience'];
  
  // Check products
  extractedData.products?.forEach(product => {
    requiredFields.forEach(field => {
      if (!product[field]) {
        console.warn(`⚠️ Product ${product.name} missing ${field}`);
      }
    });
  });
  
  // Check services  
  extractedData.services?.forEach(service => {
    requiredFields.forEach(field => {
      if (!service[field]) {
        console.warn(`⚠️ Service ${service.name} missing ${field}`);
      }
    });
  });
}
```

### 2. **Category Standardization**

```javascript
// Category normalization và standardization
const categoryMappings = {
  // Insurance variations
  "bao_hiem": "bảo_hiểm",
  "bảo hiểm": "bảo_hiểm", 
  "insurance": "bảo_hiểm",
  
  // Financial variations
  "tai_chinh": "tài_chính",
  "tài chính": "tài_chính",
  "finance": "tài_chính",
  
  // Technology variations
  "cong_nghe": "công_nghệ",
  "công nghệ": "công_nghệ",
  "technology": "công_nghệ"
};

function normalizeCategory(category) {
  const normalized = category.toLowerCase()
    .replace(/\s+/g, '_')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
    
  return categoryMappings[normalized] || normalized;
}
```

### 3. **Quality Assurance**

```javascript
// Post-extraction quality checks
function validateExtractionQuality(structured_data) {
  const qualityReport = {
    products: {
      total: structured_data.products?.length || 0,
      with_complete_categorization: 0,
      missing_fields: []
    },
    services: {
      total: structured_data.services?.length || 0, 
      with_complete_categorization: 0,
      missing_fields: []
    }
  };
  
  // Check product quality
  structured_data.products?.forEach(product => {
    const hasAllFields = ['category', 'sub_category', 'tags', 'target_audience']
      .every(field => product[field] && product[field].length > 0);
    
    if (hasAllFields) {
      qualityReport.products.with_complete_categorization++;
    } else {
      const missing = ['category', 'sub_category', 'tags', 'target_audience']
        .filter(field => !product[field] || product[field].length === 0);
      qualityReport.products.missing_fields.push({
        product: product.name,
        missing: missing
      });
    }
  });
  
  // Check service quality  
  structured_data.services?.forEach(service => {
    const hasAllFields = ['category', 'sub_category', 'tags', 'target_audience', 'service_type']
      .every(field => service[field] && service[field].length > 0);
      
    if (hasAllFields) {
      qualityReport.services.with_complete_categorization++;
    } else {
      const missing = ['category', 'sub_category', 'tags', 'target_audience', 'service_type']
        .filter(field => !service[field] || service[field].length === 0);
      qualityReport.services.missing_fields.push({
        service: service.name,
        missing: missing
      });
    }
  });
  
  return qualityReport;
}
```

## 📊 **Testing và Validation**

### Sample Test Cases

```javascript
// Test case 1: Insurance document
const insuranceTestDoc = `
Công ty ABC cung cấp các sản phẩm bảo hiểm sau:

1. Bảo hiểm nhân thọ ABC Life Plus
- Phí: 3 triệu VND/năm
- Độ tuổi: 18-65
- Bảo hiểm tử vong và thương tật

2. Dịch vụ tư vấn bảo hiểm cá nhân
- Phí: 200k/buổi
- Tư vấn online và offline
`;

// Expected output should include:
// - Products với category: "bảo_hiểm", sub_category: "bảo_hiểm_nhân_thọ"
// - Services với category: "tư_vấn", sub_category: "tư_vấn_bảo_hiểm"
// - Rich tags và target_audience
```

## 📈 **Performance Optimization**

### 1. **Prompt Efficiency**
- Sử dụng focused prompts cho specific document types
- Cache common categorization patterns
- Implement prompt versioning cho A/B testing

### 2. **Response Validation**
- Real-time validation của AI responses
- Fallback mechanisms cho incomplete categorization
- Quality scoring based on completeness

### 3. **Continuous Learning**
- Track user feedback trên categorization accuracy
- Update prompts based on common corrections
- Maintain category evolution over time

---

**📝 Note**: Các prompts này được optimize cho hybrid search strategy và có thể được customized based on specific business domains và requirements.
