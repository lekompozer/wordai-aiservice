"""
FastAPI route handlers for loan assessment endpoints
Copied EXACTLY from serve.py logic
"""

from fastapi import APIRouter, Request
from datetime import datetime
import json
import time
import traceback
import uuid
import os
import re
from typing import Dict, Any

# Import models from the same source as serve.py
from src.models import (
    LoanApplicationRequest,
    LoanAssessmentResponse,
    validate_loan_application_minimal,
    build_assessment_context
)
from config.config import DEEPSEEK_API_KEY, CHATGPT_API_KEY
from src.providers.ai_provider_manager import AIProviderManager
from src.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger()

def calculate_interest_rate(
    loan_type: str = None, 
    config: dict = None
) -> float:
    """
    Calculate interest rate based on loan type and configuration
    """
    # Default config values
    default_unsecured_rate = 18.0  # % per year
    default_mortgage_rate_first = 5.0  # % per year for first year
    default_mortgage_rate_after = 8.5  # % per year after first year
    
    # Use provided config or defaults
    if config:
        unsecured_rate = config.get('unsecuredInterestRate', default_unsecured_rate)
        mortgage_rate_first = config.get('mortgageRateFirstYear', default_mortgage_rate_first)
        mortgage_rate_after = config.get('mortgageRateAfterYear', default_mortgage_rate_after)
    else:
        unsecured_rate = default_unsecured_rate
        mortgage_rate_first = default_mortgage_rate_first
        mortgage_rate_after = default_mortgage_rate_after
    
    # Determine loan type
    if loan_type:
        loan_type_lower = loan_type.lower()
        if any(word in loan_type_lower for word in ['thế chấp', 'the chap', 'secured', 'mortgage']):
            # For secured loans, use the first year rate as base
            return mortgage_rate_first
        elif any(word in loan_type_lower for word in ['tín chấp', 'tin chap', 'unsecured']):
            return unsecured_rate
    
    # Default to unsecured rate if unable to determine
    return unsecured_rate


# Create results directory
RESULTS_DIR = "results"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)
    logger.info(f"✅ Created results directory: {RESULTS_DIR}")

@router.post("/api/loan/assessment", response_model=LoanAssessmentResponse)
async def loan_credit_assessment(request: LoanApplicationRequest):
    """
    ✅ LOAN CREDIT ASSESSMENT - Thẩm định hồ sơ vay với DeepSeek Reasoning
    """

    processing_start = time.time()
    assessment_id = f"assessment_{int(time.time() * 1000)}"

    try:
        logger.info(f"🏦 [LOAN ASSESSMENT] {assessment_id}: Starting credit assessment")
        logger.info(f"📋 [LOAN ASSESSMENT] {assessment_id}: Application ID: {request.applicationId}")
        logger.info(f"💰 [LOAN ASSESSMENT] {assessment_id}: Loan amount: {request.loanAmount:,} VNĐ")

        # ✅ SAFE APPLICANT NAME ACCESS
        applicant_name = "N/A"
        if hasattr(request, 'fullName') and request.fullName:
            applicant_name = request.fullName
        elif request.idCardInfo and hasattr(request.idCardInfo, 'fullName') and request.idCardInfo.fullName:
            applicant_name = request.idCardInfo.fullName

        logger.info(f"👤 [LOAN ASSESSMENT] {assessment_id}: Applicant: {applicant_name}")

        # ✅ STEP 1: Basic validation using utility function
        is_valid, validation_errors = validate_loan_application_minimal(request.dict())

        if not is_valid:
            return LoanAssessmentResponse(
                success=False,
                applicationId=request.applicationId or "unknown",
                error=f"Validation failed: {', '.join(validation_errors)}"
            )

        # ✅ STEP 2: Check DeepSeek availability
        if not DEEPSEEK_API_KEY:
            return LoanAssessmentResponse(
                success=False,
                applicationId=request.applicationId,
                error="DeepSeek API not configured",
                processingDetails={
                    "processingTime": time.time() - processing_start
                }
            )

        # ✅ STEP 2.5: Handle AI Sales Agent conversation context
        is_from_chat = getattr(request, 'isFromChat', False)
        conversation_history = getattr(request, 'conversationHistory', [])
        message_count = getattr(request, 'messageCount', 0)
        sales_agent_code = getattr(request, 'salesAgentCode', None)
        
        # Banking services info for enhanced assessment
        has_credit_card = getattr(request, 'hasCreditCard', False)
        has_savings_account = getattr(request, 'hasSavingsAccount', False)
        credit_card_limit = getattr(request, 'creditCardLimit', 0)
        savings_amount = getattr(request, 'savingsAmount', 0)
        
        conversation_text = ""
        if is_from_chat and conversation_history:
            logger.info(f"💬 [LOAN ASSESSMENT] {assessment_id}: Processing chat-based application")
            logger.info(f"   📝 Conversation exchanges: {len(conversation_history)}")
            logger.info(f"   👨‍💼 Sales agent: {sales_agent_code or 'AI_AUTO'}")
            logger.info(f"   💳 Has credit card: {has_credit_card}, Limit: {credit_card_limit:,}")
            logger.info(f"   💰 Has savings: {has_savings_account}, Amount: {savings_amount:,}")
            
            # Build conversation context for AI assessment
            conversation_text = "\n\n**💬 LỊCH SỬ HỘI THOẠI VỚI KHÁCH HÀNG:**\n"
            conversation_text += f"**Tổng số lượt trao đổi:** {message_count}\n"
            conversation_text += f"**Nhân viên tư vấn:** {sales_agent_code or 'AI Sales Agent'}\n\n"
            
            # Show last 5 exchanges for context
            recent_exchanges = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            for i, exchange in enumerate(recent_exchanges, 1):
                user_msg = exchange.get('user', '')
                ai_msg = exchange.get('agent', '') or exchange.get('ai', '')
                timestamp = exchange.get('timestamp', '')
                
                conversation_text += f"🔹 **Lượt {i}** {f'({timestamp})' if timestamp else ''}:\n"
                conversation_text += f"   **Khách hàng:** {user_msg}\n"
                conversation_text += f"   **Tư vấn viên:** {ai_msg}\n\n"
            
            # Add banking services context if available
            if has_credit_card or has_savings_account:
                conversation_text += "**📊 THÔNG TIN DỊCH VỤ NGÂN HÀNG HIỆN TẠI:**\n"
                if has_credit_card:
                    conversation_text += f"   ✅ Có thẻ tín dụng với hạn mức: {credit_card_limit:,} VNĐ\n"
                if has_savings_account:
                    conversation_text += f"   ✅ Có tài khoản tiết kiệm với số dư: {savings_amount:,} VNĐ\n"
                conversation_text += "\n"

        # ✅ STEP 3: Calculate comprehensive financial metrics for loan assessment
        try:
            logger.info(f"📊 [LOAN ASSESSMENT] {assessment_id}: Starting financial metrics calculation")

            # =================================================================
            # 📥 INPUT DATA COLLECTION - Thu thập dữ liệu đầu vào an toàn
            # =================================================================

            # Thu nhập hàng tháng (VNĐ)
            monthly_income = getattr(request, 'monthlyIncome', 0) or 0
            logger.info(f"   💰 Monthly income: {monthly_income:,} VNĐ")

            # Thu nhập khác (cho thuê, kinh doanh phụ, etc.)
            other_income_amount = getattr(request, 'otherIncomeAmount', 0) or 0
            logger.info(f"   💼 Other income: {other_income_amount:,} VNĐ")

            # Khoản nợ hiện tại phải trả hàng tháng
            monthly_debt_payment = getattr(request, 'monthlyDebtPayment', 0) or 0
            logger.info(f"   💳 Current monthly debt: {monthly_debt_payment:,} VNĐ")

            # Giá trị tài sản đảm bảo (thường là BĐS)
            collateral_value = getattr(request, 'collateralValue', 0) or 0
            logger.info(f"   🏠 Collateral value: {collateral_value:,} VNĐ")

            # Số tiền muốn vay
            loan_amount = getattr(request, 'loanAmount', 0) or 0
            logger.info(f"   💵 Loan amount: {loan_amount:,} VNĐ")

            # Lãi suất từ backend hoặc tính từ loan type
            loan_type = getattr(request, 'loanType', None)
            config_interest_rate = None
            
            # Try to get config from conversation history
            if hasattr(request, 'conversationHistory') and request.conversationHistory:
                for message in request.conversationHistory:
                    if isinstance(message, dict) and 'metadata' in message:
                        metadata = message.get('metadata', {})
                        if 'config' in metadata:
                            config_interest_rate = metadata['config']
                            break
            
            # Calculate interest rate
            if hasattr(request, 'interestRate') and request.interestRate:
                backend_interest_rate = request.interestRate
            else:
                backend_interest_rate = calculate_interest_rate(loan_type, config_interest_rate)
            logger.info(f"   📈 Interest rate: {backend_interest_rate}% per year")

            # Thời hạn vay
            loan_term = getattr(request, 'loanTerm', '15 năm') or '15 năm'
            logger.info(f"   ⏰ Loan term: {loan_term}")

            # =================================================================
            # 🧮 PRIMARY CALCULATIONS - Tính toán các chỉ số chính
            # =================================================================

            # 1️⃣ TỔNG THU NHẬP HÀNG THÁNG
            # Mục đích: Xác định khả năng tài chính tổng thể của khách hàng
            total_monthly_income = monthly_income + other_income_amount
            logger.info(f"   ✅ Total monthly income: {total_monthly_income:,} VNĐ")

            # 2️⃣ DTI HIỆN TẠI (Current Debt-to-Income Ratio)
            # Mục đích: Đánh giá tình trạng nợ hiện tại so với thu nhập
            # Tiêu chuẩn ngân hàng: ≤ 40% (tốt), 40-50% (cảnh báo), >50% (từ chối)
            current_debt_ratio = monthly_debt_payment / total_monthly_income if total_monthly_income > 0 else 0
            logger.info(f"   📊 Current DTI ratio: {current_debt_ratio:.2%} (Standard: ≤40% good, >50% risky)")

            # =================================================================
            # 💳 LOAN PAYMENT CALCULATION - Tính toán khoản trả góp
            # =================================================================

            # Chuyển đổi lãi suất năm sang thập phân
            estimated_rate = backend_interest_rate / 100
            logger.info(f"   🔢 Annual rate (decimal): {estimated_rate}")

            # Trích xuất số năm từ thời hạn vay
            years = 15  # Default
            try:
                if "năm" in loan_term:
                    years = int(loan_term.split()[0])
                    logger.info(f"   ⏳ Extracted loan years: {years}")
            except Exception as term_error:
                logger.warning(f"   ⚠️ Cannot parse loan term '{loan_term}', using default 15 years")
                years = 15

            # Tính toán các thông số cho công thức trả góp
            monthly_rate = estimated_rate / 12  # Lãi suất tháng
            n_payments = years * 12  # Tổng số kỳ trả

            logger.info(f"   📅 Monthly rate: {monthly_rate:.6f} ({monthly_rate*100:.4f}%)")
            logger.info(f"   🔢 Total payments: {n_payments} months")

            # 3️⃣ MONTHLY PAYMENT CALCULATION (Công thức trả góp đều)
            # Công thức: PMT = P * [r(1+r)^n] / [(1+r)^n - 1]
            # Mục đích: Tính khoản trả hàng tháng cho khoản vay mới
            if loan_amount > 0 and monthly_rate > 0:
                # Áp dụng công thức trả góp đều (Equal Monthly Installment)
                compound_factor = (1 + monthly_rate) ** n_payments
                estimated_monthly_payment = loan_amount * (monthly_rate * compound_factor) / (compound_factor - 1)

                logger.info(f"   💰 Estimated monthly payment: {estimated_monthly_payment:,} VNĐ")
                logger.info(f"   📊 Payment calculation: Loan={loan_amount:,}, Rate={monthly_rate:.6f}, Periods={n_payments}")
            else:
                estimated_monthly_payment = 0
                logger.warning(f"   ⚠️ Cannot calculate payment: loan_amount={loan_amount}, monthly_rate={monthly_rate}")

            # =================================================================
            # 📈 RISK ASSESSMENT RATIOS - Tính toán các tỷ lệ đánh giá rủi ro
            # =================================================================

            # 4️⃣ NEW DTI RATIO (Projected Debt-to-Income after new loan)
            # Mục đích: Đánh giá khả năng trả nợ sau khi có khoản vay mới
            # Tiêu chuẩn ngân hàng VN: ≤50% (SBVN), ≤40% (conservative)
            new_debt_ratio = (monthly_debt_payment + estimated_monthly_payment) / total_monthly_income if total_monthly_income > 0 else 0
            logger.info(f"   🚨 New DTI ratio: {new_debt_ratio:.2%} (Regulatory limit: ≤50%, Bank limit: ≤40%)")

            # 5️⃣ LTV RATIO (Loan-to-Value Ratio)
            # Mục đích: Đánh giá rủi ro tài sản đảm bảo
            # Tiêu chuẩn ngân hàng: ≤70% (tốt), 70-80% (chấp nhận), >80% (từ chối)
            loan_to_value = loan_amount / collateral_value if collateral_value > 0 else 0
            logger.info(f"   🏠 LTV ratio: {loan_to_value:.2%} (Standard: ≤70% good, >80% risky)")

            # =================================================================
            # 💡 FINANCIAL CAPACITY ANALYSIS - Phân tích khả năng tài chính
            # =================================================================

            # 6️⃣ REMAINING INCOME (Thu nhập còn lại sau trả nợ)
            # Mục đích: Đánh giá khả năng chi tiêu sinh hoạt sau khi trả nợ
            remaining_income = total_monthly_income - monthly_debt_payment - estimated_monthly_payment
            logger.info(f"   💵 Remaining income: {remaining_income:,} VNĐ (for living expenses)")

            # 7️⃣ DEBT SERVICE COVERAGE (Khả năng thanh toán nợ)
            # Mục đích: Đo lường mức độ an toàn trong việc trả nợ
            total_debt_service = monthly_debt_payment + estimated_monthly_payment
            debt_coverage = total_monthly_income / total_debt_service if total_debt_service > 0 else float('inf')
            logger.info(f"   🛡️ Debt service coverage: {debt_coverage:.2f}x (>1.25x recommended)")

            # =================================================================
            # 🎯 RISK ASSESSMENT SUMMARY - Tóm tắt đánh giá rủi ro
            # =================================================================

            # Đánh giá mức độ rủi ro dựa trên các chỉ số
            risk_indicators = []

            if new_debt_ratio > 0.5:  # >50%
                risk_indicators.append(f"High DTI: {new_debt_ratio:.1%}")
            elif new_debt_ratio > 0.4:  # 40-50%
                risk_indicators.append(f"Moderate DTI: {new_debt_ratio:.1%}")

            if loan_to_value > 0.8:  # >80%
                risk_indicators.append(f"High LTV: {loan_to_value:.1%}")
            elif loan_to_value > 0.7:  # 70-80%
                risk_indicators.append(f"Moderate LTV: {loan_to_value:.1%}")

            if remaining_income < 15_000_000:  # <15M VNĐ
                risk_indicators.append(f"Low remaining income: {remaining_income/1_000_000:.1f}M")

            if debt_coverage < 1.25:
                risk_indicators.append(f"Low debt coverage: {debt_coverage:.2f}x")

            # =================================================================
            # 📊 COMPREHENSIVE LOGGING - Ghi log chi tiết
            # =================================================================

            logger.info(f"📊 [LOAN ASSESSMENT] {assessment_id}: Financial metrics calculation completed")
            logger.info(f"   💵 Total monthly income: {total_monthly_income:,} VNĐ")
            logger.info(f"   📈 Current DTI ratio: {current_debt_ratio:.2%}")
            logger.info(f"   🚨 Projected DTI ratio: {new_debt_ratio:.2%}")
            logger.info(f"   🏠 Loan-to-Value ratio: {loan_to_value:.2%}")
            logger.info(f"   💰 Estimated monthly payment: {estimated_monthly_payment:,} VNĐ")
            logger.info(f"   💵 Remaining income: {remaining_income:,} VNĐ")
            logger.info(f"   🛡️ Debt service coverage: {debt_coverage:.2f}x")

            if risk_indicators:
                logger.warning(f"   ⚠️ Risk indicators: {', '.join(risk_indicators)}")
            else:
                logger.info(f"   ✅ All financial ratios within acceptable ranges")

            # =================================================================
            # 🎯 ASSESSMENT RECOMMENDATION - Đề xuất sơ bộ
            # =================================================================

            # Đưa ra đề xuất sơ bộ dựa trên các chỉ số tài chính
            if new_debt_ratio <= 0.4 and loan_to_value <= 0.7 and remaining_income >= 15_000_000:
                preliminary_recommendation = "STRONG_APPROVAL"
                logger.info(f"   🟢 Preliminary assessment: STRONG APPROVAL CANDIDATE")
            elif new_debt_ratio <= 0.5 and loan_to_value <= 0.8 and remaining_income >= 10_000_000:
                preliminary_recommendation = "CONDITIONAL_APPROVAL"
                logger.info(f"   🟡 Preliminary assessment: CONDITIONAL APPROVAL CANDIDATE")
            else:
                preliminary_recommendation = "NEEDS_REVIEW"
                logger.info(f"   🔴 Preliminary assessment: NEEDS DETAILED REVIEW")

            # Store all calculated metrics for later use
            financial_metrics = {
                'monthly_income': monthly_income,
                'other_income_amount': other_income_amount,
                'total_monthly_income': total_monthly_income,
                'monthly_debt_payment': monthly_debt_payment,
                'estimated_monthly_payment': estimated_monthly_payment,
                'current_debt_ratio': current_debt_ratio,
                'new_debt_ratio': new_debt_ratio,
                'loan_to_value': loan_to_value,
                'remaining_income': remaining_income,
                'debt_coverage': debt_coverage,
                'risk_indicators': risk_indicators,
                'preliminary_recommendation': preliminary_recommendation,
                'backend_interest_rate': backend_interest_rate,
                'loan_term_years': years
            }

            logger.info(f"✅ [LOAN ASSESSMENT] {assessment_id}: All financial metrics stored successfully")

        except Exception as calc_error:
            logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: Financial calculation error - {calc_error}")
            logger.error(f"🔍 [LOAN ASSESSMENT] {assessment_id}: Calculation traceback - {traceback.format_exc()}")

            # ✅ SAFE FALLBACK VALUES - Giá trị dự phòng an toàn
            estimated_monthly_payment = 0
            new_debt_ratio = 0
            loan_to_value = 0
            backend_interest_rate = calculate_interest_rate(
                getattr(request, 'loanType', None), 
                None  # No config in fallback
            )
            total_monthly_income = getattr(request, 'monthlyIncome', 0) or 0
            current_debt_ratio = 0
            remaining_income = 0
            debt_coverage = 0

            # Store fallback metrics
            financial_metrics = {
                'monthly_income': getattr(request, 'monthlyIncome', 0) or 0,
                'other_income_amount': 0,
                'total_monthly_income': total_monthly_income,
                'monthly_debt_payment': 0,
                'estimated_monthly_payment': 0,
                'current_debt_ratio': 0,
                'new_debt_ratio': 0,
                'loan_to_value': 0,
                'remaining_income': 0,
                'debt_coverage': 0,
                'risk_indicators': ['Calculation Error'],
                'preliminary_recommendation': 'MANUAL_REVIEW_REQUIRED',
                'backend_interest_rate': calculate_interest_rate(
                    getattr(request, 'loanType', None), 
                    None
                ),
                'loan_term_years': 15,
                'calculation_error': str(calc_error)
            }

            logger.warning(f"🔄 [LOAN ASSESSMENT] {assessment_id}: Using fallback financial metrics due to calculation error")

        # ✅ STEP 4: Build comprehensive assessment prompt
        try:
            # ✅ CALCULATE AGE FROM BIRTH YEAR
            current_year = datetime.now().year
            birth_year = getattr(request, 'birthYear', None)
            if birth_year:
                age = current_year - birth_year
            elif request.idCardInfo and request.idCardInfo.dateOfBirth:
                age = current_year - request.idCardInfo.dateOfBirth.year
            else:
                age = "Chưa xác định"

            # ✅ GET PERSONAL INFO (Priority: personalInfo over idCardInfo) - ALL SAFE
            full_name = getattr(request, 'fullName', None) or (request.idCardInfo.fullName if request.idCardInfo else "Chưa cung cấp")
            gender = getattr(request, 'gender', None) or (request.idCardInfo.gender if request.idCardInfo else "Chưa cung cấp")
            marital_status = getattr(request, 'maritalStatus', None) or "Chưa cung cấp"
            dependents = getattr(request, 'dependents', 0) or 0
            email = getattr(request, 'email', None) or "Chưa cung cấp"

            # Phone with country code
            phone_country_code = getattr(request, 'phoneCountryCode', '+84')
            phone_number = getattr(request, 'phoneNumber', None)
            phone_display = f"{phone_country_code} {phone_number}" if phone_number else "Chưa cung cấp"

            # ID Card info (optional)
            id_number = "Chưa cung cấp"
            permanent_address = "Chưa cung cấp"
            if request.idCardInfo:
                id_number = getattr(request.idCardInfo, 'idNumber', None) or "Chưa cung cấp"
                permanent_address = getattr(request.idCardInfo, 'permanentAddress', None) or "Chưa cung cấp"

            # ✅ GET FINANCIAL INFO - ALL SAFE
            monthly_income = getattr(request, 'monthlyIncome', 0) or 0
            primary_income_source = getattr(request, 'primaryIncomeSource', None) or "Chưa cung cấp"
            company_name = getattr(request, 'companyName', None) or "Chưa cung cấp"
            job_title = getattr(request, 'jobTitle', None) or "Chưa cung cấp"
            work_experience = getattr(request, 'workExperience', 0) or 0
            other_income = getattr(request, 'otherIncome', None) or "Không có"
            other_income_amount = getattr(request, 'otherIncomeAmount', 0) or 0

            # Banking info - SAFE
            bank_name = getattr(request, 'bankName', None) or "Chưa cung cấp"
            bank_account = getattr(request, 'bankAccount', None) or "Chưa cung cấp"

            # Assets - SAFE
            total_assets = getattr(request, 'totalAssets', 0) or 0
            liquid_assets = getattr(request, 'liquidAssets', 0) or 0

            # ✅ GET DEBT INFO - ALL SAFE
            has_existing_debt = getattr(request, 'hasExistingDebt', False) or False
            total_debt_amount = getattr(request, 'totalDebtAmount', 0) or 0
            monthly_debt_payment = getattr(request, 'monthlyDebtPayment', 0) or 0
            cic_credit_score_group = getattr(request, 'cicCreditScoreGroup', None) or "Chưa xác định"
            credit_history = getattr(request, 'creditHistory', None) or "Chưa có thông tin"

            # ✅ GET COLLATERAL INFO - ALL SAFE
            collateral_type = getattr(request, 'collateralType', 'Bất động sản')
            collateral_info = getattr(request, 'collateralInfo', 'Chưa có thông tin chi tiết')
            collateral_value = getattr(request, 'collateralValue', 0) or 0
            has_collateral_image = getattr(request, 'hasCollateralImage', False)

            # ✅ GET BACKEND INTEREST RATE - SAFE
            backend_interest_rate = getattr(request, 'interestRate', None) or calculate_interest_rate(
                getattr(request, 'loanType', None), 
                None
            )

            # ✅ SAFE EXISTING LOANS FORMAT
            existing_loans = getattr(request, 'existingLoans', []) or []
            existing_loans_text = ""
            if existing_loans and len(existing_loans) > 0:
                for i, loan in enumerate(existing_loans, 1):
                    lender = getattr(loan, 'lender', None) or "Không rõ"
                    amount = getattr(loan, 'amount', 0) or 0
                    payment = getattr(loan, 'monthlyPayment', 0) or 0
                    term = getattr(loan, 'remainingTerm', None) or "Không rõ"
                    existing_loans_text += f"{i}. {lender}: {amount/1_000_000:.0f} triệu VNĐ (trả {payment/1_000_000:.0f} triệu/tháng, còn {term})\n"
            else:
                existing_loans_text = "Không có khoản nợ nào"

            # ✅ BUILD SAFE PROMPT WITH ALL FALLBACKS
            assessment_prompt = f"""Bạn là CHUYÊN GIA THẨM ĐỊNH TÍN DỤNG cao cấp với 15 năm kinh nghiệm tại các ngân hàng lớn ở Việt Nam (VietinBank, BIDV, Vietcombank). Hãy thẩm định hồ sơ vay vốn này một cách chi tiết và chuyên nghiệp theo tiêu chuẩn ngân hàng Việt Nam.

🎯 **NHIỆM VỤ THẨM ĐỊNH:**

1. **PHÂN TÍCH KHẢ NĂNG TÀI CHÍNH:**
   - Đánh giá tỷ lệ thu nhập/chi phí (DTI - Debt to Income)
   - Phân tích dòng tiền hàng tháng và khả năng trả nợ
   - Đánh giá độ ổn định thu nhập và nguồn thu

2. **THẨM ĐỊNH TÀI SẢN ĐẢM BẢO:**
   - Định giá lại bất động sản dựa trên mô tả chi tiết từ khách hàng
   - Đánh giá tính thanh khoản và rủi ro giá trị
   - Phân tích vị trí địa lý và tiện ích dựa trên thông tin có sẵn

3. **ĐÁNH GIÁ RỦI RO TÍN DỤNG:**
   - Phân tích lịch sử tín dụng và nhóm CIC
   - Đánh giá khả năng trả nợ dựa trên thu nhập
   - Xác định các yếu tố rủi ro tiềm ẩn

4. **KIẾN NGHỊ QUYẾT ĐỊNH:**
   - Phê duyệt/từ chối với lý do cụ thể và chi tiết
   - Đề xuất số tiền cho vay phù hợp (nếu phê duyệt)
   - Đề xuất lãi suất và điều kiện vay
   - Các yêu cầu bổ sung (nếu có)

📋 **THÔNG TIN HỒ SƠ VAY:**

**A. THÔNG TIN KHOẢN VAY:**
- Mã hồ sơ: {getattr(request, 'applicationId', 'N/A')}
- Số tiền vay: {loan_amount/1_000_000_000:.1f} tỷ VNĐ
- Loại vay: {getattr(request, 'loanType', 'Chưa xác định')}  
- Thời hạn: {loan_term}
- Mục đích: {getattr(request, 'loanPurpose', 'Chưa cung cấp')}

**B. THÔNG TIN CÁ NHÂN:**
- Họ tên: {full_name}
- Tuổi: {age}
- Giới tính: {gender}
- Tình trạng hôn nhân: {marital_status}
- Số người phụ thuộc: {dependents} người
- Điện thoại: {phone_display}
- Email: {email}

**Thông tin CCCD (nếu có):**
- Số CCCD: {id_number}
- Địa chỉ thường trú: {permanent_address}

**C. THÔNG TIN TÀI CHÍNH:**
- Thu nhập chính: {monthly_income/1_000_000:.0f} triệu VNĐ/tháng
- Nguồn thu nhập: {primary_income_source}
- Công ty/Doanh nghiệp: {company_name}
- Chức vụ: {job_title}
- Kinh nghiệm làm việc: {work_experience} năm
- Thu nhập khác: {other_income_amount/1_000_000:.0f} triệu VNĐ/tháng ({other_income})

- Tổng tài sản: {total_assets/1_000_000_000:.1f} tỷ VNĐ
- Tài sản thanh khoản: {liquid_assets/1_000_000_000:.1f} tỷ VNĐ
- Ngân hàng chính: {bank_name}
- Số tài khoản: {bank_account}

**D. THÔNG TIN NỢ HIỆN TẠI:**
- Có nợ hiện tại: {'Có' if has_existing_debt else 'Không'}
- Tổng dư nợ: {total_debt_amount/1_000_000:.0f} triệu VNĐ
- Trả nợ hàng tháng: {monthly_debt_payment/1_000_000:.0f} triệu VNĐ
- Tỷ lệ nợ/thu nhập hiện tại: {current_debt_ratio:.1%}
- Nhóm tín dụng CIC: Nhóm {cic_credit_score_group}
- Lịch sử tín dụng: {credit_history}

**Chi tiết các khoản nợ hiện tại:**
{existing_loans_text}

**E. TÀI SẢN ĐẢM BẢO:**
- Loại tài sản: {collateral_type}
- Giá trị khách hàng ước tính: {collateral_value/1_000_000_000:.1f} tỷ VNĐ {"(có hình ảnh đính kèm)" if has_collateral_image else "(chưa có hình ảnh)"}
- Tỷ lệ cho vay/giá trị tài sản dự kiến: {loan_to_value:.1%}

**Mô tả chi tiết tài sản từ khách hàng:**
{collateral_info}

Lịch sử nói chuyện với khách hàng: {conversation_text}

📊 **CHỈ SỐ TÀI CHÍNH QUAN TRỌNG:**
- Dự kiến trả nợ mới hàng tháng: {estimated_monthly_payment/1_000_000:.1f} triệu VNĐ
- Tỷ lệ nợ/thu nhập sau khi vay: {new_debt_ratio:.1%}
- Thu nhập còn lại sau trả nợ: {(total_monthly_income - monthly_debt_payment - estimated_monthly_payment)/1_000_000:.1f} triệu VNĐ


⚠️ **YÊU CẦU QUAN TRỌNG:**
1. Phân tích từng bước một cách logic và chi tiết
2. Đưa ra quyết định dựa trên tiêu chuẩn ngân hàng Việt Nam
3. Giải thích rõ ràng lý do cho mọi quyết định
4. Đề xuất các điều kiện cụ thể và khả thi
5. **Định giá tài sản đảm bảo dựa CHÍNH XÁC trên mô tả từ khách hàng**

{f'''🤖 **LƯU Ý ĐÁNH GIÁ HỒ SƠ TỪ AI CHAT:**
- Hồ sơ này được thu thập qua {message_count} lượt trao đổi với AI Sales Agent
- Đánh giá độ tin cậy thông tin dựa trên consistency trong conversation
- Xem xét ngữ cảnh và ý định thực sự của khách hàng
- Nếu phát hiện mâu thuẫn trong hội thoại, cần lưu ý trong risk factors
- Ưu tiên thông tin mới nhất nếu có sự thay đổi
- Đề xuất next steps phù hợp với channel chat''' if is_from_chat else ''}

🎯 **TRÁCH NGHIỆM THẨM ĐỊNH:**

🌐 **QUAN TRỌNG VỀ NGÔN NGỮ:** 
- Hãy đọc kỹ lịch sử hội thoại với khách hàng để xác định ngôn ngữ chính mà khách hàng sử dụng
- TẤT CẢ nội dung văn bản trong JSON response (reasoning, riskFactors, recommendations, conditions, nextSteps, documentRequirements, marketAnalysis, estimatedProcessingTime, v.v.) PHẢI được viết bằng ngôn ngữ mà khách hàng đã sử dụng trong cuộc hội thoại
- Giữ nguyên cấu trúc JSON để frontend có thể đọc được

Trả lời theo định dạng JSON chính xác (bắt buộc) - Sử dụng ngôn ngữ của khách hàng cho tất cả nội dung text:

{{
  "status": "approved/rejected/needs_review",
  "confidence": 0.85,
  "creditScore": 750,
  "reasoning": "Chi tiết phân tích và lý do quyết định bằng ngôn ngữ của khách hàng với ít nhất 200 từ...",
  "riskFactors": ["Rủi ro cụ thể 1 bằng ngôn ngữ khách hàng", "Rủi ro cụ thể 2 bằng ngôn ngữ khách hàng", "Rủi ro cụ thể 3 bằng ngôn ngữ khách hàng"],
  "recommendations": ["Kiến nghị cụ thể 1 bằng ngôn ngữ khách hàng", "Kiến nghị cụ thể 2 bằng ngôn ngữ khách hàng"],  
  "approvedAmount": {loan_amount if estimated_monthly_payment > 0 else None},
  "interestRate": {backend_interest_rate},
  "loanTerm": {years if 'years' in locals() else 15},
  "monthlyPayment": {int(estimated_monthly_payment) if estimated_monthly_payment > 0 else None},
  "loanToValue": {loan_to_value:.3f},
  "debtToIncome": {new_debt_ratio:.3f},
  "conditions": ["Điều kiện 1 bằng ngôn ngữ khách hàng", "Điều kiện 2 bằng ngôn ngữ khách hàng"],
  "collateralValuation": {{
    "estimatedValue": {collateral_value if collateral_value > 0 else "cần định giá dựa trên tài sản đảm bảo"},
    "marketAnalysis": "Phân tích thị trường dựa trên mô tả tài sản từ khách hàng - bằng ngôn ngữ khách hàng",
    "liquidityRisk": "low/medium/high",
    "valuationMethod": "customer_description_analysis"
  }},
  "financialAnalysis": {{
    "totalMonthlyIncome": {total_monthly_income},
    "totalMonthlyDebt": {monthly_debt_payment},
    "newLoanPayment": {int(estimated_monthly_payment) if estimated_monthly_payment > 0 else 0},
    "remainingIncome": {max(0, total_monthly_income - monthly_debt_payment - estimated_monthly_payment)},
    "emergencyFund": {liquid_assets},
    "incomeStability": "high/medium/low",
    "assetLiquidity": "high/medium/low"
  }},
  "nextSteps": ["Bước tiếp theo 1 bằng ngôn ngữ khách hàng", "Bước tiếp theo 2 bằng ngôn ngữ khách hàng", "Bước tiếp theo 3 bằng ngôn ngữ khách hàng"],
  "documentRequirements": ["Giấy tờ cần bổ sung 1 bằng ngôn ngữ khách hàng", "Giấy tờ cần bổ sung 2 bằng ngôn ngữ khách hàng"],
  "estimatedProcessingTime": "Thời gian xử lý bằng ngôn ngữ khách hàng",
  "contactInfo": {{
    "hotline": "1900-xxxx",
    "email": "support@bank.com",
    "salesAgent": "{sales_agent_code or 'AI Sales Agent'}"
  }}{f''',
  "conversationSummary": "Tóm tắt cuộc hội thoại và đánh giá độ tin cậy thông tin bằng ngôn ngữ khách hàng từ {message_count} lượt trao đổi"''' if is_from_chat else ''}
}}

HÃY THẨM ĐỊNH KỸ LƯỠNG VÀ ĐƯA RA QUYẾT ĐỊNH CHÍNH XÁC THEO TIÊU CHUẨN NGÂN HÀNG VIỆT NAM."""

            logger.info(f"📝 [LOAN ASSESSMENT] {assessment_id}: Safe assessment prompt prepared")
            logger.info(f"   📄 Prompt length: {len(assessment_prompt)} characters")

        except Exception as prompt_error:
            logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: Prompt preparation error - {prompt_error}")
            return LoanAssessmentResponse(
                success=False,
                applicationId=getattr(request, 'applicationId', 'unknown'),
                error=f"Prompt preparation failed: {str(prompt_error)}",
                processingDetails={
                    "processingTime": time.time() - processing_start
                }
            )

        # ✅ STEP 5: Call DeepSeek Reasoning API
        try:
            logger.info(f"🤖 [LOAN ASSESSMENT] {assessment_id}: Calling DeepSeek Reasoning API")

            # Initialize AI Provider Manager 
            ai_provider_manager = AIProviderManager(
                deepseek_api_key=DEEPSEEK_API_KEY,
                chatgpt_api_key=CHATGPT_API_KEY
            )

            # Prepare messages for DeepSeek with language auto-detection
            messages = [
                {
                    "role": "system",
                    "content": """🌐 CRITICAL LANGUAGE RULE: You MUST automatically detect the customer's language from the conversation history and respond in the SAME language.

You are a professional credit assessment expert. Your response must be in accurate JSON format with detailed analysis.

IMPORTANT: 
1. Read the conversation history carefully to detect the customer's primary language
2. ALL text content in your JSON response (reasoning, riskFactors, recommendations, conditions, nextSteps, documentRequirements, etc.) MUST be in the customer's detected language
3. Keep JSON structure intact for frontend compatibility
4. Provide detailed professional analysis in the customer's language"""
                },
                {
                    "role": "user",
                    "content": assessment_prompt
                }
            ]

            # Call DeepSeek with reasoning
            reasoning_start = time.time()

            # Collect all chunks into a single response
            chunks = []
            async for chunk in ai_provider_manager.chat_completion_stream_with_reasoning(
                messages, "deepseek", use_reasoning=True
            ):
                chunks.append(chunk)
            
            raw_response = ''.join(chunks)
            reasoning_duration = time.time() - reasoning_start

            logger.info(f"✅ [LOAN ASSESSMENT] {assessment_id}: DeepSeek response received in {reasoning_duration:.2f}s")
            logger.info(f"📄 [LOAN ASSESSMENT] {assessment_id}: Response length: {len(raw_response)} chars")

        except Exception as api_error:
            logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: DeepSeek API error - {api_error}")
            return LoanAssessmentResponse(
                success=False,
                applicationId=request.applicationId,
                error=f"DeepSeek API failed: {str(api_error)}",
                processingDetails={
                    "processingTime": time.time() - processing_start
                }
            )

        # ✅ STEP 6: Parse assessment response
        try:
            logger.info(f"🔍 [LOAN ASSESSMENT] {assessment_id}: Parsing DeepSeek response")

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                assessment_data = json.loads(json_match.group())
            else:
                # Try to find JSON in the response
                lines = raw_response.split('\n')
                json_lines = []
                in_json = False
                for line in lines:
                    if '{' in line:
                        in_json = True
                    if in_json:
                        json_lines.append(line)
                    if '}' in line and in_json:
                        break

                if json_lines:
                    assessment_data = json.loads(''.join(json_lines))
                else:
                    raise Exception("No valid JSON found in response")

            # Validate required fields
            required_fields = ['status', 'confidence', 'reasoning']
            missing_fields = [field for field in required_fields if field not in assessment_data]

            if missing_fields:
                logger.warning(f"⚠️ [LOAN ASSESSMENT] {assessment_id}: Missing fields: {missing_fields}")

            logger.info(f"✅ [LOAN ASSESSMENT] {assessment_id}: Assessment parsing successful")
            logger.info(f"📊 [LOAN ASSESSMENT] {assessment_id}: Status: {assessment_data.get('status', 'unknown')}")
            logger.info(f"📊 [LOAN ASSESSMENT] {assessment_id}: Confidence: {assessment_data.get('confidence', 0)}")

        except Exception as parse_error:
            logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: Response parsing error - {parse_error}")
            logger.error(f"📄 [LOAN ASSESSMENT] {assessment_id}: Raw response preview: {raw_response[:500]}...")

            return LoanAssessmentResponse(
                success=False,
                applicationId=request.applicationId,
                error=f"Response parsing failed: {str(parse_error)}",
                processingDetails={
                    "processingTime": time.time() - processing_start,
                    "rawResponsePreview": raw_response[:200] + "..." if len(raw_response) > 200 else raw_response
                }
            )

        # ✅ STEP 7: Save assessment log
        try:
            logger.info(f"💾 [LOAN ASSESSMENT] {assessment_id}: Saving assessment log")

            assessment_log = {
                "assessmentId": assessment_id,
                "applicationId": request.applicationId,
                "timestamp": datetime.now().isoformat(),
                "applicant": {
                    "name": applicant_name,
                    "idNumber": id_number if 'id_number' in locals() else "N/A",
                    "age": age if 'age' in locals() else "N/A"
                },
                "loanRequest": {
                    "amount": request.loanAmount,
                    "type": getattr(request, 'loanType', 'N/A'),
                    "term": getattr(request, 'loanTerm', 'N/A'),
                    "purpose": getattr(request, 'loanPurpose', 'N/A')
                },
                "financialMetrics": {
                    "totalMonthlyIncome": total_monthly_income,
                    "currentDebtRatio": current_debt_ratio,
                    "projectedDebtRatio": new_debt_ratio,
                    "loanToValue": loan_to_value,
                    "estimatedMonthlyPayment": estimated_monthly_payment
                },
                "assessmentResult": assessment_data,
                "processingDetails": {
                    "reasoningDuration": reasoning_duration,
                    "totalProcessingTime": time.time() - processing_start,
                    "modelUsed": "deepseek-reasoning"
                },
                "rawResponse": raw_response
            }

            # Save to file
            assessment_filename = f"loan_assessment_{assessment_id}_{request.applicationId}.json"
            assessment_filepath = os.path.join(RESULTS_DIR, assessment_filename)

            with open(assessment_filepath, 'w', encoding='utf-8') as f:
                json.dump(assessment_log, f, ensure_ascii=False, indent=2)

            # Verify file creation
            if os.path.exists(assessment_filepath):
                file_size = os.path.getsize(assessment_filepath)
                logger.info(f"✅ [LOAN ASSESSMENT] {assessment_id}: Assessment log saved successfully")
                logger.info(f"📁 [LOAN ASSESSMENT] {assessment_id}: File: {assessment_filename}")
                logger.info(f"📁 [LOAN ASSESSMENT] {assessment_id}: Size: {file_size} bytes")
            else:
                logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: File was not created!")

        except Exception as log_error:
            logger.error(f"⚠️ [LOAN ASSESSMENT] {assessment_id}: Log saving error - {log_error}")
            logger.error(f"⚠️ [LOAN ASSESSMENT] {assessment_id}: Traceback - {traceback.format_exc()}")

        # ✅ STEP 8: Return successful response
        total_time = time.time() - processing_start

        processing_details = {
            "assessmentId": assessment_id,
            "processingTime": round(total_time, 2),
            "reasoningDuration": round(reasoning_duration, 2),
            "modelUsed": "deepseek-reasoning",
            "promptLength": len(assessment_prompt),
            "responseLength": len(raw_response),
            "financialMetrics": {
                "totalMonthlyIncome": total_monthly_income,
                "estimatedMonthlyPayment": int(estimated_monthly_payment),
                "projectedDebtRatio": round(new_debt_ratio, 3),
                "loanToValue": round(loan_to_value, 3)
            }
        }

        logger.info(f"🎉 [LOAN ASSESSMENT] {assessment_id}: Assessment completed successfully in {total_time:.2f}s")

        return LoanAssessmentResponse(
            success=True,
            applicationId=request.applicationId,
            assessmentId=assessment_id,
            status=assessment_data.get("status"),
            confidence=assessment_data.get("confidence"),
            creditScore=assessment_data.get("creditScore"),
            reasoning=assessment_data.get("reasoning"),
            riskFactors=assessment_data.get("riskFactors", []),
            recommendations=assessment_data.get("recommendations", []),
            approvedAmount=assessment_data.get("approvedAmount"),
            interestRate=assessment_data.get("interestRate"),
            monthlyPayment=assessment_data.get("monthlyPayment"),
            loanToValue=assessment_data.get("loanToValue"),
            debtToIncome=assessment_data.get("debtToIncome"),
            conditions=assessment_data.get("conditions", []),
            collateralValuation=assessment_data.get("collateralValuation"),
            financialAnalysis=assessment_data.get("financialAnalysis"),
            nextSteps=assessment_data.get("nextSteps", []),
            documentRequirements=assessment_data.get("documentRequirements", []),
            estimatedProcessingTime=assessment_data.get("estimatedProcessingTime"),
            contactInfo=assessment_data.get("contactInfo"),
            conversationSummary=assessment_data.get("conversationSummary") if is_from_chat else None,
            processingDetails=processing_details
        )

    except Exception as general_error:
        logger.error(f"❌ [LOAN ASSESSMENT] {assessment_id}: General error - {general_error}")
        logger.error(f"🔍 [LOAN ASSESSMENT] {assessment_id}: Traceback - {traceback.format_exc()}")

        return LoanAssessmentResponse(
            success=False,
            applicationId=request.applicationId if hasattr(request, 'applicationId') else "unknown",
            error=f"Assessment failed: {str(general_error)}",
            processingDetails={
                "processingTime": time.time() - processing_start
            }
        )
