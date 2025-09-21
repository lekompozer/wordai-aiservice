# 🤖 AI Service Integration Guide - Industry Data Extraction Flow

## 📋 Overview

This document outlines the complete flow for processing company files through industry-specific data extraction using our 4 specialized industry templates:

- 🏦 **Banking**: Savings, Credit Cards, Loans + Wealth Management, Investment, Forex
- 🛡️ **Insurance**: Multi-country (Vietnam/USA) with Life, Health, Non-Life coverage
- 🏨 **Hotel**: Universal Room, Dining + Free/Paid Services  
- 🍽️ **Restaurant**: Universal Dish + Dine-in/Delivery Services

## 🔄 Complete API Flow

### **Step 1: File Upload with Industry Context**
```http
POST /api/files/upload-with-industry
Content-Type: multipart/form-data

{
  "file": [binary data],
  "name": "Hotel Services Menu 2025",
  "description": "Complete hotel services pricing and descriptions",
  "industry": "hotel",
  "dataType": "services", 
  "tagIds": ["tag-uuid-1", "tag-uuid-2"]
}
```

**Backend Process:**
1. File validation & storage limit check
2. Upload to R2 storage
3. Save file record in database with industry metadata
4. Assign tags if provided
5. Upload to AI service for initial storage (data_type: 'info')
6. Set file status to `COMPLETED` (ready for extraction)

**Response:**
```json
{
  "success": true,
  "message": "File uploaded successfully. Ready for data extraction.",
  "data": {
    "id": "file-uuid",
    "name": "Hotel Services Menu 2025",
    "industry": "hotel",
    "dataType": "services",
    "extractionReady": true,
    "status": "completed"
  }
}
```

### **Step 2: Data Extraction Request**
```http
POST /api/files/{fileId}/extract
Content-Type: application/json

{
  "industry": "hotel",
  "dataType": "services"
}
```

**Backend Process:**
1. Verify file exists and is ready for extraction
2. Get file tags for context
3. Call AI service with extraction parameters
4. Update file status to `PROCESSING`

**AI Service Call:**
```javascript
await aiService.uploadFile(companyId, {
  file_id: fileId,
  file_name: "Hotel Services Menu 2025",
  file_type: "application/pdf",
  file_url: "https://r2-url/file.pdf",
  data_type: "services", // 'products' or 'services'
  uploaded_by: "extraction",
  metadata: {
    extraction_mode: true,
    industry: "hotel",
    original_name: "hotel-services.pdf",
    description: "Complete hotel services pricing and descriptions",
    tags: ["spa", "conference", "dining"],
    company_info: {
      company_id: "company-uuid",
      industry: "hotel"
    }
  }
})
```

## 🎯 AI Service Processing Logic

### **Industry Template Selection**

The AI service should select templates based on `industry` + `dataType`:

```javascript
const templateKey = `${industry}_${dataType}`;

// Example mappings:
const TEMPLATE_MAPPINGS = {
  // Hotel Industry
  'hotel_products': ['hotel_room_universal', 'hotel_dining'],
  'hotel_services': ['hotel_free_service', 'hotel_paid_service'],
  
  // Restaurant Industry  
  'restaurant_products': ['restaurant_dish_universal'],
  'restaurant_services': ['restaurant_dine_in', 'restaurant_delivery'],
  
  // Banking Industry
  'banking_products': ['banking_savings', 'banking_credit_card', 'banking_loans'],
  'banking_services': ['banking_wealth_mgmt', 'banking_investment', 'banking_forex'],
  
  // Insurance Industry (Multi-country)
  'insurance_products': ['insurance_vietnam_life', 'insurance_vietnam_health', 'insurance_vietnam_nonlife', 
                        'insurance_usa_health', 'insurance_usa_home', 'insurance_usa_auto', 
                        'insurance_usa_life', 'insurance_usa_liability'],
  'insurance_services': ['insurance_claims_processing']
};
```

### **Extraction Processing Steps**

1. **Document Analysis**
   - Parse file content (PDF, Word, Excel, etc.)
   - Identify data structures and patterns
   - Extract text and tabular data

2. **Template Matching**
   - Apply industry-specific templates
   - Use keywords and patterns from templates
   - Apply validation rules and field mappings

3. **Data Transformation**
   - Standardize currency (VND for Vietnam context)
   - Apply transformation rules from templates
   - Validate data types and constraints

4. **Product/Service Creation**
   - Create structured product/service records
   - Apply industry_data mapping
   - Set proper categories and metadata

### **Expected Extraction Output**

The AI service should return structured data that maps exactly to our ProductModel and ServiceModel schemas:

#### **Hotel Products Example** (Room + Dining):
```json
{
  "extraction_id": "extraction-uuid-001",
  "company_id": "company-uuid", 
  "file_id": "file-uuid",
  "industry": "hotel",
  "data_type": "products",
  "extracted_items": [
    {
      "name": "Deluxe Ocean View Room",
      "description": "Spacious deluxe room with panoramic ocean view, king bed, marble bathroom and luxury amenities",
      "sku": "ROOM-DLX-OCEAN-001",
      "category": "deluxe",
      "price": 2500000,
      "currency": "VND",
      "price_unit": "per_night",
      "image_urls": ["https://hotel.com/images/deluxe-ocean.jpg"],
      "industry_data": {
        "room_specifications": {
          "size_sqm": 45,
          "max_occupancy": {
            "adults": 2,
            "children": 1
          },
          "bed_configuration": "king",
          "bedroom_count": 1,
          "bathroom_count": 1,
          "bathroom_type": "ensuite",
          "view_type": "ocean_view",
          "floor_level": "high_floor",
          "location_in_hotel": "main_building",
          "living_area": false,
          "dining_area": false,
          "kitchen": false,
          "balcony": true,
          "terrace": false,
          "bathroom_amenities": {
            "bathtub": true,
            "rain_shower": true,
            "separate_toilet": false
          }
        },
        "room_amenities": {
          "comfort": {
            "air_conditioning": true,
            "minibar": true,
            "coffee_machine": true,
            "heating": false,
            "room_service": true
          },
          "entertainment": {
            "smart_tv_size": "55_inch",
            "sound_system": false,
            "netflix_access": true,
            "gaming_console": false
          },
          "connectivity": {
            "wifi_highspeed": true,
            "ethernet_port": true,
            "usb_charging_ports": 4
          },
          "safety": {
            "in_room_safe": true,
            "smoke_detector": true,
            "carbon_monoxide_detector": true
          },
          "luxury": {
            "jacuzzi": false,
            "butler_service": false,
            "private_chef": false,
            "limousine_service": false,
            "private_pool": false
          }
        },
        "pricing_structure": {
          "base_rate": 2500000,
          "extra_adult": 500000,
          "extra_child": 250000,
          "seasonal_multiplier": {
            "peak_season": 1.3,
            "low_season": 0.8
          }
        },
        "policies": {
          "check_in_time": "15:00",
          "check_out_time": "12:00",
          "cancellation": {
            "free_until_days": 1
          },
          "children_policy": "under_12_half_price",
          "pet_policy": "not_allowed"
        },
        "product_type": "room"
      },
      "tags": ["ocean_view", "deluxe", "king_bed", "balcony"],
      "metadata": {
        "extraction_confidence": 0.95,
        "template_used": "hotel_room_universal"
      }
    },
    {
      "name": "Grilled Salmon with Herbs",
      "description": "Fresh Atlantic salmon grilled to perfection with aromatic herbs and lemon butter sauce, served with seasonal vegetables",
      "sku": "DISH-SALMON-001",
      "category": "main_course",
      "price": 480000,
      "currency": "VND",
      "price_unit": "per_portion",
      "image_urls": ["https://hotel.com/images/salmon-dish.jpg"],
      "industry_data": {
        "cuisine_info": {
          "cuisine_type": "western",
          "meal_type": "dinner",
          "ingredients": ["atlantic_salmon", "mixed_herbs", "lemon", "butter", "seasonal_vegetables"],
          "portion_size": "300g",
          "preparation_time": 25,
          "cooking_method": "grilled",
          "spice_level": "mild",
          "chef_special": true
        },
        "dietary_info": {
          "vegetarian": false,
          "vegan": false,
          "gluten_free": true,
          "halal": false,
          "kosher": false,
          "allergens": ["fish"],
          "calories": 420
        },
        "beverage_info": {},
        "service_details": {
          "restaurant_name": "Ocean View Restaurant",
          "service_type": "a_la_carte",
          "available_times": ["dinner"],
          "reservation_required": true,
          "dress_code": "smart_casual",
          "dining_location": "main_restaurant"
        },
        "pricing_options": {
          "half_portion": 300000,
          "combo": 680000,
          "group_menu": null,
          "wine_pairing": 180000,
          "room_service_surcharge": 50000
        },
        "availability": {
          "seasonal_only": false,
          "daily_limit": null,
          "advance_order_hours": 0
        },
        "product_type": "dining"
      },
      "tags": ["western", "seafood", "gluten_free", "chef_special"],
      "metadata": {
        "extraction_confidence": 0.92,
        "template_used": "hotel_dining"
      }
    }
  ],
  "metadata": {
    "total_items_extracted": 2,
    "templates_used": ["hotel_room_universal", "hotel_dining"],
    "extraction_confidence": 0.935,
    "processing_time_ms": 3200
  }
}
```

#### **Hotel Services Example** (Free + Paid):
```json
{
  "extraction_id": "extraction-uuid-002",
  "company_id": "company-uuid", 
  "file_id": "file-uuid",
  "industry": "hotel",
  "data_type": "services",
  "extracted_items": [
    {
      "name": "Complimentary Wi-Fi & Business Center",
      "description": "High-speed wireless internet access throughout hotel premises plus 24/7 business center with printing facilities",
      "service_code": "WIFI-BUSINESS-FREE-001",
      "category": "business",
      "price_type": "free",
      "price_min": 0,
      "price_max": 0,
      "currency": "VND",
      "duration_minutes": null,
      "image_urls": [],
      "industry_data": {
        "complimentary_services": {
          "connectivity": {
            "wifi": true,
            "wifi_speed_mbps": 100,
            "business_center": true,
            "internet_kiosk": true
          },
          "business": {
            "business_center": true,
            "printing_limit": 20,
            "fax_service": true,
            "meeting_room_access": false
          },
          "wellness": {
            "gym_access": false,
            "swimming_pool": false,
            "sauna": false,
            "steam_room": false,
            "kids_club": false,
            "playground": false
          },
          "transport": {
            "shuttle_service": false,
            "shuttle_destinations": [],
            "shuttle_schedule": "",
            "parking": false,
            "valet_parking": false
          },
          "guest_services": {
            "concierge": true,
            "luggage_storage": true,
            "wake_up_calls": true,
            "newspaper_delivery": true,
            "tour_information": true,
            "ticket_booking": false
          },
          "food_beverage": {
            "welcome_drink": false,
            "afternoon_tea": false,
            "happy_hour": false,
            "coffee_tea_lobby": true,
            "fruit_basket": false
          },
          "entertainment": {
            "live_music": false,
            "cultural_shows": false,
            "game_room": false,
            "library": true,
            "movie_nights": false
          },
          "amenities": {
            "pool_towel_service": false,
            "umbrella_service": true,
            "safety_deposit_box": true,
            "ice_machine": true
          }
        },
        "service_details": {
          "operating_hours": "24/7",
          "location": "lobby_and_all_floors"
        },
        "service_policies": {
          "age_restrictions": "none",
          "dress_code": "none", 
          "advance_booking_required": false,
          "time_limits": "no_limit"
        },
        "service_type": "complimentary",
        "pricing_model": "free"
      },
      "tags": ["free", "wifi", "business", "24_7"],
      "metadata": {
        "extraction_confidence": 0.98,
        "template_used": "hotel_free_service"
      }
    },
    {
      "name": "Traditional Vietnamese Spa Massage",
      "description": "90-minute full body traditional Vietnamese massage with herbal oils and hot stone therapy in private treatment room",
      "service_code": "SPA-MASSAGE-TRADITIONAL-90",
      "category": "spa",
      "price_type": "fixed",
      "price_min": 1800000,
      "price_max": 1800000,
      "currency": "VND",
      "duration_minutes": 90,
      "image_urls": ["https://hotel.com/images/spa-traditional-massage.jpg"],
      "industry_data": {
        "spa_services": {
          "treatment_type": "massage",
          "therapist_gender_preference": "any",
          "couple_treatment_available": true,
          "products_brand": "local_herbs",
          "organic_products": true,
          "treatment_room_type": "private"
        },
        "event_services": {},
        "tour_services": {},
        "business_services": {
          "secretarial": false,
          "translation": false,
          "equipment_rental": false,
          "video_conferencing": false,
          "document_printing": false,
          "courier_service": false
        },
        "pricing_structure": {
          "price_per_person": 1800000,
          "price_per_hour": 1200000,
          "package_price": 1800000,
          "group_discount_percentage": 15,
          "cancellation_fee": 500000
        },
        "service_details": {
          "operating_hours": "09:00-21:00",
          "days_available": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
          "seasonal_availability": false,
          "weather_dependent": false
        },
        "booking_requirements": {
          "advance_booking_hours": 4,
          "cancellation_policy": "24_hours",
          "deposit_percentage": 50,
          "payment_methods": ["cash", "credit_card"],
          "dress_code": "casual",
          "age_restrictions": "18+"
        },
        "add_on_services": {
          "photography": false,
          "floral_arrangements": true,
          "special_decorations": false,
          "live_entertainment": false,
          "additional_equipment": false
        },
        "service_type": "premium"
      },
      "tags": ["spa", "massage", "traditional", "vietnamese", "90_minutes"],
      "metadata": {
        "extraction_confidence": 0.94,
        "template_used": "hotel_paid_service"
      }
    },
    {
      "name": "Half-Day Cu Chi Tunnels Tour",
      "description": "Guided half-day tour to historic Cu Chi Tunnels with transportation, English-speaking guide, and entrance fees included",
      "service_code": "TOUR-CUCHI-HALF-001", 
      "category": "tour",
      "price_type": "per_person",
      "price_min": 850000,
      "price_max": 850000,
      "currency": "VND",
      "duration_minutes": 300,
      "image_urls": ["https://hotel.com/images/cuchi-tunnels-tour.jpg"],
      "industry_data": {
        "spa_services": {},
        "event_services": {},
        "tour_services": {
          "tour_type": "historical",
          "destination": "Cu Chi Tunnels",
          "group_size": {
            "minimum": 4,
            "maximum": 16
          },
          "private_tour_available": true,
          "includes": {
            "tour_guide": true,
            "transportation": true,
            "entrance_fees": true,
            "meals": false,
            "hotel_pickup": true
          }
        },
        "business_services": {
          "secretarial": false,
          "translation": true,
          "equipment_rental": false,
          "video_conferencing": false,
          "document_printing": false,
          "courier_service": false
        },
        "pricing_structure": {
          "price_per_person": 850000,
          "price_per_hour": null,
          "package_price": 850000,
          "group_discount_percentage": 10,
          "cancellation_fee": 200000
        },
        "service_details": {
          "operating_hours": "08:00-14:00",
          "days_available": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
          "seasonal_availability": false,
          "weather_dependent": true
        },
        "booking_requirements": {
          "advance_booking_hours": 24,
          "cancellation_policy": "48_hours",
          "deposit_percentage": 30,
          "payment_methods": ["cash", "credit_card", "bank_transfer"],
          "dress_code": "casual",
          "age_restrictions": "children_welcome"
        },
        "add_on_services": {
          "photography": true,
          "floral_arrangements": false,
          "special_decorations": false,
          "live_entertainment": false,
          "additional_equipment": false
        },
        "service_type": "premium"
      },
      "tags": ["tour", "historical", "half_day", "transportation_included"],
      "metadata": {
        "extraction_confidence": 0.91,
        "template_used": "hotel_paid_service"
      }
    }
  ],
  "metadata": {
    "total_items_extracted": 3,
    "templates_used": ["hotel_free_service", "hotel_paid_service"],
    "extraction_confidence": 0.94,
    "processing_time_ms": 3400
  }
}
        "booking_requirements": {
          "advance_booking_hours": 2,
          "cancellation_policy": "24_hours",
          "deposit_percentage": 50
        },
        "pricing_structure": {
          "price_per_session": 1200000,
          "group_discount_percentage": 10
        }
      },
      "tags": ["spa", "massage", "relaxation"],
      "metadata": {
        "extraction_confidence": 0.94,
        "template_used": "hotel_paid_service"
      }
    }
  ],
  "metadata": {
    "total_items_extracted": 2,
    "templates_used": ["hotel_free_service", "hotel_paid_service"],
    "extraction_confidence": 0.96,
    "processing_time_ms": 2800
  }
}
```

#### **Banking Products Example**:
```json
{
  "extraction_id": "extraction-uuid-003",
  "company_id": "company-uuid",
  "file_id": "file-uuid", 
  "industry": "banking",
  "data_type": "products",
  "extracted_items": [
    {
      "name": "Premium Savings Account",
      "description": "High-yield savings account with competitive interest rates and flexible terms",
      "sku": "SAV-PREM-001",
      "category": "savings",
      "price": 0,
      "currency": "VND",
      "price_unit": "monthly_fee",
      "image_urls": [],
      "industry_data": {
        "account_details": {
          "account_type": "savings",
          "minimum_balance": 10000000,
          "interest_rate": 6.5,
          "interest_calculation": "daily_balance"
        },
        "fees_structure": {
          "monthly_maintenance": 0,
          "withdrawal_fee": 5000,
          "statement_fee": 0
        },
        "features": {
          "online_banking": true,
          "mobile_app": true,
          "atm_access": true,
          "international_transfer": true
        },
        "eligibility": {
          "minimum_age": 18,
          "income_requirement": 15000000,
          "required_documents": ["id_card", "income_proof"]
        }
      },
      "tags": ["savings", "premium", "high_yield"],
      "metadata": {
        "extraction_confidence": 0.91,
        "template_used": "banking_savings"
      }
    }
  ],
  "metadata": {
    "total_items_extracted": 1,
    "templates_used": ["banking_savings"],
    "extraction_confidence": 0.91,
    "processing_time_ms": 1800
  }
}
```

#### **Restaurant Products Example**:
```json
{
  "extraction_id": "extraction-uuid-004",
  "company_id": "company-uuid",
  "file_id": "file-uuid",
  "industry": "restaurant", 
  "data_type": "products",
  "extracted_items": [
    {
      "name": "Phở Bò Tái",
      "description": "Traditional Vietnamese beef noodle soup with rare beef slices in aromatic broth",
      "sku": "PHO-BO-TAI-001",
      "category": "main_course",
      "price": 85000,
      "currency": "VND", 
      "price_unit": "per_bowl",
      "image_urls": ["https://restaurant.com/images/pho-bo-tai.jpg"],
      "industry_data": {
        "dish_details": {
          "cuisine_type": "vietnamese",
          "dish_category": "noodle_soup",
          "main_ingredients": ["beef", "rice_noodles", "herbs", "onion"],
          "portion_size": "large",
          "preparation_time": 15,
          "spice_level": "mild"
        },
        "nutritional_info": {
          "calories_per_serving": 450,
          "protein_grams": 25,
          "carbs_grams": 55
        },
        "dietary_options": {
          "vegetarian": false,
          "vegan": false, 
          "gluten_free": false,
          "halal": true
        },
        "serving_info": {
          "temperature": "hot",
          "accompaniments": ["herbs", "lime", "chili"],
          "recommended_time": ["lunch", "dinner"]
        }
      },
      "tags": ["vietnamese", "beef", "noodle_soup", "traditional"],
      "metadata": {
        "extraction_confidence": 0.97,
        "template_used": "restaurant_dish_universal"
      }
    }
  ],
  "metadata": {
    "total_items_extracted": 1,
    "templates_used": ["restaurant_dish_universal"], 
    "extraction_confidence": 0.97,
    "processing_time_ms": 1200
  }
}
```

#### **Insurance Products Example** (Multi-country):
```json
{
  "extraction_id": "extraction-uuid-005",
  "company_id": "company-uuid",
  "file_id": "file-uuid",
  "industry": "insurance",
  "data_type": "products", 
  "extracted_items": [
    {
      "name": "Comprehensive Health Insurance",
      "description": "Complete healthcare coverage with extensive hospital network and outpatient benefits",
      "sku": "INS-HEALTH-COMP-VN",
      "category": "health",
      "price": 2400000,
      "currency": "VND",
      "price_unit": "annual_premium",
      "image_urls": [],
      "industry_data": {
        "policy_details": {
          "coverage_amount": 500000000,
          "policy_term_years": 1,
          "renewable": true,
          "country": "vietnam"
        },
        "coverage_benefits": {
          "inpatient_treatment": true,
          "outpatient_treatment": true,
          "emergency_care": true,
          "dental_coverage": false,
          "maternity_coverage": true
        },
        "network_providers": {
          "hospital_count": 150,
          "clinic_count": 300,
          "international_coverage": false
        },
        "policy_conditions": {
          "deductible_amount": 1000000,
          "copay_percentage": 10,
          "waiting_period_days": 30,
          "pre_existing_conditions": "excluded"
        },
        "eligibility": {
          "min_age": 18,
          "max_age": 65,
          "medical_examination_required": true
        }
      },
      "tags": ["health", "comprehensive", "vietnam", "renewable"],
      "metadata": {
        "extraction_confidence": 0.89,
        "template_used": "insurance_vietnam_health"
      }
    }
  ],
  "metadata": {
    "total_items_extracted": 1,
    "templates_used": ["insurance_vietnam_health"],
    "extraction_confidence": 0.89, 
    "processing_time_ms": 2100
  }
}
```

## 📋 Data Structure Requirements by Industry

> **🔥 IMPORTANT NOTE:** All fields in the industry_data structure are **OPTIONAL**. The AI service should return as much data as it can extract, but missing fields will not cause extraction failures. Backend will store both the structured data and raw file content for user verification and manual editing.

### **🏦 Banking Industry**

#### **Products Schema Requirements:**
```javascript
// ALL fields are optional - AI service should populate what it can extract
{
  name?: string,           // "Premium Savings Account"
  sku?: string,           // "SAV-PREM-001" 
  category?: enum,        // "savings" | "credit_card" | "loans"
  price?: number,         // Monthly fee or 0 for free
  currency?: "VND",
  price_unit?: enum,      // "monthly_fee" | "annual_fee" | "transaction_fee"
  
  // Banking-specific industry_data structure - ALL OPTIONAL
  industry_data?: {
    account_details?: {
      account_type?: string,
      minimum_balance?: number,
      interest_rate?: number,
      interest_calculation?: string
    },
    fees_structure?: {
      monthly_maintenance?: number,
      withdrawal_fee?: number,
      statement_fee?: number
    },
    features?: {
      online_banking?: boolean,
      mobile_app?: boolean,
      atm_access?: boolean
    },
    eligibility?: {
      minimum_age?: number,
      income_requirement?: number,
      required_documents?: string[]
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,    // Raw text content extracted from file
    confidence_score?: number,  // AI confidence in extraction
    extraction_notes?: string,  // AI notes about extraction challenges
    original_format?: string    // Original data format/structure
  }
}
```

#### **Services Schema Requirements:**
```javascript
{
  name?: string,                    // "Wealth Management Advisory"
  service_code?: string,           // "WM-ADV-001"
  category?: enum,                 // "wealth_management" | "investment" | "forex"
  price_type?: enum,               // "fixed" | "percentage" | "tiered"
  price_min?: number,
  price_max?: number,
  currency?: "VND",
  duration_minutes?: number,       // Session duration
  
  industry_data?: {
    service_details?: {
      minimum_portfolio?: number,
      management_fee_percentage?: number,
      advisory_fee?: number
    },
    requirements?: {
      minimum_investment?: number,
      risk_assessment_required?: boolean,
      certification_required?: boolean
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```

### **🛡️ Insurance Industry**

> **🌍 Multi-Country Support:** Insurance templates support both **Vietnam** (3 main types) and **USA** (5 main types) with country-specific regulations and currency handling.

#### **Country & Template Overview:**

**🇻🇳 Vietnam Insurance Templates (3 types):**
- **Life Insurance** (`life_insurance`): sinh kỳ, tử kỳ, hỗn hợp, trọn đời, hưu trí, liên kết đầu tư
- **Health Insurance** (`health_insurance`): tai nạn con người, y tế thương mại, chăm sóc sức khỏe  
- **Non-Life Insurance** (`non_life_insurance`): tài sản, trách nhiệm dân sự, xe cơ giới, cháy nổ, nông nghiệp

**🇺🇸 USA Insurance Templates (5 types):**
- **Health Insurance** (`health_insurance`): Medicaid, Medicare, CHIP, Private, Employer-sponsored
- **Homeowners Insurance** (`homeowners_insurance`): Replacement Cost, Actual Cash Value
- **Auto Insurance** (`auto_insurance`): Liability, Comprehensive, Collision, Full Coverage
- **Life Insurance** (`life_insurance`): Term Life, Whole Life, Universal Life
- **Liability Insurance** (`liability_insurance`): Professional, General, Personal

#### **Products Schema Requirements:**

##### **🇻🇳 Vietnam Life Insurance Products:**
```javascript
{
  name?: string,                   // "Bảo hiểm nhân thọ trọn đời ABC" | "Prudential PRU-LIFE Endowment"
  sku?: string,                   // "VN-LIFE-ABC-001" | "PRU-ENDOW-VN-001"
  category?: "life_insurance",
  price?: number,                 // Annual premium in VND
  currency?: "VND",
  price_unit?: "annual_premium",
  
  industry_data?: {
    // Location & Provider - ALL OPTIONAL
    location?: {
      country?: "vietnam",        // Auto-set for Vietnam templates
      supervision_agency?: "mic_vietnam"  // Bộ Tài chính Vietnam
    },
    provider?: {
      company_name?: string,      // "Bảo Việt" | "Prudential Việt Nam" | "AIA Việt Nam"
      license_number?: string,    // Vietnam insurance license
      license_type?: string       // "nhân thọ" | "phi nhân thọ" | "tái bảo hiểm"
    },
    
    // Policy Details - ALL OPTIONAL
    insurance_details?: {
      policy_type?: enum,         // "sinh_ky" | "tu_ky" | "hon_hop" | "tron_doi" | "huu_tri" | "lien_ket_dau_tu"
      policy_term_years?: number, // Thời hạn hợp đồng
      premium_frequency?: enum,   // "monthly" | "quarterly" | "semi_annual" | "annual"
      coverage_amount?: {
        min?: number,             // Số tiền bảo hiểm tối thiểu (VND)
        max?: number              // Số tiền bảo hiểm tối đa (VND)
      }
    },
    
    // Vietnam-specific Benefits - ALL OPTIONAL
    benefits?: {
      death_benefit?: boolean,           // Quyền lợi tử vong
      survival_benefit?: boolean,        // Quyền lợi sinh kỳ
      maturity_benefit?: boolean,        // Quyền lợi đáo hạn
      cash_surrender_value?: boolean,    // Giá trị hoàn lại
      policy_loan_facility?: boolean,    // Vay theo hợp đồng
      retirement_pension?: boolean,      // Lương hưu trí
      investment_return?: boolean        // Lợi nhuận đầu tư (liên kết)
    },
    
    // Eligibility (Vietnam regulations) - ALL OPTIONAL
    eligibility?: {
      min_age?: number,                  // Tuổi tối thiểu (0-70)
      max_age?: number,                  // Tuổi tối đa (18-99)
      health_declaration_required?: boolean, // Yêu cầu khai báo sức khỏe
      medical_exam_required?: boolean,   // Yêu cầu khám sức khỏe
      income_proof_required?: boolean    // Yêu cầu chứng minh thu nhập
    },
    
    // Premium & Payment Details - ALL OPTIONAL
    premium_details?: {
      calculation_method?: string,       // Phương pháp tính phí
      payment_period?: string,          // Thời gian đóng phí
      grace_period_days?: number,       // Thời gian gia hạn đóng phí
      late_payment_penalty?: number     // Phí phạt chậm đóng (VND)
    },
    
    // Claims & Settlement - ALL OPTIONAL
    claims?: {
      waiting_period_days?: number,     // Thời gian chờ bồi thường
      settlement_time_days?: number,    // Thời gian giải quyết
      required_documents?: string[],    // Hồ sơ yêu cầu
      exclusions?: string[]             // Điều khoản loại trừ
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,      // Raw Vietnamese text about this insurance
    confidence_score?: number,    // AI confidence (0-1)
    extraction_notes?: string,    // AI notes about extraction challenges
    original_format?: string,     // Original data format/structure
    file_section?: string         // Which section of file this was extracted from
  }
}
```

##### **🇻🇳 Vietnam Health Insurance Products:**
```javascript
{
  name?: string,                   // "Bảo hiểm y tế toàn diện XYZ" | "Care Health Gold"
  sku?: string,                   // "VN-HEALTH-XYZ-001"
  category?: "health_insurance",
  price?: number,                 // Annual premium in VND
  currency?: "VND",
  price_unit?: "annual_premium",
  
  industry_data?: {
    // Policy Details - ALL OPTIONAL
    insurance_details?: {
      policy_type?: enum,         // "tai_nan_con_nguoi" | "y_te_thuong_mai" | "cham_soc_suc_khoe"
      coverage_type?: enum,       // "basic" | "comprehensive" | "premium" | "vip"
      coverage_amount?: {
        max?: number,             // Giới hạn bảo hiểm năm (VND)
        min?: number              // Giới hạn mỗi lần (VND)
      }
    },
    
    // Vietnam Health Benefits - ALL OPTIONAL
    benefits?: {
      accident_coverage?: boolean,      // Tai nạn con người
      medical_treatment?: boolean,      // Điều trị y tế
      hospitalization?: boolean,        // Nội trú
      outpatient_care?: boolean,        // Ngoại trú
      emergency_care?: boolean,         // Cấp cứu
      maternity_care?: boolean,         // Thai sản
      dental_care?: boolean,            // Nha khoa
      vision_care?: boolean             // Chăm sóc mắt
    },
    
    // Vietnam Provider Network - ALL OPTIONAL
    provider_network?: {
      hospitals?: string[],             // Mạng lưới bệnh viện
      clinics?: string[],               // Mạng lưới phòng khám
      pharmacies?: string[],            // Mạng lưới nhà thuốc
      direct_billing?: boolean          // Thanh toán trực tiếp
    },
    
    // Cost Sharing (Vietnam style) - ALL OPTIONAL
    cost_sharing?: {
      deductible?: number,              // Khấu trừ (VND)
      copayment_percentage?: number,    // Tỷ lệ đồng chi trả (%)
      out_of_pocket_maximum?: number    // Tối đa tự chi trả (VND)
    },
    
    // Eligibility & Waiting Periods - ALL OPTIONAL
    eligibility?: {
      min_age?: number,
      max_age?: number,
      pre_existing_conditions?: string, // Bệnh có từ trước
      waiting_periods?: string,         // Thời gian chờ
      family_coverage?: boolean         // Bảo hiểm gia đình
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```

##### **🇻🇳 Vietnam Non-Life Insurance Products:**
```javascript
{
  name?: string,                   // "Bảo hiểm tài sản doanh nghiệp" | "Bảo hiểm xe ô tô bắt buộc"
  sku?: string,                   // "VN-ASSET-001" | "VN-AUTO-MAND-001"
  category?: "non_life_insurance",
  price?: number,                 // Annual premium in VND
  currency?: "VND",
  price_unit?: "annual_premium",
  
  industry_data?: {
    // Policy Details - ALL OPTIONAL
    insurance_details?: {
      policy_type?: enum,         // "tai_san" | "trach_nhiem_dan_su" | "xe_co_gioi" | "chay_no" | "thien_tai" | "nong_nghiep"
      policy_term_months?: number, // Thời hạn hợp đồng (tháng)
      coverage_amount?: {
        max?: number              // Số tiền bảo hiểm tối đa (VND)
      }
    },
    
    // Vietnam Non-Life Specific Benefits - ALL OPTIONAL
    benefits?: {
      property_coverage?: boolean,          // Bảo hiểm tài sản
      civil_liability?: boolean,            // Trách nhiệm dân sự
      motor_vehicle_coverage?: boolean,     // Bảo hiểm xe cơ giới
      fire_explosion_coverage?: boolean,    // Cháy nổ
      natural_disaster_coverage?: boolean,  // Thiên tai
      agriculture_coverage?: boolean        // Nông nghiệp
    },
    
    // Specific Coverage Details - ALL OPTIONAL
    coverage_details?: {
      third_party_liability?: number,       // Bồi thường bên thứ ba (VND)
      own_damage?: number,                  // Thiệt hại vật chất (VND)
      theft_coverage?: boolean,             // Bảo hiểm trộm cắp
      flood_coverage?: boolean              // Bảo hiểm lũ lụt
    },
    
    // Cost Sharing - ALL OPTIONAL
    cost_sharing?: {
      deductible?: number,                  // Khấu trừ (VND)
      maximum_liability?: number            // Trách nhiệm tối đa (VND)
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```

##### **🇺🇸 USA Health Insurance Products:**
```javascript
{
  name?: string,                   // "Blue Cross Blue Shield Gold Plan" | "Aetna Better Health"
  sku?: string,                   // "BCBS-GOLD-2025" | "AETNA-BH-001"
  category?: "health_insurance",
  price?: number,                 // Annual premium in USD
  currency?: "USD",
  price_unit?: "annual_premium",
  
  industry_data?: {
    // Location & Provider - ALL OPTIONAL
    location?: {
      country?: "usa",            // Auto-set for USA templates
      state?: string              // "California" | "Texas" | "New York" etc.
    },
    provider?: {
      company_name?: string       // "Blue Cross Blue Shield" | "Aetna" | "Cigna"
    },
    
    // US-specific Policy Details - ALL OPTIONAL
    insurance_details?: {
      plan_type?: enum,           // "medicaid" | "medicare" | "chip" | "individual" | "family_floater" | "employer_sponsored" | "critical_illness"
      plan_tier?: enum            // "bronze" | "silver" | "gold" | "platinum"
    },
    
    // US Cost Sharing Structure - ALL OPTIONAL
    cost_sharing?: {
      deductible?: number,                // Annual deductible (USD)
      out_of_pocket_maximum?: number,     // Annual out-of-pocket max (USD)
      copay_primary_care?: number,        // Primary care copay (USD)
      copay_specialist?: number,          // Specialist copay (USD)
      coinsurance?: number                // Coinsurance percentage (%)
    },
    
    // US Health Benefits - ALL OPTIONAL
    benefits?: {
      preventive_care?: boolean,          // Preventive care coverage
      prescription_drugs?: boolean,       // Prescription drug coverage
      mental_health?: boolean,            // Mental health coverage
      maternity_coverage?: boolean,       // Maternity coverage
      emergency_services?: boolean        // Emergency services coverage
    },
    
    // US Provider Networks - ALL OPTIONAL
    provider_network?: {
      network_type?: enum,               // "hmo" | "ppo" | "epo" | "pos"
      in_network_providers?: string[],   // List of in-network providers
      out_of_network_coverage?: boolean  // Out-of-network coverage available
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```

##### **🇺🇸 USA Homeowners Insurance Products:**
```javascript
{
  name?: string,                   // "State Farm Homeowners Gold" | "Allstate Premier Protection"
  sku?: string,                   // "SF-HOME-GOLD-001"
  category?: "homeowners_insurance",
  price?: number,                 // Annual premium in USD
  currency?: "USD",
  price_unit?: "annual_premium",
  
  industry_data?: {
    // Policy Details - ALL OPTIONAL
    insurance_details?: {
      coverage_type?: enum,       // "replacement_cost" | "actual_cash_value"
      policy_term_months?: 12     // Usually annual
    },
    
    // US Homeowners Coverage Limits - ALL OPTIONAL
    coverage_limits?: {
      dwelling?: number,          // Dwelling coverage limit (USD)
      personal_property?: number, // Personal property coverage (USD)
      liability?: number,         // Liability coverage (USD)
      medical_payments?: number   // Medical payments coverage (USD)
    },
    
    // Cost Sharing - ALL OPTIONAL
    cost_sharing?: {
      deductible?: number         // Homeowners deductible (USD)
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```

##### **🇺🇸 USA Auto Insurance Products:**
```javascript
{
  name?: string,                   // "GEICO Full Coverage Auto" | "Progressive Liability Plus"
  sku?: string,                   // "GEICO-FULL-001"
  category?: "auto_insurance",
  price?: number,                 // Annual premium in USD
  currency?: "USD",
  price_unit?: "annual_premium",
  
  industry_data?: {
    // Policy Details - ALL OPTIONAL
    insurance_details?: {
      coverage_type?: enum        // "liability_only" | "comprehensive" | "collision" | "full_coverage"
    },
    
    // Auto Coverage Limits - ALL OPTIONAL
    coverage_limits?: {
      bodily_injury_per_person?: number,      // USD
      bodily_injury_per_accident?: number,    // USD
      property_damage?: number,               // USD
      comprehensive_deductible?: number,      // USD
      collision_deductible?: number           // USD
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```

##### **🇺🇸 USA Life Insurance Products:**
```javascript
{
  name?: string,                   // "MetLife Term Life 20" | "Prudential Whole Life Plus"
  sku?: string,                   // "MET-TERM20-001"
  category?: "life_insurance",
  price?: number,                 // Annual premium in USD
  currency?: "USD",
  price_unit?: "annual_premium",
  
  industry_data?: {
    // Policy Details - ALL OPTIONAL
    insurance_details?: {
      policy_type?: enum,         // "term_life" | "whole_life" | "universal_life"
      policy_term_years?: number  // Policy term length
    },
    
    // Life Insurance Benefits - ALL OPTIONAL
    benefits?: {
      death_benefit?: number,     // Death benefit amount (USD)
      cash_value?: number         // Cash value component (USD)
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```

##### **🇺🇸 USA Liability Insurance Products:**
```javascript
{
  name?: string,                   // "Errors & Omissions Professional" | "General Liability Business"
  sku?: string,                   // "EO-PROF-001"
  category?: "liability_insurance",
  price?: number,                 // Annual premium in USD
  currency?: "USD",
  price_unit?: "annual_premium",
  
  industry_data?: {
    // Policy Details - ALL OPTIONAL
    insurance_details?: {
      policy_type?: enum          // "professional_liability" | "general_liability" | "personal_liability"
    },
    
    // Liability Coverage Limits - ALL OPTIONAL
    coverage_limits?: {
      per_occurrence?: number,    // Coverage per occurrence (USD)
      aggregate?: number          // Annual aggregate limit (USD)
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```

#### **Services Schema Requirements:**

##### **🛡️ Insurance Claims Processing Service (Multi-Country):**
```javascript
{
  name?: string,                   // "Express Claims Processing" | "Dịch vụ giải quyết bồi thường nhanh"
  service_code?: string,          // "CLAIMS-EXPRESS-001" | "BOI-THUONG-NHANH-001"
  category?: "claims_processing",
  price_type?: enum,              // "free" | "fixed" | "percentage"
  price_min?: number,             // Processing fee (VND/USD based on country)
  price_max?: number,             // Express fee (VND/USD based on country)
  currency?: enum,                // "VND" | "USD" (based on country)
  duration_minutes?: number,      // Service duration
  
  industry_data?: {
    // Location - ALL OPTIONAL
    location?: {
      country?: enum              // "vietnam" | "usa"
    },
    
    // Service Details - ALL OPTIONAL
    service_details?: {
      claim_types?: string[],     // Types of claims handled
      service_category?: string   // "standard" | "express" | "premium"
    },
    
    // Processing Time - ALL OPTIONAL
    processing_time?: {
      standard?: string,          // "5-7 business days" | "5-7 ngày làm việc"
      express?: string            // "24-48 hours" | "24-48 giờ"
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```

#### **Key Validation Rules for Insurance Industry:**

> **🔥 FLEXIBLE VALIDATION:** Since all fields are optional, validation focuses on data quality and consistency rather than completeness.

1. **Country Validation:** If provided, must be `"vietnam"` or `"usa"`

2. **Currency Consistency:** 
   - Vietnam: `currency` should be `"VND"` if specified
   - USA: `currency` should be `"USD"` if specified

3. **Category Validation:** If provided, must be one of:
   - Vietnam: `["life_insurance", "health_insurance", "non_life_insurance"]`
   - USA: `["health_insurance", "homeowners_insurance", "auto_insurance", "life_insurance", "liability_insurance"]`

4. **Policy Type Validation by Country:**
   - **Vietnam Life Insurance:** `["sinh_ky", "tu_ky", "hon_hop", "tron_doi", "huu_tri", "lien_ket_dau_tu"]`
   - **Vietnam Health Insurance:** `["tai_nan_con_nguoi", "y_te_thuong_mai", "cham_soc_suc_khoe"]`
   - **Vietnam Non-Life Insurance:** `["tai_san", "trach_nhiem_dan_su", "xe_co_gioi", "chay_no", "thien_tai", "nong_nghiep"]`
   - **USA Health Insurance:** `["medicaid", "medicare", "chip", "individual", "family_floater", "employer_sponsored", "critical_illness"]`
   - **USA Homeowners Insurance:** `["replacement_cost", "actual_cash_value"]`
   - **USA Auto Insurance:** `["liability_only", "comprehensive", "collision", "full_coverage"]`
   - **USA Life Insurance:** `["term_life", "whole_life", "universal_life"]`
   - **USA Liability Insurance:** `["professional_liability", "general_liability", "personal_liability"]`

5. **Age Restrictions (when provided):**
   - Vietnam: `min_age` 0-70, `max_age` 18-99
   - USA: Standard ranges apply based on insurance type

6. **Price Requirements (when provided):**
   - Vietnam: All amounts in VND, use `standardize_currency_vnd`
   - USA: All amounts in USD, use `standardize_currency_usd`

7. **Industry Data Guidelines (all optional):**
   - **Vietnam Products:** Include Vietnamese-specific benefits, regulatory compliance, local provider networks
   - **USA Products:** Include US-specific cost sharing, plan tiers, provider networks
   - **Claims Services:** Include processing times, fee structures, claim types handled

8. **Raw Data Storage (highly recommended):**
   - Always include `raw_data.extracted_text` with original text content
   - Include `raw_data.confidence_score` for extraction quality assessment
   - Add `raw_data.extraction_notes` for country-specific challenges or regulatory notes

9. **Multi-Country Template Selection:**
   - AI should detect country context from document content
   - Use appropriate templates based on detected country
   - Default to Vietnam templates if country cannot be determined
   - Support mixed documents with both countries
```

### **🏨 Hotel Industry**

#### **Products Schema Requirements:**

##### **Room Products (Universal Template - Covers All Room Types):**
```javascript
{
  name?: string,                   // "Deluxe Ocean View Room" | "Presidential Suite" | "Beach Villa"
  sku?: string,                   // "ROOM-DLX-OCEAN-001" | "SUITE-PRES-001" | "VILLA-BEACH-001"
  category?: enum,                // "standard" | "superior" | "deluxe" | "suite" | "junior_suite" | "executive_suite" | "presidential_suite" | "villa" | "penthouse"
  price?: number,                 // Per night base rate (VND)
  currency?: "VND",
  price_unit?: "per_night",
  
  industry_data?: {
    // Room specifications (all room types) - ALL OPTIONAL
    room_specifications?: {
      size_sqm?: number,          // Room area in square meters
      max_occupancy?: {
        adults?: number,          // Maximum adult guests
        children?: number         // Maximum children
      },
      bed_configuration?: string, // "king" | "queen" | "twin" | "2_singles" | "sofa_bed"
      bedroom_count?: number,     // For suites/villas (1 for standard rooms)
      bathroom_count?: number,    // Number of bathrooms
      bathroom_type?: enum,       // "ensuite" | "shared"
      view_type?: enum,           // "city_view" | "sea_view" | "ocean_view" | "mountain_view" | "garden_view" | "pool_view" | "river_view"
      floor_level?: string,       // "low_floor" | "mid_floor" | "high_floor" | "ground_floor"
      location_in_hotel?: string, // "main_building" | "annexe" | "beachfront" | "poolside"
      
      // Suite/Villa specific features
      living_area?: boolean,      // For suites - separate living room
      dining_area?: boolean,      // For suites - separate dining area  
      kitchen?: boolean,          // For apartments/villas - kitchenette/full kitchen
      balcony?: boolean,          // Private balcony
      terrace?: boolean,          // For penthouses - private terrace
      
      // Bathroom amenities
      bathroom_amenities?: {
        bathtub?: boolean,
        rain_shower?: boolean,
        separate_toilet?: boolean
      }
    },
    
    // Room amenities (comprehensive for all categories) - ALL OPTIONAL
    room_amenities?: {
      comfort?: {
        air_conditioning?: boolean,
        minibar?: boolean,
        coffee_machine?: boolean,
        heating?: boolean,
        room_service?: boolean
      },
      entertainment?: {
        smart_tv_size?: string,   // "32_inch" | "43_inch" | "55_inch" | "65_inch"
        sound_system?: boolean,
        netflix_access?: boolean,
        gaming_console?: boolean
      },
      connectivity?: {
        wifi_highspeed?: boolean,
        ethernet_port?: boolean,
        usb_charging_ports?: number
      },
      safety?: {
        in_room_safe?: boolean,
        smoke_detector?: boolean,
        carbon_monoxide_detector?: boolean
      },
      // Luxury amenities (for higher categories)
      luxury?: {
        jacuzzi?: boolean,           // For suites/penthouses
        butler_service?: boolean,    // For presidential suites
        private_chef?: boolean,      // For villas/penthouses
        limousine_service?: boolean, // For top-tier suites
        private_pool?: boolean       // For villas only
      }
    },
    
    // Pricing structure - ALL OPTIONAL
    pricing_structure?: {
      base_rate?: number,          // Same as main price field
      extra_adult?: number,        // Fee per additional adult (VND)
      extra_child?: number,        // Fee per additional child (VND)
      seasonal_multiplier?: {
        peak_season?: number,      // Multiplier (e.g., 1.5 for 50% increase)
        low_season?: number        // Multiplier (e.g., 0.8 for 20% decrease)
      }
    },
    
    // Hotel policies - ALL OPTIONAL
    policies?: {
      check_in_time?: string,      // "15:00" | "14:00" | "16:00"
      check_out_time?: string,     // "12:00" | "11:00" | "13:00"
      cancellation?: {
        free_until_days?: number   // Days before arrival for free cancellation
      },
      children_policy?: enum,      // "under_6_free" | "under_12_half_price" | "adult_rate"
      pet_policy?: enum           // "allowed" | "not_allowed" | "fee_required"
    },
    
    // Auto-set field to identify product type
    product_type?: "room"          // Always "room" for room products
  },
  
  // Raw data storage for user verification and editing
  raw_data?: {
    extracted_text?: string,      // Raw text content about this room
    confidence_score?: number,    // AI confidence in extraction (0-1)
    extraction_notes?: string,    // AI notes about extraction challenges
    original_format?: string,     // Original data format/structure
    file_section?: string         // Which section of file this was extracted from
  }
}
}
```

##### **Dining Products (Restaurant Menu Items):**
```javascript
{
  name?: string,                   // "Grilled Salmon with Herbs" | "Vietnamese Pho Bo" | "Chocolate Lava Cake"
  sku?: string,                   // "DISH-SALMON-001" | "DISH-PHO-BO-001" | "DESSERT-CHOC-001"
  category?: enum,                // "appetizer" | "main_course" | "dessert" | "beverage" | "soup" | "salad" | "side_dish"
  price?: number,                 // Per portion price (VND)
  currency?: "VND",
  price_unit?: "per_portion",
  
  industry_data?: {
    // Cuisine information - ALL OPTIONAL
    cuisine_info?: {
      cuisine_type?: enum,        // "vietnamese" | "asian" | "western" | "mediterranean" | "fusion" | "local" | "international"
      meal_type?: enum,           // "breakfast" | "lunch" | "dinner" | "brunch" | "afternoon_tea" | "snack"
      ingredients?: string[],     // ["salmon", "herbs", "lemon", "butter"]
      portion_size?: string,      // "300g" | "250ml" | "1_portion" | "sharing_size"
      preparation_time?: number,  // Minutes to prepare
      cooking_method?: string,    // "grilled" | "fried" | "steamed" | "baked" | "raw"
      spice_level?: enum,         // "mild" | "medium" | "hot" | "very_hot" | "not_spicy"
      chef_special?: boolean      // Chef's recommendation flag
    },
    
    // Dietary information - ALL OPTIONAL
    dietary_info?: {
      vegetarian?: boolean,
      vegan?: boolean,
      gluten_free?: boolean,
      halal?: boolean,
      kosher?: boolean,
      allergens?: string[],       // ["nuts", "dairy", "eggs", "shellfish", "fish"]
      calories?: number           // Per portion
    },
    
    // Beverage specific (when category = "beverage") - ALL OPTIONAL
    beverage_info?: {
      beverage_type?: enum,       // "wine" | "beer" | "cocktail" | "soft_drink" | "coffee" | "tea" | "juice" | "water"
      alcohol_percentage?: number, // For alcoholic beverages
      serving_size_ml?: number,   // Volume in milliliters
      serving_temperature?: enum, // "hot" | "cold" | "room_temperature" | "chilled" | "frozen"
      origin?: string,            // "France" | "Vietnam" | "Local" for wines/beers
      vintage_year?: number       // For wines
    },
    
    // Service details - ALL OPTIONAL
    service_details?: {
      restaurant_name?: string,   // "Ocean View Restaurant" | "Pool Bar" | "Lobby Cafe"
      service_type?: enum,        // "a_la_carte" | "buffet" | "set_menu" | "room_service" | "bar" | "coffee_shop"
      available_times?: string[], // ["breakfast", "lunch", "dinner"] or specific hours
      reservation_required?: boolean,
      dress_code?: enum,          // "casual" | "smart_casual" | "formal" | "none"
      dining_location?: string    // "main_restaurant" | "poolside" | "beach" | "rooftop"
    },
    
    // Pricing options - ALL OPTIONAL
    pricing_options?: {
      half_portion?: number,      // Price for half portion
      combo?: number,             // Combo meal price
      group_menu?: number,        // Group/family portion price
      wine_pairing?: number,      // Wine pairing add-on price
      room_service_surcharge?: number // Additional fee for room service
    },
    
    // Availability constraints - ALL OPTIONAL
    availability?: {
      seasonal_only?: boolean,    // Only available in certain seasons
      daily_limit?: number,       // Maximum portions per day
      advance_order_hours?: number // Hours advance notice required
    },
    
    // Auto-set field to identify product type
    product_type?: "dining"       // Always "dining" for food/beverage products
  },
  
  // Raw data storage for user verification and editing
  raw_data?: {
    extracted_text?: string,      // Raw text content about this dish/beverage
    confidence_score?: number,    // AI confidence in extraction (0-1)
    extraction_notes?: string,    // AI notes about extraction challenges
    original_format?: string,     // Original data format/structure
    file_section?: string         // Which section of file this was extracted from
  }
}
}
```

#### **Services Schema Requirements:**

##### **Free/Complimentary Services:**
```javascript
{
  name: string,                   // "Complimentary Wi-Fi" | "Free Gym Access" | "Airport Shuttle"
  service_code: string,          // "WIFI-FREE-001" | "GYM-FREE-001" | "SHUTTLE-AIRPORT"
  category: enum,                // "fitness" | "transport" | "business" | "entertainment" | "wellness" | "guest_service" | "food_beverage"
  price_type: "free",
  price_min: 0,
  price_max: 0,
  currency: "VND",
  duration_minutes: null,        // Not applicable for free services
  
  industry_data: {
    // REQUIRED: Complimentary services structure
    complimentary_services: {
      // Connectivity services
      connectivity: {
        wifi: boolean,
        wifi_speed_mbps: number, // Internet speed
        business_center: boolean,
        internet_kiosk: boolean
      },
      
      // Business services
      business: {
        business_center: boolean,
        printing_limit: number,  // Pages per day/stay
        fax_service: boolean,
        meeting_room_access: boolean
      },
      
      // Wellness & recreation
      wellness: {
        gym_access: boolean,
        swimming_pool: boolean,
        sauna: boolean,
        steam_room: boolean,
        kids_club: boolean,
        playground: boolean
      },
      
      // Transportation
      transport: {
        shuttle_service: boolean,
        shuttle_destinations: string[], // ["airport", "city_center", "beach", "shopping_mall"]
        shuttle_schedule: string,       // "every_30_mins" | "hourly" | "on_demand"
        parking: boolean,
        valet_parking: boolean
      },
      
      // Guest services
      guest_services: {
        concierge: boolean,
        luggage_storage: boolean,
        wake_up_calls: boolean,
        newspaper_delivery: boolean,
        tour_information: boolean,
        ticket_booking: boolean
      },
      
      // Food & beverage
      food_beverage: {
        welcome_drink: boolean,
        afternoon_tea: boolean,
        happy_hour: boolean,
        coffee_tea_lobby: boolean,
        fruit_basket: boolean
      },
      
      // Entertainment
      entertainment: {
        live_music: boolean,
        cultural_shows: boolean,
        game_room: boolean,
        library: boolean,
        movie_nights: boolean
      },
      
      // Additional amenities
      amenities: {
        pool_towel_service: boolean,
        umbrella_service: boolean,
        safety_deposit_box: boolean,
        ice_machine: boolean
      }
    },
    
    // REQUIRED: Service details
    service_details: {
      operating_hours: string,   // "24/7" | "06:00-22:00" | "pool_hours"
      location: string          // "lobby" | "pool_area" | "gym" | "all_areas"
    },
    
    // REQUIRED: Service policies
    service_policies: {
      age_restrictions: enum,    // "none" | "adults_only" | "16_plus" | "18_plus" | "children_welcome"
      dress_code: enum,          // "none" | "casual" | "smart_casual" | "formal"
      advance_booking_required: boolean,
      time_limits: string       // "2_hours_max" | "no_limit" | "subject_to_availability"
    },
    
    // Auto-set fields
    service_type: "complimentary",
    pricing_model: "free"
  }
}
```

##### **Paid/Premium Services:**
```javascript
{
  name: string,                   // "Spa Massage Treatment" | "Wedding Reception Package" | "City Tour"
  service_code: string,          // "SPA-MASSAGE-60" | "EVENT-WEDDING-PKG" | "TOUR-CITY-HALF"
  category: enum,                // "spa" | "conference" | "event" | "tour" | "business" | "entertainment" | "transportation"
  price_type: enum,              // "fixed" | "hourly" | "package" | "per_person" | "tiered"
  price_min: number,             // Minimum price (VND)
  price_max: number,             // Maximum price (VND) - same as min for fixed pricing
  currency: "VND",
  duration_minutes: number,      // Service duration (required for most paid services)
  
  industry_data: {
    // SPA SERVICES (when category = "spa")
    spa_services: {
      treatment_type: enum,      // "massage" | "facial" | "body_wrap" | "body_scrub" | "manicure" | "pedicure" | "hair_treatment" | "aromatherapy"
      therapist_gender_preference: enum, // "male" | "female" | "any" | "same_gender"
      couple_treatment_available: boolean,
      products_brand: string,    // "organic" | "luxury_brand" | "local_herbs"
      organic_products: boolean,
      treatment_room_type: enum  // "private" | "couples" | "group"
    },
    
    // EVENT & CONFERENCE SERVICES (when category = "conference" | "event")
    event_services: {
      venue_type: enum,          // "ballroom" | "conference_room" | "boardroom" | "garden" | "rooftop" | "poolside" | "beach"
      capacity: {
        theater_style: number,   // Theater seating capacity
        cocktail_style: number,  // Standing cocktail capacity
        classroom_style: number, // Classroom seating
        banquet_style: number   // Seated dinner capacity
      },
      includes: {
        event_coordinator: boolean,
        audio_visual_equipment: boolean,
        basic_lighting: boolean,
        microphone_system: boolean
      },
      catering: {
        style_options: string[], // ["buffet", "plated", "cocktail", "family_style", "stations"]
        dietary_accommodations: boolean,
        alcohol_license: boolean
      }
    },
    
    // TOUR SERVICES (when category = "tour")
    tour_services: {
      tour_type: enum,           // "cultural" | "adventure" | "culinary" | "shopping" | "nightlife" | "nature" | "historical" | "luxury"
      destination: string,       // "Ho Chi Minh City" | "Cu Chi Tunnels" | "Mekong Delta"
      group_size: {
        minimum: number,         // Minimum participants
        maximum: number          // Maximum participants
      },
      private_tour_available: boolean,
      includes: {
        tour_guide: boolean,
        transportation: boolean,
        entrance_fees: boolean,
        meals: boolean,
        hotel_pickup: boolean
      }
    },
    
    // BUSINESS SERVICES (when category = "business")
    business_services: {
      secretarial: boolean,
      translation: boolean,
      equipment_rental: boolean,
      video_conferencing: boolean,
      document_printing: boolean,
      courier_service: boolean
    },
    
    // REQUIRED: Pricing structure
    pricing_structure: {
      price_per_person: number,    // For group services
      price_per_hour: number,      // For hourly services
      package_price: number,       // For package deals
      group_discount_percentage: number, // Discount for groups (%)
      cancellation_fee: number     // Fee for cancellations
    },
    
    // REQUIRED: Service details
    service_details: {
      operating_hours: string,     // "09:00-18:00" | "24/7" | "by_appointment"
      days_available: string[],    // ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
      seasonal_availability: boolean, // Only available certain seasons
      weather_dependent: boolean   // Affected by weather conditions
    },
    
    // REQUIRED: Booking requirements
    booking_requirements: {
      advance_booking_hours: number,  // Hours notice required
      cancellation_policy: enum,     // "24_hours" | "48_hours" | "72_hours" | "1_week" | "non_refundable"
      deposit_percentage: number,    // Required deposit (%)
      payment_methods: string[],     // ["cash", "credit_card", "bank_transfer"]
      dress_code: enum,              // "casual" | "smart_casual" | "formal" | "swimwear"
      age_restrictions: string       // "none" | "adults_only" | "16+" | "18+" | "children_welcome"
    },
    
    // Optional: Add-on services
    add_on_services: {
      photography: boolean,
      floral_arrangements: boolean,
      special_decorations: boolean,
      live_entertainment: boolean,
      additional_equipment: boolean
    },
    
    // Auto-set field
    service_type: "premium"
  }
}
```

#### **Key Validation Rules for Hotel Industry:**

> **🔥 FLEXIBLE VALIDATION:** Since all fields are optional, validation is primarily for data quality and consistency rather than completeness.

1. **Room Categories:** If provided, must be one of: `["standard", "superior", "deluxe", "suite", "junior_suite", "executive_suite", "presidential_suite", "villa", "penthouse"]`

2. **Dining Categories:** If provided, must be one of: `["appetizer", "main_course", "dessert", "beverage", "soup", "salad", "side_dish"]`

3. **Free Service Categories:** If provided, must be one of: `["fitness", "transport", "business", "entertainment", "wellness", "guest_service", "food_beverage"]`

4. **Paid Service Categories:** If provided, must be one of: `["spa", "conference", "event", "tour", "business", "entertainment", "transportation"]`

5. **Price Requirements (when provided):**
   - Room products: `price_unit` should be `"per_night"` if specified
   - Dining products: `price_unit` should be `"per_portion"` if specified
   - Free services: `price_type` should be `"free"`, `price_min` and `price_max` should be `0`
   - Paid services: `price_type` should specify pricing model, `duration_minutes` recommended

6. **Industry Data Guidelines (all optional):**
   - Room products: Include any available data from `room_specifications`, `room_amenities`, `pricing_structure`, `policies`
   - Dining products: Include any available data from `cuisine_info`, `dietary_info`, `service_details`
   - Free services: Include any available data from `complimentary_services`, `service_details`, `service_policies`
   - Paid services: Include any available service type data, `pricing_structure`, `service_details`, `booking_requirements`

7. **Raw Data Storage (highly recommended):**
   - Always include `raw_data.extracted_text` with the original text content
   - Include `raw_data.confidence_score` to help users understand extraction quality
   - Add `raw_data.extraction_notes` for any challenges or ambiguities encountered

### **🍽️ Restaurant Industry**

#### **Products Schema Requirements:**
```javascript
{
  name?: string,                   // "Phở Bò Tái"
  sku?: string,                   // "PHO-BO-TAI-001"
  category?: enum,                // "appetizer" | "main_course" | "dessert" | "beverage" | "special"
  price?: number,
  currency?: "VND",
  price_unit?: enum,              // "per_bowl" | "per_plate" | "per_glass" | "per_serving"
  
  industry_data?: {
    dish_details?: {
      cuisine_type?: enum,        // "vietnamese" | "asian" | "western" | "fusion"
      dish_category?: string,     // "noodle_soup" | "rice_dish" | "grilled" | "fried"
      main_ingredients?: string[],
      portion_size?: enum,        // "small" | "medium" | "large"
      preparation_time?: number,  // minutes
      spice_level?: enum          // "not_spicy" | "mild" | "medium" | "hot"
    },
    nutritional_info?: {
      calories_per_serving?: number,
      protein_grams?: number,
      carbs_grams?: number
    },
    dietary_options?: {
      vegetarian?: boolean,
      vegan?: boolean,
      gluten_free?: boolean,
      halal?: boolean
    },
    serving_info?: {
      temperature?: enum,         // "hot" | "cold" | "room_temperature"
      accompaniments?: string[],
      recommended_time?: enum[]   // ["lunch", "dinner"]
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```

#### **Services Schema Requirements:**
```javascript
// Dine-in Service
{
  name?: string,                   // "Premium Table Service"
  service_code?: string,          // "DINE-PREM-001"
  category?: "dine_in",
  price_type?: enum,              // "free" | "fixed" | "percentage"
  price_min?: number,
  price_max?: number,
  
  industry_data?: {
    dining_service?: {
      service_type?: enum,        // "buffet" | "a_la_carte" | "set_menu"
      table_capacity?: {
        min_guests?: number,
        max_guests?: number
      },
      reservation_required?: boolean,
      service_charge_percentage?: number
    },
    ambiance?: {
      dining_area?: string,       // "indoor" | "outdoor" | "private_room"
      atmosphere?: string,        // "casual" | "fine_dining" | "family_friendly"
      live_music?: boolean
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}

// Delivery Service
{
  name?: string,                   // "Food Delivery Service"
  service_code?: string,          // "DELIVERY-001"
  category?: "delivery",
  price_type?: "fixed",
  price_min?: number,             // Delivery fee
  price_max?: number,
  
  industry_data?: {
    delivery_details?: {
      delivery_zones?: string[],
      minimum_order_amount?: number,
      estimated_delivery_time?: number,  // minutes
      delivery_fee?: number,
      free_delivery_threshold?: number
    },
    packaging?: {
      eco_friendly?: boolean,
      temperature_controlled?: boolean,
      special_handling?: string[]
    },
    availability?: {
      operating_hours?: string,
      days_available?: string[],
      holiday_schedule?: string
    }
  },
  
  // Raw data storage for user verification
  raw_data?: {
    extracted_text?: string,
    confidence_score?: number,
    extraction_notes?: string,
    original_format?: string
  }
}
```
## 📤 AI Service Response Flow

### **Step 3: AI Processing Complete Callback**

When AI service completes extraction, it should call the webhook with properly structured data:

```http
POST /api/webhook/extraction-complete
Content-Type: application/json

{
  "extraction_id": "extraction-uuid-001",
  "company_id": "company-uuid",
  "file_id": "file-uuid", 
  "status": "completed",
  "industry": "hotel",
  "data_type": "products",
  "extracted_data": {
    "products": [
      {
        "name": "Deluxe Ocean View Room",
        "description": "Spacious deluxe room with panoramic ocean view, king bed, and modern amenities",
        "sku": "ROOM-DLX-OCEAN-001",
        "category": "deluxe",
        "price": 2500000,
        "currency": "VND",
        "price_unit": "per_night",
        "image_urls": ["https://hotel.com/images/deluxe-ocean.jpg"],
        "industry_data": {
          "room_specifications": {
            "size_sqm": 45,
            "max_occupancy": {
              "adults": 2,
              "children": 1
            },
            "bed_configuration": "king",
            "view_type": "ocean_view"
          }
        },
        "tags": ["ocean_view", "deluxe", "king_bed"],
        "metadata": {
          "extraction_confidence": 0.95,
          "template_used": "hotel_room_universal"
        },
        "extracted_from_file_id": "file-uuid",
        "ai_confidence_score": 0.95,
        "ai_extraction_status": "pending_review",
        
        // RAW DATA for user verification
        "raw_data": {
          "extracted_text": "Deluxe Ocean View Room - 45 sqm, accommodates 2 adults + 1 child, King bed, Ocean view, Air conditioning, Minibar, Smart TV 55\", High-speed WiFi, In-room safe, Marble bathroom with bathtub, Private balcony, Rate: 2,500,000 VND per night",
          "confidence_score": 0.95,
          "extraction_notes": "High confidence extraction. Clear pricing and room specifications found.",
          "original_format": "PDF table format",
          "file_section": "Room Types - Page 3, Section 2.1"
        }
      }
    ],
    "services": [
      {
        "name": "Spa Massage Treatment", 
        "description": "60-minute full body relaxation massage with aromatherapy oils",
        "service_code": "SPA-MASSAGE-60",
        "category": "spa",
        "price_type": "fixed",
        "price_min": 1200000,
        "price_max": 1200000,
        "currency": "VND",
        "duration_minutes": 60,
        "image_urls": [],
        "industry_data": {
          "spa_services": {
            "treatment_type": "massage",
            "duration_minutes": 60,
            "treatment_room_type": "private"
          }
        },
        "tags": ["spa", "massage", "relaxation"],
        "metadata": {
          "extraction_confidence": 0.94,
          "template_used": "hotel_paid_service"
        },
        "extracted_from_file_id": "file-uuid",
        "ai_confidence_score": 0.94,
        "ai_extraction_status": "pending_review",
        
        // RAW DATA for user verification
        "raw_data": {
          "extracted_text": "Traditional Vietnamese Massage - 60 minutes full body massage using organic oils in private treatment room. Price: 1,200,000 VND. Advance booking required 2 hours. Available daily 9AM-9PM.",
          "confidence_score": 0.94,
          "extraction_notes": "Clear service description and pricing. Duration and booking requirements well defined.",
          "original_format": "PDF text paragraph",
          "file_section": "Spa Services - Page 8, Section 4.2"
        }
      }
    ]
  },
  "raw_file_content": "Complete extracted text content from the entire file for reference...",
  "metadata": {
    "total_items": 2,
    "products_count": 1,
    "services_count": 1,
    "templates_used": ["hotel_room_universal", "hotel_paid_service"],
    "processing_time_ms": 3200,
    "extraction_confidence": 0.945,
    "file_format": "PDF",
    "total_pages": 12,
    "extraction_method": "AI_powered_template_matching"
  }
}
```

**Backend Processing upon Webhook Receipt:**

### **🗄️ Optimized Data Storage Strategy**

The backend will store extracted data in an optimized format for frontend display and user editing:

#### **1. Product Storage (ProductModel.create())**
```javascript
for (const productData of extracted_data.products) {
  await ProductModel.create(companyId, {
    // Core fields (always included)
    id: generateUUID(),
    name: productData.name || `Unnamed Product ${index}`,
    description: productData.description || '',
    
    // Structured data (JSON for easy editing)
    structured_data: {
      sku: productData.sku,
      category: productData.category,
      price: productData.price,
      currency: productData.currency || 'VND',
      price_unit: productData.price_unit,
      image_urls: productData.image_urls || [],
      industry_data: productData.industry_data || {},
      tags: productData.tags || []
    },
    
    // Raw data for verification and manual editing
    raw_extraction_data: {
      extracted_text: productData.raw_data?.extracted_text || '',
      confidence_score: productData.ai_confidence_score || 0,
      extraction_notes: productData.raw_data?.extraction_notes || '',
      original_format: productData.raw_data?.original_format || '',
      file_section: productData.raw_data?.file_section || '',
      template_used: productData.metadata?.template_used || ''
    },
    
    // Metadata
    status: 'draft', // Always start as draft for user review
    ai_extraction_status: 'pending_review',
    extracted_from_file_id: productData.extracted_from_file_id,
    created_at: new Date(),
    updated_at: new Date()
  });
}
```

#### **2. Service Storage (ServiceModel.create())**
```javascript
for (const serviceData of extracted_data.services) {
  await ServiceModel.create(companyId, {
    // Core fields (always included)
    id: generateUUID(),
    name: serviceData.name || `Unnamed Service ${index}`,
    description: serviceData.description || '',
    
    // Structured data (JSON for easy editing)
    structured_data: {
      service_code: serviceData.service_code,
      category: serviceData.category,
      price_type: serviceData.price_type,
      price_min: serviceData.price_min,
      price_max: serviceData.price_max,
      currency: serviceData.currency || 'VND',
      duration_minutes: serviceData.duration_minutes,
      image_urls: serviceData.image_urls || [],
      industry_data: serviceData.industry_data || {},
      tags: serviceData.tags || []
    },
    
    // Raw data for verification and manual editing
    raw_extraction_data: {
      extracted_text: serviceData.raw_data?.extracted_text || '',
      confidence_score: serviceData.ai_confidence_score || 0,
      extraction_notes: serviceData.raw_data?.extraction_notes || '',
      original_format: serviceData.raw_data?.original_format || '',
      file_section: serviceData.raw_data?.file_section || '',
      template_used: serviceData.metadata?.template_used || ''
    },
    
    // Metadata
    status: 'draft', // Always start as draft for user review
    ai_extraction_status: 'pending_review',
    extracted_from_file_id: serviceData.extracted_from_file_id,
    created_at: new Date(),
    updated_at: new Date()
  });
}
```

### **🎨 Frontend Display Strategy**

The frontend will display extracted data in an optimized list format for easy review and editing:

#### **Product/Service List View:**
```json
{
  "products": [
    {
      "id": "prod-uuid-001",
      "name": "Deluxe Ocean View Room",
      "display_info": {
        "title": "Deluxe Ocean View Room",
        "subtitle": "2,500,000 VND per night • Ocean view • King bed",
        "status": "draft",
        "confidence_score": 0.95,
        "extraction_status": "pending_review"
      },
      "quick_edit_fields": {
        "name": "Deluxe Ocean View Room",
        "price": 2500000,
        "currency": "VND",
        "category": "deluxe"
      },
      "raw_text_preview": "Deluxe Ocean View Room - 45 sqm, accommodates 2 adults + 1 child...",
      "structured_data_json": "{ \"room_specifications\": { \"size_sqm\": 45, ... } }",
      "actions": ["edit", "approve", "reject", "view_raw"]
    }
  ],
  "services": [
    {
      "id": "serv-uuid-001", 
      "name": "Spa Massage Treatment",
      "display_info": {
        "title": "Spa Massage Treatment",
        "subtitle": "1,200,000 VND • 60 minutes • Spa category",
        "status": "draft",
        "confidence_score": 0.94,
        "extraction_status": "pending_review"
      },
      "quick_edit_fields": {
        "name": "Spa Massage Treatment",
        "price_min": 1200000,
        "price_max": 1200000,
        "currency": "VND",
        "category": "spa"
      },
      "raw_text_preview": "Traditional Vietnamese Massage - 60 minutes full body massage...",
      "structured_data_json": "{ \"spa_services\": { \"treatment_type\": \"massage\", ... } }",
      "actions": ["edit", "approve", "reject", "view_raw"]
    }
  ]
}
```

#### **Individual Item Detail View:**
```json
{
  "id": "prod-uuid-001",
  "basic_info": {
    "name": "Deluxe Ocean View Room",
    "description": "Spacious deluxe room with panoramic ocean view...",
    "category": "deluxe",
    "price": 2500000,
    "currency": "VND"
  },
  "structured_data": {
    "editable": true,
    "json_content": {
      "room_specifications": {
        "size_sqm": 45,
        "max_occupancy": { "adults": 2, "children": 1 },
        "bed_configuration": "king",
        "view_type": "ocean_view"
      },
      "room_amenities": {
        "comfort": { "air_conditioning": true, "minibar": true },
        "entertainment": { "smart_tv_size": "55_inch" }
      }
    }
  },
  "raw_data": {
    "extracted_text": "Full raw text that was extracted...",
    "confidence_score": 0.95,
    "extraction_notes": "High confidence extraction. Clear pricing...",
    "file_section": "Room Types - Page 3, Section 2.1",
    "template_used": "hotel_room_universal"
  },
  "extraction_metadata": {
    "ai_extraction_status": "pending_review",
    "extracted_from_file": "Hotel Services Menu 2025.pdf",
    "extraction_date": "2025-01-15T10:30:00Z"
  }
}
```

### **✏️ User Editing Capabilities**

1. **Quick Edit Mode:**
   - Edit name, price, category directly in list view
   - Save changes to `structured_data` JSON

2. **Advanced Edit Mode:**
   - Full JSON editor for `structured_data`
   - Side-by-side view with raw text for reference
   - Validation against industry schema (warnings, not errors)

3. **Raw Data Review:**
   - View original extracted text
   - Compare with structured data
   - Add manual notes and corrections

4. **Approval Workflow:**
   - Mark items as "approved", "needs_review", or "rejected"
   - Bulk approval for high-confidence extractions
   - Export approved items to production catalog

### **Step 4: Vector Storage (Qdrant)**

After successful extraction, call AI service again for vector storage:

```javascript
await aiService.storeInVectorDB(companyId, {
  file_id: fileId,
  file_name: "Hotel Services Menu 2025",
  company_id: companyId,
  industry: "hotel",
  data_type: "services", 
  description: "Complete hotel services pricing and descriptions",
  tags: ["spa", "conference", "dining"],
  extracted_items_count: 15,
  content_summary: "Hotel premium and complimentary services including spa treatments, conference facilities, dining options, and guest amenities",
  metadata: {
    upload_date: "2025-01-15T10:30:00Z",
    extraction_templates: ["hotel_paid_service", "hotel_free_service"],
    total_value: 25000000 // Total VND value of all services
  }
})
```

## 🏗️ Industry-Specific Processing Guidelines

### **🏦 Banking Industry**

**Products Processing:**
- Apply currency standardization (VND)
- Validate interest rates and fees
- Extract eligibility criteria and terms
- Map to appropriate product categories

**Services Processing:**  
- Extract fee structures and minimum amounts
- Identify service tiers and requirements
- Apply regulatory compliance fields

### **🛡️ Insurance Industry**

**Multi-Country Support:**
- Detect country context from content
- Apply country-specific templates
- Use appropriate currency (VND/USD)
- Include regulatory compliance fields

**Products Processing:**
- Extract coverage amounts and premiums
- Identify policy terms and conditions
- Map to country-specific categories

### **🏨 Hotel Industry**

**Products Processing:**
- **Room Products**: Consolidate all room types into universal template
- **Dining Products**: Extract dishes and beverages with pricing

**Services Processing:**
- **Free Services**: Identify complimentary amenities
- **Paid Services**: Extract premium service pricing and booking requirements

### **🍽️ Restaurant Industry**

**Products Processing:**
- Use universal dish template for all food categories
- Extract ingredients, portions, and dietary information
- Apply pricing standardization

**Services Processing:**
- **Dine-in**: Table service, reservations, ambiance details
- **Delivery**: Zones, fees, timing, packaging info

## 🔧 Error Handling & Edge Cases

### **Common Issues:**
1. **File Format Not Supported**: Return specific error with supported formats
2. **Extraction Failed**: Provide detailed error message and retry options
3. **Template Mismatch**: Suggest alternative industry/dataType combinations
4. **Partial Extraction**: Save partial results and flag incomplete items

### **Validation Requirements:**
- All prices must be positive numbers
- Currency must be standardized to VND
- Required fields per industry must be present
- Categories must match predefined values

### **Performance Guidelines:**
- Maximum processing time: 30 seconds per file
- Batch processing for large files (>100 items)
- Progress updates for long-running extractions

## 📊 Monitoring & Analytics

### **Track Key Metrics:**
- Extraction success rate per industry
- Average processing time by file size
- Template matching accuracy
- User satisfaction with extracted data

### **Logging Requirements:**
- Log all extraction attempts with parameters
- Track template usage statistics  
- Monitor error patterns by industry
- Record processing performance metrics

---

**🎯 This integration enables seamless industry-specific data extraction while maintaining flexibility for different business models and use cases across our 4 supported industries.**

## 🔧 Summary of Key Changes for Flexible AI Extraction

### **✅ All Fields Made Optional**
- **Validation Rules Updated**: All `required_fields` arrays in industry templates now empty `[]`
- **Flexible Extraction**: AI service can return partial data without validation failures
- **Progressive Enhancement**: More data can be added through user editing after initial extraction

### **📊 Raw Data Storage**
- **Complete Transparency**: Every extracted item includes `raw_data` with original text
- **User Verification**: Users can see exactly what AI extracted vs. what was structured
- **Confidence Scoring**: AI provides confidence scores for quality assessment
- **Extraction Notes**: AI can explain challenges or ambiguities encountered

### **🎨 Optimized Frontend Display**
- **List View**: Simple ID + Name + JSON preview for quick scanning
- **Detail View**: Side-by-side structured data + raw text for editing
- **Quick Edit**: Essential fields editable directly in list view
- **Advanced Edit**: Full JSON editor for complete customization

### **🏗️ Backend Storage Strategy**
- **Structured Data**: Clean JSON in `structured_data` field for API responses
- **Raw Extraction**: Complete `raw_extraction_data` for user verification
- **Status Management**: Draft → Review → Approved workflow
- **File Relationship**: Maintained link to source file for context

### **🔄 Error Handling**
- **No Extraction Failures**: Missing fields no longer cause template failures
- **Partial Success**: AI can extract 1 out of 100 items and still be successful
- **User Control**: Users decide what to keep, edit, or discard
- **Data Quality**: Confidence scores help users prioritize review efforts

### **📋 Template Updates Applied**
- ✅ **HotelIndustryTemplates.ts**: All 4 templates updated (Room, Dining, Free Service, Paid Service)
- ✅ **RestaurantIndustryTemplates.ts**: All 4 templates updated (Dish, Dine-in, Delivery, Catering)
- ✅ **BankingIndustryTemplates.ts**: All 6 templates updated (Savings, Credit Card, Loans, Wealth Management, Investment, Forex)
- ✅ **InsuranceIndustryTemplates.ts**: All 9 templates updated (3 Vietnam + 5 USA + 1 Claims Service)

### **🎯 Business Impact**
- **Higher Success Rate**: AI extractions rarely fail completely
- **User Confidence**: Users can verify AI work against original text
- **Iterative Improvement**: AI can learn from user corrections over time
- **Scalable Process**: Handles documents with mixed quality and formats

This flexible approach ensures maximum extraction success while giving users complete control over data quality and accuracy.
