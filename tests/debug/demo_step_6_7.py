"""
Demo Step 6 & 7 - Banking Loan Assessment Flow
Complete demonstration of confirmation and assessment process
"""
import asyncio
import sys
sys.path.append('/Users/user/Code/ai-chatbot-rag')

from src.ai_sales_agent.nlg.generator import NLGGenerator
from src.ai_sales_agent.services.loan_assessment_client import LoanAssessmentClient

async def demo_complete_flow():
    """Demo complete loan assessment flow from Step 6 to Step 7"""
    
    print("🏦" * 20)
    print("   DEMO: BANKING LOAN ASSESSMENT - STEP 6 & 7")
    print("🏦" * 20)
    
    # Initialize generator
    nlg = NLGGenerator()
    
    # Sample loan application data (already collected from Steps 1-5)
    loan_application = {
        "loanAmount": 1200000000,  # 1.2 billion VND
        "loanTerm": "20 năm",
        "loanPurpose": "Vay mua bất động sản",
        "loanType": "Thế chấp",
        "fullName": "Lê Thị Hương",
        "phoneNumber": "0987654321",
        "birthYear": 1985,
        "gender": "Nữ",
        "maritalStatus": "Đã kết hôn", 
        "dependents": 2,
        "email": "huong.le@email.com",
        "collateralType": "Bất động sản",
        "collateralInfo": "Nhà phố 4 tầng, 200m2, Quận 1, TP.HCM",
        "collateralValue": 8000000000,  # 8 billion VND
        "monthlyIncome": 60000000,  # 60 million VND
        "primaryIncomeSource": "Kinh doanh",
        "companyName": "Công ty TNHH Thương Mại XYZ",
        "jobTitle": "Giám đốc",
        "workExperience": 15,
        "otherIncomeAmount": 10000000,
        "hasExistingDebt": True,
        "totalDebtAmount": 200000000,
        "monthlyDebtPayment": 6000000
    }
    
    print("\n📋 STEP 6: HIỂN THỊ THÔNG TIN XÁC NHẬN")
    print("=" * 60)
    
    # Generate Step 6 confirmation
    confirmation = nlg.generate_step_6_confirmation(loan_application)
    print(confirmation["question"])
    
    print("\n" + "=" * 60)
    print("👤 KHÁCH HÀNG: 'xác nhận'")
    print("=" * 60)
    
    # Process confirmation
    confirmation_response = nlg.process_step_6_response("xác nhận", loan_application)
    print(f"✅ {confirmation_response['message']}")
    
    if confirmation_response["action"] == "confirm":
        print("\n🔄 Chuyển sang STEP 7: THẨM ĐỊNH HỒ SƠ...")
        print("=" * 60)
        
        # Prepare assessment data
        assessment_client = LoanAssessmentClient()
        assessment_payload = nlg.prepare_assessment_payload(loan_application)
        
        print("📊 Đang thực hiện thẩm định...")
        
        # Use mock assessment (since real API isn't running)
        assessment_result = assessment_client.create_mock_assessment_result(assessment_payload)
        
        # Format and display result
        formatted_result = nlg.format_assessment_result(assessment_result)
        
        print("\n🎉 KẾT QUẢ THẨM ĐỊNH:")
        print("=" * 60)
        print(formatted_result["question"])
        
        print("\n" + "=" * 60)
        print("✅ HOÀN THÀNH TOÀN BỘ QUY TRÌNH THẨM ĐỊNH!")
        print("📞 Nhân viên sẽ liên hệ khách hàng trong 24h")
        print("=" * 60)
    
    # Demo edit scenario
    print("\n\n🔄 DEMO: KHÁCH HÀNG MUỐN SỬA THÔNG TIN")
    print("=" * 60)
    print("👤 KHÁCH HÀNG: 'Sửa thu nhập: 70 triệu'")
    
    edit_response = nlg.process_step_6_response("Sửa thu nhập: 70 triệu", loan_application)
    print(f"🔧 Hành động: {edit_response['action']}")
    print(f"📝 Trường được sửa: {edit_response.get('field', 'N/A')}")
    print(f"💰 Giá trị mới: {edit_response.get('value', 'N/A'):,} VND")
    print(f"✅ {edit_response['message']}")
    
    print("\n🎯 DEMO HOÀN THÀNH!")
    print("🏦" * 20)

if __name__ == "__main__":
    asyncio.run(demo_complete_flow())
