ai_service_db> db.internal_products_catalog.find().limit(20).pretty()
[
  {
    _id: ObjectId('68a761a14c321b4532f9a456'),
    product_id: 'prod_c8d0bb91-3bc4-46fa-9ff6-d06cfd8692d8',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: 'Superior Standard',
    price: 754691,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Superior Standard có diện tích 28 m², cung cấp tùy chọn 1 giường đôi hoặc 2 giường đơn, ban công/sân hiên, quầy bar mini và là phòng không hút thuốc. Giá ưu đãi đã bao gồm bữa sáng.',
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
        condition_price_1: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày đặt | Chỗ đậu xe | WiFi miễn phí',
        condition_price_2: 'Bao gồm bữa sáng | Không được hủy | Thanh toán ngay',
        occupancy_price_1: 2,
        occupancy_price_2: 2
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Superior Standard có diện tích 28 m², cung cấp tùy chọn 1 giường đôi hoặc 2 giường đơn, ban công/sân hiên, quầy bar mini và là phòng không hút thuốc. Giá ưu đãi đã bao gồm bữa sáng.',
      content_for_embedding: 'Phòng Superior Standard. Diện tích 28m², có ban công/sân hiên, quầy bar mini. Lựa chọn 1 giường đôi hoặc 2 giường đơn. Giá ưu đãi bao gồm bữa sáng và WiFi miễn phí. Có các tùy chọn hủy miễn phí hoặc không hủy.',
      retrieval_context: 'Superior Standard là phòng nghỉ có diện tích 28m² với các tiện nghi như ban công/sân hiên, rèm cản sáng, quầy bar mini, nằm ở tầng cao và là phòng không hút thuốc. Khách sạn cung cấp 2 lựa chọn đặt phòng cho phòng Superior Standard: Lựa chọn 1 có giá 754.691 VND cho 2 người, bao gồm bữa sáng, hủy miễn phí trước ngày đặt, chỗ đậu xe và WiFi miễn phí, với giá gốc là 2.040.052 VND. Lựa chọn 2 có giá 771.013 VND cho 2 người, bao gồm bữa sáng, không được hủy và yêu cầu thanh toán ngay, với giá gốc là 2.040.105 VND.',
      other_info: {
        room_specifications: {
          size_sqm: 28,
          max_occupancy: { adults: 2 },
          bed_configuration: 'twin_or_double',
          balcony: true,
          amenities: { minibar: true, wifi: true },
          view_type: null,
          floor_level: 'high_floor',
          room_type: 'standard'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày đặt | Không được hủy',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_3be65340-e0f2-4cd0-a132-1f6580684cc0'
    },
    created_at: '2025-08-21T18:12:49.988630',
    updated_at: '2025-08-21T18:12:49.988642',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a34c321b4532f9a457'),
    product_id: 'prod_9f36b3fd-5d6e-4053-ba0a-696f50769deb',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: 'Superior Seaview',
    price: 804010,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Superior Seaview rộng 30 m² với tầm nhìn một phần ra biển, cung cấp tùy chọn 1 giường King hoặc 2 giường đơn, ban công/sân hiên và chăn điện. Giá đã bao gồm bữa sáng và có tùy chọn hủy miễn phí.',
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
      description: 'Phòng Superior Seaview rộng 30 m² với tầm nhìn một phần ra biển, cung cấp tùy chọn 1 giường King hoặc 2 giường đơn, ban công/sân hiên và chăn điện. Giá đã bao gồm bữa sáng và có tùy chọn hủy miễn phí.',
      content_for_embedding: 'Phòng Superior Seaview rộng 30m², có ban công/sân hiên, nhìn ra biển một phần. Lựa chọn 1 giường King hoặc 2 giường đơn. Giá ưu đãi bao gồm bữa sáng, WiFi miễn phí, có tùy chọn hủy miễn phí và các phương thức thanh toán khác nhau.',
      retrieval_context: 'Phòng Superior Seaview rộng 30 m² mang đến tầm nhìn một phần ra biển, với tùy chọn giường King hoặc 2 giường đơn, có ban công/sân hiên và chăn điện. Giá phòng (2 người) có 2 lựa chọn: Lựa chọn 1 với giá 804.010 VND (giảm 51% từ 1.633.028 VND) bao gồm bữa sáng, hủy miễn phí trước ngày đặt và thanh toán ngay (số lượng có hạn). Lựa chọn 2 với giá 809.532 VND (giảm 50% từ 1.633.045 VND) bao gồm bữa sáng, hủy miễn phí trước ngày đặt và thanh toán sau.',
      other_info: {
        room_specifications: {
          size_sqm: 30,
          max_occupancy: { adults: 2 },
          bed_configuration: 'king_or_twin',
          view_type: 'partial_sea_view',
          balcony: true,
          amenities: { minibar: true, wifi: true },
          floor_level: 'high_floor',
          room_type: 'superior'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày đặt',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_47623677-e143-4dcb-9773-0e26ee990975'
    },
    created_at: '2025-08-21T18:12:51.086489',
    updated_at: '2025-08-21T18:12:51.086504',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a34c321b4532f9a458'),
    product_id: 'prod_60e20bd6-2e77-4300-bc5a-f5f97369c5d4',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: '1 Bedroom Apartment',
    price: 1025324,
    quantity: 1,
    currency: 'VND',
    description: 'Căn hộ 1 phòng ngủ với diện tích rộng rãi, cung cấp không gian riêng tư và tiện nghi như phòng khách, bếp nhỏ. Giá ưu đãi đã bao gồm bữa sáng và có tùy chọn hủy miễn phí.',
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
      description: 'Căn hộ 1 phòng ngủ với diện tích rộng rãi, cung cấp không gian riêng tư và tiện nghi như phòng khách, bếp nhỏ. Giá ưu đãi đã bao gồm bữa sáng và có tùy chọn hủy miễn phí.',
      content_for_embedding: 'Căn hộ 1 phòng ngủ. Rộng rãi, tiện nghi với bếp riêng. Giá ưu đãi bao gồm bữa sáng, WiFi miễn phí. Có các tùy chọn hủy miễn phí và phương thức thanh toán linh hoạt.',
      retrieval_context: 'Căn hộ 1 phòng ngủ là lựa chọn lý tưởng cho các cặp đôi hoặc gia đình nhỏ, với giá ưu đãi cho 2 người. Lựa chọn 1 có giá 1.025.324 VND (giảm 51% từ 2.081.695 VND), bao gồm bữa sáng, hủy miễn phí trước ngày đặt và thanh toán ngay. Lựa chọn 2 có giá 1.061.955 VND (giảm 49% từ 2.081.695 VND), cũng bao gồm bữa sáng, hủy miễn phí trước ngày đặt nhưng thanh toán sau.',
      other_info: {
        room_specifications: {
          size_sqm: null,
          max_occupancy: { adults: 2 },
          bed_configuration: null,
          balcony: null,
          amenities: { wifi: true, kitchenette: true },
          room_type: 'apartment'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày đặt',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_d5a2c1e1-d101-4aa1-a41a-cf588ded3171'
    },
    created_at: '2025-08-21T18:12:51.523286',
    updated_at: '2025-08-21T18:12:51.523296',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a34c321b4532f9a459'),
    product_id: 'prod_4b620878-3e27-4637-8001-12c8fba0e6d5',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: 'Superior Triple',
    price: 1174033,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Superior Triple được thiết kế cho 3 khách, cung cấp không gian thoải mái với các tiện nghi cơ bản và bữa sáng đi kèm. Có hai tùy chọn thanh toán và hủy phòng linh hoạt.',
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
      description: 'Phòng Superior Triple được thiết kế cho 3 khách, cung cấp không gian thoải mái với các tiện nghi cơ bản và bữa sáng đi kèm. Có hai tùy chọn thanh toán và hủy phòng linh hoạt.',
      content_for_embedding: 'Phòng Superior Triple cho 3 người. Giá ưu đãi bao gồm bữa sáng và WiFi miễn phí. Có lựa chọn hủy miễn phí với các phương thức thanh toán khác nhau.',
      retrieval_context: 'Phòng Superior Triple phù hợp cho nhóm 3 người với giá ưu đãi hấp dẫn. Lựa chọn 1 có giá 1.174.033 VND (giảm 33% từ 1.743.977 VND), bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay. Lựa chọn 2 có giá 1.246.276 VND (giảm 29% từ 1.743.977 VND), cũng bao gồm bữa sáng, hủy miễn phí trước ngày nhưng thanh toán sau.',
      other_info: {
        room_specifications: {
          max_occupancy: { adults: 3 },
          amenities: { wifi: true },
          room_type: 'superior_triple'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_9f80d0b1-b644-48e7-b79c-ca038cec1bc4'
    },
    created_at: '2025-08-21T18:12:51.890582',
    updated_at: '2025-08-21T18:12:51.890598',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a44c321b4532f9a45a'),
    product_id: 'prod_d567af70-dbf5-440c-807f-c8a746fb96b6',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: 'Superior Family Room',
    price: 1531287,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Superior Family Room rộng rãi dành cho 4 khách, cung cấp không gian sinh hoạt chung tiện nghi, lý tưởng cho các gia đình. Giá đã bao gồm bữa sáng và có các lựa chọn thanh toán linh hoạt.',
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
      description: 'Phòng Superior Family Room rộng rãi dành cho 4 khách, cung cấp không gian sinh hoạt chung tiện nghi, lý tưởng cho các gia đình. Giá đã bao gồm bữa sáng và có các lựa chọn thanh toán linh hoạt.',
      content_for_embedding: 'Phòng Superior Family Room cho 4 người. Rộng rãi, tiện nghi, lý tưởng cho gia đình. Giá ưu đãi bao gồm bữa sáng và WiFi miễn phí. Có lựa chọn hủy miễn phí và các phương thức thanh toán khác nhau.',
      retrieval_context: 'Phòng Superior Family Room được thiết kế để đáp ứng nhu cầu của các gia đình hoặc nhóm lên đến 4 người. Lựa chọn 1 có giá 1.531.287 VND (giảm 33% từ 2.285.483 VND), bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay. Lựa chọn 2 có giá 1.623.977 VND (giảm 29% từ 2.285.483 VND), cũng bao gồm bữa sáng, hủy miễn phí trước ngày nhưng thanh toán sau.',
      other_info: {
        room_specifications: {
          max_occupancy: { adults: 4 },
          amenities: { wifi: true },
          room_type: 'family'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_f7b651c9-ad16-42fb-88f9-358a4c02c76a'
    },
    created_at: '2025-08-21T18:12:52.289028',
    updated_at: '2025-08-21T18:12:52.289040',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a44c321b4532f9a45b'),
    product_id: 'prod_f2aeea11-8899-4f2b-a7ca-292b7bb6ea5f',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: 'Deluxe Seaview',
    price: 911211,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Deluxe Seaview với tầm nhìn tuyệt đẹp ra biển, diện tích 30 m² và các tiện nghi cao cấp, bao gồm ban công riêng. Giá ưu đãi đã bao gồm bữa sáng và có các tùy chọn thanh toán, hủy phòng linh hoạt.',
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
      description: 'Phòng Deluxe Seaview với tầm nhìn tuyệt đẹp ra biển, diện tích 30 m² và các tiện nghi cao cấp, bao gồm ban công riêng. Giá ưu đãi đã bao gồm bữa sáng và có các tùy chọn thanh toán, hủy phòng linh hoạt.',
      content_for_embedding: 'Phòng Deluxe Seaview. Diện tích 30m², ban công riêng, nhìn ra biển. Giá ưu đãi bao gồm bữa sáng và WiFi miễn phí. Có lựa chọn hủy miễn phí và các phương thức thanh toán khác nhau.',
      retrieval_context: 'Phòng Deluxe Seaview mang đến trải nghiệm nghỉ dưỡng đẳng cấp với tầm nhìn trực diện ra biển, diện tích 30 m² và ban công riêng. Giá phòng cho 2 người có 2 lựa chọn: Lựa chọn 1 có giá 911.211 VND (giảm 48% từ 1.748.625 VND), bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay. Lựa chọn 2 có giá 950.345 VND (giảm 46% từ 1.748.625 VND), cũng bao gồm bữa sáng, hủy miễn phí trước ngày nhưng thanh toán sau.',
      other_info: {
        room_specifications: {
          size_sqm: 30,
          max_occupancy: { adults: 2 },
          bed_configuration: null,
          view_type: 'sea_view',
          balcony: true,
          amenities: { wifi: true },
          room_type: 'deluxe'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_50469986-0efa-48ef-8144-7d415f8fc21c'
    },
    created_at: '2025-08-21T18:12:52.682297',
    updated_at: '2025-08-21T18:12:52.682308',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a54c321b4532f9a45c'),
    product_id: 'prod_152b0ab9-a05f-4c69-877f-84b63ccecf6d',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: 'Deluxe Family Room',
    price: 1582302,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Deluxe Family Room là không gian lý tưởng cho gia đình 4 người, với thiết kế sang trọng, tiện nghi và tầm nhìn đẹp. Giá ưu đãi đã bao gồm bữa sáng, có các tùy chọn thanh toán và hủy phòng linh hoạt.',
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
      description: 'Phòng Deluxe Family Room là không gian lý tưởng cho gia đình 4 người, với thiết kế sang trọng, tiện nghi và tầm nhìn đẹp. Giá ưu đãi đã bao gồm bữa sáng, có các tùy chọn thanh toán và hủy phòng linh hoạt.',
      content_for_embedding: 'Phòng Deluxe Family Room cho 4 người. Sang trọng, tiện nghi, lý tưởng cho gia đình. Giá ưu đãi bao gồm bữa sáng và WiFi miễn phí. Có lựa chọn hủy miễn phí và các phương thức thanh toán khác nhau.',
      retrieval_context: 'Phòng Deluxe Family Room cung cấp không gian nghỉ dưỡng sang trọng và tiện nghi cho tối đa 4 khách. Lựa chọn 1 có giá 1.582.302 VND (giảm 31% từ 2.305.818 VND), bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay. Lựa chọn 2 có giá 1.678.961 VND (giảm 27% từ 2.305.818 VND), cũng bao gồm bữa sáng, hủy miễn phí trước ngày nhưng thanh toán sau.',
      other_info: {
        room_specifications: {
          max_occupancy: { adults: 4 },
          amenities: { wifi: true },
          room_type: 'family'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_e7cd62e8-407e-45b0-9c16-43aba72b915e'
    },
    created_at: '2025-08-21T18:12:53.075818',
    updated_at: '2025-08-21T18:12:53.075831',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a54c321b4532f9a45d'),
    product_id: 'prod_d33029c2-ae07-4133-ae97-f5a982f600c7',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: 'Grand Suite Sea View',
    price: 1630903,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Grand Suite Sea View là hạng phòng cao cấp nhất, mang đến không gian sang trọng, tầm nhìn biển ngoạn mục và các tiện nghi đẳng cấp. Giá đã bao gồm bữa sáng và có tùy chọn thanh toán linh hoạt.',
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
      description: 'Phòng Grand Suite Sea View là hạng phòng cao cấp nhất, mang đến không gian sang trọng, tầm nhìn biển ngoạn mục và các tiện nghi đẳng cấp. Giá đã bao gồm bữa sáng và có tùy chọn thanh toán linh hoạt.',
      content_for_embedding: 'Phòng Grand Suite Sea View. Hạng phòng cao cấp nhất, sang trọng, tầm nhìn biển ngoạn mục. Giá ưu đãi bao gồm bữa sáng và WiFi miễn phí. Có lựa chọn hủy miễn phí và các phương thức thanh toán khác nhau.',
      retrieval_context: 'Phòng Grand Suite Sea View là lựa chọn tối ưu cho kỳ nghỉ sang trọng với tầm nhìn biển tuyệt đẹp. Giá phòng cho 2 người: Lựa chọn 1 có giá 1.630.903 VND (giảm 19% từ 2.011.140 VND), bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay. Lựa chọn 2 có giá 2.308.333 VND, bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau.',
      other_info: {
        room_specifications: {
          max_occupancy: { adults: 2 },
          view_type: 'sea_view',
          amenities: { wifi: true },
          room_type: 'suite'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_1b20d38d-7027-4831-a312-9e947f953fdb'
    },
    created_at: '2025-08-21T18:12:53.476295',
    updated_at: '2025-08-21T18:12:53.476307',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a54c321b4532f9a45e'),
    product_id: 'prod_4f9e75c3-5031-48db-aa7d-a0e94b2a692b',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: '2 Bed Apartment',
    price: 1735565,
    quantity: 1,
    currency: 'VND',
    description: 'Căn hộ 2 phòng ngủ là lựa chọn lý tưởng cho các gia đình hoặc nhóm bạn, cung cấp không gian rộng rãi, tiện nghi với phòng khách và bếp riêng. Giá đã bao gồm bữa sáng và có các tùy chọn thanh toán, hủy phòng linh hoạt.',
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
      description: 'Căn hộ 2 phòng ngủ là lựa chọn lý tưởng cho các gia đình hoặc nhóm bạn, cung cấp không gian rộng rãi, tiện nghi với phòng khách và bếp riêng. Giá đã bao gồm bữa sáng và có các tùy chọn thanh toán, hủy phòng linh hoạt.',
      content_for_embedding: 'Căn hộ 2 phòng ngủ. Rộng rãi, tiện nghi cho gia đình hoặc nhóm bạn. Giá ưu đãi bao gồm bữa sáng và WiFi miễn phí. Có lựa chọn hủy miễn phí và các phương thức thanh toán khác nhau.',
      retrieval_context: 'Căn hộ 2 phòng ngủ cung cấp không gian sinh hoạt thoải mái cho tối đa 4 người, bao gồm phòng khách và bếp riêng. Lựa chọn 1 có giá 1.735.565 VND (giảm 38% từ 2.806.903 VND), bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay. Lựa chọn 2 có giá 1.862.148 VND (giảm 34% từ 2.806.903 VND), cũng bao gồm bữa sáng, hủy miễn phí trước ngày nhưng thanh toán sau.',
      other_info: {
        room_specifications: {
          max_occupancy: { adults: 4 },
          amenities: { wifi: true, kitchenette: true },
          room_type: 'apartment'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_2b26ba9e-ddf2-4647-9802-5d6e23bfd8bf'
    },
    created_at: '2025-08-21T18:12:53.843786',
    updated_at: '2025-08-21T18:12:53.843798',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a64c321b4532f9a45f'),
    product_id: 'prod_481afba6-0004-4d32-92b4-607df174ad19',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: 'Standard Triple Room',
    price: 1891667,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Standard Triple dành cho 3 khách, với tùy chọn không bao gồm bữa sáng hoặc có bao gồm bữa sáng. Cả hai lựa chọn đều có chính sách hủy miễn phí trước ngày và thanh toán linh hoạt.',
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
      description: 'Phòng Standard Triple dành cho 3 khách, với tùy chọn không bao gồm bữa sáng hoặc có bao gồm bữa sáng. Cả hai lựa chọn đều có chính sách hủy miễn phí trước ngày và thanh toán linh hoạt.',
      content_for_embedding: 'Phòng Standard Triple cho 3 người. Có tùy chọn không bao gồm bữa sáng (có thể mua thêm) hoặc bao gồm bữa sáng. Giá tốt, có hủy miễn phí và WiFi miễn phí.',
      retrieval_context: 'Phòng Standard Triple cung cấp không gian cho 3 khách với 2 lựa chọn giá: Lựa chọn 1 có giá 1.891.667 VND, không bao gồm bữa sáng (có thể thêm 120.000 VND/người), hủy miễn phí trước ngày và thanh toán ngay. Lựa chọn 2 có giá 1.958.333 VND, bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau.',
      other_info: {
        room_specifications: {
          max_occupancy: { adults: 3 },
          amenities: { wifi: true },
          room_type: 'triple'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_32aa5d8d-99e3-4a77-92b1-80327984a871'
    },
    created_at: '2025-08-21T18:12:54.214844',
    updated_at: '2025-08-21T18:12:54.214858',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a64c321b4532f9a460'),
    product_id: 'prod_d49db362-42db-4f5b-b1d8-18fade07f8b2',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: 'Grand Family Room',
    price: 2143918,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Grand Family Room là lựa chọn lý tưởng cho các nhóm lớn hoặc gia đình, cung cấp không gian rộng rãi và tiện nghi. Có nhiều tùy chọn về sức chứa, giá cả và phương thức thanh toán.',
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
      description: 'Phòng Grand Family Room là lựa chọn lý tưởng cho các nhóm lớn hoặc gia đình, cung cấp không gian rộng rãi và tiện nghi. Có nhiều tùy chọn về sức chứa, giá cả và phương thức thanh toán.',
      content_for_embedding: 'Phòng Grand Family Room. Rộng rãi, tiện nghi cho gia đình hoặc nhóm lớn. Giá ưu đãi bao gồm bữa sáng và WiFi miễn phí. Có nhiều tùy chọn sức chứa và phương thức thanh toán khác nhau, bao gồm hủy miễn phí.',
      retrieval_context: 'Phòng Grand Family Room là hạng phòng cao cấp dành cho gia đình hoặc nhóm, với các lựa chọn sức chứa linh hoạt. Lựa chọn 1 (4 người) có giá 2.143.918 VND (giảm 31% từ 3.106.493 VND), bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán ngay. Lựa chọn 2 (6 người) có giá 2.300.949 VND (giảm 26% từ 3.106.493 VND), bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau. Lựa chọn 3 (2 người) có giá 2.347.549 VND (giảm 24% từ 3.106.493 VND), cũng bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán sau.',
      other_info: {
        room_specifications: {
          max_occupancy: { adults: 6 },
          amenities: { wifi: true },
          room_type: 'family'
        },
        booking_info: {
          cancellation_policy: 'Hủy miễn phí trước ngày',
          payment_methods: [ 'thanh_toan_ngay', 'thanh_toan_sau' ]
        }
      },
      product_id: 'prod_b4feeb34-54b7-4d50-9095-066d6fcf9448'
    },
    created_at: '2025-08-21T18:12:54.593706',
    updated_at: '2025-08-21T18:12:54.593719',
    status: 'active'
  },
  {
    _id: ObjectId('68a761a64c321b4532f9a461'),
    product_id: 'prod_cb4fdd63-eb0b-48b8-ad5b-9cfc1c8443b3',
    company_id: '1e789800-b402-41b0-99d6-2e8d494a3beb',
    item_type: 'product',
    file_id: null,
    file_name: null,
    name: 'Quadruple Room with Balcony',
    price: 2695000,
    quantity: 1,
    currency: 'VND',
    description: 'Phòng Quadruple với ban công, lý tưởng cho 4 khách, cung cấp không gian thoáng đãng và tiện nghi. Có hai lựa chọn giá với chính sách hủy phòng và thanh toán khác nhau.',
    category: 'phong_o',
    sku: null,
    tags: [],
    raw_ai_data: {
      id: 12,
      name: 'Quadruple Room with Balcony',
      prices: { price_1: 2695000, price_2: 2750000, currency: 'VND' },
      conditions: {
        condition_price_1: 'Bao gồm bữa sáng | Không được hủy (giá thấp) | Thanh toán tại khách sạn',
        condition_price_2: 'Bao gồm bữa sáng | Hủy miễn phí trước ngày | Thanh toán tại khách sạn',
        occupancy_price_1: 4,
        occupancy_price_2: 4
      },
      category: 'phong_o',
      quantity: 1,
      description: 'Phòng Quadruple với ban công, lý tưởng cho 4 khách, cung cấp không gian thoáng đãng và tiện nghi. Có hai lựa chọn giá với chính sách hủy phòng và thanh toán khác nhau.',
      content_for_embedding: 'Phòng Quadruple có ban công cho 4 người. Giá ưu đãi bao gồm bữa sáng và WiFi miễn phí. Có lựa chọn hủy miễn phí hoặc giá thấp hơn với điều kiện không hủy.',
      retrieval_context: 'Phòng Quadruple với ban công, phù hợp cho nhóm 4 khách, có hai lựa chọn giá: Lựa chọn 1 có giá 2.695.000 VND, bao gồm bữa sáng, không được hủy (giá thấp) và thanh toán tại khách sạn. Lựa chọn 2 có giá 2.750.000 VND, cũng bao gồm bữa sáng, hủy miễn phí trước ngày và thanh toán tại khách sạn.',
      other_info: {
        room_specifications: {
          max_occupancy: { adults: 4 },
          balcony: true,
          amenities: { wifi: true },
          room_type: 'quadruple'
        },
        booking_info: {
          cancellation_policy: 'Không được hủy | Hủy miễn phí trước ngày',
          payment_methods: [ 'thanh_toan_tai_khach_san' ]
        }
      },
      product_id: 'prod_1d988962-5a2a-4acb-9494-fbba06b467f6'
    },
    created_at: '2025-08-21T18:12:54.977979',
    updated_at: '2025-08-21T18:12:54.977989',
    status: 'active'
  }
]