"""
Insurance industry extraction template
Template extraction cho ngành bảo hiểm
"""

from typing import Dict, Any, List
from .base_template import BaseExtractionTemplate


class InsuranceExtractionTemplate(BaseExtractionTemplate):
    """Insurance products and services extraction with multi-country support"""

    def _get_industry(self) -> str:
        return "insurance"

    def get_system_prompt(self, data_type: str) -> str:
        if data_type == "products":
            return """Extract insurance products with ID field for ordering (1 to total items) including:
            
            🌍 MULTI-COUNTRY SUPPORT: Vietnam (3 types) and USA (5 types)
            
            🇻🇳 VIETNAM INSURANCE (3 types):
            1. LIFE INSURANCE (life_insurance): sinh kỳ, tử kỳ, hỗn hợp, trọn đời, hưu trí, liên kết đầu tư
            2. HEALTH INSURANCE (health_insurance): tai nạn con người, y tế thương mại, chăm sóc sức khỏe
            3. NON-LIFE INSURANCE (non_life_insurance): tài sản, trách nhiệm dân sự, xe cơ giới, cháy nổ, nông nghiệp
            
            🇺🇸 USA INSURANCE (5 types):
            1. HEALTH INSURANCE (health_insurance): Medicaid, Medicare, CHIP, Private, Employer-sponsored
            2. HOMEOWNERS INSURANCE (homeowners_insurance): Replacement Cost, Actual Cash Value
            3. AUTO INSURANCE (auto_insurance): Liability, Comprehensive, Collision, Full Coverage
            4. LIFE INSURANCE (life_insurance): Term Life, Whole Life, Universal Life
            5. LIABILITY INSURANCE (liability_insurance): Professional, General, Personal
            
            🔥 CRITICAL: Generate content_for_embedding field for each product - this is a natural language description optimized for AI chatbot responses.
            
            CONTENT_FOR_EMBEDDING FORMAT:
            - "Bảo hiểm [type] [name]. [Description with coverage and benefits]. Phí bảo hiểm [premium] [currency]/năm. [Key features and eligibility]."
            
            🔥 IMPORTANT: ALL industry_data fields are OPTIONAL - extract what you can find, missing data won't cause failures.
            
            CURRENCY DETECTION RULES:
            - Look for explicit currency symbols/text in file: $, USD, đ, VNĐ, VND
            - If price ≥ 10,000: likely VND (Vietnamese Dong)
            - If price < 3,000: likely USD (US Dollar)
            - Vietnamese language file + country indicators: default VND
            - English language file + country indicators: default USD
            - Always prioritize explicit currency mentions in the source text
            
            Include raw_data with extracted_text for verification."""
        else:  # services
            return """Extract insurance services with ID field for ordering (1 to total items) including:
            
            🛡️ INSURANCE SERVICES (Multi-Country):
            1. CLAIMS PROCESSING: Express claims, standard processing, settlement services
            2. UNDERWRITING: Risk assessment, policy evaluation, medical underwriting
            3. ADVISORY SERVICES: Financial consulting, insurance planning, product recommendation
            4. CUSTOMER SUPPORT: Policy management, modifications, customer care
            
            Include processing times, fees, requirements, and country-specific regulations.
            
            🔥 CRITICAL: Generate content_for_embedding field for each service - this is a natural language description optimized for AI chatbot responses.
            
            CONTENT_FOR_EMBEDDING FORMAT:
            - "Dịch vụ [name]. [Description with key features]. Thuộc danh mục [category]. Phí dịch vụ [price] [currency]. [Processing time and requirements]."
            
            🔥 IMPORTANT: ALL industry_data fields are OPTIONAL - extract what you can find, missing data won't cause failures.
            
            CURRENCY DETECTION: Same rules as products - smart detection based on symbols and price analysis.
            
            Include raw_data with extracted_text for verification."""

    def get_extraction_schema(self, data_type: str) -> Dict[str, Any]:
        if data_type == "products":
            return {
                "id": "number - Item ordering ID (1 to total items)",
                "name": "string - Insurance product name (REQUIRED)",
                "content_for_embedding": "string - REQUIRED: Natural language description optimized for AI chatbot",
                "sku": "string - Policy code (optional)",
                "category": "string - Vietnam: life_insurance|health_insurance|non_life_insurance. USA: health_insurance|homeowners_insurance|auto_insurance|life_insurance|liability_insurance",
                "price": "number - Annual premium (REQUIRED)",
                "currency": "string - VND|USD (smart detection: look for symbols $,đ,VNĐ in text, or use price analysis: ≥10k=VND, <3k=USD)",
                "price_unit": "string - annual_premium|monthly_premium",
                "industry_data": {
                    "🔥 NOTE": "ALL FIELDS BELOW ARE OPTIONAL - extract what you can find, missing data won't cause failures",
                    # Location & Provider - ALL OPTIONAL
                    "location": {
                        "country": "string - vietnam|usa (OPTIONAL but important for template selection)",
                        "state": "string - For USA: California|Texas|New York etc. (OPTIONAL)",
                        "supervision_agency": "string - Vietnam: mic_vietnam (OPTIONAL)",
                    },
                    "provider": {
                        "company_name": "string - Bảo Việt|Prudential Việt Nam|Blue Cross Blue Shield|Aetna (OPTIONAL)",
                        "license_number": "string - Vietnam insurance license (OPTIONAL)",
                        "license_type": "string - Vietnam: nhân thọ|phi nhân thọ|tái bảo hiểm (OPTIONAL)",
                    },
                    # Insurance Policy Details - ALL OPTIONAL
                    "insurance_details": {
                        # Vietnam Life Insurance Types
                        "policy_type_vietnam_life": "string - sinh_ky|tu_ky|hon_hop|tron_doi|huu_tri|lien_ket_dau_tu (OPTIONAL)",
                        # Vietnam Health Insurance Types
                        "policy_type_vietnam_health": "string - tai_nan_con_nguoi|y_te_thuong_mai|cham_soc_suc_khoe (OPTIONAL)",
                        # Vietnam Non-Life Insurance Types
                        "policy_type_vietnam_nonlife": "string - tai_san|trach_nhiem_dan_su|xe_co_gioi|chay_no|thien_tai|nong_nghiep (OPTIONAL)",
                        # USA Health Insurance Types
                        "plan_type_usa_health": "string - medicaid|medicare|chip|individual|family_floater|employer_sponsored|critical_illness (OPTIONAL)",
                        "plan_tier_usa_health": "string - bronze|silver|gold|platinum (OPTIONAL)",
                        # USA Homeowners Insurance Types
                        "coverage_type_usa_home": "string - replacement_cost|actual_cash_value (OPTIONAL)",
                        # USA Auto Insurance Types
                        "coverage_type_usa_auto": "string - liability_only|comprehensive|collision|full_coverage (OPTIONAL)",
                        # USA Life Insurance Types
                        "policy_type_usa_life": "string - term_life|whole_life|universal_life (OPTIONAL)",
                        # USA Liability Insurance Types
                        "policy_type_usa_liability": "string - professional_liability|general_liability|personal_liability (OPTIONAL)",
                        # General Policy Details
                        "policy_term_years": "number - Thời hạn hợp đồng (OPTIONAL)",
                        "policy_term_months": "number - For non-life insurance (OPTIONAL)",
                        "premium_frequency": "string - monthly|quarterly|semi_annual|annual (OPTIONAL)",
                        "coverage_amount": {
                            "min": "number - Minimum coverage (VND/USD) (OPTIONAL)",
                            "max": "number - Maximum coverage (VND/USD) (OPTIONAL)",
                        },
                    },
                    # Benefits Structure - ALL OPTIONAL
                    "benefits": {
                        # Vietnam Life Insurance Benefits
                        "death_benefit": "boolean - Quyền lợi tử vong (OPTIONAL)",
                        "survival_benefit": "boolean - Quyền lợi sinh kỳ (OPTIONAL)",
                        "maturity_benefit": "boolean - Quyền lợi đáo hạn (OPTIONAL)",
                        "cash_surrender_value": "boolean - Giá trị hoàn lại (OPTIONAL)",
                        "policy_loan_facility": "boolean - Vay theo hợp đồng (OPTIONAL)",
                        "retirement_pension": "boolean - Lương hưu trí (OPTIONAL)",
                        "investment_return": "boolean - Lợi nhuận đầu tư (OPTIONAL)",
                        # Health Insurance Benefits (Vietnam & USA)
                        "accident_coverage": "boolean - Tai nạn con người (OPTIONAL)",
                        "medical_treatment": "boolean - Điều trị y tế (OPTIONAL)",
                        "hospitalization": "boolean - Nội trú (OPTIONAL)",
                        "outpatient_care": "boolean - Ngoại trú (OPTIONAL)",
                        "emergency_care": "boolean - Cấp cứu (OPTIONAL)",
                        "maternity_care": "boolean - Thai sản (OPTIONAL)",
                        "dental_care": "boolean - Nha khoa (OPTIONAL)",
                        "vision_care": "boolean - Chăm sóc mắt (OPTIONAL)",
                        "preventive_care": "boolean - USA: Preventive care coverage (OPTIONAL)",
                        "prescription_drugs": "boolean - USA: Prescription drug coverage (OPTIONAL)",
                        "mental_health": "boolean - USA: Mental health coverage (OPTIONAL)",
                        "emergency_services": "boolean - USA: Emergency services coverage (OPTIONAL)",
                        # Vietnam Non-Life Insurance Benefits
                        "property_coverage": "boolean - Bảo hiểm tài sản (OPTIONAL)",
                        "civil_liability": "boolean - Trách nhiệm dân sự (OPTIONAL)",
                        "motor_vehicle_coverage": "boolean - Bảo hiểm xe cơ giới (OPTIONAL)",
                        "fire_explosion_coverage": "boolean - Cháy nổ (OPTIONAL)",
                        "natural_disaster_coverage": "boolean - Thiên tai (OPTIONAL)",
                        "agriculture_coverage": "boolean - Nông nghiệp (OPTIONAL)",
                    },
                    # Coverage Limits & Cost Sharing - ALL OPTIONAL
                    "coverage_limits": {
                        # General Coverage
                        "annual_limit": "number - Annual coverage limit (OPTIONAL)",
                        "per_incident_limit": "number - Per incident limit (OPTIONAL)",
                        "lifetime_limit": "number - Lifetime limit (OPTIONAL)",
                        # USA Specific Coverage Limits
                        "dwelling": "number - USA Homeowners: Dwelling coverage (USD) (OPTIONAL)",
                        "personal_property": "number - USA Homeowners: Personal property (USD) (OPTIONAL)",
                        "liability": "number - USA: Liability coverage (USD) (OPTIONAL)",
                        "medical_payments": "number - USA Homeowners: Medical payments (USD) (OPTIONAL)",
                        "bodily_injury_per_person": "number - USA Auto: Bodily injury per person (USD) (OPTIONAL)",
                        "bodily_injury_per_accident": "number - USA Auto: Bodily injury per accident (USD) (OPTIONAL)",
                        "property_damage": "number - USA Auto: Property damage (USD) (OPTIONAL)",
                        "comprehensive_deductible": "number - USA Auto: Comprehensive deductible (USD) (OPTIONAL)",
                        "collision_deductible": "number - USA Auto: Collision deductible (USD) (OPTIONAL)",
                        # Vietnam Non-Life Specific
                        "third_party_liability": "number - Vietnam: Bồi thường bên thứ ba (VND) (OPTIONAL)",
                        "own_damage": "number - Vietnam: Thiệt hại vật chất (VND) (OPTIONAL)",
                    },
                    "cost_sharing": {
                        "deductible": "number - Khấu trừ/Annual deductible (VND/USD) (OPTIONAL)",
                        "deductible_amount": "number - Alternative field name (OPTIONAL)",
                        "copayment_percentage": "number - Vietnam: Tỷ lệ đồng chi trả (%) (OPTIONAL)",
                        "copay_percentage": "number - Alternative field name (OPTIONAL)",
                        "out_of_pocket_maximum": "number - Tối đa tự chi trả/Annual out-of-pocket max (VND/USD) (OPTIONAL)",
                        "copay_primary_care": "number - USA: Primary care copay (USD) (OPTIONAL)",
                        "copay_specialist": "number - USA: Specialist copay (USD) (OPTIONAL)",
                        "coinsurance": "number - USA: Coinsurance percentage (%) (OPTIONAL)",
                        "maximum_liability": "number - Vietnam: Trách nhiệm tối đa (VND) (OPTIONAL)",
                    },
                    # Provider Networks - ALL OPTIONAL
                    "provider_network": {
                        "hospitals": ["array - Mạng lưới bệnh viện (OPTIONAL)"],
                        "clinics": ["array - Mạng lưới phòng khám (OPTIONAL)"],
                        "pharmacies": ["array - Mạng lưới nhà thuốc (OPTIONAL)"],
                        "direct_billing": "boolean - Thanh toán trực tiếp (OPTIONAL)",
                        "network_type": "string - USA: hmo|ppo|epo|pos (OPTIONAL)",
                        "in_network_providers": [
                            "array - USA: List of in-network providers (OPTIONAL)"
                        ],
                        "out_of_network_coverage": "boolean - USA: Out-of-network coverage available (OPTIONAL)",
                    },
                    # Eligibility & Restrictions - ALL OPTIONAL
                    "eligibility": {
                        "min_age": "number - Tuổi tối thiểu (Vietnam: 0-70, USA: varies) (OPTIONAL)",
                        "max_age": "number - Tuổi tối đa (Vietnam: 18-99, USA: varies) (OPTIONAL)",
                        "renewal_age_limit": "number - Age limit for renewal (OPTIONAL)",
                        "health_declaration_required": "boolean - Vietnam: Yêu cầu khai báo sức khỏe (OPTIONAL)",
                        "medical_exam_required": "boolean - Vietnam: Yêu cầu khám sức khỏe (OPTIONAL)",
                        "income_proof_required": "boolean - Vietnam: Yêu cầu chứng minh thu nhập (OPTIONAL)",
                        "pre_existing_conditions": "string - Vietnam: Bệnh có từ trước (OPTIONAL)",
                        "waiting_periods": "string - Vietnam: Thời gian chờ (OPTIONAL)",
                        "family_coverage": "boolean - Vietnam: Bảo hiểm gia đình (OPTIONAL)",
                        "geographic_restrictions": ["array - Covered areas (OPTIONAL)"],
                    },
                    # Premium & Payment Details - ALL OPTIONAL
                    "premium_details": {
                        "base_premium": "number - Base premium amount (OPTIONAL)",
                        "calculation_method": "string - Vietnam: Phương pháp tính phí (OPTIONAL)",
                        "payment_period": "string - Vietnam: Thời gian đóng phí (OPTIONAL)",
                        "grace_period_days": "number - Vietnam: Thời gian gia hạn đóng phí (OPTIONAL)",
                        "late_payment_penalty": "number - Vietnam: Phí phạt chậm đóng (VND) (OPTIONAL)",
                        "age_based_pricing": "boolean - Age-based pricing (OPTIONAL)",
                        "gender_based_pricing": "boolean - Gender-based pricing (OPTIONAL)",
                        "occupation_loading": "number - Occupation loading percentage (OPTIONAL)",
                        "health_loading": "number - Health loading percentage (OPTIONAL)",
                        "family_discounts": {
                            "spouse_discount": "number - Spouse discount percentage (OPTIONAL)",
                            "children_discount": "number - Children discount percentage (OPTIONAL)",
                        },
                    },
                    # Claims & Settlement - ALL OPTIONAL
                    "claims": {
                        "waiting_period_days": "number - Vietnam: Thời gian chờ bồi thường (OPTIONAL)",
                        "settlement_time_days": "number - Vietnam: Thời gian giải quyết (OPTIONAL)",
                        "required_documents": [
                            "array - Vietnam: Hồ sơ yêu cầu (OPTIONAL)"
                        ],
                        "exclusions": [
                            "array - Vietnam: Điều khoản loại trừ (OPTIONAL)"
                        ],
                    },
                    # Coverage Details (Non-Life specific) - ALL OPTIONAL
                    "coverage_details": {
                        "theft_coverage": "boolean - Vietnam: Bảo hiểm trộm cắp (OPTIONAL)",
                        "flood_coverage": "boolean - Vietnam: Bảo hiểm lũ lụt (OPTIONAL)",
                    },
                },
                "raw_data": {
                    "extracted_text": "string - Raw text content about this insurance (HIGHLY RECOMMENDED)",
                    "confidence_score": "number 0.0-1.0 - AI confidence in extraction",
                    "extraction_notes": "string - AI notes about extraction challenges",
                    "original_format": "string - Original data format/structure",
                    "file_section": "string - Which section of file this was extracted from",
                },
            }
        else:  # services
            return {
                "id": "number - Item ordering ID (1 to total items)",
                "name": "string - Service name (REQUIRED)",
                "content_for_embedding": "string - REQUIRED: Natural language description optimized for AI chatbot",
                "service_code": "string - Service code (optional)",
                "category": "string - claims|underwriting|advisory|support",
                "sub_category": "string - processing|assessment|consultation|customer_care",
                "price_type": "string - free|fixed|percentage|hourly",
                "price_min": "number - Minimum fee",
                "price_max": "number - Maximum fee",
                "currency": "string - VND|USD (smart detection: look for symbols $,đ,VNĐ in text, or use price analysis: ≥10k=VND, <3k=USD)",
                "duration_minutes": "number - Service duration",
                "availability": "string - 24_7|business_hours|by_appointment",
                "operating_hours": "string - Operating hours",
                "industry_data": {
                    "🔥 NOTE": "ALL FIELDS BELOW ARE OPTIONAL - extract what you can find, missing data won't cause failures",
                    "service_details": {
                        "processing_time": "string - expected processing time (OPTIONAL)",
                        "required_documents": [
                            "array of required documents (OPTIONAL)"
                        ],
                        "digital_submission": "boolean - (OPTIONAL)",
                        "in_person_required": "boolean - (OPTIONAL)",
                        "languages_supported": ["array of languages (OPTIONAL)"],
                    },
                    "claims_processing": {
                        "claim_types_covered": ["array of claim types (OPTIONAL)"],
                        "maximum_claim_amount": "number - (OPTIONAL)",
                        "settlement_timeframe": "string - days/weeks (OPTIONAL)",
                        "direct_settlement": "boolean - (OPTIONAL)",
                        "reimbursement_method": "string - bank_transfer|check|cash (OPTIONAL)",
                    },
                    "advisory_services": {
                        "consultation_type": "string - financial|risk|product (OPTIONAL)",
                        "advisor_qualifications": [
                            "array of qualifications (OPTIONAL)"
                        ],
                        "follow_up_included": "boolean - (OPTIONAL)",
                        "report_provided": "boolean - (OPTIONAL)",
                    },
                    "support_channels": {
                        "phone_support": "boolean - (OPTIONAL)",
                        "email_support": "boolean - (OPTIONAL)",
                        "live_chat": "boolean - (OPTIONAL)",
                        "mobile_app": "boolean - (OPTIONAL)",
                        "branch_visit": "boolean - (OPTIONAL)",
                    },
                    "fees_structure": {
                        "consultation_fee": "number - (OPTIONAL)",
                        "processing_fee": "number - (OPTIONAL)",
                        "administration_fee": "number - (OPTIONAL)",
                        "rush_processing_fee": "number - (OPTIONAL)",
                    },
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
            "required_fields": ["name", "category"],
            "price_min": 0,
            "price_max": 100000000000,  # 100B VND or equivalent maximum
        }

        if data_type == "products":
            base_rules["required_fields"].append("price")
            base_rules["valid_categories"] = [
                # Vietnam insurance categories
                "life_insurance",
                "health_insurance",
                "non_life_insurance",
                # USA insurance categories
                "health_insurance",
                "homeowners_insurance",
                "auto_insurance",
                "life_insurance",
                "liability_insurance",
            ]
            base_rules["valid_countries"] = ["vietnam", "usa"]
        else:
            base_rules["valid_categories"] = [
                "claims",
                "underwriting",
                "advisory",
                "support",
            ]

        return base_rules

    def post_process(
        self, extracted_data: Dict[str, Any], data_type: str
    ) -> Dict[str, Any]:
        """Post-process insurance data with multi-country support"""
        items = extracted_data.get(data_type, [])

        for idx, item in enumerate(items):
            # Add ID field for ordering
            item["id"] = idx + 1

            # Detect country and set currency using smart detection
            country = self._detect_country(item)
            currency = self._detect_currency(item, country)
            item["currency"] = currency

            # Set country in location if not present
            if "industry_data" not in item:
                item["industry_data"] = {}
            if "location" not in item["industry_data"]:
                item["industry_data"]["location"] = {}
            if country and not item["industry_data"]["location"].get("country"):
                item["industry_data"]["location"]["country"] = country

            # Generate product code
            if data_type == "products" and not item.get("sku"):
                category_code = self._get_insurance_category_code(
                    item.get("category", "")
                )
                country_code = "US" if country == "usa" else "VN"
                item["sku"] = f"INS-{country_code}-{category_code}-{idx+1:03d}"
            elif data_type == "services" and not item.get("service_code"):
                item["service_code"] = f"INS-SVC-{idx+1:03d}"

            # Set defaults for industry_data
            if "industry_data" not in item:
                item["industry_data"] = {}

            if data_type == "products":
                # Set policy details defaults
                policy_details = item["industry_data"].setdefault("policy_details", {})
                policy_details.setdefault("country", country)
                policy_details.setdefault("renewable", True)
                policy_details.setdefault("policy_type", "individual")

                # Set default coverage limits
                coverage_limits = item["industry_data"].setdefault(
                    "coverage_limits", {}
                )
                if country == "usa":
                    coverage_limits.setdefault("deductible_amount", 1000)  # $1000 USD
                else:
                    coverage_limits.setdefault("deductible_amount", 2000000)  # 2M VND

                # Set default conditions
                conditions = item["industry_data"].setdefault("policy_conditions", {})
                conditions.setdefault("waiting_period_days", 30)
                conditions.setdefault("pre_existing_conditions", "excluded")

                # Age restrictions
                age_restrictions = conditions.setdefault("age_restrictions", {})
                age_restrictions.setdefault("min_age", 18)
                age_restrictions.setdefault("max_age", 65)

            else:  # services
                # Set default service details
                service_details = item["industry_data"].setdefault(
                    "service_details", {}
                )
                service_details.setdefault("digital_submission", True)
                service_details.setdefault("languages_supported", ["vi", "en"])

                # Set default support channels
                support = item["industry_data"].setdefault("support_channels", {})
                support.setdefault("phone_support", True)
                support.setdefault("email_support", True)

            # Generate tags
            item["tags"] = list(
                set(
                    item.get("tags", [])
                    + self._generate_insurance_tags(item, data_type, country)
                )
            )

            # Set confidence score
            item.setdefault("confidence_score", 0.82)

        return extracted_data

    def get_post_processing_instructions(self) -> str:
        return """Post-Processing Instructions for Insurance Data:

1. MULTI-COUNTRY DETECTION & VALIDATION:
   - Determine country from location data, currency, or company names
   - Vietnam indicators: VND currency, Vietnamese company names (Bảo Việt, Prudential Việt Nam), Vietnamese terms
   - USA indicators: USD currency, US company names (Blue Cross, Aetna), English terms
   - If country cannot be determined, mark as unknown but still extract available data

2. CURRENCY DETECTION & STANDARDIZATION:
   - Primary: Look for explicit symbols: $, đ, VNĐ, VND in the text
   - Secondary: Price analysis - amounts ≥10,000 typically VND, amounts <3,000 typically USD
   - Final fallback: Use country context if available
   - Always specify currency in extracted data

3. INSURANCE TYPE CATEGORIZATION:
   Vietnam (3 categories):
   - life_insurance: sinh kỳ, tử kỳ, hỗn hợp, trọn đời, hưu trí, liên kết đầu tư
   - health_insurance: tai nạn con người, y tế thương mại, chăm sóc sức khỏe
   - non_life_insurance: tài sản, trách nhiệm dân sự, xe cơ giới, cháy nổ, thiên tai, nông nghiệp
   
   USA (5 categories):
   - health_insurance: medicaid, medicare, individual, family, employer-sponsored
   - homeowners_insurance: replacement cost, actual cash value coverage
   - auto_insurance: liability, comprehensive, collision, full coverage
   - life_insurance: term life, whole life, universal life
   - liability_insurance: professional, general, personal liability

4. VALIDATION RULES:
   - Required fields: name, price (for insurance products)
   - Optional approach: If industry_data fields are missing, still extract the product
   - Raw data backup: Always include extracted text for manual verification
   - Quality indicators: Set confidence_score based on completeness of extraction

5. FIELD-SPECIFIC PROCESSING:
   - Policy terms: Convert to standardized format (years/months)
   - Coverage amounts: Ensure currency consistency
   - Age limits: Validate against country-specific ranges
   - Benefits: Map to boolean values for coverage included/excluded
   - Provider networks: Extract as arrays of provider names

6. DATA CONSISTENCY:
   - Cross-validate coverage amounts with premium prices
   - Ensure benefit selections align with policy type
   - Check age restrictions against policy terms
   - Verify deductibles don't exceed coverage limits

7. FALLBACK HANDLING:
   - If specific industry data cannot be extracted, focus on core fields (name, price, category)
   - Use raw_data section to preserve original content
   - Mark confidence appropriately for partial extractions
   - Include extraction_notes for any issues encountered

8. QUALITY ASSURANCE:
   - All monetary amounts should have consistent currency
   - Boolean fields should be true/false, not strings
   - Array fields should contain actual arrays, not strings
   - Numeric fields should be numbers, not strings with numbers"""

    def _detect_country(self, item: Dict[str, Any]) -> str:
        """Detect country based on item content"""
        # Check for explicit country mention
        text = f"{item.get('name', '')} {item.get('description', '')}".lower()

        if any(
            keyword in text
            for keyword in ["usa", "united states", "america", "usd", "$"]
        ):
            return "usa"
        elif any(keyword in text for keyword in ["vietnam", "việt nam", "vnd", "vnđ"]):
            return "vietnam"

        # Check currency
        if item.get("currency") == "USD":
            return "usa"

        # Default to Vietnam
        return "vietnam"

    def _get_insurance_category_code(self, category: str) -> str:
        """Get category code for insurance products"""
        mapping = {
            # Vietnam categories
            "life_insurance": "LIFE",
            "health_insurance": "HLTH",
            "non_life_insurance": "NLIF",
            # USA categories
            "homeowners_insurance": "HOME",
            "auto_insurance": "AUTO",
            "liability_insurance": "LIAB",
            # Fallback for old categories
            "health": "HLTH",
            "life": "LIFE",
            "auto": "AUTO",
            "property": "PROP",
            "travel": "TRV",
            "liability": "LIAB",
        }
        return mapping.get(category, "INS")

    def _generate_insurance_tags(
        self, item: Dict[str, Any], data_type: str, country: str
    ) -> List[str]:
        """Generate insurance-specific tags"""
        tags = []

        # Category and country tags
        if item.get("category"):
            tags.append(item["category"])
        tags.append(country)

        if data_type == "products":
            # Coverage type tags
            coverage = item.get("industry_data", {}).get("coverage_benefits", {})
            if coverage.get("dental_coverage"):
                tags.append("dental")
            if coverage.get("vision_coverage"):
                tags.append("vision")
            if coverage.get("maternity_coverage"):
                tags.append("maternity")

            # Policy type tags
            policy_type = (
                item.get("industry_data", {})
                .get("policy_details", {})
                .get("policy_type")
            )
            if policy_type:
                tags.append(policy_type)

            # Premium level tags
            premium = item.get("price", 0)
            if country == "usa":
                if premium > 10000:  # > $10k USD
                    tags.append("premium")
                elif premium < 2000:  # < $2k USD
                    tags.append("basic")
            else:  # Vietnam
                if premium > 50000000:  # > 50M VND
                    tags.append("premium")
                elif premium < 5000000:  # < 5M VND
                    tags.append("basic")

        else:  # services
            # Service type tags
            if item.get("price_type") == "free":
                tags.append("complimentary")

            # Processing time tags
            processing_time = (
                item.get("industry_data", {})
                .get("service_details", {})
                .get("processing_time", "")
            )
            if "24" in processing_time or "immediate" in processing_time.lower():
                tags.append("fast_processing")

        return tags

    def _detect_currency(self, item: Dict[str, Any], country: str = None) -> str:
        """Smart currency detection with multiple fallback layers"""
        # Priority 1: Look for explicit currency symbols in text data
        raw_text = ""
        if "raw_data" in item and "extracted_text" in item["raw_data"]:
            raw_text = str(item["raw_data"]["extracted_text"]).lower()

        # Also check name and other text fields
        all_text = " ".join(
            [str(item.get("name", "")), str(item.get("description", "")), raw_text]
        ).lower()

        # Check for explicit currency symbols/codes
        if any(symbol in all_text for symbol in ["$", "usd", "dollar"]):
            return "USD"
        if any(symbol in all_text for symbol in ["đ", "vnd", "vnđ", "dong", "đồng"]):
            return "VND"

        # Priority 2: Price analysis for currency detection
        price = item.get("price", 0)
        if isinstance(price, (int, float)) and price > 0:
            # Amounts >= 10,000 typically VND, < 3,000 typically USD
            if price >= 10000:
                return "VND"
            elif price < 3000:
                return "USD"

        # Priority 3: Country context fallback
        if country == "usa":
            return "USD"
        elif country == "vietnam":
            return "VND"

        # Priority 4: Look for country indicators in location data
        location = item.get("industry_data", {}).get("location", {})
        detected_country = location.get("country", "").lower()
        if detected_country == "usa":
            return "USD"
        elif detected_country == "vietnam":
            return "VND"

        # Final fallback: default to VND
        return "VND"
