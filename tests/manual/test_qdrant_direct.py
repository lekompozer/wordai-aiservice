#!/usr/bin/env python3
"""
Kiểm tra trực tiếp Qdrant data cho Ivy Fashion Store
"""

import asyncio
import sys
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.services.qdrant_company_service import QdrantCompanyDataService

# Direct Qdrant credentials
QDRANT_URL = (
    "https://f9614d10-66f5-4669-9629-617c14876551.us-east4-0.gcp.cloud.qdrant.io"
)
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.gNFcCArqNFnAASKS1MHxTvsiVBmwvClDKE5o6mhX2eg"
COMPANY_ID = "ivy-fashion-store"


async def check_qdrant_collections():
    """Kiểm tra collections trong Qdrant"""
    print("🔍 KIỂM TRA QDRANT COLLECTIONS")
    print("=" * 50)

    try:
        # Initialize Qdrant client
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )

        # Get all collections
        collections = client.get_collections()
        print(f"📁 Tổng số collections: {len(collections.collections)}")

        collection_name = f"retail_{COMPANY_ID.replace('-', '_')}"
        collection_exists = False

        for collection in collections.collections:
            print(f"   - {collection.name}")
            if collection.name == collection_name:
                collection_exists = True

        if not collection_exists:
            print(f"\n❌ Collection '{collection_name}' chưa tồn tại")
            return False

        # Get collection details
        print(f"\n✅ Collection '{collection_name}' tồn tại!")
        collection_info = client.get_collection(collection_name)

        print(f"📊 Chi tiết collection:")
        print(f"   - Vectors count: {collection_info.vectors_count}")
        print(f"   - Points count: {collection_info.points_count}")
        print(f"   - Status: {collection_info.status}")

        if collection_info.points_count == 0:
            print("\n⚠️  Collection tồn tại nhưng chưa có dữ liệu")
            return False

        # Get sample data
        print(f"\n📝 Lấy 5 mẫu dữ liệu đầu tiên:")
        scroll_result = client.scroll(
            collection_name=collection_name, limit=5, with_payload=True
        )

        for i, point in enumerate(scroll_result[0]):
            print(f"\n   📄 Point {i+1}:")
            print(f"   - ID: {point.id}")
            if point.payload:
                data_type = point.payload.get("data_type", "unknown")
                content = point.payload.get("content", "")[:100]
                company_id = point.payload.get("company_id", "unknown")
                print(f"   - Company: {company_id}")
                print(f"   - Type: {data_type}")
                print(f"   - Content: {content}...")

        return True

    except Exception as e:
        print(f"❌ Lỗi khi kiểm tra Qdrant: {e}")
        return False


async def test_search_functionality():
    """Test search với QdrantCompanyDataService"""
    print("\n🔍 TEST SEARCH FUNCTIONALITY")
    print("=" * 50)

    try:
        # Initialize service
        service = QdrantCompanyDataService(
            qdrant_url=QDRANT_URL, qdrant_api_key=QDRANT_API_KEY
        )

        # Test searches
        search_queries = [
            "áo polo",
            "quần jean",
            "giày thể thao",
            "túi xách",
            "đồng hồ",
        ]

        successful_searches = 0

        for query in search_queries:
            print(f"\n🔍 Tìm kiếm: '{query}'")

            try:
                results = await service.search_company_data(
                    company_id=COMPANY_ID, query=query, limit=3
                )

                if results:
                    print(f"   ✅ Tìm thấy {len(results)} kết quả")
                    successful_searches += 1

                    # Show top result
                    top_result = results[0]
                    print(f"   🏆 Kết quả tốt nhất:")
                    print(f"      - Score: {top_result.score:.3f}")
                    print(f"      - Type: {top_result.data_type}")
                    content = (
                        top_result.content[:100] if top_result.content else "No content"
                    )
                    print(f"      - Content: {content}...")
                else:
                    print(f"   ❌ Không tìm thấy kết quả")

            except Exception as e:
                print(f"   ❌ Lỗi search: {e}")

        print(f"\n📊 KẾT QUẢ SEARCH:")
        print(f"   - Successful: {successful_searches}/{len(search_queries)}")
        print(
            f"   - Success rate: {(successful_searches/len(search_queries)*100):.1f}%"
        )

        return successful_searches > 0

    except Exception as e:
        print(f"❌ Lỗi khi test search: {e}")
        return False


async def check_data_types():
    """Kiểm tra phân loại data types"""
    print("\n📊 KIỂM TRA DATA TYPES")
    print("=" * 50)

    try:
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )

        collection_name = f"retail_{COMPANY_ID.replace('-', '_')}"

        # Get all points to analyze data types
        scroll_result = client.scroll(
            collection_name=collection_name, limit=100, with_payload=True
        )

        data_types = {}
        total_points = 0

        for point in scroll_result[0]:
            total_points += 1
            if point.payload:
                data_type = point.payload.get("data_type", "unknown")
                data_types[data_type] = data_types.get(data_type, 0) + 1

        print(f"📊 Phân tích {total_points} points:")
        for data_type, count in data_types.items():
            percentage = (count / total_points * 100) if total_points > 0 else 0
            print(f"   - {data_type}: {count} ({percentage:.1f}%)")

        return len(data_types) > 0

    except Exception as e:
        print(f"❌ Lỗi khi phân tích data types: {e}")
        return False


async def main():
    """Main test function"""
    print("🚀 KIỂM TRA TRỰC TIẾP QDRANT CHO IVY FASHION STORE")
    print("=" * 70)
    print(f"Company ID: {COMPANY_ID}")
    print(f"Qdrant URL: {QDRANT_URL[:50]}...")

    # 1. Check collections and data
    collections_ok = await check_qdrant_collections()

    if collections_ok:
        # 2. Analyze data types
        types_ok = await check_data_types()

        # 3. Test search functionality
        search_ok = await test_search_functionality()

        print("\n" + "=" * 70)
        print("📋 KẾT QUẢ TỔNG HỢP")
        print("=" * 70)

        print(f"✅ Collection & Data: {'OK' if collections_ok else 'FAILED'}")
        print(f"✅ Data Types: {'OK' if types_ok else 'FAILED'}")
        print(f"✅ Search Function: {'OK' if search_ok else 'FAILED'}")

        if collections_ok and search_ok:
            print("\n🎉 TẤT CẢ TESTS THÀNH CÔNG!")
            print("✅ Dữ liệu Ivy Fashion Store đã được upload và search hoạt động tốt")
            print("✅ Có thể tiến hành test chat integration")
        else:
            print("\n⚠️  MỘT SỐ CHỨC NĂNG CÓ VẤN ĐỀ")
            if not search_ok:
                print("💡 Search function cần kiểm tra thêm")
    else:
        print("\n❌ COLLECTION CHƯA CÓ DỮ LIỆU")
        print("💡 Cần chạy lại quá trình extract và upload:")
        print("   1. Upload file CSV lên API")
        print("   2. Trigger AI extraction")
        print("   3. Chờ background upload hoàn thành")


if __name__ == "__main__":
    asyncio.run(main())
