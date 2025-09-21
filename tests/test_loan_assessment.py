"""
✅ TEST FILE FOR LOAN ASSESSMENT ENDPOINT
Test cases: Approved, Needs Review, Rejected
"""

import requests
import json
from datetime import datetime, timedelta
import time

# ✅ Configuration
AI_SERVICE_BASE_URL = "http://localhost:8000"  # Change to your server URL
ENDPOINT = "/api/loan/assessment"

def test_loan_assessment(test_case_data, case_name):
    """Test loan assessment endpoint with given data"""
    print(f"\n{'='*60}")
    print(f"🧪 TESTING: {case_name}")
    print(f"{'='*60}")
    
    try:
        # Send request
        start_time = time.time()
        response = requests.post(
            f"{AI_SERVICE_BASE_URL}{ENDPOINT}",
            headers={"Content-Type": "application/json"},
            json=test_case_data,
            timeout=60
        )
        duration = time.time() - start_time
        
        print(f"⏱️  Request duration: {duration:.2f}s")
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n✅ RESPONSE SUMMARY:")
            print(f"   Success: {result.get('success', False)}")
            print(f"   Application ID: {result.get('applicationId', 'N/A')}")
            print(f"   Assessment ID: {result.get('assessmentId', 'N/A')}")
            
            if result.get('success'):
                print(f"\n📋 ASSESSMENT RESULT:")
                print(f"   Status: {result.get('status', 'N/A')}")
                print(f"   Credit Score: {result.get('creditScore', 'N/A')}")
                print(f"   Confidence: {result.get('confidence', 'N/A')}")
                print(f"   Approved Amount: {result.get('approvedAmount', 'N/A'):,} VNĐ" if result.get('approvedAmount') else "   Approved Amount: N/A")
                print(f"   Interest Rate: {result.get('interestRate', 'N/A')}%")
                print(f"   Monthly Payment: {result.get('monthlyPayment', 'N/A'):,} VNĐ" if result.get('monthlyPayment') else "   Monthly Payment: N/A")
                print(f"   Loan to Value: {result.get('loanToValue', 'N/A'):.2%}" if result.get('loanToValue') else "   Loan to Value: N/A")
                print(f"   Debt to Income: {result.get('debtToIncome', 'N/A'):.2%}" if result.get('debtToIncome') else "   Debt to Income: N/A")
                
                print(f"\n🔍 REASONING:")
                reasoning = result.get('reasoning', 'N/A')
                if len(reasoning) > 200:
                    print(f"   {reasoning[:200]}...")
                else:
                    print(f"   {reasoning}")
                
                print(f"\n⚠️  RISK FACTORS:")
                risk_factors = result.get('riskFactors', [])
                for i, risk in enumerate(risk_factors[:3], 1):
                    print(f"   {i}. {risk}")
                
                print(f"\n💡 RECOMMENDATIONS:")
                recommendations = result.get('recommendations', [])
                for i, rec in enumerate(recommendations[:3], 1):
                    print(f"   {i}. {rec}")
                
                print(f"\n📊 PROCESSING DETAILS:")
                processing = result.get('processingDetails', {})
                print(f"   Processing Time: {processing.get('processingTime', 'N/A')}s")
                print(f"   Model Used: {processing.get('modelUsed', 'N/A')}")
                
            else:
                print(f"\n❌ ERROR:")
                print(f"   {result.get('error', 'Unknown error')}")
                
        else:
            print(f"\n❌ HTTP ERROR:")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:500]}...")
            
    except requests.exceptions.Timeout:
        print(f"\n⏰ TIMEOUT ERROR:")
        print(f"   Request timed out after 60 seconds")
        
    except requests.exceptions.ConnectionError:
        print(f"\n🔌 CONNECTION ERROR:")
        print(f"   Cannot connect to {AI_SERVICE_BASE_URL}")
        print(f"   Make sure the server is running")
        
    except Exception as e:
        print(f"\n💥 EXCEPTION:")
        print(f"   {str(e)}")

# ✅ TEST CASE 1: APPROVED LOAN (High income, low debt, good collateral)
test_case_approved = {
    "applicationId": "LOAN-TEST-APPROVED-001",
    "userId": "test_user_approved",
    "deviceId": "device_test_001",
    "currentStep": 6,
    "status": "submitted",
    "createdAt": "2025-06-01T09:00:00.000Z",
    "submittedAt": "2025-06-12T14:30:00.000Z",
    
    # Loan Information - Reasonable amount
    "loanAmount": 1500000000,  # 1.5 tỷ VNĐ
    "loanType": "Thế chấp",
    "loanTerm": "15 năm",
    "loanPurpose": "Mua nhà ở",
    
    # Personal Information
    "phoneNumber": "0987654321",
    "email": "approved@test.com",
    "maritalStatus": "Đã kết hôn",
    "dependents": 1,
    
    # ID Card Information - Good profile
    "idCardInfo": {
        "idNumber": "024789123456",
        "fullName": "NGUYỄN VĂN THÀNH",
        "dateOfBirth": "1980-05-15T00:00:00.000Z",  # 44 tuổi - prime age
        "gender": "Nam",
        "nationality": "Việt Nam",
        "placeOfOrigin": "Hà Nội, Việt Nam",
        "permanentAddress": "Số 123, Phố Láng Hạ, Phường Láng Hạ, Quận Đống Đa, Hà Nội",
        "dateOfIssue": "2020-05-15T00:00:00.000Z",
        "placeOfIssue": "Cục Cảnh sát ĐKQL cư trú và DLQG về dân cư",
        "expirationDate": None,
        "ethnicity": "Kinh",
        "religion": "Không",
        "ocrConfidence": 0.95
    },
    
    # Collateral Information - Excellent collateral
    "collateralType": "Bất động sản",
    "collateralInfo": """Căn hộ chung cư cao cấp Times City
- Địa chỉ: Tầng 20, Tòa T2, Times City, 458 Minh Khai, Hai Bà Trưng, Hà Nội
- Diện tích: 100m² (3 phòng ngủ, 2 phòng tắm)
- Hướng: Đông Nam, view công viên
- Nội thất: Đầy đủ nội thất cao cấp
- Tình trạng pháp lý: Sổ hồng riêng, không tranh chấp
- Thời gian xây dựng: 2018 (còn mới)
- Vị trí thuận tiện: Gần trường học, bệnh viện, trung tâm thương mại""",
    "collateralValue": 6000000000,  # 6 tỷ VNĐ - LTV = 25%
    
    # Financial Information - Strong finances
    "monthlyIncome": 120000000,  # 120 triệu/tháng
    "primaryIncomeSource": "Lương nhân viên",
    "companyName": "Công ty TNHH Samsung Electronics Việt Nam",
    "jobTitle": "Giám đốc kỹ thuật",
    "workExperience": 12,
    "otherIncome": "Thu nhập từ cho thuê nhà",
    "otherIncomeAmount": 30000000,  # 30 triệu/tháng
    "bankAccount": "1234567890123",
    "bankName": "Ngân hàng TMCP Đầu tư và Phát triển Việt Nam (BIDV)",
    "totalAssets": 12000000000,  # 12 tỷ VNĐ
    "liquidAssets": 2000000000,  # 2 tỷ VNĐ
    
    # Debt Information - Low debt
    "hasExistingDebt": True,
    "totalDebtAmount": 300000000,  # 300 triệu VNĐ
    "monthlyDebtPayment": 8000000,  # 8 triệu/tháng
    "cicCreditScoreGroup": "1",  # Excellent credit
    "creditHistory": "Lịch sử tín dụng xuất sắc, không có nợ xấu. Đã vay mua xe và trả đúng hạn.",
    "existingLoans": [
        {
            "lender": "Ngân hàng TMCP Công thương Việt Nam (VietinBank)",
            "amount": 300000000,
            "monthlyPayment": 8000000,
            "remainingTerm": "10 tháng"
        }
    ],
    
    # Administrative
    "ipAddress": "14.161.42.123",
    "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "termsAccepted": True,
    "termsAcceptedAt": "2025-06-01T09:05:00.000Z",
    "privacyPolicyAccepted": True,
    "dataProcessingConsent": True
}

# ✅ TEST CASE 2: NEEDS REVIEW (Medium income, moderate debt, requires conditions)
test_case_needs_review = {
    "applicationId": "LOAN-TEST-REVIEW-002",
    "userId": "test_user_review",
    "deviceId": "device_test_002",
    "currentStep": 6,
    "status": "submitted",
    "createdAt": "2025-06-01T09:00:00.000Z",
    "submittedAt": "2025-06-12T14:30:00.000Z",
    
    # Loan Information
    "loanAmount": 2000000000,  # 2 tỷ VNĐ
    "loanType": "Thế chấp",
    "loanTerm": "20 năm",
    "loanPurpose": "Mua nhà ở và kinh doanh",
    
    # Personal Information
    "phoneNumber": "0912345678",
    "email": "review@test.com",
    "maritalStatus": "Độc thân",
    "dependents": 0,
    
    # ID Card Information
    "idCardInfo": {
        "idNumber": "036789456123",
        "fullName": "TRẦN THỊ LAN",
        "dateOfBirth": "1985-08-20T00:00:00.000Z",  # 39 tuổi
        "gender": "Nữ",
        "nationality": "Việt Nam",
        "placeOfOrigin": "Hải Phòng, Việt Nam",
        "permanentAddress": "Số 456, Đường Lê Lợi, Phường Máy Chai, Quận Ngô Quyền, Hải Phòng",
        "dateOfIssue": "2021-08-20T00:00:00.000Z",
        "placeOfIssue": "Cục Cảnh sát ĐKQL cư trú và DLQG về dân cư",
        "expirationDate": None,
        "ethnicity": "Kinh",
        "religion": "Phật giáo",
        "ocrConfidence": 0.88
    },
    
    # Collateral Information - Moderate value
    "collateralType": "Bất động sản",
    "collateralInfo": """Nhà phố 3 tầng
- Địa chỉ: Số 78, Phố Trần Phú, Phường Lê Lợi, Quận Ngô Quyền, Hải Phòng
- Diện tích: 80m² x 3 tầng = 240m² sàn
- Tình trạng: Nhà cũ xây năm 2010, cần sửa chữa
- Tình trạng pháp lý: Sổ hồng riêng
- Vị trí: Gần chợ, trường học, nhưng hẻm hơi nhỏ""",
    "collateralValue": 3500000000,  # 3.5 tỷ VNĐ - LTV = 57%
    
    # Financial Information - Moderate income
    "monthlyIncome": 65000000,  # 65 triệu/tháng
    "primaryIncomeSource": "Kinh doanh",
    "companyName": "Cửa hàng thời trang Lan Anh",
    "jobTitle": "Chủ cửa hàng",
    "workExperience": 8,
    "otherIncome": "Cho thuê phòng trọ",
    "otherIncomeAmount": 15000000,  # 15 triệu/tháng
    "bankAccount": "9876543210987",
    "bankName": "Ngân hàng TMCP Ngoại thương Việt Nam (Vietcombank)",
    "totalAssets": 5000000000,  # 5 tỷ VNĐ
    "liquidAssets": 800000000,  # 800 triệu VNĐ
    
    # Debt Information - Moderate debt
    "hasExistingDebt": True,
    "totalDebtAmount": 800000000,  # 800 triệu VNĐ
    "monthlyDebtPayment": 15000000,  # 15 triệu/tháng
    "cicCreditScoreGroup": "2",  # Good credit
    "creditHistory": "Lịch sử tín dụng tốt, có 1 lần chậm trả 30 ngày năm 2022 nhưng đã thanh toán đầy đủ.",
    "existingLoans": [
        {
            "lender": "Ngân hàng TMCP Á Châu (ACB)",
            "amount": 500000000,
            "monthlyPayment": 10000000,
            "remainingTerm": "2 năm"
        },
        {
            "lender": "Công ty Tài chính TNHH MTV Home Credit",
            "amount": 300000000,
            "monthlyPayment": 5000000,
            "remainingTerm": "18 tháng"
        }
    ],
    
    # Administrative
    "ipAddress": "115.78.45.210",
    "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
    "termsAccepted": True,
    "termsAcceptedAt": "2025-06-01T09:05:00.000Z",
    "privacyPolicyAccepted": True,
    "dataProcessingConsent": True
}

# ✅ TEST CASE 3: REJECTED (Low income, high debt, poor credit history)
test_case_rejected = {
    "applicationId": "LOAN-TEST-REJECTED-003",
    "userId": "test_user_rejected",
    "deviceId": "device_test_003",
    "currentStep": 6,
    "status": "submitted",
    "createdAt": "2025-06-01T09:00:00.000Z",
    "submittedAt": "2025-06-12T14:30:00.000Z",
    
    # Loan Information - High amount vs income
    "loanAmount": 3000000000,  # 3 tỷ VNĐ
    "loanType": "Thế chấp",
    "loanTerm": "25 năm",
    "loanPurpose": "Mua nhà ở và đầu tư",
    
    # Personal Information
    "phoneNumber": "0901234567",
    "email": "rejected@test.com",
    "maritalStatus": "Đã kết hôn",
    "dependents": 3,  # Many dependents
    
    # ID Card Information
    "idCardInfo": {
        "idNumber": "079123789456",
        "fullName": "LÊ VĂN BÌNH",
        "dateOfBirth": "1975-12-10T00:00:00.000Z",  # 49 tuổi - getting older
        "gender": "Nam",
        "nationality": "Việt Nam",
        "placeOfOrigin": "Cần Thơ, Việt Nam",
        "permanentAddress": "Số 789, Ấp Tân Lợi, Xã Tân Thạnh, Huyện Châu Thành, Cần Thơ",
        "dateOfIssue": "2019-12-10T00:00:00.000Z",
        "placeOfIssue": "Cục Cảnh sát ĐKQL cư trú và DLQG về dân cư",
        "expirationDate": None,
        "ethnicity": "Kinh",
        "religion": "Không",
        "ocrConfidence": 0.82
    },
    
    # Collateral Information - Low value, risky location
    "collateralType": "Bất động sản",
    "collateralInfo": """Nhà cấp 4 nông thôn
- Địa chỉ: Ấp Tân Lợi, Xã Tân Thạnh, Huyện Châu Thành, Cần Thơ
- Diện tích: 150m² đất, nhà cấp 4 cũ
- Tình trạng: Nhà xây năm 2005, xuống cấp
- Tình trạng pháp lý: Sổ hồng riêng
- Vị trí: Vùng nông thôn xa trung tâm, thanh khoản thấp
- Rủi ro: Khu vực thường xuyên ngập lụt mùa mưa""",
    "collateralValue": 2500000000,  # 2.5 tỷ VNĐ - LTV = 120% (quá cao!)
    
    # Financial Information - Low income, unstable
    "monthlyIncome": 25000000,  # 25 triệu/tháng (thấp)
    "primaryIncomeSource": "Nông nghiệp",
    "companyName": "Hộ kinh doanh cá thể",
    "jobTitle": "Nông dân",
    "workExperience": 20,
    "otherIncome": "Bán hàng online",
    "otherIncomeAmount": 8000000,  # 8 triệu/tháng (không ổn định)
    "bankAccount": "5432109876543",
    "bankName": "Ngân hàng Nông nghiệp và Phát triển Nông thôn (Agribank)",
    "totalAssets": 3000000000,  # 3 tỷ VNĐ (chủ yếu là đất)
    "liquidAssets": 150000000,  # 150 triệu VNĐ (rất thấp)
    
    # Debt Information - High debt, poor credit
    "hasExistingDebt": True,
    "totalDebtAmount": 1200000000,  # 1.2 tỷ VNĐ (cao)
    "monthlyDebtPayment": 18000000,  # 18 triệu/tháng
    "cicCreditScoreGroup": "3",  # Poor credit
    "creditHistory": "Lịch sử tín dụng hơi kém, có 3 lần chậm trả quá 60 ngày trong 2 năm qua. Hiện tại đang nợ xấu nhóm 3.",
    "existingLoans": [
        {
            "lender": "Ngân hàng Nông nghiệp và Phát triển Nông thôn (Agribank)",
            "amount": 800000000,
            "monthlyPayment": 12000000,
            "remainingTerm": "5 năm"
        },
        {
            "lender": "Quỹ Tín dụng Nhân dân Châu Thành",
            "amount": 400000000,
            "monthlyPayment": 6000000,
            "remainingTerm": "3 năm"
        }
    ],
    
    # Administrative
    "ipAddress": "113.160.12.45",
    "userAgent": "Mozilla/5.0 (Linux; Android 9; SM-A102U)",
    "termsAccepted": True,
    "termsAcceptedAt": "2025-06-01T09:05:00.000Z",
    "privacyPolicyAccepted": True,
    "dataProcessingConsent": True
}

def run_all_tests():
    """Run all test cases"""
    print("🚀 STARTING LOAN ASSESSMENT API TESTS")
    print(f"🔗 Testing endpoint: {AI_SERVICE_BASE_URL}{ENDPOINT}")
    print(f"📅 Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test case 1: Should be APPROVED
    test_loan_assessment(test_case_approved, "EXPECTED: APPROVED (High income, low debt, excellent collateral)")
    
    # Test case 2: Should NEED REVIEW
    test_loan_assessment(test_case_needs_review, "EXPECTED: NEEDS REVIEW (Moderate profile, some concerns)")
    
    # Test case 3: Should be REJECTED
    test_loan_assessment(test_case_rejected, "EXPECTED: REJECTED (Low income, high debt, poor credit)")
    
    print(f"\n{'='*60}")
    print("🏁 ALL TESTS COMPLETED")
    print(f"{'='*60}")

def test_single_case(case_type="approved"):
    """Test a single case type"""
    cases = {
        "approved": (test_case_approved, "APPROVED CASE"),
        "review": (test_case_needs_review, "NEEDS REVIEW CASE"),
        "rejected": (test_case_rejected, "REJECTED CASE")
    }
    
    if case_type in cases:
        test_data, case_name = cases[case_type]
        test_loan_assessment(test_data, case_name)
    else:
        print(f"❌ Unknown case type: {case_type}")
        print(f"Available types: {list(cases.keys())}")

if __name__ == "__main__":
    import sys
    
    print("💰 LOAN ASSESSMENT API TESTER")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        case_type = sys.argv[1].lower()
        print(f"🧪 Testing single case: {case_type}")
        test_single_case(case_type)
    else:
        print("🧪 Running all test cases...")
        run_all_tests()
    
    print("\n📋 USAGE:")
    print("  python test_loan_assessment.py           # Run all tests")
    print("  python test_loan_assessment.py approved  # Test approved case")
    print("  python test_loan_assessment.py review    # Test review case") 
    print("  python test_loan_assessment.py rejected  # Test rejected case")