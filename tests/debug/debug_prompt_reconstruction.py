#!/usr/bin/env python3
"""
Reconstruct exact prompt sent to DeepSeek from ai_extraction_service.py
"""
import sys
import json

sys.path.append("/Users/user/Code/ai-chatbot-rag")

from src.services.ai_extraction_service import AIExtractionService
from src.services.extraction_templates.template_factory import ExtractionTemplateFactory


def reconstruct_deepseek_prompt():
    """Reconstruct the exact prompt sent to DeepSeek"""

    print("🔍 RECONSTRUCTING DEEPSEEK PROMPT")
    print("=" * 60)

    # Initialize services
    ai_service = AIExtractionService()
    template_factory = ExtractionTemplateFactory()

    # Test data - Fashion CSV content
    csv_text = """CSV FILE: ivy-fashion-products.csv
Total Rows: 25
Columns: product_id, product_name, category, brand, price, size, color, material, stock_quantity, description

HEADER:
product_id | product_name | category | brand | price | size | color | material | stock_quantity | description

DATA ROWS:
Row 1: FW001 | Áo blazer nữ cao cấp | Áo khoác | IVY Fashion | 1580000 | S|M|L|XL | Đen|Xám|Be | Vải wool blend | 25 | Áo blazer nữ phong cách công sở, thiết kế thanh lịch
Row 2: FW002 | Váy midi hoa nhí | Váy | IVY Fashion | 890000 | S|M|L | Hồng|Xanh|Trắng | Cotton | 40 | Váy midi họa tiết hoa nhí, phù hợp dạo phố
Row 3: FW003 | Quần jean skinny | Quần | Denim Style | 650000 | 26|27|28|29|30 | Xanh đậm|Xanh nhạt|Đen | Denim cotton | 60 | Quần jean skinny ôm dáng, co giãn tốt
Row 4: FW004 | Áo sơ mi lụa | Áo | Silk Garden | 1200000 | S|M|L | Trắng|Kem|Hồng phấn | Lụa tơ tằm | 30 | Áo sơ mi lụa cao cấp, mềm mại và thoáng mát
Row 5: FW005 | Chân váy chữ A | Váy | Classic Line | 420000 | S|M|L|XL | Đen|Xám|Navy | Polyester | 45 | Chân váy chữ A cơ bản, dễ phối đồ
Row 6: FW006 | Áo len cổ lọ | Áo len | Warm Winter | 580000 | S|M|L | Đỏ|Xanh|Nâu | Len merino | 35 | Áo len cổ lọ ấm áp, chất liệu cao cấp
Row 7: FW007 | Đầm maxi hoa | Đầm | Summer Breeze | 750000 | S|M|L | Xanh lá|Vàng|Tím | Chiffon | 28 | Đầm maxi họa tiết hoa, phù hợp dự tiệc
Row 8: FW008 | Quần tây nữ | Quần | Office Lady | 680000 | S|M|L|XL | Đen|Xám|Navy | Wool blend | 50 | Quần tây nữ công sở, form dáng chuẩn
Row 9: FW009 | Áo khoác cardigan | Áo khoác | Cozy Time | 480000 | S|M|L | Be|Xám|Hồng | Acrylic | 38 | Cardigan nhẹ nhàng, phù hợp mùa thu
Row 10: FW010 | Váy ngắn da | Váy | Rock Style | 950000 | S|M|L | Đen|Nâu | Da thật | 22 | Váy ngắn da thật, phong cách cá tính"""

    # Metadata
    metadata = {
        "industry": "fashion",
        "original_name": "ivy-fashion-products.csv",
        "file_type": "text/csv",
    }

    target_categories = ["products"]
    company_info = None

    # Step 1: Get template
    template = template_factory.get_template_with_metadata(metadata)
    print(f"📋 Template: {template.__class__.__name__}")

    # Step 2: Build prompts exactly like in ai_extraction_service.py
    system_prompt = ai_service._build_auto_categorization_system_prompt(
        template, target_categories, company_info
    )

    user_prompt = ai_service._build_auto_categorization_user_prompt(
        template, target_categories, metadata, company_info
    )

    # Step 3: Enhanced user prompt with text content (like in _extract_with_deepseek_text)
    enhanced_user_prompt = f"""{user_prompt}

DOCUMENT CONTENT TO PROCESS:
{csv_text}

RAW DATA + JSON REQUIREMENT / YÊU CẦU RAW DATA + JSON:
For DeepSeek text processing, you must return BOTH:
1. raw_content: The original text content as processed
2. structured_data: JSON formatted according to the schema

IMPORTANT INSTRUCTIONS / HƯỚNG DẪN QUAN TRỌNG:
1. Analyze the above text content carefully
2. Extract ALL text as raw_content (preserve original content)
3. Process and structure the data according to the JSON schema
4. Return BOTH raw content and structured data in the format specified
5. Return ONLY the JSON response, no additional text, explanations, or formatting

Expected response format:
{{
  "raw_content": "Complete original content of the file...",
  "structured_data": {{
    {', '.join([f'"{cat}": [...extracted {cat}...]' for cat in target_categories])},
    "extraction_summary": {{
      "total_items": number,
      "data_quality": "high|medium|low",
      "extraction_notes": "Any relevant notes..."
    }}
  }}
}}"""

    # Step 4: Enhanced system prompt (like in _call_deepseek)
    enhanced_system_prompt = f"""{system_prompt}

TEXT PROCESSING INSTRUCTIONS:
- Analyze the provided text content carefully
- Extract all relevant data following the JSON schema
- Process structured text formats (JSON, CSV, TXT)
- Pay attention to patterns and formatting in the content

RAW DATA + JSON REQUIREMENT / YÊU CẦU RAW DATA + JSON:
You must return BOTH:
1. raw_content: The original text content as processed
2. structured_data: JSON formatted according to the schema

Return format:
{{
  "raw_content": "The original text content being processed...",
  "structured_data": {{
    "items": [...],
    "extraction_summary": {{...}}
  }}
}}

CRITICAL JSON FORMATTING INSTRUCTIONS:
- Return ONLY valid JSON format
- Include both raw_content and structured_data sections
- Use proper JSON syntax with double quotes
- Ensure all numbers are numeric (not strings) 
- For missing values, use null instead of empty strings
- Array fields should be empty arrays [] if no data found
- Do not wrap JSON in code blocks or markdown
- Start response directly with {{ and end with }}
"""

    final_user_prompt = f"""{enhanced_user_prompt}

IMPORTANT: Return ONLY the JSON response with both raw_content and structured_data sections, no additional text, explanations, or formatting."""

    print(f"\n📏 PROMPT LENGTHS:")
    print(f"System prompt: {len(enhanced_system_prompt)} characters")
    print(f"User prompt: {len(final_user_prompt)} characters")
    print(f"Total: {len(enhanced_system_prompt) + len(final_user_prompt)} characters")

    print(f"\n📝 SYSTEM PROMPT:")
    print("=" * 40)
    print(enhanced_system_prompt)

    print(f"\n📝 USER PROMPT:")
    print("=" * 40)
    print(final_user_prompt)

    # Create messages for DeepSeek
    messages = [
        {"role": "system", "content": enhanced_system_prompt},
        {"role": "user", "content": final_user_prompt},
    ]

    print(f"\n📊 MESSAGES FOR DEEPSEEK:")
    print("=" * 40)
    print(f"Number of messages: {len(messages)}")
    for i, msg in enumerate(messages):
        print(f"Message {i+1} ({msg['role']}): {len(msg['content'])} chars")

    # Save to file for testing
    with open("deepseek_prompt_test.json", "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Saved to deepseek_prompt_test.json for testing")

    return messages


if __name__ == "__main__":
    reconstruct_deepseek_prompt()
