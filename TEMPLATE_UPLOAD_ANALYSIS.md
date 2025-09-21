# Template Upload & Analysis Workflow Documentation

## Tổng quan
Tài liệu này phân tích chi tiết quy trình upload và xử lý template DOCX cho hệ thống quote generation, bao gồm việc sử dụng AI để phân tích cấu trúc template và tạo metadata tự động.

## 1. Kiến trúc tổng thể

### 1.1 Các thành phần chính
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │───▶│   Backend       │───▶│   AI Service    │
│   Template      │    │   Template      │    │   Analysis      │
│   Upload UI     │    │   Storage       │    │   Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   R2 Storage    │    │   MongoDB       │    │   Gemini API    │
│   DOCX Files    │    │   Templates     │    │   Document      │
│   PDF Files     │    │   Metadata      │    │   Analysis      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 1.2 Database Collections
- **document_templates**: Lưu trữ metadata template
- **user_quote_settings**: Cài đặt quote của user
- **quote_settings**: Settings cho quote generation

## 2. Workflow chi tiết - Complete End-to-End Flow

### GIAI ĐOẠN 1: TEMPLATE UPLOAD & ANALYSIS (Thực hiện một lần)

#### **Bước 1: User Upload Template DOCX**
```
Frontend ──► Upload DOCX ──► Backend API ──► Validation ──► R2 Storage
   │              │              │             │             │
   ▼              ▼              ▼             ▼             ▼
User selects   Multipart     /api/templates/  File type   Store original
.docx file     form data     upload endpoint  size check   .docx securely
```

**Chi tiết quá trình:**
- User chọn file `.docx` từ máy tính
- Frontend tạo multipart form với: `file`, `template_name`, `description`, `category`
- Backend nhận request và validate:
  - File extension = `.docx`
  - File size ≤ 10MB
  - File structure hợp lệ (có thể mở bằng python-docx)
- Upload ngay lập tức lên R2 storage để đảm bảo an toàn
- Tạo record trong MongoDB với status `processing`
- Trả về `template_id` ngay lập tức cho user

#### **Bước 2: DOCX to PDF Conversion**
```
DOCX File ──► docx2pdf ──► PDF Format ──► R2 Storage ──► Database Update
    │             │           │            │             │
    ▼             ▼           ▼            ▼             ▼
Original      Convert    Better format   PDF URL     Store PDF
template      library    for AI vision   storage     reference
```

**Lý do convert sang PDF:**
- Gemini Vision API đọc PDF tốt hơn plain text
- PDF preserve layout, formatting, tables structure
- AI có thể "nhìn" được visual elements như logo placeholders, signature lines
- Detect complex layouts như multi-column, nested tables

#### **Bước 3: AI Analysis với Gemini Vision**
```
PDF File ──► Gemini Vision API ──► Structured Analysis ──► JSON Metadata
   │              │                      │                    │
   ▼              ▼                      ▼                    ▼
Upload to      Advanced AI            Smart placeholder    Store analysis
Gemini         document analysis      detection & typing   results in DB
```

**AI Analysis Prompt (Chi tiết):**
```
Analyze this PDF quote template and extract ALL variable information:

TASK: Convert this static template into a smart template with placeholders

ANALYSIS REQUIREMENTS:
1. PLACEHOLDER DETECTION:
   - Find all changeable data (names, addresses, amounts, dates, products)
   - Replace with {{placeholder_name}} format
   - Classify each placeholder type: text|currency|date|number|email|phone|calculated

2. STRUCTURE ANALYSIS:
   - Identify sections: header, customer_info, products, financial, footer
   - Detect table structures and repeatable rows
   - Map visual layout and formatting requirements

3. BUSINESS LOGIC DETECTION:
   - Find calculation patterns (subtotal → VAT → total)
   - Identify auto-generated fields (dates, reference numbers)
   - Detect conditional fields (discounts, special terms)

RETURN JSON FORMAT:
{
  "template_content": "Full content with placeholders replaced",
  "placeholders": {
    "{{company_name}}": {
      "type": "text",
      "description": "Tên công ty phát hành báo giá",
      "current_value": "CÔNG TY TNHH ABC",
      "section": "company_info",
      "validation_rules": ["required"],
      "auto_populate": false,
      "position": {"page": 1, "section": "header", "coordinates": "top-left"},
      "formatting": {"bold": true, "font_size": 14, "color": "black"}
    },
    "{{products[].name}}": {
      "type": "text",
      "description": "Tên sản phẩm/dịch vụ trong bảng",
      "section": "products",
      "is_array": true,
      "table_column": 2,
      "validation_rules": ["required"]
    },
    "{{total_amount}}": {
      "type": "currency",
      "description": "Tổng tiền cuối cùng",
      "section": "financial",
      "calculation_formula": "=subtotal + vat_amount - discount_amount",
      "formatting": {"bold": true, "color": "red", "alignment": "right"}
    }
  },
  "document_structure": {
    "pages": 2,
    "sections": ["header", "customer_info", "products_table", "financial_summary", "terms"],
    "tables": {
      "products_table": {
        "location": "page_1_center",
        "columns": ["STT", "Sản phẩm", "Đơn vị", "Số lượng", "Đơn giá", "Thành tiền"],
        "repeatable_rows": true,
        "calculation_columns": ["Thành tiền"],
        "row_template": "{{products[i].name}} | {{products[i].unit}} | {{products[i].quantity}} | {{products[i].price}} | {{products[i].subtotal}}"
      }
    }
  }
}
```

**AI Processing Result:**
Gemini sẽ trả về một JSON response cực kỳ chi tiết, ví dụ:
```json
{
  "placeholders": {
    "{{company_name}}": {
      "type": "text",
      "current_value": "CÔNG TY TNHH ABC TECHNOLOGY",
      "section": "company_info",
      "description": "Tên công ty"
    },
    "{{customer_name}}": {
      "type": "text",
      "current_value": "Ông Nguyễn Văn A",
      "section": "customer_info",
      "description": "Tên khách hàng"
    },
    "{{total_amount}}": {
      "type": "currency",
      "current_value": "50,000,000",
      "section": "financial",
      "calculation_formula": "=subtotal + vat_amount",
      "description": "Tổng tiền"
    }
  },
  "business_logic": {
    "auto_calculations": {
      "{{vat_amount}}": "={{subtotal}} * 0.1",
      "{{total_amount}}": "={{subtotal}} + {{vat_amount}}"
    }
  }
}
```

#### **Bước 4: Metadata Storage và Template Ready**
```
AI JSON ──► Parse & Validate ──► Database Storage ──► Template Active
   │              │                    │                │
   ▼              ▼                    ▼                ▼
Clean JSON    Structure check    Store in MongoDB   Ready for use
response      confidence score   ai_analysis field   status: completed
```

### GIAI ĐOẠN 2: QUOTE GENERATION (Sử dụng nhiều lần)

#### **Bước 1: User Request Quote Generation**
```
User Input ──► Template Selection ──► API Call ──► Load Template Metadata
    │                │                  │              │
    ▼                ▼                  ▼              ▼
"Tạo báo giá     template_12345    POST /api/quotes/  Get placeholders
50 triệu cho                       generate           and business logic
chị Lan"
```

#### **Bước 2: AI Information Extraction từ User Query**
```
User Query ──► AI Extraction ──► Structured Data ──► Validation
    │              │                │                │
    ▼              ▼                ▼                ▼
Natural text   Extract entities   JSON with values  Check completeness
request        using template     customer, price   and data types
               placeholder guide  product info
```

**AI Extraction Process:**
```python
extraction_prompt = f"""
Extract information from user query to fill template placeholders:

USER QUERY: "Tạo báo giá cho công ty ABC về dịch vụ thiết kế website, giá 50 triệu, khách hàng là chị Lan từ Hà Nội"

TEMPLATE PLACEHOLDERS: {template_placeholders}

Extract and return JSON:
{
  "customer_info": {
    "customer_name": "chị Lan",
    "customer_company": "công ty ABC",
    "customer_address": "Hà Nội",
    "customer_phone": null,
    "customer_email": null
  },
  "product_info": {
    "product_name": "dịch vụ thiết kế website",
    "product_description": "Thiết kế website chuyên nghiệp",
    "quantity": 1,
    "unit_price": 50000000,
    "subtotal": 50000000
  },
  "confidence": 0.9,
  "missing_fields": ["customer_phone", "customer_email"],
  "inferred_values": ["quantity defaulted to 1"]
}
"""
```

#### **Bước 3: Smart Data Merging**
```
Extracted Data ──► User Settings ──► Business Logic ──► Complete Dataset
      │                │               │                 │
      ▼                ▼               ▼                 ▼
From user query   Company info    Auto calculations   Ready for
AI extraction     from profile    VAT, totals, dates  template filling
```

**Data Merging Process:**
```python
final_data = {
  # From user settings
  "company_name": user_settings.company_info.name,
  "company_address": user_settings.company_info.address,

  # From AI extraction
  "customer_name": "chị Lan",
  "customer_company": "công ty ABC",
  "product_name": "dịch vụ thiết kế website",
  "unit_price": "50,000,000",

  # Auto-calculated
  "subtotal": 50000000,
  "vat_amount": 5000000,  # 10%
  "total_amount": 55000000,

  # Auto-generated
  "quote_date": "15/01/2024",
  "quote_number": "BG-2024-001",
  "valid_until": "15/02/2024"
}
```

#### **Bước 4: Template Processing & DOCX Generation**
```
Template File ──► Load from R2 ──► Replace Placeholders ──► Generate DOCX
     │               │                   │                    │
     ▼               ▼                   ▼                    ▼
Original .docx   Download file      {{placeholder}} →      New quote
from storage     to memory          actual values          document
```

**Final Generation:**
```python
# Load template
doc = Document(template_file_stream)

# Replace all placeholders
for paragraph in doc.paragraphs:
    for placeholder, value in field_mapping.items():
        paragraph.text = paragraph.text.replace(placeholder, str(value))

# Process tables for repeatable data
for table in doc.tables:
    # Handle product rows, calculations, etc.

# Save and upload result
output_stream = BytesIO()
doc.save(output_stream)
download_url = upload_to_r2(output_stream.getvalue())
```

### 2.1 Phase 1: Upload Template
```
User uploads DOCX ──► Multipart upload ──► R2 Storage ──► Database record
                                    │
                                    ▼
                              Generate PDF preview
```

**Bước 1: Frontend upload**
```javascript
// Frontend API call
const formData = new FormData();
formData.append('file', docxFile);
formData.append('template_name', 'Quote Template Premium');
formData.append('description', 'Template cao cấp cho báo giá');
formData.append('category', 'premium');

const response = await fetch('/api/templates/upload', {
    method: 'POST',
    body: formData
});
```

**Bước 2: Backend xử lý upload**
```python
@router.post("/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    template_name: str = Form(...),
    description: str = Form(...),
    category: str = Form(default="standard"),
    current_user: dict = Depends(get_current_user)
):
    # 1. Validate file type (DOCX only)
    # 2. Upload to R2 Storage
    # 3. Convert DOCX to PDF for preview
    # 4. Trigger AI analysis
    # 5. Save to database
```

### 2.2 Phase 2: AI Analysis với PDF Processing
```
DOCX File ──► Convert to PDF ──► Gemini Vision API ──► Structured metadata
    │              │                    │                      │
    ▼              ▼                    ▼                      ▼
Original       PDF Format      AI Document Analysis    Template Intelligence
Template      (Better OCR)     (Visual + Text)         (Smart Placeholders)
```

**AI Analysis Process với PDF:**

**Bước 1: DOCX to PDF Conversion**
- Hệ thống convert file `.docx` thành PDF format sử dụng `docx2pdf`
- PDF format cho phép Gemini Vision API đọc tốt hơn về layout, formatting, và structure
- Preserve toàn bộ visual elements như tables, headers, footers, styling

**Bước 2: Gemini Vision API Analysis**
- Gửi file PDF trực tiếp đến Gemini Vision API
- AI thực hiện dual analysis: Visual layout + Text content
- Detect complex structures như nested tables, multi-column layouts
- Understand formatting context để preserve trong quá trình generation

**Bước 3: Advanced AI Prompt for Template Analysis**
```
Phân tích file PDF template báo giá này và trả về JSON với cấu trúc chi tiết:

{
  "template_content": "Full content with placeholders replaced",
  "placeholders": {
    "{{placeholder_name}}": {
      "type": "text|currency|date|number|email|phone|calculated",
      "description": "Mô tả field",
      "current_value": "Giá trị hiện tại trong template",
      "section": "company_info|customer_info|products|financial|terms|header|footer",
      "validation_rules": ["required", "email", "numeric", "phone"],
      "auto_populate": false,
      "calculation_formula": "=subtotal * 0.1 (for VAT)",
      "position": {"page": 1, "section": "main_body", "table_row": 3},
      "formatting": {"bold": true, "color": "red", "alignment": "right"}
    }
  },
  "sections": [...],
  "business_logic": {...},
  "document_structure": {
    "total_pages": 2,
    "has_tables": true,
    "table_structure": {
      "products_table": {
        "location": "page_1_main",
        "columns": ["STT", "Sản phẩm", "Số lượng", "Đơn giá", "Thành tiền"],
        "repeatable_rows": true,
        "calculation_columns": ["Thành tiền"]
      }
    },
    "header_structure": "company_logo + company_info",
    "footer_structure": "terms_and_signature",
    "visual_elements": ["logo_placeholder", "signature_line"]
  }
}

CRITICAL REQUIREMENTS:
1. Tìm mọi thông tin có thể thay đổi và convert thành {{placeholder}}
2. Analyze table structures để support dynamic product lists
3. Detect calculation patterns (subtotal, VAT, discounts, totals)
4. Preserve exact formatting và positioning
5. Identify conditional sections (show/hide based on data)
```

**Bước 4: Enhanced Placeholder Detection**
AI phân tích và tạo ra các loại placeholders:

*Static Information Placeholders:*
- `{{company_name}}`, `{{company_address}}`, `{{company_phone}}`
- `{{customer_name}}`, `{{customer_company}}`, `{{customer_email}}`
- `{{quote_number}}`, `{{quote_date}}`, `{{valid_until}}`

*Dynamic Product Placeholders:*
- `{{products[].name}}`, `{{products[].quantity}}`, `{{products[].price}}`
- `{{products[].subtotal}}` (calculated field)

*Financial Calculation Placeholders:*
- `{{subtotal}}` = SUM(products[].subtotal)
- `{{vat_amount}}` = subtotal * vat_rate
- `{{discount_amount}}` (conditional)
- `{{total_amount}}` = subtotal + vat_amount - discount_amount

*Auto-Generated Placeholders:*
- `{{current_date}}`, `{{quote_expiry_date}}`
- `{{quote_reference_id}}`, `{{page_number}}`

### 2.3 Phase 3: Metadata Generation
```python
# AI Generated Template Metadata
{
    "placeholders": {
        "{{company_name}}": {
            "type": "text",
            "description": "Tên công ty",
            "default_value": "",
            "validation": "required",
            "section": "company_info"
        },
        "{{total_amount}}": {
            "type": "currency",
            "description": "Tổng tiền",
            "default_value": 0,
            "validation": "number",
            "section": "financial"
        }
    },
    "sections": [
        {
            "name": "header",
            "description": "Phần header với logo và thông tin công ty",
            "placeholders": ["{{company_name}}", "{{company_address}}"]
        },
        {
            "name": "customer_info",
            "description": "Thông tin khách hàng",
            "placeholders": ["{{customer_name}}", "{{customer_company}}"]
        }
    ],
    "business_logic": {
        "calculation_fields": ["{{subtotal}}", "{{vat_amount}}", "{{total_amount}}"],
        "auto_fill_fields": ["{{current_date}}", "{{quote_number}}"],
        "conditional_fields": ["{{discount_amount}}"]
    }
}
```

## 3. Technical Implementation

### 3.1 Data Models

```python
class TemplateAnalysisResult(BaseModel):
    """Kết quả phân tích template từ AI"""

    template_id: str
    placeholders: Dict[str, PlaceholderInfo]
    sections: List[TemplateSection]
    business_logic: Dict[str, Any]
    ai_analysis_score: float
    processing_time: float

class PlaceholderInfo(BaseModel):
    """Thông tin chi tiết về placeholder"""

    type: str  # text, number, date, currency, boolean
    description: str
    default_value: Any
    validation_rules: List[str]
    section: str
    auto_populate: bool = False
    calculation_formula: Optional[str] = None

class TemplateSection(BaseModel):
    """Thông tin về section trong template"""

    name: str
    description: str
    placeholders: List[str]
    order: int
    is_repeatable: bool = False  # Cho danh sách sản phẩm
    required: bool = True
```

### 3.2 Storage Structure

```
R2 Storage Structure:
/templates/
  /{user_id}/
    /{template_id}/
      /original.docx      # File gốc
      /preview.pdf        # PDF preview
      /analysis.json      # AI analysis result
      /thumbnails/        # Thumbnail images
        /page_1.png
        /page_2.png
```

### 3.3 Database Schema

```javascript
// MongoDB document_templates collection
{
  "_id": ObjectId("..."),
  "user_id": "firebase_uid_123",
  "name": "Premium Quote Template",
  "description": "Template cao cấp cho báo giá doanh nghiệp",
  "category": "premium",
  "type": "quote",
  "subtype": "business",

  // File information
  "files": {
    "docx_url": "https://r2.dev/templates/user123/template456/original.docx",
    "pdf_url": "https://r2.dev/templates/user123/template456/preview.pdf",
    "thumbnail_urls": ["https://r2.dev/templates/user123/template456/thumbnails/page_1.png"]
  },

  // AI Analysis results
  "ai_analysis": {
    "placeholders": {
      "{{company_name}}": {
        "type": "text",
        "description": "Tên công ty",
        "current_value": "CÔNG TY TNHH ABC",
        "section": "company_info",
        "validation_rules": ["required"],
        "auto_populate": false,
        "calculation_formula": null,
        "position": {"page": 1, "section": "header"},
        "formatting": {"bold": true, "font_size": 14}
      },
      "{{total_amount}}": {
        "type": "currency",
        "description": "Tổng tiền cuối cùng",
        "current_value": "50,000,000",
        "section": "financial",
        "validation_rules": ["required", "numeric"],
        "auto_populate": false,
        "calculation_formula": "=subtotal + vat_amount - discount_amount",
        "position": {"page": 1, "section": "financial_summary"},
        "formatting": {"bold": true, "color": "red", "alignment": "right"}
      }
    },
    "sections": [
      {
        "name": "header",
        "description": "Phần header với logo và thông tin công ty",
        "placeholders": ["{{company_name}}", "{{company_address}}", "{{company_phone}}"],
        "order": 1,
        "is_repeatable": false,
        "required": true
      },
      {
        "name": "products_table",
        "description": "Bảng danh sách sản phẩm/dịch vụ",
        "placeholders": ["{{products[].name}}", "{{products[].quantity}}", "{{products[].price}}"],
        "order": 3,
        "is_repeatable": true,
        "required": true,
        "table_structure": {
          "columns": ["STT", "Sản phẩm", "Số lượng", "Đơn giá", "Thành tiền"],
          "repeatable_rows": true,
          "calculation_columns": ["Thành tiền"]
        }
      }
    ],
    "business_logic": {
      "calculation_fields": ["{{subtotal}}", "{{vat_amount}}", "{{total_amount}}"],
      "auto_fill_fields": ["{{current_date}}", "{{quote_number}}", "{{valid_until}}"],
      "conditional_fields": ["{{discount_amount}}"],
      "validation_rules": {
        "{{customer_email}}": ["email"],
        "{{customer_phone}}": ["phone"],
        "{{total_amount}}": ["numeric", "greater_than_zero"]
      }
    },
    "document_structure": {
      "total_pages": 2,
      "has_tables": true,
      "table_locations": ["products_section"],
      "header_content": "Company logo and info",
      "footer_content": "Terms and signature line",
      "visual_elements": ["logo_placeholder", "signature_line"]
    },
    "confidence_score": 0.95,
    "analysis_version": "1.0"
  },

  // Metadata
  "is_active": true,
  "is_public": false,
  "usage_count": 0,
  "created_at": ISODate("..."),
  "updated_at": ISODate("..."),

  // Template validation
  "validation": {
    "is_valid": true,
    "errors": [],
    "warnings": ["Missing discount field"]
  }
}
```

## 4. API Endpoints

### 4.1 Template Upload Endpoint

```python
POST /api/templates/upload
Content-Type: multipart/form-data

Parameters:
- file: DOCX file (required)
- template_name: string (required)
- description: string (optional)
- category: string (default: "standard")

Response:
{
  "success": true,
  "template_id": "template_12345",
  "status": "processing",
  "message": "Template uploaded successfully. AI analysis in progress.",
  "urls": {
    "docx": "https://r2.dev/...",
    "pdf_preview": "https://r2.dev/...",
    "status_check": "/api/templates/template_12345/status"
  }
}
```

### 4.2 Template Analysis Status

```python
GET /api/templates/{template_id}/status

Response:
{
  "template_id": "template_12345",
  "status": "completed", // processing, completed, failed
  "progress": 100,
  "ai_analysis": {
    "placeholders_found": 15,
    "sections_identified": 4,
    "confidence_score": 0.92
  },
  "errors": []
}
```

### 4.3 Template Metadata

```python
GET /api/templates/{template_id}/metadata

Response:
{
  "template_id": "template_12345",
  "basic_info": { /* name, description, etc */ },
  "placeholders": { /* detailed placeholder info */ },
  "sections": [ /* section information */ ],
  "usage_stats": {
    "total_usage": 45,
    "last_used": "2024-01-15T10:30:00Z"
  }
}
```

## 5. Integration với Quote Generation - AI-Driven Workflow

### 5.1 Template Selection và User Input Processing

```python
# User chọn template và generate quote
POST /api/quotes/generate
{
  "template_id": "template_12345",
  "user_query": "Tạo báo giá cho công ty ABC về dịch vụ thiết kế website, giá 50 triệu, khách hàng là chị Lan từ Hà Nội",
  "settings_id": "settings_xyz789"  // User's company settings
}
```

### 5.2 AI-Powered Information Extraction từ User Query

**Bước 1: Load Template Metadata**
```python
# System load template metadata từ database
template_metadata = await get_template_metadata(template_id)
placeholders = template_metadata["ai_analysis"]["placeholders"]
business_logic = template_metadata["ai_analysis"]["business_logic"]
```

**Bước 2: AI Information Extraction**
Hệ thống sử dụng AI Provider để extract thông tin từ user_query dựa trên template placeholders:

```python
# AI Extraction Prompt
extraction_prompt = f"""
Dựa trên user query và danh sách placeholders của template, hãy extract thông tin và trả về JSON:

USER QUERY: "{user_query}"

TEMPLATE PLACEHOLDERS:
{json.dumps(placeholders, ensure_ascii=False, indent=2)}

Trả về JSON format:
{{
  "extracted_data": {{
    "customer_info": {{
      "customer_name": "extracted name",
      "customer_company": "extracted company",
      "customer_address": "extracted address",
      "customer_phone": "extracted phone",
      "customer_email": "extracted email"
    }},
    "product_info": {{
      "product_name": "extracted product/service",
      "product_description": "detailed description",
      "quantity": "extracted quantity",
      "unit_price": "extracted price",
      "subtotal": "calculated subtotal"
    }},
    "financial_info": {{
      "subtotal": "calculated from products",
      "vat_rate": "10%",
      "vat_amount": "calculated VAT",
      "discount_amount": "0 if not mentioned",
      "total_amount": "final total"
    }},
    "metadata": {{
      "quote_date": "current date",
      "valid_until": "quote + 30 days",
      "quote_number": "auto-generated"
    }}
  }},
  "confidence_score": 0.95,
  "missing_fields": ["fields not found in query"],
  "inferred_fields": ["fields AI inferred from context"]
}}

REQUIREMENTS:
1. Extract chính xác thông tin từ user query
2. Infer reasonable values cho missing fields
3. Calculate financial fields theo business logic
4. Format currency theo VND standard
5. Generate appropriate dates và references
"""

ai_extraction_result = await ai_service.extract_information(extraction_prompt)
```

**Bước 3: Data Validation và Enhancement**
```python
# Merge extracted data với user settings
def merge_with_user_settings(extracted_data, user_settings):
    # Fill company info từ user settings
    company_info = user_settings.company_info

    final_data = {
        "company_name": company_info.name,
        "company_address": company_info.address,
        "company_phone": company_info.phone,
        "company_email": company_info.email,
        "company_representative": company_info.representative,

        # Customer info từ AI extraction
        "customer_name": extracted_data["customer_info"]["customer_name"],
        "customer_company": extracted_data["customer_info"]["customer_company"],
        "customer_address": extracted_data["customer_info"]["customer_address"],

        # Product info
        "product_name": extracted_data["product_info"]["product_name"],
        "product_description": extracted_data["product_info"]["product_description"],
        "unit_price": extracted_data["product_info"]["unit_price"],
        "quantity": extracted_data["product_info"]["quantity"],

        # Financial calculations
        "subtotal": extracted_data["financial_info"]["subtotal"],
        "vat_amount": extracted_data["financial_info"]["vat_amount"],
        "total_amount": extracted_data["financial_info"]["total_amount"],

        # Auto-generated fields
        "quote_date": datetime.now().strftime("%d/%m/%Y"),
        "quote_number": generate_quote_number(),
        "valid_until": (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
    }

    return final_data
```

### 5.3 Smart Field Mapping với AI Validation

```python
async def smart_field_mapping(template_metadata: dict, extracted_data: dict, user_settings: dict) -> dict:
    """
    AI-powered mapping giữa extracted data và template placeholders
    """
    # Merge data sources
    final_data = merge_with_user_settings(extracted_data, user_settings)

    # Create mapping dictionary
    field_mapping = {}

    for placeholder, info in template_metadata["placeholders"].items():
        field_value = None

        # 1. Auto-populate fields
        if info["auto_populate"]:
            if "date" in placeholder.lower():
                field_value = datetime.now().strftime("%d/%m/%Y")
            elif "number" in placeholder.lower() or "id" in placeholder.lower():
                field_value = generate_reference_id()

        # 2. Map từ extracted data theo section
        elif info["section"] == "company_info":
            field_key = placeholder.replace("{{", "").replace("}}", "").replace("company_", "")
            field_value = final_data.get(f"company_{field_key}")

        elif info["section"] == "customer_info":
            field_key = placeholder.replace("{{", "").replace("}}", "").replace("customer_", "")
            field_value = final_data.get(f"customer_{field_key}")

        elif info["section"] == "products":
            field_key = placeholder.replace("{{", "").replace("}}", "").replace("product_", "")
            field_value = final_data.get(f"product_{field_key}")

        elif info["section"] == "financial":
            field_key = placeholder.replace("{{", "").replace("}}", "")
            field_value = final_data.get(field_key)

        # 3. Calculate fields với business logic
        elif info.get("calculation_formula"):
            field_value = calculate_financial_field(info["calculation_formula"], final_data)

        # 4. Default fallback
        if field_value is None:
            field_value = info.get("default_value", "")

        # Format theo type
        if info["type"] == "currency":
            field_value = format_currency(field_value)
        elif info["type"] == "date":
            field_value = format_date(field_value)

        field_mapping[placeholder] = field_value

    return field_mapping

def calculate_financial_field(formula: str, data: dict) -> float:
    """Calculate financial fields theo business logic"""
    if "subtotal * vat_rate" in formula:
        subtotal = float(data.get("subtotal", 0))
        vat_rate = 0.1  # 10%
        return subtotal * vat_rate
    elif "subtotal + vat_amount" in formula:
        subtotal = float(data.get("subtotal", 0))
        vat_amount = float(data.get("vat_amount", 0))
        return subtotal + vat_amount
    # Add more calculation logic as needed
    return 0
```

### 5.4 Final Quote Generation với Template Processing

```python
async def generate_quote_document(template_id: str, field_mapping: dict) -> dict:
    """
    Generate final DOCX document với field mapping
    """
    # 1. Load original template file từ R2
    template_file_url = await get_template_file_url(template_id)
    template_content = await download_file(template_file_url)

    # 2. Load DOCX với python-docx
    doc = Document(BytesIO(template_content))

    # 3. Replace placeholders trong document
    for paragraph in doc.paragraphs:
        for placeholder, value in field_mapping.items():
            if placeholder in paragraph.text:
                paragraph.text = paragraph.text.replace(placeholder, str(value))

    # 4. Process tables nếu có
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for placeholder, value in field_mapping.items():
                    if placeholder in cell.text:
                        cell.text = cell.text.replace(placeholder, str(value))

    # 5. Save generated document
    output_buffer = BytesIO()
    doc.save(output_buffer)
    output_buffer.seek(0)

    # 6. Upload to R2 và tạo download URL
    file_key = f"quotes/{user_id}/{quote_id}/quote.docx"
    download_url = await upload_and_get_presigned_url(output_buffer.getvalue(), file_key)

    return {
        "success": True,
        "quote_id": quote_id,
        "download_url": download_url,
        "field_mapping": field_mapping,
        "template_used": template_id
    }
```

## 6. Error Handling & Validation

### 6.1 File Validation
```python
def validate_docx_file(file: UploadFile) -> ValidationResult:
    """Validate uploaded DOCX file"""
    errors = []

    # Check file type
    if not file.filename.endswith('.docx'):
        errors.append("Only DOCX files are supported")

    # Check file size (max 10MB)
    if file.size > 10 * 1024 * 1024:
        errors.append("File size must be less than 10MB")

    # Check if file is valid DOCX
    try:
        Document(file.file)
    except Exception:
        errors.append("Invalid DOCX file format")

    return ValidationResult(is_valid=len(errors)==0, errors=errors)
```

### 6.2 AI Analysis Fallback
```python
async def analyze_template_with_fallback(docx_content: str) -> TemplateAnalysis:
    """AI analysis với fallback mechanism"""
    try:
        # Primary: Gemini 2.5 Pro analysis
        result = await gemini_analyze_template(docx_content)
        if result.confidence_score > 0.8:
            return result
    except Exception as e:
        logger.warning(f"Gemini analysis failed: {e}")

    try:
        # Fallback: Pattern-based analysis
        result = await pattern_based_analysis(docx_content)
        return result
    except Exception as e:
        logger.error(f"All analysis methods failed: {e}")
        return create_minimal_analysis(docx_content)
```

## 7. Performance Considerations

### 7.1 Async Processing
- Upload file ngay lập tức, trả về template_id
- AI analysis chạy background task
- WebSocket hoặc polling để check progress

### 7.2 Caching Strategy
```python
# Cache AI analysis results
@cached(ttl=3600)  # Cache 1 hour
async def get_template_analysis(template_id: str) -> TemplateAnalysis:
    """Get cached template analysis"""
    pass

# Cache generated PDFs
@cached(ttl=86400)  # Cache 24 hours
async def get_pdf_preview(template_id: str) -> bytes:
    """Get cached PDF preview"""
    pass
```

### 7.3 Resource Optimization
- Compress PDF previews
- Generate thumbnails asynchronously
- Lazy load template content
- Database indexing trên user_id, category, is_active

## 8. Security & Access Control

### 8.1 User Permissions
```python
class TemplatePermission:
    def can_upload(user: User) -> bool:
        """Check if user can upload templates"""
        return user.is_premium or user.template_quota > 0

    def can_access_template(user: User, template: Template) -> bool:
        """Check template access permissions"""
        return (
            template.user_id == user.id or
            template.is_public or
            user.has_shared_access(template.id)
        )
```

### 8.2 File Security
- Validate file content before processing
- Scan for malicious macros in DOCX
- Sanitize user input in template fields
- Rate limiting cho upload endpoints

## 9. Monitoring & Analytics

### 9.1 Metrics Tracking
```python
# Template usage analytics
{
  "template_id": "template_12345",
  "metrics": {
    "total_downloads": 156,
    "total_quotes_generated": 89,
    "average_rating": 4.7,
    "conversion_rate": 0.57,  # quotes generated / downloads
    "popular_fields": ["company_name", "total_amount", "customer_name"]
  }
}
```

### 9.2 Error Monitoring
- Track AI analysis failures
- Monitor file processing errors
- Alert on high error rates
- Performance metrics for each step

## 10. Future Enhancements

### 10.1 Advanced AI Features
- **Smart Template Suggestions**: AI gợi ý template dựa trên business type
- **Auto Field Detection**: Tự động detect field types từ context
- **Template Optimization**: AI đề xuất cải thiện template structure
- **Multi-language Support**: Phân tích template đa ngôn ngữ

### 10.2 Collaboration Features
- **Template Sharing**: Share template giữa users
- **Version Control**: Track template changes over time
- **Team Templates**: Shared templates cho organization
- **Approval Workflow**: Template review process

### 10.3 Integration Expansions
- **CRM Integration**: Sync với Salesforce, HubSpot
- **ERP Integration**: Connect với SAP, Oracle
- **E-signature**: Integrate với DocuSign
- **Document Management**: Version control, approval workflows

---

## Kết luận

Workflow template upload và analysis này tạo ra một hệ thống mạnh mẽ cho phép users upload template DOCX và tự động phân tích để tích hợp với quote generation system. AI analysis giúp tự động hóa việc mapping fields và đảm bảo templates được sử dụng hiệu quả trong quá trình tạo báo giá.

Key benefits:
- **Automation**: Giảm manual setup cho templates
- **Intelligence**: AI hiểu context và business logic
- **Flexibility**: Support nhiều template formats và structures
- **Scalability**: Xử lý large volume uploads và analysis
- **User Experience**: Simple upload process với powerful analysis
