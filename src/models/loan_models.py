"""
📋 LOAN APPLICATION MODELS
Flexible models cho loan assessment với optional fields
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class IDCardInfo(BaseModel):
    """Thông tin CCCD/CMND - Tất cả optional"""
    idNumber: Optional[str] = None
    fullName: Optional[str] = None
    dateOfBirth: Optional[datetime] = None
    gender: Optional[str] = None
    nationality: Optional[str] = "Việt Nam"
    placeOfOrigin: Optional[str] = None
    permanentAddress: Optional[str] = None
    dateOfIssue: Optional[datetime] = None
    placeOfIssue: Optional[str] = None
    expirationDate: Optional[datetime] = None
    ethnicity: Optional[str] = None
    religion: Optional[str] = None
    ocrConfidence: Optional[float] = None
    ocrProcessedAt: Optional[datetime] = None

class ExistingLoan(BaseModel):
    """Thông tin khoản vay hiện tại"""
    lender: Optional[str] = None
    amount: Optional[int] = 0  # VNĐ
    monthlyPayment: Optional[int] = 0  # VNĐ
    remainingTerm: Optional[str] = None

class LoanApplicationRequest(BaseModel):
    """
    ✅ FLEXIBLE LOAN APPLICATION REQUEST
    Chỉ applicationId và loanAmount là required
    Tất cả fields khác đều optional với default values
    """
    
    # ✅ REQUIRED CORE FIELDS ONLY
    applicationId: str
    loanAmount: int  # VNĐ - REQUIRED
    
    # ✅ OPTIONAL WITH SMART DEFAULTS
    userId: Optional[str] = None
    deviceId: Optional[str] = None
    
    # Application Progress
    currentStep: Optional[int] = 1
    status: Optional[str] = "submitted"
    createdAt: Optional[datetime] = Field(default_factory=datetime.now)
    submittedAt: Optional[datetime] = None
    
    # Step 1: Loan Information
    loanType: Optional[str] = "Thế chấp"
    loanTerm: Optional[str] = "15 năm"
    loanPurpose: Optional[str] = "Mua nhà ở"
    
    # Step 2: Personal Information - ALL OPTIONAL
    phoneNumber: Optional[str] = None
    email: Optional[str] = None
    maritalStatus: Optional[str] = "Chưa cung cấp"
    dependents: Optional[int] = 0
    idCardInfo: Optional[IDCardInfo] = None
    
    # Step 3: Collateral Information - ALL OPTIONAL
    collateralType: Optional[str] = "Bất động sản"
    collateralInfo: Optional[str] = "Chưa có thông tin chi tiết"
    collateralValue: Optional[int] = 0  # VNĐ
    
    # Step 4: Financial Information
    monthlyIncome: Optional[int] = 0  # VNĐ
    primaryIncomeSource: Optional[str] = "Chưa cung cấp"
    companyName: Optional[str] = "Chưa cung cấp"
    jobTitle: Optional[str] = "Chưa cung cấp"
    workExperience: Optional[int] = 0  # years
    otherIncome: Optional[str] = None
    otherIncomeAmount: Optional[int] = 0
    
    # Banking info - OPTIONAL
    bankAccount: Optional[str] = "Chưa cung cấp"
    bankName: Optional[str] = "Chưa cung cấp"
    
    # Assets - OPTIONAL
    totalAssets: Optional[int] = 0  # VNĐ
    liquidAssets: Optional[int] = 0  # VNĐ
    
    # Step 5: Debt Information - ALL OPTIONAL
    hasExistingDebt: Optional[bool] = False
    totalDebtAmount: Optional[int] = 0  # VNĐ
    monthlyDebtPayment: Optional[int] = 0  # VNĐ
    cicCreditScoreGroup: Optional[str] = "Chưa xác định"
    creditHistory: Optional[str] = "Chưa có thông tin"
    existingLoans: Optional[List[ExistingLoan]] = Field(default_factory=list)
    
    # Administrative Fields - ALL OPTIONAL
    ipAddress: Optional[str] = None
    userAgent: Optional[str] = None
    termsAccepted: Optional[bool] = True
    termsAcceptedAt: Optional[datetime] = Field(default_factory=datetime.now)
    privacyPolicyAccepted: Optional[bool] = True
    dataProcessingConsent: Optional[bool] = True

    # ✅ AI SALES AGENT EXTENDED FIELDS
    
    # Personal Information Extended (for AI extraction)
    fullName: Optional[str] = None  # Match AI extraction
    birthYear: Optional[int] = None  # Age calculation 
    gender: Optional[str] = None    # Match AI extraction
    phoneCountryCode: Optional[str] = "+84"  # International support
    
    # Banking Services (for unsecured loans assessment)
    hasCreditCard: Optional[bool] = False
    creditCardLimit: Optional[int] = 0  # VNĐ
    hasSavingsAccount: Optional[bool] = False
    savingsAmount: Optional[int] = 0  # VNĐ
    
    # Property Information (for large loans)
    hasProperty: Optional[bool] = False
    propertyValue: Optional[int] = 0  # VNĐ
    hasCar: Optional[bool] = False
    carValue: Optional[int] = 0  # VNĐ
    
    # AI Conversation Context
    conversationHistory: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    isFromChat: Optional[bool] = False  # Flag for chat-based applications
    salesAgentCode: Optional[str] = None  # Sales agent identifier
    messageCount: Optional[int] = 0  # Number of conversation exchanges
    
    # Document/Images Status
    hasCollateralImage: Optional[bool] = False
    collateralImageUrl: Optional[str] = None
    hasBankStatement: Optional[bool] = False
    bankStatementUrl: Optional[str] = None

class LoanAssessmentResponse(BaseModel):
    """Response model cho loan assessment"""
    success: bool
    applicationId: str
    assessmentId: Optional[str] = None
    
    # Assessment Result
    status: Optional[str] = None  # approved/rejected/needs_review
    confidence: Optional[float] = None
    creditScore: Optional[int] = None
    reasoning: Optional[str] = None
    
    # Financial Analysis
    riskFactors: Optional[List[str]] = None
    recommendations: Optional[List[str]] = None
    approvedAmount: Optional[int] = None
    interestRate: Optional[float] = None
    monthlyPayment: Optional[int] = None
    loanToValue: Optional[float] = None
    debtToIncome: Optional[float] = None
    conditions: Optional[List[str]] = None
    
    # Additional Analysis
    collateralValuation: Optional[Dict[str, Any]] = None
    financialAnalysis: Optional[Dict[str, Any]] = None
    
    # Processing Details
    processingDetails: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # ✅ AI SALES AGENT RESPONSE ENHANCEMENTS
    nextSteps: Optional[List[str]] = None  # Next actions for customer
    documentRequirements: Optional[List[str]] = None  # Required documents
    estimatedProcessingTime: Optional[str] = None  # Processing timeline
    contactInfo: Optional[Dict[str, str]] = None  # Contact information
    conversationSummary: Optional[str] = None  # Summary of conversation

# ✅ VALIDATION UTILITIES
def validate_loan_application_minimal(data: dict) -> tuple[bool, List[str]]:
    """
    Validate minimal required fields for loan application
    Returns: (is_valid, error_messages)
    """
    errors = []
    
    # Check required fields
    if not data.get('applicationId'):
        errors.append("applicationId is required")
    
    if not data.get('loanAmount') or data.get('loanAmount', 0) <= 0:
        errors.append("loanAmount must be greater than 0")
    
    # Check data types if provided
    if data.get('loanAmount') and not isinstance(data.get('loanAmount'), int):
        errors.append("loanAmount must be an integer")
    
    return len(errors) == 0, errors

def get_safe_value(data: dict, key: str, default_value: Any) -> Any:
    """Safely get value from dict with default"""
    value = data.get(key)
    if value is None or value == "":
        return default_value
    return value

def build_assessment_context(loan_data: dict) -> str:
    """
    Build context string for loan assessment
    
    Args:
        loan_data: Loan application data
        
    Returns:
        Formatted context string for AI assessment
    """
    context_parts = []
    
    # Basic loan information
    if loan_data.get('loanAmount'):
        context_parts.append(f"Số tiền vay: {loan_data['loanAmount']:,} VND")
    
    if loan_data.get('loanPurpose'):
        context_parts.append(f"Mục đích vay: {loan_data['loanPurpose']}")
    
    if loan_data.get('loanTerm'):
        context_parts.append(f"Thời hạn vay: {loan_data['loanTerm']} tháng")
    
    # Income information
    if loan_data.get('monthlyIncome'):
        context_parts.append(f"Thu nhập hàng tháng: {loan_data['monthlyIncome']:,} VND")
    
    if loan_data.get('additionalIncome'):
        context_parts.append(f"Thu nhập bổ sung: {loan_data['additionalIncome']:,} VND")
    
    # Employment information
    if loan_data.get('employmentType'):
        context_parts.append(f"Loại hình công việc: {loan_data['employmentType']}")
    
    if loan_data.get('workExperience'):
        context_parts.append(f"Kinh nghiệm làm việc: {loan_data['workExperience']} năm")
    
    # Existing obligations
    if loan_data.get('existingLoans'):
        loans = loan_data['existingLoans']
        if loans:
            context_parts.append(f"Khoản vay hiện có: {len(loans)} khoản")
            total_debt = sum(loan.get('remainingBalance', 0) for loan in loans)
            if total_debt > 0:
                context_parts.append(f"Tổng dư nợ: {total_debt:,} VND")
    
    return "\n".join(context_parts)

