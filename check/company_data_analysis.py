#!/usr/bin/env python3
"""
Phân tích cụ thể cấu trúc company_data sẽ trả về
Detailed analysis of company_data structure returned by the system
"""

# ====================================================================================
# 📊 PHÂN TÍCH COMPANY_DATA STRUCTURE
# ====================================================================================

company_data_examples = {
    "search_results_raw": [
        {
            "chunk_id": "aia_001",
            "score": 0.95,
            "original_score": 0.85,
            "search_source": "comprehensive_hybrid_search",
            "content_for_rag": "Điều hòa Daikin 2 chiều 18000 BTU với công nghệ inverter tiết kiệm điện, khử khuẩn nano titanium. Giá bán: 15.500.000 VNĐ. Bảo hành 3 năm chính hãng.",
            "data_type": "products",
            "content_type": "extracted_product",  # QUAN TRỌNG: Trigger tối ưu
            "structured_data": {
                # CHỈ 2 FIELDS cho extracted_product/extracted_service
                "product_id": "DAIKIN_AC_18K_INV",
                "retrieval_context": "Điều hòa Daikin 2 chiều 18000 BTU với công nghệ inverter tiết kiệm điện, khử khuẩn nano titanium. Giá bán: 15.500.000 VNĐ. Bảo hành 3 năm chính hãng.",
                # KHÔNG CÓ: price, description, features, specifications, etc.
            },
            "file_id": "products_catalog_2025.pdf",
            "language": "vi",
            "created_at": "2025-08-15T10:30:00Z",
            "categories": [],  # Empty để tiết kiệm space
            "tags": [],  # Empty để tiết kiệm space
        },
        {
            "chunk_id": "aia_002",
            "score": 0.88,
            "original_score": 0.82,
            "search_source": "vector_search",
            "content_for_rag": "Công ty AIA chuyên cung cấp các sản phẩm điện lạnh chất lượng cao. Thành lập năm 2010, có showroom tại TP.HCM và Hà Nội. Hotline: 1900-xxx-xxx",
            "data_type": "company_info",
            "content_type": "company_profile",  # KHÔNG phải product/service
            "structured_data": {
                # FULL DATA cho content khác
                "company_name": "AIA Electronics",
                "founded_year": 2010,
                "locations": ["TP.HCM", "Hà Nội"],
                "phone": "1900-xxx-xxx",
                "specialization": "điện lạnh",
                "description": "chuyên cung cấp các sản phẩm điện lạnh chất lượng cao",
                "business_type": "retail",
                "certifications": ["ISO 9001", "Đại lý chính hãng"],
                "services": ["bảo hành", "lắp đặt", "sửa chữa"],
            },
            "file_id": "company_profile.pdf",
            "language": "vi",
            "created_at": "2025-08-10T14:20:00Z",
            "categories": ["company_info", "profile"],
            "tags": ["điện lạnh", "AIA", "showroom"],
        },
        {
            "chunk_id": "aia_003",
            "score": 0.75,
            "original_score": 0.70,
            "search_source": "scroll_search",
            "content_for_rag": "Dịch vụ lắp đặt điều hòa tận nhà trong ngày, bảo hành 2 năm. Đội ngũ kỹ thuật viên chuyên nghiệp với kinh nghiệm 10+ năm.",
            "data_type": "services",
            "content_type": "extracted_service",  # QUAN TRỌNG: Trigger tối ưu
            "structured_data": {
                # CHỈ 2 FIELDS cho extracted_service
                "product_id": "INSTALL_SERVICE_AC",
                "retrieval_context": "Dịch vụ lắp đặt điều hòa tận nhà trong ngày, bảo hành 2 năm. Đội ngũ kỹ thuật viên chuyên nghiệp với kinh nghiệm 10+ năm.",
                # KHÔNG CÓ: service_details, pricing_tiers, staff_info, etc.
            },
            "file_id": "services_catalog.pdf",
            "language": "vi",
            "created_at": "2025-08-12T09:15:00Z",
            "categories": [],  # Empty để tiết kiệm space
            "tags": [],  # Empty để tiết kiệm space
        },
    ],
    "formatted_company_data_output": """[DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]
[PRODUCTS] Điều hòa Daikin 2 chiều 18000 BTU với công nghệ inverter tiết kiệm điện, khử khuẩn nano titanium. Giá bán: 15.500.000 VNĐ. Bảo hành 3 năm chính hãng.

[COMPANY_INFO] Công ty AIA chuyên cung cấp các sản phẩm điện lạnh chất lượng cao. Thành lập năm 2010, có showroom tại TP.HCM và Hà Nội. Hotline: 1900-xxx-xxx

[SERVICES] Dịch vụ lắp đặt điều hòa tận nhà trong ngày, bảo hành 2 năm. Đội ngũ kỹ thuật viên chuyên nghiệp với kinh nghiệm 10+ năm.""",
}

# ====================================================================================
# 🎯 TỐI ỦU HÓA DỰA TRÊN CONTENT_TYPE
# ====================================================================================

optimization_analysis = {
    "before_optimization": {
        "extracted_product_data": {
            "chunk_id": "aia_001",
            "structured_data": {
                "product_id": "DAIKIN_AC_18K_INV",
                "name": "Điều hòa Daikin 2 chiều 18000 BTU",
                "price": 15500000,
                "currency": "VND",
                "description": "Với công nghệ inverter tiết kiệm điện",
                "features": ["inverter", "2 chiều", "khử khuẩn nano titanium"],
                "specifications": {
                    "capacity": "18000 BTU",
                    "type": "2 chiều",
                    "brand": "Daikin",
                    "energy_efficiency": "5 sao",
                },
                "warranty": "3 năm chính hãng",
                "availability": "Có sẵn",
                "category": "Điều hòa",
                "tags": ["inverter", "tiết kiệm điện", "daikin"],
                "images": ["daikin_ac_001.jpg"],
                "installation_service": True,
                "promotion": "Giảm 10% cho khách VIP",
                "retrieval_context": "Điều hòa Daikin 2 chiều 18000 BTU với công nghệ inverter tiết kiệm điện, khử khuẩn nano titanium. Giá bán: 15.500.000 VNĐ. Bảo hành 3 năm chính hãng.",
            },
        },
        "data_size": "~1.2KB per product chunk",
    },
    "after_optimization": {
        "extracted_product_data": {
            "chunk_id": "aia_001",
            "structured_data": {
                # CHỈ CÓN 2 FIELDS THIẾT YẾU
                "product_id": "DAIKIN_AC_18K_INV",
                "retrieval_context": "Điều hòa Daikin 2 chiều 18000 BTU với công nghệ inverter tiết kiệm điện, khử khuẩn nano titanium. Giá bán: 15.500.000 VNĐ. Bảo hành 3 năm chính hãng.",
            },
        },
        "data_size": "~300B per product chunk",
        "space_saved": "75% reduction",
    },
}

# ====================================================================================
# 📈 LUỒNG XỬ LÝ COMPANY_DATA
# ====================================================================================

processing_flow = {
    "step_1_search": {
        "function": "_hybrid_search_company_data_optimized()",
        "input": {"company_id": "aia", "query": "điều hòa daikin"},
        "qdrant_search": {
            "method": "comprehensive_hybrid_search()",
            "filters": {
                "company_id": "aia",
                "industry": "other",
                "score_threshold": 0.1,
            },
        },
    },
    "step_2_optimization": {
        "location": "qdrant_company_service.py:958-995",
        "logic": """
        if content_type in ["extracted_product", "extracted_service"]:
            # TỐI ỦU: CHỈ LẤY 2 FIELDS
            structured_data = {
                "product_id": product_id,
                "retrieval_context": retrieval_context
            }
        else:
            # ĐẦY ĐỦ: Giữ nguyên tất cả fields
            structured_data = payload.get("structured_data", {})
        """,
    },
    "step_3_formatting": {
        "location": "unified_chat_service.py:2196-2202",
        "format": """
        formatted_results.append(f"[{data_type.upper()}] {content.strip()}")

        result_text = "[DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]\\n" + "\\n\\n".join(formatted_results)
        """,
    },
    "step_4_prompt_injection": {
        "location": "unified_chat_service.py:664",
        "usage": """
        response = await self._build_unified_prompt_with_intent(
            company_data=company_data,  # <- String đã format
            user_context=user_context,
            company_context=company_context,
            products_list=products_list
        )
        """,
    },
}

# ====================================================================================
# 💡 VÍ DỤ THỰC TẾ COMPANY_DATA OUTPUT
# ====================================================================================

real_example = {
    "user_query": "Tôi muốn mua điều hòa Daikin 2 chiều",
    "company_data_returned": """[DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]
[PRODUCTS] Điều hòa Daikin 2 chiều 18000 BTU với công nghệ inverter tiết kiệm điện, khử khuẩn nano titanium. Giá bán: 15.500.000 VNĐ. Bảo hành 3 năm chính hãng.

[PRODUCTS] Điều hòa Daikin 1 chiều 12000 BTU tiết kiệm điện, có remote thông minh. Giá bán: 8.900.000 VNĐ. Tặng kèm dịch vụ lắp đặt miễn phí.

[SERVICES] Dịch vụ lắp đặt điều hòa tận nhà trong ngày, bảo hành 2 năm. Đội ngũ kỹ thuật viên chuyên nghiệp với kinh nghiệm 10+ năm.

[COMPANY_INFO] Công ty AIA chuyên cung cấp các sản phẩm điện lạnh chất lượng cao. Thành lập năm 2010, có showroom tại TP.HCM và Hà Nội. Hotline: 1900-xxx-xxx

[PRODUCTS] Máy lạnh trung tâm Daikin VRV cho văn phòng, công suất từ 2HP đến 20HP. Tiết kiệm 40% điện năng so với máy thường. Liên hệ để báo giá chi tiết.

[SERVICES] Bảo trì điều hòa định kỳ 6 tháng/lần, vệ sinh máy lạnh chuyên sâu. Ưu đãi 20% cho khách hàng thân thiết. Đội ngũ có chứng chỉ Daikin.""",
    "key_benefits": [
        "🎯 Products/Services: Chỉ product_id + retrieval_context (75% space saved)",
        "📄 Other content: Full structured_data preserved",
        "🔍 RAG quality: Retrieval_context optimized cho AI chat",
        "⚡ Performance: Giảm data transfer và prompt size",
        "📊 Scalability: Hệ thống scale tốt với database lớn",
    ],
}

if __name__ == "__main__":
    print("🔍 PHÂN TÍCH COMPANY_DATA STRUCTURE")
    print("=" * 80)

    print("\n📊 1. RAW SEARCH RESULTS (từ Qdrant):")
    print("-" * 50)
    for i, result in enumerate(company_data_examples["search_results_raw"], 1):
        print(f"\n{i}. Chunk: {result['chunk_id']}")
        print(f"   Content Type: {result['content_type']}")
        print(f"   Score: {result['score']}")

        if result["content_type"] in ["extracted_product", "extracted_service"]:
            print("   🎯 OPTIMIZED - Structured Data:")
            for key, value in result["structured_data"].items():
                print(f"      {key}: {str(value)[:60]}...")
        else:
            print("   📄 FULL DATA - Structured Data:")
            structured_keys = list(result["structured_data"].keys())
            print(f"      Keys: {structured_keys[:5]}...")
            print(f"      Total fields: {len(result['structured_data'])}")

    print("\n📝 2. FORMATTED COMPANY_DATA (gửi cho AI):")
    print("-" * 50)
    print(company_data_examples["formatted_company_data_output"])

    print("\n💡 3. TỐI ỦU HÓA HIỆU QUẢ:")
    print("-" * 50)
    before = optimization_analysis["before_optimization"]
    after = optimization_analysis["after_optimization"]

    print(f"   Before: {before['data_size']}")
    print(f"   After:  {after['data_size']}")
    print(f"   Saved:  {after['space_saved']}")

    print(f"\n🎯 4. KEY BENEFITS:")
    print("-" * 50)
    for benefit in real_example["key_benefits"]:
        print(f"   {benefit}")

    print(f"\n✅ Company_data là string đã format sẵn cho AI prompt!")
    print(f"   Không phải raw JSON, mà là text dễ đọc với [LABELS]")
