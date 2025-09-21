"""
Hotel industry extraction template
Template extraction cho ngành khách sạn
"""

from typing import Dict, Any, List
from .base_template import BaseExtractionTemplate
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class HotelExtractionTemplate(BaseExtractionTemplate):
    """Hotel rooms, dining and services extraction"""

    def _get_industry(self) -> str:
        return "hotel"

    def get_system_prompt(self, data_type: str) -> str:
        if data_type == "products":
            return """Extract hotel products with standardized pricing structure:

            🔥 CRITICAL PRICING EXTRACTION:
            For each product, extract ALL available price options as price_1, price_2, price_3:
            - price_1: Primary/most common price (REQUIRED)
            - price_2: Second price option if available (e.g., different occupancy, different conditions)
            - price_3: Third price option if available
            - original_price: Original price before discount (if mentioned)

            For each price, extract corresponding conditions:
            - condition_price_1: All conditions for price_1 (includes, cancellation, payment, occupancy)
            - condition_price_2: All conditions for price_2
            - condition_price_3: All conditions for price_3
            - occupancy_price_X: Number of people each price applies to

            EXAMPLE FROM DATA:
            "Grand Family Room" with 3 offers should become:
            - price_1: 2143918 (4 người), condition_price_1: "Bao gồm bữa sáng | Hủy miễn phí | Thanh toán ngay", occupancy_price_1: 4
            - price_2: 2300949 (6 người), condition_price_2: "Bao gồm bữa sáng | Hủy miễn phí | Thanh toán sau", occupancy_price_2: 6
            - price_3: 2347549 (2 người), condition_price_3: "Bao gồm bữa sáng | Hủy miễn phí | Thanh toán sau", occupancy_price_3: 2
            - original_price: 3106493 (before discount)

            🔥 PRODUCT CATEGORIES:
            - Rooms: standard|superior|deluxe|suite|family|apartment
            - Dining: food|beverage|combo

            🔥 DESCRIPTION: Generate natural language description optimized for AI chatbot responses.

            🔥 RETRIEVAL_CONTEXT: Create a comprehensive, natural Vietnamese paragraph combining all important information for customer service chatbot responses. Format example:
            "Phòng Grand Family Room là phòng gia đình cao cấp với diện tích 45m2, phù hợp cho 4-6 người. Giá gốc 3,106,493 VND. Lựa chọn 1: 2,143,918 VND cho 4 người bao gồm bữa sáng, hủy miễn phí, thanh toán ngay. Lựa chọn 2: 2,300,949 VND cho 6 người bao gồm bữa sáng, hủy miễn phí, thanh toán sau. Lựa chọn 3: 2,347,549 VND cho 2 người bao gồm bữa sáng, hủy miễn phí, thanh toán sau. Phòng có view biển, wifi miễn phí, minibar, và ban công riêng."

            🔥 CURRENCY DETECTION: Look for ₫, VND, VNĐ (Vietnamese) or $, USD (US Dollar). Default VND for prices ≥10,000.

            🔥 OTHER INFO: Extract hotel-specific details like room size, amenities, view type, etc. into other_info section.

            Include quantity (default: 1 if not specified)."""
        else:  # services
            return """Extract hotel services with ID field for ordering (1 to total items) including:

            🔥 RETRIEVAL_CONTEXT: Create a comprehensive, natural Vietnamese paragraph for each service combining all important information for customer service chatbot responses. Format example:
            "Dịch vụ Spa massage thư giãn toàn thân (mã: SPA-001) là dịch vụ trả phí với giá từ 800,000 đến 1,500,000 VND tùy theo loại massage. Thời gian 60-90 phút. Hoạt động từ 9:00-21:00 hàng ngày tại tầng 3. Cần đặt trước 2 tiếng, chấp nhận thanh toán tiền mặt và thẻ tín dụng."

            1. FREE/COMPLIMENTARY SERVICES (price_type: "free", price_min/max: 0)
               - Categories: fitness, transport, business, entertainment, wellness, guest_service, food_beverage
               - Comprehensive structure: connectivity (WiFi speed, business center), wellness (gym, pool, sauna), transport (shuttle destinations/schedule, parking), guest services (concierge, luggage storage), food_beverage (welcome drink, afternoon tea), entertainment (live music, cultural shows)
               - Required: service_details (operating hours, location), service_policies (age restrictions, dress code, booking requirements)

            2. PAID/PREMIUM SERVICES (price_type: fixed|hourly|package|per_person|tiered)
               - Categories: spa, conference, event, tour, business, entertainment, transportation
               - Spa: treatment types, therapist preferences, couple treatments, room types
               - Events: venue types, capacities (theater/cocktail/classroom/banquet), included equipment, catering options
               - Tours: tour types, destinations, group sizes, included services (guide, transport, meals)
               - Required: pricing_structure, service_details (hours, days, seasonal availability), booking_requirements (advance hours, cancellation policy, deposit, payment methods)

            🔥 CRITICAL: Generate content_for_embedding field for each service - this is a natural language description optimized for AI chatbot responses.

            CONTENT_FOR_EMBEDDING FORMAT:
            - For free services: "Dịch vụ [name]. [Description with key features]. Miễn phí cho khách lưu trú. [Operating hours and location if available]."
            - For paid services: "Dịch vụ [name]. [Description with features]. Thuộc danh mục [category]. Giá từ [price_min] đến [price_max] [currency]. [Duration and booking info if available]."

            🔥 IMPORTANT: ALL industry_data fields are OPTIONAL - extract what you can find, missing data won't cause failures.

            CURRENCY DETECTION RULES:
            - Look for explicit currency symbols/text in file: $, USD, đ, VNĐ, VND
            - If price ≥ 10,000: likely VND (Vietnamese Dong)
            - If price < 3,000: likely USD (US Dollar)
            - Vietnamese language file with no currency indicators + price ≥ 10,000: default VND
            - English language file with no currency indicators + price < 3,000: default USD
            - Always prioritize explicit currency mentions in the source text

            Set duration_minutes=null for free services. Include raw_data with extracted_text for verification."""

    def get_extraction_schema(self, data_type: str) -> Dict[str, Any]:
        if data_type == "products":
            return {
                "id": "number - Item ordering ID (1 to total items in this file only, database will auto-increment)",
                "name": "string - Room/Product name (REQUIRED)",
                "prices": {
                    "price_1": "number - Primary/Base price (REQUIRED)",
                    "price_2": "number - Alternative price (if available)",
                    "price_3": "number - Third price option (if available)",
                    "original_price": "number - Original price before discount (if applicable)",
                    "currency": "string - VND|USD (smart detection: look for symbols $,đ,VNĐ in text, or price analysis: ≥10k=VND, <3k=USD)",
                },
                "conditions": {
                    "condition_price_1": "string - Conditions for price_1 (e.g., 'Bao gồm bữa sáng | Hủy miễn phí | Thanh toán ngay')",
                    "condition_price_2": "string - Conditions for price_2 (if applicable)",
                    "condition_price_3": "string - Conditions for price_3 (if applicable)",
                    "occupancy_price_1": "number - Number of people for price_1",
                    "occupancy_price_2": "number - Number of people for price_2",
                    "occupancy_price_3": "number - Number of people for price_3",
                },
                "category": "string - For rooms: standard|superior|deluxe|suite|family|apartment. For dining: food|beverage|combo",
                "quantity": "number - Available quantity (default: 1 if not specified)",
                "description": "string - REQUIRED: Natural language description optimized for AI chatbot",
                "content_for_embedding": "string - REQUIRED: Natural language description optimized for AI chatbot (same as description)",
                "retrieval_context": "string - REQUIRED: Comprehensive context for RAG retrieval. Format: 'Tên: [name]. Loại: [category]. Mô tả: [description]. Giá gốc: [original_price] VND (nếu có). Lựa chọn 1: [price_1] [currency_1] - [condition_price_1]. Lựa chọn 2: [price_2] [currency_2] - [condition_price_2] (nếu có). Lựa chọn 3: [price_3] [currency_3] - [condition_price_3] (nếu có). Số lượng: [quantity]. [Thông tin khác từ other_info nếu có].' Viết thành đoạn văn tự nhiên, dễ hiểu để chatbot có thể trả lời khách hàng.",
                "other_info": {
                    "🔥 NOTE": "Hotel-specific information - extract what you can find, missing data won't cause failures",
                    "product_code": "string - Room/Product code (OPTIONAL)",
                    "sku": "string - SKU code (OPTIONAL)",
                    "sub_category": "string - More specific category (e.g., seaview_room, family_room, single_room) (OPTIONAL)",
                    "tax_info": "string - Tax information if mentioned (OPTIONAL)",
                    "room_specifications": {
                        "size_sqm": "number - Room area in square meters (OPTIONAL)",
                        "max_occupancy": {
                            "adults": "number - Maximum adult guests (OPTIONAL)",
                            "children": "number - Maximum children (OPTIONAL)",
                        },
                        "bed_configuration": "string - king|queen|twin|2_singles|sofa_bed (OPTIONAL)",
                        "view_type": "string - city_view|sea_view|ocean_view|mountain_view|garden_view|pool_view|river_view (OPTIONAL)",
                        "floor_level": "string - low_floor|mid_floor|high_floor|ground_floor (OPTIONAL)",
                        "balcony": "boolean - Private balcony (OPTIONAL)",
                        "amenities": {
                            "air_conditioning": "boolean (OPTIONAL)",
                            "minibar": "boolean (OPTIONAL)",
                            "wifi": "boolean (OPTIONAL)",
                            "tv": "boolean (OPTIONAL)",
                            "safe": "boolean (OPTIONAL)",
                        },
                    },
                    "dining_info": {
                        "cuisine_type": "string - vietnamese|asian|western|international (OPTIONAL)",
                        "meal_type": "string - breakfast|lunch|dinner|snack (OPTIONAL)",
                        "portion_size": "string - serving size description (OPTIONAL)",
                        "dietary_restrictions": [
                            "array of dietary restrictions like vegetarian, halal, etc (OPTIONAL)"
                        ],
                    },
                    "booking_info": {
                        "cancellation_policy": "string - cancellation terms (OPTIONAL)",
                        "payment_methods": [
                            "array of accepted payment methods (OPTIONAL)"
                        ],
                        "advance_booking": "string - advance booking requirements (OPTIONAL)",
                    },
                },
            }
        else:  # services
            return {
                "id": "number - Item ordering ID (1 to total items)",
                "name": "string - Service name (REQUIRED)",
                "content_for_embedding": "string - REQUIRED: Natural language description optimized for AI chatbot",
                "retrieval_context": "string - REQUIRED: Comprehensive context for RAG retrieval. Format: 'Tên dịch vụ: [name]. Loại: [category]. Mã dịch vụ: [service_code]. Loại giá: [price_type]. Giá: từ [price_min] đến [price_max] [currency]. Thời gian: [duration_minutes] phút. Mô tả: [content_for_embedding]. [Thông tin chi tiết từ industry_data nếu có].' Viết thành đoạn văn tự nhiên, dễ hiểu để chatbot có thể trả lời khách hàng.",
                "service_code": "string - Service code (REQUIRED)",
                "category": "string - For free: fitness|transport|business|entertainment|wellness|guest_service|food_beverage. For paid: spa|conference|event|tour|business|entertainment|transportation",
                "price_type": "string - free for complimentary services, or fixed|hourly|package|per_person|tiered for paid services",
                "price_min": "number - Minimum price (0 for free services)",
                "price_max": "number - Maximum price (0 for free services)",
                "currency": "string - VND|USD (smart detection: look for symbols $,đ,VNĐ in text, or use price analysis: ≥10k=VND, <3k=USD)",
                "duration_minutes": "number - Service duration (null for free services, required for most paid services)",
                "industry_data": {
                    "🔥 NOTE": "ALL FIELDS BELOW ARE OPTIONAL - extract what you can find, missing data won't cause failures",
                    # Free/Complimentary Services Schema (ALL OPTIONAL)
                    "complimentary_services": {
                        "connectivity": {
                            "wifi": "boolean (OPTIONAL)",
                            "wifi_speed_mbps": "number - Internet speed (OPTIONAL)",
                            "business_center": "boolean (OPTIONAL)",
                            "internet_kiosk": "boolean (OPTIONAL)",
                        },
                        "business": {
                            "business_center": "boolean (OPTIONAL)",
                            "printing_limit": "number - Pages per day/stay (OPTIONAL)",
                            "fax_service": "boolean (OPTIONAL)",
                            "meeting_room_access": "boolean (OPTIONAL)",
                        },
                        "wellness": {
                            "gym_access": "boolean (OPTIONAL)",
                            "swimming_pool": "boolean (OPTIONAL)",
                            "sauna": "boolean (OPTIONAL)",
                            "steam_room": "boolean (OPTIONAL)",
                            "kids_club": "boolean (OPTIONAL)",
                            "playground": "boolean (OPTIONAL)",
                        },
                        "transport": {
                            "shuttle_service": "boolean (OPTIONAL)",
                            "shuttle_destinations": [
                                "array like airport, city_center, beach, shopping_mall (OPTIONAL)"
                            ],
                            "shuttle_schedule": "string - every_30_mins|hourly|on_demand (OPTIONAL)",
                            "parking": "boolean (OPTIONAL)",
                            "valet_parking": "boolean (OPTIONAL)",
                        },
                        "guest_services": {
                            "concierge": "boolean (OPTIONAL)",
                            "luggage_storage": "boolean (OPTIONAL)",
                            "wake_up_calls": "boolean (OPTIONAL)",
                            "newspaper_delivery": "boolean (OPTIONAL)",
                            "tour_information": "boolean (OPTIONAL)",
                            "ticket_booking": "boolean (OPTIONAL)",
                        },
                        "food_beverage": {
                            "welcome_drink": "boolean (OPTIONAL)",
                            "afternoon_tea": "boolean (OPTIONAL)",
                            "happy_hour": "boolean (OPTIONAL)",
                            "coffee_tea_lobby": "boolean (OPTIONAL)",
                            "fruit_basket": "boolean (OPTIONAL)",
                        },
                        "entertainment": {
                            "live_music": "boolean (OPTIONAL)",
                            "cultural_shows": "boolean (OPTIONAL)",
                            "game_room": "boolean (OPTIONAL)",
                            "library": "boolean (OPTIONAL)",
                            "movie_nights": "boolean (OPTIONAL)",
                        },
                        "amenities": {
                            "pool_towel_service": "boolean (OPTIONAL)",
                            "umbrella_service": "boolean (OPTIONAL)",
                            "safety_deposit_box": "boolean (OPTIONAL)",
                            "ice_machine": "boolean (OPTIONAL)",
                        },
                    },
                    # Paid/Premium Services Schema (ALL OPTIONAL)
                    "spa_services": {
                        "treatment_type": "string - massage|facial|body_wrap|body_scrub|manicure|pedicure|hair_treatment|aromatherapy (OPTIONAL)",
                        "therapist_gender_preference": "string - male|female|any|same_gender (OPTIONAL)",
                        "couple_treatment_available": "boolean (OPTIONAL)",
                        "products_brand": "string - organic|luxury_brand|local_herbs (OPTIONAL)",
                        "organic_products": "boolean (OPTIONAL)",
                        "treatment_room_type": "string - private|couples|group (OPTIONAL)",
                    },
                    "event_services": {
                        "venue_type": "string - ballroom|conference_room|boardroom|garden|rooftop|poolside|beach (OPTIONAL)",
                        "capacity": {
                            "theater_style": "number - Theater seating capacity (OPTIONAL)",
                            "cocktail_style": "number - Standing cocktail capacity (OPTIONAL)",
                            "classroom_style": "number - Classroom seating (OPTIONAL)",
                            "banquet_style": "number - Seated dinner capacity (OPTIONAL)",
                        },
                        "includes": {
                            "event_coordinator": "boolean (OPTIONAL)",
                            "audio_visual_equipment": "boolean (OPTIONAL)",
                            "basic_lighting": "boolean (OPTIONAL)",
                            "microphone_system": "boolean (OPTIONAL)",
                        },
                        "catering": {
                            "style_options": [
                                "array like buffet, plated, cocktail, family_style, stations (OPTIONAL)"
                            ],
                            "dietary_accommodations": "boolean (OPTIONAL)",
                            "alcohol_license": "boolean (OPTIONAL)",
                        },
                    },
                    "tour_services": {
                        "tour_type": "string - cultural|adventure|culinary|shopping|nightlife|nature|historical|luxury (OPTIONAL)",
                        "destination": "string - Ho Chi Minh City|Cu Chi Tunnels|Mekong Delta (OPTIONAL)",
                        "group_size": {
                            "minimum": "number - Minimum participants (OPTIONAL)",
                            "maximum": "number - Maximum participants (OPTIONAL)",
                        },
                        "private_tour_available": "boolean (OPTIONAL)",
                        "includes": {
                            "tour_guide": "boolean (OPTIONAL)",
                            "transportation": "boolean (OPTIONAL)",
                            "entrance_fees": "boolean (OPTIONAL)",
                            "meals": "boolean (OPTIONAL)",
                            "hotel_pickup": "boolean (OPTIONAL)",
                        },
                    },
                    "business_services": {
                        "secretarial": "boolean (OPTIONAL)",
                        "translation": "boolean (OPTIONAL)",
                        "equipment_rental": "boolean (OPTIONAL)",
                        "video_conferencing": "boolean (OPTIONAL)",
                        "document_printing": "boolean (OPTIONAL)",
                        "courier_service": "boolean (OPTIONAL)",
                    },
                    "pricing_structure": {
                        "price_per_person": "number - For group services (OPTIONAL)",
                        "price_per_hour": "number - For hourly services (OPTIONAL)",
                        "package_price": "number - For package deals (OPTIONAL)",
                        "group_discount_percentage": "number - Discount for groups (%) (OPTIONAL)",
                        "cancellation_fee": "number - Fee for cancellations (OPTIONAL)",
                    },
                    "service_details": {
                        "operating_hours": "string - 24/7|06:00-22:00|pool_hours for free, 09:00-18:00|24/7|by_appointment for paid (OPTIONAL)",
                        "location": "string - lobby|pool_area|gym|all_areas for free services (OPTIONAL)",
                        "days_available": [
                            "array like monday, tuesday, wednesday, thursday, friday, saturday, sunday (OPTIONAL)"
                        ],
                        "seasonal_availability": "boolean - Only available certain seasons (OPTIONAL)",
                        "weather_dependent": "boolean - Affected by weather conditions (OPTIONAL)",
                    },
                    "service_policies": {
                        "age_restrictions": "string - none|adults_only|16_plus|18_plus|children_welcome (OPTIONAL)",
                        "dress_code": "string - none|casual|smart_casual|formal for free, casual|smart_casual|formal|swimwear for paid (OPTIONAL)",
                        "advance_booking_required": "boolean (OPTIONAL)",
                        "time_limits": "string - 2_hours_max|no_limit|subject_to_availability (OPTIONAL)",
                    },
                    "booking_requirements": {
                        "advance_booking_hours": "number - Hours notice required (OPTIONAL)",
                        "cancellation_policy": "string - 24_hours|48_hours|72_hours|1_week|non_refundable (OPTIONAL)",
                        "deposit_percentage": "number - Required deposit (%) (OPTIONAL)",
                        "payment_methods": [
                            "array like cash, credit_card, bank_transfer (OPTIONAL)"
                        ],
                    },
                    "add_on_services": {
                        "photography": "boolean (OPTIONAL)",
                        "floral_arrangements": "boolean (OPTIONAL)",
                        "special_decorations": "boolean (OPTIONAL)",
                        "live_entertainment": "boolean (OPTIONAL)",
                        "additional_equipment": "boolean (OPTIONAL)",
                    },
                    "service_type": "string - complimentary for free services, premium for paid services (AUTO-SET)",
                    "pricing_model": "string - free for complimentary services (AUTO-SET)",
                },
                "raw_data": {
                    "extracted_text": "string - Raw text content about this service (HIGHLY RECOMMENDED)",
                    "confidence_score": "number 0.0-1.0 - AI confidence in extraction",
                    "extraction_notes": "string - AI notes about extraction challenges",
                    "original_format": "string - Original data format/structure",
                    "file_section": "string - Which section of file this was extracted from",
                },
            }

    def get_validation_rules(self, data_type: str) -> Dict[str, Any]:
        base_rules = {
            "required_fields": ["id", "name"],
            "price_min": 0,
            "price_max": 50000000,  # 50M VND maximum
        }

        if data_type == "products":
            base_rules["required_fields"].append("price")
            base_rules["valid_room_categories"] = [
                "standard",
                "superior",
                "deluxe",
                "suite",
                "junior_suite",
                "executive_suite",
                "presidential_suite",
                "villa",
                "penthouse",
            ]
            base_rules["valid_dining_categories"] = [
                "appetizer",
                "main_course",
                "dessert",
                "beverage",
                "soup",
                "salad",
                "side_dish",
            ]
        else:
            base_rules["required_fields"].extend(["service_code", "price_type"])
            base_rules["valid_free_service_categories"] = [
                "fitness",
                "transport",
                "business",
                "entertainment",
                "wellness",
                "guest_service",
                "food_beverage",
            ]
            base_rules["valid_paid_service_categories"] = [
                "spa",
                "conference",
                "event",
                "tour",
                "business",
                "entertainment",
                "transportation",
            ]

        return base_rules

    def post_process(
        self, extracted_data: Dict[str, Any], data_type: str
    ) -> Dict[str, Any]:
        """Post-process hotel data according to backend schema requirements"""
        items = extracted_data.get(data_type, [])

        for idx, item in enumerate(items):
            # REQUIRED: Add ID field for item ordering (1 to total items)
            if not item.get("id"):
                item["id"] = idx + 1

            # REQUIRED: Set smart currency detection based on file content and price analysis
            if not item.get("currency"):
                # Smart currency detection logic
                price = item.get("price", 0)
                if price >= 10000:
                    # High price likely VND
                    item["currency"] = "VND"
                elif price > 0 and price < 3000:
                    # Low price likely USD
                    item["currency"] = "USD"
                else:
                    # Fallback to VND for Vietnamese context
                    item["currency"] = "VND"

            # Generate codes if missing
            if data_type == "products" and not item.get("sku"):
                # Enhanced SKU generation based on category
                if item.get("category") in [
                    "standard",
                    "superior",
                    "deluxe",
                    "suite",
                    "junior_suite",
                    "executive_suite",
                    "presidential_suite",
                    "villa",
                    "penthouse",
                ]:
                    category_code = f"ROOM-{item.get('category', 'STD')[:3].upper()}"
                else:
                    category_code = f"DISH-{item.get('category', 'ITEM')[:4].upper()}"
                item["sku"] = f"{category_code}-{idx+1:03d}"
            elif data_type == "services" and not item.get("service_code"):
                service_type = "FREE" if item.get("price_type") == "free" else "PAID"
                category_code = item.get("category", "SVC")[:3].upper()
                item["service_code"] = f"{category_code}-{service_type}-{idx+1:03d}"

            # Set price_unit based on product type
            if data_type == "products":
                if item.get("category") in [
                    "standard",
                    "superior",
                    "deluxe",
                    "suite",
                    "junior_suite",
                    "executive_suite",
                    "presidential_suite",
                    "villa",
                    "penthouse",
                ]:
                    item["price_unit"] = "per_night"
                else:  # dining products
                    item["price_unit"] = "per_portion"

            # Initialize industry_data if missing
            if "industry_data" not in item:
                item["industry_data"] = {}

            if data_type == "products":
                # Set product_type based on category
                if item.get("category") in [
                    "standard",
                    "superior",
                    "deluxe",
                    "suite",
                    "junior_suite",
                    "executive_suite",
                    "presidential_suite",
                    "villa",
                    "penthouse",
                ]:
                    item["industry_data"]["product_type"] = "room"

                    # Default room specifications
                    room_specs = item["industry_data"].setdefault(
                        "room_specifications", {}
                    )
                    if not room_specs.get("max_occupancy"):
                        room_specs["max_occupancy"] = {"adults": 2, "children": 1}
                    room_specs.setdefault("bathroom_type", "ensuite")

                    # Default room amenities structure
                    amenities = item["industry_data"].setdefault("room_amenities", {})
                    amenities.setdefault("comfort", {})
                    amenities.setdefault("entertainment", {})
                    amenities.setdefault("connectivity", {})
                    amenities.setdefault("safety", {})
                    amenities.setdefault("luxury", {})

                    # Default pricing structure
                    pricing = item["industry_data"].setdefault("pricing_structure", {})
                    pricing.setdefault("base_rate", item.get("price", 0))
                else:
                    item["industry_data"]["product_type"] = "dining"

                    # Default dining structure
                    item["industry_data"].setdefault("cuisine_info", {})
                    item["industry_data"].setdefault("dietary_info", {})
                    item["industry_data"].setdefault("service_details", {})

            else:  # services
                # Handle free vs paid services
                if item.get("price_type") == "free":
                    item["price_min"] = 0
                    item["price_max"] = 0
                    item["duration_minutes"] = None
                    item["industry_data"]["service_type"] = "complimentary"
                    item["industry_data"]["pricing_model"] = "free"

                    # Initialize complimentary services structure
                    comp_services = item["industry_data"].setdefault(
                        "complimentary_services", {}
                    )
                    comp_services.setdefault("connectivity", {})
                    comp_services.setdefault("business", {})
                    comp_services.setdefault("wellness", {})
                    comp_services.setdefault("transport", {})
                    comp_services.setdefault("guest_services", {})
                    comp_services.setdefault("food_beverage", {})
                    comp_services.setdefault("entertainment", {})
                    comp_services.setdefault("amenities", {})
                else:
                    item["industry_data"]["service_type"] = "premium"

                    # Initialize paid services structure based on category
                    if item.get("category") == "spa":
                        item["industry_data"].setdefault("spa_services", {})
                    elif item.get("category") in ["conference", "event"]:
                        item["industry_data"].setdefault("event_services", {})
                    elif item.get("category") == "tour":
                        item["industry_data"].setdefault("tour_services", {})
                    elif item.get("category") == "business":
                        item["industry_data"].setdefault("business_services", {})

                    # Initialize required structures for paid services
                    item["industry_data"].setdefault("pricing_structure", {})
                    item["industry_data"].setdefault("booking_requirements", {})

                # Initialize service details and policies (required for all services)
                item["industry_data"].setdefault("service_details", {})
                item["industry_data"].setdefault("service_policies", {})

            # HIGHLY RECOMMENDED: Initialize raw_data for user verification
            if "raw_data" not in item:
                item["raw_data"] = {}

            raw_data = item["raw_data"]
            raw_data.setdefault("extracted_text", "")
            raw_data.setdefault("confidence_score", 0.88)
            raw_data.setdefault("extraction_notes", "")
            raw_data.setdefault("original_format", "text")
            raw_data.setdefault("file_section", f"section_{idx+1}")

            # 🔥 CRITICAL FIX: Auto-generate retrieval_context if AI didn't create it
            if not item.get("retrieval_context"):
                item["retrieval_context"] = self._generate_retrieval_context(
                    item, data_type
                )
                logger.warning(
                    f"⚠️ Generated missing retrieval_context for {item.get('name', 'Unknown')}"
                )

        return extracted_data

    def _generate_hotel_tags(self, item: Dict[str, Any], data_type: str) -> List[str]:
        """Generate hotel-specific tags based on backend schema requirements"""
        tags = []

        # Category tags
        if item.get("category"):
            tags.append(item["category"])

        if data_type == "products":
            # Room type tags
            if item.get("category") in [
                "standard",
                "superior",
                "deluxe",
                "suite",
                "junior_suite",
                "executive_suite",
                "presidential_suite",
                "villa",
                "penthouse",
            ]:
                # Room-specific tags
                view_type = (
                    item.get("industry_data", {})
                    .get("room_specifications", {})
                    .get("view_type")
                )
                if view_type:
                    tags.append(view_type)

                bed_config = (
                    item.get("industry_data", {})
                    .get("room_specifications", {})
                    .get("bed_configuration")
                )
                if bed_config:
                    tags.append(f"{bed_config}_bed")

                # Luxury amenities tags
                luxury_amenities = (
                    item.get("industry_data", {})
                    .get("room_amenities", {})
                    .get("luxury", {})
                )
                if luxury_amenities.get("jacuzzi"):
                    tags.append("jacuzzi")
                if luxury_amenities.get("butler_service"):
                    tags.append("butler_service")
                if luxury_amenities.get("private_pool"):
                    tags.append("private_pool")

            # Dining tags
            elif item.get("category") in [
                "appetizer",
                "main_course",
                "dessert",
                "beverage",
                "soup",
                "salad",
                "side_dish",
            ]:
                cuisine_type = (
                    item.get("industry_data", {})
                    .get("cuisine_info", {})
                    .get("cuisine_type")
                )
                if cuisine_type:
                    tags.append(cuisine_type)

                # Dietary tags
                dietary_info = item.get("industry_data", {}).get("dietary_info", {})
                if dietary_info.get("vegetarian"):
                    tags.append("vegetarian")
                if dietary_info.get("vegan"):
                    tags.append("vegan")
                if dietary_info.get("halal"):
                    tags.append("halal")

        else:  # services
            # Service type tags
            if item.get("price_type") == "free":
                tags.append("complimentary")
                tags.append("free")
            else:
                tags.append("premium")
                tags.append("paid")

            # Category-specific tags
            if item.get("category") == "spa":
                tags.extend(["wellness", "relaxation"])
                treatment_type = (
                    item.get("industry_data", {})
                    .get("spa_services", {})
                    .get("treatment_type")
                )
                if treatment_type:
                    tags.append(treatment_type)
            elif item.get("category") == "fitness":
                tags.append("recreation")
            elif item.get("category") in ["conference", "event"]:
                tags.extend(["meeting", "business_event"])
            elif item.get("category") == "tour":
                tags.append("sightseeing")
            elif item.get("category") == "transport":
                tags.append("transportation")

        # Product type tags from industry_data
        product_type = item.get("industry_data", {}).get("product_type")
        if product_type:
            tags.append(product_type)

        service_type = item.get("industry_data", {}).get("service_type")
        if service_type:
            tags.append(service_type)

        return tags

    def _generate_retrieval_context(self, item: Dict[str, Any], data_type: str) -> str:
        """
        🔥 FALLBACK: Generate retrieval_context if AI didn't create it

        This ensures all items have proper context for RAG retrieval even when
        AI models don't follow the schema perfectly.
        """
        try:
            if data_type == "products":
                # Generate for product (room/dining)
                name = item.get("name", "Unknown Product")
                category = item.get("category", "unknown")
                description = item.get("description", "")

                # Price information
                price_1 = item.get("price_1", 0)
                price_2 = item.get("price_2", 0)
                price_3 = item.get("price_3", 0)
                original_price = item.get("original_price", 0)
                currency = item.get("currency", "VND")

                # Conditions
                condition_1 = item.get("condition_price_1", "")
                condition_2 = item.get("condition_price_2", "")
                condition_3 = item.get("condition_price_3", "")

                # Quantity
                quantity = item.get("quantity", 1)

                # Build retrieval context
                context_parts = []
                context_parts.append(f"Tên: {name}. Loại: {category}.")

                if description:
                    context_parts.append(f"Mô tả: {description}")

                if original_price and original_price > 0:
                    context_parts.append(f"Giá gốc: {original_price:,.0f} {currency}.")

                # Add price options
                if price_1 and price_1 > 0:
                    price_text = f"Lựa chọn 1: {price_1:,.0f} {currency}"
                    if condition_1:
                        price_text += f" - {condition_1}"
                    context_parts.append(price_text + ".")

                if price_2 and price_2 > 0:
                    price_text = f"Lựa chọn 2: {price_2:,.0f} {currency}"
                    if condition_2:
                        price_text += f" - {condition_2}"
                    context_parts.append(price_text + ".")

                if price_3 and price_3 > 0:
                    price_text = f"Lựa chọn 3: {price_3:,.0f} {currency}"
                    if condition_3:
                        price_text += f" - {condition_3}"
                    context_parts.append(price_text + ".")

                if quantity > 1:
                    context_parts.append(f"Số lượng có sẵn: {quantity}.")

                # Add other info if available
                other_info = item.get("other_info", {})
                if isinstance(other_info, dict):
                    if other_info.get("area_sqm"):
                        context_parts.append(f"Diện tích: {other_info['area_sqm']}m².")

                    amenities = other_info.get("amenities", [])
                    if amenities and isinstance(amenities, list):
                        context_parts.append(f"Tiện nghi: {', '.join(amenities[:5])}.")

                return " ".join(context_parts)

            else:  # services
                # Generate for service
                name = item.get("name", "Unknown Service")
                category = item.get("category", "unknown")
                service_code = item.get("service_code", "N/A")
                price_type = item.get("price_type", "unknown")
                price_min = item.get("price_min", 0)
                price_max = item.get("price_max", 0)
                currency = item.get("currency", "VND")
                duration_minutes = item.get("duration_minutes")
                content = item.get("content_for_embedding", "")

                # Build service context
                context_parts = []
                context_parts.append(
                    f"Tên dịch vụ: {name}. Loại: {category}. Mã dịch vụ: {service_code}."
                )
                context_parts.append(f"Loại giá: {price_type}.")

                if price_type == "free":
                    context_parts.append("Miễn phí cho khách lưu trú.")
                else:
                    if price_min == price_max and price_min > 0:
                        context_parts.append(f"Giá: {price_min:,.0f} {currency}.")
                    elif price_min > 0 and price_max > 0:
                        context_parts.append(
                            f"Giá: từ {price_min:,.0f} đến {price_max:,.0f} {currency}."
                        )
                    elif price_min > 0:
                        context_parts.append(f"Giá từ: {price_min:,.0f} {currency}.")

                if duration_minutes:
                    if duration_minutes >= 60:
                        hours = duration_minutes // 60
                        minutes = duration_minutes % 60
                        if minutes > 0:
                            context_parts.append(f"Thời gian: {hours}h{minutes}m.")
                        else:
                            context_parts.append(f"Thời gian: {hours} giờ.")
                    else:
                        context_parts.append(f"Thời gian: {duration_minutes} phút.")

                if content:
                    context_parts.append(f"Mô tả: {content}")

                # Add service details if available
                industry_data = item.get("industry_data", {})
                if isinstance(industry_data, dict):
                    service_details = industry_data.get("service_details", {})
                    if isinstance(service_details, dict):
                        operating_hours = service_details.get("operating_hours")
                        if operating_hours:
                            context_parts.append(f"Giờ hoạt động: {operating_hours}.")

                        location = service_details.get("location")
                        if location:
                            context_parts.append(f"Địa điểm: {location}.")

                return " ".join(context_parts)

        except Exception as e:
            # Fallback to basic context
            logger.error(f"❌ Error generating retrieval_context: {e}")
            name = item.get("name", "Unknown Item")
            category = item.get("category", "unknown")
            return (
                f"Tên: {name}. Loại: {category}. Thông tin chi tiết sẽ được cập nhật."
            )
