"""
Setup Qdrant Collections for 3 Test Companies
Tạo Qdrant collections và ingest data cho 3 công ty test
"""

import asyncio
import os
from src.services.company_data_manager import CompanyDataManager
from src.utils.logger import setup_logger

logger = setup_logger()

async def setup_company_data():
    """Setup data cho 3 công ty trong Qdrant"""
    print("🔧 Setting up Qdrant collections for 3 companies...")
    print("=" * 60)
    
    data_manager = CompanyDataManager()
    
    # Company 1: Golden Dragon Restaurant
    print("\n🍽️ Setting up Golden Dragon Restaurant...")
    try:
        await data_manager.create_company(
            company_id="golden-dragon-restaurant",
            name="Nhà hàng Golden Dragon",
            industry="restaurant",
            description="Nhà hàng Á Đông cao cấp tại TP.HCM"
        )
        
        # Golden Dragon info
        golden_dragon_info = """
Nhà hàng Golden Dragon - Thông tin chi tiết

GIỚI THIỆU CHUNG
Nhà hàng Golden Dragon là nhà hàng Á Đông cao cấp được thành lập năm 2018 tại trung tâm TP.HCM. 
Chúng tôi chuyên về ẩm thực Trung Hoa truyền thống và Việt Nam fusion với không gian sang trọng.

THÔNG TIN LIÊN HỆ
- Địa chỉ: 456 Đồng Khởi, Quận 1, TP.HCM
- Điện thoại: (028) 3829 1234
- Hotline: 1900 888 999
- Email: info@goldendragon.vn

GIỜ HOẠT ĐỘNG
- Thứ 2 - Chủ nhật: 11:00 - 22:00
- Phục vụ liên tục không nghỉ trưa
- Nhận đặt bàn trước 24h
- Room VIP: Đặt trước 48h

KHÔNG GIAN NHÀ HÀNG
Tầng 1 - Main Dining: 80 chỗ ngồi, không gian mở
Tầng 2 - VIP Rooms: 6 phòng riêng (8-12 người/phòng), có karaoke
Tầng 3 - Sky Terrace: 40 chỗ ngồi, view toàn cảnh thành phố

MENU NỔI BẬT
- Vịt quay Bắc Kinh: 850,000đ
- Tôm hùm xào tỏi: 1,200,000đ  
- Cơm chiên Dương Châu: 180,000đ
- Súp vi cá: 280,000đ
- Set menu gia đình 4-6 người: 1,800,000đ
- Menu chay đầy đủ các món

DỊCH VỤ ĐẶT BÀN
- Đặt bàn online qua website
- Gọi hotline 1900 888 999
- Đặt trước tối thiểu 2 giờ
- Phòng VIP đặt trước 48h
- Miễn phí hủy bàn trước 4 giờ
"""
        
        result1 = await data_manager.ingest_document(
            company_id="golden-dragon-restaurant",
            content=golden_dragon_info,
            metadata={"source": "company_info", "type": "restaurant_info"}
        )
        print(f"   ✅ Golden Dragon info: {'Success' if result1 else 'Failed'}")
        
    except Exception as e:
        logger.error(f"❌ Error setting up Golden Dragon: {e}")
        print(f"❌ Error setting up Golden Dragon: {e}")
    
    # Company 2: Ivy Fashion Store
    print("\n👗 Setting up Ivy Fashion Store...")
    try:
        await data_manager.create_company(
            company_id="ivy-fashion-store",
            name="Cửa hàng Ivy Fashion",
            industry="retail",
            description="Thương hiệu thời trang nữ hàng đầu Việt Nam"
        )
        
        ivy_fashion_info = """
IVY Fashion - Thông tin cửa hàng

GIỚI THIỆU CÔNG TY
IVY Fashion là thương hiệu thời trang nữ hàng đầu Việt Nam, được thành lập năm 2005. 
Chuyên cung cấp các sản phẩm thời trang công sở và dạo phố cho phụ nữ hiện đại.

THÔNG TIN LIÊN HỆ
- Địa chỉ: 789 Nguyễn Thị Minh Khai, Q.3, TP.HCM
- Điện thoại: (028) 3932 5678
- Email: info@ivyfashion.vn
- Website: https://ivyfashion.vn

HỆ THỐNG CỬA HÀNG
- TP.HCM: 15 cửa hàng (Vincom Đồng Khởi, Crescent Mall, Landmark 81...)
- Hà Nội: 10 cửa hàng (Lotte Center, Vincom Bà Triệu...)
- Tỉnh thành khác: 20 cửa hàng

SẢN PHẨM CHÍNH
Thời trang công sở:
- Áo blazer cao cấp: 1,200,000 - 2,500,000đ
- Áo sơ mi/kiểu công sở: 450,000 - 850,000đ
- Chân váy/Quần tây công sở: 650,000 - 1,200,000đ
- Đầm công sở thanh lịch: 890,000 - 1,800,000đ

Thời trang dạo phố:
- Áo thun/tank top basic: 290,000 - 450,000đ
- Váy midi/maxi: 650,000 - 1,200,000đ
- Quần jeans/shorts: 590,000 - 950,000đ
- Áo khoác cardigan: 750,000 - 1,350,000đ

Thời trang dự tiệc:
- Đầm cocktail: 1,500,000 - 3,500,000đ
- Jumpsuit elegant: 1,200,000 - 2,200,000đ

SIZE & ĐỔI TRẢ
- Size: XS, S, M, L, XL
- Đổi trả trong 30 ngày
- Miễn phí đổi size tại cửa hàng
- Hoàn tiền 100% nếu lỗi sản xuất

DỊCH VỤ GIAO HÀNG
- Giao hàng toàn quốc
- Miễn phí ship đơn từ 500,000đ
- Giao hàng nhanh trong ngày tại TP.HCM và Hà Nội
- COD toàn quốc
"""
        
        result2 = await data_manager.ingest_document(
            company_id="ivy-fashion-store",
            content=ivy_fashion_info,
            metadata={"source": "company_info", "type": "fashion_info"}
        )
        print(f"   ✅ Ivy Fashion info: {'Success' if result2 else 'Failed'}")
        
    except Exception as e:
        logger.error(f"❌ Error setting up Ivy Fashion: {e}")
        print(f"❌ Error setting up Ivy Fashion: {e}")
    
    # Company 3: VRB Bank
    print("\n🏦 Setting up VRB Bank...")
    try:
        await data_manager.create_company(
            company_id="vrb-bank-financial",
            name="Ngân hàng VRB",
            industry="finance",
            description="Ngân hàng Thương mại Cổ phần Việt Nam Thịnh vượng"
        )
        
        vrb_bank_info = """
Ngân hàng VRB - Thông tin công ty

GIỚI THIỆU CHUNG
Ngân hàng Thương mại Cổ phần Việt Nam Thịnh vượng (VRB Bank) là một trong những ngân hàng hàng đầu Việt Nam.
Thành lập năm 2010, hiện có vốn điều lệ 5,000 tỷ VNĐ với mạng lưới 100 chi nhánh toàn quốc.

THÔNG TIN LIÊN HỆ
- Trụ sở chính: 123 Nguyễn Huệ, Q.1, TP.HCM
- Hotline: 1900 123 456
- Email: info@vrbbank.com.vn
- Website: https://vrbbank.com.vn

DỊCH VỤ CÁ NHÂN
1. Tài khoản tiết kiệm
- Lãi suất: 6.5%/năm cho kỳ hạn 12 tháng
- Số tiền gửi tối thiểu: 100,000 VNĐ
- Miễn phí thẻ ATM năm đầu

2. Vay mua nhà
- Lãi suất: Từ 8.5%/năm
- Thời hạn vay: Tối đa 25 năm
- Tỷ lệ cho vay: Lên đến 80% giá trị tài sản
- Hồ sơ: CMND, sổ hộ khẩu, giấy tờ thu nhập

3. Thẻ tín dụng VRB
- Loại thẻ: Classic, Gold, Platinum, Diamond
- Hạn mức: Từ 10 triệu - 1 tỷ VNĐ
- Ưu đãi: Cashback 1-3%, miễn phí năm đầu

4. Chuyển tiền quốc tế
- Phí chuyển: Từ 50,000 VNĐ/giao dịch
- Thời gian: 1-3 ngày làm việc
- Mạng lưới: Hơn 200 quốc gia

DỊCH VỤ DOANH NGHIỆP
1. Vay vốn kinh doanh
- Lãi suất: Từ 9.5%/năm
- Hạn mức: Từ 500 triệu - 100 tỷ VNĐ
- Thời hạn: Linh hoạt từ 6 tháng - 10 năm

2. Bảo lãnh ngân hàng
- Loại bảo lãnh: Thầu, tạm ứng, bảo hành, thanh toán
- Phí bảo lãnh: Từ 0.1%/tháng

3. Factoring
- Tỷ lệ tài trợ: Lên đến 90% giá trị hóa đơn
- Lãi suất: Từ 12%/năm

NGÂN HÀNG SỐ
- VRB Mobile Banking: Chuyển tiền, thanh toán hóa đơn
- VRB Internet Banking: Quản lý tài khoản, đầu tư
- Bảo mật sinh trắc học
- Hỗ trợ 24/7

KHÁCH HÀNG THÂN THIẾT
- VRB Elite Club: Số dư từ 500 triệu VNĐ
- VRB Premium: Số dư từ 100 triệu VNĐ
- Ưu đãi đặc biệt cho khách VIP
"""
        
        result3 = await data_manager.ingest_document(
            company_id="vrb-bank-financial",
            content=vrb_bank_info,
            metadata={"source": "company_info", "type": "bank_info"}
        )
        print(f"   ✅ VRB Bank info: {'Success' if result3 else 'Failed'}")
        
    except Exception as e:
        logger.error(f"❌ Error setting up VRB Bank: {e}")
        print(f"❌ Error setting up VRB Bank: {e}")
    
    print("\n🎉 Setup completed!")
    print("=" * 60)
    print("Companies ready for testing:")
    print("1. ✅ Golden Dragon Restaurant (golden-dragon-restaurant)")
    print("2. ✅ Ivy Fashion Store (ivy-fashion-store)")
    print("3. ✅ VRB Bank (vrb-bank-financial)")
    print("\nRun: python test_companies_simple.py")

if __name__ == "__main__":
    asyncio.run(setup_company_data())
