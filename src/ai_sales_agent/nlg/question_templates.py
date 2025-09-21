"""
Question templates for each step/sub-step of the loan application process
"""

# ==========================================================================
# STEP 1.1: THÔNG TIN KHOẢN VAY CHÍNH (loanAmount, loanTerm, loanPurpose)
# ==========================================================================

STEP_1_1_TEMPLATES = {
    "first_question": [
        "Chào bạn! Tôi sẽ hỗ trợ bạn hoàn thành hồ sơ thẩm định vay. Để bắt đầu, vui lòng cho biết:\n• Số tiền bạn muốn vay\n• Thời hạn vay mong muốn\n• Mục đích sử dụng khoản vay",
        "Xin chào! Để tôi có thể tư vấn tốt nhất cho bạn, vui lòng cung cấp thông tin cơ bản về nhu cầu vay của bạn:\n• Số tiền cần vay (ví dụ: 500 triệu, 2 tỷ)\n• Thời hạn vay (từ 1-20 năm)\n• Mục đích vay (mua nhà, kinh doanh, tiêu dùng...)",
        "Chào mừng bạn đến với dịch vụ thẩm định vay! Tôi cần một số thông tin để bắt đầu:\n• Số tiền vay mong muốn\n• Thời gian vay dự kiến\n• Lý do cần vay"
    ],
    
    "missing_amount": [
        "Bạn vui lòng cho biết số tiền cụ thể muốn vay? (từ 10 triệu đến 500 tỷ đồng)",
        "Số tiền vay bạn mong muốn là bao nhiêu? Vui lòng nhập cụ thể (ví dụ: 500 triệu, 2 tỷ)",
        "Tôi cần biết số tiền vay để có thể tư vấn phù hợp. Bạn muốn vay bao nhiêu?"
    ],
    
    "missing_term": [
        "Bạn dự định vay trong thời gian bao lâu? (có thể chọn: 1-5 năm, 10 năm, 15 năm, 20 năm)",
        "Thời hạn vay bạn mong muốn là bao nhiêu năm?",
        "Vui lòng cho biết thời gian vay dự kiến (từ 1 đến 20 năm)"
    ],
    
    "missing_purpose": [
        "Bạn có thể cho biết mục đích sử dụng khoản vay không? (mua nhà, kinh doanh, tiêu dùng, mua xe...)",
        "Khoản vay này bạn sẽ sử dụng để làm gì?",
        "Vui lòng cho biết lý do bạn cần vay tiền?"
    ],
    
    "missing_multiple": [
        "Cảm ơn thông tin! Bạn còn cần cho biết thêm: {missing_fields}",
        "Để hoàn thành bước này, tôi cần biết thêm về {missing_fields}",
        "Vui lòng bổ sung thông tin: {missing_fields}"
    ],
    
    # Validation errors
    "amount_too_low": [
        "Số tiền vay tối thiểu là 10 triệu đồng. Vui lòng nhập số tiền từ 10 triệu trở lên.",
        "Xin lỗi, hạn mức vay tối thiểu của chúng tôi là 10 triệu đồng. Bạn có thể điều chỉnh số tiền vay."
    ],
    
    "amount_too_high": [
        "Số tiền vay tối đa là 500 tỷ đồng. Vui lòng nhập số tiền nhỏ hơn.",
        "Hạn mức vay tối đa hiện tại là 500 tỷ đồng. Bạn có thể điều chỉnh số tiền phù hợp."
    ]
}

# ==========================================================================
# STEP 1.2: THÔNG TIN KHOẢN VAY BỔ SUNG (loanType, salesAgentCode)
# ==========================================================================

STEP_1_2_TEMPLATES = {
    "first_question": [
        "Cảm ơn bạn! Tiếp theo, vui lòng cho biết:\n• Hình thức vay: Thế chấp (có tài sản đảm bảo) hay Tín chấp (không cần tài sản)?\n• Mã nhân viên tư vấn (nếu có)",
        "Tuyệt vời! Bây giờ tôi cần biết thêm:\n• Bạn muốn vay theo hình thức nào: Thế chấp hay Tín chấp?\n• Bạn có mã giới thiệu của nhân viên tư vấn không?",
        "Để tiếp tục, vui lòng cho biết:\n• Loại hình vay (Thế chấp/Tín chấp)\n• Mã nhân viên (nếu có nhân viên hỗ trợ)"
    ],
    
    "missing_type": [
        "Bạn muốn vay theo hình thức nào:\n• Thế chấp: Có tài sản đảm bảo (nhà đất, xe...)\n• Tín chấp: Không cần tài sản đảm bảo",
        "Vui lòng chọn hình thức vay phù hợp:\n- Thế chấp (có tài sản)\n- Tín chấp (không cần tài sản)",
        "Bạn có tài sản để thế chấp không? Hay muốn vay tín chấp?"
    ],
    
    "missing_agent": [
        "Bạn có mã nhân viên tư vấn không? (không bắt buộc)",
        "Nếu có nhân viên hỗ trợ, vui lòng cung cấp mã nhân viên.",
        "Mã giới thiệu nhân viên (nếu có): "
    ],
    
    "completion": [
        "Hoàn thành! Chúng tôi đã ghi nhận thông tin khoản vay của bạn:\n• Số tiền: {loanAmount:,} VND\n• Thời hạn: {loanTerm}\n• Mục đích: {loanPurpose}\n• Hình thức: {loanType}",
        "Cảm ơn bạn! Thông tin khoản vay đã được ghi nhận đầy đủ."
    ]
}

# ==========================================================================
# STEP 2.1: THÔNG TIN CÁ NHÂN CỞ BẢN (fullName, phoneNumber, birthYear)
# ==========================================================================

STEP_2_1_TEMPLATES = {
    "first_question": [
        "Cảm ơn bạn! Tiếp theo, vui lòng cung cấp thông tin cá nhân cơ bản:\n• Họ và tên đầy đủ\n• Số điện thoại liên hệ\n• Năm sinh",
        "Tuyệt vời! Bây giờ tôi cần một số thông tin cá nhân:\n• Họ tên của bạn\n• Số điện thoại\n• Năm sinh (hoặc tuổi)",
        "Để tiếp tục quy trình, vui lòng cho biết:\n• Họ và tên\n• Số điện thoại (10 số)\n• Năm sinh của bạn"
    ],
    
    "missing_name": [
        "Vui lòng cho biết họ và tên đầy đủ của bạn.",
        "Họ tên của bạn là gì?",
        "Tôi cần biết tên đầy đủ của bạn để tiếp tục."
    ],
    
    "missing_phone": [
        "Vui lòng cung cấp số điện thoại liên hệ (10 số).",
        "Số điện thoại của bạn là bao nhiêu?",
        "Cho tôi xin số điện thoại để chúng tôi có thể liên hệ với bạn."
    ],
    
    "missing_birthYear": [
        "Bạn sinh năm nào? (hoặc bao nhiêu tuổi)",
        "Vui lòng cho biết năm sinh của bạn.",
        "Năm sinh của bạn là?"
    ],
    
    "missing_multiple": [
        "Cảm ơn {name}! Tôi cần thêm: {missing_fields}",
        "Vui lòng bổ sung: {missing_fields}",
        "Để hoàn thành thông tin cá nhân cơ bản, cần thêm: {missing_fields}"
    ],
    
    # Validation errors
    "invalid_phone": [
        "Số điện thoại không hợp lệ. Vui lòng nhập 10 số (ví dụ: 0901234567)",
        "Định dạng số điện thoại chưa đúng. Vui lòng nhập lại số điện thoại 10 số."
    ],
    
    "invalid_birthYear": [
        "Năm sinh không hợp lệ. Bạn phải từ 18 đến 65 tuổi để đăng ký vay.",
        "Vui lòng nhập năm sinh hợp lệ (độ tuổi từ 18-65)."
    ]
}

# ==========================================================================
# STEP 2.2: THÔNG TIN CÁ NHÂN BỔ SUNG (gender, maritalStatus, dependents, email)
# ==========================================================================

STEP_2_2_TEMPLATES = {
    "first_question": [
        "Cảm ơn {name}! Vui lòng cho biết thêm một số thông tin:\n• Giới tính (Nam/Nữ)\n• Tình trạng hôn nhân (Độc thân/Đã kết hôn/Ly hôn/Góa)\n• Số người phụ thuộc\n• Email (không bắt buộc)",
        "Tuyệt vời {name}! Để hoàn thành hồ sơ, tôi cần biết:\n• Giới tính của bạn\n• Tình trạng hôn nhân hiện tại\n• Có bao nhiêu người phụ thuộc vào thu nhập của bạn\n• Địa chỉ email (có thể bỏ qua)",
        "Cảm ơn {name}! Vui lòng cung cấp thêm:\n• Nam hay Nữ?\n• Đã kết hôn chưa?\n• Số người phụ thuộc (vợ/chồng, con cái, bố mẹ...)\n• Email liên hệ (tùy chọn)"
    ],
    
    "missing_gender": [
        "Giới tính của bạn là Nam hay Nữ?",
        "Vui lòng cho biết giới tính (Nam/Nữ).",
        "Bạn là Nam hay Nữ?"
    ],
    
    "missing_maritalStatus": [
        "Tình trạng hôn nhân hiện tại của bạn:\n• Độc thân\n• Đã kết hôn\n• Ly hôn\n• Góa",
        "Bạn đã kết hôn chưa? (Độc thân/Đã kết hôn/Ly hôn/Góa)",
        "Vui lòng cho biết tình trạng hôn nhân của bạn."
    ],
    
    "missing_dependents": [
        "Có bao nhiêu người đang phụ thuộc tài chính vào bạn? (vợ/chồng, con cái, bố mẹ...)",
        "Số người phụ thuộc vào thu nhập của bạn là bao nhiêu?",
        "Bạn đang nuôi dưỡng bao nhiêu người?"
    ],
    
    "missing_email": [
        "Bạn có muốn cung cấp email không? (không bắt buộc)",
        "Email liên hệ của bạn (có thể bỏ qua):",
        "Địa chỉ email (tùy chọn):"
    ],
    
    "missing_multiple": [
        "Cảm ơn! Còn cần: {missing_fields}",
        "Vui lòng cho biết thêm: {missing_fields}",
        "Để hoàn tất, cần thông tin: {missing_fields}"
    ],
    
    "completion": [
        "Hoàn thành! Cảm ơn {name} đã cung cấp đầy đủ thông tin cá nhân.\n\nTóm tắt hồ sơ:\n• Khoản vay: {loanAmount:,} VND trong {loanTerm}\n• Mục đích: {loanPurpose}\n• Hình thức: {loanType}\n• Người vay: {name} - {gender} - {maritalStatus}",
        "Cảm ơn {name}! Chúng tôi đã ghi nhận đầy đủ thông tin của bạn và sẽ tiến hành thẩm định trong thời gian sớm nhất."
    ]
}

# ==========================================================================
# STEP 3.1: TÀI SẢN ĐẢM BẢO - LOẠI VÀ THÔNG TIN (collateralType, collateralInfo)
# ==========================================================================

STEP_3_1_TEMPLATES = {
    "first_question": [
        "Bây giờ về tài sản đảm bảo. Anh/chị có tài sản gì để thế chấp?\n• Loại tài sản (Bất động sản/Ô tô/Xe máy/Vàng/Giấy tờ có giá...)\n• Mô tả chi tiết về tài sản",
        "Anh/chị vui lòng cho biết:\n• Loại tài sản thế chấp (nhà đất, ô tô, xe máy, vàng...)\n• Thông tin chi tiết về tài sản đó",
        "Về tài sản đảm bảo, anh/chị cần cung cấp:\n• Tài sản gì dùng để thế chấp?\n• Mô tả cụ thể (địa chỉ, diện tích, năm sản xuất...)"
    ],
    
    "missing_collateralType": [
        "Loại tài sản thế chấp của anh/chị:\n• Bất động sản (nhà đất, căn hộ)\n• Ô tô\n• Xe máy\n• Vàng, trang sức\n• Giấy tờ có giá (sổ tiết kiệm, cổ phiếu)",
        "Anh/chị có tài sản gì để làm tài sản đảm bảo?",
        "Vui lòng cho biết loại tài sản thế chấp (nhà đất/ô tô/xe máy/vàng/khác)."
    ],
    
    "missing_collateralInfo": [
        "Vui lòng mô tả chi tiết về tài sản:\n• Nếu là nhà đất: địa chỉ, diện tích, tình trạng pháp lý\n• Nếu là xe: nhãn hiệu, năm sản xuất, biển số\n• Nếu là vàng: loại vàng, trọng lượng",
        "Anh/chị có thể cung cấp thông tin chi tiết về tài sản không?",
        "Thông tin cụ thể về tài sản thế chấp (địa chỉ, diện tích, năm sản xuất...)?"
    ],
    
    "missing_multiple": [
        "Cảm ơn! Còn cần thông tin về: {missing_fields}",
        "Vui lòng bổ sung: {missing_fields}",
        "Để hoàn thành bước này, cần: {missing_fields}"
    ]
}

# ==========================================================================
# STEP 3.2: TÀI SẢN ĐẢM BẢO - GIÁ TRỊ VÀ HÌNH ẢNH (collateralValue, collateralImage)
# ==========================================================================

STEP_3_2_TEMPLATES = {
    "first_question": [
        "Vui lòng cho biết:\n• Giá trị ước tính của tài sản (theo thị trường hiện tại)\n• Có hình ảnh/video tài sản không? (không bắt buộc)",
        "Anh/chị định giá tài sản này bao nhiêu và có ảnh chụp tài sản không?",
        "Thông tin về giá trị:\n• Giá trị tài sản ước tính (VNĐ)\n• Hình ảnh tài sản (nếu có)"
    ],
    
    "missing_collateralValue": [
        "Anh/chị ước tính tài sản này có giá trị bao nhiêu? (theo giá thị trường hiện tại)",
        "Giá trị của tài sản thế chấp là bao nhiêu?",
        "Vui lòng cho biết giá trị ước tính của tài sản (VNĐ)."
    ],
    
    "missing_collateralImage": [
        "Anh/chị có hình ảnh/video của tài sản không? (không bắt buộc)",
        "Có thể cung cấp ảnh chụp tài sản không? (tùy chọn)",
        "Hình ảnh tài sản (có thể gửi sau):"
    ],
    
    "missing_multiple": [
        "Cần bổ sung: {missing_fields}",
        "Vui lòng cung cấp thêm: {missing_fields}"
    ]
}

# ==========================================================================
# STEP 4.1: THÔNG TIN TÀI CHÍNH - THU NHẬP CHÍNH (monthlyIncome, primaryIncomeSource)
# ==========================================================================

STEP_4_1_TEMPLATES = {
    "first_question": [
        "Tiếp theo về thông tin tài chính. Vui lòng cho biết:\n• Thu nhập hàng tháng từ công việc chính\n• Nguồn thu nhập (Lương/Kinh doanh/Đầu tư/Hưu trí/Khác)",
        "Về thu nhập của anh/chị:\n• Mức thu nhập ổn định hàng tháng\n• Thu nhập từ đâu (làm công, kinh doanh, đầu tư...)",
        "Thông tin thu nhập:\n• Thu nhập hàng tháng (VNĐ)\n• Nguồn thu nhập chính"
    ],
    
    "missing_monthlyIncome": [
        "Thu nhập hàng tháng của anh/chị là bao nhiêu?",
        "Mức lương/thu nhập ổn định hàng tháng là bao nhiêu?",
        "Vui lòng cho biết thu nhập hàng tháng (VNĐ)."
    ],
    
    "missing_primaryIncomeSource": [
        "Nguồn thu nhập chính của anh/chị:\n• Lương (làm công)\n• Kinh doanh\n• Đầu tư\n• Hưu trí\n• Khác",
        "Thu nhập chính từ đâu? (lương công ty, kinh doanh, đầu tư...)",
        "Nguồn thu nhập chính của anh/chị là gì?"
    ],
    
    "missing_multiple": [
        "Cần thông tin về: {missing_fields}",
        "Vui lòng bổ sung: {missing_fields}"
    ]
}

# ==========================================================================
# STEP 4.2: THÔNG TIN TÀI CHÍNH - CÔNG VIỆC (companyName, jobTitle, workExperience)
# ==========================================================================

STEP_4_2_TEMPLATES = {
    "first_question": [
        "Thông tin công việc của anh/chị:\n• Tên công ty/nơi làm việc\n• Chức vụ/vai trò\n• Thời gian làm việc (số năm kinh nghiệm)",
        "Vui lòng cho biết:\n• Anh/chị làm việc ở đâu?\n• Chức vụ hiện tại\n• Đã làm việc bao lâu?",
        "Về công việc:\n• Nơi làm việc\n• Vị trí công việc\n• Số năm kinh nghiệm"
    ],
    
    "missing_companyName": [
        "Anh/chị làm việc tại công ty/tổ chức nào?",
        "Tên nơi làm việc của anh/chị?",
        "Vui lòng cho biết tên công ty/tổ chức anh/chị đang làm việc."
    ],
    
    "missing_jobTitle": [
        "Chức vụ/vai trò của anh/chị trong công ty là gì?",
        "Anh/chị đảm nhiệm vị trí nào?",
        "Chức danh công việc của anh/chị?"
    ],
    
    "missing_workExperience": [
        "Anh/chị có bao nhiều năm kinh nghiệm làm việc?",
        "Thời gian làm việc trong nghề/công ty hiện tại?",
        "Số năm kinh nghiệm của anh/chị là bao nhiêu?"
    ],
    
    "missing_multiple": [
        "Còn cần thông tin: {missing_fields}",
        "Vui lòng bổ sung: {missing_fields}"
    ]
}

# ==========================================================================
# STEP 4.3: THÔNG TIN TÀI CHÍNH - OPTIONAL (otherIncomeAmount, totalAssets, bankName)
# ==========================================================================

STEP_4_3_TEMPLATES = {
    "first_question": [
        "Một số thông tin bổ sung (có thể bỏ qua):\n• Thu nhập khác (cho thuê, đầu tư, freelance...)\n• Tổng giá trị tài sản hiện có\n• Ngân hàng nhận lương",
        "Anh/chị có muốn cung cấp thêm:\n• Thu nhập bổ sung từ nguồn khác?\n• Tài sản hiện có?\n• Ngân hàng thường giao dịch?",
        "Thông tin tùy chọn:\n• Thu nhập khác (nếu có)\n• Tổng tài sản\n• Ngân hàng nhận lương"
    ],
    
    "missing_otherIncomeAmount": [
        "Anh/chị có thu nhập khác ngoài công việc chính không? (cho thuê, kinh doanh phụ, đầu tư...)",
        "Thu nhập bổ sung hàng tháng (nếu có)?",
        "Nguồn thu nhập khác (có thể bỏ qua):"
    ],
    
    "missing_totalAssets": [
        "Tổng giá trị tài sản hiện có của anh/chị? (nhà đất, xe, tiền tiết kiệm...)",
        "Ước tính tổng tài sản (không bắt buộc):",
        "Tài sản hiện có (tùy chọn):"
    ],
    
    "missing_bankName": [
        "Ngân hàng nào anh/chị thường nhận lương/giao dịch?",
        "Ngân hàng chính của anh/chị?",
        "Tài khoản lương tại ngân hàng nào? (không bắt buộc)"
    ],
    
    "missing_multiple": [
        "Anh/chị có muốn bổ sung: {missing_fields}?",
        "Thông tin tùy chọn: {missing_fields}"
    ]
}

# ==========================================================================
# STEP 5.1: THÔNG TIN NỢ - KIỂM TRA (hasExistingDebt)
# ==========================================================================

STEP_5_1_TEMPLATES = {
    "first_question": [
        "Về tình hình nợ hiện tại: Anh/chị có đang vay nợ ở ngân hàng hoặc tổ chức tín dụng nào không?",
        "Anh/chị hiện tại có khoản vay nào đang phải trả không?",
        "Câu hỏi cuối về nợ: Có đang vay tiền ở đâu không?"
    ],
    
    "missing_hasExistingDebt": [
        "Anh/chị có đang vay nợ ở ngân hàng/tổ chức tín dụng nào không? (Có/Không)",
        "Hiện tại có khoản nợ nào đang phải trả không?",
        "Tình trạng nợ: Có hay không có nợ?"
    ]
}

# ==========================================================================
# STEP 5.2: THÔNG TIN NỢ - CHI TIẾT (totalDebtAmount, monthlyDebtPayment, cicCreditScoreGroup)
# ==========================================================================

STEP_5_2_TEMPLATES = {
    "first_question": [
        "Vui lòng cho biết chi tiết về các khoản nợ:\n• Tổng dư nợ hiện tại (tất cả ngân hàng)\n• Số tiền phải trả hàng tháng\n• Nhóm nợ CIC (nếu biết)",
        "Thông tin chi tiết về nợ:\n• Tổng số nợ còn lại\n• Số tiền trả mỗi tháng\n• Xếp hạng tín dụng CIC (nếu có)",
        "Chi tiết khoản nợ:\n• Dư nợ tổng cộng\n• Trả hàng tháng bao nhiêu\n• Nhóm nợ CIC"
    ],
    
    "missing_totalDebtAmount": [
        "Tổng dư nợ hiện tại của anh/chị là bao nhiêu? (cộng tất cả các ngân hàng)",
        "Số nợ còn lại cần trả là bao nhiêu?",
        "Tổng cộng đang nợ bao nhiêu tiền?"
    ],
    
    "missing_monthlyDebtPayment": [
        "Hàng tháng anh/chị phải trả bao nhiêu tiền nợ?",
        "Số tiền trả nợ mỗi tháng là bao nhiêu?",
        "Khoản trả hàng tháng (tất cả khoản vay)?"
    ],
    
    "missing_cicCreditScoreGroup": [
        "Anh/chị có biết nhóm nợ CIC không? (Nhóm 1-5, không biết cũng được)",
        "Xếp hạng tín dụng CIC (nếu biết): Nhóm 1/2/3/4/5",
        "Nhóm nợ CIC của anh/chị (có thể bỏ qua):"
    ],
    
    "missing_multiple": [
        "Cần bổ sung thông tin về: {missing_fields}",
        "Vui lòng cho biết thêm: {missing_fields}"
    ],
    
    "completion": [
        "🎉 Hoàn thành! Cảm ơn {name} đã cung cấp đầy đủ thông tin. Hồ sơ vay sẽ được xử lý trong thời gian sớm nhất.",
        "🎉 Cảm ơn {name}! Chúng tôi đã thu thập đầy đủ thông tin cần thiết để thẩm định hồ sơ vay của bạn."
    ]
}

# ==========================================================================
# STEP 6: XÁC NHẬN THÔNG TIN TỔNG HỢP
# ==========================================================================

STEP_6_TEMPLATES = {
    "summary": [
        """📋 **XÁC NHẬN THÔNG TIN HỒ SƠ VAY**

**1️⃣ THÔNG TIN KHOẢN VAY**
• Số tiền vay: {loanAmount:,} VNĐ
• Thời hạn: {loanTerm}
• Mục đích: {loanPurpose}
• Hình thức: {loanType}

**2️⃣ THÔNG TIN CÁ NHÂN**  
• Họ tên: {fullName}
• Giới tính: {gender}
• Năm sinh: {birthYear}
• SĐT: {phoneNumber}
• Email: {email}
• Tình trạng hôn nhân: {maritalStatus}
• Số người phụ thuộc: {dependents}

**3️⃣ TÀI SẢN ĐẢM BẢO**
• Loại tài sản: {collateralType}
• Mô tả: {collateralInfo}
• Giá trị ước tính: {collateralValue:,} VNĐ

**4️⃣ THÔNG TIN TÀI CHÍNH**
• Thu nhập hàng tháng: {monthlyIncome:,} VNĐ
• Nguồn thu nhập: {primaryIncomeSource}
• Công ty: {companyName}
• Chức vụ: {jobTitle}
• Kinh nghiệm: {workExperience} năm
• Thu nhập khác: {otherIncomeAmount:,} VNĐ

**5️⃣ THÔNG TIN NỢ**
• Có nợ hiện tại: {hasExistingDebt}
• Tổng dư nợ: {totalDebtAmount:,} VNĐ
• Trả nợ hàng tháng: {monthlyDebtPayment:,} VNĐ

---
⚠️ **Vui lòng kiểm tra kỹ thông tin trên.**

Trả lời:
- **"Xác nhận"** - nếu thông tin chính xác
- **"Sửa [field]: [giá trị mới]"** - để chỉnh sửa
  Ví dụ: "Sửa thu nhập: 35 triệu\"""",
    ],
    
    "edit_instructions": [
        "Để chỉnh sửa thông tin, vui lòng nhập: Sửa [tên trường]: [giá trị mới]\n\nVí dụ:\n• Sửa thu nhập: 35 triệu\n• Sửa tên: Nguyễn Thị B\n• Sửa tài sản: 1 tỷ",
        "Bạn có thể sửa bất kỳ thông tin nào bằng cách nhập: Sửa + tên trường + giá trị mới\n\nHoặc trả lời 'Xác nhận' để tiếp tục thẩm định."
    ],
    
    "confirmation_success": [
        "Cảm ơn! Đã xác nhận thông tin thành công. Hệ thống đang tiến hành thẩm định hồ sơ của bạn...",
        "Thông tin đã được xác nhận. Vui lòng chờ kết quả thẩm định..."
    ],
    
    "edit_success": [
        "Đã cập nhật thông tin thành công. Vui lòng kiểm tra lại và xác nhận:",
        "Thông tin đã được điều chỉnh. Vui lòng xem lại và xác nhận hoặc tiếp tục chỉnh sửa:"
    ]
}

# ==========================================================================
# STEP 7: THẨM ĐỊNH HỒ SƠ VAY
# ==========================================================================

STEP_7_TEMPLATES = {
    "assessment_success": [
        """🎉 **THẨM ĐỊNH HỒ SƠ HOÀN TẤT**

{status_emoji} **KẾT QUẢ: {status}**

📊 **CHI TIẾT ĐÁNH GIÁ:**
• Điểm tín dụng: {creditScore}/850 ({creditRating})
• Tỷ lệ DTI: {dtiRatio}% ({dtiAssessment})
• Tỷ lệ LTV: {ltvRatio}% ({ltvAssessment})
• Độ tin cậy: {confidence}%

💰 **ĐIỀU KIỆN VAY:**
• Số tiền được duyệt: {approvedAmount:,} VNĐ
• Lãi suất: {interestRate}%/năm
• Kỳ hạn: {loanTerm}
• Trả góp hàng tháng: {monthlyPayment:,} VNĐ

{conditions_section}

{reasoning_section}

📞 **BƯỚC TIẾP THEO:**
Nhân viên tư vấn sẽ liên hệ trong 24h để hướng dẫn hoàn thiện hồ sơ.

Mã hồ sơ: **{applicationId}**"""
    ],
    
    "assessment_error": [
        "❌ **LỖI THẨM ĐỊNH**\n\nHệ thống tạm thời gặp sự cố. Vui lòng thử lại sau ít phút.\n\nMã lỗi: {error_code}",
        "⚠️ **THẨM ĐỊNH TẠM NGƯNG**\n\nDo lỗi kỹ thuật, quá trình thẩm định chưa thể hoàn thành. Chúng tôi sẽ liên hệ với bạn sớm nhất.\n\nLỗi: {error_message}"
    ],
    
    "processing": [
        "🔄 Đang thẩm định hồ sơ vay của bạn...\nVui lòng chờ trong giây lát.",
        "⏳ Hệ thống AI đang phân tích thông tin và đánh giá rủi ro...",
        "📊 Đang tính toán các chỉ số tài chính và mức độ tín nhiệm..."
    ]
}

# ==========================================================================
# FIELD DISPLAY MAPPINGS
# ==========================================================================

# Thêm templates mới
STEP_3_1_TEMPLATES = {}  # Đã định nghĩa ở trên
STEP_3_2_TEMPLATES = {}  # Đã định nghĩa ở trên  
STEP_4_1_TEMPLATES = {}  # Đã định nghĩa ở trên
STEP_4_2_TEMPLATES = {}  # Đã định nghĩa ở trên
STEP_4_3_TEMPLATES = {}  # Đã định nghĩa ở trên
STEP_5_1_TEMPLATES = {}  # Đã định nghĩa ở trên
STEP_5_2_TEMPLATES = {}  # Đã định nghĩa ở trên

FIELD_DISPLAY_NAMES = {
    # Step 1.1 fields
    "loanAmount": "số tiền vay",
    "loanTerm": "thời hạn vay",
    "loanPurpose": "mục đích vay",
    
    # Step 1.2 fields
    "loanType": "hình thức vay",
    "salesAgentCode": "mã nhân viên",
    
    # Step 2.1 fields
    "fullName": "họ tên",
    "phoneNumber": "số điện thoại",
    "birthYear": "năm sinh",
    
    # Step 2.2 fields
    "gender": "giới tính",
    "maritalStatus": "tình trạng hôn nhân",
    "dependents": "số người phụ thuộc",
    "email": "email",
    
    # Step 3.1 fields
    "collateralType": "loại tài sản đảm bảo",
    "collateralInfo": "thông tin tài sản",
    
    # Step 3.2 fields
    "collateralValue": "giá trị tài sản",
    "collateralImage": "hình ảnh tài sản",
    
    # Step 4.1 fields
    "monthlyIncome": "thu nhập hàng tháng",
    "primaryIncomeSource": "nguồn thu nhập chính",
    
    # Step 4.2 fields
    "companyName": "tên công ty",
    "jobTitle": "chức vụ",
    "workExperience": "kinh nghiệm làm việc",
    
    # Step 4.3 fields
    "otherIncomeAmount": "thu nhập khác",
    "totalAssets": "tổng tài sản",
    "bankName": "ngân hàng nhận lương",
    
    # Step 5.1 fields
    "hasExistingDebt": "tình trạng nợ",
    
    # Step 5.2 fields
    "totalDebtAmount": "tổng dư nợ",
    "monthlyDebtPayment": "số tiền trả hàng tháng",
    "cicCreditScoreGroup": "nhóm nợ CIC",
    
    # Step 6 fields
    "userConfirmation": "xác nhận thông tin",
    "corrections": "chỉnh sửa thông tin",
    
    # Step 7 fields
    "assessmentResult": "kết quả thẩm định",
    "applicationId": "mã hồ sơ"
}

# ==========================================================================
# SUGGESTED OPTIONS FOR CHOICE FIELDS
# ==========================================================================

FIELD_SUGGESTIONS = {
    "loanType": ["Thế chấp", "Tín chấp"],
    "loanTerm": ["01 năm", "02 năm", "03 năm", "05 năm", "10 năm", "15 năm", "20 năm"],
    "gender": ["Nam", "Nữ"],
    "maritalStatus": ["Độc thân", "Đã kết hôn", "Ly hôn", "Góa"],
    "loanPurpose": [
        "Vay mua bất động sản",
        "Vay kinh doanh", 
        "Vay tiêu dùng cá nhân",
        "Vay mua ô tô xe máy",
        "Vay học tập"
    ],
    "collateralType": [
        "Bất động sản",
        "Ô tô", 
        "Xe máy",
        "Vàng",
        "Giấy tờ có giá"
    ],
    "primaryIncomeSource": [
        "Lương",
        "Kinh doanh",
        "Đầu tư", 
        "Hưu trí",
        "Khác"
    ],
    "hasExistingDebt": ["Có", "Không"],
    "cicCreditScoreGroup": ["Nhóm 1", "Nhóm 2", "Nhóm 3", "Nhóm 4", "Nhóm 5"]
}

# ==========================================================================
# EXAMPLES FOR COMPLEX FIELDS
# ==========================================================================

FIELD_EXAMPLES = {
    "loanAmount": ["500 triệu", "2 tỷ", "100.000.000"],
    "phoneNumber": ["0901234567", "0987654321"],
    "birthYear": ["1990", "35 tuổi", "sinh năm 1985"],
    "fullName": ["Nguyễn Văn An", "Trần Thị Bình"],
    "dependents": ["2 con", "3 người", "không có người phụ thuộc"],
    "email": ["example@gmail.com", "user@bank.com"]
}
