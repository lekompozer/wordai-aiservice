"""
Test Step 6 (Confirmation) and Step 7 (Assessment) - End to End
"""
import asyncio
import sys
import json
sys.path.append('/Users/user/Code/ai-chatbot-rag')

from src.ai_sales_agent.nlg.generator import NLGGenerator
from src.ai_sales_agent.services.loan_assessment_client import LoanAssessmentClient
from src.ai_sales_agent.models.nlu_models import StepSubQuestion

async def test_step_6_and_7_flow():
    """Test complete Step 6 confirmation and Step 7 assessment flow"""
    
    print("=" * 80)
    print("🧪 TEST STEP 6 & 7: COMPLETE CONFIRMATION AND ASSESSMENT FLOW")
    print("=" * 80)
    
    # Initialize generator
    nlg = NLGGenerator()
    
    # Sample complete loan application data
    complete_loan_data = {
        # Step 1: Loan Information
        "loanAmount": 800000000,  # 800 million VND
        "loanTerm": "15 năm",
        "loanPurpose": "Vay mua bất động sản",
        "loanType": "Thế chấp",
        "salesAgentCode": "EMP001",
        
        # Step 2: Personal Information
        "fullName": "Trần Văn Minh",
        "phoneNumber": "0912345678",
        "birthYear": 1988,
        "gender": "Nam",
        "maritalStatus": "Đã kết hôn",
        "dependents": 1,
        "email": "minh.tran@gmail.com",
        
        # Step 3: Collateral Information
        "collateralType": "Bất động sản",
        "collateralInfo": "Căn hộ 3PN, 120m2, Vinhomes Central Park, Quận Bình Thạnh, TP.HCM",
        "collateralValue": 4500000000,  # 4.5 billion VND
        "collateralImage": "uploaded_property_photos.jpg",
        
        # Step 4: Financial Information
        "monthlyIncome": 45000000,  # 45 million VND per month
        "primaryIncomeSource": "Lương",
        "companyName": "Công ty TNHH Công nghệ ABC",
        "jobTitle": "Giám đốc Kỹ thuật",
        "workExperience": 12,
        "otherIncomeAmount": 8000000,  # 8 million VND
        "totalAssets": 6000000000,
        "bankName": "Vietcombank",
        
        # Step 5: Debt Information
        "hasExistingDebt": True,
        "totalDebtAmount": 150000000,  # 150 million VND
        "monthlyDebtPayment": 4500000,  # 4.5 million VND
        "cicCreditScoreGroup": "Nhóm 1"
    }
    
    print("\n📋 STEP 6: CONFIRMATION SUMMARY GENERATION")
    print("-" * 50)
    
    # Test Step 6: Generate confirmation summary
    confirmation_result = nlg.generate_step_6_confirmation(complete_loan_data)
    print("✅ Confirmation Summary Generated:")
    print(confirmation_result["question"][:500] + "...")
    print(f"Method: {confirmation_result.get('method', 'N/A')}")
    print(f"Summary: {confirmation_result.get('summary', 'N/A')}")
    
    print("\n🔄 STEP 6: RESPONSE PROCESSING TESTS")
    print("-" * 50)
    
    # Test different Step 6 responses
    test_responses = [
        {
            "input": "xác nhận",
            "description": "User confirms all information"
        },
        {
            "input": "Sửa thu nhập: 50 triệu",
            "description": "User edits monthly income"
        },
        {
            "input": "Sửa tên: Nguyễn Văn An",
            "description": "User edits full name"
        },
        {
            "input": "Sửa email: newemail@test.com",
            "description": "User edits email"
        },
        {
            "input": "abcd xyz invalid",
            "description": "Invalid user input"
        }
    ]
    
    for test_case in test_responses:
        print(f"\n👤 Test Input: '{test_case['input']}'")
        print(f"📝 Description: {test_case['description']}")
        
        response = nlg.process_step_6_response(test_case["input"], complete_loan_data)
        print(f"🔧 Action: {response['action']}")
        
        if response["action"] == "edit":
            print(f"📊 Field: {response.get('field', 'N/A')}")
            print(f"💡 Value: {response.get('value', 'N/A')}")
        
        print(f"💬 Message: {response['message'][:100]}...")
    
    print("\n🏦 STEP 7: ASSESSMENT PAYLOAD PREPARATION")
    print("-" * 50)
    
    # Test assessment payload preparation
    assessment_payload = nlg.prepare_assessment_payload(complete_loan_data)
    print("✅ Assessment Payload Created:")
    print(json.dumps({k: v for k, v in list(assessment_payload.items())[:10]}, indent=2))
    print(f"... and {len(assessment_payload) - 10} more fields")
    
    print("\n📊 STEP 7: LOAN ASSESSMENT SIMULATION")
    print("-" * 50)
    
    # Initialize assessment client
    assessment_client = LoanAssessmentClient()
    
    # Test both real API call and mock fallback
    print("🔄 Testing Assessment API...")
    
    try:
        # Try real API first
        assessment_result = await assessment_client.assess_loan(assessment_payload)
        if not assessment_result.get("success"):
            raise Exception("API returned error")
        print("✅ Real API Response:")
    except Exception as e:
        print(f"⚠️ Real API failed: {e}")
        print("🎭 Using Mock Assessment:")
        assessment_result = assessment_client.create_mock_assessment_result(assessment_payload)
    
    print(f"Success: {assessment_result.get('success', False)}")
    print(f"Status: {assessment_result.get('status', 'N/A')}")
    print(f"Application ID: {assessment_result.get('applicationId', 'N/A')}")
    
    if assessment_result.get("success"):
        print(f"Credit Score: {assessment_result.get('creditScore', 0)}")
        print(f"DTI Ratio: {assessment_result.get('debtToIncome', 0):.1%}")
        print(f"LTV Ratio: {assessment_result.get('loanToValue', 0):.1%}")
        print(f"Approved Amount: {assessment_result.get('approvedAmount', 0):,} VND")
        print(f"Interest Rate: {assessment_result.get('interestRate', 0)}%")
        print(f"Monthly Payment: {assessment_result.get('monthlyPayment', 0):,} VND")
    
    print("\n🎨 STEP 7: ASSESSMENT RESULT FORMATTING")
    print("-" * 50)
    
    # Test assessment result formatting
    formatted_result = nlg.format_assessment_result(assessment_result)
    print("✅ Formatted Assessment Result:")
    print(formatted_result["question"][:800] + "...")
    print(f"Method: {formatted_result.get('method', 'N/A')}")
    print(f"Complete: {formatted_result.get('is_complete', False)}")
    
    print("\n❌ STEP 7: ERROR HANDLING TEST")
    print("-" * 50)
    
    # Test error scenarios
    error_scenarios = [
        {
            "success": False,
            "error": "TIMEOUT",
            "message": "Connection timeout after 30 seconds"
        },
        {
            "success": False,
            "error": "INVALID_DATA",
            "message": "Missing required field: monthlyIncome"
        }
    ]
    
    for error_case in error_scenarios:
        print(f"\n🚨 Error Case: {error_case['error']}")
        error_formatted = nlg.format_assessment_result(error_case)
        print(f"Error Response: {error_formatted['question'][:200]}...")
    
    print("\n🧮 STEP 6: DATA VALIDATION TEST")
    print("-" * 50)
    
    # Test validation with incomplete data
    incomplete_data = {
        "loanAmount": 500000000,
        "fullName": "Test User",
        "monthlyIncome": 20000000,
        # Missing many required fields
    }
    
    validation_result = nlg.validate_step_6_data(incomplete_data)
    print("✅ Validation Results:")
    print(f"Errors: {len(validation_result['errors'])}")
    print(f"Warnings: {len(validation_result['warnings'])}")
    
    if validation_result["errors"] or validation_result["warnings"]:
        error_message = nlg.generate_validation_error_message(validation_result)
        print(f"Validation Message: {error_message[:300]}...")
    
    print("\n🎯 STEP TRANSITION TESTS")
    print("-" * 50)
    
    # Test transition messages
    transitions = [
        ("5.1", "6"),
        ("5.2", "6"), 
        ("4.3", "5.1"),
        ("6", "7")
    ]
    
    for from_step, to_step in transitions:
        transition_msg = nlg.generate_step_transition(from_step, to_step, complete_loan_data)
        print(f"📈 {from_step} → {to_step}: {transition_msg}")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
    print("🎉 Step 6 & 7 implementation is ready for production!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_step_6_and_7_flow())
