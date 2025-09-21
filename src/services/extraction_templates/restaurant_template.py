"""
Restaurant industry extraction template
Template extraction cho ngành nhà hàng
"""

from typing import Dict, Any, List
from .base_template import BaseExtractionTemplate


class RestaurantExtractionTemplate(BaseExtractionTemplate):
    """Restaurant menu and services extraction"""

    def _get_industry(self) -> str:
        return "restaurant"

    def get_system_prompt(self, data_type: str) -> str:
        if data_type == "products":
            return """Extract restaurant menu items with standardized pricing structure:

            🔥 CRITICAL PRICING EXTRACTION:
            For each menu item, extract ALL available price options as price_1, price_2, price_3:
            - price_1: Regular/standard size price (REQUIRED)
            - price_2: Large size or combo price (if available)
            - price_3: Family/sharing size price (if available)
            - original_price: Original price before discount (if mentioned)

            For each price, extract corresponding conditions:
            - condition_price_1: All conditions for price_1 (size, portion, includes, etc.)
            - condition_price_2: All conditions for price_2 (large size, extra items, etc.)
            - condition_price_3: All conditions for price_3 (family size, sharing portion, etc.)

            VIETNAMESE PRICING CONVERSION:
            - "450K" = 450000 VND
            - "25K" = 25000 VND
            - Numbers without K but >1000 are already VND

            🔥 MENU CATEGORIES:
            - Food: "mon_an" (pho, bun, com, nuong, chien, etc.)
            - Beverage: "thuc_uong" (tra, ca_phe, nuoc_ep, etc.)
            - Combo: "combo" (set meals, family packages)

            🔥 DESCRIPTION: Generate natural language description for AI chatbot.
            Format: "Món [name]. [Description with ingredients]. Thuộc danh mục [category]. Giá từ [price_1] VND. [Special notes]."

            🔥 RETRIEVAL_CONTEXT: Create a comprehensive, natural Vietnamese paragraph combining all important information for customer service chatbot responses. Format example:
            "Món Phở Tái thuộc loại món ăn. Mô tả: Phở bò truyền thống với thịt bò tái mềm, bánh phở dai, nước dùng đậm đà từ xương hầm 12 tiếng. Size thường: 65,000 VND - phần cơ bản đủ no. Size lớn: 85,000 VND - nhiều thịt và phở hơn. Thời gian chế biến 5-7 phút, độ cay nhẹ, phù hợp cho bữa sáng và bữa trưa."

            Example: "Món Phở Tái. Món phở bò truyền thống với thịt bò tái mềm, nước dùng đậm đà. Thuộc danh mục mon_an. Giá từ 65000 VND. Món đặc trưng nhà hàng."

            🔥 OTHER INFO: Extract Vietnamese cuisine details into other_info section.

            Include quantity (default: 1 if not specified)."""
        else:  # services
            return """Extract restaurant services and create AI-optimized descriptions:

            IMPORTANT: For each service, you MUST include a "content_for_embedding" field that contains a natural, conversational description.

            Extract:
            - Delivery and takeaway options with zones and fees
            - Catering services and minimum orders
            - Private dining rooms and event hosting
            - Table service and reservation policies
            - **content_for_embedding**: Natural language description for AI chatbot

            CONTENT_FOR_EMBEDDING FORMAT:
            "Dịch vụ [name]. [Description]. [Pricing info]. [Operating hours or conditions]."

            Example: "Dịch vụ giao hàng tận nơi. Giao hàng trong bán kính 5km với phí ship 20,000 VND. Thời gian giao hàng từ 30-45 phút."

            Include Vietnamese and English names, pricing structures, and terms."""

    def get_extraction_schema(self, data_type: str) -> Dict[str, Any]:
        if data_type == "products":
            return {
                "id": "number - Item ordering ID (1 to total items)",
                "name": "string - Menu item name (REQUIRED)",
                "prices": {
                    "price_1": "number - Regular/standard size price (REQUIRED)",
                    "price_2": "number - Large size or combo price (if available)",
                    "price_3": "number - Family/sharing size price (if available)",
                    "original_price": "number - Original price before discount (if applicable)",
                    "currency": "string - VND|USD (default VND for Vietnamese restaurants)",
                },
                "conditions": {
                    "condition_price_1": "string - Conditions for price_1 (size, portion, includes, etc.)",
                    "condition_price_2": "string - Conditions for price_2 (large size, extra items, etc.)",
                    "condition_price_3": "string - Conditions for price_3 (family size, sharing portion, etc.)",
                },
                "category": "string - For menu: mon_an|thuc_uong|combo",
                "quantity": "number - Available quantity (default: 1 if not specified)",
                "description": "string - REQUIRED: Natural language description optimized for AI chatbot",
                "content_for_embedding": "string - REQUIRED: Natural language description optimized for AI chatbot (same as description)",
                "retrieval_context": "string - REQUIRED: Comprehensive context for RAG retrieval. Format: 'Món [name] thuộc loại [category]. Mô tả: [description]. Giá gốc: [original_price] VND (nếu có). Size thường: [price_1] [currency_1] - [condition_price_1]. Size lớn: [price_2] [currency_2] - [condition_price_2] (nếu có). Size gia đình: [price_3] [currency_3] - [condition_price_3] (nếu có). [Thông tin khác từ other_info nếu có như nguyên liệu, độ cay, thời gian chế biến].' Viết thành đoạn văn tự nhiên, dễ hiểu để chatbot có thể trả lời khách hàng.",
                "other_info": {
                    "🔥 NOTE": "Restaurant-specific information - extract what you can find",
                    "product_code": "string - Menu item code (OPTIONAL)",
                    "sku": "string - SKU code (OPTIONAL)",
                    "sub_category": "string - More specific category (e.g., pho, bun, com, banh_mi) (OPTIONAL)",
                    "tax_info": "string - Tax information if mentioned (OPTIONAL)",
                    "dish_details": {
                        "cuisine_type": "string - vietnamese|chinese|japanese|western|fusion (OPTIONAL)",
                        "main_ingredients": ["array of main ingredients (OPTIONAL)"],
                        "portion_size": "string - small|medium|large (OPTIONAL)",
                        "preparation_time": "number - minutes (OPTIONAL)",
                        "spice_level": "string - none|mild|medium|hot|extra_hot (OPTIONAL)",
                        "temperature": "string - hot|cold|room_temp (OPTIONAL)",
                    },
                    "dietary_options": {
                        "vegetarian": "boolean (OPTIONAL)",
                        "vegan": "boolean (OPTIONAL)",
                        "gluten_free": "boolean (OPTIONAL)",
                        "halal": "boolean (OPTIONAL)",
                    },
                    "serving_info": {
                        "accompaniments": ["array of side items (OPTIONAL)"],
                        "recommended_time": [
                            "array - breakfast|lunch|dinner (OPTIONAL)"
                        ],
                        "chef_special": "boolean (OPTIONAL)",
                        "bestseller": "boolean (OPTIONAL)",
                    },
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
                    "currency": "string - VND|USD (default VND for Vietnamese restaurants)",
                },
                "conditions": {
                    "condition_price_1": "string - Conditions for price_1 (delivery area, minimum order, etc.)",
                    "condition_price_2": "string - Conditions for price_2 (if applicable)",
                    "condition_price_3": "string - Conditions for price_3 (if applicable)",
                },
                "category": "string - Service category (e.g., giao_hang, phuc_vu_ban, to_chuc_su_kien)",
                "quantity": "number - Service capacity/availability (default: 1 if not specified)",
                "description": "string - REQUIRED: Natural language description optimized for AI chatbot",
                "content_for_embedding": "string - REQUIRED: Natural language description optimized for AI chatbot (same as description)",
                "retrieval_context": "string - REQUIRED: Comprehensive context for RAG retrieval. Format: 'Dịch vụ [name] thuộc loại [category]. Mô tả: [description]. Giá: [price_1] [currency_1] - [condition_price_1]. Giá khác: [price_2] [currency_2] - [condition_price_2] (nếu có). [Thông tin từ service_details như khu vực giao hàng, thời gian, yêu cầu đặt bàn].' Viết thành đoạn văn tự nhiên, dễ hiểu để chatbot có thể trả lời khách hàng.",
                "other_info": {
                    "🔥 NOTE": "Restaurant service-specific information - extract what you can find",
                    "service_code": "string - Service code (OPTIONAL)",
                    "sku": "string - Service SKU (OPTIONAL)",
                    "sub_category": "string - More specific service category (OPTIONAL)",
                    "tax_info": "string - Tax information if mentioned (OPTIONAL)",
                    "service_details": {
                        "minimum_order_amount": "number - for delivery/catering (OPTIONAL)",
                        "delivery_zones": ["array of areas/districts (OPTIONAL)"],
                        "delivery_time": "string - estimated delivery time (OPTIONAL)",
                        "table_capacity": {
                            "min_guests": "number (OPTIONAL)",
                            "max_guests": "number (OPTIONAL)",
                        },
                    },
                    "booking_info": {
                        "reservation_required": "boolean (OPTIONAL)",
                        "advance_booking_hours": "number (OPTIONAL)",
                        "cancellation_policy": "string (OPTIONAL)",
                        "payment_methods": ["array - cash|card|transfer (OPTIONAL)"],
                        "operating_hours": "string - Service hours (OPTIONAL)",
                    },
                    "additional_features": {
                        "ambiance": "string - casual|fine_dining|family_friendly (OPTIONAL)",
                        "live_music": "boolean (OPTIONAL)",
                        "private_room": "boolean (OPTIONAL)",
                        "parking": "boolean (OPTIONAL)",
                    },
                },
            }

    def get_validation_rules(self, data_type: str) -> Dict[str, Any]:
        base_rules = {
            "required_fields": [
                "name",
                "category",
                "price" if data_type == "products" else "price_type",
            ],
            "price_min": (
                10000 if data_type == "products" else 0
            ),  # 10k VND minimum for dishes
            "price_max": 10000000,  # 10M VND maximum
        }

        if data_type == "products":
            base_rules["valid_categories"] = [
                "appetizer",
                "soup",
                "main_course",
                "dessert",
                "beverage",
                "special",
            ]
        else:
            base_rules["valid_categories"] = [
                "dine_in",
                "delivery",
                "catering",
                "event",
                "takeaway",
            ]

        return base_rules

    def post_process(
        self, extracted_data: Dict[str, Any], data_type: str
    ) -> Dict[str, Any]:
        """Post-process restaurant data"""
        items = extracted_data.get(data_type, [])

        for idx, item in enumerate(items):
            # Normalize Vietnamese text
            if item.get("name"):
                item["name"] = self._normalize_vietnamese(item["name"])

            # Auto-categorize dishes if missing sub_category
            if data_type == "products" and not item.get("sub_category"):
                item["sub_category"] = self._guess_dish_subcategory(item["name"])

            # Ensure price is in correct range for products and convert K notation
            if data_type == "products":
                price = item.get("price", 0)
                if isinstance(price, str):
                    # Handle string prices like "450K", "25K"
                    price_str = price.strip().upper()
                    if price_str.endswith("K"):
                        try:
                            price = float(price_str[:-1]) * 1000
                            item["price"] = int(price)
                        except ValueError:
                            item["price"] = 0
                    else:
                        try:
                            item["price"] = float(price_str)
                        except ValueError:
                            item["price"] = 0
                elif price < 10000 and price > 0:
                    # If number is small but positive, likely in thousands
                    item["price"] = price * 1000

            # Set default currency
            item["currency"] = "VND"

            # Generate SKU/service code
            if data_type == "products" and not item.get("sku"):
                item["sku"] = self.create_sku(item, idx)
            elif data_type == "services" and not item.get("service_code"):
                item["service_code"] = f"REST-SVC-{idx+1:03d}"

            # Set defaults for industry_data
            if "industry_data" not in item:
                item["industry_data"] = {}

            if data_type == "products":
                dish_details = item["industry_data"].setdefault("dish_details", {})
                dish_details.setdefault("cuisine_type", "vietnamese")
                dish_details.setdefault("spice_level", "mild")

                # Set dietary defaults
                dietary = item["industry_data"].setdefault("dietary_options", {})
                dietary.setdefault("vegetarian", False)
                dietary.setdefault("vegan", False)
                dietary.setdefault("halal", True)  # Default halal for Vietnamese food

            # Generate tags
            item["tags"] = list(
                set(
                    item.get("tags", [])
                    + self._generate_restaurant_tags(item, data_type)
                )
            )

            # Set confidence score
            item.setdefault("confidence_score", 0.9)

        return extracted_data

    def _normalize_vietnamese(self, text: str) -> str:
        """Normalize Vietnamese text"""
        return text.strip().title()

    def _guess_dish_subcategory(self, name: str) -> str:
        """Guess subcategory from dish name"""
        name_lower = name.lower()

        # Vietnamese dish patterns
        if "phở" in name_lower:
            return "pho"
        elif "bún" in name_lower:
            return "bun"
        elif "cơm" in name_lower:
            return "com"
        elif "bánh mì" in name_lower:
            return "banh_mi"
        elif "chả giò" in name_lower or "nem" in name_lower:
            return "cha_gio"
        elif "gỏi" in name_lower or "nộm" in name_lower:
            return "salad"
        elif "canh" in name_lower or "súp" in name_lower:
            return "soup"
        elif "nướng" in name_lower:
            return "grilled"
        elif "xào" in name_lower:
            return "stir_fried"
        else:
            return "other"

    def _generate_restaurant_tags(
        self, item: Dict[str, Any], data_type: str
    ) -> List[str]:
        """Generate restaurant-specific tags"""
        tags = []

        # Category tags
        if item.get("category"):
            tags.append(item["category"])

        if data_type == "products":
            # Cuisine type tags
            cuisine = (
                item.get("industry_data", {})
                .get("dish_details", {})
                .get("cuisine_type")
            )
            if cuisine:
                tags.append(cuisine)

            # Dietary tags
            dietary = item.get("industry_data", {}).get("dietary_options", {})
            if dietary.get("vegetarian"):
                tags.append("vegetarian")
            if dietary.get("vegan"):
                tags.append("vegan")
            if dietary.get("halal"):
                tags.append("halal")

            # Special tags
            serving = item.get("industry_data", {}).get("serving_info", {})
            if serving.get("chef_special"):
                tags.append("chef_special")
            if serving.get("bestseller"):
                tags.append("bestseller")

        else:  # services
            # Service type tags
            if item.get("price_type") == "free":
                tags.append("free")

            service_type = (
                item.get("industry_data", {})
                .get("service_details", {})
                .get("service_type")
            )
            if service_type:
                tags.append(service_type)

        return tags
