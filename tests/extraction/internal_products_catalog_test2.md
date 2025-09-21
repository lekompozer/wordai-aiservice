ai_service_db> db.internal_products_catalog.find().limit(20).pretty()
[
  {
    _id: ObjectId('68a7678a9b263be9d5f0bade'),
    product_id: 'prod_7dbdfd83-c097-4b1c-aa84-1096dab2c30c',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: 'Superior Standard',
    price: 754691,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Superior Standard (28m²) với tùy chọn 1 giường đôi hoặc 2 giường đơn, ban công, quầy bar mini. Ưu đãi bao gồm bữa sáng, wifi và chỗ đậu xe miễn phí. Có các lựa chọn giá linh hoạt với chính sách hủy và thanh toán khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 1,
      name: 'Superior Standard',
      prices: {
        price_1: 754691,
        price_2: 771013,
        original_price: 2040052,
        currency: 'VND'
      },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Có chỗ đậu xe | WiFi miễn phí',
        condition_price_2: 'Bao gồm bữa sáng | Không được hủy | Thanh toán ngay',
        occupancy_price_1: 2,
        occupancy_price_2: 2
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Superior Standard (28m²) với tùy chọn 1 giường đôi hoặc 2 giường đơn, ban công, quầy bar mini. Ưu đãi bao gồm bữa sáng, wifi và chỗ đậu xe miễn phí. Có các lựa chọn giá linh hoạt với chính sách hủy và thanh toán khác nhau.',
      content_for_embedding: 'Phòng Superior Standard tại Mermaid Seaside Hotel Vũng Tàu có diện tích 28m², phù hợp cho 2 người. Khách có thể chọn 1 giường đôi hoặc 2 giường đơn. Phòng có ban công, rèm cản sáng, quầy bar mini, nằm ở tầng cao và là phòng không hút thuốc. Có hai lựa chọn giá: một bao gồm bữa sáng, hủy miễn phí, wifi và chỗ đậu xe miễn phí với giá 754.691 ₫; lựa chọn còn lại bao gồm bữa sáng, không hủy, thanh toán ngay với giá 771.013 ₫.',
      retrieval_context: 'Tên: Superior Standard. Loại: phòng ở. Mô tả: Phòng Superior Standard (28m²) với tùy chọn 1 giường đôi hoặc 2 giường đơn, ban công, quầy bar mini. Ưu đãi bao gồm bữa sáng, wifi và chỗ đậu xe miễn phí. Có các lựa chọn giá linh hoạt với chính sách hủy và thanh toán khác nhau. Giá gốc: 2.040.052 ₫. Lựa chọn 1: 754.691 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Có chỗ đậu xe | WiFi miễn phí. Lựa chọn 2: 771.013 VND - Bao gồm bữa sáng | Không được hủy | Thanh toán ngay. Số người: 2. Phòng có ban công, rèm cản sáng, quầy bar mini, tầng cao, phòng không hút thuốc, phòng tắm chung, tủ quần áo.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'standard',
        tax_info: null,
        room_specifications: {
          size_sqm: 28,
          max_occupancy: { adults: 2, children: null },
          bed_configuration: 'twin_or_double',
          view_type: null,
          floor_level: 'high_floor',
          balcony: true,
          amenities: {
            air_conditioning: null,
            minibar: true,
            wifi: true,
            tv: null,
            safe: null
          }
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày đặt (Offer 1) / Không được hủy (Offer 2)',
          payment_methods: [ 'Thanh toán ngay (Offer 2)', 'Thanh toán ngay (Offer 1)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '1.  **Superior Standard (8.2 - Excellent)**\n' +
          '    *   **Tùy chọn giường:** 1 giường đôi hoặc 2 giường đơn (tùy tình trạng sẵn có).\n' +
          '    *   **Tiện nghi và chi tiết:**\n' +
          '        *   Diện tích: 28 m² / 301 ft².\n' +
          '        *   Loại giường: 2 giường đơn hoặc 1 giường đôi.\n' +
          '        *   Ban công/Sân hiên.\n' +
          '        *   Rèm cản sáng.\n' +
          '        *   Quầy bar mini.\n' +
          '        *   Tầng cao.\n' +
          '        *   Phòng không hút thuốc.\n' +
          '        *   Phòng tắm chung.\n' +
          '        *   Tủ quần áo.\n' +
          '    *   **Giá phòng (2 người):**\n' +
          '        *   **Offer 1:** Giá gốc 2.040.052 ₫, giảm còn 754.691 ₫ (giảm 63%). Bao gồm bữa sáng, hủy miễn phí trước ngày đặt, có chỗ đậu xe và WiFi miễn phí.\n' +
          '        *   **Offer 2:** Giá gốc 2.040.105 ₫, giảm còn 771.013 ₫ (giảm 62%). Bao gồm bữa sáng, không được hủy, thanh toán ngay.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_757b8522-f340-41cf-a421-618423d9b507'
    },
    created_at: '2025-08-21T18:38:02.521219',
    updated_at: '2025-08-21T18:38:02.521234',
    status: 'active'
  },
  {
    _id: ObjectId('68a7678b9b263be9d5f0badf'),
    product_id: 'prod_52fe5032-f118-49f1-9a2b-37db6a70e836',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: 'Superior Seaview',
    price: 804010,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Superior Seaview (30m²) hướng biển, có ban công, chăn điện, quầy bar mini. Ưu đãi bao gồm bữa sáng với các lựa chọn thanh toán và hủy phòng khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 2,
      name: 'Superior Seaview',
      prices: {
        price_1: 804010,
        price_2: 809532,
        original_price: 1633028,
        currency: 'VND'
      },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Thanh toán ngay | Số lượng có hạn',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Thanh toán sau',
        occupancy_price_1: 2,
        occupancy_price_2: 2
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Superior Seaview (30m²) hướng biển, có ban công, chăn điện, quầy bar mini. Ưu đãi bao gồm bữa sáng với các lựa chọn thanh toán và hủy phòng khác nhau.',
      content_for_embedding: 'Phòng Superior Seaview tại Mermaid Seaside Hotel Vũng Tàu có diện tích 30m² với tầm nhìn hướng biển, phù hợp cho 2 người. Phòng trang bị ban công, chăn điện và quầy bar mini. Có hai lựa chọn: bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay với giá 804.010 ₫ (số lượng có hạn); hoặc bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau với giá 809.532 ₫.',
      retrieval_context: 'Tên: Superior Seaview. Loại: phòng ở. Mô tả: Phòng Superior Seaview (30m²) hướng biển, có ban công, chăn điện, quầy bar mini. Ưu đãi bao gồm bữa sáng với các lựa chọn thanh toán và hủy phòng khác nhau. Giá gốc: 1.633.028 ₫. Lựa chọn 1: 804.010 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Thanh toán ngay | Số lượng có hạn. Lựa chọn 2: 809.532 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Thanh toán sau. Số người: 2. Phòng có ban công/sân hiên, cửa sổ, chăn điện, quầy bar mini, tầng cao, phòng không hút thuốc, phòng tắm chung.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'seaview',
        tax_info: null,
        room_specifications: {
          size_sqm: 30,
          max_occupancy: { adults: 2, children: null },
          bed_configuration: 'king_or_twin',
          view_type: 'sea_view',
          floor_level: 'high_floor',
          balcony: true,
          amenities: {
            air_conditioning: null,
            minibar: true,
            wifi: true,
            tv: null,
            safe: null
          }
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày đặt',
          payment_methods: [ 'Thanh toán ngay (Offer 1)', 'Thanh toán sau (Offer 2)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '2.  **Superior Seaview (8.3 - Excellent | Recommended)**\n' +
          '    *   **Tùy chọn giường:** 1 giường cỡ King hoặc 2 giường đơn.\n' +
          '    *   **Tiện nghi và chi tiết:**\n' +
          '        *   Diện tích: 30 m² / 323 ft².\n' +
          '        *   Hướng nhìn: Hướng nhìn ra biển (nhìn được một phần).\n' +
          '        *   Loại giường: 2 giường đơn hoặc 1 giường cỡ King.\n' +
          '        *   Ban công/Sân hiên.\n' +
          '        *   Cửa sổ.\n' +
          '        *   Chăn điện.\n' +
          '        *   Quầy bar mini (Mini bar).\n' +
          '        *   Tầng cao.\n' +
          '        *   Phòng không hút thuốc.\n' +
          '        *   Phòng tắm chung.\n' +
          '    *   **Giá phòng (2 người):**\n' +
          '        *   **Offer 1:** Giá gốc 1.633.028 ₫, giảm còn 804.010 ₫ (giảm 51%). Bao gồm bữa sáng, hủy miễn phí trước ngày đặt, thanh toán ngay. Số lượng có hạn.\n' +
          '        *   **Offer 2:** Giá gốc 1.633.045 ₫, giảm còn 809.532 ₫ (giảm 50%). Bao gồm bữa sáng, hủy miễn phí trước ngày đặt, thanh toán sau.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_9666b9d6-894c-48fa-8592-db519a4b3f33'
    },
    created_at: '2025-08-21T18:38:03.819536',
    updated_at: '2025-08-21T18:38:03.819551',
    status: 'active'
  },
  {
    _id: ObjectId('68a7678c9b263be9d5f0bae0'),
    product_id: 'prod_ed7437c6-beb9-4396-89e3-23d3d53f6181',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: '1 Bedroom Apartment',
    price: 1025324,
    quantity: 1,
    currency: 'VND',
    description: 'Căn hộ 1 phòng ngủ (diện tích không rõ) cho 2 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 3,
      name: '1 Bedroom Apartment',
      prices: {
        price_1: 1025324,
        price_2: 1061955,
        original_price: 2081695,
        currency: 'VND'
      },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Thanh toán ngay',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Thanh toán sau',
        occupancy_price_1: 2,
        occupancy_price_2: 2
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Căn hộ 1 phòng ngủ (diện tích không rõ) cho 2 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
      content_for_embedding: 'Căn hộ 1 phòng ngủ tại Mermaid Seaside Hotel Vũng Tàu dành cho 2 người, cung cấp tùy chọn giá bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay với giá 1.025.324 ₫, hoặc bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau với giá 1.061.955 ₫.',
      retrieval_context: 'Tên: 1 Bedroom Apartment. Loại: phòng ở. Mô tả: Căn hộ 1 phòng ngủ cho 2 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau. Giá gốc: 2.081.695 ₫. Lựa chọn 1: 1.025.324 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Thanh toán ngay. Lựa chọn 2: 1.061.955 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Thanh toán sau. Số người: 2.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'apartment',
        tax_info: null,
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 2, children: null },
          bed_configuration: null,
          view_type: null,
          floor_level: null,
          balcony: null,
          amenities: null
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày đặt',
          payment_methods: [ 'Thanh toán ngay (Offer 1)', 'Thanh toán sau (Offer 2)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '3.  **1 Bedroom Apartment (8.4 - Excellent)**\n' +
          '    *   **Giá phòng (2 người):**\n' +
          '        *   **Offer 1:** Giá gốc 2.081.695 ₫, giảm còn 1.025.324 ₫ (giảm 51%). Bao gồm bữa sáng, hủy miễn phí trước ngày đặt, thanh toán ngay.\n' +
          '        *   **Offer 2:** Giá gốc 2.081.695 ₫, giảm còn 1.061.955 ₫ (giảm 49%). Bao gồm bữa sáng, hủy miễn phí trước ngày đặt, thanh toán sau.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_d9ad79e2-a247-467c-b5bd-466413e1881d'
    },
    created_at: '2025-08-21T18:38:04.378434',
    updated_at: '2025-08-21T18:38:04.378450',
    status: 'active'
  },
  {
    _id: ObjectId('68a7678c9b263be9d5f0bae1'),
    product_id: 'prod_edb5e851-aa00-40c6-80af-bfb0e3f9e064',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: 'Superior Triple',
    price: 1174033,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Superior Triple dành cho 3 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 4,
      name: 'Superior Triple',
      prices: {
        price_1: 1174033,
        price_2: 1246276,
        original_price: 1743977,
        currency: 'VND'
      },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau',
        occupancy_price_1: 3,
        occupancy_price_2: 3
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Superior Triple dành cho 3 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
      content_for_embedding: 'Phòng Superior Triple tại Mermaid Seaside Hotel Vũng Tàu có sức chứa 3 người, bao gồm bữa sáng. Khách có thể chọn gói bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay với giá 1.174.033 ₫, hoặc bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau với giá 1.246.276 ₫.',
      retrieval_context: 'Tên: Superior Triple. Loại: phòng ở. Mô tả: Phòng Superior Triple dành cho 3 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau. Giá gốc: 1.743.977 ₫. Lựa chọn 1: 1.174.033 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay. Lựa chọn 2: 1.246.276 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau. Số người: 3.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'triple',
        tax_info: null,
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 3, children: null },
          bed_configuration: null,
          view_type: null,
          floor_level: null,
          balcony: null,
          amenities: null
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'Thanh toán ngay (Offer 1)', 'Thanh toán sau (Offer 2)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '4.  **Superior Triple**\n' +
          '    *   **Giá phòng (3 người):**\n' +
          '        *   **Offer 1:** Giá gốc 1.743.977 ₫, giảm còn 1.174.033 ₫ (giảm 33%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán ngay.\n' +
          '        *   **Offer 2:** Giá gốc 1.743.977 ₫, giảm còn 1.246.276 ₫ (giảm 29%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán sau.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_5ed878c1-a86a-4033-9b8a-e5a3989b5993'
    },
    created_at: '2025-08-21T18:38:04.868547',
    updated_at: '2025-08-21T18:38:04.868559',
    status: 'active'
  },
  {
    _id: ObjectId('68a7678d9b263be9d5f0bae2'),
    product_id: 'prod_c265c108-e86f-416c-9b3b-f8b8d8d2bdff',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: 'Superior Family Room',
    price: 1531287,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Superior Family Room dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 5,
      name: 'Superior Family Room',
      prices: {
        price_1: 1531287,
        price_2: 1623977,
        original_price: 2285483,
        currency: 'VND'
      },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau',
        occupancy_price_1: 4,
        occupancy_price_2: 4
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Superior Family Room dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
      content_for_embedding: 'Phòng Superior Family Room tại Mermaid Seaside Hotel Vũng Tàu có sức chứa 4 người, bao gồm bữa sáng. Khách có thể chọn gói bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay với giá 1.531.287 ₫, hoặc bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau với giá 1.623.977 ₫.',
      retrieval_context: 'Tên: Superior Family Room. Loại: phòng ở. Mô tả: Phòng Superior Family Room dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau. Giá gốc: 2.285.483 ₫. Lựa chọn 1: 1.531.287 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay. Lựa chọn 2: 1.623.977 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau. Số người: 4.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'family',
        tax_info: null,
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 4, children: null },
          bed_configuration: null,
          view_type: null,
          floor_level: null,
          balcony: null,
          amenities: null
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'Thanh toán ngay (Offer 1)', 'Thanh toán sau (Offer 2)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '5.  **Superior Family Room**\n' +
          '    *   **Giá phòng (4 người):**\n' +
          '        *   **Offer 1:** Giá gốc 2.285.483 ₫, giảm còn 1.531.287 ₫ (giảm 33%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán ngay.\n' +
          '        *   **Offer 2:** Giá gốc 2.285.483 ₫, giảm còn 1.623.977 ₫ (giảm 29%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán sau.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_b35a94c4-42f1-4b14-96ed-9631bf91d699'
    },
    created_at: '2025-08-21T18:38:05.365905',
    updated_at: '2025-08-21T18:38:05.365920',
    status: 'active'
  },
  {
    _id: ObjectId('68a7678d9b263be9d5f0bae3'),
    product_id: 'prod_2897fdea-cde3-42c6-b8b6-c76166300892',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: 'Deluxe Seaview',
    price: 911211,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Deluxe Seaview (diện tích không rõ) hướng biển cho 2 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 6,
      name: 'Deluxe Seaview',
      prices: {
        price_1: 911211,
        price_2: 950345,
        original_price: 1748625,
        currency: 'VND'
      },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau',
        occupancy_price_1: 2,
        occupancy_price_2: 2
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Deluxe Seaview (diện tích không rõ) hướng biển cho 2 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
      content_for_embedding: 'Phòng Deluxe Seaview tại Mermaid Seaside Hotel Vũng Tàu, phù hợp cho 2 người, bao gồm bữa sáng. Có hai lựa chọn: bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay với giá 911.211 ₫; hoặc bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau với giá 950.345 ₫.',
      retrieval_context: 'Tên: Deluxe Seaview. Loại: phòng ở. Mô tả: Phòng Deluxe Seaview hướng biển cho 2 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau. Giá gốc: 1.748.625 ₫. Lựa chọn 1: 911.211 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay. Lựa chọn 2: 950.345 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau. Số người: 2.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'deluxe_seaview',
        tax_info: null,
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 2, children: null },
          bed_configuration: null,
          view_type: 'sea_view',
          floor_level: null,
          balcony: null,
          amenities: null
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'Thanh toán ngay (Offer 1)', 'Thanh toán sau (Offer 2)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '6.  **Deluxe Seaview (8.4 - Excellent)**\n' +
          '    *   **Giá phòng (2 người):**\n' +
          '        *   **Offer 1:** Giá gốc 1.748.625 ₫, giảm còn 911.211 ₫ (giảm 48%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán ngay.\n' +
          '        *   **Offer 2:** Giá gốc 1.748.625 ₫, giảm còn 950.345 ₫ (giảm 46%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán sau.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_efc497d5-20fc-45e2-b679-25be46b87c75'
    },
    created_at: '2025-08-21T18:38:05.878609',
    updated_at: '2025-08-21T18:38:05.878621',
    status: 'active'
  },
  {
    _id: ObjectId('68a7678e9b263be9d5f0bae4'),
    product_id: 'prod_a3fcbe9c-a60c-4c38-9470-a850bf0d8f91',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: 'Deluxe Family Room',
    price: 1582302,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Deluxe Family Room dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 7,
      name: 'Deluxe Family Room',
      prices: {
        price_1: 1582302,
        price_2: 1678961,
        original_price: 2305818,
        currency: 'VND'
      },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau',
        occupancy_price_1: 4,
        occupancy_price_2: 4
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Deluxe Family Room dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
      content_for_embedding: 'Phòng Deluxe Family Room tại Mermaid Seaside Hotel Vũng Tàu có sức chứa 4 người, bao gồm bữa sáng. Khách có thể chọn gói bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay với giá 1.582.302 ₫, hoặc bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau với giá 1.678.961 ₫.',
      retrieval_context: 'Tên: Deluxe Family Room. Loại: phòng ở. Mô tả: Phòng Deluxe Family Room dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau. Giá gốc: 2.305.818 ₫. Lựa chọn 1: 1.582.302 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay. Lựa chọn 2: 1.678.961 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau. Số người: 4.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'deluxe_family',
        tax_info: null,
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 4, children: null },
          bed_configuration: null,
          view_type: null,
          floor_level: null,
          balcony: null,
          amenities: null
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'Thanh toán ngay (Offer 1)', 'Thanh toán sau (Offer 2)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '7.  **Deluxe Family Room**\n' +
          '    *   **Giá phòng (4 người):**\n' +
          '        *   **Offer 1:** Giá gốc 2.305.818 ₫, giảm còn 1.582.302 ₫ (giảm 31%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán ngay.\n' +
          '        *   **Offer 2:** Giá gốc 2.305.818 ₫, giảm còn 1.678.961 ₫ (giảm 27%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán sau.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_77c2389f-c258-404e-83c0-087b4e252ad7'
    },
    created_at: '2025-08-21T18:38:06.370303',
    updated_at: '2025-08-21T18:38:06.370316',
    status: 'active'
  },
  {
    _id: ObjectId('68a7678e9b263be9d5f0bae5'),
    product_id: 'prod_599ad027-4b32-4240-9715-ddd28a250d27',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: 'Grand Suite Sea View',
    price: 1630903,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Grand Suite Sea View (diện tích không rõ) hướng biển dành cho 2 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 8,
      name: 'Grand Suite Sea View',
      prices: {
        price_1: 1630903,
        price_2: 2308333,
        original_price: 2011140,
        currency: 'VND'
      },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau',
        occupancy_price_1: 2,
        occupancy_price_2: 2
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Grand Suite Sea View (diện tích không rõ) hướng biển dành cho 2 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
      content_for_embedding: 'Phòng Grand Suite Sea View tại Mermaid Seaside Hotel Vũng Tàu, phù hợp cho 2 người, có tầm nhìn hướng biển và bao gồm bữa sáng. Có hai lựa chọn: bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay với giá 1.630.903 ₫ (giá gốc 2.011.140 ₫); hoặc bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau với giá 2.308.333 ₫.',
      retrieval_context: 'Tên: Grand Suite Sea View. Loại: phòng ở. Mô tả: Phòng Grand Suite Sea View hướng biển dành cho 2 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau. Giá gốc: 2.011.140 ₫. Lựa chọn 1: 1.630.903 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay. Lựa chọn 2: 2.308.333 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau. Số người: 2.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'suite_seaview',
        tax_info: null,
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 2, children: null },
          bed_configuration: null,
          view_type: 'sea_view',
          floor_level: null,
          balcony: null,
          amenities: null
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'Thanh toán ngay (Offer 1)', 'Thanh toán sau (Offer 2)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '8.  **Grand Suite Sea View (8.5 - Excellent)**\n' +
          '    *   **Giá phòng (2 người):**\n' +
          '        *   **Offer 1:** Giá gốc 2.011.140 ₫, giảm còn 1.630.903 ₫ (giảm 19%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán ngay.\n' +
          '        *   **Offer 2:** Giá 2.308.333 ₫. Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán sau.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_56d814c1-dc89-4a64-8bc4-77213210a47b'
    },
    created_at: '2025-08-21T18:38:06.866505',
    updated_at: '2025-08-21T18:38:06.866516',
    status: 'active'
  },
  {
    _id: ObjectId('68a7678f9b263be9d5f0bae6'),
    product_id: 'prod_3492c587-2968-4239-9e6a-fbe35392dfd5',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: '2 Bed Apartment',
    price: 1735565,
    quantity: 1,
    currency: 'VND',
    description: 'Căn hộ 2 phòng ngủ (diện tích không rõ) dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 9,
      name: '2 Bed Apartment',
      prices: {
        price_1: 1735565,
        price_2: 1862148,
        original_price: 2806903,
        currency: 'VND'
      },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau',
        occupancy_price_1: 4,
        occupancy_price_2: 4
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Căn hộ 2 phòng ngủ (diện tích không rõ) dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
      content_for_embedding: 'Căn hộ 2 phòng ngủ tại Mermaid Seaside Hotel Vũng Tàu có sức chứa 4 người, bao gồm bữa sáng. Khách có thể chọn gói bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay với giá 1.735.565 ₫ (giá gốc 2.806.903 ₫), hoặc bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau với giá 1.862.148 ₫.',
      retrieval_context: 'Tên: 2 Bed Apartment. Loại: phòng ở. Mô tả: Căn hộ 2 phòng ngủ dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau. Giá gốc: 2.806.903 ₫. Lựa chọn 1: 1.735.565 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay. Lựa chọn 2: 1.862.148 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau. Số người: 4.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'apartment',
        tax_info: null,
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 4, children: null },
          bed_configuration: null,
          view_type: null,
          floor_level: null,
          balcony: null,
          amenities: null
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'Thanh toán ngay (Offer 1)', 'Thanh toán sau (Offer 2)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '9.  **2 Bed Apartment (8.5 - Excellent)**\n' +
          '    *   **Giá phòng (4 người):**\n' +
          '        *   **Offer 1:** Giá gốc 2.806.903 ₫, giảm còn 1.735.565 ₫ (giảm 38%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán ngay.\n' +
          '        *   **Offer 2:** Giá gốc 2.806.903 ₫, giảm còn 1.862.148 ₫ (giảm 34%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán sau.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_aa4dfa39-e5d1-409e-95f4-8c9f09178200'
    },
    created_at: '2025-08-21T18:38:07.392667',
    updated_at: '2025-08-21T18:38:07.392682',
    status: 'active'
  },
  {
    _id: ObjectId('68a7678f9b263be9d5f0bae7'),
    product_id: 'prod_686ac610-26fc-4bbc-a291-9c8a83151e44',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: 'Standard Triple Room',
    price: 1891667,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Standard Triple dành cho 3 người. Có hai lựa chọn: giá bao gồm hủy miễn phí, thanh toán ngay nhưng không bao gồm bữa sáng (có thể mua thêm); giá còn lại bao gồm bữa sáng, hủy miễn phí và thanh toán sau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 10,
      name: 'Standard Triple Room',
      prices: { price_1: 1891667, price_2: 1958333, currency: 'VND' },
      conditions: {
        condition_price_1: 'Không bao gồm bữa sáng (có thể thêm 120.000 ₫/người) | Hủy miễn phí trước ngày | Thanh toán ngay',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau',
        occupancy_price_1: 3,
        occupancy_price_2: 3
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Standard Triple dành cho 3 người. Có hai lựa chọn: giá bao gồm hủy miễn phí, thanh toán ngay nhưng không bao gồm bữa sáng (có thể mua thêm); giá còn lại bao gồm bữa sáng, hủy miễn phí và thanh toán sau.',
      content_for_embedding: 'Phòng Standard Triple tại Mermaid Seaside Hotel Vũng Tàu dành cho 3 người. Lựa chọn 1: giá 1.891.667 ₫, bao gồm hủy miễn phí và thanh toán ngay, không có bữa sáng (có thể thêm 120.000 ₫/người). Lựa chọn 2: giá 1.958.333 ₫, bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau.',
      retrieval_context: 'Tên: Standard Triple Room. Loại: phòng ở. Mô tả: Phòng Standard Triple dành cho 3 người. Có hai lựa chọn: giá bao gồm hủy miễn phí, thanh toán ngay nhưng không bao gồm bữa sáng (có thể mua thêm); giá còn lại bao gồm bữa sáng, hủy miễn phí và thanh toán sau. Lựa chọn 1: 1.891.667 VND - Không bao gồm bữa sáng (có thể thêm 120.000 ₫/người) | Hủy miễn phí trước ngày | Thanh toán ngay. Lựa chọn 2: 1.958.333 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau. Số người: 3.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'triple',
        tax_info: null,
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 3, children: null },
          bed_configuration: null,
          view_type: null,
          floor_level: null,
          balcony: null,
          amenities: null
        },
        dining_info: { meal_type: 'breakfast_optional' },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'Thanh toán ngay (Offer 1)', 'Thanh toán sau (Offer 2)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '10. **Standard Triple Room**\n' +
          '    *   **Giá phòng (3 người):**\n' +
          '        *   **Offer 1:** Giá 1.891.667 ₫. Không bao gồm bữa sáng (có thể thêm 120.000 ₫/người), hủy miễn phí trước ngày, thanh toán ngay.\n' +
          '        *   **Offer 2:** Giá 1.958.333 ₫. Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán sau.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_9545d042-ba9e-419c-a94e-bf9bd28dbc2e'
    },
    created_at: '2025-08-21T18:38:07.913809',
    updated_at: '2025-08-21T18:38:07.913826',
    status: 'active'
  },
  {
    _id: ObjectId('68a767909b263be9d5f0bae8'),
    product_id: 'prod_5f4e81b1-c746-4dec-a150-17500e4228da',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: 'Grand Family Room',
    price: 2143918,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Grand Family Room (diện tích không rõ) với 3 lựa chọn giá cho các mức độ người ở khác nhau (2, 4, 6 người). Tất cả đều bao gồm bữa sáng và có chính sách hủy/thanh toán linh hoạt.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 11,
      name: 'Grand Family Room',
      prices: {
        price_1: 2143918,
        price_2: 2300949,
        price_3: 2347549,
        original_price: 3106493,
        currency: 'VND'
      },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau',
        condition_price_3: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau',
        occupancy_price_1: 4,
        occupancy_price_2: 6,
        occupancy_price_3: 2
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Grand Family Room (diện tích không rõ) với 3 lựa chọn giá cho các mức độ người ở khác nhau (2, 4, 6 người). Tất cả đều bao gồm bữa sáng và có chính sách hủy/thanh toán linh hoạt.',
      content_for_embedding: 'Phòng Grand Family Room tại Mermaid Seaside Hotel Vũng Tàu có sức chứa linh hoạt cho 2, 4 hoặc 6 người, tất cả các tùy chọn đều bao gồm bữa sáng. Giá cho 4 người là 2.143.918 ₫ (bao gồm bữa sáng, hủy miễn phí, thanh toán ngay). Giá cho 6 người là 2.300.949 ₫ (bao gồm bữa sáng, hủy miễn phí, thanh toán sau). Giá cho 2 người là 2.347.549 ₫ (bao gồm bữa sáng, hủy miễn phí, thanh toán sau).',
      retrieval_context: 'Tên: Grand Family Room. Loại: phòng ở. Mô tả: Phòng Grand Family Room với 3 lựa chọn giá cho các mức độ người ở khác nhau (2, 4, 6 người). Tất cả đều bao gồm bữa sáng và có chính sách hủy/thanh toán linh hoạt. Giá gốc: 3.106.493 ₫. Lựa chọn 1: 2.143.918 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán ngay. Lựa chọn 2: 2.300.949 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau. Lựa chọn 3: 2.347.549 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán sau. Số người: 4 người (Lựa chọn 1), 6 người (Lựa chọn 2), 2 người (Lựa chọn 3).',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'family',
        tax_info: null,
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 6, children: null },
          bed_configuration: null,
          view_type: null,
          floor_level: null,
          balcony: null,
          amenities: null
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [
            'Thanh toán ngay (Offer 1)',
            'Thanh toán sau (Offer 2, Offer 3)'
          ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '11. **Grand Family Room (8.6 - Excellent)**\n' +
          '    *   **Giá phòng (4 người):**\n' +
          '        *   **Offer 1:** Giá gốc 3.106.493 ₫, giảm còn 2.143.918 ₫ (giảm 31%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán ngay.\n' +
          '    *   **Giá phòng (6 người):**\n' +
          '        *   **Offer 2:** Giá gốc 3.106.493 ₫, giảm còn 2.300.949 ₫ (giảm 26%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán sau.\n' +
          '    *   **Giá phòng (2 người):**\n' +
          '        *   **Offer 3:** Giá gốc 3.106.493 ₫, giảm còn 2.347.549 ₫ (giảm 24%). Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán sau.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_5abf10e4-b470-4389-a1d9-5014479569e5'
    },
    created_at: '2025-08-21T18:38:08.447129',
    updated_at: '2025-08-21T18:38:08.447156',
    status: 'active'
  },
  {
    _id: ObjectId('68a767919b263be9d5f0bae9'),
    product_id: 'prod_e1d5cd25-5823-4a74-a6ac-f8c12c23fa3c',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: 'fd41fccb-a0e2-44e7-a217-22ed91cafb70',
    file_name: 'Bang_gia_phong_ks_Mermaid.pdf',
    name: 'Quadruple Room with Balcony',
    price: 2695000,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Quadruple Room có ban công dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 12,
      name: 'Quadruple Room with Balcony',
      prices: { price_1: 2695000, price_2: 2750000, currency: 'VND' },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Không được hủy | Thanh toán tại khách sạn',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán tại khách sạn',
        occupancy_price_1: 4,
        occupancy_price_2: 4
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Quadruple Room có ban công dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau.',
      content_for_embedding: 'Phòng Quadruple Room có ban công tại Mermaid Seaside Hotel Vũng Tàu, sức chứa 4 người, bao gồm bữa sáng. Lựa chọn 1 có giá 2.695.000 ₫, bao gồm bữa sáng, không được hủy và thanh toán tại khách sạn. Lựa chọn 2 có giá 2.750.000 ₫, bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán tại khách sạn.',
      retrieval_context: 'Tên: Quadruple Room with Balcony. Loại: phòng ở. Mô tả: Phòng Quadruple Room có ban công dành cho 4 người, bao gồm bữa sáng. Có hai lựa chọn giá với chính sách hủy và thanh toán khác nhau. Lựa chọn 1: 2.695.000 VND - Bao gồm bữa sáng | Không được hủy | Thanh toán tại khách sạn. Lựa chọn 2: 2.750.000 VND - Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán tại khách sạn. Số người: 4.',
      other_info: {
        product_code: null,
        sku: null,
        sub_category: 'quadruple',
        tax_info: null,
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 4, children: null },
          bed_configuration: null,
          view_type: null,
          floor_level: null,
          balcony: true,
          amenities: null
        },
        dining_info: {},
        booking_info: {
          cancellation_policy: 'Không được hủy (Offer 1) / Hủy miễn phí trước ngày (Offer 2)',
          payment_methods: [ 'Thanh toán tại khách sạn (Offer 1, Offer 2)' ],
          advance_booking: null
        }
      },
      raw_data: {
        extracted_text: '12. **Quadruple Room with Balcony**\n' +
          '    *   **Giá phòng (4 người):**\n' +
          '        *   **Offer 1:** Giá 2.695.000 ₫. Bao gồm bữa sáng, không được hủy (giá thấp), thanh toán tại khách sạn.\n' +
          '        *   **Offer 2:** Giá 2.750.000 ₫. Bao gồm bữa sáng, hủy miễn phí trước ngày, thanh toán tại khách sạn.',
        confidence_score: 0.95,
        extraction_notes: null,
        original_format: 'list',
        file_section: 'Chi Tiết Các Hạng Phòng'
      },
      product_id: 'prod_16b23fd7-26ab-4d63-a46b-fca30a95427a'
    },
    created_at: '2025-08-21T18:38:09.027269',
    updated_at: '2025-08-21T18:38:09.027285',
    status: 'active'
  }
]
