"""
Template Factory for industry-specific extraction
Factory quản lý template extraction theo ngành
"""

from typing import Type, Dict, Any, Optional
from .base_template import BaseExtractionTemplate
from .generic_template import GenericExtractionTemplate
from .restaurant_template import RestaurantExtractionTemplate
from .hotel_template import HotelExtractionTemplate
from .banking_template import BankingExtractionTemplate
from .insurance_template import InsuranceExtractionTemplate


class ExtractionTemplateFactory:
    """Factory for creating industry-specific extraction templates"""

    # Template registry
    _templates: Dict[str, Type[BaseExtractionTemplate]] = {
        "generic": GenericExtractionTemplate,
        "restaurant": RestaurantExtractionTemplate,
        "hotel": HotelExtractionTemplate,
        "banking": BankingExtractionTemplate,
        "insurance": InsuranceExtractionTemplate,
    }

    # Industry keywords for auto-detection
    _industry_keywords = {
        "restaurant": [
            "menu",
            "món ăn",
            "food",
            "dish",
            "restaurant",
            "nhà hàng",
            "phở",
            "bún",
            "cơm",
            "cuisine",
            "ẩm thực",
            "chef",
            "cooking",
            "dining",
            "bánh",
            "nước",
            "drink",
            "beverage",
            "appetizer",
            "main course",
            "dessert",
            "seafood",
            "vegetarian",
            "spicy",
        ],
        "hotel": [
            "hotel",
            "khách sạn",
            "room",
            "phòng",
            "booking",
            "đặt phòng",
            "amenities",
            "tiện ích",
            "spa",
            "pool",
            "hồ bơi",
            "resort",
            "accommodation",
            "check-in",
            "check-out",
            "suite",
            "deluxe",
            "standard",
            "facilities",
            "service",
            "concierge",
            "lobby",
        ],
        "banking": [
            "bank",
            "ngân hàng",
            "loan",
            "vay",
            "credit",
            "tín dụng",
            "account",
            "tài khoản",
            "interest",
            "lãi suất",
            "deposit",
            "tiền gửi",
            "transfer",
            "chuyển khoản",
            "card",
            "thẻ",
            "payment",
            "thanh toán",
            "investment",
            "đầu tư",
            "savings",
        ],
        "insurance": [
            "insurance",
            "bảo hiểm",
            "policy",
            "hợp đồng",
            "premium",
            "phí bảo hiểm",
            "coverage",
            "bảo vệ",
            "claim",
            "bồi thường",
            "health insurance",
            "bảo hiểm y tế",
            "life insurance",
            "bảo hiểm nhân thọ",
            "auto insurance",
            "deductible",
            "copay",
        ],
    }

    @classmethod
    def create_template(cls, industry: str) -> BaseExtractionTemplate:
        """Create extraction template for specific industry with robust enum handling"""
        # 🔧 ROBUST ENUM HANDLING: Handle all variations
        industry = str(industry).lower().strip()

        # Remove enum prefix if present: Industry.HOTEL -> hotel
        if industry.startswith("industry."):
            industry = industry.replace("industry.", "")

        # Remove any remaining dots or underscores for consistency
        industry = industry.replace("_", "")

        # Map variations to standard keys
        industry_mapping = {
            "hotel": "hotel",
            "hotels": "hotel",
            "hospitality": "hotel",
            "restaurant": "restaurant",
            "restaurants": "restaurant",
            "food": "restaurant",
            "banking": "banking",
            "bank": "banking",
            "finance": "banking",
            "financial": "banking",
            "insurance": "insurance",
            "insurances": "insurance",
            "assurance": "insurance",
        }

        # Apply mapping if available
        industry = industry_mapping.get(industry, industry)

        if industry not in cls._templates:
            print(f"⚠️  Industry '{industry}' not found, using generic template")
            print(f"   📋 Available templates: {list(cls._templates.keys())}")
            industry = "generic"
        else:
            print(f"✅ Using template: {industry}")

        template_class = cls._templates[industry]
        return template_class()

    @classmethod
    def detect_industry(cls, text: str) -> str:
        """Auto-detect industry from text content"""
        text_lower = text.lower()

        # Count keyword matches for each industry
        industry_scores = {}

        for industry, keywords in cls._industry_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                industry_scores[industry] = score

        if not industry_scores:
            return "generic"

        # Return industry with highest keyword match
        best_industry = max(industry_scores, key=industry_scores.get)
        best_score = industry_scores[best_industry]

        # Require minimum threshold (at least 2 matches)
        if best_score >= 2:
            print(f"🎯 Auto-detected industry: {best_industry} (score: {best_score})")
            return best_industry

        print(f"🤖 Using generic template (highest score: {best_score})")
        return "generic"

    @classmethod
    def get_available_industries(cls) -> list:
        """Get list of available industry templates"""
        return list(cls._templates.keys())

    @classmethod
    def register_template(
        cls, industry: str, template_class: Type[BaseExtractionTemplate]
    ):
        """Register new industry template"""
        cls._templates[industry] = template_class
        print(f"✅ Registered template for industry: {industry}")

    @classmethod
    def extract_with_auto_detection(
        cls, text: str, data_type: str = "products", industry_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract data with automatic industry detection"""

        # Use hint or detect industry
        if industry_hint:
            industry = industry_hint.lower()
            print(f"🎯 Using provided industry hint: {industry}")
        else:
            industry = cls.detect_industry(text)

        # Create template and extract
        template = cls.create_template(industry)

        print(f"🏭 Using {industry} template for {data_type} extraction")

        # Perform extraction
        try:
            result = template.extract(text, data_type)
            result["extraction_metadata"] = {
                "industry_detected": industry,
                "template_used": template.__class__.__name__,
                "auto_detection": industry_hint is None,
            }
            return result
        except Exception as e:
            print(f"❌ Extraction failed: {str(e)}")
            # Fallback to generic template
            if industry != "generic":
                print("🔄 Falling back to generic template...")
                generic_template = cls.create_template("generic")
                result = generic_template.extract(text, data_type)
                result["extraction_metadata"] = {
                    "industry_detected": "generic",
                    "template_used": generic_template.__class__.__name__,
                    "auto_detection": True,
                    "fallback_reason": f"Primary extraction failed: {str(e)}",
                }
                return result
            else:
                raise e

    @classmethod
    def extract_with_metadata(
        cls, text: str, data_type: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract data using metadata from backend (recommended method)"""

        # Get industry from metadata
        industry = metadata.get("industry", "generic")
        company_info = metadata.get("company_info", {})
        company_industry = company_info.get("industry", "generic")

        # Use company industry as primary, metadata industry as fallback
        final_industry = company_industry if company_industry != "generic" else industry
        final_industry = final_industry.lower().strip()

        print(f"🎯 Using industry from metadata: {final_industry}")

        # Create template and extract
        template = cls.create_template(final_industry)

        print(f"🏭 Using {final_industry} template for {data_type} extraction")

        # Perform extraction
        try:
            result = template.extract(text, data_type)
            result["extraction_metadata"] = {
                "industry_used": final_industry,
                "template_used": template.__class__.__name__,
                "source": "backend_metadata",
                "original_metadata": {
                    "file_name": metadata.get("original_name"),
                    "description": metadata.get("description"),
                    "tags": metadata.get("tags", []),
                    "company_id": company_info.get("company_id"),
                },
            }
            return result
        except Exception as e:
            print(f"❌ Extraction failed with {final_industry} template: {str(e)}")
            # Fallback to generic template
            if final_industry != "generic":
                print("🔄 Falling back to generic template...")
                generic_template = cls.create_template("generic")
                result = generic_template.extract(text, data_type)
                result["extraction_metadata"] = {
                    "industry_used": "generic",
                    "template_used": generic_template.__class__.__name__,
                    "source": "fallback",
                    "fallback_reason": f"Primary extraction failed: {str(e)}",
                    "original_metadata": {
                        "file_name": metadata.get("original_name"),
                        "description": metadata.get("description"),
                        "tags": metadata.get("tags", []),
                        "company_id": company_info.get("company_id"),
                    },
                }
                return result
            else:
                raise e

    @classmethod
    def get_template_with_metadata(
        cls, metadata: Dict[str, Any]
    ) -> BaseExtractionTemplate:
        """Get template using metadata with proper enum handling"""
        industry = metadata.get("industry", "generic")
        company_info = metadata.get("company_info", {})
        company_industry = company_info.get("industry", "generic")

        # Use company industry as primary, metadata industry as fallback
        final_industry = company_industry if company_industry != "generic" else industry

        # 🔧 FIX ENUM HANDLING: Convert Industry.HOTEL -> hotel
        final_industry = str(final_industry).lower().strip()
        if final_industry.startswith("industry."):
            final_industry = final_industry.replace("industry.", "")

        print(
            f"🏭 Template selection: '{metadata.get('industry')}' → '{final_industry}'"
        )
        return cls.create_template(final_industry)


# Utility functions
def extract_products_with_metadata(
    text: str, metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Extract products using backend metadata (recommended)"""
    return ExtractionTemplateFactory.extract_with_metadata(text, "products", metadata)


def extract_services_with_metadata(
    text: str, metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Extract services using backend metadata (recommended)"""
    return ExtractionTemplateFactory.extract_with_metadata(text, "services", metadata)


def extract_products_auto(
    text: str, industry_hint: Optional[str] = None
) -> Dict[str, Any]:
    """Extract products with auto-detection (legacy/testing only)"""
    return ExtractionTemplateFactory.extract_with_auto_detection(
        text, "products", industry_hint
    )


def extract_services_auto(
    text: str, industry_hint: Optional[str] = None
) -> Dict[str, Any]:
    """Extract services with auto-detection (legacy/testing only)"""
    return ExtractionTemplateFactory.extract_with_auto_detection(
        text, "services", industry_hint
    )


def get_industry_template(industry: str) -> BaseExtractionTemplate:
    """Quick function to get specific industry template"""
    return ExtractionTemplateFactory.create_template(industry)


# Example usage and testing
if __name__ == "__main__":
    # Test auto-detection
    test_texts = {
        "restaurant": "Menu của chúng tôi có phở bò, bún chả, cơm tấm",
        "hotel": "Khách sạn 5 sao với phòng deluxe, suite, spa và hồ bơi",
        "banking": "Ngân hàng cung cấp vay thế chấp, thẻ tín dụng và tiết kiệm",
        "insurance": "Bảo hiểm y tế với phí bảo hiểm ưu đãi và bồi thường nhanh",
        "generic": "Sản phẩm chất lượng cao với giá cả hợp lý",
    }

    factory = ExtractionTemplateFactory()

    print("🧪 Testing Industry Auto-Detection:")
    print("=" * 50)

    for expected_industry, text in test_texts.items():
        detected = factory.detect_industry(text)
        status = "✅" if detected == expected_industry else "❌"
        print(f"{status} Text: {text[:50]}...")
        print(f"   Expected: {expected_industry}, Detected: {detected}")
        print()

    print("🏭 Available Industries:")
    print(", ".join(factory.get_available_industries()))
