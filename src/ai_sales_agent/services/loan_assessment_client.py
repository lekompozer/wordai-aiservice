"""
Client for calling loan assessment API
"""
import aiohttp
import asyncio
import json
from typing import Dict, Any
from src.core.config import APP_CONFIG
import logging

logger = logging.getLogger(__name__)

class LoanAssessmentClient:
    """Client for loan assessment API"""
    
    def __init__(self):
        self.base_url = APP_CONFIG.get("base_url", "http://localhost:8000")
        self.assessment_endpoint = f"{self.base_url}/api/loan/assessment"
        self.timeout = 30
    
    async def assess_loan(self, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call loan assessment API matching /api/loan/assessment endpoint exactly
        
        Args:
            assessment_data: Complete payload matching LoanApplicationRequest
            
        Returns:
            Assessment result from LoanAssessmentResponse
        """
        try:
            logger.info(f"🏦 Calling assessment API: {self.assessment_endpoint}")
            logger.info(f"📋 Assessment data keys: {list(assessment_data.keys())}")
            logger.info(f"💰 Loan amount: {assessment_data.get('loanAmount', 0):,} VNĐ")
            logger.info(f"👤 Applicant: {assessment_data.get('fullName', 'N/A')}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.assessment_endpoint,
                    json=assessment_data,
                    timeout=aiohttp.ClientTimeout(total=60),  # Increased timeout for AI processing
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                ) as response:
                    
                    response_text = await response.text()
                    logger.info(f"📊 API Response: status={response.status}")
                    
                    if response.status == 200:
                        try:
                            result = json.loads(response_text)
                            
                            # Log key results
                            if result.get("success"):
                                status = result.get("status", "unknown")
                                confidence = result.get("confidence", 0)
                                logger.info(f"✅ Assessment successful: {status} (confidence: {confidence*100:.1f}%)")
                            else:
                                error = result.get("error", "Unknown error")
                                logger.error(f"❌ Assessment failed: {error}")
                            
                            return result
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ Invalid JSON response: {e}")
                            return {
                                "success": False,
                                "error": f"Invalid JSON response: {str(e)}",
                                "raw_response": response_text[:500]
                            }
                    
                    elif response.status == 422:
                        # Validation error
                        try:
                            error_detail = json.loads(response_text)
                            logger.error(f"❌ Validation error: {error_detail}")
                            return {
                                "success": False,
                                "error": f"Validation failed: {error_detail.get('detail', 'Unknown validation error')}",
                                "validation_errors": error_detail
                            }
                        except:
                            return {
                                "success": False,
                                "error": f"Validation failed: {response_text}",
                                "status_code": response.status
                            }
                    
        except asyncio.TimeoutError:
            logger.error("⏰ Assessment API timeout")
            return {
                "success": False,
                "error": "TIMEOUT", 
                "message": "Thẩm định mất quá nhiều thời gian. Vui lòng thử lại."
            }
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            return {
                "success": False,
                "error": "CONNECTION_ERROR",
                "message": f"Lỗi kết nối: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in assessment: {e}")
            return {
                "success": False,
                "error": "SYSTEM_ERROR",
                "message": str(e)
            }
    
    def create_mock_assessment_result(self, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create mock assessment result for testing when API is not available
        """
        loan_amount = assessment_data.get("loanAmount", 0)
        monthly_income = assessment_data.get("monthlyIncome", 0)
        collateral_value = assessment_data.get("collateralValue", 0)
        monthly_debt = assessment_data.get("monthlyDebtPayment", 0)
        
        # Calculate basic ratios
        dti_ratio = (monthly_debt / monthly_income) if monthly_income > 0 else 0
        ltv_ratio = (loan_amount / collateral_value) if collateral_value > 0 else 1
        
        # Simple scoring logic
        credit_score = 700
        if dti_ratio < 0.3:
            credit_score += 50
        elif dti_ratio > 0.5:
            credit_score -= 100
            
        if ltv_ratio < 0.7:
            credit_score += 30
        elif ltv_ratio > 0.9:
            credit_score -= 80
        
        # Determine status
        if credit_score >= 650 and dti_ratio < 0.5 and ltv_ratio < 0.9:
            status = "APPROVED"
            approved_amount = loan_amount
        elif credit_score >= 600:
            status = "CONDITIONAL_APPROVAL"
            approved_amount = int(loan_amount * 0.8)
        else:
            status = "REJECTED"
            approved_amount = 0
        
        return {
            "success": True,
            "applicationId": f"APP_{assessment_data.get('applicationId', 'MOCK_12345')}",
            "status": status,
            "creditScore": credit_score,
            "debtToIncome": dti_ratio,
            "loanToValue": ltv_ratio,
            "confidence": 0.85,
            "approvedAmount": approved_amount,
            "interestRate": 8.5 if status == "APPROVED" else 9.5,
            "loanTerm": assessment_data.get("loanTerm", 120),
            "monthlyPayment": self._calculate_monthly_payment(
                approved_amount, 
                8.5 if status == "APPROVED" else 9.5, 
                assessment_data.get("loanTerm", 120)
            ),
            "conditions": self._generate_conditions(status, dti_ratio, ltv_ratio),
            "reasoning": self._generate_reasoning(status, credit_score, dti_ratio, ltv_ratio)
        }
    
    def _calculate_monthly_payment(self, amount: float, rate: float, term_months: int) -> float:
        """Calculate monthly payment using loan formula"""
        if amount <= 0 or rate <= 0 or term_months <= 0:
            return 0
        
        monthly_rate = rate / 100 / 12
        payment = amount * (monthly_rate * (1 + monthly_rate) ** term_months) / \
                 ((1 + monthly_rate) ** term_months - 1)
        return round(payment, 0)
    
    def _generate_conditions(self, status: str, dti: float, ltv: float) -> list:
        """Generate approval conditions based on assessment"""
        conditions = []
        
        if status == "CONDITIONAL_APPROVAL":
            conditions.append("Cần bổ sung giấy tờ chứng minh thu nhập 6 tháng gần nhất")
            
        if ltv > 0.8:
            conditions.append("Cần định giá lại tài sản thế chấp")
            
        if dti > 0.4:
            conditions.append("Cần giảm thiểu các khoản nợ hiện tại")
            
        return conditions
    
    def _generate_reasoning(self, status: str, score: int, dti: float, ltv: float) -> str:
        """Generate reasoning for assessment decision"""
        reasoning = f"Điểm tín dụng: {score}/850. "
        reasoning += f"Tỷ lệ DTI: {dti:.1%}. "
        reasoning += f"Tỷ lệ LTV: {ltv:.1%}. "
        
        if status == "APPROVED":
            reasoning += "Hồ sơ đáp ứng tốt các tiêu chí đánh giá."
        elif status == "CONDITIONAL_APPROVAL":
            reasoning += "Hồ sơ cần bổ sung một số điều kiện để được duyệt."
        else:
            reasoning += "Hồ sơ chưa đáp ứng các tiêu chí tối thiểu."
            
        return reasoning
