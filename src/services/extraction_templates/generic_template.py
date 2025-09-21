"""
Generic template for industries not covered by specific templates
Template chung cho các ngành chưa có template riêng
"""

from typing import Dict, Any, List
from .base_template import BaseExtractionTemplate


class GenericExtractionTemplate(BaseExtractionTemplate):
    """Generic extraction template for general industries"""

    def _get_industry(self) -> str:
        return "generic"

    def get_system_prompt(self, data_type: str) -> str:
        if data_type == "products":
            return """Extract products with standardized pricing structure:

            🔥 CRITICAL PRICING EXTRACTION:
            For each product, extract ALL available price options as price_1, price_2, price_3:
            - price_1: Primary/most common price (REQUIRED)
            - price_2: Second price option if available (e.g., bulk discount, different size)
            - price_3: Third price option if available
            - original_price: Original price before discount (if mentioned)

            For each price, extract corresponding conditions:
            - condition_price_1: All conditions for price_1 (quantity, size, package details, etc.)
            - condition_price_2: All conditions for price_2
            - condition_price_3: All conditions for price_3

            🔥 PRODUCT CATEGORIES: Auto-categorize into relevant business categories:
            - Technology: "cong_nghe" (laptop, phone, software, etc.)
            - Food/Beverage: "thuc_pham", "do_uong"
            - Services: "dich_vu" (consulting, repair, etc.)
            - Retail: "ban_le" (clothing, accessories, etc.)

            🔥 DESCRIPTION: Generate natural language description optimized for AI chatbot responses.
            Format: "Sản phẩm [name]. [Description]. Thuộc danh mục [category]. Giá từ [price_1] [currency]. [Special features]."

            🔥 RETRIEVAL_CONTEXT: Create a comprehensive, natural Vietnamese paragraph combining all important information for customer service chatbot responses. Format example:
            "Sản phẩm Laptop Dell Inspiron 15 thuộc danh mục công nghệ. Mô tả: Laptop văn phòng với chip Intel Core i5, RAM 8GB, SSD 256GB, màn hình 15.6 inch Full HD. Giá chính: 15,990,000 VND - giá lẻ cho khách hàng cá nhân. Giá sỉ: 14,500,000 VND - áp dụng từ 5 máy trở lên. Số lượng có sẵn: 50 chiếc. Bảo hành 2 năm chính hãng, miễn phí vận chuyển toàn quốc."

            🔥 CURRENCY DETECTION: Look for ₫, VND, VNĐ (Vietnamese) or $, USD (US Dollar).

            🔥 OTHER INFO: Extract industry-specific details into other_info section.

            Include quantity (default: 1 if not specified)."""
        else:  # services
            return """Extract services with standardized pricing structure:

            🔥 RETRIEVAL_CONTEXT: Create a comprehensive, natural Vietnamese paragraph for each service combining all important information for customer service chatbot responses. Format example:
            "Dịch vụ thiết kế website thuộc danh mục thiết kế. Mô tả: Thiết kế website responsive chuyên nghiệp cho doanh nghiệp với giao diện hiện đại, tối ưu SEO. Giá: 5,000,000 VND - gói cơ bản bao gồm 5 trang. Giá cao cấp: 12,000,000 VND - gói premium với tính năng đầy đủ. Thời gian thực hiện: 2-3 tuần. Phương thức: trực tuyến. Bảo hành 6 tháng, hỗ trợ 24/7."

            🔥 CRITICAL PRICING EXTRACTION:
            For each service, extract ALL available price options as price_1, price_2, price_3:
            - price_1: Primary/most common price (REQUIRED, use 0 for free services)
            - price_2: Second price option if available (different duration, package, etc.)
            - price_3: Third price option if available
            - original_price: Original price before discount (if mentioned)

            For each price, extract corresponding conditions:
            - condition_price_1: All conditions for price_1 (duration, includes, location, etc.)
            - condition_price_2: All conditions for price_2
            - condition_price_3: All conditions for price_3

            🔥 SERVICE CATEGORIES: Auto-categorize into relevant business categories:
            - Consulting: "tu_van" (financial, legal, business consulting)
            - Technical: "ky_thuat" (repair, installation, maintenance)
            - Design: "thiet_ke" (web, graphic, interior design)
            - Training: "dao_tao" (courses, workshops, education)
            - Support: "ho_tro" (customer service, technical support)

            🔥 DESCRIPTION: Generate natural language description optimized for AI chatbot responses.
            Format: "Dịch vụ [name]. [Description]. Thuộc danh mục [category]. Giá từ [price_1] [currency]. [Duration/conditions]."

            🔥 CURRENCY DETECTION: Look for ₫, VND, VNĐ (Vietnamese) or $, USD (US Dollar).

            🔥 OTHER INFO: Extract service-specific details into other_info section.

            Include quantity as service capacity (default: 1 if not specified)."""

    def get_extraction_schema(self, data_type: str) -> Dict[str, Any]:
        if data_type == "products":
            return {
                "id": "number - Item ordering ID (1 to total items in this file only, database will auto-increment)",
                "name": "string - Product name (REQUIRED)",
                "prices": {
                    "price_1": "number - Primary/Base price (REQUIRED)",
                    "price_2": "number - Alternative price (if available)",
                    "price_3": "number - Third price option (if available)",
                    "original_price": "number - Original price before discount (if applicable)",
                    "currency": "string - VND|USD (auto-detect from symbols or price range)",
                },
                "conditions": {
                    "condition_price_1": "string - Conditions for price_1 (quantity, size, package details, etc.)",
                    "condition_price_2": "string - Conditions for price_2 (if applicable)",
                    "condition_price_3": "string - Conditions for price_3 (if applicable)",
                },
                "category": "string - Main business category (e.g., cong_nghe, thuc_pham, dich_vu, ban_le)",
                "quantity": "number - Available quantity (default: 1 if not specified)",
                "description": "string - REQUIRED: Natural language description optimized for AI chatbot",
                "content_for_embedding": "string - REQUIRED: Natural language description optimized for AI chatbot (same as description)",
                "retrieval_context": "string - REQUIRED: Comprehensive context for RAG retrieval. Format: 'Sản phẩm [name] thuộc danh mục [category]. Mô tả: [description]. Giá gốc: [original_price] VND (nếu có). Giá chính: [price_1] [currency_1] - [condition_price_1]. Giá khác: [price_2] [currency_2] - [condition_price_2] (nếu có). Số lượng có sẵn: [quantity]. [Thông tin khác từ specifications, features, warranty nếu có].' Viết thành đoạn văn tự nhiên, dễ hiểu để chatbot có thể trả lời khách hàng.",
                "other_info": {
                    "🔥 NOTE": "Industry-specific information - extract what you can find",
                    "product_code": "string - Product code/SKU (OPTIONAL)",
                    "sku": "string - Stock keeping unit (OPTIONAL)",
                    "sub_category": "string - More specific category (OPTIONAL)",
                    "tax_info": "string - Tax information if mentioned (OPTIONAL)",
                    "specifications": {
                        "brand": "string - Brand name (OPTIONAL)",
                        "model": "string - Model number (OPTIONAL)",
                        "size": "string - Size information (OPTIONAL)",
                        "weight": "string - Weight information (OPTIONAL)",
                        "color": "string - Available colors (OPTIONAL)",
                        "material": "string - Material information (OPTIONAL)",
                    },
                    "features": ["array of key features (OPTIONAL)"],
                    "warranty": "string - Warranty information (OPTIONAL)",
                    "availability_info": "string - Stock status, availability (OPTIONAL)",
                    "shipping_info": "string - Shipping details (OPTIONAL)",
                },
            }
        else:  # services
            return {
                "id": "number - Item ordering ID (1 to total items)",
                "name": "string - Service name (REQUIRED)",
                "prices": {
                    "price_1": "number - Primary/Base price (REQUIRED for paid services, 0 for free)",
                    "price_2": "number - Alternative price (if available)",
                    "price_3": "number - Third price option (if available)",
                    "original_price": "number - Original price before discount (if applicable)",
                    "currency": "string - VND|USD (auto-detect from symbols or price range)",
                },
                "conditions": {
                    "condition_price_1": "string - Conditions for price_1 (duration, package details, etc.)",
                    "condition_price_2": "string - Conditions for price_2 (if applicable)",
                    "condition_price_3": "string - Conditions for price_3 (if applicable)",
                },
                "category": "string - Service category (e.g., tu_van, sua_chua, thiet_ke, dao_tao)",
                "quantity": "number - Service capacity/availability (default: 1 if not specified)",
                "description": "string - REQUIRED: Natural language description optimized for AI chatbot",
                "content_for_embedding": "string - REQUIRED: Natural language description optimized for AI chatbot (same as description)",
                "retrieval_context": "string - REQUIRED: Comprehensive context for RAG retrieval. Format: 'Dịch vụ [name] thuộc danh mục [category]. Mô tả: [description]. Giá: [price_1] [currency_1] - [condition_price_1]. Giá khác: [price_2] [currency_2] - [condition_price_2] (nếu có). Thời gian thực hiện: [duration]. Phương thức: [delivery_method]. [Thông tin khác từ service_details, requirements nếu có].' Viết thành đoạn văn tự nhiên, dễ hiểu để chatbot có thể trả lời khách hàng.",
                "other_info": {
                    "🔥 NOTE": "Service-specific information - extract what you can find",
                    "service_code": "string - Service code (OPTIONAL)",
                    "sku": "string - Service SKU (OPTIONAL)",
                    "sub_category": "string - More specific service category (OPTIONAL)",
                    "tax_info": "string - Tax information if mentioned (OPTIONAL)",
                    "service_details": {
                        "duration": "string - Service duration (OPTIONAL)",
                        "location": "string - Service location (OPTIONAL)",
                        "delivery_method": "string - onsite|remote|hybrid (OPTIONAL)",
                        "staff_required": "number - Number of staff (OPTIONAL)",
                        "equipment_needed": ["array of required equipment (OPTIONAL)"],
                    },
                    "booking_info": {
                        "advance_booking": "string - Advance booking requirements (OPTIONAL)",
                        "cancellation_policy": "string - Cancellation terms (OPTIONAL)",
                        "payment_methods": [
                            "array of accepted payment methods (OPTIONAL)"
                        ],
                        "operating_hours": "string - Service hours (OPTIONAL)",
                    },
                    "requirements": ["array of client requirements (OPTIONAL)"],
                    "includes": ["array of included items/services (OPTIONAL)"],
                    "excludes": ["array of excluded items (OPTIONAL)"],
                },
            }

    def get_validation_rules(self, data_type: str) -> Dict[str, Any]:
        base_rules = {
            "required_fields": ["name", "description"],
            "price_min": 0,
            "price_max": 999999999,
            "name_max_length": 200,
            "description_max_length": 2000,
        }

        if data_type == "products":
            base_rules["required_fields"].append("price")

        return base_rules

    def post_process(
        self, extracted_data: Dict[str, Any], data_type: str
    ) -> Dict[str, Any]:
        """Clean and standardize generic data"""
        items = extracted_data.get(data_type, [])

        for idx, item in enumerate(items):
            # Ensure price is numeric
            if data_type == "products" and "price" in item:
                if isinstance(item["price"], str):
                    try:
                        item["price"] = float(
                            item["price"].replace(",", "").replace(".", "")
                        )
                    except:
                        item["price"] = 0

            # Handle service pricing
            if data_type == "services":
                if item.get("price_type") == "free":
                    item["price_min"] = 0
                    item["price_max"] = 0
                elif "price_min" not in item:
                    item["price_min"] = item.get("price", 0)
                    item["price_max"] = item.get("price", 0)

            # Default values
            item.setdefault("currency", "VND")
            item.setdefault("availability", "available")
            item.setdefault("tags", [])

            # Generate SKU if missing
            if data_type == "products" and not item.get("sku"):
                item["sku"] = self.create_sku(item, idx)

            # Generate service code if missing
            if data_type == "services" and not item.get("service_code"):
                item["service_code"] = f"SVC-{idx+1:03d}"

            # Auto-generate tags
            if not item["tags"]:
                item["tags"] = self.generate_tags(item)

            # Set confidence score
            item.setdefault("confidence_score", 0.85)

        return extracted_data
