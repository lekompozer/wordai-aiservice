"""
Request and Response Models for the FastAPI application
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


# ===== CHAT MODELS =====
class QuestionRequest(BaseModel):
    question: str
    userId: Optional[str] = None
    deviceId: Optional[str] = None
    # ❌ REMOVED: session_id - causes complexity and message mixing bugs
    tone: Optional[str] = None


class ChatWithFilesRequest(BaseModel):
    question: str
    files: List[str]  # List of base64 encoded files
    file_names: List[str]  # List of file names
    file_types: List[str]  # List of file types
    # ❌ REMOVED: session_id - simplify chat flow
    userId: Optional[str] = None
    tone: Optional[str] = None

    class Config:
        # Allow large file uploads
        str_max_length = 50 * 1024 * 1024  # 50MB


# ===== REAL ESTATE MODELS =====
class RealEstateAnalysisRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    userId: Optional[str] = None


class RealEstateAnalysisResponse(BaseModel):
    success: bool
    response: str
    analysis_data: Optional[Dict[str, Any]] = None
    search_results: Optional[List[Dict[str, Any]]] = None
    session_id: Optional[str] = None
    error: Optional[str] = None


# ===== OCR MODELS =====
class CCCDOCRRequest(BaseModel):
    image: str  # base64 encoded image
    image_type: Optional[str] = "base64"


class CCCDOCRResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None


# ===== LOAN ASSESSMENT MODELS =====
class LoanAssessmentRequest(BaseModel):
    # Personal Information
    full_name: str
    age: int
    phone: str
    email: str
    address: str
    marital_status: str
    dependents: int

    # Financial Information
    monthly_income: float
    monthly_expenses: float
    current_debt: float
    employment_type: str
    employment_duration: int

    # Loan Information
    loan_amount: float
    loan_purpose: str
    loan_term: int

    # Additional Information
    assets: Optional[str] = None
    credit_history: Optional[str] = None
    guarantor: Optional[str] = None
    additional_notes: Optional[str] = None


class LoanAssessmentResponse(BaseModel):
    success: bool
    assessment_id: str
    decision: str  # APPROVED, REJECTED, REVIEW_REQUIRED
    confidence_score: float
    risk_level: str  # LOW, MEDIUM, HIGH
    recommended_amount: Optional[float] = None
    recommended_rate: Optional[float] = None
    recommended_term: Optional[int] = None
    analysis: Dict[str, Any]
    conditions: Optional[List[str]] = None
    next_steps: Optional[List[str]] = None
    processing_time: float
    timestamp: str
    error: Optional[str] = None


# ===== HEALTH CHECK MODELS =====
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    environment: str
    version: str
    uptime: float
    providers: Dict[str, Any]
    database: Dict[str, Any]


class StatusResponse(BaseModel):
    server: str
    environment: str
    timestamp: str
    uptime: str
