"""
Banking industry extraction template
Template extraction cho ngành ngân hàng
"""

from typing import Dict, Any, List
from .base_template import BaseExtractionTemplate


class BankingExtractionTemplate(BaseExtractionTemplate):
    """Banking products and services extraction"""

    def _get_industry(self) -> str:
        return "banking"

    def get_system_prompt(self, data_type: str) -> str:
        if data_type == "products":
            return """Extract banking products including:
            - Savings accounts with interest rates and terms
            - Credit cards with fees, limits, and benefits
            - Loans with rates, terms, and eligibility requirements
            - Investment products with returns and risks
            Include all rates, fees, minimum balances, and eligibility criteria.
            Pay attention to Vietnamese banking regulations and currency (VND).
            
            🔥 CRITICAL: Generate content_for_embedding field for each product - this is a natural language description optimized for AI chatbot responses.
            
            CONTENT_FOR_EMBEDDING FORMAT:
            - For accounts: "Tài khoản [type] [name]. [Description with key benefits]. Lãi suất [rate]%/năm. Số dư tối thiểu [minimum] VND. [Special features]."
            - For loans: "Khoản vay [type] [name]. [Description]. Lãi suất từ [rate]%/năm. Hạn mức [amount] VND. [Terms and conditions]."
            - For cards: "Thẻ [type] [name]. [Description with benefits]. Phí thường niên [fee] VND. [Rewards and features]."
            """
        else:  # services
            return """Extract banking services including:
            - Wealth management and advisory services
            - Investment consulting and portfolio management
            - Foreign exchange and remittance services
            - Business banking and corporate services
            Include fee structures, minimum amounts, and service requirements.
            
            🔥 CRITICAL: Generate content_for_embedding field for each service - this is a natural language description optimized for AI chatbot responses.
            
            CONTENT_FOR_EMBEDDING FORMAT:
            - "Dịch vụ [name]. [Description with key features]. Thuộc danh mục [category]. Phí dịch vụ [price] [currency]. [Requirements and benefits]."
            """

    def get_extraction_schema(self, data_type: str) -> Dict[str, Any]:
        if data_type == "products":
            return {
                "name": "string - Product name",
                "name_en": "string - English name (optional)",
                "description": "string - Detailed description",
                "content_for_embedding": "string - REQUIRED: Natural language description optimized for AI chatbot",
                "sku": "string - Product code",
                "category": "string - savings|checking|credit_card|loan|investment",
                "sub_category": "string - premium|standard|student|business|etc",
                "price": "number - Fee or minimum balance",
                "currency": "VND",
                "price_unit": "string - monthly_fee|annual_fee|minimum_balance|percentage",
                "availability": "string - available|limited|qualified_only",
                "tags": ["array of tags"],
                "images": ["array of image URLs"],
                "industry_data": {
                    "account_details": {
                        "account_type": "string - savings|checking|term_deposit",
                        "minimum_balance": "number - minimum balance required",
                        "maximum_balance": "number - maximum balance allowed",
                        "interest_rate": {
                            "base_rate": "number - annual percentage",
                            "promotional_rate": "number - promotional rate",
                            "calculation_method": "string - daily|monthly|quarterly",
                        },
                        "term_options": ["array - flexible|1m|3m|6m|12m|24m|36m"],
                    },
                    "loan_details": {
                        "loan_type": "string - personal|home|auto|business",
                        "loan_amount": {"minimum": "number", "maximum": "number"},
                        "interest_rate": {
                            "fixed_rate": "number - annual percentage",
                            "variable_rate": "number - annual percentage",
                            "apr": "number - annual percentage rate",
                        },
                        "loan_term": {
                            "minimum_months": "number",
                            "maximum_months": "number",
                        },
                        "collateral_required": "boolean",
                    },
                    "card_details": {
                        "card_type": "string - credit|debit|prepaid",
                        "credit_limit": {"minimum": "number", "maximum": "number"},
                        "annual_fee": "number",
                        "interest_rate": "number - monthly percentage",
                        "cashback_rate": "number - percentage",
                        "rewards_program": "string - description",
                    },
                    "fees_structure": {
                        "account_opening": "number",
                        "monthly_maintenance": "number",
                        "transaction_fees": {
                            "atm_withdrawal": "number",
                            "transfer_domestic": "number",
                            "transfer_international": "number or percentage",
                            "check_processing": "number",
                        },
                        "penalty_fees": {
                            "overdraft": "number",
                            "late_payment": "number",
                            "minimum_balance": "number",
                        },
                    },
                    "features": {
                        "online_banking": "boolean",
                        "mobile_app": "boolean",
                        "atm_access": "boolean",
                        "international_transfer": "boolean",
                        "investment_advisory": "boolean",
                    },
                    "eligibility": {
                        "minimum_age": "number",
                        "maximum_age": "number",
                        "income_requirement": "number - monthly income",
                        "credit_score": "string - requirement",
                        "employment_status": ["employed|self_employed|student|retired"],
                        "residency": ["citizen|permanent_resident|foreigner"],
                        "required_documents": ["array of required documents"],
                    },
                },
                "confidence_score": "number 0.0-1.0",
            }
        else:  # services
            return {
                "name": "string - Service name",
                "name_en": "string - English name (optional)",
                "description": "string - Service description",
                "content_for_embedding": "string - REQUIRED: Natural language description optimized for AI chatbot",
                "service_code": "string - Service code",
                "category": "string - wealth_management|investment|forex|advisory",
                "sub_category": "string - portfolio_mgmt|trading|consulting|etc",
                "price_type": "string - fixed|percentage|tiered|consultation",
                "price_min": "number - Minimum fee",
                "price_max": "number - Maximum fee",
                "currency": "VND",
                "duration_minutes": "number - Session duration (optional)",
                "availability": "string - available|by_appointment|qualified_only",
                "operating_hours": "string - Operating hours",
                "tags": ["array of tags"],
                "industry_data": {
                    "service_details": {
                        "minimum_portfolio": "number - minimum investment",
                        "management_fee_percentage": "number - annual percentage",
                        "performance_fee": "number - percentage",
                        "advisory_fee": "number - per session",
                        "transaction_fee": "number - per transaction",
                    },
                    "investment_options": {
                        "asset_classes": ["stocks|bonds|funds|forex|commodities"],
                        "risk_levels": ["conservative|moderate|aggressive"],
                        "investment_horizon": ["short_term|medium_term|long_term"],
                        "currency_options": ["VND|USD|EUR|JPY"],
                    },
                    "requirements": {
                        "minimum_investment": "number",
                        "risk_assessment_required": "boolean",
                        "financial_statement_required": "boolean",
                        "certification_required": "boolean",
                        "experience_level": "string - beginner|intermediate|advanced",
                    },
                    "service_features": {
                        "24_7_trading": "boolean",
                        "research_reports": "boolean",
                        "dedicated_advisor": "boolean",
                        "mobile_platform": "boolean",
                        "api_access": "boolean",
                    },
                },
                "confidence_score": "number 0.0-1.0",
            }

    def get_validation_rules(self, data_type: str) -> Dict[str, Any]:
        base_rules = {
            "required_fields": ["name", "category"],
            "price_min": 0,
            "price_max": 10000000000,  # 10B VND maximum
        }

        if data_type == "products":
            base_rules["valid_categories"] = [
                "savings",
                "checking",
                "credit_card",
                "loan",
                "investment",
            ]
        else:
            base_rules["valid_categories"] = [
                "wealth_management",
                "investment",
                "forex",
                "advisory",
            ]

        return base_rules

    def post_process(
        self, extracted_data: Dict[str, Any], data_type: str
    ) -> Dict[str, Any]:
        """Post-process banking data"""
        items = extracted_data.get(data_type, [])

        for idx, item in enumerate(items):
            # Set default currency
            item["currency"] = "VND"

            # Generate product code
            if data_type == "products" and not item.get("sku"):
                category_code = self._get_banking_category_code(
                    item.get("category", "")
                )
                item["sku"] = f"BANK-{category_code}-{idx+1:03d}"
            elif data_type == "services" and not item.get("service_code"):
                item["service_code"] = f"BANK-SVC-{idx+1:03d}"

            # Set defaults for industry_data
            if "industry_data" not in item:
                item["industry_data"] = {}

            if data_type == "products":
                # Set default eligibility
                eligibility = item["industry_data"].setdefault("eligibility", {})
                eligibility.setdefault("minimum_age", 18)
                eligibility.setdefault("residency", ["citizen", "permanent_resident"])

                # Set default features
                features = item["industry_data"].setdefault("features", {})
                features.setdefault("online_banking", True)
                features.setdefault("mobile_app", True)

                # Handle different product types
                category = item.get("category", "")
                if category == "savings":
                    account_details = item["industry_data"].setdefault(
                        "account_details", {}
                    )
                    account_details.setdefault("account_type", "savings")
                    account_details.setdefault("minimum_balance", 100000)  # 100k VND
                elif category == "loan":
                    loan_details = item["industry_data"].setdefault("loan_details", {})
                    loan_details.setdefault("collateral_required", True)
                elif category == "credit_card":
                    card_details = item["industry_data"].setdefault("card_details", {})
                    card_details.setdefault("card_type", "credit")

            else:  # services
                # Set default service requirements
                requirements = item["industry_data"].setdefault("requirements", {})
                requirements.setdefault("risk_assessment_required", True)

                # Set default features
                features = item["industry_data"].setdefault("service_features", {})
                features.setdefault("mobile_platform", True)

            # Generate tags
            item["tags"] = list(
                set(item.get("tags", []) + self._generate_banking_tags(item, data_type))
            )

            # Set confidence score
            item.setdefault("confidence_score", 0.85)

        return extracted_data

    def _get_banking_category_code(self, category: str) -> str:
        """Get category code for banking products"""
        mapping = {
            "savings": "SAV",
            "checking": "CHK",
            "credit_card": "CC",
            "loan": "LOAN",
            "investment": "INV",
        }
        return mapping.get(category, "PROD")

    def _generate_banking_tags(self, item: Dict[str, Any], data_type: str) -> List[str]:
        """Generate banking-specific tags"""
        tags = []

        # Category tags
        if item.get("category"):
            tags.append(item["category"])

        if data_type == "products":
            # Product-specific tags
            if item.get("category") == "savings":
                interest_rate = (
                    item.get("industry_data", {})
                    .get("account_details", {})
                    .get("interest_rate", {})
                    .get("base_rate", 0)
                )
                if interest_rate > 6:
                    tags.append("high_yield")

            elif item.get("category") == "credit_card":
                if item.get("price", 0) == 0:  # No annual fee
                    tags.append("no_annual_fee")
                cashback = (
                    item.get("industry_data", {})
                    .get("card_details", {})
                    .get("cashback_rate", 0)
                )
                if cashback > 0:
                    tags.append("cashback")

            elif item.get("category") == "loan":
                loan_type = (
                    item.get("industry_data", {})
                    .get("loan_details", {})
                    .get("loan_type")
                )
                if loan_type:
                    tags.append(loan_type)

            # Fee structure tags
            if item.get("price", 0) == 0:
                tags.append("free")

        else:  # services
            # Service-specific tags
            if item.get("price_type") == "percentage":
                tags.append("percentage_fee")

            min_investment = (
                item.get("industry_data", {})
                .get("requirements", {})
                .get("minimum_investment", 0)
            )
            if min_investment > 1000000000:  # 1B VND
                tags.append("premium")
            elif min_investment > 100000000:  # 100M VND
                tags.append("high_net_worth")

        return tags
