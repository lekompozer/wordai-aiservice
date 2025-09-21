"""
📦 MODELS PACKAGE
Centralized models cho toàn bộ application
"""

# Loan models
from .loan_models import (
    IDCardInfo,
    ExistingLoan,
    LoanApplicationRequest,
    LoanAssessmentResponse,
    validate_loan_application_minimal,
    get_safe_value,
    build_assessment_context
)

# OCR models  
from .ocr_models import (
    CCCDImageRequest,
    CCCDOCRResponse,
    OCRRequest
)

# Chat models
from .chat_models import (
    QuestionRequest,
    ChatWithFilesRequest
)

__all__ = [
    # Loan models
    "IDCardInfo",
    "ExistingLoan", 
    "LoanApplicationRequest",
    "LoanAssessmentResponse",
    "validate_loan_application_minimal",
    "get_safe_value",
    "build_assessment_context",
    
    # OCR models
    "CCCDImageRequest",
    "CCCDOCRResponse", 
    "OCRRequest",
    
    # Chat models
    "QuestionRequest",
    "ChatWithFilesRequest"
]