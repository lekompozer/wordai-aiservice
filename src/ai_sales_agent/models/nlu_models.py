"""
NLU Request/Response Models for AI Sales Agent
"""
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from enum import Enum

class StepSubQuestion(str, Enum):
    """Enum for step sub-questions"""
    # Step 1: Loan Information
    STEP_1_1 = "1.1"  # Main loan info: amount, term, purpose
    STEP_1_2 = "1.2"  # Additional info: type, agent code
    
    # Step 2: Personal Information  
    STEP_2_1 = "2.1"  # Basic info: name, phone, birth year
    STEP_2_2 = "2.2"  # Additional info: gender, marital, dependents, email
    
    # Step 3: Collateral Information
    STEP_3_1 = "3.1"  # Collateral type and info
    STEP_3_2 = "3.2"  # Collateral value and images
    
    # Step 4: Financial Information
    STEP_4_1 = "4.1"  # Main income
    STEP_4_2 = "4.2"  # Job information
    STEP_4_3 = "4.3"  # Other income and assets (optional)
    
    # Step 5: Debt Information
    STEP_5_1 = "5.1"  # Existing debt check
    STEP_5_2 = "5.2"  # Debt details (conditional)
    
    # Step 6: Confirmation
    STEP_6 = "6"      # Summary confirmation
    
    # Step 7: Assessment
    STEP_7 = "7"      # Loan assessment processing

class NLURequest(BaseModel):
    """Request model for NLU extraction"""
    step: Union[int, str] = Field(..., description="Step number (1, 2) or sub-step (1.1, 1.2, 2.1, 2.2)")
    stepName: str = Field(..., description="Name of the current step/sub-step")
    userMessage: str = Field(..., description="User's input message")
    requiredFields: List[str] = Field(..., description="Required fields for this sub-step")
    optionalFields: List[str] = Field(default=[], description="Optional fields for this sub-step")
    currentData: Dict[str, Any] = Field(default={}, description="Data collected so far")
    validationRules: Dict[str, Dict[str, Any]] = Field(default={}, description="Validation rules for fields")

class ExtractedField(BaseModel):
    """Single extracted field with confidence"""
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(default="", description="Part of text where value was found")

class NLUResponse(BaseModel):
    """Response model for NLU processing"""
    sessionId: str
    response: str
    currentStep: StepSubQuestion
    extractedFields: Dict[str, Any] = {}
    isCompleted: bool = False
    nextStep: Optional[StepSubQuestion] = None
    missingFields: List[str] = []
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)

# New models for Step 6/7 processing
class ProcessRequest(BaseModel):
    """Request model for processing assessment steps"""
    sessionId: str = Field(..., description="Session identifier")
    userMessage: str = Field(..., description="User's message/response")

class ProcessResponse(BaseModel):
    """Response model for processing assessment steps"""
    sessionId: str
    currentStep: StepSubQuestion
    nextStep: Optional[StepSubQuestion] = None
    extractedData: Dict[str, Any] = {}
    missingFields: List[str] = []
    aiResponse: str
    isComplete: bool = False
    assessmentResult: Optional[Dict[str, Any]] = None

# Step configurations
STEP_CONFIGS = {
    "1.1": {
        "name": "Thông tin khoản vay chính",
        "requiredFields": ["loanAmount", "loanTerm", "loanPurpose"],
        "optionalFields": [],
        "nextStep": "1.2"
    },
    "1.2": {
        "name": "Thông tin khoản vay bổ sung",
        "requiredFields": ["loanType"],
        "optionalFields": ["salesAgentCode"],
        "nextStep": "2.1"
    },
    "2.1": {
        "name": "Thông tin cá nhân cơ bản",
        "requiredFields": ["fullName", "phoneNumber", "birthYear"],
        "optionalFields": [],
        "nextStep": "2.2"
    },
    "2.2": {
        "name": "Thông tin cá nhân bổ sung",
        "requiredFields": ["gender", "maritalStatus", "dependents"],
        "optionalFields": ["email"],
        "nextStep": "3.1"
    },
    
    # Step 3: Collateral Information
    "3.1": {
        "name": "Thông tin tài sản đảm bảo - Loại và mô tả",
        "requiredFields": ["collateralType", "collateralInfo"],
        "optionalFields": [],
        "nextStep": "3.2"
    },
    "3.2": {
        "name": "Thông tin tài sản đảm bảo - Giá trị",
        "requiredFields": ["collateralValue"],
        "optionalFields": ["collateralImage"],
        "nextStep": "4.1"
    },
    
    # Step 4: Financial Information
    "4.1": {
        "name": "Thông tin tài chính - Thu nhập chính",
        "requiredFields": ["monthlyIncome", "primaryIncomeSource"],
        "optionalFields": [],
        "nextStep": "4.2"
    },
    "4.2": {
        "name": "Thông tin tài chính - Công việc",
        "requiredFields": ["companyName", "jobTitle", "workExperience"],
        "optionalFields": [],
        "nextStep": "4.3"
    },
    "4.3": {
        "name": "Thông tin tài chính - Thu nhập khác và tài sản",
        "requiredFields": [],
        "optionalFields": ["otherIncomeAmount", "totalAssets", "liquidAssets", "bankName", "bankAccount"],
        "nextStep": "5.1"
    },
    
    # Step 5: Debt Information
    "5.1": {
        "name": "Thông tin nợ - Kiểm tra nợ hiện tại",
        "requiredFields": ["hasExistingDebt"],
        "optionalFields": [],
        "nextStep": "5.2"  # Conditional based on hasExistingDebt
    },
    "5.2": {
        "name": "Thông tin nợ - Chi tiết dư nợ",
        "requiredFields": ["totalDebtAmount", "monthlyDebtPayment"],
        "optionalFields": ["cicCreditScore", "cicCreditScoreGroup"],
        "nextStep": "6"
    },
    
    # Step 6: Confirmation
    "6": {
        "name": "Xác nhận thông tin tổng hợp", 
        "requiredFields": ["userConfirmation"],
        "optionalFields": ["corrections"],
        "nextStep": "7"
    },
    
    # Step 7: Assessment
    "7": {
        "name": "Thẩm định hồ sơ vay tự động",
        "requiredFields": [],
        "optionalFields": [],
        "nextStep": None  # Final step
    }
}
