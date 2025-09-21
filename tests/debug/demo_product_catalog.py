"""
Demo Script - Test ProductCatalogService thực tế
Kịch bản demo đầy đủ cho hệ thống quản lý sản phẩm nội bộ

Usage:
python demo_product_catalog.py
"""

import asyncio
import json
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.product_catalog_service import get_product_catalog_service


async def demo_restaurant_scenario():
    """Demo kịch bản nhà hàng - đăng ký và quản lý món ăn"""
    print("\n🍜 === DEMO RESTAURANT SCENARIO ===")

    service = await get_product_catalog_service()
    company_id = "restaurant_pho_24"

    print(f"📋 Company ID: {company_id}")

    # Sample menu items
    menu_items = [
        {
            "name": "Phở Bò Tái",
            "description": "Phở bò tái nạm chín với bánh phở tươi",
            "price": 65000,
            "quantity": 50,
            "category": "Món chính",
            "tags": ["phở", "bò", "nước dùng"],
            "currency": "VND",
        },
        {
            "name": "Phở Gà",
            "description": "Phở gà thơm ngon với thịt gà tươi",
            "price": 60000,
            "quantity": 30,
            "category": "Món chính",
            "tags": ["phở", "gà"],
            "currency": "VND",
        },
        {
            "name": "Bún Chả",
            "description": "Bún chả Hà Nội với thịt nướng thơm",
            "price": 70000,
            "quantity": 25,
            "category": "Món chính",
            "tags": ["bún", "thịt nướng"],
            "currency": "VND",
        },
        {
            "name": "Chả Cá Lã Vọng",
            "description": "Chả cá truyền thống với bánh tráng",
            "price": 120000,
            "quantity": 0,  # Out of stock
            "category": "Đặc sản",
            "tags": ["cá", "đặc sản"],
            "currency": "VND",
        },
    ]

    # Register all menu items
    print("\n📝 Đăng ký các món ăn...")
    registered_items = []

    for item_data in menu_items:
        result = await service.register_item(
            item_data=item_data, company_id=company_id, item_type="product"
        )
        registered_items.append(result)

        if "product_id" in result:
            print(f"✅ Đã đăng ký: {result['name']} (ID: {result['product_id']})")
        else:
            print(f"❌ Lỗi đăng ký: {result['name']}")

    # Get catalog for AI prompt - tìm phở
    print("\n🤖 AI Prompt Data - Tìm 'phở':")
    pho_catalog = await service.get_catalog_for_prompt(
        company_id=company_id, query="phở", limit=5
    )

    print(json.dumps(pho_catalog, indent=2, ensure_ascii=False))

    # Get full catalog
    print("\n📋 Full Catalog for AI:")
    full_catalog = await service.get_catalog_for_prompt(
        company_id=company_id, query="", limit=10
    )

    for item in full_catalog:
        status = "✅" if item["quantity_raw"] > 0 else "❌"
        print(
            f"{status} {item['name']}: {item['quantity_display']} - {item['price_display']}"
        )

    # Test search by name
    print("\n🔍 Tìm sản phẩm theo tên...")
    found_pho = await service.find_by_name(company_id, "phở bò")
    if found_pho:
        print(
            f"✅ Tìm thấy: {found_pho['name']} (ID: {found_pho.get('product_id', 'N/A')})"
        )

    # Update quantity - khách đặt 2 tô phở bò
    if registered_items[0].get("product_id"):
        product_id = registered_items[0]["product_id"]
        print(f"\n📦 Cập nhật số lượng (bán 2 tô phở bò)...")

        # Current quantity
        current_item = await service.get_by_id(product_id)
        if current_item:
            current_qty = current_item.get("quantity", 0)
            new_qty = current_qty - 2

            success = await service.update_quantity(product_id, new_qty)
            if success:
                print(f"✅ Cập nhật thành công: {current_qty} → {new_qty}")
            else:
                print("❌ Lỗi cập nhật số lượng")

    # Get company statistics
    print("\n📊 Thống kê danh mục:")
    stats = await service.get_company_stats(company_id)
    print(f"- Sản phẩm: {stats['products']}")
    print(f"- Dịch vụ: {stats['services']}")
    print(f"- Tổng: {stats['total']}")


async def demo_hotel_scenario():
    """Demo kịch bản khách sạn - đăng ký phòng và dịch vụ"""
    print("\n🏨 === DEMO HOTEL SCENARIO ===")

    service = await get_product_catalog_service()
    company_id = "hotel_sunrise_danang"

    print(f"📋 Company ID: {company_id}")

    # Hotel rooms and services
    hotel_items = [
        {
            "name": "Phòng Deluxe Double",
            "description": "Phòng deluxe view biển với 2 giường đôi",
            "price": 1200000,
            "quantity": 5,  # 5 phòng trống
            "category": "Accommodation",
            "tags": ["deluxe", "sea view", "double bed"],
            "currency": "VND",
        },
        {
            "name": "Phòng VIP Suite",
            "description": "Suite cao cấp với ban công riêng",
            "price": 2500000,
            "quantity": 2,
            "category": "Accommodation",
            "tags": ["vip", "suite", "balcony"],
            "currency": "VND",
        },
        {
            "name": "Massage Therapy",
            "description": "Dịch vụ massage thư giãn 60 phút",
            "price": 500000,
            "quantity": -1,  # Service không track quantity
            "category": "Spa Services",
            "tags": ["massage", "therapy", "relaxation"],
            "currency": "VND",
        },
        {
            "name": "Airport Transfer",
            "description": "Dịch vụ đưa đón sân bay",
            "price": 300000,
            "quantity": -1,
            "category": "Transportation",
            "tags": ["airport", "transfer", "transport"],
            "currency": "VND",
        },
    ]

    print("\n📝 Đăng ký rooms & services...")
    registered_services = []

    for item_data in hotel_items:
        # Determine type based on category
        item_type = (
            "service"
            if item_data["category"] in ["Spa Services", "Transportation"]
            else "product"
        )

        result = await service.register_item(
            item_data=item_data, company_id=company_id, item_type=item_type
        )
        registered_services.append(result)

        id_key = "service_id" if item_type == "service" else "product_id"
        if id_key in result:
            print(f"✅ Đã đăng ký: {result['name']} (ID: {result[id_key]})")

    # Get catalog for availability checking
    print("\n🏨 Hotel Availability for AI:")
    availability_data = await service.get_catalog_for_prompt(
        company_id=company_id, query="phòng", limit=5
    )

    for item in availability_data:
        if item["quantity_raw"] > 0:
            print(
                f"✅ {item['name']}: {item['quantity_display']} - {item['price_display']}"
            )
        elif item["quantity_raw"] == 0:
            print(f"❌ {item['name']}: Hết phòng - {item['price_display']}")
        else:
            print(
                f"🔄 {item['name']}: {item['quantity_display']} - {item['price_display']}"
            )

    # Test booking simulation - book 1 deluxe room
    print("\n📋 Booking Simulation...")
    room_found = await service.find_by_name(company_id, "phòng deluxe")
    if room_found and room_found.get("quantity", 0) > 0:
        room_id = room_found.get("product_id")
        current_qty = room_found.get("quantity", 0)

        if room_id:
            success = await service.update_quantity(room_id, current_qty - 1)
            if success:
                print(f"✅ Đặt phòng thành công: {room_found['name']}")
                print(f"   Còn lại: {current_qty - 1} phòng")

    # Company stats
    print("\n📊 Hotel Statistics:")
    stats = await service.get_company_stats(company_id)
    print(f"- Phòng/Sản phẩm: {stats['products']}")
    print(f"- Dịch vụ: {stats['services']}")
    print(f"- Tổng: {stats['total']}")


async def demo_ai_prompt_integration():
    """Demo tích hợp dữ liệu catalog vào AI prompt"""
    print("\n🤖 === DEMO AI PROMPT INTEGRATION ===")

    service = await get_product_catalog_service()
    company_id = "restaurant_pho_24"

    # Simulate AI query scenarios
    scenarios = [
        {
            "user_query": "Có phở gì không?",
            "search_term": "phở",
            "description": "User hỏi về món phở",
        },
        {
            "user_query": "Món nào còn hàng?",
            "search_term": "",
            "description": "User hỏi về tình trạng kho",
        },
        {
            "user_query": "Bún chả bao nhiều tiền?",
            "search_term": "bún chả",
            "description": "User hỏi giá món bún chả",
        },
    ]

    for scenario in scenarios:
        print(f"\n📝 Scenario: {scenario['description']}")
        print(f"   User: '{scenario['user_query']}'")

        # Get catalog data for AI prompt
        catalog_data = await service.get_catalog_for_prompt(
            company_id=company_id, query=scenario["search_term"], limit=3
        )

        print("   AI Context Data:")
        if catalog_data:
            for item in catalog_data:
                availability = "Còn hàng" if item["quantity_raw"] > 0 else "Hết hàng"
                print(f"   - {item['name']}: {availability}, {item['price_display']}")
        else:
            print("   - Không tìm thấy sản phẩm phù hợp")


async def main():
    """Run all demo scenarios"""
    print("🚀 ProductCatalogService Demo Started")
    print("=" * 50)

    try:
        # Run restaurant demo
        await demo_restaurant_scenario()

        # Run hotel demo
        await demo_hotel_scenario()

        # Run AI integration demo
        await demo_ai_prompt_integration()

        print("\n" + "=" * 50)
        print("✅ Demo hoàn thành thành công!")
        print(
            "🔍 Kiểm tra MongoDB collection 'internal_products_catalog' để xem dữ liệu"
        )

    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run async demo
    asyncio.run(main())
