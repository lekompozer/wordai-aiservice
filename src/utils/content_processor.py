"""
Content Processing Utilities for RAG Optimization
Tiện ích xử lý nội dung để tối ưu RAG
"""

from typing import Dict, Any, Optional
from src.models.unified_models import Industry, IndustryDataType


class ContentForEmbeddingProcessor:
    """
    Processor to convert structured data into natural language content optimized for AI embedding
    Bộ xử lý chuyển đổi dữ liệu có cấu trúc thành nội dung ngôn ngữ tự nhiên tối ưu cho AI embedding
    """

    @staticmethod
    def process_company_info(data: Dict[str, Any], industry: Industry) -> str:
        """
        Convert company basic info to embedding-optimized text
        Chuyển đổi thông tin cơ bản công ty thành văn bản tối ưu embedding
        """
        parts = []

        # Company name and industry
        if data.get("company_name"):
            industry_desc = ContentForEmbeddingProcessor._get_industry_description(
                industry
            )
            parts.append(f"{data['company_name']} là {industry_desc}")

        # Address
        if data.get("address"):
            parts.append(f"Địa chỉ tại {data['address']}")

        # Contact info
        contact_parts = []
        if data.get("phone"):
            contact_parts.append(f"số điện thoại {data['phone']}")
        if data.get("email"):
            contact_parts.append(f"email {data['email']}")
        if data.get("website"):
            contact_parts.append(f"website {data['website']}")

        if contact_parts:
            parts.append(f"Liên hệ qua {', '.join(contact_parts)}")

        # Operating hours
        if data.get("operating_hours"):
            parts.append(f"Giờ hoạt động: {data['operating_hours']}")

        # Description
        if data.get("description"):
            parts.append(data["description"])

        return ". ".join(parts) + "."

    @staticmethod
    def process_product(data: Dict[str, Any], industry: Industry) -> str:
        """
        Convert product data to embedding-optimized text by industry
        Chuyển đổi dữ liệu sản phẩm thành văn bản tối ưu embedding theo ngành
        """
        if industry == Industry.RESTAURANT:
            return ContentForEmbeddingProcessor._process_restaurant_product(data)
        elif industry == Industry.HOTEL:
            return ContentForEmbeddingProcessor._process_hotel_product(data)
        elif industry == Industry.BANKING:
            return ContentForEmbeddingProcessor._process_banking_product(data)
        elif industry == Industry.RETAIL:
            return ContentForEmbeddingProcessor._process_retail_product(data)
        else:
            return ContentForEmbeddingProcessor._process_generic_product(data)

    @staticmethod
    def process_service(data: Dict[str, Any], industry: Industry) -> str:
        """
        Convert service data to embedding-optimized text by industry
        Chuyển đổi dữ liệu dịch vụ thành văn bản tối ưu embedding theo ngành
        """
        if industry == Industry.RESTAURANT:
            return ContentForEmbeddingProcessor._process_restaurant_service(data)
        elif industry == Industry.HOTEL:
            return ContentForEmbeddingProcessor._process_hotel_service(data)
        elif industry == Industry.BANKING:
            return ContentForEmbeddingProcessor._process_banking_service(data)
        elif industry == Industry.HEALTHCARE:
            return ContentForEmbeddingProcessor._process_healthcare_service(data)
        else:
            return ContentForEmbeddingProcessor._process_generic_service(data)

    @staticmethod
    def process_image_description(data: Dict[str, Any], industry: Industry) -> str:
        """
        Convert image metadata to detailed description for embedding
        Chuyển đổi metadata hình ảnh thành mô tả chi tiết cho embedding
        """
        parts = []

        # Main description
        if data.get("ai_description"):
            parts.append(data["ai_description"])
        elif data.get("description"):
            parts.append(f"Hình ảnh về {data['description']}")

        # Context based on industry
        if industry == Industry.RESTAURANT and data.get("category"):
            parts.append(f"Thuộc danh mục {data['category']} của nhà hàng")
        elif industry == Industry.HOTEL and data.get("room_type"):
            parts.append(f"Hình ảnh phòng loại {data['room_type']}")

        # Alt text
        if data.get("alt_text"):
            parts.append(data["alt_text"])

        # Folder context
        if data.get("folder_name"):
            parts.append(f"Nằm trong thư mục {data['folder_name']}")

        return ". ".join(parts) + "."

    # Industry-specific product processors
    @staticmethod
    def _process_restaurant_product(data: Dict[str, Any]) -> str:
        """Process restaurant menu items"""
        parts = []

        if data.get("name"):
            parts.append(f"Món ăn: {data['name']}")

        if data.get("description"):
            parts.append(f"Mô tả: {data['description']}")

        if data.get("category"):
            parts.append(f"Thuộc danh mục: {data['category']}")

        if data.get("price"):
            currency = data.get("currency", "VND")
            parts.append(f"Giá: {data['price']:,} {currency}")

        if data.get("ingredients"):
            if isinstance(data["ingredients"], list):
                ingredients = ", ".join(data["ingredients"])
            else:
                ingredients = data["ingredients"]
            parts.append(f"Nguyên liệu: {ingredients}")

        if data.get("cooking_time"):
            parts.append(f"Thời gian chế biến: {data['cooking_time']} phút")

        if data.get("spicy_level"):
            parts.append(f"Độ cay: {data['spicy_level']}")

        if data.get("available") is False:
            parts.append("Hiện tại tạm hết")

        return ". ".join(parts) + "."

    @staticmethod
    def _process_hotel_product(data: Dict[str, Any]) -> str:
        """Process hotel room types"""
        parts = []

        if data.get("name"):
            parts.append(f"Loại phòng: {data['name']}")

        if data.get("description"):
            parts.append(f"Mô tả: {data['description']}")

        if data.get("price_per_night"):
            currency = data.get("currency", "VND")
            parts.append(f"Giá mỗi đêm: {data['price_per_night']:,} {currency}")

        if data.get("max_guests"):
            parts.append(f"Số khách tối đa: {data['max_guests']} người")

        if data.get("bed_type"):
            parts.append(f"Loại giường: {data['bed_type']}")

        if data.get("room_size"):
            parts.append(f"Diện tích: {data['room_size']} m²")

        if data.get("amenities"):
            if isinstance(data["amenities"], list):
                amenities = ", ".join(data["amenities"])
            else:
                amenities = data["amenities"]
            parts.append(f"Tiện nghi: {amenities}")

        if data.get("view"):
            parts.append(f"Tầm nhìn: {data['view']}")

        return ". ".join(parts) + "."

    @staticmethod
    def _process_banking_product(data: Dict[str, Any]) -> str:
        """Process banking loan products"""
        parts = []

        if data.get("name"):
            parts.append(f"Sản phẩm tín dụng: {data['name']}")

        if data.get("description"):
            parts.append(f"Mô tả: {data['description']}")

        if data.get("interest_rate"):
            parts.append(f"Lãi suất: {data['interest_rate']}%/năm")

        if data.get("min_amount"):
            currency = data.get("currency", "VND")
            parts.append(f"Số tiền vay tối thiểu: {data['min_amount']:,} {currency}")

        if data.get("max_amount"):
            currency = data.get("currency", "VND")
            parts.append(f"Số tiền vay tối đa: {data['max_amount']:,} {currency}")

        if data.get("loan_term"):
            parts.append(f"Thời hạn vay: {data['loan_term']} tháng")

        if data.get("requirements"):
            if isinstance(data["requirements"], list):
                requirements = ", ".join(data["requirements"])
            else:
                requirements = data["requirements"]
            parts.append(f"Điều kiện: {requirements}")

        return ". ".join(parts) + "."

    @staticmethod
    def _process_retail_product(data: Dict[str, Any]) -> str:
        """Process retail products"""
        parts = []

        if data.get("name"):
            parts.append(f"Sản phẩm: {data['name']}")

        if data.get("brand"):
            parts.append(f"Thương hiệu: {data['brand']}")

        if data.get("category"):
            parts.append(f"Danh mục: {data['category']}")

        if data.get("price"):
            currency = data.get("currency", "VND")
            parts.append(f"Giá: {data['price']:,} {currency}")

        if data.get("description"):
            parts.append(f"Mô tả: {data['description']}")

        if data.get("specifications"):
            specs = data["specifications"]
            if isinstance(specs, dict):
                spec_parts = [f"{k}: {v}" for k, v in specs.items()]
                parts.append(f"Thông số: {', '.join(spec_parts)}")
            else:
                parts.append(f"Thông số: {specs}")

        if data.get("in_stock") is False:
            parts.append("Hiện tại hết hàng")

        return ". ".join(parts) + "."

    @staticmethod
    def _process_generic_product(data: Dict[str, Any]) -> str:
        """Process generic products"""
        parts = []

        if data.get("name"):
            parts.append(f"Sản phẩm: {data['name']}")

        if data.get("description"):
            parts.append(f"Mô tả: {data['description']}")

        if data.get("category"):
            parts.append(f"Danh mục: {data['category']}")

        if data.get("price"):
            currency = data.get("currency", "VND")
            parts.append(f"Giá: {data['price']:,} {currency}")

        return ". ".join(parts) + "."

    # Industry-specific service processors
    @staticmethod
    def _process_restaurant_service(data: Dict[str, Any]) -> str:
        """Process restaurant services"""
        parts = []

        if data.get("name"):
            parts.append(f"Dịch vụ nhà hàng: {data['name']}")

        if data.get("description"):
            parts.append(f"Mô tả: {data['description']}")

        if data.get("price"):
            currency = data.get("currency", "VND")
            parts.append(f"Giá: {data['price']:,} {currency}")

        if data.get("duration"):
            parts.append(f"Thời gian: {data['duration']}")

        if data.get("capacity"):
            parts.append(f"Sức chứa: {data['capacity']} người")

        return ". ".join(parts) + "."

    @staticmethod
    def _process_hotel_service(data: Dict[str, Any]) -> str:
        """Process hotel services"""
        parts = []

        if data.get("name"):
            parts.append(f"Dịch vụ khách sạn: {data['name']}")

        if data.get("description"):
            parts.append(f"Mô tả: {data['description']}")

        if data.get("price"):
            currency = data.get("currency", "VND")
            parts.append(f"Giá: {data['price']:,} {currency}")

        if data.get("operating_hours"):
            parts.append(f"Giờ hoạt động: {data['operating_hours']}")

        if data.get("location"):
            parts.append(f"Vị trí: {data['location']}")

        return ". ".join(parts) + "."

    @staticmethod
    def _process_banking_service(data: Dict[str, Any]) -> str:
        """Process banking services"""
        parts = []

        if data.get("name"):
            parts.append(f"Dịch vụ ngân hàng: {data['name']}")

        if data.get("description"):
            parts.append(f"Mô tả: {data['description']}")

        if data.get("fee"):
            currency = data.get("currency", "VND")
            parts.append(f"Phí dịch vụ: {data['fee']:,} {currency}")

        if data.get("processing_time"):
            parts.append(f"Thời gian xử lý: {data['processing_time']}")

        if data.get("requirements"):
            if isinstance(data["requirements"], list):
                requirements = ", ".join(data["requirements"])
            else:
                requirements = data["requirements"]
            parts.append(f"Yêu cầu: {requirements}")

        return ". ".join(parts) + "."

    @staticmethod
    def _process_healthcare_service(data: Dict[str, Any]) -> str:
        """Process healthcare services"""
        parts = []

        if data.get("name"):
            parts.append(f"Dịch vụ y tế: {data['name']}")

        if data.get("department"):
            parts.append(f"Khoa: {data['department']}")

        if data.get("description"):
            parts.append(f"Mô tả: {data['description']}")

        if data.get("doctor"):
            parts.append(f"Bác sĩ: {data['doctor']}")

        if data.get("price"):
            currency = data.get("currency", "VND")
            parts.append(f"Chi phí: {data['price']:,} {currency}")

        if data.get("duration"):
            parts.append(f"Thời gian: {data['duration']} phút")

        return ". ".join(parts) + "."

    @staticmethod
    def _process_generic_service(data: Dict[str, Any]) -> str:
        """Process generic services"""
        parts = []

        if data.get("name"):
            parts.append(f"Dịch vụ: {data['name']}")

        if data.get("description"):
            parts.append(f"Mô tả: {data['description']}")

        if data.get("price"):
            currency = data.get("currency", "VND")
            parts.append(f"Giá: {data['price']:,} {currency}")

        return ". ".join(parts) + "."

    @staticmethod
    def _get_industry_description(industry: Industry) -> str:
        """Get natural language description for industry"""
        descriptions = {
            Industry.RESTAURANT: "một nhà hàng",
            Industry.HOTEL: "một khách sạn",
            Industry.BANKING: "một ngân hàng",
            Industry.HEALTHCARE: "một cơ sở y tế",
            Industry.EDUCATION: "một cơ sở giáo dục",
            Industry.RETAIL: "một cửa hàng bán lẻ",
            Industry.FASHION: "một cửa hàng thời trang",
            Industry.INDUSTRIAL: "một công ty công nghiệp",
            Industry.INSURANCE: "một công ty bảo hiểm",
            Industry.REAL_ESTATE: "một công ty bất động sản",
            Industry.AUTOMOTIVE: "một công ty ô tô",
            Industry.TECHNOLOGY: "một công ty công nghệ",
            Industry.CONSULTING: "một công ty tư vấn",
            Industry.LOGISTICS: "một công ty logistics",
            Industry.MANUFACTURING: "một công ty sản xuất",
        }
        return descriptions.get(industry, "một doanh nghiệp")

    @staticmethod
    def create_content_for_embedding(
        original_content: str,
        structured_data: Optional[Dict[str, Any]],
        content_type: IndustryDataType,
        industry: Industry,
    ) -> str:
        """
        Create optimized content for embedding based on content type and industry
        Tạo nội dung tối ưu cho embedding dựa trên loại nội dung và ngành
        """
        if not structured_data:
            return original_content

        try:
            if content_type == IndustryDataType.COMPANY_INFO:
                return ContentForEmbeddingProcessor.process_company_info(
                    structured_data, industry
                )
            elif content_type == IndustryDataType.PRODUCTS:
                return ContentForEmbeddingProcessor.process_product(
                    structured_data, industry
                )
            elif content_type == IndustryDataType.SERVICES:
                return ContentForEmbeddingProcessor.process_service(
                    structured_data, industry
                )
            elif content_type == IndustryDataType.IMAGE_INFO:
                return ContentForEmbeddingProcessor.process_image_description(
                    structured_data, industry
                )
            else:
                # For FAQ, KNOWLEDGE_BASE, POLICIES, etc., use original content
                return original_content
        except Exception as e:
            # Fallback to original content if processing fails
            return original_content
