#!/bin/bash
# Kiểm tra Products/Services trong Production MongoDB

echo "🔍 KIỂM TRA PRODUCTS/SERVICES TRÊN PRODUCTION"
echo "=================================================="

# 1. Kiểm tra collection tổng quan
echo "📊 1. THỐNG KÊ TỔNG QUAN:"
docker exec mongodb mongosh "ai_service_db" --username "ai_service_user" --password "ai_service_2025_secure_password" --authenticationDatabase admin --eval "
db.internal_products_catalog.countDocuments()
"

# 2. Kiểm tra theo company_id
echo "📊 2. THỐNG KÊ THEO COMPANY:"
docker exec mongodb mongosh "ai_service_db" --username "ai_service_user" --password "ai_service_2025_secure_password" --authenticationDatabase admin --eval "
db.internal_products_catalog.aggregate([
    { \$group: { _id: { company_id: '\$company_id', item_type: '\$item_type' }, count: { \$sum: 1 } } },
    { \$sort: { '_id.company_id': 1, '_id.item_type': 1 } }
])
"

# 3. Xem sample data cho Mermaid Seaside Hotel
echo "📊 3. SAMPLE DATA CHO KHÁCH SẠN MERMAID SEASIDE:"
docker exec mongodb mongosh "ai_service_db" --username "ai_service_user" --password "ai_service_2025_secure_password" --authenticationDatabase admin --eval "
db.internal_products_catalog.find(
    { company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb' },
    { name: 1, item_type: 1, price: 1, quantity: 1, created_at: 1, _id: 0 }
).limit(10).pretty()
"

# 4. Kiểm tra indexes
echo "📊 4. INDEXES HIỆN TẠI:"
docker exec mongodb mongosh "ai_service_db" --username "ai_service_user" --password "ai_service_2025_secure_password" --authenticationDatabase admin --eval "
db.internal_products_catalog.getIndexes()
"

# 5. Kiểm tra dữ liệu mới nhất
echo "📊 5. 5 RECORDS MỚI NHẤT:"
docker exec mongodb mongosh "ai_service_db" --username "ai_service_user" --password "ai_service_2025_secure_password" --authenticationDatabase admin --eval "
db.internal_products_catalog.find({}, {name: 1, company_id: 1, item_type: 1, created_at: 1, _id: 0}).sort({created_at: -1}).limit(5).pretty()
"

# 6. Kiểm tra company info đã update
echo "📊 6. COMPANY INFO MỚI (MERMAID SEASIDE):"
docker exec mongodb mongosh "ai_service_db" --username "ai_service_user" --password "ai_service_2025_secure_password" --authenticationDatabase admin --eval "
db.companies.findOne(
    { company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb' },
    { company_name: 1, industry: 1, 'contact_info.phone': 1, 'metadata.description': 1, updated_at: 1, _id: 0 }
)
"

echo "=================================================="
echo "✅ HOÀN THÀNH KIỂM TRA!"
