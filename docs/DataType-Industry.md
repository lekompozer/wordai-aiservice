self.backend_data_type_mapping = {
            "company_info": IndustryDataType.COMPANY_INFO,
            "products": IndustryDataType.PRODUCTS,  # Unified products for all industries
            "services": IndustryDataType.SERVICES,  # Unified services for all industries
            "policies": IndustryDataType.POLICIES,
            "faq": IndustryDataType.FAQ,
            "knowledge_base": IndustryDataType.KNOWLEDGE_BASE,
            "other": IndustryDataType.OTHER,

def _get_industry_name_vi(industry: Industry) -> str:
    """Get Vietnamese name for industry / Lấy tên tiếng Việt cho ngành"""
    names = {
        Industry.BANKING: "Ngân hàng",
        Industry.INSURANCE: "Bảo hiểm",
        Industry.RESTAURANT: "Nhà hàng",
        Industry.HOTEL: "Khách sạn",
        Industry.RETAIL: "Bán lẻ",
        Industry.FASHION: "Thời trang",
        Industry.INDUSTRIAL: "Công nghiệp",
        Industry.HEALTHCARE: "Y tế",
        Industry.EDUCATION: "Giáo dục",
        Industry.OTHER: "Khác",
    }
    return names.get(industry, industry.value)


def _get_industry_name_en(industry: Industry) -> str:
    """Get English name for industry / Lấy tên tiếng Anh cho ngành"""
    names = {
        Industry.BANKING: "Banking",
        Industry.INSURANCE: "Insurance",
        Industry.RESTAURANT: "Restaurant",
        Industry.HOTEL: "Hotel",
        Industry.RETAIL: "Retail",
        Industry.FASHION: "Fashion",
        Industry.INDUSTRIAL: "Industrial",
        Industry.HEALTHCARE: "Healthcare",
        Industry.EDUCATION: "Education",
        Industry.OTHER: "Other",